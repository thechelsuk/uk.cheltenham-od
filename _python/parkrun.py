#!/usr/bin/env python3
"""Fetch parkrun events near Cheltenham from parkrun's own public events feed,
write _data/parkrun.json. Event locations essentially never change, so this
runs monthly rather than on a tighter schedule."""
import json
import math
import os
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "parkrun.json")

EVENTS_URL = "https://images.parkrun.com/events.json"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

LAT, LON = 51.894, -2.083   # Cheltenham centre
MAX_MILES = 4               # cleanly separates Cheltenham's own events from
                             # Gloucester/Winchcombe/Tewkesbury parkruns (~6.4mi+)

SERIES = {1: "5k", 2: "Junior (2k)"}


def miles_between(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


def main():
    resp = requests.get(EVENTS_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    features = resp.json()["events"]["features"]

    events = []
    for feature in features:
        lon, lat = feature["geometry"]["coordinates"]
        if miles_between(LAT, LON, lat, lon) > MAX_MILES:
            continue
        props = feature["properties"]
        events.append({
            "name":       props.get("EventLongName", "").replace("’", "'"),
            "location":   props.get("EventLocation", "").replace("’", "'"),
            "distance":   SERIES.get(props.get("seriesid"), ""),
            "lat":        lat,
            "lon":        lon,
            "event_page": f"https://www.parkrun.org.uk/{props.get('eventname')}/",
        })

    events.sort(key=lambda e: e["name"])

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "parkrun",
        "source_url": "https://www.parkrun.org.uk/",
        "events": events,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(events)} parkrun events to {OUT}")


if __name__ == "__main__":
    main()
