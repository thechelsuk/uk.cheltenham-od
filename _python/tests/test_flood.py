"""Offline tests for the flood warnings fetcher (flood.py): flattening
Environment Agency warnings, shaping _data/flood.json, the Atom feed
entries, and the main run against a temporary folder with the fetch faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy

import helper

SPEC = importlib.util.spec_from_file_location(
    "flood", pathlib.Path(__file__).resolve().parents[1] / "flood.py"
)
assert SPEC is not None and SPEC.loader is not None
flood = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flood)

EA_ITEM = {
    "@id": "http://environment.data.gov.uk/flood-monitoring/id/floods/031WAF212",
    "description": "River Chelt at Cheltenham",
    "severity": "Flood alert",
    "severityLevel": 3,
    "message": "River levels are rising.",
    "floodArea": {"county": "Gloucestershire", "riverOrSea": "River Chelt"},
    "timeRaised": "2026-10-08T16:35:07",
    "timeSeverityChanged": "2026-10-08T16:30:00",
}


def test_an_ea_warning_is_flattened():
    assert flood.normalize_item(EA_ITEM) == {
        "flood_id": "http://environment.data.gov.uk/flood-monitoring/id/floods/031WAF212",
        "description": "River Chelt at Cheltenham",
        "severity": "Flood alert",
        "severity_level": 3,
        "message": "River levels are rising.",
        "county": "Gloucestershire",
        "river_or_sea": "River Chelt",
        "time_raised": "2026-10-08T16:35:07",
        "time_severity_changed": "2026-10-08T16:30:00",
    }


def test_a_sparse_warning_falls_back_to_empty_strings():
    item = flood.normalize_item({"description": "Severn Vale"})
    assert item["flood_id"] == "Severn Vale"
    assert item["severity"] == "" and item["county"] == ""


def test_the_payload_carries_the_source_envelope_and_flattened_warnings():
    payload = flood.build_payload({"items": [EA_ITEM]}, generated_at="2026-10-12T14:00:00+00:00")
    assert payload["generated_at"] == "2026-10-12T14:00:00+00:00"
    assert payload["source"] == "Environment Agency flood monitoring API"
    assert payload["source_url"] == "https://environment.data.gov.uk/flood-monitoring/doc/reference"
    assert payload["licence"] == "Open Government Licence v3.0"
    assert payload["count"] == 1
    assert payload["items"] == [flood.normalize_item(EA_ITEM)]


def test_most_severe_warnings_come_first():
    alert = {**EA_ITEM, "@id": "a", "severityLevel": 3, "description": "B"}
    warning = {**EA_ITEM, "@id": "w", "severityLevel": 2, "description": "A"}
    payload = flood.build_payload({"items": [alert, warning]}, generated_at="2026-10-12T14:00:00+00:00")
    assert [i["flood_id"] for i in payload["items"]] == ["w", "a"]


def test_no_warnings_is_an_empty_list():
    payload = flood.build_payload({"items": []}, generated_at="2026-10-12T14:00:00+00:00")
    assert payload["count"] == 0
    assert payload["items"] == []


def test_feed_entries_link_by_warning_and_date_by_last_seen():
    records = [{**flood.normalize_item(EA_ITEM), "first_seen_iso": "2026-10-08T16:40:00Z",
                "last_seen_iso": "2026-10-09T08:00:00Z"},
               {"flood_id": "x", "first_seen_iso": "2026-10-01T00:00:00Z"}]
    first, second = flood.build_atom_items(records, "https://example.org/history")
    assert first == {"title": "Flood alert: River Chelt at Cheltenham",
                     "link": f"https://example.org/history#{EA_ITEM['@id']}",
                     "summary": "River levels are rising. · County: Gloucestershire",
                     "published_iso": "2026-10-09T08:00:00Z", "source": "Environment Agency"}
    assert second["title"] == "Flood: " and second["summary"] == "Flood: "
    assert len(flood.build_atom_items(records * 30, "x")) == 50


def test_main_run_writes_warnings_history_and_feed(tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    monkeypatch.setattr(helper, "fetch_flood_data", lambda: {"items": [EA_ITEM]})
    script = str(pathlib.Path(__file__).resolve().parents[1] / "flood.py")

    runpy.run_path(script, run_name="__main__")

    current = json.loads((tmp_path / "_data" / "flood.json").read_text())
    assert [i["description"] for i in current["items"]] == ["River Chelt at Cheltenham"]
    history = json.loads((tmp_path / "_data" / "flood-history.json").read_text())
    assert history["count"] == 1
    feed = (tmp_path / "feeds" / "flood.xml").read_text()
    assert "https://example.org/cheltenham-flood-warnings/history#" in feed

    # The warning is lifted: the current list empties but the history keeps it.
    monkeypatch.setattr(helper, "fetch_flood_data", lambda: {"items": []})
    runpy.run_path(script, run_name="__main__")
    assert json.loads((tmp_path / "_data" / "flood.json").read_text())["items"] == []
    (record,) = json.loads((tmp_path / "_data" / "flood-history.json").read_text())["records"]
    assert record["resolved_iso"]
