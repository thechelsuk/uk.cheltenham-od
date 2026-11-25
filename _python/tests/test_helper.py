"""Offline tests for the shared fetcher settings and helpers. Nothing here
touches the network: requests.request is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import ast
import json
import pathlib
import socket
import subprocess
import sys
from datetime import date, datetime, timezone

import pytest
import requests

import config
import helper


class Calls(list):
    """A list of recorded requests that can also carry the answer queues."""


class FakeResponse:
    def __init__(self, status=200, body=None, text="", headers=None):
        self.status_code = status
        self._body = body
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


@pytest.fixture
def calls(monkeypatch):
    """Records every request and answers from a queue of responses (or
    exceptions) keyed by URL; the last answer for a URL repeats."""
    record = Calls()
    answers = {}

    def fake_request(method, url, **kwargs):
        record.append({"method": method, "url": url, **kwargs})
        queue = answers.get(url) or [FakeResponse()]
        answer = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(helper.requests, "request", fake_request)
    monkeypatch.setattr(helper.time, "sleep", lambda seconds: None)
    record.answers = answers
    return record


# --- settings ---------------------------------------------------------------

def test_centre_is_the_one_town_centre_point():
    assert config.CENTRE == (51.8994, -2.0783)


def test_headers_carry_the_site_user_agent():
    assert config.HEADERS == {"User-Agent": config.USER_AGENT}
    assert "cheltenham-od" in config.USER_AGENT


# --- distances --------------------------------------------------------------

def test_haversine_one_degree_of_longitude_at_the_equator():
    assert helper.haversine_miles(0, 0, 0, 1) == pytest.approx(69.09, abs=0.01)


def test_haversine_km_matches_miles():
    assert helper.haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.01)
    assert helper.haversine_km(51.9, -2.0, 52.0, -2.1) == pytest.approx(
        helper.haversine_miles(51.9, -2.0, 52.0, -2.1) * 1.609344, rel=1e-3)


def test_haversine_is_zero_for_the_same_point():
    assert helper.haversine_miles(51.9, -2.08, 51.9, -2.08) == 0


def test_miles_from_centre_is_measured_from_config_centre():
    lat, lon = config.CENTRE
    assert helper.miles_from_centre(lat, lon) == 0
    # Gloucester Cross: about 7.1 miles west and 2.4 miles south, so ~7.5
    assert helper.miles_from_centre(51.8652, -2.2448) == pytest.approx(7.5, abs=0.2)


# --- HTTP -------------------------------------------------------------------

def test_get_sends_site_user_agent_and_default_timeout(calls):
    helper.get("https://example.test/a", params={"q": 1})
    sent = calls[0]
    assert sent["method"] == "GET"
    assert sent["headers"]["User-Agent"] == config.USER_AGENT
    assert sent["timeout"] == 30
    assert sent["params"] == {"q": 1}


def test_get_merges_extra_headers_and_keeps_user_agent(calls):
    helper.get("https://example.test/a", headers={"Accept": "application/json"}, timeout=5)
    sent = calls[0]
    assert sent["headers"] == {"User-Agent": config.USER_AGENT, "Accept": "application/json"}
    assert sent["timeout"] == 5


def test_get_retries_a_transient_server_error(calls):
    calls.answers["https://example.test/b"] = [FakeResponse(503), FakeResponse(200, body={"ok": True})]
    assert helper.get("https://example.test/b").json() == {"ok": True}
    assert len(calls) == 2


def test_post_sends_json_with_user_agent(calls):
    helper.post("https://example.test/p", json={"x": 1})
    assert calls[0]["method"] == "POST"
    assert calls[0]["json"] == {"x": 1}
    assert calls[0]["headers"]["User-Agent"] == config.USER_AGENT


# --- Overpass ---------------------------------------------------------------

def test_overpass_returns_elements_from_the_first_endpoint(calls):
    first = config.OVERPASS_ENDPOINTS[0]
    calls.answers[first] = [FakeResponse(200, body={"elements": [{"id": 1}]})]
    assert helper.overpass("[out:json];node;out;") == [{"id": 1}]
    assert calls[0]["data"] == {"data": "[out:json];node;out;"}
    assert len(calls) == 1


def test_overpass_falls_back_to_the_next_endpoint(calls):
    first, second = config.OVERPASS_ENDPOINTS[:2]
    calls.answers[first] = [requests.ConnectionError("down")]
    calls.answers[second] = [FakeResponse(200, body={"elements": [{"id": 2}]})]
    assert helper.overpass("q") == [{"id": 2}]
    assert {c["url"] for c in calls} == {first, second}


def test_overpass_treats_a_non_json_reply_as_a_failure(calls):
    first, second = config.OVERPASS_ENDPOINTS[:2]
    calls.answers[first] = [FakeResponse(200, body=ValueError("not json"))]
    calls.answers[second] = [FakeResponse(200, body={"elements": []})]
    assert helper.overpass("q") == []


def test_overpass_rejects_a_partial_result_that_timed_out(calls):
    """Overpass returns what it had so far, plus a remark, when a query runs
    out of time; that must not be saved as if it were complete."""
    first, second = config.OVERPASS_ENDPOINTS[:2]
    calls.answers[first] = [FakeResponse(200, body={
        "elements": [{"id": 1}],
        "remark": "runtime error: Query timed out in \"query\" at line 1 after 91 seconds.",
    })]
    calls.answers[second] = [FakeResponse(200, body={"elements": [{"id": 1}, {"id": 2}]})]
    assert helper.overpass("q") == [{"id": 1}, {"id": 2}]


def test_overpass_raises_when_every_endpoint_fails(calls):
    for endpoint in config.OVERPASS_ENDPOINTS:
        calls.answers[endpoint] = [requests.ConnectionError("down")]
    with pytest.raises(RuntimeError):
        helper.overpass("q")


# --- Nomis ------------------------------------------------------------------

def test_nomis_rows_parses_the_csv(calls):
    url = f"{config.NOMIS_API}/NM_1_1.data.csv"
    calls.answers[url] = [FakeResponse(200, text='"DATE","OBS_VALUE"\n"2024","5"\n"2025","6"\n')]
    rows = helper.nomis_rows("NM_1_1", geography="X", date="latest")
    assert rows == [{"DATE": "2024", "OBS_VALUE": "5"}, {"DATE": "2025", "OBS_VALUE": "6"}]
    assert calls[0]["params"] == {"geography": "X", "date": "latest"}
    assert calls[0]["timeout"] == 30


def test_nomis_rows_takes_a_longer_timeout_for_big_downloads(calls):
    helper.nomis_rows("NM_1_1", timeout=60, geography="X")
    assert calls[0]["timeout"] == 60
    assert calls[0]["params"] == {"geography": "X"}


# --- NHS directory and postcodes ---------------------------------------------

def test_ods_get_asks_for_json(calls):
    url = f"{config.ODS_API}/organisations/ABC"
    calls.answers[url] = [FakeResponse(200, body={"Organisation": {}})]
    assert helper.ods_get("organisations/ABC") == {"Organisation": {}}
    assert calls[0]["headers"]["Accept"] == "application/json"


def test_ods_address_joins_the_non_empty_lines(calls):
    url = f"{config.ODS_API}/organisations/ABC"
    location = {"AddrLn1": "1 HIGH STREET", "AddrLn2": None, "Town": "CHELTENHAM", "County": "GLOUCESTERSHIRE"}
    calls.answers[url] = [FakeResponse(200, body={"Organisation": {"GeoLoc": {"Location": location}}})]
    assert helper.ods_address("ABC") == "1 High Street, Cheltenham, Gloucestershire"


def test_geocode_postcodes_skips_unknown_postcodes(calls):
    calls.answers[config.POSTCODES_API] = [FakeResponse(200, body={"result": [
        {"query": "GL50 1AA", "result": {"latitude": 51.9, "longitude": -2.07}},
        {"query": "ZZ1 1ZZ", "result": None},
    ]})]
    assert helper.geocode_postcodes({"GL50 1AA", "ZZ1 1ZZ"}) == {"GL50 1AA": (51.9, -2.07)}
    assert calls[0]["json"] == {"postcodes": ["GL50 1AA", "ZZ1 1ZZ"]}


# --- UK time ------------------------------------------------------------------

def fixed_clock(instant):
    """A datetime class whose now() is pinned to a UTC instant, with a naive
    now() reading UTC like a GitHub Actions runner's clock."""
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
    return Clock


