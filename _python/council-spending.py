#!/usr/bin/env python3
"""Fetch Cheltenham Borough Council's monthly payments to suppliers (payments
of £500 or more, plus procurement card purchases), keep each month as
_data/council-spending/months/YYYY-MM.json, and build the yearly summary in
_data/council-spending/index.json.

The council publishes one CSV a month, about six weeks after the month ends,
so this runs weekly. Months already kept are read from disk; only months that
are new on the council's page, and the latest three (which the council
sometimes reissues), are downloaded. April 2016 to December 2019 came from the
web archive once, through _python/local/council-spending-backfill.py.
"""
import collections
import csv
import io
import json
import os
import re
from datetime import datetime, timezone

import helper

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "_data", "council-spending")
MONTHS_DIR = os.path.join(OUT_DIR, "months")

BASE = "https://www.cheltenham.gov.uk"
SOURCE_URL = (BASE + "/about-the-council/council-performance-and-spending/financial-information/"
              "payments-to-suppliers-and-procurement-card-purchases/")
SOURCE = "Cheltenham Borough Council"
LICENCE = "Open Government Licence v3.0"

FIRST_MONTH = "2016-04"   # the first month of the 2016-17 financial year
PAGE_YEARS = 5            # financial years with a page of their own
REFETCH_LATEST = 3        # recent months downloaded again in case they are reissued
MIN_PAYMENTS = 50         # a month with fewer rows than this can't be right
TOP_SUPPLIERS = 25
SUPPLIER_TABLE = 100
TOP_LAST_12 = 10

CARD_GROUP = "Council credit card purchases"
REDACTED_GROUP = "Redacted"

# For showing names the council's files give in capitals: words kept in
# capitals (initials and acronyms), words with a set spelling, and short
# words kept lower case inside a name.
UPPER_WORDS = {"BPE", "CBC", "CBRE", "CIC", "EA", "EDF", "EPC", "ICO", "NFU", "NHS", "PAYE", "SAS", "UK", "WME"}
SET_WORDS = {"LTD": "Ltd", "PLC": "plc", "MR": "Mr", "MRS": "Mrs", "MS": "Ms", "DR": "Dr", "ST": "St"}
LOWER_WORDS = {"and", "at", "by", "for", "in", "of", "on", "the", "to"}

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]

# Header spellings used by the council since 2010, squashed to letters only.
COLUMNS = {
    "organisationunit": "service", "organisationalunit": "service",
    "beneficiaryname": "supplier", "vendorname": "supplier", "suppliername": "supplier",
    "expensetype": "code", "expensecode": "code",
    "purpose": "purpose",
    "paymentdate": "date", "date": "date",
    "transactionnumber": "transaction", "transactionno": "transaction",
    "amount": "amount",
}

AMOUNT = re.compile(r"\(?-?£?\d[\d,]*(\.\d+)?\)?-?")


def squash(header):
    return re.sub(r"[^a-z]", "", str(header).lower())


def decode(raw):
    """The council's files are UTF-8, sometimes with a byte order mark, and
    some older ones Windows-1252."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def parse_amount(text):
    """A money amount as a float, or None when the cell isn't one (blank, a
    dash, or a value the council's spreadsheet turned into a date)."""
    value = str(text).strip().replace(" ", "").replace("£", "")
    if not value or not AMOUNT.fullmatch(value):
        return None
    negative = value.startswith("-") or value.endswith("-") or value.startswith("(")
    number = float(value.strip("()-").replace(",", ""))
    return -number if negative else number


def parse_date(text):
    value = str(text).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d %B %Y", "%d-%b-%y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def money(value, pence=False):
    sign = "-" if value < 0 else ""
    return f"{sign}£{abs(value):,.2f}" if pence else f"{sign}£{abs(value):,.0f}"


