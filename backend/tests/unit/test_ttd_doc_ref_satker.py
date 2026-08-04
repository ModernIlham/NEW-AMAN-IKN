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


# ── Regresi 500 "membubuhi & minta TTD" (laporan pemilik) ───────────────────
#
# `buat_permintaan` meng-import `scope_query_field_satker` DI DALAM cabang
# `if doc_type in {bast,lpb} ...`. Import lokal membuat namanya LOKAL untuk
# SELURUH badan fungsi (aturan scoping Python), sehingga pemakaian di gerbang
# "Meninggal Dunia" — cabang yang berjalan untuk SEMUA doc_type — meledak
# UnboundLocalError → 500 pada `POST /ttd/permintaan/unggah` maupun
# `POST /ttd/permintaan` biasa, tiap kali ada penanda tangan ber-NIP.

def test_permintaan_dokumen_unggahan_dengan_nip_tak_meledak(dbx):
    """doc_type di luar {bast,lpb} + penanda tangan ber-NIP harus SUKSES.
    Inilah jalur "unggah dokumen lalu minta TTD" yang dilaporkan 500."""
    async def skenario():
        return await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen Unggahan", doc_type="dokumen_unggahan",
                doc_ref="", mode="paralel",
                signers=[rt.SignerIn(nama="Budi Penanda",
                                     nip="198001012005011001",
                                     jabatan="Kepala")]),
            user=USER_A)
    hasil = _jalan(skenario())
    assert len(hasil["links"]) == 1
    assert hasil["links"][0]["nama"] == "Budi Penanda"


def test_gerbang_meninggal_tetap_menolak_pada_doc_type_bebas(dbx):
    """Perbaikan tak boleh mematikan gerbangnya: penanda tangan berstatus
    meninggal tetap ditolak 400 walau doc_type bukan bast/lpb."""
    async def skenario():
        await dbx.pegawai.insert_one({
            "id": "p-1", "kode_satker": USER_A["kode_satker"],
            "nama": "Almarhum Contoh", "nip": "196001011985031001",
            "status": "meninggal"})
        return await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen", doc_type="dokumen", doc_ref="",
                mode="paralel",
                signers=[rt.SignerIn(nama="Almarhum Contoh",
                                     nip="196001011985031001")]),
            user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400
    assert "Meninggal Dunia" in e.value.detail


# ── Posisi QR: SEKALI di akhir oleh pemilik, bukan per penanda tangan ───────
#
# Mandat pemilik: fitur geser & perbesar QR dicabut dari halaman penanda
# tangan (tiap orang mengaturnya membingungkan, dan yang terakhir menang),
# lalu dipasang di langkah unduh dokumen ber-TTD — sekali jalan.

def _sr_dok(**ganti):
    dasar = {"id": "sr-dok", "judul": "Dokumen", "doc_type": "dokumen_unggahan",
             "doc_ref": "", "mode": "paralel", "status": "terkirim",
             "kode_satker": USER_A["kode_satker"], "created_by": USER_A["username"],
             "dok_file_id": "abc123", "dok_nama": "d.pdf", "dok_halaman": 2,
             "signers": []}
    dasar.update(ganti)
    return dasar


def test_spesimen_tak_lagi_menerima_posisi_qr(dbx):
    """Kontrak payload penanda tangan: field `posisi_qr` DIHAPUS — kiriman
    lama yang masih menyertakannya tidak boleh menyetel apa pun."""
    assert "posisi_qr" not in rt.SpesimenIn.model_fields
    s = rt.SpesimenIn(png_base64="x", posisi=None, posisi_qr={"halaman": 1})
    assert not hasattr(s, "posisi_qr")


def test_pemilik_atur_posisi_qr_tersimpan_terjepit(dbx):
    """Posisi tersimpan dan DIJEPIT: lebar di luar 0,10–0,40 ditarik ke batas,
    halaman di luar jumlah halaman dokumen ikut dijepit."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        r = await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr={"halaman": 9, "x": 0.5,
                                               "y": 0.5, "lebar": 0.99}),
            user=USER_A)
        return r, await dbx.signature_requests.find_one({"id": "sr-dok"})
    r, doc = _jalan(skenario())
    assert r["posisi_qr"]["lebar"] == 0.40      # dijepit dari 0,99
    assert r["posisi_qr"]["halaman"] == 2       # dijepit ke jumlah halaman
    assert doc["posisi_qr"]["lebar"] == 0.40    # benar-benar tersimpan


def test_posisi_qr_null_mengembalikan_ke_otomatis(dbx):
    async def skenario():
        await dbx.signature_requests.insert_one(
            _sr_dok(posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2}))
        r = await rt.atur_posisi_qr("sr-dok", rt.PosisiQrIn(posisi_qr=None),
                                    user=USER_A)
        return r, await dbx.signature_requests.find_one({"id": "sr-dok"})
    r, doc = _jalan(skenario())
    assert r["posisi_qr"] is None and doc["posisi_qr"] is None


def test_posisi_qr_satker_lain_ditolak(dbx):
    """Isolasi satker: dokumen satker A tak bisa diatur QR-nya oleh satker B."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr=None), user=USER_B)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_posisi_qr_tanpa_dokumen_ditolak_400(dbx):
    """Permintaan tanpa lampiran dokumen tak punya halaman untuk menaruh QR."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok(dok_file_id=""))
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr={"halaman": 1, "x": 0, "y": 0,
                                               "lebar": 0.2}), user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400
