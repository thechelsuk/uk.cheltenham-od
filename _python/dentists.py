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
import os
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "dentists.json")

ROLE_ID = "RO110"                  # General Dental Practice
LIST_LIMIT = 1000
ACRONYMS = helper.DEFAULT_ACRONYMS | {"NHS"}


def list_practices():
    """Every active dental practice in the postcode districts, keyed by ODS code.

    ODS rejects Offset=0 with a 406, so each district is asked for in one call
    rather than paged; a warning flags it if a district ever hits the limit."""
    practices = {}
    for district in config.POSTCODE_DISTRICTS:
        rows = helper.ods_get("organisations", PostCode=district, PrimaryRoleId=ROLE_ID,
                              Status="Active", Limit=LIST_LIMIT).get("Organisations", [])
        if len(rows) >= LIST_LIMIT:
            print(f"Warning: ODS returned {LIST_LIMIT} practices for {district}, the limit; some may be missing")
        practices.update({row["OrgId"]: row for row in rows})
    return practices


def main():
    practices = list_practices()
    coords = helper.geocode_postcodes({p["PostCode"] for p in practices.values() if p.get("PostCode")})
    items = []
    for code, practice in practices.items():
        postcode = practice.get("PostCode")
        lat, lon = coords.get(postcode, (None, None))
        items.append({
            "code": code,
            "name": helper.clean_name(practice["Name"], ACRONYMS),
            "address": helper.ods_address(code, ACRONYMS),
            "postcode": postcode,
            "distance_miles": round(helper.miles_from_centre(lat, lon), 1) if lat is not None else None,
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
        "districts": config.POSTCODE_DISTRICTS,
        "practices": items,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(items)} dental practices to {OUT}")


if __name__ == "__main__":
    main()
