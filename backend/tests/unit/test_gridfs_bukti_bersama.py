"""Mengganti lampiran aset tidak boleh menghancurkan bukti dokumen sumber."""
import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bson import ObjectId
from mongomock_motor import AsyncMongoMockClient
import pytest

import indexes
import shared_utils as su


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def env(monkeypatch):
    db = AsyncMongoMockClient()["bukti_bersama"]
    bucket = SimpleNamespace(delete=AsyncMock())
    monkeypatch.setattr(su, "db", db)
    monkeypatch.setattr(su, "fs_bucket", bucket)
    return db, bucket, ObjectId()


@pytest.mark.parametrize("rujukan", ["bukti", "bukti_riwayat", "dok_file_id"])
@pytest.mark.parametrize("bson_id", [False, True])
def test_bukti_aktif_arsip_dan_pdf_ttd_dipertahankan(env, rujukan, bson_id):
    db, bucket, fid = env

    async def scenario():
        value = fid if bson_id else str(fid)
        if rujukan == "dok_file_id":
            # Batal tidak berarti arsip bukti boleh dihancurkan.
            await db.signature_requests.insert_one({"id": "sr1", "status": "batal", "dok_file_id": value})
        else:
            doc = {"id": "b1", "kode_satker": "satker-lain", "direvisi_oleh": "b2"}
            doc[rujukan] = [{"file_id": value}] if rujukan == "bukti_riwayat" else {"file_id": value}
            await db.bast_serah_terima.insert_one(doc)
        assert await su.delete_document_from_gridfs(str(fid)) is False
        bucket.delete.assert_not_awaited()
    run(scenario())


def test_lampiran_yang_tidak_dirujuk_tetap_dibersihkan(env):
    db, bucket, fid = env

    async def scenario():
        # Dokumen lain tidak menahan blob ini; yang diuji adalah id persis.
        await db.bast_serah_terima.insert_one({"id": "b1", "bukti": {"file_id": str(ObjectId())}})
        assert await su.delete_document_from_gridfs(str(fid)) is True
        bucket.delete.assert_awaited_once_with(fid)
    run(scenario())


@pytest.mark.parametrize("gagal_pada", ["bast_serah_terima", "signature_requests"])
@pytest.mark.parametrize("error", [RuntimeError("DB tidak tersedia"), asyncio.TimeoutError()])
def test_kegagalan_lookup_tidak_pernah_diterjemahkan_sebagai_tidak_dirujuk(env, monkeypatch, caplog, gagal_pada, error):
    _, bucket, fid = env
    db = SimpleNamespace(bast_serah_terima=SimpleNamespace(find_one=AsyncMock(return_value=None)),
                         signature_requests=SimpleNamespace(find_one=AsyncMock(return_value=None)))
    getattr(db, gagal_pada).find_one.side_effect = error
    monkeypatch.setattr(su, "db", db)
    assert run(su.delete_document_from_gridfs(str(fid))) is False
    bucket.delete.assert_not_awaited()
    assert "referensi bukti tidak dapat diperiksa" in caplog.text
    for coll in (db.bast_serah_terima, db.signature_requests):
        for call in coll.find_one.await_args_list:
            assert call.args[1] == {"_id": 1}
            assert call.kwargs["max_time_ms"] == 2000


def test_id_rusak_tidak_mengakses_database_atau_bucket(env, monkeypatch):
    _, bucket, _ = env
    db = SimpleNamespace(bast_serah_terima=SimpleNamespace(find_one=AsyncMock()))
    monkeypatch.setattr(su, "db", db)
    assert run(su.delete_document_from_gridfs("bukan-object-id")) is False
    db.bast_serah_terima.find_one.assert_not_awaited()
    bucket.delete.assert_not_awaited()


def test_lookup_bukti_memiliki_indeks_path_yang_sesuai():
    source = inspect.getsource(indexes.create_indexes)
    assert 'await _idx(db.bast_serah_terima, "bukti.file_id", sparse=True)' in source
    assert 'await _idx(db.bast_serah_terima, "bukti_riwayat.file_id", sparse=True)' in source
    assert 'await _idx(db.signature_requests, "dok_file_id", sparse=True)' in source
