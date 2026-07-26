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


# ═══════════════════════════════════════════════════════════════════════════
# HIERARKI SPASIAL (Fase 2) — registry level & pohon
# ═══════════════════════════════════════════════════════════════════════════
#
# Ordinal BERJARAK 10 supaya tingkat baru bisa disisipkan tanpa migrasi data.
# `kode_baku` tetap benar untuk ekspor & dokumen resmi; `preset_penamaan` HANYA
# mengganti label yang dilihat operator — satu data, dua tampilan.
#
# Dasar urutan (riset Fase 0, lihat docs/ARSITEKTUR-SPASIAL-IOT.md):
#   UU 26/2007 Pasal 1 mendefinisikan Kawasan sebagai wilayah berfungsi lindung
#   atau budi daya; PP 21/2021 mendefinisikan Zona sebagai "KAWASAN dengan
#   fungsi dan karakteristik tertentu" — jadi zona adalah SEJENIS kawasan,
#   bukan induknya. Karena itu KAWASAN berada di atas, bukan di bawah zona.

# Mode validasi containment per tingkat:
#   "ketat"   — geometri anak harus berada di dalam induk
#   "longgar" — boleh menyembul (persil kadaster & titik sering tak presisi)
#   "sumbu_z" — BUKAN containment: lantai diuji IoU terhadap gedung, sebab
#               modelnya 2,5D dan basement lazim melebihi footprint gedung
#   "akar"    — tak punya induk

LEVEL_SPASIAL = (
    # ordinal, kode_baku, label ikn_akrab,        label rdtr_baku,          containment
    (10,  "WILAYAH",  "Wilayah",                "Wilayah / KSN",          "akar"),
    (20,  "KAWASAN",  "Kawasan",                "Kawasan",                "ketat"),
    (30,  "WP",       "Zona (WP)",              "Wilayah Perencanaan",    "ketat"),
    (40,  "SWP",      "Distrik (Sub-WP)",       "Sub Wilayah Perencanaan", "ketat"),
    (50,  "BLOK",     "Blok",                   "Blok",                   "ketat"),
    (55,  "SUBBLOK",  "Sub-Blok",               "Sub-Blok",               "ketat"),
    (60,  "PERSIL",   "Persil / Bidang Tanah",  "Persil (NIB)",           "longgar"),
    (70,  "TAPAK",    "Kompleks / Tapak",       "Tapak",                  "ketat"),
    (80,  "GEDUNG",   "Gedung",                 "Gedung",                 "ketat"),
    (90,  "LANTAI",   "Lantai",                 "Lantai",                 "sumbu_z"),
    (95,  "SAYAP",    "Sayap / Zona Lantai",    "Seksi",                  "ketat"),
    (100, "RUANGAN",  "Ruangan",                "Ruangan",                "ketat"),
    (110, "TITIK",    "Titik / Sub-ruang",      "Fitur",                  "longgar"),
)

PRESET_PENAMAAN = ("ikn_akrab", "rdtr_baku")

# RUANGAN satu-satunya tingkat WAJIB: dialah jangkar KIR & DBR (PMK 181/2016).
# Tanpa ruangan, seluruh fitur spasial tak menyambung ke penatausahaan BMN.
KODE_LEVEL_WAJIB = "RUANGAN"

_PETA_LEVEL = {b[1]: b for b in LEVEL_SPASIAL}


def daftar_level(preset: str = "ikn_akrab") -> list:
    """Registry level terurut dari TERBESAR ke TERKECIL, berlabel sesuai preset."""
    pakai_baku = preset == "rdtr_baku"
    return [
        {"ordinal": ordinal, "kode_baku": kode,
         "label": label_baku if pakai_baku else label_akrab,
         "containment": containment, "wajib": kode == KODE_LEVEL_WAJIB}
        for (ordinal, kode, label_akrab, label_baku, containment) in LEVEL_SPASIAL
    ]


