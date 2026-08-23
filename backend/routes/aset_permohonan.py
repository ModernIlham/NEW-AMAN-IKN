"""Permohonan & persetujuan transaksi pembukuan aset — ASET-GERBANG-1.

Generalisasi pola SEDIA-KPB (routes/persediaan_permohonan.py) ke transaksi
aset yang berjurnal besar: reklasifikasi (304/107), pengembangan KDP (503),
dan penyelesaian KDP (505/105). Writer mengajukan; eksekusi HANYA saat
disetujui admin satker yang bukan pengajunya; "Surat Persetujuan Transaksi
Aset" terbit ber-kop + ber-nomor booking dengan tanda tangan KPB.

EKSEKUSI = memanggil fungsi endpoint mutasi_bmn yang SUDAH ADA dengan model
Pydantic aslinya (`request=None` → gerbang wajib-persetujuan melewatkannya).
Permohonan tidak melahirkan jalur tulis kedua: validasi kode, deret NUP,
pasangan jurnal, dan idempotensi tetap milik satu-satunya implementasi di
routes/mutasi_bmn.py. Atribusi: `oleh` pada jurnal adalah PENYETUJU (dialah
yang mengeksekusi); pengaju tercatat di dokumen permohonan dan di Surat
Persetujuan. `boleh_putuskan` diimpor dari persediaan_permohonan_utils —
satu aturan pemisahan peran untuk dua domain, bukan salinan yang bisa
menyimpang.
"""
import asyncio
import uuid
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from aset_permohonan_utils import (
    JALUR_PERMOHONAN_ASET, ringkasan_permohonan_aset, validate_permohonan_aset,
)
from auth_utils import (require_admin, require_user,
                        require_user_or_query_token, require_writer)
from db import db
from persediaan_permohonan_utils import boleh_putuskan
from shared_utils import (kode_satker_user, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)

aset_permohonan_router = APIRouter()


class PermohonanAsetIn(BaseModel):
    jalur: str
    asset_id: str
    payload: dict
    catatan: str = Field("", max_length=500)


class TolakAsetIn(BaseModel):
    alasan: str = Field(min_length=3, max_length=500)


