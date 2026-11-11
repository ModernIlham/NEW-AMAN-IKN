"""Direktori instansi & satker LUAR — instansi eksternal dan pihak ketiga.

Rencana: `docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md` (PGW-02; kontrak 6.1,
tata kelola 3.4, aturan penampungan 3.3, invarian 5.7).

Direktori ini SATU untuk seluruh instansi (keputusan pemilik K2):
- koleksi `instansi_luar` dan `satker_luar` TIDAK distempel `kode_satker` dan
  TIDAK dibungkus `scope_query_field_satker` — semua pengguna login melihat
  isi yang sama;
- semua admin boleh menambah/mengubah (K2a); setiap tulis tercatat di audit
  dengan `strict=True` beserta field yang berubah; hapus permanen hanya
  super-admin;
- jejak penulis disimpan di `dicatat_oleh`/`diubah_oleh` — KETERANGAN, bukan
  kunci isolasi, sengaja tidak bernama `kode_satker`.

Modul ini tidak pernah menulis koleksi internal (`pegawai`, `unit_kerja`,
`satker`, `assets`); `satker` hanya DIBACA untuk menolak `kode_luar` yang sama
dengan kode satker internal (aturan penampungan 6).
"""
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth_utils import require_admin, require_super_admin, require_user
from db import db
from shared_utils import kode_satker_user, log_audit
import organisasi_luar_utils as olu
from pegawai_utils import kode_satker_lengkap_sah, normalisasi_kode_satker_lengkap

organisasi_luar_router = APIRouter()

NAMA_WADAH = "Masyarakat (Perorangan)"
JENIS_RIWAYAT = {"instansi": "instansi", "satker": "satker", "orang": "orang"}

# Field yang dibandingkan untuk `changes` audit (K2a). Turunan server
# (nama_kunci, version, jejak penulis) tidak dicatat sebagai perubahan.
_FIELD_INSTANSI = (
    "kelompok", "jenis", "tataran", "induk_id", "nama", "singkatan", "alamat",
    "kota", "telepon", "email", "kode_referensi", "peran", "aktif",
    *olu.FIELD_KHUSUS_BADAN, *olu.FIELD_JENJANG)
_FIELD_SATKER = (
    "nama_satker", "kode_luar", "nama_unit_organisasi", "nama_sub_unit",
    "alamat", "telepon", "email", "aktif", "kode_satker_lengkap",
    "eselon_satker", "instansi_nama", "tataran", *olu.FIELD_JENJANG)


class SatkerLuarIn(BaseModel):
    nama_satker: str = ""
    kode_luar: Optional[str] = ""
    nama_unit_organisasi: Optional[str] = ""
    nama_sub_unit: Optional[str] = ""
    alamat: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    aktif: Optional[bool] = True
    kode_satker_lengkap: Optional[str] = ""
    eselon_satker: Optional[str] = ""
    # Hanya untuk POST /luar/satker. Pada PUT: bila dikirim dan berbeda dari
    # induk lama → 400 (aturan penampungan 1).
    instansi_id: Optional[str] = ""


class InstansiLuarIn(BaseModel):
    kelompok: str = ""
    jenis: str = ""
    nama: str = ""
    singkatan: Optional[str] = ""
    alamat: Optional[str] = ""
    kota: Optional[str] = ""
    telepon: Optional[str] = ""
    email: Optional[str] = ""
    kode_referensi: Optional[str] = ""
    induk_id: Optional[str] = ""
    peran: Optional[List[str]] = None
    nomor_induk: Optional[str] = ""
    npwp: Optional[str] = ""
    dasar_pendirian_nomor: Optional[str] = ""
    dasar_pendirian_tanggal: Optional[str] = ""
    badan_penyelenggara: Optional[str] = ""
    aktif: Optional[bool] = True
    satker_pertama: Optional[SatkerLuarIn] = None


