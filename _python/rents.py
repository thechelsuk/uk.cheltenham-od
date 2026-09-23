#!/usr/bin/env python3
"""Fetch average private rents for Cheltenham from the ONS Price Index of
Private Rents and write _data/rents.json:

- The latest month's average monthly rent, with its monthly and annual change
- The same figures for the South West and England, for comparison
- Rent by number of bedrooms and by property type, for the latest month
- The average rent for the latest month in every year since 2015
- The full monthly series since January 2015

ONS publishes a new edition of the workbook every month and puts the release
date in its file path, so the dataset page is scraped for the newest edition
rather than hardcoding a URL. Refreshed monthly to match ONS's release cadence."""
import io
import json
import os
import re
from datetime import datetime, timezone

import openpyxl
import requests

import config

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "rents.json")

DATASET_URL = "https://www.ons.gov.uk/economy/inflationandpriceindices/datasets/priceindexofprivaterentsukmonthlypricestatistics"
FILE_PATTERN = re.compile(r'href="(/file\?uri=[^"]*?/(\d{1,2})([a-z]+)(\d{4})/[^"]*\.xlsx)"')

AREA_CODE = "E07000078"  # Cheltenham
COMPARATORS = {"south_west": "E12000009", "england": "E92000001"}

# Workbook columns for each breakdown. Every breakdown has an Index, a Monthly
# change, an Annual change and a Rental price column, named "<measure> <suffix>".
BEDROOMS = [("One bedroom", "one bed"), ("Two bedrooms", "two bed"), ("Three bedrooms", "three bed"), ("Four or more bedrooms", "four or more bed")]
TYPES = [("Detached", "detached"), ("Semi-detached", "semidetached"), ("Terraced", "terraced"), ("Flat or maisonette", "flat maisonette")]


def latest_edition_url():
    resp = requests.get(DATASET_URL, headers=config.HEADERS, timeout=30)
    resp.raise_for_status()
    editions = []
    for href, day, month, year in FILE_PATTERN.findall(resp.text):
        released = datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date()
        editions.append((released, href.replace("&amp;", "&")))
    if not editions:
        raise SystemExit(f"Could not find a workbook download link on {DATASET_URL}")
    released, href = max(editions)
    return released, f"https://www.ons.gov.uk{href}"


def read_rows(workbook_bytes):
    """Return {area_code: [row dict, ...]} for the areas this page uses, keyed by header name."""
    sheet = openpyxl.load_workbook(io.BytesIO(workbook_bytes), read_only=True, data_only=True)["Table 1"]
    wanted = {AREA_CODE, *COMPARATORS.values()}
    header, rows = None, {code: [] for code in wanted}
    for row in sheet.iter_rows(values_only=True):
        if header is None:
            if row and row[0] == "Time period":
                header = list(row)
            continue
        if row[1] in wanted:
            rows[row[1]].append(dict(zip(header, row)))
    missing = [code for code, found in rows.items() if not found]
    if missing:
        raise SystemExit(f"No rows found for area codes {missing} in the ONS workbook")
    return rows


def number(value, digits=1):
    """ONS uses markers like '[x]' where a figure doesn't exist; those become None."""
    return round(float(value), digits) if isinstance(value, (int, float)) else None


def money(value):
    return f"£{int(value):,}" if value is not None else None


def change_display(value):
    if value is None:
        return None
    return f"{value:+.1f}%".replace("-", "−")


def point(row, suffix=""):
    """One month's figures for a breakdown ('' = all properties)."""
    tail = f" {suffix}" if suffix else ""
    price = row.get(f"Rental price{tail}")
    price = int(price) if isinstance(price, (int, float)) else None
    annual, monthly = number(row.get(f"Annual change{tail}")), number(row.get(f"Monthly change{tail}"), 2)
    return {
        "price": price,
        "price_display": money(price),
        "annual_change": annual,
        "annual_change_display": change_display(annual),
        "monthly_change": monthly,
    }


def main():
    released, url = latest_edition_url()
    print(f"Latest ONS edition: {released} — {url}")
    resp = requests.get(url, headers=config.HEADERS, timeout=180)
    resp.raise_for_status()
    rows = read_rows(resp.content)

    cheltenham = sorted(rows[AREA_CODE], key=lambda r: r["Time period"])
    latest = cheltenham[-1]
    latest_period = latest["Time period"]

    by_key = {name: {r["Time period"]: r for r in rows[code]} for name, code in COMPARATORS.items()}
    comparison = {}
    for name in COMPARATORS:
        row = by_key[name][latest_period]
        comparison[name] = point(row)

    series = []
    for row in cheltenham:
        period = row["Time period"]
        entry = {"period": period.strftime("%Y-%m"), "price": point(row)["price"], "annual_change": point(row)["annual_change"]}
        for name in COMPARATORS:
            other = point(by_key[name][period])
            entry[name] = other["price"]
            entry[f"{name}_annual_change"] = other["annual_change"]
        series.append(entry)

    same_month = [
        {"period": row["Time period"].strftime("%Y-%m"), "year": row["Time period"].year, **point(row)}
        for row in cheltenham
        if row["Time period"].month == latest_period.month
    ]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Office for National Statistics — Price Index of Private Rents",
        "source_url": DATASET_URL,
        "licence": "Open Government Licence v3.0",
        "edition": released.isoformat(),
        "latest": {
            "period": latest_period.strftime("%Y-%m"),
            "month_name": latest_period.strftime("%B"),
            "year": latest_period.year,
            **point(latest),
            "index": number(latest.get("Index")),
            "south_west": comparison["south_west"],
            "england": comparison["england"],
        },
        "by_bedrooms": [{"label": label, **point(latest, suffix)} for label, suffix in BEDROOMS],
        "by_type": [{"label": label, **point(latest, suffix)} for label, suffix in TYPES],
        "same_month_history": same_month,
        "series": series,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(series)} months to {OUT} (latest {output['latest']['period']}: {output['latest']['price_display']})")


if __name__ == "__main__":
    main()
