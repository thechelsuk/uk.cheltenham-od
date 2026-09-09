#!/usr/bin/env python3
"""
Build broadband coverage data for the Jekyll site, aggregated to WARD level.

Inputs (in _data-sources/):
  1. COVERAGE_CSV       Ofcom Connected Nations postcode-unit coverage CSV.
  2. WARD_BOUNDARY_FILE Ward boundary GeoJSON from the ONS Open Geography Portal
                        ("Wards May 2024 Boundaries UK BGC"), saved as
                        _data-sources/wards.geojson

Postcodes are mapped to wards via postcodes.io (cached in _data-sources/_ward-cache.json),
coverage is averaged per ward, and wards are shaded by % coverage.

Outputs:
    _data/broadband-map.json      GeoJSON ward polygons, shaded by % coverage
    _data/broadband-summary.json  header stats + ward table + tier table

Usage:
    python build_broadband.py
"""

import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

# --- CONFIG -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "_data-sources"

COVERAGE_CSV = SOURCE_DIR / "202601_fixed_pc_coverage_r2_GL.csv"
WARD_BOUNDARY_FILE = SOURCE_DIR / "wards.geojson"
WARD_CACHE = SOURCE_DIR / "_ward-cache.json"

MAP_OUT = REPO_ROOT / "_data" / "broadband-map.json"
SUMMARY_OUT = REPO_ROOT / "_data" / "broadband-summary.json"

TARGET_OUTCODES = {"GL50", "GL51", "GL52", "GL53", "GL54"}

# Which % metric drives the MAP colour, and its shade bins.
SHADE_METRIC = "gigabit_pct"  # sfbb_pct | ufbb100_pct | ufbb300_pct | gigabit_pct
SHADE_BINS = [
    (0,  "#eff3ff"),   # < 75%
    (75, "#c6dbef"),   # 75-80%
    (80, "#9ecae1"),   # 80-85%
    (85, "#6baed6"),   # 85-90%
    (90, "#3182bd"),   # 90-95%
    (95, "#08519c"),   # 95%+
]

# Ofcom CSV column names (verify against the header each release).
COL_POSTCODE = "postcode_space"
COL_SFBB = "SFBB availability (% premises)"
COL_UFBB100 = "UFBB (100Mbit/s) availability (% premises)"
COL_UFBB300 = "UFBB availability (% premises)"
COL_GIGABIT = "Gigabit availability (% premises)"

TIER_THRESHOLD = 50.0  # % of premises required to count a tier as "available"

# Ward-boundary property keys holding the GSS code (ONS BGC uses WD24CD).
WARD_CODE_KEYS = ["WD24CD", "WD23CD", "WD22CD", "WD21CD", "WD20CD", "code", "ward_code", "WardCode"]

# Tier metadata. TIER_LABELS is the long form used in the ward table and map
# popups; TIER_NAMES/SPEEDS/BLURBS feed the combined "Coverage by Tier" table.
TIER_LABELS = {
    0: "Below USO (basic broadband issues)",
    1: "Superfast (30Mbps+)",
    2: "Ultrafast entry (100Mbps+)",
    3: "Ultrafast high (300Mbps+)",
    4: "Gigabit-capable (1000Mbps+)",
}
TIER_NAMES = {
    0: "Below USO",
    1: "Superfast",
    2: "Ultrafast entry",
    3: "Ultrafast high",
    4: "Gigabit-capable",
}
TIER_SPEEDS = {
    0: "Below 30 Mbps",
    1: "30 Mbps+",
    2: "100 Mbps+",
    3: "300 Mbps+",
    4: "1000 Mbps+",
}
TIER_BLURBS = {
    0: "Fewer than half of premises reach superfast; some may fall under the Universal Service Obligation (10 Mbps) minimum.",
    1: "The UK's baseline standard for a \"decent\" broadband connection.",
    2: "Fast enough for almost any household, including streaming and video calls.",
    3: "Very fast, comfortable for heavy use across many devices at once.",
    4: "The fastest tier — full-fibre or equivalent, capable of 1000 Mbps and beyond.",
}


# --- HELPERS ----------------------------------------------------------

