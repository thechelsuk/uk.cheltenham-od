"""Offline tests for the Pi's fuel prices fetcher (pi/fuel.py).

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


fuel = _load("fuel", "pi/fuel.py")


def test_fuel_codes_get_readable_labels():
    assert fuel.fuel_label("E10") == "Unleaded"
    assert fuel.fuel_label("B7_STANDARD") == "Diesel"
    assert fuel.fuel_label("NEW_CODE") == "NEW_CODE"


def test_brand_acronyms_stay_upper_case():
    assert fuel.clean_name("ASDA EXPRESS BP CHELTENHAM") == "ASDA Express BP Cheltenham"


def test_a_forecourt_in_range_becomes_a_station():
    station = fuel.station_from_pfs_record({
        "trading_name": "Test Garage",
        "location": {"latitude": 51.90, "longitude": -2.08, "address_line_1": "1 High Street", "postcode": "GL50 1AA"},
    })
    assert station["trading_name"] == "Test Garage"
    assert station["address"] == "1 High Street, GL50 1AA"
    assert station["distance_miles"] < 1


def test_the_postcode_isnt_repeated_when_the_address_already_ends_with_it():
    station = fuel.station_from_pfs_record({
        "location": {"latitude": 51.90, "longitude": -2.08, "address_line_1": "1 High Street, GL50 1AA", "postcode": "GL50 1AA"},
    })
    assert station["address"] == "1 High Street, GL50 1AA"


def test_a_forecourt_out_of_range_or_without_a_location_is_skipped():
    assert fuel.station_from_pfs_record({"location": {"latitude": 53.48, "longitude": -2.24}}) is None
    assert fuel.station_from_pfs_record({"location": {}}) is None
