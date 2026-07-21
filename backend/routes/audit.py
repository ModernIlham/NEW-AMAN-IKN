"""
Audit log routes.
Extracted from assets.py for clean separation of concerns.
Provides: GET /audit-logs
"""
import logging
from fastapi import APIRouter, Depends
from db import db
from auth_utils import require_user
from shared_utils import (
    id_kegiatan_satker, kode_satker_user, scope_query_aset,
)
from penghapusan_utils import normalisasi_jejak_terhapus, rekap_jejak_terhapus
from integritas_utils import (
    FIELD_IDENTITAS, drift_identitas_daftar, drift_identitas_tunggal,
    gabung_temuan_integritas, hitung_masalah, identitas_drift,
    ringkasan_csv_baris,
)

# Label manusiawi jenis temuan integritas (dipakai ekspor CSV dasbor).
LABEL_MASALAH_INTEGRITAS = {
    "snapshot_basi": "Identitas basi",
    "aset_master_hilang": "Aset induk hilang",
    "golongan_tak_terdaftar": "Golongan tak terdaftar",
    "kode_spesifik_tak_terdaftar": "Kode tak terdaftar",
    "panjang_kode_tak_valid": "Panjang kode tak valid",
}
from kodefikasi_utils import (
    cek_kode_kodefikasi, derive_level, level_terdaftar_terdalam, normalize_kode,
)
from report_filters import active_asset_filter

logger = logging.getLogger(__name__)
audit_router = APIRouter()


async def _batas_activity_satker(user, activity_id: str):
    """Terapkan isolasi satker pada query audit_log by activity_id.

    Kembalikan (query_activity_filter, kosong_paksa):
      - user lintas-satker → ({activity_id} bila diminta, else {}), False.
      - user terikat satker → activity_id DIBATASI ke kegiatan satkernya;
        bila diminta activity_id di luar satker → kosong_paksa=True (hasil
        kosong, bukan bocor lintas satker). Log SISTEM tanpa activity_id
        ikut tampil bila field `kode_satker`-nya cocok satker user (mis.
        kejadian kartu pegawai) — log sistem tanpa kode tetap tersembunyi.
    """
    kode = kode_satker_user(user)
    if not kode:
        return ({"activity_id": activity_id} if activity_id else {}), False
    allowed = set(await id_kegiatan_satker(kode))
    if activity_id:
        if activity_id not in allowed:
            return {}, True
        return {"activity_id": activity_id}, False
    return {"$or": [{"activity_id": {"$in": list(allowed)}},
                    {"activity_id": "", "kode_satker": kode}]}, False


async def _filter_register_satker(user, query=None) -> dict:
    """Filter register turunan (usulan_penghapusan/pemindahtanganan/psp/
    jadwal_pemeliharaan) ke kegiatan milik satker user. Lintas-satker → apa
    adanya. Mencegah dasbor integritas membocorkan snapshot identitas aset
    (kode/NUP/nama) lintas satker ke user terikat."""
    q = dict(query or {})
    kode = kode_satker_user(user)
    if kode:
        q["activity_id"] = {"$in": await id_kegiatan_satker(kode)}
    return q


@audit_router.get("/audit-logs")
async def get_audit_logs(activity_id: str = "", asset_id: str = "", sistem: bool = False,
                         page: int = 1, page_size: int = 50,
                         user: dict = Depends(require_user)):
    """Get audit logs with optional filtering (ter-scope satker).

    `sistem=true` → HANYA log sistem (tanpa activity_id — kejadian master
    pegawai/kartu dsb.); user terikat satker dibatasi log ber-`kode_satker`
    miliknya, user lintas-satker melihat semua log sistem."""
    query = {}
    if sistem:
        query["activity_id"] = ""
        kode = kode_satker_user(user)
        if kode:
            query["kode_satker"] = kode
    else:
        scope, kosong = await _batas_activity_satker(user, activity_id)
        if kosong:
            return {"logs": [], "total": 0, "page": 1, "page_size": page_size, "total_pages": 1}
        query.update(scope)
    if asset_id:
        query["asset_id"] = asset_id

    # Clamp pagination so a caller can't request an unbounded page and dump the
    # entire audit trail (or drive huge memory use) in one request.
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)

    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(page_size).to_list(page_size)

    return {
        "logs": logs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1
    }


