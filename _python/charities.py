#!/usr/bin/env python3
"""Registered charities based in Cheltenham, written to _data/charities.json.

The source is the Charity Commission for England and Wales's full register
download: a daily extract of every charity, plus a file of each charity's
classifications (what it does, who it helps). Main charities (not linked
subsidiaries) that are still registered and give a contact postcode in the
Cheltenham postcode districts are kept.

A small charity's contact details are often a trustee's home address, phone
and email, so none of them are published: only the charity's name, number,
finances, activities, its own site and the postcode district it gives.

The register changes a little every day; a monthly refresh is plenty.
"""
import csv
import io
import os
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone

import config
import helper

# Some free-text fields (activities, objects) run past csv's default limit.
csv.field_size_limit(10**8)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "charities.json")

EXTRACT = "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/txt/publicextract.{}.zip"
REGISTER_URL = "https://register-of-charities.charitycommission.gov.uk/en/charity-search/-/charity-details/{}"
SOURCE_URL = "https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download"

ACRONYMS = helper.DEFAULT_ACRONYMS | {
    "YMCA", "YWCA", "PTA", "PCC", "CIO", "RAF", "NHS", "GCHQ", "SEND", "CIC", "UCAS", "RNLI", "RSPB", "RSPCA",
}
SMALL_WORDS = {"of", "and", "the", "for", "in", "at", "on", "to", "with", "by", "a", "an", "or"}
INCOME_BANDS = (
    (0, "Under £10,000"),
    (10_000, "£10,000 to £100,000"),
    (100_000, "£100,000 to £1 million"),
    (1_000_000, "£1 million or more"),
)


def rows(name):
    """The rows of one tab-separated file from the register download."""
    data = helper.get(EXTRACT.format(name), timeout=300).content
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        with archive.open(archive.namelist()[0]) as f:
            yield from csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"), delimiter="\t")


def tidy(name):
    """Register names are in capitals: 'FRIENDS OF THE 1ST CHELTENHAM' ->
    'Friends of the 1st Cheltenham'."""
    words = helper.clean_name(name, ACRONYMS).split()
    words = [w.lower() if i and w.lower() in SMALL_WORDS else hyphenated(w) for i, w in enumerate(words)]
    return re.sub(r"\b(\d+)(ST|ND|RD|TH)\b", lambda m: m.group(1) + m.group(2).lower(), " ".join(words))


def hyphenated(word):
    """'Stow-on-the-wold' -> 'Stow-on-the-Wold'."""
    parts = word.split("-")
    if len(parts) < 2:
        return word
    return "-".join(p if i == 0 or p.lower() in SMALL_WORDS else p[:1].upper() + p[1:] for i, p in enumerate(parts))


def sentence(text):
    """Activities are often in capitals too; give them sentence case."""
    text = " ".join((text or "").split())
    if text.isupper():
        text = text.lower()
        text = text[:1].upper() + text[1:]
    return text


def website(url):
    url = (url or "").strip()
    if not url:
        return None
    return url if re.match(r"^https?://", url, re.I) else "https://" + url


def money(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def band(income):
    if income is None:
        return None
    return [label for floor, label in INCOME_BANDS if income >= floor][-1]


def main():
    charities = {}
    for row in rows("charity"):
        postcode = (row["charity_contact_postcode"] or "").strip().upper()
        if (row["charity_registration_status"] != "Registered" or row["linked_charity_number"] != "0"
                or postcode.split(" ")[0] not in config.POSTCODE_DISTRICTS):
            continue
        income = money(row["latest_income"])
        spending = money(row["latest_expenditure"])
        number = row["registered_charity_number"]
        charities[row["organisation_number"]] = {
            "number": number,
            "name": tidy(row["charity_name"]),
            "district": postcode.split(" ")[0],
            "registered": (row["date_of_registration"] or "")[:10] or None,
            "year_end": (row["latest_acc_fin_period_end_date"] or "")[:10] or None,
            "income": income,
            "income_display": f"£{income:,}" if income is not None else None,
            "spending": spending,
            "spending_display": f"£{spending:,}" if spending is not None else None,
            "income_band": band(income),
            "activities": sentence(row["charity_activities"]) or None,
            "website": website(row["charity_contact_web"]),
            # The register's page address takes the Commission's internal
            # organisation number; for older charities it equals the charity
            # number, for newer ones it doesn't.
            "register_url": REGISTER_URL.format(row["organisation_number"]),
            "causes": [],
        }

    for row in rows("charity_classification"):
        charity = charities.get(row["organisation_number"])
        if charity and row["classification_type"] == "What":
            cause = row["classification_description"].strip().lower()   # labels are inconsistently cased
            charity["causes"].append(cause[:1].upper() + cause[1:])

    items = sorted(charities.values(), key=lambda c: c["name"].lower())
    total = sum(c["income"] or 0 for c in items)
    causes = Counter(cause for c in items for cause in c["causes"])
    bands = Counter(c["income_band"] for c in items if c["income_band"])
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Charity Commission for England and Wales",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "summary": {
            "count": len(items),
            "total_income": total,
            "total_income_display": f"£{total / 1_000_000:,.1f} million",
            "over_million": bands["£1 million or more"],
            "income_bands": [{"band": label, "count": bands[label]} for _, label in INCOME_BANDS],
            "causes": [{"cause": cause, "count": count} for cause, count in causes.most_common()],
        },
        "charities": items,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(items)} charities to {OUT}")


if __name__ == "__main__":
    main()
