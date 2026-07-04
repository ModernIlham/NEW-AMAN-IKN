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
