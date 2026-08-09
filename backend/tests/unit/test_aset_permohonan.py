"""Gerbang persetujuan KPB untuk transaksi pembukuan aset — ASET-GERBANG-1.

Empat sifat yang dikunci:
  1. Persetujuan MENGEKSEKUSI: permohonan reklasifikasi yang disetujui admin
     lain benar-benar mengganti kode aset + menulis pasangan jurnal 304/107.
  2. Pemisahan peran: pengaju tidak boleh menyetujui permohonannya sendiri
     (403, nol jurnal) — aturan boleh_putuskan yang sama dengan persediaan.
  3. Gerbang wajib-persetujuan: setelan aktif menolak panggilan HTTP langsung
     ke endpoint reklasifikasi (403), tetapi pemanggil internal
     (request=None, jalur persetujuan) tetap lewat.
  4. Jalur KDP: persetujuan kdp_pengembangan menulis 503 + menambah nilai.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.aset_permohonan as rap
import routes.mutasi_bmn as rmb

PENGAJU = {"username": "op1", "role": "operator", "kode_satker": ""}
PENYETUJU = {"username": "adm2", "role": "admin", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


class _Req:
    """Permintaan HTTP tiruan — cukup untuk kunci_idem (headers.get)."""
    headers = {}


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rap, rmb, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "ensure_activity_not_sealed", _diam)
    # mongomock: find_one_and_update + kwarg projection → None (lihat
    # test_penggunaan_henti_guna); di sini tak ada projection, aman.
    return fake


async def _seed(dbx):
    await dbx.assets.insert_one({
        "id": "as-1", "asset_code": "3050104001", "NUP": "1",
        "asset_name": "PC Unit", "purchase_price": "9000000",
        "activity_id": "", "version": 1})
    await dbx.assets.insert_one({
        "id": "kdp-1", "asset_code": "7010101001", "NUP": "1",
        "asset_name": "Pembangunan Gudang", "purchase_price": "500000000",
        "activity_id": "", "version": 1})


async def _ajukan(jalur, asset_id, payload):
    r = await _unwrap(rap.ajukan_permohonan_aset)(
        rap.PermohonanAsetIn(jalur=jalur, asset_id=asset_id, payload=payload),
        user=PENGAJU)
    return r["permohonan"]["id"]


def test_setujui_mengeksekusi_reklasifikasi(dbx):
    async def skenario():
        await _seed(dbx)
        pid = await _ajukan("reklasifikasi", "as-1",
                            {"kode_baru": "3060102001", "alasan": "salah golong"})
        # Belum tereksekusi saat diajukan.
        assert await dbx.mutasi_bmn.count_documents({}) == 0
        r = await _unwrap(rap.setujui_permohonan_aset)(pid, user=PENYETUJU)
        assert "tereksekusi" in r["message"]
        aset = await dbx.assets.find_one({"id": "as-1"})
        assert aset["asset_code"] == "3060102001"
        assert await dbx.mutasi_bmn.count_documents(
            {"kode_transaksi": {"$in": ["304", "107"]}}) == 2
        p = await dbx.aset_permohonan.find_one({"id": pid})
        assert p["status"] == "disetujui"
        assert p["disetujui_oleh"] == "adm2"
    _jalan(skenario())


def test_pengaju_tidak_boleh_menyetujui_sendiri(dbx):
    async def skenario():
        await _seed(dbx)
        pid = await _ajukan("reklasifikasi", "as-1",
                            {"kode_baru": "3060102001"})
        admin_pengaju = {**PENGAJU, "role": "admin"}
        # Pengaju yang sama (walau admin) ditolak — permohonan diajukan op1.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rap.setujui_permohonan_aset)(pid, user={
                "username": "op1", "role": "admin", "kode_satker": ""})
        assert e.value.status_code == 403
        assert await dbx.mutasi_bmn.count_documents({}) == 0
        p = await dbx.aset_permohonan.find_one({"id": pid})
        assert p["status"] == "diusulkan"
        assert admin_pengaju["role"] == "admin"
    _jalan(skenario())


def test_tolak_tidak_mengeksekusi(dbx):
    async def skenario():
        await _seed(dbx)
        pid = await _ajukan("kdp_selesai", "kdp-1", {"kode_baru": "4010101001"})
        await _unwrap(rap.tolak_permohonan_aset)(
            pid, rap.TolakAsetIn(alasan="belum ada BAST fisik"),
            user=PENYETUJU)
        assert await dbx.mutasi_bmn.count_documents({}) == 0
        aset = await dbx.assets.find_one({"id": "kdp-1"})
        assert aset["asset_code"] == "7010101001"
        p = await dbx.aset_permohonan.find_one({"id": pid})
        assert p["status"] == "ditolak"
        assert p["alasan_tolak"] == "belum ada BAST fisik"
    _jalan(skenario())


def test_gerbang_menolak_panggilan_langsung_saat_aktif(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.report_settings.insert_one(
            {"type": "global", "aset_wajib_persetujuan": True})
        with pytest.raises(HTTPException) as e:
            await _unwrap(rmb.reklasifikasi_aset)(
                rmb.ReklasifikasiIn(asset_id="as-1", kode_baru="3060102001"),
                request=_Req(), user=PENGAJU)
        assert e.value.status_code == 403
        assert "permohonan" in str(e.value.detail).lower()
        assert await dbx.mutasi_bmn.count_documents({}) == 0
        # Pemanggil internal (request=None) tetap boleh — jalur persetujuan.
        r = await _unwrap(rmb.reklasifikasi_aset)(
            rmb.ReklasifikasiIn(asset_id="as-1", kode_baru="3060102001"),
            user=PENYETUJU)
        assert r["kode_baru"] == "3060102001"
    _jalan(skenario())


def test_setujui_kdp_pengembangan_menulis_503(dbx):
    async def skenario():
        await _seed(dbx)
        pid = await _ajukan("kdp_pengembangan", "kdp-1",
                            {"nilai": 250_000_000, "keterangan": "termin II"})
        await _unwrap(rap.setujui_permohonan_aset)(pid, user=PENYETUJU)
        aset = await dbx.assets.find_one({"id": "kdp-1"})
        assert aset["purchase_price"] == "750000000"
        j = await dbx.mutasi_bmn.find_one({"kode_transaksi": "503"})
        assert j and j["nilai"] == 250_000_000
        # Atribusi jurnal = PENYETUJU (dialah eksekutornya).
        assert j["oleh"] == "adm2"
    _jalan(skenario())


def test_eksekusi_gagal_mengembalikan_status_diusulkan(dbx):
    async def skenario():
        await _seed(dbx)
        # Kode tujuan persediaan (awalan 1) ditolak validator reklasifikasi —
        # eksekusi gagal → status kembali diusulkan + galat tercatat.
        pid = await _ajukan("reklasifikasi", "as-1",
                            {"kode_baru": "1010301001"})
        with pytest.raises(HTTPException) as e:
            await _unwrap(rap.setujui_permohonan_aset)(pid, user=PENYETUJU)
        assert e.value.status_code == 400
        p = await dbx.aset_permohonan.find_one({"id": pid})
        assert p["status"] == "diusulkan"
        assert "persediaan" in p["galat_terakhir"]
    _jalan(skenario())
