"""WASDAL — dasbor pemantauan tingkat KPB (PMK 207/PMK.06/2021, pustaka §8).

Mesin aturan ringan atas register yang sudah ada (aset, pemanfaatan,
usulan penghapusan, pemindahtanganan, pemeliharaan) → temuan per lima
objek pemantauan. Bahan pra-isi laporan wasdal semesteran; kanal resmi
pelaporan tetap Modul Wasdal SIMAN v2. Register penertiban (timer 15 hari
kerja) & BA pemantauan insidentil menyusul sesuai masterplan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth_utils import require_user
from db import db
from wasdal_utils import (
    AMBANG_BERLARUT_HARI, JENIS_TEMUAN, OBJEK_WASDAL,
    periode_wasdal, rekap_wasdal, susun_temuan,
)

wasdal_router = APIRouter()

# Proyeksi hemat aset: hanya field yang dibaca mesin aturan.
_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "user": 1, "bast_file_id": 1, "condition": 1,
              "purchase_price": 1, "koordinat_latitude": 1,
              "koordinat_longitude": 1, "inventory_status": 1,
              "nomor_perkara": 1, "pihak_bersengketa": 1}

# Jumlah maksimal temuan yang dikirim per objek (rekap tetap utuh).
_MAKS_TAMPIL = 100


@wasdal_router.get("/wasdal/pemantauan")
async def pemantauan_wasdal(
    ambang_hari: int = Query(AMBANG_BERLARUT_HARI, ge=1, le=730),
    _user: dict = Depends(require_user),
):
    """Temuan pemantauan per objek wasdal + rekap + periode berjalan."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    periode = periode_wasdal(today_iso)
    tahun = periode["tahun"]

    assets = [a async for a in db.assets.find({}, _PROJ_ASET)]
    pemanfaatan = [p async for p in db.pemanfaatan.find(
        {}, {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "asset_name": 1,
             "berakhir": 1, "nomor_persetujuan": 1, "nomor_perjanjian": 1,
             "ntpn": 1})]
    usulan_hapus = [u async for u in db.usulan_penghapusan.find(
        {"status": {"$in": ["diusulkan", "diproses"]}},
        {"_id": 0, "id": 1, "asset_id": 1, "asset_name": 1, "status": 1,
         "created_at": 1})]
    usulan_pt = [u async for u in db.pemindahtanganan.find(
        {"status": "disetujui"},
        {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "status": 1,
         "tanggal_persetujuan": 1})]
    pemeliharaan = [r async for r in db.pemeliharaan.find(
        {"tanggal": {"$gte": f"{tahun}-01-01", "$lte": f"{tahun}-12-31"}},
        {"_id": 0, "asset_id": 1, "tanggal": 1})]

    per_objek = susun_temuan(assets, pemanfaatan, usulan_hapus, usulan_pt,
                             pemeliharaan, today_iso, ambang_hari)
    rekap = rekap_wasdal(per_objek)
    return {
        "periode": periode,
        "rekap": rekap,
        "temuan": {k: v[:_MAKS_TAMPIL] for k, v in per_objek.items()},
        "terpotong": {k: max(0, len(v) - _MAKS_TAMPIL)
                      for k, v in per_objek.items()},
        "label_objek": OBJEK_WASDAL,
        "label_jenis": JENIS_TEMUAN,
        "ambang_hari": ambang_hari,
        "total_aset": len(assets),
    }
