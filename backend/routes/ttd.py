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
from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth_utils import (
    create_sign_token, require_admin, require_sign_token, require_user,
    require_user_or_query_token, require_user_or_sign_token, require_writer,
)
from db import db, fs_bucket
from shared_utils import (
    cek_magic_gambar, delete_document_from_gridfs, get_document_from_gridfs,
    limiter, log_audit,
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
    # Posisi pembubuhan pilihan PENANDA TANGAN pada dokumen terlampir
    # (opsional — tanpa ini stempel memakai slot otomatis halaman terakhir):
    # {halaman: 1-based, x, y: pojok kiri-atas kotak ttd sebagai FRAKSI
    #  lebar/tinggi halaman, lebar: fraksi lebar halaman}.
    posisi: dict | None = None
    # Posisi & UKURAN QR verifikasi pilihan (dokumen-level; None = otomatis
    # pojok kanan-bawah halaman terakhir). {halaman, x, y, lebar} fraksi.
    posisi_qr: dict | None = None


def _posisi_bersih(p, maks_halaman: int = 0):
    """Validasi + jepit posisi pembubuhan dari klien; None bila tak dipakai.

    Tahan nilai liar apa pun dari JSON: Infinity/NaN (json.loads menerimanya)
    ditolak eksplisit — int(inf) melempar OverflowError, NaN merusak jepitan.
    x dijepit BERPASANGAN dengan lebar agar kotak tidak keluar tepi kanan.
    """
    if not isinstance(p, dict):
        return None
    import math
    try:
        halaman_f = float(p.get("halaman"))
        x = float(p.get("x")); y = float(p.get("y"))
        lebar = float(p.get("lebar"))
        if not all(math.isfinite(v) for v in (halaman_f, x, y, lebar)):
            return None
        halaman = int(halaman_f)
    except (TypeError, ValueError, OverflowError):
        return None
    if halaman < 1:
        return None
    if maks_halaman and halaman > maks_halaman:
        halaman = maks_halaman
    lebar = min(0.6, max(0.08, lebar))
    return {"halaman": halaman,
            "x": min(1.0 - lebar, max(0.0, x)),
            "y": min(0.95, max(0.0, y)),
            "lebar": lebar}


# Sisi QR verifikasi minimal (mutlak) agar tetap dapat dipindai — ditegakkan
# saat render, apa pun ukuran halaman. ±2cm cukup untuk kamera HP biasa.
QR_MIN_MM = 20.0


def _posisi_qr_bersih(p, maks_halaman: int = 0):
    """Validasi + jepit posisi & UKURAN QR verifikasi pilihan (dokumen-level).

    Seperti _posisi_bersih namun untuk QR: `lebar` (= sisi kotak QR sebagai
    fraksi lebar halaman) dijepit 0.10–0.40 agar tak terlalu kecil (gagal
    scan) atau terlalu besar. Batas MUTLAK (QR_MIN_MM) ditegakkan lagi saat
    render karena fraksi bergantung lebar halaman. None → QR pakai slot
    otomatis (pojok kanan-bawah halaman terakhir, perilaku lama)."""
    if not isinstance(p, dict):
        return None
    import math
    try:
        halaman_f = float(p.get("halaman"))
        x = float(p.get("x")); y = float(p.get("y"))
        lebar = float(p.get("lebar"))
        if not all(math.isfinite(v) for v in (halaman_f, x, y, lebar)):
            return None
        halaman = int(halaman_f)
    except (TypeError, ValueError, OverflowError):
        return None
    if halaman < 1:
        return None
    if maks_halaman and halaman > maks_halaman:
        halaman = maks_halaman
    lebar = min(0.40, max(0.10, lebar))
    return {"halaman": halaman,
            "x": min(1.0 - lebar, max(0.0, x)),
            "y": min(0.95, max(0.0, y)),
            "lebar": lebar}


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
@limiter.limit("20/minute")
async def olah_foto(request: Request, file: UploadFile = File(...),
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


@ttd_router.post("/ttd/permintaan/unggah")
async def buat_permintaan_dengan_dokumen(
    file: UploadFile = File(...),
    judul: str = Form(""),
    mode: str = Form("paralel"),
    signers: str = Form("[]"),
    user: dict = Depends(require_writer),
):
    """Permintaan TTD DENGAN dokumen PDF terlampir (permintaan pemilik):
    kirim dokumen yang hendak di-ttd LANGSUNG — penanda tangan meneken via
    link seperti biasa, lalu tanda tangan DIBUBUHKAN ke halaman terakhir
    dokumen (unduh 'Dokumen ber-TTD')."""
    nama = str(file.filename or "").lower()
    if not nama.endswith(".pdf"):
        raise HTTPException(status_code=400,
                            detail="Dokumen harus berformat PDF")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Maksimal 20MB")
    try:
        from pypdf import PdfReader
        n_hal = len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Berkas PDF tidak dapat dibaca/terenkripsi")
    import json as _json
    try:
        daftar = _json.loads(signers or "[]")
        assert isinstance(daftar, list)
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Format daftar penanda tangan tidak valid")
    payload = PermintaanIn(
        judul=str(judul or "").strip() or str(file.filename or "Dokumen"),
        doc_type="dokumen_unggahan", doc_ref="", mode=mode,
        signers=[SignerIn(
            nama=str((s or {}).get("nama") or ""),
            nip=str((s or {}).get("nip") or ""),
            jabatan=str((s or {}).get("jabatan") or ""),
            email=str((s or {}).get("email") or ""),
        ) for s in daftar])
    hasil = await buat_permintaan(payload=payload, user=user)

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=file.filename,
        metadata={"content_type": "application/pdf", "size": len(data)})
    await grid_in.write(data)
    await grid_in.close()
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id),
                  "dok_nama": str(file.filename or "dokumen.pdf"),
                  "dok_halaman": n_hal}})
    return {**hasil, "dok_nama": file.filename, "dok_halaman": n_hal}


