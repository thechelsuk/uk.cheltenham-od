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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

# Load .env file for local development / the Pi if present
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

BASE_URL = "https://api1.raildata.org.uk/1010-live-arrival-and-departure-boards-arr-and-dep1_1/LDBWS/api/20220120"
BOARD_METHOD = "GetArrDepBoardWithDetails"

STATION_NAME = "Cheltenham Spa"
CRS = "CNM"
NUM_ROWS = 10           # rows requested from the API
MAX_SERVICES = 10       # rows kept per board
HEARTBEAT_MINUTES = 30  # see module docstring

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
    generated = board_time(board)
    services = [parse_service(s, kind, generated) for s in board.get("trainServices") or []]
    services = sorted((s for s in services if s), key=lambda s: s["scheduled"])
    return services[:MAX_SERVICES]


def station_messages(board):
    messages = []
    for message in board.get("nrccMessages") or []:
        text = clean_text(message.get("value"))
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
    if any(old.get(k) != new[k] for k in ("messages", "departures", "arrivals")):
        return False
    return age < timedelta(minutes=HEARTBEAT_MINUTES)


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
        "licence":      "Rail Data Marketplace Live Arrival and Departure Boards licence (OGL3-based; per-product Schedule 1 terms apply)",
        "station":      {"name": STATION_NAME, "crs": CRS},
        "messages":     station_messages(board),
        "departures":   parse_board(board, "departure"),
        "arrivals":     parse_board(board, "arrival"),
    }

    if unchanged(output, now):
        print("No change since the last run; leaving _data/rail-times.json alone")
        return

    helper.write_json(OUT, output)
    print(f"Wrote {len(output['departures'])} departures and {len(output['arrivals'])} arrivals to {OUT}")


if __name__ == "__main__":
    main()