def test_updated_timestamp_shows_uk_summer_time_on_a_utc_runner(monkeypatch):
    monkeypatch.setattr(helper, "datetime", fixed_clock(datetime(2026, 7, 1, 12, 5, tzinfo=timezone.utc)))
    assert helper.updated_timestamp() == "1 July 2026 at 13:05"


def test_updated_timestamp_matches_utc_in_winter(monkeypatch):
    monkeypatch.setattr(helper, "datetime", fixed_clock(datetime(2026, 12, 1, 12, 5, tzinfo=timezone.utc)))
    assert helper.updated_timestamp() == "1 December 2026 at 12:05"


def test_uk_today_rolls_over_at_uk_midnight_not_utc(monkeypatch):
    monkeypatch.setattr(helper, "datetime", fixed_clock(datetime(2026, 7, 1, 23, 36, tzinfo=timezone.utc)))
    assert helper.uk_today() == date(2026, 7, 2)
    assert helper.uk_now().strftime("%Y-%m-%d %H:%M") == "2026-07-02 00:36"
    assert helper.updated_timestamp() == "2 July 2026 at 00:36"


# --- writing ------------------------------------------------------------------

def test_write_json_creates_the_folder_and_keeps_unicode(tmp_path):
    out = tmp_path / "new" / "data.json"
    helper.write_json(out, {"name": "Café"})
    assert json.loads(out.read_text()) == {"name": "Café"}
    assert "Café" in out.read_text()


