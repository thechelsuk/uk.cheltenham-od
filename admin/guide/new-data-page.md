---
layout: page
title: "Guide: Adding a New Data Page"
permalink: /admin/guide/new-data-page
description: "The standard shape of a data page, worked examples to copy, and the checklist from source to published page."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

This is the standard shape of a data page on Cheltenham Open Data. It's not a hard rule for every page on the site — a handful of pages are pure curated Markdown (`_pages/sports.md`, `_pages/third-spaces.md`) with no fetcher behind them — but if you're adding something backed by an external source, follow this pattern so it's consistent with the rest of the site.

Good reference examples to read alongside this guide:

- **Simple list + map**: `_python/post-office.py` → `_data/post-offices.json` → `_layouts/community-support/post-offices.html` → `assets/scripts/po-map.js`
- **Sibling pages sharing one dataset, different filters**: `_python/schools.py` → `_data/schools.json`, rendered by `_layouts/home-property/schools.html` (`/cheltenham-schools`) and `_layouts/home-property/school-catchment-areas.html` (`/cheltenham-schools/catchment-areas/secondary` and `/primary`)
- **One layout, parameterised by front matter**: `_layouts/home-property/school-catchment-areas.html` — same layout, same script, driven by `page.phase`, `page.max_miles` etc. so two pages don't duplicate markup
- **Custom map computation (Voronoi)**: `assets/scripts/school-catchment-map.js`
- **Hand-curated dataset (no fetcher)**: `_data/third-spaces.json`, `_data/parkrun.json`'s sibling pattern but fetched — see [Fetching Data](/admin/guide/fetching-data) for when to curate instead of fetch

The detail for each step is on [Fetching Data](/admin/guide/fetching-data) and [Displaying Data](/admin/guide/displaying-data).

## URLs and Where a Page Lives

- **A published URL rarely moves.** Links from search results, social posts and other sites point at it. Rename the title, move the page in the nav or change its folder as often as you like, but keep its `permalink`. If a page really must move, agree it first, then leave a page at the old address with `layout: redirect`, the old `permalink`, `redirect_to:` the new one and `robots: noindex` (as `_pages/about-info/local-elections-moved.md` does), and update every internal link.
- **A new sub-page nests under its parent's URL:** `/cheltenham-power-cuts/history`, `/cheltenham-crime-data/map`. A year archive is `/<parent>/<year>`, such as `/cheltenham-crime-data/2026`. Some older pages don't follow this (`/cheltenham-house-prices-2025`, or `/cheltenham-sewage-overflows` sitting under flood warnings in the nav); leave them where they are.
- **The page file goes in the `_pages/` folder of its nav group** (`getting-around`, `home-property`, `safety-environment`, `things-to-do`, `community-support`, `about-info`), and its `type` matches that group. A page with no menu entry of its own, such as an older year, sets `section:` to its group's name so it is still listed on the category page.

## Checklist

