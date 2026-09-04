"""Penyaring laporan gabungan satker — helper MURNI, tanpa I/O dan tanpa DB.

Permintaan pemilik: laporan gabungan harus INTERAKTIF — dapat memilih
kegiatan mana saja yang ikut, dengan filter lanjutan yang menerima **lebih
dari satu pilihan pada filter yang sama** (tahun, status, kondisi, lokasi),
plus rentang tanggal.

Tiga keputusan yang membentuk modul ini:

1. **Sebuah dimensi tak pernah menyempitkan daftarnya SENDIRI.** Kalau
   daftar tahun disusun dari aset yang sudah tersaring menurut tahun, memilih
   2023 akan membuat 2024 lenyap — dan pengguna terkurung: tak ada lagi kotak
   untuk mengembalikannya. Ini jebakan klasik filter bertingkat, dan ia hanya
   terlihat setelah seseorang benar-benar terjebak.

   **Kegiatan adalah kekecualian yang disengaja** (permintaan pemilik):
   memilih kegiatan MENYEMPITKAN daftar tahun/status/kondisi/lokasi, sebab
   kegiatan adalah puncak hierarki — satu kegiatan memang punya himpunan
   lokasi dan tahunnya sendiri, dan menawarkan lokasi milik kegiatan lain
   hanya menawarkan hasil kosong. Daftar kegiatan sendiri TIDAK PERNAH
   disempitkan oleh apa pun, jadi jalan pulang selalu ada.

   Nilai yang masih tercentang tetapi tak ada di kegiatan terpilih **tetap
   ditampilkan, bertanda `di_luar`** — bukan dihapus. Menghapusnya membuat
   centangnya lenyap dari layar sementara filternya tetap berlaku: laporan
   kosong tanpa sebab yang terlihat, dan tanpa kotak untuk membatalkannya.

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


def aset_dalam_kegiatan(all_assets, filter_dipilih):
    """Aset milik kegiatan yang DIPILIH. Tanpa pilihan kegiatan = seluruhnya.

    Inilah lingkup yang membentuk daftar pilihan dimensi lain (lihat #1).
    """
    keg = set(bersihkan((filter_dipilih or {}).get("kegiatan")))
    if not keg:
        return all_assets
    return [a for a in all_assets if a.get("activity_id") in keg]


def _rakit_opsi(tersedia, terpilih, urut_terbalik=False):
    """`[{"nilai","label","di_luar"}]` — tersedia dulu, lalu yang di luar.

    `di_luar` menandai nilai yang MASIH tercentang tetapi tak ada pada
    kegiatan terpilih. Ia sengaja tetap muncul; lihat #1.
    """
    ada = sorted({v for v in tersedia if v}, reverse=urut_terbalik)
    keluar = [{"nilai": v, "label": v, "di_luar": False} for v in ada]
    sisa = sorted({v for v in (terpilih or []) if v and v not in set(ada)},
                  reverse=urut_terbalik)
    keluar += [{"nilai": v, "label": v, "di_luar": True} for v in sisa]
    return keluar


def pilihan_filter(satker_acts, all_assets, ambil_tahun,
                   filter_dipilih=None) -> dict:
    """Nilai yang tersedia untuk tiap dimensi (lihat #1).

    Bentuknya seragam `[{"nilai", "label", "di_luar"}]` untuk SETIAP dimensi,
    termasuk kegiatan yang nilainya id dan labelnya nama. Template karenanya
    cukup mengulang satu bentuk; merakit pasangan nilai-label di dalam Jinja
    butuh filter buatan sendiri, dan logika yang pindah ke template adalah
    logika yang tak lagi bisa diuji.
    """
    f = filter_dipilih or {}
    dalam = aset_dalam_kegiatan(all_assets, f)

    return {
        # Daftar kegiatan TIDAK PERNAH disempitkan — ia jalan pulangnya.
        "kegiatan": [{"nilai": a.get("id", ""),
                      "label": a.get("nama_kegiatan") or a.get("id", ""),
                      "di_luar": False}
                     for a in satker_acts if a.get("id")],
        "tahun": _rakit_opsi((tahun_aset(a, ambil_tahun) for a in dalam),
                             bersihkan(f.get("tahun")), urut_terbalik=True),
        **{kunci: _rakit_opsi((_teks(a.get(field)) for a in dalam),
                              bersihkan(f.get(kunci)))
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
