#!/usr/bin/env python3
"""Spot months of Cheltenham crime data that police.uk has since filled in.

From February 2026 Gloucestershire Constabulary's new records system sent
police.uk only a handful of crimes a month, so those months were saved
nearly empty. The force has said it will backfill them. This check finds
saved months far below the usual total, asks police.uk again for one
neighbourhood (the town centre, the busiest), and lists the months where
that count is back to normal so the workflow can re-fetch them in full
with `crime.py --date YYYY-MM --overwrite`.

It makes no API calls when no saved month is short, and one per short
month otherwise.

Run from the repository root:
    .venv/bin/python _python/crime-backfill-check.py

In GitHub Actions the months found are written to $GITHUB_OUTPUT as
`months`, space separated.
"""
import json
import os
import statistics

import crime

INDEX = crime.OUTPUT_DIR / "index.json"
CHECK_NEIGHBOURHOOD = "Cheltenham Town Centre"
# A saved month under a quarter of the usual total was published short.
SHORT_SHARE = 0.25
# The town centre back to at least half its usual count means police.uk
# now has that month properly.
BACKFILLED_SHARE = 0.5


def month_totals(index):
    return {
        month["month"]: sum(n["crime_count"] for n in month["neighbourhoods"])
        for month in index["months"]
    }


def neighbourhood_counts(index, name):
    counts = {}
    for month in index["months"]:
        for neighbourhood in month["neighbourhoods"]:
            if neighbourhood["name"] == name:
                counts[month["month"]] = neighbourhood
    return counts


def short_months(totals):
    usual = statistics.median(totals.values())
    return sorted(month for month, total in totals.items() if total < usual * SHORT_SHARE)


def backfilled_months(index):
    totals = month_totals(index)
    short = short_months(totals)
    if not short:
        print("No saved month is short; nothing to check.")
        return []

    centre = neighbourhood_counts(index, CHECK_NEIGHBOURHOOD)
    usual_centre = statistics.median(n["crime_count"] for n in centre.values())
    found = []
    for month in short:
        saved = json.loads((crime.OUTPUT_DIR / centre[month]["file"]).read_text())
        now = crime.fetch_neighbourhood_data(saved["neighbourhood"], saved["boundary"], month)["crime_count"]
        print(f"{month}: saved {totals[month]} crimes in total; {CHECK_NEIGHBOURHOOD} "
              f"now {now} on police.uk (usually about {usual_centre:.0f})")
        if now >= usual_centre * BACKFILLED_SHARE:
            found.append(month)
    return found


def main():
    index = json.loads(INDEX.read_text())
    found = backfilled_months(index)
    if found:
        print(f"Backfilled on police.uk, re-fetch: {' '.join(found)}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"months={' '.join(found)}\n")


if __name__ == "__main__":
    main()
