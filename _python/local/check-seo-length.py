#!/usr/bin/env python3
"""List every `seo:` front matter value longer than 160 characters.

`seo` is the meta description in _includes/header.html, and search results cut
descriptions off at about 160 characters. Run from the repo root before opening a
PR that adds or edits pages, posts, classifieds or events:

  python _python/local/check-seo-length.py

Exits with status 1 if any are over the limit, so it can also be used in a hook.
"""
import glob
import re
import sys

import yaml

LIMIT = 160
PATTERNS = ["_pages/**/*.md", "_posts/*.md", "_classifieds/*.md", "_events/*.md"]


def main():
    over = []
    for pattern in PATTERNS:
        for path in sorted(glob.glob(pattern, recursive=True)):
            with open(path, encoding="utf-8") as f:
                match = re.match(r"^---\n(.*?)\n---", f.read(), re.S)
            if not match:
                continue
            try:
                seo = (yaml.safe_load(match.group(1)) or {}).get("seo")
            except yaml.YAMLError:
                continue
            if isinstance(seo, str) and len(seo) > LIMIT:
                over.append((len(seo), path))
    for length, path in sorted(over, reverse=True):
        print(f"{length} {path}")
    print(f"{len(over)} seo value(s) over {LIMIT} characters")
    sys.exit(1 if over else 0)


if __name__ == "__main__":
    main()
