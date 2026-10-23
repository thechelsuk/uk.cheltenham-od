#!/usr/bin/env python3
"""Emergency school closures for Cheltenham schools, from Gloucestershire
County Council's closures page, which schools update themselves when they
have to close (snow, a burst pipe, a power cut).

The council lists closures for every school and library in the county, and
drops each one once its day has passed, so we:
- keep only closures for schools in _data/schools.json, matched by name
  (ignoring case, punctuation and "CofE" spellings), with any council names
  that differ from ours mapped in _data/school-closure-aliases.json
- keep our own history in _data/school-closures-history.json, since the
  council keeps none

Runs with the four-times-daily workflow, so a closure announced the evening
before or posted first thing in the morning is picked up the same day.
Writes _data/school-closures.json (today's and upcoming closures), the
history, feeds/school-closures.xml and the homepage alert. The combined
alerts feed picks up the new feed on the Pi's next run."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import helper

RSS_URL = "https://www.gloucestershire.gov.uk/api/pcg-emergency-school-closures/rss-feed/get"
SOURCE_URL = "https://www.gloucestershire.gov.uk/closures/"
SOURCE = "Gloucestershire County Council"
LICENCE = "None stated"

PAGE_PATH = "/cheltenham-schools/closures"
HISTORY_RETENTION_DAYS = 730

# "Springbank Primary Academy closed on Friday, 23 October 2026": everything
# before the last " on " is the school and its status.
TITLE = re.compile(r"^(?P<rest>.+) on (?:[A-Za-z]+, )?(?P<date>\d{1,2} [A-Za-z]+ \d{4})\s*$")


def norm(name):
    """A school name reduced for matching: lower case, no punctuation, and
    "C of E" / "CofE" / "Church of England" all the same."""
    name = name.lower().replace("&", " and ")
    name = re.sub(r"[’'`]", "", name)
    name = re.sub(r"[.,()\-/]", " ", name)
    name = re.sub(r"\bc of e\b|\bchurch of england\b", "cofe", name)
    return re.sub(r"\s+", " ", name).strip()


def school_index(schools, aliases):
    """Our schools by normalised name, plus each alias (council name -> our name)."""
    index = {norm(s["name"]): s for s in schools}
    for council_name, our_name in aliases.items():
        school = index.get(norm(our_name))
        if school is None:
            raise ValueError(f"alias {council_name!r} points at {our_name!r}, which is not in schools.json")
        index[norm(council_name)] = school
    return index


def parse_title(title, index):
    """(school, status, YYYY-MM-DD) for one of our schools, else None."""
    match = TITLE.match(title.strip())
    if not match:
        return None
    try:
        day = datetime.strptime(match["date"], "%d %B %Y").date().isoformat()
    except ValueError:
        return None
    rest = norm(match["rest"])
    # The longest matching name wins, so "Dean Close School" can't swallow
    # "Dean Close Preparatory School".
    for key in sorted(index, key=len, reverse=True):
        if rest.startswith(key + " "):
            status = rest[len(key):].strip()
            return index[key], status.capitalize(), day
    return None


def urn(school):
    return school["urn_url"].rstrip("/").split("/")[-1]


def parse_closures(text, index):
    """Closures for our schools from the RSS text, and the titles we skipped."""
    root = ET.fromstring(text.lstrip("﻿"))
    closures, unmatched = [], []
    for el in root.iter("item"):
        title = el.findtext("title") or ""
        parsed = parse_title(title, index)
        if parsed is None:
            unmatched.append(title)
            continue
        school, status, day = parsed
        posted = el.findtext("pubDate")
        closures.append({
            "id": f"{urn(school)}-{day}",
            "urn": urn(school),
            "school": school["name"],
            "phase": school.get("phase") or "",
            "date": day,
            "status": status,
            "reason": re.sub(r"\s+", " ", el.findtext("description") or "").strip(),
            "posted_iso": parsedate_to_datetime(posted).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if posted else "",
        })
    closures.sort(key=lambda c: (c["date"], c["school"]))
    return closures, unmatched


def today_uk():
    return datetime.now(ZoneInfo("Europe/London")).date()


def current(closures, today):
    """Closures for today or a later day."""
    return [c for c in closures if c["date"] >= today.isoformat()]


def headline(closure):
    return f"{closure['school']} {closure['status'].lower()} on {helper.alert_date(closure['date'])}"


def build_alert_html(closures):
    return helper.alert_rows("School", [(PAGE_PATH, headline(c)) for c in closures])


def build_atom_items(records, history_url):
    return [{
        "title": headline(r),
        "link": f"{history_url}#{r['id']}",
        "summary": r.get("reason") or "",
        "published_iso": r.get("posted_iso") or r.get("first_seen_iso") or f"{r['date']}T00:00:00Z",
        "source": SOURCE,
    } for r in records[:50]]


def main():
    root = helper.repo_root()
    data_dir = root / "_data"

    text = helper.get(RSS_URL).text
    if "<rss" not in text[:500]:
        raise RuntimeError("the council returned a page that is not the closures feed")

    schools = json.loads((data_dir / "schools.json").read_text())
    aliases = json.loads((data_dir / "school-closure-aliases.json").read_text()).get("aliases", {})
    closures, unmatched = parse_closures(text, school_index(schools, aliases))
    print(f"{len(closures)} closures for our schools; skipped {len(unmatched)} others")
    for title in unmatched:
        print(f"  skipped: {title}")

    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    upcoming = current(closures, today_uk())
    helper.write_json(data_dir / "school-closures.json", {
        "generated_at": now.isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "count": len(upcoming),
        "closures": upcoming,
    })

    history_path = data_dir / "school-closures-history.json"
    history = json.loads(history_path.read_text()) if history_path.exists() else {}
    records = helper.update_history(
        history.get("records", []), closures, id_key="id", now_iso=now_iso,
        retention_days=HISTORY_RETENTION_DAYS,
    )
    records.sort(key=lambda r: (r["date"], r["school"]), reverse=True)
    helper.write_json(history_path, {
        "generated_at": now.isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "tracking_since": history.get("tracking_since") or now.date().isoformat(),
        "count": len(records),
        "records": records,
    })
    print(f"History now holds {len(records)} closures")

    site = helper.site_url()
    history_url = f"{site}{PAGE_PATH}/history"
    helper.write_items_atom(
        items=build_atom_items(records, history_url),
        filename=root / "feeds" / "school-closures.xml",
        permalink_path="/feeds/school-closures.xml",
        feed_title="Cheltenham School Closures",
        feed_subtitle="Emergency closures of Cheltenham schools, as posted by Gloucestershire County Council",
        self_url=f"{site}/feeds/school-closures.xml",
        alternate_url=f"{site}{PAGE_PATH}",
    )

    include_path = root / "_includes" / "school-closures-alert.html"
    include_path.write_text(helper.replace_chunk(
        include_path.read_text(), "school_closures_alert_marker", build_alert_html(upcoming)))


if __name__ == "__main__":
    main()
