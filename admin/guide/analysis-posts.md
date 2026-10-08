---
layout: page
title: "Guide: Analysis Posts"
permalink: /admin/guide/analysis-posts
description: "How to write a finding-led analysis post with a quotable line, chart, CSV, cite box and Dataset schema."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

An analysis post leads with one finding from the site's own data, framed so a journalist, campaigner or council officer can quote it and link to it. It uses `layout: analysis`, which adds:

- the finding in a quote box at the top, with its source
- the chart, with SVG and PNG downloads, the CSV, and a link to the live data page
- the byline from the post's `author` (a front-matter default for every post in `_config.yml`)
- Dataset and BlogPosting structured data, and the chart as the post's social sharing image
- an "Analysis" pill in the news list, and an entry in the press pack's Latest Findings once published

Worked examples: `_posts/2026-09-22-home-affordability-analysis.md` and `_posts/2026-10-06-food-hygiene-ratings-breakdown.md`.

## 1. Find and Check the Finding

Work from the `_data` files the site already has, not live API calls. Before writing anything, test whether the headline survives:

- **Start year:** if a "rose faster than" claim flips when the start year moves by one or two years, lead with a period that holds, and say in the caveats that the start year matters.
- **Season:** compare the same month in each year. January against August flatters anything seasonal, such as A&E waits.
- **Groups:** check the named examples really sit where the claim puts them. A "wealthiest ward" must actually rank among the least deprived.
- **Weighting:** know whether a figure is a share of people or premises, or an average of areas.
- **Causes:** say what the data shows, not why, unless a source says why.
- **Primary sources:** confirm any outside figure, such as a national target, against the publisher, not a secondary report.

Record every figure, its `_data` file and field, and whether it matched, in a fact-check note alongside the draft. `_notes/findings-fact-check.md` is the model. `_notes/` is never built.

## 2. Build the Chart and Data

Charts come from `_python/local/build-findings.py`. Each chart has a small builder function that reads `_data`, writes the CSV with `write_csv()` and draws with the shared helpers:

- `hbars()`: horizontal bars, one per row, for rankings by category
- `vbars()`: vertical bars, optionally stacked, for counts by year or band
- `line()`: a single-series line with value labels at chosen points
- `legend()`: a one-row legend, needed whenever two colours carry meaning
- `frame()`: adds the title, subtitle and source line, and saves the SVG, PNG and social card

Mark the series the finding is about with the `s1` class and everything else with `mute`. Use `s2` for a comparison group: it is hatched as well as coloured, so the chart never relies on colour alone. Add the function to the `BUILDERS` list at the bottom of the script, keyed by the chart's slug, then build it:

```bash
python _python/local/build-findings.py --list
python _python/local/build-findings.py <slug>
```

This writes `assets/findings/<slug>.csv`, `.svg`, `.png` (2x, for newsroom systems that will not take SVG) and `<slug>-social.png` (1200 x 630). PNGs need `rsvg-convert` (`brew install librsvg`). Open the PNG and check for overlapping labels before going on.

Charts are frozen snapshots that match their post's text, so the script never replaces an existing chart unless you add `--force`. Only use `--force` when you are refreshing the post's figures at the same time (see step 6).

## 3. Write the Post

Create the draft as `_drafts/YYYY-MM-DD-<slug>.md`. `_drafts/` is not committed, so keep the fact-check note in `_notes/` if it needs to survive. Copy this template:

```markdown
---
layout: analysis
title: Headline Stating the Finding, in AP Title Case
seo_title: "Shorter Title for Search Results, About 55 Characters"
type: cod
description: What the analysis covers, as context. Do not repeat the finding here.
seo: "160 characters or fewer, leading with the finding and its key number."
date: 2026-11-17 08:30
finding:
    quote: "The single quotable sentence, with its number."
    source: Publisher and dataset name
    licence: Open Government Licence v3.0
    licence_url: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/
    data: <chart-slug>
    page: /the-live-data-page
    chart_alt: "What the chart shows, with its key values, for screen readers."
    dataset_name: Dataset Name for Search Engines
    dataset_description: One sentence on what the CSV contains and where it comes from.
    temporal: 2021/2025
    variables:
        - Each column the CSV measures
---

Cheltenham Open Data analysed ... Context and the next most important figures,
not the quote again, ending with a link to the live data page.

## Key Figures

- **Number:** what it means.

## A Section Heading per Angle

Prose explaining the finding and what sits behind it.

## Notes to Editors

- **Method:** how the figures were calculated.
- **Sources:** each publisher and dataset.
- **Caveats:** what the figures do not show, and anything sensitive to the choice of years.
- **Data and updates:** how often the live page refreshes. For questions or interviews, use the [contact page](/contact).

Data from SOURCE, published under the LICENCE. Last updated YYYY-MM-DD.

{% include cite-this.html %}

## FAQs

### A Question People Search For?

- The answer.

### Can I Use This Chart?

- Yes. Credit Cheltenham Open Data and link to this page. The embed code and a CSV of the figures are in the Cite This section above.
```

Rules that apply to every analysis post:

- **Say the finding once.** It goes in `finding.quote`. The header `description` gives context, and the opening paragraph moves on to supporting figures.
- **Headings** use AP title case: short prepositions such as "of", "from" and "to" stay lowercase.
- **Dates** in figures and tables are `YYYY-MM-DD`.
- **`seo`** is 160 characters or fewer.
- **Copy** is for readers: no notes about how the data was processed for the site.

For a second chart in the body, build it as its own slug, place it with `{% include finding-figure.html slug="<slug>" alt="..." page="/live-page" %}`, and list the slug under `finding.extra_data` so its CSV is in the Dataset schema. `_drafts/2026-11-26-cheltenham-housing-squeeze.md` is an example.

## 4. Check It

- Lint the post as CI does: `npx markdownlint-cli -c .github/linters/.markdown-lint.yml <file>` and `npx -p textlint -p textlint-rule-terminology textlint --rule terminology <file>`.
- Preview with `bundle exec jekyll serve --drafts --future`, and read the post at desktop and phone widths.
- Check every number in the post against the fact-check note one last time.

## 5. Publish

Move the file from `_drafts/` to `_posts/` and commit it with its `assets/findings/` files. For a post that goes out on a release day, keep it in `_drafts/` until its figures are refreshed: set its date to about two hours after the release (11:30 for a 09:30 release), then move it once the chart and text are updated. A post whose date has already passed publishes on the next deploy, so it can never go out early this way. The date in the filename and front matter decides when it goes live: with `future: false`, it appears on the first deploy after that time, and is then posted to social automatically. Ask before scheduling a post, because it will go out without a further check.

The press pack's Latest Findings section lists any published post with a `finding:` block, so there is nothing to add there.

Commit the chart files with the post rather than before it. Anything in `assets/findings/` is public from the next deploy, even if the post is still a draft.

## 6. Refresh or Correct a Published Post

If the data moves after publication, for example late Land Registry registrations or a revised NHS month, refresh the post. [Data Releases and Manual Refreshes](/admin/guide/data-releases) lists when each source publishes and which posts depend on it. To refresh:

1. Rebuild the chart with `--force`.
2. Update every affected figure in the post to match the new CSV.
3. Set `last_modified_at`, so the byline shows "Updated".
4. Add a `corrections:` entry saying what changed. The Cite This box promises one:

```yaml
last_modified_at: 2026-10-08 12:00
corrections:
    - date: 2026-10-08
      note: What changed, with the old and new figures.
```

A refresh that leaves every figure the same needs only `last_modified_at`.
