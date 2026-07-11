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
