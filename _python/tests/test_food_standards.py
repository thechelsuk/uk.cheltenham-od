"""Offline tests for the Food Standards Agency converter (food-standards.py),
which turns the downloaded FHRS XML into _data JSON.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location(
    "food_standards", pathlib.Path(__file__).resolve().parents[1] / "food-standards.py"
)
assert SPEC is not None and SPEC.loader is not None
fsa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fsa)

XML = """<?xml version="1.0" encoding="utf-8"?>
<FHRSEstablishment><EstablishmentCollection>
<EstablishmentDetail>
  <FHRSID>101</FHRSID><BusinessName> The Daffodil </BusinessName><BusinessType>Restaurant/Cafe/Canteen</BusinessType>
  <AddressLine1>18-20 Suffolk Parade</AddressLine1><AddressLine2></AddressLine2><AddressLine3>Cheltenham</AddressLine3>
  <PostCode>GL50 2AE</PostCode><RatingValue>5</RatingValue><RatingDate>2025-03-04</RatingDate>
  <Geocode><Longitude>-2.0812</Longitude><Latitude>51.8932</Latitude></Geocode>
</EstablishmentDetail>
<EstablishmentDetail>
  <FHRSID>102</FHRSID><BusinessName>Cakes at Home</BusinessName><BusinessType>Manufacturers/packers</BusinessType>
  <RatingValue>AwaitingInspection</RatingValue>
  <Geocode><Longitude>bad</Longitude></Geocode>
</EstablishmentDetail>
</EstablishmentCollection></FHRSEstablishment>"""


def establishments():
    return ET.fromstring(XML).findall(".//EstablishmentDetail")


def test_value_strips_text_and_treats_missing_or_empty_as_blank():
    daffodil, cakes = establishments()
    assert fsa.value(daffodil, "BusinessName") == "The Daffodil"
    assert fsa.value(daffodil, "AddressLine2") == ""
    assert fsa.value(cakes, "PostCode") == ""


def test_coordinate_is_a_float_or_none():
    daffodil, cakes = establishments()
    assert fsa.coordinate(daffodil, "Latitude") == 51.8932
    assert fsa.coordinate(cakes, "Latitude") is None
    assert fsa.coordinate(cakes, "Longitude") is None


def test_convert_writes_one_venue_per_establishment(tmp_path, monkeypatch):
    source, destination = tmp_path / "food-standards.xml", tmp_path / "food-standards.json"
    source.write_text(XML, encoding="utf-8")
    monkeypatch.setattr(fsa, "SOURCE", source)
    monkeypatch.setattr(fsa, "DESTINATION", destination)

    fsa.convert()

    venues = json.loads(destination.read_text(encoding="utf-8"))
    assert venues[0] == {
        "id": "101",
        "name": "The Daffodil",
        "type": "Restaurant/Cafe/Canteen",
        "address": "18-20 Suffolk Parade, Cheltenham",
        "postcode": "GL50 2AE",
        "rating": "5",
        "rating_date": "2025-03-04",
        "latitude": 51.8932,
        "longitude": -2.0812,
    }
    assert venues[1]["address"] == "" and venues[1]["latitude"] is None
    assert venues[1]["rating"] == "AwaitingInspection"
