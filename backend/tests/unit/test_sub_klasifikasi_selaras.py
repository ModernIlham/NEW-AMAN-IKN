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


_FORM = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "frontend", "src", "components", "assets", "AssetForm.jsx")


def _sumber_form():
    with open(os.path.abspath(_FORM), encoding="utf-8") as f:
        return f.read()


class TestSalinanKetigaSudahHilang:
    """AssetForm.jsx dulu menulis ulang daftar yang sama sebagai <SelectItem>
    hardcoded — salinan KETIGA, di luar server dan InventoryFieldSheet. Ia bisa
    menua sendiri tanpa ada yang menagih, dan konvensi repo justru melarangnya
    ("ekspor konstanta opsi — jangan duplikasi daftar opsi di tempat lain")."""

    def test_form_memakai_konstanta_bersama(self):
        src = _sumber_form()
        assert "SUB_KLASIFIKASI_OPTIONS" in src, \
            "AssetForm harus memakai konstanta bersama, bukan daftar sendiri"

    def test_tak_ada_selectitem_sub_klasifikasi_hardcoded(self):
        """Penjaga sesungguhnya: nilai apa pun dari daftar tak boleh muncul
        lagi sebagai <SelectItem value="..."> yang ditulis tangan."""
        src = _sumber_form()
        hardcoded = [n for n in SUB_KLASIFIKASI_DITAWARKAN
                     if f'<SelectItem value="{n}"' in src]
        assert hardcoded == [], (
            "nilai sub-klasifikasi masih ditulis tangan di AssetForm.jsx "
            f"(salinan ketiga hidup lagi): {hardcoded}")


class TestPanduanOperatorLengkap:
    """Tiap pilihan punya kartu panduan (maksud/contoh/penanganan/alur) di
    `SUB_KLASIFIKASI_INFO`. Menambah pilihan tanpa panduannya membuat kartu itu
    kosong justru pada keadaan operator paling tertekan — kebakaran, bencana,
    pencurian."""

    def kunci_info(self):
        src = _sumber_form()
        blok = src.split("const SUB_KLASIFIKASI_INFO = {", 1)[1].split("\n};", 1)[0]
        return {m.group(1) for m in re.finditer(r'^\s{2}"([^"]+)":\s*\{', blok, re.M)}

    def test_pembacaan_tidak_hampa(self):
        assert len(self.kunci_info()) >= 10

    def test_setiap_pilihan_punya_panduan(self):
        tanpa = [n for n in SUB_KLASIFIKASI_DITAWARKAN if n not in self.kunci_info()]
        assert tanpa == [], f"pilihan tanpa kartu panduan: {tanpa}"

    def test_panduan_terisi_keempat_bagiannya(self):
        """Ada ≠ berguna. Entri yang hanya terisi separuh tetap lolos uji
        keberadaan tetapi menampilkan kartu setengah kosong — dan justru
        `alur` yang paling dicari orang saat kejadiannya sedang berlangsung."""
        src = _sumber_form()
        blok = src.split("const SUB_KLASIFIKASI_INFO = {", 1)[1].split("\n};", 1)[0]
        # Pecah per entri: dari satu kunci sampai kunci berikutnya.
        posisi = [(m.group(1), m.start())
                  for m in re.finditer(r'^\s{2}"([^"]+)":\s*\{', blok, re.M)]
        kurang = []
        for i, (nama, awal) in enumerate(posisi):
            akhir = posisi[i + 1][1] if i + 1 < len(posisi) else len(blok)
            isi = blok[awal:akhir]
            for bagian in ("maksud", "contoh", "penanganan", "alur"):
                m = re.search(rf'{bagian}:\s*"([^"]*)"', isi)
                if not m or len(m.group(1).strip()) < 30:
                    kurang.append(f"{nama}.{bagian}")
        assert kurang == [], f"bagian panduan kosong/terlalu pendek: {kurang}"

    def test_panduan_kedaruratan_tak_mengklaim_pasal(self):
        """Naskah panduan adalah kaidah internal satker. Nomor peraturan di
        sini akan lolos gerbang sitasi (berkas frontend tak dipindai) padahal
        tampil ke operator — jadi dijaga di sini."""
        import sitasi_regulasi as SR
        src = _sumber_form()
        blok = src.split("const SUB_KLASIFIKASI_INFO = {", 1)[1].split("\n};", 1)[0]
        assert SR.sitasi_dalam(blok) == set()