def _mask_nip(nip) -> str:
    """Masking NIP untuk tampilan publik: hanya 3 digit terakhir terlihat."""
    s = str(nip or "").strip()
    if len(s) <= 3:
        return s
    return "•" * (len(s) - 3) + s[-3:]


def _pastikan_pemilik_sr(sr: dict, user: dict) -> None:
    """403 bila user bukan pembuat permintaan & bukan admin (cegah IDOR:
    dokumen/PII penanda tangan hanya untuk pembuat & admin)."""
    if (sr or {}).get("created_by") != (user or {}).get("username") and \
            (user or {}).get("role") != "admin":
        raise HTTPException(status_code=403,
                            detail="Hanya pembuat permintaan atau admin yang berhak")


async def _ambil_dokumen_sr(sr_id: str):
    """(sr, bytes PDF asli) — 404 bila permintaan/dokumen tak ada."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    fid = str(sr.get("dok_file_id") or "").strip()
    if not fid:
        raise HTTPException(status_code=404,
                            detail="Permintaan ini tidak melampirkan dokumen")
    data = await get_document_from_gridfs(fid)
    if not data:
        raise HTTPException(status_code=404, detail="Berkas dokumen tidak ditemukan")
    return sr, data


@ttd_router.get("/ttd/permintaan/{sr_id}/dokumen")
async def dokumen_asli(sr_id: str,
                       user: dict = Depends(require_user_or_query_token)):
    """Stream dokumen PDF asli (pratinjau dasbor pembuat)."""
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_pemilik_sr(sr, user)
    return StreamingResponse(
        io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{sr.get("dok_nama", "dokumen.pdf")}"',
                 "X-Content-Type-Options": "nosniff"})


def _pastikan_jti_signer(sr: dict, tok: dict):
    """401 bila token bukan milik signer terdaftar ATAU jti-nya sudah diganti
    (terbit ulang) — link lama yang dicabut tidak boleh lagi membaca dokumen."""
    sg = next((s for s in (sr.get("signers") or [])
               if s.get("signer_id") == tok.get("signer")), None)
    if not sg or sg.get("jti") != tok.get("jti"):
        raise HTTPException(status_code=401,
                            detail="Link ini sudah tidak berlaku (telah diterbitkan ulang)")


@ttd_router.get("/ttd/tandatangan/{sr_id}/dokumen")
async def dokumen_untuk_penanda_tangan(sr_id: str,
                                       tok: dict = Depends(require_sign_token)):
    """Stream dokumen asli untuk PENANDA TANGAN (via link e-sign) — agar yang
    meneken bisa MEMBACA dulu apa yang ditandatanganinya."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_jti_signer(sr, tok)
    return StreamingResponse(
        io.BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{sr.get("dok_nama", "dokumen.pdf")}"',
                 # Content-Length → viewer PDF HP bisa menampilkan progres
                 # unduhan alih-alih layar kosong tanpa kabar.
                 "Content-Length": str(len(data)),
                 "X-Content-Type-Options": "nosniff"})


