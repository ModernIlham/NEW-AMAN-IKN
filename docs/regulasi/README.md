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
| 6 | PMK 181/PMK.06/2016 | Penatausahaan |
| 7 | PMK 207/PMK.06/2021 | Wasdal |
| 8 | PMK 53 Tahun 2023 | Rezim khusus IKN |
| 9–10 | PP 27/2014 jo. PP 28/2020 | Induk seluruh rezim |
| 11 | KMK 334/KM.6/2021 | Hibah ≤ Rp100 juta tanpa bukti kepemilikan |
| 12 | PMK 4/PMK.06/2015 | Delegasi kewenangan pemindahtanganan |

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

Total saat ini: **46 sumber untuk 12 peraturan**, 9 di antaranya tautan PDF
langsung. Pola unduh langsung JDIH yang berguna saat menambah sumber baru:
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
