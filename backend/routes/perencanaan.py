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


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan")
async def rkbmn_pemeliharaan(
    tahun: int = Query(None, ge=2000, le=2100,
                       description="Tahun anggaran riwayat biaya (default: berjalan)"),
    _user: dict = Depends(require_user),
):
    """Kandidat usulan RKBMN pemeliharaan + riwayat biaya per aset."""
    if not tahun:
        tahun = datetime.now(timezone.utc).year
    assets = [a async for a in db.assets.find({}, _PROJ_ASET)]
    records = [r async for r in db.pemeliharaan.find({}, _PROJ_BIAYA)]
    per_aset = rekap_pemeliharaan(records, tahun=tahun)["per_aset"]
    biaya_map = {p["asset_id"]: p for p in per_aset if p.get("asset_id")}
    hasil = rekap_rkbmn(assets, biaya_map)
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
