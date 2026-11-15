"""Offline tests for the crime fetcher's month handling (crime.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import sys

import pytest

import crime


@pytest.fixture
def saved(tmp_path, monkeypatch):
    (tmp_path / "2026-08").mkdir()
    monkeypatch.setattr(crime, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(crime, "fetch_latest_month", lambda: "2026-08")

    def no_fetch():
        raise AssertionError("nothing should be fetched")
    monkeypatch.setattr(crime, "fetch_neighbourhoods", no_fetch)


def test_a_scheduled_run_with_the_latest_month_saved_has_nothing_to_do(saved, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["crime.py"])
    crime.main()   # returns quietly: Police.uk hasn't published a new month yet


def test_asking_for_a_saved_month_still_needs_overwrite(saved, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["crime.py", "--date", "2026-08"])
    with pytest.raises(SystemExit):
        crime.main()
