# importing modules
import feedparser
import yaml
import helper
import re
from datetime import datetime, timedelta


def time_ago(published_parsed):
    published_date = datetime(*published_parsed[:6])
    now = datetime.now()
    diff = now - published_date
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


# processing
if __name__ == "__main__":
    root = helper.repo_root()

    config_path = root / "_data/news-sources.yml"
    with config_path.open() as f:
        sources = yaml.safe_load(f)["sources"]

    all_items = []

    for source in sources:
        feed = feedparser.parse(source["url"])
        for item in feed["items"][:25]:
            item["_source"] = source["title"]
            item["_source_color"] = source.get("color", "#7a7973")
            all_items.append(item)

    all_items = [item for item in all_items if item.get("published_parsed")]
    all_items.sort(key=lambda x: x["published_parsed"], reverse=True)

    cutoff_date = datetime.now() - timedelta(days=30)
    all_items = [item for item in all_items if datetime(*item["published_parsed"][:6]) > cutoff_date]

    news_items = []
    for item in all_items:
        dt = datetime(*item["published_parsed"][:6])
        news_items.append({
            "title": item.get("title", "").strip(),
            "link": item.get("link", ""),
            "source": item["_source"],
            "source_color": item["_source_color"],
            "published_iso": dt.isoformat(),
            "published_relative": time_ago(item["published_parsed"]),
            "summary": clean_summary(item.get("summary", "")),
        })

    payload = {
        "updated": helper.updated_timestamp(),
        "sources": [{"title": s["title"], "color": s.get("color", "#7a7973")} for s in sources],
        "count": len(news_items),
        "items": news_items,
    }

    helper.write_json(root / "_data/news.json", payload)
    print(f"News completed: wrote {len(news_items)} items to _data/news.json")
