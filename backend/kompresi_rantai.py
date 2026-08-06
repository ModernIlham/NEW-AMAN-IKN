"""Rantai kompresi gambar — SIAPA yang akan melayani permintaan berikutnya.

Bagian murni (tanpa DB/jaringan) dari satu pertanyaan yang selama ini dijawab
salah oleh layar: *layanan mana yang benar-benar dipakai sekarang?*

KENAPA ADA. Laporan pemilik: indikator kuota di toolbar menunjukkan **0/500**
padahal Compresto masih menyisakan 474. Menelusurinya menunjukkan rantai
kompresinya SENDIRI baik-baik saja — `routes/media.auto_compress_image` memang
mencoba Tinify → Compresto → Uploadcare → Pillow dan tiap fungsi mundur saat
kuotanya habis. Yang keliru adalah indikatornya: ia memilih layanan memakai
bendera `available`, dan `available` berarti **"percobaan TERAKHIR terbukti
berhasil"** (lihat `kompresi_diagnostik.py`) — catatan diagnostik di memori
proses yang hangus tiap kali server restart.

Dua pertanyaan itu berbeda, dan mencampurnya membuat layar berbohong:

  • *"Sudah TERBUKTI jalan?"* → jawaban jujur untuk panel diagnostik. Layanan
    berkunci lengkap yang belum pernah dipanggil sejak proses hidup memang
    belum terbukti apa-apa.
  • *"Akan DIPAKAI berikutnya?"* → yang ditanyakan operator saat melihat angka
    di toolbar. Untuk ini yang menentukan hanya dua hal: kuncinya terpasang,
    dan kuotanya belum habis — persis syarat yang dipakai rantai aslinya.

Modul ini menjawab pertanyaan KEDUA, dengan aturan yang diturunkan dari rantai
sungguhan sehingga keduanya tak bisa berpisah diam-diam.
"""

__all__ = ["URUTAN", "URUTAN_PDF", "layak_pakai", "layanan_aktif", "sisa_layanan"]

# Urutan rantai GAMBAR. SATU sumber kebenaran — `routes/media.auto_compress_image`
# mengikuti daftar yang sama, dan uji anti-drift menagih keduanya tetap sejalan.
URUTAN = ("tinify", "compresto", "uploadcare", "pillow")

# Urutan rantai PDF. Aturannya sama persis: layanan berkuota dulu, penutupnya
# pengolah LOKAL yang tak berkuota — sehingga tak pernah ada keadaan "tak bisa
# mengompres sama sekali", baik untuk gambar maupun PDF.
URUTAN_PDF = ("ilovepdf", "pypdf")


def _int(nilai, bawaan=None):
    try:
        return int(nilai)
    except (TypeError, ValueError):
        return bawaan


def _prioritas(nama: str, urutan=URUTAN) -> int:
    """Posisi layanan dalam rantai; yang tak dikenal ditaruh PALING BELAKANG.

    Dibuang begitu saja akan menyembunyikan layanan baru yang lupa didaftarkan
    di `URUTAN` — ia tetap boleh dipakai, hanya tak boleh mendahului yang sudah
    disepakati urutannya.
    """
    try:
        return urutan.index(nama)
    except ValueError:
        return len(urutan)


def sisa_layanan(entri) -> int:
    """Sisa kuota satu layanan. Negatif = tak terbatas (Pillow lokal).

    `remaining` dipakai bila ada; kalau tidak, dihitung dari `limit - used`
    supaya pemanggil yang hanya mengisi dua field itu tetap terlayani.
    """
    e = entri or {}
    batas = _int(e.get("limit"))
    if batas is not None and batas < 0:
        return -1
    sisa = _int(e.get("remaining"))
    if sisa is not None:
        return sisa
    if batas is None:
        return 0
    return max(0, batas - (_int(e.get("used"), 0) or 0))


def layak_pakai(entri) -> bool:
    """True bila layanan ini benar-benar akan dicoba oleh rantai.

    Syaratnya SENGAJA hanya dua — kunci/pustakanya terpasang, dan kuotanya
    belum habis — karena itulah dua syarat yang dipakai `compress_with_*` di
    `routes/media.py`. Menambahkan syarat "sudah terbukti berhasil" di sini
    akan mengulang persis cacat yang modul ini perbaiki.
    """
    e = entri or {}
    if not e.get("terpasang"):
        return False
    return sisa_layanan(e) != 0


def layanan_aktif(kuota, urutan=URUTAN) -> str:
    """Nama layanan yang melayani permintaan berikutnya; "" bila tak ada satu pun.

    Urutan daftar masukan TIDAK dipercaya — prioritasnya dihitung dari `urutan`,
    sehingga endpoint yang kelak menyusun ulang daftarnya tak diam-diam
    mengubah rantai.

    `urutan` dapat dioper `URUTAN_PDF` untuk rantai PDF; aturan kelayakannya
    identik, karena tuntutannya memang satu: apa pun jenis berkasnya, gilirannya
    ditentukan oleh kunci terpasang + kuota tersisa.
    """
    daftar = [e for e in (kuota or []) if isinstance(e, dict)]
    daftar.sort(key=lambda e: _prioritas(str(e.get("service") or ""), urutan))
    for e in daftar:
        if layak_pakai(e):
            return str(e.get("service") or "")
    return ""
