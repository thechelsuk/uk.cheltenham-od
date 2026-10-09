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

- **Simple list + map**: `_python/post-office.py` → `_data/post-offices.json` → `_layouts/post-offices.html` → `assets/scripts/po-map.js`
- **Sibling pages sharing one dataset, different filters**: `_python/schools.py` → `_data/schools.json`, rendered by `_layouts/schools.html` (`/cheltenham-schools`) and `_layouts/school-catchment-areas.html` (`/cheltenham-schools/catchment-areas/secondary` and `/primary`)
- **One layout, parameterised by front matter**: `_layouts/school-catchment-areas.html` — same layout, same script, driven by `page.phase`, `page.max_miles` etc. so two pages don't duplicate markup
- **Custom map computation (Voronoi)**: `assets/scripts/school-catchment-map.js`
- **Hand-curated dataset (no fetcher)**: `_data/third-spaces.json`, `_data/parkrun.json`'s sibling pattern but fetched — see [Fetching Data](/admin/guide/fetching-data) for when to curate instead of fetch

The detail for each step is on [Fetching Data](/admin/guide/fetching-data) and [Displaying Data](/admin/guide/displaying-data).

## Checklist

- [ ] `_python/<name>.py` fetches and normalises, writes `_data/<name>.json` with `generated_at`/`source`/`source_url`/`licence`
- [ ] Added to the right `schedule-*.yml` workflow for how often the source actually changes
- [ ] `_pages/<name>.md` (or `_pages/<group>/<name>.md`) with full front matter and real intro prose, not just a data dump — reread every sentence as a visitor would: no implementation/data-decision notes ("hand-curated because OSM coverage is patchy") leaking into published copy
- [ ] `seo:` is 160 characters or fewer on the page and on any announcement post (the admin page flags any over the limit)
- [ ] `_layouts/<name>.html` — map + table + attribution line, reusing an existing layout via front matter variables if it's a filtered sibling of another page. The attribution goes directly under the last table or map and before the FAQs: `Data from SOURCE, published under the LICENCE.` then `Last updated DATE.` or `Checked REFRESH.`, then any required notices (such as "Contains OS data © Crown copyright") and caveats. Pages with several sources name each one in the same sentence.
- [ ] Every numeric table column has `class="number"` on its `<th>` and `<td>`s (right-aligned), and any postcode column has `class="postcode"` (no mid-postcode wrapping)
- [ ] Every date/time cell in a table and every date in a map popup is `YYYY-MM-DD HH:MM` (or `YYYY-MM-DD` with no time), with the ISO value in `data-val` and `class="date"` on the `<th>`/`<td>`s
- [ ] `assets/scripts/<name>-map.js` if there's a map, following the standard IIFE shape
- [ ] Linked from the relevant parent/sibling pages. If the page is in `navigation_header`, its category overview page (`_pages/<category>/<category>.md`, e.g. `_pages/getting-around/getting-around.md`) must mention and link it in the prose too, along with any child pages — every page in the category should appear there. The list of links under the prose is generated from the nav and updates itself, but the prose (and the page's `seo`/`description` text) is hand-written and won't.
- [ ] Decided whether this is a headline main-menu item or a sub-page of an existing one — if it's a genuine new topic, add it to `navigation_header`/`footer_columns` in `_config.yml`; if it's a filtered view or a natural sub-topic of an existing page (like `/cheltenham-employment-history` under `/about-cheltenham`, or `/cheltenham-listed-buildings` under `/about-cheltenham`), link it inline from the parent page's prose instead and leave the nav/footer alone
- [ ] If the page went into `navigation_header`, **asked** whether to add it to its category's row in the sponsor categories table (`_layouts/sponsor.html`, the `/sponsor` page) — don't edit that table without an answer, since it's sales copy the site owner words themselves. The **Pages** count in that table is calculated from `navigation_header`, so it updates itself; the **Pages included** text is hardcoded per row, is kept deliberately loose (short names, only some sub-pages in an `(incl. …)` note) and will not change on its own, so it goes stale unless the question is asked. If the answer is yes, add the page's short name in nav order (e.g. `Roadworks`); for a child of an existing entry, only add it to that entry's `(incl. …)` note if it's worth a sponsor knowing about. A page linked inline from a parent (no nav entry) doesn't need the question.
- [ ] `schema:` + `_includes/schema/<name>.html` if the page has a real dataset worth marking up, and FAQs written in the standard shape (their `FAQPage` markup is generated for you)
- [ ] Checked `_data/sources.json` — add or update the entry for this source, being honest about the licence, with a short `licence_type` (such as "OGL v3.0", "ODbL" or "None stated") and its `data` files, each with its `schedule` (`every 5 minutes`, `hourly`, `every two hours`, `daily`, `weekly`, `monthly` or `manual`). The studio app's Data Freshness tab (uk.cheltenham-od.studio) reads these to flag data that has stopped updating, and `_python/tests/test_sources_registry.py` fails if a data file isn't listed
- [ ] Ask whether a `_posts/<date>-<name>-added.md` news post announcing the new page is warranted — follow the shape of recent posts like `_posts/2026-09-09-broadband-internet-added.md` (intro paragraph linking the new page, a short "what it shows" summary, an FAQs section). Not every page needs one (a minor filter/sub-page usually doesn't), but a genuinely new dataset or page usually does. Two things to know about posts: `future: false` in `_config.yml` hides any post dated later than the build time until the first site build after it, so date it in the past to publish straight away, or in the future to schedule it (it appears on the next deploy after that time); and the post's URL (`/news/<name>-added`) comes from its filename, not its title, so the title can be as descriptive as you like.
- [ ] If you changed a style sheet (`assets/*.css`), checked it with the CSS linters as CI runs them. Super-linter 7.1.0 bundles Prettier 3.3.3 and stylelint 15.11, and newer Prettier releases wrap long `font-family` and custom property values differently, so a file that passes with a newer version can still fail in CI. Keep such values short enough to sit on one line, and check with the same versions. CI's Prettier finds its settings (4-space indents) through the `.prettierrc.json` at the repository root, not the copy in `.github/linters/`, so run it without `--config`:
  - `npx prettier@3.3.3 --check assets/*.css`
  - `npm i --prefix /tmp/stylelint stylelint@15.11.0 stylelint-config-standard@34 && /tmp/stylelint/node_modules/.bin/stylelint --config .github/linters/.stylelintrc.json --config-basedir /tmp/stylelint "assets/*.css"` (stylelint needs `--config-basedir` to find `stylelint-config-standard`; `npx -p` cannot resolve it)
