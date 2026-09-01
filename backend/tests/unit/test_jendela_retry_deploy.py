"""Anggaran retry deploy: sabar tanpa menghantam.

Dua insiden membentuk aturan di berkas ini.

**18 Agu 2026** — deploy gagal karena blip jaringan penyedia. Log sshd VPS
membuktikan paketnya TIDAK PERNAH SAMPAI. Jendela lama 5x(15s+20s) ~= 2,9 menit
habis tepat di dalam gangguan itu, jadi diperlebar menjadi ~6 menit.

**19 Agu 2026** — deploy gagal DUA KALI berturut-turut, keduanya menghabiskan
jendela 6 menit penuh, padahal delapan deploy sebelumnya hari itu sukses. Yang
menarik: kegagalan pertama terjadi tepat pada run PERTAMA yang memakai jendela
lebar itu. Dugaan yang konsisten dengan seluruh fakta — blip sesaat, lalu 8
percobaan beruntun terbaca sebagai percobaan penyusupan oleh fail2ban/proteksi
penyedia, lalu IP runner diblokir.

Pelajarannya: anggaran retry tak boleh disusun seolah ujung sana pasif.
KESABARAN dan TEKANAN adalah dua hal berbeda, dan yang kedua punya batas.

Maka berkas ini menjaga TIGA hal sekaligus, bukan satu:
  1. jendela tetap panjang (blip beberapa menit terlewati),
  2. jumlah percobaan tetap sedikit (tak terbaca sebagai serangan),
  3. hanya kegagalan tingkat KONEKSI yang diulang — skrip deploy yang benar
     benar berjalan lalu gagal tidak boleh diulang, sebab itu hanya mengulang
     kegagalan yang sama sambil menyamarkannya sebagai masalah jaringan.
"""
import os
import re

import pytest

DEPLOY = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".github", "workflows", "deploy.yml"))

# Serendah-rendahnya yang masih masuk akal. Angka ini NAIK setelah 19 Agu 13:32
# UTC: pesan ssh-nya "Connection timed out" — paket dijatuhkan diam-diam,
# persis aturan iptables DROP milik fail2ban (sshd mati akan menjawab
# "Connection refused"). Bantime bawaan fail2ban 10 menit, jadi jendela 6 menit
# tak pernah bisa melewatinya seberapa pun sabarnya. 11 menit adalah batas
# terendah yang masih melampaui bantime itu.
MINIMAL_DETIK = 660
# Setinggi-tingginya sebelum polanya menyerupai serangan. Angka ini yang naik
# ke 8 pada 18 Agu, dan dua kegagalan beruntun mengikutinya.
MAKS_PERCOBAAN = 5


def _sumber():
    with open(DEPLOY, encoding="utf-8") as f:
        return f.read()


def _tanpa_komentar(src):
    """Baris perintah saja — komentar boleh menyebut apa pun, termasuk nama
    perkakas yang justru sedang dilarang dipakai."""
    return "\n".join(b for b in src.splitlines()
                      if not b.strip().startswith("#"))


def _anggaran_detik(src):
    """(total_detik, jumlah_percobaan) dari perulangan retry koneksi."""
    bersih = _tanpa_komentar(src)
    percobaan = re.search(r"for attempt in ([\d ]+); do", bersih)
    jeda = re.search(r"gagal menjangkau VPS.*?\n\s*sleep (\d+)", bersih, re.S)
    timeout = re.search(r"ConnectTimeout=(\d+)", bersih)
    assert percobaan and jeda and timeout, "pola retry tak terbaca — perbarui uji ini"
    n = len(percobaan.group(1).split())
    # Jeda hanya terjadi di ANTARA percobaan (n-1 kali), timeout tiap percobaan.
    return n * int(timeout.group(1)) + (n - 1) * int(jeda.group(1)), n


class TestAnggaranRetry:
    def test_jendela_melampaui_bantime_lazim(self):
        """Jendela yang lebih pendek daripada masa blokir tak pernah berhasil,
        seberapa pun banyak percobaannya — ia hanya menunggu di dalam blokir
        lalu menyerah tepat sebelum blokirnya berakhir."""
        total, n = _anggaran_detik(_sumber())
        assert total >= MINIMAL_DETIK, (
            f"jendela retry hanya ~{total} detik ({n} percobaan) — lebih pendek "
            f"daripada bantime fail2ban bawaan (10 menit); butuh ≥ "
            f"{MINIMAL_DETIK} detik")

    def test_percobaan_tidak_terlalu_banyak(self):
        """Sisi yang baru dipelajari: memperbanyak percobaan bukan cuma
        mubazir, ia bisa memicu pemblokiran yang membuat SEMUA deploy
        berikutnya gagal."""
        _, n = _anggaran_detik(_sumber())
        assert n <= MAKS_PERCOBAAN, (
            f"{n} percobaan beruntun — pola ini yang diduga memicu pemblokiran "
            "pada 19 Agu 2026; perpanjang JEDA-nya, bukan jumlahnya")

    def test_pesan_galat_mengarahkan_ke_penyedia(self):
        """Pesan lama hanya menyuruh memeriksa secret dan 'VPS hidup' — dan itu
        justru menyesatkan, karena VPS-nya memang hidup."""
        src = _sumber()
        assert "penyedia" in src.lower()
        assert "fail2ban" in src.lower(), (
            "pesan galat tak menyebut pemeriksaan yang paling menentukan")


