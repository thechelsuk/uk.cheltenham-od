"""Offline tests for the InPost locker fetcher (inpost.py): venue names,
point clean-up, and the Cheltenham-only filter in the main run.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
import runpy

import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "inpost.py"
SPEC = importlib.util.spec_from_file_location("inpost", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
inpost = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inpost)


def point(name, city="Cheltenham", building="", display="", **extra):
    return {
        "name": name,
        "display_name": display,
        "address_details": {"city": city, "building_number": building,
                            "street": "HIGH STREET", "post_code": "GL50 1AA"},
        "location": {"latitude": 51.9, "longitude": -2.08},
        **extra,
    }


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_venue_name_drops_the_inpost_locker_prefix():
    assert inpost.venue_name(point("A", building="24/7 InPost Locker - tesco express")) == "Tesco Express"
    assert inpost.venue_name(point("A", building="InPost Locker -   Co-op")) == "Co-op"


def test_venue_name_falls_back_to_the_display_name_then_a_default():
    assert inpost.venue_name(point("A", display="SPAR GL52")) == "Spar GL52"
    assert inpost.venue_name({"address_details": None}) == "Inpost Locker"


def test_clean_point_normalises_the_fields_the_page_uses():
    cleaned = inpost.clean_point(point("CHE01M", building="Morrisons", location_247=1,
                                       location_description="By the doors", functions=["parcel_collect"]))
    assert cleaned == {
        "id": "CHE01M",
        "name": "Morrisons",
        "street": "High Street",
        "postcode": "GL50 1AA",
        "lat": 51.9,
        "lon": -2.08,
        "is_247": True,
        "location_description": "By the doors",
        "functions": ["parcel_collect"],
    }


def test_clean_point_copes_with_missing_details():
    cleaned = inpost.clean_point({"name": "X"})
    assert cleaned["street"] == "" and cleaned["postcode"] == ""
    assert cleaned["lat"] is None and cleaned["is_247"] is False and cleaned["functions"] == []


def test_fetch_points_asks_for_operating_lockers_near_the_centre(monkeypatch):
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs["params"]))
        return FakeResponse({"items": [point("A")]})

    monkeypatch.setattr(helper, "request_with_retry", fake_request)
    assert inpost.fetch_points() == [point("A")]
    method, url, params = calls[0]
    assert (method, url) == ("GET", inpost.API_URL)
    assert params["status"] == "Operating" and params["max_distance"] == inpost.MAX_DISTANCE_M


def test_main_run_keeps_only_cheltenham_lockers_sorted_by_name(monkeypatch):
    items = [point("B", building="Waitrose"), point("C", city="Gloucester", building="Asda"),
             point("A", city=" CHELTENHAM ", building="aldi")]
    monkeypatch.setattr(helper, "request_with_retry", lambda *a, **k: FakeResponse({"items": items}))
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    runpy.run_path(str(SCRIPT), run_name="__main__")

    payload = written["payload"]
    assert written["path"].name == "inpost-lockers.json"
    assert payload["count"] == 2
    assert [locker["name"] for locker in payload["lockers"]] == ["Aldi", "Waitrose"]
