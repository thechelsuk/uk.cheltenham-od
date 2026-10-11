"""Offline tests for the EPC fetcher (epc.py): picking each home's latest
certificate, summarising ratings and placing homes in areas.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location("epc", pathlib.Path(__file__).resolve().parents[1] / "epc.py")
assert SPEC is not None and SPEC.loader is not None
epc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(epc)


def cert(band, date, uprn=None, address="1 High Street", postcode="GL50 1AA"):
    return {"currentEnergyEfficiencyBand": band, "registrationDate": date, "uprn": uprn,
            "addressLine1": address, "addressLine2": None, "postcode": postcode}


def test_each_home_keeps_only_its_latest_certificate():
    certs = [
        cert("E", "2015-03-01", uprn=1), cert("C", "2024-06-01", uprn=1),
        cert("D", "2020-01-01", address="2 High Street"), cert("B", "2023-01-01", address="2 high street"),
        cert("Z", "2025-01-01", uprn=3),
    ]
    latest = epc.latest_per_home(certs)
    assert sorted((c["band"], c["postcode"]) for c in latest) == [("B", "GL50 1AA"), ("C", "GL50 1AA")]


def test_summary_counts_share_and_average():
    summary = epc.summarise(["A", "C", "C", "D", "G"])
    assert summary["homes"] == 5
    assert summary["counts"] == {"A": 1, "B": 0, "C": 2, "D": 1, "E": 0, "F": 0, "G": 1}
    assert summary["c_or_better_pct"] == 60.0
    assert summary["e_to_g_pct"] == 20.0
    assert summary["shares"]["C"] == 40.0
    assert summary["average_score"] == 4.4  # (7 + 5 + 5 + 4 + 1) / 5
    assert summary["average_band"] == "D"


def test_average_band_rounds_to_the_nearest_letter():
    assert epc.band_for(4.5) == "C"
    assert epc.band_for(4.49) == "D"
    assert epc.band_for(7) == "A"
    assert epc.band_for(1) == "G"


def test_homes_are_placed_in_the_area_containing_their_postcode():
    square = [[51.0, -2.0], [51.0, -1.0], [52.0, -1.0], [52.0, -2.0]]
    areas = [{"code": "X", "rings": [square]}]
    assert epc.area_for(51.5, -1.5, areas) == "X"
    assert epc.area_for(53.0, -1.5, areas) is None


def test_band_edges_split_values_into_six_and_stay_increasing():
    edges = epc.band_edges([4.1, 4.1, 4.1, 4.1, 4.1, 4.1, 4.2, 4.5], 2)
    assert len(edges) == 5
    assert edges == sorted(edges) and len(set(edges)) == 5
