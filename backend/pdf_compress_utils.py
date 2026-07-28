"""Logika MURNI kompresi PDF — tanpa jaringan, tanpa DB, tanpa FastAPI.

Dipisah dari `routes/pdf_compress.py` karena satu kendala yang menentukan
seluruh cara pengujiannya: **host penyedia tidak dapat dijangkau dari CI.**
Kebijakan jaringan lingkungan build menolak CONNECT ke api.ilovepdf.com, jadi
tak mungkin membuktikan integrasi ini dengan memanggilnya sungguhan.

Konsekuensinya jujur: yang bisa dijaga uji otomatis hanyalah **bentuk
permintaan yang kita kirim** dan **cara kita membaca jawaban** — bukan bahwa
iLovePDF benar-benar menerimanya. Pembuktian ujung-ke-ujung wajib dijalankan
sekali di VPS (lihat `scripts/verifikasi_kompresi_pdf.py`). Modul ini menaruh
sebanyak mungkin keputusan ke dalam fungsi murni supaya bagian yang TIDAK bisa
diuji tinggal sesedikit mungkin.
"""
from __future__ import annotations

import io
import re
import time
from typing import Optional

# Tiga nilai ini yang diterima iLovePDF untuk alat `compress`. Nilai di luar
# daftar ditolak 400 — dan ditolak SETELAH berkas kita terlanjur terunggah,
# yaitu setelah kuota mulai terpakai. Karena itu divalidasi di sisi kita.
TINGKAT_KOMPRESI_SAH = ("low", "recommended", "extreme")
TINGKAT_KOMPRESI_BAWAAN = "recommended"

# Umur token pendek: token ini menyandang kewenangan penuh atas akun iLovePDF.
# Satu jam cukup untuk transaksi terpanjang (unggah 25 MB + proses) sambil
# membatasi jendela bila ia sempat bocor ke log.
UMUR_TOKEN_DETIK = 3600

MAKS_UKURAN_PDF = 25 * 1024 * 1024      # 25 MB — sejalan dengan batas rute


def token_ilovepdf(public_key: str, secret_key: str,
                   umur_detik: int = UMUR_TOKEN_DETIK,
                   sekarang: Optional[float] = None) -> str:
    """Buat JWT self-signed untuk iLovePDF (HS256, ditandatangani secret key).

    Ini jalur otentikasi yang TIDAK menempuh jaringan: secret key dipakai
    sebagai kunci penandatangan **secara lokal** dan tidak pernah dikirim ke
    siapa pun. Public key ditaruh di klaim `jti` sebagai penanda proyek.

    Kenapa jalur ini yang diutamakan dibanding `POST /v1/auth`:
    satu perjalanan jaringan lebih sedikit pada tiap kompresi, dan — lebih
    penting — **secret key tak pernah meninggalkan server kita.** Jalur
    `/v1/auth` tetap disediakan sebagai cadangan bila hanya public key yang
    dikonfigurasi.
    """
    import jwt  # PyJWT, sudah dipakai modul auth aplikasi

    if not public_key or not secret_key:
        raise ValueError("public_key dan secret_key wajib diisi")
    t = int(sekarang if sekarang is not None else time.time())
    return jwt.encode(
        {
            "jti": public_key,
            "iss": "",
            "iat": t,
            "nbf": t,
            "exp": t + int(umur_detik),
        },
        secret_key,
        algorithm="HS256",
    )


def tingkat_kompresi_sah(nilai) -> str:
    """Jepit `compression_level` ke salah satu nilai yang diterima iLovePDF.

    Nilai asing dibetulkan diam-diam ke bawaan, BUKAN diteruskan apa adanya:
    meneruskannya berarti 400 yang baru ketahuan setelah berkas terunggah.
    """
    v = str(nilai or "").strip().lower()
    return v if v in TINGKAT_KOMPRESI_SAH else TINGKAT_KOMPRESI_BAWAAN


def nama_berkas_aman(nama, bawaan: str = "document.pdf") -> str:
    """Bersihkan nama berkas untuk header Content-Disposition.

    Karakter CR/LF/kutip/backslash/garis miring dibuang: nama berkas berasal
    dari unggahan pengguna dan masuk ke header HTTP, jadi tanpa penyaringan ini
    ia bisa menyuntikkan header tambahan (header splitting).
    """
    bersih = re.sub(r'[\r\n";\\/]+', "_", str(nama or ""))[:120].strip()
    return bersih or bawaan


def pdf_valid(data: bytes) -> tuple[bool, str]:
    """Periksa kelayakan PDF SEBELUM ia menghabiskan kuota berbayar.

    Mengirim berkas rusak ke penyedia bukan cuma sia-sia — pada iLovePDF kuota
    terpakai saat `/v1/process`, sehingga berkas sampah pun bisa memakan
    kredit. Penyaringan paling murah adalah di sini.
    """
    if not data:
        return False, "Berkas kosong"
    if len(data) > MAKS_UKURAN_PDF:
        return False, f"PDF melebihi {MAKS_UKURAN_PDF // (1024 * 1024)}MB"
    if data[:4] != b"%PDF":
        return False, "Berkas bukan PDF yang valid"
    return True, ""


