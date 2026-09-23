import datetime
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
import helper

# -- Configuration ------------------------------------------------------------

CATALOGUE_URL   = "https://data.bus-data.dft.gov.uk/catalogue/"
SOURCE_PAGE     = "https://data.bus-data.dft.gov.uk/"
DISRUPTIONS_CSV = "disruptions_data_catalogue.csv"

# A disruption is "local" if it's published by one of our local authorities,
# or names one of the operators known to serve Cheltenham (see bus-data.py).
AUTHORITY_TERMS = ["gloucestershire", "cheltenham"]
FALLBACK_OPERATOR_TERMS = [
    "stagecoach", "go-ahead", "national express", "marchants",
    "bennetts", "first west of england", "pulham",
    "red & white", "cheltenham & gloucester",
]

# BODS source data is a mix of ALL CAPS and Title Case — normalise to Title Case.
ACRONYMS = {"UK", "LLP", "PLC"}

# History entries are kept for two years, generous for a Cheltenham-only feed.
HISTORY_RETENTION_DAYS = 730


def local_operator_terms():
    """Pull the operator names bus-data.py already identified as serving Cheltenham,
    falling back to a fixed list if that data hasn't been generated yet."""
    bus_routes_path = helper.repo_root() / "_data" / "bus-routes.json"
    if bus_routes_path.exists():
        data = json.loads(bus_routes_path.read_text())
        operators = [o.lower() for o in data.get("operators", [])]
        if operators:
            return operators
    return FALLBACK_OPERATOR_TERMS


def row_is_local(row, operator_terms):
    organisation = (row.get("Organisation") or "").lower()
    operators_affected = (row.get("Operators Affected") or "").lower()
    if any(term in organisation for term in AUTHORITY_TERMS):
        return True
    return any(term in operators_affected for term in operator_terms)


def build_disruption(r):
    d = {
        "organisation":       helper.clean_name(r.get("Organisation") or "", ACRONYMS),
        "situation_number":   r.get("Situation Number") or r.get("ID") or "",
        "validity_start":     r.get("Validity Start Date") or r.get("Validity start") or "",
        "validity_end":       r.get("Validity End Date") or r.get("Validity end") or "",
        "reason":             helper.clean_name(r.get("Reason") or "Unknown", ACRONYMS),
        "planned":            r.get("Planned") or "",
        "modes_affected":     helper.clean_name(r.get("Modes Affected") or r.get("Modes affected") or "", ACRONYMS),
        "operators_affected": helper.clean_name(r.get("Operators Affected") or r.get("Operators affected") or "", ACRONYMS),
        "services_affected":  r.get("Services Affected") or r.get("Services affected") or "",
        "stops_affected":     r.get("Stops Affected") or r.get("Stops affected") or "",
    }
    # A situation number is usually present and unique, but not guaranteed —
    # fall back to a composite key so two different disruptions never collide
    # in the history log.
    d["disruption_id"] = d["situation_number"] or "|".join([
        d["organisation"], d["reason"], d["validity_start"],
    ])
    return d


def build_alert_html(disruptions):
    if not disruptions:
        return ""

    now_str = datetime.datetime.now().strftime("%H:%M")
    items = ""
    for d in disruptions[:5]:
        label = d["operators_affected"] or d["organisation"]
        items += (
            f'  <li><a href="/cheltenham-bus-data">'
            f'Disruption to {label} bus services reported at {now_str}</a></li>\n'
        )
    return (
        "<h2>Bus Disruption Alert</h2>\n"
        "<ul>\n"
        f"{items}"
        "</ul>"
    )


def build_atom_items(history_records, history_url):
    """One entry per disruption, keyed by a stable disruption_id so a feed
    reader treats it as the same item across runs — and dated by
    last_seen_iso, so a disruption ending (once we still see it end) bumps
    its "updated" time rather than the entry silently going stale."""
    items = []
    for record in history_records[:50]:
        label = record.get("operators_affected") or record.get("organisation") or "Cheltenham"
        title = f"{record.get('reason', 'Disruption')}: {label}"
        summary_parts = []
        if record.get("modes_affected"):
            summary_parts.append(f"Modes affected: {record['modes_affected']}")
        if record.get("validity_start"):
            summary_parts.append(f"From: {record['validity_start']}")
        if record.get("validity_end"):
            summary_parts.append(f"To: {record['validity_end']}")
        items.append({
            "title": title,
            "link": f"{history_url}#{record['disruption_id']}",
            "summary": " · ".join(summary_parts) or title,
            "published_iso": record.get("last_seen_iso") or record.get("first_seen_iso"),
            "source": record.get("organisation") or "DfT Bus Open Data Service",
        })
    return items


if __name__ == "__main__":
    root      = helper.repo_root()
    data_dir  = root / "_data"
    feeds_dir = root / "feeds"

    print("Downloading BODS data catalogue...")
    rows = helper.fetch_bods_csv(DISRUPTIONS_CSV, CATALOGUE_URL)
    print(f"  {len(rows):,} total disruptions in national catalogue")

    operator_terms = local_operator_terms()
    local_rows = [r for r in rows if row_is_local(r, operator_terms)]
    print(f"  {len(local_rows)} disruptions affect Cheltenham")

    disruptions = [build_disruption(r) for r in local_rows]

    payload = {
        "updated_iso": datetime.date.today().isoformat(),
        "source": "Bus Open Data Service (Department for Transport)",
        "source_url": SOURCE_PAGE,
        "licence": "Open Government Licence v3.0",
        "refresh": "every 5 minutes",
        "count":       len(disruptions),
        "disruptions": disruptions,
    }

    data_json = data_dir / "bus-disruptions.json"
    helper.write_json(data_json, payload)
    print(f"Wrote {len(disruptions)} disruptions to {data_json}")

    now = datetime.datetime.now(datetime.timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    history_path = data_dir / "bus-disruptions-history.json"
    if history_path.exists():
        history_payload = json.loads(history_path.read_text())
        history_records = history_payload.get("records", [])
    else:
        history_records = []

    history_records = helper.update_history(
        history_records, disruptions, id_key="disruption_id", now_iso=now_iso,
        retention_days=HISTORY_RETENTION_DAYS,
    )
    history_payload = {
        "note": "Rolling log of bus disruptions recorded affecting Cheltenham, built up incrementally "
                "each run — not a full historical archive from before this page existed.",
        "source": "Bus Open Data Service (Department for Transport)",
        "source_url": SOURCE_PAGE,
        "licence": "Open Government Licence v3.0",
        "refresh": "every 5 minutes",
        "count": len(history_records),
        "records": history_records,
    }
    helper.write_json(history_path, history_payload)
    print(f"History now holds {len(history_records)} recorded disruptions")

    site = helper.site_url()
    history_url = f"{site}/cheltenham-bus-data/history"

    atom_path = feeds_dir / "bus-disruptions.xml"
    helper.write_items_atom(
        items=build_atom_items(history_records, history_url),
        filename=atom_path,
        permalink_path="/feeds/bus-disruptions.xml",
        feed_title="Cheltenham Bus Disruptions",
        feed_subtitle="Current and recent bus service disruptions affecting Cheltenham",
        self_url=f"{site}/feeds/bus-disruptions.xml",
        alternate_url=history_url,
    )
    print(f"Atom feed saved to {atom_path}")

    # Homepage alert — only appears while a disruption is live, cleared automatically once it isn't.
    include_path = root / "_includes" / "bus-alert.html"
    include_contents = include_path.open().read()
    include_contents = helper.replace_chunk(include_contents, "bus_alert_marker", build_alert_html(disruptions))
    include_path.open("w").write(include_contents)