@audit_router.get("/audit-logs/aset-terhapus")
async def get_jejak_aset_terhapus(activity_id: str = "", page: int = 1,
                                  page_size: int = 50,
                                  user: dict = Depends(require_user)):
    """Jejak Aset Terhapus — arsip read-only dari audit log (ter-scope satker).

    Aset yang dihapus permanen tetap tertelusur (kode/NUP/nama/nilai/oleh/
    waktu) tanpa mengubah mekanisme penghapusan. Nilai perolehan diambil
    dari perubahan yang direkam saat penghapusan.
    """
    query = {"action": {"$in": ["delete", "bulk_delete"]}}
    scope, kosong = await _batas_activity_satker(user, activity_id)
    if kosong:
        return {"items": [], "ringkasan": rekap_jejak_terhapus([]), "total": 0,
                "page": 1, "page_size": page_size, "total_pages": 1, "catatan": ""}
    query.update(scope)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 200)
    total = await db.audit_logs.count_documents(query)
    skip = (page - 1) * page_size
    logs = await db.audit_logs.find(query, {"_id": 0}).sort(
        "timestamp", -1).skip(skip).limit(page_size).to_list(page_size)
    rows = normalisasi_jejak_terhapus(logs)
    return {
        "items": rows,
        "ringkasan": rekap_jejak_terhapus(rows),
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "catatan": (
            "Arsip jejak penghapusan aset (read-only) dari log audit. "
            "Penghapusan permanen tetap tercatat di sini untuk penelusuran; "
            "nilai perolehan direkam saat aset dihapus."),
    }


@audit_router.get("/integritas/identitas-penghapusan")
async def integritas_identitas_penghapusan(user: dict = Depends(require_user)):
    """§5A Prinsip 1 (READ-ONLY): deteksi snapshot identitas aset yang BASI pada
    register `usulan_penghapusan`.

    Register hilir membekukan `asset_code`/`NUP`/`asset_name` saat usulan dibuat;
    bila master aset kelak diedit, snapshot itu jadi usang. Endpoint ini
    membandingkan tiap snapshot dengan master aset TERKINI (via `asset_id`) dan
    melaporkan yang **basi** (`snapshot_basi`) atau yang master-nya sudah
    **hilang** (`aset_master_hilang`). Tidak mengubah data apa pun — langkah awal
    penyegaran snapshot (penulisan menyusul sebagai langkah terpisah).
    """
    proj_snap = {"_id": 0, "id": 1, "asset_id": 1, "status": 1,
                 "asset_code": 1, "NUP": 1, "asset_name": 1}
    proj_master = {"_id": 0, "asset_code": 1, "NUP": 1, "asset_name": 1}
    items = []
    n_basi = n_hilang = 0
    async for u in db.usulan_penghapusan.find(await _filter_register_satker(user), proj_snap):
        aid = u.get("asset_id")
        master = await db.assets.find_one({"id": aid}, proj_master) if aid else None
        snap = {f: u.get(f) for f in FIELD_IDENTITAS}
        if not master:
            n_hilang += 1
            items.append({"usulan_id": u.get("id"), "asset_id": aid,
                          "status": u.get("status"),
                          "masalah": "aset_master_hilang", "snapshot": snap})
            continue
        drift = identitas_drift(u, master)
        if drift:
            n_basi += 1
            items.append({"usulan_id": u.get("id"), "asset_id": aid,
                          "status": u.get("status"),
                          "masalah": "snapshot_basi", "drift": drift})
    return {
        "jumlah": len(items),
        "snapshot_basi": n_basi,
        "aset_master_hilang": n_hilang,
        "items": items,
        "catatan": (
            "Deteksi read-only snapshot identitas aset basi di register usulan "
            "penghapusan (§5A Prinsip 1). Belum menyegarkan otomatis — hanya "
            "melaporkan agar bisa ditindaklanjuti."),
    }


