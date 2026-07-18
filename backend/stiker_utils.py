"""Grid stiker OPTIMAL — LOGIKA MURNI (teruji unit).

Permintaan pemilik: ukuran stiker harus MEMANFAATKAN SEGALA RUANG kertas
A4/A3. Caranya: jumlah kolom & baris dipilih paling dekat ke ukuran target,
lalu ukuran label DIRENTANGKAN sehingga grid mengisi penuh area cetak —
sisa ruang hanya margin halaman + celah tipis antar kotak.
"""

# Ukuran TARGET per pilihan (mm) — acuan pembulatan kolom/baris; dimensi
# akhir menyesuaikan kertas (lihat grid_optimal).
TARGET_STIKER = {
    "besar": {"w": 95, "h": 45, "header": 12, "baris_desc": 3},
    "sedang": {"w": 62, "h": 30, "header": 8.5, "baris_desc": 2},
    "kecil": {"w": 45, "h": 22, "header": 6.5, "baris_desc": 1},
}

MARGIN_MM = 6.0   # margin halaman
GAP_MM = 1.5      # celah tipis antar kotak (garis potong)


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
