"""Offline tests for the CQC fetcher (cqc.py) and its API source
(cqc_source.py): ratings, location records, grouping, re-registrations and
page addresses. helper.get and the geocoder are replaced with fakes.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import pytest

import cqc
import cqc_source
import helper


def detail(location_id="1-100", name="Rose House", **extra):
    record = {"locationId": location_id, "name": name, "postalCode": " gl52 3aa ",
              "postalAddressLine1": "1 Rose Lane,", "postalAddressLine2": " ", "postalAddressTownCity": "Cheltenham",
              "gacServiceTypes": [{"name": "Residential homes"}, {"name": "Residential homes"}],
              "specialisms": [{"name": "Dementia"}],
              "inspectionCategories": [{"name": "Residential social care", "primary": "True"}],
              "website": "www.rosehouse.example", "odsCode": ""}
    record.update(extra)
    return record


def overall(rating, date, **questions):
    return {"overall": {"rating": rating, "reportDate": date,
                        "keyQuestionRatings": [{"name": n, "rating": r} for n, r in questions.items()]}}


# -- cqc_source -----------------------------------------------------------------

def test_small_helpers():
    assert cqc_source._postcode_ok("gl50 1aa", {"GL50"})
    assert not cqc_source._postcode_ok(None, {"GL50"})
    assert cqc_source._website(" www.example.org ") == "https://www.example.org"
    assert cqc_source._website("HTTP://example.org") == "HTTP://example.org"
    assert cqc_source._website("") is None
    assert cqc_source._rating(" requires Improvement ") == "Requires improvement"
    assert cqc_source._rating("Not rated") is None


def test_latest_rating_prefers_the_newest_of_inspection_or_assessment():
    inspected = overall("Good", "2023-05-01", Safe="Good", Caring="outstanding")
    assert cqc_source._latest_rating({"currentRatings": inspected}) == (
        "Good", "2023-05-01", {"safe": "Good", "caring": "Outstanding"})

    assessed = {"currentRatings": inspected, "assessment": [{
        "assessmentPlanPublishedDateTime": "2025-02-03T10:00:00",
        "ratings": {"asgRatings": [{"rating": "Requires Improvement",
                                    "keyQuestionRatings": [{"name": "Well-led", "rating": "Inadequate"},
                                                           {"name": "Other", "rating": "Good"}]}]}}]}
    assert cqc_source._latest_rating(assessed) == ("Requires improvement", "2025-02-03", {"well_led": "Inadequate"})


def test_latest_rating_without_any_rating():
    assert cqc_source._latest_rating({"currentRatings": overall("Not rated", "2024-01-01")}) == (None, None, {})
    assert cqc_source._latest_rating({}) == (None, None, {})


def test_location_builds_the_record_the_pages_use():
    record = cqc_source._location(detail(currentRatings=overall("Good", "2024-06-01", Safe="Good")))
    assert record == {
        "id": "1-100", "ods_code": None, "name": "Rose House", "address": "1 Rose Lane, Cheltenham",
        "postcode": "GL52 3AA", "website": "https://www.rosehouse.example",
        "url": "https://www.cqc.org.uk/location/1-100",
        "service_types": ["Residential homes"], "specialisms": ["Dementia"],
        "category": "Residential social care", "care_home": True, "overall": "Good", "published": "2024-06-01",
        "ratings": {"safe": "Good", "effective": None, "caring": None, "responsive": None, "well_led": None},
    }


def test_location_spots_gps_and_care_homes_by_flag():
    gp = cqc_source._location(detail(gacServiceTypes=[{"name": "Doctors/Gps"}], inspectionCategories=None,
                                     careHome="N"))
    assert gp["service_types"] == ["Doctors/GPs"] and gp["care_home"] is False and gp["category"] is None
    flagged = cqc_source._location(detail(gacServiceTypes=[], careHome="Y"))
    assert flagged["care_home"] is True


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_load_locations_pages_the_list_and_skips_deregistered(monkeypatch):
    monkeypatch.setenv("CQC_KEY", "test-key")
    pages = {1: {"totalPages": 2, "locations": [{"locationId": "1-3", "postalCode": "GL50 1AA"},
                                                {"locationId": "1-9", "postalCode": "GL1 1AA"}]},
             2: {"totalPages": 2, "locations": [{"locationId": "1-2", "postalCode": "GL51 1AA"}]}}
    details = {"1-3": detail("1-3"), "1-2": detail("1-2", registrationStatus="Deregistered")}
    asked = []

    def fake_get(url, headers, params, timeout):
        asked.append(headers)
        path = url[len(cqc_source.API):]
        if path == "/locations":
            return FakeResponse(pages[params["page"]])
        return FakeResponse(details[path.rsplit("/", 1)[1]])

    monkeypatch.setattr(helper, "get", fake_get)
    assert [loc["id"] for loc in cqc_source.load_locations({"GL50", "GL51"})] == ["1-3"]
    assert asked[0] == {"Ocp-Apim-Subscription-Key": "test-key"}


def test_get_needs_the_api_key(monkeypatch):
    monkeypatch.delenv("CQC_KEY", raising=False)
    with pytest.raises(RuntimeError, match="CQC_KEY"):
        cqc_source._get("/locations")


# -- cqc ------------------------------------------------------------------------

def loc(location_id, name="Rose House", postcode="GL52 3AA", types=("Residential homes",), care_home=True,
        category=None, rating=None, website=None, kind=None):
    return {"id": location_id, "name": name, "postcode": postcode, "service_types": list(types),
            "care_home": care_home, "category": category, "overall": rating, "published": None,
            "ratings": {}, "overall_rank": 9, "url": f"https://www.cqc.org.uk/location/{location_id}",
            "website": website, "kind": kind}


def test_kind_sorts_locations_into_lists():
    assert cqc.kind(loc("1-1", types=("Nursing homes",))) == "nursing_home"
    assert cqc.kind(loc("1-1")) == "residential_home"
    assert cqc.kind(loc("1-1", types=("Homecare agencies",), care_home=False)) == "home_care"
    assert cqc.kind(loc("1-1", types=(), care_home=False, category="GP Practices")) == "gp"
    assert cqc.kind(loc("1-1", types=("Doctors/GPs",), care_home=False)) == "gp"
    assert cqc.kind(loc("1-1", types=("Dentists",), care_home=False)) is None


def test_slugify():
    assert cqc.slugify("St. Mary’s Care Home") == "st-marys-care-home"


def test_merge_reregistrations_keeps_the_newest_with_the_old_rating():
    old = loc("1-100", rating="Good", website="https://rose.example")
    new = loc("1-2000", name="Rose house")
    other = loc("1-5", name="Ivy Lodge", rating="Outstanding")
    merged = cqc.merge_reregistrations([old, new, other])
    assert [m["id"] for m in merged] == ["1-2000", "1-5"]
    current = merged[0]
    assert current["overall"] == "Good" and current["previous_registration"] is True
    assert current["previous_url"] == "https://www.cqc.org.uk/location/1-100"
    assert current["website"] == "https://rose.example"
    assert merged[1]["previous_registration"] is False


def test_add_slugs_adds_the_district_to_shared_names_and_skips_gps():
    locations = [loc("1-1", kind="residential_home"), loc("1-2", postcode="GL50 1AA", kind="home_care"),
                 loc("1-3", name="Ivy Lodge", kind="nursing_home"), loc("1-4", name="Surgery", kind="gp")]
    cqc.add_slugs(locations)
    assert [x["slug"] for x in locations] == ["rose-house-gl52", "rose-house-gl50", "ivy-lodge", None]


def test_main_geocodes_ranks_and_summarises(monkeypatch):
    sources = [loc("1-1", name="Ivy Lodge", types=("Nursing homes",), rating="Good"),
               loc("1-2", name="Bay Care", types=("Homecare agencies",), care_home=False, postcode=""),
               loc("1-3", name="Rose House", rating="Inadequate"),
               loc("1-4", name="Dentist", types=("Dentists",), care_home=False)]
    monkeypatch.setattr(cqc_source, "load_locations", lambda districts: sources)
    monkeypatch.setattr(helper, "geocode_postcodes", lambda postcodes: {"GL52 3AA": (51.9, -2.05)})
    monkeypatch.setattr(helper, "miles_from_centre", lambda lat, lon: 1.234)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(payload))

    cqc.main()

    names = [x["name"] for x in written["locations"]]
    assert names == ["Bay Care", "Ivy Lodge", "Rose House"]
    bay, ivy, rose = written["locations"]
    assert bay["lat"] is None and bay["distance_miles"] is None
    assert ivy["lat"] == 51.9 and ivy["distance_miles"] == 1.2 and ivy["overall_rank"] == 2
    assert rose["overall_rank"] == 4 and bay["overall_rank"] == 9
    assert written["summary"] == {"care_homes": 2, "nursing_homes": 1, "home_care": 1,
                                  "care_homes_good_or_better": 1, "care_homes_rated": 2}


def test_main_refuses_two_locations_with_one_page_address(monkeypatch):
    same_district = [loc("1-1", name="A&B", postcode="GL52 3AA"), loc("1-2", name="A B", postcode="GL52 9ZZ")]
    monkeypatch.setattr(cqc_source, "load_locations", lambda districts: same_district)
    monkeypatch.setattr(helper, "geocode_postcodes", lambda postcodes: {})
    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(payload))
    with pytest.raises(RuntimeError, match="share a page address"):
        cqc.main()
    assert written == []
