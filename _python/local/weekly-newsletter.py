#!/usr/bin/env python3
"""Interactively build a draft issue of The Cheltenham Week Ahead newsletter.

You run this yourself, whenever you want to prepare the coming week's issue —
there's no schedule. Most sections read data the site's own fetchers already
maintain (weather, roadworks, the news archive) plus the hand-picked venue
shortlist in newsletter-venues.json. "What's On" reuses
_python/local/event-roundup.py's own fetch/dedupe/review pipeline (loaded
directly, not reimplemented — it already does real text-based event-date
extraction, fuzzy deduplication across feeds and a proper terminal checkbox
review) to fetch _data/event-sources.yml live and ask you which events to
include, formatting your picks into the issue instead of writing its usual
_events/*.md post.

Nothing is published. This writes _data/newsletter-draft.json — one scratch
slot holding the complete text of the issue (front matter and all), which
the "Newsletter" tab on /admin shows with a one-click copy. That file is
gitignored: it's working state for you, not something the site needs to
ship. To publish a reviewed draft, copy it from /admin and save it yourself
as _newsletters/<monday>.md, then commit and push — there's no auto-publish
step, on purpose, so nothing reaches the public /newsletter archive without
you having looked at it first.

    python3 _python/weekly-newsletter.py                        # draft the coming week
    python3 _python/weekly-newsletter.py --for-date 2026-10-05  # draft a specific Monday
    python3 _python/weekly-newsletter.py --days 45              # widen the events search window
"""
import argparse
import importlib.util
import json
import random
import re
import os
import sys
from datetime import date, datetime, timedelta, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import helper

ROOT = helper.repo_root()
DATA = ROOT / "_data"
OUT_DIR = ROOT / "_newsletters"          # published issues live here, but this script never writes to it
DRAFT_PATH = DATA / "newsletter-draft.json"
SITE_URL = helper.site_url()             # links in the draft must resolve outside the site, e.g. in an email

TOP_STORIES = 4
MAX_ROADWORKS = 5
EVENT_DAYS_AHEAD = 28                    # a weekly issue doesn't need event-roundup's own 60-day default
SELF_SOURCE = "Cheltenham OD News"       # our own posts, already covered by "New on the site"
VENUE_REPEAT_GAP = 8                     # issues to avoid repeating a venue within


def load_event_roundup():
    """_python/local/event-roundup.py, imported by path — its filename has a hyphen, so it can't
    be a normal `import`."""
    import sys

    path = ROOT / "_python" / "local" / "event-roundup.py"
    spec = importlib.util.spec_from_file_location("event_roundup", path)
    module = importlib.util.module_from_spec(spec)
    # dataclasses looks itself up via sys.modules[cls.__module__] while the class body runs, so
    # the module must be registered before exec_module(), not after.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def clean_prose(text):
    """md_escape, plus wrapping any bare URL in <angle brackets> (markdownlint's no-bare-urls
    rule) — done via placeholders so escaping punctuation elsewhere in the text can never land
    inside a URL and corrupt it."""
    urls = []

    def stash(match):
        urls.append(match.group(0))
        return f"\x00{len(urls) - 1}\x00"

    text = re.sub(r"(?<![(<\[])\bhttps?://\S+", stash, text or "")
    text = md_escape(text)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<{urls[int(m.group(1))]}>", text)


def section(heading, content):
    """One '## Heading' block, or None if there's nothing to say — content is trimmed so every
    block joins cleanly with exactly one blank line around it, never two."""
    if not content:
        return None
    return f"## {heading}\n\n{content.strip()}"


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

