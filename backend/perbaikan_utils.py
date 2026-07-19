"""Logika murni PERBAIKAN YANG MENAMBAH MASA MANFAAT (PMK 65/2017 Pasal 15).

Dasar hukum (dokumen resmi diunggah pemilik, ditranskrip halaman-per-halaman):
- PMK 65/PMK.06/2017 Pasal 13(4)b & Pasal 15: perbaikan (renovasi/restorasi/
  overhaul) yang menambah masa manfaat/kapasitas MENGUBAH masa manfaat aset,
  berpedoman pada Tabel Masa Manfaat II yang ditetapkan Dirjen KN.
- KMK 295/KM.6/2019 Diktum KELIMA-KEENAM: Tabel II = tabel masa manfaat atas
  perbaikan; pengakuan tambahan dilakukan SAAT PENYERAHAN PEKERJAAN perbaikan
  melalui BERITA ACARA SERAH TERIMA.
- KMK 266/KM.6/2023 (Peralatan Keimigrasian 320xx, Instalasi Keselamatan
  32101) dan KMK 339/KM.6/2024 (Oil & Gas Facilities 31304, Wells 31305)
  menambah baris pada Tabel I & II.

TABEL_MASA_MANFAAT_II: kelompok 5 digit → {"jenis", "rentang"} dengan
rentang = tuple (batas_atas_persen, tambahan_tahun) terurut naik; bracket
dipilih pada batas atas PERTAMA yang >= persentase (rentang KMK memakai pola
"> a% s.d. b%"). Persentase = biaya perbaikan / nilai aset di luar penyusutan
(nilai perolehan bruto / basis revaluasi) x 100.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

# Jenis perbaikan per PMK 65/2017: Overhaul (peralatan/mesin), Renovasi
# (menambah/mengganti komponen), Restorasi (memperbaiki dengan
# mempertahankan arsitektur). Kolom JENIS pada tabel KMK menentukan jenis
# perbaikan yang relevan untuk kelompok tersebut.
TABEL_MASA_MANFAAT_II = {
    # ── Golongan 3 — Peralatan dan Mesin (KMK 295/2019) ──
    "30101": {"jenis": "Overhaul", "rentang": ((30, 1), (45, 3), (65, 5))},
    "30102": {"jenis": "Overhaul", "rentang": ((30, 1), (45, 2), (65, 4))},
    "30103": {"jenis": "Overhaul", "rentang": ((30, 1), (45, 2), (65, 4))},
    "30201": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 3), (100, 4))},
    "30202": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 1), (75, 1), (100, 1))},
    "30203": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 6))},
    "30204": {"jenis": "Renovasi", "rentang": ((25, 1), (50, 1), (75, 1), (100, 2))},
    "30205": {"jenis": "Overhaul", "rentang": ((25, 3), (50, 6), (75, 9), (100, 12))},
    "30301": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 3), (100, 4))},
    "30302": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 0), (75, 1), (100, 1))},
    "30303": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 2), (100, 3))},
    "30401": {"jenis": "Overhaul", "rentang": ((20, 1), (40, 2), (75, 5))},
    "30501": {"jenis": "Overhaul", "rentang": ((25, 0), (50, 1), (75, 2), (100, 3))},
    "30502": {"jenis": "Overhaul", "rentang": ((25, 0), (50, 1), (75, 2), (100, 3))},
    "30601": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 2), (100, 3))},
    "30602": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 3))},
    "30603": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 5))},
    "30604": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 5), (75, 7), (100, 9))},
    "30701": {"jenis": "Overhaul", "rentang": ((25, 0), (50, 1), (75, 2), (100, 3))},
    "30702": {"jenis": "Overhaul", "rentang": ((25, 0), (50, 1), (75, 2), (100, 3))},
    "30801": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 4))},
    "30802": {"jenis": "Overhaul", "rentang": ((25, 3), (50, 5), (75, 7), (100, 8))},
    "30803": {"jenis": "Overhaul", "rentang": ((25, 3), (50, 5), (75, 7), (100, 8))},
    "30804": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 5), (100, 5))},
    "30805": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 5), (100, 5))},
    "30806": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 3), (100, 4))},
    "30807": {"jenis": "Overhaul", "rentang": ((25, 3), (50, 5), (75, 7), (100, 8))},
    "30808": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 5), (100, 5))},
    "30901": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 3), (100, 4))},
    "30902": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 0), (75, 1), (100, 1))},
    "30903": {"jenis": "Overhaul", "rentang": ((25, 0), (50, 0), (75, 0), (100, 2))},
    "30904": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    "31001": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    "31002": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    "31101": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 2), (100, 3))},
    "31102": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 5), (100, 5))},
    "31201": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 6), (100, 7))},
    "31202": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 1), (75, 1), (100, 2))},
    "31301": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 1), (75, 1), (100, 2))},
    "31302": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 1), (75, 1), (100, 2))},
    "31303": {"jenis": "Overhaul", "rentang": ((25, 3), (50, 5), (75, 7), (100, 8))},
    # KMK 339/KM.6/2024 (berlaku bertahap mulai TA 2025)
    "31304": {"jenis": "Overhaul", "rentang": ((50, 0), (100, 10))},
    "31305": {"jenis": "Overhaul", "rentang": ((50, 0), (100, 10))},
    "31401": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 6), (100, 7))},
    "31402": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 6), (100, 7))},
    "31501": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 2), (100, 3))},
    "31502": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 0), (75, 1), (100, 2))},
    "31503": {"jenis": "Renovasi", "rentang": ((25, 0), (50, 1), (75, 1), (100, 1))},
    "31504": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 6))},
    "31601": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 4), (75, 5), (100, 5))},
    "31701": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 4))},
    "31801": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 3), (100, 4))},
    "31802": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 2), (75, 2), (100, 4))},
    "31803": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 5), (75, 7), (100, 9))},
    "31901": {"jenis": "Renovasi", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    # KMK 266/KM.6/2023 (Peralatan Keimigrasian + Instalasi Keselamatan)
    "32001": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    "32002": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 3), (75, 4), (100, 5))},
    "32101": {"jenis": "Overhaul", "rentang": ((25, 2), (50, 5), (75, 7), (100, 9))},
    # ── Golongan 4 — Gedung dan Bangunan ──
    "40101": {"jenis": "Renovasi", "rentang": ((25, 5), (50, 10), (75, 15), (100, 50))},
    "40102": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "40201": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "40301": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "40401": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    # ── Golongan 5 — Jalan, Irigasi, dan Jaringan ──
    "50101": {"jenis": "Renovasi", "rentang": ((30, 2), (60, 5), (100, 10))},
    "50102": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15), (100, 15))},
    "50201": {"jenis": "Renovasi", "rentang": ((5, 2), (10, 5), (20, 10))},
    "50202": {"jenis": "Renovasi", "rentang": ((5, 2), (10, 5), (20, 10))},
    "50203": {"jenis": "Renovasi", "rentang": ((5, 1), (10, 3), (20, 5))},
    "50204": {"jenis": "Renovasi", "rentang": ((5, 1), (10, 2), (20, 3))},
    "50205": {"jenis": "Renovasi", "rentang": ((5, 1), (10, 2), (20, 3))},
    "50206": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50207": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50301": {"jenis": "Renovasi", "rentang": ((30, 2), (45, 7), (65, 10))},
    "50302": {"jenis": "Renovasi", "rentang": ((30, 2), (45, 7), (65, 10))},
    "50303": {"jenis": "Renovasi", "rentang": ((30, 1), (45, 3), (65, 5))},
    "50304": {"jenis": "Renovasi", "rentang": ((30, 1), (45, 3), (65, 5))},
    "50305": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50306": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50307": {"jenis": "Renovasi", "rentang": ((30, 1), (45, 3), (65, 5))},
    "50308": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50309": {"jenis": "Renovasi", "rentang": ((30, 1), (45, 1), (65, 3))},
    "50310": {"jenis": "Renovasi", "rentang": ((30, 1), (45, 1), (65, 3))},
    "50401": {"jenis": "Overhaul", "rentang": ((30, 2), (45, 7), (65, 10))},
    "50402": {"jenis": "Overhaul", "rentang": ((30, 5), (45, 10), (65, 15))},
    "50403": {"jenis": "Overhaul", "rentang": ((30, 2), (45, 5), (65, 10))},
    "50404": {"jenis": "Overhaul", "rentang": ((30, 2), (45, 7), (65, 10))},
    # ── Golongan 6 — ATL & Aset Dalam Renovasi (referensi; penyusutan
    # golongan 6 mengikuti kebijakan aplikasi) ──
    "60201": {"jenis": "Overhaul", "rentang": ((25, 1), (50, 1), (75, 2), (100, 2))},
    "60702": {"jenis": "Overhaul", "rentang": ((100, 2),)},
    "60703": {"jenis": "Renovasi", "rentang": ((30, 5), (45, 10), (65, 15))},
    "60704": {"jenis": "Renovasi/Overhaul", "rentang": ((100, 5),)},
}

DASAR_HUKUM_PERBAIKAN = (
    "PMK 65/PMK.06/2017 Pasal 13 & 15 · KMK 295/KM.6/2019 Diktum KELIMA-"
    "KEENAM jo. KMK 266/KM.6/2023 jo. KMK 339/KM.6/2024"
)


def hitung_penambahan_masa_manfaat(kode_barang, biaya, nilai_dasar):
    """Tambahan masa manfaat akibat perbaikan → dict | None.

    None bila kelompok tidak terdaftar di Tabel II, nilai dasar tidak
    valid (<= 0), atau biaya <= 0. Persentase di atas batas tertinggi tabel
    dipagari ke rentang tertinggi (konservatif; perbaikan > nilai aset
    lazimnya diperlakukan sebagai perolehan baru — ditandai di keterangan).
    """
    kode = str(kode_barang or "").strip()
    entri = TABEL_MASA_MANFAAT_II.get(kode[:5])
    try:
        b = float(biaya)
        dasar = float(nilai_dasar)
    except (TypeError, ValueError):
        return None
    if not entri or dasar <= 0 or b <= 0:
        return None
    persen = b / dasar * 100.0
    rentang = entri["rentang"]
    tambah = None
    for batas, tahun in rentang:
        if persen <= batas:
            tambah = tahun
            break
    melebihi = tambah is None
    if melebihi:  # di atas rentang tertinggi tabel → pakai rentang tertinggi
        tambah = rentang[-1][1]
    return {
        "kelompok": kode[:5],
        "jenis": entri["jenis"],
        "persentase": round(persen, 2),
        "tambah_tahun": int(tambah),
        "melebihi_rentang": melebihi,
    }
