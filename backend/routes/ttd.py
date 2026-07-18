"""Tanda Tangan Digital — spesimen TTD & pemrosesan foto (Mandat-2).

Slice 1: kelola SPESIMEN tanda tangan per pejabat/pegawai (gambar PNG
transparan dari kanvas goresan mulus ATAU foto kertas yang di-hapus
background-nya via Pillow), tersimpan di GridFS. Blok tanda tangan PDF
(reports.py `_signature_block`) otomatis menyematkan spesimen KPB. Slice 2
(menyusul): e-sign via link per dokumen (`signature_requests`).
"""
import base64
import hashlib
import io
import os
import uuid
from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import (
    create_sign_token, require_admin, require_sign_token, require_user,
    require_user_or_query_token, require_user_or_sign_token, require_writer,
)
from db import db, fs_bucket
from shared_utils import (
    cek_magic_gambar, delete_document_from_gridfs, get_document_from_gridfs,
    log_audit,
)
from ttd_utils import foto_ke_png_transparan, png_transparan_valid

ttd_router = APIRouter()

_ENTITAS = {"pejabat": db.pejabat, "pegawai": db.pegawai}
_PROJ = {"_id": 0}

# Basis URL publik untuk link tanda tangan (frontend). Tanpa APP_PUBLIC_URL,
# jatuh ke origin CORS pertama (deploy nyata selalu mengisinya) supaya link
# yang dibagikan & QR verifikasi TIDAK pernah berupa path relatif yang mati.
# ALLOWED_ORIGINS dibaca lebih dulu — server.py memprioritaskannya untuk CORS;
# CORS_ORIGINS dipertahankan sebagai nama legacy.
def _basis_url_publik() -> str:
    u = os.environ.get("APP_PUBLIC_URL", "").strip().rstrip("/")
    if u:
        return u
    sumber = (os.environ.get("ALLOWED_ORIGINS", "")
              or os.environ.get("CORS_ORIGINS", ""))
    for o in sumber.split(","):
        o = o.strip().rstrip("/")
        if o.startswith("http") and "localhost" not in o:
            return o
    return ""


_APP_URL = _basis_url_publik()


class SpesimenIn(BaseModel):
    png_base64: str   # data-URL atau base64 murni PNG transparan


def _png_dari_base64(s: str) -> bytes:
    raw = str(s or "").strip()
    if "," in raw and raw.lower().startswith("data:"):
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=False)
    except Exception:
        raise HTTPException(status_code=400, detail="PNG base64 tidak valid")
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise HTTPException(status_code=400, detail="Berkas bukan PNG")
    if len(data) > 4 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Gambar TTD maksimal 4MB")
    return data


@ttd_router.post("/ttd/olah-foto")
async def olah_foto(file: UploadFile = File(...),
                    _user: dict = Depends(require_user_or_sign_token)):
    """Foto TTD di kertas → PNG TRANSPARAN (hapus background otomatis). Balikan
    pratinjau data-URL base64; klien menampilkan lalu menyimpannya sebagai
    spesimen bila puas. Juga bisa dipakai penanda tangan TAMU (?token= e-sign)
    dari halaman link publik."""
    nama = str(file.filename or "").lower()
    ext = next((e for e in (".jpg", ".jpeg", ".png", ".webp") if nama.endswith(e)), "")
    if not ext:
        raise HTTPException(status_code=400, detail="Foto harus JPG/PNG/WEBP")
    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto maksimal 12MB")
    if not cek_magic_gambar(data, ext):
        raise HTTPException(status_code=400, detail="Isi berkas tidak cocok ekstensi")
    try:
        png = foto_ke_png_transparan(data)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Gagal memproses foto — coba foto lebih terang/kontras")
    if not png_transparan_valid(png):
        raise HTTPException(status_code=400,
                            detail="Tanda tangan tak terdeteksi — pastikan goresan gelap di kertas terang")
    return {"png_base64": "data:image/png;base64," + base64.b64encode(png).decode()}


