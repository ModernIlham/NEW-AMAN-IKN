"""Orang LUAR — pegawai instansi eksternal dan wakil pihak ketiga.

Rencana: `docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md` (PGW-03; kontrak 6.3,
pengecualian kesetaraan 6.4, invarian 5.7). Cermin `routes/pegawai.py`:
`_bersih` dan `validate_pegawai` dipakai ULANG dari modul internal, lalu
`sesuaikan_orang_luar` memangkas field per kelompok.

Beda yang disengaja dari Master Pegawai internal:
- koleksi `pegawai_luar` adalah direktori BERSAMA: tanpa `kode_satker`,
  tanpa `scope_query_field_satker`, terlihat semua satker (keputusan K2);
- kelompok, tataran, instansi, satker, dan salinan jenjang orang SELALU
  diturunkan dari `satker_luar`-nya — nilai kiriman klien diabaikan;
- hapus permanen hanya super-admin, dan ditolak bila orang itu masih dirujuk
  di satker MANA PUN (pesannya tidak merinci satker lain);
- cacah aset yang ditampilkan tetap ter-scope satker pemanggil;
- tidak ada akses portal BMN Saya (K3) — modul ini tidak memanggil
  `portal_auth`.

Modul ini tidak pernah menulis `pegawai`, `unit_kerja`, `satker`, atau
`assets`; keempatnya hanya DIBACA (cek silang NIP/kartu, cacah aset).
"""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     Response, UploadFile)

from auth_utils import (require_admin, require_super_admin, require_user,
                        require_user_or_query_token)
from db import db, fs_bucket
from kartu_utils import hash_kandidat, label_kartu, valid_uid
from shared_utils import kode_satker_user, limiter, log_audit
import organisasi_luar_utils as olu
from pegawai_utils import (info_masa_pegawai, kelompok_unit_kerja,
                           pegawai_perlu_serah_terima, rekap_eselon,
                           unit_kerja_terdalam)
from routes.pegawai import (KartuIn, PegawaiIn, _FOTO_MAX, _bersih,
                            _jumlah_aset_per_nip, _kecilkan_foto_asli)

pegawai_luar_router = APIRouter()

# Hash kartu & pendaftarnya tak pernah dikirim ke klien (sama dengan internal).
_PROJ = {"_id": 0, "kartu_uid_hashes": 0, "kartu_terdaftar_oleh": 0}
_STATUS_AKTIF = ["aktif", "", None]
_FIELD_TURUNAN = ("satker_luar_id", "satker_luar_nama", "instansi_id",
                  "instansi_nama", "kelompok", "tataran", "jenis_instansi",
                  *olu.FIELD_JENJANG)


class PegawaiLuarIn(PegawaiIn):
    satker_luar_id: str = ""
    kapasitas_bertindak: Optional[str] = ""
    dasar_kewenangan_jenis: Optional[str] = ""
    dasar_kewenangan_nomor: Optional[str] = ""
    dasar_kewenangan_tanggal: Optional[str] = ""


# ── pembantu ───────────────────────────────────────────────────────────────
def _kini() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jejak(user) -> dict:
    return {"username": user.get("username", "system"),
            "kode_satker": kode_satker_user(user), "pada": _kini()}


def _bersih_luar(payload: PegawaiLuarIn) -> dict:
    doc = _bersih(payload)
    doc["satker_luar_id"] = str(payload.satker_luar_id or "").strip()
    for f in olu.FIELD_KHUSUS_PIHAK_KETIGA:
        doc[f] = str(getattr(payload, f, "") or "").strip()
    return doc


async def _satker_aktif(satker_id: str) -> dict:
    satker = await db.satker_luar.find_one({"id": satker_id}, {"_id": 0}) \
        if satker_id else None
    if not satker:
        raise HTTPException(status_code=400, detail="Satker luar tidak ditemukan")
    if satker.get("aktif") is False:
        raise HTTPException(status_code=400, detail=(
            "Satker luar sudah dinonaktifkan — pilih satker yang aktif"))
    return satker


