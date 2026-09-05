"""Nota Dinas persediaan tersambung ke TTD elektronik.

Bagian kedua permintaan pemilik: *"saya tidak melihat integrasi nomer surat dan
permintaan ttd elektroniknya untuk memudahkan."* Nomornya sudah; ini tanda
tangannya.

Yang dijaga:

1. **`doc_type` terdaftar di registry satu pintu** — gerbang kepemilikan,
   tautan maju, dan ringkasan status di layar dokumen semuanya diturunkan dari
   sana. `doc_type` yang tercecer kehilangan ketiganya tanpa satu pun galat.
2. **Penanda tangannya yang DIBEKUKAN di nota**, bukan KPB yang berlaku hari
   ini — mengirim ke pejabat yang namanya tak tercetak di blok tanda tangan
   adalah meminta orang meneken dokumen atas nama orang lain.
3. **PDF dibekukan ke GridFS saat dikirim** — penanda tangan meneken dokumen
   yang benar-benar ia baca.
4. **Pesan penanda tangannya menyebut isi dokumen**, bukan hanya judul +
   tautan (keluhan yang sudah diperbaiki untuk BAST lalu terulang pada LPB).
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import persediaan_nota_utils as pnu
import routes.persediaan as rp
import routes.ttd as rt
import ttd_penautan as tpn

USER = {"username": "op1", "role": "operator", "kode_satker": "401234"}
LAIN = {"username": "op2", "role": "operator", "kode_satker": "509999"}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, rt, su, tpn):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    for mod in (rp, rt):
        monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    _jalan(fake.report_settings.insert_one({
        "type": "global", "nama_instansi": "Otorita Ibu Kota Nusantara",
        "tempat_laporan": "Nusantara"}))
    _jalan(fake.persediaan_nota.insert_one({
        "id": "nota-1", "kode_satker": "401234", "jenis": "kritis",
        "tanggal": "2026-09-05", "horizon_hari": 30, "seleksi": False,
        "yth": "Pejabat Pengadaan", "hal": pnu.hal("kritis"),
        "items": [{"id": "b1", "kode_barang": "K001",
                   "nama_barang": "Kertas A4 80gsm", "satuan": "Rim",
                   "stok": 0, "batas_kritis": 5}],
        "jumlah_barang": 1, "nomor": "B-7/PL.01/2026", "surat_id": "sid-1",
        "kpb_nama": "Budi Santoso", "kpb_nip": "198001012005011001",
        "kpb_jenis_pelaksana": "", "kpb_status_kepegawaian": "PNS",
        "created_by": "op1", "created_at": "2026-09-05T00:00:00+00:00",
        "updated_at": "2026-09-05T00:00:00+00:00"}))
    return fake


@pytest.fixture()
def media(monkeypatch):
    """GridFS tiruan — menangkap byte yang DIBEKUKAN saat pengiriman."""
    simpan = {}

    async def _tulis(data, nama="", content_type="", metadata=None):
        simpan["data"] = data
        simpan["nama"] = nama
        simpan["metadata"] = metadata or {}
        return "file-1", {}

    import gerbang_media
    monkeypatch.setattr(gerbang_media, "tulis_media", _tulis)
    return simpan


def _kirim(nid="nota-1", user=USER, **kw):
    payload = rp.KirimTtdNotaIn(**kw)
    return _jalan(_unwrap(rp.kirim_ttd_nota_dinas)(nid, payload, user=user))


# ── Registry satu pintu ─────────────────────────────────────────────────

def test_doc_type_terdaftar_dengan_koleksinya():
    info = tpn.TAUT_TTD["nota_persediaan"]
    assert info["koleksi"] == "persediaan_nota"
    assert info["label"].strip()


# ── Pengiriman ──────────────────────────────────────────────────────────

def test_penanda_tangan_bawaan_adalah_KPB_YANG_DIBEKUKAN(dbx, media,
                                                         monkeypatch):
    async def _kpb_hari_ini(*a, **k):
        return {"nama": "Siti Rahayu", "nip": "199002022010012002"}

    monkeypatch.setattr(rp, "_kpb_signer", _kpb_hari_ini)
    hasil = _kirim()
    nama = [s["nama"] for s in hasil["links"]]
    assert nama == ["Budi Santoso"], (
        "dikirim ke pejabat yang namanya TIDAK tercetak di blok tanda tangan")


def test_tautan_maju_ditulis_ke_notanya(dbx, media):
    hasil = _kirim()
    nota = _jalan(dbx.persediaan_nota.find_one({"id": "nota-1"}))
    assert nota["signature_request_id"] == hasil["id"]
    assert nota.get("tt_dikirim_pada")


def test_pdf_dibekukan_ke_gridfs_saat_dikirim(dbx, media):
    hasil = _kirim()
    assert media["data"][:5] == b"%PDF-"
    assert media["metadata"]["nota_id"] == "nota-1"
    # Nama berkasnya membawa nomor surat — dua nota terbit pada bulan yang
    # sama tak boleh saling menimpa di daftar dokumen TTD.
    assert "B-7" in media["nama"]
    sr = _jalan(dbx.signature_requests.find_one({"id": hasil["id"]}))
    assert sr["dok_file_id"] == "file-1" and sr["dok_nama"] == media["nama"]


def test_dokumen_yang_dibekukan_memuat_daftar_beku_notanya(dbx, media):
    import pypdfium2 as pdfium
    _kirim()
    doc = pdfium.PdfDocument(media["data"])
    teks = "\n".join(doc[i].get_textpage().get_text_range()
                     for i in range(len(doc)))
    assert "Kertas A4 80gsm" in teks
    assert "B-7/PL.01/2026" in teks, "naskah yang diteken tak menyebut nomornya"


def test_signer_manual_menggantikan_bawaan(dbx, media):
    hasil = _kirim(signers=[{"nama": "Andi Wijaya", "nip": "",
                             "jabatan": "Sekretaris", "email": ""}])
    assert [s["nama"] for s in hasil["links"]] == ["Andi Wijaya"]


def test_nota_tanpa_KPB_menolak_dengan_alasan_yang_bisa_ditindaklanjuti(dbx,
                                                                       media):
    _jalan(dbx.persediaan_nota.update_one({"id": "nota-1"},
                                          {"$set": {"kpb_nama": ""}}))
    with pytest.raises(HTTPException) as e:
        _kirim()
    assert e.value.status_code == 400
    assert "Referensi Pejabat" in e.value.detail


def test_nota_satker_lain_tidak_bisa_dikirim(dbx, media, monkeypatch):
    """Penolakannya harus terjadi SEBELUM dokumennya disusun.

    Mutasi yang melepas gerbang di jalur nota mula-mula SELAMAT: permintaannya
    tetap gagal, tetapi oleh gerbang milik `buat_permintaan` — yang hidup dari
    keanggotaan `doc_type` di registry TAUT_TTD. Mencabut nota dari registry
    kelak akan mematikan gerbang itu tanpa satu pun test menagihnya, sementara
    isi dokumen satker lain sudah terlanjur disusun di memori.
    """
    dipanggil = []
    asli = rp.bangun_nota_dinas_pdf

    async def _rekam(*a, **k):
        dipanggil.append(1)
        return await asli(*a, **k)

    monkeypatch.setattr(rp, "bangun_nota_dinas_pdf", _rekam)
    with pytest.raises(HTTPException) as e:
        _kirim(user=LAIN)
    assert e.value.status_code in (403, 404)
    assert not dipanggil, "dokumen satker lain terlanjur disusun"
    assert _jalan(dbx.signature_requests.count_documents({})) == 0


def test_nota_tak_dikenal_menghasilkan_404(dbx, media):
    with pytest.raises(HTTPException) as e:
        _kirim(nid="entah")
    assert e.value.status_code == 404


# ── Pesan penanda tangan ────────────────────────────────────────────────

def test_ringkasan_pesan_menyebut_isi_dokumen_bukan_hanya_judul(dbx, media):
    hasil = _kirim()
    sr = _jalan(dbx.signature_requests.find_one({"id": hasil["id"]}))
    r = sr.get("ringkas") or {}
    assert r.get("nomor") == "B-7/PL.01/2026"
    assert r.get("perihal") == pnu.perihal_agenda("kritis")
    assert r.get("jumlah_barang") == 1
    assert r["barang"][0]["nama"] == "Kertas A4 80gsm"
    assert "Budi Santoso (Kuasa Pengguna Barang)" in (r.get("pihak") or [])


def test_jumlah_barang_pesan_tak_ikut_menyusut_oleh_proyeksi():
    # `items` bisa terpotong pembacaan; angkanya bermakna "berapa barang di
    # nota" dan harus tetap menyebut keseluruhan.
    r = pnu.ringkas_nota({"jenis": "kritis", "jumlah_barang": 12,
                          "items": [{"kode_barang": "K1", "nama_barang": "A"}]})
    assert r["jumlah_barang"] == 12
    assert len(r["barang"]) == 1


def test_barang_di_pesan_dibatasi_agar_pesannya_tak_meluber():
    banyak = [{"kode_barang": f"K{i}", "nama_barang": f"Barang {i}"}
              for i in range(20)]
    r = pnu.ringkas_nota({"jenis": "kritis", "items": banyak,
                          "jumlah_barang": 20})
    assert len(r["barang"]) == pnu.MAKS_BARANG_PESAN
    assert r["jumlah_barang"] == 20


# ── Status di riwayat ───────────────────────────────────────────────────

def test_riwayat_menampilkan_status_ttd_tiap_nota(dbx, media):
    _kirim()
    daftar = _jalan(_unwrap(rp.daftar_nota_dinas)(
        page=1, page_size=30, jenis="", _user=USER))
    ttd = daftar["items"][0].get("ttd")
    assert ttd and ttd.get("id"), "riwayat tak tahu notanya sudah dikirim"
    assert ttd.get("jumlah") == 1


def test_nota_yang_belum_dikirim_bertanda_None_bukan_dict_kosong(dbx, media):
    daftar = _jalan(_unwrap(rp.daftar_nota_dinas)(
        page=1, page_size=30, jenis="", _user=USER))
    assert daftar["items"][0]["ttd"] is None
