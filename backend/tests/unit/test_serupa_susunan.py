"""Eksekutif per Barang Serupa mengikuti "Susunan PDF" yang sama dengan Data Aset.

Permintaan pemilik (Nov 2026): pilihan Susunan PDF Data Aset dulu tak
berdampak pada Eksekutif per Barang Serupa. Kini aset dibagi dulu menjadi
bagian (kunci SAMA dengan Data Aset), lalu barang serupa dihitung di dalam
tiap bagian. Jumlah unit seluruh bagian tetap = total aset yang lolos filter.
"""
import asyncio
import io
import re
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import data_aset_pdf as dap
import routes.assets as ra
import routes.reports as rp
import shared_utils as su


# ── Helper murni ──────────────────────────────────────────────────────────

def test_bagi_susunan_tanpa_mode_satu_bagian_utuh():
    rows = [{"id": "1"}, {"id": "2"}]
    assert dap.bagi_susunan(rows, "") == [{"label": "", "rows": rows}]


def test_bagi_susunan_abjad_kosong_di_akhir_tanpa_mutasi():
    rows = [{"id": "1", "location": "Gudang"}, {"id": "2"},
            {"id": "3", "location": "aula"}, {"id": "4", "location": "Gudang"}]
    salinan = [dict(r) for r in rows]
    bagian = dap.bagi_susunan(rows, "lokasi")
    assert [b["label"] for b in bagian] == ["aula", "Gudang", "Lokasi belum diisi"]
    assert [[a["id"] for a in b["rows"]] for b in bagian] == [["3"], ["1", "4"], ["2"]]
    assert rows == salinan


def test_bagi_susunan_eselon_kosong_seluruhnya_di_akhir():
    rows = [{"id": "1"}, {"id": "2", "eselon1": "Zeta", "eselon2": "Biro"}]
    bagian = dap.bagi_susunan(rows, "eselon2")
    assert bagian[0]["label"] == "Zeta > Biro"
    assert "belum diisi" in bagian[-1]["label"]


@pytest.mark.parametrize("mode", list(dap.GROUP_OPTIONS))
def test_bagi_susunan_tidak_membuang_aset(mode):
    rows = [{"id": str(i), "purchase_price": i} for i in range(5)]
    bagian = dap.bagi_susunan(rows, mode)
    assert sorted(a["id"] for b in bagian for a in b["rows"]) == [str(i) for i in range(5)]


def test_bagi_susunan_menolak_mode_asing():
    with pytest.raises(ValueError):
        dap.bagi_susunan([], "$where")


# ── Builder dengan FakeDB ──────────────────────────────────────────────────

@pytest.fixture
def database(monkeypatch):
    fake = AsyncMongoMockClient()["serupa_susunan"]
    for mod in (rp, ra, su):
        monkeypatch.setattr(mod, "db", fake)
    return fake


USER = {"username": "uji", "role": "admin", "kode_satker": "A"}


# mongomock membuang SELURUH anggota `$push` objek bila satu field yang
# dirujuk tidak ada (MongoDB asli hanya menghilangkan field itu). Maka data uji
# mengisi eksplisit setiap field yang di-$push pipeline Barang Serupa.
_FIELD_DIPUSH = ("category", "nomor_spm", "perolehan_dari_nama", "nomor_kontrak",
                 "nomor_bukti_perolehan", "supplier", "serial_number", "user",
                 "pengguna_nip", "kode_satker", "kode_satker_lengkap", "siman",
                 *(f"eselon{i}" for i in range(1, 6)))


def _aset(i, nama, lokasi, **extra):
    return {**dict.fromkeys(_FIELD_DIPUSH),
            "id": f"id{i:03}", "activity_id": "k1", "asset_code": "3100102001",
            "asset_name": nama, "NUP": str(i), "purchase_price": 1000,
            "purchase_date": "2020-01-01", "brand": "Merk", "model": "X",
            "location": lokasi, "condition": "Baik", "inventory_status": "Ditemukan",
            **extra}


async def seed(db):
    await db.inventory_activities.insert_many([
        {"id": "k1", "kode_satker": "A", "nama_satker": "Satker Uji"},
        {"id": "k2", "kode_satker": "B"}])
    await db.assets.insert_many([
        # Laptop tersebar di dua lokasi → satu kelompok jadi dua baris.
        _aset(1, "Laptop", "Gedung B", user="Budi"),
        _aset(2, "Laptop", "Gedung A", user="Budi"),
        _aset(3, "Laptop", "Gedung B", pengguna_nip="199001012020011001"),
        _aset(4, "Meja", "Gedung A", asset_code="3050102001"),
        _aset(5, "Kursi", "", asset_code="3050102002"),
    ])
    await db.assets.insert_one({"id": "rahasia", "activity_id": "k2", "asset_name": "JANGAN MUNCUL"})