@audit_router.get("/integritas/kodefikasi-aset")
async def integritas_kodefikasi_aset(user: dict = Depends(require_user)):
    """§5A Prinsip 2 (READ-ONLY): kodefikasi sebagai FK tervalidasi.

    Kode barang aset diturunkan dari prefix, tetapi TAK divalidasi sebagai FK ke
    referensi `kodefikasi`. Endpoint ini mengagregasi `asset_code` DISTINCT (aset
    aktif) dan melaporkan yang prefix golongan/level-nya **tak terdaftar** di
    `db.kodefikasi` — sebagai **peringatan** (non-blocking), tanpa menolak/ubah
    data lama. Ambang: `kode_spesifik_tak_terdaftar` (hanya induk terdaftar),
    `golongan_tak_terdaftar` (level 1 pun tak ada), `panjang_kode_tak_valid`.
    """
    terdaftar = set()
    async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if k.get("kode"):
            terdaftar.add(str(k["kode"]))

    items = []
    n_golongan = n_spesifik = n_invalid = 0
    from shared_utils import filter_aset_perhitungan
    async for grp in db.assets.aggregate([
        {"$match": await filter_aset_perhitungan(
            await scope_query_aset(user, active_asset_filter()))},
        {"$group": {"_id": "$asset_code", "jumlah_aset": {"$sum": 1}}},
    ]):
        kode = normalize_kode(grp.get("_id"))
        jml = grp.get("jumlah_aset", 0)
        level_kode = derive_level(kode)
        if not level_kode:
            n_invalid += 1
            items.append({"asset_code": grp.get("_id"), "jumlah_aset": jml,
                          "masalah": "panjang_kode_tak_valid"})
            continue
        dalam = level_terdaftar_terdalam(kode, terdaftar)
        if dalam >= level_kode:
            continue  # kode terdaftar sampai level-nya → konsisten
        masalah = "golongan_tak_terdaftar" if dalam == 0 else "kode_spesifik_tak_terdaftar"
        if dalam == 0:
            n_golongan += 1
        else:
            n_spesifik += 1
        items.append({"asset_code": grp.get("_id"), "jumlah_aset": jml,
                      "level_kode": level_kode, "level_terdaftar": dalam,
                      "masalah": masalah})

    items.sort(key=lambda x: (-x.get("jumlah_aset", 0), str(x.get("asset_code") or "")))
    return {
        "jumlah_kode": len(items),
        "golongan_tak_terdaftar": n_golongan,
        "kode_spesifik_tak_terdaftar": n_spesifik,
        "panjang_kode_tak_valid": n_invalid,
        "items": items,
        "catatan": (
            "Peringatan read-only (§5A Prinsip 2): kode aset yang prefix "
            "kodefikasi-nya belum terdaftar di referensi. Non-blocking — tak "
            "menolak data lama; lengkapi referensi kodefikasi untuk menutup."),
    }


