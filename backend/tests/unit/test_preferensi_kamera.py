"""Uji preferensi kamera server — CERMIN dari lib/preferensiKamera.js.

Bila salah satu sisi berubah tanpa yang lain, setelan yang tersimpan akan
berbeda dari yang dipakai kamera; uji di kedua sisi membuat pergeseran itu
ketahuan.
"""
from preferensi_kamera import (
    BAWAAN, KUALITAS_MAX, RESOLUSI_MAX, RESOLUSI_MIN, normalkan,
)


def test_nilai_sah_dipertahankan():
    assert normalkan({"orientasi": "potret", "resolusi": 2560, "kualitas": 92}) == {
        "orientasi": "potret", "resolusi": 2560, "kualitas": 92}


def test_nilai_rusak_jatuh_ke_bawaan():
    """Setelan kamera tak boleh menggagalkan pemotretan hanya karena satu field
    rusak/usang — field bermasalah diganti bawaan, sisanya tetap dipakai."""
    assert normalkan(None) == BAWAAN
    assert normalkan("bukan objek") == BAWAAN
    assert normalkan({"orientasi": "miring", "resolusi": "abc"}) == BAWAAN
    assert normalkan({"orientasi": "lanskap", "resolusi": None})["orientasi"] == "lanskap"


def test_angka_di_luar_batas_dijepit():
    assert normalkan({"resolusi": 99999})["resolusi"] == RESOLUSI_MAX
    assert normalkan({"resolusi": 1})["resolusi"] == RESOLUSI_MIN
    assert normalkan({"kualitas": 500})["kualitas"] == KUALITAS_MAX


def test_bawaan_setara_pipeline_lama():
    """Akun yang belum pernah menyetel harus memotret PERSIS seperti sebelum
    fitur ini ada — 1920 px, q0.85 — supaya tak ada perubahan diam-diam."""
    assert BAWAAN == {"orientasi": "auto", "resolusi": 1920, "kualitas": 85}


def test_bool_bukan_angka_yang_sah():
    """True/False kebetulan lolos float() di Python; tanpa penjagaan ini
    `resolusi: true` akan tersimpan sebagai 640 tanpa ada yang sadar."""
    p = normalkan({"resolusi": True, "kualitas": False})
    assert p["resolusi"] == BAWAAN["resolusi"]
    assert p["kualitas"] == BAWAAN["kualitas"]
