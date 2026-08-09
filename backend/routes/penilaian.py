"""PENILAIAN — Fase 5 tahap awal: posisi penyusutan aset tetap.

PMK 65/PMK.06/2017 + KMK 295/KM.6/2019 jo. 266/KM.6/2023 (pustaka §5).
Rekap per golongan + daftar telaah (henti susut, tanpa referensi masa
manfaat) dari data aset nyata. Referensi masa manfaat dapat dikelola
(GET/POST/DELETE masa-manfaat); koreksi/revaluasi nilai tercatat lewat
register koreksi dan diproyeksikan ke `nilai_wajar_terakhir` aset.
"""
import math
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from auth_utils import require_admin, require_user, require_writer
from db import db
from kodefikasi_utils import GOLONGAN_DEFAULTS
from report_filters import active_asset_filter
from shared_utils import (
    filter_aset_perhitungan, kode_satker_user, log_audit,
    pastikan_akses_aset, scope_query_aset, scope_query_field_satker,
    ensure_activity_not_sealed)
from penilaian_utils import (
    MASA_MANFAAT_DEFAULT, rekap_penyusutan, validate_masa_manfaat,
    DAMPAK_MASA_MANFAAT, DOKUMEN_KOREKSI, JENIS_KOREKSI_NILAI,
    STATUS_SAKTI_KOREKSI, baris_csv_koreksi, posisi_nilai_aset,
    rekap_koreksi_nilai, susun_riwayat_nilai, validate_koreksi_nilai,
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
         "purchase_price": 1, "purchase_date": 1, "condition": 1,
         "inventory_status": 1, "nilai_wajar_terakhir": 1, "revaluasi": 1,
         "masa_manfaat_tambah_tahun": 1, "masa_manfaat_override_semester": 1}
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
        # Bedakan asal entri: dari impor SIMAN (otomatis "SIMAN menang") vs
        # input admin satker — agar transparan di UI.
        if m.get("sumber") == "siman":
            sumber = f"dari SIMAN · {int(m.get('observasi') or 0)} observasi"
        else:
            sumber = "input satker"
        items.append({**m, "sumber": sumber})
    items.sort(key=lambda x: x["kode"])
    return {"items": items, "jumlah": len(items)}


def _wajib_super_admin(user: dict) -> None:
    """Referensi masa manfaat GLOBAL (KMK berlaku nasional; satu baris per
    kelompok, dibaca semua satker) — perubahan manual dibatasi super-admin
    pusat (audit P4 #7): dulu admin satker mana pun bisa menyetel "tahun=1"
    dan seketika penyusutan SEMUA satker berubah tanpa jejak."""
    from shared_utils import kode_satker_user
    if kode_satker_user(user):
        raise HTTPException(status_code=403, detail=(
            "Referensi masa manfaat berlaku untuk SEMUA satker — hanya "
            "super-admin pusat yang boleh mengubah/menghapusnya. Impor SIMAN "
            "tetap memperbarui referensi secara otomatis."))


