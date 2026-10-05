#!/usr/bin/env python3
"""Ofsted inspection history for every school in _data/schools.json, written
to _data/ofsted.json.

Two Ofsted sources are combined:

- the monthly management information (MI) CSV of each state-funded school's
  latest inspections: report card grades, the latest graded (pre-2025
  framework) outcome, the latest ungraded outcome, and the URN the school had
  at the time, which points to the predecessor of a school that has since
  become an academy;
- the Find an Inspection Report site, for the full list of reports for the
  school and any predecessor, with the overall grade where the site shows it.

Once a school has a report card, the reports site stops showing grades
against its older reports, so grades already in _data/ofsted.json are kept
from one run to the next.

Refreshed monthly, matching the MI release. Independent schools inspected by
the Independent Schools Inspectorate have no Ofsted reports and are left out.
"""
import csv
import io
import json
import os
import re
import time
from datetime import date, datetime, timezone

import requests
from bs4 import BeautifulSoup

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
SCHOOLS = os.path.join(HERE, "..", "_data", "schools.json")
OUT = os.path.join(HERE, "..", "_data", "ofsted.json")

REPORTS_URL = "https://reports.ofsted.gov.uk"
MI_PAGE = "https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"
MI_API = "https://www.gov.uk/api/content/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes"
MI_TITLE = "state-funded schools - latest inspections as at"
# GIAS's daily file of links between establishments (predecessors, successors).
GIAS_LINKS_URL = "https://ea-edubase-api-prod.azurewebsites.net/edubase/downloads/public/links_edubasealldata{:%Y%m%d}.csv"
PAUSE_SECONDS = 1   # between requests to the reports site
# Reports-site categories for schools, most common first: maintained schools,
# academies, special and free schools, then FE colleges.
PROVIDER_CATEGORIES = (21, 23, 25, 22, 27, 39)

OEIF_GRADES = {"1": "Outstanding", "2": "Good", "3": "Requires improvement", "4": "Inadequate"}
OEIF_AREAS = (
    ("Quality of education", "Latest OEIF quality of education"),
    ("Behaviour and attitudes", "Latest OEIF behaviour and attitudes"),
    ("Personal development", "Latest OEIF personal development"),
    ("Leadership and management", "Latest OEIF effectiveness of leadership and management"),
    ("Early years provision", "Latest OEIF early years provision (where applicable)"),
    ("Sixth form provision", "Latest OEIF sixth form provision (where applicable)"),
)
CARD_AREAS = (
    ("Inclusion", "Inclusion"),
    ("Curriculum and teaching", "Curriculum and teaching"),
    ("Achievement", "Achievement"),
    ("Attendance and behaviour", "Attendance and behaviour"),
    ("Personal development and wellbeing", "Personal development and wellbeing"),
    ("Early years", "Early years (where applicable)"),
    ("Post-16 provision", "Post-16 provision (where applicable)"),
    ("Leadership and governance", "Leadership and governance"),
)
# Single-word overall grades, as the reports site and the MI word them
# ("Satisfactory" was the third grade until 2012).
OVERALL_GRADES = ("Outstanding", "Good", "Satisfactory", "Requires improvement", "Inadequate")
# Report card grades, best first; the layout colours and orders by these.
CARD_GRADES = ("Exceptional", "Strong standard", "Expected standard", "Needs attention", "Urgent improvement")
# How far apart the MI and the reports site can date the same inspection
# (one gives the first day of a two-day visit, the other the second).
MATCH_DAYS = 3


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"['’]", "", name.lower())).strip("-")


def long_date(text):
    return datetime.strptime(" ".join(text.split()), "%d %B %Y").date().isoformat()


def mi_date(text):
    text = (text or "").strip()
    if not text or text == "NULL":
        return None
    return datetime.strptime(text, "%d/%m/%Y").date().isoformat()


def mi_value(row, key):
    value = (row.get(key) or "").strip()
    return None if value in ("", "NULL", "Not applicable", "9") else value


# --- Management information ---------------------------------------------------

def latest_mi_url():
    attachments = helper.get(MI_API).json()["details"]["attachments"]
    matches = [a for a in attachments if MI_TITLE in a.get("title", "") and a["url"].endswith(".csv")]
    # Titles end "as at 31 August 2026" (or "31 Oct 2023"); sort on that date.
    def as_at(attachment):
        text = attachment["title"].rsplit("as at ", 1)[1].strip()
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
        return datetime.min
    return max(matches, key=as_at)


def load_mi(urns):
    attachment = latest_mi_url()
    text = helper.get(attachment["url"], timeout=120).content.decode("latin-1")
    rows = {row["URN"]: row for row in csv.DictReader(io.StringIO(text)) if row["URN"] in urns}
    return attachment["title"], rows


