"""Penempatan aset ke node denah OTOMATIS dari koordinat inventarisasi.

Permintaan pemilik (verbatim): *"kenapa juga halaman hierarki spasial harus
scan perpindahan sendiri dan tidak melalui inventarisasi aset karena berpusat
disana semua disetiap jenis kegiatan juga pasti diupdate dan diinventarisasi.
integrasikan saja."*

Sebelum modul ini, satu-satunya jalan aset "menempati" ruangan/gedung di
denah adalah tindakan TERPISAH: tombol Denah per aset, atau pindai stiker QR
di halaman Hierarki Spasial. Padahal inventarisasi lapangan sudah merekam
koordinat GPS setiap aset — data yang cukup untuk menempatkannya sendiri.
Akibatnya panel isi lokasi dan angka "Tercatat" opname kosong (0/0/0)
meski ribuan aset sudah diinventarisasi lengkap dengan koordinat.

Integrasi: saat jalur INVENTARISASI menulis koordinat aset (PATCH/POST/PUT
/assets — muara kamera lapangan, antrean luring, lembar edit cepat, geser
marker peta) dan aset itu BELUM punya penempatan, server menempatkannya ke
node denah aktif terdalam yang memuat titiknya. Angka "Tercatat" opname,
panel isi lokasi, dan daftar "Belum terpindai" langsung hidup dari data
inventarisasi; pindai QR tetap ada sebagai PENGUKUHAN fisik (kolom
"Dikukuhkan" — jejak bukti yang sengaja berbeda dari catatan buku).

Keputusan desain (masing-masing meniru preseden repo):

1. HANYA penempatan pertama. Aset yang sudah punya `lokasi_spasial` (manual
   lewat dialog Denah, hasil /opname/terapkan, maupun otomatis sebelumnya)
   TIDAK disentuh — GPS lapangan bergetar beberapa meter antar pemotretan,
   dan mengikutinya berarti membanjiri riwayat custody dengan "perpindahan"
   palsu. Perpindahan tetap tindakan sadar (dialog Denah / opname terapkan).
2. Kode satker dari KEGIATAN INDUK aset, fail-closed: tanpa kegiatan atau
   kegiatan tanpa kode → lewati, jangan cari lintas-satker (preseden
   routes/iot.py `_node_di_titik`: "mencari lintas-satker akan menautkan
   aset ke gedung milik satker lain"). Cabang kode-kosong-tanpa-filter milik
   `scope_query_field_satker` adalah semantik privilese super-admin, bukan
   derivasi data — sengaja TIDAK ditiru di sini.
3. Berhenti di GEDUNG (ORDINAL_GEDUNG): lantai/ruangan tak terpilih dari
   koordinat 2D — semua lantai berbagi jejak 2D yang sama. Penyempitan ke
   lantai/ruangan tetap lewat dialog Denah atau pindai QR.
4. Tanpa afordansi interaktif: tidak menghitung draft penutup, tidak mencari
   "terdekat" — titik di luar semua poligon aktif berarti lewati diam-diam.
   Aset di lapangan terbuka memang sah tanpa node.
5. Gerbang murah dahulu: tanpa sentuhan koordinat / status "Ditemukan",
   fungsi keluar sebelum satu pun kueri DB — PATCH foto/harga/dll. tidak
   membayar apa-apa.

Jalur massal (batch-update, impor Excel) SENGAJA belum dihook: batch adalah
satu `update_many` (tak bisa per-aset murah) dan impor bisa ribuan baris ×
kueri geo; keduanya juga bukan jalur lapangan. Bila dibutuhkan, jadikan job
latar terpisah.
"""
import logging

from db import db
import spasial_utils as su

logger = logging.getLogger("aman.spasial_penempatan")

# Duplikat lokal yang disengaja (pola routes/iot.py): modul tingkat-atas tak
# boleh mengimpor routes/spasial (router) hanya demi dua konstanta.
ORDINAL_GEDUNG = 80
_MAKS_KANDIDAT = 200
# Field yang dibutuhkan peringkat_kandidat + pilih_rantai +
# snapshot_lokasi_temuan; `geometry` sengaja TIDAK diproyeksikan (SLA).
_PROJ_RANTAI = {"_id": 0, "id": 1, "tipe": 1, "ordinal_level": 1, "nama": 1,
                "kode": 1, "parent_id": 1, "ancestors": 1, "ancestors_nama": 1,
                "prioritas": 1, "metrik": 1}


async def kode_satker_kegiatan(activity_id) -> str:
    """Kode satker kegiatan induk; "" bila kegiatan tak ada / tanpa kode."""
    aid = str(activity_id or "").strip()
    if not aid:
        return ""
    keg = await db.inventory_activities.find_one(
        {"id": aid}, {"_id": 0, "kode_satker": 1})
    return str((keg or {}).get("kode_satker") or "").strip()


