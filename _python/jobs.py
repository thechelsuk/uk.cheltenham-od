#!/usr/bin/env python3
"""Job vacancies within five miles of Cheltenham, from GOV.UK's Work Hub job
search, written as one classified advert per job in _classifieds/jobs/.

Each run asks for jobs posted since yesterday and skips any job already in
_classifieds/jobs/ (matched on its Work Hub ID), so the list builds up day by day.
Work Hub's five-mile search also returns national and county-wide jobs, so
only those whose location is in or around Cheltenham are kept. A new job's page is fetched once for its closing date, hours and job
type. Each advert carries the job's facts and the first sentences of its
description, and links back to the full advert on GOV.UK. An advert is
listed for a week, or until the job closes if that is sooner, and the file
is deleted once it expires. Hand-written classifieds (no job_id) are never
touched.

Work Hub's robots.txt allows /jobs; requests are paced a second apart.
"""
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup

import config
import helper

ROOT = Path(__file__).resolve().parents[1]
CLASSIFIEDS = ROOT / "_classifieds" / "jobs"

BASE_URL = "https://www.jobs.service.gov.uk"
SEARCH_PARAMS = {
    "locationId": "osgb4000000074576734",
    "location": "Cheltenham, Gloucestershire, South West, England",
    "milesFromPostcode": "5",
    "postingDateRange": "1",
}
MAX_PAGES = 20            # a safety stop; a day is normally three or four pages
# A job counts as local if its location names one of these places or gives
# a Cheltenham postcode.
LOCAL_PLACES = (
    "cheltenham", "charlton kings", "prestbury", "leckhampton", "bishop's cleeve", "bishops cleeve",
    "woodmancote", "southam", "shurdington", "up hatherley", "swindon village", "uckington", "staverton",
)
LISTING_DAYS = 7
SUMMARY_CHARS = 320
PAUSE_SECONDS = 1


def long_date(text):
    """'14 Sept 2026' or '24 Oct 2026' -> date."""
    text = " ".join(text.replace("Sept", "Sep").split())
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def tidy_salary(text):
    """'£15 to £15 an hour' -> '£15 an hour'."""
    return re.sub(r"£([\d,.]+) to £\1\b", r"£\1", text)


def summary(text):
    """The first sentences of a description, up to about SUMMARY_CHARS."""
    text = " ".join(text.split())
    if len(text) <= SUMMARY_CHARS:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = ""
    for s in sentences:
        if out and len(out) + len(s) + 1 > SUMMARY_CHARS:
            break
        out = f"{out} {s}".strip()
    if len(out) > SUMMARY_CHARS:
        out = out[:SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"
    return out


def search_page(number):
    params = dict(SEARCH_PARAMS, pageNumber=str(number))
    soup = BeautifulSoup(helper.get(BASE_URL + "/jobs/search", params=params).text, "html.parser")
    jobs = []
    for card in soup.select('div[data-testid^="searchResultCard-"]'):
        job_id = card["data-testid"].split("-", 1)[1]
        employer = card.select_one('[data-testid="searchResultCardEmployer"]')
        spans = [s.get_text(" ", strip=True) for s in employer.find_all("span")] if employer else []
        salary = card.select_one("p.govuk-\\!-font-weight-bold")
        description = card.select_one('[data-testid="searchResultCardJobDescription"]')
        jobs.append({
            "id": job_id,
            "title": card.select_one(f'[data-testid="jobTitle-{job_id}"]').get_text(" ", strip=True),
            "company": spans[0] if spans else None,
            "location": spans[1].lstrip("- ").strip() if len(spans) > 1 else None,
            "salary": tidy_salary(salary.get_text(" ", strip=True)) if salary and salary.get_text(strip=True) else None,
            "summary": summary(description.get_text(" ", strip=True)) if description else "",
        })
    return jobs


def job_details(job_id):
    """Posting date, closing date, hours and job type from a job's own page."""
    text = BeautifulSoup(helper.get(f"{BASE_URL}/jobs/{job_id}").text, "html.parser").get_text(" ", strip=True)
    text = " ".join(text.split())

    def field(label, stop):
        match = re.search(rf"{label}: (.+?) (?:{stop}):", text)
        return match.group(1).strip() if match else None

    return {
        "location": field("Location", "Working pattern|Job type"),
        "hours": field("Hours", "Location"),
        "job_type": field("Job type", "Posting date"),
        "posted": long_date(field("Posting date", "Closing date") or ""),
        "closes": long_date((re.search(r"Closing date: (\d{1,2} \w+ \d{4})", text) or [None, ""])[1]),
    }


def is_local(*locations):
    for location in locations:
        text = (location or "").lower()
        if any(place in text for place in LOCAL_PLACES):
            return True
        if any(re.search(rf"\b{district}\b", location or "", re.I) for district in config.POSTCODE_DISTRICTS):
            return True
    return False


def existing():
    """{job_id: path} for every imported advert already on disk."""
    found = {}
    for path in CLASSIFIEDS.glob("*.md"):
        match = re.search(r'^job_id: "?([0-9a-f]+)"?$', path.read_text(encoding="utf-8"), re.M)
        if match:
            found[match.group(1)] = path
    return found


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60].strip("-")


