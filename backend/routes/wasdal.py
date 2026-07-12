"""WASDAL — dasbor pemantauan tingkat KPB (PMK 207/PMK.06/2021, pustaka §8).

Mesin aturan ringan atas register yang sudah ada (aset, pemanfaatan,
usulan penghapusan, pemindahtanganan, pemeliharaan) → temuan per lima
objek pemantauan. Bahan pra-isi laporan wasdal semesteran; kanal resmi
pelaporan tetap Modul Wasdal SIMAN v2. Register penertiban (timer 15 hari
kerja) & BA pemantauan insidentil menyusul sesuai masterplan.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from auth_utils import require_user
from db import db
from wasdal_utils import (
    AMBANG_BERLARUT_HARI, JENIS_TEMUAN, OBJEK_WASDAL,
    periode_wasdal, rekap_wasdal, susun_temuan,
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
