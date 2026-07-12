"""Master PERSEDIAAN — langkah 1 modul Inventarisasi Persediaan (§7.4).

Master barang persediaan satker (aset lancar, kodefikasi berawalan '1'):
CRUD + paging/pencarian. Stok & layer FIFO (`batches`) dikelola transaksi
persediaan pada iterasi berikutnya — di sini barang lahir dengan stok 0
dan daftar layer kosong; hapus hanya boleh saat stok masih 0.

Regulasi: docs/PUSTAKA-REGULASI-BMN.md §3 (perpetual + FIFO per layer,
kode golongan '1', batas kritis & kedaluwarsa untuk peringatan/nota dinas).
Referensi teknis: modul persediaan KERJA-BARENG (dipelajari menyeluruh).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from persediaan_fields import EDITABLE_FIELD_NAMES
from persediaan_utils import (
    JENIS_KELUAR, JENIS_MASUK, KODE_PENUH_LEN, KODE_PREFIX_LEN, SATUAN_BAKU,
    buat_layer, klasifikasi_kedaluwarsa, konsumsi_fifo, mutasi_periode,
    next_kode_penuh, next_nup, nilai_persediaan_dari_batches,
    parse_import_persediaan_rows, penyesuaian_opname, status_stok,
    validate_kode_persediaan, validate_transaksi_keluar, validate_transaksi_masuk,
)

persediaan_router = APIRouter()


class PersediaanCreate(BaseModel):
    kode_barang: str = Field(min_length=1, max_length=KODE_PENUH_LEN)
    nup: str = ""                     # kosong → otomatis
    nama_barang: str = Field(min_length=1, max_length=300)
    merk: str = ""
    tipe: str = ""
    satuan: str = "Buah"
    lokasi: str = ""
    batas_kritis: int = Field(0, ge=0)
    expired_default: str = ""         # YYYY-MM-DD; kedaluwarsa bawaan batch
    tahun_anggaran: str = ""
    keterangan: str = ""


class PersediaanUpdate(BaseModel):
    nama_barang: Optional[str] = Field(None, min_length=1, max_length=300)
    merk: Optional[str] = None
    tipe: Optional[str] = None
    satuan: Optional[str] = None
    lokasi: Optional[str] = None
    batas_kritis: Optional[int] = Field(None, ge=0)
    expired_default: Optional[str] = None
    tahun_anggaran: Optional[str] = None
    keterangan: Optional[str] = None


def _doc(item: dict) -> dict:
    stok = int(item.get("stok", 0) or 0)
    return {
        **{k: item.get(k) for k in (
            "id", "kode_barang", "nup", "nama_barang", "merk", "tipe", "satuan",
            "lokasi", "batas_kritis", "expired_default", "tahun_anggaran",
            "keterangan", "stok", "version", "created_at", "updated_at")},
        "status_stok": status_stok(stok, item.get("batas_kritis")),
    }


@persediaan_router.get("/persediaan/satuan-baku")
async def list_satuan(_user: dict = Depends(require_user)):
    """Daftar satuan baku untuk dropdown (referensi, bukan pembatasan keras)."""
    return list(SATUAN_BAKU)


# CATATAN URUTAN: route literal HARUS terdaftar sebelum GET /persediaan/{item_id}
# di bawah — kalau tidak, path literal tertelan sebagai item_id.
@persediaan_router.get("/persediaan/peringatan")
async def peringatan_persediaan(
    horizon_hari: int = Query(30, ge=1, le=365),
    _user: dict = Depends(require_user),
):
    """Daftar pantau (pustaka §3): stok habis/kritis + layer kedaluwarsa.

    Bahan banner peringatan & nota dinas — dihitung dari data nyata
    (stok vs batas kritis; expired layer vs hari ini + horizon).
    """
    today_iso = datetime.now(timezone.utc).date().isoformat()
    habis, kritis, lewat, segera = [], [], [], []
    cursor = db.persediaan.find({}, {"_id": 0})
    async for item in cursor:
        stok = int(item.get("stok", 0) or 0)
        st = status_stok(stok, item.get("batas_kritis"))
        ringkas = {"id": item.get("id"), "kode_barang": item.get("kode_barang"),
                   "nup": item.get("nup"), "nama_barang": item.get("nama_barang"),
                   "satuan": item.get("satuan"), "stok": stok,
                   "batas_kritis": item.get("batas_kritis", 0)}
        if st == "habis":
            habis.append(ringkas)
        elif st == "kritis":
            kritis.append(ringkas)
        exp_lewat, exp_segera = klasifikasi_kedaluwarsa(
            item.get("batches"), today_iso, horizon_hari)
        for e in exp_lewat:
            lewat.append({**ringkas, **e})
        for e in exp_segera:
            segera.append({**ringkas, **e})
    return {"tanggal": today_iso, "horizon_hari": horizon_hari,
            "habis": habis, "kritis": kritis,
            "kedaluwarsa": lewat, "segera_kedaluwarsa": segera,
            "total_masalah": len(habis) + len(kritis) + len(lewat) + len(segera)}


@persediaan_router.get("/persediaan/nota-dinas")
async def nota_dinas_persediaan(
    jenis: str = Query(..., pattern="^(kritis|kedaluwarsa)$"),
    horizon_hari: int = Query(30, ge=1, le=365),
    _user: dict = Depends(require_user),
):
    """Nota dinas PDF otomatis (pustaka §3): stok kritis/habis ATAU layer
    kedaluwarsa — kop surat + tabel + tanda tangan Kuasa Pengguna Barang."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    data = await peringatan_persediaan(horizon_hari=horizon_hari, _user=_user)
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))

    if jenis == "kritis":
        judul = "NOTA DINAS\nUSULAN PENGADAAN PERSEDIAAN (STOK KRITIS/HABIS)"
        rows = data["habis"] + data["kritis"]
        headers = ["No", "Kode Barang", "Nama Barang", "Satuan", "Stok", "Batas Kritis"]
        widths = [28, 120, 190, 60, 45, 65]
        body = [[str(i + 1), r["kode_barang"], r["nama_barang"], r.get("satuan") or "-",
                 str(r["stok"]), str(r.get("batas_kritis") or 0)] for i, r in enumerate(rows)]
        pengantar = ("Bersama ini disampaikan daftar barang persediaan yang stoknya telah "
                     "HABIS atau mencapai batas kritis, untuk menjadi pertimbangan dalam "
                     "pengadaan berikutnya.")
    else:
        judul = "NOTA DINAS\nPERSEDIAAN KEDALUWARSA / SEGERA KEDALUWARSA"
        rows = data["kedaluwarsa"] + data["segera_kedaluwarsa"]
        headers = ["No", "Kode Barang", "Nama Barang", "Jumlah", "Kedaluwarsa"]
        widths = [28, 130, 200, 55, 85]
        body = [[str(i + 1), r["kode_barang"], r["nama_barang"], str(r["qty"]),
                 _fmt_tanggal_id(r["expired"]) or r["expired"]] for i, r in enumerate(rows)]
        pengantar = (f"Bersama ini disampaikan daftar persediaan yang telah/akan kedaluwarsa "
                     f"dalam {data['horizon_hari']} hari ke depan, untuk ditindaklanjuti "
                     f"(pemakaian prioritas, pemindahan, atau usulan penghapusan).")

    elements.extend(_title_block(judul))
    elements.append(Paragraph(f"Tanggal data: {_fmt_tanggal_id(data['tanggal'])}", st['Meta']))
    elements.append(Paragraph(pengantar, st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    if not body:
        elements.append(Paragraph("Tidak ada barang yang memenuhi kriteria saat ini.", st['Cell']))
    else:
        table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for r in body:
            table_data.append([Paragraph(str(c), st['Cell']) for c in r])
        table = Table(table_data, colWidths=_fit_col_widths(widths, doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    kasatker = settings.get("kasatker_nama") or "-"
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': kasatker,
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))

    footer = _page_footer_factory("Nota Dinas Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    fname = f"Nota_Dinas_{'Stok_Kritis' if jenis == 'kritis' else 'Kedaluwarsa'}.pdf"
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})


def _fmt_rp(val):
    try:
        return f"{int(val):,}".replace(",", ".")
    except (ValueError, TypeError, OverflowError):
        return "0"


_TEMPLATE_HEADERS = ["kode_barang", "nup", "nama_barang", "merk", "tipe", "satuan",
                     "lokasi", "batas_kritis", "expired_default", "tahun_anggaran", "keterangan"]


@persediaan_router.get("/persediaan/template")
async def template_persediaan(_user: dict = Depends(require_user)):
    """Template CSV impor master persediaan (kode 10 digit → nomor urut otomatis)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(_TEMPLATE_HEADERS)
    w.writerow(["1010101001", "", "Kertas HVS A4 80gr", "SiDU", "", "Rim", "Gudang ATK", "5", "", "2026", ""])
    w.writerow(["1010101001000002", "1", "Tinta Printer Hitam", "Epson", "003", "Botol", "Gudang ATK", "2", "", "2026", "contoh kode 16 digit"])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="template_persediaan.csv"'})


@persediaan_router.get("/persediaan/export")
async def export_persediaan(_user: dict = Depends(require_user)):
    """Ekspor CSV master persediaan + stok & nilai FIFO terkini."""
    import csv as csv_module
    import io

    from fastapi.responses import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(_TEMPLATE_HEADERS + ["stok", "nilai"])
    async for it in db.persediaan.find({}, {"_id": 0}).sort([("nama_barang", 1), ("kode_barang", 1)]):
        w.writerow([
            it.get("kode_barang"), it.get("nup"), it.get("nama_barang"),
            it.get("merk"), it.get("tipe"), it.get("satuan"), it.get("lokasi"),
            it.get("batas_kritis", 0), it.get("expired_default"),
            it.get("tahun_anggaran"), it.get("keterangan"),
            int(it.get("stok", 0) or 0),
            int(nilai_persediaan_dari_batches(it.get("batches"))),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="master_persediaan.csv"'})


@persediaan_router.post("/persediaan/import")
async def import_persediaan(file: UploadFile = File(...), _user: dict = Depends(require_user)):
    """Impor massal master (CSV/XLSX): kode 16+NUP sudah ada → perbarui field
    non-identitas; selain itu buat baru (kode 10 digit → nomor urut otomatis,
    NUP kosong → otomatis). Stok/layer TIDAK tersentuh impor."""
    from routes.kodefikasi import _rows_from_upload

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File maksimal 10MB")
    rows = _rows_from_upload(file.filename, content)
    entries, errors, dupes = parse_import_persediaan_rows(rows)

    inserted = updated = 0
    now = datetime.now(timezone.utc).isoformat()
    for e in entries:
        kode, nup = e["kode_barang"], e["nup"]
        scalar = {k: v for k, v in e.items() if k not in ("kode_barang", "nup")}
        if len(kode) == KODE_PENUH_LEN and nup:
            res = await db.persediaan.update_one(
                {"kode_barang": kode, "nup": nup},
                {"$set": {**scalar, "updated_at": now}, "$inc": {"version": 1}},
            )
            if res.matched_count:
                updated += 1
                continue
        # buat baru — pakai jalur create agar aturan kode/NUP otomatis sama
        try:
            payload = PersediaanCreate(kode_barang=kode, nup=nup, **scalar)
            await create_persediaan(payload, _user=_user)
            inserted += 1
        except HTTPException as exc:
            errors.append(f"{kode}/{nup or 'auto'}: {exc.detail}")

    return {
        "message": f"Impor selesai: {inserted} baru, {updated} diperbarui",
        "inserted": inserted, "updated": updated,
        "duplikat_dalam_file": dupes,
        "errors": errors[:50], "error_count": len(errors),
    }


@persediaan_router.get("/persediaan/opname/kertas-kerja-pdf")
async def opname_kertas_kerja_pdf(_user: dict = Depends(require_user)):
    """Kertas kerja opname (pustaka §3.3): saldo buku + kolom fisik KOSONG
    untuk diisi saat penghitungan — pola "Cetak Bahan Opname Fisik" SAKTI."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    items = [x async for x in db.persediaan.find({}, {"_id": 0, "batches": 0})]
    items.sort(key=lambda x: (x.get("nama_barang") or "", x.get("kode_barang") or ""))

    today_iso = datetime.now(timezone.utc).date().isoformat()
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("KERTAS KERJA OPNAME FISIK PERSEDIAAN"))
    elements.append(Paragraph(
        f"Saldo buku per {_fmt_tanggal_id(today_iso)} — kolom Stok Fisik & Keterangan diisi saat penghitungan.",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Kode Barang", "Nama Barang", "Satuan", "Stok Buku", "Stok Fisik", "Keterangan"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, it in enumerate(items, start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(it.get("kode_barang") or "-", st['Cell']),
            Paragraph(it.get("nama_barang") or "-", st['Cell']),
            Paragraph(it.get("satuan") or "-", st['CellCenter']),
            Paragraph(str(int(it.get("stok", 0) or 0)), st['CellCenter']),
            Paragraph("", st['Cell']),
            Paragraph("", st['Cell']),
        ])
    if not items:
        elements.append(Paragraph("Belum ada barang persediaan terdaftar.", st['Cell']))
    else:
        table = Table(table_data, colWidths=_fit_col_widths([28, 110, 150, 50, 55, 60, 80], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Penghitung,', 'nama': '...........................', 'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Saksi,', 'nama': '...........................', 'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Mengetahui,', 'nama': '...........................', 'after': ['NIP. ....................']},
    ], doc.width))
    footer = _page_footer_factory("Kertas Kerja Opname Fisik Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="Kertas_Kerja_Opname.pdf"'})


@persediaan_router.get("/persediaan/opname/baof-pdf")
async def opname_baof_pdf(
    tanggal: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """BAOF — Berita Acara Opname Fisik (pustaka §3.3): penyesuaian opname
    pada tanggal tsb + 3 penandatangan (penghitung, saksi, mengetahui)."""
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    rows = [r async for r in db.transaksi_persediaan.find(
        {"jenis": "opname"}, {"_id": 0})]
    rows = [r for r in rows if str(r.get("timestamp") or "")[:10] == tanggal]
    rows.sort(key=lambda r: (r.get("nama_barang") or "", r.get("timestamp") or ""))

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("BERITA ACARA OPNAME FISIK PERSEDIAAN (BAOF)"))
    elements.append(Paragraph(
        f"Pada tanggal {_fmt_tanggal_id(tanggal)} telah dilakukan opname fisik persediaan "
        f"dengan hasil penyesuaian sebagai berikut. Selisih telah dibukukan pada jurnal "
        f"transaksi; penjelasan selisih diungkapkan pada kolom alasan (bahan CaLK).",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    if not rows:
        elements.append(Paragraph(
            "Tidak ada penyesuaian opname pada tanggal tersebut (fisik = buku untuk seluruh barang yang diopname).",
            st['Cell']))
    else:
        headers = ["No", "Kode Barang", "Nama Barang", "Buku", "Fisik", "Selisih", "Alasan"]
        table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for i, r in enumerate(rows, start=1):
            selisih = int(r.get("stok_sesudah", 0)) - int(r.get("stok_sebelum", 0))
            table_data.append([
                Paragraph(str(i), st['CellCenter']),
                Paragraph(r.get("kode_barang") or "-", st['Cell']),
                Paragraph(r.get("nama_barang") or "-", st['Cell']),
                Paragraph(str(r.get("stok_sebelum", 0)), st['CellCenter']),
                Paragraph(str(r.get("stok_sesudah", 0)), st['CellCenter']),
                Paragraph(f"{'+' if selisih > 0 else ''}{selisih}", st['CellCenter']),
                Paragraph(r.get("keterangan") or "-", st['Cell']),
            ])
        table = Table(table_data, colWidths=_fit_col_widths([28, 105, 140, 42, 42, 48, 110], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Penghitung,', 'nama': '...........................', 'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Saksi,', 'nama': '...........................', 'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Mengetahui,', 'role': 'Kuasa Pengguna Barang,', 'nama': settings.get("kasatker_nama") or '...........................', 'after': [f"NIP. {settings.get('kasatker_nip') or '....................'}"]},
    ], doc.width))
    footer = _page_footer_factory("Berita Acara Opname Fisik Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BAOF_{tanggal}.pdf"'})


@persediaan_router.get("/persediaan/laporan/posisi-pdf")
async def laporan_posisi_pdf(_user: dict = Depends(require_user)):
    """Laporan Posisi Persediaan (hari ini) — per KELOMPOK kodefikasi.

    Grup per prefix 5 digit (uraian dari referensi kodefikasi); nilai per
    barang dihitung dari layer FIFO (pustaka §3.4). Semua data nyata.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    uraian_kelompok = {}
    async for k in db.kodefikasi.find({"level": 3}, {"_id": 0, "kode": 1, "uraian": 1}):
        uraian_kelompok[k["kode"]] = k.get("uraian") or ""

    grup = {}
    async for it in db.persediaan.find({}, {"_id": 0}):
        stok = int(it.get("stok", 0) or 0)
        nilai = nilai_persediaan_dari_batches(it.get("batches"))
        kel = str(it.get("kode_barang") or "")[:5]
        g = grup.setdefault(kel, {"kelompok": kel,
                                  "uraian": uraian_kelompok.get(kel, ""),
                                  "items": [], "stok": 0, "nilai": 0.0})
        g["items"].append({"kode": it.get("kode_barang"), "nup": it.get("nup"),
                           "nama": it.get("nama_barang"), "satuan": it.get("satuan") or "-",
                           "stok": stok, "nilai": nilai})
        g["stok"] += stok
        g["nilai"] += nilai

    today_iso = datetime.now(timezone.utc).date().isoformat()
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN POSISI PERSEDIAAN"))
    elements.append(Paragraph(f"Per tanggal: {_fmt_tanggal_id(today_iso)} · nilai dihitung FIFO per layer", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Kode Barang", "NUP", "Nama Barang", "Satuan", "Stok", "Nilai (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    grand_stok, grand_nilai = 0, 0.0
    for kel in sorted(grup):
        g = grup[kel]
        label = f"Kelompok {kel}" + (f" — {g['uraian']}" if g["uraian"] else "")
        table_data.append([Paragraph(f"<b>{label}</b>", st['Cell']), "", "", "", "", ""])
        for it in sorted(g["items"], key=lambda x: (x["nama"] or "", x["kode"] or "")):
            table_data.append([
                Paragraph(it["kode"] or "-", st['Cell']),
                Paragraph(it["nup"] or "-", st['CellCenter']),
                Paragraph(it["nama"] or "-", st['Cell']),
                Paragraph(it["satuan"], st['CellCenter']),
                Paragraph(str(it["stok"]), st['CellCenter']),
                Paragraph(_fmt_rp(it["nilai"]), st['CellRight']),
            ])
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("", st['Cell']),
            Paragraph(f"<b>Subtotal {kel}</b>", st['Cell']), Paragraph("", st['Cell']),
            Paragraph(f"<b>{g['stok']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(g['nilai'])}</b>", st['CellRight']),
        ])
        grand_stok += g["stok"]
        grand_nilai += g["nilai"]
    table_data.append([
        Paragraph("", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("<b>TOTAL</b>", st['Cell']), Paragraph("", st['Cell']),
        Paragraph(f"<b>{grand_stok}</b>", st['CellCenter']),
        Paragraph(f"<b>{_fmt_rp(grand_nilai)}</b>", st['CellRight']),
    ])
    table = Table(table_data, colWidths=_fit_col_widths([120, 40, 180, 55, 45, 90], doc.width), repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("Laporan Posisi Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="Laporan_Posisi_Persediaan.pdf"'})


@persediaan_router.get("/persediaan/laporan/mutasi-pdf")
async def laporan_mutasi_pdf(
    dari: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sampai: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Laporan Mutasi Persediaan per periode — dari JURNAL (pustaka §3.4).

    Kolom: saldo awal → masuk (qty & nilai) → keluar (qty & nilai) →
    saldo akhir per barang. Saldo dihitung murni dari jurnal transaksi.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    if sampai < dari:
        raise HTTPException(status_code=400, detail="Tanggal akhir sebelum tanggal awal")

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    rows = [r async for r in db.transaksi_persediaan.find({}, {"_id": 0})]
    rekap = mutasi_periode(rows, dari, sampai)

    buffer = BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN MUTASI PERSEDIAAN"))
    elements.append(Paragraph(
        f"Periode: {_fmt_tanggal_id(dari)} s.d. {_fmt_tanggal_id(sampai)} · dihitung dari jurnal transaksi",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Kode Barang", "Nama Barang", "Saldo\nAwal", "Masuk\nQty", "Masuk\nNilai (Rp)",
               "Keluar\nQty", "Keluar\nNilai (Rp)", "Saldo\nAkhir"]
    table_data = [[Paragraph(h.replace("\n", "<br/>"), st['TableHeader']) for h in headers]]
    urut = sorted(rekap.values(), key=lambda e: (e["nama_barang"] or "", e["kode_barang"] or ""))
    tot = {"masuk_qty": 0, "masuk_nilai": 0.0, "keluar_qty": 0, "keluar_nilai": 0.0}
    for e in urut:
        table_data.append([
            Paragraph(e["kode_barang"] or "-", st['Cell']),
            Paragraph(e["nama_barang"] or "-", st['Cell']),
            Paragraph(str(e["saldo_awal"]), st['CellCenter']),
            Paragraph(str(e["masuk_qty"]), st['CellCenter']),
            Paragraph(_fmt_rp(e["masuk_nilai"]), st['CellRight']),
            Paragraph(str(e["keluar_qty"]), st['CellCenter']),
            Paragraph(_fmt_rp(e["keluar_nilai"]), st['CellRight']),
            Paragraph(str(e["saldo_akhir"]), st['CellCenter']),
        ])
        for k in tot:
            tot[k] += e[k]
    if not urut:
        elements.append(Paragraph("Tidak ada transaksi pada periode ini.", st['Cell']))
    else:
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("<b>TOTAL</b>", st['Cell']),
            Paragraph("", st['CellCenter']),
            Paragraph(f"<b>{tot['masuk_qty']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(tot['masuk_nilai'])}</b>", st['CellRight']),
            Paragraph(f"<b>{tot['keluar_qty']}</b>", st['CellCenter']),
            Paragraph(f"<b>{_fmt_rp(tot['keluar_nilai'])}</b>", st['CellRight']),
            Paragraph("", st['CellCenter']),
        ])
        table = Table(table_data, colWidths=_fit_col_widths([115, 190, 50, 50, 90, 50, 90, 50], doc.width), repeatRows=1)
        table.setStyle(_std_table_style(zebra=True, total_row=True))
        elements.append(table)

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("Laporan Mutasi Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="Laporan_Mutasi_Persediaan_{dari}_{sampai}.pdf"'})


@persediaan_router.get("/persediaan/jenis-transaksi")
async def list_jenis_transaksi(_user: dict = Depends(require_user)):
    """Jenis transaksi masuk & keluar (peta 1:1 ke SAKTI) untuk dropdown."""
    return {
        "masuk": [{"key": k, "label": v[0], "kode": v[1]} for k, v in JENIS_MASUK.items()],
        "keluar": [{"key": k, "label": v[0], "kode": v[1]} for k, v in JENIS_KELUAR.items()],
    }


class ItemMassalIn(BaseModel):
    persediaan_id: str = Field(min_length=1)
    jumlah: int = Field(gt=0)
    harga_satuan: float = Field(0, ge=0)   # dipakai arah masuk
    expired: str = ""                       # dipakai arah masuk (opsional)


class TransaksiMassalIn(BaseModel):
    arah: str                               # "masuk" | "keluar"
    jenis: str
    no_bukti: str = ""
    jenis_dokumen: str = ""                 # masuk
    tgl_dokumen: str = ""                   # masuk
    penyedia: str = ""                      # masuk
    unit_penerima: str = ""                 # keluar
    keterangan: str = ""
    items: list[ItemMassalIn] = Field(min_length=1, max_length=100)


@persediaan_router.post("/persediaan/transaksi-massal")
async def transaksi_massal(payload: TransaksiMassalIn, user: dict = Depends(require_user)):
    """Satu dokumen (BAST/kuitansi/nota) untuk BANYAK barang sekaligus.

    Tiap barang diproses lewat jalur transaksi tunggal yang sudah atomik +
    berjurnal + berkompensasi — massal hanyalah pengulang dengan field
    dokumen yang sama. Kegagalan per barang TIDAK membatalkan barang lain
    (Mongo standalone tanpa transaksi multi-dokumen); hasil per barang
    dilaporkan apa adanya agar operator tahu persis mana yang gagal.
    """
    if payload.arah not in ("masuk", "keluar"):
        raise HTTPException(status_code=400, detail="Arah harus 'masuk' atau 'keluar'")
    peta_jenis = JENIS_MASUK if payload.arah == "masuk" else JENIS_KELUAR
    if payload.jenis not in peta_jenis:
        valid = ", ".join(peta_jenis)
        raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal (pilihan: {valid})")

    hasil = []
    for it in payload.items:
        try:
            if payload.arah == "masuk":
                r = await transaksi_masuk(it.persediaan_id, TransaksiMasukIn(
                    jenis=payload.jenis, jumlah=it.jumlah,
                    harga_satuan=it.harga_satuan, expired=it.expired,
                    no_bukti=payload.no_bukti, jenis_dokumen=payload.jenis_dokumen,
                    tgl_dokumen=payload.tgl_dokumen, penyedia=payload.penyedia,
                    keterangan=payload.keterangan,
                ), user=user)
            else:
                r = await transaksi_keluar(it.persediaan_id, TransaksiKeluarIn(
                    jenis=payload.jenis, jumlah=it.jumlah,
                    unit_penerima=payload.unit_penerima,
                    no_bukti=payload.no_bukti, keterangan=payload.keterangan,
                ), user=user)
            hasil.append({"persediaan_id": it.persediaan_id, "ok": True,
                          "stok": r.get("stok"), "message": r.get("message")})
        except HTTPException as e:
            hasil.append({"persediaan_id": it.persediaan_id, "ok": False,
                          "error": str(e.detail)})
    sukses = sum(1 for h in hasil if h["ok"])
    return {"total": len(hasil), "sukses": sukses, "gagal": len(hasil) - sukses,
            "hasil": hasil}


@persediaan_router.get("/persediaan")
async def list_persediaan(
    search: str = "",
    status: str = Query("", pattern="^(|aman|kritis|habis)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _user: dict = Depends(require_user),
):
    """Daftar master persediaan: cari kode/nama/merk, filter status stok."""
    query = {}
    if search:
        s = search.strip()
        query["$or"] = [
            {"kode_barang": {"$regex": f"^{s}" if s.isdigit() else s, "$options": "i"}},
            {"nama_barang": {"$regex": s, "$options": "i"}},
            {"merk": {"$regex": s, "$options": "i"}},
        ]
    # Filter status stok dihitung DI QUERY (bukan pasca-paging) agar total &
    # halaman benar: habis = stok<=0; kritis = 0<stok<=batas (batas>0).
    if status == "habis":
        query["stok"] = {"$lte": 0}
    elif status == "kritis":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$gt": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
            {"$lte": ["$stok", "$batas_kritis"]},
        ]}
    elif status == "aman":
        query["$expr"] = {"$and": [
            {"$gt": ["$stok", 0]},
            {"$or": [
                {"$lte": [{"$ifNull": ["$batas_kritis", 0]}, 0]},
                {"$gt": ["$stok", "$batas_kritis"]},
            ]},
        ]}
    total = await db.persediaan.count_documents(query)
    cursor = (db.persediaan.find(query, {"_id": 0, "batches": 0})
              .sort([("nama_barang", 1), ("kode_barang", 1)])
              .skip((page - 1) * page_size).limit(page_size))
    items = [_doc(x) async for x in cursor]
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
    }


@persediaan_router.get("/persediaan/{item_id}")
async def get_persediaan(item_id: str, _user: dict = Depends(require_user)):
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    out = _doc(item)
    out["batches"] = item.get("batches") or []  # detail menampilkan layer FIFO
    return out


@persediaan_router.post("/persediaan")
async def create_persediaan(data: PersediaanCreate, _user: dict = Depends(require_user)):
    kode = str(data.kode_barang or "").strip()
    ok, err = validate_kode_persediaan(kode)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    # Kode 10 digit → lengkapi 6 digit nomor urut otomatis (increment
    # dari kode terbesar se-prefix; numerik karena panjang seragam).
    if len(kode) == KODE_PREFIX_LEN:
        max_doc = await db.persediaan.find_one(
            {"kode_barang": {"$regex": f"^{kode}"}},
            {"_id": 0, "kode_barang": 1}, sort=[("kode_barang", -1)])
        try:
            kode = next_kode_penuh(kode, (max_doc or {}).get("kode_barang"))
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    # NUP otomatis bila kosong: increment NUP terbesar pada kode sama.
    nup = str(data.nup or "").strip()
    if not nup:
        max_nup_doc = await db.persediaan.find_one(
            {"kode_barang": kode}, {"_id": 0, "nup": 1},
            sort=[("nup_num", -1)])
        nup = next_nup((max_nup_doc or {}).get("nup"))
    if await db.persediaan.find_one({"kode_barang": kode, "nup": nup}, {"_id": 1}):
        raise HTTPException(status_code=409, detail=f"Kode {kode} NUP {nup} sudah terdaftar")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "kode_barang": kode,
        "nup": nup,
        "nup_num": int(nup) if nup.isdigit() else 0,
        "nama_barang": data.nama_barang.strip(),
        "merk": data.merk.strip(),
        "tipe": data.tipe.strip(),
        "satuan": (data.satuan or "Buah").strip() or "Buah",
        "lokasi": data.lokasi.strip(),
        "batas_kritis": int(data.batas_kritis or 0),
        "expired_default": data.expired_default.strip(),
        "tahun_anggaran": data.tahun_anggaran.strip(),
        "keterangan": data.keterangan.strip(),
        "stok": 0,          # stok lahir 0 — bertambah lewat transaksi masuk
        "batches": [],      # layer FIFO {batch_id, tanggal, qty, harga, expired, ref}
        "version": 1,
        "created_at": now,
        "updated_at": now,
    }
    await db.persediaan.insert_one({**doc})
    return _doc(doc)


@persediaan_router.put("/persediaan/{item_id}")
async def update_persediaan(
    item_id: str,
    data: PersediaanUpdate,
    if_match: str = Header("", alias="If-Match"),
    _user: dict = Depends(require_user),
):
    """Ubah field non-identitas master (OCC: wajib If-Match versi terkini)."""
    # Whitelist dari registry (persediaan_fields) — field identitas/terkelola
    # sistem tak akan pernah lolos meski model berubah; test registry menjaga.
    updates = {}
    for k, v in data.model_dump(exclude_none=True).items():
        if k not in EDITABLE_FIELD_NAMES:
            continue
        updates[k] = v.strip() if isinstance(v, str) else v
    if not updates:
        raise HTTPException(status_code=400, detail="Tidak ada field yang diubah")
    if not if_match.strip().isdigit():
        raise HTTPException(status_code=428, detail="Header If-Match (versi) wajib disertakan")

    version = int(if_match.strip())
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.persediaan.find_one_and_update(
        {"id": item_id, "version": version},
        {"$set": updates, "$inc": {"version": 1}},
        projection={"_id": 0},
        return_document=True,
    )
    if res is None:
        exists = await db.persediaan.find_one({"id": item_id}, {"_id": 1})
        if not exists:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        raise HTTPException(status_code=409, detail="Versi berubah — muat ulang data lalu simpan lagi")
    return _doc(res)


class TransaksiMasukIn(BaseModel):
    jenis: str = "pembelian"
    jumlah: int = Field(gt=0)
    harga_satuan: float = Field(0, ge=0)
    expired: str = ""            # YYYY-MM-DD; kosong = pakai expired_default
    no_bukti: str = ""
    jenis_dokumen: str = ""      # BAST / Kuitansi / Kontrak / SPBy / dll.
    tgl_dokumen: str = ""
    no_kontrak: str = ""
    penyedia: str = ""
    keterangan: str = ""


@persediaan_router.post("/persediaan/{item_id}/masuk")
async def transaksi_masuk(item_id: str, data: TransaksiMasukIn, user: dict = Depends(require_user)):
    """Transaksi MASUK: layer FIFO baru + stok naik + jurnal (pustaka §3).

    Pencatatan perpetual: master diperbarui ATOMIK ($push layer + $inc stok
    + $inc version); jurnal `transaksi_persediaan` menyusul dengan
    stok_sebelum/sesudah — bila penulisan jurnal gagal, layer dikompensasi
    (dicabut lagi) supaya master tidak pernah menyimpan stok tanpa jejak.
    """
    ok, err = validate_transaksi_masuk(data.jenis, data.jumlah, data.harga_satuan)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    now = datetime.now(timezone.utc)
    batch_id = str(uuid.uuid4())
    ref = (data.no_bukti or data.no_kontrak or "").strip()

    # Ambil dulu untuk stok_sebelum + expired_default (best-effort snapshot;
    # angka resmi stok sebelum/sesudah diambil dari hasil update atomik).
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")

    expired = (data.expired or item.get("expired_default") or "").strip()
    layer = buat_layer(batch_id, now.isoformat(), data.jumlah, data.harga_satuan, expired, ref)

    updated = await db.persediaan.find_one_and_update(
        {"id": item_id},
        {"$push": {"batches": layer},
         "$inc": {"stok": int(data.jumlah), "version": 1},
         "$set": {"updated_at": now.isoformat()}},
        projection={"_id": 0},
        return_document=True,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")

    stok_sesudah = int(updated.get("stok", 0) or 0)
    jurnal = {
        "id": str(uuid.uuid4()),
        "arah": "masuk",
        "jenis": data.jenis,
        "jenis_label": JENIS_MASUK[data.jenis][0],
        "kode_sakti": JENIS_MASUK[data.jenis][1],
        "persediaan_id": item_id,
        "kode_barang": updated.get("kode_barang"),
        "nup": updated.get("nup"),
        "nama_barang": updated.get("nama_barang"),
        "batch_id": batch_id,
        "jumlah": int(data.jumlah),
        "harga_satuan": float(data.harga_satuan),
        "total": int(data.jumlah) * float(data.harga_satuan),
        "stok_sebelum": stok_sesudah - int(data.jumlah),
        "stok_sesudah": stok_sesudah,
        "expired": expired,
        "no_bukti": data.no_bukti.strip(),
        "jenis_dokumen": data.jenis_dokumen.strip(),
        "tgl_dokumen": data.tgl_dokumen.strip(),
        "no_kontrak": data.no_kontrak.strip(),
        "penyedia": data.penyedia.strip(),
        "keterangan": data.keterangan.strip(),
        "petugas": user.get("username") or user.get("user_id") or "-",
        "timestamp": now.isoformat(),
    }
    try:
        await db.transaksi_persediaan.insert_one({**jurnal})
    except Exception:
        # Kompensasi: cabut layer & stok yang barusan masuk — master tidak
        # boleh menyimpan stok tanpa jejak jurnal.
        await db.persediaan.update_one(
            {"id": item_id},
            {"$pull": {"batches": {"batch_id": batch_id}},
             "$inc": {"stok": -int(data.jumlah), "version": 1}},
        )
        raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — transaksi dibatalkan")

    return {"message": f"{JENIS_MASUK[data.jenis][0]} tercatat", "stok": stok_sesudah,
            "transaksi": jurnal, "version": updated.get("version")}


class TransaksiKeluarIn(BaseModel):
    jenis: str = "habis_pakai"
    jumlah: int = Field(gt=0)
    unit_penerima: str = ""
    no_bukti: str = ""
    keterangan: str = ""


@persediaan_router.post("/persediaan/{item_id}/keluar")
async def transaksi_keluar(item_id: str, data: TransaksiKeluarIn, user: dict = Depends(require_user)):
    """Transaksi KELUAR: konsumsi layer FIFO tertua + jurnal (pustaka §3).

    Nilai keluar = Σ (qty terpakai × harga layer) — bukan rata-rata.
    Update master BERSYARAT VERSI (retry 3x saat balapan dengan transaksi
    lain); jurnal menyertakan rincian layer terpakai. Bila tulis jurnal
    gagal → batches & stok dikembalikan ke snapshot sebelumnya.
    """
    now = datetime.now(timezone.utc)
    for _attempt in range(3):
        item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        stok_sebelum = int(item.get("stok", 0) or 0)
        ok, err = validate_transaksi_keluar(data.jenis, data.jumlah, stok_sebelum)
        if not ok:
            raise HTTPException(status_code=400, detail=err)
        batches_lama = item.get("batches") or []
        try:
            batches_sisa, total_nilai, rincian = konsumsi_fifo(batches_lama, data.jumlah)
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

        stok_sesudah = stok_sebelum - int(data.jumlah)
        updated = await db.persediaan.find_one_and_update(
            {"id": item_id, "version": item.get("version")},
            {"$set": {"batches": batches_sisa, "stok": stok_sesudah,
                      "updated_at": now.isoformat()},
             "$inc": {"version": 1}},
            projection={"_id": 0},
            return_document=True,
        )
        if updated is None:
            continue  # balapan — muat ulang lalu coba lagi

        harga_rata = (total_nilai / int(data.jumlah)) if data.jumlah else 0.0
        jurnal = {
            "id": str(uuid.uuid4()),
            "arah": "keluar",
            "jenis": data.jenis,
            "jenis_label": JENIS_KELUAR[data.jenis][0],
            "kode_sakti": JENIS_KELUAR[data.jenis][1],
            "persediaan_id": item_id,
            "kode_barang": updated.get("kode_barang"),
            "nup": updated.get("nup"),
            "nama_barang": updated.get("nama_barang"),
            "jumlah": int(data.jumlah),
            "harga_satuan": harga_rata,   # rata-rata TERTIMBANG dari layer terpakai (informasi)
            "total": total_nilai,          # nilai FIFO sesungguhnya
            "rincian_layer": rincian,
            "stok_sebelum": stok_sebelum,
            "stok_sesudah": stok_sesudah,
            "unit_penerima": data.unit_penerima.strip(),
            "no_bukti": data.no_bukti.strip(),
            "keterangan": data.keterangan.strip(),
            "petugas": user.get("username") or user.get("user_id") or "-",
            "timestamp": now.isoformat(),
        }
        try:
            await db.transaksi_persediaan.insert_one({**jurnal})
        except Exception:
            # Kompensasi: kembalikan snapshot batches & stok sebelum keluar
            await db.persediaan.update_one(
                {"id": item_id},
                {"$set": {"batches": batches_lama, "stok": stok_sebelum},
                 "$inc": {"version": 1}},
            )
            raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — transaksi dibatalkan")

        return {"message": f"{JENIS_KELUAR[data.jenis][0]} tercatat", "stok": stok_sesudah,
                "nilai_keluar": total_nilai, "transaksi": jurnal,
                "version": updated.get("version")}

    raise HTTPException(status_code=409,
                        detail="Barang sedang diubah pengguna lain — coba lagi")


class OpnameIn(BaseModel):
    stok_fisik: int = Field(ge=0)
    alasan: str = Field(min_length=3, max_length=500)


@persediaan_router.post("/persediaan/{item_id}/opname")
async def opname_persediaan(item_id: str, data: OpnameIn, user: dict = Depends(require_user)):
    """Rekam hasil opname SATU barang (pustaka §3.3 — hanya yang selisih).

    fisik < buku → kekurangan dikonsumsi FIFO; fisik > buku → layer
    penyesuaian berharga layer termuda. Saldo buku disetel = fisik +
    jurnal jenis "opname" dengan ALASAN WAJIB (bahan pengungkapan CaLK).
    Update bersyarat versi + retry 3× seperti transaksi keluar.
    """
    now = datetime.now(timezone.utc)
    for _attempt in range(3):
        item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
        stok_sebelum = int(item.get("stok", 0) or 0)
        batches_lama = item.get("batches") or []
        batch_id = str(uuid.uuid4())
        try:
            batches_baru, detail = penyesuaian_opname(
                batches_lama, data.stok_fisik, batch_id, now.isoformat())
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        updated = await db.persediaan.find_one_and_update(
            {"id": item_id, "version": item.get("version")},
            {"$set": {"batches": batches_baru, "stok": int(data.stok_fisik),
                      "updated_at": now.isoformat()},
             "$inc": {"version": 1}},
            projection={"_id": 0},
            return_document=True,
        )
        if updated is None:
            continue  # balapan — muat ulang lalu coba lagi

        jurnal = {
            "id": str(uuid.uuid4()),
            "arah": detail["arah"],
            "jenis": "opname",
            "jenis_label": "Penyesuaian Opname Fisik",
            "kode_sakti": "OPN",
            "persediaan_id": item_id,
            "kode_barang": updated.get("kode_barang"),
            "nup": updated.get("nup"),
            "nama_barang": updated.get("nama_barang"),
            "jumlah": int(detail["jumlah"]),
            "harga_satuan": (detail["nilai"] / detail["jumlah"]) if detail["jumlah"] else 0.0,
            "total": float(detail["nilai"]),
            "rincian_layer": detail.get("rincian", []),
            "stok_sebelum": stok_sebelum,
            "stok_sesudah": int(data.stok_fisik),
            "keterangan": data.alasan.strip(),
            "petugas": user.get("username") or user.get("user_id") or "-",
            "timestamp": now.isoformat(),
        }
        try:
            await db.transaksi_persediaan.insert_one({**jurnal})
        except Exception:
            await db.persediaan.update_one(
                {"id": item_id},
                {"$set": {"batches": batches_lama, "stok": stok_sebelum},
                 "$inc": {"version": 1}},
            )
            raise HTTPException(status_code=500, detail="Gagal mencatat jurnal — opname dibatalkan")

        selisih = int(data.stok_fisik) - stok_sebelum
        return {"message": f"Opname tercatat (selisih {'+' if selisih > 0 else ''}{selisih})",
                "stok": int(data.stok_fisik), "transaksi": jurnal,
                "version": updated.get("version")}

    raise HTTPException(status_code=409,
                        detail="Barang sedang diubah pengguna lain — coba lagi")


@persediaan_router.get("/persediaan/{item_id}/riwayat")
async def riwayat_persediaan(
    item_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _user: dict = Depends(require_user),
):
    """Jurnal transaksi sebuah barang, terbaru dulu."""
    query = {"persediaan_id": item_id}
    total = await db.transaksi_persediaan.count_documents(query)
    cursor = (db.transaksi_persediaan.find(query, {"_id": 0})
              .sort("timestamp", -1).skip((page - 1) * page_size).limit(page_size))
    items = [x async for x in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, -(-total // page_size))}


@persediaan_router.get("/persediaan/{item_id}/kartu-barang-pdf")
async def kartu_barang_pdf(item_id: str, _user: dict = Depends(require_user)):
    """Kartu Barang Persediaan — riwayat kronologis + saldo berjalan.

    Form kendali standar penatausahaan persediaan (analog kartu barang
    manual bahan ajar DJKN): identitas barang + seluruh jurnal transaksi
    terurut waktu dengan kolom masuk/keluar/sisa dan nilai. Barang tanpa
    transaksi = 404 (tanpa data dummy).
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )

    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    rows = [r async for r in db.transaksi_persediaan
            .find({"persediaan_id": item_id}, {"_id": 0}).sort("timestamp", 1)]
    if not rows:
        raise HTTPException(status_code=404,
                            detail="Belum ada transaksi untuk barang ini")

    label_jenis = {k: v[0] for k, v in JENIS_MASUK.items()}
    label_jenis.update({k: v[0] for k, v in JENIS_KELUAR.items()})
    label_jenis["opname"] = "Penyesuaian Opname"

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("KARTU BARANG PERSEDIAAN"))
    elements.append(Paragraph(
        f"{item.get('nama_barang') or '-'} · Kode {item.get('kode_barang') or '-'} · "
        f"NUP {item.get('nup') or '-'} · Satuan {item.get('satuan') or '-'}"
        + (f" · Lokasi {item.get('lokasi')}" if item.get("lokasi") else "")
        + f" · Stok kini {int(item.get('stok', 0) or 0)}", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["Tanggal", "Uraian", "No. Bukti", "Masuk", "Keluar", "Sisa", "Nilai (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for r in rows:
        arah = r.get("arah")
        jumlah = int(r.get("jumlah", 0) or 0)
        uraian = label_jenis.get(r.get("jenis"), r.get("jenis") or "-")
        if r.get("keterangan"):
            uraian += f" — {r['keterangan']}"
        table_data.append([
            Paragraph(_fmt_tanggal_id(str(r.get("timestamp") or "")[:10]), st['CellCenter']),
            Paragraph(uraian, st['Cell']),
            Paragraph(r.get("no_bukti") or "-", st['Cell']),
            Paragraph(str(jumlah) if arah == "masuk" else "", st['CellCenter']),
            Paragraph(str(jumlah) if arah == "keluar" else "", st['CellCenter']),
            Paragraph(str(int(r.get("stok_sesudah", 0) or 0)), st['CellCenter']),
            Paragraph(_fmt_rp(r.get("total")), st['CellRight']),
        ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([62, 160, 80, 40, 40, 40, 80], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True))
    elements.append(table)
    elements.append(Spacer(1, 3 * rl_mm))
    elements.append(Paragraph(
        "Catatan: kolom Sisa = stok setelah transaksi (saldo berjalan dari jurnal); "
        "nilai keluar dihitung FIFO per layer.", st['Meta']))

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Pengurus Barang Persediaan,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("Kartu Barang Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    nama_file = (item.get("kode_barang") or item_id)[:20]
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="Kartu_Barang_{nama_file}.pdf"'})


@persediaan_router.delete("/persediaan/{item_id}")
async def delete_persediaan(item_id: str, _admin: dict = Depends(require_admin)):
    """Hapus master — hanya bila stok 0 & tanpa layer (jejak transaksi aman)."""
    item = await db.persediaan.find_one({"id": item_id}, {"_id": 0, "stok": 1, "batches": 1})
    if not item:
        raise HTTPException(status_code=404, detail="Barang persediaan tidak ditemukan")
    if int(item.get("stok", 0) or 0) > 0 or (item.get("batches") or []):
        raise HTTPException(status_code=409,
                            detail="Barang masih punya stok/layer — keluarkan stoknya dulu lewat transaksi")
    await db.persediaan.delete_one({"id": item_id})
    return {"message": "Barang persediaan dihapus"}
