"""INGEST POSISI IoT (Fase 11) — registry perangkat + penerimaan batch.

Rantai wajib tiap observasi, tanpa jalan pintas:

    token perangkat → normalisasi (iot_utils) → SARING PRIVASI (privasi_utils)
    → simpan (idempoten via obs_id)

`saring_observasi` dari Fase 10 berada DI TENGAH jalur, bukan sebagai lapisan
tampilan: observasi perangkat personal di luar jam kerja tak pernah menyentuh
disk, dan koordinatnya dibuang sebelum penulisan. Menyaring saat MEMBACA akan
menyisakan data mentah yang bisa bocor lewat backup, ekspor, atau permintaan
hukum — persis yang dihindari kebijakan.

KEPUTUSAN PENTING — posisi IoT TIDAK menimpa `koordinat_latitude/longitude`
aset. Field itu ikut terkirim ke Peta Kolaborasi PUBLIK (lihat
routes/peta_kolaborasi.py `_titik_aset`); membiarkan posisi perangkat personal
mengalir ke sana akan membocorkan keberadaan pemegangnya ke siapa pun yang
memegang link. Posisi IoT hidup di koleksi `iot_observasi` yang tak pernah
dibaca jalur publik.

AUTENTIKASI PERANGKAT memakai token acak per perangkat yang disimpan sebagai
HASH (pola password): kebocoran basis data tak memberi penyerang token yang
bisa dipakai mengirim posisi palsu.
"""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from auth_utils import require_admin, require_user
from db import db
from shared_utils import (kode_satker_user, limiter, log_audit,
                          pastikan_akses_dok_satker, scope_query_field_satker)
import geofence_utils as gf
import iot_utils as iu
import privasi_utils as pu
import spasial_utils as su

logger = logging.getLogger(__name__)
iot_router = APIRouter()

_PROJ = {"_id": 0}
_MAKS_PERANGKAT = 2000
_MAKS_RIWAYAT = 500
# Berhenti di GEDUNG: lantai tak dapat disimpulkan dari koordinat 2D (pola sama
# dengan /spasial/lokasi-di-titik).
_ORDINAL_GEDUNG = 80
_PROJ_NODE = {"_id": 0, "id": 1, "tipe": 1, "nama": 1, "ancestors_nama": 1}
# Plafon kueri geo BERBEDA per batch: satu batch 500 titik yang semuanya
# berlainan akan memicu 500 kueri. Titik dibulatkan ~11 m sebelum di-memo,
# sehingga perangkat DIAM (kasus lazim) hanya menimbulkan satu kueri.
_MAKS_RESOLUSI_NODE = 150
_PEMBULATAN_MEMO = 4


def _hash_token(token: str) -> str:
    """SHA-256 token perangkat. Token ini berentropi tinggi (32 byte acak),
    jadi hash cepat sudah memadai — berbeda dari password manusia yang
    berentropi rendah dan menuntut bcrypt/argon2 yang sengaja lambat."""
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


class PerangkatIn(BaseModel):
    nama: str
    asset_id: Optional[str] = ""
    profil_privasi: Optional[str] = "personal"   # gagal-tertutup (Fase 10)
    keterangan: Optional[str] = ""


@iot_router.post("/iot/perangkat")
async def daftar_perangkat(payload: PerangkatIn,
                           _user: dict = Depends(require_admin)):
    """Daftarkan perangkat pelacak. Token dikembalikan SEKALI — hanya hash-nya
    tersimpan, jadi token hilang berarti harus dirotasi, bukan dilihat ulang."""
    nama = str(payload.nama or "").strip()
    if not nama:
        raise HTTPException(status_code=400, detail="Nama perangkat wajib diisi")
    profil = str(payload.profil_privasi or "").strip().lower()
    if profil not in pu.PROFIL_PRIVASI:
        # Menolak (bukan diam-diam menjatuhkan ke bawaan) supaya salah ketik
        # profil ketahuan saat pendaftaran, bukan berbulan kemudian saat
        # seseorang menyadari datanya terlalu detail / terlalu sedikit.
        raise HTTPException(
            status_code=400,
            detail=(f"Profil privasi '{payload.profil_privasi}' tak dikenal — "
                    f"pilih: {', '.join(sorted(pu.PROFIL_PRIVASI))}"))

    aset = None
    aid = str(payload.asset_id or "").strip()
    if aid:
        from shared_utils import pastikan_akses_aset
        aset = await db.assets.find_one(
            {"id": aid}, {"_id": 0, "id": 1, "activity_id": 1,
                          "asset_name": 1, "asset_code": 1})
        if not aset:
            raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
        await pastikan_akses_aset(_user, aset)

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": "dev_" + uuid.uuid4().hex[:16],
        "kode_satker": kode_satker_user(_user),
        "nama": nama[:120],
        "asset_id": (aset or {}).get("id") or "",
        "asset_name": (aset or {}).get("asset_name") or "",
        "profil_privasi": profil,
        "keterangan": str(payload.keterangan or "").strip()[:300],
        "token_hash": _hash_token(token),
        "aktif": True,
        "created_at": now, "updated_at": now,
        "created_by": _user.get("username", ""),
    }
    await db.iot_perangkat.insert_one(dict(doc))
    await log_audit("iot_perangkat_daftar", "", doc["id"],
                    username=_user.get("username", "system"),
                    kode_satker=doc["kode_satker"],
                    detail=f"{nama} (profil {profil})")
    doc.pop("token_hash", None)
    return {**doc, "token": token,
            "catatan": ("Simpan token ini sekarang — token tidak dapat "
                        "dilihat lagi; kehilangan berarti rotasi.")}


