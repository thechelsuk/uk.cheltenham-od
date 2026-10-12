"""Offline tests for the planning applications fetcher (planning.py): the
Idox search form and result parsing, the merge/retention store, geocoding
and the render-ready payload. Sessions and requests.post are faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timedelta

import requests

SPEC = importlib.util.spec_from_file_location(
    "planning", pathlib.Path(__file__).resolve().parents[1] / "planning.py"
)
assert SPEC is not None and SPEC.loader is not None
planning = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planning)

FORM_PAGE = """<html><body>
<form action="/online-applications/quick.do"><input name="q"></form>
<form action="monthlyListResults.do?action=firstPage">
  <input type="hidden" name="org.apache.struts.taglib.html.TOKEN" value="tok">
  <input type="hidden" value="no-name">
  <input type="radio" name="dateType" value="DC_Validated" id="validated" checked>
  <label for="validated">Validated</label>
  <input type="radio" name="dateType" value="DC_Decided" id="decided">
  <label for="decided">Decided</label>
  <label><input type="radio" name="dateType" value="DC_Received"> Received in month</label>
  <select name="month"><option value="Oct 26">Oct 26</option><option value="Sep 26">Sep 26</option>
    <option value="Aug 26">Aug 26</option></select>
  <select name="ward"><option value="">All</option><option value="ALL" selected>Everywhere</option></select>
  <select name="empty"></select>
</form></body></html>"""


def result_item(ref, description="Erection of 2 dwellings", status="Pending Consideration",
                address="1 High Street Cheltenham GL50 1AA", received="Mon 06 Oct 2026", decided=None):
    decided_text = f" <span>|</span> Decision Issued: {decided}" if decided else ""
    return f"""<li class="searchresult">
  <a href="/online-applications/applicationDetails.do?keyVal={ref}">{description}</a>
  <p class="address">{address}</p>
  <p class="metaInfo">Ref. No: {ref} <span>|</span> Received: {received}{decided_text}
  <span class="badge-status"><span class="value">{status}</span></span></p>
