"""Fault injection for checksum storage, ownership, cleanup and bounded backfill."""
import asyncio
import base64
import copy
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
import pytest
import checklist_storage as cs

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jhV8AAAAASUVORK5CYII=")
SIGNED = b"%PDF-1.7\n/ByteRange [0 10 20 30] /Contents <c0ffee>\nexact signed bytes\n%%EOF"


def data(raw, kind):
    return "data:" + kind + ";base64," + base64.b64encode(raw).decode()


def items():
    return [{"name": "STNK", "checked": True, "photos": [data(PNG, "image/png")],
             "documents": [{"name": "signed.pdf", "data": data(SIGNED, "application/pdf")}]}]


class Stream:
    def __init__(self, raw):
        self.raw, self.offset = raw, 0
    async def readchunk(self):
        value = self.raw[self.offset:self.offset + 1024]
        self.offset += len(value)
        return value
    async def close(self):
        return None


class Bucket:
    def __init__(self, db):
        self.db, self.values, self.fail_after = db, {}, None
    async def upload_from_stream_with_id(self, gid, name, raw, metadata):
        if self.fail_after is not None and len(self.values) >= self.fail_after:
            raise IOError("injected upload failure")
        self.values[str(gid)] = raw
        await self.db["fs.files"].insert_one({"_id": gid, "length": len(raw), "metadata": metadata,
            "uploadDate": datetime.now(timezone.utc), "filename": name})
    async def open_download_stream(self, gid):
        return Stream(self.values[str(gid)])
    async def delete(self, gid):
        self.values.pop(str(gid), None)
        await self.db["fs.files"].delete_one({"_id": gid})


@pytest.fixture
def storage():
    database = AsyncMongoMockClient()["checklist_test"]
    return database, Bucket(database)


def run(coroutine):
    return asyncio.run(coroutine)


def test_normalize_stable_ids_ref_sentinels_duplicate_names_bad_legacy():
    previous = [None, "bad", {"id": "first", "name": "STNK", "photo_gridfs_ids": ["gid1"],
        "documents": [{"id": "doc1", "name": "signed.pdf", "gridfs_id": "docgid", "sha256": "digest"}]},
        {"id": "second", "name": "STNK", "photos": ["bytes"]}]
    result = cs.normalize_checklist([
        {"id": "second", "name": "Renamed", "photos": ["__existing__:0"]},
        {"name": "STNK", "photos": ["__existing__:0"], "documents": [{"data": "__existing__:0"}]}], previous)
    assert result[0]["id"] == "second" and result[0]["photos"] == ["bytes"]
    assert result[1]["id"] == "first" and result[1]["photo_gridfs_ids"] == ["gid1"]
    assert result[1]["photos"] == []
    assert result[1]["documents"][0] == previous[2]["documents"][0]
    with pytest.raises(HTTPException) as bad:
        cs.normalize_checklist([{"name": "A", "id": {"bad": "x"}}])
    assert bad.value.status_code == 400


def test_flag_default_off_no_files_and_preserves_inline(storage, monkeypatch):
    monkeypatch.delenv("AMAN_CHECKLIST_GRIDFS_WRITE", raising=False)
    database, bucket = storage
    prepared = run(cs.prepare_checklist(items(), "asset", database, bucket))
    assert prepared.created_ids == [] and bucket.values == {}
    assert prepared.items[0]["documents"][0]["data"] == items()[0]["documents"][0]["data"]
    assert prepared.items[0]["id"] and prepared.items[0]["documents"][0]["id"]


def test_staging_exact_signed_pdf_hash_hydration_and_owner_isolation(storage):
    database, bucket = storage
    prepared = run(cs.prepare_checklist(items(), "asset", database, bucket, store=True))
    assert len(prepared.created_ids) == 2
    item = prepared.items[0]
    assert item["photos"] == [] and item["documents"][0]["data"] == ""
    assert bucket.values[item["documents"][0]["gridfs_id"]] == SIGNED
    asset = {"id": "asset", "document_checklist": prepared.items}
    hydrated = run(cs.hydrate_checklist(asset, database, bucket))
    assert cs.decode_inline(hydrated[0]["photos"][0]) == PNG
    assert cs.decode_inline(hydrated[0]["documents"][0]["data"]) == SIGNED
    with pytest.raises(HTTPException) as other:
        run(cs.read_media({**asset, "id": "another"}, 0, 0, "document", database, bucket))
    assert other.value.status_code == 409
    bucket.values[item["documents"][0]["gridfs_id"]] = SIGNED[:-1] + b"!"
    with pytest.raises(HTTPException) as corrupted:
        run(cs.read_media(asset, 0, 0, "document", database, bucket))
    assert corrupted.value.status_code == 503


