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


# --- Hand-checked additions (_data/ev-charging-additions.json) ----------------

def addition(entry_id="bath-terrace", lat=51.89, lng=-2.0797, operator="Duracell E-Charge", **extra):
    entry = {
        "id": entry_id,
        "name": "Bath Terrace Car Park",
        "operator": operator,
        "address": "Bath Terrace",
        "town": "Cheltenham",
        "postcode": "GL50 2BA",
        "latitude": lat,
        "longitude": lng,
        "access": "Public - Pay At Location",
        "status": "Operational",
        "num_points": 10,
        "connections": [{"type": "CCS (Type 2)", "power_kw": 300, "quantity": 10, "level": "Level 3:  High (Over 40kW)"}],
        "sources": [{"name": "Cheltenham Borough Council", "url": "https://cheltenham.gov.uk/ev"}],
        "last_checked": "2026-11-12",
    }
    entry.update(extra)
    return entry


def test_an_addition_becomes_a_station_in_the_same_shape_as_an_ocm_one():
    station = ev.addition_to_station(addition())
    ocm_keys = set(ev.transform(poi(1)).keys()) - {"ocm_url"}
    assert ocm_keys <= set(station.keys())
    assert station["id"] == "bath-terrace"
    assert station["max_power_kw"] == 300
    assert station["distance_miles"] == round(ev.helper.miles_from_centre(51.89, -2.0797), 2)
    assert station["google_maps_url"].endswith("query=51.89,-2.0797")
    assert station["last_verified"] == "2026-11-12"
    assert station["hand_checked"] is True
    assert station["source_url"] == "https://cheltenham.gov.uk/ev"
    assert station["sources"] == [{"name": "Cheltenham Borough Council", "url": "https://cheltenham.gov.uk/ev"}]
    assert station["ocm_url"] is None


def test_an_addition_without_a_source_or_a_checked_date_is_refused():
    import pytest
    with pytest.raises(ValueError):
        ev.addition_to_station(addition(sources=[]))
    with pytest.raises(ValueError):
        ev.addition_to_station(addition(last_checked="12 November 2026"))
    with pytest.raises(ValueError):
        ev.addition_to_station(addition(latitude=None))


def test_additions_are_merged_in_and_sorted_by_distance():
    far = ev.transform(poi(1, lat=51.93, lng=-2.07))
    merged = ev.merge_additions([far], [addition()])
    assert [s["id"] for s in merged] == ["bath-terrace", 1]


def test_an_addition_is_dropped_once_ocm_lists_the_same_operator_nearby():
    ocm = ev.transform(poi(9, lat=51.8901, lng=-2.0797, operator="Duracell E-Charge"))
    assert [s["id"] for s in ev.merge_additions([ocm], [addition()])] == [9]


def test_a_different_operator_nearby_does_not_hide_an_addition():
    ocm = ev.transform(poi(9, lat=51.8901, lng=-2.0797, operator="Pod Point"))
    assert {s["id"] for s in ev.merge_additions([ocm], [addition()])} == {9, "bath-terrace"}


def test_an_addition_outside_the_search_radius_is_left_out():
    assert ev.merge_additions([], [addition(lat=52.2, lng=-2.0797)]) == []


def test_load_additions_reads_the_stations_list(tmp_path):
    import json
    path = tmp_path / "additions.json"
    path.write_text(json.dumps({"stations": [addition()]}))
    assert ev.load_additions(path)[0]["id"] == "bath-terrace"
    assert ev.load_additions(tmp_path / "missing.json") == []


def test_the_real_additions_file_is_valid():
    for entry in ev.load_additions(ev.ADDITIONS_FILE):
        station = ev.addition_to_station(entry)
        assert station["distance_miles"] * 1.609344 <= ev.RADIUS_KM
