---
layout: page
title: "Site Guide"
permalink: /admin/guide
description: "How Cheltenham Open Data is built: adding data pages, fetching and displaying data, analysis posts, and keeping data up to date."
robots: noindex
render_with_liquid: false
---

[&larr; Admin](/admin)

## Contents

- [Adding a New Data Page](/admin/guide/new-data-page): start here. The pattern every data page follows, worked examples, and the checklist from source to published page.
- [Fetching Data](/admin/guide/fetching-data): the Python fetcher, shared helpers, licences, freshness, schedules, and when to curate by hand.
- [Displaying Data](/admin/guide/displaying-data): the page front matter and copy, the layout, tables, dates, maps, charts, structured data and FAQs.
- [Analysis Posts](/admin/guide/analysis-posts): finding-led posts with a quotable line, chart, CSV, cite box and Dataset schema.
- [Data Releases and Manual Refreshes](/admin/guide/data-releases): when each source publishes, how it reaches the site, the manual downloads, and the release calendar.

## Previewing Locally

`_config.yml` keeps `future: false`, so scheduled posts never go live early. To preview drafts and future-dated posts locally:

```bash
bundle exec jekyll serve --drafts --future
```

These guide pages are only built locally. The published site leaves out `admin.md` and the `admin/` folder through `_config.production.yml`.
