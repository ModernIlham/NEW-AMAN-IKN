"""Offline DR provider stays disabled; exercise actual encryption and fake IO."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import builtins
from pathlib import Path
from types import SimpleNamespace
import zipfile
import sys

import pytest
import bcrypt
from cryptography.exceptions import InvalidTag
from mongomock_motor import AsyncMongoMockClient

import backup_dr as dr
from backup_archive import write_manifest, validate_archive


_TEST_ADMIN = {"id": "operator-id", "username": "operator", "role": "admin",
               "name": "Local test operator", "created_at": "2026-10-15T00:00:00+00:00",
               "password": bcrypt.hashpw(b"Local-Only-Test123!", bcrypt.gensalt(rounds=4)).decode()}


@pytest.fixture(autouse=True)
def machine_identity(monkeypatch):
    monkeypatch.setattr(dr, "machine_fingerprint", lambda: "a" * 64)


def escrow(key=b"k" * 32):
    return dr.escrow_attestation(key, "a" * 64, escrow_machine="b" * 64)


def archive(path):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps({"version": "3.5.0", "archive_schema_version": 1}))
        zf.writestr("assets.json", '[{"id":"synthetic"}]')
        zf.writestr("users.json", json.dumps([_TEST_ADMIN]))
        zf.writestr("categories.json", "[]")
        zf.writestr("inventory_activities.json", "[]")
        zf.writestr("gridfs/manifest.json", "[]")
        write_manifest(zf, {"assets": 1, "users": 1, "categories": 0, "inventory_activities": 0}, 0, 0)
    return path


def test_streaming_encryption_roundtrip_tampering_and_key_permission(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"synthetic" * 100000)
    encrypted = tmp_path / "encrypted.aman"
    keyfile = tmp_path / "key"
    keyfile.write_bytes(b"k" * 32)
    keyfile.chmod(0o644)
    with pytest.raises(ValueError, match="privat"):
        dr.load_key(keyfile)
    keyfile.chmod(0o600)
    key = dr.load_key(keyfile)
    dr.encrypt_file(source, encrypted, key)
    restored = tmp_path / "restored.bin"
    assert dr.decrypt_file(encrypted, restored, key) == dr.file_sha256(source)
    assert restored.read_bytes() == source.read_bytes()
    data = bytearray(encrypted.read_bytes())
    data[len(dr.MAGIC) + 30] ^= 1
    encrypted.write_bytes(data)
    with pytest.raises(InvalidTag):
        dr.decrypt_file(encrypted, tmp_path / "corrupt.bin", key)
    assert not (tmp_path / "corrupt.bin").exists()
    assert not (tmp_path / "corrupt.bin.decrypting").exists()


def test_encryption_never_overwrites_or_deletes_preexisting_target(tmp_path):
    source, target = tmp_path / "source", tmp_path / "target"
    source.write_bytes(b"source")
    target.write_bytes(b"must survive")
    with pytest.raises(FileExistsError):
        dr.encrypt_file(source, target, b"k" * 32)
    assert target.read_bytes() == b"must survive"


@pytest.mark.parametrize("invalid", ["destination", "archive", "receipt_parent"])
def test_upload_cli_rejects_local_configuration_before_sdk_credential_discovery(tmp_path, monkeypatch, invalid):
    import backup_dr_cli as cli
    source = archive(tmp_path / "backup.zip")
    key = tmp_path / "key"
    key.write_bytes(b"k" * 32)
    key.chmod(0o600)
    proof = tmp_path / "escrow.json"
    proof.write_text(json.dumps(escrow()))
    destination = "s3://test-bucket/isolated-prefix"
    receipt = tmp_path / "receipt.json"
    if invalid == "destination":
        destination = "s3://test-bucket"
    elif invalid == "archive":
        source.write_bytes(b"invalid archive")
    else:
        receipt = tmp_path / "missing" / "receipt.json"
    original_import = builtins.__import__
    def guarded_import(name, *args, **kwargs):
        if name == "boto3" or name.startswith("boto3."):
            raise AssertionError("SDK discovery must not run for invalid local input")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(sys, "argv", ["backup_dr_cli", "upload", "--archive", str(source),
        "--destination", destination, "--key-file", str(key), "--receipt", str(receipt),
        "--escrow-attestation", str(proof)])
    with pytest.raises((ValueError, zipfile.BadZipFile, FileNotFoundError)):
        cli.main()
    assert not receipt.exists()


class FakeS3:
    def __init__(self, tamper=False, fail_head=False):
        self.objects, self.metadata, self.tamper, self.fail_head = {}, {}, tamper, fail_head
    def upload_file(self, path, bucket, key, ExtraArgs):
        self.objects[(bucket, key)] = Path(path).read_bytes()
        self.metadata[(bucket, key)] = ExtraArgs["Metadata"]
    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[(Bucket, Key)]) + int(self.fail_head),
                "Metadata": self.metadata[(Bucket, Key)]}
    def download_file(self, bucket, key, target):
        data = self.objects[(bucket, key)]
        Path(target).write_bytes(data + b"tampered" if self.tamper else data)


def test_offsite_adapter_only_reports_success_after_full_readback_and_decryption(tmp_path):
    source = archive(tmp_path / "backup.zip")
    result = dr.verified_offsite_upload(source, b"k" * 32, "s3://test-bucket/isolated-prefix", FakeS3(), escrow=escrow())
    assert result["uploaded_verified"] is True
    assert result["source_independent_restore_drill"] is False
    assert result["consistency"] == "application_best_effort"
    assert result["destination"].startswith("s3://test-bucket/isolated-prefix/")


@pytest.mark.parametrize("kwargs", [{"tamper": True}, {"fail_head": True}])
def test_offsite_corrupt_readback_or_size_never_success(tmp_path, kwargs):
    with pytest.raises(ValueError):
        dr.verified_offsite_upload(archive(tmp_path / "backup.zip"), b"k" * 32,
                                  "s3://test-bucket/isolated-prefix", FakeS3(**kwargs), escrow=escrow())


@pytest.mark.parametrize("value", ["https://bucket/x", "s3://bucket", "s3://bucket/a/../b", "s3://bucket/key?secret=x"])
def test_offsite_destination_requires_explicit_dedicated_prefix(value):
    with pytest.raises(ValueError):
        dr.parse_s3_destination(value)


@pytest.fixture
def offline(tmp_path, monkeypatch):
    import db as module_db
    import routes.backup as rb
    database = AsyncMongoMockClient()["aman_ci_dr_test"]
    async def seed_admin():
        await database.users.insert_one({"id": "operator", "username": "operator", "role": "admin",
            "name": "Local test operator", "created_at": "2026-10-15T00:00:00+00:00",
            "password": bcrypt.hashpw(b"Local-Only-Test123!", bcrypt.gensalt(rounds=4)).decode()})
    asyncio.run(seed_admin())
    monkeypatch.setattr(module_db, "db", database)
    monkeypatch.setattr(rb, "db", database)
    monkeypatch.setattr(rb, "UPLOADS_DIR", tmp_path / "uploads")
    rb.UPLOADS_DIR.mkdir()
    (rb.UPLOADS_DIR / "logo.txt").write_bytes(b"synthetic")
    class Admin:
        def __init__(self):
            self.commands = []
        async def command(self, command):
            self.commands.append(command)
            if "currentOp" in command:
                return {"fsyncLock": False}
            return {"lockCount": 0 if "fsyncUnlock" in command else 1}
    admin = Admin()
    monkeypatch.setattr(module_db, "client", SimpleNamespace(admin=admin))
    async def export(zf, progress_cb=None):
        zf.writestr("gridfs/manifest.json", "[]")
        return 0
    monkeypatch.setattr(rb, "export_gridfs", export)
    inventory = tmp_path / "writers.json"
    inventory.write_text(json.dumps({"all_writers_enumerated": True,
        "supervisor_services": ["inventarisasi-backend"], "external_upload_writers": []}))
    def runner(*args, **kwargs):
        return SimpleNamespace(stdout="inventarisasi-backend STOPPED Oct 15 10:00:00", returncode=3)
    return database, admin, inventory, runner


def test_offline_snapshot_is_readonly_under_owned_lock_and_publishes_verified_class(offline, tmp_path):
    database, admin, inventory, runner = offline
    asyncio.run(database.assets.insert_one({"id": "synthetic"}))
    output = tmp_path / "snapshot.zip"
    result = asyncio.run(dr.offline_snapshot(output, ["inventarisasi-backend"], inventory, runner))
    assert result["snapshot_verified"] and result["consistency"] == dr.CONSISTENCY
    assert admin.commands == [{"currentOp": 1}, {"fsync": 1, "lock": True}, {"fsyncUnlock": 1}]
    with zipfile.ZipFile(output) as zf:
        assert validate_archive(zf, required=False)["manifest"]["consistency"] == dr.CONSISTENCY
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "completed"


def test_offline_snapshot_failure_releases_only_its_lock_and_leaves_no_valid_zip(offline, tmp_path, monkeypatch):
    database, admin, inventory, runner = offline
    import routes.backup as rb
    async def fail(*args, **kwargs):
        raise IOError("injected media read failure")
    monkeypatch.setattr(rb, "export_gridfs", fail)
    output = tmp_path / "snapshot.zip"
    with pytest.raises(IOError):
        asyncio.run(dr.offline_snapshot(output, ["inventarisasi-backend"], inventory, runner))
    assert admin.commands[-1] == {"fsyncUnlock": 1}
    assert not output.exists()
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "aborted"


def test_running_writer_services_prevent_lock_and_snapshot(offline, tmp_path):
    _, admin, inventory, _ = offline
    def running(*args, **kwargs):
        return SimpleNamespace(stdout="inventarisasi-backend RUNNING pid 1", returncode=0)
    with pytest.raises(RuntimeError, match="STOPPED"):
        asyncio.run(dr.offline_snapshot(tmp_path / "snapshot.zip", ["inventarisasi-backend"], inventory, running))
    assert not admin.commands


def test_stale_receipt_check_is_not_satisfied_by_failed_or_old_upload():
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    fresh = {"uploaded_verified": True, "key_escrow_verified": True, "verified_at": (now - timedelta(hours=2)).isoformat()}
    assert dr.receipt_freshness(fresh, now=now)["fresh"]
    assert not dr.receipt_freshness({**fresh, "uploaded_verified": False}, now=now)["fresh"]
    assert not dr.receipt_freshness({**fresh, "verified_at": (now - timedelta(hours=25)).isoformat()}, now=now)["fresh"]
    assert not dr.receipt_freshness({}, now=now)["fresh"]


def test_missing_or_wrong_escrow_attestation_blocks_before_provider_io(tmp_path):
    class NoProvider:
        def __getattr__(self, name):
            pytest.fail("Provider must not be touched before escrow verification")
    source = archive(tmp_path / "archive.zip")
    for proof in (None, {**escrow(), "key_fingerprint": "0" * 64}, escrow(b"j" * 32)):
        with pytest.raises(ValueError):
            dr.verified_offsite_upload(source, b"k" * 32, "s3://test-bucket/private-prefix", NoProvider(), escrow=proof)


def test_escrow_receipt_requires_different_machine_and_rejects_stale_or_tampered_proof():
    now = datetime(2026, 10, 15, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        dr.escrow_attestation(b"k" * 32, "a" * 64)  # Same actual host.
    proof = dr.escrow_attestation(b"k" * 32, "a" * 64, escrow_machine="b" * 64, now=now)
    assert dr.validate_escrow_attestation(b"k" * 32, proof, now=now)["escrow_machine"] == "b" * 64
    for invalid in ({**proof, "proof": "0" * 64}, {**proof, "escrow_machine": "a" * 64}):
        with pytest.raises(ValueError):
            dr.validate_escrow_attestation(b"k" * 32, invalid, now=now)
    with pytest.raises(ValueError):
        dr.validate_escrow_attestation(b"k" * 32, proof, now=now + timedelta(days=366))


def test_unknown_fsync_acquire_outcome_keeps_gate_and_never_speculatively_unlocks(offline, tmp_path):
    database, admin, inventory, runner = offline
    original = admin.command
    async def lost(command):
        if "fsync" in command:
            admin.commands.append(command)
            raise IOError("server may have acquired lock before reply was lost")
        return await original(command)
    admin.command = lost
    with pytest.raises(RuntimeError, match="fsyncLock tidak diketahui"):
        asyncio.run(dr.offline_snapshot(tmp_path / "snapshot.zip", ["inventarisasi-backend"], inventory, runner))
    assert {"fsyncUnlock": 1} not in admin.commands
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "preparing"
    journals = list(tmp_path.glob(".aman-dr-snapshot_*.json"))
    assert len(journals) == 1 and json.loads(journals[0].read_text())["phase"] == "acquire_outcome_unknown"
    assert journals[0].stat().st_mode & 0o777 == 0o600


def test_unknown_unlock_outcome_retains_gate_journal_and_never_retries_unlock(offline, tmp_path):
    database, admin, inventory, runner = offline
    original = admin.command
    async def lost(command):
        if "fsyncUnlock" in command:
            admin.commands.append(command)
            raise IOError("unlock reply lost; do not decrement someone else's lock")
        return await original(command)
    admin.command = lost
    with pytest.raises(RuntimeError, match="fsyncUnlock tidak diketahui"):
        asyncio.run(dr.offline_snapshot(tmp_path / "snapshot.zip", ["inventarisasi-backend"], inventory, runner))
    assert admin.commands.count({"fsyncUnlock": 1}) == 1
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "preparing"
    journal = list(tmp_path.glob(".aman-dr-snapshot_*.json"))[0]
    assert json.loads(journal.read_text())["phase"] == "unlock_outcome_unknown"
    assert (tmp_path / "snapshot.zip").stat().st_mode & 0o777 == 0o600


def test_preexisting_mongo_lock_is_never_unlocked(offline, tmp_path):
    database, admin, inventory, runner = offline
    async def existing(command):
        admin.commands.append(command)
        return {"fsyncLock": True}
    admin.command = existing
    with pytest.raises(RuntimeError, match="operator lain"):
        asyncio.run(dr.offline_snapshot(tmp_path / "snapshot.zip", ["inventarisasi-backend"], inventory, runner))
    assert admin.commands == [{"currentOp": 1}]
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "aborted"


def test_concurrent_external_lock_only_own_increment_is_released(offline, tmp_path):
    database, admin, inventory, runner = offline
    async def contested(command):
        admin.commands.append(command)
        if "currentOp" in command:
            return {"fsyncLock": False}
        return {"lockCount": 1 if "fsyncUnlock" in command else 2}
    admin.command = contested
    with pytest.raises(RuntimeError, match="increment sendiri"):
        asyncio.run(dr.offline_snapshot(tmp_path / "snapshot.zip", ["inventarisasi-backend"], inventory, runner))
    assert admin.commands.count({"fsyncUnlock": 1}) == 1
    assert asyncio.run(database.restore_control.find_one({"_id": "GLOBAL"}))["state"] == "preparing"
    assert not (tmp_path / "snapshot.zip").exists()
