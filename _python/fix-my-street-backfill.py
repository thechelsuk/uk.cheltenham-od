#!/usr/bin/env python3
"""One-off backfill of _data/fix-my-street-history.json from FixMyStreet's
Open311 API, since the hourly RSS feed only ever shows the newest 20 reports.

Fetches every report sent to Gloucestershire County Council (highways) and
Cheltenham Borough Council (litter, fly-tipping, graffiti, parks) over the
history window, keeps those within 10km of the town centre, and merges them
into the history log alongside whatever the hourly job has already recorded.
Reports sent to neighbouring district councils (Tewkesbury, Cotswold) aren't
covered, so those only appear from when the hourly job first sees them.

Open311 caps each response at the newest 1,000 reports and has no geographic
filter, so the county council feed is paged backwards through time.

Run manually, not from a workflow:
    python _python/fix-my-street-backfill.py
"""
import importlib.util
import json
import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

import helper

# fix-my-street.py has a hyphen in its name, so it can't be imported normally.
_spec = importlib.util.spec_from_file_location("fms", helper.repo_root() / "_python/fix-my-street.py")
fms = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fms)

OPEN311_URL = "https://www.fixmystreet.com/open311/v2/requests.xml"
AUTHORITIES = {"Gloucestershire County Council": 2226, "Cheltenham Borough Council": 2326}
CENTRE = (51.897991, -2.071308)
RADIUS_KM = 10
PAGE_CAP = 1000
PAUSE_SECONDS = 2
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk)"}


def distance_km(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(a))


def fetch_authority(agency_id, start, name):
    """Yield <request> elements for one authority, newest first, paging
    backwards by shrinking end_date until the window holds under PAGE_CAP."""
    end = None
    seen = set()
    while True:
        params = {
            "jurisdiction_id": "fixmystreet",
            "agency_responsible": agency_id,
            "start_date": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if end:
            params["end_date"] = end.strftime("%Y-%m-%dT%H:%M:%SZ")
        resp = requests.get(OPEN311_URL, params=params, headers=HEADERS, timeout=120)
        resp.raise_for_status()
        requests_xml = list(ET.fromstring(resp.content).iter("request"))
        new = [r for r in requests_xml if r.findtext("service_request_id") not in seen]
        print(f"  {name}: {len(requests_xml)} returned, {len(new)} new (end_date={params.get('end_date', 'now')})")
        for r in new:
            seen.add(r.findtext("service_request_id"))
            yield r
        if len(requests_xml) < PAGE_CAP or not new:
            return
        oldest = min(datetime.fromisoformat(r.findtext("requested_datetime")) for r in requests_xml)
        end = oldest.astimezone(timezone.utc)
        time.sleep(PAUSE_SECONDS)


def to_record(node, default_group, rules):
    lat, lon = float(node.findtext("lat")), float(node.findtext("long"))
    report_id = node.findtext("service_request_id")
    category = (node.findtext("service_name") or "").strip()
    return {
        "id": report_id,
        "title": fms.clean_title(node.findtext("title") or ""),
        "url": f"https://www.fixmystreet.com/report/{report_id}",
        "category": category,
        "group": fms.categorise(category, default_group, rules),
        "description": fms.clean_description(node.findtext("detail")),
        "lat": lat,
        "lon": lon,
        "published_iso": datetime.fromisoformat(node.findtext("requested_datetime")).isoformat(),
    }


if __name__ == "__main__":
    root = helper.repo_root()
    data_dir = root / "_data"
    default_group, rules = fms.load_category_rules(data_dir / "fix-my-street-categories.json")

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    start = now - timedelta(days=fms.HISTORY_RETENTION_DAYS)

    history_path = data_dir / "fix-my-street-history.json"
    existing = json.loads(history_path.read_text()).get("records", []) if history_path.exists() else []
    known = {r["id"] for r in existing}

    added = []
    for name, agency_id in AUTHORITIES.items():
        print(f"Fetching {name}")
        for node in fetch_authority(agency_id, start, name):
            try:
                record = to_record(node, default_group, rules)
            except (TypeError, ValueError):
                continue
            if record["id"] in known:
                continue
            if distance_km(*CENTRE, record["lat"], record["lon"]) > RADIUS_KM:
                continue
            record["first_seen_iso"] = record["published_iso"]
            record["last_seen_iso"] = now_iso
            known.add(record["id"])
            added.append(record)
        time.sleep(PAUSE_SECONDS)

    # An empty merge just prunes anything outside the window and re-sorts.
    records = fms.merge_history(existing + added, [], now_iso)
    helper.write_json(history_path, fms.payload(now, {
        "retention_days": fms.HISTORY_RETENTION_DAYS,
        "count": len(records),
        "groups": fms.group_counts(records),
        "by_month": fms.month_counts(records),
        "records": records,
    }))
    print(f"Added {len(added)} reports; history now holds {len(records)}")
