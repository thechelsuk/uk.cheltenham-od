#!/usr/bin/env python3
"""Post new blog posts to Bluesky and Mastodon.

Reads the live news feed, so a post only goes out once its page is live (Jekyll hides
posts dated in the future until the first build after their time). Each post is
title, a short description, the link and the hashtags in _data/social.yml.

What has already been posted, per network, is kept in _data/social-posted.json so a post
is never sent twice, and a failure on one network doesn't repeat the other.

  python _python/social.py            post anything new
  python _python/social.py --dry-run  show what would be posted, and change nothing
  python _python/social.py --seed     mark everything in the feed as already posted

Needs, as environment variables (repository secrets in GitHub Actions, or the
gitignored .env file when running locally). A network without its credentials is skipped:
  BLUESKY_HANDLE, BLUESKY_APP_TOKEN   an app password, not the account password
  MASTODON_TOKEN                          an access token with the write:statuses scope
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import yaml

import helper

# Load .env file for local development if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))

ROOT = helper.repo_root()
STATE = ROOT / "_data" / "social-posted.json"
FEED_URL = f"{helper.site_url()}/feeds/main.xml"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

DESCRIPTION_MAX = 200           # a brief description; the link and hashtags matter more than the detail
MAX_AGE = timedelta(days=3)     # older posts are never sent, whatever the state file says
BLUESKY_HOST = "https://bsky.social"
BLUESKY_LIMIT = 300
MASTODON_HOST = "https://mastodon.social"
MASTODON_LIMIT = 500


def hashtags():
    return yaml.safe_load((ROOT / "_data" / "social.yml").read_text())["hashtags"]


def clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def compose(title, description, link, tags, limit):
    """Title, description, link, hashtags, with the description cut at a word to fit the limit."""
    tag_line = " ".join(tags)
    room = limit - len(title) - len(link) - len(tag_line) - 6      # the three blank lines between the four parts
    room = min(room, DESCRIPTION_MAX)
    if room < 20 or not description:
        return f"{title}\n\n{link}\n\n{tag_line}"
    if len(description) > room:
        description = description[: room - 1].rsplit(" ", 1)[0].rstrip(" ,;:.-") + "…"
    return f"{title}\n\n{description}\n\n{link}\n\n{tag_line}"


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"posted": {}}


def save_state(state):
    helper.write_json(STATE, state)


def recent_entries():
    """Posts from the live feed within MAX_AGE whose page is actually up, oldest first."""
    feed = feedparser.parse(FEED_URL, agent=HEADERS["User-Agent"])
    if feed.bozo and not feed.entries:
        sys.exit(f"Could not read {FEED_URL}")
    cutoff = datetime.now(timezone.utc) - MAX_AGE
    entries = []
    for e in feed.entries:
        published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        entries.append({"title": clean(e.title), "description": clean(e.get("summary")),
                        "link": e.link, "published": published})
    return sorted(entries, key=lambda x: x["published"]), cutoff


def page_is_live(link):
    try:
        return requests.head(link, headers=HEADERS, allow_redirects=True, timeout=20).status_code == 200
    except requests.RequestException:
        return False


# ---- Bluesky ----

def byte_span(text, fragment, start=0):
    index = text.index(fragment, start)
    begin = len(text[:index].encode("utf-8"))
    return begin, begin + len(fragment.encode("utf-8"))


def bluesky_facets(text, link):
    begin, end = byte_span(text, link)
    facets = [{"index": {"byteStart": begin, "byteEnd": end},
               "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}]}]
    for match in re.finditer(r"#\w+", text):
        begin, end = byte_span(text, match.group(0), match.start())
        facets.append({"index": {"byteStart": begin, "byteEnd": end},
                       "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": match.group(0)[1:]}]})
    return facets


def bluesky_thumbnail(link, token):
    """Upload the page's social image, so the link card has a picture. Cards work without one."""
    try:
        page = requests.get(link, headers=HEADERS, timeout=20).text
        match = re.search(r'<meta property="og:image" content="([^"]+)"', page)
        if not match:
            return None
        image = requests.get(match.group(1), headers=HEADERS, timeout=20)
        image.raise_for_status()
        resp = requests.post(f"{BLUESKY_HOST}/xrpc/com.atproto.repo.uploadBlob", data=image.content, timeout=30,
                             headers={"Authorization": f"Bearer {token}",
                                      "Content-Type": image.headers.get("Content-Type", "image/png")})
        resp.raise_for_status()
        return resp.json()["blob"]
    except (requests.RequestException, KeyError, ValueError):
        return None


