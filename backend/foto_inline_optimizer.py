"""Optimasi bertahap FOTO inline tanpa memigrasi atau menghapus salinannya.

Hanya empat jalur yang merupakan foto, bukan lampiran dokumen/tanda tangan:
assets.photos, assets.photo (legacy), assets.document_checklist[].photos,
dan inventory_activities.photos. Thumbnail tetap pada indeksnya. CAS terhadap
array asal + versi mencegah hasil terlambat menimpa suntingan pengguna.

Ledger hanya menyimpan hash/ukuran/status, tidak bita maupun identitas pemilik.
Sumber identik berbagi keputusan plateau, bukan berbagi file keluaran. Cursor
berputar dengan anggaran per panggilan; foto baru sebelum cursor tetap mendapat
giliran pada putaran berikutnya. Pemanggil menyediakan idle/lease scheduler.
"""
import asyncio
import base64
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone

from PIL import Image
from pymongo import ReturnDocument

from db import db
from foto_kompresi import (AMBANG_HEMAT_PERSEN, MAKS_PIKSEL_FOTO,
                           hemat_persen, sumber_foto_valid, verifikasi_foto)
from tinify_service import optimalkan

BATAS_PEMILIK = 12
BATAS_SLOT = 64
_CURSOR_ID = "foto_inline_cursor_v1"
_TERMINAL = {"plateau", "corrupt", "manual_review"}
_SUMBER = ("assets", "inventory_activities")
_PROYEKSI = {"_id": 0, "id": 1, "version": 1, "photos": 1,
             "photo": 1, "document_checklist.photos": 1}


def _sekarang():
    return datetime.now(timezone.utc)


