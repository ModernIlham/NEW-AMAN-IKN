"""Ekspor/template/impor Master Pegawai HARUS mencakup seluruh isian form.

Keluhan pemilik: "hasil eksportnya belum menggambarkan hasil keseluruhan
inputan saat ini". Terukur: 19 dari 56 field yang dapat diisi lewat form sama
sekali tak punya kolom — sepertiga isian operator lenyap begitu diekspor, dan
tak ada apa pun yang menandainya.

Berkas ini menjaga dua hal sekaligus:

  1. CAKUPAN — dibaca dari `EMPTY` di PegawaiPage.jsx, sumber kebenaran field
     form. Menambah isian form tanpa kolomnya akan MEMBUAT UJI INI GAGAL,
     bukan diam-diam hilang lagi seperti sebelumnya.
  2. PULANG-PERGI — ekspor → impor mengembalikan nilai yang sama. Kolom yang
     ada tapi nilainya berubah/kosong saat diimpor ulang sama merusaknya
     dengan kolom yang tak ada.
"""
import os
import re

from pegawai_utils import (
    HEADER_IMPOR, KOLOM_IMPOR, KOLOM_TEKS_EKSPOR, OPSI_DROPDOWN_EKSPOR,
    baris_ekspor_pegawai, baris_impor_ke_pegawai, normalisasi_kode_referensi,
    validate_pegawai,
)

_PAGE = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "frontend", "src", "pages", "PegawaiPage.jsx")

# Field yang SENGAJA tak berkolom — alasannya di docstring HEADER_IMPOR.
TANPA_KOLOM = {
    "sub_kategori_non_asn",   # pulang-pergi lewat kolom "Status Kepegawaian"
    "kode_satker",            # dicap server dari satker pengimpor (isolasi)
}


def field_form():
    """Field yang dapat diisi form, dibaca dari `EMPTY` di PegawaiPage.jsx."""
    with open(os.path.abspath(_PAGE), encoding="utf-8") as f:
        src = f.read()
    blok = src.split("const EMPTY = {", 1)[1].split("\n};", 1)[0]
    return [m.group(1) for m in re.finditer(r'(\w+):\s*"', blok)
            if m.group(1) != "mode"]


class TestCakupanKolom:
    def test_setiap_isian_form_punya_kolomnya(self):
        tercakup = set(KOLOM_IMPOR.values()) | TANPA_KOLOM
        hilang = [f for f in field_form() if f not in tercakup]
        assert hilang == [], (
            "Isian form tanpa kolom ekspor/template/impor — data operator "
            f"akan hilang saat diekspor: {hilang}")

    def test_form_benar_benar_terbaca(self):
        """Penjaga anti-hampa: bila pembacaan `EMPTY` gagal, daftar field jadi
        kosong dan uji cakupan lolos tanpa memeriksa apa pun."""
        f = field_form()
        assert len(f) > 40
        assert "nama" in f and "tanggal_meninggal" in f

    def test_tak_ada_kolom_yatim(self):
        """Tiap header punya pemetaan field — header tanpa pemetaan diabaikan
        diam-diam saat impor, jadi kolomnya cuma hiasan."""
        yatim = [h for h in HEADER_IMPOR
                 if h.strip().lower() not in KOLOM_IMPOR]
        assert yatim == []

    def test_header_tak_kembar(self):
        assert len(HEADER_IMPOR) == len(set(HEADER_IMPOR))

    def test_lebar_baris_ekspor_sama_dengan_header(self):
        """Baris ekspor yang kurang/lebih satu sel menggeser SELURUH kolom
        sesudahnya — nilai mendarat di kolom yang salah tanpa galat."""
        assert len(baris_ekspor_pegawai({})) == len(HEADER_IMPOR)

    def test_dropdown_menunjuk_kolom_yang_ada(self):
        asing = [j for j in OPSI_DROPDOWN_EKSPOR if j not in HEADER_IMPOR]
        assert asing == []

    def test_kolom_teks_menunjuk_kolom_yang_ada(self):
        assert set(KOLOM_TEKS_EKSPOR) <= set(HEADER_IMPOR)


LENGKAP = {
    "nip": "198501012010011001", "nama": "Budi Santoso",
    "gelar_depan": "Dr.", "gelar_belakang": "S.E., M.M.",
    "jenis_kelamin": "L", "tempat_lahir": "Jakarta",
    "tanggal_lahir": "1985-01-01",
    "agama": "islam", "status_perkawinan": "kawin",
    "kewarganegaraan": "wna", "jenis_identitas_wna": "kitas",
    "nomor_identitas_wna": "0012345678",
    "status_kepegawaian": "pns", "pangkat_golongan": "Penata (III/c)",
    "jabatan": "Analis BMN", "jenis_jabatan": "fungsional",
    "jenis_pelaksana": "plt", "jabatan_pelaksana": "Kepala Bagian",
    "kategori_pegawai": "pelaksana",
    "tmt_jabatan": "2022-01-01", "tanggal_akhir_jabatan": "2027-01-01",
    "eselon1": "Sekretariat", "eselon2": "Bagian Umum", "eselon3": "Subbag",
    "eselon4": "Seksi", "eselon5": "Subseksi", "eselon": "IV.a",
    "unit_kerja": "Subseksi", "unit_organisasi": "Sekretariat Jenderal",
    "no_hp": "081200000000", "email": "budi@instansi.go.id",
    "npwp": "091234567890000", "pendidikan_terakhir": "S1",
    "alamat": "Jl. Merdeka 1", "nama_bank": "BRI",
    "no_rekening": "123456789012345",
    "nomor_kontrak": "SPK-1/2026", "tgl_mulai_kontrak": "2026-01-01",
    "tgl_selesai_kontrak": "2026-12-31",
    "jenis_kontrak_non_asn": "outsourcing",
    "perusahaan_penyedia": "PT Sejahtera",
    "kode_satker_lengkap": "123456789012",
    "status_pegawai_satker": "diperbantukan_pada",
    "status_pegawai_instansi": "Kementerian Keuangan",
    "status": "meninggal",
    "tanggal_meninggal": "2026-06-01",
    "nomor_akta_kematian": "AK-77/2026",
    "penyebab_meninggal": "Sakit",
    "ahli_waris_nama": "Siti Aminah", "ahli_waris_hubungan": "Istri",
    "ahli_waris_kontak": "081300000000",
    "pemberitahuan_ahli_waris_tanggal": "2026-06-10",
    "pemberitahuan_ahli_waris_nomor": "B-9/PL/2026",
    "keterangan": "Catatan bebas",
}


