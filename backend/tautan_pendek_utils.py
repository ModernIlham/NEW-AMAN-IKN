"""Pemendek tautan INTERNAL — untuk link yang dibagikan keluar aplikasi.

KENAPA DIBANGUN SENDIRI, BUKAN MEMAKAI TinyURL/PicSee
-----------------------------------------------------
Link e-sign membawa TOKEN TANDA TANGAN di query string (±315 dari 396
karakter panjangnya). Siapa pun yang memegang link itu bisa menandatangani
dokumen BMN resmi atas nama orang yang dituju — ia KREDENSIAL, bukan sekadar
alamat. Menitipkannya ke pemendek pihak ketiga berarti menyimpan kredensial
itu di server pihak lain, permanen, di luar kendali satker; kode pendek
layanan publik pun terbukti bisa disapu/ditebak. Aplikasi ini sudah punya
domain sendiri dan MongoDB sendiri, jadi memendekkan "di rumah sendiri"
menghasilkan tautan yang sama pendeknya, gratis, tanpa kuota, dan tidak
menyerahkan apa pun ke luar.

PANJANG KODE — dan kenapa tidak dipendekkan lagi
------------------------------------------------
10 karakter base62 ≈ 8,4 × 10^17 kemungkinan (±2^59,5). Kode ini BERDIRI
MENGGANTIKAN tautan ber-kredensial, jadi ia harus sama sulitnya ditebak;
dipadu batas laju di endpoint penukaran dan masa berlaku yang mengikuti
tautan aslinya. Memangkas kode demi tampilan = memperlemah gerbang tanda
tangan, bukan sekadar merapikan — itu sebabnya angkanya tidak diturunkan.

Anggaran panjang tautan (domain sekarang):

    https://  amanikn-inventarisasi.com  /s/  K7m2QxV9pT
    └─ 8 ─┘  └──────── 25 ────────────┘ └3┘  └── 10 ──┘   = 46 karakter

25 karakter dari 46 adalah nama domainnya sendiri — TIDAK bisa dikecilkan
dari sisi kode. Satu-satunya tuas yang tersisa adalah menyewa domain yang
lebih pendek; `APP_PUBLIC_URL` cukup diganti dan seluruh tautan ikut memendek
tanpa perubahan kode.
"""
import os
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

from db import db

# base62 — aman di URL, tanpa karakter yang perlu di-escape.
_ABJAD = string.ascii_letters + string.digits
PANJANG_KODE = 10
_MAKS_COBA = 5          # tabrakan kode praktis mustahil; ini jaring pengaman


def basis_url_publik() -> str:
    """URL publik aplikasi untuk membangun tautan absolut.

    APP_PUBLIC_URL lebih dulu, lalu origin non-localhost pertama dari
    ALLOWED_ORIGINS/CORS_ORIGINS (deploy nyata selalu mengisi salah satunya).
    '' berarti pemanggil harus memakai tautan relatif.
    """
    u = str(os.environ.get("APP_PUBLIC_URL", "")).strip().rstrip("/")
    if u:
        return u
    sumber = (str(os.environ.get("ALLOWED_ORIGINS", ""))
              or str(os.environ.get("CORS_ORIGINS", "")))
    for o in sumber.split(","):
        o = o.strip().rstrip("/")
        if (o.startswith("http") and "localhost" not in o
                and "127.0.0.1" not in o):
            return o
    return ""


def kode_acak(n: int = PANJANG_KODE) -> str:
    """Kode acak kriptografis (secrets, bukan random) — lihat catatan panjang
    kode di docstring modul."""
    return "".join(secrets.choice(_ABJAD) for _ in range(n))


def url_pendek(kode: str) -> str:
    """Tautan pendek utuh. Relatif bila basis URL tak diketahui (dev lokal)."""
    rel = f"/s/{kode}"
    basis = basis_url_publik()
    return (basis + rel) if basis else rel


