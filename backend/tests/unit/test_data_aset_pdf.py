"""Data Aset: kelompok tidak mengubah lingkup, sort, dan kelengkapan baris."""
import asyncio
import io
import os
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from pypdf import PdfReader

import data_aset_pdf as dap
import routes.assets as ra
import routes.reports as rp
import shared_utils as su


def test_opsi_frontend_backend_tetap_sama():
    src = (Path(__file__).parents[3] / "frontend/src/components/assets/rekapitulasi/ReportDownloads.jsx").read_text(encoding="utf-8")
    opsi = src.split("export const dataGroupOptions = [", 1)[1].split("\n];", 1)[0]
    assert set(re.findall(r'\["([^"]*)",', opsi)) == set(dap.GROUP_OPTIONS)


@pytest.mark.parametrize("mode", list(dap.GROUP_OPTIONS))
def test_semua_mode_mempertahankan_aset_kosong_dan_tidak_memutasi(mode):
    rows = [{"id": "1", "purchase_price": 15}, {"id": "2", "purchase_price": "salah"}]
    actual, groups = dap.irisan_kelompok(rows, mode)
    assert actual == rows
    assert len(groups) == 1 and groups[0]["count"] == 2
    assert groups[0]["value_fmt"] == "15"
    assert rows == [{"id": "1", "purchase_price": 15}, {"id": "2", "purchase_price": "salah"}]


@pytest.mark.parametrize("level,prefix", list(dap.LEVEL_LENGTHS.items()))
def test_lima_jenjang_kode(level, prefix):
    rows = [{"id": "1", "asset_code": "3100102001"}, {"id": "2", "asset_code": "3050102001"}, {"id": "3", "asset_code": ""}]
    actual, groups = dap.irisan_kelompok(rows, f"kode_{level}", uraian={"3100102001"[:prefix]: "Uraian Resmi"})
    assert groups[0]["label"] == "3100102001"[:prefix] + " - Uraian Resmi"
    assert groups[0]["count"] == (2 if level == 1 else 1)
    assert "belum tersedia" in groups[-1]["label"]
    assert {a["id"] for a in actual} == {"1", "2", "3"}


@pytest.mark.parametrize("level", range(1, 6))
def test_eselon_membedakan_jalur_induk(level):
    a = {f"eselon{i}": "Unit" for i in range(1, level + 1)}
    _, groups = dap.irisan_kelompok([a, {**a, "eselon1": "Induk lain"}], f"eselon{level}")
    assert len(groups) == 2


def test_pemegang_nik_nama_tanpa_nomor_dan_homonim():
    rows = [{"id": "a", "user": "Dewi", "pengguna_nip": "123"},
            {"id": "b", "user": "Dewi", "pengguna_nip": "456"},
            {"id": "c", "user": "Dewi"}, {"id": "d", "user": "  dewi "}, {"id": "e"}]
    actual, groups = dap.irisan_kelompok(rows, "pemegang", pegawai={"123": {"nama": "Dewi Resmi"}})
    assert len(actual) == 5 and len(groups) == 4
    assert "Dewi Resmi" in groups[0]["label"] and "NIP" not in groups[0]["label"]
    assert [g["count"] for g in groups] == [1, 1, 2, 1]


@pytest.mark.parametrize("mode,field", [("lokasi", "location"), ("spm", "nomor_spm"), ("supplier", "supplier"), ("perolehan", "perolehan_dari_nama")])
def test_kelompok_stabil_bukan_sort_abjad(mode, field):
    rows = [{"id": "z", field: "Z"}, {"id": "a", field: "A"}, {"id": "b", field: "Z"}]
    actual, groups = dap.irisan_kelompok(rows, mode)
    assert [a["id"] for a in actual] == ["z", "b", "a"]
    assert [g["label"] for g in groups] == ["Z", "A"]


def test_kelompok_sebelum_irisan_499_tanpa_hilang_duplikat():
    rows = [{"id": str(i), "location": "A" if i % 2 == 0 else "B"} for i in range(1200)]
    bagian = [dap.irisan_kelompok(rows, "lokasi", (i, i + 499)) for i in range(0, 1200, 499)]
    actual = [a for part, _ in bagian for a in part]
    assert [a["id"] for a in actual] == [str(i) for i in range(0, 1200, 2)] + [str(i) for i in range(1, 1200, 2)]
    assert len({a["id"] for a in actual}) == 1200
    assert bagian[1][1][0]["lanjutan"] is True
    assert bagian[1][1][0]["offset"] == 499
    assert bagian[1][1][0]["count"] == 600


@pytest.fixture
def database(monkeypatch):
    fake = AsyncMongoMockClient()["data_pdf"]
    for mod in (rp, ra, su):
        monkeypatch.setattr(mod, "db", fake)
    return fake


