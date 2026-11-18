#!/usr/bin/env python3
"""Fill _data/council-spending/months/ for April 2016 to December 2019 from
Cheltenham Borough Council's original payments-to-suppliers files, which the
council's current site no longer lists. The files were downloaded once from
the web archive's copies of the council's old "Payments to suppliers - YYYY"
pages, and are kept in the raw data repository (uk.cheltenham-od.raw) under
sources/cbc-payments-to-suppliers/, named YYYY-MM.csv. Where the council
reissued a month, the reissue is YYYY-MM-revised.csv and is used instead.
February 2019 survives only as YYYY-MM.xls, read with xlrd
(requirements-dev.txt).

Each month is read exactly as council-spending.py reads a current month, and
the yearly index is rebuilt afterwards. Running it again is safe: it rewrites
the same months.

  python _python/local/council-spending-backfill.py ../uk.cheltenham-od.raw/sources/cbc-payments-to-suppliers
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "council_spending", Path(__file__).resolve().parents[1] / "council-spending.py")
assert SPEC is not None and SPEC.loader is not None
cs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cs)

ARCHIVE = "https://web.archive.org/web/2024/https://www.cheltenham.gov.uk/downloads/download/"
ARCHIVE_PAGES = {
    "2016": ARCHIVE + "1306/payments_to_suppliers_-_2016",
    "2017": ARCHIVE + "1441/payments_to_suppliers_-_2017",
    "2018": ARCHIVE + "1586/payments_to_suppliers_-_2018",
    "2019": ARCHIVE + "1694/payments_to_suppliers_-_2019",
}


def original(folder, month):
    for name in (f"{month}-revised.csv", f"{month}.csv", f"{month}.xls"):
        path = folder / name
        if path.exists():
            return path
    return None


def read(path, month):
    if path.suffix == ".xls":
        import pandas as pd
        frame = pd.read_excel(path, header=None, dtype=str).fillna("")
        return cs.parse_rows(frame.values.tolist(), month)
    return cs.parse_text(cs.decode(path.read_bytes()), month)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--from", dest="start", default=cs.FIRST_MONTH)
    parser.add_argument("--to", dest="end", default="2019-12")
    args = parser.parse_args()

    months = [f"{y}-{m:02d}" for y in range(int(args.start[:4]), int(args.end[:4]) + 1) for m in range(1, 13)]
    for month in [m for m in months if args.start <= m <= args.end]:
        path = original(args.folder, month)
        if not path:
            print(f"{month}: no original file, skipped")
            continue
        data = read(path, month)
        cs.save_month(month, data, ARCHIVE_PAGES.get(month[:4], cs.SOURCE_URL))
        print(f"{month}: {len(data['payments'])} payments, {data['skipped']} unreadable, from {path.name}")

    helper.write_json(os.path.join(cs.OUT_DIR, "index.json"), cs.build_index(cs.load_months()))


if __name__ == "__main__":
    main()
