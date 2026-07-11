# AMAN - Aplikasi Manajemen Aset Negara

> Sistem Inventarisasi Barang Milik Negara (BMN) berbasis web, standar pemerintah Indonesia (SE 17/SE/M/2024 & LKPP 85/2025)

**Versi:** 2.2 (Juli 2026) — Pengesahan & kunci kegiatan, kartu inventarisasi, QR, mode offline penuh

---

## Ringkasan

**AMAN** (sebelumnya InventoryMaster Pro) adalah aplikasi full-stack untuk pengelolaan dan inventarisasi Barang Milik Negara (BMN). Mendukung proses inventarisasi lapangan, pencatatan aset, pelacakan status, manajemen tim, dan pembuatan 13+ jenis laporan resmi dalam format PDF.

**Live:** [https://amanikn-inventarisasi.com](https://amanikn-inventarisasi.com)

**Riwayat perubahan:** lihat [`CHANGELOG.md`](./CHANGELOG.md) untuk catatan lengkap
tiap rilis/PR (termasuk catatan teknis penting soal aturan tap-target 44px di ≤1023px).

---

## 🆕 Highlight Rilis v2.2 (Juli 2026)

- 🎫 **Nomor tiket kegiatan** `INV-{tahun}-{seq}` otomatis + **alur pengesahan**: unggah PDF bertanda tangan → sahkan → kegiatan **terkunci permanen** (semua mutasi ditolak 423). Lihat [`docs/PENGESAHAN.md`](./docs/PENGESAHAN.md).
- 🗂️ **Kartu Inventarisasi** — riwayat pengesahan aset lintas kegiatan (per kode register / kode aset+NUP, terlingkup satker).
- 📷 **QR kode register** pada kartu cetak (`#{kode_register}`) + scanner kamera di dashboard.
- 📴 **Mode offline penuh** — snapshot list per kegiatan (IndexedDB, delta sync), antrian simpan persisten, edit dari cache; foto streaming URL cacheable (ETag/304).
- 👤 **Pengguna "melekat ke"** (Individual/Jabatan/Operasional) + **dokumen BAST** per aset (unggah & preview).
- 💾 **Backup mencakup semua koleksi** (termasuk riwayat pengesahan & counter tiket) + GridFS; restore membangun ulang index & counter tiket.

Detail lengkap per PR di [`CHANGELOG.md`](./CHANGELOG.md) (#25–#28).

---

## Highlight Rilis v2.1 (Juli 2025)

Perbaikan menyeluruh untuk kolaborasi multi-user & performa penyimpanan:

### Stabilitas Kolaborasi (Fase 1)
- ⚛️ **Atomic Row Locking** — 5+ user klik edit bersamaan, hanya 1 yang dapat lock (race-free, terbukti lewat test).
- 🔒 **Optimistic Concurrency Control (OCC)** — field `version` per aset + header `If-Match`. Mencegah _lost update_ saat 2 user simpan bersamaan. 409 Conflict → UI orange warning + auto-refresh.
- 🔁 **Idempotency-Key** pada POST/PATCH — retry jaringan tidak duplikat aset/foto.
- 🛡️ **GridFS Auto-Rollback** — foto yang sudah upload otomatis dihapus jika save akhirnya gagal.

### Performa Save (Fase 2)
- 📦 **Kompresi Gambar Client-Side** (Canvas API): resize 1920px + JPEG q=0.85. Payload 5MB → 500-800KB (**~10x lebih kecil**).
- ⚡ **GzipMiddleware** pada respons API.
- 🎯 **Version field** di list projection agar OCC bekerja end-to-end.
- 🧠 **Smart Tinify skip** — foto sudah <500KB tidak perlu dikompres lagi di server (hemat quota & waktu).

### Skalabilitas Multi-Worker (Fase 3)
- 🔀 **Cross-Worker WebSocket Fanout** via MongoDB _capped collection_ (`ws_events`, 10MB/20k docs) + _tailable cursor_.
- 💪 Mendukung `uvicorn --workers 4+` tanpa perlu Redis atau replica set.
- 💓 **Server-Initiated WS Heartbeat** (25s) — tahan terhadap proxy timeout (Cloudflare, nginx).
- 🎯 **Lock polling per-activity** (bukan global) — payload turun 90%+.

### UX Polish (Fase 5)
- 🟧 **Indikator konflik** per baris (ikon orange) saat terjadi 409.
- 📡 **Badge "WS"** di header saat WebSocket putus.
- ✅ Status save per baris: queued / saving / saved / failed / **conflict** (baru).

---

## Tech Stack

| Layer | Teknologi |
|-------|----------|
| **Frontend** | React 19 + TailwindCSS + Shadcn/UI + Recharts + Lucide Icons |
| **Backend** | FastAPI (Python 3.11) — 19 route modules + event_bus, ~10.500 baris |
| **Database** | MongoDB 7.0 (standalone) + Motor (async) + GridFS (foto) + Capped Collection (WS events) |
| **PDF Engine** | WeasyPrint + Jinja2 (template) + ReportLab (tabel) |
| **Real-time** | WebSocket + Cross-Worker Event Bus (tailable cursor) + Server Heartbeat |
| **Consistency** | Optimistic Concurrency Control + Idempotency-Key + Atomic Lock |
| **Deployment** | Hostinger VPS (Nginx + Supervisor + Let's Encrypt SSL) + Multi-worker uvicorn |

---

## Fitur Utama

### Autentikasi & Otorisasi
- Login username/password + JWT token
- Registrasi dengan OTP email verification (via Resend API)
- Role-based: `admin` (full access) & `user` (limited)
- Heartbeat session & rate limiting

### Kegiatan Inventarisasi
- CRUD kegiatan inventarisasi dengan informasi lengkap
- Informasi Satker: kode, nama, alamat, Kasatker (nama/NIP/jabatan)
- Hirarki Eselon I → Eselon II (multiple)
- 4 jenis tim: Tim Inti, Tim Pembantu, Tim Peneliti, Tim Pendukung
- Penanggung jawab, berita acara, kesimpulan
- Upload foto & dokumen kegiatan

### Manajemen Aset
- 30+ field per aset: identitas, detail perolehan, organisasi, kondisi, stiker, inventarisasi, GPS, dokumen, foto
- 5 status inventarisasi: Belum Diinventarisasi, Ditemukan, Tidak Ditemukan (dengan klasifikasi detail), Berlebih, Sengketa
- Multiple foto per aset disimpan di MongoDB GridFS
- Kelengkapan dokumen checklist dengan foto bukti & file PDF
- Stiker tracking (status, ukuran, foto)
- Dirty-tracking & partial update (PATCH) — hanya kirim field yang berubah

### Real-time Collaboration (v2.1 — Production-ready Multi-User)
- **WebSocket + Cross-Worker Event Bus**: fanout ke semua worker via MongoDB capped collection (`ws_events`) + tailable cursor — mendukung `--workers 4+` tanpa Redis
- **Atomic Row Locking** (race-free): `find_one_and_update` + `insert_one` fallback dengan `DuplicateKeyError` — hanya 1 user bisa pegang lock pada satu waktu
- **Optimistic Concurrency Control (OCC)**: field `version` di setiap aset + header `If-Match` + atomic CAS. 409 Conflict saat bentrok, UI otomatis refresh + tampilkan warning orange
- **Idempotency-Key**: header pada POST/PATCH mencegah duplikasi saat retry setelah timeout jaringan (TTL 5 menit di Mongo)
- **Server Heartbeat**: server kirim `server_ping` tiap 25 detik untuk mencegah proxy idle timeout
- **Optimistic save queue**: background save, concurrent processing (max 3), deferred refresh
- **GridFS Auto-Rollback**: foto yang sudah upload dihapus otomatis jika DB write gagal — no orphan blobs

### Performa Upload & Save (v2.1)
- **Client-side image compression**: Canvas API resize ke 1920px + JPEG q=0.85 — payload 5MB → ~500KB (**~10x lebih kecil**)
- **Smart Tinify skip**: foto <500KB tidak dikompres lagi di server (hemat quota & latency)
- **GzipMiddleware** pada respons JSON
- **Version dalam list projection** untuk mendukung OCC end-to-end

### Import & Export
- **Import**: CSV/XLSX dengan validasi (kode aset, duplikasi, kategori)
- **Export CSV**: 46 kolom, streaming, UTF-8
- **Export XLSX**: 4 sheets (Data Aset + Kelengkapan Dokumen + Data Kegiatan + Tim Inventarisasi) dengan foto HD embedded
- **Export PDF**: Landscape A4 dengan foto thumbnail, summary box, color-coded

### 13+ Laporan PDF Resmi
| Laporan | Keterangan |
|---------|------------|
| DBHI (6 tipe) | Daftar Barang Hasil Inventarisasi |
| RHI | Ringkasan Hasil Inventarisasi |
| BAHI | Berita Acara Hasil Inventarisasi |
| SP Hasil | Surat Pernyataan Hasil |
| SP Pelaksanaan | Surat Pernyataan Pelaksanaan |
| Berita Acara | Berita Acara |
| SPTJM | Surat Pertanggungjawaban Mutlak |
| Surat Koreksi | Surat Koreksi Inventarisasi |
| Executive Summary | Ringkasan eksekutif dengan chart |
| Executive Data | Data detail paginasi |
| Laporan Satker | Laporan per satuan kerja |
| LHI Package | Gabungan semua laporan (merged PDF) |
| Batch ZIP | Download beberapa laporan sekaligus |

### Fitur Tambahan
- **Barang Serupa**: Pengelompokan aset per kode, NUP ranges, batch edit
- **KTP Card**: PDF kartu identitas aset (individual & bulk)
- **Kompresi Gambar**: Chain Tinify → Compresto → Uploadcare → Pillow
- **Kompresi PDF**: Chain iLoveAPI → WhipDoc
- **Dokumen Generator**: Presentasi PPT & Proposal DOCX otomatis
- **Backup & Restore**: Background job, ZIP format, auto-cleanup
- **Analytics**: Chart distribusi kondisi, status, kategori
- **Rekapitulasi**: Statistik lengkap per kegiatan
- **Audit Log**: Tracking semua perubahan (create/update/delete)
- **Report Settings**: Logo custom, cover page, info instansi
- **System Reset**: Hidden admin feature, hapus semua data (HAPUS SEMUA)
- **Halaman Info**: Panduan penggunaan, arsitektur, RAB, fitur lengkap

---

## Struktur Proyek

```
/app/
├── backend/                    # FastAPI Backend (10.000+ baris)
│   ├── server.py              # Entry point, router mounting, indexes
│   ├── db.py                  # MongoDB + GridFS connection
│   ├── models.py              # 16 Pydantic models
│   ├── auth_utils.py          # JWT token management
│   ├── shared_utils.py        # Cache, audit, thumbnail, OTP, constants
│   ├── routes/                # 19 route modules
│   │   ├── activities.py      # CRUD kegiatan + satker lookup
│   │   ├── assets.py          # CRUD aset + pagination + analytics
│   │   ├── audit.py           # Audit logs
│   │   ├── auth.py            # Register, login, OTP, heartbeat
│   │   ├── backup.py          # Background backup & restore
│   │   ├── batch.py           # Row locking, batch update, groups
│   │   ├── cards.py           # KTP card PDF generation
│   │   ├── categories.py      # CRUD kategori + bulk import
│   │   ├── documents.py       # PPT & Proposal DOCX generator
│   │   ├── exports.py         # CSV/PDF/XLSX export + bulk delete
│   │   ├── imports.py         # CSV/XLSX import + validation
│   │   ├── media.py           # Image compression (4 service chain)
│   │   ├── pdf_compress.py    # PDF compression (2 service chain)
│   │   ├── reports.py         # 13+ laporan PDF resmi (2.400 baris)
│   │   ├── templates.py       # CSV/XLSX template download
│   │   ├── users.py           # User management (admin)
│   │   ├── validation.py      # Asset data validation
│   │   └── websocket.py       # WebSocket real-time
│   ├── templates/             # Jinja2 HTML templates untuk PDF
│   │   ├── executive_summary.html
│   │   ├── executive_summary_data.html
│   │   ├── laporan_satker.html
│   │   └── laporan_satker_v2.html
│   └── uploads/               # File uploads (logos)
│
├── frontend/                   # React 19 Frontend
│   └── src/
│       ├── pages/             # 4 halaman utama
│       │   ├── LoginPage.jsx
│       │   ├── ActivitySelectionPage.jsx
│       │   ├── DashboardPage.jsx
│       │   └── InfoPage.jsx
│       ├── components/
│       │   ├── assets/        # 28+ komponen aset
│       │   │   ├── rekapitulasi/  # 5 sub-komponen rekapitulasi
│       │   │   └── ...
│       │   ├── ui/            # 47 komponen Shadcn/UI
│       │   └── BackgroundTaskBar.jsx
│       └── hooks/             # 9 custom hooks
│
├── scripts/                    # Deployment & maintenance scripts
│   ├── vps-fix.sh             # Diagnostik & perbaikan VPS
│   ├── vps-deploy.sh          # Deploy awal ke VPS
│   ├── vps-setup.sh           # Setup VPS
│   └── update-all.sh          # Update aplikasi
│
├── DEPLOYMENT_GUIDE_HOSTINGER.md  # Panduan deployment lengkap
└── memory/                     # Dokumentasi teknis
    ├── PRD.md                 # Product Requirements Document
    ├── CHANGELOG.md           # Riwayat perubahan
    ├── ROADMAP.md             # Rencana pengembangan
    └── REFACTORING_PLAN.md    # Rencana refactoring
```

---

## Quick Start (Development)

### Backend
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
yarn start
```

### Environment Variables

**Backend** (`backend/.env`):
```env
MONGO_URL="mongodb://localhost:27017"
DB_NAME="inventarisasi_bmn"
TINIFY_API_KEY=xxx
RESEND_API_KEY=xxx
SENDER_EMAIL=noreply@domain.com
JWT_SECRET=your_secret_key
COMPRESTO_API_KEY=xxx
UPLOADCARE_PUBLIC_KEY=xxx
ILOVEAPI_PUBLIC_KEY=xxx
ILOVEAPI_SECRET_KEY=xxx
WHIPDOC_API_KEY=xxx
```

**Frontend** (`frontend/.env`):
```env
REACT_APP_BACKEND_URL=https://your-domain.com
```

### Menjalankan Test

```bash
# Test unit bebas-infra (tanpa MongoDB/server) — juga jalan otomatis di CI:
pytest

# Test integrasi (butuh backend hidup di :8001 + MongoDB):
TEST_BASE_URL=http://localhost:8001 pytest -m integration

# Lint frontend (aturan react-hooks; error menggagalkan CI):
cd frontend && yarn lint
```

Gerbang CI (`.github/workflows/ci.yml`) menjalankan `compileall` + test unit
backend serta `eslint` + `yarn build` frontend pada setiap PR.

---

## Deployment

Lihat [DEPLOYMENT_GUIDE_HOSTINGER.md](./DEPLOYMENT_GUIDE_HOSTINGER.md) untuk panduan deployment lengkap ke Hostinger VPS.

**Update kode di VPS:**
```bash
# JANGAN gunakan git pull - selalu fetch + reset
cp /var/www/inventarisasi/backend/.env /tmp/backend_env_backup
cp /var/www/inventarisasi/frontend/.env /tmp/frontend_env_backup
cd /var/www/inventarisasi
git fetch origin && git reset --hard origin/Deploy_Hostinger_VPS
cp /tmp/backend_env_backup /var/www/inventarisasi/backend/.env
cp /tmp/frontend_env_backup /var/www/inventarisasi/frontend/.env
sudo supervisorctl restart inventarisasi-backend
cd frontend && yarn install && yarn build
```

---

## Default Credentials
- **Username**: `admin`
- **Password**: `admin123`

---

*Dikembangkan dengan Emergent.sh — Juli 2025*
*Domain: amanikn-inventarisasi.com*
