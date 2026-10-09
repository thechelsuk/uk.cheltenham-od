"""The combined alerts feed, feeds/alerts.xml: the newest entries from the
site's alert feeds (flood warnings, power cuts, bus disruptions, wildfire
risk, unplanned road closures and security alerts) in one place.

Only the Pi scripts (pi/power.py, pi/buses.py and pi/unplanned-closures.py)
call rebuild(), every five minutes. The daily GitHub workflow writes the flood,
wildfire and security feeds but never this file, so the two can't make
conflicting changes to it; their entries join it on the Pi's next run. Entries keep the id, link and
wording of their own feed, with a label in front of the title (unless the title
already starts with it) and an Atom category, so a feed reader can tell them
apart or filter them."""
import xml.etree.ElementTree as ET
from datetime import datetime

import helper

ATOM = "{http://www.w3.org/2005/Atom}"
LIMIT = 100

# (feed file under feeds/, label for its entries)
SOURCES = [
    ("flood.xml", "Flood"),
    ("power-cuts.xml", "Power cut"),
    ("bus-disruptions.xml", "Bus disruption"),
    ("wildfire.xml", "Wildfire risk"),
    ("unplanned-closures.xml", "Road closure"),
    ("security.xml", "Security"),
]


def iso(stamp):
    """An Atom <updated> value ('...Z') as an ISO time with an explicit offset."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).isoformat()


def read_entries(path, label):
    """The entries of one feed file as write_items_atom() items, labelled."""
    try:
        text = path.read_text()
    except FileNotFoundError:
        return []
    root = ET.fromstring(text[text.index("<?xml"):])
    entries = []
    for entry in root.findall(f"{ATOM}entry"):
        link = entry.find(f"{ATOM}link")
        title = entry.findtext(f"{ATOM}title") or ""
        if not title.lower().startswith(label.lower()):
            title = f"{label}: {title}"
        entries.append({
            "title": title,
            "link": link.get("href") if link is not None else entry.findtext(f"{ATOM}id"),
            "summary": entry.findtext(f"{ATOM}summary") or "",
            "published_iso": iso(entry.findtext(f"{ATOM}updated") or "1970-01-01T00:00:00Z"),
            "source": entry.findtext(f"{ATOM}author/{ATOM}name") or "",
            "category": label,
        })
    return entries


def combine(sources, limit=LIMIT):
    """Entries from every (path, label) source, newest first, at most `limit`."""
    items = [e for path, label in sources for e in read_entries(path, label)]
    items.sort(key=lambda e: e["published_iso"], reverse=True)
    return items[:limit]


def rebuild():
    feeds = helper.repo_root() / "feeds"
    site = helper.site_url()
    helper.write_items_atom(
        items=combine([(feeds / name, label) for name, label in SOURCES]),
        filename=feeds / "alerts.xml",
        permalink_path="/feeds/alerts.xml",
        feed_title="Cheltenham Alerts",
        feed_subtitle="Flood warnings, power cuts, bus disruptions, wildfire risk, road closures and security alerts for Cheltenham",
        self_url=f"{site}/feeds/alerts.xml",
        alternate_url=f"{site}/",
        feed_id=f"{site}/feeds/alerts.xml",
    )