@penilaian_router.post("/penilaian/masa-manfaat")
async def upsert_masa_manfaat(payload: MasaManfaatIn,
                              admin: dict = Depends(require_admin)):
    """Tambah/ubah masa manfaat satu kelompok (super-admin; menimpa bawaan)."""
    _wajib_super_admin(admin)
    errors = validate_masa_manfaat(payload.kode, payload.tahun)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    kode = payload.kode.strip()
    await db.masa_manfaat.update_one(
        {"kode": kode},
        {"$set": {"kode": kode, "uraian": str(payload.uraian or "").strip(),
                  "tahun": int(payload.tahun), "sumber": "input satker",
                  "updated_at": now},
         "$unset": {"observasi": "", "updated_by": ""},
         "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    await log_audit("masa_manfaat_upsert", "",
                    username=admin.get("username", "system"),
                    detail=f"Masa manfaat kelompok {kode} = {int(payload.tahun)} tahun")
    return {"ok": True, "kode": kode, "tahun": int(payload.tahun)}


@penilaian_router.delete("/penilaian/masa-manfaat/{kode}")
async def hapus_masa_manfaat(kode: str, admin: dict = Depends(require_admin)):
    """Hapus entri referensi (super-admin; kembali ke bawaan riset bila ada)."""
    _wajib_super_admin(admin)
    res = await db.masa_manfaat.delete_one({"kode": kode.strip()})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404,
                            detail="Entri tidak ditemukan (bawaan riset tidak bisa dihapus)")
    await log_audit("masa_manfaat_hapus", "",
                    username=admin.get("username", "system"),
                    detail=f"Hapus referensi masa manfaat kelompok {kode.strip()}")
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
    assets = [a async for a in db.assets.find(
        await filter_aset_perhitungan(
            await scope_query_aset(_user, active_asset_filter())), _PROJ)]
    # Aset rusak berat baru henti-susut bila TELAH diusulkan penghapusan
    # (reklas keluar aset tetap, PMK 65/2017); usulan aktif = belum ditolak.
    diusulkan_ids = set()
    async for u in db.usulan_penghapusan.find(
            scope_query_field_satker(_user, {"status": {"$ne": "ditolak"}}),
            {"_id": 0, "asset_id": 1}):
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
        "(PMK 65/2017); posisi memuat semester yang sudah berakhir — posisi "
        "tepat pada 30 Jun/31 Des memuat semester yang ditutup hari itu. Masa "
        "manfaat per kelompok (KMK 295/2019 jo. 266/2023) — kelompok tanpa "
        "referensi tidak ditebak dan tampil di daftar telaah. Aset yang sudah "
        "direvaluasi final disusutkan atas NILAI REVALUASI dengan masa manfaat "
        "di-reset penuh sejak tanggal revaluasi (PMK 118/2017 jo. 57/2018 jo. "
        "107/2019; Bultek SAP 18) — akumulasi lama dieliminasi."
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

    @field_validator("nilai_lama", "nilai_baru")
    @classmethod
    def _terhingga(cls, v: float) -> float:
        # Token JSON Infinity LOLOS ge=0 (inf >= 0 True; audit P4 #3) —
        # lalu meracuni nilai_wajar_terakhir master aset (nilai buku jadi 0
        # diam-diam) dan mematahkan int() saat penandaan SAKTI.
        if not math.isfinite(v):
            raise ValueError("nilai harus angka terhingga")
        return v


