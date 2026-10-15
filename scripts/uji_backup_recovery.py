#!/usr/bin/env python3
"""Safe local Mongo/GridFS restore drill, including real SIGKILL and recovery.

Never accepts a target DB or URI: creates an isolated localhost
aman_ci_backup_<uuid> database, temporary files, and verifies before dropping.
Run: .venv/bin/python scripts/uji_backup_recovery.py
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import uuid

# Match the isolated test runner: rate-limiter bookkeeping stays in memory,
# while the application database and GridFS below use real localhost Mongo.
import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def configure(workspace, database):
    if not database.startswith("aman_ci_backup_") or not database[15:].isalnum():
        raise RuntimeError("Unsafe test database name")
    os.environ["MONGO_URL"] = "mongodb://127.0.0.1:27017/"
    os.environ["DB_NAME"] = database
    os.environ["JWT_SECRET"] = os.environ.get("AMAN_BACKUP_DRILL_JWT", "local-ephemeral-backup-drill-only")
    os.environ["REDIS_URL"] = ""
    os.environ["MEILI_URL"] = ""
    import routes.backup as rb
    rb.BACKUP_TEMP_DIR = workspace / "temp"
    rb.BACKUP_ARSIP_DIR = workspace / "archive"
    rb.UPLOADS_DIR = workspace / "uploads"
    for directory in (rb.BACKUP_TEMP_DIR, rb.BACKUP_ARSIP_DIR, rb.UPLOADS_DIR):
        directory.mkdir(exist_ok=True)
    return rb


async def child(args):
    rb = configure(Path(args.workspace), args.database)
    from db import db, fs_bucket
    from bson import ObjectId
    fid = ObjectId("0123456789abcdef01234567")
    if args.child == "seed":
        from auth_utils import hash_password
        await db.users.insert_one({"id": "operator-id", "username": "drill-operator", "role": "admin", "is_active": True,
            "name": "Isolated recovery operator", "created_at": "2026-10-15T00:00:00+00:00",
            "password": hash_password(os.environ["AMAN_BACKUP_DRILL_PASSWORD"])})
        await db.categories.insert_one({"id": "category-id", "name": "Synthetic"})
        await db.inventory_activities.insert_one({"id": "activity-id", "ticket_number": "INV-2026-0041"})
        await db.counters.insert_one({"_id": "inventory_activity_ticket_2026", "seq": 41})
        await db.assets.insert_one({"id": "original-asset", "asset_name": "Synthetic", "photo_gridfs_ids": [str(fid)]})
        await db.portal_pemegang_akses.insert_one({"id": "pegawai-id", "aktif": True, "epoch": 4, "version": 5})
        await db.portal_pemegang_sesi.insert_one({"id": "old-portal-session"})
        stream = fs_bucket.open_upload_stream_with_id(fid, "synthetic.bin")
        await stream.write(b"synthetic media" * 5000)
        await stream.close()
        (rb.UPLOADS_DIR / "logo.txt").write_bytes(b"synthetic upload")
        await db.backup_jobs.insert_one({"job_id": "source", "type": "backup", "status": "queued"})
        await rb.run_backup_task("source", "drill-operator")
        assert (await db.backup_jobs.find_one({"job_id": "source"}))["status"] == "completed"
        return
    if args.child == "crash":
        from datetime import datetime, timezone
        await db.backup_jobs.insert_one({"job_id": "crash", "type": "restore", "status": "queued",
             "active_lock": "GLOBAL", "updated_at": datetime.now(timezone.utc).isoformat()})
        # Hard kill after an actual destructive Mongo write: finally/rollback
        # cannot run. The next process must observe a persistent maintenance gate.
        async def wipe_and_kill(zf, job_id):
            await db.assets.delete_many({})
            os.kill(os.getpid(), signal.SIGKILL)
        rb._apply_archive = wipe_and_kill
        await rb.run_restore_task("crash", rb.BACKUP_TEMP_DIR / "source.zip", "drill-operator")
        raise RuntimeError("Crash injection did not kill child")
    if args.child == "recover":
        import pemeliharaan as pm
        from auth_utils import create_token, get_current_user
        control = await rb.restore_control_status()
        assert control["state"] == "restoring" and control["destructive_started"] is True
        assert await db.assets.count_documents({}) == 0
        assert await pm.pemeliharaan_aktif_uncached() is True
        assert (rb.BACKUP_TEMP_DIR / control["safety_artifact"]).exists()
        # The old child has exited SIGKILL, so the test operator can adopt safely.
        await db.restore_control.update_one({"_id": "GLOBAL", "state": "restoring"},
             {"$set": {"state": "recovery_required"}})
        result = await rb.recover_restore("crash", "isolated-drill-operator")
        assert result["state"] == "rolled_back"
        assert await pm.pemeliharaan_aktif_uncached() is False
        assert await db.assets.count_documents({"id": "original-asset"}) == 1
        stream = await fs_bucket.open_download_stream(fid)
        data = await stream.read()
        assert hashlib.sha256(data).digest() == hashlib.sha256(b"synthetic media" * 5000).digest()
        assert (rb.UPLOADS_DIR / "logo.txt").read_bytes() == b"synthetic upload"
        assert (await db.counters.find_one({"_id": "inventory_activity_ticket_2026"}))["seq"] >= 41
        assert not (await db.portal_pemegang_akses.find_one({"id": "pegawai-id"}))["aktif"]
        assert await db.portal_pemegang_sesi.count_documents({}) == 0
        assert (await get_current_user("Bearer " + create_token("operator-id", "drill-operator")))["id"] == "operator-id"
        from routes.auth import login
        from models import UserLogin
        from starlette.requests import Request
        handler = login
        while hasattr(handler, "__wrapped__"):
            handler = handler.__wrapped__
        login_result = await handler(Request({"type": "http", "method": "POST", "path": "/api/auth/login", "headers": []}),
            UserLogin(username="drill-operator", password=os.environ["AMAN_BACKUP_DRILL_PASSWORD"]))
        assert login_result.user.id == "operator-id"
        print(json.dumps({"actual_restored_password_login": True, "crash_after_wipe": True, "maintenance_survived_restart": True,
                          "recovery_verified": True, "real_gridfs_sha256": True,
                          "uploads_restored": True, "ticket_counter_valid": True,
                          "portal_revoked": True, "restored_user_auth_valid": True}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=["seed", "crash", "recover"])
    parser.add_argument("--workspace")
    parser.add_argument("--database")
    args = parser.parse_args()
    if args.child:
        asyncio.run(child(args))
        return
    database = "aman_ci_backup_" + uuid.uuid4().hex
    environment = dict(os.environ)
    environment["AMAN_BACKUP_DRILL_JWT"] = uuid.uuid4().hex + uuid.uuid4().hex
    environment["AMAN_BACKUP_DRILL_PASSWORD"] = uuid.uuid4().hex + "Aa1!"
    with tempfile.TemporaryDirectory(prefix="aman-backup-drill-") as directory:
        base = [sys.executable, str(Path(__file__).resolve()), "--workspace", directory,
                "--database", database, "--child"]
        try:
            subprocess.run([*base, "seed"], check=True, env=environment, timeout=120)
            crashed = subprocess.run([*base, "crash"], env=environment, timeout=120)
            assert crashed.returncode == -signal.SIGKILL, f"Unexpected child result: {crashed.returncode}"
            subprocess.run([*base, "recover"], check=True, env=environment, timeout=180)
        finally:
            # Hardcoded localhost URI + exact generated DB only; never uses .env.
            from pymongo import MongoClient
            with MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=5000) as client:
                if not database.startswith("aman_ci_backup_") or database[15:] != database[15:].lower():
                    raise RuntimeError("Refusing unsafe database cleanup")
                client.drop_database(database)
                assert database not in client.list_database_names()


if __name__ == "__main__":
    main()
