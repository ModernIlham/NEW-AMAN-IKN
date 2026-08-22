"""Label NIP/NIK/NRP pada SEMUA keluaran PDF/DOCX terdeteksi, tak ditebak.

Permintaan pemilik: *"pastikan di semua generate PDF bagian NIP/NIK/NRP dapat
otomatis terdeteksi."*

Untuk nomor yang ADA, deteksinya memang sudah berjalan: `label_nomor_identitas`
memilih NIP / NI PPPK / NRP dari bentuk nomornya, dan menahan NIK demi privasi.
Yang belum tertangani adalah **garis tanda tangan yang masih kosong** — yang
diisi tangan setelah dokumen dicetak. Di situ tak ada nomor untuk dideteksi,
dan 30 tempat di seluruh backend memakai label `"NIP. ...................."`
yang dipatok.

Akibatnya bukan soal kerapian: penanda tangan Non-ASN diminta menuliskan NIK-nya
di bawah label "NIP.", dan anggota TNI/POLRI menuliskan NRP-nya di sana. Dokumen
resmi jadi menamai nomor orang dengan nama yang bukan namanya.

Jalan keluarnya bukan menebak lebih pintar, melainkan **tidak menebak**: satu
label netral yang benar untuk ketiganya.
"""
import ast
import pathlib

import pytest

from pegawai_utils import (
    PLACEHOLDER_IDENTITAS, baris_identitas_laporan, baris_identitas_ttd,
    label_nomor_identitas,
)

AKAR = pathlib.Path(__file__).resolve().parents[2]
# Satu-satunya berkas yang BOLEH merakit "NIP. <nomor>" — di sinilah labelnya
# ditentukan dari hasil deteksi.
BERKAS_PERAKIT = "pegawai_utils.py"

NIP = "197001011990031001"
NIK = "3506042503900001"
NRP = "80123456"


class TestLabelNetral:
    def test_menyebut_ketiganya(self):
        for bagian in ("NIP", "NIK", "NRP"):
            assert bagian in PLACEHOLDER_IDENTITAS

    def test_masih_berupa_garis_titik_untuk_ditulis_tangan(self):
        assert "." * 8 in PLACEHOLDER_IDENTITAS

    def test_dipakai_saat_nomornya_memang_kosong(self):
        assert baris_identitas_ttd("", PLACEHOLDER_IDENTITAS) == [PLACEHOLDER_IDENTITAS]
        assert baris_identitas_ttd("-", PLACEHOLDER_IDENTITAS) == [PLACEHOLDER_IDENTITAS]

    def test_TIDAK_dipakai_saat_nomornya_ada(self):
        """Nomor yang ada tetap dideteksi — label netral hanya untuk yang
        kosong. Memakainya di mana-mana justru membuang deteksi yang sudah
        bekerja."""
        assert baris_identitas_ttd(NIP, PLACEHOLDER_IDENTITAS) == [f"NIP. {NIP}"]


class TestDeteksiJenisNomorTetapBekerja:
    def test_nip_pns(self):
        assert label_nomor_identitas(NIP) == "NIP"

    def test_nrp_dikenali_sebagai_NRP_bukan_NIP(self):
        assert label_nomor_identitas(NRP) == "NRP"
        assert baris_identitas_laporan(NRP) == f"NRP. {NRP}"

    def test_nik_ditahan_demi_privasi(self):
        assert label_nomor_identitas(NIK) == ""
        assert baris_identitas_ttd(NIK) == []

    def test_non_asn_ditahan_apa_pun_nomornya(self):
        assert baris_identitas_ttd(NIP, status_kepegawaian="non_asn") == []


