"""Integrasi Meilisearch — mesin pencari eksternal OPSIONAL & ber-feature-flag.

MENGAPA
-------
Pencarian teks bebas AMAN memakai regex infix (`$regex` `$options:"i"`) pada
belasan field. Regex infix TIDAK bisa memanfaatkan index B-tree Mongo, jadi
pada koleksi besar setiap pencarian memaksa COLLSCAN (pindai penuh dalam
lingkup satker). Mongo self-hosted di VPS ini TIDAK punya Atlas Search, maka
"padanan trigram/n-gram" yang benar adalah mesin pencari eksternal —
**Meilisearch**: toleransi typo + pencocokan prefiks, sangat cepat.

FEATURE FLAG (tidak ada yang rusak bila mati)
--------------------------------------------
Aktif HANYA bila `MEILI_URL` **dan** `MEILI_MASTER_KEY` ter-set di `backend/.env`.
Bila salah satu kosong → seluruh fungsi jadi no-op dan pencarian JATUH-BALIK ke
regex Mongo lama. Bila Meilisearch mati / menolak / lambat, jalur pencarian
juga jatuh-balik ke Mongo (best-effort). Rollback = hapus 2 variabel env itu.

ARSITEKTUR
----------
- **Pencarian**: Meili me-resolve teks bebas → daftar `id` kandidat (sudah
  ter-scope satker), lalu id itu DIUMPANKAN ke kueri Mongo yang SUDAH ADA
  (`{"id": {"$in": [...]}}`). SEMUA filter lanjutan, sort, paginasi, dan
  isolasi-satker tetap dijalankan Mongo (otoritatif) — Meili hanya akselerator
  pencocokan teks, bukan sumber kebenaran. Ini menjaga izin & filter tak pernah
  drift.
- **Sinkronisasi**: hook best-effort NON-BLOCKING pada CRUD (buat/ubah/hapus)
  via `jadwalkan_sync` / `jadwalkan_hapus` (fire-and-forget). Kegagalan sinkron
  TIDAK menggagalkan permintaan; reindex massal menambal selisih.
- **Reindex massal**: `reindex_koleksi()` dipanggil endpoint admin / skrip CLI.

KEAMANAN
--------
Master key hanya dipakai sisi server (backend tepercaya) — tak pernah dikirim
ke browser. Filter scope satker dibangun DI SINI dan tetap ditegakkan lagi oleh
kueri Mongo, sehingga hasil Meili tak bisa membocorkan data lintas-satker.
"""
import os
import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from typing import Optional

import httpx

from db import db

logger = logging.getLogger(__name__)

# ── Feature flag & konfigurasi (dibaca sekali saat import) ──────────────────
MEILI_URL = (os.environ.get("MEILI_URL") or "").strip().rstrip("/")
MEILI_MASTER_KEY = (os.environ.get("MEILI_MASTER_KEY") or "").strip()

# Batas jumlah id kandidat yang diambil dari Meili per pencarian. Meili membatasi
# paginasi lewat `pagination.maxTotalHits` (bawaan 1000) — kita naikkan & minta
# limit sebesar ini agar daftar kandidat cukup lengkap untuk paginasi Mongo.
# Kata kunci biasanya menyempit jauh; bila hasil melebihi ambang ini yang
# ditampilkan adalah kandidat paling relevan (tetap jauh lebih baik dari
# COLLSCAN). Bisa di-override lewat env untuk satker sangat besar.
try:
    MEILI_MAX_HITS = min(10000, max(100, int(os.environ.get("MEILI_MAX_HITS") or "5000")))
except (TypeError, ValueError):
    MEILI_MAX_HITS = 5000

# Literal substring is the existing Mongo contract. Prefix/typo is a distinct,
# explicit opt-in; it never silently replaces literal search after activation.
MEILI_SEARCH_SEMANTICS = os.environ.get("MEILI_SEARCH_SEMANTICS", "literal").strip()