def _pulang_pergi(doc):
    baris = baris_ekspor_pegawai(doc)
    hasil, _ = baris_impor_ke_pegawai(dict(zip(HEADER_IMPOR, baris)))
    return hasil


class TestPulangPergi:
    def test_seluruh_field_pulih_utuh(self):
        hasil = _pulang_pergi(LENGKAP)
        beda = {k: (v, hasil.get(k)) for k, v in LENGKAP.items()
                if k not in TANPA_KOLOM and hasil.get(k) != v}
        assert beda == {}, f"Nilai berubah saat pulang-pergi: {beda}"

    def test_pegawai_meninggal_TIDAK_LAGI_hilang_saat_impor_ulang(self):
        """Cacat lama yang ikut tertutup.

        `validate_pegawai` mewajibkan tanggal meninggal bila status
        "Meninggal Dunia", sedangkan kolomnya belum ada — sehingga baris
        almarhum SELALU gagal validasi dan dibuang senyap oleh impor
        (terhitung "dilewati"). Ekspor lalu impor ulang menghapus mereka dari
        master.
        """
        hasil = _pulang_pergi(LENGKAP)
        assert hasil["status"] == "meninggal"
        assert hasil["tanggal_meninggal"] == "2026-06-01"
        assert validate_pegawai(hasil) == []

    def test_dokumen_kosong_tak_meledak(self):
        hasil = _pulang_pergi({})
        assert hasil["nama"] == ""
        assert hasil["agama"] == ""

    def test_sub_kategori_non_asn_pulih_lewat_status_kepegawaian(self):
        """Tanpa kolom sendiri, tapi tetap utuh — itulah alasan ia dikecualikan."""
        hasil = _pulang_pergi({"nama": "Ani", "status_kepegawaian": "non_asn",
                               "sub_kategori_non_asn": "satpam"})
        assert hasil["status_kepegawaian"] == "non_asn"
        assert hasil["sub_kategori_non_asn"] == "satpam"

    def test_enum_kosong_tak_jadi_uraian_pertama(self):
        """Sel kosong harus tetap kosong. Bila `.get(kode, daftar[0])` dipakai,
        setiap pegawai tanpa agama akan diekspor sebagai 'Islam' — data yang
        tak pernah diinput siapa pun."""
        baris = dict(zip(HEADER_IMPOR, baris_ekspor_pegawai({"nama": "Ani"})))
        assert baris["Agama"] == ""
        assert baris["Kewarganegaraan"] == ""
        assert baris["Jenis Jabatan"] == ""


class TestNormalisasiEnumBaru:
    def test_menerima_uraian_maupun_kode(self):
        from pegawai_utils import AGAMA
        assert normalisasi_kode_referensi("Katolik", AGAMA) == "katolik"
        assert normalisasi_kode_referensi("katolik", AGAMA) == "katolik"
        assert normalisasi_kode_referensi("  KATOLIK  ", AGAMA) == "katolik"

    def test_nilai_asing_dikosongkan_bukan_disimpan(self):
        """Kode di luar daftar ditolak `validate_pegawai`, dan penolakan itu
        membuang SELURUH baris pegawai saat impor massal."""
        from pegawai_utils import AGAMA
        assert normalisasi_kode_referensi("Zoroaster", AGAMA) == ""
        assert normalisasi_kode_referensi(None, AGAMA) == ""

    def test_impor_baris_asing_tak_menggugurkan_pegawai(self):
        hasil, _ = baris_impor_ke_pegawai(
            {"Nama Lengkap": "Ani", "Agama": "Zoroaster"})
        assert hasil["nama"] == "Ani"
        assert hasil["agama"] == ""
        assert validate_pegawai(hasil) == []

    def test_tanggal_kelengkapan_wafat_dinormalkan(self):
        hasil, _ = baris_impor_ke_pegawai({
            "Nama Lengkap": "Ani", "Status": "Meninggal Dunia",
            "Tgl Meninggal": "01/06/2026",
            "Tgl Pemberitahuan Ahli Waris": "10-06-2026"})
        assert hasil["tanggal_meninggal"] == "2026-06-01"
        assert hasil["pemberitahuan_ahli_waris_tanggal"] == "2026-06-10"

    def test_header_alias_umum_dikenali(self):
        hasil, _ = baris_impor_ke_pegawai({
            "Nama Lengkap": "Ani", "Tanggal Meninggal": "2026-06-01",
            "Ahli Waris Nama": "Budi", "Unit Organisasi / Satker": "Setjen",
            "Instansi Terkait": "Kemenkeu"})
        assert hasil["tanggal_meninggal"] == "2026-06-01"
        assert hasil["ahli_waris_nama"] == "Budi"
        assert hasil["unit_organisasi"] == "Setjen"
        assert hasil["status_pegawai_instansi"] == "Kemenkeu"
