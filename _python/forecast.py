#!/usr/bin/env python3
"""Fetch a 10-day daily forecast from OpenWeather One Call 4.0 (1-day timeline),
write normalized JSON to _data/weather.json."""
import json
import os
import sys
from datetime import datetime, time, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests

import config
import helper

# Load .env file for local development if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "weather.json")

# Constants — no CLI args.
LOCATION = "Cheltenham"
LAT, LON = config.CENTRE
DAYS     = 10
UNITS    = "metric"
BASE     = "https://api.openweathermap.org/data/4.0/onecall/timeline/1day"
API_KEY  = os.environ.get("OPEN_WEATHER_KEY", "")


def start_of_today_utc():
    midnight = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    return int(midnight.timestamp())


def force_units(url, units=UNITS):
    """The API's next/prev URLs omit `units`, so re-apply it on every follow-up call."""
    parts = urlparse(url)
    query = parse_qs(parts.query)
    query["units"] = [units]
    return urlunparse(parts._replace(query=urlencode(query, doseq=True)))


def local_time(unix, offset):
    """Return ('HH:MM', minutes-from-local-midnight) for a UTC unix time + offset."""
    dt = datetime.fromtimestamp(unix + offset, tz=timezone.utc)
    return dt.strftime("%H:%M"), dt.hour * 60 + dt.minute


def fetch_timeline(target):
    """Start the timeline at today, follow `next`; also return the location's UTC offset."""
    url = (f"{BASE}?lat={LAT}&lon={LON}&units={UNITS}"
           f"&start={start_of_today_utc()}&appid={API_KEY}")
    records, offset = [], 0
    while url and len(records) < target:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 401:
            sys.exit("401 from OpenWeather — activate the 'One Call API 4.0' "
                     "subscription for this key, then re-run.")
        resp.raise_for_status()
        payload = resp.json()
        offset = payload.get("timezone_offset", 0)
        records.extend(payload.get("data", []))
        nxt = payload.get("next")
        url = force_units(nxt) if nxt else None   # keep metric across pagination
    return records[:target], offset


def normalize(records, offset):
    days = []
    for d in records:
        w = (d.get("weather") or [{}])[0]
        sr_str, sr_min = local_time(d["sunrise"], offset)
        ss_str, ss_min = local_time(d["sunset"], offset)
        daylight = ss_min - sr_min
        days.append({
            "date":         datetime.fromtimestamp(d["dt"] + offset, tz=timezone.utc).strftime("%Y-%m-%d"),
            "min":          round(d["temp"]["min"], 1),
            "max":          round(d["temp"]["max"], 1),
            "day":          round(d["temp"]["day"], 1),          # daytime temp -> "average"
            "feels_like":   round(d["feels_like"]["day"], 1),    # daytime feels-like
            "icon":         w.get("icon", ""),
            "desc":         w.get("description", ""),
            "pop":          d.get("pop", 0),
            "wind":         round(d.get("wind_speed", 0), 1),    # m/s
            "humidity":     d.get("humidity", 0),                # %
            "pressure":     d.get("pressure", 0),                # hPa
            "uvi":          d.get("uvi", 0),
            "sunrise":      sr_str,
            "sunset":       ss_str,
            "sun_start":    sr_min,
            "sun_end":      ss_min,
            "daylight":     daylight,                            # minutes
            "daylight_str": f"{daylight // 60}h {daylight % 60:02d}m",
        })
    return {
        "location": LOCATION,
        "units":    UNITS,
        "updated":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days":     days,
    }


def main():
    if not API_KEY:
        sys.exit("OPEN_WEATHER_KEY is not set in the environment.")
    records, offset = fetch_timeline(DAYS)
    data = normalize(records, offset)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(data['days'])} days to {OUT}")


if __name__ == "__main__":
    main()
