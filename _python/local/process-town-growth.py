#!/usr/bin/env python3
"""Map how Cheltenham, Gloucester and the villages around them have been built
up since 1975, write _data/town-growth.json.

Run manually — not part of any scheduled workflow. The source is a fixed
release of the European Commission's Global Human Settlement Layer (GHSL), so
there is nothing new to fetch until the next release.

  pip install -r _python/requirements-dev.txt   (for rasterio and shapely)
  python _python/local/process-town-growth.py

GHS-BUILT-S R2023A estimates, for every 100 m square on Earth, how many square
metres are covered by buildings, every five years from 1975 to 2020 (its 2025
and 2030 layers are projections, so they are left out). A square counts as
built up once buildings cover THRESHOLD of it, and stays built up from then on.

The area is the nine postcode districts GL1 to GL4 (Gloucester) and GL50 to
GL54 (Cheltenham and the villages it serves), from the local postcode
boundaries in _data-sources/postcode-boundaries.geojson (gitignored). Groups
of fewer than MIN_CELLS squares are dropped as specks, then each year's
built-up area is smoothed so the outlines aren't blocky, and split into one
band per five-year period and per district for the map.

The ten GHSL tiles (about 100 MB) are downloaded once into _data-sources/ghsl/.

  Product:  https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php
  Licence:  CC BY 4.0, https://human-settlement.emergency.copernicus.eu/GHSLhowToCite.php
"""
import io
import json
import sys
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import geometry_mask, shapes
from rasterio.windows import from_bounds
from shapely import transform as shapely_transform
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
import helper  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "_data-sources"
CACHE = SOURCES / "ghsl"
BOUNDARIES = SOURCES / "postcode-boundaries.geojson"
OUT = ROOT / "_data" / "town-growth.json"

YEARS = [1975, 1980, 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020]
GLOUCESTER_DISTRICTS = ("GL1", "GL2", "GL3", "GL4")
DISTRICTS = list(GLOUCESTER_DISTRICTS + config.POSTCODE_DISTRICTS)
THRESHOLD = 1000       # m² of buildings in a 10,000 m² square: 10%
MIN_CELLS = 3          # smaller groups of squares are dropped as specks
SMOOTH = 50            # metres: rounds the corners of the 100 m squares
SIMPLIFY = 15          # metres
DECIMALS = 4           # about 10 metres, plenty for 100 m squares

TILE = "R3_C18"        # the 1,000 km GHSL tile holding Gloucestershire
FTP = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_BUILT_S_GLOBE_R2023A"
MOLLWEIDE = "ESRI:54009"

SOURCE = "European Commission Global Human Settlement Layer (GHS-BUILT-S R2023A)"
SOURCE_URL = "https://human-settlement.emergency.copernicus.eu/ghs_buS2023.php"
LICENCE = "Creative Commons Attribution 4.0 (CC BY 4.0)"
CITATION = ("Pesaresi, M. et al. (2024) Advances on the Global Human Settlement Layer by joint assessment "
            "of Earth Observation and population survey data. International Journal of Digital Earth, 17(1)")
CITATION_URL = "https://doi.org/10.1080/17538947.2024.2390454"


def first_built(stack, threshold):
    """For each square, the index of the first year it counts as built up, or -1 if never.
    Once built up a square stays built up, even if a later estimate dips."""
    built = np.maximum.accumulate(stack, axis=0) >= threshold
    return np.where(built.any(axis=0), built.argmax(axis=0), -1).astype(np.int16)


def drop_specks(first, min_cells):
    """Clear groups of built-up squares (touching on any side or corner) smaller than min_cells."""
    first = first.copy()
    rows, cols = first.shape
    seen = np.zeros(first.shape, dtype=bool)
    for r0, c0 in zip(*np.nonzero(first >= 0)):
        if seen[r0, c0]:
            continue
        group, queue = [], deque([(r0, c0)])
        seen[r0, c0] = True
        while queue:
            r, c = queue.popleft()
            group.append((r, c))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols and not seen[nr, nc] and first[nr, nc] >= 0:
                        seen[nr, nc] = True
                        queue.append((nr, nc))
        if len(group) < min_cells:
            for r, c in group:
                first[r, c] = -1
    return first


def hectares(first, masks, years):
    """Built-up hectares (one per 100 m square) in each district, for each year."""
    return {name: [int(((first >= 0) & (first <= k) & mask).sum()) for k in range(years)]
            for name, mask in masks.items()}


def bands(first, transform, years, area, smooth):
    """One shape per period holding the land first built up in it. Each year's whole built-up
    area is smoothed, so the bands fit together without gaps or overlaps."""
    result, previous = [], None
    for k in range(years):
        squares = [shape(g) for g, _ in shapes(np.uint8((first >= 0) & (first <= k)),
                                                mask=(first >= 0) & (first <= k), transform=transform)]
        if not squares:
            result.append(None)
            continue
        built = unary_union(squares).buffer(smooth).buffer(-smooth).intersection(area)
        if previous is not None:
            built = built.union(previous)
        band = built if previous is None else built.difference(previous)
        result.append(None if band.is_empty else band)
        previous = built
    return result


