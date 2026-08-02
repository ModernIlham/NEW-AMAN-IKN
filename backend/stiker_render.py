"""Penggambar STIKER LABEL BMN ke kanvas ReportLab — tanpa DB/auth.

Dipisahkan dari `routes/stiker.py` supaya tata letaknya bisa DIUJI dengan
merender PDF sungguhan tanpa MongoDB (pola yang sama dipakai laporan
persediaan). Keputusan tipografi & grid ada di `stiker_utils` (murni);
modul ini hanya menerjemahkannya menjadi perintah gambar.
"""
import io

from stiker_utils import (GAP_MM, MARGIN_MM, TARGET_STIKER, bagi_baris,
                          format_dimensi, grid_optimal, muat_satu_baris,
                          rencana_badan, susun_header, tinggi_header,
                          ukuran_font)


def logo_reader(logo_url: str):
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


def _pengukur():
    """(ukur_tebal, ukur_biasa) — pengukur lebar teks untuk stiker_utils."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    def tebal(teks, size):
        return stringWidth(str(teks), "Helvetica-Bold", size)

    def biasa(teks, size):
        return stringWidth(str(teks), "Helvetica", size)

    return tebal, biasa


def gambar_stiker(c, x, y, w, h, ukuran, aset, kop, logo, mm):
    """Gambar SATU stiker di (x, y) pojok kiri-bawah, dimensi (w, h) pt.

    Susunan (hierarki dari besar ke kecil): kepala = logo + NAMA INSTANSI
    (menyusut/ pecah dua baris bila panjang) + nama satker/kode satker;
    badan = KODE BARANG + NUP, lalu NAMA BARANG, lalu SUB-SUB KELOMPOK —
    dua yang terakhir MELANJUT ke baris berikutnya bila belum habis, bukan
    dipotong di baris pertama. QR di kanan dengan gap aman dari garis potong.
    Ukuran huruf & jatah baris dihitung `stiker_utils` (murni, teruji)."""
    ukur_tebal, ukur_biasa = _pengukur()
    f = ukuran_font(w / mm, h / mm)
    hdr_dasar = tinggi_header(h / mm, ukuran) * mm
    pad = 1.6 * mm

    # Kepala boleh TUMBUH (sampai batas) demi nama instansi panjang: dengan
    # kepala setinggi standar, nama sepanjang "Kementerian Pekerjaan Umum dan
    # Perumahan Rakyat Republik Indonesia" tak muat sekalipun disusutkan ke
    # lantai keterbacaan, dan dulu berakhir terpotong "..." di stiker kecil.
    # Badan menyusut seperlunya — jatah barisnya dihitung ulang dari sisa.
    hdr_maks = min(h * 0.46, hdr_dasar * 1.85)
    nama = str(kop.get("nama_instansi") or kop.get("nama_unit_organisasi")
               or "").strip()
    baris2 = str(kop.get("_baris2_stiker") or "").strip()
    logo_w_perkiraan = (hdr_dasar - 1.2 * mm + pad) if (
        logo is not None and (w / mm) >= 60) else 0
    lebar_hdr = w - logo_w_perkiraan - 2 * pad
    kepala = susun_header(nama, baris2, lebar_hdr, hdr_maks - 1.0 * mm,
                          f["instansi"], f["sub"], ukur_tebal, ukur_biasa)
    tinggi_isi = (len(kepala["baris"]) * kepala["size"] * 1.06
                  + (kepala["size2"] * 1.25 if kepala["baris2"] else 0))
    hdr = max(hdr_dasar, min(hdr_maks, tinggi_isi + 1.4 * mm))

    c.setLineWidth(0.8)
    c.rect(x, y, w, h)

    # ── Kepala: logo kiri + nama instansi + baris kedua ──
    hdr_y = y + h - hdr
    logo_w = 0
    if logo is not None and (w / mm) >= 60:
        sisi = min(hdr - 1.2 * mm, hdr_dasar)
        try:
            c.drawImage(logo, x + pad, hdr_y + (hdr - sisi) / 2, width=sisi,
                        height=sisi, preserveAspectRatio=True, mask="auto")
            logo_w = sisi + pad
        except Exception:
            logo_w = 0
    tengah_hdr = x + logo_w + (w - logo_w) / 2
    ky = hdr_y + (hdr + tinggi_isi) / 2 - kepala["size"]
    c.setFont("Helvetica-Bold", kepala["size"])
    for baris in kepala["baris"]:
        c.drawCentredString(tengah_hdr, ky, baris)
        ky -= kepala["size"] * 1.06
    if kepala["baris2"]:
        c.setFont("Helvetica", kepala["size2"])
        c.drawCentredString(tengah_hdr, ky - kepala["size2"] * 0.12,
                            kepala["baris2"])
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

    tinggi_badan = h - hdr - 2 * pad
    jatah = rencana_badan(tinggi_badan, f)

    ty = y + h - hdr - pad - f["kode"]
    label_nup = f"NUP: {nup}" if nup else ""
    lebar_nup = ukur_tebal(label_nup, f["nup"]) if label_nup else 0
    kode_muat, f_kode = muat_satu_baris(
        kode, lebar_teks - (lebar_nup + 2.5 * mm if label_nup else 0),
        ukur_tebal, f["kode"], f["kode"] * 0.78)
    c.setFont("Helvetica-Bold", f_kode)
    c.drawString(x + pad, ty, kode_muat)
    if label_nup:
        c.setFont("Helvetica-Bold", f["nup"])
        c.drawRightString(x + pad + lebar_teks, ty, label_nup)
    ty -= f["kode"] * 0.32

    if jatah["nama"]:
        c.setFont("Helvetica-Bold", f["nama"])
        for baris in bagi_baris(nama_brg, lebar_teks, ukur_tebal, f["nama"],
                                jatah["nama"]):
            ty -= f["nama"] * 1.18
            c.drawString(x + pad, ty, baris)
    if jatah["subsub"] and subsub:
        c.setFont("Helvetica", f["subsub"])
        for baris in bagi_baris(subsub, lebar_teks, ukur_biasa, f["subsub"],
                                jatah["subsub"]):
            ty -= f["subsub"] * 1.16
            c.drawString(x + pad, ty, baris)

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


def _panah_ukur(c, x1, y1, x2, y2, sirip):
    """Garis ukur ber-panah dua arah (dipakai stiker CONTOH)."""
    c.line(x1, y1, x2, y2)
    if abs(y2 - y1) < 0.01:      # mendatar
        for xx, arah in ((x1, 1), (x2, -1)):
            c.line(xx, y1, xx + arah * sirip, y1 + sirip * 0.55)
            c.line(xx, y1, xx + arah * sirip, y1 - sirip * 0.55)
    else:                        # tegak
        for yy, arah in ((y1, 1), (y2, -1)):
            c.line(x1, yy, x1 + sirip * 0.55, yy + arah * sirip)
            c.line(x1, yy, x1 - sirip * 0.55, yy + arah * sirip)


def gambar_sampel(c, x, y, w, h, ukuran, lw_mm, lh_mm, mm):
    """Stiker CONTOH berisi UKURAN sebenarnya (panjang × lebar per satuan).

    Dicetak satu buah di akhir tiap kelompok ukuran supaya pemesan bahan
    stiker bisa mengukur langsung hasil cetak — bukan untuk ditempel."""
    ukur_tebal, ukur_biasa = _pengukur()
    f = ukuran_font(w / mm, h / mm)
    pad = 1.6 * mm
    c.saveState()
    c.setDash(2, 2)
    c.setLineWidth(0.8)
    c.rect(x, y, w, h)
    c.setDash()

    judul = "CONTOH UKURAN"
    teks_dim = format_dimensi(lw_mm, lh_mm)
    f_judul = muat_satu_baris(judul, w - 2 * pad, ukur_tebal,
                              f["nama"], f["label"])[1]
    dim_teks, f_dim = muat_satu_baris(teks_dim, w - 2 * pad, ukur_tebal,
                                      f["kode"], f["label"])
    ty = y + h - pad - f_judul
    c.setFont("Helvetica-Bold", f_judul)
    c.drawCentredString(x + w / 2, ty, judul)
    ty -= f_dim * 1.35
    c.setFont("Helvetica-Bold", f_dim)
    c.drawCentredString(x + w / 2, ty, dim_teks)
    ty -= f["label"] * 1.3
    c.setFont("Helvetica", f["label"])
    c.drawCentredString(x + w / 2, ty, f"Ukuran {str(ukuran).capitalize()}"
                        " — bukan untuk ditempel")

    # Garis ukur: lebar (mendatar, bawah) & tinggi (tegak, kiri).
    sirip = 1.2 * mm
    c.setLineWidth(0.5)
    _panah_ukur(c, x + pad, y + pad + f["label"] * 1.5,
                x + w - pad, y + pad + f["label"] * 1.5, sirip)
    c.setFont("Helvetica", f["label"])
    c.drawCentredString(x + w / 2, y + pad + f["label"] * 0.3,
                        f"lebar {teks_dim.split(' × ')[0]} mm")
    _panah_ukur(c, x + pad * 1.4, y + pad, x + pad * 1.4,
                min(ty - f["label"] * 0.6, y + h - pad), sirip)
    c.saveState()
    c.translate(x + pad * 0.6, y + h / 2)
    c.rotate(90)
    c.drawCentredString(0, 0, f"tinggi {teks_dim.split(' × ')[1]}")
    c.restoreState()
    c.restoreState()


def gambar_grup(c, aset_grup, ukuran, page_w, page_h, kop, logo, mm,
                 mulai_halaman_baru, sampel_ukuran=True):
    """Gambar satu KELOMPOK ukuran (grid penuh sendiri). Bila `sampel_ukuran`,
    satu sel TERAKHIR diisi stiker CONTOH berisi dimensi nyata per satuan.
    Return True bila ada halaman yang tergambar."""
    target = TARGET_STIKER[ukuran]
    kolom, baris, lw_mm, lh_mm = grid_optimal(
        page_w / mm, page_h / mm, target["w"], target["h"])
    lw, lh = lw_mm * mm, lh_mm * mm
    margin = MARGIN_MM * mm
    gap = GAP_MM * mm
    per_hal = kolom * baris
    isi = [("aset", a) for a in aset_grup]
    if sampel_ukuran and isi:
        isi.append(("sampel", None))
    for i, (jenis, a) in enumerate(isi):
        pos = i % per_hal
        if pos == 0 and (i or mulai_halaman_baru):
            c.showPage()
        kol = pos % kolom
        brs = pos // kolom
        x = margin + kol * (lw + gap)
        y = page_h - margin - (brs + 1) * lh - brs * gap
        if jenis == "sampel":
            gambar_sampel(c, x, y, lw, lh, ukuran, lw_mm, lh_mm, mm)
        else:
            gambar_stiker(c, x, y, lw, lh, ukuran, a, kop, logo, mm)
    return bool(isi)
