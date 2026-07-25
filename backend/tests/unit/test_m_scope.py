"""Uji helper ISOLASI DATA PER-SATKER (M-SCOPE) — logika murni tanpa Mongo."""
import asyncio

import pytest
from fastapi import HTTPException

import shared_utils as su


def test_kode_satker_user():
    assert su.kode_satker_user({"kode_satker": "527"}) == "527"
    assert su.kode_satker_user({"kode_satker": "  527  "}) == "527"
    assert su.kode_satker_user({"kode_satker": ""}) == ""
    assert su.kode_satker_user({}) == ""
    assert su.kode_satker_user(None) == ""


def test_pastikan_akses_kegiatan():
    run = asyncio.run
    # Lintas-satker (kode kosong) → bebas
    run(su.pastikan_akses_kegiatan({"kode_satker": ""}, {"kode_satker": "111"}))
    # Satker sama → boleh
    run(su.pastikan_akses_kegiatan({"kode_satker": "111"}, {"kode_satker": "111"}))
    # Kegiatan era lama tanpa kode → terbuka
    run(su.pastikan_akses_kegiatan({"kode_satker": "111"}, {"kode_satker": ""}))
    run(su.pastikan_akses_kegiatan({"kode_satker": "111"}, {}))
    # Satker beda → 403
    with pytest.raises(HTTPException) as e:
        run(su.pastikan_akses_kegiatan({"kode_satker": "111"}, {"kode_satker": "222"}))
    assert e.value.status_code == 403


def test_scope_query_kegiatan():
    run = asyncio.run
    assert run(su.scope_query_kegiatan({"kode_satker": ""}, {"a": 1})) == {"a": 1}
    out = run(su.scope_query_kegiatan({"kode_satker": "527"}, {"a": 1}))
    assert out == {"a": 1, "kode_satker": "527"}
    # Query asal tidak dimutasi
    q = {"a": 1}
    run(su.scope_query_kegiatan({"kode_satker": "527"}, q))
    assert q == {"a": 1}


def test_scope_query_field_satker_dan_guard_dok():
    run = asyncio.run
    # Lintas-satker → query utuh
    assert su.scope_query_field_satker({"kode_satker": ""}, {"a": 1}) == {"a": 1}
    # Terikat → item satker sendiri + era lama (kosong/None/hilang)
    out = su.scope_query_field_satker({"kode_satker": "527"}, {"a": 1})
    assert out == {"a": 1, "kode_satker": {"$in": ["527", "", None]}}
    # Guard dokumen: era lama & satker sendiri terbuka; satker lain 403
    run(su.pastikan_akses_dok_satker({"kode_satker": "527"}, {}))
    run(su.pastikan_akses_dok_satker({"kode_satker": "527"}, {"kode_satker": ""}))
    run(su.pastikan_akses_dok_satker({"kode_satker": "527"}, {"kode_satker": "527"}))
    run(su.pastikan_akses_dok_satker({"kode_satker": ""}, {"kode_satker": "111"}))
    with pytest.raises(HTTPException) as e:
        run(su.pastikan_akses_dok_satker({"kode_satker": "527"}, {"kode_satker": "111"}))
    assert e.value.status_code == 403


def test_scope_query_aset(monkeypatch):
    run = asyncio.run

    async def fake_ids(kode):
        assert kode == "527"
        return ["act-1", "act-2"]

    monkeypatch.setattr(su, "id_kegiatan_satker", fake_ids)
    # Lintas-satker → utuh
    assert run(su.scope_query_aset({"kode_satker": ""}, {"x": 1})) == {"x": 1}
    # activity_id sudah spesifik → tidak ditimpa (guard terpisah yang menolak)
    q = {"activity_id": "act-9"}
    assert run(su.scope_query_aset({"kode_satker": "527"}, q)) == q
    # Tanpa activity_id → dibatasi $in kegiatan satker
    out = run(su.scope_query_aset({"kode_satker": "527"}, {"x": 1}))
    assert out["activity_id"] == {"$in": ["act-1", "act-2"]} and out["x"] == 1


# ── R9: guard pengelolaan AKUN lintas satker ────────────────────────────────
# Beda dari dokumen: pada akun, kode_satker KOSONG + role admin = super-admin
# pusat (harus paling terlindung), bukan "era lama, terbuka".

def _kelola(admin, target):
    from auth_utils import pastikan_kelola_akun
    return pastikan_kelola_akun(admin, target)


def test_kelola_akun_super_admin_bebas():
    su_admin = {"role": "admin", "kode_satker": ""}
    _kelola(su_admin, {"role": "admin", "kode_satker": "111"})
    _kelola(su_admin, {"role": "viewer", "kode_satker": ""})


def test_kelola_akun_satker_sama_boleh():
    _kelola({"role": "admin", "kode_satker": "111"},
            {"role": "operator", "kode_satker": "111"})


def test_kelola_akun_satker_lain_ditolak():
    with pytest.raises(HTTPException) as e:
        _kelola({"role": "admin", "kode_satker": "111"},
                {"role": "admin", "kode_satker": "222"})
    assert e.value.status_code == 403