@ttd_router.put("/ttd/spesimen/{entitas}/{eid}")
async def simpan_spesimen(entitas: str, eid: str, payload: SpesimenIn,
                          admin: dict = Depends(require_admin)):
    """Simpan spesimen TTD (PNG transparan) untuk pejabat/pegawai → GridFS +
    field `ttd_file_id`. Spesimen lama dihapus (cegah orphan)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1, "nama": 1})
    if not doc:
        raise HTTPException(status_code=404, detail=f"{entitas} tidak ditemukan")
    data = _png_dari_base64(payload.png_base64)
    if not png_transparan_valid(data):
        raise HTTPException(status_code=400, detail="PNG TTD tidak valid / kosong")

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"ttd_{entitas}_{eid}.png",
        metadata={"content_type": "image/png", "kind": "ttd_spesimen",
                  "entitas": entitas, "eid": eid})
    await grid_in.write(data)
    await grid_in.close()

    lama = str(doc.get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": str(file_id)}})
    if lama and lama != str(file_id):
        await delete_document_from_gridfs(lama)
    await log_audit("simpan_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Spesimen TTD {entitas} {doc.get('nama') or eid}")
    return {"ok": True, "ttd_file_id": str(file_id)}


@ttd_router.get("/ttd/spesimen/{entitas}/{eid}")
async def lihat_spesimen(entitas: str, eid: str,
                         _user: dict = Depends(require_user_or_query_token)):
    """Stream gambar spesimen TTD (pratinjau)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1})
    fid = str((doc or {}).get("ttd_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404, detail="Spesimen TTD belum ada")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas TTD tidak ditemukan")
    return StreamingResponse(
        io.BytesIO(data), media_type="image/png",
        headers={"Content-Disposition": 'inline; filename="ttd.png"',
                 "X-Content-Type-Options": "nosniff",
                 "Cache-Control": "private, max-age=3600"})


@ttd_router.delete("/ttd/spesimen/{entitas}/{eid}")
async def hapus_spesimen(entitas: str, eid: str,
                         admin: dict = Depends(require_admin)):
    """Hapus spesimen TTD (dokumen kembali ke tanda tangan basah)."""
    coll = _ENTITAS.get(entitas)
    if coll is None:
        raise HTTPException(status_code=400, detail="Entitas harus pejabat/pegawai")
    doc = await coll.find_one({"id": eid}, {"_id": 0, "ttd_file_id": 1})
    fid = str((doc or {}).get("ttd_file_id") or "").strip()
    await coll.update_one({"id": eid}, {"$set": {"ttd_file_id": ""}})
    if fid:
        await delete_document_from_gridfs(fid)
    await log_audit("hapus_ttd_spesimen", "", eid,
                    username=admin.get("username", "system"),
                    detail=f"Hapus spesimen TTD {entitas}")
    return {"ok": True}


# ============================================================================
# E-SIGN VIA LINK — permintaan tanda tangan per dokumen (Mandat-2, slice 2)
# ============================================================================

class SignerIn(BaseModel):
    nama: str
    nip: str = ""
    jabatan: str = ""
    email: str = ""     # opsional — link dikirim otomatis via email bila diisi


class PermintaanIn(BaseModel):
    judul: str
    doc_type: str = "dokumen"          # bast|berita_acara|dokumen|…
    doc_ref: str = ""                  # id dokumen sumber (opsional)
    mode: str = "paralel"              # "berurutan" | "paralel"
    signers: List[SignerIn]


def _link_ttd(sr_id, token):
    rel = f"/ttd/{sr_id}?token={token}"
    return (_APP_URL + rel) if _APP_URL else rel


def _publik_signer(sg):
    """Bidang aman signer untuk halaman publik (tanpa jti/token)."""
    return {k: sg.get(k) for k in ("signer_id", "nama", "nip", "jabatan",
                                   "urutan", "status", "signed_at")}


@ttd_router.post("/ttd/permintaan")
async def buat_permintaan(payload: PermintaanIn, user: dict = Depends(require_writer)):
    """Buat permintaan tanda tangan + link per penanda tangan. Mode berurutan:
    hanya penanda tangan urutan pertama yang 'aktif'; paralel: semua aktif."""
    if not payload.signers:
        raise HTTPException(status_code=400, detail="Minimal satu penanda tangan")
    if payload.mode not in ("berurutan", "paralel"):
        raise HTTPException(status_code=400, detail="Mode harus berurutan/paralel")
    now = datetime.now(timezone.utc)
    sr_id = str(uuid.uuid4())
    signers, links = [], []
    urut = 1
    for s in payload.signers:
        if not str(s.nama or "").strip():
            raise HTTPException(status_code=400, detail="Nama penanda tangan wajib")
        signer_id = str(uuid.uuid4())
        jti = str(uuid.uuid4())
        aktif = (payload.mode == "paralel") or (urut == 1)
        signers.append({
            "signer_id": signer_id, "nama": s.nama.strip(),
            "nip": str(s.nip or "").strip(), "jabatan": str(s.jabatan or "").strip(),
            "email": str(s.email or "").strip(),
            "urutan": urut, "status": "aktif" if aktif else "menunggu",
            "jti": jti, "signature_file_id": "", "hash": "",
            "signed_at": "", "ip": ""})
        token = create_sign_token(sr_id, signer_id, jti)
        link = _link_ttd(sr_id, token)
        email_terkirim = False
        if aktif and str(s.email or "").strip():
            from shared_utils import send_esign_email
            email_terkirim = await send_esign_email(
                s.email, s.nama.strip(), payload.judul.strip() or "Dokumen", link)
        links.append({"nama": s.nama.strip(), "link": link,
                      "email": str(s.email or "").strip(),
                      "email_terkirim": email_terkirim})
        urut += 1
    record = {
        "id": sr_id, "judul": payload.judul.strip() or "Dokumen",
        "doc_type": str(payload.doc_type or "dokumen"),
        "doc_ref": str(payload.doc_ref or ""), "mode": payload.mode,
        "status": "terkirim", "signers": signers,
        "created_by": user.get("username", "system"),
        "created_at": now.isoformat(),
    }
    await db.signature_requests.insert_one({**record})
    await log_audit("buat_permintaan_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=f"Permintaan TTD '{record['judul']}' — {len(signers)} penanda tangan")
    return {"id": sr_id, "judul": record["judul"], "mode": record["mode"],
            "links": links}


@ttd_router.get("/ttd/permintaan")
async def daftar_permintaan(_user: dict = Depends(require_user)):
    """Daftar permintaan tanda tangan (terbaru dulu) + ringkas status.
    Non-admin hanya melihat permintaan buatannya sendiri; IP penanda tangan
    tidak pernah ikut daftar (data forensik — cukup di audit internal)."""
    q = ({} if _user.get("role") == "admin"
         else {"created_by": _user.get("username", "")})
    items = await (db.signature_requests.find(
        q, {**_PROJ, "signers.jti": 0, "signers.ip": 0})
                   .sort("created_at", -1).limit(200).to_list(200))
    for it in items:
        sg = it.get("signers") or []
        it["jumlah"] = len(sg)
        it["selesai_jumlah"] = sum(1 for s in sg if s.get("status") == "ditandatangani")
    return {"items": items}


@ttd_router.get("/ttd/permintaan/{sr_id}")
async def detail_permintaan(sr_id: str, _user: dict = Depends(require_user)):
    """Detail status per penanda tangan (untuk dasbor pembuat)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, {**_PROJ, "signers.jti": 0})
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    return sr


@ttd_router.delete("/ttd/permintaan/{sr_id}")
async def batal_permintaan(sr_id: str, user: dict = Depends(require_writer)):
    """Batalkan permintaan (hanya pembuat atau admin)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, {"_id": 0, "created_by": 1})
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    if sr.get("created_by") != user.get("username") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya pembuat/admin dapat membatalkan")
    await db.signature_requests.update_one({"id": sr_id}, {"$set": {"status": "batal"}})
    return {"ok": True}


@ttd_router.post("/ttd/permintaan/{sr_id}/link/{signer_id}")
async def buat_ulang_link(sr_id: str, signer_id: str,
                          user: dict = Depends(require_writer)):
    """Terbitkan ULANG link e-sign seorang penanda tangan (pembuat/admin) —
    dipakai bila link hilang setelah dialog pembuatan ditutup, atau link lama
    kedaluwarsa/tersebar keliru. jti BARU dibuat sehingga link lama langsung
    MATI (sekali-pakai tetap terjaga). Ditolak bila sudah ditandatangani."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    if sr.get("created_by") != user.get("username") and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Hanya pembuat/admin dapat menerbitkan ulang link")
    signers = sr.get("signers") or []
    idx = next((i for i, s in enumerate(signers)
                if s.get("signer_id") == signer_id), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    if signers[idx].get("status") == "ditandatangani":
        raise HTTPException(status_code=409, detail="Sudah ditandatangani — link tidak diperlukan")
    jti = str(uuid.uuid4())
    await db.signature_requests.update_one(
        {"id": sr_id, "signers.signer_id": signer_id},
        {"$set": {"signers.$.jti": jti}})
    token = create_sign_token(sr_id, signer_id, jti)
    link = _link_ttd(sr_id, token)
    email_terkirim = False
    if str(signers[idx].get("email") or "").strip():
        from shared_utils import send_esign_email
        email_terkirim = await send_esign_email(
            signers[idx]["email"], signers[idx].get("nama"),
            sr.get("judul") or "Dokumen", link)
    await log_audit("terbit_ulang_link_ttd", "", sr_id,
                    username=user.get("username", "system"),
                    detail=f"Link e-sign diterbitkan ulang untuk {signers[idx].get('nama')}")
    return {"nama": signers[idx].get("nama"), "status": signers[idx].get("status"),
            "link": link, "email_terkirim": email_terkirim}


@ttd_router.get("/ttd/tandatangan/{sr_id}")
async def info_tandatangan(sr_id: str, tok: dict = Depends(require_sign_token)):
    """Info dokumen + penanda tangan untuk HALAMAN PUBLIK (link e-sign)."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    sg = next((s for s in sr.get("signers") or [] if s.get("signer_id") == tok["signer"]), None)
    if not sg:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    # Link LAMA yang jti-nya sudah diganti (terbit ulang) harus mati juga di
    # halaman info — bukan hanya saat kirim.
    if sg.get("jti") != tok["jti"]:
        raise HTTPException(status_code=401,
                            detail="Link ini sudah tidak berlaku (telah diterbitkan ulang)")
    bisa = sg.get("status") == "aktif"
    alasan = ""
    if sg.get("status") == "ditandatangani":
        alasan = "Anda sudah menandatangani dokumen ini."
    elif sg.get("status") == "menunggu":
        alasan = "Menunggu giliran penanda tangan sebelumnya (mode berurutan)."
    return {"id": sr_id, "judul": sr.get("judul"), "doc_type": sr.get("doc_type"),
            "mode": sr.get("mode"), "status_dokumen": sr.get("status"),
            "penanda_tangan": _publik_signer(sg), "boleh_ttd": bisa,
            "alasan": alasan}


@ttd_router.post("/ttd/tandatangan/{sr_id}/kirim")
async def kirim_tandatangan(sr_id: str, payload: SpesimenIn, request: Request,
                            tok: dict = Depends(require_sign_token)):
    """Kirim gambar tanda tangan (PNG transparan) via link publik."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr or sr.get("status") == "batal":
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan/dibatalkan")
    signers = sr.get("signers") or []
    idx = next((i for i, s in enumerate(signers) if s.get("signer_id") == tok["signer"]), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail="Penanda tangan tidak dikenal")
    sg = signers[idx]
    if sg.get("jti") != tok["jti"] or sg.get("status") == "ditandatangani":
        raise HTTPException(status_code=409, detail="Link sudah dipakai / tidak berlaku")
    if sg.get("status") != "aktif":
        raise HTTPException(status_code=409, detail="Belum giliran Anda menandatangani")

    data = _png_dari_base64(payload.png_base64)
    if not png_transparan_valid(data):
        raise HTTPException(status_code=400, detail="Tanda tangan tidak valid / kosong")
    now = datetime.now(timezone.utc)
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=f"ttd_sign_{sr_id}_{sg['signer_id']}.png",
        metadata={"content_type": "image/png", "kind": "ttd_sign", "sr": sr_id})
    await grid_in.write(data)
    await grid_in.close()
    h = hashlib.sha256(data + sg["signer_id"].encode() + now.isoformat().encode()).hexdigest()

    # TULIS ATOMIK per-signer ($elemMatch + operator posisional) — BUKAN
    # menulis balik seluruh array. Dua penanda tangan PARALEL yang submit
    # bersamaan tidak lagi saling menimpa (lost-update), dan filter jti/
    # status/batal di sini menutup jendela race pembatalan/link-lama yang
    # terbuka selama upload GridFS multi-await di atas.
    res = await db.signature_requests.update_one(
        {"id": sr_id, "status": {"$ne": "batal"},
         "signers": {"$elemMatch": {"signer_id": tok["signer"],
                                    "jti": tok["jti"], "status": "aktif"}}},
        {"$set": {"signers.$.status": "ditandatangani",
                  "signers.$.signature_file_id": str(file_id),
                  "signers.$.hash": h,
                  "signers.$.signed_at": now.isoformat(),
                  "signers.$.ip": (request.client.host if request.client else "")}})
    if res.modified_count == 0:
        # Kalah race (sudah ttd / dibatalkan / link diganti) — bersihkan blob.
        try:
            await fs_bucket.delete(file_id)
        except Exception:
            pass
        raise HTTPException(status_code=409,
                            detail="Link sudah dipakai / permintaan berubah — muat ulang halaman")

    # Langkah 2 (idempoten, baca kondisi TERKINI): aktifkan giliran berikutnya
    # (mode berurutan) & hitung status dokumen dari keadaan nyata.
    segar = await db.signature_requests.find_one(
        {"id": sr_id}, {"_id": 0, "mode": 1, "status": 1, "judul": 1,
                        "signers.status": 1, "signers.signer_id": 1,
                        "signers.jti": 1, "signers.email": 1, "signers.nama": 1})
    signers_segar = (segar or {}).get("signers") or []
    if (segar or {}).get("mode") == "berurutan":
        nxt_sg = next((s for s in signers_segar
                       if s.get("status") == "menunggu"), None)
        if nxt_sg:
            res_nxt = await db.signature_requests.update_one(
                {"id": sr_id, "status": {"$ne": "batal"},
                 "signers": {"$elemMatch": {"signer_id": nxt_sg["signer_id"],
                                            "status": "menunggu"}}},
                {"$set": {"signers.$.status": "aktif"}})
            # Giliran maju → beri tahu penanda tangan berikutnya via email
            # (best-effort; link memakai jti tersimpan — token identik dgn
            # yang dibagikan pembuat, jadi tidak mematikan link lama).
            if res_nxt.modified_count and str(nxt_sg.get("email") or "").strip():
                from shared_utils import send_esign_email
                tok_nxt = create_sign_token(sr_id, nxt_sg["signer_id"],
                                            nxt_sg.get("jti") or "")
                await send_esign_email(
                    nxt_sg["email"], nxt_sg.get("nama") or "",
                    (segar or {}).get("judul") or "Dokumen",
                    _link_ttd(sr_id, tok_nxt))
    semua = bool(signers_segar) and all(
        s.get("status") == "ditandatangani" for s in signers_segar)
    status_dok = "selesai" if semua else "sebagian"
    # "sebagian" tidak boleh menimpa "selesai" — dua submit paralel bisa
    # membuat pembacaan basi; status final hanya bergerak maju.
    kunci_status = (["batal"] if semua else ["batal", "selesai"])
    await db.signature_requests.update_one(
        {"id": sr_id, "status": {"$nin": kunci_status}},
        {"$set": {"status": status_dok}})
    await log_audit("kirim_ttd", "", sr_id, username=sg.get("nama") or "tamu",
                    detail=f"E-sign '{sr.get('judul')}' oleh {sg.get('nama')}")
    return {"ok": True, "status_dokumen": status_dok,
            "verifikasi": f"/ttd/verifikasi/{sr_id}"}


@ttd_router.get("/ttd/tandatangan/{sr_id}/gambar/{signer_id}")
async def gambar_ttd_signer(sr_id: str, signer_id: str,
                            _user: dict = Depends(require_user_or_query_token)):
    """Stream gambar tanda tangan seorang penanda tangan (pratinjau dasbor)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    sg = next((s for s in (sr or {}).get("signers") or []
               if s.get("signer_id") == signer_id), None)
    fid = str((sg or {}).get("signature_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404, detail="Belum ditandatangani")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return StreamingResponse(io.BytesIO(data), media_type="image/png",
                             headers={"X-Content-Type-Options": "nosniff",
                                      "Content-Disposition": 'inline; filename="ttd.png"'})


@ttd_router.get("/ttd/verifikasi/{sr_id}")
async def verifikasi_publik(sr_id: str):
    """Verifikasi PUBLIK keabsahan e-sign (dibuka dari QR). Tanpa token —
    hanya menampilkan siapa menandatangani & kapan (bukan gambar/hash mentah)."""
    sr = await db.signature_requests.find_one(
        {"id": sr_id}, {"_id": 0, "judul": 1, "doc_type": 1, "status": 1,
                        "created_at": 1, "signers.nama": 1, "signers.jabatan": 1,
                        "signers.nip": 1, "signers.status": 1, "signers.signed_at": 1})
    if not sr:
        raise HTTPException(status_code=404, detail="Dokumen tidak ditemukan")
    return {
        "judul": sr.get("judul"), "doc_type": sr.get("doc_type"),
        "status": sr.get("status"), "dibuat": sr.get("created_at"),
        "penanda_tangan": [
            {"nama": s.get("nama"), "jabatan": s.get("jabatan"),
             "nip": s.get("nip"), "status": s.get("status"),
             "signed_at": s.get("signed_at")}
            for s in sr.get("signers") or []],
        "catatan": ("Tanda tangan elektronik internal satker (integritas + "
                    "jejak audit). Sah tanpa tanda tangan basah untuk keperluan "
                    "administrasi internal."),
    }


@ttd_router.get("/ttd/permintaan/{sr_id}/lembar-pdf")
async def lembar_pdf(sr_id: str, _user: dict = Depends(require_user_or_query_token)):
    """Lembar Pengesahan Tanda Tangan Elektronik: judul dokumen + daftar
    penanda tangan dengan GAMBAR tanda tangan, waktu, NIP, dan QR verifikasi."""
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table

    from routes.reports import (
        _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _std_doc, _std_table_style, _title_block,
    )

    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    settings = await db.report_settings.find_one({"type": "global"}, _PROJ) or {}
    st = _get_report_styles()
    buffer = io.BytesIO()
    doc = _std_doc(buffer)
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("LEMBAR PENGESAHAN\nTANDA TANGAN ELEKTRONIK",
                           subjudul=sr.get("judul")))
    el.append(Paragraph(
        f"Dokumen: <b>{sr.get('judul')}</b> · Mode: {sr.get('mode')} · "
        f"Status: {sr.get('status')}", st['Meta']))
    el.append(Spacer(1, 3 * rl_mm))

    from xml.sax.saxutils import escape as _esc
    baris = [[Paragraph(h, st['TableHeader']) for h in
              ("No", "Nama & Jabatan", "Tanda Tangan", "Waktu")]]
    for i, s in enumerate(sr.get("signers") or [], 1):
        idn = f"<b>{_esc(s.get('nama') or '-')}</b>"
        if s.get("jabatan"):
            idn += f"<br/><font size=8>{_esc(s['jabatan'])}</font>"
        if s.get("nip"):
            idn += f"<br/><font size=8>NIP. {_esc(s['nip'])}</font>"
        ttd_cell = Paragraph("<font size=8 color='#94a3b8'>belum ditandatangani</font>", st['Cell'])
        fid = str(s.get("signature_file_id") or "").strip()
        if fid:
            data = await get_document_from_gridfs(fid)
            if data:
                try:
                    img = RLImage(io.BytesIO(data), mask='auto')
                    sk = min((doc.width * 0.22) / img.imageWidth, (16 * rl_mm) / img.imageHeight)
                    img.drawWidth, img.drawHeight = img.imageWidth * sk, img.imageHeight * sk
                    ttd_cell = img
                except Exception:
                    pass
        waktu = _fmt_tanggal_id(s.get("signed_at", "")[:10]) if s.get("signed_at") else "-"
        baris.append([Paragraph(str(i), st['CellCenter']),
                      Paragraph(idn, st['Cell']), ttd_cell,
                      Paragraph(waktu, st['CellCenter'])])
    t = Table(baris, colWidths=[doc.width * 0.08, doc.width * 0.40,
                                doc.width * 0.32, doc.width * 0.20], repeatRows=1)
    t.setStyle(_std_table_style(zebra=True))
    el.append(t)
    el.append(Spacer(1, 5 * rl_mm))

    # QR verifikasi.
    try:
        from routes.cards import build_qr_flowable
        verif = (_APP_URL + f"/ttd/verifikasi/{sr_id}") if _APP_URL else f"/ttd/verifikasi/{sr_id}"
        el.append(build_qr_flowable(verif, 28 * rl_mm))
    except Exception:
        pass
    el.append(Paragraph(
        "Ditandatangani secara elektronik — sah tanpa tanda tangan basah untuk "
        f"keperluan administrasi internal satker. Verifikasi kode: {sr_id[:8]}.",
        st['Small']))

    footer = _page_footer_factory("Lembar Pengesahan TTD Elektronik")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="Lembar_TTD_{sr_id[:8]}.pdf"'})