class TestTekananKoneksi:
    def test_tanpa_probe_terpisah(self):
        """`ssh-keyscan` menggandakan jumlah koneksi tiap deploy tanpa
        menambah keamanan: ia sama-sama trust-on-first-use dengan
        `StrictHostKeyChecking=accept-new` pada koneksi yang memang dipakai."""
        bersih = _tanpa_komentar(_sumber())
        assert "ssh-keyscan" not in bersih
        assert "StrictHostKeyChecking=accept-new" in bersih

    def test_hanya_kegagalan_koneksi_yang_diulang(self):
        """255 adalah kode keluar ssh untuk kegagalan tingkat koneksi. Tanpa
        pembedaan ini, skrip deploy yang gagal akan dijalankan ulang berkali
        kali dan sebabnya tersamar sebagai 'masalah jaringan'."""
        bersih = _tanpa_komentar(_sumber())
        assert re.search(r'"\$rc" -ne 255', bersih), (
            "tak ada pembedaan kegagalan koneksi vs kegagalan skrip")

    def test_kegagalan_skrip_berhenti_seketika(self):
        bersih = _tanpa_komentar(_sumber())
        assert re.search(r'exit "\$rc"', bersih), (
            "kegagalan skrip tidak diteruskan sebagai kegagalan job")


class TestDokumenTidakLagiMenyesatkan:
    """Dokumen VPS pernah dijadikan dasar diagnosis yang salah karena
    menyatakan swap belum dipasang padahal sudah."""

    def _doc(self):
        p = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "docs", "OPTIMASI-VPS.md"))
        with open(p, encoding="utf-8") as f:
            return f.read()

    def test_status_swap_terverifikasi_tercatat(self):
        d = self._doc()
        assert "Status terverifikasi" in d
        assert "SUDAH DIPASANG" in d or "SUDAH DIKERJAKAN" in d

    def test_insiden_jaringan_terdokumentasi(self):
        # Spasi dinormalkan: frasa kunci bisa terpenggal baris oleh pembungkus
        # teks Markdown, dan uji yang bergantung pada posisi baris rapuh tanpa
        # alasan. Pelajaran yang sama sudah muncul pada uji panel Riwayat.
        d = re.sub(r"\s+", " ", self._doc()).lower()
        assert "insiden jaringan penyedia" in d
        assert "tidak pernah sampai" in d


class TestGitFetchDiVpsBolehDiulang:
    """Deploy 1 Sep 2026 gagal dengan pola yang belum pernah muncul.

    SSH ke VPS BERHASIL, skripnya jalan, lalu::

        fatal: unable to access 'https://github.com/…': Failed to connect to
        github.com port 443 after 133334 ms: Couldn't connect to server

    Kaki jaringan yang putus bukan runner→VPS melainkan **VPS→GitHub**.
    Workflow hanya mengulang kegagalan tingkat koneksi SSH (exit 255); ini
    exit 128, jadi tak diulang — padahal justru jenis yang paling pantas
    diulang.

    Mengulangnya di dalam skrip TIDAK melanggar aturan kelas di atas. Aturan
    itu menahan pengulangan kegagalan yang MENGUBAH keadaan; `git fetch`
    berjalan sebelum `git reset`, jadi sampai titik itu belum ada apa pun
    yang berubah — dan itulah sifat yang diuji di sini.
    """

    def _skrip(self):
        p = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "scripts", "deploy_vps.sh"))
        with open(p, encoding="utf-8") as f:
            return f.read()

    def test_git_fetch_diulang_bukan_sekali_jalan(self):
        s = self._skrip()
        assert "ambil_perubahan()" in s, "git fetch masih panggilan tunggal"
        assert re.search(r"for n in 1 2 3", s), "jumlah percobaannya tak terbaca"

    def test_pengulangan_terjadi_SEBELUM_apa_pun_berubah(self):
        """Sifat yang membuat pengulangan ini sah. Kalau `git reset --hard`
        pindah ke ATAS pemanggilan `ambil_perubahan`, pengulangannya berubah
        makna menjadi mengulang deploy yang sudah menyentuh produksi."""
        s = self._skrip()
        panggil = s.index("\nambil_perubahan\n")
        reset = s.index('git reset --hard "origin/${DEPLOY_BRANCH}"')
        assert panggil < reset, (
            "git reset mendahului fetch — pengulangannya tak lagi aman")

    def test_percobaannya_sedikit_bukan_lima(self):
        """Kesabaran dan tekanan adalah dua hal berbeda (lihat docstring
        modul). Tiga percobaan cukup melewati blip, tak cukup terbaca sebagai
        tekanan."""
        s = self._skrip()
        blok = s[s.index("ambil_perubahan()"):s.index("\nambil_perubahan\n")]
        assert "1 2 3 4 5" not in blok

    def test_kegagalannya_menyebut_SISI_VPS(self):
        """Pesan yang tak menyebut sisinya membuat pembacanya mencari cacat
        kode yang tidak ada — persis yang terjadi pada insiden ini."""
        s = re.sub(r"\s+", " ", self._skrip())
        assert "GAGAL JARINGAN DI SISI VPS" in s
        assert "produksi tetap pada commit" in s, (
            "tak menyebut bahwa tak ada yang berubah")

    def test_workflow_tak_lagi_mengaku_tahu_bahwa_bukan_jaringan(self):
        """Langkah di workflow hanya tahu SATU hal dengan pasti: koneksi
        runner ke VPS berhasil. Menyimpulkan lebih dari itu menyesatkan."""
        p = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            ".github", "workflows", "deploy.yml"))
        with open(p, encoding="utf-8") as f:
            w = f.read()
        pesan = [b for b in w.splitlines()
                 if "::error::Koneksi runner ke VPS" in b]
        assert pesan, "pesan galatnya hilang"
        assert "Ini bukan masalah jaringan" not in w
