#!/usr/bin/env python3
"""Fetch Cheltenham Town FC's next fixture(s) and recent results from
TheSportsDB's free public API, write _data/cheltenham-town-fc.json.
Fixtures/results change with every match, so this runs daily.

Note: TheSportsDB's free tier (public test key "3") caps eventsnext.php and
eventslast.php at one fixture/result each, regardless of how many exist —
there's no paid key configured, so we store whatever it returns rather than
assuming a fixed count. The page links to the club's own fixtures page for
the full list."""
import json
import os
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "cheltenham-town-fc.json")

API = "https://www.thesportsdb.com/api/v1/json/3"
TEAM_ID = "134362"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}


def get(path, **params):
    resp = requests.get(f"{API}/{path}", params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fixture(event):
    home, away = event.get("strHomeTeam", ""), event.get("strAwayTeam", "")
    is_home = home == "Cheltenham Town"
    return {
        "date":        event.get("dateEvent", ""),
        "time":        event.get("strTimeLocal") or event.get("strTime") or "",
        "opponent":    away if is_home else home,
        "venue_type":  "Home" if is_home else "Away",
        "venue":       event.get("strVenue", ""),
        "competition": event.get("strLeague", ""),
    }


def result(event):
    row = fixture(event)
    row["home_score"] = event.get("intHomeScore")
    row["away_score"] = event.get("intAwayScore")
    return row


def main():
    team = get("searchteams.php", t="Cheltenham Town")["teams"][0]
    next_events = get("eventsnext.php", id=TEAM_ID).get("events") or []
    last_events = get("eventslast.php", id=TEAM_ID).get("results") or []

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "TheSportsDB",
        "source_url": "https://www.thesportsdb.com/",
        "team": {
            "name":    team.get("strTeam", "Cheltenham Town"),
            "badge":   team.get("strBadge", ""),
            "website": "https://" + team["strWebsite"] if team.get("strWebsite") else "",
            "league":  team.get("strLeague", ""),
        },
        "next_fixtures": [fixture(e) for e in next_events],
        "last_results":  [result(e) for e in last_events],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(output['next_fixtures'])} next fixture(s) and "
          f"{len(output['last_results'])} recent result(s) to {OUT}")


if __name__ == "__main__":
    main()