def _stempel(doc: dict, satker: dict) -> dict:
    """Isi kelompok, tataran, instansi, satker, dan salinan jenjang dari
    master satker. Nilai kiriman klien untuk field ini selalu ditimpa
    (aturan penampungan 2); kunci `kode_satker` dibuang (invarian 6)."""
    doc.update({
        "satker_luar_id": satker["id"],
        "satker_luar_nama": satker.get("nama_satker", ""),
        "instansi_id": satker.get("instansi_id", ""),
        "instansi_nama": satker.get("instansi_nama", ""),
        "kelompok": satker.get("kelompok", ""),
        "tataran": satker.get("tataran", ""),
        "jenis_instansi": satker.get("jenis", ""),
        **{f: satker.get(f, "") for f in olu.FIELD_JENJANG},
    })
    doc.pop("kode_satker", None)
    return doc


async def _siapkan(payload: PegawaiLuarIn, satker: dict) -> dict:
    doc = _bersih_luar(payload)
    kelompok, jenis = satker.get("kelompok", ""), satker.get("jenis", "")
    doc = olu.sesuaikan_orang_luar(doc, kelompok, jenis)
    doc = _stempel(doc, satker)
    # validate_orang_luar menjalankan validate_pegawai milik internal lebih
    # dulu, lalu aturan khusus kelompok luar.
    errors = olu.validate_orang_luar(doc, kelompok, jenis)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    return doc


async def _cek_nip(nip: str, kecuali_id: str = ""):
    """Invarian 4: NIP unik se-direktori luar dan tidak sama dengan NIP
    pegawai internal satker MANA PUN. Pesan tidak menyebut nama/satker orang
    internal itu."""
    if not nip:
        return
    if await db.pegawai.find_one({"nip": nip}, {"_id": 1}):
        raise HTTPException(status_code=400, detail=(
            f"NIP/NIK {nip} sudah terdaftar sebagai pegawai internal — orang "
            "yang sama tidak dicatat dua kali"))
    q = {"nip": nip}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    ada = await db.pegawai_luar.find_one(q, {"_id": 0, "id": 1})
    if ada:
        raise HTTPException(status_code=400, detail={
            "message": f"NIP/NIK {nip} sudah terdaftar di direktori luar",
            "id_ada": ada["id"]})


def _duplikat(e: Exception) -> bool:
    return "duplicate key" in str(e).lower() or e.__class__.__name__ == "DuplicateKeyError"


def _perubahan(lama: dict, baru: dict) -> list:
    out = []
    for f, b in baru.items():
        if f in ("version", "updated_at", "diubah_oleh"):
            continue
        a = lama.get(f, "")
        a, b = str("" if a is None else a), str("" if b is None else b)
        if a != b:
            out.append({"field": f, "from": a, "to": b})
    return out


async def _audit(aksi: str, record_id: str, user: dict, detail: str,
                 changes: list = None):
    await log_audit(aksi, "", record_id, username=user.get("username", "system"),
                    changes=changes or [], detail=detail,
                    kode_satker=kode_satker_user(user), strict=True)


async def _orang_atau_404(orang_id: str, proj=None) -> dict:
    doc = await db.pegawai_luar.find_one({"id": orang_id}, proj or _PROJ)
    if not doc:
        raise HTTPException(status_code=404, detail="Orang luar tidak ditemukan")
    return doc


def _halaman(page, page_size):
    return max(1, int(page or 1)), min(max(1, int(page_size or 50)), 200)