def weather_section(today):
    """The next 7 days from the day you actually run this, not the newsletter's Monday-to-Sunday
    week — otherwise running it a few days before next Monday only catches the tail of the
    forecast (weather.json only looks ~10 days ahead), and running it a day late shows a week
    that's already half gone."""
    data = load("weather.json")
    if not data:
        return None
    forecast_end = today + timedelta(days=6)
    days = [d for d in data["days"] if today <= iso_date(d["date"]) <= forecast_end]
    if not days:
        return None
    lines = []
    for d in days:
        label = iso_date(d["date"]).strftime("%a %-d %b")
        pop = round((d.get("pop") or 0) * 100)
        rain = f", {pop}% chance of rain" if pop >= 20 else ""
        lines.append(
            f"- **{label}:** {d['desc'].capitalize()}, high {round(d['max'])}°C, "
            f"low {round(d['min'])}°C{rain}."
        )
    return "\n".join(lines)


def roadworks_section(week_start, week_end):
    roadworks = load("roadworks.json")
    if not roadworks or not roadworks.get("items"):
        return None
    active = [
        r for r in roadworks["items"]
        if iso_date(r["start"]) and iso_date(r["start"]) <= week_end
        and (not iso_date(r.get("end")) or iso_date(r["end"]) >= week_start)
    ]
    if not active:
        return "No roadworks are expected to affect Cheltenham this week."
    active.sort(key=lambda r: r.get("distance_miles", 99))
    lines = []
    for r in active[:MAX_ROADWORKS]:
        roads = "/".join(r.get("roads") or []) or "Nearby road"
        lines.append(f"- **{md_escape(roads)}** — {clean_prose(trim(r['description'], 140))}")
    lines.append(f"\nSee [roadworks]({SITE_URL}/cheltenham-roadworks) for the full picture, including anything "
                  "that comes up at shorter notice during the week.")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Events — event-roundup.py's own fetch/dedupe/review pipeline, reused as-is
# --------------------------------------------------------------------------

def pick_events(days_ahead):
    """Run event-roundup's fetch → dedupe → terminal checkbox review, then format whatever you
    selected as 'What's On' markdown. Returns None if you selected nothing."""
    event_roundup = load_event_roundup()

    sources = event_roundup.load_sources(DATA / "event-sources.yml")
    print(f"{len(sources)} event source(s) loaded.\n")
    print("Fetching feeds:")
    raw_events = event_roundup.fetch_events(sources, days_ahead)
    print(f"\n{len(raw_events)} total candidate(s) before dedupe.")

    unique_events, flagged = event_roundup.dedupe(raw_events)
    print(f"{len(unique_events)} unique event(s) after fuzzy dedupe.")
    event_roundup.show_flagged(flagged)

    selected = event_roundup.review_events(unique_events)
    if not selected:
        return None

    lines = []
    for ev in sorted(selected, key=lambda e: (e.event_date or date.max, e.title)):
        bit = f"- **{ev.date_label()}:** {md_escape(ev.title)}"
        detail = []
        if ev.venue:
            detail.append(md_escape(ev.venue))
        if ev.description:
            detail.append(clean_prose(trim(ev.description, 120)))
        if detail:
            bit += " — " + "; ".join(detail)
        if ev.link:
            source_name = event_roundup.extract_source_name(ev.link, ev.source_id)
            bit += f" ([{md_escape(source_name)}]({ev.link}))"
        lines.append(bit)
    return "\n".join(lines)


def new_on_site_section(since, min_items=3):
    """Everything posted since the last issue — but if a quiet week leaves fewer than
    min_items, keep going back further rather than publish a thin (or empty) section."""
    posts_dir = ROOT / "_posts"
    all_posts = []
    for path in sorted(posts_dir.glob("*.md")):
        m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+)\.md$", path.name)
        if not m:
            continue
        post_date = date.fromisoformat(m.group(1))
        title = re.search(r'^title:\s*"?(.*?)"?\s*$', path.read_text(encoding="utf-8"), re.M)
        all_posts.append((post_date, title.group(1) if title else m.group(2), f"{SITE_URL}/news/{m.group(2)}"))
    if not all_posts:
        return None
    all_posts.sort(reverse=True)

    items = [p for p in all_posts if p[0] > since]
    if len(items) < min_items:
        items = all_posts[:min_items]
    return "\n".join(f"- [{md_escape(title)}]({link})" for _, title, link in items)


