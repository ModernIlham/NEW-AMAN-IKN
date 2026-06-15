<!-- Last updated: Feb 2026 v2.4 - Lazy-Load Asset Edit (Dokumen tab) + Lihat PDF Fix -->

# PRD - Sistem Inventaris Aset Terpadu (AMAN)
## Aplikasi Manajemen Aset Negara

**Versi: 2.4 (Feb 2026)** — Production-ready multi-worker dengan kolaborasi real-time anti-corruption + lazy-load kegiatan + lazy-load asset Dokumen tab + Lihat PDF fix

## 1. Ringkasan Produk

**AMAN** (Aplikasi Manajemen Aset Negara) adalah aplikasi web inventaris aset berbasis standar pemerintah Indonesia (LKPP 85/2025, SE 17/SE/M/2024) untuk pengelolaan Barang Milik Negara (BMN). Aplikasi mendukung proses inventarisasi lapangan, pencatatan aset, pelacakan status, manajemen tim, dan pembuatan laporan resmi dalam format PDF.

**Tech Stack v2.1**: React 19 + TailwindCSS + Shadcn/UI (Frontend) | FastAPI + Python 3.11 + Cross-Worker Event Bus (Backend) | MongoDB 7.0 standalone + GridFS + Capped Collection (Database) | WeasyPrint + Jinja2 + ReportLab (PDF) | WebSocket + Tailable Cursor (Real-time)

**Domain**: https://amanikn-inventarisasi.com

### Highlight v2.1 (Juli 2025)
- ⚛️ **OCC (Optimistic Concurrency Control)** — field `version` + `If-Match` header, anti lost-update
- 🔁 **Idempotency-Key** pada POST/PATCH — retry aman tanpa duplikasi
- 🔒 **Atomic Row Lock** — race-free via `find_one_and_update` + `insert_one` fallback
- 📦 **Client-side image compression** — payload 10x lebih kecil (5MB → ~500KB)
- 🔀 **Cross-Worker WebSocket Fanout** — MongoDB capped collection + tailable cursor, scale ke `--workers 4+` tanpa Redis
- 💓 **Server-initiated heartbeat** 25s — anti proxy timeout
- 🛡️ **GridFS auto-rollback** — no orphan blobs saat save gagal

### Highlight v2.2 (Feb 2026)
- 🐛 **OCC false-positive fix** — `aset telah diubah pengguna lain` palsu (saat solo session) sudah diperbaiki dengan handling missing version field
- 💾 **Backup/Restore lengkap** — termasuk `inventory_activities` + GridFS collections, ZIP background job dengan progress tracking
- 🖼️ **Gallery layout fix** — informasi card tidak terbenam, dynamic row heights
- 🔇 **401 polling spam fix** — BackgroundTaskBar tidak lagi spam request saat unauthenticated
- 📥 **Backup download** — query-param token + toast feedback (silent failure fixed)
- 👤 **Audit log username fix** — `X-Audit-User-Id` header propagated dari useOptimisticQueue
- 📱 **Mobile FAB scroll fix** — floating action button visible saat scroll
- 🖼️ **Cover thumbnail fix** — perubahan `thumbnail_index` benar-benar update gallery_thumbnail
- 🆕 **Status "Idle"** — opsi baru di AssetForm untuk asset yang belum digunakan
- ⚡ **Lazy-Load Activities** — list endpoint strip heavy `photos`/`documents`/`photo_thumbnails`, hanya kirim `photos_count`/`documents_count`. Edit form tidak load file sampai user klik tombol "Kelola Foto/Dokumen". Save tanpa lazy-load TIDAK menghapus data (null sentinel).
- 🚦 **Activity Status Ribbon** — badge clickable di tiap card (Belum Dimulai/On Going/Validasi/Selesai/Belum Lengkap) berdasarkan tanggal + asset inventory completeness. Klik membuka dialog validasi yang memanggil `/completion-status` (cek total aset, pending inventarisasi, no-photo count).
- 🔢 **Activity max-file enforcement** — backend reject 400 jika photos > 10 atau documents > 5

### Highlight v2.3 (Feb 2026 — Bugfix Drop)
- 📑 **Template Excel — single source of truth** — `templates.py` direfaktor pakai `ASSET_TEMPLATE_SCHEMA` (list of dict), header/sample/dropdown/widths/Panduan semua diturunkan dari satu list yang sama. Bug header & data tidak align teratasi (`eselon2` sample shifting), 5 field baru ditambahkan (kronologis, koordinat_lat/long, keterangan_berlebih, asal_usul_berlebih, nomor_perkara, pihak_bersengketa, keterangan_sengketa). Template otomatis sync dengan kategori DB.
- 🛠️ **Template Excel — silent xlsxwriter dropdown bug fixed** — `error_title` >32 char dan source list >255 char menyebabkan dropdown drop diam-diam (cols 25, 26). Fix: title clamped ke 32, long source pakai hidden `_lists` sheet via range reference.
- 📦 **Activity PDF compression + GridFS migration** — endpoint `/api/compress-pdf` (iLoveAPI → WhipDoc fallback) sekarang dipanggil dari frontend (`pdfCompression.js`) dan juga server-side di `process_activity_documents`. PDF disimpan ke GridFS keyed only by `gridfs_id` di parent doc → tidak lagi hit MongoDB BSON 16MB limit, tidak ada lagi timeout saat upload 5 PDF.
- 🌊 **Activity document streaming** — `GET /api/inventory-activities/{id}/documents/{idx}` streams PDF dari GridFS, frontend buka tab dengan URL ini (tidak transfer base64 di JSON).
- 🧹 **Orphan GridFS cleanup** — PUT yang menghapus dokumen otomatis hapus GridFS blob, DELETE kegiatan juga hapus semua dokumennya.
- 📤 **Frontend handleDocUpload (3 tempat)** — `ActivitySelectionPage.jsx`, `DocumentChecklist.jsx`, `BatchEditPanel.jsx` semua pakai `compressPdfFile` helper baru, dengan progress toast & graceful fallback ke file asli jika kompresi gagal. Limit naik 15→25MB karena ada kompresi.

