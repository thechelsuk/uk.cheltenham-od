"""Offline tests for the one-off COVID-19 history generator
(local/process-covid.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "process_covid", pathlib.Path(__file__).resolve().parents[1] / "local" / "process-covid.py"
)
covid = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(covid)


def row(date, value, **extra):
    return {"date": date, "metric_value": value, "stratum": "default", "sex": "all", "age": "all", **extra}


def test_in_range_keeps_feb_2020_to_dec_2023_only():
    rows = [row("2020-01-31", 1), row("2020-02-01", 2), row("2023-12-31", 3), row("2024-01-01", 4)]
    assert [r["metric_value"] for r in covid.in_range(rows)] == [2, 3]


def test_week_start_is_the_monday():
    assert covid.week_start("2021-01-06") == "2021-01-04"   # a Wednesday
    assert covid.week_start("2021-01-04") == "2021-01-04"   # already a Monday
    assert covid.week_start("2021-01-10") == "2021-01-04"   # the Sunday


def test_weekly_sums_means_and_takes_the_last_value():
    rows = [row("2021-01-04", 10), row("2021-01-05", 20), row("2021-01-11", 5), row("2021-01-12", None)]
    assert covid.weekly(rows, "sum") == [{"week": "2021-01-04", "value": 30}, {"week": "2021-01-11", "value": 5}]
    assert covid.weekly(rows, "mean") == [{"week": "2021-01-04", "value": 15}, {"week": "2021-01-11", "value": 5}]
    assert covid.weekly(rows, "last") == [{"week": "2021-01-04", "value": 20}, {"week": "2021-01-11", "value": 5}]


def test_weekly_skips_breakdowns_other_than_all():
    rows = [row("2021-01-04", 10), row("2021-01-04", 99, sex="f")]
    assert covid.weekly(rows, "sum") == [{"week": "2021-01-04", "value": 10}]


def test_yearly_totals_count_each_day_in_its_own_calendar_year():
    # 2020-12-31 and 2021-01-01 share a week but belong to different years
    rows = [row("2020-12-31", 3), row("2021-01-01", 4), row("2021-06-07", 1), row("2021-06-07", 50, sex="m")]
    assert covid.yearly(rows) == {"2020": 3, "2021": 5}


def test_peak_is_the_highest_week_and_the_earliest_on_a_tie():
    weeks = [{"week": "2021-01-04", "value": 9}, {"week": "2022-01-03", "value": 9}, {"week": "2021-07-05", "value": 2}]
    assert covid.peak(weeks) == {"week": "2021-01-04", "value": 9}
    assert covid.peak([]) is None


def test_uptake_at_cutoff_takes_the_last_value_per_age_for_everyone():
    rows = [
        row("2023-10-01", 20.0, age="65+"),
        row("2023-12-20", 60.5, age="65+"),
        row("2024-01-10", 62.0, age="65+"),   # after the cut-off
        row("2023-12-20", 58.0, age="65+", sex="f"),
        row("2023-12-20", 70.1, age="80+"),
    ]
    assert covid.uptake_at_cutoff(rows) == [
        {"age": "65+", "uptake": 60.5, "date": "2023-12-20"},
        {"age": "80+", "uptake": 70.1, "date": "2023-12-20"},
    ]
