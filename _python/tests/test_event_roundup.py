"""Offline tests for local/event-roundup.py's local JSON sources.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import sys
from datetime import date

SPEC = importlib.util.spec_from_file_location(
    "event_roundup", pathlib.Path(__file__).resolve().parents[1] / "local" / "event-roundup.py"
)
assert SPEC is not None and SPEC.loader is not None
roundup = importlib.util.module_from_spec(SPEC)
sys.modules["event_roundup"] = roundup  # its dataclass looks itself up here
SPEC.loader.exec_module(roundup)

START, HORIZON = date(2026, 11, 17), date(2026, 12, 14)


def write(tmp_path, monkeypatch, payload):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "_data").mkdir()
    (tmp_path / "_data" / "candidate-events.json").write_text(json.dumps(payload), encoding="utf-8")
    return "/_data/candidate-events.json"


def test_candidate_events_are_read_with_their_own_links_and_notes(tmp_path, monkeypatch):
    url = write(tmp_path, monkeypatch, {"events": [
        {"title": "Winter Showcase", "date": "2026-11-22", "time": "12:30", "venue": "Pittville Pump Room",
         "link": "https://example.org/showcase", "note": "Two performances: 12:30 and 18:30"},
    ]})
    [ev] = roundup.fetch_json_events("Candidates", url, START, HORIZON)
    assert ev.title == "Winter Showcase"
    assert ev.event_date == date(2026, 11, 22)
    assert ev.venue == "Pittville Pump Room"
    assert ev.link == "https://example.org/showcase"
    assert ev.description == "12:30 — Two performances: 12:30 and 18:30"


def test_candidate_events_without_a_note_get_no_made_up_description(tmp_path, monkeypatch):
    url = write(tmp_path, monkeypatch, {"events": [
        {"title": "Carols", "date": "2026-11-28", "link": "https://example.org/carols"},
    ]})
    [ev] = roundup.fetch_json_events("Candidates", url, START, HORIZON)
    assert ev.description == ""


def test_candidate_events_outside_the_window_or_without_a_link_are_skipped(tmp_path, monkeypatch):
    url = write(tmp_path, monkeypatch, {"events": [
        {"title": "Too soon", "date": "2026-11-16", "link": "https://example.org/a"},
        {"title": "Too late", "date": "2026-12-15", "link": "https://example.org/b"},
        {"title": "No link", "date": "2026-11-20"},
        {"title": "Bad date", "date": "soon", "link": "https://example.org/c"},
        {"title": "Spans in", "date": "2026-11-10", "end_date": "2026-11-18", "link": "https://example.org/d"},
    ]})
    titles = [ev.title for ev in roundup.fetch_json_events("Candidates", url, START, HORIZON)]
    assert titles == ["Spans in"]


def test_fixtures_files_still_read_as_before(tmp_path, monkeypatch):
    url = write(tmp_path, monkeypatch, {"source_url": "https://example.org/fixtures", "fixtures": [
        {"home": "Cheltenham Town", "away": "Exeter City", "date": "2026-11-21", "time": "15:00",
         "competition": "League Two", "venue": "Whaddon Road"},
    ]})
    [ev] = roundup.fetch_json_events("Sport", url, START, HORIZON)
    assert ev.title == "Cheltenham Town vs Exeter City"
    assert ev.description == "League Two — kick-off 15:00"
