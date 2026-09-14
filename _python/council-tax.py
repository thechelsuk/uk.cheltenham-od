#!/usr/bin/env python3
"""Fetch Cheltenham's council tax charges by parish and band, write
_data/council-tax.json.

There is no CSV or open data file for this — Cheltenham Borough Council only
publishes it as an HTML page (a GOV.UK Design System accordion, one section
per tax year). This scrapes the accordion section for the most recent year
found on the page, rather than hardcoding "2026/2027", so next year's refresh
doesn't need a code change.

Only 5 of the borough's parishes set their own precept (Charlton Kings,
Leckhampton with Warden Hill, Prestbury, Swindon Village, Up Hatherley) —
council tax elsewhere in the borough, including most of Cheltenham's
ordinary electoral wards, is the "All other parts of Cheltenham" rate.
"""
import json
import os
import re

import requests
from bs4 import BeautifulSoup

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(HERE, "..", "_data", "council-tax.json")

SOURCE_URL = "https://www.cheltenham.gov.uk/council-tax-and-benefits/council-tax-bands-charges-and-appeals/"
HEADERS = {"User-Agent": "cheltenham-od/1.0 (https://cheltenham-od.uk; contact@cheltenham-od.uk)"}

BAND_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H"]


def main():
    resp = requests.get(SOURCE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    best_year, best_year_label, best_content = None, None, None
    for section in soup.select(".govuk-accordion__section"):
        heading = section.select_one(".govuk-accordion__section-button")
        if not heading:
            continue
        match = re.search(r"(\d{4})/\d{4}", heading.get_text(strip=True))
        if not match:
            continue
        year = int(match.group(1))
        if best_year is None or year > best_year:
            best_year = year
            best_year_label = match.group(0)
            best_content = section.select_one(".govuk-accordion__section-content")

    if best_content is None:
        raise SystemExit("Could not find a dated council tax charges section on the page")

    areas = []
    for h2 in best_content.find_all("h2"):
        ul = h2.find_next_sibling("ul")
        if not ul:
            continue
        name = h2.get_text(strip=True)
        bands = {}
        for li in ul.find_all("li"):
            text = li.get_text(strip=True).replace("\xa0", "")
            if ":" not in text:
                continue
            band, value = text.split(":", 1)
            band = band.strip()
            try:
                bands[band] = float(value.replace(",", "").strip())
            except ValueError:
                continue
        areas.append({
            "area":     name,
            "is_parish": name.lower().startswith("parish of"),
            "bands":    [{"band": b, "amount": bands[b]} for b in BAND_ORDER if b in bands],
        })

    output = {
        "generated_at": helper.updated_timestamp(),
        "tax_year":     best_year_label,
        "source":       "Cheltenham Borough Council",
        "source_url":   SOURCE_URL,
        "licence":      ("Not explicitly stated on the scraped page; assumed to fall under "
                          "Cheltenham Borough Council's general Open Government Licence v3.0 "
                          "website terms, but this is unconfirmed for this specific page"),
        "band_check_url": "https://www.gov.uk/council-tax-bands",
        "areas":        areas,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(areas)} areas for {best_year_label} to {OUT}")


if __name__ == "__main__":
    main()
