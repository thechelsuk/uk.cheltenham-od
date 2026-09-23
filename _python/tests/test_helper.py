"""Offline tests for the shared fetcher settings and helpers. Nothing here
touches the network: requests.request is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json

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


# --- writing ------------------------------------------------------------------

def test_write_json_creates_the_folder_and_keeps_unicode(tmp_path):
    out = tmp_path / "new" / "data.json"
    helper.write_json(out, {"name": "Café"})
    assert json.loads(out.read_text()) == {"name": "Café"}
    assert "Café" in out.read_text()


# --- every script can reach helper and config ------------------------------

import ast
import pathlib
import subprocess
import sys

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