def proses_berhasil(payload) -> tuple[bool, str]:
    """Tafsirkan jawaban `/v1/process` iLovePDF.

    **HTTP 200 tidak menjamin sukses.** iLovePDF mengembalikan 200 dengan field
    `status` yang bisa berisi kegagalan pemrosesan. Kode yang hanya memeriksa
    status code akan mengunduh berkas galat lalu menyajikannya sebagai hasil
    kompresi — kerusakan senyap yang paling mahal di jalur ini.

    Juga menolak keluaran jamak: `output_filenumber > 1` berarti unduhan
    berikutnya adalah ZIP, bukan PDF, dan menyajikannya sebagai PDF akan
    menghasilkan berkas yang tak bisa dibuka siapa pun.
    """
    if not isinstance(payload, dict):
        return False, "jawaban proses bukan objek JSON"
    status = str(payload.get("status") or "").strip()
    if status != "TaskSuccess":
        return False, f"status proses '{status or '(kosong)'}'"
    try:
        jumlah = int(payload.get("output_filenumber") or 1)
    except (TypeError, ValueError):
        jumlah = 1
    if jumlah > 1:
        return False, f"keluaran {jumlah} berkas (ZIP), bukan PDF tunggal"
    return True, ""


def persen_hemat(ukuran_asli: int, ukuran_hasil: int) -> int:
    """Persentase penghematan, dibulatkan. Nol bila tak ada penghematan."""
    if ukuran_asli <= 0 or ukuran_hasil <= 0 or ukuran_hasil >= ukuran_asli:
        return 0
    return round((1 - ukuran_hasil / ukuran_asli) * 100)


def layak_dipakai(asli: bytes, hasil: Optional[bytes]) -> bool:
    """Hasil kompresi hanya dipakai bila BENAR-BENAR lebih kecil dan masih PDF.

    Penyedia bisa mengembalikan berkas yang lebih besar (PDF yang sudah
    terkompresi optimal), halaman galat HTML, atau ZIP. Ketiganya lolos begitu
    saja bila yang diperiksa hanya "ada isinya".
    """
    if not hasil:
        return False
    if hasil[:4] != b"%PDF":
        return False
    return 0 < len(hasil) < len(asli)


# ── Jaring pengaman LOKAL ──────────────────────────────────────────────────

def kompres_pdf_lokal(pdf_bytes: bytes) -> Optional[bytes]:
    """Kompresi PDF tanpa jaringan memakai pypdf — sepadan peran Pillow di
    jalur gambar.

    Alasan keberadaannya: rantai penyedia bisa gagal seluruhnya (kunci belum
    dipasang, kuota habis, penyedia mati, server tanpa akses keluar). Tanpa
    jaring pengaman lokal, "kompresi PDF" adalah fitur yang diam-diam tak
    melakukan apa pun. Jalur gambar sudah punya Pillow sejak awal; jalur PDF
    tidak — dan itulah yang membuat kegagalannya tak terlihat selama ini.

    SENGAJA konservatif. Dokumen BMN adalah bukti resmi: teks wajib tetap
    terbaca dan jumlah halaman wajib tetap sama. Yang dilakukan hanya
    pemadatan aman (kompres ulang content stream + buang objek kembar), bukan
    penurunan resolusi gambar yang bisa membuat stempel/tanda tangan kabur.

    Mengembalikan None bila gagal, tak menghemat, atau hasilnya mencurigakan —
    pemanggil lalu memakai berkas ASLI.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except Exception:                                  # pragma: no cover
        return None
    try:
        pembaca = PdfReader(io.BytesIO(pdf_bytes))
        # PDF terenkripsi: JANGAN disentuh. Membukanya paksa bisa menghasilkan
        # dokumen tanpa proteksi yang aslinya memang diproteksi.
        if getattr(pembaca, "is_encrypted", False):
            return None
        jumlah_halaman = len(pembaca.pages)
        if jumlah_halaman == 0:
            return None

        penulis = PdfWriter()
        for hal in pembaca.pages:
            penulis.add_page(hal)
        for hal in penulis.pages:
            try:
                hal.compress_content_streams()
            except Exception:
                # Satu halaman rewel tak boleh menggagalkan seluruh dokumen.
                pass
        try:
            penulis.compress_identical_objects()
        except Exception:
            pass

        keluar = io.BytesIO()
        penulis.write(keluar)
        hasil = keluar.getvalue()

        # Verifikasi hasilnya masih dokumen yang SAMA sebelum dipakai.
        ulang = PdfReader(io.BytesIO(hasil))
        if len(ulang.pages) != jumlah_halaman:
            return None
        return hasil if layak_dipakai(pdf_bytes, hasil) else None
    except Exception:
        return None
