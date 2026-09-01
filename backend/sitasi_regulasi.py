"""Registry sitasi peraturan yang TERCETAK ke dokumen resmi.

Latar: dokumen keluaran AMAN (Berita Acara, SPTJM, LBP, surat usulan) memuat
nomor peraturan, lalu ditandatangani Kuasa Pengguna Barang di atas meterai dan
dibaca pemeriksa. Nomor itu tersebar sebagai teks biasa di puluhan berkas —
tak ada yang tahu berapa banyak, mana yang pernah diriset, dan mana yang
dieja berbeda-beda untuk peraturan yang sama.

Modul ini tidak memutuskan apakah sebuah peraturan masih berlaku — teks asli
JDIH tidak terjangkau dari lingkungan pengembangan, dan menebaknya justru
sumber masalahnya. Yang dilakukannya dua hal yang BISA dipastikan tanpa akses
hukum sama sekali:

1. **Menagih provenans.** Tiap sitasi yang sampai ke dokumen wajib terdaftar
   di sini beserta statusnya. Sitasi baru yang belum didaftarkan membuat uji
   `test_sitasi_regulasi.py` merah — jadi tak ada nomor peraturan yang bisa
   menyelinap ke dokumen bermeterai tanpa seseorang menuliskan dari mana ia
   berasal.

2. **Menangkap repo yang membantah dirinya sendiri.** Dua sitasi dengan nomor
   dan tahun sama tetapi JENIS berbeda (mis. `KMK 29/PMK.6/2010` vs
   `PMK 29/PMK.06/2010`) pasti salah satunya keliru — tanpa perlu membuka
   satu pun peraturan.

Daftar berstatus BELUM_RISET adalah pertanyaan siap-kirim untuk Biro
Hukum/Inspektorat: itulah yang mengubah "tolong sediakan rujukan resmi" yang
mustahil dijawab menjadi permintaan konkret.
"""
import ast
import os
import re

# Jenis naskah yang dikenali. `S-` = surat dinas (mis. S-115/KN/2017).
_JENIS = "PP|PMK|KMK|UU|Perpres|Permendagri|PSAP|SE"

POLA_SITASI = re.compile(
    rf"\b(?:{_JENIS})\s+(?:Nomor\s+)?\d+(?:/[A-Za-z0-9.]+)*|\bS-\d+/KN/\d{{4}}\b")

# Status provenans.
PUSTAKA = "pustaka"            # tercatat di docs/PUSTAKA-REGULASI-BMN.md
BELUM_RISET = "belum-diriset"  # tercetak ke dokumen, tak pernah diriset
PERLU_KOREKSI = "perlu-koreksi"  # bertentangan dengan pustaka repo sendiri
# Judul & keberadaannya dikonfirmasi dari beberapa sumber luar yang saling
# bebas (riset 2026-08-16, rinciannya di docs/SITASI-DOKUMEN-RESMI.md).
# CATATAN: ini bukan pembacaan teks asli — JDIH, BPK, bahkan salinan di
# mirror universitas semuanya masih terblokir dari lingkungan ini. Yang
# dipastikan adalah NOMOR dan JUDULnya, bukan isi pasalnya.
TERVERIFIKASI = "terverifikasi"

# Tingkat tertinggi: NASKAHNYA ADA di `docs/regulasi/`, diunduh workflow
# "Unduh Regulasi" lewat runner GitHub Actions dan tercatat di MANIFEST.json
# lengkap dengan sha256-nya.
#
# Ini satu-satunya status yang menyatakan PASALNYA BISA DIBACA, bukan sekadar
# nomor dan judulnya dipastikan. Ia juga satu-satunya yang TAK BISA diklaim
# palsu: `test_teks_primer_berkasnya_memang_ada` memeriksa manifesnya, jadi
# menempelkan status ini tanpa naskahnya akan langsung ketahuan.
#
# Catatan atas TERVERIFIKASI di atas: keterangan "sumber primer terblokir"
# masih benar untuk lingkungan pengembangan, tetapi TIDAK lagi berarti
# naskahnya tak terjangkau sama sekali — runner punya egress biasa. Lihat
# `docs/regulasi/README.md`.
TEKS_PRIMER = "teks-primer"


def rapikan(sitasi: str) -> str:
    """Bentuk baku satu sitasi: spasi tunggal, tanpa kata "Nomor"."""
    return re.sub(r"\s+", " ", str(sitasi or "").replace("Nomor ", "")).strip().rstrip(".,;:")


def sitasi_dalam(teks: str) -> set:
    """Semua sitasi peraturan di dalam sepotong teks, sudah dirapikan."""
    return {rapikan(m) for m in POLA_SITASI.findall(str(teks or ""))}


