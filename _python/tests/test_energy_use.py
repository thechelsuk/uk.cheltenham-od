"""Offline tests for the gas and electricity use fetcher (energy-use.py):
reading council and small-area sheets and grouping small areas into wards.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

SPEC = importlib.util.spec_from_file_location(
    "energy_use", pathlib.Path(__file__).resolve().parents[1] / "energy-use.py")
assert SPEC is not None and SPEC.loader is not None
energy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(energy)


def test_council_sheets_read_old_and_new_headings_alike():
    old = [("Title",), ("Code", "Country or region", "Local authority",
                        "Number of meters\n(thousands):\nDomestic ", "Number of meters\n(thousands):\nNon-Domestic",
                        "Total consumption\n(GWh):\nDomestic ", "Total consumption\n(GWh):\nNon-Domestic",
                        "Mean consumption\n(kWh per meter):\nDomestic "),
           ("E07000078", "South West", "Cheltenham", 50.0, 4.0, 200.0, 300.0, 4000.0)]
    new = [("Code", "Country or region", "Local authority", "Notes",
            "Number of meters\n(thousands):\nAll Domestic", "Number of meters\n(thousands):\nAll Non-Domestic",
            "Total consumption\n(GWh):\nAll Domestic", "Total consumption\n(GWh):\nAll Non-Domestic",
            "Mean consumption\n(kWh per meter):\nAll Domestic", "Median consumption\n(kWh per meter):\nAll Domestic"),
           ("E92000001", "England", "All local authorities", None, 20000.0, 2000.0, 80000.0, 90000.0, 3000.0, 2500.0)]
    assert energy.council_rows(old)["E07000078"] == {
        "domestic_meters": 50000, "domestic_gwh": 200.0, "non_domestic_gwh": 300.0,
        "mean_kwh": 4000, "median_kwh": None}
    assert energy.council_rows(new)["E92000001"]["median_kwh"] == 2500


def test_sheets_before_2012_are_matched_on_area_names():
    rows = [("Code", "Country or region", "Local authority", "Number of meters (thousands): Domestic",
             "Total consumption (GWh): Domestic", "Total consumption (GWh): Non-Domestic",
             "Mean consumption (kWh per meter): Domestic"),
            (None, "England", "All local authorities", 21000.0, 90000.0, 100000.0, 4200.0),
            ("UKK1301", "South West", "Cheltenham", 47.8, 200.0, 250.0, 4100.0)]
    found = energy.council_rows(rows)
    assert set(found) == {"E92000001", "E07000078"}
    assert found["E07000078"]["mean_kwh"] == 4100


def test_small_area_rows_keep_only_cheltenham():
    rows = [("Local authority code", "Local authority", "MSOA code", "Middle layer super output area",
             "LSOA code", "Lower layer super output area", "Number\nof meters", "Total \nconsumption\n(kWh)",
             "Mean \nconsumption\n(kWh per meter)", "Median \nconsumption\n(kWh per meter)"),
            ("E07000078", "Cheltenham", "E02004600", "Cheltenham 001", "E01022163", "Cheltenham 001A",
             603, 1714492.2, 2843.3, 2253.6),
            ("E07000079", "Cotswold", "E02", "Cotswold 001", "E01999999", "Cotswold 001A", 1, 2, 3, 4)]
    assert energy.small_area_rows(rows) == {
        "E01022163": {"meters": 603, "kwh": 1714492.2, "mean_kwh": 2843, "median_kwh": 2254}}


def test_wards_add_up_their_small_areas_and_take_a_weighted_mean():
    lsoas = [{"code": "A", "ward_code": "W1"}, {"code": "B", "ward_code": "W1"}, {"code": "C", "ward_code": "W2"}]
    use = {"A": {"meters": 100, "kwh": 300000.0}, "B": {"meters": 300, "kwh": 600000.0}}
    wards = energy.by_ward(lsoas, use)
    assert wards["W1"] == {"meters": 400, "kwh": 900000.0, "mean_kwh": 2250}
    assert "W2" not in wards