# --- every script can reach helper and config ------------------------------

PYTHON_DIR = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = sorted(p for folder in ("", "local", "pi") for p in (PYTHON_DIR / folder).glob("*.py"))
SUBFOLDER_SCRIPTS = [p for p in SCRIPTS if p.parent != PYTHON_DIR]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: str(p.relative_to(PYTHON_DIR)))
def test_script_compiles(script):
    compile(script.read_text(), str(script), "exec")


@pytest.mark.parametrize("script", SUBFOLDER_SCRIPTS, ids=lambda p: str(p.relative_to(PYTHON_DIR)))
def test_subfolder_script_puts_python_dir_on_the_path_before_importing_helper(script):
    """_python/local and _python/pi scripts import helper/config from the
    parent folder, so they must add it to sys.path before those imports."""
    tree = ast.parse(script.read_text())
    lines = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Import) and {a.name for a in n.names} & {"helper", "config"}
             or isinstance(n, ast.ImportFrom) and n.module in {"helper", "config"}]
    if not lines:
        return
    inserts = [n.lineno for n in ast.walk(tree)
               if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "insert"
               and getattr(getattr(n.func, "value", None), "attr", "") == "path"]
    assert inserts and min(inserts) < min(lines), "sys.path.insert(0, <_python>) must come before import helper/config"


