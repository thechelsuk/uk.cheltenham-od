"""Offline tests for the weekly newsletter draft (local/weekly-newsletter.py).
The issue is pasted into Buttondown, so every link has to work off the site.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "weekly_newsletter", pathlib.Path(__file__).resolve().parents[1] / "local" / "weekly-newsletter.py"
)
assert SPEC is not None and SPEC.loader is not None
newsletter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(newsletter)


def test_top_stories_leave_out_our_own_posts(monkeypatch):
    # Our posts are already in "New on Cheltenham Open Data". They are spotted by
    # link, not source name: the name changed once and they slipped through,
    # with site-relative links that broke in Buttondown.
    archive = {"items": [
        {"title": "Growth Mapped", "link": "/news/cheltenham-growth-added.html",
         "source": "Cheltenham Open Data News"},
        {"title": "Energy Mapped", "link": "https://example.org/news/energy.html", "source": "Anything"},
        {"title": "BBC Story", "link": "https://www.bbc.co.uk/news/x", "source": "BBC News"},
    ]}
    monkeypatch.setattr(newsletter, "load", lambda name: archive)
    monkeypatch.setattr(newsletter, "SITE_URL", "https://example.org")
    section = newsletter.top_stories_section()
    assert "BBC Story" in section
    assert "Growth Mapped" not in section and "Energy Mapped" not in section
