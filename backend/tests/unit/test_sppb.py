"""SPPB — bukti bahwa barang persediaan benar-benar keluar dan benar-benar
diterima SESEORANG.

Permintaan pemilik: *"SPPB yang ditandatangani penerima barang persediaan
terkoneksi dengan master pegawai."*

Sisi MASUK sudah punya LPB sejak lama. Sisi KELUAR tidak punya apa-apa:
pengeluaran barang hanya meninggalkan baris jurnal — ada catatan bahwa stok
berkurang, tak ada naskah yang bisa ditandatangani penerimanya.

Yang dijaga di sini:

1. **SPPB terbit dari transaksi keluar**, dengan daftar barang yang dibekukan.
2. **Dua tanda tangan**: KPB yang memerintahkan keluar, dan PENERIMA yang
   membuktikan barangnya sampai. Blok penerima itulah inti dokumen ini.
3. **Gagal menerbitkan SPPB tidak menggagalkan transaksinya** — barangnya
   sudah keluar dan jurnalnya sudah tercatat.
4. **Nomor hanya dibooking bila diminta**, dan naskah tanpa nomor tetap sah.
"""
import asyncio

import pypdfium2 as pdfium
import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rp
import routes.ttd as rt
import sppb_utils as spu
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


# ── Helper murni ────────────────────────────────────────────────────────

JURNAL = [
    {"persediaan_id": "b1", "kode_barang": "K001", "nup": "1",
     "nama_barang": "Kertas A4 80gsm", "satuan": "Rim", "jumlah": 2,
     "harga_satuan": 50000, "total": 100000,
     "stok_sebelum": 10, "stok_sesudah": 8,
     "rincian_layer": [{"batch_id": "l1", "qty": 2}]},
]


def test_pembekuan_hanya_menyimpan_yang_dicetak():
    b = spu.baris_dari_jurnal(JURNAL)
    assert set(b[0]) == set(spu.FIELD_BARIS)
    # Rincian layer FIFO dan stok sebelum/sesudah tak muncul di naskah;
    # menyimpannya membuat register tampak menjanjikan kesetiaan yang tak
    # ia jamin.
    assert "rincian_layer" not in b[0] and "stok_sesudah" not in b[0]


def test_total_mengabaikan_baris_cacat_bukan_meledak():
    # Satu angka rusak tak boleh membuat SELURUH naskah gagal terbit.
    assert spu.total_nilai([{"total": 100}, {"total": "entah"},
                            {"total": 50}]) == 150.0
    assert spu.total_nilai(None) == 0.0


def test_kolom_tabel_sejajar_dengan_kepalanya():
    for baris in spu.isi_tabel(spu.baris_dari_jurnal(JURNAL)):
        assert len(baris) == len(spu.HEADERS) == len(spu.WIDTHS)


def test_perihal_agenda_satu_baris():
    assert "\n" not in spu.perihal_agenda("Pemakaian Habis Pakai")
    assert "Pemakaian Habis Pakai" in spu.perihal_agenda("Pemakaian Habis Pakai")


def test_nama_berkas_membawa_nomor_yang_aman():
    assert spu.nama_berkas() == "SPPB.pdf"
    assert "/" not in spu.nama_berkas("B-7/PL.01/2026")


def test_jumlah_barang_pesan_tak_ikut_menyusut_oleh_proyeksi():
    r = spu.ringkas_sppb({"jumlah_barang": 12, "items": [{"kode_barang": "K1"}]})
    assert r["jumlah_barang"] == 12


def test_pesan_menyebut_kedua_pihak():
    r = spu.ringkas_sppb({"penerima_nama": "Budi", "kpb_nama": "Siti"})
    assert r["pihak"] == ["Budi (Penerima)", "Siti (Kuasa Pengguna Barang)"]


# ── Register ────────────────────────────────────────────────────────────

@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, rt, su, tpn):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    for mod in (rp, rt):
        monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(rp, "jadwalkan_sync", _diam, raising=False)
    # mongomock: find_one_and_update + projection + return_document → None.
    from mongomock_motor import AsyncMongoMockCollection
    _asli = AsyncMongoMockCollection.find_one_and_update

    async def _fau(self, filter, update, **kw):
        kw.pop("projection", None)
        doc = await _asli(self, filter, update, **kw)
        if doc:
            doc.pop("_id", None)
        return doc

    monkeypatch.setattr(AsyncMongoMockCollection, "find_one_and_update", _fau)
    _jalan(fake.report_settings.insert_one({
        "type": "global", "nama_instansi": "Otorita Ibu Kota Nusantara",
        "tempat_laporan": "Nusantara",
        "kasatker_nama": "Siti Rahayu", "kasatker_nip": "197005052000032001",
        "kasatker_jabatan": "Kepala Biro Umum"}))
    _jalan(fake.persediaan.insert_one({
        "id": "b1", "kode_barang": "K001", "kode_satker": "401234",
        "nama_barang": "Kertas A4 80gsm", "satuan": "Rim", "version": 1,
        "stok": 10, "batas_kritis": 2,
        "batches": [{"batch_id": "l1", "qty": 10, "harga": 50000,
                     "expired": "", "tanggal": "2026-01-02"}]}))
    _jalan(fake.pegawai.insert_one({
        "id": "p1", "kode_satker": "401234", "nama": "Budi Santoso",
        "nip": "198001012005011001", "jabatan": "Pengelola BMN",
        "unit_kerja": "Bagian Umum", "status": "aktif",
        "status_kepegawaian": "PNS"}))
    return fake


