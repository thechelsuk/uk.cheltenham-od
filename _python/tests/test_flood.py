"""Offline tests for the flood warnings fetcher (flood.py): flattening
Environment Agency warnings and shaping _data/flood.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

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
