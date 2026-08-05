"""Ringkasan LPB untuk pesan WA/email permintaan tanda tangan.

Keluhan pemilik yang sudah diperbaiki untuk BAST: "pesan share link lewat
WhatsApp tidak sama formatnya dengan yang di TTD elektronik". Perbaikan itu
BERHENTI di BAST — `_ringkas_dokumen` mengembalikan `{}` untuk doc_type lain,
sehingga permintaan TTD LPB terbit dengan ringkasan kosong dan pesannya
menyusut jadi "judul + tautan".

Kesalahannya tak terlihat: tak ada galat, tautannya benar, pesannya cuma
lebih pendek. Uji di bawah mengunci isi ringkasannya supaya diam-diam
mengosong lagi akan ketahuan.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt
from routes.ttd import MAKS_BARANG_RINGKAS, ringkas_lpb

LPB_PERSEDIAAN = {
    "nomor": "LPB-12/OIKN/2026",
    "tanggal": "2026-08-05T00:00:00Z",
    "penyedia": "PT Sumber Makmur",
    "ppk_nama": "Budi Santoso",
    "jumlah_barang": 7,
    "items": [
        {"kode_barang": "1234567890123456", "nup": "", "nama_barang": "Kertas A4"},
        {"kode_barang": "6543210987654321", "nup": "", "nama_barang": "Tinta Printer"},
    ],
}

LPB_ASET = {**LPB_PERSEDIAAN, "kategori": "aset",
            "items": [{"kode_barang": "3.05.01.01.001", "nup": "12",
                       "nama_barang": "Laptop"}]}


class TestIsiRingkasanLpb:
    def test_membawa_nomor_tanggal_dan_barang(self):
        r = ringkas_lpb(LPB_PERSEDIAAN)
        assert r["nomor"] == "LPB-12/OIKN/2026"
        assert r["tanggal"] == "2026-08-05"        # jam dibuang
        assert r["barang"][0] == {"kode": "1234567890123456", "nup": "",
                                  "nama": "Kertas A4"}

    def test_pihak_lpb_adalah_penyedia_dan_ppk(self):
        """Bukan pihak pertama/kedua seperti BAST — LPB memang bukan dokumen
        dua-pihak; yang bermakna di sini penyerah barang & pemegang komitmen."""
        assert ringkas_lpb(LPB_PERSEDIAAN)["pihak"] == [
            "PT Sumber Makmur (Penyedia)", "Budi Santoso (PPK)"]

    def test_perihal_membedakan_bmn_dan_persediaan(self):
        assert "Persediaan" in ringkas_lpb(LPB_PERSEDIAAN)["perihal"]
        assert "BMN" in ringkas_lpb(LPB_ASET)["perihal"]

    def test_dokumen_era_lama_tanpa_kategori_dianggap_persediaan(self):
        """`kategori` baru ada setelah LPB aset diperkenalkan; dokumen lama
        memang hanya dipakai persediaan."""
        assert "Persediaan" in ringkas_lpb({"items": []})["perihal"]

    def test_nup_ikut_untuk_lpb_aset(self):
        """NUP-lah seluruh guna LPB aset — membuktikan NUP mana yang masuk."""
        assert ringkas_lpb(LPB_ASET)["barang"][0]["nup"] == "12"


class TestJumlahBarangJujur:
    def test_jumlah_tersimpan_dipakai_bukan_panjang_potongan(self):
        """Barang ditampilkan maksimal 3 baris, tapi ANGKANYA harus tetap 7 —
        kalau memakai len(items) yang sudah terpotong, pesan resmi menyebut
        barang lebih sedikit daripada yang benar-benar diterima."""
        r = ringkas_lpb(LPB_PERSEDIAAN)
        assert r["jumlah_barang"] == 7
        assert len(r["barang"]) == 2

    def test_dokumen_lama_tanpa_jumlah_barang_jatuh_ke_panjang_items(self):
        d = {**LPB_PERSEDIAAN}
        d.pop("jumlah_barang")
        assert ringkas_lpb(d)["jumlah_barang"] == 2

    def test_jumlah_barang_rusak_tak_meledak(self):
        d = {**LPB_PERSEDIAAN, "jumlah_barang": "banyak"}
        assert ringkas_lpb(d)["jumlah_barang"] == 2   # jatuh ke len(items)

    def test_barang_dipotong_di_batas_yang_sama_dengan_bast(self):
        d = {**LPB_PERSEDIAAN,
             "items": [{"kode_barang": f"K{i}", "nama_barang": f"B{i}"}
                       for i in range(10)]}
        assert len(ringkas_lpb(d)["barang"]) == MAKS_BARANG_RINGKAS


class TestTahanDataSetengahJadi:
    def test_dokumen_kosong_tak_meledak(self):
        r = ringkas_lpb({})
        assert r["nomor"] == "" and r["pihak"] == [] and r["barang"] == []
        assert r["jumlah_barang"] == 0

    def test_none_tak_meledak(self):
        assert ringkas_lpb(None)["barang"] == []

    def test_tanpa_penyedia_hanya_ppk_yang_disebut(self):
        d = {**LPB_PERSEDIAAN, "penyedia": "  "}
        assert ringkas_lpb(d)["pihak"] == ["Budi Santoso (PPK)"]

    def test_baris_barang_kosong_dibuang_bukan_jadi_baris_hampa(self):
        """Baris tanpa kode DAN tanpa nama tak boleh muncul sebagai ' — ' di
        pesan WA."""
        d = {**LPB_PERSEDIAAN,
             "items": [{"kode_barang": "", "nama_barang": ""},
                       {"kode_barang": "K1", "nama_barang": "Meja"}]}
        assert ringkas_lpb(d)["barang"] == [{"kode": "K1", "nup": "",
                                             "nama": "Meja"}]

    def test_item_None_di_dalam_array_tak_meledak(self):
        d = {**LPB_PERSEDIAAN, "items": [None, {"kode_barang": "K1"}]}
        assert ringkas_lpb(d)["barang"] == [{"kode": "K1", "nup": "", "nama": ""}]

    def test_items_bukan_array_tak_meledak(self):
        assert ringkas_lpb({"items": None})["barang"] == []


class TestBentuknyaCocokDenganPenyusunPesan:
    """Kunci bidang yang dibaca `frontend/src/lib/pesanTtd.js`.

    Ringkasan yang benar isinya tapi salah nama kuncinya sama saja dengan
    kosong: pesannya tetap menyusut, dan tak ada yang gagal.
    """
    def test_kunci_wajib_ada_semua(self):
        r = ringkas_lpb(LPB_PERSEDIAAN)
        assert set(r) == {"nomor", "perihal", "tanggal", "pihak", "barang",
                          "jumlah_barang"}

    def test_kunci_tiap_barang_kode_nup_nama(self):
        assert set(ringkas_lpb(LPB_ASET)["barang"][0]) == {"kode", "nup", "nama"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rt, "db", fake, raising=False)
    return fake


class TestPenyambunganKeDocType:
    """Fungsi murni yang benar tapi tak pernah DIPANGGIL = tetap kosong.

    Uji di atas menjaga isinya; kelas ini menjaga sambungannya —
    `_ringkas_dokumen("lpb", …)` benar-benar membaca koleksi `lpb`.
    """
    def test_doc_type_lpb_terbaca_dari_koleksi_lpb(self, dbx):
        _jalan(dbx.lpb.insert_one({"id": "lpb-1", **LPB_PERSEDIAAN}))
        r = _jalan(rt._ringkas_dokumen("lpb", "lpb-1"))
        assert r["nomor"] == "LPB-12/OIKN/2026"
        assert r["jumlah_barang"] == 7
        assert r["pihak"][0] == "PT Sumber Makmur (Penyedia)"

    def test_lpb_tak_ditemukan_kembali_kosong_bukan_meledak(self, dbx):
        assert _jalan(rt._ringkas_dokumen("lpb", "tidak-ada")) == {}

    def test_doc_ref_kosong_tak_menyentuh_basis_data(self, dbx):
        assert _jalan(rt._ringkas_dokumen("lpb", "  ")) == {}

    def test_doc_type_asing_tetap_kosong(self, dbx):
        _jalan(dbx.lpb.insert_one({"id": "x", **LPB_PERSEDIAAN}))
        assert _jalan(rt._ringkas_dokumen("dokumen_bebas", "x")) == {}

    def test_nup_lpb_aset_sampai_ke_ujung(self, dbx):
        """Perjalanan penuh: dokumen di basis data → ringkasan siap-pesan."""
        _jalan(dbx.lpb.insert_one({"id": "lpb-2", **LPB_ASET}))
        r = _jalan(rt._ringkas_dokumen("lpb", "lpb-2"))
        assert r["barang"][0]["nup"] == "12"
        assert "BMN" in r["perihal"]
