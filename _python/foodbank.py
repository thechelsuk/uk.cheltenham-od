#!/usr/bin/env python3
"""Fetch food banks within 10 miles of Cheltenham from the Give Food API and
write them, with their needs, locations and donation points, to
_data/foodbank.json.

Give Food's rules (https://www.givefood.org.uk/api/) ask that lists of needed
items are shown as published, in their original order, so needs and excess
items are stored verbatim. The API data is CC BY 4.0, so the licence and a
credit link are stored alongside it for the layouts to render.

Refreshed on every scheduled run because the source changes several times a day."""
import re
import time
from datetime import datetime, timezone

import config
import helper

API = "https://www.givefood.org.uk/api/2"
CENTRE = ",".join(str(c) for c in config.CENTRE)
RADIUS_MILES = config.FOODBANK_RADIUS_MILES
PAUSE_SECONDS = 1


def get(path, **params):
    return helper.get(f"{API}/{path}", params=params).json()


def lines(text):
    """Split a newline-separated API string into a list, without changing the items or their order."""
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def one_line(address):
    return ", ".join(lines(address))


def lat_lon(value):
    try:
        lat, lon = (float(part) for part in (value or "").split(","))
        return lat, lon
    except ValueError:
        return None, None


def clean_hours(text):
    """Opening-hours lines with the API's narrow/thin unicode spaces turned into plain spaces."""
    return [re.sub(r"[\u202f\u2009\u00a0]", " ", line) for line in lines(text)]


def normalise_place(place):
    lat, lon = lat_lon(place.get("lat_lng"))
    return {
        "name": place.get("name") or "",
        "address": one_line(place.get("address")),
        "postcode": place.get("postcode") or "",
        "phone": place.get("phone") or "",
        "url": place.get("url") or "",
        "opening_hours": clean_hours(place.get("opening_hours")),
        "wheelchair_accessible": place.get("wheelchair_accessible"),
        "lat": lat,
        "lon": lon,
    }


def display_name(name, network):
    """Trussell food banks are listed as just their area ('Gloucester'); add 'Foodbank' so the name reads properly."""
    if network == "Trussell" and "food" not in name.lower():
        return f"{name} Foodbank"
    return name


def normalise_foodbank(detail, distance_mi):
    lat, lon = lat_lon(detail.get("lat_lng"))
    items = lines((detail.get("need") or {}).get("needs"))
    need = detail.get("need") or {}
    charity = detail.get("charity") or {}
    urls = detail.get("urls") or {}
    return {
        "slug": detail["slug"],
        "name": detail["name"],
        "display_name": display_name(detail["name"], detail.get("network") or ""),
        "network": detail.get("network") or "",
        "distance_mi": distance_mi,
        "phone": detail.get("phone") or "",
        "secondary_phone": detail.get("secondary_phone") or "",
        "email": detail.get("email") or "",
        "address": one_line(detail.get("address")),
        "postcode": detail.get("postcode") or "",
        "lat": lat,
        "lon": lon,
        "homepage": urls.get("homepage") or "",
        "shopping_list": urls.get("shopping_list") or "",
        "givefood_url": urls.get("html") or "",
        "charity_number": charity.get("registration_id") or "",
        "charity_url": charity.get("register_url") or "",
        "need": {
            "found_iso": need.get("created") or "",
            "has_list": bool(items) and items != ["Unknown"],
            "items": items,
            "excess": lines(need.get("excess")),
        },
        "locations": [normalise_place(p) for p in detail.get("locations") or []],
        "donation_points": [normalise_place(p) for p in detail.get("donationpoints") or []],
    }


def summarise(foodbanks):
    listed = [fb for fb in foodbanks if fb["need"]["found_iso"] and fb["need"]["has_list"]]
    latest = max(listed, key=lambda fb: fb["need"]["found_iso"], default=None)
    return {
        "foodbank_count": len(foodbanks),
        "donation_point_count": sum(len(fb["donation_points"]) for fb in foodbanks),
        "latest_change": {
            "name": latest["display_name"],
            "slug": latest["slug"],
            "found_iso": latest["need"]["found_iso"],
        } if latest else None,
    }


def missing_pages(root, foodbanks):
    """Warn about any food bank that has no page of its own yet (pages are
    hand-written: _pages/community-support/foodbanks/<name>.md with `foodbank: <slug>`)."""
    pages_dir = root / "_pages/community-support/foodbanks"
    have = set()
    for path in pages_dir.glob("*.md"):
        match = re.search(r"^foodbank:\s*(\S+)", path.read_text(), re.M)
        if match:
            have.add(match.group(1).strip("\"'"))
    for fb in foodbanks:
        if fb["slug"] not in have:
            print(f"::notice::No page yet for food bank '{fb['name']}' ({fb['slug']}), {fb['distance_mi']} miles away")


if __name__ == "__main__":
    root = helper.repo_root()
    results = get("foodbanks/search/", lat_lng=CENTRE)

    foodbanks = []
    for result in results:
        if result["distance_mi"] > RADIUS_MILES:
            continue
        time.sleep(PAUSE_SECONDS)
        detail = get(f"foodbank/{result['slug']}/")
        if detail.get("closed"):
            print(f"Skipping closed food bank {detail['name']}")
            continue
        foodbanks.append(normalise_foodbank(detail, result["distance_mi"]))
    foodbanks.sort(key=lambda fb: fb["distance_mi"])

    now = datetime.now(timezone.utc)
    helper.write_json(root / "_data/foodbank.json", {
        "generated_at": now.isoformat(),
        "source": "Give Food",
        "source_url": "https://www.givefood.org.uk/",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "radius_miles": RADIUS_MILES,
        "summary": summarise(foodbanks),
        "foodbanks": foodbanks,
    })
    missing_pages(root, foodbanks)
    print(f"Wrote {len(foodbanks)} food banks within {RADIUS_MILES} miles")
