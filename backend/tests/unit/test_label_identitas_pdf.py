"""Label NIP/NIK/NRP pada SEMUA keluaran PDF/DOCX terdeteksi, tak ditebak —
dan pada BLOK TANDA TANGAN, tidak dicetak sama sekali bila bukan NIP/NRP.

Permintaan pemilik, dua tahap. Mula-mula: *"pastikan di semua generate PDF
bagian NIP/NIK/NRP dapat otomatis terdeteksi."* Deteksinya dibangun, dan garis
tanda tangan yang masih kosong diberi satu label netral berupa titik-titik.

Lalu pemilik menyempitkannya: *"apabila pegawai tersebut tidak memiliki
informasi mengenai NIP dan/atau tergolong sebagai Non-ASN maka di bagian tanda
tangan tidak perlu dituliskan, jadi hanya tuliskan jika NIP/NRP saja … jadikan
ini aturan sistem … diterapkan saat generate PDF/Word ke depannya TANPA
KECUALI, khusus di bagian tanda tangan saja."*

Label netral titik-titik itu karena itu DIHAPUS — beserta konstantanya, supaya
tak ada jalan memakainya lagi. Aturan lengkapnya:
`docs/ATURAN-BLOK-TANDA-TANGAN.md`.

Perhatikan batas ruang lingkupnya: yang dikosongkan hanya BLOK TANDA TANGAN.
Kolom tabel, blok identitas, dan ekspor tetap mencetak nomor apa adanya —
di sana nomornya memang informasi yang diminta, bukan tanda pengesahan.
"""
import ast
import pathlib
import re

import pytest

from pegawai_utils import (
    baris_identitas_laporan, baris_identitas_ttd, label_nomor_identitas,
)

# Bentuk label yang DILARANG berdiri sendiri sebagai konstanta: "NIP.",
# "NIP/NIK/NRP. ............", "NIP/NIK. -" — label identitas tanpa nomor.
# Sengaja berjangkar di awal & akhir baris supaya kalimat penjelas yang
# kebetulan menyebut "NIP/NIK" di tengahnya tidak ikut tertangkap.
POLA_PLACEHOLDER = re.compile(
    r"^(NIP|NIK|NRP|NI PPPK)(/(NIK|NRP|NIP))*\s*[.:]\s*(\.{3,}|-)?\s*$")

AKAR = pathlib.Path(__file__).resolve().parents[2]
# Satu-satunya berkas yang BOLEH merakit "NIP. <nomor>" — di sinilah labelnya
# ditentukan dari hasil deteksi.
BERKAS_PERAKIT = "pegawai_utils.py"

NIP = "197001011990031001"
NIK = "3506042503900001"
NRP = "80123456"


class TestBlokTtdHanyaNipAtauNrp:
    """ATURAN SISTEM: di area tanda tangan, hanya NIP/NI PPPK/NRP yang
    dicetak. Selain itu blok tanda tangan berisi NAMA SAJA."""

    def test_nomor_kosong_tidak_menghasilkan_baris(self):
        assert baris_identitas_ttd("") == []
        assert baris_identitas_ttd(None) == []

    def test_garis_titik_juga_bukan_baris(self):
        """Nomor yang "ada" tetapi isinya hanya tanda baca adalah cara lain
        menuliskan 'belum ada NIP' — ia tak boleh lolos jadi baris."""
        for kosong in ("-", "--", "...", ". . .", "___", "  "):
            assert baris_identitas_ttd(kosong) == [], kosong

    def test_nomor_yang_ADA_tetap_dicetak(self):
        assert baris_identitas_ttd(NIP) == [f"NIP. {NIP}"]
        assert baris_identitas_ttd(NRP) == [f"NRP. {NRP}"]

    def test_konstanta_placeholder_sudah_TIDAK_ADA_lagi(self):
        """Dihapus, bukan sekadar tak dipakai: selama konstantanya ada, blok
        tanda tangan berikutnya akan memakainya lagi tanpa ada yang menahan."""
        import pegawai_utils
        assert not hasattr(pegawai_utils, "PLACEHOLDER_IDENTITAS")

    def test_parameter_placeholder_sudah_TIDAK_ADA_lagi(self):
        """Argumen ketiga dihapus, bukan dibiarkan bernilai bawaan kosong —
        pemanggil lama yang masih mengirim status kepegawaian di posisi
        ketiga harus GAGAL, bukan diam-diam salah slot."""
        import inspect
        param = list(inspect.signature(baris_identitas_ttd).parameters)
        assert param == ["nomor", "status_kepegawaian"]


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

    def test_tak_ada_lagi_label_yang_dikecualikan(self):
        """Dulu ada satu label yang sengaja diloloskan pemindaian (label
        netral titik-titik). Sekarang tidak ada pengecualian sama sekali."""
        assert POLA_PLACEHOLDER.search("NIP/NIK/NRP. ................")
        assert POLA_PLACEHOLDER.search("NIP/NIK. -")