USER = {"username": "uji", "role": "admin", "kode_satker": "A"}


async def seed(db, count=40):
    await db.inventory_activities.insert_many([
        {"id": "k1", "kode_satker": "A", "nama_satker": "Satker Uji", "tanggal_mulai": "2020-01-01"},
        {"id": "k2", "kode_satker": "B"}])
    await db.assets.insert_many([{
        "id": f"id{i:04}", "activity_id": "k1", "asset_name": f"Aset Uji {i:04}",
        "asset_code": "3100102001", "NUP": str(i + 1), "purchase_price": 1000 + i,
        "location": "Gedung A" if i % 2 == 0 else "Gedung B",
        "user": "Pemegang Tanpa Nomor" if i % 2 == 0 else "Pemegang Lain",
        "inventory_status": "Ditemukan", "condition": "Baik",
        "eselon1": "Kedeputian", "eselon2": "Direktorat",
        "purchase_date": "2020-01-01", "created_at": f"2020-01-{i % 28 + 1:02}",
    } for i in range(count)])
    await db.assets.insert_one({"id": "rahasia", "activity_id": "k2", "asset_name": "JANGAN MUNCUL"})


@pytest.mark.parametrize("sort", list(dap.ASSET_SORT_OPTIONS))
def test_builder_sort_sama_dengan_daftar_mongo_dan_filter(database, sort):
    async def run():
        await seed(database, 10)
        f = rp.filter_laporan_dari_map({"location": ["Gedung A"]})
        data = await rp._build_executive_summary_data("k1", sort_by=sort, filter_aset=f)
        expected = await database.assets.find({"activity_id": "k1", **f.query}).sort(dap.ASSET_SORT_OPTIONS[sort]).to_list(None)
        assert [a["asset_name"] for a in data["assets"]] == [a["asset_name"] for a in expected]
        assert data["asset_count"] == 5 and data["filter_aktif"]
    asyncio.run(run())


def test_psp_register_resmi_scope_dan_fallback_siman(database):
    async def run():
        await seed(database, 4)
        await database.assets.update_one({"id": "id0001"}, {"$set": {"siman": {"referensi": {"no_psp": "SIMAN-1"}}}})
        await database.psp.insert_many([
            {"nomor_sk": "SK-LAMA", "tanggal_sk": "2020-01-01", "status_pengajuan": "ditetapkan", "kode_satker": "A", "aset": [{"asset_id": "id0000"}]},
            {"nomor_sk": "SK-BARU", "tanggal_sk": "2021-01-01", "status_pengajuan": "ditetapkan", "kode_satker": "A", "aset": [{"asset_id": "id0000"}]},
            {"nomor_sk": "DRAF", "status_pengajuan": "draf", "kode_satker": "A", "aset": [{"asset_id": "id0002"}]},
            {"nomor_sk": "TERLARANG", "status_pengajuan": "ditetapkan", "kode_satker": "B", "aset": [{"asset_id": "id0003"}]},
        ])
        data = await rp._build_executive_summary_data("k1", data_group_by="psp", sort_by="name_asc", data_user=USER)
        assert [g["label"] for g in data["asset_groups"]] == ["SK-BARU / 1 Januari 2021", "SIMAN-1", "Belum memiliki PSP"]
        assert [g["count"] for g in data["asset_groups"]] == [1, 1, 2]
    asyncio.run(run())


def test_embeding_foto_hanya_irisan_setelah_kelompok(database, monkeypatch):
    photo = AsyncMock(return_value="")
    monkeypatch.setattr(rp, "_gridfs_photo_data_uri", photo)
    async def run():
        await seed(database, 505)
        await database.assets.update_many({"activity_id": "k1"}, {"$set": {"photo_gridfs_ids": ["grid-id"]}})
        data = await rp._build_executive_summary_data("k1", data_group_by="lokasi", sort_by="name_desc", row_slice=(499, 998))
        assert len(data["assets"]) == 6 and data["asset_count"] == 505
        assert photo.await_count == 6
    asyncio.run(run())


@pytest.mark.parametrize("mode,sort", [("$where", "newest"), ("lokasi", "$natural")])
def test_endpoint_menolak_opsi_di_luar_allowlist(database, mode, sort):
    async def run():
        await seed(database, 1)
        with pytest.raises(HTTPException) as e:
            await rp.generate_executive_data_pdf("k1", data_group_by=mode, sort_by=sort, filter_aset=None, _user=USER)
        assert e.value.status_code == 400
    asyncio.run(run())