def ungraded_outcome(text):
    """'School remains Good (Concerns) - S5 Next' -> 'Remains Good, some concerns'.
    The newer outcomes ('Standards maintained' etc.) are already readable."""
    text = re.sub(r"\s*-\s*S\d Next$", "", text).strip()
    text = re.sub(r"^School remains", "Remains", text)
    text = text.replace(" (Concerns)", ", some concerns").replace(" (Improving)", ", may be improving")
    return text


def mi_summary(row):
    """Report card, latest graded and latest ungraded outcomes from one MI row."""
    report_card = None
    card_date = mi_date(row.get("Inspection start date"))
    if card_date and mi_value(row, "Safeguarding standards"):
        report_card = {
            "date": card_date,
            "published": mi_date(row.get("Publication date")),
            "safeguarding": mi_value(row, "Safeguarding standards"),
            "areas": [
                {"area": label, "grade": mi_value(row, key)}
                for label, key in CARD_AREAS if mi_value(row, key)
            ],
        }

    # Graded inspections from September 2024 have area grades but no overall
    # grade ("Not judged").
    graded = None
    areas = [
        {"area": label, "grade": OEIF_GRADES[mi_value(row, key)]}
        for label, key in OEIF_AREAS if mi_value(row, key) in OEIF_GRADES
    ]
    if areas:
        graded = {
            "date": mi_date(row.get("Inspection start date of latest OEIF graded inspection")),
            "overall": OEIF_GRADES.get(mi_value(row, "Latest OEIF overall effectiveness") or ""),
            "urn": mi_value(row, "URN at time of latest OEIF graded inspection"),
            "areas": areas,
        }

    ungraded = None
    if mi_value(row, "Ungraded inspection overall outcome"):
        ungraded = {
            "date": mi_date(row.get("Date of latest ungraded inspection")),
            "outcome": ungraded_outcome(mi_value(row, "Ungraded inspection overall outcome")),
            "urn": mi_value(row, "URN at time of the ungraded inspection"),
        }

    return report_card, graded, ungraded


def load_predecessors(urns):
    """{urn: [{"urn", "name"}, ...]} of predecessor schools from GIAS, following each chain back
    (a school can have been through more than one conversion or merger)."""
    today = date.today()
    for back in range(7):   # the file is dated; use the newest one there is
        try:
            text = helper.get(GIAS_LINKS_URL.format(date.fromordinal(today.toordinal() - back)), timeout=120).content.decode("latin-1")
            break
        except requests.HTTPError:
            continue
    else:
        return {}
    links = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row["LinkType"].startswith("Predecessor"):
            links.setdefault(row["URN"], []).append({"urn": row["LinkURN"], "name": row["LinkName"].strip()})
    result = {}
    for urn in urns:
        found, queue = [], list(links.get(urn, []))
        while queue:
            old = queue.pop(0)
            if old not in found and old["urn"] != urn:
                found.append(old)
                queue.extend(links.get(old["urn"], []))
        result[urn] = found
    return result


# --- Reports site -------------------------------------------------------------

def provider_page(urn):
    """The provider page URL and HTML for a school URN. The middle number of
    /provider/21/115525 is a category that varies by school type. Ofsted's
    search is no help: childcare providers have numbers that clash with school
    URNs, and closed schools don't appear in it."""
    for category in PROVIDER_CATEGORIES:
        url = f"{REPORTS_URL}/provider/{category}/{urn}"
        try:
            html = helper.get(url).text
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code == 404:
                time.sleep(PAUSE_SECONDS)
                continue
            raise
        time.sleep(PAUSE_SECONDS)
        return url, html
    return None, None


def parse_timeline(soup, urn):
    """Every published report on a provider page, newest first. Pages use
    one of two layouts: the older one shows the overall grade in bold."""
    reports = []
    for day in soup.select("ol.timeline li.timeline__day"):
        for link in day.select("a.publication-link"):
            for hidden in link.select(".nonvisual, .filetype"):
                hidden.decompose()
            date_el = day.select_one(".timeline__date time") or link.find("time")
            if not date_el:
                continue
            visit = long_date(date_el.get_text())
            if link.find("time"):
                link.find("time").decompose()
            strong = link.find("strong")
            outcome = strong.get_text(strip=True) if strong else ""
            if strong:
                strong.decompose()
            published = [t for t in day.find_all("time") if t is not date_el]
            reports.append({
                "date": visit,
                "published": long_date(published[-1].get_text()) if published else None,
                "type": re.sub(r"[\s:()]+$", "", re.sub(r"^[\s:]+", "", link.get_text(" ", strip=True))),
                "outcome": outcome.replace("Requires Improvement", "Requires improvement"),
                "report_url": link.get("href"),
                "urn": urn,
            })
    return reports


