#!/usr/bin/env python3
"""
Build the downloadable data (CSV) and embeddable charts (SVG) for the
"findings" analysis posts.

Each finding is a snapshot: the figures in the post are frozen at the time it
is written, so the CSV and charts are frozen with them.

Inputs:  _data/*.json (already fetched by the scheduled workflows)
Outputs: assets/findings/<slug>.csv, .svg and .png (the PNG is a 2x render
         for newsroom systems that will not take SVG), and <slug>-social.png
         (1200 x 630, used as the post's social sharing image). PNGs need
         rsvg-convert, from `brew install librsvg`.

Usage:
    python _python/local/build-findings.py --list
    python _python/local/build-findings.py <slug> [<slug> ...]
    python _python/local/build-findings.py <slug> --force   # refresh a chart

Charts are frozen snapshots that match their post's text, so existing ones
are never replaced without --force. Only use --force when the post's figures
are being refreshed at the same time.
"""

import argparse
import csv
import json
import shutil
import subprocess
import tempfile
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from typing import Any, Callable, Sequence

root = Path(__file__).resolve().parent.parent.parent
DATA = root / "_data"
OUT = root / "assets" / "findings"

SITE = "cheltenham-od.uk"
WIDTH = 640
FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

# Validated pair: site accent for the main series, blue for the comparison
# series. The comparison series is also hatched, so it never relies on colour
# alone. Always light, with no dark-mode rule: an embedded SVG follows the
# reader's device setting, not the page it sits on.
STYLE = """
<style>
  .bg { fill: #fcfcfb; }
  .t1 { fill: #0b0b0b; font: 600 17px FONT; }
  .t2 { fill: #52514e; font: 13px FONT; }
  .lab { fill: #0b0b0b; font: 12px FONT; }
  .val { fill: #0b0b0b; font: 600 12px FONT; }
  .ax { fill: #52514e; font: 11px FONT; }
  .src { fill: #52514e; font: 11px FONT; }
  .grid { stroke: #e4e3df; stroke-width: 1; }
  .base { stroke: #8a8984; stroke-width: 1; }
  .s1 { fill: #ca3393; }
  .s2 { fill: #2a78d6; }
  .mute { fill: #b9b8b3; }
  .line { fill: none; stroke: #ca3393; stroke-width: 2; }
  .dot { fill: #ca3393; stroke: #fcfcfb; stroke-width: 2; }
  .hatch { stroke: #fcfcfb; stroke-width: 2; }
</style>
""".replace(
    "FONT", FONT
)

Row = dict[str, Any]


def load(name: str) -> Any:
    """Read one _data JSON file."""
    with open(DATA / name, encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(slug: str, rows: Sequence[Row]) -> None:
    """Write rows to assets/findings/<slug>.csv."""
    with open(OUT / f"{slug}.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def frame(
    slug: str, height: int, titles: tuple[str, str, str], body: list[str]
) -> None:
    """Wrap chart marks in a titled, sourced, self-contained SVG and save it."""
    title, subtitle, source = titles
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
        f'width="{WIDTH}" height="{height}" role="img" '
        f'aria-labelledby="{slug}-title {slug}-desc">',
        f'<title id="{slug}-title">{escape(title)}</title>',
        f'<desc id="{slug}-desc">{escape(subtitle)}. {escape(source)}</desc>',
        STYLE,
        '<defs><pattern id="hatch" width="6" height="6" '
        'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<line class="hatch" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>',
        f'<rect class="bg" width="{WIDTH}" height="{height}"/>',
        f'<text class="t1" x="20" y="32">{escape(title)}</text>',
        f'<text class="t2" x="20" y="52">{escape(subtitle)}</text>',
        *body,
        f'<text class="src" x="20" y="{height - 14}">'
        f"{escape(source)} · {SITE}</text>",
        "</svg>",
    ]
    (OUT / f"{slug}.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")
    render_png(slug)
    render_social(slug, height, parts[1:-1])


def render_social(slug: str, height: int, inner: list[str]) -> None:
    """Fit the chart onto a 1200 x 630 card and render <slug>-social.png."""
    tool = shutil.which("rsvg-convert")
    if not tool:
        print(f"skipped {slug}-social.png: rsvg-convert not found")
        return
    card = "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" '
        'viewBox="0 0 1200 630">',
        '<rect width="1200" height="630" fill="#fcfcfb"/>',
        f'<svg x="20" y="15" width="1160" height="600" '
        f'viewBox="0 0 {WIDTH} {height}" preserveAspectRatio="xMidYMid meet">',
        *inner,
        "</svg>",
        "</svg>",
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".svg", encoding="utf-8",
                                     delete=False) as handle:
        handle.write(card)
    subprocess.run(
        [tool, "--output", str(OUT / f"{slug}-social.png"), handle.name],
        check=True,
    )
    Path(handle.name).unlink()