</li>"""


def results_page(*items, has_next=False):
    nav = '<a class="next" href="#">Next</a>' if has_next else ""
    return f"<ul id='searchresults'>{''.join(items)}</ul>{nav}"


def days_ago(n):
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


# -- Form discovery -----------------------------------------------------------

def test_discover_form_picks_the_month_form_and_its_fields():
    action, fields, month_field, months = planning.discover_form(FORM_PAGE, planning.BASE_URL, "received")
    assert action == "https://publicaccess.cheltenham.gov.uk/online-applications/monthlyListResults.do?action=firstPage"
    assert month_field == "month"
    assert months == ["Oct 26", "Sep 26", "Aug 26"]
    assert fields == {
        "org.apache.struts.taglib.html.TOKEN": "tok",
        "dateType": "DC_Received",
        "month": "Oct 26",
        "ward": "ALL",
    }


def test_discover_form_finds_the_decided_radio_by_its_label():
    _, fields, _, _ = planning.discover_form(FORM_PAGE, planning.BASE_URL, "decided")
    assert fields["dateType"] == "DC_Decided"


def test_discover_form_falls_back_to_the_first_form_and_warns_without_a_month_select():
    action, fields, month_field, months = planning.discover_form(
        '<form action="search.do"><input type="radio" name="t" value="x"></form>', planning.BASE_URL, "decided")
    assert action.endswith("/online-applications/search.do")
    assert (fields, month_field, months) == ({}, None, [])


def test_discover_form_raises_without_any_form():
    try:
        planning.discover_form("<p>maintenance</p>", planning.BASE_URL, "received")
    except RuntimeError as error:
        assert "search form" in str(error)
    else:
        raise AssertionError("expected RuntimeError")


# -- Result parsing -----------------------------------------------------------

def test_parse_results_page_reads_each_application():
    html = results_page(result_item("26/01234/FUL"),
                        result_item("26/00999/HOUSE", description="Single storey rear extension",
                                    status="Granted", received="02 Sep 2026", decided="Fri 10 Oct 2026"),
                        has_next=True)
    records, has_next = planning.parse_results_page(html)
    assert has_next is True
    assert records[0] == {
        "ref": "26/01234/FUL",
        "description": "Erection of 2 dwellings",
        "address": "1 High Street Cheltenham GL50 1AA",
        "postcode": "GL50 1AA",
        "units": 2,
        "status": "Pending Consideration",
        "received_date": "2026-10-06",
        "decided_date": None,
        "url": "https://publicaccess.cheltenham.gov.uk/online-applications/applicationDetails.do?keyVal=26/01234/FUL",
    }
    assert records[1]["decided_date"] == "2026-10-10" and records[1]["units"] is None


def test_parse_result_item_skips_items_without_a_link_or_reference():
    html = "<li class='searchresult'>No link</li><li class='searchresult'><a href='x'>No ref here</a></li>"
    assert planning.parse_results_page(html) == ([], False)


def test_parse_result_item_takes_the_address_from_the_text_when_unmarked():
    html = """<li class="searchresult"><a href="https://example.org/a">New shopfront</a>
      12 Promenade Cheltenham GL50 1LR Ref. No: 26/00001/ADV</li>"""
    (record,), _ = planning.parse_results_page(html)
    assert record["address"] == "12 Promenade Cheltenham GL50 1LR"
    assert record["url"] == "https://example.org/a" and record["status"] == "Unknown"


def test_parse_date_accepts_the_portal_formats():
    assert planning.parse_date("06/10/2026") == "2026-10-06"
    assert planning.parse_date("06.10.26") == "2026-10-06"
    assert planning.parse_date("6 October 2026") == "2026-10-06"
    assert planning.parse_date("soon") is None


def test_extract_postcode_and_units():
    assert planning.extract_postcode("land at gl52 6rt, prestbury") == "GL52 6RT"
    assert planning.extract_postcode("Land off Hales Road") is None
    assert planning.extract_units("Erection of 14 no. dwellings") == 14
    assert planning.extract_units("Conversion into 3x flats") == 3
    assert planning.extract_units("Erection of a dwelling") == 1
    assert planning.extract_units("Replacement windows") is None


# -- Fetching -----------------------------------------------------------------

class FakeResponse:
    def __init__(self, text="", body=None, status=200):
        self.text, self._body, self.status_code = text, body, status
        self.url = "https://example.org"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


class FakeSession:
    """Answers each POST with the next queued page, recording the form data."""
    def __init__(self, pages, form_page=FORM_PAGE):
        self.pages, self.posts, self.form_page = list(pages), [], form_page
        self.headers = {}

    def get(self, url, timeout):
        return FakeResponse(self.form_page)

    def post(self, url, data, timeout):
        self.posts.append(dict(data))
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return FakeResponse(page)


def test_fetch_page_adds_the_page_number_after_the_first_page():
    session = FakeSession(["one", "two"])
    assert planning.fetch_page(session, "url", {"a": 1}, 1) == "one"
    assert planning.fetch_page(session, "url", {"a": 1}, 2) == "two"
    assert session.posts == [{"a": 1}, {"a": 1, "searchCriteria.page": 2}]


def test_fetch_by_date_type_walks_pages_and_months(monkeypatch):
    monkeypatch.setattr(planning.time, "sleep", lambda s: None)
    session = FakeSession([
        results_page(result_item("A/1"), has_next=True),
        results_page(result_item("A/1"), result_item("A/2")),          # Oct page 2: A/1 is a repeat
        results_page(result_item("B/1", received="01 Sep 2026")),       # Sep page 1
    ])
    records = planning.fetch_by_date_type(session, FORM_PAGE, "decided", months=2)
    assert [r["ref"] for r in records] == ["A/1", "A/2", "B/1"]
    assert all(r["decided_date"] == planning.TODAY for r in records)
    assert [p.get("month") for p in session.posts] == ["Oct 26", "Oct 26", "Sep 26"]


def test_fetch_by_date_type_stops_a_month_on_a_request_error_or_no_new_records(monkeypatch):
    monkeypatch.setattr(planning.time, "sleep", lambda s: None)
    session = FakeSession([requests.ConnectionError("down"), results_page()])
    assert planning.fetch_by_date_type(session, FORM_PAGE, "received", months=2) == []


def test_fetch_all_searches_received_then_decided(monkeypatch):
    session = FakeSession([results_page(result_item("A/1")), results_page(result_item("A/1", status="Refused"))])
    monkeypatch.setattr(planning.requests, "Session", lambda: session)
    records = planning.fetch_all(months=1)
    assert [r["status"] for r in records] == ["Pending Consideration", "Refused"]
    assert [p["dateType"] for p in session.posts] == ["DC_Received", "DC_Decided"]


# -- Store --------------------------------------------------------------------

def test_load_existing_reads_both_tables_and_the_legacy_list(tmp_path, monkeypatch):
    store = tmp_path / "planning-applications.json"
    monkeypatch.setattr(planning, "DATA_FILE", store)
    assert planning.load_existing() == {}
    store.write_text(json.dumps({"applications": [{"ref": "A"}], "decided": [{"ref": "B"}, "junk"]}))
    assert set(planning.load_existing()) == {"A", "B"}
    store.write_text(json.dumps([{"ref": "C"}, {"no": "ref"}]))
    assert planning.load_existing() == {"C": {"ref": "C"}}
    store.write_text("{broken")
    assert planning.load_existing() == {}


def test_merge_records_never_blanks_an_existing_value():
    existing = {"A": {"ref": "A", "received_date": "2026-10-01", "status": "Pending"}}
    merged = planning.merge_records(existing, [
        {"ref": "A", "received_date": None, "status": "Granted", "decided_date": "2026-10-09"},
        {"ref": "B", "status": "Pending"},
    ])
    assert merged["A"] == {"ref": "A", "received_date": "2026-10-01", "status": "Granted",
                           "decided_date": "2026-10-09"}
    assert merged["B"] == {"ref": "B", "status": "Pending"}


def test_apply_retention_keeps_records_with_either_date_in_the_window():
    records = {
        "new": {"received_date": days_ago(5)},
        "decided": {"received_date": days_ago(400), "decided_date": days_ago(2)},
        "old": {"received_date": days_ago(200)},
        "undated": {},
    }
    assert set(planning.apply_retention(records)) == {"new", "decided"}


def test_is_decision_and_best_date():
    assert planning.is_decision("Application Permitted")
    assert planning.is_decision("REFUSED")
    assert not planning.is_decision("Pending Consideration")
    assert not planning.is_decision(None)
    assert planning.best_date({"received_date": "2026-01-01"}) == "2026-01-01"
    assert planning.best_date({"received_date": "2026-01-01", "decided_date": "2026-02-01"}) == "2026-02-01"
    assert planning.best_date({}) == ""


def test_geocode_missing_looks_up_each_new_postcode_once(monkeypatch):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(json["postcodes"])
        return FakeResponse(body={"result": [
            {"query": "GL50 1AA", "result": {"latitude": 51.9, "longitude": -2.07}},
            {"query": "ZZ1 1ZZ", "result": None},
        ]})

    monkeypatch.setattr(planning.requests, "post", fake_post)
    records = {
        "A": {"postcode": "GL50 1AA"},
        "B": {"postcode": "ZZ1 1ZZ"},
        "C": {"postcode": "GL52 2BB", "lat": 1, "lon": 2},
        "D": {"postcode": None},
    }
    planning.geocode_missing(records)
    assert calls == [["GL50 1AA", "ZZ1 1ZZ"]]
    assert (records["A"]["lat"], records["A"]["lon"]) == (51.9, -2.07)
    assert (records["B"]["lat"], records["B"]["lon"]) == (None, None)
    assert records["C"]["lat"] == 1 and "lat" not in records["D"]

    calls.clear()
    planning.geocode_missing(records)
    assert calls == []


def test_geocode_missing_leaves_postcodes_for_next_run_when_the_lookup_fails(monkeypatch):
    def failing_post(*args, **kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(planning.requests, "post", failing_post)
    records = {"A": {"postcode": "GL50 1AA"}}
    planning.geocode_missing(records)
    assert "lat" not in records["A"]


def test_build_payload_splits_received_and_decided_tables():
    records = {
        "A": {"ref": "A", "received_date": days_ago(1), "status": "Pending Consideration"},
        "B": {"ref": "B", "received_date": days_ago(10), "status": "Granted", "decided_date": days_ago(3)},
        "C": {"ref": "C", "received_date": days_ago(300), "status": "Refused", "decided_date": days_ago(5)},
    }
    payload = planning.build_payload(records)
    assert [r["ref"] for r in payload["applications"]] == ["A", "B"]
    assert [r["ref"] for r in payload["decided"]] == ["B", "C"]
    assert (payload["received_count"], payload["pending"], payload["decided_count"]) == (2, 1, 2)
    assert (payload["date_from"], payload["date_to"]) == (days_ago(10), days_ago(1))
    assert payload["lookback_days"] == planning.RETENTION_DAYS


def test_build_payload_without_records_has_no_date_range():
    payload = planning.build_payload({})
    assert payload["date_from"] is None and payload["applications"] == []


def test_save_payload_writes_the_data_file(tmp_path, monkeypatch):
    monkeypatch.setattr(planning, "DATA_DIR", tmp_path / "_data")
    monkeypatch.setattr(planning, "DATA_FILE", tmp_path / "_data" / "planning.json")
    planning.save_payload({"received_count": 0, "decided_count": 0})
    assert json.loads((tmp_path / "_data" / "planning.json").read_text()) == {"received_count": 0, "decided_count": 0}


def test_main_leaves_the_store_alone_when_nothing_is_fetched(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["planning.py"])
    monkeypatch.setattr(planning, "fetch_all", lambda months: [])
    saved = []
    monkeypatch.setattr(planning, "save_payload", saved.append)
    planning.main()
    assert saved == []


def test_main_merges_retains_geocodes_and_saves(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["planning.py", "--deep"])
    months_asked = []
    monkeypatch.setattr(planning, "fetch_all", lambda months: months_asked.append(months) or
                        [{"ref": "A", "received_date": days_ago(1), "status": "Pending", "postcode": None}])
    monkeypatch.setattr(planning, "load_existing", lambda: {})
    saved = []
    monkeypatch.setattr(planning, "save_payload", saved.append)
    planning.main()
    assert months_asked == [planning.MONTHS_DEEP]
    assert saved[0]["received_count"] == 1
