"""POST /assets menolak aset tanpa kegiatan (tinjauan mutu Nov 2026).

Dulu aset tanpa `activity_id` tersimpan (200) sebagai data yatim tanpa
satker: tak terjangkau laporan mana pun dan ditolak 403 oleh setiap pembaca.
"""
import asyncio

import pytest
from fastapi import HTTPException

import routes.assets as ra
from models import AssetCreate


class _Permintaan:
    headers = {}


def _jalan(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _buat(**kw):
    return AssetCreate(asset_code="3050102001", asset_name="Kursi lipat",
                       category="Peralatan dan Mesin", **kw)


@pytest.mark.parametrize("kegiatan", [None, "", "   "])
def test_tanpa_kegiatan_400_sebelum_menyentuh_db(monkeypatch, kegiatan):
    async def jangan(*_a, **_k):
        raise AssertionError("tidak boleh sampai ke pemeriksaan berikutnya")

    monkeypatch.setattr(ra, "pastikan_akses_kegiatan_id", jangan)
    monkeypatch.setattr(ra, "reserve_idempotency_key", jangan)
    user = {"username": "op", "role": "operator", "kode_satker": "990000"}
    with pytest.raises(HTTPException) as e:
        _jalan(ra.create_asset(_buat(activity_id=kegiatan), _Permintaan(), _user=user))
    assert e.value.status_code == 400
    assert "kegiatan" in e.value.detail
