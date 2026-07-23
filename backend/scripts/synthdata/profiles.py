"""Profil generator + injeksi anomali (edge case).

Tujuan: memperluas cakupan pengujian dengan data yang "aneh tapi mungkin" —
kasus tepi yang sering lolos dari data buatan tangan dan menyebabkan bug di
parser impor, render PDF/XLSX, peta koordinat, atau parsing tanggal.

Semua nilai anomali tetap berupa STRING sehingga record tetap lolos skema
``AssetCreate`` (semua field skalar bertipe ``Optional[str]``). Yang diuji
bukan validasi Pydantic, melainkan ketahanan LOGIKA aplikasi terhadap isi
yang ekstrem. Anomali dipilih deterministik dari ``rng`` yang di-seed.
"""

# Nilai tanggal ekstrem — termasuk 9999-12-31 (pernah memicu OverflowError
# pada strptime, lihat catatan skill aman-dev), tanggal mustahil, & format lain.
EDGE_TANGGAL = (
    "9999-12-31",       # jebakan OverflowError
    "0001-01-01",
    "1900-01-01",
    "31-02-2020",       # 31 Februari — tanggal mustahil
    "2020/13/45",       # bulan/hari di luar rentang
    "2024-02-29",       # kabisat sah (kontrol)
    "  2023-06-15  ",   # spasi berlebih
    "15 Agustus 2024",  # format Indonesia bebas
    "",                 # kosong
    "tanggal tidak diketahui",
)

# Nilai numerik/harga ekstrem.
EDGE_ANGKA = (
    "0",
    "-1",
    "999999999999999",  # sangat besar
    "1e12",             # notasi ilmiah
    "Rp 5.000.000,00",  # berformat rupiah
    "5.000.000",        # pemisah ribuan
    "gratis",           # bukan angka
    "NaN",
    "  1200000  ",      # spasi
    "",                 # kosong
)

# Koordinat ekstrem — di luar rentang sah, kutub, nol, & non-numerik.
EDGE_KOORDINAT = (
    "91.0",             # > 90, di luar rentang lintang sah
    "-181.5",           # < -180, di luar rentang bujur sah
    "0",                # Null Island
    "-0.0",
    "abc",              # non-numerik
    "116,8500",         # koma sebagai desimal (locale ID)
    "",                 # kosong
    "1.05,116.8",       # dua nilai dalam satu field
)

# Teks ekstrem — panjang, unicode/emoji, whitespace, serta pola yang MIRIP
# upaya injeksi (harus disimpan sebagai teks polos, bukan dieksekusi).
EDGE_TEKS = (
    " " * 40,                              # whitespace saja
    "A" * 4000,                            # sangat panjang (uji layout/PDF)
    "Méjà Kërjá Kāyú 🪑🔥",                 # unicode + emoji
    "اختبار العربية",                      # RTL
    "试验中文字符",                          # CJK
    "Baris1\nBaris2\tKolom",               # newline/tab
    "'; DROP TABLE assets;--",             # mirip SQLi
    '{"$gt": ""}',                         # mirip operator NoSQL
    "<script>alert('xss')</script>",       # mirip XSS
    "../../../../etc/passwd",              # mirip path traversal
    "null",
    "undefined",
    "N/A",
)

# Peta "jenis nilai" → bank anomali yang sesuai. generator.py menandai tiap
# field dengan salah satu jenis ini agar anomali yang disuntikkan masuk akal.
BANK_ANOMALI = {
    "tanggal": EDGE_TANGGAL,
    "angka": EDGE_ANGKA,
    "koordinat": EDGE_KOORDINAT,
    "teks": EDGE_TEKS,
}

# Konfigurasi profil: seberapa sering anomali disuntikkan per field (rasio),
# dan apakah boleh membuat duplikat kode/NUP sengaja (uji jalur keunikan).
PROFIL = {
    # Data "sehat" — mendekati produksi, tanpa anomali.
    "normal": {"rasio_anomali": 0.0, "izinkan_duplikat": False},
    # Sebagian besar sehat, sebagian anomali — realistis untuk uji ketahanan.
    "mixed": {"rasio_anomali": 0.15, "izinkan_duplikat": True},
    # Fokus edge case — mayoritas field beranomali; untuk uji stabilitas ekstrem.
    "edge": {"rasio_anomali": 0.6, "izinkan_duplikat": True},
}

PROFIL_DEFAULT = "normal"


def maybe_anomali(rng, jenis: str, rasio: float):
    """Kembalikan nilai anomali (str) dengan peluang ``rasio``, atau None.

    ``jenis`` ∈ {tanggal, angka, koordinat, teks}. Bila jenis tak dikenal,
    dianggap "teks". Deterministik terhadap ``rng`` yang di-seed.
    """
    if rasio <= 0:
        return None
    if rng.random() >= rasio:
        return None
    bank = BANK_ANOMALI.get(jenis, EDGE_TEKS)
    return rng.choice(bank)