### Highlight v2.4 (Feb 2026 — Lazy-Load Asset Dokumen Tab)
- 🔧 **Bug fix: "Data PDF tidak valid" pada Lihat PDF** — Sebelumnya saat edit aset, endpoint `/media` hanya mengembalikan `documents: [{name}]` tanpa field `data`, sehingga tombol Lihat selalu memunculkan toast "Data PDF tidak valid". Fix: tambah endpoint baru `GET /api/assets/{asset_id}/checklist-full` yang mengembalikan checklist lengkap dengan photo data URLs dan PDF data URLs.
- 🖼️ **Bug fix: Photo thumbnails kelengkapan tidak muncul** — `DocumentChecklist` membaca `item.photos`, tapi `/media` hanya mengisi `photo_thumbnails`. Setelah lazy-load `/checklist-full`, `item.photos` terisi data URL → thumbnail tampil normal.
- 🛡️ **Bug fix (regression): existing photo/PDF tidak terhapus saat save** — Tanpa lazy-load checklist-full, modifikasi checklist (toggle checkbox dst.) menyebabkan `cleanedChecklist` mengirim `photos: []` & `data: ''` → backend overwrite → data hilang. Fix: form sekarang wajib menunggu checklist-full ter-load sebelum tab Dokumen interaktif (loader dengan `data-testid='checklist-loading'`), `originalDataRef` di-update setelah lazy-load supaya dirty-tracking benar.
- ⚡ **Lazy-Load Edit Asset Dokumen tab** — Phase 1 (light data), Phase 2 (photo thumbnails + counts), Phase 3 (lazy on tab click): `checklist-full` baru di-fetch saat user klik tab "Dokumen" pertama kali. Phase 1 dan 2 tetap instan, payload berat hanya ditarik saat dibutuhkan.

---

## 2. Arsitektur Sistem

### 2.1 Backend Core (`/app/backend/`)

| File | Baris | Fungsi |
|------|-------|--------|
| `server.py` | ~302 | Entry point FastAPI, router mounting, database indexes (TTL idempotency/OTP/presence, unique row_locks), event_bus lifecycle hooks, GzipMiddleware, health check, system reset |
| `db.py` | 23 | Koneksi MongoDB (motor async) + GridFS bucket via `MONGO_URL` |
| `models.py` | 218 | 16+ Pydantic models: UserCreate, UserLogin, UserResponse, TokenResponse, OTPRequest, OTPVerify, UserUpdate, CategoryCreate, CategoryResponse, DocumentCheckItem, AssetCreate, AssetResponse (dgn `version` field), InventoryActivityCreate, InventoryActivityResponse, ResetConfirmation |
| `auth_utils.py` | 46 | JWT token generation & verification (PyJWT) |
| `shared_utils.py` | ~312 | GridFS photo helpers, rate limiter, TTLCache, Tinify/Resend config, OTP store, audit logging, compute_changes, thumbnail generation, **idempotency helpers (get/store_idempotent_response)**, inventory constants |
| `event_bus.py` | 138 | **NEW v2.1** — Cross-worker event fanout via MongoDB capped collection (`ws_events`, 10MB/20k) + tailable cursor. Unique WORKER_ID per process. Auto-create collection, graceful fallback. |

### 2.2 Backend Routes (`/app/backend/routes/`) — 19 Modules, ~10.500 Baris

