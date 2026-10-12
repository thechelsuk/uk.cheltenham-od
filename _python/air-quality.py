#!/usr/bin/env python3
"""
Pulls live air-quality readings from DEFRA's UK-AIR Sensor Observation Service
(52°North Timeseries REST API) for stations around Cheltenham, and writes them
to _data/air-quality.json for _layouts/safety-environment/air-quality.html.

API docs: https://uk-air.defra.gov.uk/sos-ukair/static/doc/api-doc/
Base URL: https://uk-air.defra.gov.uk/sos-ukair/api/v1

The DEFRA JSON API is not consistently documented and field names/behaviour
have been known to drift; run with --debug to see raw responses.

Usage:
    python3 _python/air-quality.py [--debug]
"""
import re
import sys
import argparse
import datetime
import pathlib

import requests

import config
import helper

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://uk-air.defra.gov.uk/sos-ukair/api/v1"
HEADERS = {**config.HEADERS, "Accept": "application/json"}

# Cheltenham town centre, used as the search origin
CENTRE_LAT, CENTRE_LON = config.CENTRE

# Covers Cheltenham + immediate surrounding area (Cheltenham, Bishop's
# Cleeve, Charlton Kings, etc). Increase if you want Gloucester included.
RADIUS_KM = config.AIR_QUALITY_RADIUS_KM

# Radius used for client-side distance filtering after fetching the full
# station list (the DEFRA SOS instance's server-side bbox/near params
# returned 400/500 errors in testing).

OUTPUT_FILE = pathlib.Path(__file__).resolve().parent.parent / "_data" / "air-quality.json"

SOURCE_NAME = "DEFRA UK-AIR"
SOURCE_URL = "https://uk-air.defra.gov.uk/"
LICENCE = "Open Government Licence v3.0"
DEBUG = False


def debug_print(*args):
    if DEBUG:
        print("[debug]", *args, file=sys.stderr)


# Pollutants we care about for a public-facing summary. UK-AIR labels vary
# by station/procedure so this is a best-effort keyword match against the
# phenomenon label returned by the API.
POLLUTANTS_OF_INTEREST = {
    "pm2.5": "PM2.5 (fine particulates)",
    "pm10": "PM10 (particulates)",
    "no2": "Nitrogen dioxide (NO2)",
    "o3": "Ozone (O3)",
    "so2": "Sulphur dioxide (SO2)",
}

# Rough UK Daily Air Quality Index (DAQI) band 1 thresholds, used only to
# flag "Low / Moderate / High / Very High" per reading. These are
# simplified single-hour bands, not the official rolling-mean DAQI
# calculation — treat as indicative only. Values are in µg/m3.
# Source basis: DEFRA DAQI banding tables (uk-air.defra.gov.uk/air-pollution/daqi)
DAQI_BANDS = {
    "pm2.5": [(11, "Low"), (23, "Moderate"), (35, "High"), (999, "Very High")],
    "pm10":  [(16, "Low"), (33, "Moderate"), (50, "High"), (999, "Very High")],
    "no2":   [(67, "Low"), (134, "Moderate"), (200, "High"), (999, "Very High")],
    "o3":    [(50, "Low"), (100, "Moderate"), (240, "High"), (999, "Very High")],
    "so2":   [(88, "Low"), (177, "Moderate"), (266, "High"), (999, "Very High")],
}

TIMEOUT = 20  # seconds per request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def match_pollutant_key(phenomenon_label: str, fallback_text: str = ""):
    """Return our internal pollutant key. The API returns the phenomenon
    label as a EIONET vocabulary URI (e.g.
    'http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001'), not plain
    text, confirmed via live debug output. Match on the known EIONET
    pollutant codes first, then fall back to matching descriptive text
    (used because each 'station' entry here is actually per-pollutant,
    with the pollutant name baked into the station label itself, e.g.
    'Cheltenham A40 Gloucester Road-Particulate matter less than 2.5
    micro m (aerosol)')."""
    # EIONET aq/pollutant vocabulary codes (documented at
    # http://dd.eionet.europa.eu/vocabulary/aq/pollutant/)
    EIONET_CODES = {
        "1": "so2",
        "5": "pm10",
        "7": "o3",
        "8": "no2",
        "6001": "pm2.5",
    }
    if phenomenon_label and "/pollutant/" in phenomenon_label:
        code = phenomenon_label.rstrip("/").rsplit("/", 1)[-1]
        if code in EIONET_CODES:
            return EIONET_CODES[code]

    label = (fallback_text or phenomenon_label).lower()
    checks = {
        "pm2.5": ["pm2.5", "pm2,5", "pm25", "2.5 micro"],
        "pm10": ["pm10", "10 micro"],
        "no2": ["no2", "nitrogen dioxide"],
        "o3": ["o3", "ozone"],
        "so2": ["so2", "sulphur dioxide", "sulfur dioxide"],
    }
    for key, needles in checks.items():
        for n in needles:
            if n in label:
                return key
    return None


