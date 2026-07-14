"""Logika murni kodefikasi barang BMN — SATU sumber kebenaran struktur kode.

Kodefikasi 5 level diturunkan dari PANJANG PREFIX kode barang (pola yang
sama dipakai sistem referensi KERJA-BARENG dan selaras penggolongan BMN):

    Level 1  Golongan            1 digit   (mis. "3")
    Level 2  Bidang              3 digit   (mis. "301")
    Level 3  Kelompok            5 digit   (mis. "30102")
    Level 4  Sub Kelompok        7 digit   (mis. "3010203")
    Level 5  Sub-sub Kelompok   10 digit   (mis. "3010203001")

Digit pertama memisahkan domain: '1' = Persediaan (aset lancar),
'2'-'8' = Aset Tetap/Lainnya. Modul aset menolak kode berawalan '1';
modul persediaan justru mewajibkannya.

Berisi fungsi murni saja (tanpa Mongo/IO) supaya dapat diuji unit tanpa
infrastruktur — route memakai fungsi-fungsi ini untuk validasi & impor.
"""

# Panjang prefix per level — urutan menentukan derivasi level & hierarki.
LEVEL_LENGTHS = {1: 1, 2: 3, 3: 5, 4: 7, 5: 10}
LENGTH_TO_LEVEL = {v: k for k, v in LEVEL_LENGTHS.items()}

LEVEL_LABELS = {
    1: "Golongan",
    2: "Bidang",
    3: "Kelompok",
    4: "Sub Kelompok",
    5: "Sub-sub Kelompok",
}

# Golongan standar BMN (digit pertama kode) — seed idempoten koleksi kosong.
GOLONGAN_DEFAULTS = (
    ("1", "Persediaan"),
    ("2", "Tanah"),
    ("3", "Peralatan dan Mesin"),
    ("4", "Gedung dan Bangunan"),
    ("5", "Jalan, Irigasi, dan Jaringan"),
    ("6", "Aset Tetap Lainnya"),
    ("7", "Konstruksi Dalam Pengerjaan"),
    ("8", "Aset Tak Berwujud"),
)


def normalize_kode(value) -> str:
    """Rapikan kode dari input/impor: buang spasi & artefak float Excel (.0)."""
    s = str(value if value is not None else "").strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def derive_level(kode: str):
    """Level (1-5) dari panjang kode; None bila panjang tidak dikenal."""
    return LENGTH_TO_LEVEL.get(len(kode or ""))


def validate_kode(kode: str):
    """(ok, pesan_error). Kode wajib numerik dan panjangnya salah satu level."""
    if not kode:
        return False, "Kode kosong"
    if not kode.isdigit():
        return False, f"Kode '{kode}' harus angka semua"
    if derive_level(kode) is None:
        valid = "/".join(str(n) for n in LEVEL_LENGTHS.values())
        return False, f"Panjang kode '{kode}' harus {valid} digit (level 1-5)"
    return True, ""


def parent_of(kode: str):
    """Kode induk (prefix level di atasnya); None untuk level 1 / kode invalid."""
    level = derive_level(kode)
    if not level or level == 1:
        return None
    return kode[: LEVEL_LENGTHS[level - 1]]


def hierarchy_prefixes(kode: str):
    """Daftar (level, prefix) dari golongan sampai level kode itu sendiri.

    Untuk lookup uraian berjenjang: "3" → "301" → "30102" → … Hanya level
    yang prefix-nya muat dalam kode yang dikembalikan.
    """
    out = []
    for level, length in LEVEL_LENGTHS.items():
        if len(kode or "") >= length:
            out.append((level, kode[:length]))
    return out


def level_terdaftar_terdalam(kode, terdaftar) -> int:
    """Level TERDALAM (1-5) yang prefix kode-nya ada di referensi kodefikasi;
    0 bila tak satu pun (bahkan golongan level 1) terdaftar (§5A gap #7 —
    kodefikasi sebagai FK tervalidasi, Prinsip 2).

    `terdaftar` = himpunan (`set`) kode kodefikasi yang terdaftar. Memakai
    `hierarchy_prefixes` sehingga kode "3050104001" dicek berjenjang: "3" →
    "301" → "30105"? … dst. Fungsi murni — pemanggil menyiapkan himpunan.
    """
    deepest = 0
    for level, prefix in hierarchy_prefixes(normalize_kode(kode)):
        if prefix in terdaftar:
            deepest = level          # level menaik → yang terakhir cocok = terdalam
    return deepest


def is_persediaan_kode(kode: str) -> bool:
    """Domain persediaan = digit pertama '1' (aset lancar)."""
    return bool(kode) and kode[0] == "1"


def parse_import_rows(rows):
    """Normalisasi baris impor kodefikasi → (entries, errors).

    rows: iterable of dict dengan kunci fleksibel ('kode'/'kode_barang',
    'uraian'/'nama'). Level TIDAK dibaca dari file — selalu diturunkan dari
    panjang kode agar tidak bisa saling bertentangan. Duplikat kode dalam
    file: baris terakhir menang (dilaporkan sebagai catatan, bukan error).
    """
    entries = {}
    errors = []
    dupes = 0
    for i, row in enumerate(rows, start=2):  # baris 1 = header
        kode = normalize_kode(row.get("kode") or row.get("kode_barang"))
        uraian = str(row.get("uraian") or row.get("nama") or "").strip()
        if not kode and not uraian:
            continue  # baris kosong
        ok, err = validate_kode(kode)
        if not ok:
            errors.append(f"Baris {i}: {err}")
            continue
        if not uraian:
            errors.append(f"Baris {i}: uraian kosong untuk kode {kode}")
            continue
        if kode in entries:
            dupes += 1
        entries[kode] = {
            "kode": kode,
            "uraian": uraian,
            "level": derive_level(kode),
            "parent_kode": parent_of(kode),
        }
    return list(entries.values()), errors, dupes
