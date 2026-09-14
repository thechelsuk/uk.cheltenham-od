#!/usr/bin/env python3
"""Fetch hotels/guest houses near Cheltenham Racecourse from OpenStreetMap,
write _data/festival_hotels.json sorted by distance to the course."""
import json
import os
import math
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "races.json")

# VERIFY THESE — Cheltenham Racecourse (Prestbury Park). Confirm from OSM before publishing.
COURSE_LAT, COURSE_LNG = 51.9251, -2.0587
RADIUS_M = 8000                    # ~5 miles from the course — covers the town + fringes
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS  = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

TYPES = {"hotel": "Hotel", "guest_house": "Guest house"}


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)), 1)


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
    resp = requests.post(OVERPASS, data={"data": build_query()},
                         headers=HEADERS, timeout=120)
    resp.raise_for_status()
    elements = resp.json()["elements"]

    seen, hotels = set(), []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen:
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
            "distance": haversine_miles(COURSE_LAT, COURSE_LNG, lat, lng),
            "lat":      lat,
            "lng":      lng,
        })

    hotels.sort(key=lambda h: h["distance"])   # nearest the course first

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(hotels, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(hotels)} places to {OUT}")


if __name__ == "__main__":
    main()
