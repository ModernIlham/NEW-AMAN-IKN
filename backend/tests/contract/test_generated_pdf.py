"""pypdf only rewrites newly generated reports, never uploaded originals."""
import hashlib
import io
import re
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def seed(contract, count=2):
    activity = "pdf-migration-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a",
        "nama_kegiatan": "Kontrak migrasi PDF", "created_at": "2026-10-15", "status_pengesahan": "draft"})
    await contract.db.assets.insert_many([{
        "id": f"{activity}-{index}", "activity_id": activity, "asset_code": "3050104001", "NUP": str(index),
        "asset_name": f"Barang migrasi {index}", "purchase_price": "1234", "purchase_date": "2020-01-01",
        "inventory_status": "Ditemukan", "condition": "Baik", "category": "Peralatan",
        "location": "Ruang uji", "status": "Aktif", "stiker_status": "Sudah Terpasang",
    } for index in range(1, count + 1)])
    return activity


def read_pdf(data):
    from pypdf import PdfReader
    assert data.startswith(b"%PDF-")
    return PdfReader(io.BytesIO(data), strict=True)


def fonts(page):
    resources = page.get("/Resources")
    assert resources is not None
    return {font.get_object().get("/BaseFont") for font in resources.get_object().get("/Font", {}).values()}


def check_rendered_pages(data, indexes):
    import pypdfium2
    with pypdfium2.PdfDocument(data) as document:
        for index in indexes:
            page = document[index]
            bitmap = page.render(scale=.35)
            try:
                image = bitmap.to_pil()
                assert image.width > 100 and image.height > 100
                assert any(low < high for low, high in image.convert("RGB").getextrema())
            finally:
                bitmap.close()
                page.close()


async def test_inventory_overlay_retains_pages_fonts_metadata_and_original_upload(contract):
    activity = await seed(contract, count=40)
    # ByteRange-like test bytes are an immutable upload fixture, not a claim
    # that the generated test PDF has a cryptographic signature.
    original = b"%PDF-1.7\nOriginal signed attachment /ByteRange [0 1 2 3]\n%%EOF"
    original_hash = hashlib.sha256(original).hexdigest()
    gid = await contract.fs.upload_from_stream("original.pdf", original, metadata={"content_type": "application/pdf"})
    aid = f"{activity}-1"
    await contract.db.assets.update_one({"id": aid}, {"$set": {"bast_file_id": str(gid), "bast_file_name": "original.pdf"}})
    response = await contract.http.get("/api/export/pdf", params={"activity_id": activity}, headers=contract.headers["a"])
    assert response.status_code == 200, response.text[:200]
    reader = read_pdf(response.content)
    assert len(reader.pages) >= 2
    assert reader.metadata.producer and "ReportLab" in reader.metadata.producer
    assert reader.metadata.title and "/Author" in reader.metadata
    assert reader.metadata.creation_date is not None
    for index, page in enumerate(reader.pages, 1):
        assert float(page.mediabox.width) > float(page.mediabox.height)
        assert f"Halaman {index} dari {len(reader.pages)}" in page.extract_text()
        assert any("Helvetica" in font for font in fonts(page))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "Barang migrasi 1" in text and "Barang migrasi 2" in text
    assert text.index("Barang migrasi 1") < text.index("Barang migrasi 2")
    check_rendered_pages(response.content, [0, len(reader.pages) - 1])
    stream = await contract.fs.open_download_stream(gid)
    assert hashlib.sha256(await stream.read()).hexdigest() == original_hash
    served = await contract.http.get(f"/api/assets/{aid}/bast", headers=contract.headers["a"])
    assert served.status_code == 200 and served.content == original
    foreign = await contract.http.get("/api/export/pdf", params={"activity_id": activity}, headers=contract.headers["b"])
    assert foreign.status_code == 403


async def test_lhi_append_preserves_every_real_section_page_order_and_fonts(contract):
    import routes.reports as reports
    activity_id = await seed(contract)
    activity = await contract.db.inventory_activities.find_one({"id": activity_id}, {"_id": 0})
    settings = await reports.pengaturan_kop(activity)
    cover = await reports._generate_cover_page(activity, settings)
    expected = [read_pdf(cover.getvalue())]
    sections = [
        (reports.generate_bahi_pdf, {}), (reports.generate_rhi_pdf, {}),
        *[(reports.generate_dbhi_pdf, {"dbhi_type": kind}) for kind in (
            "kondisi-baik", "kondisi-rusak-ringan", "kondisi-rusak-berat", "berlebih", "tidak-ditemukan", "sengketa")],
        (reports.generate_dbkp_pdf, {}), (reports.generate_sp_hasil_pdf, {}), (reports.generate_sp_pelaksanaan_pdf, {}),
    ]
    for builder, kwargs in sections:
        section = await builder(activity_id=activity_id, _user=contract.users["a"], **kwargs)
        stream = await reports._get_pdf_buffer_from_response(section)
        expected.append(read_pdf(stream.getvalue()))
    response = await contract.http.get(f"/api/inventory-activities/{activity_id}/lhi-pdf", headers=contract.headers["a"])
    assert response.status_code == 200, response.text[:300]
    merged = read_pdf(response.content)
    expected_pages = [page for section in expected for page in section.pages]
    assert len(merged.pages) == len(expected_pages) >= 12
    assert merged.metadata.title == "Laporan Hasil Inventarisasi BMN" and merged.metadata.creator == "AMAN IKN"
    assert "pypdf" in merged.metadata.producer.lower()
    for actual, source in zip(merged.pages, expected_pages):
        normalize = lambda text: re.sub(r"\s+", " ", text).strip()
        assert normalize(actual.extract_text()) == normalize(source.extract_text())
        assert tuple(actual.mediabox) == tuple(source.mediabox)
        assert fonts(actual) == fonts(source)
    check_rendered_pages(response.content, [0, len(merged.pages) // 2, len(merged.pages) - 1])
    foreign = await contract.http.get(f"/api/inventory-activities/{activity_id}/lhi-pdf", headers=contract.headers["b"])
    assert foreign.status_code == 403
