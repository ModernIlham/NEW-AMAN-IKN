"""WASDAL — dasbor pemantauan tingkat KPB (PMK 207/PMK.06/2021, pustaka §8).

Mesin aturan ringan atas register yang sudah ada (aset, pemanfaatan,
usulan penghapusan, pemindahtanganan, pemeliharaan) → temuan per lima
objek pemantauan + register penertiban ber-tenggat 15 hari kerja. Bahan
pra-isi laporan wasdal semesteran; kanal resmi pelaporan tetap Modul
Wasdal SIMAN v2. BA pemantauan insidentil menyusul sesuai masterplan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from wasdal_utils import (
    AMBANG_BERLARUT_HARI, JENIS_TEMUAN, OBJEK_WASDAL,
    SUMBER_PENERTIBAN, STATUS_PENERTIBAN, TENGGAT_HARI_KERJA,
    periode_wasdal, rekap_penertiban, rekap_wasdal,
    status_tenggat_penertiban, susun_temuan, tambah_hari_kerja,
    validate_penertiban, validate_selesai_penertiban,
)

wasdal_router = APIRouter()

# Proyeksi hemat aset: hanya field yang dibaca mesin aturan.
_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "user": 1, "bast_file_id": 1, "condition": 1,
              "purchase_price": 1, "koordinat_latitude": 1,
              "koordinat_longitude": 1, "inventory_status": 1,
              "nomor_perkara": 1, "pihak_bersengketa": 1}

# Jumlah maksimal temuan yang dikirim per objek (rekap tetap utuh).
_MAKS_TAMPIL = 100


async def _data_pemantauan(ambang_hari: int):
    """Kumpulkan register → (periode, per_objek, rekap, total_aset)."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    periode = periode_wasdal(today_iso)
    tahun = periode["tahun"]

    assets = [a async for a in db.assets.find({}, _PROJ_ASET)]
    pemanfaatan = [p async for p in db.pemanfaatan.find(
        {}, {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "asset_name": 1,
             "berakhir": 1, "nomor_persetujuan": 1, "nomor_perjanjian": 1,
             "ntpn": 1})]
    usulan_hapus = [u async for u in db.usulan_penghapusan.find(
        {"status": {"$in": ["diusulkan", "diproses"]}},
        {"_id": 0, "id": 1, "asset_id": 1, "asset_name": 1, "status": 1,
         "created_at": 1})]
    usulan_pt = [u async for u in db.pemindahtanganan.find(
        {"status": "disetujui"},
        {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "status": 1,
         "tanggal_persetujuan": 1})]
    pemeliharaan = [r async for r in db.pemeliharaan.find(
        {"tanggal": {"$gte": f"{tahun}-01-01", "$lte": f"{tahun}-12-31"}},
        {"_id": 0, "asset_id": 1, "tanggal": 1})]

    per_objek = susun_temuan(assets, pemanfaatan, usulan_hapus, usulan_pt,
                             pemeliharaan, today_iso, ambang_hari)
    return periode, per_objek, rekap_wasdal(per_objek), len(assets)


@wasdal_router.get("/wasdal/pemantauan")
async def pemantauan_wasdal(
    ambang_hari: int = Query(AMBANG_BERLARUT_HARI, ge=1, le=730),
    _user: dict = Depends(require_user),
):
    """Temuan pemantauan per objek wasdal + rekap + periode berjalan."""
    periode, per_objek, rekap, total_aset = await _data_pemantauan(ambang_hari)
    return {
        "periode": periode,
        "rekap": rekap,
        "temuan": {k: v[:_MAKS_TAMPIL] for k, v in per_objek.items()},
        "terpotong": {k: max(0, len(v) - _MAKS_TAMPIL)
                      for k, v in per_objek.items()},
        "label_objek": OBJEK_WASDAL,
        "label_jenis": JENIS_TEMUAN,
        "ambang_hari": ambang_hari,
        "total_aset": total_aset,
    }


