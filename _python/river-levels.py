#!/usr/bin/env python3
"""Fetch river level and rainfall gauge readings near Cheltenham from the
Environment Agency's flood monitoring API and write:

- _data/river-levels.json: every level gauge within 6km and rainfall gauge
  within 12km of the town centre, each with its latest reading, the typical
  range, the highest level on record and the last 48 hours of 15-minute
  readings for the chart
- _data/river-levels-history.json: one summary per gauge per day (lowest,
  average and highest level, or total rainfall), kept for two years. The API
  only holds about four weeks of readings, so this is what keeps the longer
  record. The first run backfills the four weeks the API still has.

Gauges are found by distance from the town centre rather than listed by hand,
so a new or retired gauge is picked up automatically. Readings are in UTC.

Source: https://environment.data.gov.uk/flood-monitoring/doc/reference
"""

import datetime
import json

import config
import helper

BASE_URL = "https://environment.data.gov.uk/flood-monitoring"

CENTRE = config.CENTRE
RADIUS_KM = config.RIVER_LEVELS_RADIUS_KM

CHART_HOURS = 48
BACKFILL_DAYS = 28   # about as far back as the API keeps readings
REFRESH_DAYS = 3     # each run re-reads a few days so yesterday is always complete
RETENTION_DAYS = 730
STALE_AFTER = datetime.timedelta(days=7)  # a gauge with nothing newer is treated as retired


def get(path, **params):
    response = helper.get(f"{BASE_URL}{path}", params=params, timeout=60)
    return response.json()




def parse_time(value):
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_stations():
    stations = []
    for kind, radius in RADIUS_KM.items():
        items = get("/id/stations", parameter=kind, lat=CENTRE[0], long=CENTRE[1], dist=radius, _limit=200)["items"]
        for item in items:
            measures = item.get("measures")
            measures = measures if isinstance(measures, list) else [measures]
            measure = next((m for m in measures if m and m.get("parameter") == kind), None)
            if not measure or item.get("lat") is None:
                continue
            stations.append({"kind": kind, "item": item, "measure": measure})
    return stations


def fetch_readings(reference, since):
    items = get(f"/id/stations/{reference}/readings", since=since.strftime("%Y-%m-%dT%H:%M:%SZ"), _sorted="", _limit=10000)["items"]
    readings = []
    for row in items:
        value = row.get("value")
        if isinstance(value, list):  # a station with several measures can return more than one value
            value = value[0]
        if value is not None:
            readings.append((parse_time(row["dateTime"]), float(value)))
    return sorted(readings)


def level_status(value, low, high):
    if low is None or high is None:
        return None
    if value > high:
        return "Above typical range"
    if value < low:
        return "Below typical range"
    return "Within typical range"


def daily_summaries(readings, kind, today):
    """{date: summary} for every complete UTC day in `readings`."""
    days = {}
    for when, value in readings:
        if when.date() < today:
            days.setdefault(when.date().isoformat(), []).append(value)
    if kind == "rainfall":
        return {day: {"total": round(sum(values), 1)} for day, values in days.items()}
    return {day: {"min": round(min(values), 3), "mean": round(sum(values) / len(values), 3), "max": round(max(values), 3)}
            for day, values in days.items()}


def main():
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    history_path = helper.repo_root() / "_data" / "river-levels-history.json"
    history = {"days": {}}
    if history_path.exists():
        history = json.loads(history_path.read_text())
    history_days = history.get("days", {})
    fetch_days = REFRESH_DAYS if history_days else BACKFILL_DAYS
    since = now - datetime.timedelta(days=fetch_days)
    chart_since = now - datetime.timedelta(hours=CHART_HOURS)

    stations = []
    for entry in find_stations():
        item, kind = entry["item"], entry["kind"]
        reference = item["stationReference"]
        readings = fetch_readings(reference, since)
        if not readings or now - readings[-1][0] > STALE_AFTER:
            print(f"Skipping {reference} ({item.get('label')}): no recent readings")
            continue

        latest_time, latest_value = readings[-1]
        recent = [(t, v) for t, v in readings if t >= chart_since]
        # The list response only links to the stage scale; the station's own record has it in full.
        detail = get(f"/id/stations/{reference}")["items"] if kind == "level" else {}
        scale = detail.get("stageScale") if isinstance(detail.get("stageScale"), dict) else {}
        low, high = scale.get("typicalRangeLow"), scale.get("typicalRangeHigh")
        record = scale.get("maxOnRecord") or {}

        station = {
            "reference": reference,
            "kind": kind,
            "label": item.get("label") if item.get("label") != "Rainfall station" else f"Rainfall gauge {reference}",
            "river": item.get("riverName") or "",
            "lat": item["lat"],
            "lon": item["long"],
            "distance_km": round(helper.haversine_km(*CENTRE, item["lat"], item["long"]), 1),
            "unit": "mm" if kind == "rainfall" else "m",
            "latest_time": latest_time.strftime("%Y-%m-%dT%H:%M"),
            "readings": [[t.strftime("%Y-%m-%dT%H:%M"), v] for t, v in recent],
        }
        if kind == "level":
            station.update({
                "latest": latest_value,
                "latest_display": f"{latest_value:.2f} m",
                "typical_low": low,
                "typical_high": high,
                "typical_range_display": f"{low:.2f} to {high:.2f} m" if low is not None and high is not None else None,
                "status": level_status(latest_value, low, high),
                "record": record.get("value"),
                "record_display": f"{record['value']:.2f} m" if record.get("value") is not None else None,
                "record_date": record["dateTime"][:10] if record.get("dateTime") else None,
            })
        else:
            last_24h = sum(v for t, v in recent if t >= now - datetime.timedelta(hours=24))
            station.update({
                "rain_24h": round(last_24h, 1),
                "rain_24h_display": f"{last_24h:.1f} mm",
                "rain_48h": round(sum(v for _, v in recent), 1),
                "rain_48h_display": f"{sum(v for _, v in recent):.1f} mm",
            })
        stations.append(station)

        for day, summary in daily_summaries(readings, kind, today).items():
            history_days.setdefault(day, {})[reference] = summary

    if not stations:
        raise SystemExit("No gauges returned readings — leaving the existing data in place")

    stations.sort(key=lambda s: (s["kind"] != "level", s["river"] != "River Chelt", s["river"], s["label"]))
    output = {
        "generated_at": now.isoformat(),
        "source": "Environment Agency flood monitoring API",
        "source_url": "https://environment.data.gov.uk/flood-monitoring/doc/reference",
        "licence": "Open Government Licence v3.0",
        "centre": {"latitude": CENTRE[0], "longitude": CENTRE[1]},
        "radius_km": RADIUS_KM,
        "stations": stations,
    }
    (helper.repo_root() / "_data" / "river-levels.json").write_text(json.dumps(output, indent=2, ensure_ascii=False))

    cutoff = (today - datetime.timedelta(days=RETENTION_DAYS)).isoformat()
    history["days"] = {day: values for day, values in sorted(history_days.items()) if day >= cutoff}
    history["generated_at"] = now.isoformat()
    history["retention_days"] = RETENTION_DAYS
    history_path.write_text(json.dumps(history, indent=1, ensure_ascii=False))

    levels = sum(s["kind"] == "level" for s in stations)
    print(f"Wrote {levels} level and {len(stations) - levels} rainfall gauges; history covers {len(history['days'])} days")


if __name__ == "__main__":
    main()
