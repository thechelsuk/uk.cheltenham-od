"""
planning.py

Fetches recent planning applications from Cheltenham Borough Council's
PublicAccess (Idox) portal by BOTH received date and decision date, merges
them into a running JSON store, and writes a render-ready data file.

Run:
    python planning.py          # hourly: current month, both date types
    python planning.py --deep   # backfill: walk MONTHS_DEEP months

Output:
    /_data/planning-applications.json
        { meta..., applications: [...], decided: [...] }

NOTES ON SELECTORS:
    Two spots depend on the exact Idox markup and should be confirmed with a
    DEBUG=True run before trusting the decided table:
      1. the date-type radio value for "Decided" (see set_date_type)
      2. the decision-date label in result items (see parse_result_item)
    Both are handled defensively, but verify against debug HTML.
"""

import re
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("planning")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

BASE_URL = "https://publicaccess.cheltenham.gov.uk/online-applications"
MONTHLY_LIST_URL = f"{BASE_URL}/search.do?action=monthlyList&searchType=Application"

# How many months of the list to walk. Hourly runs only need the current
# month (the merge keeps history); --deep backfills further.
MONTHS_NORMAL = 1
MONTHS_DEEP = 3

# Keep/show a record if its received OR decision date is within this window.
RETENTION_DAYS = 90

DATA_DIR = Path("_data")
DATA_FILE = DATA_DIR / "planning-applications.json"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

REQUEST_DELAY_SECONDS = 1.5
MAX_PAGES = 10

# Status text that counts as a reached decision (drives the decided table).
DECISION_TERMS = (
    "allow", "approv", "grant", "permit", "refus", "object",
    "withdraw", "dismiss", "decid", "split",
)

TODAY = datetime.now().strftime("%Y-%m-%d")

DEBUG = False


# ---------------------------------------------------------------------------
# FORM DISCOVERY
# ---------------------------------------------------------------------------

def _radio_label(form, inp):
    """Best-effort human label for a radio input."""
    iid = inp.get("id")
    if iid:
        lab = form.find("label", attrs={"for": iid})
        if lab:
            return lab.get_text(" ", strip=True).lower()
    parent = inp.find_parent(["label", "li", "div", "span"])
    return parent.get_text(" ", strip=True).lower() if parent else ""


def set_date_type(form, fields, date_type):
    """
    Point the date-type radio group at received / validated / decided.
    Matches on radio value or nearby label text rather than hardcoding the
    field name, since Idox varies. Leaves other radio groups untouched.
    """
    keyword = {"received": "receiv", "validated": "valid", "decided": "decid"}[date_type]
    for inp in form.find_all("input", attrs={"type": "radio"}):
        name = inp.get("name")
        value = (inp.get("value") or "")
        if not name:
            continue
        haystack = f"{value} {_radio_label(form, inp)}".lower()
        if keyword in haystack:
            fields[name] = value
            log.info("Date-type '%s' -> %s=%s", date_type, name, value)
            return True
    log.warning("Could not find a '%s' radio option; using form default", date_type)
    return False


def discover_form(html, base_url, date_type):
    """
    Parse the list search form for a given date type. Returns the action URL,
    the base field dict, the month field name, and the month option values
    (newest-first) so the caller can walk back multiple months.
    """
    soup = BeautifulSoup(html, "html.parser")
    forms = soup.find_all("form")

    months = ("jan", "feb", "mar", "apr", "may", "jun",
              "jul", "aug", "sep", "oct", "nov", "dec")

    form = None
    for f in forms:
        option_text = " ".join(
            o.get_text(strip=True) for s in f.find_all("select") for o in s.find_all("option")
        ).lower()
        if any(m in option_text for m in months):
            form = f
            break
    if form is None:
        form = forms[0] if forms else None
    if not form:
        raise RuntimeError("Could not find list search form on page")

    action_url = urljoin(base_url + "/", form.get("action"))

    fields = {}
    for inp in form.find_all("input"):
        itype = (inp.get("type") or "text").lower()
        name = inp.get("name")
        if not name:
            continue
        if itype == "hidden":
            fields[name] = inp.get("value", "")
        elif itype == "radio" and inp.has_attr("checked"):
            fields[name] = inp.get("value")

    # Non-month selects: submit their selected (or first) option.
    month_field = None
    month_values = []
    for select in form.find_all("select"):
        name = select.get("name")
        options = select.find_all("option")
        if not name or not options:
            continue
        option_texts = " ".join(o.get_text(strip=True) for o in options).lower()
        if any(m in option_texts for m in months):
            month_field = name
            month_values = [o.get("value", "") for o in options]  # newest-first
            fields[name] = month_values[0] if month_values else ""
        else:
            chosen = next((o for o in options if o.has_attr("selected")), options[0])
            fields[name] = chosen.get("value", "")

    set_date_type(form, fields, date_type)

    if month_field is None:
        log.warning("No month <select> detected - search may return the wrong period")

    return action_url, fields, month_field, month_values


