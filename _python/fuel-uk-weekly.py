#!/usr/bin/env python3
"""UK average pump prices for unleaded petrol and diesel from the Department
for Energy Security and Net Zero's weekly road fuel prices, for comparison on
the fuel price history page.

DESNZ publishes Monday's prices each week, and the CSV's address changes with
every release, so the current file is found through the GOV.UK content API.
Only weeks covering the local history (from the first day in
_data/fuel-prices-history.json) are kept. One small request a day, so it runs
with the daily workflow and picks up each release within a day."""
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone

import helper

CONTENT_API = "https://www.gov.uk/api/content/government/statistics/weekly-road-fuel-prices"
SOURCE_URL = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"


def parse_weekly_csv(text, since):
    """[{week, unleaded, diesel}] for every week from the one before `since`."""
    first = (date.fromisoformat(since) - timedelta(days=7)).isoformat()
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    next(reader)
    weeks = []
    for row in reader:
        if len(row) < 3 or not row[1]:
            continue
        week = datetime.strptime(row[0].strip(), "%d/%m/%Y").date().isoformat()
        if week >= first:
            weeks.append({"week": week, "unleaded": float(row[1]), "diesel": float(row[2])})
    return weeks


def csv_url():
    """The address of the current 2018-onwards CSV."""
    attachments = helper.get(CONTENT_API).json()["details"]["attachments"]
    for a in attachments:
        if "CSV" in a.get("title", "") and "2018" in a.get("title", ""):
            return a["url"]
    raise RuntimeError("No 2018-onwards CSV on the weekly road fuel prices page")


def main():
    root = helper.repo_root()
    history = json.loads((root / "_data" / "fuel-prices-history.json").read_text())
    weeks = parse_weekly_csv(helper.get(csv_url()).text, since=history["first_date"])
    helper.write_json(root / "_data" / "fuel-uk-weekly.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Department for Energy Security and Net Zero",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "weeks": weeks,
    })
    print(f"Wrote {len(weeks)} weeks of UK average fuel prices")


if __name__ == "__main__":
    main()
