"""LAPORAN PERSEDIAAN GAYA SAKTI — tujuh laporan resmi (PDF).

Meniru tata letak contoh resmi SAKTI (satker 691778): judul dua baris di
tengah, blok identitas UAPB/UAKPB kiri, blok meta (Tgl Data / Tanggal /
Kode Lap) kanan, tabel bergaris penuh dengan subtotal per kelompok.
Lima endpoint mencakup tujuh laporan (parameter `kategori` memilih daftar
Usang / Rusak / Tidak Dikuasai). Data disusun helper murni
`persediaan_laporan_utils` (teruji unit); route hanya memasok jurnal +
master ter-scope satker.
"""
import asyncio
from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth_utils import require_user
from db import db
from persediaan_akun_utils import AKUN_PERSEDIAAN_DEFAULT, akun_persediaan
from persediaan_laporan_utils import (
    posisi_asof, susun_daftar_nonaktif, susun_lap_layer, susun_lap_mutasi,
    susun_lap_neraca, susun_lap_persediaan,
)
from persediaan_utils import rekap_nonaktif, today_wib

persediaan_laporan_router = APIRouter()

_KATEGORI_NONAKTIF = {
    "usang": ("DAFTAR BARANG PERSEDIAAN USANG", "lap_sedia_usang"),
    "rusak": ("DAFTAR BARANG PERSEDIAAN RUSAK", "lap_sedia_rusak"),
    "tidak_dikuasai": ("DAFTAR BARANG PERSEDIAAN TIDAK DIKUASAI",
                       "lap_sedia_kuasa"),
}

_BULAN_ID = ["", "JANUARI", "FEBRUARI", "MARET", "APRIL", "MEI", "JUNI",
             "JULI", "AGUSTUS", "SEPTEMBER", "OKTOBER", "NOVEMBER",
             "DESEMBER"]


def _rp(v) -> str:
    """Format angka gaya laporan SAKTI: ribuan berkoma, minus di depan."""
    n = int(round(float(v or 0)))
    return f"{n:,}"


def _periode_teks(sampai_iso: str) -> str:
    from datetime import date
    try:
        t = date.fromisoformat(str(sampai_iso or "")[:10])
    except (ValueError, TypeError):
        return str(sampai_iso or "")
    return f"{t.day} {_BULAN_ID[t.month]} {t.year}"


async def _identitas_sakti(user):
    """Identitas UAPB/UAKPB untuk kop laporan: master satker (nama + kode
    lengkap 20 digit → 3 digit awal = kode BA) + nama instansi global."""
    from shared_utils import kode_satker_user
    kode = kode_satker_user(user) or ""
    satker = None
    if kode:
        satker = await db.satker.find_one(
            {"kode_satker": kode},
            {"_id": 0, "nama_satker": 1, "kode_satker_lengkap": 1})
    settings = await db.report_settings.find_one(
        {"type": "global"}, {"_id": 0}) or {}
    lengkap = str((satker or {}).get("kode_satker_lengkap") or "").strip()
    kode_ba = "".join(c for c in lengkap if c.isdigit())[:3]
    return {
        "kode_uapb": kode_ba,
        "nama_uapb": str(settings.get("nama_instansi") or "").strip().upper(),
        "kode_uakpb": kode,
        "nama_uakpb": str((satker or {}).get("nama_satker")
                          or settings.get("nama_unit_organisasi")
                          or "").strip().upper(),
    }


