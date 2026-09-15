"""Regresi identitas kegiatan → master → pemilih scope/akun lintas modul."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

import auth_utils as au
import shared_utils as su
import routes.activities as ra
import routes.satker as rs
import routes.users as ru

ADMIN = {"id": "pusat", "role": "admin", "kode_satker": ""}


def jalan(coro):
    return asyncio.run(coro)


@pytest.fixture
def basis(monkeypatch):
    db = AsyncMongoMockClient()["uji_satker"]
    for mod in (au, su, ra, rs, ru):
        monkeypatch.setattr(mod, "db", db)
    monkeypatch.setattr(rs, "log_audit", AsyncMock())
    monkeypatch.setattr(ra, "next_ticket_number", AsyncMock(return_value="INV-2026-001"))
    return db


def kegiatan(kode="A", nama="Satker A", **extra):
    return ra.InventoryActivityCreate(nomor_surat="INV/1", nama_kegiatan="Uji", kode_satker=kode,
                                      nama_satker=nama, **extra)


def siapkan(db):
    jalan(db.inventory_activities.insert_one({"id": "k1", **kegiatan().model_dump(), "created_at": "2026-01-01"}))
    jalan(db.satker.insert_one({"kode_satker": "A", "nama_satker": "Satker A", "alamat": "Alamat tetap"}))


def test_route_post_benar_memanggil_create_dengan_auth(basis):
    app = FastAPI()
    app.include_router(ra.activities_router)
    app.dependency_overrides[ra.require_writer] = lambda: ADMIN
    with TestClient(app) as client:
        r = client.post("/inventory-activities", json=kegiatan(" B ", " Satker B ").model_dump())
    assert r.status_code == 200, r.text
    assert r.json()["kode_satker"] == "B"
    assert jalan(basis.satker.find_one({"kode_satker": "B"}))["nama_satker"] == "Satker B"
    route = next(r for r in app.routes if r.path == "/inventory-activities" and "POST" in r.methods)
    assert route.endpoint is ra.create_inventory_activity
    assert any(d.call is ra.require_writer for d in route.dependant.dependencies)


def test_edit_satker_legacy_mendaftarkan_master_dan_scope(basis):
    jalan(basis.inventory_activities.insert_one({"id": "k1", **kegiatan("B", "Satker B").model_dump()}))
    hasil = jalan(ra.update_inventory_activity("k1", kegiatan(" B ", " Satker B "), ADMIN))
    assert hasil["kode_satker"] == "B"
    assert jalan(basis.satker.find_one({"kode_satker": "B"}))
    scoped = jalan(au._terapkan_satker_aktif(dict(ADMIN), "B"))
    assert scoped["kode_satker"] == "B"


def test_satker_legacy_belum_master_tetap_bisa_dipilih_dan_ikat_akun(basis):
    jalan(basis.inventory_activities.insert_one({"id": "k1", **kegiatan("B", "Satker B").model_dump()}))
    jalan(basis.users.insert_one({"id": "u", "role": "viewer", "kode_satker": ""}))
    assert jalan(au._terapkan_satker_aktif(dict(ADMIN), "B"))["kode_satker"] == "B"
    jalan(ru.set_user_satker("u", {"kode_satker": "B"}, ADMIN))
    assert jalan(basis.users.find_one({"id": "u"}))["kode_satker"] == "B"
    with pytest.raises(HTTPException):
        jalan(ru.set_user_satker("u", {"kode_satker": "TIDAK-ADA"}, ADMIN))


def test_satu_kegiatan_rename_nama_meminta_konfirmasi_dan_jaga_kop(basis):
    siapkan(basis)
    with pytest.raises(HTTPException) as e:
        jalan(ra.update_inventory_activity("k1", kegiatan(nama="Nama baru"), ADMIN))
    assert e.value.detail["konflik_satker"]
    hasil = jalan(ra.update_inventory_activity("k1", kegiatan(nama="Nama baru", perbarui_satker=True), ADMIN))
    assert hasil["nama_satker"] == "Nama baru"
    master = jalan(basis.satker.find_one({"kode_satker": "A"}))
    assert master["nama_satker"] == "Nama baru"
    assert master["alamat"] == "Alamat tetap"


@pytest.mark.parametrize("nama", ["Satker A", "Nama baru"])
def test_ganti_kode_migrasi_semua_stempel_dan_counter_tanpa_ganti_naskah(basis, nama):
    siapkan(basis)
    koleksi = ["users", "pegawai", "pejabat", "ruangan", "sign_requests", "denah_lokasi", "surat", "persuratan_settings", "modul_baru"]
    for coll in koleksi:
        jalan(basis[coll].insert_many([
            {"id": "milik", "kode_satker": "A", "nomor": "LAMA-001", "file_id": "tetap"},
            {"id": "lain", "kode_satker": "C"}, {"id": "global", "kode_satker": ""}]))
    for cid in ["surat_keluar_2026-09:A:d=B", "inventory_activity_ticket_2026:A", "ba_perbaikan_seq:A"]:
        jalan(basis.counters.insert_one({"_id": cid, "seq": 89}))
    with pytest.raises(HTTPException):
        jalan(ra.update_inventory_activity("k1", kegiatan("B", nama), ADMIN))
    jalan(ra.update_inventory_activity("k1", kegiatan("B", nama, perbarui_satker=True), ADMIN))
    for coll in koleksi:
        milik = jalan(basis[coll].find_one({"id": "milik"}))
        assert milik == {**milik, "kode_satker": "B", "nomor": "LAMA-001", "file_id": "tetap"}
        assert jalan(basis[coll].find_one({"id": "lain"}))["kode_satker"] == "C"
        assert jalan(basis[coll].find_one({"id": "global"}))["kode_satker"] == ""
    assert jalan(basis.satker.find_one({"kode_satker": "B"}))["alamat"] == "Alamat tetap"
    assert jalan(basis.satker.find_one({"kode_satker": "A"})) is None
    assert jalan(basis.counters.find_one({"_id": "surat_keluar_2026-09:B:d=B"}))["seq"] == 89


def test_master_edit_sinkron_nama_kegiatan_dan_lookup(basis):
    siapkan(basis)
    jalan(rs.simpan_satker("A", rs.SatkerIn(kode_satker="A", nama_satker="Baru"), ADMIN))
    assert jalan(basis.inventory_activities.find_one({"id": "k1"}))["nama_satker"] == "Baru"
    assert jalan(ra.satker_lookup(kode="A", _user=ADMIN))["nama_satker"] == "Baru"


def test_kode_tujuan_terpakai_tidak_menggabungkan_dua_satker(basis):
    siapkan(basis)
    jalan(basis.satker.insert_one({"kode_satker": "B", "nama_satker": "Satker B"}))
    with pytest.raises(HTTPException):
        jalan(ra.update_inventory_activity("k1", kegiatan("B", "Satker A", perbarui_satker=True), ADMIN))
    assert jalan(basis.inventory_activities.find_one({"id": "k1"}))["kode_satker"] == "A"
    assert jalan(basis.satker.find_one({"kode_satker": "B"}))["nama_satker"] == "Satker B"


def test_admin_satker_tidak_memindah_ke_kode_lain(basis):
    siapkan(basis)
    with pytest.raises(HTTPException) as e:
        jalan(ra.update_inventory_activity("k1", kegiatan("B", perbarui_satker=True), {"role": "admin", "kode_satker": "A"}))
    assert e.value.status_code == 403


def test_kegagalan_migrasi_memulihkan_stempel_dan_nama(basis):
    from satker_referensi import ganti_kode_satker
    siapkan(basis)
    jalan(basis.surat.insert_one({"id": "s", "kode_satker": "A", "nomor": "001"}))
    gagal = SimpleNamespace(find=basis.surat.find, find_one=basis.surat.find_one, update_one=basis.surat.update_one,
                            update_many=AsyncMock(side_effect=RuntimeError("uji gagal tulis")))
    class BasisGangguan:
        def __getitem__(self, nama):
            return gagal if nama == "surat" else basis[nama]

        def __getattr__(self, nama):
            return getattr(basis, nama)
    with pytest.raises(HTTPException) as e:
        jalan(ganti_kode_satker(BasisGangguan(), "A", "B", "Baru"))
    assert e.value.status_code == 503
    assert jalan(basis.inventory_activities.find_one({"id": "k1"}))["kode_satker"] == "A"
    assert jalan(basis.inventory_activities.find_one({"id": "k1"}))["nama_satker"] == "Satker A"
    assert jalan(basis.satker.find_one({"kode_satker": "A"}))["alamat"] == "Alamat tetap"
    jalan(ganti_kode_satker(basis, "A", "B", "Baru"))
    assert jalan(basis.surat.find_one({"id": "s"}))["kode_satker"] == "B"


def test_kegiatan_era_lama_tidak_memigrasi_data_global(basis):
    jalan(basis.inventory_activities.insert_one({"id": "k1", **kegiatan("", "").model_dump()}))
    jalan(basis.users.insert_one(dict(ADMIN)))
    jalan(ra.update_inventory_activity("k1", kegiatan("B", "Satker B"), ADMIN))
    assert jalan(basis.users.find_one({"id": "pusat"}))["kode_satker"] == ""
    assert jalan(basis.satker.find_one({"kode_satker": "B"}))


def test_lookup_nama_master_tetapi_hierarki_kegiatan_tetap_utuh(basis):
    siapkan(basis)
    hierarki = [{"nama": "Unit", "eselon2": ["Subunit"]}]
    jalan(basis.inventory_activities.update_one({"id": "k1"}, {"$set": {"eselon1": hierarki}}))
    jalan(basis.satker.update_one({"kode_satker": "A"}, {"$set": {"eselon1": ["Unit"], "nama_satker": "Nama master"}}))
    hasil = jalan(ra.satker_lookup(kode="A", _user=ADMIN))
    assert hasil["nama_satker"] == "Nama master"
    assert hasil["eselon1"] == hierarki


def test_kunci_migrasi_menolak_perubahan_kode_kedua(basis):
    from satker_referensi import ganti_kode_satker
    siapkan(basis)
    jalan(basis.satker.update_one({"kode_satker": "A"}, {"$set": {"migrasi_kode": {"token": "lain", "tujuan": "C"}}}))
    with pytest.raises(HTTPException) as e:
        jalan(ganti_kode_satker(basis, "A", "B", "Baru"))
    assert e.value.status_code == 409
    assert jalan(basis.inventory_activities.find_one({"id": "k1"}))["kode_satker"] == "A"
