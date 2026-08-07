# Penggunaan BMN dari Sisi Pemohon — Panduan Berkas, Surat, dan Ambang Kewenangan

> **Catatan metode — WAJIB DIBACA SEBELUM MEMAKAI DOKUMEN INI**
>
> - **Tanggal riset:** 8 Agustus 2026 (pengumpulan bahan 7–8 Agustus 2026).
> - **Metode:** pencarian web berulang + upaya pengambilan teks primer
>   (WebFetch/curl) ke JDIH Kemenkeu, JDIH BPK, DJKN, PPID DJKN, Halo DJKN,
>   SIPPN/SIPP MenPAN, dan mirror non-pemerintah, **ditambah pemeriksaan
>   skeptis (adversarial review) atas hasil riset itu sendiri**. Seluruh
>   koreksi pemeriksa sudah diterapkan pada dokumen ini.
> - **Hasil pengambilan teks primer: GAGAL TOTAL.** Setiap percobaan ditolak
>   di tingkat gateway egress (403 pada CONNECT / policy denial), bukan 403
>   dari situsnya. Tidak satu pun PDF/HTML peraturan, manual SIMAN, atau
>   artikel DJKN yang benar-benar terbuka. Yang tersedia hanya **cuplikan
>   (snippet) hasil mesin pencari** atas halaman-halaman tersebut.
> - **Konsekuensi:** **tidak ada satu pun klaim dalam dokumen ini yang
>   berstatus [F]** (terbaca dari teks resmi). Semua nomor pasal yang sempat
>   beredar dalam riset **sudah dikeluarkan** dari badan dokumen dan
>   dikumpulkan di §7.3 sebagai "daftar angka yang dilarang dikutip".
> - **Dokumen ini BUKAN pengganti pembacaan peraturan asli.** Ia adalah peta
>   kerja + daftar pertanyaan yang harus dijawab pemilik proyek dengan
>   membuka PDF resmi. Jangan mencetak nomor pasal, jangan mengunci ambang
>   nilai, dan jangan menyalakan validasi keras (hard block) di AMAN
>   berdasarkan dokumen ini saja.
> - Dokumen pendamping: `docs/PUSTAKA-REGULASI-BMN.md` (pustaka induk),
>   `docs/MASTERPLAN-SIKLUS-BMN.md` (peta siklus).

---

## Cara membaca penanda status

Instruksi awal meminta tiga label ([F]/[S]/[O]). Pemeriksa skeptis menemukan
bahwa tiga label saja **menggelembungkan kepercayaan**: label [S] dipakai
untuk klaim yang sumbernya bahkan bukan artikel yang pernah dibuka, melainkan
cuplikan mesin pencari atas halaman yang diblokir. Karena itu label dipakai
dengan sub-penanda:

| Penanda | Arti | Jumlah di dokumen ini |
|---|---|---|
| **[F]** | Terbaca dari teks resmi peraturan + nomor pasal terkonfirmasi | **0 (nol)** |
| **[S]** | Sumber sekunder. **Seluruh [S] di dokumen ini bertumpu pada cuplikan mesin pencari**, bukan halaman yang terbuka | mayoritas |
| **[S·1]** | Sama seperti [S], tetapi **hanya satu rantai sumber** (sering satu artikel yang disalin ulang situs lain) — jangan dianggap dua konfirmasi | banyak |
| **[S·lemah]** | Sumber berkualitas rendah: unggahan Scribd anonim, judul video YouTube, blog praktisi, repositori kampus | beberapa |
| **[X]** | **Nihil data** — dicari, tidak ditemukan. Bukan bukti ketiadaan norma | beberapa |
| **[O]** | Opini / rekomendasi penulis untuk AMAN. **Bukan aturan** | banyak |

**Kaidah yang dipakai sepanjang dokumen** (hasil koreksi pemeriksa):

1. Konsistensi antar sumber sekunder Indonesia **bukan** konfirmasi
   independen — artikel KPKNL dan blog satker lazim saling menyalin dari satu
   template lama, sehingga kesalahan yang sama tampak "konsisten".
2. Cuplikan mesin pencari yang isinya mirip dihitung **satu** sumber.
3. Nomor pasal yang tidak dibaca dari teks asli **lebih baik kosong daripada
   salah** — kolom pasal yang terisi akan dikutip orang lain sebagai fakta.
4. Dalam sistem kepatuhan, **false negative lebih berbahaya daripada false
   positive**: lebih baik menampilkan baris berlebih daripada menyembunyikan
   aset yang ternyata wajib diproses.

---

## Daftar isi

