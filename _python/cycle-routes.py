#!/usr/bin/env python3
"""Fetch cycle tracks and on-road cycle lanes near Cheltenham from
OpenStreetMap via Overpass, write _data/cycle-routes.json.

OSM has ~1,700 ways carrying *some* cycleway-related tag near Cheltenham,
but most of them (cycleway:*=no) just document that a road has *no*
cycling provision, and a few (cycleway:*=separate) just point at a
dedicated path mapped as its own way elsewhere. Only real infrastructure
is kept: highway=cycleway (a dedicated track), or a cycleway:*/cycleway
tag whose value is track/lane/shared_lane/share_busway/opposite_lane/both.

Named/numbered routes are grouped from two things OSM actually tags in
this area: `ncn_ref` (National Cycle Network route number, e.g. NCN 41
through Cheltenham) directly on the way, and the Honeybourne Line — the
old railway path to Bishop's Cleeve, consistently named "Honeybourne" on
its constituent ways. Everything else renders on the map but isn't
pulled out into its own table row (that's mostly ordinary street-level
lanes, plus a handful of named mountain-bike park trails at Dog Bark/
Leckhampton that aren't "getting around town" routes).

Pump tracks/bike parks are a separate, hand-curated concern — see
_data/cycle-venues.json — not fetched here.
"""
import math
import os

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "cycle-routes.json")

LAT, LNG = config.CENTRE
RADIUS_M = config.CYCLE_ROUTES_RADIUS_M

REAL_LANE_VALUES = {"track", "lane", "shared_lane", "share_busway", "opposite_lane", "both"}
HONEYBOURNE_NAME = "Honeybourne"


def build_query():
    return (
        f"[out:json][timeout:60];"
        f'(way(around:{RADIUS_M},{LAT},{LNG})["highway"="cycleway"];'
        f'way(around:{RADIUS_M},{LAT},{LNG})["cycleway"];'
        f'way(around:{RADIUS_M},{LAT},{LNG})["cycleway:left"];'
        f'way(around:{RADIUS_M},{LAT},{LNG})["cycleway:right"];'
        f'way(around:{RADIUS_M},{LAT},{LNG})["cycleway:both"];);'
        f"out geom;"
    )


def classify(tags):
    if tags.get("highway") == "cycleway":
        return "track"
    for key in ("cycleway", "cycleway:left", "cycleway:right", "cycleway:both"):
        if tags.get(key) in REAL_LANE_VALUES:
            return "lane"
    return None


def route_key(tags):
    """Returns a (name, ref) tuple if this way belongs to a named/numbered
    route worth its own table row, else None."""
    if tags.get("ncn_ref"):
        return f"National Cycle Network {tags['ncn_ref']}", f"NCN {tags['ncn_ref']}"
    if tags.get("name") == HONEYBOURNE_NAME:
        return "Honeybourne Line", None
    return None


def haversine_km(points):
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return total


def main():
    elements = helper.overpass(build_query(), timeout=90)

    segments = []
    route_lengths = {}   # (name, ref) -> km
    route_kinds = {}      # (name, ref) -> kind of its first segment, for the table

    for el in elements:
        tags = el.get("tags", {})
        kind = classify(tags)
        if not kind:
            continue

        geometry = [[pt["lat"], pt["lon"]] for pt in el.get("geometry", []) if pt]
        if len(geometry) < 2:
            continue

        route = route_key(tags)
        segments.append({
            "kind": kind,
            "name": tags.get("name"),
            "route_ref": route[1] if route else None,
            "surface": tags.get("surface"),
            "lit": tags.get("lit") == "yes",
            "geometry": geometry,
        })

        if route:
            route_lengths[route] = route_lengths.get(route, 0.0) + haversine_km(geometry)
            route_kinds.setdefault(route, kind)

    routes = [
        {
            "name": name,
            "ref": ref,
            "distance_km": round(km, 1),
            "kind": route_kinds[(name, ref)],
        }
        for (name, ref), km in sorted(route_lengths.items(), key=lambda kv: -kv[1])
    ]

    output = {
        "generated_at": helper.updated_timestamp(),
        "source": "OpenStreetMap contributors, via Overpass",
        "source_url": "https://www.openstreetmap.org/copyright",
        "licence": "Open Database Licence (ODbL) — © OpenStreetMap contributors",
        "routes": routes,
        "segments": segments,
    }

    helper.write_json(OUT, output)

    print(f"Wrote {len(segments)} segments ({len(routes)} named routes) to {OUT}")


if __name__ == "__main__":
    main()