@aset_permohonan_router.post("/pembukuan/permohonan")
async def ajukan_permohonan_aset(data: PermohonanAsetIn, request: Request = None,
                                 user: dict = Depends(require_writer)):
    """Ajukan permohonan transaksi aset — belum menyentuh aset/jurnal."""
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

    ok, err = validate_permohonan_aset(data.jalur, data.payload, data.asset_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    if data.jalur == "revaluasi_final":
        # Sumber kebenaran = register koreksi penilaian: asset_id DIPAKSA
        # dari register (payload tak bisa membelokkan persetujuan ke aset
        # lain), status harus masih belum_dicatat, dan ringkasan disalin
        # supaya surat informatif.
        koreksi = await db.penilaian_koreksi.find_one(
            scope_query_field_satker(
                user, {"id": str(data.payload.get("koreksi_id") or "")}),
            {"_id": 0})
        if not koreksi:
            raise HTTPException(status_code=404,
                                detail="Register koreksi nilai tidak ditemukan")
        if koreksi.get("status_sakti") != "belum_dicatat":
            raise HTTPException(
                status_code=409,
                detail="Koreksi sudah ditandai tercatat SAKTI — tidak perlu "
                       "permohonan lagi")
        data.asset_id = str(koreksi.get("asset_id") or "")
        data.payload = {**data.payload,
                        "jenis": koreksi.get("jenis"),
                        "nomor_dokumen": koreksi.get("nomor_dokumen"),
                        "nilai_lama": koreksi.get("nilai_lama"),
                        "nilai_baru": koreksi.get("nilai_baru")}

    aset = await db.assets.find_one(
        {"id": data.asset_id, "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_name": 1, "asset_code": 1, "NUP": 1,
         "activity_id": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    # Isolasi satker DI PINTU MASUK: tanpa ini writer satker lain bisa
    # menitipkan permohonan atas aset kita ke antrean admin kita.
    from shared_utils import pastikan_akses_aset
    await pastikan_akses_aset(user, aset)

    # Satker DOKUMEN mengikuti asetnya (super-admin bisa lintas satker) —
    # dari kegiatan induk aset; fallback satker user.
    ks = kode_satker_user(user)
    _act = await db.inventory_activities.find_one(
        {"id": aset.get("activity_id")}, {"_id": 0, "kode_satker": 1})
    ks = str((_act or {}).get("kode_satker") or "").strip() or ks

    now = datetime.now(timezone.utc).isoformat()
    dok = {
        "id": str(uuid.uuid4()),
        "kode_satker": ks,
        "jalur": data.jalur,
        "jalur_label": JALUR_PERMOHONAN_ASET[data.jalur],
        "asset_id": data.asset_id,
        "nama_aset": str(aset.get("asset_name") or ""),
        "kode_nup": f"{aset.get('asset_code') or '-'}/{aset.get('NUP') or '-'}",
        "payload": data.payload,
        "ringkasan": ringkasan_permohonan_aset(data.jalur, data.payload, aset),
        "catatan": data.catatan.strip(),
        "status": "diusulkan",
        "diajukan_oleh": user.get("username", "system"),
        "diajukan_pada": now,
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username", "system"),
                     "catatan": data.catatan.strip()}],
        "created_at": now, "updated_at": now,
    }
    await db.aset_permohonan.insert_one({**dok})
    await log_audit("aset_permohonan_ajukan", "", dok["id"],
                    username=user.get("username", "system"),
                    detail=dok["ringkasan"])
    resp = {"message": "Permohonan diajukan — menunggu persetujuan",
            "permohonan": dok}
    if idem_key:
        from shared_utils import store_idempotent_response
        await store_idempotent_response(idem_key, resp, 200)
    return resp


@aset_permohonan_router.get("/pembukuan/permohonan")
async def daftar_permohonan_aset(status: str = "", page: int = Query(1, ge=1),
                                 page_size: int = Query(30, ge=1, le=100),
                                 _user: dict = Depends(require_user)):
    q = scope_query_field_satker(_user)
    if str(status or "").strip():
        q = {**q, "status": status.strip()}
    total = await db.aset_permohonan.count_documents(q)
    items = await (db.aset_permohonan.find(q, {"_id": 0})
                   .sort("created_at", -1)
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    menunggu = await db.aset_permohonan.count_documents(
        {**scope_query_field_satker(_user), "status": "diusulkan"})
    return {"items": items, "total": total, "menunggu": menunggu,
            "page": page, "total_pages": max(1, -(-total // page_size))}


async def _eksekusi_permohonan_aset(p: dict, penyetuju: dict):
    """Jalankan transaksi lewat implementasi ASLI-nya (request=None)."""
    import routes.mutasi_bmn as rmb
    jalur = p["jalur"]
    payload = dict(p.get("payload") or {})
    aid = str(p.get("asset_id") or "")
    if jalur == "reklasifikasi":
        # asset_id di body reklas WAJIB sama dengan aset permohonan — payload
        # tidak boleh membelokkan persetujuan ke aset lain.
        payload["asset_id"] = aid
        try:
            model = rmb.ReklasifikasiIn(**payload)
        except ValidationError as e:
            raise HTTPException(status_code=400,
                                detail=f"Payload permohonan tidak valid — {e}")
        return await rmb.reklasifikasi_aset(model, user=penyetuju)
    if jalur == "revaluasi_final":
        import routes.penilaian as rp
        return await rp.tandai_tercatat_sakti(
            str(payload.get("koreksi_id") or ""), user=penyetuju)
    peta = {
        "kdp_pengembangan": (rmb.pengembangan_kdp, rmb.KdpPengembanganIn),
        "kdp_selesai": (rmb.selesaikan_kdp, rmb.KdpSelesaiIn),
    }
    fn, Model = peta[jalur]
    try:
        model = Model(**payload)
    except ValidationError as e:
        galat = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: "
                          f"{err['msg']}" for err in e.errors()[:3])
        raise HTTPException(status_code=400,
                            detail=f"Payload permohonan tidak valid — {galat}")
    return await fn(aid, model, user=penyetuju)


@aset_permohonan_router.post("/pembukuan/permohonan/{pid}/setujui")
async def setujui_permohonan_aset(pid: str, user: dict = Depends(require_admin)):
    """Setujui = EKSEKUSI. Klaim atomik (diusulkan → diproses) mencegah dua
    admin mengeksekusi dua kali; eksekusi gagal mengembalikan status ke
    diusulkan dengan galat tercatat."""
    p = await db.aset_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    ok, err = boleh_putuskan(p, user)
    if not ok:
        raise HTTPException(status_code=403, detail=err)

    now = datetime.now(timezone.utc).isoformat()
    klaim = await db.aset_permohonan.find_one_and_update(
        {"id": pid, "status": "diusulkan"},
        {"$set": {"status": "diproses", "updated_at": now}},
        return_document=True)
    if klaim is None:
        raise HTTPException(
            status_code=409,
            detail="Permohonan sudah diputus atau sedang diproses — muat ulang")
    klaim.pop("_id", None)

    try:
        hasil = await _eksekusi_permohonan_aset(klaim, user)
    except HTTPException as e:
        kembali = datetime.now(timezone.utc).isoformat()
        await db.aset_permohonan.update_one(
            {"id": pid},
            {"$set": {"status": "diusulkan", "updated_at": kembali,
                      "galat_terakhir": str(e.detail)},
             "$push": {"riwayat": {"status": "diusulkan", "tanggal": kembali,
                                   "oleh": user.get("username", "system"),
                                   "catatan": f"eksekusi gagal: {e.detail}"}}})
        raise HTTPException(status_code=e.status_code,
                            detail=f"Eksekusi gagal: {e.detail}")

    # Nomor Surat Persetujuan — deret buku agenda yang SAMA dengan LPB/BAST.
    # Gagal booking tidak membatalkan persetujuan (jurnal sudah sah terbit).
    nomor, surat_id = "", ""
    try:
        from routes.persuratan import booking_nomor_otomatis
        nomor, surat_id = await booking_nomor_otomatis(
            user, now[:10],
            perihal=f"Surat Persetujuan Transaksi Aset — {klaim['jalur_label']}",
            tujuan="", keterangan="booking otomatis dari persetujuan aset",
            kode_satker=str(p.get("kode_satker") or ""),
            jenis_naskah="Surat Persetujuan", referensi="PERSETUJUAN-ASET")
    except Exception:
        pass

    selesai = datetime.now(timezone.utc).isoformat()
    await db.aset_permohonan.update_one(
        {"id": pid},
        {"$set": {"status": "disetujui", "updated_at": selesai,
                  "disetujui_oleh": user.get("username", "system"),
                  "disetujui_pada": selesai,
                  "nomor": nomor, "surat_id": surat_id,
                  "hasil_ringkas": str((hasil or {}).get("message")
                                       or (hasil or {}).get("kode_baru") or "")},
         "$push": {"riwayat": {"status": "disetujui", "tanggal": selesai,
                               "oleh": user.get("username", "system"),
                               "catatan": ""}}})
    await log_audit("aset_permohonan_setujui", "", pid,
                    username=user.get("username", "system"),
                    detail=f"{klaim['ringkasan']} — {nomor or 'tanpa nomor'}")
    return {"message": "Permohonan disetujui dan transaksi tereksekusi",
            "nomor": nomor, "hasil": hasil}


@aset_permohonan_router.post("/pembukuan/permohonan/{pid}/tolak")
async def tolak_permohonan_aset(pid: str, data: TolakAsetIn,
                                user: dict = Depends(require_admin)):
    p = await db.aset_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    ok, err = boleh_putuskan(p, user)
    if not ok:
        raise HTTPException(status_code=403, detail=err)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.aset_permohonan.find_one_and_update(
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
    await log_audit("aset_permohonan_tolak", "", pid,
                    username=user.get("username", "system"),
                    detail=data.alasan.strip())
    return {"message": "Permohonan ditolak"}


@aset_permohonan_router.post("/pembukuan/permohonan/{pid}/batal")
async def batal_permohonan_aset(pid: str, user: dict = Depends(require_writer)):
    """Pengaju menarik permohonannya sendiri selama belum diputus."""
    p = await db.aset_permohonan.find_one({"id": pid}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Permohonan tidak ditemukan")
    await pastikan_akses_dok_satker(user, p)
    if str(p.get("diajukan_oleh") or "") != str(user.get("username") or ""):
        raise HTTPException(status_code=403,
                            detail="Hanya pengaju yang boleh membatalkan")
    now = datetime.now(timezone.utc).isoformat()
    res = await db.aset_permohonan.find_one_and_update(
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


async def bangun_persetujuan_aset_pdf(pid: str, _user: dict) -> bytes:
    """Susun Surat Persetujuan → bytes (pola bangun_persetujuan_pdf
    persediaan: satu penyusun untuk unduhan dan pembekuan e-sign)."""
    from routes.reports import (_fmt_tanggal_id, _get_report_styles,
                                _identity_table, _kop_surat_flowables,
                                _page_footer_factory, _signature_block,
                                _std_doc, _title_block)
    from reportlab.platypus import Paragraph, Spacer
    from shared_utils import blok_ttd_kpb, pengaturan_kop

    p = await db.aset_permohonan.find_one({"id": pid}, {"_id": 0})
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
    el.extend(_title_block("SURAT PERSETUJUAN\nTRANSAKSI ASET",
                           nomor=p.get("nomor") or "......./......./........"))
    el.append(Paragraph(
        "Kuasa Pengguna Barang dengan ini menyatakan MENYETUJUI permohonan "
        "transaksi pembukuan aset berikut:", st['Body']))
    el.append(Spacer(1, 6))
    baris = [
        ("Jenis Transaksi", str(p.get("jalur_label") or "-")),
        ("Aset", f"{p.get('nama_aset') or '-'} ({p.get('kode_nup') or '-'})"),
        ("Ringkasan", str(p.get("ringkasan") or "-")),
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
        "mutasi BMN terkait dan diterbitkan berdasarkan permohonan yang "
        "tercatat pada aplikasi AMAN.", st['Body']))
    el.append(Spacer(1, 14))

    pengaju = {"pre": [""], "header": "Pengaju,",
               "nama": str(p.get("diajukan_oleh") or "-"), "after": []}
    kpb = await blok_ttd_kpb(settings, per_iso=(p.get("disetujui_pada") or "")[:10],
                             kode_satker=p.get("kode_satker") or "")
    el.extend(_signature_block([pengaju, kpb], doc.width))

    footer = _page_footer_factory("Surat Persetujuan Transaksi Aset")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    return buffer.getvalue()


@aset_permohonan_router.get("/pembukuan/permohonan/{pid}/dokumen")
async def dokumen_persetujuan_aset(
        pid: str, user: dict = Depends(require_user_or_query_token)):
    data = await bangun_persetujuan_aset_pdf(pid, user)
    return StreamingResponse(
        BytesIO(data), media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="Persetujuan_Aset_{pid[:8]}.pdf"',
                 "X-Content-Type-Options": "nosniff"})


class PengaturanPermohonanAsetIn(BaseModel):
    aktif: bool


@aset_permohonan_router.get("/pembukuan/permohonan-pengaturan")
async def baca_pengaturan_permohonan_aset(_user: dict = Depends(require_user)):
    s = await db.report_settings.find_one(
        {"type": "global"}, {"aset_wajib_persetujuan": 1}) or {}
    return {"aktif": bool(s.get("aset_wajib_persetujuan"))}


@aset_permohonan_router.post("/pembukuan/permohonan-pengaturan")
async def ubah_pengaturan_permohonan_aset(data: PengaturanPermohonanAsetIn,
                                          user: dict = Depends(require_admin)):
    """Saklar gerbang wajib-persetujuan aset — kebijakan satuan kerja, khusus
    admin dan berjejak audit. Menyalakannya membuat reklasifikasi + KDP
    mengajukan permohonan alih-alih menulis jurnal langsung."""
    await db.report_settings.update_one(
        {"type": "global"},
        {"$set": {"aset_wajib_persetujuan": bool(data.aktif)},
         "$setOnInsert": {"type": "global"}},
        upsert=True)
    await log_audit("aset_permohonan_pengaturan", "",
                    username=user.get("username", "system"),
                    detail=("wajib persetujuan aset DINYALAKAN" if data.aktif
                            else "wajib persetujuan aset DIMATIKAN"))
    return {"aktif": bool(data.aktif)}


class KirimTtdPersetujuanAsetIn(BaseModel):
    signers: list = []
    mode: str = "berurutan"


@aset_permohonan_router.post("/pembukuan/permohonan/{pid}/kirim-ttd")
async def kirim_ttd_persetujuan_aset(pid: str, payload: KirimTtdPersetujuanAsetIn,
                                     user: dict = Depends(require_writer)):
    """Kirim Surat Persetujuan untuk diteken elektronik KPB (pola persediaan:
    PDF dibekukan SEKARANG ke GridFS)."""
    from routes.ttd import PermintaanIn, SignerIn, buat_permintaan
    from shared_utils import resolve_penandatangan_kpb

    p = await db.aset_permohonan.find_one({"id": pid}, {"_id": 0})
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

    data = await bangun_persetujuan_aset_pdf(pid, user)
    hasil = await buat_permintaan(
        payload=PermintaanIn(
            judul=f"Persetujuan Aset {p.get('nomor') or pid[:8]}",
            doc_type="persetujuan_aset", doc_ref=pid,
            mode=("paralel" if payload.mode == "paralel" else "berurutan"),
            signers=[SignerIn(nama=str(s.get("nama") or ""),
                              nip=str(s.get("nip") or ""),
                              jabatan=str(s.get("jabatan") or ""),
                              email=str(s.get("email") or ""))
                     for s in daftar]),
        user=user)
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        data, nama=f"Persetujuan_Aset_{pid[:8]}.pdf",
        content_type="application/pdf",
        metadata={"kind": "persetujuan_aset", "permohonan_id": pid})
    await db.signature_requests.update_one(
        {"id": hasil["id"]},
        {"$set": {"dok_file_id": str(file_id),
                  "dok_nama": f"Persetujuan_Aset_{pid[:8]}.pdf",
                  "dok_halaman": 1}})
    # Tautan MAJU ditulis `buat_permintaan` (ttd_penautan.catat_pengiriman_ttd).
    await log_audit("aset_permohonan_kirim_ttd", "", pid,
                    username=user.get("username", "system"),
                    detail=f"dikirim ke {len(daftar)} penanda tangan")
    return {**hasil, "permohonan_id": pid}