| Route File | Baris | Fungsi |
|------------|-------|--------|
| `auth.py` | 268 | Register, Login, OTP verification (Resend email), Heartbeat, Me |
| `assets.py` | 901 | CRUD aset, pagination, filter, analytics, stats, PATCH dirty-tracking, GridFS photo serve, migrate-gridfs |
| `activities.py` | 428 | CRUD kegiatan inventarisasi, satker lookup, tim inventarisasi, cascade delete |
| `categories.py` | 266 | CRUD kategori, delete all, bulk import, import progress |
| `batch.py` | 416 | Row locking (lock/heartbeat/unlock/locks), batch update, asset groups (Barang Serupa), all-ids |
| `exports.py` | 937 | Export CSV/XLSX/PDF dengan foto HD, kelengkapan dokumen, doc-file serve, bulk delete |
| `imports.py` | 409 | Import aset dari CSV/XLSX, validasi kode aset/kategori/duplikat, activity_id scoping |
| `reports.py` | 2.410 | 13+ jenis laporan PDF resmi, Executive Summary, LHI package, report settings, logo management |
| `cards.py` | 436 | KTP card PDF per aset, bulk generation |
| `backup.py` | 575 | Background backup & restore (ZIP), job management, download, dismiss |
| `audit.py` | 33 | Audit log query |
| `media.py` | 355 | Kompresi gambar otomatis: Tinify → Compresto → Uploadcare → Pillow (local), quota tracking |
| `pdf_compress.py` | 248 | Kompresi PDF: iLoveAPI (4-step) → WhipDoc, quota tracking |
| `documents.py` | 1.053 | Generate presentasi PPT (python-pptx) & proposal DOCX (python-docx) otomatis |
| `users.py` | 126 | Manajemen user admin: list, toggle active, change password, update name, delete, change role |
| `validation.py` | 65 | Validasi data aset (kode aset, kode register, SPM) |
| `templates.py` | 290 | Download template CSV/XLSX untuk import (dengan header, contoh, dropdown) |
| `websocket.py` | 129 | WebSocket real-time: asset changes, user presence, row locking broadcast |
| `__init__.py` | 1 | Module init |

### 2.3 Frontend Pages (`/app/frontend/src/pages/`) — 4 Halaman

| Page | Baris | Fungsi |
|------|-------|--------|
| `LoginPage.jsx` | 379 | Autentikasi (username/password + OTP email) |
| `ActivitySelectionPage.jsx` | 1.150 | Pilih/buat kegiatan, setting satker, tim, eselon, penanggung jawab, berita acara |
| `DashboardPage.jsx` | 832 | Dashboard utama: tabel aset, form edit, toolbar, statistik, export, import |
| `InfoPage.jsx` | 556 | Halaman informasi: panduan, arsitektur, RAB, fitur, statistik server |

### 2.4 Frontend Components (`/app/frontend/src/components/`) — 35+ Komponen

#### Komponen Aset (`components/assets/`) — 28 file, 7.014 baris

| Component | Baris | Fungsi |
|-----------|-------|--------|
| `AssetForm.jsx` | 1.284 | Form CRUD aset (13 section: identitas, detail, organisasi, status, stiker, inventarisasi, GPS, dokumen, foto) |
| `BatchEditPanel.jsx` | 615 | Panel batch edit multi-aset |
| `UserManagementDialog.jsx` | 499 | Admin: kelola user (toggle, password, delete, role) |
| `AssetGalleryView.jsx` | 372 | Gallery view aset dengan card visual |
| `AuditLogPanel.jsx` | 335 | Panel riwayat perubahan |
| `AssetGalleryCard.jsx` | 311 | Card individual untuk gallery view |
| `VirtualizedAssetTable.jsx` | 291 | Tabel aset virtualized untuk dataset besar |
| `AdvancedFilter.jsx` | 281 | Filter multi-kriteria (lokasi, kondisi, status, inventarisasi, stiker) |
| `DashboardToolbar.jsx` | 274 | Toolbar (search, filter, view mode, export, import) |
| `AnalyticsPanel.jsx` | 258 | Panel analitik dengan chart & statistik |
| `AssetMobileCard.jsx` | 249 | Card aset untuk tampilan mobile |
| `DocumentChecklist.jsx` | 243 | Checklist kelengkapan dokumen per aset |
| `CategoryManagerDialog.jsx` | 233 | CRUD kategori aset |
| `CategorySelect.jsx` | 204 | Dropdown pemilihan kategori |
| `AssetGroupsPanel.jsx` | 219 | Panel Barang Serupa (NUP ranges, batch edit) |
| `TinifyQuotaIndicator.jsx` | 182 | Indikator quota kompresi (image + PDF) |
| `AssetTableRow.jsx` | 160 | Baris tabel individual dengan status badge |
| `ReportSettingsEditor.jsx` | 146 | Setting laporan (logo, cover page) |
| `RekapitulasiPanel.jsx` | 142 | Rekapitulasi statistik kegiatan |
| `ImportDialog.jsx` | 140 | Dialog import aset (CSV/XLSX) |
| `VirtualizedMobileCards.jsx` | 105 | Tampilan card mobile virtualized |
| `ScrollToTop.jsx` | 102 | Button scroll to top + posisi memory |
| `DashboardHeader.jsx` | 93 | Header dashboard dengan info kegiatan |
| `AssetPagination.jsx` | 70 | Navigasi halaman |
| `StatsBar.jsx` | 66 | Bar statistik ringkas |
| `BulkDeleteDialog.jsx` | 64 | Konfirmasi hapus massal |
| `LoadingIndicator.jsx` | 60 | Indikator loading |
| `index.js` | 16 | Re-exports |

#### Sub-komponen Rekapitulasi (`components/assets/rekapitulasi/`) — 5 file, 567 baris

