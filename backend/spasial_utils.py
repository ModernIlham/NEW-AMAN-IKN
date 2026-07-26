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


def susun_ulang_keturunan(anc_lama: list, anc_nama_lama: list, node_id: str,
                          anc_baru: list, anc_nama_baru: list, nama_node: str,
                          id_keturunan: str) -> dict:
    """Field pohon turunan sebuah KETURUNAN setelah leluhurnya `node_id` dipindah
    dan/atau diganti nama.

    `anc_baru`/`anc_nama_baru` = rantai leluhur BARU si node yang dipindah, TANPA
    node itu sendiri (keduanya sejajar posisi). `nama_node` = namanya (bisa baru).

    Mengembalikan {ancestors, ancestors_nama, jalur, kedalaman} yang SELALU
    sejajar posisi. Menyimpan node_id TEPAT SEKALI: bug sebelumnya menggandakan
    node_id karena memasukkannya ke `anc_baru` padahal rewrite_ancestors sudah
    mempertahankannya lewat ekor `ancestors_lama[idx:]`.
    """
    anc = rewrite_ancestors(anc_lama, node_id, anc_baru)
    if node_id in anc_lama:
        idx = anc_lama.index(node_id)
        anc_nama = [*anc_nama_baru, nama_node, *(anc_nama_lama or [])[idx + 1:]]
    else:
        anc_nama = list(anc_nama_lama or [])
    return {"ancestors": anc, "ancestors_nama": anc_nama,
            "jalur": bangun_jalur(anc, id_keturunan), "kedalaman": len(anc)}


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


# ═══════════════════════════════════════════════════════════════════════════
# GEOMETRI (Fase 3) — validasi GeoJSON, bbox, luas kasar, deteksi lokasi
# ═══════════════════════════════════════════════════════════════════════════
#
# Point-in-polygon jalur PANAS dikerjakan MongoDB (indeks 2dsphere, server-side).
# Helper di sini untuk: (a) memvalidasi geometri SEBELUM disimpan agar tak
# meracuni indeks, (b) menurunkan bbox/titik wakil/luas, (c) ray casting murni
# untuk klien offline & uji unit tanpa Mongo.

TIPE_GEOMETRI_SAH = ("Polygon", "MultiPolygon", "Point")

# Jari-jari bumi rata-rata (IUGG mean radius) — untuk luas & jarak kasar.
RADIUS_BUMI_M = 6371008.8


def _cincin_sah(cincin) -> Optional[str]:
    """None bila cincin poligon sah; selain itu PESAN galat berbahasa manusia."""
    if not isinstance(cincin, (list, tuple)) or len(cincin) < 4:
        return "cincin poligon butuh minimal 4 titik (titik akhir mengulang titik awal)"
    for t in cincin:
        if isinstance(t, (str, bytes, dict)) or not isinstance(t, (list, tuple)) or len(t) < 2:
            return "setiap titik harus berupa pasangan [bujur, lintang]"
        lon, lat = t[0], t[1]
        # bool adalah subclass int di Python — [True, False] BUKAN koordinat.
        if isinstance(lon, bool) or isinstance(lat, bool):
            return "koordinat harus angka"
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            return "koordinat harus angka"
        if not (math.isfinite(lon) and math.isfinite(lat)):
            return "koordinat tak boleh NaN/tak berhingga"
        if abs(lon) > BATAS_BUJUR or abs(lat) > BATAS_LINTANG:
            return f"koordinat di luar rentang WGS84 ({lon}, {lat})"
    if list(cincin[0][:2]) != list(cincin[-1][:2]):
        return "cincin poligon harus TERTUTUP (titik akhir sama dengan titik awal)"
    # Cincin DEGENERAT (semua titik sama, atau hanya 2 titik berbeda) lolos
    # semua cek di atas tetapi ditolak MongoDB saat indeks 2dsphere dibangun —
    # dengan pesan yang tak terbaca operator, dan satu dokumen rusak bisa
    # menggagalkan pembangunan indeks untuk SELURUH koleksi. Tolak di sini.
    unik = {(t[0], t[1]) for t in cincin}
    if len(unik) < 3:
        return ("cincin poligon degenerat — butuh minimal 3 titik BERBEDA "
                f"(hanya ada {len(unik)})")
    return None


