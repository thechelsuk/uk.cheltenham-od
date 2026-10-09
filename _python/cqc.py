#!/usr/bin/env python3
"""Care homes, home care services and GP practices in Cheltenham with their
Care Quality Commission (CQC) ratings, written to _data/cqc.json.

The records come from cqc_source.load_locations(), which hides where they
are fetched from (the CQC API). This
script keeps the Cheltenham postcode districts, groups the locations, adds
coordinates from postcodes.io and writes the data file. The GP and
pharmacy finder (pharmacy.py) reads GP ratings from it by ODS code.

The CQC's ratings change as inspections are published, so it runs weekly.
"""
import os
import re
from collections import Counter
from datetime import datetime, timezone

import config
import cqc_source
import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "cqc.json")

RATINGS = ("Outstanding", "Good", "Requires improvement", "Inadequate")


def kind(location):
    """Which list a location belongs on, or None."""
    types = location["service_types"]
    if location["care_home"]:
        return "nursing_home" if "Nursing homes" in types else "residential_home"
    if "Homecare agencies" in types:
        return "home_care"
    if location["category"] == "GP Practices" or "Doctors/GPs" in types:
        return "gp"
    return None


def merge_reregistrations(locations):
    """A home that changes provider is registered again under a new location
    ID, and both can stay listed for a while, the new one unrated. Keep one
    record per name and postcode: the newest registration, carrying the
    previous one's rating until it has its own."""
    groups = {}
    for loc in locations:
        groups.setdefault((slugify(loc["name"]), loc["postcode"]), []).append(loc)
    merged = []
    for group in groups.values():
        group.sort(key=lambda loc: int(loc["id"].split("-")[-1]), reverse=True)
        current = group[0]
        current["previous_registration"] = False
        if not current["overall"]:
            rated = next((loc for loc in group[1:] if loc["overall"]), None)
            if rated:
                for key in ("overall", "published", "ratings", "overall_rank"):
                    current[key] = rated[key]
                current["previous_registration"] = True
                current["previous_url"] = rated["url"]
        current["website"] = current["website"] or next((loc["website"] for loc in group if loc["website"]), None)
        merged.append(current)
    return merged


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", name.lower())).strip("-")


def add_slugs(locations):
    """A page address for each care home and home care service; two with the
    same name get their postcode district added."""
    listed = [loc for loc in locations if loc["kind"] != "gp"]
    counts = Counter(slugify(loc["name"]) for loc in listed)
    for loc in locations:
        loc["slug"] = None
        if loc["kind"] == "gp":
            continue
        slug = slugify(loc["name"])
        if counts[slug] > 1:
            slug = f"{slug}-{loc['postcode'].split(' ')[0].lower()}"
        loc["slug"] = slug


def main():
    locations = [loc for loc in cqc_source.load_locations(set(config.POSTCODE_DISTRICTS)) if kind(loc)]
    coords = helper.geocode_postcodes({loc["postcode"] for loc in locations if loc["postcode"]})
    for loc in locations:
        loc["kind"] = kind(loc)
        lat, lon = coords.get(loc["postcode"], (None, None))
        loc["lat"] = round(lat, 6) if lat is not None else None
        loc["lon"] = round(lon, 6) if lon is not None else None
        loc["distance_miles"] = round(helper.miles_from_centre(lat, lon), 1) if lat is not None else None
        loc["overall_rank"] = RATINGS.index(loc["overall"]) + 1 if loc["overall"] in RATINGS else 9
    locations = merge_reregistrations(locations)
    locations.sort(key=lambda loc: loc["name"].lower())
    add_slugs(locations)
    slugs = [loc["slug"] for loc in locations if loc["slug"]]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("Two CQC locations share a page address")

    care_homes = [loc for loc in locations if loc["kind"] in ("nursing_home", "residential_home")]
    summary = {
        "care_homes": len(care_homes),
        "nursing_homes": sum(1 for loc in care_homes if loc["kind"] == "nursing_home"),
        "home_care": sum(1 for loc in locations if loc["kind"] == "home_care"),
        "care_homes_good_or_better": sum(1 for loc in care_homes if loc["overall"] in ("Outstanding", "Good")),
        "care_homes_rated": sum(1 for loc in care_homes if loc["overall"]),
    }

    year = datetime.now(timezone.utc).year
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Care Quality Commission",
        "source_url": cqc_source.DATA_PAGE,
        "source_method": cqc_source.SOURCE_NAME,
        "licence": "Open Government Licence v3.0",
        "geocoding_source": "postcodes.io (ONS Postcode Directory)",
        "geocoding_attribution": (
            f"Contains OS data © Crown copyright and database right {year}. "
            f"Contains Royal Mail data © Royal Mail copyright and database right {year}. "
            "Source: Office for National Statistics licensed under the Open Government Licence v3.0."),
        "summary": summary,
        "locations": locations,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(locations)} CQC locations ({summary['care_homes']} care homes) to {OUT}")


if __name__ == "__main__":
    main()
