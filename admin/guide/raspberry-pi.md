---
layout: page
title: "Guide: The Raspberry Pi"
permalink: /admin/guide/raspberry-pi
description: "How the Raspberry Pi runs the site's most frequent checks, what it needs, and what to do when it is down."
robots: noindex
render_with_liquid: false
---

[&larr; Site guide contents](/admin/guide)

The feeds that go stale within minutes (bus disruptions, power cuts, train times, unplanned road closures, weather warnings and fuel prices) are fetched by a Raspberry Pi at home rather than by GitHub Actions. Scheduled Actions can run late by up to an hour and use up the free minutes, while the Pi runs on time for the cost of its electricity. This is a stop-gap until the site earns enough to move these checks to Cloudflare Workers.

## What It Runs

The scripts live in `_python/pi/`. Each writes its `_data` file (and Atom feed, where it has one) exactly as the GitHub-run fetchers do:

| Script | Writes | Source |
| --- | --- | --- |
| `buses.py` | `_data/bus-disruptions.json`, `_data/bus-disruptions-history.json`, `_data/bus-routes.json`, `feeds/bus-disruptions.xml` | Bus Open Data Service |
| `power.py` | `_data/power-cuts.json`, `_data/power-cuts-history.json`, `feeds/power-cuts.xml` | National Grid Electricity Distribution |
| `rail-times.py` | `_data/rail-times.json`, `_data/rail-disruptions-history.json`, `feeds/rail-disruptions.xml` | National Rail Live Departure Board (Rail Data Marketplace) |
| `unplanned-closures.py` | `_data/unplanned-closures.json`, `_data/unplanned-closures-history.json`, `feeds/unplanned-closures.xml` | National Highways Road and Lane Closures |
| `weather-warnings.py` | `_data/weather-warnings.json`, `_data/weather-warnings-history.json`, `feeds/weather-warnings.xml` | Met Office warnings RSS feed (South West England) |
| `fuel.py` | `_data/fuel-prices.json`, `_data/fuel-prices-history.json`, `_data/fuel-stations.json` | GOV.UK fuel price scheme |

## How It Runs

`_python/run.sh` is the Pi's entry point. Cron calls it with a manifest name:

```bash
_python/run.sh every-5-minutes
```

A manifest is a list of scripts in `_python/pi/`: `every-5-minutes.txt` and `hourly.txt`, one path per line. `run.sh` also still takes script paths (`_python/run.sh _python/pi/power.py`), and `_python/run.sh --list every-5-minutes` prints a manifest's scripts without running anything.

For each call it:

1. changes to the repository folder and activates its `.venv`
2. runs `git pull --rebase` so it starts from the latest `main`
3. reads the manifest and runs each script, logging a warning and carrying on if one fails
4. commits any changes, including new files, as `Automated data update <UTC time> [<scripts>]` and pushes to `main`, which triggers the Pages deploy

The manifest is read after the pull, so a script added to it runs from the next run. `run.sh` is safe to change too: its body sits in one function called on its last line, so Bash has read the whole file before the pull can replace it.

## Adding a Script

1. Put the script in `_python/pi/`.
2. Add its path to `every-5-minutes.txt` or `hourly.txt`. `_python/tests/test_pi_manifests.py` fails if a script in `_python/pi/` is in neither, or in both.
3. If it needs a new API key, add it to the Pi's `.env` and as a repository secret, and pass it to the fallback workflow's `env:`.

Nothing on the Pi needs changing: the next run pulls the new list.

## Schedule

The Pi's crontab (`crontab -e` as the Pi's user) runs two jobs:

```text
*/5 * * * *  /usr/bin/flock -n /tmp/chelt-od.lock $HOME/uk.cheltenham-od/_python/run.sh every-5-minutes >> $HOME/uk.cheltenham-od/run.log 2>&1
3 * * * *    /usr/bin/flock -w 300 /tmp/chelt-od.lock $HOME/uk.cheltenham-od/_python/run.sh hourly >> $HOME/uk.cheltenham-od/run.log 2>&1
```