@audit_router.get("/integritas/kategori-kodefikasi")
async def integritas_kategori_kodefikasi(_user: dict = Depends(require_user)):
    """Validasi silang LUNAK Kelola Kategori ↔ Referensi Kodefikasi (1a, §5A
    Prinsip 2 — READ-ONLY, non-blocking): kedua master kode barang berjalan
    paralel; endpoint ini melaporkan kategori yang `kode_aset`-nya TIDAK
    terdaftar (sampai level-nya) di `db.kodefikasi`, tanpa menolak/mengubah
    data. `kode_bermasalah` = daftar kode utk penanda baris di UI Kelola
    Kategori; `items` = rincian (dibatasi 300)."""
    terdaftar = set()
    async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if k.get("kode"):
            terdaftar.add(str(k["kode"]))

    items, kode_bermasalah = [], []
    n_golongan = n_spesifik = n_invalid = n_tanpa_kode = n_total = 0
    async for cat in db.categories.find(
            {}, {"_id": 0, "kode_aset": 1, "label": 1}):
        n_total += 1
        kode = normalize_kode(cat.get("kode_aset"))
        if not kode:
            n_tanpa_kode += 1  # kategori tanpa kode sah-sah saja — info saja
            continue
        level_kode = derive_level(kode)
        if not level_kode:
            masalah = "panjang_kode_tak_valid"
            n_invalid += 1
        else:
            dalam = level_terdaftar_terdalam(kode, terdaftar)
            if dalam >= level_kode:
                continue
            masalah = ("golongan_tak_terdaftar" if dalam == 0
                       else "kode_spesifik_tak_terdaftar")
            if dalam == 0:
                n_golongan += 1
            else:
                n_spesifik += 1
        kode_bermasalah.append(str(cat.get("kode_aset") or ""))
        if len(items) < 300:
            items.append({"kode_aset": cat.get("kode_aset"),
                          "label": cat.get("label"), "masalah": masalah})

    return {
        "jumlah_kategori": n_total,
        "jumlah_bermasalah": len(kode_bermasalah),
        "golongan_tak_terdaftar": n_golongan,
        "kode_spesifik_tak_terdaftar": n_spesifik,
        "panjang_kode_tak_valid": n_invalid,
        "tanpa_kode": n_tanpa_kode,
        "kode_bermasalah": kode_bermasalah,
        "items": items,
        "catatan": (
            "Validasi silang lunak (1a): kategori dengan kode yang belum "
            "terdaftar di Referensi Kodefikasi. Non-blocking — tidak ada data "
            "yang ditolak/diubah; lengkapi referensi kodefikasi (atau perbaiki "
            "kode kategori) untuk menutup temuan."),
    }


@audit_router.get("/integritas/cek-kode")
async def integritas_cek_kode(asset_code: str = "", _user: dict = Depends(require_user)):
    """§5A Prinsip 2 (READ-ONLY, NON-BLOCKING): validasi LUNAK satu `asset_code`
    terhadap referensi `db.kodefikasi`. Kembalikan status + pesan peringatan
    (tanpa menolak) — untuk umpan balik langsung saat mengisi/menyunting kode
    aset. Melengkapi `/integritas/kodefikasi-aset` yang memindai seluruh aset."""
    terdaftar = set()
    async for kdf in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if kdf.get("kode"):
            terdaftar.add(str(kdf["kode"]))
    return cek_kode_kodefikasi(asset_code, terdaftar)


@audit_router.get("/integritas/identitas-pemindahtanganan")
async def integritas_identitas_pemindahtanganan(user: dict = Depends(require_user)):
    """§5A Prinsip 1 (READ-ONLY, lanjutan #261): deteksi snapshot identitas aset
    basi pada register `pemindahtanganan` (yang membekukan identitas per baris
    `aset[]`). Master di-lookup BATCH via `$in` (hindari N+1)."""
    usulan_list = [u async for u in db.pemindahtanganan.find(
        await _filter_register_satker(user), {"_id": 0, "id": 1, "bentuk": 1, "status": 1, "aset": 1})]
    ids = {str(r.get("asset_id") or "")
           for u in usulan_list for r in (u.get("aset") or [])
           if r.get("asset_id")}
    master_by_id = {}
    if ids:
        async for a in db.assets.find(
                {"id": {"$in": list(ids)}},
                {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}):
            master_by_id[a["id"]] = a

    items = []
    n_basi = n_hilang = 0
    for u in usulan_list:
        for t in drift_identitas_daftar(u.get("aset"), master_by_id):
            if t["masalah"] == "aset_master_hilang":
                n_hilang += 1
            else:
                n_basi += 1
            items.append({"pemindahtanganan_id": u.get("id"),
                          "bentuk": u.get("bentuk"), "status": u.get("status"),
                          **t})
    return {
        "jumlah": len(items),
        "snapshot_basi": n_basi,
        "aset_master_hilang": n_hilang,
        "items": items,
        "catatan": (
            "Deteksi read-only snapshot identitas aset basi di register "
            "pemindahtanganan (§5A Prinsip 1). Belum menyegarkan otomatis."),
    }


