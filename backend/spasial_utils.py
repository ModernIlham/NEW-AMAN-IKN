"""Helper SPASIAL murni — parsing koordinat & pembentukan GeoJSON.

Modul ini SENGAJA bebas dependensi berat (tanpa shapely/pyproj) dan bebas I/O
database, sehingga bisa diuji tanpa Mongo dan diimpor dari jalur panas mana pun.

LATAR: koordinat aset disimpan sebagai STRING di `koordinat_latitude` /
`koordinat_longitude` (lihat `asset_fields.py` & `models.py`) — warisan dari
input lapangan yang menerima format koma desimal Indonesia ("-0,8241"). String
TIDAK BISA diindeks `2dsphere`, sehingga setiap kueri peta berbasis area
terpaksa memindai seluruh koleksi. Modul ini menurunkan field `geo` (GeoJSON
Point) dari pasangan string tersebut supaya MongoDB dapat mengindeksnya.

Field string TETAP dipertahankan apa adanya sebagai sumber kebenaran untuk
ekspor/impor/template — `geo` murni TURUNAN dan boleh dibangun ulang kapan saja.

Sebelum modul ini ada, dua parser koordinat hidup terpisah
(`routes/exports.py::_geo_coord` dan `routes/peta_kolaborasi.py::_parse_coord`)
dengan kelemahan yang saling melengkapi: yang satu memeriksa rentang tetapi tidak
memeriksa nilai berhingga, yang lain sebaliknya. Keduanya kini memanggil helper
di sini agar tak ada parser ketiga yang menyimpang.
"""
import math
from typing import Optional

# Batas WGS84. Lintang (latitude) +-90, bujur (longitude) +-180.
BATAS_LINTANG = 90.0
BATAS_BUJUR = 180.0


