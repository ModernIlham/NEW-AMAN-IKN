"""Logika murni PEMELIHARAAN (Fase 3 — tahap awal: riwayat + biaya per aset).

Dasar: PP 27/2014 Pasal 46-47 — Pengguna/Kuasa Pengguna Barang bertanggung
jawab atas pemeliharaan BMN dan wajib membuat Daftar Hasil Pemeliharaan
Barang (DHPB) yang dilaporkan secara berkala. Modul ini mencatat setiap
kejadian pemeliharaan per aset (tanggal, jenis, uraian, biaya, pelaksana,
bukti) sehingga riwayat + rekap biaya per tahun anggaran tersedia sebagai
bahan DHPB dan umpan balik RKBMN pemeliharaan (masterplan Fase 4).

Catatan kapitalisasi: pemeliharaan yang hanya mempertahankan fungsi normal
dicatat sebagai beban (akun 523xxx); pengeluaran yang menambah masa
manfaat/kapasitas DAN melampaui nilai satuan minimum kapitalisasi
(PMK 181/PMK.06/2016: peralatan-mesin ≥ Rp1 jt, gedung-bangunan ≥ Rp25 jt;
PSAP 07 par. 50-51) seharusnya menambah nilai aset (belanja modal 53xxxx /
"Pengembangan Nilai Aset" SAKTI) — modul ini baru MENANDAI indikasinya,
penyesuaian nilai aset menyusul di tahap Pembukuan lanjutan.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pembukuan_utils import AMBANG_KAPITALISASI_DEFAULT

# Kunci jenis → label Indonesia (klasifikasi baku bahan ajar DJKN/KLC:
# ringan = harian oleh pemakai tanpa membebani anggaran; sedang = berkala
# oleh tenaga terdidik; berat = sewaktu-waktu oleh tenaga ahli).
JENIS_PEMELIHARAAN = {
    "ringan": "Pemeliharaan ringan (harian oleh pemakai)",
    "sedang": "Pemeliharaan sedang (berkala)",
    "berat": "Pemeliharaan berat (tenaga ahli)",
}

# Kondisi aset setelah pemeliharaan (selaras shared_utils.VALID_CONDITIONS;
# string kosong = tidak mengubah kondisi aset).
KONDISI_SETELAH_VALID = ("", "Baik", "Rusak Ringan", "Rusak Berat")


def _parse_tanggal(v):
    """ISO YYYY-MM-DD → date, atau None bila tidak valid."""
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def parse_biaya(v):
    """Biaya → float ≥ 0, atau None bila tidak valid.

    Kosong/None dianggap 0 (pemeliharaan swakelola tanpa biaya tercatat).
    """
    if v is None or str(v).strip() == "":
        return 0.0
    try:
        n = float(str(v).replace(",", ".").strip())
    except (ValueError, TypeError):
        return None
    return n if n >= 0 else None


def validate_pemeliharaan(data: dict, today_iso: str):
    """Validasi payload catatan pemeliharaan → daftar pesan kesalahan.

    Wajib: tanggal (ISO, tidak di masa depan), jenis terdaftar, uraian.
    biaya ≥ 0 (kosong = 0); kondisi_setelah opsional dari daftar valid.
    """
    errors = []
    t = _parse_tanggal(data.get("tanggal"))
    hari_ini = _parse_tanggal(today_iso)
    if not t:
        errors.append("Tanggal wajib diisi (format YYYY-MM-DD)")
    elif hari_ini and t > hari_ini:
        errors.append("Tanggal tidak boleh di masa depan")
    if data.get("jenis") not in JENIS_PEMELIHARAAN:
        valid = ", ".join(JENIS_PEMELIHARAAN)
        errors.append(f"Jenis tidak dikenal (pilihan: {valid})")
    if not str(data.get("uraian") or "").strip():
        errors.append("Uraian pekerjaan wajib diisi")
    if parse_biaya(data.get("biaya")) is None:
        errors.append("Biaya harus angka ≥ 0")
    if str(data.get("kondisi_setelah") or "") not in KONDISI_SETELAH_VALID:
        errors.append("Kondisi setelah tidak dikenal")
    return errors


def indikasi_kapitalisasi(biaya, kode_barang, ambang=None) -> bool:
    """Indikasi pengeluaran layak ditelaah kapitalisasi (PMK 181/2016).

    True bila biaya ≥ nilai satuan minimum kapitalisasi golongan aset
    (digit pertama kode barang: '3' peralatan-mesin, '4' gedung-bangunan).
    Hanya PENANDA telaah — keputusan final tetap butuh kriteria kualitatif
    PSAP 07 (menambah masa manfaat/kapasitas), bukan otomatis mengubah
    nilai aset.
    """
    peta = AMBANG_KAPITALISASI_DEFAULT if ambang is None else ambang
    batas = peta.get(str(kode_barang or "").strip()[:1])
    b = parse_biaya(biaya)
    return bool(batas and b is not None and b >= batas)


def tahun_dari_tanggal(tanggal_iso) -> int:
    """Tahun anggaran dari tanggal ISO; 0 bila tidak valid (bucket 'tak dikenal')."""
    t = _parse_tanggal(tanggal_iso)
    return t.year if t else 0


def urut_riwayat(records):
    """Riwayat terbaru dulu: (tanggal desc, created_at desc)."""
    return sorted(
        records or [],
        key=lambda r: (str(r.get("tanggal") or ""), str(r.get("created_at") or "")),
        reverse=True,
    )


def rentang_periode(tahun: int, semester=None):
    """Rentang tanggal ISO satu periode DHPB → (dari, sampai, label).

    Ps. 47 PP 27/2014: laporan berkala (praktik baku semesteran) + rekap
    per Tahun Anggaran. semester None = tahun penuh.
    """
    t = int(tahun)
    if semester == 1:
        return f"{t}-01-01", f"{t}-06-30", f"Semester I Tahun Anggaran {t}"
    if semester == 2:
        return f"{t}-07-01", f"{t}-12-31", f"Semester II Tahun Anggaran {t}"
    return f"{t}-01-01", f"{t}-12-31", f"Tahun Anggaran {t}"


def kelompok_dhpb(records):
    """Kelompokkan catatan per aset untuk DHPB → (grup, total_biaya).

    Grup terurut nama aset; catatan di dalam grup kronologis (tanggal,
    created_at) mengikuti format kartu pemeliharaan bahan ajar DJKN.
    """
    per = {}
    total = 0.0
    for r in records or []:
        kunci = r.get("asset_id") or f"{r.get('asset_code')}-{r.get('NUP')}"
        g = per.setdefault(kunci, {
            "asset_id": r.get("asset_id"),
            "asset_code": r.get("asset_code"),
            "NUP": r.get("NUP"),
            "asset_name": r.get("asset_name"),
            "items": [], "subtotal": 0.0,
        })
        g["items"].append(r)
        g["subtotal"] += parse_biaya(r.get("biaya")) or 0.0
        total += parse_biaya(r.get("biaya")) or 0.0
    grup = sorted(per.values(), key=lambda g: (
        g["asset_name"] or "", g["asset_code"] or "", str(g["NUP"] or "")))
    for g in grup:
        g["items"].sort(key=lambda r: (
            str(r.get("tanggal") or ""), str(r.get("created_at") or "")))
    return grup, total


def rekap_pemeliharaan(records, tahun: int = None):
    """Rekap catatan → jumlah, total biaya, per jenis, per tahun, per aset.

    `tahun` menyaring per_jenis/per_aset/jumlah/total ke satu tahun anggaran;
    per_tahun selalu dihitung dari seluruh catatan (untuk pilihan filter UI).
    """
    per_tahun = {}
    per_jenis = {k: {"jumlah": 0, "biaya": 0.0} for k in JENIS_PEMELIHARAAN}
    per_aset = {}
    jumlah = 0
    total_biaya = 0.0
    for r in records or []:
        biaya = parse_biaya(r.get("biaya")) or 0.0
        thn = tahun_dari_tanggal(r.get("tanggal"))
        bt = per_tahun.setdefault(thn, {"jumlah": 0, "biaya": 0.0})
        bt["jumlah"] += 1
        bt["biaya"] += biaya
        if tahun is not None and thn != tahun:
            continue
        jumlah += 1
        total_biaya += biaya
        j = r.get("jenis")
        if j in per_jenis:
            per_jenis[j]["jumlah"] += 1
            per_jenis[j]["biaya"] += biaya
        kunci = r.get("asset_id") or ""
        a = per_aset.setdefault(kunci, {
            "asset_id": kunci,
            "asset_code": r.get("asset_code"),
            "NUP": r.get("NUP"),
            "asset_name": r.get("asset_name"),
            "jumlah": 0, "total_biaya": 0.0, "terakhir": "",
        })
        a["jumlah"] += 1
        a["total_biaya"] += biaya
        t = str(r.get("tanggal") or "")
        if t > a["terakhir"]:
            a["terakhir"] = t
    aset_urut = sorted(
        per_aset.values(),
        key=lambda x: (-x["total_biaya"], x["asset_name"] or ""),
    )
    return {
        "jumlah": jumlah,
        "total_biaya": total_biaya,
        "per_jenis": per_jenis,
        "per_tahun": {k: per_tahun[k] for k in sorted(per_tahun, reverse=True)},
        "per_aset": aset_urut,
    }
