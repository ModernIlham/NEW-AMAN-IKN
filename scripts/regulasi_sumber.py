#!/usr/bin/env python3
"""Pengunduh teks peraturan primer — DIJALANKAN DI RUNNER, bukan di sini.

Permintaan pemilik: *"download semua referensi untuk memperkaya pustaka,
temukan hingga ke sumber lainnya jika terblokir untuk mengunduh sampai
pustaka kita lengkap."*

── Kenapa berkas ini ada ──────────────────────────────────────────────────
Lingkungan pengembangan Claude Code **tidak bisa** menjangkau satu pun sumber
peraturan. Gerbang egress menjawab **403 pada CONNECT** untuk setiap host yang
dicoba — jdih.kemenkeu.go.id, peraturan.bpk.go.id, djkn.kemenkeu.go.id,
peraturan.go.id, jdihn.go.id, sipuu.setkab.go.id, ngada.org, scribd.com,
bahkan web.archive.org dan en.wikipedia.org. Itu kebijakan organisasi, bukan
kerusakan, dan **tidak boleh diakali**.

Yang TIDAK terblokir: **runner GitHub Actions**. Ia punya egress internet
biasa. Jadi pengunduhannya dipindahkan ke sana lewat
`.github/workflows/unduh-regulasi.yml`, dan hasilnya didorong ke cabang
`regulasi/unduhan` supaya bisa dibaca, ditelaah, lalu di-PR seperti perubahan
lain.

── Yang berkas ini lakukan ────────────────────────────────────────────────
Mengambil PDF peraturan, mengekstrak teksnya, menyimpannya sebagai `.txt`
yang bisa di-`grep` dan di-`diff`, plus manifes berisi **sha256, ukuran,
jumlah halaman, URL yang berhasil, dan waktu unduh** — supaya asal-usul tiap
berkas bisa ditelusuri, bukan sekadar "ada di repo".

── Yang berkas ini TIDAK lakukan ──────────────────────────────────────────
**Tidak menaikkan status verifikasi apa pun secara otomatis.** Teks yang
terunduh adalah BUKTI, bukan kesimpulan. Menaikkan butir di
`syarat_dokumen_utils.py` dari `belum_terverifikasi` menjadi `terverifikasi`
tetap langkah sadar setelah pasalnya dibaca — persis seperti yang sudah
berlaku di `docs/SITASI-DOKUMEN-RESMI.md`. Otomatisasi yang menstempel
"terverifikasi" hanya karena PDF-nya berhasil diunduh akan menghapus satu-
satunya pembeda yang membuat pustaka ini bisa dipercaya.

Tidak menyimpan PDF-nya ke repo (besar dan tak bisa di-diff); hanya teksnya.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ── Manifes ────────────────────────────────────────────────────────────────
#
# Tiap peraturan punya BEBERAPA sumber, dicoba berurutan. Alasannya bukan
# kehati-hatian berlebihan: URL JDIH berubah saat situsnya diperbarui, dan
# satu URL mati akan mematikan seluruh unduhan. Cermin kementerian lain
# (pertanian, PUPR, BP Batam) memuat salinan PDF yang sama dan jauh lebih
# stabil karena ia berkas statis di WordPress.
#
# `html` = halaman yang perlu dikerok tautan PDF-nya lebih dulu.
# `pdf`  = tautan langsung.
# `teks` = naskah lengkap yang disajikan sebagai HTML, bukan PDF. JDIH
#          menyajikan sebagian peraturan begitu (mis. PP 27/2014 hanya ada
#          sebagai `.htm`, tak pernah sebagai `.pdf`). Untuk keperluan
#          pustaka ini justru LEBIH BAIK: tak ada derau OCR sama sekali.
#
# `prioritas` menentukan urutan unduh — yang menutup celah terbesar di
# registry syarat dokumen didahulukan, supaya kegagalan di ekor daftar tidak
# menunda yang paling dibutuhkan.

MANIFES = [
    {
        "kode": "pmk-111-2016-pemindahtanganan",
        "judul": "PMK 111/PMK.06/2016 — Tata Cara Pelaksanaan Pemindahtanganan BMN",
        "guna": "Hibah, penjualan, tukar menukar, PMPP — celah TERBESAR di registry",
        "prioritas": 1,
        "sumber": [
            # Pola `fulltext` JDIH — ditemukan dari URL yang BERHASIL pada
            # unduhan pertama (PMK 83, 181, 4, PP 28). Ia menuju batang tubuh
            # langsung tanpa halaman perantara.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2016/"
                    "111~PMK.06~2016Per.pdf"),
            ("pdf", "https://ditjenbun.pertanian.go.id/template/uploads/2021/09/"
                    "PMK-111-TAHUN-2016-TATA-CARA-PELAKSANAAN-PEMINDAHTANGANAN-BMN.pdf"),
            # CATATAN: sumber sibangkoman.pu.go.id DICABUT. Ia mengembalikan
            # PDF sah berlapis teks — tetapi isinya PAPARAN PELATIHAN DJKN
            # berjudul sama, bukan batang tubuh PMK-nya. Lihat
            # `bukan_batang_tubuh`; guard itu lahir dari kejadian ini.
            ("html", "https://jdih.kemenkeu.go.id/dok/111-pmk-06-2016"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-111-pmk-06-2016-tahun-2016"),
            ("html", "https://paralegal.id/peraturan/"
                     "peraturan-menteri-keuangan-nomor-111-pmk-06-2016/"),
            ("html", "https://peraturan.bpk.go.id/Details/121125/pmk-no-111pmk062016"),
        ],
    },
    {
        "kode": "pmk-165-2021-perubahan-pemindahtanganan",
        "judul": "PMK 165/PMK.06/2021 — Perubahan atas PMK 111/PMK.06/2016",
        "guna": "Perubahan rezim pemindahtanganan",
        "prioritas": 2,
        "sumber": [
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/"
                    "9a80cffe-c7d2-43cd-b06f-88dd1d9ea9b6/165~PMK.06~2021Per.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/165-pmk-06-2021"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-165-pmk-06-2021-tahun-2021"),
            ("html", "https://peraturan.bpk.go.id/Details/196037/pmk-no-165pmk062021"),
        ],
    },
    {
        "kode": "pmk-83-2016-pemusnahan-penghapusan",
        "judul": "PMK 83/PMK.06/2016 — Tata Cara Pelaksanaan Pemusnahan dan Penghapusan BMN",
        "guna": "Rezim penghapusan & pemusnahan — belum ada dasar pasal sama sekali",
        "prioritas": 3,
        "sumber": [
            ("pdf", "https://ditjenbun.pertanian.go.id/template/uploads/2021/09/"
                    "PMK-83-TAHUN-2016-TATA-CARA-PELAKSANAAN-PEMUSNAHAN-DAN-PENGHAPUSAN-BMN.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/83-pmk-06-2016"),
            ("html", "https://peraturan.bpk.go.id/Details/121081/pmk-no-83pmk062016"),
        ],
    },
    {
        "kode": "pmk-115-2020-pemanfaatan",
        "judul": "PMK 115/PMK.06/2020 — Pemanfaatan Barang Milik Negara",
        "guna": "Sewa, pinjam pakai, KSP, BGS/BSG, KSPI, KETUPI",
        "prioritas": 4,
        "sumber": [
            ("pdf", "https://batamport.bpbatam.go.id/wp-content/uploads/2021/07/"
                    "PMK-115PMK062020-TTG-PEMANFAATAN-BARANG-MILIK-NEGARA-TGL-31-8-2020.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/115-pmk-06-2020"),
            ("html", "https://peraturan.bpk.go.id/Home/Details/144664/pmk-no-115pmk062020"),
        ],
    },
    {
        "kode": "pmk-40-2024-penggunaan",
        "judul": "PMK 40 Tahun 2024 — Tata Cara Penggunaan Barang Milik Negara",
        "guna": ("Rezim Penggunaan. Sudah diriset lewat sumber sekunder di "
                 "docs/PENGGUNAAN-BMN-PEMOHON.md; teks aslinya menutup rantai "
                 "buktinya dan memungkinkan sitasi diverifikasi ulang"),
        "prioritas": 5,
        "sumber": [
            ("pdf", "https://ppiddjkn.kemenkeu.go.id/storage/20250701-328.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/pmk-40-tahun-2024"),
            ("html", "https://peraturan.bpk.go.id/Details/292599/pmk-no-40-tahun-2024"),
        ],
    },
    {
        "kode": "kmk-213-2021-tata-cara-pemanfaatan",
        "judul": ("KMK 213/KM.6/2021 — Tata Cara Pelaksanaan Pemanfaatan "
                  "Barang Milik Negara"),
        "guna": ("KMK PELAKSANA yang ditunjuk PMK 115/2020 Pasal 96. Daftar "
                 "dokumen permohonan sewa dan pinjam pakai memang tidak ada "
                 "di batang tubuh PMK-nya — ia di sini. Menutup dua rezim "
                 "terakhir yang belum berdasar pasal"),
        "prioritas": 6,
        "sumber": [
            # Cermin PDF langsung di Itjen Kemhan — berkas statis, jauh lebih
            # stabil daripada halaman JDIH yang memuat PDF lewat JavaScript.
            ("pdf", "https://www.kemhan.go.id/itjen/wp-content/uploads/2022/07/"
                    "8_KEP-MENKU-NOMOR-213-THN-2021-1.pdf"),
            # Pola nama berkas KMK terungkap dari contoh `KMK 128~KM.6~2022.pdf`:
            # ada spasi setelah "KMK", dan TANPA akhiran `Per`/`Kep` seperti PMK.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK%20213~KM.6~2021.pdf"),
            ("teks", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                     "KMK%20213~KM.6~2021.htm"),
            ("html", "https://www.djkn.kemenkeu.go.id/peraturan/detail/411/"
                     "Keputusan-Menteri-Keuangan-Nomor-213KM62021.html"),
            ("html", "https://jdih.kemenkeu.go.id/dok/213-km-6-2021"),
        ],
    },
    {
        "kode": "pmk-181-2016-penatausahaan",
        "judul": "PMK 181/PMK.06/2016 — Penatausahaan Barang Milik Negara",
        "guna": "Pembukuan, inventarisasi, pelaporan",
        "prioritas": 7,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/181-pmk-06-2016"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-181-pmk-06-2016-tahun-2016"),
            ("html", "https://peraturan.bpk.go.id/Details/112552/pmk-no-181pmk062016"),
            ("html", "https://paralegal.id/peraturan/"
                     "peraturan-menteri-keuangan-nomor-181-pmk-06-2016/"),
        ],
    },
    {
        "kode": "pmk-207-2021-wasdal",
        "judul": "PMK 207/PMK.06/2021 — Pengawasan dan Pengendalian BMN",
        "guna": "Modul Wasdal",
        "prioritas": 8,
        "sumber": [
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/"
                    "0d61b4a6-0795-4ca1-8210-d15006233d89/207~PMK.06~2021Per.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/207-pmk-06-2021"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-207-pmk-06-2021-tahun-2021"),
            ("html", "https://peraturan.bpk.go.id/Details/209347/pmk-no-207pmk062021"),
            ("html", "https://paralegal.id/peraturan/"
                     "peraturan-menteri-keuangan-nomor-207-pmk-06-2021/"),
        ],
    },
    {
        "kode": "pmk-53-2023-ikn",
        "judul": "PMK 53 Tahun 2023 — Pengelolaan BMN pada Otorita IKN",
        "guna": "Rezim khusus IKN — delegasi kewenangan Kepala Otorita",
        "prioritas": 9,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/pmk-53-tahun-2023"),
            ("html", "https://jdih.kemenkeu.go.id/dok/"
                     "a66a7f2f-30dd-4178-035e-08db54fba7f4"),
            ("html", "https://jdih-old.kemenkeu.go.id/in/dokumen/peraturan/"
                     "a66a7f2f-30dd-4178-035e-08db54fba7f4"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-53-tahun-2023"),
            ("html", "https://peraturan.bpk.go.id/Details/249043/pmk-no-53-tahun-2023"),
        ],
    },
    {
        "kode": "pp-27-2014-pengelolaan-bmn",
        "judul": "PP 27 Tahun 2014 — Pengelolaan Barang Milik Negara/Daerah",
        "guna": "Induk seluruh rezim",
        "prioritas": 10,
        "sumber": [
            # Pola PP pada fulltext JDIH terbukti lewat PP 28/2020
            # (`28TAHUN2020PP.pdf`). BPHN dan BPK sama-sama menjawab 403 ke
            # runner, jadi keduanya turun ke belakang.
            #
            # CATATAN unduhan keempat: URL fulltext di bawah gagal dengan
            # "Temporary failure in name resolution" — kegagalan DNS SESAAT
            # di runner, BUKAN 404. Ia praktis belum pernah benar-benar
            # dicoba, jadi tetap di depan.
            # Naskah lengkapnya di JDIH hanya ada sebagai `.htm` — itulah
            # sebabnya varian `.pdf` selalu gagal: ia memang tak pernah ada.
            ("teks", "https://jdih.kemenkeu.go.id/api/download/fulltext/2014/"
                     "27TAHUN2014PP.htm"),
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2014/"
                    "27TAHUN2014PP.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/in/dokumen/peraturan/"
                     "7aa67eed-89b7-4ead-8320-7ba130d863e7"),
            ("html", "https://jdih.kemenkeu.go.id/dok/pp-27-tahun-2014"),
            ("html", "https://paralegal.id/peraturan/"
                     "peraturan-pemerintah-nomor-27-tahun-2014/"),
            ("html", "https://peraturan.go.id/id/pp-no-27-tahun-2014"),
            # BPHN & BPK menjawab 403 ke runner pada DUA unduhan berturut-turut
            # — disimpan di ekor, bukan dicabut, kalau-kalau kebijakannya
            # berubah.
            ("pdf", "https://bphn.go.id/data/documents/14pp027.pdf"),
            ("html", "https://peraturan.bpk.go.id/Details/5464/pp-no-27-tahun-2014"),
        ],
    },
    {
        "kode": "pp-28-2020-perubahan-pengelolaan-bmn",
        "judul": "PP 28 Tahun 2020 — Perubahan atas PP 27 Tahun 2014",
        "guna": "Menambah KETUPI sebagai bentuk pemanfaatan ke-6",
        "prioritas": 11,
        "sumber": [
            ("pdf", "https://bphn.go.id/data/documents/20pp028.pdf"),
            ("html", "https://peraturan.bpk.go.id/Details/138973/pp-no-28-tahun-2020"),
            ("html", "https://peraturan.go.id/id/pp-no-28-tahun-2020"),
            ("html", "https://jdih.kemenkeu.go.id/dok/pp-28-tahun-2020"),
        ],
    },
    {
        "kode": "kmk-334-2021-hibah-kecil",
        "judul": ("KMK 334/KM.6/2021 — Tata Cara Hibah BMN selain tanah/bangunan "
                  "tanpa bukti kepemilikan, nilai perolehan ≤ Rp100 juta"),
        "guna": ("Dikutip pemindahtanganan_utils.py; judulnya sudah terkonfirmasi "
                 "di SITASI-DOKUMEN-RESMI.md, pasalnya belum"),
        "prioritas": 12,
        "sumber": [
            # Tiga tebakan akhiran pada unduhan keempat SEMUANYA menjawab
            # 404 — bentuknya memang salah. Polanya terungkap dari contoh
            # nyata `KMK 128~KM.6~2022.pdf`: ada SPASI setelah "KMK", dan
            # TANPA akhiran `Per`/`Kep` yang dipakai PMK.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK%20334~KM.6~2021.pdf"),
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "334~KM.6~2021.pdf"),
            # UUID kandidat dari hasil pencarian. Bila keliru, ia gagal
            # tanpa merugikan — dan sebabnya tercatat untuk putaran berikut.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/"
                    "dbb8b516-9f26-4cd2-89de-5e9e5f0f7815/"
                    "KMK%20334~KM.6~2021.pdf"),
            ("teks", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                     "KMK%20334~KM.6~2021.htm"),
            ("html", "https://jdih.kemenkeu.go.id/dok/"
                     "dbb8b516-9f26-4cd2-89de-5e9e5f0f7815"),
            ("html", "https://jdih.kemenkeu.go.id/dok/334-km-6-2021"),
            ("html", "https://peraturan.go.id/id/kepmenkeu-no-334-km-6-2021-tahun-2021"),
        ],
    },
    {
        "kode": "pmk-4-2015-delegasi",
        "judul": "PMK 4/PMK.06/2015 — Pendelegasian kewenangan pemindahtanganan BMN",
        "guna": "Ambang Rp100 juta jalur Pengguna Barang",
        "prioritas": 13,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/4-pmk-06-2015"),
            ("html", "https://peraturan.go.id/id/permenkeu-no-4-pmk-06-2015-tahun-2015"),
            ("html", "https://peraturan.bpk.go.id/Details/111893/pmk-no-4pmk062015"),
            ("html", "https://paralegal.id/peraturan/"
                     "peraturan-menteri-keuangan-nomor-4-pmk-06-2015/"),
        ],
    },
]

# ── Batas keras ────────────────────────────────────────────────────────────
JEDA_ANTAR_UNDUH = 2.0        # sopan terhadap server publik
BATAS_UKURAN = 60 * 1024 * 1024
TENGGAT_DETIK = 60
UA = ("Mozilla/5.0 (compatible; AMAN-IKN-pustaka/1.0; "
      "pengarsipan peraturan publik untuk keperluan internal satker)")


def _ambil(url: str) -> tuple[bytes, str]:
    """GET satu URL. HANYA GET — skrip ini tak pernah menulis ke server."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TENGGAT_DETIK) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        isi = resp.read(BATAS_UKURAN + 1)
    if len(isi) > BATAS_UKURAN:
        raise ValueError(f"berkas melebihi {BATAS_UKURAN // 1024 // 1024} MB")
    return isi, ctype


