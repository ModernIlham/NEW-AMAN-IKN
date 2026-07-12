"""PEMELIHARAAN — Fase 3 tahap awal: catatan riwayat + biaya per aset.

PP 27/2014 Ps. 46-47: catatan per kejadian pemeliharaan menjadi bahan
Daftar Hasil Pemeliharaan Barang (DHPB) + rekap biaya per tahun anggaran.
Jadwal pemeliharaan berkala & DHPB PDF menyusul sesuai masterplan Fase 3.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemeliharaan_utils import (
    JENIS_PEMELIHARAAN, indikasi_kapitalisasi, kelompok_dhpb,
    rekap_pemeliharaan, rentang_periode, urut_riwayat, parse_biaya,
    validate_pemeliharaan,
)

pemeliharaan_router = APIRouter()

_PROJ = {"_id": 0}
# Field ringkas untuk rekap (hemat: tanpa uraian/keterangan panjang).
_PROJ_REKAP = {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
               "asset_name": 1, "tanggal": 1, "jenis": 1, "biaya": 1}


class PemeliharaanIn(BaseModel):
    asset_id: str = Field(min_length=1)
    tanggal: str
    jenis: str
    uraian: str
    biaya: float | str | None = None
    pelaksana: str = ""          # petugas internal / penyedia jasa
    no_bukti: str = ""           # nomor SPM / kuitansi / BAST pekerjaan
    kondisi_setelah: str = ""    # opsional: perbarui kondisi aset
    keterangan: str = ""


# PENTING: rute literal (/rekap, /jenis, /aset/...) HARUS di atas rute
# berparameter agar tidak tertelan {catatan_id} (lihat SKILL.md).

@pemeliharaan_router.get("/pemeliharaan/jenis")
async def daftar_jenis(_user: dict = Depends(require_user)):
    """Daftar jenis pemeliharaan untuk pilihan form."""
    return {"items": [{"key": k, "label": v} for k, v in JENIS_PEMELIHARAAN.items()]}


@pemeliharaan_router.get("/pemeliharaan/rekap")
async def rekap(
    tahun: int = Query(None, description="Saring rekap ke satu tahun anggaran"),
    _user: dict = Depends(require_user),
):
    """Rekap biaya pemeliharaan: total, per jenis, per tahun, per aset."""
    records = [r async for r in db.pemeliharaan.find({}, _PROJ_REKAP)]
    hasil = rekap_pemeliharaan(records, tahun=tahun)
    hasil["jumlah_aset"] = len(hasil["per_aset"])
    hasil["per_aset"] = hasil["per_aset"][:50]
    hasil["label_jenis"] = JENIS_PEMELIHARAAN
    hasil["tahun"] = tahun
    return hasil


def _fmt_rp(val):
    try:
        return f"{int(val):,}".replace(",", ".")
    except (ValueError, TypeError, OverflowError):
        return "0"


@pemeliharaan_router.get("/pemeliharaan/dhpb-pdf")
async def dhpb_pdf(
    tahun: int = Query(..., ge=2000, le=2100),
    semester: int = Query(None, ge=1, le=2),
    _user: dict = Depends(require_user),
):
    """DHPB — Daftar Hasil Pemeliharaan Barang per periode (Ps. 47 PP 27/2014).

    Laporan berkala KPB → Pengguna Barang: catatan pemeliharaan periode
    terpilih (tahun penuh / semester) dikelompokkan per aset + subtotal
    dan total biaya. Hanya data nyata — periode kosong = 404.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )

    dari, sampai, label_periode = rentang_periode(tahun, semester)
    records = [r async for r in db.pemeliharaan.find(
        {"tanggal": {"$gte": dari, "$lte": sampai}}, _PROJ)]
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"Tidak ada catatan pemeliharaan pada {label_periode}")
    grup, total_biaya = kelompok_dhpb(records)
    ada_kapitalisasi = any(r.get("indikasi_kapitalisasi") for r in records)

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    buffer = BytesIO()
    doc = _std_doc(buffer, landscape_mode=True)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("DAFTAR HASIL PEMELIHARAAN BARANG (DHPB)",
                                 subjudul=label_periode))
    elements.append(Paragraph(
        f"Periode {_fmt_tanggal_id(dari)} s.d. {_fmt_tanggal_id(sampai)} · "
        f"{len(records)} catatan pada {len(grup)} aset · laporan berkala "
        "Kuasa Pengguna Barang (Pasal 47 PP 27/2014)", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Tanggal", "Jenis", "Uraian Pekerjaan", "Pelaksana",
               "No. Bukti", "Kondisi Akhir", "Biaya (Rp)"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    baris_aset = []  # indeks baris judul aset → SPAN selebar tabel
    no = 0
    for g in grup:
        label_aset = (f"{g['asset_name'] or '-'} "
                      f"({g['asset_code'] or '-'} · NUP {g['NUP'] or '-'})")
        baris_aset.append(len(table_data))
        table_data.append([Paragraph(f"<b>{label_aset}</b>", st['Cell']),
                           "", "", "", "", "", "", ""])
        for r in g["items"]:
            no += 1
            tanda = " *" if r.get("indikasi_kapitalisasi") else ""
            table_data.append([
                Paragraph(str(no), st['CellCenter']),
                Paragraph(_fmt_tanggal_id(r.get("tanggal")), st['CellCenter']),
                Paragraph((r.get("jenis") or "-").capitalize(), st['CellCenter']),
                Paragraph((r.get("uraian") or "-"), st['Cell']),
                Paragraph(r.get("pelaksana") or "-", st['Cell']),
                Paragraph(r.get("no_bukti") or "-", st['Cell']),
                Paragraph(r.get("kondisi_setelah") or "-", st['CellCenter']),
                Paragraph(f"{_fmt_rp(r.get('biaya'))}{tanda}", st['CellRight']),
            ])
        table_data.append([
            Paragraph("", st['Cell']), Paragraph("", st['Cell']),
            Paragraph("", st['Cell']),
            Paragraph(f"<b>Subtotal — {len(g['items'])} catatan</b>", st['Cell']),
            Paragraph("", st['Cell']), Paragraph("", st['Cell']),
            Paragraph("", st['Cell']),
            Paragraph(f"<b>{_fmt_rp(g['subtotal'])}</b>", st['CellRight']),
        ])
    table_data.append([
        Paragraph("", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph("<b>TOTAL BIAYA PEMELIHARAAN</b>", st['Cell']),
        Paragraph("", st['Cell']), Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph(f"<b>{_fmt_rp(total_biaya)}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([25, 62, 52, 200, 90, 80, 62, 80], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(
        zebra=True, total_row=True,
        extra=[("SPAN", (0, i), (-1, i)) for i in baris_aset]))
    elements.append(table)
    if ada_kapitalisasi:
        elements.append(Spacer(1, 2 * rl_mm))
        elements.append(Paragraph(
            "*) Biaya mencapai nilai satuan minimum kapitalisasi "
            "PMK 181/PMK.06/2016 — telaah apakah menambah masa "
            "manfaat/kapasitas (belanja modal / pengembangan nilai aset).",
            st['Meta']))

    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': ['.................., .......................'],
         'header': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or "-",
         'after': [f"NIP. {settings.get('kasatker_nip') or '-'}"]},
    ], doc.width))
    footer = _page_footer_factory("DHPB")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    suffix = f"_S{semester}" if semester else ""
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="DHPB_{tahun}{suffix}.pdf"'})


