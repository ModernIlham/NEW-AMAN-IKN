"""Lampiran form mengikuti dokumen terapan; scan lama tidak menjadi fallback."""
import asyncio
import io
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.responses import Response
from starlette.requests import Request
from mongomock_motor import AsyncMongoMockClient

import lampiran_bast_aset as lb
import routes.assets as ra
import routes.ttd as rt
from models import AssetResponse, AssetCreate

USER = {"id": "operator", "username": "operator", "role": "operator", "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


def req():
    return Request({"type": "http", "headers": [(b"if-none-match", b'"bast-scan-lama"')]})


@pytest.fixture
def env(monkeypatch):
    database = AsyncMongoMockClient()["lampiran"]
    state = SimpleNamespace(db=database, jenis="esign", sah=True, race=None)
    monkeypatch.setattr(ra, "db", database)
    monkeypatch.setattr(ra, "pastikan_akses_aset", AsyncMock())
    monkeypatch.setattr(ra, "ensure_activity_not_sealed", AsyncMock())
    state.read = AsyncMock(return_value=b"scan-terkini")
    state.delete = AsyncMock()
    monkeypatch.setattr(ra, "get_document_from_gridfs", state.read)
    monkeypatch.setattr(ra, "delete_document_from_gridfs", state.delete)

    async def evaluate(db, bast):
        return {"sah": state.sah and not bast.get("direvisi_oleh"), "jenis": state.jenis,
                "file_id": "scan-baru" if state.jenis == "basah" else "pdf-sumber",
                "kunci_bukti": "hash-final"}
    monkeypatch.setattr(lb, "evaluasi_bast_sah", evaluate)

    async def render(sr_id, user):
        assert sr_id == "sr-baru" and user == USER
        if state.race:
            await state.race()
        return Response(b"pdf-dengan-ttd-dan-qr", media_type="application/pdf",
                        headers={"X-Document-Status": "final", "Content-Disposition": 'inline; filename="final.pdf"'})
    state.render = AsyncMock(side_effect=render)
    monkeypatch.setattr(rt, "dokumen_ber_ttd", state.render)
    return state


async def seed(env, managed=True):
    asset = {"id": "a1", "activity_id": "act", "asset_code": "301", "asset_name": "Barang", "category": "Uji",
             "bast_file_id": "scan-lama", "bast_filename": "lama.pdf", "version": 3,
             "created_at": "2026-10-03T00:00:00+00:00"}
    if managed:
        asset.update(amanah_bast={"bast_id": "baru", "aksi": "serah", "kunci_bukti": "hash-final"},
                     bast_terakhir={"id": "baru", "nomor": "BAST-REVISI"})
    await env.db.assets.insert_one(deepcopy(asset))
    await env.db.inventory_activities.insert_one({"id": "act", "kode_satker": "001"})
    await env.db.bast_serah_terima.insert_many([
        {"id": "baru", "kode_satker": "001", "asset_ids": ["a1"], "signature_request_id": "sr-baru",
         "portal_otomasi": {"items": [{"asset_id": "a1", "aksi": "serah"}]},
         "bukti": {"filename": "bukti-baru.png", "content_type": "image/png"}},
        {"id": "draf-lebih-baru", "kode_satker": "001", "asset_ids": ["a1"], "revisi_dari": "baru"},
    ])
    return asset


def test_revisi_elektronik_mengalahkan_scan_lama_dan_cache_tanpa_migrasi(env):
    async def scenario():
        await seed(env)
        before = await env.db.assets.find_one({"id": "a1"})
        response = await ra.get_asset_bast("a1", req(), _user=USER)
        assert response.body == b"pdf-dengan-ttd-dan-qr"
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Content-Disposition"].startswith("inline")
        assert response.status_code == 200
        env.render.assert_awaited_once()
        env.read.assert_not_awaited()  # bukan scan lama atau PDF sumber tanpa bubuhan
        assert await env.db.assets.find_one({"id": "a1"}) == before
        env.delete.assert_not_awaited()
    run(scenario())


@pytest.mark.parametrize("aksi", ["serah", "kembali", "cabut"])
def test_bukti_basah_mengikuti_bast_terapan_bukan_nama_file_lama(env, aksi):
    async def scenario():
        await seed(env)
        env.jenis = "basah"
        await env.db.assets.update_one({"id": "a1"}, {"$set": {"amanah_bast.aksi": aksi}})
        await env.db.bast_serah_terima.update_one({"id": "baru"}, {"$set": {"portal_otomasi.items.0.aksi": aksi}})
        response = await ra.get_asset_bast("a1", req(), _user=USER)
        assert response.body == b"scan-terkini" and response.media_type == "image/png"
        assert "bukti-baru.png" in response.headers["Content-Disposition"]
        env.read.assert_awaited_once_with("scan-baru")
        env.render.assert_not_awaited()
    run(scenario())


@pytest.mark.parametrize("perubahan", ["dicabut", "lintas_satker", "pointer_beda", "hash_beda", "tanpa_barang", "hilang", "tanpa_id"])
def test_sumber_tidak_sah_tidak_fallback_arsip_lama(env, perubahan):
    async def scenario():
        await seed(env)
        if perubahan == "dicabut": env.sah = False
        elif perubahan == "lintas_satker":
            await env.db.bast_serah_terima.update_one({"id": "baru"}, {"$set": {"kode_satker": "999"}})
        elif perubahan == "pointer_beda":
            await env.db.assets.update_one({"id": "a1"}, {"$set": {"bast_terakhir.id": "lain"}})
        elif perubahan == "hash_beda":
            await env.db.assets.update_one({"id": "a1"}, {"$set": {"amanah_bast.kunci_bukti": "usang"}})
        elif perubahan == "tanpa_barang":
            await env.db.bast_serah_terima.update_one({"id": "baru"}, {"$set": {"asset_ids": []}})
        elif perubahan == "hilang": await env.db.bast_serah_terima.delete_one({"id": "baru"})
        elif perubahan == "tanpa_id": await env.db.assets.update_one({"id": "a1"}, {"$unset": {"amanah_bast.bast_id": ""}})
        with pytest.raises(HTTPException) as e:
            await ra.get_asset_bast("a1", req(), _user=USER)
        assert e.value.status_code == 409
        env.read.assert_not_awaited()
        env.render.assert_not_awaited()
    run(scenario())


@pytest.mark.parametrize("race", ["pointer", "sumber", "kegiatan"])
def test_revisi_atau_pencabutan_selama_render_tidak_menyajikan_pdf_usang(env, race):
    async def scenario():
        await seed(env)
        async def change():
            if race == "pointer":
                await env.db.assets.update_one({"id": "a1"}, {"$set": {"amanah_bast.bast_id": "berikutnya"}})
            elif race == "kegiatan":
                await env.db.assets.update_one({"id": "a1"}, {"$set": {"activity_id": "kegiatan-satker-lain"}})
            else:
                env.sah = False
        env.race = change
        with pytest.raises(HTTPException) as e:
            await ra.get_asset_bast("a1", req(), _user=USER)
        assert e.value.status_code == 409
        env.read.assert_not_awaited()
    run(scenario())


def test_unggahan_manual_legacy_masih_dapat_dibuka(env):
    async def scenario():
        await seed(env, managed=False)
        response = await ra.get_asset_bast("a1", Request({"type": "http", "headers": []}), _user=USER)
        assert response.headers["Cache-Control"] == "private, no-cache"
        env.read.assert_awaited_once_with("scan-lama")
        env.render.assert_not_awaited()
    run(scenario())


def test_unggahan_manual_tidak_mengganti_bukti_terapan(env):
    async def scenario():
        await seed(env)
        before = await env.db.assets.find_one({"id": "a1"})
        with pytest.raises(HTTPException) as e:
            await ra.upload_asset_bast("a1", req(), UploadFile(filename="baru.pdf", file=io.BytesIO(b"%PDF-test")), USER)
        assert e.value.status_code == 409
        assert await env.db.assets.find_one({"id": "a1"}) == before
        env.delete.assert_not_awaited()
    run(scenario())


def test_hak_akses_aset_diperiksa_sebelum_membaca_lampiran(env, monkeypatch):
    async def scenario():
        await seed(env)
        monkeypatch.setattr(ra, "pastikan_akses_aset", AsyncMock(side_effect=HTTPException(403, "Satker berbeda")))
        with pytest.raises(HTTPException) as e:
            await ra.get_asset_bast("a1", req(), _user=USER)
        assert e.value.status_code == 403
        env.read.assert_not_awaited()
        env.render.assert_not_awaited()
    run(scenario())


def test_referensi_bast_dibawa_response_dan_proyeksi_bukan_input(env):
    asset = run(seed(env))
    response = AssetResponse(**asset).model_dump()
    for field in ("amanah_bast", "bast_terakhir"):
        assert response[field] == asset[field]
        assert ra.LIST_PROJECTION[field] == 1
        assert field not in AssetCreate.model_fields


def test_get_detail_tetap_membawa_referensi_dengan_file_lama(env, monkeypatch):
    async def scenario():
        asset = await seed(env)
        monkeypatch.setattr(ra, "lengkapi_psp", AsyncMock())
        response = await ra.get_asset("a1", exclude_media=False, _user=USER)
        assert response.amanah_bast == asset["amanah_bast"]
        assert response.bast_terakhir == asset["bast_terakhir"]
    run(scenario())


def test_penerapan_selama_unggah_manual_tidak_ditimpa(env, monkeypatch):
    import gerbang_media
    async def scenario():
        await seed(env, managed=False)
        async def store(*args, **kwargs):
            await env.db.assets.update_one({"id": "a1"}, {"$set": {
                "amanah_bast": {"bast_id": "baru", "kunci_bukti": "hash-final"}, "bast_file_id": "scan-sah"}})
            return "unggahan-kalah", {"filename": "baru.pdf"}
        monkeypatch.setattr(gerbang_media, "tulis_media", store)
        with pytest.raises(HTTPException) as e:
            await ra.upload_asset_bast("a1", req(), UploadFile(filename="baru.pdf", file=io.BytesIO(b"%PDF-test")), USER)
        assert e.value.status_code == 409
        asset = await env.db.assets.find_one({"id": "a1"})
        assert asset["amanah_bast"]["bast_id"] == "baru"
        assert asset["bast_file_id"] == "scan-sah"
        env.delete.assert_awaited_once_with("unggahan-kalah")
    run(scenario())


def test_bukti_basah_hilang_tidak_memakai_file_legacy(env):
    async def scenario():
        await seed(env)
        env.jenis = "basah"
        env.read.return_value = None
        with pytest.raises(HTTPException) as e:
            await ra.get_asset_bast("a1", req(), _user=USER)
        assert e.value.status_code == 404
        env.read.assert_awaited_once_with("scan-baru")
    run(scenario())


def test_endpoint_tetap_menolak_akses_tanpa_autentikasi():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(ra.assets_router)
    with TestClient(app) as client:
        assert client.get("/assets/a1/bast").status_code == 401
