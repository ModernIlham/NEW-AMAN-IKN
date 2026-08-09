"""PENGHAPUSAN — Fase 6: kandidat usul hapus + tiket usulan berstatus.

PMK 83/PMK.06/2016 (pustaka §1 & §7): jaring kandidat per jalur —
Tidak Ditemukan → penelusuran + telaah TGR; Rusak Berat → pemusnahan/
pemindahtanganan. Tiket usulan: diusulkan → diproses → SK terbit/ditolak
(transisi tervalidasi, riwayat tercatat, arsip nomor SK).
"""
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from db import db
from shared_utils import kode_satker_user, scope_query_field_satker, pastikan_akses_dok_satker, delete_document_from_gridfs, get_document_from_gridfs, log_audit
from penghapusan_utils import (
    JALUR_KANDIDAT, STATUS_USULAN, build_asset_penghapusan_projection,
    jalur_kandidat, rekap_kandidat, validate_transisi,
)

penghapusan_router = APIRouter()


class UsulanIn(BaseModel):
    asset_id: str = Field(min_length=1)
    keterangan: str = ""


class TransisiIn(BaseModel):
    status: str
    nomor_sk: str = ""
    tanggal_sk: str = ""
    catatan: str = ""

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "condition": 1, "inventory_status": 1,
         "location": 1, "uraian_tidak_ditemukan": 1, "activity_id": 1}
_MAKS_BARIS = 500


@penghapusan_router.get("/penghapusan/kandidat")
async def kandidat_penghapusan(_user: dict = Depends(require_user)):
    """Kandidat usul hapus per jalur + status usulan aktifnya (bila ada)."""
    from shared_utils import filter_aset_perhitungan, scope_query_aset
    assets = [a async for a in db.assets.find(
        await filter_aset_perhitungan(await scope_query_aset(_user, {"$or": [
            {"inventory_status": "Tidak Ditemukan"},
            {"condition": "Rusak Berat"}]})), _PROJ)]
    hasil = rekap_kandidat(assets)
    # Lekatkan status usulan aktif per aset agar UI tahu mana yang sudah diusulkan
    usulan_aktif = {}
    async for u in db.usulan_penghapusan.find(
            {"status": {"$ne": "ditolak"}},
            {"_id": 0, "asset_id": 1, "status": 1, "id": 1}):
        usulan_aktif[u["asset_id"]] = {"id": u["id"], "status": u["status"]}
    for b in hasil["jalur"].values():
        for r in b["rows"]:
            r["usulan"] = usulan_aktif.get(r["id"])
        b["dipangkas"] = len(b["rows"]) > _MAKS_BARIS
        b["rows"] = b["rows"][:_MAKS_BARIS]
    hasil["label_status"] = STATUS_USULAN
    hasil["catatan"] = (
        "Kandidat dijaring otomatis dari hasil inventarisasi (kondisi + "
        "status). Penghapusan formal tetap melalui usulan, persetujuan, dan "
        "SK sesuai PMK 83/2016 — nilai tersaji adalah nilai perolehan."
    )
    return hasil