# ── daftar & rekap ─────────────────────────────────────────────────────────
@pegawai_luar_router.get("/pegawai-luar/rekap-unit")
async def rekap_unit_pegawai_luar(satker_luar_id: str = "",
                                  _user: dict = Depends(require_user)):
    if not satker_luar_id:
        raise HTTPException(status_code=400, detail="Pilih satker dulu")
    semua = await db.pegawai_luar.find(
        {"satker_luar_id": satker_luar_id}, _PROJ).to_list(20000)
    kelompok = kelompok_unit_kerja(semua)
    return {
        "unit": [{"unit_kerja": g["unit_kerja"], "jumlah": g["jumlah"]} for g in kelompok],
        "eselon1": rekap_eselon(semua, "eselon1"),
        "jumlah_pegawai": len(semua),
        "jumlah_unit": len(kelompok),
    }


@pegawai_luar_router.get("/pegawai-luar/rekap-lingkup")
async def rekap_lingkup_pegawai_luar(kelompok: str = "", tataran: str = "",
                                     _user: dict = Depends(require_user)):
    """Cacah orang luar per tataran, per instansi, dan per satker — bahan
    angka di layar pilih kelompok (3.10)."""
    if kelompok not in olu.KELOMPOK_LUAR:
        raise HTTPException(status_code=400, detail="Pilih kelompok dulu")
    match = {"kelompok": kelompok}
    if tataran and kelompok == "eksternal":
        match["tataran"] = tataran

    async def _grup(kunci, nama=None, batas=500):
        grup = {"_id": f"${kunci}", "jumlah": {"$sum": 1}}
        if nama:
            grup["nama"] = {"$first": f"${nama}"}
        out = []
        async for r in db.pegawai_luar.aggregate([
                {"$match": match}, {"$group": grup},
                {"$sort": {"jumlah": -1}}, {"$limit": batas}]):
            out.append({"id": r["_id"] or "", "nama": r.get("nama", ""),
                        "jumlah": r["jumlah"]})
        return out

    per_tataran = {r["id"]: r["jumlah"] for r in await _grup("tataran")}
    return {
        "jumlah": sum(per_tataran.values()),
        "per_tataran": per_tataran,
        "per_instansi": await _grup("instansi_id", "instansi_nama"),
        "per_satker": await _grup("satker_luar_id", "satker_luar_nama"),
    }


@pegawai_luar_router.get("/pegawai-luar/perlu-serah-terima")
async def perlu_serah_terima_luar(kelompok: str = "",
                                  _user: dict = Depends(require_user)):
    """Orang luar berisiko yang masih memegang aset SATKER PEMANGGIL."""
    q = {"kelompok": kelompok} if kelompok in olu.KELOMPOK_LUAR else {}
    orang = await db.pegawai_luar.find(q, {
        "_id": 0, "id": 1, "nama": 1, "nip": 1, "status": 1, "unit_kerja": 1,
        "tgl_selesai_kontrak": 1, "instansi_nama": 1, "satker_luar_nama": 1,
        "kelompok": 1, "tataran": 1}).to_list(20000)
    peta_aset = await _jumlah_aset_per_nip(_user)
    items = pegawai_perlu_serah_terima(orang, peta_aset,
                                       datetime.now(timezone.utc).date().isoformat())
    info = {o["id"]: o for o in orang}
    for it in items:
        o = info.get(it["id"], {})
        it.update({k: o.get(k, "") for k in ("unit_kerja", "instansi_nama",
                                             "satker_luar_nama", "kelompok",
                                             "tataran")})
    return {"items": items, "jumlah": len(items)}


