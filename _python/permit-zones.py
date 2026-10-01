#!/usr/bin/env python3
"""Draw Cheltenham's residents' permit parking zones as street lines, write
_data/permit-zones.json.

Which streets are in which zone is hand-curated in
_data/permit-zone-streets.json from Gloucestershire County Council's zone
maps. The council's boundary polygons are drawn on Ordnance Survey mapping
and can't be redistributed, so this fetches each listed street's line from
OpenStreetMap instead. Refreshed monthly: streets rarely change, and the
curated list is what needs checking when a zone is reviewed.

A street marked "part" only has some of its length inside the zone. Those are
trimmed to the stretch near the zone's whole streets, so a long road like
Bath Road isn't drawn end to end.
"""
import json
import math
import os
import re
import statistics
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
CURATED = os.path.join(HERE, "..", "_data", "permit-zone-streets.json")
OUT = os.path.join(HERE, "..", "_data", "permit-zones.json")

LAT, LNG = config.CENTRE
RADIUS_M = config.PERMIT_ZONES_RADIUS_M

# Ways of one street further than this from the zone's nearest way of that
# name are a different street that happens to share the name.
SAME_STREET_KM = 0.7
# A "part" street keeps the stretch within this distance of a whole street
# in the same zone, sampled every STEP_KM along its length.
PART_REACH_KM = 0.12
STEP_KM = 0.02

HIGHWAYS = "primary|secondary|tertiary|unclassified|residential|living_street|service|pedestrian|trunk"


def normalise(name):
    """'St. Luke's Road' and 'Saint Lukes Road' both become 'st lukes road'."""
    name = name.lower().replace("’", "").replace("'", "").replace(".", "")
    name = re.sub(r"^saint ", "st ", name)
    return re.sub(r"\s+", " ", name).strip()


def build_query():
    return (
        f"[out:json][timeout:90];"
        f'way(around:{RADIUS_M},{LAT},{LNG})["highway"~"^({HIGHWAYS})$"]["name"];'
        f"out geom;"
    )


def km(a, b):
    return helper.haversine_km(a[0], a[1], b[0], b[1])


def midpoint(line):
    return line[len(line) // 2]


def densify(line):
    """Points every STEP_KM along a line, so trimming isn't limited to the
    (sometimes far apart) OSM nodes."""
    points = [line[0]]
    for a, b in zip(line, line[1:]):
        steps = max(1, math.ceil(km(a, b) / STEP_KM))
        for i in range(1, steps + 1):
            t = i / steps
            points.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
    return points


def thin(run):
    """Every third sampled point plus the end, enough to draw a street."""
    return run[::3] + ([run[-1]] if (len(run) - 1) % 3 else [])


def trim(line, anchors):
    """The runs of a line that lie within PART_REACH_KM of any anchor point."""
    runs, current = [], []
    for point in densify(line):
        if any(km(point, a) <= PART_REACH_KM for a in anchors):
            current.append(point)
        else:
            if len(current) > 1:
                runs.append(thin(current))
            current = []
    if len(current) > 1:
        runs.append(thin(current))
    return runs


def pick_ways(lines, centre):
    """The ways of one street name that belong to this zone: the one nearest
    the zone's centre, plus any others close to it."""
    if not lines:
        return []
    nearest = min(lines, key=lambda line: km(midpoint(line), centre))
    return [line for line in lines if km(midpoint(line), midpoint(nearest)) <= SAME_STREET_KM]


def rounded(line):
    return [[round(lat, 5), round(lon, 5)] for lat, lon in line]


def build_zone(zone, ways_by_name):
    streets = zone["streets"]
    candidates = [midpoint(line) for s in streets if not s.get("part")
                  for line in ways_by_name.get(normalise(s["name"]), [])]
    if not candidates:
        candidates = [midpoint(line) for s in streets for line in ways_by_name.get(normalise(s["name"]), [])]
    centre = [statistics.median(p[0] for p in candidates), statistics.median(p[1] for p in candidates)]

    whole = {s["name"]: pick_ways(ways_by_name.get(normalise(s["name"]), []), centre)
             for s in streets if not s.get("part")}
    anchors = [point for lines in whole.values() for line in lines for point in densify(line)]

    out_streets, lines, unmatched = [], [], []
    for s in streets:
        part = bool(s.get("part"))
        ways = pick_ways(ways_by_name.get(normalise(s["name"]), []), centre)
        if part and anchors:
            ways = [run for way in ways for run in trim(way, anchors)]
        if not ways:
            unmatched.append(s["name"])
        for way in ways:
            lines.append({"street": s["name"], "part": part, "geometry": rounded(way)})
        pin = midpoint(max(ways, key=len)) if ways else None
        out_streets.append({
            "name": s["name"],
            "zone": zone["code"],
            "part": part,
            "lat": round(pin[0], 5) if pin else None,
            "lon": round(pin[1], 5) if pin else None,
        })

    return {
        "code": zone["code"],
        "name": zone["name"],
        "order": zone["order"],
        "map_url": zone["map_url"],
        "street_count": len(streets),
        "lines": lines,
    }, out_streets, unmatched


def main():
    with open(CURATED, encoding="utf-8") as f:
        curated = json.load(f)

    ways_by_name = {}
    for el in helper.overpass(build_query(), timeout=120):
        line = [[pt["lat"], pt["lon"]] for pt in el.get("geometry", []) if pt]
        if len(line) > 1:
            ways_by_name.setdefault(normalise(el["tags"]["name"]), []).append(line)

    zones, streets = [], []
    for zone in curated["zones"]:
        built, zone_streets, unmatched = build_zone(zone, ways_by_name)
        zones.append(built)
        streets.extend(zone_streets)
        for name in unmatched:
            print(f"Zone {zone['code']}: no OpenStreetMap match for {name}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked": curated["checked"],
        "source": curated["source"],
        "source_url": curated["source_url"],
        "geometry_source": "OpenStreetMap contributors",
        "geometry_source_url": "https://www.openstreetmap.org/copyright",
        "geometry_licence": "Open Database Licence (ODbL)",
        "zones": zones,
        "streets": sorted(streets, key=lambda s: (s["name"], s["zone"])),
    }

    helper.write_json(OUT, output)
    print(f"Wrote {len(zones)} zones, {len(streets)} streets to {OUT}")


if __name__ == "__main__":
    main()
