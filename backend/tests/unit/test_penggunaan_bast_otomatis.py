"""Kelengkapan terkelola membaca sumber terkini, tidak memalsukan file scan."""
import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from mongomock_motor import AsyncMongoMockClient

import portal_bast_validitas as validitas
import routes.penggunaan as rp
from penggunaan_utils import bast_lengkap_tercatat, bast_sah, rekap_pemegang


USER = {"username": "operator", "role": "operator", "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def env(monkeypatch):
    import shared_utils as su
    db = AsyncMongoMockClient()["kelengkapan_bast"]
    state = SimpleNamespace(db=db, calls=[])
    monkeypatch.setattr(rp, "db", db)
    monkeypatch.setattr(su, "db", db)
    # mongomock belum mendukung $not+$regex+$options; penjaga filter punya
    # uji tersendiri. Pengujian ini hanya berisi aset nyata non-dummy.
    monkeypatch.setattr(rp, "tanpa_dummy_filter", lambda q: q)

    async def evaluate(database, b):
        state.calls.append(b["id"])
        return {"sah": b.get("_sah", True), "jenis": "esign", "kunci_bukti": "hash-final"}
    monkeypatch.setattr(validitas, "evaluasi_bast_sah", evaluate)
    return state


async def seed(env):
    await env.db.inventory_activities.insert_one({"id": "act", "kode_satker": "001"})
    receiver = {"pegawai_id": "pg1", "nama": "Pegawai", "nip": "111"}
    await env.db.bast_serah_terima.insert_one({
        "id": "b1", "kode_satker": "001", "asset_ids": ["a1", "a2"],
        "signature_request_id": "sr1", "portal_otomasi": {"version": 4,
            "items": [{"asset_id": aid, "penerima": receiver} for aid in ("a1", "a2")]}})
    assets = [{"id": aid, "user": "Pegawai", "pengguna_nip": "111", "asset_name": aid,
               "activity_id": "act", "bast_terakhir": {"id": "b1", "jenis": "penggunaan_melekat"},
               "amanah_bast": {"id": f"p-{aid}", "bast_id": "b1", "aksi": "serah",
                               "pegawai_id": "pg1", "kunci_bukti": "hash-final"}}
              for aid in ("a1", "a2")]
    await env.db.assets.insert_many(deepcopy(assets))
    return assets


def test_satu_evaluasi_per_bast_tanpa_menulis_master_atau_berkas(env):
    async def scenario():
        assets = await seed(env)
        await rp._lengkapi_bast_terkelola(assets, USER)
        assert env.calls == ["b1"]
        assert all(a["bast_otomatis_sah"] and bast_sah(a) for a in assets)
        assert all(a["bast_signature_request_id"] == "sr1" for a in assets)
        assert all("bast_file_id" not in a for a in assets)
        assert rekap_pemegang(assets)[0]["jumlah_bast"] == 2
        assert "bast_otomatis_sah" not in await env.db.assets.find_one({"id": "a1"})
    run(scenario())


@pytest.mark.parametrize("change", [
    {"amanah_bast.kunci_bukti": "hash-usang"},
    {"amanah_bast.aksi": "cabut"},
    {"bast_terakhir.id": "b-lain"},
    {"user": "Pemegang lain"},
])
def test_pointer_atau_pemegang_berubah_tidak_terlihat_lengkap(env, change):
    async def scenario():
        await seed(env)
        await env.db.assets.update_one({"id": "a1"}, {"$set": {**change, "bast_file_id": "scan-lama"}})
        a = await env.db.assets.find_one({"id": "a1"})
        await rp._lengkapi_bast_terkelola([a], USER)
        assert a["bast_otomatis_sah"] is False
        assert not bast_lengkap_tercatat(a) and not bast_sah(a)
        assert not a["bast_signature_request_id"]
    run(scenario())


def test_pembatalan_dibaca_ulang_tiap_request_dan_lintas_satker_ditolak(env):
    async def scenario():
        assets = await seed(env)
        await rp._lengkapi_bast_terkelola(assets, USER)
        await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"_sah": False}})
        await rp._lengkapi_bast_terkelola(assets, USER)
        assert not any(bast_sah(a) for a in assets)
        assert env.calls == ["b1", "b1"]
        await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"_sah": True, "kode_satker": "999"}})
        await rp._lengkapi_bast_terkelola(assets, USER)
        assert not any(bast_sah(a) for a in assets)
        assert env.calls == ["b1", "b1"]
    run(scenario())


def test_endpoint_rekap_dan_rincian_memakai_resolver_yang_sama(env):
    async def scenario():
        await seed(env)
        summary = await rp.daftar_pemegang(page=1, page_size=50, _user=USER)
        assert summary["items"][0]["jumlah_bast"] == 2
        assert summary["total_lengkap"] == 1
        rows = await rp.aset_pemegang(nama="Pegawai", nip="111", _user=USER)
        assert all(a["ada_bast"] and a["signature_request_id"] == "sr1" for a in rows["items"])
        assert env.calls == ["b1", "b1"]
    run(scenario())


def test_legacy_tanpa_amanah_tetap_mengikuti_semantik_lama(env):
    async def scenario():
        a = {"user": "Pegawai", "pengguna_nip": "111", "bast_file_id": "scan",
             "bast_terakhir": {"tt_dicabut": True}}
        await rp._lengkapi_bast_terkelola([a], USER)
        assert "bast_otomatis_sah" not in a
        assert rekap_pemegang([a])[0]["jumlah_bast"] == 1
        assert bast_sah(a) is False
        assert not env.calls
    run(scenario())
