"""Bulk deletion preserves receipts, CAS conflicts and media ordering.

Both routes share one deletion helper. Read the media references and reconcile
application proofs before deleting a matching asset; release media afterward.
Audit intent precedes every irreversible deletion and a conflict retains parent.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import shared_utils as su
import routes.exports as rex
import routes.activities as ract
import batch_operations as batch
from fastapi import HTTPException

ADMIN = {"username": "adm", "name": "Admin Satu", "role": "admin", "kode_satker": "527010"}


def _jalan(coro):
    return asyncio.run(coro)


@pytest.fixture()
def lingkungan(monkeypatch):
    """DB palsu + GridFS palsu yang benar-benar bisa dihitung isinya."""
    fake = AsyncMongoMockClient()["uji"]
    # "GridFS": himpunan id yang masih hidup. Menghitungnya = menghitung fs.files.
    blob = {"foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran",
            "blob-kegiatan", "foto-tetangga"}
    jejak = []

    async def _hapus_foto(gid):
        blob.discard(gid)

    async def _hapus_dok(gid):
        blob.discard(gid)

    async def _catat(action, target, *a, **k):
        jejak.append({"action": action, "target": target, "detail": k.get("detail", "")})

    for mod in (su, rex, ract, batch):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "delete_photo_from_gridfs"):
            monkeypatch.setattr(mod, "delete_photo_from_gridfs", _hapus_foto, raising=False)
        if hasattr(mod, "delete_document_from_gridfs"):
            monkeypatch.setattr(mod, "delete_document_from_gridfs", _hapus_dok, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _catat, raising=False)
    monkeypatch.setattr(rex, "invalidate_asset_cache", lambda *a, **k: None, raising=False)

    async def _lolos(*a, **k):
        return None
    monkeypatch.setattr(rex, "pastikan_akses_kegiatan_id", _lolos, raising=False)
    monkeypatch.setattr(ract, "pastikan_akses_kegiatan", _lolos, raising=False)
    import shared_utils
    monkeypatch.setattr(shared_utils, "pastikan_akses_kegiatan", _lolos, raising=False)
    return fake, blob, jejak


async def _seed(dbx):
    await dbx.inventory_activities.insert_one({
        "id": "keg-1", "kode_satker": "527010", "nomor_surat": "SR-1",
        "status_pengesahan": "draft",
        "documents": [{"gridfs_id": "blob-kegiatan"}],
    })
    await dbx.assets.insert_many([
        {"id": "a1", "activity_id": "keg-1", "asset_name": "Laptop",
         "photo_gridfs_ids": ["foto-1", "foto-2"], "bast_file_id": "dok-bast"},
        {"id": "a2", "activity_id": "keg-1", "asset_name": "Printer",
         "photo_gridfs_ids": ["foto-3"],
         "document_checklist": [{"documents": [{"gridfs_id": "dok-lampiran"}]}]},
        # Aset kegiatan LAIN — blob-nya tidak boleh ikut tersapu.
        {"id": "b1", "activity_id": "keg-2", "asset_name": "Meja",
         "photo_gridfs_ids": ["foto-tetangga"]},
    ])


class _Req:
    """Objek Request minimal — hanya dipakai oleh dekorator rate-limit."""
    class _C:
        host = "127.0.0.1"
    client = _C()
    headers = {}


def test_bulk_delete_ekspor_membebaskan_blob(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    assert {"foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran"} <= blob

    _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))

    # INI temuan C18: sebelum perbaikan, kelimanya tetap hidup selamanya.
    assert "foto-1" not in blob and "foto-2" not in blob and "foto-3" not in blob
    assert "dok-bast" not in blob and "dok-lampiran" not in blob


def test_bulk_delete_ekspor_tak_menyentuh_kegiatan_lain(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))
    # Cascade harus BERPAGAR activity_id — bukan sapu bersih.
    assert "foto-tetangga" in blob
    assert _jalan(dbx.assets.count_documents({"activity_id": "keg-2"})) == 1


def test_hapus_kegiatan_membebaskan_blob(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))
    for gid in ("foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran", "blob-kegiatan"):
        assert gid not in blob, gid
    assert "foto-tetangga" in blob


def test_hapus_kegiatan_menulis_jejak_audit(lingkungan):
    dbx, _, jejak = lingkungan
    _jalan(_seed(dbx))
    _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))

    # C19: handler ini dulu tak menulis satu baris pun. Feed delta luring dan
    # tombstone LBKP keduanya membacanya lewat action "bulk_delete" + target.
    baris = [j for j in jejak if j["action"] == "bulk_delete" and j["target"] == "keg-1"]
    assert len(baris) == 1, f"jejak yang tertulis: {jejak}"
    # Jumlah aset dihitung SEBELUM delete_many — kalau sesudah, isinya 0 dan
    # jejaknya tak berguna untuk merekonstruksi apa pun.
    assert "2 aset" in baris[0]["detail"]


@pytest.mark.parametrize("activity_delete", [False, True])
def test_audit_dan_snapshot_mendahului_delete_media_sesudahnya(lingkungan, monkeypatch, activity_delete):
    dbx, blob, jejak = lingkungan
    _jalan(_seed(dbx))
    original = type(dbx.assets).delete_one
    events = []

    async def deleting(collection, query, *args, **kwargs):
        if collection.name != "assets":
            return await original(collection, query, *args, **kwargs)
        document = await collection.find_one(query)
        assert jejak and jejak[0]["action"] == "bulk_delete"
        assert document
        assert all(gid in blob for gid in document.get("photo_gridfs_ids", []))
        events.append(document["id"])
        return await original(collection, query, *args, **kwargs)

    monkeypatch.setattr(type(dbx.assets), "delete_one", deleting)
    if activity_delete:
        _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))
    else:
        _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))
    assert set(events) == {"a1", "a2"}
    assert not ({"foto-1", "foto-2", "foto-3"} & blob)


@pytest.mark.parametrize("activity_delete", [False, True])
def test_cas_conflict_mempertahankan_media_dan_kegiatan(lingkungan, monkeypatch, activity_delete):
    dbx, blob, jejak = lingkungan
    _jalan(_seed(dbx))
    original = type(dbx.assets).delete_one
    first = True

    async def interleaved(collection, query, *args, **kwargs):
        nonlocal first
        if collection.name == "assets" and first:
            first = False
            # Another editor committed after the deleter read its snapshot.
            await dbx.assets.update_one({"id": "a1"}, {"$set": {"version": 2, "location": "Concurrent"}})
        return await original(collection, query, *args, **kwargs)

    monkeypatch.setattr(type(dbx.assets), "delete_one", interleaved)
    with pytest.raises(HTTPException) as error:
        if activity_delete:
            _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))
        else:
            _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))
    assert error.value.status_code == 409
    assert _jalan(dbx.assets.count_documents({"id": "a1"})) == 1
    assert {"foto-1", "foto-2", "dok-bast", "blob-kegiatan"} <= blob
    assert _jalan(dbx.inventory_activities.count_documents({"id": "keg-1"})) == 1
    assert jejak


def test_bulk_delete_merekonsiliasi_receipt_sebelum_bukti_hilang(lingkungan):
    dbx, _, _ = lingkungan
    async def scenario():
        await _seed(dbx)
        operation = {"_id": "op-bulk-uji", "payload_hash": "hash-uji", "asset_ids": ["a1"],
                     "results": [{"id": "a1", "status": "pending"}]}
        result = {"id": "a1", "status": "applied", "version": 2}
        marker = {"operation_id": operation["_id"], "payload_hash": operation["payload_hash"],
                  "issued_epoch": batch.now_utc().timestamp(), "result": result}
        await dbx.batch_operations.insert_one(operation)
        await dbx.assets.update_one({"id": "a1"}, {"$set": {batch.MARKERS: [marker], "version": 2}})
        await rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN)
        receipt = await dbx.batch_operations.find_one({"_id": operation["_id"]})
        assert receipt["results"] == [result]
        assert await dbx.assets.count_documents({"id": "a1"}) == 0
    _jalan(scenario())
