"""Logika murni PERSEDIAAN (modul Penatausahaan › Inventarisasi Persediaan).

Dasar: docs/PUSTAKA-REGULASI-BMN.md §3 — pencatatan PERPETUAL + penilaian
FIFO per layer (kebijakan akuntansi pemerintah pusat sejak TA 2021, pola
SAKTI), dan referensi teknis modul persediaan KERJA-BARENG.

Ketentuan kode barang persediaan:
- WAJIB berawalan '1' (golongan Persediaan — digit pertama kodefikasi).
- Panjang penuh 16 digit: 10 digit kodefikasi (sampai sub-sub kelompok)
  + 6 digit nomor urut barang. Input 10 digit → 6 digit terakhir
  di-generate otomatis (increment dari yang terbesar se-prefix).

Berisi fungsi murni saja (tanpa Mongo/IO) — route memakai fungsi ini.
"""

KODE_PENUH_LEN = 16
KODE_PREFIX_LEN = 10
SUFFIX_LEN = KODE_PENUH_LEN - KODE_PREFIX_LEN

SATUAN_BAKU = (
    "Buah", "Unit", "Set", "Paket", "Lembar", "Rim", "Box", "Botol",
    "Liter", "Kilogram", "Meter", "Roll", "Lusin", "Tube", "Eksemplar",
)


def validate_kode_persediaan(kode: str):
    """(ok, err) — kode persediaan harus angka, berawalan '1', 10/16 digit."""
    s = str(kode or "").strip()
    if not s:
        return False, "Kode barang kosong"
    if not s.isdigit():
        return False, f"Kode '{s}' harus angka semua"
    if s[0] != "1":
        return False, "Kode barang persediaan harus berawalan '1' (golongan Persediaan)"
    if len(s) not in (KODE_PREFIX_LEN, KODE_PENUH_LEN):
        return False, (f"Panjang kode harus {KODE_PREFIX_LEN} digit (nomor urut dibuat "
                       f"otomatis) atau {KODE_PENUH_LEN} digit penuh")
    return True, ""


def next_kode_penuh(prefix10: str, kode_max_seprefix: str | None):
    """Kode 16 digit berikutnya untuk prefix 10 digit.

    kode_max_seprefix: kode 16 digit TERBESAR yang sudah ada dengan prefix
    sama (None bila belum ada). Suffix mentok 999999 → ValueError (pemanggil
    mengubah jadi HTTP 409).
    """
    if not kode_max_seprefix or len(kode_max_seprefix) != KODE_PENUH_LEN:
        return f"{prefix10}{1:0{SUFFIX_LEN}d}"
    try:
        seq = int(kode_max_seprefix[-SUFFIX_LEN:]) + 1
    except ValueError:
        return f"{prefix10}{1:0{SUFFIX_LEN}d}"
    if seq > 10 ** SUFFIX_LEN - 1:
        raise ValueError(f"Nomor urut untuk prefix {prefix10} sudah penuh")
    return f"{prefix10}{seq:0{SUFFIX_LEN}d}"


def next_nup(nup_max: str | None):
    """NUP berikutnya (angka string, mulai '1'); toleran nilai lama kotor."""
    try:
        return str(int(str(nup_max).strip()) + 1)
    except (ValueError, TypeError, AttributeError):
        return "1"


def stok_dari_batches(batches) -> int:
    """Stok = jumlah qty seluruh layer FIFO — satu-satunya sumber kebenaran.

    Field `stok` di master hanyalah cache dari nilai ini; setiap tulis
    transaksi wajib menyetel keduanya konsisten.
    """
    total = 0
    for b in batches or []:
        try:
            q = int(b.get("qty", 0) or 0)
        except (ValueError, TypeError):
            q = 0
        total += max(0, q)
    return total


def nilai_persediaan_dari_batches(batches) -> float:
    """Nilai persediaan = Σ (qty × harga layer) — penilaian FIFO per layer."""
    total = 0.0
    for b in batches or []:
        try:
            q = int(b.get("qty", 0) or 0)
            h = float(b.get("harga", 0) or 0)
        except (ValueError, TypeError):
            continue
        if q > 0 and h == h and h not in (float("inf"), float("-inf")):
            total += q * h
    return total


def status_stok(stok: int, batas_kritis) -> str:
    """'habis' | 'kritis' | 'aman' — untuk peringatan & nota dinas kelak."""
    try:
        batas = int(batas_kritis or 0)
    except (ValueError, TypeError):
        batas = 0
    if stok <= 0:
        return "habis"
    if batas > 0 and stok <= batas:
        return "kritis"
    return "aman"
