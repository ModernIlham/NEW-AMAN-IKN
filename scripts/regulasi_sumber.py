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

import difflib
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

#: Bentuk terbitan yang dikenali. Bawaannya `peraturan` — batang tubuh utuh
#: dengan konsiderans. `lampiran` HANYA boleh dipasang per-entri, setelah
#: naskahnya dibuktikan; lihat `bukan_batang_tubuh`.
BENTUK_PERATURAN = "peraturan"
BENTUK_LAMPIRAN = "lampiran"
#: URAIAN TENTANG peraturan, bukan peraturannya — artikel unit Kemenkeu,
#: pedoman satker, dan sejenisnya. Berkasnya berawalan `rujukan-` dan TIDAK
#: PERNAH boleh menjadi dasar status `teks-primer` di
#: `backend/sitasi_regulasi.py`; ada uji yang menagihnya.
BENTUK_RUJUKAN = "rujukan"


MANIFES = [
    {
        "kode": "pmk-111-2016-pemindahtanganan",
        "penanda": ["111/PMK.06/2016"],
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
        "penanda": ["165/PMK.06/2021"],
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
        "penanda": ["83/PMK.06/2016"],
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
        "penanda": ["115/PMK.06/2020"],
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
        "penanda": ["NOMOR 40 TAHUN 2024", "40/PMK.06/2024"],
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
        # DUA sumber resmi yang saling bebas — cermin Itjen Kemhan dan
        # endpoint unduh DJKN sendiri — mengembalikan berkas yang SAMA
        # PERSIS (469.096 karakter). Isinya lampiran KMK-nya: dibuka
        # "BAB I PENDAHULUAN", memuat MEMUTUSKAN, Menetapkan, diktum, dan
        # pasal bernomor — tetapi tanpa "Menimbang", yang tinggal di
        # halaman diktum terpisah.
        #
        # Dugaan pertama adalah OCR yang menukar huruf. Laporan kemiripan
        # membantahnya: yang ditemukan 'menyimpang' dan 'membangu' — kata
        # Indonesia biasa, bukan "Menimbang" yang rusak. Jadi naskahnya
        # memang terbit dalam bentuk ini, dan bentuk itulah yang diakui.
        "bentuk": BENTUK_LAMPIRAN,
        "penanda": ["213/KM.6/2021"],
        "judul": ("KMK 213/KM.6/2021 — Tata Cara Pelaksanaan Pemanfaatan "
                  "Barang Milik Negara"),
        "guna": ("KMK PELAKSANA yang ditunjuk PMK 115/2020 Pasal 96. Daftar "
                 "dokumen permohonan sewa dan pinjam pakai memang tidak ada "
                 "di batang tubuh PMK-nya — ia di sini. Menutup dua rezim "
                 "terakhir yang belum berdasar pasal"),
        "prioritas": 6,
        "sumber": [
            # URUTAN ADALAH PREFERENSI: perulangan berhenti pada sumber
            # PERTAMA yang lolos penjagaan, jadi yang paling lengkap harus
            # didahulukan. Cermin Kemhan sudah terbukti berhasil — kalau ia
            # tetap di depan, jalur mana pun yang ditambahkan di belakangnya
            # tak akan pernah dicoba.
            #
            # Jalur `baca/` adalah bentuk KETIGA di DJKN, berbeda dari
            # `detail/` (JavaScript, dua putaran gagal) maupun `download/`
            # (berhasil, tetapi lampirannya saja). Bila ia menyajikan dokumen
            # yang UTUH — halaman diktum berikut lampirannya — naskah itulah
            # yang seharusnya masuk pustaka. Karena itu ia didahulukan, dengan
            # `html` (cari tautan berkas) lalu `teks` (halamannya sendiri yang
            # memuat naskah).
            ("html", "https://www.djkn.kemenkeu.go.id/peraturan/baca/411/"
                     "Keputusan-Menteri-Keuangan-Nomor-213KM62021.html"),
            ("teks", "https://www.djkn.kemenkeu.go.id/peraturan/baca/411/"
                     "Keputusan-Menteri-Keuangan-Nomor-213KM62021.html"),
            # Cermin PDF langsung di Itjen Kemhan — berkas statis, jauh lebih
            # stabil daripada halaman JDIH yang memuat PDF lewat JavaScript.
            # Sudah terbukti berhasil, jadi ia jaring pengaman: bila `baca/`
            # tak memberi apa-apa, lampirannya tetap masuk.
            ("pdf", "https://www.kemhan.go.id/itjen/wp-content/uploads/2022/07/"
                    "8_KEP-MENKU-NOMOR-213-THN-2021-1.pdf"),
            # Pola nama berkas KMK terungkap dari contoh `KMK 128~KM.6~2022.pdf`:
            # ada spasi setelah "KMK", dan TANPA akhiran `Per`/`Kep` seperti PMK.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK%20213~KM.6~2021.pdf"),
            ("teks", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                     "KMK%20213~KM.6~2021.htm"),
            # DJKN memisahkan halaman `detail/` (JavaScript, tak memuat
            # tautan) dari jalur `download/` yang MENGIRIM berkasnya langsung.
            # Terkonfirmasi pada tetangga nomornya: `download/412/…216KM62021`
            # dan `download/388/…53PMK062021` keduanya mengembalikan naskah.
            # Berakhiran `.html` tetapi isinya PDF — penjaga `%PDF` sudah
            # memeriksa isi, bukan nama berkas, jadi jenis `pdf` benar di sini.
            ("pdf", "https://www.djkn.kemenkeu.go.id/peraturan/download/411/"
                    "Keputusan-Menteri-Keuangan-Nomor-213KM62021.html"),
            # JDIH menamai KMK dengan TIGA bentuk berbeda, bukan satu:
            #   `KMK 128~KM.6~2022.pdf`  (spasi)
            #   `KMK-216~KM.6~2021.pdf`  (tanda hubung)
            #   `KMK_33_KM.4_2023.pdf`   (garis bawah, pemisah `~` pun hilang)
            # Unduhan keempat sampai keenam hanya mencoba bentuk pertama.
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK-213~KM.6~2021.pdf"),
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK_213_KM.6_2021.pdf"),
            ("html", "https://www.djkn.kemenkeu.go.id/peraturan/detail/411/"
                     "Keputusan-Menteri-Keuangan-Nomor-213KM62021.html"),
            # Akhiran `/view` adalah halaman baca JDIH — bentuk yang berbeda
            # dari `/dok/<slug>`, dan kadang memuat tautan berkasnya.
            ("html", "https://jdih.kemenkeu.go.id/dok/213-km-6-2021/view"),
            ("html", "https://jdih.kemenkeu.go.id/dok/213-km-6-2021"),
        ],
    },
    {
        "kode": "pmk-181-2016-penatausahaan",
        "penanda": ["181/PMK.06/2016"],
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
        "penanda": ["207/PMK.06/2021"],
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
        "penanda": ["NOMOR 53 TAHUN 2023", "53/PMK.06/2023"],
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
        "penanda": ["NOMOR 27 TAHUN 2014"],
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
        "penanda": ["NOMOR 28 TAHUN 2020"],
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
        "penanda": ["334/KM.6/2021"],
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
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK-334~KM.6~2021.pdf"),
            ("pdf", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                    "KMK_334_KM.6_2021.pdf"),
            ("teks", "https://jdih.kemenkeu.go.id/api/download/fulltext/2021/"
                     "KMK%20334~KM.6~2021.htm"),
            ("html", "https://jdih.kemenkeu.go.id/dok/334-km-6-2021/view"),
            ("html", "https://jdih.kemenkeu.go.id/dok/"
                     "dbb8b516-9f26-4cd2-89de-5e9e5f0f7815"),
            ("html", "https://jdih.kemenkeu.go.id/dok/334-km-6-2021"),
            ("html", "https://peraturan.go.id/id/kepmenkeu-no-334-km-6-2021-tahun-2021"),
        ],
    },
    {
        "kode": "rujukan-kmk-334-2021-hibah-kecil",
        "penanda": ["334/KM.6/2021", "KMK Nomor 334 Tahun 2021"],
        "judul": ("RUJUKAN — Tata Cara Hibah BMN selain tanah/bangunan tanpa "
                  "bukti kepemilikan ≤ Rp100 juta (KPPN Lubuk Sikaping, DJPb)"),
        "guna": ("URAIAN TENTANG KMK 334/KM.6/2021, bukan naskahnya. KMK itu "
                 "tidak terindeks di bagian peraturan DJKN dan sepuluh sumber "
                 "unduhnya menjawab 404. Sampai naskahnya masuk, uraian dari "
                 "unit Kemenkeu ini yang paling dekat — dan statusnya harus "
                 "tetap terbaca sebagai rujukan, bukan bukti"),
        "prioritas": 14,
        "bentuk": BENTUK_RUJUKAN,
        "sumber": [
            ("teks", "https://djpb.kemenkeu.go.id/kppn/lubuksikaping/id/"
                     "data-publikasi/artikel/3245-tata-cara-hibah-barang-milik-"
                     "negara-bmn-selain-tanah-dan-atau-bangunan-yang-tidak-"
                     "memiliki-bukti-kepemilikan-dengan-nilai-perolehan-sampai-"
                     "dengan-rp100-000-000-berdasarkan-kmk-nomor-334-tahun-2021"
                     ".html"),
            ("teks", "https://djpb.kemenkeu.go.id/kppn/lubuksikaping/id/"
                     "data-publikasi/309-artikel/3245-tata-cara-hibah-barang-"
                     "milik-negara-bmn-selain-tanah-dan-atau-bangunan-yang-"
                     "tidak-memiliki-bukti-kepemilikan-dengan-nilai-perolehan-"
                     "sampai-dengan-rp100-000-000-berdasarkan-kmk-nomor-334-"
                     "tahun-2021.html"),
        ],
    },
    {
        "kode": "pmk-4-2015-delegasi",
        "penanda": ["4/PMK.06/2015"],
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


#: Huruf yang kerap tertukar dengan angka pada hasil pindai. Naskah PP
#: 28/2020 di pustaka ini menulis tahunnya "2O2O" — dengan huruf O.
_HURUF_MIRIP_ANGKA = str.maketrans({"o": "0", "l": "1", "i": "1"})


def _rapat_angka(teks: str) -> str:
    """Teks tanpa spasi, huruf kecil, huruf mirip-angka dinormalkan."""
    return re.sub(r"\s+", "", teks or "").lower().translate(_HURUF_MIRIP_ANGKA)


def nomor_tak_cocok(teks: str, penanda) -> str:
    """Alasan bila naskah ini bukan peraturan yang diminta; '' bila cocok.

    Guard ini lahir dari pencarian sumber KMK 334/KM.6/2021. Hasilnya
    berulang kali menawarkan **KMK 334/KMK.01/2021** — nomor yang sama,
    tahun yang sama, sama-sama tentang pengelolaan BMN, tetapi peraturan
    yang BERBEDA (yang satu tata cara hibah kecil, yang lain pengelolaan
    BMN di lingkungan Kemenkeu).

    `bukan_batang_tubuh` tak bisa menolongnya: dokumen itu peraturan yang
    sah dan berstruktur benar. Ia akan lolos setiap penjagaan yang ada, lalu
    duduk di pustaka dengan nama berkas yang salah — kekeliruan yang jauh
    lebih mahal daripada gagal unduh, sebab ia tampak seperti bukti.

    **Batas kemampuannya jangan dilebih-lebihkan.** Guard ini membuktikan
    nomor yang diminta DISEBUT di dalam naskah, bukan bahwa naskahnya
    memang peraturan itu: tiap PMK menyebut PP 27/2014 di bagian Mengingat,
    jadi penanda PP 27 cocok dengan hampir semua berkas di pustaka. Yang
    ditangkapnya adalah kasus "dokumennya sama sekali lain" — dan justru
    itulah yang hampir terjadi pada KMK 334.
    """
    if not penanda:
        return ""
    rapat = _rapat_angka(teks)
    if any(_rapat_angka(p) in rapat for p in penanda):
        return ""
    return ("naskah tak menyebut nomornya sendiri (" + " / ".join(penanda)
            + ") — kemungkinan peraturan LAIN dengan nomor mirip")


def _nyaris(teks: str, hilang) -> list:
    """Kata di dalam naskah yang MIRIP penanda yang hilang.

    Pembuangan spasi sudah menangani OCR yang memecah kata ("se bagaimana",
    "tan pa"). Yang tersisa adalah OCR yang MENUKAR huruf — "clalam" untuk
    "dalam", "MENTERlKEUANGAN" untuk "MENTERI KEUANGAN". Kalau itu yang
    menimpa kata "Menimbang", penolakannya berbunyi persis sama dengan
    penolakan sebuah paparan, dan dua putaran unduhan sudah terbuang untuk
    membedakannya.

    Kemiripan dilaporkan, BUKAN diterima: melonggarkan pencocokan penanda
    demi OCR akan membuka jalan yang sama bagi ringkasan yang kebetulan
    memuat kata serupa. Yang dibutuhkan cuma tahu ke mana harus melihat.
    """
    if not hilang:
        return []
    kata = {k.lower() for k in re.findall(r"[A-Za-z]{5,15}", teks or "")}
    if len(kata) > 40000:      # naskah raksasa: cukup contoh secukupnya
        kata = set(sorted(kata)[:40000])
    hasil = []
    for penanda in hilang:
        for cocok in difflib.get_close_matches(penanda, kata, n=2, cutoff=0.8):
            hasil.append(f"'{cocok}'~'{penanda}'")
    return hasil


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
    mirip = _nyaris(asli, [k for k in _PENANDA_BATANG_TUBUH if k not in rapat])
    if mirip:
        jejak.append("nyaris: " + ", ".join(mirip))
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


def bukan_batang_tubuh(teks: str, bentuk: str = BENTUK_PERATURAN) -> str:
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
    if bentuk == BENTUK_RUJUKAN:
        # Rujukan memang BUKAN batang tubuh — menuntutnya berarti menolak
        # setiap uraian. Yang tersisa hanyalah penjagaan bahwa ia sebuah
        # tulisan utuh, bukan halaman galat atau menu navigasi; nomornya
        # sendiri ditagih terpisah oleh `nomor_tak_cocok`.
        return ("" if len(asli.strip()) >= 2000 else
                "rujukan terlalu pendek untuk sebuah uraian | "
                + jejak_teks(asli))
    if bentuk == BENTUK_LAMPIRAN:
        # Sebagian Keputusan diterbitkan sebagai LAMPIRAN yang berdiri
        # sendiri: konsiderans ("Menimbang") tinggal di halaman diktum yang
        # terbit terpisah, sedangkan tata caranya — yang justru dicari —
        # ada di lampirannya. Menuntut "Menimbang" pada berkas semacam itu
        # menolak satu-satunya naskah yang tersedia.
        #
        # Kelonggaran ini TIDAK berlaku umum. Ia dipasang per-entri, hanya
        # setelah naskahnya dibuktikan, dan tetap menuntut penanda lain:
        # "MEMUTUSKAN", BAB bernomor romawi, serta pasal atau diktum.
        # Ditambah `nomor_tak_cocok`, paparan tak bisa lewat jalur ini.
        if not re.search(r"(?i)\bbab\s+(i|ii|iii|iv|v)\b", asli):
            return ("ditandai bentuk lampiran tetapi tak ada BAB bernomor "
                    "romawi | " + jejak_teks(asli))
        wajib = ("memutuskan",)
    else:
        wajib = _PENANDA_BATANG_TUBUH
    hilang = [k for k in wajib if k not in rapat]
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


def _sebab_tolak(teks: str, entri: dict) -> str:
    """Seluruh penjagaan isi dalam satu tempat.

    Dua jalur unduh — PDF dan naskah HTML — harus menerapkan penjagaan yang
    SAMA. Saat keduanya memanggil guard-nya sendiri-sendiri, penjagaan yang
    ditambahkan belakangan mudah terpasang di satu jalur saja, dan jalur yang
    terlewat tak akan berbunyi.
    """
    return (bukan_batang_tubuh(teks, entri.get("bentuk", BENTUK_PERATURAN))
            or nomor_tak_cocok(teks, entri.get("penanda")))


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
                sebab = _sebab_tolak(teks, entri)
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
            sebab = _sebab_tolak(teks, entri)
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
                "bentuk": entri.get("bentuk", BENTUK_PERATURAN),
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
                entri_baru["bentuk"] = entri.get("bentuk", BENTUK_PERATURAN)
                entri_baru["percobaan_gagal"] = r["galat"]
                entri_baru["dipertahankan_dari"] = lama.get("diunduh", "?")
                hasil.append(entri_baru)
                print(f"     (berkas lama dipertahankan, diunduh "
                      f"{entri_baru['dipertahankan_dari']})", flush=True)
            else:
                hasil.append({
                    "kode": entri["kode"], "judul": entri["judul"],
                    "bentuk": entri.get("bentuk", BENTUK_PERATURAN),
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
        # RUJUKAN dihitung TERPISAH. Kalau ia ikut masuk "berhasil",
        # pustaka akan terbaca "12 dari 14 naskah" padahal naskah primernya
        # tetap 11 dari 13 — angka yang membesar tanpa satu pun peraturan
        # baru terbaca. Itu jenis laporan yang sudah dua kali menyesatkan
        # putaran berikutnya.
        primer = [b for b in hasil if b.get("bentuk") != BENTUK_RUJUKAN]
        rujukan = [b for b in hasil if b.get("bentuk") == BENTUK_RUJUKAN]
        tersedia = sum(1 for b in primer if b.get("berkas"))
        rujukan_ada = sum(1 for b in rujukan if b.get("berkas"))
        json.dump({
            "dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "catatan": ("Teks hasil ekstraksi PDF peraturan publik. BUKTI, "
                        "bukan kesimpulan: status verifikasi di "
                        "syarat_dokumen_utils.py tetap dinaikkan secara sadar "
                        "setelah pasalnya dibaca. `berhasil`/`gagal` = keadaan "
                        "PUSTAKA naskah PRIMER; `rujukan_*` dihitung terpisah "
                        "karena berkas berawalan `rujukan-` adalah URAIAN "
                        "TENTANG peraturan, bukan naskahnya, dan tak pernah "
                        "boleh menjadi dasar status `teks-primer`; "
                        "`unduhan_*` = hasil run terakhir."),
            "berhasil": tersedia, "gagal": len(primer) - tersedia,
            "rujukan_ada": rujukan_ada,
            "rujukan_belum": len(rujukan) - rujukan_ada,
            "unduhan_segar": berhasil, "unduhan_gagal": gagal,
            "berkas": hasil,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nSelesai. Unduhan segar: {berhasil}; gagal: {gagal}. "
          f"Pustaka kini memuat {tersedia} dari {len(primer)} naskah primer "
          f"dan {rujukan_ada} dari {len(rujukan)} rujukan.", flush=True)
    # Keluar 0 walau sebagian gagal: sebagian pustaka lebih baik daripada tak
    # ada, dan kegagalan sudah tercatat di manifes untuk ditindaklanjuti.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
