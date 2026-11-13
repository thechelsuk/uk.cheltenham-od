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
is skipped: each hourly run costs a handful of page fetches, and only downloads
when NHS England has published something new.

"Can't be right" check: if the newest month held is older than the month due
by today (the 2nd Thursday rule), the script exits with an error, so a year
page that comes back without its links fails instead of passing silently.

Older files name their columns slightly differently, so figures are totalled
by column-name prefix rather than by exact name.
"""
import csv
import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin

import requests

# Runs from _python/pi/ on the Pi, so make the shared _python modules importable.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))
import config  # noqa: E402
import helper  # noqa: E402

OUT = os.path.join(HERE, "..", "..", "_data", "nhs-ae.json")

PAGE_URL = ("https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/"
            "ae-attendances-and-emergency-admissions-{fy}/")
LANDING_URL = "https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/"

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
    """The page's HTML, or None if it doesn't exist (yet). Anything but a 200
    is an error: the site sits behind CloudFront, and a bot challenge (HTTP
    202) is a page with no links, which would otherwise read as "nothing new"."""
    resp = requests.get(url, headers=config.HEADERS, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    if resp.status_code != 200:
        raise RuntimeError(f"{url} returned HTTP {resp.status_code}, not the page (a bot challenge?)")
    return resp.text


def second_thursday(year, month):
    first = date(year, month, 1)
    return first + timedelta(days=(3 - first.weekday()) % 7 + 7)


def months_before(year, month, n):
    index = year * 12 + month - 1 - n
    return f"{index // 12}-{index % 12 + 1:02d}"


def expected_latest_period(today):
    """The newest month NHS England should have published by `today`, as
    'YYYY-MM'. Each month comes out on the 2nd Thursday of the next; the
    publication day itself is allowed, in case the runs fall before 09:30."""
    released = (today.day > second_thursday(today.year, today.month).day)
    return months_before(today.year, today.month, 1 if released else 2)


def check_up_to_date(months, today):
    """Can't be right: fail if a month that should be published is missing,
    so a page that hides its links shows up as a failing fetcher."""
    due = expected_latest_period(today)
    newest = max(months, default=None)
    if newest is None:
        raise RuntimeError(f"no months in _data/nhs-ae.json; {due} was due")
    if newest < due:
        raise RuntimeError(f"newest month is {newest} but {due} was due by {today:%Y-%m-%d}: "
                           "check the year pages and the log above")


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


def main(today=None):
    today = today or datetime.now(timezone.utc).date()
    existing = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            existing = json.load(f)
    files = {entry["url"]: entry["period"] for entry in existing.get("files", [])}
    months = {m["period"]: m for m in existing.get("months", [])}

    fetched = 0
    for fy in financial_year_labels(today):
        page_url = PAGE_URL.format(fy=fy)
        html = fetch_text(page_url)
        if html is None:
            print(f"No page for {fy} yet, skipping")
            continue
        urls = [urljoin(page_url, href) for href in dict.fromkeys(LINK_PATTERN.findall(html))]
        new = [url for url in urls if url not in files]
        print(f"{fy}: {len(html):,} bytes, {len(urls)} CSV links, {len(new)} new")
        for url in new:
            resp = requests.get(url, headers=config.HEADERS, timeout=60)
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
        check_up_to_date(months, today)
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
    helper.write_json(OUT, output)
    print(f"Wrote {len(kept)} months ({kept[-1]['period']} to {kept[0]['period']}) to {OUT}")
    check_up_to_date(months, today)


if __name__ == "__main__":
    main()
