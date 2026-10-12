"""Offline tests for the site traffic fetcher (site-traffic.py): filling in
the 30 days and the Cloudflare reply, with the GraphQL request faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
from datetime import date, datetime, timedelta, timezone

import pytest

import helper

SPEC = importlib.util.spec_from_file_location(
    "site_traffic", pathlib.Path(__file__).resolve().parents[1] / "site-traffic.py"
)
assert SPEC is not None and SPEC.loader is not None
traffic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(traffic)


def group(day, requests=100, sent=1000, cached=250, uniques=40):
    return {"dimensions": {"date": day}, "sum": {"requests": requests, "bytes": sent, "cachedBytes": cached},
            "uniq": {"uniques": uniques}}


def test_percent_rounds_and_copes_with_nothing_sent():
    assert traffic.percent(1, 3) == 33.3
    assert traffic.percent(5, 0) == 0.0


def test_build_days_fills_every_date_and_zeroes_missing_ones():
    days = traffic.build_days([group("2026-10-01"), group("2026-10-03", requests=7, sent=0, cached=0, uniques=2)],
                              date(2026, 10, 1), date(2026, 10, 3))
    assert days == [
        {"date": "2026-10-01", "requests": 100, "cached_percent": 25.0, "uniques": 40},
        {"date": "2026-10-02", "requests": 0, "cached_percent": 0.0, "uniques": 0},
        {"date": "2026-10-03", "requests": 7, "cached_percent": 0.0, "uniques": 2},
    ]


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone-1")


def reply(days, period=None):
    period = period or {"sum": {"requests": 3000, "bytes": 40000, "cachedBytes": 10000}, "uniq": {"uniques": 1234}}
    return {"data": {"viewer": {"zones": [{"days": days, "period": [period]}]}}}


def test_main_asks_for_the_last_30_complete_days_and_writes_totals(keys, monkeypatch):
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    sent = {}
    monkeypatch.setattr(helper, "post", lambda url, headers, json, timeout: sent.update(headers=headers, json=json)
                        or FakeResponse(reply([group(yesterday.isoformat())])))
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    traffic.main()

    variables = sent["json"]["variables"]
    assert variables == {"zone": "zone-1", "start": (yesterday - timedelta(days=29)).isoformat(),
                         "end": yesterday.isoformat()}
    assert sent["headers"]["Authorization"] == "Bearer test-token"
    payload = written["payload"]
    assert written["path"] == traffic.OUT
    assert payload["totals"] == {"uniques": 1234, "display_uniques": "1,234", "requests": 3000,
                                 "display_requests": "3,000", "cached_percent": 25.0}
    assert len(payload["days"]) == 30 and payload["days"][-1]["requests"] == 100


def test_main_needs_both_keys(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.setenv("CLOUDFLARE_ZONE_ID", "zone-1")
    with pytest.raises(SystemExit, match="CLOUDFLARE_API_TOKEN"):
        traffic.main()


@pytest.mark.parametrize("body, message", [
    ({"errors": [{"message": "not authorised"}]}, "not authorised"),
    ({"data": {"viewer": {"zones": []}}}, "no zone"),
])
def test_main_stops_on_a_cloudflare_error(keys, monkeypatch, body, message):
    monkeypatch.setattr(helper, "post", lambda url, headers, json, timeout: FakeResponse(body))
    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(payload))
    with pytest.raises(SystemExit, match=message):
        traffic.main()
    assert written == []
