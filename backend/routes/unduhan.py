"""PUSAT UNDUHAN — unduhan berat sebagai job latar ber-progres + retensi 30 hari.

Masalah yang diselesaikan: unduhan laporan besar (PDF eksekutif, ekspor
berfoto, ZIP batch) sering putus "Waktu unduh habis" karena file digenerate
SAAT request dan koneksi/timeout klien membatasinya. Di sini file digenerate
DI SERVER sebagai job latar:

  POST /api/unduhan/mulai {path, nama_file, label}
      → job antre; worker memanggil endpoint GET internal `path` (in-process,
        httpx.ASGITransport — tetap melewati routing + auth + isolasi satker
        karena header Authorization/X-Satker-Aktif pemohon DITERUSKAN apa
        adanya, hanya di memori, tidak pernah disimpan ke DB) lalu menyimpan
        hasilnya ke GridFS.
  GET  /api/unduhan             → log unduhan milik user (Pusat Unduhan).
  GET  /api/unduhan/{id}/file   → unduh hasil KAPAN SAJA tanpa generate ulang.
  DELETE /api/unduhan/{id}      → hapus entri + file hasilnya.

Keandalan file banyak & besar:
  - antrean: maksimal 2 job diproses bersamaan (semaphore) + jeda 2 detik
    sebelum tiap job supaya server bernapas; sisanya menunggu giliran;
  - maksimal 3 job aktif per pengguna (409 bila melebihi);
  - plafon hasil 500 MB; timeout internal 30 menit;
  - 429 dari rate-limiter endpoint laporan di dalam → dicoba ulang hingga
    3x mengikuti Retry-After.

Retensi ("terurai jadi nol setelah 1 bulan"): dokumen `unduhan` ber-TTL
per-dokumen `hapus_pada` (= dibuat + 30 hari, expireAfterSeconds=0 di
indexes.py); blob GridFS-nya disapu `bersihkan_unduhan_kedaluwarsa()` yang
menumpang loop pemeliharaan jobs.py — blob yatim (dokumen sudah di-TTL)
ikut terhapus sehingga disk kembali nol.
"""
import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

import httpx
from bson import ObjectId

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth_utils import require_user, require_user_or_query_token
from db import db
from shared_utils import (fs_bucket, kode_satker_user, limiter,
                          nama_file_disposition)

logger = logging.getLogger(__name__)
unduhan_router = APIRouter()
_COL = db.unduhan

RETENSI_HARI = 30
# Cap job aktif per user = 1 agar TAK PERNAH melebihi kapasitas satu worker
# (temuan review: cap 3 > slot 2 = satu akun bisa membuat lapar tenant lain).
MAKS_AKTIF_PER_USER = 1
MAKS_UKURAN = 200 * 1024 * 1024          # plafon hasil 200 MB
TIMEOUT_INTERNAL = 1800.0                 # 30 menit per job (ditegakkan asyncio.timeout)
JEDA_ANTAR_JOB = 2.0                      # server bernapas di antara job
HEARTBEAT_DETIK = 60.0                    # denyut updated_at agar tak di-relabel macet
# Maks 1 job diproses per PROSES uvicorn. Dengan N worker → N job global
# (deploy VPS 2 worker → 2). Angka 1 dipilih sengaja agar cap per-user (1) tak
# pernah bisa menyaturasi seluruh worker.
_SEM = asyncio.Semaphore(1)
_TASKS = set()                            # strong-ref agar task tak di-GC

# Path API internal yang boleh dipanggil worker: relatif terhadap /api, hanya
# GET, tanpa traversal/skema, dan bukan area sensitif. '%' TIDAK diizinkan di
# segmen PATH (hanya di query-string) — mencegah bypass blocklist via
# percent-encoding; path tetap di-unquote lagi sebelum dicek untuk berjaga.
_PATH_RE = re.compile(r"^/[A-Za-z0-9_\-./]*(\?[A-Za-z0-9_\-.%=&+,:/ ]*)?$")
_TERLARANG = ("/auth", "/backup", "/unduhan", "/jobs", "/users", "/admin")