def _kop_sakti(judul, sampai_iso, ident, kode_lap, doc_width):
    """Blok kepala gaya SAKTI: judul 2 baris di tengah + identitas kiri
    (UAPB/UAKPB) + meta kanan (Tgl Data/Tanggal/Kode Lap)."""
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    st = getSampleStyleSheet()
    judul_style = ParagraphStyle("SaktiJudul", parent=st["Normal"],
                                 fontName="Helvetica-Bold", fontSize=10.5,
                                 alignment=TA_CENTER, leading=13)
    kecil = ParagraphStyle("SaktiKecil", parent=st["Normal"],
                           fontName="Helvetica", fontSize=7.5, leading=9.5)
    tebal = ParagraphStyle("SaktiTebal", parent=kecil,
                           fontName="Helvetica-Bold")
    now = datetime.now(timezone.utc)
    kiri = Table([
        [Paragraph("UAPB", tebal), Paragraph(f": {ident['kode_uapb'] or '-'}", tebal),
         Paragraph(ident["nama_uapb"] or "-", tebal)],
        [Paragraph("UAKPB", tebal), Paragraph(f": {ident['kode_uakpb'] or '-'}", tebal),
         Paragraph(ident["nama_uakpb"] or "-", tebal)],
    ], colWidths=[14 * mm, 18 * mm, None])
    kiri.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
    ]))
    kanan = Table([
        [Paragraph("Tgl Data", kecil), Paragraph(f": {today_wib()}", kecil)],
        [Paragraph("Tanggal", kecil),
         Paragraph(f": {now.date().isoformat()}", kecil)],
        [Paragraph("Kode Lap", kecil), Paragraph(f": {kode_lap}", kecil)],
    ], colWidths=[16 * mm, 34 * mm])
    kanan.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
    ]))
    baris_atas = Table([[kiri, kanan]],
                       colWidths=[doc_width - 54 * mm, 54 * mm])
    baris_atas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [
        Paragraph(judul, judul_style),
        Paragraph(f"UNTUK PERIODE YANG BERAKHIR {_periode_teks(sampai_iso)}",
                  judul_style),
        Spacer(1, 4 * mm),
        baris_atas,
        Spacer(1, 3 * mm),
    ]


def _gaya_tabel_sakti():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ])


async def _data_jurnal(user):
    """Jurnal ter-scope + master ter-scope + peta akun + uraian kode 10."""
    from routes.persediaan import _scope_jurnal
    from shared_utils import scope_query_field_satker
    # Batas keras 200k baris: jurnal append-only tumbuh monoton — tanpa
    # pagar ini setiap render PDF memuat seluruh koleksi ke memori.
    jurnal = [t async for t in db.transaksi_persediaan.find(
        await _scope_jurnal(user), {"_id": 0, "rincian_layer": 0})
        .sort("timestamp", 1).limit(200000)]
    master = [m async for m in db.persediaan.find(
        scope_query_field_satker(user), {"_id": 0})]
    peta_akun = {}
    async for m in db.persediaan_akun.find({}, {"_id": 0}):
        peta_akun[m["sub_kelompok"]] = m
    uraian_akun = dict(AKUN_PERSEDIAAN_DEFAULT)
    async for a in db.referensi_akun.find(
            {"kode": {"$regex": "^1171"}}, {"_id": 0, "kode": 1, "uraian": 1}):
        uraian_akun.setdefault(a["kode"], a.get("uraian") or "")
    kode10_set = {str(m.get("kode_barang") or "")[:10] for m in master}
    uraian_kode10 = {}
    if kode10_set:
        async for k in db.kodefikasi.find(
                {"kode": {"$in": sorted(kode10_set)}},
                {"_id": 0, "kode": 1, "uraian": 1}):
            uraian_kode10[k["kode"]] = k.get("uraian") or ""
    return jurnal, master, peta_akun, uraian_akun, uraian_kode10


def _akun_of(peta_akun):
    return lambda kode: akun_persediaan(kode, peta_akun)["akun"]


async def _kirim_pdf(elements, nama_file, judul_footer):
    from routes.reports import _page_footer_factory, _std_doc
    buffer = BytesIO()
    doc = _std_doc(buffer)
    footer = _page_footer_factory(judul_footer)
    await asyncio.to_thread(doc.build, elements, onFirstPage=footer,
                            onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nama_file}"'})


def _p(teks, tebal=False, tengah=False, kanan=False):
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph
    from xml.sax.saxutils import escape
    st = getSampleStyleSheet()
    gaya = ParagraphStyle(
        "SaktiCell", parent=st["Normal"], fontSize=7.5, leading=9,
        fontName="Helvetica-Bold" if tebal else "Helvetica",
        alignment=TA_CENTER if tengah else (TA_RIGHT if kanan else 0))
    return Paragraph(escape(str(teks)), gaya)


