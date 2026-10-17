"""Offline tests for the Pi's train times fetcher (pi/rail-times.py). The
board request is faked and the data file goes to a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
from datetime import datetime, timedelta

import pytest

import helper


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rail = _load("rail_times", "pi/rail-times.py")
GENERATED = datetime(2026, 10, 12, 23, 50, tzinfo=rail.LONDON)


def test_a_time_after_midnight_rolls_into_the_next_day():
    assert rail.resolve_time("00:10", GENERATED).date().isoformat() == "2026-10-13"
    assert rail.resolve_time("23:55", GENERATED).date().isoformat() == "2026-10-12"


def test_an_on_time_departure():
    service = {"std": "23:55", "etd": "On time", "platform": "1", "operator": "CrossCountry",
               "destination": [{"locationName": "Bristol Temple Meads"}]}
    item = rail.parse_service(service, "departure", GENERATED)
    assert item["status"] == "On time"
    assert item["scheduled"] == "2026-10-12T23:55"
    assert item["destination"] == "Bristol Temple Meads"
    assert item["calling_at"] == []


def test_a_late_estimate_is_delayed_and_a_cancellation_is_cancelled():
    late = rail.parse_service({"std": "23:55", "etd": "23:59"}, "departure", GENERATED)
    assert late["status"] == "Delayed" and late["expected"] == "2026-10-12T23:59"
    cancelled = rail.parse_service({"sta": "23:55", "eta": "Cancelled", "cancelReason": "<p>A fault</p>"}, "arrival", GENERATED)
    assert cancelled["status"] == "Cancelled" and cancelled["reason"] == "A fault"


def test_a_service_without_a_scheduled_time_is_skipped():
    assert rail.parse_service({"sta": "23:55"}, "departure", GENERATED) is None


def test_station_messages_are_plain_text_without_repeats():
    board = {"nrccMessages": [{"value": "<p>Lifts &amp; escalators closed</p>"}, {"value": "Lifts & escalators closed"}]}
    assert rail.station_messages(board) == ["Lifts & escalators closed"]


def test_station_messages_read_the_capitalised_value_key_the_api_sends():
    board = {"nrccMessages": [{"Value": "No trains this weekend because of engineering work."}]}
    assert rail.station_messages(board) == ["No trains this weekend because of engineering work."]


def test_board_time_reads_the_seven_digit_timestamp_or_falls_back_to_now():
    board = {"generatedAt": "2026-10-12T23:50:01.1234567+01:00"}
    assert rail.board_time(board) == datetime(2026, 10, 12, 23, 50, 1, 123456, tzinfo=rail.LONDON)
    assert abs(rail.board_time({}) - datetime.now(rail.LONDON)) < timedelta(minutes=1)


@pytest.mark.parametrize("estimate, status, expected", [
    ("23:55", "On time", "2026-10-12T23:55"),
    ("Delayed", "Delayed", None),
    ("", "No report", None),
    ("Starts here", "No report", None),
])
def test_other_estimates(estimate, status, expected):
    item = rail.parse_service({"std": "23:55", "etd": estimate}, "departure", GENERATED)
    assert (item["status"], item["expected"]) == (status, expected)


def test_a_cancelled_flag_wins_over_the_estimate():
    item = rail.parse_service({"sta": "23:55", "eta": "On time", "isCancelled": True,
                               "delayReason": "Signalling"}, "arrival", GENERATED)
    assert item["status"] == "Cancelled" and item["reason"] == "Signalling"
    assert "calling_at" not in item


def test_place_names_and_calling_points():
    assert rail.place_names([{"locationName": "Bristol Temple Meads"},
                             {"locationName": "Cardiff Central", "via": "via Newport"}, {}]) == \
        "Bristol Temple Meads and Cardiff Central via Newport"
    assert rail.place_names(None) == ""
    service = {"subsequentCallingPoints": [
        {"callingPoint": [{"locationName": "Gloucester"}, {"locationName": "Bristol Parkway"}]},
        {"callingPoint": [{"locationName": "Gloucester"}, {"locationName": "Cardiff Central"}, {}]},
    ]}
    assert rail.calling_at(service) == ["Gloucester", "Bristol Parkway", "Cardiff Central"]


BOARD = {
    "generatedAt": "2026-10-12T23:50:00+01:00",
    "trainServices": [
        {"std": "00:15", "etd": "On time"},                    # after midnight, so last
        {"sta": "23:52", "eta": "On time", "std": "23:54", "etd": "On time"},
        {"sta": "23:58", "eta": "On time"},                    # terminates here
    ],
    "nrccMessages": [{"value": "Ticket office closed"}],
}


def test_parse_board_splits_departures_from_arrivals_in_time_order(monkeypatch):
    assert [s["scheduled"] for s in rail.parse_board(BOARD, "departure")] == ["2026-10-12T23:54", "2026-10-13T00:15"]
    assert [s["scheduled"] for s in rail.parse_board(BOARD, "arrival")] == ["2026-10-12T23:52", "2026-10-12T23:58"]
    monkeypatch.setattr(rail, "MAX_SERVICES", 1)
    assert len(rail.parse_board(BOARD, "departure")) == 1
    assert rail.parse_board({}, "arrival") == []


def test_rail_replacement_buses_join_the_board_marked_as_buses():
    board = {
        "generatedAt": "2026-10-12T23:50:00+01:00",
        "trainServices": [{"std": "23:58", "etd": "On time", "platform": "1"}],
        "busServices": [{"std": "23:55", "etd": "On time", "platform": "BUS"}],
    }
    departures = rail.parse_board(board, "departure")
    assert [(s["scheduled"], s["mode"]) for s in departures] == [("2026-10-12T23:55", "bus"), ("2026-10-12T23:58", "train")]
    assert rail.parse_board({"busServices": [{"sta": "23:55", "eta": "On time"}]}, "arrival")[0]["mode"] == "bus"


def test_unchanged_only_within_the_heartbeat(tmp_path, monkeypatch):
    out = tmp_path / "rail-times.json"
    monkeypatch.setattr(rail, "OUT", out)
    now = datetime(2026, 10, 12, 12, 0, tzinfo=rail.LONDON)
    new = {"messages": [], "departures": [{"a": 1}], "arrivals": []}
    assert not rail.unchanged(new, now)
    out.write_text(json.dumps({**new, "generated_at": (now - timedelta(minutes=10)).isoformat()}))
    assert rail.unchanged(new, now)
    assert not rail.unchanged({**new, "arrivals": [{"b": 2}]}, now)
    assert not rail.unchanged(new, now + timedelta(minutes=25))
    out.write_text("{}")
    assert not rail.unchanged(new, now)


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return BOARD


def test_fetch_board_sends_the_key(monkeypatch):
    seen = {}
    monkeypatch.setattr(rail.requests, "get",
                        lambda url, params, headers, timeout: seen.update(url=url, params=params, headers=headers)
                        or FakeResponse())
    assert rail.fetch_board("test-key") == BOARD
    assert seen["url"].endswith("/GetArrDepBoardWithDetails/CNM")
    assert seen["params"] == {"numRows": rail.NUM_ROWS} and seen["headers"]["x-apikey"] == "test-key"


def test_main_needs_the_key(monkeypatch):
    monkeypatch.delenv("RDM_LDBWS_KEY", raising=False)
    with pytest.raises(SystemExit, match="RDM_LDBWS_KEY"):
        rail.main()


@pytest.fixture
def paths(tmp_path, monkeypatch):
    """Point every file main() writes at a temporary folder."""
    include = tmp_path / "rail-alert.html"
    include.write_text("<!-- rail_alert_marker starts -->\n\n<!-- rail_alert_marker ends -->")
    monkeypatch.setattr(rail, "OUT", tmp_path / "rail-times.json")
    monkeypatch.setattr(rail, "HISTORY", tmp_path / "rail-disruptions-history.json")
    monkeypatch.setattr(rail, "FEED", tmp_path / "rail-disruptions.xml")
    monkeypatch.setattr(rail, "ALERT_INCLUDE", include)
    monkeypatch.setattr(rail.alerts_feed, "rebuild", lambda: None)
    return tmp_path


def test_main_writes_the_board_then_leaves_an_unchanged_one_alone(paths, monkeypatch):
    out = paths / "rail-times.json"
    monkeypatch.setenv("RDM_LDBWS_KEY", "test-key")
    monkeypatch.setattr(rail, "fetch_board", lambda key: BOARD)

    rail.main()
    data = json.loads(out.read_text())
    assert data["station"] == {"name": "Cheltenham Spa", "crs": "CNM"}
    assert data["messages"] == ["Ticket office closed"]
    assert (len(data["departures"]), len(data["arrivals"])) == (2, 2)

    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(path))
    rail.main()
    assert rail.OUT not in written


BUSES_ONLY = {
    "generatedAt": "2026-10-17T12:20:00+01:00",
    "busServices": [{"std": "12:30", "etd": "On time", "platform": "BUS",
                     "destination": [{"locationName": "Worcester Foregate Street"}]}],
    "nrccMessages": [{"Value": "Lifts closed"},
                     {"Value": "There are no train services at this station today because of engineering work."}],
}


def test_only_a_board_with_buses_and_no_trains_counts_as_replacement_buses_only():
    assert rail.replacement_buses_only(BUSES_ONLY)
    assert not rail.replacement_buses_only({**BUSES_ONLY, "trainServices": [{"std": "12:40"}]})
    assert not rail.replacement_buses_only({})


def test_the_disruption_message_is_the_one_about_trains_or_a_standard_line():
    messages = rail.station_messages(BUSES_ONLY)
    assert rail.disruption_message(messages).startswith("There are no train services")
    assert rail.disruption_message(["Lifts closed"]) == rail.DEFAULT_DISRUPTION_MESSAGE


def test_a_disruption_keeps_its_id_while_it_lasts_and_a_new_one_gets_todays_date():
    assert rail.current_disruptions({}, [], [], "2026-10-17T11:20:00Z") == []
    first = rail.current_disruptions(BUSES_ONLY, ["Engineering work"], [], "2026-10-17T11:20:00Z")
    assert first == [{"disruption_id": "rail-replacement-2026-10-17", "message": "Engineering work"}]
    ongoing = [{"disruption_id": "rail-replacement-2026-10-16"}]
    assert rail.current_disruptions(BUSES_ONLY, [], ongoing, "2026-10-17T11:20:00Z")[0]["disruption_id"] == \
        "rail-replacement-2026-10-16"
    ended = [{"disruption_id": "rail-replacement-2026-10-10", "resolved_iso": "2026-10-11T22:00:00Z"}]
    assert rail.current_disruptions(BUSES_ONLY, [], ended, "2026-10-17T11:20:00Z")[0]["disruption_id"] == \
        "rail-replacement-2026-10-17"


def test_the_homepage_alert_only_shows_while_a_disruption_is_live():
    assert rail.build_alert_html([]) == ""
    html = rail.build_alert_html([{"disruption_id": "x", "message": "m"}])
    assert "<h2>Rail Disruption Alert</h2>" in html and 'href="/cheltenham-train-times"' in html


def test_feed_entries_are_dated_by_start_then_by_end():
    history = [
        {"disruption_id": "rail-replacement-2026-10-17", "message": "No trains", "first_seen_iso": "2026-10-17T06:00:00Z"},
        {"disruption_id": "rail-replacement-2026-10-10", "message": "No trains", "first_seen_iso": "2026-10-10T06:00:00Z",
         "resolved_iso": "2026-10-11T22:00:00Z"},
    ]
    live, ended = rail.build_atom_items(history, "https://example.org/cheltenham-train-times")
    assert live["published_iso"] == "2026-10-17T06:00:00Z" and live["summary"] == "No trains"
    assert live["link"] == "https://example.org/cheltenham-train-times#rail-replacement-2026-10-17"
    assert ended["title"].endswith("ended") and ended["published_iso"] == "2026-10-11T22:00:00Z"


def test_main_records_a_replacement_bus_day_in_the_alert_feed_and_data(paths, monkeypatch):
    monkeypatch.setenv("RDM_LDBWS_KEY", "test-key")
    monkeypatch.setattr(rail, "fetch_board", lambda key: BUSES_ONLY)
    rail.main()
    data = json.loads((paths / "rail-times.json").read_text())
    assert data["replacement_buses_only"] is True
    assert data["departures"][0]["mode"] == "bus"
    history = json.loads((paths / "rail-disruptions-history.json").read_text())["records"]
    assert [r["message"] for r in history] == [rail.disruption_message(data["messages"])]
    assert "Rail Disruption Alert" in (paths / "rail-alert.html").read_text()
    assert "Rail replacement buses" in (paths / "rail-disruptions.xml").read_text()

    monkeypatch.setattr(rail, "fetch_board", lambda key: BOARD)
    rail.main()
    assert "Rail Disruption Alert" not in (paths / "rail-alert.html").read_text()
    assert json.loads((paths / "rail-times.json").read_text())["replacement_buses_only"] is False
