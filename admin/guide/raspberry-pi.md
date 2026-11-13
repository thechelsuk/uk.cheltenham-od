---
layout: page
title: "Guide: The Raspberry Pi"
permalink: /admin/guide/raspberry-pi
description: "How the Raspberry Pi runs the site's most frequent checks, what it needs, and what to do when it is down."
robots: noindex
render_with_liquid: false
---

[&larr; Admin](/admin)

A Raspberry Pi at home does two jobs:

- It fetches the feeds that go stale within minutes (bus disruptions, power cuts, train times, unplanned road closures, weather warnings and fuel prices), and the sources that don't work from GitHub's servers (planning applications and NHS A&E figures), rather than GitHub Actions.
- It starts the site's scheduled GitHub workflows at their set times. GitHub's own `schedule:` trigger ran hours late, so no workflow has one.

The Pi runs on time for the cost of its electricity. When it goes quiet, from a power cut or a Wi-Fi drop, a Cloudflare Worker takes over both jobs until it is back (see [Cloudflare Watchdog](#cloudflare-watchdog)).

## What It Runs

The data scripts live in `_python/pi/`. Each writes its `_data` file (and Atom feed, where it has one) exactly as the GitHub-run fetchers do:

| Script | Writes | Source |
| --- | --- | --- |
| `buses.py` | `_data/bus-disruptions.json`, `_data/bus-disruptions-history.json`, `_data/bus-routes.json`, `feeds/bus-disruptions.xml` | Bus Open Data Service |
| `power.py` | `_data/power-cuts.json`, `_data/power-cuts-history.json`, `feeds/power-cuts.xml` | National Grid Electricity Distribution |
| `rail-times.py` | `_data/rail-times.json`, `_data/rail-disruptions-history.json`, `feeds/rail-disruptions.xml` | National Rail Live Departure Board (Rail Data Marketplace) |
| `unplanned-closures.py` | `_data/unplanned-closures.json`, `_data/unplanned-closures-history.json`, `feeds/unplanned-closures.xml` | National Highways Road and Lane Closures |
| `weather-warnings.py` | `_data/weather-warnings.json`, `_data/weather-warnings-history.json`, `feeds/weather-warnings.xml` | Met Office warnings RSS feed (South West England) |
| `fuel.py` | `_data/fuel-prices.json`, `_data/fuel-prices-history.json`, `_data/fuel-stations.json` | GOV.UK fuel price scheme |
| `planning.py` | `_data/planning-applications.json` | Cheltenham Borough Council planning portal (blocks GitHub's runners, so it runs here) |
| `nhs-ae.py` | `_data/nhs-ae.json` | NHS England A&E Attendances and Emergency Admissions (GitHub's runners never saw a new month on its year pages, so it runs here) |

## How It Runs

`_python/run.sh` is the Pi's entry point. Cron calls it with a manifest name:

```bash
_python/run.sh every-5-minutes
```

A manifest is a list of scripts in `_python/pi/`: `every-5-minutes.txt` and `hourly.txt`, one path per line. `run.sh` also still takes script paths (`_python/run.sh _python/pi/power.py`), and `_python/run.sh --list every-5-minutes` prints a manifest's scripts without running anything.

For each call it:

1. changes to the repository folder and activates its `.venv`
2. runs `git pull --rebase` so it starts from the latest `main`
3. reads the manifest and runs each script through `_python/fetch_status.py pi`, which records whether it worked in `_data/fetch-status/pi.json`, logging a warning and carrying on if one fails
4. commits any changes, including new files, as `Automated data update <UTC time> [<scripts>]` and pushes to `main`, which triggers the Pages deploy

The manifest is read after the pull, so a script added to it runs from the next run. `run.sh` is safe to change too: its body sits in one function called on its last line, so Bash has read the whole file before the pull can replace it.

## Adding a Script

1. Put the script in `_python/pi/`.
2. Add its path to `every-5-minutes.txt` or `hourly.txt`. `_python/tests/test_pi_manifests.py` fails if a script in `_python/pi/` is in neither, or in both.
3. If it needs a new API key, add it to the Pi's `.env` and as a repository secret, and pass it to the fallback workflow's `env:`.

Nothing on the Pi needs changing: the next run pulls the new list.

## Adding or Changing a Scheduled Workflow

1. Give the workflow a `workflow_dispatch:` trigger and no `schedule:`. The watchdog's tests fail if any workflow still has a GitHub schedule.
2. Add a line to `_python/pi/crontab.txt` that runs `$PI/pi/dispatch.sh <workflow>.yml` at its UK time, and the same schedule to `cloudflare/pi-watchdog/src/schedules.js`, so the watchdog can start it if the Pi is down. A test fails if the two lists differ.
3. Push, then reinstall the crontab on the Pi with `crontab ~/uk.cheltenham-od/_python/pi/crontab.txt`. Unlike the script lists, the crontab isn't read on each pull.

## Schedule

The Pi's crontab is kept in the repository as `_python/pi/crontab.txt`. Install it, or update it after a change, with:

```bash
crontab ~/uk.cheltenham-od/_python/pi/crontab.txt
```

It does two things:

- **Data scripts.** The scripts in `every-5-minutes.txt` run every 5 minutes, and those in `hourly.txt` (fuel prices, planning applications and NHS A&E figures) at 3 minutes past each hour. They only commit when something has changed. Both share one lockfile through `flock`, so two runs never pull, commit or push at the same time: a 5-minute run skips if the lock is busy (`-n`), and the hourly run waits up to 5 minutes for it (`-w 300`).
- **Scheduled workflows.** GitHub's own `schedule:` trigger was running hours late, so the site's scheduled workflows have none. The Pi starts each one at its set time with `_python/pi/dispatch.sh <workflow>`, which calls GitHub's `workflow_dispatch`.

All times are UK time. The Pi's clock is on `Europe/London`, and the watchdog reads its copy of the schedules in UK time too, so a workflow set for 08:46 runs at 08:46 UK time all year. Output goes to `run.log` in the repository folder, which is gitignored.

To change a schedule, edit `crontab.txt` and the matching line in `cloudflare/pi-watchdog/src/schedules.js` (the watchdog's test fails if they differ), push, and reinstall the crontab on the Pi.

## Setup

The Pi needs:

- a clone of the repository at `~/uk.cheltenham-od`, with push access to `main`
- a Python virtual environment at `~/uk.cheltenham-od/.venv` with `_python/requirements.txt` installed
- a `.env` file in the repository root (gitignored) holding the API keys the scripts read:
  - `FUEL_KEY` and `FUEL_TOKEN` for `fuel.py`
  - `NAT_HIGH_KEY` for `unplanned-closures.py`
  - `RDM_LDBWS_KEY` for `rail-times.py`
  - `GITHUB_DISPATCH_TOKEN`: a fine-grained GitHub token for this repository only, with **Actions: Read and write**, for `dispatch.sh`.
  - `WATCHDOG_URL` and `WATCHDOG_TOKEN`: see Cloudflare Watchdog below.

### Keeping the Wi-Fi Up

The Pi can only reach the router over Wi-Fi, and a dropped connection may not come back by itself until the Pi restarts. Two settings guard against that.

Wi-Fi power saving should be off. Check with:

```bash
iw wlan0 get power_save
```

If it says `on`, find the connection's name with `nmcli -t -f NAME,TYPE connection show --active`, then turn it off with `sudo nmcli connection modify "<name>" 802-11-wireless.powersave 2`. It takes effect when the Wi-Fi next reconnects.

Root's crontab restarts the Wi-Fi whenever the Pi can't reach the internet. It runs every 5 minutes, so a dropped connection is back within about 5 minutes. Install it (this replaces root's crontab, which is otherwise empty) with:

```bash
echo '*/5 * * * *  ping -c 3 -W 5 1.1.1.1 > /dev/null 2>&1 || { logger "wifi-recover: restarting Wi-Fi"; nmcli radio wifi off; sleep 5; nmcli radio wifi on; }' | sudo crontab -
```

Check it with `sudo crontab -l`. Each restart is noted in the system log, which `journalctl -t wifi-recover` lists. During a broadband outage it restarts the Wi-Fi every 5 minutes, which does no harm.

## Cloudflare Watchdog

A Cloudflare Worker (`cloudflare/pi-watchdog/`) takes over when the Pi goes quiet, from a power cut or a Wi-Fi drop, say.

After each run where at least one script worked, `run.sh` posts to the Worker's `/heartbeat`. Every 5 minutes, at 2 minutes past each Pi run, the Worker checks the last check-in. If it is more than 12 minutes old (two missed runs), Cloudflare takes over:

- It starts **Refresh Every 5 Minutes (Pi Fallback)** every 5 minutes.
- It starts any scheduled workflow that fell due since the Pi went quiet (looking back up to 30 minutes), unless GitHub shows it already ran. So a workflow due just before the takeover runs late rather than being missed, and none runs twice.
- It emails `mat@thechels.uk` from `alerts@cheltenham-od.uk` and turns the Hue light full-brightness orange, through the separate **cf-worker-notifier** Worker.

The first check-in after that hands back to the Pi: Cloudflare stops, the light goes back to how it was, and a "the Pi is back" email follows. The Worker never takes over before the Pi has checked in once.

The fuel prices API and the council's planning portal refuse GitHub's servers, and NHS England's A&E pages haven't shown them a new month, so fuel prices, planning applications and A&E figures don't update while Cloudflare is in charge, and they show as failing in the fetch status. Everything else does.

### Failing Fetchers

Once an hour the Worker also reads every runner's `_data/fetch-status/<runner>.json` from GitHub (written by `_python/fetch_status.py`). If any script has been failing for too long (an hour for the Pi's 5-minute scripts, 24 hours for the workflows'), it sends one email listing each one, since when, and its last error. It emails once per failure, so a script that recovers and later fails again gets a new email. The list of runners in `src/fetch-status.js` must match `RUNNERS` in `_python/fetch_status.py`, and a test checks this.

### Raw Data Archive

The Worker also runs [uk.cheltenham-od.raw](https://github.com/thechelsuk/uk.cheltenham-od.raw), which keeps the raw downloads of the sources that have no history of their own (fuel prices, road closures, bus disruptions, power cuts, flood and weather warnings, storm overflows, fire severity, school closures and public toilets; its README lists them with their licences), so a history can be rebuilt if a script here goes wrong. Every 15 minutes, at :02, :17, :32 and :47, it starts that repository's **Capture** workflow (`src/raw.js`). Fuel Finder refuses GitHub's servers but not Cloudflare's, so the workflow gets the fuel CSV through the Worker's `/raw/fuel.csv`, which needs `FUEL_PROXY_TOKEN`. The hourly fetcher check reads that repository's `status.json` too, and emails after an hour of failures.

### Status and Switching

`https://pi-watchdog.<your-subdomain>.workers.dev/status` shows the mode, when the Pi last checked in, whether Cloudflare is in charge, and what it last started.

The mode is `auto` (the default: follow the check-ins), `pi` (never take over) or `cloud` (always take over). To change it, from a phone (an iOS Shortcut works) or a terminal:

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" "https://pi-watchdog.<your-subdomain>.workers.dev/mode?mode=cloud"
```

You can also edit the `mode` key in the Worker's KV namespace in the Cloudflare dashboard. Any workflow can still be started by hand from the Actions tab.

### Watchdog Setup

1. Deploy **cf-worker-notifier** first (its readme has the steps), since the watchdog binds to it.
2. Add these repository secrets (Settings → Secrets and variables → Actions):
   - `CLOUDFLARE_WORKERS_TOKEN`: a Cloudflare API token with Workers Scripts: Edit and Workers KV Storage: Edit
   - `CLOUDFLARE_ACCOUNT_ID`
   - `WATCHDOG_GITHUB_TOKEN`: a fine-grained GitHub token for this repository only, with **Actions: Read and write**
   - `WATCHDOG_HEARTBEAT_TOKEN` and `WATCHDOG_ADMIN_TOKEN`: each from `openssl rand -hex 32`
   - `NOTIFY_TOKEN`: the same value as cf-worker-notifier's `NOTIFY_TOKEN`
   - `WATCHDOG_RAW_GITHUB_TOKEN`: a fine-grained GitHub token for **uk.cheltenham-od.raw** only, with **Actions: Read and write**
   - `WATCHDOG_FUEL_PROXY_TOKEN`: from `openssl rand -hex 32`, also saved as `FUEL_PROXY_TOKEN` in uk.cheltenham-od.raw's secrets, alongside its `NAT_HIGH_KEY`
3. Push to `main`. **Deploy Pi Watchdog** runs the tests and deploys (the first deploy creates the Worker's KV namespace) whenever `cloudflare/pi-watchdog/` or `crontab.txt` changes, or run it by hand from the Actions tab.
4. On the Pi, add `WATCHDOG_URL=https://pi-watchdog.<your-subdomain>.workers.dev` and `WATCHDOG_TOKEN=<the WATCHDOG_HEARTBEAT_TOKEN value>` to `.env`.
