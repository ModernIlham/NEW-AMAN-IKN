"""Arsip akhir tidak menimpa dasar, tidak mengulang penerapan, dan byte tetap utuh."""
import asyncio
import hashlib
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import auth_utils
import gerbang_media
import routes.bast_dokumen_akhir as route

USER = {"id": "u1", "username": "operator@example.test", "role": "operator", "kode_satker": "001"}
PDF = b"%PDF-1.7\nDokumen final /ByteRange [0 100 200 50] /Contents <123>\n%%EOF"


def run(coro):
    return asyncio.run(coro)


def req(version=1, key="unggah-1"):
    return Request({"type": "http", "headers": [
        (b"if-match", str(version).encode()), (b"idempotency-key", key.encode())]})


@pytest.fixture
def env(monkeypatch):
    db = AsyncMongoMockClient()["akhir_bast"]
    state = SimpleNamespace(db=db, blobs={}, deleted=[], before_store=None, before_read=None)
    monkeypatch.setattr(route, "db", db)
    monkeypatch.setattr(route, "log_audit", AsyncMock())

    async def store(data, **kwargs):
        assert kwargs["kelas"] == "mentah", "Dokumen tidak boleh dikompresi ulang"
        assert kwargs["metadata"]["sha256"] == hashlib.sha256(data).hexdigest()
        fid = f"blob-{len(state.blobs) + 1}"
        state.blobs[fid] = data
        if state.before_store:
            await state.before_store()
        return fid, {}

    async def read(fid):
        if state.before_read:
            await state.before_read()
        return state.blobs.get(fid)

    async def delete(fid):
        state.deleted.append(fid)
        state.blobs.pop(fid, None)

    monkeypatch.setattr(gerbang_media, "tulis_media", store)
    monkeypatch.setattr(route, "get_document_from_gridfs", read)
    monkeypatch.setattr(route, "delete_document_from_gridfs", delete)
    run(db.bast_serah_terima.insert_one({"id": "b1", "kode_satker": "001", "nomor": "BAST-1",
        "signature_request_id": "sr1", "bukti": {"file_id": "asli", "verifikasi_lengkap": True},
        "portal_otomasi": {"version": 4, "ever_applied": True, "status": "selesai"}}))
    run(db.assets.insert_one({"id": "a1", "bast_file_id": "asli", "version": 8}))
    run(db.signature_requests.insert_one({"id": "sr1", "status": "selesai", "dok_file_id": "ttd-asli"}))
    return state


async def upload(*, version=1, key="unggah-1", data=PDF, filename="final.pdf", user=USER, jenis="e_meterai", catatan="Dokumen setelah e-meterai"):
    return await route.unggah_dokumen_akhir("b1", req(version, key),
        UploadFile(file=io.BytesIO(data), filename=filename), jenis, catatan, user)


async def check(doc_id, *, version=2, key="periksa-1", status="sesuai", catatan="Isi dan kelengkapan sesuai", user=USER):
    return await route.periksa_dokumen_akhir("b1", doc_id,
        route.PemeriksaanAkhir(status=status, sudah_diperiksa=True, catatan=catatan), req(version, key), user)


def test_unggah_replay_pemeriksaan_preview_tanpa_mengubah_dasar(env):
    async def scenario():
        before = await env.db.bast_serah_terima.find_one({"id": "b1"})
        asset = await env.db.assets.find_one({"id": "a1"})
        sr = await env.db.signature_requests.find_one({"id": "sr1"})
        result = await upload()
        assert await upload() == result
        assert len(env.blobs) == 1
        b = await env.db.bast_serah_terima.find_one({"id": "b1"})
        doc = b["dokumen_akhir"][0]
        assert doc["status"] == "menunggu" and doc["sha256"] == hashlib.sha256(PDF).hexdigest()
        assert env.blobs[doc["file_id"]] == PDF
        verified = await check(doc["id"])
        assert await check(doc["id"]) == verified
        b = await env.db.bast_serah_terima.find_one({"id": "b1"})
        assert b["dokumen_akhir_version"] == 3
        assert b["dokumen_akhir"][0]["pemeriksaan"]["oleh"] == USER["username"]
        assert {k: b[k] for k in before} == before
        assert await env.db.assets.find_one({"id": "a1"}) == asset
        assert await env.db.signature_requests.find_one({"id": "sr1"}) == sr
        assert await env.db.portal_penugasan.count_documents({}) == 0
        response = await route.lihat_dokumen_akhir("b1", doc["id"], USER)
        assert response.headers["content-disposition"].startswith("inline;")
        assert response.headers["cache-control"] == "private, no-store"
        assert b"".join([chunk async for chunk in response.body_iterator]) == PDF
        with pytest.raises(HTTPException) as err:
            await check(doc["id"], version=3, key="baru")
        assert err.value.status_code == 409
    run(scenario())


