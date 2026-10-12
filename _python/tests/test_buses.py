"""Offline tests for the Pi's bus disruptions fetcher (pi/buses.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


buses = _load("buses", "pi/buses.py")


def test_a_gloucestershire_authority_disruption_is_local():
    assert buses.row_is_local({"Organisation": "Gloucestershire County Council"}, [])


def test_a_disruption_naming_a_local_operator_is_local():
    assert buses.row_is_local({"Organisation": "Somewhere Else", "Operators Affected": "Stagecoach West"}, ["stagecoach"])


def test_an_unrelated_disruption_is_not_local():
    assert not buses.row_is_local({"Organisation": "Leeds", "Operators Affected": "First Leeds"}, ["stagecoach"])


def test_disruption_names_are_title_cased_and_keyed_by_situation_number():
    disruption = buses.build_disruption({
        "Organisation": "GLOUCESTERSHIRE COUNTY COUNCIL", "Situation Number": "SIT-1",
        "Reason": "ROADWORKS", "Operators Affected": "STAGECOACH WEST",
    })
    assert disruption["organisation"] == "Gloucestershire County Council"
    assert disruption["reason"] == "Roadworks"
    assert disruption["operators_affected"] == "Stagecoach West"
    assert disruption["disruption_id"] == "SIT-1"


def test_a_disruption_without_a_situation_number_gets_a_composite_key():
    disruption = buses.build_disruption({"Organisation": "Cheltenham", "Reason": "Event", "Validity Start Date": "2026-10-12"})
    assert disruption["disruption_id"] == "Cheltenham|Event|2026-10-12"


def test_no_disruptions_means_no_alert():
    assert buses.build_alert_html([]) == ""


def test_alert_gives_when_the_disruption_starts_not_when_the_script_ran():
    html = buses.build_alert_html([{"operators_affected": "Stagecoach West", "organisation": "",
                                    "validity_start": "2026-10-12T08:30:00+01:00"}])
    assert "Stagecoach West bus services from 2026-10-12 08:30" in html


def test_alert_without_a_start_time_just_names_the_operator():
    html = buses.build_alert_html([{"operators_affected": "", "organisation": "Gloucestershire County Council",
                                    "validity_start": ""}])
    assert "Disruption to Gloucestershire County Council bus services</a>" in html
