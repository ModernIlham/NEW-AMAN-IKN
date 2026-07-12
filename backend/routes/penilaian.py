"""PENILAIAN — Fase 5 tahap awal: posisi penyusutan aset tetap.

PMK 65/PMK.06/2017 + KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka §5).
Rekap per golongan + daftar telaah (henti susut, tanpa referensi masa
manfaat) dari data aset nyata. Revaluasi & referensi masa manfaat yang
dapat dikelola menyusul sesuai masterplan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth_utils import require_user
from db import db
from kodefikasi_utils import GOLONGAN_DEFAULTS
from penilaian_utils import MASA_MANFAAT_DEFAULT, rekap_penyusutan

penilaian_router = APIRouter()

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "purchase_date": 1, "condition": 1}
_MAKS_BARIS = 500


@penilaian_router.get("/penilaian/penyusutan")
async def posisi_penyusutan(
    per_tanggal: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Posisi penyusutan per golongan + daftar telaah (per tanggal)."""
    if not per_tanggal:
        per_tanggal = datetime.now(timezone.utc).date().isoformat()
    uraian = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian[k["kode"]] = k["uraian"]
    assets = [a async for a in db.assets.find({}, _PROJ)]
    hasil = rekap_penyusutan(assets, per_tanggal, uraian_golongan=uraian)
    dipangkas = {
        "henti": len(hasil["henti"]) > _MAKS_BARIS,
        "tanpa_referensi": len(hasil["tanpa_referensi"]) > _MAKS_BARIS,
    }
    hasil["henti"] = hasil["henti"][:_MAKS_BARIS]
    hasil["tanpa_referensi"] = hasil["tanpa_referensi"][:_MAKS_BARIS]
    hasil["dipangkas"] = dipangkas
    hasil["per_tanggal"] = per_tanggal
    hasil["referensi_masa_manfaat"] = MASA_MANFAAT_DEFAULT
    hasil["catatan"] = (
        "Garis lurus tanpa residu, semesteran, konvensi semester penuh "
        "(PMK 65/2017); posisi memuat semester yang sudah berakhir. Masa "
        "manfaat per kelompok (KMK 295/2019 jo. 266/2023) — kelompok tanpa "
        "referensi tidak ditebak dan tampil di daftar telaah."
    )
    return hasil
