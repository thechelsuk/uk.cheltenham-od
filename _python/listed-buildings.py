#!/usr/bin/env python3
"""Fetch Historic England's National Heritage List for England (NHLE) listed
buildings, scheduled monuments and registered parks & gardens for Cheltenham,
writing _data/listed-buildings.json. Refreshed monthly since designations
rarely change."""
import json
import os
from datetime import datetime, timezone

import requests

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "listed-buildings.json")

SERVICE = (
    "https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/"
    "National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer"
)
SOURCE_URL = "https://www.api.gov.uk/he/national-heritage-list-for-england-nhle/"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

# Rough bounding box around Cheltenham (British National Grid, EPSG:27700).
# Slightly wider than the borough boundary; there is no local-authority field
# in the data so a geographic filter is the only option.
BBOX = (391000, 218000, 398000, 225000)  # (min E, min N, max E, max N)

LAYER_BUILDINGS = 0
LAYER_SCHEDULED_MONUMENTS = 6
LAYER_PARKS_GARDENS = 7

ACRONYMS = {"UK"}


def epoch_ms_to_iso_date(value):
    if not value:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()


def query_layer(layer, out_fields):
    min_e, min_n, max_e, max_n = BBOX
    params = {
        "where": f"Easting>={min_e} AND Easting<={max_e} AND Northing>={min_n} AND Northing<={max_n}",
        "outFields": ",".join(out_fields),
        "outSR": 4326,
        "f": "geojson",
    }
    resp = requests.get(f"{SERVICE}/{layer}/query", params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Layer {layer} query failed: {data['error']}")
    return data.get("features", [])


def fetch_buildings():
    features = query_layer(
        LAYER_BUILDINGS,
        ["ListEntry", "Name", "Grade", "ListDate", "AmendDate", "hyperlink", "Easting", "Northing"],
    )
    buildings = []
    for feature in features:
        props = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates")
        # Layer 0 is MultiPoint: coordinates is [[lon, lat]] with a single point.
        point = coords[0] if coords else None
        lon, lat = (point[0], point[1]) if point else (None, None)
        buildings.append({
            "list_entry": props.get("ListEntry"),
            "name": helper.clean_name(props.get("Name"), ACRONYMS),
            "grade": props.get("Grade"),
            "list_date": epoch_ms_to_iso_date(props.get("ListDate")),
            "amend_date": epoch_ms_to_iso_date(props.get("AmendDate")),
            "hyperlink": props.get("hyperlink"),
            "lat": lat,
            "lon": lon,
        })
    buildings.sort(key=lambda b: b["name"] or "")
    return buildings


def fetch_areas(layer, out_fields, date_field):
    features = query_layer(layer, out_fields)
    areas = []
    for feature in features:
        props = feature.get("properties", {})
        areas.append({
            "list_entry": props.get("ListEntry"),
            "name": helper.clean_name(props.get("Name"), ACRONYMS),
            "grade": props.get("Grade"),
            "list_date": epoch_ms_to_iso_date(props.get(date_field)),
            "hyperlink": props.get("hyperlink"),
            "geometry": feature.get("geometry"),
        })
    areas.sort(key=lambda a: a["name"] or "")
    return areas


def main():
    buildings = fetch_buildings()
    # Scheduled monuments have no Grade field, and use SchedDate rather than ListDate.
    scheduled_monuments = fetch_areas(
        LAYER_SCHEDULED_MONUMENTS, ["ListEntry", "Name", "SchedDate", "hyperlink"], "SchedDate"
    )
    parks_and_gardens = fetch_areas(
        LAYER_PARKS_GARDENS, ["ListEntry", "Name", "Grade", "RegDate", "hyperlink"], "RegDate"
    )

    grade_counts = {}
    for building in buildings:
        grade_counts[building["grade"]] = grade_counts.get(building["grade"], 0) + 1

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Historic England — National Heritage List for England",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "attribution": (
            f"© Crown Copyright {datetime.now(timezone.utc).year}. Contains Ordnance Survey data "
            f"© Crown copyright and database right {datetime.now(timezone.utc).year}. Released under OGL."
        ),
        "grade_counts": grade_counts,
        "buildings": buildings,
        "scheduled_monuments": scheduled_monuments,
        "parks_and_gardens": parks_and_gardens,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(
        f"Wrote {len(buildings)} listed buildings, {len(scheduled_monuments)} scheduled monuments "
        f"and {len(parks_and_gardens)} registered parks & gardens to {OUT}"
    )


if __name__ == "__main__":
    main()