| Component | Baris | Fungsi |
|-----------|-------|--------|
| `ReportDownloads.jsx` | 345 | Button download semua jenis laporan PDF |
| `SummaryCards.jsx` | 81 | Card ringkasan (total, ditemukan, tidak ditemukan) |
| `ConditionBreakdown.jsx` | 52 | Breakdown per kondisi aset |
| `InventoryProgress.jsx` | 47 | Progress bar inventarisasi |
| `TidakDitemukanBreakdown.jsx` | 42 | Breakdown detail aset tidak ditemukan |

#### Komponen Lain

| Component | Baris | Fungsi |
|-----------|-------|--------|
| `BackgroundTaskBar.jsx` | 260 | Status bar untuk background tasks (backup, restore, save queue) |
| `ui/` (47 files) | — | Komponen Shadcn/UI (accordion, alert, badge, button, calendar, card, dialog, dropdown, form, input, select, sheet, table, tabs, toast, tooltip, dll) |

### 2.5 Custom Hooks (`/app/frontend/src/hooks/`) — 9 Hooks, 973 baris

| Hook | Baris | Fungsi |
|------|-------|--------|
| `useOptimisticQueue.js` | 164 | Background save queue, optimistic UI, concurrent processing, deferred refresh |
| `useWebSocket.js` | 157 | Koneksi WebSocket real-time, broadcast asset changes, user presence |
| `use-toast.js` | 155 | Toast notification system |
| `useOfflineSync.js` | 148 | Offline synchronization support |
| `useAssetFilters.js` | 104 | State management untuk filter aset |
| `useRowLocking.js` | 98 | Multi-row locking, heartbeat, unlock |
| `usePullToRefresh.js` | 65 | Pull-to-refresh pada mobile |
| `useDragDropImport.js` | 58 | Drag & drop import file |
| `useDarkMode.js` | 24 | Toggle dark/light mode |

---

## 3. Fitur Utama (Detail)

### 3.1 Autentikasi & Otorisasi
- **Login**: Username/password dengan JWT token
- **Register**: Dengan OTP email verification (Resend API)
- **Role**: `admin` (full access), `user` (limited — no edit/delete)
- **Session**: Heartbeat system untuk mendeteksi user aktif
- **Rate Limiting**: Proteksi brute-force pada login/register (slowapi)

### 3.2 Kegiatan Inventarisasi (Activity)
- **CRUD Kegiatan**: Buat, edit, hapus kegiatan inventarisasi
- **Cascade Delete**: Hapus kegiatan → otomatis hapus semua aset terkait
- **Informasi Satker**: Kode & nama satker (lookup dari database), alamat, Kasatker (nama/NIP/jabatan)
- **Eselon**: Hirarki Eselon I → Eselon II (multiple per Eselon I)
- **Tim Inventarisasi** (4 jenis):
  - **Tim Inti (Internal)**: Nama, jabatan, NIP, unit, peran (Ketua/Anggota)
  - **Tim Pembantu (Internal)**: Nama, jabatan, NIP, unit, peran (Ketua/Anggota)
  - **Tim Peneliti (Eksternal)**: Nama, jabatan, NIP
  - **Tim Pendukung (Eksternal)**: Nama, jabatan, NIP, dari pihak
- **Penanggung Jawab**: Nama, jabatan, NIP
- **Berita Acara**: Nomor, tanggal, kesimpulan
- **Dokumen Pendukung**: Upload foto & dokumen kegiatan

### 3.3 Manajemen Aset (CRUD)
- **Data Identitas**: Kode aset, NUP, nama aset, kategori, serial number, kode register
- **Detail Perolehan**: Brand, model, tanggal beli, harga, nomor SPM, perolehan dari, nomor kontrak, bukti perolehan, supplier
- **Organisasi**: Eselon I, Eselon II, pengguna, lokasi
- **Kondisi & Status**: Baik/Rusak Ringan/Rusak Berat, Aktif/Maintenance/Nonaktif
- **Stiker**: Status (Belum Terpasang/Sudah Terpasang), ukuran (Kecil/Sedang/Besar), foto stiker
- **Foto Aset**: Multiple foto dengan gallery, pilih cover photo (thumbnail_index), foto stiker (stiker_photo_index)
- **GridFS Storage**: Foto disimpan di MongoDB GridFS untuk performa optimal
- **Kelengkapan Dokumen**: Checklist item (nama, status Ada/Tidak Ada, catatan, foto bukti, file PDF)
- **GPS Koordinat**: Latitude & longitude
- **Catatan**: Field notes bebas
- **Uniqueness**: asset_code + NUP unik per activity_id; kode_register unik per activity_id

### 3.4 Status Inventarisasi (SE 17/SE/M/2024)
- **Belum Diinventarisasi**: Default awal
- **Ditemukan**: Aset ditemukan sesuai data
- **Tidak Ditemukan**: Dengan klasifikasi:
  - Kesalahan Pencatatan: Salah Kode/NUP, Salah Pembukuan, Perubahan Kondisi, Sudah Dihibahkan, Sudah Dihapuskan, Pencatatan Ganda, Pemecahan/Penggabungan, Transfer Belum Diproses
  - Tidak Ditemukan Lainnya: Hilang/Dicuri, Rusak Total/Hancur, Bencana Alam, Lainnya
  - Uraian tidak ditemukan, tindak lanjut, kronologis
