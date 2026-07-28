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
import multiprocessing
from typing import Optional

# Mode containment dari registry level (spasial_utils.LEVEL_SPASIAL kolom ke-5).
MODE_TANPA_CEK = {"sumbu_z", "akar", "", None}

# Toleransi containment "ketat": ±0,5 m dalam derajat (1° lintang ≈ 111,32 km).
# Verteks anak yang MENEMPEL di garis induk (digambar dengan snap) tidak boleh
# dianggap "keluar" hanya karena selisih pembulatan float.
TOLERANSI_KETAT_DERAJAT = 0.5 / 111_320.0

# ── Pagar biaya GEOS ────────────────────────────────────────────────────────
#
# SEJARAH DAN KOREKSI. Dulu ada SATU plafon verteks (20.000) yang dipakai
# `validasi_topologi` maupun `perbaiki_topologi`. Pengukuran ulang di repo ini
# menunjukkan angka itu memagari hal yang salah — biaya GEOS nyaris tak
# ditentukan oleh JUMLAH verteks, melainkan oleh JUMLAH PERSILANGAN-DIRI:
#
#   bentuk                          is_valid      make_valid
#   poligon sah   200.000 verteks     1,3 ms          3,2 ms
#   poligon sah   500.000 verteks     3,9 ms         10,8 ms
#   bintang patologis  201 verteks     ~1 ms       1.650 ms
#   bintang patologis  501 verteks        —      > 20 detik (dibunuh)
#   bintang patologis 20.001 verteks    126 ms          —
#   bintang patologis 100.001 verteks 7.644 ms          —
#
# Dua akibatnya, dua-duanya nyata:
#
# 1. Plafon 20.000 MENOLAK data sah yang murah. Poligon batas wilayah 500.000
#    verteks divalidasi dalam 3,9 ms, tetapi ditolak mentah-mentah — inilah
#    sebab nyata laporan lapangan "impor 6 poligon, 1 jadi, 5 dilewati dengan
#    alasan 'geometri terlalu besar'".
# 2. Plafon 20.000 TIDAK memagari `make_valid` sama sekali. Bintang 501 verteks
#    — jauh di bawah plafon — berjalan tanpa batas. Jadi plafon itu memberi
#    rasa aman palsu justru pada operasi yang paling berbahaya.
#
# Karena itu plafon verteks diturunkan perannya menjadi sekadar batas kewarasan
# MEMORI, dan yang benar-benar memagari BIAYA adalah TENGGAT WAKTU nyata.
MAKS_TITIK_VALIDASI = 500_000
MAKS_TITIK_PERBAIKAN = 500_000

# Di bawah ambang ini, kerjakan langsung (inline): biayanya sudah terukur kecil
# bahkan untuk bentuk terburuk, sehingga ongkos fork tak sepadan.
#   validasi  : bintang 20.001 verteks = 126 ms  -> aman inline
#   perbaikan : bintang    201 verteks = 1,65 dtk -> ini SUDAH batasnya
AMBANG_TENGGAT_VALIDASI = 20_000
AMBANG_TENGGAT_PERBAIKAN = 200

BATAS_DETIK_VALIDASI = 10.0
BATAS_DETIK_PERBAIKAN = 25.0

# Bila proses terpisah tak bisa dipakai (platform tanpa fork, atau kita sudah
# berada di dalam proses daemon), kita kembali ke satu-satunya pagar yang
# tersisa: plafon verteks konservatif — persis perilaku lama.
MAKS_TITIK_TANPA_TENGGAT = 20_000

# Awalan pesan yang berarti "kami MENOLAK memeriksa/memperbaiki", bukan
# "bentuknya salah". Pemanggil memakai `perlu_disederhanakan()` untuk
# membedakan keduanya: pada kasus ini mencoba `make_valid` pasti sia-sia, dan
# menambahkan "(perbaikan otomatis gagal)" hanya menyesatkan operator.
AWALAN_TERLALU_BESAR = "geometri terlalu besar"
AWALAN_TERLALU_RUMIT = "bentuk terlalu rumit"

SARAN_SEDERHANAKAN = (
    "sederhanakan dulu di aplikasi GIS Anda "
    "(QGIS: Vector ▸ Geometry Tools ▸ Simplify) lalu ekspor ulang")