@iot_router.get("/iot/perangkat")
async def list_perangkat(_user: dict = Depends(require_user)):
    """Daftar perangkat satker + ringkasan kesehatan dari observasi terakhir."""
    items = await (db.iot_perangkat.find(
        scope_query_field_satker(_user), {**_PROJ, "token_hash": 0})
        .sort("created_at", -1).to_list(_MAKS_PERANGKAT))
    sekarang = datetime.now(timezone.utc)
    # Observasi TERAKHIR seluruh perangkat dalam SATU kueri. Versi per-perangkat
    # (find_one di dalam loop) berarti satu bolak-balik jaringan per baris —
    # daftar 200 perangkat = 200 round-trip untuk halaman yang sama. `$sort`
    # mengikuti indeks (device_id, ts_server) sehingga `$first` mengambil yang
    # terbaru tanpa memindai riwayat penuh.
    terakhir = {}
    if items:
        async for r in db.iot_observasi.aggregate([
            {"$match": {"device_id": {"$in": [d["id"] for d in items]}}},
            {"$sort": {"device_id": 1, "ts_server": -1}},
            {"$group": {"_id": "$device_id", "doc": {"$first": "$$ROOT"}}},
        ]):
            terakhir[r["_id"]] = r.get("doc") or {}
    for d in items:
        d["kesehatan"] = iu.ringkas_kesehatan(terakhir.get(d["id"]), sekarang)
        d["kebijakan"] = pu.profil_privasi(d.get("profil_privasi"))["label"]
    return {"items": items, "jumlah": len(items),
            "profil_tersedia": pu.ringkas_kebijakan()}


@iot_router.post("/iot/perangkat/{device_id}/rotasi-token")
async def rotasi_token(device_id: str, _user: dict = Depends(require_admin)):
    """Terbitkan token baru (yang lama langsung tak berlaku)."""
    dev = await db.iot_perangkat.find_one({"id": device_id}, _PROJ)
    if not dev:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    await pastikan_akses_dok_satker(_user, dev)
    token = secrets.token_urlsafe(32)
    await db.iot_perangkat.update_one(
        {"id": device_id},
        {"$set": {"token_hash": _hash_token(token),
                  "updated_at": datetime.now(timezone.utc).isoformat()}})
    await log_audit("iot_token_rotasi", "", device_id,
                    username=_user.get("username", "system"),
                    kode_satker=kode_satker_user(_user),
                    detail=str(dev.get("nama") or device_id))
    return {"ok": True, "token": token}


async def _perangkat_dari_token(token: str) -> dict:
    """Perangkat pemilik token, atau 401. Pencarian lewat HASH — token mentah
    tak pernah dibandingkan dengan isi database."""
    if not token:
        raise HTTPException(status_code=401, detail="Token perangkat wajib")
    dev = await db.iot_perangkat.find_one({"token_hash": _hash_token(token)},
                                          _PROJ)
    if not dev or not dev.get("aktif", True):
        # Pesan SAMA untuk token salah & perangkat nonaktif — membedakannya
        # memberi tahu penyerang bahwa tokennya benar tetapi sedang dimatikan.
        raise HTTPException(status_code=401, detail="Token perangkat tidak sah")
    return dev


