"""Pembacaan tanggal untuk impor Excel/CSV — bagian murni, tanpa I/O.

KENAPA ADA. Sebelum ini kolom tanggal pada impor TIDAK divalidasi sama sekali:
`parse_excel_content` melakukan `str(cell or '')` dan apa pun hasilnya langsung
masuk basis data. Akibatnya tiga bentuk sampah lolos diam-diam:

1. Sel bertipe tanggal asli dibaca openpyxl sebagai `datetime`, lalu `str()`
   membuatnya `"2024-01-01 00:00:00"` — berbeda dari tanggal yang ditulis
   aplikasi sendiri (`YYYY-MM-DD`), sehingga urutan & penyaringan meleset.
2. Sel berformat Umum berisi SERIAL DATE Excel (mis. `45658`) masuk apa adanya
   sebagai teks angka — terbaca manusia sebagai nomor, bukan tanggal.
3. Ketikan bebas (`17/8/2025`, `17 Agustus 2025`, `2025/13/45`) diterima utuh,
   termasuk tanggal yang tak pernah ada.

FORMAT RESMI: `DD/MM/YYYY` (kebiasaan dokumen resmi Indonesia). Bentuk lain
yang TIDAK ambigu tetap diterima supaya berkas lama tak tertolak — ISO
`YYYY-MM-DD`, serial Excel, dan objek tanggal asli dari Excel. Yang ditolak
adalah yang benar-benar mustahil ditebak dengan jujur.

Semua hasil dinormalkan ke `YYYY-MM-DD` — satu bentuk di basis data.
"""
from datetime import date, datetime, timedelta

__all__ = [
    "FORMAT_RESMI", "TANGGAL_MIN", "TANGGAL_MAKS",
    "baca_tanggal", "normalkan_tanggal_baris", "KOLOM_TANGGAL",
]

FORMAT_RESMI = "DD/MM/YYYY"

# Kolom bertipe tanggal pada template impor aset.
KOLOM_TANGGAL = ("purchase_date", "garansi_hingga")

# Pagar kewarasan. Serial Excel & salah ketik gampang menghasilkan tahun 1900
# atau 5138; keduanya bukan tanggal perolehan BMN yang masuk akal, dan lebih
# baik ditolak terang-terangan daripada tersimpan diam-diam.
TANGGAL_MIN = date(1945, 1, 1)
TANGGAL_MAKS = date(2200, 12, 31)

# Titik nol serial Excel. Excel keliru menganggap 1900 tahun kabisat, jadi
# serial 1 = 1900-01-01 dipetakan dari basis 1899-12-30 — bukan 1899-12-31.
_EPOCH_EXCEL = date(1899, 12, 30)

# Serial di bawah ini adalah wilayah "bug 1900" Excel (1..60) yang pemetaannya
# tak konsisten antar aplikasi. Angka sekecil itu jauh lebih mungkin salah
# ketik daripada tanggal sungguhan, jadi diperlakukan sebagai galat.
_SERIAL_MIN = 61          # 1900-03-01
_SERIAL_MAKS = 110000     # ±2201

# Bentuk teks yang diterima. `DD/MM/YYYY` lebih dulu — ia yang resmi.
_POLA = (
    ("%d/%m/%Y", "DD/MM/YYYY"),
    ("%d-%m-%Y", "DD-MM-YYYY"),
    ("%d.%m.%Y", "DD.MM.YYYY"),
    ("%Y-%m-%d", "YYYY-MM-DD"),
    ("%Y/%m/%d", "YYYY/MM/DD"),
)


def _dalam_rentang(d: date):
    if d < TANGGAL_MIN or d > TANGGAL_MAKS:
        return (
            f"tahun {d.year} di luar rentang wajar "
            f"({TANGGAL_MIN.year}–{TANGGAL_MAKS.year})"
        )
    return None


