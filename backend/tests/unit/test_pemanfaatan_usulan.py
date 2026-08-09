"""Usulan pemanfaatan berstatus + perpanjangan (ASET-MANFAAT, PMK 115/2020):

  1. Usulan baru mengalir draf → diajukan → disetujui → perjanjian, dan
     status perjanjian MELAHIRKAN dokumen register perjanjian (dokumen
     wajib per tahap ditagih).
  2. Aturan perpanjangan: BGS/BSG ditolak; perjanjian kedaluwarsa ditolak;
     Pinjam Pakai <60 hari sebelum berakhir ditolak; satu induk satu
     usulan berjalan (409).
  3. Efek perpanjangan: tanggal berakhir induk maju + riwayat perpanjangan
     tercatat (berakhir_lama/baru + nomor dokumen).
"""
import asyncio
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.pemanfaatan as rp

USER = {"username": "op1", "role": "operator", "kode_satker": ""}
ADMIN = {"username": "adm1", "role": "admin", "kode_satker": ""}


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


def _hari(delta):
    return (date.today() + timedelta(days=delta)).isoformat()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    # mongomock: find_one_and_update + kwarg projection → None (siasat kelas,
    # lihat test_tgr) — transisi usulan memakainya.
    from mongomock_motor import AsyncMongoMockCollection
    asli = AsyncMongoMockCollection.find_one_and_update

    async def _fau(self, filter, update, **kw):
        kw.pop("projection", None)
        doc = await asli(self, filter, update, **kw)
        if doc:
            doc.pop("_id", None)
        return doc

    monkeypatch.setattr(AsyncMongoMockCollection, "find_one_and_update", _fau)
    return fake


async def _seed_induk(dbx, bentuk="sewa", berakhir=None, mitra="PT Sinar"):
    rec = {
        "id": f"pmf-{bentuk}-{mitra.replace(' ', '')}", "kode_satker": "",
        "asset_id": "",
        "asset_code": "", "NUP": "", "asset_name": "",
        "bentuk": bentuk, "mitra": mitra, "jenis_mitra": "PT",
        "mulai": _hari(-300), "berakhir": berakhir or _hari(200),
        "nilai": 10_000_000, "nomor_persetujuan": "S-1/KNL/2026",
        "nomor_perjanjian": "PJ-1/2026", "ntpn": "A1B2C3",
        "kontribusi_tahunan": 0, "kontribusi": [], "lampiran": [],
        "lampiran_wasdal": [], "keterangan": "",
        "created_by": "op1", "created_at": "2025-01-01",
        "updated_at": "2025-01-01",
    }
    await dbx.pemanfaatan.insert_one({**rec})
    return rec


def test_usulan_baru_jadi_perjanjian(dbx):
    async def skenario():
        u = await _unwrap(rp.buat_usulan_pemanfaatan)(
            rp.UsulanPemanfaatanIn(
                jenis="baru", bentuk="sewa", mitra="CV Kilat",
                mulai=_hari(10), berakhir=_hari(300), nilai=12_000_000),
            user=USER)
        assert u["status"] == "draf"
        # diajukan tanpa nomor surat usulan → ditolak.
        with pytest.raises(HTTPException) as e:
            await _unwrap(rp.transisi_usulan_pemanfaatan)(
                u["id"], rp.TransisiUsulanPemanfaatanIn(status="diajukan"),
                admin=ADMIN)
        assert e.value.status_code == 400
        await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="diajukan", nomor_dokumen="ND-7/2026"), admin=ADMIN)
        await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="disetujui", nomor_dokumen="S-88/KNL/2026"),
            admin=ADMIN)
        r = await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="perjanjian", nomor_dokumen="PJ-88/2026"), admin=ADMIN)
        assert r["status"] == "perjanjian"
        # Efek: dokumen register perjanjian lahir & tertaut balik.
        p = await dbx.pemanfaatan.find_one({"mitra": "CV Kilat"}, {"_id": 0})
        assert p is not None
        assert p["nomor_persetujuan"] == "S-88/KNL/2026"
        assert p["nomor_perjanjian"] == "PJ-88/2026"
        assert p["usulan_id"] == u["id"]
        assert r["pemanfaatan_id"] == p["id"]
    _jalan(skenario())