def to_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def outcode_of(postcode: str) -> str:
    return postcode.split(" ")[0].strip().upper()


def norm(code: str) -> str:
    return (code or "").replace(" ", "").strip().upper()


def classify_tier(sfbb: float, ufbb100: float, ufbb300: float, gigabit: float) -> int:
    if gigabit >= TIER_THRESHOLD:
        return 4
    if ufbb300 >= TIER_THRESHOLD:
        return 3
    if ufbb100 >= TIER_THRESHOLD:
        return 2
    if sfbb >= TIER_THRESHOLD:
        return 1
    return 0


def shade_color(pct: float) -> str:
    colour = SHADE_BINS[0][1]
    for lower, c in SHADE_BINS:
        if pct >= lower:
            colour = c
    return colour


def blank_bucket() -> dict:
    return {"n": 0, "sfbb": 0.0, "u100": 0.0, "u300": 0.0, "giga": 0.0, "name": None}


def means_of(bucket: dict) -> dict:
    n = bucket["n"] or 1
    return {
        "sfbb_pct": round(bucket["sfbb"] / n, 1),
        "ufbb100_pct": round(bucket["u100"] / n, 1),
        "ufbb300_pct": round(bucket["u300"] / n, 1),
        "gigabit_pct": round(bucket["giga"] / n, 1),
    }