1. [Ringkasan eksekutif — empat rezim Penggunaan](#1-ringkasan-eksekutif--empat-rezim-penggunaan)
2. [Peta keputusan — aset saya jenis apa, rezim mana, siapa yang berwenang](#2-peta-keputusan--aset-saya-jenis-apa-rezim-mana-siapa-yang-berwenang)
3. [Bab per rezim](#3-bab-per-rezim)
   - 3.1 [Penetapan Status Penggunaan (PSP)](#31-penetapan-status-penggunaan-psp)
   - 3.2 [Penggunaan Sementara](#32-penggunaan-sementara)
   - 3.3 [Penggunaan BMN untuk Dioperasikan oleh Pihak Lain](#33-penggunaan-bmn-untuk-dioperasikan-oleh-pihak-lain)
   - 3.4 [Pengalihan (Alih) Status Penggunaan](#34-pengalihan-alih-status-penggunaan)
4. [BMN berbukti milik vs TANPA bukti milik](#4-bmn-berbukti-milik-vs-tanpa-bukti-milik)
5. [Unggahan berkas ke SIMAN V2](#5-unggahan-berkas-ke-siman-v2)
6. [\[O\] Rancangan untuk AMAN](#6-o-rancangan-untuk-aman)
7. [Yang BELUM terverifikasi dari teks primer](#7-yang-belum-terverifikasi-dari-teks-primer)

---

## 1. Ringkasan eksekutif — empat rezim Penggunaan

### 1.1 Lima peringatan yang harus dibaca lebih dulu

1. **Rezim induk kemungkinan besar sudah berganti.** PMK 246/PMK.06/2014
   (beserta PMK 87/PMK.06/2016 dan PMK 76/PMK.06/2019) **diduga kuat dicabut**
   dan diganti **PMK 40 Tahun 2024 tentang Tata Cara Penggunaan Barang Milik
   Negara**. [S] — seluruh bukti berupa cuplikan; klausul pencabutan tidak
   pernah terbaca. **Turunan penting:** identitas PMK 40/2024 sendiri (nomor,
   judul persis, tanggal penetapan yang beredar 21 Juni 2024) **belum
   terverifikasi primer**, dan penopangnya justru sumber lemah (Scribd,
   SlideShare, situs agregator). Bila premis ini salah, seluruh dokumen ini
   runtuh — karena itu ia menjadi butir verifikasi **nomor satu**.
2. **PMK 40/2024 sendiri belum tentu mutakhir per Agustus 2026.** Riset hanya
   membuktikan PMK 246/2014 usang; ia **tidak** membuktikan PMK 40/2024 masih
   berlaku utuh pada 2025–2026. Riset yang menemukan "pengganti" kerap
   berhenti satu lapis terlalu cepat. [O]
3. **Kekhususan IKN belum diperiksa dan itu celah terbesar.** Ada indikasi
   rezim khusus: **PMK 53 Tahun 2023** tentang Pengelolaan BMN dan **Aset
   Dalam Penguasaan (ADP)** di IKN, di atas **UU 3/2022 jo. UU 21/2023**, plus
   **PMK 139/PMK.08/2022** (khusus IKN, sudah tercatat di pustaka repo).
   Belum dipastikan: apakah Otorita IKN adalah Pengguna Barang biasa; apakah
   seluruh aset yang dikelola Otorita berstatus BMN atau sebagian ADP dengan
   rezim berbeda; dan apakah PMK 53/2023 menyimpangi atau merujuk balik ke
   PMK 40/2024 pada bab Penggunaan. [S]/[X]
4. **Tidak ada satu pun angka di dokumen ini yang layak di-hardcode.** Termasuk
   yang tampak paling mapan (tenggat 6 bulan, ambang Rp100 juta, daftar 9
   dokumen). Pemeriksa membatalkan kesimpulan riset awal yang menyebut dua
   butir terakhir "relatif aman dijadikan aturan keras". Semua → **peringatan
   lunak berlabel "perlu verifikasi"**.
5. **Jangan tertukar rezim.** Penggunaan (PMK 40/2024) ≠ Pemanfaatan
   (sewa/pinjam pakai/KSP/BGS-BSG/KSPI — PMK 115/PMK.06/2020, status
   keberlakuan belum dicek) ≠ Pemindahtanganan (PMK 111/PMK.06/2016 jo.
   165/2021) ≠ Penghapusan (PMK 83/PMK.06/2016). Pembeda cepat: **ada
   imbalan/sewa/kontribusi tetap → hampir pasti Pemanfaatan, bukan
   Penggunaan.** [O]

### 1.2 Tabel empat rezim

| # | Rezim | Pemohon (siapa bersurat) | Ditujukan kepada | Dokumen hasil | Jangka waktu |
|---|---|---|---|---|---|
| 1 | **PSP** (Penetapan Status Penggunaan) | Pengguna Barang (pimpinan K/L; untuk OIKN: Kepala Otorita atau pejabat terdelegasi). Satker/KPB mengusulkan **berjenjang ke dalam**, tidak langsung ke KPKNL [S] | Pengelola Barang (Menkeu c.q. DJKN — KPKNL / Kanwil DJKN / Kantor Pusat sesuai jenjang). Untuk BMN tertentu di bawah ambang: ditetapkan Pengguna Barang sendiri [S, ambang ragu] | **Keputusan (SK) PSP** [S] | Tenggat **pengajuan** diduga 6 bulan sejak BMN diperoleh — subjek & titik-mulai tenggat **belum pasti** (§3.1.6) [S·1] |
| 2 | **Penggunaan Sementara** | **Pengguna Barang pemilik PSP (pihak A)** — bukan peminjam. Dipicu **Surat Permintaan** dari pihak B [S] | Pengelola Barang. Untuk jangka pendek (≈≤6 bulan) diduga tanpa persetujuan Pengelola — **siapa yang menyetujui pada jalur ini masih bertentangan antar cuplikan** [S, ragu] | **Surat Persetujuan** Pengelola (jalur BMN pada Pengguna Barang) **atau Penetapan** Pengelola (jalur BMN pada Pengelola) → lalu **Perjanjian** + **BAST penyerahan** dan **BAST pengembalian** [S] | Paling lama **5 tahun** (tanah dan/atau bangunan) dan **2 tahun** (selain), **dapat diperpanjang**. Ambang **6 bulan** = batas bebas-persetujuan, **bukan** plafon jangka waktu (koreksi penting, §3.2) [S·1] |
| 3 | **Dioperasikan Pihak Lain** | Pengguna Barang. Dipicu **surat permintaan pengoperasian** dari calon Pihak Lain [S] | Pengelola Barang | **Keputusan Pengelola Barang** tentang penetapan status penggunaan untuk dioperasikan Pihak Lain → lalu **Perjanjian** Pengguna Barang–Pihak Lain; di akhir: **BAST pengembalian** [S] | Beredar: **5 tahun** dapat diperpanjang (BUMN/koperasi/"badan hukum lainnya"); **99 tahun** (Pemerintah Negara Lain) — **angka 99 ragu berat**; Organisasi Internasional mengikuti perjanjian antarnegara [S·1] |
| 4 | **Alih Status Penggunaan** | **Pengguna Barang LAMA**. Calon pengguna baru hanya menandatangani **surat pernyataan kesediaan menerima** bermeterai. Ada pula **jalur inisiatif Pengelola** tanpa permohonan [S] | Pengelola Barang | (1) **Surat Persetujuan** Pengelola; (2) **BAST** + daftar BMN + serah terima dokumen kepemilikan asli; (3) **SK Penghapusan** pengguna lama; (4) **dasar pencatatan pada pengguna baru** (SK PSP dari Pengelola **atau** keputusan internal — masih dua versi); (5) **Laporan penghapusan** [S, butir 4 ragu] | Rantai tenggat yang beredar: BAST ≤1 bulan sejak persetujuan; SK penghapusan ≤2 bulan sejak BAST; laporan ≤1 bulan sejak SK penghapusan [S·1, ragu] |

**Catatan pada tabel:**

- Kolom "dokumen hasil" adalah **inti pembeda rezim**: PSP dan Dioperasikan
  Pihak Lain menghasilkan **keputusan/penetapan**; Penggunaan Sementara dan
  Alih Status menghasilkan **persetujuan** yang harus **ditindaklanjuti**
  dokumen turunan. [S]
- **Penggunaan Bersama** juga disebut sebagai bagian ruang lingkup PMK
  40/2024 [S·1], tetapi **tidak dijadikan bab tersendiri** di sini karena
  bahan yang ada terlalu tipis. Istilah "Pengguna Barang Eminen" dan
  "Kolaborator" yang sempat muncul di riset **dicoret** — tidak lazim dalam
  peraturan pengelolaan BMN Indonesia, sumbernya rangkuman Scribd yang tidak
  pernah terbaca, dan berbau hasil parafrase/halusinasi. Jangan dipakai di
  teks bantuan AMAN. [O]

### 1.3 Perbedaan akibat pencatatan (yang paling sering salah dipahami)

| Rezim | Kepemilikan | Status penggunaan (PSP) | Pencatatan/neraca | Penanggung pemeliharaan |
|---|---|---|---|---|
| PSP | Pemerintah RI | ditetapkan pada Pengguna Barang | pada Pengguna Barang | Pengguna Barang |
| Penggunaan Sementara | tidak berubah | **tidak berubah** | **tetap pada pihak A** [S + simpulan logis, lihat catatan] | dibebankan pada **pihak B** (pengguna sementara) [S·1] |
| Dioperasikan Pihak Lain | tidak berubah | tetap pada Pengguna Barang | **tetap pada Pengguna Barang** | **Pihak Lain** [S·1] |
| Alih Status | tetap Pemerintah RI (yang berubah "c.q."-nya) | **berpindah** ke Pengguna Barang baru | **berpindah** (transfer keluar/masuk) | Pengguna Barang baru |

> **Peringatan status:** baris "pencatatan/neraca" dan "penyusutan tetap di
> pihak A" adalah **simpulan logis penulis**, bukan norma yang dikutip.
> Perlakuan penatausahaan/akuntansi diatur peraturan lain (penatausahaan BMN
> dan standar akuntansi pemerintahan), **bukan** oleh PMK Penggunaan. [O]

---

## 2. Peta keputusan — aset saya jenis apa, rezim mana, siapa yang berwenang

### 2.0 Langkah 0 — pertanyaan yang harus dijawab lebih dulu (khusus OIKN)

Sebelum memilih rezim, jawab tiga hal berikut. Ketiganya **belum terjawab**
oleh riset ini dan menentukan apakah seluruh peta di bawah berlaku:

| Pertanyaan | Status | Akibat bila terlewat |
|---|---|---|
| Objeknya **BMN** atau **ADP (Aset Dalam Penguasaan)** menurut PMK 53/2023? | [S] kategori ADP disebut ada: *tanah di wilayah IKN yang tidak terkait penyelenggaraan pemerintahan*; daftar sumber perolehannya belum terverifikasi | Salah rezim sejak awal; ADP diduga punya aturan penatausahaan sendiri |
| Siapa **Pengguna Barang** dan **Kuasa Pengguna Barang** di struktur OIKN, dan bagaimana pola pendelegasian tanda tangannya? | [X] belum diperiksa | Surat ditandatangani pejabat yang tidak berwenang → berkas dikembalikan / SK cacat kewenangan |
| Apakah **PMK 53/2023** menyimpangi PMK 40/2024 pada bab Penggunaan, atau merujuk balik? | [X] hubungan kedua PMK tidak berhasil dikonfirmasi | Memakai aturan umum padahal ada lex specialis |

**Hierarki aturan yang diusulkan untuk AMAN** (khusus → umum) [O]:
(1) PMK 53/2023 (BMN & ADP di IKN) → (2) PMK 40/2024 (Tata Cara Penggunaan
BMN) → (3) PP 27/2014 jo. PP 28/2020 → (4) UU 1/2004 (mis. kewajiban
sertipikasi tanah) + Peraturan Bersama sertipikasi → (5) PMK 118/2023 & juknis
SIMAN v2 (lapisan sistem). **Lapisan (1) belum diuji keberlakuannya pasca
UU 21/2023** — jangan dikunci sebelum diperiksa.

### 2.1 Pohon keputusan rezim

```
Aset sudah punya SK PSP?
├─ BELUM ──► REZIM 1: PSP (gerbang wajib; lihat §3.1)
│            └─ Kecuali objek diduga dikecualikan dari PSP (§3.1.7) →
│               JANGAN disembunyikan, beri penanda "diduga dikecualikan —
│               perlu konfirmasi" [O]
└─ SUDAH ──► Apa yang mau dilakukan?
             ├─ Dipakai sementara oleh K/L lain, PSP & pencatatan TIDAK pindah
             │   └─► REZIM 2: Penggunaan Sementara (§3.2)
             ├─ Dioperasikan badan/lembaga tertentu untuk PELAYANAN UMUM
             │   sesuai tusi K/L, tanpa sewa/kontribusi tetap
             │   └─► REZIM 3: Dioperasikan Pihak Lain (§3.3)
             ├─ Diserahkan permanen ke K/L lain, PSP & pencatatan PINDAH,
             │   tanpa kompensasi
             │   └─► REZIM 4: Alih Status (§3.4)
             └─ Ada imbalan / sewa / kontribusi tetap / mitranya swasta
                 atau Pemerintah Daerah
                 └─► BUKAN rezim Penggunaan. Arahkan ke PEMANFAATAN
                     (PMK 115/PMK.06/2020 — status keberlakuan belum dicek)
```

**Pembeda yang wajib dipasang sebagai pagar di UI** [O]:

| Lawan pihak | Rezim yang benar (dugaan) |
|---|---|
| Sesama **Pengguna Barang BMN** (K/L pusat) | Penggunaan Sementara / Alih Status |
| **Pemerintah Daerah** | **Pinjam Pakai** (Pemanfaatan) — bukan penggunaan sementara |
| **Badan usaha / pihak ketiga komersial** | Sewa / KSP / BGS-BSG / KSPI (Pemanfaatan) |
| **BUMN, koperasi, organisasi internasional, pemerintah negara lain, lembaga negara independen** untuk pelayanan umum | Dioperasikan Pihak Lain (Penggunaan) — **daftar kategorinya masih bertabrakan, lihat §3.3.4** |

> Koreksi pemeriksa yang diterapkan: rumusan riset awal "Pemanfaatan =
> kepada pihak **di luar** Pengguna Barang" **menyesatkan**, karena pinjam
> pakai justru dilakukan antar entitas pemerintah (lazimnya Pusat → Daerah).
> Pembedanya adalah **identitas lawan pihak**, bukan "di dalam/di luar".

### 2.2 Tiga kelompok objek dan perlakuannya

| Kelompok objek | Ke siapa PSP-nya | Dokumen kepemilikan kunci | Catatan |
|---|---|---|---|
| **Tanah** | Selalu ke **Pengelola Barang** [S] | Sertipikat (Hak Pakai atas nama Pemerintah RI c.q. K/L) | Bila belum bersertipikat → jalur substitusi §4 |
| **Tanah dan/atau bangunan** | Selalu ke **Pengelola Barang** [S]; tidak ada ambang yang membuat Pengguna Barang menetapkan sendiri | Sertipikat + **IMB/PBG** | Namai field **"IMB/PBG"** agar cocok dua rezim (pasca UU Cipta Kerja) [O] |
| **Selain tanah dan/atau bangunan** | **Bercabang** | | |
| ├─ punya dokumen kepemilikan (BPKB kapal/pesawat/kendaraan) | ke **Pengelola Barang** [S] | BPKB/STNK, bukti kepemilikan kapal/pesawat | Riset awal menulis "kendaraan **SELALU** ke Pengelola" — **dikoreksi**: kendaraan baru yang BPKB-nya belum terbit justru masuk kategori "tanpa dokumen kepemilikan". Penentu adalah **ada/tidaknya dokumen pada saat pengajuan**, bukan jenis barangnya [O] |
| └─ tidak punya dokumen kepemilikan | ≤ ambang → **Pengguna Barang menetapkan sendiri**; > ambang → **Pengelola Barang** [S, ambang ragu] | diganti BAST → SPTJ (§4) | Lihat §2.3 |

> **Alutsista** (yang dalam sumber disebut dapat ditetapkan Pengguna Barang
> tanpa batas nilai) **dikeluarkan dari spesifikasi modul AMAN**: OIKN tidak
> menguasai alutsista, dan mencantumkannya hanya melahirkan cabang logika
> mati yang tetap harus diuji dan dipelihara. Cukup dicatat sebagai konteks
> regulasi umum. [O]

### 2.3 Ambang nilai — PER UNIT atau AKUMULATIF? (titik paling rawan)

Ada **dua jenis ambang yang berbeda sama sekali** dan sering dicampur:

| Jenis ambang | Angka yang beredar | Satuan hitung yang beredar | Fungsinya | Status |
|---|---|---|---|---|
| **A. Ambang delegasi ke Pengguna Barang** | **Rp100.000.000,00** | **"per unit/satuan"** menurut satu tafsir; **"per usulan/permohonan"** menurut tafsir lain | Menentukan apakah PSP ditetapkan Pengguna Barang sendiri atau harus ke Pengelola | **[S, RAGU BERAT — dua tafsir bersaing]** |
| **B. Ambang jenjang kantor DJKN** (tanah dan/atau bangunan) | s.d. Rp10 M → KPKNL; >10–50 M → Kanwil DJKN; >50–100 M → Kantor Pusat DJKN; >100 M → Menkeu | **akumulatif "dalam satu paket pengajuan"** | Menentukan kantor tujuan surat | **[S·1, RAGU BERAT]** |
| **C. Ambang jenjang kantor DJKN** (selain tanah/bangunan tanpa bukti milik) | >Rp100 jt–5 M → KPKNL; >5–25 M → Kanwil DJKN; sisanya Kantor Pusat | akumulatif per paket pengajuan | idem | **[S·1, RAGU SANGAT BERAT — satu jalur sumber]** |

**Mengapa ini berbahaya.** Riset awal menyatakan **tegas** bahwa Rp100 juta
bersifat per unit dan "BUKAN akumulatif". Pemeriksa membatalkan ketegasan itu:
tidak ada satu pun **kutipan verbatim** yang memuat frasa "per unit" atau "per
satuan" dari teks aturan — hanya parafrase jurnal dan cuplikan. Bila
sebenarnya rumusannya **per usulan**, aplikasi akan meloloskan paket bernilai
miliaran ke jalur penetapan mandiri Pengguna Barang → **SK yang terbit cacat
kewenangan**.

**Aturan konservatif yang direkomendasikan sampai teks asli dibaca** [O]:

1. Hitung **keduanya**: `nilai_perolehan_per_nup` **dan**
   `total_nilai_paket`.
2. Bila **salah satu** melewati ambang → arahkan ke jalur **Pengelola
   Barang** (jalur paling konservatif).
3. Nilai yang **tepat berada di ambang** (persis Rp100.000.000,00) →
   **jangan dirutekan otomatis**; tandai "perlu penentuan manual". Rumusan
   operator perbandingan (`≤`, `<`, `≥`, `>`) belum diketahui, dan riset awal
   memakai tiga rumusan berbeda untuk angka yang sama dalam satu paragraf.
4. Simpan seluruh angka sebagai **parameter konfigurasi** (nilai + tanggal
   berlaku + dasar hukum + flag "belum diverifikasi"), bukan konstanta kode.
5. **Jangan** memakai angka jenjang B/C sebagai **hard block**; tampilkan
   sebagai saran kantor tujuan berlabel "perlu verifikasi".
6. **Pisahkan paket pengajuan** per kategori objek (tanah/bangunan vs selain)
   agar tidak salah alamat kantor. [O]

**Catatan tambahan dari pemeriksa:**

- Angka jenjang di atas berasal dari rumpun cuplikan era PMK 246/2014 dan
  dikaitkan ke **KMK 229/KM.6/2016**. Pelimpahan kewenangan di DJKN lazimnya
  diatur **KMK pelimpahan wewenang**, bukan PMK tata cara — menautkan angka
  ini ke "PMK 40/2024" berpotensi menunjuk instrumen yang salah. Prioritas:
  cari **KMK pelimpahan wewenang DJKN yang berlaku 2024–2026**.
- Tangga 10/50/100 M juga **bertabrakan** dengan tangga rezim lain yang sudah
  tercatat di `docs/PUSTAKA-REGULASI-BMN.md` (pemindahtanganan: ≤10 M
  Pengelola, >10–100 M Presiden, >100 M DPR) — tanda angka ini mengambang
  antar rezim.
- **PMK 4/PMK.06/2015** (pendelegasian kewenangan Pengelola→Pengguna) dipakai
  banyak sumber sebagai dasar ambang Rp100 juta dan dasar penandatanganan SK
  PSP mandiri. **Status keberlakuannya pasca PMK 40/2024 dan pasca PP 28/2020
  tidak diketahui.** Aturan yang keberlakuannya tidak diketahui **tidak boleh
  menjadi dasar rancangan**. Tambahan temuan silang: pustaka repo mencatat
  PMK 4/2015 dengan **kualifikasi yang identik kata per kata** tetapi untuk
  kewenangan **penjualan/hibah** (rezim Pemindahtanganan) — jadi entah angka
  itu berpindah lintas rezim, atau PMK tersebut mendelegasikan keduanya.
  Harus dibaca butir demi butir. [S/X]

### 2.4 Kantor tujuan untuk OIKN

- Wilayah Penajam Paser Utara/IKN berada di bawah **KPKNL Balikpapan**
  (Kanwil DJKN Kalimantan Timur dan Utara) — **[S, perlu verifikasi wilayah
  kerja]**.
- **"KPKNL Penajam" tidak ada** — nama itu muncul di riset awal dan
  **dicoret** oleh pemeriksa. Jangan pernah menulis nama kantor yang belum
  dipastikan ada pada dokumen operasional; operator akan mengirim berkas ke
  alamat yang tidak ada. [O]
- **Standar Pelayanan (SLA) harus diambil dari KPKNL Balikpapan sendiri**,
  bukan dari KPKNL Pekanbaru/Bengkulu/Bontang/Purwakarta/Pekalongan yang
  angkanya dikutip riset. [O]

---

## 3. Bab per rezim

Format tiap bab: dasar hukum → pemohon & tujuan surat → daftar surat →
daftar lampiran → syarat administratif & substantif → data yang harus
disiapkan → alur & tenggat → dokumen hasil.

### 3.1 Penetapan Status Penggunaan (PSP)

#### 3.1.1 Dasar hukum

| Aturan | Peran | Status |
|---|---|---|
| **PMK 40 Tahun 2024** tentang Tata Cara Penggunaan BMN | Aturan inti yang diduga berlaku | [S] — teks asli tidak terbaca; nomor pasal **tidak dicantumkan** (lihat §7.3) |
| PP 27/2014 jo. PP 28/2020 | Payung; PMK 40/2024 disebut sebagai pelaksanaannya | [S] — nomor pasal delegasi **dihapus** (hipotesis bersaing: Pasal 25 vs Pasal 26) |
| PMK 246/PMK.06/2014 jo. 87/2016 jo. 76/2019 | **Diduga dicabut** | [S] — hanya relevan sebagai rujukan historis, karena banyak template surat & checklist KPKNL yang beredar masih menyebut "Lampiran I B / II B PMK 246" |
| PMK 4/PMK.06/2015 | Diduga dasar delegasi PSP mandiri ≤Rp100 juta | [S] — **status keberlakuan tidak diketahui**, jangan dijadikan dasar |
| PMK 53 Tahun 2023 (BMN & ADP di IKN) | Lex specialis IKN | [S] — hubungan dengan PMK 40/2024 belum dikonfirmasi |
| KMK 229/KM.6/2016 | Diduga sumber jenjang KPKNL/Kanwil/Pusat | [S·1] — kemungkinan besar sudah diperbarui |
| KMK 601/KM.1/2020 | Dikutip standar pelayanan sebagai dasar SLA 5 hari kerja | [S·1] — **janji layanan, bukan norma PMK** |
| PMK 118 Tahun 2023 (SIMAN) | Kanal elektronik | [S] — **waspadai tabrakan nomor** dengan PMK 118/PMK.06/2017 yang sudah dirujuk di `frontend/src/pages/PenilaianPage.jsx` |

**Ketentuan Peralihan PMK 40/2024 sama sekali belum diperiksa** [X]. PMK
pengganti hampir selalu memuat pasal peralihan (permohonan yang sudah
diajukan sebelum PMK baru tetap diproses dengan aturan lama). Untuk AMAN yang
akan punya tiket berjalan, ini lubang operasional nyata.

#### 3.1.2 Pemohon & tujuan surat

- **Pemohon resmi ke Pengelola Barang = Pengguna Barang** (Menteri/Pimpinan
  Lembaga; untuk OIKN: **Kepala Otorita IKN**), atau pejabat yang menerima
  pendelegasian. [S]
- Alur internal K/L berjenjang: **Kuasa Pengguna Barang (Kepala Satker) →
  Pengguna Barang → Pengelola Barang**. Satker **tidak** bersurat langsung ke
  KPKNL. [S]
- Praktik K/L pada umumnya: kewenangan didelegasikan ke pejabat eselon I yang
  membidangi pengelolaan BMN (Sekjen/Sekretaris Utama), yang dapat menunjuk
  pejabat lain. **Untuk OIKN, pola ini TIDAK boleh diasumsikan** — Pengguna
  Barang secara rezim adalah pimpinan K/L, dan pendelegasian harus dicek pada
  Peraturan/Keputusan Kepala Otorita. [O]
- Karena itu **"peraturan/dasar pendelegasian" masuk daftar lampiran** — surat
  tanpa dasar delegasi berisiko dikembalikan. [S]

#### 3.1.3 Daftar surat (dengan kerangka isi usulan) [O untuk kerangka, [S] untuk keberadaan surat]

| # | Surat | Dari → kepada | Kerangka isi usulan |
|---|---|---|---|
| 1 | **Surat Permohonan PSP internal** | KPB/Kepala Satker → Pengguna Barang | Kepala surat; nomor/tanggal/sifat/lampiran/hal; dasar (tanggal perolehan, dokumen perolehan); maksud permohonan; rekap jumlah NUP & nilai; daftar lampiran; tanda tangan KPB |
| 2 | **Surat Permohonan PSP ke Pengelola** | Pengguna Barang / pejabat terdelegasi → **Kepala KPKNL** (atau Kanwil/Pusat sesuai jenjang) | Idem + **dasar pendelegasian kewenangan**; uraian objek per kelompok (tanah / tanah-bangunan / selain); pernyataan bahwa BMN digunakan untuk tusi; permintaan penerbitan SK PSP; tembusan (lazimnya Kanwil DJKN dan/atau eselon I) |
| 3 | **Lampiran Daftar BMN** (varian TB & varian STB) | melekat pada surat 2 | Lihat §3.1.6 |
| 4 | **Surat Pernyataan Tanggung Jawab** (bermeterai) | pejabat struktural berwenang | Identitas pejabat (nama, NIP, jabatan struktural, satker); pernyataan bahwa BMN **benar dikuasai dan digunakan untuk penyelenggaraan tugas dan fungsi**; pernyataan dibuat dalam rangka permohonan PSP; meterai + tanda tangan |
| 5 | **Surat Keterangan Kebenaran Fotokopi Dokumen** | pejabat struktural berwenang | Daftar dokumen yang difotokopi (nomor & tanggal); pernyataan sesuai aslinya; tanda tangan |
| 6 | **Surat pernyataan pengganti** untuk dokumen yang tidak tersedia | pejabat struktural berwenang | Lihat §4 |
| 7 | **Rekap KIB** | operator | Per jenis KIB |
| 8 | **Cetak Laporan Kondisi Barang** | dari aplikasi pencatatan (SIMAK-BMN/SAKTI) | — |
| 9 | **Lembar checklist kelengkapan** | operator | Mengikuti checklist resmi KPKNL wilayah |

> **Nomor surat, tanggal, pejabat penanda tangan, dan tembusan harus menjadi
> field terstruktur, bukan teks bebas.** [O]
>
> **Jangan mencetak rujukan "Lampiran II B PMK 246/2014"** pada template
> AMAN: PMK itu diduga sudah dicabut, dan **padanan lampirannya di PMK
> 40/2024 belum diketahui** [X].

#### 3.1.4 Daftar lampiran — checklist KONDISIONAL (bukan 9 wajib)

Riset awal mengusulkan "9 slot unggah **wajib**" sebagai gate sebelum tombol
kirim aktif. **Pemeriksa membatalkan usulan itu** karena bertentangan dengan
temuan lain di riset yang sama:

- Item **"fotokopi dokumen kepemilikan"** mustahil wajib untuk BMN yang
  justru **didefinisikan** sebagai "tidak mempunyai dokumen kepemilikan" —
  itulah seluruh dasar ambang Rp100 juta.
- Item **KIB** dikecualikan sendiri ("kecuali BMN yang tidak diwajibkan
  dibuatkan KIB").
- Sumber daftar 9 butir adalah **dokumen Scribd anonim** — unggahan pengguna,
  bukan sumber yang layak menjadi gate wajib di aplikasi pemerintah.
  **[S·lemah]**

Karena itu daftar berikut disusun **bercabang**:

| # | Lampiran | Sifat | Pemicu / kondisi |
|---|---|---|---|
| 1 | Surat permohonan (asli) | **Wajib inti** | selalu |
| 2 | Daftar/rincian BMN | **Wajib inti** | selalu |
| 3 | Surat Pernyataan Tanggung Jawab (bermeterai) | **Wajib inti** | selalu |
| 4 | Fotokopi dokumen kepemilikan | Wajib-bersyarat | hanya bila objek **punya** dokumen kepemilikan |
| 5 | Surat Keterangan Kebenaran Fotokopi | Wajib-bersyarat | bila ada lampiran berupa fotokopi |
| 6 | KIB | Wajib-bersyarat | untuk jenis BMN yang diwajibkan ber-KIB (tanah; gedung & bangunan; alat angkutan bermotor; alat besar — daftar 6 jenis KIB resmi ada di pustaka repo). **Harus ditandatangani Kepala Satker** [S] |
| 7 | Foto BMN | Wajib-bersyarat/dianjurkan | dianjurkan selalu — Pengelola dapat melakukan **pengecekan lapangan** [S] |
| 8 | Dasar pendelegasian kewenangan penandatangan | Wajib-bersyarat | bila surat tidak ditandatangani Pengguna Barang sendiri |
| 9 | Laporan kondisi barang dari SIMAK-BMN/SAKTI | Wajib-bersyarat | bila tersedia dari aplikasi pencatatan |
| 10 | Surat pernyataan pengganti (bila dokumen tidak ada) | Kondisional | lihat §4 |
| 11 | Surat laporan kehilangan dari Kepolisian | Kondisional | bila BPKB/STNK **hilang** [S·lemah — satu blog praktisi] |

**Dokumen kepemilikan per jenis objek** [S]:

| Objek | Dokumen |
|---|---|
| Tanah | Fotokopi **sertipikat** (Hak Pakai/Hak Pengelolaan atas nama Pemerintah RI c.q. K/L). Bila belum bersertipikat: dokumen perolehan lain (AJB, girik, Letter C, BAST, ledger/legger jalan) — **lihat peringatan girik di §4.5** |
| Bangunan | Fotokopi **IMB** atau **PBG** (istilah pasca UU Cipta Kerja) + dokumen perolehan + dokumen lain (mis. BAST perolehan) |
| Selain tanah/bangunan yang punya bukti milik | BPKB (kendaraan), bukti kepemilikan kapal, bukti kepemilikan pesawat udara, atau setara; ditambah STNK dan/atau BAST perolehan |

#### 3.1.5 Syarat administratif & substantif

**Administratif** [S]:

- Surat permohonan **asli** (bertanda tangan basah atau TTE) — beberapa
  standar pelayanan menghitung SLA sejak **surat asli** diterima.
- Seluruh fotokopi disertai surat keterangan kebenaran dari **pejabat
  struktural** yang berwenang (bukan bendahara, bukan operator SIMAN, bukan
  pejabat fungsional).
- Meterai cukup pada surat pernyataan.
- Data pada lampiran **identik** dengan data di aplikasi pencatatan (kode
  barang, NUP, nilai, tanggal perolehan) — selisih menghambat persetujuan.

**Substantif** [S]:

- BMN benar **dikuasai dan digunakan untuk penyelenggaraan tugas dan fungsi**
  K/L pemohon.
- Pengelola Barang berwenang meneliti: meminta keterangan/data tambahan,
  meminta konfirmasi/klarifikasi ke instansi terkait, dan melakukan
  **pengecekan lapangan**. Penetapan didasarkan pada hasil penelitian itu.

**Akibat hukum bila belum PSP** [S, atribusi diperbaiki]: PSP adalah gerbang
bagi tahapan hilir. Rezim hilir **masing-masing punya PMK sendiri** dan tidak
boleh diatribusikan ke PMK Penggunaan:

| Tahapan hilir | Rezim/aturannya (bukan PMK 40/2024) |
|---|---|
| Perencanaan kebutuhan/RKBMN & pemeliharaan | rezim perencanaan kebutuhan BMN |
| Penggunaan sementara, dioperasikan pihak lain, penggunaan bersama, alih status | **PMK 40/2024** (rezim Penggunaan) |
| Pemanfaatan (sewa, pinjam pakai, KSP, BGS/BSG, KSPI) | PMK 115/PMK.06/2020 |
| Pemindahtanganan (penjualan, tukar-menukar, hibah, PMPP) | PMK 111/PMK.06/2016 jo. 165/2021 |
| Penghapusan & pemusnahan | PMK 83/PMK.06/2016 |

> Klaim "BMN belum PSP adalah temuan berulang BPK yang memengaruhi **opini**
> laporan keuangan" **diturunkan menjadi [O]/dihapus sebagai justifikasi**:
> tidak ada satu pun LHP BPK yang dikutip, dan opini ditentukan materialitas,
> bukan keberadaan satu jenis temuan.

#### 3.1.6 Data yang harus disiapkan

**Kolom minimum Daftar BMN (umum)** [S untuk daftar kolom, [O] untuk format]:

| Field | Format usulan |
|---|---|
| No urut | integer |
| **Kode Barang** | **10 digit** (Golongan·Bidang·Kelompok·Sub·Sub-sub) |
| **NUP** | integer |
| Nama/Uraian Barang | teks |
| Merk/Tipe atau Nomor Identitas | teks (rangka/mesin/nopol untuk kendaraan) |
| Tahun Perolehan | YYYY |
| Tanggal perolehan | YYYY-MM-DD |
| **Nilai Perolehan** | rupiah, bilangan bulat (tanpa desimal), pemisah ribuan pada cetakan |
| Nilai Buku | rupiah, bilangan bulat |
| Kondisi | enum B / RR / RB |
| Keterangan | teks |

**Varian kolom per jenis objek** [S]:

- **Tanah dan/atau bangunan**: Kode Barang, NUP, Jenis BMN, **Lokasi/alamat**,
  **Luas** (m², 2 desimal), Tahun Perolehan, Nilai Perolehan, Dokumen
  Kepemilikan (nomor & tanggal).
- **Selain tanah/bangunan**: kolom Lokasi dan Luas **diganti** Merk/Tipe dan
  **Kuantitas** (+ satuan).

Set kolom yang sama disebut dimuat kembali dalam SK PSP yang terbit — sehingga
data lampiran harus identik dengan data aplikasi pencatatan. [S]

**Field permohonan (level tiket)** [O]:
`kode_satker`, `nama_satker`, `jenis_objek` (TANAH | TANAH_DAN_BANGUNAN |
BANGUNAN | SELAIN_TB), `punya_dokumen_kepemilikan` (bool),
`nilai_perolehan_per_nup`, `total_nilai_paket`, `tanggal_perolehan_yuridis`,
`tanggal_bast_perolehan` (**dipisah** — lihat catatan tenggat),
`jalur_penetapan` (PENGELOLA | PENGGUNA_SENDIRI | PERLU_PENENTUAN_MANUAL),
`instansi_tujuan`, `nomor_surat_permohonan`, `tanggal_surat`,
`pejabat_penanda_tangan` + `dasar_pendelegasian`, slot dokumen (kondisional),
`nomor_sk_psp`, `tanggal_sk_psp`, `tanggal_lapor_ke_pengelola`.

#### 3.1.7 Alur & tenggat

**Alur** [S]:

1. Satker menyusun berkas → usul berjenjang ke Pengguna Barang.
2. Pengguna Barang meneliti → meneruskan ke Pengelola Barang, **atau**
   menetapkan sendiri bila masuk kewenangan delegasi.
3. Di KPKNL: surat diterima Kepala KPKNL → disposisi ke Kepala Seksi
   Pengelolaan Kekayaan Negara → pelaksana meneliti kelengkapan.
4. Berkas **lengkap** → penerbitan SK PSP. Berkas **tidak lengkap** →
   dikembalikan untuk dilengkapi.
5. SK PSP disampaikan ke satker → **direkam kembali** pada aplikasi SIMAN.

**Tenggat**:

| Tenggat | Angka yang beredar | Status & catatan |
|---|---|---|
| Pengajuan permohonan PSP | **paling lama 6 bulan sejak BMN diperoleh** | [S·1]. **Tiga keraguan yang harus diselesaikan:** (a) **subjeknya** — tenggat untuk *mengajukan permohonan* (di bawah kendali satker) atau untuk *terbitnya SK* (di luar kendali satker)? (b) **titik mulai** — "sejak BMN diperoleh" = tanggal BAST, tanggal dokumen perolehan yuridis, atau tanggal pencatatan? Untuk hibah/rampasan/tukar-menukar, tanggal yuridis bisa berbeda dari BAST fisik. (c) apakah berlaku **seragam untuk semua jenis objek** atau khusus tanah/bangunan. Angka "6 bulan" juga muncul di **tiga rezim berbeda** (PSP; penggunaan sementara bebas-persetujuan; permohonan lelang penjualan), sehingga cuplikan mudah tertukar |
| Penerbitan SK PSP di KPKNL | **5 hari kerja** sejak surat asli diterima **dan** berkas dinyatakan lengkap | [S·1]. **Hanya untuk BMN berupa TANAH DAN/ATAU BANGUNAN**, dan berasal dari **Standar Pelayanan/janji layanan**, **bukan norma PMK**. Jangan disandingkan setara dengan tenggat normatif; jangan dipakai sebagai dasar alarm keterlambatan yang menuduh KPKNL |
| Pelaporan SK PSP mandiri ke Pengelola | **paling lama 1 bulan** sejak ditetapkan | [S·1] — cek silang minimal satu sumber independen sebelum dijadikan tugas turunan otomatis |
| Biaya layanan | **Rp0** | [S] |

**Rekomendasi implementasi tenggat** [O]: jangan hardcode satu basis hitung.
Sediakan `tanggal_perolehan_yuridis` terpisah dari `tanggal_bast`, tampilkan
hitung mundur sebagai **estimasi berlabel "indikatif"**, dan **jangan**
menyalakan penanda "TERLAMBAT" sebelum subjek & titik mulai tenggat
dikonfirmasi dari teks asli.

**Objek yang diduga dikecualikan dari PSP** [S, padanan di PMK 40/2024 belum
terkonfirmasi]: barang persediaan; Konstruksi Dalam Pengerjaan (KDP); barang
yang sejak awal direncanakan untuk dihibahkan; barang dari dana dekonsentrasi
& dana penunjang tugas pembantuan yang direncanakan diserahkan; BPYBDS; Aset
Tetap Renovasi (ATR).

> **Koreksi arah risiko:** riset awal menyarankan daftar ini dipakai sebagai
> **filter** agar daftar "BMN belum PSP" tidak menampilkan false positive.
> **Jangan.** Menyembunyikan aset menukar false positive murah (operator
> melihat baris berlebih) dengan false negative mahal (aset yang wajib di-PSP
> hilang dari radar, lewat tenggat, jadi temuan). **Rancangan yang benar:**
> tetap tampilkan, beri penanda *"diduga dikecualikan — perlu konfirmasi"*,
> sediakan tombol **dismiss manual yang tercatat siapa yang men-dismiss dan
> kapan**. [O]

#### 3.1.8 Dokumen hasil

- **Keputusan (SK) PSP** — memuat set kolom BMN yang sama dengan lampiran
  permohonan. [S]
- Penerbit: Kepala KPKNL / Kepala Kanwil DJKN / pejabat Kantor Pusat DJKN
  sesuai jenjang **atau** Keputusan Pengguna Barang (jalur delegasi). [S,
  jenjang ragu]
- **Jalur PSP tanpa didahului permohonan**: Pengelola Barang dapat menetapkan
  status penggunaan tanpa usulan Pengguna Barang, antara lain untuk
  melengkapi bukti kepemilikan atas BMN yang menjadi objek sengketa di
  pengadilan, sengketa pertanahan di BPN, atau penetapan BMN dari perolehan
  lain yang sah. **[S·1 — dan cuplikan yang sama sempat dipakai untuk tiga
  norma berbeda, jadi perlakukan sebagai indikasi kasar]**

---

### 3.2 Penggunaan Sementara

#### 3.2.1 Dasar hukum

- **PMK 40 Tahun 2024**, bab Penggunaan Sementara. [S] — **seluruh nomor
  pasal dihapus** (riset sempat memetakan Pasal 32–40, tetapi pemetaannya
  tidak konsisten: satu nomor dipakai untuk dua materi berbeda, dan pola
  "Pasal X/Y" menandakan nomor ditebak dari kedekatan).
- **PP 27/2014 jo. PP 28/2020**, bagian Penggunaan. [S] — nomor pasal
  **dihapus** (hipotesis bersaing Pasal 26 vs 27).
- PP 28/2020 disebut **menambahkan Pengelola Barang** sebagai subjek yang
  BMN-nya dapat digunakan sementara — inilah dasar adanya jalur "penetapan"
  (bukan "persetujuan"). [S·1 — halaman sumber tidak pernah terbaca].

#### 3.2.2 Pemohon & tujuan surat

- **Prasyarat mutlak:** BMN **sudah ber-PSP**. Rumusan yang beredar: *"BMN yang
  telah ditetapkan status Penggunaannya pada Pengguna Barang dapat digunakan
  sementara oleh Pengguna Barang lainnya tanpa harus mengubah kepemilikan dan
  status Penggunaan BMN."* [S]
- **Pemohon resmi ke Pengelola Barang = Pengguna Barang PEMILIK PSP (pihak
  A)** — **bukan** pihak peminjam. [S]
- Pemicunya **Surat Permintaan** dari **pihak B** (calon pengguna sementara)
  kepada pihak A. [S]
- **Dua jalur berbeda** [S]:
  - BMN berada pada **Pengguna Barang** → **persetujuan** Pengelola Barang
    (produk: surat persetujuan);
  - BMN berada pada **Pengelola Barang** (mis. BMN idle yang telah
    diserahkan) → **penetapan** Pengelola Barang, dalam rangka optimalisasi
    atau tindak lanjut penyelesaian BMN yang tercatat pada dua/lebih K/L.

#### 3.2.3 Daftar surat

| # | Surat | Dari → kepada | Kerangka isi |
|---|---|---|---|
| 1 | **Surat Permintaan Penggunaan Sementara** | Pengguna Barang **B** → Pengguna Barang **A** | Identitas pemohon; objek BMN yang diminta (uraian + lokasi + bagian yang diminta); jangka waktu yang diminta; alasan/urgensi; pernyataan kesediaan menanggung pemeliharaan |
| 2 | **Surat Permohonan Penggunaan Sementara** | Pengguna Barang **A** → **Pengelola Barang** | **Isi minimal 4 blok** [S]: (a) **data BMN**; (b) **informasi Pengguna Barang yang akan menggunakan sementara** (K/L, satker, alamat, pejabat); (c) **jangka waktu** (tanggal mulai–berakhir); (d) **penjelasan serta pertimbangan** |
| 3 | **Perjanjian Penggunaan Sementara** | A ↔ B | Lihat §3.2.7 |
| 4 | **BAST penyerahan** dan **BAST pengembalian** | A ↔ B | Daftar BMN; kondisi saat serah terima; dokumentasi foto |
| 5 | **Surat laporan berakhirnya penggunaan** | A → Pengelola | Melampirkan fotokopi BAST — **dasar pasalnya belum terkonfirmasi**, lihat §3.2.8 |
| 6 | **Pemberitahuan tertulis ke Pengelola** pada jalur pendek | A → Pengelola | **Bersyarat & belum terkonfirmasi** — lihat peringatan §3.2.5 |

#### 3.2.4 Daftar lampiran

**Menurut cuplikan teks PMK — hanya 2 dokumen** (jauh lebih ringan daripada
PSP) [S]:

1. **Fotokopi Keputusan PSP** atas BMN bersangkutan;
2. **Fotokopi Surat Permintaan** penggunaan sementara dari pihak B.

**Menurut praktik lapangan (booklet/checklist KPKNL)** — lebih luas
[S·lemah, flipbook tidak pernah terbaca; **sebagian checklist itu kemungkinan
milik rezim PSP, bukan penggunaan sementara**]: surat permohonan; daftar
rincian BMN; identitas calon pengguna sementara; penjelasan & pertimbangan;
fotokopi surat permintaan; fotokopi SK PSP; **KIB** untuk
tanah/bangunan/kendaraan.

> Rekomendasi: siapkan berkas versi luas meski PMK hanya mewajibkan dua,
> karena kekurangan lampiran memicu surat permintaan kelengkapan — **tetapi
> tandai mana yang wajib menurut aturan dan mana yang anjuran praktik.** [O]

#### 3.2.5 Ambang 6 bulan — konflik rumusan yang belum selesai

| Sumber | Rumusan | Akibat pada kasus "tepat 6 bulan" |
|---|---|---|
| Cuplikan PP 27/2014 | *"kurang dari 6 bulan"* (<6) | tepat 6 bulan → **butuh** persetujuan |
| Cuplikan PMK 40/2024 | *"paling lama 6 bulan"* (≤6) | tepat 6 bulan → **tidak butuh** persetujuan |

**Dan siapa yang menyetujui pada jalur pendek pun bertentangan** [S, dua
cuplikan saling bertolak belakang]: satu menyebut **Pengguna Barang** yang
memberi persetujuan (kewenangan turun, tanpa ke DJKN); satu lagi menyebut
**Pengelola Barang**.

**Koreksi penting dari pemeriksa — jangan menghapus kewajiban pemberitahuan.**
Riset awal merancang jalur pendek sebagai "memotong langkah 4–6" (tanpa
keterlibatan Pengelola sama sekali) dan menulis "jangan diasumsikan ada
pemberitahuan". Itu **membalik beban risiko**: rumusan yang dikenal untuk
penggunaan sementara di bawah 6 bulan adalah **tanpa persetujuan Pengelola
TETAPI dengan kewajiban memberitahukan** kepada Pengelola Barang. Bila benar
ada dan AMAN menghapusnya, aplikasi akan **menuntun satker melanggar**.

**Rancangan yang benar** [O]:

- Cantumkan langkah **"pemberitahuan tertulis ke Pengelola Barang"** sebagai
  **langkah bersyarat berlabel "perlu verifikasi"**, bukan dihilangkan.
- **Jangan hardcode 179 hari.** "6 bulan" dihitung secara **kalender**, bukan
  180/179 hari (Feb–Agu vs Jul–Jan berbeda panjang). Simpan sebagai parameter
  (`ambang_bulan = 6`, `mode_penghitungan = kalender`).
- Kasus **tepat 6 bulan** → tampilkan banner "ambang belum diverifikasi,
  konsultasikan ke KPKNL", jangan dirutekan otomatis ke salah satu jalur.

#### 3.2.6 Jangka waktu

| Objek | Jangka waktu maksimal | Status |
|---|---|---|
| Tanah dan/atau bangunan | **5 tahun**, dapat diperpanjang | [S·1 — satu rantai sumber; angka 5 tahun juga muncul di rezim pinjam pakai/sewa sehingga rawan tertukar] |
| Selain tanah dan/atau bangunan | **2 tahun**, dapat diperpanjang | [S·1] |
| Permohonan **perpanjangan** | paling lambat **1 bulan sebelum** berakhir; ketentuan permohonan/penelitian/persetujuan berlaku **mutatis mutandis** (berkas sama dengan permohonan awal) | [S·1] |
| Jumlah maksimal perpanjangan & panjang tiap perpanjangan | **[X] tidak ada sumber sama sekali** | — |

> **KOREKSI PENTING LINTAS-RISET.** Riset rezim Alih Status sempat menulis
> bahwa penggunaan sementara sebagai jembatan sebelum alih status berjangka
> **"sampai dengan 6 bulan"**. **Itu keliru** — mengacaukan **ambang
> persetujuan** dengan **plafon jangka waktu**. Bila dikodekan, timer AMAN
> akan memaksa berakhirnya perjanjian yang sah berjalan bertahun-tahun.
> Yang benar (dugaan): **5 tahun / 2 tahun, dapat diperpanjang**; **6 bulan =
> ambang bebas-persetujuan**.

#### 3.2.7 Perjanjian & biaya

- **Perjanjian Penggunaan Sementara** dibuat antara pihak A dan pihak B,
  ditandatangani **paling lama 3 bulan** sejak surat persetujuan terbit.
  **[S·1 — satu cuplikan; jangan dijadikan deadline otomatis yang memicu
  status "terlambat", cukup pengingat lunak]**
- **Isi minimal perjanjian** [S]: hak dan kewajiban para pihak, termasuk
  kewajiban **pengamanan dan pemeliharaan** BMN; kewajiban pihak B
  **menyerahkan kembali** BMN saat penggunaan sementara berakhir. Materi
  pembahasan DJKN/Biro BMN menambahkan bahwa perjanjian ini menjadi **dasar
  penganggaran** pengamanan/pemeliharaan oleh pihak B. [S·1]
- **Biaya pengamanan & pemeliharaan dibebankan kepada K/L yang menggunakan
  sementara (pihak B).** [S]
  **Frasa "kecuali ditentukan lain dalam perjanjian" DIHAPUS** — tidak
  didukung kutipan mana pun dan tampak ditambahkan sendiri oleh riset awal.
  Bila norma aslinya imperatif, membuka opsi override di aplikasi bisa
  melahirkan perjanjian yang bertentangan dengan PMK. **Default AMAN:
  pembebanan ke pihak B, tanpa opsi override.** [O]
- **Tidak ada sewa/kompensasi** — penggunaan sementara bukan Pemanfaatan.
  Konsekuensi "tidak menimbulkan PNBP sewa" adalah **simpulan logis penulis
  [O]**, bukan norma yang dikutip.

#### 3.2.8 Alur & tenggat

**Alur 8 langkah** [O — sintesis, bukan kutipan]:

1. Pastikan **SK PSP** terbit (validasi keras yang aman: tanpa SK PSP,
   pengajuan diblokir).
2. Terima **Surat Permintaan** dari K/L peminjam.
3. Susun **Surat Permohonan** + Daftar BMN + lampiran.
4. Ajukan ke Pengelola Barang (unggah lewat SIMAN V2, modul Pengelolaan).
5. Layani **penelitian/klarifikasi** Pengelola (Pengelola dapat meminta
   keterangan ke pemohon **dan/atau** konfirmasi-klarifikasi ke calon
   pengguna sementara) [S].
6. Terima **Surat Persetujuan** — atau **surat penolakan disertai alasan**
   [S]. Simpan kedua kemungkinan keluaran.
7. Tandatangani **Perjanjian** (≈≤3 bulan sejak persetujuan) lalu **BAST
   penyerahan**.
8. Saat berakhir: **cek fisik** → **BAST pengembalian** → **laporan ke
   Pengelola**.

> Jalur ≤6 bulan **mungkin** memotong langkah 4–6 **tetapi tetap menyisakan
> kewajiban pemberitahuan** — lihat §3.2.5.

**Isi minimal Surat Persetujuan (6 butir)** [S·lemah — bersumber booklet
SIMAN v2 yang tidak pernah terbaca]: (a) data BMN yang disetujui; (b)
Pengguna Barang yang akan menggunakan sementara; (c) kewajiban pihak
pengguna sementara; (d) jangka waktu; (e) pembebanan biaya pemeliharaan;
(f) kewajiban menindaklanjuti dengan **perjanjian**.

**Tenggat pelaporan pasca-berakhir**: **paling lama 1 bulan** sejak BAST
ditandatangani, melampirkan fotokopi BAST. **[O + RAGU]** — cuplikan yang
terbaca secara eksplisit berbicara tentang rezim *"Penggunaan BMN untuk
dioperasikan Pihak Lain"*, lalu dianalogikan ke penggunaan sementara. Itu
persis **pencampuran rezim** yang harus dihindari. Tampilkan sebagai
"pengingat praktik, dasar pasal belum terkonfirmasi", **bukan** validasi
keras.

**BAST**: ada **dua** dalam satu siklus — penyerahan (awal) dan pengembalian
(akhir). Pengguna Barang menandatangani BAST pengembalian **setelah lebih
dahulu melakukan pengecekan** atas kondisi BMN. [S] → AMAN sebaiknya
mewajibkan unggah foto kondisi + checklist cek fisik sebelum BAST
pengembalian difinalkan. [O]

#### 3.2.9 Khusus tanah/bangunan

- Jangka waktu 5 tahun (bukan 2 tahun); KIB Tanah/Bangunan lazim diminta.
- Penggunaan sementara **dapat atas sebagian objek** → Daftar BMN harus
  menyebut **luas bagian yang dipinjamkan**, bukan sekadar NUP. [S·1 — contoh
  praktik yang dikutip berasal dari berita yang tidak pernah terbaca; **angka
  nominal rupiah pada contoh itu dibuang** karena tidak punya nilai normatif]
- Tidak ada pemecahan/pengubahan sertipikat karena kepemilikan dan PSP tidak
  berubah. [O — simpulan logis]

#### 3.2.10 Konteks masa transisi (relevan untuk perpindahan ke IKN)

**Fakta [S·1]:** ada berita kegiatan kanwil sebuah kementerian yang memakai
skema penggunaan sementara berjangka sampai dengan 6 bulan terhadap BMN yang
**akan dialihstatuskan**, sambil menunggu proses audited BPK pada masa
transisi organisasi, didahului perjanjian penggunaan sementara.

**Rekomendasi [O]:** pola ini *mungkin* cocok sebagai jembatan legal atas
penguasaan fisik sementara berkas alih status disiapkan. **Jangan dijadikan
preset alur di AMAN tanpa konfirmasi KPKNL wilayah IKN** — sumbernya paparan
internal satu K/L (bukan norma), dan KPKNL setempat bisa berpendapat lain.

---

### 3.3 Penggunaan BMN untuk Dioperasikan oleh Pihak Lain

#### 3.3.1 Dasar hukum

- **PP 27/2014 jo. PP 28/2020**, bab Penggunaan. Bunyi yang dikutip dua
  cuplikan: *"Barang Milik Negara/Daerah dapat ditetapkan status penggunaannya
  untuk penyelenggaraan tugas dan fungsi Kementerian/Lembaga/satuan kerja
  perangkat daerah, guna dioperasikan oleh Pihak Lain dalam rangka menjalankan
  pelayanan umum sesuai tugas dan fungsi Kementerian/Lembaga/satuan kerja
  perangkat daerah yang bersangkutan."* [S·1]
- **Koreksi premis riset yang dipertahankan:** rezim ini **bukan** Pasal 27
  PP 27/2014 — pasal itu berada di bab **Pemanfaatan**. Riset menduga kuat
  pasal yang benar adalah **Pasal 18**. **Namun nomor itu tetap tidak
  dicantumkan sebagai dasar** karena (a) teks PP tidak pernah terbaca, dan
  (b) kutipan verbatim di atas diambil dari artikel lama **tanpa memeriksa
  apakah PP 28/2020 mengubah pasal tersebut** — mengutip "PP 27/2014 jo. PP
  28/2020" sambil menyalin bunyi versi pra-2020 adalah kesalahan tersendiri.
  **Yang boleh ditulis:** *"bab Penggunaan PP 27/2014 jo. PP 28/2020"*.
  **Yang dilarang:** mencetak "Pasal 27" sebagai dasar rezim ini.
- **PMK 40 Tahun 2024**, bab Penetapan Status Penggunaan BMN untuk
  Dioperasikan oleh Pihak Lain. [S] — **seluruh nomor pasal dihapus**; riset
  sempat menyusun daftar "Pasal 11/15/21–23/24/25/26" yang **tumpang tindih
  secara semantik** (21–23 diklaim mencakup "permohonan/penelitian", lalu 24
  mengulang "permohonan" dan 25 mengulang "penelitian") — ciri khas nomor
  yang dikarang lalu diberi label fungsi berurutan.
- Aturan pendamping yang **nomor dan keberlakuannya belum diverifikasi**, dan
  karena itu **tidak boleh masuk bagian "Mengingat" surat**: PMK Pemanfaatan
  (klaim 115/PMK.06/2020), Penatausahaan (klaim 181/PMK.06/2016), Wasdal
  (klaim 207/PMK.06/2021), Asuransi BMN (klaim 97/PMK.06/2019), juknis SIMAN
  v2 (klaim KMK 248 Tahun 2024). [S·lemah/X]

#### 3.3.2 Pemohon & tujuan surat

- **Pemohon: Pengguna Barang → Pengelola Barang.** Satker/KPB mengusulkan
  berjenjang (KPB → UAPPB-W/E1 → Pengguna Barang), lalu Pengguna Barang yang
  bersurat ke Pengelola. [S]
- **Prasyarat mutlak: sudah ber-PSP.** Tiket rezim ini wajib divalidasi
  terhadap adanya SK PSP aktif untuk NUP terkait. [S]
- **Pemicu:** **surat permintaan pengoperasian** dari calon Pihak Lain kepada
  Pengguna Barang; fotokopinya wajib dilampirkan. [S]

#### 3.3.3 Syarat substantif — dan pembedanya dari Pemanfaatan

| Ciri | Dioperasikan Pihak Lain (Penggunaan) | Pemanfaatan |
|---|---|---|
| Rezim | tetap Penggunaan; BMN tetap dipakai untuk tusi K/L | rezim tersendiri |
| Imbalan | **tanpa sewa, tanpa kontribusi tetap, tanpa pembagian keuntungan** [S] | ada sewa/kontribusi/pembagian keuntungan |
| Tujuan | **pelayanan umum** sesuai tusi K/L dan/atau pelaksanaan urusan pemerintahan | optimalisasi/pendapatan |
| Mitra | badan/lembaga tertentu yang dibatasi peraturan | badan usaha/pihak ketiga/Pemda |
| Dokumen hasil | **Keputusan Pengelola Barang** | persetujuan pemanfaatan + perjanjian sewa/KSP dll. |

> **Kontradiksi yang belum selesai — jangan dijadikan dasar desain PNBP.**
> Riset menyajikan tiga klaim yang **tidak koheren satu sama lain**: (a)
> rezim ini "tanpa sewa/kontribusi/pembagian keuntungan"; (b) bila Pihak Lain
> memperoleh **keuntungan**, keuntungan itu **disetor seluruhnya** ke Rekening
> Kas Umum Negara sebagai PNBP; (c) muatan keputusan memuat kewajiban
> "menyetorkan penerimaan/**kompensasi**". Kata "kompensasi" adalah kosakata
> **Pemanfaatan**. Secara ekonomi, gabungan "menanggung seluruh biaya
> pemeliharaan + menyetor 100% keuntungan" juga sulit dipercaya. Ini pola
> khas ringkasan yang menggabungkan potongan aturan dari rezim berbeda.
> **Yang harus dipastikan dari teks asli:** apakah yang disetor adalah
> *seluruh keuntungan*, *hasil pungutan*, atau justru pungutan itu memerlukan
> dasar tarif PNBP tersendiri — tiga hal dengan konsekuensi sangat berbeda.
> [S, RAGU BERAT]

#### 3.3.4 Daftar "Pihak Lain" — enum yang masih bertabrakan

Daftar yang beredar [S]: (a) **BUMN** — "termasuk anak perusahaan BUMN yang
diperlakukan sama dengan BUMN"; (b) **Koperasi**; (c) **Pemerintah Negara
Lain**; (d) **Organisasi Internasional**; (e) **Lembaga Negara Independen**
yang bukan Pengguna Anggaran/Pengguna Barang; (f) **Organisasi/Lembaga yang
dibentuk dengan atau berdasarkan undang-undang** yang bukan Pengguna
Anggaran/Pengguna Barang.

**Tiga masalah yang membatalkan implementasi enum ini sekarang:**

1. **Tabel jangka waktu tidak cocok dengan daftar.** Jangka 5 tahun disebut
   untuk "BUMN, Koperasi, atau **badan hukum lainnya**" — kategori yang
   **tidak ada** dalam enam butir di atas; sebaliknya "Lembaga Negara
   Independen" dan "Organisasi bentukan UU" **tidak kebagian** jangka waktu.
   Pemetaannya bolong dan bertabrakan.
2. **"Badan hukum lainnya" berpotensi mencakup swasta**, langsung menabrak
   klaim tegas "perusahaan swasta murni TIDAK termasuk".
3. **Anak perusahaan BUMN** adalah klaim hukum kontroversial yang disajikan
   sebagai fakta datar. Berdasarkan UU BUMN, anak perusahaan BUMN pada
   umumnya **bukan** BUMN, dan kedudukannya lama diperdebatkan.

**Rekomendasi** [O]: **jangan bangun enum maupun validasi jangka waktu**
sebelum daftar pihak lain dan tabel jangka waktu dibaca dari **satu pasal
yang sama**. Bila terpaksa dibuat lebih dulu, pecah "BUMN" dan "Anak
perusahaan BUMN" menjadi dua nilai terpisah, dengan yang kedua berstatus
**ragu — wajib telaah hukum/konfirmasi KPKNL per kasus, tidak auto-approve**.

#### 3.3.5 Daftar surat

| # | Surat | Dari → kepada |
|---|---|---|
| 1 | **Surat permintaan pengoperasian** | calon Pihak Lain → Pengguna Barang |
| 2 | **Surat permohonan penetapan status penggunaan untuk dioperasikan Pihak Lain** | Pengguna Barang → Pengelola Barang |
| 3 | **Keputusan Pengelola Barang** (atau surat penolakan) | Pengelola → Pengguna Barang |
| 4 | **Perjanjian pengoperasian** | Pengguna Barang ↔ Pihak Lain |
| 5 | **BAST pengembalian** | Pihak Lain ↔ Pengguna Barang |
| 6 | **Laporan berakhirnya penggunaan** | Pengguna Barang → Pengelola |

#### 3.3.6 Daftar lampiran

Yang paling konsisten muncul [S]:

1. Fotokopi **Keputusan PSP** atas objek yang dimohonkan;
2. Fotokopi **surat permintaan pengoperasian** dari Pihak Lain;
3. **Surat pernyataan bermeterai cukup dari Pihak Lain** yang akan
   mengoperasikan BMN;
4. **Perhitungan estimasi biaya operasional dan besaran pungutan** —
   **kondisional**, bila Pihak Lain akan memungut dari masyarakat;
5. **Data/rincian BMN** yang akan dioperasikan;
6. **Surat keterangan kebenaran fotokopi** dari pejabat struktural berwenang.

Pendukung yang lazim: daftar rincian/KIB, foto BMN, laporan kondisi barang.

> Riset juga menempelkan "checklist 9 butir" milik rezim **PSP** ke rezim ini.
> Itu **checklist praktik**, bukan norma, dan sumbernya Scribd anonim
> [S·lemah] — pakai sebagai anjuran, bukan gate. [O]

#### 3.3.7 Data yang harus disiapkan

Selain kolom Daftar BMN umum (§3.1.6), tambahkan [O]:

| Field | Format |
|---|---|
| `jenis_pihak_lain` | enum (lihat peringatan §3.3.4) |
| `nama_pihak_lain`, `dasar_pendirian` | teks |
| `nomor_surat_permintaan`, `tanggal_surat_permintaan` | teks / YYYY-MM-DD |
| `ada_pungutan_ke_masyarakat` | bool → memicu slot lampiran 4 |
| `estimasi_biaya_operasional`, `besaran_pungutan` | rupiah |
| `jangka_waktu_mulai`, `jangka_waktu_berakhir` | YYYY-MM-DD |
| `penanggung_asuransi` | enum/teks — lihat §3.3.10 |
| `ada_bangunan_milik_pihak_lain_di_atas_bmn` | bool (khusus tanah) |

#### 3.3.8 Alur & tenggat

**Alur 9 langkah** [O — sintesis; riset awal melabelinya [S] padahal sumbernya
sendiri menulis "sintesis"]:

1. Pihak Lain mengirim surat permintaan → 2. satker menyiapkan berkas &
usul berjenjang → 3. Pengguna Barang mengajukan permohonan tertulis ke
Pengelola (via SIMAN V2) → 4. **penelitian** Pengelola atas kelengkapan &
kesesuaian, dapat disertai peninjauan lapangan → 5. **Keputusan** Pengelola
(atau penolakan) → 6. **Perjanjian** Pengguna Barang–Pihak Lain → 7. serah
terima pengoperasian & pencatatan → 8. selama berjalan: pemeliharaan &
pengamanan oleh Pihak Lain, **wasdal** oleh Pengguna Barang → 9. berakhir →
**BAST pengembalian** → laporan ke Pengelola.

| Tenggat | Angka beredar | Status |
|---|---|---|
| Permohonan **perpanjangan** | paling lambat **3 bulan sebelum** berakhir (alarm T-90) | [S·1] — bersandar satu artikel yang tidak pernah dibuka |
| **Pelaporan berakhirnya** penggunaan | paling lama **1 bulan** sejak BAST pengembalian, melampirkan fotokopi BAST (alarm T+30) | [S·1] |
| Jangka waktu | 5 tahun (BUMN/koperasi/"badan hukum lainnya"), dapat diperpanjang; **99 tahun** (Pemerintah Negara Lain, atas BMN fasilitas pelayanan umum, pertimbangan hubungan antarnegara); Organisasi Internasional mengikuti perjanjian antarnegara | [S·1]. **99 tahun = angka paling mencurigakan di seluruh riset** — tidak berpadanan dengan tenor mana pun dalam rezim BMN yang dikenal (Sewa 5/10 th, Pinjam Pakai 5 th, KSP 30/50 th, BGS-BSG 30 th, KSPI 50 th) dan lebih berbau konsep sewa tanah/HGB. **Dilarang masuk formulir/validasi sebelum dibaca dari PDF** |

#### 3.3.9 Ketentuan khusus & larangan

- **Biaya pemeliharaan dibebankan kepada Pihak Lain**, dituangkan dalam
  perjanjian; tidak membebani APBN/DIPA satker. [S·1] → konsekuensi: usulan
  RKBMN pemeliharaan untuk NUP tersebut sebaiknya **ditandai**, bukan otomatis
  dinolkan (lihat §6). [O]
- **Larangan bagi Pihak Lain:** mengalihkan pengoperasian ke pihak lainnya,
  memindahtangankan, menjaminkan/menggadaikan BMN. [S·1]
- **Pembatasan objek untuk mitra asing:** pengoperasian oleh Organisasi
  Internasional dan Pemerintah Negara Lain hanya atas BMN berupa **tanah
  dan/atau bangunan**, untuk melaksanakan kesepakatan dalam perjanjian antara
  Pemerintah RI dan pihak tersebut. [S·1]
- **Tanah — Pihak Lain mendirikan bangunan.** Beredar klaim bahwa dalam hal
  objeknya tanah, Pihak Lain **dapat mendirikan bangunan** yang berstatus
  miliknya selama jangka waktu berjalan; dan lebih jauh, bahwa **pemanfaatan
  atas bangunan milik Pihak Lain itu tidak memerlukan persetujuan Pengelola
  Barang karena objeknya bukan BMN**.

  > **PERINGATAN — KLAIM PALING BERISIKO HUKUM DI SELURUH DOKUMEN INI.**
  > Sumbernya cuplikan atas **PMK 246/2014 yang diduga sudah dicabut**.
  > Logikanya rapuh: memanfaatkan bangunan di atas tanah BMN tetap merupakan
  > pemanfaatan tanah BMN — dan justru itulah yang diatur rezim **BGS/BSG**.
  > Menampilkan "tidak perlu persetujuan" di UI berpotensi mendorong
  > pemanfaatan komersial tanah negara tanpa izin dan menjadi temuan BPK.
  > **DILARANG ditampilkan di UI AMAN.** Bila benar-benar dibutuhkan, minta
  > **konfirmasi tertulis KPKNL**, bukan mengandalkan teks aturan yang sudah
  > dicabut. [S·1 → dinaikkan ke status "berisiko tinggi, jangan dipakai"]

#### 3.3.10 Dokumen hasil & kewajiban turunan

- **Keputusan Pengelola Barang.** Muatan minimal yang beredar [S·1]: (a) data
  BMN; (b) jangka waktu; (c) informasi Pihak Lain; (d) kewajiban Pihak Lain
  memelihara & mengamankan BMN serta menyetorkan penerimaan/kompensasi
  (**istilah "kompensasi" diragukan**, §3.3.3).
- **Perjanjian pengoperasian** — klausul yang harus ada [S/O]: objek &
  rincian BMN; jangka waktu; hak & kewajiban; kewajiban
  pemeliharaan/pengamanan dan penanggung biayanya; larangan
  pengalihan/pemindahtanganan; perlakuan atas penerimaan/pungutan; dan
  **klausul pihak yang wajib mengasuransikan BMN**.
- **Asuransi** [S·lemah]: untuk BMN berstatus "dioperasikan Pihak Lain"
  dan/atau "penggunaan sementara", perjanjian disebut wajib menyebut pihak/K-L
  yang berkewajiban mengasuransikan; pihak itulah yang mengajukan Rencana
  Asuransi BMN di SIMAN V2. Nomor PMK asuransinya (klaim 97/PMK.06/2019)
  **belum diverifikasi**.
- **Wasdal** [S·1]: Pengguna/Kuasa Pengguna Barang tetap wajib memantau,
  menertibkan, dan menyusun **laporan wasdal semesteran & tahunan**. Nomor
  PMK wasdal (klaim 207/PMK.06/2021) **belum diverifikasi**.
- **Ambang nilai kewenangan** untuk rezim ini: **[X] tidak ditemukan.**
  Pemeriksa menilai ini **kemungkinan besar kegagalan pencarian, bukan
  ketiadaan norma** — rezim Penggunaan dikenal punya pendelegasian berbasis
  nilai. Tulis sebagai *"belum ditemukan — diduga ADA, prioritas verifikasi
  tinggi"*, jangan sebagai temuan bahwa tidak ada.

---

### 3.4 Pengalihan (Alih) Status Penggunaan

#### 3.4.1 Dasar hukum

- **PMK 40 Tahun 2024**, bab Pengalihan Status Penggunaan BMN. [S] — nomor
  bab/pasal **dihapus** (riset menyebut "Bab VII, Pasal 10/53/54/55", dengan
  Pasal 55 diakui sendiri sebagai "perkiraan posisi" alias hasil ekstrapolasi
  "54+1"; dan pola "ayat (1) pemohon / ayat (2) isi surat / ayat (3) lampiran"
  adalah pola baku yang justru akan dihasilkan pencocokan pola, bukan
  pembacaan).
- **PMK 83/PMK.06/2016** (Pemusnahan & Penghapusan) — disebut sebagai dasar
  bahwa penghapusan karena alih status **dikecualikan** dari kewajiban
  persetujuan penghapusan, sekaligus sumber tenggat 2 bulan & 1 bulan.
  **[S·1 — satu pasal yang sama dipakai memikul dua norma berbeda; sumbernya
  halaman sarpras sebuah universitas dan tulisan hukum perwakilan BPK yang
  kemungkinan menyalin ringkasan yang sama. Nomor pasal dihapus.]**
- **PMK 90 Tahun 2024** (penggunaan anggaran & aset pada masa transisi K/L)
  — menempatkan alih status sebagai salah satu opsi pemenuhan kebutuhan BMN
  K/L hasil perubahan nomenklatur/pemisahan/penggabungan/pembentukan baru.
  **Relevansinya untuk OIKN masih spekulatif** — OIKN dibentuk oleh UU IKN,
  bukan oleh perubahan nomenklatur; pastikan dulu OIKN memang subjek PMK ini.
  [S·1]
- **Sirkularitas yang harus disadari:** banyak butir di bab ini dibenarkan
  dengan alasan "konsisten dengan rumusan PMK 246/2014 yang beredar" — yaitu
  aturan yang **dinyatakan dicabut oleh PMK 40/2024 itu sendiri**. Pada
  titik-titik yang justru **diubah** PMK baru, metode ini dijamin salah.
  Setiap butir warisan diberi penanda **[warisan PMK 246/2014]**.

#### 3.4.2 Pemohon & prinsip dasar

- **Pemohon = PENGGUNA BARANG LAMA.** Calon Pengguna Barang baru **tidak**
  mengajukan permohonan; perannya menandatangani **surat pernyataan kesediaan
  menerima** bermeterai yang dilampirkan pada permohonan pengguna lama. [S]
  → **Bila OIKN adalah pihak PENERIMA, yang disiapkan operator adalah surat
  pernyataan kesediaan, bukan surat permohonan.**
- **Jalur kedua — inisiatif Pengelola Barang**: alih status dapat berjalan
  **tanpa permohonan**, atas dasar kajian Pengelola, dengan lebih dahulu
  **memberitahukan secara tertulis** kepada pengguna lama dan calon pengguna
  baru; calon pengguna baru menjawab dengan pernyataan kesediaan. [S]
  → AMAN perlu **dua jenis berkas**: inisiatif Pengguna dan inisiatif
  Pengelola.
- **Prinsip:** dilakukan **antar Pengguna Barang**, **berdasarkan persetujuan
  Pengelola Barang**, **tanpa kompensasi**, dan **tidak diikuti pengadaan BMN
  pengganti**. Setelahnya BMN ditatausahakan dan dipelihara Pengguna Barang
  baru. [S]

> **Koreksi instrumen — kata "perjanjian" dihapus dari alur alih status.**
> Riset PSP sempat menulis bahwa alih status "dituangkan dalam perjanjian
> antar-Pengguna Barang dan diikuti BAST". Instrumen **perjanjian** adalah
> ciri khas **Penggunaan Sementara** dan **Penggunaan Bersama**. Alih status
> lazimnya berjalan lewat **persetujuan Pengelola + BAST + penetapan/
> pencatatan pada Pengguna Barang baru**. Menyalin pola perjanjian ke modul
> alih status akan menghasilkan **template surat yang salah instrumen**. [O]

> **Alih status ≠ hibah.** Perpindahan BMN antar K/L adalah alih status
> (tanpa kompensasi, kepemilikan tetap Pemerintah RI), **bukan** hibah
> (rezim Pemindahtanganan). Ini kesalahan klasik operator dan layak dipasang
> sebagai peringatan validasi di AMAN. [O]

#### 3.4.3 Daftar surat

| # | Surat | Dari → kepada | Kerangka isi usulan |
|---|---|---|---|
| 1 | **Surat Permohonan Pengalihan Status Penggunaan** | Pengguna Barang **lama** → Pengelola Barang | (a) **data BMN** — jenis, nilai perolehan, lokasi, luas, tahun perolehan; (b) **identitas calon Pengguna Barang baru**; (c) **penjelasan & pertimbangan** (BMN tidak digunakan lagi / tidak ada rencana penggunaan / optimalisasi / dukungan tusi K/L penerima) [S] |
| 2 | **Surat Pernyataan Kesediaan Menerima** (bermeterai cukup) | calon Pengguna Barang **baru** → dilampirkan pada surat 1 | Identitas penandatangan tingkat Pengguna Barang; pernyataan kesediaan menerima pengalihan; rujukan daftar BMN |
| 3 | **Surat Pemberitahuan** (jalur inisiatif Pengelola) | Pengelola → kedua Pengguna Barang | — |
| 4 | **Berita Acara Serah Terima (BAST)** + lampiran daftar BMN | pengguna lama ↔ pengguna baru | Termasuk **serah terima dokumen kepemilikan asli** |
| 5 | **Berita Acara Serah Terima Dokumen** (terpisah/lampiran khusus) | idem | Daftar nomor sertipikat, NIB, luas, letak, jumlah lembar — **[O]**, tetapi inilah yang paling sering jadi temuan audit bila hilang |
| 6 | **SK Penghapusan BMN** | Pengguna Barang lama | Dasar: BAST |
| 7 | **Laporan Penghapusan** (lampiran: SK penghapusan + BAST) | pengguna lama → Pengelola, **tembusan** pengguna baru | — |
| 8 | **Dasar pencatatan pada pengguna baru** | Pengelola **atau** Pengguna Barang baru | **Dua versi bersaing, lihat §3.4.7** |

#### 3.4.4 Daftar lampiran

**Versi minimal menurut peraturan (2 butir)** [S]:
(1) fotokopi **SK PSP** atas BMN yang akan dialihkan; (2) **surat pernyataan
bermeterai cukup** dari calon Pengguna Barang baru berisi kesediaan menerima.

**Versi praktik KPKNL (±11 butir)** [S·lemah — dokumen Scribd tanpa identitas
penerbit dan tahun; **kekuatan bukti paling lemah di seluruh dokumen ini**;
jadikan daftar anjuran, **bukan** validasi wajib unggahan]:
surat permohonan; daftar rincian BMN; fotokopi SK PSP; surat pernyataan
kesediaan menerima (bermeterai); fotokopi dokumen kepemilikan; KIB; foto
BMN; surat pernyataan tanggung jawab atas kebenaran data; surat pernyataan
kebenaran fotokopi; laporan kondisi barang; peraturan/SK pendelegasian
kewenangan penandatangan.

> **Wajib:** minta **checklist resmi KPKNL Balikpapan** (kantor yang diduga
> mewilayahi IKN) dan pakai itu sebagai sumber kebenaran daftar lampiran. [O]

#### 3.4.5 Penandatangan

- Surat permohonan: **Pengguna Barang** (untuk OIKN: Kepala Otorita) atau
  pejabat yang dikuasakan. Satker/KPB **tidak** berwenang bersurat ke
  Pengelola. [S]
- Surat pernyataan kesediaan menerima: pejabat tingkat **Pengguna Barang** di
  K/L penerima (atau yang dikuasakan) — **bukan kepala satker**. [S]
- Surat persetujuan: Kepala KPKNL / Kepala Kanwil DJKN / pejabat DJKN sesuai
  kewenangan. [S]

#### 3.4.6 Data yang harus disiapkan

Kolom **Daftar BMN yang Dialihkan** (dipakai ulang untuk lampiran surat,
lampiran BAST, dan lampiran SK penghapusan — satu tabel yang sama agar
konsisten) [O]:

| Field | Format |
|---|---|
| No | integer |
| Kode Barang | 10 digit |
| NUP | integer |
| Uraian/Nama Barang | teks |
| Merk/Tipe atau Nomor Identitas | teks (rangka/mesin/nopol) |
| Lokasi & Alamat lengkap | teks |
| Luas | m², 2 desimal (tanah/bangunan) |
| Tahun Perolehan | YYYY |
| Nilai Perolehan | rupiah bulat |
| Akumulasi Penyusutan | rupiah bulat |
| Nilai Buku | rupiah bulat |
| Kondisi | B / RR / RB |
| Nomor & Tanggal Dokumen Kepemilikan | teks + YYYY-MM-DD |
| Nomor & Tanggal SK PSP | teks + YYYY-MM-DD |
| Keterangan | teks |

Total nilai perolehan per paket dijumlahkan — **hanya sebagai informasi
pendukung penentuan kantor tujuan**, bukan sebagai perutean otomatis (§2.3).

#### 3.4.7 Alur, tenggat, dan dokumen hasil

**Alur** [S]: permohonan → **penelitian Pengelola** (kelengkapan & kesesuaian
dokumen; dapat meminta keterangan tambahan, konfirmasi/klarifikasi ke calon
pengguna baru, dan **pengecekan lapangan**) → **disetujui** (surat
persetujuan) **atau ditolak** (pemberitahuan tertulis + alasan) → tindak
lanjut.

**Rantai tenggat yang beredar** [S·1 — satu rumpun cuplikan; **perlakukan
sebagai pengingat lunak, jangan memblokir input tanggal riil**]:

| # | Tenggat | Titik nol |
|---|---|---|
| 1 | **BAST ≤ 1 bulan** | sejak **surat persetujuan** Pengelola diterbitkan |
| 2 | **SK Penghapusan ≤ 2 bulan** | sejak **tanggal BAST** |
| 3 | **Laporan penghapusan ≤ 1 bulan** | sejak **SK penghapusan** ditetapkan |

> Versi ringkas yang menyatakan hanya "lapor ≤1 bulan sejak SK penghapusan"
> dan menghilangkan dua tenggat lain **tidak dipakai** — pustaka repo mencatat
> rantai tiga tahap ini lebih dahulu. Keduanya tetap harus direkonsiliasi dari
> teks PMK 40/2024 sebelum pengingat dinyalakan.

**Pengecualian persetujuan penghapusan** [S·1, warisan]: penghapusan karena
alih status **dikecualikan** dari kewajiban meminta persetujuan penghapusan
Pengelola — pengguna lama langsung menetapkan SK penghapusan berdasarkan BAST.
Artinya **tidak perlu permohonan penghapusan terpisah** ke KPKNL.

**SLA layanan** [S·1]: 5 hari kerja sejak berkas lengkap; sebagian KPKNL
menjanjikan 3 hari kerja. **Inkonsisten**, dan diambil dari KPKNL yang tidak
mewilayahi OIKN → **ambil dari Standar Pelayanan KPKNL Balikpapan sendiri**.
Biaya Rp0.

**Dokumen hasil (rekonsiliasi jumlah — koreksi kontradiksi internal riset):**

- **3 dokumen yang relatif pasti**: surat persetujuan Pengelola; BAST (+
  daftar BMN + dokumen kepemilikan asli); SK penghapusan pengguna lama.
- **1 dokumen bersyarat**: dasar pencatatan pada pengguna baru — **dua versi
  bersaing**: (A) Pengelola menerbitkan **keputusan PSP baru** untuk pengguna
  baru; (B) praktik SIMAN: pengguna baru cukup **merekam "SK Alih Status
  Penggunaan BMN"** sebagai dasar pencatatan. **Jangan diasumsikan satu
  dokumen cukup**; konfirmasikan ke KPKNL. [S, ragu]
- **1 dokumen pelaporan**: laporan penghapusan ke Pengelola.

#### 3.4.8 Khusus tanah

- **Sertipikat**: tanah BMN wajib bersertipikat **atas nama Pemerintah
  Republik Indonesia c.q. Kementerian/Lembaga** yang menggunakan (dasar yang
  paling pasti statusnya: **UU 1/2004**). [S]
- Karena alih status memindahkan penguasaan ke K/L lain, dilakukan
  **perubahan pencatatan instansi "c.q." pada sertipikat Hak Pakai** melalui
  Kantor Pertanahan.
  > **Istilah "balik nama" DIHAPUS** — itu peristilahan **peralihan hak**.
  > Pada alih status pemegang haknya tetap Pemerintah RI; yang berubah adalah
  > instansi c.q.-nya. Dasar dan syarat prosesnya diatur regulasi ATR/BPN yang
  > **tidak satu pun disebut** dalam riset ini → **[X] perlu dicari**.
- **Pemecahan/perubahan sertipikat tidak terjadi** pada penggunaan sementara
  (karena PSP tidak berubah), tetapi **terjadi pencatatan c.q.** pada alih
  status — dua hal yang tidak boleh tertukar. [O]

#### 3.4.9 Pencatatan akuntansi pasca-alih status

[S·1 — panduan komunitas SAKTI, bukan peraturan]: pengguna lama merekam
**Transfer Keluar**, pengguna baru merekam **Transfer Masuk** (setelah entitas
pengirim menyetujui). **Transfer masuk sebaiknya direkam pada bulan yang sama**
dengan transfer keluar untuk menghindari **selisih TKTM** di MonSAKTI.
→ AMAN sebaiknya memunculkan peringatan "batas akhir bulan berjalan" begitu
BAST direkam. [O]

---

## 4. BMN berbukti milik vs TANPA bukti milik

### 4.1 Jawaban atas pertanyaan pokok

**Ketiadaan bukti kepemilikan diduga kuat TIDAK menghalangi permohonan — ia
hanya mengubah dan menambah syarat lampiran.** Tidak ditemukan satu pun
ketentuan yang menyatakan permohonan PSP ditolak semata-mata karena BMN belum
bersertipikat; sebaliknya, aturan yang beredar justru **menyediakan jalur
substitusi** agar BMN tanpa dokumen tetap dapat ditetapkan status
penggunaannya.

> **Derajat keyakinan diturunkan menjadi "hipotesis kerja yang kuat", bukan
> pernyataan hukum.** Riset awal menuliskannya sebagai "JAWABAN" atas
> pertanyaan inti, padahal itu **argumentum e silentio** yang ditarik dari
> sesi yang gagal membaca satu pun sumber primer. Ketiadaan temuan pada
> pencarian yang tersumbat bukan bukti ketiadaan norma. **Konsekuensi
> desainnya tetap aman diterapkan** karena bersifat permisif (jangan
> memblokir), **tetapi jangan ditulis sebagai pernyataan hukum di teks
> bantuan aplikasi.** [S → O]

**Sertipikasi tanah adalah kewajiban PARALEL, bukan prasyarat yang
memblokir.** Sejumlah SOP satker menulis "sebelum PSP, Pengguna/Kuasa
Pengguna Barang harus menyelesaikan dokumen kepemilikan tanah/bangunan" —
itu kalimat **kebijakan tertib administrasi**, jangan diterjemahkan menjadi
hard-block di AMAN. [S/O]

### 4.2 Aturan pengganti berjenjang (tiga lapis)

| Lapis | Dokumen | Kondisi |
|---|---|---|
| **1** | Dokumen kepemilikan asli — sertipikat / IMB-PBG / BPKB-STNK / bukti kepemilikan kapal-pesawat | tersedia |
| **2** | **Berita Acara Serah Terima (BAST)** terkait perolehan barang | dokumen kepemilikan **tidak ada** |
| **3** | **Surat Pernyataan Tanggung Jawab bermeterai cukup**, ditandatangani **pejabat struktural** pada K/L | BAST pun **tidak ada** |

[S] — model tiga lapis ini konsisten muncul di cuplikan, **tetapi nomor
pasal/ayatnya tidak diketahui**, dan padanan lampiran formatnya di PMK
40/2024 belum diketahui [X].

**Tambahan kondisional yang berdiri sendiri:**

| Kasus | Dokumen tambahan |
|---|---|
| BPKB dan/atau STNK **hilang** | **Surat Laporan Kehilangan dari Kepolisian** [S·lemah — satu blog praktisi] |
| Bangunan tanpa IMB/PBG, tanpa dokumen perolehan | Surat Pernyataan Tanggung Jawab (lapis 3) [S] |
| Seluruh lampiran berupa fotokopi | **Surat Keterangan Kebenaran Fotokopi** — dokumen **terpisah**, bukan bagian SPTJ [S] |
| Berkas diunggah dalam bentuk pindaian | **Surat Keterangan Kebenaran Arsip Digital** — **nama persis belum pasti** (§5.4) [S·lemah] |

### 4.3 SPTJ / SPTJM — siapa tanda tangan & isi pokoknya

**Penandatangan** [S]: **pejabat struktural yang berwenang** pada K/L
bersangkutan. **Bukan** bendahara, **bukan** operator SIMAN, **bukan**
pejabat fungsional. Untuk satker OIKN, ini berarti pejabat struktural pada
satker/unit organisasi OIKN — lazimnya **Kuasa Pengguna Barang (Kepala
Satker)** atau pejabat yang menerima pelimpahan. **Wajib bermeterai cukup.**

**Isi pokok yang berulang di sumber** [S]:

1. Identitas pejabat: nama, NIP, jabatan **struktural**, satker.
2. Pernyataan bahwa barang tersebut **merupakan Barang Milik Negara**.
3. Pernyataan bahwa barang tersebut **dikuasai dan digunakan untuk
   penyelenggaraan tugas dan fungsi** Kementerian/Lembaga (satker) yang
   bersangkutan.
4. Pernyataan bahwa surat dibuat **dalam rangka permohonan penetapan status
   penggunaan BMN** (atau rezim lain yang relevan).
5. Rincian BMN yang dimaksud (atau rujukan ke lampiran daftar).
6. Meterai + tanda tangan + tanggal.

**Nomenklatur — SPTJ vs SPTJM** [O]: teks aturan yang tercuplik konsisten
memakai frasa **"Surat Pernyataan Tanggung Jawab" (SPTJ)**. Istilah
**"SPTJM"** (…Tanggung Jawab **Mutlak**) muncul di sumber sekunder/praktik
dan dipakai repo ini pada modul **RKBMN**. Rekomendasi: pakai label
**"Surat Pernyataan Tanggung Jawab (SPTJ)"** untuk modul Penggunaan, dan
pertahankan "SPTJM" hanya di modul RKBMN — sampai nomenklatur final
dipastikan dari Lampiran PMK 40/2024.

**Dokumen penguat yang bersifat OPSIONAL** [S·1]: **surat keterangan
Lurah/Camat** dipakai dalam praktik sebuah K/L untuk memperkuat SPTJ atas
tanah. Dari bukti yang ada ini **praktik penguat di tingkat K/L, bukan
dokumen yang disyaratkan PMK** → sediakan sebagai slot **opsional**, jangan
wajib.

### 4.4 Penerapan per rezim

| Rezim | Apakah aturan substitusi berlaku? |
|---|---|
| PSP | **Ya** — inti jalur substitusi ada di sini [S] |
| Alih Status | **Ya** — dokumen permohonan mencakup fotokopi dokumen kepemilikan **atau** BAST perolehan [S] |
| Penggunaan Sementara | **Tidak relevan langsung** — lampiran wajibnya hanya SK PSP + surat permintaan; bukti kepemilikan **bukan** lampiran wajib. Artinya tanah yang belum bersertipikat pada prinsipnya tetap bisa diusulkan **asalkan sudah ber-PSP**. **[O — simpulan penulis, bukan norma]**. Tetap siapkan SPTJ sebagai lampiran tambahan sukarela agar penelitian lebih lancar |
| Dioperasikan Pihak Lain | **Tidak ditemukan ketentuan khusus** [X]. Karena PSP adalah prasyarat mutlak, jalur substitusi sudah terselesaikan di tahap PSP. Perlu konfirmasi langsung ke KPKNL |

### 4.5 Tanah — status kepemilikan bukan boolean

**Enumerasi status yang disarankan** (ganti boolean bersertipikat/tidak) [O]:

`belum_bersertipikat` | `dalam_proses (K1/K2/K3/K4)` | `BBSK` (Bersertipikat
Belum Sesuai Ketentuan — sudah bersertipikat tetapi belum atas nama
Pemerintah RI c.q. K/L yang tepat) | `bersertipikat_sesuai_ketentuan`

**Kategori K1–K4** — dipakai **definisi deskriptif versi pustaka repo**, bukan
label "clean/clear" [O, koreksi pemeriksa]:

| Kategori | Deskripsi yang dipakai |
|---|---|
| K1 | Data yuridis & fisik **lengkap**, tidak sengketa → output sertipikat |
| K2 | Data yuridis/fisik **tidak lengkap**, tidak sengketa → output sertipikat atau **Peta Bidang Tanah (PBT)** |
| K3 | Ada **sengketa/perkara** → output PBT atau produk lain |
| K4 | **Update & validasi** data atas bidang yang sudah bersertipikat |

> Pasangan istilah "clean and clear / not clean but clear / clean but not
> clear" **dipakai terbalik-balik antar artikel DJKN**, dan sumbernya
> berita/artikel, bukan juknis. **Jangan menurunkan aturan validasi otomatis
> dari kesetaraan "K2 = tanpa bukti milik".**

**Untuk tanah yang belum dapat disertipikatkan**, langkah pengamanan
pengganti yang disebut sumber adalah **penandaan Peta Bidang Tanah (PBT)**
dan/atau **Nomor Induk Sementara (NIS)** di Kantor Pertanahan [S·1].
**Apakah PBT/NIS diterima Pengelola Barang sebagai lampiran permohonan
belum dipastikan** [X] — sediakan sebagai jenis lampiran, jangan klaim
sebagai pengganti resmi.

**Girik / Letter C / petok D / eigendom verponding** [S·1, RAGU]:

- Secara substansi ini **dokumen pajak masa kolonial** (girik/petok D) dan
  **buku administrasi desa** (Letter C) — bukan bukti kepemilikan modern,
  melainkan petunjuk hubungan subjek–objek yang perlu diperkuat lewat
  pendaftaran tanah pertama kali.
- Beredar klaim bahwa **PP 18/2021** membatasi pengakuan alat bukti hak lama
  **5 tahun** sejak 2 Februari 2021 (yakni sampai 2 Februari 2026) — sehingga
  per Agustus 2026 **tenggatnya sudah lewat**.
  > **Jangan menampilkan peringatan "dokumen kedaluwarsa" kepada operator
  > atas dasar ini.** Klaim berkonsekuensi paling tinggi ini justru
  > disajikan paling pasti, dibangun dari artikel sekunder tanpa teks PP,
  > tanpa memeriksa adanya perpanjangan/penundaan/aturan pelaksana susulan —
  > padahal tenggat yang lewat justru lazim memicu aturan susulan. Akibat
  > hukumnya juga dirumuskan terlalu keras: pembatasan itu menyangkut
  > **penggunaan alat bukti lama sebagai dasar pendaftaran tanah pertama
  > kali**, bukan pembatalan girik.
- **Perlakuan yang disarankan** [O]: untuk permohonan **PSP**, jalur resminya
  tetap **BAST → SPTJ**; girik/Letter C diperlakukan sebagai **dokumen
  pendukung proses sertipikasi** (alas hak untuk permohonan ke Kantor
  Pertanahan), bukan pengganti bukti kepemilikan dalam berkas PSP.

### 4.6 Peringatan khusus IKN

Banyak aset di kawasan IKN diduga **belum bersertipikat** dan sebagian
mungkin bukan BMN melainkan **ADP**. Dua hal yang harus dipastikan sebelum
modul ini dibangun [X]:

1. Apakah aset OIKN memakai **Hak Pakai** atau **Hak Pengelolaan (HPL)** —
   HPL adalah instrumen berbeda (pelimpahan kewenangan Hak Menguasai Negara),
   lazim untuk badan pengelola kawasan. Riset **gagal** memetakan ini, tetapi
   tetap mengusulkan enum `SERTIPIKAT_HP` dan `SERTIPIKAT_HPL` — enum boleh
   dibuat, **klaim pemetaannya tidak boleh**.
2. Daftar sumber perolehan ADP yang beredar (penetapan & pemberian hak
   pengelolaan lahan; hibah/sumbangan; hasil perjanjian/kontrak; pengalihan
   BMN/BMD; pelaksanaan peraturan perundang-undangan; putusan pengadilan
   berkekuatan hukum tetap) **berpola sama dengan daftar "perolehan lain yang
   sah" BMN pada umumnya** — patut dicurigai sebagai salin-tempel lintas
   konteks. Baca pasal aslinya di PMK 53/2023.

---

## 5. Unggahan berkas ke SIMAN V2

### 5.1 Di mana modul Penggunaan berada

**Tidak ditemukan bukti adanya modul terpisah bernama "Penggunaan".**
Indikasi mengarah pada: **Modul Pengelolaan → submenu Permohonan Pengelolaan
→ pilih jenis pengelolaan (mis. "Penetapan Status Penggunaan") → Tambah →
buat "tiket"**. [O — dinaikkan dari [S] karena sumbernya judul video dan
judul dokumen Scribd yang isinya tidak pernah dibuka; klaim negatif absolut
"tidak ada modul Penggunaan" **tidak boleh ditulis** sebagai temuan]

**Modul yang beredar di SIMAN V2** [S·lemah]: warisan V1 = Master Aset,
Inventarisasi, RKBMN, Pengelolaan, BMN Idle; baru di V2 = Wasdal, Asuransi,
Evaluasi Kinerja Aset, SBSN, Dashboard, User Management.

**Enumerasi "tab Penggunaan"** yang disebut beberapa artikel (Alih Fungsi,
Alih Penggunaan, Penggunaan Sementara, digunakan sementara oleh satker lain
dalam satu Kementerian, Dioperasikan pihak lain, Alih Status Penggunaan,
Penggunaan Sendiri/BMN terindikasi idle) [S·lemah] — riset awal menyarankan
menyalin enumerasi ini **1:1** ke model data AMAN. **Jangan**: satu butir
salah langsung merusak pemetaan, dan nama menu adalah hal yang paling sering
berubah antarversi. Verifikasi dengan **login ke SIMAN V2 dan memotret alur
sebenarnya** — ini satu-satunya butir yang bisa diverifikasi pemilik proyek
**tanpa** akses JDIH. [O]

### 5.2 Format, ukuran, dan penamaan berkas

**[X] TIDAK DIKETAHUI SAMA SEKALI.** Tidak ada satu pun sumber yang menyebut
jenis MIME yang diterima, batas ukuran per berkas/per tiket, pola penamaan,
apakah ADK (Arsip Data Komputer) masih dipakai untuk modul Pengelolaan, atau
apakah tanda tangan elektronik diterima.

> Rumusan jujurnya: *"tidak ditemukan melalui pencarian; dokumen yang paling
> mungkin memuatnya (juknis SIMAN v2, user manual Modul Pengelolaan, booklet
> KPKNL) tidak dapat diakses"* — **bukan** "tidak ada di sumber publik mana
> pun".

**Asumsi kerja sementara (BUKAN spesifikasi SIMAN)** [O]:

| Parameter | Nilai awal usulan | Catatan |
|---|---|---|
| Format | PDF | satu PDF **per jenis dokumen**, bukan satu PDF gabungan raksasa |
| Resolusi | 200–300 DPI | — |
| Warna | **BERWARNA** untuk dokumen bertanda tangan/bermeterai/cap dinas/sertipikat; grayscale hanya untuk lampiran teks polos | **koreksi**: usulan awal "grayscale" berisiko — meterai dan tanda tangan harus terverifikasi, grayscale bisa jadi alasan penolakan |
| Ukuran target | 1–2 MB per berkas | sekadar target, bukan batas resmi |
| Penamaan | deskriptif, tanpa spasi/karakter khusus, mis. `PSP_TANAH_SERTIPIKAT_<NUP>.pdf` atau `PS_<KodeSatker>_<NoSurat>_<Jenis>.pdf` | — |

Seluruh parameter di atas **harus disimpan sebagai konfigurasi**, bukan
konstanta kode, dan diberi label "asumsi, bukan spesifikasi SIMAN". Sediakan
tombol **regenerasi berkas** agar mudah menyesuaikan bila batas asli ternyata
lebih ketat.

### 5.3 Alur berjenjang & peran

**Peran yang beredar** [S·lemah — user manual bertanggal 13 Februari 2023,
yakni **sebelum** juknis 2024]: **Analis** (input/unggah) → **Koordinator**
(verifikasi) → **Supervisor** (persetujuan/kirim) di tingkat satker →
**Eselon 1** (draft verifikasi → verifikasi) → **Pengelola Barang**
(KPKNL/Kanwil DJKN → DJKN).

**Peringatan** [O]:

- Rantai "Eselon 1" mengandaikan struktur kementerian klasik; **OIKN
  memiliki struktur Otorita yang berbeda**, sehingga simpul itu belum tentu
  berpadanan langsung.
- Jadikan rantai persetujuan AMAN sebagai **konfigurasi (daftar simpul yang
  bisa diubah)**, bukan hardcode 5 tahap.
- Akun & peran SIMAN ditetapkan lewat **SK pejabat K/L** (contoh di K/L lain:
  SK penetapan user Administrator/Supervisor/Koordinator/Analis) → OIKN perlu
  SK internal serupa sebelum modul Pengelolaan bisa dipakai [S·lemah].

**Di sisi Pengelola** [S·lemah]: verifikasi berkas → penetapan SETUJU/TIDAK
SETUJU → pencetakan SK → pengiriman ke pemohon → pemohon mengunduh SK dari
aplikasi. Ada pula praktik **verifikasi dini** oleh KPKNL sebelum permohonan
diajukan resmi, dan "modul e-PSP".
> **Anakronisme yang mungkin:** berita modul e-PSP berasal dari **era SIMAN
> V1**. Beri stempel versi/tahun pada setiap temuan fitur SIMAN; tandai e-PSP
> sebagai *"era V1, status di V2 belum diketahui"*.

**Karakteristik SIMAN V2 lain** [S·lemah]: berbasis web (bukan desktop
seperti V1), modular, ada log transaksi, interkoneksi antarmodul, dan
**terkoneksi NADINE** (naskah dinas elektronik Kemenkeu).
> **NADINE adalah aplikasi internal Kemenkeu.** OIKN bukan Kemenkeu, sehingga
> manfaat integrasi itu kemungkinan hanya berlaku di sisi DJKN. Jangan
> merancang AMAN mengandalkan alur naskah dinas yang tidak tersedia bagi
> OIKN — surat permohonan kemungkinan tetap diunggah sebagai PDF
> bertanda tangan. [O]

**Klaim "pengajuan & penerbitan persetujuan dapat dilakukan secara
elektronik" yang diatribusikan ke PMK 40/2024**: sumber yang dicantumkan
riset justru artikel tentang SIMAN, **bukan** cuplikan PMK. Pisahkan: klaim
tentang SIMAN [S·lemah] vs klaim tentang klausul elektronik dalam PMK
[X — belum ada sumber].

### 5.4 Dokumen khas era elektronik

**Surat Keterangan Kebenaran Arsip Digital** — surat yang menyatakan berkas
pindaian yang diunggah benar sesuai aslinya; berbeda dari surat keterangan
kebenaran fotokopi. [S·lemah]
> **Nama persisnya belum pasti** (bisa "surat pernyataan kebenaran dokumen
> digital", "surat keterangan kesesuaian arsip digital dengan aslinya", dst.).
> Template dengan judul yang salah adalah penyebab klasik berkas
> dikembalikan → konfirmasi judul ke KPKNL sebelum template dibekukan. [O]

### 5.5 Hubungan SIMAN ↔ SAKTI (sumber kebenaran terbagi)

| Aplikasi | Perannya | Sumber kebenaran untuk |
|---|---|---|
| **SAKTI** (modul Aset Tetap/Persediaan/GLP) | Pencatatan & penjurnalan BMN | **Nilai & akuntansi** (feeder laporan keuangan) |
| **SIMAN v2** | Pengelolaan BMN (RKBMN, permohonan pengelolaan/PSP, wasdal, asuransi) | **Proses pengelolaan & dokumen persetujuan** |
| **MonSAKTI** | Rekonsiliasi | Selisih TKTM dsb. |

[S·lemah] Jurnal/nilai terbentuk **di SAKTI**, bukan di SIMAN; setelah BAST
disahkan PPK di SAKTI, data mengalir dalam sistem sehingga operator BMN
melengkapi detail barang tanpa input ulang nilai.

**Konsekuensi operasional** [S/O]:

- Data BMN pada tiket SIMAN harus **identik** dengan Master Aset/SAKTI (kode
  barang, NUP, nilai perolehan, tanggal perolehan) — selisih menghambat
  persetujuan; ada praktik **rekonsiliasi usulan data PSP** bersama KPKNL.
- Gejala umum: **daftar BMN tidak muncul** saat membuat tiket PSP → tiket
  hanya menarik BMN yang memenuhi prasyarat tertentu di Master Aset (belum
  ber-PSP, data lengkap, kelompok barang sesuai). AMAN sebaiknya
  **memvalidasi kelengkapan atribut BMN sebelum operator membuka SIMAN**.
- **Setelah SK terbit, satker wajib merekam SK tersebut di SIMAN** (ada
  artikel knowledgebase khusus untuk PSP maupun alih status). Siklus tidak
  berhenti di terbitnya SK → AMAN harus melacak langkah perekaman balik.
- **Hardcopy masih diminta** di banyak KPKNL meski pengajuan elektronik
  [S·lemah, sumber tunggal lingkungan satu K/L] → AMAN sebaiknya menghasilkan
  **paket cetak** sekaligus **paket PDF unggah**.

### 5.6 Dasar hukum lapisan sistem

| Aturan | Catatan |
|---|---|
| **PMK 118 Tahun 2023** (pengelolaan BMN elektronik/SIMAN) | [S] — **waspadai tabrakan nomor** dengan PMK 118/PMK.06/2017 (revaluasi) yang sudah dirujuk di `frontend/src/pages/PenilaianPage.jsx`. Jangan pula diasumsikan menggantikan PMK 181/PMK.06/2016 (Penatausahaan): keduanya **materi berbeda** (sistem vs penatausahaan) — dugaan penggantian itu **dihapus** |
| **KMK 125/KM.6/2024** (tahapan implementasi SIMAN v2, Juli–Desember 2024) | [S·lemah] |
| **"KMK 248 Tahun 2024" (juknis SIMAN v2)** | **[S·lemah — keberadaannya belum terbukti]**. Nomor ini hanya dibaca dari **judul unggahan Scribd**. Ditambah, dua format penomoran berbeda untuk tahun yang sama ("248 Tahun 2024" vs "125/KM.6/2024") adalah indikator kuat salah kutip pada salah satunya — keputusan bernomor `/KM.6/` adalah keputusan yang ditetapkan **atas nama Menteri Keuangan oleh Dirjen Kekayaan Negara**, sehingga menyebutnya "KMK" begitu saja bisa salah rujuk. **Jangan cantumkan nomornya**; tulis "juknis SIMAN v2 (nomor belum dipastikan)" |

---

## 6. [O] Rancangan untuk AMAN

> **Seluruh isi bab ini adalah REKOMENDASI, bukan aturan.** Tidak satu pun
> butir di sini boleh dikutip sebagai dasar hukum. Bab ini menjawab: "apa
> yang sebaiknya dibangun di modul Penggunaan".

### 6.1 Prinsip rancangan (turunan langsung dari keterbatasan bukti)

1. **Aturan sebagai data, bukan kode.** Setiap ambang nilai, tenggat, dan
   daftar lampiran disimpan di tabel konfigurasi bersama: `nilai`,
   `satuan_hitung`, `dasar_hukum`, `tanggal_berlaku`, `status_verifikasi`
   (BELUM_VERIFIKASI | TERVERIFIKASI | DIRAGUKAN), `catatan`. UI menampilkan
   badge "perlu verifikasi" untuk yang belum terverifikasi.
2. **Peringatan lunak, bukan hard block.** Satu-satunya validasi keras yang
   relatif aman: **tidak boleh mengajukan rezim 2/3/4 tanpa SK PSP aktif**
   pada NUP terkait — dan itu pun beri jalur override bercatat untuk kasus
   yang dikecualikan.
3. **Jangan menyembunyikan baris.** Aset yang diduga dikecualikan dari PSP
   tetap tampil dengan penanda + tombol dismiss bercatat (siapa, kapan,
   alasan).
4. **Jangan mencetak nomor pasal.** Generator surat tidak boleh punya slot
   "Pasal …" sampai §7.3 tuntas. Bagian "Mengingat" cukup menyebut nama
   peraturan tanpa nomor pasal, dan hanya peraturan yang statusnya sudah
   diverifikasi.
5. **Rute paling konservatif saat ragu** (ke Pengelola Barang), dan **"perlu
   penentuan manual"** untuk kasus tepat di ambang.
6. **Perluas struktur yang sudah ada, jangan bikin entitas baru.** Repo sudah
   memiliki `backend/penggunaan_utils.py` dengan `JENIS_PROSES_PENGGUNAAN`
   (alih_status, penggunaan_sementara, dioperasikan_pihak_lain,
   penggunaan_bersama), `ARAH_PROSES` (keluar/masuk), `STATUS_PROSES`, dan
   `TRANSISI_PROSES` per jenis. Usulan "entitas BerkasAlihStatus" yang berdiri
   sendiri **ditolak** — ia menduplikasi register dan memakai penamaan field
   yang berbeda. Yang benar: **tambah field** pada tiket proses yang ada.

### 6.2 Field baru yang diusulkan pada tiket proses Penggunaan

| Field | Tipe/format | Berlaku untuk rezim | Guna |
|---|---|---|---|
| `jalur` | enum: `permohonan_pengguna` \| `inisiatif_pengelola` | alih status, PSP | dua jenis berkas berbeda |
| `sub_jalur_objek_pada` | enum: `pengguna_barang` \| `pengelola_barang` | penggunaan sementara | menentukan produk: **persetujuan** vs **penetapan** |
| `jenis_objek` | enum: `TANAH` \| `TANAH_DAN_BANGUNAN` \| `BANGUNAN` \| `SELAIN_TB` | semua | pohon keputusan |
| `punya_dokumen_kepemilikan` | bool | semua | cabang lampiran |
| `tingkat_substitusi_bukti` | enum 1/2/3 (asli / BAST / SPTJ) | semua | validasi lampiran §4.2 |
| `nilai_perolehan_per_nup` | rupiah | semua | uji ambang A |
| `total_nilai_paket` | rupiah (terhitung) | semua | uji ambang B/C |
| `hasil_uji_ambang` | enum: `PENGGUNA_SENDIRI` \| `PENGELOLA` \| `PERLU_PENENTUAN_MANUAL` | PSP | rute + badge |
| `instansi_tujuan` | teks (default KPKNL Balikpapan, dapat diubah) | semua | alamat surat |
| `tanggal_perolehan_yuridis` | date | PSP | basis tenggat (dipisah dari BAST) |
| `tanggal_bast_perolehan` | date | PSP | idem |
| `tanggal_surat_permintaan` / `nomor_surat_permintaan` | date/teks | sementara, dioperasikan | dokumen pemicu |
| `tanggal_persetujuan_pengelola` | date | sementara, alih status | **titik nol** rantai tenggat |
| `tanggal_perjanjian` | date | sementara, dioperasikan | pengingat lunak ≈3 bulan |
| `tanggal_bast_penyerahan` / `tanggal_bast_pengembalian` | date | sementara, dioperasikan, alih status | siklus |
| `tanggal_sk_penghapusan` / `tanggal_laporan_penghapusan` | date | alih status | rantai tenggat |
| `status_penguasaan` | enum, mis. `digunakan_sementara_oleh_kl_lain`, `dioperasikan_pihak_lain` | sementara, dioperasikan | penanda pada aset, bukan mutasi keluar |
| `kl_pengguna_sementara` / `satker_pengguna_sementara` | teks | sementara | pengungkapan |
| `penanggung_asuransi` | teks/enum | sementara, dioperasikan | kaitkan ke modul asuransi |
| `jenis_pihak_lain` | enum **belum boleh dikunci** (§3.3.4) | dioperasikan | — |
| `ada_pungutan_ke_masyarakat` | bool | dioperasikan | memicu lampiran estimasi biaya & pungutan |
| `ada_bangunan_milik_pihak_lain` | bool | dioperasikan (tanah) | penanda pada NUP tanah |
| `nomor_tiket_siman` | teks | semua | penelusuran balik |

### 6.3 Generator surat

- Satu **template terkunci per jenis surat** (§3.1.3, §3.2.3, §3.3.5,
  §3.4.3), bukan unggah bebas. Alasan: DJKN sendiri mencatat kendala utama
  satker adalah **ketidakseragaman dan ketidaklengkapan dokumen** [S·lemah].
- Field terstruktur untuk: nomor surat, tanggal, hal, pejabat penanda tangan
  (nama/NIP/jabatan struktural) + **dasar pendelegasian**, tembusan, daftar
  lampiran bernomor.
- **Pisahkan** `pejabat_penanda_tangan` dari `petugas_penyusun` agar template
  tidak salah tanda tangan.
- Generator **Daftar BMN** dengan dua varian kolom (TB dan STB, §3.1.6) yang
  bisa langsung ditempel ke surat dan dipakai ulang pada BAST & SK
  penghapusan.
- Generator **SPTJ**, **Surat Keterangan Kebenaran Fotokopi**, dan **Surat
  Keterangan Kebenaran Arsip Digital** (judul dokumen terakhir masih perlu
  konfirmasi).
- **Tanpa slot nomor pasal.**

### 6.4 Checklist berkas per rezim (kondisional)

Bangun sebagai **konfigurasi berversi**, bukan sembilan slot ter-hardcode —
karena daftar lampiran PMK 40/2024 belum diketahui dan checklist yang ada
berasal dari era PMK 246/2014:

```
checklist_set:
  id: psp_v2024_dugaan
  rezim: PSP
  versi_rezim: "PMK 40/2024 (dugaan)"
  status_verifikasi: BELUM_VERIFIKASI
  butir:
    - kode: surat_permohonan        wajib: selalu
    - kode: daftar_bmn              wajib: selalu
    - kode: sptj                    wajib: selalu
    - kode: dok_kepemilikan         wajib: jika punya_dokumen_kepemilikan
    - kode: ket_kebenaran_fotokopi  wajib: jika ada_lampiran_fotokopi
    - kode: kib                     wajib: jika jenis_bmn_wajib_kib
    - kode: dasar_pendelegasian     wajib: jika penandatangan != pengguna_barang
    - kode: laporan_kondisi         wajib: jika tersedia_di_sakti
    - kode: foto_bmn                wajib: dianjurkan
    - kode: lapor_kehilangan_polri  wajib: jika dokumen_hilang
```

Tombol "kirim" **boleh** meminta konfirmasi bila ada butir wajib yang kosong,
tetapi **tidak memblokir** butir yang statusnya `BELUM_VERIFIKASI`.

### 6.5 Pengingat & timer (semua bersifat lunak)

| Pengingat | Basis | Label |
|---|---|---|
| PSP mendekati 6 bulan sejak perolehan | `tanggal_perolehan_yuridis` **dan** `tanggal_bast_perolehan` (tampilkan keduanya) | "indikatif — subjek & basis tenggat belum terverifikasi" |
| Perpanjangan penggunaan sementara | T-60 dan T-45 sebelum berakhir (agar tenggat T-30 tidak terlewat) | "perlu verifikasi" |
| Perpanjangan dioperasikan pihak lain | T-90 | "perlu verifikasi" |
| Penandatanganan perjanjian pasca-persetujuan | ≈3 bulan | pengingat lunak, **jangan** memicu status "terlambat" |
| Rantai alih status | BAST T+1 bln → SK hapus T+2 bln → laporan T+1 bln | "perlu verifikasi", jangan memblokir input tanggal riil |
| Pelaporan berakhirnya penggunaan | T+30 sejak BAST pengembalian | "dasar pasal belum terkonfirmasi" |
| Rekam transfer keluar/masuk SAKTI | bulan yang sama dengan BAST | peringatan "batas akhir bulan berjalan" |
| Rekam SK ke SIMAN setelah terbit | begitu `nomor_sk` diisi | tugas turunan |

**Tidak** dibuat: alarm keterlambatan yang menuduh KPKNL berdasarkan SLA 5
hari kerja (itu janji layanan, dan hanya untuk tanah/bangunan).

### 6.6 Validasi ambang nilai

```
uji_ambang(objek, nilai_per_nup, total_paket):
  jika objek in (TANAH, TANAH_DAN_BANGUNAN, BANGUNAN):
      -> PENGELOLA  (tidak ada jalur mandiri)  [dugaan]
  jika objek == SELAIN_TB:
      jika punya_dokumen_kepemilikan:
          -> PENGELOLA  [dugaan]
      selain itu:
          jika nilai_per_nup == AMBANG or total_paket == AMBANG:
              -> PERLU_PENENTUAN_MANUAL
          jika nilai_per_nup > AMBANG or total_paket > AMBANG:
              -> PENGELOLA          # konservatif: cukup salah satu lewat
          selain itu:
              -> PENGGUNA_SENDIRI (badge "perlu verifikasi")
```

Saran kantor tujuan (KPKNL/Kanwil/Pusat) dari tangga nilai ditampilkan
sebagai **teks saran** dengan badge "angka belum diverifikasi" — **tidak**
mengunci pilihan operator.

### 6.7 Hal yang sengaja TIDAK dibangun

| Tidak dibangun | Alasan |
|---|---|
| Cabang logika **alutsista** | OIKN tidak menguasai alutsista; hanya menambah cabang mati |
| **Filter** yang menyembunyikan objek yang diduga dikecualikan dari PSP | menukar false positive murah dengan false negative mahal |
| Teks bantuan "pemanfaatan bangunan milik pihak lain di atas tanah BMN tidak perlu persetujuan Pengelola" | klaim berisiko hukum tertinggi, sumbernya aturan yang diduga dicabut |
| Enum kategori Pihak Lain + validasi jangka waktu turunannya | daftar dan tabel jangka waktunya saling bertabrakan |
| Slot "nomor pasal" pada template surat | surat dinas dengan nomor pasal salah lebih berbahaya daripada surat tanpa nomor pasal |
| Hard block "belum bersertipikat" | ketiadaan bukti milik diduga **tidak** menghalangi permohonan |
| Istilah "Pengguna Barang Eminen"/"Kolaborator" | tidak lazim; diduga hasil parafrase/halusinasi |
| Konstanta 179 hari untuk ambang 6 bulan | "6 bulan" adalah satuan **kalender**; konversi ke hari memperkenalkan galat sendiri |

### 6.8 Keluaran yang diharapkan dari modul

1. **Paket unggah SIMAN**: PDF per jenis dokumen + penamaan baku +
   `nomor_tiket_siman` tersimpan untuk penelusuran balik.
2. **Paket cetak** (hardcopy) untuk KPKNL yang masih memintanya.
3. **Lembar checklist kelengkapan** yang tercetak mengikuti checklist resmi
   KPKNL wilayah.
4. **Dasbor kepatuhan** berisi: BMN belum PSP (tanpa disembunyikan), tiket
   berjalan per rezim, tenggat mendekat, SK yang belum direkam ke SIMAN.
5. **Pengungkapan** status penguasaan pada Laporan Barang/CaLBMN untuk aset
   yang sedang digunakan sementara / dioperasikan pihak lain.

---

## 7. Yang BELUM terverifikasi dari teks primer

> Bagian ini adalah **bagian terpenting dokumen**. Ia menyatakan dengan
> tepat apa yang tidak diketahui, sehingga sisa dokumen bisa dipercaya
> sebatas yang memang layak dipercaya.

### 7.1 Sebab: seluruh sumber primer diblokir

Setiap percobaan pengambilan halaman ditolak **di tingkat gateway egress**
(403 pada CONNECT / policy denial), bukan 403 dari situsnya. Kuota pencarian
web pada sesi riset dan sesi pemeriksaan juga habis. Karena itu:

- **Tidak satu pun** peraturan, manual, checklist, atau artikel di bawah ini
  yang pernah dibaca isinya.
- Seluruh isi dokumen ini berasal dari **cuplikan mesin pencari** +
  **pemeriksaan konsistensi internal** + **silang ke pustaka repo**.
- **Pemeriksaan skeptis pun tidak memverifikasi apa pun secara independen** —
  koreksi-koreksinya adalah **daftar hal yang harus dicurigai**, bukan
  koreksi yang sudah terbukti.

### 7.2 Sepuluh prioritas verifikasi manual

| # | Yang harus dibuka/dilakukan | Yang harus dicatat |
|---|---|---|
| 1 | **PDF PMK 40 Tahun 2024** (JDIH Kemenkeu / PPID DJKN) | Benarkah ada; judul persis; tanggal penetapan & pengundangan; **Ketentuan Penutup** (daftar yang dicabut) dan **Ketentuan Peralihan** (nasib permohonan berjalan) |
| 2 | **Perubahan/pencabutan atas PMK 40/2024 sampai 2026** | Apakah masih rezim terkini per Agustus 2026 |
| 3 | **PMK 53 Tahun 2023** (BMN & ADP di IKN) + **UU 3/2022 jo. UU 21/2023** + **PMK 139/PMK.08/2022** | Status OIKN sebagai Pengguna Barang; definisi & sumber perolehan ADP; apakah menyimpangi PMK 40/2024; adakah PMK penyesuaian pasca-UU 21/2023 |
| 4 | **Rumusan ambang Rp100 juta — kutip VERBATIM** | "per unit/satuan" **atau** "per usulan/permohonan"; operator perbandingan (≤/<) |
| 5 | **KMK pelimpahan wewenang DJKN yang berlaku 2024–2026** | Tangga nilai KPKNL/Kanwil/Pusat yang sebenarnya (bukan KMK 229/KM.6/2016 era lama) |
| 6 | **Ambang 6 bulan penggunaan sementara** | "kurang dari" vs "paling lama"; **siapa yang menyetujui** pada jalur pendek; **apakah tetap wajib pemberitahuan** ke Pengelola |
| 7 | **PMK 4/PMK.06/2015** | Masih berlaku atau sudah diserap PMK 40/2024; daftar kewenangan yang didelegasikan butir demi butir (PSP saja / pemindahtanganan saja / keduanya) |
| 8 | **Checklist resmi KPKNL Balikpapan** + Standar Pelayanannya | Daftar lampiran otoritatif per rezim; SLA yang benar; konfirmasi wilayah kerja atas IKN/PPU |
| 9 | **Juknis & user manual SIMAN v2** (nomor belum dipastikan) | Struktur menu; slot unggah; format/ukuran/penamaan berkas; peran & rantai persetujuan; apakah TTE diterima |
| 10 | **Login SIMAN V2 dan potret alur sebenarnya** | Satu-satunya butir yang bisa diverifikasi **tanpa** akses JDIH |

**Pertanyaan lain yang masih terbuka** (tidak berurut prioritas):

- Subjek dan titik-mulai tenggat 6 bulan PSP; apakah seragam untuk semua
  jenis objek.
- Jumlah maksimal & panjang perpanjangan penggunaan sementara **[X]**.
- Tenggat penandatanganan perjanjian (3 bulan?) — satu cuplikan.
- Kewajiban lapor 1 bulan pasca-SK PSP mandiri — satu jalur sumber.
- Rantai tenggat alih status (1/2/1 bulan) — satu rumpun cuplikan; dan
  apakah pengecualian persetujuan penghapusan benar ada.
- Dasar pencatatan pada Pengguna Barang baru: SK PSP dari Pengelola atau
  keputusan internal.
- Instrumen alih status: benarkah **tanpa** perjanjian (cukup persetujuan +
  BAST + penetapan).
- Daftar resmi kategori "Pihak Lain" dan tabel jangka waktunya **dalam satu
  pasal**; kebenaran angka **99 tahun**; status anak perusahaan BUMN.
- Perlakuan uang pada rezim dioperasikan pihak lain (seluruh keuntungan /
  hasil pungutan / perlu dasar tarif PNBP tersendiri); apakah istilah
  "kompensasi" memang dipakai.
- Benarkah Pihak Lain boleh mendirikan bangunan miliknya di atas tanah BMN,
  dan benarkah pemanfaatan bangunan itu bebas persetujuan Pengelola.
- Ambang nilai kewenangan untuk **penggunaan sementara** dan **dioperasikan
  pihak lain** — **[X] nihil, diduga ADA**.
- Apakah **Lampiran** PMK 40/2024 memuat **format baku** Surat Permohonan /
  Persetujuan / Perjanjian / BAST / SPTJ / Surat Keterangan Kebenaran
  Fotokopi. Bila ada, seluruh kerangka surat [O] di dokumen ini **harus
  diganti** format resminya.
- Padanan "Lampiran I B / II B PMK 246/2014" di PMK 40/2024.
- Daftar pengecualian PSP: bertahan identik atau berubah.
- Identitas & status PMK 87/PMK.06/2016 dan PMK 76/PMK.06/2019 (benarkah
  keduanya perubahan atas PMK 246/2014, benarkah keduanya dicabut).
- Nomor & keberlakuan peraturan pendamping: PMK Pemanfaatan (klaim
  115/PMK.06/2020), Penatausahaan (181/PMK.06/2016), Wasdal (klaim
  207/PMK.06/2021), Asuransi BMN (klaim 97/PMK.06/2019), Penghapusan
  (83/PMK.06/2016), **PMK 120 Tahun 2024** tentang BMN idle (yang sama sekali
  tidak dibahas riset padahal "BMN terindikasi idle" muncul di enumerasi tab
  Penggunaan), **PMK 90 Tahun 2024** (masa transisi K/L).
- **PMK 118 Tahun 2023 vs PMK 118/PMK.06/2017** — pastikan nomor yang benar
  sebelum dikutip (tabrakan dengan rujukan di `PenilaianPage.jsx`).
- Peraturan ATR/BPN yang mengatur **perubahan pencatatan instansi c.q.** pada
  sertipikat Hak Pakai; dan pemetaan **Hak Pakai vs HPL** untuk aset OIKN.
- **PP 18/2021** dan aturan susulannya terkait alat bukti hak lama.
- Peraturan/Keputusan **Kepala Otorita IKN** tentang pendelegasian kewenangan
  pengelolaan BMN & penandatanganan.

### 7.3 Daftar angka & nomor yang DILARANG dikutip

Nomor-nomor berikut sempat beredar dalam riset. **Semua sudah dikeluarkan
dari badan dokumen** dan dicatat di sini **hanya sebagai jejak**, agar tidak
tanpa sengaja masuk kembali:

| Yang beredar | Mengapa dilarang |
|---|---|
| "Pasal 11 PMK 40/2024" | dipakai untuk **enam klaim berbeda** (dokumen per jenis objek, substitusi berjenjang, penandatangan SPTJ, kebenaran fotokopi, ambang Rp100 juta, tenggat 6 bulan) — mustahil satu pasal memuat semuanya; ciri khas satu cuplikan yang direplikasi |
| "Pasal 32–40 PMK 40/2024" (penggunaan sementara) | pemetaan tidak konsisten: Pasal 33 & 37 masing-masing dipakai untuk dua materi; Pasal 39 dipakai ganda; pola "X/Y" = nomor ditebak dari kedekatan |
| "Pasal 11/15/21–23/24/25/26 PMK 40/2024" (dioperasikan pihak lain) | tumpang tindih semantik (21–23 "permohonan/penelitian", lalu 24 "permohonan", 25 "penelitian") |
| "Bab VII / Pasal 10 / 52 / 53 / 54 / 55 PMK 40/2024" (alih status) | Pasal 55 diakui sendiri sebagai "perkiraan posisi" (54+1); Pasal 52 dipakai secara analogi lalu tampil seolah sitasi |
| "Pasal 25 PP 27/2014" (delegasi) & "Pasal 26/27 PP 27/2014" | hipotesis bersaing; dan "Pasal 25" dipakai untuk dua rezim berbeda dalam satu dokumen |
| "Pasal 18 PP 27/2014" (dioperasikan pihak lain) | arah koreksinya diduga benar, tetapi bunyinya dikutip dari artikel lama **tanpa** memeriksa perubahan PP 28/2020 |
| "Pasal 16 ayat (3) PMK 83/2016" | satu pasal memikul dua norma berbeda; sumber sekunder yang kemungkinan saling menyalin |
| "Pasal 3 & 4 PMK 246/2014", "Pasal 9 PMK 246/2014", "Lampiran I B / II B" | rezim yang diduga sudah dicabut |
| "KMK 248 Tahun 2024" | keberadaannya hanya dari judul unggahan Scribd |
| Tangga nilai Rp5 M / Rp25 M / Rp10 M / Rp50 M / Rp100 M | satu jalur sumber; instrumen (PMK vs KMK) kemungkinan salah; bertabrakan dengan tangga rezim pemindahtanganan |
| "99 tahun" | tidak berpadanan dengan tenor mana pun dalam rezim BMN yang dikenal |
| "KPKNL Penajam" | kantor yang kemungkinan besar tidak ada |
| Angka rupiah presisi pada contoh kasus (mis. nilai tanah pada berita penggunaan sementara) | dari halaman yang tidak pernah terbaca; tidak punya nilai normatif |
| Tanggal & data bibliografis presisi (21 Juni 2024; BN 2016 No. 791, 18 halaman; 6 Januari 2015 berlaku 1 Juli 2015; 14 Mei 2019; 24 Desember 2014; 4 November 2024 berlaku 5 November 2024) | **presisi palsu** — semua dari cuplikan, disajikan setingkat kutipan primer sehingga pembaca berikutnya akan mengira sudah diverifikasi |

### 7.4 Daftar URL yang diblokir (untuk dibuka manual dari jaringan biasa)

**Peraturan inti**

- https://jdih.kemenkeu.go.id/dok/pmk-40-tahun-2024
- https://jdih.kemenkeu.go.id/dok/pmk-40-tahun-2024/view
- https://jdih.kemenkeu.go.id/dok/pmk-40-tahun-2024/summary
- https://jdih.kemenkeu.go.id/api/download/57218375-2d3d-443c-9271-8d7a20731081/2024pmkeuangan040.pdf
- https://ppiddjkn.kemenkeu.go.id/storage/20250701-328.pdf
- https://peraturan.bpk.go.id/Details/292599/pmk-no-40-tahun-2024
- https://peraturan.go.id/id/permenkeu-no-40--tahun-2024
- https://www.regulasip.id/book/21940/read
- https://djpb.kemenkeu.go.id/kppn/bandarlampung/id/download/peraturan-terbaru/3078-pmk-no-40-tahun-2024-tentang-tata-cara-penggunaan-barang-milik-negara.html
- https://meridianhukum.com/peraturan/pmk-no-40-tahun-2024
- https://andzaribrahim.com/analisis-pmk-no-40-2024-tentang-penggunaan-barang-milik-negara/

**Rezim lama (untuk memastikan pencabutan & rujukan historis)**

- https://peraturan.bpk.go.id/Details/122027/pmk-no-246pmk062014
- https://jdih.kemenkeu.go.id/dok/246-pmk-06-2014
- https://jdih.kemenkeu.go.id/fulltext/2014/246~PMK.06~2014Per.HTM
- https://jdih.kemenkeu.go.id/api/download/1a793e9d-a108-43a2-84b5-b22602abb4c5/PMK%20246%202014.pdf
- https://www.kemhan.go.id/itjen/wp-content/uploads/2022/08/pmk-246-2014-tentang-penggunaan-bmn-1.pdf
- https://kppip.go.id/en/download/peraturan/permen/permenkeu/46.-Peraturan-Menteri-Keuangan-Nomor-246PMK.062014-tentang-Tata-Cara-Pelaksanaan-Penggunaan-Barang-Milik-Negara.pdf
- https://peraturan.bpk.go.id/Details/121089/pmk-no-87pmk062016
- https://jdih.kemenkeu.go.id/api/download/fulltext/2016/87~PMK.06~2016Per.pdf
- https://jdih-old.kemenkeu.go.id/FullText/2016/87~PMK.06~2016Per.pdf
- https://peraturan.bpk.go.id/Details/128061/pmk-no-76pmk062019
- https://jdih.kemenkeu.go.id/fullText/2019/76~PMK.06~2019Per.pdf
- https://www.regulasip.id/book/15337/read
- https://paralegal.id/peraturan/peraturan-menteri-keuangan-nomor-246-pmk-06-2014/

**Payung & aturan pendamping**

- https://peraturan.bpk.go.id/Details/5464/pp-no-27-tahun-2014
- https://peraturan.go.id/id/pp-no-27-tahun-2014
- https://bphn.go.id/data/documents/14pp027.pdf
- https://jdih.kemenkeu.go.id/fulltext/2014/27TAHUN2014PP.htm
- https://peraturan.bpk.go.id/Details/138973/pp-no-28-tahun-2020
- https://peraturan.bpk.go.id/Details/121909/pmk-no-4pmk062015
- https://jdih.kemenkeu.go.id/dok/4-pmk-06-2015
- http://bmn.bmkg.go.id/wp-content/uploads/2014/06/PMK-4-Tahun-2015-Tentang-pendelegasian-sbagian-kewenangan-ke-pengguna-barang.pdf
- https://peraturan.bpk.go.id/Home/Details/121081/pmk-no-83pmk062016
- https://ditjenbun.pertanian.go.id/template/uploads/2021/09/PMK-83-TAHUN-2016-TATA-CARA-PELAKSANAAN-PEMUSNAHAN-DAN-PENGHAPUSAN-BMN.pdf
- https://peraturan.bpk.go.id/Details/307187/pmk-no-90-tahun-2024
- https://jdih.kemenkeu.go.id/dok/pmk-90-tahun-2024
- https://jdih.kemenkeu.go.id/fulltext/2009/186~PMK.06~2009Per.htm
- https://jdih.kemenkeu.go.id/dok/186-pmk-06-2009
- https://ekolumajang.com/wp-content/uploads/2010/11/pmk-186-2009-pensertipikatan-bmn-tanah.pdf
- https://jdih.kemenkeu.go.id/api/download/5d3f3816-bfc9-492d-8b6b-332acee5d33f/2023pmkeuangan118%20(2).pdf

**Khusus IKN**

- https://peraturan.bpk.go.id/Details/249043/pmk-no-53-tahun-2023
- https://jdih.kemenkeu.go.id/dok/pmk-53-tahun-2023/view
- https://jdih-old.kemenkeu.go.id/in/dokumen/peraturan/a66a7f2f-30dd-4178-035e-08db54fba7f4
- https://www.djkn.kemenkeu.go.id/kanwil-rsk/baca-artikel/17184/Aset-Dalam-Penguasaan-ADP-Di-Ibu-Kota-Nusantara-Dalam-PMK-Nomor-53-Tahun-2023.html

**SIMAN v2, juknis, manual**

- https://halodjkn.kemenkeu.go.id/kb/siman-v2
- https://halodjkn.kemenkeu.go.id/en-US/kb/articles/panduan-user-manual-aplikasi-siman-v2-modul-pengelolaan
- https://halodjkn.kemenkeu.go.id/en-US/kb/articles/panduan-user-manual-pendaftaran-user-aplikasi-siman-v2
- https://halodjkn.kemenkeu.go.id/kb/articles/cara-merekam-sk-penetapan-status-penggunaan-pada-aplikasi-siman
- https://halodjkn.kemenkeu.go.id/kb/articles/cara-merekam-sk-alih-status-penggunaan-bmn-pada-aplikasi-siman
- https://halodjkn.kemenkeu.go.id/en-US/kb/articles/cara-melihat-bmn-belum-psp-penetapan-status-penggunaan-pada-aplikasi-siman
- https://halodjkn.kemenkeu.go.id/kb/bantuan-aplikasi
- https://e-dropbox.kemenkeu.go.id/index.php/s/MGNXFtgQR23byvE
- https://fliphtml5.com/BOOKLETSIMAN/ujol/BOOKLET_PANDUAN_PENGGUNAAN_BMN_PADA_APLIKASI_SIMAN_v2/
- https://cdn.heyzine.com/files/uploaded/6347e70bcc1f4e4344c37c469b5b9279f7a1ef11.pdf
- https://klc2.kemenkeu.go.id/kms/knowledge/panduan-lengkap-pengajuan-status-penggunaan-bmn-bagian-1-f8deebbd/detail/
- https://klc2.kemenkeu.go.id/kms/knowledge/prosedur-penetapan-status-penggunaan-psp-bmn-282e4771/detail/
- https://klc2.kemenkeu.go.id/kms/faq/permohonan-penetapan-status-penggunaan-barang-milik-negara-oleh-pengelola-barang-ce8c0d67/detail/
- https://www.pta-jambi.go.id/attachments/article/5919/pengajuan%20Permohonan%20PSP%20BMN%20melalui%20SIMAN.pdf
- https://www.mahkamahagung.go.id/media/6370
- https://ms-aceh.go.id/publikasi/arsip-pengumuman%E2%80%8B/item/7221-pengajuan-permohonan-penetapan-status-penggunaan-bmn-melalui-aplikasi-siman.html
- https://sipora.polije.ac.id/40992/

**Artikel & standar pelayanan DJKN/KPKNL**

- https://www.djkn.kemenkeu.go.id/artikel/baca/16053/Mengenal-Penetapan-Status-Penggunaan-Barang-PSP-Barang-Milik-Negara-BMN.html
- https://www.djkn.kemenkeu.go.id/kpknl-cirebon/baca-artikel/18333/PENTINGNYA-PENETAPAN-STATUS-PENGGUNAAN-BARANG-MILIK-NEGARA-MENUJU-PENGELOLAAN-ASET-NEGARA-YANG-TERTIB-DAN-OPTIMAL.html
- https://www.djkn.kemenkeu.go.id/kpknl-tarakan/baca-artikel/15619/Penetapan-Status-Penggunaan-BMN-Bagaimana-Prosedurnya.html
- https://www.djkn.kemenkeu.go.id/kpknl-palu/baca-artikel/16841/Penetapan-Status-Penggunaan-PSP-BMN-Tertib-Wujudkan-Pengelolaan-Anggaran-Yang-Baik.html
- https://www.djkn.kemenkeu.go.id/kpknl-pekalongan/baca-artikel/13418/Standar-Pelayanan-Penetapan-Status-Penggunaan-Barang-Milik-Negara-BMN-Berupa-Tanah-danatau-Bangunan.html
- https://www.djkn.kemenkeu.go.id/kpknl-yogyakarta/baca-artikel/16931/PENGGUNAAN-BMN-SESUAI-DENGAN-KETENTUAN.html
- https://www.djkn.kemenkeu.go.id/kpknl-jakarta2/baca-berita/32647/Penggunaan-Sementara-BMN-Kementerian-Sekretariat-Negara-Untuk-Optimalisasi-Aset.html
- https://www.djkn.kemenkeu.go.id/kpknl-tasikmalaya/baca-berita/29353/Alih-Status-Penggunaan-pada-PP-Tasikmalaya-kepada-Bawaslu-Kota-Tasikmalaya-sebagai-upaya-optimalisasi-Penggunaan-BMN.html
- https://www.djkn.kemenkeu.go.id/kpknl-banjarmasin/baca-berita/11665/Modul-e-PSP-Semangat-Inovasi-Pengelolaan-BMN-pada-Pengguna-Barang.html
- https://www.djkn.kemenkeu.go.id/kanwil-jatim/baca-artikel/17236/Implementasi-Aplikasi-SIMAN-Versi-2-dalam-Pengelolaan-BMN.html
- https://www.djkn.kemenkeu.go.id/kanwil-lampungbengkulu/baca-artikel/17289/Memahami-Asas-Pengelolaan-BMN-dan-Alur-Proses-Pengelolaan-BMN-Kunci-Sukses-untuk-Trouble-Shooting-SIMAN-V2.html
- https://www.djkn.kemenkeu.go.id/kpknl-pangkalanbun/baca-artikel/15283/Dinamika-Pensertipikatan-BMN-Berupa-Tanah.html
- https://www.djkn.kemenkeu.go.id/kpknl-jakarta4/baca-berita/29219/Monitoring-Sertipikasi-Tanah-BMN-yang-Masih-BBSK-Bersertipikat-Belum-Sesuai-Ketentuan.html
- https://sippn.menpan.go.id/pelayanan-publik/8197677/kpknl-jakarta-ii/penetapan-status-penggunaan-barang-milik-negara-bmn-berupa-tanah-danatau-bangunan
- https://sippn.menpan.go.id/pelayanan-publik/7951559/kpknl-padang/penetapan-status-penggunaan-bmn-berupa-tanah-dan-atau-bangunan
- https://sippn.menpan.go.id/pelayanan-publik/kementerian-keuangan/direktorat-jenderal-kekayaan-negara/kpknl-pekanbaru/kantor-pelayanan-kekayaan-negara-dan-lelang-pekanbaru/pengalihan-status-penggunaan-barang-milik-negara
- https://sippn.menpan.go.id/pelayanan-publik/8133181/kpknl-bengkulu/pengalihan-status-penggunaan-barang-milik-negara
- https://sippn.menpan.go.id/pelayanan-publik/8129739/kantor-wilayah-direktorat-jenderal-kekayaan-negara-kalimantan-timur-dan-utara/pengalihan-status-penggunaan-barang-milik-negara
- https://sibangkoman.pu.go.id/center/pelatihan/uploads/edok/2020/07/d6cee_39291_07._Penggunaan_BMN.pdf
- https://www.kemhan.go.id/pusbmn/2019/07/01/penetapan-status-penggunaan-dan-implikasinya-dalam-pengelolaan-bmn.html
- https://www.kemhan.go.id/pusbmn/2018/12/14/panduan-singkat-pelaksanaan-penggunaan-bmn-di-lingkungan-kemhan-dan-tni.html
- https://gorontalo.kemenag.go.id/opini/400/-
- https://ntt.kemenag.go.id/artikel/43223/layanan-permohonan-penetapan-status-penggunaan-bmn-bangunan
- https://sarpras.upi.edu/tata-cara-pelaksanaan-penghapusan-barang-milik-negara/
- https://jdih.pu.go.id/internal/assets/assets/produk/SEMenteriPUPR/2025/02/2025SEMenteriPU2.pdf
- https://batam.imigrasi.go.id/assets/resources/files/TATACARA_TRANSFER_BMN.pdf
- https://jurnal.fh.unila.ac.id/index.php/fiat/article/download/734/616/2241
- https://statik.unesa.ac.id/akuntansi/file/982c36df-76cd-4498-98b7-defec70fb28f.pdf
- https://jogja.kemenkum.go.id/attachments/2025/PEDOMAN_TEKNIS_PENGELOLAAN_BMN_PADA_MASA_TRANSISI_KABINET_MERAH_PUTIH.pdf

**Sumber lemah (Scribd/SlideShare/blog) — hanya untuk pelacakan, bukan
rujukan**

- https://www.scribd.com/document/488794208/Checklist-Permohonan-Penetapan-Status-Penggunaan-BMN
- https://www.scribd.com/document/367122530/2-Ceklist-Alih-Status-Penggunaan-BMN
- https://www.scribd.com/document/854440591/Checklist-Alih-Status-Penggunaan
- https://www.scribd.com/document/798793870/KMK-248-Tahun-2024-Juknis-SIMAN-v2
- https://www.scribd.com/document/895287707/Rangkuman-PMK-40-2024
- https://www.scribd.com/document/889343413/Tutor-pengajuan-Tiket-Psp
- https://www.scribd.com/document/526161293/tutorial-perekaman-psp-bmn
- https://www.scribd.com/document/428816586/Prosedur-Tata-Cara-Pengajuan-PSP-BMN
- https://www.scribd.com/document/613652462/Alur-Kerja-Penetapan-Status-Penggunaan
- https://www.scribd.com/document/756618275/Contoh-Format-Surat-Kebenaran-Fotokopi-Dokumen-Kepemilikan
- https://www.scribd.com/doc/217391679/Contoh-Usulan-Penetapan-Status-Penggunaan-Bmn
- https://id.scribd.com/presentation/968615518/BAHAN-PAPARAN-S-165-KN-2024-Detil
- https://www.slideshare.net/slideshow/penetapan-status-penggunaan-bmn-untuk-operasi-pihak-lain-sesuai-pmk-40-2024/286854534
- https://bmnsemarang.wordpress.com/tag/psp-bmn/
- https://bmnpekalongan.wordpress.com/2012/02/14/peraturan-bersama-menteri-keuangan-dan-kepala-badan-pertanahan-nasional-republik-indonesia-nomor-186pmk-062009-nomor-24-tahun-2009-tentang-pensertipikatan-barang-milik-negara-berupa-tanah/

### 7.5 Cara memperlakukan dokumen ini setelah verifikasi

1. Setelah sebuah butir diverifikasi dari teks asli, **ubah labelnya menjadi
   [F]** dan tulis nomor pasalnya.
2. Perbarui `status_verifikasi` pada tabel konfigurasi AMAN yang bersangkutan;
   badge "perlu verifikasi" akan hilang dengan sendirinya di UI.
3. Bila sebuah butir ternyata **salah**, catat koreksinya di sini — jangan
   dihapus diam-diam; jejak kesalahan mencegah kesalahan yang sama masuk lagi
   lewat riset berikutnya.
4. Tambahkan hasil verifikasi ke `docs/PUSTAKA-REGULASI-BMN.md` agar menjadi
   rujukan lintas modul.
