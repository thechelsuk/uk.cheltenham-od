#!/usr/bin/env python3
"""
Fetch public EV charging locations around Cheltenham from Open Charge Map
and write them to _data/ev-charging.json (sibling of the _python folder).

Run locally:      OCM_API_KEY=your_key python _python/ev-charging.py
GitHub Actions:   refresh-4-times-daily.yml passes the OCM_API_KEY repo secret to this step.

Data © Open Charge Map contributors, licensed CC-BY-SA 4.0.

Open Charge Map can lag behind new sites, so hand-checked stations in
_data/ev-charging-additions.json are merged in too. Each one names its
sources and the date it was last checked, and is dropped automatically once
Open Charge Map lists the same operator within DEDUPE_METRES of it.
"""

import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

import config
import helper

# --- Configuration (edit these, no CLI args) --------------------------------

# Resolve _data as a sibling of the _python folder this script lives in,
# independent of the current working directory (local or GitHub Actions).
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent          # .../_python
DATA_DIR = SCRIPT_DIR.parent / "_data"                        # .../_data
OUTPUT_FILE = DATA_DIR / "ev-charging.json"
ADDITIONS_FILE = DATA_DIR / "ev-charging-additions.json"

# Cheltenham town centre — search radius is measured from here.
CENTRE_LAT, CENTRE_LNG = config.CENTRE
RADIUS_KM = config.EV_CHARGING_RADIUS_KM

COUNTRY_CODE = "GB"
MAX_RESULTS = 500

OCM_API_BASE = "https://api.openchargemap.io/v3/poi/"
OCM_API_KEY = os.environ.get("OCM_API_KEY", "")

REQUEST_TIMEOUT = 60  # seconds

SOURCE_NAME = "Open Charge Map"
SOURCE_URL = "https://openchargemap.org"
LICENCE = "Creative Commons Attribution-ShareAlike 4.0 licence (CC BY-SA 4.0)"

# An addition counts as already on Open Charge Map when OCM has a station run
# by the same operator this close to it.
DEDUPE_METRES = 150

# --- Helpers ----------------------------------------------------------------




def google_maps_url(lat, lng):
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def fetch_pois():
    """Call the Open Charge Map API and return the raw list of POIs."""
    params = {
        "output": "json",
        "countrycode": COUNTRY_CODE,
        "latitude": CENTRE_LAT,
        "longitude": CENTRE_LNG,
        "distance": RADIUS_KM,
        "distanceunit": "KM",
        "maxresults": MAX_RESULTS,
        "key": OCM_API_KEY,
    }
    url = OCM_API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": config.USER_AGENT,
        "X-API-Key": OCM_API_KEY,
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        if resp.status != 200:
            raise RuntimeError(f"OCM returned HTTP {resp.status}")
        return json.loads(resp.read().decode("utf-8"))


def summarise_connections(connections):
    """Turn OCM's Connections array into clean records."""
    out = []
    for c in connections or []:
        out.append({
            "type": (c.get("ConnectionType") or {}).get("Title"),
            "power_kw": c.get("PowerKW"),
            "quantity": c.get("Quantity"),
            "level": (c.get("Level") or {}).get("Title"),
        })
    return out


def transform(poi):
    """Map a raw OCM POI to the shape we want in ev-charging.json."""
    addr = poi.get("AddressInfo") or {}
    lat = addr.get("Latitude")
    lng = addr.get("Longitude")
    if lat is None or lng is None:
        return None

    connections = summarise_connections(poi.get("Connections"))
    powers = [c["power_kw"] for c in connections if c.get("power_kw")]

    return {
        "id": poi.get("ID"),
        "name": addr.get("Title"),
        "operator": (poi.get("OperatorInfo") or {}).get("Title"),
        "address": addr.get("AddressLine1"),
        "town": addr.get("Town"),
        "postcode": addr.get("Postcode"),
        "latitude": lat,
        "longitude": lng,
        "distance_miles": round(helper.miles_from_centre(lat, lng), 2),
        "access": (poi.get("UsageType") or {}).get("Title"),
        "status": (poi.get("StatusType") or {}).get("Title"),
        "num_points": poi.get("NumberOfPoints"),
        "connections": connections,
        "max_power_kw": max(powers) if powers else None,
        "last_verified": poi.get("DateLastVerified"),
        "google_maps_url": google_maps_url(lat, lng),
        "ocm_url": f"https://openchargemap.org/site/poi/details/{poi.get('ID')}",
    }


def load_additions(path=ADDITIONS_FILE):
    """The hand-checked stations from the additions file (none if it's missing)."""
    path = pathlib.Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("stations", [])