@pytest.fixture()
def media(monkeypatch):
    simpan = {}

    async def _tulis(data, nama="", content_type="", metadata=None):
        simpan.update({"data": data, "nama": nama, "metadata": metadata or {}})
        return "file-1", {}

    import gerbang_media
    monkeypatch.setattr(gerbang_media, "tulis_media", _tulis)
    return simpan


def _massal(user=USER, **kw):
    payload = rp.TransaksiMassalIn(
        arah="keluar", jenis="habis_pakai",
        items=[rp.ItemMassalIn(persediaan_id="b1", jumlah=2)], **kw)
    return _jalan(_unwrap(rp.transaksi_massal)(payload, user=user))


def _teks(data):
    doc = pdfium.PdfDocument(data)
    return "\n".join(doc[i].get_textpage().get_text_range()
                     for i in range(len(doc)))


def _pdf(sppb_id, user=USER):
    resp = _jalan(_unwrap(rp.unduh_sppb)(sppb_id, _user=user))
    data = b"".join(_jalan(_kumpul(resp.body_iterator)))
    assert data[:5] == b"%PDF-"
    return _teks(data)


async def _kumpul(it):
    return [b async for b in it]


def test_transaksi_keluar_menerbitkan_sppb(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    assert hasil["sukses"] == 1
    assert hasil["sppb_id"]
    s = _jalan(dbx.persediaan_sppb.find_one({"id": hasil["sppb_id"]}))
    assert s["jumlah_barang"] == 1
    assert s["total_nilai"] == 100000
    assert s["penerima_nama"] == "Budi Santoso"
    assert s["kode_satker"] == "401234"


def test_transaksi_MASUK_tidak_menerbitkan_sppb(dbx):
    payload = rp.TransaksiMassalIn(
        arah="masuk", jenis="pembelian",
        items=[rp.ItemMassalIn(persediaan_id="b1", jumlah=1,
                               harga_satuan=1000)])
    hasil = _jalan(_unwrap(rp.transaksi_massal)(payload, user=USER))
    assert hasil["sppb_id"] == ""
    assert _jalan(dbx.persediaan_sppb.count_documents({})) == 0


def test_nomor_hanya_dibooking_bila_diminta(dbx, monkeypatch):
    panggilan = []
    import routes.persuratan as rsu

    async def _booking(*a, **k):
        panggilan.append(k)
        return "B-9/PL.01/2026", "sid-9"

    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _booking)
    tanpa = _massal(penerima_nip="198001012005011001")
    assert tanpa["nomor_sppb"] == "" and not panggilan
    dengan = _massal(penerima_nip="198001012005011001", booking_otomatis=True)
    assert dengan["nomor_sppb"] == "B-9/PL.01/2026"
    assert panggilan[0]["jenis_naskah"] == "Surat Perintah"
    assert panggilan[0]["referensi"] == "SPPB"


