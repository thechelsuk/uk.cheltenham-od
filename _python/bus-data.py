import csv
import datetime
import io
import json
import pathlib
import re
import zipfile

import requests

# -- Configuration ------------------------------------------------------------

CATALOGUE_URL = "https://data.bus-data.dft.gov.uk/catalogue/"
SOURCE_PAGE   = "https://data.bus-data.dft.gov.uk/"
TIMETABLES_CSV = "timetables_data_catalogue.csv"

# A route "serves Cheltenham" if the town name appears in any of these fields.
MATCH_FIELDS = [
    "OTC:Origin", "OTC:Destination", "OTC:Via",
    "OTC:Start Point", "OTC:Finish Point",
]
MATCH_TERM = "cheltenham"

ATTENTION_LABELS = {
    "Up to date":                             "Up to date",
    "OTC variation not published":            "Registration change not published",
    "42 day look ahead is incomplete":        "Timetable doesn't look far enough ahead",
    "Service hasn't been updated within a year": "Not updated in over a year",
}

# BODS source data is a mix of ALL CAPS and Title Case. Normalise to Title
# Case, keeping known acronyms and anything with a digit (road refs like A40,
# B4063) upper-case — same approach as toilets.py's clean_name.
ACRONYMS = {"UK", "LLP", "PLC"}


def clean_name(name):
    """Tidy an operator/place name: collapse stray whitespace, title-case each
    word (including inside brackets), and keep known acronyms and anything
    containing a digit (A40, B4063, 80-86) upper-case."""
    def fix(w):
        lead, core, trail = re.match(r"(\W*)(.*?)(\W*)$", w).groups()
        if core.upper() in ACRONYMS or any(c.isdigit() for c in core):
            core = core.upper()
        elif core:
            core = core[:1].upper() + core[1:].lower()
        return lead + core + trail

    name = re.sub(r"(?<! )- ", " - ", name or "")
    return " ".join(fix(w) for w in name.split())


def fetch_catalogue_zip():
    """Download and return the BODS data catalogue zip as bytes."""
    resp = requests.get(CATALOGUE_URL, timeout=(10, 120))
    resp.raise_for_status()
    return resp.content


def load_timetables_csv(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(TIMETABLES_CSV))
        with zf.open(name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig")
            return list(csv.DictReader(text))


def row_serves_cheltenham(row):
    return any(MATCH_TERM in (row.get(field) or "").lower() for field in MATCH_FIELDS)


def timeliness_label(row):
    status = row.get("Timeliness Status") or ""
    for key, label in ATTENTION_LABELS.items():
        if key in status:
            return label
    return status or "Unknown"


if __name__ == "__main__":
    out_path = pathlib.Path(__file__).parent.parent / "_data" / "bus-routes.json"

    print("Downloading BODS data catalogue...")
    zip_bytes = fetch_catalogue_zip()
    print(f"  {len(zip_bytes):,} bytes")

    print("Extracting timetables data catalogue...")
    rows = load_timetables_csv(zip_bytes)
    print(f"  {len(rows):,} total rows in national catalogue")

    local_rows = [r for r in rows if row_serves_cheltenham(r)]
    print(f"  {len(local_rows)} rows mention Cheltenham")

    routes = []
    for r in local_rows:
        requires_attention = (r.get("Requires Attention") or "").strip().lower() == "yes"
        routes.append({
            "service_number": r.get("OTC:Service Number") or r.get("XML:Line Name") or "",
            "operator":       clean_name(r.get("OTC:Operator Name") or r.get("Organisation Name") or "Unknown"),
            "start_point":    clean_name(r.get("OTC:Start Point") or r.get("OTC:Origin") or ""),
            "finish_point":   clean_name(r.get("OTC:Finish Point") or r.get("OTC:Destination") or ""),
            "via":            clean_name(r.get("OTC:Via") or ""),
            "requires_attention": requires_attention,
            "published_status":   r.get("Published Status") or "",
            "timeliness":         timeliness_label(r),
            "authority":          r.get("Local Transport Authority") or "",
            "last_modified":      (r.get("XML:Last Modified Date") or "")[:10],
        })

    # De-dupe identical service number + operator + start/finish combos (variations of the same route).
    seen = {}
    for route in routes:
        key = (route["service_number"], route["operator"], route["start_point"], route["finish_point"])
        existing = seen.get(key)
        if existing is None or route["last_modified"] > existing["last_modified"]:
            seen[key] = route
    routes = sorted(seen.values(), key=lambda r: (r["operator"].lower(), r["service_number"]))

    attention_count = sum(1 for r in routes if r["requires_attention"])
    operators = sorted({r["operator"] for r in routes})

    payload = {
        "updated":          datetime.datetime.now().strftime("%-d %B %Y at %H:%M"),
        "updated_iso":      datetime.date.today().isoformat(),
        "source":           SOURCE_PAGE,
        "source_catalogue": CATALOGUE_URL,
        "total_routes":     len(routes),
        "attention_count":  attention_count,
        "operator_count":   len(operators),
        "operators":        operators,
        "routes":           routes,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {len(routes)} routes to {out_path}")
