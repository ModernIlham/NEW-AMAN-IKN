"""Tidak ada nomor peraturan yang boleh menyelinap ke dokumen bermeterai.

Dokumen keluaran AMAN memuat nomor peraturan lalu ditandatangani Kuasa
Pengguna Barang dan dibaca pemeriksa. Nomor-nomor itu tersebar sebagai teks
biasa di puluhan berkas; sebelum registry ini tak seorang pun tahu ada berapa,
mana yang pernah diriset, dan mana yang dieja berbeda untuk peraturan yang
sama.

Uji ini TIDAK menilai apakah suatu peraturan masih berlaku — teks asli JDIH
tak terjangkau dari lingkungan pengembangan, dan menebaknya justru pangkal
masalahnya. Yang ditegakkan hanya hal-hal yang bisa dipastikan tanpa akses
hukum sama sekali:

  1. Tiap sitasi yang sampai ke dokumen TERDAFTAR beserta provenansnya.
  2. Statusnya JUJUR terhadap pustaka riset — bukan sekadar klaim penulisnya.
  3. Repo tidak membantah dirinya sendiri (satu peraturan, dua sub-kode).
  4. Nomor peraturan di docstring/komentar TIDAK ikut ditagih — itu catatan
     untuk pengembang dan tak pernah sampai ke kertas.
"""
import os

import pytest

import sitasi_regulasi as S

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PUSTAKA_MD = os.path.join(BACKEND, "..", "docs", "PUSTAKA-REGULASI-BMN.md")


@pytest.fixture(scope="module")
def dipindai():
    return S.pindai_sumber(BACKEND)


@pytest.fixture(scope="module")
def kunci_pustaka():
    with open(PUSTAKA_MD, encoding="utf-8") as f:
        return S.kunci_pustaka(f.read())


class TestFungsiMurni:
    def test_rapikan_membuang_kata_nomor(self):
        assert S.rapikan("PMK  Nomor 181/PMK.06/2016.") == "PMK 181/PMK.06/2016"

    def test_sitasi_dalam_menangkap_beragam_bentuk(self):
        teks = ("Berdasarkan PP 27/2014 jo. PP 28/2020, PMK Nomor 83/PMK.06/2016 "
                "dan Surat Nomor S-115/KN/2017 serta PSAP 05.")
        assert S.sitasi_dalam(teks) == {
            "PP 27/2014", "PP 28/2020", "PMK 83/PMK.06/2016",
            "S-115/KN/2017", "PSAP 05"}

    def test_kunci_menyamakan_bentuk_panjang_dan_pendek(self):
        panjang = S.kunci_peraturan("PMK 181/PMK.06/2016")
        pendek = S.kunci_peraturan("PMK Nomor 181/2016")
        assert panjang == pendek == ("PMK", "181", "2016")

    def test_kunci_membedakan_jenis(self):
        """Inti deteksi: nomor & tahun sama, jenis beda → salah satu keliru."""
        assert S.kunci_peraturan("KMK 29/PMK.6/2010")[0] == "KMK"
        assert S.kunci_peraturan("PMK 29/PMK.06/2010")[0] == "PMK"
        assert S.kunci_peraturan("KMK 29/PMK.6/2010")[1:] == \
            S.kunci_peraturan("PMK 29/PMK.06/2010")[1:]

    def test_surat_dinas_dikenali(self):
        assert S.kunci_peraturan("S-115/KN/2017") == ("S", "115", "2017")

    def test_sub_kode_hanya_segmen_huruf(self):
        assert S.sub_kode("PMK 181/PMK.06/2016") == "PMK.06"
        # Bentuk pendek bukan pertentangan — cuma penyingkatan.
        assert S.sub_kode("PMK 181/2016") == ""
        assert S.sub_kode("PMK 181") == ""

    def test_masukan_kosong_aman(self):
        assert S.sitasi_dalam("") == set()
        assert S.sitasi_dalam(None) == set()
        assert S.kunci_peraturan("") == ("", "", "")


class TestPemindaian:
    def test_docstring_tidak_ikut_ditagih(self, tmp_path):
        """Menyebut peraturan di docstring justru dianjurkan — itu catatan
        pengembang, bukan teks yang tercetak. Bila pemindai ikut menagihnya,
        registry membengkak oleh hal yang tak pernah sampai ke kertas dan
        seluruh gerbang ini kehilangan makna."""
        modul = tmp_path / "contoh.py"
        modul.write_text(
            '"""Modul contoh sesuai PMK 999/PMK.06/2099."""\n'
            'JUDUL = "Berita Acara"\n', encoding="utf-8")
        assert S.pindai_sumber(str(tmp_path)) == {}

    def test_string_biasa_tertangkap(self, tmp_path):
        modul = tmp_path / "contoh.py"
        modul.write_text('DASAR = "sesuai PMK 999/PMK.06/2099 tentang apa pun"\n',
                         encoding="utf-8")
        assert set(S.pindai_sumber(str(tmp_path))) == {"PMK 999/PMK.06/2099"}


