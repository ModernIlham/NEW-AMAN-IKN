"""Batas integrasi BAST/portal: race revisi, laporan, alias dan akses lama.

Seluruh data sintetis dan Mongo tiruan. Gerbang kriptografis diuji terpisah;
di sini status bukti dipasang oleh fixture untuk menguji urutan proyeksi.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import portal_bast as pb
import portal_bast_validitas as validitas
import routes.portal_pemegang as rp
from test_portal_bast import bast, gate, run, sah, seed


ADMIN = {"id": "admin-batas", "username": "admin-batas", "role": "admin",
         "kode_satker": "001"}
HOLDER = {"pegawai_id": "p1", "kode_satker": "001", "session_id": "s1"}


class Req:
    def __init__(self, key="batas", version=0):
        self.headers = {"Idempotency-Key": key, "If-Match": str(version)}


@pytest.fixture
def database(monkeypatch):
    db = AsyncMongoMockClient()["portal_bast_batas"]
    monkeypatch.setattr(validitas, "evaluasi_bast_sah", gate)
    monkeypatch.setattr(rp, "db", db)
    monkeypatch.setattr(rp, "log_audit", AsyncMock())
    monkeypatch.setattr(pb, "_segarkan_aset", AsyncMock())
    return db


def test_dua_revisi_serentak_tidak_membelah_satu_sumber(database, monkeypatch):
    """Lease per BAST saja tidak cukup: garis revisi sumber harus satu."""
    async def scenario():
        await seed(database)
        await bast(database, ids=["a1", "a2"])
        await sah(database)
        for bid in ("revisi-1", "revisi-2"):
            await bast(database, bid=bid, pid="p2", ids=["a1", "a2"],
                       revisi_dari="b1", revisi_mode="mengubah", revisi_alasan="Koreksi penerima")
            await database.bast_serah_terima.update_one({"id": bid}, {"$set": {"_sah": True}})
        original = pb._terapkan_item
        pertama_selesai, lanjutkan = asyncio.Event(), asyncio.Event()

        async def sela(db, doc, item, bukti, oleh):
            hasil = await original(db, doc, item, bukti, oleh)
            if doc["id"] == "revisi-1" and item["asset_id"] == "a1":
                pertama_selesai.set()
                await lanjutkan.wait()
            return hasil

        monkeypatch.setattr(pb, "_terapkan_item", sela)
        awal = asyncio.create_task(pb.sinkronkan_bast(database, "revisi-1"))
        await asyncio.wait_for(pertama_selesai.wait(), timeout=3)
        try:
            try:
                await pb.sinkronkan_bast(database, "revisi-2")
            except HTTPException as exc:
                assert exc.status_code == 409
        finally:
            lanjutkan.set()
        await awal
        rows = await database.assets.find({"id": {"$in": ["a1", "a2"]}}).to_list(None)
        # Dua revisi sah tidak boleh masing-masing mengklaim separuh aset
        # sementara BAST sumber tetap tanpa pengganti resmi.
        assert {a["amanah_bast"]["bast_id"] for a in rows} == {"revisi-1"}
        assert (await database.bast_serah_terima.find_one({"id": "b1"}))["direvisi_oleh"] == "revisi-1"
    run(scenario())


def test_pemetaan_manual_tidak_melewati_bast_yang_dibatalkan(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        await database.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"_sah": False}})
        p = await database.portal_penugasan.find_one({"asset_id": "a1"})
        with pytest.raises(HTTPException) as blocked:
            await rp.periksa_penugasan_aktif(p, HOLDER, True)
        assert blocked.value.status_code == 403
        with pytest.raises(HTTPException) as blocked:
            await rp.buat_penugasan(rp.PenugasanIn(pegawai_id="p1", asset_id="a1",
                dasar_penugasan="Pemetaan manual setelah pembatalan"), Req(), ADMIN)
        assert blocked.value.status_code == 409
        assert await database.portal_penugasan.count_documents({}) == 1
    run(scenario())


@pytest.mark.parametrize("duplicate", [{"NUP": "0001"}, {"NUP": "3", "kode_register": "REGISTER-1"}])
def test_alias_baris_lain_ditolak_sebelum_master_diubah(database, duplicate):
    async def scenario():
        await seed(database)
        await database.assets.update_one({"id": "a1"}, {"$set": {"kode_register": "REGISTER-1"}})
        await bast(database)
        await sah(database)
        await database.assets.insert_one({"id": "alias", "activity_id": "k1",
            "asset_code": "3050104001", "asset_name": "Salinan", "version": 1,
            "user": "", "pengguna_nip": "", **duplicate})
        sebelum = await database.assets.find_one({"id": "alias"})
        await bast(database, bid="alias-bast", pid="p2", ids=["alias"])
        assert (await sah(database, "alias-bast"))["status"] == "perlu_tinjauan"
        assert await database.assets.find_one({"id": "alias"}) == sebelum
        assert await database.portal_penugasan.count_documents({"asset_id": "alias"}) == 0
    run(scenario())


def test_transfer_saat_laporan_inflight_tidak_memberi_akses_ke_pemegang_lama(database, monkeypatch):
    """Observasi historis boleh tersimpan, tidak mengalahkan dasar BAST baru."""
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        lama = await database.portal_penugasan.find_one({"asset_id": "a1"})
        await bast(database, bid="mutasi", pid="p2", jenis="mutasi_pengguna")
        collection_class = type(database.portal_laporan)
        insert = collection_class.insert_one

        async def berpindah_lalu_simpan(collection, doc, *args, **kwargs):
            # Titik tersulit: sesudah guard laporan terakhir dan sesudah
            # lease, tetapi sebelum insert. Status lama belum dapat dicabut.
            if collection.name == "portal_laporan":
                hasil = await sah(database, "mutasi")
                assert hasil["status"] == "perlu_tinjauan"
            return await insert(collection, doc, *args, **kwargs)

        monkeypatch.setattr(collection_class, "insert_one", berpindah_lalu_simpan)
        data = rp.LaporanIn(penugasan_id=lama["id"], penugasan_version=lama["version"],
            jenis="berkala", kondisi="Baik", status_operasional="digunakan",
            catatan="Pengamatan sebelum perpindahan selesai")
        hasil = await rp.kirim_laporan(data, Req("laporan-lama", lama["version"]), HOLDER)
        assert hasil["item"]["status"] == "diajukan"
        assert (await rp.laporan_saya(HOLDER))["total"] == 0
        with pytest.raises(HTTPException):
            await rp.kirim_laporan(data, Req("laporan-lama", lama["version"]), HOLDER)
        administrasi = await rp.daftar_laporan_admin(page=1, page_size=30, user=ADMIN)
        assert administrasi["total"] == 1
        assert administrasi["items"][0]["penugasan_valid"] is False
        asset = await database.assets.find_one({"id": "a1"})
        assert asset["user"] == "Pemegang Dua" and asset["condition"] == "Baik"
        assert (await pb.sinkronkan_bast(database, "mutasi"))["status"] == "selesai"
        assert (await database.assets.find_one({"id": "a1"}))["version"] == asset["version"]
        assert (await database.portal_penugasan.find_one({"id": lama["id"]}))["status"] == "dicabut"
    run(scenario())


def test_retry_lease_laporan_berakhir_tidak_menggandakan_mutasi(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        lama = await database.portal_penugasan.find_one({"asset_id": "a1"})
        await database.portal_penugasan.update_one({"id": lama["id"]}, {"$set": {
            "laporan_aktif": {"id": "proses-terputus", "expires_at": datetime.now(timezone.utc) + timedelta(minutes=2)}}})
        await bast(database, bid="mutasi", pid="p2", jenis="mutasi_pengguna")
        assert (await sah(database, "mutasi"))["status"] == "perlu_tinjauan"
        aset = await database.assets.find_one({"id": "a1"})
        await database.portal_penugasan.update_one({"id": lama["id"]}, {"$set": {
            "laporan_aktif.expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}})
        assert (await pb.sinkronkan_bast(database, "mutasi"))["status"] == "selesai"
        assert await database.assets.find_one({"id": "a1"}) == aset
        assert len(aset["amanah_riwayat"]) == 2
    run(scenario())