def path_unduhan_valid(path: str) -> bool:
    """True bila `path` aman dipanggil worker sebagai GET /api<path>.

    Validasi dilakukan pada bentuk TERDEKODE — httpx.ASGITransport merutekan
    berdasarkan `scope['path']` yang sudah di-percent-decode, jadi kalau kita
    hanya memeriksa string mentah, `/%75sers/list` (%75='u') lolos blocklist
    tetapi tetap mencapai `/api/users/list`."""
    if not isinstance(path, str) or not path.startswith("/"):
        return False
    if len(path) > 2000 or not _PATH_RE.match(path):
        return False
    raw = path.split("?", 1)[0]
    murni_dec = unquote(raw)      # samakan dengan scope['path'] Starlette
    if ("%" in murni_dec or ".." in murni_dec or "://" in murni_dec
            or "\\" in murni_dec):
        return False              # sisa encoding (mis. %252e) / traversal
    murni = murni_dec.rstrip("/") or "/"
    return not any(murni == t or murni.startswith(t + "/") for t in _TERLARANG)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt):
    """Samakan datetime (aware/naive) ke naive-UTC agar bisa dibandingkan —
    motor mengembalikan BSON datetime sebagai naive-UTC."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


async def _update(unduhan_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    await _COL.update_one({"unduhan_id": unduhan_id}, {"$set": fields})


def _potong_detail(teks, maks: int = 300) -> str:
    """Ringkas pesan galat respons internal (JSON {detail} atau teks)."""
    import json
    if isinstance(teks, bytes):
        try:
            teks = teks.decode("utf-8", "replace")
        except Exception:
            teks = ""
    try:
        d = json.loads(teks or "")
        if isinstance(d, dict) and d.get("detail"):
            teks = str(d["detail"])
    except Exception:
        pass
    return str(teks or "").strip()[:maks]


class MulaiUnduhanIn(BaseModel):
    path: str = Field(min_length=1, max_length=2000)
    nama_file: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=200)


def _boleh_akses(doc: dict, user: dict) -> bool:
    """Pemilik, atau admin dari satker yang SAMA (fail-closed — pola sama
    dengan routes/jobs.py: dokumen tanpa stempel tertutup bagi admin satker)."""
    pemilik = str(doc.get("dibuat_oleh") or "").strip()
    username = str(user.get("username") or "").strip()
    if pemilik and username and pemilik == username:
        return True
    if str(user.get("role") or "") in ("admin", "super_admin"):
        milik = str(doc.get("kode_satker") or "").strip()
        kode = kode_satker_user(user)
        if not kode:
            return True          # super-admin pusat: lintas satker
        return bool(milik) and milik == kode
    return False


def _app_internal():
    """Aplikasi FastAPI untuk panggilan internal — lazy import (server
    meng-impor router ini, jadi impor modul-atas akan melingkar)."""
    from server import app
    return app


async def _denyut(unduhan_id: str):
    """Perbarui updated_at berkala selama job hidup (antre di belakang _SEM
    maupun fase generate yang buffered tanpa progres) agar sapuan tak
    salah me-relabel job yang masih berjalan sebagai macet."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_DETIK)
            await _COL.update_one({"unduhan_id": unduhan_id},
                                  {"$set": {"updated_at": _now()}})
    except asyncio.CancelledError:
        raise
    except Exception:       # denyut best-effort — tak boleh menjatuhkan job
        pass


async def _ambil_dan_simpan(unduhan_id: str, path: str, headers: dict) -> None:
    """Panggil endpoint internal, alirkan hasil LANGSUNG ke GridFS (tanpa
    menampung dua kali di RAM), stempel metadata unduhan_id."""
    transport = httpx.ASGITransport(app=_app_internal())
    async with httpx.AsyncClient(transport=transport,
                                 base_url="http://internal") as klien:
        for percobaan in range(3):
            async with klien.stream("GET", f"/api{path}",
                                     headers=headers) as r:
                if r.status_code == 429 and percobaan < 2:
                    # Rate-limiter endpoint laporan — tunggu lalu ulangi.
                    try:
                        tunggu = float(r.headers.get("retry-after") or 30)
                    except ValueError:
                        tunggu = 30.0
                    await r.aread()
                    await _update(unduhan_id,
                                  message="Server sibuk — menunggu "
                                          f"{int(tunggu)} detik")
                    await asyncio.sleep(min(tunggu, 120.0))
                    continue
                if r.status_code != 200:
                    badan = await r.aread()
                    raise RuntimeError(
                        f"HTTP {r.status_code}: "
                        f"{_potong_detail(badan) or 'galat server'}")
                ctype = (r.headers.get("content-type")
                         or "application/octet-stream").split(";")[0].strip()
                doc = await _COL.find_one({"unduhan_id": unduhan_id},
                                          {"_id": 0, "nama_file": 1})
                nama = (doc or {}).get("nama_file") or "unduhan.bin"
                file_id = ObjectId()
                keluar = fs_bucket.open_upload_stream_with_id(
                    file_id, filename=nama,
                    metadata={"content_type": ctype, "unduhan_id": unduhan_id})
                terunduh = 0
                t_lapor = 0.0
                try:
                    async for potongan in r.aiter_bytes(65536):
                        if terunduh + len(potongan) > MAKS_UKURAN:
                            raise RuntimeError("Hasil melebihi plafon 200 MB")
                        await keluar.write(potongan)      # langsung ke GridFS
                        terunduh += len(potongan)
                        kini = time.monotonic()
                        if kini - t_lapor > 1.5:
                            t_lapor = kini
                            await _update(
                                unduhan_id, ukuran=terunduh,
                                message="Menyusun file… "
                                        f"{terunduh // 1024:,} KB".replace(
                                            ",", "."))
                    await keluar.close()
                except BaseException:
                    # Batalkan unggahan parsial agar tak meninggalkan chunk
                    # GridFS yatim saat gagal/timeout/plafon terlampaui.
                    try:
                        await keluar.abort()
                    except Exception:
                        pass
                    raise
                await _update(unduhan_id, status="done", progress=100,
                              ukuran=terunduh, artifact_id=str(file_id),
                              artifact_type=ctype, message="Selesai")
                return
        raise RuntimeError("Server sibuk — coba lagi nanti")


