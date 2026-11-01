#!/usr/bin/env python3
"""Download every season's results file for the divisions Cheltenham Town
have played in from football-data.co.uk into _data-sources/football/
(gitignored), so the history can be rebuilt from local copies without
asking the site again.

Run manually, once, before building the history:

  python _python/local/football-data-download.py
  python _python/ctfc-results.py --all

Files already downloaded are skipped, so re-running only fetches what is
missing. The weekly job (_python/ctfc-results.py) refreshes just the current
season's file itself.

  Source: https://football-data.co.uk/englandm.php
  Key to the columns: https://football-data.co.uk/notes.txt
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import helper  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]

INDEX = "https://football-data.co.uk/englandm.php"
BASE = "https://football-data.co.uk/"
OUT = ROOT / "_data-sources" / "football"

# football-data.co.uk division codes for the tiers Cheltenham have played in, named by the tier's
# current name so a file keeps the same name across the 2004 rebranding of the divisions.
DIVISIONS = {"E2": "league-one", "E3": "league-two", "EC": "national-league"}


def local_name(code, division):
    """'0506', 'E3' -> 'season-2005-2006-league-two.csv'."""
    first = int(code[:2])
    start = (1900 if first > 50 else 2000) + first
    return f"season-{start}-{start + 1}-{DIVISIONS[division]}.csv"


def season_files(index_html):
    """(season code, division) for every file of the divisions above listed on the index page."""
    found = re.findall(r"mmz4281/(\d{4})/(E2|E3|EC)\.csv", index_html)
    return sorted(set(found))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    resp = helper.get(INDEX)
    resp.raise_for_status()
    files = season_files(resp.text)
    fetched = 0
    for code, division in files:
        path = OUT / local_name(code, division)
        if path.exists():
            continue
        r = helper.get(f"{BASE}mmz4281/{code}/{division}.csv", timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
        fetched += 1
        print(f"  {path.name}", flush=True)
        time.sleep(1)  # be gentle with a small free site
    print(f"{len(files)} season files listed, {fetched} downloaded, {len(files) - fetched} already here, in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
