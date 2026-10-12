"""Offline tests for the Pi's fuel prices fetcher (pi/fuel.py). The Fuel
Finder API is replaced with a fake, and the main run is pointed at a
temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import datetime
import importlib.util
import json
import pathlib
import runpy
import sys

import pytest
import requests

import helper


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, pathlib.Path(__file__).resolve().parents[1] / relative)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fuel = _load("fuel", "pi/fuel.py")


def test_fuel_codes_get_readable_labels():
    assert fuel.fuel_label("E10") == "Unleaded"
    assert fuel.fuel_label("B7_STANDARD") == "Diesel"
    assert fuel.fuel_label("NEW_CODE") == "NEW_CODE"


def test_brand_acronyms_stay_upper_case():
    assert fuel.clean_name("ASDA EXPRESS BP CHELTENHAM") == "ASDA Express BP Cheltenham"


def test_a_forecourt_in_range_becomes_a_station():
    station = fuel.station_from_pfs_record({
        "trading_name": "Test Garage",
        "location": {"latitude": 51.90, "longitude": -2.08, "address_line_1": "1 High Street", "postcode": "GL50 1AA"},
    })
    assert station["trading_name"] == "Test Garage"
    assert station["address"] == "1 High Street, GL50 1AA"
    assert station["distance_miles"] < 1


def test_the_postcode_isnt_repeated_when_the_address_already_ends_with_it():
    station = fuel.station_from_pfs_record({
        "location": {"latitude": 51.90, "longitude": -2.08, "address_line_1": "1 High Street, GL50 1AA", "postcode": "GL50 1AA"},
    })
    assert station["address"] == "1 High Street, GL50 1AA"


def test_a_forecourt_out_of_range_or_without_a_location_is_skipped():
    assert fuel.station_from_pfs_record({"location": {"latitude": 53.48, "longitude": -2.24}}) is None
    assert fuel.station_from_pfs_record({"location": {}}) is None


SCRIPT = str(pathlib.Path(__file__).resolve().parents[1] / "pi" / "fuel.py")
TODAY = datetime.date.today()


def day(offset):
    return (TODAY - datetime.timedelta(days=offset)).isoformat()


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


def fake_api(pfs_pages=(), price_pages=()):
    """requests.get for the Fuel Finder API: each list holds one answer per
    batch (a list of records, or a status code); past the end is a 404."""
    calls = []

    def get(url, headers, params, timeout):
        calls.append((url, params))
        pages = pfs_pages if url.endswith(fuel.PFS_PATH) else price_pages
        index = params["batch-number"] - 1
        if index >= len(pages):
            return FakeResponse(404)
        page = pages[index]
        if isinstance(page, Exception):
            raise page
        return FakeResponse(page) if isinstance(page, int) else FakeResponse(body=page)
    return get, calls


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(fuel.time, "sleep", lambda s: None)


def test_haversine_miles():
    assert fuel.haversine_miles(51.899, -2.078, 51.899, -2.078) == 0
    assert fuel.haversine_miles(51.899, -2.078, 51.454, -2.588) == pytest.approx(37.7, abs=0.1)  # Bristol


def test_authenticate_reads_the_token_with_or_without_a_data_wrapper(monkeypatch):
    sent = []

    def fake_request(method, url, **kwargs):
        sent.append((method, url, kwargs["json"]))
        return FakeResponse(body=answers.pop(0))

    answers = [{"data": {"access_token": "abc"}}, {"access_token": "def"}]
    monkeypatch.setattr(helper, "request_with_retry", fake_request)
    assert fuel.authenticate("id", "secret") == "abc"
    assert fuel.authenticate("id", "secret") == "def"
    assert sent[0] == ("POST", fuel.BASE_URL + fuel.AUTH_PATH, {"client_id": "id", "client_secret": "secret"})


def test_fetch_all_pages_reads_full_batches_until_a_short_one(monkeypatch, no_sleep):
    get, calls = fake_api(pfs_pages=[[{"n": i} for i in range(500)], [{"n": "last"}], [{"n": "unread"}]])
    monkeypatch.setattr(fuel.requests, "get", get)
    results = fuel.fetch_all_pages(fuel.PFS_PATH, "tok", extra_params={"x": 1})
    assert len(results) == 501
    assert [c[1]["batch-number"] for c in calls] == [1, 2]
    assert calls[0][1] == {"batch-number": 1, "x": 1}


def test_fetch_all_pages_retries_a_504_then_stops_at_a_404(monkeypatch, no_sleep):
    answers = [FakeResponse(504), FakeResponse(body=[{"n": i} for i in range(500)]), FakeResponse(404)]
    monkeypatch.setattr(fuel.requests, "get", lambda url, headers, params, timeout: answers.pop(0))
    assert len(fuel.fetch_all_pages(fuel.PFS_PATH, "tok")) == 500


def test_fetch_all_pages_gives_up_after_four_timeouts(monkeypatch, no_sleep):
    def timeout(url, headers, params, timeout):
        raise requests.exceptions.ReadTimeout("slow")

    monkeypatch.setattr(fuel.requests, "get", timeout)
    with pytest.raises(requests.exceptions.ReadTimeout):
        fuel.fetch_all_pages(fuel.PFS_PATH, "tok")
    monkeypatch.setattr(fuel.requests, "get", lambda url, headers, params, timeout: FakeResponse(504))
    with pytest.raises(requests.HTTPError):
        fuel.fetch_all_pages(fuel.PFS_PATH, "tok")


def test_fetch_all_pages_stops_on_an_empty_page(monkeypatch, no_sleep):
    get, _ = fake_api(pfs_pages=[[]])
    monkeypatch.setattr(fuel.requests, "get", get)
    assert fuel.fetch_all_pages(fuel.PFS_PATH, "tok") == []


def test_fetch_local_prices_keeps_local_records_and_stops_once_all_are_found(monkeypatch, no_sleep):
    first = [{"node_id": f"far{i}"} for i in range(499)] + [{"node_id": "A"}]
    second = [{"node_id": f"far{i}"} for i in range(499)] + [{"node_id": "B"}]
    get, calls = fake_api(price_pages=[first, second, [{"node_id": "never"}]])
    monkeypatch.setattr(fuel.requests, "get", get)
    results = fuel.fetch_local_prices({"A", "B"}, "tok", "2026-09-17")
    assert [r["node_id"] for r in results] == ["A", "B"]
    assert len(calls) == 2
    assert calls[0][1] == {"batch-number": 1, "effective-start-timestamp": "2026-09-17"}
    assert fuel.fetch_local_prices(set(), "tok", "2026-09-17") == []


def test_fetch_local_prices_retries_and_stops_at_the_end_of_the_feed(monkeypatch, no_sleep):
    answers = [requests.exceptions.ReadTimeout("slow"), FakeResponse(504), FakeResponse(body=[])]

    def get(url, headers, params, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(fuel.requests, "get", get)
    assert fuel.fetch_local_prices({"A"}, "tok", "2026-09-17") == []
    get404, _ = fake_api(price_pages=[])
    monkeypatch.setattr(fuel.requests, "get", get404)
    assert fuel.fetch_local_prices({"A"}, "tok", "2026-09-17") == []


def test_station_cache_and_ignore_list_round_trip(tmp_path):
    cache_path, ignore_path = tmp_path / "cache.json", tmp_path / "ignore.json"
    assert fuel.load_station_cache(cache_path) == {} and fuel.load_ignore_set(ignore_path) == set()
    fuel.save_station_cache(cache_path, {"A": {"x": 1}, "B": None})
    assert fuel.load_station_cache(cache_path) == {"A": {"x": 1}}
    fuel.save_ignore_set(ignore_path, {"Z", "Y"})
    assert json.loads(ignore_path.read_text()) == ["Y", "Z"]
    assert fuel.load_ignore_set(ignore_path) == {"Y", "Z"}


def test_a_station_without_a_postcode_keeps_its_address_as_is():
    station = fuel.station_from_pfs_record({"is_supermarket_service_station": 1, "brand_name": "BP",
                                            "location": {"lat": "51.9", "lng": "-2.08", "address_line_1": "Bath Road"}})
    assert station["address"] == "Bath Road" and station["is_supermarket"] is True
    assert station["trading_name"] == "Unknown" and station["brand_name"] == "BP"


# -- The main run -----------------------------------------------------------------


def cached(name, postcode, distance, brand="", prices=None, updated=None):
    station = {"trading_name": name, "brand_name": brand, "distance_miles": distance, "is_supermarket": False,
               "address": "1 Road", "postcode": postcode, "lat": 51.9, "lon": -2.08}
    if prices:
        station.update(fuel_prices=prices, prices_updated=updated)
    return station


def price(fuel_type, value, changed):
    return {"fuel_type": fuel_type, "price": value, "price_change_effective_timestamp": f"{changed}T08:00:00Z"}


# -- Building the page data ---------------------------------------------------------


def test_station_as_of_is_the_latest_price_change_or_the_fetch_date():
    station = {"fuel_prices": [price("E10", 1, "2026-10-01"), price("E5", 1, "2026-10-05"), {"fuel_type": "B7"}],
               "prices_updated": "2026-10-09"}
    assert fuel.station_as_of(station) == "2026-10-05"
    assert fuel.station_as_of({"fuel_prices": [{"fuel_type": "E10"}], "prices_updated": "2026-10-09"}) == "2026-10-09"
    assert fuel.station_as_of({}) == ""


def test_dedupe_keeps_the_freshest_of_the_same_forecourt():
    priced = {
        "old": {"trading_name": "Tesco ", "postcode": "GL50 1AA", "fuel_prices": [price("E10", 1, "2026-10-01")]},
        "new": {"trading_name": "TESCO", "postcode": "gl501aa", "fuel_prices": [price("E10", 1, "2026-10-05")]},
        "other": {"trading_name": "Tesco", "postcode": "GL52 2BB", "fuel_prices": [price("E10", 1, "2026-10-01")]},
    }
    assert fuel.dedupe_stations(priced) == {"new", "other"}


def test_fuel_columns_put_the_usual_fuels_first():
    cache = {"A": {"fuel_prices": [{"fuel_type": "HVO"}, {"fuel_type": "B7_STANDARD"}, {"fuel_type": "E10"}, {}]}}
    assert fuel.fuel_columns(cache, {"A"}) == ["E10", "B7_STANDARD", "HVO"]


def test_median():
    assert fuel.median([3, 1, 2]) == 2
    assert fuel.median([4, 1, 3, 2]) == 2.5
    assert fuel.median([]) is None


def test_merge_prices_takes_newer_records_and_leaves_newer_cached_prices():
    cache = {"A": {"fuel_prices": [price("E10", 130, "2026-10-01")], "prices_updated": "2026-10-05"}}
    older = [{"node_id": "A", "effective_start_timestamp": "2026-10-03T09:00:00Z", "fuel_prices": [price("E10", 1, "2026-10-03")]}]
    assert fuel.merge_prices(cache, older, "2026-09-17") == 0
    newer = [{"node_id": "A", "effective_start_timestamp": "2026-10-12T09:00:00Z", "fuel_prices": [price("E10", 125, "2026-10-12")]},
             {"node_id": "A", "effective_start_timestamp": "2026-10-12T10:00:00Z", "fuel_prices": []},
             {"node_id": "FAR", "fuel_prices": [price("E10", 99, "2026-10-12")]}]
    assert fuel.merge_prices(cache, newer, "2026-09-17") == 1
    assert cache["A"]["prices_updated"] == "2026-10-12" and cache["A"]["fuel_prices"][0]["price"] == 125
    assert "FAR" not in cache


def test_an_undated_record_only_fills_a_station_with_no_prices():
    undated = [{"node_id": "A", "fuel_prices": [price("E10", 125, "2026-10-12")]}]
    priced = {"A": {"fuel_prices": [price("E10", 130, "2026-10-01")], "prices_updated": "2026-10-01"}}
    assert fuel.merge_prices(priced, undated, "2026-09-17") == 0
    assert priced["A"]["prices_updated"] == "2026-10-01"
    empty = {"A": {"trading_name": "New Garage"}}
    assert fuel.merge_prices(empty, undated, "2026-09-17") == 1
    assert empty["A"]["prices_updated"] == "2026-09-17"


def test_headline_entry_names_a_brand_only_when_it_differs_and_shows_any_saving():
    station = {"trading_name": "TESCO CHELTENHAM", "brand_name": "TESCO"}
    entry = fuel.headline_entry("E10", station, 130.9, 133.4)
    assert entry["name"] == "Tesco Cheltenham" and entry["brand"] == "Tesco" and entry["pct_cheaper"] == "1.9"
    same = fuel.headline_entry("E5", {"trading_name": "Shell", "brand_name": "SHELL"}, 150.9, 150.9)
    assert same == {"label": "Prem Unleaded", "price": "150.9", "name": "Shell", "brand": ""}


@pytest.fixture
def site(tmp_path, monkeypatch, no_sleep):
    """A temporary repo root with _data/, the API keys set and auth faked."""
    (tmp_path / "_data").mkdir()
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setenv("FUEL_KEY", "id")
    monkeypatch.setenv("FUEL_TOKEN", "secret")
    monkeypatch.setattr(sys, "argv", ["fuel.py"])
    monkeypatch.setattr(helper, "request_with_retry",
                        lambda *a, **k: FakeResponse(body={"access_token": "tok"}))
    return tmp_path / "_data"


def test_main_run_needs_the_api_keys(monkeypatch):
    monkeypatch.delenv("FUEL_KEY", raising=False)
    with pytest.raises(SystemExit):
        runpy.run_path(SCRIPT, run_name="__main__")


def test_main_run_prices_dedupes_and_finds_the_cheapest(site, monkeypatch):
    (site / "fuel-stations.json").write_text(json.dumps({
        "A": cached("TESCO CHELTENHAM", "GL50 1AA", 0.5, brand="TESCO"),
        "B": cached("SHELL BATH ROAD", "GL53 7AA", 1.2, brand="Shell"),
        "C": cached("Tesco Cheltenham", "GL501AA", 0.6, prices=[price("E10", 120.9, day(15))], updated=day(15)),
        "D": cached("No Prices Garage", "GL51 1AA", 2.0),
    }))
    prices = [
        {"node_id": "A", "effective_start_timestamp": f"{day(0)}T09:00:00Z",
         "fuel_prices": [price("E10", 130.9, day(0)), price("B7_STANDARD", 140.9, day(0))]},
        {"node_id": "B", "effective_start_timestamp": f"{day(0)}T09:00:00Z",
         "fuel_prices": [price("E10", 135.9, day(20)), price("E5", 150.9, day(20)), price("B7_STANDARD", 139.9, day(20))]},
        {"node_id": "FAR", "fuel_prices": [price("E10", 99.9, day(0))]},
    ]
    get, _ = fake_api(price_pages=[prices])
    monkeypatch.setattr(requests, "get", get)

    runpy.run_path(SCRIPT, run_name="__main__")

    data = json.loads((site / "fuel-prices.json").read_text())
    assert data["columns"] == ["Unleaded", "Prem Unleaded", "Diesel"]
    assert data["context"] == [{"label": "Unleaded", "cheapest": 130.9, "typical": 133.4},
                               {"label": "Prem Unleaded", "cheapest": 150.9, "typical": 150.9},
                               {"label": "Diesel", "cheapest": 139.9, "typical": 140.4}]
    unleaded, premium, diesel = data["headline"]
    assert unleaded == {"label": "Unleaded", "price": "130.9", "name": "Tesco Cheltenham", "brand": "Tesco",
                        "pct_cheaper": "1.9", "tank_litres": 55,
                        "tank_saving": f"{(133.4 - 130.9) * 55 / 100:.2f}"}
    assert "pct_cheaper" not in premium
    assert diesel["name"] == "Shell Bath Road" and diesel["brand"] == "Shell"

    tesco, shell = data["stations"]          # C is a duplicate of A, D has no prices
    assert (tesco["name"], tesco["as_of"], tesco["stale"]) == ("Tesco Cheltenham", day(0), False)
    assert tesco["cells"] == [{"display": "130.9p", "val": "130.9", "cheapest": True},
                              {"display": "–", "val": "9999", "cheapest": False},
                              {"display": "140.9p", "val": "140.9", "cheapest": False}]
    assert tesco["popup"] == "Tesco Cheltenham — from 130.9p"
    assert (shell["as_of"], shell["stale"]) == (day(20), True)

    cache = json.loads((site / "fuel-stations.json").read_text())
    assert cache["A"]["prices_updated"] == day(0) and "FAR" not in cache
    history = json.loads((site / "fuel-prices-history.json").read_text())
    assert [r["date"] for r in history["records"]] == [day(0)]


def test_main_run_keeps_newer_cached_prices_over_an_older_record(site, monkeypatch):
    newer = [price("E10", 131.9, day(1))]
    (site / "fuel-stations.json").write_text(json.dumps({
        "A": cached("Garage", "GL50 1AA", 0.5, prices=newer, updated=day(1))}))
    old_record = {"node_id": "A", "effective_start_timestamp": f"{day(5)}T09:00:00Z",
                  "fuel_prices": [price("E10", 125.9, day(5))]}
    get, _ = fake_api(price_pages=[[old_record]])
    monkeypatch.setattr(requests, "get", get)
    runpy.run_path(SCRIPT, run_name="__main__")
    station = json.loads((site / "fuel-prices.json").read_text())["stations"][0]
    assert station["cells"][0]["val"] == "131.9"


def test_bootstrap_rebuilds_the_station_list_and_seeds_prices(site, monkeypatch):
    (site / "fuel-stations.json").write_text(json.dumps({
        "MOVED": cached("Moved Away", "GL50 9ZZ", 0.1),
        "NEAR": cached("Old Name", "GL50 1AA", 0.1, prices=[price("E10", 128.9, day(3))], updated=day(3)),
    }))
    (site / "ignore-stations.json").write_text(json.dumps(["STALE-IGNORE"]))
    monkeypatch.setattr(sys, "argv", ["fuel.py", "--bootstrap"])
    near = {"latitude": 51.90, "longitude": -2.08, "address_line_1": "1 High Street", "postcode": "GL50 1AA"}
    far = {"latitude": 53.48, "longitude": -2.24}
    pfs = [{"node_id": "NEAR", "trading_name": "New Name", "location": near},
           {"node_id": "MOVED", "trading_name": "Moved Away", "location": far},
           {"node_id": "FAR", "trading_name": "Manchester", "location": far}]
    get, _ = fake_api(pfs_pages=[pfs], price_pages=[[]])
    monkeypatch.setattr(requests, "get", get)

    runpy.run_path(SCRIPT, run_name="__main__")

    cache = json.loads((site / "fuel-stations.json").read_text())
    assert list(cache) == ["NEAR"]
    assert cache["NEAR"]["trading_name"] == "New Name" and cache["NEAR"]["prices_updated"] == day(3)
    assert json.loads((site / "ignore-stations.json").read_text()) == ["FAR", "MOVED"]
    assert [s["name"] for s in json.loads((site / "fuel-prices.json").read_text())["stations"]] == ["New Name"]


def test_a_failed_bootstrap_keeps_the_stations_it_had_and_carries_on(site, monkeypatch):
    (site / "fuel-stations.json").write_text(json.dumps({
        "NEAR": cached("Garage", "GL50 1AA", 0.1, prices=[price("E10", 128.9, day(3))], updated=day(3))}))
    (site / "ignore-stations.json").write_text(json.dumps(["OLD-IGNORE"]))
    monkeypatch.setattr(sys, "argv", ["fuel.py", "--bootstrap"])
    get, _ = fake_api(pfs_pages=[500], price_pages=[500])
    monkeypatch.setattr(requests, "get", get)

    with pytest.raises(requests.HTTPError):
        runpy.run_path(SCRIPT, run_name="__main__")      # the daily price fetch still fails

    assert list(json.loads((site / "fuel-stations.json").read_text())) == ["NEAR"]
    assert json.loads((site / "ignore-stations.json").read_text()) == []
