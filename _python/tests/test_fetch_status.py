"""Offline tests for fetch_status.py, the wrapper that runs each fetcher and
records in _data/fetch-status/<runner>.json whether it worked, plus checks
that every runner (the refresh workflows and the Pi) goes through it.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import importlib.util
import json
import pathlib
import re
import sys
from datetime import datetime, timezone

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("fetch_status", ROOT / "_python" / "fetch_status.py")
assert SPEC is not None and SPEC.loader is not None
fetch_status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_status)

NOW = datetime(2026, 11, 2, 9, 30, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------- redact

def test_redact_drops_query_strings():
    line = "403 Client Error: Forbidden for url: https://api.example.com/v1/x?key=abc123&q=1"
    assert fetch_status.redact(line, {}) == "403 Client Error: Forbidden for url: https://api.example.com/v1/x?…"


def test_redact_hides_secret_values_from_the_environment():
    env = {"OCM_API_KEY": "s3cr3t-value", "HOME": "/home/runner"}
    out = fetch_status.redact("failed with s3cr3t-value in /home/runner", env)
    assert out == "failed with *** in /home/runner"


def test_redact_ignores_short_secret_values():
    # A one-character "secret" would blank out every matching letter.
    assert fetch_status.redact("abc", {"X_TOKEN": "a"}) == "abc"


def test_redact_caps_the_length():
    assert len(fetch_status.redact("x" * 1000, {})) == fetch_status.MAX_ERROR


# ---------------------------------------------------------------- last error

def test_last_error_is_the_last_non_empty_stderr_line():
    lines = ["Traceback (most recent call last):\n", "  File ...\n", "HTTPError: 403\n", "\n"]
    assert fetch_status.last_error(lines, 1) == "HTTPError: 403"


def test_last_error_falls_back_to_the_exit_code():
    assert fetch_status.last_error([], 2) == "exit code 2"


# ---------------------------------------------------------------- update

def test_success_records_today_and_clears_a_failure():
    old = {"last_ok": "2026-10-01", "failing_since": "2026-10-15T12:00Z", "last_error": "403"}
    assert fetch_status.update(old, True, NOW, None) == {
        "last_ok": "2026-11-02", "failing_since": None, "last_error": None}


def test_first_failure_starts_the_clock():
    old = {"last_ok": "2026-11-01", "failing_since": None, "last_error": None}
    assert fetch_status.update(old, False, NOW, "HTTPError: 403") == {
        "last_ok": "2026-11-01", "failing_since": "2026-11-02T09:30Z", "last_error": "HTTPError: 403"}


def test_later_failures_keep_the_start_and_take_the_newest_error():
    old = {"last_ok": "2026-11-01", "failing_since": "2026-11-01T20:00Z", "last_error": "HTTPError: 403"}
    new = fetch_status.update(old, False, NOW, "Timeout")
    assert new["failing_since"] == "2026-11-01T20:00Z" and new["last_error"] == "Timeout"


def test_a_new_script_that_fails_has_no_last_ok():
    assert fetch_status.update({}, False, NOW, "boom")["last_ok"] is None


# ---------------------------------------------------------------- run end to end

@pytest.fixture
def status_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_status, "STATUS_DIR", tmp_path / "fetch-status")
    return tmp_path / "fetch-status"


def script(tmp_path, body):
    path = tmp_path / "fetcher.py"
    path.write_text(body)
    return str(path)


def read(status_dir, runner="pi"):
    return json.loads((status_dir / f"{runner}.json").read_text())


def test_main_passes_the_exit_code_through_and_records_a_failure(tmp_path, status_dir, capsys):
    path = script(tmp_path, "import sys\nprint('working')\nsys.exit('Could not find the link')\n")
    assert fetch_status.main(["pi", path], now=NOW) == 1
    record = read(status_dir)["scripts"][fetch_status.key(path)]
    assert record["failing_since"] == "2026-11-02T09:30Z"
    assert record["last_error"] == "Could not find the link"
    # stderr is still shown, so the workflow log is unchanged
    assert "Could not find the link" in capsys.readouterr().err


def test_main_records_a_success(tmp_path, status_dir):
    path = script(tmp_path, "print('ok')\n")
    assert fetch_status.main(["refresh-monthly", path], now=NOW) == 0
    data = read(status_dir, "refresh-monthly")
    assert data["runner"] == "refresh-monthly"
    assert data["scripts"][fetch_status.key(path)]["last_ok"] == "2026-11-02"


def test_main_leaves_the_file_alone_when_nothing_changed(tmp_path, status_dir):
    path = script(tmp_path, "print('ok')\n")
    fetch_status.main(["pi", path], now=NOW)
    before = (status_dir / "pi.json").stat().st_mtime_ns
    assert fetch_status.main(["pi", path], now=NOW.replace(hour=15)) == 0
    assert (status_dir / "pi.json").stat().st_mtime_ns == before


def test_main_rejects_an_unknown_runner(tmp_path, status_dir):
    with pytest.raises(SystemExit):
        fetch_status.main(["somewhere", script(tmp_path, "")], now=NOW)


def test_key_is_relative_to_the_repository():
    assert fetch_status.key("_python/news.py") == "_python/news.py"
    assert fetch_status.key(str(ROOT / "_python" / "pi" / "fuel.py")) == "_python/pi/fuel.py"


# ---------------------------------------------------------------- every runner uses it

WORKFLOWS = ROOT / ".github" / "workflows"


@pytest.mark.parametrize("runner", [r for r in fetch_status.RUNNERS if r != "pi"])
def test_each_refresh_workflow_runs_its_scripts_through_fetch_status(runner):
    text = (WORKFLOWS / f"{runner}.yml").read_text()
    calls = re.findall(r"^\s*python (.+?) \|\|", text, re.M)
    assert calls, f"{runner}.yml runs no scripts"
    for call in calls:
        assert call.startswith(f"_python/fetch_status.py {runner} "), f"{runner}.yml: {call}"


def test_every_refresh_workflow_is_a_runner():
    names = {p.stem for p in WORKFLOWS.glob("refresh-*.yml")} - {"refresh-every-5-minutes"}
    assert names == set(fetch_status.RUNNERS) - {"pi"}


def test_the_pi_and_its_fallback_run_scripts_through_fetch_status():
    run_sh = (ROOT / "_python" / "run.sh").read_text()
    assert 'python _python/fetch_status.py pi "$script"' in run_sh
    fallback = (WORKFLOWS / "refresh-every-5-minutes.yml").read_text()
    assert 'python _python/fetch_status.py pi "$script"' in fallback


def test_the_watchdog_reads_every_runner():
    js = (ROOT / "cloudflare" / "pi-watchdog" / "src" / "fetch-status.js").read_text()
    listed = re.search(r"RUNNERS = \[([^\]]*)\]", js)
    assert listed, "fetch-status.js has no RUNNERS list"
    assert re.findall(r'"([^"]+)"', listed.group(1)) == list(fetch_status.RUNNERS)


def test_sys_executable_runs_the_child():
    # The wrapper must run the fetcher with the same Python (the Pi's venv).
    assert fetch_status.PYTHON == sys.executable
