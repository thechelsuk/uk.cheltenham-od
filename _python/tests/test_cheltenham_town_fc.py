"""Offline tests for the Cheltenham Town FC fixtures fetcher
(cheltenham-town-fc.py). TheSportsDB calls are replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import helper

SPEC = importlib.util.spec_from_file_location(
    "cheltenham_town_fc", pathlib.Path(__file__).resolve().parents[1] / "cheltenham-town-fc.py"
)
assert SPEC is not None and SPEC.loader is not None
fc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fc)

HOME = {"strHomeTeam": "Cheltenham Town", "strAwayTeam": "Walsall", "strTimestamp": "2026-08-15T14:00:00",
        "dateEvent": "2026-08-15", "strVenue": "Whaddon Road", "strLeague": "English League Two",
        "intHomeScore": "2", "intAwayScore": "1"}
AWAY = {"strHomeTeam": "Swindon Town", "strAwayTeam": "Cheltenham Town", "dateEvent": "2026-12-26",
        "strTime": "15:00:00", "strVenue": "County Ground", "strLeague": "English League Two"}


def test_kickoff_turns_utc_into_uk_time():
    assert fc.kickoff(HOME) == "2026-08-15T15:00:00+01:00"
    assert fc.kickoff(AWAY) == "2026-12-26T15:00:00+00:00"
    assert fc.kickoff({"dateEvent": "2026-12-26"}) == ""


def test_fixture_names_the_opponent_from_cheltenhams_side():
    assert fc.fixture(HOME) == {"date": "2026-08-15", "kickoff": "2026-08-15T15:00:00+01:00",
                                "opponent": "Walsall", "venue_type": "Home", "venue": "Whaddon Road",
                                "competition": "English League Two"}
    assert fc.fixture(AWAY)["opponent"] == "Swindon Town"
    assert fc.fixture(AWAY)["venue_type"] == "Away"
    assert fc.fixture({"dateEvent": "2027-01-01"})["date"] == "2027-01-01"


def test_result_adds_the_scores():
    row = fc.result(HOME)
    assert (row["home_score"], row["away_score"]) == ("2", "1")


def test_main_writes_team_fixtures_and_results(monkeypatch):
    answers = {
        "searchteams.php": {"teams": [{"strTeam": "Cheltenham Town", "strWebsite": "www.ctfc.com",
                                       "strBadge": "badge.png", "strLeague": "English League Two"}]},
        "eventsnext.php": {"events": [AWAY]},
        "eventslast.php": {"results": None},
    }
    monkeypatch.setattr(fc, "get", lambda path, **params: answers[path])
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    fc.main()
    payload = written["payload"]
    assert payload["team"]["website"] == "https://www.ctfc.com"
    assert [f["opponent"] for f in payload["next_fixtures"]] == ["Swindon Town"]
    assert payload["last_results"] == []


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"ok": True}


def test_get_calls_the_sportsdb_api(monkeypatch):
    seen = {}
    monkeypatch.setattr(fc.requests, "get", lambda url, params, headers, timeout: seen.update(url=url, params=params)
                        or FakeResponse())
    assert fc.get("eventsnext.php", id="1") == {"ok": True}
    assert seen == {"url": f"{fc.API}/eventsnext.php", "params": {"id": "1"}}