@ttd_router.get("/ttd/tandatangan/{sr_id}/dokumen/halaman/{no}")
@limiter.limit("60/minute")
async def halaman_dokumen_penanda_tangan(sr_id: str, no: int, request: Request,
                                         tok: dict = Depends(require_sign_token)):
    """Render SATU halaman dokumen sebagai PNG untuk PRATINJAU PEMBUBUHAN di
    halaman publik — penanda tangan memilih letak & ukuran tanda tangannya
    langsung di atas gambar halaman (tanpa perlu mengunduh PDF penuh)."""
    if tok["sr"] != sr_id:
        raise HTTPException(status_code=401, detail="Token tidak cocok dokumen")
    _sr, data = await _ambil_dokumen_sr(sr_id)
    _pastikan_jti_signer(_sr, tok)
    import pypdfium2 as pdfium
    try:
        pdf = pdfium.PdfDocument(io.BytesIO(data))
    except Exception:
        raise HTTPException(status_code=422, detail="Dokumen tidak dapat dirender")
    try:
        total = len(pdf)
        idx = min(max(1, int(no)), total) - 1
        page = pdf[idx]
        # Skala menuju lebar ±1100px — cukup tajam untuk pratinjau posisi,
        # ringan diunduh di jaringan seluler. Tinggi ikut dibatasi (halaman
        # ekstrem memanjang tidak boleh menghasilkan bitmap raksasa).
        skala = 1100 / max(1.0, page.get_width())
        skala = min(skala, 2400 / max(1.0, page.get_height()))
        skala = min(2.0, max(0.3, skala))
        pil = page.render(scale=skala).to_pil()
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        buf.seek(0)
    finally:
        pdf.close()
    return StreamingResponse(
        buf, media_type="image/png",
        headers={"Cache-Control": "private, max-age=600",
                 "X-Jumlah-Halaman": str(total),
                 "X-Content-Type-Options": "nosniff"})