def daqi_band(pollutant_key: str, value: float):
    bands = DAQI_BANDS.get(pollutant_key)
    if bands is None or value is None:
        return "n/a"
    for threshold, name in bands:
        if value <= threshold:
            return name
    return "Very High"


def site_name(station_label: str) -> str:
    """Strip the pollutant description this SOS instance appends to each
    station label, e.g. 'Cheltenham A40 Gloucester Road-Particulate matter
    less than 2.5 micro m (aerosol)' -> 'Cheltenham A40 Gloucester Road'."""
    for suffix in ["-Particulate", "-Nitrogen", "-Ozone", "-Sulphur", "-Sulfur"]:
        idx = station_label.find(suffix)
        if idx != -1:
            return station_label[:idx]
    return station_label


def get_all_stations():
    """Fetch the full station list (no spatial filter — the DEFRA SOS
    instance returns 400/500 on both 'bbox' and 'near' params in testing,
    likely a bug in their old 52North/Tomcat deployment). Paginates using
    offset/limit since the full UK list can be large. Filtering to
    Cheltenham happens client-side afterwards."""
    all_stations = []
    offset = 0
    limit = 200

    while True:
        params = {"expanded": "true", "offset": offset, "limit": limit}
        debug_print("GET", f"{BASE_URL}/stations", "params:", params)
        resp = requests.get(f"{BASE_URL}/stations", params=params, headers=HEADERS, timeout=TIMEOUT)
        debug_print("status:", resp.status_code, "body length:", len(resp.text))
        if resp.status_code != 200:
            debug_print("body snippet:", resp.text[:500])
        resp.raise_for_status()
        page = resp.json()

        if not isinstance(page, list):
            debug_print("Unexpected shape, full body:", resp.text[:2000])
            break

        debug_print(f"page at offset {offset}: {len(page)} stations")
        all_stations.extend(page)

        if len(page) < limit:
            break  # last page
        offset += limit

        if offset > 5000:  # sanity cap
            debug_print("hit pagination sanity cap, stopping")
            break

    debug_print(f"{len(all_stations)} total stations fetched (unfiltered, whole service)")
    return all_stations


def filter_stations_by_distance(all_stations):
    filtered = []
    min_dist = None
    min_dist_label = None
    cheltenham_name_matches = []

    for station in all_stations:
        props = station.get("properties", {})
        label = props.get("label", "")

        if "cheltenham" in label.lower():
            cheltenham_name_matches.append((label, station.get("geometry", {}).get("coordinates")))

        coords = station.get("geometry", {}).get("coordinates")
        if not coords or len(coords) < 2:
            continue
        # NOTE: this API returns coordinates as [lat, lon, elevation] —
        # NOT the GeoJSON-standard [lon, lat]. Confirmed via live debug
        # output (e.g. "Cheltenham A40..." -> [51.896592, -2.113747, NaN]).
        lat, lon = float(coords[0]), float(coords[1])
        dist = helper.haversine_km(CENTRE_LAT, CENTRE_LON, lat, lon)

        if min_dist is None or dist < min_dist:
            min_dist = dist
            min_dist_label = f"{label} @ {coords}"

        if dist <= RADIUS_KM:
            station["_distance_km"] = round(dist, 1)
            filtered.append(station)

    debug_print(f"{len(filtered)} stations within {RADIUS_KM}km of Cheltenham centre")
    debug_print(f"closest station overall: {min_dist_label} -> {min_dist:.1f}km" if min_dist is not None else "no station had usable coordinates")
    if cheltenham_name_matches:
        debug_print(f"stations with 'cheltenham' in label: {cheltenham_name_matches}")
    else:
        debug_print("no station label contains the word 'cheltenham'")

    return filtered


def get_timeseries_last_value(ts_id: str):
    """Fetch metadata + lastValue for a single timeseries id."""
    debug_print("GET", f"{BASE_URL}/timeseries/{ts_id}")
    resp = requests.get(f"{BASE_URL}/timeseries/{ts_id}", headers=HEADERS, timeout=TIMEOUT)
    debug_print("status:", resp.status_code)
    resp.raise_for_status()
    return resp.json()