@penghapusan_router.get("/penghapusan/usulan")
async def list_usulan(
    status: str = Query("", description="Saring satu status"),
    _user: dict = Depends(require_user),
):
    """Daftar tiket usulan penghapusan, terbaru dulu."""
    query = {}
    if status:
        if status not in STATUS_USULAN:
            valid = ", ".join(STATUS_USULAN)
            raise HTTPException(status_code=400,
                                detail=f"Status tidak dikenal (pilihan: {valid})")
        query["status"] = status
    query = scope_query_field_satker(_user, query)
    items = [u async for u in db.usulan_penghapusan.find(query, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    return {"items": items, "jumlah": len(items), "label_status": STATUS_USULAN,
            "label_jalur": {k: v[0] for k, v in JALUR_KANDIDAT.items()}}


@penghapusan_router.get("/penghapusan/usulan/export")
async def export_usulan_penghapusan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh tiket usulan penghapusan (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["jalur", "kode_aset", "nup", "nama_aset", "status",
                "nomor_sk", "tanggal_sk", "tanggal_usulan", "keterangan",
                "jumlah_lampiran", "dibuat_oleh"])
    async for u in db.usulan_penghapusan.find(scope_query_field_satker(_user), {"_id": 0}).sort("created_at", -1):
        w.writerow([
            JALUR_KANDIDAT.get(u.get("jalur"), (u.get("jalur"),))[0],
            u.get("asset_code"), u.get("NUP"), u.get("asset_name"),
            STATUS_USULAN.get(u.get("status"), u.get("status")),
            u.get("nomor_sk"), u.get("tanggal_sk"),
            str(u.get("created_at") or "")[:10], u.get("keterangan"),
            len(u.get("lampiran") or []), u.get("created_by"),
        ])
    return HttpResponse(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="register_usulan_penghapusan.csv"'})


@penghapusan_router.post("/penghapusan/usulan")
async def buat_usulan(payload: UsulanIn, user: dict = Depends(require_writer)):
    """Buat tiket usulan penghapusan untuk satu aset kandidat."""
    from shared_utils import pastikan_akses_aset
    asset = await db.assets.find_one({"id": payload.asset_id}, _PROJ)
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, asset)  # isolasi satker (REVIEW-9 R8)
    jalur = jalur_kandidat(asset)
    if not jalur:
        raise HTTPException(
            status_code=400,
            detail="Aset bukan kandidat penghapusan (bukan Rusak Berat / Tidak Ditemukan)")
    aktif = await db.usulan_penghapusan.find_one(
        {"asset_id": payload.asset_id, "status": {"$ne": "ditolak"}}, {"_id": 0, "id": 1})
    if aktif:
        raise HTTPException(status_code=409,
                            detail="Aset ini sudah punya usulan penghapusan aktif")
    now = datetime.now(timezone.utc).isoformat()
    # Derivasi satker dari kegiatan induk aset utk super-admin lintas-satker
    # (stempel "" lolos scope dan tampil di semua satker).
    from shared_utils import kode_satker_efektif_dari_aset
    _ks = await kode_satker_efektif_dari_aset(user, [asset["id"]])
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": _ks,
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "jalur": jalur,
        "status": "diusulkan",
        "nomor_sk": "",
        "tanggal_sk": "",
        "keterangan": str(payload.keterangan or "").strip(),
        "lampiran": [],
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.usulan_penghapusan.insert_one({**record})
    # Cek silang lintas register keluar (non-blocking, audit G5 #11).
    from shared_utils import proses_keluar_aktif
    lain = (await proses_keluar_aktif([asset["id"]])).get(asset["id"], [])
    lain = [x for x in lain if x != "usulan penghapusan"]
    record["peringatan_proses"] = (
        [f"Aset ini juga sedang dalam {', '.join(lain)} — periksa agar tidak dobel jalur keluar"]
        if lain else [])
    return record


async def _proyeksi_master_penghapusan(usulan: dict, oleh: str) -> bool:
    """Proyeksikan master aset saat SK penghapusan terbit (Prinsip 3 Bab 5).

    Best-effort & idempoten: SK sudah tercatat di register `usulan_penghapusan`
    (jurnal), jadi kegagalan/no-op proyeksi TIDAK menggagalkan transisi. Filter
    `dihapus != true` membuat pemanggilan ulang aman; `$inc version` mem-bust
    cache media/ETag dan memicu OCC 409 pada form edit yang masih terbuka atas
    aset itu (memang seharusnya konflik — asetnya baru saja dihapus). Tidak
    menyentuh field yang dibaca laporan → tanpa regresi laporan.
    """
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_penghapusan_projection(usulan, now)
    updated = await db.assets.find_one_and_update(
        {"id": usulan.get("asset_id"), "dihapus": {"$ne": True}},
        {"$set": proj, "$inc": {"version": 1}},
        projection={"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1,
                    "asset_name": 1, "NUP": 1},
        return_document=True,
    )
    if not updated:
        # Aset sudah dihapus/diproyeksikan atau tak ada lagi — SK tetap sah.
        return False
    await log_audit(
        "penghapusan", updated.get("activity_id", ""), updated.get("id", ""),
        updated.get("asset_code", ""), updated.get("asset_name", ""),
        username=oleh,
        detail=f"Aset dihapus dari master via SK penghapusan {proj['penghapusan']['nomor_sk']}".strip(),
        nup=updated.get("NUP", ""),
    )
    return True


@penghapusan_router.post("/penghapusan/usulan/{usulan_id}/status")
async def transisi_usulan(usulan_id: str, payload: TransisiIn,
                          admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (khusus admin — gerbang persetujuan)."""
    u = await db.usulan_penghapusan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(admin, u)  # 403 bila usulan milik satker lain
    errors = validate_transisi(u["status"], payload.status, payload.nomor_sk)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    # Gerbang TGR (ASET-TGR, PP 38/2016 + PMK 83/2016): SK penghapusan aset
    # HILANG tidak boleh terbit tanpa bukti proses TGR terekam — wajib ada
    # tiket TGR berkeputusan (ditetapkan/bebas/lunas) untuk aset itu.
    if payload.status == "sk_terbit" and u.get("jalur") == "tidak_ditemukan":
        from routes.tgr import tgr_berkeputusan_untuk
        if not await tgr_berkeputusan_untuk(u.get("asset_id")):
            raise HTTPException(
                status_code=400,
                detail="SK penghapusan aset hilang ditolak: belum ada tiket "
                       "TGR berkeputusan (TGR ditetapkan / bebas TGR) untuk "
                       "aset ini — buka & selesaikan telaah TGR dulu di "
                       "kartu TGR Aset Hilang")
    now = datetime.now(timezone.utc).isoformat()
    update = {
        "status": payload.status,
        "updated_at": now,
    }
    if payload.status == "sk_terbit":
        update["nomor_sk"] = payload.nomor_sk.strip()
        update["tanggal_sk"] = str(payload.tanggal_sk or "").strip()[:10]
    res = await db.usulan_penghapusan.find_one_and_update(
        # Status diikutkan di filter: dua admin yang berlomba tidak bisa
        # menerapkan transisi ganda dari status yang sama
        {"id": usulan_id, "status": u["status"]},
        {"$set": update,
         "$push": {"riwayat": {"status": payload.status, "tanggal": now,
                               "oleh": admin.get("username"),
                               "catatan": str(payload.catatan or "").strip()}}},
        projection={"_id": 0}, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=409,
                            detail="Status usulan berubah oleh proses lain — muat ulang")
    # Proyeksi master (Prinsip 3): saat SK terbit, tandai aset `dihapus` di
    # db.assets + audit. Setelah transisi CAS sukses agar tak double-proyeksi.
    if payload.status == "sk_terbit":
        terproyeksi = await _proyeksi_master_penghapusan(
            res, admin.get("username") or "system")
        res["proyeksi_master"] = terproyeksi
        # Jurnal Buku Barang (G7): penghapusan → 301 (best-effort).
        #
        # HANYA bila proyeksi benar-benar men-tombstone aset ini. Aset yang
        # SUDAH keluar buku lewat register lain (mis. tiket idle → 302, atau
        # pemindahtanganan) mengembalikan proyeksi False; menulis 301 tetap
        # akan menjurnal KURANG kedua kalinya untuk satu aset — dan penjaga
        # anti-ganda catat_mutasi_bmn hanya per (asset_id, kode_transaksi,
        # ref_id), sehingga ref usulan yang berbeda lolos → saldo CaLBMN dobel.
        # Pola sama dengan `terproyeksi` di routes/penggunaan.py.
        if terproyeksi:
            from pembukuan_utils import parse_harga
            from shared_utils import catat_mutasi_bmn
            aset = await db.assets.find_one(
                {"id": res.get("asset_id")},
                {"_id": 0, "asset_code": 1, "NUP": 1, "purchase_price": 1})
            await catat_mutasi_bmn({
                "asset_id": res.get("asset_id"), "kode_transaksi": "301",
                "kode_barang": str((aset or {}).get("asset_code") or ""),
                "nup": str((aset or {}).get("NUP") or ""),
                "tanggal_buku": (res.get("tanggal_sk") or now[:10]),
                "jumlah": 1,
                "nilai": parse_harga((aset or {}).get("purchase_price")),
                "sumber_modul": "penghapusan", "ref_id": res.get("id"),
                "keterangan": f"SK Penghapusan {res.get('nomor_sk') or '-'}",
                "oleh": admin.get("username", "system")})
    return res


# Arsip lampiran per tiket (SK penghapusan + dokumen pendukung —
# PMK 83/2016). Pola sama dengan lampiran pemanfaatan/pemusnahan
# (#131/#132).
_LAMPIRAN_MEDIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
_MAX_LAMPIRAN_BYTES = 10 * 1024 * 1024
_MAX_LAMPIRAN = 10


def _lampiran_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _LAMPIRAN_MEDIA:
        if name.endswith(ext):
            return ext
    return ""


@penghapusan_router.post("/penghapusan/usulan/{usulan_id}/lampiran")
async def unggah_lampiran_usulan(usulan_id: str, file: UploadFile = File(...),
                                 user: dict = Depends(require_writer)):
    """Unggah scan SK/dokumen pendukung (PDF/gambar, maks 10MB, 10 berkas)."""
    u = await db.usulan_penghapusan.find_one(
        {"id": usulan_id}, {"_id": 0, "id": 1, "lampiran": 1, "kode_satker": 1})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(user, u)
    if len(u.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per usulan")
    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    ext = _lampiran_ext(filename)
    if not ext:
        raise HTTPException(status_code=400,
                            detail="Lampiran harus PDF atau gambar (JPG/PNG/WEBP)")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > _MAX_LAMPIRAN_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran lampiran maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    # GERBANG KOMPRESI — satu aturan untuk satu aplikasi utuh. Lampiran modul
    # siklus dulu ditulis apa adanya, jadi PDF hasil pindai dan foto bukti
    # masuk GridFS tanpa pernah menyentuh rantai berjenjang.
    #
    # `content_type` DAN `filename` entri diambil dari metadata yang
    # DIKEMBALIKAN gerbang, bukan dari ekstensi: rantai gambar mengembalikan
    # JPEG walau masukannya PNG, dan entri yang tetap menyebut `.png` membuat
    # pengguna mengunduh berkas yang isinya tak sesuai namanya.
    from gerbang_media import tulis_media
    file_id, _meta = await tulis_media(
        file_bytes, nama=filename, content_type=_LAMPIRAN_MEDIA[ext],
        metadata={"kind": "penghapusan", "usulan_id": usulan_id})

    entri = {"file_id": file_id, "filename": _meta["filename"],
             "content_type": _meta["content_type"],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.usulan_penghapusan.find_one_and_update(
        {"id": usulan_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@penghapusan_router.get("/penghapusan/usulan/{usulan_id}/lampiran/{file_id}")
async def unduh_lampiran_usulan(usulan_id: str, file_id: str, request: Request,
                                _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran usulan (menerima header ATAU ?token)."""
    u = await db.usulan_penghapusan.find_one(
        scope_query_field_satker(
            _user, {"id": usulan_id, "lampiran.file_id": file_id}),
        {"_id": 0, "lampiran.$": 1})
    if not u or not u.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = u["lampiran"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "dokumen"}"'})


@penghapusan_router.delete("/penghapusan/usulan/{usulan_id}/lampiran/{file_id}")
async def hapus_lampiran_usulan(usulan_id: str, file_id: str,
                                _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.usulan_penghapusan.update_one(
        scope_query_field_satker(_admin, {"id": usulan_id}),
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@penghapusan_router.delete("/penghapusan/usulan/{usulan_id}")
async def hapus_usulan(usulan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (status diusulkan) + berkas lampirannya."""
    from shared_utils import scope_query_field_satker
    u = await db.usulan_penghapusan.find_one(
        scope_query_field_satker(_admin, {"id": usulan_id, "status": "diusulkan"}),
        {"_id": 0, "lampiran": 1})
    res = await db.usulan_penghapusan.delete_one(
        scope_query_field_satker(_admin, {"id": usulan_id, "status": "diusulkan"}))
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    for lamp in (u or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": usulan_id}


@penghapusan_router.get("/penghapusan/nota-dinas-pdf")
async def nota_dinas_penghapusan(ids: str = "", booking: int = 0,
                                 _user: dict = Depends(require_user)):
    """Nota Dinas Usulan Penghapusan (ASET-DOK-1) — daftar tiket berstatus
    `diusulkan` dalam satu dokumen resmi ke Pengelola (PMK 83/PMK.06/2016).

    `ids` (dipisah koma) menyaring ke tiket TERPILIH; id di luar kandidat
    diabaikan (pola nota dinas persediaan — bukan pintu belakang). `booking=1`
    membooking nomor Persuratan untuk cetakan INI; tanpa itu nomor
    titik-titik — setiap cetakan ber-nomor adalah surat baru di buku agenda.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from pembukuan_utils import parse_harga
    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )
    from shared_utils import blok_ttd_kpb, pengaturan_kop

    q = scope_query_field_satker(_user, {"status": "diusulkan"})
    rows = await (db.usulan_penghapusan.find(q, {"_id": 0})
                  .sort("created_at", 1).to_list(500))
    terpilih = {s for s in (x.strip() for x in ids.split(",")) if s}
    if terpilih:
        rows = [r for r in rows if r.get("id") in terpilih]

    # Nilai perolehan dari master aset (tiket tak menyimpan harga).
    harga = {}
    aids = [r.get("asset_id") for r in rows if r.get("asset_id")]
    if aids:
        async for a in db.assets.find({"id": {"$in": aids}},
                                      {"_id": 0, "id": 1, "purchase_price": 1}):
            harga[a["id"]] = parse_harga(a.get("purchase_price"))

    now = datetime.now(timezone.utc).isoformat()
    ks = kode_satker_user(_user)
    nomor = ""
    if booking and rows:
        try:
            from routes.persuratan import booking_nomor_otomatis
            nomor, _sid = await booking_nomor_otomatis(
                _user, now[:10],
                perihal=f"Nota Dinas Usulan Penghapusan BMN ({len(rows)} unit)",
                tujuan="Pengelola Barang",
                keterangan="booking otomatis dari nota dinas penghapusan",
                kode_satker=ks,
                jenis_naskah="Nota Dinas", referensi="USULAN-PENGHAPUSAN")
        except Exception:
            nomor = ""

    settings = await pengaturan_kop(kode_satker=ks)
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("NOTA DINAS\nUSULAN PENGHAPUSAN BMN",
                           nomor=nomor or "......./......./........"))
    total = sum(harga.get(r.get("asset_id"), 0) for r in rows)
    pengantar = (
        f"Bersama ini diusulkan penghapusan {len(rows)} unit Barang Milik "
        f"Negara dengan total nilai perolehan Rp{int(total):,} ".replace(",", ".")
        + "sebagaimana daftar berikut, untuk dapat diproses sesuai "
          "PMK 83/PMK.06/2016.")
    if terpilih:
        pengantar += (" Daftar ini memuat tiket yang DIPILIH untuk diusulkan; "
                      "tiket lain sengaja tidak disertakan.")
    el.append(Paragraph(pengantar, st['Body']))
    el.append(Spacer(1, 4 * rl_mm))
    if not rows:
        el.append(Paragraph(
            "Tidak ada tiket usulan penghapusan berstatus diusulkan.",
            st['Cell']))
    else:
        headers = ["No", "Kode Barang / NUP", "Nama Barang", "Jalur",
                   "Nilai Perolehan (Rp)"]
        widths = [26, 118, 180, 80, 92]
        table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for i, r in enumerate(rows):
            label_jalur = JALUR_KANDIDAT.get(r.get("jalur"),
                                             (r.get("jalur") or "-",))[0]
            table_data.append([
                Paragraph(str(i + 1), st['Cell']),
                Paragraph(f"{r.get('asset_code') or '-'} / {r.get('NUP') or '-'}",
                          st['Cell']),
                Paragraph(str(r.get("asset_name") or "-"), st['Cell']),
                Paragraph(str(label_jalur), st['Cell']),
                Paragraph(f"{int(harga.get(r.get('asset_id'), 0)):,}".replace(",", "."),
                          st['Cell']),
            ])
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("", st['Cell']),
            Paragraph("<b>TOTAL</b>", st['Cell']), Paragraph("", st['Cell']),
            Paragraph(f"<b>{int(total):,}</b>".replace(",", "."), st['Cell'])])
        tabel = Table(table_data, colWidths=_fit_col_widths(widths, doc.width),
                      repeatRows=1)
        tabel.setStyle(_std_table_style(zebra=True))
        el.append(tabel)
    el.append(Paragraph(f"Tanggal data: {_fmt_tanggal_id(now[:10])}", st['Meta']))
    el.append(Spacer(1, 12 * rl_mm))
    kpb = await blok_ttd_kpb(settings, per_iso=now[:10], kode_satker=ks)
    el.extend(_signature_block([kpb], doc.width))
    footer = _page_footer_factory("Nota Dinas Usulan Penghapusan")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition":
                 'attachment; filename="Nota_Dinas_Usulan_Penghapusan.pdf"'})
