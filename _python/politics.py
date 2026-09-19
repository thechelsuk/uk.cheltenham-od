#!/usr/bin/env python3
"""Fetch Cheltenham's current MP and its general election results since 2010
from the UK Parliament Members API (no key needed) and write
_data/politics.json.

The API holds two Cheltenham constituency records: 3406 (the 2010-2024
boundaries) and 3976 (created by the 2024 boundary review). Both are read and
merged so the history runs unbroken. If the boundaries are redrawn again,
add the new constituency ID to CONSTITUENCY_IDS.

MPs only change at elections and by-elections, so a monthly refresh is plenty.
"""
import json
import os
import re
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "politics.json")

API = "https://members-api.parliament.uk/api"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

CONSTITUENCY_IDS = [3976, 3406]   # current boundaries first
PROFILE_URL = "https://members.parliament.uk/member/{id}/contact"


def get(path):
    resp = requests.get(f"{API}/{path}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()["value"]


def display(n):
    """7210 -> '7,210'. Layouts print *_display fields rather than formatting in Liquid."""
    return f"{n:,}" if n is not None else ""


def iso_date(text):
    """'2024-07-04T00:00:00' -> '2024-07-04' (None stays None)."""
    return text[:10] if text else None


def strip_html(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def mp_for(date, terms):
    """The MP whose term covers an election date (terms are ISO date strings)."""
    for term in terms:
        if term["from"] <= date and (term["to"] is None or date <= term["to"]):
            return term
    return None


def main():
    terms, results = [], []
    for constituency_id in CONSTITUENCY_IDS:
        for rep in get(f"Location/Constituency/{constituency_id}/Representations"):
            member, span = rep["member"]["value"], rep["representation"]
            terms.append({
                "id": member["id"],
                "name": member["nameDisplayAs"],
                "party": member["latestParty"]["name"],
                "from": iso_date(span["membershipStartDate"]),
                "to": iso_date(span.get("membershipEndDate")),
            })
        results.extend(get(f"Location/Constituency/{constituency_id}/ElectionResults"))

    elections = []
    for result in results:
        if not result.get("isGeneralElection"):
            continue
        date = iso_date(result["electionDate"])
        electorate, votes_cast = result.get("electorate"), result.get("turnout")
        turnout_pct = round(votes_cast / electorate * 100, 1) if electorate and votes_cast else None
        term = mp_for(date, terms)
        elections.append({
            "date": date,
            "title": result["electionTitle"],
            "mp": term["name"] if term else "",
            "party": result["winningParty"]["name"],
            "result": result.get("result", ""),
            "majority": result.get("majority"),
            "majority_display": display(result.get("majority")),
            "electorate": electorate,
            "electorate_display": display(electorate),
            "votes_cast": votes_cast,
            "votes_cast_display": display(votes_cast),
            "turnout_pct": turnout_pct,
            "turnout_display": f"{turnout_pct}%" if turnout_pct is not None else "",
        })
    elections.sort(key=lambda e: e["date"], reverse=True)

    current = next(t for t in terms if t["to"] is None)
    member = get(f"Members/{current['id']}")
    synopsis = strip_html(get(f"Members/{current['id']}/Synopsis"))

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "UK Parliament Members API",
        "source_url": "https://members-api.parliament.uk/",
        "licence": "Open Parliament Licence v3.0",
        "current_mp": {
            "id": current["id"],
            "name": member["nameDisplayAs"],
            "party": member["latestParty"]["name"],
            "constituency": member["latestHouseMembership"]["membershipFrom"],
            "since": current["from"],
            "synopsis": synopsis,
            "profile_url": PROFILE_URL.format(id=current["id"]),
        },
        "elections": elections,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote current MP {member['nameDisplayAs']} and {len(elections)} elections to {OUT}")


if __name__ == "__main__":
    main()
