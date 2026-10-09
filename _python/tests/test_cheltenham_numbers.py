"""The Cheltenham in Numbers figures, built from the site's real data files:
every figure needs a value, a source and a link to a page that exists.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("cheltenham_numbers", ROOT / "_python" / "cheltenham-numbers.py")
numbers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(numbers)


def permalinks():
    links = set()
    for page in ROOT.glob("_pages/**/*.md"):
        match = re.search(r"^permalink:\s*(\S+)", page.read_text(encoding="utf-8"), re.M)
        if match:
            links.add(match.group(1).strip("\"'"))
    return links


def test_every_figure_has_a_value_a_source_and_a_real_page():
    pages = permalinks()
    figures = [f for group in numbers.build()["groups"] for f in group["figures"]]
    assert len(figures) >= 15
    for f in figures:
        assert f["value_display"], f["label"]
        assert f["source"], f["label"]
        assert f["link"] in pages, f"{f['label']} links to {f['link']}, which isn't a page"


def test_number_and_percentage_formatting():
    assert numbers.number(121452) == "121,452"
    assert numbers.pct(4894, 5496) == 89
    assert numbers.pct(1, 0) == 0
