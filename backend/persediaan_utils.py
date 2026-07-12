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


# ── Transaksi persediaan (pustaka §3.2 — peta 1:1 ke jenis SAKTI) ──────
# Kunci enum internal → (label Indonesia, kode warisan aplikasi Persediaan)
JENIS_MASUK = {
    "saldo_awal": ("Saldo Awal", "M01"),
    "pembelian": ("Pembelian", "M02"),
    "transfer_masuk": ("Transfer Masuk", "M03"),
    "hibah_masuk": ("Hibah Masuk", "M04"),
    "perolehan_lainnya": ("Perolehan Lainnya", "M99"),
}


JENIS_KELUAR = {
    "habis_pakai": ("Habis Pakai/Pemakaian", "K01"),
    "transfer_keluar": ("Transfer Keluar", "K02"),
    "hibah_keluar": ("Hibah Keluar", "K03"),
    "usang": ("Usang", "K04"),
    "rusak": ("Rusak", "K05"),
}


def validate_transaksi_keluar(jenis: str, jumlah, stok_tersedia: int):
    """(ok, err) — jenis dikenal, jumlah bulat > 0 dan <= stok tersedia."""
    if jenis not in JENIS_KELUAR:
        valid = ", ".join(JENIS_KELUAR)
        return False, f"Jenis transaksi keluar tidak dikenal (pilihan: {valid})"
    try:
        j = int(jumlah)
    except (ValueError, TypeError):
        return False, "Jumlah harus bilangan bulat"
    if j <= 0:
        return False, "Jumlah harus lebih dari 0"
    if j > int(stok_tersedia or 0):
        return False, f"Stok tidak cukup — tersedia {int(stok_tersedia or 0)}"
    return True, ""


def konsumsi_fifo(batches, jumlah: int):
    """Konsumsi layer FIFO tertua dulu → (batches_sisa, total_nilai, rincian).

    - Layer diurutkan menaik berdasarkan `tanggal` (string ISO — urutan
      leksikografis = kronologis); layer qty<=0 dibuang.
    - Nilai keluar = Σ (qty terpakai × harga layer) — penilaian FIFO murni,
      BUKAN rata-rata (pustaka §3.1).
    - rincian: [{batch_id, qty, harga}] layer yang terpakai (jejak jurnal).
    - Stok kurang → ValueError (pemanggil sudah memvalidasi; ini pagar akhir).
    """
    sisa_butuh = int(jumlah)
    if sisa_butuh <= 0:
        raise ValueError("Jumlah keluar harus lebih dari 0")
    urut = sorted((dict(b) for b in (batches or []) if int(b.get("qty", 0) or 0) > 0),
                  key=lambda b: str(b.get("tanggal", "")))
    total_nilai = 0.0
    rincian = []
    batches_sisa = []
    for b in urut:
        qty = int(b.get("qty", 0) or 0)
        harga = float(b.get("harga", 0) or 0)
        if sisa_butuh <= 0:
            batches_sisa.append(b)
            continue
        ambil = min(qty, sisa_butuh)
        total_nilai += ambil * harga
        rincian.append({"batch_id": b.get("batch_id"), "qty": ambil, "harga": harga})
        sisa_butuh -= ambil
        if qty > ambil:
            b["qty"] = qty - ambil
            batches_sisa.append(b)
        # layer habis → tidak ikut sisa
    if sisa_butuh > 0:
        raise ValueError("Stok layer tidak mencukupi jumlah keluar")
    return batches_sisa, total_nilai, rincian


def validate_transaksi_masuk(jenis: str, jumlah, harga_satuan):
    """(ok, err) — jenis dikenal, jumlah bulat > 0, harga >= 0."""
    if jenis not in JENIS_MASUK:
        valid = ", ".join(JENIS_MASUK)
        return False, f"Jenis transaksi masuk tidak dikenal (pilihan: {valid})"
    try:
        j = int(jumlah)
    except (ValueError, TypeError):
        return False, "Jumlah harus bilangan bulat"
    if j <= 0:
        return False, "Jumlah harus lebih dari 0"
    try:
        h = float(harga_satuan)
    except (ValueError, TypeError):
        return False, "Harga satuan harus angka"
    if h != h or h in (float("inf"), float("-inf")) or h < 0:
        return False, "Harga satuan tidak boleh negatif"
    return True, ""


def validate_pindah_gudang(lokasi_lama, lokasi_baru):
    """(ok, err) — lokasi baru wajib terisi dan berbeda dari lokasi lama
    (perbandingan abaikan kapital & spasi tepi)."""
    baru = str(lokasi_baru or "").strip()
    if not baru:
        return False, "Lokasi/Gudang tujuan wajib diisi"
    if baru.casefold() == str(lokasi_lama or "").strip().casefold():
        return False, "Lokasi/Gudang tujuan sama dengan lokasi saat ini"
    return True, ""


