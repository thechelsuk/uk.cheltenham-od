"""Offline tests for the Post Office branches fetcher (post-office.py).
helper.overpass is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import helper

SPEC = importlib.util.spec_from_file_location(
    "post_office", pathlib.Path(__file__).resolve().parents[1] / "post-office.py"
)
assert SPEC is not None and SPEC.loader is not None
post_office = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(post_office)


def test_query_searches_nodes_and_ways_around_the_centre():
    query = post_office.build_query()
    around = f"(around:{post_office.RADIUS_M},{post_office.LAT},{post_office.LON})"
    assert f'node["amenity"="post_office"]{around}' in query
    assert f'way["amenity"="post_office"]{around}' in query


def test_record_builds_an_address_and_uses_a_ways_centre():
    node = {"type": "node", "id": 1, "lat": 51.9, "lon": -2.07,
            "tags": {"name": "Cheltenham Post Office", "addr:housenumber": "225",
                     "addr:street": "High Street", "addr:postcode": "GL50 3HH"}}
    way = {"type": "way", "id": 2, "center": {"lat": 51.88, "lon": -2.1}}
    assert post_office.record(node) == {"name": "Cheltenham Post Office",
                                        "address": "225, High Street, GL50 3HH",
                                        "lat": 51.9, "lon": -2.07, "osm_type": "node", "osm_id": 1}
    assert post_office.record(way) == {"name": "Post Office", "address": "", "lat": 51.88, "lon": -2.1,
                                       "osm_type": "way", "osm_id": 2}


def test_main_writes_one_record_per_element(monkeypatch):
    monkeypatch.setattr(helper, "overpass", lambda query, timeout: [{"type": "node", "id": 1, "lat": 1, "lon": 2}])
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    post_office.main()
    assert written["path"] == post_office.OUT
    assert [r["osm_id"] for r in written["payload"]] == [1]
