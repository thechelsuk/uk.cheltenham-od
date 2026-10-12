"""Current Environment Agency flood warnings for Gloucestershire, written to
_data/flood.json for _layouts/safety-environment/flood-warnings.html, plus
the rolling _data/flood-history.json log and the feeds/flood.xml Atom feed."""
import datetime
import json

import helper

# History entries are kept for two years, generous for a Gloucestershire-only feed.
HISTORY_RETENTION_DAYS = 730

SOURCE_NAME = "Environment Agency flood monitoring API"
SOURCE_URL = "https://environment.data.gov.uk/flood-monitoring/doc/reference"
LICENCE = "Open Government Licence v3.0"


def normalize_item(item):
    """Flatten one EA flood API item into the flat shape used for the
    history log and the Atom feed — see
    https://environment.data.gov.uk/flood-monitoring/doc/reference for the
    raw item shape (a nested floodArea object, no lat/lon)."""
    flood_area = item.get("floodArea") or {}
    return {
        "flood_id": item.get("@id") or item.get("floodAreaID") or item.get("description") or "",
        "description": item.get("description") or "",
        "severity": item.get("severity") or "",
        "severity_level": item.get("severityLevel"),
        "message": item.get("message") or "",
        "county": flood_area.get("county") or "",
        "river_or_sea": flood_area.get("riverOrSea") or "",
        "time_raised": item.get("timeRaised") or "",
        "time_severity_changed": item.get("timeSeverityChanged") or "",
    }


def build_payload(data, generated_at):
    """The current warnings from an EA /id/floods response, flattened and
    ordered most severe first (severity level 1 is a severe flood warning,
    4 a warning no longer in force)."""
    items = [normalize_item(i) for i in data.get("items", [])]
    items.sort(key=lambda i: i["severity_level"] if i["severity_level"] is not None else 99)
    return {
        "generated_at": generated_at,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "count": len(items),
        "items": items,
    }


def build_atom_items(history_records, history_url):
    """One entry per flood warning, keyed by a stable flood_id so a feed
    reader treats it as the same item across runs, dated by last_seen_iso so
    a severity change or removal (once we still see it) bumps "updated"."""
    items = []
    for record in history_records[:50]:
        title = f"{record.get('severity', 'Flood')}: {record.get('description', '')}"
        summary_parts = []
        if record.get("message"):
            summary_parts.append(record["message"])
        if record.get("county"):
            summary_parts.append(f"County: {record['county']}")
        items.append({
            "title": title,
            "link": f"{history_url}#{record['flood_id']}",
            "summary": " · ".join(summary_parts) or title,
            "published_iso": record.get("last_seen_iso") or record.get("first_seen_iso"),
            "source": "Environment Agency",
        })
    return items


if __name__ == "__main__":
    root      = helper.repo_root()
    data_dir  = root / "_data"
    feeds_dir = root / "feeds"
    data_dir.mkdir(parents=True, exist_ok=True)
    feeds_dir.mkdir(parents=True, exist_ok=True)

    flood_json = data_dir / "flood.json"
    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    current = build_payload(helper.fetch_flood_data(), now.isoformat())
    current_items = current["items"]
    helper.write_json(flood_json, current)
    print(f"  {len(current_items)} current flood warnings for Gloucestershire, saved to {flood_json}")

    history_path = data_dir / "flood-history.json"
    if history_path.exists():
        history_payload = json.loads(history_path.read_text())
        history_records = history_payload.get("records", [])
    else:
        history_records = []

    history_records = helper.update_history(
        history_records, current_items, id_key="flood_id", now_iso=now_iso,
        retention_days=HISTORY_RETENTION_DAYS,
    )
    history_payload = {
        "generated_at": now.isoformat(),
        "note": "Rolling log of flood warnings recorded for Gloucestershire, built up incrementally each "
                "run — not a full historical archive from before this page existed.",
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "count": len(history_records),
        "records": history_records,
    }
    helper.write_json(history_path, history_payload)
    print(f"History now holds {len(history_records)} recorded flood warnings")

    site = helper.site_url()
    history_url = f"{site}/cheltenham-flood-warnings/history"

    flood_atom = feeds_dir / "flood.xml"
    helper.write_items_atom(
        items=build_atom_items(history_records, history_url),
        filename=flood_atom,
        permalink_path="/feeds/flood.xml",
        feed_title="Flood Warnings",
        feed_subtitle="Current and recent flood warnings for Gloucestershire",
        self_url=f"{site}/feeds/flood.xml",
        alternate_url=history_url,
    )
    print(f"Atom feed saved to {flood_atom}")
