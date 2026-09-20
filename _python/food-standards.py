"""Convert the Food Standards Agency XML feed into Jekyll data JSON."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "_data" / "food-standards.xml"
DESTINATION = REPO_ROOT / "_data" / "food-standards.json"


def value(establishment, name):
    element = establishment.find(name)
    return element.text.strip() if element is not None and element.text else ""


def coordinate(establishment, name):
    """The FSA's own latitude/longitude, or None where a venue has none (mostly mobile
    and home-based caterers, which have no fixed premises to map)."""
    text = establishment.findtext(f"Geocode/{name}")
    try:
        return float(text) if text else None
    except ValueError:
        return None


def convert():
    root = ET.parse(SOURCE).getroot()
    establishments = root.findall(".//EstablishmentDetail")
    venues = []
    for establishment in establishments:
        address = ", ".join(
            part
            for part in (
                value(establishment, "AddressLine1"),
                value(establishment, "AddressLine2"),
                value(establishment, "AddressLine3"),
                value(establishment, "AddressLine4"),
            )
            if part
        )
        venues.append(
            {
                "id": value(establishment, "FHRSID"),
                "name": value(establishment, "BusinessName"),
                "type": value(establishment, "BusinessType"),
                "address": address,
                "postcode": value(establishment, "PostCode"),
                "rating": value(establishment, "RatingValue"),
                "rating_date": value(establishment, "RatingDate"),
                "latitude": coordinate(establishment, "Latitude"),
                "longitude": coordinate(establishment, "Longitude"),
            }
        )

    DESTINATION.write_text(json.dumps(venues, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(venues)} food standards venues to {DESTINATION}")


if __name__ == "__main__":
    convert()
