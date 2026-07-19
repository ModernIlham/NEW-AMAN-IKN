"""Referensi Akun Neraca (BAS) per golongan BMN — merged default + override satker.

Semua user login melihat pemetaan golongan → akun neraca; admin menimpa per
golongan dari Lampiran BAS (default riset ditandai perlu-verifikasi). Pola sama
dengan referensi masa manfaat (#107).
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from akun_bas_utils import AKUN_NERACA_DEFAULT, validate_akun_bas

akun_bas_router = APIRouter()


class AkunBasIn(BaseModel):
    golongan: str
    akun: str
    uraian: str = ""


async def _peta_akun():
    """Peta golongan → {akun, uraian}: entri satker (DB) menimpa default riset."""
    peta = {g: dict(v) for g, v in AKUN_NERACA_DEFAULT.items()}
    entri = {}
    async for m in db.akun_bas.find({}, {"_id": 0}):
        peta[m["golongan"]] = {"akun": m.get("akun", ""), "uraian": m.get("uraian", "")}
        entri[m["golongan"]] = m
    return peta, entri


@akun_bas_router.get("/akun-bas")
async def list_akun_bas(_user: dict = Depends(require_user)):
    """Pemetaan golongan → akun neraca (default riset ditimpa entri satker).

    Tiap golongan DITAUTKAN ke master aset: jumlah NUP & total nilai buku
    (nilai wajar revaluasi bila ada) aset aktif ter-scope satker — sehingga
    referensi akun langsung memperlihatkan isi master yang memakainya.
    """
    from pembukuan_utils import golongan_of, nilai_buku_aset
    from report_filters import active_asset_filter
    from shared_utils import (filter_aset_perhitungan,
                              scope_query_aset)

    _, entri = await _peta_akun()
    # Rekap master aset per golongan (scoped satker, aset aktif saja)
    rekap = {}
    async for a in db.assets.find(
            await filter_aset_perhitungan(
                await scope_query_aset(_user, active_asset_filter())),
            {"_id": 0, "asset_code": 1, "purchase_price": 1,
             "nilai_wajar_terakhir": 1}):
        g = golongan_of(a.get("asset_code")) or "?"
        r = rekap.setdefault(g, {"jumlah": 0, "nilai": 0.0})
        r["jumlah"] += 1
        r["nilai"] += nilai_buku_aset(a)
    items = []
    for g in sorted(AKUN_NERACA_DEFAULT):
        if g in entri:
            m = entri[g]
            row = {"golongan": g, "akun": m.get("akun", ""),
                   "uraian": m.get("uraian", ""), "sumber": "input satker"}
        else:
            d = AKUN_NERACA_DEFAULT[g]
            row = {"golongan": g, "akun": d["akun"], "uraian": d["uraian"],
                   "sumber": "default riset (verifikasi Lampiran BAS)"}
        r = rekap.get(g, {"jumlah": 0, "nilai": 0.0})
        row["jumlah_aset"] = r["jumlah"]
        row["nilai_aset"] = round(r["nilai"], 2)
        items.append(row)
    tanpa_gol = {g: r for g, r in rekap.items() if g not in AKUN_NERACA_DEFAULT}
    return {"items": items, "jumlah": len(items),
            "total_aset": sum(r["jumlah"] for r in rekap.values()),
            "aset_tanpa_golongan": sum(r["jumlah"] for r in tanpa_gol.values())}


@akun_bas_router.post("/akun-bas")
async def upsert_akun_bas(payload: AkunBasIn, _admin: dict = Depends(require_admin)):
    """Tambah/ubah akun neraca satu golongan (admin; menimpa default)."""
    errors = validate_akun_bas(payload.golongan, payload.akun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    g = payload.golongan.strip()
    await db.akun_bas.update_one(
        {"golongan": g},
        {"$set": {"golongan": g, "akun": payload.akun.strip(),
                  "uraian": str(payload.uraian or "").strip(), "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True, "golongan": g, "akun": payload.akun.strip()}


@akun_bas_router.delete("/akun-bas/{golongan}")
async def hapus_akun_bas(golongan: str, _admin: dict = Depends(require_admin)):
    """Hapus entri satker (kembali ke default riset)."""
    res = await db.akun_bas.delete_one({"golongan": golongan.strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404,
                            detail="Entri satker tidak ditemukan (default riset tidak bisa dihapus)")
    return {"ok": True, "golongan": golongan.strip()}
