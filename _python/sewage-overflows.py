#!/usr/bin/env python3
"""Fetch live storm overflow (sewage discharge) activity near Cheltenham from
Water UK's National Storm Overflow Hub, write _data/sewage-overflows.json.

Severn Trent publishes near-real-time Event Duration Monitor (EDM) status for
every overflow it operates, refreshed roughly hourly at source — this covers
the River Chelt itself plus the brooks that feed it (Wyman's Brook, Hatherley
Brook, Hyde Brook, Ham Brook, Mill Stream), filtered to a radius around
Cheltenham rather than a hardcoded watercourse name list, so it also picks up
any newly added or renamed monitoring points nearby.

Queries the underlying ArcGIS Feature Service directly with a spatial filter,
rather than the Hub's "static" geojson download link — that link now kicks
off an async on-demand export and returns a 202 "still generating, check
back later" JSON body instead of the data, which silently produced an empty
overflows list (no exception, since .get("features", []) just came back
empty) until this was noticed on the live site."""
import json
import os
from datetime import datetime, timezone

from dateutil.parser import parse as parse_date

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "sewage-overflows.json")

QUERY_URL = ("https://services1.arcgis.com/NO7lTIlnxRMMG9Gw/arcgis/rest/services/"
             "Severn_Trent_Water_Storm_Overflow_Activity/FeatureServer/0/query")
FRIENDLY_SOURCE_URL = "https://www.stwater.co.uk/in-my-area/storm-overflow-map/"

CHELTENHAM_LAT, CHELTENHAM_LON = config.CENTRE
RADIUS_MILES = config.SEWAGE_RADIUS_MILES  # covers the Chelt catchment without pulling in Gloucester's own brooks




def parse_field_date(raw):
    """Esri fields come back as epoch milliseconds (an int), not a string."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw / 1000, tz=timezone.utc)
    try:
        return parse_date(raw)
    except (ValueError, TypeError):
        return None


def friendly_date(raw):
    parsed = parse_field_date(raw)
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else None


def main():
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson",
        "geometry": json.dumps({"x": CHELTENHAM_LON, "y": CHELTENHAM_LAT,
                                 "spatialReference": {"wkid": 4326}}),
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "distance": RADIUS_MILES,
        "units": "esriSRUnit_StatuteMile",
        "spatialRel": "esriSpatialRelIntersects",
    }
    body = helper.get(QUERY_URL, params=params).json()
    if "features" not in body:
        raise SystemExit(f"Unexpected response from storm overflow query (no 'features' key): {body}")
    features = body["features"]

    overflows = []
    for feat in features:
        props = feat.get("properties", {})
        lat, lon = props.get("Latitude"), props.get("Longitude")
        if lat is None or lon is None:
            continue
        dist = helper.miles_from_centre(lat, lon)
        if dist > RADIUS_MILES:
            continue

        event_start, event_end = props.get("LatestEventStart"), props.get("LatestEventEnd")
        start_dt, end_dt = parse_field_date(event_start), parse_field_date(event_end)
        duration_hours = round((end_dt - start_dt).total_seconds() / 3600, 1) if start_dt and end_dt else None

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
        "source_url":   FRIENDLY_SOURCE_URL,
        "radius_miles": RADIUS_MILES,
        "overflows":    overflows,
    }

    helper.write_json(OUT, output)

    discharging = sum(1 for o in overflows if o["discharging"])
    print(f"Wrote {len(overflows)} overflow points to {OUT} ({discharging} currently discharging)")


if __name__ == "__main__":
    main()
