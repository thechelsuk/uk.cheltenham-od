#!/usr/bin/env python3
"""Filter GIAS schools to Cheltenham postcode districts, write _data/schools.json.

Run manually after downloading a new GIAS extract into _data-sources/ — not
part of any scheduled workflow, since that gitignored input file only exists
locally.
"""
import re
import csv
import json
import os

from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))          # _python/
SRC  = os.path.join(HERE, "..", "_data-sources", "edubasealldata.csv")
OUT  = os.path.join(HERE, "..", "_data", "schools.json")

DISTRICTS = {"GL50", "GL51", "GL52", "GL53", "GL54"}

# OSGB36 National Grid (Easting/Northing) -> WGS84 (lat/lon)
_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

def latlon(easting: str, northing: str):
    try:
        e, n = float(easting), float(northing)
    except (TypeError, ValueError):
        return None, None
    if not e or not n:
        return None, None
    lon, lat = _to_wgs84.transform(e, n)
    return round(lat, 6), round(lon, 6)

def district(postcode: str) -> str:
    pc = (postcode or "").strip().upper()
    return pc.split(" ")[0] if " " in pc else pc[:-3]

def address(row) -> str:
    parts = [row.get(k, "").strip() for k in ("Street", "Locality", "Address3", "Town")]
    return ", ".join(p for p in parts if p)

def normalize_url(url: str) -> str:
    url = url.strip()
    if not url:
        return ""
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = "https://" + url
    return url

schools = []
with open(SRC, encoding="latin-1", newline="") as f:
    for row in csv.DictReader(f):
        if district(row["Postcode"]) not in DISTRICTS:
            continue
        if row.get("EstablishmentStatus (name)", "").strip() != "Open":
            continue
        urn = row.get("URN", "").strip()
        lat, lon = latlon(row.get("Easting"), row.get("Northing"))
        schools.append({
            "name":                 row["EstablishmentName"].strip(),
            "phase":                row.get("PhaseOfEducation (name)", "").strip(),
            "type":                 row.get("TypeOfEstablishment (name)", "").strip(),
            "religious_character":  row.get("ReligiousCharacter (name)", "").strip(),
            "address":              address(row),
            "postcode":             row["Postcode"].strip(),
            "district":             district(row["Postcode"]),
            "website":              normalize_url(row.get("SchoolWebsite", "").strip()),
            "lat":                  lat,
            "lon":                  lon,
            "urn_url": f"https://get-information-schools.service.gov.uk/Establishments/Establishment/Details/{urn}",
        })

schools.sort(key=lambda s: s["name"])

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(schools, f, indent=2, ensure_ascii=False)   # array, not wrapped object

print(f"Wrote {len(schools)} schools to {OUT}")
