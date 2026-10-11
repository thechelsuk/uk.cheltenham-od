"""Offline tests for the local EPC scores job (local/epc-scores.py): reading
certificate details and summarising homes by area, type, tenure and heating.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "epc_scores", pathlib.Path(__file__).resolve().parents[1] / "local" / "epc-scores.py"
)
assert SPEC is not None and SPEC.loader is not None
scores = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scores)

LABELS = {
    "tenure": {"1": "owner-occupied", "2": "rented (social)", "3": "rented (private)", "ND": "unknown"},
    "property_type": {"0": "house", "1": "bungalow", "2": "flat", "3": "maisonette"},
    "built_form": {"1": "detached", "2": "semi-detached", "4": "mid-terrace", "6": "enclosed mid-terrace", "NR": "not recorded"},
}


def test_details_reads_scores_and_unwraps_costs():
    data = {
        "energy_rating_current": 76, "energy_rating_potential": 80, "potential_energy_efficiency_band": "C",
        "tenure": 2, "property_type": 0, "built_form": 4, "total_floor_area": 69,
        "heating_cost_current": {"value": 501, "currency": "GBP"}, "main_heating": [{"description": "Boiler and radiators, mains gas"}],
        "sap_building_parts": [{"construction_age_band": "H"}], "postcode": "GL50 1AA", "address_line_1": "1 High Street",
    }
    fields = scores.details(data)
    assert fields["score"] == 76.0 and fields["potential_score"] == 80.0
    assert fields["heating_cost"] == 501.0 and fields["age_band"] == "H"
    assert "postcode" not in fields and "address_line_1" not in fields


def test_homes_without_a_uprn_are_keyed_by_a_hash_not_their_address():
    key = scores.home_key({"uprn": None, "addressLine1": "1 High Street", "postcode": "GL50 1AA"})
    assert key.startswith("address:") and "HIGH" not in key
    assert scores.home_key({"uprn": 123}) == "uprn:123"


def test_home_type_tenure_and_heating_labels():
    assert scores.home_type({"property_type": 0, "built_form": 4}, LABELS) == "Mid-terrace house"
    assert scores.home_type({"property_type": 0, "built_form": 6}, LABELS) == "Mid-terrace house"
    assert scores.home_type({"property_type": 2, "built_form": 4}, LABELS) == "Flat"
    assert scores.tenure({"tenure": 3}, LABELS) == "Private rented"
    assert scores.tenure({"tenure": "rental (social)"}, LABELS) == "Social rented"
    assert scores.tenure({"tenure": "ND"}, LABELS) is None
    assert scores.heating({"main_heating": "Air source heat pump, radiators, electric"}) == "Heat pump"
    assert scores.heating({"main_heating": "Electric storage heaters"}) == "Electric"
    assert scores.heating({"main_heating": "Boiler and radiators, mains gas"}) == "Mains gas"
    assert scores.heating({"main_heating": {"language": "1", "value": "Room heaters, electric"}}) == "Electric"


def test_summary_of_a_group_of_homes():
    homes = [
        {"band": "C", "score": 72, "potential_band": "B"},
        {"band": "D", "score": 60, "potential_band": "C"},
        {"band": "E", "score": 45, "potential_band": "D"},
        {"band": "B", "score": 85, "potential_band": "A"},
    ]
    summary = scores.summarise(homes)
    assert summary["homes"] == 4 and summary["median_score"] == 66
    assert summary["c_plus_pct"] == 50.0 and summary["below_c"] == 2
    assert summary["potential_c_plus_pct"] == 75.0
