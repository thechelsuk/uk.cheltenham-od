#!/usr/bin/env python3
"""Fetch the site's own traffic for the last 30 complete days from Cloudflare's
GraphQL Analytics API and write _data/traffic.json.

Refreshed daily so the page is always a rolling 30 days. Cloudflare reports each
day as a whole, so today is left out until it has finished.

Unique visitors for the 30 days is Cloudflare's own count across the whole period,
so someone who visits on several days is counted once. It is not the sum of the
daily figures. Percent cached is the share of bytes served from cache, which is
how the Cloudflare dashboard works it out.

Needs two environment variables (repository secrets in GitHub Actions, or in the
gitignored .env file when running locally):
  CLOUDFLARE_API_TOKEN  a token with the Zone > Analytics > Read permission
  CLOUDFLARE_ZONE_ID    the zone ID shown on the site's Cloudflare overview page
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

import config

# Load .env file for local development if present
import helper

# Load .env file for local development if present
_env_file = helper.repo_root() / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "_data", "traffic.json")

SOURCE_URL = "https://developers.cloudflare.com/analytics/graphql-api/"
ENDPOINT = "https://api.cloudflare.com/client/v4/graphql"
DAYS = 30

QUERY = """
query Traffic($zone: String!, $start: Date!, $end: Date!) {
  viewer {
    zones(filter: {zoneTag: $zone}) {
      days: httpRequests1dGroups(limit: 40, orderBy: [date_ASC],
                                  filter: {date_geq: $start, date_leq: $end}) {
        dimensions { date }
        sum { requests bytes cachedBytes }
        uniq { uniques }
      }
      period: httpRequests1dGroups(limit: 1, filter: {date_geq: $start, date_leq: $end}) {
        sum { requests bytes cachedBytes }
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
        sent = g["sum"]["bytes"] if g else 0
        cached = g["sum"]["cachedBytes"] if g else 0
        days.append({
            "date": iso,
            "requests": g["sum"]["requests"] if g else 0,
            "cached_percent": percent(cached, sent),
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
        headers={**config.HEADERS, "Authorization": f"Bearer {token}"},
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

    days = build_days(zones[0]["days"], start, end)
    period = zones[0]["period"][0]
    uniques_total = period["uniq"]["uniques"]
    requests_total = period["sum"]["requests"]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Cloudflare",
        "source_url": SOURCE_URL,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "totals": {
            "uniques": uniques_total,
            "display_uniques": f"{uniques_total:,}",
            "requests": requests_total,
            "display_requests": f"{requests_total:,}",
            "cached_percent": percent(period["sum"]["cachedBytes"], period["sum"]["bytes"]),
        },
        "days": days,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(days)} days ({start} to {end}) to {OUT}")


if __name__ == "__main__":
    main()
