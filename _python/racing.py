#!/usr/bin/env python3
"""Fetch hotels/guest houses near Cheltenham Racecourse from OpenStreetMap,
write _data/races.json sorted by distance to the course. Hotels change rarely, so it
runs monthly with the other OpenStreetMap scripts."""
import os

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "races.json")

COURSE_LAT, COURSE_LNG = config.RACECOURSE
RADIUS_M = config.RACING_RADIUS_M

TYPES = {"hotel": "Hotel", "guest_house": "Guest house"}

# OpenStreetMap tags both Ellenborough Park's grounds (way 448480127) and its
# listed building (way 448480136) as tourism=hotel; skip the building so the
# hotel is listed once. Remove once the building's hotel tag is fixed upstream.
EXCLUDED_NAMES = {"Ellenborough Park Hotel"}


def address(tags):
    line = " ".join(p for p in (tags.get("addr:housenumber", "").strip(),
                                 tags.get("addr:street", "").strip()) if p)
    suburb = tags.get("addr:suburb", "").strip()
    return ", ".join(p for p in (line, suburb) if p)


def parse_stars(tags):
    digits = "".join(c for c in tags.get("stars", "").strip() if c.isdigit())
    return int(digits) if digits else None


def build_query():
    clauses = []
    for value in TYPES:
        for kind in ("node", "way"):
            clauses.append(f'{kind}(around:{RADIUS_M},{COURSE_LAT},{COURSE_LNG})["tourism"="{value}"]["name"];')
    return f"[out:json][timeout:90];({''.join(clauses)});out center tags;"


def main():
    elements = helper.overpass(build_query(), timeout=120)

    seen, hotels = set(), []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen or name in EXCLUDED_NAMES:
            continue
        seen.add(name)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lng = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lng is None:
            continue
        hotels.append({
            "name":     name,
            "type":     TYPES.get(tags.get("tourism"), "Hotel"),
            "stars":    parse_stars(tags),
            "address":  address(tags),
            "postcode": tags.get("addr:postcode", ""),
            "distance": round(helper.haversine_miles(COURSE_LAT, COURSE_LNG, lat, lng), 1),
            "lat":      lat,
            "lng":      lng,
        })

    hotels.sort(key=lambda h: h["distance"])   # nearest the course first

    helper.write_json(OUT, hotels)

    print(f"Wrote {len(hotels)} places to {OUT}")


if __name__ == "__main__":
    main()