def fetch_reports(urn):
    url, html = provider_page(urn)
    if not url:
        return None, []
    return url, parse_timeline(BeautifulSoup(html, "html.parser"), urn)


# --- Combining ----------------------------------------------------------------

def days_apart(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def fill_outcome(reports, when, outcome):
    """Set the outcome on the report closest to `when`, if one is close enough."""
    if not when or not outcome:
        return
    near = [r for r in reports if days_apart(r["date"], when) <= MATCH_DAYS]
    if near and not near[0]["outcome"]:
        near[0]["outcome"] = outcome


def build_record(school, row, old_schools, previous):
    urn = school["urn_url"].rstrip("/").rsplit("/", 1)[1]
    report_card, graded, ungraded = mi_summary(row) if row else (None, None, None)

    ofsted_url, reports = fetch_reports(urn)
    if not ofsted_url:
        return None

    # GIAS links first; the MI's "URN at the time" covers any it misses.
    old_schools = list(old_schools)
    for summary in (graded, ungraded):
        if summary and summary["urn"] and summary["urn"] not in [o["urn"] for o in old_schools] + [urn]:
            old_schools.append({"urn": summary["urn"], "name": school["name"]})
    predecessors = []
    for old in old_schools:
        old_url, old_reports = fetch_reports(old["urn"])
        if old_url:
            predecessors.append({**old, "ofsted_url": old_url})
            reports += old_reports

    # Keep grades captured on earlier runs, then fill any gaps from the MI.
    kept = {r["report_url"]: r["outcome"] for r in (previous or {}).get("inspections", []) if r["outcome"]}
    for report in reports:
        if not report["outcome"] and report["report_url"] in kept:
            report["outcome"] = kept[report["report_url"]]
    if graded:
        fill_outcome(reports, graded["date"], graded["overall"] or "Graded by area")
    if ungraded:
        fill_outcome(reports, ungraded["date"], ungraded["outcome"])
    if report_card:
        fill_outcome(reports, report_card["date"], "Report card")

    if not reports:
        return None
    return summarise({
        "urn": urn,
        "name": school["name"],
        "slug": slugify(school["name"]),
        "phase": school["phase"],
        "type": school["type"],
        "ofsted_url": ofsted_url,
        "predecessors": predecessors,
        "report_card": report_card,
        "graded": graded,
        "ungraded": ungraded,
        "inspections": reports,
    })


def summarise(record):
    """Sort the reports and add the fields the pages show at a glance."""
    names = {record["urn"]: record["name"], **{p["urn"]: p["name"] for p in record["predecessors"]}}
    reports = sorted(record["inspections"], key=lambda r: r["date"], reverse=True)
    for report in reports:
        report["school"] = names.get(report["urn"], record["name"])
    rated = [r for r in reports if r["outcome"]]
    record["inspections"] = reports
    record["rated_count"] = len(rated)
    record["latest_rated"] = rated[0] if rated else None
    overall = [r for r in rated if r["outcome"] in OVERALL_GRADES]
    record["last_overall"] = overall[0] if overall else None
    record["first_year"] = reports[-1]["date"][:4]
    return record


def main():
    with open(SCHOOLS, encoding="utf-8") as f:
        schools = json.load(f)
    previous = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            previous = json.load(f).get("schools", {})

    urns = {s["urn_url"].rstrip("/").rsplit("/", 1)[1] for s in schools}
    mi_title, mi_rows = load_mi(urns)
    predecessors = load_predecessors(urns)

    results = {}
    for school in schools:
        urn = school["urn_url"].rstrip("/").rsplit("/", 1)[1]
        try:
            record = build_record(school, mi_rows.get(urn), predecessors.get(urn, []), previous.get(urn))
        except requests.RequestException as error:
            print(f"Skipped {school['name']}: {error}")
            record = previous.get(urn)   # keep last month's rather than drop it
        if record:
            results[urn] = record

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Ofsted",
        "source_url": REPORTS_URL,
        "mi_title": mi_title,
        "mi_url": MI_PAGE,
        "licence": "Open Government Licence v3.0",
        "card_grades": list(CARD_GRADES),
        "schools": dict(sorted(results.items(), key=lambda kv: kv[1]["name"])),
    }
    helper.write_json(OUT, output)
    print(f"Wrote Ofsted inspections for {len(results)} of {len(schools)} schools to {OUT}")


if __name__ == "__main__":
    main()
