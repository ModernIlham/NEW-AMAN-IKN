"""Grid + TIPOGRAFI stiker BMN — LOGIKA MURNI (teruji unit).

Dua hal yang diputuskan di sini, keduanya tanpa menyentuh ReportLab supaya
bisa diuji tanpa merender PDF:

1. **Grid** — ukuran stiker harus MEMANFAATKAN SEGALA RUANG kertas A4/A3:
   jumlah kolom & baris dipilih paling dekat ke ukuran target, lalu ukuran
   label DIRENTANGKAN sehingga grid mengisi penuh area cetak; sisa ruang
   hanya margin halaman + celah tipis antar kotak.
2. **Tipografi** — ukuran huruf per peran (hierarki), pemenggalan baris, dan
   penyusutan otomatis agar teks panjang tetap terbaca. Semua fungsi di sini
   menerima fungsi pengukur `ukur(teks, size) -> lebar_pt` sebagai parameter,
   jadi pemanggil boleh memakai `pdfmetrics.stringWidth` sementara uji unit
   memakai pengukur palsu yang deterministik.

Prinsip keterbacaan (permintaan pemilik: "rapi di SEMUA ukuran"):
- Hierarki tetap: kode barang > nama barang > sub-sub kelompok > baris
  identitas satker. Perbandingannya dipertahankan di semua ukuran stiker,
  jadi mata langsung menemukan kode barang lebih dulu.
- LANTAI ukuran huruf: di stiker kecil huruf tidak dibiarkan mengecil
  mengikuti skala (dulu bisa ~4,2 pt — praktis tak terbaca setelah dicetak);
  ada batas bawah per peran, dan teks yang tak muat diselesaikan dengan
  pemenggalan baris, bukan dengan mengecilkan huruf tanpa batas.
- Teks panjang LANJUT KE BARIS BERIKUTNYA (nama barang & sub-sub kelompok),
  bukan dipotong di baris pertama.
"""

# Ukuran TARGET per pilihan (mm) — acuan pembulatan kolom/baris; dimensi
# akhir menyesuaikan kertas (lihat grid_optimal). `header` = tinggi kepala
# stiker pada ukuran target; tinggi kepala sebenarnya dihitung proporsional
# terhadap tinggi label nyata (lihat tinggi_header).
TARGET_STIKER = {
    "besar": {"w": 95, "h": 45, "header": 12},
    "sedang": {"w": 62, "h": 30, "header": 8.5},
    "kecil": {"w": 45, "h": 22, "header": 6.5},
}

MARGIN_MM = 6.0   # margin halaman
GAP_MM = 1.5      # celah tipis antar kotak (garis potong)

# Perbandingan hierarki (pt pada stiker "besar" 95×45 mm) dan LANTAI
# keterbacaan cetak (pt) per peran. Lantai inilah yang menjaga stiker kecil
# tetap terbaca; tanpa itu semua peran menyusut ke ±4 pt dan hierarkinya
# ikut hilang karena semua terlihat sama besar.
_SKALA_FONT = {
    #  peran        acuan  lantai  langit-langit
    "instansi":     (9.6,   5.6,   13.0),
    "sub":          (7.6,   5.0,   10.5),
    "kode":         (11.5,  6.6,   15.0),
    "nup":          (8.8,   5.6,   11.5),
    "nama":         (9.0,   6.0,   12.0),
    "subsub":       (7.4,   5.2,    9.5),
    "label":        (6.4,   4.8,    8.5),
}


def grid_optimal(page_w_mm, page_h_mm, target_w_mm, target_h_mm,
                 margin_mm=MARGIN_MM, gap_mm=GAP_MM):
    """(kolom, baris, lebar_label, tinggi_label) dalam mm — grid mengisi
    PENUH area cetak: kolom/baris = pembulatan terdekat ke ukuran target,
    label direntangkan menutup sisa ruang. MURNI."""
    avail_w = float(page_w_mm) - 2 * margin_mm
    avail_h = float(page_h_mm) - 2 * margin_mm
    kolom = max(1, round((avail_w + gap_mm) / (float(target_w_mm) + gap_mm)))
    baris = max(1, round((avail_h + gap_mm) / (float(target_h_mm) + gap_mm)))
    lw = (avail_w - (kolom - 1) * gap_mm) / kolom
    lh = (avail_h - (baris - 1) * gap_mm) / baris
    return kolom, baris, lw, lh


