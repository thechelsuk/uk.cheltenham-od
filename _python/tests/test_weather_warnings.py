"""Offline tests for the weather warnings fetcher (pi/weather-warnings.py):
reading the Met Office South West England RSS feed, keeping the warnings that
list Gloucestershire, the homepage alert, feed entries, and the main run
against a temporary folder with the download faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy

import requests

import alerts_feed
import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "pi" / "weather-warnings.py"
SPEC = importlib.util.spec_from_file_location("weather_warnings", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
ww = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ww)

LINK = ("https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings"
        "#?date={day}&amp;id={id}&amp;referrer=rss")


def item(title, description, day="2026-11-01", id_="abc-123"):
    return (f"<item><title>{title}</title><link>{LINK.format(day=day, id=id_)}</link>"
            f"<description>{description}</description></item>")


def feed(*items):
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
            f"<title>Met Office warnings for South West England</title>{''.join(items)}</channel></rss>")


GLOS_RAIN = item(
    "Yellow warning of rain affecting South West England",
    "Yellow warning of rain affecting South West England: Bristol, Gloucestershire, Somerset "
    "valid from 0600 Sun 01 Nov to 2100 Sun 01 Nov",
)
CORNWALL_WIND = item(
    "Yellow warning of wind affecting South West England",
    "Yellow warning of wind affecting South West England: Cornwall, Devon "
    "valid from 0900 Sun 01 Nov to 1800 Sun 01 Nov",
    id_="def-456",
)


def test_reads_level_hazard_areas_and_local_times():
    (warning,) = ww.parse(feed(GLOS_RAIN))
    assert warning["id"] == "abc-123"
    assert warning["level"] == "Yellow" and warning["hazard"] == "rain"
    assert warning["areas"] == ["Bristol", "Gloucestershire", "Somerset"]
    assert warning["starts"] == "2026-11-01T06:00" and warning["ends"] == "2026-11-01T21:00"


def test_keeps_the_met_office_title_description_and_link_unchanged():
    (warning,) = ww.parse(feed(GLOS_RAIN))
    assert warning["title"] == "Yellow warning of rain affecting South West England"
    assert warning["description"].startswith("Yellow warning of rain affecting South West England: Bristol")
    assert warning["link"] == LINK.format(day="2026-11-01", id="abc-123").replace("&amp;", "&")


def test_a_warning_running_into_the_new_year_ends_the_next_year():
    (warning,) = ww.parse(feed(item(
        "Amber warning of snow affecting South West England",
        "Amber warning of snow affecting South West England: Gloucestershire "
        "valid from 1800 Thu 31 Dec to 1200 Fri 01 Jan",
        day="2026-12-31",
    )))
    assert warning["starts"] == "2026-12-31T18:00" and warning["ends"] == "2027-01-01T12:00"


def test_only_warnings_listing_gloucestershire_are_kept():
    warnings = ww.parse(feed(GLOS_RAIN, CORNWALL_WIND))
    assert [w["id"] for w in ww.local_warnings(warnings)] == ["abc-123"]


def test_south_gloucestershire_alone_is_not_gloucestershire():
    warnings = ww.parse(feed(item(
        "Yellow warning of fog affecting South West England",
        "Yellow warning of fog affecting South West England: Bristol, South Gloucestershire "
        "valid from 0300 Sun 01 Nov to 1000 Sun 01 Nov",
    )))
    assert ww.local_warnings(warnings) == []


def test_a_warning_whose_areas_cannot_be_read_is_kept_rather_than_missed():
    warnings = ww.parse(feed(item("Red warning of wind affecting South West England", "A description in a new format")))
    (warning,) = ww.local_warnings(warnings)
    assert warning["areas"] is None and warning["starts"] is None
    assert warning["level"] == "Red" and warning["hazard"] == "wind"


def test_an_empty_feed_has_no_warnings():
    assert ww.parse(feed()) == []


def test_alert_shows_the_met_office_title_and_end_time_linking_to_the_met_office():
    html = ww.build_alert_html(ww.parse(feed(GLOS_RAIN)))
    assert 'latest-pill-announcements">Weather warning</span>' in html
    assert ">Yellow warning of rain affecting South West England, until Sunday 1 November 2026 (21:00)</a>" in html
    assert 'href="https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings#?date=2026-11-01&id=abc-123' in html


def test_alert_is_empty_with_no_warnings():
    assert ww.build_alert_html([]) == ""


def test_feed_entries_keep_the_met_office_wording_and_link():
    records = [dict(ww.parse(feed(GLOS_RAIN))[0], first_seen_iso="2026-10-31T21:00:00Z",
                    updated_iso="2026-11-01T08:00:00Z")]
    (entry,) = ww.build_atom_items(records)
    assert entry["title"] == "Yellow warning of rain affecting South West England"
    assert entry["summary"].startswith("Yellow warning of rain affecting South West England: Bristol")
    assert entry["link"].startswith("https://www.metoffice.gov.uk/weather/warnings-and-advice/uk-warnings#?")
    assert entry["published_iso"] == "2026-11-01T08:00:00Z" and entry["source"] == "Met Office"
    assert len(ww.build_atom_items(records * 60)) == 50


def test_log_only_changes_when_a_warning_starts_changes_or_ends():
    (warning,) = ww.parse(feed(GLOS_RAIN))
    log = ww.update_log([], [warning], "2026-10-31T21:00:00Z")
    assert log == [dict(warning, first_seen_iso="2026-10-31T21:00:00Z", updated_iso="2026-10-31T21:00:00Z")]
    assert ww.update_log([dict(r) for r in log], [warning], "2026-10-31T21:05:00Z") == log
    longer = dict(warning, ends="2026-11-02T06:00")
    (record,) = ww.update_log([dict(r) for r in log], [longer], "2026-11-01T07:00:00Z")
    assert record["ends"] == "2026-11-02T06:00" and record["updated_iso"] == "2026-11-01T07:00:00Z"
    assert record["first_seen_iso"] == "2026-10-31T21:00:00Z"
    (ended,) = ww.update_log([record], [], "2026-11-02T06:05:00Z")
    assert ended["resolved_iso"] == "2026-11-02T06:05:00Z"
    assert ww.update_log([dict(ended)], [], "2026-11-02T06:10:00Z") == [ended]


EMPTY_ALERT = "<!-- weather_warnings_alert_marker starts -->\n\n<!-- weather_warnings_alert_marker ends -->"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_main_run_writes_data_history_feed_and_alert_then_logs_the_warning_as_ended(tmp_path, monkeypatch):
    for folder in ("_data", "feeds", "_includes"):
        (tmp_path / folder).mkdir()
    alert = tmp_path / "_includes" / "weather-warnings-alert.html"
    alert.write_text(EMPTY_ALERT)
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse(feed(GLOS_RAIN, CORNWALL_WIND)))
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    rebuilt = []
    monkeypatch.setattr(alerts_feed, "rebuild", lambda: rebuilt.append(True))

    runpy.run_path(str(SCRIPT), run_name="__main__")

    data = json.loads((tmp_path / "_data" / "weather-warnings.json").read_text())
    assert [w["id"] for w in data["warnings"]] == ["abc-123"] and data["count"] == 1
    assert data["source"] == "Met Office"
    history = json.loads((tmp_path / "_data" / "weather-warnings-history.json").read_text())
    assert [r["id"] for r in history["records"]] == ["abc-123"]
    feed_xml = (tmp_path / "feeds" / "weather-warnings.xml").read_text()
    assert "Yellow warning of rain affecting South West England" in feed_xml
    assert "Cornwall, Devon" not in feed_xml
    assert "until Sunday 1 November 2026 (21:00)" in alert.read_text()
    assert rebuilt == [True]

    # The warning drops out of the Met Office feed: the alert clears and the history marks it ended.
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse(feed()))
    runpy.run_path(str(SCRIPT), run_name="__main__")
    assert alert.read_text() == EMPTY_ALERT
    (record,) = json.loads((tmp_path / "_data" / "weather-warnings-history.json").read_text())["records"]
    assert record["resolved_iso"]
