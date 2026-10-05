#!/usr/bin/env python3
"""Nurseries, pre-schools and out-of-school clubs in Cheltenham, with their
latest Ofsted outcome, written to _data/childcare.json.

The source is Ofsted's childcare providers and inspections management
information on GOV.UK: one CSV of every registered childcare provider in
England and its latest inspections. Providers in the Cheltenham postcode
districts are kept. Ofsted redacts the name and address of childminders and
home childcarers, so only childcare run from non-domestic premises (and the
odd named childminder) can be listed. Postcodes are geocoded in one bulk call
to postcodes.io.

Ofsted publishes the file quarterly; the monthly run picks up each new release.
"""
import csv
import io
import os
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "childcare.json")

PAGE_URL = "https://www.gov.uk/government/statistical-data-sets/childcare-providers-and-inspections-management-information"
PAGE_API = "https://www.gov.uk/api/content/government/statistical-data-sets/childcare-providers-and-inspections-management-information"
FILE_TITLE = "childcare provider data as at"
REPORTS_URL = "https://reports.ofsted.gov.uk/provider/16/{}"

GRADES = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate"}
CARD_AREAS = (
    ("Inclusion", "EYR REIF: Most recent: Inclusion"),
    ("Curriculum and teaching", "EYR REIF: Most recent: Curriculum and teaching"),
    ("Achievement", "EYR REIF: Most recent: Achievement"),
    ("Behaviour, attitudes and routines", "EYR REIF: Most recent: Behaviour, attitudes and establishing routines"),
    ("Children's welfare and wellbeing", "EYR REIF: Most recent: Children's welfare and wellbeing"),
    ("Leadership and governance", "EYR REIF: Most recent: Leadership and governance"),
)
TYPES = {
    "Full day care": "Nursery (full day care)",
    "Sessional day care": "Pre-school (sessional care)",
    "Out-of-school day care": "Out-of-school club",
}


def latest_file():
    """The newest provider-level CSV and the date it is 'as at'."""
    attachments = helper.get(PAGE_API).json()["details"]["attachments"]

    def as_at(attachment):
        text = attachment["title"].rsplit("as at", 1)[1].strip()
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
        return datetime.min

    files = [a for a in attachments if FILE_TITLE in a.get("title", "").lower() and a["url"].endswith(".csv")]
    newest = max(files, key=as_at)
    return newest["url"], as_at(newest).date().isoformat()


def iso(text):
    text = (text or "").strip()
    return datetime.strptime(text, "%d/%m/%Y").date().isoformat() if text else None


def latest_outcome(row):
    """The provider's most recent Ofsted outcome, whichever kind of inspection it was."""
    card_date = iso(row["EYR REIF: Most recent: Inspection date"])
    if card_date:
        return {
            "kind": "report_card",
            "date": card_date,
            "outcome": "Report card",
            "safeguarding": row["EYR REIF: Most recent: Safeguarding standards met?"] or None,
            "areas": [{"area": label, "grade": row[key]} for label, key in CARD_AREAS if row[key]],
        }
    overall = GRADES.get(row["EYR OEIF/CIF: Most recent: Overall effectiveness"])
    if overall:
        return {"kind": "graded", "date": iso(row["EYR OEIF: Most recent: Full inspection date"]), "outcome": overall}
    # Out-of-school clubs and Childcare Register-only providers are checked
    # against requirements rather than graded.
    for date_key, outcome_key in (
        ("EYR OEIF OOSC: Most recent: Inspection date", "EYR OEIF OOSC: Most recent: Overall effectiveness"),
        ("CR: Most recent: Inspection date", "CR: Compliance"),
    ):
        if row[outcome_key]:
            met = row[outcome_key].startswith("Met")
            return {"kind": "requirements", "date": iso(row[date_key]),
                    "outcome": "Requirements met" if met else "Requirements not met"}
    if row["Individual register combinations"] == "VCR only":
        # Ofsted only inspects voluntary-register providers if it has concerns.
        return {"kind": "none", "date": None, "outcome": "Voluntary register"}
    return {"kind": "none", "date": None, "outcome": "Not yet inspected"}


def address(row):
    parts = [row[f"Provider address line {n}"].strip() for n in (1, 2, 3)] + [row["Provider town"].strip().title()]
    return ", ".join(p for p in parts if p)


def main():
    url, as_at = latest_file()
    text = helper.get(url, timeout=180).content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("Web link,Provider URN"))
    rows = [
        row for row in csv.DictReader(io.StringIO("\n".join(lines[header:])))
        if row["Provider postcode"][:4] in config.POSTCODE_DISTRICTS
        and row["Provider name"] != "REDACTED"
        and row["Provider status"] == "Active"
    ]
    coords = helper.geocode_postcodes({r["Provider postcode"] for r in rows})

    providers = []
    for row in rows:
        lat, lon = coords.get(row["Provider postcode"], (None, None))
        places = int(row["Places"]) if row["Places"].isdigit() else None
        providers.append({
            "urn": row["Provider URN"],
            "name": row["Provider name"].strip(),
            "type": TYPES.get(row["Provider subtype"], "Childcare"),
            "registered_person": row["Registered person name"].strip() or None,
            "address": address(row),
            "postcode": row["Provider postcode"].strip(),
            "places": places,
            "places_display": f"{places:,}" if places is not None else None,
            "registered": iso(row["Registration date"]),
            "latest": latest_outcome(row),
            "ofsted_url": REPORTS_URL.format(row["Provider URN"]),
            "distance_miles": round(helper.miles_from_centre(lat, lon), 1) if lat is not None else None,
            "lat": round(lat, 6) if lat is not None else None,
            "lon": round(lon, 6) if lon is not None else None,
        })
    providers.sort(key=lambda p: p["name"].lower())
    places = sum(p["places"] or 0 for p in providers)
    summary = {
        "providers": len(providers),
        "places": places,
        "places_display": f"{places:,}",
        "good_or_better": sum(1 for p in providers if p["latest"]["outcome"] in ("Outstanding", "Good")),
        "graded": sum(1 for p in providers if p["latest"]["kind"] in ("graded", "report_card")),
    }

    year = datetime.now(timezone.utc).year
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_at": as_at,
        "source": "Ofsted",
        "source_url": PAGE_URL,
        "licence": "Open Government Licence v3.0",
        "geocoding_source": "postcodes.io (ONS Postcode Directory)",
        "geocoding_attribution": (
            f"Contains OS data © Crown copyright and database right {year}. "
            f"Contains Royal Mail data © Royal Mail copyright and database right {year}. "
            "Source: Office for National Statistics licensed under the Open Government Licence v3.0."),
        "summary": summary,
        "providers": providers,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(providers)} childcare providers (as at {as_at}) to {OUT}")


if __name__ == "__main__":
    main()
