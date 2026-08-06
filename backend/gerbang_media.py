"""GERBANG MEDIA — satu aturan kompresi untuk satu aplikasi utuh.

Permintaan pemilik, apa adanya: *"pastikan kembali setiap gerbang agar mematuhi
aturan agar terkompresi terlebih dahulu sesuai jenjang yang ada apapun itu dan
di modul manapun dan di satker manapun dan rule apapun universal untuk 1
aplikasi utuh. baik foto maupun pdf."*

Pemicunya laporan lapangan: foto dari KAMERA yang disimpan dari HALAMAN EDIT
aset tidak terkompres. Penelusurannya menemukan `routes/assets.py` memang tak
pernah memanggil rantai kompresi — hanya `routes/activities.py` dan
`routes/batch.py` yang memanggilnya. Audit menyeluruh atas 113 jalur tulis
bita menemukan 25 jalur lain bernasib sama, dan 7 jalur yang justru **TIDAK
BOLEH** dikompres.

KENAPA MODUL SENDIRI, BUKAN MIDDLEWARE ATAU PEMBUNGKUS `fs_bucket`:

  • Middleware (`server.py`) hanya melihat RESPONS, bukan bita yang ditulis.
  • Membungkus `fs_bucket` di `db.py` buta terhadap tulis INLINE ke dokumen
    Mongo (`routes/assets.py` document_checklist, logo di `routes/reports.py`),
    buta terhadap `upload_from_stream` (foto pegawai), dan akan mengompres
    ulang blob RESTORE — yang wajib bita identik.

Maka: satu modul dengan dua pintu — `olah_media` (murni, untuk jalur INLINE)
dan `tulis_media` (olah + tulis GridFS + metadata jujur).

ATURAN TUNGGALNYA, berlaku modul mana pun dan satker mana pun:

  1. Jenis berkas ditentukan MAGIC BYTE, bukan ekstensi — ekstensi bisa
     dipalsukan, dan sebagian modul memang hanya memeriksa ekstensi.
  2. PDF ber-TANDA TANGAN DIGITAL atau terenkripsi TIDAK PERNAH disentuh.
     Penjaganya dipanggil DI SINI, sebelum penyedia mana pun — dulu ia hidup
     di dalam `kompres_pdf_lokal` sementara iLovePDF berjalan lebih dulu,
     sehingga dokumen ber-TTE bisa dikirim ke pihak ketiga dan tanda tangannya
     batal.
  3. Gambar ber-ALFA hanya lewat Pillow lossless. Tiga dari empat mata rantai
     memaksa JPEG; spesimen tanda tangan dan logo instansi akan jadi kotak
     buram menimpa naskah.
  4. Gambar opak KECIL (≤ `AMBANG_JARINGAN`) cukup Pillow lokal — membakar
     kuota berbayar untuk berkas yang sudah kecil itu pemborosan.
  5. Hasil dipakai HANYA bila lebih kecil. Kalau tidak, bita ASLI dikembalikan.
  6. IDEMPOTEN: bita yang sudah lewat gerbang (atau sudah WebP) dilewati.
  7. FAIL-OPEN: kegagalan kompresi tak boleh menggagalkan unggahan pengguna.
     Foto yang gagal dikompres tetap tersimpan utuh.
"""
import asyncio
import io
import logging
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

__all__ = [
    "AMBANG_JARINGAN", "VERSI_GERBANG", "HasilMedia",
    "jenis_media", "punya_alfa", "sudah_diolah", "olah_media", "tulis_media",
    "samakan_ekstensi",
]

# Penanda versi pada metadata. Naikkan bila aturan berubah dan blob lama perlu
# diolah ulang; jangan dipakai untuk hal lain.
VERSI_GERBANG = 1

# Di bawah ambang ini, layanan berkuota TIDAK dipanggil — Pillow lokal saja.
# Foto kamera lapangan biasanya 2–5 MB, jadi ambang ini tak menghalangi yang
# memang butuh; ia hanya mencegah kuota habis untuk ikon dan avatar.
AMBANG_JARINGAN = 300 * 1024


