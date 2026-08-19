"""Test logika murni persuratan (persuratan_utils.py) — tanpa Mongo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from persuratan_utils import (  # noqa: E402
    FORMAT_NOMOR_DEFAULT, bangun_nomor, baris_agenda_csv,
    placeholder_tak_dikenal, validate_surat_keluar, validate_surat_masuk,
    validate_transisi,
)


class TestBangunNomor:
    def test_format_default_lengkap(self):
        n = bangun_nomor(FORMAT_NOMOR_DEFAULT, 15, "2026-07-17",
                         kode_klasifikasi="PL.02", kode_unit="OIKN",
                         kode_keamanan="B")
        assert n == "B-015/PL.02/OIKN/VII/2026"

    def test_bagian_kosong_dirapikan(self):
        # Tanpa kode unit & klasifikasi → dobel '/' hilang, tepi bersih
        n = bangun_nomor(FORMAT_NOMOR_DEFAULT, 3, "2026-01-05")
        assert n == "B-003/I/2026"
        assert "//" not in n

    def test_template_kustom(self):
        n = bangun_nomor("{urut}/{kode_unit}/{bulan}/{tahun}", 7,
                         "2026-12-01", kode_unit="SET")
        assert n == "007/SET/12/2026"

    def test_tanggal_tak_valid_tetap_menghasilkan_nomor(self):
        n = bangun_nomor(FORMAT_NOMOR_DEFAULT, 1, "tanggal-rusak",
                         kode_klasifikasi="PL", kode_unit="X")
        assert "001" in n and "{" not in n

    def test_placeholder_tak_dikenal(self):
        assert placeholder_tak_dikenal("{urut}/{ngawur}/{tahun}") == ["ngawur"]
        assert placeholder_tak_dikenal(FORMAT_NOMOR_DEFAULT) == []


class TestValidasi:
    def test_surat_keluar_wajib_perihal(self):
        assert any("Perihal" in e for e in validate_surat_keluar({}))
        assert validate_surat_keluar({"perihal": "Laporan BMN",
                                      "kode_keamanan": "B"}) == []

    def test_surat_keluar_kode_keamanan(self):
        errs = validate_surat_keluar({"perihal": "x", "kode_keamanan": "Z"})
        assert any("keamanan" in e for e in errs)

    def test_surat_keluar_modul_dikenal(self):
        assert validate_surat_keluar({"perihal": "x", "modul": "pelaporan"}) == []
        assert any("Modul" in e for e in
                   validate_surat_keluar({"perihal": "x", "modul": "asing"}))

    def test_surat_masuk_field_wajib(self):
        errs = validate_surat_masuk({})
        assert len(errs) == 3
        assert validate_surat_masuk({"nomor_surat": "1", "pengirim": "KPKNL",
                                     "perihal": "Undangan"}) == []


class TestTransisi:
    def test_keluar_sah(self):
        assert validate_transisi("dibooking", "disahkan", "keluar") == ""
        assert validate_transisi("dibooking", "dibatalkan", "keluar") == ""

    def test_keluar_final_terkunci(self):
        assert validate_transisi("disahkan", "dibatalkan", "keluar") != ""
        assert validate_transisi("dibatalkan", "disahkan", "keluar") != ""

    def test_masuk_alur(self):
        assert validate_transisi("diterima", "diproses", "masuk") == ""
        assert validate_transisi("diproses", "selesai", "masuk") == ""
        assert validate_transisi("selesai", "diproses", "masuk") != ""


class TestAgendaCsv:
    def test_baris_keluar_dan_masuk(self):
        rows = baris_agenda_csv([
            {"jenis": "keluar", "no_agenda": 15, "status": "disahkan",
             "nomor": "B-015/PL/VII/2026", "tanggal_surat": "2026-07-17",
             "perihal": "LHI", "tujuan": "KPKNL", "jenis_naskah": "Laporan",
             "modul": "pelaporan", "sifat_urgensi": "segera",
             "disahkan_pada": "2026-07-18T01:00:00Z"},
            {"jenis": "masuk", "no_agenda": 4, "status": "diterima",
             "nomor": "S-9/KPKNL/2026", "tanggal_surat": "2026-07-10",
             "perihal": "Undangan rekon", "pengirim": "KPKNL",
             "jenis_naskah": "Surat Biasa", "modul": "pelaporan",
             "created_at": "2026-07-11T02:00:00Z"},
        ])
        # Kolom dicari lewat NAMANYA, bukan posisinya. Uji ini sudah pernah
        # pecah sekali saat kolom Keberlakuan menyisip (lihat komentar lama),
        # dan pecah lagi saat kolom Sifat Urgensi ditambahkan — padahal
        # keduanya penambahan yang benar. Yang layak dijaga adalah PEMETAAN
        # nilai ke kolomnya, bukan nomor urut kolom.
        kolom = {nama: i for i, nama in enumerate(rows[0])}
        for wajib in ("No Agenda", "Keberlakuan", "Nomor Eksternal",
                      "Jenis Naskah", "Sifat Urgensi"):
            assert wajib in kolom, f"kolom '{wajib}' hilang dari buku agenda"

        def sel(baris, nama):
            return rows[baris][kolom[nama]]

        assert sel(1, "Jenis") == "Keluar"
        assert sel(1, "Dari/Kepada") == "KPKNL"
        assert sel(1, "Disahkan/Diterima Pada") == "2026-07-18"
        assert sel(2, "Jenis") == "Masuk"
        assert sel(2, "Disahkan/Diterima Pada") == "2026-07-11"
        # Sifat urgensi tercetak sebagai LABEL manusia, bukan kunci mesinnya.
        assert sel(1, "Sifat Urgensi") == "Segera"
        # Baris tanpa sifat urgensi tampil kosong, bukan mengarang "Biasa" —
        # buku agenda tak boleh menyatakan sesuatu yang tak pernah dicatat.
        assert sel(2, "Sifat Urgensi") == ""


# ── Klasifikasi otomatis (persuratan smart) ──
from persuratan_utils import pilih_klasifikasi, validate_peta_klasifikasi

PETA = [
    {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "PL.02"},
    {"modul": "", "jenis_naskah": "Berita Acara", "kode": "HK.06"},
    {"modul": "inventarisasi", "jenis_naskah": "", "kode": "PL.01"},
]


class TestPilihKlasifikasi:
    def test_eksplisit_menang(self):
        assert pilih_klasifikasi(PETA, "pelaporan", "Laporan",
                                 eksplisit="XX.99") == "XX.99"

    def test_aturan_paling_spesifik_menang(self):
        # modul+jenis (skor 2) mengalahkan aturan jenis-saja (skor 1)
        peta = PETA + [{"modul": "", "jenis_naskah": "Laporan", "kode": "UM.01"}]
        assert pilih_klasifikasi(peta, "pelaporan", "Laporan") == "PL.02"

    def test_wildcard_jenis(self):
        assert pilih_klasifikasi(PETA, "inventarisasi", "Surat Tugas") == "PL.01"

    def test_wildcard_modul_dan_case_insensitive_jenis(self):
        assert pilih_klasifikasi(PETA, "wasdal", "berita acara") == "HK.06"

    def test_fallback_default(self):
        assert pilih_klasifikasi(PETA, "umum", "Nota Dinas", default="UM.00") == "UM.00"
        assert pilih_klasifikasi([], "umum", "Nota Dinas") == ""


class TestValidatePeta:
    def test_peta_sah(self):
        assert validate_peta_klasifikasi(PETA) == []

    def test_kode_wajib_dan_modul_dikenal(self):
        errs = validate_peta_klasifikasi([
            {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": ""},
            {"modul": "asing", "jenis_naskah": "", "kode": "A"},
        ])
        assert len(errs) == 2

    def test_aturan_semua_modul_semua_jenis_SAH(self):
        """RANTAI YANG DULU PUTUS. Layar pengaturan menambahkan baris baru
        dengan kedua filter kosong dan keterangannya sendiri berbunyi
        "kosong = berlaku untuk semua" — tapi validator menolaknya, jadi
        SELURUH simpanan gagal 400 dan Master Kode Klasifikasi Arsip tak
        pernah berpengaruh apa pun pada nomor surat.

        Mesin pemilihnya selalu mendukung: aturan tanpa filter berskor 0,
        menang hanya bila tak ada yang lebih spesifik."""
        peta = [{"modul": "", "jenis_naskah": "", "kode": "UM.01"}]
        assert validate_peta_klasifikasi(peta) == []
        assert pilih_klasifikasi(peta, "pelaporan", "Laporan") == "UM.01"

    def test_aturan_semua_kalah_dari_yang_spesifik(self):
        """Aturan 'semua' adalah JARING, bukan penimpa — kalau ia menang atas
        aturan spesifik, mengizinkannya justru merusak pemetaan yang sudah ada."""
        peta = [{"modul": "", "jenis_naskah": "", "kode": "UM.01"}] + PETA
        assert pilih_klasifikasi(peta, "pelaporan", "Laporan") == "PL.02"
        assert pilih_klasifikasi(peta, "penilaian", "Nota Dinas") == "UM.01"

    def test_aturan_kembar_ditolak_karena_baris_mati(self):
        """`pilih_klasifikasi` memakai `skor > skor_terbaik`, jadi di antara dua
        aturan bercakupan sama hanya yang PERTAMA yang pernah terpakai. Yang di
        bawah adalah baris mati yang menipu pembacanya."""
        errs = validate_peta_klasifikasi([
            {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "PL.02"},
            {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "XX.99"},
        ])
        assert len(errs) == 1 and "#1" in errs[0]
        # ...dan memang benar yang kedua tak pernah menang.
        assert pilih_klasifikasi([
            {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "PL.02"},
            {"modul": "pelaporan", "jenis_naskah": "Laporan", "kode": "XX.99"},
        ], "pelaporan", "Laporan") == "PL.02"

    def test_kembar_tak_peduli_besar_kecil_huruf_jenis(self):
        """`pilih_klasifikasi` mencocokkan jenis naskah case-insensitive —
        pemeriksaan kembarnya harus memakai ukuran yang sama, kalau tidak
        baris mati lolos hanya karena beda kapitalisasi."""
        errs = validate_peta_klasifikasi([
            {"modul": "", "jenis_naskah": "Berita Acara", "kode": "HK.06"},
            {"modul": "", "jenis_naskah": "berita acara", "kode": "XX.99"},
        ])
        assert len(errs) == 1

    def test_dua_aturan_semua_juga_kembar(self):
        errs = validate_peta_klasifikasi([
            {"modul": "", "jenis_naskah": "", "kode": "UM.01"},
            {"modul": "", "jenis_naskah": "", "kode": "UM.02"},
        ])
        assert len(errs) == 1
        assert "semua modul & semua jenis naskah" in errs[0]


# ── Periode deret nomor + nomor sisipan (reset bulanan & backdate .01) ───────
from persuratan_utils import (  # noqa: E402
    RESET_URUT_DEFAULT, periode_urut, urut_tampil, validate_format_reset,
)


class TestPeriodeUrut:
    def test_bulanan_per_bulan(self):
        assert periode_urut("bulanan", "2026-08-04") == "2026-08"
        assert periode_urut("bulanan", "2026-09-01") == "2026-09"

    def test_tahunan_per_tahun(self):
        assert periode_urut("tahunan", "2026-08-04") == "2026"

    def test_bawaan_dan_nilai_asing_jatuh_ke_bulanan(self):
        assert RESET_URUT_DEFAULT == "bulanan"
        assert periode_urut("", "2026-08-04") == "2026-08"
        assert periode_urut(None, "2026-08-04") == "2026-08"
        assert periode_urut("mingguan", "2026-08-04") == "2026-08"

    def test_tanggal_rusak_terlihat_bukan_diam(self):
        assert periode_urut("bulanan", "tanggal-rusak") == ""
        assert periode_urut("tahunan", "") == ""


class TestUrutTampil:
    def test_tanpa_sisipan_tiga_digit(self):
        assert urut_tampil(5) == "005"
        assert urut_tampil(150) == "150"

    def test_dengan_sisipan(self):
        assert urut_tampil(5, 1) == "005.01"
        assert urut_tampil(5, 12) == "005.12"

    def test_nilai_kosong_aman(self):
        assert urut_tampil(None) == "000"
        assert urut_tampil(7, None) == "007"
        assert urut_tampil(7, "aneh") == "007"


class TestBangunNomorSisipan:
    def test_urut_string_dipakai_apa_adanya(self):
        n = bangun_nomor(FORMAT_NOMOR_DEFAULT, "005.01", "2026-08-01",
                         kode_klasifikasi="PL.02", kode_unit="OIKN")
        assert n == "B-005.01/PL.02/OIKN/VIII/2026"

    def test_urut_int_tetap_tiga_digit(self):
        assert "015" in bangun_nomor(FORMAT_NOMOR_DEFAULT, 15, "2026-08-01")


class TestValidasiSisipan:
    def test_sisipan_wajib_tanggal(self):
        errs = validate_surat_keluar(
            {"perihal": "x", "sisipan": True}, today_iso="2026-08-04")
        assert any("Tanggal" in e for e in errs)

    def test_sisipan_tak_boleh_masa_depan(self):
        errs = validate_surat_keluar(
            {"perihal": "x", "sisipan": True, "tanggal_surat": "2026-08-05"},
            today_iso="2026-08-04")
        assert any("masa depan" in e for e in errs)

    def test_sisipan_backdate_dan_hari_ini_sah(self):
        for tgl in ("2026-08-01", "2026-08-04"):
            assert validate_surat_keluar(
                {"perihal": "x", "sisipan": True, "tanggal_surat": tgl},
                today_iso="2026-08-04") == []

    def test_tanpa_sisipan_perilaku_lama_utuh(self):
        assert validate_surat_keluar({"perihal": "x"},
                                     today_iso="2026-08-04") == []


class TestValidateFormatReset:
    def test_bulanan_wajib_unsur_bulan(self):
        assert validate_format_reset("bulanan", "{urut}/{tahun}") != ""
        assert validate_format_reset("bulanan", FORMAT_NOMOR_DEFAULT) == ""
        assert validate_format_reset("bulanan", "{urut}/{bulan}/{tahun}") == ""

    def test_tahunan_bebas(self):
        assert validate_format_reset("tahunan", "{urut}/{tahun}") == ""


class TestAgendaCsvSisipan:
    def test_no_agenda_sisipan_tampil_bertitik(self):
        rows = baris_agenda_csv([
            {"jenis": "keluar", "no_agenda": 5, "sisipan": 1,
             "status": "dibooking", "nomor": "B-005.01/VIII/2026",
             "tanggal_surat": "2026-08-01", "perihal": "x"},
            {"jenis": "keluar", "no_agenda": 6,
             "status": "dibooking", "nomor": "B-006/VIII/2026",
             "tanggal_surat": "2026-08-02", "perihal": "y"},
        ])
        assert rows[1][0] == "005.01"
        assert rows[2][0] == 6  # baris biasa: nilai mentah tak berubah
