"""PERSURATAN — buku agenda & penomoran naskah dinas lintas modul (pustaka §12).

Mengakomodir SEMUA jenis laporan/naskah yang terbit dari modul mana pun
(inventarisasi, pelaporan, penggunaan, dst.) dan kegiatan mana pun:

- **Surat keluar**: nomor DIBOOKING saat draf dibuat (atomik per tahun
  takwim — dua pemanggil tak pernah dapat nomor sama), lalu **disahkan**
  setelah surat final ditandatangani atau **dibatalkan** (nomor hangus,
  tidak didaur ulang — celah nomor tetap dapat dijelaskan, kaidah
  kearsipan). Susunan nomor mengikuti PerANRI 5/2021 dan dapat diatur.
- **Surat masuk**: agenda kembar — nomor agenda sendiri per tahun,
  status diterima → diproses → selesai.

Logika murni (format nomor, validasi, transisi, baris agenda) di
persuratan_utils.py — teruji unit.
"""
import csv as csv_module
import io
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from pymongo import ReturnDocument

from auth_utils import require_admin, require_user
from db import db
from shared_utils import log_audit
from persuratan_utils import (
    FORMAT_NOMOR_DEFAULT, JENIS_NASKAH, KODE_KEAMANAN, MODUL_AMAN,
    STATUS_KELUAR, STATUS_MASUK, TRANSISI_KELUAR, TRANSISI_MASUK,
    bangun_nomor, baris_agenda_csv, pilih_klasifikasi,
    placeholder_tak_dikenal, validate_peta_klasifikasi,
    validate_surat_keluar, validate_surat_masuk, validate_transisi,
)

persuratan_router = APIRouter()

_PROJ = {"_id": 0}


class SuratKeluarIn(BaseModel):
    perihal: str
    tujuan: Optional[str] = ""
    jenis_naskah: Optional[str] = "Laporan"
    modul: Optional[str] = "umum"
    kegiatan_id: Optional[str] = ""
    kode_klasifikasi: Optional[str] = ""
    kode_keamanan: Optional[str] = "B"
    tanggal_surat: Optional[str] = ""   # default: hari ini (UTC date)
    referensi: Optional[str] = ""       # mis. "BAHI", "LHI", "LBKP S1 2026"
    # Anchor nomor SAH dari sistem lain (Srikandi/e-office instansi dsb.)
    # bila penomoran resmi tidak dari AMAN — nomor internal tetap dibooking
    # sebagai nomor agenda, nomor eksternal jadi rujukan silang.
    nomor_eksternal: Optional[str] = ""
    keterangan: Optional[str] = ""


class SuratMasukIn(BaseModel):
    nomor_surat: str
    pengirim: str
    perihal: str
    tanggal_surat: Optional[str] = ""
    modul: Optional[str] = "umum"
    kegiatan_id: Optional[str] = ""
    keterangan: Optional[str] = ""


class TransisiIn(BaseModel):
    status: str
    alasan: Optional[str] = ""


class UbahSuratIn(BaseModel):
    perihal: Optional[str] = None
    tujuan: Optional[str] = None
    pengirim: Optional[str] = None
    # Hanya untuk surat MASUK: nomor surat dari pengirim boleh dikoreksi.
    nomor_surat: Optional[str] = None
    jenis_naskah: Optional[str] = None
    modul: Optional[str] = None
    kegiatan_id: Optional[str] = None
    kode_klasifikasi: Optional[str] = None
    tanggal_surat: Optional[str] = None
    referensi: Optional[str] = None
    nomor_eksternal: Optional[str] = None
    keterangan: Optional[str] = None


class PengaturanIn(BaseModel):
    format_nomor: Optional[str] = None
    kode_unit: Optional[str] = None
    kode_klasifikasi_default: Optional[str] = None
    # Aturan klasifikasi otomatis: [{modul, jenis_naskah, kode}] — field
    # kosong = wildcard; aturan paling spesifik menang (pilih_klasifikasi).
    peta_klasifikasi: Optional[list] = None


class KlasifikasiIn(BaseModel):
    kode: str
    uraian: Optional[str] = ""
    aktif: Optional[bool] = True


