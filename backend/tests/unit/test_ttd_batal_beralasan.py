"""Pembatalan permintaan TTD WAJIB beralasan.

Permintaan pemilik: *"ketika diklik pembatalan permintaan di ttd elektronik,
munculkan kotak penjelasan alasannya kenapa."*

Sebelumnya pembatalan hanya dijaga konfirmasi ya/tidak. Konfirmasi menahan
salah-tekan, tetapi tak menjawab pertanyaan yang PASTI muncul sesudahnya:
seluruh tautan penanda tangan mati permanen, tautan verifikasi yang tercetak
sebagai QR ikut dicabut, dan bila permintaan menaut BAST/LPB maka dokumen itu
beserta asetnya ditandai ``tt_dicabut``. Yang bertanya "kenapa?" bukan hanya
pemeriksa audit, melainkan orang-orang di dalam permintaan itu sendiri.

Sejajar dengan pembatalan surat keluar di Persuratan, yang juga wajib
beralasan karena menghanguskan nomor agenda.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt

USER_A = {"username": "penulis-a", "role": "admin", "kode_satker": "111111"}
USER_B = {"username": "penulis-b", "role": "admin", "kode_satker": "222222"}
OPERATOR_A = {"username": "operator-a", "role": "operator", "kode_satker": "111111"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    import tautan_pendek_utils as tp
    for mod in (rt, su, tp):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "send_esign_email", _diam, raising=False)
    return fake


def _sr(**ganti):
    doc = {"id": "sr-1", "kode_satker": USER_A["kode_satker"],
           "created_by": USER_A["username"], "judul": "Dokumen Uji",
           "status": "terkirim", "doc_type": "dokumen_unggahan", "doc_ref": "",
           "signers": [{"signer_id": "s-1", "nama": "Budi", "status": "aktif"}]}
    doc.update(ganti)
    return doc


async def _batal(dbx, alasan, user=USER_A, sr=None):
    await dbx.signature_requests.insert_one(sr or _sr())
    return await rt.batal_permintaan_beralasan(
        "sr-1", rt.BatalPermintaanIn(alasan=alasan), user=user)


# ── Alasan wajib ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("alasan", ["", "   ", "x", "abcd", "\n\t "])
def test_alasan_kosong_atau_terlalu_pendek_ditolak(dbx, alasan):
    """Bukan sekadar "tidak kosong": satu spasi atau "x" lolos uji tak-kosong
    tetapi tak menjelaskan apa pun, padahal inilah satu-satunya catatan
    mengapa tautan orang lain dimatikan."""
    with pytest.raises(HTTPException) as e:
        _jalan(_batal(dbx, alasan))
    assert e.value.status_code == 400
    assert "alasan" in str(e.value.detail).lower()


def test_permintaan_tetap_hidup_saat_alasannya_ditolak(dbx):
    """Penolakan harus BATAL TOTAL — bukan sekadar tak mencatat alasan."""
    async def skenario():
        with pytest.raises(HTTPException):
            await _batal(dbx, "")
        return await dbx.signature_requests.find_one({"id": "sr-1"}, {"_id": 0, "status": 1})
    assert _jalan(skenario())["status"] == "terkirim"


def test_alasan_memadai_membatalkan_dan_tersimpan(dbx):
    async def skenario():
        r = await _batal(dbx, "Dokumen salah unggah, akan dikirim ulang")
        doc = await dbx.signature_requests.find_one({"id": "sr-1"}, {"_id": 0})
        return r, doc
    r, doc = _jalan(skenario())
    assert r["ok"] is True
    assert doc["status"] == "batal"
    assert doc["batal_alasan"] == "Dokumen salah unggah, akan dikirim ulang"
    assert doc["batal_oleh"] == USER_A["username"]
    assert doc["batal_pada"]


def test_alasan_dirapikan_spasinya(dbx):
    """Spasi ganda/baris baru dari textarea tak boleh ikut tersimpan mentah."""
    async def skenario():
        await _batal(dbx, "  Dokumen   salah\n\nunggah  ")
        return await dbx.signature_requests.find_one({"id": "sr-1"}, {"_id": 0, "batal_alasan": 1})
    assert _jalan(skenario())["batal_alasan"] == "Dokumen salah unggah"


def test_alasan_sangat_panjang_dipotong(dbx):
    """Batas simpan menjaga dokumen & baris audit tetap wajar."""
    async def skenario():
        await _batal(dbx, "A" * 2000)
        return await dbx.signature_requests.find_one({"id": "sr-1"}, {"_id": 0, "batal_alasan": 1})
    assert len(_jalan(skenario())["batal_alasan"]) == 500


# ── Urutan pemeriksaan ─────────────────────────────────────────────────────

def test_bukan_pemilik_ditolak_403_bukan_400(dbx):
    """Otorisasi didahulukan: pemanggil tak berhak tidak diberi umpan balik
    tentang bentuk masukan yang benar."""
    with pytest.raises(HTTPException) as e:
        _jalan(_batal(dbx, "", user=OPERATOR_A))
    assert e.value.status_code == 403


def test_satker_lain_ditolak_meski_alasannya_benar(dbx):
    with pytest.raises(HTTPException) as e:
        _jalan(_batal(dbx, "Alasan yang memadai", user=USER_B))
    assert e.value.status_code == 403


def test_permintaan_tak_dikenal_404(dbx):
    async def skenario():
        return await rt.batal_permintaan_beralasan(
            "sr-tak-ada", rt.BatalPermintaanIn(alasan="Alasan memadai"), user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 404


# ── Jejak audit ────────────────────────────────────────────────────────────

def test_alasan_ikut_ke_jejak_audit(dbx, monkeypatch):
    """Bidang pada dokumen menjawab "kenapa" bagi pengguna; baris audit
    menjawabnya bagi pemeriksa. Keduanya harus memuat alasan yang sama."""
    dicatat = {}

    async def _rekam(aksi, _a, sasaran, username="", detail="", **k):
        dicatat.update(aksi=aksi, sasaran=sasaran, username=username, detail=detail)

    monkeypatch.setattr(rt, "log_audit", _rekam, raising=False)
    _jalan(_batal(dbx, "Penanda tangan sudah pensiun"))
    assert dicatat["aksi"] == "batal_ttd"
    assert dicatat["username"] == USER_A["username"]
    assert "Penanda tangan sudah pensiun" in dicatat["detail"]


# ── Jalur DELETE lama ──────────────────────────────────────────────────────

def test_delete_lama_juga_menuntut_alasan(dbx):
    """Menyisakan satu jalur tanpa alasan berarti syaratnya cuma hiasan."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr())
        return await rt.batal_permintaan("sr-1", user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400


def test_delete_lama_dengan_alasan_tetap_bekerja(dbx):
    """Pemanggil lama yang menyesuaikan diri tidak perlu pindah endpoint."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr())
        await rt.batal_permintaan("sr-1", alasan="Salah tujuan", user=USER_A)
        return await dbx.signature_requests.find_one({"id": "sr-1"}, {"_id": 0})
    doc = _jalan(skenario())
    assert doc["status"] == "batal" and doc["batal_alasan"] == "Salah tujuan"


# ── Cascade tetap jalan ────────────────────────────────────────────────────

def test_cascade_bast_tetap_berjalan_dengan_alasan(dbx):
    """Syarat alasan tak boleh mengubah dampak pembatalan — hanya menambah
    catatan tentangnya."""
    async def skenario():
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-1", "kode_satker": USER_A["kode_satker"],
            "signature_request_id": "sr-1"})
        await dbx.assets.insert_one({
            "id": "aset-1", "kode_satker": USER_A["kode_satker"],
            "bast_terakhir": {"id": "bast-1"}})
        await _batal(dbx, "BAST keliru, akan diterbitkan ulang",
                     sr=_sr(doc_type="bast", doc_ref="bast-1"))
        b = await dbx.bast_serah_terima.find_one({"id": "bast-1"}, {"_id": 0})
        a = await dbx.assets.find_one({"id": "aset-1"}, {"_id": 0})
        return b, a
    b, a = _jalan(skenario())
    assert b["tt_dicabut"] is True
    assert a["bast_terakhir"]["tt_dicabut"] is True
