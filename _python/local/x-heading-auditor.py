#!/usr/bin/env python3
"""
Scan a built Jekyll site (_site) for every H1/H2 heading and check it against
standard English title-case rules (Chicago/AP style), flagging mismatches
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

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# Minor words per Chicago Manual of Style / AP style convention: articles,
# coordinating conjunctions, and prepositions of four letters or fewer.
MINOR_WORDS = {
    "a", "an", "the",
    "and", "but", "or", "nor", "for", "so", "yet",
    "as", "at", "by", "in", "of", "off", "on", "per", "to", "up", "via",
    "vs", "from", "into", "like", "near", "onto", "over", "past", "than",
    "with",
}


def is_word_token(token: str) -> bool:
    """True if token contains at least one letter (i.e. is a real word,
    not pure punctuation like '—' or ':')."""
    return bool(re.search(r"[A-Za-z]", token))


def has_intentional_internal_caps(core: str) -> bool:
    """True for words that look deliberately styled (eBay, iPhone, McDonald's,
    GL50, USA) rather than just wrongly-cased — i.e. any uppercase letter
    after position 0. These are left completely untouched, first letter
    included, since forcing them to standard case breaks brand/proper-noun
    styling."""
    return bool(re.search(r"[A-Za-z]", core[1:])) and any(c.isupper() for c in core[1:])


def apply_title_case(text: str) -> str:
    """Return the title-case-corrected version of a heading.

    Normal case: only the FIRST character of each word is changed —
    everything else is left as-is, so ordinary acronyms are untouched.

    All-caps heading (e.g. "THE BEST PLACES TO VISIT"): a first-letter-only
    pass can't fix this without producing a garbled mix, so the whole
    heading is first lowercased, then title-cased word by word.

    Words with intentional internal capitals (eBay, iPhone, McDonald's,
    GL50) are detected and left completely untouched, including their
    first letter, rather than forced into "Ebay"/"Iphone".
    """
    is_all_caps_heading = text.isupper()

    raw_words = text.split(" ")
    word_tokens = [w for w in raw_words if is_word_token(w)]
    corrected = []

    for word in raw_words:
        if not is_word_token(word):
            corrected.append(word)
            continue

        m = re.match(r"^(\W*)([A-Za-z][\w'-]*)(\W*)$", word)
        if not m:
            corrected.append(word)
            continue
        lead, core, trail = m.groups()

        # An all-caps heading gives us no signal about intended internal
        # styling (GL50 vs Gl50 look identical once shouted), so only
        # apply the "leave it alone" exception for mixed-case source text.
        if not is_all_caps_heading and has_intentional_internal_caps(core):
            corrected.append(lead + core + trail)
            continue

        work_core = core.lower() if is_all_caps_heading else core
        core_lower = work_core.lower()
        is_first_or_last_word = (word == word_tokens[0]) or (word == word_tokens[-1])

        should_lowercase = (core_lower in MINOR_WORDS) and not is_first_or_last_word

        if should_lowercase:
            new_core = core_lower[0] + core_lower[1:] if len(core_lower) > 1 else core_lower
        else:
            new_core = work_core[0].upper() + work_core[1:] if len(work_core) > 1 else work_core.upper()

        corrected.append(lead + new_core + trail)

    return " ".join(corrected)


def find_headings(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    headings = []
    for tag_name in ("h1", "h2", "h3"):
        for tag in soup.find_all(tag_name):
            text = tag.get_text(strip=True)
            if text:
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
            suggestion = apply_title_case(text)
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