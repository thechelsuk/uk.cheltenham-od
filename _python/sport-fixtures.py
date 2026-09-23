#!/usr/bin/env python3
"""Fetch upcoming fixtures for local sports teams from BBC Sport's public
JSON feed, write _data/sport-fixtures.json.

Covers football (Cheltenham Town, Forest Green Rovers, Cheltenham Town
Women), rugby union (Gloucester Rugby) and cricket (Gloucestershire), looking
ahead 7 days from today. Football is fetched a tournament at a time (BBC
groups it into leagues, so we only pull the leagues our teams could be in,
same as before); rugby union and cricket have no equivalent "collated"
collection, so those are fetched sport-wide instead and filtered by team
name after the fact.

This is a plain daily snapshot, not a history log: every run replaces
_data/sport-fixtures.json wholesale with whatever BBC reports as upcoming
over the window, in the shape event-roundup.py's newsletter step expects
(one flat, date-ordered fixtures list, RSS-feed style) — there's no id/merge
bookkeeping to preserve across runs.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests

import config

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "sport-fixtures.json")

BASE_URL = "https://web-cdn.api.bbci.co.uk/wc-poll-data/container/sport-data-scores-fixtures"
HEADERS = {**config.HEADERS, "Accept": "application/json"}
REQUEST_DELAY_SECONDS = 0.6
LOOKAHEAD_DAYS = 7  # today + the next 6 days
NOT_STARTED_STATUS = "PreEvent"

# Football is scoped to these leagues (BBC's tournament-collection groups
# fixtures by league, so we only fetch the ones our teams could appear in),
# then filtered down to the tracked teams below.
FOOTBALL_URN = "urn:bbc:sportsdata:football:tournament-collection:collated"
FOOTBALL_LEAGUES = {"League One", "League Two", "National League",
                     "Women's Super League", "English WSL 2", "FA Women's National League Division One South West"}

# Rugby union and cricket have no per-league "collated" collection on BBC's
# feed, so these fetch every tournament in the sport and get filtered by
# team name below instead of by league.
RUGBY_URN = "urn:bbc:sportsdata:rugby-union"
CRICKET_URN = "urn:bbc:sportsdata:cricket"

TRACKED_TEAMS = {
    "football": {"Cheltenham Town", "Forest Green Rovers", "Cheltenham Town Women"},
    "rugby-union": {"Gloucester"},
    "cricket": {"Gloucestershire"},
}


def daterange(start, end):
    for n in range((end - start).days + 1):
        yield start + timedelta(days=n)


def fetch(urn, day, today):
    params = {"selectedStartDate": day.isoformat(), "selectedEndDate": day.isoformat(),
              "todayDate": today.isoformat(), "urn": urn}
    r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_football_event(competition, event):
    if event.get("status") != NOT_STARTED_STATUS:
        return None
    try:
        home, away, d = event["home"], event["away"], event["date"]
        home_name = home["name"]["fullName"] if "name" in home else home["fullName"]
        away_name = away["name"]["fullName"] if "name" in away else away["fullName"]
        return {
            "sport": "football", "competition": competition,
            "home": home_name, "away": away_name,
            "date": d["isoDate"], "end_date": None, "time": d.get("time"),
            "venue": event.get("venue", {}).get("name", ""),
        }
    except (KeyError, TypeError):
        return None


def fetch_football(today, end):
    events = []
    for day in daterange(today, end):
        try:
            payload = fetch(FOOTBALL_URN, day, today)
        except requests.RequestException as exc:
            print(f"  ! football {day}: request failed ({exc})")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        for group in payload.get("eventGroups", []):
            competition = (group.get("displayLabel") or "").strip()
            if competition not in FOOTBALL_LEAGUES:
                continue
            for sub in group.get("secondaryGroups", []):
                for event in sub.get("events", []):
                    rec = parse_football_event(competition, event)
                    if rec:
                        events.append(rec)
        time.sleep(REQUEST_DELAY_SECONDS)
    return events


def parse_rugby_event(competition, event):
    if event.get("status") != NOT_STARTED_STATUS:
        return None
    try:
        home, away = event["home"], event["away"]
        start = event["startDateTime"]
        return {
            "sport": "rugby-union", "competition": competition,
            "home": home["fullName"], "away": away["fullName"],
            "date": start[:10], "end_date": None,
            "time": event.get("time", {}).get("displayTimeUK"),
            "venue": event.get("venue", {}).get("name", ""),
        }
    except (KeyError, TypeError):
        return None


def fetch_rugby(today, end):
    events = []
    for day in daterange(today, end):
        try:
            payload = fetch(RUGBY_URN, day, today)
        except requests.RequestException as exc:
            print(f"  ! rugby {day}: request failed ({exc})")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        for group in payload.get("eventGroups", []):
            competition = (group.get("displayLabel") or "").strip()
            for sub in group.get("secondaryGroups", []):
                for event in sub.get("events", []):
                    rec = parse_rugby_event(competition, event)
                    if rec:
                        events.append(rec)
        time.sleep(REQUEST_DELAY_SECONDS)
    return events


def parse_cricket_event(competition, event):
    if event.get("status") != NOT_STARTED_STATUS:
        return None
    try:
        participants = event["participants"]
        home, away = participants["homeTeam"], participants["awayTeam"]
        summary = event.get("matchDateSummary", {})
        return {
            "sport": "cricket", "competition": competition,
            "home": home["name"], "away": away["name"],
            "date": summary.get("startDate"), "end_date": summary.get("endDate"),
            "time": event.get("startTime"),
            "venue": event.get("groundName", ""),
        }
    except (KeyError, TypeError):
        return None


def fetch_cricket(today, end):
    events = []
    for day in daterange(today, end):
        try:
            payload = fetch(CRICKET_URN, day, today)
        except requests.RequestException as exc:
            print(f"  ! cricket {day}: request failed ({exc})")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue
        for group in payload.get("eventGroups", []):
            for sub in group.get("secondaryGroups", []):
                for event in sub.get("events", []):
                    competition = event.get("tournamentName") or (sub.get("displayLabel") or "").strip()
                    rec = parse_cricket_event(competition, event)
                    if rec:
                        events.append(rec)
        time.sleep(REQUEST_DELAY_SECONDS)
    return events


def filter_and_tag(events, sport):
    """Keeps only events involving a tracked team for this sport, tagging
    each with which tracked team it is and that team's home/away status."""
    tracked = TRACKED_TEAMS[sport]
    kept = []
    for rec in events:
        if rec["home"] in tracked:
            team, opponent, home_away = rec["home"], rec["away"], "Home"
        elif rec["away"] in tracked:
            team, opponent, home_away = rec["away"], rec["home"], "Away"
        else:
            continue
        kept.append({**rec, "team": team, "opponent": opponent, "home_away": home_away})
    return kept


def main():
    today = date.today()
    end = today + timedelta(days=LOOKAHEAD_DAYS - 1)

    print(f"Fetching fixtures {today} to {end}...")
    football = filter_and_tag(fetch_football(today, end), "football")
    rugby = filter_and_tag(fetch_rugby(today, end), "rugby-union")
    cricket = filter_and_tag(fetch_cricket(today, end), "cricket")

    fixtures = sorted(football + rugby + cricket, key=lambda r: (r["date"], r["time"] or "", r["team"]))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "BBC Sport",
        "source_url": "https://www.bbc.co.uk/sport",
        "lookahead_days": LOOKAHEAD_DAYS,
        "window_start": today.isoformat(),
        "window_end": end.isoformat(),
        "fixtures": fixtures,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(fixtures)} fixture(s) ({len(football)} football, "
          f"{len(rugby)} rugby, {len(cricket)} cricket) to {OUT}")


if __name__ == "__main__":
    main()