async def node_terdalam_di_titik(kode_satker: str, lon: float, lat: float):
    """Node AKTIF terdalam (≤ gedung) milik satker yang memuat titik.

    `$in [kode, "", None]` = padanan eksplisit `scope_query_field_satker`:
    node era-lama tanpa kode ikut, supaya hasil hook sama dengan yang dilihat
    operator satker itu di /spasial/lokasi-di-titik. Kode KOSONG → None
    (fail-closed, lihat keputusan desain #2).
    """
    if not kode_satker:
        return None
    # Null Island (0,0) — penanda de-facto parsing koordinat gagal di suatu
    # tempat pada rantai data, bukan posisi. Invarian yang sama ditegakkan
    # `spasial_utils.titik_geojson`; menirunya di sini menjaga hook tak
    # pernah "menemukan" gedung untuk data rusak.
    if float(lat) == 0.0 and float(lon) == 0.0:
        return None
    titik = {"type": "Point", "coordinates": [float(lon), float(lat)]}
    kandidat = await db.spasial_node.find({
        "kode_satker": {"$in": [kode_satker, "", None]},
        "status": "aktif",
        "ordinal_level": {"$lte": ORDINAL_GEDUNG},
        "geometry": {"$geoIntersects": {"$geometry": titik}},
    }, _PROJ_RANTAI).sort("ordinal_level", -1).to_list(_MAKS_KANDIDAT)
    return su.pilih_rantai(kandidat)["terdalam"]


async def penempatan_dari_inventarisasi(existing: dict, update_data: dict,
                                        username: str, now: str):
    """Hitung `lokasi_spasial` otomatis untuk satu tulisan aset, atau None.

    Dipanggil SEBELUM CAS/insert: hasil non-None digabung pemanggil ke
    update/dokumen sehingga penempatan ikut atomik dengan tulisan utamanya;
    baris `riwayat_lokasi_aset` ditulis pemanggil SETELAH tulisan sukses
    (pola set_lokasi_aset — riwayat tak boleh mendahului kenyataan).

    `existing` = dokumen tersimpan ({} untuk create); `update_data` = field
    yang akan ditulis. Semua kondisi diperiksa dari murah ke mahal.
    """
    sentuh_koordinat = ("koordinat_latitude" in update_data
                       or "koordinat_longitude" in update_data)
    jadi_ditemukan = str(update_data.get("inventory_status") or "") == "Ditemukan"
    if not (sentuh_koordinat or jadi_ditemukan):
        return None
    # Penempatan yang SUDAH ada menang — manual, opname, maupun otomatis
    # sebelumnya (keputusan desain #1). Jalur yang menulis lokasi_spasial
    # eksplisit (tak ada saat ini di PATCH/PUT/POST aset) juga menang.
    if existing.get("lokasi_spasial") or update_data.get("lokasi_spasial"):
        return None
    lat = su.parse_lintang(update_data.get(
        "koordinat_latitude", existing.get("koordinat_latitude")))
    lon = su.parse_bujur(update_data.get(
        "koordinat_longitude", existing.get("koordinat_longitude")))
    if lat is None or lon is None:
        return None
    try:
        kode = await kode_satker_kegiatan(
            update_data.get("activity_id") or existing.get("activity_id"))
        if not kode:
            return None
        node = await node_terdalam_di_titik(kode, lon, lat)
    except Exception as e:
        # BEST-EFFORT: tulisan inventarisasi adalah urat nadi aplikasi;
        # penempatan hanyalah pengayaan. Kegagalan di sini (indeks geo belum
        # terpasang, DB uji tanpa dukungan $geoIntersects, dsb.) dicatat lalu
        # dilewati — TIDAK pernah menggagalkan simpan aset.
        logger.warning("penempatan otomatis dilewati: %s", e)
        return None
    if node is None:
        return None
    lokasi = su.snapshot_lokasi_temuan(node, lon, lat)
    lokasi.update({
        "ditandai_oleh": str(username or ""),
        "ditandai_pada": str(now or ""),
        # Pembeda asal-usul di panel/laporan: penempatan ini derivasi mesin
        # dari koordinat inventarisasi, bukan penunjukan manual operator.
        "sumber": "inventarisasi",
    })
    return lokasi


async def catat_penempatan(aset: dict, lokasi: dict, username: str,
                           now: str) -> None:
    """Riwayat custody + jejak audit untuk satu penempatan otomatis.

    Dipanggil SETELAH tulisan aset berhasil — riwayat tak boleh mendahului
    kenyataan (pola `set_lokasi_aset`).

    Pembungkus try/except di sini BUKAN kerapian, melainkan bagian dari
    kontrak best-effort modul ini: saat fungsi ini berjalan, asetnya SUDAH
    tersimpan. Membiarkan galat naik berarti membalas 500 atas tulisan yang
    BERHASIL — dan klien lapangan (termasuk antrean luring yang otomatis
    mengirim ulang) akan memperlakukannya sebagai kegagalan lalu mengulang
    permintaan yang sebenarnya sudah sukses.
    """
    try:
        from shared_utils import log_audit
        await db.riwayat_lokasi_aset.insert_one(su.entri_riwayat_lokasi(
            str(aset.get("id") or ""), None, lokasi, username, now))
        await log_audit(
            "aset_lokasi_otomatis", str(aset.get("activity_id") or ""),
            str(aset.get("id") or ""), str(aset.get("asset_code") or ""),
            str(aset.get("asset_name") or ""), username or "system",
            detail=(lokasi.get("jalur_nama") or "")[:120])
    except Exception as e:                       # noqa: BLE001 — sengaja luas
        logger.warning("jejak penempatan otomatis dilewati (%s): %s",
                       aset.get("id"), e)