def kunci_peraturan(sitasi: str):
    """Identitas peraturan LEPAS dari variasi ejaannya → (jenis, nomor, tahun).

    "PMK 181/PMK.06/2016", "PMK 181/2016", dan "PMK Nomor 181/PMK.06/2016"
    semuanya menghasilkan ("PMK", "181", "2016"). Inilah yang membuat dua
    ejaan berbeda untuk peraturan yang sama dapat dibandingkan — dan yang
    membuat `KMK 29/PMK.6/2010` ketahuan bertabrakan dengan
    `PMK 29/PMK.06/2010`: nomor & tahun sama, jenis berbeda.

    Tahun = kelompok 4 angka TERAKHIR; sitasi tanpa tahun (mis. "PMK 181")
    mengembalikan tahun "" dan sengaja tidak ikut dibandingkan.
    """
    s = rapikan(sitasi)
    m = re.match(rf"^(?:({_JENIS})\s+)?(?:S-)?(\d+)", s)
    if not m:
        return ("", "", "")
    jenis = m.group(1) or ("S" if s.startswith("S-") else "")
    nomor = m.group(2)
    tahun = ""
    for bagian in re.findall(r"\d{4}", s):
        tahun = bagian
    # Nomor yang KEBETULAN 4 angka (tak ada di praktik BMN) tak boleh
    # menelan dirinya sendiri sebagai tahun.
    if tahun == nomor and s.count(nomor) == 1:
        tahun = ""
    return (jenis, nomor, tahun)


