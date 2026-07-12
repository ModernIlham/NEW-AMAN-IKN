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
        harga = parse_harga(a.get("purchase_price"))
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
