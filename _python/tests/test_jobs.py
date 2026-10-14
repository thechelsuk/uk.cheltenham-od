"""Offline tests for the Work Hub jobs importer (jobs.py): date, salary and
summary tidying, the search and job page scrapers, the local-place filter,
and the classified adverts it writes and expires. helper.get is replaced
with a fake and adverts are written to a temporary folder.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
from datetime import date, timedelta

import pytest

import helper
import jobs

SEARCH_HTML = """<html><body>
<div data-testid="searchResultCard-0a1b2c3d4e5f6071">
  <h2><a data-testid="jobTitle-0a1b2c3d4e5f6071">Care Worker</a></h2>
  <div data-testid="searchResultCardEmployer"><span>Sunrise Care</span><span>- Prestbury, GL52</span></div>
  <p class="govuk-!-font-weight-bold">£12.60 to £12.60 an hour</p>
  <p data-testid="searchResultCardJobDescription">Help people live well at home.</p>
</div>
<div data-testid="searchResultCard-ffff000011112222">
  <h2><a data-testid="jobTitle-ffff000011112222">Remote analyst</a></h2>
  <p class="govuk-!-font-weight-bold"> </p>
</div>
</body></html>"""

JOB_HTML = """<html><body><dl>
<dt>Hours:</dt><dd>37.5 hours a week</dd>
<dt>Location:</dt><dd>Prestbury, Cheltenham</dd>
<dt>Working pattern:</dt><dd>Shifts</dd>
<dt>Job type:</dt><dd>Permanent</dd>
<dt>Posting date:</dt><dd>5 Oct 2026</dd>
<dt>Closing date:</dt><dd>14 Sept 2026</dd>
</dl></body></html>"""


class FakeResponse:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def classifieds(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "CLASSIFIEDS", tmp_path)
    return tmp_path


def test_long_date_reads_short_and_long_month_names():
    assert jobs.long_date("14 Sept 2026") == date(2026, 9, 14)
    assert jobs.long_date("24  October 2026") == date(2026, 10, 24)
    assert jobs.long_date("") is None


def test_tidy_salary_collapses_a_range_with_equal_ends():
    assert jobs.tidy_salary("£15 to £15 an hour") == "£15 an hour"
    assert jobs.tidy_salary("£25,000 to £28,000 a year") == "£25,000 to £28,000 a year"


def test_summary_keeps_whole_sentences_up_to_the_limit(monkeypatch):
    monkeypatch.setattr(jobs, "SUMMARY_CHARS", 30)
    assert jobs.summary("  Short   text. ") == "Short text."
    assert jobs.summary("First sentence here. Second sentence is long.") == "First sentence here."
    assert jobs.summary("One very long sentence without any stop at all in it") == "One very long sentence…"


def test_search_page_reads_each_result_card(monkeypatch):
    asked = []
    monkeypatch.setattr(helper, "get", lambda url, params=None: asked.append((url, params)) or FakeResponse(SEARCH_HTML))
    care, remote = jobs.search_page(2)
    assert asked[0][1]["pageNumber"] == "2" and asked[0][1]["milesFromPostcode"] == "5"
    assert care == {"id": "0a1b2c3d4e5f6071", "title": "Care Worker", "company": "Sunrise Care",
                    "location": "Prestbury, GL52", "salary": "£12.60 an hour",
                    "summary": "Help people live well at home."}
    assert remote == {"id": "ffff000011112222", "title": "Remote analyst", "company": None,
                      "location": None, "salary": None, "summary": ""}


def test_job_details_reads_the_labelled_fields(monkeypatch):
    monkeypatch.setattr(helper, "get", lambda url: FakeResponse(JOB_HTML))
    assert jobs.job_details("abc") == {
        "location": "Prestbury, Cheltenham",
        "hours": "37.5 hours a week",
        "job_type": "Permanent",
        "posted": date(2026, 10, 5),
        "closes": date(2026, 9, 14),
    }


def test_job_details_without_the_fields(monkeypatch):
    monkeypatch.setattr(helper, "get", lambda url: FakeResponse("<p>Gone</p>"))
    assert jobs.job_details("abc") == {"location": None, "hours": None, "job_type": None,
                                       "posted": None, "closes": None}


def test_is_local_by_place_name_or_postcode_district():
    assert jobs.is_local("Bishop's Cleeve, Gloucestershire")
    assert jobs.is_local(None, "Unit 4, GL51 9TH")
    assert not jobs.is_local("Gloucester, GL1 2AA", None)
    assert not jobs.is_local("GL510")


def test_slug_is_short_and_url_safe():
    assert jobs.slug("Care Worker (Nights) – £13/hr!") == "care-worker-nights-13-hr"
    assert len(jobs.slug("word " * 30)) <= 60


def test_write_advert_lists_for_a_week_or_until_closing(classifieds):
    today = date(2026, 10, 12)
    job = {"id": "0a1b2c3d4e5f6071", "title": "Care Worker", "company": "Sunrise Care",
           "location": "Prestbury", "salary": None, "summary": "Help people \"live\" well."}
    jobs.write_advert(job, {"hours": "Full time", "job_type": "Permanent", "posted": date(2026, 10, 11),
                            "closes": date(2026, 10, 15), "location": None}, today)
    path = classifieds / "2026-10-12-care-worker-4e5f6071.md"
    text = path.read_text(encoding="utf-8")
    assert 'title: "Care Worker"' in text
    assert 'job_type: "Full time, Permanent"' in text
    assert "date: 2026-10-12\nexpires: 2026-10-15\ncloses: 2026-10-15\n" in text
    assert "salary" not in text
    assert 'Help people "live" well.' in text
    assert "Posted on GOV.UK on 2026-10-11, applications close 2026-10-15." in text
    assert jobs.existing() == {"0a1b2c3d4e5f6071": path}


def test_write_advert_without_dates_uses_today_and_a_week(classifieds):
    today = date(2026, 10, 12)
    job = {"id": "abc", "title": "Cook", "company": None, "location": None, "salary": None, "summary": ""}
    jobs.write_advert(job, {"hours": None, "job_type": None, "posted": None, "closes": None}, today)
    text = (classifieds / "2026-10-12-cook-abc.md").read_text(encoding="utf-8")
    assert "expires: 2026-10-19" in text and "job_type" not in text and "closes" not in text
    assert "Posted on GOV.UK on 2026-10-12." in text


def test_existing_ignores_hand_written_adverts(classifieds):
    (classifieds / "barista.md").write_text("---\ntitle: Barista\n---\n", encoding="utf-8")
    assert jobs.existing() == {}


def test_main_expires_old_adverts_and_adds_new_local_jobs(classifieds, monkeypatch):
    today = date.today()
    old = classifieds / "old.md"
    old.write_text(f'---\njob_id: "aaa"\nexpires: {(today - timedelta(days=1)).isoformat()}\n---\n', encoding="utf-8")
    kept = classifieds / "kept.md"
    kept.write_text(f'---\njob_id: "bbb"\nexpires: {today.isoformat()}\n---\n', encoding="utf-8")

    def card(job_id, location):
        return {"id": job_id, "title": f"Job {job_id}", "company": "Co", "location": location,
                "salary": None, "summary": ""}

    pages = [[card("bbb", "Cheltenham"), card("ccc", "Cheltenham ,  GL50"), card("ddd", "Bristol"),
              card("eee", None), card("fff", None), card("ccc", "Cheltenham")], []]
    details = {
        "ccc": {"location": None, "hours": None, "job_type": None, "posted": None, "closes": None},
        "eee": {"location": "Gloucester", "hours": None, "job_type": None, "posted": None, "closes": None},
        "fff": {"location": "Leckhampton", "hours": None, "job_type": None, "posted": None,
                "closes": today - timedelta(days=1)},
    }
    opened = []
    monkeypatch.setattr(jobs, "search_page", lambda number: pages[number - 1])
    monkeypatch.setattr(jobs, "job_details", lambda job_id: opened.append(job_id) or details[job_id])
    monkeypatch.setattr(jobs.time, "sleep", lambda s: None)

    jobs.main()

    assert not old.exists() and kept.exists()
    assert opened == ["ccc", "eee", "fff"]
    (added,) = [p for p in classifieds.glob("*.md") if p not in (kept,)]
    assert 'job_id: "ccc"' in added.read_text(encoding="utf-8")
    assert 'location: "Cheltenham, GL50"' in added.read_text(encoding="utf-8")