async def _node_di_titik(lon: float, lat: float, kode_satker: str, memo: dict):
    """Node denah TERDALAM yang memuat titik, atau None.

    Resolusi ini WAJIB, bukan hiasan: profil `personal` membuang koordinat, jadi
    tanpa node yang teresolusi lebih dulu observasinya tersimpan TANPA lokasi
    apa pun — kebijakan "simpan level gedung saja" berubah jadi "tak simpan
    apa-apa yang berguna". Karena itu resolusi dijalankan SEBELUM penyaringan.
    """
    if not kode_satker:
        # Perangkat tanpa satker tak punya cakupan denah yang sah untuk dicari;
        # mencari lintas-satker akan menautkan aset ke gedung milik satker lain.
        return None
    kunci = (round(lon, _PEMBULATAN_MEMO), round(lat, _PEMBULATAN_MEMO))
    if kunci in memo:
        return memo[kunci]
    if len(memo) >= _MAKS_RESOLUSI_NODE:
        return None
    node = await db.spasial_node.find_one(
        {"kode_satker": kode_satker, "status": "aktif",
         "ordinal_level": {"$lte": _ORDINAL_GEDUNG},
         "geometry": {"$geoIntersects": {
             "$geometry": {"type": "Point", "coordinates": [lon, lat]}}}},
        _PROJ_NODE, sort=[("ordinal_level", -1)])
    memo[kunci] = node
    return node


class BatchIn(BaseModel):
    observasi: list


@iot_router.post("/iot/observasi")
@limiter.limit("60/minute")
async def terima_observasi(request: Request, payload: BatchIn,
                           x_device_token: str = Header(default="")):
    """Terima batch posisi dari perangkat.

    IDEMPOTEN: `obs_id` dihitung dari isi observasi dan dilindungi indeks unik,
    sehingga pengiriman ulang (normal pada at-least-once) tak menggandakan
    data. Duplikat DIHITUNG dan dilaporkan, bukan disembunyikan — lonjakan
    duplikat adalah sinyal perangkat/jaringan bermasalah.
    """
    from pymongo.errors import BulkWriteError

    dev = await _perangkat_dari_token(x_device_token)
    sekarang = datetime.now(timezone.utc)
    siap = iu.siapkan_batch(payload.observasi, dev["id"], sekarang)

    profil_nama = dev.get("profil_privasi")
    profil = pu.profil_privasi(profil_nama)
    satker = dev.get("kode_satker") or ""
    # Umur simpan diambil dari SUMBER YANG SAMA dengan penyapu & dokumen
    # kebijakan (Fase 10); TTL index memakai field turunannya, jadi retensi tak
    # bisa menyimpang diam-diam antara indeks dan kebijakan tertulis.
    umur = sekarang - pu.batas_retensi(profil_nama, sekarang)

    disimpan, ditolak_privasi, duplikat, tanpa_kawasan = 0, 0, 0, 0
    memo_node, dok = {}, []
    for obs in siap["terima"]:
        lon, lat = obs["geo"]["coordinates"]
        node = await _node_di_titik(lon, lat, satker, memo_node)
        obs["lokasi_spasial"] = su.snapshot_lokasi_temuan(node, lon, lat)

        hasil = pu.saring_observasi(obs, profil_nama, sekarang=sekarang)
        if not hasil["simpan"]:
            ditolak_privasi += 1
            continue
        d = hasil["observasi"]
        if profil.get("presisi") == "wilayah" and not node:
            # Koordinat sudah dibuang penyaring dan tak ada node yang tersisa —
            # dokumen ini tak memuat lokasi apa pun, jadi menyimpannya hanya
            # menambah baris kosong. Efek sampingnya justru diinginkan: laptop
            # dinas DI RUMAH pemegangnya berada di luar kawasan terpetakan,
            # sehingga sistem tak merekam apa-apa tentang tempat itu.
            tanpa_kawasan += 1
            continue
        d.update({"kode_satker": satker,
                  "asset_id": dev.get("asset_id") or "",
                  "kedaluwarsa_pada": sekarang + umur})
        dok.append(d)

    # OUTLIER ditandai SEBELUM disimpan — geofence menolak observasi bertanda
    # ini, dan satu koordinat kacau yang melompat 40 km lalu kembali akan
    # melahirkan sepasang peringatan keluar-masuk yang sepenuhnya palsu.
    if dok:
        dok.sort(key=lambda d: str(d.get("ts_device") or ""))
        acuan = await db.iot_observasi.find_one(
            {"device_id": dev["id"]}, {"_id": 0, "geo": 1, "ts_device": 1},
            sort=[("ts_device", -1)])
        for d in dok:
            if acuan and gf.lompatan_mustahil(acuan, d):
                d["outlier"] = True
            else:
                acuan = d          # hanya titik waras yang jadi acuan berikutnya

    gagal_idx = set()
    if dok:
        try:
            r = await db.iot_observasi.insert_many(dok, ordered=False)
            disimpan = len(r.inserted_ids)
        except BulkWriteError as e:
            rincian = e.details or {}
            disimpan = int(rincian.get("nInserted", 0))
            # Galat 11000 = kembar obs_id → memang idempotensi bekerja, bukan
            # kegagalan. Galat lain tetap dihitung agar tak lolos senyap.
            duplikat = sum(1 for w in rincian.get("writeErrors", [])
                           if w.get("code") == 11000)
            lain = len(rincian.get("writeErrors", [])) - duplikat
            # Indeks dokumen yang DITOLAK — dipakai menjaga idempotensi geofence
            # di bawah. `index` menunjuk ke posisi dalam `dok` (sudah terurut).
            gagal_idx = {w.get("index") for w in rincian.get("writeErrors", [])}
            if lain:
                raise HTTPException(
                    status_code=500,
                    detail=f"{lain} observasi gagal disimpan")

    # GEOFENCE dievaluasi di jalur TULIS: status histeresis butuh melihat setiap
    # observasi berurutan, dan menghitungnya belakangan dari data yang sudah
    # dipadatkan mustahil. Kegagalannya SENGAJA tidak menggagalkan penerimaan —
    # posisi yang sudah tersimpan lebih berharga daripada peringatan yang gagal
    # dihitung, dan perangkat yang menerima 500 akan mengirim ulang batch yang
    # sebenarnya sudah aman (lalu ditolak indeks unik, lalu mencoba lagi).
    #
    # HANYA observasi yang BENAR-BENAR baru tersimpan yang diputar. Pengiriman
    # ulang adalah perilaku NORMAL at-least-once (seluruh Fase 11 dibangun di
    # sekitar kenyataan itu), dan memutar ulang observasi yang sudah pernah
    # dievaluasi berarti mesin histeresis menghitung sampel & dwell dua kali —
    # penyimpanannya idempoten, peringatannya tidak.
    peringatan = 0
    segar = [d for i, d in enumerate(dok) if i not in gagal_idx]
    if segar:
        try:
            from routes.geofence import evaluasi_perangkat
            peringatan = (await evaluasi_perangkat(dev, segar, sekarang))["event"]
        except Exception as e:            # noqa: BLE001 — sengaja menelan
            logger.warning("Evaluasi geofence gagal untuk %s: %s", dev["id"], e)

    return {"diterima": len(siap["terima"]), "disimpan": disimpan,
            "duplikat": duplikat, "ditolak_privasi": ditolak_privasi,
            "di_luar_kawasan": tanpa_kawasan, "peringatan_geofence": peringatan,
            "ditolak_validasi": siap["tolak"][:20],
            "melebihi_plafon": siap["plafon"],
            "profil": profil_nama}


