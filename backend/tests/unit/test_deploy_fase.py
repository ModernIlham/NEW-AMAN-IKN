"""Fault injection menjalankan deploy produksi pada checkout Git terisolasi.

Tidak ada SSH, package install, service restart, atau Mongo produksi: hanya
batas eksternal di PATH yang distub. Reset Git, env, rename, trap, dan exit
status tetap dieksekusi sungguhan, termasuk jalur stdin yang dipakai workflow.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/deploy_vps.sh"

STUB = r'''#!/usr/bin/env python3
import json, os, pathlib, signal, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
app = pathlib.Path(os.environ["APP_DIR"])
state = pathlib.Path(os.environ["AMAN_FAULT_STATE"])
fault = os.environ.get("AMAN_FAULT", "")
version = (app / "version.txt").read_text().strip()
with (state / "events.jsonl").open("a") as log:
    log.write(json.dumps({"name":name,"args":args,"version":version,
                         "action":os.environ.get("AMAN_GUARD_ACTION")}) + "\n")
def real(command, arguments):
    return subprocess.run([command, *arguments]).returncode
def stop():
    os.kill(os.getppid(), signal.SIGTERM)
    sys.exit(0)
if name == "git":
    if args[0] == "fetch": sys.exit(128 if fault == "fetch" else 0)
    if args == ["rev-parse", "HEAD"] and fault == "head_mismatch" and version == "new":
        print("0" * 40); sys.exit(0)
    if args[:2] == ["reset", "--hard"]:
        if fault == "rollback_git" and args[2] == os.environ["AMAN_PREV"]: sys.exit(19)
        rc = real(os.environ["AMAN_REAL_GIT"], args)
        if fault == "signal_reset" and args[2] == os.environ["AMAN_TARGET"]: stop()
        if fault == "reset" and args[2] == os.environ["AMAN_TARGET"]: sys.exit(19)
        sys.exit(rc)
    sys.exit(real(os.environ["AMAN_REAL_GIT"], args))
if name == "mongosh":
    action = os.environ["AMAN_GUARD_ACTION"]
    lock = state / "lock.json"
    current = json.loads(lock.read_text()) if lock.exists() else {"state":"completed"}
    if fault == "guard_error": sys.exit(1)
    if action == "drain": print(1 if fault == "active_jobs" else 0)
    elif action == "release":
        if fault == "release": print(1)
        elif current.get("owner") == os.environ["AMAN_GUARD_OWNER"]:
            lock.write_text(json.dumps({"state":"completed","active":False})); print(0)
        else: print(1)
    elif current["state"] not in ["completed","rolled_back","aborted"]: print(1)
    elif action == "acquire":
        lock.write_text(json.dumps({"state":"deploying", "owner":os.environ["AMAN_GUARD_OWNER"]})); print(0)
    else: print(0)
    sys.exit(0)
if name == "pip":
    if fault == "signal_pip" and version == "new": stop()
    if fault == "pip" and version == "new": sys.exit(19)
    if fault == "rollback_pip" and version == "old": sys.exit(19)
    (state / "dependency-version").write_text(version)
    sys.exit(0)
if name == "sudo": sys.exit(1)
if name == "supervisorctl":
    if version == "new" and fault == "signal_restart": stop()
    if version == "new" and fault == "restart": sys.exit(19)
    if version == "old" and fault == "rollback_restart": sys.exit(19)
    (state / "backend-version").write_text(version)
    sys.exit(0)
if name == "curl":
    if version == "old" and fault == "rollback_health": sys.exit(22)
    if version == "new":
        if fault == "signal_final" and (app/"frontend/build/index.html").read_text() == "bundel baru": stop()
        if fault == "health" or (fault == "deep" and args[-1].endswith("/deep")): sys.exit(22)
        if fault == "final_health" and (app/"frontend/build/index.html").read_text() == "bundel baru": sys.exit(22)
    sys.exit(0)
if name == "sleep": sys.exit(0)
if name == "yarn":
    if args[0] == "install":
        if fault == "signal_install": stop()
        sys.exit(19 if fault == "install" else 0)
    if args[0] == "build":
        if fault == "signal_build": stop()
        if fault in ["build", "rollback_git", "rollback_pip", "rollback_restart", "rollback_health", "rollback_env"]: sys.exit(19)
        if fault == "missing_build": sys.exit(0)
        (app / "frontend/build.new").mkdir()
        (app / "frontend/build.new/index.html").write_text("bundel baru")
        sys.exit(0)
if name == "mv":
    if fault == "env" and version == "new" and args[-1].endswith("backend/.env"): sys.exit(19)
    if fault == "rollback_env" and version == "old" and args[-1].endswith("backend/.env"): sys.exit(19)
    if args == ["build", "build.old"] and fault == "archive_move": sys.exit(19)
    if args == ["build.new", "build"] and fault in ["activate", "rollback_frontend"]: sys.exit(19)
    if args == ["frontend/build.old", "frontend/build"] and fault == "rollback_frontend": sys.exit(19)
    rc = real(os.environ["AMAN_REAL_MV"], args)
    if fault == "signal_env" and version == "new" and args[-1].endswith("backend/.env"): stop()
    if args == ["build", "build.old"] and fault == "signal_archive": stop()
    if args == ["build.new", "build"] and fault == "signal_activate": stop()
    sys.exit(rc)
if name == "rm":
    if args == ["-rf", "build.new"] and fault == "clear_new": sys.exit(19)
    if args == ["-rf", "build.old"] and fault == "clear_old": sys.exit(19)
    sys.exit(real(os.environ["AMAN_REAL_RM"], args))
if name == "mktemp":
    result = subprocess.run([os.environ["AMAN_REAL_MKTEMP"], *args], capture_output=True, text=True)
    if result.returncode == 0 and result.stdout.startswith("/tmp/aman-env."):
        with (state / "snapshots").open("a") as log: log.write(result.stdout)
    sys.stdout.write(result.stdout); sys.exit(result.returncode)
raise SystemExit("stub tak dikenal: " + name)
'''


@pytest.fixture
def deploy_case(tmp_path):
    app = tmp_path / "aplikasi dengan spasi"
    app.mkdir()
    state = tmp_path / "batas-eksternal"
    state.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = shutil.which("git")
    def git_run(*args):
        return subprocess.check_output([git, "-C", str(app), *args], text=True).strip()
    git_run("init", "-q")
    git_run("config", "user.email", "uji@example.test")
    git_run("config", "user.name", "Fault injection")
    (app / "backend").mkdir()
    (app / "frontend").mkdir()
    (app / ".gitignore").write_text("backend/.env\nfrontend/.env\nbackend/venv/\nfrontend/build*/\n")
    (app / "version.txt").write_text("old")
    (app / "backend/requirements.txt").write_text("old-dependency==1.0\n")
    git_run("add", ".")
    git_run("commit", "-qm", "known good")
    prev = git_run("rev-parse", "HEAD")
    (app / "version.txt").write_text("new")
    (app / "backend/requirements.txt").write_text("new-dependency==2.0\n")
    git_run("commit", "-qam", "target CI immutable")
    target = git_run("rev-parse", "HEAD")
    (app / "version.txt").write_text("future unapproved")
    git_run("commit", "-qam", "main moves after CI")
    latest = git_run("rev-parse", "HEAD")
    git_run("update-ref", "refs/remotes/origin/main", latest)
    git_run("reset", "--hard", prev)
    original_env = b'MONGO_URL="mongodb://invalid.test:27017"\nDB_NAME=isolated_test\nPRIVATE_FIXTURE=never-log-this\n'
    (app / "backend/.env").write_bytes(original_env)
    (app / "frontend/.env").write_bytes(b"PUBLIC_FIXTURE=synthetic\n")
    (app / "frontend/build").mkdir()
    (app / "frontend/build/index.html").write_text("bundel lama")
    (app / "frontend/build.old").mkdir()
    (app / "frontend/build.old/index.html").write_text("bundel lebih lama")
    for name in ["git", "mongosh", "sudo", "supervisorctl", "curl", "sleep", "yarn", "mv", "rm", "mktemp"]:
        tool = bin_dir / name
        tool.write_text(STUB)
        tool.chmod(0o755)
    pip = app / "backend/venv/bin/pip"
    pip.parent.mkdir(parents=True)
    pip.write_text(STUB)
    pip.chmod(0o755)
    env = dict(os.environ, APP_DIR=str(app), PATH=str(bin_dir)+os.pathsep+os.environ["PATH"],
               AMAN_FAULT_STATE=str(state), AMAN_REAL_GIT=git, AMAN_REAL_MV=shutil.which("mv"),
               AMAN_REAL_MKTEMP=shutil.which("mktemp"), AMAN_REAL_RM=shutil.which("rm"),
               AMAN_PREV=prev, AMAN_TARGET=target)
    def run(fault="", target_sha=target, mode="otomatis", control_state=None):
        if control_state:
            (state / "lock.json").write_text(json.dumps({"state": control_state, "destructive_started":True}))
        result = subprocess.run(["bash", "-s", "--", target_sha, mode], input=SCRIPT.read_text(),
                                env=dict(env, AMAN_FAULT=fault), capture_output=True, text=True, timeout=40)
        events = [json.loads(line) for line in (state / "events.jsonl").read_text().splitlines()]
        assert "never-log-this" not in result.stdout + result.stderr
        assert (app / "backend/.env").read_bytes() == original_env
        assert (app / "frontend/.env").read_bytes() == b"PUBLIC_FIXTURE=synthetic\n"
        return result, events
    yield app, state, prev, target, latest, git_run, run
    # Hanya snapshot fixture yang sengaja dipertahankan akibat fault injection
    # boleh dibersihkan setelah skenario selesai.
    if (state / "snapshots").exists():
        for snapshot in (state / "snapshots").read_text().splitlines():
            path = Path(snapshot)
            if path.parent == Path("/tmp") and path.name.startswith("aman-env."):
                shutil.rmtree(path, ignore_errors=True)


def test_deploy_success_exact_ci_sha_keeps_previous_frontend(deploy_case):
    app, state, prev, target, latest, git_run, run = deploy_case
    result, events = run()
    assert result.returncode == 0, result.stderr
    assert git_run("rev-parse", "HEAD") == target != latest
    assert (app / "frontend/build/index.html").read_text() == "bundel baru"
    assert (app / "frontend/build.old/index.html").read_text() == "bundel lama"
    assert json.loads((state / "lock.json").read_text())["state"] == "completed"
    assert "Deploy selesai:" in result.stdout
    assert (app / "backend/.env").stat().st_mode & 0o777 == 0o600
    for snapshot in (state / "snapshots").read_text().splitlines():
        assert not Path(snapshot).exists()


@pytest.mark.parametrize("fault", ["reset", "head_mismatch", "env", "pip", "restart", "health", "deep", "install", "build", "missing_build", "clear_new", "clear_old", "archive_move", "activate", "final_health", "signal_reset", "signal_env", "signal_pip", "signal_restart", "signal_install", "signal_build", "signal_archive", "signal_activate", "signal_final"])
def test_every_mutating_failure_restores_verified_old_pair(deploy_case, fault):
    app, state, prev, target, latest, git_run, run = deploy_case
    result, events = run(fault)
    assert result.returncode in [1, 19, 143], result.stderr
    assert git_run("rev-parse", "HEAD") == prev
    assert (app / "frontend/build/index.html").read_text() == "bundel lama"
    assert (state / "backend-version").read_text() == "old"
    assert "ROLLBACK selesai" in result.stderr
    assert "Deploy selesai:" not in result.stdout
    assert any(e["name"] == "curl" and e["version"] == "old" and e["args"][-1].endswith("/deep") for e in events)
    assert json.loads((state / "lock.json").read_text())["state"] == "completed"
    if fault != "env":
        assert all(not Path(p).exists() for p in (state / "snapshots").read_text().splitlines())


@pytest.mark.parametrize("fault", ["rollback_git", "rollback_env", "rollback_pip", "rollback_restart", "rollback_health", "rollback_frontend", "release"])
def test_failed_recovery_never_announces_success_and_blocks_next_deploy(deploy_case, fault):
    app, state, prev, target, latest, git_run, run = deploy_case
    result, events = run(fault)
    assert result.returncode == 70, result.stderr
    assert "RECOVERY_REQUIRED" in result.stderr
    if fault != "release":
        assert "ROLLBACK selesai" not in result.stderr
    assert "Deploy selesai:" not in result.stdout
    assert json.loads((state / "lock.json").read_text())["state"] == "deploying"
    if fault == "rollback_frontend":
        assert (app / "frontend/build.old/index.html").read_text() == "bundel lama"


@pytest.mark.parametrize("control", ["preparing", "restoring", "rolling_back", "recovery_required", "deploying", "unknown"])
def test_restore_or_unknown_persistent_control_blocks_before_fetch_or_reset(deploy_case, control):
    app, state, prev, target, latest, git_run, run = deploy_case
    result, events = run(control_state=control)
    assert result.returncode == 1
    assert git_run("rev-parse", "HEAD") == prev
    assert not any(e["name"] == "git" and e["args"][0] in ["fetch", "reset"] for e in events)


@pytest.mark.parametrize("fault", ["guard_error", "fetch", "active_jobs"])
def test_preflight_error_never_mutates_release(deploy_case, fault):
    app, state, prev, target, latest, git_run, run = deploy_case
    result, events = run(fault)
    assert result.returncode != 0
    assert git_run("rev-parse", "HEAD") == prev
    assert (app / "frontend/build/index.html").read_text() == "bundel lama"
    assert not any(e["name"] in ["pip", "supervisorctl", "yarn"] for e in events)


def test_anti_downgrade_and_explicit_manual_rollback(deploy_case):
    app, state, prev, target, latest, git_run, run = deploy_case
    git_run("reset", "--hard", target)
    result, _ = run(target_sha=prev)
    assert result.returncode == 1
    assert git_run("rev-parse", "HEAD") == target
    result, _ = run(target_sha=prev, mode="manual")
    assert result.returncode == 0, result.stderr
    assert git_run("rev-parse", "HEAD") == prev


def test_existing_commit_outside_main_never_activates(deploy_case):
    app, state, prev, target, latest, git_run, run = deploy_case
    tree = git_run("rev-parse", target + "^{tree}")
    outside_main = git_run("commit-tree", tree, "-p", prev, "-m", "outside approved main")
    result, events = run(target_sha=outside_main)
    assert result.returncode == 1
    assert git_run("rev-parse", "HEAD") == prev
    assert not any(e["name"] == "git" and e["args"][0] == "reset" for e in events)
