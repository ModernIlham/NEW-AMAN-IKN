"""PENILAIAN — Fase 5 tahap awal: posisi penyusutan aset tetap.

PMK 65/PMK.06/2017 + KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka §5).
Rekap per golongan + daftar telaah (henti susut, tanpa referensi masa
manfaat) dari data aset nyata. Revaluasi & referensi masa manfaat yang
dapat dikelola menyusul sesuai masterplan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from kodefikasi_utils import GOLONGAN_DEFAULTS
from penilaian_utils import (
    MASA_MANFAAT_DEFAULT, rekap_penyusutan, validate_masa_manfaat,
)

penilaian_router = APIRouter()


class MasaManfaatIn(BaseModel):
    kode: str = Field(min_length=5, max_length=5)
    uraian: str = ""
    tahun: int


async def _peta_masa_manfaat():
    """Peta kelompok → tahun: entri satker (DB) menimpa bawaan riset."""
    peta = dict(MASA_MANFAAT_DEFAULT)
    entri = {}
    async for m in db.masa_manfaat.find({}, {"_id": 0}):
        peta[m["kode"]] = int(m["tahun"])
        entri[m["kode"]] = m
    return peta, entri

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "purchase_date": 1, "condition": 1}
_MAKS_BARIS = 500


@penilaian_router.get("/penilaian/masa-manfaat")
async def list_masa_manfaat(_user: dict = Depends(require_user)):
    """Referensi masa manfaat gabungan: entri satker menimpa bawaan riset.

    Bawaan berasal dari riset KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka
    §5); entri satker diinput admin dari lampiran KMK (butir verifikasi
    #11) dan selalu menang.
    """
    _, entri = await _peta_masa_manfaat()
    items = []
    for kode, tahun in sorted(MASA_MANFAAT_DEFAULT.items()):
        if kode not in entri:
            items.append({"kode": kode, "uraian": "", "tahun": tahun,
                          "sumber": "bawaan riset (validasi lampiran KMK)"})
    for m in sorted(entri.values(), key=lambda x: x["kode"]):
        items.append({**m, "sumber": "input satker"})
    items.sort(key=lambda x: x["kode"])
    return {"items": items, "jumlah": len(items)}


@penilaian_router.post("/penilaian/masa-manfaat")
async def upsert_masa_manfaat(payload: MasaManfaatIn,
                              _admin: dict = Depends(require_admin)):
    """Tambah/ubah masa manfaat satu kelompok (admin; menimpa bawaan)."""
    errors = validate_masa_manfaat(payload.kode, payload.tahun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    kode = payload.kode.strip()
    await db.masa_manfaat.update_one(
        {"kode": kode},
        {"$set": {"kode": kode, "uraian": str(payload.uraian or "").strip(),
                  "tahun": int(payload.tahun), "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True, "kode": kode, "tahun": int(payload.tahun)}


@penilaian_router.delete("/penilaian/masa-manfaat/{kode}")
async def hapus_masa_manfaat(kode: str, _admin: dict = Depends(require_admin)):
    """Hapus entri satker (kembali ke bawaan riset bila ada)."""
    res = await db.masa_manfaat.delete_one({"kode": kode.strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404,
                            detail="Entri satker tidak ditemukan (bawaan riset tidak bisa dihapus)")
    return {"ok": True, "kode": kode.strip()}


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
    peta, _ = await _peta_masa_manfaat()
    assets = [a async for a in db.assets.find({}, _PROJ)]
    hasil = rekap_penyusutan(assets, per_tanggal, peta=peta,
                             uraian_golongan=uraian)
    dipangkas = {
        "henti": len(hasil["henti"]) > _MAKS_BARIS,
        "tanpa_referensi": len(hasil["tanpa_referensi"]) > _MAKS_BARIS,
    }
    hasil["henti"] = hasil["henti"][:_MAKS_BARIS]
    hasil["tanpa_referensi"] = hasil["tanpa_referensi"][:_MAKS_BARIS]
    hasil["dipangkas"] = dipangkas
    hasil["per_tanggal"] = per_tanggal
    hasil["referensi_masa_manfaat"] = peta
    hasil["catatan"] = (
        "Garis lurus tanpa residu, semesteran, konvensi semester penuh "
        "(PMK 65/2017); posisi memuat semester yang sudah berakhir. Masa "
        "manfaat per kelompok (KMK 295/2019 jo. 266/2023) — kelompok tanpa "
        "referensi tidak ditebak dan tampil di daftar telaah."
    )
    return hasil