@pytest.mark.parametrize("change", [{"data": PDF + b" "}, {"catatan": "Catatan baru"}, {"jenis": "scan_manual"}, {"version": 2}])
def test_idempotensi_tidak_membenarkan_payload_berbeda(env, change):
    async def scenario():
        await upload()
        with pytest.raises(HTTPException) as err:
            await upload(**change)
        assert err.value.status_code == 409
        assert len(env.blobs) == 1
    run(scenario())


@pytest.mark.parametrize("version,key,status", [(0, "a", 428), (1, "", 428), (2, "a", 409)])
def test_header_versi_wajib_sebelum_menyimpan(env, version, key, status):
    async def scenario():
        with pytest.raises(HTTPException) as err:
            await upload(version=version, key=key)
        assert err.value.status_code == status and not env.blobs
    run(scenario())


@pytest.mark.parametrize("patch", [{"direvisi_oleh": "baru"}, {"tt_dicabut": True}])
def test_bast_lama_hanya_boleh_dilihat(env, patch):
    async def scenario():
        result = await upload()
        await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": patch})
        for coro in (upload(version=2, key="baru", data=PDF + b"b"), check(result["dokumen_id"])):
            with pytest.raises(HTTPException) as err:
                await coro
            assert err.value.status_code == 409
        assert (await route.lihat_dokumen_akhir("b1", result["dokumen_id"], USER)).status_code == 200
    run(scenario())


@pytest.mark.parametrize("data,filename", [(b"", "a.pdf"), (b"<html>asing</html>", "a.pdf"),
    (PDF, "a.jpg"), (PDF, "a.exe"), (b"x" * (10 * 1024 * 1024 + 1), "besar.pdf")],
    ids=["kosong", "html", "salah-mime", "ekstensi", "terlalu-besar"])
def test_batas_dan_magic_sebelum_blob(env, data, filename):
    async def scenario():
        with pytest.raises(HTTPException) as err:
            await upload(data=data, filename=filename)
        assert err.value.status_code == 400 and not env.blobs
    run(scenario())


def test_duplikat_dan_semua_versi_dipertahankan(env):
    async def scenario():
        one = await upload(jenis="scan_manual")
        await check(one["dokumen_id"], status="tidak_sesuai")
        with pytest.raises(HTTPException) as err:
            await upload(version=3, key="lagi")
        assert err.value.status_code == 409
        await upload(version=3, key="perbaikan", data=PDF + b"dokumen-baru")
        docs = (await env.db.bast_serah_terima.find_one({"id": "b1"}))["dokumen_akhir"]
        assert len(docs) == 2 and docs[0]["status"] == "tidak_sesuai"
        assert len(env.blobs) == 2 and not env.deleted
    run(scenario())


def test_izin_lintas_satker_unggah_periksa_dan_baca(env):
    async def scenario():
        result = await upload()
        other = {**USER, "kode_satker": "999"}
        for coro in (upload(user=other), check(result["dokumen_id"], user=other), route.lihat_dokumen_akhir("b1", result["dokumen_id"], other)):
            with pytest.raises(HTTPException) as err:
                await coro
            assert err.value.status_code == 403
        assert len(env.blobs) == 1
    run(scenario())


@pytest.mark.parametrize("patch", [{"direvisi_oleh": "b2"}, {"signature_request_id": "sr-baru"}, {"nomor": "NOMOR-LAIN"}])
def test_perubahan_selama_unggah_mengalahkan_snapshot_dan_bersihkan_blob_kalah(env, patch):
    async def scenario():
        async def race():
            await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": patch})
        env.before_store = race
        with pytest.raises(HTTPException) as err:
            await upload()
        assert err.value.status_code == 409
        assert env.deleted == ["blob-1"] and not env.blobs
    run(scenario())


def test_dokumen_sumber_berubah_tidak_boleh_dinyatakan_sesuai(env):
    async def scenario():
        result = await upload()
        await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"nomor": "BAST-BARU"}})
        with pytest.raises(HTTPException) as err:
            await check(result["dokumen_id"])
        assert err.value.status_code == 409
        await check(result["dokumen_id"], status="tidak_sesuai")
    run(scenario())


def test_integritas_arsip_diperiksa_sebelum_preview_dan_verifikasi(env):
    async def scenario():
        result = await upload()
        env.blobs["blob-1"] = b"berubah"
        for coro in (check(result["dokumen_id"]), route.lihat_dokumen_akhir("b1", result["dokumen_id"], USER)):
            with pytest.raises(HTTPException) as err:
                await coro
            assert err.value.status_code == 409
    run(scenario())


def test_race_pemeriksaan_dengan_revisi(env):
    async def scenario():
        result = await upload()
        async def race():
            await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"direvisi_oleh": "b2"}})
        env.before_read = race
        with pytest.raises(HTTPException) as err:
            await check(result["dokumen_id"])
        assert err.value.status_code == 409
        assert (await env.db.bast_serah_terima.find_one({"id": "b1"}))["dokumen_akhir"][0]["status"] == "menunggu"
    run(scenario())


