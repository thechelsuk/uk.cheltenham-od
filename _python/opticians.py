#!/usr/bin/env python3
"""Fetch the opticians in Cheltenham and write _data/opticians.json.

Opticians come from the NHS Organisation Data Service (ODS) ORD API, which is
open and needs no key: every active organisation with the Optical Site role
(RO167) in a Cheltenham postcode district. That is the NHS's own directory of
optical sites, so opticians that only offer private eye care are mostly not in
it. ODS has no coordinates or phone numbers, so each site's postcode is
geocoded in one bulk call to postcodes.io.

Opticians change slowly, so a monthly refresh is plenty.
"""
import os
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "opticians.json")

ROLE_ID = "RO167"                  # Optical Site
LIST_LIMIT = 1000
ACRONYMS = helper.DEFAULT_ACRONYMS | {"NHS"}


def list_sites():
    """Every active optical site in the postcode districts, keyed by ODS code.

    ODS rejects Offset=0 with a 406, so each district is asked for in one call
    rather than paged; a warning flags it if a district ever hits the limit."""
    sites = {}
    for district in config.POSTCODE_DISTRICTS:
        rows = helper.ods_get("organisations", PostCode=district, PrimaryRoleId=ROLE_ID,
                              Status="Active", Limit=LIST_LIMIT).get("Organisations", [])
        if len(rows) >= LIST_LIMIT:
            print(f"Warning: ODS returned {LIST_LIMIT} sites for {district}, the limit; some may be missing")
        sites.update({row["OrgId"]: row for row in rows})
    return sites


def display_name(name, address_text):
    """ODS names one supermarket optician just 'CHELTENHAM'; lead with the first address line instead."""
    if name.strip().lower() == "cheltenham":
        return f"{address_text.split(',')[0]}, {helper.clean_name(name, ACRONYMS)}"
    return helper.clean_name(name, ACRONYMS)


def main():
    sites = list_sites()
    coords = helper.geocode_postcodes({s["PostCode"] for s in sites.values() if s.get("PostCode")})
    items = []
    for code, site in sites.items():
        postcode = site.get("PostCode")
        lat, lon = coords.get(postcode, (None, None))
        full_address = helper.ods_address(code, ACRONYMS)
        items.append({
            "code": code,
            "name": display_name(site["Name"], full_address),
            "address": full_address,
            "postcode": postcode,
            "distance_miles": round(helper.miles_from_centre(lat, lon), 1) if lat is not None else None,
            "lat": round(lat, 6) if lat is not None else None,
            "lon": round(lon, 6) if lon is not None else None,
        })
    items.sort(key=lambda s: (s["distance_miles"] is None, s["distance_miles"] or 0, s["name"]))

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
        "opticians": items,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(items)} opticians to {OUT}")


if __name__ == "__main__":
    main()
