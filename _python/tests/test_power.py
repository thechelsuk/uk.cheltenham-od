"""Offline tests for the power cuts fetcher (pi/power.py): the Cheltenham
postcode filter, incidents, the homepage alert, feed entries, and the main
run against a temporary folder with the NGED download faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy

import pytest
import requests

import alerts_feed
import helper

SPEC = importlib.util.spec_from_file_location(
    "power", pathlib.Path(__file__).resolve().parents[1] / "pi" / "power.py"
)
assert SPEC is not None and SPEC.loader is not None
power = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(power)


@pytest.mark.parametrize("postcode", ["GL50 1AA", "GL51 0JU", "gl52 3nq", "GL533AB", "GL54 4EU"])
def test_cheltenham_postcodes_match(postcode):
    assert power.is_cheltenham_postcode(postcode)


@pytest.mark.parametrize("postcode", ["GL5 1HH", "GL5 2NJ", "GL51HH", "GL5 5BU", "GL55 1AA", "SY8 2JR", "", "GL51"])
def test_other_postcodes_do_not_match(postcode):
    assert not power.is_cheltenham_postcode(postcode)


def test_row_with_only_stroud_postcodes_is_not_local():
    row = {"postcode": "SY8 2JR, SY8 2JW, GL5 1HH, SY8 2II"}
    assert not power.row_is_local(row)


def _incident(**overrides):
    incident = {
        "fault_id": "INCD-1", "status": "In Progress", "confirmed_off": 4, "predicted_off": 0,
        "restored": 39, "date_of_reported_fault": "2026-10-11T20:40:00", "postcodes": ["GL50 4DB"],
    }
    incident.update(overrides)
    return incident


def test_alert_includes_a_partly_restored_cut_with_homes_still_off():
    html = power.build_alert_html([_incident()])
    assert "GL50 4DB" in html


def test_alert_leaves_out_a_cut_with_no_homes_off():
    assert power.build_alert_html([_incident(confirmed_off=0, predicted_off=0)]) == ""


def test_alert_leaves_out_a_restored_cut():
    assert power.build_alert_html([_incident(status="Restored")]) == ""


def test_alert_gives_the_time_the_cut_was_reported():
    html = power.build_alert_html([_incident()])
    assert "reported 2026-10-11 20:40" in html


def test_incident_counts_properties_affected_as_off_plus_restored():
    row = {"fault_id": "INCD-1", "status": "In Progress", "confirmed_off": "4", "restored": "39",
           "postcode": "GL50 4DB"}
    assert power.build_incident(row)["affected"] == 43


def test_older_history_records_get_properties_affected_filled_in():
    records = [{"fault_id": "A", "confirmed_off": 25, "restored": 39}, {"fault_id": "B", "affected": 7}]
    power.fill_affected(records)
    assert records[0]["affected"] == 39
    assert records[1]["affected"] == 7


def test_planned_cut_keeps_its_start_end_and_properties():
    row = {"fault_id": "INCD-2", "status": "Awaiting", "planned": "true", "postcode": "GL51 0JU",
           "planned_outage_start_date": "2026-10-14T09:00:00", "planned_outage_end_date": "2026-10-14T15:30:00",
           "planned_outage_off": "12"}
    incident = power.build_incident(row)
    assert incident["planned"] is True
    assert incident["planned_start"] == "2026-10-14T09:00:00"
    assert incident["planned_end"] == "2026-10-14T15:30:00"
    assert incident["planned_off"] == 12


def test_unplanned_cut_has_no_planned_times():
    incident = power.build_incident({"fault_id": "INCD-3", "planned": "false", "postcode": "GL50 1AA"})
    assert incident["planned_start"] == ""
    assert incident["planned_off"] == 0


def test_coordinates_are_numbers_or_none():
    incident = power.build_incident({"postcode": "GL50 1AA", "location_latitude": "51.9",
                                     "location_longitude": "bad", "confirmed_off": "x"})
    assert incident["lat"] == 51.9 and incident["lon"] is None and incident["confirmed_off"] == 0


def test_feed_entries_link_by_fault_and_carry_status_and_restoration():
    records = [
        {"fault_id": "INCD-1", "postcodes": ["GL50 4DB"], "status": "Restored", "category": "Low Voltage",
         "confirmed_off": 4, "affected": 43, "date_of_restoration": "2026-10-11T23:00:00",
         "first_seen_iso": "2026-10-11T20:45:00Z", "last_seen_iso": "2026-10-11T23:05:00Z"},
        {"fault_id": "INCD-2", "postcodes": [], "first_seen_iso": "2026-10-12T08:00:00Z"},
    ]
    first, second = power.build_atom_items(records, "https://example.org/history")
    assert first == {"title": "Power cut near GL50 4DB — Restored", "link": "https://example.org/history#INCD-1",
                     "summary": "Low Voltage · 43 properties affected · Restored: 2026-10-11T23:00:00",
                     "published_iso": "2026-10-11T23:05:00Z", "source": "National Grid Electricity Distribution"}
    assert second["title"] == "Power cut near Cheltenham" and second["summary"] == ""
    assert second["published_iso"] == "2026-10-12T08:00:00Z"
    assert len(power.build_atom_items(records * 30, "x")) == 50


CSV_HEADER = ("fault_id,status,planned,category,confirmed_off,predicted_off,restored,"
              "date_of_reported_fault,postcode,location_latitude,location_longitude")
EMPTY_ALERT = "<!-- power_cuts_alert_marker starts -->\n\n<!-- power_cuts_alert_marker ends -->"


class FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def test_main_run_writes_data_history_feed_and_alert_then_marks_the_cut_restored(tmp_path, monkeypatch):
    for folder in ("_data", "feeds", "_includes"):
        (tmp_path / folder).mkdir()
    alert = tmp_path / "_includes" / "power-cuts-alert.html"
    alert.write_text(EMPTY_ALERT)
    csv_text = (CSV_HEADER + "\n"
                'INCD-1,In Progress,false,LOW VOLTAGE,4,0,39,2026-10-11T20:40:00,"GL50 4DB, GL50 4DD",51.9,-2.08\n'
                "INCD-9,In Progress,false,HIGH VOLTAGE,100,0,0,2026-10-11T20:00:00,GL5 1HH,51.7,-2.2\n")
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse(csv_text))
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    rebuilt = []
    monkeypatch.setattr(alerts_feed, "rebuild", lambda: rebuilt.append(True))
    script = str(pathlib.Path(__file__).resolve().parents[1] / "pi" / "power.py")

    runpy.run_path(script, run_name="__main__")

    data = json.loads((tmp_path / "_data" / "power-cuts.json").read_text())
    assert [i["fault_id"] for i in data["incidents"]] == ["INCD-1"]
    assert data["incidents"][0]["category"] == "Low Voltage"
    history = json.loads((tmp_path / "_data" / "power-cuts-history.json").read_text())
    assert [(r["fault_id"], r["affected"]) for r in history["records"]] == [("INCD-1", 43)]
    feed = (tmp_path / "feeds" / "power-cuts.xml").read_text()
    assert "https://example.org/cheltenham-power-cuts/history#INCD-1" in feed
    assert "Power cut near GL50 4DB, reported 2026-10-11 20:40" in alert.read_text()
    assert rebuilt == [True]

    # The cut drops out of the live feed: the alert clears and the history records it as restored.
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse(CSV_HEADER + "\n"))
    runpy.run_path(script, run_name="__main__")
    assert alert.read_text() == EMPTY_ALERT
    (record,) = json.loads((tmp_path / "_data" / "power-cuts-history.json").read_text())["records"]
    assert record["status"] == "Restored" and record["date_of_restoration"] == record["resolved_iso"]
