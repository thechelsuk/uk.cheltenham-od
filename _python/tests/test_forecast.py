"""Offline tests for the OpenWeather forecast fetcher (forecast.py) and the
homepage's today picker (weather.py). requests.get is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime as dt
import importlib.util
import json
import pathlib
import runpy
from urllib.parse import parse_qs, urlparse

import pytest

import helper

HERE = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("forecast", HERE / "forecast.py")
assert SPEC is not None and SPEC.loader is not None
forecast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forecast)

# 2026-06-21 00:00 UTC, with sunrise 03:43 and sunset 20:32 UTC (04:43/21:32 BST).
MIDNIGHT = 1782000000 - 1782000000 % 86400


def day(offset_days=0, **overrides):
    record = {
        "dt": MIDNIGHT + offset_days * 86400 + 12 * 3600,
        "sunrise": MIDNIGHT + offset_days * 86400 + 3 * 3600 + 43 * 60,
        "sunset": MIDNIGHT + offset_days * 86400 + 20 * 3600 + 32 * 60,
        "temp": {"min": 11.04, "max": 22.46, "day": 20.15},
        "feels_like": {"day": 19.96},
        "weather": [{"icon": "02d", "description": "few clouds"}],
        "pop": 0.2, "wind_speed": 4.06, "humidity": 55, "pressure": 1018, "uvi": 7.1,
    }
    record.update(overrides)
    return record


def test_force_units_puts_metric_back_on_next_links():
    url = forecast.force_units("https://api.example.org/x?lat=1&start=2&units=imperial")
    assert parse_qs(urlparse(url).query) == {"lat": ["1"], "start": ["2"], "units": ["metric"]}


def test_local_time_applies_the_offset():
    assert forecast.local_time(MIDNIGHT + 3 * 3600 + 43 * 60, 3600) == ("04:43", 4 * 60 + 43)


def test_start_of_today_is_a_utc_midnight():
    assert forecast.start_of_today_utc() % 86400 == 0


def test_normalize_rounds_and_formats_each_day():
    data = forecast.normalize([day(), day(1, weather=None)], 3600)
    first = data["days"][0]
    assert first == {
        "date": dt.datetime.fromtimestamp(MIDNIGHT, dt.timezone.utc).strftime("%Y-%m-%d"),
        "min": 11.0, "max": 22.5, "day": 20.1, "feels_like": 20.0,
        "icon": "02d", "desc": "few clouds", "pop": 0.2, "wind": 4.1,
        "humidity": 55, "pressure": 1018, "uvi": 7.1,
        "sunrise": "04:43", "sunset": "21:32", "sun_start": 283, "sun_end": 1292,
        "daylight": 1009, "daylight_str": "16h 49m",
    }
    assert data["location"] == "Cheltenham" and data["units"] == "metric"
    assert data["days"][1]["icon"] == "" and data["days"][1]["desc"] == ""


def test_normalize_treats_a_missing_wind_speed_as_calm():
    record = day()
    del record["wind_speed"]
    assert forecast.normalize([record], 0)["days"][0]["wind"] == 0


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_fetch_timeline_follows_next_links_until_it_has_enough(monkeypatch):
    pages = [FakeResponse({"timezone_offset": 3600, "data": [day(0), day(1)],
                           "next": "https://api.example.org/next?start=3"}),
             FakeResponse({"timezone_offset": 3600, "data": [day(2), day(3)], "next": "https://unused"})]
    urls = []
    monkeypatch.setattr(forecast.requests, "get", lambda url, timeout: urls.append(url) or pages.pop(0))

    records, offset = forecast.fetch_timeline(3)

    assert len(records) == 3 and offset == 3600
    assert "units=metric" in urls[1] and len(urls) == 2


def test_fetch_timeline_explains_a_401(monkeypatch):
    monkeypatch.setattr(forecast.requests, "get", lambda url, timeout: FakeResponse({}, status=401))
    with pytest.raises(SystemExit, match="One Call API 4.0"):
        forecast.fetch_timeline(10)


def test_main_needs_an_api_key(monkeypatch):
    monkeypatch.setattr(forecast, "API_KEY", "")
    with pytest.raises(SystemExit, match="OPEN_WEATHER_KEY"):
        forecast.main()


def test_main_writes_the_normalised_days(monkeypatch):
    monkeypatch.setattr(forecast, "API_KEY", "test-key")
    monkeypatch.setattr(forecast, "fetch_timeline", lambda target: ([day()], 0))
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    forecast.main()
    assert written["path"] == forecast.OUT and len(written["payload"]["days"]) == 1


def test_weather_today_picks_todays_record_or_the_first(tmp_path, monkeypatch):
    data_dir = tmp_path / "_data"
    data_dir.mkdir()
    today = dt.date.today().strftime("%Y-%m-%d")
    days = forecast.normalize([day(), day(1)], 0)["days"]
    days[1]["date"], days[1]["desc"] = today, "sunny"
    (data_dir / "weather.json").write_text(json.dumps({"days": days}))
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)

    runpy.run_path(str(HERE / "weather.py"), run_name="__main__")
    out = json.loads((data_dir / "weather-today.json").read_text())
    assert out["desc"] == "sunny" and out["high"] == 22.5 and out["sunrise"] == "03:43"

    days[1]["date"] = "1999-01-01"
    (data_dir / "weather.json").write_text(json.dumps({"days": days}))
    runpy.run_path(str(HERE / "weather.py"), run_name="__main__")
    assert json.loads((data_dir / "weather-today.json").read_text())["desc"] == "few clouds"
