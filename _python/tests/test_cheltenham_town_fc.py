"""Offline tests for the Cheltenham Town FC fixtures fetcher
(cheltenham-town-fc.py): reading FotMob's team calendar for the next and last
three matches in every competition, and falling back to Football-Data.co.uk's
league fixtures and results when the calendar can't be read.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import date, datetime, timezone

import helper

SPEC = importlib.util.spec_from_file_location(
    "cheltenham_town_fc", pathlib.Path(__file__).resolve().parents[1] / "cheltenham-town-fc.py"
)
assert SPEC is not None and SPEC.loader is not None
fc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fc)

ICS = (
    "BEGIN:VCALENDAR\r\nX-WR-CALNAME:Cheltenham Town\r\n"
    "BEGIN:VEVENT\r\nDESCRIPTION:https://www.fotmob.com/match/1\\nLeague Two\r\nDTSTART:20261031T150000Z\r\n"
    "LOCATION:Prenton Park\r\nSUMMARY:⚽️ Tranmere Rovers - Cheltenham Town  (3-1)\r\n"
    "BEGIN:VALARM\r\nACTION:DISPLAY\r\nDESCRIPTION:⚽️ Tranmere Rovers - Cheltenham Town starting in 15 minutes. Noti\r\n"
    " fications can be turned off\r\nSUMMARY:⚽️ Tranmere Rovers - Cheltenham Town starting in 15 minutes\r\n"
    "TRIGGER:-PT15M\r\nEND:VALARM\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nDESCRIPTION:https://www.fotmob.com/match/2\\nFA Cup\r\nDTSTART:20261107T150000Z\r\n"
    "LOCATION:EV Charger Points Stadium\\, Whaddon Road\\, Cheltenham\\, Glouceste\r\n rshire\\, ENG\r\n"
    "SUMMARY:⚽️ Cheltenham Town - FC Halifax Town\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nDESCRIPTION:https://www.fotmob.com/match/3\\nLeague Two\r\nDTSTART:20260815T140000Z\r\n"
    "LOCATION:EV Charger Points Stadium\r\nSUMMARY:⚽️ Cheltenham Town - Rotherham United  (2-1)\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nDESCRIPTION:https://www.fotmob.com/match/4\\nLeague Two\r\nDTSTART:20261024T113000Z\r\n"
    "LOCATION:Somewhere\r\nSUMMARY:⚽️ Cheltenham Town - Postponed FC\r\nEND:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def test_calendar_events_are_unfolded_and_unescaped():
    events = fc.calendar_events(ICS)
    halifax = next(e for e in events if "Halifax" in e["SUMMARY"])
    assert halifax["LOCATION"] == "EV Charger Points Stadium, Whaddon Road, Cheltenham, Gloucestershire, ENG"
    assert halifax["DESCRIPTION"] == "https://www.fotmob.com/match/2\nFA Cup"


def test_matches_from_cheltenhams_side():
    matches = fc.calendar_matches(ICS)
    tranmere = next(m for m in matches if m["opponent"] == "Tranmere Rovers")
    assert tranmere == {"date": "2026-10-31", "kickoff": "2026-10-31T15:00:00+00:00", "opponent": "Tranmere Rovers",
                        "venue_type": "Away", "venue": "Prenton Park", "competition": "League Two",
                        "url": "https://www.fotmob.com/match/1", "home_score": "3", "away_score": "1"}
    halifax = next(m for m in matches if m["opponent"] == "FC Halifax Town")
    assert halifax["venue"] == "EV Charger Points Stadium" and halifax["venue_type"] == "Home"
    assert "home_score" not in halifax and halifax["competition"] == "FA Cup"
    rotherham = next(m for m in matches if m["opponent"] == "Rotherham United")
    assert rotherham["kickoff"] == "2026-08-15T15:00:00+01:00"  # summer kick-offs in UK time


def test_split_next_and_last_skips_past_games_with_no_score():
    upcoming, played = fc.split(fc.calendar_matches(ICS), NOW, 3)
    assert [m["opponent"] for m in upcoming] == ["FC Halifax Town"]
    assert [m["opponent"] for m in played] == ["Tranmere Rovers", "Rotherham United"]


def test_main_uses_the_calendar(monkeypatch):
    monkeypatch.setattr(fc, "fetch_calendar", lambda: ICS)
    monkeypatch.setattr(fc, "now", lambda: NOW)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(payload=payload))
    fc.main()
    payload = written["payload"]
    assert payload["source"] == "FotMob"
    assert [f["opponent"] for f in payload["next_fixtures"]] == ["FC Halifax Town"]
    assert payload["last_results"][0]["opponent"] == "Tranmere Rovers"


def test_main_falls_back_to_football_data_when_the_calendar_fails(monkeypatch, tmp_path):
    def broken():
        raise RuntimeError("calendar down")
    seasons = tmp_path / "seasons"
    seasons.mkdir()
    (seasons / "2026-27.json").write_text(json.dumps({"division": "League Two", "matches": [
        {"date": "2026-10-24", "venue": "H", "opponent": "Newport County", "gf": 1, "ga": 0}]}))
    monkeypatch.setattr(fc, "fetch_calendar", broken)
    monkeypatch.setattr(fc, "SEASONS_DIR", seasons)
    monkeypatch.setattr(fc, "fetch_fixtures", lambda: [
        {"Div": "E3", "Date": "14/11/2026", "Time": "12:30", "HomeTeam": "Exeter", "AwayTeam": "Cheltenham"}])
    monkeypatch.setattr(fc, "load_clubs", lambda: {"Exeter": {"name": "Exeter City"}})
    monkeypatch.setattr(fc, "now", lambda: NOW)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(payload=payload))
    fc.main()
    payload = written["payload"]
    assert payload["source"] == "Football-Data.co.uk"
    assert [f["opponent"] for f in payload["next_fixtures"]] == ["Exeter City"]
    assert payload["last_results"][0] == {"date": "2026-10-24", "kickoff": "", "opponent": "Newport County",
                                          "venue_type": "Home", "venue": "", "competition": "League Two",
                                          "home_score": "1", "away_score": "0"}


def test_kickoff_from_football_data_is_uk_time():
    assert fc.uk_kickoff("2026-08-15", "15:00") == "2026-08-15T15:00:00+01:00"
    assert fc.uk_kickoff("2026-12-26", "") == ""


def test_league_fixtures_skip_played_matches():
    rows = [{"Div": "E3", "Date": "31/10/2026", "Time": "15:00", "HomeTeam": "Tranmere", "AwayTeam": "Cheltenham"}]
    assert fc.league_fixtures(rows, {}, date(2026, 11, 1)) == []
