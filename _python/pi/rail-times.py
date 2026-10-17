#!/usr/bin/env python3
"""Next departures and arrivals at Cheltenham Spa station (CRS: CNM), from
National Rail's Live Departure Board Web Service (LDBWS) on the Rail Data
Marketplace. Writes _data/rail-times.json.

Runs from the Pi via _python/run.sh rather than a GitHub Actions schedule,
since a departure board is stale within minutes:

    _python/run.sh _python/pi/rail-times.py

Only the next MAX_SERVICES of each are kept and the file is overwritten every
run — a board only ever shows what's coming up, so there is no history.
Because each run is a commit, a run whose services and messages are unchanged
leaves the file alone until HEARTBEAT_MINUTES have passed, so the page's
"last updated" time (and its stale-data warning) still moves on quiet nights
without a commit every few minutes.

Needs RDM_LDBWS_KEY (the "Consumer key" from the free "Live Arrival and
Departure Boards" product on raildata.org.uk) in the environment or in the
repo's gitignored .env.

That product has one combined board, GetArrDepBoardWithDetails. Each service on
it carries whichever of the scheduled arrival (sta) and departure (std) times
apply at this station, so a train that starts here has only std, one that
terminates has only sta, and a through train has both. One call therefore feeds
both tables: departures are the services with a std, arrivals the ones with a sta.
"""
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

# Load .env file for local development / the Pi if present
import alerts_feed
import config
import helper

# Load .env file for local development / the Pi if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

OUT = helper.repo_root() / "_data" / "rail-times.json"
HISTORY = helper.repo_root() / "_data" / "rail-disruptions-history.json"
FEED = helper.repo_root() / "feeds" / "rail-disruptions.xml"
ALERT_INCLUDE = helper.repo_root() / "_includes" / "rail-alert.html"

BASE_URL = "https://api1.raildata.org.uk/1010-live-arrival-and-departure-boards-arr-and-dep1_1/LDBWS/api/20220120"
BOARD_METHOD = "GetArrDepBoardWithDetails"

STATION_NAME = "Cheltenham Spa"
CRS = "CNM"
NUM_ROWS = 10           # rows requested from the API
MAX_SERVICES = 10       # rows kept per board
HEARTBEAT_MINUTES = 30  # see module docstring

HISTORY_RETENTION_DAYS = 365
PAGE_PATH = "/cheltenham-train-times"
DEFAULT_DISRUPTION_MESSAGE = "Rail replacement buses are running instead of trains at Cheltenham Spa."
DISRUPTION_WORDS = re.compile(r"train services|engineering|replacement", re.IGNORECASE)

