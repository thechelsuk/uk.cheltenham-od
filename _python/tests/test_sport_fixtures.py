"""Offline tests for the BBC Sport fixtures fetcher (sport-fixtures.py): the
football, rugby and cricket event parsers, the tracked-team filter and the
day-by-day fetch loops. The BBC feed is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
from datetime import date

import requests

import helper

SPEC = importlib.util.spec_from_file_location(
    "sport_fixtures", pathlib.Path(__file__).resolve().parents[1] / "sport-fixtures.py"
)
assert SPEC is not None and SPEC.loader is not None
sport = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sport)

FOOTBALL = {"status": "PreEvent", "home": {"name": {"fullName": "Cheltenham Town"}},
            "away": {"fullName": "Walsall"}, "date": {"isoDate": "2026-10-17", "time": "15:00"},
            "venue": {"name": "Whaddon Road"}}
RUGBY = {"status": "PreEvent", "home": {"fullName": "Bath"}, "away": {"fullName": "Gloucester"},
         "startDateTime": "2026-10-18T15:00:00Z", "time": {"displayTimeUK": "15:00"}}
CRICKET = {"status": "PreEvent", "tournamentName": "County Championship",
           "participants": {"homeTeam": {"name": "Gloucestershire"}, "awayTeam": {"name": "Kent"}},
           "matchDateSummary": {"startDate": "2026-10-13", "endDate": "2026-10-16"},
           "startTime": "10:30", "groundName": "Bristol"}


def test_daterange_includes_both_ends():
    assert list(sport.daterange(date(2026, 10, 12), date(2026, 10, 14))) == [
        date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]


def test_parse_football_event_reads_either_name_shape():
    assert sport.parse_football_event("League Two", FOOTBALL) == {
        "sport": "football", "competition": "League Two", "home": "Cheltenham Town", "away": "Walsall",
        "date": "2026-10-17", "end_date": None, "time": "15:00", "venue": "Whaddon Road"}
    assert sport.parse_football_event("League Two", {**FOOTBALL, "status": "PostEvent"}) is None
    assert sport.parse_football_event("League Two", {"status": "PreEvent", "home": None}) is None


def test_parse_rugby_event():
    assert sport.parse_rugby_event("Premiership", RUGBY) == {
        "sport": "rugby-union", "competition": "Premiership", "home": "Bath", "away": "Gloucester",
        "date": "2026-10-18", "end_date": None, "time": "15:00", "venue": ""}
    assert sport.parse_rugby_event("Premiership", {"status": "PreEvent"}) is None


def test_parse_cricket_event():
    assert sport.parse_cricket_event("County Championship", CRICKET) == {
        "sport": "cricket", "competition": "County Championship", "home": "Gloucestershire", "away": "Kent",
        "date": "2026-10-13", "end_date": "2026-10-16", "time": "10:30", "venue": "Bristol"}
    assert sport.parse_cricket_event("x", {"status": "PreEvent", "participants": {}}) is None
    assert sport.parse_cricket_event("x", {"status": "Live"}) is None


def test_filter_and_tag_keeps_tracked_teams_home_or_away():
    events = [sport.parse_rugby_event("P", RUGBY), {**sport.parse_rugby_event("P", RUGBY), "away": "Sale"}]
    assert sport.filter_and_tag(events, "rugby-union") == [
        {**events[0], "team": "Gloucester", "opponent": "Bath", "home_away": "Away"}]
    football = sport.parse_football_event("League Two", FOOTBALL)
    assert sport.filter_and_tag([football], "football")[0]["home_away"] == "Home"


def payload(group_label, events, sub_label=""):
    return {"eventGroups": [{"displayLabel": group_label,
                             "secondaryGroups": [{"displayLabel": sub_label, "events": events}]}]}


def fake_fetch(answers):
    """sport.fetch replacement: answers[day] is a payload or an exception."""
    def fetch(urn, day, today):
        answer = answers.get(day, {})
        if isinstance(answer, Exception):
            raise answer
        return answer
    return fetch


def test_fetch_football_only_reads_tracked_leagues_and_skips_failed_days(monkeypatch):
    monkeypatch.setattr(sport.time, "sleep", lambda s: None)
    day1, day2, day3 = date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)
    monkeypatch.setattr(sport, "fetch", fake_fetch({
        day1: payload(" League Two ", [FOOTBALL, {"status": "PostEvent"}]),
        day2: requests.ConnectionError("down"),
        day3: payload("Premier League", [FOOTBALL]),
    }))
    assert [e["home"] for e in sport.fetch_football(day1, day3)] == ["Cheltenham Town"]


def test_fetch_rugby_and_cricket(monkeypatch):
    monkeypatch.setattr(sport.time, "sleep", lambda s: None)
    day1, day2 = date(2026, 10, 12), date(2026, 10, 13)
    monkeypatch.setattr(sport, "fetch", fake_fetch({day1: payload("Premiership", [RUGBY]),
                                                    day2: requests.Timeout("slow")}))
    assert [e["competition"] for e in sport.fetch_rugby(day1, day2)] == ["Premiership"]

    no_name = {**CRICKET, "tournamentName": None}
    monkeypatch.setattr(sport, "fetch", fake_fetch({day1: payload("", [CRICKET, no_name], sub_label=" T20 Blast "),
                                                    day2: requests.Timeout("slow")}))
    assert [e["competition"] for e in sport.fetch_cricket(day1, day2)] == ["County Championship", "T20 Blast"]


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"eventGroups": []}


def test_fetch_asks_for_a_single_day(monkeypatch):
    seen = {}
    monkeypatch.setattr(helper, "get",
                        lambda url, params, headers, timeout: seen.update(params) or FakeResponse())
    sport.fetch("urn:x", date(2026, 10, 13), date(2026, 10, 12))
    assert seen == {"selectedStartDate": "2026-10-13", "selectedEndDate": "2026-10-13",
                    "todayDate": "2026-10-12", "urn": "urn:x"}


def test_main_writes_tracked_fixtures_in_date_order(monkeypatch):
    football = sport.parse_football_event("League Two", FOOTBALL)
    rugby = sport.parse_rugby_event("Premiership", RUGBY)
    cricket = sport.parse_cricket_event("County Championship", CRICKET)
    monkeypatch.setattr(sport, "fetch_football", lambda today, end: [football])
    monkeypatch.setattr(sport, "fetch_rugby", lambda today, end: [rugby])
    monkeypatch.setattr(sport, "fetch_cricket", lambda today, end: [cricket, {**cricket, "home": "Kent", "away": "Surrey"}])
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    sport.main()
    fixtures = written["payload"]["fixtures"]
    assert [(f["date"], f["team"]) for f in fixtures] == [
        ("2026-10-13", "Gloucestershire"), ("2026-10-17", "Cheltenham Town"), ("2026-10-18", "Gloucester")]
    assert written["payload"]["lookahead_days"] == 7