def render_png(slug: str) -> None:
    """Render <slug>.svg to a 2x PNG beside it."""
    tool = shutil.which("rsvg-convert")
    if not tool:
        print(f"skipped {slug}.png: rsvg-convert not found")
        return
    subprocess.run(
        [tool, "--zoom", "2", "--output", str(OUT / f"{slug}.png"),
         str(OUT / f"{slug}.svg")],
        check=True,
    )


def hbars(
    rows: Sequence[tuple[str, float, str]],
    fmt: Callable[[float], str],
    top: float = 76,
    label_w: int = 200,
) -> tuple[list[str], int]:
    """Horizontal bars, one per row: (label, value, css class)."""
    step, bar_h = 24, 16
    span = WIDTH - label_w - 80
    vmax = max(value for _, value, _ in rows) or 1
    marks = []
    for i, (label, value, cls) in enumerate(rows):
        y = top + i * step
        w = max(span * value / vmax, 1)
        marks.append(
            f'<text class="lab" x="{label_w - 8}" y="{y + 12}" '
            f'text-anchor="end">{escape(label)}</text>'
        )
        marks.append(
            f'<rect class="{cls}" x="{label_w}" y="{y}" width="{w:.1f}" '
            f'height="{bar_h}" rx="2"/>'
        )
        if cls == "s2":
            marks.append(
                f'<rect fill="url(#hatch)" x="{label_w}" y="{y}" '
                f'width="{w:.1f}" height="{bar_h}" rx="2"/>'
            )
        marks.append(
            f'<text class="val" x="{label_w + w + 6:.1f}" y="{y + 12}">'
            f"{escape(fmt(value))}</text>"
        )
    return marks, int(top + len(rows) * step + 44)


def vbars(
    cats: Sequence[str],
    stacks: Sequence[Sequence[tuple[float, str]]],
    label_every: int = 1,
    value_labels: bool = True,
) -> tuple[list[str], int]:
    """Vertical bars; each bar is a stack of (value, css class) segments."""
    top, plot_h, left, right = 76, 220, 48, 20
    span = WIDTH - left - right
    slot = span / len(cats)
    bar_w = max(slot - 4, 2)
    totals = [sum(v for v, _ in stack) for stack in stacks]
    vmax = max(totals) or 1
    base = top + plot_h
    marks = [f'<line class="base" x1="{left}" x2="{WIDTH - right}" '
             f'y1="{base}" y2="{base}"/>']
    for i, (cat, stack) in enumerate(zip(cats, stacks)):
        x = left + i * slot + (slot - bar_w) / 2
        y = float(base)
        for value, cls in stack:
            h = plot_h * value / vmax
            y -= h
            marks.append(
                f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" '
                f'width="{bar_w:.1f}" height="{h:.1f}"/>'
            )
            if cls == "s2" and h > 0:
                marks.append(
                    f'<rect fill="url(#hatch)" x="{x:.1f}" y="{y:.1f}" '
                    f'width="{bar_w:.1f}" height="{h:.1f}"/>'
                )
            y -= 2 if h > 0 else 0
        if value_labels:
            marks.append(
                f'<text class="val" x="{x + bar_w / 2:.1f}" y="{y - 4:.1f}" '
                f'text-anchor="middle">{totals[i]:,.0f}</text>'
            )
        if i % label_every == 0:
            marks.append(
                f'<text class="ax" x="{x + bar_w / 2:.1f}" y="{base + 16}" '
                f'text-anchor="middle">{escape(cat)}</text>'
            )
    return marks, base + 64


