"""Offline tests for the unplanned road closures fetcher
(pi/unplanned-closures.py), using records in the shape National Highways'
Road and Lane Closures v2 service returns.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "unplanned_closures", pathlib.Path(__file__).resolve().parents[1] / "pi" / "unplanned-closures.py"
)
unplanned = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(unplanned)


def record(rid, status, pos, description="M5 northbound between J11 and J10", kind="laneClosures",
           start="2026-10-08T17:22:35.35Z", end="2026-10-08T17:37:35.35Z", group=False):
    linear = {
        "gmlLineString": {"locGmlLineString": {"posList": pos}},
        "supplementaryPositionalDescription": {"locationDescription": description},
    }
    location = (
        {"locLocationGroupByList": {"locationContainedInGroup": [{"locLinearLocation": linear}]}}
        if group else {"locLinearLocation": linear}
    )
    location["locSingleRoadLinearLocation"] = {"linearWithinLinearElement": [
        {"linearElement": {"locLinearElementByCode": {"roadName": description.split()[0]}}}]}
    return {"sitRoadOrCarriagewayOrLaneManagement": {
        "idG": rid,
        "roadOrCarriagewayOrLaneManagementType": {"value": kind},
        "source": {"sourceIdentification": "Signs and Signals"},
        "validity": {"validityStatus": status, "validityTimeSpecification": {
            "overallStartTime": start, "overallEndTime": end}},
        "locationReference": location,
    }}


def payload(*records):
    return {"D2Payload": {"situation": [{"situationRecord": [r]} for r in records]}}


def test_closure_label_reads_as_words():
    assert unplanned.closure_label("laneClosures") == "Lane closures"
    assert unplanned.closure_label("carriagewayClosures") == "Carriageway closures"
    assert unplanned.closure_label("") == "Closure"


def test_local_time_converts_utc_to_uk_time():
    assert unplanned.local_iso("2026-10-08T17:22:35.35Z") == "2026-10-08T18:22"   # BST
    assert unplanned.local_iso("2026-12-08T17:22:35Z") == "2026-12-08T17:22"      # GMT
    assert unplanned.local_iso(None) is None


def test_parse_reads_records_with_one_or_several_locations():
    records = unplanned.parse(payload(
        record("a", "active", "51.95 -2.13 51.96 -2.14"),
        record("b", "suspended", "52.40 -1.50", description="M6 southbound between J3 and J2", group=True),
    ))
    assert [r["id"] for r in records] == ["a", "b"]
    assert records[0]["road"] == "M5"
    assert records[0]["closure"] == "Lane closures"
    assert records[0]["points"] == [(51.95, -2.13), (51.96, -2.14)]
    assert records[1]["description"] == "M6 southbound between J3 and J2"
    assert records[1]["points"] == [(52.40, -1.50)]


def test_local_items_keep_nearby_closures_with_the_nearest_point_and_status():
    records = unplanned.parse(payload(
        record("near", "active", "51.95 -2.13 51.90 -2.10"),
        record("ended", "suspended", "51.92 -2.12"),
        record("far", "active", "53.27 -2.39"),
    ))
    items = unplanned.local_items(records, centre=(51.8994, -2.0783), radius_miles=10)
    assert [i["id"] for i in items] == ["near", "ended"]
    assert items[0]["lat"] == 51.90 and items[0]["lon"] == -2.10
    assert items[0]["status"] == "Active" and items[1]["status"] == "Ended"
    assert items[0]["start"] == "2026-10-08T18:22"
    assert "points" not in items[0]


def test_a_closure_has_ended_once_reported_ended_or_no_longer_seen():
    assert not unplanned.has_ended({"status": "Active"})
    assert unplanned.has_ended({"status": "Ended"})
    # dropped out of the 24-hour window while still marked active
    assert unplanned.has_ended({"status": "Active", "resolved_iso": "2026-10-09T10:00:00Z"})


def test_atom_items_describe_each_closure_and_link_to_its_row():
    history = [
        {"id": "a-1", "road": "M5", "description": "M5 northbound between J11 and J10", "closure": "Lane closures",
         "status": "Active", "start": "2026-10-09T08:15", "end": "2026-10-09T08:30",
         "last_seen_iso": "2026-10-09T07:20:00Z"},
        {"id": "b-2", "road": "A417", "description": "A417 both directions near Birdlip", "closure": "Road closed",
         "status": "Ended", "start": "2026-10-08T22:00", "end": "2026-10-08T23:40",
         "last_seen_iso": "2026-10-08T22:45:00Z"},
    ]
    items = unplanned.build_atom_items(history, "https://example.test/cheltenham-roadworks/unplanned-closures")
    assert items[0]["title"] == "Lane closures: M5 northbound between J11 and J10"
    assert items[0]["link"] == "https://example.test/cheltenham-roadworks/unplanned-closures#a-1"
    assert items[0]["summary"] == "Started 2026-10-09 08:15. Still in force."
    assert items[0]["published_iso"] == "2026-10-09T07:20:00Z"
    assert items[1]["title"] == "Ended: Road closed: A417 both directions near Birdlip"
    assert items[1]["summary"] == "Started 2026-10-08 22:00. Ended 2026-10-08 23:40."