def test_owned_reference_never_bypasses_new_pdf_validation(storage):
    database, bucket = storage
    prepared = run(cs.prepare_checklist(items(), "asset", database, bucket, store=True))
    changed = copy.deepcopy(prepared.items)
    changed[0]["documents"][0]["data"] = data(b"not a PDF", "application/pdf")
    with pytest.raises(HTTPException) as invalid:
        run(cs.prepare_checklist(changed, "asset", database, bucket, existing=prepared.items, store=False))
    assert invalid.value.status_code == 400 and len(bucket.values) == 2


def test_large_pdf_storage_keeps_asset_document_small_and_exact(storage):
    from bson import BSON
    database, bucket = storage
    raw = SIGNED + b"x" * (2 * 1024 * 1024)
    original = [{"name": "Signed", "documents": [{"name": "signed.pdf", "data": data(raw, "application/pdf")}]}]
    prepared = run(cs.prepare_checklist(original, "asset", database, bucket, store=True))
    assert len(BSON.encode({"document_checklist": prepared.items})) < len(BSON.encode({"document_checklist": original})) // 100
    assert bucket.values[prepared.created_documents[0]] == raw


def test_partial_staging_failure_discards_only_allocated_files(storage):
    database, bucket = storage
    bucket.fail_after = 1
    with pytest.raises(IOError):
        run(cs.prepare_checklist(items(), "asset", database, bucket, store=True))
    assert bucket.values == {} and run(database["fs.files"].count_documents({})) == 0


def test_uncertain_commit_cleanup_retains_committed_references(storage):
    database, bucket = storage
    prepared = run(cs.prepare_checklist(items(), "asset", database, bucket, store=True))
    run(database.assets.insert_one({"id": "asset", "document_checklist": prepared.items}))
    run(cs.discard_staged(bucket, prepared, database=database, asset_id="asset"))
    assert len(bucket.values) == 2
    run(database.assets.delete_one({"id": "asset"}))
    run(cs.discard_staged(bucket, prepared, database=database, asset_id="asset"))
    assert bucket.values == {}


def test_backfill_dry_run_cas_and_inline_retention(storage):
    database, bucket = storage
    run(database.assets.insert_one({"id": "asset", "version": 1, "document_checklist": items()}))
    assert run(cs.backfill_asset(database, bucket, "asset"))["dry_run"] is True
    assert bucket.values == {}
    result = run(cs.backfill_asset(database, bucket, "asset", dry_run=False))
    assert result["inline_retained"] and result["created_files"] == 2
    saved = run(database.assets.find_one({"id": "asset"}))
    assert saved["version"] == 2 and saved["document_checklist"][0]["photos"] == items()[0]["photos"]
    assert saved["document_checklist"][0]["documents"][0]["data"] == items()[0]["documents"][0]["data"]
    assert run(database.restore_write_leases.count_documents({})) == 0


def test_backfill_cas_loser_retains_concurrent_data_discards_new_files(storage, monkeypatch):
    database, bucket = storage
    run(database.assets.insert_one({"id": "asset", "version": 1, "document_checklist": items()}))
    original = cs.prepare_checklist
    async def raced(*args, **kwargs):
        prepared = await original(*args, **kwargs)
        await database.assets.update_one({"id": "asset"}, {
            "$inc": {"version": 1}, "$set": {"notes": "concurrent"}})
        return prepared
    monkeypatch.setattr(cs, "prepare_checklist", raced)
    with pytest.raises(HTTPException) as conflict:
        run(cs.backfill_asset(database, bucket, "asset", dry_run=False))
    assert conflict.value.status_code == 409
    saved = run(database.assets.find_one({"id": "asset"}))
    assert saved["notes"] == "concurrent" and saved["document_checklist"] == items()
    assert bucket.values == {}


