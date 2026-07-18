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
