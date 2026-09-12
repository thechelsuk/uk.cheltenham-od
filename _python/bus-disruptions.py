import datetime
import json
import xml.etree.ElementTree as ET
from xml.dom import minidom

import helper

# -- Configuration ------------------------------------------------------------

CATALOGUE_URL   = "https://data.bus-data.dft.gov.uk/catalogue/"
SOURCE_PAGE     = "https://data.bus-data.dft.gov.uk/"
DISRUPTIONS_CSV = "disruptions_data_catalogue.csv"

# A disruption is "local" if it's published by one of our local authorities,
# or names one of the operators known to serve Cheltenham (see bus-data.py).
AUTHORITY_TERMS = ["gloucestershire", "cheltenham"]
FALLBACK_OPERATOR_TERMS = [
    "stagecoach", "go-ahead", "national express", "marchants",
    "bennetts", "first west of england", "pulham",
    "red & white", "cheltenham & gloucester",
]

ATOM_NS = "http://www.w3.org/2005/Atom"

# BODS source data is a mix of ALL CAPS and Title Case — normalise to Title Case.
ACRONYMS = {"UK", "LLP", "PLC"}


def local_operator_terms():
    """Pull the operator names bus-data.py already identified as serving Cheltenham,
    falling back to a fixed list if that data hasn't been generated yet."""
    bus_routes_path = helper.repo_root() / "_data" / "bus-routes.json"
    if bus_routes_path.exists():
        data = json.loads(bus_routes_path.read_text())
        operators = [o.lower() for o in data.get("operators", [])]
        if operators:
            return operators
    return FALLBACK_OPERATOR_TERMS


def row_is_local(row, operator_terms):
    organisation = (row.get("Organisation") or "").lower()
    operators_affected = (row.get("Operators Affected") or "").lower()
    if any(term in organisation for term in AUTHORITY_TERMS):
        return True
    return any(term in operators_affected for term in operator_terms)


def convert_to_atom(disruptions, filename):
    ET.register_namespace("", ATOM_NS)
    feed = ET.Element("feed", xmlns=ATOM_NS)

    title = ET.SubElement(feed, "title")
    title.text = "Cheltenham Bus Disruptions"

    link_self = ET.SubElement(feed, "link")
    link_self.set("rel", "self")
    link_self.set("href", "https://data.bus-data.dft.gov.uk/disruptions/download/")

    feed_id = ET.SubElement(feed, "id")
    feed_id.text = "https://cod.thechels.uk/feeds/bus-disruptions.xml"

    updated = ET.SubElement(feed, "updated")
    updated.text = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    subtitle = ET.SubElement(feed, "subtitle")
    subtitle.text = "Current bus service disruptions affecting Cheltenham"

    for d in disruptions:
        entry = ET.SubElement(feed, "entry")

        entry_title = ET.SubElement(entry, "title")
        entry_title.text = f"{d['reason']}: {d['organisation']}"

        entry_id = ET.SubElement(entry, "id")
        entry_id.text = d["situation_number"] or entry_title.text

        entry_link = ET.SubElement(entry, "link")
        entry_link.set("href", "https://data.bus-data.dft.gov.uk/disruptions/download/")

        summary = ET.SubElement(entry, "summary")
        parts = [f"Reason: {d['reason']}"]
        if d["planned"]:
            parts.append("Planned" if d["planned"].lower() == "true" else "Unplanned")
        if d["modes_affected"]:
            parts.append(f"Modes affected: {d['modes_affected']}")
        if d["operators_affected"]:
            parts.append(f"Operators affected: {d['operators_affected']}")
        if d["validity_start"]:
            parts.append(f"From: {d['validity_start']}")
        if d["validity_end"]:
            parts.append(f"To: {d['validity_end']}")
        summary.text = " · ".join(parts)

        entry_updated = ET.SubElement(entry, "updated")
        entry_updated.text = d["validity_start"] or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    tree = ET.ElementTree(feed)
    filename = str(filename)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

    with open(filename, "r") as f:
        xml_content = f.read()
    xml_pretty = minidom.parseString(xml_content).toprettyxml(indent="  ")

    front_matter = "---\nlayout: empty\npermalink: /feeds/bus-disruptions.xml\n---\n"
    with open(filename, "w") as f:
        f.write(front_matter + xml_pretty)


if __name__ == "__main__":
    root      = helper.repo_root()
    data_dir  = root / "_data"
    feeds_dir = root / "feeds"

    print("Downloading BODS data catalogue...")
    rows = helper.fetch_bods_csv(DISRUPTIONS_CSV, CATALOGUE_URL)
    print(f"  {len(rows):,} total disruptions in national catalogue")

    operator_terms = local_operator_terms()
    local_rows = [r for r in rows if row_is_local(r, operator_terms)]
    print(f"  {len(local_rows)} disruptions affect Cheltenham")

    disruptions = []
    for r in local_rows:
        disruptions.append({
            "organisation":       helper.clean_name(r.get("Organisation") or "", ACRONYMS),
            "situation_number":   r.get("Situation Number") or r.get("ID") or "",
            "validity_start":     r.get("Validity Start Date") or r.get("Validity start") or "",
            "validity_end":       r.get("Validity End Date") or r.get("Validity end") or "",
            "reason":             helper.clean_name(r.get("Reason") or "Unknown", ACRONYMS),
            "planned":            r.get("Planned") or "",
            "modes_affected":     helper.clean_name(r.get("Modes Affected") or r.get("Modes affected") or "", ACRONYMS),
            "operators_affected": helper.clean_name(r.get("Operators Affected") or r.get("Operators affected") or "", ACRONYMS),
            "services_affected":  r.get("Services Affected") or r.get("Services affected") or "",
            "stops_affected":     r.get("Stops Affected") or r.get("Stops affected") or "",
        })

    payload = {
        "updated":     helper.updated_timestamp(),
        "updated_iso": datetime.date.today().isoformat(),
        "source":      SOURCE_PAGE,
        "count":       len(disruptions),
        "disruptions": disruptions,
    }

    data_json = data_dir / "bus-disruptions.json"
    helper.write_json(data_json, payload)
    print(f"Wrote {len(disruptions)} disruptions to {data_json}")

    atom_path = feeds_dir / "bus-disruptions.xml"
    convert_to_atom(disruptions, atom_path)
    print(f"Atom feed saved to {atom_path}")

    # Homepage alert — only appears while a disruption is live, cleared automatically once it isn't.
    if not disruptions:
        alert_html = ""
    else:
        now_str = datetime.datetime.now().strftime("%H:%M")
        items = ""
        for d in disruptions[:5]:
            label = d["operators_affected"] or d["organisation"]
            items += (
                f'  <li><a href="/cheltenham-bus-data">'
                f'Disruption to {label} bus services reported at {now_str}</a></li>\n'
            )
        alert_html = (
            '<h2>Bus Disruption Alert</h2>\n'
            '<ul>\n'
            f'{items}'
            '</ul>'
        )

    include_path = root / "_includes" / "bus-alert.html"
    include_contents = include_path.open().read()
    include_contents = helper.replace_chunk(include_contents, "bus_alert_marker", alert_html)
    include_path.open("w").write(include_contents)
