"""Cetak STIKER LABEL BMN — ukuran OPTIMAL memenuhi seluruh ruang A4/A3.

Desain meniru contoh label resmi satker: border kotak, kepala = logo + nama
instansi + nama satker (atau kode satker lengkap), garis pemisah, badan kiri
= KODE BARANG + NUP → NAMA BARANG → SUB-SUB KELOMPOK, QR di kanan dengan gap
aman dari garis potong. Payload QR memakai format pemindai internal
(`#kode_register` / `#kode-nup`).

Keterbacaan (mandat pemilik): ukuran huruf per peran, jatah baris, dan
penyusutan otomatis dihitung `stiker_utils` — nama instansi yang panjang
menyusut lalu pecah dua baris alih-alih meluber, sedangkan nama barang &
sub-sub kelompok MELANJUT ke baris berikutnya alih-alih dipotong di baris
pertama. Ada lantai ukuran huruf supaya stiker kecil tetap terbaca.

Grid dihitung `grid_optimal` (stiker_utils): kolom/baris dibulatkan ke
ukuran target lalu label DIRENTANGKAN mengisi penuh area cetak — sisa ruang
hanya margin 6mm + celah potong 1,5mm. Mode `ukuran=per_aset` mencetak
SESUAI PILIHAN tiap aset (field `stiker_ukuran`) dan MENGELOMPOKKAN hasil
per ukuran (besar → sedang → kecil). Satu sel terakhir tiap kelompok berisi
stiker CONTOH bertuliskan dimensi nyata per satuan (`sampel_ukuran=false`
untuk mematikannya) — bahan ukur saat memesan bahan stiker.
"""
import io

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth_utils import require_user
from db import db
from shared_utils import (kode_satker_user, pastikan_akses_kegiatan_id,
                          pengaturan_kop, scope_query_aset)
from stiker_render import gambar_grup, logo_reader
from stiker_utils import MARGIN_MM, TARGET_STIKER, kelompokkan_per_ukuran

stiker_router = APIRouter()

MAKS_STIKER = 2000

_PROJ_STIKER = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
                "category": 1, "kode_register": 1, "activity_id": 1,
                "stiker_ukuran": 1}


def _bangun_query_stiker(asset_ids, **f):
    """Query aset utk stiker: asset_ids eksplisit ATAU filter daftar aset."""
    ids = [i.strip() for i in str(asset_ids or "").split(",") if i.strip()]
    if ids:
        return {"id": {"$in": ids[:MAKS_STIKER]}, "dihapus": {"$ne": True}}
    from routes.assets import build_asset_search_query
    return build_asset_search_query(**f)


@stiker_router.get("/stiker/rekap-ukuran")
async def rekap_ukuran_stiker(
    asset_ids: str = "",
    search: str = "",
    category: str = "",
    activity_id: str = "",
    condition: List[str] = Query(default=[]),
    status: List[str] = Query(default=[]),
    location: List[str] = Query(default=[]),
    eselon1_filter: List[str] = Query(default=[]),
    eselon2_filter: List[str] = Query(default=[]),
    stiker_status: List[str] = Query(default=[]),
    inventory_status: List[str] = Query(default=[]),
    price_min: float = None,
    price_max: float = None,
    nomor_spm: str = "",
    perolehan_dari: str = "",
    user_filter: str = "",
    pengguna_nip: str = "",
    beli_dari: str = "",
    beli_sampai: str = "",
    _user: dict = Depends(require_user),
):
    """Rekap pilihan `stiker_ukuran` aset dlm cakupan cetak — pengguna tahu
    berapa stiker per ukuran & BERAPA yang belum diisi (akan memakai Sedang)
    sehingga bisa ditindaklanjuti (isi via form/edit cepat/Ubah Massal)."""
    query = _bangun_query_stiker(
        asset_ids, search=search, category=category, activity_id=activity_id,
        condition=condition, status=status, location=location,
        eselon1_filter=eselon1_filter, eselon2_filter=eselon2_filter,
        stiker_status=stiker_status, inventory_status=inventory_status,
        price_min=price_min, price_max=price_max, nomor_spm=nomor_spm,
        perolehan_dari=perolehan_dari, user_filter=user_filter,
        pengguna_nip=pengguna_nip, beli_dari=beli_dari,
        beli_sampai=beli_sampai)
    await pastikan_akses_kegiatan_id(_user, activity_id)
    query = await scope_query_aset(_user, query)
    rekap = {"besar": 0, "sedang": 0, "kecil": 0, "belum_terisi": 0}
    total = 0
    async for g in db.assets.aggregate([
            {"$match": query},
            {"$group": {"_id": {"$toLower": {"$ifNull": ["$stiker_ukuran", ""]}},
                        "n": {"$sum": 1}}}]):
        kunci = str(g["_id"] or "").strip()
        total += g["n"]
        if kunci in rekap:
            rekap[kunci] += g["n"]
        else:
            rekap["belum_terisi"] += g["n"]
    rekap["total"] = total
    return rekap


