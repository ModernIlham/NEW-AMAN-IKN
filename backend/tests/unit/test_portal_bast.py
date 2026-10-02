"""Amanah otomatis: proyeksi idempoten, perpindahan, dan pemulihan kegagalan."""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import portal_bast as pb
import portal_bast_validitas as validitas
import routes.portal_pemegang as rp
from portal_pemegang_utils import ikatan_sumber
from routes.backup import _amankan_portal_hasil_pulih


def run(coro):
    return asyncio.run(coro)


async def gate(db, b):
    # Gerbang bukti diuji tersendiri di test_portal_bast_validitas.
    sah = b.get("_sah", False) and not b.get("direvisi_oleh")
    return {"sah": sah, "alasan": "Menunggu bukti", "kunci_bukti": b.get("_bukti", "proof-1"),
            "jenis": "basah", "file_id": "scan", "oleh": "validator"}


@pytest.fixture
def database(monkeypatch):
    db = AsyncMongoMockClient()["portal_bast"]
    monkeypatch.setattr(validitas, "evaluasi_bast_sah", gate)
    monkeypatch.setattr(rp, "db", db)
    monkeypatch.setattr(pb, "_segarkan_aset", AsyncMock())
    return db


async def seed(db):
    await db.inventory_activities.insert_one({"id": "k1", "kode_satker": "001"})
    await db.pegawai.insert_many([
        {"id": "p1", "nama": "Pemegang Satu", "nip": "123", "kode_satker": "001",
         "email": "satu@example.test", "status": "aktif"},
        {"id": "p2", "nama": "Pemegang Dua", "nip": "456", "kode_satker": "001",
         "email": "dua@example.test", "status": "aktif"},
    ])
    await db.assets.insert_many([
        {"id": f"a{i}", "activity_id": "k1", "asset_code": "3050104001", "NUP": str(i),
         "asset_name": "Laptop", "user": "", "pengguna_nip": "", "version": 1,
         "purchase_price": 10000000, "condition": "Baik", "location": "Ruang A"}
        for i in (1, 2)])


async def bast(db, bid="b1", pid="p1", jenis="penggunaan_melekat", ids=None, **kwargs):
    peg = await db.pegawai.find_one({"id": pid})
    rows = await db.assets.find({"id": {"$in": ids or ["a1"]}}, {"_id": 0}).to_list(None)
    b = {"id": bid, "kode_satker": "001", "jenis": jenis, "nomor": f"BAST/{bid}",
         "tanggal": "2026-10-03", "asset_ids": [a["id"] for a in rows],
         "pihak_kedua": {"pegawai_id": pid, "nama": peg["nama"], "nip": peg["nip"]}, **kwargs}
    b["portal_otomasi"] = await pb.siapkan_otomasi_bast(db, b, rows)
    await db.bast_serah_terima.insert_one(deepcopy(b))
    return b


async def sah(db, bid="b1"):
    await db.bast_serah_terima.update_one({"id": bid}, {"$set": {"_sah": True}})
    return await pb.sinkronkan_bast(db, bid, "validator")


def test_draft_tidak_mengubah_master_dan_final_langsung_diterima(database):
    async def scenario():
        await seed(database)
        before = await database.assets.find_one({"id": "a1"})
        await bast(database)
        result = await pb.sinkronkan_bast(database, "b1")
        assert result["status"] == "menunggu_keabsahan"
        assert await database.assets.find_one({"id": "a1"}) == before
        assert await database.portal_penugasan.count_documents({}) == 0
        result = await sah(database)
        assert result["status"] == "selesai"
        p = await database.portal_penugasan.find_one({"asset_id": "a1"})
        assert p["status"] == "diterima" and p["penerimaan_otomatis"]
        assert p["sumber_bast"]["id"] == "b1"
        assert (await database.portal_pemegang_akses.find_one({"id": "p1"}))["aktif"]
        assert len((await rp.aset_saya({"pegawai_id": "p1", "kode_satker": "001"}))["items"]) == 1
        updated = await database.assets.find_one({"id": "a1"})
        assert updated["user"] == "Pemegang Satu"
        for k in ("purchase_price", "condition", "location"):
            assert updated[k] == before[k]
        assert await database.mutasi_bmn.count_documents({}) == 0
    run(scenario())


