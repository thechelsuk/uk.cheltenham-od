#!/usr/bin/env python3
"""Fetch live storm overflow (sewage discharge) activity near Cheltenham from
Water UK's National Storm Overflow Hub, write _data/sewage-overflows.json.

Severn Trent publishes near-real-time Event Duration Monitor (EDM) status for
every overflow it operates, refreshed roughly hourly at source — this covers
the River Chelt itself plus the brooks that feed it (Wyman's Brook, Hatherley
Brook, Hyde Brook, Ham Brook, Mill Stream), filtered to a radius around
Cheltenham rather than a hardcoded watercourse name list, so it also picks up
any newly added or renamed monitoring points nearby.
"""
import json
import math
import os
from datetime import datetime, timezone

import requests
from dateutil.parser import parse as parse_date

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "sewage-overflows.json")

SOURCE_URL = ("https://portal-streamwaterdata.hub.arcgis.com/datasets/"
              "stwmaps::severn-trent-water-storm-overflow-activity.geojson")
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

CHELTENHAM_LAT  = 51.899
CHELTENHAM_LON  = -2.078
RADIUS_MILES    = 4          # covers the Chelt catchment without pulling in Gloucester's own brooks
EARTH_RADIUS_MI = 3958.8


def haversine_miles(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi       = math.radians(lat2 - lat1)
    dlambda    = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def friendly_date(raw):
    if not raw:
        return None
    try:
        return parse_date(raw).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return raw


def main():
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    features = resp.json().get("features", [])

    overflows = []
    for feat in features:
        props = feat.get("properties", {})
        lat, lon = props.get("Latitude"), props.get("Longitude")
        if lat is None or lon is None:
            continue
        dist = haversine_miles(CHELTENHAM_LAT, CHELTENHAM_LON, lat, lon)
        if dist > RADIUS_MILES:
            continue

        event_start, event_end = props.get("LatestEventStart"), props.get("LatestEventEnd")
        duration_hours = None
        if event_start and event_end:
            try:
                duration_hours = round((parse_date(event_end) - parse_date(event_start)).total_seconds() / 3600, 1)
            except (ValueError, TypeError):
                pass

        overflows.append({
            "id":                 props.get("Id"),
            "watercourse":        helper.clean_name(props.get("ReceivingWaterCourse") or ""),
            "discharging":        props.get("Status") == 1,
            "status_since":       friendly_date(props.get("StatusStart")),
            "latest_event_start": friendly_date(event_start),
            "latest_event_end":   friendly_date(event_end),
            "latest_event_hours": duration_hours,
            "distance_miles":     round(dist, 2),
            "lat":                lat,
            "lon":                lon,
        })

    overflows.sort(key=lambda o: (not o["discharging"], o["distance_miles"]))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "Water UK National Storm Overflow Hub (Severn Trent Water EDM feed)",
        "source_url":   "https://www.stwater.co.uk/in-my-area/storm-overflow-map/",
        "licence":      ("No formal licence stated — published as a free public near-real-time "
                          "data feed by Severn Trent Water via Water UK's National Storm "
                          "Overflow Hub"),
        "radius_miles": RADIUS_MILES,
        "overflows":    overflows,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    discharging = sum(1 for o in overflows if o["discharging"])
    print(f"Wrote {len(overflows)} overflow points to {OUT} ({discharging} currently discharging)")


if __name__ == "__main__":
    main()
