#!/usr/bin/env bash
# The Pi's entry point, called by cron. Each argument is either a manifest
# name, meaning the scripts listed in _python/pi/<name>.txt, or a script path:
#
#   _python/run.sh every-5-minutes
#   _python/run.sh _python/pi/power.py
#   _python/run.sh --list every-5-minutes hourly    (print the scripts and stop)
#
# It pulls the latest main, runs each script, then commits and pushes any
# changes. Manifests are read after the pull, so a script added to one runs
# from the next run without touching the crontab.
#
# git pull can replace this file while it runs, and bash reads a script as it
# goes. So everything is inside main(), called on the last lines: bash has read
# the whole file before anything runs, and exits before reading any further.
set -euo pipefail

# Print the scripts each argument names, one per line.
resolve() {
    local arg manifest
    for arg in "$@"; do
        if [[ "$arg" == *.py ]]; then
            echo "$arg"
        else
            manifest="_python/pi/$arg.txt"
            if [[ ! -f "$manifest" ]]; then
                echo "ERROR: no manifest $manifest for '$arg'" >&2
                return 1
            fi
            grep -v -E '^[[:space:]]*(#|$)' "$manifest" || true
        fi
    done
}

# Tell the Cloudflare watchdog this run worked, so it leaves the fallback off.
# Reads WATCHDOG_URL and WATCHDOG_TOKEN from .env; does nothing if either is unset.
# The token goes to curl on stdin so it never shows in the process list.
heartbeat() {
    local url token
    url="$(grep -E '^WATCHDOG_URL=' .env 2>/dev/null | cut -d= -f2- || true)"
    token="$(grep -E '^WATCHDOG_TOKEN=' .env 2>/dev/null | cut -d= -f2- || true)"
    if [[ -z "$url" || -z "$token" ]]; then
        return 0
    fi
    printf 'Authorization: Bearer %s\n' "$token" \
        | curl -fsS -m 10 -X POST -H @- "${url%/}/heartbeat" > /dev/null \
        || echo "WARN: watchdog heartbeat failed"
}

main() {
    cd "$(dirname "$0")/.."

    if [[ "${1:-}" == "--list" ]]; then
        shift
        resolve "$@"
        return
    fi

    # shellcheck source=/dev/null
    source .venv/bin/activate

    git pull --rebase --quiet origin main

    local list
    list="$(resolve "$@")"
    local scripts=()
    while IFS= read -r script; do
        [[ -n "$script" ]] && scripts+=("$script")
    done <<< "$list"
    if [[ ${#scripts[@]} -eq 0 ]]; then
        echo "ERROR: no scripts to run for [$*]" >&2
        return 1
    fi

    local ok=0
    for script in "${scripts[@]}"; do
        if python "$script"; then
            ok=$((ok + 1))
        else
            echo "WARN: $script failed"
        fi
    done

    if ! git diff --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
        git add -A
        git commit -m "Automated data update $(date -u +'%Y-%m-%dT%H:%M:%SZ') [${scripts[*]}]"
        git push --quiet origin main
        echo "$(date -u +%H:%M:%SZ) pushed [${scripts[*]}]"
    else
        echo "$(date -u +%H:%M:%SZ) no changes [${scripts[*]}]"
    fi

    # A run where every script failed (the Pi lost its connection, say) must
    # not count as healthy, or the watchdog would never start the fallback.
    if [[ $ok -gt 0 ]]; then
        heartbeat
    else
        echo "WARN: every script failed, so no watchdog heartbeat"
    fi
}

main "$@"
exit
