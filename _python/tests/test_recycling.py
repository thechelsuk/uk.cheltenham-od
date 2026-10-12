"""Offline tests for the recycling banks fetcher (recycling.py): reading the
council's recycling banks page and shaping _data/recycling.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "recycling", pathlib.Path(__file__).resolve().parents[1] / "recycling.py"
)
assert SPEC is not None and SPEC.loader is not None
recycling = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(recycling)


def section(name, materials):
    items = "".join(f"<li>{m}</li>" for m in materials)
    return f"""<div class="govuk-accordion__section">
      <div class="govuk-accordion__section-header"><h2 class="govuk-accordion__section-heading">
        <span class="govuk-accordion__section-button">{name}</span></h2></div>
      <div class="govuk-accordion__section-content"><ul>{items}</ul></div>
    </div>"""


PAGE = f"""<html><body><div class="govuk-accordion">
{section("Bath Terrace car park, GL50 2AL", ["Glass", "Paper", "Textiles and shoes"])}
{section("Church Piece Car Park, GL53 8JN", ["Textiles and shoes"])}
{section("Empty site, GL50 1AA", [])}
</div></body></html>"""


def test_each_accordion_section_with_materials_is_a_bank():
    assert recycling.parse_banks(PAGE) == [
        {"name": "Bath Terrace car park, GL50 2AL", "materials": ["Glass", "Paper", "Textiles and shoes"]},
        {"name": "Church Piece Car Park, GL53 8JN", "materials": ["Textiles and shoes"]},
    ]


def test_a_page_without_banks_is_an_error():
    with pytest.raises(RuntimeError):
        recycling.parse_banks("<html><body><p>Moved</p></body></html>")


def test_names_are_title_cased_but_postcodes_and_acronyms_stay():
    assert recycling.smart_title("Whaddon Road, Cheltenham Town FC, GL2 5NA") == "Whaddon Road, Cheltenham Town FC, GL2 5NA"
    assert recycling.smart_title("bath terrace car park") == "Bath Terrace Car Park"


def test_the_payload_lists_banks_with_their_postcode_and_counts_sites_per_material():
    payload = recycling.build_payload(recycling.parse_banks(PAGE), generated_at="2026-10-12T14:00:00+00:00")
    assert payload["generated_at"] == "2026-10-12T14:00:00+00:00"
    assert payload["source"] == "Cheltenham Borough Council"
    assert payload["source_url"] == "https://www.cheltenham.gov.uk/recyclingbanks"
    assert "licence" not in payload  # the council's page states no licence
    assert payload["banks"][0] == {
        "name": "Bath Terrace Car Park, GL50 2AL",
        "postcode": "GL50 2AL",
        "materials": ["Glass", "Paper", "Textiles and shoes"],
    }
    assert payload["bank_count"] == 2
    assert payload["materials"] == [
        {"material": "Textiles and shoes", "sites": 2},
        {"material": "Glass", "sites": 1},
        {"material": "Paper", "sites": 1},
    ]