class HasilMedia:
    """Hasil olahan satu berkas. Sengaja kelas kecil, bukan tuple: pemanggil
    membaca `content_type` dan `metode`, dan tuple posisional sudah pernah
    membuat label tertukar."""

    __slots__ = ("bita", "content_type", "metode", "ukuran_asli", "ukuran_hasil")

    def __init__(self, bita, content_type, metode, ukuran_asli, ukuran_hasil):
        self.bita = bita
        self.content_type = content_type
        self.metode = metode
        self.ukuran_asli = ukuran_asli
        self.ukuran_hasil = ukuran_hasil

    @property
    def berubah(self) -> bool:
        return self.metode not in ("", "none", "lewat")

    def metadata(self) -> dict:
        """Potongan metadata WAJIB pada tiap blob yang lewat gerbang."""
        return {"content_type": self.content_type, "size": self.ukuran_hasil,
                "kompresi": {"metode": self.metode, "v": VERSI_GERBANG,
                             "asli": self.ukuran_asli}}


# ---------------------------------------------------------------------------
# Pengenalan jenis — MAGIC BYTE, bukan ekstensi
# ---------------------------------------------------------------------------

def jenis_media(data: bytes) -> str:
    """"pdf" | "gambar" | "lain" — dari isi berkas, bukan namanya.

    Ekstensi bisa dipalsukan, dan beberapa modul memang hanya memeriksa
    ekstensi. Gerbang tak boleh ikut tertipu: berkas yang menyamar cukup
    diperlakukan sebagai "lain" dan lewat tanpa disentuh.
    """
    if not data:
        return "lain"
    b = bytes(data[:16])
    if b.startswith(b"%PDF"):
        return "pdf"
    if (b.startswith(b"\xff\xd8\xff") or b.startswith(b"\x89PNG\r\n\x1a\n")
            or b.startswith(b"GIF87a") or b.startswith(b"GIF89a")
            or (b.startswith(b"RIFF") and bytes(data[8:12]) == b"WEBP")
            or b.startswith(b"BM")):
        return "gambar"
    return "lain"


def punya_alfa(data: bytes) -> bool:
    """True bila gambar membawa transparansi yang HARUS dipertahankan.

    Spesimen tanda tangan dan logo instansi bergantung padanya: diratakan ke
    JPEG, keduanya berubah jadi kotak buram yang menimpa naskah dokumen resmi.
    """
    try:
        from PIL import Image as PILImage
        img = PILImage.open(io.BytesIO(data))
        return img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info)
    except Exception:
        return False


def sudah_diolah(metadata) -> bool:
    """True bila blob ini TIDAK boleh diolah lagi.

    Dua sumber: penanda gerbang sendiri, dan `webp: True` milik konverter WebP
    latar belakang — yang sudah membakar kuota Tinify untuk blob itu.
    """
    m = metadata or {}
    if m.get("webp") is True:
        return True
    k = m.get("kompresi")
    return isinstance(k, dict) and k.get("v") is not None


# ---------------------------------------------------------------------------
# Olahan
# ---------------------------------------------------------------------------

async def _olah_pdf(data: bytes, nama: str) -> HasilMedia:
    import pdf_compress_utils as pcu

    asli = len(data)

    # PENJAGA PERTAMA, sebelum penyedia mana pun. Dulu ia hidup di dalam
    # `kompres_pdf_lokal` sementara iLovePDF dipanggil LEBIH DULU — dokumen
    # ber-tanda tangan digital bisa dikirim ke pihak ketiga dan tanda
    # tangannya batal. Kebijakan modulnya sendiri: "ragu = anggap bertanda
    # tangan".
    def _terkunci() -> bool:
        try:
            from pypdf import PdfReader
            pembaca = PdfReader(io.BytesIO(data))
            if getattr(pembaca, "is_encrypted", False):
                return True
            return pcu._pdf_bertanda_tangan(pembaca)
        except Exception:
            return True     # tak terbaca → jangan sentuh

    if await asyncio.to_thread(_terkunci):
        return HasilMedia(data, "application/pdf", "lewat", asli, asli)

    try:
        from routes.pdf_compress import compress_pdf_ilovepdf
        hasil, metode, _alasan = await compress_pdf_ilovepdf(
            data, pcu.nama_berkas_aman(nama))
        if hasil and pcu.layak_dipakai(data, hasil):
            return HasilMedia(hasil, "application/pdf", metode or "ilovepdf",
                              asli, len(hasil))
    except Exception as e:
        logger.warning("Gerbang: iLovePDF dilewati (%s)", e)

    try:
        lokal = await asyncio.to_thread(pcu.kompres_pdf_lokal, data)
        if lokal and pcu.layak_dipakai(data, lokal):
            return HasilMedia(lokal, "application/pdf", "pypdf", asli, len(lokal))
    except Exception as e:
        logger.warning("Gerbang: kompresi PDF lokal gagal (%s)", e)

    return HasilMedia(data, "application/pdf", "none", asli, asli)


