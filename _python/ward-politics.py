#!/usr/bin/env python3
"""Fetch ward-level politics for Cheltenham and write _data/ward-politics.json.

Both sources are Cheltenham Borough Council's own modern.gov site, so the
figures are the council's published results rather than a re-published copy:

* Election results by ward (candidates, votes, electorate, ballots issued,
  seats) scraped from the council's per-ward results pages, which are listed
  under each election's "results by wards" page.
* Sitting councillors and their party by ward from the council's modern.gov
  web service, which reflects by-elections and changes of party.

Cheltenham's wards were redrawn in 2024, so only elections since then are
comparable. Add each new election to ELECTIONS once it has been held: the ID is
the "ID=" in its link on https://democracy.cheltenham.gov.uk/mgManageElectionResults.aspx.
The council elects by halves, so most ward contests after 2024 are for one seat.

The results pages are HTML, not an API, so the parser is deliberately strict
and fails loudly if a page's tables change shape. Requests are spaced out to be
kind to the council's server. Councillors change rarely and elections happen
in May, so a monthly refresh is plenty.
"""
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "ward-politics.json")

BASE = "https://democracy.cheltenham.gov.uk/"
RESULTS_INDEX = BASE + "mgManageElectionResults.aspx"
AREAS_URL = BASE + "mgElectionElectionAreaResults.aspx?Page=all&EID={id}"
WARD_URL = BASE + "mgElectionAreaResults.aspx?XXR=0&ID={id}&RPID=0"
COUNCILLORS_URL = BASE + "mgWebService.asmx/GetCouncillorsByWard"
PROFILE_URL = BASE + "mgUserInfo.aspx?UID={id}"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}
PAUSE_SECONDS = 1

ELECTIONS = [
    {"id": 21, "date": "2024-05-02", "title": "2024 borough election"},
    {"id": 23, "date": "2025-05-01", "title": "2025 Charlton Kings by-election"},
    {"id": 24, "date": "2026-05-07", "title": "2026 borough election"},
]

PARTIES = {
    "Liberal Democrats": "Liberal Democrat",
    "The Conservative Party Candidate": "Conservative",
    "Conservative and Unionist Party": "Conservative",
    "Labour Party": "Labour",
    "Labour and Co-operative Party": "Labour and Co-operative",
    "Green Party": "Green",
    "People Against Bureaucracy Group": "People Against Bureaucracy",
}


def party_name(name):
    return PARTIES.get(name.strip(), name.strip())


def slugify(name):
    """'St. Marks' -> 'st-marks'; drops 'and'/'&' so the Benhall ward matches the
    slug used in _data/wards/ ('benhall-the-reddings-fiddlers-green')."""
    name = re.sub(r"\band\b|&", " ", name.lower().replace("'", "").replace("’", ""))
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-")


def get(url):
    time.sleep(PAUSE_SECONDS)
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp


def number(text):
    return int(re.sub(r"[^\d]", "", text))


def parse_ward_page(html):
    """One ward's results page -> (candidates, summary dict keyed by lowercase label)."""
    soup = BeautifulSoup(html, "html.parser")
    results = soup.find("table", summary="Table of results for Wards ")
    summary = soup.find("table", summary="Voting summary table")
    if results is None or summary is None:
        raise RuntimeError("results tables not found; the page layout has changed")
    candidates = []
    for row in results.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 5:
            continue
        candidates.append({"name": cells[0], "party": party_name(cells[1]), "votes": number(cells[2]),
                           "elected": cells[4].strip().lower() == "elected"})
    facts = {}
    for row in summary.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) == 2 and cells[0]:
            facts[cells[0].lower()] = cells[1]
    if not candidates or "electorate" not in facts:
        raise RuntimeError("no candidates or electorate found on the page")
    return candidates, facts


def fetch_election(election):
    """One election -> {slug: result dict}, one council page per ward."""
    soup = BeautifulSoup(get(AREAS_URL.format(id=election["id"])).text, "html.parser")
    wards = {}
    for a in soup.find_all("a", href=re.compile(r"mgElectionAreaResults\.aspx")):
        area_id = re.search(r"ID=(\d+)", a["href"]).group(1)
        ward_name = a.get_text(strip=True)
        page_url = WARD_URL.format(id=area_id)
        candidates, facts = parse_ward_page(get(page_url).text)
        total = sum(c["votes"] for c in candidates)
        if total != number(facts["total votes"]):
            print(f"WARNING: {ward_name} {election['date']}: candidate votes add up to {total} but the page says {facts['total votes']}")
        if sum(c["elected"] for c in candidates) != number(facts["seats"]):
            print(f"WARNING: {ward_name} {election['date']}: number elected does not match seats")
        electorate = number(facts["electorate"])
        issued = number(facts["number of ballot papers issued"])
        for c in candidates:
            c["votes_display"] = f"{c['votes']:,}"
            c["share"] = round(100 * c["votes"] / total, 1) if total else 0
        wards[slugify(ward_name)] = {
            "date": election["date"],
            "title": election["title"],
            "seats": number(facts["seats"]),
            "electorate": electorate,
            "electorate_display": f"{electorate:,}",
            "ballots_cast": issued,
            "ballots_cast_display": f"{issued:,}",
            "turnout_pct": round(100 * issued / electorate, 2) if electorate else None,
            "spoilt": number(facts.get("number of ballot papers rejected", "0")),
            "total_votes": total,
            "source_url": page_url,
            "candidates": sorted(candidates, key=lambda c: -c["votes"]),
        }
    if not wards:
        raise RuntimeError(f"no ward links found for election {election['id']}")
    return wards


