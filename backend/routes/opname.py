"""OPNAME LEWAT SCAN STIKER (Fase 11) — scan sebagai observasi lokasi.

Stiker QR sudah tercetak dan tertempel (routes/stiker.py). Fase ini menjadikan
pemindaiannya SUMBER LOKASI: biaya nol, tanpa isu privasi (yang direkam barang,
bukan orang), akurasi ruangan sempurna — pelengkap yang tepat untuk GPS yang
justru mati di dalam gedung.

MENGAPA SCAN PUNYA KOLEKSI SENDIRI, BUKAN MENUMPANG `iot_observasi`
====================================================================
Rancangan Fase 10 menetapkan satu pipeline observasi untuk semua sumber, dan
BENTUK dokumennya memang dipertahankan sama di sini (`sumber`, `akurasi_m`,
`kepercayaan`, `lokasi_spasial`) supaya suatu saat bisa disatukan pembacaannya.
Yang TIDAK boleh diwarisi adalah RETENSINYA: `iot_observasi` memakai TTL yang
diturunkan dari profil privasi perangkat — 30/90 hari — karena isinya jejak
keberadaan ORANG yang wajib kedaluwarsa. Hasil opname sebaliknya adalah BUKTI
penatausahaan BMN yang harus bertahan; menumpangkannya pada TTL privasi berarti
catatan opname terhapus diam-diam beberapa bulan setelah dibuat, tepat saat
diperiksa. Karena itu `opname_scan` berdiri sendiri, tanpa TTL.

MENGAPA SCAN TIDAK LANGSUNG MEMINDAHKAN CATATAN LOKASI
======================================================
Lihat opname_utils (keputusan 2): opname adalah PEMERIKSAAN. Menulis ulang buku
di setiap pindaian menghapus selisih yang justru dicari, dan salah pindai
(stiker tetangga, barang yang sedang dijinjing) akan mengubah custody tanpa
seorang pun sempat berkeberatan. Scan mencatat + mengklasifikasi; pemindahan
adalah tindakan terpisah lewat `/opname/terapkan` yang tercatat di audit dan
memakai jalur riwayat yang sama dengan Fase 9.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from auth_utils import require_user, require_writer, require_writer_satker
from db import db
from shared_utils import (kode_satker_user, limiter, log_audit,
                          pastikan_akses_aset, scope_query_aset,
                          scope_query_field_satker)
import opname_utils as ou
import spasial_utils as su

logger = logging.getLogger(__name__)
opname_router = APIRouter()

_PROJ = {"_id": 0}
_MAKS_NODE = 20000
_MAKS_ISI = 1000
_MAKS_SCAN = 2000
_MAKS_KANDIDAT = 20
_MAKS_TERAPKAN = 200
# Kepercayaan scan stiker. Angka ini SENGAJA di satu tempat: bila suatu hari
# sumber lain (BLE, RFID) ikut menulis lokasi, perbandingannya harus memakai
# skala yang sama, bukan tebakan per pemanggil.
KEPERCAYAAN_SCAN = 0.99

_PROJ_ASET = {"_id": 0, "id": 1, "activity_id": 1, "asset_code": 1, "NUP": 1,
              "asset_name": 1, "category": 1, "condition": 1, "status": 1,
              "user": 1, "kode_register": 1, "lokasi_spasial": 1,
              # `location` (teks bebas) ikut dibaca karena /opname/terapkan
              # memindahkannya juga — dan nilai LAMANYA harus tersimpan ke
              # riwayat sebelum ditimpa.
              "location": 1}
_PROJ_NODE = {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "ancestors": 1,
              "ancestors_nama": 1, "status": 1}


def _sekarang() -> datetime:
    return datetime.now(timezone.utc)


def _waktu_scan(ts_klien, sekarang: datetime) -> str:
    """Waktu kejadian scan — jam klien DIPAKAI tetapi tak pernah dipercaya bulat.

    Scan luring yang tertahan berjam-jam di ransel memang harus tercatat pada
    waktu KEJADIANNYA, bukan waktu tiba; itulah gunanya menerima `ts_scan`.
    Tetapi jam HP bisa maju/mundur, jadi nilai di luar rentang wajar dijatuhkan
    ke waktu server ketimbang menyusup ke urutan opname sebagai kejadian palsu.

    SELALU dinormalkan ke UTC sebelum di-isoformat. `pada` disimpan sebagai
    STRING dan dibandingkan sebagai string (filter periode `$gte`, pemilihan
    scan terbaru per aset). HP Indonesia mengirim `+07:00`, sehingga tanpa
    normalisasi "2026-07-27T08:00:00+07:00" akan tampak LEBIH BESAR daripada
    "2026-07-27T09:00:00+00:00" yang sebenarnya terjadi dua jam kemudian —
    urutan opname jadi kacau tanpa satu pun galat.
    """
    if not ts_klien:
        return sekarang.isoformat()
    try:
        t = datetime.fromisoformat(str(ts_klien).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return sekarang.isoformat()
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    if t > sekarang + timedelta(hours=1):
        return sekarang.isoformat()
    if t < sekarang - timedelta(days=ou.MAKS_UMUR_SCAN_HARI):
        return sekarang.isoformat()
    return t.astimezone(timezone.utc).isoformat()


async def _node_terjamin(node_id: str, _user: dict) -> dict:
    """Node denah ter-scope satker, atau 404. Menempatkan/mengukuhkan aset pada
    ruangan milik satker lain harus mustahil — sama seperti Fase 9."""
    node = await db.spasial_node.find_one(
        scope_query_field_satker(_user, {"id": str(node_id or "").strip()}),
        _PROJ_NODE)
    if not node or node.get("status") == "dihapus":
        raise HTTPException(status_code=404, detail="Node denah tidak ditemukan")
    return node


async def _lingkup_node(node: dict, _user: dict, dalam: bool) -> List[str]:
    """Id node + (opsional) SELURUH keturunannya — satu kueri lewat `ancestors`."""
    ids = [node["id"]]
    if dalam:
        anak = await db.spasial_node.find(
            scope_query_field_satker(_user, {"ancestors": node["id"],
                                             "status": {"$ne": "dihapus"}}),
            {"_id": 0, "id": 1}).to_list(_MAKS_NODE)
        ids.extend(d["id"] for d in anak)
    return ids


def _ringkas_aset(a: dict) -> dict:
    return {k: a.get(k) for k in ("id", "asset_code", "NUP", "asset_name",
                                  "category", "condition", "status", "user",
                                  "kode_register", "lokasi_spasial")}


class ScanIn(BaseModel):
    kode: str
    node_id: str = ""
    lat: object = None
    lon: object = None
    akurasi_m: object = None
    ts_scan: Optional[str] = ""
    scan_id: Optional[str] = ""
    activity_id: Optional[str] = ""
    asset_id: Optional[str] = ""       # dipilih petugas saat kode ambigu
    catatan: Optional[str] = ""


@opname_router.post("/opname/scan")
@limiter.limit("120/minute")
async def catat_scan(request: Request, payload: ScanIn,
                     _user: dict = Depends(require_writer_satker)):
    """Catat satu pemindaian stiker sebagai observasi lokasi.

    IDEMPOTEN lewat `scan_id` yang dibuat KLIEN sekali per tindakan pindai.
    Antrean luring mengirim ulang isi yang sama saat sinyal pulih — itu perilaku
    normal, bukan anomali — dan pengiriman ulang harus menghasilkan SATU catatan.
    Sebaliknya, memindai ulang barang yang sama secara sengaja adalah tindakan
    BARU dengan `scan_id` baru, dan memang layak tercatat lagi.

    KODE AMBIGU TIDAK PERNAH DITEBAK. Kode register hanya unik di dalam satu
    kegiatan, sehingga satu isi QR bisa menunjuk lebih dari satu aset. Jawabannya
    409 berisi daftar kandidat agar petugas memilih — menebak salah satunya
    persis cara sebuah pengamatan tercatat pada gerbong yang salah.
    """
    sekarang = _sekarang()
    kode = ou.normalisasi_kode(payload.kode)
    if not kode:
        raise HTTPException(status_code=400,
                            detail="Isi QR/barcode tidak berisi kode yang dikenali")

    scan_id = str(payload.scan_id or "").strip()[:64] or ("scan_" + uuid.uuid4().hex)
    lama = await db.opname_scan.find_one({"scan_id": scan_id}, _PROJ)
    if lama:
        # Replay antrean luring: kembalikan catatan yang SUDAH ada apa adanya.
        return {"ok": True, "duplikat": True, "scan": lama}

    kriteria = ou.kandidat_kriteria(kode)
    q = await scope_query_aset(_user, {"$or": kriteria})
    if str(payload.activity_id or "").strip():
        q["activity_id"] = str(payload.activity_id).strip()
    kandidat = await db.assets.find(q, _PROJ_ASET).to_list(_MAKS_KANDIDAT + 1)
    # Guard baku modul aset (lewat kegiatan induk) — `scope_query_aset` menyaring
    # kasar, guard ini yang menutup aset yatim & kegiatan lintas-satker.
    tersaring = []
    for a in kandidat:
        try:
            await pastikan_akses_aset(_user, a)
        except HTTPException:
            continue
        tersaring.append(a)

    if not tersaring:
        raise HTTPException(
            status_code=404,
            detail=(f"Kode '{kode}' tidak cocok dengan aset mana pun yang dapat "
                    "Anda akses. Periksa stiker atau pilih kegiatan yang benar."))

    pilihan_id = str(payload.asset_id or "").strip()
    if pilihan_id:
        # Pilihan petugas WAJIB berasal dari kandidat hasil kode yang dipindai —
        # tanpa ini, `asset_id` menjadi jalan memalsukan scan untuk aset apa pun.
        aset = next((a for a in tersaring if a.get("id") == pilihan_id), None)
        if not aset:
            raise HTTPException(
                status_code=400,
                detail="Aset yang dipilih bukan hasil dari kode yang dipindai")
    elif len(tersaring) > 1:
        raise HTTPException(status_code=409, detail={
            "pesan": (f"Kode '{kode}' cocok dengan {len(tersaring)} aset — "
                      "pilih yang benar."),
            "kode": kode,
            "kandidat": [_ringkas_aset(a) for a in tersaring[:_MAKS_KANDIDAT]],
        })
    else:
        aset = tersaring[0]

    # ── Lokasi scan: node eksplisit, atau deteksi dari titik ────────────────
    lat = su.parse_lintang(payload.lat)
    lon = su.parse_bujur(payload.lon)
    node = None
    if str(payload.node_id or "").strip():
        node = await _node_terjamin(payload.node_id, _user)
    elif lat is not None and lon is not None:
        node = await db.spasial_node.find_one(
            scope_query_field_satker(_user, {
                "status": "aktif",
                "geometry": {"$geoIntersects": {"$geometry": {
                    "type": "Point", "coordinates": [lon, lat]}}}}),
            _PROJ_NODE, sort=[("ordinal_level", -1)])

    lokasi = su.snapshot_lokasi_temuan(node, lon if lon is not None else 0.0,
                                       lat if lat is not None else 0.0)
    if lat is None or lon is None:
        # Tanpa koordinat, `titik` [0,0] adalah Null Island — penanda parsing
        # gagal, bukan posisi. Dikosongkan supaya tak pernah dipetakan.
        lokasi["titik"] = None

    # ── Klasifikasi terhadap catatan yang berlaku ──────────────────────────
    lokasi_lama = aset.get("lokasi_spasial") or {}
    node_lama_id = str(lokasi_lama.get("node_id") or "")
    anc_lama = []
    if node_lama_id and node and node_lama_id != node["id"]:
        n_lama = await db.spasial_node.find_one({"id": node_lama_id},
                                                {"_id": 0, "ancestors": 1})
        anc_lama = (n_lama or {}).get("ancestors") or []
    status = ou.klasifikasi_scan(node_lama_id, (node or {}).get("id"), anc_lama)

    akurasi = su.parse_koordinat(payload.akurasi_m, 100000.0)
    dok = {
        "id": "opn_" + uuid.uuid4().hex[:16],
        "scan_id": scan_id,
        "kode_satker": kode_satker_user(_user),
        "asset_id": aset["id"],
        "activity_id": aset.get("activity_id") or "",
        "asset_code": aset.get("asset_code") or "",
        "NUP": aset.get("NUP") or "",
        "asset_name": aset.get("asset_name") or "",
        "kode_dipindai": kode,
        "sumber": "scan_qr",
        "kepercayaan": KEPERCAYAAN_SCAN,
        "node_id": (node or {}).get("id") or "",
        "lokasi_spasial": lokasi,
        "lokasi_sebelum": {"node_id": node_lama_id,
                           "nama": str(lokasi_lama.get("node_nama") or ""),
                           "jalur": str(lokasi_lama.get("jalur_nama") or "")},
        "status_rekonsiliasi": status,
        "diterapkan": False,
        "catatan": str(payload.catatan or "").strip()[:300],
        "oleh": _user.get("username", ""),
        "pada": _waktu_scan(payload.ts_scan, sekarang),
        "diterima_pada": sekarang.isoformat(),
    }
    if akurasi is not None and akurasi >= 0:
        dok["akurasi_m"] = round(akurasi, 1)

    try:
        await db.opname_scan.insert_one(dict(dok))
    except DuplicateKeyError:
        # Lomba antar dua pengiriman `scan_id` yang sama (antrean luring
        # mengirim ganda saat sinyal berkedip). Indeks unik yang memutuskan;
        # yang kalah membaca catatan pemenang, bukan melempar galat ke petugas.
        ada = await db.opname_scan.find_one({"scan_id": scan_id}, _PROJ)
        if ada:
            return {"ok": True, "duplikat": True, "scan": ada}
        raise

    await log_audit("opname_scan", dok["activity_id"], aset["id"],
                    asset_code=dok["asset_code"], asset_name=dok["asset_name"],
                    username=_user.get("username", "system"),
                    kode_satker=dok["kode_satker"],
                    detail=f"{status} — {lokasi.get('jalur_nama') or 'tanpa node'}"[:120])

    dok.pop("_id", None)
    return {"ok": True, "duplikat": False, "scan": dok,
            "aset": _ringkas_aset(aset),
            "perlu_dipindahkan": status == "pindah"}


@opname_router.get("/opname/rekonsiliasi")
async def rekonsiliasi(node_id: str = Query(...), dalam: bool = Query(True),
                       sejak: str = Query("", description="ISO-8601; kosong = 30 hari terakhir"),
                       _user: dict = Depends(require_user)):
    """Sanding BUKU vs LAPANGAN untuk satu lingkup lokasi.

    Keluarannya tiga keranjang (lihat `opname_utils.rekap_rekonsiliasi`), dan
    yang paling berguna di lapangan justru `belum_terpindai`: daftar kerja yang
    tersisa. Tanpa memisahkannya, opname berakhir dengan pertanyaan "sudah
    semua?" yang tak pernah terjawab.
    """
    node = await _node_terjamin(node_id, _user)
    ids = await _lingkup_node(node, _user, bool(dalam))

    batas = str(sejak or "").strip()
    if not batas:
        batas = (_sekarang() - timedelta(days=ou.MAKS_UMUR_SCAN_HARI)).isoformat()

    # SATU kueri kegiatan-satker untuk KEDUA daftar, bukan satu guard per baris.
    # Versi lama memanggil `pastikan_akses_aset` di dalam loop: ruangan berisi
    # 1.000 aset berarti 1.000 find_one BERURUTAN untuk satu halaman.
    #
    # Filter yang sama dipakai untuk SCAN — dan itu sekaligus menutup kebocoran
    # yang ditemukan audit: dokumen scan distempel satker PEMINDAI, bukan satker
    # aset, sehingga scan yang dibuat super-admin atas aset satker lain (di node
    # era-lama tanpa kode_satker) muncul di keranjang "Ditemukan di sini" milik
    # satker mana pun — lengkap dengan kode & nama barangnya.
    q_aset = {"lokasi_spasial.node_id": {"$in": ids}}
    q_scan = scope_query_field_satker(
        _user, {"node_id": {"$in": ids}, "pada": {"$gte": batas}})
    kode_satker = kode_satker_user(_user)
    if kode_satker:
        from shared_utils import id_kegiatan_satker
        keg_boleh = await id_kegiatan_satker(kode_satker)
        q_aset["activity_id"] = {"$in": keg_boleh}
        # Scan YATIM (kegiatan induknya sudah dihapus) sengaja TIDAK ikut:
        # kepemilikan satkernya tak dapat dipastikan, dan menampilkannya berarti
        # menebak — pola fail-closed yang sama dengan pastikan_akses_kegiatan_id.
        q_scan["activity_id"] = {"$in": keg_boleh}

    rows = await (db.assets.find(q_aset, _PROJ_ASET)
                  .sort("asset_name", 1).to_list(_MAKS_ISI))
    harapan = [_ringkas_aset(r) for r in rows]

    scans = await (db.opname_scan.find(q_scan, _PROJ)
                   .sort("pada", -1).to_list(_MAKS_SCAN))

    hasil = ou.rekap_rekonsiliasi(harapan, scans)
    hasil["ringkas"]["persen_terkonfirmasi"] = ou.persen_terkonfirmasi(
        hasil["ringkas"])
    return {
        "node": {"id": node["id"], "nama": node.get("nama"),
                 "tipe": node.get("tipe")},
        "termasuk_keturunan": bool(dalam),
        "sejak": batas,
        **hasil,
        "terpotong": len(rows) >= _MAKS_ISI or len(scans) >= _MAKS_SCAN,
    }


class TerapkanIn(BaseModel):
    scan_ids: List[str]


@opname_router.post("/opname/terapkan")
@limiter.limit("30/minute")
async def terapkan_perpindahan(request: Request, payload: TerapkanIn,
                               _user: dict = Depends(require_writer)):
    """Terapkan hasil scan sebagai perpindahan lokasi yang sah.

    Hanya scan berstatus `pindah`/`baru` yang punya makna di sini; `sesuai` tak
    mengubah apa pun dan `tanpa_lokasi` tak punya tujuan. Penulisannya memakai
    jalur yang SAMA persis dengan Fase 9 (snapshot `lokasi_spasial` di dokumen
    aset + baris `riwayat_lokasi_aset`), bukan jalur pintas — supaya riwayat
    custody tetap satu untai, dari mana pun perpindahan berasal.

    Scan yang SUDAH diterapkan dilewati, bukan diterapkan ulang: menekan tombol
    dua kali tak boleh melahirkan dua baris riwayat untuk satu kejadian.
    """
    ids = [str(x).strip() for x in (payload.scan_ids or []) if str(x).strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="Tidak ada scan yang dipilih")
    if len(ids) > _MAKS_TERAPKAN:
        raise HTTPException(
            status_code=400,
            detail=f"Maksimal {_MAKS_TERAPKAN} scan sekali terap")

    scans = await db.opname_scan.find(
        scope_query_field_satker(_user, {"id": {"$in": ids}}), _PROJ).to_list(
            _MAKS_TERAPKAN)
    now = _sekarang().isoformat()
    username = _user.get("username", "")
    diterapkan, dilewati = [], []

    # Aset dibaca SEKALI untuk semua scan (satu `$in`), bukan `find_one`
    # per-scan. Hanya PEMBACAAN yang dibatch: klaim `diterapkan` dan tulisannya
    # SENGAJA tetap satu per satu, karena klaim bersyarat itulah penjaga lomba
    # yang dijelaskan panjang lebar di bawah — menundanya ke `bulk_write` di
    # akhir akan melebarkan jendela "sudah diklaim tetapi belum tertulis".
    id_aset = [s.get("asset_id") for s in scans if s.get("asset_id")]
    aset_by_id = {}
    if id_aset:
        async for a in db.assets.find({"id": {"$in": id_aset}}, _PROJ_ASET):
            aset_by_id[a.get("id")] = a

    for s in scans:
        if s.get("status_rekonsiliasi") not in ("pindah", "baru"):
            dilewati.append({"id": s["id"],
                             "alasan": f"status {s.get('status_rekonsiliasi')}"})
            continue
        aset = aset_by_id.get(s.get("asset_id"))
        if not aset:
            dilewati.append({"id": s["id"], "alasan": "aset tidak ditemukan"})
            continue
        try:
            await pastikan_akses_aset(_user, aset)
        except HTTPException:
            dilewati.append({"id": s["id"], "alasan": "di luar akses satker"})
            continue

        # SATU penjaga saja, dan itu update BERSYARAT — bukan pembacaan.
        # Dulu ada cek `if s.get("diterapkan")` di atas yang selalu menghentikan
        # panggilan kedua lebih dulu, sehingga penjaga lomba di bawah TAK PERNAH
        # dievaluasi satu kali pun: audit membuktikannya dengan mengubahnya jadi
        # `if False:` tanpa satu uji pun gagal. Penjaga yang tak pernah berjalan
        # bukan penjaga. Cek pembacaannya dibuang; yang tersisa inilah yang
        # benar-benar memutuskan, dan kini ia yang diuji.
        #
        # KLAIM DULU, baru tulis. Penanda `diterapkan` diambil lewat update
        # bersyarat: yang menang menulis riwayat, yang kalah berhenti di sini.
        # Urutan sebaliknya (tulis dulu, tandai belakangan) menyisakan jendela
        # tempat dua permintaan serentak SAMA-SAMA sempat menulis riwayat,
        # sehingga satu kejadian fisik melahirkan dua baris jejak custody —
        # dan pemeriksa tak punya cara membedakannya dari dua perpindahan asli.
        klaim = await db.opname_scan.update_one(
            {"id": s["id"], "diterapkan": {"$ne": True}},
            {"$set": {"diterapkan": True, "diterapkan_oleh": username,
                      "diterapkan_pada": now}})
        if not klaim.modified_count:
            dilewati.append({"id": s["id"], "alasan": "sudah diterapkan"})
            continue

        lokasi_lama = aset.get("lokasi_spasial")
        lokasi_baru = dict(s.get("lokasi_spasial") or {})
        # Koordinat presisi TIDAK DITURUNKAN. Pemindaian dari aplikasi tak
        # membawa lat/lon (ruangan dipilih, bukan diukur), sehingga `titik`
        # bernilai None — dan menuliskannya apa adanya MENGHAPUS koordinat yang
        # dikumpulkan lewat jalur Fase 9, yang justru menolak koordinat kosong.
        if lokasi_baru.get("titik") is None and (lokasi_lama or {}).get("titik"):
            lokasi_baru["titik"] = lokasi_lama["titik"]
        lokasi_baru.update({"ditandai_oleh": username, "ditandai_pada": now,
                            "sumber": "scan_qr", "scan_id": s.get("scan_id")})
        nama_ruang = str(lokasi_baru.get("node_nama") or "").strip()
        lokasi_teks_lama = str(aset.get("location") or "")
        if su.pindah_lokasi_berarti(lokasi_lama, lokasi_baru):
            baris = su.entri_riwayat_lokasi(aset["id"], lokasi_lama, lokasi_baru,
                                            username, now)
            # Nilai `location` LAMA ikut disimpan: ia akan ditimpa di bawah, dan
            # riwayat custody adalah satu-satunya tempat ia masih bisa dibaca.
            baris["location_lama"] = lokasi_teks_lama
            await db.riwayat_lokasi_aset.insert_one(baris)
        set_aset = {"lokasi_spasial": lokasi_baru, "updated_at": now}
        # `location` (teks bebas) IKUT BERPINDAH — inilah yang dibaca KIR & DBR
        # (reports.py `cocok_ruangan_master` mencocokkan STRING, bukan node_id).
        # Tanpa ini, menerapkan hasil opname memperbarui denah tetapi membiarkan
        # DOKUMEN RESMI menyebut ruangan lama: peta dan kertas saling
        # bertentangan, dan yang dipegang pemeriksa justru kertasnya.
        if nama_ruang and nama_ruang != lokasi_teks_lama:
            set_aset["location"] = nama_ruang
        # $inc version: tanpa ini penjaga OCC/If-Match & cache media buta
        # terhadap perpindahan lokasi hasil opname (pola batch.py).
        await db.assets.update_one({"id": aset["id"]},
                                   {"$set": set_aset,
                                    "$inc": {"version": 1}})
        try:
            from meili_utils import jadwalkan_sync
            _doc = await db.assets.find_one({"id": aset["id"]}, {"_id": 0})
            if _doc:
                jadwalkan_sync("assets", _doc)
        except Exception:
            pass
        await log_audit("opname_terapkan", aset.get("activity_id") or "",
                        aset["id"], asset_code=aset.get("asset_code") or "",
                        asset_name=aset.get("asset_name") or "",
                        username=username or "system",
                        kode_satker=kode_satker_user(_user),
                        detail=(lokasi_baru.get("jalur_nama") or "")[:120])
        diterapkan.append({"id": s["id"], "asset_id": aset["id"],
                           "asset_name": aset.get("asset_name") or ""})

    tak_ketemu = [i for i in ids if i not in {s["id"] for s in scans}]
    return {"ok": True, "diterapkan": diterapkan, "dilewati": dilewati,
            "tidak_ditemukan": tak_ketemu,
            "jumlah_diterapkan": len(diterapkan)}


@opname_router.get("/opname/riwayat-aset/{asset_id}")
async def riwayat_scan_aset(asset_id: str, batas: int = Query(50),
                            _user: dict = Depends(require_user)):
    """Jejak pemindaian satu aset (terbaru dulu) — bukti kapan & di mana barang
    terakhir benar-benar terlihat, terlepas dari apa yang tercatat di buku."""
    aset = await db.assets.find_one({"id": asset_id},
                                    {"_id": 0, "id": 1, "activity_id": 1})
    if not aset:
        raise HTTPException(status_code=404, detail="Aset tidak ditemukan")
    await pastikan_akses_aset(_user, aset)
    n = max(1, min(int(batas or 50), 200))
    items = await (db.opname_scan.find({"asset_id": asset_id}, _PROJ)
                   .sort("pada", -1).to_list(n))
    return {"items": items, "jumlah": len(items)}
