"""Offline tests for the air quality fetcher (air-quality.py): matching
DEFRA UK-AIR series to pollutants, banding readings and shaping
_data/air-quality.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "air_quality", pathlib.Path(__file__).resolve().parents[1] / "air-quality.py"
)
assert SPEC is not None and SPEC.loader is not None
aq = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(aq)

FOUR_AM = datetime.datetime(2026, 10, 12, 4, 0, tzinfo=datetime.timezone.utc)


def reading(station, key, value, distance=2.5, when=FOUR_AM, uom="ug.m-3"):
    return {
        "station": station,
        "distance_km": distance,
        "pollutant_key": key,
        "pollutant_label": aq.POLLUTANTS_OF_INTEREST[key],
        "value": value,
        "uom": uom,
        "timestamp": when,
        "band": aq.daqi_band(key, value),
    }


def test_pollutants_are_matched_by_eionet_code_then_by_label_text():
    assert aq.match_pollutant_key("http://dd.eionet.europa.eu/vocabulary/aq/pollutant/6001") == "pm2.5"
    assert aq.match_pollutant_key("", fallback_text="Gloucester-Nitrogen dioxide (air)") == "no2"
    assert aq.match_pollutant_key("Benzene") is None


def test_readings_are_banded_against_the_daqi_thresholds():
    assert aq.daqi_band("pm2.5", 0.9) == "Low"
    assert aq.daqi_band("pm10", 40) == "High"
    assert aq.daqi_band("no2", None) == "n/a"


def test_the_pollutant_suffix_is_stripped_from_a_station_label():
    label = "Cheltenham A40 Gloucester Road-Particulate matter less than 2.5 micro m (aerosol)"
    assert aq.site_name(label) == "Cheltenham A40 Gloucester Road"
    assert aq.site_name("Gloucester Tredworth") == "Gloucester Tredworth"


def test_readings_are_grouped_into_stations_sorted_by_name_then_pollutant():
    stations = aq.build_stations([
        reading("Gloucester Tredworth", "pm2.5", 3.019, distance=12.1),
        reading("Cheltenham A40 Gloucester Road", "pm2.5", 0.9),
        reading("Gloucester Tredworth", "pm10", 6.0, distance=12.1),
    ])
    assert [s["name"] for s in stations] == ["Cheltenham A40 Gloucester Road", "Gloucester Tredworth"]
    assert stations[1]["distance_km"] == 12.1
    assert [r["pollutant"] for r in stations[1]["readings"]] == ["PM10 (particulates)", "PM2.5 (fine particulates)"]


def test_a_reading_keeps_its_value_and_a_display_string_and_an_iso_time():
    [station] = aq.build_stations([reading("CHELTENHAM ROAD", "pm10", 1234.5)])
    assert station["name"] == "Cheltenham Road"
    assert station["readings"] == [{
        "pollutant_key": "pm10",
        "pollutant": "PM10 (particulates)",
        "value": 1234.5,
        "uom": "ug.m-3",
        "reading_display": "1,234.5 ug.m-3",
        "band": "Very High",
        "measured": "2026-10-12T04:00",
    }]


def test_a_reading_with_no_value_or_time_shows_not_available():
    [station] = aq.build_stations([reading("Cheltenham", "o3", None, when=None)])
    assert station["readings"][0]["reading_display"] == "n/a"
    assert station["readings"][0]["measured"] is None


def test_the_highest_band_ignores_readings_without_a_band():
    readings = [reading("A", "pm2.5", 0.9), reading("A", "pm10", 20), reading("A", "o3", None)]
    assert aq.highest_band(readings) == "Moderate"
    assert aq.highest_band([]) is None


def test_the_payload_carries_the_source_envelope_and_headline_figures():
    payload = aq.build_payload([
        reading("Gloucester Tredworth", "pm10", 6.0, distance=12.1),
        reading("Cheltenham A40 Gloucester Road", "pm2.5", 0.9),
    ], generated_at="2026-10-12T06:27:00+00:00")
    assert payload["generated_at"] == "2026-10-12T06:27:00+00:00"
    assert payload["source"] == "DEFRA UK-AIR"
    assert payload["source_url"] == "https://uk-air.defra.gov.uk/"
    assert payload["licence"] == "Open Government Licence v3.0"
    assert payload["reading_count"] == 2
    assert payload["highest_band"] == "Low"
    assert payload["nearest_km"] == 2.5
    assert len(payload["stations"]) == 2


def test_an_empty_run_still_writes_a_payload():
    payload = aq.build_payload([], generated_at="2026-10-12T06:27:00+00:00")
    assert payload["stations"] == []
    assert payload["reading_count"] == 0
    assert payload["nearest_km"] is None
