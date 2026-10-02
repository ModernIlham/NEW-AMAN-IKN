"""Kontrak route BAST: draf tanpa proyeksi; arsip basah dengan OCC/replay."""
import asyncio
import copy
import hashlib
import io
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import routes.bast as rb


USER = {"id": "u1", "username": "operator@example.test", "role": "operator",
        "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


def req(version=1, key="test-1"):
    headers = []
    if version is not None:
        headers.append((b"if-match", str(version).encode()))
    if key:
        headers.append((b"idempotency-key", key.encode()))
    return Request({"type": "http", "headers": headers})


@pytest.fixture
def env(monkeypatch):
    db = AsyncMongoMockClient()["uji_bast_otomasi"]
    state = SimpleNamespace(db=db, blobs={}, deleted=[], calls=[], plans=[], before_store=None)
    import shared_utils as su
    import routes.persuratan as rp

    async def diam(*a, **k):
        return None

    for mod in (rb, su, rp):
        monkeypatch.setattr(mod, "db", db)
        monkeypatch.setattr(mod, "log_audit", diam)

    async def plan(database, bast, assets):
        state.plans.append(copy.deepcopy(assets))
        return {"version": 1, "status": "menunggu_bukti", "items": []}

    async def sync(database, bast_id, oleh="sistem"):
        state.calls.append((bast_id, oleh))
        b = await db.bast_serah_terima.find_one({"id": bast_id})
        return {**b["portal_otomasi"], "status": "menunggu_penyelarasan"}

    async def store(data, **kw):
        fid = f"blob-{len(state.blobs) + 1}"
        state.blobs[fid] = b"bytes-tersimpan:" + data
        if state.before_store:
            await state.before_store()
        return fid, {}

    async def read(fid):
        return state.blobs.get(fid)

    async def delete(fid):
        state.deleted.append(fid)
        state.blobs.pop(fid, None)

    monkeypatch.setitem(sys.modules, "portal_bast", SimpleNamespace(
        siapkan_otomasi_bast=plan, sinkronkan_bast=sync))
    monkeypatch.setitem(sys.modules, "portal_bast_validitas", SimpleNamespace(
        sidik_isi_bast=lambda b: "sidik-isi-dokumen"))
    monkeypatch.setitem(sys.modules, "gerbang_media", SimpleNamespace(tulis_media=store))
    monkeypatch.setattr(su, "get_document_from_gridfs", read)
    monkeypatch.setattr(su, "delete_document_from_gridfs", delete)
    return state


async def seed(env, **changes):
    bast = {"id": "b1", "kode_satker": "001", "nomor": "BAST-1",
            "jenis": "penggunaan_melekat", "asset_ids": ["a1"],
            "portal_otomasi": {"version": 1, "status": "menunggu_bukti", "items": []}}
    bast.update(changes)
    await env.db.bast_serah_terima.insert_one(bast)
    await env.db.assets.insert_one({"id": "a1", "user": "Pemegang Lama", "version": 3})
    return bast


async def upload(env, *, version=1, key="test-1", verified=False, data=b"scan", user=USER):
    return await rb.unggah_bukti_bast(
        "b1", UploadFile(file=io.BytesIO(data), filename="scan.pdf"),
        verifikasi_lengkap=verified, request=req(version, key), user=user)


@pytest.mark.parametrize("jenis", ["mutasi_pengguna", "pengembalian"])
def test_create_hanya_membekukan_rencana_tanpa_mengubah_master(env, jenis):
    async def scenario():
        await env.db.inventory_activities.insert_one({"id": "act", "kode_satker": "001"})
        asset = {"id": "a1", "asset_code": "3100102001", "NUP": "01", "asset_name": "Laptop",
                 "activity_id": "act", "kode_register": "REG-1", "version": 3,
                 "user": "Lama", "pengguna_nip": "111", "pengguna_jabatan": "Staf",
                 "pengguna_melekat_ke": "Individu", "bast_terakhir": {"id": "lama"},
                 "amanah_bast": {"bast_id": "lama"}}
        await env.db.assets.insert_one(copy.deepcopy(asset))
        before = await env.db.assets.find_one({"id": "a1"})
        result = await rb.buat_bast(rb.BastIn(
            jenis=jenis, asset_ids=["a1"], terapkan_ke_aset=True,
            pihak_pertama=rb.PihakIn(nama="Lama", pegawai_id="pg-lama"),
            pihak_kedua=rb.PihakIn(nama="Baru", pegawai_id="pg-baru")), user=USER)
        assert await env.db.assets.find_one({"id": "a1"}) == before
        assert result["pihak_pertama"]["pegawai_id"] == "pg-lama"
        assert result["pihak_kedua"]["pegawai_id"] == "pg-baru"
        assert result["portal_otomasi"]["version"] == 1
        for field in asset:
            assert env.plans[0][0][field] == asset[field]
    run(scenario())


def test_revisi_tidak_boleh_menghilangkan_sebagian_aset(env):
    async def scenario():
        await seed(env, asset_ids=["a1", "a2"])
        with pytest.raises(HTTPException) as err:
            await rb.buat_bast(rb.BastIn(
                jenis="penggunaan_melekat", asset_ids=["a1"],
                pihak_kedua=rb.PihakIn(nama="Baru"), revisi_dari="b1",
                revisi_alasan="Perbaikan isi"), user=USER)
        assert err.value.status_code == 409
        assert "seluruh barang" in err.value.detail
        assert await env.db.bast_serah_terima.count_documents({}) == 1
    run(scenario())


def test_bukti_tanpa_attest_tidak_menyinkronkan_dan_tanpa_proyeksi(env):
    async def scenario():
        await seed(env)
        result = await upload(env)
        b = await env.db.bast_serah_terima.find_one({"id": "b1"})
        assert b["bukti"]["verifikasi_lengkap"] is False
        assert "diverifikasi_pada" not in b["bukti"]
        assert b["portal_otomasi"]["version"] == 2
        assert result["portal_otomasi"]["version"] == 2
        assert env.calls == []
        assert (await env.db.assets.find_one({"id": "a1"}))["version"] == 3
        assert await env.db.surat.count_documents({}) == 0
    run(scenario())


def test_attest_hash_bytes_tersimpan_arsip_dan_replay(env):
    async def scenario():
        await seed(env, bukti={"file_id": "lama", "filename": "lama.pdf"})
        env.blobs["lama"] = b"arsip"
        await upload(env, verified=True)
        b = await env.db.bast_serah_terima.find_one({"id": "b1"})
        proof = b["bukti"]
        assert proof["verifikasi_lengkap"] is True
        assert proof["bast_sidik"] == "sidik-isi-dokumen"
        assert proof["diverifikasi_oleh"] == USER["username"]
        assert proof["sha256"] == hashlib.sha256(env.blobs[proof["file_id"]]).hexdigest()
        assert b["bukti_riwayat"][0]["file_id"] == "lama"
        assert env.deleted == [] and len(env.calls) == 1
        await upload(env, verified=True)  # versi awal boleh diputar ulang
        assert len(env.blobs) == 2
        assert len(env.calls) == 1, "replay hasil tidak memfinalisasi ulang"
        with pytest.raises(HTTPException) as err:
            await upload(env, verified=True, data=b"berbeda")
        assert err.value.status_code == 409
        assert (await env.db.bast_serah_terima.find_one({"id": "b1"}))["bukti"] == proof
    run(scenario())


@pytest.mark.parametrize("version,key,status", [(None, "k", 428), (1, "", 428), (2, "k", 409)])
def test_bukti_memerlukan_header_dan_versi(env, version, key, status):
    async def scenario():
        await seed(env)
        with pytest.raises(HTTPException) as err:
            await upload(env, version=version, key=key)
        assert err.value.status_code == status
        assert not env.blobs
    run(scenario())


def test_bukti_yang_pernah_diterapkan_tidak_dapat_diganti(env):
    async def scenario():
        await seed(env, portal_otomasi={"version": 1, "ever_applied": True})
        with pytest.raises(HTTPException) as err:
            await upload(env, verified=True)
        assert err.value.status_code == 409
        assert "revisi resmi" in err.value.detail
        assert not env.blobs
    run(scenario())


def test_bukti_verified_tetap_terkunci_meski_flag_penerapan_belum_tersimpan(env):
    async def scenario():
        await seed(env, bukti={"file_id": "asli", "verifikasi_lengkap": True})
        with pytest.raises(HTTPException) as err:
            await upload(env, verified=True)
        assert err.value.status_code == 409
        assert not env.blobs
    run(scenario())


@pytest.mark.parametrize("awal,akhir", [("2026-10-04", "2026-10-03"),
                                        ("2026-02-30", "2026-03-01")])
def test_jangka_sementara_valid_dan_berurutan(env, awal, akhir):
    async def scenario():
        with pytest.raises(HTTPException) as err:
            await rb.buat_bast(rb.BastIn(jenis="penggunaan_sementara", asset_ids=["a1"],
                pihak_kedua=rb.PihakIn(nama="Penerima"), jangka_dari=awal, jangka_sampai=akhir),
                user=USER)
        assert err.value.status_code == 400
        assert await env.db.bast_serah_terima.count_documents({}) == 0
    run(scenario())


def test_finalisasi_di_tengah_upload_mengalahkan_bukti_basi(env):
    async def scenario():
        await seed(env, bukti={"file_id": "lama"})
        async def race():
            await env.db.bast_serah_terima.update_one({"id": "b1"}, {
                "$set": {"portal_otomasi.ever_applied": True},
                "$inc": {"portal_otomasi.version": 1}})
        env.before_store = race
        with pytest.raises(HTTPException) as err:
            await upload(env, verified=True)
        assert err.value.status_code == 409
        assert (await env.db.bast_serah_terima.find_one({"id": "b1"}))["bukti"]["file_id"] == "lama"
        assert len(env.deleted) == 1 and not env.calls
    run(scenario())


def test_bukti_ditolak_selama_lease_finalisasi_aktif(env):
    async def scenario():
        await seed(env, portal_otomasi={"version": 1, "lease": {
            "id": "worker", "expires_at": datetime.now(timezone.utc) + timedelta(minutes=1)}})
        with pytest.raises(HTTPException) as err:
            await upload(env, verified=True)
        assert err.value.status_code == 409
        assert not env.blobs
    run(scenario())


def test_scope_dan_retry_sinkronisasi(env):
    async def scenario():
        await seed(env)
        with pytest.raises(HTTPException) as err:
            await rb.sinkronkan_bmn_bast("b1", req(), user={**USER, "kode_satker": "999"})
        assert err.value.status_code == 403
        one = await rb.sinkronkan_bmn_bast("b1", req(), user=USER)
        assert await rb.sinkronkan_bmn_bast("b1", req(), user=USER) == one
        assert len(env.calls) == 1
        with pytest.raises(HTTPException) as err:
            await rb.sinkronkan_bmn_bast("b1", req(2), user=USER)
        assert err.value.status_code == 409
    run(scenario())


def test_create_upload_dengan_layanan_asli_mengaktifkan_satu_amanah(monkeypatch):
    """Route + resolver + proyeksi asli; hanya DB/media sintetis."""
    import gerbang_media
    import portal_bast
    import shared_utils as su
    import routes.persuratan as rp
    db = AsyncMongoMockClient()["bast_terpadu"]
    blobs = {}

    async def diam(*a, **k):
        return None

    async def store(data, **kwargs):
        fid = f"file-{len(blobs) + 1}"
        blobs[fid] = data
        return fid, {}

    async def read(fid):
        return blobs.get(fid)

    for mod in (rb, su, rp):
        monkeypatch.setattr(mod, "db", db)
        monkeypatch.setattr(mod, "log_audit", diam)
    monkeypatch.setattr(gerbang_media, "tulis_media", store)
    monkeypatch.setattr(su, "get_document_from_gridfs", read)
    monkeypatch.setattr(portal_bast, "_segarkan_aset", diam, raising=False)

    async def scenario():
        await db.inventory_activities.insert_one({"id": "act", "kode_satker": "001"})
        await db.assets.insert_one({"id": "a1", "activity_id": "act", "version": 2,
                                   "asset_code": "3100102001", "NUP": "1", "asset_name": "Laptop",
                                   "user": "Lama", "pengguna_nip": "100", "condition": "Baik"})
        await db.pegawai.insert_one({"id": "pg1", "kode_satker": "001", "nama": "Penerima",
                                    "nip": "200", "email": "penerima@example.test", "status": "aktif",
                                    "status_kepegawaian": "PNS"})
        result = await rb.buat_bast(rb.BastIn(
            jenis="penggunaan_melekat", asset_ids=["a1"], nomor="BAST-TERPADU",
            pihak_pertama=rb.PihakIn(nama="Pejabat"),
            pihak_kedua=rb.PihakIn(nama="Penerima", nip="200", pegawai_id="pg1")), user=USER)
        assert await db.portal_penugasan.count_documents({}) == 0
        assert (await db.assets.find_one({"id": "a1"}))["user"] == "Lama"
        output = await rb.unggah_bukti_bast(result["id"],
            UploadFile(file=io.BytesIO(b"%PDF-scan-sintetis"), filename="scan.pdf"),
            verifikasi_lengkap=True, request=req(1, "proof-terpadu"), user=USER)
        assert output["portal_otomasi"]["status"] == "selesai"
        assert (await db.assets.find_one({"id": "a1"}))["pengguna_nip"] == "200"
        assignment = await db.portal_penugasan.find_one({"pegawai_id": "pg1"})
        assert assignment["status"] == "diterima"
        assert assignment["penerimaan_otomatis"] is True
        assert assignment["sumber_bast"]["id"] == result["id"]
        assert await db.portal_penugasan.count_documents({}) == 1
        assert (await db.bast_serah_terima.find_one({"id": result["id"]}))["portal_otomasi"]["ever_applied"]
    run(scenario())
