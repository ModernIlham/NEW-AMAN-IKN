"""PRIVASI PELACAKAN — kebijakan §10 ARSITEKTUR-SPASIAL-IOT dijadikan KODE.

Kenapa modul ini ada SEBELUM ingest posisi dibangun (Fase 11+), bukan sesudah:
kebijakan privasi yang hanya hidup di dokumen akan dilewati diam-diam oleh
kode yang menyusul — bukan karena niat buruk, tetapi karena tak ada yang
memaksanya. Dengan pagar berada di jalur tulis SEBELUM data pertama masuk,
"lupa" menjadi mustahil: tak ada observasi yang bisa disimpan tanpa melewati
`saring_observasi()`.

DASAR: UU 27/2022 (Pelindungan Data Pribadi). Melacak perangkat yang dipegang
perorangan = memproses data pribadi orang itu, bukan sekadar data barang.
Kalimat pengarah dari §10 dokumen arsitektur:

    "Sistem melacak BARANG NEGARA, bukan ORANG. Untuk perangkat yang dipegang
     perorangan, sistem sengaja hanya menyimpan level gedung dan hanya pada
     jam kerja — presisi penuh dibuka hanya saat barang dilaporkan hilang,
     dengan persetujuan pejabat dan tercatat."

Itu sekaligus keputusan TEKNIS yang lebih murah: menyimpan "gedung X, jam
kerja" alih-alih jejak titik 24/7 memangkas volume data secara drastis.

Modul ini MURNI (tanpa I/O, tanpa DB) supaya bisa diuji tanpa infrastruktur
dan dipanggil dari jalur panas mana pun.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

# ── Profil privasi per JENIS PEMEGANG ───────────────────────────────────────
#
# Sumbu yang menentukan bukan "jenis perangkat" melainkan SIAPA yang terdampak
# bila posisinya terekam. GPS di kendaraan dinas merekam pergerakan kendaraan
# (barang); GPS di HP yang dipegang seorang pegawai merekam pergerakan ORANG
# itu — termasuk ke rumah, klinik, atau tempat ibadah di luar jam kerja.
#
# presisi:
#   "penuh"  → koordinat apa adanya
#   "wilayah"→ HANYA node denah (gedung/kawasan), koordinat DIBUANG
# jam_aktif: (mulai, selesai) jam lokal 0–23, atau None = tanpa batas waktu
# retensi_hari: umur simpan observasi mentah
PROFIL_PRIVASI = {
    # Barang murni — tak ada orang yang melekat pada posisinya.
    "aset_tetap": {"presisi": "penuh", "jam_aktif": None,
                   "retensi_hari": 365, "hari_kerja_saja": False,
                   "label": "Aset tetap (tanpa pemegang perorangan)"},
    # Kendaraan dinas: pengemudi berganti, dan pemakaian di luar jam kerja
    # justru hal yang WAJIB terpantau (indikasi penyalahgunaan BMN).
    "kendaraan": {"presisi": "penuh", "jam_aktif": None,
                  "retensi_hari": 90, "hari_kerja_saja": False,
                  "label": "Kendaraan dinas"},
    # Perangkat yang dipegang PERORANGAN — pagar paling ketat.
    "personal": {"presisi": "wilayah", "jam_aktif": (7, 18),
                 "retensi_hari": 30, "hari_kerja_saja": True,
                 "label": "Perangkat pegangan perorangan (HP/laptop)"},
}
PROFIL_BAWAAN = "personal"        # gagal-tertutup: paling ketat bila tak jelas

# Pembukaan presisi penuh darurat (barang hilang) TIDAK boleh permanen.
MAKS_JAM_DARURAT = 72
ALASAN_DARURAT_MIN = 10           # alasan wajib bermakna, bukan "." atau "x"

# Kunci yang menyimpan koordinat mentah DI DALAM snapshot lokasi. Dibuang untuk
# profil berpresisi "wilayah" — lihat `saring_observasi`.
_KUNCI_TITIK_MENTAH = ("titik", "koordinat", "lon", "lat")


def profil_privasi(nama) -> dict:
    """Profil terdaftar, atau profil TERKETAT bila nama tak dikenal.

    Gagal-TERTUTUP disengaja: perangkat dengan profil salah ketik harus
    diperlakukan seketat mungkin, bukan dibiarkan merekam penuh 24/7.
    """
    return PROFIL_PRIVASI.get(str(nama or "").strip().lower(),
                              PROFIL_PRIVASI[PROFIL_BAWAAN])


def _jam_lokal(ts: datetime, offset_jam: int = 8) -> datetime:
    """UTC → waktu lokal. IKN memakai WITA (UTC+8); offset dibuat parameter
    agar satker di zona lain tak memakai jam kerja yang salah."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone(timedelta(hours=offset_jam)))


