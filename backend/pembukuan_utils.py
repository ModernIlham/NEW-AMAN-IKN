"""Logika murni PEMBUKUAN BMN (modul Penatausahaan › Pembukuan).

Dasar: PMK 181/PMK.06/2016 + rangkuman riset di
docs/PUSTAKA-REGULASI-BMN.md §2.1 — pembukuan memilah barang menjadi
INTRAKOMPTABEL (masuk neraca) vs EKSTRAKOMPTABEL (dibukukan, tidak masuk
neraca) berdasarkan NILAI SATUAN MINIMUM KAPITALISASI per golongan:

    Golongan 3 (Peralatan & Mesin)   ≥ Rp1.000.000  → intra
    Golongan 4 (Gedung & Bangunan)   ≥ Rp25.000.000 → intra
    Golongan lain (tanah, jalan, dst) → selalu intra (tanpa ambang)

Ambang dibuat PARAMETER (dict) — nilai bisa berubah oleh aturan baru;
default mengikuti PMK 181. Golongan barang diturunkan dari digit pertama
kode barang (selaras kodefikasi_utils).

Berisi fungsi murni saja (tanpa Mongo/IO) agar teruji unit tanpa
infrastruktur — endpoint DBKP di routes/reports.py memakai fungsi ini.
"""

# Ambang kapitalisasi default (PMK 181/PMK.06/2016) per digit golongan.
# Golongan yang tidak terdaftar = tanpa ambang (selalu intrakomptabel).
AMBANG_KAPITALISASI_DEFAULT = {
    "3": 1_000_000,    # Peralatan dan Mesin
    "4": 25_000_000,   # Gedung dan Bangunan
}


def parse_harga(value) -> float:
    """Harga dari string/angka toleran format Indonesia ('Rp1.234.567,89').

    Kembalikan 0.0 bila tidak bisa diparse — barang tanpa harga dibukukan
    bernilai nol (tetap masuk daftar, mengikuti perlakuan kuantitas).
    """
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        try:
            f = float(value)
        except (ValueError, OverflowError):
            return 0.0
        return f if f == f and f not in (float("inf"), float("-inf")) else 0.0
    s = str(value).strip().replace("Rp", "").replace(" ", "")
    if not s:
        return 0.0
    # Format ID: titik = pemisah ribuan, koma = desimal
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def golongan_of(kode_barang) -> str:
    """Digit pertama kode barang = golongan; '' bila kosong/bukan digit."""
    s = str(kode_barang or "").strip()
    return s[0] if s and s[0].isdigit() else ""


def klasifikasi_komptabel(kode_barang, harga_satuan, ambang=None) -> str:
    """'intra' | 'ekstra' menurut ambang kapitalisasi golongan barang.

    Barang tanpa golongan dikenali ('' ) tetap 'intra' agar tidak hilang
    dari neraca hanya karena kodenya belum rapi — kualitas kode ditagih
    lewat dashboard kesehatan data, bukan dengan menyembunyikan barang.
    """
    peta = AMBANG_KAPITALISASI_DEFAULT if ambang is None else ambang
    batas = peta.get(golongan_of(kode_barang))
    if not batas:
        return "intra"
    return "intra" if parse_harga(harga_satuan) >= batas else "ekstra"


def nilai_buku_aset(a):
    """Nilai buku TERKINI aset untuk laporan POSISI/NILAI (DBKP, Posisi BMN di
    Neraca, rekonsiliasi): nilai wajar hasil revaluasi (`nilai_wajar_terakhir`,
    proyeksi #254) BILA ADA, jika tidak nilai perolehan (`purchase_price`).

    `nilai_wajar_terakhir` BOLEH bernilai 0 (aset direvaluasi ke nol) → dibedakan
    dari 'tidak pernah direvaluasi' lewat `is not None`, bukan truthiness.
    SENGAJA tidak dipakai di laporan MUTASI (LBKP/CaLBMN — di sana revaluasi
    adalah jenis mutasi tersendiri) maupun dasar penyusutan (langkah terpisah).
    """
    nw = a.get("nilai_wajar_terakhir")
    if nw is not None:
        return parse_harga(nw)
    return parse_harga(a.get("purchase_price"))