@stiker_router.get("/stiker/label")
async def cetak_stiker_label(
    ukuran: str = "sedang",
    kertas: str = "A4",
    header_info: str = "nama",
    sampel_ukuran: bool = True,
    asset_ids: str = "",
    # ── filter identik GET /assets (mengikuti filter aktif daftar) ──
    search: str = "",
    category: str = "",
    activity_id: str = "",
    condition: List[str] = Query(default=[]),
    status: List[str] = Query(default=[]),
    location: List[str] = Query(default=[]),
    eselon1_filter: List[str] = Query(default=[]),
    eselon2_filter: List[str] = Query(default=[]),
    stiker_status: List[str] = Query(default=[]),
    inventory_status: List[str] = Query(default=[]),
    price_min: float = None,
    price_max: float = None,
    nomor_spm: str = "",
    perolehan_dari: str = "",
    user_filter: str = "",
    pengguna_nip: str = "",
    beli_dari: str = "",
    beli_sampai: str = "",
    _user: dict = Depends(require_user),
):
    """PDF stiker label siap cetak. `ukuran=per_aset` → tiap aset memakai
    ukuran pilihannya sendiri (field `stiker_ukuran`), hasil dikelompokkan
    per ukuran (besar → sedang → kecil). `sampel_ukuran` (default aktif)
    menambahkan SATU stiker contoh berisi dimensi nyata per satuan di akhir
    tiap kelompok."""
    from reportlab.lib.pagesizes import A3, A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    ukuran = str(ukuran).strip().lower()
    if ukuran not in ("per_aset", *TARGET_STIKER):
        raise HTTPException(status_code=400,
                            detail="Ukuran harus besar/sedang/kecil/per_aset")
    kertas_map = {"A4": A4, "A3": A3}
    page = kertas_map.get(str(kertas).strip().upper())
    if page is None:
        raise HTTPException(status_code=400, detail="Kertas harus A4 atau A3")

    query = _bangun_query_stiker(
        asset_ids, search=search, category=category, activity_id=activity_id,
        condition=condition, status=status, location=location,
        eselon1_filter=eselon1_filter, eselon2_filter=eselon2_filter,
        stiker_status=stiker_status, inventory_status=inventory_status,
        price_min=price_min, price_max=price_max, nomor_spm=nomor_spm,
        perolehan_dari=perolehan_dari, user_filter=user_filter,
        pengguna_nip=pengguna_nip, beli_dari=beli_dari,
        beli_sampai=beli_sampai)
    await pastikan_akses_kegiatan_id(_user, activity_id)
    query = await scope_query_aset(_user, query)
    aset = await (db.assets.find(query, _PROJ_STIKER)
                  .sort([("asset_code", 1), ("NUP", 1)])
                  .to_list(MAKS_STIKER + 1))
    terpotong = len(aset) > MAKS_STIKER
    aset = aset[:MAKS_STIKER]
    if not aset:
        raise HTTPException(status_code=404,
                            detail="Tidak ada aset sesuai filter/pilihan")

    # Uraian SUB-SUB KELOMPOK dari master kodefikasi (satu query batch) —
    # tampil di stiker sebagai info kategori terinci; fallback kategori aset.
    import re as _re
    kode_set = {_re.sub(r"\D", "", str(a.get("asset_code") or ""))
                for a in aset}
    kode_set.discard("")
    peta_subsub = {}
    if kode_set:
        async for k in db.kodefikasi.find(
                {"kode": {"$in": sorted(kode_set)}},
                {"_id": 0, "kode": 1, "uraian": 1}):
            peta_subsub[k["kode"]] = k["uraian"]
    for a in aset:
        kd = _re.sub(r"\D", "", str(a.get("asset_code") or ""))
        if peta_subsub.get(kd):
            a["_subsub"] = peta_subsub[kd]

    kop = await pengaturan_kop(kode_satker=kode_satker_user(_user)) or {}
    logo = logo_reader(kop.get("logo_url"))
    # Baris kedua header: NAMA satuan kerja (default) atau KODE SATKER
    # LENGKAP ±20 digit (switch di dialog) — fallback silang bila kosong.
    nama_instansi = str(kop.get("nama_instansi")
                        or kop.get("nama_unit_organisasi") or "").strip()
    nama_satker = str(kop.get("nama_sub_unit")
                      or kop.get("nama_unit_organisasi") or "").strip()
    if nama_satker == nama_instansi and not kop.get("nama_sub_unit"):
        nama_satker = ""
    kode_lengkap = str(kop.get("kode_satker_lengkap") or "").strip()
    if str(header_info).strip().lower() == "kode":
        kop["_baris2_stiker"] = kode_lengkap or nama_satker
    else:
        kop["_baris2_stiker"] = nama_satker

    page_w, page_h = page
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page)
    c.setTitle(f"Stiker Label BMN — {ukuran} — {kertas}")
    if ukuran == "per_aset":
        # Kelompokkan sesuai pilihan tiap aset; tiap kelompok grid sendiri
        # (dan contoh ukurannya sendiri — dimensinya memang berbeda).
        ada = False
        for u, grup in kelompokkan_per_ukuran(aset):
            gambar_grup(c, grup, u, page_w, page_h, kop, logo, mm,
                         mulai_halaman_baru=ada, sampel_ukuran=sampel_ukuran)
            ada = True
    else:
        gambar_grup(c, aset, ukuran, page_w, page_h, kop, logo, mm,
                     mulai_halaman_baru=False, sampel_ukuran=sampel_ukuran)
    if terpotong:
        c.showPage()
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN_MM * mm, page_h - MARGIN_MM * mm - 12,
                     f"Catatan: hasil melebihi batas {MAKS_STIKER} stiker — "
                     "persempit filter lalu cetak lagi untuk sisanya.")
    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="stiker_label_{ukuran}_{kertas}.pdf"',
                 "X-Total-Stiker": str(len(aset))})