def parse_rows(rows, month):
    """Payments from a file's rows (lists of cells), whatever header spelling
    and title lines it has. Rows whose amount can't be read are counted in
    skipped; blank and section-title rows are ignored."""
    header_at = next((i for i, r in enumerate(rows) if any(squash(c) == "amount" for c in r)), None)
    if header_at is None:
        raise ValueError(f"{month}: no Amount column")
    fields = {}
    for i, name in enumerate(rows[header_at]):
        key = COLUMNS.get(squash(name))
        if key and key not in fields:
            fields[key] = i
    for key in ("supplier", "amount"):
        if key not in fields:
            raise ValueError(f"{month}: no {key} column")

    def cell(r, key):
        i = fields.get(key)
        return str(r[i]).strip() if i is not None and i < len(r) and r[i] is not None else ""

    payments, skipped = [], 0
    for r in rows[header_at + 1:]:
        supplier, raw_amount = cell(r, "supplier"), cell(r, "amount")
        if not supplier and not raw_amount:
            continue
        if raw_amount.replace("-", "").strip() == "" and not supplier:
            continue
        amount = parse_amount(raw_amount)
        if amount is None:
            if raw_amount.replace("-", "").strip():
                skipped += 1
            continue
        payments.append({
            "date": parse_date(cell(r, "date")),
            "supplier": re.sub(r"\s+", " ", supplier),
            "service": re.sub(r"\s+", " ", cell(r, "service")),
            "purpose": re.sub(r"\s+", " ", cell(r, "purpose")),
            "code": re.sub(r"\s+", " ", cell(r, "code")),
            "transaction": cell(r, "transaction"),
            "amount": round(amount, 2),
            "amount_display": money(amount, pence=True),
        })
    return {"payments": payments, "skipped": skipped}


def parse_text(text, month):
    return parse_rows(list(csv.reader(io.StringIO(text))), month)


def parse_links(html):
    """{"YYYY-MM": csv url} for every monthly CSV on the council's page."""
    links = {}
    pattern = re.compile(r'href="(/media/[^"]+\.csv)"', re.I)
    for path in pattern.findall(html):
        name = path.rsplit("/", 1)[-1].lower()
        found = re.search(r"(%s)[_-]?(\d{4})" % "|".join(MONTHS), name)
        if not found:
            continue
        key = f"{found.group(2)}-{MONTHS.index(found.group(1)) + 1:02d}"
        links.setdefault(key, BASE + path)
    return links


def display_word(word, first):
    if word in SET_WORDS:
        return SET_WORDS[word]
    if word in UPPER_WORDS or len(word) == 1 or re.search(r"\d", word) or not re.search(r"[AEIOUY]", word):
        return word
    if word.lower() in LOWER_WORDS and not first:
        return word.lower()
    parts = word.split("'")
    if len(parts[0]) == 1:
        return "'".join(part.capitalize() for part in parts)
    if word.startswith("MC") and len(word) > 3:
        return "Mc" + word[2:].capitalize()
    return word.capitalize()


def display_name(name):
    """A name as shown on the pages: one written all in capitals is put in
    title case, keeping initials, acronyms and legal suffixes right. Names
    with any lower case letters are shown as the council wrote them, apart
    from "REDACTED"."""
    if re.search(r"[a-z]", name):
        return re.sub(r"\bREDACTED\b", "Redacted", name)
    if not re.search(r"[A-Z]", name):
        return name
    seen = []

    def word(match):
        seen.append(match)
        return display_word(match.group(0), len(seen) == 1)
    return re.sub(r"[A-Z0-9']+", word, name)


def supplier_group(name):
    """The name a payment is ranked under: card purchases and withheld payees
    each as one line, other suppliers with spacing tidied and capitals eased."""
    upper = name.upper()
    # Barclaycard is paid each month for taking card payments at the car parks
    # ("credit card charges"): a supplier, whatever account details follow its name.
    if upper.strip().startswith("BARCLAYCARD"):
        return "Barclaycard"
    if re.search(r"CREDIT CARD|CHARGE CARD|CHG CARD|CORPORATE CARD|BUS(INESS)? CARD", upper):
        return CARD_GROUP
    if "REDACTED" in upper:
        return REDACTED_GROUP
    return display_name(re.sub(r"\s+", " ", name).strip())


