import datetime

import helper

# -- Configuration ------------------------------------------------------------

CATALOGUE_URL = "https://data.bus-data.dft.gov.uk/catalogue/"
SOURCE_PAGE   = "https://data.bus-data.dft.gov.uk/"
TIMETABLES_CSV = "timetables_data_catalogue.csv"

# A route "serves Cheltenham" if the town name appears in any of these fields.
MATCH_FIELDS = [
    "OTC:Origin", "OTC:Destination", "OTC:Via",
    "OTC:Start Point", "OTC:Finish Point",
]
MATCH_TERM = "cheltenham"

ATTENTION_LABELS = {
    "Up to date":                             "Up to date",
    "OTC variation not published":            "Registration change not published",
    "42 day look ahead is incomplete":        "Timetable doesn't look far enough ahead",
    "Service hasn't been updated within a year": "Not updated in over a year",
}

# BODS source data is a mix of ALL CAPS and Title Case. Normalise to Title
# Case, keeping known acronyms and anything with a digit (road refs like A40,
# B4063) upper-case.
ACRONYMS = {"UK", "LLP", "PLC"}


def row_serves_cheltenham(row):
    return any(MATCH_TERM in (row.get(field) or "").lower() for field in MATCH_FIELDS)


def timeliness_label(row):
    status = row.get("Timeliness Status") or ""
    for key, label in ATTENTION_LABELS.items():
        if key in status:
            return label
    return status or "Unknown"


if __name__ == "__main__":
    out_path = helper.repo_root() / "_data" / "bus-routes.json"

    print("Downloading BODS data catalogue...")
    rows = helper.fetch_bods_csv(TIMETABLES_CSV, CATALOGUE_URL)
    print(f"  {len(rows):,} total rows in national catalogue")

    local_rows = [r for r in rows if row_serves_cheltenham(r)]
    print(f"  {len(local_rows)} rows mention Cheltenham")

    routes = []
    for r in local_rows:
        requires_attention = (r.get("Requires Attention") or "").strip().lower() == "yes"
        routes.append({
            "service_number": r.get("OTC:Service Number") or r.get("XML:Line Name") or "",
            "operator":       helper.clean_name(r.get("OTC:Operator Name") or r.get("Organisation Name") or "Unknown", ACRONYMS),
            "start_point":    helper.clean_name(r.get("OTC:Start Point") or r.get("OTC:Origin") or "", ACRONYMS),
            "finish_point":   helper.clean_name(r.get("OTC:Finish Point") or r.get("OTC:Destination") or "", ACRONYMS),
            "via":            helper.clean_name(r.get("OTC:Via") or "", ACRONYMS),
            "requires_attention": requires_attention,
            "published_status":   r.get("Published Status") or "",
            "timeliness":         timeliness_label(r),
            "authority":          r.get("Local Transport Authority") or "",
            "last_modified":      (r.get("XML:Last Modified Date") or "")[:10],
        })

    # De-dupe identical service number + operator + start/finish combos (variations
    # of the same route registered separately in BODS/OTC). We display the most
    # recently modified variation, but a route still counts as needing attention
    # if ANY of its variations does — an older, stale-but-still-live registration
    # shouldn't be hidden just because a newer variation happens to be clean.
    groups = {}
    for route in routes:
        key = (route["service_number"], route["operator"], route["start_point"], route["finish_point"])
        groups.setdefault(key, []).append(route)

    merged = []
    for group in groups.values():
        display = max(group, key=lambda r: r["last_modified"])
        needs_attention = any(r["requires_attention"] for r in group)
        if needs_attention and not display["requires_attention"]:
            # Surface the reason from whichever variation actually needs attention,
            # so the displayed status matches the flag instead of contradicting it.
            flagged = next(r for r in group if r["requires_attention"])
            display = {**display, "requires_attention": True, "timeliness": flagged["timeliness"]}
        merged.append(display)
    routes = sorted(merged, key=lambda r: (r["operator"].lower(), r["service_number"]))

    attention_count = sum(1 for r in routes if r["requires_attention"])
    operators = sorted({r["operator"] for r in routes})

    payload = {
        "updated":          helper.updated_timestamp(),
        "updated_iso":      datetime.date.today().isoformat(),
        "source":           SOURCE_PAGE,
        "source_catalogue": CATALOGUE_URL,
        "total_routes":     len(routes),
        "attention_count":  attention_count,
        "operator_count":   len(operators),
        "operators":        operators,
        "routes":           routes,
    }

    helper.write_json(out_path, payload)
    print(f"Wrote {len(routes)} routes to {out_path}")