# ── pembantu ───────────────────────────────────────────────────────────────
def _kini() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jejak(user) -> dict:
    return {"username": user.get("username", "system"),
            "kode_satker": kode_satker_user(user), "pada": _kini()}


def _perubahan(lama: dict, baru: dict, fields) -> list:
    out = []
    for f in fields:
        a, b = lama.get(f, ""), baru.get(f, "")
        if isinstance(a, list) or isinstance(b, list):
            a, b = ", ".join(a or []), ", ".join(b or [])
        a, b = str("" if a is None else a), str("" if b is None else b)
        if a != b:
            out.append({"field": f, "from": a, "to": b})
    return out


async def _audit(aksi: str, record_id: str, user: dict, detail: str,
                 changes: list = None):
    await log_audit(aksi, "", record_id, username=user.get("username", "system"),
                    changes=changes or [], detail=detail,
                    kode_satker=kode_satker_user(user), strict=True)


def _versi_diminta(request: Request, versi_kini: int):
    if_match = (request.headers.get("If-Match") or "").strip().strip('"')
    if not if_match:
        return None
    try:
        return int(if_match)
    except ValueError:
        return versi_kini


def _tolak_versi_usang(request: Request, lama: dict, label: str) -> int:
    versi_kini = int(lama.get("version") or 1)
    harapan = _versi_diminta(request, versi_kini)
    if harapan is not None and harapan != versi_kini:
        raise HTTPException(status_code=409, detail={
            "message": f"Data {label} telah diubah pengguna lain. Muat ulang "
                       "lalu simpan kembali.",
            "current_version": versi_kini, "your_version": harapan})
    return versi_kini


def _filter_versi(doc_id: str, versi_kini: int) -> dict:
    if versi_kini == 1:
        return {"id": doc_id, "$or": [{"version": 1},
                                      {"version": {"$exists": False}},
                                      {"version": None}]}
    return {"id": doc_id, "version": versi_kini}


def _galat(errors):
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))


def _payload(model: BaseModel, *, tanpa=()) -> dict:
    d = model.model_dump() if hasattr(model, "model_dump") else model.dict()
    for k in tanpa:
        d.pop(k, None)
    return d


