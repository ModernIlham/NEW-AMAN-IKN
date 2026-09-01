# Syarat Dokumen Usulan BMN — daftar periksa per rezim

> Sumber kebenaran kode: `backend/syarat_dokumen_utils.py`.
> Dokumen ini menjelaskan **mengapa** tabel itu berbentuk demikian.
> Rezim Penggunaan diuraikan lengkap di `docs/PENGGUNAAN-BMN-PEMOHON.md`.

## Ringkas untuk yang terburu-buru

1. **Daftar sembilan butir wajib itu sudah usang untuk Penggunaan.** Ia
   berasal dari **PMK 246/PMK.06/2014 jo. 76/PMK.06/2019**. Untuk rezim
   Penggunaan keduanya digantikan **PMK 40 Tahun 2024**, yang menyusun
   daftarnya **bercabang per jenis objek** (Pasal 11 ayat (2) huruf a–g).
2. **Tabel kewenangan Rp100 juta pada artikel KPKNL tetap sejalan** dengan
   PMK 40/2024 (Pasal 6 ayat (3) dan Pasal 7 ayat (3)) — yang berubah adalah
   daftar lampirannya, bukan ambangnya.
3. **BAST Penetapan Status Penggunaan BUKAN berkas usulan.** Lihat §4.
4. Setiap butir membawa **kekuatan buktinya sendiri**. Tiga tingkat, §2.

---

## 1. Kenapa "sembilan slot wajib" salah

Sembilan slot seragam akan:

- menagih **sertipikat** kepada pemilik laptop;
- menagih **IMB/PBG** kepada pemilik kendaraan;
- menagih **SPTJ** selalu, padahal SPTJ adalah **pengganti** dokumen yang
  tidak ada (PMK 40/2024 Pasal 11 ayat (3)–(7));
- menagih **KIB** atas dasar PMK 40/2024 — padahal kata "KIB" maupun "Kartu
  Identitas Barang" **tidak ada** di seluruh PMK itu.

PMK memecah tanah/bangunan menjadi **tiga** keranjang lampiran terpisah
(huruf a tanah; huruf b bangunan; huruf c tanah **dan** bangunan). Frasa
*"tanah dan/atau bangunan"* hanya dipakai untuk objek **kewenangan**, tak
pernah untuk lampiran. Karena itu form punya **empat** cabang jenis objek,
bukan dua.

## 2. Tiga tingkat kekuatan bukti

| Penanda | Artinya | Perlakuan di layar |
|---|---|---|
| `terverifikasi` | Pasalnya sudah dibaca dan dikutip di dokumen repo | Boleh jadi butir wajib |
| `empiris_siman` | **Terbaca dari layar SIMAN V2 sendiri** | Boleh jadi butir wajib — ia yang menentukan diterima/tidaknya unggahan |
| `belum_terverifikasi` | Praktik lapangan / booklet KPKNL | **Anjuran saja**, tak boleh jadi gerbang |

Sumber primer (`jdih.kemenkeu.go.id`, `peraturan.bpk.go.id`,
`djkn.kemenkeu.go.id`) **terblokir** dari lingkungan pengembangan — lihat
`docs/SITASI-DOKUMEN-RESMI.md`. Menyeragamkan seluruh daftar jadi "wajib"
akan menyembunyikan perbedaan antara pasal yang sudah dibaca dan tebakan.

**Uji `test_rezim_penggunaan_setiap_wajibnya_berdasar_pasal` menegakkan ini:**
rezim yang diklaim berdasar pasal tak boleh punya satu pun butir wajib yang
belum terverifikasi. Uji itu sudah menangkap dua kesalahan saya sendiri —
`daftar_bmn` dan `lapor_kehilangan` — saat tabel ini pertama ditulis.

## 3. Muatan surat ≠ lampiran

Beberapa pasal meminta datanya ada **di dalam** surat permohonan tanpa pernah
menyebutnya berkas terpisah — data BMN pada Pasal 11, 24, 34, 46, dan 54.
Menagihnya sebagai unggahan akan melaporkan "belum lengkap" untuk usulan yang
sebenarnya sudah benar; menghapusnya akan menyembunyikan kewajiban yang nyata.

Karena itu ada sifat **`muatan`**: ditampilkan, tidak dihitung sebagai berkas
kurang, dan keterangannya menyebut ia bagian isi surat.

## 4. BAST PSP tidak diminta sebagai berkas usulan

Permintaan pemilik: *"untuk output BERITA ACARA SERAH TERIMA PENETAPAN STATUS
PENGGUNAAN BARANG MILIK NEGARA harusnya tidak diperlukan."*

