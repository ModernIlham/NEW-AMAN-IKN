"""Penyaring laporan gabungan satker — helper MURNI, tanpa I/O dan tanpa DB.

Permintaan pemilik: laporan gabungan harus INTERAKTIF — dapat memilih
kegiatan mana saja yang ikut, dengan filter lanjutan yang menerima **lebih
dari satu pilihan pada filter yang sama** (tahun, status, kondisi, lokasi),
plus rentang tanggal.

Tiga keputusan yang membentuk modul ini:

1. **Daftar pilihan dibangun dari data PENUH, bukan dari hasil saringan.**
   Kalau daftar tahun disusun dari aset yang sudah tersaring, memilih 2023
   akan membuat pilihan lain lenyap — dan pengguna terkurung: tak ada lagi
   kotak untuk mengembalikannya. Ini jebakan klasik filter bertingkat, dan
   ia hanya terlihat setelah seseorang benar-benar terjebak.

2. **Filter kegiatan menyusutkan KEDUA sisi.** Kegiatan yang tak dipilih
   hilang dari kartu capaian DAN asetnya hilang dari seluruh angka. Kalau
   hanya asetnya yang disaring, kartu kegiatan kosong tetap tercetak dan
   terbaca sebagai "kegiatan ini nol", bukan "kegiatan ini tak dipilih".

3. **Filter kosong berarti SEMUA, bukan TIDAK ADA.** Halaman yang dibuka
   tanpa parameter harus menampilkan laporan utuh, sebagaimana selama ini.
"""
from datetime import datetime

import inventarisasi_stempel as stempel_inv

#: Dimensi filter aset beserta nama field sumbernya. Satu tempat, supaya
#: menambah dimensi tak perlu menyentuh empat berkas.
DIMENSI = (
    ("status", "inventory_status"),
    ("kondisi", "condition"),
    ("lokasi", "location"),
)


def _teks(v) -> str:
    return str(v if v is not None else "").strip()


def tahun_aset(a, ambil_tahun) -> str:
    """Tahun perolehan aset sebagai teks; '' bila tak terbaca."""
    th = ambil_tahun(a.get("purchase_date"))
    return "" if th in ("-", None) else _teks(th)


def bersihkan(nilai) -> list:
    """Daftar pilihan dari query string — kosong dan duplikat dibuang.

    Nilai kosong DIBUANG, bukan diperlakukan sebagai pilihan: `?tahun=` yang
    terkirim dari formulir kosong tak boleh berubah makna menjadi "hanya aset
    tanpa tahun".
    """
    if nilai is None:
        return []
    if isinstance(nilai, str):
        nilai = [nilai]
    keluar, terlihat = [], set()
    for v in nilai:
        t = _teks(v)
        if t and t not in terlihat:
            terlihat.add(t)
            keluar.append(t)
    return keluar


def _tanggal(teks):
    try:
        return datetime.strptime(_teks(teks)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def dalam_rentang(a, dari, sampai) -> bool:
    """Apakah tanggal pemeriksaan aset masuk rentang yang diminta.

    Aset TANPA stempel ikut lolos saat rentangnya kosong, tetapi TERSARING
    KELUAR begitu rentang diisi: menanyakan "yang diperiksa Agustus" lalu
    menerima aset yang tanggal periksanya tak diketahui akan menjawab
    pertanyaan yang berbeda dari yang diajukan.
    """
    d0, d1 = _tanggal(dari), _tanggal(sampai)
    if not d0 and not d1:
        return True
    dt = _tanggal(a.get(stempel_inv.FIELD))
    if dt is None:
        return False
    if d0 and dt < d0:
        return False
    if d1 and dt > d1:
        return False
    return True


def pilihan_filter(satker_acts, all_assets, ambil_tahun) -> dict:
    """Seluruh nilai yang TERSEDIA — dibangun dari data penuh (lihat #1).

    Bentuknya seragam `[{"nilai", "label"}]` untuk SETIAP dimensi, termasuk
    kegiatan yang nilainya id dan labelnya nama. Template karenanya cukup
    mengulang satu bentuk; merakit pasangan nilai-label di dalam Jinja butuh
    filter buatan sendiri, dan logika yang pindah ke template adalah logika
    yang tak lagi bisa diuji.
    """
    def opsi(nilai):
        return [{"nilai": v, "label": v} for v in sorted({v for v in nilai if v})]

    return {
        "kegiatan": [{"nilai": a.get("id", ""),
                      "label": a.get("nama_kegiatan") or a.get("id", "")}
                     for a in satker_acts if a.get("id")],
        "tahun": [{"nilai": v, "label": v} for v in
                  sorted({tahun_aset(a, ambil_tahun) for a in all_assets
                          if tahun_aset(a, ambil_tahun)}, reverse=True)],
        **{kunci: opsi(_teks(a.get(field)) for a in all_assets)
           for kunci, field in DIMENSI},
    }


def terapkan(satker_acts, all_assets, filter_dipilih, ambil_tahun):
    """Terapkan filter; kembalikan (kegiatan, aset) yang lolos."""
    f = filter_dipilih or {}
    keg = bersihkan(f.get("kegiatan"))
    if keg:
        pilih = set(keg)
        satker_acts = [a for a in satker_acts if a.get("id") in pilih]
        # Sisi aset ikut disusutkan (lihat #2).
        all_assets = [a for a in all_assets if a.get("activity_id") in pilih]

    tahun = set(bersihkan(f.get("tahun")))
    if tahun:
        all_assets = [a for a in all_assets
                      if tahun_aset(a, ambil_tahun) in tahun]

    for kunci, field in DIMENSI:
        dipilih = set(bersihkan(f.get(kunci)))
        if dipilih:
            all_assets = [a for a in all_assets if _teks(a.get(field)) in dipilih]

    dari, sampai = _teks(f.get("dari")), _teks(f.get("sampai"))
    if dari or sampai:
        all_assets = [a for a in all_assets if dalam_rentang(a, dari, sampai)]

    return satker_acts, all_assets


def ada_yang_aktif(filter_dipilih) -> bool:
    """Apakah ada filter yang benar-benar menyempitkan laporan.

    Dipakai layar untuk menyatakan bahwa angka yang tampil BUKAN keseluruhan
    satker. Laporan tersaring yang tak mengatakan dirinya tersaring adalah
    laporan yang menyesatkan pembacanya.
    """
    f = filter_dipilih or {}
    if any(bersihkan(f.get(k)) for k in ("kegiatan", "tahun", *[d[0] for d in DIMENSI])):
        return True
    return bool(_teks(f.get("dari")) or _teks(f.get("sampai")))