def build_dbkp_rows(assets, uraian_map=None, ambang=None):
    """Rekap DBKP per golongan dari daftar aset → (rows, total).

    assets: iterable dict minimal {asset_code, purchase_price}.
    uraian_map: {digit_golongan: uraian} (dari koleksi kodefikasi; fallback
    pemanggil). Baris = per golongan terurut naik; kolom jumlah & nilai
    untuk intra, ekstra, dan gabungan. Barang tanpa golongan dikelompokkan
    ke '?' (uraian 'Tanpa Golongan (kode belum rapi)') agar terlihat dan
    dibereskan — bukan disembunyikan.
    """
    uraian_map = uraian_map or {}
    agg = {}
    for a in assets or []:
        gol = golongan_of(a.get("asset_code")) or "?"
        # Nilai buku terkini: pakai nilai wajar revaluasi bila ada (#254),
        # jika tidak nilai perolehan. Ini juga menentukan ambang intra/ekstra.
        harga = nilai_buku_aset(a)
        kelas = klasifikasi_komptabel(a.get("asset_code"), harga, ambang)
        row = agg.setdefault(gol, {
            "golongan": gol,
            "uraian": uraian_map.get(gol) or (
                "Tanpa Golongan (kode belum rapi)" if gol == "?" else f"Golongan {gol}"),
            "jumlah_intra": 0, "nilai_intra": 0.0,
            "jumlah_ekstra": 0, "nilai_ekstra": 0.0,
        })
        if kelas == "intra":
            row["jumlah_intra"] += 1
            row["nilai_intra"] += harga
        else:
            row["jumlah_ekstra"] += 1
            row["nilai_ekstra"] += harga

    rows = []
    for gol in sorted(agg, key=lambda g: (g == "?", g)):
        r = agg[gol]
        r["jumlah_total"] = r["jumlah_intra"] + r["jumlah_ekstra"]
        r["nilai_total"] = r["nilai_intra"] + r["nilai_ekstra"]
        rows.append(r)

    total = {
        "jumlah_intra": sum(r["jumlah_intra"] for r in rows),
        "nilai_intra": sum(r["nilai_intra"] for r in rows),
        "jumlah_ekstra": sum(r["jumlah_ekstra"] for r in rows),
        "nilai_ekstra": sum(r["nilai_ekstra"] for r in rows),
        "jumlah_total": sum(r["jumlah_total"] for r in rows),
        "nilai_total": sum(r["nilai_total"] for r in rows),
    }
    return rows, total


_KOLOM_LBKP = ("jumlah_awal", "nilai_awal", "jumlah_tambah", "nilai_tambah",
               "jumlah_kurang", "nilai_kurang", "jumlah_akhir", "nilai_akhir")


def _baris_lbkp_kosong(gol, uraian_map):
    uraian_map = uraian_map or {}
    return {
        "golongan": gol,
        "uraian": uraian_map.get(gol) or (
            "Tanpa Golongan (kode belum rapi)" if gol == "?" else f"Golongan {gol}"),
        **{k: (0.0 if k.startswith("nilai") else 0) for k in _KOLOM_LBKP},
    }


def tombstones_penghapusan(assets, ambang=None):
    """Bangun 'tombstone' mutasi KURANG dari aset yang dihapus via SK penghapusan
    (proyeksi master #234: `dihapus=True` + `penghapusan.tanggal_sk`). Bentuknya
    sama dengan tombstone hard-delete audit — {asset_code, timestamp, nilai} —
    agar build_lbkp_rows menghitungnya sebagai mutasi kurang di periode SK terbit.

    `timestamp` = tanggal SK; `nilai` = harga perolehan; `kelas_komptabel` =
    kelas aset SEMASA HIDUP (dari harga perolehan yang sama dengan saat aset
    dihitung di saldo awal/tambah) agar mutasi kurang jatuh di seksi yang sama
    walau nilainya 0 (#63). Aset tanpa tanggal SK dilewati (tak bisa
    ditempatkan pada periode mana pun). Melengkapi audit hard-delete sehingga
    laporan MUTASI (LBKP/CaLBMN) juga mencerminkan penghapusan lewat SK —
    bukan hanya penghapusan permanen.
    """
    out = []
    for a in assets or []:
        if not a.get("dihapus"):
            continue
        sk = str((a.get("penghapusan") or {}).get("tanggal_sk") or "")[:10]
        if not sk:
            continue
        out.append({
            "asset_code": a.get("asset_code"),
            "timestamp": sk,
            "nilai": a.get("purchase_price"),
            "kelas_komptabel": klasifikasi_komptabel(
                a.get("asset_code"), a.get("purchase_price"), ambang),
        })
    return out


