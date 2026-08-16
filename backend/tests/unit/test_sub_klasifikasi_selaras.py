"""Daftar sub-klasifikasi di UI dan di server tidak boleh berjalan sendiri-sendiri.

Yang ditemukan sebelum berkas ini ada: kedua sisi punya daftarnya masing-masing
dan **irisannya NOL**. Konsekuensinya nyata, bukan teoretis:

  * SELURUH 10 nilai yang bisa dihasilkan UI aplikasi DITOLAK ketika berkasnya
    diimpor ulang lewat Excel — operator mengekspor datanya sendiri lalu tidak
    bisa memasukkannya kembali;
  * template Excel menyodorkan nilai ("Bencana Alam", "Hilang / Dicuri") yang
    UI-nya tak pernah bisa hasilkan;
  * bahkan baris CONTOH di template itu ("Pencatatan Ganda") ditolak oleh
    validator impor milik template itu sendiri.

Tak satu pun uji menangkapnya, karena masing-masing sisi konsisten dengan
dirinya sendiri. Yang hilang adalah uji yang membandingkan KEDUANYA — dan
itulah berkas ini.

Kaidah yang ditegakkan: **longgar saat menerima, ketat saat menawarkan.** Nilai
lawas tetap diterima impor supaya berkas & data lama tak mendadak ditolak,
tetapi tidak lagi disodorkan kepada operator.
"""
import os
import re

import pytest

from shared_utils import (
    SUB_KLASIFIKASI_DITAWARKAN, SUB_KLASIFIKASI_LAWAS,
    VALID_KLASIFIKASI, VALID_SUB_KLASIFIKASI_ALL,
    VALID_SUB_KLASIFIKASI_LAINNYA, VALID_SUB_KLASIFIKASI_PENCATATAN,
)

_SHEET = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "frontend", "src", "components", "assets", "InventoryFieldSheet.jsx")


def opsi_frontend():
    """{klasifikasi: [nilai]} dibaca dari SUB_KLASIFIKASI_OPTIONS di JSX.

    Sengaja membaca berkas frontend apa adanya, bukan menyalin daftarnya ke
    sini — salinan akan menua diam-diam dan mengulang persis cacat yang
    hendak dicegah.
    """
    with open(os.path.abspath(_SHEET), encoding="utf-8") as f:
        src = f.read()
    blok = src.split("export const SUB_KLASIFIKASI_OPTIONS = {", 1)[1] \
              .split("\n};", 1)[0]
    keluar, kini = {}, None
    for baris in blok.splitlines():
        judul = re.match(r'\s*"([^"]+)":\s*\[', baris)
        if judul:
            kini = judul.group(1)
            keluar[kini] = []
            continue
        nilai = re.search(r'value:\s*"([^"]+)"', baris)
        if nilai and kini:
            keluar[kini].append(nilai.group(1))
    return keluar


@pytest.fixture(scope="module")
def fe():
    return opsi_frontend()


class TestPembacaanBenar:
    """Penjaga anti-hampa. Bila pembacaan JSX gagal, daftarnya jadi kosong dan
    SELURUH uji kesamaan di bawah lolos tanpa memeriksa apa pun."""

    def test_kedua_klasifikasi_terbaca(self, fe):
        assert set(fe) == set(VALID_KLASIFIKASI)

    def test_isinya_tidak_kosong(self, fe):
        for klas, nilai in fe.items():
            assert len(nilai) >= 3, f"{klas} hanya terbaca {len(nilai)} nilai"

    def test_nilai_contoh_benar_terbaca(self, fe):
        assert "Kesalahan Kodefikasi" in fe["Kesalahan Pencatatan"]
        assert "Tidak Ditemukan Fisiknya" in fe["Tidak Ditemukan Lainnya"]


class TestSelarasDenganServer:
    def test_kesalahan_pencatatan_sama_persis(self, fe):
        assert fe["Kesalahan Pencatatan"] == VALID_SUB_KLASIFIKASI_PENCATATAN

    def test_tidak_ditemukan_lainnya_sama_persis(self, fe):
        assert fe["Tidak Ditemukan Lainnya"] == VALID_SUB_KLASIFIKASI_LAINNYA

    def test_urutannya_ikut_dijaga(self, fe):
        """Bukan sekadar himpunan: urutan menentukan susunan pilihan di layar
        dan di dropdown template, dan operator menghafal posisinya."""
        gabung = fe["Kesalahan Pencatatan"] + fe["Tidak Ditemukan Lainnya"]
        assert gabung == SUB_KLASIFIKASI_DITAWARKAN


class TestPulangPergiEksporImpor:
    def test_semua_nilai_ui_lolos_validasi_impor(self, fe):
        """Inti cacatnya: sebelum perbaikan, 10 dari 10 nilai ini ditolak."""
        ditolak = [n for nilai in fe.values() for n in nilai
                   if n not in VALID_SUB_KLASIFIKASI_ALL]
        assert ditolak == [], (
            "Nilai berikut bisa dihasilkan UI tetapi DITOLAK saat diimpor "
            f"ulang — operator kehilangan datanya sendiri: {ditolak}")

    def test_dropdown_template_hanya_yang_ditawarkan(self):
        """Template tidak boleh lagi menyodorkan kosakata usang."""
        assert set(SUB_KLASIFIKASI_DITAWARKAN).isdisjoint(SUB_KLASIFIKASI_LAWAS)

    def test_nilai_lawas_tetap_diterima(self):
        """Merapikan daftar tak boleh membuat berkas & data lama ditolak."""
        for lawas in ("Bencana Alam", "Hilang / Dicuri",
                      "Pencatatan Ganda (Double Counting)"):
            assert lawas in VALID_SUB_KLASIFIKASI_ALL

    def test_contoh_di_template_valid(self):
        """Baris contoh template dulu memakai nilai yang ditolak validator
        template itu sendiri."""
        from routes.templates import ASSET_TEMPLATE_SCHEMA
        for f in ASSET_TEMPLATE_SCHEMA:
            if f["field"] == "sub_klasifikasi":
                assert f["sample2"] in VALID_SUB_KLASIFIKASI_ALL
                assert f["dropdown"] == SUB_KLASIFIKASI_DITAWARKAN
                return
        pytest.fail("field sub_klasifikasi tak ada di template")


class TestTidakAdaNilaiKembar:
    def test_tanpa_duplikat(self):
        assert len(VALID_SUB_KLASIFIKASI_ALL) == len(set(VALID_SUB_KLASIFIKASI_ALL))

    def test_dua_klasifikasi_tak_berbagi_nilai(self):
        """Satu nilai di dua klasifikasi membuat pilihan operator ambigu."""
        assert set(VALID_SUB_KLASIFIKASI_PENCATATAN).isdisjoint(
            VALID_SUB_KLASIFIKASI_LAINNYA)
