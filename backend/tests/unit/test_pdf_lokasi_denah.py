"""Render templat produksi: kategori luar denah tampil pada PDF, bukan hanya data."""
import asyncio
import io
import os
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient
from pypdf import PdfReader
from weasyprint import HTML

import routes.reports as rp
import shared_utils as su
from test_laporan_eksekutif_kategori_jenjang import _seed, _seed_denah


@pytest.mark.parametrize("dengan_denah", [True, False])
def test_kategori_luar_dan_belum_tercetak_terpisah(monkeypatch, dengan_denah):
    database = AsyncMongoMockClient()["uji_pdf_lokasi"]
    monkeypatch.setattr(rp, "db", database)
    monkeypatch.setattr(su, "db", database)

    async def data_laporan():
        await _seed(database, barang=[("3050104001", "HT", 2)])
        if dengan_denah:
            await _seed_denah(database)
        await database.assets.insert_one({
            "id": "luar", "activity_id": "k1", "asset_name": "Aset Uji Luar",
            "asset_code": "3050104001", "purchase_price": 750,
            "location": "Lapangan sisi timur", "lokasi_spasial": {"titik": [116.9, -1.5]},
        })
        return await rp._build_executive_summary_data("k1", with_asset_rows=False)

    data = asyncio.run(data_laporan())
    html = rp._jinja_env().get_template("executive_summary.html").render(
        **{**data, "preview": False, "asset_pages": [], "assets": []})
    pdf = HTML(string=html).write_pdf()
    reader = PdfReader(io.BytesIO(pdf))
    lokasi_pages = [i for i, page in enumerate(reader.pages)
                    if "Di luar kawasan terpetakan" in " ".join(page.extract_text().split())]
    assert lokasi_pages, "Kategori luar kawasan hilang pada PDF"
    teks = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
    assert "(belum ditempatkan di denah)" in teks
    assert "Lapangan sisi timur" in teks
    # Opsional: simpan hasil QA lokal; CI cukup merender/memeriksa di memori.
    folder_qa = os.environ.get("AMAN_QA_PDF_DIR")
    if folder_qa:
        out = Path(folder_qa)
        out.mkdir(parents=True, exist_ok=True)
        nama = "lokasi-campuran" if dengan_denah else "lokasi-tanpa-node"
        (out / f"{nama}.pdf").write_bytes(pdf)
        print(f"QA {nama}: halaman lokasi {[i + 1 for i in lokasi_pages]}")
