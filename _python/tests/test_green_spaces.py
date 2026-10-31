"""Offline tests for the green spaces fetcher (green-spaces.py), which reads
the Ordnance Survey Open Greenspace GML for the SO grid square.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests/test_green_spaces.py
"""
import importlib.util
import io
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "green_spaces", pathlib.Path(__file__).resolve().parents[1] / "green-spaces.py"
)
assert SPEC is not None and SPEC.loader is not None
green_spaces = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(green_spaces)

NS = (
    'xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:os="http://namespaces.os.uk/product/1.0" '
    'xmlns:ogsp="http://namespaces.ordnancesurvey.co.uk/Open/Greenspace/1.0"'
)


def square(e, n, size):
    """A closed square ring as a GML posList, south-west corner at (e, n)."""
    pts = [(e, n), (e + size, n), (e + size, n + size), (e, n + size), (e, n)]
    return " ".join(f"{x} {y}" for x, y in pts)


def site(gid, function, ring, name=None, hole=None):
    name_xml = f"<ogsp:distinctiveName1>{name}</ogsp:distinctiveName1>" if name else ""
    hole_xml = (
        f"<gml:interior><gml:LinearRing><gml:posList>{hole}</gml:posList></gml:LinearRing></gml:interior>"
        if hole else ""
    )
    return (
        f'<os:featureMember><ogsp:GreenspaceSite gml:id="{gid}">'
        f"<ogsp:function>{function}</ogsp:function>{name_xml}"
        f'<ogsp:geometry><gml:MultiSurface gml:id="{gid}-0"><gml:surfaceMember><gml:Surface gml:id="{gid}-1">'
        f"<gml:patches><gml:PolygonPatch><gml:exterior><gml:LinearRing><gml:posList>{ring}</gml:posList>"
        f"</gml:LinearRing></gml:exterior>{hole_xml}</gml:PolygonPatch></gml:patches>"
        f"</gml:Surface></gml:surfaceMember></gml:MultiSurface></ogsp:geometry>"
        f"</ogsp:GreenspaceSite></os:featureMember>"
    )


def access(gid, site_id, kind):
    return (
        f'<os:featureMember><ogsp:AccessPoint gml:id="{gid}"><ogsp:accessType>{kind}</ogsp:accessType>'
        f"<ogsp:refToGreenspaceSite>{site_id}</ogsp:refToGreenspaceSite>"
        f'<ogsp:geometry><gml:Point gml:id="{gid}-0"><gml:pos>395000 222000</gml:pos></gml:Point></ogsp:geometry>'
        f"</ogsp:AccessPoint></os:featureMember>"
    )


GML = (
    f'<?xml version="1.0" encoding="UTF-8"?><os:FeatureCollection {NS}>'
    + access("a1", "park", "Pedestrian")
    + access("a2", "park", "Motor Vehicle And Pedestrian")
    + access("a3", "field", "Pedestrian")
    # Pittville-ish park, 200 m square (4 ha) with a 100 m square hole (1 ha).
    + site("park", "Public Park Or Garden", square(395000, 223000, 200), name="Pittville Park",
           hole=square(395050, 223050, 100))
    # Unnamed 100 m square (1 ha) playing field in the same ward.
    + site("field", "Playing Field", square(395300, 223000, 100))
    # A cemetery far away in Hereford, outside every ward.
    + site("far", "Cemetery", square(350000, 240000, 100))
    + "</os:FeatureCollection>"
).encode()

# One ward covering the middle of Cheltenham (about 1 km x 1.1 km), as
# _data/wards/index.json holds it: [lat, lon] points.
WARDS = [{
    "name": "Pittville", "slug": "pittville", "area_km2": 1.0,
    "boundary": [[51.905, -2.08], [51.905, -2.06], [51.915, -2.06], [51.915, -2.08], [51.905, -2.08]],
}]


def test_parse_reads_sites_and_counts_access_points():
    sites, entrances = green_spaces.parse(io.BytesIO(GML))
    assert [s["id"] for s in sites] == ["park", "field", "far"]
    assert sites[0]["name"] == "Pittville Park"
    assert sites[1]["name"] == ""
    assert len(sites[0]["polygons"][0]) == 2  # exterior and one hole
    assert entrances == {"park": {"total": 2, "vehicle": 1}, "field": {"total": 1, "vehicle": 0}}


def test_ring_area_in_hectares():
    ring = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
    assert green_spaces.ring_area(ring) == 10_000


def test_build_keeps_sites_inside_the_wards_with_area_net_of_holes():
    sites, entrances = green_spaces.parse(io.BytesIO(GML))
    payload = green_spaces.build(sites, entrances, WARDS, "2026-04")

    names = [s["name"] for s in payload["sites"]]
    assert names == ["Pittville Park", "Playing field, Pittville"]  # largest first, Hereford dropped

    park = payload["sites"][0]
    assert park["hectares"] == 3.0
    assert park["type"] == "Public park or garden"
    assert park["group"] == "parks"
    assert park["ward_slug"] == "pittville"
    assert park["access_points"] == 2 and park["vehicle_access"] == 1
    assert park["named"] is True
    # Polygons are [lat, lon] rings ready for Leaflet, holes kept.
    assert len(park["polygons"][0]) == 2
    lat, lon = park["polygons"][0][0][0]
    assert 51.9 < lat < 51.92 and -2.08 < lon < -2.06

    assert payload["os_version"] == "2026-04"
    assert payload["totals"] == {"sites": 2, "hectares": 4.0, "access_points": 3, "pct_of_borough": 4.0}

    ward = payload["wards"][0]
    assert ward == {"name": "Pittville", "slug": "pittville", "sites": 2, "hectares": 4.0,
                    "pct_of_ward": 4.0, "largest": "Pittville Park"}

    groups = {g["id"]: g for g in payload["groups"]}
    assert groups["parks"]["sites"] == 1 and groups["parks"]["hectares"] == 3.0
    assert groups["burial"]["sites"] == 0
