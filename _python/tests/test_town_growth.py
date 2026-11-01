"""Offline tests for the local town growth job (local/process-town-growth.py):
when each 100 m square was first built up, dropping specks, hectares by
postcode district and the smoothed outlines for the map.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import numpy as np
import pytest

pytest.importorskip("rasterio")
pytest.importorskip("shapely")

from affine import Affine  # noqa: E402  (installed with rasterio)
from shapely.geometry import box, shape  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "town_growth", pathlib.Path(__file__).resolve().parents[1] / "local" / "process-town-growth.py"
)
assert SPEC is not None and SPEC.loader is not None
growth = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(growth)


def test_first_built_uses_threshold_and_never_unbuilds():
    stack = np.array([
        [[0, 2000, 0]],      # 1975
        [[500, 0, 1500]],    # 1980: the middle square dips below, but stays built up
        [[1200, 0, 0]],      # 1985
    ])
    first = growth.first_built(stack, threshold=1000)
    assert first.tolist() == [[2, 0, 1]]


def test_first_built_marks_never_built_squares():
    stack = np.zeros((3, 1, 2), dtype=np.int32)
    assert growth.first_built(stack, threshold=1000).tolist() == [[-1, -1]]


def test_drop_specks_removes_small_groups_only():
    first = np.array([
        [0, -1, -1, -1, 3],
        [0, -1, -1, -1, -1],
        [1, -1, 2, -1, -1],
        [-1, -1, 2, 5, -1],
    ])
    cleaned = growth.drop_specks(first, min_cells=3)
    # The left column (3 squares) and the diagonal-touching group of 3 stay;
    # the lone square top right goes.
    assert cleaned[0, 4] == -1
    assert cleaned[:3, 0].tolist() == [0, 0, 1]
    assert cleaned[2, 2] == 2 and cleaned[3, 2] == 2 and cleaned[3, 3] == 5


def test_hectares_are_cumulative_per_district():
    first = np.array([[0, 1, -1, 2]])
    masks = {"GL50": np.array([[True, True, False, False]]), "GL51": np.array([[False, False, True, True]])}
    assert growth.hectares(first, masks, years=3) == {"GL50": [1, 2, 2], "GL51": [0, 0, 1]}


def test_footprints_grow_and_bands_do_not_overlap():
    # 100 m squares: one built by the first year, its neighbour by the second.
    first = np.array([[0, 1, -1]])
    transform = Affine(100, 0, 0, 0, -100, 100)
    area = box(0, 0, 300, 100)
    bands = growth.bands(first, transform, years=2, area=area, smooth=20)
    assert bands[0] is not None and bands[1] is not None
    assert bands[0].intersection(bands[1]).area < 1
    assert bands[0].within(area.buffer(0.01)) and bands[1].within(area.buffer(0.01))
    assert 18000 < bands[0].area + bands[1].area <= 20001


def test_features_split_bands_by_district_with_labels():
    to_wgs = lambda x, y, z=None: (x, y)  # noqa: E731
    band = box(0, 0, 200, 100)
    districts = {"GL50": box(0, 0, 100, 100), "GL51": box(100, 0, 200, 100)}
    feats = growth.features([band, None], districts, [1975, 1980], to_wgs)
    assert [f["properties"] for f in feats] == [
        {"band": 0, "district": "GL50", "label": "By 1975"},
        {"band": 0, "district": "GL51", "label": "By 1975"},
    ]
    assert shape(feats[0]["geometry"]).area == pytest.approx(10000)


def test_summary_rows_and_total_with_display_strings():
    rows, total = growth.summary({"GL50": [900, 1200], "GL51": [400, 500]}, ["GL50", "GL51"])
    assert rows[0] == {"name": "GL50", "hectares": [900, 1200], "hectares_display": ["900", "1,200"],
                       "added": 300, "added_display": "300"}
    assert total == {"name": "Total", "hectares": [1300, 1700], "hectares_display": ["1,300", "1,700"],
                     "added": 400, "added_display": "400"}


def test_period_labels():
    assert growth.period_label(0, [1975, 1980]) == "By 1975"
    assert growth.period_label(1, [1975, 1980]) == "1975 to 1980"