def buat_layer(batch_id: str, tanggal_iso: str, jumlah: int, harga_satuan: float,
               expired: str = "", ref: str = "") -> dict:
    """Layer FIFO baru — bentuk baku yang dibaca stok/nilai_dari_batches."""
    return {
        "batch_id": batch_id,
        "tanggal": tanggal_iso,
        "qty": int(jumlah),
        "harga": float(harga_satuan),
        "expired": (expired or "").strip(),
        "ref": (ref or "").strip(),
    }


def parse_import_persediaan_rows(rows):
    """Normalisasi baris impor master persediaan → (entries, errors, dupes).

    Kolom dikenali (fleksibel): kode_barang/kode, nup, nama_barang/nama,
    merk, tipe, satuan, lokasi, batas_kritis, expired_default/kedaluwarsa,
    tahun_anggaran, keterangan. Kode wajib valid persediaan (10/16 digit
    berawalan '1'); nama wajib. batas_kritis non-angka → 0. Duplikat
    (kode 16 digit + nup) dalam file: baris terakhir menang; kode 10
    digit tidak dianggap duplikat (nomor urut dibuat saat insert).
    """
    def _s(row, *keys):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    entries = []
    by_identity = {}
    errors = []
    dupes = 0
    for i, row in enumerate(rows or [], start=2):  # baris 1 = header
        kode = _s(row, "kode_barang", "kode")
        if kode.endswith(".0"):
            kode = kode[:-2]
        nama = _s(row, "nama_barang", "nama")
        if not kode and not nama:
            continue  # baris kosong
        ok, err = validate_kode_persediaan(kode)
        if not ok:
            errors.append(f"Baris {i}: {err}")
            continue
        if not nama:
            errors.append(f"Baris {i}: nama barang kosong untuk kode {kode}")
            continue
        nup = _s(row, "nup")
        if nup.endswith(".0"):
            nup = nup[:-2]
        try:
            batas = max(0, int(float(_s(row, "batas_kritis") or 0)))
        except (ValueError, TypeError):
            batas = 0
        entry = {
            "kode_barang": kode,
            "nup": nup,
            "nama_barang": nama,
            "merk": _s(row, "merk"),
            "tipe": _s(row, "tipe"),
            "satuan": _s(row, "satuan") or "Buah",
            "lokasi": _s(row, "lokasi"),
            "batas_kritis": batas,
            "expired_default": _s(row, "expired_default", "kedaluwarsa")[:10],
            "tahun_anggaran": _s(row, "tahun_anggaran")[:4],
            "keterangan": _s(row, "keterangan"),
        }
        if len(kode) == KODE_PENUH_LEN and nup:
            key = (kode, nup)
            if key in by_identity:
                dupes += 1
                entries[by_identity[key]] = entry  # baris terakhir menang
                continue
            by_identity[key] = len(entries)
        entries.append(entry)
    return entries, errors, dupes


def penyesuaian_opname(batches, stok_fisik: int, batch_id_baru: str, tanggal_iso: str):
    """Setel layer agar total qty = stok_fisik → (batches_baru, detail).

    - fisik < buku  → kekurangan dikonsumsi FIFO (layer tertua dulu);
      detail {"arah": "keluar", "jumlah", "nilai", "rincian"}.
    - fisik > buku  → kelebihan jadi LAYER PENYESUAIAN baru dengan harga
      layer TERMUDA yang ada (pendekatan konservatif; 0 bila tanpa layer);
      detail {"arah": "masuk", "jumlah", "nilai", "harga"}.
    - fisik == buku → ValueError (tidak ada selisih untuk disesuaikan).
    stok_fisik < 0 → ValueError. Fungsi murni — batch_id & tanggal dipasok.
    """
    fisik = int(stok_fisik)
    if fisik < 0:
        raise ValueError("Stok fisik tidak boleh negatif")
    buku = stok_dari_batches(batches)
    if fisik == buku:
        raise ValueError("Tidak ada selisih — stok fisik sama dengan buku")
    if fisik < buku:
        sisa, nilai, rincian = konsumsi_fifo(batches, buku - fisik)
        return sisa, {"arah": "keluar", "jumlah": buku - fisik,
                      "nilai": nilai, "rincian": rincian}
    # fisik > buku — harga layer termuda (tanggal terbesar) sebagai acuan
    urut = sorted((b for b in (batches or []) if int(b.get("qty", 0) or 0) > 0),
                  key=lambda b: str(b.get("tanggal", "")))
    harga = float(urut[-1].get("harga", 0) or 0) if urut else 0.0
    tambah = fisik - buku
    layer = buat_layer(batch_id_baru, tanggal_iso, tambah, harga, "", "OPNAME")
    return list(batches or []) + [layer], {
        "arah": "masuk", "jumlah": tambah, "nilai": tambah * harga, "harga": harga,
    }


