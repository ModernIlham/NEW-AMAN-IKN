"""CI tidak boleh menggantung tanpa batas.

Latar: 18 Agustus 2026, job "Backend (compileall + pytest unit)" tersangkut
**61 menit** di langkah `apt-get` pemasangan dependensi WeasyPrint. Bukan
gagal — menggantung: tidak ada baris baru, tidak ada galat. Dua job lain
sudah hijau dalam 2 menit, dan suite backend sendiri berjalan ~70 detik.

Yang membuatnya berbahaya adalah batas bawaan GitHub: **6 jam**. Selama itu
PR tidak bisa di-merge, dan sesi tanpa hak membatalkan run hanya bisa
menunggu. Dua pengaman dipasang:

1. `timeout-minutes` di setiap job — gagal cepat, jangan menggantung.
2. `apt-get` dibungkus `sudo timeout` + diulang — blip cermin paket runner
   tidak lagi menghabiskan satu jam.

Uji ini menjaga keduanya. Keduanya adalah baris yang gampang hilang saat
seseorang "merapikan" workflow tanpa tahu insiden ini.
"""
import os
import re

import pytest
import yaml

CI = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".github", "workflows", "ci.yml"))

# Job terlama (frontend build) normalnya <3 menit. 30 menit sudah sangat
# longgar; di atas itu namanya bukan batas lagi.
BATAS_MAKS_MENIT = 30


def _sumber():
    with open(CI, encoding="utf-8") as f:
        return f.read()


def _jobs():
    return yaml.safe_load(_sumber())["jobs"]


def _langkah_apt(jobs):
    for step in jobs["backend"]["steps"]:
        if "apt-get" in str(step.get("run", "")):
            return step["run"]
    pytest.fail("langkah apt-get di job backend tak ditemukan — perbarui uji ini")


class TestBatasWaktuJob:
    def test_semua_job_punya_batas_waktu(self):
        tanpa = [n for n, j in _jobs().items() if "timeout-minutes" not in j]
        assert not tanpa, (
            f"job tanpa timeout-minutes: {tanpa} — batas bawaan GitHub 6 jam, "
            "dan langkah yang menggantung membuat PR macet setengah hari")

    def test_batas_waktu_tidak_kelewat_longgar(self):
        # Sengaja hanya menilai job yang PUNYA batas — job tanpa batas sudah
        # jadi urusan uji di atas, dan satu cacat sebaiknya menggagalkan satu
        # uji saja supaya pesannya menunjuk ke sebab yang benar.
        longgar = {n: j["timeout-minutes"] for n, j in _jobs().items()
                   if j.get("timeout-minutes", 0) > BATAS_MAKS_MENIT}
        assert not longgar, (
            f"batas terlalu longgar: {longgar} menit — maksimal {BATAS_MAKS_MENIT}")


class TestAptTahanGantung:
    def test_apt_dibungkus_timeout(self):
        run = _langkah_apt(_jobs())
        assert re.search(r"sudo timeout \d+ apt-get", run), (
            "apt-get tidak dibungkus batas waktu — inilah yang menggantung "
            "61 menit pada 18 Agu 2026")

    def test_timeout_dijalankan_sebagai_root(self):
        """`timeout sudo apt-get` mengirim sinyal ke *sudo*, bukan ke apt-get.

        Prosesnya bisa selamat dan tetap memegang kunci /var/lib/dpkg,
        sehingga percobaan berikutnya gagal dengan "Could not get lock" —
        retry-nya jadi teater. Urutannya harus `sudo timeout apt-get`.
        """
        run = _langkah_apt(_jobs())
        terbalik = re.search(r"\btimeout\b[^\n|&;]*?\bsudo\b", run)
        assert not terbalik, (
            f"urutan terbalik ({terbalik.group(0)!r}): pakai `sudo timeout ... "
            "apt-get`, bukan `timeout ... sudo apt-get` — sinyal harus sampai "
            "ke apt-get sendiri, bukan berhenti di sudo")

    def test_apt_diulang_bila_gagal(self):
        run = _langkah_apt(_jobs())
        m = re.search(r"for \w+ in ([\d ]+); do", run)
        assert m, "tidak ada perulangan retry pada langkah apt-get"
        assert len(m.group(1).split()) >= 3, (
            "percobaan apt-get kurang dari 3 — blip cermin paket runner "
            "biasanya sekali lewat, sekali coba tidak cukup")

    def test_gagal_tegas_setelah_percobaan_habis(self):
        """Jangan berakhir sukses diam-diam: dependensi WeasyPrint yang tak
        terpasang membuat laporan PDF gagal, dan itu harus terlihat di CI."""
        run = _langkah_apt(_jobs())
        assert re.search(r"^\s*exit 1\s*$", run, re.M), (
            "langkah apt-get tidak pernah keluar dengan status gagal")
