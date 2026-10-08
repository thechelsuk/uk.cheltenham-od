#!/usr/bin/env python3
"""Wildfire risk around Cheltenham from the Met Office Fire Severity Index (FSI),
which Natural England publishes on its Open Access site as a daily map of 10 km
Ordnance Survey grid squares (today plus five days ahead). We take every square
within config.WILDFIRE_RADIUS_KM of the town centre, since smoke and wind from
the Cotswold escarpment carry well beyond the borough boundary.

The FSI is issued once each morning, so this runs with the daily workflow.
Writes the current snapshot to _data/wildfire.json, logs today to
_data/wildfire-history.json when it reaches HISTORY_LEVEL (the source keeps no
past days, and most days are low, so only the days that matter are kept), and
writes an Atom feed and the homepage alert."""
import json
from datetime import datetime, timezone

import config
import helper

FSI_SERVICE = "https://services.arcgis.com/JJzESW51TqeY9uat/arcgis/rest/services/OASYS_FSI_PRD_VIEW/FeatureServer"
SOURCE_URL = "https://openaccess.naturalengland.org.uk/"
SOURCE = "Met Office Fire Severity Index, published by Natural England"

LEVELS = {1: "Low", 2: "Moderate", 3: "High", 4: "Very high", 5: "Exceptional"}

# The homepage alert shows from "very high"; the feed and the history log
# keep every day from "high".
ALERT_LEVEL = 4
FEED_LEVEL = 3
HISTORY_LEVEL = 3

PAGE_PATH = "/cheltenham-wildfire-risk"


def level_label(rating):
    return LEVELS.get(rating, "Unknown")


def summarise_days(features):
    """One entry per forecast day, rated by the highest square that day."""
    by_offset = {}
    for f in features:
        by_offset.setdefault(f["data_date_offset_pk"], []).append(f)
    days = []
    for offset in sorted(by_offset):
        squares = by_offset[offset]
        rating = max(s["rating"] for s in squares)
        days.append({
            "date": squares[0]["dow_date"],
            "offset": offset,
            "rating": rating,
            "label": level_label(rating),
            "squares_at_max": sorted(s["square_reference_pk"] for s in squares if s["rating"] == rating),
        })
    return days


def upsert_history(records, entry, threshold=HISTORY_LEVEL):
    """Replace any record for entry's date with entry, newest first. A day
    below `threshold` is not logged, and drops out if a later run that day
    revises it down."""
    kept = [r for r in records if r.get("date") != entry["date"]]
    if entry["rating"] >= threshold:
        kept.append(entry)
    return sorted(kept, key=lambda r: r["date"], reverse=True)


def build_alert_html(days, threshold=ALERT_LEVEL):
    """Homepage alert for today and tomorrow at `threshold` or above."""
    items = ""
    for day in days[:2]:
        if day["rating"] >= threshold:
            items += (
                f'  <li><a href="{PAGE_PATH}">{day["label"]} ({day["rating"]} of 5) fire severity '
                f'forecast around Cheltenham on {day["date"]}</a></li>\n'
            )
    if not items:
        return ""
    return "<h2>Wildfire Risk Alert</h2>\n<ul>\n" + items + "</ul>"


def build_atom_items(history, days, page_url, issued_iso, threshold=FEED_LEVEL):
    """One entry per day at `threshold` or above, keyed by its date so a
    forecast day and the same day once it has passed stay one item."""
    items = []
    forecast_dates = set()
    for day in days:
        forecast_dates.add(day["date"])
        if day["rating"] >= threshold:
            items.append({
                "title": f"Forecast: {day['label']} fire severity around Cheltenham on {day['date']}",
                "link": f"{page_url}#{day['date']}",
                "summary": f"Fire Severity Index {day['rating']} of 5 ({day['label']}) forecast for "
                           f"{day['date']} within {config.WILDFIRE_RADIUS_KM} km of Cheltenham.",
                "published_iso": issued_iso,
                "source": "Met Office",
            })
    for record in history:
        if record["date"] in forecast_dates or record["rating"] < threshold:
            continue
        label = level_label(record["rating"])
        items.append({
            "title": f"{label} fire severity around Cheltenham on {record['date']}",
            "link": f"{page_url}/history#{record['date']}",
            "summary": f"Fire Severity Index {record['rating']} of 5 ({label}) on {record['date']} "
                       f"within {config.WILDFIRE_RADIUS_KM} km of Cheltenham.",
            "published_iso": record.get("recorded_iso") or f"{record['date']}T00:00:00Z",
            "source": "Met Office",
        })
    return items[:50]


