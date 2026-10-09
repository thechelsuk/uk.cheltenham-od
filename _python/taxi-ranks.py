#!/usr/bin/env python3
"""Taxi ranks in Cheltenham, from Cheltenham Borough Council's Google My Maps
rank map and OpenStreetMap, plus any ranks the editor has checked in person
(_data/taxi-ranks-curated.json, which can also exclude or rename an OSM rank).

A rank on the council's map or the editor's list that OpenStreetMap also has,
within MATCH_METRES, is counted once under that name, with the number of
spaces from OpenStreetMap where it has one. An OSM-only
rank is named after its street, looked up from OpenStreetMap's Nominatim
service. Ranks change rarely, so this runs monthly.
"""
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import config
import helper

COUNCIL_MAP = "https://www.google.com/maps/d/viewer?mid=195JFz65LYxzFO0M_iNAOUJawnoTnkB4"
COUNCIL_KML = "https://www.google.com/maps/d/kml?mid=195JFz65LYxzFO0M_iNAOUJawnoTnkB4&forcekml=1"
COUNCIL_PAGE = "https://www.cheltenham.gov.uk/parking-travel-and-visitors/public-transport/"
NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
KML = "{http://www.opengis.net/kml/2.2}"
MATCH_METRES = 30
SEARCH_METRES = 8000

COUNCIL = "Cheltenham Borough Council"
OSM = "OpenStreetMap"
EDITOR = "Checked by Cheltenham Open Data"


def parse_kml(text):
    """[{name, lat, lon}] from the council's map export, without "taxi rank" in the name."""
    ranks = []
    for placemark in ET.fromstring(text.encode()).iter(f"{KML}Placemark"):
        name = (placemark.findtext(f"{KML}name") or "").strip()
        name = name.removesuffix(" taxi rank").removesuffix(" Taxi Rank").strip()
        coords = (placemark.findtext(f".//{KML}coordinates") or "").strip().split(",")
        if len(coords) < 2:
            continue
        ranks.append({"name": name, "lat": round(float(coords[1]), 6), "lon": round(float(coords[0]), 6)})
    return ranks


def osm_point(element):
    centre = element.get("center") or element
    return centre["lat"], centre["lon"]


def merge(council, osm_elements, streets, curated):
    """One list of ranks from the council's map, OSM and the editor's checks,
    nearest the town centre first."""
    excluded = {e["id"] for e in curated.get("exclude_osm", [])}
    renamed = {n["osm_id"]: n["name"] for n in curated.get("names", [])}
    ranks = [{"name": c["name"], "street": c["name"], "lat": c["lat"], "lon": c["lon"], "spaces": None,
              "sources": [COUNCIL]} for c in council]
    # Ranks checked in person join before OSM is matched, so a checked rank
    # that later appears in OSM is counted once rather than twice.
    for extra in curated.get("add", []):
        ranks.append({"name": extra["name"], "street": extra.get("street", ""), "lat": extra["lat"],
                      "lon": extra["lon"], "spaces": extra.get("spaces"), "sources": [EDITOR]})
    for element in osm_elements:
        if element["id"] in excluded:
            continue
        lat, lon = osm_point(element)
        tags = element.get("tags", {})
        spaces = int(tags["capacity"]) if str(tags.get("capacity", "")).isdigit() else None
        match = next((r for r in ranks if OSM not in r["sources"]
                      and helper.haversine_km(lat, lon, r["lat"], r["lon"]) * 1000 <= MATCH_METRES), None)
        if match:
            match["sources"].append(OSM)
            match["spaces"] = match["spaces"] or spaces
            continue
        street = streets.get(element["id"], "")
        ranks.append({"name": renamed.get(element["id"]) or tags.get("name") or street or "Taxi rank",
                      "street": street, "lat": round(lat, 6), "lon": round(lon, 6), "spaces": spaces,
                      "sources": [OSM]})
    for r in ranks:
        r["distance_miles"] = round(helper.miles_from_centre(r["lat"], r["lon"]), 2)
    return sorted(ranks, key=lambda r: r["distance_miles"])


def fetch_osm():
    lat, lon = config.CENTRE
    query = f"""[out:json][timeout:60];
(node["amenity"="taxi"](around:{SEARCH_METRES},{lat},{lon});way["amenity"="taxi"](around:{SEARCH_METRES},{lat},{lon}););
out center tags;"""
    return helper.overpass(query)


def street_names(elements):
    """{OSM id: street} for each OSM rank, one Nominatim lookup a second."""
    streets = {}
    for element in elements:
        lat, lon = osm_point(element)
        result = helper.get(NOMINATIM, params={"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 17}).json()
        streets[element["id"]] = result.get("address", {}).get("road", "")
        time.sleep(1.1)
    return streets


def main():
    root = helper.repo_root()
    curated = json.loads((root / "_data" / "taxi-ranks-curated.json").read_text())
    council = parse_kml(helper.get(COUNCIL_KML).text)
    elements = fetch_osm()
    excluded = {e["id"] for e in curated.get("exclude_osm", [])}
    ranks = merge(council, elements, street_names([e for e in elements if e["id"] not in excluded]), curated)
    helper.write_json(root / "_data" / "taxi-ranks.json", {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {"name": COUNCIL, "url": COUNCIL_PAGE, "licence": None},
            {"name": OSM, "url": "https://www.openstreetmap.org/copyright", "licence": "Open Database Licence (ODbL)"},
        ],
        "council_map": COUNCIL_MAP,
        "count": len(ranks),
        "ranks": ranks,
    })
    print(f"Wrote {len(ranks)} taxi ranks ({len(council)} from the council map, {len(elements)} in OpenStreetMap)")


if __name__ == "__main__":
    main()
