#!/usr/bin/env python3
"""Fetch public car parks near Cheltenham from OpenStreetMap via Overpass,
write _data/car-parks.json.

OSM has hundreds of amenity=parking entries in Cheltenham, most of them tiny
private/staff/customer lots. This keeps only ones that are genuinely
"where do I park in town": access isn't private/customers/residents-only,
and it's either run by a known public car park operator, or carries data
(capacity, a fee tag, or park_ride) that marks it as a real car park rather
than an informal spot.

Note: several Cheltenham Borough Council car parks have their *charging
hours* recorded in OSM's `fee` tag instead of a proper `opening_hours` tag
(e.g. "Mo-Sa 08:00-20:00; PH 08:00-20:00; Su 10:00-20:00") — a known local
tagging quirk, not a mistake in this script. Where that's detected, `fee` is
reported as true and the time range is used as `charging_hours`.
"""
import json
import os
import re

import requests

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "car-parks.json")

LAT, LNG = 51.899, -2.078          # Cheltenham centre
RADIUS_M = 6000                    # ~3.7 miles — keeps it to the town, matches hotels.py
OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS  = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

EXCLUDE_ACCESS   = {"private", "customers", "residents", "no"}
PUBLIC_OPERATORS = {"cheltenham borough council", "national car parks",
                     "apcoa parking (uk) limited", "gloucestershire county council"}

# A "charging hours" string wrongly stored in the fee tag, e.g. "Mo-Sa 08:00-20:00; PH 08:00-20:00"
HOURS_PATTERN = re.compile(r"\d{2}:\d{2}")


def build_query():
    return (
        f'[out:json][timeout:60];'
        f'(node(around:{RADIUS_M},{LAT},{LNG})["amenity"="parking"]["name"];'
        f'way(around:{RADIUS_M},{LAT},{LNG})["amenity"="parking"]["name"];);'
        f'out center tags;'
    )


def is_public(tags):
    if tags.get("access", "yes") in EXCLUDE_ACCESS:
        return False
    if (tags.get("operator") or "").strip().lower() in PUBLIC_OPERATORS:
        return True
    return bool(tags.get("capacity") or tags.get("fee") or tags.get("park_ride"))


def parse_fee_and_hours(tags):
    """Return (fee, charging_hours) — see module docstring for the OSM tagging quirk."""
    raw_fee = (tags.get("fee") or "").strip()
    opening_hours = tags.get("opening_hours")
    if HOURS_PATTERN.search(raw_fee):
        return True, raw_fee
    if raw_fee.lower() == "yes":
        return True, opening_hours
    if raw_fee.lower() == "no":
        return False, opening_hours
    return None, opening_hours


def main():
    resp = requests.post(OVERPASS, data={"data": build_query()}, headers=HEADERS, timeout=90)
    resp.raise_for_status()
    elements = resp.json().get("elements", [])

    seen, car_parks = set(), []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or name in seen or not is_public(tags):
            continue
        seen.add(name)

        fee, charging_hours = parse_fee_and_hours(tags)
        car_parks.append({
            "name":            helper.clean_name(name),
            "operator":        tags.get("operator", ""),
            "capacity":        int(tags["capacity"]) if str(tags.get("capacity", "")).isdigit() else None,
            "fee":             fee,
            "charging_hours":  charging_hours,
            "maxstay":         tags.get("maxstay", ""),
            "park_and_ride":   tags.get("park_ride") == "yes",
            "lat":             el.get("lat") or el.get("center", {}).get("lat"),
            "lon":             el.get("lon") or el.get("center", {}).get("lon"),
        })

    car_parks.sort(key=lambda c: c["name"])

    output = {
        "generated_at": helper.updated_timestamp(),
        "source":       "OpenStreetMap contributors, via Overpass",
        "source_url":   "https://www.openstreetmap.org/copyright",
        "licence":      "Open Database Licence (ODbL) — © OpenStreetMap contributors",
        "car_parks":    car_parks,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(car_parks)} car parks to {OUT}")


if __name__ == "__main__":
    main()