def test_naskah_tanpa_nomor_tetap_terbit(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    t = _pdf(hasil["sppb_id"])
    assert "SURAT PERINTAH PENGELUARAN BARANG" in t
    assert "..." in t, "nomor kosong dihilangkan, bukan diberi garis isian"


def test_gagal_menerbitkan_sppb_tak_membatalkan_transaksinya(dbx, monkeypatch):
    """Barangnya sudah keluar dan jurnalnya sudah tercatat; membatalkan
    transaksi yang sah karena dokumennya gagal disusun jauh lebih merusak."""
    # Kegagalan disuntikkan DI DALAM penerbitan (tulis register), bukan
    # dengan mengganti fungsinya: mengganti fungsinya justru melewati
    # penjaga try/except yang sedang diuji.
    import sppb_utils as _spu

    def _meledak(*a, **k):
        raise RuntimeError("register tak bisa ditulis")

    monkeypatch.setattr(_spu, "baris_dari_jurnal", _meledak)
    hasil = _massal(penerima_nip="198001012005011001")
    assert hasil["sppb_id"] == ""
    assert hasil["sukses"] == 1
    item = _jalan(dbx.persediaan.find_one({"id": "b1"}))
    assert item["stok"] == 8
    assert _jalan(dbx.transaksi_persediaan.count_documents({})) == 1


# ── Naskahnya ───────────────────────────────────────────────────────────

def test_pdf_memuat_barang_dan_KEDUA_penanda_tangan(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    t = _pdf(hasil["sppb_id"])
    assert "Kertas A4 80gsm" in t
    # Blok penerima adalah INTI dokumen ini — tanpanya SPPB hanya perintah
    # keluar yang tak pernah dibuktikan sampai ke tangan siapa pun.
    assert "Budi Santoso" in t and "Yang Menerima" in t
    assert "Siti Rahayu" in t and "Kuasa Pengguna Barang" in t
    assert "Nusantara," in t


def test_pdf_menyebut_unit_penerima_dari_master(dbx):
    hasil = _massal(penerima_nip="198001012005011001",
                    unit_penerima="Salah Ketik")
    assert "Bagian Umum" in _pdf(hasil["sppb_id"])


def test_daftar_beku_tak_berubah_walau_master_barang_berubah(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    _jalan(dbx.persediaan.update_one(
        {"id": "b1"}, {"$set": {"nama_barang": "Nama Sudah Diganti"}}))
    t = _pdf(hasil["sppb_id"])
    assert "Kertas A4 80gsm" in t and "Nama Sudah Diganti" not in t


def test_sppb_satker_lain_tak_bisa_diunduh(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    with pytest.raises(HTTPException) as e:
        _pdf(hasil["sppb_id"], user=LAIN)
    assert e.value.status_code in (403, 404)


def test_register_ter_scope_satker(dbx):
    _massal(penerima_nip="198001012005011001")
    milikku = _jalan(_unwrap(rp.daftar_sppb)(page=1, page_size=30, _user=USER))
    orang_lain = _jalan(_unwrap(rp.daftar_sppb)(page=1, page_size=30, _user=LAIN))
    assert milikku["total"] == 1 and orang_lain["total"] == 0


# ── Tanda tangan elektronik ─────────────────────────────────────────────

def test_doc_type_sppb_terdaftar():
    assert tpn.TAUT_TTD["sppb"]["koleksi"] == "persediaan_sppb"


def _kirim(sppb_id, user=USER, **kw):
    payload = rp.KirimTtdSppbIn(**kw)
    return _jalan(_unwrap(rp.kirim_ttd_sppb)(sppb_id, payload, user=user))


def test_dikirim_ke_KPB_lalu_PENERIMA(dbx, media):
    hasil = _kirim(_massal(penerima_nip="198001012005011001")["sppb_id"])
    # Urutannya tak sembarang: penerima menandatangani bahwa ia menerima
    # barang yang diperintahkan keluar, jadi perintahnya harus lebih dulu ada.
    assert [s["nama"] for s in hasil["links"]] == ["Siti Rahayu", "Budi Santoso"]


def test_pdf_dibekukan_ke_gridfs_dan_bertaut_maju(dbx, media):
    sid = _massal(penerima_nip="198001012005011001")["sppb_id"]
    hasil = _kirim(sid)
    assert media["data"][:5] == b"%PDF-"
    assert media["metadata"]["sppb_id"] == sid
    s = _jalan(dbx.persediaan_sppb.find_one({"id": sid}))
    assert s["signature_request_id"] == hasil["id"]


def test_ringkasan_pesan_menyebut_isi_dokumennya(dbx, media):
    sid = _massal(penerima_nip="198001012005011001")["sppb_id"]
    hasil = _kirim(sid)
    sr = _jalan(dbx.signature_requests.find_one({"id": hasil["id"]}))
    r = sr.get("ringkas") or {}
    assert r["jumlah_barang"] == 1
    assert r["barang"][0]["nama"] == "Kertas A4 80gsm"
    assert "Budi Santoso (Penerima)" in r["pihak"]


def test_sppb_satker_lain_tak_bisa_dikirim(dbx, media, monkeypatch):
    """Penolakannya harus terjadi SEBELUM dokumennya disusun."""
    sid = _massal(penerima_nip="198001012005011001")["sppb_id"]
    with pytest.raises(HTTPException) as e:
        _kirim(sid, user=LAIN)
    assert e.value.status_code in (403, 404)
    assert _jalan(dbx.signature_requests.count_documents({})) == 0


def test_riwayat_menampilkan_status_ttd(dbx, media):
    sid = _massal(penerima_nip="198001012005011001")["sppb_id"]
    _kirim(sid)
    daftar = _jalan(_unwrap(rp.daftar_sppb)(page=1, page_size=30, _user=USER))
    assert (daftar["items"][0].get("ttd") or {}).get("jumlah") == 2