def test_retry_tidak_menggandakan_amanah_riwayat_dan_versi_aset(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        first = await database.assets.find_one({"id": "a1"})
        result = await pb.sinkronkan_bast(database, "b1")
        assert result["status"] == "selesai"
        assert await database.assets.find_one({"id": "a1"}) == first
        assert await database.portal_penugasan.count_documents({}) == 1
        assert await database.portal_pemegang_akses.count_documents({}) == 1
    run(scenario())


def test_mutasi_tutup_lama_dan_draft_tidak_mencabut(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        p = await database.portal_penugasan.find_one({"pegawai_id": "p1"})
        await bast(database, "b2", "p2", "mutasi_pengguna")
        assert await rp.periksa_penugasan_aktif(p)
        assert (await sah(database, "b2"))["status"] == "selesai"
        with pytest.raises(HTTPException):
            await rp.periksa_penugasan_aktif(p)
        assert (await database.portal_penugasan.find_one({"id": p["id"]}))["status"] == "dicabut"
        assert await database.portal_penugasan.count_documents({"status": "diterima"}) == 1
        assert len((await database.assets.find_one({"id": "a1"}))["amanah_riwayat"]) == 2
        # Callback lama tidak merebut ulang barang.
        assert (await pb.sinkronkan_bast(database, "b1"))["status"] == "perlu_tinjauan"
        assert (await database.assets.find_one({"id": "a1"}))["user"] == "Pemegang Dua"
    run(scenario())


@pytest.mark.parametrize("jenis", ["pengembalian", "pengembalian_almarhum"])
def test_pengembalian_tidak_memberi_akses_personal_kpb(database, jenis):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        await bast(database, "b2", jenis=jenis)
        result = await sah(database, "b2")
        assert result["hasil"][0]["status"] == "ditutup"
        assert await database.portal_penugasan.count_documents({"status": "diterima"}) == 0
        assert (await database.assets.find_one({"id": "a1"}))["user"] == ""
    run(scenario())


def test_revisi_efektif_hanya_setelah_sah_dan_cabut_tidak_rollback_fisik(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        await bast(database, "b2", revisi_dari="b1", revisi_mode="mencabut", revisi_ke=1)
        assert not (await database.bast_serah_terima.find_one({"id": "b1"})).get("direvisi_oleh")
        assert (await sah(database, "b2"))["status"] == "selesai"
        assert (await database.bast_serah_terima.find_one({"id": "b1"}))["direvisi_oleh"] == "b2"
        assert (await database.assets.find_one({"id": "a1"}))["user"] == "Pemegang Satu"
        assert await database.portal_penugasan.count_documents({"status": "diterima"}) == 0
    run(scenario())


def test_pj_operasional_hanya_barang_bagiannya(database):
    async def scenario():
        await seed(database)
        b = await bast(database, jenis="operasional_unit", ids=["a1", "a2"],
                       penanggung_jawab_tambahan=[{"nama": "Pemegang Dua", "nip": "456", "asset_ids": ["a2"]}])
        assert b["penanggung_jawab_tambahan"][0]["pegawai_id"] == "p2"
        assert (await sah(database))["status"] == "selesai"
        assert (await database.portal_penugasan.find_one({"asset_id": "a1"}))["pegawai_id"] == "p1"
        assert (await database.portal_penugasan.find_one({"asset_id": "a2"}))["pegawai_id"] == "p2"
    run(scenario())


def test_identitas_nama_sama_tidak_digabung_dan_nik_diterima(database):
    async def scenario():
        await seed(database)
        await database.pegawai.update_one({"id": "p2"}, {"$set": {"nama": "Pemegang Satu", "status_kepegawaian": "non_asn"}})
        await bast(database, pid="p2")
        assert (await sah(database))["status"] == "selesai"
        assert (await database.portal_penugasan.find_one({}))["pegawai_id"] == "p2"
    run(scenario())


@pytest.mark.parametrize("modifikasi", ["nip_ganda", "id_palsu", "tanpa_nip", "satker_lain", "nama_berbeda"])
def test_identitas_ambigu_tidak_mengubah_barang(database, modifikasi):
    async def scenario():
        await seed(database)
        if modifikasi == "nip_ganda":
            await database.pegawai.update_one({"id": "p2"}, {"$set": {"nip": "123"}})
        elif modifikasi == "satker_lain":
            await database.pegawai.update_one({"id": "p1"}, {"$set": {"kode_satker": "002"}})
        pihak = {"nama": "Pemegang Satu", "nip": "123", "pegawai_id": "p1"}
        if modifikasi == "id_palsu": pihak["pegawai_id"] = "p2"
        if modifikasi == "tanpa_nip": pihak["nip"] = ""
        if modifikasi == "nama_berbeda": pihak["nama"] = "Orang Berbeda"
        await bast(database, pihak_kedua=pihak)
        before = await database.assets.find_one({"id": "a1"})
        assert (await sah(database))["status"] == "perlu_tinjauan"
        assert await database.assets.find_one({"id": "a1"}) == before
        assert await database.portal_penugasan.count_documents({}) == 0
    run(scenario())


@pytest.mark.parametrize("kondisi", ["email_kosong", "email_ganda", "dicabut", "restore", "identitas_berubah"])
def test_email_pengecualian_tidak_menggagalkan_catatan_amanah(database, kondisi):
    async def scenario():
        await seed(database)
        if kondisi == "email_kosong":
            await database.pegawai.update_one({"id": "p1"}, {"$set": {"email": ""}})
        if kondisi == "email_ganda":
            await database.pegawai.update_one({"id": "p2"}, {"$set": {"email": "satu@example.test"}})
        if kondisi == "dicabut":
            await database.portal_pemegang_akses.insert_one({"id": "p1", "aktif": False, "epoch": 6})
        b = await bast(database)
        if kondisi == "restore":
            restored = _amankan_portal_hasil_pulih("bast_serah_terima", [b])[0]
            await database.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"portal_otomasi": restored["portal_otomasi"]}})
        if kondisi == "identitas_berubah":
            await database.pegawai.update_one({"id": "p1"}, {"$set": {"email": "baru@example.test"}})
        result = await sah(database)
        assert result["status"] == "selesai" and result["hasil"][0]["alasan"]
        assert await database.portal_penugasan.count_documents({"status": "diterima"}) == 1
        akses = await database.portal_pemegang_akses.find_one({"id": "p1"})
        assert not akses or not akses.get("aktif")
    run(scenario())