@pytest.mark.parametrize("folder", ["local", "pi"])
def test_helper_and_config_import_from_a_subfolder(folder):
    """As a local or Pi script sees it: _python on the path, run from elsewhere."""
    code = f"import sys; sys.path.insert(0, {str(PYTHON_DIR)!r}); import helper, config; print(config.CENTRE)"
    result = subprocess.run([sys.executable, "-c", code], cwd=PYTHON_DIR / folder, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(config.CENTRE)


SQUARE = [[51.0, -2.0], [51.0, -1.0], [52.0, -1.0], [52.0, -2.0], [51.0, -2.0]]


def test_point_in_ring_uses_lat_lon_points():
    assert helper.point_in_ring(51.5, -1.5, SQUARE)
    assert not helper.point_in_ring(52.5, -1.5, SQUARE)
    assert not helper.point_in_ring(51.5, -2.5, SQUARE)


def test_ward_for_names_the_ward_containing_a_point():
    wards = [{"name": "Square", "slug": "square", "boundary": SQUARE},
             {"name": "Elsewhere", "slug": "elsewhere", "boundary": [[0, 0], [0, 1], [1, 1], [0, 0]]}]
    assert helper.ward_for(51.5, -1.5, wards) == {"name": "Square", "slug": "square"}
    assert helper.ward_for(53.0, -1.5, wards) is None


def test_record_seen_keeps_first_and_last_seen_dates():
    records = helper.record_seen([], [{"id": "A", "street": "High St", "lat": 51.9}], ["street"], "2026-10-11")
    assert records == [{"id": "A", "street": "High St", "first_seen": "2026-10-11", "last_seen": "2026-10-11"}]
    records = helper.record_seen(records, [{"id": "A", "street": "High Street"}], ["street"], "2026-10-12")
    assert records == [{"id": "A", "street": "High Street", "first_seen": "2026-10-11", "last_seen": "2026-10-12"}]


def test_record_seen_keeps_items_that_have_gone_and_drops_old_ones():
    old = {"id": "OLD", "first_seen": "2025-01-01", "last_seen": "2025-01-05"}
    gone = {"id": "GONE", "first_seen": "2026-09-01", "last_seen": "2026-09-03"}
    records = helper.record_seen([old, gone], [{"id": "NEW"}], [], "2026-10-11", keep_days=365)
    assert [r["id"] for r in records] == ["NEW", "GONE"]


def test_write_json_leaves_a_file_alone_when_only_its_timestamp_changes(tmp_path):
    path = tmp_path / "data.json"
    assert helper.write_json(path, {"generated_at": "2026-10-11T10:00:00", "items": [1, 2]}) is True
    assert helper.write_json(path, {"generated_at": "2026-10-12T10:00:00", "items": [1, 2]}) is False
    assert json.loads(path.read_text())["generated_at"] == "2026-10-11T10:00:00"
    assert helper.write_json(path, {"generated_at": "2026-10-12T11:00:00", "items": [1, 2, 3]}) is True
    assert json.loads(path.read_text())["generated_at"] == "2026-10-12T11:00:00"


def test_alert_rows_are_list_items_with_the_alert_kind_marker():
    html = helper.alert_rows("bus", [("/buses", "Disruption to Stagecoach West bus services")])
    assert html == (
        '  <li class="latest-item latest-item-kind">'
        '{% include kind.html group="alerts" kind="bus" part="dot" %}'
        '<span class="latest-title">{% include kind.html group="alerts" kind="bus" part="label" %}'
        '<a href="/buses">Disruption to Stagecoach West bus services</a></span></li>'
    )


def test_alert_rows_are_empty_with_nothing_to_show():
    assert helper.alert_rows("bus", []) == ""


def test_title_case_follows_ap_style():
    assert helper.title_case("Mystery shopper") == "Mystery Shopper"
    assert helper.title_case("Getting Around near All Saints") == "Getting Around Near All Saints"
    assert helper.title_case("Streets with the Most Reports") == "Streets With the Most Reports"
    assert helper.title_case("Employment Rates over Time") == "Employment Rates over Time"
    assert (helper.title_case("Employment Locum - 15-20 hours per week - 3+ months - remote working")
            == "Employment Locum - 15-20 Hours per Week - 3+ Months - Remote Working")


def test_title_case_handles_curly_apostrophes_and_styled_words():
    assert helper.title_case("Why you’ll like it") == "Why You’ll Like It"
    assert helper.title_case("Why you'll like It") == "Why You'll Like It"
    assert helper.title_case("Parking near GL50 on eBay") == "Parking Near GL50 on eBay"


def test_title_case_fixes_an_all_capitals_heading():
    assert helper.title_case("THE BEST PLACES TO VISIT") == "The Best Places to Visit"


FOOTER_TAG = "{% capture feed_footer %}{% include feed-footer.html %}{% endcapture %}{{ feed_footer | xml_escape }}"


def atom_entries(path):
    import xml.etree.ElementTree as ET
    body = path.read_text().split("---\n", 2)[2]
    ns = {"a": "http://www.w3.org/2005/Atom"}
    return ET.fromstring(body).findall("a:entry", ns), ns


def test_atom_writer_adds_the_feed_footer_to_each_entry_when_asked(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "Road closed", "link": "https://example.test/x", "summary": "A & B roads"}],
                            path, "/feeds/f.xml", "f", "f", "https://example.test/self", "https://example.test/f",
                            footer=True)
    (entry,), ns = atom_entries(path)
    content = entry.find("a:content", ns)
    assert content.get("type") == "html"
    assert content.text == "<p>A &amp; B roads</p>" + FOOTER_TAG
    assert entry.find("a:summary", ns).text == "A & B roads"


