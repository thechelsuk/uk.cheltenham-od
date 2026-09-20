#!/usr/bin/env python3
"""Fetch the dental practices in Cheltenham and write _data/dentists.json.

Practices come from the NHS Organisation Data Service (ODS) ORD API, which is
open and needs no key: every active organisation with the General Dental
Practice role (RO110) in a Cheltenham postcode district. That is the NHS's own
directory of dental practices, so practices that only offer private care are
mostly not in it. ODS has no coordinates or phone numbers, so each practice's
postcode is geocoded in one bulk call to postcodes.io.

Dental practices change slowly, so a monthly refresh is plenty.
"""
import json
import math
import os
from datetime import datetime, timezone

import requests

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "dentists.json")

ODS = "https://directory.spineservices.nhs.uk/ORD/2-0-0"
POSTCODES = "https://api.postcodes.io/postcodes"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

ROLE_ID = "RO110"                  # General Dental Practice
DISTRICTS = ["GL50", "GL51", "GL52", "GL53"]  # the same catchment as the GP and pharmacy finder
LAT, LNG = 51.899, -2.078          # Cheltenham centre
LIST_LIMIT = 1000
ACRONYMS = helper.DEFAULT_ACRONYMS | {"NHS"}


def ods_get(path, **params):
    resp = requests.get(f"{ODS}/{path}", params=params, timeout=30,
                        headers={**HEADERS, "Accept": "application/json"})
    resp.raise_for_status()
    return resp.json()


def list_practices():
    """Every active dental practice in the postcode districts, keyed by ODS code.

    ODS rejects Offset=0 with a 406, so each district is asked for in one call
    rather than paged; a warning flags it if a district ever hits the limit."""
    practices = {}
    for district in DISTRICTS:
        rows = ods_get("organisations", PostCode=district, PrimaryRoleId=ROLE_ID,
                       Status="Active", Limit=LIST_LIMIT).get("Organisations", [])
        if len(rows) >= LIST_LIMIT:
            print(f"Warning: ODS returned {LIST_LIMIT} practices for {district}, the limit; some may be missing")
        practices.update({row["OrgId"]: row for row in rows})
    return practices


def address(code):
    loc = ods_get(f"organisations/{code}")["Organisation"]["GeoLoc"]["Location"]
    lines = [loc.get(k) for k in ("AddrLn1", "AddrLn2", "AddrLn3", "Town", "County")]
    return ", ".join(helper.clean_name(line, ACRONYMS) for line in lines if line)


def geocode(postcodes):
    """postcodes.io bulk lookup -> {postcode: (lat, lon)}."""
    resp = requests.post(POSTCODES, json={"postcodes": sorted(postcodes)}, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return {r["query"]: (r["result"]["latitude"], r["result"]["longitude"])
            for r in resp.json()["result"] if r.get("result")}


def distance_miles(lat, lon):
    """Great-circle (haversine) distance from the Cheltenham centre point."""
    p1, p2 = math.radians(LAT), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - LNG)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def main():
    practices = list_practices()
    coords = geocode({p["PostCode"] for p in practices.values() if p.get("PostCode")})
    items = []
    for code, practice in practices.items():
        postcode = practice.get("PostCode")
        lat, lon = coords.get(postcode, (None, None))
        items.append({
            "code": code,
            "name": helper.clean_name(practice["Name"], ACRONYMS),
            "address": address(code),
            "postcode": postcode,
            "distance_miles": round(distance_miles(lat, lon), 1) if lat is not None else None,
            "lat": round(lat, 6) if lat is not None else None,
            "lon": round(lon, 6) if lon is not None else None,
        })
    items.sort(key=lambda p: (p["distance_miles"] is None, p["distance_miles"] or 0, p["name"]))

    year = datetime.now(timezone.utc).year
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "NHS Organisation Data Service",
        "source_url": "https://digital.nhs.uk/services/organisation-data-service",
        "licence": "Open Government Licence v3.0",
        "geocoding_source": "postcodes.io (ONS Postcode Directory)",
        "geocoding_attribution": (
            f"Contains OS data © Crown copyright and database right {year}. "
            f"Contains Royal Mail data © Royal Mail copyright and database right {year}. "
            "Source: Office for National Statistics licensed under the Open Government Licence v3.0."),
        "districts": DISTRICTS,
        "practices": items,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} dental practices to {OUT}")


if __name__ == "__main__":
    main()