@persediaan_laporan_router.get("/persediaan/laporan/sakti/persediaan-pdf")
async def lap_sakti_persediaan(
    sampai: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: dict = Depends(require_user),
):
    """LAPORAN BARANG PERSEDIAAN — per akun neraca → kode barang 10 digit
    → nilai, + keterangan nilai kondisi rusak/usang (bahan CaLK)."""
    from reportlab.lib.units import mm
    from reportlab.platypus import Spacer, Table
    from routes.reports import _fit_col_widths, _std_doc

    sampai = sampai or today_wib()
    jurnal, _master, peta_akun, uraian_akun, uraian_kode10 = \
        await _data_jurnal(user)
    posisi = posisi_asof(jurnal, sampai)
    lap = susun_lap_persediaan(posisi, _akun_of(peta_akun), uraian_akun,
                               uraian_kode10)
    non = rekap_nonaktif(jurnal)
    nilai_rusak = sum(e["nilai"] for e in non["rusak"].values())
    nilai_usang = sum(e["nilai"] for e in non["usang"].values())
    ident = await _identitas_sakti(user)

    doc_width = _std_doc(BytesIO()).width
    elements = _kop_sakti("LAPORAN BARANG PERSEDIAAN", sampai, ident,
                          "lap_bmn_sedia_satker", doc_width)
    data = [[_p("Kode", tebal=True, tengah=True),
             _p("Uraian", tebal=True, tengah=True),
             _p("Jumlah", tebal=True, tengah=True)]]
    for a in lap["akun"]:
        data.append([_p(a["akun"], tebal=True, tengah=True),
                     _p(a["uraian"], tebal=True), _p("")])
        for b in a["baris"]:
            data.append([_p(b["kode10"], tengah=True), _p(b["uraian"]),
                         _p(_rp(b["nilai"]), kanan=True)])
        data.append([_p(""), _p(f"Jumlah {a['uraian']}", tebal=True),
                     _p(_rp(a["nilai"]), tebal=True, kanan=True)])
    data.append([_p(""), _p("TOTAL", tebal=True, tengah=True),
                 _p(_rp(lap["total"]), tebal=True, kanan=True)])
    tabel = Table(data, colWidths=_fit_col_widths([90, 300, 110], doc_width),
                  repeatRows=1)
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    elements.append(Spacer(1, 4 * mm))
    elements.append(_p("Keterangan :"))
    elements.append(_p(f"1. Persediaan senilai Rp. {_rp(nilai_rusak)} "
                       "dalam kondisi rusak."))
    elements.append(_p(f"2. Persediaan senilai Rp. {_rp(nilai_usang)} "
                       "dalam kondisi usang."))
    return await _kirim_pdf(elements, "Laporan_Persediaan.pdf",
                            "Laporan Barang Persediaan")


@persediaan_laporan_router.get("/persediaan/laporan/sakti/neraca-pdf")
async def lap_sakti_neraca(
    sampai: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: dict = Depends(require_user),
):
    """LAPORAN POSISI PERSEDIAAN DI NERACA — satu baris per akun 1171xx;
    akun yang dipakai master tetap tampil meski nilainya 0 (pola SAKTI)."""
    from reportlab.platypus import Table
    from routes.reports import _fit_col_widths, _std_doc

    sampai = sampai or today_wib()
    jurnal, master, peta_akun, uraian_akun, _u10 = await _data_jurnal(user)
    posisi = posisi_asof(jurnal, sampai)
    akun_of = _akun_of(peta_akun)
    akun_terdaftar = {akun_of(m.get("kode_barang") or "") for m in master}
    lap = susun_lap_neraca(posisi, akun_of, uraian_akun, akun_terdaftar)
    ident = await _identitas_sakti(user)

    doc_width = _std_doc(BytesIO()).width
    elements = _kop_sakti("LAPORAN POSISI PERSEDIAAN DI NERACA", sampai,
                          ident, "lap_bmn_sedia_posisi_neraca_satker",
                          doc_width)
    data = [[_p("Kode", tebal=True, tengah=True),
             _p("Uraian", tebal=True, tengah=True),
             _p("NILAI", tebal=True, tengah=True)]]
    for b in lap["baris"]:
        data.append([_p(b["akun"], tengah=True), _p(b["uraian"]),
                     _p(_rp(b["nilai"]), kanan=True)])
    data.append([_p(""), _p("JUMLAH", tebal=True),
                 _p(_rp(lap["total"]), tebal=True, kanan=True)])
    tabel = Table(data, colWidths=_fit_col_widths([90, 300, 110], doc_width),
                  repeatRows=1)
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    return await _kirim_pdf(elements, "Laporan_Posisi_Persediaan_Neraca.pdf",
                            "Laporan Posisi Persediaan di Neraca")


