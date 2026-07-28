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


# ── Ambang kompresi gambar tersemat ────────────────────────────────────────
# Angka-angka ini adalah keputusan sadar, bukan selera. Dokumen BMN adalah
# bukti hukum: nomor seri pada foto dan teks pada hasil scan WAJIB tetap
# terbaca. Semua ambang di bawah dipilih agar itu terjaga.

SISI_MAKS_FOTO = 1700     # px — pada lebar A4 ≈ 200 DPI; foto BMN tetap tajam
SISI_MIN_SENTUH = 700     # px — di bawah ini JANGAN disentuh: itu wilayah
                          # logo, stempel, QR, dan spesimen tanda tangan
SISI_MAKS_SCAN = 2200     # px — halaman hasil scan berisi TEKS: ≈265 DPI,
                          # sengaja lebih longgar daripada foto biasa
MUTU_FOTO = 75
MUTU_SCAN = 85            # scan lebih tinggi: artefak JPEG pada huruf tipis
                          # jauh lebih merusak daripada pada foto
UNTUNG_MIN = 0.03         # < 3% tak sepadan dengan risikonya — kembalikan asli
TOLERANSI_TEKS = 0.98     # teks hasil ekstraksi wajib >= 98% panjang aslinya


def _pdf_bertanda_tangan(pembaca) -> bool:
    """Deteksi tanda tangan digital pada PDF.

    Dokumen ber-TTD digital TIDAK BOLEH disentuh sama sekali: menulis ulang
    strukturnya membatalkan tanda tangannya, dan dokumen BMN yang tanda
    tangannya batal lebih buruk daripada dokumen yang besar.
    """
    try:
        akar = pembaca.trailer["/Root"]
        acro = akar.get("/AcroForm")
        if not acro:
            return False
        acro = acro.get_object()
        if acro.get("/SigFlags"):
            return True
        for f in (acro.get("/Fields") or []):
            try:
                if f.get_object().get("/FT") == "/Sig":
                    return True
            except Exception:
                continue
    except Exception:
        # Ragu = anggap bertanda tangan. Salah menolak hanya berarti berkas
        # tak terkompresi; salah menerima berarti tanda tangan batal.
        return True
    return False


def _teks_pdf(pembaca) -> str:
    potong = []
    for h in pembaca.pages:
        try:
            potong.append(h.extract_text() or "")
        except Exception:
            pass
    return "".join(potong)


# ── Jaring pengaman LOKAL ──────────────────────────────────────────────────

def _kecilkan_gambar_halaman(halaman) -> int:
    """Turunkan resolusi gambar tersemat pada satu halaman. Kembalikan cacah
    gambar yang benar-benar diganti."""
    from PIL import Image

    diganti = 0
    try:
        daftar = list(halaman.images)
    except Exception:
        return 0
    for berkas_gambar in daftar:
        try:
            gbr = berkas_gambar.image
            if gbr is None:
                continue
            w, h = gbr.size
            # Gambar kecil TIDAK disentuh: itu logo, stempel, QR, spesimen
            # tanda tangan. Mengecilkannya merusak tanpa menghemat berarti.
            if max(w, h) < SISI_MIN_SENTUH:
                continue
            # Bitonal (hasil fotokopi) dilewati: JPEG justru MEMBESARKANNYA
            # dan menambah artefak pada teks.
            if gbr.mode in ("1", "P"):
                continue

            # Halaman yang gambarnya sangat besar dan berbentuk potret
            # umumnya hasil SCAN dokumen — isinya teks, jadi diperlakukan
            # lebih hati-hati daripada foto biasa.
            adalah_scan = max(w, h) >= 2000 and (h >= w)
            sisi_maks = SISI_MAKS_SCAN if adalah_scan else SISI_MAKS_FOTO
            mutu = MUTU_SCAN if adalah_scan else MUTU_FOTO

            baru = gbr
            if max(w, h) > sisi_maks:
                skala = sisi_maks / float(max(w, h))
                baru = gbr.resize((max(1, int(w * skala)), max(1, int(h * skala))),
                                  Image.LANCZOS)
            if baru.mode not in ("RGB", "L"):
                baru = baru.convert("RGB")

            keluar = io.BytesIO()
            baru.save(keluar, format="JPEG", quality=mutu, optimize=True)
            calon = keluar.getvalue()
            # Hanya ganti bila benar-benar lebih kecil. PDF yang gambarnya
            # sudah optimal akan MEMBESAR bila di-encode ulang.
            if len(calon) < len(berkas_gambar.data):
                berkas_gambar.replace(baru, quality=mutu, optimize=True)
                diganti += 1
        except Exception:
            # Satu gambar rewel tak boleh menggagalkan seluruh dokumen.
            continue
    return diganti


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
        # PDF ber-TTD digital: menulis ulang strukturnya MEMBATALKAN tanda
        # tangannya. Dokumen besar jauh lebih baik daripada dokumen yang
        # tanda tangannya batal.
        if _pdf_bertanda_tangan(pembaca):
            return None
        jumlah_halaman = len(pembaca.pages)
        if jumlah_halaman == 0:
            return None
        teks_asli = _teks_pdf(pembaca)

        penulis = PdfWriter()
        for hal in pembaca.pages:
            penulis.add_page(hal)
        for hal in penulis.pages:
            # Turunkan resolusi gambar tersemat (ambang aman di atas), lalu
            # padatkan content stream. Urutan ini penting: memadatkan dulu
            # lalu mengganti gambar akan meninggalkan stream lama.
            _kecilkan_gambar_halaman(hal)
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

        # ── Gerbang keselamatan: hasilnya WAJIB dokumen yang sama ──────────
        ulang = PdfReader(io.BytesIO(hasil))
        if len(ulang.pages) != jumlah_halaman:
            return None
        # Teks tak boleh menyusut. Ini penjaga terpenting bagi dokumen bukti:
        # kalau ekstraksi teks tiba-tiba jauh lebih pendek, ada yang rusak —
        # dan kerusakan pada BAST/kontrak jauh lebih mahal daripada berkas
        # yang besar.
        if teks_asli:
            teks_baru = _teks_pdf(ulang)
            if len(teks_baru) < len(teks_asli) * TOLERANSI_TEKS:
                return None
        # Penghematan sepele tak sepadan dengan risiko encode ulang lossy.
        if len(hasil) >= len(pdf_bytes) * (1 - UNTUNG_MIN):
            return None
        return hasil if layak_dipakai(pdf_bytes, hasil) else None
    except Exception:
        return None
