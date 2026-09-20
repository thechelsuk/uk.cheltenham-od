#!/usr/bin/env python3
"""One-off backfill for Cheltenham's historical Council Tax stock of
properties total (1993-2024), written to _data/council-tax-stock-history.json.

Run manually with `python _python/local/council-tax-stock-history-backfill.py`.
This is NOT part of any scheduled workflow. The VOA's CTSOP1.1 time-series
archive is a ~130MB zip of one ~4MB CSV per year for the whole of England and
Wales, which is too heavy to re-download on every scheduled run just to read
one Cheltenham row per year. Since 1993-2024 is now a fixed, closed series
(the VOA's newer annual releases are single-year snapshots, not an updated
time series — see housing-supply.py), run this once to seed the history,
then housing-supply.py appends each new year's snapshot on top of it."""
import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "_data", "council-tax-stock-history.json")

SERIES_PAGE_URL = "https://www.gov.uk/government/statistics/council-tax-stock-of-properties-2024"
ECODE = "E07000078"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}


def find_series_zip_url():
    resp = requests.get(SERIES_PAGE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    match = re.search(r'href="(https://assets\.publishing\.service\.gov\.uk/media/[^"]+CTSOP1-1-1993-2024\.zip)"', resp.text)
    if not match:
        raise SystemExit("Could not find the CTSOP1.1 1993-2024 time-series zip link on the page")
    return match.group(1)


def main():
    zip_url = find_series_zip_url()
    resp = requests.get(zip_url, headers=HEADERS, timeout=120)
    resp.raise_for_status()

    years = []
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            match = re.search(r"CTSOP1_1_(\d{4})_\d{2}_\d{2}\.csv$", name)
            if not match:
                continue
            year = int(match.group(1))
            with zf.open(name) as f:
                reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    if row.get("ecode") == ECODE:
                        years.append({
                            "year": year,
                            "all_properties": int(row["all_properties"]),
                        })
                        break

    years.sort(key=lambda y: y["year"])

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "One-off backfill of the closed 1993-2024 VOA time series. Not refreshed on a schedule.",
        "source_url": zip_url,
        "years": years,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(years)} years of council tax stock history to {OUT}")


if __name__ == "__main__":
    main()
