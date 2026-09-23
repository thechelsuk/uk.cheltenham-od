#!/usr/bin/env python3
"""Fetch Cheltenham Borough Council's local authority land and assets data
(2021 and 2023 snapshots) and write _data/council-land-and-assets.json.

The council's own open data page (a Local Government Transparency Code
requirement) has since gone offline, so this reads chrismytton's mirror of
the original CSVs on GitHub. Run manually, not on a schedule, since these are
historical snapshots rather than a live feed; the data will not change again:

  python _python/local/council-land-and-assets.py"""
import sys
import csv
import io
import json
import os
from datetime import datetime, timezone

import requests
from pyproj import Transformer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import config  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "_data", "council-land-and-assets.json")

REPO = "https://raw.githubusercontent.com/chrismytton/cheltenham-council-land-and-assets/main"
SOURCE_URL = "https://github.com/chrismytton/cheltenham-council-land-and-assets"
ORIGINAL_SOURCE_URL = "https://web.archive.org/web/2023/https://www.cheltenham.gov.uk/info/16/open_data/1190/local_authority_land_and_assets"

YEARS = [2021, 2023]

_to_wgs84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def fetch_csv(year):
    url = f"{REPO}/local_authority_land_and_assets_{year}.csv"
    resp = requests.get(url, headers=config.HEADERS, timeout=30)
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def to_latlon(geo_x, geo_y):
    if not geo_x or not geo_y:
        return None, None
    lon, lat = _to_wgs84.transform(float(geo_x), float(geo_y))
    return lat, lon


def normalise_2021(row):
    address = ", ".join(p for p in (
        row.get("PropertyName", "").strip(),
        row.get("StreetName", "").strip(),
        row.get("PostTown", "").strip(),
    ) if p)
    lat, lon = to_latlon(row.get("GeoX"), row.get("GeoY"))
    return {
        "year": 2021,
        "uprn": row.get("UPRN", "").strip(),
        "asset_code": row.get("AssetCode", "").strip(),
        "address": address,
        "postcode": row.get("PostCode", "").strip().replace("\n", ""),
        "tenure_type": row.get("TenureType", "").strip(),
        "tenure_detail": row.get("TenureDetail", "").strip(),
        "holding_type": row.get("HoldingType", "").strip(),
        "lat": lat,
        "lon": lon,
    }


def normalise_2023(row):
    lat, lon = to_latlon(row.get("GeoX"), row.get("GeoY"))
    return {
        "year": 2023,
        "uprn": row.get("UPRN", "").strip(),
        "asset_code": row.get("AssetCode", "").strip(),
        "address": row.get("Site Address", "").strip(),
        "postcode": "",
        "tenure_type": row.get("TenureType", "").strip(),
        "tenure_detail": row.get("Tenure Detail", "").strip(),
        "holding_type": row.get("Holding Type", "").strip(),
        "lat": lat,
        "lon": lon,
    }


NORMALISERS = {2021: normalise_2021, 2023: normalise_2023}


def is_blank_row(row):
    """The council's CSV exports end with a couple of stray rows that are
    just commas (every field empty) — skip those rather than normalising
    them into placeholder entries."""
    return not any(v.strip() for v in row.values() if v)


def main():
    items = []
    for year in YEARS:
        rows = fetch_csv(year)
        normalise = NORMALISERS[year]
        items.extend(normalise(row) for row in rows if not is_blank_row(row))

    output = {
        "generated_at": None,
        "source": "chrismytton/cheltenham-council-land-and-assets (GitHub mirror)",
        "source_url": SOURCE_URL,
        "original_source_url": ORIGINAL_SOURCE_URL,        "items": items,
    }
    output["generated_at"] = datetime.now(timezone.utc).isoformat()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(items)} land and asset records to {OUT}")


if __name__ == "__main__":
    main()