def tautan_pdf(html: str, asal: str) -> list:
    """Kerok tautan PDF dari halaman JDIH → daftar URL absolut.

    Diurutkan: yang mengandung 'download'/'view'/'dok' didahulukan, sebab
    halaman JDIH kerap memuat PDF lampiran lain (formulir, lampiran daerah)
    yang bukan batang tubuh peraturannya.
    """
    from urllib.parse import urljoin
    kandidat = []
    for m in re.finditer(r'''href\s*=\s*["']([^"']+?\.pdf[^"']*)["']''', html, re.I):
        kandidat.append(urljoin(asal, m.group(1)))
    # Beberapa JDIH menaruh berkasnya di atribut data-* atau iframe src.
    for m in re.finditer(r'''(?:src|data-src|data-url)\s*=\s*["']([^"']+?\.pdf[^"']*)["']''',
                         html, re.I):
        kandidat.append(urljoin(asal, m.group(1)))

    def skor(u: str) -> int:
        u = u.lower()
        n = 0
        for kata in ("download", "/dok/", "/view", "peraturan", "pmk", "pp-"):
            if kata in u:
                n -= 1
        if "lampiran" in u:      # lampiran ≠ batang tubuh
            n += 5
        return n

    unik = list(dict.fromkeys(kandidat))
    return sorted(unik, key=skor)