def test_atom_writer_leaves_out_the_footer_by_default(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "x", "link": "https://example.test/x"}], path,
                            "/feeds/f.xml", "f", "f", "https://example.test/self", "https://example.test/f")
    (entry,), ns = atom_entries(path)
    assert entry.find("a:content", ns) is None



def test_atom_writer_makes_relative_links_and_ids_absolute(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "x", "link": "/news/new-post"}], path, "/feeds/f.xml", "f", "f",
                            "https://example.test/feeds/f.xml", "https://example.test/f")
    (entry,), ns = atom_entries(path)
    assert entry.find("a:link", ns).get("href") == "https://example.test/news/new-post"
    assert entry.find("a:id", ns).text == "https://example.test/news/new-post"


def test_atom_writer_keeps_a_legacy_id_as_it_was_but_makes_its_link_absolute(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "x", "link": "/news/old-post"}, {"title": "y", "link": "/news/new-post"}],
                            path, "/feeds/f.xml", "f", "f", "https://example.test/feeds/f.xml",
                            "https://example.test/f", legacy_ids={"/news/old-post"})
    old, new = atom_entries(path)[0]
    ns = atom_entries(path)[1]
    assert old.find("a:link", ns).get("href") == "https://example.test/news/old-post"
    assert old.find("a:id", ns).text == "/news/old-post"
    assert new.find("a:id", ns).text == "https://example.test/news/new-post"


def test_atom_writer_leaves_external_links_alone(tmp_path):
    path = tmp_path / "f.xml"
    helper.write_items_atom([{"title": "x", "link": "https://other.test/a?b=1"}], path, "/feeds/f.xml", "f", "f",
                            "https://example.test/feeds/f.xml", "https://example.test/f")
    (entry,), ns = atom_entries(path)
    assert entry.find("a:link", ns).get("href") == entry.find("a:id", ns).text == "https://other.test/a?b=1"


# --- website checks ------------------------------------------------------

@pytest.fixture
def dead_list(tmp_path, monkeypatch):
    path = tmp_path / "dead-websites.json"
    path.write_text(json.dumps({"last_checked": "2026-11-15", "websites": [
        {"url": "https://leygore.manor/", "checked": "2026-11-15", "reason": "Not a valid web address"},
        {"url": "http://live.example.org.uk/old-page.aspx", "checked": "2026-11-15", "reason": "Redirects to an unrelated page"},
    ]}))
    monkeypatch.setattr(helper, "DEAD_WEBSITES_FILE", path)
    helper.dead_websites.cache_clear()
    yield
    helper.dead_websites.cache_clear()