@penilaian_router.get("/penilaian/koreksi")
async def list_koreksi_nilai(_user: dict = Depends(require_user)):
    """Register koreksi nilai & hasil penilaian (terbaru dulu)."""
    items = [k async for k in db.penilaian_koreksi.find(
                 scope_query_field_satker(_user), {"_id": 0})
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

    koreksi = [k async for k in db.penilaian_koreksi.find(
                   scope_query_field_satker(_user), {"_id": 0})
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
async def riwayat_nilai_aset(
    asset_id: str,
    per_tanggal: str = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    _user: dict = Depends(require_user),
):
    """Jejak nilai satu aset LENGKAP: perolehan → kapitalisasi/koreksi/
    revaluasi (register + jurnal Buku Barang per NUP) → posisi penyusutan
    → NILAI BUKU per tanggal.

    Dirombak dari versi lama yang hanya membaca register koreksi: kini
    jurnal `mutasi_bmn` (kapitalisasi 202, terapan SIMAN 204/205, perolehan
    100/101, penghapusan 301, dll.) ikut tampil, dan penyusutan dihitung
    PER ASET dengan mesin yang sama dengan Laporan Penyusutan — dulu angka
    penyusutan hanya pernah tersaji agregat per golongan.
    """
    if not per_tanggal:
        per_tanggal = datetime.now(timezone.utc).date().isoformat()
    asset = await db.assets.find_one(
        {"id": asset_id}, {**_PROJ, "activity_id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, asset)
    koreksi = [k async for k in db.penilaian_koreksi.find(
        {"asset_id": asset_id}, {"_id": 0})]
    mutasi = [m async for m in db.mutasi_bmn.find(
        {"asset_id": asset_id}, {"_id": 0}).sort("tanggal_buku", 1)]
    # Henti-susut hanya bila rusak berat/hilang DAN telah diusulkan hapus —
    # kriteria yang sama dengan rekap agregat (PMK 65/2017).
    diusulkan = await db.usulan_penghapusan.find_one(
        {"asset_id": asset_id, "status": {"$ne": "ditolak"}}, {"_id": 1})
    peta, _ = await _peta_masa_manfaat()
    posisi = posisi_nilai_aset(asset, per_tanggal, peta=peta,
                               diusulkan=diusulkan is not None)
    riwayat = susun_riwayat_nilai(asset, koreksi, mutasi)
    return {"aset": asset, **riwayat, "posisi": posisi,
            "label_jenis": JENIS_KOREKSI_NILAI,
            "label_dokumen": DOKUMEN_KOREKSI,
            "label_sakti": STATUS_SAKTI_KOREKSI,
            "catatan": ("Read-only — nilai buku = dasar penyusutan − akumulasi "
                        "(mesin yang sama dengan Laporan Penyusutan); angka "
                        "resmi tetap di SAKTI.")}


@penilaian_router.post("/penilaian/koreksi")
async def catat_koreksi_nilai(payload: KoreksiNilaiIn,
                              user: dict = Depends(require_writer)):
    """Catat satu peristiwa nilai untuk satu aset (status SAKTI: belum)."""
    data = payload.model_dump()
    errors = validate_koreksi_nilai(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    asset = await db.assets.find_one(
        {"id": data["asset_id"]},
        {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1,
         "activity_id": 1})
    if not asset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(user, asset)
    now = datetime.now(timezone.utc).isoformat()
    # Super-admin lintas-satker: derivasi dari kegiatan induk aset — stempel
    # "" akan lolos scope_query_field_satker dan tampil di SEMUA satker.
    from shared_utils import kode_satker_efektif_dari_aset
    _ks = await kode_satker_efektif_dari_aset(user, [asset["id"]])
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": _ks,
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
    # Kunci kegiatan disahkan (423) berlaku juga untuk proyeksi revaluasi —
    # semua jalur mutasi aset wajib melewatinya (shared_utils).
    _a = await db.assets.find_one({"id": asset_id},
                                  {"_id": 0, "activity_id": 1})
    if _a:
        await ensure_activity_not_sealed(_a.get("activity_id"))
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
                                request: Request = None,
                                user: dict = Depends(require_writer)):
    """Tandai koreksi sudah divalidasi & di-approve di SAKTI (anti-race).

    Saat transisi BERHASIL, PROYEKSIKAN nilai wajar ke master aset
    (`nilai_wajar_terakhir` + jejak revaluasi, #254) — best-effort, tak
    menggagalkan transisi bila aset sudah tak ada.

    ASET-GERBANG-2: finalisasi menulis jurnal 204/205 + proyeksi master —
    saat gerbang wajib-persetujuan aktif, HTTP langsung ditolak dan jalur
    sahnya lewat permohonan `revaluasi_final` (routes/aset_permohonan.py,
    pemanggilan internal request=None).
    """
    from routes.mutasi_bmn import _gerbang_wajib_persetujuan_aset
    await _gerbang_wajib_persetujuan_aset(request)
    now = datetime.now(timezone.utc).isoformat()
    res = await db.penilaian_koreksi.find_one_and_update(
        scope_query_field_satker(
            user, {"id": koreksi_id, "status_sakti": "belum_dicatat"}),
        {"$set": {"status_sakti": "tercatat_sakti", "updated_at": now,
                  "sakti_oleh": user.get("username"), "sakti_tanggal": now[:10]}},
        projection={"_id": 0},
    )
    if not res:
        raise HTTPException(
            status_code=409,
            detail="Koreksi tidak ditemukan atau sudah ditandai tercatat")
    res["status_sakti"] = "tercatat_sakti"
    # "Penilaian tujuan tertentu" bersifat INFORMASIONAL — modul ini sendiri
    # mengecualikannya dari nilai buku (rekap_koreksi_nilai/susun_riwayat_
    # nilai) → jangan proyeksikan ke master maupun jurnalkan rupiahnya.
    #
    # Kompensasi CAS (audit P4 #4, pola pemeliharaan.py posting_kapitalisasi):
    # tiga tulisan berurutan (register → master aset → jurnal) terjadi SETELAH
    # penanda status terkunci — kegagalan di tengah dulu meninggalkan register
    # "tercatat_sakti" TANPA jurnal 204/205, dan CAS menolak pengulangan
    # selamanya. Kini penanda dilepas lagi agar transisi bisa diulang.
    try:
        informasional = res.get("jenis") == "penilaian_tujuan_tertentu"
        if not informasional:
            await _proyeksi_master_revaluasi(res, user.get("username"))
        # Jurnal Buku Barang (G7, REVIEW-9 R3): revaluasi FINAL → 204 (nilai
        # bertambah) / 205 (nilai berkurang), magnitudo positif + jumlah 0
        # (kuantitas barang tidak berubah). Best-effort + anti-ganda via ref_id.
        selisih = float(res.get("selisih") or 0)
        if selisih and not informasional:
            from shared_utils import catat_mutasi_bmn
            aset = await db.assets.find_one(
                {"id": res.get("asset_id")},
                {"_id": 0, "asset_code": 1, "NUP": 1})
            await catat_mutasi_bmn({
                "asset_id": res.get("asset_id"),
                "kode_transaksi": "204" if selisih > 0 else "205",
                "kode_barang": str((aset or res).get("asset_code") or ""),
                "nup": str((aset or res).get("NUP") or ""),
                "tanggal_buku": (str(res.get("tanggal_dokumen") or "").strip()[:10]
                                 or now[:10]),
                "jumlah": 0, "nilai": abs(selisih),
                "sumber_modul": "penilaian", "ref_id": res.get("id"),
                "keterangan": (f"Revaluasi/koreksi nilai {res.get('jenis') or ''} — "
                               f"dok {res.get('nomor_dokumen') or '-'} "
                               f"(Rp{int(res.get('nilai_lama') or 0):,} → "
                               f"Rp{int(res.get('nilai_baru') or 0):,})").strip(),
                "oleh": user.get("username", "system")})
    except Exception:
        await db.penilaian_koreksi.update_one(
            {"id": koreksi_id},
            {"$set": {"status_sakti": "belum_dicatat",
                      "updated_at": datetime.now(timezone.utc).isoformat()},
             "$unset": {"sakti_oleh": "", "sakti_tanggal": ""}})
        raise
    return res


@penilaian_router.delete("/penilaian/koreksi/{koreksi_id}")
async def hapus_koreksi_nilai(koreksi_id: str,
                              _admin: dict = Depends(require_admin)):
    """Hapus satu catatan koreksi (admin, dalam lingkup satker).

    Koreksi FINAL (tercatat_sakti) TIDAK boleh dihapus — jurnal 204/205 dan
    proyeksi master sudah terbit (append-only) sehingga hapus-lalu-buat-ulang
    menggandakan mutasi rupiah di Buku Barang (pola sama dengan larangan
    hapus catatan pemeliharaan yang sudah berjurnal 202)."""
    final = await db.penilaian_koreksi.find_one(
        scope_query_field_satker(
            _admin, {"id": koreksi_id, "status_sakti": "tercatat_sakti"}),
        {"_id": 1})
    if final:
        raise HTTPException(
            status_code=409,
            detail="Koreksi sudah tercatat SAKTI & berjurnal — tidak dapat "
                   "dihapus; buat koreksi baru sebagai pembalik bila perlu.")
    res = await db.penilaian_koreksi.delete_one(
        scope_query_field_satker(_admin, {"id": koreksi_id}))
    if not res.deleted_count:
        raise HTTPException(status_code=404, detail="Koreksi tidak ditemukan")
    return {"ok": True}