def perlu_disederhanakan(pesan: Optional[str]) -> bool:
    """True bila pesan galat berarti "terlalu besar/rumit untuk DIPERIKSA".

    Bedakan dari "bentuknya memang salah": untuk yang ini `perbaiki_topologi`
    dijamin menolak juga (pagarnya sama), jadi pemanggil harus BERHENTI di sini
    dan menyuruh operator menyederhanakan bentuknya — bukan menawarkan
    perbaikan otomatis yang tak akan pernah jalan.
    """
    if not pesan:
        return False
    return pesan.startswith(AWALAN_TERLALU_BESAR) or \
        pesan.startswith(AWALAN_TERLALU_RUMIT)


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


# ── Tenggat waktu keras untuk kerja GEOS ────────────────────────────────────

SELESAI, TENGGAT, TANPA_PROSES = "selesai", "tenggat", "tanpa_proses"


def _anak_hitung(kerja, geom_dict, pengirim):
    """Badan proses anak: hitung, kirim hasilnya, tutup. Tak menyentuh apa pun
    milik induk (soket DB, event loop) — hanya CPU dan pipa ini."""
    try:
        pengirim.send((True, kerja(geom_dict)))
    except BaseException:                      # apa pun -> anggap gagal
        try:
            pengirim.send((False, None))
        except BaseException:
            pass
    finally:
        try:
            pengirim.close()
        except BaseException:
            pass


def _jalankan_bertenggat(kerja, geom_dict, batas_detik):
    """(status, hasil) — jalankan `kerja(geom_dict)` dengan tenggat KERAS.

    KENAPA PROSES, BUKAN THREAD ATAU SINYAL. Dua fakta terukur di repo ini:

    - GEOS MELEPAS GIL. Selama `make_valid` berjalan 1.614 ms, thread Python
      lain tetap berdetak dengan jeda terpanjang 11 ms. Jadi `asyncio.to_thread`
      memang menyelamatkan event loop — tetapi hanya itu; kerjanya sendiri
      tetap berjalan dan tetap membakar satu inti CPU tanpa batas.
    - SIGALRM TIDAK MENOLONG. Penangan sinyal Python hanya jalan di thread utama
      di antara instruksi bytecode; selama eksekusi berada di dalam panggilan C
      milik GEOS, penangan itu tak pernah dapat giliran. Percobaan pertama
      memakai `signal.setitimer` gagal total: alarmnya tak pernah menyala dan
      benchmark-nya sendiri yang harus dibunuh dari luar.

    Yang tersisa hanyalah membunuh PROSES. Karena itu fungsi ini ada.
    """
    try:
        ctx = multiprocessing.get_context("fork")
    except (ValueError, RuntimeError):          # platform tanpa fork
        return TANPA_PROSES, None
    try:
        penerima, pengirim = ctx.Pipe(duplex=False)
    except OSError:                             # kehabisan fd
        return TANPA_PROSES, None
    proses = ctx.Process(target=_anak_hitung,
                         args=(kerja, geom_dict, pengirim), daemon=True)
    try:
        proses.start()
    except BaseException:        # fork ditolak, atau induk sendiri daemon
        penerima.close()
        pengirim.close()
        return TANPA_PROSES, None
    # Tutup ujung kirim milik INDUK: tanpa ini `poll()` tak pernah melihat EOF
    # ketika anak mati mendadak, dan kita menunggu sia-sia sampai tenggat.
    pengirim.close()
    try:
        if not penerima.poll(batas_detik):
            return TENGGAT, None
        berhasil, hasil = penerima.recv()
        return (SELESAI, hasil) if berhasil else (SELESAI, None)
    except (EOFError, OSError, ValueError):     # anak mati sebelum menjawab
        return SELESAI, None
    finally:
        try:
            penerima.close()
        except BaseException:
            pass
        if proses.is_alive():
            proses.kill()
        proses.join(5)


def _kerja_validasi(geom_dict) -> Optional[str]:
    """Inti validasi tanpa pagar apa pun — dipakai inline maupun di proses anak."""
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