def validasi_geometri(geom) -> Optional[str]:
    """None bila geometri layak diindeks 2dsphere; selain itu PESAN galat.

    Menolak SEBELUM menyentuh MongoDB, karena geometri rusak membuat
    `create_index`/insert gagal dengan pesan yang tak terbaca operator — dan
    satu dokumen rusak dapat menggagalkan pembangunan indeks untuk semuanya.

    CAKUPAN — ini validasi STRUKTURAL, bukan topologis. Yang diperiksa: bentuk
    larik, tipe & rentang angka, cincin tertutup, dan cincin degenerat. Yang
    BELUM diperiksa: poligon menyilang-diri (bow-tie), cincin dalam yang keluar
    dari cincin luar, dan cincin yang saling tumpang tindih. Memeriksanya butuh
    operasi geometri sungguhan (shapely) yang sengaja belum ditarik sebagai
    dependensi di fase ini; ia sudah dijadwalkan untuk validasi topologi pada
    fase menggambar & impor. Sampai saat itu MongoDB tetap menjadi penjaring
    terakhir untuk kasus-kasus itu — hanya saja pesannya kurang ramah.
    """
    if not isinstance(geom, dict):
        return "geometri harus objek GeoJSON"
    tipe = geom.get("type")
    if tipe not in TIPE_GEOMETRI_SAH:
        return f"tipe geometri '{tipe}' tidak didukung (pakai {', '.join(TIPE_GEOMETRI_SAH)})"
    koor = geom.get("coordinates")
    if koor is None:
        return "geometri tanpa 'coordinates'"
    # `coordinates` WAJIB list/tuple sebelum diindeks. Tanpa cek ini, payload
    # seperti {"type":"Point","coordinates":{"lon":1}} melempar KeyError sehingga
    # validator sendiri yang jatuh — pengguna menerima HTTP 500, bukan pesan 400
    # yang menjelaskan salahnya di mana (temuan tinjauan).
    if isinstance(koor, (str, bytes, dict)) or not isinstance(koor, (list, tuple)):
        return "'coordinates' harus berupa larik angka bersarang"
    if tipe == "Point":
        return None if bangun_geo_point(
            koor[1] if len(koor) > 1 else None,
            koor[0] if koor else None) else "titik tidak valid"
    poligon = [koor] if tipe == "Polygon" else koor
    if not poligon:
        return "poligon kosong"
    for i, pol in enumerate(poligon):
        if not pol:
            return f"poligon ke-{i + 1} kosong"
        if isinstance(pol, (str, bytes, dict)) or not isinstance(pol, (list, tuple)):
            return f"poligon ke-{i + 1} harus berupa larik cincin"
        for j, cincin in enumerate(pol):
            galat = _cincin_sah(cincin)
            if galat:
                sebutan = f"poligon ke-{i + 1}" if tipe == "MultiPolygon" else "poligon"
                cincin_ke = "cincin luar" if j == 0 else f"cincin dalam ke-{j}"
                return f"{sebutan} {cincin_ke}: {galat}"
    return None


def _semua_titik(geom) -> list:
    """Seluruh pasangan (lon, lat) dari sebuah geometri, datar."""
    if not isinstance(geom, dict):
        return []
    tipe, koor = geom.get("type"), geom.get("coordinates") or []
    if tipe == "Point":
        return [(koor[0], koor[1])] if len(koor) >= 2 else []
    poligon = [koor] if tipe == "Polygon" else koor
    return [(t[0], t[1]) for pol in poligon for cincin in pol for t in cincin
            if isinstance(t, (list, tuple)) and len(t) >= 2]


