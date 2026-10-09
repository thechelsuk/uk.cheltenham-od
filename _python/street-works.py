#!/usr/bin/env python3
"""Street works on local roads around Cheltenham, from Street Manager open
data. Street Manager pushes every works event to the receiver Worker
(uk.cheltenham-od.receiver, on Cloudflare), which keeps the Gloucestershire
works and serves them at /works.json. This reads that, keeps the works within
config.STREET_WORKS_RADIUS_MILES of the town centre that are current or
coming up, and writes _data/street-works.json.

Runs with the hourly workflow. For a local preview without the Worker, pass a
saved works.json: python _python/street-works.py --sample path/to/works.json
"""
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config
import helper

SOURCE = "Department for Transport Street Manager"
SOURCE_URL = "https://www.gov.uk/guidance/find-and-use-roadworks-data"
LONDON = ZoneInfo("Europe/London")


def uk_time(stamp):
    """'2026-10-09T07:45:00.000Z' as UK local time, 'YYYY-MM-DDTHH:MM'."""
    utc = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return utc.astimezone(LONDON).strftime("%Y-%m-%dT%H:%M")


def uk_date(stamp):
    """The UK date of a Street Manager time. Planned dates are sent as UK
    midnight in UTC, so 15 October arrives as '2026-10-14T23:00:00.000Z'."""
    return uk_time(stamp)[:10] if stamp else None


def local_items(works, centre, radius_miles, today, wards=()):
    """Current and upcoming works near `centre`, unplanned first, then works
    in progress, then by start. Each is tagged with the Cheltenham ward it
    falls in, if any, for the ward pages."""
    items = []
    for w in works:
        if w.get("lat") is None or w.get("lon") is None:
            continue
        status = (w.get("status") or "").lower()
        if "cancel" in status or "completed" in status or w.get("actual_end"):
            continue
        if not w.get("actual_start") and w.get("proposed_end") and uk_date(w["proposed_end"]) < today:
            continue
        distance = helper.haversine_miles(centre[0], centre[1], w["lat"], w["lon"])
        if distance > radius_miles:
            continue
        started = bool(w.get("actual_start"))
        ward = helper.ward_for(w["lat"], w["lon"], wards) or {"name": "", "slug": ""}
        items.append({
            "id": w["id"],
            "street": helper.clean_name(w.get("street_name") or ""),
            "area": helper.clean_name(w.get("area_name") or w.get("town") or ""),
            "kind": "Unplanned" if w.get("immediate") else "Planned",
            "category": w.get("work_category") or "",
            "status": w.get("status") or ("In progress" if started else "Planned"),
            "in_progress": started,
            "traffic_management": w.get("traffic_management") or "",
            "road_closure": "road closure" in (w.get("traffic_management") or "").lower(),
            "promoter": w.get("promoter") or "",
            "start": uk_time(w["actual_start"]) if started else uk_date(w.get("proposed_start")),
            "end": uk_date(w.get("proposed_end")),
            "lat": w["lat"],
            "lon": w["lon"],
            "distance_miles": round(distance, 1),
            "ward": ward["name"],
            "ward_slug": ward["slug"],
        })
    items.sort(key=lambda i: (i["kind"] != "Unplanned", not i["in_progress"], i["start"] or ""))
    return items


def summarise(items):
    return {
        "total": len(items),
        "unplanned": sum(i["kind"] == "Unplanned" for i in items),
        "road_closures": sum(i["road_closure"] for i in items),
        "in_progress": sum(i["in_progress"] for i in items),
    }


def main():
    if "--sample" in sys.argv:
        payload = json.loads(open(sys.argv[sys.argv.index("--sample") + 1]).read())
    else:
        payload = helper.get(config.STREET_WORKS_URL).json()
    now = datetime.now(timezone.utc)
    today = now.astimezone(LONDON).date().isoformat()
    wards = json.loads((helper.repo_root() / "_data" / "wards" / "index.json").read_text())["wards"]
    items = local_items(payload.get("works", []), config.CENTRE, config.STREET_WORKS_RADIUS_MILES, today, wards)
    helper.write_json(helper.repo_root() / "_data" / "street-works.json", {
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "refresh": "every two hours",
        "radius_miles": config.STREET_WORKS_RADIUS_MILES,
        "summary": summarise(items),
        "items": items,
    })
    print(f"Wrote {len(items)} street works within {config.STREET_WORKS_RADIUS_MILES} miles of Cheltenham")


if __name__ == "__main__":
    main()
