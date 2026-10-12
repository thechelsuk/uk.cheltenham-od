"""Offline tests for the river levels fetcher (river-levels.py). The
Environment Agency API is replaced with a fake, and the main run writes to a
temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import date, datetime, timedelta, timezone

import pytest

import helper


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


river = _load("river_levels", "river-levels.py")


def test_level_status_against_the_typical_range():
    assert river.level_status(0.9, 0.2, 0.8) == "Above typical range"
    assert river.level_status(0.1, 0.2, 0.8) == "Below typical range"
    assert river.level_status(0.5, 0.2, 0.8) == "Within typical range"
    assert river.level_status(0.5, None, 0.8) is None


def test_daily_summaries_skip_today_and_summarise_each_day():
    readings = [(datetime(2026, 10, 10, 6), 0.4), (datetime(2026, 10, 10, 18), 0.6), (datetime(2026, 10, 12, 6), 9.9)]
    assert river.daily_summaries(readings, "level", date(2026, 10, 12)) == {
        "2026-10-10": {"min": 0.4, "mean": 0.5, "max": 0.6},
    }


def test_rainfall_is_totalled_per_day():
    readings = [(datetime(2026, 10, 10, 6), 1.2), (datetime(2026, 10, 10, 7), 0.3)]
    assert river.daily_summaries(readings, "rainfall", date(2026, 10, 12)) == {"2026-10-10": {"total": 1.5}}


NOW = datetime.now(timezone.utc).replace(second=0, microsecond=0)


def stamp(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def station(reference, kind, label, river_name="", lat=51.9, measures=None):
    return {"stationReference": reference, "label": label, "riverName": river_name, "lat": lat, "long": -2.07,
            "measures": measures if measures is not None else [{"parameter": kind}]}


class FakeApi:
    """river.get replacement: station lists by parameter, readings and detail by reference."""
    def __init__(self, stations, readings, details=None):
        self.stations, self.readings, self.details = stations, readings, details or {}
        self.calls = []

    def __call__(self, path, **params):
        self.calls.append((path, params))
        if path == "/id/stations":
            return {"items": self.stations.get(params["parameter"], [])}
        reference = path.split("/")[3]
        if path.endswith("/readings"):
            return {"items": self.readings.get(reference, [])}
        return {"items": self.details.get(reference, {})}


def test_get_reads_the_api_through_helper(monkeypatch):
    class Response:
        def json(self):
            return {"items": []}

    asked = []
    monkeypatch.setattr(helper, "get", lambda url, params, timeout: asked.append((url, params)) or Response())
    assert river.get("/id/stations", parameter="level") == {"items": []}
    assert asked == [(river.BASE_URL + "/id/stations", {"parameter": "level"})]


def test_find_stations_keeps_gauges_with_a_matching_measure_and_a_location(monkeypatch):
    api = FakeApi({
        "level": [station("L1", "level", "Cheltenham"),
                  station("L2", "level", "No location", lat=None),
                  station("L3", "level", "Flow only", measures=[{"parameter": "flow"}])],
        "rainfall": [station("R1", "rainfall", "Rainfall station", measures={"parameter": "rainfall"})],
    }, {})
    monkeypatch.setattr(river, "get", api)
    found = river.find_stations()
    assert [(s["kind"], s["item"]["stationReference"]) for s in found] == [("level", "L1"), ("rainfall", "R1")]
    assert {params["parameter"]: params["dist"] for path, params in api.calls} == river.RADIUS_KM


def test_fetch_readings_sorts_and_skips_empty_values(monkeypatch):
    api = FakeApi({}, {"L1": [{"dateTime": "2026-10-12T10:00:00Z", "value": 0.5},
                              {"dateTime": "2026-10-12T09:45:00Z", "value": [0.4, 9.9]},
                              {"dateTime": "2026-10-12T09:30:00Z", "value": None}]})
    monkeypatch.setattr(river, "get", api)
    readings = river.fetch_readings("L1", datetime(2026, 10, 12, tzinfo=timezone.utc))
    assert [v for _, v in readings] == [0.4, 0.5]
    assert readings[0][0] == datetime(2026, 10, 12, 9, 45, tzinfo=timezone.utc)
    assert api.calls[0][1]["since"] == "2026-10-12T00:00:00Z"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    (tmp_path / "_data").mkdir()
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    return tmp_path / "_data"


def readings(*pairs):
    return [{"dateTime": stamp(hours), "value": value} for hours, value in pairs]


def test_main_writes_gauges_and_backfills_the_history(data_dir, monkeypatch):
    api = FakeApi(
        {"level": [station("L2", "level", "Swindon Village", "River Chelt"),
                   station("L1", "level", "Sandford Park", "River Chelt"),
                   station("OLD", "level", "Retired", "River Chelt")],
         "rainfall": [station("R1", "rainfall", "Rainfall station")]},
        {"L1": readings((60, 0.3), (30, 0.5), (1, 0.95)),
         "L2": readings((2, 0.4)),
         "OLD": readings((24 * 10, 0.2)),
         "R1": readings((50, 4.0), (30, 1.0), (10, 0.4), (2, 0.2))},
        {"L1": {"stageScale": {"typicalRangeLow": 0.2, "typicalRangeHigh": 0.8,
                               "maxOnRecord": {"value": 1.62, "dateTime": "2007-07-20T10:00:00Z"}}},
         "L2": {"stageScale": "http://link-only"}},
    )
    monkeypatch.setattr(river, "get", api)

    river.main()

    output = json.loads((data_dir / "river-levels.json").read_text())
    assert [s["reference"] for s in output["stations"]] == ["L1", "L2", "R1"]
    sandford, swindon, rain = output["stations"]
    assert sandford["latest_display"] == "0.95 m" and sandford["status"] == "Above typical range"
    assert sandford["typical_range_display"] == "0.20 to 0.80 m"
    assert (sandford["record_display"], sandford["record_date"]) == ("1.62 m", "2007-07-20")
    assert len(sandford["readings"]) == 2                    # only the last 48 hours are charted
    assert swindon["status"] is None and swindon["record_display"] is None
    assert rain["label"] == "Rainfall gauge R1" and rain["unit"] == "mm"
    assert (rain["rain_24h_display"], rain["rain_48h_display"]) == ("0.6 mm", "1.6 mm")

    since = [params["since"] for path, params in api.calls if path.endswith("/readings")][0]
    assert NOW - datetime.fromisoformat(since.replace("Z", "+00:00")) >= timedelta(days=river.BACKFILL_DAYS - 1)
    history = json.loads((data_dir / "river-levels-history.json").read_text())
    assert history["retention_days"] == river.RETENTION_DAYS
    assert all(day < NOW.date().isoformat() for day in history["days"])


def test_main_refreshes_a_few_days_and_drops_history_past_retention(data_dir, monkeypatch):
    old_day = (NOW.date() - timedelta(days=river.RETENTION_DAYS + 1)).isoformat()
    kept_day = (NOW.date() - timedelta(days=100)).isoformat()
    (data_dir / "river-levels-history.json").write_text(json.dumps(
        {"days": {old_day: {"L1": {"min": 1}}, kept_day: {"L1": {"min": 2}}}}))
    api = FakeApi({"level": [station("L1", "level", "Sandford Park", "River Chelt")]},
                  {"L1": readings((1, 0.5))})
    monkeypatch.setattr(river, "get", api)

    river.main()

    since = [params["since"] for path, params in api.calls if path.endswith("/readings")][0]
    assert NOW - datetime.fromisoformat(since.replace("Z", "+00:00")) < timedelta(days=river.REFRESH_DAYS + 1)
    days = json.loads((data_dir / "river-levels-history.json").read_text())["days"]
    assert old_day not in days and days[kept_day] == {"L1": {"min": 2}}


def test_main_leaves_the_files_alone_when_no_gauge_reports(data_dir, monkeypatch):
    monkeypatch.setattr(river, "get", FakeApi({"level": [station("L1", "level", "Quiet")]}, {}))
    with pytest.raises(SystemExit, match="No gauges"):
        river.main()
    assert list(data_dir.iterdir()) == []
