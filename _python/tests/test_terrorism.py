"""Offline tests for the UK threat level fetcher (terrorism.py): reading
MI5's feed, the change log, the Atom feed entries, and the main run against
a temporary folder with the download faked.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy

import pytest
import requests

import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "terrorism.py"
SPEC = importlib.util.spec_from_file_location("terrorism", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
terrorism = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(terrorism)

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>UK Threat Level</title>
<item><title>Current Threat Level: SUBSTANTIAL</title>
<pubDate>Thursday, April 30, 2026 -  06:09</pubDate>
<description>&lt;p&gt;The threat to the UK from terrorism is SUBSTANTIAL.&amp;nbsp;The threat level for
Northern Ireland-related terrorism is substantial in Northern Ireland.&lt;/p&gt;</description></item>
</channel></rss>"""

CURRENT = {
    "title": "Current Threat Level: SUBSTANTIAL",
    "level": "SUBSTANTIAL",
    "level_title": "Substantial",
    "northern_ireland_level": "SUBSTANTIAL",
    "details": "The threat to the UK from terrorism is SUBSTANTIAL. The threat level for Northern "
               "Ireland-related terrorism is substantial in Northern Ireland.",
    "published_iso": "2026-04-30T06:09:00+01:00",
}


def test_parse_feed_reads_the_current_level():
    assert terrorism.parse_feed(FEED) == CURRENT


def test_parse_feed_without_an_item_is_an_error():
    with pytest.raises(RuntimeError, match="No entries"):
        terrorism.parse_feed("<rss><channel></channel></rss>")


def test_small_helpers():
    assert terrorism.strip_html("<b>A</b>&nbsp; &amp;  B") == "A & B"
    assert terrorism.northern_ireland_level("no mention") == ""
    assert terrorism.parse_published("2022-02-08").isoformat() == "2022-02-08T00:00:00+00:00"


def test_merge_history_adds_a_new_level_and_refreshes_a_known_one():
    old = {"published_iso": "2022-02-08", "level": "SUBSTANTIAL", "level_title": "Substantial", "note": "By hand"}
    records = terrorism.merge_history([old], CURRENT, "2026-05-01T00:00:00Z")
    assert [r["published_iso"] for r in records] == [CURRENT["published_iso"], "2022-02-08"]
    assert records[0]["first_seen_iso"] == "2026-05-01T00:00:00Z" and records[0]["source"] == "mi5"

    records = terrorism.merge_history(records, {**CURRENT, "details": "Updated"}, "2026-05-02T00:00:00Z")
    assert len(records) == 2
    assert records[0]["details"] == "Updated" and records[0]["first_seen_iso"] == "2026-05-01T00:00:00Z"
    assert records[0]["last_seen_iso"] == "2026-05-02T00:00:00Z" and records[1]["note"] == "By hand"


def test_feed_entries_are_dated_by_the_change():
    records = [{**CURRENT, "details": ""}, {"published_iso": "2022-02-08", "level_title": "Substantial"}]
    first, second = terrorism.build_atom_items(records, "https://example.org/security")
    assert first == {"title": "UK threat level: Substantial", "link": "https://example.org/security#2026-04-30",
                     "summary": "The UK national threat level was set to Substantial.",
                     "published_iso": CURRENT["published_iso"], "source": "MI5"}
    assert second["published_iso"] == "2022-02-08T00:00:00+00:00"


class FakeResponse:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_fetch_retries_a_cloudflare_page_and_saves_the_xml(tmp_path, monkeypatch):
    answers = [FakeResponse("<title>Just a moment...</title> cloudflare"), FakeResponse(status=503, text=""),
               FakeResponse(FEED)]
    monkeypatch.setattr(terrorism.requests, "get", lambda url, headers, timeout: answers.pop(0))
    monkeypatch.setattr(terrorism.time, "sleep", lambda s: None)
    saved = tmp_path / "terrorism.xml"
    assert terrorism.fetch_terrorism_xml(saved) == FEED
    assert saved.read_text() == FEED


def test_fetch_gives_up_after_four_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(terrorism.requests, "get", lambda url, headers, timeout: FakeResponse("", status=503))
    monkeypatch.setattr(terrorism.time, "sleep", lambda s: None)
    with pytest.raises(requests.HTTPError):
        terrorism.fetch_terrorism_xml(tmp_path / "terrorism.xml")


@pytest.fixture
def site(tmp_path, monkeypatch):
    (tmp_path / "_data").mkdir()
    (tmp_path / "feeds").mkdir()
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(helper, "site_url", lambda: "https://example.org")
    monkeypatch.setattr(terrorism.time, "sleep", lambda s: None)
    return tmp_path


def run_main():
    runpy.run_path(str(SCRIPT), run_name="__main__")


def test_main_run_writes_the_level_history_and_feed(site, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse(FEED))
    run_main()
    current = json.loads((site / "_data" / "terrorism.json").read_text())
    assert current["level"] == "SUBSTANTIAL" and current["source"] == "MI5"
    history = json.loads((site / "_data" / "terrorism-history.json").read_text())
    assert history["count"] == 1 and history["backfill_source"] == terrorism.BACKFILL_SOURCE
    assert "https://example.org/cheltenham-security-alerts#2026-04-30" in (site / "feeds" / "security.xml").read_text()


def test_a_failed_fetch_keeps_the_existing_level(site, monkeypatch):
    (site / "_data" / "terrorism.json").write_text('{"level": "KEEP"}')
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse("", status=503))
    with pytest.raises(SystemExit) as exit_info:
        run_main()
    assert exit_info.value.code == 0
    assert json.loads((site / "_data" / "terrorism.json").read_text()) == {"level": "KEEP"}


def test_a_failed_first_fetch_falls_back_to_the_saved_xml(site, monkeypatch):
    (site / "_data" / "terrorism.xml").write_text(FEED)
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse("", status=503))
    run_main()
    assert json.loads((site / "_data" / "terrorism.json").read_text())["level"] == "SUBSTANTIAL"


def test_a_failed_first_fetch_with_nothing_saved_is_an_error(site, monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers, timeout: FakeResponse("", status=503))
    with pytest.raises(requests.HTTPError):
        run_main()