- **Berlebih**: Keterangan, asal usul berlebih
- **Sengketa**: Nomor perkara, pihak bersengketa, keterangan

### 3.5 Dirty-Tracking & Partial Update (PATCH)
- Hanya field yang diubah yang dikirim ke server
- Endpoint `PATCH /api/assets/{asset_id}`
- Mengurangi payload dan mencegah overwrite data concurrent

### 3.6 Optimistic Save Queue
- Background save queue (concurrent max parallel)
- Optimistic UI: data langsung terupdate tanpa menunggu server
- **Deferred Refresh**: Jika user sedang edit, refresh ditunda sampai form ditutup
- Status tracking: queued → saving → saved/failed
- Retry mechanism

### 3.7 Row Locking (Concurrent Editing)
- Row di-lock saat user edit — user lain tidak bisa edit bersamaan
- **Multi-lock**: User bisa lock multiple rows (Save & Navigate)
- Heartbeat refresh + auto-release jika disconnect
- TTL index di MongoDB untuk auto-cleanup
- Visual indicator row terkunci

### 3.8 WebSocket Real-Time
- **Asset Changes**: Broadcast saat aset dibuat/diupdate/dihapus
- **User Presence**: Lihat user lain yang sedang online
- **Lock Broadcast**: Notifikasi lock/unlock row
- **Deferred Refresh**: WS event saat editing ditunda

### 3.9 Import & Export

#### Import (CSV/XLSX)
- Upload file CSV atau XLSX
- Validasi: format kode aset, duplikasi (per activity), kategori match
- Auto-create kategori baru
- Force update mode
- Scoped per activity_id

#### Export CSV
- Streaming export, 41 kolom, UTF-8
- Header kegiatan sebagai komentar

#### Export XLSX (Excel)
- **Sheet 1 - Data Aset**: 41 kolom + foto thumbnail HD (800x800) + foto stiker
- **Sheet 2 - Kelengkapan Dokumen**: Checklist per aset, thumbnail foto, link PDF (hanya item Ada)
- **Sheet 3 - Data Kegiatan**: Info kegiatan terstruktur
- **Sheet 4 - Tim Inventarisasi**: Tabel per tim

#### Export PDF
- Landscape A4, tabel dengan foto thumbnail
- Summary box, color-coded, halaman numbered

### 3.10 Laporan PDF Resmi (13+ Jenis)

| Laporan | Endpoint | Keterangan |
|---------|----------|------------|
| **DBHI** (6 tipe) | `/api/.../dbhi/{type}` | Daftar Barang Hasil Inventarisasi |
| **RHI** | `/api/.../rhi-pdf` | Ringkasan Hasil Inventarisasi |
| **BAHI** | `/api/.../bahi-pdf` | Berita Acara Hasil Inventarisasi |
| **SP Hasil** | `/api/.../sp-hasil-pdf` | Surat Pernyataan Hasil |
| **SP Pelaksanaan** | `/api/.../sp-pelaksanaan-pdf` | Surat Pernyataan Pelaksanaan |
| **Berita Acara** | `/api/.../berita-acara-pdf` | Berita Acara |
| **SPTJM** | `/api/.../sptjm-pdf` | Surat Pertanggungjawaban Mutlak |
| **Surat Koreksi** | `/api/.../surat-koreksi-pdf` | Surat Koreksi Inventarisasi |
| **Executive Summary** | `/api/.../executive-summary-pdf` | Ringkasan eksekutif (WeasyPrint + Jinja2) |
| **Executive Data** | `/api/.../executive-data-pdf` | Data detail paginasi |
| **Laporan Satker** | `/api/.../laporan-satker-pdf` | Laporan per satuan kerja |
| **LHI Package** | `/api/.../lhi-pdf` | Gabungan semua laporan (merged PDF) |
| **Batch ZIP** | `/api/.../batch-pdf-zip` | Download beberapa laporan (ZIP) |

- **Report Settings**: Logo custom, info cover page, disimpan di database
- **Template HTML**: Jinja2 (`executive_summary.html`, `executive_summary_data.html`, `laporan_satker.html/v2`)
- **PDF Engine**: WeasyPrint (template HTML), ReportLab (tabel data)

### 3.11 Kompresi Media

#### Kompresi Gambar (Fallback Chain)
1. **Tinify** (TinyPNG) — 500/bulan
2. **Compresto** — 500/bulan
3. **Uploadcare** — 1.000/bulan
4. **Pillow** (lokal) — unlimited

#### Kompresi PDF (Fallback Chain)
1. **iLoveAPI** — 250/bulan (4-step: start → upload → process → download)
2. **WhipDoc** — 50/bulan

Quota tracking per service per bulan di MongoDB.

### 3.12 Dokumen Generator
- **Presentasi PPT**: Generate otomatis menggunakan python-pptx
- **Proposal DOCX**: Generate otomatis menggunakan python-docx

### 3.13 Barang Serupa (Asset Groups)
- Pengelompokan aset berdasarkan kode aset sama
- NUP ranges, jumlah member, detail per member
- Integrasi batch edit