@audit_router.get("/integritas/identitas-psp")
async def integritas_identitas_psp(user: dict = Depends(require_user)):
    """§5A Prinsip 1 (READ-ONLY, lanjutan #261/#263): deteksi snapshot identitas
    aset basi pada register SK PSP Penggunaan (`db.psp`, per baris `aset[]`).
    Master di-lookup BATCH via `$in` (hindari N+1)."""
    sk_list = [s async for s in db.psp.find(
        await _filter_register_satker(user), {"_id": 0, "id": 1, "nomor_sk": 1, "status_pengajuan": 1, "aset": 1})]
    ids = {str(r.get("asset_id") or "")
           for s in sk_list for r in (s.get("aset") or [])
           if r.get("asset_id")}
    master_by_id = {}
    if ids:
        async for a in db.assets.find(
                {"id": {"$in": list(ids)}},
                {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}):
            master_by_id[a["id"]] = a

    items = []
    for s in sk_list:
        for t in drift_identitas_daftar(s.get("aset"), master_by_id):
            items.append({"psp_id": s.get("id"), "nomor_sk": s.get("nomor_sk"),
                          "status_pengajuan": s.get("status_pengajuan"), **t})
    ringkas = hitung_masalah(items)
    return {
        "jumlah": len(items),
        "snapshot_basi": ringkas.get("snapshot_basi", 0),
        "aset_master_hilang": ringkas.get("aset_master_hilang", 0),
        "items": items,
        "catatan": (
            "Deteksi read-only snapshot identitas aset basi di register SK PSP "
            "Penggunaan (§5A Prinsip 1). Belum menyegarkan otomatis."),
    }


@audit_router.get("/integritas/identitas-jadwal-pemeliharaan")
async def integritas_identitas_jadwal_pemeliharaan(user: dict = Depends(require_user)):
    """§5A Prinsip 1 (READ-ONLY, lanjutan #261/#263/#264): deteksi snapshot
    identitas aset basi pada register `jadwal_pemeliharaan` (membekukan identitas
    per record). Master di-lookup BATCH via `$in` (hindari N+1)."""
    jadwal = [j async for j in db.jadwal_pemeliharaan.find(
        await _filter_register_satker(user), {"_id": 0, "id": 1, "asset_id": 1, "asset_code": 1, "NUP": 1,
             "asset_name": 1, "jatuh_tempo": 1})]
    ids = {str(j.get("asset_id") or "") for j in jadwal if j.get("asset_id")}
    master_by_id = {}
    if ids:
        async for a in db.assets.find(
                {"id": {"$in": list(ids)}},
                {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}):
            master_by_id[a["id"]] = a

    items = []
    for j in jadwal:
        aid = str(j.get("asset_id") or "")
        temuan = drift_identitas_tunggal(j, master_by_id.get(aid))
        if temuan:
            items.append({"jadwal_id": j.get("id"), "asset_id": aid,
                          "jatuh_tempo": j.get("jatuh_tempo"), **temuan})
    ringkas = hitung_masalah(items)
    return {
        "jumlah": len(items),
        "snapshot_basi": ringkas.get("snapshot_basi", 0),
        "aset_master_hilang": ringkas.get("aset_master_hilang", 0),
        "items": items,
        "catatan": (
            "Deteksi read-only snapshot identitas aset basi di register jadwal "
            "pemeliharaan (§5A Prinsip 1). Belum menyegarkan otomatis."),
    }