def addition_to_station(entry):
    """Turn a hand-checked addition into the same shape as transform() gives."""
    sources = [src for src in entry.get("sources") or [] if src.get("url")]
    if not sources:
        raise ValueError(f"{entry.get('id')}: an addition needs at least one source with a url")
    try:
        datetime.strptime(entry.get("last_checked") or "", "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{entry.get('id')}: last_checked must be an ISO date (YYYY-MM-DD)") from None
    lat, lng = entry.get("latitude"), entry.get("longitude")
    if lat is None or lng is None:
        raise ValueError(f"{entry.get('id')}: an addition needs latitude and longitude")

    connections = [
        {"type": c.get("type"), "power_kw": c.get("power_kw"),
         "quantity": c.get("quantity"), "level": c.get("level")}
        for c in entry.get("connections") or []
    ]
    powers = [c["power_kw"] for c in connections if c.get("power_kw")]

    return {
        "id": entry.get("id"),
        "name": entry.get("name"),
        "operator": entry.get("operator"),
        "address": entry.get("address"),
        "town": entry.get("town"),
        "postcode": entry.get("postcode"),
        "latitude": lat,
        "longitude": lng,
        "distance_miles": round(helper.miles_from_centre(lat, lng), 2),
        "access": entry.get("access"),
        "status": entry.get("status"),
        "num_points": entry.get("num_points"),
        "connections": connections,
        "max_power_kw": max(powers) if powers else None,
        "last_verified": entry["last_checked"],
        "google_maps_url": google_maps_url(lat, lng),
        "ocm_url": None,
        "hand_checked": True,
        "source_url": sources[0]["url"],
        "sources": sources,
    }


def _same_operator(a, b):
    return bool(a and b) and a.strip().casefold() == b.strip().casefold()


def merge_additions(stations, additions):
    """Add hand-checked stations that OCM doesn't list yet, sorted by distance."""
    merged = list(stations)
    for entry in additions:
        extra = addition_to_station(entry)
        if extra["distance_miles"] * 1.609344 > RADIUS_KM:
            continue
        on_ocm = any(
            _same_operator(s.get("operator"), extra["operator"])
            and helper.haversine_km(s["latitude"], s["longitude"], extra["latitude"], extra["longitude"]) * 1000
            <= DEDUPE_METRES
            for s in stations
        )
        if on_ocm:
            print(f"Open Charge Map now lists {extra['name']}: remove {extra['id']} from {ADDITIONS_FILE.name}")
            continue
        merged.append(extra)
    merged.sort(key=lambda s: s["distance_miles"])
    return merged


def build_summary(stations):
    """Aggregate connector types and headline stats for the page."""
    by_type = defaultdict(lambda: {"stations": 0, "connectors": 0, "max_power_kw": 0})
    total_connectors = 0
    powers = []
    operators = set()

    for s in stations:
        if s.get("operator"):
            operators.add(s["operator"])
        seen = set()
        for c in s.get("connections", []):
            t = c.get("type") or "Unknown"
            qty = c.get("quantity") or 1
            by_type[t]["connectors"] += qty
            total_connectors += qty
            if t not in seen:
                by_type[t]["stations"] += 1
                seen.add(t)
            if c.get("power_kw"):
                by_type[t]["max_power_kw"] = max(by_type[t]["max_power_kw"], c["power_kw"])
                powers.append(c["power_kw"])
        if s.get("max_power_kw"):
            powers.append(s["max_power_kw"])

    connector_types = [
        {"type": t, **v}
        for t, v in sorted(by_type.items(), key=lambda kv: -kv[1]["stations"])
    ]

    return {
        "total_locations": len(stations),
        "total_connectors": total_connectors,
        "operators": len(operators),
        "max_power_kw": max(powers) if powers else None,
        "connector_types": connector_types,
    }


def main():
    if not OCM_API_KEY:
        sys.exit("ERROR: set the OCM_API_KEY environment variable "
                 "(register a free key at https://openchargemap.org).")

    raw = fetch_pois()
    stations = [t for t in (transform(p) for p in raw) if t]
    stations = merge_additions(stations, load_additions())

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "centre": {"latitude": CENTRE_LAT, "longitude": CENTRE_LNG},
        "radius_km": RADIUS_KM,
        "count": len(stations),
        "hand_checked_count": sum(1 for s in stations if s.get("hand_checked")),
        "summary": build_summary(stations),
        "stations": stations,
    }

    helper.write_json(OUTPUT_FILE, payload)

    print(f"Wrote {len(stations)} charging locations to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
