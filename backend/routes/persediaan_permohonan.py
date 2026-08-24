"""Permohonan & persetujuan transaksi persediaan — SEDIA-KPB.

Keputusan pemilik (2026-08-09): SEMUA transaksi persediaan diajukan sebagai
permohonan, dieksekusi HANYA saat disetujui admin satker yang bukan
pengajunya, dan menerbitkan "Surat Persetujuan Transaksi Persediaan" ber-kop
+ ber-nomor dengan tanda tangan Kuasa Pengguna Barang.

Rangka desain meniru tiga preseden repo sekaligus:
  - izin darurat IoT: pemisahan pemohon/penyetuju ditegakkan kode + transisi
    status bersyarat anti-double-approve;
  - usulan peta kolaborasi: perubahan NYATA dieksekusi DI DALAM endpoint
    setujui, bukan saat mengajukan;
  - LPB: builder-bytes terpisah dari route (jalur unduh & jalur TTD memakai
    dokumen yang sama), dibekukan ke GridFS hanya saat dikirim e-sign.

EKSEKUSI = memanggil fungsi endpoint transaksi yang SUDAH ADA dengan model
Pydantic aslinya (`request=None` → gerbang wajib-persetujuan melewatkannya).
Permohonan tidak melahirkan jalur tulis kedua: seluruh validasi, FIFO,
kompensasi jurnal, dan idempotensi tetap milik satu-satunya implementasi di
routes/persediaan.py. Catatan atribusi: `petugas` pada jurnal adalah
PENYETUJU (dialah yang mengeksekusi); pengaju tercatat di dokumen permohonan
dan di Surat Persetujuan.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from auth_utils import (require_admin, require_user,
                        require_user_or_query_token, require_writer,
    require_writer_satker,
)
from db import db
from persediaan_permohonan_utils import (
    JALUR_PERMOHONAN, boleh_putuskan, ringkasan_permohonan,
    validate_permohonan_baru,
)
from shared_utils import (kode_satker_user, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)

persediaan_permohonan_router = APIRouter()


class PermohonanIn(BaseModel):
    jalur: str
    item_id: str = ""
    payload: dict
    catatan: str = Field("", max_length=500)


class TolakIn(BaseModel):
    alasan: str = Field(min_length=3, max_length=500)


@persediaan_permohonan_router.post("/persediaan/permohonan")
async def ajukan_permohonan(data: PermohonanIn, request: Request = None,
                            user: dict = Depends(require_writer_satker)):
    """Ajukan permohonan transaksi — belum menyentuh stok/jurnal sama sekali."""
    from shared_utils import kunci_idem
    idem_key = kunci_idem(
        request.headers.get("Idempotency-Key", "") if request is not None else "",
        user)
    if idem_key:
        from shared_utils import (get_idempotent_response,
                                  reserve_idempotency_key)
        cached = await get_idempotent_response(idem_key)
        if cached and cached.get("response"):
            return cached["response"]
        _idem = await reserve_idempotency_key(idem_key)
        if _idem == "done":
            cached = await get_idempotent_response(idem_key)
            if cached and cached.get("response"):
                return cached["response"]
        elif _idem == "pending":
            raise HTTPException(
                status_code=409,
                detail="Permintaan dengan kunci idempotensi ini sedang diproses")

    ok, err = validate_permohonan_baru(data.jalur, data.payload, data.item_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    nama_barang = ""
    ks = kode_satker_user(user)
    if data.item_id:
        item = await db.persediaan.find_one({"id": data.item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404,
                                detail="Barang persediaan tidak ditemukan")
        await pastikan_akses_dok_satker(user, item)
        nama_barang = str(item.get("nama_barang") or "")
        # Satker DOKUMEN mengikuti barangnya (super-admin bisa lintas satker).
        ks = str(item.get("kode_satker") or "") or ks

    now = datetime.now(timezone.utc).isoformat()
    dok = {
        "id": str(uuid.uuid4()),
        "kode_satker": ks,
        "jalur": data.jalur,
        "jalur_label": JALUR_PERMOHONAN[data.jalur],
        "item_id": data.item_id,
        "nama_barang": nama_barang,
        "payload": data.payload,
        "ringkasan": ringkasan_permohonan(data.jalur, data.payload,
                                          nama_barang),
        "catatan": data.catatan.strip(),
        "status": "diusulkan",
        "diajukan_oleh": user.get("username", "system"),
        "diajukan_pada": now,
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username", "system"),
                     "catatan": data.catatan.strip()}],
        "created_at": now, "updated_at": now,
    }
    await db.persediaan_permohonan.insert_one({**dok})
    await log_audit("persediaan_permohonan_ajukan", "", dok["id"],
                    username=user.get("username", "system"),
                    detail=dok["ringkasan"])
    resp = {"message": "Permohonan diajukan — menunggu persetujuan",
            "permohonan": dok}
    if idem_key:
        from shared_utils import store_idempotent_response
        await store_idempotent_response(idem_key, resp, 200)
    return resp


@persediaan_permohonan_router.get("/persediaan/permohonan")
async def daftar_permohonan(status: str = "", page: int = Query(1, ge=1),
                            page_size: int = Query(30, ge=1, le=100),
                            _user: dict = Depends(require_user)):
    q = scope_query_field_satker(_user)
    if str(status or "").strip():
        q = {**q, "status": status.strip()}
    total = await db.persediaan_permohonan.count_documents(q)
    items = await (db.persediaan_permohonan.find(q, {"_id": 0})
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    from ttd_penautan import lampirkan_status_ttd
    await lampirkan_status_ttd(db, "persetujuan_persediaan", items)
    menunggu = await db.persediaan_permohonan.count_documents(
        {**scope_query_field_satker(_user), "status": "diusulkan"})
    return {"items": items, "total": total, "menunggu": menunggu,
            "page": page, "total_pages": max(1, -(-total // page_size))}


async def _eksekusi_permohonan(p: dict, penyetuju: dict):
    """Jalankan transaksi lewat implementasi ASLI-nya (request=None)."""
    import routes.persediaan as rps
    jalur = p["jalur"]
    payload = p.get("payload") or {}
    iid = str(p.get("item_id") or "")
    peta = {
        "masuk": (rps.transaksi_masuk, rps.TransaksiMasukIn, True),
        "keluar": (rps.transaksi_keluar, rps.TransaksiKeluarIn, True),
        "massal": (rps.transaksi_massal, rps.TransaksiMassalIn, False),
        "opname": (rps.opname_persediaan, rps.OpnameIn, True),
        "koreksi_nilai": (rps.koreksi_nilai_persediaan,
                          rps.KoreksiNilaiPersediaanIn, True),
        "hapus_definitif": (rps.hapus_definitif_persediaan,
                            rps.HapusDefinitifIn, True),
        "pindah_gudang": (rps.pindah_gudang_persediaan,
                          rps.PindahGudangIn, True),
    }
    fn, Model, pakai_item = peta[jalur]
    try:
        model = Model(**payload)
    except ValidationError as e:
        galat = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: "
                          f"{err['msg']}" for err in e.errors()[:3])
        raise HTTPException(status_code=400,
                            detail=f"Payload permohonan tidak valid — {galat}")
    if pakai_item:
        return await fn(iid, model, user=penyetuju)
    return await fn(model, user=penyetuju)


@persediaan_permohonan_router.post("/persediaan/permohonan/{pid}/setujui")
async def setujui_permohonan(pid: str, user: dict = Depends(require_admin)):
    """Setujui = EKSEKUSI. Klaim atomik dulu (diusulkan → diproses) supaya
    dua admin yang menekan Setujui bersamaan tak mengeksekusi dua kali;
    eksekusi gagal mengembalikan status ke diusulkan dengan galat tercatat —
    permohonan tidak pernah "hilang" karena barangnya sedang bermasalah."""
    p = await db.persediaan_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    ok, err = boleh_putuskan(p, user)
    if not ok:
        raise HTTPException(status_code=403, detail=err)

    now = datetime.now(timezone.utc).isoformat()
    klaim = await db.persediaan_permohonan.find_one_and_update(
        {"id": pid, "status": "diusulkan"},
        {"$set": {"status": "diproses", "updated_at": now}},
        return_document=True)
    if klaim is None:
        raise HTTPException(
            status_code=409,
            detail="Permohonan sudah diputus atau sedang diproses — muat ulang")
    klaim.pop("_id", None)

    try:
        hasil = await _eksekusi_permohonan(klaim, user)
    except HTTPException as e:
        kembali = datetime.now(timezone.utc).isoformat()
        await db.persediaan_permohonan.update_one(
            {"id": pid},
            {"$set": {"status": "diusulkan", "updated_at": kembali,
                      "galat_terakhir": str(e.detail)},
             "$push": {"riwayat": {"status": "diusulkan", "tanggal": kembali,
                                   "oleh": user.get("username", "system"),
                                   "catatan": f"eksekusi gagal: {e.detail}"}}})
        raise HTTPException(status_code=e.status_code,
                            detail=f"Eksekusi gagal: {e.detail}")

    # Nomor Surat Persetujuan — deret buku agenda yang SAMA dengan LPB/BAST.
    # Gagal booking tidak membatalkan persetujuan (transaksi sudah sah
    # tereksekusi); dokumen tampil dengan nomor titik-titik seperti BAST
    # belum bernomor.
    nomor, surat_id = "", ""
    try:
        from routes.persuratan import booking_nomor_otomatis
        nomor, surat_id = await booking_nomor_otomatis(
            user, now[:10],
            perihal=f"Surat Persetujuan Transaksi Persediaan — {klaim['jalur_label']}",
            tujuan="", keterangan="booking otomatis dari persetujuan persediaan",
            kode_satker=str(p.get("kode_satker") or ""),
            jenis_naskah="Surat Persetujuan", referensi="PERSETUJUAN-PERSEDIAAN")
    except Exception:
        pass

    selesai = datetime.now(timezone.utc).isoformat()
    await db.persediaan_permohonan.update_one(
        {"id": pid},
        {"$set": {"status": "disetujui", "updated_at": selesai,
                  "disetujui_oleh": user.get("username", "system"),
                  "disetujui_pada": selesai,
                  "nomor": nomor, "surat_id": surat_id,
                  "hasil_ringkas": str((hasil or {}).get("message") or "")},
         "$push": {"riwayat": {"status": "disetujui", "tanggal": selesai,
                               "oleh": user.get("username", "system"),
                               "catatan": ""}}})
    await log_audit("persediaan_permohonan_setujui", "", pid,
                    username=user.get("username", "system"),
                    detail=f"{klaim['ringkasan']} — {nomor or 'tanpa nomor'}")
    return {"message": "Permohonan disetujui dan transaksi tereksekusi",
            "nomor": nomor, "hasil": hasil}


@persediaan_permohonan_router.post("/persediaan/permohonan/{pid}/tolak")
async def tolak_permohonan(pid: str, data: TolakIn,
                           user: dict = Depends(require_admin)):
    p = await db.persediaan_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    ok, err = boleh_putuskan(p, user)
    if not ok:
        raise HTTPException(status_code=403, detail=err)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.persediaan_permohonan.find_one_and_update(
        {"id": pid, "status": "diusulkan"},
        {"$set": {"status": "ditolak", "updated_at": now,
                  "ditolak_oleh": user.get("username", "system"),
                  "ditolak_pada": now, "alasan_tolak": data.alasan.strip()},
         "$push": {"riwayat": {"status": "ditolak", "tanggal": now,
                               "oleh": user.get("username", "system"),
                               "catatan": data.alasan.strip()}}},
        return_document=True)
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Permohonan sudah diputus — muat ulang")
    await log_audit("persediaan_permohonan_tolak", "", pid,
                    username=user.get("username", "system"),
                    detail=data.alasan.strip())
    return {"message": "Permohonan ditolak"}


@persediaan_permohonan_router.post("/persediaan/permohonan/{pid}/batal")
async def batal_permohonan(pid: str, user: dict = Depends(require_writer)):
    """Pengaju menarik permohonannya sendiri selama belum diputus."""
    p = await db.persediaan_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    if str(p.get("diajukan_oleh") or "") != str(user.get("username") or ""):
        raise HTTPException(status_code=403,
                            detail="Hanya pengaju yang boleh membatalkan")
    now = datetime.now(timezone.utc).isoformat()
    res = await db.persediaan_permohonan.find_one_and_update(
        {"id": pid, "status": "diusulkan"},
        {"$set": {"status": "dibatalkan", "updated_at": now},
         "$push": {"riwayat": {"status": "dibatalkan", "tanggal": now,
                               "oleh": user.get("username", "system"),
                               "catatan": ""}}},
        return_document=True)
    if res is None:
        raise HTTPException(status_code=409,
                            detail="Permohonan sudah diputus — muat ulang")
    return {"message": "Permohonan dibatalkan"}


async def bangun_persetujuan_pdf(pid: str, _user: dict) -> bytes:
    """Susun Surat Persetujuan → bytes (pola bangun_lpb_pdf: satu penyusun,
    dua pemakai — unduhan dan pembekuan e-sign memuat dokumen yang sama)."""
    from routes.reports import (_fmt_tanggal_id, _get_report_styles,
                                _identity_table, _kop_surat_flowables,
                                _page_footer_factory, _signature_block,
                                _std_doc, _title_block)
    from reportlab.platypus import Paragraph, Spacer
    from shared_utils import blok_ttd_kpb, pengaturan_kop
    from xml.sax.saxutils import escape as _esc

    p = await db.persediaan_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, p)
    if p.get("status") != "disetujui":
        raise HTTPException(
            status_code=409,
            detail="Surat Persetujuan hanya terbit untuk permohonan yang disetujui")

    settings = await pengaturan_kop(kode_satker=p.get("kode_satker") or "")
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()

    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("SURAT PERSETUJUAN\nTRANSAKSI PERSEDIAAN",
                           nomor=p.get("nomor") or "......./......./........"))
    el.append(Paragraph(
        "Kuasa Pengguna Barang dengan ini menyatakan MENYETUJUI permohonan "
        "transaksi persediaan berikut:", st['Body']))
    el.append(Spacer(1, 6))
    baris = [
        ("Jenis Transaksi", str(p.get("jalur_label") or "-")),
        ("Ringkasan", str(p.get("ringkasan") or "-")),
        ("Barang", (f"{_esc(str(p.get('nama_barang') or '-'))}"
                    if p.get("item_id") else "— (lihat rincian massal)")),
        ("Catatan Pengaju", str(p.get("catatan") or "-")),
        ("Diajukan oleh", (f"{p.get('diajukan_oleh') or '-'} pada "
                           f"{_fmt_tanggal_id(p.get('diajukan_pada')) or '-'}")),
        ("Disetujui melalui aplikasi oleh",
         (f"{p.get('disetujui_oleh') or '-'} pada "
          f"{_fmt_tanggal_id(p.get('disetujui_pada')) or '-'}")),
        ("Hasil Eksekusi", str(p.get("hasil_ringkas") or "-")),
    ]
    el.append(_identity_table(baris))
    el.append(Spacer(1, 8))
    el.append(Paragraph(
        "Persetujuan ini merupakan bagian tidak terpisahkan dari jurnal "
        "transaksi persediaan terkait dan diterbitkan berdasarkan permohonan "
        "yang tercatat pada aplikasi AMAN.", st['Body']))
    el.append(Spacer(1, 14))

    pengaju = {"pre": [""], "header": "Pengaju,",
               "nama": str(p.get("diajukan_oleh") or "-"), "after": []}
    kpb = await blok_ttd_kpb(settings, per_iso=(p.get("disetujui_pada") or "")[:10],
                             kode_satker=p.get("kode_satker") or "")
    # _signature_block mengembalikan LIST flowables (zona atas + KeepTogether).
    el.extend(_signature_block([pengaju, kpb], doc.width))

    footer = _page_footer_factory("Surat Persetujuan Transaksi Persediaan")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    return buffer.getvalue()


@persediaan_permohonan_router.get("/persediaan/permohonan/{pid}/dokumen")
async def dokumen_persetujuan(pid: str,
                              user: dict = Depends(require_user_or_query_token)):
    data = await bangun_persetujuan_pdf(pid, user)
    return StreamingResponse(
        BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="Persetujuan_Persediaan_{pid[:8]}.pdf"',
                 "X-Content-Type-Options": "nosniff"})


class PengaturanPermohonanIn(BaseModel):
    aktif: bool


@persediaan_permohonan_router.get("/persediaan/permohonan-pengaturan")
async def baca_pengaturan_permohonan(_user: dict = Depends(require_user)):
    s = await db.report_settings.find_one(
        {"type": "global"}, {"persediaan_wajib_persetujuan": 1}) or {}
    return {"aktif": bool(s.get("persediaan_wajib_persetujuan"))}


@persediaan_permohonan_router.post("/persediaan/permohonan-pengaturan")
async def ubah_pengaturan_permohonan(data: PengaturanPermohonanIn,
                                     user: dict = Depends(require_admin)):
    """Saklar gerbang wajib-persetujuan — keputusan kebijakan satuan kerja,
    maka khusus admin dan berjejak audit. Menyalakannya membuat SEMUA
    dialog transaksi mengajukan permohonan alih-alih menulis langsung."""
    await db.report_settings.update_one(
        {"type": "global"},
        {"$set": {"persediaan_wajib_persetujuan": bool(data.aktif)},
         "$setOnInsert": {"type": "global"}},
        upsert=True)
    await log_audit("persediaan_permohonan_pengaturan", "",
                    username=user.get("username", "system"),
                    detail=("wajib persetujuan DINYALAKAN" if data.aktif
                            else "wajib persetujuan DIMATIKAN"))
    return {"aktif": bool(data.aktif)}


class KirimTtdPersetujuanIn(BaseModel):
    signers: list = []
    mode: str = "berurutan"


@persediaan_permohonan_router.post("/persediaan/permohonan/{pid}/kirim-ttd")
async def kirim_ttd_persetujuan(pid: str, payload: KirimTtdPersetujuanIn,
                                user: dict = Depends(require_writer)):
    """Kirim Surat Persetujuan untuk diteken elektronik KPB (pola LPB:
    PDF dibekukan SEKARANG ke GridFS — penanda tangan meneken dokumen yang
    benar-benar ia baca, bukan yang dibangun ulang belakangan)."""
    from routes.ttd import PermintaanIn, SignerIn, buat_permintaan
    from shared_utils import resolve_penandatangan_kpb

    p = await db.persediaan_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)

    daftar = list(payload.signers or [])
    if not daftar:
        settings = await db.report_settings.find_one(
            {"type": "global"}, {"_id": 0}) or {}
        kpb = await resolve_penandatangan_kpb(
            settings, per_iso=(p.get("disetujui_pada") or "")[:10],
            kode_satker=str(p.get("kode_satker") or ""))
        from pejabat_utils import jabatan_kapasitas_kpb
        if (kpb or {}).get("nama"):
            daftar = [{"nama": kpb.get("nama", ""), "nip": kpb.get("nip", ""),
                       "jabatan": jabatan_kapasitas_kpb(kpb),
                       "email": kpb.get("email", "")}]
    if not daftar:
        raise HTTPException(
            status_code=400,
            detail="Belum ada KPB di Referensi Pejabat — isi dulu, atau kirim "
                   "daftar penanda tangan secara manual")

    data = await bangun_persetujuan_pdf(pid, user)
    hasil = await buat_permintaan(
        payload=PermintaanIn(
            judul=f"Persetujuan Persediaan {p.get('nomor') or pid[:8]}",
            doc_type="persetujuan_persediaan", doc_ref=pid,
            mode=("paralel" if payload.mode == "paralel" else "berurutan"),
            signers=[SignerIn(nama=str(s.get("nama") or ""),
                              nip=str(s.get("nip") or ""),
                              jabatan=str(s.get("jabatan") or ""),
                              email=str(s.get("email") or ""))
                     for s in daftar]),
        user=user)
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        data, nama=f"Persetujuan_Persediaan_{pid[:8]}.pdf",
        content_type="application/pdf",
        metadata={"kind": "persetujuan_persediaan", "permohonan_id": pid})
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id),
                  "dok_nama": f"Persetujuan_Persediaan_{pid[:8]}.pdf",
                  "dok_halaman": 1}})
    # Tautan MAJU ditulis `buat_permintaan` (ttd_penautan.catat_pengiriman_ttd).
    await log_audit("persediaan_permohonan_kirim_ttd", "", pid,
                    username=user.get("username", "system"),
                    detail=f"dikirim ke {len(daftar)} penanda tangan")
    return {**hasil, "permohonan_id": pid}
