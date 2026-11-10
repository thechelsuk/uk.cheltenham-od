#!/usr/bin/env python3
"""Choose which pages to tell IndexNow about after a deploy.

IndexNow asks to be told only about pages that are new or have really
changed, not the whole site on every deploy. The sitemap already gives each
page the time it, or the data it shows, last changed
(_plugins/data_freshness.rb), so the pages to send are those whose <lastmod>
is later than the commit the last successful deploy published. Each change
is then sent once, however long ago that deploy was.

Pages in _data/indexnow.json's "exclude" list are never sent: the home page,
whose lastmod is the build time, and pages that change on almost every run.
The sitemap still covers them. A page with no lastmod is left out too.

Run from the repository root, after a build:
    .venv/bin/python _python/indexnow-urls.py --since 2026-11-10T14:00:10+00:00

Prints the URLs as a JSON list. In GitHub Actions it is also written to
$GITHUB_OUTPUT as `urls`. Uses only the standard library, so the deploy
workflow can run it without installing anything.
"""
import argparse
import json
import os
import pathlib
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
SITEMAP = ROOT / "_site" / "sitemap.xml"
SETTINGS = ROOT / "_data" / "indexnow.json"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def changed_urls(sitemap_xml, since, exclude=()):
    """URLs in the sitemap whose lastmod is after `since`, in sitemap order."""
    excluded = set(exclude)
    urls = []
    for entry in ET.fromstring(sitemap_xml).findall("s:url", NS):
        loc = (entry.findtext("s:loc", default="", namespaces=NS) or "").strip()
        lastmod = (entry.findtext("s:lastmod", default="", namespaces=NS) or "").strip()
        if not loc or not lastmod:
            continue
        if (urlparse(loc).path or "/") in excluded:
            continue
        if datetime.fromisoformat(lastmod) > since:
            urls.append(loc)
    return urls


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", required=True, help="commit time of the last successful deploy, ISO 8601")
    parser.add_argument("--sitemap", default=str(SITEMAP))
    args = parser.parse_args()

    exclude = json.loads(SETTINGS.read_text())["exclude"]
    urls = changed_urls(pathlib.Path(args.sitemap).read_text(), datetime.fromisoformat(args.since), exclude)

    output = json.dumps(urls)
    print(output)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"urls={output}\n")


if __name__ == "__main__":
    main()
