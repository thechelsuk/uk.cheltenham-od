# importing modules
import json
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser
import yaml
from dateutil.parser import parse as parse_date

import helper

PAGE_SIZE = 25
SITE_TIMEZONE = ZoneInfo("Europe/London")
SITE_URL = "https://cheltenham-od.uk"


def time_ago(dt):
    now = datetime.now()
    diff = now - dt
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        h = diff.seconds // 3600
        return f"{h} hour{'s' if h != 1 else ''} ago"
    elif diff.seconds > 60:
        m = diff.seconds // 60
        return f"{m} minute{'s' if m != 1 else ''} ago"
    else:
        return "just now"


def clean_summary(raw, max_len=160):
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "…"
    return text


def fetch_rss_items(source):
    feed = feedparser.parse(source["url"])
    items = []
    for entry in feed["items"][:25]:
        if not entry.get("published_parsed"):
            continue
        dt = datetime(*entry["published_parsed"][:6])
        items.append({
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", ""),
            "source": source["title"],
            "source_color": source.get("color", "#7a7973"),
            "published_iso": dt.isoformat(),
            "summary": clean_summary(entry.get("summary", "")),
        })
    return items


def slug_from_filename(path):
    """'2026-09-14-council-tax-added.md' -> 'council-tax-added'."""
    match = re.match(r"^\d{4}-\d{2}-\d{2}-(.+)$", path.stem)
    return match.group(1) if match else path.stem


def as_datetime(value):
    if isinstance(value, datetime):
        return value
    if hasattr(value, "year"):  # datetime.date, from a bare YAML date
        return datetime(value.year, value.month, value.day)
    return parse_date(str(value))


def fetch_local_items(source, root):
    """Pull items straight from this site's own _posts/_events collections,
    rather than round-tripping through our own already-derived Atom feeds."""
    kind = source["kind"]
    collection_dir = root / ("_posts" if kind == "posts" else "_events")
    link_template = "/news/{slug}.html" if kind == "posts" else "/events/{slug}/"

    items = []
    for path in sorted(collection_dir.glob("*.md")):
        front_matter, _ = helper.parse_front_matter(path.read_text())
        if not front_matter or not front_matter.get("date"):
            continue
        items.append({
            "title": (front_matter.get("title") or "").strip(),
            "link": link_template.format(slug=slug_from_filename(path)),
            "source": source["title"],
            "source_color": source.get("color", "#7a7973"),
            "published_iso": as_datetime(front_matter["date"]).isoformat(),
            "summary": clean_summary(front_matter.get("description", "")),
        })
    return items


def load_archive(archive_path):
    if not archive_path.exists():
        return {}
    try:
        payload = json.loads(archive_path.read_text())
    except json.JSONDecodeError:
        return {}
    return {item["link"]: item for item in payload.get("items", []) if item.get("link")}


def write_paginated_page(path, page_num):
    """Generated pages only need a permalink and which page they are —
    page_size/total_pages/offset/prev_url/next_url are all derived in the
    layout from site.data.news_archive, so they don't need to be baked into
    every page's front matter (and news.md, page 1, needs none of this at
    all: page_num defaults to 1 in the layout)."""
    front_matter = {
        "layout": "news-aggregation",
        "title": f"Cheltenham News Archive — Page {page_num}",
        "seo": f"Older Cheltenham local news headlines, page {page_num} of our aggregation archive.",
        "description": "Older headlines from our Cheltenham news aggregation archive.",
        "extra_css": "/assets/news-aggregation.css",
        "type": "about",
        "permalink": f"/cheltenham-news/page/{page_num}/",
        "robots": "noindex,follow",
        "page_num": page_num,
    }
    content = "---\n" + yaml.safe_dump(front_matter, sort_keys=False, allow_unicode=True) + "---\n\n{% include sponsor.html %}\n"
    path.write_text(content)


# processing
if __name__ == "__main__":
    root = helper.repo_root()

    config_path = root / "_data/news-sources.yml"
    with config_path.open() as f:
        sources = yaml.safe_load(f)["sources"]

    fetched_items = []
    for source in sources:
        if source.get("kind") in ("posts", "events"):
            fetched_items.extend(fetch_local_items(source, root))
        else:
            fetched_items.extend(fetch_rss_items(source))

    archive_path = root / "_data/news_archive.json"
    merged = load_archive(archive_path)
    for item in fetched_items:
        if item["link"]:
            merged[item["link"]] = item

    # Jekyll hides anything dated in the future (future: false in _config.yml) until the
    # first build after that time, so leave those items out too, or they link to pages that 404.
    now = datetime.now(SITE_TIMEZONE).replace(tzinfo=None)
    all_items = [item for item in merged.values() if datetime.fromisoformat(item["published_iso"]) <= now]
    for item in all_items:
        item["published_relative"] = time_ago(datetime.fromisoformat(item["published_iso"]))
    all_items.sort(key=lambda x: x["published_iso"], reverse=True)

    payload = {
        "updated": helper.updated_timestamp(),
        "sources": [{"title": s["title"], "color": s.get("color", "#7a7973")} for s in sources],
        "count": len(all_items),
        "page_size": PAGE_SIZE,
        "items": all_items,
    }
    helper.write_json(archive_path, payload)

    # Every headline, one entry each, as soon as it's picked up — a typical
    # "new item appears in the feed" RSS reader experience. The once-a-day
    # round-up feed (feeds/news-summary.xml) is generated separately by
    # news-digest.py, since it needs to fire once at a fixed time of day
    # rather than every time this script runs.
    helper.write_items_atom(
        all_items,
        root / "feeds/news-breaking.xml",
        permalink_path="/feeds/news-breaking.xml",
        feed_title="Cheltenham OD - Breaking Cheltenham News",
        feed_subtitle="Every local headline aggregated across Cheltenham news, council, police and community sources, as it's picked up.",
        self_url=f"{SITE_URL}/feeds/news-breaking.xml",
        alternate_url=f"{SITE_URL}/cheltenham-news",
    )

    total_pages = max(1, math.ceil(len(all_items) / PAGE_SIZE))

    pages_dir = root / "_pages/about-info/news-pages"
    pages_dir.mkdir(exist_ok=True)

    for stale in pages_dir.glob("page-*.md"):
        stale_num = int(re.search(r"page-(\d+)\.md", stale.name).group(1))
        if stale_num > total_pages:
            stale.unlink()

    for page_num in range(2, total_pages + 1):
        write_paginated_page(pages_dir / f"page-{page_num}.md", page_num)

    print(f"News completed: {len(all_items)} items across {len(sources)} sources, {total_pages} page(s)")
