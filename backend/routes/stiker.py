"""Cetak STIKER LABEL BMN — ukuran OPTIMAL memenuhi seluruh ruang A4/A3.

Desain meniru contoh label resmi satker: border kotak, header logo + nama
instansi + NAMA SATKER, garis pemisah, badan kiri (kode barang + NUP,
kategori, nama barang terpotong "..."), QR di kanan MEPET garis tepi
(kanan/bawah/garis header). Payload QR memakai format pemindai internal
(`#kode_register` / `#kode-nup`).

Grid dihitung `grid_optimal` (stiker_utils): kolom/baris dibulatkan ke
ukuran target lalu label DIRENTANGKAN mengisi penuh area cetak — sisa ruang
hanya margin 6mm + celah potong 1,5mm. Mode `ukuran=per_aset` mencetak
SESUAI PILIHAN tiap aset (field `stiker_ukuran`) dan MENGELOMPOKKAN hasil
per ukuran (besar → sedang → kecil).
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth_utils import require_user
from db import db
from shared_utils import (kode_satker_user, pastikan_akses_kegiatan_id,
                          pengaturan_kop, scope_query_aset)
from stiker_utils import (GAP_MM, MARGIN_MM, TARGET_STIKER, grid_optimal,
                          kelompokkan_per_ukuran)

stiker_router = APIRouter()

MAKS_STIKER = 2000

_PROJ_STIKER = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
                "category": 1, "kode_register": 1, "activity_id": 1,
                "stiker_ukuran": 1}


def _logo_reader(logo_url: str):
    """ImageReader dari data-URL logo kop (None bila tak ada/gagal)."""
    try:
        if not str(logo_url or "").startswith("data:"):
            return None
        import base64

        from reportlab.lib.utils import ImageReader
        b64 = logo_url.split(",", 1)[1]
        return ImageReader(io.BytesIO(base64.b64decode(b64)))
    except Exception:
        return None


def _qr_drawing(payload: str, size: float, level: str = "M"):
    """QR lokal dengan level koreksi galat dapat diatur — level "H" (30%)
    dipakai saat logo ditumpangkan di tengah QR agar tetap terbaca."""
    try:
        from reportlab.graphics.barcode import qr
        from reportlab.graphics.shapes import Drawing
        widget = qr.QrCodeWidget(payload, barLevel=level, barBorder=1)
        x0, y0, x1, y1 = widget.getBounds()
        w, h = (x1 - x0) or 1, (y1 - y0) or 1
        d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        d.add(widget)
        return d
    except Exception:
        return None


def _potong_baris(teks, font, size, lebar, maks_baris):
    """Pecah teks ke maks N baris selebar `lebar`; baris terakhir di-'...'."""
    from reportlab.lib.utils import simpleSplit
    baris = simpleSplit(str(teks or ""), font, size, lebar)
    if len(baris) > maks_baris:
        baris = baris[:maks_baris]
        baris[-1] = baris[-1].rstrip(".") + "..."
    return baris


def _gambar_stiker(c, x, y, w, h, target, aset, kop, logo, mm):
    """Gambar SATU stiker di (x, y) pojok kiri-bawah, dimensi (w, h) pt.

    Header: logo + nama instansi + NAMA SATKER (bukan lagi kode register —
    permintaan pemilik); QR MEPET garis tepi kanan/bawah/garis header."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    hdr = target["header"] * mm
    pad = 1.6 * mm
    s = (w / mm) / 95.0  # faktor skala relatif desain besar
    f_satker = max(4.6, 8.5 * s)
    f_sub = max(4.0, 7.0 * s)
    f_kode = max(4.6, 8.0 * s)
    f_teks = max(4.2, 7.0 * s)

    c.setLineWidth(0.8)
    c.rect(x, y, w, h)

    # ── Header: logo kiri + nama instansi + nama satker ──
    hdr_y = y + h - hdr
    tengah_x = x + w / 2
    logo_w = 0
    if logo is not None and (w / mm) >= 60:
        sisi = hdr - 1.2 * mm
        try:
            c.drawImage(logo, x + pad, hdr_y + 0.6 * mm, width=sisi,
                        height=sisi, preserveAspectRatio=True, mask="auto")
            logo_w = sisi + pad
        except Exception:
            logo_w = 0
    nama = str(kop.get("nama_instansi") or kop.get("nama_unit_organisasi")
               or "").strip()
    satker = str(kop.get("nama_sub_unit") or kop.get("nama_unit_organisasi")
                 or "").strip()
    if satker == nama:
        satker = str(kop.get("nama_unit_organisasi") or "").strip() \
            if kop.get("nama_sub_unit") else ""
    c.setFont("Helvetica-Bold", f_satker)
    c.drawCentredString(tengah_x + logo_w / 2, y + h - hdr / 2 - f_satker * 0.1,
                        nama[:60])
    if satker:
        c.setFont("Helvetica", f_sub)
        c.drawCentredString(tengah_x + logo_w / 2,
                            y + h - hdr / 2 - f_satker - f_sub * 0.35,
                            satker[:60])
    c.setLineWidth(0.5)
    c.line(x, hdr_y, x + w, hdr_y)

    # ── Badan: teks kiri, QR kanan dengan GAP AMAN dari garis tepi
    # (antisipasi meleset di mesin cutting — QR tidak ikut terpotong) ──
    pad_qr = 1.8 * mm
    qr_sisi = h - hdr - 2 * pad_qr
    qr_x = x + w - pad_qr - qr_sisi
    qr_y = y + pad_qr
    lebar_teks = qr_x - x - 2 * pad

    kode = str(aset.get("asset_code") or "").strip()
    nup = str(aset.get("NUP") or "").strip()
    # Sub-sub kelompok dari kodefikasi (di-resolve batch oleh endpoint);
    # fallback kategori aset.
    subsub = str(aset.get("_subsub") or aset.get("category") or "").strip()
    nama_brg = str(aset.get("asset_name") or "").strip()

    ty = y + h - hdr - pad - f_kode
    c.setFont("Helvetica-Bold", f_kode)
    c.drawString(x + pad, ty, kode[:24])
    if nup:
        label_nup = f"NUP: {nup}"
        nx = x + pad + max(stringWidth(kode[:24], "Helvetica-Bold", f_kode)
                           + 4 * mm, lebar_teks * 0.5)
        nx = min(nx, x + pad + lebar_teks
                 - stringWidth(label_nup, "Helvetica-Bold", f_kode))
        c.drawString(max(nx, x + pad), ty, label_nup)
    ty -= f_teks * 1.25
    if subsub:
        c.setFont("Helvetica", f_teks)
        c.drawString(x + pad, ty, subsub[:48])
        ty -= f_teks * (1.5 if target["baris_desc"] >= 2 else 1.2)
    c.setFont("Helvetica", f_teks)
    for baris in _potong_baris(nama_brg, "Helvetica", f_teks, lebar_teks,
                               target["baris_desc"]):
        c.drawString(x + pad, ty, baris)
        ty -= f_teks * 1.2

    # QR — payload format pemindai kartu (#kreg / #kode-nup). Stiker KECIL
    # tak punya ruang logo di header → logo ditaruh DI TENGAH QR dengan
    # koreksi galat tertinggi (level H, 30%) agar QR tetap terbaca.
    kreg = str(aset.get("kode_register") or "").strip()
    payload = f"#{kreg}" if kreg else f"#{kode}-{nup or '0'}"
    logo_di_qr = logo is not None and (w / mm) < 60
    try:
        from reportlab.graphics import renderPDF
        d = _qr_drawing(payload, qr_sisi, level="H" if logo_di_qr else "M")
        if d is not None:
            renderPDF.draw(d, c, qr_x, qr_y)
            if logo_di_qr:
                kotak = qr_sisi * 0.26
                sisi_logo = qr_sisi * 0.22
                cx = qr_x + (qr_sisi - kotak) / 2
                cy = qr_y + (qr_sisi - kotak) / 2
                c.setFillGray(1)
                c.rect(cx, cy, kotak, kotak, stroke=0, fill=1)
                c.setFillGray(0)
                c.drawImage(logo, qr_x + (qr_sisi - sisi_logo) / 2,
                            qr_y + (qr_sisi - sisi_logo) / 2,
                            width=sisi_logo, height=sisi_logo,
                            preserveAspectRatio=True, mask="auto")
    except Exception:
        pass


