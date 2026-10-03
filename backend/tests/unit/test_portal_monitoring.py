"""Monitoring read-only: seluruh halaman, scope satker, metadata dan riwayat."""
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.portal_pemegang as rp

STAFF = {"id": "op", "role": "operator", "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def database(monkeypatch):
    db = AsyncMongoMockClient()["uji_monitoring_portal"]
    monkeypatch.setattr(rp, "db", db)
    return db


def test_ringkasan_kosong_dan_satker_wajib(database):
    async def scenario():
        data = await rp.monitoring_admin(user=STAFF)
        assert data == {
            "penugasan": {"total": 0, "diterima": 0, "menunggu_konfirmasi": 0,
                           "disanggah": 0, "dicabut": 0},
            "laporan": {"total": 0, "menunggu_tinjauan": 0, "perlu_perbaikan": 0,
                        "terverifikasi": 0, "ditolak": 0}, "pemegang": 0,
        }
        with pytest.raises(HTTPException) as err:
            await rp.monitoring_admin(user={**STAFF, "kode_satker": ""})
        assert err.value.status_code == 409
    run(scenario())


def test_total_semua_halaman_dan_pegawai_tidak_bocor_satker(database):
    async def scenario():
        await database.portal_penugasan.insert_many([
            {"id": "a1", "kode_satker": "001", "pegawai_id": "p1", "status": "diterima"},
            {"id": "a2", "kode_satker": "001", "pegawai_id": "p1", "status": "dicabut"},
            {"id": "a3", "kode_satker": "001", "pegawai_id": "p2", "status": "menunggu_konfirmasi"},
            {"id": "a4", "kode_satker": "001", "pegawai_id": "p2", "status": "disanggah"},
            {"id": "a5", "kode_satker": "002", "pegawai_id": "p3", "status": "diterima"},
        ])
        await database.portal_laporan.insert_many([
            {"id": f"r{i}", "kode_satker": "001", "pegawai_id": "p1", "status": "diajukan"}
            for i in range(65)
        ] + [
            {"id": "legacy", "kode_satker": "001", "pegawai_id": "p2", "status": "menunggu_verifikasi"},
            {"id": "revisi", "kode_satker": "001", "pegawai_id": "p2", "status": "perlu_perbaikan"},
            {"id": "valid", "kode_satker": "001", "pegawai_id": "p2", "status": "terverifikasi"},
            {"id": "tolak", "kode_satker": "001", "pegawai_id": "p2", "status": "ditolak"},
            {"id": "lain", "kode_satker": "002", "pegawai_id": "p3", "status": "diajukan"},
        ])
        data = await rp.monitoring_admin(user=STAFF)
        assert data["penugasan"] == {"total": 4, "diterima": 1, "dicabut": 1,
                                     "menunggu_konfirmasi": 1, "disanggah": 1}
        assert data["pemegang"] == 2
        assert data["laporan"] == {"total": 69, "menunggu_tinjauan": 66,
                                   "perlu_perbaikan": 1, "terverifikasi": 1, "ditolak": 1}
        selected = await rp.monitoring_admin(pegawai_id="p1", user=STAFF)
        assert selected["penugasan"]["total"] == 2
        assert selected["laporan"]["total"] == 65
        assert selected["pemegang"] == 1
        other = await rp.monitoring_admin(pegawai_id="p3", user=STAFF)
        assert other["penugasan"]["total"] == other["laporan"]["total"] == other["pemegang"] == 0
        assert await database.assets.count_documents({}) == 0
        assert await database.portal_penugasan.count_documents({}) == 5
        assert await database.portal_laporan.count_documents({}) == 70
    run(scenario())


def test_laporan_terakhir_mengikuti_penugasan_dan_waktu_server(database, monkeypatch):
    async def scenario():
        await database.portal_penugasan.insert_many([
            {"id": "aktif", "kode_satker": "001", "pegawai_id": "p1", "asset_id": "as1", "status": "diterima"},
            {"id": "lama", "kode_satker": "001", "pegawai_id": "p2", "asset_id": "as1", "status": "dicabut"},
            {"id": "kosong", "kode_satker": "001", "pegawai_id": "p1", "asset_id": "as2", "status": "diterima"},
        ])
        base = {"kode_satker": "001", "pegawai_id": "p1", "penugasan_id": "aktif",
                "asset_id": "as1", "status": "diajukan", "kondisi": "Rusak Ringan",
                "bukti": [{"data_base64": "RAHASIA-FOTO"}], "_operasi": ["RAHASIA-IDEM"],
                "_identitas_pelapor": {"email": "pribadi@example.test"}}
        await database.portal_laporan.insert_many([
            {**base, "id": "r1", "created_at": "2026-10-01", "updated_at": "2099-01-01"},
            {**base, "id": "r2", "created_at": "2026-10-02", "diambil_pada": "2020-01-01"},
            {**base, "id": "r3", "created_at": "2026-10-02", "status": "perlu_perbaikan",
             "tinjauan": [{"catatan": "Lengkapi foto"}]},
            {**base, "id": "rsalah", "created_at": "2099-01-02", "pegawai_id": "p2"},
            {**base, "id": "rluar", "created_at": "2099-01-03", "kode_satker": "002"},
            {**base, "id": "rlama", "created_at": "2099-01-04", "penugasan_id": "lama", "pegawai_id": "p2"},
        ])
        async def guard(p, **kwargs):
            if p["status"] == "dicabut":
                raise HTTPException(403, "Akses dicabut")
            return {"asset_name": "Laptop", "condition": "Baik", "location": "Ruang A"}
        monkeypatch.setattr(rp, "periksa_penugasan_aktif", guard)
        data = await rp.daftar_penugasan_admin(user=STAFF)
        rows = {a["id"]: a for a in data["items"]}
        assert rows["aktif"]["condition"] == "Baik"
        latest = rows["aktif"]["laporan_terakhir"]
        assert latest["id"] == "r3"
        assert latest["kondisi"] == "Rusak Ringan"
        assert latest["tinjauan"] == [{"catatan": "Lengkapi foto"}]
        assert rows["lama"]["laporan_terakhir"]["id"] == "rlama"
        assert rows["lama"]["akses_valid"] is False
        assert rows["kosong"]["laporan_terakhir"] is None
        assert "RAHASIA" not in str(data)
        assert "pribadi@example.test" not in str(data)
        assert "data_base64" not in str(data)
    run(scenario())


def test_metadata_batch_melewati_200_penugasan(database):
    async def scenario():
        items = [{"id": str(i), "pegawai_id": "p1"} for i in range(205)]
        await database.portal_laporan.insert_many([
            {"id": "r" + str(i), "penugasan_id": str(i), "pegawai_id": "p1",
             "kode_satker": "001", "created_at": "2026-10-03"} for i in range(205)
        ])
        assert len(await rp._laporan_terakhir_penugasan(items, "001")) == 205
        assert await rp._laporan_terakhir_penugasan([], "001") == {}
    run(scenario())


def test_pencarian_literal_sebelum_paginasi_dan_status(database, monkeypatch):
    async def scenario():
        monkeypatch.setattr(rp, "_validitas_penugasan", AsyncMock(return_value=(True, "")))
        base = {"kode_satker": "001", "pegawai_id": "p1", "penugasan_id": "a1", "status": "diajukan",
                "asset_name": "Laptop [A]+", "pegawai_nama": "Siti", "lokasi_laporan": "Gudang", "bukti": []}
        await database.portal_laporan.insert_many([
            {**base, "id": f"r{i}", "created_at": f"2026-10-03T10:{i:02d}"} for i in range(35)
        ] + [
            {**base, "id": "beda", "asset_name": "Laptop AAA"},
            {**base, "id": "beda-status", "status": "ditolak"},
            {**base, "id": "beda-pegawai", "pegawai_id": "p2"},
            {**base, "id": "beda-satker", "kode_satker": "002"},
        ])
        data = await rp.daftar_laporan_admin("diajukan", 2, 30, STAFF, "p1", " [a]+ ")
        assert data["total"] == 35
        assert len(data["items"]) == 5
        assert all(r["pegawai_id"] == "p1" and r["kode_satker"] == "001" for r in data["items"])
        assert (await rp.daftar_laporan_admin("", 1, 30, STAFF, "", ".*"))["total"] == 0
        for search in ("sITI", "GUDANG"):
            assert (await rp.daftar_laporan_admin("", 1, 30, STAFF, "", search))["total"] == 38
        with pytest.raises(HTTPException) as err:
            await rp.daftar_laporan_admin("", 1, 30, STAFF, "", "x" * 121)
        assert err.value.status_code == 422
    run(scenario())
