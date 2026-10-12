"""Offline tests for the DPD Pickup fetcher (dpd-pickup.py): opening-hours
summaries, postcode districts, point clean-up and the GL50-GL53 filter.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
import runpy

import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "dpd-pickup.py"
SPEC = importlib.util.spec_from_file_location("dpd_pickup", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
dpd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dpd)


def window(day, start, end):
    return {"pickupLocationOpenWindowDay": day,
            "pickupLocationOpenWindowStartTime": start,
            "pickupLocationOpenWindowEndTime": end}


def result(code, postcode, organisation="Shop", distance=1.23, windows=None):
    return {
        "distance": distance,
        "pickupLocation": {
            "pickupLocationCode": code,
            "address": {"organisation": organisation, "street": "LONDON ROAD", "postcode": postcode},
            "addressPoint": {"latitude": 51.9, "longitude": -2.07},
            "pickupLocationAvailability": {"pickupLocationOpenWindow": windows or []},
        },
    }


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_postcode_district_is_the_outward_code():
    assert dpd.postcode_district("GL50 1NB") == "GL50"
    assert dpd.postcode_district("GL52") == "GL52"


def test_day_span_joins_split_windows_into_one_span():
    assert dpd.day_span([]) == "Closed"
    assert dpd.day_span([window(1, "13:00", "17:00"), window(1, "09:00", "12:00")]) == "09:00-17:00"


def test_summarise_hours_groups_runs_of_identical_days():
    windows = [window(d, "08:30", "18:00") for d in range(1, 7)] + [window(7, "10:30", "16:30")]
    assert dpd.summarise_hours(windows) == ("Mon-Sat 08:30-18:00, Sun 10:30-16:30", False)


def test_summarise_hours_marks_closed_days_and_round_the_clock_sites():
    assert dpd.summarise_hours([window(3, "09:00", "17:00")]) == (
        "Mon-Tue Closed, Wed 09:00-17:00, Thu-Sun Closed", False)
    always = [window(d, "00:01", "23:59") for d in range(1, 8)]
    assert dpd.summarise_hours(always) == ("Mon-Sun 00:01-23:59", True)
    assert dpd.summarise_hours(None) == ("Mon-Sun Closed", False)


def test_clean_point_flags_post_offices_and_rounds_distance():
    cleaned = dpd.clean_point(result("GB1", "GL50 1AA", organisation="Bath Road Post Office", distance=0.456))
    assert cleaned == {
        "id": "GB1",
        "name": "Bath Road Post Office",
        "street": "London Road",
        "postcode": "GL50 1AA",
        "lat": 51.9,
        "lon": -2.07,
        "distance_miles": 0.5,
        "is_247": False,
        "opening_hours": "Mon-Sun Closed",
        "is_post_office": True,
    }


def test_clean_point_names_an_unnamed_point():
    res = result("GB2", "GL51 2AA", organisation="")
    res["pickupLocation"]["addressPoint"] = None
    cleaned = dpd.clean_point(res)
    assert cleaned["name"] == "DPD Pickup Point" and cleaned["lat"] is None


def test_fetch_points_returns_the_results_list(monkeypatch):
    monkeypatch.setattr(helper, "request_with_retry", lambda *a, **k: FakeResponse({"results": [1, 2]}))
    assert dpd.fetch_points() == [1, 2]


def test_main_run_keeps_cheltenham_districts_nearest_first(monkeypatch):
    results = [result("FAR", "GL53 7AA", distance=2.0), result("GLOS", "GL1 1AA", distance=0.1),
               result("NEAR", "GL50 1AA", distance=0.3), result("ANDO", "GL54 4AA", distance=0.2)]
    monkeypatch.setattr(helper, "request_with_retry", lambda *a, **k: FakeResponse({"results": results}))
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    runpy.run_path(str(SCRIPT), run_name="__main__")

    assert written["path"].name == "dpd-pickup-points.json"
    assert [p["id"] for p in written["payload"]["points"]] == ["NEAR", "FAR"]
    assert written["payload"]["count"] == 2