def post_bluesky(entry, text):
    session = requests.post(f"{BLUESKY_HOST}/xrpc/com.atproto.server.createSession", timeout=30,
                            json={"identifier": os.environ["BLUESKY_HANDLE"],
                                  "password": os.environ["BLUESKY_APP_TOKEN"]})
    session.raise_for_status()
    auth = session.json()
    card = {"uri": entry["link"], "title": entry["title"], "description": entry["description"]}
    thumb = bluesky_thumbnail(entry["link"], auth["accessJwt"])
    if thumb:
        card["thumb"] = thumb
    record = {"$type": "app.bsky.feed.post", "text": text, "langs": ["en-GB"],
              "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
              "facets": bluesky_facets(text, entry["link"]),
              "embed": {"$type": "app.bsky.embed.external", "external": card}}
    resp = requests.post(f"{BLUESKY_HOST}/xrpc/com.atproto.repo.createRecord", timeout=30,
                         headers={"Authorization": f"Bearer {auth['accessJwt']}"},
                         json={"repo": auth["did"], "collection": "app.bsky.feed.post", "record": record})
    resp.raise_for_status()
    return resp.json()["uri"]


# ---- Mastodon ----

def post_mastodon(entry, text):
    resp = requests.post(f"{MASTODON_HOST}/api/v1/statuses", timeout=30,
                         headers={"Authorization": f"Bearer {os.environ['MASTODON_TOKEN']}",
                                  "Idempotency-Key": hashlib.sha256(entry["link"].encode()).hexdigest()},
                         data={"status": text, "visibility": "public", "language": "en"})
    resp.raise_for_status()
    return resp.json()["url"]


NETWORKS = {
    "bluesky": {"needs": ("BLUESKY_HANDLE", "BLUESKY_APP_TOKEN"), "limit": BLUESKY_LIMIT, "post": post_bluesky},
    "mastodon": {"needs": ("MASTODON_TOKEN",), "limit": MASTODON_LIMIT, "post": post_mastodon},
}


def main():
    dry_run, seed = "--dry-run" in sys.argv, "--seed" in sys.argv
    state = load_state()
    entries, cutoff = recent_entries()

    if seed:
        for e in entries:
            state["posted"].setdefault(e["link"], {}).update({name: "seeded" for name in NETWORKS})
        save_state(state)
        print(f"Marked {len(entries)} posts in the feed as already posted")
        return

    active = [n for n, cfg in NETWORKS.items() if dry_run or all(os.environ.get(v) for v in cfg["needs"])]
    for name in NETWORKS:
        if name not in active:
            print(f"Skipping {name}: credentials not set")

    failed = False
    for e in entries:
        if e["published"] < cutoff:
            continue
        done = state["posted"].get(e["link"], {})
        todo = [n for n in active if n not in done]
        if not todo:
            continue
        if not dry_run and not page_is_live(e["link"]):
            print(f"Waiting for {e['link']} to go live")
            continue
        for name in todo:
            text = compose(e["title"], e["description"], e["link"], hashtags(), NETWORKS[name]["limit"])
            if dry_run:
                print(f"--- {name} ({len(text)} characters) ---\n{text}\n")
                continue
            try:
                result = NETWORKS[name]["post"](e, text)
            except (requests.RequestException, KeyError, ValueError) as err:
                print(f"Could not post {e['link']} to {name}: {err}")
                failed = True
                continue
            state["posted"].setdefault(e["link"], {})[name] = result
            save_state(state)
            print(f"Posted {e['link']} to {name}: {result}")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
