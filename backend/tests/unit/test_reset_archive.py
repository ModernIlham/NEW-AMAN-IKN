"""Pure reset target tests retain current configuration ownership, not just tags."""
import json
from types import SimpleNamespace
import zipfile

import bcrypt
import pytest

from backup_archive import read_json, validate_archive, write_manifest
from reset_service import build_reset_archive


def safety_archive(path):
    admin = {"id": "root", "username": "root", "role": "admin", "name": "Synthetic",
             "created_at": "2026-10-15T00:00:00+00:00",
             "password": bcrypt.hashpw(b"SyntheticReset9", bcrypt.gensalt(rounds=4)).decode()}
    keep_id, asset_id, orphan_employee = "custom-ttd-id", "operational-asset", "old-employee"
    docs = {"users": [admin], "assets": [{"id": "asset", "photo_gridfs_ids": [asset_id]}],
            "categories": [], "inventory_activities": [],
            "report_settings": [{"kasatker_ttd_file_id": keep_id}]}
    media = [{"_id": keep_id, "length": 3}, {"_id": asset_id, "length": 3},
             {"_id": orphan_employee, "length": 3, "metadata": {"jenis": "foto_pegawai"}}]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for collection, rows in docs.items():
            archive.writestr(collection + ".json", json.dumps(rows))
        for entry in media:
            archive.writestr("gridfs/" + entry["_id"] + ".bin", b"123")
        archive.writestr("gridfs/manifest.json", json.dumps(media))
        archive.writestr("uploads/logo.txt", b"synthetic local logo")
        archive.writestr("metadata.json", "{}")
        write_manifest(archive, {key: len(rows) for key, rows in docs.items()}, len(media), 1)
    return path


def test_reset_target_uses_retained_references_and_legacy_policy(tmp_path):
    source = safety_archive(tmp_path / "safety.zip")
    target = tmp_path / "target.zip"
    deleted = build_reset_archive(source, target)
    assert deleted["assets"] == 1 and deleted["gridfs_files"] == 1
    with zipfile.ZipFile(target) as archive:
        validated = validate_archive(archive, True, True)
        assert {row["_id"] for row in validated["gridfs"]} == {"custom-ttd-id", "old-employee"}
        assert read_json(archive, "assets.json") == []
        assert read_json(archive, "report_settings.json")[0]["kasatker_ttd_file_id"] == "custom-ttd-id"
        assert archive.read("uploads/logo.txt") == b"synthetic local logo"
    assert target.stat().st_mode & 0o777 == 0o600


def test_reset_target_never_overwrites_or_deletes_existing_path(tmp_path):
    source = safety_archive(tmp_path / "safety.zip")
    target = tmp_path / "target.zip"
    target.write_bytes(b"preexisting operator data")
    with pytest.raises(FileExistsError):
        build_reset_archive(source, target)
    assert target.read_bytes() == b"preexisting operator data"


def test_invalid_safety_archive_aborts_without_publishing_target(tmp_path):
    source = safety_archive(tmp_path / "safety.zip")
    with zipfile.ZipFile(source, "a") as archive:
        archive.writestr("unknown.json", "invalid JSON")
    target = tmp_path / "target.zip"
    with pytest.raises(ValueError):
        build_reset_archive(source, target)
    assert not target.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("collision", ["safety", "source"])
async def test_reset_coordinator_preserves_unowned_collision_files_before_wipe(tmp_path, monkeypatch, collision):
    from mongomock_motor import AsyncMongoMockClient
    import routes.backup as backup
    import pemeliharaan
    import reset_service
    database = AsyncMongoMockClient()["aman_ci_reset_collision"]
    monkeypatch.setattr(backup, "db", database)
    monkeypatch.setattr(backup, "BACKUP_TEMP_DIR", tmp_path)
    monkeypatch.setattr(backup, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(pemeliharaan, "_CACHE_TTL", 0)
    monkeypatch.setattr(reset_service.uuid, "uuid4", lambda: SimpleNamespace(hex="a" * 32))
    source = safety_archive(tmp_path / "fixture.zip")
    with zipfile.ZipFile(source) as archive:
        await database.users.insert_many(read_json(archive, "users.json"))
    await database.assets.insert_one({"id": "original"})
    path = tmp_path / (("safety_data_" if collision == "safety" else "reset_") + "reset-" + "a" * 16 + ".zip")
    path.write_bytes(b"preexisting archive owned by another operation")
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await reset_service.reset_system("operator")
    assert path.read_bytes() == b"preexisting archive owned by another operation"
    assert await database.assets.count_documents({"id": "original"}) == 1
    assert (await backup.restore_control_status())["state"] == "aborted"
