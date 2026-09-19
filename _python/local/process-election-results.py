#!/usr/bin/env python3
"""Build Cheltenham's general election history since 1918 from the House of
Commons Library's election datasets, write _data/election-results.json.

Run manually after saving the source files into _data-sources/ — not part of
any scheduled workflow, since those gitignored inputs only exist locally (the
Commons Library file host blocks scripted downloads). The 1918-2019 results
never change; re-run only after a new general election, once the Library
publishes that election's dataset:

  1918-2019election_results.csv       https://commonslibrary.parliament.uk/research-briefings/cbp-8647/
  HoC-GE2024-results-by-candidate.csv https://commonslibrary.parliament.uk/research-briefings/cbp-10009/

The 1918-2019 file is by constituency with four fixed vote groups (Con, Lib,
Lab and Others) and no party names, candidate names or dates, so:
  - election dates come from _data/general-election-dates.json
  - the "Lib" group is the Liberal Party, the SDP-Liberal Alliance and the
    Liberal Democrats, named per year in liberal_name()
  - a group's winner is only named when it beats the whole Others group
The 2024 file is by candidate, so its rows are folded into the same four
groups. 2024's electorate comes from _data/politics.json (run politics.py
first); the candidate file doesn't carry it.
"""
import csv
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))            # _python/local/
ROOT = os.path.join(HERE, "..", "..")
SRC_HISTORIC = os.path.join(ROOT, "_data-sources", "1918-2019election_results.csv")
SRC_2024 = os.path.join(ROOT, "_data-sources", "HoC-GE2024-results-by-candidate.csv")
DATES = os.path.join(ROOT, "_data", "general-election-dates.json")
POLITICS = os.path.join(ROOT, "_data", "politics.json")
OUT = os.path.join(ROOT, "_data", "election-results.json")

CONSTITUENCY = "Cheltenham"
GROUPS = [("con", "Conservative"), ("lib", "Liberal / Alliance / Lib Dem"), ("lab", "Labour"), ("oth", "Others")]


def display(n):
    return f"{n:,}" if n is not None else ""


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def liberal_name(year):
    """The Liberal group's party name at the time."""
    if year <= 1979:
        return "Liberal"
    if year <= 1987:
        return "SDP–Liberal Alliance"
    return "Liberal Democrat"


def winner_name(votes, year):
    """Name the winning group, or 'Others' when the Others group out-polled every
    named party (it can hold several candidates, so its winner isn't knowable)."""
    named = {g: votes[g] or 0 for g in ("con", "lib", "lab")}
    top = max(named, key=named.get)
    if (votes["oth"] or 0) > named[top]:
        return "Others"
    return {"con": "Conservative", "lab": "Labour", "lib": liberal_name(year)}[top]


def build_parties(votes, total):
    parties = []
    for key, name in GROUPS:
        v = votes[key]
        parties.append({
            "id": key,
            "name": name,
            "votes": v,
            "votes_display": display(v),
            "share_display": f"{v / total * 100:.1f}%" if v is not None and total else "",
        })
    return parties


def historic_rows(dates):
    with open(SRC_HISTORIC, encoding="cp1252", newline="") as f:      # not UTF-8
        rows = [{k.strip(): v for k, v in r.items()} for r in csv.DictReader(f)]
    items = []
    for r in rows:
        if r["constituency_name"].strip().lower() != CONSTITUENCY.lower():
            continue
        key = r["election"].strip()
        votes = {"con": num(r["con_votes"]), "lib": num(r["lib_votes"]), "lab": num(r["lab_votes"])}
        others = [num(r["oth_votes"]), num(r["natSW_votes"])]
        votes["oth"] = sum(v for v in others if v) or None
        votes = {k: int(v) if v is not None else None for k, v in votes.items()}
        total = int(num(r["total_votes"]))
        electorate = int(num(r["electorate"]))
        turnout = round(num(r["turnout"]) * 100, 1)
        year = int(key[:4])
        items.append({
            "key": key,
            "date": dates[key],
            "winner": winner_name(votes, year),
            "electorate": electorate,
            "electorate_display": display(electorate),
            "turnout_pct": turnout,
            "turnout_display": f"{turnout}%",
            "total_votes": total,
            "parties": build_parties(votes, total),
        })
    return items


def election_2024(dates):
    with open(SRC_2024, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["Constituency name"].strip().lower() == CONSTITUENCY.lower()]
    if not rows:
        raise SystemExit("Cheltenham not found in the 2024 candidate file")

    votes = {"con": None, "lib": None, "lab": None, "oth": None}
    party_of = {"Conservative": "con", "Liberal Democrat": "lib", "Labour": "lab"}
    for r in rows:
        group = party_of.get(r["Party name"].strip(), "oth")
        votes[group] = (votes[group] or 0) + int(r["Votes"])
    total = sum(int(r["Votes"]) for r in rows)
    winner = max(rows, key=lambda r: int(r["Votes"]))["Party name"].strip()

    electorate = turnout = None
    if os.path.exists(POLITICS):
        with open(POLITICS, encoding="utf-8") as f:
            for e in json.load(f)["elections"]:
                if e["date"] == dates["2024"]:
                    electorate, turnout = e["electorate"], e["turnout_pct"]
    if electorate is None:
        print("Warning: 2024 electorate not found in _data/politics.json — run politics.py first")

    return {
        "key": "2024",
        "date": dates["2024"],
        "winner": winner,
        "electorate": electorate,
        "electorate_display": display(electorate),
        "turnout_pct": turnout,
        "turnout_display": f"{turnout}%" if turnout is not None else "",
        "total_votes": total,
        "parties": build_parties(votes, total),
    }


def main():
    with open(DATES, encoding="utf-8") as f:
        dates = json.load(f)["dates"]

    items = historic_rows(dates) + [election_2024(dates)]
    items.sort(key=lambda i: i["date"], reverse=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "House of Commons Library, general election results by constituency",
        "source_url": "https://commonslibrary.parliament.uk/research-briefings/cbp-8647/",
        "source_url_2024": "https://commonslibrary.parliament.uk/research-briefings/cbp-10009/",
        "licence": "Open Parliament Licence v3.0",
        "groups": [{"id": k, "name": n} for k, n in GROUPS],
        "items": items,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(items)} elections ({items[-1]['date'][:4]}-{items[0]['date'][:4]}) to {OUT}")


if __name__ == "__main__":
    main()
