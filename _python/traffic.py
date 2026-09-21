#!/usr/bin/env python3
"""Fetch the site's own traffic for the last 30 complete days from Cloudflare's
GraphQL Analytics API and write _data/traffic.json.

Refreshed daily so the page is always a rolling 30 days. Cloudflare reports each
day as a whole, so today is left out until it has finished.

Needs two environment variables (repository secrets in GitHub Actions):
  CLOUDFLARE_API_TOKEN  a token with the Zone > Analytics > Read permission
  CLOUDFLARE_ZONE_ID    the zone ID shown on the site's Cloudflare overview page
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "traffic.json")

SOURCE_URL = "https://developers.cloudflare.com/analytics/graphql-api/"
ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}
DAYS = 30

QUERY = """
query Traffic($zone: String!, $start: Date!, $end: Date!) {
  viewer {
    zones(filter: {zoneTag: $zone}) {
      httpRequests1dGroups(limit: 40, orderBy: [date_ASC],
                           filter: {date_geq: $start, date_leq: $end}) {
        dimensions { date }
        sum { requests cachedRequests }
        uniq { uniques }
      }
    }
  }
}
"""


def percent(part, whole):
    return round(part * 100 / whole, 1) if whole else 0.0


def build_days(groups, start, end):
    """One entry for every date from start to end. A date Cloudflare has no row for is zero."""
    by_date = {g["dimensions"]["date"]: g for g in groups}
    days, day = [], start
    while day <= end:
        iso = day.isoformat()
        g = by_date.get(iso)
        requests_total = g["sum"]["requests"] if g else 0
        cached = g["sum"]["cachedRequests"] if g else 0
        days.append({
            "date": iso,
            "requests": requests_total,
            "cached_requests": cached,
            "cached_percent": percent(cached, requests_total),
            "uniques": g["uniq"]["uniques"] if g else 0,
        })
        day += timedelta(days=1)
    return days


def main():
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    zone = os.environ.get("CLOUDFLARE_ZONE_ID")
    if not token or not zone:
        sys.exit("Set CLOUDFLARE_API_TOKEN and CLOUDFLARE_ZONE_ID to fetch traffic figures.")

    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    start = end - timedelta(days=DAYS - 1)

    resp = requests.post(
        ENDPOINT,
        headers={**HEADERS, "Authorization": f"Bearer {token}"},
        json={"query": QUERY, "variables": {"zone": zone, "start": start.isoformat(), "end": end.isoformat()}},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        sys.exit(f"Cloudflare returned an error: {body['errors'][0].get('message')}")
    zones = body["data"]["viewer"]["zones"]
    if not zones:
        sys.exit("Cloudflare returned no zone for that ID and token.")

    days = build_days(zones[0]["httpRequests1dGroups"], start, end)
    requests_total = sum(d["requests"] for d in days)
    cached_total = sum(d["cached_requests"] for d in days)
    uniques_total = sum(d["uniques"] for d in days)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Cloudflare",
        "source_url": SOURCE_URL,
        "licence": "The site's own traffic figures; no open licence applies",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "totals": {
            "uniques": uniques_total,
            "display_uniques": f"{uniques_total:,}",
            "average_uniques": round(uniques_total / len(days)),
            "display_average_uniques": f"{round(uniques_total / len(days)):,}",
            "requests": requests_total,
            "display_requests": f"{requests_total:,}",
            "cached_requests": cached_total,
            "cached_percent": percent(cached_total, requests_total),
        },
        "days": [
            {**d,
             "display_uniques": f"{d['uniques']:,}",
             "display_requests": f"{d['requests']:,}"}
            for d in days
        ],
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(days)} days ({start} to {end}) to {OUT}")


if __name__ == "__main__":
    main()