def _dari_serial(angka: float):
    """Serial Excel → (date, galat)."""
    if angka != int(angka):
        # Serial pecahan = tanggal + jam. Jamnya tak dipakai; ambil harinya.
        angka = int(angka)
    n = int(angka)
    if n < _SERIAL_MIN or n > _SERIAL_MAKS:
        return None, (
            f"angka {n} bukan tanggal Excel yang wajar. "
            f"Bila ini memang tanggal, format ulang selnya sebagai Tanggal "
            f"atau ketik dengan format {FORMAT_RESMI}"
        )
    return _EPOCH_EXCEL + timedelta(days=n), None


def baca_tanggal(nilai):
    """Baca satu sel tanggal.

    Mengembalikan `(iso, galat)`:
      - `("2025-08-17", None)` bila terbaca,
      - `(None, None)` bila sel KOSONG (kolom tanggal semuanya opsional),
      - `(None, "alasan")` bila tak bisa dibaca dengan jujur.

    Alasan galat sengaja menyebut apa yang dilihat DAN apa yang seharusnya —
    operator perlu tahu sel mana yang harus dibetulkan, bukan sekadar bahwa
    ada yang salah.
    """
    # 1) Objek tanggal asli (openpyxl mengembalikan ini untuk sel bertipe
    #    tanggal). `datetime` diperiksa lebih dulu: ia turunan `date`.
    if isinstance(nilai, datetime):
        d = nilai.date()
        return (None, _dalam_rentang(d)) if _dalam_rentang(d) else (d.isoformat(), None)
    if isinstance(nilai, date):
        return (None, _dalam_rentang(nilai)) if _dalam_rentang(nilai) else (nilai.isoformat(), None)

    # 2) Angka murni = serial Excel. `bool` disaring: True/False adalah int
    #    di Python dan jelas bukan tanggal.
    if isinstance(nilai, bool):
        return None, f"nilai '{nilai}' bukan tanggal"
    if isinstance(nilai, (int, float)):
        d, galat = _dari_serial(float(nilai))
        if galat:
            return None, galat
        g = _dalam_rentang(d)
        return (None, g) if g else (d.isoformat(), None)

    teks = str(nilai if nilai is not None else "").strip()
    if not teks:
        return None, None

    # 3) Teks hasil `str(datetime)` — "2024-01-01 00:00:00". Buang bagian jam.
    if " " in teks:
        depan = teks.split(" ", 1)[0]
        if depan:
            teks = depan
    if "T" in teks and len(teks) > 10:
        teks = teks.split("T", 1)[0]

    # 4) Serial Excel yang sudah terlanjur jadi teks ("45658", "45658.0").
    if teks.replace(".", "", 1).isdigit() and "/" not in teks and "-" not in teks:
        d, galat = _dari_serial(float(teks))
        if galat:
            return None, galat
        g = _dalam_rentang(d)
        return (None, g) if g else (d.isoformat(), None)

    for pola, _label in _POLA:
        try:
            d = datetime.strptime(teks, pola).date()
        except ValueError:
            continue
        g = _dalam_rentang(d)
        return (None, g) if g else (d.isoformat(), None)

    return None, (
        f"'{teks}' bukan tanggal yang dikenali. "
        f"Pakai format {FORMAT_RESMI} (contoh: 17/08/2025)"
    )


def normalkan_tanggal_baris(row: dict, nomor_baris: int, kolom=KOLOM_TANGGAL):
    """Baca & normalkan semua kolom tanggal pada satu baris.

    Mengubah `row` DI TEMPAT menjadi bentuk `YYYY-MM-DD`, dan mengembalikan
    daftar pesan galat (kosong = semua beres). Baris dibiarkan apa adanya untuk
    kolom yang bermasalah supaya nilai aslinya masih terlihat operator saat
    membetulkan berkasnya.
    """
    galat = []
    for k in kolom:
        if k not in row:
            continue
        iso, pesan = baca_tanggal(row.get(k))
        if pesan:
            galat.append(f"Baris {nomor_baris}: kolom '{k}' — {pesan}")
        elif iso is not None:
            row[k] = iso
        else:
            row[k] = ""      # kosong tetap kosong, bukan "None"
    return galat
