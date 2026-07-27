"""SBSK BERBASIS RUANG NYATA (Fase 15) — helper MURNI.

Sebelum fase ini, SBSK ruang kerja hanyalah tabel standar yang berdiri sendiri:
angka "247 m² untuk pimpinan" tanpa satu pun ruangan nyata untuk dibandingkan.
Denah poligon yang dibangun Fase 3–7 mengubah itu — luas ruangan bisa dihitung
DARI GAMBARNYA, bukan dari angka yang diketik ulang seseorang.

TIGA HAL YANG MENENTUKAN BENTUK MODUL INI
==========================================

1. **Peruntukan ruangan DITETAPKAN, bukan disimpulkan.** Godaannya besar:
   tebak penghuni ruangan dari pemegang aset yang ada di dalamnya. Tetapi ruang
   rapat yang penuh kursi ber-pemegang satu orang akan terbaca sebagai ruang
   kerja orang itu, lalu dibandingkan dengan standar jabatannya, lalu dilaporkan
   "melebihi standar 300%". Angka yang salah tetapi rapi jauh lebih berbahaya
   daripada kolom kosong. Karena itu peruntukan adalah FIELD pada node denah;
   isi aset hanya ditampilkan di sebelahnya sebagai INDIKASI.

2. **Ruangan tanpa peruntukan bukan kegagalan — itu temuan.** Justru ruangan
   yang sudah tergambar, punya luas, tetapi belum ditetapkan peruntukannya dan
   tak berisi aset apa pun, adalah RUANG MENGANGGUR: bukti paling langsung
   untuk menahan usulan pengadaan ruang baru.

3. **Selisih dilaporkan apa adanya, tanpa vonis.** SBSK adalah standar
   PERENCANAAN, bukan ambang pelanggaran. Ruangan yang lebih luas dari standar
   bisa saja gedung warisan yang tak bisa disekat. Modul ini menghitung selisih
   dan menamainya; keputusan tetap pada manusia.
"""

# Kategori SBSK yang relevan untuk ruangan. Baris kategori lain (kendaraan,
# barang) tak pernah ikut dicocokkan — mencocokkan "Pejabat eselon I" milik
# baris KENDARAAN ke sebuah ruangan akan membandingkan m² dengan unit.
KATEGORI_RUANG = "ruang_kerja"

# Toleransi kesesuaian. Denah dijiplak dari gambar kerja atau ditelusuri di
# atas citra; ketelitiannya beberapa persen, bukan sentimeter. Menyebut
# ruangan 246,8 m² "di bawah standar 247 m²" adalah presisi palsu.
TOLERANSI_PERSEN = 5.0

# Kata yang terlalu umum untuk dijadikan dasar pencocokan peruntukan.
_KATA_UMUM = {"ruang", "kerja", "pejabat", "kantor", "dan", "atau", "untuk",
              "setingkat", "milik", "para", "staf"}


def _kata_kunci(teks) -> set:
    """Kata bermakna dari sebuah frasa peruntukan (huruf kecil, ≥4 huruf)."""
    kata = str(teks or "").lower().replace("/", " ").replace("-", " ").split()
    return {k.strip(".,()") for k in kata
            if len(k.strip(".,()")) >= 4 and k.strip(".,()") not in _KATA_UMUM}


def cocokkan_standar_ruang(peruntukan, standar):
    """Baris SBSK `ruang_kerja` yang paling cocok dengan peruntukan ruangan.

    Pencocokan berbasis irisan kata kunci, dan yang menang adalah irisan
    TERBANYAK — bukan yang pertama ketemu. Tanpa itu, "Kepala Biro" akan
    tersambar baris "Menteri/pimpinan setingkat" hanya karena sama-sama memuat
    kata umum, dan seluruh laporan luas jadi salah acuan.

    Mengembalikan None bila tak ada yang beririsan: lebih baik kolom kosong
    yang jelas daripada standar yang keliru.
    """
    kunci_ruang = _kata_kunci(peruntukan)
    if not kunci_ruang:
        return None
    terbaik, skor_terbaik = None, 0
    for s in standar or []:
        if str((s or {}).get("kategori") or "").strip() != KATEGORI_RUANG:
            continue
        skor = len(kunci_ruang & _kata_kunci(s.get("peruntukan")))
        if skor > skor_terbaik:
            terbaik, skor_terbaik = s, skor
    return terbaik


def _angka(nilai):
    try:
        n = float(nilai)
        return n if n == n and n not in (float("inf"), float("-inf")) else None
    except (TypeError, ValueError):
        return None


def status_kesesuaian(luas_m2, standar_m2, toleransi_persen=TOLERANSI_PERSEN) -> str:
    """`sesuai` / `di_bawah` / `melebihi` / `tanpa_standar`.

    Toleransi dipakai DUA arah supaya ruangan yang praktis pas tidak dilaporkan
    menyimpang hanya karena pembulatan jiplakan denah.
    """
    l, s = _angka(luas_m2), _angka(standar_m2)
    if s is None or s <= 0 or l is None:
        return "tanpa_standar"
    batas = s * (float(toleransi_persen or 0) / 100.0)
    if l < s - batas:
        return "di_bawah"
    if l > s + batas:
        return "melebihi"
    return "sesuai"


