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
