---
layout: page
title: "Guide: Data Releases and Manual Refreshes"
permalink: /admin/guide/data-releases
description: "When each data source publishes, how new releases reach the site, the manual downloads, and the release calendar."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

New data reaches the site in one of three ways:

1. **Scheduled fetchers** pick up new releases by themselves. A source fetched by the daily workflow appears within a day of release. One fetched by the monthly workflow appears on the 2nd of the following month, unless you run the workflow by hand sooner (Actions, then the workflow, then "Run workflow").
2. **Manual sources** need a file downloading and a script running. The monthly "Data Refresh Reminder" issue lists them on the 2nd of each month, and this page explains each one.
3. **Analysis posts** never update themselves. Their figures, CSV and charts are frozen snapshots, so a new release only matters when you are refreshing a draft or correcting a published post. See [Analysis Posts](/admin/guide/analysis-posts), step 6.

Dates on this page were checked on 2026-10-08. "Confirmed" means the publisher has announced the day. "Usual timing" is the pattern from past releases, so check the release calendar before relying on it.

## Staying Ahead of Releases

- **Calendar file:** import `admin/data-releases.ics` into your calendar. It holds every confirmed release date below, reminders to check for expected releases, and deadlines for drafts that need fresh figures. See [The Release Calendar](#the-release-calendar).
- **GOV.UK email alerts:** on [GOV.UK research and statistics](https://www.gov.uk/search/research-and-statistics), filter by organisation (Ministry of Housing, Communities and Local Government; Department for Transport) and sign up for email updates. Upcoming releases are announced there weeks ahead.
- **ONS release calendar:** [ons.gov.uk/releasecalendar](https://www.ons.gov.uk/releasecalendar) lists confirmed dates for private rents and earnings. Each release page also offers email alerts.
- **Feeds:** subscribe in a feed reader to see announcements as they are made:
  - ONS upcoming releases: `https://www.ons.gov.uk/releasecalendar?rss&release-type=type-upcoming`. Add `&keywords=private%20rents` (or another phrase) to follow one series.
  - GOV.UK upcoming statistics from all departments: `https://www.gov.uk/search/research-and-statistics.atom?content_store_document_type=upcoming_statistics`.
  - The same, MHCLG only (housing supply, dwelling stock): add `&organisations%5B%5D=ministry-of-housing-communities-local-government`. Use `department-for-transport` for road casualties.
  - When a provisional month becomes a confirmed day, the announcement page changes. For the housing figures, watch [Housing supply: net additional dwellings, England: 2025 to 2026](https://www.gov.uk/government/statistics/announcements/housing-supply-net-additional-dwellings-england-2025-to-2026).
- **NHS England statistics calendar:** the [12-month calendar](https://www.england.nhs.uk/statistics/12-months-statistics-calendar/) gives the A&E dates a year ahead. Bookmark that page rather than its PDF, which is replaced when it is updated.

## Scheduled Sources

These update themselves. The "Feeds" column lists the analysis posts that would need a deliberate refresh.

| Source | Script and workflow | When it publishes | Next known release | Feeds |
| --- | --- | --- | --- | --- |
| NHS England A&E attendances | `nhs-ae.py`, daily | Monthly, usually the second Thursday at 09:30, for the month before | 2026-11-12 (confirmed) | `/cheltenham-ae-waiting-times`; A&E analysis |
| ONS Price Index of Private Rents | `rents.py`, monthly | Monthly, usually the third Wednesday at 09:30 | 2026-10-21 and 2026-11-18 (confirmed) | `/cheltenham-rent-prices`; housing squeeze analysis |
| ONS Annual Survey of Hours and Earnings | `earnings.py` and `affordability.py`, monthly | Once a year, in October or November | 2026-10-22 at 09:30 (confirmed) | `/cheltenham-earnings-history`, `/cheltenham-house-prices/affordability`; affordability and housing squeeze analyses |
| MHCLG net additional dwellings | `housing-supply.py`, monthly | Once a year, in November | November 2026 (expected, day not yet announced) | `/cheltenham-house-prices/housing-supply`; housing squeeze analysis |
| HM Land Registry Price Paid Data | `land_registry.py`, every two hours | Monthly. Recent months keep growing as late sales are registered | No fixed date | House price pages, `/cheltenham-house-prices/affordability`; affordability analysis |
| Care Quality Commission ratings | `cqc.py`, monthly | Updated continuously as inspections are published | No fixed date | `/cheltenham-care-homes`; care homes analysis |
| Food Standards Agency hygiene ratings | `food-standards.py`, every two hours | Updated continuously as councils publish inspections | No fixed date | `/cheltenham-food-standards`; food hygiene analysis |
| English Indices of Deprivation | `deprivation.py`, by hand | Every four to six years. The 2025 edition is current | Next edition not announced | `/cheltenham-deprivation`, `/cheltenham-wards`; deprivation and turnout analyses |

Because the monthly workflow runs on the 2nd, a release later in the month waits up to a few weeks. Run the monthly workflow by hand after a release that an upcoming post depends on. The housing figures due in November are an example: the workflow would not fetch them until 2 December, after the housing squeeze post.

## Manual Sources

These are the items on the monthly reminder issue. Each downloaded file goes in the gitignored `_data-sources/` folder before you run its script from `_python/local/`.

### Schools (Get Information About Schools)

- **Download:** the latest extract from the [GIAS downloads page](https://get-information-schools.service.gov.uk/Downloads), saved as `_data-sources/edubasealldata.csv`.
- **Run:** `process-schools-data.py`.
- **When it publishes:** GIAS is updated continuously, so the monthly download is enough.
- **Feeds:** the schools and catchment area pages.

### Ofcom Connected Nations (Mobile and Fixed Broadband)

- **Download:** the mobile coverage CSV and the fixed broadband postcode coverage CSV from the [Connected Nations hub](https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/connected-nations-and-infrastructure-reports).
- **Run:** `process-mobile-coverage.py` for mobile, and `process-wardband.py` for fixed broadband by ward, then `process-wards.py` so each ward page picks up the new broadband figures. Update the filename constants at the top of `process-mobile-coverage.py` and `process-wardband.py` first (both currently January 2026 files).
- **When it publishes:** twice a year. A spring update usually in early May (13 May 2026, with January 2026 data) and the full annual report in late autumn (19 November 2025). Neither 2026–27 date is confirmed.
- **Feeds:** the broadband and mobile coverage pages, and the broadband figures on each ward page.

### Ward Boundaries

- **Download:** the newest "Wards Boundaries UK BGC" GeoJSON from the [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/), saved as `_data-sources/wards.geojson`.
- **Run:** `process-wardband.py` again, then `process-wards.py`.
- **When it publishes:** ONS publishes a May edition in late summer and a December edition early the following year. The May 2026 edition came out in August 2026.
- **Note:** `process-wardband.py` describes its input as the May 2024 boundaries. Check whether any Cheltenham ward has changed since, and if not, there is nothing to do.
- **Feeds:** the ward broadband figures and the broadband ward map.

### Election Results

- **Download:** only after a general election. The by-candidate CSV for the new election from the House of Commons Library's [elections data](https://commonslibrary.parliament.uk/tag/elections-data/).
- **Run:** `_python/politics.py` first, because it supplies the electorate. Then update `process-election-results.py` to read the new file and run it.
- **When it publishes:** a few weeks after a general election. Skip this item otherwise.
- **Feeds:** the party history page.

### Flood Zones

- **Download:** nothing. The script fetches the Environment Agency's latest Flood Zone 2 and 3 outlines itself.
- **Run:** `process-flood-zones.py`, then commit `_data/flood-zones.json`.
- **When it publishes:** as needed, with no fixed schedule. Only run it if the [dataset page](https://environment.data.gov.uk/dataset/04532375-a198-476e-985e-0579a0a11b47) shows a newer release.
- **Feeds:** the flood zones page.

### Road Collisions (DfT STATS19)

- **Download:** the "last 5 years" collision, casualty and vehicle CSVs from the [DfT road safety data](https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-safety-data). Update the three filename constants at the top of `process-road-collisions.py` if the names change.
- **Run:** `process-road-collisions.py`, then commit `_data/road-collisions.json`.
- **When it publishes:** once a year. Final results for 2025 came out on 30 July 2026. Final results for 2026 are announced for July 2027 (provisional), with provisional figures in May 2027. Use the final results.
- **Feeds:** `/cheltenham-road-collisions`; road casualties analysis.

### Wildfire History (MHCLG Outdoor Fires Dataset)

- **Download:** every "Outdoor fires dataset" `.ods` file from the [fire statistics incident level datasets](https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets) into `_data-sources/outdoor-fires/`, replacing the old files. The script reads every `.ods` file in that folder. It also needs `_data-sources/gloucestershire-postcodes.csv` and fetches LSOA centroids from the ONS itself.
- **Run:** `process-wildfire-incidents.py` (about a minute), then commit `_data/wildfire-incidents.json`.
- **When it publishes:** once a year in late July (22 July in 2026), covering fires to the end of the previous March. The newest year can arrive with no LSOA for Gloucestershire; the page then shows the county total for that year only, and the next release usually fills it in.
- **Feeds:** `/cheltenham-wildfire-risk/history`. The live fire severity level comes from `wildfire.py` in the daily workflow and needs no manual step.

## Analysis Posts and Their Sources

| Post | Depends on | Refresh needed |
| --- | --- | --- |
| Home affordability (published 2026-09-22) | Land Registry, ASHE | Refreshed 2026-10-08. Late registrations keep moving the latest year, so check again when 2026 is added |
| Food hygiene (published 2026-10-06) | Food Standards Agency | None planned |
| Two Cheltenhams (draft, 2026-10-13) | Indices of Deprivation, Land Registry | None |
| Road casualties (draft, 2026-10-20) | DfT STATS19 | None |
| Turnout (draft, 2026-10-27) | Council election results, Indices of Deprivation | None |
| Care homes (draft, 2026-11-03) | CQC | None |
| A&E (draft, 2026-11-12 11:30) | NHS England A&E | **Yes, on release day.** Rebuild with the October figures after the 09:30 release, then publish |
| Housing squeeze (draft, provisionally 2026-11-26) | Net additional dwellings, ONS rents, ASHE | **Yes, on release day.** Publish the day the new housing figures come out (expected late November; re-date the draft once GOV.UK confirms it), with 2026 pay (22 October) added beforehand |

## The Release Calendar

The dated events live in `admin/data-releases.json`, one entry per release or reminder, each with a `status`:

- `confirmed`: the publisher has announced the day and time.
- `expected`: usual timing only. The calendar shows it as an all-day "[Expected]" reminder to check the release calendar.
- `deadline`: a draft that needs refreshing before it publishes.

To change the calendar, edit the JSON, then rebuild the file and import it again:

```bash
python _python/local/release-calendar.py
```

Every event keeps a stable ID made from its date and title, so importing again updates existing events rather than duplicating them. Before changing an event's date or title, for example when a housing release day is confirmed, give it an `id` field with its current ID (`YYYYMMDD-title-in-lowercase-with-hyphens`), so it moves rather than being copied. When an expected date is confirmed, change its `status` to `confirmed` and add the `time`. NHS England's current plan runs to the March 2027 release, so add the next A&E dates when the calendar is extended.

The calendar sits in `admin/`, so it is only on your machine and in the repository, never on the published site.

## Keeping This Page Current

- When a new page uses a new source, add it to Scheduled Sources or Manual Sources here.
- When a source becomes manual, also add it to the reminder text in `.github/workflows/data-refresh-reminder.yml`.
- When an analysis post is drafted, add it to Analysis Posts and Their Sources, and add a `deadline` event to the calendar if it needs fresh figures.
