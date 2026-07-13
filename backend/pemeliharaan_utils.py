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


def tambah_bulan(tanggal_iso: str, n: int) -> str:
    """Tanggal ISO + n bulan; hari dijepit ke akhir bulan tujuan.

    Contoh: 2026-01-31 + 1 bulan → 2026-02-28 (bukan meloncat ke Maret).
    """
    t = _parse_tanggal(tanggal_iso)
    if not t:
        return ""
    total = (t.year * 12) + (t.month - 1) + int(n)
    tahun, bulan = divmod(total, 12)
    bulan += 1
    # Hari terakhir bulan tujuan (tanpa modul calendar agar tetap ringan)
    if bulan == 12:
        akhir = 31
    else:
        akhir = (date(tahun, bulan + 1, 1) - date(tahun, bulan, 1)).days
    return date(tahun, bulan, min(t.day, akhir)).isoformat()


def validate_jadwal(data: dict) -> list:
    """Validasi payload jadwal berkala → daftar pesan kesalahan."""
    errors = []
    try:
        interval = int(data.get("interval_bulan"))
    except (TypeError, ValueError):
        interval = 0
    if not 1 <= interval <= 60:
        errors.append("Interval harus 1-60 bulan")
    if not _parse_tanggal(data.get("mulai")):
        errors.append("Tanggal mulai wajib diisi (format YYYY-MM-DD)")
    return errors


def jatuh_tempo(jadwal: dict) -> str:
    """Tanggal jatuh tempo berikutnya sebuah jadwal berkala.

    Belum pernah dilaksanakan → jatuh tempo = tanggal mulai; sesudahnya =
    pelaksanaan terakhir + interval bulan.
    """
    terakhir = str(jadwal.get("terakhir") or "").strip()
    if not terakhir:
        return str(jadwal.get("mulai") or "").strip()[:10]
    return tambah_bulan(terakhir, int(jadwal.get("interval_bulan") or 1))


def status_jadwal(due_iso: str, today_iso: str, ambang_hari: int = 14) -> str:
    """Status jadwal: terlambat / segera (≤ ambang_hari) / terjadwal."""
    due = _parse_tanggal(due_iso)
    hari_ini = _parse_tanggal(today_iso)
    if not due or not hari_ini:
        return "terjadwal"
    if due < hari_ini:
        return "terlambat"
    if (due - hari_ini).days <= ambang_hari:
        return "segera"
    return "terjadwal"


STATUS_JADWAL_LABEL = {
    "terlambat": "Terlambat",
    "segera": "Segera jatuh tempo",
    "terjadwal": "Terjadwal",
}

HEADER_CSV_JADWAL = [
    "kode_aset", "nup", "nama_aset", "interval_bulan", "mulai",
    "terakhir_dilaksanakan", "jatuh_tempo", "status", "keterangan",
    "dibuat_oleh",
]


def baris_csv_jadwal(jadwal_list, today_iso) -> list:
    """Susun baris CSV jadwal pemeliharaan berkala: [header, *data] — murni.

    Jatuh tempo & status dihitung via jatuh_tempo/status_jadwal (terlambat/
    segera/terjadwal → label); tanggal dipangkas 10 char; field hilang →
    string kosong. Tanpa Mongo/IO agar teruji unit (pola ekspor #158).
    """
    baris = [list(HEADER_CSV_JADWAL)]
    for j in jadwal_list or []:
        due = jatuh_tempo(j)
        baris.append([
            j.get("asset_code") or "",
            j.get("NUP") or "",
            j.get("asset_name") or "",
            int(j.get("interval_bulan") or 0),
            str(j.get("mulai") or "")[:10],
            str(j.get("terakhir") or "")[:10],
            due or "",
            STATUS_JADWAL_LABEL.get(status_jadwal(due, today_iso), ""),
            j.get("keterangan") or "",
            j.get("created_by") or "",
        ])
    return baris


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