@pegawai_luar_router.get("/pegawai-luar")
async def daftar_pegawai_luar(kelompok: str = "", tataran: str = "",
                              instansi_id: str = "", satker_luar_id: str = "",
                              provinsi_id: str = "", q: str = "",
                              semua_status: bool = False,
                              page: int = 1, page_size: int = 50,
                              _user: dict = Depends(require_user)):
    """Daftar orang luar — dicari dan dipotong halamannya di server (3.10
    butir 4). Hanya yang aktif kecuali `semua_status=true`."""
    if kelompok not in olu.KELOMPOK_LUAR:
        raise HTTPException(status_code=400, detail=(
            "Pilih kelompok dulu: eksternal atau pihak_ketiga"))
    query = {"kelompok": kelompok}
    if tataran and kelompok == "eksternal":
        query["tataran"] = tataran
    for k, v in (("instansi_id", instansi_id), ("satker_luar_id", satker_luar_id),
                 ("provinsi_id", provinsi_id)):
        if v:
            query[k] = v
    if not semua_status:
        query["status"] = {"$in": _STATUS_AKTIF}
    if q.strip():
        pola = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"nama": pola}, {"nip": pola}, {"jabatan": pola}]
    page, page_size = _halaman(page, page_size)
    total = await db.pegawai_luar.count_documents(query)
    items = await db.pegawai_luar.find(query, _PROJ).sort("nama", 1) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    hari_ini = datetime.now(timezone.utc).date().isoformat()
    for it in items:
        it["info_masa"] = info_masa_pegawai(it, hari_ini)
        if not str(it.get("unit_kerja") or "").strip():
            it["unit_kerja"] = unit_kerja_terdalam(it)
        it["label_unit"] = olu.label_unit_orang(it)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@pegawai_luar_router.get("/pegawai-luar/{orang_id}/aset")
async def aset_dipegang_orang_luar(orang_id: str, _user: dict = Depends(require_user)):
    """Aset yang dipegang orang luar — HANYA aset satker pemanggil."""
    from shared_utils import filter_aset_perhitungan, scope_query_aset
    orang = await _orang_atau_404(orang_id)
    nip = str(orang.get("nip") or "").strip()
    ringkas = {"id": orang_id, "nama": orang.get("nama"), "nip": nip}
    if not nip:
        return {"pegawai": ringkas, "items": [], "jumlah": 0}
    q = await filter_aset_perhitungan(await scope_query_aset(_user, {
        "pengguna_nip": nip, "dihapus": {"$ne": True}}))
    items = await db.assets.find(q, {
        "_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
        "condition": 1, "location": 1, "activity_id": 1,
    }).sort("asset_code", 1).to_list(2000)
    return {"pegawai": ringkas, "items": items, "jumlah": len(items)}


# ── tulis ──────────────────────────────────────────────────────────────────
@pegawai_luar_router.post("/pegawai-luar")
async def buat_pegawai_luar(payload: PegawaiLuarIn, user: dict = Depends(require_admin)):
    satker = await _satker_aktif(str(payload.satker_luar_id or "").strip())
    doc = await _siapkan(payload, satker)
    await _cek_nip(doc["nip"])
    jejak = _jejak(user)
    doc.update({"id": str(uuid.uuid4()), "created_at": _kini(),
                "updated_at": _kini(), "version": 1,
                "dicatat_oleh": jejak, "diubah_oleh": jejak})
    try:
        await db.pegawai_luar.insert_one(dict(doc))
    except Exception as e:
        if _duplikat(e):
            raise HTTPException(status_code=400, detail=(
                f"NIP/NIK {doc['nip']} baru saja didaftarkan — muat ulang"))
        raise
    await _audit("luar_orang_tambah", doc["id"], user,
                 f"Tambah orang luar {doc['nama']} ({doc['instansi_nama']})")
    return {"ok": True, "id": doc["id"],
            "peringatan": olu.peringatan_orang_luar(doc, doc["kelompok"])}


