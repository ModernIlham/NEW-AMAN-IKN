"""Harness load test tidak boleh mengarang kredensial yang tampak resmi.

Kredensial bawaan lama tidak dipakai runtime AMAN, tetapi dokumentasi dan
Locust masih membuat orang mengira akun ``admin`` tersedia. Lebih buruk,
workflow live dapat tampak berjalan dengan fallback itu ketika secrets kosong.
Tes ini mengeksekusi modul dengan Locust palsu; tidak ada request jaringan.
"""
import os
import pathlib
import subprocess
import sys


AKAR = pathlib.Path(__file__).resolve().parents[3]
LOCUSTFILE = AKAR / "scripts" / "loadtest" / "locustfile.py"
PANDUAN = AKAR / "scripts" / "loadtest" / "README.md"
README = AKAR / "README.md"
WORKFLOW = AKAR / ".github" / "workflows" / "loadtest.yml"


_PEMUAT_DENGAN_LOCUST_PALSU = r"""
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


def _jalankan(env):
    lingkungan = os.environ.copy()
    lingkungan.pop("AMAN_USERNAME", None)
    lingkungan.pop("AMAN_PASSWORD", None)
    lingkungan.update(env)
    return subprocess.run(
        [sys.executable, "-c", _PEMUAT_DENGAN_LOCUST_PALSU,
         str(LOCUSTFILE)],
        capture_output=True,
        text=True,
        env=lingkungan,
        check=False,
    )


def test_tanpa_kredensial_gagal_cepat_sebelum_request():
    hasil = _jalankan({})
    assert hasil.returncode != 0
    assert "AMAN_USERNAME dan AMAN_PASSWORD wajib" in hasil.stderr


def test_kredensial_eksplisit_membolehkan_modul_dimuat():
    hasil = _jalankan({
        "AMAN_USERNAME": "penguji-staging@domain.go.id",
        "AMAN_PASSWORD": "rahasia-staging",
    })
    assert hasil.returncode == 0, hasil.stderr


def test_dokumentasi_tidak_mengiklankan_kredensial_bawaan_lama():
    gabungan = "\n".join((
        README.read_text(encoding="utf-8"),
        PANDUAN.read_text(encoding="utf-8"),
        LOCUSTFILE.read_text(encoding="utf-8"),
    ))
    assert "admin123" not in gabungan
    assert "Default Credentials" not in gabungan
    assert "Tidak Ada Kredensial Bawaan" in gabungan


def test_workflow_dry_run_fiktif_dan_live_tetap_memakai_secrets():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "AMAN_USERNAME: dry-run-tidak-dipakai" in workflow
    assert "AMAN_PASSWORD: dry-run-tidak-dipakai" in workflow
    assert "AMAN_USERNAME: ${{ secrets.LOADTEST_USERNAME }}" in workflow
    assert "AMAN_PASSWORD: ${{ secrets.LOADTEST_PASSWORD }}" in workflow
