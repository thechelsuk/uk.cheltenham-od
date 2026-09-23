"""Fetch InPost parcel locker locations in Cheltenham from InPost's public
locations API (the same one powering their own "find a locker" map — no API
key required), and write normalised JSON to Jekyll's _data dir.

Source: https://api-uk-global-points.easypack24.net
"""

import datetime
import re

import config
import helper

API_URL = "https://api-uk-global-points.easypack24.net/v1/points"

CHELTENHAM_LAT, CHELTENHAM_LON = config.CENTRE
MAX_DISTANCE_M = config.INPOST_MAX_DISTANCE_M
LIMIT = 100
AREA_NAME = "cheltenham"

VENUE_PREFIX = re.compile(r"^(24/7\s+)?InPost Locker\s*-\s*", re.IGNORECASE)

ACRONYMS = {"UK"}


def fetch_points():
    resp = helper.request_with_retry(
        "GET", API_URL,
        params={
            "relative_point": f"{CHELTENHAM_LAT},{CHELTENHAM_LON}",
            "limit": LIMIT,
            "max_distance": MAX_DISTANCE_M,
            "status": "Operating",
            "virtual": "0",
        },
        timeout=20,
    )
    return resp.json().get("items", [])


def venue_name(point):
    building_number = (point.get("address_details") or {}).get("building_number") or ""
    name = VENUE_PREFIX.sub("", building_number).strip()
    return helper.clean_name(name or point.get("display_name") or "InPost Locker", ACRONYMS)


def clean_point(point):
    details = point.get("address_details") or {}
    street = details.get("street") or ""
    postcode = details.get("post_code") or ""
    location = point.get("location") or {}
    return {
        "id": point.get("name"),
        "name": venue_name(point),
        "street": helper.clean_name(street, ACRONYMS),
        "postcode": postcode,
        "lat": location.get("latitude"),
        "lon": location.get("longitude"),
        "is_247": bool(point.get("location_247")),
        "location_description": point.get("location_description") or "",
        "functions": point.get("functions") or [],
    }


if __name__ == "__main__":
    out_path = helper.repo_root() / "_data" / "inpost-lockers.json"

    print("Fetching InPost locker locations...")
    points = fetch_points()
    print(f"  {len(points)} lockers within {MAX_DISTANCE_M / 1000:.0f}km")

    local = [
        p for p in points
        if ((p.get("address_details") or {}).get("city") or "").strip().lower() == AREA_NAME
    ]
    print(f"  {len(local)} in Cheltenham")

    lockers = sorted((clean_point(p) for p in local), key=lambda locker: locker["name"].lower())

    payload = {
        "updated":     helper.updated_timestamp(),
        "updated_iso": datetime.date.today().isoformat(),
        "source":      "InPost",
        "source_url":  "https://www.inpost.co.uk/",
        "refresh":     "every two hours",
        "count":       len(lockers),
        "lockers":     lockers,
    }

    helper.write_json(out_path, payload)
    print(f"Wrote {len(lockers)} lockers to {out_path}")
