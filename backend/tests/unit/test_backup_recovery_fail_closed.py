"""Fault injection around actual archive builder and destructive restore paths."""
import asyncio
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import bcrypt
from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient

import routes.backup as rb
import pemeliharaan as pm
from backup_archive import iter_json_documents, validate_archive, write_manifest


_TEST_ADMIN = {"id": "operator-id", "username": "operator", "name": "Local test operator",
               "role": "admin", "kode_satker": "", "is_active": True,
               "created_at": "2026-10-15T00:00:00+00:00",
               "password": bcrypt.hashpw(b"Local-Only-Test123!", bcrypt.gensalt(rounds=4)).decode()}


def run(coro):
    return asyncio.run(coro)


class Download:
    def __init__(self, data):
        self.data, self.offset = data, 0
    async def readchunk(self):
        result = self.data[self.offset:self.offset + 1024]
        self.offset += len(result)
        return result
    async def close(self):
        return None


class Bucket:
    def __init__(self, database):
        self.db, self.data, self.fail_read, self.fail_write = database, {}, False, False
    async def open_download_stream(self, fid):
        if self.fail_read:
            raise IOError("injected source blob read failure")
        return Download(self.data[str(fid)])
    def open_upload_stream_with_id(self, fid, filename, metadata=None):
        outer = self
        class Upload:
            data = bytearray()
            def __init__(self):
                self.data = bytearray()
            async def write(self, chunk):
                if outer.fail_write:
                    raise IOError("injected target disk failure")
                self.data.extend(chunk)
            async def close(self):
                await outer.db["fs.files"].insert_one({"_id": fid, "filename": filename,
                                                     "metadata": metadata, "length": len(self.data)})
                outer.data[str(fid)] = bytes(self.data)
            async def abort(self):
                return None
        return Upload()


@pytest.fixture
def env(tmp_path, monkeypatch):
    database = AsyncMongoMockClient()["aman_backup_fault_test"]
    bucket = Bucket(database)
    monkeypatch.setattr(rb, "db", database)
    monkeypatch.setattr(rb, "fs_bucket", bucket)
    import db as db_module
    monkeypatch.setattr(db_module, "db", database)
    monkeypatch.setattr(rb, "BACKUP_TEMP_DIR", tmp_path / "temp")
    monkeypatch.setattr(rb, "BACKUP_ARSIP_DIR", tmp_path / "archive")
    monkeypatch.setattr(rb, "UPLOADS_DIR", tmp_path / "uploads")
    rb.BACKUP_TEMP_DIR.mkdir()
    rb.BACKUP_ARSIP_DIR.mkdir()
    rb.UPLOADS_DIR.mkdir()
    pm._cache = (0.0, False)
    import indexes
    import shared_utils
    async def noop(*args, **kwargs):
        return None
    monkeypatch.setattr(indexes, "create_indexes", noop)
    monkeypatch.setattr(indexes, "_KEGAGALAN_INDEKS", [])
    monkeypatch.setattr(shared_utils, "bersihkan_penanda_migrasi", noop)
    monkeypatch.setattr(shared_utils, "_CACHE_EPOCH_TTL", 0.0)
    monkeypatch.setattr(pm, "_CACHE_TTL", 0.0)
    async def seed():
        await database.assets.insert_one({"id": "original", "asset_name": "Before"})
        await database.users.insert_one(dict(_TEST_ADMIN))
        await database.categories.insert_one({"id": "category-original"})
        await database.inventory_activities.insert_one({"id": "activity-original"})
        await database.backup_jobs.insert_one({"job_id": "test-job", "type": "restore",
             "status": "queued", "active_lock": "GLOBAL", "updated_at": datetime.now(timezone.utc).isoformat()})
    run(seed())
    return database, bucket


def make_archive(path, missing=False, legacy=False, media=True):
    fid = "0123456789abcdef01234567"
    docs = {"assets": [{"id": "restored", "photo_gridfs_ids": [fid] if media else []}],
            "users": [{**_TEST_ADMIN, "id": "new-operator-id", "username": "new-operator"}], "categories": [],
            "inventory_activities": []}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, rows in docs.items():
            zf.writestr(name + ".json", json.dumps(rows))
        zf.writestr("metadata.json", json.dumps({"version": "legacy" if legacy else "3.5.0"}))
        if media:
            zf.writestr("gridfs/manifest.json", json.dumps([{"_id": fid, "length": 2048}]))
            if not missing:
                zf.writestr(f"gridfs/{fid}.bin", b"b" * 2048)
        zf.writestr("uploads/logo.txt", b"new logo")
        if not legacy:
            write_manifest(zf, {name: len(rows) for name, rows in docs.items()}, int(media), 1)
    return path


