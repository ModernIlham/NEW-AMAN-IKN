"""LAPISAN EKSISTING peta: citra (foto udara) dan gambar (titik/garis/area).

Validasi murni ada di `peta_lapisan_utils.py`.

SENGAJA BERSAMA untuk dibaca. Citra dan gambar kondisi lapangan adalah rekaman
GEOGRAFIS: satu foto udara kawasan benar bagi semua satker yang asetnya ada di
sana, sama sifatnya dengan peta dasar OSM. Daftar lapisan aktif TIDAK di-scope
satker.

PENULISAN tetap dijaga ketat: lapisan distempel `kode_satker` pembuatnya dan
hanya boleh diubah/dihapus admin satker itu atau super-admin. Lapisan buatan
super-admin (kode kosong) tak bisa diubah admin satker — ia tampil di peta
SEMUA satker. Urutan tampil boleh diatur admin mana pun (kosmetik, diaudit).

UBIN CITRA dipotong di peramban admin (bukan di server 2 vCPU tanpa GDAL) lalu
diunggah per batch. Ubin disimpan DI LUAR folder `uploads/` karena folder itu
ikut dibackup utuh dan DIHAPUS saat restore — citra bisa berukuran gigabyte.
Ubin disajikan endpoint ber-token HMAC (tanpa kueri DB per ubin) dengan cache
peramban jangka panjang.
"""
import asyncio
import os
import secrets
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from peta_lapisan_utils import (
    FORMAT_UBIN, JENIS, UBIN_MAKS_PER_LAPISAN, UKURAN_UBIN_MAKS, bentuk_publik,
    id_lapisan_sah, isi_cocok_format, jumlah_ubin, nama_berkas_ubin,
    normalisasi_citra_baru, normalisasi_citra_ubah, normalisasi_gambar,
    token_ubin, token_ubin_sah, ubin_dalam_batas,
)
from shared_utils import kode_satker_user, log_audit

peta_lapisan_router = APIRouter()

BATAS_DAFTAR = 200
UBIN_PER_BATCH_MAKS = 200
SISA_DISK_MIN = 3 * 1024 ** 3           # tolak unggahan bila disk tersisa < 3 GB

# Rahasia token ubin. JWT_SECRET bila ada; tanpa itu rahasia acak per proses
# (token berlaku sampai proses dimulai ulang — cukup untuk dev/uji).
_RAHASIA_UBIN = os.environ.get("JWT_SECRET") or secrets.token_hex(32)


def akar_ubin() -> Path:
    return Path(os.environ.get("AMAN_UBIN_DIR")
                or Path(__file__).resolve().parent.parent / "data_ubin")


def _folder_lapisan(lapisan_id: str) -> Path:
    if not id_lapisan_sah(lapisan_id):
        raise HTTPException(status_code=400, detail="Id lapisan tidak sah")
    return akar_ubin() / lapisan_id


