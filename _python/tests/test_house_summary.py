"""Offline tests for the house price summary builder (house_summary.py): the
statistics, change strings, rolling and calendar-year periods, and the
history-file comparisons. Files are written to a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json
from datetime import date

import pytest

import house_summary as hs


def sale(day, amount, new_build=False, ptype="Detached"):
    return {"date": day, "amount": amount, "new_build": new_build, "property_type": ptype}


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Point the raw, summary and history paths at a temporary folder."""
    paths = {"raw": tmp_path / "raw.json", "summary": tmp_path / "summary.json", "history": tmp_path / "history.json"}
    monkeypatch.setattr(hs, "RAW_DATA_PATH", paths["raw"])
    monkeypatch.setattr(hs, "SUMMARY_DATA_PATH", paths["summary"])
    monkeypatch.setattr(hs, "HISTORY_DATA_PATH", paths["history"])
    return paths


def test_normalize_property_type_matches_the_table_default():
    assert hs.normalize_property_type({"property_type": None}) == "Other"
    assert hs.normalize_property_type({"property_type": "  "}) == "Other"
    assert hs.normalize_property_type({"property_type": " OTHER "}) == "Other"
    assert hs.normalize_property_type({"property_type": " Flat-maisonette "}) == "Flat-maisonette"


def test_compute_stats_ignores_missing_amounts():
    assert hs.compute_stats([sale("2026-01-01", None)]) == {"count": 0}
    stats = hs.compute_stats([sale("2026-01-01", 100), sale("2026-01-02", 200), sale("2026-01-03", 400)])
    assert stats == {"count": 3, "median": 200, "mean": 233, "min": 100, "max": 400}


def test_change_strings_say_up_or_down_with_the_earlier_figure():
    assert hs.pct_change(110, 100) == pytest.approx(10)
    assert hs.pct_change(1, 0) is None
    assert hs.change_str(1900, 2000, "2025") == "down 5% (2025: 2,000)"
    assert hs.change_str(330000, 300000, "2025", currency=True) == "up 10% (2025: £300,000)"
    assert hs.change_str(5, 0, "2025") is None
    assert hs.money(1234567) == "£1,234,567"


def test_month_helpers():
    idx = hs.month_index(date(2026, 3, 9))
    assert hs.month_name(idx) == "March 2026"
    assert hs.month_name(idx - 3) == "December 2025"
    assert hs.transaction_date({"date": "2026-03-09T00:00:00"}) == date(2026, 3, 9)
    assert hs.transaction_date({"date": None}) is None


def test_data_bounds_leave_out_part_months_at_either_end():
    first, last = hs.data_bounds([sale("2024-03-15", 1), sale("2026-08-10", 1), {"date": None}])
    assert hs.month_name(first) == "April 2024"
    assert hs.month_name(last) == "July 2026"
    first, _ = hs.data_bounds([sale("2024-03-01", 1), sale("2026-08-10", 1)])
    assert hs.month_name(first) == "March 2024"


def test_split_rolling_12mo_compares_full_years_of_complete_months():
    txns = [sale("2024-03-15", 1), sale("2024-08-01", 2), sale("2025-07-31", 3),
            sale("2025-08-01", 4), sale("2026-07-31", 5), sale("2026-08-10", 6)]
    current, prior, current_label, prior_label = hs.split_rolling_12mo(txns)
    assert [t["amount"] for t in current] == [4, 5]
    assert [t["amount"] for t in prior] == [2, 3]
    assert current_label == "12 months to July 2026"
    assert prior_label == "12 months to July 2025"


def test_split_rolling_12mo_has_no_prior_when_the_data_is_too_short():
    _, prior, _, prior_label = hs.split_rolling_12mo([sale("2025-06-01", 1), sale("2026-08-10", 2)])
    assert prior == [] and prior_label is None


def test_bucket_by_calendar_year_skips_undated_sales():
    buckets = hs.bucket_by_calendar_year([sale("2025-01-01", 1), sale("2026-01-01", 2), sale(None, 3)])
    assert {year: len(txns) for year, txns in buckets.items()} == {"2025": 1, "2026": 1}


def test_build_period_block_formats_changes_against_the_prior_period():
    current = [sale("2026-01-01", 200000), sale("2026-02-01", 300000, ptype="Other")]
    prior = [sale("2025-01-01", 250000)]
    block = hs.build_period_block(current, prior, "2025")
    assert block["count_display"] == "2"
    assert block["count_change"] == "up 100% (2025: 1)"
    assert block["median_display"] == "£250,000"
    assert block["median_change"] == "up 0% (2025: £250,000)"
    assert block["range_prior_display"] == "2025: £250,000–£250,000"
    assert block["domestic_count"] == 1 and block["domestic_mean_change"] == "down 20% (2025: £250,000)"
    assert block["other_note"] == '1 sale this period and 0 the period before was classed as "Other".'
    assert block["new_build_count"] == 0 and block["new_build_median_display"] is None


