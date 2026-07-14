"""Logika murni PEMINDAHTANGANAN (Fase 6 tahap awal: register usulan).

PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 (pustaka §7): empat bentuk —
Penjualan (prinsip lelang; tanpa lelang hanya kasus khusus), Tukar
Menukar, Hibah, PMPP. Register per USULAN multi-aset berstatus; dokumen
wajib per tahap mengunci transisi (mencegah temuan: pemindahtanganan
tanpa persetujuan, hasil tidak disetor, tak ditindaklanjuti penghapusan).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from datetime import date

from pembukuan_utils import parse_harga

BENTUK_PEMINDAHTANGANAN = {
    "penjualan_lelang": "Penjualan (lelang KPKNL)",
    "penjualan_langsung": "Penjualan tanpa lelang (kasus khusus)",
    "tukar_menukar": "Tukar Menukar",
    "hibah": "Hibah",
    "pmpp": "Penyertaan Modal Pemerintah Pusat",
}

# Label dokumen pelaksanaan per bentuk (syarat status "dilaksanakan")
DOKUMEN_PELAKSANAAN = {
    "penjualan_lelang": "Risalah Lelang",
    "penjualan_langsung": "Perjanjian Jual Beli/BAST",
    "tukar_menukar": "Perjanjian Tukar Menukar + BAST",
    "hibah": "Naskah Hibah + BAST",
    "pmpp": "Peraturan Pemerintah PMPP + BAST",
}

STATUS_USULAN_PT = {
    "diusulkan": "Diusulkan",
    "disetujui": "Disetujui",
    "dilaksanakan": "Dilaksanakan",
    "selesai": "Selesai (SK Penghapusan terbit)",
    "ditolak": "Ditolak/Batal",
}

TRANSISI_PT = {
    "diusulkan": {"disetujui", "ditolak"},
    "disetujui": {"dilaksanakan", "ditolak"},
    "dilaksanakan": {"selesai"},
    "selesai": set(),
    "ditolak": set(),
}

TENGGAT_LELANG_HARI = 183  # permohonan lelang ≤6 bulan sejak persetujuan


def _tgl(v):
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except (ValueError, TypeError):
        return None


def validate_usulan_pt(data: dict) -> list:
    """Validasi usulan baru → daftar pesan kesalahan."""
    errors = []
    if data.get("bentuk") not in BENTUK_PEMINDAHTANGANAN:
        valid = ", ".join(BENTUK_PEMINDAHTANGANAN)
        errors.append(f"Bentuk tidak dikenal (pilihan: {valid})")
    if not str(data.get("pihak") or "").strip():
        errors.append("Pihak penerima/pembeli/mitra wajib diisi")
    if not data.get("asset_ids"):
        errors.append("Minimal satu aset dalam usulan")
    return errors


def validate_transisi_pt(u: dict, ke: str, data: dict) -> list:
    """Validasi transisi status + dokumen wajib per tahap.

    disetujui  → wajib nomor persetujuan (+ instansi pemberi).
    dilaksanakan → wajib nomor dokumen pelaksanaan sesuai bentuk;
                   bentuk penjualan juga wajib NTPN setor PNBP.
    selesai    → wajib nomor SK Penghapusan (tindak lanjut PMK 83/2016).
    """
    errors = []
    dari = u.get("status")
    if ke not in STATUS_USULAN_PT:
        valid = ", ".join(STATUS_USULAN_PT)
        errors.append(f"Status tidak dikenal (pilihan: {valid})")
        return errors
    if ke not in TRANSISI_PT.get(dari, set()):
        errors.append(
            f"Transisi {STATUS_USULAN_PT.get(dari, dari)} → {STATUS_USULAN_PT[ke]} tidak sah")
        return errors
    if ke == "disetujui" and not str(data.get("nomor_persetujuan") or "").strip():
        errors.append("Nomor surat persetujuan wajib diisi")
    if ke == "dilaksanakan":
        label = DOKUMEN_PELAKSANAAN.get(u.get("bentuk"), "dokumen pelaksanaan")
        if not str(data.get("nomor_dokumen") or "").strip():
            errors.append(f"Nomor {label} wajib diisi")
        if u.get("bentuk", "").startswith("penjualan") and not str(data.get("ntpn") or "").strip():
            errors.append("NTPN bukti setor hasil penjualan ke Kas Negara wajib diisi")
    if ke == "selesai" and not str(data.get("nomor_sk_penghapusan") or "").strip():
        errors.append("Nomor SK Penghapusan wajib diisi (tindak lanjut PMK 83/2016)")
    return errors


def build_asset_pemindahtanganan_projection(usulan: dict, now_iso: str) -> dict:
    """Proyeksi master aset saat pemindahtanganan SELESAI — SK Penghapusan terbit
    (Prinsip 3 Bab 5: transaksi = jurnal, master = proyeksi).

    Pemindahtanganan yang tuntas (jual/tukar/hibah/PMPP) menghapus aset dari
    pembukuan lewat SK Penghapusan (tindak lanjut PMK 83/2016). Master diproyeksi
    memakai BENTUK MARKER YANG SAMA dengan penghapusan langsung (#234):
    `dihapus=True` + jejak `penghapusan.{...}` — sehingga SELURUH mesin laporan
    hilir ikut OTOMATIS: penyaringan posisi/nilai (DBKP/Neraca/rekonsiliasi,
    #248/#249) dan tombstone mutasi KURANG di LBKP/CaLBMN (#253, lewat
    `penghapusan.tanggal_sk`). Pembeda dari penghapusan biasa: `jalur=
    "pemindahtanganan"` + `pemindahtanganan_id`/`bentuk` untuk telusur.

    `tanggal_sk`: SK ditetapkan saat transisi 'selesai'; pakai
    `tanggal_sk_penghapusan` bila ada, jika tidak tanggal transisi (`now_iso`).
    Pemanggil menambah `$inc: {version: 1}` (bust cache/ETag + picu OCC 409 pada
    form usang). SENGAJA tak menyentuh `purchase_price`/`condition` (dibaca
    laporan; nilai perolehan historis tetap utuh untuk tombstone & audit).
    """
    return {
        "dihapus": True,
        "penghapusan": {
            "status": "sk_terbit",
            "jalur": "pemindahtanganan",
            "pemindahtanganan_id": str(usulan.get("id") or ""),
            "bentuk": str(usulan.get("bentuk") or ""),
            "nomor_sk": str(usulan.get("nomor_sk_penghapusan") or "").strip(),
            "tanggal_sk": (str(usulan.get("tanggal_sk_penghapusan") or "").strip()[:10]
                           or now_iso[:10]),
            "diproyeksikan_pada": now_iso,
        },
    }


def taut_penghapusan(nomor_sk, usulan) -> dict:
    """Bentuk taut FK Pemindahtanganan→Penghapusan (§5A gap #5). Saat usulan
    pemindahtanganan SELESAI, `nomor_sk_penghapusan`-nya dicocokkan ke tiket
    `usulan_penghapusan`. `usulan` = dokumen tiket yang cocok (atau None/{}).

    Kembalikan `{"penghapusan_id", "penghapusan_nomor_sk"}` bila tiket ada &
    ber-`id` (FK id, bukan sekadar string); else `{}` (nomor teks tetap
    disimpan pemanggil — tanpa FK). Fungsi murni — pemanggil melakukan lookup
    (mis. `db.usulan_penghapusan.find_one({"nomor_sk": ...})`)."""
    nk = str(nomor_sk or "").strip()
    if not nk or not usulan or not usulan.get("id"):
        return {}
    return {"penghapusan_id": usulan["id"],
            "penghapusan_nomor_sk": str(usulan.get("nomor_sk") or nk).strip()}


def peringatan_pt(u: dict, today_iso: str) -> list:
    """Peringatan kepatuhan per usulan (tenggat lelang 6 bulan)."""
    warn = []
    hari_ini = _tgl(today_iso)
    if (u.get("status") == "disetujui"
            and u.get("bentuk") == "penjualan_lelang"):
        setuju = _tgl(u.get("tanggal_persetujuan"))
        if setuju and hari_ini:
            sisa = TENGGAT_LELANG_HARI - (hari_ini - setuju).days
            if sisa < 0:
                warn.append("Lewat 6 bulan sejak persetujuan tanpa pelaksanaan "
                            "lelang — wajib penilaian ulang (PMK 165/2021)")
            elif sisa <= 30:
                warn.append(f"Tenggat permohonan lelang tinggal ±{sisa} hari "
                            "(≤6 bulan sejak persetujuan)")
    return warn


def rekap_pt(items):
    """Ringkasan register: hitung per status/bentuk + nilai perolehan."""
    per_status = {k: 0 for k in STATUS_USULAN_PT}
    per_bentuk = {k: 0 for k in BENTUK_PEMINDAHTANGANAN}
    nilai = 0.0
    jumlah_aset = 0
    for u in items or []:
        s = u.get("status")
        if s in per_status:
            per_status[s] += 1
        b = u.get("bentuk")
        if b in per_bentuk:
            per_bentuk[b] += 1
        for a in u.get("aset") or []:
            jumlah_aset += 1
            nilai += parse_harga(a.get("harga"))
    return {"jumlah": len(items or []), "jumlah_aset": jumlah_aset,
            "per_status": per_status, "per_bentuk": per_bentuk, "nilai": nilai}


# ---------------------------------------------------------------------------
# Referensi jenjang persetujuan pemindahtanganan (riset #201). Ambang
# STATUTORI dari UU 1/2004 Ps. 45-46 + PP 27/2014 jo. 28/2020 Ps. 55-58
# (di atas level PMK — PMK 111/2016 jo. 165/2021 tak mengubah ambang).
# Ambang dihitung atas NILAI WAJAR hasil penilaian, bukan nilai buku.
# AMAN hanya MENYARANKAN (indikatif); keputusan resmi tetap pejabat
# berwenang. Pendelegasian internal DJKN (KPKNL/Kanwil/Dirjen) & delegasi
# ke Pengguna Barang belum diverifikasi dari teks resmi (pustaka §14).
# ---------------------------------------------------------------------------
JENIS_BMN_PT = {
    "selain_tanah_bangunan": "Selain tanah dan/atau bangunan",
    "tanah_bangunan": "Tanah dan/atau bangunan",
}

JENJANG_PERSETUJUAN = {
    "pengguna": "Pengguna Barang (K/L)",
    "pengelola": "Pengelola Barang (Menkeu c.q. DJKN)",
    "presiden": "Presiden",
    "dpr": "DPR RI",
}

_MILIAR = 1_000_000_000
_AMBANG_PRESIDEN = 10 * _MILIAR      # > Rp10 M
_AMBANG_DPR = 100 * _MILIAR          # > Rp100 M (selain tanah/bangunan)

# Tabel referensi untuk ditampilkan (nilai None = tak berhingga).
AMBANG_PERSETUJUAN_PT = [
    {"jenis_bmn": "selain_tanah_bangunan", "batas_bawah": 0,
     "batas_atas": _AMBANG_PRESIDEN, "jenjang": "pengelola",
     "dasar": "UU 1/2004 Ps. 46; PP 27/2014"},
    {"jenis_bmn": "selain_tanah_bangunan", "batas_bawah": _AMBANG_PRESIDEN,
     "batas_atas": _AMBANG_DPR, "jenjang": "presiden",
     "dasar": "UU 1/2004 Ps. 46"},
    {"jenis_bmn": "selain_tanah_bangunan", "batas_bawah": _AMBANG_DPR,
     "batas_atas": None, "jenjang": "dpr", "dasar": "UU 1/2004 Ps. 46"},
    {"jenis_bmn": "tanah_bangunan", "batas_bawah": 0, "batas_atas": None,
     "jenjang": "dpr", "dasar": "PP 27/2014 Ps. 55(1) — umum, tanpa batas nilai"},
    {"jenis_bmn": "tanah_bangunan_terkecuali", "batas_bawah": 0,
     "batas_atas": _AMBANG_PRESIDEN, "jenjang": "pengelola",
     "dasar": "PP 27/2014 Ps. 56 (pengecualian Ps. 55(2))"},
    {"jenis_bmn": "tanah_bangunan_terkecuali", "batas_bawah": _AMBANG_PRESIDEN,
     "batas_atas": None, "jenjang": "presiden",
     "dasar": "PP 27/2014 Ps. 56 (pengecualian Ps. 55(2))"},
]


def sarankan_jenjang(bentuk, jenis_bmn, nilai, tb_terkecuali=False) -> dict:
    """Sarankan jenjang persetujuan (indikatif) dari jenis BMN + nilai wajar.

    Mengembalikan {jenjang, jenjang_label, dasar, catatan(list), disclaimer}.
    Tidak memblok apa pun — hanya panduan. Nilai idealnya nilai wajar.
    """
    n = parse_harga(nilai)
    catatan = []
    if jenis_bmn == "tanah_bangunan":
        if tb_terkecuali:
            jenjang = "presiden" if n > _AMBANG_PRESIDEN else "pengelola"
            dasar = "PP 27/2014 Ps. 56 (pengecualian Ps. 55(2))"
        else:
            jenjang = "dpr"
            dasar = "PP 27/2014 Ps. 55(1) — tanah/bangunan wajib persetujuan DPR"
            catatan.append("Bila termasuk pengecualian Ps. 55(2) (tak sesuai "
                           "tata ruang, untuk pegawai/kepentingan umum, dsb.), "
                           "jenjang mengikuti nilai (Pengelola/Presiden).")
    else:  # selain tanah/bangunan
        if n > _AMBANG_DPR:
            jenjang, dasar = "dpr", "UU 1/2004 Ps. 46"
        elif n > _AMBANG_PRESIDEN:
            jenjang, dasar = "presiden", "UU 1/2004 Ps. 46"
        else:
            jenjang, dasar = "pengelola", "UU 1/2004 Ps. 46; PP 27/2014"
        if bentuk == "hibah" and n <= 100_000_000:
            catatan.append("Hibah selain tanah/bangunan tanpa bukti "
                           "kepemilikan & nilai perolehan ≤ Rp100 jt dapat "
                           "cukup Pengguna Barang (KMK 334/2021).")
    # PMPP ditetapkan dengan Peraturan Pemerintah → minimal melibatkan Presiden
    if bentuk == "pmpp" and jenjang == "pengelola":
        jenjang = "presiden"
        catatan.append("PMPP ditetapkan dengan Peraturan Pemerintah — "
                       "minimal melibatkan Presiden.")
    return {
        "jenjang": jenjang,
        "jenjang_label": JENJANG_PERSETUJUAN.get(jenjang, jenjang),
        "dasar": dasar,
        "catatan": catatan,
        "disclaimer": ("Indikatif berbasis nilai wajar — bukan penetapan; "
                       "keputusan resmi di pejabat berwenang. Ambang statutori "
                       "[perlu verifikasi vs teks resmi, pustaka §14]."),
    }