async def _olah_gambar(data: bytes, *, izinkan_jaringan: bool) -> HasilMedia:
    from routes.media import _FUNGSI_KOMPRESI, compress_with_pillow
    from kompresi_rantai import URUTAN

    asli = len(data)

    # Alfa → HANYA Pillow. Cabang alfa di `compress_with_pillow` menyimpan PNG
    # lossless dan mengembalikan bita ASLI bila hasilnya tak lebih kecil.
    if not izinkan_jaringan or punya_alfa(data):
        try:
            # `asyncio.to_thread` BUKAN hiasan: Pillow itu CPU-bound dan
            # sebelumnya dipanggil langsung di dalam coroutine, membekukan
            # seluruh server selama tiap unggahan. Gerbang memperbanyak
            # panggilan ini belasan kali lipat.
            hasil = await asyncio.to_thread(compress_with_pillow, data)
            if hasil and len(hasil) < asli:
                return HasilMedia(hasil, _sniff_gambar(hasil), "pillow", asli, len(hasil))
        except Exception as e:
            logger.warning("Gerbang: Pillow gagal (%s)", e)
        return HasilMedia(data, _sniff_gambar(data), "none", asli, asli)

    for nama_layanan in URUTAN:
        fn = _FUNGSI_KOMPRESI.get(nama_layanan)
        if fn is None:
            continue    # "pillow" ditangani di bawah
        try:
            hasil = await fn(data)
        except Exception as e:
            logger.warning("Gerbang: %s gagal (%s)", nama_layanan, e)
            continue
        if hasil and len(hasil) < asli:
            return HasilMedia(hasil, _sniff_gambar(hasil), nama_layanan,
                              asli, len(hasil))

    try:
        hasil = await asyncio.to_thread(compress_with_pillow, data)
        if hasil and len(hasil) < asli:
            return HasilMedia(hasil, _sniff_gambar(hasil), "pillow", asli, len(hasil))
    except Exception as e:
        logger.warning("Gerbang: Pillow penutup gagal (%s)", e)

    return HasilMedia(data, _sniff_gambar(data), "none", asli, asli)


def _sniff_gambar(data: bytes) -> str:
    """Content-type dari BITA HASIL, bukan dari label maupun ekstensi.

    Rantai lama selalu melabeli hasilnya `image/jpeg` — padahal cabang alfa
    mengembalikan PNG. Metadata yang berbohong membuat penyaji mengirim header
    yang salah, dan peramban menampilkan berkas rusak.
    """
    b = bytes(data[:16])
    if b.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if b.startswith(b"GIF87a") or b.startswith(b"GIF89a"):
        return "image/gif"
    if b.startswith(b"RIFF") and bytes(data[8:12]) == b"WEBP":
        return "image/webp"
    return "image/jpeg"


_EKSTENSI_TIPE = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
    "image/webp": ".webp", "application/pdf": ".pdf",
}