@pegawai_luar_router.put("/pegawai-luar/{orang_id}")
async def ubah_pegawai_luar(orang_id: str, payload: PegawaiLuarIn, request: Request,
                            user: dict = Depends(require_admin)):
    lama = await _orang_atau_404(orang_id, {"_id": 0})
    versi_kini = int(lama.get("version") or 1)
    if_match = (request.headers.get("If-Match") or "").strip().strip('"')
    if if_match:
        try:
            harapan = int(if_match)
        except ValueError:
            harapan = versi_kini
        if harapan != versi_kini:
            raise HTTPException(status_code=409, detail={
                "message": "Data orang luar telah diubah pengguna lain. Muat "
                           "ulang lalu simpan kembali.",
                "current_version": versi_kini, "your_version": harapan})
    tujuan_id = str(payload.satker_luar_id or "").strip() or lama.get("satker_luar_id", "")
    satker = await _satker_aktif(tujuan_id)
    if tujuan_id != lama.get("satker_luar_id"):
        lama_satker = await db.satker_luar.find_one(
            {"id": lama.get("satker_luar_id")}, {"_id": 0})
        galat = olu.periksa_penampungan(lama_satker, satker)
        if galat:
            raise HTTPException(status_code=400, detail="; ".join(galat))
    payload.satker_luar_id = tujuan_id
    doc = await _siapkan(payload, satker)
    await _cek_nip(doc["nip"], kecuali_id=orang_id)
    changes = _perubahan(lama, doc)
    doc.update({"updated_at": _kini(), "version": versi_kini + 1,
                "diubah_oleh": _jejak(user)})
    filter_versi = {"id": orang_id, "version": versi_kini}
    if versi_kini == 1:
        filter_versi = {"id": orang_id, "$or": [
            {"version": 1}, {"version": {"$exists": False}}, {"version": None}]}
    try:
        res = await db.pegawai_luar.update_one(filter_versi, {"$set": doc})
    except Exception as e:
        if _duplikat(e):
            raise HTTPException(status_code=400, detail=(
                f"NIP/NIK {doc['nip']} baru saja didaftarkan — muat ulang"))
        raise
    if res.matched_count == 0:
        raise HTTPException(status_code=409, detail=(
            "Data orang luar telah berubah. Muat ulang sebelum menyimpan."))
    await _audit("luar_orang_ubah", orang_id, user,
                 f"Ubah orang luar {doc['nama']}", changes)
    return {"ok": True, "id": orang_id,
            "peringatan": olu.peringatan_orang_luar(doc, doc["kelompok"])}


@pegawai_luar_router.delete("/pegawai-luar/{orang_id}")
async def hapus_pegawai_luar(orang_id: str, user: dict = Depends(require_super_admin)):
    """Hapus permanen (super-admin). Rujukan dihitung LINTAS satker — aset dan
    BAST — tetapi pesannya tidak merinci satker mana."""
    orang = await _orang_atau_404(orang_id, {"_id": 0})
    nip = str(orang.get("nip") or "").strip()
    dirujuk = 0
    if nip:
        dirujuk += await db.assets.count_documents(
            {"pengguna_nip": nip, "dihapus": {"$ne": True}})
    dirujuk += await db.bast_serah_terima.count_documents({"$or": [
        {"pihak_kesatu.pegawai_id": orang_id}, {"pihak_kedua.pegawai_id": orang_id},
        {"pj_tambahan.pegawai_id": orang_id}]})
    if dirujuk:
        raise HTTPException(status_code=409, detail=(
            "Orang ini masih dirujuk aset atau berita acara — nonaktifkan saja"))
    from bson import ObjectId
    for fid in (orang.get("foto_file_id"), orang.get("foto_asli_file_id")):
        if fid:
            try:
                await fs_bucket.delete(ObjectId(fid))
            except Exception:
                pass
    await db.pegawai_luar.delete_one({"id": orang_id})
    await _audit("luar_orang_hapus", orang_id, user,
                 f"Hapus orang luar {orang.get('nama', '')}")
    return {"ok": True, "id": orang_id}


