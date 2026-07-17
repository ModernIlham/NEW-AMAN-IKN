"""PERENCANAAN — Fase 4 tahap awal: kandidat RKBMN pemeliharaan.

PMK 153/PMK.06/2021: satker menyusun usulan RKBMN pemeliharaan dari
daftar barang + hasil pemeliharaan. Modul ini menyaring aset yang LAYAK
diusulkan (Baik/Rusak Ringan, dioperasikan) vs yang tidak (rusak berat,
idle, nonaktif) + riwayat biaya pemeliharaan sebagai bahan pertimbangan.
RKBMN pengadaan + sanding SBSK menyusul sesuai masterplan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from pemeliharaan_utils import rekap_pemeliharaan
from perencanaan_utils import (
    JENIS_USULAN_RKBMN, STATUS_USULAN_RKBMN, TRANSISI_USULAN_RKBMN,
    rekap_rkbmn, rekap_usulan_rkbmn, validate_transisi_rkbmn,
    validate_usulan_rkbmn,
)

perencanaan_router = APIRouter()

_PROJ_ASET = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
              "condition": 1, "status": 1, "location": 1}
_PROJ_BIAYA = {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
               "asset_name": 1, "tanggal": 1, "jenis": 1, "biaya": 1}
_MAKS_BARIS = 1000  # daftar dipangkas untuk UI; ringkasan tetap utuh


async def _data_rkbmn(tahun: int):
    """Kumpulkan kandidat RKBMN (dipakai endpoint JSON & XLSX)."""
    assets = [a async for a in db.assets.find({}, _PROJ_ASET)]
    records = [r async for r in db.pemeliharaan.find({}, _PROJ_BIAYA)]
    per_aset = rekap_pemeliharaan(records, tahun=tahun)["per_aset"]
    biaya_map = {p["asset_id"]: p for p in per_aset if p.get("asset_id")}
    return rekap_rkbmn(assets, biaya_map)


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan-xlsx")
async def rkbmn_pemeliharaan_xlsx(
    tahun: int = Query(None, ge=2000, le=2100),
    _user: dict = Depends(require_user),
):
    """Kertas kerja usulan RKBMN pemeliharaan (XLSX) — siap diisi satker.

    Sheet "Layak Diusulkan" menambahkan kolom kosong Usulan Pekerjaan &
    Perkiraan Biaya untuk diisi lalu dibawa ke SIMAN; sheet "Tidak Layak"
    memuat alasan + jalur yang benar (jejak keputusan untuk auditor).
    """
    import io as io_module

    import xlsxwriter
    from fastapi.responses import StreamingResponse

    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun)
    buffer = io_module.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    f_judul = wb.add_format({"bold": True})
    f_kepala = wb.add_format({"bold": True, "bg_color": "#DDE6F2", "border": 1})
    f_isi = wb.add_format({"bold": True, "bg_color": "#FFF6DD", "border": 1})
    f_sel = wb.add_format({"border": 1})
    f_angka = wb.add_format({"border": 1, "num_format": "#,##0"})

    s1 = wb.add_worksheet("Layak Diusulkan")
    s1.write(0, 0, f"Kertas kerja usulan RKBMN pemeliharaan TA {tahun + 1} "
                   f"(PMK 153/2021) — riwayat biaya TA {tahun}; kolom kuning diisi satker",
             f_judul)
    kolom1 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status",
              "Lokasi", "Riwayat (x)", "Riwayat Biaya (Rp)"]
    for c, h in enumerate(kolom1):
        s1.write(2, c, h, f_kepala)
    s1.write(2, len(kolom1), "Usulan Pekerjaan", f_isi)
    s1.write(2, len(kolom1) + 1, "Perkiraan Biaya (Rp)", f_isi)
    for i, a in enumerate(hasil["layak"], start=3):
        s1.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s1.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s1.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s1.write(i, 3, str(a.get("condition") or ""), f_sel)
        s1.write(i, 4, str(a.get("status") or ""), f_sel)
        s1.write(i, 5, str(a.get("location") or ""), f_sel)
        s1.write_number(i, 6, a["riwayat_jumlah"], f_angka)
        s1.write_number(i, 7, a["riwayat_biaya"], f_angka)
        s1.write(i, 8, "", f_sel)
        s1.write(i, 9, "", f_angka)
    s1.set_column(0, 0, 14)
    s1.set_column(2, 2, 36)
    s1.set_column(3, 5, 14)
    s1.set_column(6, 7, 14)
    s1.set_column(8, 8, 32)
    s1.set_column(9, 9, 18)

    s2 = wb.add_worksheet("Tidak Layak")
    kolom2 = ["Kode Barang", "NUP", "Nama Barang", "Kondisi", "Status", "Alasan / Jalur yang Benar"]
    for c, h in enumerate(kolom2):
        s2.write(0, c, h, f_kepala)
    for i, a in enumerate(hasil["tidak"], start=1):
        s2.write(i, 0, str(a.get("asset_code") or ""), f_sel)
        s2.write(i, 1, str(a.get("NUP") or ""), f_sel)
        s2.write(i, 2, str(a.get("asset_name") or ""), f_sel)
        s2.write(i, 3, str(a.get("condition") or ""), f_sel)
        s2.write(i, 4, str(a.get("status") or ""), f_sel)
        s2.write(i, 5, a.get("alasan") or "", f_sel)
    s2.set_column(0, 0, 14)
    s2.set_column(2, 2, 36)
    s2.set_column(5, 5, 60)

    wb.close()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="Usulan_RKBMN_Pemeliharaan_TA{tahun + 1}.xlsx"'})


@perencanaan_router.get("/perencanaan/rkbmn-pemeliharaan")
async def rkbmn_pemeliharaan(
    tahun: int = Query(None, ge=2000, le=2100,
                       description="Tahun anggaran riwayat biaya (default: berjalan)"),
    _user: dict = Depends(require_user),
):
    """Kandidat usulan RKBMN pemeliharaan + riwayat biaya per aset."""
    if not tahun:
        tahun = datetime.now(timezone.utc).year
    hasil = await _data_rkbmn(tahun)
    dipangkas = {
        "layak": len(hasil["layak"]) > _MAKS_BARIS,
        "tidak": len(hasil["tidak"]) > _MAKS_BARIS,
    }
    hasil["layak"] = hasil["layak"][:_MAKS_BARIS]
    hasil["tidak"] = hasil["tidak"][:_MAKS_BARIS]
    hasil["tahun"] = tahun
    hasil["dipangkas"] = dipangkas
    hasil["catatan"] = (
        "Kriteria PMK 153/2021: hanya kondisi Baik/Rusak Ringan yang layak "
        "diusulkan; rusak berat = jalur penghapusan; BMN idle = penetapan "
        "status (PMK 120/2024). Riwayat biaya dari modul Pemeliharaan TA "
        f"{tahun}."
    )
    return hasil


class UsulanRkbmnIn(BaseModel):
    tahun_rkbmn: str = Field(min_length=4, max_length=4)
    jenis: str
    unit_pengusul: str = Field(min_length=1)
    uraian: str = Field(min_length=1)
    volume: float = Field(gt=0)
    satuan: str = Field(min_length=1)
    asset_id: str = ""                 # opsional (pemeliharaan/eksisting)
    keterangan: str = ""


class TransisiRkbmnIn(BaseModel):
    status: str
    catatan: str = ""
    sptjm: bool | None = None          # penanda SPTJM ditandatangani
    reviu_apip: bool | None = None     # penanda sudah direviu APIP


@perencanaan_router.get("/perencanaan/usulan")
async def list_usulan_rkbmn(_user: dict = Depends(require_user)):
    """Register usulan RKBMN per unit (terbaru dulu) + ringkasan."""
    items = [u async for u in db.perencanaan_usulan.find({}, {"_id": 0})
             .sort("updated_at", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_usulan_rkbmn(items),
            "label_jenis": JENIS_USULAN_RKBMN,
            "label_status": STATUS_USULAN_RKBMN,
            "transisi": {k: sorted(v) for k, v in TRANSISI_USULAN_RKBMN.items()},
            "catatan": (
                "Register pendamping rantai usulan RKBMN internal (PMK "
                "153/2021 + KMK 128/KM.6/2022) — usulan resmi tetap via "
                "SIMAN V2; status di sini tak berkekuatan hukum dan bukan "
                "cetakan RKBMN/SPTJM/Hasil Penelaahan.")}


@perencanaan_router.get("/perencanaan/usulan/export")
async def export_usulan_rkbmn(_user: dict = Depends(require_user)):
    """Ekspor CSV register usulan RKBMN (pola #158 — audit G4 #11)."""
    import csv as csv_module
    import io

    from fastapi import Response

    buf = io.StringIO()
    w = csv_module.writer(buf)
    w.writerow(["tahun_rkbmn", "jenis", "unit_pengusul", "uraian", "volume",
                "satuan", "status", "sptjm", "reviu_apip", "kode_barang",
                "nup", "nama_aset", "keterangan", "dibuat_oleh"])
    async for u in db.perencanaan_usulan.find({}, {"_id": 0}).sort("updated_at", -1):
        w.writerow([
            u.get("tahun_rkbmn"), JENIS_USULAN_RKBMN.get(u.get("jenis"), u.get("jenis")),
            u.get("unit_pengusul"), u.get("uraian"), u.get("volume"), u.get("satuan"),
            STATUS_USULAN_RKBMN.get(u.get("status"), u.get("status")),
            "ya" if u.get("sptjm") else "belum",
            "ya" if u.get("reviu_apip") else "belum",
            u.get("asset_code"), u.get("NUP"), u.get("asset_name"),
            u.get("keterangan"), u.get("created_by"),
        ])
    return Response(content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="register_usulan_rkbmn.csv"'})


@perencanaan_router.post("/perencanaan/usulan")
async def buat_usulan_rkbmn(payload: UsulanRkbmnIn,
                            user: dict = Depends(require_user)):
    """Buat usulan RKBMN baru (status awal draft; aset opsional)."""
    data = payload.model_dump()
    errors = validate_usulan_rkbmn(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    aset_snapshot = {}
    aid = str(data.get("asset_id") or "").strip()
    if aid:
        a = await db.assets.find_one({"id": aid}, _PROJ_ASET)
        if not a:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        aset_snapshot = {"asset_id": a["id"], "asset_code": a.get("asset_code"),
                         "NUP": a.get("NUP"), "asset_name": a.get("asset_name")}
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "tahun_rkbmn": data["tahun_rkbmn"].strip(),
        "jenis": data["jenis"],
        "unit_pengusul": data["unit_pengusul"].strip(),
        "uraian": data["uraian"].strip(),
        "volume": float(data["volume"]),
        "satuan": data["satuan"].strip(),
        **aset_snapshot,
        "status": "draft",
        "sptjm": False,
        "reviu_apip": False,
        "keterangan": str(data.get("keterangan") or "").strip(),
        "riwayat": [{"status": "draft", "tanggal": now,
                     "oleh": user.get("username"), "catatan": ""}],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.perencanaan_usulan.insert_one({**record})
    return record


@perencanaan_router.post("/perencanaan/usulan/{usulan_id}/status")
async def transisi_usulan_rkbmn(usulan_id: str, payload: TransisiRkbmnIn,
                                user: dict = Depends(require_user)):
    """Pindahkan status usulan (anti-race; dikembalikan wajib catatan)."""
    u = await db.perencanaan_usulan.find_one({"id": usulan_id}, {"_id": 0})
    if not u:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    ke = payload.status
    errors = validate_transisi_rkbmn(u, ke, payload.catatan)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    set_fields = {"status": ke, "updated_at": now}
    if payload.sptjm is not None:
        set_fields["sptjm"] = bool(payload.sptjm)
    if payload.reviu_apip is not None:
        set_fields["reviu_apip"] = bool(payload.reviu_apip)
    entri = {"status": ke, "tanggal": now, "oleh": user.get("username"),
             "catatan": str(payload.catatan or "").strip()}
    res = await db.perencanaan_usulan.find_one_and_update(
        {"id": usulan_id, "status": u["status"]},
        {"$set": set_fields, "$push": {"riwayat": entri}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Status usulan berubah di perangkat lain — muat ulang")
    res.update(set_fields)
    return res


@perencanaan_router.delete("/perencanaan/usulan/{usulan_id}")
async def hapus_usulan_rkbmn(usulan_id: str,
                             _admin: dict = Depends(require_admin)):
    """Hapus satu usulan dari register (admin)."""
    res = await db.perencanaan_usulan.delete_one({"id": usulan_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Usulan tidak ditemukan")
    return {"ok": True}
