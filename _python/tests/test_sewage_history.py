"""Offline tests for the storm overflow fetcher (sewage-overflows.py): the
spill log, Esri date fields, and the main run with the overflow query
faked and the files written to a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import datetime, timezone

import pytest

import helper

SPEC = importlib.util.spec_from_file_location(
    "sewage_overflows", pathlib.Path(__file__).resolve().parents[1] / "sewage-overflows.py"
)
assert SPEC is not None and SPEC.loader is not None
sewage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sewage)


def overflow(**overrides):
    base = {
        "id": "SVT00527", "watercourse": "River Chelt", "discharging": False,
        "latest_event_start": "2026-08-20 14:25", "latest_event_end": "2026-08-20 16:13",
        "latest_event_hours": 1.8, "distance_miles": 1.06,
    }
    return {**base, **overrides}


def test_a_finished_spill_is_logged_once():
    spills = sewage.update_spills([], [overflow()], "2026-10-11")
    spills = sewage.update_spills(spills, [overflow()], "2026-10-11")
    assert spills == [{
        "key": "SVT00527 2026-08-20 14:25", "overflow_id": "SVT00527", "watercourse": "River Chelt",
        "start": "2026-08-20 14:25", "end": "2026-08-20 16:13", "hours": 1.8,
    }]


def test_a_spill_still_running_waits_until_it_ends():
    running = overflow(discharging=True, latest_event_start="2026-10-11 09:00", latest_event_end=None,
                       latest_event_hours=None)
    assert sewage.update_spills([], [running], "2026-10-11") == []


def test_new_spills_come_first_and_old_ones_drop_off():
    old = {"key": "SVT1 2024-01-01 10:00", "overflow_id": "SVT1", "watercourse": "Hyde Brook",
           "start": "2024-01-01 10:00", "end": "2024-01-01 12:00", "hours": 2.0}
    newer = overflow(id="SVT2", latest_event_start="2026-10-10 06:00", latest_event_end="2026-10-10 07:30",
                     latest_event_hours=1.5)
    spills = sewage.update_spills([old], [overflow(), newer], "2026-10-11")
    assert [s["start"] for s in spills] == ["2026-10-10 06:00", "2026-08-20 14:25"]


def test_summaries_by_month_and_watercourse():
    spills = [
        {"watercourse": "River Chelt", "start": "2026-10-10 06:00", "hours": 1.5},
        {"watercourse": "River Chelt", "start": "2026-10-02 06:00", "hours": 3.0},
        {"watercourse": "Hyde Brook", "start": "2026-09-30 22:00", "hours": 0.5},
    ]
    assert sewage.summarise(spills, "month") == [
        {"month": "2026-10", "spills": 2, "hours": 4.5},
        {"month": "2026-09", "spills": 1, "hours": 0.5},
    ]
    assert sewage.summarise(spills, "watercourse") == [
        {"watercourse": "River Chelt", "spills": 2, "hours": 4.5, "longest_hours": 3.0},
        {"watercourse": "Hyde Brook", "spills": 1, "hours": 0.5, "longest_hours": 0.5},
    ]


def test_esri_dates_are_epoch_milliseconds_or_text():
    assert sewage.parse_field_date(1787234700000) == datetime(2026, 8, 20, 14, 5, tzinfo=timezone.utc)
    assert sewage.friendly_date("2026-08-20T14:25:00Z") == "2026-08-20 14:25"
    assert sewage.parse_field_date("not a date") is None
    assert sewage.friendly_date(None) is None


def feature(overflow_id, lat, lon, status=0, start=None, end=None, watercourse="RIVER CHELT"):
    return {"properties": {"Id": overflow_id, "Latitude": lat, "Longitude": lon, "Status": status,
                           "StatusStart": "2026-10-12T06:00:00Z", "ReceivingWaterCourse": watercourse,
                           "LatestEventStart": start, "LatestEventEnd": end}}


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


@pytest.fixture
def files(tmp_path, monkeypatch):
    out, history = tmp_path / "sewage-overflows.json", tmp_path / "sewage-overflows-history.json"
    monkeypatch.setattr(sewage, "OUT", str(out))
    monkeypatch.setattr(sewage, "HISTORY_OUT", str(history))
    return out, history


def test_main_lists_nearby_overflows_discharging_first_and_logs_finished_spills(files, monkeypatch):
    out, history = files
    features = [
        feature("NEAR-QUIET", 51.900, -2.079, start="2026-10-10T14:00:00Z", end="2026-10-10T15:30:00Z"),
        feature("FURTHER-ON", 51.910, -2.090, status=1, start="2026-10-12T07:00:00Z", watercourse="WYMANS BROOK"),
        feature("GLOUCESTER", 51.86, -2.24),
        feature("NO-LOCATION", None, -2.08),
    ]
    asked = []
    monkeypatch.setattr(helper, "get", lambda url, params: asked.append(params) or FakeResponse({"features": features}))

    sewage.main()

    assert asked[0]["distance"] == sewage.RADIUS_MILES and asked[0]["f"] == "geojson"
    overflows = json.loads(out.read_text())["overflows"]
    assert [o["id"] for o in overflows] == ["FURTHER-ON", "NEAR-QUIET"]
    running, quiet = overflows
    assert running["discharging"] is True and running["watercourse"] == "Wymans Brook"
    assert running["latest_event_hours"] is None
    assert quiet["latest_event_hours"] == 1.5 and quiet["status_since"] == "2026-10-12 06:00"
    log = json.loads(history.read_text())
    assert [s["overflow_id"] for s in log["spills"]] == ["NEAR-QUIET"]
    assert log["by_watercourse"][0]["watercourse"] == "River Chelt"
    assert log["tracking_since"] == datetime.now(timezone.utc).date().isoformat()


def test_write_history_keeps_when_tracking_started(files):
    _, history = files
    history.write_text(json.dumps({"tracking_since": "2026-01-01", "spills": []}))
    spills = sewage.write_history([overflow()], datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert len(spills) == 1
    assert json.loads(history.read_text())["tracking_since"] == "2026-01-01"


def test_main_stops_on_an_unexpected_reply(files, monkeypatch):
    out, _ = files
    monkeypatch.setattr(helper, "get", lambda url, params: FakeResponse({"status": "processing"}))
    with pytest.raises(SystemExit, match="no 'features' key"):
        sewage.main()
    assert not out.exists()
