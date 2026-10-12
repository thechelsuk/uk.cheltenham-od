"""Offline tests for the Pi's train times fetcher (pi/rail-times.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
from datetime import datetime

import importlib.util
import pathlib


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rail = _load("rail_times", "pi/rail-times.py")
GENERATED = datetime(2026, 10, 12, 23, 50, tzinfo=rail.LONDON)


def test_a_time_after_midnight_rolls_into_the_next_day():
    assert rail.resolve_time("00:10", GENERATED).date().isoformat() == "2026-10-13"
    assert rail.resolve_time("23:55", GENERATED).date().isoformat() == "2026-10-12"


def test_an_on_time_departure():
    service = {"std": "23:55", "etd": "On time", "platform": "1", "operator": "CrossCountry",
               "destination": [{"locationName": "Bristol Temple Meads"}]}
    item = rail.parse_service(service, "departure", GENERATED)
    assert item["status"] == "On time"
    assert item["scheduled"] == "2026-10-12T23:55"
    assert item["destination"] == "Bristol Temple Meads"
    assert item["calling_at"] == []


def test_a_late_estimate_is_delayed_and_a_cancellation_is_cancelled():
    late = rail.parse_service({"std": "23:55", "etd": "23:59"}, "departure", GENERATED)
    assert late["status"] == "Delayed" and late["expected"] == "2026-10-12T23:59"
    cancelled = rail.parse_service({"sta": "23:55", "eta": "Cancelled", "cancelReason": "<p>A fault</p>"}, "arrival", GENERATED)
    assert cancelled["status"] == "Cancelled" and cancelled["reason"] == "A fault"


def test_a_service_without_a_scheduled_time_is_skipped():
    assert rail.parse_service({"sta": "23:55"}, "departure", GENERATED) is None


def test_station_messages_are_plain_text_without_repeats():
    board = {"nrccMessages": [{"value": "<p>Lifts &amp; escalators closed</p>"}, {"value": "Lifts & escalators closed"}]}
    assert rail.station_messages(board) == ["Lifts & escalators closed"]
