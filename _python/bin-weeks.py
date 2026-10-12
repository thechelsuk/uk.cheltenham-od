#!/usr/bin/env python3
"""Cheltenham's Week 1 / Week 2 bin collection weeks, from Cheltenham Borough
Council's public collection calendar (a Google Calendar the council links to
from its "check your collection day" page).

Every address is collected on the same weekday each week. Food caddies go
every week; recycling and the green general waste bin alternate, so an
address has its recycling one week and its green bin the next. The calendar
only says whether a week is Week 1 or Week 2: which of those is an address's
recycling week comes from the council's postcode checker.

Writes the next WEEKS_AHEAD weeks to _data/bin-weeks.json, each with any
weekday bank holidays from _data/holidays.json (collections move in those
weeks). The page picks out the current week when the site is built, so this
only needs to run weekly.
"""
import datetime
import json
import re

import helper

CALENDAR_ID = "v7oettki6t1pi2p7s0j6q6121k@group.calendar.google.com"
ICS_URL = f"https://calendar.google.com/calendar/ical/{CALENDAR_ID.replace('@', '%40')}/public/basic.ics"
CALENDAR_PAGE = f"https://calendar.google.com/calendar/u/0/embed?src={CALENDAR_ID}&ctz=Europe/London"
SOURCE_PAGE = "https://www.cheltenham.gov.uk/bins-and-recycling/check-your-collection-day/"
WEEKS_AHEAD = 26


def parse_anchors(ics_text):
    """{1: first Monday of Week 1, 2: first Monday of Week 2} from the calendar's events."""
    text = ics_text.replace("\r\n ", "").replace("\r\n", "\n")
    anchors = {}
    for event in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        summary = re.search(r"^SUMMARY:Week (\d)\s*$", event, re.M)
        start = re.search(r"^DTSTART[^:]*:(\d{8})", event, re.M)
        if summary and start:
            anchors[int(summary.group(1))] = datetime.datetime.strptime(start.group(1), "%Y%m%d").date()
    return anchors


def week_number(monday, anchors):
    """1 or 2 for the week starting `monday`: the weeks alternate from Week 1's first Monday."""
    weeks_since = (monday - anchors[1]).days // 7
    return 1 if weeks_since % 2 == 0 else 2


def upcoming_weeks(today, anchors, count, holidays):
    """`count` collection weeks (Monday to Friday) from the week containing `today`."""
    monday = today - datetime.timedelta(days=today.weekday())
    weeks = []
    for i in range(count):
        start = monday + datetime.timedelta(weeks=i)
        end = start + datetime.timedelta(days=4)
        weekday_holidays = [
            {"date": h["date"], "title": h["title"]}
            for h in holidays
            if start.isoformat() <= h["date"] <= end.isoformat()
        ]
        weeks.append({
            "start": start.isoformat(),
            "end": end.isoformat(),
            "week": week_number(start, anchors),
            "bank_holidays": weekday_holidays,
        })
    return weeks


if __name__ == "__main__":
    root = helper.repo_root()
    resp = helper.get(ICS_URL)
    resp.raise_for_status()
    found = parse_anchors(resp.text)
    if set(found) != {1, 2}:
        raise SystemExit(f"Expected Week 1 and Week 2 events in the council calendar, found {sorted(found)}")

    holidays_data = json.loads((root / "_data" / "holidays.json").read_text())
    bank_holidays = holidays_data["england-and-wales"]["events"]

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "Cheltenham Borough Council",
        "source_url": SOURCE_PAGE,
        "calendar_url": CALENDAR_PAGE,
        "week_1_from": found[1].isoformat(),
        "weeks": upcoming_weeks(datetime.date.today(), found, WEEKS_AHEAD, bank_holidays),
    }
    out = root / "_data" / "bin-weeks.json"
    helper.write_json(out, payload)
    print(f"Wrote {WEEKS_AHEAD} collection weeks to {out}")