class TestSebabKedaruratanTersedia:
    def test_kejadian_tak_terduga_punya_kategorinya(self):
        """Permintaan pemilik: kejadian force majeure harus terakomodasi."""
        for sebab in ("Kebakaran", "Bencana Alam", "Hilang / Dicuri",
                      "Kerusuhan / Huru-hara"):
            assert sebab in VALID_SUB_KLASIFIKASI_LAINNYA

    def test_sebab_lain_bukan_pengganti_belum_diteliti(self):
        """"Sebab Lain" berarti SUDAH diteliti tetapi tak masuk kategori —
        berbeda dari sub-klasifikasi kosong yang berarti belum diteliti."""
        assert "Sebab Lain (Diuraikan)" in VALID_SUB_KLASIFIKASI_LAINNYA
        assert "" not in VALID_SUB_KLASIFIKASI_LAINNYA


class TestLandasanKlasifikasiDjkn:
    """Sembilan dari sebelas klasifikasi resmi DJKN untuk Barang Tidak
    Ditemukan (tindak lanjut revaluasi BMN 2017–2018) terpetakan ke daftar
    aplikasi ini — rinciannya di docs/SITASI-DOKUMEN-RESMI.md.

    Uji ini menjaga padanannya tetap ada. Menghapus salah satunya berarti
    memutus daftar aplikasi dari landasan resminya, dan itu tak boleh terjadi
    diam-diam hanya karena seseorang merapikan kata-katanya."""

    PADANAN_DJKN = [
        "Kesalahan Kodefikasi",                     # 1
        "BMN Tercatat di Satker Lain",              # 2
        "Kegiatan Perencanaan/Pengembangan Dicatat Sebagai BMN Tersendiri",  # 3
        "Pencatatan Ganda",                         # 5
        "BMN Objek Alih Status/Pemindahtanganan/Penghapusan",               # 6
        "Penggabungan BMN Satu Kesatuan Fungsi",    # 7
        "Kesalahan Pencatatan Pihak Ketiga",        # 9
        "Tidak Ditemukan Fisiknya",                 # 10
        "Tidak Dapat Ditelusuri",                   # 11
    ]

    def test_sembilan_padanan_djkn_masih_ditawarkan(self):
        hilang = [n for n in self.PADANAN_DJKN
                  if n not in SUB_KLASIFIKASI_DITAWARKAN]
        assert hilang == [], f"padanan klasifikasi resmi DJKN hilang: {hilang}"

    def test_sebab_kedaruratan_diakui_sebagai_perluasan(self):
        """Enam sebab kedaruratan BUKAN bagian 11 klasifikasi DJKN. Uji ini
        merekam fakta itu supaya tak pernah diklaim sebagai klasifikasi
        resmi di naskah mana pun."""
        perluasan = {"Kebakaran", "Bencana Alam", "Hilang / Dicuri",
                     "Kerusuhan / Huru-hara", "Rusak Total / Hancur",
                     "Sebab Lain (Diuraikan)"}
        assert perluasan.isdisjoint(self.PADANAN_DJKN)
        assert perluasan <= set(SUB_KLASIFIKASI_DITAWARKAN)


class TestTidakAdaNilaiKembar:
    def test_tanpa_duplikat(self):
        assert len(VALID_SUB_KLASIFIKASI_ALL) == len(set(VALID_SUB_KLASIFIKASI_ALL))

    def test_dua_klasifikasi_tak_berbagi_nilai(self):
        """Satu nilai di dua klasifikasi membuat pilihan operator ambigu."""
        assert set(VALID_SUB_KLASIFIKASI_PENCATATAN).isdisjoint(
            VALID_SUB_KLASIFIKASI_LAINNYA)
