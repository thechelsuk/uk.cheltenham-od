"""Offline tests for the taxi ranks fetcher (taxi-ranks.py): the council's
Google My Maps export, OpenStreetMap ranks, and the editor's own checks.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "taxi_ranks", pathlib.Path(__file__).resolve().parents[1] / "taxi-ranks.py"
)
taxi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(taxi)

KML = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Taxi ranks in Cheltenham</name>
<Placemark><name>Promenade taxi rank
</name><Point><coordinates>-2.0773162,51.8990138,0</coordinates></Point></Placemark>
<Placemark><name>Montpellier Walk taxi rank</name><Point><coordinates>-2.0824942,51.8949863,0</coordinates></Point></Placemark>
</Document></kml>"""


def test_council_ranks_are_read_from_the_map_export():
    assert taxi.parse_kml(KML) == [
        {"name": "Promenade", "lat": 51.899014, "lon": -2.077316},
        {"name": "Montpellier Walk", "lat": 51.894986, "lon": -2.082494},
    ]


def osm(osm_id, lat, lon, **tags):
    return {"type": "node", "id": osm_id, "lat": lat, "lon": lon, "tags": {"amenity": "taxi", **tags}}


def test_osm_ranks_close_to_a_council_rank_are_merged_and_lend_their_spaces():
    council = taxi.parse_kml(KML)
    ranks = taxi.merge(council, [osm(1, 51.89507, -2.08248, capacity="3"), osm(2, 51.89722, -2.09923)],
                       streets={2: "Queen's Road"}, curated={})
    montpellier = next(r for r in ranks if r["name"] == "Montpellier Walk")
    assert montpellier["spaces"] == 3
    assert montpellier["sources"] == ["Cheltenham Borough Council", "OpenStreetMap"]
    station = next(r for r in ranks if r["street"] == "Queen's Road")
    assert station["name"] == "Queen's Road"
    assert station["sources"] == ["OpenStreetMap"]
    assert len(ranks) == 3


def test_curated_names_exclusions_and_additions_apply():
    curated = {
        "exclude_osm": [{"id": 9, "reason": "Private hire office, not a public rank"}],
        "names": [{"osm_id": 2, "name": "Cheltenham Spa station"}],
        "add": [{"name": "Queen's Hotel", "street": "Promenade", "lat": 51.8961, "lon": -2.0791,
                 "verified": "2026-10-09"}],
    }
    ranks = taxi.merge([], [osm(2, 51.89722, -2.09923), osm(9, 51.89933, -2.07983, name="Starline")],
                       streets={2: "Queen's Road", 9: "Royal Well Place"}, curated=curated)
    # nearest the town centre first
    assert [r["name"] for r in ranks] == ["Queen's Hotel", "Cheltenham Spa station"]
    assert ranks[0]["sources"] == ["Checked by Cheltenham Open Data"]


def test_ranks_get_a_distance_and_are_sorted_by_it():
    ranks = taxi.merge(taxi.parse_kml(KML), [], streets={}, curated={})
    assert [r["name"] for r in ranks] == ["Promenade", "Montpellier Walk"]
    assert ranks[0]["distance_miles"] < ranks[1]["distance_miles"]


def test_an_osm_rank_at_a_checked_rank_is_merged_not_duplicated():
    curated = {"add": [{"name": "Queen's Hotel", "street": "Promenade", "lat": 51.896427, "lon": -2.079838}]}
    ranks = taxi.merge([], [osm(5, 51.89645, -2.07980, capacity="4")], streets={5: "Promenade"}, curated=curated)
    assert len(ranks) == 1
    assert ranks[0]["name"] == "Queen's Hotel"
    assert ranks[0]["spaces"] == 4
    assert ranks[0]["sources"] == ["Checked by Cheltenham Open Data", "OpenStreetMap"]
