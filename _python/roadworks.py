#!/usr/bin/env python3
"""Fetch National Highways' planned roadworks within 10 miles of Cheltenham,
write _data/roadworks.json.

National Highways publishes one XML file a week (Mondays) listing every
planned works on its network (motorways and major A roads) for roughly the
next 15 days. The filename carries the publication date without zero padding
(nh_roadworks_2026_14_9.xml) and the dataset's listing on data.gov.uk is no
longer machine-readable, so this walks back from today until it finds the
newest file that exists.

Each works has a single centre point in British National Grid coordinates;
that is converted to lat/lon and used for the distance filter. Works that
have already finished are dropped on every run, so the daily schedule clears
completed works between the weekly files.

This only covers National Highways roads (here: M5, A417, A40, A46). Works on
local streets are held in Street Manager, which is push-only and not covered.
"""
import math
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from pyproj import Transformer

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "roadworks.json")

FILE_BASE = "https://s3.eu-west-2.amazonaws.com/webdata.nationalhighways.co.uk/ha-roadworks/"
DATASET_URL = "https://www.data.gov.uk/dataset/5b3267d8-4307-4eef-a9af-3a4c28224694/highways_agency_planned_roadworks"
HEADERS = config.HEADERS

LAT, LNG = config.CENTRE
RADIUS_MILES = config.ROADWORKS_RADIUS_MILES
LOOKBACK_DAYS = 14           # newest file is at most a week old; allow for a missed week
NS = "{WebTeam}"             # the XML's default namespace
LONDON = ZoneInfo("Europe/London")

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
DATE_PATTERN = re.compile(r"(\d{1,2})-([A-Z]{3})-(\d{4}) (\d{2}):(\d{2})")

_to_bng = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)
_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def fetch_latest_file(today):
    """Return (published_date, xml_bytes) for the newest weekly file.

    A file that isn't published yet answers 403 (S3 hides missing keys), so
    403/404 both mean "try the previous day"; anything else is a real error."""
    for offset in range(LOOKBACK_DAYS + 1):
        day = today - timedelta(days=offset)
        url = f"{FILE_BASE}nh_roadworks_{day.year}_{day.day}_{day.month}.xml"
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code == 200:
            return day, url, resp.content
        if resp.status_code not in (403, 404):
            resp.raise_for_status()
    raise RuntimeError(f"No National Highways roadworks file found in the last {LOOKBACK_DAYS} days")


def parse_datetime(text):
    """'21-SEP-2026 21:00' -> timezone-aware Europe/London datetime, or None."""
    m = DATE_PATTERN.match((text or "").strip().upper())
    if not m:
        return None
    day, mon, year, hour, minute = m.groups()
    return datetime(int(year), MONTHS[mon], int(day), int(hour), int(minute), tzinfo=LONDON)


def clean_description(text):
    """Join the description's lines into sentences: each line is ended with a
    full stop if it doesn't already have punctuation, then they are joined
    with spaces."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line]
    return " ".join(line if line[-1] in ".!?" else line + "." for line in lines)


def parse_works(xml_bytes, now):
    centre_x, centre_y = _to_bng.transform(LNG, LAT)
    items = []
    for w in ET.fromstring(xml_bytes).iter(f"{NS}HE_PLANNED_WORKS"):
        attrs = w.attrib
        point = w.find(f".//{NS}EASTNORTH[@CENTRE_EASTING]")
        start, end = parse_datetime(attrs.get("SDATE")), parse_datetime(attrs.get("EDATE"))
        if point is None or start is None or end is None or end < now:
            continue

        easting, northing = float(point.attrib["CENTRE_EASTING"]), float(point.attrib["CENTRE_NORTHING"])
        distance = math.hypot(easting - centre_x, northing - centre_y) / 1609.344
        if distance > RADIUS_MILES:
            continue

        lon, lat = _to_wgs84.transform(easting, northing)
        roads = list(dict.fromkeys(r.attrib["ROAD_NUMBER"] for r in w.iter(f"{NS}ROAD")))
        items.append({
            "id":             attrs.get("NEW_EVENT_NUMBER", ""),
            "roads":          roads,
            "description":    clean_description(attrs.get("DESCRIPTION")),
            "closure_type":   attrs.get("CLOSURE_TYPE", ""),
            "expected_delay": attrs.get("EXPDEL", ""),
            "start":          start.strftime("%Y-%m-%dT%H:%M"),
            "end":            end.strftime("%Y-%m-%dT%H:%M"),
            "in_progress":    start <= now,
            "distance_miles": round(distance, 1),
            "lat":            round(lat, 6),
            "lon":            round(lon, 6),
        })

    items.sort(key=lambda i: (i["start"], i["end"], i["id"]))
    return items


def main():
    now = datetime.now(LONDON)
    published, file_url, xml_bytes = fetch_latest_file(now.date())
    items = parse_works(xml_bytes, now)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "National Highways planned roadworks",
        "source_url":   DATASET_URL,
        "licence":      "Open Government Licence v3.0",
        "file_url":     file_url,
        "published":    published.isoformat(),
        "radius_miles": RADIUS_MILES,
        "items":        items,
    }

    helper.write_json(OUT, output)

    print(f"Wrote {len(items)} roadworks (file published {published}) to {OUT}")


if __name__ == "__main__":
    main()