LONDON = ZoneInfo("Europe/London")
TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def fetch_board(api_key):
    resp = requests.get(
        f"{BASE_URL}/{BOARD_METHOD}/{CRS}",
        params={"numRows": NUM_ROWS},
        headers={**config.HEADERS, "x-apikey": api_key},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def board_time(board):
    """When the board was generated, as an aware London datetime (used to give
    the bare HH:MM times a date). Falls back to now if it's missing."""
    raw = board.get("generatedAt") or ""
    # LDBWS timestamps carry 7 fractional digits; fromisoformat wants at most 6.
    raw = re.sub(r"(\.\d{6})\d+", r"\1", raw)
    try:
        return datetime.fromisoformat(raw).astimezone(LONDON)
    except ValueError:
        return datetime.now(LONDON)


def resolve_time(hhmm, generated):
    """'16:24' -> datetime on the board's date. A time more than 12 hours
    before the board was generated is taken to be after midnight."""
    hour, minute = (int(part) for part in hhmm.split(":"))
    resolved = generated.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if resolved < generated - timedelta(hours=12):
        resolved += timedelta(days=1)
    return resolved


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M") if dt else None


def clean_text(text):
    """Strip the HTML LDBWS puts in messages and reasons down to plain text."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def place_names(points):
    """Origin/destination lists -> 'Bristol Temple Meads' (with any 'via ...')."""
    names = []
    for point in points or []:
        name = point.get("locationName", "")
        names.append(f"{name} {point['via']}" if point.get("via") else name)
    return " and ".join(n for n in names if n)


def calling_at(service):
    names = []
    for group in service.get("subsequentCallingPoints") or []:
        for point in group.get("callingPoint") or []:
            name = point.get("locationName")
            if name and name not in names:
                names.append(name)
    return names


def parse_service(service, kind, generated):
    """One LDBWS service -> the flat dict the layout reads, or None if it has
    no scheduled time. `kind` is "departure" or "arrival"."""
    scheduled_key, estimate_key = ("std", "etd") if kind == "departure" else ("sta", "eta")
    scheduled_text = service.get(scheduled_key)
    if not scheduled_text or not TIME_PATTERN.match(scheduled_text):
        return None

    scheduled = resolve_time(scheduled_text, generated)
    estimate = (service.get(estimate_key) or "").strip()
    expected = None

    if service.get("isCancelled") or estimate.lower() == "cancelled":
        status = "Cancelled"
    elif estimate.lower() == "on time":
        status, expected = "On time", scheduled
    elif TIME_PATTERN.match(estimate):
        expected = resolve_time(estimate, generated)
        status = "On time" if expected == scheduled else "Delayed"
    elif estimate.lower() == "delayed":
        status = "Delayed"
    else:
        status = "No report"

    item = {
        "scheduled":   iso(scheduled),
        "expected":    iso(expected),
        "status":      status,
        "platform":    service.get("platform") or "",
        "operator":    service.get("operator") or "",
        "origin":      place_names(service.get("origin")),
        "destination": place_names(service.get("destination")),
        "reason":      clean_text(service.get("cancelReason") or service.get("delayReason")),
    }
    if kind == "departure":
        item["calling_at"] = calling_at(service)
    return item


def parse_board(board, kind):
    """Trains and rail replacement buses together in time order, each marked
    with its `mode` so the page can label the buses."""
    generated = board_time(board)
    services = []
    for mode, key in (("train", "trainServices"), ("bus", "busServices")):
        for service in board.get(key) or []:
            item = parse_service(service, kind, generated)
            if item:
                services.append({**item, "mode": mode})
    services.sort(key=lambda s: s["scheduled"])
    return services[:MAX_SERVICES]


def station_messages(board):
    messages = []
    for message in board.get("nrccMessages") or []:
        # The API capitalises the key as "Value"; accept either spelling.
        text = clean_text(message.get("Value") or message.get("value"))
        if text and text not in messages:
            messages.append(text)
    return messages


def unchanged(new, now):
    """True when the existing file has the same services/messages and is
    younger than the heartbeat."""
    try:
        old = json.loads(OUT.read_text())
        age = now - datetime.fromisoformat(old["generated_at"])
    except (OSError, ValueError, KeyError):
        return False
    if any(old.get(k) != new.get(k) for k in ("messages", "departures", "arrivals", "replacement_buses_only")):
        return False
    return age < timedelta(minutes=HEARTBEAT_MINUTES)


def replacement_buses_only(board):
    """True when rail replacement buses are running and no trains are, which
    is how the board shows the line closed for engineering work. A late night
    with neither isn't a closure."""
    return bool(board.get("busServices")) and not board.get("trainServices")


def disruption_message(messages):
    """The station message about the closure, or a standard line if there
    isn't one. Messages carry no category, so this goes by their wording."""
    return next((m for m in messages if DISRUPTION_WORDS.search(m)), DEFAULT_DISRUPTION_MESSAGE)


def current_disruptions(board, messages, history, now_iso):
    """The live disruption as a one-item list for helper.update_history, or
    an empty list. It keeps the id of a disruption that hasn't ended yet, so a
    closure stays one feed entry however many runs it spans."""
    if not replacement_buses_only(board):
        return []
    ongoing = next((r for r in history if not r.get("resolved_iso")), None)
    disruption_id = ongoing["disruption_id"] if ongoing else f"rail-replacement-{now_iso[:10]}"
    return [{"disruption_id": disruption_id, "message": disruption_message(messages)}]


def build_alert_html(active):
    if not active:
        return ""
    return (
        "<h2>Rail Disruption Alert</h2>\n"
        "<ul>\n"
        f'  <li><a href="{PAGE_PATH}">No trains at Cheltenham Spa: rail replacement buses are running</a></li>\n'
        "</ul>"
    )


def build_atom_items(history, page_url):
    """One entry per disruption, dated when it started and again when it
    ended, so a feed reader sees each change once rather than every run."""
    items = []
    for record in history[:50]:
        ended = record.get("resolved_iso")
        title = "Rail replacement buses at Cheltenham Spa"
        items.append({
            "title": f"{title}, now ended" if ended else title,
            "link": f"{page_url}#{record['disruption_id']}",
            "summary": record.get("message") or DEFAULT_DISRUPTION_MESSAGE,
            "published_iso": ended or record.get("first_seen_iso"),
            "source": "National Rail Enquiries",
        })
    return items


def record_disruptions(board, messages):
    """Update the disruption history, its Atom feed, the homepage alert and
    the combined alerts feed."""
    try:
        history = json.loads(HISTORY.read_text()).get("records", [])
    except (OSError, ValueError):
        history = []
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    active = current_disruptions(board, messages, history, now_iso)
    history = helper.update_history(history, active, id_key="disruption_id", now_iso=now_iso,
                                    retention_days=HISTORY_RETENTION_DAYS)
    helper.write_json(HISTORY, {
        "note": "Days when only rail replacement buses served Cheltenham Spa, recorded as they happen.",
        "source": "National Rail Enquiries, via the Rail Data Marketplace",
        "source_url": "https://raildata.org.uk/",
        "refresh": "every 5 minutes",
        "count": len(history),
        "records": history,
    })

    site = helper.site_url()
    helper.write_items_atom(
        items=build_atom_items(history, f"{site}{PAGE_PATH}"),
        filename=FEED,
        permalink_path="/feeds/rail-disruptions.xml",
        feed_title="Cheltenham Rail Disruptions",
        feed_subtitle="Days when rail replacement buses run instead of trains at Cheltenham Spa",
        self_url=f"{site}/feeds/rail-disruptions.xml",
        alternate_url=f"{site}{PAGE_PATH}",
    )

    include = ALERT_INCLUDE.read_text()
    ALERT_INCLUDE.write_text(helper.replace_chunk(include, "rail_alert_marker", build_alert_html(active)))
    alerts_feed.rebuild()


def main():
    api_key = os.getenv("RDM_LDBWS_KEY") or ""
    if not api_key:
        sys.exit("Error: RDM_LDBWS_KEY environment variable is required")

    board = fetch_board(api_key)

    now = datetime.now(LONDON)
    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "source":       "National Rail Enquiries, via the Rail Data Marketplace",
        "source_url":   "https://raildata.org.uk/",
        "refresh":      "every 5 minutes",
        "licence":      "Rail Data Marketplace licence",
        "station":      {"name": STATION_NAME, "crs": CRS},
        "messages":     station_messages(board),
        "departures":   parse_board(board, "departure"),
        "arrivals":     parse_board(board, "arrival"),
        "replacement_buses_only": replacement_buses_only(board),
    }

    record_disruptions(board, output["messages"])

    if unchanged(output, now):
        print("No change since the last run; leaving _data/rail-times.json alone")
        return

    helper.write_json(OUT, output)
    print(f"Wrote {len(output['departures'])} departures and {len(output['arrivals'])} arrivals to {OUT}")


if __name__ == "__main__":
    main()
