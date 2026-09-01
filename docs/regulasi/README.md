# Pustaka teks peraturan primer

Direktori ini menampung **teks hasil ekstraksi PDF peraturan**, diunduh oleh
workflow **Unduh Regulasi** (`.github/workflows/unduh-regulasi.yml`).

## Cara mengisinya

**Actions → "Unduh Regulasi" → Run workflow.**

Hasilnya didorong ke cabang **`regulasi/unduhan`** — bukan ke `main`. Teks
peraturan adalah bahan mentah yang perlu ditelaah dulu; mendorongnya langsung
ke `main` melewati review yang justru paling dibutuhkan di sini.

Sesudah workflow selesai:

```bash
git fetch origin regulasi/unduhan
git checkout regulasi/unduhan -- docs/regulasi
```

## Kenapa lewat runner, bukan langsung

Lingkungan pengembangan Claude Code **tidak bisa** menjangkau satu pun sumber
peraturan. Gerbang egress menjawab **403 pada CONNECT**. Diuji 2026-08-31,
seluruhnya ditolak:

| Host | Jalur | Hasil |
|---|---|---|
| `jdih.kemenkeu.go.id` | curl | 403 CONNECT |
| `peraturan.bpk.go.id` | curl + WebFetch | 403 CONNECT / EGRESS_BLOCKED |
| `djkn.kemenkeu.go.id`, `www.djkn.kemenkeu.go.id` | curl | 403 CONNECT |
| `ppiddjkn.kemenkeu.go.id` | WebFetch | EGRESS_BLOCKED |
| `peraturan.go.id`, `jdihn.go.id`, `sipuu.setkab.go.id` | curl | 403 CONNECT |
| `ngada.org`, `regulasip.id`, `peraturanpedia.id` | curl | 403 CONNECT |
| `scribd.com`, `id.scribd.com`, `media.neliti.com` | curl | 403 CONNECT |
| `web.archive.org`, `archive.org` | curl + WebFetch | 403 CONNECT / ditolak |
| `docs.google.com`, `drive.google.com`, `r.jina.ai` | curl | 403 CONNECT |
| `meridianhukum.com` | WebFetch | EGRESS_BLOCKED |
| `sibangkoman.pu.go.id` | WebFetch | EGRESS_BLOCKED |
| **`en.wikipedia.org`** | WebFetch | EGRESS_BLOCKED |