def parse_koordinat(nilai, batas: float = BATAS_BUJUR) -> Optional[float]:
    """Ubah koordinat (string/angka) menjadi float valid, atau None.

    Menerima format koma desimal Indonesia ("-0,8241" -> -0.8241) karena input
    lapangan dan tempelan dari Excel lazim memakainya.

    Mengembalikan None bila: kosong, bukan angka, tak berhingga (inf/NaN), atau
    di luar `batas`. NaN ditolak eksplisit — perbandingan NaN selalu False
    sehingga tanpa cek `isfinite` nilai itu bisa lolos lewat celah logika.
    """
    if nilai is None:
        return None
    try:
        angka = float(str(nilai).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None
    if not math.isfinite(angka):
        return None
    return angka if abs(angka) <= batas else None


def parse_lintang(nilai) -> Optional[float]:
    """Lintang valid (-90..90) atau None."""
    return parse_koordinat(nilai, BATAS_LINTANG)


def parse_bujur(nilai) -> Optional[float]:
    """Bujur valid (-180..180) atau None."""
    return parse_koordinat(nilai, BATAS_BUJUR)


def koordinat_tertukar(lintang, bujur) -> bool:
    """True bila pasangan ini HANYA masuk akal setelah ditukar.

    Kekeliruan lintang<->bujur adalah jebakan klasik GeoJSON (GeoJSON memakai
    urutan bujur DULU, sementara manusia menyebut "lat, long"). Untuk Indonesia
    kekeliruan itu hampir selalu ketahuan sendiri: bujur nusantara berkisar
    95..141 sehingga bila nilainya ditaruh di kolom lintang ia melanggar batas
    +-90. Fungsi ini dipakai untuk memberi PESAN yang tepat, bukan untuk
    memperbaiki diam-diam — menukar otomatis berisiko memindahkan aset ke
    tempat yang salah tanpa disadari siapa pun.
    """
    if parse_lintang(lintang) is not None:
        return False  # lintang sudah sah — tak ada indikasi tertukar
    return (parse_koordinat(lintang, BATAS_BUJUR) is not None
            and parse_lintang(bujur) is not None)


def bangun_geo_point(lintang, bujur) -> Optional[dict]:
    """GeoJSON Point dari pasangan lintang/bujur, atau None bila tak layak.

    PENTING: GeoJSON (RFC 7946) memakai urutan **[bujur, lintang]** — kebalikan
    dari cara manusia menyebutnya. Urutan terbalik menempatkan seluruh IKN di
    Samudra Hindia dan MongoDB tidak akan mengeluhkannya karena kedua nilai
    masih dalam rentang sah.

    Titik (0, 0) DITOLAK: itu "Null Island" di Teluk Guinea, penanda de-facto
    bahwa parsing koordinat gagal di suatu tempat pada rantai data. Tak ada BMN
    IKN yang berada persis di sana, sehingga menolaknya jauh lebih berguna
    daripada memetakan ribuan aset ke satu titik di tengah laut.
    """
    lat = parse_lintang(lintang)
    lon = parse_bujur(bujur)
    if lat is None or lon is None:
        return None
    if lat == 0.0 and lon == 0.0:
        return None
    return {"type": "Point", "coordinates": [lon, lat]}


def geo_dari_aset(doc: dict) -> Optional[dict]:
    """Turunkan field `geo` dari dokumen aset (memakai field string yang ada)."""
    if not doc:
        return None
    return bangun_geo_point(doc.get("koordinat_latitude"),
                            doc.get("koordinat_longitude"))


def terapkan_geo(doc: dict) -> dict:
    """Sisipkan/buang `geo` pada dokumen aset SESUAI koordinat terkini.

    Dipanggil di jalur tulis. Bila koordinat dikosongkan atau menjadi tak valid,
    `geo` DIBUANG — bukan dibiarkan basi. Tanpa ini, aset yang koordinatnya
    dihapus tetap muncul di kueri area pada posisi lamanya.
    """
    geo = geo_dari_aset(doc)
    if geo:
        doc["geo"] = geo
    else:
        doc.pop("geo", None)
    return doc


def operasi_geo_update(koordinat_baru: dict) -> dict:
    """Bagian `$set`/`$unset` untuk memutakhirkan `geo` pada operasi update.

    `koordinat_baru` cukup berisi field yang relevan; kembalikan dict berisi
    kunci "set" dan "unset" agar pemanggil menggabungkannya ke operasi update
    miliknya sendiri (jalur tulis di repo ini memakai OCC + Idempotency-Key,
    jadi helper ini sengaja TIDAK menyentuh database).
    """
    geo = geo_dari_aset(koordinat_baru)
    return {"set": {"geo": geo}, "unset": {}} if geo else {"set": {}, "unset": {"geo": ""}}


# Field koordinat yang, bila tersentuh sebuah update, mewajibkan `geo` dihitung ulang.
FIELD_KOORDINAT = ("koordinat_latitude", "koordinat_longitude")


def sisip_geo_ke_update(lama: dict, perubahan: dict) -> dict:
    """Selipkan pemutakhiran `geo` ke dalam dict `$set` sebuah update parsial.

    `perubahan` DIMUTASI di tempat (disisipi "geo" bila perlu) dan fungsi
    mengembalikan dict `$unset` yang harus digabung pemanggil — kosong bila tak
    ada yang perlu dibuang.

    Tidak melakukan apa pun bila update tak menyentuh koordinat sama sekali;
    dengan begitu update yang hanya mengubah, misalnya, kondisi barang tidak
    ikut menulis ulang `geo` tanpa alasan.

    Nilai efektif dihitung dari gabungan dokumen LAMA + perubahan, karena
    pengguna lazim mengubah SATU sumbu saja (mis. memperbaiki bujur yang salah
    ketik); menghitung hanya dari `perubahan` akan membuang sumbu yang lain.
    """
    if not any(f in (perubahan or {}) for f in FIELD_KOORDINAT):
        return {}
    efektif = {f: (perubahan.get(f) if f in perubahan else (lama or {}).get(f))
               for f in FIELD_KOORDINAT}
    geo = geo_dari_aset(efektif)
    if geo:
        perubahan["geo"] = geo
        return {}
    perubahan.pop("geo", None)
    return {"geo": ""}