Benar menurut teksnya. Pasal 11 ayat (2) **tidak pernah** meminta BAST sebagai
lampiran yang berdiri sendiri. BAST muncul di sana hanya sebagai
`dok_lain_bast` — **pengganti** dokumen kepemilikan yang tidak ada (huruf b,
c, dan d angka 2).

BAST PSP yang dicetak AMAN adalah dokumen serah terima **internal** kepada
pemegang, dan ia terbit **sesudah** SK-nya ada. Menagihnya sebagai syarat
usulan akan membalik urutan sebab-akibat: berkas untuk **memperoleh** SK tidak
mungkin memuat dokumen yang lahir **dari** SK itu.

Tombol unduh BAST PSP **tetap ada** di register PSP — ia dokumen internal yang
memang berguna. Yang berubah: ia tidak lagi muncul sebagai butir daftar
periksa usulan.

## 5. Daftar per rezim

### 5.1 Penetapan Status Penggunaan (PSP) — [F] PMK 40/2024 Pasal 11

> **Diverifikasi dari teks primer 2026-09-01** (`docs/regulasi/pmk-40-2024-penggunaan.txt`).
> Tabel di bawah dibaca langsung dari pasalnya, bukan dari ringkasan.

| Objek | Yang diminta pasal |
|---|---|
| **Tanah** | fotokopi **sertipikat** — hanya itu (huruf a) |
| **Bangunan** | IMB/PBG + dokumen perolehan + **dokumen lain termasuk BAST perolehan** (huruf b angka 1–3) |
| **Tanah dan bangunan** | sertipikat + IMB/PBG + dokumen perolehan bangunan + **dokumen lain termasuk BAST** (huruf c angka 1–4) |
| **Selain t/b, punya dokumen kepemilikan** | dokumen kepemilikan (BPKB/kapal/pesawat/setara) **+ dokumen lain termasuk STNK atau BAST** (huruf d angka 1 huruf a dan b) |
| **Selain t/b, tanpa dokumen kepemilikan, ≥ Rp100 juta/unit** | **BAST perolehan** + dokumen lain (huruf d angka 2) |
| **Untuk PMPP** | + dokumen penganggaran, reviu APIP/BPK, sertipikat/IMB/dokumen perolehan sesuai objek, BAST perolehan, dan BAST pengelolaan sementara bila fisiknya tak dikuasai (huruf e angka 1–7) |
| **PMPP, DIPA tak tegas** | + **KAK, RKA-K/L, atau POK** (huruf f) |
| **Tanah BELUM bersertipikat** | sertipikat **DIGANTI** SPTJ bermeterai dari pejabat struktural, **dilengkapi** akta jual beli/girik/letter C/BAST/ledger jalan, surat keterangan lurah/camat, surat permohonan pendaftaran hak, dan/atau dokumen penguasaan (ayat (3) huruf a–d) |
| **Semua fotokopi** | + **Surat Keterangan Kebenaran Fotokopi** (huruf g) |
| **Semua unggahan pindaian** | + **Surat Keterangan Kebenaran Arsip Digital** (Pasal 73 ayat (1) huruf a) |

Nama baku Surat Keterangan Kebenaran Arsip Digital **belum ditetapkan** PMK —
konfirmasikan judulnya ke KPKNL sebelum templatenya dibekukan.

#### Tiga koreksi yang hanya muncul setelah pasalnya dibaca

Registry pertama dibangun dari riset sekunder. Membaca teks aslinya
mengonfirmasi sebagian besarnya **dan menemukan tiga kekurangan nyata**:

1. **"Dokumen lain termasuk BAST perolehan" diminta jauh lebih luas** —
   huruf b angka 3, huruf c angka 4, huruf d angka 1 huruf b, dan huruf d
   angka 2. Satu-satunya yang tidak dimintai adalah **tanah berdiri sendiri**.
   Registry lama hanya menagihnya pada cabang terakhir, sehingga **pemegang
   gedung tak pernah ditagih BAST perolehan** yang pasalnya minta.
2. **SPTJ bukan pengganti dokumen apa pun yang hilang.** Ayat (3)
   dikecualikan dari huruf a, huruf c angka 1, dan huruf e angka 3 —
   ketiganya tentang **sertipikat tanah**. SPTJ tak pernah menggantikan BPKB
   kendaraan ataupun IMB bangunan. Dan ia wajib **dilengkapi** empat dokumen
   pendukung yang registry lama tak punya sama sekali.
