---
name: aman-dev
description: Panduan pengembangan bertahap aplikasi AMAN (inventarisasi BMN) — peta arsitektur, konvensi wajib, pipeline ship per fitur (verifikasi → PR → CI → merge → auto-deploy), jebakan umum, dan checklist pemilik proyek. Gunakan saat mengembangkan fitur apa pun di repo ini.
---

# Pengembangan AMAN — Proses Baku per Fitur

Aplikasi: **AMAN** — inventarisasi BMN offline-first (FastAPI + Motor/MongoDB
+ React CRA/craco + Tailwind/shadcn). Arah produk: platform siklus penuh
pengelolaan BMN — baca `docs/MASTERPLAN-SIKLUS-BMN.md` sebelum menambah modul.

## Peta repo (titik sentuh tersering)

| Area | Lokasi | Catatan |
|---|---|---|
| Registry field aset | `backend/asset_fields.py` | SATU sumber kebenaran ±45 field skalar → proyeksi list, PATCH, batch, CSV, impor, audit. Tambah field = ikuti panduan di header file; test anti-drift menagih semua turunan |
| Helper isolasi satker | `backend/shared_utils.py` | `scope_query_field_satker` / `scope_query_aset` / `pastikan_akses_dok_satker` / `pastikan_akses_aset` / `kode_satker_user` — lihat bagian "Isolasi multi-satker" di bawah |
| Jurnal Buku Barang | `backend/shared_utils.py:catat_mutasi_bmn` + `mutasi_bmn_utils.py` | Append-only, ber-guard anti-ganda via `ref_id` — lihat bagian "Jurnal" di bawah |
| Kebijakan backup/reset | `backend/backup_utils.py` | Registry `SKIP_COLLECTIONS` / `RESET_KEEP_COLLECTIONS` — koleksi BARU wajib ditimbang masuk mana |
| Kodefikasi barang | `backend/kodefikasi_utils.py` + `routes/kodefikasi.py` | Struktur 5 level dari panjang prefix (1/3/5/7/10 digit); digit 1 = domain ('1' persediaan, '2'-'8' aset); seed 8 golongan idempoten; lookup hierarki `/api/kodefikasi/lookup/{kode}` |
| Route API | `backend/routes/*.py` | assets, exports (geo/xlsx/pdf), reports (ReportLab), activities, auth, backup |
| Laporan PDF | `backend/routes/reports.py` | Helper wajib dipakai: `_kop_surat_flowables`, `_activity_identity`, `_identity_table`, `_fmt_tanggal_id`, `_signature_block` ("Kuasa Pengguna Barang") |
| Test unit | `backend/tests/unit/` | Jalan tanpa Mongo; registry test menjaga drift |
| Halaman utama | `frontend/src/pages/DashboardPage.jsx` | Mode Dashboard/Inventarisasi, antrean simpan optimistis, peta, filter |
| Form aset | `frontend/src/components/assets/AssetForm.jsx` | Intent `camera:*`, validasi, photo_ops |
| Kamera lapangan | `frontend/src/components/assets/FullCameraSheet.jsx` | Watermark, flash/brightness, scan QR, panel Edit Info |
| Lembar edit cepat | `frontend/src/components/assets/InventoryFieldSheet.jsx` | Ekspor konstanta opsi — jangan duplikasi daftar opsi di tempat lain |
| Peta aset | `frontend/src/components/assets/AssetMapFullView.jsx` | Lembar dalam halaman; ikut filter aktif; ekspor geo |
| Offline | `frontend/src/lib/offlineSnapshot.js`, `hooks/useOptimisticQueue*` | Snapshot IndexedDB + antrean simpan persisten |
| Registry modul siklus | `frontend/src/lib/bmnModules.js` | Beranda Modul + status aktif/segera; modul baru daftar di sini |
| CI/CD | `.github/workflows/ci.yml`, `deploy.yml`, `scripts/deploy_vps.sh` | CI tiap PR; auto-deploy ke VPS saat merge ke main |

## Konvensi WAJIB

1. **Seluruh teks UI, commit, dan PR berbahasa Indonesia.**
2. **Field aset baru lewat registry** (`asset_fields.py`) + models.py +
   exports/templates + frontend (emptyForm/buildEditFormData/TEXT_FIELDS/
   SNAPSHOT_FIELDS) — test registry akan menagih yang terlewat.
