"""Offline tests for the air quality fetcher (air-quality.py): matching
DEFRA UK-AIR series to pollutants, banding readings and shaping
_data/air-quality.json. requests.get is replaced with a fake for the
station list and time series.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime
import importlib.util
import pathlib
import sys

import pytest
import requests

import helper

SPEC = importlib.util.spec_from_file_location(
    "air_quality", pathlib.Path(__file__).resolve().parents[1] / "air-quality.py"
)
assert SPEC is not None and SPEC.loader is not None
aq = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aq)

FOUR_AM = datetime.datetime(2026, 10, 12, 4, 0, tzinfo=datetime.timezone.utc)


def reading(station, key, value, distance=2.5, when=FOUR_AM, uom="ug.m-3"):
    return {
        "station": station,
        "distance_km": distance,
        "pollutant_key": key,
        "pollutant_label": aq.POLLUTANTS_OF_INTEREST[key],
        "value": value,
        "uom": uom,
        "timestamp": when,
        "band": aq.daqi_band(key, value),
    }


def test_pollutants_are_matched_by_eionet_code_then_by_label_text():
    assert aq.match_pollutant_key("http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001") == "pm2.5"
    assert aq.match_pollutant_key("", fallback_text="Gloucester-Nitrogen dioxide (air)") == "no2"
    assert aq.match_pollutant_key("Benzene") is None


def test_readings_are_banded_against_the_daqi_thresholds():
    assert aq.daqi_band("pm2.5", 0.9) == "Low"
    assert aq.daqi_band("pm10", 40) == "High"
    assert aq.daqi_band("no2", None) == "n/a"


def test_the_pollutant_suffix_is_stripped_from_a_station_label():
    label = "Cheltenham A40 Gloucester Road-Particulate matter less than 2.5 micro m (aerosol)"
    assert aq.site_name(label) == "Cheltenham A40 Gloucester Road"
    assert aq.site_name("Gloucester Tredworth") == "Gloucester Tredworth"


def test_readings_are_grouped_into_stations_sorted_by_name_then_pollutant():
    stations = aq.build_stations([
        reading("Gloucester Tredworth", "pm2.5", 3.019, distance=12.1),
        reading("Cheltenham A40 Gloucester Road", "pm2.5", 0.9),
        reading("Gloucester Tredworth", "pm10", 6.0, distance=12.1),
    ])
    assert [s["name"] for s in stations] == ["Cheltenham A40 Gloucester Road", "Gloucester Tredworth"]
    assert stations[1]["distance_km"] == 12.1
    assert [r["pollutant"] for r in stations[1]["readings"]] == ["PM10 (particulates)", "PM2.5 (fine particulates)"]


def test_a_reading_keeps_its_value_and_a_display_string_and_an_iso_time():
    [station] = aq.build_stations([reading("CHELTENHAM ROAD", "pm10", 1234.5)])
    assert station["name"] == "Cheltenham Road"
    assert station["readings"] == [{
        "pollutant_key": "pm10",
        "pollutant": "PM10 (particulates)",
        "value": 1234.5,
        "uom": "ug.m-3",
        "reading_display": "1,234.5 ug.m-3",
        "band": "Very High",
        "measured": "2026-10-12T04:00",
    }]


def test_a_reading_with_no_value_or_time_shows_not_available():
    [station] = aq.build_stations([reading("Cheltenham", "o3", None, when=None)])
    assert station["readings"][0]["reading_display"] == "n/a"
    assert station["readings"][0]["measured"] is None


def test_the_highest_band_ignores_readings_without_a_band():
    readings = [reading("A", "pm2.5", 0.9), reading("A", "pm10", 20), reading("A", "o3", None)]
    assert aq.highest_band(readings) == "Moderate"
    assert aq.highest_band([]) is None


def test_the_payload_carries_the_source_envelope_and_headline_figures():
    payload = aq.build_payload([
        reading("Gloucester Tredworth", "pm10", 6.0, distance=12.1),
        reading("Cheltenham A40 Gloucester Road", "pm2.5", 0.9),
    ], generated_at="2026-10-12T06:27:00+00:00")
    assert payload["generated_at"] == "2026-10-12T06:27:00+00:00"
    assert payload["source"] == "DEFRA UK-AIR"
    assert payload["source_url"] == "https://uk-air.defra.gov.uk/"
    assert payload["licence"] == "Open Government Licence v3.0"
    assert payload["reading_count"] == 2
    assert payload["highest_band"] == "Low"
    assert payload["nearest_km"] == 2.5
    assert len(payload["stations"]) == 2


def test_an_empty_run_still_writes_a_payload():
    payload = aq.build_payload([], generated_at="2026-10-12T06:27:00+00:00")
    assert payload["stations"] == []
    assert payload["reading_count"] == 0
    assert payload["nearest_km"] is None


PM25 = "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001"
BENZENE = "http://dd.eionet.europa.eu/vocabulary/aq/pollutant/20"


def site(label, lat, lon, timeseries=None):
    """A station as the SOS API lists it: coordinates are [lat, lon, elevation]."""
    return {"properties": {"label": label, "timeseries": timeseries or {}},
            "geometry": {"coordinates": [lat, lon, "NaN"]}}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code, self.text = body, status, str(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


def test_smart_title_keeps_codes_and_short_acronyms():
    assert aq.smart_title("cheltenham A40 GL51 road") == "Cheltenham A40 GL51 Road"
    assert aq.smart_title("CHELTENHAM BATH ROAD HQ") == "Cheltenham Bath Road Hq"
    assert aq.smart_title("council HQ site") == "Council HQ Site"


def test_get_all_stations_pages_through_the_whole_list(monkeypatch):
    pages = [[{"n": i} for i in range(200)], [{"n": "last"}]]
    offsets = []

    def fake_get(url, params, headers, timeout):
        offsets.append(params["offset"])
        return FakeResponse(pages.pop(0))

    monkeypatch.setattr(aq.requests, "get", fake_get)
    assert len(aq.get_all_stations()) == 201
    assert offsets == [0, 200]


def test_get_all_stations_stops_on_an_unexpected_reply(monkeypatch):
    monkeypatch.setattr(aq.requests, "get", lambda url, params, headers, timeout: FakeResponse({"error": "x"}))
    assert aq.get_all_stations() == []


def test_filter_stations_by_distance_reads_lat_then_lon(monkeypatch):
    monkeypatch.setattr(aq, "DEBUG", True)
    near = site("Cheltenham A40 Gloucester Road-Ozone", 51.896592, -2.113747)
    swapped = site("Cheltenham swapped", -2.113747, 51.896592)
    far = site("Bristol", 51.45, -2.58)
    kept = aq.filter_stations_by_distance([near, swapped, far, {"properties": {}, "geometry": {}}])
    assert kept == [near] and near["_distance_km"] == pytest.approx(2.5, abs=0.1)
    assert aq.filter_stations_by_distance([]) == []


def test_collect_readings_walks_stations_to_their_latest_values(monkeypatch):
    stations = [
        site("Cheltenham A40 Gloucester Road-Particulate matter less than 2.5 micro m (aerosol)", 51.8966, -2.1137,
             {"ts1": {"phenomenon": {"label": PM25}}}),
        site("Cheltenham A40 Gloucester Road-Ozone", 51.8966, -2.1137,
             {"ts2": {"phenomenon": {"label": "http://x/pollutant/7"}},
              "ts3": {"phenomenon": {"label": "http://x/pollutant/7"}},
              "ts4": {"phenomenon": {"label": "http://x/pollutant/7"}}}),
        site("Benzene site", 51.9, -2.08, {"ts5": {"phenomenon": {"label": BENZENE}}}),
        site("Bristol-Ozone", 51.45, -2.58, {"ts6": {"phenomenon": {"label": PM25}}}),
    ]
    series = {
        "ts1": FakeResponse({"uom": "ug.m-3", "lastValue": {"value": 14.0, "timestamp": 1791777600000}}),
        "ts2": FakeResponse({"uom": "ug.m-3", "lastValue": {"value": 30.0, "timestamp": None}}),
        "ts3": FakeResponse({"uom": "ug.m-3", "lastValue": None}),
        "ts4": FakeResponse({}, status=500),
    }

    def fake_get(url, headers, timeout, params=None):
        if url.endswith("/stations"):
            return FakeResponse(stations if params["offset"] == 0 else [])
        return series[url.rsplit("/", 1)[1]]

    monkeypatch.setattr(aq.requests, "get", fake_get)
    readings = aq.collect_readings()
    assert [(r["station"], r["pollutant_key"], r["band"]) for r in readings] == [
        ("Cheltenham A40 Gloucester Road", "pm2.5", "Moderate"),
        ("Cheltenham A40 Gloucester Road", "o3", "Low"),
    ]
    assert readings[0]["timestamp"] == datetime.datetime.fromtimestamp(1791777600, tz=datetime.timezone.utc)
    assert readings[1]["timestamp"] is None


def test_collect_readings_returns_nothing_when_the_list_fails_or_nothing_is_near(monkeypatch):
    def down(url, params, headers, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(aq.requests, "get", down)
    assert aq.collect_readings() == []
    monkeypatch.setattr(aq.requests, "get", lambda url, params, headers, timeout: FakeResponse([site("Bristol", 51.45, -2.58)]))
    assert aq.collect_readings() == []


def test_main_writes_the_payload(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["air-quality.py"])
    monkeypatch.setattr(aq, "collect_readings", lambda: [reading("Cheltenham", "no2", 20.0)])
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    aq.main()
    assert written["path"] == aq.OUTPUT_FILE
    assert written["payload"]["reading_count"] == 1 and written["payload"]["highest_band"] == "Low"
    monkeypatch.setattr(aq, "collect_readings", lambda: [])
    aq.main()
    assert written["payload"]["reading_count"] == 0
