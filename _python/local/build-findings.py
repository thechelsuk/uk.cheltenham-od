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
  .pt { stroke: #fcfcfb; stroke-width: 1.5; }
  .ring { fill: #fcfcfb; stroke: #52514e; stroke-width: 1.5; }
  .arrow { fill: none; stroke: #0b0b0b; stroke-width: 1.5; }
  .divide { stroke: #8a8984; stroke-width: 1; stroke-dasharray: 4 3; }
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


def marker(shape: str, x: float, y: float, cls: str, size: float = 5) -> str:
    """One point: a circle, diamond or triangle, so shape can carry a category."""
    if shape == "diamond":
        s = size * 1.3
        return (f'<polygon class="{cls} pt" points="{x:.1f},{y - s:.1f} '
                f'{x + s:.1f},{y:.1f} {x:.1f},{y + s:.1f} {x - s:.1f},{y:.1f}"/>')
    if shape == "triangle":
        s = size * 1.3
        return (f'<polygon class="{cls} pt" points="{x:.1f},{y - s:.1f} '
                f'{x + s:.1f},{y + s * 0.8:.1f} {x - s:.1f},{y + s * 0.8:.1f}"/>')
    return f'<circle class="{cls} pt" cx="{x:.1f}" cy="{y:.1f}" r="{size}"/>'


def shape_legend(items: Sequence[tuple[str, str, str]], y: int) -> list[str]:
    """A one-row legend of (shape, css class, label) markers."""
    marks, x = [], 26
    for shape, cls, label in items:
        marks.append(marker(shape, x, y + 6, cls))
        marks.append(f'<text class="lab" x="{x + 12}" y="{y + 10}">{escape(label)}</text>')
        x += 36 + 7 * len(label)
    return marks


class Scatter:
    """Axes for a scatter plot. `px` and `py` map data values to the canvas, so
    builders can place points, arrows and notes on the same scale."""

    top, plot_h, left, right = 116, 260, 64, 24

    def __init__(self, x_range: tuple[float, float], y_range: tuple[float, float],
                 left: int = 64):
        self.left = left
        self.x0, self.x1 = x_range
        self.y0, self.y1 = y_range
        self.base = self.top + self.plot_h

    def px(self, x: float) -> float:
        """Canvas x for a data x."""
        span = WIDTH - self.left - self.right
        return self.left + span * (x - self.x0) / (self.x1 - self.x0)

    def py(self, y: float) -> float:
        """Canvas y for a data y."""
        return self.top + self.plot_h * (self.y1 - y) / (self.y1 - self.y0)

    def axes(
        self,
        x_ticks: Sequence[tuple[float, str]],
        y_ticks: Sequence[tuple[float, str]],
        labels: tuple[str, str],
    ) -> list[str]:
        """Gridlines, tick labels and axis titles (x title, y title)."""
        marks = [f'<line class="base" x1="{self.left}" x2="{WIDTH - self.right}" '
                 f'y1="{self.base}" y2="{self.base}"/>']
        for value, text in y_ticks:
            y = self.py(value)
            marks.append(f'<line class="grid" x1="{self.left}" x2="{WIDTH - self.right}" '
                         f'y1="{y:.1f}" y2="{y:.1f}"/>')
            marks.append(f'<text class="ax" x="{self.left - 6}" y="{y + 4:.1f}" '
                         f'text-anchor="end">{escape(text)}</text>')
        for value, text in x_ticks:
            marks.append(f'<text class="ax" x="{self.px(value):.1f}" '
                         f'y="{self.base + 16}" text-anchor="middle">{escape(text)}</text>')
        x_title, y_title = labels
        marks.append(f'<text class="ax" x="{(self.left + WIDTH - self.right) / 2:.1f}" '
                     f'y="{self.base + 34}" text-anchor="middle">{escape(x_title)}</text>')
        marks.append(f'<text class="ax" x="20" y="{self.top - 12}">{escape(y_title)}</text>')
        return marks

    def arrow(self, start: tuple[float, float], end: tuple[float, float],
              gap: float = 9) -> list[str]:
        """A line with an arrowhead from start to end (data values), stopping
        `gap` px short of each point so the markers stay visible."""
        x1, y1 = self.px(start[0]), self.py(start[1])
        x2, y2 = self.px(end[0]), self.py(end[1])
        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        ax, ay = x1 + ux * gap, y1 + uy * gap
        bx, by = x2 - ux * gap, y2 - uy * gap
        head = 7
        lx, ly = bx - ux * head - uy * head * 0.6, by - uy * head + ux * head * 0.6
        rx, ry = bx - ux * head + uy * head * 0.6, by - uy * head - ux * head * 0.6
        return [
            f'<line class="arrow" x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}"/>',
            f'<polygon fill="#0b0b0b" points="{bx:.1f},{by:.1f} {lx:.1f},{ly:.1f} '
            f'{rx:.1f},{ry:.1f}"/>',
        ]


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
    """A&E post: monthly 12-hour trolley waits, with each September highlighted."""
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
    focus = "-09"  # the month the post compares year on year
    cats = [m["period"][:4] if m["period"].endswith("-01") else "" for m in months]
    stacks = [
        [(float(m["dta_12hrs"]), "s1" if m["period"].endswith(focus) else "mute")]
        for m in months
    ]
    marks, height = vbars(cats, stacks, value_labels=False)
    top = max(r["dta_12hrs"] for r in months)
    slot = (WIDTH - 68) / len(months)
    for i, m in enumerate(months):
        if m["period"].endswith(focus) or m["dta_12hrs"] == top:
            x = 48 + i * slot + slot / 2
            y = 76 + 220 - 220 * m["dta_12hrs"] / top
            marks.append(f'<text class="val" x="{x:.1f}" y="{y - 6:.1f}" '
                         f'text-anchor="middle">{m["dta_12hrs"]}</text>')
    frame(
        "gloucestershire-ae-12-hour-waits",
        height,
        (
            "12-hour waits from decision to admit, Gloucestershire Hospitals",
            f"Monthly, {months[0]['period']} to {months[-1]['period']}; "
            "Septembers highlighted",
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


def private_rented_epc() -> None:
    """Privately rented homes below EPC C, by ward."""
    scores = load("epc-scores.json")
    names = {w["code"]: w["name"] for w in load("wards/index.json")["wards"]}
    wards = sorted(
        scores["private_rented_by_ward"].items(),
        key=lambda item: -item[1]["below_c"],
    )
    rows = [
        {
            "ward": names[code],
            "private_rented_homes": w["homes"],
            "below_c": w["below_c"],
            "below_c_pct": round(100 * w["below_c"] / w["homes"], 1),
            "below_c_could_reach_c": w["below_c_could_reach_c"],
        }
        for code, w in wards
    ]
    write_csv("cheltenham-private-rented-epc", rows)
    top = {r["ward"] for r in rows[:5]}
    marks, height = hbars(
        [(r["ward"], float(r["below_c"]), "s1" if r["ward"] in top else "mute") for r in rows],
        lambda v: f"{v:,.0f}",
        label_w=290,
    )
    frame(
        "cheltenham-private-rented-epc",
        height,
        (
            "Privately rented homes rated below EPC C, by ward",
            "Homes whose latest certificate records them as privately rented, rated D to G",
            "Source: Energy Performance of Buildings Register, MHCLG (OGL v3.0)",
        ),
        marks,
    )


def crime_missing() -> None:
    """Crime data post: monthly crimes published on police.uk for Cheltenham,
    with the months since February 2026 highlighted and labelled."""
    months = sorted(load("crime/index.json")["months"], key=lambda m: m["month"])
    rows = [
        {
            "month": m["month"],
            "crimes_published": sum(n["crime_count"] for n in m["neighbourhoods"]),
        }
        for m in months
    ]
    write_csv("cheltenham-crime-data-missing", rows)
    gap_from = "2026-02"  # first month published nearly empty
    cats = [r["month"][:4] if r["month"].endswith("-01") else "" for r in rows]
    stacks = [
        [(float(r["crimes_published"]), "s1" if r["month"] >= gap_from else "mute")]
        for r in rows
    ]
    marks, height = vbars(cats, stacks, value_labels=False)
    # The highlighted bars are almost flat, so print their counts: the numbers,
    # not the colour, carry the drop.
    slot = (WIDTH - 68) / len(rows)
    for i, r in enumerate(rows):
        if r["month"] >= gap_from:
            x = 48 + i * slot + slot / 2
            marks.append(f'<text class="val" x="{x:.1f}" y="{76 + 220 - 6}" '
                         f'text-anchor="middle">{r["crimes_published"]}</text>')
    frame(
        "cheltenham-crime-data-missing",
        height,
        (
            "Crimes published on police.uk, Cheltenham",
            f"Monthly, {rows[0]['month']} to {rows[-1]['month']}; "
            f"months since {gap_from} highlighted",
            "Source: Police.uk (OGL v3.0)",
        ),
        marks,
    )


OFSTED_GRADES = ("Outstanding", "Good", "Requires improvement", "Inadequate")
ABSENCE_YEAR = ("2024-09-01", "2025-08-31")  # the 2024/25 school year


def ofsted_grade_on(record: Row, day: str) -> tuple[str, str] | None:
    """The four-point Ofsted grade in force on `day`, with its inspection date.
    Inspections from September 2024 graded each area but gave no overall grade;
    for those, the quality of education grade stands in. Ungraded inspections
    keep the previous grade."""
    found = [(i["date"], i["outcome"]) for i in record["inspections"]
             if i["outcome"] in OFSTED_GRADES and i["date"] <= day]
    graded = record["graded"]
    if graded and graded["date"] <= day and not graded.get("overall") and graded["areas"]:
        quality = [a["grade"] for a in graded["areas"] if a["area"] == "Quality of education"]
        if quality:
            found.append((graded["date"], quality[0]))
    if not found:
        return None
    day_found, grade = max(found)
    return grade, day_found


def inside(point: tuple[float, float], ring: Sequence[Sequence[float]]) -> bool:
    """Whether a (lat, lon) point lies inside a polygon ring of [lat, lon] pairs."""
    lat, lon = point
    hit = False
    for (lat1, lon1), (lat2, lon2) in zip(ring, [ring[-1], *ring[:-1]]):
        if (lat1 > lat) != (lat2 > lat) and lon < (lon2 - lon1) * (lat - lat1) / (lat2 - lat1) + lon1:
            hit = not hit
    return hit


def school_ward_rows() -> list[Row]:
    """Cheltenham borough state primaries with 2024/25 absence, the deprivation
    of the ward each school sits in, and its Ofsted grade at the start and end
    of the school year."""
    dep = load("deprivation.json")
    ofsted = load("ofsted.json")["schools"]
    places = {s["urn_url"].rsplit("/", 1)[-1]: s for s in load("schools.json")}
    rows = []
    for school in load("school-absence.json")["schools"]:
        year = school.get("full_year")
        if school["phase"] != "Primary" or not year:
            continue
        place = places[school["urn"]]
        area = next((a for a in dep["lsoas"]
                     if any(inside((place["lat"], place["lon"]), ring) for ring in a["boundary"])),
                    None)
        if not area:
            continue  # outside Cheltenham borough
        ward = dep["wards"][area["ward_code"]]
        start = ofsted_grade_on(ofsted[school["urn"]], ABSENCE_YEAR[0])
        end = ofsted_grade_on(ofsted[school["urn"]], ABSENCE_YEAR[1])
        if not end:
            continue
        rows.append({
            "school": school["name"],
            "urn": school["urn"],
            "ward": ward["name"],
            "ward_deprivation_rank_in_cheltenham": ward["rank"],
            "ward_imd_score": ward["score"],
            "enrolments": year["enrolments"],
            "overall_absence_pct": year["overall"],
            "persistent_absence_pct": year["persistent"],
            "severe_absence_pct": year["severe"],
            "ofsted_grade_2024_09_01": start[0] if start else "",
            "ofsted_grade_2025_08_31": end[0],
            "ofsted_grade_date": end[1],
        })
    return sorted(rows, key=lambda r: (r["ward_deprivation_rank_in_cheltenham"],
                                       r["persistent_absence_pct"]))


def ward_offsets(rows: Sequence[Row]) -> list[float]:
    """Small sideways offsets so schools in the same ward don't overlap."""
    by_ward: dict[int, list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        by_ward[r["ward_deprivation_rank_in_cheltenham"]].append(i)
    offsets = [0.0] * len(rows)
    for members in by_ward.values():
        for j, i in enumerate(members):
            offsets[i] = (j - (len(members) - 1) / 2) * 0.36
    return offsets


def weighted(rows: Sequence[Row], field: str) -> float:
    """Enrolment-weighted rate across schools."""
    pupils = sum(r["enrolments"] for r in rows)
    return sum(r[field] * r["enrolments"] for r in rows) / pupils


WARD_TICKS = [(1, "1"), (5, "5"), (10, "10"), (15, "15"), (20, "20")]
WARD_AXIS = "Ward deprivation rank in Cheltenham (1 = most deprived of 20 wards)"
SHAPES = {"Outstanding": "diamond", "Good": "circle", "Requires improvement": "triangle"}


def school_absence_deprivation() -> None:
    """School absence post: persistent absence at each primary against the
    deprivation of its ward, with the Ofsted grade as the marker's shape."""
    slug = "cheltenham-school-absence-deprivation"
    rows = school_ward_rows()
    write_csv(slug, rows)
    plot = Scatter((0.5, 20.5), (0, 40))
    marks = plot.axes(WARD_TICKS, [(v, f"{v}%") for v in (0, 10, 20, 30, 40)],
                      (WARD_AXIS, "% of pupils persistently absent, 2024/25"))
    most = [r for r in rows if r["ward_deprivation_rank_in_cheltenham"] <= 5]
    least_wards = sorted({r["ward_deprivation_rank_in_cheltenham"] for r in rows})[-5:]
    least = [r for r in rows if r["ward_deprivation_rank_in_cheltenham"] in least_wards]
    split = plot.px(5.5)
    marks.append(f'<line class="divide" x1="{split:.1f}" x2="{split:.1f}" '
                 f'y1="{plot.top}" y2="{plot.base}"/>')
    marks.append(f'<text class="val" x="{split + 6:.1f}" y="{plot.top + 14}">'
                 f"5 most deprived wards: {weighted(most, 'persistent_absence_pct'):.1f}%"
                 "</text>")
    marks.append(f'<text class="val" x="{WIDTH - plot.right}" y="{plot.py(17):.1f}" '
                 f'text-anchor="end">5 least deprived wards with a primary: '
                 f"{weighted(least, 'persistent_absence_pct'):.1f}%</text>")
    for r, dx in zip(rows, ward_offsets(rows)):
        marks.append(marker(
            SHAPES[r["ofsted_grade_2025_08_31"]],
            plot.px(r["ward_deprivation_rank_in_cheltenham"] + dx),
            plot.py(r["persistent_absence_pct"]),
            "s1" if r in most else "mute",
        ))
    marks += shape_legend([(SHAPES[g], "mute", g)
                           for g in ("Outstanding", "Good", "Requires improvement")], 64)
    frame(
        slug,
        plot.base + 64,
        (
            "Persistent absence at Cheltenham primaries, by ward deprivation",
            f"{len(rows)} state primaries, 2024/25; schools in the 5 most deprived wards highlighted",
            "Source: DfE pupil absence; MHCLG IoD 2025; Ofsted (OGL v3.0)",
        ),
        marks,
    )


def school_ofsted_deprivation() -> None:
    """School absence post: each primary's Ofsted grade against the deprivation
    of its ward, with an arrow where the grade changed during 2024/25."""
    slug = "cheltenham-school-ofsted-deprivation"
    rows = school_ward_rows()
    write_csv(slug, rows)
    level = {"Outstanding": 3, "Good": 2, "Requires improvement": 1}
    counts = Counter(r["ofsted_grade_2025_08_31"] for r in rows)
    plot = Scatter((0.5, 20.5), (0.5, 3.5), left=170)
    marks = plot.axes(
        WARD_TICKS,
        [(v, f"{g} ({counts[g]})") for g, v in level.items()],
        (WARD_AXIS, "Ofsted grade at the end of 2024/25 (number of schools)"),
    )
    for r, dx in zip(rows, ward_offsets(rows)):
        x = r["ward_deprivation_rank_in_cheltenham"] + dx
        before, after = r["ofsted_grade_2024_09_01"], r["ofsted_grade_2025_08_31"]
        if before and before != after:
            marks.append(marker(SHAPES[before], plot.px(x), plot.py(level[before]), "ring"))
            marks += plot.arrow((x, level[before]), (x, level[after]))
            marks.append(marker(SHAPES[after], plot.px(x), plot.py(level[after]), "s1"))
            note_y = (plot.py(level[before]) + plot.py(level[after])) / 2 + 4
            marks.append(f'<text class="lab" x="{plot.px(x) - 10:.1f}" y="{note_y:.1f}" '
                         f'text-anchor="end">{escape(r["school"])}</text>')
        else:
            marks.append(marker(SHAPES[after], plot.px(x), plot.py(level[after]), "mute"))
    marks += shape_legend([("circle", "ring", "Grade on 1 September 2024"),
                           ("circle", "s1", "Grade after a 2024/25 inspection")], 64)
    frame(
        slug,
        plot.base + 64,
        (
            "Ofsted grades at Cheltenham primaries, by ward deprivation",
            f"{len(rows)} state primaries; arrows show grades that changed during 2024/25",
            "Source: Ofsted; MHCLG IoD 2025 (OGL v3.0)",
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
    "cheltenham-private-rented-epc": private_rented_epc,
    "cheltenham-crime-data-missing": crime_missing,
    "cheltenham-school-absence-deprivation": school_absence_deprivation,
    "cheltenham-school-ofsted-deprivation": school_ofsted_deprivation,
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