class TestRegistryTidakBolehMelenceng:
    def test_semua_sitasi_di_sumber_terdaftar(self, dipindai):
        """Gerbangnya: nomor peraturan baru di naskah → uji merah sampai
        seseorang menuliskan dari mana ia berasal."""
        belum = sorted(set(dipindai) - set(S.SITASI_TERDAFTAR))
        assert not belum, (
            "Sitasi berikut tercetak ke dokumen tetapi belum didaftarkan di "
            f"sitasi_regulasi.SITASI_TERDAFTAR: {belum}")

    def test_registry_tidak_menyimpan_sitasi_hantu(self, dipindai):
        """Sitasi yang sudah dicabut dari naskah harus dicabut juga dari
        registry — kalau tidak, daftar pertanyaan untuk Biro Hukum ikut
        memuat peraturan yang tak lagi dipakai siapa pun."""
        hantu = sorted(set(S.SITASI_TERDAFTAR) - set(dipindai))
        assert not hantu, f"terdaftar tetapi tak ada di sumber: {hantu}"

    def test_status_jujur_terhadap_pustaka(self, kunci_pustaka):
        """Status di registry diperiksa terhadap dokumen risetnya, bukan
        dipercaya begitu saja. Versi pertama registry ini salah pada LIMA
        entri — semuanya ketahuan justru oleh pemeriksaan ini."""
        salah = []
        for sitasi, status in S.SITASI_TERDAFTAR.items():
            ada = S.ada_di_pustaka(sitasi, kunci_pustaka)
            if status == S.PUSTAKA and not ada:
                salah.append(f"{sitasi}: diklaim '{S.PUSTAKA}' tapi tak ada di pustaka")
            if status == S.BELUM_RISET and ada:
                salah.append(f"{sitasi}: diklaim '{S.BELUM_RISET}' padahal ada di pustaka")
        assert not salah, salah

    def test_status_hanya_dari_nilai_baku(self):
        assert set(S.SITASI_TERDAFTAR.values()) <= {
            S.PUSTAKA, S.BELUM_RISET, S.PERLU_KOREKSI, S.TERVERIFIKASI,
            S.TEKS_PRIMER}


class TestRepoTidakMembantahDirinya:
    # Satu-satunya pertentangan yang SUDAH diketahui saat registry dibuat.
    # Didaftarkan eksplisit supaya pertentangan BARU tetap menjatuhkan uji,
    # dan supaya yang ini tidak diam-diam dianggap wajar selamanya.
    DIKETAHUI = {("KMK", "295", "2019")}

    def test_tak_ada_bentrokan_sub_kode_baru(self, dipindai):
        bentrok = set(S.bentrokan_sub_kode(set(dipindai))) - self.DIKETAHUI
        assert not bentrok, (
            f"peraturan yang sama ditulis dengan sub-kode berbeda: {sorted(bentrok)}")

    def test_bentrokan_yang_diketahui_masih_ada(self, dipindai):
        """Bila sudah diperbaiki, hapus dari DIKETAHUI — jangan biarkan
        daftar pengecualian menua tanpa ada yang menagih."""
        assert set(S.bentrokan_sub_kode(set(dipindai))) == self.DIKETAHUI

    def test_detektor_menangkap_bentrokan_jenis(self):
        """KMK vs PMK untuk nomor & tahun yang sama — tak perlu membuka satu
        pun peraturan untuk tahu salah satunya keliru."""
        bentrok = S.bentrokan_jenis({"KMK 29/PMK.6/2010", "PMK 29/PMK.06/2010"})
        assert ("29", "2010") in bentrok

    def test_bentrokan_jenis_tak_salah_tuduh(self):
        """Bentuk panjang & pendek peraturan yang SAMA bukan pertentangan."""
        assert S.bentrokan_jenis({"PMK 181/PMK.06/2016", "PMK 181/2016"}) == {}


