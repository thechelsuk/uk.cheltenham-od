"""Offline tests for the housing supply fetcher (housing-supply.py): finding
the VOA council tax stock zip on the yearly GOV.UK page.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import re

SPEC = importlib.util.spec_from_file_location(
    "housing_supply", pathlib.Path(__file__).resolve().parents[1] / "housing-supply.py"
)
assert SPEC is not None and SPEC.loader is not None
housing_supply = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(housing_supply)

MEDIA = "https://assets.publishing.service.gov.uk/media/abc123/"


def matches(name):
    return re.search(housing_supply.CTSOP_ZIP_PATTERN, MEDIA + name) is not None


def test_zip_pattern_matches_the_2025_and_2026_names():
    assert matches("CTSOP1.1.zip")
    assert matches("CTSOP_1_1.zip")


def test_zip_pattern_skips_the_other_ctsop_tables():
    assert not matches("CTSOP_3_1__1_.zip")
    assert not matches("CTSOP_4_1.zip")
    assert not matches("CTSOP1-1-1993-2024.zip")


def test_each_new_snapshot_year_is_kept_in_the_history(tmp_path):
    # VOA publishes one year per release, so a year is lost unless the
    # history keeps it before the next release replaces it.
    history = tmp_path / "history.json"
    history.write_text(json.dumps({"note": "n", "years": [{"year": 2024, "all_properties": 57250}]}))
    series = housing_supply.build_council_tax_stock_series(
        {"year": 2025, "all_properties": 57550}, history)
    assert series == [{"year": 2024, "all_properties": 57250}, {"year": 2025, "all_properties": 57550}]
    series = housing_supply.build_council_tax_stock_series(
        {"year": 2026, "all_properties": 57760}, history)
    assert [y["year"] for y in series] == [2024, 2025, 2026]
    assert json.loads(history.read_text())["years"] == series