# ── foto ───────────────────────────────────────────────────────────────────
@pegawai_luar_router.post("/pegawai-luar/{orang_id}/foto")
async def upload_foto_pegawai_luar(orang_id: str, file: UploadFile = File(...),
                                   file_asli: UploadFile = File(None),
                                   krop: str = Form(""),
                                   admin: dict = Depends(require_admin)):
    orang = await _orang_atau_404(orang_id, {
        "_id": 0, "id": 1, "nama": 1, "foto_file_id": 1, "foto_asli_file_id": 1})
    if (file.content_type or "") not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format harus JPG/PNG/WebP")
    data = await file.read()
    if len(data) > _FOTO_MAX:
        raise HTTPException(status_code=400, detail="Ukuran foto maksimal 5MB")
    from shared_utils import cek_magic_gambar
    _ext_ct = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if not cek_magic_gambar(data, _ext_ct.get(file.content_type or "", "")):
        raise HTTPException(status_code=400, detail="Isi berkas tidak cocok tipe gambar")
    from bson import ObjectId
    from gerbang_media import tulis_media
    fid, _meta = await tulis_media(
        data, nama=f"pegawai_luar_{orang_id}.jpg", content_type=file.content_type,
        metadata={"jenis": "foto_pegawai_luar", "pegawai_luar_id": orang_id})
    perubahan = {"foto_file_id": str(fid), "updated_at": _kini()}
    if file_asli is not None:
        asli_raw = await file_asli.read()
        if len(asli_raw) > _FOTO_MAX:
            raise HTTPException(status_code=400, detail="Ukuran foto asli maksimal 5MB")
        aid, _ = await tulis_media(
            _kecilkan_foto_asli(asli_raw), nama=f"pegawai_luar_{orang_id}_asli.jpg",
            content_type="image/jpeg",
            metadata={"jenis": "foto_pegawai_luar_asli", "pegawai_luar_id": orang_id})
        if orang.get("foto_asli_file_id"):
            try:
                await fs_bucket.delete(ObjectId(orang["foto_asli_file_id"]))
            except Exception:
                pass
        perubahan["foto_asli_file_id"] = str(aid)
    if str(krop or "").strip():
        try:
            perubahan["foto_krop"] = json.loads(krop)
        except (ValueError, TypeError):
            pass
    if orang.get("foto_file_id"):
        try:
            await fs_bucket.delete(ObjectId(orang["foto_file_id"]))
        except Exception:
            pass
    await db.pegawai_luar.update_one({"id": orang_id}, {"$set": perubahan})
    await _audit("luar_orang_foto", orang_id, admin,
                 f"Foto orang luar {orang.get('nama')} diperbarui")
    return {"ok": True, "foto_file_id": str(fid),
            "foto_asli_file_id": perubahan.get("foto_asli_file_id",
                                               orang.get("foto_asli_file_id") or "")}


async def _stream_foto(orang_id: str, field: str):
    orang = await db.pegawai_luar.find_one({"id": orang_id}, {"_id": 0, field: 1})
    if not orang or not orang.get(field):
        raise HTTPException(status_code=404, detail="Foto tidak ada")
    from bson import ObjectId
    try:
        stream = await fs_bucket.open_download_stream(ObjectId(orang[field]))
        data = await stream.read()
    except Exception:
        raise HTTPException(status_code=404, detail="Foto tidak ditemukan di penyimpanan")
    ct = (stream.metadata or {}).get("content_type") or "image/jpeg"
    return Response(content=data, media_type=ct,
                    headers={"Cache-Control": "private, max-age=86400",
                             "X-Content-Type-Options": "nosniff"})


@pegawai_luar_router.get("/pegawai-luar/{orang_id}/foto-asli")
async def get_foto_asli_pegawai_luar(orang_id: str,
                                     _user: dict = Depends(require_user_or_query_token)):
    return await _stream_foto(orang_id, "foto_asli_file_id")


@pegawai_luar_router.get("/pegawai-luar/{orang_id}/foto")
async def get_foto_pegawai_luar(orang_id: str,
                                _user: dict = Depends(require_user_or_query_token)):
    return await _stream_foto(orang_id, "foto_file_id")


