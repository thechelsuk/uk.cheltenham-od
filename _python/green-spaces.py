#!/usr/bin/env python3
"""Fetch Cheltenham's parks, playing fields, allotments and other green
spaces from Ordnance Survey's OS Open Greenspace, write _data/green-spaces.json.

OS publishes the product twice a year (April and October) through its free
Downloads API, split into 100 km grid squares. Cheltenham lies wholly inside
the SO square, a 1.5 MB GML file, so the national file is never needed. The
fetcher runs monthly but first asks the API for the product's version and
stops there if it matches the one already saved (pass --force to rebuild
anyway, for example after the ward boundaries change).

A site belongs to Cheltenham when the middle of its largest polygon falls
inside one of the borough's 20 wards (_data/wards/index.json), which also
gives each site its ward. Areas are measured on the British National Grid,
so they are true areas in square metres, net of any holes.
"""
import hashlib
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import datetime, timezone

import helper
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "green-spaces.json")
WARDS = os.path.join(HERE, "..", "_data", "wards", "index.json")

PRODUCT_URL = "https://api.os.uk/downloads/v1/products/OpenGreenspace"
SQUARE = "SO"
FORMAT = "GML"

GML = "{http://www.opengis.net/gml/3.2}"
OGSP = "{http://namespaces.ordnancesurvey.co.uk/Open/Greenspace/1.0}"

# OS's site functions: (label for the page, map group).
TYPES = {
    "Public Park Or Garden": ("Public park or garden", "parks"),
    "Playing Field": ("Playing field", "sports"),
    "Other Sports Facility": ("Sports facility", "sports"),
    "Tennis Court": ("Tennis court", "sports"),
    "Bowling Green": ("Bowling green", "sports"),
    "Golf Course": ("Golf course", "sports"),
    "Play Space": ("Play space", "play"),
    "Allotments Or Community Growing Spaces": ("Allotments or community growing space", "allotments"),
    "Cemetery": ("Cemetery", "burial"),
    "Religious Grounds": ("Religious grounds", "burial"),
}
GROUPS = [
    ("parks", "Parks & Gardens"),
    ("sports", "Sports & Playing Fields"),
    ("play", "Play Spaces"),
    ("allotments", "Allotments"),
    ("burial", "Cemeteries & Churchyards"),
]
# Access points of these types let a vehicle in; the rest are pedestrian only.
VEHICLE_ACCESS = {"Motor Vehicle", "Motor Vehicle And Pedestrian"}

_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def pos_list(el):
    values = [float(v) for v in el.text.split()]
    return list(zip(values[::2], values[1::2]))


def parse(stream):
    """Read the GML into (sites, entrances). Each site is {id, function, name,
    polygons}, a polygon being [exterior, *holes] rings of (easting, northing).
    entrances maps a site id to its {total, vehicle} access point counts."""
    sites = []
    entrances = defaultdict(lambda: {"total": 0, "vehicle": 0})
    for _, el in ET.iterparse(stream):
        if el.tag == OGSP + "GreenspaceSite":
            polygons = []
            for patch in el.iter(GML + "PolygonPatch"):
                rings = [pos_list(p) for p in patch.find(GML + "exterior").iter(GML + "posList")]
                for interior in patch.findall(GML + "interior"):
                    rings += [pos_list(p) for p in interior.iter(GML + "posList")]
                polygons.append(rings)
            sites.append({
                "id": el.get(GML + "id"),
                "function": el.findtext(OGSP + "function"),
                "name": (el.findtext(OGSP + "distinctiveName1") or "").strip(),
                "polygons": polygons,
            })
            el.clear()
        elif el.tag == OGSP + "AccessPoint":
            counts = entrances[el.findtext(OGSP + "refToGreenspaceSite")]
            counts["total"] += 1
            if el.findtext(OGSP + "accessType") in VEHICLE_ACCESS:
                counts["vehicle"] += 1
            el.clear()
    return sites, dict(entrances)


def ring_area(ring):
    """Area of a ring of (x, y) points in square units (shoelace)."""
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))) / 2


def ring_centroid(ring):
    """Centre of mass of a ring of (x, y) points, falling back to the average
    vertex for a degenerate ring."""
    twice_area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cross = x0 * y1 - x1 * y0
        twice_area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if not twice_area:
        return sum(x for x, _ in ring) / len(ring), sum(y for _, y in ring) / len(ring)
    return cx / (3 * twice_area), cy / (3 * twice_area)


