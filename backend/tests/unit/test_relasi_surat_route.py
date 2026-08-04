"""Uji endpoint relasi antar surat + stempel keberlakuan di buku agenda.

Yang dijaga: badge "Tidak Berlaku" muncul OTOMATIS pada surat yang dicabut
(tanpa ada yang mengetik status), asas non-herleving (mencabut pencabut tidak
menghidupkan kembali yang dicabut; hanya PEMBATALAN nomor pencabut yang
mematikan panahnya), isolasi satker pada panah, dan timeline dua arah.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from routes.persuratan import RelasiIn, SuratKeluarIn, TransisiIn

USER = {"username": "arsiparis", "role": "admin", "kode_satker": "527010"}
USER_LAIN = {"username": "tetangga", "role": "admin", "kode_satker": "999999"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    for nama in ("jadwalkan_sync", "jadwalkan_hapus"):
        monkeypatch.setattr(rp, nama, lambda *a, **k: None, raising=False)
    return fake


async def _buat(user=USER, **kw):
    dasar = {"perihal": "SK uji", "jenis_naskah": "Surat Keputusan",
             "modul": "umum", "tanggal_surat": "2026-08-01"}
    dasar.update(kw)
    return await rp.booking_surat_keluar(SuratKeluarIn(**dasar), user=user)


async def _sahkan(surat_id, user=USER):
    await rp.transisi_surat(surat_id, TransisiIn(status="disahkan"), user=user)


def test_mencabut_membuat_sasaran_tidak_berlaku_otomatis(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        baru = await _buat(perihal="SK baru")
        await _sahkan(lama["id"])
        await _sahkan(baru["id"])
        hasil = await rp.tambah_relasi_surat(
            baru["id"], RelasiIn(ke_id=lama["id"], jenis="mencabut",
                                 catatan="digantikan"), user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        return hasil, {s["id"]: s for s in daftar["items"]}, lama, baru
    hasil, peta, lama, baru = _jalan(skenario())
    assert hasil["sasaran"]["keberlakuan"] == "tidak_berlaku"
    assert peta[lama["id"]]["keberlakuan"] == "tidak_berlaku"
    assert peta[baru["id"]]["keberlakuan"] == "berlaku"
    assert "Tidak Berlaku" in peta[lama["id"]]["keberlakuan_label"]


def test_mengubah_membuat_sasaran_berlaku_dengan_perubahan(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        ralat = await _buat(perihal="Ralat")
        await _sahkan(lama["id"])
        await rp.tambah_relasi_surat(
            ralat["id"], RelasiIn(ke_id=lama["id"], jenis="mengubah"),
            user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        return {s["id"]: s for s in daftar["items"]}[lama["id"]]
    assert _jalan(skenario())["keberlakuan"] == "diubah"


def test_non_herleving_membatalkan_nomor_pencabut_menghidupkan_lagi(dbx):
    """Panah pencabutan hanya mati bila surat PENCABUTNYA DIBATALKAN nomornya
    (dokumen tak pernah sah). Sekadar pencabutnya ikut dicabut surat ketiga
    TIDAK menghidupkan kembali surat pertama (asas non-herleving)."""
    async def skenario():
        a = await _buat(perihal="SK A")
        b = await _buat(perihal="SK B pencabut")
        c = await _buat(perihal="SK C pencabut B")
        for s in (a, b, c):
            await _sahkan(s["id"])
        await rp.tambah_relasi_surat(
            b["id"], RelasiIn(ke_id=a["id"], jenis="mencabut"), user=USER)
        await rp.tambah_relasi_surat(
            c["id"], RelasiIn(ke_id=b["id"], jenis="mencabut"), user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        peta = {s["id"]: s["keberlakuan"] for s in daftar["items"]}
        # B dicabut C, tapi A TETAP tidak berlaku (tak hidup kembali).
        tahap1 = (peta[a["id"]], peta[b["id"]], peta[c["id"]])
        return tahap1
    assert _jalan(skenario()) == ("tidak_berlaku", "tidak_berlaku", "berlaku")


def test_pembatalan_nomor_pencabut_mematikan_panahnya(dbx):
    async def skenario():
        a = await _buat(perihal="SK A")
        b = await _buat(perihal="SK B pencabut keliru")
        await _sahkan(a["id"])
        await rp.tambah_relasi_surat(
            b["id"], RelasiIn(ke_id=a["id"], jenis="mencabut"), user=USER)
        # B masih dibooking → nomornya DIBATALKAN (salah terbit).
        await rp.transisi_surat(b["id"], TransisiIn(
            status="dibatalkan", alasan="draf keliru"), user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        return {s["id"]: s["keberlakuan"] for s in daftar["items"]}[a["id"]]
    assert _jalan(skenario()) == "berlaku", \
        "panah dari surat yang nomornya hangus tidak boleh tetap mencabut"


def test_relasi_lintas_satker_ditolak(dbx):
    async def skenario():
        milik_a = await _buat(user=USER)
        milik_b = await _buat(user=USER_LAIN)
        with pytest.raises(HTTPException) as ex:
            await rp.tambah_relasi_surat(
                milik_a["id"], RelasiIn(ke_id=milik_b["id"], jenis="mengubah"),
                user=USER)
        return ex.value.status_code
    assert _jalan(skenario()) == 403


def test_timeline_memuat_dua_arah_dan_keberlakuan_ujung(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        baru = await _buat(perihal="SK baru")
        await _sahkan(lama["id"])
        await _sahkan(baru["id"])
        await rp.tambah_relasi_surat(
            baru["id"], RelasiIn(ke_id=lama["id"], jenis="mencabut"),
            user=USER)
        return (await rp.timeline_surat(lama["id"], _user=USER),
                await rp.timeline_surat(baru["id"], _user=USER))
    tl_lama, tl_baru = _jalan(skenario())
    assert tl_lama["surat"]["keberlakuan"] == "tidak_berlaku"
    assert any("Dicabut oleh" in b["teks"] for b in tl_lama["timeline"])
    assert any("Mencabut" in b["teks"] for b in tl_baru["timeline"])
    # Ujung panah membawa keberlakuan lawan — dialog bisa menandai tanpa
    # fetch ulang.
    assert tl_baru["ujung"][tl_lama["surat"]["id"]]["keberlakuan"] == \
        "tidak_berlaku"


def test_hapus_surat_membersihkan_panah_gantung(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        baru = await _buat(perihal="SK baru")
        await _sahkan(lama["id"])
        await rp.tambah_relasi_surat(
            baru["id"], RelasiIn(ke_id=lama["id"], jenis="mencabut"),
            user=USER)
        # `baru` masih dibooking → boleh dihapus admin; panahnya wajib ikut.
        await rp.hapus_surat(baru["id"], user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        sisa_relasi = await dbx.surat_relasi.count_documents({})
        return ({s["id"]: s["keberlakuan"] for s in daftar["items"]}[lama["id"]],
                sisa_relasi)
    keberlakuan_lama, sisa = _jalan(skenario())
    assert sisa == 0
    assert keberlakuan_lama == "berlaku", \
        "surat tak boleh tetap 'dicabut oleh' dokumen yang sudah tak ada"


def test_hapus_relasi_salah_catat_memulihkan_keberlakuan(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        baru = await _buat(perihal="SK baru")
        await _sahkan(lama["id"])
        h = await rp.tambah_relasi_surat(
            baru["id"], RelasiIn(ke_id=lama["id"], jenis="mencabut"),
            user=USER)
        await rp.hapus_relasi_surat(h["relasi"]["id"], user=USER)
        daftar = await rp.daftar_surat(jenis="keluar", _user=USER)
        return {s["id"]: s["keberlakuan"] for s in daftar["items"]}[lama["id"]]
    assert _jalan(skenario()) == "berlaku"


def test_ekspor_csv_berkolom_keberlakuan(dbx):
    async def skenario():
        lama = await _buat(perihal="SK lama")
        baru = await _buat(perihal="SK baru")
        await _sahkan(lama["id"])
        await rp.tambah_relasi_surat(
            baru["id"], RelasiIn(ke_id=lama["id"], jenis="mencabut"),
            user=USER)
        return await rp.export_agenda(jenis="keluar", _user=USER)
    resp = _jalan(skenario())
    teks = resp.body.decode("utf-8-sig")
    assert "Keberlakuan" in teks.splitlines()[0]
    assert "Tidak Berlaku" in teks