def rings_to_latlon(rings):
    """Esri polygon rings ([x, y] = [lon, lat]) as Leaflet [lat, lon] rings."""
    return [[[y, x] for x, y in ring] for ring in rings]


def fetch_squares():
    lat, lon = config.CENTRE
    resp = helper.get(f"{FSI_SERVICE}/0/query", params={
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": 4326,
        "distance": config.WILDFIRE_RADIUS_KM * 1000,
        "units": "esriSRUnit_Meter",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "square_reference_pk,dow_date,data_date_offset_pk,rating",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "json",
    })
    payload = resp.json()
    if "error" in payload:
        raise RuntimeError(f"FSI query failed: {payload['error']}")
    return payload["features"]


def fetch_issued_iso():
    """When the Met Office issued today's FSI, as 'YYYY-MM-DDTHH:MM' UK time."""
    resp = helper.get(f"{FSI_SERVICE}/1/query", params={
        "where": "language='DEFAULT'",
        "outFields": "received_date,time_received",
        "f": "json",
    })
    features = resp.json().get("features") or []
    if not features:
        return None
    attrs = features[0]["attributes"]
    day = datetime.fromtimestamp(attrs["received_date"] / 1000, timezone.utc).date().isoformat()
    return f"{day}T{attrs.get('time_received') or '00:00'}"


def main():
    root = helper.repo_root()
    data_dir = root / "_data"
    feeds_dir = root / "feeds"

    features = fetch_squares()
    attrs = [f["attributes"] for f in features]
    days = summarise_days(attrs)
    if not days:
        raise RuntimeError("FSI returned no squares around Cheltenham")
    issued_iso = fetch_issued_iso()
    now = datetime.now(timezone.utc)

    squares = {}
    for f in features:
        a = f["attributes"]
        sq = squares.setdefault(a["square_reference_pk"], {"ref": a["square_reference_pk"], "days": []})
        sq["days"].append({"date": a["dow_date"], "rating": a["rating"], "label": level_label(a["rating"])})
        if a["data_date_offset_pk"] == 0:
            sq["rating"] = a["rating"]
            sq["label"] = level_label(a["rating"])
            sq["rings"] = rings_to_latlon(f["geometry"]["rings"])
    for sq in squares.values():
        sq["days"].sort(key=lambda d: d["date"])
    square_list = sorted(squares.values(), key=lambda s: s["ref"])

    today = days[0]
    payload = {
        "generated_at": now.isoformat(),
        "issued_iso": issued_iso,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "radius_km": config.WILDFIRE_RADIUS_KM,
        "today": today,
        "days": days,
        "squares": square_list,
    }
    helper.write_json(data_dir / "wildfire.json", payload)
    print(f"Today {today['date']}: {today['label']} ({today['rating']}) across {len(square_list)} squares")

    history_path = data_dir / "wildfire-history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    records = history.get("records", [])
    records = upsert_history(records, {
        "date": today["date"],
        "rating": today["rating"],
        "label": today["label"],
        "squares": {s["ref"]: s["rating"] for s in square_list if "rating" in s},
        "recorded_iso": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    helper.write_json(history_path, {
        "generated_at": now.isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "radius_km": config.WILDFIRE_RADIUS_KM,
        "level": HISTORY_LEVEL,
        "tracking_since": history.get("tracking_since") or today["date"],
        "count": len(records),
        "records": records,
    })
    print(f"History now holds {len(records)} days at level {HISTORY_LEVEL} or above")

    site = helper.site_url()
    page_url = f"{site}{PAGE_PATH}"
    helper.write_items_atom(
        items=build_atom_items(records, days, page_url, now.strftime("%Y-%m-%dT%H:%M:%SZ")),
        filename=feeds_dir / "wildfire.xml",
        permalink_path="/feeds/wildfire.xml",
        feed_title="Cheltenham Wildfire Risk",
        feed_subtitle="Days of high, very high or exceptional fire severity around Cheltenham",
        self_url=f"{site}/feeds/wildfire.xml",
        alternate_url=page_url,
    )

    include_path = root / "_includes" / "wildfire-alert.html"
    contents = include_path.read_text()
    include_path.write_text(helper.replace_chunk(contents, "wildfire_alert_marker", build_alert_html(days)))


if __name__ == "__main__":
    main()
