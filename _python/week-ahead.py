#!/usr/bin/env python3
"""Build the next issue of The Cheltenham Week Ahead newsletter.

Nothing is fetched — every section reads data the site's own fetchers
already maintain (weather, roadworks, the news archive, the latest curated
events post) plus the hand-picked venue shortlist in newsletter-venues.json.
Writes one page to the `newsletters` collection, _newsletters/<monday>.md,
covering the coming Monday to Sunday.

Bus disruptions, power cuts and flood warnings are deliberately left out —
those are breaking-news timescales (minutes to days), not something anyone
can know on a Sunday night for the Thursday after. Roadworks are kept
because they're planned weeks or months ahead, which does suit a week-ahead
email.

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
COMING_UP_DAYS = 28                         # how far past this week "coming up" reaches
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
    return (
        "| Day | High | Low | Rain | Weather |\n"
        "| --- | ---: | ---: | ---: | --- |\n" + "\n".join(rows)
    )


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
    lines.append("\nSee [roadworks](/cheltenham-roadworks) for the full picture, including anything "
                  "that comes up at shorter notice during the week.")
    return "\n".join(lines)


def parse_events_file():
    """[(date, title)] from the most recent curated 'Upcoming Events' post, sorted by date."""
    files = sorted((ROOT / "_events").glob("*.md"), reverse=True)
    if not files:
        return []
    text = files[0].read_text(encoding="utf-8")
    body = text.split("---", 2)[2] if text.startswith("---") else text
    reference_year = date.today().year
    day_blocks = re.split(r"^## (.+)$", body, flags=re.M)[1:]   # alternating heading, content
    events = []
    for heading, content in zip(day_blocks[0::2], day_blocks[1::2]):
        try:
            event_date = datetime.strptime(f"{heading.strip()} {reference_year}", "%A %d %B %Y").date()
        except ValueError:
            continue
        # The post has no year in its day headings, and can span a New Year; a date that reads as
        # months in the past is next year's, not this one.
        if event_date < date.today() - timedelta(days=180):
            event_date = event_date.replace(year=event_date.year + 1)
        for title, _ in re.findall(r"^### (.+)$\n((?:(?!^##).*\n?)*)", content, re.M):
            events.append((event_date, title.strip()))
    events.sort()
    return events


def events_window(events, start, end, limit):
    picked = [(d, t) for d, t in events if start <= d <= end][:limit]
    if not picked:
        return None
    return "\n".join(f"- **{d.strftime('%a %-d %b')}:** {md_escape(t)}" for d, t in picked)


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
    kind = "a pub" if venue["type"] == "Pub or bar" else "a restaurant or cafe"
    body = (
        f"This week, why not try **[{md_escape(venue['name'])}]({maps_url})**, "
        f"{kind} at {md_escape(venue['address'])}."
    )
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

    events = parse_events_file()
    this_week_events = events_window(events, week_start, week_end, MAX_EVENTS)
    coming_up_events = events_window(events, week_end + timedelta(days=1),
                                      week_end + timedelta(days=COMING_UP_DAYS), MAX_EVENTS)
    venue_body, venue_name = venue_section(recent_venues)

    date_range = f"{week_start.strftime('%-d')} to {week_end.strftime('%-d %B %Y')}" \
        if week_start.month == week_end.month else f"{week_start.strftime('%-d %B')} to {week_end.strftime('%-d %B %Y')}"
    title = f"The Cheltenham Week Ahead: {date_range}"
    seo = f"This week in Cheltenham, {date_range}: weather, roadworks, events and the week's top local stories."

    blocks = [
        f"Good morning! Here's what's happening in Cheltenham from {date_range}.",
        section("This Week's Weather", weather_section(week_start, week_end)),
        section("Roadworks", roadworks_section(week_start, week_end)),
        section("What's On This Week", this_week_events),
        section("Coming Up Later This Month", coming_up_events),
        section("New on Cheltenham Open Data", new_on_site_section(since_date)),
        section("This Week's Top Stories", top_stories_section()),
        section("Somewhere to Eat", venue_body),
        "---\n\nThat's the week ahead. Missed an issue? The [newsletter archive](/newsletter) has "
        "every one, and you can read the day's headlines any time on [Cheltenham Open Data](/).",
    ]
    body = "\n\n".join(b for b in blocks if b) + "\n"

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