def build_lbkp_rows(assets, tombstones, dari, sampai, uraian_map=None, ambang=None):
    """LBKP per golongan: saldo awal + mutasi tambah/kurang + saldo akhir.

    assets: aset HIDUP {asset_code, purchase_price, created_at}.
    tombstones: jejak penghapusan {asset_code, timestamp, nilai} — nilai
    0.0 bila audit lama belum merekam harga; opsional `kelas_komptabel`
    ("intra"/"ekstra") bila kelas semasa hidup diketahui.
    dari/sampai: ISO YYYY-MM-DD inklusif.

    Kembalikan (per_kelas, n_kurang_tanpa_nilai) dengan per_kelas =
    {"intra"|"ekstra"|"gabungan": (rows, total)}; tiap baris memuat kolom
    awal/tambah/kurang/akhir (jumlah & nilai). Saldo akhir = awal + tambah
    − kurang (identitas mutasi). Mutasi kurang TANPA nilai terekam DAN tanpa
    kelas terekam tidak ditebak seksinya (nilai 0 akan selalu jatuh 'ekstra'
    padahal semasa hidup bisa intra, #63) — dihitung pada seksi GABUNGAN
    saja, sehingga Gabungan bisa berbeda dari I+II sebesar penghapusan itu.
    Keterbatasan yang HARUS dicatat pemanggil: aset yang dibuat lalu dihapus
    sebelum `dari` tak dapat direkonstruksi (tombstone tanpa tanggal
    perolehan), dan penghapusan lama tanpa nilai terekam dihitung jumlahnya
    dengan nilai 0.
    """
    agg = {"intra": {}, "ekstra": {}}

    def _baris(kelas, gol):
        return agg[kelas].setdefault(gol, _baris_lbkp_kosong(gol, uraian_map))

    for a in assets or []:
        tanggal = str(a.get("created_at") or "")[:10]
        if not tanggal or tanggal > sampai:
            continue
        # Aset DIHAPUS via SK penghapusan (proyeksi #234) yang SK-nya terbit
        # SEBELUM `dari` sudah tak ada di saldo awal periode ini — lewati
        # (setara aset yang lenyap sebelum periode). Bila SK >= dari, aset MASIH
        # hidup di awal periode → tetap dihitung saldo awal/tambah, lalu dikurangi
        # oleh tombstone penghapusan (tombstones_penghapusan) di periode SK-nya
        # sehingga identitas mutasi (akhir = awal + tambah − kurang) tetap seimbang.
        if a.get("dihapus"):
            sk_hapus = str((a.get("penghapusan") or {}).get("tanggal_sk") or "")[:10]
            if sk_hapus and sk_hapus < dari:
                continue
        gol = golongan_of(a.get("asset_code")) or "?"
        harga = parse_harga(a.get("purchase_price"))
        kelas = klasifikasi_komptabel(a.get("asset_code"), harga, ambang)
        row = _baris(kelas, gol)
        if tanggal < dari:
            row["jumlah_awal"] += 1
            row["nilai_awal"] += harga
        else:
            row["jumlah_tambah"] += 1
            row["nilai_tambah"] += harga

    n_tanpa_nilai = 0
    tanpa_kelas = {}  # kurang yang seksinya tak diketahui → Gabungan saja (#63)
    for t in tombstones or []:
        tanggal = str(t.get("timestamp") or "")[:10]
        if not (dari <= tanggal <= sampai):
            continue
        gol = golongan_of(t.get("asset_code")) or "?"
        nilai = parse_harga(t.get("nilai"))
        if nilai <= 0:
            n_tanpa_nilai += 1
        kelas = str(t.get("kelas_komptabel") or "").strip()
        if kelas not in ("intra", "ekstra"):
            kelas = (klasifikasi_komptabel(t.get("asset_code"), nilai, ambang)
                     if nilai > 0 else "")
        row = (_baris(kelas, gol) if kelas
               else tanpa_kelas.setdefault(gol, _baris_lbkp_kosong(gol, uraian_map)))
        row["jumlah_kurang"] += 1
        row["nilai_kurang"] += nilai

    def _tutup(peta):
        rows = []
        for gol in sorted(peta, key=lambda g: (g == "?", g)):
            r = peta[gol]
            r["jumlah_akhir"] = r["jumlah_awal"] + r["jumlah_tambah"] - r["jumlah_kurang"]
            r["nilai_akhir"] = r["nilai_awal"] + r["nilai_tambah"] - r["nilai_kurang"]
            rows.append(r)
        total = {k: sum(r[k] for r in rows) for k in _KOLOM_LBKP}
        return rows, total

    gabungan = {}
    for peta in (agg["intra"], agg["ekstra"], tanpa_kelas):
        for gol, r in peta.items():
            g = gabungan.setdefault(gol, _baris_lbkp_kosong(gol, uraian_map))
            for k in _KOLOM_LBKP[:6]:  # akhir dihitung ulang di _tutup
                g[k] += r[k]
    per_kelas = {
        "intra": _tutup(agg["intra"]),
        "ekstra": _tutup(agg["ekstra"]),
        "gabungan": _tutup(gabungan),
    }
    return per_kelas, n_tanpa_nilai


