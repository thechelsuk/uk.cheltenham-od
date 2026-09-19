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
import json
import math
import os
import time

import requests

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "play-areas.json")

LAT, LNG = 51.899, -2.078          # Cheltenham centre
RADIUS_MILES = 10
RADIUS_M = round(RADIUS_MILES * 1609.344)
OVERPASS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
HEADERS  = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

EXCLUDE_ACCESS = {"private", "customers", "no"}
DEDUPE_M = 150
ACRONYMS = helper.DEFAULT_ACRONYMS | {"II", "V", "ABC", "KGV"}


def build_query():
    return (
        f'[out:json][timeout:90];'
        f'nwr(around:{RADIUS_M},{LAT},{LNG})["leisure"="playground"]["name"];'
        f'out center tags;'
    )


def fetch_elements():
    """POST the query, trying each Overpass endpoint twice — the public
    instances occasionally return a transient dispatcher error."""
    last_error = None
    for endpoint in OVERPASS:
        for attempt in range(2):
            try:
                resp = requests.post(endpoint, data={"data": build_query()}, headers=HEADERS, timeout=120)
                resp.raise_for_status()
                return resp.json()["elements"]
            except (requests.RequestException, ValueError, KeyError) as e:
                last_error = e
                print(f"Overpass {endpoint} attempt {attempt + 1} failed: {e}")
                time.sleep(10)
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


def distance_miles(lat, lon):
    """Great-circle (haversine) distance from the Cheltenham centre point."""
    p1, p2 = math.radians(LAT), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - LNG)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def metres_between(a, b):
    """Flat-earth approximation — plenty accurate at a 150 m scale."""
    return math.hypot(
        (a["lat"] - b["lat"]) * 111_320,
        (a["lon"] - b["lon"]) * 111_320 * math.cos(math.radians(a["lat"])),
    )


def main():
    elements = fetch_elements()

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
            "distance_miles": round(distance_miles(lat, lon), 1),
            "lat":            round(lat, 6),
            "lon":            round(lon, 6),
            "osm_url":        f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        }
        if any(p["name"] == name and metres_between(p, candidate) < DEDUPE_M for p in play_areas):
            continue
        play_areas.append(candidate)

    play_areas.sort(key=lambda p: (p["distance_miles"], p["name"]))

    output = {
        "generated_at": helper.updated_timestamp(),
        "source":       "OpenStreetMap contributors, via Overpass",
        "source_url":   "https://www.openstreetmap.org/copyright",
        "licence":      "Open Database Licence (ODbL) — © OpenStreetMap contributors",
        "radius_miles": RADIUS_MILES,
        "play_areas":   play_areas,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(play_areas)} play areas to {OUT}")


if __name__ == "__main__":
    main()
