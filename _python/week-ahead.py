#!/usr/bin/env python3
"""Build the next issue of The Cheltenham Week Ahead newsletter.

Nothing is fetched — every section reads data the site's own fetchers
already maintain (weather, roadworks, bus/power/flood alerts, the news
archive) plus the hand-picked venue shortlist in newsletter-venues.json.
Writes one page to the `newsletters` collection, _newsletters/<monday>.md,
covering the coming Monday to Sunday.

This does not send anything — Buttondown has no free-plan API for that.
Review the generated page (or the file itself), then copy its body into
Buttondown's compose window and send it yourself. Run manually or from the
Sunday-evening schedule workflow:

    python3 _python/week-ahead.py              # builds the coming week's issue
    python3 _python/week-ahead.py --overwrite  # rebuilds it if it already exists
"""
import argparse
import json
import random
import re
from datetime import date, datetime, timedelta, timezone

import helper

ROOT = helper.repo_root()
DATA = ROOT / "_data"
OUT_DIR = ROOT / "_newsletters"

TOP_STORIES = 4
MAX_EVENTS = 6
MAX_ROADWORKS = 5
SELF_SOURCE = "Cheltenham OD News"          # our own posts, already covered by "New on the site"
VENUE_REPEAT_GAP = 8                        # issues to avoid repeating a venue within


def load(name):
    path = DATA / name
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def next_monday(today):
    days_ahead = (7 - today.weekday()) % 7 or 7    # weekday(): Monday == 0
    return today + timedelta(days=days_ahead)


