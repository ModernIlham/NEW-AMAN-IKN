"""Kesetaraan rute orang luar dengan Master Pegawai internal (PGW-03).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — 3.5 (logika dipakai
bersama), 6.3, 6.4 (pengecualian), aturan main 1–3.
"""
import re
from pathlib import Path

import routes.pegawai as rp
import routes.pegawai_luar as rpl

BACKEND = Path(rp.__file__).resolve().parent.parent

# 6.4 — rute internal yang sengaja tanpa padanan luar.
PENGECUALIAN_SETARA = {
    ("GET", "/referensi"), ("GET", "/deteksi-identitas"),
    ("GET", "/{id}/sinkron-aset/pratinjau"), ("POST", "/{id}/sinkron-aset"),
    ("POST", "/kartu/identifikasi"),
}
# Templat, ekspor, impor — dibangun PGW-04. Hapus himpunan ini di sana.
MENUNGGU_PGW04 = {
    ("GET", "/template-impor"), ("GET", "/export-xlsx"), ("POST", "/impor"),
}
TAMBAHAN_LUAR = {("GET", "/rekap-lingkup")}


def _akhiran(router, awalan):
    out = set()
    for r in router.routes:
        for m in r.methods:
            if m == "HEAD":
                continue
            ekor = r.path[len(awalan):]
            out.add((m, re.sub(r"\{[^}]+\}", "{id}", ekor)))
    return out


def test_himpunan_rute_setara():
    internal = _akhiran(rp.pegawai_router, "/pegawai")
    luar = _akhiran(rpl.pegawai_luar_router, "/pegawai-luar")
    assert luar == (internal - PENGECUALIAN_SETARA - MENUNGGU_PGW04) | TAMBAHAN_LUAR


def test_pengecualian_masih_ada_di_internal():
    """Pengecualian yang tak lagi ada di internal harus dibuang dari daftar."""
    internal = _akhiran(rp.pegawai_router, "/pegawai")
    assert PENGECUALIAN_SETARA <= internal
    assert MENUNGGU_PGW04 <= internal


def test_model_luar_memuat_seluruh_field_internal():
    assert set(rpl.PegawaiLuarIn.model_fields) >= set(rp.PegawaiIn.model_fields)


def _sumber(rel):
    return (BACKEND / rel).read_text(encoding="utf-8")


def test_logika_internal_dipakai_ulang():
    src = _sumber("routes/pegawai_luar.py")
    for pola in ("_bersih(", "info_masa_pegawai(", "tulis_media(",
                 "validate_orang_luar("):
        assert pola in src, pola
    # validate_orang_luar menjalankan validate_pegawai milik internal.
    assert "validate_pegawai(" in _sumber("organisasi_luar_utils.py")


def test_larangan_tulis_koleksi_internal():
    pola = re.compile(r"db\.(pegawai|unit_kerja|satker|assets)\."
                      r"(insert|update|delete|bulk_write|replace)")
    for rel in ("routes/pegawai_luar.py", "routes/organisasi_luar.py"):
        assert not pola.search(_sumber(rel)), rel


def test_larangan_scope_satker_pada_direktori_bersama():
    for rel in ("routes/pegawai_luar.py", "routes/organisasi_luar.py"):
        assert "scope_query_field_satker(" not in _sumber(rel), rel


def test_larangan_portal():
    src = _sumber("routes/pegawai_luar.py")
    assert not re.search(r"^\s*(from|import)\s+portal_auth", src, re.M)
    assert "cabut_akses_portal" not in src and "cabut_email_bentrok" not in src


def test_larangan_balik_internal_tidak_mengenal_modul_luar():
    for rel in ("routes/pegawai.py", "routes/unit_kerja.py", "routes/satker.py"):
        assert "_luar" not in _sumber(rel), rel