def fetch_councillors():
    """Current councillors -> {slug: [{name, party, url}]}."""
    root = ET.fromstring(get(COUNCILLORS_URL).content)
    by_slug = {}
    for ward in root.iter("ward"):
        people = []
        for c in ward.iter("councillor"):
            name = re.sub(r"\s+", " ", (c.findtext("fullusername") or "").replace("Councillor ", "", 1)).strip()
            people.append({
                "name": name,
                "party": party_name(c.findtext("politicalpartytitle") or ""),
                "url": PROFILE_URL.format(id=c.findtext("councillorid")),
            })
        by_slug[slugify(ward.findtext("wardtitle") or "")] = sorted(people, key=lambda p: p["name"].split()[-1])
    return by_slug


def summary(people):
    """'2 Liberal Democrat' / '1 Green, 1 Reform UK'."""
    counts = {}
    for p in people:
        counts[p["party"]] = counts.get(p["party"], 0) + 1
    return ", ".join(f"{n} {party}" for party, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def election_summaries(results):
    """Council-wide totals for each election: seats and votes by party, turnout."""
    out = []
    for election in ELECTIONS:
        rows = [e for elections in results.values() for e in elections if e["date"] == election["date"]]
        seats, votes = {}, {}
        for e in rows:
            for c in e["candidates"]:
                votes[c["party"]] = votes.get(c["party"], 0) + c["votes"]
                if c["elected"]:
                    seats[c["party"]] = seats.get(c["party"], 0) + 1
        total = sum(votes.values())
        electorate = sum(e["electorate"] for e in rows)
        issued = sum(e["ballots_cast"] for e in rows)
        out.append({
            "date": election["date"],
            "title": election["title"],
            "wards": len(rows),
            "seats": sum(seats.values()),
            "electorate": electorate,
            "electorate_display": f"{electorate:,}",
            "ballots_cast": issued,
            "ballots_cast_display": f"{issued:,}",
            "turnout_pct": round(100 * issued / electorate, 1) if electorate else None,
            "parties": [
                {"party": p, "seats": seats.get(p, 0), "votes": votes[p], "votes_display": f"{votes[p]:,}",
                 "share": round(100 * votes[p] / total, 1) if total else 0}
                for p in sorted(votes, key=lambda p: (-seats.get(p, 0), -votes[p]))
            ],
        })
    return out


def council_composition(wards):
    """Current seats by party across all wards, from the sitting councillors."""
    counts = {}
    for w in wards.values():
        for c in w["councillors"]:
            counts[c["party"]] = counts.get(c["party"], 0) + 1
    total = sum(counts.values())
    return {"total": total,
            "parties": [{"party": p, "seats": n, "share": round(100 * n / total, 1)}
                        for p, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]}


def wards_summary(wards):
    """Compact per-ward rows for the map: who sits there and which party holds the ward."""
    rows = []
    for slug, w in sorted(wards.items()):
        parties = {c["party"] for c in w["councillors"]}
        rows.append({"slug": slug,
                     "party": next(iter(parties)) if len(parties) == 1 else "Split",
                     "councillors": [{"name": c["name"], "party": c["party"]} for c in w["councillors"]]})
    return rows


def main():
    results = {}
    for election in ELECTIONS:
        for slug, result in fetch_election(election).items():
            results.setdefault(slug, []).append(result)
    councillors = fetch_councillors()

    wards = {}
    for slug, elections in sorted(results.items()):
        people = councillors.get(slug, [])
        wards[slug] = {
            "councillors": people,
            "councillors_display": summary(people),
            "elections": sorted(elections, key=lambda e: e["date"], reverse=True),
        }

    parties = sorted({c["party"] for w in wards.values() for e in w["elections"] for c in e["candidates"]})
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Cheltenham Borough Council",
        "source_url": RESULTS_INDEX,
        "councillors_source_url": BASE + "mgFindMember.aspx",
        "licence": "None stated on the council's election results pages",
        "elections": [{"date": e["date"], "title": e["title"]} for e in ELECTIONS],
        "parties": parties,
        "council": council_composition(wards),
        "election_summaries": election_summaries(results),
        "wards_summary": wards_summary(wards),
        "wards": wards,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")
    missing = [s for s, w in wards.items() if not w["councillors"]]
    print(f"Wrote {len(wards)} wards to {OUT}" + (f"; no councillors matched for {missing}" if missing else ""))
    print("Parties:", ", ".join(parties))


if __name__ == "__main__":
    main()
