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
             "modul": "pelaporan", "disahkan_pada": "2026-07-18T01:00:00Z"},
            {"jenis": "masuk", "no_agenda": 4, "status": "diterima",
             "nomor": "S-9/KPKNL/2026", "tanggal_surat": "2026-07-10",
             "perihal": "Undangan rekon", "pengirim": "KPKNL",
             "jenis_naskah": "Surat Biasa", "modul": "pelaporan",
             "created_at": "2026-07-11T02:00:00Z"},
        ])
        assert rows[0][0] == "No Agenda"
        assert rows[1][1] == "Keluar" and rows[1][6] == "KPKNL"
        assert rows[1][11] == "2026-07-18"
        assert rows[2][1] == "Masuk" and rows[2][11] == "2026-07-11"