3. **Huruf f tak ada di registry lama.** Bila DIPA tak tegas menyatakan BMN
   untuk PMPP, permohonan harus didukung KAK/RKA-K/L/POK.

**Yang TIDAK berubah:** BAST *Penetapan Status Penggunaan* — dokumen yang
AMAN cetak setelah SK terbit — tetap **bukan** berkas usulan. Ia berbeda dari
BAST **perolehan** yang pasal ini minta. Uji pertama untuk aturan itu sempat
mencampur keduanya; kini ia mencocokkan kedua frasa sekaligus, dengan
pembanding bahwa **SK** PSP justru wajib pada rezim lain.

### 5.2 Rezim Penggunaan lain — jauh lebih ringan

| Rezim | Lampiran wajib menurut pasal |
|---|---|
| **Penggunaan Sementara** | 2 — fotokopi SK PSP + fotokopi surat permintaan (Pasal 34 ayat (3)) |
| **Dioperasikan Pihak Lain** | 3 — fotokopi SK PSP + fotokopi surat permintaan pengoperasian + surat pernyataan bermeterai Pihak Lain (Pasal 24 ayat (3)–(4)) |
| **Alih Status Penggunaan** | 2 — fotokopi SK PSP + surat pernyataan kesediaan **menerima** dari calon Pengguna Barang **baru** (Pasal 54 ayat (3)) |
| **Penggunaan Bersama** | 2 dokumen pendukung (Pasal 46) |

**Titik yang sering tertukar:** pada alih status, surat pernyataan diteken
**penerima**, bukan pemohon. Pada **KSPI** ada **dua** surat pernyataan
berlawanan arah (Pasal 59 ayat (2)).

Menempelkan checklist PSP ke rezim-rezim ini adalah kekeliruan yang berulang
di banyak booklet praktik — daftarnya jauh lebih pendek.

### 5.3 Hibah — [F] PMK 111/2016 Pasal 93 & 95, dipadu layar SIMAN V2

> **Diverifikasi dari teks primer 2026-09-01**
> (`docs/regulasi/pmk-111-2016-pemindahtanganan.txt`, 104 halaman).

**Daftar SIMAN ternyata hampir seluruhnya bisa diturunkan dari pasalnya** —
konvergensi yang baru terlihat setelah naskahnya dibaca:

| Dokumen | SIMAN | Pasal |
|---|---|---|
| Surat Permohonan | Mandatory | Pasal 93 huruf c / Pasal 95 huruf c |
| Surat pernyataan kesediaan menerima hibah | Mandatory | Pasal 93 huruf c / Pasal 95 huruf c |
| Data Calon Penerima Hibah | Mandatory | Pasal 93 huruf a.1.c / Pasal 95 huruf a.1.b |
| Kartu Identitas Barang (KIB) | Mandatory | **Pasal 93 menyebutnya untuk tanah/bangunan; Pasal 95 TIDAK** |
| Dokumen Penganggaran | Opsional | Pasal 94 — wajib bila BMN diadakan untuk dihibahkan |
| SK Pembentukan Tim Internal | Opsional | Pasal 93/95 huruf a — **timnya** wajib, SK-nya opsional |

**Satu butir yang SIMAN pun tak sebut:** *berita acara penelitian* tim
internal (Pasal 93 huruf b, Pasal 95 huruf b). Ia tak ada di dropdown SIMAN
maupun di registry sebelumnya — ditemukan hanya karena pasalnya dibaca.

**KIB adalah pembeda yang membenarkan adanya tingkat `empiris_siman`.**
Pasal 95 — yang mengatur hibah **selain** tanah/bangunan, persis layar di
tangkapan pemilik — **tidak menyebut KIB sama sekali**, padahal di situlah
SIMAN menandainya Mandatory. Sistem meminta lebih dari pasalnya.
Menaikkannya jadi `terverifikasi` akan mengklaim dasar yang tak ada;
menurunkannya jadi anjuran akan membuat unggahan ditolak SIMAN. Ia
dipertahankan apa adanya, dan ada uji yang menjaga bahwa **hanya butir ini**
yang wajib tanpa dasar pasal.

### 5.3a Daftar asli SIMAN V2 (arsip)

Dropdown **"Jenis Dokumen"** pada dialog *Kelengkapan Dokumen* SIMAN V2 untuk
hibah selain tanah dan bangunan, lengkap dengan penanda milik SIMAN sendiri:

