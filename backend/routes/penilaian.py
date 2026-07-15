"""PENILAIAN — Fase 5 tahap awal: posisi penyusutan aset tetap.

PMK 65/PMK.06/2017 + KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka §5).
Rekap per golongan + daftar telaah (henti susut, tanpa referensi masa
manfaat) dari data aset nyata. Revaluasi & referensi masa manfaat yang
dapat dikelola menyusul sesuai masterplan.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_utils import require_admin, require_user
from db import db
from kodefikasi_utils import GOLONGAN_DEFAULTS
from report_filters import active_asset_filter
from shared_utils import log_audit
from penilaian_utils import (
    MASA_MANFAAT_DEFAULT, rekap_penyusutan, validate_masa_manfaat,
    DAMPAK_MASA_MANFAAT, DOKUMEN_KOREKSI, JENIS_KOREKSI_NILAI,
    STATUS_SAKTI_KOREKSI, baris_csv_koreksi, rekap_koreksi_nilai,
    susun_riwayat_nilai, validate_koreksi_nilai,
    build_asset_revaluasi_projection,
)

penilaian_router = APIRouter()


class MasaManfaatIn(BaseModel):
    kode: str = Field(min_length=5, max_length=5)
    uraian: str = ""
    tahun: int


async def _peta_masa_manfaat():
    """Peta kelompok → tahun: entri satker (DB) menimpa bawaan riset."""
    peta = dict(MASA_MANFAAT_DEFAULT)
    entri = {}
    async for m in db.masa_manfaat.find({}, {"_id": 0}):
        peta[m["kode"]] = int(m["tahun"])
        entri[m["kode"]] = m
    return peta, entri

_PROJ = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_price": 1, "purchase_date": 1, "condition": 1}
_MAKS_BARIS = 500


@penilaian_router.get("/penilaian/masa-manfaat")
async def list_masa_manfaat(_user: dict = Depends(require_user)):
    """Referensi masa manfaat gabungan: entri satker menimpa bawaan riset.

    Bawaan berasal dari riset KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka
    §5); entri satker diinput admin dari lampiran KMK (butir verifikasi
    #11) dan selalu menang.
    """
    _, entri = await _peta_masa_manfaat()
    items = []
    for kode, tahun in sorted(MASA_MANFAAT_DEFAULT.items()):
        if kode not in entri:
            items.append({"kode": kode, "uraian": "", "tahun": tahun,
                          "sumber": "bawaan riset (validasi lampiran KMK)"})
    for m in sorted(entri.values(), key=lambda x: x["kode"]):
        items.append({**m, "sumber": "input satker"})
    items.sort(key=lambda x: x["kode"])
    return {"items": items, "jumlah": len(items)}


@penilaian_router.post("/penilaian/masa-manfaat")
async def upsert_masa_manfaat(payload: MasaManfaatIn,
                              _admin: dict = Depends(require_admin)):
    """Tambah/ubah masa manfaat satu kelompok (admin; menimpa bawaan)."""
    errors = validate_masa_manfaat(payload.kode, payload.tahun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    kode = payload.kode.strip()
    await db.masa_manfaat.update_one(
        {"kode": kode},
        {"$set": {"kode": kode, "uraian": str(payload.uraian or "").strip(),
                  "tahun": int(payload.tahun), "updated_at": now},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return {"ok": True, "kode": kode, "tahun": int(payload.tahun)}


@penilaian_router.delete("/penilaian/masa-manfaat/{kode}")
async def hapus_masa_manfaat(kode: str, _admin: dict = Depends(require_admin)):
    """Hapus entri satker (kembali ke bawaan riset bila ada)."""
    res = await db.masa_manfaat.delete_one({"kode": kode.strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404,
                            detail="Entri satker tidak ditemukan (bawaan riset tidak bisa dihapus)")
    return {"ok": True, "kode": kode.strip()}


@penilaian_router.get("/penilaian/penyusutan")
async def posisi_penyusutan(
    per_tanggal: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Posisi penyusutan per golongan + daftar telaah (per tanggal)."""
    if not per_tanggal:
        per_tanggal = datetime.now(timezone.utc).date().isoformat()
    uraian = {k: u for k, u in GOLONGAN_DEFAULTS}
    async for k in db.kodefikasi.find({"level": 1}, {"_id": 0, "kode": 1, "uraian": 1}):
        if k.get("uraian"):
            uraian[k["kode"]] = k["uraian"]
    peta, _ = await _peta_masa_manfaat()
    # Rekap penyusutan hanya atas aset yang MASIH dimiliki — aset ber-SK
    # penghapusan (#234) dikecualikan agar nilai buku tidak lebih saji (§5A).
    assets = [a async for a in db.assets.find(active_asset_filter(), _PROJ)]
    # Aset rusak berat baru henti-susut bila TELAH diusulkan penghapusan
    # (reklas keluar aset tetap, PMK 65/2017); usulan aktif = belum ditolak.
    diusulkan_ids = set()
    async for u in db.usulan_penghapusan.find(
            {"status": {"$ne": "ditolak"}}, {"_id": 0, "asset_id": 1}):
        if u.get("asset_id"):
            diusulkan_ids.add(u["asset_id"])
    hasil = rekap_penyusutan(assets, per_tanggal, peta=peta,
                             uraian_golongan=uraian, diusulkan_ids=diusulkan_ids)
    dipangkas = {
        "henti": len(hasil["henti"]) > _MAKS_BARIS,
        "tanpa_referensi": len(hasil["tanpa_referensi"]) > _MAKS_BARIS,
    }
    hasil["henti"] = hasil["henti"][:_MAKS_BARIS]
    hasil["tanpa_referensi"] = hasil["tanpa_referensi"][:_MAKS_BARIS]
    hasil["dipangkas"] = dipangkas
    hasil["per_tanggal"] = per_tanggal
    hasil["referensi_masa_manfaat"] = peta
    hasil["catatan"] = (
        "Garis lurus tanpa residu, semesteran, konvensi semester penuh "
        "(PMK 65/2017); posisi memuat semester yang sudah berakhir. Masa "
        "manfaat per kelompok (KMK 295/2019 jo. 266/2023) — kelompok tanpa "
        "referensi tidak ditebak dan tampil di daftar telaah."
    )
    return hasil


class KoreksiNilaiIn(BaseModel):
    asset_id: str = Field(min_length=1)
    jenis: str
    jenis_dokumen: str
    nomor_dokumen: str = Field(min_length=1)
    tanggal_dokumen: str = Field(min_length=10, max_length=10)
    nilai_lama: float = Field(ge=0)
    nilai_baru: float = Field(ge=0)
    penilai_pelaksana: str = ""
    dampak_masa_manfaat: str = "tetap"
    masa_manfaat_semester: int = 0
    catatan: str = ""


@penilaian_router.get("/penilaian/koreksi")
async def list_koreksi_nilai(_user: dict = Depends(require_user)):
    """Register koreksi nilai & hasil penilaian (terbaru dulu)."""
    items = [k async for k in db.penilaian_koreksi.find({}, {"_id": 0})
             .sort("tanggal_dokumen", -1).limit(500)]
    return {"items": items, "ringkasan": rekap_koreksi_nilai(items),
            "label_jenis": JENIS_KOREKSI_NILAI,
            "label_dokumen": DOKUMEN_KOREKSI,
            "label_dampak": DAMPAK_MASA_MANFAAT,
            "label_sakti": STATUS_SAKTI_KOREKSI,
            "catatan": (
                "Register pendamping (PMK 99/2024 + PMK 118/2017) — AMAN "
                "bukan penilai dan tidak menghitung nilai wajar; pencatatan "
                "resmi di SAKTI (koreksi revaluasi di-push pusat, satker "
                "memverifikasi vs LHIP); penilaian tujuan tertentu tidak "
                "mengubah nilai buku.")}


@penilaian_router.get("/penilaian/koreksi/export")
async def export_koreksi_nilai(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh register koreksi nilai/hasil penilaian (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    koreksi = [k async for k in db.penilaian_koreksi.find({}, {"_id": 0})
               .sort("tanggal_dokumen", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_koreksi(koreksi):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_koreksi_nilai.csv"'})


@penilaian_router.get("/penilaian/riwayat-nilai/{asset_id}")
async def riwayat_nilai_aset(asset_id: str, _user: dict = Depends(require_user)):
    """Jejak kronologis nilai satu aset (perolehan → koreksi/revaluasi).

    Read-only: menggabungkan nilai perolehan master aset dengan peristiwa
    di register koreksi nilai (#184). Nilai buku terkini mengikuti koreksi
    non-informasional terakhir.
    """
    asset = await db.assets.find_one(
        {"id": asset_id},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "purchase_date": 1, "purchase_price": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    koreksi = [k async for k in db.penilaian_koreksi.find(
        {"asset_id": asset_id}, {"_id": 0})]
    riwayat = susun_riwayat_nilai(asset, koreksi)
    return {"aset": asset, **riwayat,
            "label_jenis": JENIS_KOREKSI_NILAI,
            "label_dokumen": DOKUMEN_KOREKSI,
            "label_sakti": STATUS_SAKTI_KOREKSI,
            "catatan": ("Read-only — nilai buku terkini indikatif dari koreksi "
                        "non-informasional terakhir; angka resmi tetap di SAKTI.")}


@penilaian_router.post("/penilaian/koreksi")
async def catat_koreksi_nilai(payload: KoreksiNilaiIn,
                              user: dict = Depends(require_user)):
    """Catat satu peristiwa nilai untuk satu aset (status SAKTI: belum)."""
    data = payload.model_dump()
    errors = validate_koreksi_nilai(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "asset_id": asset["id"],
        "asset_code": asset.get("asset_code"),
        "NUP": asset.get("NUP"),
        "asset_name": asset.get("asset_name"),
        "jenis": data["jenis"],
        "jenis_dokumen": data["jenis_dokumen"],
        "nomor_dokumen": data["nomor_dokumen"].strip(),
        "tanggal_dokumen": data["tanggal_dokumen"].strip()[:10],
        "nilai_lama": float(data["nilai_lama"]),
        "nilai_baru": float(data["nilai_baru"]),
        "selisih": float(data["nilai_baru"]) - float(data["nilai_lama"]),
        "penilai_pelaksana": str(data.get("penilai_pelaksana") or "").strip(),
        "dampak_masa_manfaat": data["dampak_masa_manfaat"],
        "masa_manfaat_semester": int(data.get("masa_manfaat_semester") or 0),
        "status_sakti": "belum_dicatat",
        "catatan": str(data.get("catatan") or "").strip(),
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.penilaian_koreksi.insert_one({**record})
    return record


async def _proyeksi_master_revaluasi(koreksi: dict, oleh: str) -> bool:
    """Proyeksikan master aset saat koreksi/revaluasi nilai FINAL (tercatat SAKTI)
    — Prinsip 3 Bab 5. Best-effort & idempoten: nilai sudah tercatat di register
    `penilaian_koreksi` (jurnal), jadi kegagalan/no-op proyeksi TIDAK menggagalkan
    transisi SAKTI. `$inc version` mem-bust cache/ETag + memicu OCC 409 pada form
    edit usang. `tandai_tercatat_sakti` hanya bertransisi sekali (guard
    status_sakti) → proyeksi berjalan maksimal sekali per koreksi; koreksi
    berikutnya menimpa `nilai_wajar_terakhir` (revaluasi terbaru menang).
    """
    asset_id = koreksi.get("asset_id")
    if not asset_id:
        return False
    now = datetime.now(timezone.utc).isoformat()
    proj = build_asset_revaluasi_projection(koreksi, now)
    updated = await db.assets.find_one_and_update(
        {"id": asset_id},
        {"$set": proj, "$inc": {"version": 1}},
        projection={"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1,
                    "asset_name": 1, "NUP": 1},
        return_document=True,
    )
    if not updated:
        return False
    await log_audit(
        "revaluasi", updated.get("activity_id", ""), updated.get("id", ""),
        updated.get("asset_code", ""), updated.get("asset_name", ""),
        username=oleh,
        detail=(f"Nilai wajar diproyeksikan ke master: "
                f"Rp{int(proj['nilai_wajar_terakhir'])}"
                f" (dok {proj['revaluasi']['nomor_dokumen']})").strip(),
        nup=updated.get("NUP", ""),
    )
    return True


@penilaian_router.post("/penilaian/koreksi/{koreksi_id}/sakti")
async def tandai_tercatat_sakti(koreksi_id: str,
                                user: dict = Depends(require_user)):
    """Tandai koreksi sudah divalidasi & di-approve di SAKTI (anti-race).

    Saat transisi BERHASIL, PROYEKSIKAN nilai wajar ke master aset
    (`nilai_wajar_terakhir` + jejak revaluasi, #254) — best-effort, tak
    menggagalkan transisi bila aset sudah tak ada.
    """
    now = datetime.now(timezone.utc).isoformat()
    res = await db.penilaian_koreksi.find_one_and_update(
        {"id": koreksi_id, "status_sakti": "belum_dicatat"},
        {"$set": {"status_sakti": "tercatat_sakti", "updated_at": now,
                  "sakti_oleh": user.get("username"), "sakti_tanggal": now[:10]}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Koreksi tidak ditemukan atau sudah ditandai tercatat")
    res["status_sakti"] = "tercatat_sakti"
    await _proyeksi_master_revaluasi(res, user.get("username"))
    return res


@penilaian_router.delete("/penilaian/koreksi/{koreksi_id}")
async def hapus_koreksi_nilai(koreksi_id: str,
                              _admin: dict = Depends(require_admin)):
    """Hapus satu catatan koreksi (admin)."""
    res = await db.penilaian_koreksi.delete_one({"id": koreksi_id})
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Koreksi tidak ditemukan")
    return {"ok": True}
