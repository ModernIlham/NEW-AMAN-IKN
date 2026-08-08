"""Kolom SIMAN yang berganti nama TIDAK BOLEH jadi "SIMAN bilang 0" — C9.

Skenarionya bukan hipotesis. Peta kolom repo ini sudah memuat DUA ejaan untuk
hal yang sama — `"tanggal pengapusan"` dan `"tanggal penghapusan"` — bukti
bahwa header ekspor SIMAN memang pernah bergeser dan akan bergeser lagi.

Yang terjadi bila "Nilai Perolehan" berganti judul, sebelum perbaikan:

  1. `petakan_header` diam saja — hanya kode barang + NUP yang berstatus wajib;
  2. `parse_baris` tetap mengisi kuncinya lewat `parse_harga(None)` → **0.0**;
  3. cabang "angka" di `banding_aset` hanya menyaring `(None, "")`, jadi 0.0
     lolos sebagai angka sah → SELURUH aset dilaporkan berselisih;
  4. operator menuruti panduan aplikasi dan menekan "terapkan nilai SIMAN" →
     `nilai_terapkan` mengembalikan `"0"` → nilai perolehan **nol** ditulis
     massal ke master aset.

Setelahnya DBKP, LBKP, penyusutan, dan klasifikasi intra/ekstra semuanya nol —
dari satu perubahan judul kolom di file yang dikirim SIMAN.

Perbaikannya dua lapis: angka yang tak disebut SIMAN jadi `None` (bukan 0.0),
dan kolom perbandingan yang hilang dilaporkan supaya penyebabnya terlihat.
"""
import pytest

from siman_utils import (
    PERBANDINGAN, banding_aset, harga_atau_none, kolom_banding_hilang,
    nilai_terapkan, parse_baris, petakan_header,
)

HEADER_LENGKAP = ["Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan",
                  "Merk", "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
                  "Kode Register"]
# Persis file yang sama, HANYA judul kolom nilainya bergeser.
HEADER_BERGESER = ["Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan (Rp)",
                   "Merk", "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
                   "Kode Register"]

BARIS = ["3100102001", "1", "Laptop", "15000000",
         "Lenovo", "T14", "Baik", "2024-03-01", "Budi", "REG-1"]

ASET = {
    "asset_code": "3100102001", "NUP": "1", "category": "Laptop",
    "purchase_price": "15000000", "brand": "Lenovo", "model": "T14",
    "condition": "Baik", "purchase_date": "2024-03-01", "user": "Budi",
    "kode_register": "REG-1",
}


def _parse(header, baris=BARIS):
    peta, hilang = petakan_header(header)
    assert hilang == []          # kode barang + NUP tetap ada
    return peta, parse_baris(baris, peta)


class TestHargaAtauNone:
    def test_angka_sungguhan_tetap_angka(self):
        assert harga_atau_none("15000000") == 15_000_000.0
        assert harga_atau_none("Rp1.234.567,89") == pytest.approx(1_234_567.89)
        assert harga_atau_none(0) == 0.0        # nol EKSPLISIT tetap nol

    def test_tak_disebut_jadi_None_bukan_nol(self):
        # Inilah pembedanya: "tidak tahu" ≠ "nol".
        assert harga_atau_none(None) is None
        assert harga_atau_none("") is None
        assert harga_atau_none("   ") is None


class TestKolomBergeser:
    def test_kolom_nilai_hilang_TIDAK_menghasilkan_nol(self):
        _peta, b = _parse(HEADER_BERGESER)
        assert b["nilai_perolehan"] is None, (
            "0.0 di sini adalah akar C9 — ia lolos sebagai angka sah")

    def test_kolom_nilai_ada_tetap_terbaca(self):
        _peta, b = _parse(HEADER_LENGKAP)
        assert b["nilai_perolehan"] == 15_000_000.0

    def test_kolom_hilang_TIDAK_dilaporkan_sebagai_selisih(self):
        _peta, b = _parse(HEADER_BERGESER)
        selisih = banding_aset(ASET, b)
        field_selisih = {s["field"] for s in selisih}
        assert "purchase_price" not in field_selisih, selisih

    def test_selisih_nilai_ASLI_tetap_tertangkap(self):
        # Perbaikannya tidak boleh membutakan pembanding untuk kasus nyata.
        _peta, b = _parse(HEADER_LENGKAP, BARIS[:3] + ["20000000"] + BARIS[4:])
        selisih = banding_aset(ASET, b)
        assert any(s["field"] == "purchase_price" for s in selisih), selisih

    def test_SIMAN_bilang_nol_sungguhan_tetap_selisih(self):
        # Nol yang memang ditulis SIMAN berbeda dari nol hasil kolom hilang —
        # yang ini WAJIB tetap muncul, kalau tidak perbaikannya kebablasan.
        _peta, b = _parse(HEADER_LENGKAP, BARIS[:3] + ["0"] + BARIS[4:])
        assert b["nilai_perolehan"] == 0.0
        selisih = banding_aset(ASET, b)
        assert any(s["field"] == "purchase_price" for s in selisih), selisih

    def test_terapkan_tidak_pernah_menulis_nol_dari_kolom_hilang(self):
        """Rantai penuh sampai nilai yang BENAR-BENAR ditulis ke master aset."""
        _peta, b = _parse(HEADER_BERGESER)
        for s in banding_aset(ASET, b):
            if s["field"] == "purchase_price":
                pytest.fail(f"selisih palsu → nilai_terapkan = {nilai_terapkan(s)!r}")


class TestKolomHilangDilaporkan:
    def test_header_lengkap_tak_melaporkan_apa_pun(self):
        peta, _b = _parse(HEADER_LENGKAP)
        assert kolom_banding_hilang(peta) == []

    def test_header_bergeser_menyebut_kolomnya(self):
        peta, _b = _parse(HEADER_BERGESER)
        assert kolom_banding_hilang(peta) == ["Nilai Perolehan"]

    def test_menyebut_LABEL_yang_dikenali_operator(self):
        # Label, bukan kunci internal — pesannya dibaca petugas satker, bukan
        # pengembang. Semua label berasal dari satu sumber: PERBANDINGAN.
        label_sah = {label for _f, _k, label, _j in PERBANDINGAN}
        assert set(kolom_banding_hilang({})) <= label_sah
        assert len(kolom_banding_hilang({})) == len(PERBANDINGAN)


def test_peringatan_impor_benar_benar_menampilkannya():
    """Penjaga sambungan — helper murni tak berguna bila tak dipanggil."""
    import inspect
    import routes.siman as rs
    src = inspect.getsource(rs.import_siman)
    assert "kolom_banding_hilang(peta_header)" in src
    assert "peringatan.append" in src
    i = src.index("kolom_banding_hilang(peta_header)")
    assert "TIDAK dibandingkan" in src[i:i + 600]