def to_lat_lon(easting, northing):
    lon, lat = _to_wgs84.transform(easting, northing)
    return round(lat, 5), round(lon, 5)


def build(sites, entrances, wards, version):
    """Keep the sites inside Cheltenham's wards and shape the output payload."""
    kept = []
    for s in sites:
        if s["function"] not in TYPES:
            raise ValueError(f"Unknown OS Open Greenspace function: {s['function']!r}")
        label, group = TYPES[s["function"]]
        largest = max(s["polygons"], key=lambda rings: ring_area(rings[0]))
        lat, lon = to_lat_lon(*ring_centroid(largest[0]))
        ward = helper.ward_for(lat, lon, wards)
        if ward is None:
            continue
        square_metres = sum(ring_area(rings[0]) - sum(ring_area(h) for h in rings[1:]) for rings in s["polygons"])
        access = entrances.get(s["id"], {"total": 0, "vehicle": 0})
        kept.append({
            "name": s["name"] or f"{label}, {ward['name']}",
            "named": bool(s["name"]),
            "type": label,
            "group": group,
            "ward": ward["name"],
            "ward_slug": ward["slug"],
            "hectares": round(square_metres / 10_000, 2),
            "access_points": access["total"],
            "vehicle_access": access["vehicle"],
            "lat": lat,
            "lon": lon,
            "polygons": [[[list(to_lat_lon(*p)) for p in ring] for ring in rings] for rings in s["polygons"]],
        })
    kept.sort(key=lambda s: (-s["hectares"], s["name"]))

    total_ha = sum(s["hectares"] for s in kept)
    borough_km2 = sum(w["area_km2"] for w in wards)

    by_ward = []
    for w in sorted(wards, key=lambda w: w["name"]):
        mine = [s for s in kept if s["ward_slug"] == w["slug"]]
        hectares = sum(s["hectares"] for s in mine)
        named = [s for s in mine if s["named"]]
        by_ward.append({
            "name": w["name"],
            "slug": w["slug"],
            "sites": len(mine),
            "hectares": round(hectares, 1),
            # hectares / (km² x 100 ha) x 100 %
            "pct_of_ward": round(hectares / w["area_km2"], 1),
            "largest": named[0]["name"] if named else "",
        })

    groups = []
    for gid, name in GROUPS:
        mine = [s for s in kept if s["group"] == gid]
        groups.append({"id": gid, "name": name, "sites": len(mine),
                       "hectares": round(sum(s["hectares"] for s in mine), 1)})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ordnance Survey, OS Open Greenspace",
        "source_url": "https://www.ordnancesurvey.co.uk/products/os-open-greenspace",
        "licence": "Open Government Licence v3.0",
        "os_version": version,
        "totals": {
            "sites": len(kept),
            "hectares": round(total_ha, 1),
            "access_points": sum(s["access_points"] for s in kept),
            "pct_of_borough": round(total_ha / borough_km2, 1),
        },
        "groups": groups,
        "wards": by_ward,
        "sites": kept,
    }


def saved_version():
    try:
        with open(OUT) as f:
            return json.load(f).get("os_version")
    except (OSError, ValueError):
        return None


def download():
    """The SO square's GML zip, checked against the MD5 the API lists."""
    listing = helper.get(f"{PRODUCT_URL}/downloads", params={"area": SQUARE, "format": FORMAT}).json()
    entry = next(d for d in listing if d["area"] == SQUARE and d["format"] == FORMAT)
    body = helper.get(entry["url"], timeout=120).content
    if hashlib.md5(body).hexdigest() != entry["md5"]:
        raise ValueError(f"{entry['fileName']} failed its MD5 check")
    return body


def main():
    version = helper.get(PRODUCT_URL).json()["version"]
    if version == saved_version() and "--force" not in sys.argv:
        print(f"OS Open Greenspace is still {version}, nothing to do")
        return

    with zipfile.ZipFile(io.BytesIO(download())) as archive:
        member = next(n for n in archive.namelist() if n.lower().endswith(".gml"))
        with archive.open(member) as stream:
            sites, entrances = parse(stream)

    with open(WARDS) as f:
        wards = json.load(f)["wards"]

    payload = build(sites, entrances, wards, version)
    helper.write_json(OUT, payload)
    print(f"Wrote {payload['totals']['sites']} green spaces ({payload['totals']['hectares']} ha, "
          f"OS version {version}) to {OUT}")


if __name__ == "__main__":
    main()
