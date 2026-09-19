#!/usr/bin/env python3
"""Fetch Gloucestershire Hospitals NHS Foundation Trust's monthly A&E figures
from NHS England's "A&E Attendances and Emergency Admissions" statistics and
write _data/nhs-ae.json, keeping the last 36 months.

The trust (ODS code RTE) runs Cheltenham General and Gloucestershire Royal
hospitals; the published figures are for the whole trust, not split by site.

NHS England publishes one provider-level CSV per month (2nd Thursday, for the
previous month) on a page per financial year. The CSV filenames carry random
tokens and are named inconsistently, so this scrapes the year pages for .csv
links and reads each file's own `Period` column for its month. Because a new
month or a revision arrives under a new URL, a URL already recorded in the JSON
is skipped: the daily run costs a handful of page fetches, and only downloads
when NHS England has published something new.

Older files name their columns slightly differently, so figures are totalled
by column-name prefix rather than by exact name.
"""
import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "nhs-ae.json")

PAGE_URL = ("https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/"
            "ae-attendances-and-emergency-admissions-{fy}/")
LANDING_URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

ORG_CODE = "RTE"
TRUST_NAME = "Gloucestershire Hospitals NHS Foundation Trust"
MONTHS_KEPT = 36

MONTH_NUMBERS = {name: i for i, name in enumerate(
    ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
     "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}
LINK_PATTERN = re.compile(r'href="([^"]+?\.csv)"', re.IGNORECASE)


def financial_year_labels(today):
    """Enough financial years, newest first, to cover MONTHS_KEPT months: '2026-27', ..."""
    start = today.year if today.month >= 4 else today.year - 1
    return [f"{y}-{str(y + 1)[-2:]}" for y in range(start, start - MONTHS_KEPT // 12 - 1, -1)]


def fetch_text(url):
    resp = requests.get(url, headers=HEADERS, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.text


def to_int(value):
    digits = re.sub(r"[^\d]", "", value or "")
    return int(digits) if digits else 0


def total(row, prefix):
    """Sum every column whose (lower-cased) header starts with `prefix`."""
    return sum(to_int(v) for k, v in row.items() if (k or "").strip().lower().startswith(prefix))


def display(n):
    return f"{n:,}"


def period_display(period):
    """'2026-08' -> 'August 2026', for prose. Layouts print this rather than
    building it from the period in Liquid."""
    year, month = period.split("-")
    return f"{list(MONTH_NUMBERS)[int(month) - 1].title()} {year}"


def parse_month(csv_text):
    """One monthly provider CSV -> this trust's record, or None if it isn't an A&E provider file."""
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("﻿")))
    for row in reader:
        row = {(k or "").strip(): v for k, v in row.items()}
        if "Period" not in row or "Org Code" not in row:
            return None
        if row["Org Code"].strip() != ORG_CODE:
            continue
        # 'MSitAE-AUGUST-2026' -> '2026-08'
        parts = row["Period"].strip().upper().split("-")
        month = MONTH_NUMBERS.get(parts[-2])
        if not month or not parts[-1].isdigit():
            return None

        attendances = total(row, "a&e attendances")
        over_4hrs = total(row, "attendances over 4hrs")
        within_pct = round((attendances - over_4hrs) / attendances * 100, 1) if attendances else None
        dta_12 = total(row, "patients who have waited 12")
        admissions = total(row, "emergency admissions via a&e") + total(row, "other emergency admissions")
        return {
            "period": f"{parts[-1]}-{month:02d}",
            "attendances": attendances,
            "attendances_display": display(attendances),
            "over_4hrs": over_4hrs,
            "over_4hrs_display": display(over_4hrs),
            "within_4hrs_pct": within_pct,
            "within_4hrs_display": f"{within_pct}%" if within_pct is not None else "",
            "dta_12hrs": dta_12,
            "dta_12hrs_display": display(dta_12),
            "emergency_admissions": admissions,
            "emergency_admissions_display": display(admissions),
        }
    return None


def main():
    existing = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            existing = json.load(f)
    files = {entry["url"]: entry["period"] for entry in existing.get("files", [])}
    months = {m["period"]: m for m in existing.get("months", [])}

    fetched = 0
    for fy in financial_year_labels(datetime.now(timezone.utc)):
        page_url = PAGE_URL.format(fy=fy)
        html = fetch_text(page_url)
        if html is None:
            print(f"No page for {fy} yet, skipping")
            continue
        for href in dict.fromkeys(LINK_PATTERN.findall(html)):
            url = urljoin(page_url, href)
            if url in files:
                continue
            resp = requests.get(url, headers=HEADERS, timeout=60)
            resp.raise_for_status()
            record = parse_month(resp.content.decode("utf-8-sig", errors="replace"))
            files[url] = record["period"] if record else None    # remember non-A&E files too
            fetched += 1
            if record:
                record["source_file"] = url
                months.setdefault(record["period"], record)      # first seen (newest page order) wins
                print(f"  {record['period']}: {record['within_4hrs_display']} within 4 hours")
            else:
                print(f"  Skipped {url} (no {ORG_CODE} row / not a provider file)")

    # Months saved before period_display existed get it added on the next run.
    needs_backfill = any("period_display" not in m for m in months.values())
    if not fetched and existing and not needs_backfill:
        print("No new NHS England files; leaving _data/nhs-ae.json alone")
        return

    for m in months.values():
        m["period_display"] = period_display(m["period"])

    kept = sorted(months.values(), key=lambda m: m["period"], reverse=True)[:MONTHS_KEPT]
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NHS England, A&E Attendances and Emergency Admissions",
        "source_url": LANDING_URL,
        "licence": "Open Government Licence v3.0",
        "trust": {"name": TRUST_NAME, "code": ORG_CODE},
        "months_kept": MONTHS_KEPT,
        "files": [{"url": u, "period": p} for u, p in files.items()],   # every URL seen, so none is re-downloaded
        "months": kept,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(kept)} months ({kept[-1]['period']} to {kept[0]['period']}) to {OUT}")


if __name__ == "__main__":
    main()