def mutasi_periode(jurnal_rows, dari_iso: str, sampai_iso: str):
    """Rekap mutasi per barang dari JURNAL → {persediaan_id: rekap}.

    Rekap: saldo_awal (Σ masuk−keluar sebelum `dari`), masuk_qty/nilai &
    keluar_qty/nilai dalam periode [dari..sampai] inklusif, saldo_akhir =
    awal + masuk − keluar. Semua dari jurnal nyata — tidak menyentuh master.
    Batas tanggal 'YYYY-MM-DD'; timestamp jurnal ISO (perbandingan prefix
    10 karakter = kronologis). Baris tanpa persediaan_id diabaikan.
    """
    dari = (dari_iso or "")[:10]
    sampai = (sampai_iso or "")[:10]
    rekap = {}
    for r in jurnal_rows or []:
        pid = r.get("persediaan_id")
        if not pid:
            continue
        tgl = str(r.get("timestamp") or "")[:10]
        arah = r.get("arah")
        try:
            qty = int(r.get("jumlah", 0) or 0)
            nilai = float(r.get("total", 0) or 0)
        except (ValueError, TypeError):
            continue
        e = rekap.setdefault(pid, {
            "persediaan_id": pid,
            "kode_barang": r.get("kode_barang"),
            "nup": r.get("nup"),
            "nama_barang": r.get("nama_barang"),
            "saldo_awal": 0,
            "masuk_qty": 0, "masuk_nilai": 0.0,
            "keluar_qty": 0, "keluar_nilai": 0.0,
        })
        if arah not in ("masuk", "keluar"):
            continue  # mutasi lokasi (pindah gudang) tidak mengubah saldo
        if tgl < dari:
            e["saldo_awal"] += qty if arah == "masuk" else -qty
        elif tgl <= sampai:
            if arah == "masuk":
                e["masuk_qty"] += qty
                e["masuk_nilai"] += nilai
            else:
                e["keluar_qty"] += qty
                e["keluar_nilai"] += nilai
        # transaksi setelah `sampai` diabaikan (laporan periode)
    for e in rekap.values():
        e["saldo_akhir"] = e["saldo_awal"] + e["masuk_qty"] - e["keluar_qty"]
    return rekap


def klasifikasi_kedaluwarsa(batches, today_iso: str, horizon_hari: int = 30):
    """Pilah layer ber-kedaluwarsa → (lewat, segera) relatif `today_iso`.

    today_iso 'YYYY-MM-DD' dipasok pemanggil — fungsi tetap deterministik/
    murni. `lewat` = expired <= hari ini; `segera` = expired dalam
    `horizon_hari` ke depan. Layer tanpa expired / qty 0 / tanggal rusak
    diabaikan.
    """
    from datetime import date

    try:
        today = date.fromisoformat((today_iso or "")[:10])
    except ValueError:
        return [], []
    lewat, segera = [], []
    for b in batches or []:
        exp_raw = str(b.get("expired") or "").strip()[:10]
        if not exp_raw:
            continue
        try:
            exp = date.fromisoformat(exp_raw)
        except ValueError:
            continue
        qty = int(b.get("qty", 0) or 0)
        if qty <= 0:
            continue
        info = {"batch_id": b.get("batch_id"), "qty": qty,
                "harga": float(b.get("harga", 0) or 0), "expired": exp_raw}
        if exp <= today:
            lewat.append(info)
        elif (exp - today).days <= int(horizon_hari):
            segera.append(info)
    return lewat, segera


def status_opname_semester(tanggal_opname_terakhir, today_iso: str) -> dict:
    """Status opname fisik pada semester berjalan (pustaka §3.3).

    Opname wajib tiap semester; `tanggal_opname_terakhir` = tanggal
    transaksi opname terbaru (ISO, boleh None). Hasil: {sudah, label,
    terakhir, pesan} — pesan kosong bila semester ini sudah diopname.
    """
    from datetime import date

    try:
        today = date.fromisoformat((today_iso or "")[:10])
    except ValueError:
        return {"sudah": False, "label": "", "terakhir": "", "pesan": ""}
    sem = 1 if today.month <= 6 else 2
    label = f"Semester {'I' if sem == 1 else 'II'} {today.year}"
    awal = date(today.year, 1 if sem == 1 else 7, 1)
    terakhir = str(tanggal_opname_terakhir or "").strip()[:10]
    try:
        sudah = bool(terakhir) and date.fromisoformat(terakhir) >= awal
    except ValueError:
        sudah = False
    pesan = "" if sudah else (
        f"Belum ada opname fisik pada {label}"
        + (f" — opname terakhir {terakhir}" if terakhir else
           " — belum pernah ada opname tercatat")
        + ". Jadwalkan opname semesteran (PSAP 05 / praktik SAKTI).")
    return {"sudah": sudah, "label": label, "terakhir": terakhir,
            "pesan": pesan}


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