def payment_name(name):
    """The supplier name shown against a single payment: as published, with
    capitals eased."""
    return display_name(re.sub(r"\s+", " ", name).strip())


def financial_year(month):
    year, mon = int(month[:4]), int(month[5:7])
    start = year if mon >= 4 else year - 1
    return f"{start}-{str(start + 1)[2:]}"


def year_label(year):
    start = int(year[:4])
    return f"April {start} to March {start + 1}"


def check_month(month, data):
    if len(data["payments"]) < MIN_PAYMENTS:
        raise ValueError(f"{month}: only {len(data['payments'])} payments read, which can't be right")


class Tally:
    """Payments added up by a name, keeping the most common spelling of it."""

    def __init__(self):
        self.total = collections.defaultdict(float)
        self.count = collections.Counter()
        self.spellings = collections.defaultdict(collections.Counter)

    def add(self, name, amount):
        key = name.upper()
        self.total[key] += amount
        self.count[key] += 1
        self.spellings[key][name] += 1

    def name(self, key):
        """The most common spelling, preferring one not written all in capitals."""
        ranked = [n for n, _ in self.spellings[key].most_common()]
        mixed = [n for n in ranked if re.search(r"[a-z]", n)]
        return display_name((mixed or ranked)[0])

    def ranked(self, limit=None):
        keys = sorted(self.total, key=lambda k: (-self.total[k], k))[:limit]
        return [{"name": self.name(k), "payments": round(self.total[k], 2),
                 "payments_display": money(self.total[k]), "count": self.count[k],
                 "count_display": f"{self.count[k]:,}"} for k in keys]


def totals(payments):
    out = sum(p["amount"] for p in payments if p["amount"] > 0)
    back = sum(p["amount"] for p in payments if p["amount"] < 0)
    count = sum(1 for p in payments if p["amount"] > 0)
    return {"payments": round(out, 2), "payments_display": money(out),
            "credits": round(back, 2), "credits_display": money(back),
            "count": count, "count_display": f"{count:,}"}


def withheld(payment):
    return supplier_group(payment["supplier"]) == REDACTED_GROUP


def withheld_totals(payments):
    """Money paid where the council withheld the payee's name, which the
    supplier rankings leave out because it isn't one supplier."""
    kept = [p["amount"] for p in payments if p["amount"] > 0 and withheld(p)]
    return {"payments": round(sum(kept), 2), "payments_display": money(sum(kept)),
            "count": len(kept), "count_display": f"{len(kept):,}"}


