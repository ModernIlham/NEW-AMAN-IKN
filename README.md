# AMAN - Aplikasi Manajemen Aset Negara

> Sistem Inventarisasi Barang Milik Negara (BMN) berbasis web, standar pemerintah Indonesia (SE 17/SE/M/2024 & LKPP 85/2025)

**Versi:** 2.3 (Juli 2026) — Peta aset interaktif + ekspor GIS, kamera lapangan penuh, CI/CD auto-deploy

---

## Ringkasan

**AMAN** (sebelumnya InventoryMaster Pro) adalah aplikasi full-stack untuk pengelolaan dan inventarisasi Barang Milik Negara (BMN). Mendukung proses inventarisasi lapangan, pencatatan aset, pelacakan status, manajemen tim, dan pembuatan 13+ jenis laporan resmi dalam format PDF.

**Live:** [https://amanikn-inventarisasi.com](https://amanikn-inventarisasi.com)

**Riwayat perubahan:** lihat [`CHANGELOG.md`](./CHANGELOG.md) untuk catatan lengkap
tiap rilis/PR (termasuk catatan teknis penting soal aturan tap-target 44px di ≤1023px).

---

## 🧭 Arah Pengembangan — Siklus Penuh Pengelolaan BMN

AMAN berkembang bertahap dari aplikasi inventarisasi menjadi platform siklus
penuh pengelolaan BMN (PP 27/2014). **Beranda Modul** — halaman pertama
setelah login — memetakan seluruh tahap siklus: *Penatausahaan ›
Inventarisasi Aset* aktif penuh; **SEMUA 14 modul siklus lainnya sudah
Sebagian Aktif** (Persediaan, Pelaporan, Perencanaan, Penganggaran,
Pengadaan, Penggunaan, Pemanfaatan, Penilaian, Pengamanan, Pemeliharaan,
Pemindahtanganan, Pemusnahan, Penghapusan, Wasdal) — seluruh kartu siklus
bisa dimasuki; hanya sub-modul Pembukuan/KIB yang masih **Segera Hadir**
(menunggu verifikasi lampiran PMK 181).

- Rencana induk & prinsip integrasi antar modul: [`docs/MASTERPLAN-SIKLUS-BMN.md`](./docs/MASTERPLAN-SIKLUS-BMN.md)
- Rujukan regulasi & alur bisnis: [`docs/PUSTAKA-REGULASI-BMN.md`](./docs/PUSTAKA-REGULASI-BMN.md)
- Registry modul (konsep yang tampil di aplikasi): `frontend/src/lib/bmnModules.js`
- Proses baku pengembangan per fitur: `.claude/skills/aman-dev/SKILL.md`

**Progres Fase 2 (Juli 2026):** Referensi Kodefikasi 5 level (#73–74) ·
DBKP per golongan (#76) · **modul Inventarisasi Persediaan inti lengkap**
(#77–85): master ber-layer **FIFO** selaras SAKTI, transaksi masuk/keluar
berjurnal, peringatan + nota dinas, laporan posisi/mutasi, stock opname +
BAOF + pengingat semesteran (#128), impor/ekspor + template, **filter
Lokasi/Gudang + laporan posisi per gudang** (#152), **pindah gudang
ber-jurnal** (#154) · **Pelaporan inti lengkap**: hub arsip
lintas kegiatan (#86), **Posisi BMN di Neraca** (#93), ekspor
**rekonsiliasi XLSX** sandingan SAKTI (#94), **LBKP** semesteran/
tahunan per golongan dengan saldo awal–mutasi–akhir (#95), dan
**CaLBMN pra-isi bab I–V** per periode (struktur lampiran PMK 181,
bahan penyusunan — final via SAKTI) (#144), **LKB — Laporan Kondisi
Barang** per NUP + ringkasan B/RR/RB per golongan (#146), **periode
pelaporan ber-kunci** dengan penanda FINAL di LBKP/CaLBMN (#148), dan
**tenggat penyampaian konfigurabel per periode** dengan pengingat
lewat tenggat (#150) — semua dapat diakses dari Beranda Modul.

**Progres Fase 3 (Juli 2026):** Penggunaan — rekap aset per pemegang +
kelengkapan BAST (#87) + **Daftar Barang yang Digunakan per pemegang**
(PDF lampiran BAST, PMK 40/2024) (#125) + **daftar pantau BMN idle**
dengan tiket klarifikasi → usul serah → diserahkan (PMK 120/2024)
(#126) + **register SK penetapan penggunaan** 5 jenis dengan cakupan
aset ter-PSP (#129) + **arsip scan SK penetapan per register** (#137)
+ **tiket proses 4 rezim PMK 40/2024** (alih status, penggunaan
sementara, dioperasikan pihak lain, penggunaan bersama) dengan
pengingat tenggat/perpanjangan (#181, #183) + **BAST penetapan status
penggunaan PDF siap tanda tangan per SK** (#192)
· Pengamanan — dasbor tertib administrasi + daftar
pantau sengketa (#88) + **register BMN bermasalah berstatus**
identifikasi → mediasi → blokir → litigasi → selesai (PP 27/2014
Ps. 42, pustaka §11) (#169) + **arsip dokumen kepemilikan per aset**
(sertipikat/BPKB/STNK/IMB-PBG + lokasi penyimpanan Ps. 43 + scan +
penanda kedaluwarsa) (#171) + **status sertipikasi tanah** belum/
proses/K1–K4/SHP terbit per dokumen sertipikat (#173) + **checklist
pengamanan per aset** butir fisik/administrasi/hukum per jenis objek
dengan skor (#175) + **register polis Asuransi BMN** dengan pengingat
masa berlaku (PMK 43/2025, mencabut PMK 97/2019) (#177) · Pemeliharaan — riwayat & biaya per aset dengan
telaah kapitalisasi PMK 181 (#89) + **DHPB PDF** semesteran/tahunan
(Ps. 47 PP 27/2014) (#90) + jadwal berkala dengan status jatuh tempo (#92)
+ **ekspor CSV riwayat** (#167).

**Progres Fase 4 (Juli 2026):** Perencanaan — **kandidat RKBMN
pemeliharaan** (saringan kelayakan PMK 153/2021 dari kondisi aset +
riwayat biaya Pemeliharaan) (#99) + **kertas kerja XLSX** siap diisi
satker untuk dibawa ke SIMAN (#100) + **usulan RKBMN per unit
berstatus** draft → diajukan → disetujui PB → dikirim Pengelola →
hasil penelaahan, dengan penanda SPTJM/reviu APIP (PMK 153/2021 +
KMK 128/KM.6/2022) (#179) · Penganggaran — **register
usulan berstatus** diusulkan → disetujui telaah → masuk DIPA →
terealisasi, nilai per tahap + serapan (PMK 62/2023 + 153/2021)
(#115) + **sanding rencana vs realisasi per akun BAS** (#123) +
**ekspor CSV register** (#163) + **kalender tenggat konfigurabel dengan
pengingat** (#165) + **sanding realisasi per triwulan per tahun
anggaran** (kumulatif + serapan kumulatif vs DIPA) (#186 — daftar
"menyusul" Penganggaran tuntas) ·
Pengadaan — **register perolehan per BAST/kontrak** dengan
checklist dokumen sumber, tautan barang ke aset master, dan penanda
ekstrakomptabel PMK 181 (Perpres 16/2018 jo. 46/2025) (#117) +
**arsip scan berkas per perolehan** (BAST/kontrak/faktur) (#135) +
**ekspor CSV register** (#161).
Pelaporan Fase 2 juga tuntas inti:
Posisi BMN di Neraca (#93), rekonsiliasi XLSX (#94), LBKP mutasi (#95),
Kartu Barang (#97), transaksi massal persediaan (#98).

**Progres Fase 5–6 (Juli 2026):** Penilaian — **penyusutan garis lurus
semesteran** (PMK 65/2017; masa manfaat KMK 295/2019 jo. 266/2023) dengan
halaman posisi per golongan + daftar telaah (#102–#103) + referensi masa
manfaat dapat dikelola (#107) + **register koreksi nilai** (revaluasi
LHIP/koreksi inventarisasi/temuan/pencatatan, dampak masa manfaat, status
pencatatan SAKTI; Perpres 75/2017, PMK 118/2017 jo. perubahannya, PMK 99/2024)
(#184) · Pemanfaatan — **register perjanjian 6
bentuk** dengan penjaga dokumen persetujuan/NTPN + jatuh tempo ≤60 hari
(PMK 115/2020) (#108) + **kontribusi tahunan ber-NTPN dengan pengingat
tunggakan** (#121) + **arsip scan dokumen per perjanjian** (#131) +
**ekspor CSV register** (#158) + **lampiran wasdal terpisah per
perjanjian** (laporan monitoring/BA peninjauan lapangan) (#188) +
**atribut fasilitas transaksi** pada perjanjian KSP/BGS-BSG (PMK 18/2024;
khusus IKN PMK 139/PMK.08/2022 — pendampingan, bukan bentuk pemanfaatan)
(#190 — daftar "menyusul" Pemanfaatan tuntas)
· Penghapusan — **kandidat usul hapus** per jalur
PMK 83/2016 (#104) + **tiket usulan berstatus** usul → proses → SK (#106)
+ **arsip scan SK/berkas per usulan** (#134) + **ekspor CSV** (#159)
· Pemusnahan — **register BA multi-aset** (#110) + **PDF Berita Acara
siap tanda tangan** (#119) + **usulan penghapusan otomatis per aset BA**
(#120) + **lampiran bukti pelaksanaan** (#132) + **ekspor CSV** (#161)
· Pemindahtanganan — **register usulan 4 bentuk** dengan dokumen
wajib per tahap + tenggat lelang 6 bulan (PMK 111/2016 jo. 165/2021)
(#111) + **arsip scan dokumen per usulan** (#138) + **ekspor CSV**
(#159) · Wasdal — **dasbor pemantauan 5 objek** PMK 207/2021, temuan
otomatis dari register yang ada (#113) + **Laporan Hasil Pemantauan PDF
pra-isi** untuk SIMAN v2 (#122) + **register penertiban ber-tenggat
15 hari kerja** dengan peringatan lewat tenggat (#140) + **pemantauan
insidentil 10+5 hari kerja dengan PDF Berita Acara** (#142) + **arsip
lampiran per tiket insidentil** (#156).
**Seluruh kartu modul siklus kini bisa dimasuki dari Beranda Modul.**

---

## 🆕 Highlight Rilis v2.3 (Juli 2026)

- 🗺️ **Peta Aset interaktif** — lembar peta di halaman utama (leaflet + OpenStreetMap): pin berwarna status, badge foto, border hijau kelengkapan pengguna+BAST; **geser pin = koordinat tersimpan otomatis**; mengikuti pencarian/filter aktif + filter Barang Serupa; jalan penuh saat offline (snapshot).
- 🌐 **Ekspor GIS** — unduh titik peta sebagai **KML / KMZ / SHP** (shapefile WGS84) lengkap 27 atribut, mengikuti filter aktif.
- 📷 **Kamera lapangan penuh** — flash, gestur kecerahan (dibakar ke foto), watermark jam+GPS, **Simpan & Baru instan** (tanpa menunggu jaringan), dan **Simpan & Scan** untuk alur scan-QR → edit → scan berikutnya.
- 📄 **Kop surat resmi 3 baris** (instansi / unit / sub-unit) + alamat multi-baris; seluruh tanda tangan memakai **Kuasa Pengguna Barang**; belasan perbaikan isi laporan (binding data, penomoran, tanggal Indonesia).
- 🚀 **CI/CD** — test + build otomatis di tiap PR (GitHub Actions), **auto-deploy ke VPS Hostinger** pada setiap merge ke `main`.
- 🧱 **Registry field aset** — menambah field baru kini ±3 titik sentuh (dulu 13+), dijaga test anti-drift; filter rentang tanggal input.

Detail lengkap per PR di [`CHANGELOG.md`](./CHANGELOG.md) (#38–#65).

---

## Highlight Rilis v2.2 (Juli 2026)

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
| **Frontend** | React 19 + TailwindCSS + Shadcn/UI + Recharts + Leaflet (peta) + Lucide Icons |
| **Backend** | FastAPI (Python 3.11) — 19 route modules + event_bus, ~10.500 baris |
| **Database** | MongoDB 7.0 (standalone) + Motor (async) + GridFS (foto) + Capped Collection (WS events) |
| **PDF Engine** | WeasyPrint + Jinja2 (template) + ReportLab (tabel) |
| **Real-time** | WebSocket + Cross-Worker Event Bus (tailable cursor) + Server Heartbeat |
| **Consistency** | Optimistic Concurrency Control + Idempotency-Key + Atomic Lock |
| **Deployment** | Hostinger VPS (Nginx + Supervisor + Let's Encrypt SSL) + Multi-worker uvicorn + CI/CD GitHub Actions (auto-deploy saat merge) |

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
| Ekspor GIS | Titik peta aset: KML / KMZ / SHP (WGS84) + 27 atribut |

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

**Update kode di VPS (otomatis):** setiap merge ke `main` memicu workflow
[Deploy ke Hostinger VPS](.github/workflows/deploy.yml) yang menjalankan
`scripts/deploy_vps.sh` lewat SSH. Sekali saja, isi secret repo
(Settings → Secrets and variables → Actions): `VPS_HOST`, `VPS_USER`,
`VPS_SSH_KEY` (opsional `VPS_PORT`). Bisa juga dipicu manual dari tab
Actions → Run workflow.

**Update kode di VPS (manual):**
```bash
cd /var/www/inventarisasi && bash scripts/deploy_vps.sh
# — atau langkah demi langkah (JANGAN git pull, selalu fetch + reset) —
cp /var/www/inventarisasi/backend/.env /tmp/backend_env_backup
cp /var/www/inventarisasi/frontend/.env /tmp/frontend_env_backup
cd /var/www/inventarisasi
git fetch origin && git reset --hard origin/main
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
