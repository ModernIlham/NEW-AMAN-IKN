"""Validasi TOPOLOGI geometri denah — lapisan di atas validasi struktural.

`spasial_utils.validasi_geometri` (Fase 3) memeriksa STRUKTUR: bentuk larik,
rentang angka, cincin tertutup, cincin degenerat. Modul ini (Fase 4) memeriksa
yang tak terlihat dari struktur: poligon menyilang-diri (bow-tie), lubang yang
keluar dari cincin luar, cincin bertumpang-tindih — kasus yang lolos cek
struktural tetapi ditolak MongoDB saat indeks 2dsphere dibangun, dengan pesan
yang tak terbaca operator.

KENAPA MODUL TERPISAH + LAZY IMPORT. shapely adalah dependensi biner (libgeos).
Ia ada di requirements.txt sehingga CI & VPS memilikinya, tetapi server TIDAK
boleh mati hanya karena lingkungan darurat/dev kekurangan libgeos — tanpa
shapely seluruh fungsi di sini melewatkan pemeriksaan (mengembalikan None) dan
MongoDB kembali menjadi jaring terakhir, persis perilaku Fase 3.

KEBIJAKAN BLOKIR vs PERINGATAN (keputusan sadar, jangan diubah tanpa alasan):
- Galat TOPOLOGI  -> BLOKIR simpan (HTTP 400). Geometri tak sah merusak
  pembangunan indeks untuk SELURUH koleksi, bukan hanya dokumen itu.
- Pelanggaran CONTAINMENT (anak keluar dari batas induk) -> PERINGATAN saja.
  Poligon digambar orang berbeda pada waktu berbeda; seluruh desain deteksi
  Fase 3 (`pilih_rantai`) sudah menerima containment yang tak sempurna. Memblokir
  di sini berarti operator tak bisa menyimpan gedung yang benar hanya karena
  batas kawasan digambar kasar — urutan perbaikan yang terbalik.
"""
from typing import Optional

# Mode containment dari registry level (spasial_utils.LEVEL_SPASIAL kolom ke-5).
MODE_TANPA_CEK = {"sumbu_z", "akar", "", None}

# Toleransi containment "ketat": ±0,5 m dalam derajat (1° lintang ≈ 111,32 km).
# Verteks anak yang MENEMPEL di garis induk (digambar dengan snap) tidak boleh
# dianggap "keluar" hanya karena selisih pembulatan float.
TOLERANSI_KETAT_DERAJAT = 0.5 / 111_320.0

# Plafon verteks untuk operasi shapely. Goresan tangan berisi puluhan titik;
# denah gedung terperinci ratusan. Di atas plafon ini operasi GEOS pada VPS
# kecil makan CPU berarti — dan endpoint pratinjau dapat dipanggil bebas oleh
# user terautentikasi. Fase impor (SHP/KML) memproses file besar lewat job latar
# dengan plafonnya sendiri, bukan lewat jalur request-response ini.
#
# Angka 100.000 SENGAJA diturunkan ke 20.000 setelah pengukuran: `make_valid`
# pada poligon menyilang-diri berskala SUPER-LINEAR — bintang 201 verteks saja
# sudah > 60 detik. Plafon tinggi memberi rasa aman palsu; yang menahan beban
# sesungguhnya adalah kombinasi plafon ketat + rate-limit + offload ke thread.
MAKS_TITIK_TOPOLOGI = 20_000


def jumlah_titik(geom_dict) -> int:
    """Cacah verteks sebuah geometri GeoJSON (0 bila bentuknya bukan dict)."""
    if not isinstance(geom_dict, dict):
        return 0
    tipe = geom_dict.get("type")
    koor = geom_dict.get("coordinates")
    if not isinstance(koor, (list, tuple)):
        return 0
    if tipe == "Point":
        return 1
    poligon = [koor] if tipe == "Polygon" else koor
    total = 0
    try:
        for pol in poligon:
            for cincin in pol or []:
                total += len(cincin or [])
    except TypeError:
        return 0
    return total


def _shapely():
    """Modul shapely, atau None bila tak terpasang (degradasi anggun)."""
    try:
        import shapely
        import shapely.geometry    # noqa: F401 — pastikan submodul ikut termuat
        import shapely.validation  # noqa: F401
        return shapely
    except Exception:                          # ImportError / libgeos rusak
        return None


def topologi_aktif() -> bool:
    """True bila pemeriksaan topologi benar-benar berjalan di proses ini."""
    return _shapely() is not None


def _bentuk(geom_dict):
    """GeoJSON dict -> objek shapely, atau None bila gagal dibangun."""
    sh = _shapely()
    if sh is None or not isinstance(geom_dict, dict):
        return None
    try:
        from shapely.geometry import shape
        return shape(geom_dict)
    except Exception:
        return None


# explain_validity() berbahasa Inggris teknis; operator lapangan butuh bahasa
# manusia. Pemetaan per-awalan — sisa pesan asli dilampirkan untuk debugging.
_TERJEMAHAN = (
    ("Self-intersection", "poligon menyilang dirinya sendiri (bow-tie) — geser "
                          "verteks yang bersilangan"),
    ("Ring Self-intersection", "cincin menyilang dirinya sendiri — geser verteks "
                               "yang bersilangan"),
    ("Hole lies outside shell", "lubang berada di LUAR cincin luar"),
    ("Holes are nested", "lubang berada di dalam lubang lain"),
    ("Interior is disconnected", "lubang-lubang memutus poligon jadi beberapa "
                                 "bagian yang tak tersambung"),
    ("Nested shells", "satu bagian poligon berada di dalam bagian lain"),
    ("Duplicate Rings", "ada cincin kembar (digambar dua kali)"),
    ("Too few points", "cincin kekurangan titik"),
    ("Ring is not closed", "cincin tidak tertutup"),
)