# ---------------------------------------------------------------------------
# FETCHING
# ---------------------------------------------------------------------------

def fetch_page(session, action_url, fields, page_number):
    fields = dict(fields)
    if page_number > 1:
        fields["searchCriteria.page"] = page_number
    resp = session.post(action_url, data=fields, timeout=30)
    log.info("POST %s -> %s, %s bytes", resp.url, resp.status_code, len(resp.text))
    resp.raise_for_status()
    if DEBUG:
        Path(f"debug_{fields.get('searchCriteria.page', 1)}.html").write_text(resp.text, encoding="utf-8")
    return resp.text


def parse_results_page(html):
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.searchresult") or soup.select("ul#searchresults li")

    if DEBUG and items:
        log.info("--- RAW FIRST RESULT ITEM ---")
        log.info(str(items[0])[:2000])
        log.info("--- END ---")

    records = [r for r in (parse_result_item(i) for i in items) if r]
    has_next = bool(soup.select_one("a.next, a[title='Next']"))
    return records, has_next


def parse_result_item(item):
    link = item.select_one("a")
    if not link:
        return None

    detail_url = link.get("href", "")
    if detail_url and not detail_url.startswith("http"):
        detail_url = urljoin(BASE_URL + "/", detail_url)

    full_text = " ".join(item.get_text(separator=" ").split())

    ref_match = re.search(r"Ref\.?\s*No:?\s*([A-Z0-9/]+)", full_text, re.IGNORECASE)
    ref = ref_match.group(1) if ref_match else None
    if not ref:
        return None

    received_match = re.search(
        r"Received:\s*(?:\w{3}\s+)?(\d{1,2}\s+\w{3,9}\s+\d{4})", full_text, re.IGNORECASE)
    received_date = parse_date(received_match.group(1)) if received_match else None

    # Decision date label varies: "Decision:", "Decided:", "Decision Issued:".
    decided_match = re.search(
        r"(?:Decision(?:\s+Issued)?|Decided):\s*(?:\w{3}\s+)?(\d{1,2}\s+\w{3,9}\s+\d{4})",
        full_text, re.IGNORECASE)
    decided_date = parse_date(decided_match.group(1)) if decided_match else None

    status_el = item.select_one(".badge-status .value")
    status = status_el.get_text(strip=True) if status_el else "Unknown"

    description = link.get_text(strip=True)

    addr_el = item.select_one(".address, .location")
    if addr_el:
        address = addr_el.get_text(strip=True)
    else:
        after = full_text.split(description, 1)[-1]
        address = after.split("Ref")[0].strip(" -\u2013")

    return {
        "ref": ref,
        "description": description,
        "address": address,
        "postcode": extract_postcode(address or ""),
        "units": extract_units(description),
        "status": status,
        "received_date": received_date,
        "decided_date": decided_date,
        "url": detail_url,
    }


