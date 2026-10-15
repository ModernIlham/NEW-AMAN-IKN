"""Execute the workflow's controller/target gates against real local Git history."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def deployment(tmp_path):
    origin = tmp_path / "origin.git"
    source = tmp_path / "source"
    source.mkdir()
    def git(*args, cwd=source):
        return subprocess.check_output(["git", *args], cwd=cwd, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    git("init", "-b", "main")
    git("config", "user.name", "Deployment fixture")
    git("config", "user.email", "deployment-fixture@example.invalid")
    script = source / "scripts/deploy_vps.sh"
    script.parent.mkdir()
    script.write_text('#!/bin/bash\ngit reset --hard "$DEPLOY_SHA"\n')
    git("add", ".")
    git("commit", "-m", "legacy target")
    legacy = git("rev-parse", "HEAD")
    script.write_text(script.read_text() + "AMAN_CLEAN_VENV_PROTOCOL=1\n")
    git("add", ".")
    git("commit", "-m", "current controller")
    current = git("rev-parse", "HEAD")
    git("checkout", "-b", "unapproved")
    (source / "unapproved").write_text("not on main")
    git("add", ".")
    git("commit", "-m", "unapproved controller")
    unapproved = git("rev-parse", "HEAD")
    git("checkout", "main")
    git("clone", "--bare", str(source), str(origin), cwd=tmp_path)
    checkout = tmp_path / "checkout"
    git("clone", str(origin), str(checkout), cwd=tmp_path)
    commands = tmp_path / "bin"
    commands.mkdir()
    calls = tmp_path / "ci-calls.jsonl"
    curl = commands / "curl"
    curl.write_text(f"#!{sys.executable}\n" + '''import json, os, sys
from urllib.parse import parse_qs, urlparse
sha = parse_qs(urlparse(sys.argv[-1]).query)['head_sha'][0]
with open(os.environ['FIXTURE_CI_CALLS'], 'a') as output:
    output.write(json.dumps(sha) + '\\n')
allowed = os.environ['FIXTURE_CI_ALLOWED'].split(',')
row = {'head_sha':sha, 'head_branch':'main', 'event':'push',
       'status':'completed', 'conclusion':'success'}
print(json.dumps({'workflow_runs':[row] if sha in allowed else []}))
''')
    curl.chmod(0o700)
    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    validation = next(step["run"] for step in workflow["jobs"]["deploy"]["steps"]
                      if step.get("name") == "Validasi asal dan hasil CI commit rilis")
    def run(target=legacy, controller=current, *, allowed=None, event="workflow_dispatch"):
        git("checkout", "--detach", controller, cwd=checkout)
        env = {**os.environ, "PATH":str(commands)+os.pathsep+os.environ["PATH"],
               "DEPLOY_SHA":target, "DEPLOY_CONTROLLER_SHA":controller,
               "GITHUB_EVENT_NAME":event, "GH_TOKEN":"test-ci-token",
               "GITHUB_API_URL":"https://ci-fixture.invalid", "GITHUB_REPOSITORY":"fixture/repo",
               "FIXTURE_CI_CALLS":str(calls),
               "FIXTURE_CI_ALLOWED":",".join(allowed if allowed is not None else [legacy,current])}
        result = subprocess.run(["bash", "-euo", "pipefail", "-c", validation],
                                cwd=checkout, env=env, capture_output=True, text=True, timeout=15)
        observed = [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else []
        return result, observed
    return run, legacy, current, unapproved


def test_manual_legacy_target_uses_current_approved_controller(deployment):
    run, legacy, current, _ = deployment
    result, calls = run()
    assert result.returncode == 0, result.stderr
    assert calls == [legacy, current]


@pytest.mark.parametrize("part", ["target", "controller"])
def test_both_manual_commits_must_have_successful_main_ci(deployment, part):
    run, legacy, current, _ = deployment
    allowed = [current] if part == "target" else [legacy]
    result, _ = run(allowed=allowed)
    assert result.returncode != 0
    assert "belum lulus CI push/main" in result.stdout


@pytest.mark.parametrize("part", ["target", "controller"])
def test_non_main_target_or_controller_rejected_before_ci_api(deployment, part):
    run, legacy, current, unapproved = deployment
    result, calls = run(target=unapproved if part == "target" else legacy,
                        controller=unapproved if part == "controller" else current)
    assert result.returncode != 0
    assert calls == []


def test_automatic_controller_must_equal_triggering_ci_sha(deployment):
    run, _, _, _ = deployment
    result, calls = run(event="workflow_run")
    assert result.returncode != 0
    assert calls == []
    assert "SHA CI yang sama" in result.stdout


def test_automatic_matching_sha_uses_trigger_ci_without_manual_api(deployment):
    run, _, current, _ = deployment
    result, calls = run(target=current, event="workflow_run")
    assert result.returncode == 0, result.stderr
    assert calls == []


def test_old_controller_cannot_take_over_protocol(deployment):
    run, legacy, _, _ = deployment
    result, _ = run(controller=legacy)
    assert result.returncode != 0
    assert "lingkungan rilis terisolasi" in result.stdout
