#!/usr/bin/env python3
"""Fetch river water quality readings near Cheltenham from the Environment
Agency's Water Quality Archive, write _data/water-quality.json.

Unlike the sewage overflow feed, this isn't live — the EA visits each
sampling point roughly monthly and tests a batch of determinands (pH,
temperature, nutrients, etc) in one go. This fetches the most recent visit's
readings for every open freshwater-river sampling point within a radius of
Cheltenham, one row per determinand (a "tidy" table) rather than picking a
curated subset — that's a judgement call better left to the reader.
"""
import os
import re
from datetime import datetime, timedelta, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "water-quality.json")

BASE_URL = "https://environment.data.gov.uk/water-quality"
HEADERS = {
    "Accept": "application/ld+json",
    "Accept-Crs": "http://www.opengis.net/def/crs/EPSG/0/4326",
}

CHELTENHAM_LAT, CHELTENHAM_LON = config.CENTRE
RADIUS_KM = config.WATER_QUALITY_RADIUS_KM  # ~5 miles, matches the sewage overflow catchment
LOOKBACK_DAYS   = 150          # comfortably covers at least one monthly visit

WKT_POINT = re.compile(r"POINT\(([-\d.]+) ([-\d.]+)\)")




def fetch_nearby_points():
    params = {
        "latitude": CHELTENHAM_LAT,
        "longitude": CHELTENHAM_LON,
        "radius": RADIUS_KM,
        "samplingPointStatus": "O",     # OPEN — still actively monitored
        "samplingPointType": "F6",      # FRESHWATER - RIVERS
        "limit": 100,
    }
    return helper.get(f"{BASE_URL}/sampling-point", params=params, headers=HEADERS).json().get("member", [])


def fetch_latest_readings(notation):
    since = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    params = {"dateFrom": since, "limit": 250}
    observations = helper.get(f"{BASE_URL}/sampling-point/{notation}/observation",
                              params=params, headers=HEADERS).json().get("member", [])
    if not observations:
        return None, []

    latest_date = max(o.get("phenomenonTime", "") for o in observations)[:10]
    readings = [
        {
            "determinand": o.get("observedProperty", {}).get("prefLabel", ""),
            "value":       o.get("hasSimpleResult"),
            "unit":        (o.get("hasResult") or {}).get("hasUnit", {}).get("altLabel", ""),
        }
        for o in observations
        if o.get("phenomenonTime", "").startswith(latest_date)
    ]
    return latest_date, readings


def main():
    points = fetch_nearby_points()

    sampling_points = []
    for point in points:
        notation = point.get("notation")
        wkt = point.get("geometry", {}).get("asWKT", "")
        match = WKT_POINT.search(wkt)
        if not match:
            continue
        lon, lat = float(match.group(1)), float(match.group(2))

        latest_date, readings = fetch_latest_readings(notation)
        if not readings:
            continue

        sampling_points.append({
            "notation":     notation,
            "name":         helper.clean_name(point.get("prefLabel", "")),
            "latest_date":  latest_date,
            "distance_miles": round(helper.miles_from_centre(lat, lon), 2),
            "lat":          lat,
            "lon":          lon,
            "readings":     readings,
        })

    sampling_points.sort(key=lambda p: p["distance_miles"])

    output = {
        "generated_at":   helper.updated_timestamp(),
        "source":         "Environment Agency Water Quality Archive",
        "source_url":     "https://environment.data.gov.uk/water-quality/",
        "licence":        "Open Government Licence v3.0",
        "radius_miles":   round(RADIUS_KM / 1.60934, 1),
        "sampling_points": sampling_points,
    }

    helper.write_json(OUT, output)

    total_readings = sum(len(p["readings"]) for p in sampling_points)
    print(f"Wrote {len(sampling_points)} sampling points ({total_readings} readings) to {OUT}")


if __name__ == "__main__":
    main()