def line(
    points: Sequence[tuple[str, float]],
    ticks: Sequence[float],
    labelled: Sequence[str],
    fmt: Callable[[float], str],
    label_every: int = 1,
) -> tuple[list[str], int]:
    """Single-series line with dots; value labels only at the `labelled` points."""
    top, plot_h, left, right = 80, 220, 48, 30
    lo, hi = ticks[0], ticks[-1]
    span = WIDTH - left - right
    marks = []
    for tick in ticks:
        y = top + plot_h * (hi - tick) / (hi - lo)
        marks.append(f'<line class="grid" x1="{left}" x2="{WIDTH - right}" '
                     f'y1="{y:.1f}" y2="{y:.1f}"/>')
        marks.append(f'<text class="ax" x="{left - 6}" y="{y + 4:.1f}" '
                     f'text-anchor="end">{escape(fmt(tick))}</text>')
    pts = []
    for i, (cat, value) in enumerate(points):
        x = left + span * i / (len(points) - 1)
        pts.append((x, top + plot_h * (hi - value) / (hi - lo), cat, value))
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in pts)
    marks.append(f'<polyline class="line" points="{path}"/>')
    last = len(pts) - 1
    for i, (x, y, cat, value) in enumerate(pts):
        marks.append(f'<circle class="dot" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')
        if (last - i) % label_every == 0:  # count back so the latest is shown
            marks.append(f'<text class="ax" x="{x:.1f}" y="{top + plot_h + 18}" '
                         f'text-anchor="middle">{escape(cat)}</text>')
        if cat in labelled:
            anchor = "start" if i == 0 else "end" if i == last else "middle"
            near = [points[j][1] for j in (i - 1, i + 1) if 0 <= j <= last]
            dip = value <= min(near)  # label a low point below, clear of the line
            marks.append(f'<text class="val" x="{x:.1f}" '
                         f'y="{y + 20 if dip else y - 10:.1f}" '
                         f'text-anchor="{anchor}">{escape(fmt(value))}</text>')
    return marks, top + plot_h + 60


def legend(items: Sequence[tuple[str, str]], y: int) -> list[str]:
    """A one-row legend of (css class, label) swatches."""
    marks, x = [], 20
    for cls, label in items:
        marks.append(f'<rect class="{cls}" x="{x}" y="{y}" width="12" height="12"/>')
        if cls == "s2":
            marks.append(
                f'<rect fill="url(#hatch)" x="{x}" y="{y}" width="12" height="12"/>'
            )
        marks.append(f'<text class="lab" x="{x + 18}" y="{y + 11}">{escape(label)}</text>')
        x += 30 + 7 * len(label)
    return marks


def rents_vs_pay() -> None:
    """Housing squeeze post: August rent as a share of median full-time pay."""
    rent = {h["year"]: h["price"] for h in load("rents.json")["same_month_history"]}
    pay = {s["year"]: s["resident"] for s in load("cheltenham-earnings.json")["series"]}
    rows = [
        {
            "year": y,
            "average_monthly_rent_august_gbp": rent[y],
            "annual_rent_gbp": rent[y] * 12,
            "resident_median_full_time_pay_gbp": int(pay[y]),
            "rent_share_of_pay_pct": round(rent[y] * 12 / pay[y] * 100, 1),
        }
        for y in sorted(rent)
        if y in pay
    ]
    write_csv("cheltenham-rent-share-of-pay", rows)
    marks, height = line(
        [(str(r["year"]), r["rent_share_of_pay_pct"]) for r in rows],
        [28, 30, 32, 34, 36, 38],
        ["2015", "2018", "2022", "2025"],
        lambda v: f"{v:g}%",
    )
    frame(
        "cheltenham-rent-share-of-pay",
        height,
        (
            "Rent as a share of typical full-time pay, Cheltenham",
            "Average August rent × 12 as % of resident median gross full-time pay",
            "Source: ONS Price Index of Private Rents; ONS ASHE via Nomis (OGL v3.0)",
        ),
        marks,
    )


def road_casualties() -> None:
    """Post 2: killed or seriously injured casualties by road user, 2021-2025."""
    data = load("road-collisions.json")
    rows = [
        {
            "road_user": u["user"],
            "killed": u["fatal"],
            "seriously_injured": u["serious"],
            "killed_or_seriously_injured": u["fatal"] + u["serious"],
            "slightly_injured": u["slight"],
            "all_casualties": u["total"],
        }
        for u in data["by_user"]
    ]
    write_csv("cheltenham-road-casualties-walking-cycling", rows)
    ordered = sorted(rows, key=lambda r: -r["killed_or_seriously_injured"])
    bars = [
        (
            r["road_user"],
            float(r["killed_or_seriously_injured"]),
            "s1" if r["road_user"] in ("Pedestrian", "Cyclist") else "mute",
        )
        for r in ordered
    ]
    marks, height = hbars(bars, lambda v: f"{v:.0f}", label_w=220)
    frame(
        "cheltenham-road-casualties-walking-cycling",
        height,
        (
            "Killed or seriously injured on Cheltenham's roads, 2021–2025",
            "Casualties by road user; pedestrians and cyclists highlighted",
            "Source: Department for Transport STATS19 (OGL v3.0)",
        ),
        marks,
    )