class TestNolPlaceholderIdentitasDiSeluruhBackend:
    """ATURAN SISTEM berlaku "tanpa kecuali" — jadi yang menjaganya pun harus
    menyapu SELURUH backend, bukan daftar berkas yang harus diingat orang.

    Daftar berkas yang ditulis tangan gagal pada kasus yang justru paling
    mungkin terjadi: modul PDF/Word BARU. Ia lahir di luar daftar, jadi
    pemindaiannya hijau sejak hari pertama sementara dokumennya mencetak
    "NIP. ............" untuk penanda tangan Non-ASN.
    """

    def _berkas(self):
        for f in sorted(AKAR.glob("**/*.py")):
            bagian = set(f.parts)
            if "tests" in bagian or "__pycache__" in bagian or "node_modules" in bagian:
                continue
            yield f

    def test_pemindaiannya_menyapu_berkas_sungguhan(self):
        """Pemindai yang jalurnya salah menyapu nol berkas dan selalu hijau."""
        nama = {f.name for f in self._berkas()}
        assert {"bast.py", "persediaan.py", "reports.py", "docx_utils.py",
                "shared_utils.py", "penggunaan.py", "pengadaan.py",
                "wasdal.py", "pemusnahan.py"} <= nama
        assert len(nama) >= 50

    def test_polanya_benar_benar_menangkap(self):
        """Pola yang tak pernah cocok membuat pemindaian di bawah tak berarti."""
        assert POLA_PLACEHOLDER.search("NIP. ....................")
        assert POLA_PLACEHOLDER.search("NIP.")
        # …dan TIDAK menangkap yang sah:
        assert not POLA_PLACEHOLDER.search(f"NIP. {NIP}")
        assert not POLA_PLACEHOLDER.search("NIP/NIK Pegawai")
        assert not POLA_PLACEHOLDER.search("Non-ASN/NIK: baris NIP/NIK tidak dicetak.")

    def test_nol_placeholder_identitas(self):
        """PERKECUALIAN TUNGGAL: `pegawai_utils.py` boleh memuat literalnya —
        di situlah `BARIS_ISIAN_TANGAN` didefinisikan, satu-satunya baris
        identitas yang boleh dicetak pada garis tanda tangan KOSONG (lembar
        yang diisi tangan). Berkas lain tetap nol."""
        pelanggar = []
        for f in self._berkas():
            if f.name == BERKAS_PERAKIT:
                continue
            try:
                pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except SyntaxError:                     # pragma: no cover
                continue
            for n in ast.walk(pohon):
                if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
                    continue
                for baris in n.value.split("\n"):
                    if POLA_PLACEHOLDER.search(baris.strip()):
                        pelanggar.append(f"{f.name}:{n.lineno} {baris.strip()!r}")
        assert pelanggar == [], (
            "Blok tanda tangan tidak boleh mencetak label identitas tanpa "
            "nomor — lihat docs/ATURAN-BLOK-TANDA-TANGAN.md: " + "; ".join(pelanggar))

    def test_konstanta_lama_tidak_diimpor_di_mana_pun(self):
        for f in self._berkas():
            assert "PLACEHOLDER_IDENTITAS" not in f.read_text(encoding="utf-8"), f.name

    def test_literal_isian_HANYA_ada_di_berkas_perakitnya(self):
        """Perkecualiannya sempit karena literalnya berumah SATU. Menyalinnya
        ke modul lain mengembalikan kelas cacat yang sama: label dipatok yang
        tak seorang pun menagih kebenarannya."""
        from pegawai_utils import BARIS_ISIAN_TANGAN
        for f in self._berkas():
            if f.name == BERKAS_PERAKIT:
                continue
            assert BARIS_ISIAN_TANGAN not in f.read_text(encoding="utf-8"), f.name


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


