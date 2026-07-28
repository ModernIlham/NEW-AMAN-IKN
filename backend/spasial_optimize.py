"""OPTIMALISASI GEOMETRI PETA — helper MURNI (tanpa I/O, tanpa DB).

Peta kawasan IKN yang diimpor dari SHP/KML lazim memuat puluhan ribu verteks
per poligon. Peramban harus mengurai, mengirim, dan menggambar semuanya —
padahal pada zoom mana pun mata manusia tak bisa membedakan garis yang
verteksnya berjarak 2 cm. Beban itu ditanggung petugas lapangan yang membuka
peta lewat HP dengan sinyal seadanya.

EMPAT KEPUTUSAN YANG MENENTUKAN BENTUK MODUL INI
=================================================

1. **GEOMETRI ASLI TIDAK PERNAH DISENTUH.** Hasil optimasi disimpan di field
   TERPISAH. Ini bukan kehati-hatian berlebihan: poligon denah adalah dasar
   perhitungan LUAS RUANGAN untuk SBSK, dasar deteksi lokasi otomatis, dan
   bahan ekspor ke QGIS. Menyederhanakan di tempat berarti membuang presisi
   survei yang mahal dikumpulkan dan MUSTAHIL dipulihkan. Yang boleh
   disederhanakan hanyalah SALINAN untuk ditampilkan.

2. **TOLERANSI DIHITUNG DARI UKURAN OBJEKNYA, bukan angka tetap.** Ruangan
   10 m dan kawasan 50 km tak mungkin memakai toleransi yang sama: angka yang
   aman bagi kawasan akan MELENYAPKAN ruangan. Karena itu toleransi diturunkan
   dari diagonal bbox objek itu sendiri.

3. **SWEET SPOT DICARI, BUKAN DITEBAK.** Modul ini menaiki tangga toleransi
   dan berhenti pada nilai TERBESAR yang penyimpangannya masih di bawah
   anggaran (pergeseran meter DAN perubahan luas). Jadi "seberapa banyak
   detail yang hilang" bukan harapan, melainkan angka yang diukur dan
   dilaporkan — dan operator boleh menolaknya.

4. **TOPOLOGI DIJAGA.** `preserve_topology=True` mencegah poligon berpotongan
   sendiri atau lenyap. Poligon yang rusak lebih buruk daripada poligon berat:
   ia menggagalkan perhitungan luas dan deteksi lokasi, diam-diam.

Rujukan pendekatan: mapshaper.org (penyederhanaan Douglas–Peucker/Visvalingam
ber-topologi, pembulatan presisi koordinat, penyaringan per-bbox).
"""
from spasial_utils import hitung_bbox, meter_per_derajat

# Batas presisi koordinat derajat desimal. Pada khatulistiwa:
#   6 desimal ≈ 11 cm · 7 desimal ≈ 1,1 cm · 8 desimal ≈ 1,1 mm
# Denah dalam-gedung butuh sentimeter; menyimpan 14 desimal (bawaan float
# JSON) hanya membesarkan payload tanpa menambah informasi apa pun.
PRESISI_MIN, PRESISI_MAKS = 4, 9
PRESISI_BAWAAN = 7

# Anggaran penyimpangan bawaan — sengaja KETAT. Ini denah aset negara yang
# dipakai menghitung luas ruangan SBSK, bukan peta hiasan.
MAKS_GESER_M = 0.35        # LANTAI mutlak: pergeseran garis maksimum
MAKS_DELTA_LUAS = 0.5      # persen perubahan luas maksimum