def test_konflik_master_tidak_menimpa_dan_sebagian_jelas(database):
    async def scenario():
        await seed(database)
        await bast(database, ids=["a1", "a2"])
        await database.assets.update_one({"id": "a1"}, {"$set": {"user": "Pemegang terbaru"}, "$inc": {"version": 1}})
        result = await sah(database)
        assert result["status"] == "sebagian"
        assert (await database.assets.find_one({"id": "a1"}))["user"] == "Pemegang terbaru"
        assert (await database.assets.find_one({"id": "a2"}))["user"] == "Pemegang Satu"
    run(scenario())


def test_crash_setelah_cas_aset_dapat_dipulihkan(database, monkeypatch):
    async def scenario():
        await seed(database)
        await bast(database)
        original = pb._tutup_lama
        async def crash(*args, **kwargs):
            raise RuntimeError("koneksi terputus")
        monkeypatch.setattr(pb, "_tutup_lama", crash)
        with pytest.raises(RuntimeError):
            await sah(database)
        version = (await database.assets.find_one({"id": "a1"}))["version"]
        assert await database.portal_penugasan.count_documents({}) == 0
        monkeypatch.setattr(pb, "_tutup_lama", original)
        assert (await pb.sinkronkan_bast(database, "b1"))["status"] == "selesai"
        assert (await database.assets.find_one({"id": "a1"}))["version"] == version
        assert await database.portal_penugasan.count_documents({}) == 1
    run(scenario())


def test_cancel_sumber_menolak_guard_walau_callback_cascade_gagal(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        p = await database.portal_penugasan.find_one({})
        await database.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"_sah": False}})
        with pytest.raises(HTTPException):
            await rp.periksa_penugasan_aktif(p)
        assert (await rp.aset_saya({"pegawai_id": "p1", "kode_satker": "001"}))["total"] == 0
        assert (await database.assets.find_one({"id": "a1"}))["user"] == "Pemegang Satu"
    run(scenario())


def test_admin_revokasi_tidak_dihidupkan_retry(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        await database.portal_penugasan.update_one({}, {"$set": {"status": "dicabut"}, "$unset": {"slot_aktif": ""}})
        assert (await pb.sinkronkan_bast(database, "b1"))["status"] == "perlu_tinjauan"
        assert await database.portal_penugasan.count_documents({"status": "diterima"}) == 0
    run(scenario())


def test_draft_konkuren_yang_basis_sama_tidak_merebut_amanah(database):
    async def scenario():
        await seed(database)
        await bast(database, "b1")
        await bast(database, "b2", "p2")
        assert (await sah(database, "b1"))["status"] == "selesai"
        assert (await sah(database, "b2"))["status"] == "perlu_tinjauan"
        assert (await database.assets.find_one({"id": "a1"}))["user"] == "Pemegang Satu"
    run(scenario())


def test_lease_dan_restore_tidak_membawa_worker_hantu(database):
    async def scenario():
        await seed(database)
        b = await bast(database)
        lease = {"id": "worker-mati", "expires_at": datetime.now(timezone.utc) + timedelta(minutes=1)}
        await database.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"portal_otomasi.lease": lease}})
        with pytest.raises(HTTPException) as exc:
            await pb.sinkronkan_bast(database, "b1")
        assert exc.value.status_code == 409
        b["portal_otomasi"]["lease"] = lease
        restored = _amankan_portal_hasil_pulih("bast_serah_terima", [b])[0]
        assert "lease" not in restored["portal_otomasi"]
        assert restored["portal_otomasi"]["akses_otomatis_ditahan"]
    run(scenario())


def test_master_berubah_setelah_penerapan_retry_tidak_melegitimasi(database):
    async def scenario():
        await seed(database)
        await bast(database)
        await sah(database)
        await database.assets.update_one({"id": "a1"}, {"$set": {"pengguna_nip": "456"}})
        assert (await pb.sinkronkan_bast(database, "b1"))["status"] == "perlu_tinjauan"
    run(scenario())


def test_lama_tidak_dimigrasi_diam_diam(database):
    async def scenario():
        await seed(database)
        await database.bast_serah_terima.insert_one({"id": "lama", "_sah": True})
        assert (await pb.sinkronkan_bast(database, "lama"))["status"] == "perlu_tinjauan"
        assert await database.portal_penugasan.count_documents({}) == 0
    run(scenario())
