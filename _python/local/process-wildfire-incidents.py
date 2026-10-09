#!/usr/bin/env python3
"""Summarise grassland, woodland and crop fires around Cheltenham from the
fire statistics incident level datasets (the outdoor fires dataset), and write
_data/wildfire-incidents.json for the wildfire risk history page.

Run manually, once a year — not part of any scheduled workflow. MHCLG (the
Home Office until April 2025) publishes the outdoor fires dataset each summer,
covering incidents to the end of the previous March.

  1. Download the outdoor fires dataset files (.ods) from
     https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets
     into the gitignored _data-sources/outdoor-fires/ folder. Every .ods file in
     that folder is read, so replace the old files rather than adding to them.
  2. Make sure _data-sources/gloucestershire-postcodes.csv is present (the same
     postcode file _python/local/process-wards.py uses).
  3. python _python/local/process-wildfire-incidents.py

Incidents are published by small census area (LSOA). Each area is placed by its
population-weighted centroid from the ONS: areas whose nearest postcode is in
GL50-GL54 count as Cheltenham, and other areas within config.WILDFIRE_RADIUS_KM
of the town centre count as the surrounding area. The ward and district named
for each area are those of its nearest postcode.
"""
import csv
import json
import math
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import helper  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "_data-sources" / "outdoor-fires"
POSTCODES_CSV = ROOT / "_data-sources" / "gloucestershire-postcodes.csv"
OUT = ROOT / "_data" / "wildfire-incidents.json"

SOURCE = "Ministry of Housing, Communities and Local Government"
SOURCE_URL = "https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets"
LICENCE = "Open Government Licence v3.0"

CENTROIDS_URL = (
    "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
    "LSOA_PopCentroids_EW_2021_V4/FeatureServer/0/query"
)
# Wide enough to reach the far side of GL54 (Stow, Bourton, Northleach).
SEARCH_RADIUS_KM = 40
# A centroid further than this from any Gloucestershire postcode is over the
# county border, so its nearest postcode says nothing about where it is.
MAX_POSTCODE_KM = 3