Wikipedia ikut ditolak — artinya ini **bukan** pemblokiran khusus situs
hukum, melainkan kebijakan egress deny-all untuk web umum. Itu kebijakan
organisasi, **bukan kerusakan**, dan tidak boleh diakali (lihat
`/root/.ccr/README.md`: *"Do not retry or route around it — report the
blocked host"*).

Satu-satunya kanal web yang hidup dari sesi pengembangan adalah **WebSearch**,
yang mengembalikan tautan hasil pencarian + ringkasan mesin pencari —
**bukan** teks primer verbatim. Ringkasan seperti itu tetap bukti sekunder,
persis yang selama ini ditandai `[S]` di `docs/SITASI-DOKUMEN-RESMI.md`.

**Runner GitHub Actions punya egress internet biasa.** Karena itu
pengunduhannya dipindahkan ke sana — bukan mengakali kebijakan, melainkan
memakai jalur yang memang terbuka dan tercatat.

## Yang unduhan ini BUKAN

**Teks yang terunduh adalah BUKTI, bukan kesimpulan.**

Menaikkan butir di `backend/syarat_dokumen_utils.py` dari
`belum_terverifikasi` menjadi `terverifikasi` tetap **langkah sadar setelah
pasalnya dibaca** — bukan akibat otomatis dari berhasilnya sebuah unduhan.
Otomatisasi yang menstempel "terverifikasi" hanya karena PDF-nya masuk akan
menghapus satu-satunya pembeda yang membuat pustaka ini bisa dipercaya.

Uji `test_rezim_penggunaan_setiap_wajibnya_berdasar_pasal` menegakkan batas
itu dari sisi kode; direktori ini menegakkannya dari sisi bukti.

## Hasil putaran pertama (2026-09-01)

**9 dari 12 naskah masuk.** Yang gagal, dan sebabnya:

| Peraturan | Sebab |
|---|---|
| **PMK 111/2016** | Sumbernya mengembalikan **paparan pelatihan DJKN** berjudul sama — bukan batang tubuhnya. Lihat di bawah. |
| PP 27/2014 | BPHN dan BPK menjawab 403 ke runner; `peraturan.go.id` timeout; halaman JDIH tak memuat tautan PDF |
| KMK 334/KM.6/2021 | Halaman JDIH tak memuat tautan PDF; `peraturan.go.id` timeout |

**Temuan terpenting: pola `fulltext` JDIH.** Tujuh unduhan yang berhasil
memakai pola yang bisa ditebak, dan ia kini dipakai lebih dulu untuk ketiga
yang gagal:

```
https://jdih.kemenkeu.go.id/api/download/fulltext/<tahun>/<nomor>~PMK.06~<tahun>Per.pdf
https://jdih.kemenkeu.go.id/api/download/fulltext/<tahun>/<nomor>TAHUN<tahun>PP.pdf
```

### Kegagalan yang paling berbahaya: berhasil dengan isi yang keliru

PMK 111/2016 kembali sebagai PDF **sah**, **berlapis teks**, **ditautkan dari
situs kementerian** — dan lolos setiap guard yang ada. Isinya 29 halaman
slide ber-bullet Wingdings dari `.../pelatihan/uploads/...`: **paparan
tentang** PMK 111, bukan PMK-nya.

Ia akan duduk di direktori ini berbulan-bulan sambil tampak persis seperti
kutipan primer. Ketahuannya hanya karena naskahnya dibaca.

Karena itu ada guard kelima — `bukan_batang_tubuh` — yang menuntut penanda
naskah resmi: **"Menimbang"**, **"MEMUTUSKAN"**, dan **pasal bernomor**.
Diuji terhadap kesepuluh berkas hasil unduhan sungguhan: menolak tepat satu
yang salah, menerima kesembilan yang asli. Sumber `sibangkoman.pu.go.id`
dicabut dari manifes, dan ada uji yang menahannya kembali.

## Unduhan ketiga (2026-09-01) — dan dua cacat pada perkakasnya sendiri

Sumber untuk tiga naskah yang gagal sudah diperbaiki, tetapi ketiganya
**tetap gagal** — dan sebabnya tak bisa dibaca, karena perkakasnya menghapus
buktinya sendiri.

**Cacat 1 — diagnosis run terbaru ditimpa catatan lama.** Penjaga
"pertahankan manifes lama" mempertahankan entri **apa pun keadaannya**,
termasuk yang `berkas`-nya `None`. Akibatnya `percobaan_gagal` lama ikut
bertahan. PMK 111/2016 melaporkan kegagalan sumber yang **sudah dicabut**,
sementara apa yang terjadi pada URL penggantinya hilang tanpa jejak. Satu
putaran penuh terbuang.

Kini entri tanpa berkas **ditulis ulang** dari manifes yang berlaku, dan
bahkan saat berkasnya dipertahankan, `percobaan_gagal` diisi hasil **kali
ini** — provenans berkasnya tetap utuh, diagnosisnya yang diperbarui.

**Cacat 2 — penghitung menggambarkan satu run, bukan keadaan pustaka.**
Unduhan ketiga melaporkan *"berhasil 5, gagal 7"* padahal **sembilan** naskah
ada di direktori: tujuh sumber memang gagal kali itu (JDIH dan BPK banyak
menjawab 403/timeout), tetapi berkas lamanya bertahan sebagaimana mestinya.
Pembacanya akan mengira pustakanya menyusut.

Kini `berhasil`/`gagal` = **keadaan pustaka**; hasil per-run dilaporkan
terpisah sebagai `unduhan_segar`/`unduhan_gagal`.

**Catatan operasional:** JDIH dan BPK tampak membatasi laju. Unduhan ketiga
berjalan 36 menit dengan banyak timeout pada sumber yang sebelumnya lancar.
Menjalankan workflow berturut-turut dalam waktu dekat memperbesar peluang
gagal; beri jeda bila memungkinkan.

## Pola nama berkas JDIH — tiga bentuk, bukan satu

Terungkap bertahap dari unduhan yang berhasil dan yang gagal:

| Jenis | Pola | Contoh |
|---|---|---|
| PMK (lama) | `<nomor>~PMK.06~<tahun>Per.pdf` | `111~PMK.06~2016Per.pdf` |
| PMK (2023+) | `<tahun>pmkeuangan<nnn>.pdf` | `2023pmkeuangan053.pdf` |
| PP | `<nomor>TAHUN<tahun>PP.pdf` | `28TAHUN2020PP.pdf` |
| **KMK** | **`KMK <nomor>~KM.6~<tahun>.pdf`** — ada **spasi**, dan **tanpa** akhiran `Per`/`Kep` | `KMK 128~KM.6~2022.pdf` |

Dua jalur URL: `api/download/fulltext/<tahun>/<berkas>` (bisa ditebak) dan
`api/download/<uuid>/<berkas>` (perlu UUID dari halaman dokumennya).

**Dan dua FORMAT, bukan satu.** Sebagian peraturan hanya ada sebagai
**`.htm`**, tak pernah sebagai `.pdf` — PP 27/2014 salah satunya. Pengunduh
yang cuma menerima PDF tak akan pernah bisa mengambilnya, berapa kali pun
dijalankan. Jenis sumber **`teks`** menangani itu, dan hasilnya justru lebih
bersih: tak ada derau OCR sama sekali.

Bentuk KMK baru ketahuan setelah **tiga tebakan berakhiran `Kep`/`KMK`
semuanya menjawab 404** pada unduhan keempat. Ada uji
(`test_kmk_memakai_pola_nama_berkasnya_sendiri`) yang menahan bentuk yang
sudah terbukti salah itu kembali masuk.

## Unduhan kelima — dan dua cacat pada guard batang tubuh

Sepuluh naskah terunduh segar (jaringan sehat), tetapi ketiga target tetap
gagal. Diagnosisnya — kini bisa dipercaya — menunjukkan **guard-nya sendiri**
yang salah pada satu kasus:

**KMK 213/KM.6/2021 sebenarnya BERHASIL diunduh** dari cermin Itjen Kemhan,
lalu **ditolak** dengan alasan *"tak memuat 'menimbang'"*. Naskahnya benar;
guard-nya yang keliru. Dua sebab:

1. **Pencocokan substring apa adanya.** Ekstraksi PDF hasil pindai menyisipkan
   spasi di tengah kata — teks yang sudah ada di pustaka ini memuat
   *"se bagaimana"*, *"tan pa"*, *"clalam"*, *"MENTERlKEUANGAN"*. Kini spasi
   dibuang seluruhnya sebelum penanda dicocokkan.
2. **Menuntut "Pasal 1" bernomor.** **PERATURAN** memakai pasal; **KEPUTUSAN**
   memakai diktum **KESATU/KEDUA/KETIGA**. Guard lama menolak **setiap KMK** —
   padahal justru KMK yang memuat tata cara pelaksanaan yang didelegasikan PMK.

Diuji ulang terhadap kesepuluh naskah yang sudah ada: semuanya tetap diterima,
dan paparan pelatihan tetap ditolak.

## Unduhan keenam — PP 27/2014 masuk, dan pesan gagal yang buntu

**11 dari 13 naskah kini ada.** PP 27/2014 — peraturan **induk** seluruh
rezim, yang gagal tiga putaran berturut-turut — masuk lewat jenis sumber
`teks`, 112.792 karakter, tanpa derau OCR sama sekali. Bersama PP 28/2020
yang sudah lebih dulu ada, keduanya naik ke `teks-primer` di
`backend/sitasi_regulasi.py`.

Yang tersisa dua, keduanya KMK: **213/KM.6/2021** dan **334/KM.6/2021**.

### Pesan gagal yang tak bisa ditindaklanjuti

Unduhan kelima menolak KMK 213 dengan *"tak memuat 'menimbang'"*. Sesudah
pencocokan spasi diperbaiki, unduhan keenam menolaknya dengan **alasan yang
sama** — dan dari kalimat itu tak ada cara memilih tindak lanjutnya:

| Kalau berkasnya… | Tindak lanjutnya |
|---|---|
| paparan/ringkasan | cabut sumbernya, cari cermin lain |
| kutipan sebagian | cari naskah utuh |
| naskah asli, OCR rusak | perbaiki guard-nya |

Tiga kemungkinan, tiga tindakan berbeda, satu pesan yang tak memisahkannya.
Satu putaran lagi terbuang untuk menebak.

Kini penolakan membawa **jejak apa yang DITEMUKAN**, bukan cuma apa yang
hilang: panjang naskah, penanda mana yang ternyata ada, ada tidaknya
pasal/diktum, dan **kalimat pembukanya** — yang hampir selalu menyebut jenis
dokumennya sendiri.

Bentuknya (ilustrasi, bukan salinan run sungguhan):

```
bukan batang tubuh peraturan — tak memuat 'menimbang' (kemungkinan
paparan/ringkasan tentang peraturannya) | <n> karakter; ada memutuskan;
ada diktum; pembuka: “<kalimat pertama naskah>”
```

Pembukanya sendiri yang menjawab: `KEPUTUSAN MENTERI KEUANGAN ...` berarti
guard-nya yang salah; `Sosialisasi KMK 213 ...` berarti sumbernya. Jejak ini
sengaja dibatasi < 300 karakter — ia ikut ter-commit di `MANIFEST.json`.

## Unduhan ketujuh — dua KMK terakhir, dan sebuah nyaris-kekeliruan

Jejak diagnostik langsung terbayar. KMK 213/KM.6/2021 ditolak dengan:

```
tak memuat 'menimbang' | 469096 karakter; ada memutuskan; ada pasal bernomor;
ada diktum; ada 'menetapkan'; pembuka: “MENTERI KEUANGAN REPUBLIK INDONESIA
BAB I PENDAHULUAN A. Latar Belakang Pada dasarnya, Barang Milik Negara (BMN)
diadaka…”
```

469 ribu karakter yang memuat diktum, "MEMUTUSKAN", "Menetapkan", **dan**
pasal bernomor — tetapi tidak "Menimbang". Itu bukan paparan. Kemungkinan
terbesarnya: OCR yang **menukar huruf**, bukan yang memecah kata. Pembuangan
spasi sudah menangani yang kedua; yang pertama belum pernah terlihat karena
pesan penolakannya tak pernah menyebutkan apa yang ditemukan.

Karena itu jejaknya kini melaporkan **kemiripan**: kata di dalam naskah yang
berjarak dekat dari penanda yang hilang, mis. `'menirnbang'~'menimbang'`
(r-n terbaca m). Kemiripan **dilaporkan, tak pernah meluluskan** — melonggarkan
pencocokan demi OCR membuka jalan yang sama bagi ringkasan.

### Nyaris keliru: nomor sama, peraturan berbeda

Pencarian sumber KMK 334/KM.6/2021 berulang kali menawarkan **KMK
334/KMK.01/2021** — nomor sama, tahun sama, sama-sama tentang pengelolaan BMN,
peraturan yang **berbeda**. Yang satu tata cara hibah kecil; yang lain
pengelolaan BMN di lingkungan Kemenkeu.

`bukan_batang_tubuh` tak bisa menolongnya: dokumen itu peraturan sah yang
berstruktur benar dan akan lolos setiap penjagaan yang ada. Ia akan duduk di
direktori ini dengan nama berkas yang salah — kekeliruan yang lebih mahal
daripada gagal unduh, sebab ia tampak seperti bukti.

Guard keenam, `nomor_tak_cocok`, menuntut naskah menyebut **nomornya sendiri
lengkap dengan serinya** (`334/KM.6/2021`, bukan sekadar "334" dan "2021").
Tahan rusak OCR: PP 28/2020 di pustaka ini menulis tahunnya **"2O2O"** dengan
huruf O, jadi huruf mirip-angka dinormalkan sebelum dicocokkan.

**Batasnya dinyatakan apa adanya:** guard ini membuktikan nomornya *disebut*,
bukan bahwa naskahnya memang peraturan itu — tiap PMK menyebut PP 27/2014 di
bagian Mengingat, jadi penanda PP 27 cocok dengan hampir semua berkas di sini.
Yang ditangkapnya adalah kasus "dokumennya sama sekali lain".

### Pola nama KMK ternyata TIGA bentuk

Tiga putaran menyimpulkan berkas KMK-nya "tidak ada" padahal hanya satu dari
tiga bentuk penamaan yang pernah dicoba:

| Bentuk | Contoh nyata |
|---|---|
| spasi | `KMK 128~KM.6~2022.pdf` |
| tanda hubung | `KMK-216~KM.6~2021.pdf` |
| garis bawah (pemisah `~` pun hilang) | `KMK_33_KM.4_2023.pdf` |

Ditambah **jalur unduh DJKN** yang berbeda dari halaman detail-nya:
`/peraturan/download/<id>/<slug>.html` mengirim berkasnya langsung, sedangkan
`/peraturan/detail/<id>/…` memuatnya lewat JavaScript dan sudah dua putaran
menjawab "halaman tak memuat tautan PDF". Berakhiran `.html` tetapi isinya
PDF — penjaga `%PDF` memeriksa isi, bukan nama berkas.

### Rujukan sekunder untuk KMK 334

KMK 334/KM.6/2021 **tidak terindeks** di bagian peraturan DJKN. Sampai
naskahnya masuk, uraian tata caranya ada di artikel KPPN Lubuk Sikaping
(DJPb Kemenkeu): *"Tata Cara Hibah Barang Milik Negara (BMN) Selain Tanah
dan/atau Bangunan yang Tidak Memiliki Bukti Kepemilikan dengan Nilai Perolehan
Sampai dengan Rp100.000.000"*. Ia **rujukan, bukan naskah** — tak boleh masuk
pustaka ini, dan `bukan_batang_tubuh` memang akan menolaknya.

## Unduhan kedelapan — dugaan OCR terbantah, dan dua tingkat baru

Jalur unduh DJKN **berhasil**: `download/411` mengembalikan berkas yang sama
persis dengan cermin Itjen Kemhan — 469.096 karakter, dua sumber resmi yang
saling bebas. Berkasnya bukan masalah.

Dan laporan kemiripan **membantah dugaan sebelumnya**. Yang ditemukan bukan
"Menimbang" yang rusak OCR, melainkan `'menyimpang'` dan `'membangu'` — kata
Indonesia biasa. Jadi naskah itu memang **tidak memuat "Menimbang" sama
sekali**, dan hipotesis putaran lalu keliru. Itulah gunanya jejak diagnostik:
ia tak cuma mempercepat tebakan yang benar, ia menutup tebakan yang salah.

### Bentuk `lampiran`

Naskah itu adalah **lampiran** KMK 213/KM.6/2021 — dibuka "BAB I
PENDAHULUAN", memuat MEMUTUSKAN, Menetapkan, diktum, dan pasal bernomor.
Konsiderans tinggal di halaman diktum yang terbit terpisah. Menuntut
"Menimbang" pada berkas semacam itu berarti menolak satu-satunya naskah yang
tersedia — dan justru lampiran itulah yang memuat tata caranya.

Kelonggarannya **per-entri, bukan berlaku umum**, dan tetap berlapis:

| Syarat | Tetap ditagih? |
|---|---|
| "Menimbang" | tidak, untuk bentuk `lampiran` |
| "MEMUTUSKAN" | ya |
| BAB bernomor romawi | ya |
| pasal bernomor atau diktum | ya |
| menyebut nomornya sendiri | ya (`nomor_tak_cocok`) |

Diuji: paparan pelatihan tetap ditolak walau ditandai `lampiran`, dan paparan
yang **mengutip** "MEMUTUSKAN" + "BAB I" + "Pasal 1" lolos guard bentuk
tetapi tertahan guard nomor. Satu uji menahan agar penandaan ini tetap satu
pengecualian yang bisa ditunjuk, bukan kebiasaan baru.

### Jalur `baca/` DJKN, dan urutan yang menentukan

DJKN ternyata punya **tiga** jalur untuk satu peraturan:

| Jalur | Hasil |
|---|---|
| `/peraturan/detail/<id>/…` | halaman JavaScript, dua putaran gagal |
| `/peraturan/download/<id>/…` | berkasnya langsung — tetapi lampirannya saja |
| `/peraturan/baca/<id>/…` | belum dicoba; mungkin dokumen yang utuh |

**Urutan sumber adalah preferensi.** `unduh_satu` berhenti pada sumber
pertama yang lolos penjagaan, jadi sumber baru yang ditaruh di belakang
sumber yang sudah terbukti berhasil **tak akan pernah dicoba** — ia mati
diam-diam, dan manifesnya tak menyebutkannya sama sekali. Cermin Kemhan
sudah terbukti berhasil, jadi `baca/` didahulukan dan Kemhan jadi jaring
pengaman. Ada uji yang menahan urutan itu.

Satu URL kini boleh muncul dua kali dengan jenis berbeda: `html` mencari
tautan berkas di halamannya, `teks` memperlakukan halamannya sendiri sebagai
naskah — halaman yang memuat naskah langsung (seperti PP 27/2014) hanya
terjangkau lewat yang kedua. Yang tetap dilarang adalah pasangan
(jenis, url) yang identik, sebab itu percobaan yang benar-benar terbuang.

### Tingkat `rujukan` — uraian TENTANG peraturan

KMK 334/KM.6/2021 **tidak terindeks** di bagian peraturan DJKN, dan sepuluh
sumber unduhnya menjawab 404. Yang paling dekat adalah uraian dari unit
Kemenkeu sendiri (artikel KPPN Lubuk Sikaping, DJPb).

Ia disimpan — tetapi tak boleh menyamar jadi naskah:

- berkasnya berawalan **`rujukan-`**, terbaca dari namanya saja;
- penghitungnya **terpisah** (`rujukan_ada`/`rujukan_belum`), supaya pustaka
  tak terbaca membesar tanpa satu pun peraturan baru terbaca;
- ada uji yang menahannya menjadi dasar status `teks-primer` di
  `backend/sitasi_regulasi.py`.

Guard-nya melonggar pada bentuk, **tidak** pada sasaran: rujukan tetap wajib
menyebut nomor peraturannya dan tetap ditolak bila terlalu pendek — halaman
galat dan menu navigasi juga "bukan batang tubuh".

### PMK 115/2020 memang tak memuat daftar dokumennya

Ditelusuri langsung di naskah primer yang sudah ada di sini (OCR menulisnya
"Pasal96" tanpa spasi, itu sebabnya luput dari pencarian sebelumnya):

> **Pasal 96** — *Ketentuan lebih lanjut mengenai tata cara pelaksanaan
> Pemanfaatan BMN ditetapkan dengan Keputusan Menteri Keuangan yang
> ditandatangani oleh Direktur Jenderal atas nama Menteri Keuangan.*

Dua frasa "dengan melampirkan" di PMK 115/2020 (Pasal 101 dan 102) mengatur
**persetujuan surut** KSP dan BGS/BSG yang sudah terlanjur terjadi — bukan
daftar dokumen permohonan. Jadi sewa dan pinjam pakai tetap
`belum_terverifikasi` sampai KMK 213 masuk; tak ada jalan pintas lewat
PMK-nya.

## Unduhan kesembilan — pustaka selesai untuk keperluannya

**12 dari 13 naskah primer + 1 rujukan.** Yang menang untuk KMK 213 adalah
jalur **`baca/411`** — bentuk ketiga DJKN yang baru dicoba putaran ini.
Berkasnya lampiran KMK-nya, 470 KB, tujuh BAB.

Yang penting bukan angkanya, melainkan apa yang dibuka olehnya:

| BAB | Isi | Menutup |
|---|---|---|
| III | Tata Cara Pelaksanaan Sewa | rezim `sewa` |
| IV | Tata Cara Pelaksanaan Pinjam Pakai | rezim `pinjam_pakai` |

Kedua rezim terakhir di `backend/syarat_dokumen_utils.py` naik ke
berdasar-pasal. **Keempat belas rezim kini berdasar pasal** — sesuatu yang
sembilan putaran unduhan lalu tampak tak mungkin, sebab lingkungan
pengembangan ini tak bisa menjangkau satu pun sumber peraturan.

### Yang tersisa

Naskah asli **KMK 334/KM.6/2021** tetap tak ditemukan: ia tak terindeks di
bagian peraturan DJKN, dan sepuluh sumber unduhnya menjawab 404. Yang ada
adalah rujukan sekunder — uraian dari KPPN Lubuk Sikaping (DJPb) — yang
**tidak** boleh menjadi dasar `terverifikasi`.

Itu bukan kegagalan yang menghalangi apa pun: rezim `hibah` sudah berdasar
pasal lewat PMK 111/2016 Pasal 93 & 95. KMK 334 hanya mengatur jalur khusus
hibah ≤ Rp100 juta tanpa bukti kepemilikan.

**Keterbatasan berkas rujukan.** `teks_dari_html` mengambil seluruh halaman,
jadi berkas `rujukan-*.txt` ikut memuat menu navigasi situsnya. Isi
substantifnya tetap utuh dan bisa di-`grep`; ia sengaja tidak dibersihkan,
sebab penyaring yang menebak "bagian mana yang artikel" bisa membuang justru
kalimat yang dicari. Untuk naskah primer masalah ini tak muncul — halaman
`fulltext` JDIH memang hanya berisi naskahnya.

## Isi

- `<kode>.txt` — teks batang tubuh hasil ekstraksi
- `MANIFEST.json` — untuk tiap berkas: **sha256, ukuran, jumlah halaman, URL
  yang berhasil, waktu unduh, dan seluruh percobaan yang gagal**

Percobaan yang gagal sengaja disimpan: itulah yang memberi tahu URL mana yang
perlu diganti pada putaran berikutnya.

PDF aslinya **tidak** disimpan — besar dan tak bisa di-`diff`. Yang disimpan
teksnya, yang bisa di-`grep` saat menelusuri satu pasal.

## Daftar target

Urutan prioritas mengikuti celah terbesar di registry syarat dokumen.
Sumbernya ada di `scripts/regulasi_sumber.py`.

| # | Peraturan | Menutup celah |
|---|---|---|
| 1 | PMK 111/PMK.06/2016 | Hibah, penjualan, tukar menukar, PMPP |
| 2 | PMK 165/PMK.06/2021 | Perubahan atas 111/2016 |
| 3 | PMK 83/PMK.06/2016 | Penghapusan & pemusnahan |
| 4 | PMK 115/PMK.06/2020 | Sewa, pinjam pakai, KSP, BGS/BSG |
| 5 | PMK 40 Tahun 2024 | Penggunaan — menutup rantai bukti riset yang sudah ada |
| 6 | KMK 213/KM.6/2021 | Sewa & pinjam pakai — tata cara yang didelegasikan PMK 115/2020 Pasal 96 |
| 7 | PMK 181/PMK.06/2016 | Penatausahaan |
| 8 | PMK 207/PMK.06/2021 | Wasdal |
| 9 | PMK 53 Tahun 2023 | Rezim khusus IKN |
| 10–11 | PP 27/2014 jo. PP 28/2020 | Induk seluruh rezim |
| 12 | KMK 334/KM.6/2021 | Hibah ≤ Rp100 juta tanpa bukti kepemilikan |
| 13 | PMK 4/PMK.06/2015 | Delegasi kewenangan pemindahtanganan |

Tiap peraturan punya **beberapa** sumber, dicoba berurutan: URL JDIH berubah
saat situsnya diperbarui, dan cermin kementerian lain (Pertanian, PUPR, BP
Batam, BPHN) memuat salinan PDF yang sama serta jauh lebih stabil karena ia
berkas statis.

**Dua aturan yang dijaga uji**, bukan sekadar niat baik:

- `test_tak_ada_peraturan_yang_bersumber_tunggal` — ambangnya **nol**.
- `test_ada_cermin_di_luar_dua_host_utama` — tiap peraturan wajib punya
  minimal satu sumber di luar `jdih.kemenkeu.go.id` dan
  `peraturan.bpk.go.id`. Kalau seluruh sumber ada di dua host itu saja, satu
  gangguan di sisi Kemenkeu/BPK menjatuhkan semuanya sekaligus.

Total saat ini: **72 sumber untuk 13 peraturan primer + 1 rujukan**,
20 di antaranya tautan PDF langsung. Pola unduh langsung JDIH yang berguna saat menambah sumber baru:
`https://jdih.kemenkeu.go.id/api/download/<uuid>/<nomor>~PMK.06~<tahun>Per.pdf`,
dan BPHN memakai pola nama berkas yang bisa ditebak untuk PP:
`https://bphn.go.id/data/documents/<yy>pp<nnn>.pdf`.

## Kalau sebuah peraturan tetap gagal

`MANIFEST.json` mencatat sebabnya per URL. Tiga pola yang lazim:

1. **404 / host mati** → cari cermin baru, tambahkan ke
   `scripts/regulasi_sumber.py`, jalankan ulang.
2. **"PDF tanpa lapisan teks"** → PDF hasil pindai. Perlu OCR; sengaja
   **ditolak**, sebab berkas `.txt` kosong yang tersimpan akan terlihat
   seperti bukti padahal tak memuat apa pun.
3. **"halaman tak memuat tautan PDF"** → situsnya memuat berkas lewat
   JavaScript. Buka halamannya di peramban, salin URL PDF sebenarnya, dan
   tambahkan sebagai sumber bertipe `pdf`.
