"""Aturan murni foto untuk kompresi bertahap, tanpa jaringan atau tulis berkas.

Satu persen adalah penghematan TAMBAHAN dibanding foto sebelum putaran ini,
bukan janji bahwa foto akhir tinggal satu persen ukuran unggahan awal.
Hasil yang meragukan ditolak: pemanggil wajib mempertahankan sumbernya.
"""
import io
import math

from PIL import Image, ImageChops, ImageStat


AMBANG_HEMAT_PERSEN = 1.0
MAKS_PIKSEL_FOTO = 40_000_000

# Penjaga perubahan besar, BUKAN ukuran perseptual/OCR atau bukti bahwa lossy
# identik dengan sumber. Bandingkan SEMUA piksel terlihat tanpa resize/sampling.
# Blok membatasi memori kerja dan mencegah kerusakan lokal tenggelam dalam
# rata-rata seluruh foto. Lebih konservatif = hasil ditolak, sumber tetap utuh.
SISI_BLOK = 128
MAKS_RMS_GLOBAL = 12.0
MAKS_RMS_BLOK = 24.0


def hemat_persen(ukuran_lama: int, ukuran_baru: int) -> float:
    """Persentase penghematan; negatif bila membesar, nol bila input tidak sah."""
    try:
        lama, baru = float(ukuran_lama), float(ukuran_baru)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    if not math.isfinite(lama) or not math.isfinite(baru) or lama <= 0 or baru < 0:
        return 0.0
    hemat = (lama - baru) / lama * 100.0
    return hemat if math.isfinite(hemat) else 0.0


def _buka_foto(data: bytes, *, wajib_webp=False):
    """Periksa struktur lalu dekode penuh; pemanggil menutup objek hasil."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise ValueError("Bita foto kosong atau tidak sah")
    # Pustaka lain bisa mengaktifkan LOAD_TRUNCATED_IMAGES secara global:
    # dekoder JPEG Pillow kemudian menyisipkan EOI sendiri saat input habis.
    # Jangan mengubah flag global di worker/thread. Foto JPEG tanpa penutup
    # nyata harus ditahan meskipun dekoder permisif bisa menampilkannya.
    if data[:2] == b"\xff\xd8" and not data.endswith(b"\xff\xd9"):
        raise ValueError("Kontainer JPEG tidak utuh")
    # RIFF menyatakan panjang utuh: jangan menerima WebP terpotong atau data
    # tambahan yang disembunyikan setelah kontainer yang terlihat valid.
    if wajib_webp and (
        len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP"
        or int.from_bytes(data[4:8], "little") + 8 != len(data)
    ):
        raise ValueError("Kontainer WebP tidak utuh")
    with Image.open(io.BytesIO(data)) as pemeriksaan:
        if wajib_webp and pemeriksaan.format != "WEBP":
            raise ValueError("Hasil bukan WebP")
        if (pemeriksaan.width * pemeriksaan.height > MAKS_PIKSEL_FOTO
                or pemeriksaan.width <= 0 or pemeriksaan.height <= 0):
            raise ValueError("Dimensi foto di luar batas pemeriksaan")
        if getattr(pemeriksaan, "is_animated", False) or getattr(pemeriksaan, "n_frames", 1) != 1:
            raise ValueError("Foto animasi tidak boleh dikonversi sebagai satu bingkai")
        # WebP keluaran hanya 8 bit per kanal. Konversi RGBA untuk membandingkan
        # PNG 16-bit atau floating point akan menjepit nilainya dan bisa
        # menyamarkan hilangnya detail; simpan sumber presisi tinggi apa adanya.
        if pemeriksaan.mode not in ("1", "L", "LA", "P", "RGB", "RGBA", "CMYK", "YCbCr"):
            raise ValueError("Presisi warna sumber tidak boleh diturunkan")
        pemeriksaan.verify()
    gambar = Image.open(io.BytesIO(data))
    try:
        gambar.load()
    except Exception:
        gambar.close()
        raise
    return gambar


def sumber_foto_valid(data: bytes) -> bool:
    """Preflight sebelum memakai kuota: foto statis JPEG/PNG/WebP/AVIF utuh.

    Format lain, animasi, atau presisi >8-bit dibiarkan tetap tersimpan utuh;
    jangan baru menolaknya setelah memanggil layanan kompresi berbayar.
    """
    try:
        with _buka_foto(data) as foto:
            return foto.format in {"JPEG", "PNG", "WEBP", "AVIF"}
    except Exception:
        return False


def verifikasi_foto(sumber: bytes, hasil: bytes) -> bool:
    """WebP utuh, resolusi/alfa identik, tanpa perubahan piksel yang besar.

    Transparansi dibandingkan persis, termasuk PNG palet dan gambar opak.
    Selisih RGB ditimbang alfa sehingga warna piksel yang sepenuhnya tidak
    terlihat tidak menyebabkan penolakan. Tidak mengubah orientasi, mengecilkan,
    atau mengodekan ulang salah satu gambar. Jalankan di thread pekerja karena
    dekode dan pemeriksaan piksel bersifat CPU-bound.
    """
    try:
        with _buka_foto(sumber) as awal, _buka_foto(hasil, wajib_webp=True) as akhir:
            if awal.size != akhir.size:
                return False
            jumlah_kuadrat = [0.0, 0.0, 0.0]
            lebar, tinggi = awal.size
            for y in range(0, tinggi, SISI_BLOK):
                for x in range(0, lebar, SISI_BLOK):
                    kotak = (x, y, min(x + SISI_BLOK, lebar), min(y + SISI_BLOK, tinggi))
                    with awal.crop(kotak).convert("RGBA") as a, akhir.crop(kotak).convert("RGBA") as b:
                        alfa_a, alfa_b = a.getchannel("A"), b.getchannel("A")
                        try:
                            with ImageChops.difference(alfa_a, alfa_b) as beda_alfa:
                                if beda_alfa.getbbox() is not None:
                                    return False
                            with a.convert("RGB") as rgb_a, b.convert("RGB") as rgb_b:
                                with ImageChops.difference(rgb_a, rgb_b) as beda:
                                    # Selisih RGB premultiplied-alpha sama pada
                                    # latar apa pun bila alfa kedua gambar sama.
                                    with Image.merge("RGB", (alfa_a, alfa_a, alfa_a)) as bobot:
                                        with ImageChops.multiply(beda, bobot) as terlihat:
                                            statistik = ImageStat.Stat(terlihat)
                                            if max(statistik.rms) > MAKS_RMS_BLOK:
                                                return False
                                            for kanal, kuadrat in enumerate(statistik.sum2):
                                                jumlah_kuadrat[kanal] += kuadrat
                        finally:
                            alfa_a.close()
                            alfa_b.close()
            return max(math.sqrt(v / (lebar * tinggi)) for v in jumlah_kuadrat) <= MAKS_RMS_GLOBAL
    except Exception:
        return False
