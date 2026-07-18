"""Logika murni PERENCANAAN (Fase 4 — tahap awal: kandidat RKBMN pemeliharaan).

PMK 153/PMK.06/2021 (riset di pustaka §4): usulan RKBMN pemeliharaan hanya
untuk BMN kondisi Baik/Rusak Ringan; TIDAK boleh untuk rusak berat
(jalurnya usul penghapusan/pemindahtanganan), BMN idle (PMK 120/2024),
atau barang yang tidak dioperasikan. Bahan penyusunan: Daftar Barang Kuasa
Pengguna + Daftar Hasil Pemeliharaan — di AMAN: master aset + riwayat
biaya modul Pemeliharaan.

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""
from pembukuan_utils import parse_harga

KONDISI_LAYAK = ("Baik", "Rusak Ringan")


def kelayakan_rkbmn(asset: dict):
    """(layak, alasan) usulan pemeliharaan satu aset — urutan telaah:
    kondisi RB dulu (jalur lain), lalu status operasional, lalu kondisi."""
    kondisi = str(asset.get("condition") or "").strip()
    status = str(asset.get("status") or "").strip()
    if kondisi == "Rusak Berat":
        return False, "Rusak Berat — jalurnya usul penghapusan/pemindahtanganan, bukan pemeliharaan"
    if status == "Nonaktif":
        return False, "Status Nonaktif — barang tidak dioperasikan"
    if status == "Idle":
        return False, "BMN idle — usulkan penetapan status/penyerahan (PMK 120/2024)"
    if kondisi in KONDISI_LAYAK:
        return True, ""
    return False, f"Kondisi belum tercatat ({kondisi or 'kosong'}) — lengkapi data aset dulu"


def rekap_rkbmn(assets, biaya_per_aset=None):
    """Pisahkan aset layak/tidak layak usul pemeliharaan + biaya riwayat.

    biaya_per_aset: {asset_id: {"jumlah": n, "total_biaya": x}} dari rekap
    modul Pemeliharaan (tahun anggaran berjalan) — aset dengan riwayat
    biaya terbesar tampil dulu (bahan pertimbangan usulan).
    """
    biaya_per_aset = biaya_per_aset or {}
    layak, tidak = [], []
    for a in assets or []:
        ok, alasan = kelayakan_rkbmn(a)
        b = biaya_per_aset.get(a.get("id")) or {}
        row = {
            "id": a.get("id"),
            "asset_code": a.get("asset_code"),
            "NUP": a.get("NUP"),
            "asset_name": a.get("asset_name"),
            "condition": a.get("condition"),
            "status": a.get("status"),
            "location": a.get("location"),
            "riwayat_jumlah": int(b.get("jumlah", 0) or 0),
            "riwayat_biaya": float(b.get("total_biaya", 0) or 0.0),
        }
        if ok:
            layak.append(row)
        else:
            row["alasan"] = alasan
            tidak.append(row)
    layak.sort(key=lambda r: (-r["riwayat_biaya"], r["asset_name"] or ""))
    tidak.sort(key=lambda r: (r["alasan"], r["asset_name"] or ""))
    return {
        "layak": layak,
        "tidak": tidak,
        "ringkasan": {
            "total": len(layak) + len(tidak),
            "layak": len(layak),
            "tidak": len(tidak),
            "total_biaya_riwayat": sum(r["riwayat_biaya"] for r in layak),
        },
    }


# ---------------------------------------------------------------------------
# Register usulan RKBMN per unit (PMK 153/2021 + KMK 128/KM.6/2022) —
# rantai persetujuan berjenjang internal K/L sebelum masuk SIMAN V2.
# Register pendamping (pola e-SADEWA MA): status tak berkekuatan hukum,
# bukan cetakan RKBMN/SPTJM/Hasil Penelaahan resmi.
# ---------------------------------------------------------------------------

JENIS_USULAN_RKBMN = {
    "pengadaan": "Pengadaan",
    "pemeliharaan": "Pemeliharaan",
}

STATUS_USULAN_RKBMN = {
    "draft": "Draft",
    "diajukan": "Diajukan unit",
    "dikembalikan": "Dikembalikan (perbaikan)",
    "disetujui_pb": "Disetujui Pengguna Barang",
    "dikirim_pengelola": "Dikirim ke Pengelola (SIMAN)",
    "disetujui_telaah": "Disetujui Hasil Penelaahan",
    "ditolak_telaah": "Ditolak Hasil Penelaahan",
}

TRANSISI_USULAN_RKBMN = {
    "draft": {"diajukan"},
    "diajukan": {"disetujui_pb", "dikembalikan"},
    "dikembalikan": {"diajukan"},
    "disetujui_pb": {"dikirim_pengelola", "dikembalikan"},
    "dikirim_pengelola": {"disetujui_telaah", "ditolak_telaah"},
    "disetujui_telaah": set(),
    "ditolak_telaah": set(),
}


def validate_usulan_rkbmn(data: dict) -> list:
    """Validasi usulan RKBMN baru → daftar pesan kesalahan."""
    errors = []
    tahun = str(data.get("tahun_rkbmn") or "").strip()
    if not (len(tahun) == 4 and tahun.isdigit()):
        errors.append("Tahun RKBMN harus 4 digit angka")
    if data.get("jenis") not in JENIS_USULAN_RKBMN:
        valid = ", ".join(JENIS_USULAN_RKBMN)
        errors.append(f"Jenis usulan tidak dikenal (pilihan: {valid})")
    if not str(data.get("unit_pengusul") or "").strip():
        errors.append("Unit/KPB pengusul wajib diisi")
    if not str(data.get("uraian") or "").strip():
        errors.append("Uraian usulan wajib diisi")
    try:
        if float(data.get("volume") or 0) <= 0:
            errors.append("Volume harus lebih dari 0")
    except (TypeError, ValueError):
        errors.append("Volume harus angka")
    if not str(data.get("satuan") or "").strip():
        errors.append("Satuan wajib diisi")
    return errors


def validate_transisi_rkbmn(usulan: dict, ke: str, catatan: str = "") -> list:
    """Validasi transisi status usulan; dikembalikan wajib beralasan."""
    dari = usulan.get("status")
    if ke not in STATUS_USULAN_RKBMN:
        valid = ", ".join(STATUS_USULAN_RKBMN)
        return [f"Status tujuan tidak dikenal (pilihan: {valid})"]
    if ke not in TRANSISI_USULAN_RKBMN.get(dari, set()):
        return [f"Transisi {dari} → {ke} tidak diizinkan"]
    if ke == "dikembalikan" and not str(catatan or "").strip():
        return ["Pengembalian usulan wajib disertai catatan perbaikan"]
    return []


def rekap_usulan_rkbmn(items) -> dict:
    """Ringkasan usulan per status + per jenis + berjalan (non-terminal)."""
    per_status = {k: 0 for k in STATUS_USULAN_RKBMN}
    per_jenis = {k: 0 for k in JENIS_USULAN_RKBMN}
    for u in items or []:
        s = u.get("status")
        if s in per_status:
            per_status[s] += 1
        j = u.get("jenis")
        if j in per_jenis:
            per_jenis[j] += 1
    berjalan = sum(v for s, v in per_status.items()
                   if s not in ("disetujui_telaah", "ditolak_telaah"))
    return {"jumlah": len(items or []), "berjalan": berjalan,
            "per_status": per_status, "per_jenis": per_jenis}


def snapshot_rkbmn(usulan) -> dict:
    """Ringkas identitas usulan RKBMN (Perencanaan) untuk disimpan sebagai FK
    pada usulan Penganggaran (§5A gap #4: hubungkan simpul Perencanaan →
    Penganggaran, tiru pola `snapshot_penganggaran` Pengadaan→Penganggaran #199).

    Snapshot dibekukan saat usulan anggaran dibuat — jejak asal RKBMN tetap utuh
    walau usulan RKBMN sumber kelak berubah/terhapus. usulan None / kosong →
    snapshot kosong (tautan dilepas).
    """
    if not usulan:
        return {"rkbmn_id": "", "rkbmn_uraian": "", "rkbmn_tahun": "",
                "rkbmn_jenis": "", "rkbmn_unit": ""}
    return {
        "rkbmn_id": str(usulan.get("id") or "").strip(),
        "rkbmn_uraian": str(usulan.get("uraian") or "").strip(),
        "rkbmn_tahun": str(usulan.get("tahun_rkbmn") or "").strip(),
        "rkbmn_jenis": str(usulan.get("jenis") or "").strip(),
        "rkbmn_unit": str(usulan.get("unit_pengusul") or "").strip(),
    }


# ============================================================================
# SBSK — Standar Barang & Standar Kebutuhan (PMK 138/2024) + SANDING (M-MODUL)
# ============================================================================
# Standar berupa TABEL KONFIGURABEL (koleksi `sbsk_standar`) yang dirawat
# admin dari Lampiran PMK 138/2024 — angka lampiran terlalu rinci untuk
# di-hardcode dan bisa direvisi. Seed default memuat baris yang
# terdokumentasi publik + penanda "verifikasi Lampiran" (pola akun_bas).

SBSK_SEED_DEFAULT = (
    {"kategori": "ruang_kerja", "peruntukan": "Menteri/pimpinan setingkat",
     "satuan": "m²", "standar": 247,
     "keterangan": "Luas maksimum ruang kerja (riset publik PMK 138/2024 — verifikasi Lampiran)"},
    {"kategori": "kendaraan", "peruntukan": "Pejabat eselon I",
     "satuan": "unit", "standar": 1,
     "keterangan": "Kendaraan dinas jabatan (verifikasi Lampiran PMK 138/2024)"},
    {"kategori": "kendaraan", "peruntukan": "Pejabat eselon II",
     "satuan": "unit", "standar": 1,
     "keterangan": "Kendaraan dinas jabatan (verifikasi Lampiran PMK 138/2024)"},
    {"kategori": "barang", "peruntukan": "Komputer/laptop per pegawai",
     "satuan": "unit", "standar": 1,
     "keterangan": "Praktik umum standar kebutuhan alat pengolah data (improvisasi — sesuaikan kebijakan K/L)"},
)


def validate_sbsk(data: dict) -> list:
    """Validasi baris standar SBSK → daftar pesan kesalahan."""
    errors = []
    if str(data.get("kategori") or "").strip() not in ("ruang_kerja", "kendaraan", "barang", "tanah_bangunan"):
        errors.append("Kategori harus ruang_kerja/kendaraan/barang/tanah_bangunan")
    if not str(data.get("peruntukan") or "").strip():
        errors.append("Peruntukan (jabatan/penggunaan) wajib diisi")
    if not str(data.get("satuan") or "").strip():
        errors.append("Satuan wajib diisi")
    try:
        if float(data.get("standar") or 0) <= 0:
            errors.append("Angka standar harus > 0")
    except (TypeError, ValueError):
        errors.append("Angka standar harus angka")
    return errors


def _umur_tahun(purchase_date, kini_iso):
    """Umur aset dalam tahun (float) dari tanggal perolehan; None bila kosong."""
    s = str(purchase_date or "")[:10]
    k = str(kini_iso or "")[:10]
    if len(s) != 10 or len(k) != 10:
        return None
    try:
        th = int(k[:4]) - int(s[:4])
        sisa = (int(k[5:7]), int(k[8:10])) < (int(s[5:7]), int(s[8:10]))
        return max(0, th - (1 if sisa else 0))
    except ValueError:
        return None


def sanding_usulan_aset(usulan, assets, kini_iso, standar=None):
    """SANDING satu usulan RKBMN vs aset EKSISTING sejenis + standar SBSK.

    Pencocokan eksisting: `kode_barang` usulan sebagai PREFIX kode aset
    (kosong = tanpa sanding otomatis; uraian bebas tak bisa dicocokkan).
    Hasil: jumlah eksisting, sebaran kondisi, umur rata-rata, nilai total,
    baris standar SBSK yang relevan (match kata peruntukan/uraian), dan
    CATATAN analisis sederhana untuk reviewer.
    """
    prefix = str((usulan or {}).get("kode_barang") or "").strip()
    cocok = []
    if prefix:
        for a in assets or []:
            if str(a.get("asset_code") or "").startswith(prefix):
                cocok.append(a)
    kondisi = {}
    umur_list = []
    nilai = 0.0
    for a in cocok:
        k = str(a.get("condition") or "Belum dicatat")
        kondisi[k] = kondisi.get(k, 0) + 1
        u = _umur_tahun(a.get("purchase_date"), kini_iso)
        if u is not None:
            umur_list.append(u)
        nilai += parse_harga(a.get("purchase_price"))
    umur_rata = round(sum(umur_list) / len(umur_list), 1) if umur_list else None

    uraian = str((usulan or {}).get("uraian") or "").lower()
    relevan = []
    for s in standar or []:
        kunci = str(s.get("peruntukan") or "").lower()
        if kunci and (kunci in uraian or any(w in uraian for w in kunci.split()[:2] if len(w) > 3)):
            relevan.append(s)

    catatan = []
    vol = 0.0
    try:
        vol = float((usulan or {}).get("volume") or 0)
    except (TypeError, ValueError):
        pass
    rb = kondisi.get("Rusak Berat", 0)
    if prefix and not cocok:
        catatan.append("Belum ada aset eksisting sejenis — usulan pengadaan baru.")
    if cocok:
        catatan.append(f"{len(cocok)} unit eksisting sejenis"
                       + (f", {rb} Rusak Berat" if rb else "")
                       + (f", umur rata-rata {umur_rata} th" if umur_rata is not None else "") + ".")
        if vol and rb and vol <= rb:
            catatan.append("Volume usulan ≤ jumlah Rusak Berat — wajar sebagai penggantian.")
        elif vol and vol > len(cocok):
            catatan.append("Volume usulan melebihi populasi eksisting — pastikan dasar kebutuhan (SBSK).")
    for s in relevan:
        catatan.append(f"Standar SBSK terkait: {s.get('peruntukan')} = "
                       f"{s.get('standar')} {s.get('satuan')} ({s.get('keterangan') or 'PMK 138/2024'}).")

    return {
        "jumlah_eksisting": len(cocok),
        "kondisi": kondisi,
        "umur_rata_tahun": umur_rata,
        "nilai_eksisting": nilai,
        "standar_relevan": relevan,
        "catatan": catatan,
    }