def write_advert(job, details, today):
    posted = details["posted"] or today
    expires = today + timedelta(days=LISTING_DAYS)
    if details["closes"] and details["closes"] < expires:
        expires = details["closes"]
    job_type = ", ".join(t for t in (details["hours"], details["job_type"]) if t)
    front = {
        "layout": "advert",
        "type": "about",
        "title": job["title"],
        "category": "jobs",
        "company": job["company"],
        "location": job["location"],
        "salary": job["salary"],
        "job_type": job_type or None,
        "date": today.isoformat(),
        "expires": expires.isoformat(),
        "apply_url": f"{BASE_URL}/jobs/{job['id']}",
        "apply_text": "Apply on GOV.UK",
        "source": "GOV.UK Work Hub",
        "job_id": job["id"],
        "robots": "noindex",
    }
    lines = ["---"]
    for key, value in front.items():
        if value:
            # JSON strings are valid YAML double-quoted strings.
            lines.append(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, str) and key not in ('date', 'expires') else value}")
    lines.append("---")
    body = [job["summary"], ""] if job["summary"] else []
    body.append(f"Posted on GOV.UK on {posted.isoformat()}"
                + (f", applications close {details['closes'].isoformat()}." if details["closes"] else "."))
    body.append("")
    body.append("This vacancy is listed from GOV.UK's Work Hub job search. Read the full advert and apply there.")
    path = CLASSIFIEDS / f"{today.isoformat()}-{slug(job['title'])}-{job['id'][-8:]}.md"
    path.write_text("\n".join(lines + [""] + body) + "\n", encoding="utf-8")


def main():
    today = date.today()
    CLASSIFIEDS.mkdir(parents=True, exist_ok=True)
    on_disk = existing()

    # Drop expired imported adverts.
    removed = 0
    for job_id, path in list(on_disk.items()):
        match = re.search(r"^expires: (\d{4}-\d{2}-\d{2})", path.read_text(encoding="utf-8"), re.M)
        if match and date.fromisoformat(match.group(1)) < today:
            path.unlink()
            removed += 1

    added = 0
    seen = set()
    for number in range(1, MAX_PAGES + 1):
        jobs = search_page(number)
        time.sleep(PAUSE_SECONDS)
        if not jobs:
            break
        for job in jobs:
            if job["id"] in on_disk or job["id"] in seen:
                continue
            seen.add(job["id"])
            if job["location"] and not is_local(job["location"]):
                continue   # national or county-wide; no need to open it
            details = job_details(job["id"])
            time.sleep(PAUSE_SECONDS)
            if not is_local(job["location"], details["location"]):
                continue
            if details["closes"] and details["closes"] < today:
                continue
            job["location"] = " ".join((job["location"] or details["location"] or "").replace(" ,", ",").split())
            write_advert(job, details, today)
            added += 1
    print(f"Added {added} job adverts, removed {removed} expired ones")


if __name__ == "__main__":
    main()
