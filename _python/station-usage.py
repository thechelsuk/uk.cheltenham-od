#!/usr/bin/env python3
"""Fetch Cheltenham Spa's annual passenger numbers from the Office of Rail and
Road's "estimates of station usage" (Table 1410) and write
_data/station-usage.json.

ORR publishes one CSV a year, each replacing the last under a new media ID, so
the current link is scraped from the statistics page (as toilets.py does for
the Toilet Map) rather than hardcoded. Runs monthly, which is plenty for
figures that change once a year.
"""
import csv
import io
import json
import os
import re
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "station-usage.json")

PAGE_URL = "https://dataportal.orr.gov.uk/statistics/usage/estimates-of-station-usage"
BASE_URL = "https://dataportal.orr.gov.uk"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

CRS = "CNM"   # Cheltenham Spa

LINK_PATTERN = re.compile(r'href="([^"]*table-1410[^"]*\.csv)"')
PERIOD_PATTERN = re.compile(r"annual data, (.+)$")


def find_csv_url():
    resp = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = LINK_PATTERN.search(resp.text)
    if not match:
        raise ValueError(f"No Table 1410 CSV link found on {PAGE_URL} — page markup may have changed.")
    href = match.group(1)
    return href if href.startswith("http") else BASE_URL + href


def to_int(value):
    """'2,418,292' -> 2418292; '[z]' (not applicable) or blank -> None."""
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else None


def display(n):
    """2418292 -> '2,418,292' (empty string when the source had no figure).
    Layouts print these *_display fields rather than formatting in Liquid."""
    return f"{n:,}" if n is not None else ""


def parse_row(rows, crs):
    """Return (period, row_dict) for the station with the given three-letter code."""
    title = rows[0][0] if rows and rows[0] else ""
    period_match = PERIOD_PATTERN.search(title)
    period = period_match.group(1).strip() if period_match else ""

    header_index = next(i for i, r in enumerate(rows) if r and r[0].strip() == "Station name")
    header = [re.sub(r"\s+", " ", h).strip() for h in rows[header_index]]
    for row in rows[header_index + 1:]:
        record = dict(zip(header, row))
        if record.get("Three Letter Code (TLC)") == crs:
            return period, record
    raise ValueError(f"Station {crs} not found in the ORR table")


def main():
    csv_url = find_csv_url()
    resp = requests.get(csv_url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    period, record = parse_row(rows, CRS)

    entries_exits = {
        "all": to_int(record.get("Entries and exits: All tickets")),
        "full_price": to_int(record.get("Entries and exits: Full price tickets")),
        "reduced_price": to_int(record.get("Entries and exits: Reduced price tickets")),
        "season": to_int(record.get("Entries and exits: Season tickets")),
    }
    rank = to_int(record.get("Entries and exits: Rank"))
    interchanges = to_int(record.get("Interchanges"))
    main_journeys = to_int(record.get("Number of journeys to or from main origin or destination station"))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Office of Rail and Road, estimates of station usage",
        "source_url": PAGE_URL,
        "licence": "Not confirmed here — check the ORR Data Portal terms before reuse",
        "csv_url": csv_url,
        "period": period,
        "station": {
            "name": record["Station name"],
            "crs": CRS,
            "region": record.get("Region", ""),
            "facility_owner": record.get("Station facility owner", ""),
            "entries_exits": entries_exits,
            "entries_exits_display": {k: display(v) for k, v in entries_exits.items()},
            "rank": rank,
            "rank_display": display(rank),
            "interchanges": interchanges,
            "interchanges_display": display(interchanges),
            "main_destination": record.get("Main origin or destination station", ""),
            "main_destination_journeys": main_journeys,
            "main_destination_journeys_display": display(main_journeys),
        },
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {period} usage for {record['Station name']} to {OUT}")


if __name__ == "__main__":
    main()