# Timeout ketat: pencarian harus instan; sinkron tulis tak boleh menahan request.
_TIMEOUT = httpx.Timeout(5.0, connect=2.0)

# ── Registry indeks per koleksi ─────────────────────────────────────────────
# `searchable`: field teks yang dicocokkan (mirror daftar $or regex lama).
# `filterable`: field untuk scope isolasi satker (WAJIB agar hasil tak bocor).
# `key`      : primary key dokumen Meili (= field `id` aplikasi).
# `tanpa_typo`: field IDENTITAS (nomor/kode/NIP). Toleransi typo bawaan Meili
# menganggap dua kode yang beda satu karakter itu "cocok" — NUP 00012 ikut
# memunculkan 00013, dan kode barang berbeda satu digit saling tertukar. Untuk
# identitas, salah satu karakter = barang LAIN, jadi typo dimatikan di sana.
INDEKS = {
    "assets": {
        "uid": "aman_assets",
        "key": "id",
        # Mirror FIELD_CARI_ASET di routes/assets.py — bila berbeda, hasil
        # pencarian akan berubah tergantung Meili hidup atau mati.
        "searchable": [
            "asset_code", "NUP", "asset_name", "serial_number", "location",
            "brand", "model", "category", "eselon1", "eselon2", "eselon3",
            "eselon4", "eselon5", "user",
            "pengguna_jabatan", "supplier",
            "perolehan_dari_nama", "condition", "status", "nomor_spm",
            "kode_register", "nomor_kontrak", "nomor_bast",
            "nomor_bukti_perolehan", "notes", "year",
        ],
        "tanpa_typo": [
            "asset_code", "NUP", "serial_number", "nomor_spm",
            "kode_register", "nomor_kontrak", "nomor_bast",
            "nomor_bukti_perolehan",
        ],
        "filterable": ["activity_id"],
    },
    "surat": {
        "uid": "aman_surat",
        "key": "id",
        "searchable": [
            "nomor", "perihal", "tujuan", "pengirim", "referensi",
            "nama_kegiatan", "nomor_eksternal", "keterangan",
        ],
        "tanpa_typo": ["nomor", "nomor_eksternal"],
        "filterable": ["kode_satker"],
    },
    "persediaan": {
        "uid": "aman_persediaan",
        "key": "id",
        "searchable": [
            "kode_barang", "nama_barang", "merk", "tipe", "lokasi", "keterangan",
        ],
        "tanpa_typo": ["kode_barang"],
        "filterable": ["kode_satker"],
    },
}

# Nama koleksi Mongo sumber untuk reindex massal (sengaja eksplisit).
_MONGO_COL = {"assets": "assets", "surat": "surat", "persediaan": "persediaan"}


def meili_aktif() -> bool:
    """True bila Meilisearch dikonfigurasi (URL + master key ter-set)."""
    return bool(MEILI_URL and MEILI_MASTER_KEY)


# ── Proyeksi dokumen: hanya field yang diindeks (hemat payload & privasi) ────
def proyeksi_dokumen(koleksi: str, doc: dict) -> Optional[dict]:
    """Ambil HANYA {id + searchable + filterable} dari dokumen sumber untuk
    dikirim ke Meili. Mengembalikan None bila konfigurasi/koleksi/id tak valid.

    - Nilai None dipangkas (Meili tak perlu menyimpan field kosong).
    - `filterable` yang hilang di-set "" agar filter scope (mis. kode_satker
      era-lama) tetap cocok dengan `IN ["<kode>", ""]` alih-alih null."""
    cfg = INDEKS.get(koleksi)
    if not cfg or not isinstance(doc, dict):
        return None
    doc_id = str(doc.get(cfg["key"]) or "").strip()
    if not doc_id:
        return None
    keluar = {"id": doc_id}
    for f in cfg["searchable"]:
        v = doc.get(f)
        if v is not None and v != "":
            keluar[f] = v
    for f in cfg["filterable"]:
        # Selalu sertakan field filter (walau kosong) → dinormalkan ke string.
        keluar[f] = str(doc.get(f) or "").strip()
    return keluar