### 3.14 KTP Card
- PDF kartu identitas aset (individual & bulk)
- Layout: foto, identitas, kode aset, NUP, lokasi

### 3.15 Backup & Restore
- Background backup (ZIP) — async job
- Background restore — async job
- Job tracking: progress, status, error
- Auto-cleanup file lama

### 3.16 Analytics & Rekapitulasi
- **Analytics**: Chart distribusi kondisi, status, kategori
- **Rekapitulasi**: total BMN, ditemukan/tidak ditemukan, breakdown klasifikasi, sub-klasifikasi
- **Filter Options**: Dynamic filter values

### 3.17 Audit Log
- Tracking semua perubahan (create/update/delete)
- Detail field yang berubah (before/after)
- Timestamp & username

### 3.18 Manajemen User (Admin)
- List user, toggle active/inactive
- Change password, update name, change role
- Delete user
- **System Reset**: Hidden feature, hapus semua data (ketik "HAPUS SEMUA")

### 3.19 Halaman Info
- Panduan penggunaan langkah demi langkah
- Arsitektur sistem visual
- RAB (Rencana Anggaran Biaya)
- Daftar fitur lengkap
- Statistik server real-time

---

## 4. Model Data (MongoDB Collections)

### 4.1 Collection: `assets`
```json
{
  "id": "uuid",
  "asset_code": "8010101999",
  "NUP": "1",
  "asset_name": "Laptop Dell Latitude",
  "category": "Komputer",
  "brand": "Dell",
  "model": "Latitude 5520",
  "kode_register": "",
  "serial_number": "SN12345",
  "purchase_date": "2024-01-15",
  "purchase_price": "15000000",
  "location": "Gedung A Lt.2",
  "eselon1": "Deputi Bidang X",
  "eselon2": "Biro Y",
  "user": "John Doe",
  "condition": "Baik|Rusak Ringan|Rusak Berat",
  "status": "Aktif|Maintenance|Nonaktif",
  "nomor_spm": "02060T/621001/2025",
  "perolehan_dari_nama": "PT Supplier",
  "nomor_kontrak": "KTR/001/2024",
  "nomor_bukti_perolehan": "BP/001",
  "supplier": "PT Supplier",
  "notes": "Catatan",
  "photos": ["data:image/jpeg;base64,..."],
  "photo_gridfs_ids": ["gridfs_id_1", "gridfs_id_2"],
  "thumbnail": "data:image/jpeg;base64,...(50x50)",
  "gallery_thumbnail": "data:image/jpeg;base64,...(256x256)",
  "thumbnail_index": 0,
  "document_checklist": [
    {"name": "Buku Manual", "checked": true, "notes": "", "photos": [], "documents": []}
  ],
  "activity_id": "uuid",
  "stiker_status": "Belum Terpasang|Sudah Terpasang",
  "stiker_ukuran": "Kecil|Sedang|Besar",
  "stiker_photo_index": null,
  "inventory_status": "Belum Diinventarisasi|Ditemukan|Tidak Ditemukan|Berlebih|Sengketa",
  "klasifikasi_tidak_ditemukan": "",
  "sub_klasifikasi": "",
  "uraian_tidak_ditemukan": "",
  "tindak_lanjut": "",
  "koordinat_latitude": "-6.200000",
  "koordinat_longitude": "106.816666",
  "kronologis": "",
  "keterangan_berlebih": "",
  "asal_usul_berlebih": "",
  "nomor_perkara": "",
  "pihak_bersengketa": "",
  "keterangan_sengketa": "",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-02-28T05:00:00Z"
}
```

### 4.2 Collection: `inventory_activities`
```json
{
  "id": "uuid",
  "nomor_surat": "SURAT/001/2026",
  "nama_kegiatan": "Inventarisasi BMN 2026",
  "deskripsi": "Kegiatan inventarisasi tahunan",
  "tanggal_mulai": "2026-01-01",
  "tanggal_selesai": "2026-03-31",
  "penanggung_jawab": "Nama PJ",
  "penanggung_jawab_jabatan": "Kepala Biro",
  "penanggung_jawab_nip": "198001012005011001",
  "kode_satker": "0000134",
  "nama_satker": "SATKER XYZ",
  "alamat_satker": "Jl. Sudirman No.1",
  "eselon1": [
    {"nama": "Deputi Bidang A", "eselon2": ["Biro X", "Biro Y"]}
  ],
  "tim_inti": [
    {"nama": "Ahmad", "jabatan": "Koordinator", "nip": "19800101", "unit": "Biro Umum", "is_ketua": true}
  ],
  "tim_pembantu": [
    {"nama": "Budi", "jabatan": "Staff", "nip": "19900202", "unit": "Biro TI", "is_ketua": false}
  ],
  "tim_peneliti": [
    {"nama": "Dr. Siti", "jabatan": "Auditor", "nip": "19850303"}
  ],
  "tim_pendukung": [
    {"nama": "Charlie", "jabatan": "Konsultan", "nip": "19950404", "dari_pihak": "PT Audit"}
  ],
  "kasatker_nama": "Nama Kasatker",
  "kasatker_nip": "197001012000011001",
  "kasatker_jabatan": "Kepala Satuan Kerja",
  "nomor_berita_acara": "BA/001/2026",
  "tanggal_berita_acara": "2026-03-31",
  "kesimpulan": "Inventarisasi berjalan lancar",
  "photos": [],
  "documents": [],
  "status": "Aktif",
  "created_at": "2026-01-01T00:00:00Z"
}
```

