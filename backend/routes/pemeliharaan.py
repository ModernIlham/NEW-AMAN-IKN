"""PEMELIHARAAN — Fase 3 tahap awal: catatan riwayat + biaya per aset.

PP 27/2014 Ps. 46-47: catatan per kejadian pemeliharaan menjadi bahan
Daftar Hasil Pemeliharaan Barang (DHPB, tersedia sebagai PDF) + rekap
biaya per tahun anggaran; jadwal pemeliharaan berkala dikelola di sini.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user, require_writer
from db import db
from shared_utils import blok_ttd_kpb, kode_satker_user
from pemeliharaan_utils import (
    JENIS_PEMELIHARAAN, baris_csv_jadwal, indikasi_kapitalisasi, jatuh_tempo,
    kelompok_dhpb, rekap_pemeliharaan, rentang_periode, status_jadwal,
    parse_biaya, validate_jadwal, validate_pemeliharaan,
)

pemeliharaan_router = APIRouter()

_PROJ = {"_id": 0}
# Field ringkas untuk rekap (hemat: tanpa uraian/keterangan panjang).
_PROJ_REKAP = {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
               "asset_name": 1, "tanggal": 1, "jenis": 1, "biaya": 1}


class JadwalIn(BaseModel):
    asset_id: str = Field(min_length=1)
    interval_bulan: int
    mulai: str
    keterangan: str = ""     # uraian pekerjaan berkala (mis. "servis AC")


class JadwalUpdate(BaseModel):
    interval_bulan: int
    mulai: str
    keterangan: str = ""


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


class KapitalisasiIn(BaseModel):
    """Data Berita Acara serah terima pekerjaan perbaikan (KMK 295/2019
    Diktum KEENAM: pengakuan tambahan masa manfaat dilakukan saat penyerahan
    pekerjaan melalui Berita Acara Serah Terima). Nomor kosong → otomatis."""
    nomor_ba: str = ""
    tanggal_serah_terima: str = ""     # default = hari ini
    pihak_pelaksana: str = ""          # penyedia jasa / pelaksana pekerjaan
    jabatan_pelaksana: str = ""
    pihak_penerima: str = ""           # pejabat penerima hasil pekerjaan
    jabatan_penerima: str = ""
    terapkan_masa_manfaat: bool = True  # matikan bila perbaikan TIDAK menambah umur


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
    from xml.sax.saxutils import escape as _esc
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    baris_aset = []  # indeks baris judul aset → SPAN selebar tabel
    no = 0
    for g in grup:
        label_aset = (f"{g['asset_name'] or '-'} "
                      f"({g['asset_code'] or '-'} · NUP {g['NUP'] or '-'})")
        baris_aset.append(len(table_data))
        table_data.append([Paragraph(f"<b>{_esc(label_aset)}</b>", st['Cell']),
                           "", "", "", "", "", "", ""])
        for r in g["items"]:
            no += 1
            tanda = " *" if r.get("indikasi_kapitalisasi") else ""
            table_data.append([
                Paragraph(str(no), st['CellCenter']),
                Paragraph(_fmt_tanggal_id(r.get("tanggal")), st['CellCenter']),
                Paragraph((r.get("jenis") or "-").capitalize(), st['CellCenter']),
                Paragraph(_esc(r.get("uraian") or "-"), st['Cell']),
                Paragraph(_esc(r.get("pelaksana") or "-"), st['Cell']),
                Paragraph(_esc(r.get("no_bukti") or "-"), st['Cell']),
                Paragraph(_esc(r.get("kondisi_setelah") or "-"), st['CellCenter']),
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
        # KPB dari registry pejabat ter-scope satker penerbit (temuan #26)
        await blok_ttd_kpb(settings, kode_satker=kode_satker_user(_user)),
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


@pemeliharaan_router.get("/pemeliharaan/jadwal")
async def list_jadwal(_user: dict = Depends(require_user)):
    """Jadwal berkala semua aset + jatuh tempo & status, terlambat dulu.

    Pedoman DKPB Ps. 46(2) PP 27/2014: pemeliharaan berpedoman pada daftar
    kebutuhan pemeliharaan — jadwal ini bentuk operasionalnya di satker.
    """
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = []
    async for j in db.jadwal_pemeliharaan.find({}, _PROJ):
        due = jatuh_tempo(j)
        j["jatuh_tempo"] = due
        j["status"] = status_jadwal(due, today_iso)
        items.append(j)
    items.sort(key=lambda x: (x["jatuh_tempo"] or "9999", x.get("asset_name") or ""))
    return {
        "items": items,
        "jumlah": len(items),
        "terlambat": sum(1 for i in items if i["status"] == "terlambat"),
        "segera": sum(1 for i in items if i["status"] == "segera"),
    }


@pemeliharaan_router.get("/pemeliharaan/jadwal/export")
async def export_jadwal(_user: dict = Depends(require_user)):
    """Ekspor CSV jadwal pemeliharaan berkala (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [j async for j in db.jadwal_pemeliharaan.find({}, _PROJ)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_jadwal(items, today_iso):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="jadwal_pemeliharaan.csv"'})


@pemeliharaan_router.post("/pemeliharaan/jadwal")
async def create_jadwal(payload: JadwalIn, user: dict = Depends(require_writer)):
    """Buat jadwal pemeliharaan berkala untuk satu aset."""
    data = payload.model_dump()
    errors = validate_jadwal(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1},
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "interval_bulan": int(data["interval_bulan"]),
        "mulai": str(data["mulai"]).strip()[:10],
        "terakhir": "",   # terisi otomatis saat pemeliharaan dicatat
        "keterangan": str(data.get("keterangan") or "").strip(),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.jadwal_pemeliharaan.insert_one({**record})
    return record


@pemeliharaan_router.put("/pemeliharaan/jadwal/{jadwal_id}")
async def update_jadwal(jadwal_id: str, payload: JadwalUpdate,
                        _user: dict = Depends(require_writer)):
    """Ubah interval/mulai/keterangan sebuah jadwal berkala."""
    data = payload.model_dump()
    errors = validate_jadwal(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    res = await db.jadwal_pemeliharaan.find_one_and_update(
        {"id": jadwal_id},
        {"$set": {"interval_bulan": int(data["interval_bulan"]),
                  "mulai": str(data["mulai"]).strip()[:10],
                  "keterangan": str(data.get("keterangan") or "").strip(),
                  "updated_at": datetime.now(timezone.utc).isoformat()}},
        projection=_PROJ, return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    return res


@pemeliharaan_router.delete("/pemeliharaan/jadwal/{jadwal_id}")
async def delete_jadwal(jadwal_id: str, _admin: dict = Depends(require_admin)):
    """Hapus jadwal berkala (khusus admin)."""
    res = await db.jadwal_pemeliharaan.delete_one({"id": jadwal_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan")
    return {"ok": True, "id": jadwal_id}


@pemeliharaan_router.get("/pemeliharaan/export")
async def export_pemeliharaan(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh riwayat pemeliharaan (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["kode_aset", "nup", "nama_aset", "tanggal", "jenis",
                "uraian", "biaya", "kondisi_sebelum", "kondisi_setelah",
                "telaah_kapitalisasi", "pelaksana", "no_bukti",
                "keterangan", "dibuat_oleh"])
    async for c in db.pemeliharaan.find({}, {"_id": 0}) \
            .sort([("tanggal", -1), ("created_at", -1)]):
        w.writerow([
            c.get("asset_code"), c.get("NUP"), c.get("asset_name"),
            c.get("tanggal"),
            JENIS_PEMELIHARAAN.get(c.get("jenis"), c.get("jenis")),
            c.get("uraian"), int(parse_biaya(c.get("biaya")) or 0),
            c.get("kondisi_sebelum"), c.get("kondisi_setelah"),
            "Ya" if c.get("indikasi_kapitalisasi") else "",
            c.get("pelaksana"), c.get("no_bukti"), c.get("keterangan"),
            c.get("created_by"),
        ])
    return HttpResponse(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="riwayat_pemeliharaan.csv"'})


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
async def create_pemeliharaan(payload: PemeliharaanIn, user: dict = Depends(require_writer)):
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
    # Jadwal berkala aset ini bergeser otomatis: pelaksanaan terbaru menjadi
    # dasar jatuh tempo berikutnya ($max aman utk ISO string; "" selalu kalah).
    await db.jadwal_pemeliharaan.update_many(
        {"asset_id": asset["id"]},
        {"$max": {"terakhir": record["tanggal"]}, "$set": {"updated_at": now}},
    )
    return record


async def _konteks_kapitalisasi(catatan_id: str):
    """Muat catatan + aset + perhitungan Tabel II — dipakai pratinjau & posting.

    Persentase dihitung terhadap NILAI DASAR PENYUSUTAN (basis revaluasi bila
    ada, kalau tidak nilai perolehan) SEBELUM biaya perbaikan ditambahkan —
    sesuai kolom KMK "dari nilai aset (di luar penyusutan)".
    """
    from pembukuan_utils import parse_harga
    from penilaian_utils import dasar_penyusutan
    from perbaikan_utils import hitung_penambahan_masa_manfaat

    rec = await db.pemeliharaan.find_one({"id": catatan_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan")
    aset = await db.assets.find_one(
        {"id": rec.get("asset_id"), "dihapus": {"$ne": True}},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "purchase_date": 1, "nilai_wajar_terakhir": 1,
         "revaluasi": 1, "masa_manfaat_tambah_tahun": 1, "location": 1})
    if not aset:
        raise HTTPException(status_code=404,
                            detail="Aset tidak ditemukan / sudah dihapus")
    biaya = parse_harga(rec.get("biaya"))
    nilai_dasar, _mulai, _sumber = dasar_penyusutan(aset)
    hitung = hitung_penambahan_masa_manfaat(
        aset.get("asset_code"), biaya, nilai_dasar)
    return rec, aset, biaya, nilai_dasar, hitung


@pemeliharaan_router.get("/pemeliharaan/{catatan_id}/pratinjau-kapitalisasi")
async def pratinjau_kapitalisasi(catatan_id: str,
                                 _user: dict = Depends(require_user)):
    """Pratinjau efek posting: nilai bertambah + tambahan masa manfaat
    Tabel II KMK 295/266/339 (persentase biaya terhadap nilai dasar)."""
    from perbaikan_utils import DASAR_HUKUM_PERBAIKAN

    rec, aset, biaya, nilai_dasar, hitung = await _konteks_kapitalisasi(catatan_id)
    return {
        "catatan_id": catatan_id,
        "sudah_diposting": bool(rec.get("kapitalisasi_diposting")),
        "indikasi_kapitalisasi": bool(rec.get("indikasi_kapitalisasi")),
        "biaya": biaya,
        "nilai_dasar": nilai_dasar,
        "perbaikan": hitung,   # None = kelompok tak terdaftar di Tabel II
        "masa_manfaat_tambah_sekarang": int(aset.get("masa_manfaat_tambah_tahun") or 0),
        "dasar_hukum": DASAR_HUKUM_PERBAIKAN,
        "ba_perbaikan": rec.get("ba_perbaikan") or None,
    }


@pemeliharaan_router.post("/pemeliharaan/{catatan_id}/kapitalisasi")
async def posting_kapitalisasi(catatan_id: str,
                               payload: KapitalisasiIn = None,
                               admin: dict = Depends(require_admin)):
    """Posting PENGEMBANGAN NILAI ASET (jurnal 202) dari catatan pemeliharaan
    ber-indikasi kapitalisasi (PMK 181) — integrasi Pemeliharaan → Pembukuan.

    Sekaligus (PMK 65/2017 Ps.15 + KMK 295/2019 Diktum KEENAM): perbaikan
    yang menambah umur diakui lewat BERITA ACARA serah terima pekerjaan —
    payload BA disimpan (nomor otomatis bila kosong), tambahan masa manfaat
    dari Tabel Masa Manfaat II diterapkan ke aset, dan BA dapat diunduh
    sebagai PDF. Keputusan kualitatif tetap pada admin; catatan ditandai
    agar tidak dobel-posting (CAS idempoten).
    """
    from shared_utils import catat_mutasi_bmn, log_audit

    ba = payload or KapitalisasiIn()
    rec, aset, biaya, nilai_dasar, hitung = await _konteks_kapitalisasi(catatan_id)
    if not rec.get("indikasi_kapitalisasi"):
        raise HTTPException(
            status_code=400,
            detail="Catatan ini tidak berindikasi kapitalisasi (biaya di bawah ambang PMK 181)")
    if biaya <= 0:
        raise HTTPException(status_code=400, detail="Biaya tidak valid")
    now = datetime.now(timezone.utc).isoformat()
    tgl_ba = str(ba.tanggal_serah_terima or "").strip()[:10] or now[:10]
    tambah_tahun = int((hitung or {}).get("tambah_tahun") or 0) \
        if ba.terapkan_masa_manfaat else 0
    nomor_ba = str(ba.nomor_ba or "").strip()
    if not nomor_ba:
        urut = await db.pemeliharaan.count_documents(
            {"ba_perbaikan.nomor": {"$exists": True}}) + 1
        nomor_ba = f"BA-PRB/{urut:03d}/{tgl_ba[:4]}"
    ba_doc = {
        "nomor": nomor_ba,
        "tanggal": tgl_ba,
        "pihak_pelaksana": str(ba.pihak_pelaksana or "").strip(),
        "jabatan_pelaksana": str(ba.jabatan_pelaksana or "").strip(),
        "pihak_penerima": str(ba.pihak_penerima or "").strip(),
        "jabatan_penerima": str(ba.jabatan_penerima or "").strip(),
        "nilai_dasar": nilai_dasar,
        "perbaikan": hitung,           # {kelompok, jenis, persentase, ...}|None
        "tambah_tahun_diterapkan": tambah_tahun,
        "dibuat_oleh": admin.get("username"),
        "dibuat_pada": now,
    }
    # CAS idempoten: hanya SATU request yang lolos menandai — cegah dobel
    # penambahan nilai bila tombol diklik dua kali / dua tab.
    res = await db.pemeliharaan.update_one(
        {"id": catatan_id, "kapitalisasi_diposting": {"$ne": True}},
        {"$set": {"kapitalisasi_diposting": True,
                  "kapitalisasi_oleh": admin.get("username"),
                  "kapitalisasi_pada": now, "ba_perbaikan": ba_doc,
                  "updated_at": now}})
    if res.modified_count == 0:
        raise HTTPException(status_code=409,
                            detail="Sudah pernah diposting sebagai pengembangan nilai")
    # Nilai perolehan BERTAMBAH — pengembangan nilai menambah nilai yang
    # dibukukan (DBKP/posisi neraca membaca purchase_price); masa manfaat
    # bertambah sesuai Tabel II (dibaca status_susut Penilaian/DBKP/LBP);
    # version naik untuk bust cache/OCC form.
    inc = {"purchase_price": biaya, "version": 1}
    if tambah_tahun > 0:
        inc["masa_manfaat_tambah_tahun"] = tambah_tahun
    await db.assets.update_one(
        {"id": aset["id"]},
        {"$inc": inc, "$set": {"updated_at": now}})
    await catat_mutasi_bmn({
        "asset_id": aset["id"], "kode_transaksi": "202",
        "kode_barang": str(aset.get("asset_code") or ""),
        "nup": str(aset.get("NUP") or ""),
        "tanggal_buku": str(rec.get("tanggal") or now)[:10], "jumlah": 1,
        "nilai": biaya, "sumber_modul": "pemeliharaan", "ref_id": catatan_id,
        "keterangan": ("Pengembangan nilai dari pemeliharaan: "
                       + str(rec.get("uraian") or ""))[:200],
        "oleh": admin.get("username", "system")})
    detail_mm = (f" + masa manfaat +{tambah_tahun} th (Tabel II KMK, {nomor_ba})"
                 if tambah_tahun > 0 else f" (BA {nomor_ba})")
    await log_audit("kapitalisasi_pemeliharaan", "", asset_id=aset["id"],
                    asset_code=str(aset.get("asset_code") or ""),
                    asset_name=str(aset.get("asset_name") or ""),
                    username=admin.get("username", "system"),
                    detail=f"Jurnal 202 Rp{int(biaya):,} dari catatan {catatan_id}{detail_mm}")
    return {"ok": True, "nilai_ditambahkan": biaya, "asset_id": aset["id"],
            "kode_transaksi": "202", "nomor_ba": nomor_ba,
            "tambah_masa_manfaat_tahun": tambah_tahun,
            "perbaikan": hitung}


@pemeliharaan_router.get("/pemeliharaan/{catatan_id}/ba-perbaikan-pdf")
async def ba_perbaikan_pdf(catatan_id: str, _user: dict = Depends(require_user)):
    """BERITA ACARA SERAH TERIMA HASIL PEKERJAAN PERBAIKAN (PDF).

    Dokumen pengakuan tambahan masa manfaat akibat perbaikan (KMK 295/2019
    Diktum KEENAM) — memuat identitas aset, uraian & biaya pekerjaan,
    persentase terhadap nilai aset, jenis perbaikan, dan tambahan masa
    manfaat sesuai Tabel Masa Manfaat II.
    """
    from io import BytesIO

    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from perbaikan_utils import DASAR_HUKUM_PERBAIKAN
    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles,
        _kop_surat_flowables, _page_footer_factory, _signature_block,
        _std_doc, _std_table_style, _title_block,
    )

    rec = await db.pemeliharaan.find_one({"id": catatan_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan")
    ba = rec.get("ba_perbaikan")
    if not ba:
        raise HTTPException(
            status_code=404,
            detail="Belum ada Berita Acara — posting kapitalisasi dahulu")
    hit = ba.get("perbaikan") or {}
    tambah = int(ba.get("tambah_tahun_diterapkan") or 0)

    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block(
        "BERITA ACARA SERAH TERIMA HASIL PEKERJAAN PERBAIKAN",
        subjudul=f"Nomor: {ba.get('nomor') or '-'}"))
    el.append(Paragraph(
        f"Pada hari ini, tanggal {_fmt_tanggal_id(ba.get('tanggal'))}, "
        "telah dilakukan serah terima hasil pekerjaan perbaikan Barang "
        "Milik Negara dengan rincian sebagai berikut:", st['Body']))
    el.append(Spacer(1, 3 * rl_mm))
    from xml.sax.saxutils import escape as _esc
    pct = hit.get("persentase")
    baris = [
        ("Nama Barang", rec.get("asset_name") or "-"),
        ("Kode Barang · NUP", f"{rec.get('asset_code') or '-'} · {rec.get('NUP') or '-'}"),
        ("Tanggal Pekerjaan", _fmt_tanggal_id(rec.get("tanggal"))),
        ("Uraian Pekerjaan", rec.get("uraian") or "-"),
        ("Pelaksana", rec.get("pelaksana") or ba.get("pihak_pelaksana") or "-"),
        ("No. Bukti/SPM/Kontrak", rec.get("no_bukti") or "-"),
        ("Biaya Perbaikan", f"Rp{_fmt_rp(rec.get('biaya'))}"),
        ("Nilai Aset (di luar penyusutan)", f"Rp{_fmt_rp(ba.get('nilai_dasar'))}"),
        ("Persentase thd Nilai Aset", f"{pct}%" if pct is not None else "-"),
        ("Jenis Perbaikan (Tabel II)", hit.get("jenis") or "-"),
        ("Tambahan Masa Manfaat", f"{tambah} tahun" if tambah > 0
         else "Tidak menambah masa manfaat"),
    ]
    tdata = [[Paragraph(f"<b>{_esc(k)}</b>", st['Cell']),
              Paragraph(_esc(str(v)), st['Cell'])] for k, v in baris]
    tbl = Table(tdata, colWidths=_fit_col_widths([160, 340], doc.width))
    tbl.setStyle(_std_table_style(zebra=True))
    el.append(tbl)
    el.append(Spacer(1, 3 * rl_mm))
    if tambah > 0:
        el.append(Paragraph(
            "Dengan ditandatanganinya Berita Acara ini, tambahan masa manfaat "
            f"sebesar <b>{tambah} tahun</b> atas Aset Tetap tersebut DIAKUI "
            "terhitung sejak tanggal serah terima pekerjaan, sesuai "
            f"{DASAR_HUKUM_PERBAIKAN}.", st['Body']))
    else:
        el.append(Paragraph(
            "Perbaikan ini dibukukan sebagai pengembangan nilai aset "
            f"(jurnal 202) sesuai {DASAR_HUKUM_PERBAIKAN}; berdasarkan "
            "Tabel Masa Manfaat II tidak terdapat tambahan masa manfaat "
            "untuk rentang persentase tersebut.", st['Body']))
    el.append(Spacer(1, 10 * rl_mm))
    el.extend(_signature_block([
        {"header": "Yang Menyerahkan,",
         "role": ba.get("jabatan_pelaksana") or "Pelaksana Pekerjaan",
         "nama": ba.get("pihak_pelaksana") or "................"},
        {"header": "Yang Menerima,",
         "role": ba.get("jabatan_penerima") or "Pejabat Penerima Hasil Pekerjaan",
         "nama": ba.get("pihak_penerima") or "................"},
    ], doc.width))
    footer = _page_footer_factory("BA Perbaikan")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    from fastapi.responses import StreamingResponse
    aman = "".join(c if c.isalnum() else "_" for c in (ba.get("nomor") or catatan_id))[:40]
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="BA_Perbaikan_{aman}.pdf"'})


@pemeliharaan_router.delete("/pemeliharaan/{catatan_id}")
async def delete_pemeliharaan(catatan_id: str, _admin: dict = Depends(require_admin)):
    """Hapus catatan pemeliharaan (khusus admin, mis. salah input).

    Catatan yang SUDAH diposting sebagai pengembangan nilai (jurnal 202)
    tidak boleh dihapus — nilai aset sudah bertambah dan jejaknya harus
    tetap tertelusur (koreksi nilai lewat register Penilaian bila salah).
    """
    rec = await db.pemeliharaan.find_one(
        {"id": catatan_id}, {"_id": 0, "kapitalisasi_diposting": 1})
    if not rec:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan")
    if rec.get("kapitalisasi_diposting"):
        raise HTTPException(
            status_code=409,
            detail=("Catatan sudah diposting sebagai pengembangan nilai "
                    "(jurnal 202) — tidak dapat dihapus; koreksi nilai "
                    "dilakukan lewat register Penilaian"))
    res = await db.pemeliharaan.delete_one({"id": catatan_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Catatan tidak ditemukan")
    return {"ok": True, "id": catatan_id}
