"""Offline tests for the power cuts fetcher's Cheltenham postcode filter.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import pytest

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
