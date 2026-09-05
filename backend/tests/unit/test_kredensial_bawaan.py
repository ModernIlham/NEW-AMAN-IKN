"""Tidak ada berkas yang boleh menjanjikan kredensial bawaan.

Runtime AMAN memang tidak pernah membuat akun bawaan — administrator pertama
hanya lahir lewat bootstrap ber-token sekali-pakai. Yang salah adalah dokumen
dan perkakasnya, dan dua-duanya salah dengan cara yang berbeda:

* **Dokumentasi** (`README.md`, `memory/PRD.md`) mengiklankan `admin`/`admin123`
  sebagai "Default Credentials". Itu bukan sekadar tidak aman melainkan TIDAK
  BENAR: yang mencobanya gagal masuk tanpa tahu sebabnya, dan yang
  mempercayainya justru membuat akun bertebak-tebakan itu dengan tangannya
  sendiri.

* **Harness Locust** jatuh ke pasangan yang sama bila environmentnya kosong.
  Bahayanya ada pada DIAMNYA: workflow live membaca `secrets.LOADTEST_*`, dan
  secret yang belum dipasang menjadi string kosong — bukan galat. Harness lalu
  berjalan mulus sambil menembakkan kredensial tebakan ke staging, dan
  kegagalan konfigurasi itu terbaca sebagai uji beban yang loginnya gagal
  semua.

Berkas ini menjalankan locustfile-nya sungguhan dengan Locust palsu — tanpa
satu pun request jaringan — lalu menagih dokumennya tetap jujur.
"""
import os
import pathlib
import subprocess
import sys

AKAR = pathlib.Path(__file__).resolve().parents[3]
LOCUSTFILE = AKAR / "scripts" / "loadtest" / "locustfile.py"
PANDUAN_LOADTEST = AKAR / "scripts" / "loadtest" / "README.md"
README = AKAR / "README.md"
PRD = AKAR / "memory" / "PRD.md"
WORKFLOW = AKAR / ".github" / "workflows" / "loadtest.yml"

# Locust tidak terpasang di lingkungan uji unit, dan memang tak perlu: yang
# diuji adalah gerbang kredensial di kepala modul, bukan Locust-nya.
_PEMUAT_LOCUST_PALSU = r"""
import runpy
import sys
import types

locust = types.ModuleType("locust")
locust.HttpUser = type("HttpUser", (), {})
locust.between = lambda *args: args
locust.task = lambda *args: (lambda fn: fn)
exception = types.ModuleType("locust.exception")
exception.StopUser = type("StopUser", (Exception,), {})
sys.modules["locust"] = locust
sys.modules["locust.exception"] = exception
runpy.run_path(sys.argv[1], run_name="aman_loadtest_uji")
"""


def _muat(env):
    lingkungan = os.environ.copy()
    lingkungan.pop("AMAN_USERNAME", None)
    lingkungan.pop("AMAN_PASSWORD", None)
    lingkungan.update(env)
    return subprocess.run(
        [sys.executable, "-c", _PEMUAT_LOCUST_PALSU, str(LOCUSTFILE)],
        capture_output=True, text=True, env=lingkungan, check=False)


# ── Gerbang kredensial harness ──────────────────────────────────────────

def test_tanpa_kredensial_berhenti_sebelum_request_apa_pun():
    hasil = _muat({})
    assert hasil.returncode != 0, "harness jalan tanpa kredensial"
    assert "wajib diisi" in hasil.stderr
    # Pesannya harus menyebut JALAN KELUARNYA. Berhenti tanpa memberitahu apa
    # yang harus dipasang membuat orang menebak, dan tebakan pertamanya
    # biasanya mengembalikan nilai bawaan yang baru saja dihapus.
    assert "LOADTEST_USERNAME" in hasil.stderr


def test_setengah_kredensial_juga_ditolak():
    # Username saja tak cukup; password kosong akan tetap dikirim ke server.
    assert _muat({"AMAN_USERNAME": "penguji"}).returncode != 0
    assert _muat({"AMAN_PASSWORD": "rahasia"}).returncode != 0


def test_username_spasi_saja_dianggap_kosong():
    # Secret yang "diisi" dengan spasi adalah kegagalan konfigurasi yang sama.
    assert _muat({"AMAN_USERNAME": "   ",
                  "AMAN_PASSWORD": "rahasia"}).returncode != 0


def test_kredensial_lengkap_membolehkan_modul_dimuat():
    hasil = _muat({"AMAN_USERNAME": "penguji-staging@contoh.go.id",
                   "AMAN_PASSWORD": "rahasia-staging"})
    assert hasil.returncode == 0, hasil.stderr


def test_password_TIDAK_dipangkas_spasinya():
    """Spasi di tepi password adalah karakter yang sah.

    Memangkasnya diam-diam mengubah kredensial yang dikirim menjadi bukan yang
    dimaksud pemakainya — lalu loginnya gagal dengan pesan "kredensial salah"
    yang tak menunjuk ke sebab sesungguhnya.
    """
    isi = LOCUSTFILE.read_text(encoding="utf-8")
    assert 'PASSWORD = os.environ.get("AMAN_PASSWORD", "")' in isi
    assert 'os.environ.get("AMAN_PASSWORD", "").strip()' not in isi


# ── Dokumentasi tetap jujur ─────────────────────────────────────────────

def test_tak_ada_dokumen_yang_mengiklankan_kredensial_bawaan():
    for berkas in (README, PRD, PANDUAN_LOADTEST, LOCUSTFILE):
        isi = berkas.read_text(encoding="utf-8")
        assert "admin123" not in isi, berkas.name
        assert "Default Credentials" not in isi, berkas.name


def test_README_dan_PRD_menyebut_bootstrap_sebagai_satu_satunya_jalan():
    for berkas in (README, PRD):
        isi = berkas.read_text(encoding="utf-8")
        assert "Tidak Ada Kredensial Bawaan" in isi, berkas.name
        assert "bootstrap" in isi.lower(), berkas.name


def test_panduan_loadtest_menyebut_kredensialnya_wajib():
    isi = PANDUAN_LOADTEST.read_text(encoding="utf-8")
    assert "Wajib" in isi


# ── Workflow ────────────────────────────────────────────────────────────

def test_live_run_memakai_secrets_dan_dry_run_memakai_nilai_fiktif():
    isi = WORKFLOW.read_text(encoding="utf-8")
    assert "AMAN_USERNAME: ${{ secrets.LOADTEST_USERNAME }}" in isi
    assert "AMAN_PASSWORD: ${{ secrets.LOADTEST_PASSWORD }}" in isi
    # Dry-run tetap mandiri: ia menguji locustfile-nya jalan, bukan loginnya.
    assert "AMAN_USERNAME: dry-run-tanpa-target" in isi
    assert "AMAN_PASSWORD: dry-run-tanpa-target" in isi


def test_nilai_fiktif_dry_run_tidak_menyerupai_kredensial_sungguhan():
    # Nilai fiktif yang terlihat masuk akal akan disalin orang ke tempat lain.
    isi = WORKFLOW.read_text(encoding="utf-8")
    assert "AMAN_USERNAME: admin" not in isi
    assert "admin123" not in isi