@persediaan_laporan_router.get("/persediaan/laporan/sakti/mutasi-pdf")
async def lap_sakti_mutasi(
    dari: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sampai: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    user: dict = Depends(require_user),
):
    """LAPORAN MUTASI BARANG PERSEDIAAN — per akun: SALDO AWAL / MUTASI
    TAMBAH / MUTASI KURANG / NILAI akhir (nilai rupiah, dari jurnal)."""
    from reportlab.platypus import Table
    from routes.reports import _fit_col_widths, _std_doc

    if dari > sampai:
        raise HTTPException(status_code=400,
                            detail="Tanggal 'dari' melewati 'sampai'")
    jurnal, _m, peta_akun, uraian_akun, _u10 = await _data_jurnal(user)
    lap = susun_lap_mutasi(jurnal, dari, sampai, _akun_of(peta_akun),
                           uraian_akun)
    ident = await _identitas_sakti(user)

    doc_width = _std_doc(BytesIO()).width
    elements = _kop_sakti("LAPORAN MUTASI BARANG PERSEDIAAN", sampai, ident,
                          "lap_bmn_sedia_mutasi_satker", doc_width)
    data = [[_p("Kode", tebal=True, tengah=True),
             _p("Uraian", tebal=True, tengah=True),
             _p("SALDO AWAL", tebal=True, tengah=True),
             _p("MUTASI TAMBAH", tebal=True, tengah=True),
             _p("MUTASI KURANG", tebal=True, tengah=True),
             _p("NILAI", tebal=True, tengah=True)]]
    for b in lap["baris"]:
        data.append([_p(b["akun"], tengah=True), _p(b["uraian"]),
                     _p(_rp(b["awal"]), kanan=True),
                     _p(_rp(b["tambah"]), kanan=True),
                     _p(_rp(b["kurang"]), kanan=True),
                     _p(_rp(b["akhir"]), kanan=True)])
    t = lap["total"]
    data.append([_p(""), _p("JUMLAH", tebal=True),
                 _p(_rp(t["awal"]), tebal=True, kanan=True),
                 _p(_rp(t["tambah"]), tebal=True, kanan=True),
                 _p(_rp(t["kurang"]), tebal=True, kanan=True),
                 _p(_rp(t["akhir"]), tebal=True, kanan=True)])
    tabel = Table(data, colWidths=_fit_col_widths(
        [55, 150, 75, 75, 75, 75], doc_width), repeatRows=1)
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    return await _kirim_pdf(elements, "Laporan_Mutasi_Persediaan.pdf",
                            "Laporan Mutasi Barang Persediaan")