# ── Pembangun filter scope satker (string ekspresi filter Meili) ────────────
def _kutip(nilai: str) -> str:
    """Bungkus nilai sebagai literal string filter Meili (escape aman)."""
    s = str(nilai or "")
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _filter_in(field: str, nilai_list) -> str:
    """Bangun ekspresi `field IN [..]` dari daftar nilai (sudah di-kutip)."""
    isi = ", ".join(_kutip(v) for v in nilai_list)
    return f"{field} IN [{isi}]"


# ── Klien HTTP (singleton malas; httpx tak terikat event-loop tertentu) ─────
_client: Optional[httpx.AsyncClient] = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=MEILI_URL,
            timeout=_TIMEOUT,
            headers={"Authorization": f"Bearer {MEILI_MASTER_KEY}"},
        )
    return _client


async def tutup_client() -> None:
    """Tutup klien HTTP saat shutdown aplikasi (dipanggil server.py)."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        finally:
            _client = None


async def _req(method: str, path: str, *, json=None, params=None):
    """Panggil REST API Meili. Mengembalikan Response; melempar untuk 4xx/5xx.
    Pemanggil membungkus dengan try/except (best-effort)."""
    r = await _http().request(method, path, json=json, params=params)
    r.raise_for_status()
    return r


class MeiliTaskError(RuntimeError):
    def __init__(self, task_id, task):
        self.code = (task.get("error") or {}).get("code", "")
        super().__init__(f"Meili task {task_id} {task.get('status')}: {self.code}")


async def _submit(method, path, *, json=None):
    """HTTP202 only queues work. Advance durable state after succeeded, never before."""
    response = await _req(method, path, json=json)
    task_id = (response.json() or {}).get("taskUid")
    if task_id is None:
        raise RuntimeError("Meili mutation did not return a task identity")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        task = (await _req("GET", f"/tasks/{task_id}")).json() or {}
        if task.get("status") == "succeeded":
            return task
        if task.get("status") in {"failed", "canceled"}:
            raise MeiliTaskError(task_id, task)
        await asyncio.sleep(0.1)
    raise TimeoutError(f"Meili task {task_id} acknowledgement timeout")


# ── Penyiapan indeks (idempoten) ────────────────────────────────────────────
async def pastikan_indeks() -> None:
    """Buat indeks + terapkan setelan (searchable/filterable/pagination).
    Idempoten & best-effort — aman dipanggil tiap startup. Tidak me-reindex
    data (itu tugas reindex massal)."""
    if not meili_aktif():
        return
    for koleksi, cfg in INDEKS.items():
        try:
            # Buat indeks (abaikan bila sudah ada).
            try:
                await _submit("POST", "/indexes",
                           json={"uid": cfg["uid"], "primaryKey": cfg["key"]})
            except MeiliTaskError as e:
                if e.code != "index_already_exists":
                    raise
            except httpx.HTTPStatusError as e:
                # 'index_already_exists' → sudah ada, bukan kegagalan.
                if e.response.status_code not in (409,):
                    kode = ""
                    try:
                        kode = (e.response.json() or {}).get("code", "")
                    except Exception:
                        pass
                    if kode != "index_already_exists":
                        raise
            # Terapkan setelan (searchable/filterable + naikkan maxTotalHits
            # + matikan toleransi typo pada field identitas).
            await _submit("PATCH", f"/indexes/{cfg['uid']}/settings", json={
                "searchableAttributes": cfg["searchable"],
                "filterableAttributes": cfg["filterable"],
                "pagination": {"maxTotalHits": MEILI_MAX_HITS},
                "typoTolerance": {
                    "enabled": True,
                    "disableOnAttributes": list(cfg.get("tanpa_typo") or []),
                },
            })
        except Exception as e:
            logger.warning("Meili: gagal siapkan indeks %s (non-fatal): %s",
                           cfg["uid"], e)


# ── Pencarian: teks bebas → daftar id kandidat ──────────────────────────────
async def kandidat_pencarian(koleksi, q, filter_expr=None):
    """Explicit completeness contract, consumed by the compatibility adapter.

    Even an exact estimatedTotalHits is not a proof of completeness. A full
    candidate page, missing acknowledgement, unfinished reconciliation or stale
    checkpoint falls back to authoritative Mongo (list/count/export together).
    """
    result = {"ids": [], "complete": False, "truncated": False, "lag_seconds": None,
              "semantics": "prefix_typo", "usable": False, "reason": "disabled"}
    cfg = INDEKS.get(koleksi)
    if not meili_aktif() or not cfg:
        return result
    if MEILI_SEARCH_SEMANTICS != "prefix_typo":
        result["reason"] = "literal_substring_requires_mongo"
        return result
    try:
        state = await db[_KOL_TANDA].find_one({"_id": koleksi}) or {}
        if state.get("force_mongo"):
            result["reason"] = "restore_requires_acknowledged_reindex"
            return result
        completed = state.get("completed_at")
        if isinstance(completed, datetime):
            if completed.tzinfo is None:
                completed = completed.replace(tzinfo=timezone.utc)
            result["lag_seconds"] = max(0, (datetime.now(timezone.utc) - completed).total_seconds())
        if not state.get("complete") or result["lag_seconds"] is None or result["lag_seconds"] > 300:
            result["reason"] = "incomplete_or_stale_checkpoint"
            return result
        body = {"q": q, "limit": MEILI_MAX_HITS, "attributesToRetrieve": ["id"],
                "matchingStrategy": "all"}
        if filter_expr:
            body["filter"] = filter_expr
        data = (await _req("POST", f"/indexes/{cfg['uid']}/search", json=body)).json() or {}
        hits = data.get("hits") or []
        result["ids"] = [str(hit["id"]) for hit in hits if hit.get("id")]
        estimate = data.get("estimatedTotalHits", data.get("totalHits"))
        result["truncated"] = len(hits) >= MEILI_MAX_HITS or (estimate is not None and estimate > len(hits))
        result["complete"] = not result["truncated"]
        result["usable"] = result["complete"]
        result["reason"] = "complete" if result["complete"] else "candidate_limit_or_partial_result"
    except Exception:
        result["reason"] = "engine_or_checkpoint_unavailable"
        logger.warning("Meili candidate unavailable for %s; using Mongo", koleksi)
    return result


async def _cari_id(koleksi: str, q: str, filter_expr: Optional[str]) -> Optional[list]:
    result = await kandidat_pencarian(koleksi, q, filter_expr)
    return result["ids"] if result["usable"] else None


async def cari_id_aset(user: dict, activity_id: str, search: str) -> Optional[list]:
    """Resolusi pencarian aset → id kandidat ter-scope satker.

    Scope (mirror `scope_query_aset`):
    - activity_id spesifik → filter `activity_id = <id>` (guard kepemilikan
      dilakukan endpoint terpisah).
    - user terikat satker → filter `activity_id IN [kegiatan-satker]`; bila
      satker tak punya kegiatan → `[]` (nihil kandidat).
    - super-admin lintas-satker → tanpa filter.
    None = fallback regex.
    """
    if not meili_aktif():
        return None
    filter_expr = None
    aid = str(activity_id or "").strip()
    kode = str((user or {}).get("kode_satker") or "").strip()
    if aid:
        filter_expr = f"activity_id = {_kutip(aid)}"
    elif kode:
        from shared_utils import id_kegiatan_satker
        ids = await id_kegiatan_satker(kode)
        if not ids:
            return []  # satker tanpa kegiatan → tak ada aset yang boleh dilihat
        filter_expr = _filter_in("activity_id", ids)
    return await _cari_id("assets", search, filter_expr)


def _filter_satker_dok(user: dict) -> Optional[str]:
    """Filter Meili untuk koleksi ber-`kode_satker` langsung (surat/persediaan),
    padanan `scope_query_field_satker` (`{"$in": [kode, "", None]}`). Dokumen
    era-lama diindeks dengan kode_satker="" sehingga cocok. None = tanpa filter
    (super-admin lintas-satker)."""
    kode = str((user or {}).get("kode_satker") or "").strip()
    if not kode:
        return None
    return _filter_in("kode_satker", [kode, ""])


async def cari_id_surat(user: dict, search: str) -> Optional[list]:
    """Resolusi pencarian surat → id kandidat ter-scope satker (None = fallback)."""
    if not meili_aktif():
        return None
    return await _cari_id("surat", search, _filter_satker_dok(user))


async def cari_id_persediaan(user: dict, search: str) -> Optional[list]:
    """Resolusi pencarian persediaan → id kandidat ter-scope satker."""
    if not meili_aktif():
        return None
    return await _cari_id("persediaan", search, _filter_satker_dok(user))


# ── Sinkronisasi dokumen (best-effort, fire-and-forget) ─────────────────────
_bg_tasks: set = set()


async def _sync_dokumen(koleksi: str, doc: dict) -> None:
    payload = proyeksi_dokumen(koleksi, doc)
    if payload is None:
        return
    cfg = INDEKS[koleksi]
    try:
        await _submit("POST", f"/indexes/{cfg['uid']}/documents", json=[payload])
    except Exception as e:
        logger.warning("Meili: sinkron dokumen %s/%s gagal (non-fatal): %s",
                       cfg["uid"], payload.get("id"), e)


async def _hapus_dokumen(koleksi: str, doc_id: str) -> None:
    cfg = INDEKS.get(koleksi)
    did = str(doc_id or "").strip()
    if not cfg or not did:
        return
    try:
        await _submit("DELETE", f"/indexes/{cfg['uid']}/documents/{did}")
    except Exception as e:
        logger.warning("Meili: hapus dokumen %s/%s gagal (non-fatal): %s",
                       cfg["uid"], did, e)


def _fire_and_forget(coro) -> None:
    """Jalankan coroutine tanpa menahan pemanggil; simpan referensi agar tak
    di-GC & tangani exception via callback (best-effort)."""
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError:
        # Tak ada event loop berjalan (mis. dipanggil dari konteks sync).
        coro.close()
        return
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def jadwalkan_sync(koleksi: str, doc: dict) -> None:
    """Jadwalkan upsert dokumen ke Meili (no-op bila nonaktif). Aman dipanggil
    di jalur tulis — tak pernah menggagalkan/menahan request."""
    if not meili_aktif():
        return
    _fire_and_forget(_sync_dokumen(koleksi, doc))


def jadwalkan_hapus(koleksi: str, doc_id: str) -> None:
    """Jadwalkan penghapusan dokumen dari Meili (no-op bila nonaktif)."""
    if not meili_aktif():
        return
    _fire_and_forget(_hapus_dokumen(koleksi, doc_id))


async def _sync_dari_mongo(koleksi: str, ids: list) -> None:
    """Baca ulang dokumen dari Mongo lalu kirim ke Meili (potongan 500)."""
    cfg = INDEKS.get(koleksi)
    nama_col = _MONGO_COL.get(koleksi)
    if not cfg or not nama_col or not ids:
        return
    col = getattr(db, nama_col)
    proyeksi = {"_id": 0, cfg["key"]: 1}
    for f in list(cfg["searchable"]) + list(cfg["filterable"]):
        proyeksi[f] = 1
    for i in range(0, len(ids), 500):
        potongan = ids[i:i + 500]
        docs = [d async for d in col.find({cfg["key"]: {"$in": potongan}}, proyeksi)]
        payload = [p for p in (proyeksi_dokumen(koleksi, d) for d in docs) if p]
        if not payload:
            continue
        try:
            await _submit("PUT", f"/indexes/{cfg['uid']}/documents", json=payload)
        except Exception as e:                       # noqa: BLE001
            logger.warning("Meili: sync massal %s gagal (non-fatal): %s",
                           cfg["uid"], e)
            return


def jadwalkan_sync_id(koleksi: str, ids) -> None:
    """Sinkron ulang dokumen berdasarkan ID — untuk jalur tulis MASSAL
    (`update_many`/`bulk_write`) yang tak memegang dokumen hasilnya.

    MENGAPA PENTING: tanpa ini indeks pencarian memegang nilai LAMA setelah
    ubah massal, sehingga barang yang baru saja diisi lokasinya tidak ketemu
    saat dicari — padahal datanya ADA di basis data. Gejalanya membingungkan
    karena aset yang kebetulan pernah diedit manual (jalur tunggal yang sudah
    sinkron) tetap ketemu. No-op bila Meili nonaktif.
    """
    if not meili_aktif():
        return
    daftar = [str(i) for i in (ids or []) if i]
    if not daftar:
        return
    _fire_and_forget(_sync_dari_mongo(koleksi, daftar))


# ── Reindex massal (dipanggil endpoint admin / skrip CLI) ───────────────────
_BATCH = 1000


async def reindex_koleksi(koleksi: str) -> dict:
    """Bounded full reconciliation, guarded by the same cross-worker lease.

    Rebuild starts by acknowledged deletion: obsolete documents cannot survive
    a reindex. Search uses Mongo while the index is rebuilding. Source writes
    remain available; subsequent bounded sweep revisits same-timestamp changes.
    """
    cfg = INDEKS.get(koleksi)
    if not meili_aktif() or not cfg:
        return {"koleksi": koleksi, "terindeks": 0, "aktif": meili_aktif()}
    state = await _claim(koleksi)
    if not state:
        return {"koleksi": koleksi, "terindeks": 0, "aktif": True, "busy": True}
    total = 0
    try:
        await _checkpoint(koleksi, state, {"complete": False})
        await pastikan_indeks()
        await _submit("DELETE", f"/indexes/{cfg['uid']}/documents")
        col = db[_MONGO_COL[koleksi]]
        cursor = ""
        while True:
            docs = await col.find({"id": {"$gt": cursor}} if cursor else {}, _projection(koleksi)).sort("id", 1).limit(_BATCH).to_list(_BATCH)
            if not docs:
                break
            payload = [p for p in (proyeksi_dokumen(koleksi, d) for d in docs) if p]
            if payload:
                await _submit("PUT", f"/indexes/{cfg['uid']}/documents", json=payload)
            total += len(payload)
            cursor = docs[-1]["id"]
            await _checkpoint(koleksi, state, {"reindex_last_id": cursor})
        # Incremental cycle must still reconcile writes/deletes concurrent to rebuild.
        await _checkpoint(koleksi, state, {"schema": 2, "phase": "legacy", "sejak": "", "last_id": "", "delete_offset": 0, "force_mongo": False})
        return {"koleksi": koleksi, "terindeks": total, "aktif": True, "complete": False}
    finally:
        await _release(koleksi, state)


async def reindex_semua() -> dict:
    """Reindex ketiga koleksi. Ringkasan per koleksi + total."""
    hasil = {}
    for koleksi in INDEKS:
        hasil[koleksi] = await reindex_koleksi(koleksi)
    hasil["total"] = sum(v.get("terindeks", 0) for v in hasil.values()
                         if isinstance(v, dict))
    return hasil


async def status_indeks() -> dict:
    """Status ringkas untuk endpoint admin: aktif? + jumlah dokumen per indeks."""
    if not meili_aktif():
        return {"aktif": False, "indeks": {}}
    out = {"aktif": True, "url": MEILI_URL, "max_hits": MEILI_MAX_HITS, "search_semantics": MEILI_SEARCH_SEMANTICS, "indeks": {}}
    for koleksi, cfg in INDEKS.items():
        try:
            r = await _req("GET", f"/indexes/{cfg['uid']}/stats")
            data = r.json() or {}
            sync_state = await db[_KOL_TANDA].find_one({"_id": koleksi}) or {}
            out["indeks"][koleksi] = {
                "complete": bool(sync_state.get("complete")) and not sync_state.get("force_mongo", False),
                "force_mongo": bool(sync_state.get("force_mongo")),
                "completed_at": str(sync_state.get("completed_at") or ""),
                "phase": sync_state.get("phase", "not_initialized"),
                "uid": cfg["uid"],
                "jumlah_dokumen": data.get("numberOfDocuments", 0),
                "sedang_indexing": data.get("isIndexing", False),
            }
        except Exception as e:
            out["indeks"][koleksi] = {"uid": cfg["uid"], "error": str(e)[:200]}
    return out


# ── Penyelaras inkremental (pagar sistemik) ─────────────────────────────────
# Hook sinkron per-dokumen mudah TERLEWAT di jalur tulis massal atau modul
# baru — dan begitu terlewat, barang yang ada di basis data tidak muncul saat
# dicari. Alih-alih mengandalkan setiap penulis ingat memanggil hook, penyelaras
# ini menyapu berkala: ambil dokumen yang `updated_at`-nya lebih baru dari
# tanda terakhir, kirim ke Meili, simpan tanda baru. Kueri memakai indeks
# updated_at, jadi murah walau dijalankan tiap beberapa menit.
_KOL_TANDA = "meili_sync_state"
# Kolom stempel waktu per koleksi (semua ISO-8601 string, terurut leksikografis).
_FIELD_WAKTU = {"assets": "updated_at", "surat": "updated_at",
                "persediaan": "updated_at"}
_BATAS_SAPUAN = 2000       # dokumen per koleksi per putaran (jaga latensi)


def _projection(koleksi):
    cfg = INDEKS[koleksi]
    return {"_id": 0, "id": 1, "updated_at": 1,
            **{field: 1 for field in cfg["searchable"] + cfg["filterable"]}}


async def invalidate_after_restore(database=None):
    """Await before opening restore admission, including successful rollback.

    Derivative state is never trusted after a dataset replacement. Fence old
    checkpoint owners and keep Mongo authoritative until explicit acked reindex.
    This intentionally fails the caller if Mongo cannot persist invalidation.
    """
    target = db if database is None else database
    for koleksi in INDEKS:
        await target[_KOL_TANDA].update_one({"_id": koleksi}, {"$set": {
            "schema": 2, "complete": False, "force_mongo": True, "phase": "legacy",
            "sejak": "", "last_id": "", "delete_offset": 0,
        }, "$unset": {"owner": "", "lease_until": "", "completed_at": ""}}, upsert=True)


async def _claim(koleksi):
    """_id uniqueness + compare-and-set expiry prevents checkpoint races."""
    now = datetime.now(timezone.utc)
    await db[_KOL_TANDA].update_one({"_id": koleksi}, {"$setOnInsert": {"schema": 2,
        "phase": "legacy", "sejak": "", "last_id": "", "complete": False}}, upsert=True)
    return await db[_KOL_TANDA].find_one_and_update(
        {"_id": koleksi, "$or": [{"lease_until": {"$lte": now}}, {"lease_until": {"$exists": False}}]},
        {"$set": {"owner": uuid.uuid4().hex, "lease_until": now + timedelta(seconds=120)}},
        return_document=ReturnDocument.AFTER)


async def _checkpoint(koleksi, state, fields):
    now = datetime.now(timezone.utc)
    result = await db[_KOL_TANDA].update_one({"_id": koleksi, "owner": state["owner"], "lease_until": {"$gt": now}},
        {"$set": {**fields, "lease_until": now + timedelta(seconds=120)}})
    if not result.matched_count:
        raise RuntimeError("Meili checkpoint lease lost")


async def _release(koleksi, state):
    await db[_KOL_TANDA].update_one({"_id": koleksi, "owner": state["owner"]},
        {"$unset": {"owner": "", "lease_until": ""}})


async def _reconcile_deletes(koleksi, state):
    cfg = INDEKS[koleksi]
    offset = state.get("delete_offset", 0)
    data = (await _req("GET", f"/indexes/{cfg['uid']}/documents",
                       params={"offset": offset, "limit": _BATAS_SAPUAN, "fields": "id"})).json() or {}
    documents = data.get("results") or []
    ids = [str(doc["id"]) for doc in documents if doc.get("id")]
    existing = {doc["id"] async for doc in db[_MONGO_COL[koleksi]].find({"id": {"$in": ids}}, {"_id": 0, "id": 1})} if ids else set()
    missing = [did for did in ids if did not in existing]
    if missing:
        await _submit("POST", f"/indexes/{cfg['uid']}/documents/delete-batch", json=missing)
        # Deletion shifts offsets. Read this page again next turn.
        await _checkpoint(koleksi, state, {"delete_offset": offset})
    elif len(documents) >= _BATAS_SAPUAN:
        await _checkpoint(koleksi, state, {"delete_offset": offset + len(documents)})
    else:
        await _checkpoint(koleksi, state, {"complete": True, "completed_at": datetime.now(timezone.utc),
            "phase": "legacy", "sejak": "", "last_id": "", "delete_offset": 0})


async def selaraskan_inkremental() -> dict:
    """Bounded cursor (updated_at,id), acknowledged tasks, cross-worker lease.

    Complete cycles revisit timestamps from the beginning. A write with the
    same timestamp behind the current cursor therefore waits at most one cycle,
    rather than being lost forever. Legacy timestamp-only checkpoints start a
    bounded full cycle. Every cycle also removes deleted IDs, including deletes
    while the engine was down; no volatile fire-and-forget receipt is trusted.
    """
    hasil = {}
    if not meili_aktif():
        return hasil
    for koleksi, cfg in INDEKS.items():
        state = None
        try:
            state = await _claim(koleksi)
            if not state:
                continue
            if state.get("schema") != 2:
                await _checkpoint(koleksi, state, {"schema": 2, "phase": "legacy", "sejak": "", "last_id": "", "complete": False})
                state.update(schema=2, phase="legacy", sejak="", last_id="", complete=False)
            phase = state.get("phase", "legacy")
            if phase == "deletes":
                await _reconcile_deletes(koleksi, state)
                hasil[koleksi] = 0
                continue
            last_id = state.get("last_id", "")
            since = state.get("sejak", "")
            if phase == "legacy":
                query = {"updated_at": {"$in": [None, ""]}}
                if last_id:
                    query["id"] = {"$gt": last_id}
                sort = [("id", 1)]
            else:
                query = {"$or": [{"updated_at": {"$gt": since}}, {"updated_at": since, "id": {"$gt": last_id}}]} if since else {"updated_at": {"$gt": ""}}
                sort = [("updated_at", 1), ("id", 1)]
            docs = await db[_MONGO_COL[koleksi]].find(query, _projection(koleksi)).sort(sort).limit(_BATAS_SAPUAN).to_list(_BATAS_SAPUAN)
            payload = [p for p in (proyeksi_dokumen(koleksi, doc) for doc in docs) if p]
            if payload:
                await _submit("PUT", f"/indexes/{cfg['uid']}/documents", json=payload)
            fields = {"complete": False}
            if len(docs) < _BATAS_SAPUAN:
                fields.update(phase="updates" if phase == "legacy" else "deletes", last_id="", sejak="", delete_offset=0)
            else:
                fields.update(last_id=docs[-1]["id"], sejak=str(docs[-1].get("updated_at") or ""))
            await _checkpoint(koleksi, state, fields)
            hasil[koleksi] = len(payload)
        except Exception:
            logger.warning("Meili reconciliation %s failed; checkpoint retained", koleksi, exc_info=True)
        finally:
            if state:
                await _release(koleksi, state)
    return hasil
