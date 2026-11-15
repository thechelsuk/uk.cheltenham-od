"""Offline tests for ward-politics.py: election results already saved are
reused (they never change), so only a new election is scraped.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "ward_politics", pathlib.Path(__file__).resolve().parents[1] / "ward-politics.py")
assert SPEC is not None and SPEC.loader is not None
wp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wp)


def result(date, title, party="Liberal Democrats"):
    return {"date": date, "title": title, "seats": 1, "electorate": 100, "electorate_display": "100",
            "ballots_cast": 40, "ballots_cast_display": "40", "turnout_pct": 40.0, "spoilt": 0, "total_votes": 40,
            "source_url": "https://democracy.example/ward", "candidates": [
                {"name": "A Person", "party": party, "votes": 40, "votes_display": "40", "share": 100.0,
                 "elected": True}]}


@pytest.fixture
def saved(tmp_path, monkeypatch):
    out = tmp_path / "ward-politics.json"
    out.write_text(json.dumps({"wards": {"all-saints": {"elections": [
        result("2025-05-01", "2025 By-election"), result("2024-05-02", "2024 Borough Election")]}}}))
    monkeypatch.setattr(wp, "OUT", str(out))
    monkeypatch.setattr(wp, "ELECTIONS", [
        {"id": 21, "date": "2024-05-02", "title": "2024 Borough Election"},
        {"id": 23, "date": "2025-05-01", "title": "2025 By-election"},
        {"id": 24, "date": "2026-05-07", "title": "2026 Borough Election"}])
    monkeypatch.setattr(wp, "fetch_councillors", lambda: {})
    written = {}
    monkeypatch.setattr(wp.helper, "write_json", lambda path, payload: written.update(payload))
    return written


def test_saved_results_are_read_back_by_election_date(saved):
    results = wp.saved_results(wp.OUT)
    assert sorted(results) == ["2024-05-02", "2025-05-01"]
    assert results["2024-05-02"]["all-saints"]["title"] == "2024 Borough Election"


def test_only_an_election_not_yet_saved_is_scraped(saved, monkeypatch):
    fetched = []

    def fake_fetch(election):
        fetched.append(election["id"])
        return {"all-saints": result(election["date"], election["title"])}
    monkeypatch.setattr(wp, "fetch_election", fake_fetch)
    wp.main()
    assert fetched == [24]
    assert [e["date"] for e in saved["wards"]["all-saints"]["elections"]] == ["2026-05-07", "2025-05-01", "2024-05-02"]


def test_a_missing_or_empty_file_scrapes_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(wp, "OUT", str(tmp_path / "none.json"))
    assert wp.saved_results(wp.OUT) == {}
