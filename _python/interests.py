#!/usr/bin/env python3
"""Fetch OSM points of interest (incl. plaques) near Cheltenham via Overpass,
write _data/points_of_interest.json as a distance-sorted array."""
import re
import os

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "points_of_interest.json")

LAT, LNG = config.CENTRE
RADIUS_M = config.INTERESTS_RADIUS_M

# Each entry: (Overpass selector, human label).
CATEGORIES = [
    ('["tourism"="museum"]',                          "Museum"),
    ('["leisure"="stadium"]',                         "Stadium"),
    ('["historic"="castle"]',                         "Castle"),
    ('["historic"="monastery"]',                      "Historic site"),
    ('["historic"="ruins"]',                          "Historic site"),
    ('["historic"="monument"]',                       "Historic site"),
    ('["historic"="archaeological_site"]',            "Historic site"),
    ('["natural"="peak"]',                            "Hill"),
    ('["tourism"="attraction"]',                      "Attraction"),
    ('["historic"="memorial"]["memorial"="plaque"]',  "Plaque"),
]


def classify(tags):
    if tags.get("historic") == "memorial" and tags.get("memorial") == "plaque":
        return "Plaque"
    if tags.get("tourism") == "museum":
        return "Museum"
    if tags.get("leisure") == "stadium":
        return "Stadium"
    if tags.get("historic") == "castle":
        return "Castle"
    if tags.get("historic") in ("monastery", "ruins", "monument", "archaeological_site"):
        return "Historic site"
    if tags.get("natural") == "peak":
        return "Hill"
    if tags.get("tourism") == "attraction":
        return "Attraction"
    return "Other"


def wiki_url(tags):
    w = tags.get("wikipedia", "")
    if ":" in w:                                   # e.g. "en:Cheltenham Town Hall"
        lang, title = w.split(":", 1)
        return f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
    return ""


def build_query():
    clauses = []
    for selector, _ in CATEGORIES:
        for kind in ("node", "way"):
            clauses.append(f"{kind}(around:{RADIUS_M},{LAT},{LNG}){selector};")
    return f"[out:json][timeout:90];({''.join(clauses)});out center tags;"

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "https://" + url
    return url

def main():
    elements = helper.overpass(build_query(), timeout=120)

    seen, pois = set(), []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        pois.append({
            "name":        name,
            "category":    classify(tags),
            "distance":    round(helper.miles_from_centre(lat, lon), 1),
            "postcode":    tags.get("addr:postcode", ""),
            "website": normalize_url(tags.get("website") or tags.get("contact:website", "")),
            "wikipedia":   wiki_url(tags),
            "gmaps":       f"https://www.google.com/maps/search/?api=1&query={lat},{lon}",
            "inscription": tags.get("inscription", ""),
            "lat":         lat,
            "lng":         lon,
        })

    pois.sort(key=lambda p: p["distance"])

    helper.write_json(OUT, pois)

    print(f"Wrote {len(pois)} points of interest to {OUT}")


if __name__ == "__main__":
    main()
