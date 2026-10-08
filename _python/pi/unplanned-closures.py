#!/usr/bin/env python3
"""Unplanned road and lane closures on National Highways roads within
config.ROADWORKS_RADIUS_MILES of Cheltenham, from the Road and Lane Closures
v2 service on the National Highways developer portal (DATEX II, as JSON).

Unplanned closures often last less than an hour, so this runs on the Pi with
the other fast feeds rather than in a GitHub workflow. Each run asks for the
closures of the last 24 hours and keeps those still in force plus any that
ended in that time, so the page shows what is happening now and what has just
cleared. Every closure seen is also logged to _data/unplanned-closures-history.json
(kept for two years, like the power cut and flood histories) and listed in the
feeds/unplanned-closures.xml Atom feed. Needs a subscription key from the
portal in NAT_HIGH_KEY (.env).

Planned works still come from roadworks.py and its weekly file."""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import config  # noqa: E402
import helper  # noqa: E402

API_URL = "https://api.data.nationalhighways.co.uk/roads/v2.0/closures"
SOURCE_URL = "https://developer.data.nationalhighways.co.uk/"
LOOKBACK_HOURS = 24
HISTORY_RETENTION_DAYS = 730
LONDON = ZoneInfo("Europe/London")
HISTORY_PATH = "/cheltenham-roadworks/unplanned-closures"


def load_env():
    """Read KEY=value lines from the repo's .env into the environment, if present."""
    env_file = helper.repo_root() / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def closure_label(kind):
    """'laneClosures' -> 'Lane closures'."""
    if not kind:
        return "Closure"
    words = re.sub(r"(?<!^)([A-Z])", r" \1", kind).lower()
    return words[0].upper() + words[1:]


def local_iso(stamp):
    """A DATEX II UTC time ('2026-10-08T17:22:35.35Z') as UK time, 'YYYY-MM-DDTHH:MM'."""
    if not stamp:
        return None
    utc = datetime.strptime(stamp[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return utc.astimezone(LONDON).strftime("%Y-%m-%dT%H:%M")


def find(obj, key):
    """The first value stored under `key` anywhere in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            found = find(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find(v, key)
            if found is not None:
                return found
    return None


def pos_lists(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "posList":
                yield v
            else:
                yield from pos_lists(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from pos_lists(v)


def parse(payload):
    """Every situation record as a flat dict, whatever its record type."""
    records = []
    for situation in payload["D2Payload"].get("situation", []):
        for wrapped in situation.get("situationRecord", []):
            for rec in wrapped.values():
                validity = rec.get("validity") or {}
                times = validity.get("validityTimeSpecification") or {}
                location = rec.get("locationReference")
                points = []
                for pos in pos_lists(location):
                    nums = [float(n) for n in pos.split()]
                    points += list(zip(nums[0::2], nums[1::2]))
                kind = find(rec, "roadOrCarriagewayOrLaneManagementType") or {}
                records.append({
                    "id": rec.get("idG") or "",
                    "road": find(location, "roadName") or "",
                    "description": find(location, "locationDescription") or "",
                    "closure": closure_label(kind.get("value") if isinstance(kind, dict) else ""),
                    "active": validity.get("validityStatus") == "active",
                    "start": local_iso(times.get("overallStartTime")),
                    "end": local_iso(times.get("overallEndTime")),
                    "points": points,
                })
    return records


def local_items(records, centre, radius_miles):
    """Closures with any point within `radius_miles` of `centre`, placed at
    their nearest point, those still in force first, then by distance."""
    items = []
    for r in records:
        if not r["points"]:
            continue
        lat, lon = min(r["points"], key=lambda p: helper.haversine_miles(centre[0], centre[1], p[0], p[1]))
        distance = helper.haversine_miles(centre[0], centre[1], lat, lon)
        if distance > radius_miles:
            continue
        item = {k: v for k, v in r.items() if k not in ("points", "active")}
        item.update(status="Active" if r["active"] else "Ended", lat=lat, lon=lon,
                    distance_miles=round(distance, 1))
        items.append(item)
    return sorted(items, key=lambda i: (i["status"] != "Active", i["distance_miles"]))


def has_ended(record):
    """Reported ended, or dropped out of the 24-hour window while still active."""
    return record.get("status") == "Ended" or bool(record.get("resolved_iso"))


def build_atom_items(history, history_url):
    """One entry per closure, keyed by its id so a feed reader sees the same
    item update when the closure ends, dated by when it was last seen."""
    items = []
    for r in history[:50]:
        ended = has_ended(r)
        title = f"{r['closure']}: {r['description']}"
        summary = f"Started {(r.get('start') or '').replace('T', ' ')}."
        if ended:
            title = f"Ended: {title}"
            summary += f" Ended {(r.get('end') or '').replace('T', ' ')}."
        else:
            summary += " Still in force."
        items.append({
            "title": title,
            "link": f"{history_url}#{r['id']}",
            "summary": summary,
            "published_iso": r.get("last_seen_iso") or r.get("first_seen_iso"),
            "source": "National Highways",
        })
    return items


def main():
    load_env()
    key = os.environ.get("NAT_HIGH_KEY")
    if not key:
        raise SystemExit("NAT_HIGH_KEY is not set")
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    resp = helper.get(API_URL, headers={
        "Ocp-Apim-Subscription-Key": key,
        "X-Response-MediaType": "application/json",
    }, params={
        "closureType": "unplanned",
        "startDateTime": (now - timedelta(hours=LOOKBACK_HOURS)).isoformat(),
        "endDateTime": now.isoformat(),
    })
    items = local_items(parse(resp.json()), config.CENTRE, config.ROADWORKS_RADIUS_MILES)
    root = helper.repo_root()
    out = root / "_data" / "unplanned-closures.json"
    helper.write_json(out, {
        "source": "National Highways",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "refresh": "every 5 minutes",
        "radius_miles": config.ROADWORKS_RADIUS_MILES,
        "items": items,
    })
    active = sum(i["status"] == "Active" for i in items)
    print(f"Wrote {len(items)} unplanned closures ({active} active) to {out}")

    history_path = root / "_data" / "unplanned-closures-history.json"
    records = json.loads(history_path.read_text()).get("records", []) if history_path.exists() else []
    records = helper.update_history(
        records, items, id_key="id", now_iso=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        retention_days=HISTORY_RETENTION_DAYS,
    )
    for r in records:
        # Gone from the 24-hour window while still marked active: it ended
        # some time after it was last seen.
        if r.get("resolved_iso") and r.get("status") != "Ended":
            r["status"] = "Ended"
            r["end"] = local_iso(r["resolved_iso"])
    helper.write_json(history_path, {
        "source": "National Highways",
        "source_url": SOURCE_URL,
        "licence": "Open Government Licence v3.0",
        "refresh": "every 5 minutes",
        "radius_miles": config.ROADWORKS_RADIUS_MILES,
        "count": len(records),
        "records": records,
    })
    print(f"History now holds {len(records)} unplanned closures")

    site = helper.site_url()
    history_url = f"{site}{HISTORY_PATH}"
    helper.write_items_atom(
        items=build_atom_items(records, history_url),
        filename=root / "feeds" / "unplanned-closures.xml",
        permalink_path="/feeds/unplanned-closures.xml",
        feed_title="Cheltenham Unplanned Road Closures",
        feed_subtitle="Unplanned lane and road closures on National Highways roads near Cheltenham",
        self_url=f"{site}/feeds/unplanned-closures.xml",
        alternate_url=history_url,
    )


if __name__ == "__main__":
    main()
