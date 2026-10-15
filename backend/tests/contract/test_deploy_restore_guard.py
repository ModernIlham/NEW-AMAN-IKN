"""Mutex deploy dengan Mongo lokal nyata, tanpa mengubah service produksi."""
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
import uuid

from pymongo import MongoClient
import pytest

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def real_guard(tmp_path):
    url = os.environ.get("AMAN_CONTRACT_MONGO_URL", "")
    parsed = urlparse(url)
    if parsed.scheme != "mongodb" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("AMAN_CONTRACT_MONGO_URL harus menunjuk Mongo loopback terisolasi")
    database = "aman_deploy_contract_" + uuid.uuid4().hex
    client = MongoClient(url, serverSelectionTimeoutMS=3000)
    db = client[database]
    app = tmp_path / "app"
    (app / "backend").mkdir(parents=True)
    (app / "backend/venv").symlink_to(Path(sys.executable).parent.parent)
    (app / "backend/.env").write_text("MONGO_URL=" + url + "\nDB_NAME=" + database + "\n")
    source = (ROOT / "scripts/deploy_vps.sh").read_text()
    begin = source.index('AMAN_DEPLOY_OWNER="deploy:')
    end = source.index("\nperiksa_restore_aktif\n", begin)
    body = "set -euo pipefail\ncd \"$APP_DIR\"\n" + source[begin:end]
    def command(action, owner):
        return body + '\nAMAN_DEPLOY_OWNER="$GUARD_TEST_OWNER"\nkelola_kontrol_restore "$GUARD_TEST_ACTION"\n', dict(
            os.environ, APP_DIR=str(app), GUARD_TEST_ACTION=action, GUARD_TEST_OWNER=owner)
    def run(action="check", owner="deploy:test"):
        text, env = command(action, owner)
        result = subprocess.run(["bash", "-s"], input=text, env=env, capture_output=True, text=True, timeout=15)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    yield db, run, command
    if db.name == database and db.name.startswith("aman_deploy_contract_"):
        client.drop_database(database)
    client.close()


@pytest.mark.parametrize("state", ["preparing", "restoring", "rolling_back", "recovery_required", "deploying"])
def test_persistent_state_survives_old_heartbeat_and_missing_jobs(real_guard, state):
    db, run, _ = real_guard
    db.restore_control.insert_one({"_id":"GLOBAL", "state":state, "active":True,
                                  "destructive_started":True, "updated_at":"2000-01-01T00:00:00+00:00"})
    assert db.backup_jobs.count_documents({}) == 0
    assert run("check") == "1"
    assert run("acquire") == "1"
    assert db.restore_control.find_one({"_id":"GLOBAL"})["state"] == state


def test_atomic_acquire_has_single_owner_and_release_cannot_clear_other_owner(real_guard):
    db, run, command = real_guard
    processes = []
    for index in range(6):
        text, env = command("acquire", "deploy:race-" + str(index))
        proc = subprocess.Popen(["bash", "-s"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
        proc.stdin.write(text)
        proc.stdin.close()
        processes.append(proc)
    outputs = []
    for proc in processes:
        proc.wait(timeout=20)
        assert proc.returncode == 0, proc.stderr.read()
        outputs.append(proc.stdout.read().strip())
    assert outputs.count("0") == 1 and outputs.count("1") == 5
    owner = db.restore_control.find_one({"_id":"GLOBAL"})["owner"]
    assert run("release", "deploy:wrong-owner") == "1"
    assert db.restore_control.find_one({"_id":"GLOBAL"})["owner"] == owner
    assert run("release", owner) == "0"
    assert db.restore_control.find_one({"_id":"GLOBAL"})["active"] is False
    assert run("acquire", "deploy:next") == "0"


def test_deploy_requires_download_workers_to_drain(real_guard):
    db, run, _ = real_guard
    assert run("acquire") == "0"
    assert run("drain") == "0"
    db.unduhan.insert_one({"unduhan_id":"fixture", "status":"running"})
    assert run("drain") == "1"
    db.unduhan.update_one({"unduhan_id":"fixture"}, {"$set":{"status":"done"}})
    assert run("drain") == "0"
    db.restore_write_leases.insert_one({"_id":"writer-still-admitted"})
    assert run("drain") == "1"
    db.restore_write_leases.delete_one({"_id":"writer-still-admitted"})
    assert run("drain") == "0"
    db.background_jobs.insert_one({"job_id":"legacy-detached","status":"importing"})
    assert run("drain") == "1"
    db.background_jobs.update_one({"job_id":"legacy-detached"},{"$set":{"status":"done","done":True}})
    assert run("drain") == "0"
    db.background_jobs.insert_one({"job_id":"unknown-detached","status":"future_state"})
    assert run("drain") == "1"
    db.background_jobs.update_one({"job_id":"unknown-detached"},{"$set":{"done":True}})
    assert run("drain") == "0"
    db.background_jobs.insert_one({"job_id":"typed-queue","worker_protocol":"export_v1","status":"queued"})
    assert run("drain") == "0"
    db.background_jobs.update_one({"job_id":"typed-queue"},{"$set":{"status":"running"}})
    assert run("drain") == "1"
    db.background_jobs.update_one({"job_id":"typed-queue"},{"$set":{"status":"done"}})
    db.background_jobs.insert_one({"job_id":"legacy-queue","status":"queued"})
    assert run("drain") == "1"
    assert run("release") == "0"
