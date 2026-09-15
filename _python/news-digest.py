# Builds the once-a-day round-up feed (feeds/news-summary.xml) from the
# archive news.py maintains. Deliberately a separate script/schedule from
# news.py: it needs to fire once at a fixed time of day, not every time the
# (much more frequent) headline fetch runs.
import json
from datetime import datetime

import helper

DIGEST_SIZE = 10
SITE_URL = "https://cheltenham-od.uk"


def load_digests(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text()).get("digests", [])
    except json.JSONDecodeError:
        return []


if __name__ == "__main__":
    root = helper.repo_root()

    archive_path = root / "_data/news_archive.json"
    if not archive_path.exists():
        raise SystemExit("_data/news_archive.json not found — run news.py first")
    archive = json.loads(archive_path.read_text())
    all_items = archive.get("items", [])

    digests_path = root / "_data/news_digests.json"
    digests = load_digests(digests_path)

    today = datetime.now().date().isoformat()
    already_done = any(d["date"] == today for d in digests)

    if already_done:
        print(f"Digest for {today} already exists — leaving it as-is")
    else:
        snapshot = all_items[:DIGEST_SIZE]
        digests.append({
            "date": today,
            "created_iso": datetime.now().isoformat(),
            "items": [
                {"title": item["title"], "link": item["link"], "source": item["source"]}
                for item in snapshot
            ],
        })
        digests.sort(key=lambda d: d["date"], reverse=True)
        helper.write_json(digests_path, {"updated": helper.updated_timestamp(), "digests": digests})
        print(f"Created digest for {today} from {len(snapshot)} stories")

    helper.write_digest_atom(
        digests,
        root / "feeds/news-summary.xml",
        permalink_path="/feeds/news-summary.xml",
        feed_title="Cheltenham OD - Cheltenham Daily News Summary",
        feed_subtitle="One round-up a day of the top local headlines — a daily newsletter without the inbox.",
        self_url=f"{SITE_URL}/feeds/news-summary.xml",
        alternate_url=f"{SITE_URL}/cheltenham-news",
    )
    print(f"news-summary.xml written with {len(digests)} daily digest(s)")
