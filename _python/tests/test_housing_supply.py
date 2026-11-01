"""Offline tests for the housing supply fetcher (housing-supply.py): finding
the VOA council tax stock zip on the yearly GOV.UK page.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
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