class TestPemindaiLabelDipatok:
    """Pemindai: tak ada lagi label `"NIP. …"` yang dipatok di kode keluaran.

    Kelas cacatnya mudah kembali — menambah satu blok tanda tangan baru dan
    menyalin baris `'after': ['NIP. ....................']` dari tetangganya
    adalah gerakan paling wajar di dunia. Pemindaian menagihnya sebelum
    dokumennya dicetak.
    """

    def _berkas(self):
        for pola in ("routes/*.py", "*.py"):
            for f in sorted(AKAR.glob(pola)):
                if f.name != BERKAS_PERAKIT:
                    yield f

    def test_pemindaiannya_menyapu_berkas_sungguhan(self):
        nama = {f.name for f in self._berkas()}
        assert {"bast.py", "persediaan.py", "reports.py", "docx_utils.py"} <= nama
        assert BERKAS_PERAKIT not in nama

    def test_nol_label_dipatok(self):
        pelanggar = []
        for f in self._berkas():
            try:
                pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(pohon):
                if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
                    continue
                # "NIP." di AWAL string = label baris tanda tangan. Label netral
                # diawali "NIP/" sehingga lolos; pesan galat menyebut NIP di
                # tengah kalimat, bukan di awal.
                if n.value.startswith("NIP."):
                    pelanggar.append(f"{f.name}:{n.lineno} {n.value[:30]!r}")
        assert pelanggar == []

    def test_nol_tebakan_NIP_polos(self):
        """Varian kedua dari cacat yang sama: nomor berformat TAK DIKENAL
        dilabeli `label_nomor_identitas(n) or "NIP"`. Deteksinya sendiri
        menyediakan label netral ("No. Identitas") — menebak di sini
        menghasilkan dokumen resmi yang menamai nomor orang dengan nama yang
        bukan namanya, persis seperti garis tanda tangan kosong.

        Judul KOLOM tabel boleh berbunyi "NIP/NIK" (itu memang nama kolom);
        yang dilarang konstanta "NIP" polos sebagai label sebuah nilai.
        """
        pelanggar = []
        for f in self._berkas():
            try:
                pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except SyntaxError:                     # pragma: no cover
                continue
            # "NIP" di dalam PERBANDINGAN bukan label — mis. menyaring pesan
            # galat dengan `if "NIP" not in e`. Menagihnya di situ memaksa
            # penulisan berbelit tanpa menambah satu pun kebenaran pada
            # dokumen yang tercetak.
            dibanding = set()
            for n in ast.walk(pohon):
                if isinstance(n, ast.Compare):
                    for x in [n.left, *n.comparators]:
                        dibanding.add(id(x))
            for n in ast.walk(pohon):
                if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and n.value == "NIP" and id(n) not in dibanding):
                    pelanggar.append(f"{f.name}:{n.lineno}")
        assert pelanggar == []

    def test_pengecualian_perbandingan_memang_sempit(self):
        """Pengecualiannya HANYA untuk perbandingan — label yang dioper
        sebagai nilai tetap tertangkap."""
        pohon = ast.parse('x = [("NIP", nip)]\nif "NIP" in e: pass')
        dibanding = set()
        for n in ast.walk(pohon):
            if isinstance(n, ast.Compare):
                for y in [n.left, *n.comparators]:
                    dibanding.add(id(y))
        kena = [n.lineno for n in ast.walk(pohon)
                if isinstance(n, ast.Constant) and n.value == "NIP"
                and id(n) not in dibanding]
        assert kena == [1]

    def test_deteksi_menyediakan_label_netral_untuk_format_asing(self):
        from pegawai_utils import deteksi_identitas
        assert deteksi_identitas("XYZ-123")["label"] == "No. Identitas"
        assert deteksi_identitas("")["label"] == "No. Identitas"

    def test_pemindainya_benar_benar_bisa_melihat(self):
        """Pemindai yang polanya salah akan selalu melaporkan nol."""
        pohon = ast.parse("x = 'NIP. ....................'")
        temuan = [n.value for n in ast.walk(pohon)
                  if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and n.value.startswith("NIP.")]
        assert temuan == ["NIP. ...................."]

    def test_label_netral_LOLOS_pemindaian(self):
        assert not PLACEHOLDER_IDENTITAS.startswith("NIP.")


class TestSemuaBerkasKeluaranMemakaiLabelNetral:
    """Berkas yang mencetak garis tanda tangan kosong WAJIB memakai konstanta
    bersama, bukan menuliskan labelnya sendiri."""

    BERKAS = ["routes/bast.py", "routes/pemusnahan.py", "routes/pengadaan.py",
              "routes/penggunaan.py", "routes/persediaan.py",
              "routes/reports.py", "routes/wasdal.py", "docx_utils.py",
              "shared_utils.py"]

    @pytest.mark.parametrize("nama", BERKAS)
    def test_mengimpor_dan_memakai_konstanta(self, nama):
        teks = (AKAR / nama).read_text(encoding="utf-8")
        assert "PLACEHOLDER_IDENTITAS" in teks, nama
        assert "from pegawai_utils import" in teks, nama


class TestLabelBlokIdentitas:
    """Blok identitas ('Nama / <label> / Jabatan') menamai nomornya dari
    DETEKSI, bukan dari tebakan.

    Berbeda dari baris tanda tangan: di blok identitas nomornya memang sudah
    tercetak, jadi yang dibutuhkan namanya yang BENAR — bukan penyembunyian
    setengah jalan yang justru menamai NIK sebagai "NIP".
    """

    def test_nip_pns(self):
        from pegawai_utils import label_identitas_cetak
        assert label_identitas_cetak(NIP) == "NIP"

    def test_nik_dinamai_NIK_bukan_NIP(self):
        from pegawai_utils import label_identitas_cetak
        assert label_identitas_cetak(NIK) == "NIK"

    def test_nrp_dinamai_NRP(self):
        from pegawai_utils import label_identitas_cetak
        assert label_identitas_cetak(NRP) == "NRP"

    def test_format_asing_dan_kosong_dapat_label_netral(self):
        from pegawai_utils import label_identitas_cetak
        assert label_identitas_cetak("XYZ-9") == "No. Identitas"
        assert label_identitas_cetak("") == "No. Identitas"

    def test_BERBEDA_dari_aturan_baris_tanda_tangan(self):
        """`label_nomor_identitas` menahan NIK (baris ttd dilewati demi
        privasi); `label_identitas_cetak` tidak — dua aturan untuk dua tempat
        yang berbeda, dan menyamakannya akan merusak salah satunya."""
        from pegawai_utils import label_identitas_cetak, label_nomor_identitas
        assert label_nomor_identitas(NIK) == ""
        assert label_identitas_cetak(NIK) == "NIK"