def deprivation() -> None:
    """Post 3: Cheltenham's 77 neighbourhoods by national deprivation decile."""
    data = load("deprivation.json")
    rows = [
        {
            "lsoa_code": area["code"],
            "lsoa_name": area["name"],
            "ward": area["ward_name"],
            "population": area["population"],
            "imd_score": area["score"],
            "imd_rank_of_33755": area["rank"],
            "imd_decile": area["deciles"]["imd"],
        }
        for area in sorted(data["lsoas"], key=lambda a: a["rank"])
    ]
    write_csv("cheltenham-deprivation-two-cheltenhams", rows)
    counts = Counter(r["imd_decile"] for r in rows)
    cats = [str(d) for d in range(1, 11)]
    stacks = [[(float(counts[d]), "s1" if d <= 2 else "mute")] for d in range(1, 11)]
    marks, height = vbars(cats, stacks)
    marks.append(f'<text class="ax" x="48" y="{height - 30}">'
                 "1 = most deprived 10% in England · 10 = least deprived 10%</text>")
    frame(
        "cheltenham-deprivation-two-cheltenhams",
        height + 10,
        (
            "Cheltenham's 77 neighbourhoods by deprivation decile",
            "Number of neighbourhoods (LSOAs) in each national decile, IoD 2025",
            "Source: MHCLG English Indices of Deprivation 2025 (OGL v3.0)",
        ),
        marks,
    )


def ward_rows() -> list[Row]:
    """Ward table joined from deprivation, politics and the ward files."""
    dep = {w["name"]: w for w in load("deprivation.json")["wards"].values()}
    pol = load("ward-politics.json")["wards"]
    rows = []
    for path in sorted((DATA / "wards").glob("*.json")):
        if path.name == "index.json":
            continue
        ward = json.loads(path.read_text(encoding="utf-8"))
        votes = {e["date"]: e["turnout_pct"] for e in pol[ward["slug"]]["elections"]}
        rows.append(
            {
                "ward": ward["name"],
                "deprivation_rank_in_cheltenham": dep[ward["name"]]["rank"],
                "imd_score": dep[ward["name"]]["score"],
                "turnout_2026_pct": votes.get("2026-05-07"),
                "turnout_2024_pct": votes.get("2024-05-02"),
            }
        )
    return sorted(rows, key=lambda r: r["deprivation_rank_in_cheltenham"])


def ward_chart(slug: str, field: str, titles: tuple[str, str, str]) -> None:
    """Horizontal bars of one ward field, most deprived ward first."""
    rows = ward_rows()
    bars = [
        (
            r["ward"].replace("Benhall, the Reddings & Fiddler's Green", "Benhall & Reddings"),
            float(r[field]),
            "s1" if r["deprivation_rank_in_cheltenham"] <= 4
            else "s2" if r["deprivation_rank_in_cheltenham"] >= 17 else "mute",
        )
        for r in rows
    ]
    marks, height = hbars(bars, lambda v: f"{v:.1f}%", top=96, label_w=170)
    marks += legend([("s1", "4 most deprived wards"), ("s2", "4 least deprived wards")], 66)
    frame(slug, height, titles, marks)


def turnout() -> None:
    """Post 4: 2026 borough election turnout by ward, most deprived first."""
    keep = ["ward", "deprivation_rank_in_cheltenham", "imd_score",
            "turnout_2026_pct", "turnout_2024_pct"]
    write_csv("cheltenham-turnout-deprivation",
              [{k: r[k] for k in keep} for r in ward_rows()])
    ward_chart(
        "cheltenham-turnout-deprivation",
        "turnout_2026_pct",
        (
            "Turnout by ward, Cheltenham borough election, 7 May 2026",
            "Wards ordered from most deprived (top) to least deprived",
            "Source: Cheltenham Borough Council; MHCLG IoD 2025 (OGL v3.0)",
        ),
    )


