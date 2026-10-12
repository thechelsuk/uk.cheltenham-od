"""Offline tests for the GP and pharmacy fetcher (pharmacy.py): tidying NHS
ODS records, removing duplicates and shaping _data/gp-pharmacy.json, with
the ODS API replaced by a fake for the fetching and the main run.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import sys

import requests

import helper

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


class FakeResponse:
    def __init__(self, body=None, status=200):
        self._body, self.status_code, self.text = body, status, json.dumps(body)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


def detail(address_line, phone=None):
    org = {"GeoLoc": {"Location": {"AddrLn1": address_line, "Town": "CHELTENHAM", "PostCode": "GL50 1AA"}}}
    if phone:
        org["Contacts"] = {"Contact": [{"type": "email", "value": "x@example.org"}, {"type": "tel", "value": phone}]}
    return {"Organisation": org}


class FakeOds:
    """requests.get for the ODS ORD API: roles, searches by postcode district
    and role, and organisation details by id."""
    def __init__(self, roles, orgs, details):
        self.roles, self.orgs, self.details, self.searches = roles, orgs, details, []

    def __call__(self, url, params=None, timeout=None):
        path = url[len(pharmacy.BASE_URL):]
        if path == "/roles":
            return FakeResponse({"Roles": self.roles})
        if path == "/organisations":
            self.searches.append(params)
            role = params.get("PrimaryRoleId") or params.get("NonPrimaryRoleId")
            return FakeResponse({"Organisations": self.orgs.get((role, params["PostCode"]), [])})
        org_id = path.rsplit("/", 1)[1]
        return FakeResponse(self.details[org_id]) if org_id in self.details else FakeResponse(status=404)


def test_pharmacy_roles_are_found_by_name(monkeypatch):
    monkeypatch.setattr(pharmacy.requests, "get", FakeOds(
        [{"id": "RO182", "displayName": "PHARMACY"}, {"id": "RO177", "displayName": "Prescribing Cost Centre"},
         {"id": "RO280", "displayName": "Pharmacy Headquarters"}], {}, {}))
    assert pharmacy.find_pharmacy_role_ids() == ["RO182", "RO280"]


def test_search_organisations_pages_by_offset(monkeypatch):
    pages = [[{"OrgId": str(i)} for i in range(200)], [{"OrgId": "last"}]]
    asked = []
    monkeypatch.setattr(pharmacy.requests, "get",
                        lambda url, params, timeout: asked.append(dict(params)) or FakeResponse({"Organisations": pages.pop(0)}))
    assert len(pharmacy.search_organisations({"PostCode": "GL50"})) == 201
    assert asked == [{"PostCode": "GL50", "Limit": 200}, {"PostCode": "GL50", "Limit": 200, "Offset": 200}]


def test_each_district_is_searched_and_duplicates_dropped(monkeypatch):
    ods = FakeOds([], {("RO76", "GL50"): [{"OrgId": "A"}, {"OrgId": None}],
                       ("RO76", "GL51"): [{"OrgId": "A"}, {"OrgId": "B"}]}, {})
    monkeypatch.setattr(pharmacy.requests, "get", ods)
    assert [o["OrgId"] for o in pharmacy.fetch_orgs_for_postcodes({"NonPrimaryRoleId": "RO76"})] == ["A", "B"]
    assert [s["PostCode"] for s in ods.searches] == pharmacy.CHELTENHAM_POSTCODES
    assert all(s["Status"] == "Active" for s in ods.searches)


def test_maps_link_encodes_the_address():
    assert pharmacy.maps_link("1 High St, GL50 1AA") == \
        "https://www.google.com/maps/search/?api=1&query=1+High+St%2C+GL50+1AA"


def test_cqc_ratings_are_keyed_by_ods_code(tmp_path, monkeypatch):
    cqc_file = tmp_path / "cqc.json"
    monkeypatch.setattr(pharmacy, "CQC_FILE", str(cqc_file))
    assert pharmacy.cqc_ratings() == {}
    cqc_file.write_text(json.dumps({"locations": [{"ods_code": "A", "overall": "Good"},
                                                  {"ods_code": "B", "overall": None},
                                                  {"ods_code": None, "overall": "Good"}]}))
    assert pharmacy.cqc_ratings() == {"A": {"ods_code": "A", "overall": "Good"}}


def test_gp_practices_get_details_and_ratings(monkeypatch):
    monkeypatch.setattr(pharmacy, "cqc_ratings", lambda: {"A": GOOD})
    monkeypatch.setattr(pharmacy.requests, "get", FakeOds(
        [], {("RO76", "GL52"): [{"OrgId": "A", "Name": "PRESTBURY SURGERY"},
                                {"OrgId": "B", "Name": "NO DETAIL", "PostCode": "GL52 1AA"}]},
        {"A": detail("236 PRESTBURY ROAD", phone="01242 513975")}))
    first, second = pharmacy.fetch_gp_practices()
    assert first == {"name": "Prestbury Surgery", "address": "236 Prestbury Road, Cheltenham, GL50 1AA",
                     "phone": "01242 513975", "cqc": GOOD}
    assert second == {"name": "No Detail", "address": "GL52 1AA", "phone": "", "cqc": None}


def test_pharmacies_are_merged_across_roles(monkeypatch):
    monkeypatch.setattr(pharmacy.requests, "get", FakeOds(
        [{"id": "R1", "displayName": "Pharmacy"}, {"id": "R2", "displayName": "Pharmacy Site"}],
        {("R1", "GL50"): [{"OrgId": "P1", "Name": "BOOTS"}], ("R2", "GL50"): [{"OrgId": "P1", "Name": "BOOTS"}]},
        {"P1": detail("1 HIGH STREET")}))
    assert pharmacy.fetch_pharmacies() == [{"name": "Boots", "address": "1 High Street, Cheltenham, GL50 1AA",
                                            "phone": ""}]


def test_no_pharmacy_roles_means_no_pharmacies(monkeypatch):
    monkeypatch.setattr(pharmacy.requests, "get", FakeOds([{"id": "X", "displayName": "Other"}], {}, {}))
    assert pharmacy.fetch_pharmacies() == []


def test_main_writes_both_lists(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pharmacy.py"])
    monkeypatch.setattr(pharmacy, "fetch_gp_practices", lambda: [entry("Surgery", "1 Road, GL50 1AA", cqc=GOOD)])
    monkeypatch.setattr(pharmacy, "fetch_pharmacies", lambda: [entry("Boots", "2 Road, GL50 1AA")])
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))
    pharmacy.main()
    assert written["path"] == pharmacy.OUTPUT_FILE
    assert (written["payload"]["gp_count"], written["payload"]["pharmacy_count"]) == (1, 1)


def test_main_still_writes_when_a_list_fails(monkeypatch):
    def down():
        raise requests.ConnectionError("down")

    monkeypatch.setattr(sys, "argv", ["pharmacy.py"])
    monkeypatch.setattr(pharmacy, "fetch_gp_practices", down)
    monkeypatch.setattr(pharmacy, "fetch_pharmacies", down)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(payload))
    pharmacy.main()
    assert (written["gp_count"], written["pharmacy_count"]) == (0, 0)