def test_endpoint_tidak_boleh_lintas_satker(database):
    async def run():
        await seed(database, 1)
        with pytest.raises(HTTPException) as e:
            await rp.generate_executive_data_pdf("k2", data_group_by="psp", filter_aset=None, _user=USER)
        assert e.value.status_code == 403
    asyncio.run(run())


def test_route_pdf_meneruskan_kelompok_sort_dan_filter(database, monkeypatch):
    captured = []
    class Html:
        def __init__(self, string):
            captured.append(string)

        def write_pdf(self):
            return b"%PDF-uji"

    import weasyprint
    monkeypatch.setattr(weasyprint, "HTML", Html)
    async def run():
        await seed(database, 8)
        f = rp.filter_laporan_dari_map({"location": ["Gedung A"]})
        await rp.generate_executive_data_pdf("k1", filter_aset=f, _user=USER,
                                              data_group_by="lokasi", sort_by="name_desc")
        html = captured[0]
        assert "Lokasi: Gedung A" in html and "Gedung B" not in html
        assert "JANGAN MUNCUL" not in html and "Laporan tersaring" in html
        assert html.index("Aset Uji 0006") < html.index("Aset Uji 0004") < html.index("Aset Uji 0000")
    asyncio.run(run())


def test_zip_meneruskan_pilihan_ke_seluruh_bagian(database, monkeypatch):
    from starlette.requests import Request
    from fastapi.responses import StreamingResponse
    import zipfile
    gen = AsyncMock(side_effect=lambda *args, **kw: StreamingResponse(io.BytesIO(b"%PDF-uji")))
    monkeypatch.setattr(rp, "generate_executive_data_pdf", gen)
    async def run():
        await seed(database, 1000)
        payload = rp.BatchPDFRequest(types=["executive-data"], data_group_by="eselon5", sort_by="price_asc",
                                     filter={"location": ["Gedung A"]}, detail_fields="spm")
        response = await rp.batch_download_pdf_zip.__wrapped__(
            Request({"type": "http"}), "k1", payload, USER)
        assert gen.await_count == 2
        for i, call in enumerate(gen.call_args_list, 1):
            assert call.kwargs["data_group_by"] == "eselon5"
            assert call.kwargs["sort_by"] == "price_asc"
            assert call.kwargs["detail_fields"] == "spm"
            assert call.kwargs["page"] == i
            assert call.kwargs["_user"] is USER
            assert call.kwargs["filter_aset"].aktif
        raw = await rp._get_pdf_buffer_from_response(response)
        with zipfile.ZipFile(raw) as z:
            assert len(z.namelist()) == 2
            assert not any("GAGAL" in name for name in z.namelist())
    asyncio.run(run())


@pytest.mark.parametrize("mode", ["", "lokasi", "pemegang"], ids=["biasa", "lokasi", "pemegang"])
def test_pdf_nyata_semua_baris_footer_dan_header_aman(database, mode):
    from weasyprint import HTML
    async def run():
        await seed(database)
        # Uji escaping serta nama panjang, bukan Markup dari input pengguna.
        await database.assets.update_many({"location": "Gedung A"}, {"$set": {"location": "Gedung A <b>Bukan HTML</b> " + "Nama lokasi panjang " * 5}})
        return await rp._build_executive_summary_data("k1", data_group_by=mode, sort_by="name_desc")
    data = asyncio.run(run())
    html = rp._jinja_env().get_template("executive_summary_data.html").render(
        chunk_assets=data["assets"], chunk_groups=data["asset_groups"],
        data_group_by=mode, data_group_label=data["data_group_label"],
        global_offset=0, total_chunk=40, total_all=40, satker_name=data["satker_name"],
        total_value_fmt=data["total_value_fmt"], data_page_num=1, total_data_pages=1)
    assert "<b>Bukan HTML</b>" not in html
    # QA mandiri tanpa ketergantungan jaringan Google Fonts.
    html = re.sub(r"@import url\([^;]+;", "", html)
    document = HTML(string=html).render()
    pdf = document.write_pdf()
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(p.extract_text() for p in reader.pages)
    for i in range(40):
        assert text.count(f"Aset Uji {i:04}") == 1
    for page in reader.pages:
        assert "Bagian 1/1" in page.extract_text()
    for page in document.pages:
        # Tiap baris tabel tetap di dalam kotak cetak, tidak menimpa footer.
        for box in page._page_box.descendants():
            if type(box).__name__ == "TableRowBox":
                assert box.position_y + box.height <= page._page_box.position_y + page._page_box.margin_top + page._page_box.height + 1
    if folder := os.environ.get("AMAN_QA_PDF_DIR"):
        out = Path(folder)
        out.mkdir(parents=True, exist_ok=True)
        (out / f"data-aset-{mode or 'biasa'}.pdf").write_bytes(pdf)
