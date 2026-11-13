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


def works(street, tm, start, end, ward="Lansdown", kind="Planned", promoter="Severn Trent Water"):
    return {"street": street, "ward": ward, "ward_slug": ward.lower().replace(" ", "-") if ward else "",
            "kind": kind, "traffic_management": tm, "start": start, "end": end, "promoter": promoter}


WEEK = (newsletter.date(2026, 11, 2), newsletter.date(2026, 11, 8))


def test_local_works_keep_closures_and_longer_traffic_control_in_the_borough():
    items = [
        works("Hall Road", "Road closure", "2026-11-03", "2026-11-03"),
        works("Queens Road", "Multi-way signals", "2026-11-02", "2026-11-05"),
        works("Short Lights", "Two-way signals", "2026-11-04", "2026-11-05"),       # under 3 days
        works("Pavement Only", "Some carriageway incursion", "2026-11-02", "2026-11-20"),
        works("Outside Town", "Road closure", "2026-11-03", "2026-11-04", ward=""),  # no ward
        works("Already Started", "Road closure", "2026-10-20T08:00", "2026-11-04"),
        works("Next Week", "Road closure", "2026-11-09", "2026-11-10"),
        works("Burst Main", "Road closure", "2026-11-03", "2026-11-04", kind="Unplanned"),
        works("Odd Spelling", "lane_closure", "2026-11-06", "2026-11-09"),
    ]
    picked = newsletter.local_street_works(items, *WEEK)
    assert [p["street"] for p in picked] == ["Hall Road", "Odd Spelling", "Queens Road"]


def test_local_works_on_one_street_share_a_line():
    items = [
        works("Church Road", "Two-way signals", "2026-11-02", "2026-11-04", ward="Leckhampton"),
        works("Church Road", "Road closure", "2026-11-03", "2026-11-07", ward="Leckhampton",
              promoter="Gloucestershire County Council"),
    ]
    [line] = newsletter.local_street_works(items, *WEEK)
    assert line["effect"] == "road closed"
    assert (line["start"], line["end"]) == ("2026-11-02", "2026-11-07")
    assert line["promoters"] == ["Severn Trent Water", "Gloucestershire County Council"]


def test_local_works_put_closures_first_and_stop_at_the_cap():
    items = [works(f"Lights {n}", "Multi-way signals", "2026-11-02", "2026-11-06") for n in range(10)]
    items.append(works("Closed Road", "Road closure", "2026-11-08", "2026-11-08"))
    picked = newsletter.local_street_works(items, *WEEK)
    assert len(picked) == newsletter.MAX_STREET_WORKS
    assert picked[0]["street"] == "Closed Road"


def test_roadworks_section_lists_local_works_after_national_highways(monkeypatch):
    data = {
        "roadworks.json": {"items": [{"roads": ["M5"], "description": "Lane closed at junction 11.",
                                      "start": "2026-11-01", "end": "2026-11-20", "distance_miles": 3}]},
        "street-works.json": {"items": [
            works("Queens Road", "Multi-way signals", "2026-11-02", "2026-11-05"),
            works("Hall Road", "Road closure", "2026-11-03", "2026-11-03", ward="Leckhampton",
                  promoter="Gloucestershire County Council"),
            works("Long Job", "Two-way signals", "2026-10-30", "2026-12-04", ward="Park"),
        ]},
    }
    monkeypatch.setattr(newsletter, "load", data.get)
    section = newsletter.roadworks_section(*WEEK)
    lines = section.splitlines()
    assert lines[0].startswith("- **M5**")
    assert "- **Hall Road, Leckhampton:** road closed, 3 November (Gloucestershire County Council)." in lines
    assert "- **Queens Road, Lansdown:** temporary traffic lights, 2 to 5 November (Severn Trent Water)." in lines
    assert "Long Job" not in section
    assert "/cheltenham-street-works" in section


def test_works_dates_read_naturally_across_months():
    assert newsletter.date_span("2026-11-03", "2026-11-03") == "3 November"
    assert newsletter.date_span("2026-11-30", "2026-12-02") == "30 November to 2 December"
    assert newsletter.date_span("2026-11-03", None) == "from 3 November"


def test_roadworks_section_says_so_when_nothing_is_planned(monkeypatch):
    monkeypatch.setattr(newsletter, "load", {"roadworks.json": {"items": []},
                                             "street-works.json": {"items": []}}.get)
    assert newsletter.roadworks_section(*WEEK) == "No roadworks are expected to affect Cheltenham this week."


def test_prune_candidate_events_drops_only_past_ones(tmp_path):
    # Hand-added candidate events tidy themselves: anything that ended before the
    # issue date goes, a multi-day event stays until its last day has passed.
    path = tmp_path / "candidate-events.json"
    path.write_text(newsletter.json.dumps({"source": "x", "events": [
        {"title": "Gone", "date": "2026-11-01", "link": "https://example.org/a"},
        {"title": "Still running", "date": "2026-11-01", "end_date": "2026-11-20", "link": "https://example.org/b"},
        {"title": "Today", "date": "2026-11-16", "link": "https://example.org/c"},
        {"title": "Later", "date": "2026-12-01", "link": "https://example.org/d"},
    ]}), encoding="utf-8")
    dropped = newsletter.prune_candidate_events(newsletter.date(2026, 11, 16), path)
    assert dropped == 1
    titles = [e["title"] for e in newsletter.json.loads(path.read_text(encoding="utf-8"))["events"]]
    assert titles == ["Still running", "Today", "Later"]


def test_prune_candidate_events_leaves_the_file_alone_when_nothing_has_passed(tmp_path):
    path = tmp_path / "candidate-events.json"
    original = '{"events": [{"title": "Later", "date": "2026-12-01", "link": "https://example.org/d"}]}'
    path.write_text(original, encoding="utf-8")
    assert newsletter.prune_candidate_events(newsletter.date(2026, 11, 16), path) == 0
    assert path.read_text(encoding="utf-8") == original


def test_prune_candidate_events_without_a_file(tmp_path):
    assert newsletter.prune_candidate_events(newsletter.date(2026, 11, 16), tmp_path / "missing.json") == 0