class PenertibanIn(BaseModel):
    sumber: str
    tanggal_dasar: str = Field(min_length=10, max_length=10)
    objek: str = ""                 # salah satu 5 objek pemantauan (opsional)
    uraian: str = Field(min_length=1)
    asset_id: str = ""              # tautan opsional ke aset


class SelesaiPenertibanIn(BaseModel):
    tindak_lanjut: str = Field(min_length=1)
    tanggal_selesai: str = ""


@wasdal_router.get("/wasdal/penertiban")
async def daftar_penertiban(_user: dict = Depends(require_user)):
    """Register penertiban + sisa/lewat tenggat + rekap."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [t async for t in db.penertiban.find({}, {"_id": 0})
             .sort("created_at", -1).limit(500)]
    for t in items:
        t["info_tenggat"] = status_tenggat_penertiban(t, today_iso)
    return {"items": items, "ringkasan": rekap_penertiban(items, today_iso),
            "label_sumber": SUMBER_PENERTIBAN,
            "label_status": STATUS_PENERTIBAN,
            "label_objek": OBJEK_WASDAL,
            "tenggat_hari_kerja": TENGGAT_HARI_KERJA,
            "catatan": (
                "PMK 207/2021: penertiban oleh KPB selesai paling lama "
                f"{TENGGAT_HARI_KERJA} hari kerja sejak pemantauan selesai / "
                "surat permintaan Pengelola diterima (juga dipicu temuan "
                "APIP/BPK). Tenggat dihitung hari kerja Senin–Jumat.")}


@wasdal_router.post("/wasdal/penertiban")
async def catat_penertiban(payload: PenertibanIn,
                           user: dict = Depends(require_user)):
    """Buka tiket penertiban — tenggat otomatis 15 hari kerja."""
    data = payload.model_dump()
    errors = validate_penertiban(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset = None
    if str(data.get("asset_id") or "").strip():
        aset = await db.assets.find_one(
            {"id": data["asset_id"].strip()},
            {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
        if not aset:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "sumber": data["sumber"],
        "tanggal_dasar": data["tanggal_dasar"].strip()[:10],
        "tenggat": tambah_hari_kerja(data["tanggal_dasar"]),
        "objek": str(data.get("objek") or "").strip(),
        "uraian": data["uraian"].strip(),
        "status": "berjalan",
        "tindak_lanjut": "",
        "tanggal_selesai": "",
        "asset_id": (aset or {}).get("id") or "",
        "asset_code": (aset or {}).get("asset_code"),
        "NUP": (aset or {}).get("NUP"),
        "asset_name": (aset or {}).get("asset_name"),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.penertiban.insert_one({**record})
    record["info_tenggat"] = status_tenggat_penertiban(
        record, datetime.now(timezone.utc).date().isoformat())
    return record


@wasdal_router.post("/wasdal/penertiban/{tiket_id}/selesai")
async def selesaikan_penertiban(tiket_id: str, payload: SelesaiPenertibanIn,
                                admin: dict = Depends(require_admin)):
    """Tutup tiket penertiban dengan uraian tindak lanjut (admin)."""
    t = await db.penertiban.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    data = payload.model_dump()
    errors = validate_selesai_penertiban(t, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    res = await db.penertiban.find_one_and_update(
        # Anti-balapan: hanya tiket yang masih berjalan
        {"id": tiket_id, "status": "berjalan"},
        {"$set": {"status": "selesai",
                  "tindak_lanjut": data["tindak_lanjut"].strip(),
                  "tanggal_selesai": (str(data.get("tanggal_selesai") or "").strip()[:10]
                                      or now[:10]),
                  "diselesaikan_oleh": admin.get("username"),
                  "updated_at": now}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Tiket berubah oleh proses lain — muat ulang")
    return res


@wasdal_router.delete("/wasdal/penertiban/{tiket_id}")
async def hapus_penertiban(tiket_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (khusus admin)."""
    res = await db.penertiban.delete_one({"id": tiket_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    return {"ok": True, "id": tiket_id}


@wasdal_router.get("/wasdal/laporan-pdf")
async def laporan_wasdal_pdf(
    ambang_hari: int = Query(AMBANG_BERLARUT_HARI, ge=1, le=730),
    _user: dict = Depends(require_user),
):
    """Laporan Hasil Pemantauan Wasdal tingkat KPB (PDF pra-isi).

    Bahan penyusunan laporan wasdal semesteran — kanal resmi pelaporan
    tetap Modul Wasdal SIMAN v2 (pustaka §8). Rincian dibatasi 30 temuan
    per objek dengan penanda sisa; data murni dari register.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _fit_col_widths, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    _MAKS_RINCI = 30
    periode, per_objek, rekap, total_aset = await _data_pemantauan(ambang_hari)
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("LAPORAN HASIL PEMANTAUAN\nPENGAWASAN DAN PENGENDALIAN BMN",
                                 subjudul=f"Tingkat Kuasa Pengguna Barang — {periode['label']}"))
    elements.append(Paragraph(
        f"Pemantauan dilakukan atas {total_aset} aset dalam penguasaan Kuasa "
        f"Pengguna Barang terhadap lima objek pemantauan PMK 207/PMK.06/2021. "
        f"Terdapat <b>{rekap['total']} temuan</b> yang memerlukan tindak "
        f"lanjut/penertiban. Laporan ini adalah bahan pra-isi — pelaporan "
        f"wasdal resmi disampaikan melalui Modul Wasdal SIMAN v2.",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    # Rekap per objek pemantauan
    headers = ["No", "Objek Pemantauan", "Jumlah Temuan"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    for i, (kunci, label) in enumerate(OBJEK_WASDAL.items(), start=1):
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(label, st['Cell']),
            Paragraph(str(rekap["per_objek"].get(kunci, 0)), st['CellCenter']),
        ])
    table_data.append([
        Paragraph("", st['Cell']),
        Paragraph("<b>Jumlah</b>", st['Cell']),
        Paragraph(f"<b>{rekap['total']}</b>", st['CellCenter']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([28, 330, 100], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)
    elements.append(Spacer(1, 5 * rl_mm))

    # Rincian per objek (maks 30 baris per objek)
    for kunci, label in OBJEK_WASDAL.items():
        temuan = per_objek.get(kunci) or []
        if not temuan:
            continue
        elements.append(Paragraph(f"<b>{label}</b> — {len(temuan)} temuan",
                                  st['Meta']))
        elements.append(Spacer(1, 1.5 * rl_mm))
        headers = ["No", "Jenis Temuan", "Objek/Aset", "Keterangan"]
        rinci = [[Paragraph(h, st['TableHeader']) for h in headers]]
        for i, t in enumerate(temuan[:_MAKS_RINCI], start=1):
            nama = t.get("asset_name") or t.get("pihak") or "-"
            kode = t.get("asset_code")
            if kode:
                nama = f"{nama} ({kode} · {t.get('NUP') or '-'})"
            rinci.append([
                Paragraph(str(i), st['CellCenter']),
                Paragraph(t.get("label") or t.get("jenis") or "-", st['Cell']),
                Paragraph(nama, st['Cell']),
                Paragraph(t.get("detail") or "-", st['Cell']),
            ])
        table = Table(rinci,
                      colWidths=_fit_col_widths([26, 140, 160, 132], doc.width),
                      repeatRows=1)
        table.setStyle(_std_table_style(zebra=True))
        elements.append(table)
        if len(temuan) > _MAKS_RINCI:
            elements.append(Paragraph(
                f"…dan {len(temuan) - _MAKS_RINCI} temuan lain (lihat dasbor "
                f"Wasdal untuk daftar lengkap).", st['Meta']))
        elements.append(Spacer(1, 4 * rl_mm))

    elements.append(Spacer(1, 8 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Pemantauan,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Mengetahui,', 'role': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or '...........................',
         'after': [f"NIP. {settings.get('kasatker_nip') or '....................'}"]},
    ], doc.width))
    footer = _page_footer_factory("Laporan Hasil Pemantauan Wasdal BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama = f"Laporan_Wasdal_{periode['label'].replace(' ', '_')}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{nama}"'})
