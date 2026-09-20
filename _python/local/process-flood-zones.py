#!/usr/bin/env python3
"""Build a small map layer of Flood Zones 2 and 3 for Cheltenham, write
_data/flood-zones.json.

Run manually — not part of any scheduled workflow. The Environment Agency
updates its Flood Map for Planning as needed rather than on a fixed schedule, and
each run downloads around 10MB of very detailed boundaries, which is more than a
page needs. Re-run it when the monthly data refresh reminder asks.

  python _python/local/process-flood-zones.py

It downloads every flood zone polygon that touches the Cheltenham area from the
Environment Agency's OGC API Features service (no key), clips them to the area
so the huge Severn floodplain doesn't come along, simplifies the outlines to a
about 9 metres, and merges them into one shape per zone.

Flood Zone 2 is land with between a 1 in 1,000 (0.1%) and 1 in 100 (1%) annual
chance of flooding from rivers, and Flood Zone 3 is land with a 1 in 100 (1%)
or greater chance, both ignoring the effect of flood defences.

  Service:  https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1
  Dataset:  https://environment.data.gov.uk/dataset/04532375-a198-476e-985e-0579a0a11b47
"""
import json
import os
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))          # _python/local/
OUT = os.path.join(HERE, "..", "..", "_data", "flood-zones.json")

SERVICE = "https://environment.data.gov.uk/spatialdata/flood-map-for-planning-flood-zones/ogc/features/v1"
COLLECTION = "Flood_Zones_2_3_Rivers_and_Sea"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

# The area covered, as west, south, east, north in longitude/latitude. It takes in the
# whole borough and a margin.
WEST, SOUTH, EAST, NORTH = -2.16, 51.85, -2.00, 51.95
PAGE_SIZE = 100
TOLERANCE = 0.00008        # about 9 metres: outlines are simplified to within this
MIN_AREA = 1e-7            # about 760 square metres: smaller fragments are dropped
DECIMALS = 5               # about 1 metre
ZONES = {"FZ2": "Flood Zone 2", "FZ3": "Flood Zone 3"}


def fetch_features():
    """Every polygon in the area. This service pages with startIndex (it ignores offset) and
    reports numberMatched, so stop when it has them all rather than trusting the page size."""
    features, start = [], 0
    while True:
        resp = requests.get(f"{SERVICE}/collections/{COLLECTION}/items", headers=HEADERS, timeout=120,
                            params={"f": "json", "bbox": f"{WEST},{SOUTH},{EAST},{NORTH}",
                                    "limit": PAGE_SIZE, "startIndex": start})
        resp.raise_for_status()
        body = resp.json()
        page = body.get("features", [])
        features += page
        total = body.get("numberMatched", len(features))
        print(f"  downloaded {len(features)} of {total} polygons", flush=True)
        if not page or len(features) >= total:
            return features
        start += len(page)


def polygons(geometry):
    """A geometry as a list of polygons, each a list of rings of (lon, lat) points."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    return geometry["coordinates"]


def clip_ring(ring):
    """Clip one ring to the area rectangle (Sutherland-Hodgman), one edge at a time."""
    edges = [
        (lambda p: p[0] >= WEST, lambda a, b: (WEST, a[1] + (b[1] - a[1]) * (WEST - a[0]) / (b[0] - a[0]))),
        (lambda p: p[0] <= EAST, lambda a, b: (EAST, a[1] + (b[1] - a[1]) * (EAST - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] >= SOUTH, lambda a, b: (a[0] + (b[0] - a[0]) * (SOUTH - a[1]) / (b[1] - a[1]), SOUTH)),
        (lambda p: p[1] <= NORTH, lambda a, b: (a[0] + (b[0] - a[0]) * (NORTH - a[1]) / (b[1] - a[1]), NORTH)),
    ]
    points = [tuple(p[:2]) for p in ring[:-1]] if ring[0] == ring[-1] else [tuple(p[:2]) for p in ring]
    for inside, cross in edges:
        if not points:
            break
        clipped = []
        for i, current in enumerate(points):
            previous = points[i - 1]
            if inside(current):
                if not inside(previous):
                    clipped.append(cross(previous, current))
                clipped.append(current)
            elif inside(previous):
                clipped.append(cross(previous, current))
        points = clipped
    return points


def thin(points):
    """Drop points closer than half the tolerance to the last one kept: a fast first pass,
    because the source outlines have a vertex every metre or so and the next step is slow on those."""
    if len(points) < 3:
        return points
    limit = (TOLERANCE / 2) ** 2
    kept = [points[0]]
    for point in points[1:-1]:
        if (point[0] - kept[-1][0]) ** 2 + (point[1] - kept[-1][1]) ** 2 >= limit:
            kept.append(point)
    return kept + [points[-1]]


def simplify(points):
    """Ramer-Douglas-Peucker on an open list of points, without recursion."""
    points = thin(points)
    if len(points) < 3:
        return points
    keep = {0, len(points) - 1}
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        (x1, y1), (x2, y2) = points[start], points[end]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        worst, index = 0.0, None
        for i in range(start + 1, end):
            x, y = points[i]
            distance = abs(dy * (x - x1) - dx * (y - y1)) / length if length else ((x - x1) ** 2 + (y - y1) ** 2) ** 0.5
            if distance > worst:
                worst, index = distance, i
        if index is not None and worst > TOLERANCE:
            keep.add(index)
            stack += [(start, index), (index, end)]
    return [points[i] for i in sorted(keep)]


def ring_area(points):
    return abs(sum(points[i][0] * points[i - 1][1] - points[i - 1][0] * points[i][1] for i in range(len(points)))) / 2


def process_ring(ring):
    points = simplify(clip_ring(ring))
    if len(points) < 3 or ring_area(points) < MIN_AREA:
        return None
    rounded = [[round(x, DECIMALS), round(y, DECIMALS)] for x, y in points]
    return rounded + [rounded[0]]


def build(features):
    by_zone = {code: [] for code in ZONES}
    for feature in features:
        zone = feature["properties"].get("flood_zone")
        if zone not in by_zone:
            continue
        for polygon in polygons(feature["geometry"]):
            rings = [process_ring(r) for r in polygon]
            if rings[0] is None:
                continue  # the outer ring is gone, so the polygon is too
            by_zone[zone].append([r for r in rings if r])
    return by_zone


def main():
    print("Downloading flood zones for the Cheltenham area...")
    features = fetch_features()
    by_zone = build(features)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Environment Agency Flood Map for Planning: Flood Zones 2 and 3",
        "source_url": "https://environment.data.gov.uk/dataset/04532375-a198-476e-985e-0579a0a11b47",
        "licence": "Open Government Licence v3.0",
        "area": {"west": WEST, "south": SOUTH, "east": EAST, "north": NORTH},
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"zone": code, "label": label},
             "geometry": {"type": "MultiPolygon", "coordinates": by_zone[code]}}
            for code, label in ZONES.items()
        ],
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))
    size = os.path.getsize(OUT)
    counts = ", ".join(f"{label}: {len(by_zone[code])} polygons" for code, label in ZONES.items())
    print(f"Wrote {counts} to {os.path.normpath(OUT)} ({size / 1024:.0f} KB) from {len(features)} downloaded features")


if __name__ == "__main__":
    main()