@ttd_router.get("/ttd/permintaan/{sr_id}/dokumen-ttd")
async def dokumen_ber_ttd(sr_id: str,
                          user: dict = Depends(require_user_or_query_token)):
    """Dokumen PDF asli DENGAN BUBUHAN tanda tangan elektronik di halaman
    terakhir: gambar ttd + nama/NIP/jabatan + waktu per penanda tangan yang
    sudah meneken, plus QR verifikasi & kode. Dibangun on-the-fly sehingga
    selalu memuat tanda tangan terbaru."""
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.units import mm as rl_mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    sr, data = await _ambil_dokumen_sr(sr_id)
    penanda = [s for s in (sr.get("signers") or [])
               if str(s.get("signature_file_id") or "").strip()]
    if not penanda:
        raise HTTPException(status_code=400,
                            detail="Belum ada tanda tangan yang masuk")

    reader = PdfReader(io.BytesIO(data))

    # Pisahkan penanda tangan ber-POSISI PILIHAN (diatur sendiri di halaman
    # publik: halaman + x/y/lebar fraksi) dari yang memakai slot otomatis.
    kustom = [s for s in penanda if isinstance(s.get("posisi_ttd"), dict)]
    otomatis = [s for s in penanda if not isinstance(s.get("posisi_ttd"), dict)]

    per_halaman = {}
    for s in kustom:
        p = s["posisi_ttd"]
        idx = min(max(1, int(p.get("halaman") or 1)), len(reader.pages)) - 1
        per_halaman.setdefault(idx, []).append(s)

    # QR verifikasi: posisi/ukuran pilihan (dokumen-level) bila diatur penanda
    # tangan; jika tidak → slot otomatis pojok kanan-bawah halaman terakhir.
    qr_pos = sr.get("posisi_qr") if isinstance(sr.get("posisi_qr"), dict) else None
    qr_idx = (min(max(1, int(qr_pos.get("halaman") or 1)), len(reader.pages)) - 1
              if qr_pos else None)

    # Halaman ber-/Rotate: pratinjau posisi dirender pypdfium2 PASCA-rotasi,
    # sedangkan mediabox pypdf PRA-rotasi — normalisasi rotasi ke konten dulu
    # supaya overlay (posisi pilihan MAUPUN slot otomatis) WYSIWYG dengan
    # tampilan. Berlaku untuk semua halaman yang menerima overlay.
    for idx in (set(per_halaman) | {len(reader.pages) - 1}
                | ({qr_idx} if qr_idx is not None else set())):
        try:
            if (reader.pages[idx].rotation or 0) % 360 != 0:
                reader.pages[idx].transfer_rotation_to_content()
        except Exception:
            pass

    hal_akhir = reader.pages[-1]
    lebar = float(hal_akhir.mediabox.width)
    tinggi = float(hal_akhir.mediabox.height)

    # ── Overlay POSISI PILIHAN: gambar ttd + keterangan kecil di halaman &
    #    koordinat yang dipilih penanda tangan sendiri ──
    overlay_kustom = {}
    for idx, daftar in per_halaman.items():
        hal = reader.pages[idx]
        hw = float(hal.mediabox.width)
        hh = float(hal.mediabox.height)
        buf_k = io.BytesIO()
        ck = rl_canvas.Canvas(buf_k, pagesize=(hw, hh))
        ada_isi = False
        for s in daftar:
            p = s["posisi_ttd"]
            img_data = await get_document_from_gridfs(s["signature_file_id"])
            if not img_data:
                continue
            try:
                img = ImageReader(io.BytesIO(img_data))
                iw, ih = img.getSize()
                # lebar/x/y sudah dijepit _posisi_bersih saat kirim (fraksi);
                # jepit ULANG terhadap tepi halaman nyata (tepi bawah/kanan
                # bergantung rasio gambar yang tidak diketahui saat kirim).
                w_pt = float(p.get("lebar") or 0.25) * hw
                h_pt = w_pt * (ih / iw)
                if h_pt > hh - 6:
                    h_pt = hh - 6
                    w_pt = h_pt * (iw / ih)
                x_pt = min(float(p.get("x") or 0) * hw, hw - w_pt)
                y_pt = max(3.0, hh - float(p.get("y") or 0) * hh - h_pt)
                ck.drawImage(img, x_pt, y_pt, width=w_pt, height=h_pt,
                             mask="auto")
                # Keterangan identitas kecil di bawah gambar (jejak formal).
                ck.setFont("Helvetica", 6)
                ck.setFillGray(0.35)
                ket = f"{str(s.get('nama') or '')[:34]}"
                if s.get("signed_at"):
                    ket += f" · {str(s['signed_at'])[:10]}"
                ck.drawCentredString(x_pt + w_pt / 2, max(2.0, y_pt - 7), ket)
                ada_isi = True
            except Exception:
                pass
        ck.save()
        buf_k.seek(0)
        # Canvas tanpa operasi menghasilkan PDF 0 halaman — jangan sampai
        # satu blob hilang membuat SELURUH unduhan dokumen-ttd gagal.
        if ada_isi:
            try:
                overlay_kustom[idx] = PdfReader(buf_k).pages[0]
            except Exception:
                pass

    # ── Overlay slot OTOMATIS halaman terakhir: berderet maks 3/baris ──
    buf_ov = io.BytesIO()
    c = rl_canvas.Canvas(buf_ov, pagesize=(lebar, tinggi))
    margin = 14 * rl_mm
    per_baris = min(3, max(1, len(otomatis)))
    slot_w = (lebar - 2 * margin) / per_baris
    slot_h = 30 * rl_mm
    for i, s in enumerate(otomatis):
        kol = i % per_baris
        brs = i // per_baris
        x = margin + kol * slot_w
        y = margin + brs * slot_h
        c.setFont("Helvetica", 6.5)
        c.setFillGray(0.35)
        c.drawCentredString(x + slot_w / 2, y + slot_h - 8,
                            "Ditandatangani secara elektronik")
        c.setFillGray(0)
        img_data = await get_document_from_gridfs(s["signature_file_id"])
        if img_data:
            try:
                img = ImageReader(io.BytesIO(img_data))
                iw, ih = img.getSize()
                maks_w, maks_h = slot_w - 8 * rl_mm, 13 * rl_mm
                sk = min(maks_w / iw, maks_h / ih)
                c.drawImage(img, x + (slot_w - iw * sk) / 2,
                            y + slot_h - 10 - ih * sk,
                            width=iw * sk, height=ih * sk, mask="auto")
            except Exception:
                pass
        c.setFont("Helvetica-Bold", 8)
        nama_y = y + 9 * rl_mm
        c.drawCentredString(x + slot_w / 2, nama_y, str(s.get("nama") or "")[:38])
        # Garis bawah nama dibatasi ±70mm agar tak membentang penuh saat
        # penanda tangan tunggal (slot = selebar halaman).
        garis_w = min(slot_w - 12 * rl_mm, 70 * rl_mm)
        c.setLineWidth(0.5)
        c.line(x + (slot_w - garis_w) / 2, nama_y - 1.5,
               x + (slot_w + garis_w) / 2, nama_y - 1.5)
        c.setFont("Helvetica", 6.5)
        info = []
        if s.get("jabatan"):
            info.append(str(s["jabatan"])[:40])
        if s.get("nip"):
            # Aturan privasi: penanda tangan Non-ASN (status dari registry
            # pejabat/Master Pegawai per NIP) atau nomor berformat NIK →
            # baris NIP/NIK tidak dicetak di stempel dokumen.
            from pegawai_utils import baris_identitas_laporan
            from shared_utils import status_kepegawaian_by_nip
            b_nip = baris_identitas_laporan(
                s["nip"], await status_kepegawaian_by_nip(s["nip"]))
            if b_nip:
                info.append(b_nip)
        if s.get("signed_at"):
            info.append(str(s["signed_at"])[:10])
        for j, baris in enumerate(info[:3]):
            c.drawCentredString(x + slot_w / 2, nama_y - 8 - j * 7, baris)
    # URL verifikasi publik (dipakai QR otomatis MAUPUN posisi pilihan).
    verif = (_APP_URL + f"/ttd/verifikasi/{sr_id}") if _APP_URL \
        else f"/ttd/verifikasi/{sr_id}"
    # QR otomatis pojok kanan-bawah HANYA bila QR tak diatur posisinya sendiri.
    if qr_pos is None:
        try:
            from reportlab.graphics import renderPDF

            from routes.cards import build_qr_flowable
            qr = build_qr_flowable(verif, 12 * rl_mm)
            if qr is not None:
                renderPDF.draw(qr, c, lebar - margin - 12 * rl_mm, 2 * rl_mm)
            c.setFont("Helvetica", 5.5)
            c.setFillGray(0.4)
            c.drawRightString(lebar - margin - 13 * rl_mm, 5 * rl_mm,
                              f"Verifikasi: {sr_id[:8]}")
        except Exception:
            pass
    c.save()
    buf_ov.seek(0)

    overlay = PdfReader(buf_ov).pages[0]

    # ── Overlay QR POSISI PILIHAN (dokumen-level): pada halaman & koordinat/
    #    ukuran yang diatur, sisi minimal QR_MIN_MM agar tetap dapat dipindai ──
    overlay_qr = None
    if qr_pos is not None and qr_idx is not None:
        halq = reader.pages[qr_idx]
        qw = float(halq.mediabox.width)
        qh = float(halq.mediabox.height)
        # Sisi QR (kotak persegi): fraksi lebar halaman, tapi tak kurang dari
        # QR_MIN_MM (scannable) dan tak melebihi halaman.
        side = max(QR_MIN_MM * rl_mm, float(qr_pos.get("lebar") or 0.16) * qw)
        side = min(side, qw - 4, qh - 4)
        x_left = min(max(0.0, float(qr_pos.get("x") or 0) * qw), qw - side)
        # (x,y) posisi = pojok KIRI-ATAS kotak (fraksi) → koord bawah ReportLab.
        y_bottom = max(2.0, qh - float(qr_pos.get("y") or 0) * qh - side)
        buf_q = io.BytesIO()
        cq = rl_canvas.Canvas(buf_q, pagesize=(qw, qh))
        try:
            from reportlab.graphics import renderPDF

            from routes.cards import build_qr_flowable
            qrf = build_qr_flowable(verif, side)
            if qrf is not None:
                renderPDF.draw(qrf, cq, x_left, y_bottom)
            cq.setFont("Helvetica", 5.5)
            cq.setFillGray(0.4)
            cq.drawCentredString(x_left + side / 2, max(1.0, y_bottom - 6),
                                 f"Verifikasi: {sr_id[:8]}")
        except Exception:
            pass
        cq.save()
        buf_q.seek(0)
        try:
            overlay_qr = (qr_idx, PdfReader(buf_q).pages[0])
        except Exception:
            overlay_qr = None
    writer = PdfWriter()
    for idx, page in enumerate(reader.pages):
        if idx in overlay_kustom:
            page.merge_page(overlay_kustom[idx])
        if overlay_qr is not None and idx == overlay_qr[0]:
            # QR verifikasi di posisi/ukuran pilihan (bisa halaman mana pun).
            page.merge_page(overlay_qr[1])
        if idx == len(reader.pages) - 1:
            # Slot ttd otomatis (+ QR otomatis bila tak diatur) di halaman akhir.
            page.merge_page(overlay)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    nama_dok = str(sr.get("dok_nama") or "dokumen.pdf").rsplit(".", 1)[0]
    return StreamingResponse(
        out, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="{nama_dok}_ber-TTD.pdf"',
                 "X-Content-Type-Options": "nosniff"})


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
async def detail_permintaan(sr_id: str, user: dict = Depends(require_user)):
    """Detail status per penanda tangan (untuk dasbor pembuat)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, {**_PROJ, "signers.jti": 0})
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pemilik_sr(sr, user)  # isolasi: hanya pembuat/admin
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
            "alasan": alasan,
            # dokumen terlampir → halaman publik menampilkan tombol baca
            # + pratinjau pembubuhan (jumlah halaman utk navigasi posisi)
            "ada_dokumen": bool(str(sr.get("dok_file_id") or "").strip()),
            "dok_nama": sr.get("dok_nama", ""),
            "jumlah_halaman": int(sr.get("dok_halaman") or 0)}


@ttd_router.post("/ttd/tandatangan/{sr_id}/kirim")
@limiter.limit("15/minute")
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
    # Posisi divalidasi SEBELUM blob diunggah — nilai liar (Infinity dkk.)
    # tidak boleh meninggalkan blob yatim di GridFS lewat jalur exception.
    posisi_ttd = _posisi_bersih(payload.posisi, int(sr.get("dok_halaman") or 0))
    # QR verifikasi dokumen-level: bila penanda tangan ini memilih posisi/ukuran
    # QR, simpan di root signature_request (bukan per-signer). None → biarkan
    # nilai lama (penanda tangan yg tak mengatur QR tak menghapus pilihan orang
    # lain); pengatur terakhir yang menang.
    posisi_qr = _posisi_qr_bersih(payload.posisi_qr, int(sr.get("dok_halaman") or 0))
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
    set_fields = {"signers.$.status": "ditandatangani",
                  "signers.$.signature_file_id": str(file_id),
                  "signers.$.hash": h,
                  "signers.$.signed_at": now.isoformat(),
                  # Posisi pembubuhan pilihan penanda tangan (None = slot
                  # otomatis di halaman terakhir seperti sebelumnya).
                  "signers.$.posisi_ttd": posisi_ttd,
                  "signers.$.ip": (request.client.host if request.client else "")}
    # Dokumen-level: hanya set bila penanda tangan ini mengatur QR (jangan
    # timpa jadi None saat tak diatur).
    if posisi_qr is not None:
        set_fields["posisi_qr"] = posisi_qr
    res = await db.signature_requests.update_one(
        {"id": sr_id, "status": {"$ne": "batal"},
         "signers": {"$elemMatch": {"signer_id": tok["signer"],
                                    "jti": tok["jti"], "status": "aktif"}}},
        {"$set": set_fields})
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
                            user: dict = Depends(require_user_or_query_token)):
    """Stream gambar tanda tangan seorang penanda tangan (pratinjau dasbor)."""
    sr = await db.signature_requests.find_one({"id": sr_id}, _PROJ)
    if not sr:
        raise HTTPException(status_code=404, detail="Permintaan tidak ditemukan")
    _pastikan_pemilik_sr(sr, user)
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
             # NIP di-masking di halaman verifikasi PUBLIK (data pribadi):
             # cukup 3 digit akhir untuk memastikan kecocokan, sisanya bintang.
             "nip": _mask_nip(s.get("nip")), "status": s.get("status"),
             "signed_at": s.get("signed_at")}
            for s in sr.get("signers") or []],
        "catatan": ("Tanda tangan elektronik internal satker (integritas + "
                    "jejak audit). Sah tanpa tanda tangan basah untuk keperluan "
                    "administrasi internal."),
    }


@ttd_router.get("/ttd/permintaan/{sr_id}/lembar-pdf")
async def lembar_pdf(sr_id: str, user: dict = Depends(require_user_or_query_token)):
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
            # Non-ASN/NIK: baris NIP tidak dicetak di Lembar Pengesahan
            from pegawai_utils import baris_identitas_laporan
            from shared_utils import status_kepegawaian_by_nip
            b_nip = baris_identitas_laporan(
                s["nip"], await status_kepegawaian_by_nip(s["nip"]))
            if b_nip:
                idn += f"<br/><font size=8>{_esc(b_nip)}</font>"
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
