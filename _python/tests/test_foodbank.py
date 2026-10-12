"""Offline tests for the food banks fetcher (foodbank.py).

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


foodbank = _load("foodbank", "foodbank.py")


def test_trussell_food_banks_get_foodbank_added_to_their_name():
    assert foodbank.display_name("Gloucester", "Trussell") == "Gloucester Foodbank"
    assert foodbank.display_name("Cheltenham Foodbank", "Trussell") == "Cheltenham Foodbank"
    assert foodbank.display_name("Open Door", "Independent") == "Open Door"


def test_addresses_and_locations_are_tidied():
    assert foodbank.one_line("1 High St\n\nCheltenham ") == "1 High St, Cheltenham"
    assert foodbank.lat_lon("51.9,-2.08") == (51.9, -2.08)
    assert foodbank.lat_lon("") == (None, None)


def test_an_unknown_needs_list_doesnt_count_as_a_list():
    fb = foodbank.normalise_foodbank({"slug": "x", "name": "X", "need": {"needs": "Unknown"}}, 1.0)
    assert fb["need"]["has_list"] is False


def test_summary_counts_donation_points_and_finds_the_latest_list():
    def fb(slug, found, points):
        return {"slug": slug, "display_name": slug.title(), "donation_points": [{}] * points,
                "need": {"found_iso": found, "has_list": True}}
    summary = foodbank.summarise([fb("a", "2026-10-01", 2), fb("b", "2026-10-06", 3)])
    assert summary["foodbank_count"] == 2
    assert summary["donation_point_count"] == 5
    assert summary["latest_change"]["slug"] == "b"
