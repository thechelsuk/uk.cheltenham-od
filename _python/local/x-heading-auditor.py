#!/usr/bin/env python3
"""
Scan a built Jekyll site (_site) for every H1/H2 heading and check it against
AP title-case rules (the site's heading style), flagging mismatches
and suggesting a corrected version.

Title case rule applied:
  - First and last word of the heading: always capitalised.
  - Major words (nouns, verbs, adjectives, adverbs, pronouns): capitalised.
  - Minor words (articles, coordinating conjunctions, short prepositions):
    lowercase, UNLESS first or last word.

The script only adjusts the FIRST LETTER of each word — the rest of the
word is left untouched. This deliberately preserves things like "GL50",
"eBay", "iPhone", acronyms, etc. It will not correct an all-caps or
all-lowercase word beyond its first letter, so spot-check the suggestions
rather than trusting them blindly (see note printed at the end).

Usage:
    python audit_headers.py [path-to-_site]

Defaults to "./_site" if no path given.

Requires: beautifulsoup4
    pip install beautifulsoup4
"""

import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402  (shared AP title case)

# Proper names and brands whose own capitalisation wins over the rules
# (a minor word that is part of a name, or a lower-case brand).
ALLOWLIST = ["Up Hatherley", "Aim Up", "parkrun", "parkruns", "Turn On", "MP"]

DATA = Path(__file__).resolve().parents[2] / "_data"


def name_allowlist():
    """ALLOWLIST plus every school, care home and football referee name,
    read from the site's data so new ones are covered too. These are
    registered names, so their own capitalisation stands."""
    names = list(ALLOWLIST)
    for file, key in (("schools.json", None), ("cqc.json", "locations")):
        path = DATA / file
        if not path.exists():
            continue
        records = json.loads(path.read_text(encoding="utf-8"))
        for record in records[key] if key else records:
            if record.get("name"):
                names.append(record["name"])
    # Football referees are named by initial and surname ("A Backhouse"),
    # so the initial isn't the article "a".
    referees = DATA / "ctfc-referees.json"
    if referees.exists():
        names.extend(r["name"] for r in json.loads(referees.read_text(encoding="utf-8"))["referees"])
    # Longest first, so a full name wins over any shorter one inside it.
    return sorted(set(names), key=len, reverse=True)


PROTECTED = name_allowlist()


def protect_names(original: str, suggestion: str) -> str:
    """Put allowlisted names back exactly as they appear in the original."""
    for name in PROTECTED:
        if name in original:
            suggestion = re.sub(re.escape(name), lambda _m, n=name: n, suggestion, flags=re.IGNORECASE)
    return suggestion


def is_quoted_headline(tag) -> bool:
    """True for a heading that is wholly a link to another site, such as a
    newsletter's news item: that is the other publisher's headline, quoted
    as published, so it isn't ours to re-case."""
    link = tag.find("a", href=True)
    if link is None or link.get_text(strip=True) != tag.get_text(strip=True):
        return False
    href = link["href"]
    return href.startswith(("http://", "https://")) and "cheltenham-od.uk" not in href


def find_headings(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    headings = []
    for tag_name in ("h1", "h2", "h3"):
        for tag in soup.find_all(tag_name):
            text = tag.get_text(strip=True)
            if text and not is_quoted_headline(tag):
                headings.append((tag_name, text))
    return headings


def main():
    site_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("_site")
    if not site_dir.is_dir():
        print(f"Error: {site_dir} is not a directory. Pass the path to your built _site folder.")
        sys.exit(1)

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        print(f"No .html files found under {site_dir}")
        sys.exit(1)

    all_rows = []  # (page, tag, original, suggestion, needs_fix)

    for html_path in html_files:
        rel_path = html_path.relative_to(site_dir)
        for tag_name, text in find_headings(html_path):
            suggestion = protect_names(text, helper.title_case(text))
            needs_fix = suggestion != text
            all_rows.append((str(rel_path), tag_name.upper(), text, suggestion, needs_fix))

    if not all_rows:
        print("No headings found on any page.")
        sys.exit(0)

    flagged = [r for r in all_rows if r[4]]

    # --- Full listing, grouped by page ---
    print("=" * 70)
    print("ALL HEADINGS BY PAGE")
    print("=" * 70)
    current_page = None
    for page, tag, original, suggestion, needs_fix in all_rows:
        if page != current_page:
            print(f"\n{page}")
            current_page = page
        if needs_fix:
            print(f"  [{tag}] {original}")
            print(f"       -> {suggestion}")
        else:
            print(f"  [{tag}] {original}    (OK)")

    # --- Flagged shortlist ---
    print("\n" + "=" * 70)
    print(f"HEADINGS TO FIX ({len(flagged)} of {len(all_rows)})")
    print("=" * 70)
    for page, tag, original, suggestion, needs_fix in flagged:
        print(f"  {page}")
        print(f"    [{tag}] {original}")
        print(f"        -> {suggestion}")

    print(f"\n{len(flagged)} of {len(all_rows)} headings don't match standard title case.")
    print(
        "\nNote: only the first letter of each word is adjusted, to avoid mangling "
        "acronyms/postcodes/brand names (e.g. 'GL50', 'eBay'). Spot-check suggestions "
        "before bulk-applying — words already in ALL CAPS or with internal capitals "
        "keep everything after their first letter unchanged."
    )


if __name__ == "__main__":
    main()