"""The Pi's script manifests (_python/pi/*.txt) and its entry point,
_python/run.sh. Cron, the GitHub fallback workflow and any other runner read
the manifests, so a new Pi script only has to be listed in one of them.
Offline; reads files and runs `run.sh --list`, which never pulls or commits.

Run from the repository root:
    .venv/bin/python -m pytest _python/tests
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
PI = ROOT / "_python" / "pi"
RUN = ROOT / "_python" / "run.sh"
MANIFESTS = ("every-5-minutes", "hourly")


def listed(name):
    lines = (PI / f"{name}.txt").read_text().splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def test_every_listed_script_exists():
    for name in MANIFESTS:
        for script in listed(name):
            assert (ROOT / script).is_file(), f"{name}.txt lists {script}, which does not exist"


def test_every_pi_script_is_in_exactly_one_manifest():
    entries = [script for name in MANIFESTS for script in listed(name)]
    scripts = sorted(f"_python/pi/{p.name}" for p in PI.glob("*.py"))
    assert sorted(entries) == scripts


def test_run_sh_lists_a_manifest_without_pulling():
    out = subprocess.run(["bash", str(RUN), "--list", "every-5-minutes", "hourly"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert out == listed("every-5-minutes") + listed("hourly")


def test_run_sh_still_accepts_script_paths():
    out = subprocess.run(["bash", str(RUN), "--list", "_python/pi/power.py", "hourly"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert out == ["_python/pi/power.py"] + listed("hourly")


def test_run_sh_fails_on_an_unknown_manifest():
    result = subprocess.run(["bash", str(RUN), "--list", "no-such-manifest"], capture_output=True, text=True)
    assert result.returncode != 0 and "no-such-manifest" in result.stderr


def test_run_sh_is_read_in_full_before_it_pulls():
    # git pull can replace run.sh mid-run; bash reads a file as it goes, so the
    # body lives in main(), called on the last lines, and nothing runs before it.
    lines = [line for line in RUN.read_text().splitlines() if line.strip()]
    assert lines[-2:] == ['main "$@"', "exit"]


def test_fallback_workflow_runs_the_manifests_not_its_own_list():
    workflow = (ROOT / ".github" / "workflows" / "refresh-every-5-minutes.yml").read_text()
    assert "run.sh --list every-5-minutes hourly" in workflow
    assert "python '_python/pi/" not in workflow and "python _python/pi/" not in workflow
