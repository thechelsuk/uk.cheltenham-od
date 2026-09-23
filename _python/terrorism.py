#!/usr/bin/env python3
"""Fetch MI5's national threat level feed and write it to _data/terrorism.json
(the current level) and _data/terrorism-history.json (a log of every change).

The feed only ever holds the current level, so changes are recorded run by
run: a record is added the first time a new publication date appears, and
never removed. Changes before tracking began (2006 onwards) were added to the
history file by hand from Wikipedia's "UK Threat Levels" article and are
preserved as they are. Refreshed daily since the level changes rarely."""
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

import config
import helper

URL = "https://www.mi5.gov.uk/UKThreatLevel/UKThreatLevel.xml"
SOURCE_URL = "https://www.mi5.gov.uk/threat-levels"
LICENCE = "Crown copyright"
# Where the hand-added history (everything before this script began tracking) came from.
BACKFILL_SOURCE = {
    "name": "Wikipedia's UK Threat Levels article",
    "url": "https://en.wikipedia.org/wiki/UK_Threat_Levels",
    "licence": "CC BY-SA 4.0",
    "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
}


def strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", html.unescape(text).replace("\xa0", " ")).strip()


def parse_published(value):
    """A record's publication time. Hand-added records only have a date, which
    is taken as midnight UK time so records can always be compared."""
    published = datetime.fromisoformat(value)
    if published.tzinfo is None:
        published = published.replace(tzinfo=ZoneInfo("Europe/London"))
    return published


def northern_ireland_level(details):
    """The Northern Ireland-related level, which the feed gives in its text."""
    match = re.search(r"Northern Ireland-related terrorism is (\w+)", details)
    return match.group(1).upper() if match else ""


def fetch_terrorism_xml(destination):
    headers = {
        **config.HEADERS,
        "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    }
    last_error = None
    for attempt in range(4):
        try:
            response = requests.get(URL, headers=headers, timeout=30)
            response.raise_for_status()
            content = response.text
            lower = content.lower()
            if "just a moment" in lower and "cloudflare" in lower:
                raise RuntimeError("Cloudflare challenge page returned instead of XML")
            destination.write_text(content)
            return content
        except (requests.RequestException, RuntimeError) as error:
            last_error = error
            if attempt == 3:
                raise
            time.sleep(2)
    raise last_error


def parse_feed(xml_content):
    """The current threat level from the feed's single <item>."""
    item = ET.fromstring(xml_content).find("./channel/item")
    if item is None:
        raise RuntimeError("No entries found in terrorism feed")
    title = (item.findtext("title") or "").strip()
    level = title.split()[-1].upper()
    # e.g. "Thursday, April 30, 2026 -  06:09", UK local time.
    published = datetime.strptime(
        re.sub(r"\s+", " ", item.findtext("pubDate") or ""), "%A, %B %d, %Y - %H:%M"
    ).replace(tzinfo=ZoneInfo("Europe/London"))
    details = strip_html(item.findtext("description"))
    return {
        "title": title,
        "level": level,
        "level_title": level.capitalize(),
        "northern_ireland_level": northern_ireland_level(details),
        "details": details,
        "published_iso": published.isoformat(),
    }


def merge_history(records, current, now_iso):
    """Add the current level if its publication date is new, otherwise refresh
    its details. Records are never dropped, and any hand-written fields (such
    as a note) are kept. Returns them newest first."""
    by_id = {r["published_iso"]: r for r in records}
    record = by_id.get(current["published_iso"])
    if record is None:
        record = {
            "published_iso": current["published_iso"],
            "first_seen_iso": now_iso,
            "reporting_format": "new",
            "source": "mi5",
        }
        records.append(record)
    record.update({key: current[key] for key in ("level", "level_title", "northern_ireland_level", "details")})
    record["last_seen_iso"] = now_iso
    records.sort(key=lambda r: parse_published(r["published_iso"]), reverse=True)
    return records


def payload(now, extra):
    return {
        "generated_at": now.isoformat(),
        "source": "MI5",
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        **extra,
    }


if __name__ == "__main__":
    root = helper.repo_root()
    terror_xml = root / "_data/terrorism.xml"
    current_path = root / "_data/terrorism.json"
    history_path = root / "_data/terrorism-history.json"

    try:
        xml_content = fetch_terrorism_xml(terror_xml)
    except Exception as error:
        if current_path.exists():
            print(f"::warning::Fetch failed, keeping existing terrorism.json: {error}")
            raise SystemExit(0)
        if not terror_xml.exists():
            raise
        print(f"Fetch failed, using cached terrorism.xml: {error}")
        xml_content = terror_xml.read_text()

    current = parse_feed(xml_content)
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    records = json.loads(history_path.read_text()).get("records", []) if history_path.exists() else []
    records = merge_history(records, current, now_iso)

    helper.write_json(current_path, payload(now, current))
    helper.write_json(history_path, payload(now, {"backfill_source": BACKFILL_SOURCE, "count": len(records), "records": records}))
    print(f"Threat level {current['level']}, {len(records)} recorded change(s)")