def validasi_topologi(geom_dict) -> Optional[str]:
    """None bila topologi sah (atau shapely absen); selain itu PESAN galat.

    Dipanggil SETELAH `spasial_utils.validasi_geometri` lolos — masukan di sini
    sudah pasti berstruktur benar, jadi kegagalan membangun objek shapely
    diperlakukan sebagai galat (bukan dilewatkan diam-diam).

    Geometri besar TIDAK lagi ditolak begitu saja: `is_valid` atas poligon sah
    500.000 verteks hanya 3,9 ms. Yang dijaga adalah bentuk PATOLOGIS (ribuan
    persilangan-diri), dan penjaganya tenggat waktu — bukan cacah verteks.
    """
    sh = _shapely()
    if sh is None:
        return None                            # degradasi anggun — MongoDB jaring terakhir
    n = jumlah_titik(geom_dict)
    if n > MAKS_TITIK_VALIDASI:
        return (f"{AWALAN_TERLALU_BESAR} ({n:,} titik, batas "
                f"{MAKS_TITIK_VALIDASI:,}) — {SARAN_SEDERHANAKAN}")
    if n <= AMBANG_TENGGAT_VALIDASI:
        return _kerja_validasi(geom_dict)      # terukur ≤ 126 ms, tak perlu fork
    status, hasil = _jalankan_bertenggat(
        _kerja_validasi, geom_dict, BATAS_DETIK_VALIDASI)
    if status == SELESAI:
        return hasil
    if status == TANPA_PROSES:
        # Tanpa tenggat, plafon verteks konservatif adalah satu-satunya pagar.
        return (f"{AWALAN_TERLALU_BESAR} ({n:,} titik, batas "
                f"{MAKS_TITIK_TANPA_TENGGAT:,} pada lingkungan ini) — "
                f"{SARAN_SEDERHANAKAN}")
    return (f"{AWALAN_TERLALU_RUMIT} — pemeriksaan {n:,} titik melewati "
            f"{BATAS_DETIK_VALIDASI:.0f} detik. Ini hampir selalu berarti garis "
            f"batasnya menyilang dirinya sendiri sangat banyak kali; "
            f"{SARAN_SEDERHANAKAN}")


def _kerja_perbaikan(geom_dict):
    """Inti `make_valid` tanpa pagar — dipakai inline maupun di proses anak."""
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


def perbaiki_topologi(geom_dict):
    """Usaha perbaikan otomatis (`make_valid`) -> GeoJSON dict, atau None.

    HANYA untuk PRATINJAU di editor ("coba perbaiki otomatis") dan jalur impor
    ber-opsi "perbaiki" — hasil make_valid bisa memecah poligon atau menggeser
    bentuk, jadi keputusan memakainya harus di tangan operator, bukan diam-diam
    saat menyimpan. Hasil non-poligon (mis. GeometryCollection berisi garis
    sisa) dibuang; hanya Polygon/MultiPolygon yang dikembalikan.

    Inilah operasi yang benar-benar berbahaya. `make_valid` atas bintang
    menyilang-diri 501 verteks TIDAK selesai dalam 20 detik, sementara poligon
    sah 500.000 verteks selesai dalam 10,8 ms — maka plafon verteks memang tak
    pernah bisa menjadi pagarnya. Pagarnya adalah tenggat waktu keras.
    """
    sh = _shapely()
    if sh is None:
        return None
    n = jumlah_titik(geom_dict)
    if n > MAKS_TITIK_PERBAIKAN:
        return None
    if n <= AMBANG_TENGGAT_PERBAIKAN:
        return _kerja_perbaikan(geom_dict)     # terukur ≤ 1,7 dtk pada kasus terburuk
    status, hasil = _jalankan_bertenggat(
        _kerja_perbaikan, geom_dict, BATAS_DETIK_PERBAIKAN)
    if status == SELESAI:
        return hasil
    if status == TANPA_PROSES:
        # Tanpa tenggat kita TIDAK boleh menjalankan make_valid pada bentuk
        # sebesar ini: pengukuran menunjukkan bintang 501 verteks pun tak
        # kunjung selesai. Menolak jauh lebih baik daripada membeku.
        return None if n > MAKS_TITIK_TANPA_TENGGAT else _kerja_perbaikan(geom_dict)
    return None                                # tenggat lewat → menyerah, aman


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