async def _jalankan_unduhan(unduhan_id: str, path: str, headers: dict) -> None:
    """Worker: panggil endpoint internal, simpan hasil ke GridFS.

    `headers` (Authorization + X-Satker-Aktif pemohon) hanya hidup di closure
    task ini — TIDAK pernah ditulis ke database."""
    async with _SEM:
        await asyncio.sleep(JEDA_ANTAR_JOB)
        denyut = asyncio.create_task(_denyut(unduhan_id))
        try:
            await _update(unduhan_id, status="running",
                          message="Menyusun file di server")
            # asyncio.timeout MENEGAKKAN batas (httpx.Timeout DIABAIKAN oleh
            # ASGITransport) → slot _SEM pasti lepas walau endpoint menggantung.
            async with asyncio.timeout(TIMEOUT_INTERNAL):
                await _ambil_dan_simpan(unduhan_id, path, headers)
        except asyncio.TimeoutError:
            logger.warning("Unduhan %s: melebihi batas waktu", unduhan_id)
            try:
                await _update(unduhan_id, status="error", message="Gagal",
                              error_message="Melebihi batas 30 menit — coba "
                                            "persempit rentang lalu ulangi")
            except Exception:
                pass
        except Exception as e:      # noqa: BLE001 — job tak boleh mati senyap
            logger.warning("Unduhan %s gagal: %s", unduhan_id, e)
            try:
                await _update(unduhan_id, status="error",
                              error_message=str(e)[:300], message="Gagal")
            except Exception:
                pass
        finally:
            denyut.cancel()
            try:
                await denyut
            except (asyncio.CancelledError, Exception):
                pass


@unduhan_router.post("/unduhan/mulai")
@limiter.limit("10/minute")
async def mulai_unduhan(payload: MulaiUnduhanIn, request: Request,
                        user: dict = Depends(require_user)):
    """Daftarkan unduhan berat sebagai job latar; kembalikan {unduhan_id}."""
    if not path_unduhan_valid(payload.path):
        raise HTTPException(status_code=400, detail="Path unduhan tidak valid")
    username = str(user.get("username") or "")
    aktif = await _COL.count_documents(
        {"dibuat_oleh": username, "status": {"$in": ["queued", "running"]}})
    if aktif >= MAKS_AKTIF_PER_USER:
        raise HTTPException(
            status_code=409,
            detail=f"Maksimal {MAKS_AKTIF_PER_USER} unduhan berjalan "
                   "bersamaan — tunggu yang lain selesai")
    unduhan_id = uuid.uuid4().hex
    kini = _now()
    await _COL.insert_one({
        "unduhan_id": unduhan_id,
        "label": payload.label or payload.nama_file,
        "nama_file": payload.nama_file,
        "path": payload.path,
        "status": "queued", "message": "Menunggu giliran",
        "ukuran": 0,
        "dibuat_oleh": username,
        "kode_satker": kode_satker_user(user),
        "created_at": kini, "updated_at": kini,
        "hapus_pada": kini + timedelta(days=RETENSI_HARI),
    })
    # Header auth pemohon diteruskan ke panggilan internal (di memori saja).
    headers = {}
    auth = request.headers.get("authorization")
    if auth:
        headers["authorization"] = auth
    sa = request.headers.get("x-satker-aktif")
    if sa:
        headers["x-satker-aktif"] = sa
    task = asyncio.create_task(
        _jalankan_unduhan(unduhan_id, payload.path, headers))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return {"unduhan_id": unduhan_id}


@unduhan_router.get("/unduhan")
async def daftar_unduhan(user: dict = Depends(require_user)):
    """Log unduhan MILIK pengguna (Pusat Unduhan), terbaru dulu, maks 50."""
    username = str(user.get("username") or "")
    hasil = []
    async for d in _COL.find(
            {"dibuat_oleh": username}, {"_id": 0}).sort(
            "created_at", -1).limit(50):
        hasil.append(d)
    return {"items": hasil}


