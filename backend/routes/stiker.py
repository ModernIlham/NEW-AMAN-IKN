"""Cetak STIKER LABEL BMN — 3 ukuran (besar/sedang/kecil) pada kertas A4/A3.

Desain meniru contoh label resmi satker (referensi pemilik): border kotak,
header logo + nama instansi + kode register lengkap, garis pemisah, badan
kiri (kode barang + NUP, kategori, nama barang terpotong "..."), QR besar di
kanan. Payload QR memakai format yang sama dengan Kartu Inventarisasi
(`#kode_register` / `#kode-nup`) sehingga pemindai internal aplikasi langsung
mengenalinya.

Cakupan aset MENGIKUTI FILTER AKTIF daftar aset (search/kategori/kondisi/
lokasi/eselon/status stiker/dll. — parameter identik `GET /assets`) atau
daftar `asset_ids` eksplisit (mis. halaman yang sedang tampil).
"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth_utils import require_user
from db import db
from shared_utils import (kode_satker_user, pastikan_akses_kegiatan_id,
                          pengaturan_kop, scope_query_aset)

stiker_router = APIRouter()

# (lebar, tinggi, tinggi header, jumlah baris deskripsi) dalam mm.
UKURAN_STIKER = {
    "besar": {"w": 95, "h": 45, "header": 12, "baris_desc": 3},
    "sedang": {"w": 62, "h": 30, "header": 8.5, "baris_desc": 2},
    "kecil": {"w": 45, "h": 22, "header": 6.5, "baris_desc": 1},
}
MAKS_STIKER = 2000

_PROJ_STIKER = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
                "category": 1, "kode_register": 1, "activity_id": 1}


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


def _potong_baris(teks, font, size, lebar, maks_baris):
    """Pecah teks ke maks N baris selebar `lebar`; baris terakhir di-'...'."""
    from reportlab.lib.utils import simpleSplit
    baris = simpleSplit(str(teks or ""), font, size, lebar)
    if len(baris) > maks_baris:
        baris = baris[:maks_baris]
        baris[-1] = baris[-1].rstrip(".") + "..."
    return baris


def _gambar_stiker(c, x, y, spec, aset, kop, logo, mm):
    """Gambar SATU stiker di posisi (x, y) = pojok kiri-bawah. Meniru desain
    referensi: border, header (logo+instansi+kode register), garis, badan
    kiri + QR kanan."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    w, h = spec["w"] * mm, spec["h"] * mm
    hdr = spec["header"] * mm
    pad = 1.6 * mm
    s = spec["w"] / 95.0  # faktor skala relatif desain besar
    f_satker = max(4.6, 8.5 * s)
    f_kreg = max(4.0, 7.0 * s)
    f_kode = max(4.6, 8.0 * s)
    f_teks = max(4.2, 7.0 * s)

    c.setLineWidth(0.8)
    c.rect(x, y, w, h)

    # ── Header: logo kiri + nama instansi (tengah) + kode register ──
    hdr_y = y + h - hdr
    tengah_x = x + w / 2
    logo_w = 0
    if logo is not None and spec["w"] >= 60:
        sisi = hdr - 1.2 * mm
        try:
            c.drawImage(logo, x + pad, hdr_y + 0.6 * mm, width=sisi,
                        height=sisi, preserveAspectRatio=True, mask="auto")
            logo_w = sisi + pad
        except Exception:
            logo_w = 0
    nama = str(kop.get("nama_instansi") or kop.get("nama_unit_organisasi")
               or "").strip()
    kreg = str(aset.get("kode_register") or "").strip()
    c.setFont("Helvetica-Bold", f_satker)
    c.drawCentredString(tengah_x + logo_w / 2, y + h - hdr / 2 - f_satker * 0.1,
                        nama[:60])
    if kreg:
        c.setFont("Helvetica", f_kreg)
        c.drawCentredString(tengah_x + logo_w / 2,
                            y + h - hdr / 2 - f_satker - f_kreg * 0.35, kreg[:40])
    c.setLineWidth(0.5)
    c.line(x, hdr_y, x + w, hdr_y)

    # ── Badan: teks kiri, QR kanan (QR TIDAK setinggi penuh badan —
    # permintaan pemilik: jangan terlalu besar; 78% tinggi badan, rata
    # tengah vertikal) ──
    badan_h = h - hdr - 2 * pad
    qr_sisi = badan_h * 0.78
    qr_x = x + w - pad - qr_sisi
    qr_y = y + pad + (badan_h - qr_sisi) / 2
    lebar_teks = qr_x - x - 2 * pad

    kode = str(aset.get("asset_code") or "").strip()
    nup = str(aset.get("NUP") or "").strip()
    kategori = str(aset.get("category") or "").strip()
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
    if kategori and spec["baris_desc"] >= 2:
        c.setFont("Helvetica", f_teks)
        c.drawString(x + pad, ty, kategori[:40])
        ty -= f_teks * 1.5
    c.setFont("Helvetica", f_teks)
    for baris in _potong_baris(nama_brg, "Helvetica", f_teks, lebar_teks,
                               spec["baris_desc"]):
        c.drawString(x + pad, ty, baris)
        ty -= f_teks * 1.2

    # QR — payload format pemindai kartu (#kreg / #kode-nup).
    payload = f"#{kreg}" if kreg else f"#{kode}-{nup or '0'}"
    try:
        from reportlab.graphics import renderPDF
        from routes.cards import build_qr_flowable
        qr = build_qr_flowable(payload, qr_sisi)
        if qr is not None:
            renderPDF.draw(qr, c, qr_x, qr_y)
    except Exception:
        pass


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
    """PDF stiker label siap cetak (grid otomatis sesuai ukuran & kertas)."""
    from reportlab.lib.pagesizes import A3, A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas

    spec = UKURAN_STIKER.get(str(ukuran).strip().lower())
    if not spec:
        raise HTTPException(status_code=400,
                            detail="Ukuran harus besar/sedang/kecil")
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

    kop = await pengaturan_kop(kode_satker=kode_satker_user(_user)) or {}
    logo = _logo_reader(kop.get("logo_url"))

    # ── Grid otomatis: kolom × baris menyesuaikan kertas & ukuran stiker.
    # Jarak antar kotak SANGAT RAPAT (permintaan pemilik) — hanya celah
    # tipis 1.5mm agar mudah dipotong tanpa buang kertas. ──
    page_w, page_h = page
    margin = 6 * mm
    gap = 1.5 * mm
    lw, lh = spec["w"] * mm, spec["h"] * mm
    kolom = max(1, int((page_w - 2 * margin + gap) // (lw + gap)))
    baris = max(1, int((page_h - 2 * margin + gap) // (lh + gap)))
    per_hal = kolom * baris

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page)
    c.setTitle(f"Stiker Label BMN — {ukuran} — {kertas}")
    for i, a in enumerate(aset):
        pos = i % per_hal
        if i and pos == 0:
            c.showPage()
        kol = pos % kolom
        brs = pos // kolom
        x = margin + kol * (lw + gap)
        y = page_h - margin - (brs + 1) * lh - brs * gap
        _gambar_stiker(c, x, y, spec, a, kop, logo, mm)
    if terpotong:
        c.showPage()
        c.setFont("Helvetica", 9)
        c.drawString(margin, page_h - margin - 12,
                     f"Catatan: hasil melebihi batas {MAKS_STIKER} stiker — "
                     "persempit filter lalu cetak lagi untuk sisanya.")
    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="stiker_label_{ukuran}_{kertas}.pdf"',
                 "X-Total-Stiker": str(len(aset))})
