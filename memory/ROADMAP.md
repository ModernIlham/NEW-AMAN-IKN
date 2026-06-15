# ROADMAP - AMAN (Aplikasi Manajemen Aset Negara)

## Status: Juli 2025 — v2.1 Production-Ready Multi-Worker

---

## ✅ COMPLETED — v2.1 Collaborative Stability & Scale-Out (Juli 2025)

### Fase 1: Anti-Corruption 🛡️
- [x] **Optimistic Concurrency Control (OCC)** — field `version` + header `If-Match` + atomic CAS
- [x] **409 Conflict handling** — response dengan `{current_version, your_version, current}`
- [x] **Atomic Row Lock** — `find_one_and_update` + `insert_one` fallback, race-free
- [x] **Idempotency-Key** — POST/PATCH cache 5min TTL, mencegah duplikat retry
- [x] **GridFS Auto-Rollback** — hapus blob saat DB write fail
- [x] **Lock filter per-activity** — kurangi payload 90%+

### Fase 2: Performance Save 🚀
- [x] **Client-side image compression** (Canvas 1920px + JPEG q=0.85) — payload 10x lebih kecil
- [x] **Smart Tinify skip** untuk foto <500KB
- [x] **GzipMiddleware** pada respons API
- [x] **Version field di list projection**

### Fase 3: Multi-Worker Scalability 🔀
- [x] **Cross-Worker WebSocket Fanout** via capped collection (`ws_events`) + tailable cursor
- [x] **Server-initiated WS heartbeat** (25s) — anti proxy timeout
- [x] **Cross-worker presence events** (`__presence_join__/__presence_leave__`)
- [x] **Multi-worker uvicorn config** (`--workers 4`) di DEPLOYMENT_GUIDE

### Fase 5: UX Polish ✨
- [x] **Conflict indicator per baris** (ikon orange + tooltip)
- [x] **WS disconnect badge** di header
- [x] **server_ping → pong** handler di frontend
- [x] **onConflict callback** + auto-refresh row pada 409

---

## ✅ COMPLETED (P0 - Critical)

- [x] Login + Register (OTP email) + JWT Auth + Rate Limiting
- [x] CRUD Kegiatan Inventarisasi (dengan cascade delete)
- [x] Satker Info + Eselon Hierarchy + 4 Jenis Tim
- [x] CRUD Aset (30+ field) + GridFS Photo Storage
- [x] Status Inventarisasi: Ditemukan, Tidak Ditemukan (klasifikasi+sub), Berlebih, Sengketa
- [x] Dirty-Tracking & Partial Update (PATCH)
- [x] Optimistic Save Queue + Deferred Refresh
- [x] Row Locking + Multi-lock + Heartbeat + WebSocket
- [x] Import CSV/XLSX (per activity, validasi, duplikasi)
- [x] Export CSV (41 kolom, streaming)
- [x] Export XLSX (4 sheets: Data+Dokumen+Kegiatan+Tim, foto HD)
- [x] Export PDF (landscape A4, foto, summary)
- [x] 13+ Laporan PDF Resmi (DBHI, RHI, BAHI, SP, BA, SPTJM, Koreksi, Executive, Satker, LHI)
- [x] Batch PDF ZIP download
- [x] Report Settings (logo, cover page)
- [x] Stiker Tracking (status, ukuran, foto)
- [x] Kelengkapan Dokumen Checklist (foto+PDF)
- [x] KTP Card PDF (individual + bulk)
- [x] Barang Serupa (Asset Groups) + Batch Edit
- [x] Analytics Panel + Rekapitulasi
- [x] Audit Logging
- [x] User Management (admin)
- [x] Backup & Restore (background job)
- [x] Kompresi Gambar (Tinify → Compresto → Uploadcare → Pillow)
- [x] Kompresi PDF (iLoveAPI → WhipDoc)
- [x] Dokumen Generator (PPT + DOCX)
- [x] WebSocket Real-Time (asset changes, presence, lock broadcast)
- [x] Backend Modular (19 route modules, 10.000+ baris)
- [x] System Reset (admin hidden feature)
- [x] Halaman Info (panduan, arsitektur, RAB)
- [x] Mobile Responsive + Gallery View + Pull to Refresh
- [x] Dark Mode
- [x] Scroll to Top + Posisi Memory
- [x] Service Worker (PWA/cache)
- [x] VPS Deployment Guide + Scripts (multi-worker)
- [x] Save & Navigate Form Persistence
- [x] WebSocket Deferred Refresh

