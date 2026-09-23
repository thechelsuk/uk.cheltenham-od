#!/usr/bin/env python3
"""Turn the hourly FixMyStreet RSS download (_data/fix-my-street.xml) into
_data/fix-my-street.json (the latest reports) and _data/fix-my-street-history.json
(a rolling log of every report seen since tracking began).

The feed only ever holds the ~20 newest reports within 10km of the town
centre, so the history log is the only way to see anything older than a day or
two."""
import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import helper

DESCRIPTION_MAX_CHARS = 220
GEORSS = {"g": "http://www.georss.org/georss"}
SOURCE_URL = "https://www.fixmystreet.com/"


def load_category_rules(path):
    data = json.loads(path.read_text())
    rules = []
    for rule in data["rules"]:
        pattern = "|".join(rf"\b{re.escape(k)}s?\b" for k in rule["keywords"])
        rules.append((rule["group"], re.compile(pattern, re.I)))
    return data["default"], rules


def categorise(category, default, rules):
    for group, pattern in rules:
        if pattern.search(category):
            return group
    return default


def clean_title(title):
    """Drop the trailing ', 18th September' (the date has its own column) and
    the FixMyStreet/council jargon around auto-generated highways defects."""
    title = re.sub(r",\s*\d{1,2}(st|nd|rd|th)\s+[A-Za-z]+$", "", title.strip())
    title = re.sub(r"\s+problem$", "", title)
    match = re.match(r"^TMC - Defects\s*-\s*(?:CW\d+\s*)?(.+)$", title)
    if match:
        title = f"Highways defect: {match.group(1).strip()}"
    return title


def clean_description(raw):
    """Plain-text reporter description: strip markup, the automatic OpenStreetMap
    'nearest road' and 'Report on FixMyStreet' lines, redact anything that looks
    like an email address or phone number, and truncate. Angle brackets are
    dropped so the text is safe to embed in a JSON <script> tag."""
    text = html.unescape(raw or "")
    text = re.sub(r"<[^>]+>", "\n", text)
    text = re.sub(r"Nearest road to the pin.*", "", text)
    text = re.sub(r"Report on FixMyStreet", "", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email removed]", text)
    text = re.sub(r"(?<!\d)(?:\+44\s?|0)\d[\d\s]{8,11}\d(?!\d)", "[phone removed]", text)
    text = text.replace("<", "").replace(">", "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > DESCRIPTION_MAX_CHARS:
        text = text[:DESCRIPTION_MAX_CHARS].rsplit(" ", 1)[0].rstrip(",.;: ") + "…"
    return text


def parse_feed(path, default_group, rules):
    items = []
    for node in ET.parse(path).getroot().iter("item"):
        link = (node.findtext("link") or "").strip()
        report_id = link.rstrip("/").rsplit("/", 1)[-1]
        point = (node.findtext("g:point", namespaces=GEORSS) or "").split()
        category = (node.findtext("category") or "").strip()
        try:
            published = parsedate_to_datetime(node.findtext("pubDate")).isoformat()
        except (TypeError, ValueError):
            published = ""
        items.append({
            "id": report_id,
            "title": clean_title(html.unescape(node.findtext("title") or "")),
            "url": link,
            "category": category,
            "group": categorise(category, default_group, rules),
            "description": clean_description(node.findtext("description")),
            "lat": float(point[0]) if len(point) == 2 else None,
            "lon": float(point[1]) if len(point) == 2 else None,
            "published_iso": published,
        })
    return items


def group_counts(items):
    counts = {}
    for item in items:
        counts[item["group"]] = counts.get(item["group"], 0) + 1
    return [{"name": name, "count": n} for name, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def month_counts(records):
    counts = {}
    for record in records:
        month = (record.get("published_iso") or "")[:7]
        if month:
            counts[month] = counts.get(month, 0) + 1
    return [{"month": month, "count": counts[month]} for month in sorted(counts)]


def merge_history(existing, items, now_iso):
    """Add new reports and refresh ones still in the feed. Nothing is ever
    dropped, so the history only grows. Returns records newest-first."""
    by_id = {r["id"]: r for r in existing}
    for item in items:
        record = by_id.get(item["id"])
        if record is None:
            record = {"first_seen_iso": now_iso}
            by_id[item["id"]] = record
        record.update(item)
        record["last_seen_iso"] = now_iso
    kept = list(by_id.values())
    kept.sort(key=lambda r: r.get("published_iso", ""), reverse=True)
    return kept


def payload(now, extra):
    return {
        "generated_at": now.isoformat(),
        "source": "FixMyStreet (mySociety)",
        "source_url": SOURCE_URL,
        "refresh": "every two hours",
        **extra,
    }


if __name__ == "__main__":
    root = helper.repo_root()
    data_dir = root / "_data"
    default_group, rules = load_category_rules(data_dir / "fix-my-street-categories.json")

    items = parse_feed(data_dir / "fix-my-street.xml", default_group, rules)
    for item in items:
        if item["group"] == default_group:
            print(f"Uncategorised FixMyStreet category: {item['category']!r}")

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    history_path = data_dir / "fix-my-street-history.json"
    existing = json.loads(history_path.read_text()).get("records", []) if history_path.exists() else []
    records = merge_history(existing, items, now_iso)

    helper.write_json(data_dir / "fix-my-street.json", payload(now, {
        "count": len(items),
        "groups": group_counts(items),
        "items": items,
    }))
    helper.write_json(history_path, payload(now, {
        "count": len(records),
        "groups": group_counts(records),
        "by_month": month_counts(records),
        "records": records,
    }))
    print(f"Fix My Street: {len(items)} latest reports, {len(records)} in history")