def _utc(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _query_foto(nama):
    if nama == "inventory_activities":
        return {"photos.0": {"$exists": True}}
    return {"$or": [{"photos.0": {"$exists": True}},
                    {"photo": {"$type": "string", "$ne": ""}},
                    {"document_checklist.photos.0": {"$exists": True}}]}


def _slot_foto(owner, nama):
    """(path tepat, array/field pembanding CAS, nilai awal) dalam urutan tetap."""
    photos = owner.get("photos")
    if isinstance(photos, list):
        for index, value in enumerate(photos):
            if isinstance(value, str) and value:
                yield f"photos.{index}", "photos", value
    if nama != "assets":
        return
    photo = owner.get("photo")
    if isinstance(photo, str) and photo:
        yield "photo", "photo", photo
    for index, item in enumerate(owner.get("document_checklist") or []):
        if not isinstance(item, dict) or not isinstance(item.get("photos"), list):
            continue
        for photo_index, value in enumerate(item["photos"]):
            if isinstance(value, str) and value:
                parent = f"document_checklist.{index}.photos"
                yield f"{parent}.{photo_index}", parent, value


def _nilai(owner, path):
    value = owner
    for part in path.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def _decode(value):
    """Hash bita = sama walau header data-URI berbeda; gagal tak kirim jaringan."""
    try:
        payload = value
        if value.startswith("data:"):
            header, payload = value.split(",", 1)
            mime = header.split(";", 1)[0].lower()
            if mime not in {"data:image/jpeg", "data:image/jpg", "data:image/png",
                            "data:image/webp", "data:image/avif", "data:image/gif", "data:image/bmp"}:
                return None, "", "lewat"
            if ";base64" not in header.lower():
                raise ValueError("Bukan data-URI base64")
        elif value.startswith(("http:", "https:", "blob:", "__existing__:")):
            return None, "", "lewat"
        data = base64.b64decode("".join(payload.split()), validate=True)
        if not data:
            raise ValueError("Foto kosong")
        return data, "inline:v1:" + hashlib.sha256(data).hexdigest(), ""
    except (ValueError, TypeError):
        # Status encoding rusak pun deterministik, tanpa menyimpan payloadnya.
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return None, "inline:v1:rusak:" + digest, "corrupt"


def _validasi_sumber(data):
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in {"JPEG", "PNG", "WEBP", "AVIF"}:
                return "manual_review"
            # Animasi jangan diam-diam diratakan menjadi satu frame.
            if getattr(img, "n_frames", 1) != 1 or img.width * img.height > MAKS_PIKSEL_FOTO:
                return "manual_review"
            # WebP 8-bit bukan pengganti yang aman untuk sumber 16-bit/float;
            # jangan membakar kuota untuk hasil yang pasti ditolak verifier.
            if img.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK", "YCbCr"}:
                return "manual_review"
            img.load()
        return "" if sumber_foto_valid(data) else "corrupt"
    except Exception:
        return "corrupt"


def _layak(state, now):
    if (state or {}).get("status") in _TERMINAL:
        return False
    return all(not _utc((state or {}).get(field))
               or _utc(state[field]) <= now for field in ("retry_at", "busy_until"))


async def _catat(key, token, status, **fields):
    await db.foto_kompresi_status.update_one(
        {"_id": key, "processing_token": token},
        {"$set": {"status": status, "updated_at": _sekarang(), **fields},
         "$unset": {"processing_token": "", "busy_until": ""}})


async def _klaim(key, data):
    """Satu hash satu percobaan; crash pulih setelah lease pendek kadaluwarsa."""
    now = _sekarang()
    await db.foto_kompresi_status.update_one(
        {"_id": key}, {"$setOnInsert": {
            "source": "inline", "status": "pending", "created_at": now,
            "baseline_bytes": len(data or b""), "current_bytes": len(data or b""),
            "pass_count": 0, "attempt_count": 0}}, upsert=True)
    token = uuid.uuid4().hex
    tersedia = [{"$or": [{field: {"$exists": False}}, {field: None},
                          {field: {"$lte": now}}]}
                for field in ("retry_at", "busy_until")]
    state = await db.foto_kompresi_status.find_one_and_update(
        {"_id": key, "status": {"$nin": sorted(_TERMINAL)}, "$and": tersedia},
        {"$set": {"processing_token": token, "busy_until": now + timedelta(minutes=10),
                  "updated_at": now}}, return_document=ReturnDocument.AFTER)
    return state, token


def _ulang_nanti(status, retry_at):
    now = _sekarang()
    retry = _utc(retry_at)
    if retry and retry > now:
        return retry
    if status == "kuota":
        return (now.replace(day=1) + timedelta(days=32)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0)
    return now + timedelta(hours=6) if status == "tidak_tersedia" else now + timedelta(minutes=10)


async def _berwenang(callback):
    if callback is None:
        return True
    try:
        return bool(await callback())
    except Exception:
        return False


async def _proses(owner, nama, slot, data, key, masalah, cadangan, masih_berwenang):
    state, token = await _klaim(key, data)
    if not state:
        return "lewat"
    masalah = masalah or await asyncio.to_thread(_validasi_sumber, data)
    if masalah:
        await _catat(key, token, masalah, reason="sumber_tidak_layak")
        return "rusak" if masalah == "corrupt" else "manual_review"
    if not await _berwenang(masih_berwenang):
        await _catat(key, token, "pending", reason="lease_berakhir", retry_at=None)
        return "berubah"
    await db.foto_kompresi_status.update_one(
        {"_id": key, "processing_token": token}, {"$inc": {"attempt_count": 1}})
    try:
        hasil = await optimalkan(data, webp=True, cadangan=cadangan)
    except Exception:
        await _catat(key, token, "retry", reason="sementara",
                     retry_at=_ulang_nanti("sementara", None))
        return "sementara"
    if hasil.status != "ok":
        if hasil.status == "input_rusak":
            # Sudah terdekode lokal: penolakan penyedia bukan bukti sumber rusak.
            await _catat(key, token, "manual_review", reason="ditolak_penyedia")
            return "manual_review"
        alasan = hasil.status if hasil.status in {"kuota", "sementara", "tidak_tersedia"} else "sementara"
        await _catat(key, token, "retry", reason=alasan,
                     retry_at=_ulang_nanti(alasan, hasil.retry_at))
        return "kuota" if alasan == "kuota" else "sementara"
    if not await asyncio.to_thread(verifikasi_foto, data, hasil.data):
        await _catat(key, token, "manual_review", reason="hasil_tidak_lolos_verifikasi")
        return "manual_review"
    savings = hemat_persen(len(data), len(hasil.data))
    if savings < AMBANG_HEMAT_PERSEN:
        await _catat(key, token, "plateau", previous_bytes=len(data),
                     result_bytes=len(hasil.data), last_savings_percent=savings,
                     reason="penghematan_di_bawah_ambang", retry_at=None)
        return "hemat_tipis"

    # Tidak menyimpan output di ledger; catat lineage sebelum CAS supaya crash
    # sesudah CAS tidak menghilangkan baseline yang sudah diketahui.
    new_key = "inline:v1:" + hashlib.sha256(hasil.data).hexdigest()
    now = _sekarang()
    await db.foto_kompresi_status.update_one(
        {"_id": new_key}, {"$setOnInsert": {
            "source": "inline", "status": "pending", "created_at": now,
            "baseline_bytes": state.get("baseline_bytes", len(data)),
            "current_bytes": len(hasil.data), "previous_bytes": len(data),
            "pass_count": int(state.get("pass_count", 0)) + 1,
            "attempt_count": 0, "last_savings_percent": savings}}, upsert=True)
    path, parent, _value = slot
    query = {"id": owner["id"], parent: _nilai(owner, parent)}
    changes = {"$set": {
        path: "data:image/webp;base64," + base64.b64encode(hasil.data).decode("ascii"),
        # Versi baru harus ikut delta snapshot offline, bukan hanya membatalkan
        # cache media di browser yang kebetulan sedang membuka aset.
        "updated_at": now.isoformat()}}
    if "version" in owner:
        query["version"] = owner["version"]
    else:
        query["version"] = {"$exists": False}
    if nama == "assets" or isinstance(owner.get("version"), int):
        if owner.get("version") is None and "version" in owner:
            changes["$set"]["version"] = 1
        else:
            changes["$inc"] = {"version": 1}
    if not await _berwenang(masih_berwenang):
        await _catat(key, token, "pending", reason="lease_berakhir", retry_at=None)
        return "berubah"
    result = await db[nama].update_one(query, changes)
    if not result.matched_count:
        await _catat(key, token, "pending", reason="pemilik_berubah", retry_at=None)
        return "berubah"
    # Sumber sama mungkin masih ada pada pemilik lain: bukan terminal. Baru
    # hasil yang dicoba kembali dan hemat <1% ditandai plateau per hash.
    await _catat(key, token, "pending", previous_bytes=len(data),
                 result_bytes=len(hasil.data), result_digest=new_key,
                 last_savings_percent=savings, reason="diterapkan", retry_at=None)
    return "sukses"


async def proses_satu(cadangan: int = 0, masih_berwenang=None):
    """Paling banyak SATU percobaan foto; None = sapuan tanpa kerja saat ini.

    `lewat` berarti cursor maju/anggaran batch habis, bukan seluruh antrean
    tuntas. Galat DB boleh naik ke scheduler; cursor berputar dan ledger lease
    kadaluwarsa, jadi gangguan sementara tidak mengunci foto selamanya.
    """
    state = await db.app_runtime.find_one({"_id": _CURSOR_ID}) or {}
    positions = state.get("positions") or {}
    start = int(state.get("source_index", 0)) % len(_SUMBER)
    remaining_owners, remaining_slots = BATAS_PEMILIK, BATAS_SLOT
    lanjut = False

    async def simpan(next_source):
        await db.app_runtime.update_one({"_id": _CURSOR_ID}, {"$set": {
            "positions": positions, "source_index": next_source,
            "updated_at": _sekarang()}}, upsert=True)

    for offset in range(len(_SUMBER)):
        source_index = (start + offset) % len(_SUMBER)
        nama = _SUMBER[source_index]
        pos = dict(positions.get(nama) or {})
        last = pos.get("last_id", "")
        query = {"$and": [_query_foto(nama), {"id": {"$gte": last}}]}
        owners = await (db[nama].find(query, _PROYEKSI).sort("id", 1)
                        .limit(remaining_owners + 1).to_list(remaining_owners + 1))
        batch = owners[:remaining_owners]
        for owner in batch:
            remaining_owners -= 1
            slots = list(_slot_foto(owner, nama))
            from_slot = int(pos.get("slot", 0)) if owner["id"] == last else 0
            for index in range(from_slot, len(slots)):
                pos.update(last_id=owner["id"], slot=index + 1)
                positions[nama] = pos
                remaining_slots -= 1
                data, key, masalah = await asyncio.to_thread(_decode, slots[index][2])
                if key:
                    ledger = await db.foto_kompresi_status.find_one({"_id": key})
                    if _layak(ledger, _sekarang()):
                        pos["ada_kerja"] = True
                        await simpan((source_index + 1) % len(_SUMBER))
                        return await _proses(owner, nama, slots[index], data, key,
                                             masalah, cadangan, masih_berwenang)
                if remaining_slots <= 0:
                    await simpan((source_index + 1) % len(_SUMBER))
                    return "lewat"
            pos.update(last_id=owner["id"], slot=len(slots))
            positions[nama] = pos
        if len(owners) > len(batch):
            await simpan((source_index + 1) % len(_SUMBER))
            return "lewat"
        # Selesai satu putaran. Ada hasil baru di belakang cursor? Segera
        # putar sekali lagi; putaran tanpa kandidat barulah mengembalikan None.
        lanjut = lanjut or bool(pos.get("ada_kerja"))
        positions[nama] = {"last_id": "", "slot": 0, "ada_kerja": False}
        if remaining_owners <= 0:
            await simpan((source_index + 1) % len(_SUMBER))
            return "lewat"
    await simpan((start + 1) % len(_SUMBER))
    return "lewat" if lanjut else None