def posisi_neraca(rows, total, persediaan_jumlah=0, persediaan_nilai=0.0):
    """Gabungkan rekap aset tetap + persediaan → Posisi BMN di Neraca.

    Komponen LBKP (pustaka §2.3). Persediaan adalah aset lancar (akun
    1171xx) — selalu intrakomptabel tanpa ambang; jumlahnya dihitung per
    JENIS barang (bukan per unit stok) agar sebanding dengan kolom NUP.
    Posisi lengkap (KDP, ATB, penyusutan) menyusul bertahap.
    """
    p_jumlah = int(persediaan_jumlah or 0)
    p_nilai = float(persediaan_nilai or 0.0)
    grand = {
        "jumlah_intra": total["jumlah_intra"] + p_jumlah,
        "nilai_intra": total["nilai_intra"] + p_nilai,
        "jumlah_ekstra": total["jumlah_ekstra"],
        "nilai_ekstra": total["nilai_ekstra"],
        "jumlah_total": total["jumlah_total"] + p_jumlah,
        "nilai_total": total["nilai_total"] + p_nilai,
    }
    return {
        "aset": rows,
        "total_aset": total,
        "persediaan": {"jumlah": p_jumlah, "nilai": p_nilai},
        "total": grand,
    }


# Kondisi resmi barang (SIMAK-BMN): Baik / Rusak Ringan / Rusak Berat.
KONDISI_LKB = ("Baik", "Rusak Ringan", "Rusak Berat")


def build_lkb_rows(assets, uraian_map=None):
    """Rekap Laporan Kondisi Barang per golongan → (rows, total).

    assets: iterable dict minimal {asset_code, condition, purchase_price}.
    Kolom per baris: kuantitas Baik / Rusak Ringan / Rusak Berat /
    belum dicatat + total + nilai perolehan. Kondisi di luar tiga
    kategori resmi dihitung 'belum' agar ditagih dibereskan — tidak
    pernah ditebak.
    """
    uraian_map = uraian_map or {}
    agg = {}
    for a in assets or []:
        gol = golongan_of(a.get("asset_code")) or "?"
        row = agg.setdefault(gol, {
            "golongan": gol,
            "uraian": uraian_map.get(gol) or (
                "Tanpa Golongan (kode belum rapi)" if gol == "?" else f"Golongan {gol}"),
            "baik": 0, "rusak_ringan": 0, "rusak_berat": 0, "belum": 0,
            "jumlah": 0, "nilai": 0.0,
        })
        kondisi = str(a.get("condition") or "").strip()
        if kondisi == "Baik":
            row["baik"] += 1
        elif kondisi == "Rusak Ringan":
            row["rusak_ringan"] += 1
        elif kondisi == "Rusak Berat":
            row["rusak_berat"] += 1
        else:
            row["belum"] += 1
        row["jumlah"] += 1
        row["nilai"] += parse_harga(a.get("purchase_price"))

    rows = [agg[g] for g in sorted(agg, key=lambda g: (g == "?", g))]
    total = {k: sum(r[k] for r in rows)
             for k in ("baik", "rusak_ringan", "rusak_berat", "belum", "jumlah")}
    total["nilai"] = sum(r["nilai"] for r in rows)
    return rows, total
