"""Real report previews/PDFs embed Inter without remote font requests."""

import asyncio
import io
import json
from pathlib import Path
import sys
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


async def test_inter_embeds_when_host_inter_and_http_fonts_are_unavailable():
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(Path(__file__).with_name("_font_probe.py")),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(30):
            stdout, stderr = await process.communicate()
        assert process.returncode == 0, stderr.decode()[-2000:]
        proof = json.loads(stdout)
        assert proof["http_font_requests"] == 0
        assert proof["pages"] == 1
        assert proof["layout_equal_to_pinned_file"] is True
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def test_four_real_report_templates_embed_the_same_offline_font(contract, monkeypatch):
    import weasyprint
    from pypdf import PdfReader
    from report_fonts import report_font_css
    from weasyprint.urls import URLFetcher

    attempted_http = []
    captured_html = []
    original_html = weasyprint.HTML

    class OfflineFetcher(URLFetcher):
        def fetch(self, url, *args, **kwargs):
            if url.startswith(("http://", "https://")):
                attempted_http.append(url)
                raise AssertionError("Report proof denies HTTP resources")
            return super().fetch(url, *args, **kwargs)

    class OfflineHTML(original_html):
        def __init__(self, *args, **kwargs):
            captured_html.append(kwargs.get("string", ""))
            kwargs["url_fetcher"] = OfflineFetcher()
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(weasyprint, "HTML", OfflineHTML)
    suffix = uuid.uuid4().hex
    activity = "font-" + suffix
    code = "font-satker-" + suffix
    await contract.db.satker.insert_one({"kode_satker": code, "nama_satker": "Laporan font lokal"})
    await contract.db.inventory_activities.insert_one({
        "id": activity, "kode_satker": code, "nama_kegiatan": "Font <uji> lokal",
        "created_at": "2026-10-15", "status_pengesahan": "draft",
    })
    await contract.db.assets.insert_one({
        "id": activity + "-asset", "activity_id": activity, "asset_code": "3100102001",
        "NUP": "1", "asset_name": "Laptop Inter", "category": "Peralatan dan Mesin",
        "purchase_price": "15000000", "condition": "Baik", "inventory_status": "Ditemukan",
        "stiker_status": "Sudah Terpasang", "purchase_date": "2024-01-01",
    })
    try:
        for endpoint in ("executive-summary-html", "executive-grouped-html", "laporan-satker-html"):
            response = await contract.http.get(f"/api/inventory-activities/{activity}/{endpoint}",
                                               headers=contract.headers["root"])
            assert response.status_code == 200, response.text[:500]
            assert str(report_font_css()) in response.text
            assert "fonts.googleapis.com" not in response.text
            assert "fonts.gstatic.com" not in response.text
            assert "file://" not in response.text
        for endpoint in ("executive-summary-pdf", "executive-data-pdf",
                         "executive-grouped-pdf", "laporan-satker-pdf"):
            response = await contract.http.get(f"/api/inventory-activities/{activity}/{endpoint}",
                                               headers=contract.headers["root"])
            assert response.status_code == 200, response.text[:500]
            document = PdfReader(io.BytesIO(response.content))
            inter_fonts = []
            for page in document.pages:
                width, height = float(page.mediabox.width), float(page.mediabox.height)
                assert sorted((width, height)) == pytest.approx((595.2756, 841.8898), abs=0.1)
                if endpoint in ("executive-data-pdf", "executive-grouped-pdf"):
                    assert width > height
                elif endpoint == "laporan-satker-pdf":
                    assert height > width
                for reference in page["/Resources"].get("/Font", {}).values():
                    font = reference.get_object()
                    if "Inter" in str(font.get("/BaseFont", "")):
                        descendant = font["/DescendantFonts"][0].get_object()
                        descriptor = descendant["/FontDescriptor"].get_object()
                        stream = descriptor.get("/FontFile2") or descriptor.get("/FontFile3")
                        assert stream and stream.get_object().get_data()
                        inter_fonts.append(str(font["/BaseFont"]))
            assert inter_fonts, endpoint
        assert len(captured_html) == 4
        assert all(str(report_font_css()) in html for html in captured_html)
        assert attempted_http == []
    finally:
        await contract.db.assets.delete_many({"activity_id": activity})
        await contract.db.inventory_activities.delete_one({"id": activity})
        await contract.db.satker.delete_one({"kode_satker": code})