def iso_date(value):
    """'2026-09-22T14:00:00' / '2026-09-22' -> date(2026, 9, 22); None on anything else."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def md_escape(text):
    return re.sub(r"([|_*\[\]])", r"\\\1", text or "")


def trim(text, limit=170):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;: ") + "…"


# --------------------------------------------------------------------------
# Existing issues, for the "new on the site" window and repeat-venue avoidance
# --------------------------------------------------------------------------

def existing_issues():
    """[{path, issue_date, venue}], oldest first."""
    issues = []
    if not OUT_DIR.exists():
        return issues
    for path in sorted(OUT_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        front = text.split("---", 2)[1] if text.startswith("---") else ""
        issue_date = re.search(r'^issue_date:\s*"?([\d-]+)"?', front, re.M)
        venue = re.search(r'^venue:\s*"(.*)"', front, re.M)
        issues.append({
            "path": path,
            "issue_date": issue_date.group(1) if issue_date else None,
            "venue": venue.group(1) if venue else None,
        })
    issues.sort(key=lambda i: i["issue_date"] or "")
    return issues


# --------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------

def weather_section(week_start, week_end):
    data = load("weather.json")
    if not data:
        return None
    days = [d for d in data["days"] if week_start <= iso_date(d["date"]) <= week_end]
    if not days:
        return None
    rows = []
    for d in days:
        label = iso_date(d["date"]).strftime("%a %-d %b")
        pop = round((d.get("pop") or 0) * 100)
        rows.append(f"| {label} | {round(d['max'])}° | {round(d['min'])}° | {pop}% | {d['desc'].capitalize()} |")
    table = (
        "| Day | High | Low | Rain | Weather |\n"
        "| --- | ---: | ---: | ---: | --- |\n" + "\n".join(rows)
    )
    if len(days) < 7:
        last = iso_date(days[-1]["date"]).strftime("%A")
        table += (
            f"\n\n*The forecast only reaches {last} so far — check the "
            "[10-day forecast](/cheltenham-10-day-weather-forecast) nearer the time for the rest of the week.*"
        )
    return table


def disruption_section(week_start, week_end):
    lines = []

    roadworks = load("roadworks.json")
    if roadworks and roadworks.get("items"):
        active = [
            r for r in roadworks["items"]
            if iso_date(r["start"]) and iso_date(r["start"]) <= week_end
            and (not iso_date(r.get("end")) or iso_date(r["end"]) >= week_start)
        ]
        active.sort(key=lambda r: r.get("distance_miles", 99))
        for r in active[:MAX_ROADWORKS]:
            roads = "/".join(r.get("roads") or []) or "Nearby road"
            lines.append(f"- **{md_escape(roads)}** — {md_escape(trim(r['description'], 140))}")

    bus = load("bus-disruptions.json")
    for d in (bus or {}).get("disruptions") or []:
        label = d.get("operators_affected") or d.get("organisation") or "Buses"
        lines.append(f"- **Bus — {label}:** {d.get('reason', 'Disruption')}")

    power = load("power-cuts.json")
    for i in (power or {}).get("incidents") or []:
        if i.get("status") == "Restored" or i.get("restored"):
            continue
        area = (i.get("postcodes") or ["Cheltenham"])[0]
        lines.append(f"- **Power — {area}:** {i.get('status', 'Ongoing incident')}")

    flood = load("flood.json")
    for i in (flood or {}).get("items") or []:
        lines.append(f"- **Flood — {i.get('severity', 'Warning')}:** {trim(i.get('description', ''), 120)}")

    if not lines:
        return "No roadworks, bus, power or flood disruption is expected to affect Cheltenham this week."
    lines.append("\nSee [roadworks](/cheltenham-roadworks), [buses](/cheltenham-bus-data), "
                  "[power cuts](/cheltenham-power-cuts) and [flood warnings](/cheltenham-flood-warnings) "
                  "for the full picture.")
    return "\n".join(lines)


def events_section(week_start, week_end):
    events_dir = ROOT / "_events"
    files = sorted(events_dir.glob("*.md"), reverse=True)
    if not files:
        return None
    text = files[0].read_text(encoding="utf-8")
    body = text.split("---", 2)[2] if text.startswith("---") else text
    day_blocks = re.split(r"^## (.+)$", body, flags=re.M)[1:]   # alternating heading, content
    picked = []
    for heading, content in zip(day_blocks[0::2], day_blocks[1::2]):
        try:
            event_date = datetime.strptime(f"{heading.strip()} {week_start.year}", "%A %d %B %Y").date()
        except ValueError:
            continue
        if event_date < week_start:
            event_date = event_date.replace(year=event_date.year + 1)
        if not (week_start <= event_date <= week_end):
            continue
        for title, _ in re.findall(r"^### (.+)$\n((?:(?!^##).*\n?)*)", content, re.M):
            picked.append((event_date, title.strip()))
    if not picked:
        return None
    picked.sort()
    lines = [f"- **{d.strftime('%a %-d %b')}:** {md_escape(t)}" for d, t in picked[:MAX_EVENTS]]
    lines.append("\nMore at [Cheltenham events](/cheltenham-events).")
    return "\n".join(lines)


def new_on_site_section(since):
    posts_dir = ROOT / "_posts"
    items = []
    for path in sorted(posts_dir.glob("*.md")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md$", path.name)
        if not m:
            continue
        post_date = date.fromisoformat(m.group(1))
        if post_date <= since:
            continue
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', path.read_text(encoding="utf-8"), re.M)
        items.append((post_date, title.group(1) if title else m.group(2), f"/news/{m.group(2)}"))
    if not items:
        return None
    items.sort(reverse=True)
    return "\n".join(f"- [{md_escape(title)}]({link})" for _, title, link in items)


def top_stories_section():
    archive = load("news_archive.json")
    if not archive:
        return None
    items = [i for i in archive["items"] if i.get("source") != SELF_SOURCE][:TOP_STORIES]
    if not items:
        return None
    lines = []
    for i in items:
        lines.append(f"### [{md_escape(i['title'])}]({i['link']})")
        if i.get("summary"):
            lines.append(md_escape(trim(i["summary"], 200)))
        lines.append(f"*{md_escape(i.get('source', ''))}*\n")
    return "\n".join(lines)


def venue_section(recent_venues):
    data = load("newsletter-venues.json")
    if not data:
        return None, None
    pool = [v for v in data["venues"] if not v.get("exclude") and v["name"] not in recent_venues]
    if not pool:
        pool = [v for v in data["venues"] if not v.get("exclude")]
    if not pool:
        return None, None
    venue = random.choice(pool)
    maps_url = f"https://www.google.com/maps/search/?api=1&query={venue['lat']},{venue['lon']}"
    body = f"**[{md_escape(venue['name'])}]({maps_url})** — {venue['type']}, {md_escape(venue['address'])}"
    return body, venue["name"]


# --------------------------------------------------------------------------

def build(week_start, since_date, overwrite):
    week_end = week_start + timedelta(days=6)
    issues = existing_issues()
    recent_venues = {i["venue"] for i in issues[-VENUE_REPEAT_GAP:] if i["venue"]}

    out_path = OUT_DIR / f"{week_start.isoformat()}.md"
    if out_path.exists() and not overwrite:
        print(f"{out_path.relative_to(ROOT)} already exists — use --overwrite to rebuild it")
        return

    weather = weather_section(week_start, week_end)
    disruption = disruption_section(week_start, week_end)
    events = events_section(week_start, week_end)
    new_on_site = new_on_site_section(since_date)
    top_stories = top_stories_section()
    venue_body, venue_name = venue_section(recent_venues)

    date_range = f"{week_start.strftime('%-d')} to {week_end.strftime('%-d %B %Y')}" \
        if week_start.month == week_end.month else f"{week_start.strftime('%-d %B')} to {week_end.strftime('%-d %B %Y')}"
    title = f"The Cheltenham Week Ahead: {date_range}"
    seo = f"This week in Cheltenham, {date_range}: weather, roadworks, events and the week's top local stories."

    parts = [f"Good morning! Here's what's happening in Cheltenham from {date_range}.\n"]
    if weather:
        parts.append(f"## This Week's Weather\n\n{weather}\n")
    parts.append(f"## Roadworks and Disruption\n\n{disruption}\n")
    if events:
        parts.append(f"## What's On\n\n{events}\n")
    if new_on_site:
        parts.append(f"## New on Cheltenham Open Data\n\n{new_on_site}\n")
    if top_stories:
        parts.append(f"## This Week's Top Stories\n\n{top_stories}\n")
    if venue_body:
        parts.append(f"## Somewhere to Eat\n\n{venue_body}\n")
    parts.append(
        "---\n\n"
        "That's the week ahead. Missed an issue? The [newsletter archive](/newsletter) has "
        "every one, and you can read the day's headlines any time on [Cheltenham Open Data](/)."
    )
    body = "\n".join(parts)

    front = "\n".join([
        "---",
        "layout: newsletter-issue",
        f'title: "{title}"',
        f'seo: "{seo[:160]}"',
        f'description: "This week in Cheltenham ({date_range}): weather, roadworks, events, what\'s new on the site and the top local stories."',
        # An explicit UTC offset, not a bare local timestamp: `future: false` in _config.yml
        # applies to every collection with a date, and an offset-less timestamp parsed against
        # the site's Europe/London timezone can register as a little in the future and get
        # silently skipped, right when this is generated and built in the same few minutes.
        f"date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %z')}",
        f"issue_date: {week_start.isoformat()}",
        f"week_start: {week_start.isoformat()}",
        f"week_end: {week_end.isoformat()}",
        f'venue: "{venue_name or ""}"',
        'type: "cod"',
        "---",
        "",
        body,
        "",
    ])

    OUT_DIR.mkdir(exist_ok=True)
    out_path.write_text(front, encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true", help="rebuild the issue if it already exists")
    parser.add_argument("--for-date", help="build for a specific Monday (YYYY-MM-DD), mainly for testing")
    args = parser.parse_args()

    today = date.today()
    week_start = date.fromisoformat(args.for_date) if args.for_date else next_monday(today)

    # The issue being (re)built doesn't count as "the last issue" — with --overwrite it would
    # otherwise use its own previous version as the "since" marker and find nothing new.
    prior = [i for i in existing_issues() if i["issue_date"] and i["issue_date"] != week_start.isoformat()]
    since_date = date.fromisoformat(prior[-1]["issue_date"]) if prior else week_start - timedelta(days=7)

    build(week_start, since_date, args.overwrite)


if __name__ == "__main__":
    main()
