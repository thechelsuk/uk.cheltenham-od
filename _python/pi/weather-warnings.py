#!/usr/bin/env python3
"""Met Office severe weather warnings that cover Gloucestershire, from the
Met Office's South West England warnings RSS feed.

Each feed item lists the council areas it affects; only warnings that list
Gloucestershire are kept (South Gloucestershire is a separate area). If an
item's areas can't be read, it is kept rather than missed.

Writes the current warnings to _data/weather-warnings.json, a log of every
warning seen to _data/weather-warnings-history.json, an Atom feed to
feeds/weather-warnings.xml and the homepage alert include. The Met Office's
RSS terms ask for its wording and links to be used unchanged, so titles,
descriptions and links are passed through as given.

The log only changes when a warning appears, changes or ends, so a warning
that runs for days doesn't make the Pi commit on every run."""
import datetime
import os
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import config
import alerts_feed
import helper

FEED_URL = "https://www.metoffice.gov.uk/public/data/PWSCache/WarningsRSS/Region/sw"
SOURCE_PAGE = "https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings"
SOURCE = "Met Office"
LICENCE = "Met Office RSS feed terms"
COUNTY = "Gloucestershire"

# Logged warnings are kept for two years, like the power cuts log.
HISTORY_RETENTION_DAYS = 730

TITLE = re.compile(r"^(\w+) warning of (.+?) affecting ")
DESCRIPTION = re.compile(r": (.+) valid from (\d{4}) \w{3} (\d{1,2} \w{3}) to (\d{4}) \w{3} (\d{1,2} \w{3})$")
# Fields compared between runs; a change to any of them counts as an update.
FIELDS = ("title", "description", "link", "level", "hazard", "areas", "starts", "ends")


def _local(hhmm, day_month, year):
    """UK local time as written in the feed, e.g. "0600", "01 Nov", 2026."""
    return datetime.datetime.strptime(f"{day_month} {year} {hhmm}", "%d %b %Y %H%M")


def parse(feed_text):
    """Every warning in the RSS feed. The feed gives times without a year
    ("valid from 0600 Sun 01 Nov"), so the year comes from the date in the
    warning's link. Parts that can't be read are left as None."""
    warnings = []
    for item in ET.fromstring(feed_text).iter("item"):
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or "").strip()
        link = (item.findtext("link") or "").strip()
        query = parse_qs(urlparse(link).fragment.removeprefix("?"))
        level = hazard = areas = starts = ends = None
        if m := TITLE.match(title):
            level, hazard = m[1], m[2]
        if (m := DESCRIPTION.search(description)) and "date" in query:
            year = int(query["date"][0][:4])
            areas = [a.strip() for a in m[1].split(",") if a.strip()]
            start = _local(m[2], m[3], year)
            end = _local(m[4], m[5], year)
            if end < start:
                end = _local(m[4], m[5], year + 1)
            starts, ends = start.strftime("%Y-%m-%dT%H:%M"), end.strftime("%Y-%m-%dT%H:%M")
        warnings.append({
            "id": query["id"][0] if "id" in query else (item.findtext("guid") or title),
            "title": title,
            "description": description,
            "link": link,
            "level": level,
            "hazard": hazard,
            "areas": areas,
            "starts": starts,
            "ends": ends,
        })
    return warnings


def local_warnings(warnings):
    """Warnings listing Gloucestershire, plus any whose areas can't be read."""
    return [w for w in warnings if w["areas"] is None or COUNTY in w["areas"]]


def update_log(records, warnings, now_iso):
    """The history log: a record is added when a warning first appears, its
    fields and updated_iso refreshed only when the Met Office changes it, and
    resolved_iso stamped once when it drops out of the feed. A warning that
    comes back is reopened."""
    by_id = {r["id"]: r for r in records}
    current = set()
    for warning in warnings:
        current.add(warning["id"])
        record = by_id.get(warning["id"])
        if record is None:
            record = dict(warning, first_seen_iso=now_iso, updated_iso=now_iso)
            records.append(record)
            by_id[warning["id"]] = record
            continue
        if any(record.get(f) != warning.get(f) for f in FIELDS) or record.get("resolved_iso"):
            record.update(warning)
            record["updated_iso"] = now_iso
            record.pop("resolved_iso", None)
    for record in records:
        if record["id"] not in current and not record.get("resolved_iso"):
            record["resolved_iso"] = now_iso

    cutoff = (datetime.datetime.now(datetime.timezone.utc)
              - datetime.timedelta(days=HISTORY_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    kept = [r for r in records if (r.get("resolved_iso") or r.get("updated_iso") or "") >= cutoff]
    kept.sort(key=lambda r: r.get("first_seen_iso", ""), reverse=True)
    return kept


def build_alert_html(warnings):
    rows = []
    for warning in warnings[:5]:
        ends = helper.alert_date(warning.get("ends"))
        text = warning["title"] + (f", until {ends}" if ends else "")
        rows.append((warning["link"] or SOURCE_PAGE, text))
    return helper.alert_rows("Weather warning", rows)


def build_atom_items(records):
    """One entry per warning in the Met Office's own words, linking to its
    page, dated by when it last changed so an update surfaces in readers."""
    return [{
        "title": r["title"],
        "link": r["link"] or SOURCE_PAGE,
        "summary": r["description"],
        "published_iso": r.get("updated_iso") or r.get("first_seen_iso"),
        "source": SOURCE,
    } for r in records[:50]]


if __name__ == "__main__":
    import json

    import requests

    root = helper.repo_root()
    data_dir = root / "_data"
    feeds_dir = root / "feeds"

    print("Downloading Met Office South West England warnings feed...")
    resp = requests.get(FEED_URL, headers=config.HEADERS, timeout=30)
    resp.raise_for_status()
    every = parse(resp.text)
    warnings = local_warnings(every)
    print(f"  {len(every)} warnings for the region, {len(warnings)} covering {COUNTY}")

    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    history_path = data_dir / "weather-warnings-history.json"
    records = json.loads(history_path.read_text()).get("records", []) if history_path.exists() else []
    records = update_log(records, warnings, now_iso)

    common = {"source": SOURCE, "source_url": SOURCE_PAGE, "licence": LICENCE, "refresh": "every 5 minutes"}
    helper.write_json(data_dir / "weather-warnings.json", {
        **common, "area": COUNTY, "count": len(warnings), "warnings": warnings,
    })
    helper.write_json(history_path, {
        **common,
        "note": "Log of Met Office weather warnings covering Gloucestershire, built up from each run.",
        "count": len(records), "records": records,
    })
    print(f"Wrote {len(warnings)} warnings; the log holds {len(records)}")

    site = helper.site_url()
    history_url = f"{site}/cheltenham-10-day-weather-forecast/weather-warnings"
    helper.write_items_atom(
        items=build_atom_items(records),
        filename=feeds_dir / "weather-warnings.xml",
        permalink_path="/feeds/weather-warnings.xml",
        feed_title="Cheltenham Weather Warnings",
        feed_subtitle="Met Office weather warnings covering Gloucestershire",
        self_url=f"{site}/feeds/weather-warnings.xml",
        alternate_url=history_url,
    )

    include_path = root / "_includes" / "weather-warnings-alert.html"
    include_path.write_text(helper.replace_chunk(
        include_path.read_text(), "weather_warnings_alert_marker", build_alert_html(warnings)))

    alerts_feed.rebuild()
