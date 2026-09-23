"""Find Post Office branches around Cheltenham from OpenStreetMap (via the
Overpass API, no key needed) and write _data/post-offices.json.

Run from anywhere:
    python _python/post-office.py
"""

import os

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "post-offices.json")

LAT, LON = config.CENTRE
RADIUS_M = config.POST_OFFICES_RADIUS_M


def build_query():
    return f"""
    [out:json][timeout:25];
    (
      node["amenity"="post_office"](around:{RADIUS_M},{LAT},{LON});
      way["amenity"="post_office"](around:{RADIUS_M},{LAT},{LON});
    );
    out center tags;
    """


def record(el):
    tags = el.get("tags", {})
    addr_parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city"),
        tags.get("addr:postcode"),
    ]
    return {
        "name": tags.get("name", "Post Office"),
        "address": ", ".join(p for p in addr_parts if p),
        "lat": el.get("lat") or el.get("center", {}).get("lat"),
        "lon": el.get("lon") or el.get("center", {}).get("lon"),
        "osm_type": el["type"],
        "osm_id": el["id"],
    }


def main():
    records = [record(el) for el in helper.overpass(build_query(), timeout=30)]
    helper.write_json(OUT, records)
    print(f"Saved {len(records)} post office(s) to {OUT}")


if __name__ == "__main__":
    main()
