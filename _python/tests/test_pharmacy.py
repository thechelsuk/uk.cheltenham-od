"""Offline tests for the GP and pharmacy fetcher (pharmacy.py): tidying NHS
ODS records, removing duplicates and shaping _data/gp-pharmacy.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "pharmacy", pathlib.Path(__file__).resolve().parents[1] / "pharmacy.py"
)
assert SPEC is not None and SPEC.loader is not None
pharmacy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pharmacy)

GOOD = {"overall": "Good", "url": "https://www.cqc.org.uk/location/1-1", "published": "2020-04-03"}


def entry(name, address, phone="01242 513975", cqc=None):
    return {"name": name, "address": address, "phone": phone, "cqc": cqc}


def test_names_are_title_cased_but_postcodes_stay_upper_case():
    assert pharmacy.to_title_case("ST. CATHERINE'S SURGERY, GL52 3EY") == "St. Catherine's Surgery, GL52 3EY"


def test_address_and_phone_are_read_from_an_ods_record():
    detail = {"Organisation": {
        "GeoLoc": {"Location": {"AddrLn1": "236 PRESTBURY ROAD", "Town": "CHELTENHAM", "PostCode": "GL52 3EY"}},
        "Contacts": {"Contact": {"type": "tel", "value": "01242 513975"}},
    }}
    assert pharmacy.extract_detail_fields(detail) == ("236 PRESTBURY ROAD, CHELTENHAM, GL52 3EY", "01242 513975")


def test_duplicate_records_keep_the_one_with_a_phone_number():
    entries = pharmacy.dedupe_entries([
        entry("Boots", "1 High Street, Cheltenham, GL50 1AA", phone=""),
        entry("Boots", "1 High Street, Cheltenham, GL50 1AA"),
    ])
    assert len(entries) == 1
    assert entries[0]["phone"] == "01242 513975"


def test_entries_are_sorted_and_given_links():
    [first, second] = pharmacy.build_entries([
        entry("Tesco Instore Pharmacy", "Colletts Drive, Cheltenham, GL51 8JQ"),
        entry("Berkeley Place Surgery", "Wilson Health Centre, 236 Prestbury Road, Cheltenham, GL52 3EY", cqc=GOOD),
    ])
    assert first["name"] == "Berkeley Place Surgery"
    assert first["heading"] == "Berkeley Place Surgery"
    assert first["postcode"] == "GL52 3EY"
    assert first["maps_url"] == ("https://www.google.com/maps/search/?api=1&query="
                                 "Wilson+Health+Centre%2C+236+Prestbury+Road%2C+Cheltenham%2C+GL52+3EY")
    assert first["tel"] == "01242513975"
    assert first["cqc"] == GOOD
    assert second["cqc"] is None


def test_branches_sharing_a_name_are_told_apart_by_street():
    headings = [e["heading"] for e in pharmacy.build_entries([
        entry("Boots", "1 High Street, Cheltenham, GL50 1AA"),
        entry("Boots", "Bath Road, Cheltenham, GL53 7HG"),
    ])]
    assert headings == ["Boots (1 High Street)", "Boots (Bath Road)"]


def test_a_trailing_comma_is_dropped_from_the_heading():
    [e] = pharmacy.build_entries([entry("Lloyds Pharmacy,", "Bath Road, Cheltenham, GL53 7HG", phone="")])
    assert e["heading"] == "Lloyds Pharmacy"
    assert e["tel"] == ""


def test_the_payload_carries_the_source_envelope_and_counts():
    payload = pharmacy.build_payload(
        gps=[entry("A Surgery", "Road, GL50 1AA", cqc=GOOD),
             entry("B Surgery", "Road, GL50 1AB", cqc={**GOOD, "overall": "Outstanding"}),
             entry("C Surgery", "Road, GL50 1AC", cqc={**GOOD, "overall": "Requires improvement"}),
             entry("D Surgery", "Road, GL50 1AD")],
        pharmacies=[entry("Boots", "1 High Street, Cheltenham, GL50 1AA")],
        generated_at="2026-10-12T11:22:00+00:00",
    )
    assert payload["source"] == "NHS Organisation Data Service"
    assert payload["source_url"] == "https://digital.nhs.uk/services/organisation-data-service"
    assert payload["licence"] == "Open Government Licence v3.0"
    assert payload["postcode_districts"] == ["GL50", "GL51", "GL52", "GL53"]
    assert payload["gp_count"] == 4
    assert payload["pharmacy_count"] == 1
    assert payload["gps_good_or_better"] == 2
    assert [g["name"] for g in payload["gp_practices"]] == ["A Surgery", "B Surgery", "C Surgery", "D Surgery"]
