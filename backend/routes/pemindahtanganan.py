"""PEMINDAHTANGANAN — Fase 6 tahap awal: register usulan berstatus.

PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 (pustaka §7): usulan multi-aset →
disetujui → dilaksanakan → selesai (SK Penghapusan). Dokumen wajib per
tahap mengunci transisi; peringatan tenggat lelang 6 bulan.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, HTTPException, Request, UploadFile,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from db import db
from shared_utils import (
    kode_satker_user, scope_query_field_satker, pastikan_akses_dok_satker,
    pastikan_akses_aset, delete_document_from_gridfs, get_document_from_gridfs,
    log_audit,
)
from pemindahtanganan_utils import (
    AMBANG_PERSETUJUAN_PT, BENTUK_PEMINDAHTANGANAN, DOKUMEN_PELAKSANAAN,
    JENIS_BMN_PT, JENJANG_PERSETUJUAN, STATUS_USULAN_PT,
    build_asset_pemindahtanganan_projection, peringatan_pt,
    rekap_pt, sarankan_jenjang, taut_penghapusan, validate_transisi_pt,
    validate_usulan_pt,
)
from pembukuan_utils import parse_harga

pemindahtanganan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "condition": 1, "dihapus": 1,
              "activity_id": 1}

# Status usulan PT yang masih hidup (belum terminal) — dipakai guard anti-ganda.
_STATUS_PT_AKTIF = ("diusulkan", "disetujui", "dilaksanakan")


class UsulanPtIn(BaseModel):
    bentuk: str
    pihak: str = Field(min_length=1)   # penerima hibah / pembeli / mitra / BUMN
    keterangan: str = ""
    # Input untuk saran jenjang persetujuan (indikatif, tak memblok)
    jenis_bmn: str = "selain_tanah_bangunan"
    nilai_wajar: float = 0             # 0 = pakai jumlah nilai perolehan aset
    tb_terkecuali: bool = False        # tanah/bangunan termasuk pengecualian Ps.55(2)
    asset_ids: list[str] = Field(min_length=1, max_length=100)


def _nilai_dasar_saran(u: dict) -> float:
    """Nilai untuk saran jenjang: nilai wajar bila diisi, jika tidak jumlah
    nilai perolehan aset (dengan disclaimer di keluaran saran)."""
    nw = parse_harga(u.get("nilai_wajar"))
    if nw > 0:
        return nw
    return sum(parse_harga(a.get("harga")) for a in u.get("aset") or [])


def _saran_untuk(u: dict) -> dict:
    """Bungkus sarankan_jenjang + tandai basis nilai yang dipakai."""
    nilai = _nilai_dasar_saran(u)
    saran = sarankan_jenjang(
        u.get("bentuk"), u.get("jenis_bmn") or "selain_tanah_bangunan",
        nilai, bool(u.get("tb_terkecuali")))
    saran["nilai_dipakai"] = nilai
    saran["basis_nilai"] = ("nilai_wajar" if parse_harga(u.get("nilai_wajar")) > 0
                            else "nilai_perolehan")
    return saran


class TransisiPtIn(BaseModel):
    status: str
    nomor_persetujuan: str = ""
    tanggal_persetujuan: str = ""
    nomor_dokumen: str = ""            # risalah lelang / BAST / naskah hibah / PP
    ntpn: str = ""                     # bukti setor PNBP (penjualan)
    nomor_sk_penghapusan: str = ""
    catatan: str = ""


@pemindahtanganan_router.get("/pemindahtanganan/export")
async def export_pemindahtanganan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh usulan pemindahtanganan (pola #158).

    Rincian aset diringkas jumlah + nilai perolehan total per usulan.
    """
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    from pembukuan_utils import parse_harga

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["bentuk", "pihak", "status", "jumlah_aset",
                "nilai_perolehan_total", "nomor_persetujuan",
                "tanggal_persetujuan", "nomor_dokumen", "ntpn",
                "nomor_sk_penghapusan", "tanggal_usulan", "keterangan",
                "jumlah_lampiran", "dibuat_oleh"])
    async for u in db.pemindahtanganan.find(scope_query_field_satker(_user), {"_id": 0}).sort("created_at", -1):
        aset = u.get("aset") or []
        w.writerow([
            BENTUK_PEMINDAHTANGANAN.get(u.get("bentuk"), u.get("bentuk")),
            u.get("pihak"),
            STATUS_USULAN_PT.get(u.get("status"), u.get("status")),
            len(aset),
            int(sum(parse_harga(a.get("harga")) for a in aset)),
            u.get("nomor_persetujuan"), u.get("tanggal_persetujuan"),
            u.get("nomor_dokumen"), u.get("ntpn"),
            u.get("nomor_sk_penghapusan"),
            str(u.get("created_at") or "")[:10], u.get("keterangan"),
            len(u.get("lampiran") or []), u.get("created_by"),
        ])
    return HttpResponse(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="register_pemindahtanganan.csv"'})


@pemindahtanganan_router.get("/pemindahtanganan")
async def list_pemindahtanganan(_user: dict = Depends(require_user)):
    """Register usulan (terbaru dulu) + ringkasan + peringatan tenggat."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [u async for u in db.pemindahtanganan.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("created_at", -1).limit(500)]
    for u in items:
        u["peringatan"] = peringatan_pt(u, today_iso)
        u["saran_jenjang"] = _saran_untuk(u)
    return {"items": items, "ringkasan": rekap_pt(items),
            "label_status": STATUS_USULAN_PT,
            "label_bentuk": BENTUK_PEMINDAHTANGANAN,
            "label_dokumen": DOKUMEN_PELAKSANAAN,
            "label_jenis_bmn": JENIS_BMN_PT,
            "label_jenjang": JENJANG_PERSETUJUAN,
            "ambang_referensi": AMBANG_PERSETUJUAN_PT,
            "catatan": (
                "Register penatausahaan: persetujuan bertingkat nilai (Pengguna "
                "delegasi PMK 4/2015 / KPKNL / Kanwil / DJKN / Presiden / DPR); "
                "hasil penjualan disetor seluruhnya ke Kas Negara; selesai = SK "
                "Penghapusan terbit (PMK 83/2016).")}


@pemindahtanganan_router.post("/pemindahtanganan")
async def buat_usulan_pt(payload: UsulanPtIn, user: dict = Depends(require_writer)):
    """Buat usulan pemindahtanganan multi-aset (snapshot identitas)."""
    data = payload.model_dump()
    errors = validate_usulan_pt(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        await pastikan_akses_aset(user, a)  # isolasi satker (REVIEW-9 R8)
        # Guard temuan #9: aset yang sudah keluar pembukuan tak bisa diusulkan
        # pindah tangan; satu aset tak boleh punya dua usulan PT aktif.
        if a.get("dihapus"):
            raise HTTPException(
                status_code=400,
                detail=f"Aset {a.get('asset_code')} NUP {a.get('NUP')} sudah "
                       f"dihapus dari pembukuan — tidak dapat diusulkan")
        ganda = await db.pemindahtanganan.find_one(
            {"status": {"$in": list(_STATUS_PT_AKTIF)}, "aset.asset_id": aid},
            {"_id": 0, "id": 1, "bentuk": 1, "status": 1})
        if ganda:
            raise HTTPException(
                status_code=409,
                detail=f"Aset {a.get('asset_code')} NUP {a.get('NUP')} masih punya "
                       f"usulan pemindahtanganan aktif ({ganda.get('bentuk')}, "
                       f"status {ganda.get('status')})")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "harga": a.get("purchase_price"),
                          "kondisi": a.get("condition")})
    now = datetime.now(timezone.utc).isoformat()
    from shared_utils import kode_satker_efektif_dari_aset
    _ks = await kode_satker_efektif_dari_aset(
        user, [r["asset_id"] for r in aset_rows])
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": _ks,
        "bentuk": data["bentuk"],
        "pihak": data["pihak"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "jenis_bmn": (data.get("jenis_bmn") if data.get("jenis_bmn") in JENIS_BMN_PT
                      else "selain_tanah_bangunan"),
        "nilai_wajar": float(parse_harga(data.get("nilai_wajar"))),
        "tb_terkecuali": bool(data.get("tb_terkecuali")),
        "status": "diusulkan",
        "nomor_persetujuan": "",
        "tanggal_persetujuan": "",
        "nomor_dokumen": "",
        "ntpn": "",
        "nomor_sk_penghapusan": "",
        "aset": aset_rows,
        "lampiran": [],
        "riwayat": [{"status": "diusulkan", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemindahtanganan.insert_one({**record})
    # Cek silang lintas register keluar (non-blocking, audit G5 #11).
    from shared_utils import proses_keluar_aktif
    ids_baru = [a.get("asset_id") for a in record.get("aset") or []]
    peta = await proses_keluar_aktif(ids_baru)
    record["peringatan_proses"] = [
        f"{next((a.get('asset_name') for a in record['aset'] if a.get('asset_id') == aid), aid)}: "
        f"juga dalam {', '.join(x for x in labels if x != 'usulan pemindahtanganan')}"
        for aid, labels in peta.items()
        if [x for x in labels if x != "usulan pemindahtanganan"]][:10]
    record["saran_jenjang"] = _saran_untuk(record)
    return record


async def _proyeksi_master_pemindahtanganan(usulan: dict, oleh: str) -> set:
    """Proyeksikan master aset saat pemindahtanganan SELESAI — tandai `dihapus`
    (SK Penghapusan terbit) untuk SETIAP aset dalam usulan (Prinsip 3 Bab 5).

    Best-effort & idempoten (pola #234/#254): register `pemindahtanganan` tetap
    jurnal sumber; kegagalan/no-op proyeksi TIDAK menggagalkan transisi. Filter
    `dihapus != true` membuat aman dipanggil ulang & tak menimpa jejak
    penghapusan lain (mis. aset sudah dihapus jalur langsung). `$inc version`
    mem-bust cache/ETag + memicu OCC 409 pada form aset usang.

    Mengembalikan HIMPUNAN asset_id yang BENAR-BENAR diproyeksikan (baru
    di-tombstone di sini). Pemanggil memakainya untuk menjurnalkan HANYA aset
    itu — aset yang sudah keluar buku lewat register lain (penghapusan langsung
    / tiket idle) tak boleh dijurnal keluar untuk kedua kalinya.
    """
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_pemindahtanganan_projection(usulan, now)
    terproyeksi = set()
    for row in usulan.get("aset") or []:
        aid = row.get("asset_id")
        if not aid:
            continue
        updated = await db.assets.find_one_and_update(
            {"id": aid, "dihapus": {"$ne": True}},
            {"$set": proj, "$inc": {"version": 1}},
            projection={"_id": 0, "id": 1, "activity_id": 1,
                        "asset_code": 1, "asset_name": 1},
            return_document=True,
        )
        if not updated:
            # Aset sudah dihapus/diproyeksikan atau tak ada — SK tetap sah.
            continue
        terproyeksi.add(aid)
        await log_audit(
            "penghapusan", updated.get("activity_id", ""), updated.get("id", ""),
            asset_code=updated.get("asset_code", ""),
            asset_name=updated.get("asset_name", ""),
            username=oleh or "system",
            detail=(f"Aset dihapus dari master via pemindahtanganan "
                    f"({proj['penghapusan']['bentuk']}) — SK "
                    f"{proj['penghapusan']['nomor_sk']}").strip(),
        )
    return terproyeksi


@pemindahtanganan_router.post("/pemindahtanganan/{usulan_id}/status")
async def transisi_pt(usulan_id: str, payload: TransisiPtIn,
                      admin: dict = Depends(require_admin)):
    """Pindahkan status usulan (admin — gerbang persetujuan berdokumen)."""
    u = await db.pemindahtanganan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(admin, u)  # 403 bila usulan milik satker lain
    data = payload.model_dump()
    errors = validate_transisi_pt(u, payload.status, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    update = {"status": payload.status, "updated_at": now}
    if payload.status == "disetujui":
        update["nomor_persetujuan"] = payload.nomor_persetujuan.strip()
        update["tanggal_persetujuan"] = (str(payload.tanggal_persetujuan or "").strip()[:10]
                                         or now[:10])
    if payload.status == "dilaksanakan":
        update["nomor_dokumen"] = payload.nomor_dokumen.strip()
        if payload.ntpn:
            update["ntpn"] = payload.ntpn.strip()
    if payload.status == "selesai":
        sk = payload.nomor_sk_penghapusan.strip()
        update["nomor_sk_penghapusan"] = sk
        # §5A gap #5: taut FK ke tiket usulan_penghapusan bila nomor SK cocok
        # (bukan sekadar string) → penelusuran dua arah. Best-effort: tak cocok
        # → nomor teks tetap tersimpan tanpa FK (tak menggagalkan transisi).
        if sk:
            tiket = await db.usulan_penghapusan.find_one(
                {"nomor_sk": sk}, {"_id": 0, "id": 1, "nomor_sk": 1})
            update.update(taut_penghapusan(sk, tiket))
    res = await db.pemindahtanganan.find_one_and_update(
        # Anti-balapan: status lama diikutkan di filter
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
    # Proyeksi master (Prinsip 3): saat SELESAI (SK Penghapusan terbit), tandai
    # aset `dihapus` di db.assets agar berhenti double-count di laporan (#256).
    # Setelah CAS sukses agar tak double-proyeksi.
    if payload.status == "selesai":
        terproyeksi = await _proyeksi_master_pemindahtanganan(
            res, admin.get("username"))
        # Jurnal Buku Barang (G7): hibah keluar → 303; bentuk lain keluar
        # daftar via SK penghapusan → 301 (best-effort).
        #
        # HANYA untuk aset yang BENAR-BENAR baru di-tombstone di transisi ini
        # (`terproyeksi`). Aset yang sudah keluar buku lewat register lain —
        # mis. usulan penghapusan yang men-taut SK yang sama, atau tiket idle —
        # akan dijurnal KURANG kedua kalinya bila diloop tanpa syarat; penjaga
        # anti-ganda catat_mutasi_bmn hanya per (asset_id, kode_transaksi,
        # ref_id), dan ref_id usulan ≠ ref_id PT sehingga lolos → saldo CaLBMN
        # dobel. Pola `terproyeksi` yang sama dipakai penggunaan.py/penghapusan.py.
        from shared_utils import catat_mutasi_bmn
        kode_trx = "303" if res.get("bentuk") == "hibah" else "301"
        for a_row in res.get("aset") or []:
            if a_row.get("asset_id") not in terproyeksi:
                continue
            aset = await db.assets.find_one(
                {"id": a_row.get("asset_id")},
                {"_id": 0, "asset_code": 1, "NUP": 1, "purchase_price": 1})
            await catat_mutasi_bmn({
                "asset_id": a_row.get("asset_id"), "kode_transaksi": kode_trx,
                "kode_barang": str((aset or {}).get("asset_code") or ""),
                "nup": str((aset or {}).get("NUP") or ""),
                "tanggal_buku": now[:10], "jumlah": 1,
                "nilai": parse_harga((aset or {}).get("purchase_price")),
                "sumber_modul": "pemindahtanganan", "ref_id": res.get("id"),
                "keterangan": (f"Pemindahtanganan {res.get('bentuk')} selesai — "
                               f"SK {res.get('nomor_sk_penghapusan') or '-'}"),
                "oleh": admin.get("username", "system")})
        # Back-link §5A gap #5: tandai tiket penghapusan sumbernya (dua arah).
        # Best-effort — tak menyentuh version tiket (hindari OCC 409 palsu).
        if res.get("penghapusan_id"):
            await db.usulan_penghapusan.update_one(
                {"id": res["penghapusan_id"]},
                {"$set": {"sumber_pemindahtanganan_id": res.get("id"),
                          "sumber_pemindahtanganan_bentuk": res.get("bentuk", "")}})
    return res


@pemindahtanganan_router.delete("/pemindahtanganan/{usulan_id}")
async def hapus_usulan_pt(usulan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus usulan salah input (hanya status diusulkan) + berkas lampirannya."""
    from shared_utils import scope_query_field_satker
    u = await db.pemindahtanganan.find_one(
        scope_query_field_satker(_admin, {"id": usulan_id, "status": "diusulkan"}),
        {"_id": 0, "lampiran": 1})
    res = await db.pemindahtanganan.delete_one(
        scope_query_field_satker(_admin, {"id": usulan_id, "status": "diusulkan"}))
    if res.deleted_count == 0:
        raise HTTPException(
            status_code=409,
            detail="Usulan tidak ditemukan atau sudah diproses (tidak boleh dihapus)")
    for lamp in (u or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": usulan_id}


# Arsip lampiran per usulan (surat persetujuan, risalah lelang, BAST,
# naskah hibah, bukti setor PNBP — PMK 111/2016 jo. 165/2021). Pola sama
# dengan lampiran pemanfaatan/pemusnahan/penghapusan/pengadaan/PSP
# (#131/#132/#134/#135/#137).
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


@pemindahtanganan_router.post("/pemindahtanganan/{usulan_id}/lampiran")
async def unggah_lampiran_pt(usulan_id: str, file: UploadFile = File(...),
                             user: dict = Depends(require_writer)):
    """Unggah scan dokumen usulan (PDF/gambar, maks 10MB, 10 berkas)."""
    u = await db.pemindahtanganan.find_one(
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
        metadata={"kind": "pemindahtanganan", "usulan_id": usulan_id})

    entri = {"file_id": file_id, "filename": _meta["filename"],
             "content_type": _meta["content_type"],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pemindahtanganan.find_one_and_update(
        {"id": usulan_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@pemindahtanganan_router.get("/pemindahtanganan/{usulan_id}/lampiran/{file_id}")
async def unduh_lampiran_pt(usulan_id: str, file_id: str, request: Request,
                            _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran usulan (menerima header ATAU ?token)."""
    u = await db.pemindahtanganan.find_one(
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


@pemindahtanganan_router.delete("/pemindahtanganan/{usulan_id}/lampiran/{file_id}")
async def hapus_lampiran_pt(usulan_id: str, file_id: str,
                            _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pemindahtanganan.update_one(
        scope_query_field_satker(_admin, {"id": usulan_id}),
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@pemindahtanganan_router.get("/pemindahtanganan/{usulan_id}/nota-dinas-pdf")
async def nota_dinas_pt(usulan_id: str, _user: dict = Depends(require_user)):
    """Nota Dinas Usulan Pemindahtanganan (ASET-DOK-1) — dokumen resmi yang
    selama ini tidak ada: usulan ke Pengelola/KPKNL mensyaratkan daftar
    barang (PMK 165/PMK.06/2021), tetapi register hanya keluar sebagai CSV.

    Nomor dibooking otomatis ke buku agenda Persuratan SEKALI lalu disimpan
    di register (`nomor_nota`) — unduh ulang memakai nomor yang sama, tidak
    memboroskan deret. Gagal booking → nomor titik-titik (pola BAST).
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )
    from shared_utils import blok_ttd_kpb, pengaturan_kop

    u = await db.pemindahtanganan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    await pastikan_akses_dok_satker(_user, u)

    now = datetime.now(timezone.utc).isoformat()
    nomor = str(u.get("nomor_nota") or "")
    if not nomor:
        try:
            from routes.persuratan import booking_nomor_otomatis
            nomor, surat_id = await booking_nomor_otomatis(
                _user, now[:10],
                perihal=(f"Nota Dinas Usulan "
                         f"{BENTUK_PEMINDAHTANGANAN.get(u.get('bentuk'), u.get('bentuk'))}"
                         f" BMN — {u.get('pihak') or '-'}"),
                tujuan="Pengelola Barang",
                keterangan="booking otomatis dari nota dinas pemindahtanganan",
                kode_satker=str(u.get("kode_satker") or ""),
                jenis_naskah="Nota Dinas", referensi="USULAN-PEMINDAHTANGANAN")
            await db.pemindahtanganan.update_one(
                {"id": usulan_id},
                {"$set": {"nomor_nota": nomor, "surat_id_nota": surat_id,
                          "updated_at": now}})
        except Exception:
            nomor = ""

    settings = await pengaturan_kop(kode_satker=u.get("kode_satker") or "")
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    label_bentuk = BENTUK_PEMINDAHTANGANAN.get(u.get("bentuk"), u.get("bentuk"))
    el.extend(_title_block(
        f"NOTA DINAS\nUSULAN {str(label_bentuk).upper()} BMN",
        nomor=nomor or "......./......./........"))
    aset = u.get("aset") or []
    total = sum(parse_harga(a.get("harga")) for a in aset)
    saran = _saran_untuk(u)
    el.append(Paragraph(
        (f"Bersama ini diusulkan {label_bentuk} Barang Milik Negara kepada "
         f"<b>{u.get('pihak') or '-'}</b> sebanyak {len(aset)} unit dengan total "
         f"nilai perolehan Rp{int(total):,} ".replace(",", ".")
         + "sebagaimana Daftar Barang yang Diusulkan berikut, untuk dapat "
           "diproses sesuai PP 27/2014 jo. PP 28/2020 dan PMK 165/PMK.06/2021. "
         + (f"Jenjang persetujuan indikatif: {saran.get('jenjang', '-')}."
            if saran.get("jenjang") else "")), st['Body']))
    el.append(Spacer(1, 4 * rl_mm))
    headers = ["No", "Kode Barang / NUP", "Nama Barang", "Kondisi",
               "Nilai Perolehan (Rp)"]
    widths = [26, 118, 190, 70, 92]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, a in enumerate(aset):
        table_data.append([
            Paragraph(str(i + 1), st['Cell']),
            Paragraph(f"{a.get('asset_code') or '-'} / {a.get('NUP') or '-'}", st['Cell']),
            Paragraph(str(a.get("asset_name") or "-"), st['Cell']),
            Paragraph(str(a.get("kondisi") or "-"), st['Cell']),
            Paragraph(f"{int(parse_harga(a.get('harga'))):,}".replace(",", "."), st['Cell']),
        ])
    table_data.append([
        Paragraph("", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("<b>TOTAL</b>", st['Cell']), Paragraph("", st['Cell']),
        Paragraph(f"<b>{int(total):,}</b>".replace(",", "."), st['Cell'])])
    tabel = Table(table_data, colWidths=_fit_col_widths(widths, doc.width),
                  repeatRows=1)
    tabel.setStyle(_std_table_style(zebra=True))
    el.append(tabel)
    if str(u.get("keterangan") or "").strip():
        el.append(Spacer(1, 3 * rl_mm))
        el.append(Paragraph(f"Keterangan: {u.get('keterangan')}", st['Meta']))
    el.append(Paragraph(
        f"Tanggal usulan: {_fmt_tanggal_id(str(u.get('created_at') or '')[:10]) or '-'}",
        st['Meta']))
    el.append(Spacer(1, 12 * rl_mm))
    kpb = await blok_ttd_kpb(settings, per_iso=now[:10],
                             kode_satker=u.get("kode_satker") or "")
    el.extend(_signature_block([kpb], doc.width))
    footer = _page_footer_factory("Nota Dinas Usulan Pemindahtanganan")
    await asyncio.to_thread(doc.build, el, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="Nota_Dinas_Usulan_{usulan_id[:8]}.pdf"'})
