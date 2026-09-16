#!/usr/bin/env bash
set -euo pipefail

REPO="$HOME/uk.cheltenham-od"
cd "$REPO"
source .venv/bin/activate

git pull --rebase --quiet origin main

for script in "$@"; do
    python "$script" || echo "WARN: $script failed"
done

if ! git diff --quiet; then
    git add -A
    git commit -m "Automated data update $(date -u +'%Y-%m-%dT%H:%M:%SZ') [$*]"
    git push --quiet origin main
    echo "$(date -u +%H:%M:%SZ) pushed [$*]"
else
    echo "$(date -u +%H:%M:%SZ) no changes [$*]"
fi