def baris_ruang(node, luas_m2, isi, standar) -> dict:
    """Satu baris laporan SBSK-ruang.

    `isi` = ringkasan aset di dalam ruangan ({jumlah, pemegang}) — DITAMPILKAN
    sebagai indikasi okupansi, tidak pernah dipakai menebak peruntukan
    (lihat keputusan 1 di kepala berkas).
    """
    node = node or {}
    peruntukan = str(node.get("peruntukan") or "").strip()
    baris_standar = cocokkan_standar_ruang(peruntukan, standar) if peruntukan else None
    standar_m2 = _angka((baris_standar or {}).get("standar"))
    luas = _angka(luas_m2) or 0.0
    status = status_kesesuaian(luas, standar_m2)
    jumlah_aset = int((isi or {}).get("jumlah") or 0)
    return {
        "node_id": str(node.get("id") or ""),
        "nama": str(node.get("nama") or ""),
        "tipe": str(node.get("tipe") or ""),
        "jalur_nama": str(node.get("jalur_nama") or ""),
        "peruntukan": peruntukan,
        "luas_m2": round(luas, 2),
        "standar_m2": standar_m2,
        "standar_peruntukan": str((baris_standar or {}).get("peruntukan") or ""),
        "selisih_m2": (None if standar_m2 is None
                       else round(luas - standar_m2, 2)),
        "status": status,
        "jumlah_aset": jumlah_aset,
        "pemegang": sorted((isi or {}).get("pemegang") or []),
        # Sudah digambar, punya luas, tetapi tak berperuntukan DAN tak berisi
        # apa pun — inilah bukti ruang menganggur (keputusan 2).
        "menganggur": bool(not peruntukan and jumlah_aset == 0 and luas > 0),
    }


def rekap_sbsk_ruang(rows) -> dict:
    """Rekap satu lingkup: luas total, komposisi status, dan ruang menganggur.

    `luas_menganggur` sengaja dipisah dari "ruangan tanpa peruntukan": ruangan
    yang belum ditetapkan peruntukannya TETAPI penuh aset jelas terpakai — ia
    kekurangan administrasi, bukan kekurangan penghuni. Menyatukan keduanya
    akan melaporkan gedung yang sibuk sebagai gedung kosong.
    """
    rows = [r for r in (rows or []) if r]
    hitung = {"sesuai": 0, "di_bawah": 0, "melebihi": 0, "tanpa_standar": 0}
    luas_total = luas_menganggur = 0.0
    berperuntukan = menganggur = 0
    lebih = kurang = 0.0
    for r in rows:
        hitung[r.get("status", "tanpa_standar")] = hitung.get(
            r.get("status", "tanpa_standar"), 0) + 1
        luas_total += float(r.get("luas_m2") or 0)
        if r.get("peruntukan"):
            berperuntukan += 1
        if r.get("menganggur"):
            menganggur += 1
            luas_menganggur += float(r.get("luas_m2") or 0)
        selisih = r.get("selisih_m2")
        if selisih is not None:
            if selisih > 0:
                lebih += selisih
            else:
                kurang += -selisih
    return {
        "jumlah_ruangan": len(rows),
        "berperuntukan": berperuntukan,
        "tanpa_peruntukan": len(rows) - berperuntukan,
        "menganggur": menganggur,
        "luas_total_m2": round(luas_total, 2),
        "luas_menganggur_m2": round(luas_menganggur, 2),
        "kelebihan_m2": round(lebih, 2),
        "kekurangan_m2": round(kurang, 2),
        "status": hitung,
    }


def sebaran_per_induk(rows) -> list:
    """Sebaran ruangan per induk terdekat (lantai/gedung) — pengganti tekstual
    "peta sebaran" yang bisa dibaca tanpa merender peta.

    Diurutkan menurun berdasarkan luas: yang paling banyak memakan ruang muncul
    lebih dulu, karena di situlah keputusan perencanaan paling berdampak.
    """
    peta = {}
    for r in rows or []:
        # Induk = ruas kedua-dari-belakang pada jalur ("Gedung A / Lantai 3 /
        # Ruang 305" → "Lantai 3"). Jalur kosong tetap punya keranjangnya
        # sendiri supaya barisnya tak lenyap dari rekap.
        ruas = [x.strip() for x in str(r.get("jalur_nama") or "").split("/") if x.strip()]
        induk = ruas[-2] if len(ruas) >= 2 else (ruas[0] if ruas else "(tanpa induk)")
        e = peta.setdefault(induk, {"induk": induk, "jumlah_ruangan": 0,
                                    "luas_m2": 0.0, "menganggur": 0,
                                    "jumlah_aset": 0})
        e["jumlah_ruangan"] += 1
        e["luas_m2"] += float(r.get("luas_m2") or 0)
        e["jumlah_aset"] += int(r.get("jumlah_aset") or 0)
        if r.get("menganggur"):
            e["menganggur"] += 1
    hasil = list(peta.values())
    for e in hasil:
        e["luas_m2"] = round(e["luas_m2"], 2)
    hasil.sort(key=lambda e: (-e["luas_m2"], e["induk"]))
    return hasil