def hitung_bbox(geom) -> Optional[list]:
    """[lon_min, lat_min, lon_maks, lat_maks] — dipakai pemuatan peta per-viewport.

    BATASAN SADAR — antimeridian (bujur ±180) TIDAK ditangani. Poligon yang
    melintasi garis itu menghasilkan bbox selebar dunia (dan `titik_wakil`
    mendarat di sisi bumi yang salah, `luas_kasar_m2` ikut kacau). Menanganinya
    dengan benar berarti memecah geometri jadi dua dan mengubah semua turunan —
    biaya besar untuk kasus yang TAK BISA terjadi di sini: seluruh wilayah
    Indonesia berada di 95°BT–141°BT, dan denah ini melayani satker Indonesia.
    Bila suatu hari dipakai lintas-antimeridian (mis. Pasifik), yang harus
    ditinjau adalah fungsi ini, `titik_wakil`, dan `luas_kasar_m2` sekaligus.
    """
    titik = _semua_titik(geom)
    if not titik:
        return None
    lons = [t[0] for t in titik]
    lats = [t[1] for t in titik]
    return [min(lons), min(lats), max(lons), max(lats)]


def titik_wakil(geom) -> Optional[dict]:
    """Titik wakil (pusat bbox) sebagai GeoJSON Point.

    SENGAJA pusat bbox, bukan centroid sejati: untuk label peta & pengurutan
    jarak, pusat bbox sudah memadai dan tak butuh pustaka geometri. Catatan:
    untuk poligon berbentuk L, titik ini bisa jatuh DI LUAR poligon — jadi
    jangan dipakai sebagai "titik di dalam" (gunakan kueri geo untuk itu).
    """
    bb = hitung_bbox(geom)
    if not bb:
        return None
    return {"type": "Point", "coordinates": [(bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0]}


def luas_kasar_m2(geom) -> float:
    """Luas KASAR dalam m² (shoelace pada proyeksi lokal setara-persegi).

    Cukup untuk PERINGKAT ("poligon terkecil = paling spesifik" saat titik jatuh
    di beberapa area bertumpuk) dan tampilan informatif. BUKAN luas geodetik
    resmi — untuk angka yang dipakai dokumen, hitung dengan pustaka geodesi.
    Cincin dalam (lubang) dikurangkan.
    """
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        return 0.0
    koor = geom.get("coordinates") or []
    poligon = [koor] if geom["type"] == "Polygon" else koor
    titik = _semua_titik(geom)
    if not titik:
        return 0.0
    lat0 = sum(t[1] for t in titik) / len(titik)          # lintang acuan
    m_per_deg_lat = math.pi * RADIUS_BUMI_M / 180.0
    m_per_deg_lon = m_per_deg_lat * math.cos(math.radians(lat0))
    total = 0.0
    for pol in poligon:
        for j, cincin in enumerate(pol):
            s = 0.0
            for k in range(len(cincin) - 1):
                x1 = cincin[k][0] * m_per_deg_lon
                y1 = cincin[k][1] * m_per_deg_lat
                x2 = cincin[k + 1][0] * m_per_deg_lon
                y2 = cincin[k + 1][1] * m_per_deg_lat
                s += x1 * y2 - x2 * y1
            luas = abs(s) / 2.0
            total += luas if j == 0 else -luas       # cincin dalam = lubang
    return max(0.0, total)


def titik_di_dalam(lon: float, lat: float, geom) -> bool:
    """Ray casting murni — untuk klien OFFLINE & uji unit tanpa Mongo.

    Server memakai MongoDB `$geoIntersects` (terindeks). Fungsi ini sengaja
    sederhana: cukup untuk poligon berukuran gedung/ruangan pada bidang datar
    lokal; TIDAK menangani poligon yang melintasi antimeridian.
    """
    if not isinstance(geom, dict) or geom.get("type") not in ("Polygon", "MultiPolygon"):
        return False
    koor = geom.get("coordinates") or []
    poligon = [koor] if geom["type"] == "Polygon" else koor
    for pol in poligon:
        if not pol:
            continue
        if not _dalam_cincin(lon, lat, pol[0]):
            continue
        # Di dalam cincin luar — pastikan tidak berada di salah satu lubang.
        if any(_dalam_cincin(lon, lat, lubang) for lubang in pol[1:]):
            continue
        return True
    return False


def _dalam_cincin(lon: float, lat: float, cincin) -> bool:
    dalam = False
    n = len(cincin)
    for i in range(n - 1):
        x1, y1 = cincin[i][0], cincin[i][1]
        x2, y2 = cincin[i + 1][0], cincin[i + 1][1]
        if (y1 > lat) != (y2 > lat):
            x_potong = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_potong:
                dalam = not dalam
    return dalam


# ── Deteksi lokasi dari titik: pemeringkatan & konsistensi rantai ───────────

def peringkat_kandidat(kandidat: list) -> list:
    """Urutkan area yang SAMA-SAMA memuat sebuah titik, paling spesifik dahulu.

    Titik bisa jatuh di beberapa poligon sesama tingkat (batas berimpit, area
    fungsi ganda). Urutan: `prioritas` DESC (kurasi manusia menang) → luas
    TERKECIL (paling spesifik) → nama, agar hasilnya stabil/deterministik.

    Memakai `metrik.luas_m2` yang TERSIMPAN, bukan menghitung dari geometri:
    kueri deteksi sengaja tidak memproyeksikan `geometry` demi SLA.
    """
    def kunci(n):
        luas = ((n.get("metrik") or {}).get("luas_m2"))
        luas = luas if isinstance(luas, (int, float)) and luas > 0 else float("inf")
        # `prioritas` bisa berisi apa saja setelah impor data lama; `int("tinggi")`
        # melempar ValueError dan menjatuhkan SELURUH endpoint deteksi jadi HTTP
        # 500. Nilai tak terbaca diperlakukan sebagai "tanpa prioritas".
        try:
            prio = int(n.get("prioritas") or 0)
        except (TypeError, ValueError):
            prio = 0
        return (-prio, luas, str(n.get("nama") or ""))
    return sorted(kandidat or [], key=kunci)


def pilih_rantai(kandidat: list) -> dict:
    """Susun rantai lokasi yang KONSISTEN dari hasil kueri geo.

    Kenyataan lapangan: poligon digambar orang berbeda pada waktu berbeda,
    sehingga sebuah titik bisa jatuh di dalam Gedung A tetapi TIDAK di dalam
    poligon Kawasan yang seharusnya memuatnya (batas kawasan digambar kasar).
    Bila rantai disusun apa adanya dari hasil geo, breadcrumb jadi bolong dan
    berbeda dari pohon — dua sumber kebenaran yang bertengkar.

    Aturan: **percayai fitur TERDALAM**, lalu isi tingkat di atasnya dari
    `ancestors` miliknya (pohon), bukan dari hasil geo. Hasilnya selalu
    konsisten dengan hierarki yang tersimpan.

    Mengembalikan:
      terdalam    — node terpilih (paling dalam; bila seri, paling spesifik)
      ancestors   — id leluhur menurut POHON (nama dilengkapi oleh pemanggil)
      alternatif  — kandidat lain di tingkat terdalam yang sama (untuk dropdown)
      diabaikan   — id hasil geo yang TIDAK berada di rantai terdalam
      konsisten   — True bila seluruh hasil geo memang sejalur
      catatan     — penanda mesin bila rantai dilengkapi dari pohon
    """
    if not kandidat:
        return {"terdalam": None, "ancestors": [], "alternatif": [],
                "diabaikan": [], "konsisten": True, "catatan": ""}
    ordinal_maks = max(int(n.get("ordinal_level") or 0) for n in kandidat)
    terdalam_set = peringkat_kandidat(
        [n for n in kandidat if int(n.get("ordinal_level") or 0) == ordinal_maks])
    terdalam = terdalam_set[0]
    rantai_id = set(terdalam.get("ancestors") or []) | {terdalam.get("id")}
    # Kandidat SEJAJAR di tingkat terdalam sudah sengaja dikembalikan lewat
    # `alternatif` — mereka BUKAN tanda poligon bertentangan. Dua gedung yang
    # berimpit dinding itu lumrah, dan $geoIntersects memang memuat titik di
    # batas untuk KEDUA poligon. Tanpa pengecualian ini setiap titik di dinding
    # bersama membuat `konsisten` palsu-False dan `catatan` mengaku rantai
    # ditambal dari ancestors padahal tak ada tingkat yang ditambal — node yang
    # sama pun dilaporkan dua kali dengan makna berlawanan (temuan tinjauan).
    id_alternatif = {n.get("id") for n in terdalam_set[1:]}
    diabaikan = [n.get("id") for n in kandidat
                 if n.get("id") not in rantai_id and n.get("id") not in id_alternatif]
    konsisten = not diabaikan
    return {
        "terdalam": terdalam,
        "ancestors": list(terdalam.get("ancestors") or []),
        "alternatif": terdalam_set[1:],
        "diabaikan": diabaikan,
        "konsisten": konsisten,
        "catatan": "" if konsisten else "rantai_dilengkapi_dari_ancestors",
    }


# Ambang akurasi GPS (meter) — di atas ini ruangan TIDAK di-commit otomatis.
# Ruangan kantor lazim berukuran 3-8 m; akurasi 30 m berarti titik bisa berada
# di ruangan mana pun dalam radius itu, jadi menebak justru menyesatkan.
# Ambang "kotak terlalu lebar untuk disaring" — lihat kotak_dari_bbox.
LEBAR_BBOX_MAKS_DERAJAT = 180.0
TINGGI_BBOX_MAKS_DERAJAT = 170.0


def kotak_dari_bbox(bbox: str):
    """Ubah "lon_min,lat_min,lon_maks,lat_maks" menjadi poligon kotak GeoJSON.

    Mengembalikan `(kotak, galat)` dengan TIGA hasil yang bermakna:
      (kotak, None) — saring dengan $geoIntersects memakai kotak ini
      (None, pesan) — bbox tak sah, pemanggil balas HTTP 400
      (None, None)  — bbox SAH tetapi terlalu lebar untuk disaring; pemanggil
                      WAJIB melewatkan $geoIntersects dan mengandalkan LOD +
                      plafon fitur.

    Hasil ketiga itu ada karena JEBAKAN MONGODB: poligon GeoJSON biasa yang
    luasnya melebihi setengah bola ditafsirkan sebagai KOMPLEMEN-nya. Pada zoom
    sangat jauh viewport berpadding bisa mencakup hampir seluruh dunia, dan
    kueri lalu mencari di sisi bumi yang SALAH — denah hilang tanpa satu pun
    pesan galat. Menyaring pada kotak selebar itu memang tak ada gunanya.
    """
    if not bbox:
        return None, None
    try:
        bagian = [float(v) for v in str(bbox).split(",")]
    except (ValueError, TypeError):
        return None, "bbox harus 'lon_min,lat_min,lon_maks,lat_maks'"
    if len(bagian) != 4:
        return None, "bbox harus berisi TEPAT 4 angka: lon_min,lat_min,lon_maks,lat_maks"
    x1, y1, x2, y2 = bagian
    if not all(math.isfinite(v) for v in bagian):
        return None, "bbox mengandung nilai tak berhingga"
    # Terbalik atau pipih menghasilkan cincin berverteks kembar / berputar
    # terbalik; MongoDB menjawabnya dengan OperationFailure (HTTP 500), bukan
    # hasil kosong yang wajar.
    if x2 <= x1 or y2 <= y1:
        return None, "bbox harus lon_min < lon_maks dan lat_min < lat_maks"
    if abs(x1) > BATAS_BUJUR or abs(x2) > BATAS_BUJUR:
        return None, "bujur bbox di luar rentang WGS84"
    if abs(y1) > BATAS_LINTANG or abs(y2) > BATAS_LINTANG:
        return None, "lintang bbox di luar rentang WGS84"
    if (x2 - x1) >= LEBAR_BBOX_MAKS_DERAJAT or (y2 - y1) >= TINGGI_BBOX_MAKS_DERAJAT:
        return None, None                      # sah, tapi jangan disaring
    kotak = {"type": "Polygon", "coordinates": [[
        [x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]]]}
    galat = validasi_geometri(kotak)
    return (None, f"bbox tidak valid: {galat}") if galat else (kotak, None)


AMBANG_AKURASI_RUANGAN_M = 30.0


def boleh_auto_ruangan(akurasi_m) -> bool:
    """True bila akurasi GPS cukup baik untuk menetapkan RUANGAN otomatis.

    TIGA keadaan yang WAJIB dibedakan — menggabungkannya pernah MEMBALIK gerbang
    ini (temuan tinjauan adversarial):

      1. Tak dilaporkan (None / "")            -> CUKUP. Banyak sumber tak
         melaporkan akurasi, dan titik yang ditancapkan manual di peta justru
         yang paling akurat; menolak semuanya membuat fitur ini tak terpakai.
      2. Dilaporkan & masuk akal               -> bandingkan dengan ambang.
      3. Dilaporkan tapi TAK masuk akal
         (negatif, NaN, inf, bukan angka)      -> TOLAK. Nilai rusak bukan
         alasan untuk menebak ruangan.

    JANGAN memakai `parse_koordinat` dengan batas berhingga di sini. Semantik
    fungsi itu "rentang koordinat": nilai di LUAR batas keluar sebagai None —
    yang di sini berarti "tak dilaporkan = cukup". Peramban yang jatuh ke
    penentuan posisi berbasis IP/menara melaporkan akurasi ratusan KILOMETER,
    jadi justru nilai TERBURUK yang lolos. Batas 100 km sebelumnya membuat
    150000 m (radius 150 km) dianggap layak meng-commit ruangan 3-8 m.
    """
    if akurasi_m is None or str(akurasi_m).strip() == "":
        return True
    a = parse_koordinat(akurasi_m, math.inf)   # inf = tanpa batas rentang
    if a is None or a < 0:
        return False
    return a <= AMBANG_AKURASI_RUANGAN_M


# ── Overlay gambar denah dalam-gedung (Fase 7) ──────────────────────────────
# Gambar denah lantai (ekspor CAD/PDF → PNG/JPG) ditempatkan di atas peta
# lewat TIGA titik sudut: kiri-atas (tl), kanan-atas (tr), kiri-bawah (bl) —
# cukup untuk posisi + rotasi + skala + aspek (transformasi affine), dan
# persis kontrak L.ImageOverlay.Rotated di sisi klien.

SUDUT_OVERLAY = ("tl", "tr", "bl")
OPASITAS_OVERLAY_BAWAAN = 0.7
MAKS_BENTANG_OVERLAY = 0.5          # derajat ≈ 55 km — lebih dari itu pasti salah tempat
MAKS_PIKSEL_OVERLAY = 40_000_000    # 40 MP; bom dekompresi ditolak dari METADATA
FORMAT_OVERLAY = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def validasi_sudut_overlay(sudut) -> Optional[str]:
    """Pesan galat penempatan overlay, atau None bila sah.

    Tiga pagar: (1) tiap sudut [bujur, lintang] dalam rentang dunia;
    (2) tak degenerat — luas jajar genjang tl→tr × tl→bl > ~(10 cm)²,
    sudut yang bertumpuk membuat transformasi CSS klien meledak jadi NaN;
    (3) bentang ≤ MAKS_BENTANG_OVERLAY — overlay selebar provinsi adalah
    salah ketik koordinat, bukan niat."""
    if not isinstance(sudut, dict):
        return "sudut harus objek {tl, tr, bl}"
    titik = {}
    for k in SUDUT_OVERLAY:
        p = sudut.get(k)
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            return f"sudut '{k}' harus [bujur, lintang]"
        lon, lat = parse_bujur(p[0]), parse_lintang(p[1])
        if lon is None or lat is None:
            return f"sudut '{k}' di luar rentang koordinat dunia"
        titik[k] = (lon, lat)
    (x0, y0), (x1, y1), (x2, y2) = titik["tl"], titik["tr"], titik["bl"]
    luas2 = abs((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0))
    if luas2 < 1e-12:
        return "ketiga sudut bertumpuk/segaris — geser hingga membentuk bidang"
    lons = [x0, x1, x2]
    lats = [y0, y1, y2]
    if max(lons) - min(lons) > MAKS_BENTANG_OVERLAY \
            or max(lats) - min(lats) > MAKS_BENTANG_OVERLAY:
        return (f"bentang overlay melebihi {MAKS_BENTANG_OVERLAY}° (~55 km) — "
                "periksa koordinat sudut")
    return None


def rapikan_sudut_overlay(sudut) -> dict:
    """Salinan bersih {tl,tr,bl} ber-float murni (buang elevasi/kunci asing).

    WAJIB memakai parser yang SAMA dengan validasi_sudut_overlay: string
    desimal-koma "116,70" (format Excel/lapangan Indonesia) LOLOS validasi
    (parse_koordinat menormalkan koma→titik) tetapi float() mentah melempar —
    validator dan pembersih yang tak sepakat = 500 pada input yang justru
    diiklankan didukung (temuan tinjauan)."""
    hasil = {}
    for k in SUDUT_OVERLAY:
        lon, lat = parse_bujur(sudut[k][0]), parse_lintang(sudut[k][1])
        if lon is None or lat is None:      # defensif — validator harusnya menahan
            raise ValueError(f"sudut '{k}' di luar rentang koordinat dunia")
        hasil[k] = [lon, lat]
    return hasil


def opasitas_overlay_sah(nilai) -> float:
    """Jepit opasitas ke [0.05, 1]; nilai rusak jatuh ke bawaan (ini setelan
    tampilan dari slider UI — dijepit, bukan ditolak)."""
    try:
        v = float(nilai)
    except (TypeError, ValueError):
        return OPASITAS_OVERLAY_BAWAAN
    if v != v:                                   # NaN
        return OPASITAS_OVERLAY_BAWAAN
    return max(0.05, min(1.0, v))


def sudut_overlay_bawaan(bbox) -> Optional[dict]:
    """Penempatan awal dari bbox [barat, selatan, timur, utara] — gambar
    memenuhi kotak itu, utara di atas. None bila bbox tak layak.

    Bentang dijepit ke bawah plafon MAKS_BENTANG_OVERLAY (dipotong simetris
    dari pusat): bbox kawasan raksasa tak boleh menghasilkan penempatan awal
    yang API-nya sendiri akan TOLAK saat operator menggeser lalu menyimpan
    (temuan tinjauan — keadaan tersimpan harus selalu sah menurut validator)."""
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
        return None
    try:
        b, s, t, u = (float(bbox[0]), float(bbox[1]),
                      float(bbox[2]), float(bbox[3]))
    except (TypeError, ValueError):
        return None
    if not (b < t and s < u) or not all(map(math.isfinite, (b, s, t, u))):
        return None
    plafon = MAKS_BENTANG_OVERLAY * 0.9        # sisakan ruang geser operator
    if t - b > plafon:
        tengah = (b + t) / 2
        b, t = tengah - plafon / 2, tengah + plafon / 2
    if u - s > plafon:
        tengah = (s + u) / 2
        s, u = tengah - plafon / 2, tengah + plafon / 2
    return {"tl": [b, u], "tr": [t, u], "bl": [b, s]}


def periksa_gambar_overlay(data: bytes):
    """(format, lebar, tinggi) atau ValueError berpesan-operator.

    HANYA header yang dibaca — piksel tidak pernah didekode di server (byte
    asli disimpan apa adanya, peramban yang mendekode), sehingga bom
    dekompresi tertolak murah dari metadata IHDR. SVG sengaja tak masuk
    daftar: SVG bisa membawa skrip dan PIL memang tak membukanya.
    """
    import io as _io
    from PIL import Image                       # lazy — jaga impor modul ringan
    try:
        img = Image.open(_io.BytesIO(data or b""))
        fmt = (img.format or "").upper()
        lebar, tinggi = img.size
    except Exception:
        raise ValueError("File bukan gambar yang dikenali — pakai PNG/JPG/WebP")
    if fmt not in FORMAT_OVERLAY:
        raise ValueError(f"Format {fmt or 'tak dikenal'} tidak didukung — "
                         "pakai PNG/JPG/WebP")
    if lebar * tinggi > MAKS_PIKSEL_OVERLAY:
        raise ValueError(f"Gambar {lebar}×{tinggi} piksel terlalu besar "
                         f"(> {MAKS_PIKSEL_OVERLAY // 1_000_000} MP) — "
                         "perkecil resolusinya")
    # verify() menyusuri chunk + CRC TANPA mendekode piksel (aman dari bom,
    # murah) — tanpa ini file terpotong/rusak berheader sah LOLOS, tersimpan,
    # lalu gagal render DIAM-DIAM di peramban; saat mengganti overlay, blob
    # lama yang berfungsi ikut terhapus demi file rusak (temuan tinjauan).
    # Urutan disengaja: plafon piksel dicek DULU sebelum menyusuri chunk.
    try:
        img.verify()
    except Exception:
        raise ValueError("File gambar rusak/terpotong — ekspor ulang lalu "
                         "unggah kembali")
    return fmt, lebar, tinggi
