"""Offline tests for the Pi's bus disruptions fetcher (pi/buses.py). The
main run is pointed at a temporary folder, with the BODS download and the
alerts feed rebuild faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy

import alerts_feed
import helper


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


def row(**fields):
    base = {"Organisation": "GLOUCESTERSHIRE COUNTY COUNCIL", "Situation Number": "S1",
            "Validity Start Date": "2026-10-12T08:00:00", "Validity End Date": "2026-10-20T18:00:00",
            "Reason": "ROADWORKS", "Planned": "True", "Modes Affected": "BUS",
            "Operators Affected": "STAGECOACH WEST", "Services Affected": "94", "Stops Affected": ""}
    base.update(fields)
    return base


def test_local_operators_come_from_bus_routes_or_the_fallback_list(tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    assert buses.local_operator_terms() == buses.FALLBACK_OPERATOR_TERMS
    (tmp_path / "_data").mkdir()
    routes = tmp_path / "_data" / "bus-routes.json"
    routes.write_text(json.dumps({"operators": []}))
    assert buses.local_operator_terms() == buses.FALLBACK_OPERATOR_TERMS
    routes.write_text(json.dumps({"operators": ["Stagecoach West", "Pulhams"]}))
    assert buses.local_operator_terms() == ["stagecoach west", "pulhams"]


def test_disruption_columns_are_read_under_either_spelling():
    disruption = buses.build_disruption({"ID": "X9", "Validity start": "2026-10-13", "Modes affected": "bus"})
    assert disruption["situation_number"] == "X9" and disruption["validity_start"] == "2026-10-13"
    assert disruption["reason"] == "Unknown" and disruption["modes_affected"] == "Bus"


def test_alert_time_shortens_iso_times_and_keeps_other_text():
    assert buses.alert_time("2026-10-12") == "2026-10-12"
    assert buses.alert_time(" next Monday ") == "next Monday"
    assert buses.alert_time(None) == ""


def test_the_alert_lists_at_most_five_disruptions():
    disruptions = [buses.build_disruption(row(**{"Situation Number": f"S{i}"})) for i in range(7)]
    html = buses.build_alert_html(disruptions)
    assert html.startswith("<h2>Bus Disruption Alert</h2>\n<ul>\n") and html.endswith("</ul>")
    assert html.count("<li>") == 5


def test_feed_entries_link_by_id_and_are_dated_by_when_last_seen():
    records = [{"disruption_id": "S1", "reason": "Roadworks", "operators_affected": "Stagecoach West",
                "organisation": "GCC", "modes_affected": "Bus", "validity_start": "2026-10-12",
                "validity_end": "2026-10-20", "first_seen_iso": "2026-10-01T00:00:00Z",
                "last_seen_iso": "2026-10-12T09:00:00Z"},
               {"disruption_id": "S2", "first_seen_iso": "2026-10-02T00:00:00Z"}]
    first, second = buses.build_atom_items(records, "https://example.org/history")
    assert first == {"title": "Roadworks: Stagecoach West", "link": "https://example.org/history#S1",
                     "summary": "Modes affected: Bus · From: 2026-10-12 · To: 2026-10-20",
                     "published_iso": "2026-10-12T09:00:00Z", "source": "GCC"}
    assert second == {"title": "Disruption: Cheltenham", "link": "https://example.org/history#S2",
                      "summary": "Disruption: Cheltenham", "published_iso": "2026-10-02T00:00:00Z",
                      "source": "DfT Bus Open Data Service"}
    assert len(buses.build_atom_items(records * 30, "x")) == 50


EMPTY_ALERT = "<!-- bus_alert_marker starts -->\n\n<!-- bus_alert_marker ends -->"


def test_main_run_writes_data_history_feed_and_alert(tmp_path, monkeypatch):
    for folder in ("_data", "feeds", "_includes"):
        (tmp_path / folder).mkdir()
    alert = tmp_path / "_includes" / "bus-alert.html"
    alert.write_text(EMPTY_ALERT)
    rows = [row(), row(Organisation="Bristol City Council",
                       **{"Situation Number": "FAR", "Operators Affected": "FIRST BRISTOL"})]
    rebuilt = []
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    monkeypatch.setattr(helper, "fetch_bods_csv", lambda name, url: rows)
    monkeypatch.setattr(alerts_feed, "rebuild", lambda: rebuilt.append(True))
    script = str(pathlib.Path(__file__).resolve().parents[1] / "pi" / "buses.py")

    runpy.run_path(script, run_name="__main__")

    data = json.loads((tmp_path / "_data" / "bus-disruptions.json").read_text())
    assert data["count"] == 1 and data["disruptions"][0]["disruption_id"] == "S1"
    history = json.loads((tmp_path / "_data" / "bus-disruptions-history.json").read_text())
    assert [r["disruption_id"] for r in history["records"]] == ["S1"]
    assert "https://example.org/cheltenham-bus-data/history#S1" in (tmp_path / "feeds" / "bus-disruptions.xml").read_text()
    assert "Disruption to Stagecoach West bus services from 2026-10-12 08:00" in alert.read_text()
    assert rebuilt == [True]

    # Once the disruption has gone the alert clears, but the history keeps it.
    monkeypatch.setattr(helper, "fetch_bods_csv", lambda name, url: [])
    runpy.run_path(script, run_name="__main__")
    assert alert.read_text() == EMPTY_ALERT
    history = json.loads((tmp_path / "_data" / "bus-disruptions-history.json").read_text())
    assert [r["disruption_id"] for r in history["records"]] == ["S1"]