@pytest.mark.parametrize("url", [
    "https://leygore.manor/",
    "http://leygore.manor",                    # scheme and trailing slash don't matter
    "https://www.LEYGORE.manor/",              # nor www. or the host's case
    "https://live.example.org.uk/old-page.aspx",
])
def test_listed_websites_are_dead(dead_list, url):
    assert helper.is_dead_website(url)


@pytest.mark.parametrize("url", ["https://live.example.org.uk/", "https://www.other.example.org.uk/", "", None])
def test_other_websites_are_not_listed(dead_list, url):
    assert not helper.is_dead_website(url)


def test_the_real_dead_websites_list_loads():
    helper.dead_websites.cache_clear()
    data = json.loads(helper.DEAD_WEBSITES_FILE.read_text())
    for entry in data["websites"]:
        assert entry["url"].startswith(("http://", "https://")), entry
        assert entry["reason"] and entry["checked"], entry


@pytest.mark.parametrize("raw, expected", [
    ("www.example.org.uk", "http://www.example.org.uk"),     # no scheme: http, and a site with https redirects
    ("example.org.uk/about", "http://example.org.uk/about"),
    ("https://www.example.org.uk", "https://www.example.org.uk"),
    ("HTTP://example.org.uk", "HTTP://example.org.uk"),
    ("http:/example.org.uk", "http://example.org.uk"),        # a slash missing
    ("  ", ""),
    (None, ""),
])
def test_web_address(raw, expected):
    assert helper.web_address(raw) == expected


class FakeCheckResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def close(self):
        pass


def resolves(monkeypatch, error=None):
    def fake_getaddrinfo(host, port):
        if error is not None:
            raise socket.gaierror(error, "lookup failed")
        return [("addr",)]
    monkeypatch.setattr(helper.socket, "getaddrinfo", fake_getaddrinfo)


def answers(monkeypatch, status=None, error=None):
    def fake_get(url, **kwargs):
        if error is not None:
            raise error
        return FakeCheckResponse(status)
    monkeypatch.setattr(helper.requests, "get", fake_get)


def test_a_domain_that_doesnt_exist_is_dead(monkeypatch):
    resolves(monkeypatch, socket.EAI_NONAME)
    assert helper._probe("https://www.lapsed.example.org.uk/") == "Domain not found"


def test_a_failed_lookup_isnt_taken_as_dead(monkeypatch):
    resolves(monkeypatch, socket.EAI_AGAIN)
    assert helper._probe("https://www.example.org.uk/") is None


@pytest.mark.parametrize("status, expected", [
    (404, "Page not found (404)"), (410, "Page gone (410)"), (200, None), (403, None), (500, None),
])
def test_only_404_and_410_count_as_dead(monkeypatch, status, expected):
    resolves(monkeypatch)
    answers(monkeypatch, status)
    assert helper._probe("https://www.example.org.uk/page") == expected


def test_a_timeout_or_certificate_error_isnt_taken_as_dead(monkeypatch):
    resolves(monkeypatch)
    answers(monkeypatch, error=requests.exceptions.SSLError("bad certificate"))
    assert helper._probe("https://www.example.org.uk/") is None


def test_the_wayback_machine_copy_is_found(monkeypatch):
    seen = {}

    def fake_get(url, params=None, **kwargs):
        seen.update(params)
        return FakeCheckResponse(200, {"archived_snapshots": {"closest": {
            "available": True, "status": "200", "url": "http://web.archive.org/web/2019/http://lapsed.example.org/"}}})
    monkeypatch.setattr(helper.requests, "get", fake_get)
    assert helper._archive("https://www.lapsed.example.org/") == "https://web.archive.org/web/2019/http://lapsed.example.org/"
    assert seen["url"] == "www.lapsed.example.org"