# Anggaran pergeseran juga BOLEH tumbuh mengikuti ukuran objek — dan harus.
# Anggaran mutlak yang pas untuk ruangan 4 m MUSTAHIL dipenuhi kawasan 27 km:
# jarak antar-verteks aslinya saja sudah puluhan meter, sehingga tak satu pun
# anak tangga lolos dan poligon raksasa itu tak pernah teroptimasi sama sekali
# (ditemukan oleh uji `test_kawasan_besar_juga_tertangani`).
#
# 1/20.000 diagonal ≈ 0,05 mm per meter layar pada zoom yang wajar untuk objek
# seukuran itu — pergeseran yang secara harfiah lebih tipis daripada garis yang
# menggambarnya. Untuk ruangan (diagonal ~78 m) angka ini hanya 4 mm, jadi
# LANTAI mutlak 0,35 m yang tetap berlaku; keduanya tak pernah saling melonggarkan.
FRAKSI_GESER_RELATIF = 0.00005

# Tangga toleransi sebagai FRAKSI diagonal bbox objek. Dinaikkan pelan-pelan;
# yang dipakai adalah anak tangga TERTINGGI yang masih lolos anggaran.
TANGGA_FRAKSI = (0.0, 0.00002, 0.00005, 0.0001, 0.0002, 0.0005,
                 0.001, 0.002, 0.005)

# Di bawah ini tak ada gunanya dioptimalkan: poligon sederhana justru bisa
# rusak, dan hematnya tak terasa.
MIN_TITIK_OPTIMASI = 12


def _titik_geom(geom) -> int:
    """Cacah verteks sebuah GeoJSON geometry (rekursif, tahan bentuk aneh)."""
    if not isinstance(geom, dict):
        return 0
    if geom.get("type") == "GeometryCollection":
        return sum(_titik_geom(g) for g in geom.get("geometries") or [])
    return _cacah(geom.get("coordinates"))


def _cacah(koordinat) -> int:
    if not isinstance(koordinat, (list, tuple)) or not koordinat:
        return 0
    kepala = koordinat[0]
    if isinstance(kepala, (int, float)):
        return 1                       # ini SATU posisi [lon, lat]
    return sum(_cacah(k) for k in koordinat)


def _bulatkan(koordinat, desimal: int):
    """Bulatkan seluruh posisi secara rekursif — struktur dipertahankan."""
    if isinstance(koordinat, (int, float)):
        return round(float(koordinat), desimal)
    if isinstance(koordinat, (list, tuple)):
        return [_bulatkan(k, desimal) for k in koordinat]
    return koordinat


def presisi_koordinat(geom, desimal: int = PRESISI_BAWAAN):
    """Pangkas desimal koordinat. Geometri baru; masukan TIDAK diubah.

    Pembulatan dilakukan SETELAH penyederhanaan, bukan sebelum: membulatkan
    lebih dulu dapat membuat verteks berimpit dan menggagalkan `simplify`.
    """
    if not isinstance(geom, dict) or "coordinates" not in geom:
        return geom
    d = max(PRESISI_MIN, min(PRESISI_MAKS, int(desimal)))
    return {**geom, "coordinates": _bulatkan(geom.get("coordinates"), d)}


def diagonal_bbox_m(geom) -> float:
    """Panjang diagonal bbox objek dalam METER — skala acuan toleransi.

    0.0 bila bbox tak terhitung (geometri kosong/rusak).
    """
    bbox = hitung_bbox(geom)
    if not bbox or len(bbox) < 4:
        return 0.0
    lon0, lat0, lon1, lat1 = (float(bbox[0]), float(bbox[1]),
                              float(bbox[2]), float(bbox[3]))
    mlat, mlon = meter_per_derajat((lat0 + lat1) / 2.0)
    dx, dy = abs(lon1 - lon0) * mlon, abs(lat1 - lat0) * mlat
    return (dx * dx + dy * dy) ** 0.5


def _shapely(geom):
    """GeoJSON → objek shapely; None bila tak bisa dibaca."""
    try:
        from shapely.geometry import shape
        g = shape(geom)
        return g if not g.is_empty else None
    except Exception:                                   # noqa: BLE001
        return None


