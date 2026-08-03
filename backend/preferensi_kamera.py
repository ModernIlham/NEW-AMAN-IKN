"""PREFERENSI KAMERA LAPANGAN yang MELEKAT PADA AKUN.

Petugas yang berganti HP (atau memakai HP pinjaman) harus tetap memotret
dengan setelan yang sama, supaya hasil foto satu satker seragam di laporan &
stiker. Karena itu nilainya disimpan di dokumen user — bukan di perangkat.

Aturan normalisasinya CERMIN dari `frontend/src/lib/preferensiKamera.js`. Bila
salah satu berubah tanpa yang lain, setelan yang disimpan bisa berbeda dari
yang dipakai kamera; keduanya punya uji sendiri agar pergeseran itu ketahuan.
"""

ORIENTASI = ("auto", "potret", "lanskap")

RESOLUSI_MIN = 640
RESOLUSI_MAX = 4096
KUALITAS_MIN = 50
KUALITAS_MAX = 100

BAWAAN = {"orientasi": "auto", "resolusi": 1920, "kualitas": 85}


def _jepit(n: float, bawah: int, atas: int) -> int:
    return int(round(min(atas, max(bawah, n))))


def _angka(v):
    """Ubah ke float, atau None bila bukan angka yang masuk akal.

    `bool` DITOLAK meski `float(True)` sah di Python: tanpa penjagaan ini
    `{"resolusi": true}` tersimpan diam-diam sebagai 640 px — foto jadi kecil
    tanpa ada yang tahu sebabnya.
    """
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def normalkan(raw) -> dict:
    """Bersihkan nilai apa pun menjadi preferensi yang sah.

    Field rusak/usang JATUH KE BAWAAN, bukan menolak seluruh permintaan:
    setelan kamera tak boleh membuat petugas gagal memotret di lapangan.
    """
    p = raw if isinstance(raw, dict) else {}

    orientasi = p.get("orientasi")
    if orientasi not in ORIENTASI:
        orientasi = BAWAAN["orientasi"]

    res = _angka(p.get("resolusi"))
    kual = _angka(p.get("kualitas"))
    return {
        "orientasi": orientasi,
        "resolusi": _jepit(res, RESOLUSI_MIN, RESOLUSI_MAX) if res is not None
        else BAWAAN["resolusi"],
        "kualitas": _jepit(kual, KUALITAS_MIN, KUALITAS_MAX) if kual is not None
        else BAWAAN["kualitas"],
    }