async def _pengaturan() -> dict:
    s = await db.persuratan_settings.find_one({"type": "global"}, _PROJ) or {}
    return {
        "format_nomor": s.get("format_nomor") or FORMAT_NOMOR_DEFAULT,
        "kode_unit": s.get("kode_unit") or "",
        "kode_klasifikasi_default": s.get("kode_klasifikasi_default") or "",
        "peta_klasifikasi": s.get("peta_klasifikasi") or [],
    }


async def _no_agenda_berikut(jenis: str, tahun: int) -> int:
    """Nomor agenda berikutnya (atomik — $inc pada dokumen counter)."""
    c = await db.counters.find_one_and_update(
        {"_id": f"surat_{jenis}_{tahun}"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(c["seq"])


async def _nama_kegiatan(kegiatan_id: str) -> str:
    if not str(kegiatan_id or "").strip():
        return ""
    act = await db.inventory_activities.find_one(
        {"id": kegiatan_id}, {"_id": 0, "nama_kegiatan": 1})
    if not act:
        raise HTTPException(status_code=404, detail="Kegiatan tidak ditemukan")
    return act.get("nama_kegiatan") or ""


@persuratan_router.get("/persuratan/referensi")
async def referensi_persuratan(_user: dict = Depends(require_user)):
    """Pilihan dropdown + pengaturan aktif (untuk form UI)."""
    return {
        "jenis_naskah": list(JENIS_NASKAH),
        "modul": list(MODUL_AMAN),
        "kode_keamanan": [{"kode": k, "uraian": v} for k, v in KODE_KEAMANAN.items()],
        "status_keluar": [{"kode": k, "uraian": v} for k, v in STATUS_KELUAR.items()],
        "status_masuk": [{"kode": k, "uraian": v} for k, v in STATUS_MASUK.items()],
        "transisi_keluar": {k: sorted(v) for k, v in TRANSISI_KELUAR.items()},
        "transisi_masuk": {k: sorted(v) for k, v in TRANSISI_MASUK.items()},
        "pengaturan": await _pengaturan(),
        "klasifikasi": await db.klasifikasi_arsip.find(
            {"aktif": {"$ne": False}}, _PROJ).sort("kode", 1).to_list(2000),
    }


# ── Master kode klasifikasi arsip (dinamis, admin mengelola) ──

@persuratan_router.get("/persuratan/klasifikasi")
async def daftar_klasifikasi(_user: dict = Depends(require_user)):
    """Master kode klasifikasi arsip (semua, termasuk nonaktif)."""
    items = await db.klasifikasi_arsip.find({}, _PROJ).sort("kode", 1).to_list(2000)
    return {"items": items, "jumlah": len(items)}


@persuratan_router.post("/persuratan/klasifikasi")
async def tambah_klasifikasi(payload: KlasifikasiIn,
                             user: dict = Depends(require_admin)):
    """Tambah kode klasifikasi arsip (admin; kode unik)."""
    kode = payload.kode.strip()
    if not kode:
        raise HTTPException(status_code=400, detail="Kode klasifikasi wajib diisi")
    if await db.klasifikasi_arsip.find_one({"kode": kode}, _PROJ):
        raise HTTPException(status_code=409, detail=f"Kode {kode} sudah terdaftar")
    doc = {"id": str(uuid.uuid4()), "kode": kode,
           "uraian": str(payload.uraian or "").strip(),
           "aktif": payload.aktif is not False,
           "created_at": datetime.now(timezone.utc).isoformat()}
    await db.klasifikasi_arsip.insert_one({**doc})
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Tambah kode klasifikasi {kode}")
    return doc


@persuratan_router.put("/persuratan/klasifikasi/{klas_id}")
async def ubah_klasifikasi(klas_id: str, payload: KlasifikasiIn,
                           user: dict = Depends(require_admin)):
    """Ubah kode klasifikasi arsip (admin)."""
    kode = payload.kode.strip()
    if not kode:
        raise HTTPException(status_code=400, detail="Kode klasifikasi wajib diisi")
    bentrok = await db.klasifikasi_arsip.find_one(
        {"kode": kode, "id": {"$ne": klas_id}}, _PROJ)
    if bentrok:
        raise HTTPException(status_code=409, detail=f"Kode {kode} sudah terdaftar")
    res = await db.klasifikasi_arsip.find_one_and_update(
        {"id": klas_id},
        {"$set": {"kode": kode, "uraian": str(payload.uraian or "").strip(),
                  "aktif": payload.aktif is not False}},
        projection=_PROJ, return_document=ReturnDocument.AFTER)
    if res is None:
        raise HTTPException(status_code=404, detail="Kode klasifikasi tidak ditemukan")
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Ubah kode klasifikasi {kode}")
    return res


@persuratan_router.delete("/persuratan/klasifikasi/{klas_id}")
async def hapus_klasifikasi(klas_id: str, user: dict = Depends(require_admin)):
    """Hapus kode klasifikasi. Ditolak bila dipakai aturan pemetaan (#34)."""
    k = await db.klasifikasi_arsip.find_one({"id": klas_id}, _PROJ)
    if not k:
        raise HTTPException(status_code=404, detail="Kode klasifikasi tidak ditemukan")
    atur = await _pengaturan()
    dipakai = [a for a in atur["peta_klasifikasi"] if a.get("kode") == k["kode"]]
    if dipakai:
        raise HTTPException(status_code=409, detail=(
            f"Kode {k['kode']} masih dipakai {len(dipakai)} aturan pemetaan — "
            "hapus/ubah aturannya dulu"))
    await db.klasifikasi_arsip.delete_one({"id": klas_id})
    await log_audit("klasifikasi_arsip", "", username=user.get("username", "system"),
                    detail=f"Hapus kode klasifikasi {k['kode']}")
    return {"ok": True, "id": klas_id}


@persuratan_router.get("/persuratan/pratinjau-nomor")
async def pratinjau_nomor(jenis_naskah: str = "", modul: str = "",
                          kode_klasifikasi: str = "", kode_keamanan: str = "B",
                          tanggal_surat: str = "",
                          _user: dict = Depends(require_user)):
    """Pratinjau nomor yang AKAN terbit (tanpa memesan — counter tidak naik).

    Perkiraan: bila ada booking lain sebelum Anda menekan simpan, nomor
    final bisa bergeser maju — keunikan tetap dijamin counter atomik.
    """
    atur = await _pengaturan()
    tanggal = (str(tanggal_surat or "").strip()[:10]
               or datetime.now(timezone.utc).date().isoformat())
    tahun = int(tanggal[:4]) if tanggal[:4].isdigit() else datetime.now(timezone.utc).year
    c = await db.counters.find_one({"_id": f"surat_keluar_{tahun}"})
    urut_berikut = int((c or {}).get("seq") or 0) + 1
    kode = pilih_klasifikasi(atur["peta_klasifikasi"], modul, jenis_naskah,
                             eksplisit=kode_klasifikasi,
                             default=atur["kode_klasifikasi_default"])
    nomor = bangun_nomor(atur["format_nomor"], urut_berikut, tanggal,
                         kode_klasifikasi=kode, kode_unit=atur["kode_unit"],
                         kode_keamanan=kode_keamanan)
    return {"nomor": nomor, "urut_berikut": urut_berikut,
            "kode_klasifikasi": kode,
            "sumber_klasifikasi": ("eksplisit" if str(kode_klasifikasi or "").strip()
                                   else ("pemetaan" if kode and kode != atur["kode_klasifikasi_default"]
                                         else ("bawaan" if kode else "kosong")))}


@persuratan_router.get("/persuratan/pengaturan")
async def get_pengaturan_persuratan(_user: dict = Depends(require_user)):
    return await _pengaturan()


@persuratan_router.post("/persuratan/pengaturan")
async def set_pengaturan_persuratan(payload: PengaturanIn,
                                    user: dict = Depends(require_admin)):
    """Atur format nomor & kode unit (admin). Placeholder divalidasi."""
    mentah = {k: v for k, v in payload.model_dump().items() if v is not None}
    update = {k: v.strip() for k, v in mentah.items() if isinstance(v, str)}
    if "peta_klasifikasi" in mentah:
        peta = [{"modul": str((a or {}).get("modul") or "").strip(),
                 "jenis_naskah": str((a or {}).get("jenis_naskah") or "").strip(),
                 "kode": str((a or {}).get("kode") or "").strip()}
                for a in mentah["peta_klasifikasi"]]
        errors = validate_peta_klasifikasi(peta)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))
        update["peta_klasifikasi"] = peta
    if "format_nomor" in update:
        if not update["format_nomor"]:
            update["format_nomor"] = FORMAT_NOMOR_DEFAULT
        asing = placeholder_tak_dikenal(update["format_nomor"])
        if asing:
            raise HTTPException(status_code=400, detail=(
                f"Placeholder tidak dikenal: {', '.join(asing)} — yang sah: "
                "{kode_keamanan} {urut} {kode_klasifikasi} {kode_unit} "
                "{bulan} {bulan_romawi} {tahun}"))
        if "{urut}" not in update["format_nomor"]:
            raise HTTPException(status_code=400,
                                detail="Format nomor wajib memuat {urut}")
    if not update:
        raise HTTPException(status_code=400, detail="Tidak ada yang diubah")
    update["type"] = "global"
    await db.persuratan_settings.update_one({"type": "global"},
                                            {"$set": update}, upsert=True)
    await log_audit("pengaturan_persuratan", "",
                    username=user.get("username", "system"),
                    detail=f"Ubah pengaturan persuratan: {sorted(set(update) - {'type'})}")
    return await _pengaturan()