def ukur_penyimpangan(asli, hasil) -> dict:
    """Seberapa jauh hasil menyimpang dari aslinya.

    - `geser_m`      — jarak Hausdorff (pergeseran garis TERBURUK), meter.
                       Inilah ukuran yang benar untuk "bentuknya berubah tidak";
                       selisih luas saja bisa nol pada perubahan yang menggeser
                       dua sisi ke arah berlawanan.
    - `delta_luas_persen` — perubahan luas, penting karena luas ruangan dipakai
                       menghitung kesesuaian SBSK.

    Keduanya `None` bila tak terukur (shapely gagal / geometri kosong).
    """
    a, b = _shapely(asli), _shapely(hasil)
    if a is None or b is None:
        return {"geser_m": None, "delta_luas_persen": None}
    try:
        pusat_lat = (a.bounds[1] + a.bounds[3]) / 2.0
        mlat, mlon = meter_per_derajat(pusat_lat)
        # Hausdorff dalam DERAJAT → meter. Dipakai skala terkecil (lintang vs
        # bujur) supaya angkanya konservatif, bukan optimistis.
        geser_deg = a.hausdorff_distance(b)
        geser_m = geser_deg * min(mlat, mlon)
        luas_a, luas_b = a.area, b.area
        delta = (abs(luas_a - luas_b) / luas_a * 100.0) if luas_a else 0.0
        return {"geser_m": round(geser_m, 3),
                "delta_luas_persen": round(delta, 4)}
    except Exception:                                   # noqa: BLE001
        return {"geser_m": None, "delta_luas_persen": None}


def sederhanakan(geom, toleransi_deg: float):
    """Douglas–Peucker BER-TOPOLOGI. None bila gagal / hasilnya rusak.

    `preserve_topology=True` mencegah poligon berpotongan sendiri atau lenyap.
    Poligon rusak lebih berbahaya daripada poligon berat: ia menggagalkan
    perhitungan luas dan deteksi lokasi otomatis TANPA galat yang terlihat.
    """
    g = _shapely(geom)
    if g is None or toleransi_deg <= 0:
        return None
    try:
        from shapely.geometry import mapping
        hasil = g.simplify(toleransi_deg, preserve_topology=True)
        if hasil.is_empty or not hasil.is_valid:
            return None
        return mapping(hasil)
    except Exception:                                   # noqa: BLE001
        return None


