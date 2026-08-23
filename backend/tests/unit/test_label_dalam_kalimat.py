"""Akronim tetap kapital saat label disisipkan ke tengah kalimat.

Laporan pemilik atas BAST PPK→KPB: *"ubah apbn menjadi kapital semua APBN."*

Kalimat Pasal-nya dulu memakai `str(label).lower()` pada label
`"Pembelian (APBN)"`, sehingga tercetak *"diperoleh melalui pembelian
(apbn)"* — akronim resmi berubah menjadi kata biasa pada dokumen yang
ditandatangani Kuasa Pengguna Barang.

Cacatnya sekelas dengan label identitas yang dipatok: tak ada galat, tak ada
uji yang jatuh, dan yang membacanya di kertas menganggap aplikasinya memang
menulis begitu.
"""
import ast
import pathlib

from pelaporan_utils import label_dalam_kalimat
from pengadaan_utils import JENIS_PEROLEHAN

AKAR = pathlib.Path(__file__).resolve().parents[2]


class TestLabelDalamKalimat:
    def test_akronim_dalam_kurung_tetap_kapital(self):
        assert label_dalam_kalimat("Pembelian (APBN)") == "pembelian (APBN)"

    def test_kata_biasa_dikecilkan(self):
        assert label_dalam_kalimat("Penyelesaian Pembangunan") == \
            "penyelesaian pembangunan"

    def test_campuran_kata_biasa_dan_akronim(self):
        assert label_dalam_kalimat("Transfer Masuk (antar entitas)") == \
            "transfer masuk (antar entitas)"

    def test_akronim_bertanda_hubung_dan_berangka_utuh(self):
        """`"MPHL-BJS".isupper()` dan `"SP2D".isupper()` sama-sama True —
        tanda baca & angka diabaikan penilaiannya."""
        assert label_dalam_kalimat("MPHL-BJS") == "MPHL-BJS"
        assert label_dalam_kalimat("SP2D") == "SP2D"

    def test_angka_romawi_tidak_ikut_dikecilkan(self):
        assert label_dalam_kalimat("Semester I 2026") == "semester I 2026"

    def test_kosong_aman(self):
        assert label_dalam_kalimat("") == "" and label_dalam_kalimat(None) == ""

    def test_spasi_beruntun_dirapikan_bukan_dipertahankan(self):
        assert label_dalam_kalimat("  Hibah   Masuk  ") == "hibah masuk"


class TestSeluruhLabelPerolehanSelamat:
    def test_akronim_pada_tiap_label_jenis_bertahan(self):
        """Yang dijaga bukan satu label, melainkan SELURUH daftar — jenis
        perolehan baru yang membawa akronim ikut terlindungi."""
        for kunci, (label, _kode) in JENIS_PEROLEHAN.items():
            hasil = label_dalam_kalimat(label)
            for kata in label.split():
                if kata.isupper():
                    assert kata in hasil, (kunci, kata, hasil)

    def test_hasilnya_memang_berhuruf_kecil_untuk_kata_biasa(self):
        """Penjaga bagi penjaganya: helper yang mengembalikan teks apa adanya
        akan meloloskan uji di atas tanpa mengerjakan apa pun."""
        assert label_dalam_kalimat("Pembelian (APBN)") != "Pembelian (APBN)"


class TestTakAdaLagiPelataanHurufKecilPadaLabel:
    """Pemindai: label jenis perolehan tak boleh diratakan `.lower()` lagi.

    Menyalin baris tetangganya adalah gerakan paling wajar saat menambah pasal
    baru — dan cacatnya kembali tanpa satu pun galat.
    """

    def _berkas(self):
        for f in sorted(AKAR.glob("**/*.py")):
            bagian = set(f.parts)
            if "tests" in bagian or "__pycache__" in bagian:
                continue
            yield f

    def test_pemindaiannya_menyapu_berkas_sungguhan(self):
        nama = {f.name for f in self._berkas()}
        assert {"pengadaan.py", "pelaporan_utils.py"} <= nama
        assert len(nama) >= 50

    def test_nol_lower_pada_label_jenis(self):
        pelanggar = []
        for f in self._berkas():
            try:
                pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(pohon):
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr == "lower"
                        and "label_jenis" in ast.dump(n.func.value)):
                    pelanggar.append(f"{f.name}:{n.lineno}")
        assert pelanggar == [], (
            "Pakai `label_dalam_kalimat`, bukan `.lower()`, agar akronim "
            "seperti APBN tak berubah jadi kata biasa: " + "; ".join(pelanggar))

    def test_polanya_benar_benar_menangkap(self):
        pohon = ast.parse("x = str(label_jenis).lower()")
        kena = [n for n in ast.walk(pohon)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "lower"
                and "label_jenis" in ast.dump(n.func.value)]
        assert len(kena) == 1
