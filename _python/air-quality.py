#!/usr/bin/env python3
"""
fetch_air_quality.py

Pulls live air-quality readings from DEFRA's UK-AIR Sensor Observation Service
(52°North Timeseries REST API) for stations around Cheltenham, and writes a
Jekyll-ready markdown page (air-quality.md).

API docs: https://uk-air.defra.gov.uk/sos-ukair/static/doc/api-doc/
Base URL: https://uk-air.defra.gov.uk/sos-ukair/api/v1

NOTE: This script could not be executed against the live API from the
sandbox this was written in (uk-air.defra.gov.uk is not on the allowed
network list here), so it has NOT been run end-to-end. Please run it
yourself and report back any errors / unexpected JSON shapes so it can
be corrected — the DEFRA JSON API is not consistently documented and
field names/behaviour have been known to drift.

Usage:
    python3 fetch_air_quality.py

Requires:
    pip install requests
"""
import re
import sys
import math
import argparse
import datetime
import requests
import helper

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://uk-air.defra.gov.uk/sos-ukair/api/v1"
HEADERS = {"Accept": "application/json"}

# Cheltenham town centre, used as the search origin
CENTRE_LAT = 51.8994
CENTRE_LON = -2.0783

# Covers Cheltenham + immediate surrounding area (Cheltenham, Bishop's
# Cleeve, Charlton Kings, etc). Increase if you want Gloucester included.
RADIUS_KM = 20

# Radius used for client-side distance filtering after fetching the full
# station list (the DEFRA SOS instance's server-side bbox/near params
# returned 400/500 errors in testing).

OUTPUT_FILE = "_pages/air-quality.md"
DEBUG = False


def debug_print(*args):
    if DEBUG:
        print("[debug]", *args, file=sys.stderr)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))

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


def get_all_stations():
    """Fetch the full station list (no spatial filter — the DEFRA SOS
    instance returns 400/500 on both 'bbox' and 'near' params in testing,
    likely a bug in their old 52North/Tomcat deployment). Paginates using
    offset/limit since the full UK list can be large. Filtering to
    Cheltenham happens client-side afterwards."""
    import json as _json

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
        dist = haversine_km(CENTRE_LAT, CENTRE_LON, lat, lon)

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
        site_name = station_label
        for marker in ["-Particulate", "-Nitrogen", "-Ozone", "-Sulphur", "-Sulfur"]:
            idx = site_name.find(marker)
            if idx != -1:
                site_name = site_name[:idx]
                break

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
                "station": site_name,
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
# Rendering
# ---------------------------------------------------------------------------
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


def render_markdown(readings):
    generated = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    lines = []
    lines.append(
        "Air quality in Cheltenham changes hour to hour depending on traffic, "
        "weather and wider weather patterns. The readings below come directly "
        "from [DEFRA's UK-AIR monitoring network](https://uk-air.defra.gov.uk/), "
        "the UK government's official air pollution data source, and are pulled "
        f"from the nearest monitoring stations to Cheltenham.\n"
    )
    lines.append(
        "\nThe main pollutants tracked here are fine particulates (PM2.5 and "
        "PM10, from vehicle exhaust, brake dust and burning), nitrogen dioxide "
        "(NO2, mostly from traffic), ozone (O3, which builds up in sunny "
        "weather) and sulphur dioxide (SO2, from industrial and fuel burning "
        "sources). Each reading is given a rough band — Low, Moderate, High or "
        "Very High — based on DEFRA's Daily Air Quality Index thresholds, "
        "so you can see at a glance whether levels are a concern. This is a "
        "simplified, single-reading guide rather than the official rolling-"
        "average DAQI figure, so treat it as indicative rather than exact.\n"
    )
    lines.append(
        "\nIf you have asthma, another lung condition, or a heart condition, "
        "the NHS and DEFRA recommend reducing strenuous activity outdoors "
        "when readings are in the High or Very High bands. See "
        "[DEFRA's air quality advice](https://uk-air.defra.gov.uk/air-pollution/daqi) "
        "for more detail on what each band means for your health.\n"
    )

    if not readings:
        lines.append(
            "\n> No data was available from DEFRA at the time this page was "
            "last generated. This will update automatically on the next "
            "scheduled run.\n"
        )
        return "".join(lines)

    # Group by station
    stations = {}
    for r in readings:
        stations.setdefault(r["station"], []).append(r)

    for station_name, station_readings in sorted(stations.items()):
        distance = station_readings[0].get("distance_km")
        distance_str = f" ({distance}km from Cheltenham centre)" if distance is not None else ""
        lines.append(f"\n## {smart_title(station_name)}{distance_str}\n")
        lines.append("\n| Pollutant | Reading | Band | Measured (UTC) |\n")
        lines.append("|---|---|---|---|\n")
        for r in sorted(station_readings, key=lambda x: x["pollutant_label"]):
            value_str = f"{r['value']} {r['uom']}".strip() if r["value"] is not None else "n/a"
            when_str = r["timestamp"].strftime("%Y-%m-%d %H:%M") if r["timestamp"] else "n/a"
            lines.append(
                f"| {r['pollutant_label']} | {value_str} | {r['band']} | {when_str} |\n"
            )

    lines.append(
        f"\n*Source: [DEFRA UK-AIR](https://uk-air.defra.gov.uk/). "
        f"Data last refreshed {generated}.*\n"
    )

    return "".join(lines)


def update_target_file(body_markdown: str):
    """Replace the air-quality section in OUTPUT_FILE using the project's
    existing helper.replace_chunk(). That function matches markers of the
    form:"""

    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        print(f"ERROR: {OUTPUT_FILE} does not exist. Create it first with "
              f"front matter and the air_quality starts/ends markers in "
              f"place, then re-run this script.", file=sys.stderr)
        sys.exit(1)

    new_content = helper.replace_chunk(existing, "air_quality", body_markdown)

    if new_content == existing:
        print("WARNING: file content unchanged — the 'air_quality starts'/"
              "'air_quality ends' markers may not be present in "
              f"{OUTPUT_FILE}. Check spelling exactly matches.", file=sys.stderr)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    global DEBUG
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true",
                         help="Print raw API request/response info to stderr")
    args = parser.parse_args()
    DEBUG = args.debug

    readings = collect_readings()
    markdown = render_markdown(readings)
    update_target_file(markdown)

    print(f"Updated {OUTPUT_FILE} with {len(readings)} readings")
    if not readings:
        print("No readings found — re-run with --debug for diagnostics, "
              "e.g.: python3 fetch_air_quality.py --debug", file=sys.stderr)


if __name__ == "__main__":
    main()