### 4.3 Collection: `categories`
```json
{
  "id": "uuid",
  "label": "Laptop",
  "kode_aset": "8010101999",
  "created_at": "2026-01-01T00:00:00Z"
}
```

### 4.4 Collection: `users`
```json
{
  "id": "uuid",
  "username": "admin",
  "password_hash": "$2b$...",
  "name": "Administrator",
  "role": "admin|user",
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z"
}
```

### 4.5 Collection: `audit_logs`
```json
{
  "id": "uuid",
  "action": "update",
  "activity_id": "uuid",
  "asset_id": "uuid",
  "asset_code": "8010101999",
  "nup": "1",
  "asset_name": "Laptop",
  "username": "admin",
  "changes": [{"field": "condition", "from": "Baik", "to": "Rusak Ringan"}],
  "detail": "",
  "timestamp": "2026-02-28T05:00:00Z"
}
```

### 4.6 Collection: `report_settings`
```json
{
  "id": "report_settings",
  "kop_kiri": "KEMENTERIAN XYZ",
  "kop_kanan": "INSPEKTORAT",
  "nama_instansi": "Nama Instansi",
  "alamat": "Jl. Sudirman No.1",
  "telepon": "021-1234567",
  "website": "www.instansi.go.id",
  "logo_base64": "data:image/png;base64,..."
}
```

### 4.7 Collection: `backup_jobs`
```json
{
  "id": "uuid",
  "type": "backup|restore",
  "status": "running|done|failed",
  "progress": 75,
  "message": "Proses backup...",
  "file_path": "/path/to/backup.zip",
  "created_by": "admin",
  "created_at": "2026-02-28T05:00:00Z"
}
```

### 4.8 Collection: `compression_quotas` & `pdf_compression_quotas`
```json
{
  "service": "tinify|compresto|uploadcare|iloveapi|whipdoc",
  "month": "2026-07",
  "used": 42,
  "limit": 500
}
```

### 4.9 Collection: `row_locks` (TTL auto-expire)
```json
{
  "asset_id": "uuid",
  "locked_by": "admin",
  "locked_by_name": "Administrator",
  "expires_at": "2026-07-01T10:05:00Z"
}
```

### 4.10 Collection: `otp_store` (TTL auto-expire)
```json
{
  "email": "user@example.com",
  "otp": "123456",
  "user_data": {"username": "...", "name": "..."},
  "expires_at": 1719900000,
  "created_at": "2026-07-01T10:00:00Z"
}
```

---

## 5. API Endpoint Reference (88+ Endpoints)

### Auth (`/api/auth/`)
| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/auth/register` | Register user baru |
| POST | `/auth/request-otp` | Kirim OTP ke email |
| POST | `/auth/resend-otp` | Kirim ulang OTP |
| POST | `/auth/verify-otp` | Verifikasi OTP |
| POST | `/auth/login` | Login |
| GET | `/auth/me` | Get current user |
| POST | `/auth/heartbeat` | Session heartbeat |

### Assets (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/assets` | List aset (paginated, searchable, filterable) |
| POST | `/assets` | Create aset baru |
| GET | `/assets/{id}` | Get detail aset |
| GET | `/assets/{id}/media` | Get media aset (foto, dokumen) |
| GET | `/assets/{id}/photos/{idx}` | Get foto full-res |
| PUT | `/assets/{id}` | Update aset (full) |
| PATCH | `/assets/{id}` | Update aset (partial/dirty) |
| DELETE | `/assets/{id}` | Hapus aset |
| GET | `/assets/filter-options` | Opsi filter dinamis |
| GET | `/assets/stats` | Statistik aset |
| GET | `/assets/analytics` | Data analitik |
| POST | `/assets/validate` | Validasi data aset |
| POST | `/assets/migrate-gridfs` | Migrasi foto ke GridFS |

### Batch & Locking (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/assets/lock` | Lock row |
| POST | `/assets/heartbeat` | Heartbeat lock |
| POST | `/assets/unlock` | Unlock row |
| GET | `/assets/locks` | Semua lock aktif |
| PUT | `/assets/batch-update` | Batch update |
| GET | `/assets/groups` | Asset groups |
| GET | `/assets/all-ids` | Semua asset IDs |

### Activities (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/inventory-activities` | List kegiatan |
| POST | `/inventory-activities` | Buat kegiatan |
| GET | `/inventory-activities/{id}` | Detail kegiatan |
| PUT | `/inventory-activities/{id}` | Update kegiatan |
| DELETE | `/inventory-activities/{id}` | Hapus kegiatan (cascade) |
| GET | `/satker-list` | Daftar satker |
| GET | `/satker-lookup` | Lookup satker |

