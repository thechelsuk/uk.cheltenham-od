"""Offline tests for the bin collection weeks fetcher.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "bin_weeks", pathlib.Path(__file__).resolve().parents[1] / "bin-weeks.py"
)
assert SPEC is not None and SPEC.loader is not None
bin_weeks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bin_weeks)

ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20221205\r
RRULE:FREQ=WEEKLY;WKST=MO;INTERVAL=2;BYDAY=MO,TU,WE,TH,FR\r
SUMMARY:Week 1\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20221212\r
RRULE:FREQ=WEEKLY;WKST=MO;INTERVAL=2;BYDAY=MO,TU,WE,TH,FR\r
SUMMARY:Week 2\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_reads_the_first_monday_of_each_week_from_the_calendar():
    assert bin_weeks.parse_anchors(ICS) == {
        1: datetime.date(2022, 12, 5),
        2: datetime.date(2022, 12, 12),
    }


def test_works_out_week_1_and_week_2_for_later_mondays():
    anchors = bin_weeks.parse_anchors(ICS)
    assert bin_weeks.week_number(datetime.date(2026, 10, 12), anchors) == 2
    assert bin_weeks.week_number(datetime.date(2026, 10, 19), anchors) == 1


def test_lists_weeks_from_the_monday_of_the_given_day():
    anchors = bin_weeks.parse_anchors(ICS)
    weeks = bin_weeks.upcoming_weeks(datetime.date(2026, 10, 14), anchors, count=2, holidays=[])
    assert weeks == [
        {"start": "2026-10-12", "end": "2026-10-16", "week": 2, "bank_holidays": []},
        {"start": "2026-10-19", "end": "2026-10-23", "week": 1, "bank_holidays": []},
    ]


def test_flags_a_bank_holiday_on_a_weekday():
    anchors = bin_weeks.parse_anchors(ICS)
    holidays = [{"date": "2026-12-25", "title": "Christmas Day"}, {"date": "2026-12-26", "title": "Boxing Day"}]
    weeks = bin_weeks.upcoming_weeks(datetime.date(2026, 12, 21), anchors, count=1, holidays=holidays)
    assert weeks[0]["bank_holidays"] == [{"date": "2026-12-25", "title": "Christmas Day"}]
