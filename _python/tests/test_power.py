"""Offline tests for the power cuts fetcher's Cheltenham postcode filter.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "power", pathlib.Path(__file__).resolve().parents[1] / "pi" / "power.py"
)
power = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(power)


@pytest.mark.parametrize("postcode", ["GL50 1AA", "GL51 0JU", "gl52 3nq", "GL533AB", "GL54 4EU"])
def test_cheltenham_postcodes_match(postcode):
    assert power.is_cheltenham_postcode(postcode)


@pytest.mark.parametrize("postcode", ["GL5 1HH", "GL5 2NJ", "GL51HH", "GL5 5BU", "GL55 1AA", "SY8 2JR", "", "GL51"])
def test_other_postcodes_do_not_match(postcode):
    assert not power.is_cheltenham_postcode(postcode)


def test_row_with_only_stroud_postcodes_is_not_local():
    row = {"postcode": "SY8 2JR, SY8 2JW, GL5 1HH, SY8 2II"}
    assert not power.row_is_local(row)
