#!/usr/bin/env python3
"""Live and historical power cuts affecting Cheltenham (postcodes GL50-GL54),
from National Grid Electricity Distribution's open "Live Power Cuts" feed —
the electricity DNO for Gloucestershire, formerly Western Power Distribution.

Writes the current snapshot to _data/power-cuts.json (full overwrite, like
bus-disruptions.py/flood.py), an Atom feed to feeds/power-cuts.xml, and the
homepage alert include — but unlike those two, also keeps a real rolling
history in _data/power-cuts-history.json, since the live feed only ever shows
what's active right now and drops an incident the moment it's restored."""
import datetime
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import helper

DETAILED_CSV_URL = (
    "https://connecteddata.nationalgrid.co.uk/dataset/d6672e1e-c684-4cea-bb78-c7e5248b62a2/"
    "resource/a1365982-4e05-463c-8304-8323a2ba0ccd/download/live_detailed_power_cuts.csv"
)
SOURCE_PAGE = "https://connecteddata.nationalgrid.co.uk/dataset/live-power-cuts"
LICENCE = "WPD Open Data Licence"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

CHELTENHAM_POSTCODE_PREFIXES = ("GL50", "GL51", "GL52", "GL53", "GL54")

# History entries are kept for two years, generous for a Cheltenham-only feed
# that will only ever see a handful of incidents a year, but still bounded.
HISTORY_RETENTION_DAYS = 730


def is_cheltenham_postcode(postcode):
    compact = postcode.replace(" ", "").upper()
    return compact.startswith(CHELTENHAM_POSTCODE_PREFIXES)


def row_postcodes(row):
    raw = row.get("postcode") or ""
    return [p.strip() for p in raw.split(",") if p.strip()]


def row_is_local(row):
    return any(is_cheltenham_postcode(p) for p in row_postcodes(row))


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_incident(row):
    return {
        "fault_id": row.get("fault_id") or "",
        "status": row.get("status") or "",
        "planned": (row.get("planned") or "").lower() == "true",
        "category": helper.clean_name(row.get("category") or ""),
        "confirmed_off": to_int(row.get("confirmed_off")),
        "predicted_off": to_int(row.get("predicted_off")),
        "restored": to_int(row.get("restored")),
        "voltage": row.get("voltage") or "",
        "date_of_reported_fault": row.get("date_of_reported_fault") or "",
        "last_updated": row.get("last_updated") or "",
        "date_of_restoration": row.get("date_of_restoration") or "",
        "etr": row.get("etr") or "",
        "lat": to_float(row.get("location_latitude")),
        "lon": to_float(row.get("location_longitude")),
        "postcodes": row_postcodes(row),
    }


def build_alert_html(incidents):
    active = [i for i in incidents if i["status"] not in ("Restored",) and i["restored"] == 0]
    if not active:
        return ""

    now_str = datetime.datetime.now().strftime("%H:%M")
    items = ""
    for incident in active[:5]:
        area = incident["postcodes"][0] if incident["postcodes"] else "Cheltenham"
        items += (
            f'  <li><a href="/cheltenham-power-cuts">'
            f'Power cut reported near {area} at {now_str}</a></li>\n'
        )
    return (
        "<h2>Power Cut Alert</h2>\n"
        "<ul>\n"
        f"{items}"
        "</ul>"
    )


def build_atom_items(history_records, page_url):
    """One entry per incident, keyed by a stable per-fault_id link/id so a
    feed reader treats it as the *same* item across runs rather than a new
    one — and dated by last_seen_iso (not first_seen_iso), so a status change
    such as being restored bumps its "updated" time and surfaces as an
    update, not just a silent edit to an entry the reader already saw."""
    items = []
    for record in history_records[:50]:
        area = record["postcodes"][0] if record["postcodes"] else "Cheltenham"
        status = record.get("status", "")
        title = f"Power cut near {area} — {status}" if status else f"Power cut near {area}"
        summary_parts = [record.get("category") or ""]
        if record.get("confirmed_off"):
            summary_parts.append(f"{record['confirmed_off']} properties affected (peak)")
        if record.get("date_of_restoration"):
            summary_parts.append(f"Restored: {record['date_of_restoration']}")
        items.append({
            "title": title,
            "link": f"{page_url}#{record['fault_id']}",
            "summary": " · ".join(p for p in summary_parts if p),
            "published_iso": record.get("last_seen_iso") or record.get("first_seen_iso"),
            "source": "National Grid Electricity Distribution",
        })
    return items


if __name__ == "__main__":
    import csv
    import io

    import requests

    root = helper.repo_root()
    data_dir = root / "_data"
    feeds_dir = root / "feeds"

    print("Downloading NGED live power cuts feed...")
    resp = requests.get(DETAILED_CSV_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    print(f"  {len(rows):,} incidents nationally")

    local_rows = [r for r in rows if row_is_local(r)]
    incidents = [build_incident(r) for r in local_rows]
    print(f"  {len(incidents)} incidents affecting Cheltenham postcodes")

    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = {
        "updated": helper.updated_timestamp(),
        "updated_iso": datetime.date.today().isoformat(),
        "source": SOURCE_PAGE,
        "licence": LICENCE,
        "count": len(incidents),
        "incidents": incidents,
    }
    data_json = data_dir / "power-cuts.json"
    helper.write_json(data_json, payload)
    print(f"Wrote {len(incidents)} incidents to {data_json}")

    history_path = data_dir / "power-cuts-history.json"
    if history_path.exists():
        import json
        history_payload = json.loads(history_path.read_text())
        history_records = history_payload.get("records", [])
    else:
        history_records = []

    history_records = helper.update_history(
        history_records, incidents, id_key="fault_id", now_iso=now_iso,
        peak_fields=["confirmed_off"], retention_days=HISTORY_RETENTION_DAYS,
    )
    history_payload = {
        "generated_at": now.isoformat(),
        "note": "Rolling log of power cuts recorded affecting Cheltenham (GL50-GL54) postcodes, "
                "built up incrementally each run — not a full historical archive from before this page existed.",
        "source": SOURCE_PAGE,
        "licence": LICENCE,
        "count": len(history_records),
        "records": history_records,
    }
    helper.write_json(history_path, history_payload)
    print(f"History now holds {len(history_records)} recorded incidents")

    site = helper.site_url()
    page_url = f"{site}/cheltenham-power-cuts"
    history_url = f"{page_url}/history"

    atom_path = feeds_dir / "power-cuts.xml"
    helper.write_items_atom(
        items=build_atom_items(history_records, history_url),
        filename=atom_path,
        permalink_path="/feeds/power-cuts.xml",
        feed_title="Cheltenham Power Cuts",
        feed_subtitle="Live and recent power cuts affecting Cheltenham",
        self_url=f"{site}/feeds/power-cuts.xml",
        alternate_url=history_url,
    )
    print(f"Atom feed saved to {atom_path}")

    include_path = root / "_includes" / "power-cuts-alert.html"
    include_contents = include_path.open().read()
    include_contents = helper.replace_chunk(include_contents, "power_cuts_alert_marker", build_alert_html(incidents))
    include_path.open("w").write(include_contents)