def ae_waits() -> None:
    """Post 5: monthly 12-hour trolley waits at Gloucestershire Hospitals."""
    months = sorted(load("nhs-ae.json")["months"], key=lambda m: m["period"])
    rows = [
        {
            "month": m["period"],
            "attendances": m["attendances"],
            "seen_within_4_hours_pct": m["within_4hrs_pct"],
            "waits_over_12_hours_from_decision_to_admit": m["dta_12hrs"],
            "emergency_admissions": m["emergency_admissions"],
        }
        for m in months
    ]
    write_csv("gloucestershire-ae-12-hour-waits", rows)
    cats = [m["period"][:4] if m["period"].endswith("-01") else "" for m in months]
    stacks = [
        [(float(m["dta_12hrs"]), "s1" if m["period"].endswith("-01") else "mute")]
        for m in months
    ]
    marks, height = vbars(cats, stacks, value_labels=False)
    for i, m in enumerate(months):
        if m["period"].endswith("-01") or i == len(months) - 1:
            slot = (WIDTH - 68) / len(months)
            x = 48 + i * slot + slot / 2
            y = 76 + 220 - 220 * m["dta_12hrs"] / max(r["dta_12hrs"] for r in months)
            marks.append(f'<text class="val" x="{x:.1f}" y="{y - 6:.1f}" '
                         f'text-anchor="middle">{m["dta_12hrs"]}</text>')
    frame(
        "gloucestershire-ae-12-hour-waits",
        height,
        (
            "12-hour waits from decision to admit, Gloucestershire Hospitals",
            f"Monthly, {months[0]['period']} to {months[-1]['period']}; "
            "Januarys highlighted",
            "Source: NHS England A&E Attendances and Emergency Admissions (OGL v3.0)",
        ),
        marks,
    )


def care_homes() -> None:
    """Post 6: current care home ratings by year the report was published."""
    homes = [
        loc for loc in load("cqc.json")["locations"]
        if loc["care_home"] and loc["overall"]
    ]
    rows = [
        {
            "name": h["name"],
            "type": h["kind"].replace("_", " "),
            "overall_rating": h["overall"],
            "report_published": h["published"],
            "cqc_url": h["url"],
        }
        for h in sorted(homes, key=lambda h: (h["published"], h["name"]))
    ]
    write_csv("cheltenham-care-home-ratings", rows)
    by_year: dict[str, Counter[str]] = defaultdict(Counter)
    for h in homes:
        good = h["overall"] in ("Good", "Outstanding")
        by_year[h["published"][:4]]["good" if good else "ri"] += 1
    years = [str(y) for y in range(int(min(by_year)), int(max(by_year)) + 1)]
    stacks = [
        [(float(by_year[y]["good"]), "s1"), (float(by_year[y]["ri"]), "s2")]
        for y in years
    ]
    marks, height = vbars(years, stacks)
    marks += legend([("s1", "Good or outstanding"), ("s2", "Requires improvement")],
                    height - 40)
    frame(
        "cheltenham-care-home-ratings",
        height + 10,
        (
            "Cheltenham care homes by current CQC rating and report year",
            f"{len(homes)} rated care homes, grouped by year the rating was published",
            "Source: Care Quality Commission (OGL v3.0)",
        ),
        marks,
    )


def housing_supply() -> None:
    """Housing squeeze post: net additional dwellings, with student bedspaces."""
    data = load("housing-supply.json")
    student = {
        e["year"]: e["student_net_change"]
        for e in data["communal_accommodation"]["entries"]
        if e["metric"] == "bedspaces"
    }
    years = data["net_additional_dwellings"]["years"]
    rows = [
        {
            "year": y["year"],
            "net_additional_dwellings": y["net_additional_dwellings"],
            "student_bedspaces_net_change": student.get(y["year"], ""),
        }
        for y in years
    ]
    write_csv("cheltenham-housing-supply-slowdown", rows)
    recent = [y for y in years if y["year"] >= "2012-13"]
    cats = [y["year"][2:4] + "/" + y["year"][5:] for y in recent]
    stacks = [
        [(float(max(y["net_additional_dwellings"], 0)),
          "s2" if y["year"] >= "2021-22" else "s1")]
        for y in recent
    ]
    marks, height = vbars(cats, stacks)
    marks += legend([("s1", "2012/13 to 2020/21"), ("s2", "2021/22 onwards")],
                    height - 40)
    frame(
        "cheltenham-housing-supply-slowdown",
        height + 10,
        (
            "Net additional homes a year, Cheltenham",
            "Financial years, April to March",
            "Source: MHCLG Live Table 122 (OGL v3.0)",
        ),
        marks,
    )