3. **Semua tulis ber-OCC** (version/If-Match) + Idempotency-Key; jangan buat
   jalur tulis baru yang melewatinya.
4. **Fitur lapangan wajib jalan offline** (snapshot + antrean); fitur kantor
   boleh online-only.
5. **Laporan**: pakai helper desain reports.py; tanggal gaya Indonesia; tanpa
   data dummy; smoke-test dengan harness FakeDB sebelum ship.
6. **Jangan perkecil tombol** di ≤1023px — aturan tap-target 44px global di
   `index.css`. Elemen kecil yang membengkak → beri `min-w-0 min-h-0`.
   (Riwayat lengkap: header CHANGELOG.md.)
6b. **ATURAN HOVER (sering menggigit — ikon peta #66, tombol Kartu #75):**
   token `--accent` proyek ini = **BIRU pekat** + `--accent-foreground` =
   **PUTIH** (bukan abu lembut ala shadcn standar). Konsekuensi:
   - Hover halus pada tombol/kartu/baris buatan sendiri: pakai
     `hover:bg-muted` (atau `hover:bg-accent/10`) — JANGAN `hover:bg-accent`
     polos kecuali sengaja mau biru solid (maka teks harus putih).
   - `Button variant="ghost"/"outline"` base-nya menyetel
     `hover:text-accent-foreground` (putih). Bila memberi warna teks kustom
     (mis. `text-emerald-700`) WAJIB sertakan pasangan `hover:text-*` untuk
     kedua tema — kalau tidak, teks jadi putih di atas latar terang.
   - Uji SETIAP elemen interaktif baru di light DAN dark mode sebelum ship.
7. **Overlay di atas kamera** (z-[120]): pakai elemen native (select, bukan
   Radix portal) di dalam FullCameraSheet.
8. **Data uji**: `data-testid` untuk elemen interaktif baru.
9. **Modul baru** ikut prinsip integrasi Bab 5 masterplan: satu identitas
   aset, satu kodefikasi, transaksi = jurnal, dokumen sumber = simpul,
   approval = gerbang, offline-first, registry anti-drift.
10. **Regulasi dulu, kode kemudian**: sebelum membangun fitur ber-alur
   bisnis pemerintahan, baca `docs/PUSTAKA-REGULASI-BMN.md`. Bila alurnya
   belum tercakup di sana → riset internet (peraturan + praktik SAKTI),
   TAMBAHKAN ke pustaka (beserta sumber & tanda "perlu verifikasi"), baru
   implementasi. Jangan menebak aturan; jangan data dummy di laporan.

## Isolasi multi-satker — CHECKLIST WAJIB tiap endpoint baru

Audit REVIEW-9 (Juli 2026) menemukan puluhan kebocoran di endpoint yang
"kelihatannya kecil" — pola bocornya SELALU sama. Untuk SETIAP endpoint
baru yang menyentuh koleksi ber-`kode_satker`, periksa kelima titik ini
(inilah kelas endpoint yang dulu bocor — hapus, transisi status, foto,
ekspor, lookup silang):

1. **INSERT** → stempel `"kode_satker": kode_satker_user(user)` di record.
2. **LIST / rekap / agregasi / count lintas modul** → bungkus query dengan
   `scope_query_field_satker(user, q)` (aset: `scope_query_aset`).
3. **GET-BY-ID / stream file (foto, PDF, GridFS)** → setelah fetch, panggil
   `await pastikan_akses_dok_satker(user, doc)` (aset:
   `pastikan_akses_aset`). Endpoint `require_user_or_query_token` (media)
   juga wajib — token media membawa user penuh.
4. **UPDATE / DELETE / TRANSISI STATUS** → filter delete/update dengan
   `scope_query_field_satker(_admin, {"id": ...})` ATAU guard
   `pastikan_akses_dok_satker` sebelum mutasi. Transisi status = jalur tulis
   juga (dulu 10 endpoint transisi lolos tanpa guard).
5. **LOOKUP SILANG antar modul** (mis. Pengadaan mencari master Persediaan
   by kode) → lookup juga ber-scope; tanpa itu dokumen satker lain terpilih
   dan alurnya macet/menulis silang.

Aturan pendamping:
- **Keunikan per satker ≠ indeks unik global.** Bila dup-check aplikasi
  di-scope per satker, indeks unik Mongo WAJIB menyertakan `kode_satker`
  (pola migrasi: `drop_index("<nama-otomatis-lama>")` dalam try/except lalu
  `create_index` baru — lihat `indexes.py` persediaan/idempotency).
- **Deret nomor otomatis (NUP, agenda, urutan) per satker** — increment yang
  membaca "max global" membocorkan deret satker lain.
- **Kunci cache menyertakan satker** (pola namespace `wasdal`:
  `f"{kode_satker_user(user) or '*'}:{param}"`).
- Semantik `scope_query_field_satker`: dokumen era-lama TANPA `kode_satker`
  terbuka untuk semua (disengaja, kompatibel mundur); super-admin (kode "")
  lintas satker. `pastikan_akses_dok_satker` hanya 403 bila kode dokumen
  TERISI dan berbeda.
- **Pengaturan**: kop surat ber-resolusi kegiatan→satker→global; pengaturan
  `report_settings type:"global"` lain (ambang, wajib_pegawai) memang
  universal — jangan menambah pengaturan per-alur baru ke "global" tanpa
  memikirkan satker.

### Lima titik buta yang lolos DUA gelombang audit (REVIEW-9 R8 → R9)

Setelah R8 menutup 20 kebocoran, sapuan adversarial ulang masih menemukan 33
lagi. Semuanya luput karena checklist di atas dibaca sebagai "endpoint CRUD
biasa". Periksa kelima kelas ini SECARA TERPISAH — bukan bagian dari CRUD:

1. **`require_admin` BUKAN gerbang satker.** Ia hanya mengecek `role ==
   "admin"`; admin yang terikat satker lolos sepenuhnya. Semua endpoint
   `/users` dan `/satker` sempat memungkinkan admin satker A mereset password
   admin B lalu login sebagai dia. Untuk akun, pakai
   `auth_utils.pastikan_kelola_akun(admin, target)`; untuk operasi seluruh-DB
   (backfill, migrasi, reset), pakai `require_super_admin`.
   **Catatan penting:** pada AKUN, `kode_satker` kosong berarti akun PUSAT
   (super-admin) — kebalikan dari dokumen, di mana kosong berarti "era lama,
   terbuka". Jangan pakai `pastikan_akses_dok_satker` untuk akun.

2. **Yang mengubah batas isolasi harus super-admin.** `PUT /users/{id}/satker`
   sempat bisa dipanggil admin atas dirinya sendiri dengan `kode_satker`
   kosong → naik pangkat jadi super-admin. Setiap field yang MENENTUKAN
   scope (ikatan satker user, `kode_satker` kegiatan) tidak boleh diubah oleh
   pemiliknya sendiri ke nilai yang memperluas akses.

3. **Laporan PDF/XLSX agregat sering melewatkan scope walau list-nya benar.**
   LBKP & CaLBMN memanggil `filter_aset_perhitungan({})` — helper itu TIDAK
   men-scope satker (docstring-nya menyebut ia dipanggil SESUDAH scoping).
   Pola benar: `filter_aset_perhitungan(await scope_query_aset(user, {...}))`.
   Ingat juga register PENDUKUNG di laporan yang sama (persediaan, PSP,
   pemanfaatan, penghapusan, idle, kasus) — masing-masing perlu di-scope.

4. **Koleksi jurnal/turunan yang tak ber-`kode_satker`.** `transaksi_persediaan`
   dan `mutasi_bmn` sengaja ramping. Isolasinya lewat RELASI:
   `persediaan_id` → master persediaan (helper `_scope_jurnal` di
   `routes/persediaan.py`), `asset_id` → aset → kegiatan (lihat `daftar_mutasi`).
   Kalau koleksi baru tak bisa distempel, tentukan jalur relasinya SEKARANG —
   jangan tinggalkan "nanti saja", karena filter apa pun kemudian tak punya
   pegangan. Kalau BISA distempel (mis. `lpb`), stempel sejak insert pertama.

5. **Master "referensi" yang sebenarnya milik satker.** Referensi UNIVERSAL
   (kodefikasi barang, akun BAS, masa manfaat, kategori) memang global.
   Tetapi ruangan, pejabat, dan setelan penomoran melekat pada satker —
   `ruangan` sempat sepenuhnya terbuka (admin A menghapus ruangan B), dan
   setelan persuratan dulu satu dokumen `type:"global"` yang bisa ditulis
   admin mana pun sehingga `kode_unit` satu satker mengubah nomor resmi semua
   satker. Uji pertanyaan ini: *"kalau dua satker mengisi ini berbeda, apakah
   keduanya benar?"* Bila ya → per satker, bukan global.

Dua pelengkap yang juga terbukti berulang:

- **WebSocket & endpoint non-REST ikut aturan yang sama.** `/ws/{activity_id}`
  memvalidasi token tetapi tak pernah membandingkan kegiatan dengan satker
  user — token JWT TIDAK membawa `kode_satker`, jadi harus dibaca dari
  dokumen user. Room kolaborasi menyiarkan perubahan aset & daftar user online.
- **"Publik demi kemudahan" hampir selalu keliru.** `doc-file` dibiarkan anonim
  dengan alasan tautannya dibuka dari spreadsheet — padahal UUID aset justru
  ditanam aplikasi ke CSV yang beredar, tanpa TTL dan tanpa pencabutan. Pola
  benar: `require_user_or_query_token` + tanam `?token=` ber-scope media
  (`create_media_token`) ke dalam tautan ekspor.

### Kesalahan ARAH SEBALIKNYA: men-scope yang memang bersama

Isolasi bisa salah ke dua arah. Men-scope koleksi yang SENGAJA global sama
merusaknya dengan membiarkan yang privat terbuka — bedanya kerusakan ini
sunyi: fitur tetap "jalan", hanya datanya terpecah diam-diam.

Kasus nyata (R10): `penganggaran_kalender` sempat distempel + di-scope.
Padahal ia KONFIGURASI BERSAMA — satu siklus anggaran nasional, terdaftar di
`RESET_KEEP_COLLECTIONS` bersama `masa_manfaat`/`akun_bas`/`kodefikasi`, dan
DUA sapuan isolasi sebelumnya sengaja melewatinya sambil menstempel
`db.penganggaran` di file yang sama. Setelah di-scope, tahapan baru yang
dibuat satu satker jadi tak terlihat satker lain — kalender bersama pecah.

Sebelum menstempel/men-scope koleksi, buktikan dulu ia per-satker:
1. Apakah ada penulis yang SUDAH menyetel `kode_satker`? (grep penulisnya)
2. Apakah ia terdaftar di `RESET_KEEP_COLLECTIONS` sebagai konfigurasi?
3. Apakah sapuan isolasi sebelumnya MELEWATINYA padahal menyentuh file itu?
   (`git log -p` file tersebut) — kalau ya, itu keputusan, bukan kelalaian.
4. Uji pertanyaan pemilik: *"kalau dua satker mengisi ini berbeda, apakah
   keduanya benar?"* Tidak → memang bersama.

Petunjuk diagnostik: bila perbaikan yang diusulkan **tidak mengubah perilaku
apa pun** (mis. menambah `scope_query_field_satker` pada koleksi yang seluruh
dokumennya tanpa `kode_satker` — `$in` memuat `None` sehingga cocok semua),
berarti model datanya salah dibaca. Perbaikan yang no-op = temuan yang keliru.

**Cara memverifikasi, bukan sekadar membaca:** jangan percaya "sudah ditutup di
gelombang lalu". Grep pola mentahnya di seluruh `routes/` dan periksa satu per
satu terhadap kode SAAT INI:
`db\.\w+\.(find|count_documents|aggregate)\(\{\}` (query kosong),
`find_one\(\{"id":` (get-by-id tanpa guard), `counters` (deret nomor),
`type": "global"` (setelan bersama).

## Jurnal Buku Barang (`mutasi_bmn`) — aturan TERKUNCI audit

1. **Semua transaksi keluar/nilai berjurnal** — modul yang membuat aset
   keluar buku (SK penghapusan 301, pemindahtanganan 301/303, alih status &
   idle 302) atau menggeser nilai (pemeliharaan 202, revaluasi 204/205,
   perolehan 100/101/102/103/105) WAJIB `await catat_mutasi_bmn({...})`
   (best-effort — tak menggagalkan transaksi pemanggil). LBKP/LBP/CaLBMN
   membaca JURNAL, bukan hanya tombstone master.
2. **Selalu sertakan `ref_id`** (id dokumen sumber) — guard anti jurnal
   ganda terpusat memakai kunci `(asset_id, kode_transaksi, ref_id)`.
3. **`jumlah: 0` untuk transaksi murni NILAI** (202/204/205 — rupiah
   bergeser, unit tidak); `jumlah: 1` hanya bila barang benar-benar
   masuk/keluar.
4. **204 vs 205**: kode dari tanda selisih; `nilai` = magnitudo POSITIF
   (konsumen LBP menegatifkan 3xx/4xx **dan 205** — satu-satunya 2xx
   berarah kurang).
5. **Register yang sudah berjurnal TIDAK boleh dihapus** — tolak 409, minta
   koreksi pembalik (pola `hapus_koreksi_nilai`, `hapus_proses`,
   `delete_pemeliharaan`).
6. **Jurnalkan hanya aset yang benar-benar terproyeksi** — helper proyeksi
   terminal mengembalikan daftar id yang berubah; aset yang sudah keluar
   buku lewat jalur lain tidak dijurnal KURANG dua kali.

## Performa & keandalan tulis — pola baku

- **Render dokumen berat (reportlab `doc.build`, weasyprint `write_pdf`,
  PIL) WAJIB `await asyncio.to_thread(...)`** — satu render sinkron
  membekukan seluruh server. Endpoint sangat mahal + `@limiter.limit(...)`
  (perlu `request: Request` di signature).
- **Loop impor/massal: muat data pembanding SEKALI jadi peta** — jangan
  `find_one` per baris (file 5.000 baris = ribuan query beruntun).
- **POST pencipta dokumen resmi ber-`Idempotency-Key`** (pola PATCH aset /
  POST /bast): reservasi `reserve_idempotency_key` di awal, cache respons
  `store_idempotent_response` di akhir. Frontend: satu kunci per pembukaan
  form, **ganti kunci setelah kegagalan validasi** (reservasi "pending"
  menggantung ±30 dtk).
- **Cache ringkasan**: daftarkan namespace di `_CACHE_LOCAL`/`_CACHE_TTL`
  `shared_utils.py` (Redis bila aktif, TTLCache per-worker bila tidak) —
  kunci menyertakan satker.
- **Komponen React JANGAN didefinisikan di dalam komponen halaman** — tipe
  baru tiap render → seluruh subtree remount (avatar berkedip, fetch
  ulang). Angkat ke level modul; callback lewat prop.
- **Daftar ribuan baris**: jendela render (slice + "Tampilkan N lagi"),
  ingat daftar sering dirender DUA kali (kartu HP + tabel desktop).

## Backup / restore / reset — saat menambah koleksi/fitur

- Koleksi BARU otomatis ikut backup/restore/reset (enumerasi dinamis) —
  tapi WAJIB ditimbang: transien → `SKIP_COLLECTIONS`; konfigurasi/master →
  `RESET_KEEP_COLLECTIONS`; `_id` bermakna → `KEEP_ID_COLLECTIONS`
  (`backend/backup_utils.py`, teruji unit).
- Retensi arsip hanya menghapus `backup_otomatis_*` terurut STEMPEL WAKTU —
  jangan pernah menghapus backup manual otomatis.
- Deteksi job macet memakai `updated_at` (denyut progres), bukan umur sejak
  mulai.
- Pola restore: parse manifest SEBELUM wipe; safety snapshot ke DISK per
  koleksi (bukan dict RAM); reindex Meilisearch pasca-restore/reset bila
  aktif.

## Pipeline ship per fitur (urutan eksak)

```bash
# 1. Pastikan branch bersih di atas main terbaru
git fetch origin main && git checkout -B <branch-kerja> origin/main

# 2. Bangun fitur (kecil — satu fitur satu PR)

# 3. Verifikasi lokal
cd backend && python -m pytest tests/unit -q          # unit test
cd frontend && npx eslint <file-berubah> --max-warnings=0
CI=false yarn build                                    # build produksi

# 4. Commit (Indonesia) + push
git push -u origin <branch-kerja>

# 5. PR DRAFT → tunggu CI hijau (check-runs) → tandai ready → SQUASH merge
# 6. Merge ke main memicu deploy.yml → pantau sampai "Deploy selesai"
# 7. Reset branch kerja ke main untuk fitur berikutnya
git fetch origin main && git checkout -B <branch-kerja> origin/main
git push --force-with-lease -u origin <branch-kerja>
```

Definisi Selesai: CI hijau · terdeploy · UI Indonesia · offline OK (fitur
lapangan) · CHANGELOG terisi (entri `[#PR]`) · tanpa regresi lint/test.

**Dokumentasi ikut PR yang sama**: CHANGELOG selalu; README + halaman PRD
(`frontend/src/pages/InfoPage.jsx`) bila fitur besar; `bmnModules.js` bila
status modul berubah.

## Jebakan yang sudah pernah menggigit

- `yarn.lock` harus di-regenerate bila menambah dependency (CI pakai
  `--frozen-lockfile`).
- Deploy gagal `Permission denied` padahal kunci benar → cek
  `authorized_keys` baris menempel (butuh newline sebelum append).
- Deploy gagal "Tidak bisa terhubung ke VPS" berulang (keyscan 5x pun
  gagal, lintas run/IP runner) = VPS-nya yang tumbang/SSH mati — BUKAN
  salah workflow/secrets. Pemulihan: cek hPanel Hostinger (status VPS,
  restart, sshd, firewall, RAM penuh). Kode di `main` aman; setelah VPS
  hidup, picu deploy via tab Actions → "Deploy ke Hostinger VPS" → Run
  workflow (atau merge PR berikutnya). Insiden: 2026-07-11 ±23:14 UTC,
  3 run gagal beruntun.
- Re-run workflow lama ≠ menjalankan workflow baru — pakai "Run workflow".
- Test laporan: `scripts` smoke FakeDB di scratchpad sesi lama — pola:
  render semua laporan ke PDF via pypdfium2 tanpa Mongo.
- Radix Select di bawah overlay kamera tidak muncul (z-index portal).
- Tanggal `9999-12-31` → `OverflowError` pada strptime: tangkap
  `(ValueError, OverflowError)`.
- Efek refetch harus menyertakan SEMUA filter di deps — filter baru yang
  lupa didaftarkan tidak memicu muat ulang.
- Sesi Claude Code yang sangat panjang: token konektor GitHub bisa
  kedaluwarsa sesaat ("requires re-authorization") — coba ulang dulu
  (token biasanya diperbarui otomatis); bila tetap gagal, PR yang CI-nya
  hijau bisa di-merge manual lewat tombol GitHub, pekerjaan tidak hilang.
- Check CI "cancelled" berpasangan / run "startup_failure" / antre >10 mnt
  tanpa job = antrean GitHub Actions macet, BUKAN kegagalan kode — picu
  ulang dengan `git commit --allow-empty` + push. Insiden 2026-07-25:
  antrean macet ±35 menit lalu pulih sendiri.
- Import Python di dalam fungsi menjadikan nama itu VARIABEL LOKAL —
  pemakaian nama yang sama SEBELUM baris import di fungsi yang sama =
  `UnboundLocalError` di runtime (lolos compileall!). Contoh nyata: `_esc`
  di PDF BA Pemusnahan membuat endpoint 500 permanen.
- Nomor entri CHANGELOG `[#N]` = **nomor PR + 2** (bergeser sejak `[#276]`)
  — catatan resminya ada di kepala CHANGELOG.md.
- `rekap`/`agregasi` yang membaca `jumlah` jurnal: field ABSEN = 1 unit,
  tapi `jumlah: 0` eksplisit harus dihormati (jangan pakai `or 1`).

## Checklist pemilik proyek (setingan untuk kesuksesan bertahap)

Sekali pasang:
- [x] Secrets GitHub Actions: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
      (+opsional `VPS_PORT`) — kunci privat HANYA di secret, jangan pernah
      ditempel di chat/tempat lain; rotasi bila bocor.
- [ ] Branch protection `main`: wajib CI hijau sebelum merge (Settings →
      Branches → Require status checks).
- [ ] Backup MongoDB terjadwal di VPS (cron `mongodump` harian + salin ke
      luar server mingguan) — fitur Backup aplikasi bukan pengganti backup
      infrastruktur.
- [ ] Pantau kapasitas disk VPS (foto GridFS tumbuh); siapkan alarm 80%.

Tiap siklus fitur:
- [ ] Tulis permintaan fitur sekecil mungkin & satu per satu — "satu fitur,
      satu PR" membuat rollback dan review mudah.
- [ ] Setelah deploy: uji singkat di HP lapangan (online + offline + kembali
      online) sebelum minta fitur berikutnya.
- [ ] Sebelum modul baru dibangun: sepakati kontraknya di
      `docs/MASTERPLAN-SIKLUS-BMN.md` (data apa dibaca/ditulis dari mana).
- [ ] Simpan file impor/ekspor contoh (Excel SIMAN dsb.) — bahan uji
      kompatibilitas saat modul pembukuan/rekonsiliasi dibangun.
