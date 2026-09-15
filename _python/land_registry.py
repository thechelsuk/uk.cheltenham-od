#!/usr/bin/env python3
"""
extract_house_prices.py

Single responsibility: pull Cheltenham transactions from the HM Land
Registry SPARQL endpoint and write them to _data/ as raw JSON.

Does NOT compute stats, does NOT touch markdown, does NOT format anything
for display. That's build_house_summary.py's job, which reads the file
this script writes.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
MONTHS = 48
DRY_RUN = False
JSON_DATA_PATH = Path("_data/cheltenham-house-prices.json")
# ---------------------------------------------------------------------------

ENDPOINT = "https://landregistry.data.gov.uk/landregistry/query"
TIMEOUT_SECONDS = 90  # bumped from 30 - 48mo scan is heavier than 24mo
CHELTENHAM_POSTCODE_DISTRICTS = ["GL50", "GL51", "GL52", "GL53", "GL54"]
PAGE_SIZE = 2000


def _common_where(months: int) -> tuple[str, str]:
    postcode_filters = " || ".join(f'STRSTARTS(?postcode, "{d}")' for d in CHELTENHAM_POSTCODE_DISTRICTS)
    threshold_date = (datetime.now(timezone.utc) - timedelta(days=months * 30)).strftime("%Y-%m-%d")
    return postcode_filters, threshold_date


def build_count_query(months: int) -> str:
    postcode_filters, threshold_date = _common_where(months)
    return f"""
PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>

SELECT (COUNT(*) AS ?n)
WHERE {{
  ?transx lrppi:pricePaid ?amount ;
          lrppi:transactionDate ?date ;
          lrppi:propertyAddress ?addr .
  ?addr lrcommon:town ?town ;
        lrcommon:postcode ?postcode .
  FILTER (?town = "CHELTENHAM")
  FILTER ({postcode_filters})
  FILTER (?date >= "{threshold_date}"^^<http://www.w3.org/2001/XMLSchema#date>)
}}
"""


def build_query(months: int, limit: int, offset: int) -> str:
    postcode_filters, threshold_date = _common_where(months)
    return f"""
PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>

SELECT ?paon ?saon ?street ?town ?postcode ?amount ?date ?propertyTypeLabel ?newBuild
WHERE {{
  ?transx lrppi:pricePaid ?amount ;
          lrppi:transactionDate ?date ;
          lrppi:propertyAddress ?addr .
  ?addr lrcommon:town ?town ;
        lrcommon:postcode ?postcode .
  OPTIONAL {{ ?addr lrcommon:paon ?paon }}
  OPTIONAL {{ ?addr lrcommon:saon ?saon }}
  OPTIONAL {{ ?addr lrcommon:street ?street }}
  OPTIONAL {{ ?transx lrppi:propertyType ?propertyTypeUri .
             ?propertyTypeUri <http://www.w3.org/2000/01/rdf-schema#label> ?propertyTypeLabel }}
  OPTIONAL {{ ?transx lrppi:newBuild ?newBuild }}
  FILTER (?town = "CHELTENHAM")
  FILTER ({postcode_filters})
  FILTER (?date >= "{threshold_date}"^^<http://www.w3.org/2001/XMLSchema#date>)
}}
ORDER BY DESC(?date)
LIMIT {limit}
OFFSET {offset}
"""


def _run_query(query: str) -> dict:
    resp = requests.get(
        ENDPOINT,
        params={"query": query, "output": "json"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()


def get_true_count(months: int) -> int:
    data = _run_query(build_count_query(months))
    bindings = data.get("results", {}).get("bindings", [])
    n = int(bindings[0]["n"]["value"]) if bindings else 0
    print(f"COUNT check: {n} true matching rows for the last {months} months.")
    return n


def _rows_to_transactions(bindings: list[dict]) -> list[dict]:
    transactions = []
    for row in bindings:
        def val(key):
            return row.get(key, {}).get("value")

        transactions.append({
            "paon": val("paon"),
            "saon": val("saon"),
            "street": val("street"),
            "town": val("town"),
            "postcode": val("postcode"),
            "amount": int(float(val("amount"))) if val("amount") else None,
            "display_amount": f"£{int(float(val('amount'))):,}" if val("amount") else "",
            "date": val("date"),
            "property_type": (
                "Other" if not val("propertyTypeLabel") or val("propertyTypeLabel").strip().lower() == "other"
                else val("propertyTypeLabel").strip()
            ),
            "new_build": val("newBuild") == "true",
        })
    return transactions


def fetch_transactions(months: int, expected_count: int | None = None) -> list[dict]:
    all_transactions: list[dict] = []
    offset = 0
    while True:
        query = build_query(months, limit=PAGE_SIZE, offset=offset)
        data = _run_query(query)
        bindings = data.get("results", {}).get("bindings", [])
        if not bindings:
            break
        all_transactions.extend(_rows_to_transactions(bindings))
        print(f"Fetched page at offset {offset}: {len(bindings)} rows (running total {len(all_transactions)}).")
        if len(bindings) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    if not all_transactions:
        print("WARNING: query returned zero rows. Check filters/date range.", file=sys.stderr)

    if expected_count is not None and len(all_transactions) != expected_count:
        print(
            f"WARNING: fetched {len(all_transactions)} rows but COUNT query reported "
            f"{expected_count}. Results may be inconsistent.",
            file=sys.stderr,
        )

    return all_transactions


def write_json(transactions: list[dict], months: int, dry_run: bool) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "months_fetched": months,
        "transactions": transactions,
    }
    if dry_run:
        print(f"--- DRY RUN: would write {JSON_DATA_PATH} ({len(transactions)} records) ---")
        return
    JSON_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_DATA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {JSON_DATA_PATH} ({len(transactions)} records)")


def main():
    print(f"Checking true row count for last {MONTHS} months...")
    true_count = get_true_count(MONTHS)

    print(f"Fetching Cheltenham transactions from last {MONTHS} months...")
    transactions = fetch_transactions(MONTHS, expected_count=true_count)
    print(f"Retrieved {len(transactions)} transactions (COUNT query reported {true_count}).")

    write_json(transactions, MONTHS, DRY_RUN)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as exc:
        # The Land Registry SPARQL endpoint is occasionally unavailable
        # (rate limiting, maintenance, a stray 403). Treat that as a soft
        # failure rather than a build error: log it clearly and leave
        # JSON_DATA_PATH untouched so the site keeps serving the last
        # good fetch until the next scheduled run succeeds.
        print(f"::warning::land_registry.py: SPARQL request failed ({exc}); "
              f"leaving {JSON_DATA_PATH} unchanged", file=sys.stderr)