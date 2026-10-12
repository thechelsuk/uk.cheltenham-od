"""Offline tests for the daily news round-up (news-digest.py): one digest a
day from the news archive, and the feed built from them. The main run reads
and writes a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import runpy
from datetime import date

import pytest

import helper

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "news-digest.py"
SPEC = importlib.util.spec_from_file_location("news_digest", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
digest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(digest)


def test_load_digests_copes_with_a_missing_or_broken_file(tmp_path):
    path = tmp_path / "news-digests.json"
    assert digest.load_digests(path) == []
    path.write_text("{broken")
    assert digest.load_digests(path) == []
    path.write_text(json.dumps({"digests": [{"date": "2026-10-11"}]}))
    assert digest.load_digests(path) == [{"date": "2026-10-11"}]


@pytest.fixture
def site(tmp_path, monkeypatch):
    for folder in ("_data", "feeds"):
        (tmp_path / folder).mkdir()
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    items = [{"title": f"Story {i}", "link": f"/news/{i}", "source": "Echo", "summary": "x"} for i in range(12)]
    (tmp_path / "_data" / "news-archive.json").write_text(json.dumps({"items": items}))
    return tmp_path


def run_main():
    runpy.run_path(str(SCRIPT), run_name="__main__")


def test_main_adds_todays_digest_of_the_top_ten_newest_first(site):
    (site / "_data" / "news-digests.json").write_text(json.dumps({"digests": [
        {"date": "2026-10-01", "created_iso": "2026-10-01T07:00:00", "items": []}]}))

    run_main()

    digests = json.loads((site / "_data" / "news-digests.json").read_text())["digests"]
    today = date.today().isoformat()
    assert [d["date"] for d in digests] == [today, "2026-10-01"]
    assert len(digests[0]["items"]) == digest.DIGEST_SIZE
    assert digests[0]["items"][0] == {"title": "Story 0", "link": "/news/0", "source": "Echo"}
    feed = (site / "feeds" / "news-summary.xml").read_text()
    assert "Story 0" in feed


def test_main_leaves_todays_digest_alone_on_a_second_run(site):
    run_main()
    first = (site / "_data" / "news-digests.json").read_text()
    archive = json.loads((site / "_data" / "news-archive.json").read_text())
    archive["items"].insert(0, {"title": "Late story", "link": "/news/late", "source": "Echo"})
    (site / "_data" / "news-archive.json").write_text(json.dumps(archive))

    run_main()

    assert (site / "_data" / "news-digests.json").read_text() == first


def test_main_needs_the_archive(site):
    (site / "_data" / "news-archive.json").unlink()
    with pytest.raises(SystemExit, match="run news.py first"):
        run_main()
