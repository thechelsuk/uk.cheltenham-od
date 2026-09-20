#!/usr/bin/env python3
"""Summarise Cheltenham house prices from 1995 to 2022 by year, write
_data/cheltenham-house-price-history.json.

Run manually — not part of any scheduled workflow, since the gitignored
input file only exists locally. The 1995-2022 figures never change, so run
this once; the scheduled land_registry.py fetcher covers 2022 onwards.

  python _python/local/process-land-registry-history.py --download
      Streams HM Land Registry's yearly Price Paid Data files (1995-2022,
      ~150MB each), keeps only the Cheltenham rows and saves them to
      _data-sources/pp-cheltenham-1995-2022.csv. The complete files are not
      kept — only the few tens of MB of Cheltenham rows.

  python _python/local/process-land-registry-history.py
      Summarises that file into _data/cheltenham-house-price-history.json.

The area matches land_registry.py exactly: Town/City of CHELTENHAM with a
GL50-GL54 postcode, every PPD category (A and B).

  Downloads:  https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
  Columns:    https://www.gov.uk/guidance/about-the-price-paid-data
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone
from statistics import mean, median

import requests

HERE = os.path.dirname(os.path.abspath(__file__))          # _python/local/
SRC = os.path.join(HERE, "..", "..", "_data-sources", "pp-cheltenham-1995-2022.csv")
OUT = os.path.join(HERE, "..", "..", "_data", "cheltenham-house-price-history.json")

FIRST_YEAR, LAST_YEAR = 1995, 2022
YEAR_URL = "http://prod.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-{year}.csv"
DISTRICTS = ("GL50", "GL51", "GL52", "GL53", "GL54")

# The yearly files have no header row. Column order per HM Land Registry's guidance.
COLUMNS = ["id", "price", "date", "postcode", "property_type", "new_build", "duration",
           "paon", "saon", "street", "locality", "town", "district", "county", "category"]
TYPES = {"D": "detached", "S": "semi_detached", "T": "terraced", "F": "flat", "O": "other"}


def is_cheltenham(row):
    return row[11] == "CHELTENHAM" and row[3].split(" ")[0] in DISTRICTS


def download():
    os.makedirs(os.path.dirname(SRC), exist_ok=True)
    total = 0
    with open(SRC, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(COLUMNS)
        for year in range(FIRST_YEAR, LAST_YEAR + 1):
            kept = 0
            with requests.get(YEAR_URL.format(year=year), stream=True, timeout=(30, 120)) as resp:
                resp.raise_for_status()
                resp.encoding = "utf-8"
                for line in resp.iter_lines(decode_unicode=True):
                    # Cheap pre-filter before parsing: the town and district columns are both "CHELTENHAM".
                    if '"CHELTENHAM"' not in line:
                        continue
                    row = next(csv.reader([line]))
                    if len(row) >= 15 and is_cheltenham(row):
                        writer.writerow(row[:15])
                        kept += 1
            total += kept
            print(f"{year}: kept {kept:,} Cheltenham rows", flush=True)
    print(f"Wrote {total:,} rows to {os.path.normpath(SRC)}")


def money(n):
    return f"£{int(n):,}"


def block(prices):
    return {
        "count": len(prices),
        "count_display": f"{len(prices):,}",
        "median": int(median(prices)),
        "median_display": money(median(prices)),
        "mean": int(mean(prices)),
        "mean_display": money(mean(prices)),
        "total": sum(prices),
        "min": min(prices),
        "max": max(prices),
    }


def summarise():
    if not os.path.exists(SRC):
        sys.exit(f"{os.path.normpath(SRC)} not found — run with --download first.")
    by_year = {}
    with open(SRC, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            price = int(row["price"])
            by_year.setdefault(int(row["date"][:4]), []).append(
                (price, TYPES.get(row["property_type"], "other"), row["new_build"] == "Y")
            )

    years = []
    for year in sorted(by_year):
        rows = by_year[year]
        entry = {"year": year, **block([p for p, _, _ in rows])}
        entry["by_type"] = {
            name: block([p for p, t, _ in rows if t == name]) if any(t == name for _, t, _ in rows) else None
            for name in TYPES.values()
        }
        # The splits house_summary.py compares year on year: new builds, and domestic sales (everything not "Other").
        new_builds = [p for p, _, new in rows if new]
        domestic = [p for p, t, _ in rows if t != "other"]
        entry["new_build"] = block(new_builds) if new_builds else None
        entry["domestic"] = block(domestic) if domestic else None
        entry["other_count"] = sum(1 for _, t, _ in rows if t == "other")
        years.append(entry)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "HM Land Registry Price Paid Data",
        "source_url": "https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads",
        "licence": "Open Government Licence v3.0",
        "first_year": years[0]["year"],
        "last_year": years[-1]["year"],
        "years": years,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(years)} years ({years[0]['year']}-{years[-1]['year']}) to {os.path.normpath(OUT)}")


if __name__ == "__main__":
    if "--download" in sys.argv:
        download()
    else:
        summarise()