@iot_router.get("/iot/perangkat/{device_id}/posisi")
async def posisi_perangkat(device_id: str, batas: int = Query(50),
                           _user: dict = Depends(require_user)):
    """Riwayat posisi perangkat (terbaru dulu), ter-scope satker.

    Data yang keluar SUDAH tersaring saat masuk — endpoint ini tak perlu (dan
    tak boleh) menyaring ulang, karena menyaring saat baca berarti data mentah
    tetap ada di disk.
    """
    dev = await db.iot_perangkat.find_one({"id": device_id},
                                          {**_PROJ, "token_hash": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    await pastikan_akses_dok_satker(_user, dev)
    n = max(1, min(int(batas or 50), _MAKS_RIWAYAT))
    items = await (db.iot_observasi.find(
        {"device_id": device_id},
        {"_id": 0, "obs_id": 0, "kedaluwarsa_pada": 0})
        .sort("ts_server", -1).to_list(n))
    return {"perangkat": {"id": dev["id"], "nama": dev.get("nama"),
                          "profil_privasi": dev.get("profil_privasi"),
                          "kebijakan": pu.profil_privasi(
                              dev.get("profil_privasi"))["label"]},
            "items": items, "jumlah": len(items)}


@iot_router.get("/iot/kebijakan-privasi")
async def kebijakan_privasi(_user: dict = Depends(require_user)):
    """Kebijakan privasi yang BERLAKU, dibaca dari kode penegaknya.

    Ditampilkan ke pengguna karena kebijakan yang tak terlihat tak bisa
    diperiksa siapa pun — dan karena angka di sini dijamin sama dengan yang
    dijalankan mesin, bukan salinan dokumen yang bisa basi.
    """
    return {"profil": pu.ringkas_kebijakan(),
            "maks_jam_izin_darurat": pu.MAKS_JAM_DARURAT,
            "catatan": ("Sistem melacak BARANG NEGARA, bukan ORANG. Perangkat "
                        "pegangan perorangan hanya menyimpan level wilayah dan "
                        "hanya pada jam kerja.")}