def test_uncertain_inner_task_retains_physical_no_ttl_lease(storage):
    import pemeliharaan as pm
    database, _ = storage
    async def scenario():
        async with pm.writer_admission(database=database) as lease_id:
            await asyncio.create_task(pm.mark_current_writer_uncertain("checklist_backfill"))
        lease = await database.restore_write_leases.find_one({"_id": lease_id})
        assert lease["kind"] == "background" and lease["status"] == "uncertain_write"
        assert lease["uncertainty_reason"] == "checklist_backfill" and "expires_at" not in lease
        assert pm.current_writer_lease_id() is None
    run(scenario())


def test_uncertainty_metadata_failure_never_removes_physical_admission(storage):
    import pemeliharaan as pm
    database, _ = storage
    class Leases:
        async def insert_one(self, *args, **kwargs):
            return await database.restore_write_leases.insert_one(*args, **kwargs)
        async def update_one(self, *args, **kwargs):
            raise IOError("injected metadata outage")
        async def delete_one(self, *args, **kwargs):
            return await database.restore_write_leases.delete_one(*args, **kwargs)
    class Database:
        restore_write_leases = Leases()
        def __getattr__(self, name):
            return getattr(database, name)
    async def scenario():
        async with pm.writer_admission(database=Database()) as lease_id:
            assert not await pm.mark_current_writer_uncertain("checklist_backfill")
        assert await database.restore_write_leases.find_one({"_id": lease_id})
    run(scenario())


def test_pre_dispatch_validation_error_releases_admission_and_bad_reason_rejected(storage):
    import pemeliharaan as pm
    database, _ = storage
    async def scenario():
        with pytest.raises(HTTPException):
            async with pm.writer_admission(database=database):
                raise HTTPException(400, "pre-dispatch invalid input")
        assert await database.restore_write_leases.count_documents({}) == 0
        async with pm.writer_admission(database=database):
            with pytest.raises(ValueError):
                await pm.mark_current_writer_uncertain("arbitrary user content")
        assert await database.restore_write_leases.count_documents({}) == 0
    run(scenario())


def test_operator_lease_release_requires_stopped_writers_and_verified_mongo_outcomes(storage, monkeypatch, capsys):
    from types import SimpleNamespace
    import restore_recovery
    import db as db_module
    database, _ = storage
    monkeypatch.setattr(db_module, "db", database)
    run(database.restore_write_leases.insert_many([{"_id": "one"}, {"_id": "two"}]))
    args = SimpleNamespace(action="release-writer-lease", lease_id="one", workers_stopped=True,
                           mongo_outcomes_verified=False)
    with pytest.raises(SystemExit, match="mongo-outcomes-verified"):
        run(restore_recovery.main(args))
    assert run(database.restore_write_leases.count_documents({})) == 2
    args.mongo_outcomes_verified = True
    run(restore_recovery.main(args))
    assert run(database.restore_write_leases.find_one({"_id": "two"}))
    assert not run(database.restore_write_leases.find_one({"_id": "one"}))
    assert '"cleared_writer_leases": 1' in capsys.readouterr().out


def test_gc_dry_run_all_owner_collections_history_grace_incomplete(storage):
    database, bucket = storage
    prepared = run(cs.prepare_checklist(items(), "asset", database, bucket, store=True))
    past = datetime.now(timezone.utc) - timedelta(days=10)
    run(database["fs.files"].update_many({}, {"$set": {"uploadDate": past}}))
    gid = prepared.created_documents[0]
    run(database.historical_unknown_module.insert_one({"before": {"url": "https://example/" + gid}}))
    report = run(cs.orphan_report(database))
    assert report["complete"] and report["dry_run"]
    assert next(item for item in report["candidates"] if item["gridfs_id"] == gid)["owner_documents"] == 1
    run(cs.retire_if_managed(database, prepared.created_photos[0]))
    assert len(run(cs.orphan_report(database))["candidates"]) == 1
    run(database.other.insert_many([{"x": 1}, {"x": 2}]))
    incomplete = run(cs.orphan_report(database, max_documents=1))
    assert not incomplete["complete"]
    assert all(not item["eligible_for_operator_review"] for item in incomplete["candidates"])
    assert len(bucket.values) == 2