def level_dari_kode(kode_baku: str) -> dict:
    """Satu baris registry, atau None bila kode tak dikenal."""
    b = _PETA_LEVEL.get(str(kode_baku or "").strip().upper())
    if not b:
        return None
    return {"ordinal": b[0], "kode_baku": b[1], "label": b[2],
            "label_baku": b[3], "containment": b[4],
            "wajib": b[1] == KODE_LEVEL_WAJIB}


def ordinal_level(kode_baku: str):
    b = _PETA_LEVEL.get(str(kode_baku or "").strip().upper())
    return b[0] if b else None


def parent_level_sah(kode_induk: str, kode_anak: str) -> bool:
    """Induk WAJIB berada di tingkat yang lebih LUAS (ordinal lebih kecil).

    Tingkat boleh DILOMPATI — satker daerah lazim hanya memakai
    Tapak → Gedung → Lantai → Ruangan tanpa Blok/Persil, dan memaksa node
    kosong palsu hanya untuk memenuhi rantai justru merusak data.
    """
    oi, oa = ordinal_level(kode_induk), ordinal_level(kode_anak)
    if oi is None or oa is None:
        return False
    return oi < oa


# ── Pohon: ancestors[] & jalur ──────────────────────────────────────────────
#
# `parent_id` adalah SATU-SATUNYA field pohon yang boleh diedit pengguna;
# `ancestors[]` dan `jalur` SELALU diturunkan ulang dari rantai parent oleh
# helper di bawah. Menyimpan tiga-tiganya sebagai sumber kebenaran terpisah
# adalah resep data pohon yang saling bertentangan.

PEMISAH_JALUR = ","


def rantai_induk(node_id: str, peta_parent: dict, batas: int = 64) -> list:
    """Daftar id leluhur dari yang TERJAUH ke induk langsung.

    `peta_parent` = {id_anak: id_induk}. Berhenti pada siklus atau kedalaman
    berlebih dan mengembalikan apa yang sudah terkumpul — data pohon rusak
    tidak boleh membuat permintaan menggantung selamanya.
    """
    naik, kini, terlihat = [], peta_parent.get(node_id), {node_id}
    while kini and kini not in terlihat and len(naik) < batas:
        naik.append(kini)
        terlihat.add(kini)
        kini = peta_parent.get(kini)
    naik.reverse()          # terjauh -> terdekat
    return naik


def bangun_jalur(ancestors: list, node_id: str) -> str:
    """Materialized path ",A,B,C," — dibungkus pemisah di KEDUA ujung.

    Pembungkus itu yang membuat pencarian sub-pohon aman: prefix ",A," tak
    akan salah cocok dengan node lain bernama "A2" (yang jalurnya ",A2,").
    """
    bagian = [*(ancestors or []), node_id]
    return PEMISAH_JALUR + PEMISAH_JALUR.join(str(b) for b in bagian) + PEMISAH_JALUR


def turunkan_pohon(node_id: str, parent_id, peta_parent: dict) -> dict:
    """Field pohon turunan untuk satu node: {ancestors, jalur, kedalaman}."""
    peta = dict(peta_parent or {})
    if parent_id:
        peta[node_id] = parent_id
    else:
        peta.pop(node_id, None)
    anc = rantai_induk(node_id, peta)
    return {"ancestors": anc, "jalur": bangun_jalur(anc, node_id),
            "kedalaman": len(anc)}


def rewrite_ancestors(ancestors_lama: list, pindah_id: str, pindah_ancestors_baru: list) -> list:
    """Ancestors keturunan setelah salah satu leluhurnya (`pindah_id`) dipindah.

    Saat sebuah node dipindah ke induk lain, SELURUH keturunannya ikut berpindah
    dan `ancestors`/`jalur` mereka basi. Bagian rantai leluhur dari `pindah_id`
    ke bawah tetap sama; yang berubah hanya bagian DI ATAS `pindah_id`, yang kini
    digantikan oleh rantai leluhur baru si node yang dipindah.

    Mengembalikan `ancestors_lama` apa adanya bila `pindah_id` tak ada di dalamnya
    (keturunan itu tak terpengaruh) — pemanggil memfilter lewat prefix jalur, jadi
    ini hanya jaring pengaman.
    """
    if pindah_id not in ancestors_lama:
        return list(ancestors_lama)
    idx = ancestors_lama.index(pindah_id)
    return [*pindah_ancestors_baru, *ancestors_lama[idx:]]