@pemeliharaan_router.get("/pemeliharaan/aset/{asset_id}")
async def riwayat_aset(asset_id: str, _user: dict = Depends(require_user)):
    """Riwayat pemeliharaan satu aset (terbaru dulu) + subtotal biaya."""
    records = [r async for r in db.pemeliharaan.find({"asset_id": asset_id}, _PROJ)]
    records = urut_riwayat(records)
    total = sum(parse_biaya(r.get("biaya")) or 0.0 for r in records)
    return {"items": records, "jumlah": len(records), "total_biaya": total}


@pemeliharaan_router.get("/pemeliharaan")
async def list_pemeliharaan(
    asset_id: str = "",
    tahun: int = Query(None),
    jenis: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _user: dict = Depends(require_user),
):
    """Daftar catatan pemeliharaan (terbaru dulu), saring aset/tahun/jenis."""
    query = {}
    if asset_id:
        query["asset_id"] = asset_id
    if jenis:
        if jenis not in JENIS_PEMELIHARAAN:
            valid = ", ".join(JENIS_PEMELIHARAAN)
            raise HTTPException(status_code=400, detail=f"Jenis tidak dikenal (pilihan: {valid})")
        query["jenis"] = jenis
    if tahun:
        # tanggal tersimpan sebagai string ISO → rentang leksikografis aman
        query["tanggal"] = {"$gte": f"{tahun}-01-01", "$lte": f"{tahun}-12-31"}
    total = await db.pemeliharaan.count_documents(query)
    skip = (page - 1) * page_size
    cursor = (db.pemeliharaan.find(query, _PROJ)
              .sort([("tanggal", -1), ("created_at", -1)])
              .skip(skip).limit(page_size))
    items = [r async for r in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "total_pages": max(1, -(-total // page_size)),
            "label_jenis": JENIS_PEMELIHARAAN}


@pemeliharaan_router.post("/pemeliharaan")
async def create_pemeliharaan(payload: PemeliharaanIn, user: dict = Depends(require_user)):
    """Catat satu kejadian pemeliharaan; opsional perbarui kondisi aset."""
    data = payload.model_dump()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    errors = validate_pemeliharaan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "condition": 1},
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    biaya = parse_biaya(data.get("biaya")) or 0.0
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        # Snapshot identitas agar riwayat tetap terbaca bila aset berubah
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "tanggal": str(data["tanggal"]).strip()[:10],
        "jenis": data["jenis"],
        "uraian": str(data["uraian"]).strip(),
        "biaya": biaya,
        # Kondisi B/RR/RB sebelum-sesudah — jejak yang dicari auditor
        "kondisi_sebelum": str(asset.get("condition") or "").strip(),
        # Penanda telaah PMK 181/2016 (≥ ambang kapitalisasi golongan)
        "indikasi_kapitalisasi": indikasi_kapitalisasi(
            biaya, asset.get("asset_code")),
        "pelaksana": str(data.get("pelaksana") or "").strip(),
        "no_bukti": str(data.get("no_bukti") or "").strip(),
        "kondisi_setelah": str(data.get("kondisi_setelah") or "").strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemeliharaan.insert_one({**record})
    # Integrasi masterplan: kondisi aset ter-update dari hasil pemeliharaan.
    if record["kondisi_setelah"]:
        await db.assets.update_one(
            {"id": asset["id"]},
            {"$set": {"condition": record["kondisi_setelah"], "updated_at": now},
             "$inc": {"version": 1}},
        )
    return record


@pemeliharaan_router.delete("/pemeliharaan/{catatan_id}")
async def delete_pemeliharaan(catatan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus catatan pemeliharaan (khusus admin, mis. salah input)."""
    res = await db.pemeliharaan.delete_one({"id": catatan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan")
    return {"ok": True, "id": catatan_id}
