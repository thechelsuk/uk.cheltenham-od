"""Offline tests for the social poster (social.py): composing posts, the
live feed, Bluesky link and hashtag facets, and the main run's state file.
Nothing is ever sent: every request is faked, and the main-run tests replace
the posting functions themselves.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import hashlib
import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import feedparser
import pytest
import requests

SPEC = importlib.util.spec_from_file_location(
    "social", pathlib.Path(__file__).resolve().parents[1] / "social.py"
)
assert SPEC is not None and SPEC.loader is not None
social = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(social)

TAGS = ["#Cheltenham", "#OpenData"]
LINK = "https://cheltenham-od.uk/news/bin-collections.html"


class FakeResponse:
    def __init__(self, body=None, status=200, text="", content=b"", headers=None):
        self._body, self.status_code, self.text = body, status, text
        self.content, self.headers = content, headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def never_post(monkeypatch):
    """Belt and braces: no test may reach a real network through requests."""
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to make a real request")
    for name in ("get", "post", "head"):
        monkeypatch.setattr(social.requests, name, refuse)


# -- Composing ------------------------------------------------------------------

def test_clean_strips_tags_and_whitespace():
    assert social.clean("<p>Bin  days\nchange</p>") == "Bin days change"
    assert social.clean(None) == ""


def test_compose_puts_title_description_link_and_tags_on_separate_lines():
    text = social.compose("Bin days change", "New rounds from Monday.", LINK, TAGS, 300)
    assert text == f"Bin days change\n\nNew rounds from Monday.\n\n{LINK}\n\n#Cheltenham #OpenData"


def test_compose_cuts_a_long_description_at_a_word_to_fit():
    description = "word " * 100
    text = social.compose("Title", description, LINK, TAGS, 300)
    assert len(text) <= 300
    assert "word…" in text and "word …" not in text


def test_compose_keeps_descriptions_brief_even_with_room():
    text = social.compose("Title", "x " * 400, LINK, TAGS, 500)
    middle = text.split("\n\n")[1]
    assert len(middle) <= social.DESCRIPTION_MAX


def test_compose_drops_the_description_when_there_is_no_room_or_none():
    assert social.compose("T" * 250, "Some description", LINK, TAGS, 300) == f"{'T' * 250}\n\n{LINK}\n\n#Cheltenham #OpenData"
    assert social.compose("Title", "", LINK, TAGS, 300) == f"Title\n\n{LINK}\n\n#Cheltenham #OpenData"


def test_hashtags_come_from_the_data_file(tmp_path, monkeypatch):
    (tmp_path / "_data").mkdir()
    (tmp_path / "_data" / "social.yml").write_text("hashtags:\n  - '#Cheltenham'\n")
    monkeypatch.setattr(social, "ROOT", tmp_path)
    assert social.hashtags() == ["#Cheltenham"]


# -- State, feed and live check -------------------------------------------------------

@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "social-posted.json"
    monkeypatch.setattr(social, "STATE", path)
    return path


def test_state_starts_empty_and_round_trips(state_file):
    assert social.load_state() == {"posted": {}}
    social.save_state({"posted": {LINK: {"bluesky": "at://x"}}})
    assert json.loads(state_file.read_text()) == {"posted": {LINK: {"bluesky": "at://x"}}}
    assert social.load_state()["posted"][LINK] == {"bluesky": "at://x"}


def entry(link, hours_ago, title="<b>Title</b>", summary="<p>Summary</p>"):
    published = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).timetuple()
    return feedparser.FeedParserDict(title=title, summary=summary, link=link, published_parsed=published)


def test_recent_entries_are_oldest_first_and_cleaned(monkeypatch):
    feed = feedparser.FeedParserDict(bozo=False, entries=[entry("/new", 1), entry("/old", 100)])
    monkeypatch.setattr(social.feedparser, "parse", lambda url, agent: feed)
    entries, cutoff = social.recent_entries()
    assert [e["link"] for e in entries] == ["/old", "/new"]
    assert entries[0]["title"] == "Title" and entries[0]["description"] == "Summary"
    assert datetime.now(timezone.utc) - cutoff == pytest.approx(social.MAX_AGE, abs=timedelta(seconds=5))


def test_an_unreadable_feed_stops_the_run(monkeypatch):
    monkeypatch.setattr(social.feedparser, "parse", lambda url, agent: feedparser.FeedParserDict(bozo=True, entries=[]))
    with pytest.raises(SystemExit, match="Could not read"):
        social.recent_entries()


def test_page_is_live_only_on_a_200(monkeypatch):
    monkeypatch.setattr(social.requests, "head", lambda url, headers, allow_redirects, timeout: FakeResponse(status=200))
    assert social.page_is_live(LINK)
    monkeypatch.setattr(social.requests, "head", lambda url, headers, allow_redirects, timeout: FakeResponse(status=404))
    assert not social.page_is_live(LINK)

    def down(*args, **kwargs):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(social.requests, "head", down)
    assert not social.page_is_live(LINK)


# -- Bluesky --------------------------------------------------------------------

def test_facets_use_byte_offsets_for_the_link_and_each_hashtag():
    text = f"Café news\n\n{LINK}\n\n#Cheltenham #OpenData"
    link_facet, cheltenham, open_data = social.bluesky_facets(text, LINK)
    encoded = text.encode("utf-8")
    start, end = link_facet["index"]["byteStart"], link_facet["index"]["byteEnd"]
    assert encoded[start:end].decode() == LINK
    assert link_facet["features"][0] == {"$type": "app.bsky.richtext.facet#link", "uri": LINK}
    start, end = open_data["index"]["byteStart"], open_data["index"]["byteEnd"]
    assert encoded[start:end].decode() == "#OpenData"
    assert cheltenham["features"][0] == {"$type": "app.bsky.richtext.facet#tag", "tag": "Cheltenham"}


def test_thumbnail_uploads_the_pages_social_image(monkeypatch):
    page = '<meta property="og:image" content="https://cheltenham-od.uk/og.png">'
    got = []
    monkeypatch.setattr(social.requests, "get", lambda url, headers, timeout: got.append(url) or (
        FakeResponse(text=page) if url == LINK else FakeResponse(content=b"png", headers={"Content-Type": "image/png"})))
    uploads = []
    monkeypatch.setattr(social.requests, "post", lambda url, data, timeout, headers: uploads.append((url, data, headers))
                        or FakeResponse({"blob": {"ref": "b1"}}))
    assert social.bluesky_thumbnail(LINK, "jwt") == {"ref": "b1"}
    assert got == [LINK, "https://cheltenham-od.uk/og.png"]
    assert uploads[0][1] == b"png" and uploads[0][2]["Authorization"] == "Bearer jwt"


def test_thumbnail_is_optional(monkeypatch):
    monkeypatch.setattr(social.requests, "get", lambda url, headers, timeout: FakeResponse(text="<p>no image</p>"))
    assert social.bluesky_thumbnail(LINK, "jwt") is None

    def down(*args, **kwargs):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(social.requests, "get", down)
    assert social.bluesky_thumbnail(LINK, "jwt") is None


def test_post_bluesky_signs_in_then_creates_a_post_with_a_link_card(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", "cheltenham-od.uk")
    monkeypatch.setenv("BLUESKY_APP_TOKEN", "app-password")
    monkeypatch.setattr(social, "bluesky_thumbnail", lambda link, token: {"ref": "b1"})
    calls = []

    def fake_post(url, timeout, json, headers=None):
        calls.append((url, json, headers))
        if url.endswith("createSession"):
            return FakeResponse({"accessJwt": "jwt", "did": "did:plc:abc"})
        return FakeResponse({"uri": "at://did:plc:abc/post/1"})

    monkeypatch.setattr(social.requests, "post", fake_post)
    item = {"link": LINK, "title": "Bin days change", "description": "New rounds"}
    text = f"Bin days change\n\n{LINK}\n\n#Cheltenham"
    assert social.post_bluesky(item, text) == "at://did:plc:abc/post/1"

    (session_url, session, _), (record_url, body, headers) = calls
    assert session == {"identifier": "cheltenham-od.uk", "password": "app-password"}
    assert headers == {"Authorization": "Bearer jwt"} and body["repo"] == "did:plc:abc"
    record = body["record"]
    assert record["text"] == text and record["langs"] == ["en-GB"] and record["createdAt"].endswith("Z")
    assert record["embed"]["external"] == {"uri": LINK, "title": "Bin days change", "description": "New rounds",
                                           "thumb": {"ref": "b1"}}
    assert len(record["facets"]) == 2


def test_post_mastodon_sends_an_idempotency_key(monkeypatch):
    monkeypatch.setenv("MASTODON_TOKEN", "token")
    sent = {}
    monkeypatch.setattr(social.requests, "post", lambda url, timeout, headers, data: sent.update(
        url=url, headers=headers, data=data) or FakeResponse({"url": "https://mastodon.social/@x/1"}))
    assert social.post_mastodon({"link": LINK}, "Hello") == "https://mastodon.social/@x/1"
    assert sent["headers"]["Idempotency-Key"] == hashlib.sha256(LINK.encode()).hexdigest()
    assert sent["data"] == {"status": "Hello", "visibility": "public", "language": "en"}


# -- The main run ------------------------------------------------------------------

NOW = datetime.now(timezone.utc)


def item(link, hours_ago=1):
    return {"title": "Title", "description": "Summary", "link": link, "published": NOW - timedelta(hours=hours_ago)}


@pytest.fixture
def run(state_file, monkeypatch):
    """Run main() with the given feed entries; returns what each network was asked to post."""
    monkeypatch.setattr(social, "hashtags", lambda: TAGS)
    monkeypatch.setattr(social, "page_is_live", lambda link: True)
    for name in ("BLUESKY_HANDLE", "BLUESKY_APP_TOKEN", "MASTODON_TOKEN"):
        monkeypatch.setenv(name, "set")
    posted = []

    def poster(name):
        def post(e, text):
            posted.append((name, e["link"]))
            return f"{name}:{e['link']}"
        return post

    for name in social.NETWORKS:
        monkeypatch.setitem(social.NETWORKS[name], "post", poster(name))

    def go(entries, *args):
        monkeypatch.setattr(sys, "argv", ["social.py", *args])
        monkeypatch.setattr(social, "recent_entries", lambda: (entries, NOW - social.MAX_AGE))
        social.main()
        return posted
    return go


def test_main_posts_new_entries_to_each_network_once(run, state_file):
    assert run([item("/a"), item("/old", hours_ago=24 * 4)]) == [("bluesky", "/a"), ("mastodon", "/a")]
    assert json.loads(state_file.read_text())["posted"]["/a"] == {"bluesky": "bluesky:/a", "mastodon": "mastodon:/a"}
    assert run([item("/a")]) == [("bluesky", "/a"), ("mastodon", "/a")]      # nothing new the second time


def test_main_only_posts_to_networks_with_credentials(run, monkeypatch, state_file):
    monkeypatch.delenv("MASTODON_TOKEN")
    assert run([item("/a")]) == [("bluesky", "/a")]
    assert json.loads(state_file.read_text())["posted"]["/a"] == {"bluesky": "bluesky:/a"}


def test_main_waits_for_the_page_to_go_live(run, monkeypatch, state_file):
    monkeypatch.setattr(social, "page_is_live", lambda link: False)
    assert run([item("/a")]) == []
    assert not state_file.exists()


def test_main_keeps_the_other_network_when_one_fails_and_exits_non_zero(run, monkeypatch, state_file):
    def broken(e, text):
        raise requests.HTTPError("503")

    monkeypatch.setitem(social.NETWORKS["bluesky"], "post", broken)
    with pytest.raises(SystemExit) as exit_info:
        run([item("/a")])
    assert exit_info.value.code == 1
    assert json.loads(state_file.read_text())["posted"]["/a"] == {"mastodon": "mastodon:/a"}


def test_dry_run_posts_nothing_and_changes_nothing(run, monkeypatch, state_file, capsys):
    monkeypatch.delenv("MASTODON_TOKEN")
    assert run([item("/a")], "--dry-run") == []
    assert not state_file.exists()
    out = capsys.readouterr().out
    assert "--- bluesky (" in out and "--- mastodon (" in out


def test_seed_marks_everything_in_the_feed_as_posted(run, state_file):
    assert run([item("/a"), item("/b")], "--seed") == []
    assert json.loads(state_file.read_text())["posted"] == {
        "/a": {"bluesky": "seeded", "mastodon": "seeded"}, "/b": {"bluesky": "seeded", "mastodon": "seeded"}}
