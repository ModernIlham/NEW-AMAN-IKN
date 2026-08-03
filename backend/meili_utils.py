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
    MEILI_MAX_HITS = max(100, int(os.environ.get("MEILI_MAX_HITS") or "5000"))
except (TypeError, ValueError):
    MEILI_MAX_HITS = 5000

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
            "brand", "model", "category", "eselon1", "eselon2", "user",
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
                await _req("POST", "/indexes",
                           json={"uid": cfg["uid"], "primaryKey": cfg["key"]})
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
            await _req("PATCH", f"/indexes/{cfg['uid']}/settings", json={
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
async def _cari_id(koleksi: str, q: str, filter_expr: Optional[str]) -> Optional[list]:
    """Kembalikan daftar id kandidat dari Meili (terurut relevansi), atau None
    bila Meili nonaktif/gagal (sinyal agar pemanggil jatuh-balik ke regex).
    Daftar KOSONG `[]` berarti 'tak ada kecocokan' (bukan sinyal fallback)."""
    cfg = INDEKS.get(koleksi)
    if not meili_aktif() or not cfg:
        return None
    body = {
        "q": q,
        "limit": MEILI_MAX_HITS,
        "attributesToRetrieve": ["id"],
        # SEMUA kata wajib ada. Bawaan Meili ("last") membuang kata dari akhir
        # kueri sampai hasil dianggap cukup — mengetik lebih spesifik justru
        # memunculkan dokumen yang tak memuat kata terakhir, dan hasilnya
        # berbeda dari jalur regex Mongo. "all" menyamakan keduanya.
        "matchingStrategy": "all",
    }
    if filter_expr:
        body["filter"] = filter_expr
    try:
        r = await _req("POST", f"/indexes/{cfg['uid']}/search", json=body)
        hits = (r.json() or {}).get("hits") or []
        return [str(h.get("id")) for h in hits if h.get("id")]
    except Exception as e:
        logger.warning("Meili: pencarian %s gagal → fallback regex Mongo: %s",
                       cfg["uid"], e)
        return None


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
        await _req("POST", f"/indexes/{cfg['uid']}/documents", json=[payload])
    except Exception as e:
        logger.warning("Meili: sinkron dokumen %s/%s gagal (non-fatal): %s",
                       cfg["uid"], payload.get("id"), e)


async def _hapus_dokumen(koleksi: str, doc_id: str) -> None:
    cfg = INDEKS.get(koleksi)
    did = str(doc_id or "").strip()
    if not cfg or not did:
        return
    try:
        await _req("DELETE", f"/indexes/{cfg['uid']}/documents/{did}")
    except Exception as e:
        logger.warning("Meili: hapus dokumen %s/%s gagal (non-fatal): %s",
                       cfg["uid"], did, e)


def _fire_and_forget(coro) -> None:
    """Jalankan coroutine tanpa menahan pemanggil; simpan referensi agar tak
    di-GC & tangani exception via callback (best-effort)."""
    try:
        task = asyncio.ensure_future(coro)
    except RuntimeError:
        # Tak ada event loop berjalan (mis. dipanggil dari konteks sync) — abaikan.
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
            await _req("PUT", f"/indexes/{cfg['uid']}/documents", json=payload)
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
    """Bangun ulang indeks satu koleksi dari Mongo (semua satker; scope
    ditegakkan saat pencarian). Mengembalikan ringkasan {koleksi, terindeks}."""
    cfg = INDEKS.get(koleksi)
    if not meili_aktif() or not cfg:
        return {"koleksi": koleksi, "terindeks": 0, "aktif": meili_aktif()}
    await pastikan_indeks()
    col = db[_MONGO_COL[koleksi]]
    proj = {"_id": 0, cfg["key"]: 1, **{f: 1 for f in cfg["searchable"]},
            **{f: 1 for f in cfg["filterable"]}}
    total = 0
    batch = []
    async for doc in col.find({}, proj):
        payload = proyeksi_dokumen(koleksi, doc)
        if payload is None:
            continue
        batch.append(payload)
        if len(batch) >= _BATCH:
            await _req("POST", f"/indexes/{cfg['uid']}/documents", json=batch)
            total += len(batch)
            batch = []
    if batch:
        await _req("POST", f"/indexes/{cfg['uid']}/documents", json=batch)
        total += len(batch)
    logger.info("Meili: reindex %s selesai — %d dokumen dikirim", cfg["uid"], total)
    return {"koleksi": koleksi, "terindeks": total, "aktif": True}


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
    out = {"aktif": True, "url": MEILI_URL, "max_hits": MEILI_MAX_HITS, "indeks": {}}
    for koleksi, cfg in INDEKS.items():
        try:
            r = await _req("GET", f"/indexes/{cfg['uid']}/stats")
            data = r.json() or {}
            out["indeks"][koleksi] = {
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


async def selaraskan_inkremental() -> dict:
    """Sinkronkan dokumen yang berubah sejak sapuan terakhir. Aman dipanggil
    berkala; no-op bila Meili nonaktif. Mengembalikan {koleksi: jumlah}."""
    hasil = {}
    if not meili_aktif():
        return hasil
    for koleksi, cfg in INDEKS.items():
        field_waktu = _FIELD_WAKTU.get(koleksi)
        nama_col = _MONGO_COL.get(koleksi)
        if not field_waktu or not nama_col:
            continue
        try:
            tanda_doc = await db[_KOL_TANDA].find_one({"_id": koleksi})
            sejak = (tanda_doc or {}).get("sejak") or ""
            col = getattr(db, nama_col)
            proyeksi = {"_id": 0, cfg["key"]: 1, field_waktu: 1}
            for f in list(cfg["searchable"]) + list(cfg["filterable"]):
                proyeksi[f] = 1
            kueri = {field_waktu: {"$gt": sejak}} if sejak else {}
            docs = [d async for d in col.find(kueri, proyeksi)
                    .sort(field_waktu, 1).limit(_BATAS_SAPUAN)]
            if not docs:
                continue
            payload = [p for p in (proyeksi_dokumen(koleksi, d) for d in docs) if p]
            if payload:
                await _req("PUT", f"/indexes/{cfg['uid']}/documents", json=payload)
            # Tanda baru = stempel terbesar yang BENAR-BENAR terkirim.
            terbaru = max((str(d.get(field_waktu) or "") for d in docs), default="")
            if terbaru:
                await db[_KOL_TANDA].update_one(
                    {"_id": koleksi}, {"$set": {"sejak": terbaru}}, upsert=True)
            hasil[koleksi] = len(payload)
        except Exception as e:      # noqa: BLE001
            logger.warning("Meili: selaras inkremental %s gagal (non-fatal): %s",
                           koleksi, e)
    return hasil
