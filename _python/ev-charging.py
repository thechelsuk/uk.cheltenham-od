#!/usr/bin/env python3
"""
Fetch public EV charging locations around Cheltenham from Open Charge Map
and write them to _data/ev-charging.json (sibling of the _python folder).

Run locally:      OCM_API_KEY=your_key python _python/ev-charging.py
GitHub Actions:   schedule-daily.yml passes the OCM_API_KEY repo secret to this step.

Data © Open Charge Map contributors, licensed CC-BY-SA 4.0.
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
LICENCE = "CC-BY-SA 4.0 — Data © Open Charge Map contributors"

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
    stations.sort(key=lambda s: s["distance_miles"])

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "centre": {"latitude": CENTRE_LAT, "longitude": CENTRE_LNG},
        "radius_km": RADIUS_KM,
        "count": len(stations),
        "summary": build_summary(stations),
        "stations": stations,
    }

    helper.write_json(OUTPUT_FILE, payload)

    print(f"Wrote {len(stations)} charging locations to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