- The scripts in `every-5-minutes.txt` run every 5 minutes. They only commit when something has changed, so the history shows a commit every half hour or so rather than every 5 minutes.
- The scripts in `hourly.txt` (fuel prices) run once an hour, at 3 minutes past.
- Both jobs share one lockfile through `flock`, so two runs never pull, commit or push at the same time. A 5-minute run skips if the lock is busy (`-n`); the hourly run waits up to 5 minutes for it (`-w 300`).
- Output from both is appended to `run.log` in the repository folder, which is gitignored.

## Setup

The Pi needs:

- a clone of the repository at `~/uk.cheltenham-od`, with push access to `main`
- a Python virtual environment at `~/uk.cheltenham-od/.venv` with `_python/requirements.txt` installed
- a `.env` file in the repository root (gitignored) holding the API keys the scripts read:
  - `FUEL_KEY` and `FUEL_TOKEN` for `fuel.py`
  - `NAT_HIGH_KEY` for `unplanned-closures.py`
  - `RDM_LDBWS_KEY` for `rail-times.py`

## Cloudflare Watchdog and Scheduler

A Cloudflare Worker (`cloudflare/pi-watchdog/`) does two jobs:

- **Pi watchdog.** After each run where at least one script worked, `run.sh` posts to the Worker's `/heartbeat`. Every 5 minutes (at 2 minutes past each Pi run) the Worker checks the last heartbeat. If it is more than 12 minutes old, it starts **Refresh Every 5 Minutes (Pi Fallback)** through `workflow_dispatch`, and keeps doing so every 5 minutes. The first heartbeat after that stops it. It never starts the fallback before the Pi has sent its first heartbeat.
- **Scheduler.** GitHub's `schedule:` trigger was running hours late, so the site's scheduled workflows have no schedule of their own. The Worker starts each one at its set time (UTC). The times are in `src/schedules.js` and `wrangler.toml`, which must match; a test checks. Write days of the week as names (`MON`, `FRI`): Cloudflare counts 1 = Sunday, not 0.

The fuel prices API refuses GitHub's servers, so fuel prices don't update while the fallback is running. The other scripts do.

### Status and Switching

`https://pi-watchdog.<your-subdomain>.workers.dev/status` shows the mode, when the Pi last checked in, whether the fallback is on, and when each scheduled workflow last started.

The mode is `auto` (the default: follow the heartbeat), `pi` (never start the fallback) or `cloud` (always start it). To change it, from a phone (an iOS Shortcut works) or a terminal:

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "https://pi-watchdog.<your-subdomain>.workers.dev/mode?mode=cloud"
```

You can also edit the `mode` key in the Worker's KV namespace in the Cloudflare dashboard. The fallback workflow can still be started by hand from the Actions tab if the Worker is ever down.

### Watchdog Setup

1. Create a fine-grained GitHub token: only `thechelsuk/uk.cheltenham-od`, Repository permissions **Actions: Read and write**.
2. In `cloudflare/pi-watchdog/`: `npx wrangler login`, then `npx wrangler kv namespace create PI_WATCHDOG` and paste the ID into `wrangler.toml`.
3. Add the secrets: `npx wrangler secret put GITHUB_TOKEN`, `npx wrangler secret put HEARTBEAT_TOKEN` and `npx wrangler secret put ADMIN_TOKEN` (make each of the last two with `openssl rand -hex 32`).
4. `npx wrangler deploy`.
5. On the Pi, add `WATCHDOG_URL=https://pi-watchdog.<your-subdomain>.workers.dev` and `WATCHDOG_TOKEN=<the HEARTBEAT_TOKEN value>` to `.env`.

Deploy the Worker before the workflow changes reach `main`, or the scheduled workflows stop running. To change a schedule, edit both files, run `npm test`, and redeploy.
