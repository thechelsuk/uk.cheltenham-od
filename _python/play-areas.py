#!/usr/bin/env python3
"""Fetch children's play areas within 10 miles of Cheltenham from
OpenStreetMap via Overpass, write _data/play-areas.json.

Refreshed monthly since playgrounds rarely open or close.

Only named, publicly accessible play areas are kept: unnamed polygons are
mostly extra pieces of a park that is already mapped (a toddler area beside a
main one), and access=private/customers/no covers school, pub-garden and
restaurant playgrounds. Entries carrying a `fixme` tag are dropped until a
mapper has confirmed them, and the same name within 150 m is treated as one
play area (OSM often splits a single site into several polygons).
"""
import math
import os
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "play-areas.json")

LAT, LNG = config.CENTRE
RADIUS_MILES = config.PLAY_AREAS_RADIUS_MILES
RADIUS_M = round(RADIUS_MILES * 1609.344)

EXCLUDE_ACCESS = {"private", "customers", "no"}
DEDUPE_M = 150
ACRONYMS = helper.DEFAULT_ACRONYMS | {"II", "V", "ABC", "KGV"}


def build_query():
    return (
        f'[out:json][timeout:90];'
        f'nwr(around:{RADIUS_M},{LAT},{LNG})["leisure"="playground"]["name"];'
        f'out center tags;'
    )


def metres_between(a, b):
    """Flat-earth approximation — plenty accurate at a 150 m scale."""
    return math.hypot(
        (a["lat"] - b["lat"]) * 111_320,
        (a["lon"] - b["lon"]) * 111_320 * math.cos(math.radians(a["lat"])),
    )


def main():
    elements = helper.overpass(build_query())

    play_areas = []
    for el in elements:
        tags = el.get("tags", {})
        if tags.get("access") in EXCLUDE_ACCESS or "fixme" in tags:
            continue
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue

        name = helper.clean_name(tags["name"], ACRONYMS)
        candidate = {
            "name":           name,
            "operator":       tags.get("operator", ""),
            "surface":        (tags.get("surface") or "").replace("_", " "),
            "theme":          (tags.get("playground:theme") or "").replace("_", " "),
            "distance_miles": round(helper.miles_from_centre(lat, lon), 1),
            "lat":            round(lat, 6),
            "lon":            round(lon, 6),
            "osm_url":        f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        }
        if any(p["name"] == name and metres_between(p, candidate) < DEDUPE_M for p in play_areas):
            continue
        play_areas.append(candidate)

    play_areas.sort(key=lambda p: (p["distance_miles"], p["name"]))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source":       "OpenStreetMap contributors",
        "source_url":   "https://www.openstreetmap.org/copyright",
        "licence":      "Open Database Licence (ODbL)",
        "radius_miles": RADIUS_MILES,
        "play_areas":   play_areas,
    }

    helper.write_json(OUT, output)

    print(f"Wrote {len(play_areas)} play areas to {OUT}")


if __name__ == "__main__":
    main()
