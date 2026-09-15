"""Regresi deteksi ulang: denah, data induk, dan versi harus satu simpanan."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import shared_utils
import meili_utils
from routes import spasial, websocket

USER = {"id": "u1", "username": "uji", "name": "Petugas Uji", "kode_satker": "A"}


def request(version="3", key="k1"):
    headers = [(k.encode(), v.encode()) for k, v in (
        ("if-match", version), ("idempotency-key", key)) if v is not None]
    return Request({"type": "http", "headers": headers})


async def siapkan(monkeypatch):
    db = AsyncMongoMockClient().uji
    monkeypatch.setattr(spasial, "db", db)
    monkeypatch.setattr(shared_utils, "db", db)
    monkeypatch.setattr(shared_utils, "invalidate_asset_cache", Mock())
    monkeypatch.setattr(meili_utils, "jadwalkan_sync", Mock())
    monkeypatch.setattr(websocket, "notify_asset_change", AsyncMock())
    await db.inventory_activities.insert_one({"id": "k1", "kode_satker": "A"})
    await db.assets.insert_one({"id": "a1", "activity_id": "k1", "version": 3,
        "asset_name": "Meja", "asset_code": "123", "NUP": "2", "notes": "Tetap",
        "location": "Ruang Lama", "koordinat_latitude": "-1.4", "koordinat_longitude": "116.7",
        "geo": {"type": "Point", "coordinates": [116.7, -1.4]},
        "lokasi_spasial": {"node_id": "lama", "titik": [116.7, -1.4]}})
    await db.spasial_node.insert_one({"id": "baru", "kode_satker": "A", "status": "aktif",
        "nama": "Ruang Baru", "tipe": "RUANGAN", "ancestors_nama": ["Gedung B", "Lantai 2"]})
    return db


async def simpan(req=None, **isi):
    return await spasial.set_lokasi_aset("a1", spasial.LokasiAsetIn(
        **({"lat": "-1,5", "lon": "116,8", "node_id": "baru"} | isi)), req or request(), USER)


def test_pindah_menyamakan_geo_snapshot_riwayat_tanpa_menimpa_lokasi_manual(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        hasil = await simpan()
        a = await db.assets.find_one({"id": "a1"})
        assert a["version"] == hasil["asset"]["version"] == 4
        assert a["location"] == "Ruang Lama"
        assert a["koordinat_latitude"] == "-1.5"
        assert a["koordinat_longitude"] == "116.8"
        assert a["geo"]["coordinates"] == a["lokasi_spasial"]["titik"] == [116.8, -1.5]
        assert a["notes"] == "Tetap"
        assert hasil["asset"]["di_denah"] is True
        assert hasil["asset"]["denah_nama"] == "Ruang Baru"
        assert hasil["asset"]["denah_jalur"] == "Gedung B / Lantai 2 / Ruang Baru"
        assert hasil["asset"]["denah_titik"] == [116.8, -1.5]
        jejak = await db.riwayat_lokasi_aset.find_one({"asset_id": "a1"})
        assert jejak and jejak["oleh"] == "uji"
        shared_utils.invalidate_asset_cache.assert_called_once()
        meili_utils.jadwalkan_sync.assert_called_once()
        websocket.notify_asset_change.assert_awaited_once()
    asyncio.run(jalan())


def test_cabut_tidak_menghapus_koordinat_atau_nama_lokasi(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        hasil = await simpan(hapus=True)
        a = await db.assets.find_one({"id": "a1"})
        assert "lokasi_spasial" not in a
        assert a["version"] == 4
        assert a["location"] == "Ruang Lama"
        assert a["geo"]["coordinates"] == [116.7, -1.4]
        assert hasil["asset"]["di_denah"] is False
        assert hasil["asset"]["denah_titik"] is None
    asyncio.run(jalan())


def test_titik_tanpa_node_memperbarui_koordinat_tanpa_menghapus_label(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        hasil = await simpan(node_id="")
        assert hasil["asset"]["location"] == "Ruang Lama"
        assert hasil["asset"]["di_denah"] is False
        assert (await db.assets.find_one({"id": "a1"}))["geo"]["coordinates"] == [116.8, -1.5]
    asyncio.run(jalan())


@pytest.mark.parametrize("version,key,status", [(None,"k",428),("3",None,428),
    ("rusak","k",400),("0","k",400),("3","k"*201,400),("2","k",409)])
def test_header_tidak_sah_atau_versi_usang_tanpa_tulisan(monkeypatch, version, key, status):
    async def jalan():
        db = await siapkan(monkeypatch)
        with pytest.raises(HTTPException) as e:
            await simpan(request(version, key))
        assert e.value.status_code == status
        assert (await db.assets.find_one({"id": "a1"}))["version"] == 3
        assert await db.riwayat_lokasi_aset.count_documents({}) == 0
    asyncio.run(jalan())


@pytest.mark.parametrize("target,status", [("aset",403),("node",404),("disahkan",423)])
def test_guard_satker_dan_pengesahan(monkeypatch, target, status):
    async def jalan():
        db = await siapkan(monkeypatch)
        if target == "aset":
            await db.inventory_activities.update_one({"id":"k1"},{"$set":{"kode_satker":"B"}})
        elif target == "node":
            await db.spasial_node.update_one({"id":"baru"},{"$set":{"kode_satker":"B"}})
        else:
            await db.inventory_activities.update_one({"id":"k1"},{"$set":{"status_pengesahan":"disahkan"}})
        with pytest.raises(HTTPException) as e:
            await simpan()
        assert e.value.status_code == status
        assert (await db.assets.find_one({"id":"a1"}))["version"] == 3
    asyncio.run(jalan())


def test_replay_tidak_menggandakan_riwayat_dan_key_beda_isi_ditolak(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        pertama = await simpan()
        assert await simpan() == pertama
        assert await db.riwayat_lokasi_aset.count_documents({}) == 1
        with pytest.raises(HTTPException) as e:
            await simpan(lat=-1.6)
        assert e.value.status_code == 409
        assert (await db.assets.find_one({"id":"a1"}))["version"] == 4
    asyncio.run(jalan())


def test_cas_kalah_tidak_mencatat_perpindahan_palsu(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        tulis = db.assets.update_one
        async def berlomba(query, update):
            await tulis({"id":"a1"},{"$inc":{"version":1}, "$set":{"notes":"Edit orang lain"}})
            return await tulis(query, update)
        monkeypatch.setattr(spasial, "db", SimpleNamespace(
            assets=SimpleNamespace(find_one=db.assets.find_one, update_one=berlomba),
            spasial_node=db.spasial_node, riwayat_lokasi_aset=db.riwayat_lokasi_aset))
        with pytest.raises(HTTPException) as e:
            await simpan()
        assert e.value.status_code == 409
        a = await db.assets.find_one({"id":"a1"})
        assert a["location"] == "Ruang Lama" and a["notes"] == "Edit orang lain"
        assert await db.riwayat_lokasi_aset.count_documents({}) == 0
    asyncio.run(jalan())


def test_aset_lama_tanpa_version_dibackfill_ke_dua(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        await db.assets.update_one({"id":"a1"},{"$unset":{"version":""}})
        hasil = await simpan(request("1"))
        assert hasil["asset"]["version"] == 2
        assert (await db.assets.find_one({"id":"a1"}))["version"] == 2
    asyncio.run(jalan())


@pytest.mark.parametrize("isi", [{"lat": 91}, {"lon": 181}, {"lat": "rusak"}, {"lat": None}])
def test_koordinat_tidak_valid_tidak_mengubah_induk(monkeypatch, isi):
    async def jalan():
        db = await siapkan(monkeypatch)
        with pytest.raises(HTTPException) as e:
            await simpan(**isi)
        assert e.value.status_code == 400
        assert (await db.assets.find_one({"id":"a1"}))["version"] == 3
    asyncio.run(jalan())


def test_cache_idempotensi_tidak_tersedia_tetap_tidak_menulis_dua_kali(monkeypatch):
    async def jalan():
        db = await siapkan(monkeypatch)
        monkeypatch.setattr(shared_utils, "get_idempotent_response", AsyncMock(return_value=None))
        await simpan()
        with pytest.raises(HTTPException) as e:
            await simpan()
        assert e.value.status_code == 409
        assert await db.riwayat_lokasi_aset.count_documents({}) == 1
        assert (await db.assets.find_one({"id":"a1"}))["version"] == 4
    asyncio.run(jalan())