| Dokumen | SIMAN |
|---|---|
| Surat permintaan hibah / surat pernyataan bersedia menerima hibah BMN dari calon penerima hibah | **Mandatory** |
| Kartu Identitas Barang (KIB) | **Mandatory** |
| Surat Permohonan | **Mandatory** |
| Data Calon Penerima Hibah | **Mandatory** |
| Surat Pernyataan Tanggung Jawab (SPTJ) | Opsional |
| Dokumen Penganggaran yang menunjukkan bahwa BMN tersebut untuk dihibahkan | Opsional |
| SK Pembentukan Tim Internal | Opsional |
| Dokumen Lainnya | Opsional |

**Perhatikan kontrasnya:** KIB **Mandatory** di SIMAN untuk hibah, sementara
pasal PSP tak menyebut KIB sama sekali. Menyeragamkan keduanya akan salah di
salah satu sisi. Aplikasi ini sengaja membiarkan keduanya berbeda.

Nama dokumen dipakai **apa adanya**, termasuk yang panjang — operator harus
bisa mencocokkan satu lawan satu dengan dropdown SIMAN, dan nama yang
"diperbaiki" justru menghambat.

### 5.3b Pemusnahan — [F] PMK 83/2016 Pasal 11

| Dokumen | Sifat | Pasal |
|---|---|---|
| Surat permohonan | Wajib | ayat (1) |
| Surat Pernyataan Pengguna/Kuasa Pengguna Barang | Wajib | ayat (2) huruf a |
| Fotokopi dokumen kepemilikan | Wajib bila BMN-nya berdokumen | ayat (2) huruf b |
| Pengganti (kontrak/akta/pernyataan bermeterai) | Wajib bila dokumennya tak ada | ayat (3) |
| Kartu Identitas Barang | Wajib bila BMN-nya ber-KIB | ayat (2) huruf c |
| **Laporan kondisi barang** | **Wajib** | ayat (2) huruf d |
| **Foto terkini BMN** | **Wajib** | ayat (2) huruf e |

Dua yang terakhir **wajib** di sini, sedangkan pada rezim PSP hanya anjuran —
perbedaan yang hanya terlihat setelah kedua pasalnya dibaca.

### 5.3c Penghapusan — [F] PMK 83/2016 Pasal 38 & 40

**Sebabnya menentukan berkasnya**, dan keduanya sama sekali berbeda:

| Sebab | Dokumen |
|---|---|
| **Pemindahtanganan** (paling lazim) | Laporan Penghapusan + risalah lelang dan/atau BAST (penjualan lelang), perjanjian penjualan dan/atau BAST (tanpa lelang), BAST (tukar menukar/PMPP), naskah hibah dan/atau BAST (hibah) — **Pasal 38 ayat (3) huruf a–d** |
| **Putusan pengadilan** | Salinan putusan berkekuatan hukum tetap yang dilegalisasi + dokumen kepemilikan + KIB — **Pasal 40 ayat (2)** |

Pasal 38 ayat (3) **mengonfirmasi pemetaan `DOKUMEN_PELAKSANAAN` yang sudah
ada** di `backend/pemindahtanganan_utils.py` sejak sebelum pustaka ini ada.

### 5.3d Penjualan — [F] PMK 111/2016 Pasal 32 & 33

| Dokumen | Sifat | Pasal |
|---|---|---|
| Surat permohonan | Wajib | Pasal 32 huruf e / 33 huruf g |
| Surat pernyataan kebenaran objek | Wajib | Pasal 32 huruf e.3 (**materiil**) / 33 huruf g.4 (**formil dan materiil**, termasuk besaran nilai) |
| Berita acara penelitian | Wajib | Pasal 32 huruf a.2 jo. d / 33 huruf a.2 jo. f |
| Laporan Penilaian / nilai limit | Wajib **hanya untuk selain t/b** | Pasal 33 huruf c–e jo. g.3 |
| KIB | Wajib bila BMN-nya ber-KIB | Pasal 32 huruf a.1 |
| IMB/PBG | Wajib bila ada bangunan | Pasal 32 huruf a.1.b |
| SK PSP | Muatan (selain t/b) | Pasal 33 huruf a.1 |

**Pembeda yang mudah terlewat:** pada **tanah/bangunan**, Penilaian dimohonkan
**Pengelola** kepada Penilai (Pasal 32 huruf f angka 4) — jadi ia **bukan
lampiran pemohon**. Pada selain t/b, Pengguna Barang-lah yang menetapkan nilai
limitnya.

