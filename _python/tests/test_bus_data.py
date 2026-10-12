"""Offline tests for the bus routes fetcher (bus-data.py): which BODS rows
count as Cheltenham routes, attention labels, and the de-duplication of
route variations in the main run.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
import runpy

import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "bus-data.py"
SPEC = importlib.util.spec_from_file_location("bus_data", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bus = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bus)


def row(service, start="CHELTENHAM", finish="GLOUCESTER", operator="STAGECOACH WEST",
        modified="2026-01-01T10:00:00", attention="No", timeliness="Up to date", **extra):
    return {
        "OTC:Service Number": service,
        "OTC:Operator Name": operator,
        "OTC:Start Point": start,
        "OTC:Finish Point": finish,
        "XML:Last Modified Date": modified,
        "Requires Attention": attention,
        "Timeliness Status": timeliness,
        **extra,
    }


def test_rows_serve_cheltenham_by_any_route_field_but_not_new_cheltenham():
    assert bus.row_serves_cheltenham({"OTC:Via": "Prestbury, Cheltenham"})
    assert bus.row_serves_cheltenham({"OTC:Destination": "CHELTENHAM SPA"})
    assert not bus.row_serves_cheltenham({"OTC:Origin": "Gloucester", "OTC:Via": None})
    assert not bus.row_serves_cheltenham({"OTC:Origin": "Yate", "OTC:Via": "New Cheltenham, Kingswood"})


def test_school_routes_are_spotted_from_the_service_type():
    assert bus.row_is_school_route({"OTC:Service Type Description": "School or Works"})
    assert not bus.row_is_school_route({"OTC:Service Type Description": None})


def test_timeliness_labels_are_reworded_for_readers():
    assert bus.timeliness_label({"Timeliness Status": "Stale - 42 day look ahead is incomplete"}) == \
        "Timetable doesn't look far enough ahead"
    assert bus.timeliness_label({"Timeliness Status": "Something new"}) == "Something new"
    assert bus.timeliness_label({}) == "Unknown"


def run_main(monkeypatch, rows):
    monkeypatch.setattr(helper, "fetch_bods_csv", lambda *args: rows)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    runpy.run_path(str(SCRIPT), run_name="__main__")
    return written


def test_main_run_merges_variations_and_keeps_any_attention_flag(monkeypatch):
    rows = [
        row("94", modified="2026-03-01T00:00:00"),
        row("94", modified="2025-01-01T00:00:00", attention="Yes",
            timeliness="Service hasn't been updated within a year"),
        row("D", operator="PULHAMS", start="BOURTON", finish="CHELTENHAM",
            **{"OTC:Service Type Description": "School"}),
        row("X", start="BRISTOL", finish="BATH"),
    ]
    written = run_main(monkeypatch, rows)

    payload = written["payload"]
    assert written["path"].name == "bus-routes.json"
    assert payload["total_routes"] == 2
    assert payload["operators"] == ["Pulhams", "Stagecoach West"]
    assert (payload["attention_count"], payload["school_route_count"]) == (1, 1)
    pulhams, stagecoach = payload["routes"]
    assert pulhams["is_school"] and pulhams["start_point"] == "Bourton"
    assert stagecoach["last_modified"] == "2026-03-01"
    assert stagecoach["requires_attention"] is True
    assert stagecoach["timeliness"] == "Not updated in over a year"


def test_main_run_marks_a_route_school_if_any_variation_is(monkeypatch):
    rows = [row("801", modified="2026-02-01"),
            row("801", modified="2025-02-01", **{"OTC:Service Type Description": "School"})]
    routes = run_main(monkeypatch, rows)["payload"]["routes"]
    assert len(routes) == 1 and routes[0]["is_school"] is True
