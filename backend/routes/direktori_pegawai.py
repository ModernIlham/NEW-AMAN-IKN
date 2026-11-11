"""Direktori gabungan pegawai — hanya baca (PGW-06; kontrak 6.5).

Satu pintu untuk pemilih lintas modul: internal (ter-scope satker pemanggil,
persis `GET /pegawai`) atau orang luar (direktori bersama, hanya yang aktif),
dicari dan dipotong halamannya di server.
"""
import re
from functools import partial
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth_utils import require_user
from db import db
from kartu_utils import hash_kandidat, valid_uid
from shared_utils import (kode_satker_user, limiter, log_audit,
                          scope_query_field_satker)
import direktori_pegawai as dp
import organisasi_luar_utils as olu

direktori_pegawai_router = APIRouter()

KELOMPOK_DIREKTORI = ("internal", *olu.KELOMPOK_LUAR)


class NomorIn(BaseModel):
    nomor: List[str] = Field(default_factory=list)


class KartuDirektoriIn(BaseModel):
    uid: str = Field(min_length=1, max_length=64)


def _ringkas(doc: dict, luar: bool) -> dict:
    d = dp.tandai_luar(doc) if luar else dp.tandai_internal(doc)
    if not str(d.get("unit_kerja") or "").strip():
        from pegawai_utils import unit_kerja_terdalam
        d["unit_kerja"] = unit_kerja_terdalam(d)
    for k in ("jenis_instansi", "instansi_nama", "provinsi_nama",
              "satker_luar_nama", "kapasitas_bertindak"):
        d.setdefault(k, "")
    for k in ("eselon1", "eselon2", "eselon3", "eselon4", "eselon5"):
        d.pop(k, None)
    return d


@direktori_pegawai_router.get("/direktori-pegawai")
async def daftar_direktori_pegawai(kelompok: str = "", tataran: str = "", q: str = "",
                                   instansi_id: str = "", satker_luar_id: str = "",
                                   provinsi_id: str = "", page: int = 1,
                                   page_size: int = 30,
                                   user: dict = Depends(require_user)):
    if kelompok not in KELOMPOK_DIREKTORI:
        raise HTTPException(status_code=400, detail=(
            "Pilih kelompok: internal, eksternal, atau pihak_ketiga"))
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 30)), 100)
    pola = {"$regex": re.escape(q.strip()), "$options": "i"} if q.strip() else None
    if kelompok == "internal":
        query = {}
        if pola:
            query["$or"] = [{"nama": pola}, {"nip": pola}, {"jabatan": pola}]
        query = scope_query_field_satker(user, query)
        koleksi, proj, luar = db.pegawai, dp.PROYEKSI_RINGKAS, False
    else:
        query = {"kelompok": kelompok, "status": {"$in": dp.STATUS_AKTIF_LUAR}}
        if tataran and kelompok == "eksternal":
            query["tataran"] = tataran
        for k, v in (("instansi_id", instansi_id), ("satker_luar_id", satker_luar_id),
                     ("provinsi_id", provinsi_id)):
            if v:
                query[k] = v
        if pola:
            query["$or"] = [{"nama": pola}, {"nip": pola}, {"jabatan": pola},
                            {"instansi_nama": pola}]
        koleksi, proj, luar = db.pegawai_luar, dp.PROYEKSI_RINGKAS_LUAR, True
    total = await koleksi.count_documents(query)
    items = await koleksi.find(query, proj).sort("nama", 1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    return {"items": [_ringkas(i, luar) for i in items], "total": total,
            "page": page, "page_size": page_size}


@direktori_pegawai_router.post("/direktori-pegawai/kelompok")
@limiter.limit("60/minute")
async def kelompok_direktori_pegawai(request: Request, payload: NomorIn,
                                     user: dict = Depends(require_user)):
    """{nomor: kunci_ikon} hanya untuk nomor yang ditanyakan DAN dikenal."""
    if len(payload.nomor) > dp.BATAS_NOMOR:
        raise HTTPException(status_code=400, detail=(
            f"Maksimal {dp.BATAS_NOMOR} nomor per permintaan"))
    peta = await dp.kelompok_nomor(partial(scope_query_field_satker, user), payload.nomor)
    return {"nomor": peta}


@direktori_pegawai_router.post("/direktori-pegawai/kartu/identifikasi")
@limiter.limit("30/minute")
async def identifikasi_kartu_direktori(request: Request, payload: KartuDirektoriIn,
                                       user: dict = Depends(require_user)):
    """Tap kartu → orangnya: Master Pegawai satker pemanggil dulu, lalu orang
    luar. Kartu tak dikenal dicatat ke audit tanpa UID mentah."""
    err = valid_uid(payload.uid)
    if err:
        raise HTTPException(status_code=400, detail=err)
    hashes = hash_kandidat(payload.uid)
    peg = await db.pegawai.find_one(
        scope_query_field_satker(user, {"kartu_uid_hashes": {"$in": hashes}}),
        dp.PROYEKSI_RINGKAS)
    if peg:
        return {"pegawai": _ringkas(peg, False)}
    luar = await db.pegawai_luar.find_one(
        {"kartu_uid_hashes": {"$in": hashes}}, dp.PROYEKSI_RINGKAS_LUAR)
    if luar:
        return {"pegawai": _ringkas(luar, True)}
    await log_audit("kartu_tak_dikenal", "", "",
                    username=user.get("username", "system"),
                    detail=f"Tap kartu tidak dikenal (hash {hashes[0][:8]}…)",
                    kode_satker=kode_satker_user(user))
    raise HTTPException(status_code=404, detail=(
        "Kartu tidak dikenal — daftarkan dulu di Master Pegawai"))
