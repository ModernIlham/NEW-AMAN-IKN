"""GEOFENCE (Fase 12) — aturan area, evaluasi di jalur tulis, register peringatan.

Mesin statusnya murni dan hidup di `geofence_utils`; modul ini yang menyambungkan
mesin itu ke database: memuat aturan, memuat geometri area, memutar observasi
menurut urutan waktu, lalu menyimpan status dan menerbitkan peringatan.

TIGA KEPUTUSAN YANG MENENTUKAN BENTUK MODUL INI:

1. **Evaluasi di jalur TULIS, bukan saat baca.** Geofence yang dihitung saat
   halaman dibuka hanya tahu keadaan SEKARANG; ia melewatkan seluruh perpindahan
   yang terjadi saat tak ada yang menonton — padahal justru itu yang ingin
   diketahui. Selain itu status histeresis butuh melihat SETIAP observasi
   berurutan; menghitungnya belakangan dari data yang sudah dipadatkan mustahil.

2. **Observasi diurutkan waktu sebelum dievaluasi.** Perangkat yang menumpahkan
   antrean offline mengirim batch yang urutannya tak dijamin, dan mesin
   berdwell yang menerima observasi terbalik akan menghitung durasi negatif lalu
   mengambil keputusan yang salah tanpa gejala apa pun.

3. **Peringatan TIDAK didorong ke WebSocket yang ada.** Bus realtime repo ini
   ber-"room" `activity_id` (kegiatan inventarisasi) dan siapa pun yang membuka
   kegiatan itu menerima seluruh isi room — sementara perangkat pelacak tak
   selalu terikat kegiatan mana pun. Menyalurkan posisi aset ke sana berarti
   menyiarkannya ke penonton yang tak seharusnya. Peringatan disimpan ke
   register yang bisa dikueri, ber-scope satker; kanal dorong khusus adalah
   pekerjaan tersendiri, bukan tumpangan.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth_utils import require_admin, require_user, require_writer
from db import db
from shared_utils import (kode_satker_user, log_audit, pastikan_akses_dok_satker,
                          scope_query_field_satker)
import geofence_utils as gf

logger = logging.getLogger(__name__)
geofence_router = APIRouter()

_PROJ = {"_id": 0}
_MAKS_ATURAN = 200          # aturan per perangkat; di atas ini pasti salah pakai
_MAKS_SAPU = 5000           # plafon GLOBAL sapuan berkala (seluruh satker)
_MAKS_EVENT = 500
_JENIS_EVENT = ("masuk", "keluar", "dwell_terlampaui")


# ── Aturan ──────────────────────────────────────────────────────────────────

class AturanIn(BaseModel):
    nama: str
    device_id: str
    area_node_id: str
    jenis: Optional[list] = None            # bawaan: masuk + keluar
    maks_di_luar_jam: Optional[float] = 0   # 0 = tanpa pemantauan dwell
    param: Optional[dict] = None
    aktif: Optional[bool] = True


async def _pastikan_perangkat(user, device_id: str) -> dict:
    dev = await db.iot_perangkat.find_one({"id": str(device_id or "").strip()},
                                          {**_PROJ, "token_hash": 0})
    if not dev:
        raise HTTPException(status_code=404, detail="Perangkat tidak ditemukan")
    await pastikan_akses_dok_satker(user, dev)
    return dev


async def _pastikan_area(user, node_id: str) -> dict:
    node = await db.spasial_node.find_one(
        {"id": str(node_id or "").strip()},
        {"_id": 0, "id": 1, "nama": 1, "tipe": 1, "kode_satker": 1,
         "geometry": 1, "status": 1})
    if not node:
        raise HTTPException(status_code=404, detail="Area denah tidak ditemukan")
    await pastikan_akses_dok_satker(user, node)
    geom = node.get("geometry") or {}
    if not geom:
        # Node tanpa geometri (baru disusun strukturnya) TAK BISA jadi pagar.
        # Menerimanya berarti aturan yang diam selamanya tanpa pernah memberi
        # tahu pemiliknya bahwa ia tak pernah berfungsi.
        raise HTTPException(
            status_code=400,
            detail=(f"Area '{node.get('nama')}' belum punya geometri — gambar "
                    "atau impor batasnya dulu di Hierarki Spasial"))
    if geom.get("type") not in ("Polygon", "MultiPolygon"):
        # Node BOLEH bergeometri Point (mis. titik penanda) dan itu sah sebagai
        # data spasial — tetapi sebuah PAGAR menuntut luasan. Titik tak punya
        # dalam/luar: jaraknya selalu tak-hingga, aturannya bisu selamanya, dan
        # kebisuan itu tak bisa dibedakan dari "aset memang tak pernah keluar".
        raise HTTPException(
            status_code=400,
            detail=(f"Area '{node.get('nama')}' bergeometri {geom.get('type')} "
                    "— pagar membutuhkan poligon (area berluas), bukan titik "
                    "atau garis"))
    return node


@geofence_router.post("/geofence/aturan")
async def buat_aturan(payload: AturanIn, user: dict = Depends(require_admin)):
    """Pasang pagar: perangkat X dipantau terhadap area Y."""
    nama = str(payload.nama or "").strip()
    if not nama:
        raise HTTPException(status_code=400, detail="Nama aturan wajib diisi")
    dev = await _pastikan_perangkat(user, payload.device_id)
    node = await _pastikan_area(user, payload.area_node_id)

    jenis = [j for j in (payload.jenis or ["masuk", "keluar"])
             if j in _JENIS_EVENT]
    if not jenis:
        raise HTTPException(
            status_code=400,
            detail=f"Jenis peringatan harus salah satu dari: {', '.join(_JENIS_EVENT)}")

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": "gf_" + uuid.uuid4().hex[:16],
        "kode_satker": kode_satker_user(user) or dev.get("kode_satker") or "",
        "nama": nama[:120],
        "device_id": dev["id"], "device_nama": dev.get("nama") or "",
        "asset_id": dev.get("asset_id") or "",
        "area_node_id": node["id"], "area_nama": node.get("nama") or "",
        "jenis": jenis,
        "maks_di_luar_jam": max(0.0, float(payload.maks_di_luar_jam or 0)),
        # Disimpan APA ADANYA; penyaringan nilai ngawur terjadi saat dipakai
        # (gf.ringkas_aturan) supaya aturan lama tak jadi tak sah saat daftar
        # parameter bertambah.
        "param": dict(payload.param or {}),
        "aktif": bool(payload.aktif if payload.aktif is not None else True),
        "created_at": now, "updated_at": now,
        "created_by": user.get("username", ""),
    }
    await db.iot_geofence_aturan.insert_one(dict(doc))
    await log_audit("geofence_aturan_buat", "", doc["id"],
                    username=user.get("username", "system"),
                    kode_satker=doc["kode_satker"],
                    detail=f"{nama}: {dev.get('nama')} ↔ {node.get('nama')}")
    return {**doc, "param_efektif": gf.ringkas_aturan(doc)}


@geofence_router.get("/geofence/aturan")
async def daftar_aturan(_user: dict = Depends(require_user)):
    items = await (db.iot_geofence_aturan.find(scope_query_field_satker(_user), _PROJ)
                   .sort("created_at", -1).to_list(_MAKS_ATURAN))
    for a in items:
        a["param_efektif"] = gf.ringkas_aturan(a)
    return {"items": items, "jumlah": len(items),
            "param_bawaan": gf.GEO_PARAM, "jenis_tersedia": list(_JENIS_EVENT)}


@geofence_router.put("/geofence/aturan/{aturan_id}")
async def ubah_aturan(aturan_id: str, payload: AturanIn,
                      user: dict = Depends(require_admin)):
    lama = await db.iot_geofence_aturan.find_one({"id": aturan_id}, _PROJ)
    if not lama:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    await pastikan_akses_dok_satker(user, lama)
    dev = await _pastikan_perangkat(user, payload.device_id)
    node = await _pastikan_area(user, payload.area_node_id)
    jenis = [j for j in (payload.jenis or ["masuk", "keluar"]) if j in _JENIS_EVENT]
    ubah = {"nama": str(payload.nama or "").strip()[:120] or lama.get("nama"),
            "device_id": dev["id"], "device_nama": dev.get("nama") or "",
            "asset_id": dev.get("asset_id") or "",
            "area_node_id": node["id"], "area_nama": node.get("nama") or "",
            "jenis": jenis or lama.get("jenis") or ["masuk", "keluar"],
            "maks_di_luar_jam": max(0.0, float(payload.maks_di_luar_jam or 0)),
            "param": dict(payload.param or {}),
            "aktif": bool(payload.aktif if payload.aktif is not None else True),
            # kode_satker IKUT perangkat barunya. Membiarkannya menempel pada
            # nilai lama membuat peringatan aset satker B mendarat di register
            # satker A — terlihat oleh mata yang tak berhak, dan luput dari mata
            # yang berhak.
            "kode_satker": (dev.get("kode_satker") or lama.get("kode_satker")
                            or kode_satker_user(user)),
            "updated_at": datetime.now(timezone.utc).isoformat()}
    await db.iot_geofence_aturan.update_one({"id": aturan_id}, {"$set": ubah})
    if (lama.get("device_id") != ubah["device_id"]
            or lama.get("area_node_id") != ubah["area_node_id"]):
        # Pasangan perangkat↔area berubah = pagar yang BERBEDA. Status lama
        # (mis. "sudah DALAM") tak lagi punya arti dan akan menekan event masuk
        # yang seharusnya terbit; dibuang supaya mesin mulai dari nol.
        await db.iot_geofence_state.delete_many({"aturan_id": aturan_id})
    await log_audit("geofence_aturan_ubah", "", aturan_id,
                    username=user.get("username", "system"),
                    # Satker DOKUMEN, bukan satker pemanggil: super-admin yang
                    # mengubah pagar satker A tak boleh membuat jejaknya hilang
                    # dari log satker A.
                    kode_satker=ubah["kode_satker"],
                    detail=str(ubah["nama"])[:80])
    return {"ok": True, "param_efektif": gf.ringkas_aturan(ubah)}


@geofence_router.delete("/geofence/aturan/{aturan_id}")
async def hapus_aturan(aturan_id: str, user: dict = Depends(require_admin)):
    a = await db.iot_geofence_aturan.find_one({"id": aturan_id}, _PROJ)
    if not a:
        raise HTTPException(status_code=404, detail="Aturan tidak ditemukan")
    await pastikan_akses_dok_satker(user, a)
    await db.iot_geofence_aturan.delete_one({"id": aturan_id})
    await db.iot_geofence_state.delete_many({"aturan_id": aturan_id})
    # Peringatan yang SUDAH terbit sengaja TIDAK ikut dihapus: ia catatan
    # peristiwa yang benar-benar terjadi, dan riwayat pengawasan tak boleh
    # lenyap hanya karena pemantauannya dihentikan hari ini.
    await log_audit("geofence_aturan_hapus", "", aturan_id,
                    username=user.get("username", "system"),
                    kode_satker=a.get("kode_satker") or kode_satker_user(user),
                    detail=str(a.get("nama") or aturan_id)[:80])
    return {"ok": True}


# ── Evaluasi (dipanggil jalur ingest) ───────────────────────────────────────

async def evaluasi_perangkat(dev: dict, observasi: list,
                             sekarang: datetime) -> dict:
    """Putar observasi yang baru masuk melalui semua aturan aktif perangkat.

    Dipanggil dari jalur ingest SETELAH observasi tersimpan. Kegagalan di sini
    TIDAK BOLEH menggagalkan penerimaan data: posisi yang sudah tersimpan lebih
    berharga daripada peringatan yang gagal dihitung, dan perangkat yang
    menerima 500 akan mengirim ulang batch yang sebenarnya sudah aman.
    """
    if not observasi:
        return {"event": 0, "aturan": 0}
    aturan = await db.iot_geofence_aturan.find(
        {"device_id": dev["id"], "aktif": True}, _PROJ).to_list(_MAKS_ATURAN)
    if not aturan:
        return {"event": 0, "aturan": 0}

    # URUT WAKTU — lihat catatan #2 di docstring modul. Diurutkan lewat waktu
    # yang SUDAH DIURAI, bukan perbandingan string: "…T10:00+07:00" dan
    # "…T04:00Z" menunjuk instan yang sama tetapi berbeda jauh sebagai teks,
    # dan perangkat berbeda merek memang menulis offset berbeda.
    urut = sorted(observasi, key=lambda o: gf.kunci_urut(o.get("ts_device")))

    # Geometri seluruh area diambil dalam SATU kueri, bukan satu per aturan.
    nid_set = {a.get("area_node_id") for a in aturan if a.get("area_node_id")}
    geom_area = {}
    if nid_set:
        async for n in db.spasial_node.find({"id": {"$in": list(nid_set)}},
                                            {"_id": 0, "id": 1, "geometry": 1}):
            geom_area[n["id"]] = n.get("geometry")

    jumlah = 0
    for a in aturan:
        try:
            jumlah += await _evaluasi_satu_aturan(
                a, dev, urut, geom_area.get(a.get("area_node_id")), sekarang)
        except Exception as e:      # noqa: BLE001
            # Satu aturan yang gagal TIDAK BOLEH membatalkan sisanya: aturan
            # ke-3 yang bermasalah akan membuat aturan ke-4 dan seterusnya
            # tak pernah dievaluasi, dan diamnya terlihat persis seperti
            # "tak ada yang perlu dilaporkan".
            logger.warning("Aturan geofence %s gagal dievaluasi: %s",
                           a.get("id"), e)
    return {"event": jumlah, "aturan": len(aturan)}


async def _evaluasi_satu_aturan(a: dict, dev: dict, urut: list, geom,
                                sekarang: datetime) -> int:
    if not geom:
        # Area kehilangan geometri (node dihapus/diubah) — dicatat, tidak
        # dilewati diam-diam. Pagar yang mati tanpa suara adalah pagar yang
        # dikira masih menjaga.
        logger.warning("Aturan geofence %s menunjuk area %s yang tak "
                       "bergeometri — tidak dievaluasi",
                       a.get("id"), a.get("area_node_id"))
        return 0
    param = gf.ringkas_aturan(a)
    kunci = {"aturan_id": a["id"], "device_id": dev["id"]}
    st = await db.iot_geofence_state.find_one(kunci, _PROJ)
    if not st:
        st = gf.status_awal(dev["id"], a.get("area_node_id") or "")
        st["aturan_id"] = a["id"]
    baru = []
    for obs in urut:
        hasil = gf.evaluasi(st, obs, geom, sekarang, param)
        st = hasil["state"]
        st["aturan_id"] = a["id"]
        ev = hasil["event"]
        if ev and ev["jenis"] in (a.get("jenis") or []):
            baru.append(_dok_event(a, dev, ev))
    # PERINGATAN ditulis SEBELUM status. Urutan sebaliknya berarti: status
    # sudah bilang "sudah keluar" sementara peringatannya gagal tersimpan —
    # dan karena status tak akan berpindah lagi, peringatan itu hilang
    # PERMANEN. Dengan urutan ini, kegagalan menyimpan status hanya membuat
    # batch berikutnya menghitung ulang, dan cooldown menelan duplikatnya.
    if baru:
        await db.iot_geofence_event.insert_many(baru, ordered=False)
    # Status ditulis SEKALI per aturan, bukan per observasi: batch 500 titik
    # kalau tidak akan menghasilkan 500 tulis untuk satu baris yang sama.
    await db.iot_geofence_state.update_one(kunci, {"$set": st}, upsert=True)
    return len(baru)


def _dok_event(aturan: dict, dev: dict, ev: dict) -> dict:
    return {
        "id": "ge_" + uuid.uuid4().hex[:16],
        "kode_satker": aturan.get("kode_satker") or dev.get("kode_satker") or "",
        "aturan_id": aturan["id"], "aturan_nama": aturan.get("nama") or "",
        "device_id": dev["id"], "device_nama": dev.get("nama") or "",
        "asset_id": dev.get("asset_id") or "",
        "asset_name": dev.get("asset_name") or "",
        "area_node_id": aturan.get("area_node_id") or "",
        "area_nama": aturan.get("area_nama") or "",
        "jenis": ev["jenis"], "pada": ev["pada"], "jarak_m": ev.get("jarak_m"),
        # `retro` = peristiwa dari antrean offline, bukan yang sedang terjadi.
        # Dibedakan supaya operator tak mengejar aset yang sudah kembali kemarin.
        "retro": bool(ev.get("retro")),
        "titik": ev.get("titik") or [],
        "dibaca": False, "penertiban_id": "",
        "dibuat_pada": datetime.now(timezone.utc).isoformat(),
    }


async def sapu_dwell(sekarang: Optional[datetime] = None) -> int:
    """Terbitkan `dwell_terlampaui` untuk aset yang keluar dan tak kunjung balik.

    Dijalankan berkala, BUKAN dari ingest — dan justru itu intinya: aset yang
    keluar area lalu perangkatnya mati tak akan pernah mengirim observasi lagi,
    sehingga peringatan yang hanya lahir dari data masuk tak akan pernah terbit
    untuk kasus yang paling perlu diketahui.
    """
    from pymongo.errors import DuplicateKeyError

    kini = sekarang or datetime.now(timezone.utc)
    terbit = 0
    # Plafon GLOBAL (bukan per perangkat) + urutan pasti. Memakai plafon
    # per-perangkat di sini berarti aturan ke-201 dan seterusnya tak pernah
    # tersapu sama sekali — diam yang tak bisa dibedakan dari "tak ada temuan".
    aturan = await (db.iot_geofence_aturan.find(
        {"aktif": True, "maks_di_luar_jam": {"$gt": 0}}, _PROJ)
        .sort("created_at", 1).to_list(_MAKS_SAPU))
    for a in aturan:
        if "dwell_terlampaui" not in (a.get("jenis") or []):
            continue
        st = await db.iot_geofence_state.find_one(
            {"aturan_id": a["id"], "device_id": a.get("device_id")}, _PROJ)
        if not st or gf.jatuh_tempo_dwell(st, a, kini) is None:
            continue
        sejak = (st.get("transisi") or {}).get("keluar") or ""
        dev = await db.iot_perangkat.find_one({"id": a.get("device_id")},
                                              {**_PROJ, "token_hash": 0})
        if not dev:
            continue
        dok = _dok_event(a, dev, {"jenis": "dwell_terlampaui",
                                  "pada": kini.isoformat(),
                                  "jarak_m": st.get("jarak_m"), "retro": False,
                                  "titik": []})
        dok["sejak"] = sejak
        try:
            # Idempoten: satu peringatan per KEPERGIAN, bukan per sapuan —
            # ditegakkan INDEKS UNIK, bukan cek-lalu-tulis. Loop pemeliharaan
            # berjalan di SETIAP worker uvicorn, jadi dua sapuan nyaris serempak
            # akan sama-sama lolos pemeriksaan "sudah ada?" lalu menyisipkan
            # dua peringatan untuk kepergian yang sama.
            await db.iot_geofence_event.insert_one(dok)
            terbit += 1
        except DuplicateKeyError:
            continue                # worker lain sudah menerbitkannya
    return terbit


# ── Register peringatan ─────────────────────────────────────────────────────

@geofence_router.get("/geofence/event")
async def daftar_event(belum_dibaca: bool = Query(False),
                       device_id: str = Query(""),
                       batas: int = Query(100),
                       _user: dict = Depends(require_user)):
    q = scope_query_field_satker(_user)
    if belum_dibaca:
        q["dibaca"] = False
    if str(device_id or "").strip():
        q["device_id"] = device_id.strip()
    n = max(1, min(int(batas or 100), _MAKS_EVENT))
    items = await (db.iot_geofence_event.find(q, _PROJ)
                   .sort("dibuat_pada", -1).to_list(n))
    belum = await db.iot_geofence_event.count_documents(
        {**scope_query_field_satker(_user), "dibaca": False})
    return {"items": items, "jumlah": len(items), "belum_dibaca": belum}


@geofence_router.post("/geofence/event/{event_id}/dibaca")
async def tandai_dibaca(event_id: str, user: dict = Depends(require_writer)):
    ev = await db.iot_geofence_event.find_one({"id": event_id}, _PROJ)
    if not ev:
        raise HTTPException(status_code=404, detail="Peringatan tidak ditemukan")
    await pastikan_akses_dok_satker(user, ev)
    await db.iot_geofence_event.update_one(
        {"id": event_id},
        {"$set": {"dibaca": True, "dibaca_oleh": user.get("username", ""),
                  "dibaca_pada": datetime.now(timezone.utc).isoformat()}})
    return {"ok": True}


class EskalasiIn(BaseModel):
    uraian: Optional[str] = ""


@geofence_router.post("/geofence/event/{event_id}/penertiban")
async def jadikan_penertiban(event_id: str, payload: EskalasiIn,
                             user: dict = Depends(require_writer)):
    """Naikkan satu peringatan jadi tiket penertiban Wasdal.

    SENGAJA manual, bukan otomatis. Tiket penertiban punya tenggat 15 hari kerja
    dan masuk register resmi PMK 207/2021; membuatnya otomatis dari pembacaan
    GPS berarti membanjiri register wajib itu dengan tiket yang mungkin hanya
    disebabkan pagar salah pasang. Manusia yang memutuskan mana peringatan yang
    naik jadi perkara — sistem yang menyiapkan bahannya.
    """
    from wasdal_utils import status_tenggat_penertiban, tambah_hari_kerja

    ev = await db.iot_geofence_event.find_one({"id": event_id}, _PROJ)
    if not ev:
        raise HTTPException(status_code=404, detail="Peringatan tidak ditemukan")
    await pastikan_akses_dok_satker(user, ev)

    hari_ini = datetime.now(timezone.utc).date().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    uraian = str(payload.uraian or "").strip() or (
        f"Peringatan geofence: {ev.get('device_nama') or ev.get('device_id')} "
        f"{ev.get('jenis')} area {ev.get('area_nama')} pada {ev.get('pada')}")
    tiket = {
        "id": str(uuid.uuid4()),
        "kode_satker": ev.get("kode_satker") or kode_satker_user(user),
        "sumber": "pemantauan",
        "tanggal_dasar": hari_ini,
        "tenggat": tambah_hari_kerja(hari_ini),
        "objek": "Pengamanan",
        "uraian": uraian[:1000],
        "status": "berjalan", "tindak_lanjut": "", "tanggal_selesai": "",
        "asset_id": ev.get("asset_id") or "",
        "asset_name": ev.get("asset_name") or "",
        "geofence_event_id": ev["id"],
        "created_by": user.get("username"), "created_at": now, "updated_at": now,
    }
    if ev.get("titik") and ev.get("area_node_id"):
        # Titik kejadian ikut dibawa supaya tiket bisa dibuka langsung di denah
        # (pola snapshot lokasi Fase 8).
        tiket["lokasi_spasial"] = {"titik": ev["titik"],
                                   "node_id": ev.get("area_node_id") or "",
                                   "node_nama": ev.get("area_nama") or "",
                                   "node_tipe": "", "jalur_nama": ""}
    # KLAIM ATOMIK sebelum menyisipkan tiket. Cek-lalu-tulis (`if
    # ev["penertiban_id"]` lalu insert) bisa dilewati dua klik beruntun atau dua
    # operator sekaligus, dan hasilnya DUA tiket bertenggat di register wajib
    # PMK 207/2021 untuk satu peristiwa yang sama — dokumen resmi ganda yang
    # harus ditutup manual satu per satu.
    klaim = await db.iot_geofence_event.find_one_and_update(
        {"id": event_id, "$or": [{"penertiban_id": ""},
                                 {"penertiban_id": {"$exists": False}}]},
        {"$set": {"penertiban_id": tiket["id"], "dibaca": True}})
    if not klaim:
        raise HTTPException(status_code=409,
                            detail="Peringatan ini sudah pernah dinaikkan")
    await db.penertiban.insert_one(dict(tiket))
    await log_audit("geofence_eskalasi_penertiban", "", tiket["id"],
                    username=user.get("username", "system"),
                    kode_satker=tiket["kode_satker"],
                    detail=uraian[:80])
    tiket["info_tenggat"] = status_tenggat_penertiban(tiket, hari_ini)
    return tiket