def test_kelola_akun_super_admin_tak_boleh_disentuh_admin_satker():
    """Akun admin TANPA ikatan satker = super-admin pusat → selalu 403.

    Ini yang mencegah pengambilalihan: admin satker mereset password akun
    pusat lalu login sebagai super-admin.
    """
    with pytest.raises(HTTPException) as e:
        _kelola({"role": "admin", "kode_satker": "111"},
                {"role": "admin", "kode_satker": ""})
    assert e.value.status_code == 403


def test_kelola_akun_pendaftar_baru_boleh_di_onboard():
    """Registrasi mandiri menghasilkan akun viewer nonaktif TANPA ikatan —
    admin satker tetap harus bisa mengaktifkan lalu mengikatnya."""
    _kelola({"role": "admin", "kode_satker": "111"},
            {"role": "viewer", "kode_satker": ""})
    _kelola({"role": "admin", "kode_satker": "111"}, {"role": "viewer"})


def test_kelola_akun_admin_tanpa_satker_bukan_admin_role_ditolak():
    """Pemanggil tanpa ikatan satker DAN bukan admin → tak berwenang."""
    with pytest.raises(HTTPException) as e:
        _kelola({"role": "operator", "kode_satker": ""},
                {"role": "viewer", "kode_satker": "111"})
    assert e.value.status_code == 403


# ── R10: token berkas ekspor dipersempit ────────────────────────────────────

def test_token_docfile_scope_dan_umur():
    """Tautan doc-file di dalam CSV/XLSX membawa token; token itu harus
    SESEMPIT mungkin karena berkas ekspor rutin dikirim ke auditor/KPKNL."""
    import jwt as _jwt
    import auth_utils as au

    tok = au.create_docfile_token("u1", "budi", 3)
    payload = _jwt.decode(tok, au.JWT_SECRET, algorithms=[au.JWT_ALGORITHM])
    assert payload["scope"] == "docfile"        # bukan "media" (30 hari, ~30 endpoint)
    assert payload["sesi_epoch"] == 3           # ikut dicabut saat reset password
    assert au.DOCFILE_TOKEN_EXPIRATION_DAYS == 7
    assert au.DOCFILE_TOKEN_EXPIRATION_DAYS < au.MEDIA_TOKEN_EXPIRATION_DAYS


# ── R15: PATCH aset — field berbentuk list boleh, operator NoSQL tetap ditolak ──

def test_patch_field_list_diizinkan_operator_ditolak():
    """`photos` & `document_checklist` ADA di PATCHABLE_FIELDS dan memang
    berbentuk list. Dulu semua list ditolak → kedua field itu mustahil di-PATCH
    (selalu 400). Yang harus ditolak hanyalah operator NoSQL."""
    from fastapi import HTTPException

    # Replika logika guard di routes/assets.py patch_asset.
    FIELD_LIST = {"photos", "document_checklist"}

    def bebas_operator(nilai, jalur):
        if isinstance(nilai, dict):
            for kk, vv in nilai.items():
                if not isinstance(kk, str) or kk.startswith("$") or "." in kk:
                    raise HTTPException(status_code=400, detail=jalur)
                bebas_operator(vv, jalur)
        elif isinstance(nilai, list):
            for vv in nilai:
                bebas_operator(vv, jalur)

    def guard(update):
        for k, v in update.items():
            if k in FIELD_LIST:
                if not isinstance(v, list):
                    raise HTTPException(status_code=400, detail=k)
                bebas_operator(v, k)
            elif isinstance(v, (dict, list)):
                raise HTTPException(status_code=400, detail=k)

    # Kelengkapan dokumen yang wajar → LOLOS (dulu 400).
    guard({"document_checklist": [{"nama": "BAST", "ada": True, "files": []}]})
    guard({"photos": ["data:image/webp;base64,AAAA"]})

    # Operator NoSQL di kedalaman mana pun → DITOLAK.
    for jahat in (
        {"document_checklist": [{"nama": {"$ne": None}}]},
        {"document_checklist": [{"a": {"b": {"$gt": ""}}}]},
        {"document_checklist": [{"pakai.titik": 1}]},
    ):
        try:
            guard(jahat)
            raise AssertionError(f"seharusnya ditolak: {jahat}")
        except HTTPException:
            pass

    # Field SKALAR tetap menolak list/dict.
    for jahat in ({"asset_code": {"$ne": None}}, {"NUP": ["a"]}):
        try:
            guard(jahat)
            raise AssertionError(f"seharusnya ditolak: {jahat}")
        except HTTPException:
            pass


# ── R15: Idempotency-Key terikat pemilik ────────────────────────────────────

def test_kunci_idem_terikat_pemilik():
    """Kunci idempotensi dipilih KLIEN. Bila disimpan apa adanya, siapa pun
    yang menebak kunci satker lain dapat memutar ulang respons tersimpan
    mereka. Kunci efektif harus berbeda per akun."""
    from shared_utils import kunci_idem

    a = {"id": "u-a", "username": "andi", "kode_satker": "527"}
    b = {"id": "u-b", "username": "budi", "kode_satker": "999"}

    assert kunci_idem("ABC", a) != kunci_idem("ABC", b)   # inti temuan
    assert kunci_idem("ABC", a) == kunci_idem("ABC", a)   # tetap idempoten
    assert kunci_idem("", a) == ""                        # kosong = nonaktif
    assert "ABC" in kunci_idem("ABC", a)
