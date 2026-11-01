#!/usr/bin/env python3
"""Cheltenham Town FC's next three fixtures and last three results in every
competition, written to _data/cheltenham-town-fc.json for the club page.

Runs four times a day (refresh-4-times-daily.yml), after ctfc-results.py.

The matches come from FotMob's public team calendar (an iCalendar feed that
fans subscribe to, refreshed every six hours), which covers the league, the
FA Cup, the EFL Cup and the EFL Trophy, with kick-off times, venues and
scores. If the calendar can't be read, the page falls back to league matches
only: the coming round from Football-Data.co.uk's fixtures.csv and results
from the current season's _data/ctfc-seasons/ file, and the run says so.

This replaced TheSportsDB in November 2026, after its free API key was
switched off and the page silently stopped updating.
"""
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import helper

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_data" / "cheltenham-town-fc.json"
SEASONS_DIR = ROOT / "_data" / "ctfc-seasons"
CLUBS_FILE = ROOT / "_data" / "ctfc-clubs.json"
LOCAL_FIXTURES = ROOT / "_data-sources" / "football" / "fixtures.csv"

TEAM_NAME = "Cheltenham Town"
CALENDAR_URL = "https://pub.fotmob.com/prod/pub/api/v2/calendar/team/8680.ics"
CALENDAR_SOURCE = "FotMob"
CALENDAR_SOURCE_URL = "https://www.fotmob.com/teams/8680/overview/cheltenham-town"
FIXTURES_URL = "https://football-data.co.uk/fixtures.csv"
LEAGUE_SOURCE = "Football-Data.co.uk"
LEAGUE_SOURCE_URL = "https://football-data.co.uk/englandm.php"
WEBSITE = "https://www.ctfc.com"
COUNT = 3
UK = ZoneInfo("Europe/London")

_spec = importlib.util.spec_from_file_location("ctfc_results", Path(__file__).resolve().parent / "ctfc-results.py")
assert _spec is not None and _spec.loader is not None
ctfc = importlib.util.module_from_spec(_spec)
sys.modules["ctfc_results"] = ctfc
_spec.loader.exec_module(ctfc)


def now():
    return datetime.now(timezone.utc)


# --- FotMob calendar ---

def calendar_events(text):
    """Each VEVENT as a dict of its properties, with folded lines joined and iCalendar escapes undone."""
    text = re.sub(r"\r?\n[ \t]", "", text)
    # Each match carries a reminder alarm with its own SUMMARY and DESCRIPTION; drop it so it can't overwrite the match's.
    text = re.sub(r"BEGIN:VALARM.*?END:VALARM\r?\n?", "", text, flags=re.S)
    events = []
    for block in text.split("BEGIN:VEVENT")[1:]:
        props = {}
        for line in block.split("END:VEVENT")[0].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
            props[key.split(";")[0]] = value.strip()
        events.append(props)
    return events


SUMMARY = re.compile(r"^\W*(?P<home>.+?) - (?P<away>.+?)(?:\s+\((?P<hs>\d+)-(?P<as>\d+)\))?\s*$")