def dalam_jam_aktif(ts: datetime, profil: dict, offset_jam: int = 8) -> bool:
    """True bila waktu observasi berada dalam jendela yang boleh direkam.

    Profil tanpa `jam_aktif` selalu True. Untuk profil personal, observasi di
    luar jam kerja / akhir pekan TIDAK BOLEH disimpan sama sekali — bukan
    disimpan lalu disembunyikan, karena data yang tak pernah ada tak bisa
    bocor, disalahgunakan, atau diminta lewat jalur hukum.
    """
    if not profil.get("jam_aktif"):
        return True
    lokal = _jam_lokal(ts, offset_jam)
    if profil.get("hari_kerja_saja") and lokal.weekday() >= 5:   # Sabtu/Minggu
        return False
    mulai, selesai = profil["jam_aktif"]
    return mulai <= lokal.hour < selesai


def saring_observasi(obs: dict, profil_nama, sekarang: Optional[datetime] = None,
                     offset_jam: int = 8, darurat: bool = False) -> dict:
    """GERBANG WAJIB jalur tulis posisi. Kembalikan:

        {"simpan": bool, "alasan": str, "observasi": dict|None}

    `observasi` sudah DIDEGRADASI sesuai profil — pemanggil menyimpan APA
    ADANYA hasil fungsi ini, tak pernah dokumen aslinya. Dengan begitu satu
    tempat menentukan apa yang boleh menyentuh disk.

    `darurat=True` (barang dilaporkan hilang, sudah disetujui & tercatat)
    membuka presisi penuh + mengabaikan jam aktif — lihat `izin_darurat_sah`.
    """
    profil = profil_privasi(profil_nama)
    ts = obs.get("ts_device") or obs.get("ts_server") or sekarang
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            ts = None
    if not isinstance(ts, datetime):
        ts = sekarang or datetime.now(timezone.utc)

    if not darurat and not dalam_jam_aktif(ts, profil, offset_jam):
        return {"simpan": False,
                "alasan": ("Di luar jam aktif profil "
                           f"'{profil['label']}' — observasi TIDAK disimpan"),
                "observasi": None}

    hasil = dict(obs)
    if not darurat and profil.get("presisi") == "wilayah":
        # Koordinat & turunan presisi-tinggi DIBUANG; yang tersisa hanya
        # "ada di wilayah/gedung mana" — cukup untuk penatausahaan BMN,
        # tak cukup untuk merekonstruksi pergerakan seseorang.
        for k in ("geo", "akurasi_m", "kecepatan_kmh", "arah_deg", "hdop"):
            hasil.pop(k, None)
        # `lokasi_spasial` SENGAJA bertahan — itulah "level wilayah" yang boleh
        # disimpan. Tetapi snapshot lokasi membawa serta koordinat mentahnya
        # (`titik`), dan membiarkannya berarti presisi penuh tetap tersimpan
        # lewat pintu belakang setelah `geo` susah payah dibuang.
        lok = hasil.get("lokasi_spasial")
        if isinstance(lok, dict):
            # Dibangun ulang, bukan di-pop: `hasil` hanya salinan DANGKAL, jadi
            # memutasi dict bersarang akan merusak dokumen milik pemanggil.
            hasil["lokasi_spasial"] = {k: v for k, v in lok.items()
                                       if k not in _KUNCI_TITIK_MENTAH}
        hasil["presisi_didegradasi"] = True
    hasil["profil_privasi"] = str(profil_nama or PROFIL_BAWAAN).strip().lower()
    if darurat:
        hasil["akses_darurat"] = True
    return {"simpan": True, "alasan": "", "observasi": hasil}