def optimalkan(geom, maks_geser_m: float = MAKS_GESER_M,
               maks_delta_luas: float = MAKS_DELTA_LUAS,
               desimal: int = PRESISI_BAWAAN) -> dict:
    """Cari SWEET SPOT: penyederhanaan terbesar yang masih di bawah anggaran.

    → {"geometry", "metrik"} — `geometry` None berarti "tak ada gunanya
    dioptimalkan"; pemanggil harus tetap memakai yang asli, bukan menyimpan
    None sebagai hasil.

    Metrik yang dikembalikan adalah BUKTI, bukan janji: berapa verteks hilang,
    berapa persen hemat, seberapa jauh garis bergeser, dan berapa persen luas
    berubah. Operator berhak menolak angka itu.
    """
    titik_asli = _titik_geom(geom)
    metrik = {"titik_asli": titik_asli, "titik_hasil": titik_asli,
              "hemat_persen": 0.0, "toleransi_deg": 0.0, "toleransi_m": 0.0,
              "geser_m": 0.0, "delta_luas_persen": 0.0, "desimal": int(desimal),
              "anggaran_geser_m": float(maks_geser_m), "alasan": ""}

    if titik_asli < MIN_TITIK_OPTIMASI:
        metrik["alasan"] = (f"hanya {titik_asli} titik — di bawah ambang "
                            f"{MIN_TITIK_OPTIMASI}, tak ada yang perlu dihemat")
        return {"geometry": None, "metrik": metrik}

    diag_m = diagonal_bbox_m(geom)
    if diag_m <= 0:
        metrik["alasan"] = "bbox tak terhitung — geometri kosong atau rusak"
        return {"geometry": None, "metrik": metrik}

    bbox = hitung_bbox(geom) or [0, 0, 0, 0]
    mlat, mlon = meter_per_derajat((float(bbox[1]) + float(bbox[3])) / 2.0)
    m_per_deg = min(mlat, mlon) or 1.0

    # Anggaran efektif: LANTAI mutlak, dinaikkan mengikuti ukuran objek.
    anggaran_geser = max(float(maks_geser_m), diag_m * FRAKSI_GESER_RELATIF)
    metrik["anggaran_geser_m"] = round(anggaran_geser, 3)

    terbaik = None
    for fraksi in TANGGA_FRAKSI:
        if fraksi <= 0:
            continue
        tol_m = diag_m * fraksi
        tol_deg = tol_m / m_per_deg
        calon = sederhanakan(geom, tol_deg)
        if calon is None:
            continue
        dev = ukur_penyimpangan(geom, calon)
        geser, dluas = dev["geser_m"], dev["delta_luas_persen"]
        if geser is None or dluas is None:
            continue
        if geser > anggaran_geser or dluas > maks_delta_luas:
            break          # tangga menaik: sekali lewat, sisanya pasti lewat
        terbaik = {"geometry": calon, "tol_deg": tol_deg, "tol_m": tol_m,
                   "geser_m": geser, "delta_luas_persen": dluas}

    if terbaik is None:
        # Tak ada anak tangga yang lolos — pembulatan presisi SAJA masih
        # menghemat payload tanpa menggeser garis sedikit pun.
        bulat = presisi_koordinat(geom, desimal)
        metrik["alasan"] = ("tak ada toleransi yang lolos anggaran; hanya "
                            "presisi koordinat yang dipangkas")
        metrik["titik_hasil"] = _titik_geom(bulat)
        return {"geometry": bulat, "metrik": metrik}

    akhir = presisi_koordinat(terbaik["geometry"], desimal)
    # Pembulatan bisa menggeser garis sedikit lagi — diukur ULANG supaya angka
    # yang dilaporkan benar-benar milik geometri yang disimpan.
    dev_akhir = ukur_penyimpangan(geom, akhir)
    titik_hasil = _titik_geom(akhir)
    metrik.update({
        "titik_hasil": titik_hasil,
        "hemat_persen": (round(100.0 * (titik_asli - titik_hasil) / titik_asli, 1)
                         if titik_asli else 0.0),
        "toleransi_deg": round(terbaik["tol_deg"], 12),
        "toleransi_m": round(terbaik["tol_m"], 3),
        "geser_m": dev_akhir["geser_m"],
        "delta_luas_persen": dev_akhir["delta_luas_persen"],
        "alasan": "",
    })
    return {"geometry": akhir, "metrik": metrik}


def pilih_geometri_tampil(doc: dict, pakai_asli: bool = False):
    """Geometri mana yang dikirim ke peta.

    Bawaan: versi OPTIMIZE bila ada. `pakai_asli=True` (saklar "lihat file
    asli" di layar) mengembalikan yang asli. Dokumen yang belum pernah
    dioptimalkan selalu mengembalikan aslinya — tak ada keadaan di mana peta
    kehilangan bentuknya karena optimasi belum dijalankan.
    """
    d = doc or {}
    asli = d.get("geometry")
    if pakai_asli:
        return asli
    return d.get("geometry_opt") or asli


def ringkas_optimasi(doc: dict) -> dict:
    """Ringkasan status optimasi satu node — bahan badge & tombol di layar."""
    d = doc or {}
    m = d.get("optimasi") or {}
    ada = bool(d.get("geometry_opt"))
    return {
        "dioptimalkan": ada,
        "titik_asli": int(m.get("titik_asli") or 0),
        "titik_hasil": int(m.get("titik_hasil") or 0),
        "hemat_persen": float(m.get("hemat_persen") or 0.0),
        "geser_m": m.get("geser_m"),
        "delta_luas_persen": m.get("delta_luas_persen"),
        "pada": str(m.get("pada") or ""),
    }
