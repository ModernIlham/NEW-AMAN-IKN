"""Catatan hasil PERCOBAAN terakhir tiap layanan kompresi gambar — bagian murni.

KENAPA ADA. Laporan pemilik: "kompresi dengan compresto tidak berfungsi".
Menelusurinya membuka dua cacat yang saling menutupi:

1. `compress_with_compresto` / `compress_with_uploadcare` menelan SETIAP
   kegagalan menjadi `return None` — kunci salah, host tak terjangkau, kontrak
   berubah, kuota habis, semuanya menghasilkan hasil yang sama. Rantai lalu
   jatuh ke Pillow dan endpoint menjawab `success: true, method: "pillow"`.
   Dari kursi operator, layanan itu "tidak berfungsi" TANPA satu pun petunjuk
   sebabnya; satu-satunya jejak ada di log server yang tak bisa dia buka.

2. Indikator kuota melaporkan `"available": bool(COMPRESTO_API_KEY)` — sekadar
   "env var terisi", bukan "layanan menjawab". Kebohongan yang sama pernah
   diperbaiki untuk iLovePDF; di sini ia masih hidup, dan justru itulah yang
   membuat layar tampak sehat sementara kompresinya tak pernah jalan.

Modul ini menyimpan hasil percobaan TERAKHIR per layanan supaya jawabannya bisa
ditanyakan lewat API: berhasil atau gagal, kapan, dan KENAPA.

Sengaja di memori proses (bukan basis data): ini data diagnostik yang murah,
berumur pendek, dan tak layak menambah tulisan ke DB pada jalur panas unggah
foto. Hilang saat restart — dan itu memang benar, karena yang ingin diketahui
adalah keadaan SEKARANG.
"""
import threading
from typing import Optional

__all__ = [
    "STATUS_BELUM_DICOBA", "STATUS_BERHASIL", "STATUS_GAGAL", "STATUS_TAK_DISETEL",
    "catat_percobaan", "ambil_status", "reset_status", "ringkas_layanan",
]

STATUS_BELUM_DICOBA = "belum_dicoba"    # kunci ada, tapi belum pernah dipakai sejak proses hidup
STATUS_BERHASIL = "berhasil"
STATUS_GAGAL = "gagal"
STATUS_TAK_DISETEL = "tak_disetel"      # kunci API kosong

_kunci = threading.Lock()
_catatan = {}   # nama layanan -> dict


def catat_percobaan(layanan: str, berhasil: bool, alasan: str = "",
                    kode_http: Optional[int] = None, waktu: Optional[str] = None):
    """Catat hasil satu percobaan kompresi.

    `waktu` disuntikkan (bukan diambil dari jam sistem di dalam) agar bisa diuji
    tanpa membekukan waktu — pola yang sama dipakai modul murni lain di repo ini.
    """
    with _kunci:
        _catatan[layanan] = {
            "status": STATUS_BERHASIL if berhasil else STATUS_GAGAL,
            "alasan": str(alasan or "")[:300],
            "kode_http": kode_http,
            "waktu": waktu,
        }


def ambil_status(layanan: str):
    """Catatan terakhir layanan, atau None bila belum pernah dicoba."""
    with _kunci:
        rec = _catatan.get(layanan)
        return dict(rec) if rec else None


def reset_status(layanan: Optional[str] = None):
    """Kosongkan catatan (dipakai uji, dan saat kunci API diganti)."""
    with _kunci:
        if layanan is None:
            _catatan.clear()
        else:
            _catatan.pop(layanan, None)


def ringkas_layanan(layanan: str, kunci_terpasang: bool, kuota_terpakai: int,
                    kuota_batas: int):
    """Bentuk ringkasan satu layanan untuk endpoint status.

    `tersedia` DIJAWAB JUJUR: True hanya bila percobaan terakhir memang
    berhasil. Kunci terpasang tapi belum pernah dipakai → `belum_dicoba`, BUKAN
    "tersedia" — karena tak ada satu pun bukti bahwa layanannya menjawab.
    """
    if not kunci_terpasang:
        return {
            "service": layanan,
            "status": STATUS_TAK_DISETEL,
            "tersedia": False,
            "alasan": "Kunci API belum dipasang di .env server",
            "kode_http": None,
            "waktu_percobaan_terakhir": None,
            "used": kuota_terpakai,
            "limit": kuota_batas,
            "remaining": max(0, kuota_batas - kuota_terpakai),
        }

    rec = ambil_status(layanan)
    if rec is None:
        return {
            "service": layanan,
            "status": STATUS_BELUM_DICOBA,
            "tersedia": False,
            "alasan": "Kunci terpasang, tetapi layanan belum pernah dipanggil "
                      "sejak server terakhir dijalankan — unggah satu foto untuk mengujinya",
            "kode_http": None,
            "waktu_percobaan_terakhir": None,
            "used": kuota_terpakai,
            "limit": kuota_batas,
            "remaining": max(0, kuota_batas - kuota_terpakai),
        }

    return {
        "service": layanan,
        "status": rec["status"],
        "tersedia": rec["status"] == STATUS_BERHASIL,
        "alasan": rec["alasan"],
        "kode_http": rec["kode_http"],
        "waktu_percobaan_terakhir": rec["waktu"],
        "used": kuota_terpakai,
        "limit": kuota_batas,
        "remaining": max(0, kuota_batas - kuota_terpakai),
    }
