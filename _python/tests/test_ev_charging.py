"""Offline tests for the EV charging fetcher (ev-charging.py): turning Open
Charge Map POIs into station records and the page's headline summary.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "ev_charging", pathlib.Path(__file__).resolve().parents[1] / "ev-charging.py"
)
assert SPEC is not None and SPEC.loader is not None
ev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ev)


def poi(poi_id, lat=51.9, lng=-2.07, operator="Pod Point", connections=None):
    return {
        "ID": poi_id,
        "AddressInfo": {"Title": f"Site {poi_id}", "AddressLine1": "1 High St", "Town": "Cheltenham",
                        "Postcode": "GL50 1AA", "Latitude": lat, "Longitude": lng},
        "OperatorInfo": {"Title": operator} if operator else None,
        "UsageType": {"Title": "Public"},
        "StatusType": {"Title": "Operational"},
        "NumberOfPoints": 2,
        "Connections": connections or [],
        "DateLastVerified": "2026-09-01T10:00:00Z",
    }


def conn(kind, power, quantity=1):
    return {"ConnectionType": {"Title": kind}, "PowerKW": power, "Quantity": quantity,
            "Level": {"Title": "Level 2"}}


def test_a_poi_without_coordinates_is_dropped():
    raw = poi(1)
    raw["AddressInfo"]["Latitude"] = None
    assert ev.transform(raw) is None


def test_a_poi_becomes_a_station_with_its_fastest_connector_and_links():
    station = ev.transform(poi(7, connections=[conn("Type 2", 7), conn("CCS", 50)]))
    assert station["name"] == "Site 7"
    assert station["operator"] == "Pod Point"
    assert station["max_power_kw"] == 50
    assert [c["type"] for c in station["connections"]] == ["Type 2", "CCS"]
    assert station["ocm_url"] == "https://openchargemap.org/site/poi/details/7"
    assert station["google_maps_url"].endswith("query=51.9,-2.07")


def test_a_station_with_no_power_ratings_has_no_fastest_connector():
    assert ev.transform(poi(3, connections=[conn("Type 2", None)]))["max_power_kw"] is None


def test_the_summary_counts_locations_connectors_and_operators():
    stations = [
        ev.transform(poi(1, connections=[conn("Type 2", 7, 2), conn("CCS", 150)])),
        ev.transform(poi(2, operator="Tesla", connections=[conn("Type 2", 22)])),
        ev.transform(poi(3, operator=None, connections=[conn("Type 2", 7)])),
    ]
    summary = ev.build_summary(stations)
    assert summary["total_locations"] == 3
    assert summary["total_connectors"] == 5
    assert summary["operators"] == 2
    assert summary["max_power_kw"] == 150


def test_connector_types_are_ordered_by_how_many_locations_have_them():
    stations = [
        ev.transform(poi(1, connections=[conn("CCS", 50), conn("Type 2", 7)])),
        ev.transform(poi(2, connections=[conn("Type 2", 22), conn("Type 2", 7)])),
    ]
    types = ev.build_summary(stations)["connector_types"]
    assert types[0] == {"type": "Type 2", "stations": 2, "connectors": 3, "max_power_kw": 22}
    assert types[1] == {"type": "CCS", "stations": 1, "connectors": 1, "max_power_kw": 50}
