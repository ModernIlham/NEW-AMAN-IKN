"""Restore portal mempertahankan riwayat, bukan akses maupun lease worker lama."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import AsyncMock
import zipfile

from mongomock_motor import AsyncMongoMockClient
import pytest

import indexes
import meili_utils
import portal_auth as pa
import routes.backup as rb
import shared_utils


def arsip(tmp_path, **collections):
    docs = {"users": [], "categories": [], "assets": [],
            "inventory_activities": [], **collections}
    path = tmp_path / "unggahan.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"version": "uji"}))
        for name, rows in docs.items():
            zf.writestr(f"{name}.json", json.dumps([rb.serialize_doc(d) for d in rows]))
    return path


def akses(pegawai_id="p-arsip"):
    return {"id": pegawai_id, "aktif": True, "epoch": 7, "version": 9,
            "email_verified": "pemegang@example.org", "kode_satker": "111111",
            "catatan": "Email pernah diverifikasi", "disetujui_oleh": "admin-lama"}


def penugasan(penugasan_id="t-arsip"):
    return {"id": penugasan_id, "status": "diterima", "version": 3,
            "pegawai_id": "p-arsip", "kode_satker": "111111", "slot_aktif": ["slot-uji"],
            "laporan_aktif": {"id": "laporan-proses-lama", "sidik": "sidik-uji",
                              "expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}}


@pytest.fixture
def env(monkeypatch, tmp_path):
    database = AsyncMongoMockClient()["portal_restore"]
    monkeypatch.setattr(rb, "db", database)
    monkeypatch.setattr(pa, "db", database)
    monkeypatch.setattr(rb, "BACKUP_TEMP_DIR", tmp_path)
    monkeypatch.setattr(rb, "UPLOADS_DIR", tmp_path / "uploads")
    monkeypatch.setattr(rb, "export_gridfs", AsyncMock(return_value=0))
    monkeypatch.setattr(rb, "import_gridfs", AsyncMock(return_value=0))
    monkeypatch.setattr(rb, "repair_ticket_counters", AsyncMock())
    monkeypatch.setattr(indexes, "create_indexes", AsyncMock())
    monkeypatch.setattr(shared_utils, "bersihkan_penanda_migrasi", AsyncMock(return_value=0))
    monkeypatch.setattr(meili_utils, "meili_aktif", lambda: False)
    jobs = []

    async def update_job(job_id, **fields):
        jobs.append(fields)

    monkeypatch.setattr(rb, "update_job", update_job)
    revoke = AsyncMock(wraps=pa.cabut_semua_portal_akses)
    monkeypatch.setattr(pa, "cabut_semua_portal_akses", revoke)
    return database, jobs, revoke


@pytest.mark.parametrize("epoch,version", [(7, 9), (None, "rusak"), (-1, -2), ("7", "9")])
def test_normalisasi_akses_menutup_akses_dan_menjaga_bukti_persetujuan(epoch, version):
    original = {**akses(), "epoch": epoch, "version": version}
    rows = [deepcopy(original)]
    rb._amankan_portal_hasil_pulih("portal_pemegang_akses", rows)
    result = rows[0]
    assert result["aktif"] is False
    assert isinstance(result["epoch"], int) and result["epoch"] >= 1
    assert isinstance(result["version"], int) and result["version"] >= 1
    assert isinstance(result["dicabut_pada"], datetime)
    assert "Verifikasi ulang" in result["alasan_pencabutan"]
    for field in ("id", "email_verified", "kode_satker", "catatan", "disetujui_oleh"):
        assert result[field] == original[field]


def test_normalisasi_tidak_menyentuh_laporan_asli():
    original = {"id": "r1", "status": "terverifikasi", "catatan": "Observasi pemegang",
                "bukti": [{"sha256": "foto-utuh"}], "tinjauan": [{"catatan": "Ditelaah"}]}
    rows = [deepcopy(original)]
    assert rb._amankan_portal_hasil_pulih("portal_laporan", rows) == [original]


@pytest.mark.asyncio
async def test_restore_sukses_membuang_lease_dan_mencabut_sesi_lama(env, tmp_path):
    database, jobs, revoke = env
    await database.portal_pemegang_sesi.insert_one({"id": "sesi-lama"})
    await database.portal_pemegang_tokens.insert_one({"id": "tautan-lama"})
    laporan = {"id": "r1", "catatan": "Bukti tetap tersimpan"}
    path = arsip(tmp_path, portal_pemegang_akses=[akses()],
                 portal_penugasan=[penugasan()], portal_laporan=[laporan])
    await rb.run_restore_task("sukses", path, "pengelola")
    assert jobs[-1]["status"] == "completed"
    assert revoke.await_count == 2  # pagar sebelum dan sesudah restore tetap ada
    restored_access = await database.portal_pemegang_akses.find_one({"id": "p-arsip"})
    assert restored_access["aktif"] is False
    assert restored_access["epoch"] > 7 and restored_access["version"] > 9
    restored = await database.portal_penugasan.find_one({"id": "t-arsip"})
    assert "laporan_aktif" not in restored
    assert restored["slot_aktif"] == ["slot-uji"] and restored["status"] == "diterima"
    # Filter Mongo yang dipakai kirim/cabut penugasan kini dapat maju lagi.
    assert await database.portal_penugasan.count_documents({"id": "t-arsip", "$or": [
        {"laporan_aktif": {"$exists": False}},
        {"laporan_aktif.expires_at": {"$lte": datetime.now(timezone.utc)}}]}) == 1
    assert await database.portal_laporan.find_one({"id": "r1"}, {"_id": 0}) == laporan
    assert await database.portal_pemegang_sesi.count_documents({}) == 0
    assert await database.portal_pemegang_tokens.count_documents({}) == 0


@pytest.mark.asyncio
async def test_worker_terputus_setelah_insert_tidak_menghidupkan_akses(env, tmp_path, monkeypatch):
    database, jobs, revoke = env
    path = arsip(tmp_path, portal_pemegang_akses=[akses()], portal_penugasan=[penugasan()])

    async def worker_berhenti(job_id, **fields):
        jobs.append(fields)
        # Urutan koleksi: akses telah diinsert, belum mencapai hook akhir.
        if fields.get("message") == "Restore: portal_penugasan...":
            raise asyncio.CancelledError()

    monkeypatch.setattr(rb, "update_job", worker_berhenti)
    with pytest.raises(asyncio.CancelledError):
        await rb.run_restore_task("terputus", path, "pengelola")
    assert revoke.await_count == 1
    restored = await database.portal_pemegang_akses.find_one({"id": "p-arsip"})
    assert restored is not None and restored["aktif"] is False
    assert restored["epoch"] == 8 and restored["version"] == 10


@pytest.mark.asyncio
async def test_rollback_juga_membuang_lease_dari_safety_snapshot(env, tmp_path, monkeypatch):
    database, jobs, revoke = env
    await database.portal_pemegang_akses.insert_one(akses("p-sebelum"))
    await database.portal_penugasan.insert_one(penugasan("t-sebelum"))
    path = arsip(tmp_path, portal_pemegang_akses=[akses()], portal_penugasan=[penugasan()])

    async def gagal_di_akhir_koleksi(job_id, **fields):
        jobs.append(fields)
        if fields.get("message") == "Restore: users...":
            raise RuntimeError("Simulasi kegagalan restore")

    monkeypatch.setattr(rb, "update_job", gagal_di_akhir_koleksi)
    await rb.run_restore_task("rollback", path, "pengelola")
    assert jobs[-1]["status"] == "failed"
    assert revoke.await_count == 1
    restored_access = await database.portal_pemegang_akses.find_one({"id": "p-sebelum"})
    assert restored_access is not None and restored_access["aktif"] is False
    assert await database.portal_pemegang_akses.find_one({"id": "p-arsip"}) is None
    restored = await database.portal_penugasan.find_one({"id": "t-sebelum"})
    assert restored is not None and "laporan_aktif" not in restored
    assert restored["slot_aktif"] == ["slot-uji"]
    assert await database.portal_penugasan.find_one({"id": "t-arsip"}) is None