def parse_date(text):
    text = text.replace(".", "/")
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def extract_postcode(text):
    m = re.search(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", text.upper())
    return m.group(0) if m else None


def extract_units(description):
    m = re.search(r"(\d+)\s*(?:no\.?|x)?\s*(?:dwellings?|flats?|units?|apartments?)",
                  description, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if re.search(r"\bdwelling\b", description, re.IGNORECASE) and "dwellings" not in description.lower():
        return 1
    return None


def fetch_by_date_type(session, form_html, date_type, months):
    action_url, fields, month_field, month_values = discover_form(form_html, BASE_URL, date_type)

    collected = []
    seen = set()
    walk = month_values[:months] if (month_field and month_values) else [None]

    for mv in walk:
        if month_field and mv is not None:
            fields[month_field] = mv
        page = 1
        while page <= MAX_PAGES:
            try:
                html = fetch_page(session, action_url, fields, page)
            except requests.RequestException as exc:
                log.error("Request failed (%s, month=%s, page=%s): %s", date_type, mv, page, exc)
                break
            records, has_next = parse_results_page(html)
            fresh = [r for r in records if r["ref"] not in seen]
            log.info("%s month=%s page=%s: %s records (%s new)", date_type, mv, page, len(records), len(fresh))
            if not fresh:
                break
            for r in fresh:
                # If the decided search found it but the list didn't expose a
                # decision date, floor it to today so retention keeps it and
                # the decided table can still surface it.
                if date_type == "decided" and not r["decided_date"]:
                    r["decided_date"] = TODAY
                seen.add(r["ref"])
            collected.extend(fresh)
            if not has_next:
                break
            page += 1
            time.sleep(REQUEST_DELAY_SECONDS)

    return collected


def fetch_all(months):
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)

    log.info("Loading list search form: %s", MONTHLY_LIST_URL)
    form_resp = session.get(MONTHLY_LIST_URL, timeout=30)
    form_resp.raise_for_status()
    if DEBUG:
        Path("debug_form_page.html").write_text(form_resp.text, encoding="utf-8")

    all_records = []
    # Received first, then decided so decision status/date win on merge.
    for date_type in ("received", "decided"):
        all_records.extend(fetch_by_date_type(session, form_resp.text, date_type, months))
    return all_records


# ---------------------------------------------------------------------------
# STORE
# ---------------------------------------------------------------------------

def load_existing():
    if not DATA_FILE.exists():
        return {}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            recs = []
            for key in ("applications", "decided"):
                val = data.get(key)
                if isinstance(val, list):
                    recs.extend(val)
        else:
            recs = data  # legacy flat array
        return {r["ref"]: r for r in recs if isinstance(r, dict) and r.get("ref")}
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning("Could not parse existing store (%s); starting fresh", exc)
        return {}



def merge_records(existing, new_records):
    """Field-wise merge: a non-empty new value wins, but we never blank an
    existing value (so a decided-search hit can't wipe received_date)."""
    for rec in new_records:
        ref = rec["ref"]
        if ref in existing:
            for k, v in rec.items():
                if v not in (None, "", []):
                    existing[ref][k] = v
        else:
            existing[ref] = rec
    return existing


def is_decision(status):
    s = (status or "").lower()
    return any(term in s for term in DECISION_TERMS)


def best_date(r):
    return r.get("decided_date") or r.get("received_date") or ""


def apply_retention(records_by_ref):
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    kept = {}
    for ref, r in records_by_ref.items():
        rec_ok = (r.get("received_date") or "") >= cutoff
        dec_ok = (r.get("decided_date") or "") >= cutoff
        if rec_ok or dec_ok:
            kept[ref] = r
    dropped = len(records_by_ref) - len(kept)
    if dropped:
        log.info("Dropped %s records outside the %s-day window", dropped, RETENTION_DAYS)
    return kept


def build_payload(records_by_ref):
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    records = list(records_by_ref.values())

    applications = sorted(
        (r for r in records if (r.get("received_date") or "") >= cutoff),
        key=lambda r: r.get("received_date") or "", reverse=True)

    decided = sorted(
        (r for r in records if is_decision(r.get("status")) and best_date(r) >= cutoff),
        key=best_date, reverse=True)

    rec_dates = [r["received_date"] for r in applications if r.get("received_date")]
    now = datetime.now()
    pending = sum(1 for r in applications if not is_decision(r.get("status")))


    return {
        "updated": now.strftime("%d %B %Y"),
        "updated_iso": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "lookback_days": RETENTION_DAYS,
        "received_count": len(applications),
        "pending": pending,
        "decided_count": len(decided),
        "date_from": min(rec_dates) if rec_dates else None,
        "date_to": max(rec_dates) if rec_dates else None,
        "applications": applications,
        "decided": decided,
    }


def save_payload(payload):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Saved %s applications / %s decided to %s",
             payload["received_count"], payload["decided_count"], DATA_FILE)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deep", action="store_true", help="walk more months for backfill")
    args = parser.parse_args()

    months = MONTHS_DEEP if args.deep else MONTHS_NORMAL
    new_records = fetch_all(months)

    if not new_records:
        log.warning("No records fetched; leaving existing store untouched")
        return

    merged = merge_records(load_existing(), new_records)
    merged = apply_retention(merged)
    save_payload(build_payload(merged))


if __name__ == "__main__":
    main()
