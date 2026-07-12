"""PERENCANAAN — Fase 4 tahap awal: kandidat RKBMN pemeliharaan.

PMK 153/PMK.06/2021: satker menyusun usulan RKBMN pemeliharaan dari
daftar barang + hasil pemeliharaan. Modul ini menyaring aset yang LAYAK
diusulkan (Baik/Rusak Ringan, dioperasikan) vs yang tidak (rusak berat,
idle, nonaktif) + riwayat biaya pemeliharaan sebagai bahan pertimbangan.
RKBMN pengadaan + sanding SBSK menyusul sesuai masterplan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth_utils import require_user
from db import db
from pemeliharaan_utils import rekap_pemeliharaan
from perencanaan_utils import rekap_rkbmn

perencanaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "condition": 1, "status": 1, "location": 1}
_PROJ_BIAYA = {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
               "asset_name": 1, "tanggal": 1, "jenis": 1, "biaya": 1}
_MAKS_BARIS = 1000  # daftar dipangkas untuk UI; ringkasan tetap utuh


async def _data_rkbmn(tahun: int):
    """Kumpulkan kandidat RKBMN (dipakai endpoint JSON & XLSX)."""
    assets = [a async for a in db.assets.find({}, _PROJ_ASET)]
    records = [r async for r in db.pemeliharaan.find({}, _PROJ_BIAYA)]
    per_aset = rekap_pemeliharaan(records, tahun=tahun)["per_aset"]
    biaya_map = {p["asset_id"]: p for p in per_aset if p.get("asset_id")}
    return rekap_rkbmn(assets, biaya_map)


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan-xlsx")
async def rkbmn_pemeliharaan_xlsx(
    tahun: int = Query(None, ge=2000, le=2100),
    _user: dict = Depends(require_user),
):
    """Kertas kerja usulan RKBMN pemeliharaan (XLSX) — siap diisi satker.

    Sheet "Layak Diusulkan" menambahkan kolom kosong Usulan Pekerjaan &
    Perkiraan Biaya untuk diisi lalu dibawa ke SIMAN; sheet "Tidak Layak"
    memuat alasan + jalur yang benar (jejak keputusan untuk auditor).
    """
    import io as io_module

    import xlsxwriter
    from fastapi.responses import StreamingResponse

    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun)
    buffer = io_module.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    f_judul = wb.add_format({"bold": True})
    f_kepala = wb.add_format({"bold": True, "bg_color": "#DDE6F2", "border": 1})
    f_isi = wb.add_format({"bold": True, "bg_color": "#FFF6DD", "border": 1})
    f_sel = wb.add_format({"border": 1})
    f_angka = wb.add_format({"border": 1, "num_format": "#,##0"})

    s1 = wb.add_worksheet("Layak Diusulkan")
    s1.write(0, 0, f"Kertas kerja usulan RKBMN pemeliharaan TA {tahun + 1} "
                   f"(PMK 153/2021) — riwayat biaya TA {tahun}; kolom kuning diisi satker",
             f_judul)
    kolom1 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status",
              "Lokasi", "Riwayat (x)", "Riwayat Biaya (Rp)"]
    for c, h in enumerate(kolom1):
        s1.write(2, c, h, f_kepala)
    s1.write(2, len(kolom1), "Usulan Pekerjaan", f_isi)
    s1.write(2, len(kolom1) + 1, "Perkiraan Biaya (Rp)", f_isi)
    for i, a in enumerate(hasil["layak"], start=3):
        s1.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s1.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s1.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s1.write(i, 3, str(a.get("condition") or ""), f_sel)
        s1.write(i, 4, str(a.get("status") or ""), f_sel)
        s1.write(i, 5, str(a.get("location") or ""), f_sel)
        s1.write_number(i, 6, a["riwayat_jumlah"], f_angka)
        s1.write_number(i, 7, a["riwayat_biaya"], f_angka)
        s1.write(i, 8, "", f_sel)
        s1.write(i, 9, "", f_angka)
    s1.set_column(0, 0, 14)
    s1.set_column(2, 2, 36)
    s1.set_column(3, 5, 14)
    s1.set_column(6, 7, 14)
    s1.set_column(8, 8, 32)
    s1.set_column(9, 9, 18)

    s2 = wb.add_worksheet("Tidak Layak")
    kolom2 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status", "Alasan / Jalur yang Benar"]
    for c, h in enumerate(kolom2):
        s2.write(0, c, h, f_kepala)
    for i, a in enumerate(hasil["tidak"], start=1):
        s2.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s2.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s2.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s2.write(i, 3, str(a.get("condition") or ""), f_sel)
        s2.write(i, 4, str(a.get("status") or ""), f_sel)
        s2.write(i, 5, a.get("alasan") or "", f_sel)
    s2.set_column(0, 0, 14)
    s2.set_column(2, 2, 36)
    s2.set_column(5, 5, 60)

    wb.close()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="Usulan_RKBMN_Pemeliharaan_TA{tahun + 1}.xlsx"'})


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan")
async def rkbmn_pemeliharaan(
    tahun: int = Query(None, ge=2000, le=2100,
                       description="Tahun anggaran riwayat biaya (default: berjalan)"),
    _user: dict = Depends(require_user),
):
    """Kandidat usulan RKBMN pemeliharaan + riwayat biaya per aset."""
    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun)
    dipangkas = {
        "layak": len(hasil["layak"]) > _MAKS_BARIS,
        "tidak": len(hasil["tidak"]) > _MAKS_BARIS,
    }
    hasil["layak"] = hasil["layak"][:_MAKS_BARIS]
    hasil["tidak"] = hasil["tidak"][:_MAKS_BARIS]
    hasil["tahun"] = tahun
    hasil["dipangkas"] = dipangkas
    hasil["catatan"] = (
        "Kriteria PMK 153/2021: hanya kondisi Baik/Rusak Ringan yang layak "
        "diusulkan; rusak berat = jalur penghapusan; BMN idle = penetapan "
        "status (PMK 120/2024). Riwayat biaya dari modul Pemeliharaan TA "
        f"{tahun}."
    )
    return hasil