def _ringkas(data):
    return [(s["label"], [(r["asset_name"], r["count"], r["nup_range"]) for r in s["rows"]])
            for s in data["sections"]]


def test_tanpa_susunan_perilaku_lama(database):
    async def run():
        await seed(database)
        data = await rp._build_executive_grouped_data("k1")
        assert len(data["sections"]) == 1 and data["sections"][0]["label"] == ""
        laptop = next(r for r in data["rows"] if r["asset_name"] == "Laptop")
        assert laptop["count"] == 3 and laptop["nup_range"] == "1-3"
        assert data["total_units"] == 5 and data["data_group_by"] == ""
    asyncio.run(run())


def test_lokasi_memecah_kelompok_dan_total_tetap(database):
    async def run():
        await seed(database)
        data = await rp._build_executive_grouped_data("k1", data_group_by="lokasi")
        assert _ringkas(data) == [
            ("Gedung A", [("Meja", 1, "4"), ("Laptop", 1, "2")]),
            ("Gedung B", [("Laptop", 2, "1, 3")]),
            ("Lokasi belum diisi", [("Kursi", 1, "5")]),
        ]
        assert data["total_units"] == 5 and data["total_groups"] == 4
        assert [r["no"] for r in data["rows"]] == [1, 2, 3, 4]
        assert data["data_group_label"] == "Lokasi"
        assert data["sections"][1]["total_units"] == 2
        assert data["sections"][1]["value_fmt"] == "2.000"
    asyncio.run(run())


def test_susunan_ikut_filter_layar(database):
    async def run():
        await seed(database)
        f = rp.filter_laporan_dari_map({"location": ["Gedung B"]})
        data = await rp._build_executive_grouped_data("k1", filter_aset=f, data_group_by="lokasi")
        assert _ringkas(data) == [("Gedung B", [("Laptop", 2, "1, 3")])]
        assert data["filter_aktif"]
    asyncio.run(run())


def test_jenjang_kode_memakai_uraian_kodefikasi(database):
    async def run():
        await seed(database)
        await database.kodefikasi.insert_many([
            {"kode": "310", "uraian": "Alat Kantor"}, {"kode": "305", "uraian": "Alat Rumah Tangga"}])
        data = await rp._build_executive_grouped_data("k1", data_group_by="kode_2")
        assert [s["label"] for s in data["sections"]] == [
            "305 - Alat Rumah Tangga", "310 - Alat Kantor"]
        # Jenjang kode tidak pernah memecah satu kelompok (kode penuh sama).
        assert [r["count"] for r in data["sections"][1]["rows"]] == [3]
    asyncio.run(run())


def test_pemegang_memakai_master_pegawai_satker_kegiatan(database):
    async def run():
        await seed(database)
        await database.pegawai.insert_many([
            {"nip": "199001012020011001", "nama": "Siti Resmi", "kode_satker": "A"},
            {"nip": "199001012020011001", "nama": "BOCOR SATKER LAIN", "kode_satker": "B"}])
        data = await rp._build_executive_grouped_data("k1", data_group_by="pemegang")
        assert [s["label"] for s in data["sections"]] == [
            "Budi (tanpa nomor identitas)",
            "Siti Resmi (Identitas: 199001012020011001)",
            "Belum ada pemegang"]
        assert data["total_units"] == 5
    asyncio.run(run())


def test_psp_wajib_lingkup_pengguna_dan_register_ber_scope(database):
    async def run():
        await seed(database)
        with pytest.raises(ValueError):
            await rp._build_executive_grouped_data("k1", data_group_by="psp")
        await database.psp.insert_many([
            {"nomor_sk": "SK-1", "tanggal_sk": "2021-01-01", "status_pengajuan": "ditetapkan",
             "kode_satker": "A", "aset": [{"asset_id": "id001"}, {"asset_id": "id002"}]},
            {"nomor_sk": "TERLARANG", "tanggal_sk": "2021-01-01", "status_pengajuan": "ditetapkan",
             "kode_satker": "B", "aset": [{"asset_id": "id003"}]}])
        data = await rp._build_executive_grouped_data("k1", data_group_by="psp", data_user=USER)
        assert [s["label"] for s in data["sections"]] == ["SK-1 / 1 Januari 2021", "Belum memiliki PSP"]
        assert [r["count"] for r in data["sections"][0]["rows"]] == [2]
    asyncio.run(run())