def _gambar_grup(c, aset_grup, ukuran, page_w, page_h, kop, logo, mm,
                 mulai_halaman_baru):
    """Gambar satu KELOMPOK ukuran (grid penuh sendiri). Return True bila
    ada halaman yang tergambar."""
    target = TARGET_STIKER[ukuran]
    kolom, baris, lw_mm, lh_mm = grid_optimal(
        page_w / mm, page_h / mm, target["w"], target["h"])
    lw, lh = lw_mm * mm, lh_mm * mm
    margin = MARGIN_MM * mm
    gap = GAP_MM * mm
    per_hal = kolom * baris
    for i, a in enumerate(aset_grup):
        pos = i % per_hal
        if pos == 0 and (i or mulai_halaman_baru):
            c.showPage()
        kol = pos % kolom
        brs = pos // kolom
        x = margin + kol * (lw + gap)
        y = page_h - margin - (brs + 1) * lh - brs * gap
        _gambar_stiker(c, x, y, lw, lh, target, a, kop, logo, mm)
    return bool(aset_grup)


@stiker_router.get("/stiker/label")
async def cetak_stiker_label(
    ukuran: str = "sedang",
    kertas: str = "A4",
    asset_ids: str = "",
    # ── filter identik GET /assets (mengikuti filter aktif daftar) ──
    search: str = "",
    category: str = "",
    activity_id: str = "",
    condition: str = "",
    status: str = "",
    location: str = "",
    eselon1_filter: str = "",
    eselon2_filter: str = "",
    stiker_status: str = "",
    inventory_status: str = "",
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
    per ukuran (besar → sedang → kecil)."""
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

    ids = [i.strip() for i in str(asset_ids or "").split(",") if i.strip()]
    if ids:
        query = {"id": {"$in": ids[:MAKS_STIKER]}, "dihapus": {"$ne": True}}
    else:
        from routes.assets import build_asset_search_query
        query = build_asset_search_query(
            search=search, category=category, activity_id=activity_id,
            condition=condition, status=status, location=location,
            eselon1_filter=eselon1_filter, eselon2_filter=eselon2_filter,
            stiker_status=stiker_status, inventory_status=inventory_status,
            price_min=price_min, price_max=price_max, nomor_spm=nomor_spm,
            perolehan_dari=perolehan_dari, user_filter=user_filter,
            pengguna_nip=pengguna_nip, beli_dari=beli_dari,
            beli_sampai=beli_sampai,
        )
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
    logo = _logo_reader(kop.get("logo_url"))

    page_w, page_h = page
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page)
    c.setTitle(f"Stiker Label BMN — {ukuran} — {kertas}")
    if ukuran == "per_aset":
        # Kelompokkan sesuai pilihan tiap aset; tiap kelompok grid sendiri.
        ada = False
        for u, grup in kelompokkan_per_ukuran(aset):
            _gambar_grup(c, grup, u, page_w, page_h, kop, logo, mm,
                         mulai_halaman_baru=ada)
            ada = True
    else:
        _gambar_grup(c, aset, ukuran, page_w, page_h, kop, logo, mm,
                     mulai_halaman_baru=False)
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
