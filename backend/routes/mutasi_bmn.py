"""Pembukuan — Jurnal Mutasi BMN & Reklasifikasi (Gelombang 7, pustaka §2.6).

Koleksi `mutasi_bmn` append-only = "Buku Barang" AMAN: jurnal transaksi
ber-kode per aset (pola SIMAK/SAKTI). Endpoint reklasifikasi memutakhirkan
kode+NUP aset IN-PLACE (id internal & kode register SIMAN tidak berubah)
sambil merekam pasangan 304/107 dan riwayat pada dokumen aset.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth_utils import (require_admin, require_user,
                        require_user_or_query_token, require_writer)
from db import db
from shared_utils import scope_query_field_satker
from kodefikasi_utils import normalize_kode, validate_kode
from mutasi_bmn_utils import (
    KODE_TRANSAKSI_BMN, buat_pasangan_reklasifikasi, validate_entri_mutasi,
)
from shared_utils import log_audit

mutasi_bmn_router = APIRouter()

_PROJ = {"_id": 0}


class ReklasifikasiIn(BaseModel):
    asset_id: str
    kode_baru: str
    alasan: Optional[str] = ""
    tanggal_buku: Optional[str] = ""   # default hari ini


@mutasi_bmn_router.get("/pembukuan/mutasi")
async def daftar_mutasi(asset_id: str = "", kode_transaksi: str = "",
                        dari: str = "", sampai: str = "", page: int = 1,
                        page_size: int = 50,
                        _user: dict = Depends(require_user)):
    """Jurnal mutasi BMN (Buku Barang) — terbaru dulu, filter opsional."""
    page, page_size = max(1, page), min(max(1, page_size), 200)
    q = {}
    if asset_id.strip():
        q["asset_id"] = asset_id.strip()
    if kode_transaksi.strip():
        q["kode_transaksi"] = kode_transaksi.strip()
    if dari.strip() or sampai.strip():
        rentang = {}
        if dari.strip():
            rentang["$gte"] = dari.strip()[:10]
        if sampai.strip():
            rentang["$lte"] = sampai.strip()[:10]
        q["tanggal_buku"] = rentang
    total = await db.mutasi_bmn.count_documents(q)
    items = await (db.mutasi_bmn.find(q, _PROJ)
                   .sort([("tanggal_buku", -1), ("created_at", -1)])
                   .skip((page - 1) * page_size).limit(page_size)
                   .to_list(page_size))
    # Perkaya untuk tampilan: uraian & efek dari peta kode (entri jurnal
    # sendiri sengaja ramping — hanya kode).
    for it in items:
        info = KODE_TRANSAKSI_BMN.get(str(it.get("kode_transaksi") or ""))
        if info:
            it.setdefault("uraian_transaksi", info[0])
            it.setdefault("efek", info[1])
    return {"items": items, "total": total, "page": page,
            "total_pages": max(1, -(-total // page_size)),
            "label_kode": {k: v[0] for k, v in KODE_TRANSAKSI_BMN.items()}}


@mutasi_bmn_router.post("/pembukuan/mutasi/backfill")
async def backfill_saldo_awal(admin: dict = Depends(require_admin)):
    """Backfill sekali (idempoten): aset aktif TANPA entri jurnal apa pun
    diberi satu entri sintetis **100 Saldo Awal** (tanggal buku = tanggal
    perolehan, fallback created_at) — riset G7: aset tanpa jejak transaksi
    tetap harus punya titik awal di Buku Barang."""
    import uuid as _uuid

    from pembukuan_utils import parse_harga

    sudah = set()
    async for m in db.mutasi_bmn.find({}, {"_id": 0, "asset_id": 1}):
        sudah.add(m.get("asset_id"))
    dibuat = 0
    now = datetime.now(timezone.utc).isoformat()
    from shared_utils import filter_aset_perhitungan, scope_query_aset
    q_backfill = await filter_aset_perhitungan(
        await scope_query_aset(admin, {"dihapus": {"$ne": True}}))
    async for a in db.assets.find(
            q_backfill,
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1,
             "purchase_price": 1, "purchase_date": 1, "created_at": 1}):
        if a["id"] in sudah:
            continue
        tgl = (str(a.get("purchase_date") or "").strip()[:10]
               or str(a.get("created_at") or now)[:10])
        if len(tgl) != 10 or tgl[4] != "-":
            tgl = now[:10]
        await db.mutasi_bmn.insert_one({
            "id": str(_uuid.uuid4()), "asset_id": a["id"],
            "kode_transaksi": "100",
            "kode_barang": str(a.get("asset_code") or ""),
            "nup": str(a.get("NUP") or ""),
            "tanggal_buku": tgl, "jumlah": 1,
            "nilai": parse_harga(a.get("purchase_price")),
            "sumber_modul": "backfill", "ref_id": "",
            "keterangan": "Saldo awal sintetis (backfill Buku Barang)",
            "oleh": admin.get("username", "system"),
            "created_at": now})
        dibuat += 1
    await log_audit("backfill_mutasi_bmn", "", username=admin.get("username", "system"),
                    detail=f"Backfill saldo awal Buku Barang: {dibuat} aset")
    return {"dibuat": dibuat, "sudah_berjurnal": len(sudah)}


async def _nup_berikut_kode(kode_baru: str) -> str:
    """NUP berikut pada kode tujuan (increment NUP numerik terbesar)."""
    res = await db.assets.aggregate([
        {"$match": {"asset_code": kode_baru, "dihapus": {"$ne": True}}},
        {"$group": {"_id": None, "max_nup": {"$max": {"$convert": {
            "input": "$NUP", "to": "int",
            "onError": None, "onNull": None}}}}},
    ]).to_list(1)
    return str(int((res[0].get("max_nup") if res else None) or 0) + 1)


@mutasi_bmn_router.post("/pembukuan/reklasifikasi")
async def reklasifikasi_aset(payload: ReklasifikasiIn,
                             user: dict = Depends(require_writer)):
    """Reklasifikasi kodefikasi aset (SAKTI 304/107, riset §3):
    kode+NUP dimutakhirkan IN-PLACE (aset tidak dibuat ulang — nilai &
    tanggal perolehan, id internal, dan kode register SIMAN tetap), NUP baru
    berurut pada kode tujuan, riwayat tercatat pada aset + pasangan jurnal
    304/107 pada `mutasi_bmn` (periode sama, nilai bruto sama)."""
    kode_baru = normalize_kode(payload.kode_baru)
    ok, err = validate_kode(kode_baru)
    if not ok:
        raise HTTPException(status_code=400, detail=err)
    if len(kode_baru) != 10:
        raise HTTPException(status_code=400,
                            detail="Kode tujuan harus kode barang penuh 10 digit (sub-sub kelompok)")
    if kode_baru.startswith("1"):
        raise HTTPException(status_code=400, detail=(
            "Kode berawalan '1' = persediaan — reklasifikasi aset→persediaan "
            "tidak dilakukan di sini (rekam keluar aset + masuk persediaan)"))

    aset = await db.assets.find_one(
        {"id": payload.asset_id, "dihapus": {"$ne": True}}, _PROJ)
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    if normalize_kode(aset.get("asset_code")) == kode_baru:
        raise HTTPException(status_code=400,
                            detail="Kode tujuan sama dengan kode sekarang")

    now = datetime.now(timezone.utc)
    tgl_buku = (str(payload.tanggal_buku or "").strip()[:10]
                or now.date().isoformat())
    nup_baru = await _nup_berikut_kode(kode_baru)
    oleh = user.get("username", "system")

    keluar, masuk = buat_pasangan_reklasifikasi(
        aset, kode_baru, nup_baru, tgl_buku, payload.alasan, oleh)
    for e in (keluar, masuk):
        errs = validate_entri_mutasi(e)
        if errs:
            raise HTTPException(status_code=400, detail="; ".join(errs))
        e.update({"id": str(uuid.uuid4()), "created_at": now.isoformat()})
    await db.mutasi_bmn.insert_one({**keluar})
    await db.mutasi_bmn.insert_one({**masuk})

    riwayat = {
        "kode_lama": aset.get("asset_code"), "nup_lama": aset.get("NUP"),
        "kode_baru": kode_baru, "nup_baru": nup_baru,
        "tanggal": tgl_buku, "alasan": str(payload.alasan or "").strip(),
        "oleh": oleh,
    }
    await db.assets.update_one(
        {"id": payload.asset_id},
        {"$set": {"asset_code": kode_baru, "NUP": nup_baru,
                  "updated_at": now.isoformat()},
         "$push": {"riwayat_reklasifikasi": riwayat},
         "$inc": {"version": 1}})
    await log_audit("reklasifikasi_aset", "", payload.asset_id,
                    username=oleh,
                    detail=(f"Reklasifikasi {riwayat['kode_lama']}/"
                            f"{riwayat['nup_lama']} → {kode_baru}/{nup_baru}"))
    return {"ok": True, "kode_baru": kode_baru, "nup_baru": nup_baru,
            "riwayat": riwayat}


# ============================================================================
# SETELAN AMBANG KAPITALISASI (PMK 181 → dapat diatur admin, Mandat-2)
# ============================================================================

class AmbangIn(BaseModel):
    ambang: dict   # {"3": 1000000, "4": 25000000} — golongan digit → rupiah


@mutasi_bmn_router.get("/pembukuan/ambang-kapitalisasi")
async def lihat_ambang(_user: dict = Depends(require_user)):
    """Ambang kapitalisasi intra/ekstra EFEKTIF + default PMK 181 + override
    tersimpan. Semua laporan pembukuan (DBKP/LBKP/Posisi) memakai nilai ini."""
    from pembukuan_utils import AMBANG_KAPITALISASI_DEFAULT
    from shared_utils import ambang_kapitalisasi
    doc = await db.report_settings.find_one(
        {"type": "kapitalisasi"}, {"_id": 0, "ambang": 1}) or {}
    return {"efektif": await ambang_kapitalisasi(),
            "default": AMBANG_KAPITALISASI_DEFAULT,
            "override": doc.get("ambang") or {}}


@mutasi_bmn_router.put("/pembukuan/ambang-kapitalisasi")
async def simpan_ambang(payload: AmbangIn,
                        admin: dict = Depends(require_admin)):
    """Simpan override ambang kapitalisasi (admin). Kosongkan dict = kembali
    ke default PMK 181. Hanya golongan 3 (Peralatan & Mesin) dan 4 (Gedung &
    Bangunan) yang punya ambang menurut PMK 181; golongan lain ditolak agar
    tidak diam-diam mengeluarkan tanah/jalan dari neraca."""
    from pembukuan_utils import parse_harga
    bersih = {}
    for k, v in (payload.ambang or {}).items():
        g = str(k or "").strip()
        if g not in ("3", "4"):
            raise HTTPException(
                status_code=400,
                detail="Hanya golongan 3 dan 4 yang ber-ambang (PMK 181)")
        harga = parse_harga(v)
        if harga <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Ambang golongan {g} harus angka rupiah > 0")
        bersih[g] = harga
    await db.report_settings.update_one(
        {"type": "kapitalisasi"},
        {"$set": {"ambang": bersih,
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": admin.get("username", "system")}},
        upsert=True)
    await log_audit("ubah_ambang_kapitalisasi", "", "kapitalisasi",
                    username=admin.get("username", "system"),
                    detail=f"Override ambang kapitalisasi: {bersih or 'default PMK 181'}")
    from shared_utils import ambang_kapitalisasi
    return {"ok": True, "efektif": await ambang_kapitalisasi()}


# ============================================================================
# DBKP JSON — Daftar Barang Kuasa Pengguna GLOBAL (halaman modul Pembukuan)
# ============================================================================

@mutasi_bmn_router.get("/pembukuan/dbkp")
async def dbkp_json(_user: dict = Depends(require_user)):
    """Rekap DBKP per golongan (intra/ekstrakomptabel, ambang efektif) atas
    SELURUH aset aktif — sumber halaman Pembukuan. Ter-scope satker user."""
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import build_dbkp_rows, posisi_neraca
    from persediaan_utils import nilai_persediaan_dari_batches
    from report_filters import active_asset_filter
    from shared_utils import (ambang_kapitalisasi, filter_aset_perhitungan,
                              scope_query_aset)

    q = await filter_aset_perhitungan(
        await scope_query_aset(_user, active_asset_filter()))
    assets = await db.assets.find(
        q, {"_id": 0, "asset_code": 1, "purchase_price": 1,
            "nilai_wajar_terakhir": 1}).to_list(500000)
    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian_map[k["kode"]] = k["uraian"]
    amb = await ambang_kapitalisasi()
    rows, total = build_dbkp_rows(assets, uraian_map, ambang=amb)
    p_jumlah, p_nilai = 0, 0.0
    async for it in db.persediaan.find(
            scope_query_field_satker(_user), {"_id": 0, "batches": 1}):
        p_jumlah += 1
        p_nilai += nilai_persediaan_dari_batches(it.get("batches"))
    return {"rows": rows, "total": total, "ambang": amb,
            "posisi": posisi_neraca(rows, total, p_jumlah, p_nilai)}


# ============================================================================
# KIB — KARTU IDENTITAS BARANG per unit (PMK 181, pola SAKTI) — M-MODUL
# ============================================================================

class KibIn(BaseModel):
    data: dict


def _aset_kib_proj():
    return {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
            "brand": 1, "serial_number": 1, "location": 1, "condition": 1,
            "purchase_price": 1, "purchase_date": 1, "perolehan_dari_nama": 1,
            "activity_id": 1, "kib": 1, "photo_gridfs_ids": 1}


@mutasi_bmn_router.get("/pembukuan/kib/{asset_id}")
async def lihat_kib(asset_id: str, _user: dict = Depends(require_user)):
    """Info KIB satu aset: jenis terdeteksi dari kode barang + spesifikasi
    field khusus jenis itu + data tersimpan. 400 bila jenis BMN tak ber-KIB."""
    from pembukuan_utils import KIB_FIELDS, KIB_LABELS, jenis_kib
    from shared_utils import pastikan_akses_aset
    aset = await db.assets.find_one({"id": asset_id}, _aset_kib_proj())
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, aset)
    jenis = jenis_kib(aset.get("asset_code"))
    if not jenis:
        raise HTTPException(
            status_code=400,
            detail="KIB hanya untuk tanah, bangunan gedung, alat angkutan (302), "
                   "alat besar (301), dan alat persenjataan (307) — PMK 181")
    aset.pop("photo_gridfs_ids", None)
    return {"jenis": jenis, "label": KIB_LABELS[jenis],
            "fields": [{"key": k, "label": l} for k, l in KIB_FIELDS[jenis]],
            "data": aset.get("kib") or {}, "aset": aset}


@mutasi_bmn_router.put("/pembukuan/kib/{asset_id}")
async def simpan_kib(asset_id: str, payload: KibIn,
                     user: dict = Depends(require_writer)):
    """Simpan data khusus KIB (disanitasi per jenis) ke dokumen aset."""
    from pembukuan_utils import bersihkan_kib, jenis_kib
    from shared_utils import pastikan_akses_aset
    aset = await db.assets.find_one(
        {"id": asset_id}, {"_id": 0, "asset_code": 1, "activity_id": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, aset)
    jenis = jenis_kib(aset.get("asset_code"))
    if not jenis:
        raise HTTPException(status_code=400, detail="Jenis BMN ini tidak ber-KIB")
    bersih = bersihkan_kib(jenis, payload.data)
    await db.assets.update_one(
        {"id": asset_id},
        {"$set": {"kib": bersih,
                  "updated_at": datetime.now(timezone.utc).isoformat()},
         "$inc": {"version": 1}})
    await log_audit("simpan_kib", "", asset_id,
                    username=user.get("username", "system"),
                    detail=f"Data KIB {jenis} diperbarui")
    return {"ok": True, "jenis": jenis, "data": bersih}


@mutasi_bmn_router.get("/pembukuan/kib-pdf/{asset_id}")
async def kib_pdf(asset_id: str, _user: dict = Depends(require_user_or_query_token)):
    """KARTU IDENTITAS BARANG (PDF resmi): identitas aset + field khusus per
    jenis (terisi dari data tersimpan; kosong = garis titik untuk dilengkapi
    manual) + riwayat mutasi Buku Barang + blok tanda tangan KPB."""
    import io as _io
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Image as RLImage, Paragraph, Spacer, Table

    from pembukuan_utils import KIB_FIELDS, KIB_LABELS, jenis_kib, parse_harga
    from routes.reports import (
        _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _std_doc, _std_table_style, _title_block,
    )
    from shared_utils import (
        get_photo_from_gridfs, pastikan_akses_aset, pengaturan_kop,
    )

    aset = await db.assets.find_one({"id": asset_id}, _aset_kib_proj())
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, aset)
    jenis = jenis_kib(aset.get("asset_code"))
    if not jenis:
        raise HTTPException(status_code=400, detail="Jenis BMN ini tidak ber-KIB")

    activity = await db.inventory_activities.find_one(
        {"id": aset.get("activity_id")}, {"_id": 0}) if aset.get("activity_id") else None
    settings = await pengaturan_kop(activity)
    st = _get_report_styles()
    buffer = _io.BytesIO()
    doc = _std_doc(buffer)
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("KARTU IDENTITAS BARANG (KIB)",
                           subjudul=KIB_LABELS[jenis]))

    from xml.sax.saxutils import escape as _esc
    kib = aset.get("kib") or {}
    kosong = "................................"

    def _v(x):
        s = str(x or "").strip()
        return _esc(s) if s else kosong

    harga = parse_harga(aset.get("purchase_price"))
    umum = [
        ("Kode Barang / NUP", f"{aset.get('asset_code') or '-'} / {aset.get('NUP') or '-'}"),
        ("Nama Barang", aset.get("asset_name") or "-"),
        ("Merk / Tipe", aset.get("brand") or ""),
        ("Nomor Seri Pabrik", aset.get("serial_number") or ""),
        ("Lokasi", aset.get("location") or ""),
        ("Asal Perolehan", aset.get("perolehan_dari_nama") or ""),
        ("Tanggal Perolehan", _fmt_tanggal_id(str(aset.get("purchase_date") or "")[:10])
         if aset.get("purchase_date") else ""),
        ("Nilai Perolehan", f"Rp{harga:,.0f}".replace(",", ".") if harga else ""),
        ("Kondisi", aset.get("condition") or ""),
    ]
    baris = [[Paragraph("<b>DATA UMUM</b>", st['TableHeader']), Paragraph("", st['TableHeader'])]]
    for label, nilai in umum:
        baris.append([Paragraph(label, st['Cell']), Paragraph(_v(nilai), st['Cell'])])
    baris.append([Paragraph(f"<b>DATA KHUSUS — {_esc(KIB_LABELS[jenis])}</b>", st['TableHeader']),
                  Paragraph("", st['TableHeader'])])
    for key, label in KIB_FIELDS[jenis]:
        baris.append([Paragraph(label, st['Cell']), Paragraph(_v(kib.get(key)), st['Cell'])])
    t = Table(baris, colWidths=[doc.width * 0.38, doc.width * 0.62], repeatRows=0)
    t.setStyle(_std_table_style(zebra=True))
    el.append(t)

    # Foto aset (opsional, foto pertama)
    fids = aset.get("photo_gridfs_ids") or []
    if fids:
        try:
            data = await get_photo_from_gridfs(str(fids[0]))
            if data:
                img = RLImage(_io.BytesIO(data))
                sk = min((doc.width * 0.35) / img.imageWidth, (45 * rl_mm) / img.imageHeight)
                img.drawWidth, img.drawHeight = img.imageWidth * sk, img.imageHeight * sk
                el.append(Spacer(1, 3 * rl_mm))
                el.append(img)
        except Exception:
            pass

    # Riwayat mutasi Buku Barang (maks 10 terbaru)
    mutasi = await (db.mutasi_bmn.find({"asset_id": asset_id}, _PROJ)
                    .sort([("tanggal_buku", -1)]).limit(10).to_list(10))
    if mutasi:
        el.append(Spacer(1, 4 * rl_mm))
        el.append(Paragraph("<b>Riwayat Mutasi (Buku Barang)</b>", st['Meta']))
        mb = [[Paragraph(h, st['TableHeader']) for h in ("Tanggal", "Kode", "Uraian", "Nilai")]]
        for m in mutasi:
            mb.append([Paragraph(str(m.get("tanggal_buku") or "-"), st['CellCenter']),
                       Paragraph(str(m.get("kode_transaksi") or "-"), st['CellCenter']),
                       Paragraph(_esc(str(m.get("uraian_transaksi") or "")), st['Cell']),
                       Paragraph(f"Rp{parse_harga(m.get('nilai')):,.0f}".replace(",", "."), st['Cell'])])
        tm = Table(mb, colWidths=[doc.width * 0.16, doc.width * 0.10,
                                  doc.width * 0.50, doc.width * 0.24], repeatRows=1)
        tm.setStyle(_std_table_style(zebra=True))
        el.append(tm)

    el.append(Spacer(1, 6 * rl_mm))
    try:
        from routes.reports import _signature_block
        from shared_utils import blok_ttd_kpb
        el.extend(_signature_block([await blok_ttd_kpb(settings)], doc.width))
    except Exception:
        pass

    footer = _page_footer_factory("Kartu Identitas Barang")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse as _SR
    from shared_utils import nama_file_disposition
    nama = f"KIB_{(aset.get('asset_code') or 'aset')}_{(aset.get('NUP') or '')}.pdf"
    return _SR(buffer, media_type="application/pdf",
               headers={"Content-Disposition": nama_file_disposition(nama)})