def test_missing_blob_is_rejected_before_any_live_wipe(env):
    database, _ = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", missing=True)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "failed"
    assert not run(database.restore_control.find_one({}))


def test_gridfs_snapshot_failure_aborts_before_wipe(env):
    database, bucket = env
    fid = ObjectId()
    run(database["fs.files"].insert_one({"_id": fid, "length": 10}))
    bucket.fail_read = True
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip")
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(rb.restore_control_status())["state"] == "aborted"
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "failed"


def test_media_failure_rolls_back_data_and_uploads_verified(env):
    database, bucket = env
    (rb.UPLOADS_DIR / "logo.txt").write_bytes(b"original logo")
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip")
    bucket.fail_write = True
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert not run(database.assets.find_one({"id": "restored"}))
    assert (rb.UPLOADS_DIR / "logo.txt").read_bytes() == b"original logo"
    assert run(rb.restore_control_status())["state"] == "rolled_back"
    job = run(database.backup_jobs.find_one({"job_id": "test-job"}))
    assert job["status"] == "failed" and job["recovery_required"] is False


def test_failed_rollback_keeps_both_artifacts_gate_and_operator_recovers(env):
    database, bucket = env
    fid = ObjectId()
    bucket.data[str(fid)] = b"old media"
    run(database["fs.files"].insert_one({"_id": fid, "length": 9}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip")
    bucket.fail_write = True  # Both source application AND old-media rollback fail.
    run(rb.run_restore_task("test-job", source, "operator"))
    control = run(rb.restore_control_status())
    assert control["state"] == "recovery_required"
    assert source.exists()
    assert (rb.BACKUP_TEMP_DIR / control["safety_artifact"]).exists()
    assert run(pm.pemeliharaan_aktif_uncached()) is True
    # Expired job lease must not open the dataset or allow a fresh restore.
    run(database.backup_jobs.update_one({"job_id": "test-job"}, {"$set": {
        "status": "running", "updated_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()}}))
    run(rb.cleanup_stale_jobs())
    assert run(pm.pemeliharaan_aktif_uncached()) is True
    for path in rb.BACKUP_TEMP_DIR.glob("*.zip"):
        import os
        os.utime(path, (1, 1))
    run(rb.cleanup_old_files())
    assert source.exists() and (rb.BACKUP_TEMP_DIR / control["safety_artifact"]).exists()
    bucket.fail_write = False
    result = run(rb.recover_restore("test-job", "operator-recovery"))
    assert result["state"] == "rolled_back"
    assert run(database.assets.find_one({"id": "original"}))
    assert bucket.data[str(fid)] == b"old media"
    assert run(pm.pemeliharaan_aktif_uncached()) is False


def test_legacy_archive_roundtrip_revokes_portal_and_preserves_local_control(env):
    database, _ = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", legacy=True, media=False)
    with zipfile.ZipFile(source, "a") as zf:
        zf.writestr("portal_pemegang_akses.json", json.dumps([{"id": "p", "aktif": True, "epoch": 4}]))
        zf.writestr("restore_control.json", json.dumps([{"_id": "GLOBAL", "state": "completed"}]))
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(rb.restore_control_status())["state"] == "completed"
    assert run(database.assets.find_one({"id": "restored"}))["version"] == 1
    assert run(database.portal_pemegang_akses.find_one({"id": "p"}))["aktif"] is False
    assert (rb.UPLOADS_DIR / "logo.txt").read_bytes() == b"new logo"


@pytest.mark.parametrize("failure", [PermissionError("injected move denied"), OSError(28, "injected disk full")])
def test_real_scheduler_archive_failure_retains_old_success_and_retention(env, monkeypatch, failure):
    database, _ = env
    run(database.backup_jobs.delete_many({}))
    run(database.report_settings.insert_one({"type": "backup_otomatis", "terakhir": "2026-10-15",
                                           "terakhir_sukses": "old-verified-success"}))
    old = rb.BACKUP_ARSIP_DIR / "backup_otomatis_20250101_000000.zip"
    old.write_bytes(b"old backup")
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(rb.shutil, "copyfile", fail)
    run(rb._jalankan_backup_otomatis(1))
    settings = run(database.report_settings.find_one({"type": "backup_otomatis"}))
    job = run(database.backup_jobs.find_one({"type": "backup"}))
    assert settings["status_terakhir"] == "gagal"
    assert settings["terakhir_sukses"] == "old-verified-success"
    assert job["download_ready"] is True and job["archive_state"] == "archive_failed"
    assert job["durable_verified"] is False and old.exists()
    assert (rb.BACKUP_TEMP_DIR / (job["job_id"] + ".zip")).exists()


def test_blob_read_failure_builder_never_creates_success(env):
    database, bucket = env
    fid = ObjectId()
    run(database["fs.files"].insert_one({"_id": fid, "length": 10}))
    bucket.fail_read = True
    run(rb.run_backup_task("test-job", "operator", arsipkan="otomatis"))
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "failed"
    assert not list(rb.BACKUP_ARSIP_DIR.iterdir())


def test_complete_archive_builder_and_scheduler_durable_success(env):
    database, _ = env
    run(database.backup_jobs.delete_many({}))
    run(rb._jalankan_backup_otomatis(2))
    job = run(database.backup_jobs.find_one({"type": "backup"}))
    assert job["durable_verified"] and job["archive_state"] == "archived"
    with zipfile.ZipFile(rb.BACKUP_ARSIP_DIR / job["arsip_nama"]) as zf:
        result = validate_archive(zf)
        assert result["manifest"]["complete"] is True
    assert run(database.report_settings.find_one({"type": "backup_otomatis"}))["terakhir_sukses"]


@pytest.mark.parametrize("body", [b'[{},]', b'[{"a":1}', b'[1]', b'[]{}', b'{}', b'[] trailing'])
def test_bounded_reader_rejects_invalid_or_partial_json(body):
    with pytest.raises(ValueError):
        list(iter_json_documents(io.BytesIO(body)))


def test_bounded_reader_supports_legacy_whitespace_and_rejects_large_document():
    assert list(iter_json_documents(io.BytesIO(b' [ {"id":"a"},\n {"id":"b"} ] \n'))) == [{"id":"a"}, {"id":"b"}]
    with pytest.raises(ValueError):
        list(iter_json_documents(io.BytesIO(json.dumps([{"data": "x" * 1000}]).encode()), max_document_chars=128))


def test_new_writer_request_registers_then_rechecks_uncached_gate(env, monkeypatch):
    database, _ = env
    # Legacy restore job from fixture is removed: simulate stale negative cache.
    run(database.backup_jobs.delete_many({}))
    pm._cache = (float("inf"), False)
    run(database.restore_control.insert_one({"_id": "GLOBAL", "state": "recovery_required"}))
    reached, messages = [], []
    async def app(scope, receive, send):
        reached.append(True)
    async def execute():
        async def receive():
            return {"type": "http.request"}
        async def send(msg):
            messages.append(msg)
        await pm.PemeliharaanMiddleware(app)({"type": "http", "method": "POST", "path": "/api/assets"}, receive, send)
    run(execute())
    assert not reached and messages[0]["status"] == 503
    assert run(database.restore_write_leases.count_documents({})) == 0


@pytest.mark.parametrize("bad_name", ["uploads/../../outside.txt", "/absolute.json", "uploads\\outside.txt"])
def test_preflight_rejects_unsafe_paths_before_wipe(env, bad_name):
    database, _ = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", legacy=True, media=False)
    with zipfile.ZipFile(source, "a") as zf:
        zf.writestr(bad_name, b"unsafe")
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert not run(rb.restore_control_status())


def test_preflight_rejects_modified_checksum_and_missing_new_manifest(env):
    source = make_archive(rb.BACKUP_TEMP_DIR / "modified.zip")
    # Rebuild without duplicate names, preserving old manifest to expose drift.
    target = rb.BACKUP_TEMP_DIR / "mutated.zip"
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w") as new:
        for info in old.infolist():
            data = old.read(info.filename)
            if info.filename == "uploads/logo.txt":
                data = b"changed bytes"
            new.writestr(info.filename, data)
    with zipfile.ZipFile(target) as zf, pytest.raises(ValueError, match="checksum"):
        validate_archive(zf)
    stripped = rb.BACKUP_TEMP_DIR / "stripped.zip"
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(stripped, "w") as new:
        for name in old.namelist():
            if name != "backup-manifest.json":
                data = old.read(name)
                if name == "metadata.json":
                    data = json.dumps({"version": "3.5.0", "archive_schema_version": 1}).encode()
                new.writestr(name, data)
    with zipfile.ZipFile(stripped) as zf, pytest.raises(ValueError, match="Manifest wajib"):
        validate_archive(zf)


def test_incomplete_manifest_never_reaches_wipe(env):
    database, _ = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "complete.zip")
    target = rb.BACKUP_TEMP_DIR / "incomplete.zip"
    with zipfile.ZipFile(source) as old, zipfile.ZipFile(target, "w") as new:
        for name in old.namelist():
            data = old.read(name)
            if name == "backup-manifest.json":
                manifest = json.loads(data)
                manifest["complete"] = False
                data = json.dumps(manifest).encode()
            new.writestr(name, data)
    run(rb.run_restore_task("test-job", target, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert not run(rb.restore_control_status())


def test_deploy_mutex_rejects_restore_control_claim(env):
    database, _ = env
    run(database.restore_control.insert_one({"_id": "GLOBAL", "state": "deploying", "owner": "deploy:1"}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip")
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(rb.restore_control_status())["state"] == "deploying"


def test_writer_drain_does_not_expire_a_paused_writer(env):
    database, _ = env
    run(database.restore_write_leases.insert_one({"_id": "paused-request",
         "expires_at": datetime.now(timezone.utc) - timedelta(days=1)}))
    with pytest.raises(RuntimeError, match="belum selesai"):
        run(rb._wait_writer_drain(timeout=-1))


def test_restore_reader_peak_memory_is_independent_of_collection_size(tmp_path):
    import tracemalloc
    path = tmp_path / "collection.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        with zf.open("assets.json", "w") as out:
            out.write(b"[")
            for index in range(5000):
                if index:
                    out.write(b",")
                out.write(json.dumps({"id": str(index), "data": "x" * 2000}).encode())
            out.write(b"]")
    with zipfile.ZipFile(path) as zf:
        tracemalloc.start()
        old = json.loads(zf.read("assets.json"))
        _, old_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert len(old) == 5000
        del old
        tracemalloc.start()
        with zf.open("assets.json") as fp:
            count = sum(1 for _ in iter_json_documents(fp))
        _, new_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    assert count == 5000 and new_peak * 5 < old_peak, (new_peak, old_peak)


def test_restore_projection_invalidation_is_awaited_and_forces_mongo(env, monkeypatch):
    database, _ = env
    import redis_utils as redis
    import shared_utils
    import meili_utils as meili
    class Redis:
        def __init__(self):
            self.values = {"aman:cache:stats:0:scope": json.dumps({"old": True})}
        async def get(self, key):
            return self.values.get(key)
        async def incr(self, key):
            self.values[key] = str(int(self.values.get(key, 0)) + 1)
            return int(self.values[key])
    fake = Redis()
    monkeypatch.setattr(redis, "REDIS_URL", "redis://isolated-test")
    monkeypatch.setattr(redis, "_get_client", lambda: fake)
    monkeypatch.setattr(meili, "db", database)
    monkeypatch.setattr(meili, "meili_aktif", lambda: True)
    monkeypatch.setattr(meili, "MEILI_SEARCH_SEMANTICS", "prefix_typo")
    shared_utils._CACHE_LOCAL["stats"]["scope"] = {"old": True}
    assert run(redis.redis_get("stats", "scope")) == {"old": True}
    run(database.meili_sync_state.insert_one({"_id": "assets", "complete": True,
        "completed_at": datetime.now(timezone.utc), "owner": "old-worker"}))
    run(rb._invalidate_restored_projections())
    assert run(redis.redis_get("stats", "scope")) is None
    assert not shared_utils._CACHE_LOCAL["stats"]
    state = run(database.meili_sync_state.find_one({"_id": "assets"}))
    assert state["force_mongo"] and not state["complete"] and "owner" not in state
    result = run(meili.kandidat_pencarian("assets", "synthetic query"))
    assert not result["usable"] and result["reason"] == "restore_requires_acknowledged_reindex"


def test_failed_strict_projection_invalidation_does_not_open_recovery_gate(env, monkeypatch):
    database, _ = env
    import redis_utils as redis
    class BrokenRedis:
        async def incr(self, key):
            raise IOError("injected Redis generation failure")
    monkeypatch.setattr(redis, "REDIS_URL", "redis://isolated-test")
    monkeypatch.setattr(redis, "_get_client", lambda: BrokenRedis())
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(rb.restore_control_status())["state"] == "recovery_required"
    assert (rb.BACKUP_TEMP_DIR / "safety_data_test-job.zip").exists()


@pytest.mark.parametrize("collection,status", [("background_jobs", "importing"), ("unduhan", "running")])
def test_detached_work_blocks_restore_drain_before_wipe(env, collection, status):
    database, _ = env
    run(database[collection].insert_one({"job_id": "live-worker", "status": status}))
    with pytest.raises(RuntimeError, match="belum selesai"):
        run(rb._wait_writer_drain(timeout=-1))


def test_background_writer_admission_is_held_for_entire_context_and_cleans_up(env):
    database, _ = env
    run(database.backup_jobs.delete_many({}))
    async def scenario():
        async with pm.writer_admission(database=database):
            assert await database.restore_write_leases.count_documents({}) == 1
        assert await database.restore_write_leases.count_documents({}) == 0
        await database.restore_control.insert_one({"_id": "GLOBAL", "state": "deploying"})
        with pytest.raises(Exception) as caught:
            async with pm.writer_admission(database=database):
                pytest.fail("blocked writer entered")
        assert caught.value.status_code == 503
        assert await database.restore_write_leases.count_documents({}) == 0
    run(scenario())


def test_job_completion_failure_rolls_back_before_control_can_be_terminal(env, monkeypatch):
    database, _ = env
    original = rb.update_job
    fired = False
    async def fail_completion(job_id, **fields):
        nonlocal fired
        if fields.get("status") == "completed" and not fired:
            fired = True
            raise IOError("injected job receipt persistence failure")
        await original(job_id, **fields)
    monkeypatch.setattr(rb, "update_job", fail_completion)
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(rb.restore_control_status())["state"] == "rolled_back"


def test_legacy_without_gridfs_references_restores_empty_media_set(env):
    database, bucket = env
    fid = ObjectId()
    bucket.data[str(fid)] = b"old private photo"
    run(database["fs.files"].insert_one({"_id": fid, "length": len(bucket.data[str(fid)])}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", legacy=True, media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(rb.restore_control_status())["state"] == "completed"
    assert run(database["fs.files"].count_documents({})) == 0
    assert run(database["fs.chunks"].count_documents({})) == 0


def test_unknown_incomplete_control_can_never_be_overwritten_by_new_restore(env):
    database, _ = env
    run(database.restore_control.insert_one({"_id": "GLOBAL", "destructive_started": True}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(rb.restore_control_status())["destructive_started"] is True
    assert "state" not in run(rb.restore_control_status())


def test_epoch_rotation_failure_releases_only_preflight_claim_without_wipe(env, monkeypatch):
    database, _ = env
    import dataset_epoch
    async def fail(*args, **kwargs):
        raise IOError("injected generation persistence error")
    monkeypatch.setattr(dataset_epoch, "rotate_generation", fail)
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    control = run(rb.restore_control_status())
    assert control["state"] == "aborted" and not control["destructive_started"]


def test_historical_deleted_media_references_do_not_make_current_backup_incomplete(env):
    database, _ = env
    run(database.audit_logs.insert_one({"id": "history", "before": {
        "photo_gridfs_ids": ["deleted-historical-blob"], "dok_file_id": "deleted-doc"}}))
    run(database.inventory_history.insert_one({"id": "history", "asset_snapshot": {
        "document_checklist": [{"documents": [{"gridfs_id": "old-removed-blob"}]}]}}))
    run(rb.run_backup_task("test-job", "operator"))
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "completed"


@pytest.mark.parametrize("collection,document", [
    ("signature_requests", {"id": "sr", "dok_file_id": "missing-document"}),
    ("signature_requests", {"id": "sr", "signers": [{"signature_file_id": "missing-signature"}]}),
    ("report_settings", {"kasatker_ttd_file_id": "missing-specimen"}),
    ("bast_serah_terima", {"id": "bast", "bukti": {"file_id": "missing-evidence"}}),
    ("bast_serah_terima", {"id": "bast", "dokumen_akhir": [{"file_id": "missing-final"}]}),
    ("pengadaan", {"id": "purchase", "lampiran_berkas": [{"file_id": "missing-attachment"}]}),
    ("spasial_node", {"id": "map", "properties": {"denah_overlay": {"file_id": "missing-overlay"}}}),
])
def test_live_current_signature_and_other_media_owners_require_blob(env, collection, document):
    database, _ = env
    run(database[collection].insert_one(document))
    run(rb.run_backup_task("test-job", "operator"))
    job = run(database.backup_jobs.find_one({"job_id": "test-job"}))
    assert job["status"] == "failed" and "Referensi GridFS tanpa blob" in job["error"]


def test_legacy_download_jobs_are_ignored_without_reviving_claims_or_string_ttl(env):
    database, bucket = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", legacy=True, media=True)
    fid = "0123456789abcdef01234567"
    with zipfile.ZipFile(source, "a") as zf:
        zf.writestr("unduhan.json", json.dumps([{
            "unduhan_id": "archived-download", "status": "running", "active_lock": True,
            "dibuat_oleh": "old-owner", "artifact_id": fid,
            "created_at": "2024-01-01T00:00:00Z", "hapus_pada": "2024-01-02T00:00:00Z",
        }]))
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(rb.restore_control_status())["state"] == "completed"
    assert run(database.unduhan.count_documents({})) == 0
    assert run(database["fs.files"].count_documents({"_id": ObjectId(fid)})) == 1
    assert bucket.data[fid] == b"b" * 2048


def test_backup_excludes_download_job_metadata_but_keeps_gridfs_bytes(env):
    database, bucket = env
    fid = ObjectId()
    bucket.data[str(fid)] = b"download artifact bytes"
    run(database["fs.files"].insert_one({"_id": fid, "length": len(bucket.data[str(fid)]),
                                        "metadata": {"unduhan_id": "job-current"}}))
    run(database.unduhan.insert_one({"unduhan_id": "job-current", "status": "done",
                                    "artifact_id": str(fid), "created_at": datetime.now(timezone.utc)}))
    run(rb.run_backup_task("test-job", "operator"))
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "completed"
    with zipfile.ZipFile(rb.BACKUP_TEMP_DIR / "test-job.zip") as zf:
        assert "unduhan.json" not in zf.namelist()
        assert zf.read(f"gridfs/{fid}.bin") == b"download artifact bytes"


def replace_users_archive(path, users):
    rebuilt = path.with_name("rebuilt-" + path.name)
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(rebuilt, "w") as target:
        for name in source.namelist():
            target.writestr(name, json.dumps(users).encode() if name == "users.json" else source.read(name))
    return rebuilt


@pytest.mark.parametrize("users", [
    [], [{"username": "admin"}],
    [{**_TEST_ADMIN, "is_active": False}],
    [{**_TEST_ADMIN, "role": "operator", "_super_admin_asli": True}],
    [{**_TEST_ADMIN, "kode_satker": "111111", "_super_admin_asli": True}],
    [{**_TEST_ADMIN, "password": "not-a-bcrypt-hash"}],
    [{**_TEST_ADMIN, "id": ""}],
    [{**_TEST_ADMIN, "username": " cannot-login-with-whitespace "}],
    [{key: value for key, value in _TEST_ADMIN.items() if key != "password"}],
    [{key: value for key, value in _TEST_ADMIN.items() if key != "name"}],
    [{key: value for key, value in _TEST_ADMIN.items() if key != "created_at"}],
    [{**_TEST_ADMIN, "login_terkunci_hingga": "2100-01-01T00:00:00+00:00"}],
])
def test_restore_without_usable_persisted_central_admin_is_rejected_before_wipe(env, users):
    database, _ = env
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", legacy=True, media=False)
    source = replace_users_archive(source, users)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(database.users.find_one({"username": "operator"}))["password"] == _TEST_ADMIN["password"]
    assert not run(rb.restore_control_status())
    job = run(database.backup_jobs.find_one({"job_id": "test-job"}))
    assert job["status"] == "failed" and "admin pusat aktif" in job["error"]


def test_safety_without_usable_admin_aborts_before_first_wipe(env):
    database, _ = env
    run(database.users.update_many({}, {"$set": {"is_active": False}}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(database.assets.find_one({"id": "original"}))
    assert run(rb.restore_control_status())["state"] == "aborted"
    assert not run(rb.restore_control_status())["destructive_started"]


def test_applied_auth_invariant_failure_rolls_back_before_opening_or_deleting_safety(env, monkeypatch):
    database, _ = env
    original = rb._apply_archive
    fired = False
    async def lose_admin(zf, job_id):
        nonlocal fired
        result = await original(zf, job_id)
        if not fired:
            fired = True
            await database.users.update_many({}, {"$set": {"is_active": False}})
        return result
    monkeypatch.setattr(rb, "_apply_archive", lose_admin)
    source = make_archive(rb.BACKUP_TEMP_DIR / "restore_test-job.zip", media=False)
    run(rb.run_restore_task("test-job", source, "operator"))
    assert run(rb.restore_control_status())["state"] == "rolled_back"
    assert run(database.users.find_one({"username": "operator"}))["is_active"] is True
    assert run(database.backup_jobs.find_one({"job_id": "test-job"}))["status"] == "failed"


def test_fresh_install_builder_exports_required_empty_collections_and_can_restore_itself(env):
    database, _ = env
    for collection in ("assets", "categories", "inventory_activities"):
        run(database.drop_collection(collection))
    run(rb.run_backup_task("test-job", "operator"))
    job = run(database.backup_jobs.find_one({"job_id": "test-job"}))
    assert job["status"] == "completed"
    path = rb.BACKUP_TEMP_DIR / "test-job.zip"
    with zipfile.ZipFile(path) as zf:
        result = validate_archive(zf)
        for name in ("assets", "categories", "inventory_activities"):
            assert result["collections"][name] == 0
            assert json.loads(zf.read(name + ".json")) == []
    run(rb.run_restore_task("test-job", path, "operator"))
    assert run(rb.restore_control_status())["state"] == "completed"
    assert run(database.users.find_one({"username": "operator"}))["password"] == _TEST_ADMIN["password"]


def test_reset_can_exclude_only_its_own_admitted_writer_lease(env):
    database, _ = env
    run(database.backup_jobs.delete_many({}))
    async def scenario():
        async with pm.writer_admission(database=database) as own_lease:
            assert pm.current_writer_lease_id() == own_lease
            await rb._wait_writer_drain(timeout=-1, exclude_lease_id=pm.current_writer_lease_id())
            await database.restore_write_leases.insert_one({"_id": "someone-else"})
            with pytest.raises(RuntimeError, match="belum selesai"):
                await rb._wait_writer_drain(timeout=-1, exclude_lease_id=own_lease)
            await database.restore_write_leases.delete_one({"_id": "someone-else"})
        assert pm.current_writer_lease_id() is None
    run(scenario())


def test_reset_preserve_master_collections_keeps_live_bson_types_and_identity(env):
    database, _ = env
    original_id = ObjectId()
    bson_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    run(database.report_settings.insert_one({"_id": original_id, "type": "master", "created_at": bson_date}))
    source = make_archive(rb.BACKUP_TEMP_DIR / "preserve.zip", legacy=True, media=False)
    with zipfile.ZipFile(source, "a") as zf:
        zf.writestr("report_settings.json", json.dumps([{"type": "master", "created_at": "different-string"}]))
    with zipfile.ZipFile(source) as zf:
        stats, _, _ = run(rb._apply_archive(zf, "test-job", preserve_collections={"users", "report_settings"}))
    actual = run(database.report_settings.find_one({"type": "master"}))
    assert actual["_id"] == original_id and isinstance(actual["created_at"], datetime)
    assert stats["report_settings"] == 1
    assert run(database.users.find_one({"username": "operator"}))["password"] == _TEST_ADMIN["password"]
    assert run(database.assets.find_one({"id": "restored"}))