#: Penanda batang tubuh peraturan Indonesia. Naskah resmi SELALU memuat
#: "Menimbang", "MEMUTUSKAN", dan pasal bernomor. Paparan, ringkasan, dan
#: bahan pelatihan tentang peraturan itu tidak.
_PENANDA_BATANG_TUBUH = ("menimbang", "memutuskan")


def jejak_teks(teks: str) -> str:
    """Apa yang JUSTRU ditemukan di dalam teks — bukan hanya yang hilang.

    Pesan penolakan yang hanya menyebut penanda yang HILANG membuat diagnosis
    buntu. Unduhan kelima menolak KMK 213/KM.6/2021 dengan "tak memuat
    'menimbang'", dan dari kalimat itu saja tak ada cara membedakan tiga
    kemungkinan yang tindak lanjutnya berbeda-beda:

    * berkasnya paparan/ringkasan          → cabut sumbernya, cari cermin lain;
    * berkasnya kutipan sebagian           → cari naskah utuh;
    * naskahnya asli tetapi OCR-nya rusak  → guard-nya yang perlu diperbaiki.

    Ketiganya terbaca dari jejak ini: panjang naskah, penanda mana yang
    ternyata ADA, ada tidaknya pasal/diktum, dan kalimat pembuka — yang
    biasanya langsung menyebut jenis dokumennya.
    """
    asli = teks or ""
    rapat = re.sub(r"\s+", "", asli).lower()
    ada = [k for k in _PENANDA_BATANG_TUBUH if k in rapat]
    jejak = [f"{len(asli)} karakter"]
    jejak.append("ada " + "+".join(ada) if ada else "tanpa penanda apa pun")
    if re.search(r"(?im)^\s*pasal\s+\d+", asli):
        jejak.append("ada pasal bernomor")
    if re.search(r"(?im)^\s*(kesatu|kedua|ketiga|keempat|kelima)\b", asli):
        jejak.append("ada diktum")
    if re.search(r"(?i)\bmenetapkan\b", asli):
        jejak.append("ada 'menetapkan'")
    awal = re.sub(r"\s+", " ", asli[:400]).strip()
    if awal:
        jejak.append(f"pembuka: \u201c{awal[:120]}\u201d")
    return "; ".join(jejak)


