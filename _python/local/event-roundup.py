#!/usr/bin/env python3
"""
event_roundup.py

Pulls events from RSS feeds listed in /_data/event-sources.yml, filters to
the next ~30 days, fuzzy-dedupes near-identical listings across feeds, lets
you pick which ones to keep via a terminal checkbox list, then writes a
Jekyll markdown post straight into _posts/.

Usage:
    python _python/event_roundup.py
    python _python/event_roundup.py --days 45
    python _python/event_roundup.py --sources _data/event-sources.yml --posts-dir _posts

Run from the repo root (or pass --sources / --posts-dir explicitly).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from pathlib import Path
from time import mktime
from typing import Optional
from urllib.parse import urlparse

import feedparser
import questionary
import yaml
from bs4 import BeautifulSoup
from rapidfuzz import fuzz


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class Event:
    source_id: str
    source_url: str
    title: str
    event_date: Optional[date]
    end_date: Optional[date] = None
    link: str = ""
    venue: str = ""
    description: str = ""
    raw_entry: dict = field(default_factory=dict, repr=False)

    def date_label(self) -> str:
        if not self.event_date:
            return "date unknown"
        if self.end_date and self.end_date != self.event_date:
            return f"{self.event_date.strftime('%d %b')} – {self.end_date.strftime('%d %b')}"
        return self.event_date.strftime("%a %d %b")

    def display_line(self) -> str:
        bits = [self.date_label(), f"— {self.title}"]
        if self.venue:
            bits.append(f"@ {self.venue}")
        bits.append(f"[{self.source_id}]")
        return " ".join(bits)


# --------------------------------------------------------------------------
# Step 1: load sources
# --------------------------------------------------------------------------

def load_sources(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(f"Could not find sources file at {path}. "
                  f"Expected something like:\n\n- id: cheltenham-festivals\n  url: https://example.org/feed.rss\n")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        sys.exit(f"{path} should be a YAML list of {{id, url}} entries.")
    cleaned = []
    for entry in data:
        if "id" not in entry or "url" not in entry:
            print(f"  ! skipping malformed source entry: {entry}")
            continue
        cleaned.append(entry)
    return cleaned


# --------------------------------------------------------------------------
# Step 2: fetch + parse feeds
# --------------------------------------------------------------------------

DATE_FIELDS = ("published_parsed", "updated_parsed", "created_parsed")


def extract_date(entry: dict) -> Optional[date]:
    for field_name in DATE_FIELDS:
        val = entry.get(field_name)
        if val:
            try:
                return datetime.fromtimestamp(mktime(val)).date()
            except (OverflowError, ValueError, TypeError):
                continue
    return None


# Matches WordPress's classic "The post X appeared first on Y." boilerplate
# that leaks into RSS <description>/<summary> on many self-hosted feeds.
WORDPRESS_BOILERPLATE_RE = re.compile(
    r"\s*The post .*? appeared first on .*?\.\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)


# Feeds sometimes ship a literal placeholder instead of leaving the field
# empty. Treat these as "no description at all".
PLACEHOLDER_DESCRIPTIONS = {"no description", "n/a", "none", "tbc", "-"}


def clean_description(raw_html: str) -> str:
    """
    Strips HTML down to plain text: removes all tags (including images —
    sketchy feeds often hotlink third-party images we don't want to keep),
    strips trailing "The post X appeared first on Y." boilerplate, collapses
    whitespace, and returns plain prose suitable for markdown.
    """
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for img in soup.find_all("img"):
        img.decompose()
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = " ".join(text.split())
    text = WORDPRESS_BOILERPLATE_RE.sub("", text)
    for punct in (".", ",", "!", "?", ";", ":"):
        text = text.replace(f" {punct}", punct)
    text = text.strip()
    if text.lower() in PLACEHOLDER_DESCRIPTIONS:
        return ""
    return text


def extract_venue(entry: dict) -> str:
    for key in ("location", "venue", "geo_lat"):
        if key in entry:
            return str(entry.get(key, "")).strip()
    return ""


# --------------------------------------------------------------------------
# Text-based event date parsing
#
# Sketchy feeds routinely report the *publish* date of the post (e.g. "4
# Sept") in RSS metadata, while the actual event date(s) are only mentioned
# in the title/description text, e.g. "18 September – 18 October" or
# "3 – 4 October". We parse those out and prefer them over the RSS
# published/updated date whenever we find one.
# --------------------------------------------------------------------------

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
MONTH_NAMES = "|".join(sorted(MONTHS.keys(), key=len, reverse=True))

# "18 September – 18 October" / "18 Sept - 18 Oct" (cross-month range)
RANGE_CROSS_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAMES})\s*(?:–|-|to)\s*"
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAMES})\b",
    flags=re.IGNORECASE,
)
# "3 – 4 October" (same-month range)
RANGE_SAME_MONTH_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:–|-|to)\s*"
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAMES})\b",
    flags=re.IGNORECASE,
)
# "18 September" / "10th Sept" (single date)
SINGLE_DATE_RE = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_NAMES})\b",
    flags=re.IGNORECASE,
)


def _resolve_year(month: int, day: int, today: date) -> int:
    """Picks a year for a bare day/month: this year, unless that's already
    well in the past, in which case assume next year."""
    year = today.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        return year
    if candidate < today - timedelta(days=60):
        return year + 1
    return year


def find_dates_in_text(text: str, today: date) -> list[tuple[date, Optional[date]]]:
    """
    Returns every distinct (start_date, end_date_or_None) found in text, in
    the order they appear. end_date is None for single (non-range) dates.
    """
    if not text:
        return []

    found: list[tuple[date, Optional[date]]] = []
    consumed_spans: list[tuple[int, int]] = []

    def overlaps_consumed(span):
        return any(s < span[1] and span[0] < e for s, e in consumed_spans)

    for m in RANGE_CROSS_MONTH_RE.finditer(text):
        if overlaps_consumed(m.span()):
            continue
        d1, mon1, d2, mon2 = m.groups()
        month1, month2 = MONTHS[mon1.lower()], MONTHS[mon2.lower()]
        year1 = _resolve_year(month1, int(d1), today)
        try:
            start = date(year1, month1, int(d1))
            end = date(year1 if month2 >= month1 else year1 + 1, month2, int(d2))
        except ValueError:
            continue
        found.append((start, end))
        consumed_spans.append(m.span())

    for m in RANGE_SAME_MONTH_RE.finditer(text):
        if overlaps_consumed(m.span()):
            continue
        d1, d2, mon = m.groups()
        month = MONTHS[mon.lower()]
        year = _resolve_year(month, int(d1), today)
        try:
            start = date(year, month, int(d1))
            end = date(year, month, int(d2))
        except ValueError:
            continue
        found.append((start, end))
        consumed_spans.append(m.span())

    for m in SINGLE_DATE_RE.finditer(text):
        if overlaps_consumed(m.span()):
            continue
        d1, mon = m.groups()
        month = MONTHS[mon.lower()]
        year = _resolve_year(month, int(d1), today)
        try:
            start = date(year, month, int(d1))
        except ValueError:
            continue
        found.append((start, None))
        consumed_spans.append(m.span())

    # Keep original left-to-right order of appearance in the text.
    found_with_pos = []
    for start, end in found:
        found_with_pos.append((start, end))
    return found_with_pos


def extract_source_name(link: str, source_id: str) -> str:
    """
    Best-effort human-readable site name for the 'More info at [source]' line.
    Falls back to the source_id from event-sources.yml if the link has no
    usable domain.
    """
    if link:
        domain = urlparse(link).netloc
        domain = domain.removeprefix("www.")
        if domain:
            return domain
    return source_id


def fetch_events(sources: list[dict], days_ahead: int) -> list[Event]:
    today = date.today()
    start = today + timedelta(days=1)  # exclude today — typically too late to act on
    horizon = today + timedelta(days=days_ahead)
    events: list[Event] = []

    for source in sources:
        source_id, url = source["id"], source["url"]
        print(f"  fetching {source_id} ...", end=" ")
        try:
            parsed = feedparser.parse(url)
        except Exception as exc:
            print(f"FAILED ({exc})")
            continue

        if parsed.bozo and not parsed.entries:
            print(f"FAILED (unparseable, bozo_exception={parsed.get('bozo_exception')})")
            continue

        kept = 0
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            raw_description = clean_description(entry.get("summary") or entry.get("description") or "")
            published = extract_date(entry)

            # Prefer date(s) mentioned in the text over the RSS publish date —
            # sketchy feeds report when the POST was published, not the event.
            text_dates = find_dates_in_text(f"{title} {raw_description}", today)

            multi_date_warning = ""
            if text_dates:
                event_date, end_date = text_dates[0]
                if len(text_dates) > 1:
                    # More than one date mentioned — likely several events bundled
                    # into one post (seen on e.g. Cheltenham Festivals). Don't guess
                    # which is right; flag it for a manual check instead.
                    source_link = (
                        (entry.get("link") or "").strip()
                        or (entry.get("id") or "").strip()
                        or (entry.get("guid") or "").strip()
                        or url  # last resort: the feed URL itself
                    )
                    multi_date_warning = (
                        f"⚠ MULTIPLE DATES FOUND ON THIS PAGE ({len(text_dates)}) — "
                        f"this post may bundle more than one event; check the source"
                        + (f" ({source_link})" if source_link else "")
                        + " and consider splitting into separate entries."
                    )
            elif published:
                event_date, end_date = published, None
            else:
                continue  # no date anywhere — can't place it on the calendar

            if not title or not event_date:
                continue

            # Overlap check: include if any part of the event falls in [start, horizon].
            span_end = end_date or event_date
            if span_end < start or event_date > horizon:
                continue

            description = raw_description
            if multi_date_warning:
                description = f"{multi_date_warning} {description}".strip()

            link = (
                (entry.get("link") or "").strip()
                or (entry.get("id") or "").strip()
                or (entry.get("guid") or "").strip()
                or url  # last resort: the feed URL itself
            )

            events.append(Event(
                source_id=source_id,
                source_url=url,
                title=title,
                event_date=event_date,
                end_date=end_date,
                link=link,
                venue=extract_venue(entry),
                description=description,
                raw_entry=entry,
            ))
            kept += 1
        print(f"{kept} candidate(s) in range")

    return events


# --------------------------------------------------------------------------
# Step 3: fuzzy dedupe
# --------------------------------------------------------------------------

TITLE_MATCH_THRESHOLD = 82
DATE_PROXIMITY_DAYS = 1


def dedupe(events: list[Event]) -> tuple[list[Event], list[tuple[Event, Event, int]]]:
    kept: list[Event] = []
    flagged: list[tuple[Event, Event, int]] = []

    for ev in events:
        match_found = False
        for existing in kept:
            if ev.event_date is None or existing.event_date is None:
                continue
            if abs((ev.event_date - existing.event_date).days) > DATE_PROXIMITY_DAYS:
                continue
            score = fuzz.token_sort_ratio(ev.title.lower(), existing.title.lower())
            if score >= TITLE_MATCH_THRESHOLD:
                flagged.append((existing, ev, int(score)))
                match_found = True
                break
        if not match_found:
            kept.append(ev)

    return kept, flagged


# --------------------------------------------------------------------------
# Step 4: terminal checkbox review
# --------------------------------------------------------------------------

def review_events(events: list[Event]) -> list[Event]:
    if not events:
        print("\nNo candidate events found in range. Nothing to review.")
        return []

    events_sorted = sorted(events, key=lambda e: (e.event_date or date.max, e.title))

    choices = [
        questionary.Choice(title=ev.display_line(), value=idx, checked=False)
        for idx, ev in enumerate(events_sorted)
    ]

    print(
        "\nReview candidates below.\n"
        "  ↑ / ↓   move cursor\n"
        "  space   toggle the item under the cursor on/off\n"
        "  a       toggle ALL items on/off\n"
        "  enter   confirm your selection\n"
        "Nothing is selected by default — you choose what goes in.\n"
    )

    selected_indices = questionary.checkbox(
        "Select events to include:",
        choices=choices,
    ).ask()

    if selected_indices is None:
        sys.exit("Cancelled — no file written.")

    if not selected_indices:
        proceed = questionary.confirm(
            "Nothing is checked. If you meant to select items, press Ctrl-C now, "
            "re-run, and use SPACE (not Enter) to check items. Continue with zero events?",
            default=False,
        ).ask()
        if not proceed:
            sys.exit("Cancelled — no file written. Re-run and use Space to toggle, Enter only to finish.")

    return [events_sorted[i] for i in selected_indices]


def show_flagged(flagged: list[tuple[Event, Event, int]]) -> None:
    if not flagged:
        return
    print(f"\n{len(flagged)} likely duplicate(s) collapsed automatically:")
    for kept_ev, dropped_ev, score in flagged:
        print(f"  - kept: [{kept_ev.source_id}] {kept_ev.title!r}")
        print(f"    dropped: [{dropped_ev.source_id}] {dropped_ev.title!r} (match {score}%)")


# --------------------------------------------------------------------------
# Step 5: front matter (extend this as you identify fields you need)
# --------------------------------------------------------------------------

def create_front_matter(post_date: date, events: list[Event]) -> str:
    title = f"Upcoming Events for {post_date.strftime('%B %Y')}"

    lines = [
        "---",
        "layout: posts",
        f"title: \"{title}\"",
        f"date: {post_date.isoformat()}",
        f"type: news",
        f"description: \"A curated list of what's up and coming in Cheltenham in the next month or so.\"",
        f"seo: \"A curated list of what's on in Cheltenham in the next month or so.\"",
        f"categories: [events]",
        "---",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Step 6: write the post
# --------------------------------------------------------------------------

def build_post_body(events: list[Event]) -> str:
    """
    Structure per event:
        ### Event Title

        - Venue: ...
        - description text
        - More info at [source](link).
    """
    events_sorted = sorted(events, key=lambda e: (e.event_date or date.max, e.title))

    blocks: list[str] = []
    current_date = None

    for ev in events_sorted:
        if ev.event_date != current_date:
            current_date = ev.event_date
            blocks.append(f"## {current_date.strftime('%A %d %B')}")

        heading = ev.title
        if ev.end_date and ev.end_date != ev.event_date:
            heading += f" ({ev.event_date.strftime('%d %b')} – {ev.end_date.strftime('%d %b')})"
        blocks.append(f"### {heading}")

        detail_items: list[str] = []
        if ev.venue:
            detail_items.append(f"- Venue: {ev.venue}")
        if ev.description:
            detail_items.append(f"- {ev.description}")
        if ev.link:
            source_name = extract_source_name(ev.link, ev.source_id)
            detail_items.append(f"- More info at [{source_name}]({ev.link}).")

        if detail_items:
            blocks.append("\n".join(detail_items))

    return "\n\n".join(blocks).strip() + "\n"


def write_post(events: list[Event], posts_dir: Path) -> Path:
    post_date = date.today()
    front_matter = create_front_matter(post_date, events)
    body = build_post_body(events)

    posts_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{post_date.isoformat()}-upcoming-events-{post_date.isoformat()}.md"
    out_path = posts_dir / filename

    out_path.write_text(front_matter + "\n\n" + body, encoding="utf-8")
    return out_path


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build a weekly Jekyll events roundup from RSS feeds.")
    parser.add_argument("--sources", default="_data/event-sources.yml", help="Path to sources YAML file.")
    parser.add_argument("--posts-dir", default="_events", help="Jekyll _events collection directory to write into.")
    parser.add_argument("--days", type=int, default=60, help="How many days ahead to include (default 6 weeks).")
    args = parser.parse_args()

    sources_path = Path(args.sources)
    posts_dir = Path(args.posts_dir)

    print(f"Loading sources from {sources_path} ...")
    sources = load_sources(sources_path)
    print(f"  {len(sources)} source(s) loaded.\n")

    print("Fetching feeds:")
    raw_events = fetch_events(sources, args.days)
    print(f"\n{len(raw_events)} total candidate(s) before dedupe.")

    unique_events, flagged = dedupe(raw_events)
    print(f"{len(unique_events)} unique event(s) after fuzzy dedupe.")
    show_flagged(flagged)

    selected = review_events(unique_events)
    if not selected:
        print("\nNo events selected — nothing written.")
        return

    out_path = write_post(selected, posts_dir)
    print(f"\nWrote {len(selected)} event(s) to {out_path}")


if __name__ == "__main__":
    main()