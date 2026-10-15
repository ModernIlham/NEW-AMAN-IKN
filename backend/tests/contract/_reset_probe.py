"""Actual ASGI/Mongo reset probes in a disposable database, never production."""
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlparse
import uuid


async def run():
    scenario, database_name, directory = sys.argv[1:4]
    mongo = os.environ["AMAN_CONTRACT_MONGO_URL"]
    if (urlparse(mongo).hostname not in {"127.0.0.1", "localhost", "::1"}
            or not database_name.startswith("aman_ci_reset_")):
        raise RuntimeError("Disposable loopback database required")
    os.environ["MONGO_URL"] = mongo
    os.environ["DB_NAME"] = database_name
    os.environ["REDIS_URL"] = os.environ.get("AMAN_CONTRACT_REDIS_URL", "")
    os.environ["MEILI_URL"] = ""
    os.environ["JWT_SECRET"] = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(48)
    os.environ["ADMIN_BOOTSTRAP_TOKEN"] = secrets.token_urlsafe(48)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from db import client, db, fs_bucket
    import routes.backup as backup
    import pemeliharaan
    from reset_service import reset_system
    import httpx

    directory = Path(directory)
    backup.BACKUP_TEMP_DIR = directory / "backup"
    backup.UPLOADS_DIR = directory / "uploads"
    backup.BACKUP_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    backup.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    if scenario == "crash-worker":
        apply = backup._apply_archive
        async def die_after_wipe(*args, **kwargs):
            await apply(*args, **kwargs)
            os._exit(73)
        backup._apply_archive = die_after_wipe
        await reset_system("local-test-worker")
        raise AssertionError("Crash hook did not run")

    from server import app
    from indexes import create_indexes, kegagalan_indeks
    from dataset_epoch import get_generation
    import redis_utils
    await create_indexes()
    assert not kegagalan_indeks(), kegagalan_indeks()
    password = "SyntheticReset9-" + secrets.token_urlsafe(16)
    try:
        # Keep the real shared test Redis limiter, using one loopback client
        # identity per disposable database so parallel CI bootstrap probes do
        # not consume each other's three-per-minute admission allowance.
        client_ip = "127.77." + str(int(database_name[-4:-2], 16)) + "." + str(int(database_name[-2:], 16))
        transport = httpx.ASGITransport(app=app, client=(client_ip, 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://reset-probe") as http:
            bootstrap = await http.post("/api/auth/bootstrap", json={
                "username": "reset-root", "name": "Synthetic reset operator", "password": password,
            }, headers={"X-Admin-Bootstrap-Token": os.environ["ADMIN_BOOTSTRAP_TOKEN"]})
            assert bootstrap.status_code == 200, bootstrap.text
            headers = {"Authorization": "Bearer " + bootstrap.json()["access_token"]}
            root = await db.users.find_one({"username": "reset-root"})
            root_id = root["id"]
            body = {"admin_id": root_id, "confirmation": "HAPUS SEMUA"}
            now = datetime.now(timezone.utc)
            kept = {}
            for name in ("signature", "overlay", "future", "employee"):
                kept[name] = await fs_bucket.upload_from_stream(name, (name + " bytes").encode(),
                    metadata={"jenis": "foto_pegawai"} if name == "employee" else {})
            removed = await fs_bucket.upload_from_stream("asset", b"asset bytes")
            await db.report_settings.insert_one({"type": "global",
                "kasatker_ttd_file_id": str(kept["signature"]), "logo_url": "data:image/png;base64,c3ludGhldGlj",
                "future_media": {"url": "/api/media/" + str(kept["future"])}, "bson_time": now})
            await db.spasial_node.insert_one({"id": "reset-node",
                "properties": {"denah_overlay": {"file_id": str(kept["overlay"])}}})
            await db.categories.insert_one({"id": "master-category", "name": "Master tetap"})
            await db.inventory_activities.insert_one({"id": "reset-activity", "status_pengesahan": "draft"})
            await db.assets.insert_one({"id": "reset-asset", "asset_code": "301", "asset_name": "Synthetic",
                "activity_id": "reset-activity", "NUP": "1", "version": 1,
                "photo_gridfs_ids": [str(removed)]})
            (backup.UPLOADS_DIR / "logo.txt").write_bytes(b"local logo kept")
            original_setting = await db.report_settings.find_one({"type": "global"})
            old_generation = await get_generation(db)

            async def reset():
                return await http.request("DELETE", "/api/system/reset-all", json=body, headers=headers)

            async def login_works():
                result = await http.post("/api/auth/login", json={"username": "reset-root", "password": password})
                assert result.status_code == 200, result.text

            async def assert_media(ids):
                assert {row["_id"] async for row in db["fs.files"].find({})} == set(ids)
                for identifier in ids:
                    stream = await fs_bucket.open_download_stream(identifier)
                    assert await stream.readchunk()
                assert (backup.UPLOADS_DIR / "logo.txt").read_bytes() == b"local logo kept"

            if scenario == "success-race":
                await db.background_jobs.insert_one({"job_id": "reset-expired-legacy", "status": "done",
                    "artifact_id": str(removed), "dibuat_oleh": "reset-root", "kode_satker": ""})
                await db.unduhan.insert_one({"unduhan_id": "reset-expired-download", "status": "done",
                    "artifact_id": str(removed), "dibuat_oleh": "reset-root", "kode_satker": ""})
                expired_links = ("/api/jobs/reset-expired-legacy/download", "/api/unduhan/reset-expired-download/file")
                for link in expired_links:
                    existing = await http.get(link, headers=headers)
                    assert existing.status_code == 200 and existing.content == b"asset bytes", existing.text
                invalid = await http.request("DELETE", "/api/system/reset-all", headers=headers,
                    json={"admin_id": root_id, "confirmation": "wrong"})
                assert invalid.status_code == 400
                await db.satker.insert_one({"id": "reset-satker", "kode_satker": "990009", "nama_satker": "Synthetic"})
                acting = await http.request("DELETE", "/api/system/reset-all", json=body,
                    headers={**headers, "X-Satker-Aktif": "990009"})
                assert acting.status_code == 400, acting.text
                assert await db.assets.count_documents({}) == 1
                assert await db.backup_jobs.count_documents({}) == 0
                preflight = await http.post("/api/assets/batch-v2/preflight", json={"asset_ids": ["reset-asset"]}, headers=headers)
                assert preflight.status_code == 200, preflight.text
                prepared = {"operation_id": "b2_" + str(int(now.timestamp() * 1000)) + "_" + str(uuid.uuid4()),
                    "dataset_generation": preflight.json()["dataset_generation"], "asset_ids": ["reset-asset"],
                    "expected_versions": {"reset-asset": 1}, "updates": {"location": "old request"}}
                async with pemeliharaan.writer_admission(database=db):
                    operation = asyncio.create_task(reset())
                    for _ in range(200):
                        control = await backup.restore_control_status()
                        if control.get("state") == "preparing":
                            break
                        await asyncio.sleep(0.025)
                    assert control.get("state") == "preparing"
                    # The exact HTTP lease must be excluded, while this other
                    # live writer's physical lease still prevents the wipe.
                    assert await db.assets.count_documents({}) == 1
                    rejected = await http.put("/api/assets/batch-v2", json=prepared, headers=headers)
                    assert rejected.status_code == 503, rejected.text
                    await db.assets.update_one({"id": "reset-asset"}, {"$set": {"notes": "last admitted writer"}})
                    assert not operation.done()
                result = await asyncio.wait_for(operation, 30)
                assert result.status_code == 200, result.text
                assert result.json()["deleted"]["assets"] == 1
                assert result.json()["deleted"]["gridfs_files"] == 1
                assert await db.assets.count_documents({}) == 0
                assert await db.inventory_activities.count_documents({}) == 0
                assert await db.report_settings.find_one({"type": "global"}) == original_setting
                assert await db.categories.count_documents({"id": "master-category"}) == 1
                assert await get_generation(db) != old_generation
                await assert_media(kept.values())
                assert await db.restore_write_leases.count_documents({}) == 0
                assert (await backup.restore_control_status())["state"] == "completed"
                assert not list(backup.BACKUP_TEMP_DIR.glob("*.zip"))
                await login_works()
                for link in expired_links:
                    expired = await http.get(link, headers=headers)
                    assert expired.status_code in {404, 410}, expired.text
                    assert "kedaluwarsa" in expired.json()["detail"].lower()
                # Reusing a semantic ID after reset cannot revive a prepared
                # operation from the old installation-local dataset generation.
                await db.inventory_activities.insert_one({"id": "reset-activity", "status_pengesahan": "draft"})
                await db.assets.insert_one({"id": "reset-asset", "asset_code": "301", "NUP": "1",
                    "activity_id": "reset-activity", "version": 1, "location": "fresh dataset"})
                stale = await http.put("/api/assets/batch-v2", json=prepared, headers=headers)
                assert stale.status_code == 409, stale.text
                assert (await db.assets.find_one({"id": "reset-asset"}))["location"] == "fresh dataset"
            elif scenario in {"rollback", "failed-rollback"}:
                apply = backup._apply_archive
                attempts = 0
                async def fail_after_wipe(*args, **kwargs):
                    nonlocal attempts
                    attempts += 1
                    applied = await apply(*args, **kwargs)
                    if attempts == 1 or scenario == "failed-rollback":
                        raise IOError("injected post-wipe verification failure")
                    return applied
                backup._apply_archive = fail_after_wipe
                result = await reset()
                assert result.status_code in {500, 503}, result.text
                control = await backup.restore_control_status()
                if scenario == "failed-rollback":
                    assert control["state"] == "recovery_required", control
                    assert (backup.BACKUP_TEMP_DIR / control["safety_artifact"]).exists()
                    assert (backup.BACKUP_TEMP_DIR / control["source_artifact"]).exists()
                    blocked = await http.post("/api/auth/login", json={"username": "reset-root", "password": password})
                    assert blocked.status_code == 503, blocked.text
                    backup._apply_archive = apply
                    recovered = await backup.recover_restore(control["job_id"], "test-operator")
                    assert recovered["state"] == "rolled_back"
                else:
                    assert control["state"] == "rolled_back", control
                    assert not list(backup.BACKUP_TEMP_DIR.glob("*.zip"))
                assert await db.assets.count_documents({"id": "reset-asset"}) == 1
                assert await db.users.count_documents({"id": root_id}) == 1
                await assert_media([*kept.values(), removed])
                await login_works()
            elif scenario == "killed-worker":
                worker = await asyncio.create_subprocess_exec(sys.executable, __file__, "crash-worker", database_name, str(directory),
                                                              stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                stdout, stderr = await asyncio.wait_for(worker.communicate(), 35)
                assert worker.returncode == 73, (worker.returncode, stderr.decode()[-3000:])
                control = await backup.restore_control_status()
                assert control["state"] == "restoring" and control["destructive_started"] is True
                assert await db.assets.count_documents({}) == 0
                assert (backup.BACKUP_TEMP_DIR / control["safety_artifact"]).exists()
                blocked = await http.post("/api/auth/login", json={"username": "reset-root", "password": password})
                assert blocked.status_code == 503
                # This worker has exited. Adopt the durable journal through the
                # same explicit stopped-worker recovery contract as the CLI.
                await db.restore_control.update_one({"_id": "GLOBAL", "job_id": control["job_id"], "state": "restoring"},
                    {"$set": {"state": "recovery_required", "active": True}})
                recovered = await backup.recover_restore(control["job_id"], "test-stopped-worker-operator")
                assert recovered["state"] == "rolled_back"
                assert await db.assets.count_documents({"id": "reset-asset"}) == 1
                await assert_media([*kept.values(), removed])
                await login_works()
            else:
                raise AssertionError("Unknown scenario")
            print(json.dumps({"scenario": scenario, "passed": True}))
    finally:
        assert db.name == database_name and db.name.startswith("aman_ci_reset_")
        await client.drop_database(database_name)
        await redis_utils.tutup_client()
        client.close()


if __name__ == "__main__":
    asyncio.run(run())
