from dateutil.parser import parse
import re
import json
import requests
import time
from datetime import datetime, timezone
from requests import get
import xml.etree.ElementTree as ET
from xml.dom import minidom


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