@unduhan_router.get("/unduhan/{unduhan_id}/file")
async def unduh_file(unduhan_id: str,
                     user: dict = Depends(require_user_or_query_token)):
    """Unduh hasil yang SUDAH jadi dari GridFS — tanpa generate ulang.
    Dual-auth (header ATAU ?token=) agar bisa lewat anchor native."""
    doc = await _COL.find_one({"unduhan_id": unduhan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Unduhan tidak ditemukan")
    if not _boleh_akses(doc, user):
        raise HTTPException(status_code=403, detail="Bukan unduhan Anda")
    if doc.get("status") != "done" or not doc.get("artifact_id"):
        raise HTTPException(status_code=404,
                            detail="Hasil belum siap atau sudah kedaluwarsa")
    # Alirkan langsung dari GridFS (chunk demi chunk) alih-alih memuat seluruh
    # file ke RAM — hasil 200 MB tak lagi menjadi lonjakan memori per unduhan.
    try:
        grid_out = await fs_bucket.open_download_stream(
            ObjectId(doc["artifact_id"]))
    except Exception:
        raise HTTPException(status_code=404, detail="Hasil sudah kedaluwarsa")

    async def _aliran():
        while True:
            potongan = await grid_out.readchunk()
            if not potongan:
                break
            yield potongan

    aman = nama_file_disposition(doc.get("nama_file") or "unduhan.bin")
    return StreamingResponse(
        _aliran(),
        media_type=doc.get("artifact_type") or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{aman}"'})


@unduhan_router.delete("/unduhan/{unduhan_id}")
async def hapus_unduhan(unduhan_id: str, user: dict = Depends(require_user)):
    """Hapus entri log + blob hasilnya (bila ada)."""
    doc = await _COL.find_one({"unduhan_id": unduhan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Unduhan tidak ditemukan")
    if not _boleh_akses(doc, user):
        raise HTTPException(status_code=403, detail="Bukan unduhan Anda")
    if doc.get("artifact_id"):
        try:
            from bson import ObjectId
            await fs_bucket.delete(ObjectId(doc["artifact_id"]))
        except Exception:
            pass                      # blob mungkin sudah tersapu — tak fatal
    await _COL.delete_one({"unduhan_id": unduhan_id})
    return {"success": True}


async def bersihkan_unduhan_kedaluwarsa(ambang_macet_menit: int = 90) -> int:
    """Sapuan berkala (menumpang loop pemeliharaan jobs.py):
    1. hapus blob GridFS ber-metadata.unduhan_id yang dokumennya sudah
       di-TTL Mongo (blob tidak ikut cascade) ATAU berumur > RETENSI_HARI;
    2. relabel job macet (tak ber-denyut > ambang) jadi error — dijalankan
       juga SEKALI saat startup (ambang pendek) supaya job yang mati saat
       server dimulai ulang tak menahan slot 'running' berlarut-larut.
    Idempoten & best-effort. Kembalikan jumlah blob terhapus."""
    n = 0
    batas_naive = datetime.utcnow() - timedelta(days=RETENSI_HARI)
    try:
        # Kumpulkan dulu semua kandidat, lalu SATU query keanggotaan (hindari
        # find_one per blob = N+1). Indeks metadata.unduhan_id (indexes.py)
        # membuat pemindaian ini terarah, bukan COLLSCAN koleksi foto.
        kandidat = []
        uids = set()
        async for f in db["fs.files"].find(
                {"metadata.unduhan_id": {"$exists": True}},
                {"_id": 1, "metadata.unduhan_id": 1, "uploadDate": 1}):
            uid = (f.get("metadata") or {}).get("unduhan_id")
            tua = (_naive_utc(f.get("uploadDate")) or batas_naive) < batas_naive
            kandidat.append((f["_id"], uid, tua))
            if uid:
                uids.add(uid)
        hidup = set()
        if uids:
            async for d in _COL.find({"unduhan_id": {"$in": list(uids)}},
                                     {"_id": 0, "unduhan_id": 1}):
                hidup.add(d.get("unduhan_id"))
        for fid, uid, tua in kandidat:
            if tua or uid not in hidup:
                try:
                    await fs_bucket.delete(fid)
                    n += 1
                except Exception:
                    pass
        await _COL.update_many(
            {"status": {"$in": ["queued", "running"]},
             "updated_at": {"$lt": _now() - timedelta(
                 minutes=max(1, ambang_macet_menit))}},
            {"$set": {"status": "error", "message": "Gagal",
                      "error_message": "Terputus (server dimulai ulang) — "
                                       "silakan mulai ulang unduhan",
                      "updated_at": _now()}})
    except Exception as e:
        logger.warning("bersihkan_unduhan_kedaluwarsa gagal: %s", e)
    return n