@pegawai_luar_router.delete("/pegawai-luar/{orang_id}/foto")
async def hapus_foto_pegawai_luar(orang_id: str, admin: dict = Depends(require_admin)):
    orang = await _orang_atau_404(orang_id, {
        "_id": 0, "nama": 1, "foto_file_id": 1, "foto_asli_file_id": 1})
    if not orang.get("foto_file_id"):
        raise HTTPException(status_code=404, detail="Foto tidak ada")
    from bson import ObjectId
    for fid in (orang.get("foto_file_id"), orang.get("foto_asli_file_id")):
        if fid:
            try:
                await fs_bucket.delete(ObjectId(fid))
            except Exception:
                pass
    await db.pegawai_luar.update_one(
        {"id": orang_id},
        {"$unset": {"foto_file_id": "", "foto_asli_file_id": "", "foto_krop": ""},
         "$set": {"updated_at": _kini()}})
    await _audit("luar_orang_foto", orang_id, admin,
                 f"Foto orang luar {orang.get('nama')} dihapus")
    return {"ok": True}


# ── kartu ──────────────────────────────────────────────────────────────────
@pegawai_luar_router.post("/pegawai-luar/{orang_id}/kartu")
@limiter.limit("10/minute")
async def daftar_kartu_pegawai_luar(request: Request, orang_id: str, payload: KartuIn,
                                    admin: dict = Depends(require_admin)):
    """Satu kartu hanya untuk satu orang — dicek ke direktori luar DAN ke
    pegawai internal (invarian 5). Pemilik internal tidak pernah disebut."""
    err = valid_uid(payload.uid)
    if err:
        raise HTTPException(status_code=400, detail=err)
    orang = await _orang_atau_404(orang_id)
    hashes = hash_kandidat(payload.uid)
    if await db.pegawai.find_one({"kartu_uid_hashes": {"$in": hashes}}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=(
            "Kartu ini sudah terdaftar pada pegawai internal — tidak dapat "
            "dipakai orang luar"))
    lain = await db.pegawai_luar.find_one(
        {"kartu_uid_hashes": {"$in": hashes}, "id": {"$ne": orang_id}},
        {"_id": 0, "nama": 1})
    if lain:
        raise HTTPException(status_code=409, detail=(
            f"Kartu ini sudah terdaftar pada orang luar lain ({lain.get('nama') or '-'})"
            ". Lepas dulu dari orang tersebut."))
    label = label_kartu(payload.uid)
    now = _kini()
    try:
        await db.pegawai_luar.update_one({"id": orang_id}, {"$set": {
            "kartu_uid_hashes": hashes, "kartu_label": label,
            "kartu_terdaftar_pada": now,
            "kartu_terdaftar_oleh": admin.get("username", "system"),
            "updated_at": now}})
    except Exception:
        raise HTTPException(status_code=409, detail=(
            "Kartu baru saja terdaftar pada orang lain — muat ulang lalu coba lagi."))
    await _audit("luar_orang_kartu", orang_id, admin,
                 f"Daftarkan kartu {label} untuk {orang.get('nama') or '-'}")
    return {"ok": True, "kartu_label": label, "kartu_terdaftar_pada": now}


@pegawai_luar_router.delete("/pegawai-luar/{orang_id}/kartu")
@limiter.limit("10/minute")
async def lepas_kartu_pegawai_luar(request: Request, orang_id: str,
                                   admin: dict = Depends(require_admin)):
    orang = await _orang_atau_404(orang_id, {
        "_id": 0, "nama": 1, "kartu_label": 1, "kartu_uid_hashes": 1})
    if not orang.get("kartu_uid_hashes"):
        raise HTTPException(status_code=404, detail="Orang ini belum punya kartu terdaftar")
    await db.pegawai_luar.update_one({"id": orang_id}, {
        "$unset": {"kartu_uid_hashes": "", "kartu_label": "",
                   "kartu_terdaftar_pada": "", "kartu_terdaftar_oleh": ""},
        "$set": {"updated_at": _kini()}})
    await _audit("luar_orang_kartu", orang_id, admin,
                 f"Lepas kartu {orang.get('kartu_label') or ''} dari {orang.get('nama') or '-'}")
    return {"ok": True}
