"""Helper MURNI ingest posisi IoT (Fase 11) — validasi, idempotensi, normalisasi.

Bebas I/O & DB supaya bisa diuji tanpa infrastruktur dan dipanggil dari jalur
panas ingest.

DUA SIFAT BAWAAN pengiriman IoT yang menentukan desain modul ini:

1. **At-least-once.** Perangkat lapangan kehilangan sinyal, mengirim ulang
   batch yang sebenarnya sudah tiba, lalu menyala kembali dan mengirim antrean
   offline-nya. DUPLIKAT ADALAH NORMAL, bukan anomali. Penangkalnya bukan
   "jangan kirim dua kali" (mustahil dijamin perangkat), melainkan **id stabil
   per observasi** yang dihitung dari ISI-nya, sehingga penyimpanan menolak
   kembar tanpa perlu koordinasi dengan pengirim.

2. **Jam perangkat tidak dapat dipercaya.** GPS murah kerap menyala dengan
   jam 1970 atau melompat setelah sinkronisasi. Waktu perangkat TETAP disimpan
   (bahan diagnosis), tetapi ditandai `ts_ragu` dan tak pernah dipakai sebagai
   satu-satunya sumber urutan.
"""
import hashlib
import math
from datetime import datetime, timedelta, timezone

import spasial_utils as su

MAKS_OBSERVASI_PER_BATCH = 500
# Jam perangkat yang menyimpang lebih dari ini dari waktu server dianggap ragu.
AMBANG_SKEW_JAM = 24
# Lebih tua dari ini = data basi yang tak berguna untuk penatausahaan; ditolak
# agar antrean offline bertahun dari perangkat terlantar tak membanjiri koleksi.
MAKS_UMUR_HARI = 30
# Kecepatan di atas ini mustahil untuk BMN darat (≈ pesawat jet) — penanda
# koordinat kacau, bukan perjalanan sungguhan.
MAKS_KECEPATAN_KMH = 400.0


def obs_id(device_id, ts_device, lon, lat) -> str:
    """ID stabil per observasi — kunci idempotensi.

    Dihitung dari (perangkat, waktu perangkat, koordinat) sehingga pengiriman
    ULANG observasi yang SAMA menghasilkan id yang sama dan ditolak indeks
    unik. Server TIDAK ikut dalam hash: memasukkan waktu terima akan membuat
    tiap pengiriman ulang tampak sebagai observasi baru — persis kegagalan
    yang hendak dicegah.
    """
    bahan = f"{device_id}|{ts_device}|{lon}|{lat}"
    return "sha1:" + hashlib.sha1(bahan.encode("utf-8")).hexdigest()


def _parse_ts(nilai):
    if isinstance(nilai, datetime):
        return nilai if nilai.tzinfo else nilai.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(nilai).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError, AttributeError):
        return None


