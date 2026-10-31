# Pi Watchdog

A Cloudflare Worker that stands in for the [Cheltenham Open Data](https://cheltenham-od.uk) Raspberry Pi when it goes quiet.

The Pi fetches the 5-minute data feeds and starts the site's scheduled GitHub workflows. After each run where at least one script worked, it posts to this Worker's `/heartbeat`. Every 5 minutes the Worker checks the last check-in. After two missed runs it takes over:

- it starts the **Refresh Every 5 Minutes (Pi Fallback)** workflow every 5 minutes
- it starts any scheduled workflow that fell due while the Pi was quiet, unless GitHub shows it already ran
- it sends an email and turns a Hue light orange, through the [cf-worker-notifier](https://github.com/thechelsuk/cf-worker-notifier) Worker

The Pi's next check-in hands back control, restores the light and sends a "the Pi is back" email.

## Endpoints

| Path | Method | Auth | What it does |
| --- | --- | --- | --- |
| `/heartbeat` | POST | `HEARTBEAT_TOKEN` | Records a check-in from the Pi |
| `/status` | GET | None | The mode, last check-in, whether Cloudflare is in charge, and what it last started |
| `/mode?mode=auto\|pi\|cloud` | POST | `ADMIN_TOKEN` | Follow the check-ins, never take over, or always take over |

## Files

- `src/index.js`: the routes and the 5-minute check
- `src/schedules.js`: the scheduled workflows, in UK time; must match `_python/pi/crontab.txt` (a test checks)
- `src/cron.js`: reads those schedules in `Europe/London`
- `wrangler.toml`: the Worker's cron trigger, settings, KV store and notifier binding; secrets are never in it

## Tests and Deploying

```bash
npm test
```

The tests also check that no workflow in `.github/workflows/` has a GitHub `schedule:` of its own. The **Deploy Pi Watchdog** workflow runs them and deploys on every push to `main` that changes this folder or the crontab.

Setup, secrets and switching are covered in the site's [Raspberry Pi guide](../../admin/guide/raspberry-pi.md).