def kelompokkan_per_ukuran(aset_list, default="sedang"):
    """Kelompokkan aset menurut field `stiker_ukuran`-nya (mode cetak
    "sesuai pilihan per aset"). Nilai kosong/tak dikenal → `default`.
    Kembalikan list (ukuran, [aset...]) berurut besar → sedang → kecil,
    hanya kelompok berisi. MURNI."""
    kelompok = {"besar": [], "sedang": [], "kecil": []}
    for a in (aset_list or []):
        u = str((a or {}).get("stiker_ukuran") or "").strip().lower()
        if u not in kelompok:
            u = default
        kelompok[u].append(a)
    return [(u, kelompok[u]) for u in ("besar", "sedang", "kecil")
            if kelompok[u]]


def tinggi_header(tinggi_label_mm, ukuran):
    """Tinggi kepala stiker (mm) PROPORSIONAL terhadap tinggi label nyata.

    Label direntangkan mengisi kertas, jadi tinggi nyatanya tak persis sama
    dengan target; memakai angka `header` target apa adanya membuat kepala
    terlihat terlalu tebal/tipis pada kertas tertentu. MURNI."""
    t = TARGET_STIKER.get(str(ukuran or "").lower()) or TARGET_STIKER["sedang"]
    return float(tinggi_label_mm) * (t["header"] / t["h"])


def ukuran_font(lebar_mm, tinggi_mm):
    """Ukuran huruf (pt) per peran untuk label seukuran `lebar × tinggi` mm.

    Skalanya mengikuti dimensi label NYATA (dimensi terkecil yang menentukan,
    supaya label lebar-pendek tidak memakai huruf yang tak muat tingginya),
    lalu setiap peran dijepit antara lantai keterbacaan dan langit-langit
    agar hierarkinya tetap terasa di semua ukuran. MURNI."""
    t = TARGET_STIKER["besar"]
    skala = min(float(lebar_mm) / t["w"], float(tinggi_mm) / t["h"])
    hasil = {}
    for peran, (acuan, lantai, atap) in _SKALA_FONT.items():
        hasil[peran] = round(max(lantai, min(atap, acuan * skala)), 2)
    return hasil


def _penggal_kata(kata, lebar, ukur, size):
    """Penggal SATU kata yang lebih lebar daripada baris (mis. kode panjang
    tanpa spasi) menjadi beberapa potongan yang muat. MURNI."""
    potongan, kini = [], ""
    for huruf in kata:
        if kini and ukur(kini + huruf, size) > lebar:
            potongan.append(kini)
            kini = huruf
        else:
            kini += huruf
    if kini:
        potongan.append(kini)
    return potongan or [kata]


def _potong_elipsis(teks, lebar, ukur, size, elipsis="..."):
    """Potong `teks` sampai muat termasuk elipsis. MURNI."""
    if ukur(teks, size) <= lebar:
        return teks
    inti = teks
    while inti and ukur(inti.rstrip(" .,;:-") + elipsis, size) > lebar:
        inti = inti[:-1]
    return (inti.rstrip(" .,;:-") + elipsis) if inti else ""


def bagi_baris(teks, lebar, ukur, size, maks_baris=3):
    """Pecah `teks` menjadi maksimal `maks_baris` baris selebar `lebar` pt.

    Teks yang belum habis LANJUT KE BARIS BERIKUTNYA (bukan dipotong di baris
    pertama seperti perilaku lama); baru bila jatah baris habis, sisa terakhir
    diberi elipsis. MURNI — `ukur(teks, size)` disuntikkan pemanggil."""
    kata_semua = str(teks or "").strip()[:400].split()
    if not kata_semua or lebar <= 0 or maks_baris <= 0:
        return []
    semua, kini = [], ""
    for kata in kata_semua:
        coba = f"{kini} {kata}".strip()
        if ukur(coba, size) <= lebar:
            kini = coba
            continue
        if kini:
            semua.append(kini)
            kini = ""
        if ukur(kata, size) <= lebar:
            kini = kata
        else:
            potongan = _penggal_kata(kata, lebar, ukur, size)
            semua.extend(potongan[:-1])
            kini = potongan[-1]
    if kini:
        semua.append(kini)
    if len(semua) <= maks_baris:
        return semua
    dipakai = semua[:maks_baris]
    sisa = " ".join(semua[maks_baris:])
    dipakai[-1] = _potong_elipsis(f"{dipakai[-1]} {sisa}".strip(), lebar,
                                  ukur, size)
    return dipakai


