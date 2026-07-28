"""Uji GERBANG KEPEMILIKAN `doc_ref` pada permintaan tanda tangan.

Temuan audit adversarial (TINGGI). `kirim_tandatangan` menulis back-link ke
dokumen yang ditunjuk `doc_ref` TANPA memeriksa satker — itu disengaja, karena
pemeriksaannya dilakukan SEKALI di muka saat permintaan dibuat. Konsekuensinya:
setiap `doc_type` yang punya back-link WAJIB terdaftar di gerbang itu.

`lpb` sempat punya back-link tanpa gerbang. `POST /persediaan/lpb/{id}/kirim-ttd`
memang ber-guard, tetapi `POST /ttd/permintaan` bisa dipanggil langsung dengan
`doc_type="lpb"` + id LPB satker lain — dan saat tandatangan selesai, servernya
sendiri yang menulis ke dokumen satker itu.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt

# Dua satker, dua penulis. Yang satu mencoba menunjuk dokumen yang lain.
USER_A = {"username": "penulis-a", "role": "admin", "kode_satker": "111111"}
USER_B = {"username": "penulis-b", "role": "admin", "kode_satker": "222222"}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rt, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "send_esign_email", _diam, raising=False)
    return fake


def _permintaan(doc_type, doc_ref):
    return rt.PermintaanIn(
        judul="Uji", doc_type=doc_type, doc_ref=doc_ref, mode="paralel",
        signers=[rt.SignerIn(nama="Penanda Tangan")])


async def _seed(dbx):
    await dbx.lpb.insert_one({"id": "lpb-B", "kode_satker": "222222",
                              "nomor": "LPB-B/2026"})
    await dbx.bast_serah_terima.insert_one({"id": "bast-B",
                                            "kode_satker": "222222"})


def test_lpb_satker_lain_ditolak_403(dbx):
    """INTI: satker A tak boleh menunjuk LPB milik satker B."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "lpb-B"),
                                              user=USER_A)
        assert e.value.status_code == 403
        assert "LPB" in str(e.value.detail)
        # Tak ada permintaan yang tersisa — penolakan terjadi sebelum insert.
        assert await dbx.signature_requests.count_documents({}) == 0
    _jalan(skenario())


def test_bast_satker_lain_tetap_ditolak_403(dbx):
    """Perlindungan lama tak boleh ikut rusak saat gerbangnya digeneralisasi."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("bast", "bast-B"),
                                              user=USER_A)
        assert e.value.status_code == 403
        assert "BAST" in str(e.value.detail)
    _jalan(skenario())


def test_lpb_milik_sendiri_diterima(dbx):
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "lpb-B"),
                                                  user=USER_B)
        assert hasil["id"]
        sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
        assert sr["doc_type"] == "lpb" and sr["doc_ref"] == "lpb-B"
        assert sr["kode_satker"] == "222222"
    _jalan(skenario())


def test_lpb_yang_tak_ada_juga_ditolak(dbx):
    """id ngawur ditolak sama kerasnya — pesannya tak membedakan 'tak ada'
    dari 'milik orang lain' (cegah oracle keberadaan dokumen)."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "tidak-ada"),
                                              user=USER_B)
        assert e.value.status_code == 403
    _jalan(skenario())


def test_doc_type_tanpa_backlink_tak_ikut_divalidasi(dbx):
    """`doc_ref` untuk surat/register adalah teks bebas tanpa back-link —
    memvalidasinya akan mematahkan alur yang memang memakainya begitu."""
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(
            _permintaan("dokumen_unggahan", "No. 123/BEBAS/2026"), user=USER_A)
        assert hasil["id"]
    _jalan(skenario())


def test_super_admin_lintas_satker_tetap_boleh(dbx):
    """kode_satker kosong = super-admin; itu perilaku yang disengaja."""
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(
            _permintaan("lpb", "lpb-B"),
            user={"username": "sa", "role": "admin", "kode_satker": ""})
        assert hasil["id"]
    _jalan(skenario())
