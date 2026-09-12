import helper
import json
import xml.etree.ElementTree as ET

ATOM_NS = "{http://www.w3.org/2005/Atom}"

if __name__ == "__main__":
    # Compute repo root FIRST, before it's needed anywhere else
    root = helper.repo_root()

    data_dir = root / "_data"
    feeds_dir = root / "feeds"
    data_dir.mkdir(parents=True, exist_ok=True)
    feeds_dir.mkdir(parents=True, exist_ok=True)

    flood_json = data_dir / "flood.json"
    flood_atom = feeds_dir / "flood.xml"

    data = helper.fetch_flood_data()
    with open(flood_json, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {flood_json}")

    with open(flood_json, "r") as f:
        data = json.load(f)
    helper.convert_to_atom(data, flood_atom)
    print(f"Atom feed saved to {flood_atom}")

    with open(flood_atom, "r") as f:
        content = f.read()
    # Strip leading Jekyll front matter (--- ... ---) before XML parsing
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        content = content[end_idx + 3:].lstrip()

    root_el = ET.fromstring(content)

    entries = root_el.findall(f"./{ATOM_NS}entry")

    if not entries:
        output = "> No current flood warnings reports in this area\n"
    else:
        output = ""
        for entry in entries:
            title = entry.find(f"{ATOM_NS}title").text
            summary = entry.find(f"{ATOM_NS}summary").text
            output += f"- {title}\n"
            output += f"- {summary}\n"

    md = root / "_pages/flood-warnings.md"
    md_contents = md.open().read()
    md_contents = helper.replace_chunk(md_contents, "flood_marker", output)
    md.open("w").write(md_contents)