def muat_satu_baris(teks, lebar, ukur, size, size_min, langkah=0.94):
    """(teks, size) yang muat dalam SATU baris selebar `lebar` pt.

    Huruf dikecilkan bertahap sampai `size_min`; bila masih tak muat barulah
    teksnya dipotong ber-elipsis. Dipakai untuk nama instansi & baris kedua
    kepala stiker — nama instansi panjang tak boleh meluber keluar kotak.
    MURNI."""
    teks = str(teks or "").strip()
    if not teks or lebar <= 0:
        return "", size
    kini = float(size)
    while ukur(teks, kini) > lebar and kini > size_min:
        kini = max(float(size_min), kini * langkah)
    if ukur(teks, kini) <= lebar:
        return teks, kini
    return _potong_elipsis(teks, lebar, ukur, kini), kini


def susun_header(nama_instansi, baris2, lebar, tinggi, f_instansi, f_sub,
                 ukur_tebal, ukur_biasa):
    """Susun kepala stiker: nama instansi (boleh 2 baris) + baris kedua.

    Urutan usaha untuk nama instansi yang panjang:
    1. satu baris dengan huruf penuh;
    2. satu baris dengan huruf disusutkan (sampai lantai keterbacaan);
    3. DUA baris — hanya bila tinggi kepala memang cukup;
    4. terakhir barulah dipotong ber-elipsis.

    Kembalikan dict {baris: [...], size, baris2, size2}. MURNI."""
    nama = str(nama_instansi or "").strip()
    lantai = max(4.6, f_instansi * 0.72)
    tinggi_sub = (f_sub * 1.25) if str(baris2 or "").strip() else 0.0
    muat_dua_baris = tinggi >= f_instansi * 2.1 + tinggi_sub

    baris = []
    size = float(f_instansi)
    if nama:
        satu, size_satu = muat_satu_baris(nama, lebar, ukur_tebal, f_instansi,
                                          lantai)
        if satu == nama:
            baris, size = [nama], size_satu
        elif muat_dua_baris:
            dua = bagi_baris(nama, lebar, ukur_tebal, f_instansi, maks_baris=2)
            baris, size = dua, float(f_instansi)
        else:
            baris, size = [satu], size_satu

    teks2, size2 = "", float(f_sub)
    if str(baris2 or "").strip():
        teks2, size2 = muat_satu_baris(str(baris2).strip(), lebar, ukur_biasa,
                                       f_sub, max(4.2, f_sub * 0.75))
    return {"baris": baris, "size": size, "baris2": teks2, "size2": size2}


def rencana_badan(tinggi_badan, f, sisakan=0.0):
    """Jatah baris untuk nama barang & sub-sub kelompok pada ruang setinggi
    `tinggi_badan` pt.

    Kode barang selalu dapat satu baris. Sisanya dibagi: nama barang lebih
    dulu (maks 3 baris) karena paling dicari petugas saat mencocokkan fisik,
    lalu sub-sub kelompok (maks 2 baris). Keduanya dijamin minimal satu baris
    selama ruangnya ada — sub-sub kelompok tidak lagi hilang di stiker kecil.
    MURNI."""
    sisa = float(tinggi_badan) - float(sisakan) - f["kode"] * 1.32
    tinggi_nama = f["nama"] * 1.18
    tinggi_sub = f["subsub"] * 1.16
    if sisa < tinggi_nama:
        return {"nama": 1 if sisa > 0 else 0, "subsub": 0}
    # satu baris untuk masing-masing lebih dulu, baru tambahan untuk nama
    n_nama, n_sub = 1, 0
    sisa -= tinggi_nama
    if sisa >= tinggi_sub:
        n_sub = 1
        sisa -= tinggi_sub
    while n_nama < 3 and sisa >= tinggi_nama:
        n_nama += 1
        sisa -= tinggi_nama
    while n_sub < 2 and n_sub >= 1 and sisa >= tinggi_sub:
        n_sub += 1
        sisa -= tinggi_sub
    return {"nama": n_nama, "subsub": n_sub}


def format_dimensi(lebar_mm, tinggi_mm):
    """Teks dimensi stiker gaya Indonesia (koma desimal) — dipakai pada
    stiker CONTOH agar pemesan tahu ukuran per satuan. MURNI."""
    import math

    def satu(n):
        # Pembulatan setengah-KE-ATAS yang eksplisit: format "%.1f" memakai
        # pembulatan bankir (98,25 → 98,2) yang membingungkan pada label ukur.
        return f"{math.floor(float(n) * 10 + 0.5) / 10:.1f}".replace(".", ",")
    return f"{satu(lebar_mm)} × {satu(tinggi_mm)} mm"
