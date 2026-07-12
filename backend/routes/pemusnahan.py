"""PEMUSNAHAN — Fase 6 tahap awal: register Berita Acara Pemusnahan.

PMK 83/PMK.06/2016 (pustaka §1 & §12): BA dicatat setelah persetujuan +
pelaksanaan; objek dibatasi aset rusak berat (kelayakan divalidasi per
aset). Tindak lanjut penghapusan lewat modul Penghapusan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemusnahan_utils import (
    CARA_PEMUSNAHAN, alasan_usulan_dari_ba, kelayakan_musnah,
    rekap_pemusnahan, validate_pemusnahan,
)

pemusnahan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "purchase_price": 1, "condition": 1}


class PemusnahanIn(BaseModel):
    nomor_ba: str
    tanggal_ba: str
    cara: str
    nomor_persetujuan: str
    keterangan: str = ""
    asset_ids: list[str] = Field(min_length=1, max_length=100)


@pemusnahan_router.get("/pemusnahan")
async def list_pemusnahan(_user: dict = Depends(require_user)):
    """Register BA pemusnahan (terbaru dulu) + ringkasan + status usulan."""
    items = [r async for r in db.pemusnahan.find({}, {"_id": 0})
             .sort("tanggal_ba", -1).limit(500)]
    # Satu kueri: aset BA mana yang sudah punya usulan penghapusan aktif
    semua_id = [a.get("asset_id") for r in items for a in (r.get("aset") or [])]
    diusulkan = set()
    if semua_id:
        async for u in db.usulan_penghapusan.find(
                {"asset_id": {"$in": semua_id}, "status": {"$ne": "ditolak"}},
                {"_id": 0, "asset_id": 1}):
            diusulkan.add(u["asset_id"])
    for r in items:
        r["aset_diusulkan"] = sum(
            1 for a in (r.get("aset") or []) if a.get("asset_id") in diusulkan)
    return {"items": items, "ringkasan": rekap_pemusnahan(items),
            "label_cara": CARA_PEMUSNAHAN,
            "catatan": (
                "BA dicatat setelah persetujuan Pengelola/Pengguna Barang dan "
                "pelaksanaan pemusnahan (PMK 83/2016); tindak lanjut usulan "
                "penghapusan lewat modul Penghapusan.")}


@pemusnahan_router.post("/pemusnahan")
async def buat_pemusnahan(payload: PemusnahanIn, user: dict = Depends(require_user)):
    """Catat satu BA pemusnahan multi-aset (aset harus rusak berat)."""
    data = payload.model_dump()
    today_iso = datetime.now(timezone.utc).date().isoformat()
    errors = validate_pemusnahan(data, today_iso)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_rows = []
    for aid in dict.fromkeys(data["asset_ids"]):  # dedup, jaga urutan
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail=f"Aset {aid} tidak ditemukan")
        layak, alasan = kelayakan_musnah(a)
        if not layak:
            raise HTTPException(status_code=400,
                                detail=f"{a.get('asset_name') or aid}: {alasan}")
        aset_rows.append({"asset_id": a["id"], "asset_code": a.get("asset_code"),
                          "NUP": a.get("NUP"), "asset_name": a.get("asset_name"),
                          "harga": a.get("purchase_price")})
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "nomor_ba": data["nomor_ba"].strip(),
        "tanggal_ba": str(data["tanggal_ba"]).strip()[:10],
        "cara": data["cara"],
        "nomor_persetujuan": data["nomor_persetujuan"].strip(),
        "keterangan": str(data.get("keterangan") or "").strip(),
        "aset": aset_rows,
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemusnahan.insert_one({**record})
    return record


@pemusnahan_router.post("/pemusnahan/{ba_id}/usulkan-penghapusan")
async def usulkan_penghapusan_dari_ba(ba_id: str,
                                      user: dict = Depends(require_user)):
    """Buat usulan penghapusan (register Penghapusan) untuk aset BA ini.

    Tindak lanjut PMK 83/2016: barang yang telah dimusnahkan diusulkan
    hapus dari DBKP. Aset yang sudah punya usulan aktif dilewati (bukan
    galat) supaya tombol aman diklik ulang.
    """
    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0})
    if not ba:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    hasil = []
    dibuat = 0
    for a in ba.get("aset") or []:
        aid = a.get("asset_id")
        aktif = await db.usulan_penghapusan.find_one(
            {"asset_id": aid, "status": {"$ne": "ditolak"}},
            {"_id": 0, "id": 1, "status": 1})
        if aktif:
            hasil.append({"asset_id": aid, "asset_name": a.get("asset_name"),
                          "dibuat": False,
                          "alasan": f"Sudah ada usulan aktif ({aktif.get('status')})"})
            continue
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": str(uuid.uuid4()),
            "asset_id": aid,
            "asset_code": a.get("asset_code"),
            "NUP": a.get("NUP"),
            "asset_name": a.get("asset_name"),
            "jalur": "rusak_berat",
            "status": "diusulkan",
            "nomor_sk": "",
            "tanggal_sk": "",
            "keterangan": alasan_usulan_dari_ba(ba),
            "riwayat": [{"status": "diusulkan", "tanggal": now,
                         "oleh": user.get("username"),
                         "catatan": f"Otomatis dari BA {ba.get('nomor_ba')}"}],
            "created_by": user.get("username"),
            "created_at": now,
            "updated_at": now,
        }
        await db.usulan_penghapusan.insert_one({**record})
        dibuat += 1
        hasil.append({"asset_id": aid, "asset_name": a.get("asset_name"),
                      "dibuat": True, "alasan": ""})
    return {"total": len(hasil), "dibuat": dibuat,
            "terlewati": len(hasil) - dibuat, "hasil": hasil}


@pemusnahan_router.get("/pemusnahan/{ba_id}/ba-pdf")
async def ba_pemusnahan_pdf(ba_id: str, _user: dict = Depends(require_user)):
    """Berita Acara Pemusnahan siap tanda tangan (PMK 83/2016).

    Kop surat satker, narasi dasar persetujuan + cara pemusnahan, tabel
    aset multi-baris dengan nilai perolehan, blok tanda tangan pelaksana/
    saksi/KPB. Data murni dari register — tanpa isian dummy.
    """
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from pembukuan_utils import parse_harga
    from routes.reports import (
        _fit_col_widths, _fmt_tanggal_id, _get_report_styles, _kop_surat_flowables,
        _page_footer_factory, _signature_block, _std_doc, _std_table_style,
        _title_block,
    )

    ba = await db.pemusnahan.find_one({"id": ba_id}, {"_id": 0})
    if not ba:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}
    aset = ba.get("aset") or []
    cara = CARA_PEMUSNAHAN.get(ba.get("cara"), ba.get("cara") or "-")

    def _rp(v):
        n = parse_harga(v)
        return f"Rp{n:,.0f}".replace(",", ".") if n else "-"

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block("BERITA ACARA PEMUSNAHAN BARANG MILIK NEGARA",
                                 nomor=ba.get("nomor_ba") or "-"))
    elements.append(Paragraph(
        f"Pada tanggal {_fmt_tanggal_id(ba.get('tanggal_ba'))}, berdasarkan "
        f"persetujuan pemusnahan Nomor {ba.get('nomor_persetujuan') or '-'}, "
        f"telah dilaksanakan pemusnahan Barang Milik Negara dengan cara "
        f"<b>{cara.lower()}</b> terhadap {len(aset)} unit barang dalam kondisi "
        f"rusak berat yang tidak dapat digunakan, dimanfaatkan, maupun "
        f"dipindahtangankan (PMK 83/PMK.06/2016), dengan rincian sebagai berikut:",
        st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))

    headers = ["No", "Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan"]
    table_data = [[Paragraph(h, st['TableHeader']) for h in headers]]
    total = 0.0
    for i, a in enumerate(aset, start=1):
        total += parse_harga(a.get("harga"))
        table_data.append([
            Paragraph(str(i), st['CellCenter']),
            Paragraph(a.get("asset_code") or "-", st['Cell']),
            Paragraph(str(a.get("NUP") or "-"), st['CellCenter']),
            Paragraph(a.get("asset_name") or "-", st['Cell']),
            Paragraph(_rp(a.get("harga")), st['CellRight']),
        ])
    table_data.append([
        Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph("", st['Cell']),
        Paragraph("<b>Jumlah</b>", st['Cell']),
        Paragraph(f"<b>{_rp(total)}</b>", st['CellRight']),
    ])
    table = Table(table_data,
                  colWidths=_fit_col_widths([28, 120, 45, 190, 90], doc.width),
                  repeatRows=1)
    table.setStyle(_std_table_style(zebra=True, total_row=True))
    elements.append(table)

    if str(ba.get("keterangan") or "").strip():
        elements.append(Spacer(1, 3 * rl_mm))
        elements.append(Paragraph(f"Keterangan: {ba['keterangan']}", st['Meta']))
    elements.append(Spacer(1, 4 * rl_mm))
    elements.append(Paragraph(
        "Demikian Berita Acara Pemusnahan ini dibuat dengan sebenarnya untuk "
        "dipergunakan sebagaimana mestinya, sebagai dasar usulan penghapusan "
        "dari Daftar Barang Kuasa Pengguna.", st['Meta']))
    elements.append(Spacer(1, 12 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Pelaksana,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Saksi,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        {'pre': [''], 'header': 'Mengetahui,', 'role': 'Kuasa Pengguna Barang,',
         'nama': settings.get("kasatker_nama") or '...........................',
         'after': [f"NIP. {settings.get('kasatker_nip') or '....................'}"]},
    ], doc.width))
    footer = _page_footer_factory("Berita Acara Pemusnahan BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama_file = (ba.get("nomor_ba") or "BA").replace("/", "-").replace(" ", "_")
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="BA_Pemusnahan_{nama_file}.pdf"'})


@pemusnahan_router.delete("/pemusnahan/{ba_id}")
async def hapus_pemusnahan(ba_id: str, _admin: dict = Depends(require_admin)):
    """Hapus BA salah input (khusus admin)."""
    res = await db.pemusnahan.delete_one({"id": ba_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="BA tidak ditemukan")
    return {"ok": True, "id": ba_id}