class TestPdfSungguhanMematuhiAturan:
    """Bukti terakhir bukan pemindaian kode, melainkan **teks PDF-nya**.

    Pemindai statis menjaga agar labelnya tak ditulis ulang; ia tidak bisa
    membuktikan bahwa yang sampai ke kertas memang bersih. Uji ini merender
    blok tanda tangan sungguhan lalu membacanya kembali.
    """

    def _teks(self, penanda_tangan):
        import io
        import pypdfium2 as pdfium
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate
        import routes.reports as rrep
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4)
        doc.build(list(rrep._signature_block(penanda_tangan, doc.width)))
        return pdfium.PdfDocument(buf.getvalue())[0].get_textpage().get_text_range()

    def test_penanda_tangan_ber_nip_tetap_tercetak(self):
        teks = self._teks([{"header": "Yang Menerima,", "nama": "Sari",
                            "after": baris_identitas_ttd(NIP)}])
        assert "Sari" in teks
        assert f"NIP. {NIP}" in teks

    def test_nrp_tercetak_sebagai_NRP(self):
        teks = self._teks([{"header": "Yang Menerima,", "nama": "Rudi",
                            "after": baris_identitas_ttd(NRP)}])
        assert f"NRP. {NRP}" in teks

    @pytest.mark.parametrize("nomor,status", [
        ("", ""),                 # tak punya NIP
        ("-", ""),                # penanda "belum ada" era lama
        (NIK, ""),                # NIK
        (NIP, "non_asn"),         # Non-ASN meski nomornya berformat NIP
    ])
    def test_tanpa_nip_yang_sah_HANYA_nama_yang_tercetak(self, nomor, status):
        teks = self._teks([{"header": "Yang Menyerahkan,", "nama": "Budi",
                            "after": baris_identitas_ttd(nomor, status)}])
        assert "Budi" in teks
        for jejak in ("NIP", "NIK", "NRP"):
            assert jejak not in teks, teks


class TestAturannyaTertulisDiDokumentasi:
    """Pemilik meminta aturan ini *"ditulis di dalam dokumentasi agar
    diterapkan … ke depannya tanpa terkecuali"*. Dokumentasi yang hilang
    membuat aturannya hanya hidup di kepala orang yang menulisnya.
    """

    DOK = AKAR.parent / "docs" / "ATURAN-BLOK-TANDA-TANGAN.md"

    def test_dokumennya_ada(self):
        assert self.DOK.is_file(), self.DOK

    def test_menyebut_fungsi_yang_harus_dipakai(self):
        isi = self.DOK.read_text(encoding="utf-8")
        assert "baris_identitas_ttd" in isi
        assert "baris_identitas_laporan" in isi

    def test_menyebut_batas_ruang_lingkupnya(self):
        """Tanpa batas yang tertulis, aturan ini gampang melebar ke kolom
        tabel dan ekspor — tempat nomornya justru memang diminta."""
        isi = self.DOK.read_text(encoding="utf-8").lower()
        assert "kolom tabel" in isi
        assert "ekspor" in isi

    def test_kode_menunjuk_balik_ke_dokumennya(self):
        """Rujukan dua arah: yang membaca kodenya menemukan aturannya."""
        import pegawai_utils
        assert "ATURAN-BLOK-TANDA-TANGAN.md" in pegawai_utils.baris_identitas_ttd.__doc__