# ── Kapstone: dasbor gabungan integritas (§5A gap #8, read-only) ──────────────
# Helper internal BARU khusus ringkasan — hanya MENGHITUNG temuan per register
# (bukan daftar item detail), agar dasbor menyajikan total lintas-cek. Sengaja
# tidak me-refactor 5 endpoint detail di atas (hindari regresi; tak ada uji
# endpoint). Master aset di-lookup BATCH via $in untuk hindari N+1.

_PROJ_MASTER_ID = {"_id": 0, "id": 1, "asset_code": 1, "NUP": 1, "asset_name": 1}


async def _master_identitas_by_id(ids):
    """Ambil identitas master aset BATCH via `$in` → dict `{id: master}`."""
    uniq = [i for i in {str(x or "") for x in ids} if i]
    out = {}
    if uniq:
        async for a in db.assets.find({"id": {"$in": uniq}}, _PROJ_MASTER_ID):
            out[a["id"]] = a
    return out


async def _ringkas_identitas_snapshot(coll, register, label):
    """Ringkas cek identitas basi untuk register yang membekukan identitas PER
    RECORD (usulan_penghapusan, jadwal_pemeliharaan)."""
    rows = [r async for r in db[coll].find(
        {}, {"_id": 0, "asset_id": 1, "asset_code": 1, "NUP": 1,
             "asset_name": 1})]
    master = await _master_identitas_by_id(r.get("asset_id") for r in rows)
    temuan = []
    for r in rows:
        t = drift_identitas_tunggal(r, master.get(str(r.get("asset_id") or "")))
        if t:
            temuan.append(t)
    return {"register": register, "label": label, "jumlah": len(temuan),
            "per_masalah": hitung_masalah(temuan)}


async def _ringkas_identitas_daftar(coll, register, label):
    """Ringkas cek identitas basi untuk register ber-`aset[]`
    (pemindahtanganan, psp)."""
    docs = [d async for d in db[coll].find({}, {"_id": 0, "aset": 1})]
    master = await _master_identitas_by_id(
        r.get("asset_id") for d in docs for r in (d.get("aset") or []))
    temuan = []
    for d in docs:
        temuan.extend(drift_identitas_daftar(d.get("aset"), master))
    return {"register": register, "label": label, "jumlah": len(temuan),
            "per_masalah": hitung_masalah(temuan)}


async def _ringkas_kodefikasi():
    """Ringkas cek kodefikasi FK (§5A Prinsip 2) — hitung asset_code DISTINCT
    (aset aktif) yang prefix kodefikasinya tak terdaftar."""
    terdaftar = set()
    async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if k.get("kode"):
            terdaftar.add(str(k["kode"]))
    temuan = []
    from shared_utils import filter_aset_perhitungan
    async for grp in db.assets.aggregate([
        {"$match": await filter_aset_perhitungan(active_asset_filter())},
        {"$group": {"_id": "$asset_code"}},
    ]):
        kode = normalize_kode(grp.get("_id"))
        level_kode = derive_level(kode)
        if not level_kode:
            temuan.append({"masalah": "panjang_kode_tak_valid"})
            continue
        dalam = level_terdaftar_terdalam(kode, terdaftar)
        if dalam >= level_kode:
            continue
        temuan.append({"masalah": "golongan_tak_terdaftar" if dalam == 0
                       else "kode_spesifik_tak_terdaftar"})
    return {"register": "kodefikasi_aset", "label": "Kodefikasi Aset",
            "jumlah": len(temuan), "per_masalah": hitung_masalah(temuan)}