async def _instansi_atau_404(instansi_id: str) -> dict:
    doc = await db.instansi_luar.find_one({"id": instansi_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Instansi tidak ditemukan")
    return doc


async def _satker_atau_404(satker_id: str) -> dict:
    doc = await db.satker_luar.find_one({"id": satker_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Satker tidak ditemukan")
    return doc


async def _induk_dan_jenjang(doc: dict) -> dict:
    """Validasi jenjang daerah (invarian 12) lalu isi salinan jenjangnya."""
    induk = None
    if doc.get("induk_id"):
        induk = await db.instansi_luar.find_one({"id": doc["induk_id"]}, {"_id": 0})
    _galat(olu.periksa_jenjang_daerah(doc, induk))
    doc.update(olu.salinan_jenjang(doc, induk))
    return doc


async def _cek_kembar_instansi(doc: dict, kecuali_id: str = ""):
    q = {"kelompok": doc["kelompok"], "induk_id": doc["induk_id"],
         "nama_kunci": doc["nama_kunci"]}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    ada = await db.instansi_luar.find_one(q, {"_id": 0, "id": 1, "nama": 1})
    if ada:
        raise HTTPException(status_code=400, detail={
            "message": f"Instansi \"{ada['nama']}\" sudah tercatat — pakai "
                       "catatan yang ada.", "id_ada": ada["id"]})
    if doc.get("kode_referensi"):
        q = {"kelompok": doc["kelompok"], "kode_referensi": doc["kode_referensi"]}
        if kecuali_id:
            q["id"] = {"$ne": kecuali_id}
        ada = await db.instansi_luar.find_one(q, {"_id": 0, "id": 1, "nama": 1})
        if ada:
            raise HTTPException(status_code=400, detail={
                "message": f"Kode {doc['kode_referensi']} sudah dipakai "
                           f"\"{ada['nama']}\".", "id_ada": ada["id"]})


def _bersihkan_satker_masuk(payload: dict, instansi: dict) -> dict:
    doc = olu.bersihkan_satker_luar(payload, instansi)
    ksl = normalisasi_kode_satker_lengkap(doc.get("kode_satker_lengkap"))
    if ksl and not kode_satker_lengkap_sah(ksl):
        raise HTTPException(status_code=400, detail=(
            "Kode satker lengkap harus 20 karakter (18 digit + 2 huruf kewenangan)"))
    if doc.get("kelompok") == "eksternal":
        doc["kode_satker_lengkap"] = ksl
    doc["aktif"] = bool(payload.get("aktif", True))
    for f in ("nama_unit_organisasi", "nama_sub_unit", "alamat", "telepon",
              "email", "eselon_satker"):
        doc[f] = str(doc.get(f) or "").strip()
    return doc


async def _cek_satker(doc: dict, kecuali_id: str = ""):
    _galat(olu.validate_satker_luar(doc))
    q = {"instansi_id": doc["instansi_id"], "nama_kunci": doc["nama_kunci"]}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    ada = await db.satker_luar.find_one(q, {"_id": 0, "id": 1, "nama_satker": 1})
    if ada:
        raise HTTPException(status_code=400, detail={
            "message": f"Satker \"{ada['nama_satker']}\" sudah ada di instansi "
                       "ini.", "id_ada": ada["id"]})
    kode = doc.get("kode_luar")
    if kode:
        if await db.satker.find_one({"kode_satker": kode}, {"_id": 1}):
            raise HTTPException(status_code=400, detail=(
                f"Kode {kode} adalah kode satker internal — satker internal "
                "tidak dicatat di direktori luar"))
        q = {"instansi_id": doc["instansi_id"], "kode_luar": kode}
        if kecuali_id:
            q["id"] = {"$ne": kecuali_id}
        ada = await db.satker_luar.find_one(q, {"_id": 0, "id": 1})
        if ada:
            raise HTTPException(status_code=400, detail={
                "message": f"Kode {kode} sudah dipakai satker lain di instansi "
                           "ini.", "id_ada": ada["id"]})


async def _segarkan_turunan(instansi: dict, _dilihat=None):
    """Rambatkan nama, tataran, jenis, dan salinan jenjang sebuah instansi ke
    satker & orangnya, lalu ke pemda di bawahnya (rekursif, ber-pengaman
    lingkaran). Dipanggil setelah instansi diubah."""
    dilihat = _dilihat if _dilihat is not None else set()
    if instansi["id"] in dilihat:
        return
    dilihat.add(instansi["id"])
    jenjang = {f: instansi.get(f, "") for f in olu.FIELD_JENJANG}
    await db.satker_luar.update_many(
        {"instansi_id": instansi["id"]},
        {"$set": {"instansi_nama": instansi["nama"],
                  "tataran": instansi.get("tataran", ""),
                  "jenis": instansi["jenis"], **jenjang}})
    await db.pegawai_luar.update_many(
        {"instansi_id": instansi["id"]},
        {"$set": {"instansi_nama": instansi["nama"],
                  "tataran": instansi.get("tataran", ""),
                  "jenis_instansi": instansi["jenis"], **jenjang}})
    async for anak in db.instansi_luar.find({"induk_id": instansi["id"]}, {"_id": 0}):
        salinan = olu.salinan_jenjang(anak, instansi)
        await db.instansi_luar.update_one({"id": anak["id"]}, {"$set": salinan})
        await _segarkan_turunan({**anak, **salinan}, dilihat)


async def pastikan_wadah_perorangan(user: dict = None) -> dict:
    """Instansi-wadah "Masyarakat (Perorangan)" + satu satker-wadahnya.
    Idempoten: memanggil berkali-kali mengembalikan pasangan yang sama."""
    instansi = await db.instansi_luar.find_one(
        {"kelompok": "pihak_ketiga", "jenis": "perorangan", "wadah": True},
        {"_id": 0})
    jejak = {"username": (user or {}).get("username", "system"),
             "kode_satker": kode_satker_user(user) if user else "", "pada": _kini()}
    if not instansi:
        instansi = olu.bersihkan_instansi_luar({
            "kelompok": "pihak_ketiga", "jenis": "perorangan",
            "nama": NAMA_WADAH, "wadah": True})
        instansi.update({"id": str(uuid.uuid4()), "aktif": True, "version": 1,
                         "dicatat_oleh": jejak, "diubah_oleh": jejak,
                         **olu.salinan_jenjang(instansi)})
        try:
            await db.instansi_luar.insert_one(dict(instansi))
        except Exception:
            ada = await db.instansi_luar.find_one(
                {"kelompok": "pihak_ketiga", "jenis": "perorangan", "wadah": True},
                {"_id": 0})
            if not ada:
                raise
            instansi = ada
    satker = await db.satker_luar.find_one(
        {"instansi_id": instansi["id"], "wadah": True}, {"_id": 0})
    if not satker:
        satker = olu.bersihkan_satker_luar({"nama_satker": NAMA_WADAH}, instansi)
        satker.update({"id": str(uuid.uuid4()), "wadah": True, "aktif": True,
                       "version": 1, "dicatat_oleh": jejak, "diubah_oleh": jejak})
        try:
            await db.satker_luar.insert_one(dict(satker))
        except Exception:
            ada = await db.satker_luar.find_one(
                {"instansi_id": instansi["id"], "wadah": True}, {"_id": 0})
            if not ada:
                raise
            satker = ada
    instansi.pop("_id", None)
    satker.pop("_id", None)
    return {"instansi": instansi, "satker": satker}


def _halaman(page: int, page_size: int):
    page = max(1, int(page or 1))
    page_size = min(max(1, int(page_size or 30)), 100)
    return page, page_size


def _pola_cari(q: str):
    return {"$regex": re.escape(q.strip()), "$options": "i"}


# ── referensi ──────────────────────────────────────────────────────────────
@organisasi_luar_router.get("/luar/referensi")
async def referensi_luar(_user: dict = Depends(require_user)):
    """Semua kode referensi direktori luar. Layar membaca ini, tidak menyalin
    daftar. Gambar ikon (ikon_kelompok.json) menyusul di PGW-08; kuncinya
    sudah dikunci di sini."""
    return {
        "kelompok": olu.KELOMPOK_LUAR,
        "tataran": olu.TATARAN_EKSTERNAL,
        "jenis_instansi": olu.JENIS_INSTANSI,
        "tataran_dari_jenis": olu.TATARAN_DARI_JENIS,
        "induk_daerah": olu.INDUK_DAERAH,
        "peran_instansi": olu.PERAN_INSTANSI,
        "kapasitas_bertindak": olu.KAPASITAS_BERTINDAK,
        "dasar_kewenangan": olu.DASAR_KEWENANGAN,
        "label_tingkat": olu.LABEL_TINGKAT,
        "field_nonaktif": {k: list(v) for k, v in olu.FIELD_NONAKTIF.items()},
        "field_khusus_badan": list(olu.FIELD_KHUSUS_BADAN),
        "field_khusus_pihak_ketiga": list(olu.FIELD_KHUSUS_PIHAK_KETIGA),
        "label_field": olu.LABEL_FIELD,
        "kunci_ikon": list(olu.KUNCI_IKON),
    }


# ── wadah perorangan ───────────────────────────────────────────────────────
@organisasi_luar_router.post("/luar/wadah-perorangan")
async def buka_wadah_perorangan(user: dict = Depends(require_admin)):
    """Pasangan wadah "Masyarakat (Perorangan)" — dibuat saat pertama
    dibutuhkan (3.3), yaitu saat admin memilih Perorangan di layar Master
    Pegawai. Idempoten; tidak menulis audit karena tidak ada data pengguna
    yang berubah selain wadah sistem itu sendiri."""
    return await pastikan_wadah_perorangan(user)


# ── riwayat ────────────────────────────────────────────────────────────────
@organisasi_luar_router.get("/luar/riwayat/{jenis}/{record_id}")
async def riwayat_luar(jenis: str, record_id: str,
                       _user: dict = Depends(require_user)):
    """Jejak audit satu catatan direktori luar — TANPA scope satker: catatan
    itu milik bersama, jadi jejaknya pun terlihat semua satker (6.1)."""
    if jenis not in JENIS_RIWAYAT:
        raise HTTPException(status_code=400, detail="Jenis riwayat tidak dikenal")
    awalan = f"luar_{JENIS_RIWAYAT[jenis]}_"
    items = await db.audit_logs.find(
        {"asset_id": record_id, "action": {"$regex": f"^{re.escape(awalan)}"}},
        {"_id": 0, "action": 1, "username": 1, "kode_satker": 1,
         "timestamp": 1, "changes": 1, "detail": 1}
    ).sort("timestamp", -1).to_list(200)
    return {"items": items}


# ── instansi ───────────────────────────────────────────────────────────────
@organisasi_luar_router.get("/luar/instansi")
async def daftar_instansi_luar(kelompok: str = "", tataran: str = "",
                               jenis: str = "", provinsi_id: str = "",
                               induk_id: str = "", q: str = "",
                               aktif: Optional[bool] = None,
                               page: int = 1, page_size: int = 30,
                               _user: dict = Depends(require_user)):
    if kelompok not in olu.KELOMPOK_LUAR:
        raise HTTPException(status_code=400, detail=(
            "Pilih kelompok dulu: eksternal atau pihak_ketiga"))
    query = {"kelompok": kelompok}
    if tataran and kelompok == "eksternal":
        query["tataran"] = tataran
    if jenis:
        query["jenis"] = jenis
    if provinsi_id:
        query["provinsi_id"] = provinsi_id
    if induk_id:
        query["induk_id"] = induk_id
    if aktif is not None:
        query["aktif"] = aktif
    if q.strip():
        pola = _pola_cari(q)
        query["$or"] = [{"nama": pola}, {"singkatan": pola},
                        {"kode_referensi": pola}]
    page, page_size = _halaman(page, page_size)
    total = await db.instansi_luar.count_documents(query)
    items = await db.instansi_luar.find(query, {"_id": 0}).sort("nama", 1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    ids = [i["id"] for i in items]
    jumlah_satker, jumlah_orang = {}, {}
    if ids:
        async for r in db.satker_luar.aggregate([
                {"$match": {"instansi_id": {"$in": ids}}},
                {"$group": {"_id": "$instansi_id", "n": {"$sum": 1}}}]):
            jumlah_satker[r["_id"]] = r["n"]
        async for r in db.pegawai_luar.aggregate([
                {"$match": {"instansi_id": {"$in": ids}}},
                {"$group": {"_id": "$instansi_id", "n": {"$sum": 1}}}]):
            jumlah_orang[r["_id"]] = r["n"]
    for i in items:
        i["jumlah_satker"] = jumlah_satker.get(i["id"], 0)
        i["jumlah_orang"] = jumlah_orang.get(i["id"], 0)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@organisasi_luar_router.get("/luar/instansi/{instansi_id}")
async def ambil_instansi_luar(instansi_id: str, _user: dict = Depends(require_user)):
    return await _instansi_atau_404(instansi_id)


@organisasi_luar_router.post("/luar/instansi")
async def buat_instansi_luar(payload: InstansiLuarIn,
                             user: dict = Depends(require_admin)):
    data = _payload(payload, tanpa=("satker_pertama",))
    _galat(olu.validate_instansi_luar(data))
    if data["jenis"] == "perorangan":
        raise HTTPException(status_code=400, detail=(
            f"Perorangan dicatat di wadah \"{NAMA_WADAH}\", bukan sebagai "
            "instansi baru"))
    doc = olu.bersihkan_instansi_luar(data)
    doc["id"] = str(uuid.uuid4())
    doc["aktif"] = bool(data.get("aktif", True))
    doc["wadah"] = False
    for f in ("singkatan", "alamat", "kota", "telepon", "email"):
        doc[f] = str(doc.get(f) or "").strip()
    await _induk_dan_jenjang(doc)
    await _cek_kembar_instansi(doc)
    pemda = doc["jenis"] in olu.INDUK_DAERAH
    if payload.satker_pertama is None and not pemda:
        raise HTTPException(status_code=400, detail=(
            "Instansi dicatat bersama satker pertamanya"))
    jejak = _jejak(user)
    doc.update({"version": 1, "dicatat_oleh": jejak, "diubah_oleh": jejak})
    satker = None
    if payload.satker_pertama is not None:
        satker = _bersihkan_satker_masuk(_payload(payload.satker_pertama), doc)
        satker.update({"id": str(uuid.uuid4()), "wadah": False, "version": 1,
                       "dicatat_oleh": jejak, "diubah_oleh": jejak})
        await _cek_satker(satker)
        # Satker dulu: bila instansi gagal disisipkan, satker dibuang lagi —
        # tak pernah ada instansi tanpa satker yang wajib punya satker.
        await db.satker_luar.insert_one(dict(satker))
    try:
        await db.instansi_luar.insert_one(dict(doc))
    except Exception:
        if satker:
            await db.satker_luar.delete_one({"id": satker["id"]})
        raise
    await _audit("luar_instansi_tambah", doc["id"], user,
                 f"Tambah instansi luar {doc['nama']}")
    if satker:
        await _audit("luar_satker_tambah", satker["id"], user,
                     f"Tambah satker luar {satker['nama_satker']} "
                     f"({doc['nama']})")
        satker.pop("_id", None)
    doc.pop("_id", None)
    return {"instansi": doc, "satker": satker}


@organisasi_luar_router.put("/luar/instansi/{instansi_id}")
async def ubah_instansi_luar(instansi_id: str, payload: InstansiLuarIn,
                             request: Request, user: dict = Depends(require_admin)):
    lama = await _instansi_atau_404(instansi_id)
    if lama.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            f"\"{NAMA_WADAH}\" adalah wadah sistem — tidak dapat diubah"))
    versi_kini = _tolak_versi_usang(request, lama, "instansi")
    data = _payload(payload, tanpa=("satker_pertama",))
    _galat(olu.validate_instansi_luar(data))
    punya_satker = await db.satker_luar.count_documents({"instansi_id": instansi_id}) > 0
    punya_anak = await db.instansi_luar.count_documents({"induk_id": instansi_id}) > 0
    if data["kelompok"] != lama["kelompok"] and punya_satker:
        raise HTTPException(status_code=400, detail=(
            "Kelompok instansi yang sudah punya satker tidak dapat diubah"))
    if data["jenis"] != lama["jenis"] and (punya_satker or punya_anak):
        raise HTTPException(status_code=400, detail=(
            "Jenis instansi yang sudah punya satker atau pemda di bawahnya "
            "tidak dapat diubah"))
    if data["jenis"] == "perorangan":
        raise HTTPException(status_code=400, detail=(
            f"Perorangan dicatat di wadah \"{NAMA_WADAH}\""))
    doc = olu.bersihkan_instansi_luar(data)
    doc["id"] = instansi_id
    doc["aktif"] = bool(data.get("aktif", True))
    doc["wadah"] = False
    for f in ("singkatan", "alamat", "kota", "telepon", "email"):
        doc[f] = str(doc.get(f) or "").strip()
    await _induk_dan_jenjang(doc)
    await _cek_kembar_instansi(doc, kecuali_id=instansi_id)
    changes = _perubahan(lama, doc, _FIELD_INSTANSI)
    doc["version"] = versi_kini + 1
    doc["diubah_oleh"] = _jejak(user)
    res = await db.instansi_luar.update_one(_filter_versi(instansi_id, versi_kini),
                                            {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail=(
            "Data instansi telah berubah. Muat ulang sebelum menyimpan."))
    baru = {**lama, **doc}
    await _segarkan_turunan(baru)
    await _audit("luar_instansi_ubah", instansi_id, user,
                 f"Ubah instansi luar {doc['nama']}", changes)
    return baru


@organisasi_luar_router.delete("/luar/instansi/{instansi_id}")
async def hapus_instansi_luar(instansi_id: str,
                              user: dict = Depends(require_super_admin)):
    lama = await _instansi_atau_404(instansi_id)
    if lama.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            f"\"{NAMA_WADAH}\" adalah wadah sistem — tidak dapat dihapus"))
    if await db.instansi_luar.count_documents({"induk_id": instansi_id}):
        raise HTTPException(status_code=409, detail=(
            "Instansi masih punya pemda di bawahnya — pindahkan atau hapus dulu"))
    if await db.pegawai_luar.count_documents({"instansi_id": instansi_id}):
        raise HTTPException(status_code=409, detail=(
            "Instansi masih punya orang tercatat — nonaktifkan saja bila sudah "
            "tidak dipakai"))
    # Rujukan dari transaksi (BAST, pemanfaatan, …) belum ada; PGW-10/11 yang
    # menambah pemeriksaannya di sini, lintas satker, tanpa merinci satker lain.
    satker_ids = [s["id"] async for s in db.satker_luar.find(
        {"instansi_id": instansi_id}, {"_id": 0, "id": 1})]
    if satker_ids:
        await db.unit_kerja_luar.delete_many({"satker_luar_id": {"$in": satker_ids}})
        await db.satker_luar.delete_many({"id": {"$in": satker_ids}})
    await db.instansi_luar.delete_one({"id": instansi_id})
    await _audit("luar_instansi_hapus", instansi_id, user,
                 f"Hapus instansi luar {lama.get('nama', '')} beserta "
                 f"{len(satker_ids)} satker kosong")
    return {"ok": True, "satker_dihapus": len(satker_ids)}


# ── satker ─────────────────────────────────────────────────────────────────
@organisasi_luar_router.get("/luar/satker")
async def daftar_satker_luar(instansi_id: str = "", q: str = "",
                             aktif: Optional[bool] = None,
                             page: int = 1, page_size: int = 50,
                             _user: dict = Depends(require_user)):
    if not instansi_id:
        raise HTTPException(status_code=400, detail="Pilih instansi dulu")
    query = {"instansi_id": instansi_id}
    if aktif is not None:
        query["aktif"] = aktif
    if q.strip():
        pola = _pola_cari(q)
        query["$or"] = [{"nama_satker": pola}, {"kode_luar": pola}]
    page, page_size = _halaman(page, page_size)
    total = await db.satker_luar.count_documents(query)
    items = await db.satker_luar.find(query, {"_id": 0}).sort("nama_satker", 1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    ids = [s["id"] for s in items]
    jumlah = {}
    if ids:
        async for r in db.pegawai_luar.aggregate([
                {"$match": {"satker_luar_id": {"$in": ids}}},
                {"$group": {"_id": "$satker_luar_id", "n": {"$sum": 1}}}]):
            jumlah[r["_id"]] = r["n"]
    for s in items:
        s["jumlah_orang"] = jumlah.get(s["id"], 0)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@organisasi_luar_router.get("/luar/satker/{satker_id}")
async def ambil_satker_luar(satker_id: str, _user: dict = Depends(require_user)):
    return await _satker_atau_404(satker_id)


@organisasi_luar_router.post("/luar/satker")
async def buat_satker_luar(payload: SatkerLuarIn, user: dict = Depends(require_admin)):
    instansi = await _instansi_atau_404(str(payload.instansi_id or ""))
    if instansi.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            f"\"{NAMA_WADAH}\" hanya punya satu satker-wadah"))
    doc = _bersihkan_satker_masuk(_payload(payload), instansi)
    jejak = _jejak(user)
    doc.update({"id": str(uuid.uuid4()), "wadah": False, "version": 1,
                "dicatat_oleh": jejak, "diubah_oleh": jejak})
    await _cek_satker(doc)
    await db.satker_luar.insert_one(dict(doc))
    await _audit("luar_satker_tambah", doc["id"], user,
                 f"Tambah satker luar {doc['nama_satker']} ({instansi['nama']})")
    doc.pop("_id", None)
    return doc


@organisasi_luar_router.put("/luar/satker/{satker_id}")
async def ubah_satker_luar(satker_id: str, payload: SatkerLuarIn, request: Request,
                           user: dict = Depends(require_admin)):
    lama = await _satker_atau_404(satker_id)
    if lama.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            f"Satker \"{NAMA_WADAH}\" adalah wadah sistem — tidak dapat diubah"))
    dikirim = str(payload.instansi_id or "").strip()
    if dikirim and dikirim != lama["instansi_id"]:
        raise HTTPException(status_code=400, detail=(
            "Satker tidak dapat dipindah ke instansi lain — buat satker di "
            "instansi yang benar lalu pindahkan orangnya"))
    versi_kini = _tolak_versi_usang(request, lama, "satker")
    instansi = await _instansi_atau_404(lama["instansi_id"])
    doc = _bersihkan_satker_masuk(_payload(payload), instansi)
    doc["id"] = satker_id
    await _cek_satker(doc, kecuali_id=satker_id)
    changes = _perubahan(lama, doc, _FIELD_SATKER)
    doc["version"] = versi_kini + 1
    doc["diubah_oleh"] = _jejak(user)
    res = await db.satker_luar.update_one(_filter_versi(satker_id, versi_kini),
                                          {"$set": doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail=(
            "Data satker telah berubah. Muat ulang sebelum menyimpan."))
    if doc["nama_satker"] != lama.get("nama_satker"):
        await db.pegawai_luar.update_many(
            {"satker_luar_id": satker_id},
            {"$set": {"satker_luar_nama": doc["nama_satker"]}})
    await _audit("luar_satker_ubah", satker_id, user,
                 f"Ubah satker luar {doc['nama_satker']}", changes)
    return {**lama, **doc}


@organisasi_luar_router.delete("/luar/satker/{satker_id}")
async def hapus_satker_luar(satker_id: str, user: dict = Depends(require_super_admin)):
    lama = await _satker_atau_404(satker_id)
    if lama.get("wadah"):
        raise HTTPException(status_code=400, detail=(
            f"Satker \"{NAMA_WADAH}\" adalah wadah sistem — tidak dapat dihapus"))
    if await db.pegawai_luar.count_documents({"satker_luar_id": satker_id}):
        raise HTTPException(status_code=409, detail=(
            "Satker masih punya orang tercatat — nonaktifkan saja bila sudah "
            "tidak dipakai"))
    if await db.unit_kerja_luar.count_documents({"satker_luar_id": satker_id}):
        raise HTTPException(status_code=409, detail=(
            "Satker masih punya unit kerja — hapus unitnya dulu"))
    await db.satker_luar.delete_one({"id": satker_id})
    await _audit("luar_satker_hapus", satker_id, user,
                 f"Hapus satker luar {lama.get('nama_satker', '')}")
    return {"ok": True}