def _pesan_topologi(pesan_asli: str) -> str:
    for awalan, indo in _TERJEMAHAN:
        if pesan_asli.startswith(awalan):
            return f"{indo} [{pesan_asli}]"
    return f"geometri tidak sah secara topologi [{pesan_asli}]"


def validasi_topologi(geom_dict) -> Optional[str]:
    """None bila topologi sah (atau shapely absen); selain itu PESAN galat.

    Dipanggil SETELAH `spasial_utils.validasi_geometri` lolos — masukan di sini
    sudah pasti berstruktur benar, jadi kegagalan membangun objek shapely
    diperlakukan sebagai galat (bukan dilewatkan diam-diam).
    """
    sh = _shapely()
    if sh is None:
        return None                            # degradasi anggun — MongoDB jaring terakhir
    if jumlah_titik(geom_dict) > MAKS_TITIK_TOPOLOGI:
        return (f"geometri terlalu besar (> {MAKS_TITIK_TOPOLOGI:,} titik) — "
                "sederhanakan bentuknya atau pakai jalur impor file")
    bentuk = _bentuk(geom_dict)
    if bentuk is None:
        return "geometri tidak dapat dibaca sebagai bentuk"
    if bentuk.is_valid:
        return None
    try:
        from shapely.validation import explain_validity
        return _pesan_topologi(str(explain_validity(bentuk)))
    except Exception:
        return "geometri tidak sah secara topologi"


def perbaiki_topologi(geom_dict):
    """Usaha perbaikan otomatis (`make_valid`) -> GeoJSON dict, atau None.

    HANYA untuk PRATINJAU di editor ("coba perbaiki otomatis") — hasil
    make_valid bisa memecah poligon atau menggeser bentuk, jadi keputusan
    memakainya harus di tangan operator, bukan diam-diam saat menyimpan.
    Hasil non-poligon (mis. GeometryCollection berisi garis sisa) dibuang;
    hanya Polygon/MultiPolygon yang dikembalikan.
    """
    sh = _shapely()
    if sh is None:
        return None
    # Plafon SAMA seperti validasi_topologi. `make_valid` GEOS pada poligon
    # menyilang-diri berskala super-linear — beberapa ratus verteks patologis
    # sudah bisa membeku berpuluh detik — jadi cek ini WAJIB ada di sini juga,
    # bukan hanya di validasi_topologi. Tanpa ini endpoint pratinjau meneruskan
    # geometri raksasa langsung ke make_valid (temuan tinjauan: DoS terautentikasi).
    if jumlah_titik(geom_dict) > MAKS_TITIK_TOPOLOGI:
        return None
    bentuk = _bentuk(geom_dict)
    if bentuk is None:
        return None
    try:
        from shapely import make_valid
        from shapely.geometry import mapping, MultiPolygon
        hasil = make_valid(bentuk)
        if hasil.geom_type == "GeometryCollection":
            poligon = [g for g in hasil.geoms
                       if g.geom_type in ("Polygon", "MultiPolygon")]
            if not poligon:
                return None
            if len(poligon) == 1:
                hasil = poligon[0]
            else:
                datar = []
                for p in poligon:
                    datar.extend(p.geoms if p.geom_type == "MultiPolygon" else [p])
                hasil = MultiPolygon(datar)
        if hasil.is_empty or hasil.geom_type not in ("Polygon", "MultiPolygon"):
            return None
        return dict(mapping(hasil))
    except Exception:
        return None


def validasi_containment(geom_anak, geom_induk, mode) -> Optional[str]:
    """None bila anak berada di dalam induk sesuai `mode`; selain itu PESAN.

    mode (dari registry level milik ANAK):
      "ketat"   -> anak wajib TERCAKUP induk (toleransi ±0,5 m untuk verteks
                   yang menempel di garis batas)
      "longgar" -> cukup BERSINGGUNGAN (persil/titik lazim menyeberang batas
                   administratif)
      "sumbu_z"/"akar"/kosong -> tidak diperiksa (lantai menumpuk di jejak yang
                   sama; akar tak punya induk)

    Induk TANPA geometri -> None: belum digambar bukan pelanggaran. Ingat
    kebijakan modul: hasil fungsi ini adalah PERINGATAN, bukan pemblokir.
    """
    if mode in MODE_TANPA_CEK:
        return None
    sh = _shapely()
    if sh is None:
        return None
    if not isinstance(geom_induk, dict) or not geom_induk:
        return None                            # induk belum digambar
    anak = _bentuk(geom_anak)
    induk = _bentuk(geom_induk)
    if anak is None or induk is None:
        return None                            # biarkan validasi lain yang bicara
    try:
        if mode == "longgar":
            if anak.intersects(induk):
                return None
            return ("bentuk ini sama sekali tidak bersinggungan dengan batas "
                    "induknya — periksa apakah induknya benar")
        # "ketat" (bawaan untuk mode lain yang tak dikenal — lebih aman ketat)
        if induk.buffer(TOLERANSI_KETAT_DERAJAT).covers(anak):
            return None
        luar = anak.difference(induk)
        persen = (100.0 * luar.area / anak.area) if anak.area > 0 else 100.0
        return (f"±{persen:.0f}% bentuk ini berada di LUAR batas induknya — "
                "boleh disimpan, tapi periksa salah satu batasnya")
    except Exception:
        return None                            # cek gagal ≠ bentuk salah