def test_unggah_serentak_idem_hanya_menghasilkan_satu_arsip(env):
    async def scenario():
        barrier = asyncio.Event()
        async def race():
            if len(env.blobs) == 2:
                barrier.set()
            await barrier.wait()
        env.before_store = race
        one, two = await asyncio.gather(upload(), upload())
        assert one == two
        assert len(env.blobs) == 1 and len(env.deleted) == 1
        assert len((await env.db.bast_serah_terima.find_one({"id": "b1"}))["dokumen_akhir"]) == 1
    run(scenario())


def test_backup_menganggap_semua_arsip_akhir_sebagai_referensi_wajib():
    from backup_archive import _references
    assert list(_references("bast_serah_terima", {"dokumen_akhir": [
        {"file_id": "ditolak", "status": "tidak_sesuai"}, {"file_id": "aktif", "status": "sesuai"}]})) == ["ditolak", "aktif"]


def test_batas_jumlah_arsip_dan_nama_unicode_aman(env):
    async def scenario():
        result = await upload(filename="C:\\fakepath\\Bukti-é\r\nakhir.pdf")
        response = await route.lihat_dokumen_akhir("b1", result["dokumen_id"], USER)
        disposition = response.headers["content-disposition"]
        assert "%C3%A9" in disposition and "fakepath" not in disposition
        assert "\r" not in disposition and "\n" not in disposition
        await env.db.bast_serah_terima.update_one({"id": "b1"}, {"$set": {
            "dokumen_akhir": [{"id": str(i), "file_id": f"arsip-{i}"} for i in range(20)]}})
        with pytest.raises(HTTPException) as err:
            await upload(version=2, key="kelebihan", data=PDF + b"lain")
        assert err.value.status_code == 400 and len(env.blobs) == 1
    run(scenario())


@pytest.mark.parametrize("filename,data,tipe", [("scan.png", b"\x89PNG\r\n\x1a\nscan", "image/png"),
    ("scan.jpeg", b"\xff\xd8\xffscan", "image/jpeg")])
def test_scan_gambar_mentah_dengan_tipe_yang_benar(env, filename, data, tipe):
    async def scenario():
        result = await upload(filename=filename, data=data, jenis="scan_manual")
        response = await route.lihat_dokumen_akhir("b1", result["dokumen_id"], USER)
        assert response.media_type == tipe
        assert b"".join([chunk async for chunk in response.body_iterator]) == data
    run(scenario())


def test_simpanan_beda_byte_ditolak_dan_dibersihkan(env):
    async def scenario():
        async def corrupt():
            env.blobs["blob-1"] = b"berubah saat disimpan"
        env.before_store = corrupt
        with pytest.raises(HTTPException) as err:
            await upload()
        assert err.value.status_code == 503
        assert not env.blobs
        assert not (await env.db.bast_serah_terima.find_one({"id": "b1"})).get("dokumen_akhir")
    run(scenario())


def test_salah_id_dokumen_tidak_membaca_arsip_lain(env):
    async def scenario():
        await upload()
        for coro in (check("bukan-dokumen"), route.lihat_dokumen_akhir("b1", "bukan-dokumen", USER),
                     route.lihat_dokumen_akhir("tidak-ada", "apa-pun", USER)):
            with pytest.raises(HTTPException) as err:
                await coro
            assert err.value.status_code == 404
    run(scenario())


def test_http_otorisasi_dan_kontrak_multipart(env):
    app = FastAPI()
    app.include_router(route.bast_dokumen_akhir_router)
    with TestClient(app) as client:
        assert client.post("/bast/b1/dokumen-akhir").status_code == 401
        app.dependency_overrides[auth_utils.require_user] = lambda: {**USER, "role": "viewer"}
        assert client.post("/bast/b1/dokumen-akhir").status_code == 403
        app.dependency_overrides[auth_utils.require_user] = lambda: USER
        headers = {"If-Match": "1", "Idempotency-Key": "http-1"}
        for jenis in ("jenis-asing",):
            response = client.post("/bast/b1/dokumen-akhir", headers=headers,
                files={"file": ("akhir.pdf", PDF)}, data={"jenis": jenis, "catatan": "Dokumen lengkap"})
            assert response.status_code == 422
        response = client.post("/bast/b1/dokumen-akhir", headers=headers,
            files={"file": ("akhir.pdf", PDF)}, data={"jenis": "e_meterai", "catatan": "Dokumen lengkap"})
        assert response.status_code == 200
        doc_id = response.json()["dokumen_id"]
        response = client.post(f"/bast/b1/dokumen-akhir/{doc_id}/periksa", headers={**headers, "If-Match": "2"},
            json={"status": "sesuai", "sudah_diperiksa": False, "catatan": "Belum diperiksa"})
        assert response.status_code == 422