def calendar_matches(text):
    """Cheltenham's matches from the calendar, from their side, with scores (home team first) once played."""
    out = []
    for e in calendar_events(text):
        m = SUMMARY.match(e.get("SUMMARY", ""))
        if not m or TEAM_NAME not in (m["home"], m["away"]):
            continue
        start = datetime.strptime(e["DTSTART"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(UK)
        url, _, competition = e.get("DESCRIPTION", "").partition("\n")
        is_home = m["home"] == TEAM_NAME
        match = {"date": start.date().isoformat(), "kickoff": start.isoformat(),
                 "opponent": m["away"] if is_home else m["home"], "venue_type": "Home" if is_home else "Away",
                 "venue": e.get("LOCATION", "").split(",")[0].strip(), "competition": competition.strip(),
                 "url": url.strip()}
        if m["hs"] is not None:
            match["home_score"], match["away_score"] = m["hs"], m["as"]
        out.append(match)
    return out


def split(matches, at, count):
    """The next `count` unplayed matches, soonest first, and the last `count` results, newest first.
    A past match with no score (postponed or abandoned) is left out of both."""
    upcoming = sorted((m for m in matches if "home_score" not in m and m["kickoff"] >= at.astimezone(UK).isoformat()),
                      key=lambda m: m["kickoff"])
    played = sorted((m for m in matches if "home_score" in m), key=lambda m: m["kickoff"], reverse=True)
    return upcoming[:count], played[:count]


def fetch_calendar():
    resp = helper.get(CALENDAR_URL, timeout=60)
    resp.raise_for_status()
    return resp.content.decode("utf-8")


# --- Football-Data fallback: league matches only ---

def uk_kickoff(day, time):
    """'2026-08-15', '15:00' -> '2026-08-15T15:00:00+01:00' (UK time), or '' when the time isn't known."""
    if not time:
        return ""
    return datetime.fromisoformat(f"{day}T{time}").replace(tzinfo=UK).isoformat()


def league_fixtures(rows, clubs, on_or_after):
    """Cheltenham's matches in Football-Data's fixtures file that haven't been played yet, soonest first."""
    out = []
    for r in rows:
        home, away = r["HomeTeam"].strip(), r["AwayTeam"].strip()
        if ctfc.TEAM not in (home, away):
            continue
        day = ctfc.iso_date(r["Date"])
        if day < on_or_after.isoformat():
            continue
        is_home = home == ctfc.TEAM
        division = r["Div"].strip()
        out.append({"date": day, "kickoff": uk_kickoff(day, (r.get("Time") or "").strip()),
                    "opponent": ctfc.club(away if is_home else home, division, clubs)["name"],
                    "venue_type": "Home" if is_home else "Away", "venue": "",
                    "competition": ctfc.NEW_NAMES.get(division, division)})
    return sorted(out, key=lambda f: f["kickoff"] or f["date"])


def league_results(season, count):
    """The latest league results from a season file, newest first, scores home team first."""
    out = []
    for m in sorted(season.get("matches", []), key=lambda m: m["date"], reverse=True)[:count]:
        home = m["venue"] == "H"
        out.append({"date": m["date"], "kickoff": "", "opponent": m["opponent"],
                    "venue_type": "Home" if home else "Away", "venue": "",
                    "competition": season.get("division", ""),
                    "home_score": str(m["gf"] if home else m["ga"]), "away_score": str(m["ga"] if home else m["gf"])})
    return out


def fetch_fixtures():
    resp = helper.get(FIXTURES_URL, timeout=60)
    resp.raise_for_status()
    LOCAL_FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FIXTURES.write_bytes(resp.content)
    return ctfc.read_rows(LOCAL_FIXTURES)


def load_clubs():
    return json.loads(CLUBS_FILE.read_text()).get("clubs", {})


def current_season():
    files = sorted(SEASONS_DIR.glob("*.json"))
    return json.loads(files[-1].read_text()) if files else {}


def main():
    season = current_season()
    try:
        upcoming, played = split(calendar_matches(fetch_calendar()), now(), COUNT)
        source, source_url = CALENDAR_SOURCE, CALENDAR_SOURCE_URL
    except Exception as err:  # pylint: disable=broad-exception-caught
        # Say so in the run log, then show league matches rather than nothing.
        print(f"::warning::FotMob calendar unavailable ({err}); falling back to Football-Data league matches")
        upcoming = league_fixtures(fetch_fixtures(), load_clubs(), now().astimezone(UK).date())[:COUNT]
        played = league_results(season, COUNT)
        source, source_url = LEAGUE_SOURCE, LEAGUE_SOURCE_URL
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "source_url": source_url,
        "team": {"name": TEAM_NAME, "website": WEBSITE, "league": season.get("division", "")},
        "next_fixtures": upcoming,
        "last_results": played,
    }
    helper.write_json(OUT, output)
    print(f"Wrote {len(upcoming)} next fixture(s) and {len(played)} recent result(s) from {source} to {OUT}")


if __name__ == "__main__":
    main()