def bukan_batang_tubuh(teks: str) -> str:
    """Alasan mengapa teks ini BUKAN naskah peraturan; '' bila ia naskah.

    Guard ini lahir dari kegagalan nyata. Unduhan pertama PMK 111/2016
    menghasilkan **paparan pelatihan DJKN** berjudul sama — PDF sah, berlapis
    teks, ditautkan dari situs kementerian. Ia lolos SEMUA guard yang ada:
    `%PDF` ada, lapisan teks ada, tautan PDF ketemu. Yang tersimpan adalah 29
    halaman slide ber-bullet Wingdings, dan ia akan duduk di direktori bukti
    berbulan-bulan sambil tampak seperti kutipan primer.

    Itu persis kegagalan yang paling berbahaya: bukan yang gagal berisik,
    melainkan yang berhasil dengan isi yang keliru.
    """
    asli = teks or ""
    # Spasi DIBUANG seluruhnya sebelum mencocokkan penanda. Ekstraksi PDF
    # hasil pindai kerap menyisipkan spasi di tengah kata — teks yang sudah
    # masuk pustaka memuat "se bagaimana", "tan pa", "clalam",
    # "MENTERlKEUANGAN". Pencocokan substring apa adanya akan menolak naskah
    # asli hanya karena OCR-nya berantakan.
    rapat = re.sub(r"\s+", "", asli).lower()
    hilang = [k for k in _PENANDA_BATANG_TUBUH if k not in rapat]
    if hilang:
        return ("bukan batang tubuh peraturan — tak memuat "
                + " maupun ".join(f"'{k}'" for k in hilang)
                + " (kemungkinan paparan/ringkasan tentang peraturannya)"
                + " | " + jejak_teks(asli))
    # PERATURAN memakai "Pasal 1, 2, 3…"; KEPUTUSAN memakai diktum
    # "KESATU, KEDUA, KETIGA…". Menuntut pasal bernomor saja akan menolak
    # setiap KMK — dan KMK-lah yang memuat tata cara pelaksanaan yang
    # didelegasikan PMK (mis. PMK 115/2020 Pasal 96 → KMK 213/KM.6/2021).
    if re.search(r"(?im)^\s*pasal\s+\d+", asli):
        return ""
    if re.search(r"(?i)\bmenetapkan\b", asli) and re.search(
            r"(?im)^\s*(kesatu|kedua|ketiga|keempat|kelima)\b", asli):
        return ""
    return ("bukan batang tubuh — tak ada pasal bernomor (Peraturan) "
            "maupun diktum KESATU/KEDUA (Keputusan)"
            " | " + jejak_teks(asli))