LOCATION_TYPE = "Grassland, woodland and crops"
COUNTY = "Gloucestershire"
# Damage area bands by OUTDOOR_DAMAGE_AREA_CODE. The published descriptions
# for codes 2 and 3 were turned into dates ("06-Oct", "Nov-20") somewhere
# upstream, so the labels are taken from the code instead.
DAMAGE_BANDS = {
    1: "Up to 5 m²", 2: "6 to 10 m²", 3: "11 to 20 m²", 4: "21 to 50 m²", 5: "51 to 100 m²",
    6: "101 to 200 m²", 7: "201 to 500 m²", 8: "501 to 1,000 m²", 9: "1,001 to 2,000 m²",
    10: "2,001 to 5,000 m²", 11: "5,001 to 10,000 m²", 12: "Over 10,000 m²",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
OFFICE = "{urn:oasis:names:tc:opendocument:xmlns:office:1.0}"


def postcode_district(postcode):
    return postcode.strip().upper().split(" ")[0]


def classify_area(district, km_from_centre):
    if district in config.POSTCODE_DISTRICTS:
        return "cheltenham"
    if km_from_centre <= config.WILDFIRE_RADIUS_KM:
        return "surrounding"
    return None


def nearest_postcode(lat, lon, postcodes):
    """The (lat, lon, postcode, ...) tuple closest to the point. Equirectangular
    distance is plenty at county scale."""
    k = math.cos(math.radians(lat))
    return min(postcodes, key=lambda p: (p[0] - lat) ** 2 + ((p[1] - lon) * k) ** 2)


def incident_date(row):
    return f"{int(row['CALENDAR_YEAR']):04d}-{int(row['MONTH_CODE']):02d}-{int(row['DAY']):02d}"


def ods_rows(path, sheet="Datasheet"):
    """Rows of one sheet of an .ods file as dicts keyed by its header row,
    streamed so a file that unzips to hundreds of megabytes stays cheap."""
    header = None
    with zipfile.ZipFile(path).open("content.xml") as f:
        in_sheet = False
        for event, el in ET.iterparse(f, events=("start", "end")):
            if event == "start" and el.tag == TABLE + "table":
                in_sheet = el.get(TABLE + "name") == sheet
            elif event == "end" and el.tag == TABLE + "table-row":
                if in_sheet:
                    cells = []
                    for c in el:
                        repeat = min(int(c.get(TABLE + "number-columns-repeated", "1")), 50)
                        value = c.get(OFFICE + "value")
                        if value is None:
                            value = "".join("".join(p.itertext()) for p in c.iter(TEXT + "p"))
                        cells.extend([value] * repeat)
                    if header is None:
                        header = cells
                    else:
                        yield dict(zip(header, cells))
                el.clear()
            elif event == "end" and el.tag == TABLE + "table" and in_sheet:
                return


def load_postcodes():
    with open(POSTCODES_CSV, encoding="utf-8", newline="") as f:
        return [
            (float(r["Latitude"]), float(r["Longitude"]), r["Postcode"], r["Ward"], r["District"])
            for r in csv.DictReader(f)
            if r["In Use?"] == "Yes" and r["Latitude"]
        ]


def fetch_centroids():
    """{LSOA code: (lat, lon)} for every LSOA within SEARCH_RADIUS_KM."""
    lat, lon = config.CENTRE
    centroids, offset = {}, 0
    while True:
        payload = helper.get(CENTROIDS_URL, params={
            "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
            "distance": SEARCH_RADIUS_KM * 1000, "units": "esriSRUnit_Meter",
            "spatialRel": "esriSpatialRelIntersects", "where": "1=1",
            "outFields": "LSOA21CD", "outSR": 4326, "resultOffset": offset, "f": "json",
        }, timeout=60).json()
        features = payload["features"]
        for f in features:
            centroids[f["attributes"]["LSOA21CD"]] = (f["geometry"]["y"], f["geometry"]["x"])
        if not payload.get("exceededTransferLimit"):
            return centroids
        offset += len(features)


def place_areas(centroids, postcodes):
    """{LSOA code: {area, place, district}} for the areas the page covers."""
    clat, clon = config.CENTRE
    places = {}
    for code, (lat, lon) in centroids.items():
        nearest = nearest_postcode(lat, lon, postcodes)
        near_km = helper.haversine_km(lat, lon, nearest[0], nearest[1])
        district = postcode_district(nearest[2]) if near_km <= MAX_POSTCODE_KM else ""
        area = classify_area(district, helper.haversine_km(lat, lon, clat, clon))
        if area:
            places[code] = {"area": area, "place": nearest[3], "district": nearest[4]}
    return places


def damage_code(row):
    try:
        return int(row.get("OUTDOOR_DAMAGE_AREA_CODE") or 0)
    except ValueError:
        return 0


def damage_band(code):
    return DAMAGE_BANDS.get(code, "")


def summarise(fires, years, county=None, located=None):
    """Totals, yearly and monthly counts, busiest days, places and the
    largest fires, split between Cheltenham and the surrounding area.
    `county` ({year: fires}) adds Gloucestershire-wide counts, and `located`
    (a set of years) marks the years whose fires were published with a place."""
    def split(items):
        c = Counter(f["area"] for f in items)
        return {"cheltenham": c["cheltenham"], "surrounding": c["surrounding"], "total": len(items)}

    by_year = defaultdict(list)
    by_month = defaultdict(list)
    by_day = defaultdict(list)
    by_place = Counter()
    for f in fires:
        by_year[f["financial_year"]].append(f)
        by_month[int(f["date"][5:7])].append(f)
        by_day[f["date"]].append(f)
        by_place[(f["place"], f["district"], f["area"])] += 1

    deliberate = sum(1 for f in fires if f["deliberate"])
    totals = {
        "all": len(fires),
        "cheltenham": sum(1 for f in fires if f["area"] == "cheltenham"),
        "surrounding": sum(1 for f in fires if f["area"] == "surrounding"),
        "deliberate": deliberate,
        "deliberate_pct": round(100 * deliberate / len(fires)) if fires else 0,
    }
    for key in ("all", "cheltenham", "surrounding", "deliberate"):
        totals[f"{key}_display"] = f"{totals[key]:,}"

    busiest = sorted(by_day.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:10]
    largest = sorted((f for f in fires if f["damage"]),
                     key=lambda f: (-f["damage_code"], f["date"]))[:15]

    rows = []
    for y in years:
        row = {"year": y, **split(by_year[y])}
        if county is not None:
            row["county"] = county.get(y, 0)
            row["located"] = y in (located or set())
        rows.append(row)

    summary = {
        "totals": totals,
        "by_year": rows,
        "by_month": [{"month": MONTHS[m - 1], **split(by_month[m])} for m in range(1, 13)],
        "busiest_days": [{"date": d, "fires": len(items), **{k: v for k, v in split(items).items() if k != "total"}}
                         for d, items in busiest],
        "by_place": [{"place": p, "district": d, "area": a, "fires": n}
                     for (p, d, a), n in by_place.most_common(20)],
        "largest": [{"date": f["date"], "place": f["place"], "district": f["district"],
                     "area": f["area"], "damage": f["damage"]} for f in largest],
    }
    if county is not None:
        summary["county_total"] = sum(county.values())
        summary["county_total_display"] = f"{summary['county_total']:,}"
    return summary


def by_ward(fires, lsoa_ward, years, recent_years=5):
    """Fires per Cheltenham ward, all years and the last `recent_years` years,
    using the ONS best-fit lookup from small census area to ward."""
    recent = set(years[-recent_years:])
    counts = {}
    for f in fires:
        ward = lsoa_ward.get(f.get("lsoa"))
        if not ward:
            continue
        row = counts.setdefault(ward, {"ward": ward, "fires": 0, "recent": 0})
        row["fires"] += 1
        row["recent"] += f["financial_year"] in recent
    return sorted(counts.values(), key=lambda r: r["ward"])


def main():
    files = sorted(SOURCE_DIR.glob("*.ods"))
    if not files:
        sys.exit(f"No .ods files in {SOURCE_DIR}; see the instructions at the top of this script.")

    postcodes = load_postcodes()
    lsoa_ward = {a["code"]: a["ward_name"] for a in json.loads((ROOT / "_data" / "small-areas.json").read_text())["lsoas"]}
    places = place_areas(fetch_centroids(), postcodes)
    print(f"{len(places)} small areas: "
          f"{sum(p['area'] == 'cheltenham' for p in places.values())} Cheltenham, "
          f"{sum(p['area'] == 'surrounding' for p in places.values())} surrounding")

    fires, years, county, located = [], set(), Counter(), set()
    for path in files:
        print(f"Reading {path.name}...")
        for row in ods_rows(path):
            if not row.get("FINANCIAL_YEAR"):
                continue
            years.add(row["FINANCIAL_YEAR"])
            if row.get("OUTDOOR_LOCATION_TYPE") != LOCATION_TYPE:
                continue
            if row.get("FRS_NAME_TERRITORY") == COUNTY:
                county[row["FINANCIAL_YEAR"]] += 1
                if row.get("LSOA_CODE", "").startswith("E01"):
                    located.add(row["FINANCIAL_YEAR"])
            place = places.get(row.get("LSOA_CODE"))
            if not place:
                continue
            fires.append({
                "lsoa": row["LSOA_CODE"],
                "date": incident_date(row),
                "financial_year": row["FINANCIAL_YEAR"],
                "deliberate": "deliberate" in (row.get("ACCIDENTAL_OR_DELIBERATE") or "").lower(),
                "damage_code": damage_code(row),
                "damage": damage_band(damage_code(row)),
                **place,
            })

    fires.sort(key=lambda f: f["date"])
    years = sorted(years)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "radius_km": config.WILDFIRE_RADIUS_KM,
        "first_date": fires[0]["date"] if fires else None,
        "last_date": fires[-1]["date"] if fires else None,
        "first_year": years[0],
        "last_year": years[-1],
        "last_located_year": max(located) if located else None,
        "county": COUNTY,
        **summarise(fires, years, county=county, located=located),
        "recent_years": sorted(located)[-5:],
        "by_ward": by_ward(fires, lsoa_ward, sorted(located)),
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(fires):,} fires ({years[0]} to {years[-1]}) to {OUT}")


if __name__ == "__main__":
    main()
