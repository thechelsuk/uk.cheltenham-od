---
layout: page
title: "Guide: The Raspberry Pi"
permalink: /admin/guide/raspberry-pi
description: "How the Raspberry Pi runs the site's most frequent checks, what it needs, and what to do when it is down."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

The feeds that go stale within minutes (bus disruptions, power cuts, train times, unplanned road closures and fuel prices) are fetched by a Raspberry Pi at home rather than by GitHub Actions. Scheduled Actions can run late by up to an hour and use up the free minutes, while the Pi runs on time for the cost of its electricity. This is a stop-gap until the site earns enough to move these checks to Cloudflare Workers.

## What It Runs

The scripts live in `_python/pi/`. Each writes its `_data` file (and Atom feed, where it has one) exactly as the GitHub-run fetchers do:

| Script | Writes | Source |
| --- | --- | --- |
| `buses.py` | `_data/bus-disruptions.json`, `_data/bus-disruptions-history.json`, `_data/bus-routes.json`, `feeds/bus-disruptions.xml` | Bus Open Data Service |
| `power.py` | `_data/power-cuts.json`, `_data/power-cuts-history.json`, `feeds/power-cuts.xml` | National Grid Electricity Distribution |
| `rail-times.py` | `_data/rail-times.json`, `_data/rail-disruptions-history.json`, `feeds/rail-disruptions.xml` | National Rail Live Departure Board (Rail Data Marketplace) |
| `unplanned-closures.py` | `_data/unplanned-closures.json`, `_data/unplanned-closures-history.json`, `feeds/unplanned-closures.xml` | National Highways Road and Lane Closures |
| `fuel.py` | `_data/fuel-prices.json`, `_data/fuel-prices-history.json`, `_data/fuel-stations.json` | GOV.UK fuel price scheme |

## How It Runs

`_python/run.sh` is the Pi's entry point. Cron calls it with one or more scripts:

```bash
_python/run.sh _python/pi/buses.py _python/pi/power.py _python/pi/rail-times.py _python/pi/unplanned-closures.py
```

For each call it:

1. changes to `~/uk.cheltenham-od` and activates its `.venv`
2. runs `git pull --rebase` so it starts from the latest `main`
3. runs each script, logging a warning and carrying on if one fails
4. commits any changes as `Automated data update <UTC time> [<scripts>]` and pushes to `main`, which triggers the Pages deploy

## Schedule

The Pi's crontab (`crontab -e` as the Pi's user) runs two jobs:

```text
*/5 * * * *  /usr/bin/flock -n /tmp/chelt-od.lock $HOME/uk.cheltenham-od/_python/run.sh _python/pi/buses.py _python/pi/power.py _python/pi/rail-times.py _python/pi/unplanned-closures.py >> $HOME/uk.cheltenham-od/run.log 2>&1
3 * * * *    /usr/bin/flock -w 300 /tmp/chelt-od.lock $HOME/uk.cheltenham-od/_python/run.sh _python/pi/fuel.py >> $HOME/uk.cheltenham-od/run.log 2>&1
```

- The four fast feeds run every 5 minutes. They only commit when something has changed, so the history shows a commit every half hour or so rather than every 5 minutes.
- Fuel prices run once an hour, at 3 minutes past.
- Both jobs share one lockfile through `flock`, so two runs never pull, commit or push at the same time. A 5-minute run skips if the lock is busy (`-n`); the hourly fuel run waits up to 5 minutes for it (`-w 300`).
- Output from both is appended to `run.log` in the repository folder, which is gitignored.

## Setup

The Pi needs:

- a clone of the repository at `~/uk.cheltenham-od`, with push access to `main`
- a Python virtual environment at `~/uk.cheltenham-od/.venv` with `_python/requirements.txt` installed
- a `.env` file in the repository root (gitignored) holding the API keys the scripts read:
  - `FUEL_KEY` and `FUEL_TOKEN` for `fuel.py`
  - `NAT_HIGH_KEY` for `unplanned-closures.py`
  - `RDM_LDBWS_KEY` for `rail-times.py`

## When the Pi Is Down

If the Pi stops (a power cut, say), run **Refresh Every 5 Minutes (Pi Fallback)** (`.github/workflows/refresh-every-5-minutes.yml`) by hand from the Actions tab, from a phone if need be. It runs the same five scripts with the same keys, stored as repository secrets, and commits and deploys any changes. It has no schedule of its own: trigger it as often as needed, and stop once the Pi is back, as running both just makes duplicate commits.
