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


def lt122_frame(lead_columns, values):
    import pandas as pd
    header = lead_columns + ["Current ONS code", "Authority data", "2001-02", "2024-25 [r] [note 18]", "2025-26 [p] [note 19]"]
    pad = [None] * (len(lead_columns) + 1)
    rows = [["Title"] + [None] * (len(header) - 1) for _ in range(4)]
    rows.append(header)
    rows.append(pad[:-1] + ["E92000001", "England"] + [100.0, 200.0, 300.0])
    rows.append(pad[:-1] + ["E07000078", "Cheltenham"] + values)
    return pd.DataFrame(rows)


def test_lt122_reads_the_2026_layout_with_a_geography_column():
    # The 2025-26 release added a "Geography type" column first and gave
    # decimal values, so columns are found by their headers and rounded.
    df = lt122_frame(["Geography type", "DCLG code", "Former ONS code"], [322.7, 410.2, None])
    assert housing_supply.parse_net_additional_dwellings(df) == [
        {"year": "2001-02", "net_additional_dwellings": 323},
        {"year": "2024-25", "net_additional_dwellings": 410},
    ]


def test_lt122_still_reads_the_older_layout():
    df = lt122_frame(["DCLG code", "Former ONS code"], [323, 410, 455])
    years = housing_supply.parse_net_additional_dwellings(df)
    assert [y["year"] for y in years] == ["2001-02", "2024-25", "2025-26"]
    assert years[-1]["net_additional_dwellings"] == 455