def build_index(months, page_years=PAGE_YEARS):
    """The yearly summary. Every year gets its totals; only the latest
    page_years get months, services and suppliers."""
    by_year = collections.defaultdict(list)
    for month in sorted(months):
        by_year[financial_year(month)].append(month)
    years_newest = sorted(by_year, reverse=True)
    detailed = set(years_newest[:page_years])

    years, monthly = [], []
    supplier_years = collections.defaultdict(dict)
    supplier_all = Tally()
    for year in years_newest:
        keys = by_year[year]
        payments = [p for m in keys for p in months[m]["payments"]]
        entry = {"year": year, "label": year_label(year), "first_month": keys[0], "last_month": keys[-1],
                 "months": len(keys), "complete": len(keys) == 12,
                 "skipped": sum(months[m].get("skipped", 0) for m in keys),
                 "has_page": year in detailed, **totals(payments),
                 "suppliers_count": len({supplier_group(p["supplier"]).upper() for p in payments
                                         if p["amount"] > 0 and not withheld(p)})}
        if year in detailed:
            services, suppliers = Tally(), Tally()
            for p in payments:
                if p["amount"] > 0:
                    services.add(p["service"] or "Not stated", p["amount"])
                    if not withheld(p):
                        group = supplier_group(p["supplier"])
                        suppliers.add(group, p["amount"])
                        supplier_all.add(group, p["amount"])
            entry["withheld"] = withheld_totals(payments)
            entry["month_totals"] = [{"month": m, "skipped": months[m].get("skipped", 0),
                                      **totals(months[m]["payments"])} for m in keys]
            entry["services"] = services.ranked()
            entry["top_suppliers"] = suppliers.ranked(TOP_SUPPLIERS)
            for s in suppliers.ranked():
                supplier_years[s["name"].upper()][year] = s
            monthly.extend(entry["month_totals"])
        years.append(entry)

    supplier_table = []
    for s in supplier_all.ranked(SUPPLIER_TABLE):
        per_year = supplier_years[s["name"].upper()]
        supplier_table.append({
            "name": s["name"], "total": s["payments"], "total_display": s["payments_display"],
            "count": s["count"], "count_display": s["count_display"],
            "years": [{"year": y, "payments": per_year[y]["payments"],
                       "payments_display": per_year[y]["payments_display"]}
                      for y in sorted(per_year, reverse=True)],
        })

    latest = sorted(months)[-1]
    last_12_keys = sorted(months)[-12:]
    last_12 = [p for m in last_12_keys for p in months[m]["payments"]]
    l12_services, l12_suppliers = Tally(), Tally()
    for p in last_12:
        if p["amount"] > 0:
            l12_services.add(p["service"] or "Not stated", p["amount"])
            if not withheld(p):
                l12_suppliers.add(supplier_group(p["supplier"]), p["amount"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "licence": LICENCE,
        "first_month": sorted(months)[0],
        "latest_month": latest,
        "page_years": [y for y in years_newest if y in detailed],
        "last_12": {"first_month": last_12_keys[0], "last_month": latest, **totals(last_12),
                    "withheld": withheld_totals(last_12),
                    "top_services": l12_services.ranked(TOP_LAST_12),
                    "top_suppliers": l12_suppliers.ranked(TOP_LAST_12)},
        "years": years,
        "monthly": sorted(monthly, key=lambda m: m["month"]),
        "suppliers": supplier_table,
    }


def month_path(month):
    return os.path.join(MONTHS_DIR, f"{month}.json")


def load_months():
    months = {}
    if os.path.isdir(MONTHS_DIR):
        for name in sorted(os.listdir(MONTHS_DIR)):
            if name.endswith(".json"):
                with open(os.path.join(MONTHS_DIR, name)) as f:
                    months[name[:-5]] = json.load(f)
    return months


def save_month(month, data, source_url):
    check_month(month, data)
    payments = [{**p, "supplier_display": payment_name(p["supplier"])} for p in data["payments"]]
    payload = {"month": month, "source_url": source_url, "skipped": data["skipped"], "payments": payments}
    return helper.write_json(month_path(month), payload)


def main():
    links = parse_links(helper.get(SOURCE_URL, timeout=60).text)
    if not links:
        raise ValueError("no monthly CSV links found on the council's page")
    months = load_months()
    wanted = [m for m in sorted(links) if m >= FIRST_MONTH]
    fetch = [m for m in wanted if m not in months] + [m for m in wanted[-REFETCH_LATEST:] if m in months]
    for month in fetch:
        data = parse_text(decode(helper.get(links[month], timeout=60).content), month)
        if save_month(month, data, links[month]):
            print(f"Wrote {month}: {len(data['payments'])} payments, {data['skipped']} unreadable")
    months = load_months()
    helper.write_json(os.path.join(OUT_DIR, "index.json"), build_index(months))
    print(f"Wrote index for {len(months)} months, {sorted(months)[0]} to {sorted(months)[-1]}")


if __name__ == "__main__":
    main()