def _hari_ini() -> int:
    return int(time.time() // 86400)


class LapisanIn(BaseModel):
    jenis: str = "gambar"
    nama: str = ""
    sumber: Optional[str] = ""
    tanggal_rekam: Optional[str] = ""
    batas: Optional[dict] = None
    zoom_min: Optional[int] = None
    zoom_maks: Optional[int] = None
    format: Optional[str] = ""
    opasitas: Optional[float] = None
    crs_asal: Optional[str] = ""
    aktif: Optional[bool] = True
    fitur: Optional[list] = None
    label_zoom_min: Optional[int] = None
    version: Optional[int] = None   # OCC: wajib saat mengubah


class UrutanIn(BaseModel):
    ids: List[str]


def _boleh_ubah(user: dict, dok: dict) -> bool:
    kode = kode_satker_user(user)
    return not kode or str(dok.get("kode_satker") or "").strip() == kode


def _pastikan_boleh_ubah(user: dict, dok: dict) -> None:
    if not _boleh_ubah(user, dok):
        pemilik = str(dok.get("kode_satker") or "").strip() or "pusat"
        raise HTTPException(
            status_code=403,
            detail=f"Lapisan ini dikelola satker {pemilik} — hanya admin satker "
                   f"tersebut atau super-admin yang dapat mengubahnya")


async def _ambil(lapisan_id: str) -> dict:
    dok = await db.peta_lapisan.find_one({"id": lapisan_id, "jenis": {"$in": list(JENIS)}},
                                         {"_id": 0})
    if not dok:
        raise HTTPException(status_code=404, detail="Lapisan tidak ditemukan")
    return dok


def _tolak(galat: list) -> None:
    if galat:
        raise HTTPException(status_code=400, detail="; ".join(galat[:8]))


@peta_lapisan_router.get("/peta-lapisan")
async def daftar_lapisan(user: dict = Depends(require_user)):
    """Pengguna biasa: lapisan aktif yang siap. Admin: semua, plus pengelola
    dan hak ubahnya. `ubin_token` dipakai peta untuk memuat ubin citra."""
    admin = user.get("role") == "admin"
    q = {"jenis": {"$in": list(JENIS)}}
    if not admin:
        q.update({"aktif": True, "status": {"$ne": "memproses"}})
    items = await (db.peta_lapisan.find(q, {"_id": 0})
                   .sort([("urutan", 1), ("created_at", 1)])
                   .to_list(BATAS_DAFTAR))
    hasil = []
    for dok in items:
        item = bentuk_publik(dok)
        if admin:
            item["kode_satker"] = str(dok.get("kode_satker") or "")
            item["bisa_ubah"] = _boleh_ubah(user, dok)
        hasil.append(item)
    return {"items": hasil, "jumlah": len(hasil),
            "ubin_token": token_ubin(_RAHASIA_UBIN, _hari_ini())}


async def _urutan_berikut(jenis: str) -> int:
    akhir = await (db.peta_lapisan.find({"jenis": jenis}, {"_id": 0, "urutan": 1})
                   .sort("urutan", -1).limit(1).to_list(1))
    return int((akhir[0].get("urutan") if akhir else 0) or 0) + 1


@peta_lapisan_router.post("/peta-lapisan")
async def buat_lapisan(payload: LapisanIn, user: dict = Depends(require_admin)):
    data = payload.model_dump()
    if payload.jenis == "citra":
        dok, galat = normalisasi_citra_baru(data)
    elif payload.jenis == "gambar":
        dok, galat = normalisasi_gambar(data)
    else:
        raise HTTPException(status_code=400, detail="Jenis lapisan tidak dikenal")
    _tolak(galat)
    now = datetime.now(timezone.utc).isoformat()
    dok.update({"id": str(uuid.uuid4()), "version": 1, "created_at": now,
                "updated_at": now, "urutan": await _urutan_berikut(dok["jenis"]),
                "kode_satker": kode_satker_user(user),
                "dibuat_oleh": user.get("username", "")})
    await db.peta_lapisan.insert_one(dict(dok))
    await log_audit("buat_peta_lapisan", "", dok["id"],
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Tambah lapisan {dok['jenis']} {dok['nama']}")
    return bentuk_publik(dok)


@peta_lapisan_router.put("/peta-lapisan/{lapisan_id}")
async def ubah_lapisan(lapisan_id: str, payload: LapisanIn,
                       user: dict = Depends(require_admin)):
    if payload.version is None:
        raise HTTPException(status_code=428, detail="Versi lapisan wajib dikirim saat mengubah")
    lama = await _ambil(lapisan_id)
    _pastikan_boleh_ubah(user, lama)
    data = payload.model_dump()
    if lama["jenis"] == "citra":
        perubahan, galat = normalisasi_citra_ubah(data)
        if lama.get("status") == "memproses":
            perubahan["aktif"] = False   # belum selesai diunggah → belum boleh tampil
    else:
        perubahan, galat = normalisasi_gambar(data)
        perubahan.pop("jenis", None)
    _tolak(galat)
    perubahan.update({"updated_at": datetime.now(timezone.utc).isoformat(),
                      "diubah_oleh": user.get("username", "")})
    res = await db.peta_lapisan.update_one(
        {"id": lapisan_id, "version": payload.version},
        {"$set": perubahan, "$inc": {"version": 1}})
    if res.matched_count == 0:
        raise HTTPException(status_code=409,
                            detail="Lapisan sudah diubah orang lain — muat ulang lalu coba lagi")
    await log_audit("ubah_peta_lapisan", "", lapisan_id,
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Ubah lapisan {lama['jenis']} {perubahan.get('nama', '')}")
    return bentuk_publik(await _ambil(lapisan_id))


@peta_lapisan_router.put("/peta-lapisan-urutan")
async def atur_urutan(payload: UrutanIn, user: dict = Depends(require_admin)):
    """Urutan tampil: indeks pertama = paling BAWAH. Citra dan gambar diurutkan
    terpisah (gambar selalu di atas citra)."""
    ids = [i for i in payload.ids if id_lapisan_sah(i)][:BATAS_DAFTAR]
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail="Urutan memuat lapisan ganda")
    for i, lid in enumerate(ids, 1):
        await db.peta_lapisan.update_one({"id": lid}, {"$set": {"urutan": i}})
    await log_audit("urutan_peta_lapisan", "", "",
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Atur urutan {len(ids)} lapisan peta")
    return {"ok": True, "jumlah": len(ids)}


@peta_lapisan_router.delete("/peta-lapisan/{lapisan_id}")
async def hapus_lapisan(lapisan_id: str, user: dict = Depends(require_admin)):
    lama = await _ambil(lapisan_id)
    _pastikan_boleh_ubah(user, lama)
    await db.peta_lapisan.delete_one({"id": lapisan_id})
    if lama["jenis"] == "citra":
        await asyncio.to_thread(shutil.rmtree, _folder_lapisan(lapisan_id), True)
    await log_audit("hapus_peta_lapisan", "", lapisan_id,
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Hapus lapisan {lama['jenis']} {lama.get('nama', '')}")
    return {"ok": True, "id": lapisan_id}


# ── Ubin citra ──────────────────────────────────────────────────────────────

def _tulis_ubin(folder: Path, berkas: list) -> int:
    n = 0
    for (z, x, y, fmt), data in berkas:
        tujuan = folder / str(z) / str(x) / f"{y}.{fmt}"
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        sementara = tujuan.with_suffix(f".{fmt}.tmp")
        sementara.write_bytes(data)
        os.replace(sementara, tujuan)
        n += 1
    return n


@peta_lapisan_router.post("/peta-lapisan/{lapisan_id}/ubin")
async def unggah_ubin(lapisan_id: str, files: List[UploadFile] = File(...),
                      user: dict = Depends(require_admin)):
    """Simpan satu batch ubin hasil potong peramban. Nama berkas `z-x-y.fmt`."""
    lama = await _ambil(lapisan_id)
    _pastikan_boleh_ubah(user, lama)
    if lama["jenis"] != "citra" or lama.get("status") != "memproses":
        raise HTTPException(status_code=409, detail="Citra ini tidak sedang menerima unggahan")
    if len(files) > UBIN_PER_BATCH_MAKS:
        raise HTTPException(status_code=400, detail=f"Maksimal {UBIN_PER_BATCH_MAKS} ubin per kiriman")
    folder = _folder_lapisan(lapisan_id)
    akar = akar_ubin()
    await asyncio.to_thread(akar.mkdir, parents=True, exist_ok=True)
    if (await asyncio.to_thread(shutil.disk_usage, akar)).free < SISA_DISK_MIN:
        raise HTTPException(status_code=507, detail="Ruang penyimpanan server hampir penuh")
    siap = []
    for f in files:
        info = nama_berkas_ubin(f.filename)
        if not info:
            raise HTTPException(status_code=400, detail=f"Nama ubin tidak sah: {f.filename}")
        z, x, y, fmt = info
        if fmt != lama["format"] or not (lama["zoom_min"] <= z <= lama["zoom_maks"]) \
                or not ubin_dalam_batas(lama["batas"], z, x, y):
            raise HTTPException(status_code=400, detail=f"Ubin di luar citra: {f.filename}")
        data = await f.read(UKURAN_UBIN_MAKS + 1)
        if len(data) > UKURAN_UBIN_MAKS or not isi_cocok_format(data, fmt):
            raise HTTPException(status_code=400, detail=f"Isi ubin tidak sah: {f.filename}")
        siap.append(((z, x, y, fmt), data))
    n = await asyncio.to_thread(_tulis_ubin, folder, siap)
    return {"ok": True, "tersimpan": n}


def _hitung_ubin(folder: Path) -> tuple[int, int]:
    n = ukuran = 0
    if folder.exists():
        for p in folder.rglob("*"):
            if p.is_file() and not p.name.endswith(".tmp"):
                n += 1
                ukuran += p.stat().st_size
    return n, ukuran


@peta_lapisan_router.post("/peta-lapisan/{lapisan_id}/selesai")
async def selesai_unggah(lapisan_id: str, user: dict = Depends(require_admin)):
    lama = await _ambil(lapisan_id)
    _pastikan_boleh_ubah(user, lama)
    if lama["jenis"] != "citra":
        raise HTTPException(status_code=400, detail="Bukan lapisan citra")
    n, ukuran = await asyncio.to_thread(_hitung_ubin, _folder_lapisan(lapisan_id))
    if n == 0:
        raise HTTPException(status_code=400, detail="Belum ada ubin yang terunggah")
    if n > min(UBIN_MAKS_PER_LAPISAN,
               jumlah_ubin(lama["batas"], lama["zoom_min"], lama["zoom_maks"])):
        raise HTTPException(status_code=400, detail="Jumlah ubin melebihi rencana")
    await db.peta_lapisan.update_one(
        {"id": lapisan_id},
        {"$set": {"status": "siap", "aktif": True, "jumlah_ubin": n, "ukuran_byte": ukuran,
                  "updated_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"version": 1}})
    await log_audit("unggah_citra_peta", "", lapisan_id,
                    username=user.get("username", "system"),
                    kode_satker=kode_satker_user(user),
                    detail=f"Citra {lama['nama']}: {n} ubin")
    return bentuk_publik(await _ambil(lapisan_id))


@peta_lapisan_router.get("/peta-lapisan/{lapisan_id}/ubin/{z}/{x}/{nama}")
async def ambil_ubin(lapisan_id: str, z: int, x: int, nama: str, t: str = Query(default="")):
    """Satu ubin citra. Tanpa kueri DB: token HMAC + jalur dari bilangan bulat."""
    if not token_ubin_sah(_RAHASIA_UBIN, t, _hari_ini()):
        raise HTTPException(status_code=403, detail="Token ubin tidak sah")
    bagian = nama.split(".")
    if len(bagian) != 2 or not bagian[0].isdigit() or bagian[1] not in FORMAT_UBIN \
            or not (0 <= z <= 22) or x < 0:
        raise HTTPException(status_code=404, detail="Ubin tidak ditemukan")
    path = _folder_lapisan(lapisan_id) / str(z) / str(x) / f"{int(bagian[0])}.{bagian[1]}"
    if not await asyncio.to_thread(path.is_file):
        raise HTTPException(status_code=404, detail="Ubin tidak ditemukan")
    # Isi ubin tak pernah berubah untuk id lapisan yang sama (citra baru = id
    # baru), jadi boleh di-cache lama. "private": ubin hanya untuk pengguna login.
    return FileResponse(path, media_type=FORMAT_UBIN[bagian[1]],
                        headers={"Cache-Control": "private, max-age=2592000, immutable"})
