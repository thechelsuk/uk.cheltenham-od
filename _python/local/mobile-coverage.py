#!/usr/bin/env python3
"""Extract Cheltenham's row from Ofcom's Connected Nations mobile coverage
release and write _data/mobile-coverage.json. Ofcom only publishes mobile
coverage at local authority / parliamentary constituency / devolved
constituency level (no postcode-level file, unlike fixed broadband), so this
is a single constituency-wide summary. Run manually after dropping a new
release CSV into _data-sources/ (roughly twice a year) — not part of any
scheduled workflow, since that gitignored input file only exists locally.
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_CSV = os.path.join(HERE, "..", "..", "_data-sources", "202601_mobile_coverage_pcon_r01.csv")
OUT = os.path.join(HERE, "..", "..", "_data", "mobile-coverage.json")

SOURCE_URL = "https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/connected-nations-update-spring-2026"
CONSTITUENCY_NAME = "Cheltenham"
REFERENCE_DATE = "2026-01-01"  # Ofcom's stated reference date for this release

# (key, label, has_indoor)
SERVICES = [
    ("2G", "2G", True),
    ("3G", "3G", True),
    ("4G", "4G", True),
    ("Voice", "Voice calls", True),
    ("5G_high_confidence", "5G (high confidence)", False),
    ("5G_very_high_confidence", "5G (very high confidence)", False),
    ("5G_SA_high_confidence", "5G Standalone (high confidence)", False),
    ("5G_SA_very_high_confidence", "5G Standalone (very high confidence)", False),
]


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def at_least_one(row, prefix):
    """100% minus the share with coverage from zero operators (Ofcom's own formula)."""
    return round(100 - to_float(row.get(f"{prefix}_0")), 1)


def none_pct(row, prefix):
    return round(to_float(row.get(f"{prefix}_0")), 1)


def all_operators(row, prefix, service_key):
    # 2G tops out at 3 operators, 3G and 5G SA effectively fewer — only report
    # an "all networks" figure for services where a 4-operator column is
    # meaningful (i.e. not left blank/zero by design).
    if service_key in ("2G", "3G"):
        return None
    value = row.get(f"{prefix}_4")
    if value in (None, ""):
        return None
    return round(to_float(value), 1)


def build_services(row):
    services = []
    for key, label, has_indoor in SERVICES:
        entry = {
            "key": key,
            "label": label,
            "outdoor_at_least_one": at_least_one(row, f"{key}_prem_out"),
            "outdoor_none": none_pct(row, f"{key}_prem_out"),
            "outdoor_all_operators": all_operators(row, f"{key}_prem_out", key),
            "geographic_at_least_one": at_least_one(row, f"{key}_geo_out"),
            "geographic_none": none_pct(row, f"{key}_geo_out"),
        }
        if has_indoor:
            entry["indoor_at_least_one"] = at_least_one(row, f"{key}_prem_in")
            entry["indoor_none"] = none_pct(row, f"{key}_prem_in")
            entry["indoor_all_operators"] = all_operators(row, f"{key}_prem_in", key)
        else:
            entry["indoor_at_least_one"] = None
            entry["indoor_none"] = None
            entry["indoor_all_operators"] = None
        services.append(entry)
    return services


def main():
    if not os.path.exists(SOURCE_CSV):
        print(f"ERROR: input file not found: {SOURCE_CSV}", file=sys.stderr)
        print(
            "-> Download the Westminster parliamentary constituency mobile coverage CSV "
            "from https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/ "
            "(Connected Nations data downloads) and save it to _data-sources/.",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(SOURCE_CSV, encoding="utf-8-sig", newline="") as f:
        row = next(
            (r for r in csv.DictReader(f) if r.get("parl_const_name") == CONSTITUENCY_NAME),
            None,
        )

    if row is None:
        print(f"ERROR: no row found for '{CONSTITUENCY_NAME}' in {SOURCE_CSV}", file=sys.stderr)
        sys.exit(1)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ofcom Connected Nations",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "reference_date": REFERENCE_DATE,
        "geography": "Westminster parliamentary constituency",
        "geography_name": CONSTITUENCY_NAME,
        "premises_count": int(to_float(row.get("prem_count"))),
        "services": build_services(row),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote mobile coverage summary for {CONSTITUENCY_NAME} to {OUT}")


if __name__ == "__main__":
    main()