def test_build_period_block_needs_ten_new_builds_each_side_for_a_change():
    current = [sale("2026-01-01", 300000, new_build=True) for _ in range(10)]
    enough = [sale("2025-01-01", 250000, new_build=True) for _ in range(10)]
    assert hs.build_period_block(current, enough, "2025")["new_build_median_change"] == "up 20% (2025: £250,000)"
    assert hs.build_period_block(current, enough[:9], "2025")["new_build_count_change"] is None


def test_build_period_block_without_prior_data():
    block = hs.build_period_block([sale("2026-01-01", 1, ptype="Other"), sale("2026-01-02", 2, ptype="Other")], [], "x")
    assert block["count_change"] is None and block["range_prior_display"] is None
    assert block["other_note"] == '2 sales were classed as "Other".'
    assert hs.build_period_block([], [], "x")["median_display"] is None


def test_build_period_block_can_compare_with_a_history_year():
    history = {"count": 4, "median": 200000, "mean": 210000, "min": 1, "max": 9,
               "new_build": None, "other_count": 2}
    block = hs.build_period_block([sale("2023-01-01", 220000)], [], "2022", prior_history=history)
    assert block["count_change"] == "down 75% (2022: 4)"
    assert block["median_change"] == "up 10% (2022: £200,000)"
    assert block["other_note"] == '0 sales this period and 2 the period before were classed as "Other".'


def test_period_label():
    assert hs.period_label(2025, 1, 12) == "2025"
    assert hs.period_label(2026, 6, 6) == "June 2026"
    assert hs.period_label(2026, 1, 7) == "January to July 2026"


def test_build_by_year_compares_like_months_and_falls_back_to_history(files):
    files["history"].write_text(json.dumps({"first_year": 1995, "last_year": 2024, "years": [
        {"year": 2024, "count": 1, "median": 100000, "mean": 100000, "min": 100000, "max": 100000}]}))
    txns = [sale("2025-01-01", 200000), sale("2025-12-31", 300000),
            sale("2026-03-01", 250000), sale("2026-08-10", 1)]
    blocks = hs.build_by_year(txns)
    assert [(b["year"], b["period_label"]) for b in blocks] == [("2026", "January to July 2026"), ("2025", "2025")]
    assert blocks[0]["count_change"] == "up 0% (January to July 2025: 1)"  # December 2025 is left out
    assert blocks[1]["count_change"] == "up 100% (2024: 1)"


def test_build_by_year_skips_years_with_no_complete_month(files):
    blocks = hs.build_by_year([sale("2025-12-15", 1), sale("2026-01-10", 2)])
    assert blocks == []


def test_build_overall_since_history_adds_live_sales_after_the_history(files):
    assert hs.build_overall_since_history([sale("2026-01-01", 1)]) is None
    files["history"].write_text(json.dumps({"first_year": 1995, "last_year": 2024, "years": [
        {"year": 2024, "count": 2, "total": 500000, "min": 100000, "max": 400000}]}))
    overall = hs.build_overall_since_history([sale("2024-06-01", 999), sale("2025-03-01", 700000),
                                              sale("2026-05-02", 50000), sale(None, 1)])
    assert overall == {"first_year": 1995, "to_month": "May 2026", "count": 4, "count_display": "4",
                       "mean_display": "£312,500", "min_display": "£50,000", "max_display": "£700,000"}


def test_load_transactions_exits_without_the_raw_file(files):
    with pytest.raises(SystemExit):
        hs.load_transactions()


def test_main_writes_the_summary(files):
    files["raw"].write_text(json.dumps({"generated_at": "2026-10-01T00:00:00+00:00", "months_fetched": 48,
                                        "transactions": [sale("2025-01-01", 200000), sale("2026-08-10", 300000)]}))
    hs.main()
    summary = json.loads(files["summary"].read_text())
    assert summary["source_generated_at"] == "2026-10-01T00:00:00+00:00"
    assert summary["current"]["period_label"] == "12 months to July 2026"
    assert summary["full_dataset"] == {"count_display": "2", "median_display": "£250,000",
                                       "mean_display": "£250,000", "min_display": "£200,000",
                                       "max_display": "£300,000", "months": 48}
    assert summary["overall"] is None
    assert [b["year"] for b in summary["by_year"]] == ["2026", "2025"]


def test_write_summary_dry_run_writes_nothing(files):
    hs.write_summary({"a": 1}, dry_run=True)
    assert not files["summary"].exists()