def affordability() -> None:
    """Affordability post: share of sales within 4.5 times median pay."""
    data = load("cheltenham-affordability.json")
    types = ("flat", "terraced", "semi_detached", "detached")
    rows = []
    for y in data["years"]:
        row: Row = {
            "year": y["year"],
            "resident_median_full_time_pay_gbp": y["pay"],
            "price_limit_gbp": y["cap"],
            "sales": y["sales"],
            "sales_within_reach": y["within"],
            "share_within_reach_pct": y["share"],
            "median_sale_price_gbp": y["median_price"],
        }
        for kind in types:
            row[f"{kind}_share_within_reach_pct"] = y["by_type"][kind]["share"]
        rows.append(row)
    write_csv("cheltenham-home-affordability", rows)
    marks, height = line(
        [(str(r["year"]), r["share_within_reach_pct"]) for r in rows],
        [0, 4, 8, 12, 16],
        ["2008", "2009", "2018", "2025"],
        lambda v: f"{v:g}%",
        label_every=2,
    )
    frame(
        "cheltenham-home-affordability",
        height,
        (
            "Cheltenham homes sold within reach of a typical earner",
            f"% of sales at no more than {data['multiple']:g} times median "
            "full-time pay",
            "Source: HM Land Registry; ONS ASHE via Nomis (OGL v3.0)",
        ),
        marks,
    )


def food_hygiene() -> None:
    """Food hygiene post: share of businesses rated 5, by type of business."""
    rated = [b for b in load("food-standards.json") if b["rating"] in "012345"]
    by_type: dict[str, Counter[str]] = defaultdict(Counter)
    for b in rated:
        by_type[b["type"]][b["rating"]] += 1
    rows = []
    for kind, counts in sorted(by_type.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(counts.values())
        row: Row = {"business_type": kind, "rated": total}
        for rating in "543210":
            row[f"rating_{rating}"] = counts[rating]
        row["share_rated_5_pct"] = round(counts["5"] / total * 100, 1)
        rows.append(row)
    write_csv("cheltenham-food-hygiene-ratings", rows)
    shown = sorted((r for r in rows if r["rated"] >= 20),
                   key=lambda r: r["share_rated_5_pct"])
    lowest = {r["business_type"] for r in shown[:2]}
    bars = [
        (r["business_type"], float(r["share_rated_5_pct"]),
         "s1" if r["business_type"] in lowest else "mute")
        for r in shown
    ]
    marks, height = hbars(bars, lambda v: f"{v:.1f}%", label_w=260)
    frame(
        "cheltenham-food-hygiene-ratings",
        height,
        (
            "Cheltenham food businesses with a five-star hygiene rating",
            "% rated 5 by type of business (types with 20 or more rated)",
            "Source: Food Standards Agency (OGL v3.0)",
        ),
        marks,
    )


# One entry per chart, keyed by the slug its files are written under. A new
# analysis post adds a builder above and one line here.
BUILDERS: dict[str, Callable[[], None]] = {
    "cheltenham-home-affordability": affordability,
    "cheltenham-food-hygiene-ratings": food_hygiene,
    "cheltenham-deprivation-two-cheltenhams": deprivation,
    "cheltenham-road-casualties-walking-cycling": road_casualties,
    "cheltenham-turnout-deprivation": turnout,
    "cheltenham-care-home-ratings": care_homes,
    "gloucestershire-ae-12-hour-waits": ae_waits,
    "cheltenham-housing-supply-slowdown": housing_supply,
    "cheltenham-rent-share-of-pay": rents_vs_pay,
}


def main() -> None:
    """Build the named charts, leaving existing (published) ones alone."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("slugs", nargs="*", help="charts to build")
    parser.add_argument("--force", action="store_true",
                        help="overwrite a chart whose files already exist")
    parser.add_argument("--list", action="store_true",
                        help="list the charts this script can build")
    args = parser.parse_args()
    if args.list or not args.slugs:
        for slug in BUILDERS:
            state = "built" if (OUT / f"{slug}.csv").exists() else "not built"
            print(f"{slug} ({state})")
        return
    OUT.mkdir(parents=True, exist_ok=True)
    for slug in args.slugs:
        if slug not in BUILDERS:
            raise SystemExit(f"unknown chart: {slug} (see --list)")
        if (OUT / f"{slug}.csv").exists() and not args.force:
            print(f"skipped {slug}: already built; use --force to replace it")
            continue
        BUILDERS[slug]()
        print(f"built {slug}")


if __name__ == "__main__":
    main()
