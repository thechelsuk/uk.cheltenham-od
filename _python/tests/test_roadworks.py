"""Offline tests for the National Highways roadworks fetcher (roadworks.py):
finding the newest weekly file, parsing dates and descriptions, and the
distance filter. requests.get is replaced with a fake.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import json
from datetime import date, datetime, timedelta

import pytest
import requests

import helper
import roadworks

LONDON = roadworks.LONDON
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=LONDON)


def bng(lat, lon):
    return roadworks._to_bng.transform(lon, lat)


def works(event, sdate, edate, lat, lon, roads=("M5",), description="Lane closure&#10;for resurfacing", **attrs):
    easting, northing = bng(lat, lon)
    road_xml = "".join(f'<ROAD ROAD_NUMBER="{r}"/>' for r in roads)
    extra = "".join(f' {k}="{v}"' for k, v in attrs.items())
    return (f'<HE_PLANNED_WORKS NEW_EVENT_NUMBER="{event}" SDATE="{sdate}" EDATE="{edate}" '
            f'DESCRIPTION="{description}" CLOSURE_TYPE="Planned Works" EXPDEL="Slight (less than 10 mins)"{extra}>'
            f'<EASTNORTH CENTRE_EASTING="{easting}" CENTRE_NORTHING="{northing}"/>'
            f'<ROADS>{road_xml}</ROADS></HE_PLANNED_WORKS>')


def xml(*items):
    return f'<Report xmlns="WebTeam"><HE_PLANNED_WORKS_COLLECTION>{"".join(items)}</HE_PLANNED_WORKS_COLLECTION></Report>'.encode()


def test_parse_datetime_reads_the_files_format():
    assert roadworks.parse_datetime("21-sep-2026 21:00") == datetime(2026, 9, 21, 21, 0, tzinfo=LONDON)
    assert roadworks.parse_datetime("") is None
    assert roadworks.parse_datetime(None) is None


def test_clean_description_turns_lines_into_sentences():
    assert roadworks.clean_description("M5 northbound\n  Jct 11  \n\nLane 1 closed.") == \
        "M5 northbound. Jct 11. Lane 1 closed."
    assert roadworks.clean_description(None) == ""


def test_parse_works_keeps_current_nearby_works_in_start_order():
    lat, lon = roadworks.LAT, roadworks.LNG
    doc = xml(
        works("B", "13-OCT-2026 20:00", "14-OCT-2026 06:00", lat + 0.01, lon, roads=("A40", "A40", "M5")),
        works("A", "10-OCT-2026 20:00", "15-OCT-2026 06:00", lat, lon),
        works("OLD", "01-OCT-2026 20:00", "02-OCT-2026 06:00", lat, lon),
        works("FAR", "13-OCT-2026 20:00", "14-OCT-2026 06:00", 52.9, -2.0),
        works("NODATE", "", "14-OCT-2026 06:00", lat, lon),
        '<HE_PLANNED_WORKS NEW_EVENT_NUMBER="NOPOINT" SDATE="13-OCT-2026 20:00" EDATE="14-OCT-2026 06:00"/>',
    )
    items = roadworks.parse_works(doc, NOW)
    assert [i["id"] for i in items] == ["A", "B"]
    first, second = items
    assert first["in_progress"] is True and second["in_progress"] is False
    assert first["distance_miles"] == 0.0
    assert first["lat"] == pytest.approx(lat, abs=1e-5) and first["lon"] == pytest.approx(lon, abs=1e-5)
    assert first["description"] == "Lane closure. for resurfacing."
    assert second["roads"] == ["A40", "M5"]
    assert (second["start"], second["end"]) == ("2026-10-13T20:00", "2026-10-14T06:00")


class FakeResponse:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def test_fetch_latest_file_walks_back_to_the_newest_published(monkeypatch):
    urls = []

    def fake_get(url, headers, timeout):
        urls.append(url)
        return FakeResponse(200, b"<xml/>") if url.endswith("nh_roadworks_2026_5_10.xml") else FakeResponse(403)

    monkeypatch.setattr(roadworks.requests, "get", fake_get)
    day, url, content = roadworks.fetch_latest_file(date(2026, 10, 12))
    assert day == date(2026, 10, 5) and content == b"<xml/>"
    assert urls[0].endswith("nh_roadworks_2026_12_10.xml") and len(urls) == 8


def test_fetch_latest_file_raises_on_a_real_error_or_nothing_found(monkeypatch):
    monkeypatch.setattr(roadworks.requests, "get", lambda url, headers, timeout: FakeResponse(500))
    with pytest.raises(requests.HTTPError):
        roadworks.fetch_latest_file(date(2026, 10, 12))
    monkeypatch.setattr(roadworks.requests, "get", lambda url, headers, timeout: FakeResponse(404))
    with pytest.raises(RuntimeError, match="No National Highways"):
        roadworks.fetch_latest_file(date(2026, 10, 12))


def test_main_writes_works_and_starts_a_history(tmp_path, monkeypatch):
    out, history = tmp_path / "roadworks.json", tmp_path / "roadworks-history.json"
    monkeypatch.setattr(roadworks, "OUT", str(out))
    monkeypatch.setattr(roadworks, "HISTORY_OUT", str(history))
    start = datetime.now(LONDON) - timedelta(hours=1)
    end = start + timedelta(days=2)
    fmt = "%d-%b-%Y %H:%M"
    doc = xml(works("A", start.strftime(fmt).upper(), end.strftime(fmt).upper(), roadworks.LAT, roadworks.LNG))
    monkeypatch.setattr(roadworks, "fetch_latest_file", lambda today: (today, "https://example.org/f.xml", doc))

    roadworks.main()

    data = json.loads(out.read_text())
    assert [i["id"] for i in data["items"]] == ["A"] and data["file_url"] == "https://example.org/f.xml"
    hist = json.loads(history.read_text())
    assert hist["tracking_since"] == datetime.now(LONDON).date().isoformat()
    assert len(hist["records"]) == 1

    written = []
    monkeypatch.setattr(helper, "write_json", lambda path, payload: written.append(payload))
    roadworks.main()
    assert written[1]["tracking_since"] == hist["tracking_since"]