class TestBuktiRisetTercatat:
    """Status `terverifikasi` tak boleh jadi klaim kosong. Tiap sitasi yang
    diberi status itu wajib punya jejaknya di laporan audit — kalau tidak,
    registry ini cuma memindahkan tebakan dari satu kolom ke kolom lain."""

    @pytest.fixture(scope="class")
    def laporan(self):
        p = os.path.join(BACKEND, "..", "docs", "SITASI-DOKUMEN-RESMI.md")
        with open(p, encoding="utf-8") as f:
            return f.read()

    def test_setiap_terverifikasi_ada_di_laporan(self, laporan):
        tanpa = [s for s, st in S.SITASI_TERDAFTAR.items()
                 if st == S.TERVERIFIKASI and s not in laporan]
        assert tanpa == [], f"diklaim terverifikasi tetapi tak ada buktinya: {tanpa}"

    def test_laporan_menyebut_batas_riset(self, laporan):
        """Yang dipastikan NOMOR & JUDUL, bukan isi pasal — sumber primer
        tetap terblokir. Batas itu harus tertulis, bukan tersirat."""
        assert "belum terbaca dari teks aslinya" in laporan.lower() \
            or "bukan pembacaan teks asli" in laporan.lower()

    def test_yang_belum_ketemu_tetap_tercatat(self):
        """KMK 339/KM.6/2024 tak ditemukan setelah empat sudut pencarian.
        Ia harus tetap berstatus belum-diriset, bukan diam-diam dianggap
        beres karena sisanya sudah ketemu."""
        assert S.SITASI_TERDAFTAR["KMK 339/KM.6/2024"] == S.BELUM_RISET


# ── TEKS_PRIMER: satu-satunya status yang tak bisa diklaim palsu ──────────

def test_teks_primer_berkasnya_memang_ada():
    """Status `teks-primer` menyatakan NASKAHNYA bisa dibaca — klaim
    terkuat di seluruh registry ini.

    Karena itu ia diperiksa terhadap artefaknya, bukan terhadap niat baik:
    tiap sitasi bertanda `teks-primer` wajib punya berkas di
    `docs/regulasi/MANIFEST.json`. Menempelkan status ini tanpa naskahnya
    langsung ketahuan di sini — tidak seperti tingkat lain, yang bertumpu
    pada seseorang pernah merisetnya.
    """
    import json
    import sitasi_regulasi as S

    dir_reg = os.path.join(BACKEND, "..", "docs", "regulasi")
    with open(os.path.join(dir_reg, "MANIFEST.json"), encoding="utf-8") as f:
        manifes = json.load(f)

    # Diperiksa terhadap BERKAS DI DISK, bukan terhadap manifesnya.
    # Manifes adalah catatan; catatan bisa keliru. Sebuah entri yang
    # `berkas`-nya None tetap muncul di daftar, jadi memeriksa manifes saja
    # akan meloloskan peraturan yang justru GAGAL diunduh — dan itu persis
    # klaim yang status ini ada untuk mencegahnya.
    tersedia = set()
    for b in manifes.get("berkas", []):
        nama = b.get("berkas")
        if not nama:
            continue
        jalur_teks = os.path.join(dir_reg, nama)
        if os.path.exists(jalur_teks) and os.path.getsize(jalur_teks) > 5000:
            tersedia.add(b["kode"])

    kurang = []
    for sitasi, status in S.SITASI_TERDAFTAR.items():
        if status != S.TEKS_PRIMER:
            continue
        _, nomor, tahun = S.kunci_peraturan(sitasi)
        if not (nomor and tahun):
            continue
        # Kode manifes berbentuk `<jenis>-<nomor>-<tahun>-<slug>`.
        pola = f"-{nomor}-{tahun}-"
        if not any(f"-{k}".find(pola) >= 0 for k in tersedia):
            kurang.append(sitasi)
    assert not kurang, (
        "Sitasi bertanda teks-primer tetapi naskahnya TIDAK ada di "
        f"docs/regulasi/: {kurang}")


def test_teks_primer_lebih_kuat_daripada_pustaka():
    """Peraturan yang naskahnya ada tak boleh turun lagi jadi `pustaka` —
    itu akan menyembunyikan bukti terkuat yang sudah dimiliki."""
    import sitasi_regulasi as S
    for sitasi in ("PMK 40/2024", "PMK 83/2016", "PMK 111/2016",
                   "PMK 115/2020",
                   # Dua peraturan INDUK — paling sering dirujuk registry
                   # syarat dokumen, jadi paling mahal bila statusnya
                   # diam-diam turun lagi.
                   "PP 27/2014", "PP 28/2020"):
        assert S.SITASI_TERDAFTAR[sitasi] == S.TEKS_PRIMER, sitasi