def _teks_dokumen(sumber: str) -> list:
    """String literal yang BUKAN docstring — hanya ini yang bisa tercetak.

    Docstring & komentar adalah catatan untuk pengembang; menyebut nomor
    peraturan di sana justru dianjurkan dan tidak pernah sampai ke kertas.
    """
    pohon = ast.parse(sumber)
    docs = set()
    for simpul in ast.walk(pohon):
        if isinstance(simpul, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            d = ast.get_docstring(simpul, clean=False)
            if d:
                docs.add(d)
    return [s.value for s in ast.walk(pohon)
            if isinstance(s, ast.Constant) and isinstance(s.value, str)
            and s.value not in docs]


def pindai_sumber(akar: str) -> dict:
    """{sitasi → {berkas}} untuk seluruh berkas .py di bawah `akar`.

    Uji & skrip dikecualikan: keduanya tidak menghasilkan dokumen resmi.
    """
    keluar = {}
    for dirpath, _, berkas in os.walk(akar):
        if any(x in dirpath for x in ("/tests", "/scripts", "__pycache__")):
            continue
        for b in berkas:
            if not b.endswith(".py"):
                continue
            # Registry ini sendiri memuat tiap sitasi sebagai kunci dict.
            # Memindainya membuat setiap entri "ditemukan di sumber" oleh
            # dirinya sendiri — gerbangnya jadi selalu hijau, dan laporan
            # auditnya menunjuk berkas yang tidak mencetak dokumen apa pun.
            if b == os.path.basename(__file__):
                continue
            p = os.path.join(dirpath, b)
            try:
                sumber = open(p, encoding="utf-8").read()
                potongan = _teks_dokumen(sumber)
            except (SyntaxError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(p, akar)
            for teks in potongan:
                for s in sitasi_dalam(teks):
                    keluar.setdefault(s, set()).add(rel)
    return keluar


def bentrokan_jenis(daftar_sitasi) -> dict:
    """Sitasi yang nomor+tahunnya sama tetapi JENIS naskahnya berbeda.

    Salah satunya pasti keliru. Tak perlu membuka peraturan untuk tahu itu —
    cukup repo ini konsisten dengan dirinya sendiri.
    """
    per_kunci = {}
    for s in daftar_sitasi:
        jenis, nomor, tahun = kunci_peraturan(s)
        if not (nomor and tahun):
            continue
        per_kunci.setdefault((nomor, tahun), {}).setdefault(jenis, set()).add(s)
    return {k: v for k, v in per_kunci.items() if len(v) > 1}


def sub_kode(sitasi: str) -> str:
    """Segmen tengah sitasi, mis. "PMK.06" pada PMK 181/PMK.06/2016.

    Bentuk pendek tanpa segmen tengah ("PMK 181/2016") mengembalikan "" dan
    bukan pertentangan — ia cuma penyingkatan.
    """
    bagian = rapikan(sitasi).split("/")
    if len(bagian) < 3:
        return ""
    tengah = bagian[1].strip()
    return "" if tengah.isdigit() else tengah


def bentrokan_sub_kode(daftar_sitasi) -> dict:
    """Peraturan yang sama ditulis dengan DUA sub-kode berbeda.

    Contoh nyata di repo ini: `KMK 295/KM.6/2019` dan `KMK 295/KMK.06/2019`.
    Jenis, nomor, dan tahunnya sama persis, tetapi sub-kodenya berbeda — satu
    di antaranya pasti salah ketik, dan keduanya tercetak ke dokumen. Sekali
    lagi: tak perlu membuka peraturan untuk menyimpulkannya.
    """
    per_kunci = {}
    for s in daftar_sitasi:
        jenis, nomor, tahun = kunci_peraturan(s)
        sk = sub_kode(s)
        if not (nomor and tahun and sk):
            continue
        per_kunci.setdefault((jenis, nomor, tahun), {}).setdefault(sk, set()).add(s)
    return {k: v for k, v in per_kunci.items() if len(v) > 1}


def kunci_pustaka(teks_pustaka: str) -> set:
    """{(nomor, tahun)} setiap peraturan yang disebut pustaka riset."""
    keluar = set()
    for s in sitasi_dalam(teks_pustaka):
        _, nomor, tahun = kunci_peraturan(s)
        if nomor:
            keluar.add((nomor, tahun))
    return keluar


def ada_di_pustaka(sitasi: str, kunci_set: set) -> bool:
    """Apakah nomor peraturan ini tercatat di pustaka riset repo.

    Dibandingkan lewat (nomor, tahun), bukan teks mentah — supaya bentuk
    pendek "PMK 83/2016" dikenali sama dengan "PMK 83/PMK.06/2016" di
    pustaka. Sitasi tanpa tahun dicocokkan pada nomornya saja.

    Ini TIDAK menyatakan peraturannya masih berlaku; hanya bahwa seseorang
    pernah menuliskannya sebagai hasil riset, bukan mengetiknya begitu saja
    di tengah naskah.
    """
    _, nomor, tahun = kunci_peraturan(sitasi)
    if not nomor:
        return False
    if tahun:
        return (nomor, tahun) in kunci_set
    return any(n == nomor for n, _ in kunci_set)


# ── Registry ────────────────────────────────────────────────────────────────
# Setiap sitasi yang muncul di string dokumen WAJIB ada di sini. Menambah
# nomor peraturan ke naskah tanpa mendaftarkannya di bawah = uji merah.
#
# PUSTAKA       : nomornya tercatat di docs/PUSTAKA-REGULASI-BMN.md.
#                 CATATAN: "tercatat" ≠ "terverifikasi" — pustaka itu sendiri
#                 menandai sebagian butirnya "[perlu verifikasi]" karena teks
#                 asli JDIH tak terjangkau.
# BELUM_RISET   : sampai ke dokumen tetapi TIDAK ADA di pustaka. Inilah daftar
#                 pertanyaan untuk Biro Hukum/Inspektorat.
# PERLU_KOREKSI : bertentangan dengan pustaka repo sendiri — dapat diperbaiki
#                 tanpa akses hukum, tetapi butuh keputusan pemilik dulu.
SITASI_TERDAFTAR = {
    # — Induk & penatausahaan —
    "UU 17/2003": PUSTAKA,
    "UU 1/2004": PUSTAKA,
    "PP 27": PUSTAKA,
    "PP 27/2014": PUSTAKA,
    "PP 28": PUSTAKA,
    "PP 28/2020": PUSTAKA,
    "PP 71": PUSTAKA,
    "PSAP 05": PUSTAKA,
    "PSAP 07": PUSTAKA,
    "PMK 181": TEKS_PRIMER,
    "PMK 181/2016": TEKS_PRIMER,
    "PMK 181/PMK.06/2016": TEKS_PRIMER,
    # — Siklus BMN —
    "PMK 40": TEKS_PRIMER,
    "PMK 40/2024": TEKS_PRIMER,
    "PMK 115/2020": TEKS_PRIMER,
    "PMK 120/2024": PUSTAKA,
    "PMK 120/PMK.06/2024": PUSTAKA,
    "PMK 138/2024": PUSTAKA,
    "PMK 139/PMK.08/2022": PUSTAKA,
    "PMK 18/2024": PUSTAKA,
    # Naskahnya masuk pustaka pada unduhan keempat (2026-09-01) lewat pola
    # `fulltext` JDIH — 104 halaman.
    "PMK 111/2016": TEKS_PRIMER,
    "PMK 165/2021": TEKS_PRIMER,
    "PMK 165/PMK.06/2021": TEKS_PRIMER,
    "PMK 83/2016": TEKS_PRIMER,
    "PMK 83/PMK.06/2016": TEKS_PRIMER,
    "PMK 207": TEKS_PRIMER,
    "PMK 207/2021": TEKS_PRIMER,
    "PMK 207/PMK.06/2021": TEKS_PRIMER,
    "PMK 118/2017": PUSTAKA,
    "PMK 118/PMK.06/2017": PUSTAKA,
    "PMK 4/2015": TEKS_PRIMER,
    "PMK 218/2015": PUSTAKA,
    "PMK 234/2020": PUSTAKA,
    "PMK 65/2017": PUSTAKA,
    "PMK 65/PMK.06/2017": PUSTAKA,
    "PMK 43/2025": PUSTAKA,
    "PMK 99/2024": PUSTAKA,
    "PMK 153/2021": PUSTAKA,
    "Permendagri 7/2024": PUSTAKA,
    "Perpres 46": PUSTAKA,
    "KMK 128/KM.6/2022": PUSTAKA,
    "KMK 266/KM.6/2023": PUSTAKA,
    "KMK 295/KM.6/2019": PUSTAKA,
    "KMK 295/2019": PUSTAKA,            # bentuk pendek dari KMK 295/KM.6/2019
    "KMK 21/2012": PUSTAKA,             # pustaka: 21/KMK.01/2012
    "PMK 1/PMK.06/2013": PUSTAKA,       # pustaka baris 114
    "PMK 251/PMK.06/2015": PUSTAKA,     # pustaka baris 115 (amortisasi ATB)
    "PMK 234/PMK.05/2020": PUSTAKA,

    # — Diriset 2026-08-16, nomor & judul terkonfirmasi dari sumber luar —
    # "Bagan Akun Standar"; menggantikan PMK 91/PMK.05/2007. Judul di
    # lbp_utils.py cocok persis.
    "PMK 214/PMK.05/2013": TERVERIFIKASI,
    # "Masa Manfaat dalam rangka Amortisasi BMN berupa Aset Tak Berwujud",
    # diubah oleh KMK 81/KM.6/2018. Rantai "620 jo. 81" di lbp_utils cocok.
    "KMK 620/KM.6/2015": TERVERIFIKASI,
    "KMK 81/KM.6/2018": TERVERIFIKASI,
    # Hibah BMN selain tanah/bangunan tanpa bukti kepemilikan, nilai perolehan
    # ≤ Rp100 juta — persis yang diklaim pemindahtanganan_utils.py.
    "KMK 334/2021": TERVERIFIKASI,
    # "Pedoman Pelaksanaan Tindak Lanjut Hasil Penertiban BMN pada K/L".
    # TERBATAS: judulnya terkonfirmasi, tetapi klaim SPTJM di reports.py soal
    # tanggung jawab "formil dan materiil" BELUM terbaca dari teks aslinya.
    "KMK 403/KMK.06/2013": TERVERIFIKASI,
    # Surat Dirjen KN soal tindak lanjut Barang Tidak Ditemukan, terkait
    # PMK 118/PMK.06/2017 (penilaian kembali BMN) & Perpres 75/2017.
    # PERHATIAN: sumber menyebut konteksnya PENILAIAN KEMBALI (revaluasi),
    # sedangkan ba_utils.py menuliskannya sebagai "tindak lanjut hasil
    # INVENTARISASI". Beda konteks — perlu ditegaskan pemilik.
    "S-115/KN/2017": TERVERIFIKASI,
    # Semula saya tandai PERLU_KOREKSI karena mengira tahunnya keliru.
    # KELIRU: "Tata Cara Rekonsiliasi BMN dalam rangka Penyusunan LKPP"
    # memang bernomor 118/PMK.06/2018 dan mencabut PMK 69/PMK.06/2016.
    # Nomor 118 dipakai dua peraturan berbeda di dua tahun berbeda.
    "PMK 118/PMK.06/2018": TERVERIFIKASI,

    # — Masih belum ketemu —
    # Diklaim perbaikan_utils.py sebagai perubahan kedua atas KMK 295/KM.6/2019
    # (menambah baris 31304 Oil & Gas Facilities dan 31305 Wells). Perubahan
    # keduanya MEMANG ada, tetapi nomornya tak muncul di sumber mana pun
    # setelah empat sudut pencarian berbeda.
    "KMK 339/KM.6/2024": BELUM_RISET,

    # — Bertentangan dengan pustaka repo sendiri —
    # `KMK 29/PMK.6/2010`: pustaka (baris 21 & 1322) menulis PMK 29/PMK.06/2010
    #   untuk Penggolongan & Kodefikasi. Sitasi ini salah pada DUA hal
    #   sekaligus — jenisnya (KMK, padahal PMK) dan sub-kodenya (PMK.6,
    #   padahal PMK.06). Nomor KMK dengan sub-kode PMK tidak koheren.
    "KMK 29/PMK.6/2010": PERLU_KOREKSI,
    # `KMK 295/KMK.06/2019`: ejaan ketiga untuk peraturan yang di tempat lain
    #   ditulis KMK 295/KM.6/2019 dan KMK 295/2019. Riset 2026-08-16
    #   menguatkan bentuk `KM.6`: Hukumonline mengindeksnya sebagai
    #   "Keputusan Menteri Keuangan Nomor 295/KM.6/2019".
    "KMK 295/KMK.06/2019": PERLU_KOREKSI,
}
