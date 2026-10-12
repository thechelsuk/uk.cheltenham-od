"""Offline tests for the toilet map fetcher (toilets.py): opening times, the
junk-entry heuristics, record clean-up, the Cheltenham filter and the export
link scrape. requests.get is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import pytest
import requests

import helper
import toilets

OPEN_9_5 = [["09:00", "17:00"]] * 5 + [[], []]


def toilet(id_="t1", name="Montpellier Gardens", area="Cheltenham", **extra):
    return {"id": id_, "name": name, "areas": {"name": area},
            "location": {"coordinates": [-2.08, 51.89]}, **extra}


@pytest.fixture(autouse=True)
def keyword_checks_only(monkeypatch):
    """Run the heuristics without the optional profanity library, so results
    don't depend on whether it is installed."""
    monkeypatch.setattr(toilets, "HAS_PROFANITY_LIB", False)


def test_parse_opening_times_labels_each_day():
    parsed = toilets.parse_opening_times([["00:00", "00:00"], [], ["08:00", "18:00"], ["bad"]])
    assert parsed == {"monday": "24 hours", "tuesday": "closed", "wednesday": "08:00-18:00",
                      "thursday": "unknown", "friday": None, "saturday": None, "sunday": None}
    assert toilets.parse_opening_times(None) is None
    assert toilets.parse_opening_times("Mon-Fri") is None


def test_summarise_opening_times_groups_runs_of_days():
    assert toilets.summarise_opening_times(toilets.parse_opening_times(OPEN_9_5)) == \
        "Mon-Fri 09:00-17:00, Sat-Sun closed"
    one_day = toilets.parse_opening_times([[]] * 6 + [["10:00", "16:00"]])
    assert toilets.summarise_opening_times(one_day) == "Mon-Sat closed, Sun 10:00-16:00"
    assert toilets.summarise_opening_times(None) is None


def test_has_implausible_price():
    assert toilets.has_implausible_price("£20 entry")
    assert not toilets.has_implausible_price("£0.50 or 50p")
    assert not toilets.has_implausible_price("")


@pytest.mark.parametrize("rec, reason", [
    ({"name": "Pee in bush"}, "keyword match"),
    ({"name": "Station", "notes": "test entry"}, "keyword match"),
    ({"name": "Pump Room", "payment_details": "£ 9.99"}, "implausible price"),
    ({"name": "Hedge"}, "generic/implausible name"),
    ({"name": "AB"}, "name too short"),
    ({"name": "Garage", "opening_times": [["00:00", "00:00"]] * 7},
     "24/7 hours + single-word name (likely placeholder)"),
])
def test_is_likely_junk_flags_joke_entries(rec, reason):
    assert toilets.is_likely_junk(rec) == (True, reason)


def test_is_likely_junk_passes_real_toilets():
    assert toilets.is_likely_junk({"name": "BP Garage", "opening_times": [["00:00", "00:00"]] * 7}) == (False, "")
    assert toilets.is_likely_junk({"name": "Pittville Pump Room", "payment_details": "20p"}) == (False, "")


def test_is_likely_junk_uses_the_profanity_library_when_present(monkeypatch):
    class Profanity:
        @staticmethod
        def contains_profanity(text):
            return "rude" in text.lower()

    monkeypatch.setattr(toilets, "HAS_PROFANITY_LIB", True)
    monkeypatch.setattr(toilets, "profanity", Profanity, raising=False)
    assert toilets.is_likely_junk({"name": "Rude Loo"}) == (True, "profanity")


def test_clean_record_flattens_location_and_tidies_the_name():
    rec = toilet(name="  ASDA cheltenham  ", accessible=True, radar=True, opening_times=OPEN_9_5)
    cleaned = toilets.clean_record(rec)
    assert cleaned["name"] == "ASDA Cheltenham"
    assert (cleaned["latitude"], cleaned["longitude"]) == (51.89, -2.08)
    assert cleaned["maps_url"] == "https://www.google.com/maps/search/?api=1&query=51.89,-2.08"
    assert cleaned["radar_key"] is True and cleaned["accessible"] is True
    assert cleaned["opening_hours_summary"] == "Mon-Fri 09:00-17:00, Sat-Sun closed"


def test_filter_records_keeps_named_cheltenham_toilets_and_counts_drops():
    records = [
        toilet("a"),
        toilet("2319b85caf99ec61aba515e4"),          # on the ignore list
        toilet("b", area="Tewkesbury"),
        {"id": "c", "areas": None, "name": "No area"},
        toilet("d", name="   "),
        toilet("e", name="Wee stop"),
    ]
    clean, dropped = toilets.filter_records(records, "Cheltenham")
    assert [r["id"] for r in clean] == ["a"]
    assert dropped == 2


class FakeResponse:
    def __init__(self, text="", body=None):
        self.text, self._body = text, body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def test_find_json_download_url_picks_the_json_export(monkeypatch):
    page = ("<a href='https://x.blob.vercel-storage.com/exports/toilets-1.csv?download=1'>CSV</a>"
            '<a href="https://x.blob.vercel-storage.com/exports/toilets-1.json?download=1&amp;v=2">JSON</a>')
    monkeypatch.setattr(helper, "get", lambda url, timeout: FakeResponse(page))
    assert toilets.find_json_download_url() == \
        "https://x.blob.vercel-storage.com/exports/toilets-1.json?download=1&v=2"

    monkeypatch.setattr(helper, "get", lambda url, timeout: FakeResponse("<p>new layout</p>"))
    with pytest.raises(ValueError, match="markup may have changed"):
        toilets.find_json_download_url()


def test_main_sorts_by_name_and_falls_back_to_the_last_known_export(monkeypatch, tmp_path):
    def no_page():
        raise requests.ConnectionError("down")

    fetched = []
    monkeypatch.setattr(toilets, "find_json_download_url", no_page)
    monkeypatch.setattr(toilets, "fetch_data", lambda url: fetched.append(url) or
                        [toilet("z", name="Sandford Park"), toilet("y", name="imperial gardens")])
    monkeypatch.setattr(helper, "repo_root", lambda: tmp_path)
    written = {}
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.update(path=path, payload=payload))

    toilets.main()

    assert fetched == [toilets.FALLBACK_SOURCE_URL]
    assert written["path"] == tmp_path / "_data/toilets.json"
    assert [r["name"] for r in written["payload"]] == ["Imperial Gardens", "Sandford Park"]


def test_main_exits_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(toilets, "find_json_download_url", lambda: "https://example.org/x.json")
    monkeypatch.setattr(toilets, "fetch_data", lambda url: [toilet(area="Elsewhere")])
    with pytest.raises(SystemExit):
        toilets.main()


def test_fetch_data_returns_the_json(monkeypatch):
    monkeypatch.setattr(helper, "get", lambda url, timeout: FakeResponse(body=[1]))
    assert toilets.fetch_data("https://example.org/x.json") == [1]
