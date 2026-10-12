"""Offline tests for the Land Registry fetcher (land-registry.py): the SPARQL
queries, row conversion, paging and the written payload. The SPARQL endpoint
is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib

import pytest
import requests

import helper

SPEC = importlib.util.spec_from_file_location(
    "land_registry", pathlib.Path(__file__).resolve().parents[1] / "land-registry.py"
)
assert SPEC is not None and SPEC.loader is not None
lr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lr)


def binding(amount="325000", date="2026-08-01", ptype="Detached", new_build="false", **extra):
    row = {"amount": amount, "date": date, "propertyTypeLabel": ptype, "newBuild": new_build,
           "paon": "12", "street": "HIGH STREET", "town": "CHELTENHAM", "postcode": "GL50 1AA", **extra}
    return {key: {"value": value} for key, value in row.items() if value is not None}


def test_queries_filter_on_cheltenham_districts_and_a_date_threshold():
    count_query = lr.build_count_query(12)
    query = lr.build_query(12, limit=50, offset=100)
    for district in lr.CHELTENHAM_POSTCODE_DISTRICTS:
        assert f'STRSTARTS(?postcode, "{district}")' in query
    assert "COUNT(*)" in count_query and 'FILTER (?town = "CHELTENHAM")' in count_query
    assert "LIMIT 50" in query and "OFFSET 100" in query
    _, threshold = lr._common_where(12)
    assert f'?date >= "{threshold}"' in query


def test_rows_become_transactions_with_display_amounts_and_types():
    rows = [binding(amount="325000.0", new_build="true"),
            binding(ptype=" other ", saon="Flat 2"),
            binding(amount=None, ptype=None)]
    first, second, third = lr._rows_to_transactions(rows)
    assert first == {"paon": "12", "saon": None, "street": "HIGH STREET", "town": "CHELTENHAM",
                     "postcode": "GL50 1AA", "amount": 325000, "display_amount": "£325,000",
                     "date": "2026-08-01", "property_type": "Detached", "new_build": True}
    assert second["property_type"] == "Other" and second["saon"] == "Flat 2"
    assert third["amount"] is None and third["display_amount"] == "" and third["property_type"] == "Other"


def test_get_true_count_reads_the_count_binding(monkeypatch):
    monkeypatch.setattr(lr, "_run_query", lambda q: {"results": {"bindings": [{"n": {"value": "42"}}]}})
    assert lr.get_true_count(48) == 42
    monkeypatch.setattr(lr, "_run_query", lambda q: {})
    assert lr.get_true_count(48) == 0


def test_fetch_transactions_pages_until_a_short_page(monkeypatch, capsys):
    monkeypatch.setattr(lr, "PAGE_SIZE", 2)
    pages = [[binding(), binding()], [binding()]]
    offsets = []

    def fake_query(query):
        offsets.append(int(query.split("OFFSET")[1]))
        return {"results": {"bindings": pages.pop(0)}}

    monkeypatch.setattr(lr, "_run_query", fake_query)
    assert len(lr.fetch_transactions(12, expected_count=4)) == 3
    assert offsets == [0, 2]
    assert "COUNT query reported 4" in capsys.readouterr().err


def test_fetch_transactions_warns_about_an_empty_result(monkeypatch, capsys):
    monkeypatch.setattr(lr, "_run_query", lambda q: {"results": {"bindings": []}})
    assert lr.fetch_transactions(12) == []
    assert "zero rows" in capsys.readouterr().err


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code, self._body = status, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


def test_run_query_asks_for_json_and_raises_http_errors(monkeypatch):
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen.update(url=url, params=params)
        return FakeResponse(body={"ok": True})

    monkeypatch.setattr(helper, "get", fake_get)
    assert lr._run_query("SELECT 1") == {"ok": True}
    assert seen == {"url": lr.ENDPOINT, "params": {"query": "SELECT 1", "output": "json"}}

    monkeypatch.setattr(helper, "get", lambda *a, **k: FakeResponse(status=403))
    with pytest.raises(requests.HTTPError):
        lr._run_query("SELECT 1")


def test_write_json_writes_the_payload_unless_dry_run(tmp_path, monkeypatch):
    out = tmp_path / "_data" / "prices.json"
    monkeypatch.setattr(lr, "JSON_DATA_PATH", out)
    lr.write_json([{"amount": 1}], 48, dry_run=True)
    assert not out.exists()
    lr.write_json([{"amount": 1}], 48, dry_run=False)
    payload = json.loads(out.read_text())
    assert payload["months_fetched"] == 48 and payload["transactions"] == [{"amount": 1}]
    assert payload["source"] == "HM Land Registry Price Paid Data"


def test_main_counts_fetches_and_writes(monkeypatch):
    monkeypatch.setattr(lr, "get_true_count", lambda months: 1)
    monkeypatch.setattr(lr, "fetch_transactions", lambda months, expected_count: [{"amount": 1}])
    written = []
    monkeypatch.setattr(lr, "write_json", lambda txns, months, dry_run: written.append((txns, months, dry_run)))
    lr.main()
    assert written == [([{"amount": 1}], lr.MONTHS, lr.DRY_RUN)]