@persuratan_router.get("/persuratan")
async def daftar_surat(jenis: str = "", status: str = "", modul: str = "",
                       tahun: str = "", q: str = "", page: int = 1,
                       page_size: int = 50,
                       _user: dict = Depends(require_user)):
    """Buku agenda gabungan (filter jenis/status/modul/tahun + cari)."""
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    query = {}
    if jenis in ("keluar", "masuk"):
        query["jenis"] = jenis
    if status:
        query["status"] = status
    if modul:
        query["modul"] = modul
    if tahun.strip().isdigit():
        query["tahun"] = int(tahun)
    if q.strip():
        rx = {"$regex": q.strip(), "$options": "i"}
        query["$or"] = [{"nomor": rx}, {"perihal": rx}, {"tujuan": rx},
                        {"pengirim": rx}, {"referensi": rx},
                        {"nama_kegiatan": rx}]
    total = await db.surat.count_documents(query)
    items = await (db.surat.find(query, _PROJ)
                   .sort([("tahun", -1), ("no_agenda", -1)])
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    ringkas = {
        "keluar_dibooking": await db.surat.count_documents(
            {"jenis": "keluar", "status": "dibooking"}),
        "keluar_disahkan": await db.surat.count_documents(
            {"jenis": "keluar", "status": "disahkan"}),
        "keluar_dibatalkan": await db.surat.count_documents(
            {"jenis": "keluar", "status": "dibatalkan"}),
        "masuk_terbuka": await db.surat.count_documents(
            {"jenis": "masuk", "status": {"$in": ["diterima", "diproses"]}}),
    }
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "ringkasan": ringkas}