**Tim internal di sini OPSIONAL** — Pasal 32/33 huruf b berbunyi *"DAPAT
membentuk"*, sedangkan hibah (Pasal 93/95 huruf a) berbunyi *"membentuk"*.
Beda satu kata, beda kewajiban.

### 5.3e Tukar Menukar — [F] PMK 111/2016 Pasal 77

Selain surat permohonan, KIB, dan IMB, tukar menukar menagih tiga hal yang
**tak ada padanannya** di bentuk pemindahtanganan lain:

1. **Surat pernyataan tanggung jawab atas perlunya dilaksanakan Tukar
   Menukar** (huruf a angka 2)
2. **Peraturan daerah tata ruang wilayah / penataan kota** (huruf a angka 3) —
   hanya untuk tanah dan/atau bangunan
3. **Rincian kebutuhan barang pengganti** (huruf a angka 5) — pembeda pokok
   tukar menukar

### 5.3f PMPP — [F] PMK 111/2016 BAB VI

Permohonan disertai **kelengkapan data administratif**, **hasil kajian tim
internal**, **hasil Penilaian** BMN selain t/b yang telah ditetapkan Pengguna
Barang, dan **pernyataan kesediaan calon penerima** menerima PMPP yang berasal
dari BMN.

Pernyataan kesediaan itu sejajar dengan hibah — keduanya memindahkan
kepemilikan kepada pihak lain, jadi kesediaan penerimanya harus tertulis.

### 5.4 Sewa & Pinjam Pakai — pasalnya memang BUKAN di PMK 115/2020

Dua rezim ini **tetap** bertanda `belum_terverifikasi`, dan itu **bukan
karena teksnya belum dibaca**.

**PMK 115/2020 Pasal 96** berbunyi:

> *"Ketentuan lebih lanjut mengenai tata cara pelaksanaan Pemanfaatan BMN
> ditetapkan dengan Keputusan Menteri Keuangan yang ditandatangani oleh
> Direktur Jenderal atas nama Menteri Keuangan."*

Daftar dokumen permohonan sewa dan pinjam pakai **tidak ada di batang tubuh
PMK-nya** — ia didelegasikan ke KMK pelaksana. Nomor KMK itu belum berhasil
dipastikan dan **belum ada di manifes unduhan**.

Menaikkan keduanya berdasarkan PMK 115/2020 akan mengklaim dasar yang teksnya
sendiri menyatakan ada di tempat lain. Ada uji yang menahan godaan itu:
`test_sewa_dan_pinjam_pakai_TETAP_belum_terverifikasi`.

**Cara melengkapinya:** temukan nomor KMK pelaksana Pasal 96, tambahkan ke
`scripts/regulasi_sumber.py`, jalankan workflow. Atau — lebih cepat — potret
dropdown "Jenis Dokumen" SIMAN V2 pada layar permohonan sewa, yang langsung
menaikkannya ke `empiris_siman`.

**Sisa pekerjaan tercatat di kode, bukan hanya di dokumen ini:**
`test_hanya_sewa_dan_pinjam_pakai_yang_tersisa` akan gagal begitu daftarnya
berubah.

Sumber primer PMK 111/2016 jo. 165/2021 dan PMK 115/2020 terblokir. Yang
disediakan adalah **kerangka dasar** yang benar-benar berulang di semua rezim
usulan — surat permohonan, daftar BMN, dua surat keterangan kebenaran, KIB,
foto, laporan kondisi — seluruhnya `belum_terverifikasi`, sehingga layar
menampilkannya sebagai **anjuran dengan peringatan**, bukan gerbang.

Operator tetap mendapat daftar periksa yang berguna, tanpa aplikasi
berpura-pura tahu.

**Cara melengkapinya nanti:** minta **checklist resmi KPKNL Balikpapan**
(kantor yang diduga mewilayahi IKN) atau buka satu tiket di SIMAN V2 untuk
tiap jenis usulan dan potret dropdown "Jenis Dokumen"-nya — persis seperti
tangkapan layar hibah yang sudah masuk. Itu langsung menaikkan statusnya ke
`empiris_siman`.

## 6. Yang modul ini TIDAK lakukan

- Tidak memutuskan siapa berwenang menyetujui apa. Perutean ambang Rp100 juta
  tinggal di tempatnya sendiri.
- Tidak mencetak nomor pasal ke dokumen bermeterai.
- Tidak memblokir pengiriman. Daftar periksa memberi tahu, bukan menahan —
  butir `belum_terverifikasi` tak boleh menahan usulan atas dasar yang teksnya
  sendiri tak pernah minta.