- [ ] `_python/<name>.py` fetches and normalises, writes `_data/<name>.json` with `generated_at`/`source`/`source_url`/`licence`
- [ ] Added to the right `refresh-*.yml` workflow for how often the source actually changes
- [ ] `_pages/<name>.md` (or `_pages/<group>/<name>.md`) with full front matter and real intro prose, not just a data dump — reread every sentence as a visitor would: no implementation/data-decision notes ("hand-curated because OSM coverage is patchy") leaking into published copy
- [ ] `seo:` is 160 characters or fewer on the page and on any announcement post (the admin page flags any over the limit)
- [ ] `_layouts/<category>/<name>.html`, in the folder for the page's menu category (the same as its `_pages/<category>/` folder) — map + table + attribution line, reusing an existing layout via front matter variables if it's a filtered sibling of another page. The page runs intro, then data and maps, then FAQs, then an `<h2 id="about-this-data">About This Data</h2>` section at the very bottom holding the attribution: `Data from SOURCE, published under the LICENCE.` then `{% include freshness.html file="_data/<name>.json" %}` (which writes "Last updated 9 September 2026, checked daily."), then any required notices (such as "Contains OS data © Crown copyright") and caveats. Pages with several sources name each one in the same sentence.
- [ ] Every numeric table column has `class="number"` on its `<th>` and `<td>`s (right-aligned), and any postcode column has `class="postcode"` (no mid-postcode wrapping)
- [ ] Every date/time cell in a table and every date in a map popup is `YYYY-MM-DD HH:MM` (or `YYYY-MM-DD` with no time), with the ISO value in `data-val` and `class="date"` on the `<th>`/`<td>`s
- [ ] `assets/scripts/<name>-map.js` if there's a map, following the standard IIFE shape
- [ ] Linked from the relevant parent/sibling pages. If the page is in the menu, its category overview page (`_pages/<category>/<category>.md`, e.g. `_pages/getting-around/getting-around.md`) must mention and link it in the prose too, along with any child pages — every page in the category should appear there. The list of links under the prose is generated from the nav and updates itself, but the prose (and the page's `seo`/`description` text) is hand-written and won't.
- [ ] Decided where the page sits, in `_data/navigation/<category>.yml` (field notes in `_plugins/navigation.rb`). A genuine new topic is a menu item under the right subgroup. A page that continues another one (a history, a year, a map view, like `/cheltenham-employment-history` under `/cheltenham-economy`) is one of that item's `children`, with `a_z: true` if it belongs in the footer's Pages (A-Z). A page that belongs in the category but continues nothing (like `/cheltenham-covid-19`) stays out of the menu: set `section:`, `subgroup:` and `nav_title:` in its front matter. The breadcrumb, the "In this section" row, the category page and the footer all follow from that, and `jekyll serve` picks up edits to these files without a restart
- [ ] If the page went into the menu, **asked** whether to add it to its category's row in the sponsor categories table (`_layouts/site/sponsor.html`, the `/sponsor` page) — don't edit that table without an answer, since it's sales copy the site owner words themselves. The **Pages** count in that table is calculated from the menu files and section pages, so it updates itself; the **Pages included** text is hardcoded per row, is kept deliberately loose (short names, only some sub-pages in an `(incl. …)` note) and will not change on its own, so it goes stale unless the question is asked. If the answer is yes, add the page's short name in nav order (e.g. `Roadworks`); for a child of an existing entry, only add it to that entry's `(incl. …)` note if it's worth a sponsor knowing about. A page linked inline from a parent (no nav entry) doesn't need the question.
- [ ] `schema:` + `_includes/schema/<name>.html` if the page has a real dataset worth marking up, and FAQs written in the standard shape (their `FAQPage` markup is generated for you)
- [ ] Checked `_data/sources.json` — add or update the entry for this source, being honest about the licence, with a short `licence_type` (such as "OGL v3.0", "ODbL" or "None stated") and its `data` files, each with its `schedule` (`every 5 minutes`, `hourly`, `every two hours`, `daily`, `weekly`, `monthly` or `manual`). The studio app's Data Freshness tab (uk.cheltenham-od.studio) reads these to flag data that has stopped updating, and `_python/tests/test_sources_registry.py` fails if a data file isn't listed
- [ ] Ask whether a `_posts/<date>-<name>-added.md` news post announcing the new page is warranted — follow the shape of recent posts like `_posts/2026-09-09-broadband-internet-added.md` (intro paragraph linking the new page, a short "what it shows" summary, an FAQs section). Not every page needs one (a minor filter/sub-page usually doesn't), but a genuinely new dataset or page usually does. Two things to know about posts: `future: false` in `_config.yml` hides any post dated later than the build time until the first site build after it, so date it in the past to publish straight away, or in the future to schedule it (it appears on the next deploy after that time); and the post's URL (`/news/<name>-added`) comes from its filename, not its title, so the title can be as descriptive as you like.
- [ ] If you changed a style sheet (`assets/*.css`), checked it with the CSS linters as CI runs them. Super-linter 7.1.0 bundles Prettier 3.3.3 and stylelint 15.11, and newer Prettier releases wrap long `font-family` and custom property values differently, so a file that passes with a newer version can still fail in CI. Keep such values short enough to sit on one line, and check with the same versions. CI's Prettier finds its settings (4-space indents) through the `.prettierrc.json` at the repository root, not the copy in `.github/linters/`, so run it without `--config`:
  - `npx prettier@3.3.3 --check assets/*.css`
  - `npm i --prefix /tmp/stylelint stylelint@15.11.0 stylelint-config-standard@34 && /tmp/stylelint/node_modules/.bin/stylelint --config .github/linters/.stylelintrc.json --config-basedir /tmp/stylelint "assets/*.css"` (stylelint needs `--config-basedir` to find `stylelint-config-standard`; `npx -p` cannot resolve it)