@persuratan_router.post("/persuratan/keluar")
async def booking_surat_keluar(payload: SuratKeluarIn,
                               user: dict = Depends(require_user)):
    """BOOKING nomor surat keluar — nomor terbit atomik, status 'dibooking'.

    Nomor tetap milik surat ini sampai disahkan/dibatalkan; pembatalan
    TIDAK mengembalikan nomor ke antrean.
    """
    data = payload.model_dump()
    errors = validate_surat_keluar(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    nama_kegiatan = await _nama_kegiatan(data.get("kegiatan_id"))
    now = datetime.now(timezone.utc)
    tanggal_surat = (str(data.get("tanggal_surat") or "").strip()[:10]
                     or now.date().isoformat())
    tahun = int(tanggal_surat[:4])
    atur = await _pengaturan()
    # Klasifikasi otomatis: eksplisit → aturan pemetaan (modul/jenis naskah,
    # paling spesifik menang) → kode bawaan pengaturan.
    kode_klas = pilih_klasifikasi(
        atur["peta_klasifikasi"], data.get("modul"), data.get("jenis_naskah"),
        eksplisit=data.get("kode_klasifikasi"),
        default=atur["kode_klasifikasi_default"])
    no_agenda = await _no_agenda_berikut("keluar", tahun)
    nomor = bangun_nomor(
        atur["format_nomor"], no_agenda, tanggal_surat,
        kode_klasifikasi=kode_klas,
        kode_unit=atur["kode_unit"],
        kode_keamanan=data.get("kode_keamanan") or "B")
    record = {
        "id": str(uuid.uuid4()),
        "jenis": "keluar",
        "no_agenda": no_agenda,
        "tahun": tahun,
        "nomor": nomor,
        "status": "dibooking",
        "perihal": data["perihal"].strip(),
        "tujuan": str(data.get("tujuan") or "").strip(),
        "jenis_naskah": str(data.get("jenis_naskah") or "Laporan").strip(),
        "modul": str(data.get("modul") or "umum").strip(),
        "kegiatan_id": str(data.get("kegiatan_id") or "").strip(),
        "nama_kegiatan": nama_kegiatan,
        "kode_klasifikasi": kode_klas,
        "kode_keamanan": str(data.get("kode_keamanan") or "B").strip().upper(),
        "tanggal_surat": tanggal_surat,
        "referensi": str(data.get("referensi") or "").strip(),
        "nomor_eksternal": str(data.get("nomor_eksternal") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "dibuat_oleh": user.get("username", "system"),
        "riwayat": [{"status": "dibooking", "tanggal": now.isoformat(),
                     "oleh": user.get("username", "system"), "catatan": ""}],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.surat.insert_one({**record})
    await log_audit("booking_surat", record["kegiatan_id"],
                    username=user.get("username", "system"),
                    detail=f"Booking nomor surat keluar {nomor} — {record['perihal']}")
    return record


@persuratan_router.post("/persuratan/masuk")
async def agenda_surat_masuk(payload: SuratMasukIn,
                             user: dict = Depends(require_user)):
    """Catat surat masuk pada buku agenda (nomor agenda otomatis per tahun)."""
    data = payload.model_dump()
    errors = validate_surat_masuk(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    nama_kegiatan = await _nama_kegiatan(data.get("kegiatan_id"))
    now = datetime.now(timezone.utc)
    tahun = now.year
    no_agenda = await _no_agenda_berikut("masuk", tahun)
    record = {
        "id": str(uuid.uuid4()),
        "jenis": "masuk",
        "no_agenda": no_agenda,
        "tahun": tahun,
        "nomor": data["nomor_surat"].strip(),
        "status": "diterima",
        "perihal": data["perihal"].strip(),
        "pengirim": data["pengirim"].strip(),
        "tanggal_surat": str(data.get("tanggal_surat") or "").strip()[:10],
        "modul": str(data.get("modul") or "umum").strip(),
        "kegiatan_id": str(data.get("kegiatan_id") or "").strip(),
        "nama_kegiatan": nama_kegiatan,
        "keterangan": str(data.get("keterangan") or "").strip(),
        "dibuat_oleh": user.get("username", "system"),
        "riwayat": [{"status": "diterima", "tanggal": now.isoformat(),
                     "oleh": user.get("username", "system"), "catatan": ""}],
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.surat.insert_one({**record})
    await log_audit("agenda_surat_masuk", record["kegiatan_id"],
                    username=user.get("username", "system"),
                    detail=f"Agenda surat masuk #{no_agenda}/{tahun}: {record['nomor']}")
    return record


@persuratan_router.post("/persuratan/{surat_id}/status")
async def transisi_surat(surat_id: str, payload: TransisiIn,
                         user: dict = Depends(require_user)):
    """Pindahkan status surat (sahkan/batalkan/proses/selesai) — anti-race.

    Pembatalan surat keluar WAJIB beralasan (tercatat; nomor hangus).
    """
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    ke = str(payload.status or "").strip()
    err = validate_transisi(s.get("status"), ke, s.get("jenis"))
    if err:
        raise HTTPException(status_code=409, detail=err)
    alasan = str(payload.alasan or "").strip()
    if ke == "dibatalkan" and not alasan:
        raise HTTPException(status_code=400,
                            detail="Pembatalan wajib disertai alasan")
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": ke, "updated_at": now}
    if ke == "disahkan":
        set_fields["disahkan_pada"] = now
        set_fields["disahkan_oleh"] = user.get("username", "system")
    if ke == "dibatalkan":
        set_fields["alasan_batal"] = alasan
    res = await db.surat.find_one_and_update(
        {"id": surat_id, "status": s.get("status")},  # anti-race
        {"$set": set_fields,
         "$push": {"riwayat": {"status": ke, "tanggal": now,
                               "oleh": user.get("username", "system"),
                               "catatan": alasan}}},
        projection=_PROJ, return_document=ReturnDocument.AFTER)
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Status surat berubah — muat ulang dulu")
    await log_audit("status_surat", s.get("kegiatan_id", ""),
                    username=user.get("username", "system"),
                    detail=f"Surat {s.get('nomor')} → {ke}"
                           + (f" (alasan: {alasan})" if alasan else ""))
    return res


@persuratan_router.put("/persuratan/{surat_id}")
async def ubah_surat(surat_id: str, payload: UbahSuratIn,
                     user: dict = Depends(require_user)):
    """Ubah metadata surat. Surat keluar DISAHKAN terkunci (hanya keterangan);
    nomor & no. agenda tidak pernah bisa diubah."""
    s = await db.surat.find_one({"id": surat_id}, _PROJ)
    if not s:
        raise HTTPException(status_code=404, detail="Surat tidak ditemukan")
    update = {k: str(v).strip() for k, v in payload.model_dump().items()
              if v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Tidak ada yang diubah")
    if "nomor_surat" in update:
        # Nomor surat keluar milik counter agenda — tak pernah bisa diubah;
        # nomor surat MASUK berasal dari pengirim, boleh dikoreksi.
        if s.get("jenis") != "masuk":
            raise HTTPException(status_code=409,
                                detail="Nomor surat keluar tidak dapat diubah")
        if not update["nomor_surat"]:
            raise HTTPException(status_code=400, detail="Nomor surat wajib diisi")
        update["nomor"] = update.pop("nomor_surat")
    if s.get("jenis") == "keluar" and s.get("status") != "dibooking":
        terlarang = set(update) - {"keterangan", "nomor_eksternal"}
        if terlarang:
            raise HTTPException(status_code=409, detail=(
                "Surat sudah final — hanya 'keterangan' dan 'nomor eksternal' yang boleh diubah "
                f"(ditolak: {', '.join(sorted(terlarang))})"))
    if "modul" in update and update["modul"] and update["modul"] not in MODUL_AMAN:
        raise HTTPException(status_code=400,
                            detail=f"Modul tidak dikenal: {update['modul']}")
    if "kegiatan_id" in update:
        update["nama_kegiatan"] = await _nama_kegiatan(update["kegiatan_id"])
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.surat.find_one_and_update(
        {"id": surat_id}, {"$set": update},
        projection=_PROJ, return_document=ReturnDocument.AFTER)
    await log_audit("ubah_surat", s.get("kegiatan_id", ""),
                    username=user.get("username", "system"),
                    detail=f"Ubah surat {s.get('nomor')}: "
                           f"{sorted(set(update) - {'updated_at', 'nama_kegiatan'})}")
    return res


@persuratan_router.get("/persuratan/export")
async def export_agenda(jenis: str = "", tahun: str = "",
                        _user: dict = Depends(require_user)):
    """Ekspor buku agenda ke CSV (pola ekspor #158)."""
    query = {}
    if jenis in ("keluar", "masuk"):
        query["jenis"] = jenis
    if tahun.strip().isdigit():
        query["tahun"] = int(tahun)
    items = await (db.surat.find(query, _PROJ)
                   .sort([("tahun", 1), ("no_agenda", 1)]).to_list(100000))
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_agenda_csv(items):
        w.writerow(row)
    nama = f"Buku_Agenda_Surat{('_' + jenis) if jenis else ''}{('_' + tahun) if tahun else ''}.csv"
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{nama}"'})