def lookup_wards(postcodes: list) -> dict:
    """postcode -> {'ward_code', 'ward_name'} via postcodes.io, cached on disk."""
    cache = json.loads(WARD_CACHE.read_text()) if WARD_CACHE.exists() else {}
    missing = [p for p in postcodes if p not in cache]
    if missing:
        print(f"Looking up wards for {len(missing)} new postcodes via postcodes.io ...",
              file=sys.stderr)
    for i in range(0, len(missing), 100):  # bulk endpoint: 100 max
        batch = missing[i:i + 100]
        req = urllib.request.Request(
            "https://api.postcodes.io/postcodes",
            data=json.dumps({"postcodes": batch}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
        for entry in payload.get("result", []):
            r = entry.get("result") or {}
            cache[entry.get("query")] = {
                "ward_code": (r.get("codes") or {}).get("admin_ward"),
                "ward_name": r.get("admin_ward"),
            }
        time.sleep(0.4)
    WARD_CACHE.write_text(json.dumps(cache, indent=2))
    return cache


# --- MAIN -------------------------------------------------------------

def main():
    for path in (COVERAGE_CSV, WARD_BOUNDARY_FILE):
        if not path.exists():
            print(f"ERROR: input file not found: {path}", file=sys.stderr)
            print("-> Put both input files in _data-sources/ (see reminder above).", file=sys.stderr)
            sys.exit(1)

    # Pass 1: read coverage rows for target outcodes.
    rows = []
    tier_totals = defaultdict(int)
    print(f"Reading coverage from {COVERAGE_CSV.name} ...", file=sys.stderr)
    with COVERAGE_CSV.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            postcode = (row.get(COL_POSTCODE) or "").strip()
            if not postcode or outcode_of(postcode) not in TARGET_OUTCODES:
                continue
            rec = {
                "postcode": postcode,
                "sfbb": to_float(row.get(COL_SFBB)),
                "u100": to_float(row.get(COL_UFBB100)),
                "u300": to_float(row.get(COL_UFBB300)),
                "giga": to_float(row.get(COL_GIGABIT)),
            }
            rec["tier"] = classify_tier(rec["sfbb"], rec["u100"], rec["u300"], rec["giga"])
            rows.append(rec)
            tier_totals[rec["tier"]] += 1

    if not rows:
        print("ERROR: no matching postcodes found. Check TARGET_OUTCODES / column names.",
              file=sys.stderr)
        sys.exit(1)

    # Pass 2: map postcodes to wards and aggregate by ward.
    ward_of = lookup_wards([r["postcode"] for r in rows])
    wards = defaultdict(blank_bucket)  # keyed by norm(ward_code)
    unmatched_pc = 0
    for r in rows:
        w = ward_of.get(r["postcode"]) or {}
        code = w.get("ward_code")
        if not code:
            unmatched_pc += 1
            continue
        b = wards[norm(code)]
        b["name"] = w.get("ward_name")
        b["n"] += 1
        b["sfbb"] += r["sfbb"]; b["u100"] += r["u100"]
        b["u300"] += r["u300"]; b["giga"] += r["giga"]

    if unmatched_pc:
        print(f"Note: {unmatched_pc} postcodes had no ward from postcodes.io (skipped).",
              file=sys.stderr)

    ward_props = {}
    for k, b in wards.items():
        m = means_of(b)
        tier = classify_tier(m["sfbb_pct"], m["ufbb100_pct"], m["ufbb300_pct"], m["gigabit_pct"])
        ward_props[k] = {
            "name": b["name"] or "Ward",
            "ward_code": k,
            "tier": tier,
            "tier_label": TIER_LABELS[tier],
            "marker-color": shade_color(m[SHADE_METRIC]),
            "shade_metric": SHADE_METRIC,
            "shade_value": m[SHADE_METRIC],
            "unit_count": b["n"],
            **m,
        }

    # Join aggregated wards onto ward polygons by GSS code ONLY. Ward names are
    # not unique across the UK (many "College"/"Park" wards), so a name fallback
    # pulls in far-away namesakes and blows the map extent out to the whole UK.
    # The GSS code (WD24CD) is unique, so match on that alone.
    boundary = json.loads(WARD_BOUNDARY_FILE.read_text())
    features = []
    matched_keys = set()
    for feature in boundary.get("features", []):
        props = feature.get("properties", {}) or {}
        code = next((props[k] for k in WARD_CODE_KEYS if props.get(k)), None)
        stats = ward_props.get(norm(code))
        if not stats:
            continue
        matched_keys.add(stats["ward_code"])
        features.append({
            "type": "Feature",
            "properties": stats,
            "geometry": feature["geometry"],
        })

    if not features:
        print("WARNING: no ward polygons matched — fall back to option 1 (district labels). "
              "Check WARD_CODE_KEYS and the wards.geojson vintage vs postcodes.io codes.",
              file=sys.stderr)
    else:
        print(f"Matched {len(features)} of {len(ward_props)} wards to polygons.", file=sys.stderr)

    # Ward summary table: one row per ward that made it onto the map, A-Z.
    ward_summary = sorted(
        (
            {
                "name": p["name"],
                "unit_count": p["unit_count"],
                "tier": p["tier"],
                "tier_label": p["tier_label"],
                "sfbb_pct": p["sfbb_pct"],
                "ufbb100_pct": p["ufbb100_pct"],
                "ufbb300_pct": p["ufbb300_pct"],
                "gigabit_pct": p["gigabit_pct"],
            }
            for p in ward_props.values() if p["ward_code"] in matched_keys
        ),
        key=lambda w: w["name"],
    )

    # Combined tier table: name, speed, postcode count, description.
    tier_table = [
        {
            "tier": t,
            "name": TIER_NAMES[t],
            "speed": TIER_SPEEDS[t],
            "blurb": TIER_BLURBS[t],
            "count": tier_totals.get(t, 0),
        }
        for t in sorted(TIER_LABELS, reverse=True)
    ]

    summary = {
        "updated": date.today().isoformat(),
        "shade_metric": SHADE_METRIC,
        "outcodes": sorted(TARGET_OUTCODES),
        "unit_total": len(rows),
        "ward_total": len(features),
        "tier_totals": tier_table,
        "ward_summary": ward_summary,
    }

    MAP_OUT.parent.mkdir(parents=True, exist_ok=True)
    MAP_OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {len(features)} ward polygons (shaded by {SHADE_METRIC}) to {MAP_OUT.name}",
          file=sys.stderr)
    print(f"Wrote summary ({len(rows)} postcodes, {len(ward_summary)} wards) to {SUMMARY_OUT.name}",
          file=sys.stderr)


if __name__ == "__main__":
    print("Reminder: put the Ofcom coverage CSV *and* wards.geojson in _data-sources/ "
          "before running.", file=sys.stderr)
    main()