def samakan_ekstensi(nama: str, content_type: str) -> str:
    """Betulkan ekstensi nama berkas agar cocok dengan isi yang SEBENARNYA.

    Tinify, Compresto, dan Uploadcare mengembalikan JPEG walau masukannya PNG.
    Modul-modul lampiran menyimpan `filename` dan `content_type` SENDIRI di
    dokumen Mongo — di luar metadata GridFS — sehingga tanpa penyamaan ini
    pengguna mengunduh berkas bernama `.png` yang isinya JPEG, dan sebagian
    aplikasi penampil menolak membukanya.

    Nama tanpa ekstensi dikenal, atau tipe di luar daftar, dibiarkan apa adanya:
    menebak lebih berbahaya daripada tidak menyentuh.
    """
    ext = _EKSTENSI_TIPE.get(content_type or "")
    if not ext or not nama:
        return nama
    pangkal, titik, lama = nama.rpartition(".")
    if not titik:
        return nama
    lama = "." + lama.lower()
    if lama == ext or (lama in (".jpeg", ".jpg") and ext == ".jpg"):
        return nama
    if lama not in _EKSTENSI_TIPE.values() and lama != ".jpeg":
        return nama     # ekstensi asing (.dwg, .zip) — bukan urusan gerbang
    return pangkal + ext


async def olah_media(data: bytes, *, kelas: str = "auto",
                     nama: str = "") -> HasilMedia:
    """Olah bita menurut aturan tunggal. TIDAK menyentuh basis data.

    `kelas`:
      "auto"    — tentukan sendiri dari magic byte (bawaan)
      "alfa"    — paksa jalur lossless lokal (logo, spesimen TTD, overlay denah)
      "mentah"  — jangan sentuh sama sekali (restore, artefak job)
    """
    asli = len(data or b"")
    if not data:
        return HasilMedia(data, "application/octet-stream", "lewat", 0, 0)

    if kelas == "mentah":
        return HasilMedia(data, "application/octet-stream", "lewat", asli, asli)

    jenis = jenis_media(data)

    if kelas == "alfa":
        if jenis != "gambar":
            return HasilMedia(data, "application/octet-stream", "lewat", asli, asli)
        return await _olah_gambar(data, izinkan_jaringan=False)

    if jenis == "pdf":
        return await _olah_pdf(data, nama)
    if jenis == "gambar":
        # Berkas kecil tak dikirim ke layanan berkuota — penutup lokal memang
        # bagian dari desain rantai, bukan darurat.
        return await _olah_gambar(data, izinkan_jaringan=asli > AMBANG_JARINGAN)

    # Bukan gambar/PDF (XLSX, ZIP, SHP, DOCX…) — bukan urusan gerbang.
    return HasilMedia(data, "application/octet-stream", "lewat", asli, asli)


async def tulis_media(data: bytes, *, nama: str, content_type: str = "",
                      kelas: str = "auto", metadata=None) -> tuple:
    """Olah lalu tulis ke GridFS. Kembalikan `(str(file_id), metadata_final)`.

    Metadata hasil SELALU memuat `content_type` yang di-sniff dari bita akhir
    dan penanda `kompresi` — dua hal yang membuat pengolahan ganda mustahil dan
    penyaji tak pernah salah header.
    """
    from bson import ObjectId
    from db import fs_bucket

    meta_awal = dict(metadata or {})
    if sudah_diolah(meta_awal):
        hasil = HasilMedia(data, content_type or "application/octet-stream",
                           "lewat", len(data), len(data))
    else:
        try:
            hasil = await olah_media(data, kelas=kelas, nama=nama)
        except Exception as e:
            # FAIL-OPEN. Unggahan pengguna tak boleh gagal gara-gara kompresi.
            logger.warning("Gerbang: olah gagal, simpan apa adanya (%s)", e)
            hasil = HasilMedia(data, content_type or "application/octet-stream",
                               "none", len(data), len(data))

    meta = dict(meta_awal)
    meta.update(hasil.metadata())
    if hasil.content_type == "application/octet-stream" and content_type:
        meta["content_type"] = content_type

    # Nama berkas disamakan dengan isi SEBELUM ditulis, bukan sesudah: rantai
    # gambar mengembalikan JPEG walau masukannya PNG, dan nama yang tertinggal
    # `.png` akan ikut terbawa ke unduhan pengguna.
    nama_akhir = samakan_ekstensi(nama, meta.get("content_type") or "") or nama
    meta["filename"] = nama_akhir or f"media_{uuid.uuid4()}"

    file_id = ObjectId()
    grid_in = fs_bucket.open_upload_stream_with_id(
        file_id, filename=meta["filename"], metadata=meta)
    await grid_in.write(hasil.bita)
    await grid_in.close()
    return str(file_id), meta