def ada_siklus(node_id: str, calon_parent_id, peta_parent: dict) -> bool:
    """True bila menjadikan `calon_parent_id` induk akan membentuk siklus.

    Kasus nyata: operator menyeret Gedung ke bawah salah satu Ruangan di
    dalamnya sendiri. Tanpa penjagaan ini, seluruh sub-pohon lenyap dari
    breadcrumb dan tiap kueri leluhur berputar sampai batas kedalaman.
    """
    if not calon_parent_id:
        return False
    if calon_parent_id == node_id:
        return True
    return node_id in rantai_induk(calon_parent_id, peta_parent or {})


# ── Ordinal lantai (gaya IMDF) ──────────────────────────────────────────────
#
# `ordinal` INTEGER dipisah dari `label` karena "Lantai 1" di Indonesia ambigu
# (kadang lantai dasar, kadang satu tingkat di atasnya) dan banyak gedung
# MENGHILANGKAN lantai 4 dan 13. Ordinal tetap RAPAT; yang melompat hanya
# labelnya. Mezanin mendapat ordinal SENDIRI, bukan pecahan 0.5 — pecahan
# merusak pengurutan integer dan tak bisa diindeks dengan rapi.
#
#   0  = lantai dengan akses masuk utama
#   <0 = basement (-1 paling dekat permukaan)
#   >0 = naik ke atas sampai rooftop

import re as _re

_POLA_BASEMENT = _re.compile(r"^(?:B|BASEMENT|LB)\s*-?\s*(\d+)$", _re.I)
_POLA_ANGKA = _re.compile(r"^(?:L|LANTAI|LT\.?|FLOOR|F)?\s*(\d+)$", _re.I)
_LABEL_DASAR = {"G", "GF", "LD", "DASAR", "LANTAI DASAR", "GROUND", "LG", "UG", "P"}
_LABEL_ATAP = {"R", "RF", "ROOFTOP", "ATAP", "ROOF", "TOP"}
_LABEL_MEZANIN = {"M", "MZ", "MEZANIN", "MEZZANINE", "SEMI"}


def tebak_ordinal_lantai(label) -> Optional[int]:
    """Tebakan ordinal dari label lantai yang lazim ditulis operator.

    Hanya USULAN untuk mengisi formulir — ordinal final tetap ditentukan
    manusia, sebab hanya dia yang tahu lantai mana yang punya akses masuk
    utama. Mengembalikan None bila tak terbaca (mis. "Mezanin": tingginya
    relatif, tak ada ordinal universal).
    """
    s = str(label or "").strip().upper().replace("_", " ")
    if not s:
        return None
    if s in _LABEL_DASAR:
        return 0
    if s in _LABEL_ATAP or s in _LABEL_MEZANIN:
        return None          # butuh konteks gedung — jangan menebak
    m = _POLA_BASEMENT.match(s)
    if m:
        return -int(m.group(1))
    m = _POLA_ANGKA.match(s)
    if m:
        n = int(m.group(1))
        # Konvensi Indonesia: "Lantai 1" LAZIM berarti lantai dasar.
        return n - 1 if n >= 1 else None
    return None


def ordinal_rapat(ordinals: list) -> list:
    """Rapatkan daftar ordinal agar berurutan tanpa celah, urutan dipertahankan.

    Dipakai setelah sebuah lantai dihapus atau saat mengimpor gedung yang
    melompati lantai 4/13: posisi relatif antar lantai tetap, tetapi tak ada
    lubang di tengah yang membuat "lantai berikutnya" jadi ambigu. Nilai nol
    (akses masuk utama) dipertahankan sebagai titik jangkar.
    """
    if not ordinals:
        return []
    urut = sorted(set(int(o) for o in ordinals))
    jangkar = urut.index(0) if 0 in urut else 0
    return [i - jangkar for i in range(len(urut))]