def test_aturan_perpanjangan(dbx):
    async def skenario():
        # BGS/BSG: tegas tidak dapat diperpanjang (PMK 115/2020).
        bgs = await _seed_induk(dbx, bentuk="bgs_bsg", mitra="PT Bangun")
        with pytest.raises(HTTPException) as e1:
            await _unwrap(rp.buat_usulan_pemanfaatan)(
                rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                       pemanfaatan_id=bgs["id"],
                                       berakhir=_hari(500)), user=USER)
        assert e1.value.status_code == 400
        assert "tidak dapat diperpanjang" in str(e1.value.detail)
        # Perjanjian sudah kedaluwarsa → harus pemanfaatan baru.
        mati = await _seed_induk(dbx, bentuk="sewa", berakhir=_hari(-5),
                                 mitra="PT Usang")
        with pytest.raises(HTTPException) as e2:
            await _unwrap(rp.buat_usulan_pemanfaatan)(
                rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                       pemanfaatan_id=mati["id"],
                                       berakhir=_hari(300)), user=USER)
        assert e2.value.status_code == 400
        assert "sudah berakhir" in str(e2.value.detail)
        # Pinjam Pakai: wajib diajukan ≥60 hari sebelum berakhir.
        pp = await _seed_induk(dbx, bentuk="pinjam_pakai", berakhir=_hari(30),
                               mitra="Pemda Sepaku")
        with pytest.raises(HTTPException) as e3:
            await _unwrap(rp.buat_usulan_pemanfaatan)(
                rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                       pemanfaatan_id=pp["id"],
                                       berakhir=_hari(400)), user=USER)
        assert e3.value.status_code == 400
        assert "60 hari" in str(e3.value.detail)
        # Jalur sah + anti-duplikat usulan berjalan per induk.
        sewa = await _seed_induk(dbx, bentuk="sewa", berakhir=_hari(200))
        u = await _unwrap(rp.buat_usulan_pemanfaatan)(
            rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                   pemanfaatan_id=sewa["id"],
                                   berakhir=_hari(500)), user=USER)
        assert u["status"] == "draf" and u["bentuk"] == "sewa"
        with pytest.raises(HTTPException) as e4:
            await _unwrap(rp.buat_usulan_pemanfaatan)(
                rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                       pemanfaatan_id=sewa["id"],
                                       berakhir=_hari(600)), user=USER)
        assert e4.value.status_code == 409
    _jalan(skenario())


def test_efek_perpanjangan(dbx):
    async def skenario():
        sewa = await _seed_induk(dbx, bentuk="sewa", berakhir=_hari(100))
        baru = _hari(465)
        u = await _unwrap(rp.buat_usulan_pemanfaatan)(
            rp.UsulanPemanfaatanIn(jenis="perpanjangan",
                                   pemanfaatan_id=sewa["id"],
                                   berakhir=baru), user=USER)
        await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="diajukan", nomor_dokumen="ND-9/2026"), admin=ADMIN)
        await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="disetujui", nomor_dokumen="S-99/KNL/2026"),
            admin=ADMIN)
        await _unwrap(rp.transisi_usulan_pemanfaatan)(
            u["id"], rp.TransisiUsulanPemanfaatanIn(
                status="perjanjian", nomor_dokumen="ADD-1/2026"), admin=ADMIN)
        induk = await dbx.pemanfaatan.find_one({"id": sewa["id"]}, {"_id": 0})
        assert induk["berakhir"] == baru
        assert induk["nomor_persetujuan"] == "S-99/KNL/2026"
        riw = induk.get("perpanjangan") or []
        assert len(riw) == 1
        assert riw[0]["berakhir_lama"] == sewa["berakhir"]
        assert riw[0]["berakhir_baru"] == baru
        assert riw[0]["usulan_id"] == u["id"]
    _jalan(skenario())