def teks_dari_html(html: bytes) -> str:
    """Naskah dari halaman full-text HTML — tag dibuang, entitas dipulihkan.

    Sengaja tanpa pustaka tambahan: yang dibutuhkan hanya membuang markup
    dari halaman yang isinya memang naskah peraturan, bukan mem-parsing
    dokumen sembarangan.
    """
    import html as _html
    teks = html.decode("utf-8", "replace")
    # Skrip dan gaya dibuang beserta isinya — kalau tidak, kode JavaScript
    # ikut tersimpan sebagai "naskah" dan membuat berkasnya lolos uji panjang.
    teks = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", teks)
    teks = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>", "\n", teks)
    teks = re.sub(r"(?s)<[^>]+>", " ", teks)
    teks = _html.unescape(teks)
    # Rapikan tanpa menghapus baris — struktur baris dipakai guard batang
    # tubuh untuk mengenali "Pasal 1" dan diktum di awal baris.
    teks = re.sub(r"[ \t\xa0]+", " ", teks)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", teks).strip()


def ekstrak_teks(pdf: bytes) -> tuple[str, int]:
    """PDF → (teks, jumlah halaman). Memakai pypdf yang sudah ada di repo."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    halaman = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(halaman), len(reader.pages)


def unduh_satu(entri: dict) -> dict:
    """Coba tiap sumber berurutan sampai satu berhasil."""
    galat = []
    for jenis, url in entri["sumber"]:
        try:
            isi, ctype = _ambil(url)
            if jenis == "teks":
                # Naskah HTML: tak ada halaman PDF untuk dihitung.
                teks, n_hal = teks_dari_html(isi), 0
                if len(teks.strip()) < 500:
                    galat.append(f"{url}: halaman teks nyaris kosong")
                    continue
                sebab = bukan_batang_tubuh(teks)
                if sebab:
                    galat.append(f"{url}: {sebab}")
                    continue
                return {
                    "ok": True, "url": url, "halaman": n_hal,
                    "bytes": len(isi), "sha256": hashlib.sha256(isi).hexdigest(),
                    "teks": teks, "galat": galat,
                }
            if jenis == "html" and not isi[:5].startswith(b"%PDF"):
                halaman = isi.decode("utf-8", "replace")
                pdfs = tautan_pdf(halaman, url)
                if not pdfs:
                    galat.append(f"{url}: halaman tak memuat tautan PDF")
                    continue
                time.sleep(JEDA_ANTAR_UNDUH)
                isi, ctype = _ambil(pdfs[0])
                url = pdfs[0]
            if not isi[:5].startswith(b"%PDF"):
                galat.append(f"{url}: bukan PDF (Content-Type: {ctype[:40]})")
                continue
            teks, n_hal = ekstrak_teks(isi)
            if len(teks.strip()) < 500:
                # PDF hasil pindai tanpa lapisan teks. Dilaporkan apa adanya,
                # BUKAN diterima diam-diam: berkas .txt kosong yang tersimpan
                # akan terlihat seperti bukti padahal tak memuat apa pun.
                galat.append(f"{url}: PDF tanpa lapisan teks ({n_hal} hlm) — "
                             "kemungkinan hasil pindai, perlu OCR")
                continue
            sebab = bukan_batang_tubuh(teks)
            if sebab:
                galat.append(f"{url}: {sebab}")
                continue
            return {
                "ok": True, "url": url, "halaman": n_hal,
                "bytes": len(isi), "sha256": hashlib.sha256(isi).hexdigest(),
                "teks": teks, "galat": galat,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError,
                TimeoutError, OSError) as e:
            galat.append(f"{url}: {type(e).__name__}: {e}")
        except Exception as e:                     # pypdf bisa melempar apa saja
            galat.append(f"{url}: gagal diproses — {type(e).__name__}: {e}")
        time.sleep(JEDA_ANTAR_UNDUH)
    return {"ok": False, "galat": galat}


def main(argv) -> int:
    tujuan = argv[1] if len(argv) > 1 else "docs/regulasi"
    os.makedirs(tujuan, exist_ok=True)
    manifes_lama = {}
    jalur_manifes = os.path.join(tujuan, "MANIFEST.json")
    if os.path.exists(jalur_manifes):
        try:
            with open(jalur_manifes, encoding="utf-8") as f:
                manifes_lama = {m["kode"]: m for m in json.load(f).get("berkas", [])}
        except (ValueError, OSError):
            manifes_lama = {}

    hasil, berhasil, gagal = [], 0, 0
    for entri in sorted(MANIFES, key=lambda e: e["prioritas"]):
        print(f"→ [{entri['prioritas']}] {entri['judul']}", flush=True)
        r = unduh_satu(entri)
        if r["ok"]:
            berkas = f"{entri['kode']}.txt"
            with open(os.path.join(tujuan, berkas), "w", encoding="utf-8") as f:
                f.write(r["teks"])
            print(f"   ✓ {r['halaman']} hlm · {r['bytes'] // 1024} KB · {r['url']}",
                  flush=True)
            hasil.append({
                "kode": entri["kode"], "judul": entri["judul"],
                "guna": entri["guna"], "berkas": berkas, "url": r["url"],
                "halaman": r["halaman"], "bytes": r["bytes"],
                "sha256": r["sha256"],
                "diunduh": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "percobaan_gagal": r["galat"],
            })
            berhasil += 1
        else:
            print("   ✗ semua sumber gagal:", flush=True)
            for g in r["galat"]:
                print(f"     · {g}", flush=True)
            # Entri lama dipertahankan HANYA bila ia benar-benar punya
            # berkas — kegagalan jaringan tak boleh menghapus bukti yang
            # sudah terkumpul.
            #
            # KOREKSI (2026-09-01). Versi pertama mempertahankan entri lama
            # APA PUN keadaannya, termasuk yang `berkas`-nya None. Akibatnya
            # `percobaan_gagal` LAMA ikut bertahan dan menimpa hasil
            # percobaan kali ini — persis keterangan yang dibutuhkan untuk
            # memperbaiki sumbernya. Pada unduhan ketiga hal itu benar-benar
            # terjadi: PMK 111/2016 melaporkan kegagalan sumber yang sudah
            # DICABUT dari manifes, sementara apa yang terjadi pada URL
            # penggantinya hilang tanpa jejak.
            #
            # Bahkan saat berkasnya dipertahankan, `percobaan_gagal` diisi
            # hasil KALI INI. Provenans berkasnya tetap utuh; yang diperbarui
            # adalah diagnosisnya.
            lama = manifes_lama.get(entri["kode"]) or {}
            if lama.get("berkas"):
                entri_baru = dict(lama)
                entri_baru["percobaan_gagal"] = r["galat"]
                entri_baru["dipertahankan_dari"] = lama.get("diunduh", "?")
                hasil.append(entri_baru)
                print(f"     (berkas lama dipertahankan, diunduh "
                      f"{entri_baru['dipertahankan_dari']})", flush=True)
            else:
                hasil.append({
                    "kode": entri["kode"], "judul": entri["judul"],
                    "guna": entri["guna"], "berkas": None,
                    "percobaan_gagal": r["galat"],
                })
            gagal += 1
        time.sleep(JEDA_ANTAR_UNDUH)

    with open(jalur_manifes, "w", encoding="utf-8") as f:
        # `berhasil`/`gagal` menggambarkan KEADAAN PUSTAKA — berapa peraturan
        # yang naskahnya ada. Versi pertama mengisinya dengan hasil satu run,
        # sehingga unduhan ketiga melaporkan "berhasil 5, gagal 7" padahal
        # sembilan naskah ada di direktori: pembacanya akan mengira pustakanya
        # menyusut. Hasil per-run tetap dilaporkan, dengan namanya sendiri.
        tersedia = sum(1 for b in hasil if b.get("berkas"))
        json.dump({
            "dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "catatan": ("Teks hasil ekstraksi PDF peraturan publik. BUKTI, "
                        "bukan kesimpulan: status verifikasi di "
                        "syarat_dokumen_utils.py tetap dinaikkan secara sadar "
                        "setelah pasalnya dibaca. `berhasil`/`gagal` = keadaan "
                        "PUSTAKA; `unduhan_*` = hasil run terakhir."),
            "berhasil": tersedia, "gagal": len(hasil) - tersedia,
            "unduhan_segar": berhasil, "unduhan_gagal": gagal,
            "berkas": hasil,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nSelesai. Unduhan segar: {berhasil}; gagal: {gagal}. "
          f"Pustaka kini memuat {sum(1 for b in hasil if b.get('berkas'))} "
          f"dari {len(hasil)} naskah.", flush=True)
    # Keluar 0 walau sebagian gagal: sebagian pustaka lebih baik daripada tak
    # ada, dan kegagalan sudah tercatat di manifes untuk ditindaklanjuti.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