def collect_readings():
    """Walk stations -> timeseries -> last value, filtered to pollutants
    of interest. Returns a list of dicts ready for rendering."""
    readings = []

    try:
        all_stations = get_all_stations()
    except requests.RequestException as exc:
        print(f"ERROR: could not fetch stations list: {exc}", file=sys.stderr)
        return readings

    stations = filter_stations_by_distance(all_stations)

    if not stations:
        print("WARNING: no stations found within radius around Cheltenham "
              "(run with --debug to see raw API responses)", file=sys.stderr)
        return readings

    for station in stations:
        props = station.get("properties", {})
        station_label = props.get("label", "Unknown station")
        station_distance = station.get("_distance_km")
        timeseries_map = props.get("timeseries", {})

        debug_print(f"station '{station_label}' has {len(timeseries_map)} timeseries entries")

        # This SOS instance names each station-pollutant combination as one
        # "station" entry, with the pollutant description appended to the
        # site name (e.g. "Cheltenham A40 Gloucester Road-Particulate
        # matter less than 2.5 micro m (aerosol)"). Strip that suffix so
        # readings for the same physical site group together in the output.
        name = site_name(station_label)

        for ts_id, ts_meta in timeseries_map.items():
            phenomenon_label = ts_meta.get("phenomenon", {}).get("label", "")
            pollutant_key = match_pollutant_key(phenomenon_label, fallback_text=station_label)
            debug_print(f"  ts_id={ts_id} phenomenon='{phenomenon_label}' -> matched={pollutant_key}")
            if pollutant_key is None:
                continue  # not one of the pollutants we're displaying

            try:
                ts_detail = get_timeseries_last_value(ts_id)
            except requests.RequestException as exc:
                print(f"WARNING: failed to fetch {ts_id} ({station_label}): {exc}",
                      file=sys.stderr)
                continue

            debug_print(f"  ts_detail keys: {list(ts_detail.keys())}")
            last_value = ts_detail.get("lastValue")
            debug_print(f"  lastValue: {last_value}")
            if not last_value:
                continue

            value = last_value.get("value")
            timestamp_ms = last_value.get("timestamp")
            uom = ts_detail.get("uom", "")

            when = None
            if timestamp_ms:
                when = datetime.datetime.fromtimestamp(
                    timestamp_ms / 1000, tz=datetime.timezone.utc
                )

            readings.append({
                "station": name,
                "distance_km": station_distance,
                "pollutant_key": pollutant_key,
                "pollutant_label": POLLUTANTS_OF_INTEREST[pollutant_key],
                "value": value,
                "uom": uom,
                "timestamp": when,
                "band": daqi_band(pollutant_key, value),
            })

    return readings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
BAND_ORDER = ["Low", "Moderate", "High", "Very High"]


def smart_title(text: str) -> str:
    """Title-case a name, handling messy source data sensibly.

    - Words containing a digit (postcodes, unit codes like 'GL51') are
      left completely untouched.
    - If the whole name is SHOUTING, every other word gets re-cased.
    - A short (<=3 letter) standalone all-caps word (e.g. 'HQ') is treated
      as a deliberate acronym and left alone, UNLESS the whole name is
      shouting (in which case there's no way to distinguish it from an
      accidental caps-lock name, so it's re-cased along with everything
      else).
    """
    is_shouting = text.isupper()
    out = []
    for word in text.split():
        if re.search(r"\d", word):
            out.append(word)
        elif is_shouting:
            out.append(word.capitalize())
        elif word.isupper() and len(word) <= 3:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:] if word else word)
    return " ".join(out)


def shape_reading(r):
    """One reading as stored in the JSON: the raw value for sorting, a
    display string with thousands separators, and the time as ISO (UTC)."""
    value = r["value"]
    return {
        "pollutant_key": r["pollutant_key"],
        "pollutant": r["pollutant_label"],
        "value": value,
        "uom": r["uom"],
        "reading_display": f"{value:,} {r['uom']}".strip() if value is not None else "n/a",
        "band": r["band"],
        "measured": r["timestamp"].strftime("%Y-%m-%dT%H:%M") if r["timestamp"] else None,
    }


def build_stations(readings):
    """Group readings by monitoring site, sorted by site name, each site's
    readings sorted by pollutant."""
    grouped = {}
    for r in readings:
        grouped.setdefault(r["station"], []).append(r)

    stations = []
    for name, station_readings in sorted(grouped.items()):
        stations.append({
            "name": smart_title(name),
            "distance_km": station_readings[0].get("distance_km"),
            "readings": [shape_reading(r) for r in sorted(station_readings, key=lambda x: x["pollutant_label"])],
        })
    return stations


def highest_band(readings):
    """The worst DAQI band across all readings, or None if none has a band."""
    ranks = [BAND_ORDER.index(r["band"]) for r in readings if r.get("band") in BAND_ORDER]
    return BAND_ORDER[max(ranks)] if ranks else None


def build_payload(readings, generated_at):
    stations = build_stations(readings)
    distances = [s["distance_km"] for s in stations if s["distance_km"] is not None]
    return {
        "generated_at": generated_at,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "radius_km": RADIUS_KM,
        "reading_count": len(readings),
        "highest_band": highest_band(readings),
        "nearest_km": min(distances) if distances else None,
        "stations": stations,
    }


def main():
    global DEBUG
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                         help="Print raw API request/response info to stderr")
    args = parser.parse_args()
    DEBUG = args.debug

    readings = collect_readings()
    generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    helper.write_json(OUTPUT_FILE, build_payload(readings, generated_at))

    print(f"Wrote {len(readings)} readings to {OUTPUT_FILE}")
    if not readings:
        print("No readings found — re-run with --debug for diagnostics, "
              "e.g.: python3 _python/air-quality.py --debug", file=sys.stderr)


if __name__ == "__main__":
    main()