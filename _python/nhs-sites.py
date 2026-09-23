#!/usr/bin/env python3
"""Fetch the hospitals run by Gloucestershire Hospitals NHS Foundation Trust
that are within 10 miles of Cheltenham, and write _data/nhs-hospitals.json.

Sites come from the NHS Organisation Data Service (ODS) ORD API, which is open
and needs no key: every active site with a "is located in the geography of"
(RE6) relationship to the trust's ODS code. ODS has no coordinates, so each
site's postcode is geocoded in one bulk call to postcodes.io.

Only real hospital sites are kept: the trust's own site codes (RTE + 2
characters) whose name has the word "HOSPITAL" (not the trust's own "HOSPITALS"
name, which would match its head office). That drops the trust's clinics,
nurseries and community halls, and the per-department sub-sites ODS records at
the same address ("A&E CGH"). Those A&E sub-sites are used, though, to flag
which hospitals have an A&E listed.

Hospitals rarely change, so a monthly refresh is plenty.
"""
import os
import re
from datetime import datetime, timezone

import config
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "nhs-hospitals.json")

TRUST_CODE = "RTE"
TRUST_NAME = "Gloucestershire Hospitals NHS Foundation Trust"
LIST_LIMIT = 1000
ACRONYMS = helper.DEFAULT_ACRONYMS | {"NHS", "CGH", "GRH"}


def list_sites():
    """Every active site of the trust (about 200) in one call.

    ODS rejects Offset=0 with a 406, so this asks for the whole list at once
    rather than paging; a warning flags it if the list ever hits the limit."""
    rows = helper.ods_get("organisations", TargetOrgId=TRUST_CODE, RelTypeId="RE6",
                          RelStatus="Active", Limit=LIST_LIMIT).get("Organisations", [])
    if len(rows) >= LIST_LIMIT:
        print(f"Warning: ODS returned {LIST_LIMIT} sites, the limit; some may be missing")
    return {r["OrgId"]: r for r in rows}


def join_names(names):
    """['A', 'B', 'C'] -> 'A, B and C'. Layouts print this display string
    rather than joining names in Liquid."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def main():
    sites = list_sites()
    hospitals = {c: s for c, s in sites.items()
                 if re.fullmatch(rf"{TRUST_CODE}\w{{2}}", c) and re.search(r"\bHOSPITAL\b", s["Name"].upper())}
    ae_postcodes = {s.get("PostCode") for s in sites.values() if s["Name"].upper().startswith("A&E ")}

    coords = helper.geocode_postcodes({s["PostCode"] for s in hospitals.values() if s.get("PostCode")})
    items = []
    for code, site in hospitals.items():
        if site.get("PostCode") not in coords:
            continue
        lat, lon = coords[site["PostCode"]]
        distance = helper.miles_from_centre(lat, lon)
        if distance > config.HOSPITALS_RADIUS_MILES:
            continue
        items.append({
            "code": code,
            "name": helper.clean_name(site["Name"], ACRONYMS),
            "address": helper.ods_address(code, ACRONYMS),
            "postcode": site["PostCode"],
            "has_ae": site["PostCode"] in ae_postcodes,
            "distance_miles": round(distance, 1),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
        })
    items.sort(key=lambda h: (h["distance_miles"], h["name"]))

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
        "trust": {"name": TRUST_NAME, "code": TRUST_CODE},
        "radius_miles": config.HOSPITALS_RADIUS_MILES,
        "ae_hospitals_display": join_names([h["name"] for h in items if h["has_ae"]]),
        "hospitals": items,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(items)} hospitals (of {len(hospitals)} trust hospital sites, {len(sites)} sites in all) to {OUT}")


if __name__ == "__main__":
    main()
