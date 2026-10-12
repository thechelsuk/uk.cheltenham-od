#!/usr/bin/env python3
"""
Scrapes the Cheltenham Borough Council recycling banks page and writes the
banks and the materials each takes to _data/recycling.json, rendered by
_layouts/home-property/recycling.html.

Run from the repo root:
    python _python/recycling.py

Requires: requests, beautifulsoup4
"""
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

import helper

URL = "https://www.cheltenham.gov.uk/recyclingbanks"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "_data" / "recycling.json"
SOURCE_NAME = "Cheltenham Borough Council"
# The council's page states no licence, so the JSON carries none; see
# _data/sources.json for the note.

def fetch_page(url: str) -> str:
    response = helper.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_banks(html: str) -> list[dict]:
    """
    Parse the recycling bank locations section into a list of
    {"name": str, "materials": [str, ...]} dicts.

    The site renders each bank as a GOV.UK accordion section:

        <div class="govuk-accordion__section">
          <div class="govuk-accordion__section-header">
            <h2 class="govuk-accordion__section-heading">
              <span class="govuk-accordion__section-button">Site name, POSTCODE</span>
            </h2>
          </div>
          <div class="govuk-accordion__section-content">
            <p class="govuk-body"><ul><li>Material</li>...</ul></p>
          </div>
        </div>

    We parse every ".govuk-accordion__section" within the accordion
    container. This is more robust than relying on the surrounding
    prose/headings, which have changed between site revisions.
    """
    soup = BeautifulSoup(html, "html.parser")

    accordion = soup.find("div", class_="govuk-accordion")
    if accordion is None:
        raise RuntimeError("Could not find the recycling banks accordion")

    banks = []

    for section in accordion.find_all("div", class_="govuk-accordion__section"):
        button = section.find(class_="govuk-accordion__section-button")
        if button is None:
            continue
        name = button.get_text(strip=True)
        if not name:
            continue

        content = section.find(class_="govuk-accordion__section-content")
        if content is None:
            continue

        materials = [
            li.get_text(strip=True)
            for li in content.find_all("li")
            if li.get_text(strip=True)
        ]
        if materials:
            banks.append({"name": name, "materials": materials})

    if not banks:
        raise RuntimeError("No recycling banks were parsed from the page")

    return banks


def title_case_address(text):
    return " ".join(
        word if re.match(r'^[A-Z0-9]+$', word) else word.capitalize()
        for word in text.split()
    )


def smart_title(text: str) -> str:
    """Title-case a name, handling messy source data sensibly.

    - Words containing a digit (postcodes, unit codes like 'GL51') are
      left completely untouched.
    - If the whole name is SHOUTING, every other word gets re-cased.
    - A short (<=3 letter) standalone all-caps word (e.g. 'HQ') is treated
      as a deliberate acronym and left alone, UNLESS the whole name is
      shouting (in which case there's no way to distinguish it from an
      accidental caps-lock name, so it's re-cased along with everything
      else).
    """
    is_shouting = text.isupper()
    out = []
    for word in text.split():
        if re.search(r"\d", word):
            out.append(word)
        elif is_shouting:
            out.append(word.capitalize())
        elif word.isupper() and len(word) <= 3:
            out.append(word)
        else:
            out.append(word[:1].upper() + word[1:] if word else word)
    return " ".join(out)


def postcode_in(text: str) -> str:
    m = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\b", text.upper())
    return f"{m.group(1)} {m.group(2)}" if m else ""


def build_payload(banks: list[dict], generated_at: str) -> dict:
    """The banks in the council's order, each with its postcode, plus how
    many sites take each material (most widely accepted first)."""
    counts = Counter(m for bank in banks for m in bank["materials"])
    return {
        "generated_at": generated_at,
        "source": SOURCE_NAME,
        "source_url": URL,
        "bank_count": len(banks),
        "materials": [{"material": m, "sites": n} for m, n in counts.most_common()],
        "banks": [
            {"name": smart_title(bank["name"]), "postcode": postcode_in(bank["name"]), "materials": bank["materials"]}
            for bank in banks
        ],
    }


def main() -> int:
    try:
        html = fetch_page(URL)
        banks = parse_banks(html)
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch or parse recycling banks: {exc}", file=sys.stderr)
        return 1

    payload = build_payload(banks, datetime.now(timezone.utc).isoformat())
    helper.write_json(OUTPUT_PATH, payload)

    print(f"Wrote {len(banks)} recycling bank locations to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())