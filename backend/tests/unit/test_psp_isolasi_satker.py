"""Uji ISOLASI SATKER register PSP (kebocoran yang dilaporkan pemilik).

SK PSP lama tanpa stempel `kode_satker` diloloskan scope_query_field_satker
ke SEMUA satker — daftar "Penetapan Status Penggunaan (PMK 40/2024)" dan
hitungan "Aset ter-PSP" satker lain ikut tercemar. Penyembuhan-mandiri
(_sembuhkan_stempel_psp) menurunkan stempel dari aset cakupan SK (aset →
kegiatan → satker) dan MENYIMPANNYA sehingga kebocoran tertutup permanen.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rp

USER_A = {"username": "a", "role": "admin", "kode_satker": "527010"}
USER_B = {"username": "b", "role": "admin", "kode_satker": "999999"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)

    # Gerbang W9 memakai $regex+$options yang tak didukung mongomock; yang
    # diuji di sini isolasi satker register PSP, bukan gerbang itu (punya
    # ujinya sendiri) — dilewatkan apa adanya.
    async def _lewat(query=None):
        return dict(query or {})
    monkeypatch.setattr(su, "filter_aset_perhitungan", _lewat, raising=False)
    return fake


async def _seed(dbx):
    # Kegiatan + aset milik satker A dan satker B (layak hitung — disahkan).
    await dbx.inventory_activities.insert_many([
        {"id": "keg-a", "kode_satker": "527010",
         "status_pengesahan": "disahkan", "tanggal_selesai": "2026-01-01"},
        {"id": "keg-b", "kode_satker": "999999",
         "status_pengesahan": "disahkan", "tanggal_selesai": "2026-01-01"},
    ])
    await dbx.assets.insert_many([
        {"id": "aset-a", "asset_code": "3100102001", "NUP": "1",
         "asset_name": "Laptop A", "activity_id": "keg-a"},
        {"id": "aset-b", "asset_code": "3100102002", "NUP": "1",
         "asset_name": "Laptop B", "activity_id": "keg-b"},
    ])
    # SK PSP ERA LAMA milik satker A — TANPA stempel kode_satker (inilah
    # dokumen yang bocor tampil di satker B).
    await dbx.psp.insert_one({
        "id": "sk-lama", "nomor_sk": "SK-PSP-1/2025", "tanggal_sk": "2025-05-01",
        "jenis": "psp", "status_pengajuan": "ditetapkan",
        "aset": [{"asset_id": "aset-a", "asset_code": "3100102001",
                  "NUP": "1", "asset_name": "Laptop A"}],
        "lampiran": [], "created_at": "2025-05-01T00:00:00",
    })


def test_sk_tanpa_stempel_tak_lagi_bocor_ke_satker_lain(dbx):
    async def skenario():
        await _seed(dbx)
        a = await rp.daftar_psp(_user=USER_A)
        b = await rp.daftar_psp(_user=USER_B)
        tersimpan = await dbx.psp.find_one({"id": "sk-lama"})
        return a, b, tersimpan
    a, b, tersimpan = _jalan(skenario())
    assert [s["id"] for s in a["items"]] == ["sk-lama"], \
        "satker pemilik harus tetap melihat SK-nya"
    assert b["items"] == [], "SK satker A bocor ke daftar satker B"
    # Stempel tersembuhkan PERMANEN (bukan penyaringan sesaat).
    assert tersimpan["kode_satker"] == "527010"


def test_hitungan_aset_ter_psp_tak_menghitung_satker_lain(dbx):
    async def skenario():
        await _seed(dbx)
        a = await rp.daftar_psp(_user=USER_A)
        b = await rp.daftar_psp(_user=USER_B)
        return a["ringkasan"], b["ringkasan"]
    ring_a, ring_b = _jalan(skenario())
    assert ring_a["aset_tercakup"] == 1
    assert ring_b["aset_tercakup"] == 0, \
        "jumlah Aset ter-PSP satker B tercemar SK satker A"


def test_sk_aset_yatim_tidak_dikarang_stempelnya(dbx):
    """SK yang asetnya tak berkegiatan tidak bisa diturunkan satkernya —
    dibiarkan tanpa stempel (era-lama, dirapikan backfill), TIDAK dikarang."""
    async def skenario():
        await dbx.psp.insert_one({
            "id": "sk-yatim", "nomor_sk": "SK-X", "tanggal_sk": "2025-01-01",
            "jenis": "psp", "status_pengajuan": "ditetapkan",
            "aset": [{"asset_id": "aset-hilang"}], "lampiran": [],
        })
        await rp.daftar_psp(_user=USER_A)
        return await dbx.psp.find_one({"id": "sk-yatim"})
    doc = _jalan(skenario())
    assert not str(doc.get("kode_satker") or "")


def test_ekspor_csv_psp_ikut_tersembuhkan(dbx):
    async def skenario():
        await _seed(dbx)
        return await rp.export_psp(_user=USER_B)
    resp = _jalan(skenario())
    assert "SK-PSP-1/2025" not in resp.body.decode("utf-8-sig")
