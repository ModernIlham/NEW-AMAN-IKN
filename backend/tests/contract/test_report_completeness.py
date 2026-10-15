"""Real HTTP/Mongo/rendering never present bounded report subsets as complete."""
import io
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="session")]


@pytest.mark.parametrize("count", [2, 3, 4])
async def test_report_limit_minus_one_exact_and_overflow(contract, monkeypatch, count):
    import report_read_limits
    monkeypatch.setattr(report_read_limits, "MAX_REPORT_ROWS", 3)
    activity = "opt15-" + uuid.uuid4().hex
    await contract.db.inventory_activities.insert_one({"id": activity, "kode_satker": "99000a",
        "nama_kegiatan": "Laporan batas sintetis", "created_at": "2026-10-15", "status_pengesahan": "draft"})
    await contract.db.assets.insert_many([{"id": f"{activity}-{i}", "activity_id": activity,
        "asset_code": "3100102001", "NUP": str(i), "asset_name": f"Barang lengkap {i}",
        "purchase_price": "10", "condition": "Baik", "inventory_status": "Ditemukan",
        "stiker_status": "Sudah Terpasang", "purchase_date": "2020-01-01"} for i in range(count)])
    for endpoint in ("rekapitulasi", "rhi-pdf", "executive-summary-html"):
        response = await contract.http.get(f"/api/inventory-activities/{activity}/{endpoint}", headers=contract.headers["a"])
        if count > 3:
            assert response.status_code == 413, response.text[:500]
            assert "tidak terpotong" in response.json()["detail"]
            assert "CSV" in response.json()["detail"]
        else:
            assert response.status_code == 200, response.text[:500]
            if endpoint == "rhi-pdf":
                assert response.content.startswith(b"%PDF")
                from pypdf import PdfReader
                text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
                assert "Rekapitulasi" in text or "REKAPITULASI" in text
            elif endpoint == "executive-summary-html":
                assert "<html" in response.text.lower()

    if count > 3:
        batch = await contract.http.post(f"/api/inventory-activities/{activity}/batch-pdf-zip",
            headers=contract.headers["a"], json={"types": ["rhi", "executive-summary"]})
        assert batch.status_code == 413, batch.text[:500]
