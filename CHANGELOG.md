# Changelog — AMAN IKN

Catatan perubahan aplikasi **AMAN** (Aplikasi Manajemen Aset Negara) IKN, dari
awal pengembangan di branch ini hingga rilis terakhir. Diurutkan dari yang
**terbaru** ke yang **terlama**. Setiap entri merujuk ke nomor Pull Request
(`#n`) dan commit pada branch `main`.

> Format tanggal: `YYYY-MM-DD`. Semua perubahan UI di bawah sudah di-`yarn build`
> (craco) hingga sukses sebelum di-merge.

---

## ⚠️ Catatan teknis penting — aturan tap-target 44px global

Banyak bug tata letak di layar kecil (PR #7, #9, #11 — dan berpotensi muncul lagi)
berakar dari **satu** aturan global di `frontend/src/index.css`:

```css
/* Mobile touch targets */
@media (max-width: 1023px) {
  button, a { min-height: 44px; min-width: 44px; }
}
```

Aturan ini bagus untuk tombol berdiri sendiri (target sentuh WCAG ~44px), tetapi
**memaksa SETIAP `<button>`/`<a>` di ≤1023px menjadi minimal 44×44px** — termasuk:

- baris ikon padat (footer kartu galeri),
- badge berbentuk tombol (ribbon status kegiatan),
- kontrol kecil seperti `Switch` (Radix `Switch` merender sebuah `<button>`).

Akibatnya elemen-elemen itu membengkak → meluber, terpotong, atau menutupi
elemen lain — **hanya** di ≤1023px (di atas itu aturan mati, jadi terlihat normal).

### Pola perbaikan baku

Tambahkan utility **`min-w-0 min-h-0`** pada elemen yang terdampak. Selector
class (`.min-w-0` = `0,0,1,0`) menang atas selector tipe (`button` = `0,0,0,1`),
jadi override-nya pasti berlaku tanpa `!important`. Gunakan ini untuk:

- ikon-tombol di dalam strip/baris padat,
- badge/ribbon yang kebetulan berupa `<button>`,
- `Switch`/kontrol kecil yang tak boleh ikut 44px.

> Jika nanti ada lagi elemen mobile yang "tiba-tiba kebesaran/menutupi" di
> ≤1023px, **cek dulu apakah itu `<button>`/`<a>`** — kemungkinan besar penyebabnya
> aturan ini. Solusinya `min-w-0 min-h-0` (dan kalau perlu `leading-none`).

---

## [#216] Ekspor CSV checklist pengamanan (Pengamanan) — 2026-07-13

- **Ekspor CSV** checklist pengamanan per aset (`GET
  /pengamanan/checklist/export`) — melengkapi ekspor register modul
  Pengamanan (kini kasus #213, polis #205, dokumen #214, **checklist**
  semua ber-CSV). Kolom: identitas aset, jenis objek (label:
  Tanah/Gedung/Kendaraan/lainnya), terpenuhi, total butir, persen,
  **butir_belum** (label butir yang belum terpenuhi, dipisah "; " sebagai
  bahan tindak lanjut), keterangan, tanggal cek, petugas. Helper murni
  `baris_csv_checklist` (skor via `skor_checklist`, tanpa Mongo, teruji
  unit) + tombol unduh CSV di panel "Checklist Pengamanan per Aset"
  (muncul saat ada data). Baca-saja, alat bantu internal (pustaka §11.2).
  Unit test +1 → 277 passed.

## [#215] Satukan toggle Analytics/Rekapitulasi/Barang Serupa jadi satu baris — 2026-07-13

- **Inventarisasi Aset** — tiga panel di atas baris data (**Dashboard
  Analytics**, **Rekapitulasi Inventarisasi**, **Barang Serupa**) yang
  sebelumnya bertumpuk vertikal (tiga bar ~120px) kini disatukan menjadi
  **satu kontrol segmented menyamping** — satu kartu utuh ber-divider,
  bukan tiga tombol/kartu terpisah. Segmen aktif diberi warna (biru untuk
  Analytics/Rekapitulasi, ungu untuk Barang Serupa) + chevron; badge
  jumlah (mis. "163 BMN", "N grup") tetap tampil di segmennya.
- Berlaku **seragam di semua viewport** (desktop, tablet, HP) — menghemat
  ruang vertikal dan **memperlebar area data**. Isi panel dirender di
  bawah baris kontrol saat segmennya dibuka (mode *embedded*: panel hanya
  merender konten, header jadi segmen). Pegangan geser-tinggi grafik
  Analytics dipindah ke tepi bawah kartunya.
- Teknis: komponen `PanelSegment` baru di `DashboardPage`; `AnalyticsPanel`
  / `RekapitulasiPanel` / `AssetGroupsPanel` menerima prop `embedded`
  (+ callback `onTotal`/`onCount` untuk badge). Menggantikan baris chip
  mobile lama. `eslint` bersih; `CI=false yarn build` sukses.

## [#214] Ekspor CSV arsip dokumen kepemilikan (Pengamanan) — 2026-07-13

- **Ekspor CSV** arsip dokumen kepemilikan (`GET
  /pengamanan/dokumen/export`), melengkapi pola ekspor register di modul
  Pengamanan (setelah polis #205 & kasus #213). Kolom: identitas aset,
  jenis (label: sertipikat/BPKB/STNK/IMB-PBG/perolehan/lainnya), nomor,
  atas nama, lokasi simpan (label Pengelola/Pengguna Barang), kategori
  sertipikasi (label K1–K4/SHP, untuk jenis sertipikat), berlaku sampai,
  **status berlaku** (Berlaku / Kedaluwarsa dihitung dari tanggal vs hari
  ini; kosong bila tanpa masa berlaku), jumlah lampiran, keterangan,
  pembuat. Helper murni `baris_csv_dokumen` (tanpa Mongo, teruji unit) +
  tombol unduh CSV di panel "Arsip Dokumen Kepemilikan" (muncul saat ada
  dokumen). Baca-saja. Unit test +1 → 276 passed. Dasar PP 27/2014 Ps. 43.

## [#213] Ekspor CSV register kasus BMN bermasalah (Pengamanan) — 2026-07-13

- **Ekspor CSV** register kasus/sengketa BMN bermasalah (`GET
  /pengamanan/kasus/export`), melengkapi pola ekspor register di modul
  Pengamanan (setelah polis #205). Kolom: identitas aset (kode/NUP/nama/
  lokasi), kategori (label: dikuasai pihak lain / tumpang tindih
  sertipikat / berperkara), status (label: identifikasi → mediasi →
  blokir → litigasi → selesai), uraian, pihak lawan, nomor perkara,
  pendamping, tanggal dibuat & diperbarui, pembuat. Helper murni
  `baris_csv_kasus` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel "Register BMN Bermasalah" (muncul saat ada kasus). Baca-saja,
  bahan laporan wasdal/CaLBMN. Unit test +1 → 275 passed.

## [#212] Ekspor CSV register tiket BMN idle (Penggunaan) — 2026-07-13

- **Ekspor CSV** register tiket penanganan BMN idle (`GET
  /penggunaan/idle/export`), melengkapi pola ekspor register. Kolom:
  identitas aset, alasan indikasi idle, status (label:
  klarifikasi/digunakan kembali/usul serah/diserahkan), nomor usulan
  penyerahan, nomor BAST serah, keterangan, pembuat, tanggal dibuat.
  Helper murni `baris_csv_idle` (tanpa Mongo, teruji unit) + tombol unduh
  CSV di panel "BMN Idle — Daftar Pantau" (muncul saat ada tiket).
  Baca-saja. Unit test +1 → 274 passed. Dasar PMK 120/2024.

## [#211] List mode: auto-pindah halaman saat lewati baris terakhir + area data lebih luas (desktop) — 2026-07-13

- **List (tabel) mode — auto-pindah halaman:** saat menekan Simpan/Update
  pada **baris terakhir** halaman tabel desktop sementara masih ada
  halaman berikutnya, aplikasi kini **otomatis berpindah ke halaman
  berikutnya** (kontrol paginasi + tabel ikut geser) lalu membuka baris
  **pertama**-nya untuk diedit — ritme input tak lagi mentok di halaman
  lama. `doFetch`/`goToPage` mengembalikan baris halaman baru; navigasi
  memilih `goToPage` (mode list ≥lg) vs infinite scroll (galeri/kartu HP).
- **Area data lebih luas (desktop):** kartu statistik atas (Total Aset /
  Nilai / Aktif / Maintenance) dibuat **ringkas satu baris** (label–nilai
  sejajar, padding & ukuran font lebih kecil) dan jarak antar-seksi header
  dipadatkan khusus `lg` — memberi porsi layar lebih besar untuk baris
  data. Tampilan tablet/HP tak berubah.

## [#210] Ekspor CSV register pemantauan insidentil Wasdal — 2026-07-13

- **Ekspor CSV** register pemantauan insidentil wasdal (`GET
  /wasdal/insidentil/export`), melengkapi ekspor register Wasdal
  (penertiban #207). Kolom: pemicu (label), tanggal mulai, lokasi, objek
  pemantauan (label), uraian, status, **tenggat aktif** + **status
  tenggat** (Lewat tenggat / "N hk lagi" per tahap pelaksanaan/lapor /
  Selesai, dihitung via `info_tenggat_insidentil`), nomor & tanggal BA,
  hasil, tanggal lapor, keterangan lapor, pembuat. Helper murni
  `baris_csv_insidentil` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel pemantauan insidentil. Baca-saja. Unit test +1 → 273 passed.
  Dasar PMK 207/2021 (pelaksanaan ≤10 hk, lapor ≤5 hk sejak BA).

## [#209] Galeri: infinite scroll dua arah + jaga aset terseleksi terlihat — 2026-07-13

- **Scroll dua arah (muat halaman sebelumnya):** bila pengguna berada di
  halaman tabel yang jauh (mis. halaman 5) lalu beralih ke mode galeri,
  kini **scroll ke atas otomatis memuat halaman sebelumnya** (4, 3, 2, 1)
  dan scroll ke bawah memuat berikutnya — data tetap **urut & sesuai
  filter**. Sebelumnya galeri hanya menampilkan halaman masuk dan halaman
  yang lebih kecil tak terjangkau. Diperbaiki bug `doFetch` yang mereset
  jendela galeri ke halaman 1; ditambah state `mobileFirstPage`,
  `loadPrevMobile` (prepend + paritas offline), sentinel atas
  IntersectionObserver, dan **penjangkaran posisi scroll saat prepend**
  (useLayoutEffect) agar tampilan tak "melompat".
- **Aset terseleksi selalu terlihat:** saat aset yang diedit berganti
  (mis. auto-lanjut setelah simpan), galeri/kartu kini **otomatis
  menggulir kartu aset tersebut ke tengah layar** (`scrollToIndex`) —
  tak perlu mencari lagi. Hanya saat aset aktif berubah, tidak melawan
  gulir manual pengguna.

- **Ritme input tak putus lintas halaman:** saat menekan Simpan/Update pada
  aset **terakhir yang dimuat** sementara masih ada halaman berikutnya,
  aplikasi kini otomatis memuat halaman berikutnya lalu membuka aset
  **pertama**-nya untuk diedit — tak lagi berhenti/menutup form di baris
  terakhir. Berlaku di form penuh, sheet inventarisasi cepat, dan Mode
  Kamera (tombol ▶). `loadMoreMobile` mengembalikan baris baru (menghindari
  masalah closure basi); gerbang tombol memakai `hasMoreToLoad`
  (`mobileCurrentPage < totalPages`); aset baru dikunci seperti navigasi
  biasa. Di tabel (≥lg) tak mengubah paginasi; di galeri/kartu memakai
  infinite scroll yang sama.
- **Galeri auto-muat lebih sigap:** pemicu "muat lebih banyak" diganti dari
  pengecekan indeks baris virtual (baru ter-mount saat mepet bawah) menjadi
  **IntersectionObserver** pada sentinel nyata dengan **prefetch 600px** —
  daftar termuat otomatis SAAT gulir *hampir* sampai bawah, terasa lebih
  cepat. Ditambah `overscroll-behavior: contain` agar momentum gulir tak
  bocor ke halaman (mengunci kepemilikan scroll di kontainer galeri).

- **Ekspor CSV** register penertiban wasdal (`GET
  /wasdal/penertiban/export`), melengkapi pola ekspor register. Kolom:
  sumber (label), tanggal dasar, tenggat, **status tenggat** (Selesai /
  Lewat tenggat / "N hk lagi" dihitung dari `status_tenggat_penertiban`),
  status, objek pemantauan (label), uraian, tindak lanjut, tanggal
  selesai, identitas aset tertaut (opsional), pembuat. Helper murni
  `baris_csv_penertiban` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel penertiban (muncul saat ada data). Bersifat baca-saja. Unit test
  +1 → 272 passed. Dasar PMK 207/2021 (tenggat 15 hari kerja).

## [#206] Perbaiki: Simpan di mode galeri halaman 2+ menutup form & reload — 2026-07-13

- **Bug:** di tampilan **mode galeri** inventarisasi aset, menekan
  "Simpan" pada baris di **halaman kedua dan seterusnya** (hasil infinite
  scroll) membuat panel edit menutup sendiri dan daftar seolah dimuat
  ulang — padahal di halaman pertama Simpan lancar melanjutkan ke aset
  berikutnya. Terjadi di tablet/HP dan layout kartu.
- **Sebab:** galeri/kartu merender `mobileAssets` (superset infinite
  scroll), tetapi gerbang tombol Simpan + navigasi (`editAssetIndex`,
  `totalAssetsInView`, `handleSaveAndNavigate`) membaca `assets` yang
  **beku di halaman 1**. Baris halaman 2+ tak ditemukan di `assets`
  (indeks −1) → gerbang gagal → Simpan jatuh ke jalur tutup-form yang
  memicu `refreshData()` sehingga daftar kolaps ke halaman 1.
- **Perbaikan:** samakan indeks, jumlah, dan navigasi form agar semua
  membaca `mobileAssets` (di tabel ≥lg isinya sama dengan halaman aktif,
  jadi perilaku desktop tak berubah). Kini Simpan di galeri halaman 2+
  lanjut ke aset berikutnya tanpa menutup form / reload daftar.

## [#205] Ekspor CSV register polis asuransi BMN (Pengamanan) — 2026-07-13

- **Ekspor CSV** register polis asuransi BMN (`GET
  /pengamanan/polis/export`), melengkapi pola ekspor register. Kolom:
  identitas aset, nomor polis, penanggung, kategori objek & sumber dana
  premi (label terbaca), nilai pertanggungan & premi (rupiah bulat),
  masa berlaku (mulai–berakhir), status masa berlaku + sisa hari
  (dihitung via `info_polis`), keterangan, pembuat. Helper murni
  `baris_csv_polis` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel polis (muncul saat ada data). Bersifat baca-saja. Unit test +1
  → 271 passed.

## [#204] Ekspor CSV register koreksi nilai (Penilaian) — 2026-07-13

- **Ekspor CSV** register koreksi nilai/hasil penilaian (`GET
  /penilaian/koreksi/export`), melengkapi pola ekspor register yang sudah
  ada (pemanfaatan/pemeliharaan/pemindahtanganan/pemusnahan/pengadaan/
  penganggaran/penghapusan). Kolom: identitas aset, jenis & dokumen
  (label terbaca), nomor & tanggal dokumen, nilai lama→baru + selisih
  (rupiah bulat, konsisten), dampak masa manfaat, penilai, status SAKTI,
  catatan, pembuat. Helper murni `baris_csv_koreksi` (tanpa Mongo, teruji
  unit) + tombol unduh CSV di panel koreksi (muncul saat ada data).
  Unit test +1 → 270 passed.

## [#203] Riwayat nilai per aset (Penilaian) — 2026-07-13

- **Riwayat Nilai per Aset** (read-only) di halaman Penilaian: cari satu
  aset lalu lihat jejak kronologis nilainya — **perolehan** (dari
  `purchase_date` + `purchase_price`) → tiap **koreksi/revaluasi** (LHIP/
  BA/Laporan Penilaian, urut tanggal dokumen) → **nilai terkini**. Nilai
  terkini mengikuti koreksi non-informasional terakhir; koreksi
  "penilaian tujuan tertentu" ditandai **informasional** dan tidak
  mengubah nilai buku. Endpoint `GET /penilaian/riwayat-nilai/{asset_id}`
  + helper murni `susun_riwayat_nilai` (tanpa Mongo, teruji unit). Tidak
  ada mutasi data — hanya menyusun ulang catatan yang sudah ada. Unit
  test +1 → 269 passed. Melengkapi butir "menyusul" pada modul Penilaian.

## [#202] Filter rentang waktu pakai tanggal beli (+ peta) — 2026-07-12

- **Filter rentang tanggal** di daftar inventarisasi aset kini menyaring
  berdasarkan **tanggal beli** (`purchase_date`), bukan tanggal input
  (`created_at`). Karena builder query dipakai bersama `/assets` + ekspor
  geo, dan peta memakai `buildParams` + `clientFilter` yang sama,
  **peta ikut tersaring**. Param → `beli_dari/beli_sampai` (batas atas
  inklusif); label UI "Tanggal Input" → "Tanggal Beli"; aset tanpa
  tanggal beli keluar saat rentang diisi; indeks `purchase_date` ditambah.

## [#201] Saran jenjang persetujuan Pemindahtanganan — 2026-07-12

- **Saran jenjang persetujuan (indikatif)** dari jenis BMN + nilai wajar:
  Pengelola Barang (≤Rp10 M) / Presiden (>10–100 M) / DPR (>100 M) untuk
  selain tanah/bangunan; tanah/bangunan umum → DPR, terkecuali Ps. 55(2)
  ikut nilai; PMPP lantai Presiden; hibah ≤Rp100 jt catatan Pengguna
  Barang (UU 1/2004 Ps. 45–46 + PP 27/2014). **Tidak memblok** — panduan
  saja. Pustaka §7 + verifikasi §14 no. 25. Unit test +1 → 251 passed.

## [#200] Konsolidasi dokumentasi #199 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + masterplan + pustaka §13
  baris Pengadaan (✅ tautan paket → Penganggaran #199; butir "menyusul"
  tautan paket ke register penganggaran tuntas).

## [#199] Tautan Pengadaan → usulan Penganggaran — 2026-07-12

- **Jembatan #117 ↔ #115**: register perolehan Pengadaan dapat ditautkan
  ke usulan Penganggaran (field `penganggaran_id` + snapshot uraian/nomor
  DIPA/tahun). Endpoint `POST /pengadaan/{id}/penganggaran` (tautkan/lepas);
  dropdown di form + baris info di register; kolom penganggaran + DIPA di
  CSV. Referensi lunak (tak memvalidasi nilai). Unit test +1 → 250 passed.

## [#198] Konsolidasi dokumentasi #197 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5–6 + masterplan + pustaka
  §13 baris Penghapusan (✅ Jejak Aset Terhapus #197 — butir "menyusul"
  arsip aset terhapus tuntas).

## [#197] Jejak Aset Terhapus (arsip read-only) — 2026-07-12

- **Aset yang dihapus permanen kini tetap tertelusur**: endpoint
  read-only `GET /audit-logs/aset-terhapus` (dari log audit; kode/NUP/
  nama/nilai perolehan/oleh/waktu, rekap jumlah + total nilai) + seksi
  "Jejak Aset Terhapus" di halaman Penghapusan. Tidak mengubah mekanisme
  hapus/offline-sync. Unit test +1 → 249 passed. Butir "menyusul"
  Penghapusan (arsip aset terhapus) tuntas.

## [#196] Peta: zoom maksimal dinaikkan ke 22 — 2026-07-12

- **Peta full-view** kini bisa diperbesar hingga zoom 22 (dari 19):
  `maxNativeZoom: 19` + `maxZoom: 22` pada TileLayer & objek peta →
  Leaflet memperbesar ubin OSM z19 pada z20–22, sehingga pin aset yang
  berdekatan dapat dipisahkan lebih presisi saat diperbesar. Auto-fit
  dibatasi z19 agar tampilan awal tetap tajam.

## [#195] Konsolidasi dokumentasi #194 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + masterplan + pustaka §13
  baris Penggunaan (✅ alur pengajuan PSP #194 — daftar "menyusul"
  Penggunaan tuntas).

## [#194] Alur pengajuan PSP berstatus — 2026-07-12

- **Alur pengajuan PSP** (butir "menyusul" terakhir Penggunaan): usulan
  dapat dibuat sebagai draf tanpa SK → diajukan → ditetapkan (nomor/
  tanggal SK wajib saat itu) / ditolak / dikembalikan (catatan wajib).
  Kompatibel mundur (SK lama tanpa status = ditetapkan); cakupan aset
  ter-PSP & BAST PDF hanya untuk yang ditetapkan; anti-balapan +
  riwayat. UI: checkbox draf + badge status + tombol transisi. Unit
  test +2 → 248 passed. **Daftar "menyusul" Penggunaan tuntas.**

## [#193] Konsolidasi dokumentasi #192 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + masterplan + pustaka §13
  baris Penggunaan (✅ BAST PSP PDF #192; sisa "menyusul" = alur
  pengajuan PSP berstatus).

## [#192] BAST penetapan status penggunaan PDF — 2026-07-12

- **BAST digital penetapan PSP**: PDF siap tanda tangan per SK dari
  register SK PSP (#129) — kop surat, narasi dasar SK (PMK 40/2024),
  tabel aset, tanda tangan pihak menyerahkan/menerima + KPB (pola BA
  pemusnahan #119; data murni register). Tombol unduh per SK di halaman
  Penggunaan; smoke test PDF lolos. Sisa "menyusul" Penggunaan: alur
  pengajuan PSP berstatus.

## [#191] Konsolidasi dokumentasi #190 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 butir Pemanfaatan
  (+ atribut fasilitas transaksi #190; daftar "menyusul" tuntas).

## [#190] Koreksi PMK 18/2024 + atribut fasilitas transaksi — 2026-07-12

- **Koreksi regulasi (riset)**: PMK 18/2024 = "Tata Cara Pemberian
  Fasilitas Penyiapan & Pelaksanaan Transaksi Pemanfaatan BMN"
  (pendampingan DJPPR, analog PDF KPBU) — BUKAN bentuk pemanfaatan ke-7;
  khusus IKN berlaku PMK 139/PMK.08/2022 (PT PII). Salah kaprah "bentuk
  PDF" dikoreksi di pustaka (sub-bab §6.a baru + butir verifikasi 24),
  masterplan, dan bmnModules.
- **Fitur**: atribut fasilitas transaksi opsional pada register
  perjanjian (dasar/nomor penetapan/pelaksana) — hanya KSP/BGS-BSG,
  nomor penetapan wajib bila ber-fasilitas; kolom CSV + blok form baru.
  Daftar "menyusul" Pemanfaatan tuntas. Unit test +1 → 246 passed.

## [#189] Konsolidasi dokumentasi #188 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 + tabel modul & roadmap
  masterplan (Pemanfaatan "Lengkap tahap awal") + pustaka §13 baris
  Pemanfaatan (✅ lampiran wasdal #188; "menyusul" tinggal PDF PMK
  18/2024).

## [#188] Lampiran wasdal per perjanjian pemanfaatan — 2026-07-12

- **Arsip lampiran wasdal terpisah** per perjanjian pemanfaatan: laporan
  monitoring/BA peninjauan lapangan (5 objek pemantauan KPB, pustaka §8)
  di array `lampiran_wasdal` + trio endpoint GridFS `/wasdal` — terpisah
  dari dokumen perjanjian (#131). Logika lampiran direfaktor jadi helper
  bersama; kolom `jumlah_lampiran_wasdal` di CSV; tombol "Wasdal" +
  dialog dua jenis di halaman Pemanfaatan. Butir "menyusul" Pemanfaatan
  tinggal PDF PMK 18/2024.

## [#187] Konsolidasi dokumentasi #186 + perapian status modul — 2026-07-12

- **Dokumentasi + data statis modul**: README Progres Fase 4 & masterplan
  (Penganggaran "Lengkap tahap awal", daftar "menyusul" tuntas #186);
  perapian baris pustaka §13 yang basi (Pemeliharaan #90/#91/#167,
  Pemanfaatan #121/#131/#158, Pemusnahan #119/#120/#132, Penghapusan
  #106/#134/#159); bmnModules: butir tiket proses 4 rezim (#181/#183)
  masuk checklist Penggunaan, blok Penilaian dimutakhirkan (dasar hukum
  PMK 99/2024 + Perpres 75/2017 + PMK 118/2017 jo. perubahannya).

## [#186] Sanding realisasi per triwulan (Penganggaran) — 2026-07-12

- **Sanding realisasi per triwulan per tahun anggaran**: realisasi
  dipetakan ke TW I–IV dari tanggal riwayat "terealisasi"; kumulatif +
  serapan kumulatif dibanding total DIPA. Usulan tanpa tanggal riwayat
  tetap masuk total (tidak hilang). Butir "menyusul" terakhir modul
  Penganggaran tuntas.
- Unit test +1 → 245 passed; seksi tabel baru di halaman Penganggaran.

## [#185] Konsolidasi dokumentasi #184 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 (Penilaian + koreksi nilai
  #184) + tabel modul & roadmap masterplan — dasar hukum dimutakhirkan:
  revaluasi Perpres 75/2017 + PMK 118/2017 jo. perubahannya, penilaian
  PMK 99/2024, asuransi PMK 43/2025; baris Pengamanan & Penggunaan
  menjadi "Lengkap tahap awal".

## [#184] Register koreksi nilai & hasil penilaian — 2026-07-12

- **Register koreksi nilai per aset** di modul Penilaian: catat hasil
  revaluasi (LHIP), koreksi inventarisasi, koreksi temuan/putusan,
  koreksi pencatatan, dan penilaian tujuan tertentu (informasional,
  tidak mengubah nilai buku) — nilai lama → baru, selisih otomatis,
  dampak masa manfaat (tetap / masa manfaat baru), dan status
  pencatatan SAKTI (tandai "tercatat di SAKTI", anti-race).
- Dasar riset: Perpres 75/2017 + PMK 118/2017 jo. 57/2018 jo. 107/2019
  (revaluasi), PMK 99 Tahun 2024 (penilaian) — pustaka §13 baris
  Penilaian dimutakhirkan + butir verifikasi 23 di §14.
- Unit test +2 → 244 passed; UI seksi baru + dialog pencarian aset di
  halaman Penilaian; indeks `penilaian_koreksi`.

## [#183] Tiket proses: dioperasikan pihak lain & penggunaan bersama — 2026-07-12

- **Dua rezim PMK 40/2024 tersisa** pada register tiket proses:
  dioperasikan pihak lain (penetapan Pengelola, pihak non-K/L) dan
  penggunaan bersama (Eminen + Kolaborator) — pipeline berjangka tanpa
  jalur pintas ≤6 bulan; pengingat perpanjangan ≤90 hari untuk semua
  jenis berjangka. Daftar "menyusul" Penggunaan tuntas (4 rezim).
- Unit test +2 → 242 passed; UI opsi jenis baru + dokumentasi
  (README/masterplan/pustaka/bmnModules) dalam PR yang sama.

## [#182] Konsolidasi dokumentasi #181 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Penggunaan (dimutakhirkan menyeluruh) + butir
  verifikasi 22 di §14 (tenggat/jangka waktu PMK 40/2024).

## [#181] Tiket proses alih status & penggunaan sementara — 2026-07-12

- **Tiket proses PMK 40/2024** di modul Penggunaan: alih status
  (draf → diajukan → disetujui → BAST → dihapus & dibukukan; tenggat
  1/2/1 bulan sebagai pengingat, [perlu verifikasi]) dan penggunaan
  sementara (5/2 tahun; ≤6 bulan boleh langsung berjalan tanpa
  persetujuan Pengelola; pengingat perpanjangan ≤90 hari).
- Endpoint GET/POST/status (dokumen tahap otomatis terpetakan)/DELETE +
  indeks; seksi UI + dialog buka tiket multi-aset di `PenggunaanPage`.
- Unit test +3 → 240 passed; checklist bmnModules.

## [#180] Konsolidasi dokumentasi #179 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + roadmap masterplan +
  pustaka §13 baris Perencanaan (usulan RKBMN per unit #179; menyusul
  tinggal sanding SBSK menunggu lampiran PMK 138/2024).

## [#179] Usulan RKBMN per unit berstatus — 2026-07-12

- **Register usulan RKBMN per unit** (PMK 153/2021 + KMK 128/KM.6/2022):
  pipeline draft → diajukan → disetujui PB → dikirim Pengelola (SIMAN)
  → disetujui/ditolak penelaahan, jalur dikembalikan wajib catatan;
  penanda SPTJM + reviu APIP; aset opsional ber-snapshot; anti-race.
- Temuan riset: PMK 138/2024 (SBSK) mencabut PMK 172/2020 — angka
  lampiran belum terverifikasi, kalkulator SBSK ditunda (pustaka §14
  butir 21).
- UI: seksi usulan + dialog buat usulan di `PerencanaanPage` (prop
  `user`); checklist bmnModules. Unit test +3 → 237 passed.

## [#178] Konsolidasi dokumentasi #177 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (polis asuransi #177 — seluruh item
  "menyusul" modul Pengamanan tuntas).

## [#177] Register polis Asuransi BMN (PMK 43/2025) — 2026-07-12

- **Subbab pustaka §11.5 Asuransi BMN** (riset dulu): PMK 97/2019
  ternyata sudah dicabut **PMK 43 Tahun 2025** (skema premi baru via
  Pooling Fund Bencana) — modul merujuk PMK 43/2025; butir verifikasi
  20 di §14.
- **Register polis** per aset di modul Pengamanan: nomor polis,
  penanggung (default Konsorsium Asuransi BMN), kategori objek
  Program/Nonprogram, nilai pertanggungan, premi + sumber dana
  (DIPA/PFB), masa berlaku dengan status akan datang/aktif/
  **segera berakhir ≤90 hari**/berakhir + ringkasan.
- UI seksi polis + dialog ber-pencarian aset; item "menyusul"
  Pengamanan kini TUNTAS semua. Unit test +2 → 234 passed.

## [#176] Konsolidasi dokumentasi #175 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (checklist per aset #175; menyusul
  tinggal asuransi BMN).

## [#175] Checklist pengamanan per aset per jenis — 2026-07-12

- **Checklist pengamanan** per aset (pustaka §11.2): butir fisik/
  administrasi/hukum per jenis objek (tanah/gedung/kendaraan/lainnya),
  skor terpenuhi + tanggal cek + petugas, upsert satu checklist per
  aset (`GET/POST /pengamanan/checklist`, DELETE admin).
- UI: seksi checklist dengan badge skor berwarna + tombol Perbarui
  pra-isi + dialog isi ber-pencarian aset (tebakan jenis dari golongan
  kode aset). Alat bantu internal — bukan bukti hukum.
- Unit test +2 → 232 passed; indeks `pengamanan_checklist`.

## [#174] Konsolidasi dokumentasi #173 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (status sertipikasi K1–K4 #173).

## [#173] Status sertipikasi tanah K1–K4 — 2026-07-12

- **Status sertipikasi** pada arsip dokumen jenis sertipikat (pustaka
  §11.4): belum/proses/K1–K4/SHP terbit + rekap per kategori di
  `GET /pengamanan/dokumen`; select hanya muncul untuk jenis sertipikat
  + badge ungu kategori di daftar. Unit test +2 → 230 passed.

## [#172] Konsolidasi dokumentasi #171 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (arsip dokumen kepemilikan #171).

## [#171] Arsip dokumen kepemilikan per aset — 2026-07-12

- **Arsip dokumen kepemilikan** di modul Pengamanan (pustaka §11.3,
  PP 27/2014 Ps. 43 + PMK 218/2015): sertipikat/BPKB/STNK/IMB-PBG per
  aset, atas nama, lokasi penyimpanan (Pengelola vs Pengguna Barang),
  tanggal berlaku opsional dengan penanda kedaluwarsa, lampiran scan
  GridFS pola baku (unggah/unduh/hapus admin).
- UI: seksi arsip + dialog catat dokumen ber-pencarian aset + dialog
  lampiran di `PengamananPage`; lokasi simpan otomatis mengikuti jenis.
- Unit test +2 → 228 passed; indeks `pengamanan_dokumen`.

## [#170] Konsolidasi dokumentasi #169 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan
  (pengamanan: register BMN bermasalah #169, pustaka §11).

## [#169] Register BMN bermasalah + bab pustaka Pengamanan — 2026-07-12

- **Bab pustaka baru §11 "Pengamanan BMN"** (riset dulu): induk regulasi
  PP 27/2014 Ps. 42–43 jo. PP 28/2020 + UU 1/2004 Ps. 49 + PMK 218/2015
  (koreksi: PMK 244/2012 = Wasdal, sudah dicabut PMK 207/2021); bentuk
  pengamanan per jenis BMN; alur kasus; sertipikasi K1–K4; bab lama
  §11–§14 bergeser jadi §12–§15.
- **Register BMN bermasalah/sengketa** di modul Pengamanan: kategori
  (dikuasai pihak lain / sertipikat pihak lain / berperkara), pipeline
  identifikasi → mediasi → blokir → litigasi → selesai dengan riwayat +
  anti-race, satu kasus aktif per aset, hapus admin — bahan laporan
  wasdal/CaLBMN.
- UI: seksi register + dialog buka kasus ber-pencarian aset di
  `PengamananPage` (prop `user` dari App). Unit test +3 → 226 passed.

## [#168] Konsolidasi dokumentasi #167 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan
  (pemeliharaan: ekspor CSV riwayat #167).

## [#167] Ekspor CSV riwayat pemeliharaan — 2026-07-12

- **Ekspor CSV** riwayat pemeliharaan (`GET /pemeliharaan/export`) —
  aset, tanggal, jenis DJKN, biaya, kondisi sebelum/sesudah, penanda
  telaah kapitalisasi PMK 181, pelaksana/bukti — melanjutkan pola
  #158–#163.
- Tombol **CSV** di header `PemeliharaanPage`; checklist bmnModules
  diperbarui.

## [#166] Konsolidasi dokumentasi #165 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + roadmap masterplan +
  pustaka §12 baris Penganggaran (kalender tenggat #165; "menyusul"
  tinggal sanding per triwulan).

## [#165] Kalender penganggaran konfigurabel — 2026-07-12

- **Kalender penganggaran** (pustaka §9.4): register tahapan ber-tenggat
  yang dikelola admin (`GET/POST /penganggaran/kalender`, DELETE per
  tahapan) — tanggal konfigurabel karena tenggat internal tiap K/L
  berbeda; pengingat lewat tenggat (merah) dan ≤30 hari (kuning) di
  `PenganggaranPage` memakai pola tenggat pelaporan #150.
- Utils + 3 unit test baru (validasi tahapan, info tenggat, rekap);
  indeks `penganggaran_kalender`; checklist bmnModules — item "menyusul"
  terakhir modul Penganggaran tuntas.

## [#164] Konsolidasi dokumentasi #163 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 (penganggaran:
  penanda ekspor CSV #163) + roadmap masterplan fase 4.

## [#163] Ekspor CSV register penganggaran — 2026-07-12

- **Ekspor CSV** register usulan penganggaran (`GET /penganggaran/export`)
  — tahun, jenis, akun BAS berlabel, uraian, status, nilai per tahap
  (usulan/disetujui/DIPA/realisasi), nomor DIPA, jumlah aset tertaut,
  sumber, pembuat — menutup gelombang ekspor CSV register pendamping
  (#158–#161).
- Tombol **CSV** di header `PenganggaranPage` (`downloadFileWithProgress`,
  `utf-8-sig`); checklist `bmnModules.js` penganggaran diperbarui.

## [#162] Konsolidasi dokumentasi #161 — 2026-07-12

- **Dokumentasi saja**: README blok Progres (pemusnahan + pengadaan:
  penanda ekspor CSV #161) + roadmap masterplan fase 4 & 6.

## [#161] Ekspor CSV register pemusnahan & pengadaan — 2026-07-12

- **Ekspor CSV** dua register terakhir gelombang #158–#159: pemusnahan
  (`GET /pemusnahan/export` — nomor/tanggal BA, cara, persetujuan, jumlah
  aset, nilai perolehan, lampiran) dan pengadaan (`GET /pengadaan/export`
  — jenis, pihak, kontrak/BAST, jumlah barang, nilai, dokumen kurang,
  lampiran).
- Tombol **CSV** di header `PemusnahanPage` & `PengadaanPage`
  (`downloadFileWithProgress`, `utf-8-sig` agar aman dibuka Excel); rute
  literal `.../export` sebelum catch-all `/{id}`.
- Checklist `bmnModules.js` pemusnahan & pengadaan diberi penanda
  ekspor CSV ✅.

## [#160] Konsolidasi dokumentasi #158–#159 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + roadmap
  masterplan (ekspor CSV register hilir #158–#159).

## [#159] Ekspor CSV register penghapusan & pemindahtanganan — 2026-07-12

- **Ekspor CSV** dua register hilir lagi (pola #158): usulan penghapusan
  (jalur + status + SK + jumlah lampiran) dan pemindahtanganan (bentuk +
  status + dokumen per tahap + ringkas aset); tombol CSV di kedua
  halaman.

## [#158] Ekspor CSV register pemanfaatan — 2026-07-12

- **Ekspor CSV** register perjanjian (kolom lengkap + status turunan +
  rekap kontribusi tercatat + jumlah lampiran, UTF-8 BOM); tombol CSV
  di header halaman Pemanfaatan.

## [#157] Konsolidasi dokumentasi #156 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + roadmap
  masterplan fase 6 (lampiran tiket insidentil #156).

## [#156] Arsip lampiran tiket insidentil wasdal — 2026-07-12

- **Lampiran per tiket insidentil** (scan BA bertanda tangan + foto
  temuan, pola lampiran baku): tombol klip + dialog di seksi Pemantauan
  Insidentil halaman Wasdal; hapus tiket membersihkan berkasnya.

## [#155] Konsolidasi dokumentasi #154 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (pindah gudang ✅; fase 2 tersisa hanya KIB).

## [#154] Pindah gudang persediaan ber-jurnal — 2026-07-12

- **Pindah gudang per barang**: lokasi berpindah anti-balapan, stok &
  layer FIFO tak tersentuh, jurnal arah "mutasi" mencatat asal → tujuan
  (+kompensasi bila jurnal gagal); `mutasi_periode` kini mengabaikan
  arah mutasi agar saldo laporan tak terganggu. Dialog + render riwayat
  khusus. Suite 220.

## [#153] Konsolidasi dokumentasi #152 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (filter gudang ✅; tersisa KIB + transfer stok antar gudang).

## [#152] Filter Lokasi/Gudang persediaan — 2026-07-12

- **Dimensi gudang aktif**: daftar gudang unik + filter gudang di daftar
  master (paging benar di query) + **laporan posisi per gudang** dengan
  subjudul; dropdown filter + unduhan ikut filter aktif. Smoke pypdfium2
  dua skenario lulus.

## [#151] Konsolidasi dokumentasi #150 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (implikasi Pelaporan §2.3 tuntas; tersisa KIB/gudang persediaan).

## [#150] Tenggat pelaporan konfigurabel per periode — 2026-07-12

- **Tenggat penyampaian per periode** (surat DJKN/K/L): atur/ubah/hapus
  oleh admin saat periode terbuka (tercatat riwayat); pengingat sisa
  hari + badge lewat tenggat di kartu Periode Pelaporan. Daftar
  "Implikasi AMAN" Pelaporan §2.3 tuntas. Suite 218.

## [#149] Konsolidasi dokumentasi #148 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (periode ber-kunci ✅; tersisa KIB/gudang persediaan).

## [#148] Periode pelaporan ber-kunci + penanda FINAL — 2026-07-12

- **Periode pelaporan** (Semester I/II/Tahunan) berstatus terbuka →
  terkunci (admin, anti-balapan; buka kembali wajib beralasan &
  tercatat); saat terkunci, **LBKP & CaLBMN berpenanda FINAL** di
  subjudul. Kartu kelola periode di hub Pelaporan. Suite 216; smoke
  pypdfium2 tiga skenario lulus.

## [#147] Konsolidasi dokumentasi #146 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (LKB ✅; tersisa KIB/gudang/periode ber-kunci).

## [#146] LKB — Laporan Kondisi Barang — 2026-07-12

- **LKB per NUP + ringkasan B/RR/RB per golongan** (format LKBT-PKPB1,
  riset → pustaka §2.3b): kondisi kosong tampil "(belum dicatat)",
  kolom satuan tidak difabrikasi; tombol di hub Pelaporan. Suite 211;
  smoke pypdfium2 lulus.

## [#145] Konsolidasi dokumentasi #144 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (CaLBMN ✅; tersisa KIB/gudang/LKB/periode ber-kunci).

## [#144] CaLBMN pra-isi bab I–V per periode — 2026-07-12

- **CaLBMN pra-isi** (struktur lampiran PMK 181/2016, riset → pustaka
  §2.3a): bab I–V terisi dari data nyata — ringkasan mutasi LBKP per
  golongan, intra/ekstra, persediaan FIFO, cakupan PSP, PNBP kontribusi
  ber-NTPN periode berjalan, pemindahtanganan/penghapusan/idle/sengketa;
  dropdown periode di hub Pelaporan. Posisi: bahan penyusunan — dokumen
  resmi via SAKTI; smoke pypdfium2 lulus.

## [#143] Konsolidasi dokumentasi #142 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan fase 6 (pemantauan insidentil wasdal #142).

## [#142] Pemantauan insidentil wasdal (10+5 hari kerja) + PDF BA — 2026-07-12

- **Pemantauan insidentil** (PMK 207/2021): pemicu masyarakat/media/
  audit, alur berjalan → BA terbit → dilaporkan dengan tenggat
  pelaksanaan 10 hari kerja + lapor 5 hari kerja sejak BA, peringatan
  lewat tenggat; **PDF Berita Acara siap tanda tangan** (placeholder
  bila BA belum terbit, smoke pypdfium2). Suite 208.

## [#141] Konsolidasi dokumentasi #140 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan fase 6 (register penertiban wasdal #140).

## [#140] Register penertiban wasdal (tenggat 15 hari kerja) — 2026-07-12

- **Tiket penertiban KPB** (PMK 207/2021): sumber pemantauan/permintaan
  Pengelola/temuan APIP-BPK, tenggat otomatis 15 hari kerja
  (Senin–Jumat), peringatan lewat tenggat, selesai ber-tindak-lanjut
  (anti-balapan); seksi baru + 2 dialog di halaman Wasdal. Suite 204.

## [#139] Konsolidasi dokumentasi #137–#138 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 3 (arsip SK PSP #137) &
  Fase 5–6 (arsip lampiran pemindahtanganan #138) + penanda roadmap
  masterplan fase 3 dan 6.

## [#138] Arsip lampiran register pemindahtanganan — 2026-07-12

- **Lampiran per usulan** (PMK 111/2016 jo. 165/2021): scan persetujuan/
  risalah lelang/BAST/naskah hibah/bukti setor PNBP (pola lampiran baku);
  tombol klip + dialog di halaman Pemindahtanganan. Seluruh register
  hilir siklus BMN kini punya arsip berkas konsisten.

## [#137] Arsip scan SK PSP (lampiran register penetapan) — 2026-07-12

- **Lampiran per SK PSP** (PMK 40/2024): scan SK penetapan + dokumen
  pendukung (pola #131/#132/#134/#135 — GridFS, tautan ber-token,
  hapus admin, bersih saat SK dihapus); tombol klip + dialog di bagian
  PSP halaman Penggunaan.

## [#136] Konsolidasi dokumentasi #134–#135 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 (arsip berkas
  perolehan #135) & Fase 5–6 (arsip SK penghapusan #134) + penanda
  roadmap masterplan fase 4 dan 6.

## [#135] Lampiran berkas register perolehan — 2026-07-12

- **Arsip berkas per perolehan** (melengkapi checklist #117): scan
  kontrak/BAPHP/BAST/kuitansi/SP2D (pola lampiran baku); tombol klip +
  dialog di halaman Pengadaan. Semua register hilir kini punya arsip
  lampiran konsisten.

## [#134] Arsip SK penghapusan (lampiran tiket usulan) — 2026-07-12

- **Lampiran per tiket usulan** (PMK 83/2016): scan SK penghapusan +
  dokumen pendukung (pola #131/#132 — GridFS, tautan ber-token, hapus
  admin, bersih saat tiket dihapus); tombol klip + dialog di halaman
  Penghapusan.

## [#133] Konsolidasi dokumentasi #131–#132 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan diperluas dengan arsip lampiran (#131–#132).

## [#132] Lampiran bukti pelaksanaan pemusnahan — 2026-07-12

- **Lampiran per BA** (PMK 83/2016): foto pelaksanaan + scan BA
  bertanda tangan (pola #131 — GridFS, tautan ber-token, hapus admin,
  bersih saat BA dihapus); dialog Lampiran di halaman Pemusnahan.

## [#131] Arsip scan dokumen pemanfaatan — 2026-07-12

- **Lampiran per perjanjian** (pustaka §6): unggah scan persetujuan/
  perjanjian/bukti setor (PDF/gambar, GridFS, maks 10×10MB), buka via
  tautan ber-token, hapus admin; hapus register ikut membersihkan
  berkasnya. Dialog Lampiran di halaman Pemanfaatan.

## [#130] Konsolidasi dokumentasi #128–#129 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 & 3 + masterplan
  (baris Penggunaan & roadmap Fase 3) diperluas dengan #128–#129.

## [#129] Register SK penetapan penggunaan (PSP) — 2026-07-12

- **Register SK PSP multi-aset** (PMK 40/2024): 5 jenis penetapan,
  snapshot aset per SK, rekap per jenis + cakupan aset unik ter-PSP vs
  total; seksi baru + dialog catat di halaman Penggunaan. 2 unit test
  (suite 199).

## [#128] Pengingat opname semesteran persediaan — 2026-07-12

- **Banner pengingat opname fisik** (pustaka §3.3): status per semester
  berjalan dari transaksi opname terakhir; tampil di halaman Persediaan
  bila semester ini belum diopname. 3 unit test (suite 197).

## [#127] Konsolidasi dokumentasi Penggunaan #125–#126 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 3 + masterplan (baris
  Peta Siklus Penggunaan & roadmap Fase 3) diperluas dengan #125–#126.

## [#126] Daftar pantau BMN idle + tiket klarifikasi — 2026-07-12

- **BMN idle (PMK 120/2024)**: kandidat otomatis (Nonaktif / tanpa
  pengguna; Tidak Ditemukan dikecualikan), tiket klarifikasi →
  digunakan kembali / usul serah → diserahkan (dokumen wajib per tahap,
  anti-balapan, riwayat); seksi baru di halaman Penggunaan. 3 unit test
  (suite 194).

## [#125] Daftar Barang yang Digunakan per pemegang (PDF) — 2026-07-12

- **Lampiran BAST penggunaan** (PMK 40/2024): PDF per pemegang berisi
  identitas + tabel aset yang dipegang + penanda BAST + tanda tangan
  pemegang/KPB; unduh dari dialog aset pemegang. Smoke FakeDB + PNG
  lulus. PSP/alih status/BMN idle menyusul.

## [#124] Konsolidasi dokumentasi fitur #119–#123 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 & 5–6 + penanda
  roadmap masterplan diperluas dengan lima fitur pendalaman (#119–#123).

## [#123] Sanding per akun BAS di register penganggaran — 2026-07-12

- **Sanding rencana vs realisasi per akun** (pustaka §9): tabel per akun
  53x/523 dengan nilai usulan/disetujui/DIPA/realisasi + serapan persen;
  usulan tanpa akun digabung baris "lainnya". 1 unit test (suite 191).

## [#122] Laporan Hasil Pemantauan Wasdal PDF — 2026-07-12

- **Laporan pra-isi wasdal semesteran** (PMK 207/2021): rekap 5 objek
  pemantauan ber-total + rincian temuan per objek (maks 30/objek) + blok
  tanda tangan; unduh dari header dasbor Wasdal. Kanal resmi tetap Modul
  Wasdal SIMAN v2. Smoke FakeDB + PNG lulus.

## [#121] Kontribusi tahunan pemanfaatan + pengingat tunggakan — 2026-07-12

- **Kewajiban PNBP tahunan** (KSP/BGS/KSPI, pustaka §6): field kontribusi
  tahunan pada perjanjian, pencatatan pembayaran per tahun ber-NTPN
  (duplikat tahun ditolak), pengingat tunggakan otomatis dari tahun
  mulai s.d. tahun berjalan/berakhir. 2 unit test (suite 190).

## [#120] Usulan penghapusan otomatis dari BA Pemusnahan — 2026-07-12

- **Tindak lanjut PMK 83/2016 satu klik**: tombol Usulkan Hapus per BA
  membuat tiket usulan penghapusan tiap aset (keterangan merujuk nomor
  BA + persetujuan); aset ber-usulan aktif dilewati; lencana ✓ saat
  semua tercakup. 1 unit test baru (suite 188).

## [#119] PDF Berita Acara Pemusnahan — 2026-07-12

- **PDF BA Pemusnahan siap tanda tangan** (PMK 83/2016) dari register
  #110: kop surat, nomor BA + persetujuan, cara pemusnahan, tabel aset
  ber-total, blok tanda tangan pelaksana/saksi/KPB; tombol unduh per BA.
  Smoke FakeDB + PNG lulus. Foto bukti pelaksanaan menyusul.

## [#118] Konsolidasi dokumentasi Pengadaan — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Pengadaan →
  Sebagian, roadmap Fase 4 + #117), README (intro **SEMUA 14 modul
  siklus Sebagian Aktif** — tersisa sub-modul Pembukuan/KIB — + blok
  Progres Fase 4), dan pustaka §12 (baris implikasi Pengadaan).

## [#117] Pengadaan tahap awal: register perolehan per dokumen — 2026-07-12

- **Register perolehan** (bab pustaka §10, Perpres 16/2018 jo. 46/2025):
  satu entri per BAST/kontrak (jenis 101/102/103/105), checklist dokumen
  sumber per jenis (penangkal "BAST tercecer"), tautan barang → aset
  master + penanda ekstrakomptabel ambang PMK 181. Kartu naik Sebagian —
  Segera Hadir tersisa Pembukuan/KIB. 4 unit test (suite 187).

## [#116] Konsolidasi dokumentasi Penganggaran — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Penganggaran →
  Sebagian + PMK 62/2023, roadmap Fase 4 + #115), README (intro 13 modul
  Sebagian Aktif — sisa Pengadaan & Pembukuan/KIB — + blok Progres
  Fase 4), dan pustaka §11 (baris implikasi Penganggaran).

## [#115] Penganggaran tahap awal: register usulan berstatus — 2026-07-12

- **Register usulan penganggaran** (bab pustaka §9, PMK 62/2023 +
  PMK 153/2021): pipeline diusulkan → disetujui telaah → masuk DIPA →
  terealisasi dengan nilai wajib per tahap, akun BAS 53x/523 sesuai
  jenis, tautan aset opsional, rekap serapan. Kartu naik Sebagian —
  tinggal Pengadaan yang Segera Hadir. 4 unit test (suite 183).

## [#114] Konsolidasi dokumentasi Wasdal — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Wasdal → Sebagian,
  penanda roadmap Fase 6 + #113), README (intro 12 modul Sebagian Aktif +
  blok Progres Fase 5–6), dan pustaka §10 (baris implikasi Wasdal).

## [#113] Wasdal tahap awal: dasbor pemantauan 5 objek — 2026-07-12

- **Dasbor pemantauan Wasdal KPB** (bab pustaka §8, PMK 207/2021): mesin
  aturan membaca register yang ada → 12 jenis temuan per 5 objek
  pemantauan (BAST kosong, perjanjian berakhir/dokumen kurang, usulan
  hapus berlarut, kandidat belum diusulkan, tenggat lelang, data belum
  lengkap, sengketa, rusak tanpa pemeliharaan). Kartu naik Sebagian;
  8 unit test (suite 179). Penertiban & laporan formulir PMK menyusul.

## [#112] Konsolidasi dokumentasi Fase 6 — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Pemindahtanganan &
  Pemusnahan → Sebagian, penanda roadmap Fase 6 diperluas #106/#110/#111),
  README (intro 11 modul Sebagian Aktif + blok Progres Fase 5–6), dan
  pustaka §9 (baris implikasi Pemindahtanganan & Pemusnahan).

## [#111] Pemindahtanganan tahap awal: register usulan 4 bentuk — 2026-07-12

- **Register pemindahtanganan** (bab pustaka §7, PMK 111/2016 jo.
  165/2021): usulan multi-aset berstatus diusulkan → disetujui →
  dilaksanakan → selesai; dokumen wajib per tahap (persetujuan, risalah/
  BAST/naskah/PP, NTPN utk penjualan, SK Penghapusan) + peringatan
  tenggat lelang 6 bulan. Kartu naik Sebagian; 4 unit test (suite 171).

## [#110] Pemusnahan tahap awal: register BA multi-aset — 2026-07-12

- **Register BA Pemusnahan** (PMK 83/2016): nomor persetujuan wajib,
  objek dibatasi Rusak Berat (divalidasi per aset), cara pemusnahan
  baku, snapshot identitas + nilai; halaman baru dengan ringkasan +
  form multi-aset. Kartu naik Sebagian Aktif; 3 unit test (suite 167).

## [#109] Konsolidasi dokumentasi Pemanfaatan & status modul — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #106–#108; README kini
  menyebut 9 modul Sebagian Aktif (13 kartu siklus bisa dimasuki).

## [#108] Pemanfaatan tahap awal: register perjanjian 6 bentuk — 2026-07-12

- **Fase 5 Pemanfaatan dimulai** (bab pustaka §6, PMK 115/2020): register
  perjanjian Sewa/Pinjam Pakai/KSP/BGS-BSG/KSPI/KETUPI dengan validasi
  jangka maksimal per bentuk; status Aktif menuntut nomor persetujuan
  Pengelola + perjanjian (sewa: + NTPN) — pencegah temuan auditor;
  peringatan jatuh tempo ≤60 hari. Seluruh 13 kartu siklus kini bisa
  dimasuki. 4 unit test (suite 164).

## [#107] Referensi masa manfaat dapat dikelola — 2026-07-12

- **Referensi masa manfaat** per kelompok (KMK 295/2019 jo. 266/2023):
  daftar gabungan berlabel sumber; admin tambah/ubah/hapus entri satker
  (menimpa bawaan riset); posisi penyusutan langsung memakai peta terbaru.

## [#106] Tiket usulan penghapusan berstatus (usul → proses → SK) — 2026-07-12

- **Tiket usulan** per aset kandidat (jalur otomatis, duplikat aktif
  ditolak): transisi tervalidasi diusulkan → diproses → SK terbit /
  ditolak (admin; SK wajib bernomor; anti-balapan; riwayat tercatat);
  kandidat menampilkan status usulannya. 2 unit test (suite 159).

## [#105] Konsolidasi dokumentasi Fase 5–6 tahap awal — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #102–#104 (Penilaian &
  Penghapusan → Sebagian); README dapat blok Progres Fase 5–6.

## [#104] Penghapusan tahap awal: kandidat usul hapus — 2026-07-12

- **Fase 6 dimulai** — halaman Penghapusan: kandidat dijaring dari
  inventarisasi per jalur PMK 83/2016 (Tidak Ditemukan → penelusuran +
  telaah TGR; Rusak Berat → pemusnahan/pemindahtanganan) + nilai
  perolehan. Kartu naik Sebagian Aktif; 3 unit test (suite 157).

## [#103] Halaman Penilaian: posisi penyusutan + daftar telaah — 2026-07-12

- **Halaman Penilaian** (dari Beranda Modul): kartu perolehan/akumulasi/
  nilai buku/habis masa manfaat, tabel per golongan, telaah henti-susut &
  perlu-referensi, pemilih tanggal posisi. Kartu naik Sebagian Aktif.

## [#102] Penyusutan BMN: garis lurus semesteran per golongan (API) — 2026-07-12

- **Fase 5 dimulai** — bab pustaka §5 Penyusutan (koreksi: KMK 59/2013
  dicabut → KMK 295/2019 jo. 266/2023) + logika murni PMK 65/2017 (tanpa
  residu, konvensi semester penuh, nilai buku habis = 0, bucket telaah
  henti-susut/perlu-referensi tanpa menebak angka) + endpoint
  `/penilaian/penyusutan`. 7 unit test (suite 154); UI menyusul.

## [#101] Konsolidasi dokumentasi Fase 4 tahap awal — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #99–#100 (Perencanaan
  → Sebagian); README dapat blok Progres Fase 4.

## [#100] Kertas kerja usulan RKBMN pemeliharaan (XLSX) — 2026-07-12

- **Kertas kerja RKBMN** siap diisi satker: sheet Layak (identitas +
  riwayat biaya + kolom kuning Usulan Pekerjaan & Perkiraan Biaya) +
  sheet Tidak Layak (alasan/jalur benar); tombol di halaman Perencanaan;
  nama file mengikuti TA usulan (+1). Smoke roundtrip openpyxl.

## [#99] Perencanaan tahap awal: kandidat RKBMN pemeliharaan — 2026-07-12

- **Fase 4 dimulai** — halaman Perencanaan: saringan kelayakan usulan
  pemeliharaan (PMK 153/2021: Baik/RR layak; rusak berat → jalur hapus;
  idle → penetapan status) + riwayat biaya per aset dari modul
  Pemeliharaan (terbesar dulu). Kartu naik Sebagian Aktif; 6 unit test
  (suite 147 lulus).

## [#98] Transaksi massal persediaan: satu dokumen banyak barang — 2026-07-12

- **Transaksi Massal** (tombol baru di toolbar): satu bukti untuk ≤100
  barang; tiap barang tetap lewat jalur transaksi FIFO tunggal yang sudah
  teruji; kegagalan per barang dilaporkan per item (baris disorot merah,
  dialog tetap terbuka) tanpa membatalkan barang lain.

## [#97] Kartu Barang Persediaan PDF: riwayat + saldo berjalan — 2026-07-12

- **Kartu Barang** per barang persediaan (form kendali standar): identitas
  + jurnal kronologis dengan kolom masuk/keluar/sisa (saldo berjalan) dan
  nilai FIFO; tombol di dialog Riwayat. Barang tanpa transaksi = 404.

## [#96] Konsolidasi status Pelaporan Fase 2 (dokumentasi) — 2026-07-12

- Masterplan/README/pustaka/kartu modul diselaraskan: inti Pelaporan
  Fase 2 lengkap (#86, #93–#95); sisa pekerjaan Fase 2 didaftar eksplisit
  (KIB menunggu verifikasi lampiran, gudang/massal persediaan, CaLBMN/LKB).

## [#95] LBKP per golongan: saldo awal + mutasi + saldo akhir — 2026-07-12

- **LBKP semesteran/tahunan** (PMK 181): tiga seksi Intra/Ekstra/Gabungan
  per golongan — saldo awal, mutasi tambah (pencatatan), mutasi kurang
  (tombstone audit; nilai terekam sejak #94, kasus lama diungkap jujur),
  saldo akhir = identitas mutasi; dropdown periode di hub Pelaporan.
- 3 unit test (suite 141); smoke render tervalidasi angka-per-angka.

## [#94] Ekspor rekonsiliasi XLSX — sandingan SAKTI — 2026-07-12

- **Rekonsiliasi XLSX** (3 sheet): Posisi per Golongan, Rincian Aset
  (klasifikasi per NUP), Rincian Persediaan (nilai FIFO) — tombol di hub
  Pelaporan; angka numerik agar bisa dihitung ulang di Excel.
- Fondasi LBKP: audit hapus aset kini merekam nilai perolehan (tombstone
  bernilai untuk mutasi kurang mendatang). Smoke roundtrip openpyxl.

## [#93] Laporan Posisi BMN di Neraca — komponen LBKP — 2026-07-12

- **Posisi BMN di Neraca** (PMK 181, pustaka §2.3): seluruh aset satker
  lintas kegiatan per golongan (intra/ekstra) + baris Persediaan (nilai
  FIFO per layer) + total posisi; unduh dari hub Pelaporan.
- Helper murni `posisi_neraca` + 2 test (suite 138); fix impor `timezone`
  reports.py (tertangkap smoke).

## [#92] Jadwal pemeliharaan berkala: jatuh tempo + status + auto-geser — 2026-07-12

- **Jadwal Berkala** per aset (pedoman DKPB Ps. 46(2) PP 27/2014): interval
  1–60 bulan, jatuh tempo dihitung dari pelaksanaan terakhir + interval,
  status **Terlambat / Segera (≤14 hari) / Terjadwal**; mencatat
  pemeliharaan otomatis menggeser jadwal aset tsb.
- Seksi baru di halaman Pemeliharaan: badge peringatan, aksi Catat
  (prefill aset), ubah, hapus admin. 5 unit test (suite 136 lulus).

## [#91] Konsolidasi dokumentasi Fase 3 (masterplan + README) — 2026-07-12

- Tabel peta siklus masterplan: 5 modul kini berstatus **Sebagian** dengan
  rujukan PR (#76–#90); README dapat blok **Progres Fase 3** (#87–#90) dan
  paragraf Beranda Modul yang menyebut modul-modul Sebagian Aktif.

## [#90] DHPB PDF semesteran/tahunan — laporan berkala pemeliharaan — 2026-07-12

- **DHPB (Daftar Hasil Pemeliharaan Barang)** per periode (tahun penuh /
  Semester I / II — Ps. 47 PP 27/2014): PDF landscape berkop surat, grup
  per aset + subtotal & total, tanda telaah kapitalisasi, ttd KPB; tombol
  dropdown di halaman Pemeliharaan. Periode kosong = 404 (tanpa dummy).
- Smoke render FakeDB menangkap bug label aset terjepit → SPAN baris grup.

## [#89] Pemeliharaan tahap awal: riwayat + biaya per aset (bahan DHPB) — 2026-07-12

- **Modul Pemeliharaan** (PP 27/2014 Ps. 46-47, riset regulasi → pustaka
  §4): catat kejadian per aset (jenis ringan/sedang/berat DJKN, biaya,
  pelaksana, bukti), kondisi sebelum/sesudah (opsional memperbarui kondisi
  aset), rekap per tahun anggaran/jenis + aset terboros, filter, dan
  **penanda telaah kapitalisasi** bila biaya ≥ ambang PMK 181/2016.
- Kartu Pemeliharaan naik Sebagian Aktif. 18 unit test (suite 128 lulus);
  koleksi baru `pemeliharaan` + indeks.

## [#88] Pengamanan tahap awal: dasbor tertib administrasi + sengketa — 2026-07-12

- **Dasbor kesehatan data aset**: 6 kartu (Data Lengkap + tanpa foto/
  register/lokasi/pengguna/BAST — klik → daftar aset bermasalah) +
  **Daftar Pantau Sengketa** (perkara, pihak) dari data inventarisasi.
- Kartu Pengamanan naik Sebagian Aktif. 8 unit test; tanpa koleksi baru.

## [#87] Penggunaan tahap awal: rekap aset per pemegang + BAST — 2026-07-12

- **Fase 3 dimulai** — halaman "Aset per Pemegang" (lintas kegiatan) dari
  data pengguna+NIP+BAST inventarisasi: badge Lengkap / BAST x/y, dialog
  daftar aset per pemegang; kunci nama ternormalisasi + NIP. Kartu
  Penggunaan naik Sebagian Aktif. 7 unit test; tanpa koleksi baru.

## [#86] Hub Pelaporan — arsip laporan lintas kegiatan satu pintu — 2026-07-12

- **Halaman Arsip Pelaporan** (dari Beranda Modul): daftar semua kegiatan
  (cari, badge Disahkan) + dropdown unduh 7 laporan resmi per kegiatan
  (LHI/RHI/BAHI/DBKP/SP/Eksekutif) + seksi laporan persediaan.
- Kartu Pelaporan kini bisa dimasuki; LBKP & rekonsiliasi menyusul.

## [#85] Impor/ekspor master persediaan + template + toolbar menu — 2026-07-12

- **Impor CSV/XLSX master persediaan**: identitas (kode 16 + NUP) sudah ada
  → perbarui field non-identitas; baru → jalur create (kode 10 digit
  auto-suffix, NUP otomatis); stok/layer tak tersentuh; laporan per baris.
- **Template CSV** + **Ekspor CSV** (master + stok & nilai FIFO terkini).
- Toolbar persediaan dirapikan: menu **Dokumen** (Posisi/Mutasi/Kertas
  Kerja/BAOF) + menu **Data** (Impor/Template/Ekspor) — ramah HP.
  5 unit test parser impor (48 total lulus).

## [#84] Konsolidasi status modul Persediaan (dokumentasi) — 2026-07-12

- Kartu modul Persediaan di Beranda Modul menampilkan fitur berjalan
  (✅ #77–#83) vs menyusul (gudang, impor massal, massal per dokumen);
  masterplan §7.4 ditandai per PR; README blok "Progres Fase 2".

## [#83] Stock opname persediaan + BAOF 3 penandatangan — 2026-07-12

- **Opname per barang**: stok fisik + alasan wajib → selisih dibukukan
  otomatis (kurang = konsumsi FIFO; lebih = layer penyesuaian harga layer
  termuda) + jurnal jenis opname (OPN); bersyarat versi + retry.
- **Kertas Kerja Opname** (kolom fisik kosong, pola SAKTI) & **BAOF** per
  tanggal (buku → fisik → selisih ± + alasan) — keduanya PDF berkop.
- `_signature_block` kini mendukung **3 penandatangan** (penghitung, saksi,
  mengetahui) — dulu ttd ke-3 terbuang diam-diam. 90 unit test lulus.

## [#82] Laporan persediaan: Posisi Stok + Mutasi Periode (PDF) — 2026-07-12

- **Laporan Posisi Persediaan**: per kelompok kodefikasi (uraian dari
  referensi), nilai per barang dihitung FIFO per layer, subtotal +
  grand total.
- **Laporan Mutasi Persediaan** per periode dari JURNAL: saldo awal →
  masuk (qty/nilai) → keluar (qty/nilai) → saldo akhir + TOTAL.
- Tombol Posisi & Mutasi (dialog rentang, default bulan berjalan) di
  toolbar Master Persediaan. 3 unit test mutasi_periode (39 total);
  smoke render tervalidasi visual.

## [#81] Peringatan kritis/kedaluwarsa + nota dinas PDF persediaan — 2026-07-12

- **Daftar pantau persediaan** (`/persediaan/peringatan`): habis, kritis
  (stok ≤ batas), layer kedaluwarsa & segera kedaluwarsa (horizon 30 hari).
- **Nota dinas PDF otomatis** (kritis/kedaluwarsa): kop surat + tabel +
  tanda tangan KPB — usulan pengadaan atau tindak lanjut kedaluwarsa.
- **Banner peringatan** kuning + tombol unduh nota dinas di halaman
  Master Persediaan. 3 unit test klasifikasi kedaluwarsa (36 total).

## [#80] Transaksi keluar FIFO persediaan — konsumsi layer tertua — 2026-07-12

- **Transaksi KELUAR persediaan**: konsumsi layer FIFO tertua dulu; nilai
  keluar = Σ qty terpakai × harga layer (FIFO murni); jenis peta SAKTI
  (Habis Pakai K01, Transfer K02, Hibah K03, Usang K04, Rusak K05);
  update master bersyarat versi + retry 3× (aman balapan); jurnal berisi
  rincian layer + unit penerima; jurnal gagal → snapshot dikembalikan.
- Tombol **Keluar** di halaman persediaan (nonaktif saat stok 0) + toast
  nilai keluar FIFO. 8 unit test konsumsi FIFO baru (33 total lulus).

## [#79] Transaksi masuk FIFO persediaan — layer + jurnal + UI — 2026-07-12

- **Transaksi MASUK persediaan**: jenis memetakan 1:1 ke SAKTI (Saldo Awal
  M01, Pembelian M02, Transfer M03, Hibah M04, Perolehan Lainnya M99);
  layer FIFO baru (harga & kedaluwarsa melekat di layer) + stok naik
  atomik + **jurnal** ber-stok sebelum/sesudah + dokumen sumber; bila
  jurnal gagal → layer & stok dikompensasi.
- Tombol **Masuk** & **Riwayat** per baris di halaman Master Persediaan
  (kartu jurnal: jenis + kode SAKTI, jumlah × harga, stok →, bukti,
  petugas). 5 unit test baru.

## [#78] UI Master Persediaan — modul naik Sebagian Aktif — 2026-07-12

- **Halaman Master Persediaan** dari Beranda Modul: cari + chip filter
  status stok (aman/kritis/habis, dihitung di server), tambah barang
  (kode '1' 10 digit → nomor urut otomatis; NUP otomatis; satuan baku),
  edit ber-OCC (If-Match; 409 memuat ulang), hapus admin berkonfirmasi.
- Kartu "Inventarisasi Persediaan" di Beranda Modul naik status
  **Sebagian Aktif** dan bisa dimasuki. Transaksi FIFO/gudang/opname
  menyusul (§7.4).

## [#77] Master Persediaan — langkah 1 modul Inventarisasi Persediaan — 2026-07-12

- **Master barang persediaan** (`/api/persediaan`): kode wajib berawalan '1'
  (10 digit → nomor urut otomatis; 16 digit penuh), NUP otomatis, identitas
  unik; stok lahir 0 dan **stok/nilai bersumber dari layer FIFO** (perpetual
  + FIFO per layer, selaras SAKTI — pustaka §3); status stok
  habis/kritis/aman terfilter di query; update ber-OCC (If-Match); hapus
  hanya saat stok 0. Registry field anti-drift + 20 unit test.
- KIB **ditunda** menunggu verifikasi Lampiran PMK 181 (aturan "regulasi
  dulu, kode kemudian") — tercatat di masterplan.

## [#76] DBKP per golongan — langkah pertama modul Pembukuan — 2026-07-12

- **Laporan DBKP (Daftar Barang Kuasa Pengguna) per golongan** sesuai PMK
  181/2016: pemilahan **intra/ekstrakomptabel** dari ambang kapitalisasi
  ber-parameter (Peralatan & Mesin ≥ Rp1 jt; Gedung & Bangunan ≥ Rp25 jt;
  lainnya selalu intra); uraian golongan dari referensi kodefikasi; barang
  tanpa golongan tampil sebagai baris "?" (tidak disembunyikan); catatan
  ambang + tanda tangan Kuasa Pengguna Barang.
- Tombol "DBKP per Golongan" di panel Laporan Resmi + masuk batch ZIP.
- `pembukuan_utils.py` + 14 unit test; smoke render FakeDB tervalidasi
  visual (menemukan & memperbaiki header patah + field nama kegiatan).

## [#75] Perbaikan hover light/dark + aturan anti-terulang + pustaka regulasi — 2026-07-12

- **Hover dibetulkan di kedua tema**: akar masalah = token `--accent`
  proyek adalah biru pekat + teks putih. `hover:bg-accent` → `hover:bg-muted`
  (Beranda Modul, Kodefikasi, bar peta); tombol **Kartu** di header edit
  aset diberi pasangan `hover:text-*` kedua tema (dulu teks putih di atas
  emerald terang → tak terbaca di light mode). Aturan anti-terulang 6b
  tertulis di SKILL.md.
- **`docs/PUSTAKA-REGULASI-BMN.md`** — rujukan wajib sebelum membangun
  modul: penatausahaan PMK 181/2016 (DBKP/DBR/KIB 6 jenis/LBKP/jenjang),
  persediaan (desain **FIFO per batch tervalidasi** — perpetual + FIFO per
  layer ala SAKTI sejak TA 2021; enum transaksi resmi; opname + BAOF;
  akun 1171xx), kendala satker → fitur penangkal, butir perlu-verifikasi,
  sumber. SKILL.md aturan 10: "regulasi dulu, kode kemudian".

## [#74] UI Referensi Kodefikasi — kelola & impor dari Beranda Modul — 2026-07-12

- **Halaman Referensi Kodefikasi**: cari kode/uraian (debounce), chip filter
  per level, tabel berpaging + badge level berwarna + penanda PERSEDIAAN
  (kode berawalan '1'); back-guard HP.
- **Admin**: tambah (level otomatis dari panjang kode), ubah uraian, hapus
  berkonfirmasi (turunan ditolak server), impor CSV/XLSX + ringkasan hasil,
  unduh template. Non-admin baca saja.
- Tombol perkakas "Referensi Kodefikasi Barang" di kartu Penatausahaan
  Beranda Modul.

## [#73] Kodefikasi referensi barang 5 level — fondasi Fase 2 — 2026-07-12

- **Referensi kodefikasi BMN** (`/api/kodefikasi`): struktur 5 level dari
  panjang prefix kode (1/3/5/7/10 digit — Golongan/Bidang/Kelompok/Sub/
  Sub-sub); digit pertama memisahkan domain ('1' persediaan, '2'-'8' aset).
- Endpoint: list (cari/filter/paging), `/golongan` (seed 8 golongan standar
  idempoten), `/lookup/{kode}` uraian berjenjang, `/template` CSV, CRUD
  admin (hapus ditolak bila punya turunan), `/import` CSV/XLSX upsert
  dengan laporan per baris. Index kode unik.
- 24 unit test logika murni (anti-drift) — level SELALU diturunkan dari
  panjang kode, tak bisa bertentangan dengan file impor.
- Fondasi untuk Pembukuan (DBKP/KIB), Inventarisasi Persediaan, dan
  Pengadaan pada iterasi loop fase berikutnya.

## [#70] Deploy: retry jangkauan VPS 5x + ulangi SSH sekali — 2026-07-11

- `deploy.yml` kini tahan gangguan sesaat: `ssh-keyscan` dicoba **5 kali**
  berjarak 20 detik (timeout 15 dtk/percobaan) dan eksekusi skrip deploy
  **diulang sekali** bila koneksi putus (skrip idempoten). Latar: run
  deploy pasca-merge #69 gagal keyscan padahal konfigurasi benar.

## [#69] Bar peta HP satu baris (menu gabungan) + siklus selaras diagram resmi Kemenkeu — 2026-07-11

- **Bar peta di HP jadi SATU baris**: filter Barang Serupa + Unduh
  (KML/KMZ/SHP) + Muat Ulang dilebur ke **satu tombol ber-menu** — ikon
  Layers menyala violet + titik penanda saat filter kelompok aktif,
  berganti spinner saat memuat; item menu ≥42px. ≥sm tetap kontrol
  terpisah.
- **Siklus selaras diagram resmi Kemenkeu** (12 tahap): Perencanaan
  Kebutuhan ≠ Penganggaran, Pengamanan ≠ Pemeliharaan; **dasar hukum
  (PMK) per tahap** tampil di dialog konsep; sub-kegiatan dirinci
  (Penggunaan: PSP/alih status/sementara/pihak lain/bersama + BMN idle;
  Pemanfaatan: Sewa/Pinjam Pakai/KSP/BGS/BSG/KSPI/KETUPI/PDF;
  Pemindahtanganan: Penjualan/Hibah/Tukar Menukar/Penyertaan Modal;
  Wasdal: pemantauan/investigasi/portofolio aset/analisis SBSK/
  penertiban); strip **6 asas pengelolaan** di Beranda Modul; masterplan
  diperbarui mengikuti diagram.

## [#68] Rumah modul Siklus BMN + masterplan pengembangan + skill proses baku — 2026-07-11

- **Beranda Modul** — halaman pertama setelah login: peta Siklus Pengelolaan
  BMN (PP 27/2014) dengan Penatausahaan sebagai poros. **Inventarisasi Aset
  AKTIF** (pintu ke aplikasi berjalan); Pembukuan, Inventarisasi Persediaan,
  Pelaporan + 10 tahap siklus lain berstatus **Segera Hadir** — klik kartu
  menampilkan konsep, rencana fitur, integrasi, dan fase roadmap.
- Registry modul `frontend/src/lib/bmnModules.js` (satu sumber kebenaran
  status & konsep modul); pilihan modul per-tab — reload di tengah kerja
  lapangan tidak terlempar; tombol **Modul** di halaman Pilih Kegiatan.
- **`docs/MASTERPLAN-SIKLUS-BMN.md`** — rencana induk hasil pendalaman repo
  referensi KERJA-BARENG (SIMAN-G): pola yang diadopsi (kodefikasi prefix
  5 level, transaksi stok vs atribut, approval `pending_changes`,
  reklasifikasi 2 langkah, dokumen sumber sebagai simpul, FIFO batch,
  interop SIMAN) & anti-pola yang dihindari; 7 prinsip integrasi antar
  modul; **konsep rinci Inventarisasi Persediaan** (master ber-batch FIFO,
  transaksi masuk/keluar per dokumen sumber, gudang, stock opname +
  penyesuaian otomatis, nota dinas kritis/kedaluwarsa); roadmap fase 1–6.
- **`.claude/skills/aman-dev/SKILL.md`** — proses baku pengembangan bertahap
  per fitur: peta repo, konvensi wajib, pipeline verifikasi→PR→CI→merge→
  auto-deploy, jebakan umum, checklist pemilik proyek.
- README: bagian "Arah Pengembangan — Siklus Penuh Pengelolaan BMN".

## [#67] Popup pin berbingkai foto + bar peta ringkas di HP + halaman PRD v2.3 — 2026-07-11

- **Popup marker peta dirombak** — padat & informatif: bingkai foto sampul
  62×62 (streaming 256px saat online, thumbnail snapshot saat offline; tanpa
  foto → blok judul melebar penuh), badge "N foto", pill status/kondisi
  berwarna + pill hijau "Pengguna lengkap ✓", baris info berlabel (Merk/Tipe,
  Kategori, Lokasi, Pengguna+NIP) yang hanya tampil bila terisi, tombol
  **Edit Aset** selebar popup.
- **Bar peta dua baris di HP**: [ikon · judul · tutup] lalu [filter kelompok
  (melebar) · unduh · muat ulang] — teks jumlah titik tidak lagi terpotong
  (versi ringkas "616/616 titik"); ≥sm tetap satu baris.
- **Halaman PRD tersembunyi → v2.3**: bagian baru "Apa yang Baru — Rilis
  v2.3" (6 kartu catatan rilis), hero dipoles (copy, chip kapabilitas, cahaya
  latar), grid statistik 5 kartu dibetulkan, timeline implementasi responsif.

## [#66] Hover ikon peta, tata letak mode pindai, & panel Edit Info kamera — 2026-07-11

- Tombol peta di toolbar: warna teks saat **hover di light mode** dibetulkan
  (dulu putih di atas latar terang → tidak terlihat).
- **Mode pindai kamera**: saat scanner aktif, tombol shutter/zoom/aksi
  disembunyikan dan diganti bilah pindai dengan tombol "Batal Scan" lebar
  penuh — tidak ada lagi kontrol bertumpuk.
- **Panel Edit Info kamera selengkap lembar edit cepat inventarisasi**:
  chip Status & Kondisi, blok detail kondisional (klasifikasi/sub, asal-usul,
  sengketa, tindak lanjut), stiker + ukuran, Pengguna Barang (melekat ke,
  jenis operasional, jabatan, nama, NIP/NIK) — konstanta diimpor dari
  `InventoryFieldSheet` (satu sumber). Tombol **"Simpan & Scan"** di dalam
  panel: simpan → kamera kembali memindai aset berikutnya.

## [#65] Peta jadi lembar di halaman utama + alur Simpan & Scan + pembaruan dokumen — 2026-07-11

- **Peta Aset kini lembar di halaman utama** (bukan overlay lepas): header,
  saklar Dashboard/Inventarisasi, dan toolbar filter tetap tampil; area baris
  data digantikan peta saat terbuka. Form tambah/edit aset tetap bisa muncul di
  samping (desktop) / di atasnya (HP) — selesai edit **kembali ke peta**.
- **Barang Serupa jadi filter peta**: dropdown kelompok (kode+nama, ≥2 unit)
  diturunkan dari data peta sendiri — ikut filter aktif dan jalan saat offline.
- Pin kini **satu popup** saja (tooltip hover dihapus — dulu tampil dobel di
  layar sentuh); tombol Edit menutup popup, peta tetap terbuka.
- **Alur scan-edit lapangan dirapikan**: tombol utama **"Simpan & Scan"**
  (simpan aset ini → scanner langsung terbuka lagi untuk stiker berikutnya),
  "Simpan & Aset Baru" jadi baris sekunder, tombol Batal Scan diperbesar.
  Intent `camera:stay` menyimpan tanpa berpindah aset.
- HP: padding & jarak antar blok diperkecil khusus layar kecil — baris data
  dapat ruang lebih (tinggi tombol tetap ≥44px sesuai aturan tap-target).
- Dokumentasi menyeluruh: CHANGELOG terisi ulang (#38–#65), README v2.3,
  halaman PRD tersembunyi diperbarui (peta, kamera, CI/CD, ekspor GIS).

## [#64] Ekspor peta KML/KMZ/SHP + marker berlapis info + filter tanggal + kop KPB — 2026-07-11

- **Unduh KML/KMZ/SHP** dari peta — 27 atribut per titik, mengikuti filter
  aktif (endpoint `/api/export/geo`, shapefile WGS84 via pyshp).
- Pin peta: **badge kamera** bila ada foto; **border hijau** bila pengguna +
  NIP/NIK + BAST lengkap.
- Filter Lanjutan: **rentang Tanggal Input** (server + offline + badge).
- **Kop surat 3 baris** sesuai format resmi (instansi besar; unit + sub-unit
  tebal) + **alamat multi-baris** (textarea; tiap Enter = baris kop).
- Seluruh tanda tangan laporan: "Kepala Satuan Kerja" → **"Kuasa Pengguna
  Barang"**.
- `build_asset_search_query` diekstrak dari GET /assets — daftar, peta, dan
  ekspor geo memakai SATU builder filter (tidak bisa drift).

## [#63] Peta Aset halaman penuh + filter aktif + tombol ikon toolbar — 2026-07-11

- Peta pindah dari panel bertumpuk ke tampilan penuh; tombol ikon pin teal di
  samping Cari & Scan (ikon saja di HP/tablet).
- Data peta mengikuti pencarian + kategori + filter lanjutan; offline memakai
  snapshot dengan filter yang sama.
- Backend: semua opsi sort GET /assets diberi tiebreaker `id` — paging
  skip/limit deterministik.

## [#59–#62] Auto-deploy ke VPS Hostinger — 2026-07-11

- Workflow **Deploy ke Hostinger VPS**: setiap merge ke `main` menjalankan
  `scripts/deploy_vps.sh` di VPS lewat SSH (fetch+reset, pip install, restart
  backend, yarn build). Manual dispatch juga tersedia.
- Secret `VPS_SSH_KEY` menerima format **base64 satu-baris** (anti salah
  tempel); validasi kunci & uji jangkauan host dengan pesan error berbahasa
  jelas. README deploy dibetulkan ke `origin/main`.

## [#58] Kamera lapangan: flash, gestur kecerahan, simpan instan; edit cepat scan QR; Peta Aset — 2026-07-11

- **Flash/senter** (menyala ulang setelah flip kamera) + **gestur kecerahan**
  (tahan & geser atas/bawah; dibakar ke hasil foto, termasuk fallback iOS ≤17).
- **Simpan & Baru instan**: alur kamera melewati validasi server & kompresi
  Tinify per foto (lokal saja) — antrean latar tetap memvalidasi & auto-renumber
  NUP saat sinkron.
- **Kamera + Scan QR** untuk edit cepat antar-aset di mode inventarisasi
  (cocok EKSAK pada register/kode/serial; ambigu → isi kotak pencarian).
- **Peta Aset** perdana (leaflet + OSM): pin status berwarna, geser pin =
  koordinat tersimpan otomatis lewat antrean (If-Match + Idempotency-Key).
- 19 temuan verifikasi adversarial (43 agen) diperbaiki pra-merge, termasuk
  XSS tooltip peta dan bypass OCC/row-lock.

## [#57] Gerbang CI + registry field aset + perbaikan menyeluruh laporan — 2026-07-11

- **CI GitHub Actions**: backend compileall + 26 test unit bebas-infra;
  frontend eslint (react-hooks) + build — jalan di setiap PR. Run pertamanya
  langsung menangkap `yarn.lock` yang drift (entri idb hilang).
- **Registry field aset** (`backend/asset_fields.py`): PATCH, ubah massal,
  audit, proyeksi list, CSV, impor diturunkan dari satu daftar + test
  anti-drift. Bonus: eselon1/2 kini terlacak audit.
- **Perbaikan laporan besar**: binding "Unit Organisasi" (dulu terisi nama
  kegiatan), blok identitas rata (tabel titik dua sejajar + baris NIP),
  penomoran BAHI/BA, "Halaman 2 dari N" eksekutif, Tim Inti/Pembantu muncul
  di Personil laporan satker, footer ekspor dobel, jam WIB, kartu KONDISI/
  STATUS tertukar, footer barang-serupa di tiap halaman, tanggal gaya
  Indonesia di semua laporan.
- pytest hygiene: 15 skrip test era scaffold dihapus, `pytest` default hanya
  test unit; test live-server ber-marker `integration`.

## [#38–#56] Ringkasan gelombang sebelumnya — 2026-07-08 s.d. 2026-07-10

Progres unduhan kartu; posisi tombol X pop-up; perbaikan header otorisasi
"pengguna melekat"; paritas ubah-massal dengan form edit; halaman riwayat
sebagai panel; verifikasi hasil scan terhadap kegiatan aktif; back/undo
browser tetap di aplikasi; GPS selalu realtime; baris terakhir laporan tak
tertimpa footer (running element); **Mode Kamera Penuh ala Timemark** dengan
alur beruntun + NUP dummy otomatis per perangkat; hapus baris optimistik
langsung hilang; **performa menyeluruh** (index Mongo, proyeksi list ramping,
virtualisasi kartu HP, streaming foto ber-ETag); **foto GridFS-only** dengan
migrasi terverifikasi; token media 30 hari; **deteksi versi baru otomatis**
("Muat Ulang" tanpa hapus cache); logo 3-klik ke halaman PRD; kartu tim
2 baris; **field NIP/NIK pegawai** end-to-end; label NIP/NIK + kolom Dari
Satker pada tim; gating auth batch endpoints; dokumen review refactoring.

## [#37] Kartu Inventarisasi cetak: presisi ke mockup + riwayat 8 baris — 2026-07-05

- **Riwayat** menyimpan: **petugas** (akun pelaku dari audit-log, fallback pelaku
  pengesahan), **nomor surat**, **dokumen** (checklist checked/total), dan
  **catatan** (notes aset) — semua di-snapshot saat pengesahan.
- **Depan Hal 1** disesuaikan presisi ke mockup: header dua baris (KARTU
  INVENTARIS + "Aset Tetap Milik Instansi"); **QR pindah ke kanan-atas** dekat
  kode (bukan footer); placeholder "FOTO ASET 4:3" + ikon kamera; badge jadi
  tiga kolom berlabel **STATUS · AKTIVITAS · NILAI PEROLEHAN**; footer **"ID
  ASET"** kotak gelap + ikon perisai + kode register, dan KODE|NUP di kanan.
- **Detail Administrasi**: KATEGORI → **PEROLEHAN DARI**, tile **KELENGKAPAN**
  (checked/total + %), Penanggung Jawab = pengguna + konteks melekat-ke; ikon
  vektor asli di semua label.
- **Riwayat 5 kolom** hemat ruang: NO · TIKET/TANGGAL · KEGIATAN (nama + No.
  Surat + Lokasi) · **PETUGAS/CATATAN** (catatan dapat ruang lebih) ·
  **KONDISI/DOK**. Menampilkan **8 baris** (4/halaman); bila >8, hanya **8
  terbaru** yang tampil (tertua mengalah), urut kronologis lama→baru.
- Panel **saling menempel** + garis lipat silang + label judul di tepi luar.
  Kartu massal memakai renderer sama.

## [#36] Redesain Kartu Inventarisasi cetak (4 panel + garis lipat + riwayat) — 2026-07-05

Kartu inventarisasi cetak (`cards.py`) dirombak sesuai contoh desain: **4 panel
dalam grid 2×2** pada satu halaman A4 landscape dengan **garis lipat** (dashed)
— vertikal antara Halaman 1 & 2, horizontal antara Tampak Depan & Belakang —
agar depan-belakang dan hal 1-2 menempel saat dilipat jadi kartu dua sisi:
- **Depan Hal 1**: header "KARTU INVENTARIS" + NUP, foto, KODE INVENTARIS besar,
  nama, grid spec (kategori/S-N/merek/lokasi), badge kondisi & status, Nilai
  Perolehan, footer QR asli (`#kode_register`) + ID/Kode/NUP.
- **Depan Hal 2**: "DETAIL ADMINISTRATIF" — tile eselon I/II, penanggung jawab,
  tgl/kontrak/BAST, lokasi/SPM/supplier/kategori.
- **Belakang Hal 1 & 2**: tabel "RIWAYAT INVENTARISASI" (No/Tanggal/Jenis
  Kegiatan/Lokasi/Petugas/Kondisi/Ket, 3 baris/halaman, footer "Halaman X dari 2").
- **Data riwayat** kini diambil dari `inventory_history` (per kode register /
  kode+NUP, scope satker) — sebelumnya kartu tak memuat riwayat.
Endpoint bulk memakai renderer sama (satu halaman lipat per aset). Diverifikasi
dengan render PDF → raster PNG.

## [#33] UX ronde B: validasi inline, aksesibilitas, empty/error state — 2026-07-05

- **Validasi inline**: error di form aset & kegiatan kini tampil di bawah field
  terkait (border merah + teks bantuan + `aria-invalid`), auto-scroll & pindah
  tab ke field pertama yang salah; toast jadi ringkasan singkat (bukan sumber
  detail).
- **Aksesibilitas**: baris tabel & kartu mobile bisa dioperasikan keyboard
  (Enter/Space, `role=button`, focus-ring); target sentuh aksi baris 20→28px;
  glyph status inventaris diberi label penuh + font dinaikkan; ukuran teks
  data (badge) di dua tampilan list utama dinaikkan; overlay buatan-sendiri
  (lightbox foto kegiatan, reset, restore) dapat `role=dialog aria-modal`,
  autofocus, Escape, dan focus-restore.
- **Empty/error state**: gagal muat kegiatan → kartu error + "Coba Lagi"
  (bukan seolah tak ada kegiatan); daftar aset kosong dibedakan: filter aktif →
  "tidak cocok" + Reset filter, vs kegiatan baru → "Belum ada aset" + CTA
  tambah; overlay blocking ekspor yang redundan dihapus.

## [#32] UX ronde A: pill pengesahan dashboard, dialog konfirmasi terpadu, paritas aksi mobile, branding — 2026-07-05

- **Pengesahan di layar kerja**: pill toolbar (admin) — "Siap disahkan" / "{n}
  syarat belum" / "Disahkan · {tiket}" — membuka dialog pengesahan langsung;
  tombol di kartu kegiatan dibuat selalu terlihat.
- **Dialog konfirmasi terpadu** (`ui/ConfirmDialog` + `useConfirm`): menggantikan
  semua `window.confirm`; hapus kegiatan (cascade) butuh ketik "HAPUS".
- **Paritas aksi mobile**: menu ⋯ (Kartu Inventarisasi / Riwayat / Cetak Kartu /
  Hapus) setara aksi baris desktop.
- **Branding/istilah**: wordmark AMAN, tahun copyright dinamis, "Users"→
  "Pengguna", "Logout"→"Keluar".

## [#31] Pengerasan keamanan menyeluruh (hasil audit) — 2026-07-05

> ⚠️ **Prasyarat deploy**: (1) `JWT_SECRET` **wajib** diset di environment —
> backend kini menolak boot tanpanya (menutup lubang secret hardcoded).
> (2) Set `ALLOWED_ORIGINS` (koma) bila domain frontend ≠
> `amanikn-inventarisasi.com`.

Audit adversarial menemukan bahwa banyak API inti **belum terproteksi auth**;
semua ditutup:

- **Auth gating ~54 handler**: seluruh CRUD aset & kegiatan, list/stats/
  analytics, ekspor CSV/PDF/XLSX, audit-log, semua generator laporan,
  report-settings (tulis→admin), compress-image, kartu cetak, validasi —
  kini `require_user`/`require_admin`. (Dulu bisa dihapus/dibaca **anonim**,
  termasuk `DELETE /inventory-activities` yang cascade hapus semua aset.)
- **JWT fail-fast** (tak ada lagi secret default), **CORS** dipin ke allowlist
  env (bukan `*` + credentials).
- **Auth media/preview via token** (`?token=`) untuk `<img>`/`window.open`
  (foto, checklist, BAST, dokumen pengesahan, preview laporan) — dulu terbuka
  anonim.
- **XSS**: Jinja `autoescape` diaktifkan di 7 environment (nilai user di-escape;
  HTML server-built dibungkus `Markup`); `doc-file` tak lagi menuruti MIME dari
  data user (paksa image/pdf + `X-Content-Type-Options: nosniff`).
- **ReDoS/regex injection**: input pencarian di-`re.escape` sebelum `$regex`.
- **Orphan GridFS**: hapus aset/kegiatan kini membersihkan foto/BAST/checklist.
- **Audit actor** diambil dari JWT (bukan header `X-Audit-User` yang bisa
  dipalsu); audit-log dibatasi `page_size` ≤200.
- **OTP debug** hanya keluar bila `ALLOW_DEBUG_OTP` & non-produksi; pesan error
  ke klien digeneralkan (detail hanya di log server).

Diverifikasi: 22/22 uji ASGI+mongomock (401 tanpa token, 200 dengan; delete
admin-only; regex literal; cleanup GridFS; XSS ter-escape); `yarn build`
bersih. Sisa yang di-defer terdokumentasi (mis. `doc-file` publik untuk tautan
spreadsheet — dikeraskan MIME/nosniff, konten sama tersedia lewat endpoint
checklist ber-token).

## [#28] Lingkup satker kartu, pengguna melekat-ke + BAST, validasi & backup parity — 2026-07-04

- **Kartu Inventarisasi per satker**: record `inventory_history` kini menyimpan
  kode/nama satker; query kartu difilter satker kegiatan aktif (record lama
  tanpa satker tetap tampil, ditandai legacy); satker tampil di header & baris.
- **Pengguna "Melekat ke"** (Individual/Jabatan/Operasional) + nama jabatan
  kondisional; **Nomor BAST + unggah dokumen BAST** per aset (PDF/JPG/PNG/WEBP
  ≤10MB, GridFS, preview setelah simpan, 423 saat terkunci, tanpa bump OCC).
  Field mengalir ke PATCH diff, list projection, snapshot offline, import,
  audit `TRACKED_FIELDS`, dan ekspor CSV (45 kolom) + XLSX.
- **Validasi pengesahan tambahan**: nol aset kategori dummy; semua aset wajib
  kode register, Eselon I/II, lokasi, dan pengguna — baris merah/hijau per
  syarat di dialog pengesahan; detail 400 teritemisasi pada `/sahkan`.
- **Pemeriksaan sistem lintas-fitur** (celah integrasi diperbaiki): whitelist
  snapshot offline kini membawa field pengguna/BAST (edit & tampilan offline
  tidak kehilangan nilainya); antrian offline **tidak auto-retry** simpanan
  yang ditolak 423 (kegiatan terkunci) — toast/pesan kunci jelas, hanya
  retry/dismiss manual; audit log untuk unggah/hapus dokumen pengesahan;
  label aksi "Pengesahan" + label field baru di panel audit; template import
  CSV/XLSX ikut memuat 3 kolom pengguna/BAST (dropdown Melekat Ke); reset
  sistem (HAPUS SEMUA) kini juga menghapus `inventory_history` + `counters`.
- **Paritas backup & restore**: backup kini mencakup `inventory_history` dan
  `counters` (sequence tiket — `_id` string dipertahankan); restore membangun
  ulang counter tiket dari `ticket_number` kegiatan (anti nomor duplikat saat
  restore backup lama) dan membangun ulang semua index; alasan skip koleksi
  transient (row_locks, otp_store, idempotency_keys, ws_events, backup_jobs)
  terdokumentasi. GridFS satu bucket `fs` — foto aset, dokumen kegiatan,
  dokumen pengesahan, dan BAST otomatis tercakup `export_gridfs`.
- **Dokumentasi**: `docs/PENGESAHAN.md` — alur tiket → pengesahan → kunci →
  kartu inventarisasi + format QR untuk operator.

## [#27] Tiket kegiatan, alur pengesahan + kunci, kartu inventarisasi, QR — 2026-07-04

- **Nomor tiket kegiatan** `INV-{tahun}-{seq}` (counter atomik di koleksi
  `counters`; backfill startup/lazy untuk kegiatan lama) — tampil di kartu
  kegiatan & header dashboard.
- **Pengesahan**: layak hanya bila semua aset sudah diinventarisasi & berfoto
  (dan total > 0); admin unggah ≥1 PDF bertanda tangan (GridFS, cek `%PDF`,
  ≤20MB) lalu `POST /sahkan` mengunci kegiatan secara atomik + menulis satu
  record `inventory_history` per aset (tiket, kegiatan, tanggal, identitas,
  snapshot status/kondisi/lokasi/pengguna).
- **Kunci ditegakkan server-side**: create/PUT/PATCH/DELETE/batch-update/
  bulk-delete/import (+ hapus kegiatan) → **423 "Kegiatan sudah disahkan dan
  terkunci"**; frontend menampilkan banner tersegel dengan tiket dan
  menyembunyikan edit/hapus/import/batch/FAB; antrian menampilkan 423 dengan
  jelas pada simpanan background.
- **Kartu Inventarisasi**: `GET /assets/kartu-inventarisasi` per
  `kode_register` atau `asset_code`+`NUP` → riwayat lintas kegiatan; dialog
  lazy dari header form edit & aksi baris tabel desktop.
- **QR**: hasil scan berawalan `#` dipakai verbatim sebagai kode_register;
  kartu cetak kini memuat QR asli berisi `#{kode_register}` (ReportLab
  QrCodeWidget — tanpa dependensi baru, fallback placeholder).

## [#26] Foto sebagai URL streaming cacheable + ruang teks baris maksimal — 2026-07-04

- **Media tidak lagi base64-in-JSON**: `GET /assets/{id}/photos/{i}` mendukung
  `?thumb=1` (thumbnail tersimpan per foto, generate on-the-fly untuk aset
  lama); ketiga endpoint streaming media mengirim `Cache-Control: private,
  max-age=86400` + ETag berbasis versi (304 If-None-Match).
- **Form edit tanpa roundtrip `/media`**: strip foto dibangun dari URL
  thumbnail per-index (`?thumb=1&v={version}`) dari `photo_count`/`version`
  fetch ringan — tiap `<img>` lazy-load progresif & ter-cache browser
  (`?v=` mem-bust cache setelah tiap edit); lightbox render foto pertama
  begitu byte-nya tiba (fallback data-URI dipertahankan).
- **UI list**: batas lebar keras (120/60/80px) kartu mobile dihapus —
  kategori/lokasi/eselon kini flex `min-w-0` (teks penuh tampil, ellipsis
  hanya saat benar-benar sempit); kolom Eselon/Lokasi tabel desktop xl
  berubah dari `w-20` tetap ke `flex-1 min-w-0` proporsional.

## [#25] Perbaikan offline: form edit dari cache + guard photo_ops destruktif — 2026-07-04

- **Edit offline berfungsi**: form edit kini terinisialisasi dari baris cache
  (snapshot offline) saat `GET /assets/{id}` tak terjangkau — dulu hanya toast
  error dan form kosong tak bisa disimpan. Simpan lewat PATCH diff
  non-destruktif dengan `If-Match` dari versi baris cache; notice amber bahwa
  foto/checklist penuh butuh koneksi. Error server nyata (404/401) tetap
  lewat jalur error eksplisit.
- **Guard data-loss laten**: bila media belum termuat, menambah foto tidak
  lagi mengirim `photo_ops keep:[]` yang menghapus semua foto lama
  server-side (`mediaLoadedRef` + `_photoCount` mempertahankan foto existing
  per index).
- Offline tanpa/kadaluarsa snapshot: pesan actionable ("Aktifkan Mode
  Inventarisasi saat online…") alih-alih "Gagal memuat data"; progress bar
  inventarisasi menampilkan angka terakhir yang diketahui per kegiatan
  (bukan 0/0).

## [#24] Laporan resmi: satu sistem desain rapi & profesional — 2026-07-04

Kedelapan laporan resmi ReportLab (Berita Acara, SPTJM, Surat Koreksi, DBHI ×6,
RHI, BAHI, SP Hasil, SP Pelaksanaan) kini memakai **satu sistem desain bersama**
(isi/teks hukum tidak diubah): blok judul+nomor seragam di bawah kop; gaya tabel
tunggal (header abu muda tebal, grid tipis, header berulang tiap halaman, zebra
lembut untuk DBHI/RHI, angka rata kanan, baris total tebal); blok tanda tangan
seragam (nama tebal bergaris bawah + NIP); **footer tiap halaman** (nama laporan
+ "Halaman X"); margin & tipografi Helvetica konsisten. Perbaikan nyata ikut:
sel NIP/nama panjang kini membungkus (dulu meluber), label total tak lagi patah
di tabel kosong. Laporan eksekutif tidak disentuh (sudah baik).

## [#23] Cache baca offline: mode inventarisasi berfungsi penuh tanpa koneksi — 2026-07-04

- **Snapshot data kegiatan** (proyeksi list + thumbnail, tanpa foto penuh) ke
  IndexedDB saat mode inventarisasi ON — sinkron **delta** via `updated_at`
  (endpoint ber-auth `GET /assets/offline-snapshot`, per-halaman 1000).
- **Saat offline**: daftar/cari/filter/sort dilayani dari cache lokal dengan
  banner "menampilkan data tersimpan (terakhir sinkron …)"; edit tetap lewat
  antrian persisten dan ikut di-upsert ke cache; lock dilewati optimistik
  (OCC menangkap konflik saat sinkron).
- **Online kembali**: flush antrian → delta-sync → data live.
- **Keamanan**: snapshot per user+kegiatan; dihapus saat logout manual & saat
  user berbeda login di perangkat sama (auto-logout 401/idle sengaja TIDAK
  menghapus — melindungi data lapangan); TTL 7 hari; `storage.persist()`.
- **Service worker**: precache app-shell agar aplikasi bisa dibuka cold-start
  saat offline.

## [#22] Tindak lanjut pematangan: kompresi offline, reachability, presence, WS auth — 2026-07-04

- **Kompresi foto offline**: bila server kompresi tak terjangkau/offline, foto
  dikompres lokal via canvas (1920px, q0.85) — base64 mentah hanya bila canvas
  gagal; berlaku di create, edit, dan foto checklist. Validasi pra-simpan
  dilewati saat offline (backend tetap memvalidasi saat sinkron).
- **Ping reachability**: `GET /api/health` baru; status online & auto-flush
  antrian diverifikasi dulu (timeout 3 dtk, retry 10 dtk) — Wi-Fi tanpa uplink
  tidak lagi mengaku online.
- **Presence lintas-worker**: daftar user online = gabungan snapshot semua
  worker via event bus (snapshot join/leave + periodik 30 dtk, kadaluarsa 60
  dtk, konvergensi cepat saat kontak pertama).
- **Autentikasi WebSocket**: koneksi WS wajib JWT (`?token=`); identitas
  diambil dari token, bukan parameter klien; token invalid ditutup kode 4401
  tanpa reconnect-loop.

## [#21] Pematangan kolaborasi & offline (hasil review menyeluruh) — 2026-07-04

Review mendalam stack kolaborasi + offline menemukan beberapa cacat serius;
semuanya diperbaiki:

- **Antrian simpan kini persisten (IndexedDB)** — sebelumnya hanya di RAM:
  app ditutup/di-logout (401) = semua simpanan offline **hilang**. Kini
  ter-rehydrate saat app dibuka lagi (baris + tombol retry muncul kembali)
  dan **auto-flush saat online kembali**. Indikator "N menunggu sinkron" &
  tombol Sync kini terhubung ke antrian sungguhan (dulu ke antrian mati).
- **Create gagal tidak menghapus barisnya lagi** — baris tetap tampil dengan
  status gagal + retry; hilang hanya lewat dismiss eksplisit.
- **Konflik 409 tidak lagi mengunci baris permanen di desktop** — status
  bersih otomatis (4 dtk), baris bisa diedit ulang; retry konflik memakai
  versi terbaru + idempotency key baru (dulu selalu 409 lagi selamanya).
- **Simpan ganda ke aset yang sama diserialisasi** — tak ada lagi 409 buatan
  sendiri saat save-cepat dua kali pada baris yang sama.
- **WebSocket**: reconnect kini melakukan satu catch-up refetch (event yang
  terlewat tidak hilang), tidak pernah menyerah permanen (backoff s/d 60 dtk),
  tab yang kembali visible + basi ikut refetch; refetch akibat event rekan
  di-debounce 2 dtk (anti badai refetch N×N saat banyak user menyimpan).
- **Backend**: TTL idempotency 5 menit → 24 jam (jeda offline realistis);
  TTL row-lock 300 dtk → 60 dtk (crash membebaskan baris ≤1 menit); broadcast
  unlock hanya setelah unlock DB sukses; bug fallback service-worker diperbaiki.

Tindak lanjut terdokumentasi (belum dikerjakan): kompresi foto client-side
saat offline, ping reachability (bukan hanya `navigator.onLine`), presence
lintas worker, autentikasi WebSocket, perampingan payload thumbnail per view.

## [#20] Toggle kolom di laporan Barang Serupa + progres unduhan seragam — 2026-07-04

- **Laporan Eksekutif per Barang Serupa kini ikut toggle kolom tambahan**
  (SPM/Perolehan/Kontrak/BAST/Supplier/S-N): nilai unik antar anggota kelompok
  ditampilkan ringkas di bawah Nama Barang (maks 3 + "+N lainnya"); param
  `detail_fields` yang sama dengan laporan data aset.
- **Progres unduhan seragam di seluruh aplikasi**: helper baru
  `downloadFileWithProgress` (toast: "Mengunduh … 2,4 MB (47%)"; tanpa persen
  bila server tak mengirim total; format KB/MB Indonesia) dipakai di **11 titik
  download**: export CSV/XLSX, laporan eksekutif + data per halaman + Barang
  Serupa, LHI/RHI/BAHI/SP/dokumen pendukung, 6 jenis DBHI, batch ZIP, laporan
  satker, template import CSV/XLSX, dan unduhan InfoPage (PPT/DOCX).
- Pengecualian sengaja: unduhan **backup** tetap anchor native — pendekatan
  blob terdokumentasi gagal di produksi untuk file ratusan MB; progres sudah
  ditampilkan UI unduhan browser.

## [#19] Lembar Inventarisasi Lapangan eksklusif (redesign) — 2026-07-04

Menggantikan panel "Aksi Cepat" tempelan (#18) dengan **tampilan input lapangan
eksklusif** (`InventoryFieldSheet`) yang mengambil alih seluruh body form saat
mode inventarisasi + edit aset:

- **Header identitas sticky** (read-only): kode aset mono + badge NUP + nama +
  penghitung "X/Y" — petugas memverifikasi barang, bukan mengetik ulang.
- **Kartu langkah bernomor** dengan bahasa visual seragam: 1 Status
  Inventarisasi (segmented 2×2), 2 Kondisi Fisik (segmented 3), kartu
  kondisional beraksen amber muncul sesuai status (Detail Tidak Ditemukan /
  Berlebih / Sengketa / Tindak Lanjut Rusak Berat — field sama persis dengan
  form penuh), 3 Foto (strip thumbnail + Kamera/Galeri), 4 Lokasi & Pengguna
  (+ baris GPS + salin dari aset sebelumnya), 5 Stiker, 6 Catatan (lipat).
- **Footer sticky**: "Simpan & Lanjut →" besar (jalur navigationIntent yang
  sama), Simpan, dan "Form Lengkap" (semua field tetap bisa diakses; banner
  "← Kembali ke Mode Cepat" di form penuh).
- Field meja (harga, SPM, kontrak, dsb.) tidak tampil di alur cepat.
- Logika simpan/validasi tidak diduplikasi — sheet murni presentasional di
  dalam `<form>` AssetForm yang sama.

## [#18] Mode Inventarisasi Lapangan: progres, aksi cepat, scan QR, GPS cache — 2026-07-04

Paket fitur untuk mempercepat input di lapangan (offline maupun kolaborasi online):

- **Bar progres inventarisasi** (`InventoryProgressBar`, tampil saat mode
  inventarisasi aktif): "Diinventarisasi X / Y" + persentase (refetch otomatis
  setelah save background & tiap 60 dtk), chip filter cepat **Belum / Ditemukan
  / Semua**, indikator offline + "N menunggu sinkron", dan badge **"N dikerjakan
  rekan"** (dari row-lock sesi lain).
- **Aksi Cepat Inventarisasi** di atas form (mode inventarisasi, saat edit):
  tombol besar sekali-ketuk untuk Status (Ditemukan/Tidak Ditemukan/Berlebih/
  Sengketa) dan Kondisi (Baik/RR/RB). Memakai logika clearing yang sama dengan
  Select lama (field klasifikasi ikut bersih saat status berganti).
- **"Salin dari aset sebelumnya"**: lokasi/eselon/pengguna aset yang baru
  disimpan tersimpan di `localStorage`; satu ketukan mengisi field yang masih
  kosong (tidak pernah menimpa isian).
- **Scan QR/barcode** (`QrScanButton` di samping kolom cari): kamera belakang +
  `BarcodeDetector`; hasil scan diekstrak (URL / `kode|NUP` / teks mentah) lalu
  masuk ke pencarian multi-kolom. Tombol tersembunyi otomatis di browser yang
  tak mendukung. Catatan: QR pada kartu cetak backend masih placeholder —
  scanner ini menyasar stiker bersistem eksternal (SIMAK-BMN dsb.).
- **Cache GPS**: fix terakhir (<5 menit) dipakai instan saat form butuh
  koordinat, lalu diperbarui di background — GPS indoor tidak lagi menahan
  input. (Tombol kamera langsung sudah ada sebelumnya — tidak diubah.)

## [#17] Laporan: Kop Surat di semua laporan resmi + Eksekutif per Barang Serupa + kolom detail opsional — 2026-06-16

- **Kop Surat (issue 6):** helper `_kop_surat_flowables()` baru — logo instansi
  (dari pengaturan "Sampul") + nama instansi/unit/alamat + garis ganda klasik —
  kini tampil di **semua 8 laporan resmi ReportLab**: Berita Acara, SPTJM,
  Surat Koreksi, DBHI (6 jenis), RHI, BAHI, SP Hasil, SP Pelaksanaan. Kop
  mengikuti pengaturan yang bisa diubah di panel "Sampul" (`ReportSettingsEditor`).
- **Laporan Eksekutif per Barang Serupa (issue 8):** endpoint & tombol unduh
  baru — aset dikelompokkan persis seperti panel Barang Serupa (kunci 6 kolom),
  termasuk aset tunggal, sehingga **total unit = total seluruh aset**. Foto
  perwakilan = anggota dengan **NUP terkecil**; NUP ditampilkan sebagai rentang
  ringkas ("1-3, 5, 7"). Template baru `executive_grouped.html`.
- **Kolom detail opsional (issue 9):** 6 toggle (SPM, Perolehan, Kontrak, BAST,
  Supplier, S/N) di bagian Laporan Eksekutif — jika aktif, ditambahkan rapi ke
  kolom "Kondisi & Status" laporan data aset (param `detail_fields`, tersimpan
  di localStorage).

## [#16] UX batch: input tak lagi terhapus, skeleton, auto-logout, dll — 2026-06-16
`80ac0e2`

- **Issue 1 (kritis):** ketikan hilang saat save background selesai → timer basi
  `handleFormClose` kini hanya menutup edit miliknya; init form di-key by id.
- **Issue 2/4/5:** skeleton loading (komponen `ListLoadingSkeleton`) untuk ganti
  page size / pindah halaman / filter / sort; refresh background tetap senyap.
- **Issue 3:** import — sel `status` kosong → "Aktif" (dan `condition` → "Baik").
- **Issue 7:** interceptor 401 → logout + redirect login; idle 30 menit → logout.
- **Issue 10:** kategori ber-label "dummy" → NUP otomatis via `GET /assets/next-nup`.

## [#15] Lightbox: efek glass kembali + panel info adaptif tema — 2026-06-16
`fba598f` — latar `bg-black/40` + blur; panel `bg-white/70`/`dark:bg-slate-900/70`;
badge dua-warna kontras di kedua mode.

## [#14] Lightbox: panel info gelap solid — 2026-06-16
`f4943c3` — digantikan oleh #15 (permintaan: efek glass dipertahankan).

## [#13] Lightbox: teks info tak terbaca di light mode — 2026-06-16
`97a988f` — `bg-black/92`/`bg-white/8` (step opacity non-standar) tidak
ter-generate Tailwind → overlay tak pernah gelap. Diganti step standar.

## [#11] Stats: tombol toggle Inventarisasi ringkas & seragam — 2026-06-16
`a3fdf5c`

- **Masalah:** di bar stat compact (tablet / HP-landscape, sm–lg / ≤1023px),
  kartu toggle "Inventarisasi" lebih **tinggi** dari kartu stat lain karena
  `Switch` (Radix `<button>`) dipaksa 44×44 oleh aturan global di atas.
- **Perbaikan (`StatsBar.jsx`):**
  - Hapus label teks "Inventarisasi" → cukup tombol toggle (hemat ruang);
    aksesibilitas dijaga via `aria-label` + `title`.
  - `min-h-0 min-w-0` pada `Switch` → kembali ke ukuran natural (`h-5 w-9`).
  - Baris compact dibuat `items-stretch` → kartu toggle setinggi kartu stat lain,
    switch di tengah.

## [#10] Stats: ruang lebih untuk "Total Nilai" di semua ukuran — 2026-06-16
`091ea1c`

- **Masalah:** angka rupiah ("Total Nilai") jauh lebih panjang dari kartu jumlah,
  tapi mendapat lebar yang sama → terasa sempit.
- **Perbaikan (`StatsBar.jsx`):**
  - Desktop (lg+): grid `grid-cols-4` → `grid-cols-[1fr_1.6fr_1fr_1fr]`
    (kolom Total Nilai **1.6×**); `min-w-0` agar nilai sangat panjang membungkus,
    bukan meluber.
  - Tablet/HP-landscape (sm–lg): kartu Total Nilai `flex-[1.7]` vs `flex-1`,
    plus `min-w-0` + `truncate` sebagai pengaman.
  - HP portrait (<sm): kartu stat memang tidak ditampilkan (hanya toggle).

## [#9] Kegiatan: badge status tidak lagi menutupi nomor surat — 2026-06-16
`2526f3a`

- **Masalah:** di ≤1023px, ribbon status (`Belum Dimulai`/`On Going`/…) — sebuah
  `<button>` `absolute top-0 left-0` — dipaksa setinggi 44px oleh aturan global,
  sehingga melewati jarak aman `pt-5` konten dan **menutupi baris nomor surat**.
- **Perbaikan (`ActivitySelectionPage.jsx`):** tambah `min-h-0 min-w-0 leading-none`
  pada tombol ribbon → kembali ke tinggi natural (~16px), nomor surat tampil penuh.

## [#8] List mobile: baris menyatu + "Barang Serupa" jadi batas scroll — 2026-06-16
`2170fd8`

- **Masalah A:** tiap kartu (`AssetMobileCard`) memakai `rounded-lg mb-1.5` → ada
  celah 6px di antara setiap baris.
- **Masalah B:** `VirtualizedMobileCards` berada di alur halaman biasa, jadi
  seluruh list (dan panel di atasnya, termasuk *Barang Serupa*) ikut ter-scroll
  hilang ke atas.
- **Perbaikan:**
  - `AssetMobileCard.jsx`: buang `rounded-lg` + `mb-1.5` → list rapi & menerus
    (pembatas baris tetap dari `border-y`).
  - `VirtualizedMobileCards.jsx`: bungkus dengan container scroll tinggi-tetap
    **sama dengan galeri** (`h-[calc(100dvh-140px)] sm:h-[calc(100dvh-280px)]`),
    dan `IntersectionObserver` infinite-scroll di-`root`-kan ke container itu →
    saat scroll, "Barang Serupa" mendarat di atas sebagai batas; muat-lebih-banyak
    tetap jalan.

## [#7] Galeri: ikon aksi kartu rapi & "Hapus" selalu tampil di HP — 2026-06-16
`8b2a829`

- **Masalah:** footer kartu galeri berisi 5 tombol ikon; aturan global memaksa
  tiap `<button>` ≥44px → 5×44=220px ke kartu ~158px → baris meluber dan
  `overflow-hidden` kartu **memotong ikon Hapus**. Terjadi di semua lebar HP
  (termasuk 375px).
- **Perbaikan:**
  - `AssetGalleryCard.jsx`: tiap tombol ikon footer `min-w-0 min-h-0`
    (+ `flex-shrink-0` pada ikon, `overflow-hidden` & jarak rata pada baris,
    hover state lembut) → strip rapi, semua ikon tampil.
  - `AssetGalleryView.jsx`: seed jumlah kolom **mobile-first** dari lebar viewport
    (default 2) → hilangkan "kedip" grid 4 kolom sesaat saat load.

## [#6] Pengamanan auth + integritas data — 2026-06-16
`e8e1074`

- **Auth endpoint destruktif:** endpoint yang sebelumnya jalan **tanpa verifikasi
  token** kini di-gate (frontend sudah mengirim `Authorization: Bearer` via
  interceptor axios global):
  - `require_user`: `POST /import`, `DELETE /assets/bulk-delete/{id}`,
    `PUT /assets/batch-update`, `POST /categories/import-bulk`,
    `POST /categories/import`.
  - `require_admin`: semua `/users/*` dan `DELETE /system/reset-all`
    (catatan: `change-password`/`change-role` sebelumnya tanpa auth sama sekali).
- **Idempotency race:** `reserve_idempotency_key()` mengklaim `Idempotency-Key`
  secara atomik sebelum bekerja (request kedua dengan key sama → `409`).
  **Fail-open** saat error infra; reservasi basi (>30s) bisa diambil alih.
- **Merge checklist:** PATCH `document_checklist` dulu mencocokkan item by-name via
  dict (item duplikat/kosong bisa saling tertukar / kehilangan foto). Sekarang
  mengonsumsi item existing by-name **berurutan** (deque) → duplikat aman.

## [#5] Testing + perbaikan audit log & broadcast batch — 2026-06-16
`e58e00d`

- **Audit log:** `compute_changes` dulu hanya mencatat penyelesaian dokumen saat
  **jumlah** item checklist berubah → centang/uncentang item yang sudah ada (jumlah
  tetap) tidak tercatat. Diperbaiki + test regresi.
- **Batch update WebSocket:** `batch.py` memanggil `notify_asset_change` dengan 1
  dict, padahal signature 5 argumen → `TypeError` (ditelan) sehingga viewer lain
  tak dapat refresh realtime setelah batch edit. Kini dipanggil benar.
- **Test:** tambah `backend/check_pure_logic.py` (auth hashing+JWT, `decode_data_url`,
  thumbnail/`_prepare_image`, `compute_changes`, formatter export, model pydantic,
  template Jinja2).

## [#4] Mobile: toggle mode ikon + scroll galeri berhenti di "Barang Serupa" — 2026-06-16
`b6e79fc`

- **StatsBar (HP):** toolbar atas diganti **satu tombol toggle ikon** yang jelas
  (Dashboard ↔ Inventarisasi).
- **Galeri:** offset window-scroll mobile diperbesar (170 → 140) supaya saat
  discroll ke bawah, "Barang Serupa" mendarat di dekat atas dan galeri mengisi
  sisanya. (Mekanisme ini kemudian disamakan untuk list mode di #8.)

## [#3] GPS opsional saat "Belum Diinventarisasi" + galeri mobile lebih padat — 2026-06-16
`546cce8`

- Tidak lagi mewajibkan titik GPS ketika status inventarisasi masih
  "Belum Diinventarisasi".
- Galeri mobile dibuat lebih padat (lebih banyak kartu per layar).

## [#2] Galeri mobile: densitas + popup foto (portal, scroll-lock, tombol) — 2026-06-16
`161e2d6`

- Perbaikan densitas galeri mobile dan popup foto: render via portal,
  penguncian scroll saat popup terbuka, serta tombol-tombolnya.

## [#1] Inisialisasi aplikasi AMAN — 2026-06-16
`36f8019`

- Menambahkan aplikasi AMAN secara lengkap, memperbaiki timeout export XLSX, dan
  merapikan repo.

---

## Peta file UI yang sering disentuh

| Area | File |
| --- | --- |
| Kartu galeri (footer ikon, dll.) | `frontend/src/components/assets/AssetGalleryCard.jsx` |
| Galeri (grid virtual, kolom, scroll) | `frontend/src/components/assets/AssetGalleryView.jsx` |
| Kartu list mobile | `frontend/src/components/assets/AssetMobileCard.jsx` |
| List mobile (scroll/infinite) | `frontend/src/components/assets/VirtualizedMobileCards.jsx` |
| Bar statistik + toggle inventarisasi | `frontend/src/components/assets/StatsBar.jsx` |
| Halaman pemilihan kegiatan (badge status) | `frontend/src/pages/ActivitySelectionPage.jsx` |
| Aturan global mobile (tap-target 44px) | `frontend/src/index.css` (≤1023px) |

## Breakpoint (Tailwind, lihat `frontend/tailwind.config.js`)

`xs 0` → `sm 640` → `md 768` → `lg 1024` → `xl 1280` → `2xl 1536`.
Aturan tap-target 44px aktif pada **≤1023px** (di bawah `lg`).