### Export (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/export/csv` | Export CSV |
| GET | `/export/xlsx` | Export XLSX (4 sheets) |
| GET | `/export/pdf` | Export PDF |
| GET | `/assets/{id}/doc-file/{idx}/{type}/{fidx}` | Serve doc file |
| DELETE | `/assets/bulk-delete/{activity_id}` | Hapus massal |

### Import (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/import` | Import CSV/XLSX |
| GET | `/templates/csv` | Download template CSV |
| GET | `/templates/xlsx` | Download template XLSX |

### Categories (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/categories` | List kategori (paginated) |
| GET | `/categories/all` | Semua kategori |
| POST | `/categories` | Buat kategori |
| DELETE | `/categories/{id}` | Hapus kategori |
| DELETE | `/categories-all` | Hapus semua kategori |
| POST | `/categories/import-bulk` | Bulk import kategori |
| GET | `/categories/import-progress/{job_id}` | Progress import |
| POST | `/categories/import` | Import kategori |

### Reports (`/api/inventory-activities/{id}/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/rekapitulasi` | Data rekapitulasi |
| GET | `/dbhi/{type}` | DBHI PDF (6 tipe) |
| GET | `/rhi-pdf` | RHI PDF |
| GET | `/bahi-pdf` | BAHI PDF |
| GET | `/sp-hasil-pdf` | SP Hasil PDF |
| GET | `/sp-pelaksanaan-pdf` | SP Pelaksanaan PDF |
| GET | `/berita-acara-pdf` | Berita Acara PDF |
| GET | `/sptjm-pdf` | SPTJM PDF |
| GET | `/surat-koreksi-pdf` | Surat Koreksi PDF |
| GET | `/executive-summary-html` | Executive Summary HTML |
| GET | `/executive-summary-pdf` | Executive Summary PDF |
| GET | `/executive-data-pdf` | Executive Data PDF (paginated) |
| GET | `/executive-data-info` | Info pagination |
| GET | `/laporan-satker-html` | Laporan Satker HTML |
| GET | `/laporan-satker-pdf` | Laporan Satker PDF |
| GET | `/lhi-pdf` | LHI complete package |
| POST | `/batch-pdf-zip` | Batch download PDF (ZIP) |
| GET | `/report-settings` | Get report settings |
| PUT | `/report-settings` | Update settings |
| POST | `/report-settings/logo` | Upload logo |
| DELETE | `/report-settings/logo` | Hapus logo |

### Media & Compression (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| POST | `/compress-image` | Kompresi gambar |
| GET | `/compression-stats` | Stats kompresi Tinify |
| GET | `/compression-quotas` | Quota semua service gambar |
| POST | `/compress-pdf` | Kompresi PDF |
| GET | `/pdf-compression-quotas` | Quota service PDF |

### Documents (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/documents/ppt` | Generate presentasi PPT |
| GET | `/documents/proposal` | Generate proposal DOCX |

### Cards (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/assets/{id}/card` | KTP card PDF |
| POST | `/assets/cards/bulk` | Bulk KTP cards |

### Backup (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/stats` | Backup statistics |
| POST | `/start` | Start backup |
| POST | `/restore/start` | Start restore |
| GET | `/progress/{job_id}` | Progress job |
| GET | `/active` | Active backup job |
| GET | `/download/{job_id}` | Download backup |
| POST | `/dismiss/{job_id}` | Dismiss job |
| GET | `/create` | Create backup (legacy) |
| POST | `/restore` | Restore (legacy) |

### Users (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/users` | List users |
| PUT | `/users/{id}/toggle-active` | Toggle user aktif |
| PUT | `/users/{id}/change-password` | Change password |
| PUT | `/users/{id}/update-name` | Update name |
| DELETE | `/users/{id}` | Delete user |
| PUT | `/users/{id}/change-role` | Change role |

### System (`/api/`)
| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/` | Health check |
| GET | `/user/` | User health |
| GET | `/inventory-classifications` | Opsi klasifikasi inventarisasi |
| DELETE | `/system/reset-all` | Reset semua data (admin) |
| GET | `/audit-logs` | Audit logs |

---

## 6. Environment Variables

### Backend (`backend/.env`)
| Variable | Keterangan |
|----------|------------|
| `MONGO_URL` | MongoDB connection string |
| `DB_NAME` | Nama database |
| `CORS_ORIGINS` | Allowed origins |
| `TINIFY_API_KEY` | Tinify (TinyPNG) API key |
| `RESEND_API_KEY` | Resend email API key |
| `SENDER_EMAIL` | Email pengirim OTP |
| `JWT_SECRET` | Secret key untuk JWT token |
| `COMPRESTO_API_KEY` | Compresto compression API |
| `UPLOADCARE_PUBLIC_KEY` | Uploadcare public key |
| `ILOVEAPI_PUBLIC_KEY` | iLoveAPI public key |
| `ILOVEAPI_SECRET_KEY` | iLoveAPI secret key |
| `WHIPDOC_API_KEY` | WhipDoc PDF compression |

### Frontend (`frontend/.env`)
| Variable | Keterangan |
|----------|------------|
| `REACT_APP_BACKEND_URL` | URL backend API |

---

## 7. Default Credentials
- **Username**: `admin`
- **Password**: `admin123`
