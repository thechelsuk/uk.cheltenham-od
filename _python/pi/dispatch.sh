#!/usr/bin/env bash
# Start a GitHub workflow on main, for the Pi's crontab (_python/pi/crontab.txt):
#
#   _python/pi/dispatch.sh social-post.yml
#
# GitHub's own schedule trigger runs hours late, so the Pi starts the site's
# scheduled workflows itself. Needs GITHUB_DISPATCH_TOKEN in the repository's
# .env: a fine-grained token for this repository with Actions: read and write.
# The token goes to curl on stdin so it never shows in the process list.
set -euo pipefail

main() {
    cd "$(dirname "$0")/../.."
    local workflow="${1:?usage: dispatch.sh <workflow.yml>}"
    local token
    token="$(grep -E '^GITHUB_DISPATCH_TOKEN=' .env 2>/dev/null | cut -d= -f2- || true)"
    if [[ -z "$token" ]]; then
        echo "ERROR: GITHUB_DISPATCH_TOKEN is not set in .env" >&2
        return 1
    fi
    printf 'Authorization: Bearer %s\n' "$token" \
        | curl -fsS -m 30 -X POST -H @- \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            -d '{"ref":"main"}' \
            "https://api.github.com/repos/thechelsuk/uk.cheltenham-od/actions/workflows/$workflow/dispatches" \
            > /dev/null
    echo "$(date -u +%H:%M:%SZ) started $workflow"
}

main "$@"
exit
