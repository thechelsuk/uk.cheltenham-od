from dateutil.parser import parse
import pathlib
import re
import json
import requests
import time
from datetime import datetime, timezone
from requests import get
import xml.etree.ElementTree as ET
from xml.dom import minidom


def repo_root():
    """Resolve the repository root from within any _python/*.py script."""
    return pathlib.Path(__file__).parent.parent.resolve()


def updated_timestamp():
    """The "updated" string used across _data/*.json payloads, e.g. '12 September 2026 at 20:53'."""
    return datetime.now().strftime("%-d %B %Y at %H:%M")


def write_json(path, payload):
    pathlib.Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


DEFAULT_ACRONYMS = {"UK"}


def clean_name(name, acronyms=DEFAULT_ACRONYMS):
    """Tidy a station/operator/place name: collapse stray whitespace, title-case
    each word (including inside brackets, so '(summer Only)' -> '(Summer Only)'),
    and keep known acronyms and anything containing a digit (A40, B4083, 80-86)
    upper-case — even wrapped in brackets like '(GWSR)'.

    Also fixes 'Waterstones- upper floor' -> 'Waterstones - upper floor': a
    space is only added before a hyphen when a space already follows it, so the
    hyphen is being used as a dash/separator. Untouched: 'Stratford-upon-Avon'
    (no spaces) and already-correct 'Foo - bar' (already has both).
    """
    def fix(w):
        lead, core, trail = re.match(r"(\W*)(.*?)(\W*)$", w).groups()
        if core.upper() in acronyms or any(c.isdigit() for c in core):
            core = core.upper()
        elif core:
            core = core[:1].upper() + core[1:].lower()
        return lead + core + trail

    name = re.sub(r"(?<! )- ", " - ", name or "")
    return " ".join(fix(w) for w in name.split())


def fetch_bods_csv(csv_filename, catalogue_url="https://data.bus-data.dft.gov.uk/catalogue/"):
    """Download the BODS data catalogue zip and return one of its CSVs as a
    list of dict rows (via csv.DictReader). `csv_filename` matches by suffix,
    e.g. 'timetables_data_catalogue.csv' or 'disruptions_data_catalogue.csv'."""
    import csv
    import io
    import zipfile

    resp = requests.get(catalogue_url, timeout=(10, 120))
    resp.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(csv_filename))
        with zf.open(name) as f:
            text = io.TextIOWrapper(f, encoding="utf-8-sig")
            return list(csv.DictReader(text))


def replace_chunk(content, marker, chunk):
    replacer = re.compile(
        r"<!\-\- {} starts \-\->.*<!\-\- {} ends \-\->".format(marker, marker),
        re.DOTALL,
    )
    chunk = "<!-- {} starts -->\n{}\n<!-- {} ends -->".format(marker, chunk, marker)
    return replacer.sub(chunk, content)


def ord(n):
    return str(n)+("th" if 4<=n%100<=20 else {1:"st",2:"nd",3:"rd"}.get(n%10, "th"))


def dtStylish(dt,f):
    return dt.strftime(f).replace("{th}", ord(dt.day))


def pprint(string):
    json_formatted_str = json.dumps(string, indent=2)
    print(json_formatted_str)

def date_to_iso(string):
    dt = parse(string)
    return dt.strftime('%Y-%m-%d')

def get_data(endpoint):
    print(endpoint)
    response = get(endpoint, timeout=20)
    if response.status_code >= 400:
        print(response.status_code)
        print(f"Request failed: { response.text }")
    return response.json()


def request_with_retry(method, url, max_attempts=5, retry_statuses=(429, 500, 502, 503, 504), **kwargs):
    """requests.request(), retrying transient failures: a connection error/
    timeout, or a response with one of `retry_statuses`. Honours a
    Retry-After header when present, otherwise backs off exponentially
    (1, 2, 4, 8... seconds). Raises (the last error, or via raise_for_status)
    once `max_attempts` is exhausted. Returns the successful `requests.Response`
    — callers call .json()/.text themselves, since that varies by caller.
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            response = requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as error:
            last_error = error
            if attempt == max_attempts - 1:
                raise
            time.sleep(2 ** attempt)
            continue

        if response.status_code in retry_statuses:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else (2 ** attempt)
            last_error = requests.HTTPError(f"{response.status_code} received, retrying in {delay}s")
            if attempt == max_attempts - 1:
                response.raise_for_status()
            time.sleep(delay)
            continue

        response.raise_for_status()
        return response

    raise last_error


def fetch_flood_data():
    url = "https://environment.data.gov.uk/flood-monitoring/id/floods"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://environment.data.gov.uk/flood-monitoring/",
    }
    response = request_with_retry(
        "GET", url, max_attempts=6, retry_statuses=(429, 503), headers=headers, timeout=30,
    )
    data = response.json()
    items = data.get("items", [])
    filtered = [
        item for item in items
        if item.get("floodArea", {}).get("county", "").find("Gloucestershire") != -1
    ]
    data["items"] = filtered
    return data


def convert_to_atom(data, filename):
        """Write an Atom 1.0 feed to `filename` (a pathlib.Path or str)."""
        ATOM_NS = "http://www.w3.org/2005/Atom"
        ET.register_namespace("", ATOM_NS)

        feed = ET.Element("feed", xmlns=ATOM_NS)

        title = ET.SubElement(feed, "title")
        title.text = "Flood Warnings"

        link_self = ET.SubElement(feed, "link")
        link_self.set("rel", "self")
        link_self.set("href", "https://environment.data.gov.uk/flood-monitoring/id/floods")

        feed_id = ET.SubElement(feed, "id")
        feed_id.text = "https://environment.data.gov.uk/flood-monitoring/id/floods"

        updated = ET.SubElement(feed, "updated")
        updated.text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        subtitle = ET.SubElement(feed, "subtitle")
        subtitle.text = "Current flood warnings for Gloucestershire"

        for item in data.get("items", []):
            entry = ET.SubElement(feed, "entry")

            severity = item.get("severity", "No severity")
            description_text = item.get("description", "")
            entry_title = ET.SubElement(entry, "title")
            entry_title.text = f"{severity}: {description_text}"

            # Atom requires a stable, unique id per entry — use the source item's own id/url if present
            entry_id = ET.SubElement(entry, "id")
            entry_id.text = item.get("@id") or item.get("floodAreaID") or description_text

            entry_link = ET.SubElement(entry, "link")
            entry_link.set("href", item.get("@id", "https://environment.data.gov.uk/flood-monitoring/id/floods"))

            summary = ET.SubElement(entry, "summary")
            summary.text = item.get("message", "No message")

            # Atom wants ISO 8601 with a timezone; timeRaised from the API is already ISO 8601
            time_raised = item.get("timeRaised")
            entry_updated = ET.SubElement(entry, "updated")
            entry_updated.text = time_raised if time_raised else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        tree = ET.ElementTree(feed)
        filename = str(filename)
        tree.write(filename, encoding="utf-8", xml_declaration=True)

        with open(filename, "r") as f:
            xml_content = f.read()
        xml_pretty = minidom.parseString(xml_content).toprettyxml(indent="  ")

        front_matter = "---\nlayout: empty\npermalink: /feeds/flood.xml\n---\n"
        with open(filename, "w") as f:
            f.write(front_matter + xml_pretty)