class TestPerkecualianLembarIsianTangan:
    """Lembar yang memang DIISI TANGAN — BA opname, pemantauan, pemusnahan —
    mencetak garis titik untuk NAMANYA juga: belum ada siapa pun di situ.

    Menghapus baris identitasnya (akibat aturan "tanpa kecuali") membuat
    penandatangan tak punya tempat menuliskan nomornya, dan ia menuliskannya
    menyilang di ruang kosong atau tidak sama sekali.
    """

    def test_labelnya_menyebut_PERSIS_dua_yang_boleh_dicetak(self):
        """Perkecualian ini tidak melonggarkan aturannya — ia menerapkannya
        pada lembar kosong. Karena itu NIK TIDAK boleh ikut disebut."""
        from pegawai_utils import BARIS_ISIAN_TANGAN
        assert "NIP" in BARIS_ISIAN_TANGAN and "NRP" in BARIS_ISIAN_TANGAN
        assert "NIK" not in BARIS_ISIAN_TANGAN

    def test_masih_berupa_garis_titik_untuk_ditulis_tangan(self):
        from pegawai_utils import BARIS_ISIAN_TANGAN
        assert "." * 8 in BARIS_ISIAN_TANGAN

    def test_muncul_saat_namanya_juga_kosong(self):
        from pegawai_utils import BARIS_ISIAN_TANGAN, baris_identitas_isian
        for kosong in (None, "", "   ", "..........................."):
            assert baris_identitas_isian(kosong) == [BARIS_ISIAN_TANGAN], kosong

    def test_HILANG_begitu_ada_nama_sungguhan(self):
        """Penjagaannya di dalam fungsi, bukan pada kedisiplinan pemanggil:
        begitu penanda tangannya diketahui, aturan pokok berlaku lagi."""
        from pegawai_utils import baris_identitas_isian
        assert baris_identitas_isian("Budi") == []
        assert baris_identitas_isian("  Sari  ") == []

    def test_berlaku_di_seluruh_lembar_isian_tangan(self):
        """Empat modul mencetak lembar semacam itu. Yang terlewat akan tampak
        benar — hanya kehilangan satu baris yang tak seorang pun sadari.

        DIHITUNG PEMANGGILANNYA, bukan kemunculan namanya. Versi pertama uji
        ini hanya mencari teks "baris_identitas_isian" di berkasnya — dan
        BARIS IMPORNYA saja sudah membuatnya hijau, sehingga modul yang
        berhenti memanggilnya tetap lolos.
        """
        for nama in ("routes/persediaan.py", "routes/pemusnahan.py",
                     "routes/wasdal.py", "routes/penggunaan.py"):
            pohon = ast.parse((AKAR / nama).read_text(encoding="utf-8"))
            panggil = [n for n in ast.walk(pohon)
                       if isinstance(n, ast.Call)
                       and getattr(n.func, "id", "") == "baris_identitas_isian"]
            assert panggil, nama

    def test_penghitung_panggilannya_benar_benar_membedakan(self):
        """Penjaga bagi penjaganya: pola yang hanya cocok pada impor akan
        membuat uji di atas selalu hijau."""
        pohon = ast.parse("from x import baris_identitas_isian\n")
        panggil = [n for n in ast.walk(pohon)
                   if isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "baris_identitas_isian"]
        assert panggil == []

    def test_aturannya_menyebut_perkecualian_ini(self):
        dok = (AKAR.parent / "docs" / "ATURAN-BLOK-TANDA-TANGAN.md").read_text(
            encoding="utf-8")
        assert "BARIS_ISIAN_TANGAN" in dok
        assert "isian tangan" in dok.lower()