def top_stories_section():
    archive = load("news_archive.json")
    if not archive:
        return None
    items = [i for i in archive["items"] if i.get("source") != SELF_SOURCE][:TOP_STORIES]
    if not items:
        return None
    blocks = []
    for i in items:
        block = f"### [{md_escape(i['title'])}]({i['link']})"
        # Summary and source share one paragraph — a line that's nothing but *emphasis* reads
        # to markdownlint (MD036) as a heading someone forgot to mark up as one.
        summary = clean_prose(trim(i["summary"], 200)) if i.get("summary") else ""
        source = f"*{md_escape(i['source'])}*" if i.get("source") else ""
        tail = " — ".join(p for p in (summary, source) if p)
        if tail:
            block += f"\n\n{tail}"
        blocks.append(block)
    return "\n\n".join(blocks)


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
    body = (
        "Each week we pick a local eatery at random from around the area. "
        f"This week, why not try **[{md_escape(venue['name'])}]({maps_url})**, located at "
        f"{md_escape(venue['address'])}. [Check for opening hours]({maps_url})."
    )
    return body, venue["name"]


# --------------------------------------------------------------------------

def build(week_start, since_date, event_days_ahead):
    week_end = week_start + timedelta(days=6)
    today = date.today()
    issues = existing_issues()
    recent_venues = {i["venue"] for i in issues[-VENUE_REPEAT_GAP:] if i["venue"]}

    whats_on = pick_events(event_days_ahead)
    venue_body, venue_name = venue_section(recent_venues)

    date_range = f"{week_start.strftime('%-d')} to {week_end.strftime('%-d %B %Y')}" \
        if week_start.month == week_end.month else f"{week_start.strftime('%-d %B')} to {week_end.strftime('%-d %B %Y')}"
    title = f"The Cheltenham Week Ahead: {date_range}"
    seo = f"This week in Cheltenham, {date_range}: weather, roadworks, events and the week's top local stories."

    blocks = [
        f"Good morning! Here's what's happening in Cheltenham from {date_range}.",
        section("Weather for the Next 7 Days", weather_section(today)),
        section("Roadworks", roadworks_section(week_start, week_end)),
        section("What's On", whats_on),
        section("New on Cheltenham Open Data", new_on_site_section(since_date)),
        section("This Week's Top Stories", top_stories_section()),
        section("Somewhere to Eat", venue_body),
        f"---\n\nThat's the week ahead. Missed an issue? The [newsletter archive]({SITE_URL}/newsletter) has "
        f"every one, and you can read the day's headlines any time on [Cheltenham Open Data]({SITE_URL}/).",
    ]
    body = "\n\n".join(b for b in blocks if b) + "\n"

    # This exact text is what you copy from /admin and save as _newsletters/<monday>.md to
    # publish it — so it needs to be the complete, valid file, front matter included.
    full_file = "\n".join([
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
    ])

    draft = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue_date": week_start.isoformat(),
        "title": title,
        "filename": f"{week_start.isoformat()}.md",
        "save_as": f"_newsletters/{week_start.isoformat()}.md",
        "content": full_file,
    }
    DATA.mkdir(exist_ok=True)
    with open(DRAFT_PATH, "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nWrote {DRAFT_PATH.relative_to(ROOT)} — review and copy it from /admin, "
          f"save as {draft['save_as']} to publish")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--for-date", help="draft a specific Monday (YYYY-MM-DD) instead of the coming one")
    parser.add_argument("--days", type=int, default=EVENT_DAYS_AHEAD,
                         help=f"how many days ahead to search for events (default {EVENT_DAYS_AHEAD})")
    args = parser.parse_args()

    today = date.today()
    week_start = date.fromisoformat(args.for_date) if args.for_date else next_monday(today)

    issues = existing_issues()
    since_date = date.fromisoformat(issues[-1]["issue_date"]) if issues else week_start - timedelta(days=7)

    build(week_start, since_date, args.days)


if __name__ == "__main__":
    main()