def normalisasi_observasi(mentah: dict, device_id: str, sekarang: datetime) -> dict:
    """Satu observasi mentah → dokumen tervalidasi, atau {"tolak": alasan}.

    Nilai yang TIDAK masuk akal dibuang PER FIELD, bukan menolak seluruh
    observasi: GPS yang melaporkan kecepatan kacau tetapi koordinat waras masih
    berguna untuk penatausahaan. Yang menggugurkan seluruh observasi hanyalah
    koordinat tak sah — tanpa itu tak ada yang bisa dicatat.
    """
    lat = su.parse_lintang(mentah.get("lat"))
    lon = su.parse_bujur(mentah.get("lon"))
    if lat is None or lon is None:
        return {"tolak": "koordinat tidak valid"}
    if lat == 0.0 and lon == 0.0:
        # Null Island = penanda de-facto parsing gagal di rantai data, bukan
        # posisi sungguhan (lihat spasial_utils.bangun_geo_point).
        return {"tolak": "koordinat (0,0) — kemungkinan sensor gagal"}

    ts_dev = _parse_ts(mentah.get("ts_device"))
    ts_ragu = False
    if ts_dev is None:
        ts_dev, ts_ragu = sekarang, True
    else:
        skew = abs((sekarang - ts_dev).total_seconds()) / 3600.0
        if skew > AMBANG_SKEW_JAM:
            ts_ragu = True
    if ts_dev > sekarang + timedelta(hours=1):
        # Observasi "dari masa depan" — jam perangkat maju. Waktu server dipakai
        # sebagai jangkar agar urutan tetap masuk akal.
        ts_dev, ts_ragu = sekarang, True
    if ts_dev < sekarang - timedelta(days=MAKS_UMUR_HARI):
        return {"tolak": f"observasi lebih tua dari {MAKS_UMUR_HARI} hari"}

    doc = {
        "obs_id": obs_id(device_id, ts_dev.isoformat(), lon, lat),
        "device_id": device_id,
        "ts_device": ts_dev.isoformat(),
        "ts_server": sekarang.isoformat(),
        "geo": {"type": "Point", "coordinates": [lon, lat]},
        "ts_ragu": ts_ragu,
    }
    akurasi = su.parse_koordinat(mentah.get("akurasi_m"), math.inf)
    if akurasi is not None and akurasi >= 0:
        doc["akurasi_m"] = round(akurasi, 1)
    laju = su.parse_koordinat(mentah.get("kecepatan_kmh"), math.inf)
    if laju is not None and 0 <= laju <= MAKS_KECEPATAN_KMH:
        doc["kecepatan_kmh"] = round(laju, 1)
    arah = su.parse_koordinat(mentah.get("arah_deg"), math.inf)
    if arah is not None and 0 <= arah <= 360:
        doc["arah_deg"] = round(arah, 1)
    baterai = su.parse_koordinat(mentah.get("baterai_persen"), math.inf)
    if baterai is not None and 0 <= baterai <= 100:
        doc["baterai_persen"] = int(baterai)
    return doc


def siapkan_batch(batch, device_id: str, sekarang: datetime) -> dict:
    """Batch mentah → {"terima": [...], "tolak": [{i, alasan}], "plafon": bool}.

    Observasi ditolak DILAPORKAN dengan alasan per indeks, tak dibuang diam-
    diam: perangkat yang koordinatnya selalu ditolak harus bisa diketahui
    pemiliknya, bukan tampak "terkirim" padahal tak ada yang tersimpan.
    """
    if not isinstance(batch, (list, tuple)):
        return {"terima": [], "tolak": [{"i": 0, "alasan": "batch harus daftar"}],
                "plafon": False}
    plafon = len(batch) > MAKS_OBSERVASI_PER_BATCH
    terima, tolak, terlihat = [], [], set()
    for i, mentah in enumerate(batch[:MAKS_OBSERVASI_PER_BATCH]):
        if not isinstance(mentah, dict):
            tolak.append({"i": i, "alasan": "observasi harus objek"})
            continue
        doc = normalisasi_observasi(mentah, device_id, sekarang)
        if "tolak" in doc:
            tolak.append({"i": i, "alasan": doc["tolak"]})
            continue
        # Kembar DI DALAM satu batch (perangkat mengirim ulang isi antrean
        # tanpa membersihkannya) disaring di sini supaya insert_many tak
        # menabrak indeks unik untuk kasus yang bisa dicegah lebih murah.
        if doc["obs_id"] in terlihat:
            tolak.append({"i": i, "alasan": "duplikat dalam batch ini"})
            continue
        terlihat.add(doc["obs_id"])
        terima.append(doc)
    return {"terima": terima, "tolak": tolak, "plafon": plafon}


def ringkas_kesehatan(doc: dict, sekarang: datetime) -> dict:
    """Ringkasan kesehatan perangkat dari observasi terakhir — dipakai daftar
    perangkat agar operator melihat mana yang diam tanpa membuka satu per satu."""
    ts = _parse_ts((doc or {}).get("ts_server"))
    diam_menit = None if ts is None else int((sekarang - ts).total_seconds() // 60)
    return {"terakhir_terdengar": (doc or {}).get("ts_server") or "",
            "diam_menit": diam_menit,
            "baterai_persen": (doc or {}).get("baterai_persen"),
            "ts_ragu": bool((doc or {}).get("ts_ragu"))}