---

## 🔄 P1 (Important) - Next Up

- [ ] **Typing indicator real-time**
  - Throttled WS event saat user mengetik di field aset (event `__typing__`)
  - Tampilkan "User X sedang mengetik" di baris yg bersangkutan

- [ ] **Presence avatars per-row**
  - Tampilkan avatar mini user yang sedang melihat baris aset (bukan hanya yang edit)
  - Event `__viewing__` di WS

- [ ] **Side-by-side conflict resolution UI**
  - Saat 409 Conflict, tampilkan diff antara versi user vs server
  - Tombol "Keep mine" / "Keep theirs" / "Merge"
  - Gantikan auto-refresh + toast yg sekarang

- [ ] **Stop storing base64 `photos[]` inline di MongoDB**
  - Hanya simpan GridFS IDs — hemat storage 50%+
  - Migrasi online untuk existing assets
  - Requires: lazy photo fetch di edit form

- [ ] **Background job untuk photo processing**
  - Gunakan FastAPI `BackgroundTasks` untuk GridFS store + thumbnail
  - Response API kembali lebih cepat
  - WS update saat foto siap

- [ ] **Performance: XLSX Export optimization**
  - Current: Slow for 1000+ assets with photos
  - Target: Use GridFS stream instead of base64 for photo embedding

- [ ] **Refactor ActivitySelectionPage.jsx** (~1.150 baris)
  - Pecah ke sub-komponen: ActivityCard, SatkerForm, TimSection, EselonEditor

- [ ] **Offline mode penuh**
  - IndexedDB sync untuk data aset
  - Queue operations saat offline
  - Auto-sync saat kembali online

---

## 📋 P2 (Moderate) - Backlog

- [ ] **Observability & Metrics**
  - Structured JSON logging dengan request_id, user_id, activity_id, latency_ms
  - Endpoint `/api/metrics` (admin-only) — WS connections, queue depth, slow queries
  - Frontend error boundary + logger ke backend audit

- [ ] **Refactor AssetForm.jsx** (~1.284 baris)
  - Split form sections ke komponen terpisah

- [ ] **Refactor routes/reports.py** (~2.410 baris)
  - Extract common PDF helpers
  - Separate report logic ke service modules

- [ ] **Refactor DashboardPage.jsx** (~848 baris)
  - Extract editing/locking/refresh logic ke custom hook

- [ ] **Multi-database support**
  - Support multiple DB untuk beda satker

- [ ] **Redis Integration (optional — capped collection sudah cukup)**
  - Untuk >10 workers atau cross-region deployment
  - Hot-path lock cache (lebih cepat dari Mongo)

---

## 💡 P3 (Enhancement) - Ideas

- [ ] Progress indicator Save & Navigate
- [ ] Badge notifikasi pending WS updates saat editing
- [ ] Bulk photo upload dengan drag & drop
- [ ] Dashboard statistik antar-kegiatan (cross-activity analytics)
- [ ] PDF template customization oleh user
- [ ] Export PDF dengan foto resolusi tinggi (opsional)
- [ ] Multi-language support (EN/ID)
- [ ] Notifikasi email scheduled (reminder inventarisasi)
- [ ] QR Code per aset
- [ ] Barcode scanning (mobile camera)
- [ ] Multipart/form-data upload endpoint (hentikan base64 di JSON body)
- [ ] HTTP/2 + streaming upload