def izin_darurat_sah(izin: dict, sekarang: Optional[datetime] = None) -> Optional[str]:
    """Pesan galat bila pembukaan presisi darurat tak sah, atau None.

    Tiga syarat, semuanya WAJIB — pembukaan presisi penuh atas perangkat
    perorangan adalah tindakan berdampak tinggi:
      1. ALASAN tertulis yang bermakna (jejak akuntabilitas);
      2. PEJABAT yang menyetujui (bukan operator yang sama);
      3. MASA BERLAKU berhingga ≤ 72 jam (izin permanen = kebijakan yang
         dibatalkan diam-diam).
    """
    izin = izin or {}
    alasan = str(izin.get("alasan") or "").strip()
    if len(alasan) < ALASAN_DARURAT_MIN:
        return (f"Alasan wajib diisi (min. {ALASAN_DARURAT_MIN} karakter) — "
                "pembukaan presisi lokasi perorangan harus dapat "
                "dipertanggungjawabkan")
    if not str(izin.get("disetujui_oleh") or "").strip():
        return "Pejabat yang menyetujui wajib dicatat"
    if str(izin.get("disetujui_oleh")).strip() == str(izin.get("diminta_oleh") or "").strip():
        return "Pemohon dan pemberi persetujuan tidak boleh orang yang sama"
    berlaku = izin.get("berlaku_sampai")
    if isinstance(berlaku, str):
        try:
            berlaku = datetime.fromisoformat(berlaku.replace("Z", "+00:00"))
        except ValueError:
            berlaku = None
    if not isinstance(berlaku, datetime):
        return "Masa berlaku izin wajib diisi"
    if berlaku.tzinfo is None:
        berlaku = berlaku.replace(tzinfo=timezone.utc)
    kini = sekarang or datetime.now(timezone.utc)
    if berlaku <= kini:
        return "Izin sudah kedaluwarsa"
    if berlaku > kini + timedelta(hours=MAKS_JAM_DARURAT):
        return f"Masa berlaku maksimal {MAKS_JAM_DARURAT} jam"
    return None


def batas_retensi(profil_nama, sekarang: Optional[datetime] = None) -> datetime:
    """Ambang waktu: observasi lebih tua dari ini WAJIB dihapus.

    Dipakai penyapu terjadwal DAN sebagai sumber angka TTL index, supaya
    kedua jalur tak pernah menyimpang (retensi yang berbeda antara dokumen
    kebijakan dan indeks database = kepatuhan di atas kertas saja).
    """
    profil = profil_privasi(profil_nama)
    kini = sekarang or datetime.now(timezone.utc)
    return kini - timedelta(days=int(profil["retensi_hari"]))


def ringkas_kebijakan() -> list:
    """Ringkasan profil untuk DITAMPILKAN di UI/laporan kepatuhan — kebijakan
    yang tak terlihat pengguna tak bisa diperiksa siapa pun."""
    return [{"profil": k, "label": v["label"], "presisi": v["presisi"],
             "jam_aktif": (f"{v['jam_aktif'][0]:02d}:00–{v['jam_aktif'][1]:02d}:00"
                           if v["jam_aktif"] else "24 jam"),
             "hari_kerja_saja": v["hari_kerja_saja"],
             "retensi_hari": v["retensi_hari"]}
            for k, v in PROFIL_PRIVASI.items()]
