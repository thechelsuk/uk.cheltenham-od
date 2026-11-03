---
layout: page
title: "Admin"
permalink: /admin
description: "How Cheltenham Open Data is built, the local admin tools, and working notes."
robots: noindex
render_with_liquid: false
---

## Site Guide

- [Adding a New Data Page](/admin/guide/new-data-page): start here. The pattern every data page follows, worked examples, and the checklist from source to published page.
- [Fetching Data](/admin/guide/fetching-data): the Python fetcher, shared helpers, licences, freshness, schedules, and when to curate by hand.
- [Displaying Data](/admin/guide/displaying-data): the page front matter and copy, the layout, tables, dates, maps, charts, structured data and FAQs.
- [Style Guide](/admin/guide/style-guide): the shared components and their rules: units, colours, headings, pills, tables, keys, attribution and kind markers.
- [Analysis Posts](/admin/guide/analysis-posts): finding-led posts with a quotable line, chart, CSV, cite box and Dataset schema.
- [Data Releases and Manual Refreshes](/admin/guide/data-releases): when each source publishes, how it reaches the site, the manual downloads, and the release calendar.
- [The Raspberry Pi](/admin/guide/raspberry-pi): the home server that runs the most frequent checks and starts the scheduled workflows, its setup, and the Cloudflare watchdog that takes over when it is down.

- [Outreach](/admin/guide/outreach): who to tell when an analysis post goes out. Local only.

## Tools

- [Pages and SEO](/admin/pages): every page with its type, SEO title and description, flagging any that are too long.
- [Kinds: Icons and Colours](/admin/kinds): every news, alert and classifieds kind marker, in light and dark mode.

## Working Notes

These are local only: they are listed in `.git/info/exclude`, so they never reach GitHub.

- [Site Review Checklist](/admin/review-checklist): follow-ups from the full site review and merged work.
- [Hand-Written Pages](/admin/hand-written-pages): pages written by hand, for the "Last reviewed" idea.

## Previewing Locally

`_config.yml` keeps `future: false`, so scheduled posts never go live early. To preview drafts and future-dated posts locally:

```bash
bundle exec jekyll serve --drafts --future
```

```bash
bundle exec jekyll serve --drafts --future --livereload --port 4000
```

These guide pages are only built locally. The published site leaves out `admin.md` and the `admin/` folder through `_config.production.yml`.
