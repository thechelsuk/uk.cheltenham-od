from dateutil.parser import parse
import pathlib
import re
import json
import requests
import time
import html
from datetime import datetime, timedelta, timezone
from requests import get
import xml.etree.ElementTree as ET
from xml.dom import minidom


def repo_root():
    """Resolve the repository root from within any _python/*.py script."""
    return pathlib.Path(__file__).parent.parent.resolve()


def site_url():
    """The site's canonical URL (no trailing slash), read from _config.yml's
    `url:` key rather than hardcoded, so it tracks a domain change automatically."""
    import yaml as _yaml

    config = _yaml.safe_load((repo_root() / "_config.yml").read_text())
    return config["url"].rstrip("/")


def updated_timestamp():
    """The "updated" string used across _data/*.json payloads, e.g. '12 September 2026 at 20:53'."""
    return datetime.now().strftime("%-d %B %Y at %H:%M")


def write_json(path, payload):
    pathlib.Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False))


def update_history(history_records, current_items, id_key, now_iso, peak_fields=None, retention_days=730):
    """Generic incremental history log, shared by any fetcher whose live
    source only ever shows what's currently active (power cuts, bus
    disruptions, flood warnings) and drops an item the moment it's no longer
    live — so the live feed alone can never show "this has now ended".

    On every run: a history record is created the first time an `id_key` is
    seen, then refreshed from that item's current fields (so 'status' etc.
    stay current) on every run it's still present; `peak_fields` are tracked
    as a running max rather than overwritten. Anything not seen within
    `retention_days` is dropped. Returns the updated list, most-recently-seen
    first. `history_records`/`current_items` are both lists of plain dicts;
    each dict in `current_items` must have an `id_key` key."""
    peak_fields = peak_fields or []
    by_id = {r[id_key]: r for r in history_records if id_key in r}

    for item in current_items:
        key = item[id_key]
        record = by_id.get(key)
        if record is None:
            record = {"first_seen_iso": now_iso}
            by_id[key] = record
            history_records.append(record)

        first_seen = record.get("first_seen_iso", now_iso)
        previous_peaks = {f: record.get(f) for f in peak_fields}
        record.update(item)
        record["first_seen_iso"] = first_seen
        record["last_seen_iso"] = now_iso
        for f in peak_fields:
            values = [v for v in (previous_peaks.get(f), item.get(f)) if isinstance(v, (int, float))]
            if values:
                record[f] = max(values)

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = []
    for record in history_records:
        try:
            last_seen = datetime.fromisoformat(record["last_seen_iso"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            kept.append(record)
            continue
        if last_seen >= cutoff:
            kept.append(record)

    kept.sort(key=lambda r: r.get("last_seen_iso", ""), reverse=True)
    return kept


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


def parse_front_matter(text):
    """Split a Jekyll page's '---\\nYAML\\n---\\nbody' into (front_matter_dict, body).
    Returns ({}, text) if `text` has no front matter block."""
    import yaml as _yaml

    match = re.match(r"^---\s*\n(.*?\n)---\s*\n?(.*)$", text, re.DOTALL)
    if not match:
        return {}, text
    front_matter = _yaml.safe_load(match.group(1)) or {}
    return front_matter, match.group(2)


def write_items_atom(items, filename, permalink_path, feed_title, feed_subtitle, self_url, alternate_url, feed_id=None):
    """Write an Atom 1.0 feed of arbitrary `items` (each a dict with title,
    link, published_iso, summary, source) to `filename`, with the usual
    front-matter + layout:empty wrapper so Jekyll serves it as a static file.
    `permalink_path` is the site-relative path (e.g. '/feeds/news-summary.xml')
    written into that front matter; `self_url`/`alternate_url` are the full
    URLs used in the feed's own <link> elements. Mirrors convert_to_atom()
    above, generalised for reuse."""
    ATOM_NS = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", ATOM_NS)

    feed = ET.Element("feed", xmlns=ATOM_NS)

    ET.SubElement(feed, "title").text = feed_title
    ET.SubElement(feed, "subtitle").text = feed_subtitle

    link_self = ET.SubElement(feed, "link")
    link_self.set("rel", "self")
    link_self.set("href", self_url)

    link_alt = ET.SubElement(feed, "link")
    link_alt.set("rel", "alternate")
    link_alt.set("type", "text/html")
    link_alt.set("href", alternate_url)

    ET.SubElement(feed, "id").text = feed_id or alternate_url
    ET.SubElement(feed, "updated").text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for item in items:
        entry = ET.SubElement(feed, "entry")
        ET.SubElement(entry, "title").text = item.get("title", "")

        link = ET.SubElement(entry, "link")
        link.set("href", item.get("link", alternate_url))

        ET.SubElement(entry, "id").text = item.get("link", alternate_url)

        author = ET.SubElement(entry, "author")
        ET.SubElement(author, "name").text = item.get("source", feed_title)

        summary = ET.SubElement(entry, "summary")
        summary.text = item.get("summary") or item.get("title", "")

        published_iso = item.get("published_iso")
        updated_text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if published_iso:
            try:
                updated_text = datetime.fromisoformat(published_iso).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        ET.SubElement(entry, "updated").text = updated_text

    tree = ET.ElementTree(feed)
    filename = str(filename)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

    with open(filename, "r") as f:
        xml_content = f.read()
    xml_pretty = minidom.parseString(xml_content).toprettyxml(indent="  ")

    front_matter = f"---\nlayout: empty\npermalink: {permalink_path}\n---\n"
    with open(filename, "w") as f:
        f.write(front_matter + xml_pretty)


def write_digest_atom(digests, filename, permalink_path, feed_title, feed_subtitle, self_url, alternate_url, feed_id=None):
    """Write an Atom 1.0 feed with one entry per day's digest (each `digests`
    entry a dict with date, created_iso, items — a list of {title, link,
    source}), so subscribers get one round-up post a day rather than one
    entry per headline. `permalink_path`/`self_url`/`alternate_url` as in
    write_items_atom() above."""
    ATOM_NS = "http://www.w3.org/2005/Atom"
    ET.register_namespace("", ATOM_NS)

    feed = ET.Element("feed", xmlns=ATOM_NS)

    ET.SubElement(feed, "title").text = feed_title
    ET.SubElement(feed, "subtitle").text = feed_subtitle

    link_self = ET.SubElement(feed, "link")
    link_self.set("rel", "self")
    link_self.set("href", self_url)

    link_alt = ET.SubElement(feed, "link")
    link_alt.set("rel", "alternate")
    link_alt.set("type", "text/html")
    link_alt.set("href", alternate_url)

    ET.SubElement(feed, "id").text = feed_id or alternate_url
    ET.SubElement(feed, "updated").text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for digest in digests:
        entry = ET.SubElement(feed, "entry")

        display_date = datetime.fromisoformat(digest["date"]).strftime("%-d %B %Y")
        ET.SubElement(entry, "title").text = f"Daily News Summary — {display_date}"

        entry_url = f"{alternate_url}#{digest['date']}"
        link = ET.SubElement(entry, "link")
        link.set("href", entry_url)
        ET.SubElement(entry, "id").text = entry_url

        author = ET.SubElement(entry, "author")
        ET.SubElement(author, "name").text = feed_title

        rows = "".join(
            '<li><a href="{link}">{title}</a> — {source}</li>'.format(
                link=html.escape(item["link"], quote=True),
                title=html.escape(item["title"]),
                source=html.escape(item["source"]),
            )
            for item in digest["items"]
        )
        content = ET.SubElement(entry, "content")
        content.set("type", "html")
        content.text = f"<p>Today's top {len(digest['items'])} local headlines:</p><ul>{rows}</ul>"

        updated_text = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        created_iso = digest.get("created_iso")
        if created_iso:
            try:
                updated_text = datetime.fromisoformat(created_iso).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        ET.SubElement(entry, "updated").text = updated_text

    tree = ET.ElementTree(feed)
    filename = str(filename)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

    with open(filename, "r") as f:
        xml_content = f.read()
    xml_pretty = minidom.parseString(xml_content).toprettyxml(indent="  ")

    front_matter = f"---\nlayout: empty\npermalink: {permalink_path}\n---\n"
    with open(filename, "w") as f:
        f.write(front_matter + xml_pretty)
