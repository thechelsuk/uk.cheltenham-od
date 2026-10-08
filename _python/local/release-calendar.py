#!/usr/bin/env python3
"""
Build admin/data-releases.ics, a calendar of data releases and draft
deadlines, from the hand-curated admin/data-releases.json.

Timed events are releases at a known time (UK local time). Events without a
time are all-day reminders: an expected release to check for, or a draft that
needs refreshing before it publishes. Each event keeps a stable UID (its
"id", or else its date and title), so importing the file again updates events
instead of duplicating them.

Usage:
    python _python/local/release-calendar.py

Then import admin/data-releases.ics into your calendar. The process for each
source is in admin/guide/data-releases.md.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parent.parent.parent
SOURCE = root / "admin" / "data-releases.json"
OUT = root / "admin" / "data-releases.ics"

LABELS = {"confirmed": "", "expected": "[Expected] ", "deadline": "[Deadline] "}

# Europe/London with its daylight saving rules, so timed events stay at the
# right local time whatever calendar imports them.
VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/London",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0000",
    "TZOFFSETTO:+0100",
    "TZNAME:BST",
    "DTSTART:19700329T010000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0000",
    "TZNAME:GMT",
    "DTSTART:19701025T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def escape(text: str) -> str:
    """Escape a value for an iCalendar text property."""
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line: str) -> list[str]:
    """Split a content line into 75-octet pieces, as iCalendar requires."""
    pieces: list[str] = []
    current = ""
    for char in line:
        limit = 75 if not pieces else 74
        if len((current + char).encode("utf-8")) > limit:
            pieces.append(current)
            current = char
        else:
            current += char
    pieces.append(current)
    return [pieces[0]] + [" " + piece for piece in pieces[1:]]


def event_lines(event: dict, stamp: str) -> list[str]:
    """The VEVENT lines for one release or reminder."""
    day = date.fromisoformat(event["date"])
    slug = "".join(c if c.isalnum() else "-" for c in event["title"].lower())
    # The UID comes from date and title, so changing either makes a new event.
    # Give an event a fixed "id" before re-dating or renaming it.
    uid = event.get("id") or f"{day:%Y%m%d}-{slug.strip('-')}"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}@cheltenham-od.uk",
        f"DTSTAMP:{stamp}",
    ]
    if event.get("time"):
        start = datetime.fromisoformat(f"{event['date']}T{event['time']}")
        end = start + timedelta(minutes=30)
        lines += [f"DTSTART;TZID=Europe/London:{start:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Europe/London:{end:%Y%m%dT%H%M%S}"]
    else:
        lines += [f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}"]
    summary = LABELS.get(event["status"], "") + event["title"]
    description = f"{event['notes']}\n\n{event['url']}"
    lines += [
        f"SUMMARY:{escape(summary)}",
        f"DESCRIPTION:{escape(description)}",
        f"URL:{event['url']}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return lines


def main() -> None:
    """Write the calendar file from the JSON list of events."""
    events = json.loads(SOURCE.read_text(encoding="utf-8"))["events"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Cheltenham Open Data//Data releases//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Cheltenham Open Data releases",
        *VTIMEZONE,
    ]
    for event in sorted(events, key=lambda e: (e["date"], e.get("time", ""))):
        lines += event_lines(event, stamp)
    lines.append("END:VCALENDAR")
    folded = [piece for line in lines for piece in fold(line)]
    OUT.write_text("\r\n".join(folded) + "\r\n", encoding="utf-8", newline="")
    print(f"Wrote {len(events)} events to {OUT}")


if __name__ == "__main__":
    main()
