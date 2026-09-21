"""Nilai sama harus sejajar pada geometri PDF, bukan hanya label datanya."""
import asyncio
import os
from pathlib import Path

import pytest
from mongomock_motor import AsyncMongoMockClient
from weasyprint import HTML

import routes.reports as rp
import shared_utils as su


def _kotak(document, kelas):
    return [box for page in document.pages
            for box in page._page_box.descendants(placeholders=True)
            if box.element is not None
            and kelas in (box.element.get("class") or "").split()
            and box.element_tag == "div"
            and type(box).__name__ in ("BlockBox", "FlexBox", "AbsolutePlaceholder")]


async def _data(database, gabungan):
    # Tahun lampau membuat uji tidak bergantung bulan/tahun saat dijalankan.
    for kid in ("k1", "k2"):
        await database.inventory_activities.insert_one({
            "id": kid, "kode_satker": "401234", "nama_satker": "Satker Uji",
            "nama_kegiatan": f"Inventarisasi {kid}", "nomor_surat": f"S-{kid}",
            "tanggal_mulai": "2020-03-01", "created_at": "2020-03-01",
        })
    aset = []
    # Persis hitungan screenshot: total 168/213/244/246, ditemukan 152/152/152/153.
    for bulan, tambahan, temuan in ((3, 1, 1), (5, 35, 35), (6, 132, 116),
                                    (7, 45, 0), (8, 31, 0), (9, 2, 1)):
        for i in range(tambahan):
            aset.append({
                "id": f"a{len(aset)}", "activity_id": "k1",
                "asset_code": "3050105007", "asset_name": "Aset Uji",
                "NUP": str(len(aset) + 1), "condition": "Baik", "status": "Aktif",
                "purchase_price": 1000, "purchase_date": f"2020-{bulan:02}-01",
                "inventory_status": "Ditemukan" if i < temuan else "Belum Diinventarisasi",
                "tanggal_inventarisasi": f"2020-{bulan:02}-02" if i < temuan else "",
            })
    await database.assets.insert_many(aset)
    if gabungan:
        # Irisan kedua menguji bahwa label/komposisi kegiatan tak mengubah rumah.
        await database.assets.update_one({"id": "a0"}, {"$set": {"activity_id": "k2"}})
        return await rp._build_satker_report_v2("k1")
    return await rp._build_executive_summary_data("k1", with_asset_rows=False)


@pytest.mark.parametrize("gabungan", [False, True], ids=["eksekutif", "gabungan"])
def test_nilai_152_juni_juli_agustus_sejajar_di_pdf(monkeypatch, gabungan):
    database = AsyncMongoMockClient()["uji_grafik"]
    monkeypatch.setattr(rp, "db", database)
    monkeypatch.setattr(su, "db", database)
    data = asyncio.run(_data(database, gabungan))
    assert [b["ditemukan"] for b in data["linimasa"][5:8]] == [152, 152, 152]
    nama = "laporan_satker_v2" if gabungan else "executive_summary"
    html = rp._jinja_env().get_template(f"{nama}.html").render(
        **{**data, "preview": False, "asset_pages": [], "assets": []})
    document = HTML(string=html).render()
    folder_qa = os.environ.get("AMAN_QA_PDF_DIR")
    if folder_qa:
        out = Path(folder_qa)
        out.mkdir(parents=True, exist_ok=True)
        document.write_pdf(out / f"{nama}.pdf")
    # Januari/Februari kosong: batang hijau ke-4/5/6 = Juni/Juli/Agustus.
    batang = _kotak(document, "lm-temu")
    juni, juli, agustus = batang[3:6]
    assert juli.position_y == pytest.approx(juni.position_y, abs=0.01)
    assert agustus.position_y == pytest.approx(juni.position_y, abs=0.01)
    assert juli.height == pytest.approx(juni.height, abs=0.01)
    assert agustus.height == pytest.approx(juni.height, abs=0.01)
    # Kenaikan satu unit pada September tetap terlihat, tanpa pembulatan persen.
    assert batang[6].height > agustus.height
    assert batang[0].height > 0  # Maret hanya satu unit, tidak lenyap.
    rumah = _kotak(document, "lm-rumah")
    if gabungan:
        separuh = len(rumah) // 2
        assert separuh == 10
        for utama, per_kegiatan in zip(rumah[:separuh], rumah[separuh:]):
            assert per_kegiatan.height == pytest.approx(utama.height, abs=0.01)