def _sekarang_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def buat_tautan_pendek(tujuan: str, jenis: str, ref: str = "",
                             sub_ref: str = "", kode_satker: str = "",
                             dibuat_oleh: str = "",
                             kedaluwarsa: Optional[str] = None,
                             pakai_ulang: bool = False) -> str:
    """Daftarkan `tujuan` dan kembalikan KODE pendeknya ('' bila gagal).

    `jenis` + `ref` menandai DOKUMENNYA (mis. satu permintaan TTD), `sub_ref`
    menandai satu bagian di dalamnya (mis. satu penanda tangan). Dua lapis ini
    dibutuhkan karena pencabutannya berbeda: menerbitkan ulang link SEORANG
    penanda tangan hanya boleh mematikan tautan orang itu, sedangkan
    membatalkan permintaan mematikan tautan SEMUA orang.

    `kedaluwarsa` sebaiknya disamakan dengan masa berlaku token di dalam
    `tujuan` — tautan pendek yang hidup lebih lama dari tokennya hanya
    menyesatkan penerima.

    Mengembalikan '' alih-alih melempar: memendekkan tautan adalah kenyamanan,
    dan kegagalannya TIDAK boleh menggagalkan penerbitan permintaan TTD. Yang
    memanggil wajib jatuh kembali ke tautan panjang.
    """
    tujuan = str(tujuan or "").strip()
    if not tujuan:
        return ""
    if pakai_ulang:
        # QR verifikasi dirender ULANG setiap kali dokumen ber-TTD diunduh.
        # Tanpa pemakaian ulang, tiap unduhan melahirkan kode baru: koleksinya
        # membengkak dan — lebih buruk — QR pada dua salinan dokumen yang sama
        # berisi alamat berbeda, sehingga sulit ditelusuri.
        try:
            lama = await db.tautan_pendek.find_one(
                {"jenis": str(jenis), "ref": str(ref or ""),
                 "sub_ref": str(sub_ref or ""), "tujuan": tujuan,
                 "dicabut": False},
                {"_id": 0, "kode": 1})
            if lama and lama.get("kode"):
                return str(lama["kode"])
        except Exception:
            pass
    for _ in range(_MAKS_COBA):
        kode = kode_acak()
        try:
            await db.tautan_pendek.insert_one({
                "kode": kode,
                "tujuan": tujuan,
                "jenis": str(jenis or "lain"),
                "ref": str(ref or ""),
                "sub_ref": str(sub_ref or ""),
                "kode_satker": str(kode_satker or ""),
                "dibuat_oleh": str(dibuat_oleh or ""),
                "created_at": _sekarang_iso(),
                "kedaluwarsa": kedaluwarsa,
                "dicabut": False,
                "hit": 0,
                "terakhir_dibuka": None,
            })
            return kode
        except Exception:
            # Duplikat kode (unik) → coba kode lain. Galat lain (Mongo mati)
            # akan habis percobaannya dan jatuh ke '' → pemanggil pakai
            # tautan panjang.
            continue
    return ""


def _sudah_lewat(kedaluwarsa) -> bool:
    if not kedaluwarsa:
        return False
    try:
        t = datetime.fromisoformat(str(kedaluwarsa).replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        return False        # nilai tak terbaca ≠ mati; jangan matikan tautan sah
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t < datetime.now(timezone.utc)


async def resolve_tautan(kode: str) -> Optional[str]:
    """Tujuan untuk `kode`, atau None bila tak ada / dicabut / kedaluwarsa.

    Penghitung buka dimutakhirkan sebaik-usaha — statistik tak boleh
    menggagalkan pengalihan.
    """
    kode = str(kode or "").strip()
    if not kode or len(kode) > 64:
        return None
    doc = await db.tautan_pendek.find_one({"kode": kode}, {"_id": 0})
    if not doc or doc.get("dicabut") or _sudah_lewat(doc.get("kedaluwarsa")):
        return None
    try:
        await db.tautan_pendek.update_one(
            {"kode": kode},
            {"$inc": {"hit": 1}, "$set": {"terakhir_dibuka": _sekarang_iso()}})
    except Exception:
        pass
    return str(doc.get("tujuan") or "") or None


async def cabut_tautan(jenis: str, ref: str, sub_ref: str = "") -> int:
    """Matikan tautan pendek — tautan pendek tak boleh hidup lebih lama dari
    tautan panjang yang diwakilinya.

    `sub_ref` kosong = SELURUH tautan dokumen itu (permintaan TTD dibatalkan).
    `sub_ref` terisi = hanya bagian itu (link SEORANG penanda tangan
    diterbitkan ulang) — mencabut semuanya di sini akan mematikan tautan
    penanda tangan LAIN yang masih sah dan belum meneken.
    """
    if not str(ref or "").strip():
        return 0
    q = {"jenis": str(jenis), "ref": str(ref), "dicabut": False}
    if str(sub_ref or "").strip():
        q["sub_ref"] = str(sub_ref)
    try:
        r = await db.tautan_pendek.update_many(q, {"$set": {"dicabut": True}})
        return int(getattr(r, "modified_count", 0) or 0)
    except Exception:
        return 0
