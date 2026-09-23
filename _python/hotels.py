#!/usr/bin/env python3
"""Fetch hotels and guest houses near Cheltenham from OpenStreetMap via Overpass,
write _data/hotels.json."""
import os

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "hotels.json")

LAT, LNG = config.CENTRE
RADIUS_M = config.HOTELS_RADIUS_M

TYPES = {"hotel": "Hotel", "guest_house": "Guest house"}


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
            clauses.append(f'{kind}(around:{RADIUS_M},{LAT},{LNG})["tourism"="{value}"]["name"];')
    return f"[out:json][timeout:90];({''.join(clauses)});out center tags;"


def main():
    elements = helper.overpass(build_query(), timeout=120)

    seen, hotels = set(), []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        hotels.append({
            "name":     name,
            "type":     TYPES.get(tags.get("tourism"), "Hotel"),
            "stars":    parse_stars(tags),
            "address":  address(tags),
            "postcode": tags.get("addr:postcode", ""),
            "lat":      el.get("lat") or el.get("center", {}).get("lat"),
            "lng":      el.get("lon") or el.get("center", {}).get("lon")

        })

    hotels.sort(key=lambda h: h["name"])

    helper.write_json(OUT, hotels)

    print(f"Wrote {len(hotels)} hotels and guest houses to {OUT}")


if __name__ == "__main__":
    main()
