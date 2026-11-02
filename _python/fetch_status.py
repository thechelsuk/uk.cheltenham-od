"""
fetch_status.py

Runs one fetcher and records whether it worked, so a script that fails on
every run shows up instead of hiding behind a green job.

    python _python/fetch_status.py <runner> <script> [args...]

<runner> is where it runs: "pi" (run.sh and its GitHub fallback) or the
refresh workflow's file name, e.g. "refresh-every-2-hours". Each runner has
its own _data/fetch-status/<runner>.json, so two runners never edit the same
file at once. For each script it holds:

    last_ok        the UTC date of the last run that worked
    failing_since  when the current run of failures began (null when fine)
    last_error     the last stderr line of the latest failure, redacted

Dates are kept to the day and the file is only rewritten when something
changes, so a healthy script adds at most one commit a day. The script's
output passes straight through, and its exit code is returned, so
`|| echo "::warning::..."` still works. The studio's freshness tab and the
Cloudflare watchdog (which emails after an hour of failures for the Pi's
scripts, 24 hours for the workflows') read the files.
"""

import collections
import json
import os
import pathlib
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATUS_DIR = ROOT / "_data" / "fetch-status"
PYTHON = sys.executable

# Must match RUNNERS in cloudflare/pi-watchdog/src/fetch-status.js (a test checks).
RUNNERS = ("pi", "refresh-every-2-hours", "refresh-4-times-daily", "refresh-weekly", "refresh-monthly")

MAX_ERROR = 300
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)$")


def redact(line, env):
    """The repository is public, so keep API keys out of the saved error:
    drop query strings, and blank the value of any *_KEY/*_TOKEN-style
    environment variable."""
    line = re.sub(r"\?[^\s'\"]*", "?…", line)
    for name, value in env.items():
        if SECRET_NAME.search(name) and len(value) >= 6:
            line = line.replace(value, "***")
    return line[:MAX_ERROR]


def last_error(lines, code):
    for line in reversed(lines):
        if line.strip():
            return line.strip()
    return f"exit code {code}"


def update(record, ok, now, error):
    if ok:
        return {"last_ok": now.date().isoformat(), "failing_since": None, "last_error": None}
    return {
        "last_ok": record.get("last_ok"),
        "failing_since": record.get("failing_since") or now.strftime("%Y-%m-%dT%H:%MZ"),
        "last_error": error,
    }


def key(script):
    path = pathlib.Path(script)
    if not path.is_absolute():
        path = pathlib.Path.cwd() / path
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def run(script, args):
    """Run the script, showing its stderr as it goes and keeping the tail."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    tail = collections.deque(maxlen=50)
    with subprocess.Popen([PYTHON, script, *args], stderr=subprocess.PIPE, text=True,
                          errors="replace", env=env) as proc:
        assert proc.stderr is not None
        for line in proc.stderr:
            sys.stderr.write(line)
            tail.append(line)
    return proc.returncode, list(tail)


def record(runner, script, ok, error, now):
    path = STATUS_DIR / f"{runner}.json"
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        data = {}
    scripts = dict(data.get("scripts") or {})
    name = key(script)
    new = update(scripts.get(name) or {}, ok, now, error)
    if scripts.get(name) == new and data.get("runner") == runner:
        return
    scripts[name] = new
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"runner": runner, "scripts": dict(sorted(scripts.items()))}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def main(argv=None, now=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] not in RUNNERS:
        raise SystemExit(f"usage: fetch_status.py <{'|'.join(RUNNERS)}> <script> [args...]")
    runner, script, args = argv[0], argv[1], argv[2:]
    code, tail = run(script, args)
    error = None if code == 0 else redact(last_error(tail, code), os.environ)
    try:
        record(runner, script, code == 0, error, now or datetime.now(timezone.utc))
    except OSError as exc:
        # Never let the bookkeeping change the outcome of the run.
        print(f"fetch_status: could not record {script}: {exc}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
