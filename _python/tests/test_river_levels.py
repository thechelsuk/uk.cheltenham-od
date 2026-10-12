"""Offline tests for the river levels fetcher (river-levels.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
from datetime import date, datetime

import importlib.util
import pathlib


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