@persediaan_laporan_router.get("/persediaan/laporan/sakti/layer-pdf")
async def lap_sakti_layer(user: dict = Depends(require_user)):
    """LAPORAN BARANG PERSEDIAAN PER LAYER — komposisi layer FIFO KINI
    (kode 16 digit per layer, kuantitas & nilai) per kode barang 10 digit.

    Berbeda dari laporan lain, per-layer memotret keadaan sekarang di
    master — komposisi layer historis tidak disimpan per tanggal.
    """
    from reportlab.platypus import Table
    from routes.reports import _fit_col_widths, _std_doc

    _j, master, _pa, _ua, uraian_kode10 = await _data_jurnal(user)
    lap = susun_lap_layer(master, uraian_kode10)
    ident = await _identitas_sakti(user)
    sampai = today_wib()

    doc_width = _std_doc(BytesIO()).width
    elements = _kop_sakti("LAPORAN BARANG PERSEDIAAN PER LAYER", sampai,
                          ident, "lap_bmn_sedia_layer_satker", doc_width)
    data = [[_p("Kode", tebal=True, tengah=True),
             _p("Uraian", tebal=True, tengah=True),
             _p("Layer", tebal=True, tengah=True),
             _p("Kuantitas", tebal=True, tengah=True),
             _p("Jumlah", tebal=True, tengah=True)]]
    nama_uakpb = ident["nama_uakpb"] or "-"
    data.append([_p(f"UAPKPB - 000 ({nama_uakpb})", tebal=True),
                 _p(""), _p(""), _p(""), _p("")])
    for k in lap["kelompok"]:
        data.append([_p(f"{k['kode10']} ({k['uraian']})", tebal=True),
                     _p(""), _p(""), _p(""), _p("")])
        for b in k["baris"]:
            data.append([_p(b["kode16"], tengah=True), _p(b["uraian"]),
                         _p(b["layer"], tengah=True),
                         _p(b["qty"], kanan=True),
                         _p(_rp(b["nilai"]), kanan=True)])
        data.append([_p(""), _p(f"Jumlah Kode Barang {k['kode10']} "
                                f"({k['uraian']})", tebal=True),
                     _p(""), _p(""),
                     _p(_rp(k["nilai"]), tebal=True, kanan=True)])
    data.append([_p(""), _p("TOTAL", tebal=True, tengah=True), _p(""),
                 _p(""), _p(_rp(lap["total"]), tebal=True, kanan=True)])
    tabel = Table(data, colWidths=_fit_col_widths(
        [105, 210, 35, 55, 90], doc_width), repeatRows=1)
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    return await _kirim_pdf(elements, "Laporan_Persediaan_Per_Layer.pdf",
                            "Laporan Barang Persediaan Per Layer")


@persediaan_laporan_router.get("/persediaan/laporan/sakti/nonaktif-pdf")
async def lap_sakti_nonaktif(
    kategori: str = Query(..., pattern=r"^(usang|rusak|tidak_dikuasai)$"),
    user: dict = Depends(require_user),
):
    """DAFTAR BARANG PERSEDIAAN USANG / RUSAK / TIDAK DIKUASAI — dari
    derivasi jurnal (K04/K05/K09 dikurangi H01/H02/H03/M94)."""
    from reportlab.platypus import Table
    from routes.reports import _fit_col_widths, _std_doc

    judul, kode_lap = _KATEGORI_NONAKTIF[kategori]
    jurnal, _m, _pa, _ua, _u10 = await _data_jurnal(user)
    lap = susun_daftar_nonaktif(rekap_nonaktif(jurnal).get(kategori))
    ident = await _identitas_sakti(user)
    sampai = today_wib()

    doc_width = _std_doc(BytesIO()).width
    elements = _kop_sakti(judul, sampai, ident, kode_lap, doc_width)
    data = [[_p("KODE", tebal=True, tengah=True),
             _p("URAIAN", tebal=True, tengah=True),
             _p("KUANTITAS", tebal=True, tengah=True),
             _p("NILAI", tebal=True, tengah=True)]]
    for b in lap["baris"]:
        data.append([_p(b["kode"], tengah=True), _p(b["uraian"]),
                     _p(b["qty"], kanan=True),
                     _p(_rp(b["nilai"]), kanan=True)])
    if lap["baris"]:
        data.append([_p(""), _p("JUMLAH", tebal=True),
                     _p(lap["total_qty"], tebal=True, kanan=True),
                     _p(_rp(lap["total_nilai"]), tebal=True, kanan=True)])
    tabel = Table(data, colWidths=_fit_col_widths(
        [110, 250, 60, 90], doc_width), repeatRows=1)
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    if not lap["baris"]:
        elements.append(_p("Tidak ada barang pada daftar ini.", tengah=True))
    nama = {"usang": "Daftar_Persediaan_Usang.pdf",
            "rusak": "Daftar_Persediaan_Rusak.pdf",
            "tidak_dikuasai": "Daftar_Persediaan_Tidak_Dikuasai.pdf"}[kategori]
    return await _kirim_pdf(elements, nama, judul.title())
