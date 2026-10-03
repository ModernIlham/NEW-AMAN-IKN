"""Saran legacy dibatasi satker/identitas; simpan tetap memeriksa ulang.

Seluruh data sintetis lokal. Tidak mengirim email atau mengubah master.
"""
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from auth_utils import require_user
from portal_pemegang_utils import alias_identitas_aset
import routes.portal_pemegang as rp

ADMIN = {"id": "petugas-uji", "username": "admin-uji", "role": "admin", "kode_satker": "001"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def database(monkeypatch):
    db = AsyncMongoMockClient()["uji_kandidat_portal"]
    monkeypatch.setattr(rp, "db", db)
    monkeypatch.setattr(rp, "log_audit", AsyncMock())
    run(db.pegawai.insert_many([
        {"id": "p1", "nama": "Pemegang Uji", "nip": "123456789", "kode_satker": "001",
         "status": "aktif", "email": "pemegang@example.test"},
        {"id": "p2", "nama": "Pegawai Luar", "nip": "123456789", "kode_satker": "002",
         "status": "aktif", "email": "lain@example.test"},
    ]))
    run(db.inventory_activities.insert_many([
        {"id": "k1", "name": "Kegiatan Pertama", "kode_satker": "001"},
        {"id": "k2", "name": "Kegiatan Kedua", "kode_satker": "001"},
        {"id": "k3", "name": "Kegiatan Luar", "kode_satker": "002"},
    ]))
    return db


def aset(id="a1", **kwargs):
    return {"id": id, "activity_id": "k1", "asset_name": "Laptop [A]+", "asset_code": "3050104001",
            "NUP": id, "location": "Ruang Uji", "condition": "Baik", "pengguna_nip": "123456789",
            "user": "Pemegang Uji", "photo": "FOTO-PRIBADI", "purchase_price": 10000000, **kwargs}


async def kandidat(**kwargs):
    return await rp.kandidat_aset_admin(**{"pegawai_id": "p1", "search": "", "page": 1,
                                          "page_size": 20, "user": ADMIN, **kwargs})


def test_default_exact_identitas_lintas_kegiatan_bukan_nama_atau_substring(database):
    async def scenario():
        await database.assets.insert_many([
            aset(), aset("a2", activity_id="k2", pengguna_nip=" 123456789 "),
            aset("substring", pengguna_nip="1234567890"), aset("kosong", pengguna_nip=""),
            aset("luar", activity_id="k3"), aset("hapus", dihapus=True),
            aset("dummy", category="Barang DUMMY"), aset("yatim", activity_id="hilang"),
        ])
        data = await kandidat()
        assert data["total"] == 2
        assert {a["id"] for a in data["items"]} == {"a1", "a2"}
        assert all(a["boleh_dipilih"] and not a["alasan"] for a in data["items"])
        assert {a["activity_name"] for a in data["items"]} == {"Kegiatan Pertama", "Kegiatan Kedua"}
        assert "pengguna_nip" not in str(data) and "FOTO-PRIBADI" not in str(data)
        assert "purchase_price" not in str(data)
        assert await database.portal_penugasan.count_documents({}) == 0
    run(scenario())


def test_paginasi_dan_pencarian_literal_sebelum_count(database):
    async def scenario():
        await database.assets.insert_many([aset(f"a{i:02}") for i in range(25)] + [aset("lain", asset_name="Laptop AAA")])
        first = await kandidat(search=" [a]+ ")
        second = await kandidat(search="[a]+", page=2)
        assert first["total"] == second["total"] == 25
        assert len(first["items"]) == 20 and len(second["items"]) == 5
        assert first["total_pages"] == 2
        assert not {a["id"] for a in first["items"]} & {a["id"] for a in second["items"]}
        assert (await kandidat(search=".*"))["total"] == 0
        assert (await kandidat(search="rUANG"))["total"] == 26
    run(scenario())


def test_pengecualian_tidak_melewati_pemegang_bast_dan_identitas(database):
    async def scenario():
        await database.assets.insert_many([
            aset(), aset("tanpa-id", pengguna_nip="", user="  PEMEGANG   UJI "),
            aset("nama-lain", pengguna_nip="", user="Pegawai Berbeda"),
            aset("nomor-lain", pengguna_nip="987654321"), aset("bast", amanah_bast={"bast_id": "b1"}),
            aset("kode-tidak-lengkap", asset_code="123"), aset("luar", activity_id="k3"),
        ])
        data = await kandidat(semua_satker=True)
        rows = {a["id"]: a for a in data["items"]}
        assert data["total"] == 6 and "luar" not in rows
        assert rows["tanpa-id"]["boleh_dipilih"]
        for id in ("nama-lain", "nomor-lain", "bast", "kode-tidak-lengkap"):
            assert rows[id]["boleh_dipilih"] is False and rows[id]["alasan"]
        # Nomor identitas tepat lebih otoritatif daripada ejaan nama lama.
        assert rp._periksa_aset_manual(aset(user="Ejaan Lama"), {"nip": "123456789"}, "001")
    run(scenario())


def test_alias_fisik_terpakai_lintas_kegiatan_tetap_tidak_bisa_dipilih(database):
    async def scenario():
        await database.assets.insert_many([
            aset("a1", NUP="001"), aset("a2", NUP="1", activity_id="k2"),
            aset("a3", NUP="3", kode_register="ABC"), aset("a4", NUP="4"),
        ])
        await database.portal_penugasan.insert_many([
            {"id": "p-as1", "kode_satker": "001", "slot_aktif": alias_identitas_aset(aset(NUP="1"), "001")},
            {"id": "p-reg", "kode_satker": "001", "slot_aktif": alias_identitas_aset(aset(NUP="9", kode_register="abc"), "001")},
            {"id": "p-luar", "kode_satker": "002", "slot_aktif": alias_identitas_aset(aset(NUP="4"), "002")},
        ])
        rows = {a["id"]: a for a in (await kandidat())["items"]}
        assert all(not rows[id]["boleh_dipilih"] for id in ("a1", "a2", "a3"))
        assert rows["a1"]["kunci_fisik"] == rows["a2"]["kunci_fisik"]
        assert rows["a4"]["boleh_dipilih"]
    run(scenario())


def test_scope_pegawai_tidak_layak_dan_nomor_kosong(database):
    async def scenario():
        for kwargs, code in [({"pegawai_id": "p2"}, 404), ({"user": {**ADMIN, "kode_satker": ""}}, 409)]:
            with pytest.raises(HTTPException) as error:
                await kandidat(**kwargs)
            assert error.value.status_code == code
        await database.pegawai.update_one({"id": "p1"}, {"$set": {"nip": ""}})
        await database.assets.insert_one(aset(pengguna_nip=""))
        empty = await kandidat()
        assert empty["items"] == [] and "NIP/NIK" in empty["message"]
        assert (await kandidat(semua_satker=True))["total"] == 1
        await database.pegawai.update_one({"id": "p1"}, {"$set": {"status": "meninggal"}})
        with pytest.raises(HTTPException) as error:
            await kandidat(semua_satker=True)
        assert error.value.status_code == 409
    run(scenario())


def test_post_memeriksa_ulang_pemegang_dan_replay_batch_per_item(database):
    async def scenario():
        await database.assets.insert_many([aset("a1", pengguna_nip=""), aset("a2")])
        assert all(a["boleh_dipilih"] for a in (await kandidat(semua_satker=True))["items"])
        await database.assets.update_one({"id": "a1"}, {"$set": {"user": "Pemegang Baru"}})
        snapshots = await database.assets.find({}, {"_id": 0}).to_list(None)
        body = rp.PenugasanIn(pegawai_id="p1", asset_id="a1", dasar_penugasan="BAST lama yang telah diperiksa")
        req = type("Req", (), {"headers": {"If-Match": "0", "Idempotency-Key": "item-1"}})()
        with pytest.raises(HTTPException) as error:
            await rp.buat_penugasan(body, req, ADMIN)
        assert error.value.status_code == 409
        body = body.model_copy(update={"asset_id": "a2"})
        req.headers["Idempotency-Key"] = "item-2"
        saved = await rp.buat_penugasan(body, req, ADMIN)
        assert await rp.buat_penugasan(body, req, ADMIN) == saved
        assert await database.portal_penugasan.count_documents({}) == 1
        assert await database.assets.find({}, {"_id": 0}).to_list(None) == snapshots
        assert await database.mutasi_bmn.count_documents({}) == 0
    run(scenario())


def test_http_admin_wajib_dan_batas_kueri(database):
    app = FastAPI()
    app.include_router(rp.portal_pemegang_router)
    app.dependency_overrides[require_user] = lambda: {**ADMIN, "role": "operator"}
    with TestClient(app) as client:
        assert client.get("/portal-pemegang/admin/kandidat-aset?pegawai_id=p1").status_code == 403
        app.dependency_overrides[require_user] = lambda: ADMIN
        for params in ({"page": 0}, {"page_size": 101}, {"search": "x" * 121}, {"pegawai_id": ""}):
            response = client.get("/portal-pemegang/admin/kandidat-aset", params={"pegawai_id": "p1", **params})
            assert response.status_code == 422
        assert client.get("/portal-pemegang/admin/kandidat-aset?pegawai_id=p1").status_code == 200