def test_no_wayback_copy(monkeypatch):
    monkeypatch.setattr(helper.requests, "get", lambda url, **kwargs: FakeCheckResponse(200, {"archived_snapshots": {}}))
    assert helper._archive("https://www.lapsed.example.org/") is None


@pytest.fixture
def checks_dir(tmp_path, monkeypatch, dead_list):
    monkeypatch.setattr(helper, "WEBSITE_CHECKS_DIR", tmp_path / "website-checks")
    probed = []
    monkeypatch.setattr(helper, "_probe", lambda url: probed.append(url) or ("Domain not found" if "lapsed" in url else None))
    monkeypatch.setattr(helper, "_archive", lambda url: "https://web.archive.org/web/2020/" + url if "lapsed" in url else None)
    return probed


def test_websites_are_checked_and_the_results_kept(checks_dir):
    urls = ["https://lapsed.example.org/", "https://live.example.org/", "https://leygore.manor", "", None]
    checks = helper.check_websites(urls, "test", today=date(2026, 11, 15))
    assert sorted(checks_dir) == ["https://lapsed.example.org/", "https://live.example.org/"]
    assert checks["https://lapsed.example.org/"] == {
        "checked": "2026-11-15", "dead": "Domain not found",
        "archive": "https://web.archive.org/web/2020/https://lapsed.example.org/"}
    assert checks["https://live.example.org/"] == {"checked": "2026-11-15", "dead": None, "archive": None}
    assert checks["https://leygore.manor"]["dead"] == "Not a valid web address"
    saved = json.loads((helper.WEBSITE_CHECKS_DIR / "test.json").read_text())
    assert saved["websites"] == checks


def test_a_recent_check_is_reused_and_an_old_one_redone(checks_dir):
    urls = ["https://lapsed.example.org/", "https://live.example.org/"]
    helper.check_websites(urls, "test", today=date(2026, 11, 15))
    checks_dir.clear()
    helper.check_websites(urls, "test", today=date(2026, 12, 1))
    assert checks_dir == []
    helper.check_websites(urls, "test", today=date(2026, 12, 20))
    assert sorted(checks_dir) == urls


def test_addresses_no_longer_used_are_dropped_from_the_cache(checks_dir):
    helper.check_websites(["https://live.example.org/", "https://old.example.org/"], "test", today=date(2026, 11, 15))
    checks = helper.check_websites(["https://live.example.org/"], "test", today=date(2026, 11, 16))
    assert list(checks) == ["https://live.example.org/"]


def test_website_link():
    checks = {"https://lapsed.example.org/": {"dead": "Domain not found", "archive": "https://web.archive.org/x"},
              "https://live.example.org/": {"dead": None, "archive": None}}
    assert helper.website_link("https://lapsed.example.org/", checks) == (None, "https://web.archive.org/x")
    assert helper.website_link("https://live.example.org/", checks) == ("https://live.example.org/", None)
    assert helper.website_link("", checks) == (None, None)
    assert helper.website_link("https://unchecked.example.org/", checks) == ("https://unchecked.example.org/", None)


def test_link_websites_swaps_a_dead_site_for_its_archive(checks_dir):
    items = [{"website": "https://lapsed.example.org/"}, {"website": "https://live.example.org/"}, {"website": None}]
    helper.link_websites(items, "test", today=date(2026, 11, 15))
    assert items == [
        {"website": None, "website_archive": "https://web.archive.org/web/2020/https://lapsed.example.org/"},
        {"website": "https://live.example.org/", "website_archive": None},
        {"website": None, "website_archive": None},
    ]


def test_link_websites_keeps_a_fetchers_own_field_and_empty_value(checks_dir):
    items = [{"url": "https://lapsed.example.org/"}, {"url": ""}]
    helper.link_websites(items, "test", field="url", empty="", today=date(2026, 11, 15))
    assert items == [
        {"url": "", "url_archive": "https://web.archive.org/web/2020/https://lapsed.example.org/"},
        {"url": "", "url_archive": ""},
    ]
