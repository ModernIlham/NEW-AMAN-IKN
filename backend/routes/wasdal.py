"""WASDAL — dasbor pemantauan tingkat KPB (PMK 207/PMK.06/2021, pustaka §8).

Mesin aturan ringan atas register yang sudah ada (aset, pemanfaatan,
usulan penghapusan, pemindahtanganan, pemeliharaan) → temuan per lima
objek pemantauan + register penertiban ber-tenggat 15 hari kerja. Bahan
pra-isi laporan wasdal semesteran; kanal resmi pelaporan tetap Modul
Wasdal SIMAN v2. Pemantauan insidentil ber-BA (isi + PDF + lampiran)
dikelola lewat register tersendiri di modul ini.
"""
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request, UploadFile,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field

from auth_utils import (
    require_admin, require_user, require_user_or_query_token, require_writer,
)
from db import db, fs_bucket
from shared_utils import kode_satker_user, scope_query_field_satker, pastikan_akses_dok_satker, blok_ttd_kpb_titik, delete_document_from_gridfs, get_document_from_gridfs
from wasdal_utils import (
    AMBANG_BERLARUT_HARI, JENIS_TEMUAN, OBJEK_WASDAL, PEMICU_INSIDENTIL,
    STATUS_INSIDENTIL, SUMBER_PENERTIBAN, STATUS_PENERTIBAN,
    TENGGAT_HARI_KERJA, TENGGAT_LAPOR_HK, TENGGAT_PELAKSANAAN_HK,
    baris_csv_insidentil, baris_csv_penertiban, info_tenggat_insidentil,
    periode_wasdal, rekap_insidentil,
    rekap_penertiban, rekap_wasdal, status_tenggat_penertiban,
    susun_temuan, tambah_hari_kerja, validate_ba_insidentil,
    validate_insidentil, validate_lapor_insidentil, validate_penertiban,
    validate_selesai_penertiban,
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


async def _data_pemantauan(ambang_hari: int, user=None):
    """Kumpulkan register → (periode, per_objek, rekap, total_aset).
    Ter-scope satker `user` bila diberikan (M-SCOPE) — pemanggil endpoint
    WAJIB meneruskan user agar rekap tidak mencampur satker lain."""
    from shared_utils import scope_query_aset
    today_iso = datetime.now(timezone.utc).date().isoformat()
    periode = periode_wasdal(today_iso)
    tahun = periode["tahun"]

    from shared_utils import filter_aset_perhitungan
    q_aset = await scope_query_aset(user, {}) if user is not None else {}
    q_aset = await filter_aset_perhitungan(q_aset)
    assets = [a async for a in db.assets.find(q_aset, _PROJ_ASET)]
    _sq = (lambda q: scope_query_field_satker(user, q)) if user is not None else (lambda q: q)
    pemanfaatan = [p async for p in db.pemanfaatan.find(
        _sq({}), {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "asset_name": 1,
             "berakhir": 1, "mulai": 1, "nomor_persetujuan": 1,
             "nomor_perjanjian": 1, "ntpn": 1,
             # field kontribusi utk deteksi tunggakan PNBP (integrasi Wasdal)
             "kontribusi_tahunan": 1, "kontribusi": 1})]
    # Integrasi Pengamanan → Wasdal: polis asuransi BMN yang masa berlakunya
    # sudah lewat menjadi temuan objek pengamanan & pemeliharaan.
    polis = [p async for p in db.pengamanan_polis.find(
        _sq({}), {"_id": 0, "id": 1, "asset_id": 1, "asset_name": 1,
                  "nama_aset": 1, "nomor_polis": 1, "penanggung": 1,
                  "berakhir": 1})]
    usulan_hapus = [u async for u in db.usulan_penghapusan.find(
        _sq({"status": {"$in": ["diusulkan", "diproses"]}}),
        {"_id": 0, "id": 1, "asset_id": 1, "asset_name": 1, "status": 1,
         "created_at": 1})]
    usulan_pt = [u async for u in db.pemindahtanganan.find(
        _sq({"status": "disetujui"}),
        {"_id": 0, "id": 1, "bentuk": 1, "pihak": 1, "status": 1,
         "tanggal_persetujuan": 1})]
    pemeliharaan = [r async for r in db.pemeliharaan.find(
        {"tanggal": {"$gte": f"{tahun}-01-01", "$lte": f"{tahun}-12-31"}},
        {"_id": 0, "asset_id": 1, "tanggal": 1})]
    # Integrasi Master Pegawai → Wasdal: pemegang berisiko (keluar/pensiun/
    # kontrak habis) yang masih memegang aset = temuan objek Penggunaan
    # (deteksi sama dengan /pegawai/perlu-serah-terima).
    from routes.pegawai import _jumlah_aset_per_nip
    pegawai = [p async for p in db.pegawai.find(
        _sq({}), {"_id": 0, "id": 1, "nama": 1, "nip": 1, "status": 1,
                  "tgl_selesai_kontrak": 1})]
    peta_aset_nip = await _jumlah_aset_per_nip(user)
    # Integrasi Pengamanan → Wasdal: dokumen kepemilikan (STNK/pajak/IMB)
    # yang masa berlakunya lewat = temuan objek pengamanan & pemeliharaan.
    dokumen = [d async for d in db.pengamanan_dokumen.find(
        _sq({}), {"_id": 0, "id": 1, "asset_id": 1, "asset_code": 1,
                  "NUP": 1, "asset_name": 1, "jenis": 1, "nomor": 1,
                  "berlaku_sampai": 1})]
    # Integrasi Pemusnahan → Wasdal: aset ber-BA pemusnahan tanpa SK
    # penghapusan = fisik lenyap tapi masih tersaji di neraca (lebih saji).
    pemusnahan = [r async for r in db.pemusnahan.find(
        _sq({}), {"_id": 0, "aset": 1, "nomor_ba": 1, "tanggal_ba": 1})]
    aset_ber_sk = {u["asset_id"] async for u in db.usulan_penghapusan.find(
        _sq({"status": "sk_terbit"}), {"_id": 0, "asset_id": 1})
        if u.get("asset_id")}
    # Integrasi Pengadaan → Wasdal: perolehan berdokumen sumber kurang
    # (BAST/kontrak/SP2D tercecer) = temuan objek penatausahaan.
    pengadaan = [p async for p in db.pengadaan.find(
        _sq({}), {"_id": 0, "id": 1, "jenis": 1, "nomor_bast": 1,
                  "tanggal_bast": 1, "pihak": 1, "dokumen": 1})]
    # Integrasi Persediaan → Wasdal: opname semesteran belum dilakukan +
    # layer kedaluwarsa masih tercatat = temuan objek penatausahaan.
    from persediaan_utils import tanggal_wib
    persediaan = [p async for p in db.persediaan.find(
        {}, {"_id": 0, "id": 1, "kode_barang": 1, "nup": 1,
             "nama_barang": 1, "batches": 1})]
    opname_doc = await db.transaksi_persediaan.find_one(
        {"jenis": "opname"}, {"_id": 0, "timestamp": 1},
        sort=[("timestamp", -1)])
    tanggal_opname = tanggal_wib((opname_doc or {}).get("timestamp"))
    # Integrasi register kasus Pengamanan → Wasdal: kasus AKTIF (belum
    # selesai) membuat asetnya tampil sebagai temuan sengketa meski master
    # belum menandai (read-side join — master tidak dimutasi).
    kasus_aktif = {}
    async for kk in db.pengamanan_kasus.find(
            _sq({"status": {"$ne": "selesai"}}),
            {"_id": 0, "asset_id": 1, "kategori": 1, "pihak_lawan": 1,
             "nomor_perkara": 1}):
        if kk.get("asset_id"):
            kasus_aktif[kk["asset_id"]] = kk

    per_objek = susun_temuan(assets, pemanfaatan, usulan_hapus, usulan_pt,
                             pemeliharaan, today_iso, ambang_hari, polis=polis,
                             pegawai=pegawai, jumlah_aset_per_nip=peta_aset_nip,
                             dokumen=dokumen, pemusnahan=pemusnahan,
                             aset_ber_sk=aset_ber_sk, pengadaan=pengadaan,
                             persediaan=persediaan,
                             tanggal_opname_terakhir=tanggal_opname,
                             kasus_aktif=kasus_aktif)
    return periode, per_objek, rekap_wasdal(per_objek), len(assets)


@wasdal_router.get("/wasdal/pemantauan")
async def pemantauan_wasdal(
    ambang_hari: int = Query(AMBANG_BERLARUT_HARI, ge=1, le=730),
    _user: dict = Depends(require_user),
):
    """Temuan pemantauan per objek wasdal + rekap + periode berjalan."""
    periode, per_objek, rekap, total_aset = await _data_pemantauan(ambang_hari, _user)
    # Ringkasan register Pengamanan & Penggunaan (temuan review #12 — dulu
    # wasdal tak membaca kedua register itu). Additif: UI lama tetap jalan.
    lintas_modul = {
        "kasus_pengamanan_terbuka": await db.pengamanan_kasus.count_documents(
            {"status": {"$ne": "selesai"}}),
        "polis_asuransi": await db.pengamanan_polis.count_documents({}),
        "sk_psp": await db.psp.count_documents({}),
        "proses_penggunaan_aktif": await db.penggunaan_proses.count_documents(
            {"status": {"$nin": ["dihapus_dibukukan", "berakhir", "ditolak"]}}),
        "bmn_idle_aktif": await db.bmn_idle.count_documents(
            {"status": {"$in": ["klarifikasi", "usul_serah"]}}),
        # BAST penggunaan sementara yang jangka waktunya sudah lewat —
        # barang mestinya sudah kembali (tindak lanjut manual/pengembalian).
        "bast_sementara_lewat_tenggat": await db.bast_serah_terima.count_documents(
            {"jenis": "penggunaan_sementara",
             "jangka_sampai": {"$gt": "", "$lt":
                               datetime.now(timezone.utc).date().isoformat()}}),
    }
    return {
        "periode": periode,
        "rekap": rekap,
        "lintas_modul": lintas_modul,
        "label_lintas_modul": {
            "kasus_pengamanan_terbuka": "Kasus pengamanan belum selesai",
            "polis_asuransi": "Polis asuransi BMN tercatat",
            "sk_psp": "SK Penetapan Status Penggunaan",
            "proses_penggunaan_aktif": "Tiket alih status/penggunaan aktif",
            "bmn_idle_aktif": "Tiket BMN idle aktif",
            "bast_sementara_lewat_tenggat":
                "BAST penggunaan sementara lewat tenggat kembali",
        },
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
    items = [t async for t in db.penertiban.find(scope_query_field_satker(_user), {"_id": 0})
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


@wasdal_router.get("/wasdal/penertiban/export")
async def export_penertiban(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh register penertiban wasdal (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [t async for t in db.penertiban.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("created_at", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_penertiban(items, today_iso):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_penertiban_wasdal.csv"'})


@wasdal_router.post("/wasdal/penertiban")
async def catat_penertiban(payload: PenertibanIn,
                           user: dict = Depends(require_writer)):
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
        "kode_satker": kode_satker_user(user),
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


class InsidentilIn(BaseModel):
    pemicu: str
    tanggal_mulai: str = Field(min_length=10, max_length=10)
    objek: str = ""                 # salah satu 5 objek pemantauan (opsional)
    uraian: str = Field(min_length=1)
    lokasi: str = ""


class BaInsidentilIn(BaseModel):
    nomor_ba: str = Field(min_length=1)
    tanggal_ba: str = Field(min_length=10, max_length=10)
    hasil: str = Field(min_length=1)


class LaporInsidentilIn(BaseModel):
    tanggal_lapor: str = Field(min_length=10, max_length=10)
    keterangan: str = ""


@wasdal_router.get("/wasdal/insidentil")
async def daftar_insidentil(_user: dict = Depends(require_user)):
    """Register pemantauan insidentil + tenggat aktif per tiket + rekap."""
    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [t async for t in db.pemantauan_insidentil.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("created_at", -1).limit(500)]
    for t in items:
        t["info_tenggat"] = info_tenggat_insidentil(t, today_iso)
    return {"items": items, "ringkasan": rekap_insidentil(items, today_iso),
            "label_pemicu": PEMICU_INSIDENTIL,
            "label_status": STATUS_INSIDENTIL,
            "label_objek": OBJEK_WASDAL,
            "tenggat_pelaksanaan_hk": TENGGAT_PELAKSANAAN_HK,
            "tenggat_lapor_hk": TENGGAT_LAPOR_HK,
            "catatan": (
                "PMK 207/2021: pemantauan insidentil dilaksanakan paling lama "
                f"{TENGGAT_PELAKSANAAN_HK} hari kerja sejak mulai; hasilnya "
                f"dilaporkan paling lama {TENGGAT_LAPOR_HK} hari kerja sejak "
                "tanggal BA. Tenggat dihitung hari kerja Senin–Jumat.")}


@wasdal_router.get("/wasdal/insidentil/export")
async def export_insidentil(_user: dict = Depends(require_user)):
    """Ekspor CSV seluruh register pemantauan insidentil wasdal (pola #158)."""
    import csv as csv_module
    import io

    from fastapi.responses import Response as HttpResponse

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items = [t async for t in db.pemantauan_insidentil.find(scope_query_field_satker(_user), {"_id": 0})
             .sort("created_at", -1)]
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in baris_csv_insidentil(items, today_iso):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="register_pemantauan_insidentil.csv"'})


@wasdal_router.post("/wasdal/insidentil")
async def catat_insidentil(payload: InsidentilIn,
                           user: dict = Depends(require_writer)):
    """Buka pemantauan insidentil (pemicu masyarakat/media/audit)."""
    data = payload.model_dump()
    errors = validate_insidentil(data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "kode_satker": kode_satker_user(user),
        "pemicu": data["pemicu"],
        "tanggal_mulai": data["tanggal_mulai"].strip()[:10],
        "objek": str(data.get("objek") or "").strip(),
        "uraian": data["uraian"].strip(),
        "lokasi": str(data.get("lokasi") or "").strip(),
        "status": "berjalan",
        "nomor_ba": "",
        "tanggal_ba": "",
        "hasil": "",
        "tanggal_lapor": "",
        "keterangan_lapor": "",
        "lampiran": [],
        "created_by": user.get("username"),
        "created_at": now,
        "updated_at": now,
    }
    await db.pemantauan_insidentil.insert_one({**record})
    record["info_tenggat"] = info_tenggat_insidentil(
        record, datetime.now(timezone.utc).date().isoformat())
    return record


@wasdal_router.post("/wasdal/insidentil/{tiket_id}/ba")
async def terbitkan_ba_insidentil(tiket_id: str, payload: BaInsidentilIn,
                                  admin: dict = Depends(require_admin)):
    """Catat BA pemantauan insidentil (admin) → status ba_terbit."""
    t = await db.pemantauan_insidentil.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    data = payload.model_dump()
    errors = validate_ba_insidentil(t, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    res = await db.pemantauan_insidentil.find_one_and_update(
        # Anti-balapan: hanya tiket yang masih berjalan
        {"id": tiket_id, "status": "berjalan"},
        {"$set": {"status": "ba_terbit",
                  "nomor_ba": data["nomor_ba"].strip(),
                  "tanggal_ba": data["tanggal_ba"].strip()[:10],
                  "hasil": data["hasil"].strip(),
                  "ba_oleh": admin.get("username"),
                  "updated_at": now}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Tiket berubah oleh proses lain — muat ulang")
    return res


@wasdal_router.post("/wasdal/insidentil/{tiket_id}/lapor")
async def laporkan_insidentil(tiket_id: str, payload: LaporInsidentilIn,
                              admin: dict = Depends(require_admin)):
    """Catat pelaporan hasil (admin) → status dilaporkan."""
    t = await db.pemantauan_insidentil.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    data = payload.model_dump()
    errors = validate_lapor_insidentil(t, data)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))
    now = datetime.now(timezone.utc).isoformat()
    res = await db.pemantauan_insidentil.find_one_and_update(
        {"id": tiket_id, "status": "ba_terbit"},
        {"$set": {"status": "dilaporkan",
                  "tanggal_lapor": data["tanggal_lapor"].strip()[:10],
                  "keterangan_lapor": str(data.get("keterangan") or "").strip(),
                  "lapor_oleh": admin.get("username"),
                  "updated_at": now}},
        projection={"_id": 0}, return_document=True)
    if not res:
        raise HTTPException(status_code=409,
                            detail="Tiket berubah oleh proses lain — muat ulang")
    return res


@wasdal_router.delete("/wasdal/insidentil/{tiket_id}")
async def hapus_insidentil(tiket_id: str, _admin: dict = Depends(require_admin)):
    """Hapus tiket salah input (khusus admin) + berkas lampirannya."""
    t = await db.pemantauan_insidentil.find_one(
        {"id": tiket_id}, {"_id": 0, "lampiran": 1})
    res = await db.pemantauan_insidentil.delete_one({"id": tiket_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    for lamp in (t or {}).get("lampiran") or []:
        if lamp.get("file_id"):
            await delete_document_from_gridfs(lamp["file_id"])
    return {"ok": True, "id": tiket_id}


# Arsip lampiran per tiket insidentil (scan BA bertanda tangan + foto
# temuan). Pola sama dengan lampiran pemanfaatan/pemusnahan/penghapusan/
# pengadaan/PSP/pemindahtanganan (#131–#138).
_LAMPIRAN_MEDIA = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".webp": "image/webp",
}
_MAX_LAMPIRAN_BYTES = 10 * 1024 * 1024
_MAX_LAMPIRAN = 10


def _lampiran_ext(filename: str) -> str:
    name = (filename or "").lower()
    for ext in _LAMPIRAN_MEDIA:
        if name.endswith(ext):
            return ext
    return ""


@wasdal_router.post("/wasdal/insidentil/{tiket_id}/lampiran")
async def unggah_lampiran_insidentil(tiket_id: str, file: UploadFile = File(...),
                                     user: dict = Depends(require_writer)):
    """Unggah scan BA/foto temuan (PDF/gambar, maks 10MB, 10 berkas)."""
    t = await db.pemantauan_insidentil.find_one(
        {"id": tiket_id}, {"_id": 0, "id": 1, "lampiran": 1, "kode_satker": 1})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    await pastikan_akses_dok_satker(user, t)
    if len(t.get("lampiran") or []) >= _MAX_LAMPIRAN:
        raise HTTPException(status_code=400,
                            detail=f"Maksimal {_MAX_LAMPIRAN} lampiran per tiket")
    filename = (file.filename or "dokumen.pdf").strip() or "dokumen.pdf"
    ext = _lampiran_ext(filename)
    if not ext:
        raise HTTPException(status_code=400,
                            detail="Lampiran harus PDF atau gambar (JPG/PNG/WEBP)")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File kosong")
    if len(file_bytes) > _MAX_LAMPIRAN_BYTES:
        raise HTTPException(status_code=400, detail="Ukuran lampiran maksimal 10MB")
    if ext == ".pdf" and not file_bytes[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File bukan PDF yang valid")

    from bson import ObjectId
    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=filename,
        metadata={"content_type": _LAMPIRAN_MEDIA[ext], "size": len(file_bytes),
                  "kind": "insidentil", "tiket_id": tiket_id})
    await grid_in.write(file_bytes)
    await grid_in.close()

    entri = {"file_id": str(file_id), "filename": filename,
             "content_type": _LAMPIRAN_MEDIA[ext],
             "oleh": user.get("username"),
             "tanggal": datetime.now(timezone.utc).isoformat()}
    res = await db.pemantauan_insidentil.find_one_and_update(
        {"id": tiket_id},
        {"$push": {"lampiran": entri}, "$set": {"updated_at": entri["tanggal"]}},
        projection={"_id": 0, "lampiran": 1}, return_document=True)
    if not res:
        await delete_document_from_gridfs(str(file_id))
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    return {"message": "Lampiran terunggah", "lampiran": res.get("lampiran") or []}


@wasdal_router.get("/wasdal/insidentil/{tiket_id}/lampiran/{file_id}")
async def unduh_lampiran_insidentil(tiket_id: str, file_id: str, request: Request,
                                    _user: dict = Depends(require_user_or_query_token)):
    """Stream lampiran tiket insidentil (menerima header ATAU ?token)."""
    t = await db.pemantauan_insidentil.find_one(
        scope_query_field_satker(
            _user, {"id": tiket_id, "lampiran.file_id": file_id}),
        {"_id": 0, "lampiran.$": 1})
    if not t or not t.get("lampiran"):
        raise HTTPException(status_code=404, detail="Lampiran tidak ditemukan")
    meta = t["lampiran"][0]
    etag = f'"lampiran-{file_id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    data = await get_document_from_gridfs(file_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Berkas tidak ditemukan")
    return Response(content=data,
                    media_type=meta.get("content_type") or "application/octet-stream",
                    headers={"ETag": etag, "Cache-Control": "private, max-age=86400",
                             "Content-Disposition": f'inline; filename="{meta.get("filename") or "dokumen"}"'})


@wasdal_router.delete("/wasdal/insidentil/{tiket_id}/lampiran/{file_id}")
async def hapus_lampiran_insidentil(tiket_id: str, file_id: str,
                                    _admin: dict = Depends(require_admin)):
    """Hapus lampiran salah unggah (khusus admin)."""
    res = await db.pemantauan_insidentil.update_one(
        scope_query_field_satker(_admin, {"id": tiket_id}),
        {"$pull": {"lampiran": {"file_id": file_id}},
         "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    if res.modified_count:
        await delete_document_from_gridfs(file_id)
    return {"ok": True, "file_id": file_id}


@wasdal_router.get("/wasdal/insidentil/{tiket_id}/ba-pdf")
async def ba_insidentil_pdf(tiket_id: str, _user: dict = Depends(require_user)):
    """Berita Acara Pemantauan Insidentil (PDF siap tanda tangan).

    Bila BA belum diterbitkan, nomor/tanggal tampil sebagai isian kosong —
    dokumen tetap bisa disiapkan lebih dulu.
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

    t = await db.pemantauan_insidentil.find_one({"id": tiket_id}, {"_id": 0})
    if not t:
        raise HTTPException(status_code=404, detail="Tiket tidak ditemukan")
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    elements = []
    elements.extend(_kop_surat_flowables(settings, doc.width))
    elements.extend(_title_block(
        "BERITA ACARA\nPEMANTAUAN INSIDENTIL BMN",
        nomor=t.get("nomor_ba") or "....................",
        subjudul="Pengawasan dan Pengendalian BMN — PMK 207/PMK.06/2021"))
    elements.append(Paragraph(
        f"Pada tanggal {t.get('tanggal_ba') or '....................'} telah "
        f"dilaksanakan pemantauan insidentil atas Barang Milik Negara "
        f"berdasarkan pemicu berikut, dimulai tanggal "
        f"{t.get('tanggal_mulai') or '-'} dengan batas pelaksanaan "
        f"{TENGGAT_PELAKSANAAN_HK} hari kerja.", st['Meta']))
    elements.append(Spacer(1, 3 * rl_mm))

    baris = [
        ("Pemicu", PEMICU_INSIDENTIL.get(t.get("pemicu"), t.get("pemicu") or "-")),
        ("Objek pemantauan", OBJEK_WASDAL.get(t.get("objek"), "") or "Tidak spesifik"),
        ("Uraian", t.get("uraian") or "-"),
        ("Lokasi", t.get("lokasi") or "-"),
        ("Hasil pemantauan", t.get("hasil") or "(diisi setelah pemantauan selesai)"),
    ]
    table_data = [[Paragraph(f"<b>{k}</b>", st['Cell']), Paragraph(str(v), st['Cell'])]
                  for k, v in baris]
    table = Table(table_data, colWidths=_fit_col_widths([130, 328], doc.width))
    table.setStyle(_std_table_style(zebra=False))
    elements.append(table)
    elements.append(Spacer(1, 4 * rl_mm))
    elements.append(Paragraph(
        f"Hasil pemantauan dilaporkan secara berjenjang paling lama "
        f"{TENGGAT_LAPOR_HK} hari kerja sejak tanggal Berita Acara ini. "
        f"Berita Acara dibuat dengan sebenarnya untuk dipergunakan "
        f"sebagaimana mestinya.", st['Meta']))
    elements.append(Spacer(1, 8 * rl_mm))
    elements.extend(_signature_block([
        {'pre': [''], 'header': 'Petugas Pemantauan,',
         'nama': '...........................',
         'after': ['NIP. ....................']},
        await blok_ttd_kpb_titik(settings, kode_satker=kode_satker_user(_user)),   # KPB dari registry pejabat (temuan #26)
    ], doc.width))
    footer = _page_footer_factory("Berita Acara Pemantauan Insidentil BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama = f"BA_Pemantauan_Insidentil_{(t.get('nomor_ba') or tiket_id[:8]).replace('/', '-')}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{nama}"'})


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
    periode, per_objek, rekap, total_aset = await _data_pemantauan(ambang_hari, _user)
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
        await blok_ttd_kpb_titik(settings, kode_satker=kode_satker_user(_user)),   # KPB dari registry pejabat (temuan #26)
    ], doc.width))
    footer = _page_footer_factory("Laporan Hasil Pemantauan Wasdal BMN")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    nama = f"Laporan_Wasdal_{periode['label'].replace(' ', '_')}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{nama}"'})


# ============================================================================
# LAPORAN TAHUNAN WASDAL (formulir Lampiran PMK 207/2021) + PORTOFOLIO SBSK
# (M-MODUL — dua butir terakhir modul Wasdal)
# ============================================================================

async def _data_portofolio(user):
    """Portofolio BMN untuk wasdal: rekap per golongan (reuse DBKP) + status
    penggunaan (PSP/idle/sengketa) + standar SBSK — bahan analisis kesesuaian
    penggunaan BMN vs SBSK (metrik DJKN). Ter-scope satker user."""
    from kodefikasi_utils import GOLONGAN_DEFAULTS
    from pembukuan_utils import build_dbkp_rows
    from pengamanan_utils import is_sengketa
    from report_filters import active_asset_filter
    from shared_utils import (ambang_kapitalisasi, filter_aset_perhitungan,
                              scope_query_aset)

    q = await filter_aset_perhitungan(
        await scope_query_aset(user, active_asset_filter()))
    assets = await db.assets.find(
        q, {"_id": 0, "asset_code": 1, "purchase_price": 1,
            "nilai_wajar_terakhir": 1, "status": 1, "inventory_status": 1,
            "nomor_perkara": 1, "pihak_bersengketa": 1}).to_list(500000)
    uraian_map = {k: u for k, u in GOLONGAN_DEFAULTS}
    rows, total = build_dbkp_rows(assets, uraian_map,
                                  ambang=await ambang_kapitalisasi())
    n_sengketa = sum(1 for a in assets if is_sengketa(a))
    n_psp = await db.psp.count_documents({})
    n_idle = await db.bmn_idle.count_documents(
        {"status": {"$in": ["klarifikasi", "usul_serah"]}})
    standar = await db.sbsk_standar.find({}, {"_id": 0}).to_list(1000)
    return {"rows": rows, "total": total, "jumlah_aset": len(assets),
            "psp_terbit": n_psp, "idle_proses": n_idle,
            "sengketa": n_sengketa, "sbsk": standar}


@wasdal_router.get("/wasdal/portofolio")
async def portofolio_wasdal(_user: dict = Depends(require_user)):
    """Portofolio aset + indikator tertib penggunaan + tabel standar SBSK
    (PMK 138/2024) — dasbor analisis kesesuaian untuk pengawasan."""
    return await _data_portofolio(_user)


@wasdal_router.get("/wasdal/laporan-tahunan-pdf")
async def laporan_tahunan_wasdal_pdf(
    tahun: int = Query(None, ge=2000, le=2100),
    _user: dict = Depends(require_user),
):
    """LAPORAN TAHUNAN PENGAWASAN DAN PENGENDALIAN BMN tingkat KPB —
    formulir rekap mengikuti struktur Lampiran PMK 207/PMK.06/2021:
    (1) pemantauan per objek, (2) penertiban & tindak lanjutnya,
    (3) pemantauan insidentil, (4) portofolio BMN ringkas — satu tahun."""
    from io import BytesIO

    from fastapi.responses import StreamingResponse
    from reportlab.lib.units import mm as rl_mm
    from reportlab.platypus import Paragraph, Spacer, Table

    from routes.reports import (
        _get_report_styles, _kop_surat_flowables, _page_footer_factory,
        _signature_block, _std_doc, _std_table_style, _title_block,
    )

    th = tahun or datetime.now(timezone.utc).year
    awal, akhir = f"{th}-01-01", f"{th}-12-31"

    periode, per_objek, rekap, total_aset = await _data_pemantauan(AMBANG_BERLARUT_HARI, _user)
    porto = await _data_portofolio(_user)
    tertib = [t async for t in db.penertiban.find(
        scope_query_field_satker(
            _user, {"created_at": {"$gte": awal, "$lte": akhir + "T~"}}),
        {"_id": 0})]
    insidentil = [i async for i in db.pemantauan_insidentil.find(
        scope_query_field_satker(
            _user, {"created_at": {"$gte": awal, "$lte": akhir + "T~"}}),
        {"_id": 0})]
    settings = await db.report_settings.find_one({"type": "global"}, {"_id": 0}) or {}

    buffer = BytesIO()
    doc = _std_doc(buffer)
    st = _get_report_styles()
    el = []
    el.extend(_kop_surat_flowables(settings, doc.width))
    el.extend(_title_block("LAPORAN TAHUNAN\nPENGAWASAN DAN PENGENDALIAN BMN",
                           subjudul=f"Tingkat Kuasa Pengguna Barang — Tahun {th}"))
    el.append(Paragraph(
        f"Disusun mengikuti struktur formulir Lampiran PMK 207/PMK.06/2021 "
        f"atas {total_aset} BMN dalam penguasaan KPB: hasil pemantauan lima "
        f"objek wasdal, pelaksanaan penertiban beserta tindak lanjutnya, "
        f"pemantauan insidentil, dan portofolio BMN. Penyampaian resmi tetap "
        f"melalui Modul Wasdal SIMAN v2.", st['Meta']))
    el.append(Spacer(1, 4 * rl_mm))

    # I. Pemantauan per objek
    el.append(Paragraph("<b>I. HASIL PEMANTAUAN PER OBJEK WASDAL</b>", st['Meta']))
    td = [[Paragraph(h, st['TableHeader']) for h in ("No", "Objek", "Temuan")]]
    for i, (kunci, label) in enumerate(OBJEK_WASDAL.items(), 1):
        td.append([Paragraph(str(i), st['CellCenter']),
                   Paragraph(label, st['Cell']),
                   Paragraph(str(rekap["per_objek"].get(kunci, 0)), st['CellCenter'])])
    t = Table(td, colWidths=[doc.width * 0.08, doc.width * 0.72, doc.width * 0.20],
              repeatRows=1)
    t.setStyle(_std_table_style(zebra=True))
    el.append(t)
    el.append(Spacer(1, 3 * rl_mm))

    # II. Penertiban tahun berjalan
    sel = sum(1 for x in tertib if x.get("status") == "selesai")
    el.append(Paragraph(
        f"<b>II. PENERTIBAN TAHUN {th}</b> — {len(tertib)} tiket "
        f"({sel} selesai, {len(tertib) - sel} berjalan; tenggat "
        f"{TENGGAT_HARI_KERJA} hari kerja per PMK 207).", st['Meta']))
    if tertib:
        td2 = [[Paragraph(h, st['TableHeader']) for h in
                ("No", "Objek/Temuan", "Sumber", "Status")]]
        for i, x in enumerate(tertib[:30], 1):
            td2.append([Paragraph(str(i), st['CellCenter']),
                        Paragraph(str(x.get("uraian") or x.get("temuan") or "-")[:120], st['Cell']),
                        Paragraph(str(x.get("sumber") or "-"), st['CellCenter']),
                        Paragraph(str(x.get("status") or "-"), st['CellCenter'])])
        t2 = Table(td2, colWidths=[doc.width * 0.07, doc.width * 0.53,
                                   doc.width * 0.20, doc.width * 0.20], repeatRows=1)
        t2.setStyle(_std_table_style(zebra=True))
        el.append(t2)
        if len(tertib) > 30:
            el.append(Paragraph(f"… dan {len(tertib) - 30} tiket lainnya (lihat register).",
                                st['Small']))
    el.append(Spacer(1, 3 * rl_mm))

    # III. Pemantauan insidentil
    el.append(Paragraph(
        f"<b>III. PEMANTAUAN INSIDENTIL TAHUN {th}</b> — {len(insidentil)} kegiatan.",
        st['Meta']))
    el.append(Spacer(1, 3 * rl_mm))

    # IV. Portofolio BMN ringkas + indikator tertib
    el.append(Paragraph("<b>IV. PORTOFOLIO BMN & INDIKATOR TERTIB</b>", st['Meta']))
    td3 = [[Paragraph(h, st['TableHeader']) for h in
            ("Golongan", "Unit", "Nilai (Rp)")]]
    for r in porto["rows"]:
        td3.append([Paragraph(f"{r['golongan']} — {r['uraian']}", st['Cell']),
                    Paragraph(str(r["jumlah_total"]), st['CellCenter']),
                    Paragraph(f"{r['nilai_total']:,.0f}".replace(",", "."), st['Cell'])])
    t3 = Table(td3, colWidths=[doc.width * 0.55, doc.width * 0.15, doc.width * 0.30],
               repeatRows=1)
    t3.setStyle(_std_table_style(zebra=True))
    el.append(t3)
    el.append(Paragraph(
        f"PSP terbit: {porto['psp_terbit']} · BMN idle diproses: {porto['idle_proses']} · "
        f"sengketa: {porto['sengketa']}. Analisis kesesuaian penggunaan vs SBSK "
        f"(PMK 138/2024) memakai tabel standar pada modul Perencanaan "
        f"({len(porto['sbsk'])} baris standar terdaftar).", st['Small']))
    el.append(Spacer(1, 6 * rl_mm))
    el.extend(_signature_block([await blok_ttd_kpb_titik(settings, kode_satker=kode_satker_user(_user))], doc.width))

    footer = _page_footer_factory("Laporan Tahunan Wasdal")
    doc.build(el, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return StreamingResponse(
        buffer, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="Laporan_Tahunan_Wasdal_{th}.pdf"'})