def summary(totals, order):
    """Table rows per district plus a total, each with hectares by year and hectares added since the first."""
    def row(name, values):
        return {"name": name, "hectares": values, "hectares_display": [f"{v:,}" for v in values],
                "added": values[-1] - values[0], "added_display": f"{values[-1] - values[0]:,}"}
    rows = [row(name, totals[name]) for name in order]
    return rows, row("Total", [sum(col) for col in zip(*(totals[name] for name in order))])


def period_label(k, years):
    return f"By {years[0]}" if k == 0 else f"{years[k - 1]} to {years[k]}"


def rounded(geometry):
    return json.loads(json.dumps(mapping(geometry)), parse_float=lambda v: round(float(v), DECIMALS))


def features(band_shapes, districts, years, to_wgs):
    """Each band split by postcode district, in longitude/latitude, for map popups."""
    out = []
    for k, band in enumerate(band_shapes):
        if band is None:
            continue
        for name, district in districts.items():
            part = band.intersection(district).simplify(SIMPLIFY)
            if part.is_empty or part.area < 1:
                continue
            geo = shapely_transform(part, lambda xy: np.column_stack(to_wgs(xy[:, 0], xy[:, 1])))
            out.append({"type": "Feature", "properties": {"band": k, "district": name, "label": period_label(k, years)},
                        "geometry": rounded(geo)})
    return out


def tile_path(year):
    name = f"GHS_BUILT_S_E{year}_GLOBE_R2023A_54009_100"
    path = CACHE / f"{name}_V1_0_{TILE}.tif"
    if not path.exists():
        print(f"  downloading {year} tile", flush=True)
        resp = helper.get(f"{FTP}/{name}/V1-0/tiles/{name}_V1_0_{TILE}.zip", timeout=300)
        resp.raise_for_status()
        CACHE.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            z.extract(path.name, CACHE)
    return path


def main():
    to_moll = Transformer.from_crs(4326, MOLLWEIDE, always_xy=True).transform
    to_wgs = Transformer.from_crs(MOLLWEIDE, 4326, always_xy=True).transform

    with open(BOUNDARIES, encoding="utf-8") as f:
        outlines = {feat["properties"]["name"]: shape(feat["geometry"]) for feat in json.load(f)["features"]
                    if feat["properties"]["name"] in DISTRICTS}
    missing = set(DISTRICTS) - set(outlines)
    if missing:
        sys.exit(f"Missing postcode districts in {BOUNDARIES}: {sorted(missing)}")
    districts = {name: shapely_transform(g, lambda xy: np.column_stack(to_moll(xy[:, 0], xy[:, 1]))).buffer(0)
                 for name, g in outlines.items()}
    area = unary_union(list(districts.values()))

    print("Reading GHSL built-up surface...")
    layers = []
    for year in YEARS:
        with rasterio.open(tile_path(year)) as src:
            window = from_bounds(*area.bounds, src.transform).round_offsets().round_lengths()
            layers.append(src.read(1, window=window).astype(np.int32))
            transform = src.window_transform(window)
    first = first_built(np.array(layers), THRESHOLD)
    masks = {name: ~geometry_mask([mapping(g)], first.shape, transform) for name, g in districts.items()}
    first[~np.any(list(masks.values()), axis=0)] = -1
    first = drop_specks(first, MIN_CELLS)

    band_shapes = bands(first, transform, len(YEARS), area, SMOOTH)
    rows, total = summary(hectares(first, masks, len(YEARS)), DISTRICTS)
    district_outlines = [{"type": "Feature", "properties": {"name": name},
                          "geometry": rounded(outlines[name].simplify(0.0003))} for name in DISTRICTS]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "citation": CITATION,
        "citation_url": CITATION_URL,
        "threshold_percent": THRESHOLD // 100,
        "years": YEARS,
        "periods": [period_label(k, YEARS) for k in range(len(YEARS))],
        "districts": rows,
        "total": total,
        "outlines": {"type": "FeatureCollection", "features": district_outlines},
        "bands": {"type": "FeatureCollection", "features": features(band_shapes, districts, YEARS, to_wgs)},
    }
    written = helper.write_json(OUT, output)
    print(f"{'Wrote' if written else 'No change to'} {len(output['bands']['features'])} band shapes in "
          f"{OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
    for d in output["districts"]:
        print(f"  {d['name']}: {d['hectares'][0]:,} ha in {YEARS[0]}, {d['hectares'][-1]:,} ha in {YEARS[-1]}")


if __name__ == "__main__":
    main()