async def _ringkas_kategori_kodefikasi():
    """Ringkas validasi silang Kelola Kategori ↔ Referensi Kodefikasi (1a):
    kategori ber-kode yang tak terdaftar (sampai level-nya) di kodefikasi."""
    terdaftar = set()
    async for k in db.kodefikasi.find({}, {"_id": 0, "kode": 1}):
        if k.get("kode"):
            terdaftar.add(str(k["kode"]))
    temuan = []
    async for cat in db.categories.find({}, {"_id": 0, "kode_aset": 1}):
        kode = normalize_kode(cat.get("kode_aset"))
        if not kode:
            continue  # kategori tanpa kode: sah, bukan temuan
        level_kode = derive_level(kode)
        if not level_kode:
            temuan.append({"masalah": "panjang_kode_tak_valid"})
            continue
        dalam = level_terdaftar_terdalam(kode, terdaftar)
        if dalam >= level_kode:
            continue
        temuan.append({"masalah": "golongan_tak_terdaftar" if dalam == 0
                       else "kode_spesifik_tak_terdaftar"})
    return {"register": "kategori_kodefikasi",
            "label": "Kategori ↔ Kodefikasi",
            "jumlah": len(temuan), "per_masalah": hitung_masalah(temuan)}


async def _kumpulkan_bagian_integritas():
    """Jalankan SEMUA cek integritas §5A → daftar ringkasan per register.
    Satu sumber untuk endpoint ringkasan JSON & ekspor CSV (hindari duplikasi)."""
    return [
        await _ringkas_identitas_snapshot(
            "usulan_penghapusan", "usulan_penghapusan", "Usulan Penghapusan"),
        await _ringkas_identitas_daftar(
            "pemindahtanganan", "pemindahtanganan", "Pemindahtanganan"),
        await _ringkas_identitas_daftar("psp", "psp", "SK PSP Penggunaan"),
        await _ringkas_identitas_snapshot(
            "jadwal_pemeliharaan", "jadwal_pemeliharaan", "Jadwal Pemeliharaan"),
        await _ringkas_kodefikasi(),
        await _ringkas_kategori_kodefikasi(),
    ]


@audit_router.get("/integritas/ringkasan")
async def integritas_ringkasan(_user: dict = Depends(require_user)):
    """Kapstone §5A gap #8 (READ-ONLY): dasbor gabungan seluruh cek integritas
    dalam satu panggilan — hitungan temuan per register (identitas basi 4
    register + kodefikasi FK) beserta total lintas-cek. Tak menyertakan daftar
    item detail (ambil dari endpoint per-register bila perlu). Tak mengubah data
    apa pun."""
    hasil = gabung_temuan_integritas(await _kumpulkan_bagian_integritas())
    return {
        **hasil,
        "catatan": (
            "Dasbor gabungan integritas data siklus BMN (§5A, read-only): "
            "identitas snapshot basi di register hilir + kodefikasi FK aset. "
            "Total di sini menyatukan hitungan; detail per temuan tersedia di "
            "endpoint /integritas/* masing-masing. Tak mengubah data."),
    }


@audit_router.get("/integritas/ekspor-ringkasan")
async def integritas_ekspor_ringkasan(_user: dict = Depends(require_user)):
    """Ekspor CSV dasbor integritas §5A (READ-ONLY, pola #158): satu baris per
    register (jumlah temuan + rincian per masalah) + baris TOTAL. Untuk arsip /
    tindak lanjut kesehatan data. Sumber `bagian` sama dengan `/integritas/
    ringkasan`. Tak mengubah data."""
    import csv as csv_module
    import io
    from fastapi.responses import Response as HttpResponse

    hasil = gabung_temuan_integritas(await _kumpulkan_bagian_integritas())
    buf = io.StringIO()
    w = csv_module.writer(buf)
    for row in ringkasan_csv_baris(hasil, LABEL_MASALAH_INTEGRITAS):
        w.writerow(row)
    return HttpResponse(
        content=buf.getvalue().encode("utf-8-sig"), media_type="text/csv",
        headers={"Content-Disposition":
                 'attachment; filename="ringkasan_integritas.csv"'})
