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

| Objek | Yang diminta pasal |
|---|---|
| **Tanah** | fotokopi **sertipikat** (huruf a) |
| **Bangunan** | fotokopi **IMB/PBG** + dokumen perolehan + dokumen lain termasuk BAST (huruf b) |
| **Tanah dan bangunan** | sertipikat + IMB/PBG + dokumen perolehan bangunan + dokumen lain (huruf c) |
| **Selain tanah/bangunan, punya dokumen kepemilikan** | fotokopi dokumen kepemilikan (BPKB/kapal/pesawat atau setara) (huruf d angka 1) |
| **Selain tanah/bangunan, tanpa dokumen kepemilikan** | fotokopi **BAST perolehan** sebagai penggantinya (huruf d angka 2) |
| **Untuk PMPP** | + dokumen penganggaran, hasil reviu APIP/BPK, dan BAST pengelolaan sementara bila fisiknya sudah tak dikuasai (huruf e) |
| **Semua fotokopi** | + **Surat Keterangan Kebenaran Fotokopi** (huruf g) |
| **Semua unggahan pindaian** | + **Surat Keterangan Kebenaran Arsip Digital** (Pasal 73 ayat (1) huruf a) |

Nama baku Surat Keterangan Kebenaran Arsip Digital **belum ditetapkan** PMK —
konfirmasikan judulnya ke KPKNL sebelum templatenya dibekukan.

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

### 5.3 Hibah — [E] terbaca dari layar SIMAN V2

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

### 5.4 Rezim yang pasalnya BELUM terbaca

Penjualan (lelang & tanpa lelang), tukar menukar, PMPP, penghapusan,
pemusnahan, sewa, pinjam pakai.

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