def test_foto_sampul_dari_anggota_bagian_itu(database):
    async def run():
        await seed(database)
        await database.assets.update_one({"id": "id001"}, {"$set": {"gallery_thumbnail": "data:foto-1"}})
        await database.assets.update_one({"id": "id002"}, {"$set": {"gallery_thumbnail": "data:foto-2"}})
        data = await rp._build_executive_grouped_data("k1", data_group_by="lokasi")
        laptop_a = data["sections"][0]["rows"][1]
        laptop_b = data["sections"][1]["rows"][0]
        assert laptop_a["photo_url"] == "data:foto-2"
        assert laptop_b["photo_url"] == "data:foto-1"
    asyncio.run(run())


def test_gerbang_baris_setelah_dipecah_ditolak_bukan_dipangkas(database, monkeypatch):
    async def run():
        await seed(database)
        monkeypatch.setattr(rp, "MAKS_KELOMPOK_LAPORAN", 3)
        # Tanpa Susunan: 3 kelompok → lolos.
        await rp._build_executive_grouped_data("k1")
        with pytest.raises(HTTPException) as e:
            await rp._build_executive_grouped_data("k1", data_group_by="lokasi")
        assert e.value.status_code == 400 and "Persempit" in e.value.detail
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["$where", "lokasi; drop"])
def test_endpoint_menolak_susunan_di_luar_allowlist(database, mode):
    async def run():
        await seed(database)
        with pytest.raises(HTTPException) as e:
            await rp.generate_executive_grouped_pdf("k1", data_group_by=mode, filter_aset=None, _user=USER)
        assert e.value.status_code == 400
    asyncio.run(run())


def test_endpoint_tidak_boleh_lintas_satker(database):
    async def run():
        await seed(database)
        with pytest.raises(HTTPException) as e:
            await rp.generate_executive_grouped_pdf("k2", data_group_by="lokasi", filter_aset=None, _user=USER)
        assert e.value.status_code == 403
    asyncio.run(run())


def test_zip_meneruskan_susunan_ke_barang_serupa(database, monkeypatch):
    from starlette.requests import Request
    from fastapi.responses import StreamingResponse
    gen = AsyncMock(side_effect=lambda *a, **kw: StreamingResponse(io.BytesIO(b"%PDF-uji")))
    monkeypatch.setattr(rp, "generate_executive_grouped_pdf", gen)
    async def run():
        await seed(database)
        payload = rp.BatchPDFRequest(types=["executive-grouped"], data_group_by="eselon2",
                                     filter={"location": ["Gedung A"]}, detail_fields="spm")
        await rp.batch_download_pdf_zip.__wrapped__(Request({"type": "http"}), "k1", payload, USER)
        call = gen.call_args
        assert call.kwargs["data_group_by"] == "eselon2"
        assert call.kwargs["detail_fields"] == "spm"
        assert call.kwargs["_user"] is USER and call.kwargs["filter_aset"].aktif
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["", "lokasi"], ids=["biasa", "lokasi"])
def test_pdf_nyata_judul_bagian_dan_seluruh_baris(database, mode, monkeypatch):
    from pypdf import PdfReader
    import weasyprint
    asli = weasyprint.HTML
    captured = []

    def html_lokal(string):
        # QA mandiri tanpa ketergantungan jaringan Google Fonts.
        captured.append(string)
        return asli(string=re.sub(r"@import url\([^;]+;", "", string))
    monkeypatch.setattr(weasyprint, "HTML", html_lokal)

    async def run():
        await seed(database)
        await database.assets.update_one({"id": "id004"}, {"$set": {"location": "<b>Bukan HTML</b>"}})
        return await rp.generate_executive_grouped_pdf("k1", data_group_by=mode, filter_aset=None, _user=USER)
    response = asyncio.run(run())
    raw = asyncio.run(rp._get_pdf_buffer_from_response(response))
    text = "\n".join(p.extract_text() for p in PdfReader(raw).pages)
    html = captured[0]
    assert "<b>Bukan HTML</b>" not in html and "JANGAN MUNCUL" not in text
    for nama in ("Laptop", "Meja", "Kursi"):
        assert nama in text
    if mode:
        assert "Disusun menurut" in text
        for judul in ("Lokasi: Gedung A", "Lokasi: Gedung B", "Lokasi: Lokasi belum diisi"):
            assert judul in text
        assert "dalam 4 bagian" in text
        assert response.headers["content-disposition"].endswith('_lokasi.pdf"')
    else:
        assert "Disusun menurut" not in text and "Lokasi:" not in text
        assert response.headers["content-disposition"].endswith('Barang_Serupa.pdf"')
