"""Offline tests for the street works fetcher (street-works.py), which reads
the receiver Worker's /works.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "street_works", pathlib.Path(__file__).resolve().parents[1] / "street-works.py"
)
street_works = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(street_works)

CENTRE = (51.8994, -2.0783)
TODAY = "2026-10-09"


def work(**overrides):
    base = {
        "id": "PERMIT:AB123", "object_type": "PERMIT", "reference": "AB123", "event_type": "WORK_START",
        "event_time": "2026-10-09T08:00:00.000Z", "promoter": "Severn Trent Water", "street_name": "PROMENADE",
        "area_name": "CHELTENHAM", "town": None, "work_category": "Standard", "immediate": False,
        "traffic_management": "Multi-way signals", "status": "Works in progress",
        "proposed_start": "2026-10-08T00:00:00.000Z", "proposed_end": "2026-10-12T00:00:00.000Z",
        "actual_start": "2026-10-09T07:45:00.000Z", "actual_end": None, "lat": 51.8972, "lon": -2.0759,
    }
    return base | overrides


def test_a_nearby_works_is_kept_with_readable_names_and_uk_times():
    [item] = street_works.local_items([work()], CENTRE, 6, TODAY)
    assert item["street"] == "Promenade"
    assert item["area"] == "Cheltenham"
    assert item["kind"] == "Planned"
    assert item["start"] == "2026-10-09T08:45"   # actual start, in BST
    assert item["end"] == "2026-10-12"           # proposed end date, no time given
    assert item["distance_miles"] == 0.2
    assert item["road_closure"] is False


def test_immediate_works_are_unplanned_and_listed_first():
    items = street_works.local_items([
        work(id="a", street_name="HIGH STREET"),
        work(id="b", immediate=True, work_category="Immediate - emergency", traffic_management="Road closure"),
    ], CENTRE, 6, TODAY)
    assert [i["id"] for i in items] == ["b", "a"]
    assert items[0]["kind"] == "Unplanned"
    assert items[0]["road_closure"] is True


def test_far_away_cancelled_finished_and_out_of_date_works_are_dropped():
    items = street_works.local_items([
        work(id="far", lat=51.8642, lon=-2.2382),                     # Gloucester, about 7 miles
        work(id="cancelled", status="Cancelled"),
        work(id="finished", actual_end="2026-10-08T16:00:00.000Z"),
        work(id="never-started", actual_start=None, proposed_end="2026-10-01T00:00:00.000Z"),
        work(id="no-location", lat=None, lon=None),
        work(id="keep"),
    ], CENTRE, 6, TODAY)
    assert [i["id"] for i in items] == ["keep"]


def test_a_planned_works_not_started_shows_its_proposed_dates():
    [item] = street_works.local_items([work(actual_start=None, status=None)], CENTRE, 6, TODAY)
    assert item["start"] == "2026-10-08"
    assert item["status"] == "Planned"


def test_works_are_tagged_with_the_ward_they_fall_in():
    wards = [{"name": "Lansdown", "slug": "lansdown",
              "boundary": [[51.89, -2.09], [51.89, -2.06], [51.91, -2.06], [51.91, -2.09], [51.89, -2.09]]}]
    inside, outside = street_works.local_items(
        [work(id="in"), work(id="out", lat=51.95, lon=-2.08)], CENTRE, 6, TODAY, wards)
    assert (inside["ward"], inside["ward_slug"]) == ("Lansdown", "lansdown")
    assert (outside["ward"], outside["ward_slug"]) == ("", "")


def test_summary_counts_unplanned_closures_and_works_in_progress():
    items = street_works.local_items([
        work(id="a"),
        work(id="b", immediate=True, work_category="Immediate - urgent", traffic_management="Road closure"),
        work(id="c", actual_start=None, status=None),
    ], CENTRE, 6, TODAY)
    assert street_works.summarise(items) == {"total": 3, "unplanned": 1, "road_closures": 1, "in_progress": 2}


def test_planned_dates_are_shown_as_the_uk_date():
    # Street Manager sends midnight UK time as UTC, so 15 October arrives as 14 October 23:00
    [item] = street_works.local_items([work(actual_start=None, status="Works planned",
                                            proposed_start="2026-10-14T23:00:00.000Z",
                                            proposed_end="2026-10-18T23:00:00.000Z")], CENTRE, 6, TODAY)
    assert item["start"] == "2026-10-15"
    assert item["end"] == "2026-10-19"


def test_works_cancelled_and_works_completed_are_dropped():
    items = street_works.local_items([
        work(id="cancelled", status="Works cancelled", actual_start=None),
        work(id="completed", status="Works completed"),
        work(id="keep"),
    ], CENTRE, 6, TODAY)
    assert [i["id"] for i in items] == ["keep"]
