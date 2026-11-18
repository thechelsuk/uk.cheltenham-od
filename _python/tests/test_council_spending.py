"""Offline tests for the council spending fetcher (council-spending.py):
reading Cheltenham Borough Council's monthly payments-to-suppliers files,
finding them on the council's page, and building the yearly summary in
_data/council-spending/index.json.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import pathlib

import pytest

SPEC = importlib.util.spec_from_file_location(
    "council_spending", pathlib.Path(__file__).resolve().parents[1] / "council-spending.py"
)
assert SPEC is not None and SPEC.loader is not None
cs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cs)

HEADER_2026 = ("OrganisationURI,OrganisationLabel,Organisation Unit,TransactionNumber,Beneficiary Name,"
               "Expense Type,Purpose,Payment Date,Amount")
URI = "https://opendatacommunities.org/doc/district-council/cheltenham "


def row(unit, supplier, code, purpose, date, amount, txn="14149289"):
    return f'{URI},Cheltenham Borough Council,{unit},{txn},{supplier},{code},{purpose},{date},{amount}'


FILE_2026 = "\n".join([
    HEADER_2026,
    row("Household Waste", "Ubico Limited", "R5001 - ENV001", "TPP - Major External Contractors",
        "16/09/2026", '"1,032,987.00"'),
    row("Public Conveniences R&M", "Personnel Hygiene Services Ltd T/A PHS Interclean", "R2083 - PCV001",
        "R&M of Build - Routine", "30/09/2026", "829.89"),
    row("Marketing Cheltenham", "Lloyds Corporate Credit Card -   Intuit Limited - Mailchimp",
        "R4014 - TOU002", "Marketing", "16/09/2026", "336.73"),
    row("Homelessness", "REDACTED", "R4401 - HOS100", "Services - Fees and Charges", "02/09/2026", "650"),
    row("Response Repairs", "A & E Fire and Security Ltd", "R5006 - HRA540", "Sub Contractor Payments",
        "30/09/2026", "-120.50"),
    "",
])


def test_reads_a_current_file_into_payments():
    month = cs.parse_text(FILE_2026, "2026-09")
    assert month["skipped"] == 0
    first = month["payments"][0]
    assert first == {
        "date": "2026-09-16",
        "supplier": "Ubico Limited",
        "service": "Household Waste",
        "purpose": "TPP - Major External Contractors",
        "code": "R5001 - ENV001",
        "transaction": "14149289",
        "amount": 1032987.0,
        "amount_display": "£1,032,987.00",
    }
    assert [p["amount"] for p in month["payments"]] == [1032987.0, 829.89, 336.73, 650.0, -120.5]


def test_older_header_spellings_and_a_title_preamble_are_read():
    text = "\n".join([
        ",,,,,,,,,",
        "Cheltenham Borough Council Payments To Suppliers,,,,,,,,,",
        "OrganisationURI,OrganisationLabel,OrganisationalUnit,TransactionNumber,Invoice Ref.,"
        "BeneficiaryName,Expense Type,Purpose,PaymentDate, Amount ,",
        "http://statistics.data.gov.uk/id/local-authority-district/23UB,Cheltenham Borough Council,"
        'Repairs and Maintenance,14045405,184501,A & E Fire Equipment Limited,R2083-HRA100,'
        'R&M of Build - Routine,10/06/2016,"1,094.36 ",',
    ])
    month = cs.parse_text(text, "2016-06")
    assert month["payments"][0]["supplier"] == "A & E Fire Equipment Limited"
    assert month["payments"][0]["service"] == "Repairs and Maintenance"
    assert month["payments"][0]["amount"] == 1094.36


def test_amounts_the_council_file_shows_as_dates_are_skipped_and_counted():
    text = "\n".join([
        HEADER_2026,
        row("Cheltenham Municipal Offices", "WME - MUNICIPAL OFFICES", "R2101-ADB101", "Gas",
            "19/06/2017", "03/06/1903"),
        row("Treasury Management", "Bank charges", "R4403-COR006", "Bank Charges", "24/06/2017", "650.00"),
        "Bank Transaction Data,,,,,,,,",
    ])
    month = cs.parse_text(text, "2017-06")
    assert [p["amount"] for p in month["payments"]] == [650.0]
    assert month["skipped"] == 1


@pytest.mark.parametrize("raw, value", [
    ('1,032,987.00', 1032987.0), (' 1,094.36 ', 1094.36), ('-120.50', -120.5), ('£2,580.00', 2580.0),
    ('615', 615.0), ('(45.00)', -45.0),
])
def test_amounts(raw, value):
    assert cs.parse_amount(raw) == value


@pytest.mark.parametrize("raw", ["03/06/1903", "", " -   ", "n/a"])
def test_unreadable_amounts(raw):
    assert cs.parse_amount(raw) is None


@pytest.mark.parametrize("raw, iso", [
    ("16/09/2026", "2026-09-16"), ("2019-02-15 00:00:00", "2019-02-15"), ("22 June 2012", "2012-06-22"),
])
def test_dates(raw, iso):
    assert cs.parse_date(raw) == iso


def test_rows_from_a_spreadsheet_are_read_the_same_way():
    rows = [
        ["OrganisationURI", "OrganisationLabel", "Organisation Unit", "TransactionNumber", "Invoice Ref.",
         "Beneficiary Name", "Expense Type", "Purpose", "Payment Date", "Amount"],
        ["x", "Cheltenham Borough Council", "Repairs and Maintenance", "14065825", "211282",
         "A & E Fire and Security Ltd", "R2042-HRA100", "R & M of Build Fire Systems", "2019-02-15 00:00:00",
         "631.81"],
    ]
    month = cs.parse_rows(rows, "2019-02")
    assert month["payments"][0]["date"] == "2019-02-15"
    assert month["payments"][0]["amount"] == 631.81


def test_cp1252_files_are_decoded():
    assert cs.decode("ICT – HRA".encode("cp1252")) == "ICT – HRA"
    assert cs.decode("﻿Amount".encode("utf-8")) == "Amount"


PAGE = """<main>
<h2>Council spending in 2026</h2>
<a href="/media/jgvhlbjd/september_2026_bank_payments.xlsx">September 2026 bank payments (XLSX)</a>
<a href="/media/id4cbiqb/september_2026_bank_payments.csv">September 2026 bank payments (CSV)</a>
<a href="/media/a1tmapqz/october_2025_payments_to_suppliers.csv">October 2025 bank payments (CSV)</a>
<a href="/media/rmeh1b2g/april2025_bank_payments.csv">April 2025 bank payments - csv</a>
<a href="/media/pqfayc5s/may2021_bank_payments.csv">May 2021 Bank Payments (XLSX)</a>
</main>"""


def test_finds_each_months_csv_on_the_council_page():
    assert cs.parse_links(PAGE) == {
        "2026-09": "https://www.cheltenham.gov.uk/media/id4cbiqb/september_2026_bank_payments.csv",
        "2025-10": "https://www.cheltenham.gov.uk/media/a1tmapqz/october_2025_payments_to_suppliers.csv",
        "2025-04": "https://www.cheltenham.gov.uk/media/rmeh1b2g/april2025_bank_payments.csv",
        "2021-05": "https://www.cheltenham.gov.uk/media/pqfayc5s/may2021_bank_payments.csv",
    }


@pytest.mark.parametrize("name, group", [
    ("Ubico  Limited", "Ubico Limited"),
    ("Lloyds Corporate Credit Card -   Intuit Limited - Mailchimp", cs.CARD_GROUP),
    ("BUS CHG CARD - REDACTED - UK MAIL", cs.CARD_GROUP),
    ("Business Charge Card - REDACTED - The Woodland Trust", cs.CARD_GROUP),
    ("REDACTED", cs.REDACTED_GROUP),
    ("Purchase of REDACTED", cs.REDACTED_GROUP),
    ("EDF ENERGY", "EDF Energy"),
    ("Lloyds Corporate Card - REDACTED - Selco", cs.CARD_GROUP),
    ("BUSINESS CARD CHARGE - REDACTED - ROMAN BATHS", cs.CARD_GROUP),
    # Barclaycard's monthly car park card-processing charges: a supplier, not card purchases
    ("BARCLAYCARD REDACTED", "Barclaycard"),
    ("BARCLAYCARD -REDACTED", "Barclaycard"),
    ("BARCLAYCARD - 1154295310723", "Barclaycard"),
    ("BARCLAYCARD", "Barclaycard"),
    ("CARDNET SERVICE CHARGES", "Cardnet Service Charges"),
    ("CARDO (WALES & WEST) LIMITED", "Cardo (Wales & West) Limited"),
])
def test_supplier_groups(name, group):
    assert cs.supplier_group(name) == group


def test_withheld_names_have_a_plain_label():
    assert cs.REDACTED_GROUP == "Redacted"


@pytest.mark.parametrize("name, shown", [
    ("NETWORK MERCHANTS", "Network Merchants"),
    ("EDF ENERGY", "EDF Energy"),
    ("CARDNET SERVICE CHARGES", "Cardnet Service Charges"),
    ("ANTHONY COL F/FLOWSHURDINGTON", "Anthony Col F/Flowshurdington"),
    ("BPE SOLICITORS LLP", "BPE Solicitors LLP"),
    ("NFU MUTUAL COMBINED FUND", "NFU Mutual Combined Fund"),
    ("HMRC PAYE", "HMRC PAYE"),
    ("ACME SERVICES LTD", "Acme Services Ltd"),
    ("WIDGETS UK PLC", "Widgets UK plc"),
    ("FRIENDS OF THE PARK CIC", "Friends of the Park CIC"),
    ("THE ROYAL BRITISH LEGION", "The Royal British Legion"),
    ("ST JOHN'S CHURCH", "St John's Church"),
    ("O'BRIEN & MCDONALD", "O'Brien & McDonald"),
    ("ROOM HIRE GL50 1QA", "Room Hire GL50 1QA"),
    ("Ubico Limited", "Ubico Limited"),
    ("UBICO Limited", "UBICO Limited"),
    ("WME - AUGUST - COOPERS COURT", "WME - August - Coopers Court"),
    ("REDACTED", "Redacted"),
    ("Purchase of REDACTED", "Purchase of Redacted"),
    ("", ""),
])
def test_all_capital_names_are_shown_in_title_case(name, shown):
    assert cs.display_name(name) == shown


def test_rankings_prefer_the_spelling_that_isnt_all_capitals():
    tally = cs.Tally()
    for name in ("EDF ENERGY", "EDF ENERGY", "EDF Energy"):
        tally.add(name, 100.0)
    assert [s["name"] for s in tally.ranked()] == ["EDF Energy"]
    tally = cs.Tally()
    tally.add("NETWORK MERCHANTS", 100.0)
    assert tally.ranked()[0]["name"] == "Network Merchants"


def test_each_payment_keeps_the_councils_name_and_gains_a_display_name(tmp_path, monkeypatch):
    monkeypatch.setattr(cs, "MONTHS_DIR", str(tmp_path))
    written = {}
    monkeypatch.setattr(cs.helper, "write_json", lambda path, data: written.update(data) or True)
    payments = [pay("EDF ENERGY", "Energy", 600.0, "2026-09-01"), pay("REDACTED", "Homes", 700.0, "2026-09-02"),
                pay("Business Charge Card - REDACTED - The Woodland Trust", "Parks", 800.0, "2026-09-03")]
    cs.save_month("2026-09", {"payments": payments * 20, "skipped": 0}, "https://example.org")
    shown = [(p["supplier"], p["supplier_display"]) for p in written["payments"][:3]]
    assert shown == [("EDF ENERGY", "EDF Energy"), ("REDACTED", "Redacted"),
                     ("Business Charge Card - REDACTED - The Woodland Trust",
                      "Business Charge Card - Redacted - The Woodland Trust")]


@pytest.mark.parametrize("month, year", [("2026-03", "2025-26"), ("2026-04", "2026-27"), ("2016-04", "2016-17")])
def test_financial_year(month, year):
    assert cs.financial_year(month) == year


def pay(supplier, service, amount, date):
    return {"supplier": supplier, "service": service, "amount": amount, "date": date}


def test_index_keeps_payments_and_credits_apart_and_details_only_recent_years():
    months = {
        "2016-04": {"payments": [pay("Ubico Limited", "Household Waste", 1000.0, "2016-04-08")], "skipped": 0},
        "2025-04": {"payments": [
            pay("Ubico Limited", "Household Waste", 500.0, "2025-04-04"),
            pay("ubico limited", "Household Waste", 250.0, "2025-04-11"),
            pay("REDACTED", "Homelessness", 900.0, "2025-04-11"),
            pay("Some Ltd", "Trees", -100.0, "2025-04-18"),
        ], "skipped": 2},
        "2026-09": {"payments": [pay("Ubico Limited", "Household Waste", 2000.0, "2026-09-16")], "skipped": 0},
    }
    index = cs.build_index(months, page_years=2)
    years = {y["year"]: y for y in index["years"]}
    assert list(years) == ["2026-27", "2025-26", "2016-17"]

    recent = years["2025-26"]
    assert recent["payments"] == 1650.0 and recent["payments_display"] == "£1,650"
    assert recent["credits"] == -100.0 and recent["credits_display"] == "-£100"
    assert recent["count"] == 3 and recent["skipped"] == 2
    assert recent["has_page"] and recent["months"] == 1 and not recent["complete"]
    assert [s["name"] for s in recent["top_suppliers"]] == ["Ubico Limited"]
    assert recent["top_suppliers"][0]["payments"] == 750.0
    assert recent["withheld"] == {"payments": 900.0, "payments_display": "£900", "count": 1, "count_display": "1"}
    assert recent["suppliers_count"] == 1
    assert recent["services"][0]["name"] == "Homelessness"

    old = years["2016-17"]
    assert old["payments"] == 1000.0 and not old["has_page"]
    assert "services" not in old and "top_suppliers" not in old

    assert [m["month"] for m in index["monthly"]] == ["2025-04", "2026-09"]
    assert index["latest_month"] == "2026-09"
    ubico = next(s for s in index["suppliers"] if s["name"] == "Ubico Limited")
    assert ubico["total"] == 2750.0
    assert [y["year"] for y in ubico["years"]] == ["2026-27", "2025-26"]
    assert ubico["years"][1]["payments_display"] == "£750"


def test_a_month_with_too_few_payments_is_refused():
    with pytest.raises(ValueError):
        cs.check_month("2026-09", {"payments": [pay("A", "B", 1.0, "2026-09-01")] * 10, "skipped": 0})
