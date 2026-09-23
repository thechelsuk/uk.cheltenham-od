#!/usr/bin/env python3
"""Fetch parkrun events near Cheltenham from parkrun's own public events feed,
write _data/parkrun.json. Event locations essentially never change, so this
runs monthly rather than on a tighter schedule."""
import os
from datetime import datetime, timezone

import config
import helper


HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "parkrun.json")

EVENTS_URL = "https://images.parkrun.com/events.json"

MAX_MILES = config.PARKRUN_MAX_MILES              # cleanly separates Cheltenham's own events from
                             # Gloucester/Winchcombe/Tewkesbury parkruns (~6.4mi+)

SERIES = {1: "5k", 2: "Junior (2k)"}




def main():
    features = helper.get(EVENTS_URL).json()["events"]["features"]

    events = []
    for feature in features:
        lon, lat = feature["geometry"]["coordinates"]
        if helper.miles_from_centre(lat, lon) > MAX_MILES:
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

    helper.write_json(OUT, output)

    print(f"Wrote {len(events)} parkrun events to {OUT}")


if __name__ == "__main__":
    main()
