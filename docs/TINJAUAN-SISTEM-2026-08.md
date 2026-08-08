# Tinjauan Sistem AMAN — Agustus 2026

Tinjauan menyeluruh baca-saja atas backend, frontend, model data, operasional, keamanan
multi-satker, integritas data, dan ketahanan model domain BMN terhadap perubahan aturan.
Setiap temuan berjangkar pada berkas dan nomor baris. Tidak ada berkas kode yang diubah
dalam penyusunan dokumen ini.

Semua temuan di bawah sudah melewati fase sanggah: klaim yang tidak bertahan dipindahkan
ke Bagian 4 dan **tidak boleh** dipakai sebagai dasar keputusan.

---

## 1. Ringkasan untuk pemilik

Sistem ini **sehat secara struktural** dan jauh di atas rata-rata aplikasi seukurannya:
nol ketergantungan melingkar antar-modul, satu titik koneksi basis data, indeks terpusat
berkomentar sebab-akibat, gerbang CI yang benar-benar menutup jalur deploy, dan 2.194 uji
unit yang lulus dalam 40 detik tanpa infrastruktur. Fondasinya layak dipertahankan apa adanya.

Yang paling mendesak **bukan** soal skala, melainkan soal *ketidaktahuan*: **tidak ada satu
pun yang memantau sistem ini.** Probe `/api/health/deep` yang bagus itu hanya dipanggil oleh
skrip deploy; backup otomatis menandai dirinya "berhasil" sebelum benar-benar berhasil; dan
deploy tidak punya jalan pulang. Artinya cara pertama Anda tahu ada masalah tetap: pengguna
menelepon. Memasang satu monitor eksternal ke URL yang sudah ada adalah pekerjaan nol baris
kode dan menutup separuh risiko operasional.

Setelahnya, tiga hal yang benar-benar salah hari ini: urutan "Harga Tertinggi" memberi
hasil keliru, berkas rekonsiliasi SAKTI menjumlahkan persediaan seluruh satker, dan satu
dependensi hook yang hilang bisa membuat foto Mode Kamera Penuh lenyap tanpa pesan.

**Yang JANGAN diutak-atik:** `asset_fields.py` + uji registry-nya, `pembukuan_utils.py`,
`gerbang_media.py`, arsitektur cache berlapis, keyset pagination snapshot luring, komentar
panjang di seluruh repo, uji anti-regresi yang ada, dan pemisahan uji unit vs integrasi.
Semua itu adalah hasil kerja mahal yang sedang bekerja dengan benar.

---

## 2. Apa yang sudah benar

Bagian ini bukan basa-basi. Saran perbaikan cenderung menggoda orang membongkar hal yang
sehat; daftar ini adalah pagarnya.

### Arsitektur

| Hal | Bukti | Kenapa layak dipertahankan |
|---|---|---|
| Nol siklus impor level-modul | DFS atas graf impor 148 modul (86 level-atas + 62 di `routes/`) | Urutan impor tidak pernah jadi sumber kegagalan misterius. Langka pada basis kode 118 ribu baris. |
| Lapisan util murni | Hanya 11 dari 86 modul level-atas mengimpor `db` (`grep -l 'from db import' backend/*.py \| wc -l` → 11) | Inilah sebabnya 2.194 uji unit bebas-infra bisa ada. |
| `pembukuan_utils.py` (461 baris, fan-in 26) | `parse_harga`, `klasifikasi_komptabel`, `build_dbkp_rows`, `build_lbkp_rows`, `posisi_neraca` | Logika akuntansi BMN paling berisiko justru yang paling mudah diuji. Jadikan cetakan, jangan sentuh. |
| `asset_fields.py` + `tests/unit/test_asset_field_registry.py` | Menagih 8 turunan; nol drift saat diperiksa | Pola registry + meta-test yang benar-benar bekerja. Perluas, jangan ganti. |
| `auth_utils.py` sebagai titik otorisasi tunggal | fan-in 61, tanpa junk drawer | Satu tempat untuk menilai keamanan otorisasi. |
| Disiplin `asyncio.to_thread` | 107 pemakaian; `reports.py:5467`, `exports.py:879`, `media.py:374` | Yang mencegah satu unduhan PDF membekukan worker. Pola baku — samakan yang menyimpang. |
| Gerbang CI + deploy | `.github/workflows/deploy.yml:36,42` (`workflow_run` + `head_sha`) | Commit yang di-deploy persis commit yang lulus CI. Banyak tim salah di titik ini. |
| Uji endpoint in-process | 23 berkas `tests/unit/*` memakai `mongomock_motor`; `test_belah_endpoint.py` | Handler asli dijalankan tanpa Mongo. Perkakasnya sudah ada — perluasan cakupan tidak butuh infrastruktur baru. |

### Data & skala

- **`backend/indexes.py` sebagai satu sumber definisi indeks**, dengan komentar yang
  menjelaskan kueri mana yang dilayani (mis. `:193-197`, `:335-346` yang lahir dari
  pengukuran `mongotop`, bukan tebakan). Ini dokumentasi hidup.
- **Indeks unik dipakai sebagai penegak invarian**, bukan sekadar optimasi:
  `iot_observasi.obs_id` (`indexes.py:439`), `assets.idem_key` partial (`:119-122`),
  `tautan_pendek.kode` (`:539`).
- **Retensi dikerjakan MongoDB sendiri, bukan job yang bisa mati diam-diam**: TTL
  `unduhan.hapus_pada` (`:322`), `background_jobs` 7 hari (`:314`), `iot_observasi` yang
  angkanya hidup di satu tempat (`privasi_utils.batas_retensi()`).
- **Keyset pagination di `/assets/offline-snapshot`** (`routes/assets.py:549-565`) dengan
  alasan memilih `id` alih-alih `created_at` ditulis eksplisit. Penalaran yang tepat.
- **`ws_events` sebagai capped collection** (`event_bus.py:29-30`) — bus realtime yang
  secara struktural tak bisa tumbuh tanpa batas.
- **Cache berlapis Redis→TTLCache** dengan bump generasi lintas-worker, dan kunci cache
  membawa `kode_satker` sehingga tidak bocor antar satker.

### Keamanan & integritas

- **Helper isolasi terpusat dipakai luas**: `scope_query_field_satker` 205 callsite,
  `pastikan_akses_dok_satker` 118 callsite. Dari 271 endpoint mutasi hanya 11 tanpa
  `require_writer`/`require_admin`, dan kesebelasnya memang disengaja.
- **`pastikan_akses_kegiatan_id` FAIL-CLOSED** saat kegiatan induk hilang
  (`shared_utils.py:938-960`). Jangan pernah dilonggarkan.
- **`_buang_efemeral`** (`auth_utils.py:253-258`): kunci `_super_admin_asli` dibersihkan
  agar tak bisa diselundupkan lewat restore backup pihak luar. Kelas serangan yang jarang
  diantisipasi.
- **Rantai anti-eskalasi di `routes/users.py`** (`:157-164`, `:201-206`) menutup tangga naik
  pangkat ke backup/restore seluruh sistem.
- **Peta kolaborasi publik**: tamu hanya bisa MENGUSULKAN; proyeksi publik
  `baris_titik_publik` (`peta_kolaborasi.py:551-568`) memakai ALLOWLIST eksplisit sehingga
  field baru otomatis tidak bocor. Pola ini layak ditiru modul lain.
- **CAS tahan-legacy** (`routes/assets.py:149-165`) dan **idempotensi tiga lapis** pada
  `POST /assets`. Jangan disederhanakan.
- **Rollback GridFS di PATCH** dengan urutan yang benar (`assets.py:2517-2530`, `:2334-2337`)
  — mahal untuk ditemukan ulang.
- **Kompensasi eksplisit di persediaan** (`persediaan.py:2075-2083`) dan `penilaian.py:405-415`.
  Ini teladan yang seharusnya ditiru sisi aset.

### Frontend & operasional

- **Code splitting nyata berjalan**: 59 titik `lazy(() => import(...))`; Leaflet, recharts,
  dan geoman terisolasi di potongan sendiri.
- **`components/BatasGalat.jsx:71-84`** — batas galat di LUAR Suspense dan sengaja tidak
  menawarkan "Coba lagi" untuk kegagalan unduh potongan, karena `React.lazy` mengingat
  penolakan `import()` selamanya. Detail yang hampir selalu salah di aplikasi lain.
- **Virtualisasi tiga daftar besar** dengan `getItemKey` ber-identitas aset, bukan indeks slot.
- **63 berkas uji di `src/lib/`** — logika berisiko sengaja dikeluarkan dari komponen.
- **Health gate dua lapis** (`scripts/deploy_vps.sh:31-34`, `:51-55`) dengan komentar yang
  menjelaskan jebakan `supervisorctl restart` mengembalikan 0 walau proses mati.
- **Backup mengenumerasi koleksi secara DINAMIS** (`backup_utils.py:123-132`) — modul baru
  otomatis ikut ter-backup.
- **Retensi hanya memangkas backup OTOMATIS dan hanya bila backup SUKSES**
  (`backup_utils.py:166-183`, `backup.py:930-938`). Cadangan manual tidak pernah terhapus sendiri.
- **Setiap layanan luar berkuota berakhir pada pengolah LOKAL** (`kompresi_rantai.py:32,37`).
  Kuota habis tidak pernah berarti "tak bisa mengompres sama sekali".
- **Penolakan tertulis untuk over-engineering** (`docs/LOGGING.md:29-53`,
  `docs/OPTIMASI-VPS.md:140-175`). Penilaian yang matang untuk 2 vCPU/8 GB.

---

## 3. Temuan per golongan

Skala ukuran PR: **XS** ≈ 1–10 baris · **S** ≈ satu berkas, < 100 baris ·
**M** ≈ beberapa berkas atau butuh backfill · **L** ≈ butuh perancangan tersendiri.

### 3A. CACAT — sudah salah sekarang

#### Prioritas tertinggi (kehilangan data / angka salah / sistem buta)

**C1 · `photoItems` hilang dari dependensi `handleSubmit` — foto Mode Kamera Penuh bisa lenyap tanpa pesan**
Larik dep di `frontend/src/components/assets/AssetForm.jsx:1938` tidak memuat `photoItems`,
padahal nilainya diiterasi di `:1758` untuk membangun `patch.photo_ops.add` dan dibaca di `:1687`.
Asimetrinya yang menentukan: jalur galeri cabang edit memanggil `setPhotoItems` **dan**
`setFormData` (`:1503-1508`) sehingga closure ikut segar; jalur kamera cabang edit hanya
`setPhotoItems` lalu `return` (`:1105`). Dikonfirmasi lint: `npx eslint src` →
`AssetForm.jsx 1938:6 missing dependency: 'photoItems'`.
*Dampak:* patch terkirim dengan `add: []`, chip baris berakhir "saved", dan byte fotonya sudah
tak ada di perangkat karena snapshot luring memang membuang foto. Intermiten — tertutup bila
kebetulan ada perubahan `formData` di antara jepretan dan ketukan Simpan.
*Usul (XS):* tambahkan cermin ref `photoItemsRef` (pola sudah dipakai di `DashboardPage.jsx:984-985`)
dan baca `photoItemsRef.current` **hanya** di `:1687` dan `:1758` — bacaan di JSX dan `:1442`
biarkan tetap membaca state. Larik dep tidak berubah, nol risiko render tambahan.
Memindahkan pembangun `photo_ops` ke `lib/photoOps.js` adalah **PR terpisah**.

**C2 · `purchase_price` disimpan sebagai STRING — urutan "Harga Tertinggi" salah**
`backend/models.py:210-215` memaksa `str(v)` di setiap jalur tulis; `routes/assets.py:454-455`
mengirim `[("purchase_price", 1), ("id", 1)]` apa adanya ke Mongo. Perbandingan string bersifat
leksikografis: `"10000000"` (10 juta) berurut SEBELUM `"9000000"` (9 juta). Frontend memang
memakainya (`DashboardToolbar.jsx:229-230`, `DashboardPage.jsx:799`), dan mode luring justru
mengurutkan **numerik** (`DashboardPage.jsx:148-149`) — jadi pengguna melihat urutan berbeda
untuk data yang sama tergantung daring/luring, yang terbaca sebagai bug sinkronisasi padahal bukan.
Tim sudah sadar nilainya bukan angka: filter rentang harga terpaksa `$expr`+`$convert`
(`assets.py:344-357`), sehingga indeks `sort_price_id` (`indexes.py:329`) tak pernah terpakai.
*Catatan penting:* bila di produksi ada campuran tipe (angka dari impor lama + string dari
Pydantic), MongoDB mengurutkan antar-tipe BSON lebih dulu — semua harga numerik menggerombol
di satu ujung terlepas nilainya.
*Usul (M, 3 PR):* (1) tulis field turunan `purchase_price_num` (double) di semua jalur tulis
tanpa pembaca; (2) backfill + indeks `(purchase_price_num, id)`; (3) alihkan sort dan blok
`$expr` ke field numerik, drop indeks mati. String tetap ditulis dan dikembalikan → nol klien rusak.
Uji anti-regresi wajib menyertakan kasus campuran tipe.

**C3 · Berkas rekonsiliasi SAKTI memuat persediaan SELURUH satker**
`backend/routes/reports.py:3893-3896`: `persediaan = await db.persediaan.find({}, {...}).to_list(100000)`
— filter KOSONG, padahal empat baris di atasnya (`:3881-3886`) aset sudah di-scope. Tiga kueri
persediaan lain di berkas yang sama melakukannya dengan benar (`reports.py:2690`, `:3591`,
`lbp.py:222`). Hasilnya langsung masuk `posisi_neraca` (`:3897-3898`), dan endpointnya menerima
token kueri (`require_user_or_query_token`).
*Dampak:* nilai persediaan di berkas rekonsiliasi resmi lebih saji dan tak akan pernah tie-out
dengan SAKTI satker itu; sekaligus data persediaan satker lain terbaca oleh yang tak berhak.
*Usul (XS):* ganti `find({}, ...)` → `find(scope_query_field_satker(_user), ...)`. Uji
anti-regresi dua-satker bergaya REVIEW-9 R15 yang sudah jadi pola repo.

**C4 · Tidak ada yang MEMANTAU — probe kesehatan hanya dipanggil skrip deploy**
`/api/health/deep` (`server.py:239-296`) berkualitas: ping Mongo + baca `fs.files`, balas 503
saat degraded. Satu-satunya pemanggilnya adalah `scripts/deploy_vps.sh:53-65`. Pencarian
menyeluruh atas `prometheus|/metrics|uptimerobot|healthchecks.io|betteruptime` hanya menemukan
`memory/ROADMAP.md:122` — yaitu rencana, bukan implementasi.
*Dampak:* Mongo mati, disk penuh, backend gagal start setelah reboot, backup berhenti — semuanya
tanpa pemberitahuan. Jarak antara "sistem sakit" dan "seseorang tahu" bisa berhari-hari.
*Usul:* **(nol kode)** daftarkan URL itu di UptimeRobot/Better Stack interval 5 menit dengan
notifikasi. **(S)** tambahkan `checks["disk"]` di `server.py:239-296` memakai `shutil.disk_usage`
seperti pola `backup.py:328`, tandai `ok:false` di bawah 15% bebas — monitor yang sama langsung
jadi alarm disk.

**C5 · Backup otomatis mengklaim tanggal SEBELUM sukses dan tak memberi tahu siapa pun bila gagal**
`backup.py:955-960` menulis klaim `{"terakhir": hari_ini}` lebih dulu, baru `:963` menjalankan
backup. Penjadwal menolak mencoba lagi hari itu (`backup_utils.py:200-201`). Satu-satunya jejak
kegagalan adalah `logger.warning` (`:936-938`). Layar Pengaturan menampilkan klaim itu sebagai
`Terakhir jalan` (`PengaturanPage.jsx:473`).
*Peredam yang perlu dicatat:* retensi **sudah** digerbangi keberhasilan (`backup.py:930-938`),
jadi kegagalan tidak memangkas arsip lama — skenario terburuknya "cadangan menua tanpa ada yang
tahu", bukan "tidak ada cadangan sama sekali". Dan `aktif` bawaannya `False` (`:884`), jadi ini
menggigit setelah backup otomatis dinyalakan.
*Usul (S):* pisahkan klaim dari hasil — tambah `terakhir_sukses`, `status_terakhir`,
`galat_terakhir`, tulis hanya setelah `job.status == "completed"`. Tampilkan `terakhir_sukses`
di UI dengan lencana merah bila gagal. **Bonus murah:** kosongkan `terakhir` saat gagal supaya
siklus 5 menit berikutnya mencoba lagi hari itu juga.

**C6 · Deploy tidak punya rollback, dan `yarn build` mengosongkan docroot sebelum membangun ulang**
`scripts/deploy_vps.sh` berjalan `set -euo pipefail` (`:6`), reset ke `origin/main` (`:16-17`),
restart (`:28-29`), gerbang kesehatan (`:37-71`), **baru** `yarn build` (`:74-76`). Tidak ada
jalur yang menyimpan atau mengembalikan commit lama. Docroot nginx menunjuk langsung ke direktori
build (`scripts/vps-deploy.sh:168`) dan react-scripts mengosongkannya di awal
(`react-scripts/scripts/build.js:72 fs.emptyDirSync`). Bukti terkuat: `grep -rn NODE_OPTIONS scripts/`
menemukannya di `vps-deploy.sh:105` dan `update-all.sh:209` **tetapi tidak di `deploy_vps.sh`** —
skrip yang benar-benar dipakai otomatis justru satu-satunya tanpa pagar memori, di mesin tanpa swap.
*Peredam:* `ci.yml:77` sudah menjalankan `CI=false yarn build`, jadi build gagal karena kesalahan
kode umumnya tertangkap sebelum menyentuh VPS. Yang tersisa: OOM di VPS.
*Usul (S, urutan penting):* (a) `export NODE_OPTIONS=--max-old-space-size=2048` — satu baris,
langsung menutup risiko terbesar; (b) `BUILD_PATH=frontend/build.new` lalu tukar atomik dengan
`mv` — nol detik docroot kosong, dan `build.old` menjadi rollback frontend instan;
(c) simpan `PREV=$(git rev-parse HEAD)` dan kembalikan bila gerbang kesehatan gagal.

**C7 · Skrip pemulihan darurat menunjuk cabang git yang sudah tidak ada**
`git ls-remote --heads origin` hanya mengembalikan `main` dan satu cabang kerja. Namun
`Deploy_Hostinger_VPS` muncul **8 kali**: `scripts/vps-fix.sh:74,83,615,628` dan
`scripts/update-all.sh:35,41,44,49`. Keduanya `set -e`, dan diuji langsung:
`bash -c 'set -e; V=$(git rev-parse origin/Deploy_Hostinger_VPS 2>/dev/null); echo LANJUT'`
tidak mencetak apa pun (rc=128).
*Dua varian kegagalan — sebutkan keduanya:* (a) skrip berhenti tanpa pesan; (b) **lebih berbahaya**
— bila klon di VPS masih menyimpan ref pelacak lama (fetch tanpa `--prune`), `rev-parse` berhasil
dan `git reset --hard` justru **memutar mundur produksi ke commit beku**.
*Usul (XS):* ganti ke `origin/${DEPLOY_BRANCH:-main}` di 8 titik + pemeriksaan eksplisit di awal.
Lebih baik lagi: pindahkan keduanya ke `scripts/arsip/` dengan catatan pengarah ke `deploy_vps.sh`
— dua skrip yang tumpang tindih di jam 2 pagi adalah masalahnya sendiri.

**C8 · Laporan periode "TERKUNCI/FINAL" tidak membekukan angka**
`routes/pelaporan.py:134-141` hanya menulis status dan tanggal kunci — tidak satu parameter pun
ikut disimpan. Di endpoint CaLBMN yang sama, penanda FINAL dipasang di `reports.py:3532`
sementara masa manfaat dibaca ULANG dari DB saat cetak (`:3653`) dan ambang kapitalisasi di `:3570`.
Pola sama di `lbp.py:222,264`.
*Pemicunya konkret dan sudah ada di kode:* `routes/siman.py:206-232` menulis ulang
`db.masa_manfaat` setiap impor SIMAN, tanpa campur tangan manusia. Jadi jalur gagalnya lengkap:
kunci periode → impor SIMAN → cetak ulang → angka berbeda di bawah stempel FINAL yang dikirim
ke KPKNL.
*Usul (M):* saat kunci periode, simpan cuplikan parameter (`masa_manfaat`, `ambang_kapitalisasi`,
`akun_bas`) ke dokumen periode — tiga dict kecil, bukan angka laporan. Saat cetak, pakai
`periode_rec.get("parameter", ...)` dengan **fallback** ke perilaku sekarang: periode lama tetap
tercetak, nol migrasi. Uji: kunci → ubah `db.masa_manfaat` → cetak ulang → angka harus identik.

**C9 · Kolom SIMAN yang berganti nama menjadi "SIMAN bilang 0" — dan "terapkan" menulis nol**
`siman_utils.py:155-165` hanya mewajibkan `kode_barang` + `nup`; kolom tak dikenali diabaikan
diam-diam. `parse_baris:266` tetap mengisi `"nilai_perolehan": parse_harga(d.get(...))` dan
`parse_harga(None) → 0.0` (`pembukuan_utils.py:34-35`). Pembandingnya hanya menyaring `(None, "")`
(`:294-295`), jadi `0.0` lolos → seluruh aset dilaporkan berselisih → `nilai_terapkan` (`:331-333`)
mengembalikan `"0"`. Peta kolom sudah memuat dua ejaan `"tanggal pengapusan"`/`"tanggal penghapusan"`
(`:38-39`) — bukti header SIMAN memang pernah bergeser.
*Dampak:* satu perubahan judul kolom di ekspor SIMAN berikutnya → operator yang mengikuti panduan
aplikasi menulis nilai perolehan 0 ke master aset secara massal → DBKP/LBKP, penyusutan, dan
klasifikasi intra/ekstra semuanya nol.
*Usul (S):* isi kunci numerik dengan `None` (bukan `0.0`) bila kuncinya tidak ada di `peta_header`
— cabang `"angka"` otomatis aman. Sekalian kembalikan daftar kolom perbandingan yang tak ditemukan
dan tampilkan di ringkasan impor.

**C10 · Impor SIMAN satu satker menimpa referensi masa manfaat SEMUA satker**
`routes/siman.py:207-232` menulis `db.masa_manfaat` dengan `"sumber": "siman"`. Pagar di `:213-218`
hanya mengecualikan entri yang dikelola **manusia** — komentarnya sendiri berbunyi "impor SIMAN
milik satu satker TIDAK BOLEH menimpa entri yang dikelola manusia", yang berarti impor satker
**lain** memang tidak dipagari. Koleksinya global (`indexes.py:171` unik pada `kode` saja).
*Dampak:* satker B mengimpor, kelompok 30801 diderivasi 8 tahun; satker A yang sebelumnya 10 tahun
ikut berubah tanpa menyentuh apa pun. Digabung C8, LBP satker A pun berubah.
*Usul — langkah kecil dulu (S):* tolak penimpaan lintas-kode di dalam pagar `dilindungi`
(`siman.py:213-218`) dengan menstempel `kode_satker`+`observasi` pada entri ber-sumber siman.
Perilaku instalasi satu-satker tetap utuh. Usul yang lebih besar (koleksi `masa_manfaat_usulan` +
endpoint promosi super-admin + UI) realistis **dua PR** dan bukan langkah pertama.

**C11 · PostHog session recording aktif tanpa syarat di halaman produksi**
`frontend/public/index.html:244-247` memanggil `posthog.init(...)` dengan `session_recording`
di dalam skrip yang sama dengan registrasi service worker — bukan di balik gerbang env maupun
iframe. Terkonfirmasi ikut ke bundel: `grep -o "us.i.posthog.com" frontend/build/index.html` → 1.
`grep -in posthog docs/DPIA-PELACAKAN-ASET.md` → nihil.
*Dampak:* perekaman sesi merekam apa yang tampil di layar — NIK/NIP pegawai dan data BMN lintas
satker — lalu mengirimkannya ke penyedia di AS, di luar jaminan DPIA dan di luar redaksi PII yang
dibangun susah payah di backend (`docs/LOGGING.md:11` menyensor NIK di log server sementara layar
berisi NIK yang sama direkam utuh).
*Usul (XS):* hapus blok PostHog. Bila analitik memang diinginkan, kembalikan di balik
`process.env.REACT_APP_POSTHOG_KEY` dengan `session_recording` MATI dan `mask_all_text: true`,
lalu catat keputusannya di `docs/DPIA-PELACAKAN-ASET.md`.
*(Lihat Bagian 4: klaim "kunci bocor" dan "tiga host luar" pada temuan ini GUGUR.)*

#### Isolasi satker & akuntabilitas

**C12 · `DELETE /api/categories-all` menghapus master kategori SELURUH satker**
`routes/categories.py:120-125`: `Depends(require_admin)` + `db.categories.delete_many({})`.
`require_admin` (`auth_utils.py:376-380`) hanya memeriksa `role == 'admin'`; super-admin adalah
konsep terpisah. Koleksi `categories` tak berdimensi satker. Tidak ada `log_audit` di berkas ini.
`delete_category` (`:102-118`) justru menolak 409 bila kategori masih dipakai — jalur `-all`
melewati guard itu sepenuhnya.
*Usul (XS):* ganti ke `Depends(require_super_admin)`, tambah `log_audit`, pertahankan
`invalidate_category_cache()`. Pertimbangkan mengangkat guard "masih dipakai" ke level `-all`.

**C13 · `routes/users.py` tidak meninggalkan satu pun jejak audit**
Berkas 210 baris, tidak pernah mengimpor `log_audit`, dan tidak punya `$push riwayat` seperti
`pelaporan.py:135-170`. Yang tak tercatat: `toggle_user_active` (`:63-78`),
`change_user_password` (`:80-104`), `update_user_name` (`:106-119`), `delete_user` (`:121-133`),
`set_user_satker` (`:135-174` — **menggeser batas isolasi**), `change_user_role` (`:177-209`).
*Dampak:* aksi paling berbahaya dalam aplikasi multi-tenant justru yang paling tidak terlacak.
Guard eskalasinya bagus, tapi guard hanya mencegah yang dilarang — ia tidak mencatat yang diizinkan.
*Usul (S):* satu `log_audit` per handler mutasi dengan `activity_id=""`, `asset_id=user_id`.
**Penting:** stempel `kode_satker` harus kode satker **TARGET** (`str(user.get("kode_satker") or "")`),
bukan kode admin pelaku — untuk super-admin pusat kode pelaku kosong sehingga catatannya kembali
tak terlihat siapa pun. Untuk `set_user_satker`, catat kedua kode di `detail`.

**C14 · Aksi berdampak dicatat sehingga tak pernah muncul di layar audit satker sendiri**
Dari 131 pemanggilan `log_audit` di `routes/`, 62 membawa `kode_satker` dan **44** ber-`activity_id`
kosong **tanpa** `kode_satker` (dihitung dengan pencocok tanda kurung berimbang atas seluruh
`routes/*.py`). Penyaringnya: `routes/audit.py:87-91` dan `_batas_activity_satker` (`:56-57`)
hanya meloloskan `{"activity_id": "", "kode_satker": kode}`.
*Lingkup sebenarnya lebih kecil dari 44:* sebagian memang milik super-admin pusat atau setelan
seluruh-DB (`satker.py:188,205,240`, `referensi_akun.py:249,270,291`, `mutasi_bmn.py:307`) dan
menyembunyikannya dari admin satker justru sesuai desain. Yang benar-benar merugikan:
`ttd.py:725,1521,1574,1774`, `bast.py:656,687,780,859`, `ruangan.py:81,109,146`, `pejabat.py:219`,
`persediaan.py:519,1619`, `mutasi_bmn.py:247`.
*Dampak:* admin satker membuka halaman Audit dan TIDAK melihat pembatalan TTD, pembuatan BAST,
penghapusan ruangan/pejabat, atau reklasifikasi aset — di satkernya sendiri. Kegagalan diam:
layar tampak sehat dan justru meyakinkan.
*Usul (S per modul):* tambahkan `kode_satker=...` — pola benar sudah ada di `spasial.py:1738`
dan `peta_kolaborasi.py:1283`. Kerjakan `ttd.py` dan `bast.py` dulu (paling sering disengketakan).

**C15 · Syarat kekuatan kata sandi bocor di jalur admin**
`routes/users.py:83-85` hanya `len(new_password) < 8`, sementara `periksa_kekuatan_password`
(`auth_utils.py:30`) dipakai di `routes/auth.py:126` dan `:240`. Docstring helper itu
(`auth_utils.py:24-29`) menjelaskan bahwa ia dibuat justru karena reset-password dulu hanya
menuntut 8 karakter sehingga akun bisa jadi `"aaaaaaaa"` — persis kondisi yang masih berlaku di
`users.py`.
*Usul (XS):* pakai helper yang sama + satu uji yang menegaskan ketiga jalur menolak masukan yang
sama. Pastikan layar admin juga memakai `frontend/src/lib/passwordRules.js` supaya pengguna tak
menemui 400 yang mengejutkan.

**C16 · Tabel referensi & setelan GLOBAL bisa diubah admin satker mana pun**
Paling tajam: `PUT /pembukuan/ambang-kapitalisasi` (`routes/mutasi_bmn.py:279-281`,
`Depends(require_admin)`) menulis dokumen tunggal `report_settings{type:"kapitalisasi"}`
(`:299-305`); pembacanya global (`shared_utils.py:1036-1044`, docstring-nya sendiri menyatakan
"dipakai seluruh laporan pembukuan"). Pola sama tanpa pagar super-admin di `kodefikasi.py:213,229,240,275`,
`referensi_akun.py:276`, `akun_bas.py:81,99`, `persediaan_akun.py:85,107`, `categories.py:103,121`.
`DELETE /kodefikasi/{kode}` hanya mengecek turunan, bukan aset pemakai.
*Dampak:* admin satker A mengubah ambang kapitalisasi dan seketika neraca serta DBKP/LBKP SEMUA
satker berubah. Karena ini setelan akuntansi, kesalahannya baru ketahuan saat rekonsiliasi.
*Usul (S):* pola sudah ada dan terbukti — angkat `_wajib_super_admin` dari `routes/penilaian.py:83-93`
ke `auth_utils.py`, pasang sebagai guard **di dalam badan fungsi** (bukan mengganti `Depends`),
tambah `log_audit`. Untuk `DELETE /kodefikasi/{kode}` tambahkan cek `db.assets.count_documents`
dan tolak 409.
*(Lihat Bagian 4: `masa_manfaat` dan `sbsk_standar` SUDAH dipagari — jangan disertakan.)*

**C17 · `backfill_saldo_awal` menulis jurnal Buku Barang tanpa stempel satker**
`routes/mutasi_bmn.py:116-126` memanggil `db.mutasi_bmn.insert_one({...})` langsung, melewati
penulis kanonik `catat_mutasi_bmn` (`shared_utils.py:1107-1154`) yang sejak REVIEW-9 R10 sengaja
menurunkan dan menstempel `kode_satker` (`:1136-1149`). Karena `scope_query_field_satker` menyusun
`{"$in": [kode, "", None]}`, entri tanpa stempel cocok untuk **setiap** satker.
*Arah yang jujur:* ini bukan satker A membaca data satker B — ini entri milik A yang ikut tampil
di daftar B. Kategori "dokumen tanpa stempel = terlihat semua satker" sudah ada sebagai konvensi
era-lama yang disengaja (`mutasi_bmn.py:60-61`). Yang salah adalah jalur tulis **baru** yang masih
memproduksi dokumen tanpa stempel hari ini.
*Usul (XS):* ganti `insert_one` menjadi `await catat_mutasi_bmn({...})` — helper sudah idempoten
lewat guard `ref_id` dan menurunkan satker sendiri.

#### Integritas & kehilangan blob

**C18 · Hapus massal aset per kegiatan membocorkan seluruh blob GridFS**
`routes/exports.py:287-326` mencabut dokumen dari Meili lalu `:314 delete_many({"activity_id": ...})`
— nol pengumpulan `photo_gridfs_ids`/`bast_file_id`/`document_checklist`. Jalur yang BENAR ada
persis di `routes/activities.py:988-1014` dengan komentar "afterwards their blob ids are lost →
orphans". Penyapu berkala (`jobs.py:118-119`) hanya menyasar artifact ekspor.
*Yang membuatnya permanen:* setelah bulk-delete, menghapus kegiatannya pun tidak menolong — loop
cascade di `activities.py` beriterasi atas `db.assets.find(...)` yang sudah kosong. Id blob-nya
ikut lenyap bersama dokumen aset, jadi byte-nya tak pernah bisa ditemukan lagi.
*Usul (S):* angkat blok `activities.py:991-1014` menjadi helper bersama
`cascade_hapus_blob_aset(activity_id)` dan panggil dari KEDUA tempat. Uji anti-regresi menghitung
`fs.files` sebelum/sesudah.

**C19 · Hapus kegiatan menghapus semua asetnya tanpa menulis jejak apa pun**
`routes/activities.py:1029 delete_many({"activity_id": ...})`; `grep -n log_audit
backend/routes/activities.py` → tanpa hasil. Bandingkan `exports.py:319` yang menulis
`log_audit("bulk_delete", ...)`. Dua konsumen jejak itu buta: `routes/assets.py:581-590`
(`deleted_ids` dan `requires_full_refresh` diturunkan dari audit) dan `routes/lbp.py:243-254`
(tombstone LBKP dibaca dari audit beserta `changes[purchase_price].from`).
*Dampak:* nilai aset yang lenyap tidak pernah muncul sebagai baris "mutasi kurang" pada LBKP —
saldo periode turun tanpa baris penjelas, dan pemeriksa tak punya cara merekonstruksinya.
Klien luring yang sedang berada di dalam kegiatan itu tak mendapat sinyal apa pun dan antrean
simpannya berakhir 404.
*Usul (XS):* satu `log_audit("bulk_delete", activity_id, ...)` sebelum `delete_many`.
**Tunda** langkah kedua (satu audit per aset) — pada kegiatan 5.000 aset itu berarti 5.000 dokumen
audit dalam satu request; ukur dulu.

**C20 · Sinkron snapshot luring memajukan `lastSync` walau berhenti separuh jalan**
`frontend/src/lib/offlineSnapshot.js:229-233` menyetel `quotaHit = true; break;` lalu `:260-263`
tetap menulis `lastSync: lastSyncCursor`, yang diisi dari `server_time` **halaman pertama** (`:194`).
Sinkron berikutnya memakai `since = meta.lastSync` (`:165`) → baris yang belum sempat ditarik
punya `updated_at < since` dan tidak pernah ikut delta. Lubang permanen sampai TTL 7 hari.
*Koreksi penting:* peringatannya **ada** — `DashboardPage.jsx:1004-1010` memancarkan toast
"Penyimpanan perangkat hampir penuh… kosongkan ruang lalu sinkron ulang". Yang cacat adalah
**obat yang disarankannya tidak bekerja**: sinkron ulang berjalan sebagai delta dari kursor yang
sudah terlanjur maju.
*Usul (XS):* saat `quotaHit`, jangan tulis `lastSync` baru — pertahankan yang lama (atau tulis
`null` untuk memaksa full-sync berikutnya). Satu baris kondisi di sekitar `:261`.

**C21 · Kuota IndexedDB ditangani anggun di cache BACA, ditelan diam di antrean TULIS**
`grep -rn "isQuotaExceeded" frontend/src` → hanya `lib/idbErrors.js`, `lib/offlineSnapshot.js`,
dan uji; nol kemunculan di `hooks/useOptimisticQueue.js`. `persistQueueItem` (`:119-130`) punya
cabang catch yang **benar-benar kosong di produksi**. Muatannya besar: 900 KB/foto
(`lib/imageCompression.js:72`) × hingga 6 foto.
*Dampak:* simpanan luring gagal ditulis tanpa satu pesan; antrean hanya hidup di memori. Chip
barisnya tetap menampilkan "queued" seperti biasa. Begitu tab ditutup atau di-swap keluar Android,
seluruh muatan itu hilang termasuk fotonya. Prioritasnya terbalik: cache BACA yang selalu bisa
disinkron ulang diberi peringatan; kerja BELUM TERKIRIM yang tak bisa dipulihkan diam sepenuhnya.
*Usul (S):* impor `isQuotaExceeded` yang sudah ada, panggil callback baru sekali per sesi,
DashboardPage menampilkan `toast.error(..., { duration: 0 })`. Uji pemetaan galat→keputusan di
`lib/` (pola `lib/idbErrors.test.js`).

**C22 · Peta Aset keep-alive memuat ulang di latar walau tersembunyi**
`components/assets/AssetMapFullView.jsx:481-494` melakukan paging berurutan sampai 100×500;
efeknya `:534-539` tanpa penjaga `visible` (prop `visible` hanya dipakai untuk `invalidateSize`
di `:670-680`). `load` berubah identitas tiap kata kunci berubah (`:531`,
`DashboardPage.jsx:1237-1245`), dan petanya sengaja keep-alive (`DashboardPage.jsx:300,1879-1880`).
*Magnitudo dikoreksi:* ada penjaga `loadSeqRef` (`:472-473,487`) yang menghentikan loop lama
setelah halaman yang sedang terbang. Jadi biayanya **bukan** 60 kueri per tiga kata kunci,
melainkan ≈ satu halaman sisa per kata kunci yang tersalip + satu paging penuh untuk kata kunci
yang akhirnya mengendap (≈20 permintaan pada kegiatan 10.000 aset). Tetap tidak sepele.
*Usul (XS):* penjaga `visible` pada efek — bila tersembunyi, tandai "perlu muat" dan tunda sampai
peta ditampilkan lagi. Perilaku yang dilihat pengguna tidak berubah sedikit pun.

**C23 · Reklasifikasi menulis dua baris jurnal SEBELUM master aset, tanpa CAS**
`routes/mutasi_bmn.py:232-233` dua `insert_one`, baru `:241-247 db.assets.update_one({"id": ...})`
— filter hanya `id` tanpa `version`, tanpa try/except.
*Lingkup yang jujur:* indeks unik `unique_asset_code_nup_activity` (`indexes.py:33-36`) mencakup
`activity_id`, jadi dua reklasifikasi serentak hanya bentrok bila kedua asetnya di kegiatan yang
sama. Dan `Idempotency-Key` (`mutasi_bmn.py:169-186`) sudah menutup double-click satu klien.
Yang tersisa: dua pengguna berbeda pada detik yang sama, **dan** — tanpa konkurensi sama sekali —
proses mati di antara insert dan update.
*Usul (XS, alternatif minimal dulu):* bungkus `update_one` dengan try/except dan hapus dua baris
jurnal (id-nya sudah dipegang di `keluar`/`masuk`) sebelum melempar. Membalik urutan + CAS penuh
menuntut penanganan 409 baru di frontend — **PR terpisah**.

#### Event loop & ketersediaan

**C24 · `broadcast_local` mengirim serial tanpa timeout**
`routes/websocket.py:134-150` loop `await ws.send_json(message)` tanpa `wait_for`;
`grep -n "wait_for|timeout" routes/websocket.py` → kosong. Dipanggil dari `_on_remote_event`
(`:184`, dijalankan dari **satu** loop tail bus di `event_bus.py:111`) dan `notify_asset_change`
(`:376`, di-await inline pada 6 jalur tulis aset).
*Dampak:* satu klien dengan koneksi setengah-mati (ponsel di area sinyal buruk) menggantung
`send_json` → loop tail `event_bus` berhenti mengonsumsi, sehingga **semua** notifikasi
lintas-worker tertahan di worker itu. Untuk jalur simpan, dampaknya terbatas pada kegiatan yang
sama. Ini cacat, bukan risiko skala: satu klien lambat sudah cukup.
*Usul (S):* `asyncio.gather` + `asyncio.wait_for(..., timeout=5)` + `return_exceptions=True`,
lalu tandai socket yang gagal sebagai mati. **Wajib juga memanggil `await ws.close()`** (atau
`manager.disconnect`) — mem-`pop` dari `self.active` tidak menutup koneksi dan buffernya tetap penuh.
Uji anti-regresi dengan socket tiruan yang menggantung.

**C25 · `POST /assets/cards/bulk` tanpa plafon, tanpa rate-limit, tanpa offload**
`routes/cards.py:1140-1164`: `to_list(len(asset_ids))` tanpa cap, lalu loop dengan
`_fetch_asset_history` (N+1 kueri), `_hydrate_cover_from_gridfs` (1 baca GridFS/aset), dan
seluruh kerja Pillow+QR+ReportLab di event loop. `grep -c to_thread routes/cards.py` → 0;
`grep -n limiter routes/cards.py` → kosong. Frontend juga tidak membatasi:
`lib/cakupanCetak.js:33-36` mengembalikan seluruh seleksi, dan seleksi bisa lintas halaman
lewat "Pilih semua N aset".
*Usul (XS lalu S):* (1) plafon eksplisit meniru `stiker.py:37 MAKS_STIKER=2000` dan
`exports.py:63 MAX_FOTO_EXPORT_ASSETS=5000` + `@limiter.limit("3/minute")` — dua baris, langsung
menutup kasus terburuk; (2) PR terpisah: pisahkan bagian murni-CPU ke fungsi sinkron,
hilangkan N+1 dengan satu `find({'asset_id': {'$in': ids}})`, bungkus `asyncio.to_thread`.
**Ukur dulu** dengan 100/500/1000 aset sebelum memaku angka plafon.

**C26 · `batch.py` membuat thumbnail Pillow di event loop**
`routes/batch.py:286` `generate_photo_thumbnail(...)` telanjang di dalam loop foto, dan `:289-290`
`create_thumbnail`/`create_gallery_thumbnail` juga. `grep -c to_thread routes/batch.py` → 0,
sementara fungsi yang **sama** sudah dibungkus benar di `routes/assets.py:1199,1209,1252,2697`,
dan `routes/activities.py:41-46` menulis eksplisit "WAJIB dipanggil lewat `asyncio.to_thread`".
*Angka yang diukur (bukan ditaksir):* JPEG 1600×1200 (~890 KB) → `create_thumbnail` ≈ 37 ms,
`create_gallery_thumbnail` ≈ 36 ms. Jadi 8 thumbnail ≈ 0,3 detik di mesin uji, mungkin ~0,5–0,6
detik di core VPS — **bukan** beberapa detik. Biaya sesungguhnya adalah dekode JPEG + resize,
bukan encode WebP. Dan `auto_compress_image` yang dipanggil tepat sebelumnya sudah memakai
`to_thread`, jadi blokirnya terpotong-potong.
*Usul (XS):* salin pola `assets.py:1199`. Jualnya adalah kerapian + jitter, bukan penyelamatan darurat.

**C27 · `workbook.close()` xlsxwriter tidak di-offload**
`routes/exports.py:1341` di dalam `async def bangun_xlsx_bytes` — sementara penyisipan gambar
di `:1022,1050,1145` **sudah** `await asyncio.to_thread`. `in_memory=False` (`:933`) memindahkan
arsip ke temp disk, tapi `close()` tetap harus membaca dan men-deflate seluruhnya, sinkron.
Poin paling berharga: memindahkannya ke job latar **tidak menolong**, karena `_jalankan_ekspor_xlsx`
adalah `asyncio.create_task` di event loop yang sama (`:1408`).
*Peredam:* `_EKSPOR_SEM = asyncio.Semaphore(2)` (`:1381`) dan `@limiter.limit("3/minute")`.
*Usul (XS):* bungkus jadi helper sinkron `_tutup_dan_ambil(workbook, buffer)` lalu `to_thread`.
Keluaran tidak berubah, uji yang ada tetap hijau.

**C28 · Parsing openpyxl seluruh berkas berjalan di event loop (5 modul)**
`grep -c to_thread` = 0 untuk `routes/siman.py`, `categories.py`, `imports.py`, `pegawai.py`,
`kodefikasi.py`. Semuanya `async def`, jadi FastAPI **tidak** melemparnya ke threadpool.
Yang paling tajam: `imports.py:173 all_rows = list(ws.iter_rows(values_only=True))` —
materialisasi seluruh sheet **tanpa** `read_only=True`.
*Ukuran terburuk terbatas:* nginx `client_max_body_size 50M` (`scripts/vps-deploy.sh:131`),
SIMAN 25 MB (`siman.py:73`), impor aset 15 MB (`imports.py:230`).
*Usul (XS × 3 dulu):* `imports.py:236`, `kodefikasi.py:285`, `persediaan.py:621` sudah memanggil
fungsi yang sinkron dan terpisah — cukup `await asyncio.to_thread(fn, content)`. `siman.py` dan
`categories.py` butuh sedikit ekstraksi; kerjakan belakangan.

**C29 · Job latar tanpa sapuan pemulihan saat startup**
`backend/jobs.py:137-151`: blok startup HANYA menyapu Pusat Unduhan (`:143-144`), lalu
`while True:` → `sleep(3600)` → baru `bersihkan_job_basi(60)`. Jadi `db.background_jobs` tidak
pernah disapu saat startup.
*Dampak:* setiap deploy (auto-deploy tiap merge) dan setiap OOM meninggalkan job yang tampak
`"importing"` — `GET /api/jobs/{id}` terus mengembalikan status itu dan frontend memutar spinner
tanpa akhir. Skenario terburuk: baru ditandai pada t≈2 jam.
*Usul (XS):* tambahkan `await bersihkan_job_basi(menit=5)` di blok startup yang sama. Tiga baris.
PR lanjutan (mencatat `processed` ter-commit) **jangan** dijanjikan bersamaan.

**C30 · Restore mengosongkan basis data sementara aplikasi tetap melayani**
`routes/backup.py:496 delete_many({})` per koleksi, `:530-534` mengosongkan koleksi di luar arsip,
`import_gridfs:263-264` menghapus seluruh `fs.files`/`fs.chunks`. `_ACTIVE_LOCK` (`:919`) hanya
mencegah job kedua, bukan lalu lintas pengguna. Dengan 2 worker, worker lain tetap melayani.
Tidak ada mode pemeliharaan di `server.py`.
*Dampak:* pengguna melihat daftar kosong lalu terisi lagi, foto 404, dan simpanan mereka menulis
ke basis data yang sedang setengah terhapus. Antrean optimistis akan mengirim ulang saat pulih
dan menempelkan tulisan pasca-restore ke atas data point-in-time yang baru dipulihkan.
*Usul (S) — dengan satu koreksi penting:* dokumen `{"type": "maintenance"}` + middleware yang
membalas 503. **`/api/health` TIDAK boleh dikecualikan** — justru endpoint itulah yang harus
melaporkan pemeliharaan, karena `frontend/src/lib/connectivity.js` hanya menyondir `/api/health`
dan `lib/muatAndal.js` memetakan 5xx ke `JENIS.SERVER` (bukan offline). Tanpa koreksi ini, PR-nya
menukar "tulisan nyasar" dengan "antrean simpan gagal beruntun".

#### Indeks, uji, dan dokumen operasional

**C31 · Seluruh pembuatan indeks dibungkus SATU `try/except`**
`backend/indexes.py:16 try:` … `:546-547 except Exception as e: logger.error(...)`. Tiga indeks
unik yang bisa gagal pada data produksi lama (`:119-122`, `:149-150`, `:213-214`) berada di
dalamnya tanpa penjaga sendiri. Bahwa ini bukan hipotesis terlihat dari kompensasi di sekitarnya
(`:105-110`, `:145-148`, `:209-212` men-drop indeks era lama).
Indeks setelah titik rapuh terakhir: `awk 'NR>214 && /create_index/' backend/indexes.py | wc -l`
→ **105** (bukan 117 seperti taksiran awal).
*Kapan menyala:* `create_index` idempoten, jadi risikonya tidak menyala tiap boot — ia menyala
pada boot **pertama** setelah indeks unik baru ditambahkan, atau bila data lama melanggar keunikan.
Itu justru yang membuatnya mendesak: C32 mengusulkan menambah indeks unik baru.
*Usul (S):* helper `_idx(coll, *a, **kw)` yang menangkap galat, mencatat nama koleksi+spesifikasi,
dan MELANJUTKAN; kumpulkan daftar gagal dan tampilkan di `/api/health/deep` sebagai
`checks["indexes"]`. Nol definisi indeks berubah.

**C32 · Dua koleksi tanpa indeks apa pun, dipakai sebagai penjaga keunikan**
`grep -rn "satker.create_index|komentar_aset.create_index" backend/` → kosong.
`routes/satker.py:225-228` `find_one` lalu `insert_one` di dalam loop agregasi;
`routes/peta_kolaborasi.py:1008-1012` sama, dengan komentar yang justru **mengandalkan**
idempotensi tanpa indeks yang menegakkannya.
*Dampak (satker):* masalahnya kebenaran, bukan kecepatan. Dua worker/dua admin bisa melahirkan
dua dokumen master untuk satu kode; setelah itu `find_one({"kode_satker": kode})` — dipakai di
`shared_utils.py:1032`, `auth_utils.py:324`, `users.py:166` — mengembalikan salah satunya secara
sembarang, membuat kop dokumen resmi tidak deterministik.
*Usul (S) — kirim SETELAH C31:* tambahkan indeks unik dengan **fallback non-unik di dalam
try/except** mengikuti pola `indexes.py:270-276`. Jalankan sekali agregasi hitung-duplikat dan
rapikan **sebelum** menyalakan unik; kalau tidak, PR ini sendiri yang memicu kegagalan C31.

**C33 · `pytest -m integration` tidak bisa dikoleksi sama sekali**
`pytest.ini:8` dan `backend/tests/conftest.py:31-33` sama-sama menjanjikan
"jalankan dengan `pytest -m integration`". Dijalankan: `668/2862 tests collected (2194 deselected),
6 errors` → `Interrupted: 6 errors during collection`. Sebabnya `REACT_APP_BACKEND_URL not set`;
`grep -rl REACT_APP_BACKEND_URL backend/tests/*.py | wc -l` → 59 dari 61 berkas, sementara
`conftest.py:16` menyediakan `TEST_BASE_URL` yang hanya dipakai 1 berkas.
*Dampak:* 668 uji (RBAC, OTP, ekspor, PDF eksekutif, penguncian sesi, WebSocket, GridFS) tidak
pernah jalan dan **tidak bisa** dijalankan manual oleh siapa pun yang mengikuti instruksinya.
Efek psikologisnya lebih berbahaya daripada efek teknisnya.
*Usul (S):* `os.environ.setdefault("REACT_APP_BACKEND_URL", TEST_BASE_URL)` di puncak conftest;
berkas yang memang usang **pindahkan** ke `backend/tests/arsip/` dengan README jujur — lebih baik
20 uji hidup daripada 61 berkas yang menipu.

**C34 · Dua daftar koleksi ber-`kode_satker` sudah menyimpang — GANTI KODE meninggalkan 5 koleksi yatim**
`routes/activities.py:404-415` `_KOLEKSI_KODE_SATKER` (21 nama) mengklaim di komentarnya
(`:400-403`) "ikut mesin backfill routes/satker.py", tetapi mesin itu (`satker.py:307-309` +
`:328-333`) memuat 22 nama. Selisihnya persis lima: `pengamanan_checklist`, `lpb`, `ruangan`,
`surat`, `mutasi_bmn` — dan `satker.py:324-327` sendiri menyebut kelimanya sebagai koleksi
berstempel. Migrasi hanya menyapu tuple `activities.py` (`:494-496`).
*Dampak:* saat kode satker diganti, LBP, Master Ruangan, register Persuratan, Jurnal Mutasi BMN,
dan checklist pengamanan satker itu HILANG dari layar, permanen, tanpa pesan galat.
*Peredam:* jalur GANTI KODE dipagari super-admin (`activities.py:440-451`), jadi frekuensinya rendah.
*Usul (S, dua PR):* (1) satukan sumbernya di `shared_utils.py` + uji registry yang menagih
`daftar migrasi ⊇ daftar backfill`; (2) baru perbaiki cakupannya. Jangan digabung.

**C35 · Pemeriksa magic-byte gambar hanya hidup di 1 dari 8 modul lampiran**
`grep -rn "^def _lampiran_ext" backend/routes/*.py` → 8, kedelapan badan fungsinya byte-identik.
Hanya `routes/pemanfaatan.py:361-362` memanggil `cek_magic_gambar`. Uji penjaganya
(`tests/unit/test_penjaga_senyap.py:154-164`) **mendaftar 5 berkas secara hardcode** sehingga buta
pada 7 sisanya.
*Dampak (integritas, bukan keamanan):* berkas apa pun bernama `bukti.jpg` diterima oleh 7 modul
siklus. Lampiran BA Pemusnahan / usulan Penghapusan / SK PSP — dokumen yang harus bertahan
diaudit — bisa berisi bita sampah sampai 10 MB, baru ketahuan saat auditor mengkliknya.
Aturan yang ditulis repo ini sendiri (`gerbang_media.py:29-31`) dilanggar di 7 dari 8 tempat.
*Usul (S):* `backend/lampiran_utils.py::validasi_lampiran(file_bytes, filename)` yang melakukan
ketiga cek; ganti 8 pemanggil. **Ganti daftar hardcode di uji menjadi PENEMUAN** — setiap berkas
yang mendefinisikan `_LAMPIRAN_MEDIA` wajib terbukti memanggil validator bersama, sehingga uji
tahan terhadap modul ke-9.

**C36 · Sheet 1 dan Sheet 2 berkas rekonsiliasi memakai ambang kapitalisasi berbeda**
Di satu fungsi yang sama: `routes/reports.py:3891-3892` meneruskan `ambang=amb`, sementara
`:3977 klasifikasi_komptabel(a.get("asset_code"), harga)` tanpa ambang → jatuh ke konstanta
(`pembukuan_utils.py:82-83`). Dua titik lain juga: `routes/pemeliharaan.py:476` dan
`pengadaan_utils.py:101`.
*Kualifikasi jujur:* kontradiksi baru muncul setelah fitur override ambang dipakai; tanpa override
kedua sheet sepakat. Karena itu kegawatan efektifnya **sedang**.
*Usul (XS + plumbing):* teruskan `ambang=amb` di `:3977`; alirkan ambang ke
`indikasi_kapitalisasi` dan `is_ekstrakomptabel`. Uji: override golongan 3 = Rp2 juta, aset
Rp1,5 juta, dua sheet harus sepakat.

**C37 · Dasar hukum dokumen tidak dibekukan**
`routes/bast.py:83-97` menyimpan dasar hukum sebagai konstanta modul, dengan komentar yang
membuktikan konstanta itu memang pernah disunting di tempat (PMK 246/2014 dicabut, digantikan
PMK 40/2024). Konstanta dipakai saat **render** (`:1107-1109`), bukan saat pembuatan. Record BAST
(`:539-587`) memuat snapshot aset, pihak, dan kebijakan `tampilkan_nilai` — tetapi bukan dasar hukum.
*Yang membuatnya jelas cacat, bukan selera:* komentar `bast.py:547-551` tepat di sebelah field
yang hilang itu SUDAH menyatakan prinsipnya — "BAST yang sudah ditandatangani harus tercetak ulang
persis seperti saat diterbitkan". Aturan repo sendiri yang belum dikenakan pada satu field.
*Usul (XS):* tambahkan `dasar_hukum` + `dasar_hukum_ringkas` ke record sebelum `insert_one`, lalu
baca `b.get("dasar_hukum_ringkas") or DASAR_HUKUM_RINGKAS`. Fallback → nol migrasi. Ulangi untuk
BA perbaikan dan LBP (yang terakhir satu langkah dengan C8).

**C38 · `docs/LOGGING.md` menyuruh membaca log lewat unit systemd yang tidak pernah ada**
`docs/LOGGING.md:13` menyatakan "journald/systemd yang menampung… Tidak ada file log aplikasi"
dan `:21-24` memberi resep `journalctl -u aman-backend`. Kenyataannya backend berjalan di bawah
supervisor dengan stdout dialihkan ke berkas (`scripts/vps-deploy.sh:202,213,215-218`).
`grep -rn "aman-backend"` di seluruh repo → hanya 4 baris, semuanya di `LOGGING.md`.
*Dampak:* saat insiden, perintah pertama yang diketik mengembalikan `-- No entries --`, dan
kesimpulan wajarnya adalah "aplikasi tidak menulis log" — persis kebalikan kenyataan. Efek kedua:
plafon `journalctl --vacuum-size=200M` (`OPTIMASI-VPS.md:121-123`) menjaga journald yang hampir
kosong, sementara berkas yang benar-benar tumbuh (2 worker × out+err × 10 MB × 5) di luar pengawasan.
*Usul (XS, dokumentasi murni):* ganti empat perintah ke bentuk `tail`/`jq` atas
`/var/log/supervisor/inventarisasi-backend.out.log`, koreksi baris 13, dan tambahkan satu kalimat
di `OPTIMASI-VPS.md` bahwa plafon journald tidak mencakup log aplikasi.

**C39 · Cron backup di panduan memakai nama basis data yang tidak konsisten**
`DEPLOYMENT_GUIDE_HOSTINGER.md:1173,1176,1185,1220` memakai `inventarisasi_bmn`, sedangkan
`scripts/vps-deploy.sh:72` dan `vps-fix.sh:131` menulis `DB_NAME="${DB_NAME:-inventaris_bmn}"`
dan panduan yang sama di `:533` mencontohkan `inventaris_bmn`. `mongodump` atas basis data yang
tidak ada **berhasil dengan exit code 0** dan menghasilkan direktori kosong; karena dirangkai
`&& find … -mtime +7 -delete`, hasilnya cron yang tiap malam membuat cadangan kosong lalu
memangkasnya dengan rapi.
*Kegawatan diturunkan ke SEDANG:* di repo hanya ada **dua** nama (bukan tiga — `README.md:472`
memakai nama yang sama dengan `:1185`), dan karena `${DB_NAME:-...}`, operator yang mengikuti
README justru mendapat cron yang benar. Nama DB produksi tidak dapat diketahui dari repo.
*Usul (XS + satu verifikasi):* jalankan di VPS `crontab -l` dan
`grep DB_NAME /var/www/inventarisasi/backend/.env`. Lalu ubah panduan agar **membaca** nama dari
`.env` alih-alih menuliskannya, pakai `--archive` + penjaga ukuran, dan selaraskan `README.md:472`.

---

### 3B. RISIKO SKALA — benar sekarang, patah pada ukuran tertentu

> **Peringatan tentang angka.** Dataset sekarang menurut `docs/OPTIMASI-VPS.md` masih
> "belasan ribu dokumen" dengan disk terpakai ±15,7 GB dari 100 GB. Sebagian besar ambang di
> bawah ini adalah **perkiraan mekanisme, bukan pengukuran**. Yang dapat dipercaya adalah arah
> dan sebab-akibatnya, bukan angka persisnya. Di mana ambang diberi angka, dasarnya disebutkan.

| # | Temuan | Jangkar | Ambang (dasar) | Usul | Ukuran |
|---|---|---|---|---|---|
| S1 | **Plafon diam `to_list(N)`** pada 35 rute laporan menarik seluruh aset ke memori. `to_list(500000)` → 12 titik, `to_list(100000)` → 23 titik; `allowDiskUse` → 0 | `reports.py:3068`, `lbp.py:196-203`, `mutasi_bmn.py:333` | **500.000 aset** = plafon keras: di atasnya laporan penyusutan/LBP memberi angka SALAH tanpa peringatan. Ambang memori tidak terukur; arahnya linear terhadap jumlah aset | **Prioritaskan penjaga plafon**, bukan optimasi: `count_documents` dulu, di atas ambang alihkan ke Pusat Unduhan (infrastrukturnya SUDAH ada di `jobs.py` + `routes/unduhan.py`). Sekalian bungkus `wb.save`/`prs.save` di `pegawai.py:635`, `kodefikasi.py:170`, `documents.py:511` dengan `to_thread`, dan pindahkan filter `dihapus` dari `lbp.py:204` ke dalam kueri | S per rute |
| S2 | **Backup & restore memuat setiap koleksi utuh ke RAM** — list dict Python + string JSON penuh, berbarengan | `routes/backup.py:343-347`, `:496-512` | Mekanismenya pasti; ambangnya tidak terukur. VPS 8 GB **tanpa swap** (`docs/OPTIMASI-VPS.md:17,31`) | **Langkah nol hari ini: pasang swap 4 GB** (blok B, `OPTIMASI-VPS.md:98-103`) — nol kode. Lalu tulis JSON bertahap lewat `zf.open(...,'w')` **pada kedua jalur** (`run_backup_task` dan safety-snapshot). Format arsip tidak berubah → arsip lama tetap bisa dipulihkan | M |
| S3 | **`audit_logs` tumbuh tanpa batas; `timestamp` STRING sehingga TTL mustahil** | `shared_utils.py:706`, `indexes.py:77-82`, `audit.py:105-107` | 131 titik `log_audit`; satu inventarisasi 50.000 aset × 3 suntingan = 150.000 entri. Melambat saat `count_documents` + `skip` atas `$or` bekerja pada jutaan baris — angka pastinya tidak diukur | 4 PR bertahap, **jangan menghapus jejak** (keputusan sadar di CHANGELOG): (1) tulis field `ts` BSON berdampingan; (2) backfill + indeks `(activity_id, ts)`; (3) **naikkan prioritas keyset** `{"ts": {"$lt": kursor}}` menggantikan `skip` — polanya sudah dikuasai (`assets.py:549-565`); (4) arsip ke `audit_logs_arsip`. Peredam yang sudah ada: `page_size` dijepit 200 (`audit.py:102-103`) | M |
| S4 | **Arsip backup di disk yang sama dengan GridFS, retensi 7** | `backup.py:39-40`, `:884` | Aturannya: kebutuhan disk ≈ (1 + retensi) × total byte GridFS. **Angka aset spesifik sengaja tidak diberikan** — tiga asumsi (foto/aset, ukuran pasca-WebP, sisa disk) semuanya tak terukur. Belum menggigit: `aktif` bawaan `False` | Ukur dulu: `du -sh backend/backup_arsip && df -h /`. Turunkan retensi bawaan 7→3. **Pindahkan arsip ke luar VPS** (rclone/rsync + cron) sebelum menyalakan backup otomatis — ini juga memperbaiki fakta bahwa cadangan saat ini tidak bertahan dari kegagalan disk VPS itu sendiri | S (skrip) |
| S5 | **Daftar Kegiatan menjumlahkan seluruh aset satker tiap muat, tanpa cache; potong senyap di 100** | `routes/activities.py:352-367`, `:330`, `:340` | Biaya linear terhadap jumlah aset, berulang tiap muat halaman/refetch WS. Pemotongan senyap menggigit pada **>100 kegiatan per satker** — itu angka pasti | **PR kecil dulu: penanda `terpotong: true`** (kerusakan kebenaran kecil, perbaikan sepele). Lalu cache 60 detik — **bukan satu baris**: namespace `"kegiatan"` harus didaftarkan di `_CACHE_LOCAL` (`shared_utils.py:306-313`), `_CACHE_TTL` (`:315-316`), **dan** `invalidate_asset_cache()` (`:339-343`), atau `cache_get` melempar KeyError | S |
| S6 | **Tiga pemindaian penuh tanpa indeks memblokir startup, di balik gerbang deploy sempit** | `server.py:111,118-121,132-135,143-144`; `pengesahan.py:131-137` | Gerbang efektif ≈ **30 detik**, bukan 75 (`deploy_vps.sh:34` sendiri menulis "sampai ~30 dtk"): port belum listen selama startup, jadi curl gagal instan dan hanya `sleep 2` menghitung. Ambang jumlah dokumen **belum diukur** | (1) Jadikan tiga backfill sekali-seumur-hidup dengan penanda di koleksi `app_runtime` — koleksi itu ada di SKIP_COLLECTIONS backup (`backup_utils.py:22-25`) sehingga pasca-restore backfill otomatis jalan lagi; (2) naikkan iterasi gerbang dari 15 ke 45 — murah dan menghilangkan kelas "deploy merah padahal sistem sehat" | S |
| S7 | **Render halaman PDF & perakitan PDF ber-TTD di event loop** | `routes/ttd.py:935,996,1009,1044`; `grep -c to_thread` → 1 pada berkas 95 KB | Biaya per render lebih terbatas dari kesan pertama: skala dijepit ke ~1100×2400 px dan `min(2.0, max(0.3, skala))` (`:952-954`). Gejalanya muncul sebagai kontensi saat beberapa penanda tangan bersamaan; angka "3–6 pengguna" adalah tebakan | Pecah `_render_halaman_png` menjadi fungsi murni yang mengembalikan `(bytes, total)` lalu `await asyncio.to_thread(...)` di dua pemanggil. **Jangan** turunkan `@limiter.limit` dari 60/menit tanpa keputusan pemilik — itu mengubah pengalaman menggeser posisi tanda tangan | S |
| S8 | **Unduh artifact job memuat seluruh berkas ke RAM** | `jobs.py:84-95`, `shared_utils.py:164-171`, `routes/jobs.py:78-80` | Kualitatif. Catatan penting: lonjakan sebesar artifact **sudah ada di jalur produksinya** (`exports.py:1428` → `jobs.py:66` menerima `bytes` penuh), jadi perbaikan ini mengurangi jumlah salinan serentak, bukan menghapus puncaknya | Salin pola `routes/unduhan.py:354-371` (`readchunk()` per potongan). Biarkan `ambil_artifact()` tetap ada supaya PR benar-benar aditif | S |
| S9 | **`asset_created` rekan memicu refetch daftar PENUH per event** | `hooks/useWebSocket.js:104` (`oac?.()` tanpa argumen) vs `:113`, `:118` yang sudah benar | Dengan N surveyor, tiap klien menerima N−1 event; refetch dijepit 1 per 2 detik (debounce **trailing murni**, tanpa lantai leading). Pada N besar timer terus di-reset → daftar terasa basi. Asumsi: tiap surveyor menyimpan sekali per 30 detik | Perlakukan sama dengan saudaranya: `oac?.("asset_created", msg.asset)` + cabang prepend satu baris meniru `DashboardPage.jsx:341-349`. Toast jadi agregat ber-id tetap. **Peredam yang sudah ada:** refetch ditunda selama form edit terbuka (`:358-362`) | S |
| S10 | **Snapshot luring dibaca utuh ke memori dan di-sort ulang tiap interaksi — saat OFFLINE** | `lib/offlineSnapshot.js:279-291`; 6 titik `serveFromSnapshot` | Keenam titik semuanya jalur luring/gagal-jaringan; saat daring, daftar dilayani server. Ambang "5.000–10.000 aset" adalah orde besaran, bukan angka | Cache modul-level berkunci `(activityId, meta.lastSync)`, ~30 baris, tanpa mengubah tanda tangan fungsi. Tiga titik pembatalan sudah ada. *(Catatan kecil: `SNAPSHOT_FIELDS` masih mencantumkan `gallery_thumbnail` yang server tak lagi kirim — baris mati, bersihkan sekalian)* | S |
| S11 | **`mobileAssets` tumbuh tanpa batas pada gulir tak-hingga** | `DashboardPage.jsx:238` + 24 titik `setMobileAssets`, tak satu pun memangkas | DOM aman (virtualisasi benar); yang tidak dibatasi adalah heap JS. Ambang tidak terukur — **jangan** pakai angka | **Usulnya lebih besar dari yang terlihat**: "jendela geser" menyentuh pembukuan `mobileFirstPage`/`mobileCurrentPage` di lima titik DAN diam-diam mengubah `siblings` PhotoLightbox (`:2042`), sehingga navigasi kiri-kanan di lightbox berhenti lebih cepat. Butuh perancangan tersendiri, bukan slot "PR kecil" | L |
| S12 | **`backfill_saldo_awal` memuat seluruh `asset_id` jurnal ke satu set Python** | `routes/mutasi_bmn.py:97-100`, insert satu-per-satu di `:113` | Pada 1 juta baris ≈ 110 MB di mesin 8 GB — **jauh dari OOM**. Masalah sebenarnya **DURASI**: satu round-trip per aset; pada 50 ribu aset bisa belasan menit dengan HTTP menggantung tanpa progres | Ganti set global dengan `count_documents({"asset_id": ...}, limit=1)` (dilayani indeks `:293`) dan `insert_many` per 500. **Jangan** naikkan gerbang ke super-admin — loop TULIS-nya sudah ter-scope penuh (`:105-106`); yang bocor hanya angka `"sudah_berjurnal"` pada respons, cukup jangan dikembalikan | S |
| S13 | **Badai reconnect WebSocket saat deploy** | `useWebSocket.js:166-168` (3000 ms tetap, tanpa jitter); `websocket.py:245-263` (2× `find_one` tanpa cache, berbeda dari `:214-215` yang punya TTLCache) | **Angka "N≈50 terasa, N≈200 gagal" GUGUR** — tidak berdasar. Yang pasti: semua klien memanggil `tryConnect` pada detik ke-3 yang sama, ke worker yang cache-nya masih dingin | Dua PR kecil: `TTLCache(maxsize=4000, ttl=30)` untuk `_ws_satker_allowed` (~6 baris, pola persis ada di berkas yang sama), dan jitter `2000 + Math.random()*4000` (1 baris). **PR ketiga (jitter pada `onAssetChange`) dibuang** — refetch reconnect sudah melewati debounce 2 detik | XS ×2 |

---

### 3C. UTANG — tidak salah, tetapi memperlambat perubahan berikutnya

#### Prioritas tinggi (ranjau tersembunyi)

**U1 · Enam endpoint hanya dijaga oleh urutan baris `include_router`, tanpa satu pun uji**
*Dibuktikan empiris,* bukan dari membaca komentar. Mengimpor `server.app` dan mencetak indeks rute:

```
31 /api/assets/locks [GET]          62 /api/assets/{asset_id} [GET]
32 /api/assets/batch-update [PUT]   71 /api/assets/{asset_id} [PUT]
33 /api/assets/groups [GET]
34 /api/assets/all-ids [GET]
53 /api/assets/kartu-inventarisasi [GET]
54 /api/assets/garansi-sebelumnya [GET]
```

Keenam rute literal mendahului catch-all dengan metode yang sama, dan satu-satunya yang menjaga
urutan itu adalah tiga komentar manual di `server.py:367,368,371`. Starlette memilih kecocokan
pertama dari daftar datar, jadi **mengurutkan blok `include_router` menurut abjad — perubahan
kosmetik yang lolos review, `compileall`, dan `pytest` — akan menguburkan keenamnya** dengan 404
bermakna menyesatkan.
*Usul (S, nol perubahan produksi):* `backend/tests/unit/test_urutan_rute.py` yang mengimpor
`server.app` (berhasil tanpa MongoDB — 595 rute termuat, env dummy sudah di `tests/unit/conftest.py:16-18`),
mengiterasi `app.routes`, dan meng-assert indeks rute literal < indeks `{asset_id}` untuk metode
yang sama. ±40 baris. **Ini yang paling murah dari seluruh daftar — kirim lebih dulu.**

**U2 · Menambah satu modul siklus butuh menyunting ~14 daftar manual, tak satu pun dijaga uji**
Titik pendaftaran yang terverifikasi: modul util + route baru; `server.py:343-348` impor +
`:365-372` `include_router` (urutannya bermakna, lihat U1); `indexes.py`; `satker.py:307-309`
`RELASI`; `satker.py:328-333` `SISA`; `activities.py:404-415`; `timeline_utils.py:25-38`;
`routes/timeline.py` (14 blok kueri manual); `shared_utils.py:1216`; `reports.py:3618`;
`wasdal.py:105-108`; `ttd.py:635-638`; `App.js` (4 suntingan terpisah);
`lib/bmnModules.js:160+`; `ModuleHomePage.jsx:49` + `:74` (dua peta terpisah);
`AssetTimelineDialog.jsx:34`.
*Dampak:* melewatkan satu tidak menghasilkan galat — semua gagal DIAM. C34 adalah kejadian nyata
dari pola ini. Inilah alasan sesungguhnya mengapa modul ke-13 akan lebih mahal daripada ke-12.
*Usul (3 PR, WAJIB bertahap):* (1) `backend/siklus_registry.py` **murni deskriptif** untuk 12
modul yang sudah ada, belum dipakai siapa pun — benar-benar aman; (2) turunkan
`_KOLEKSI_KODE_SATKER`, `RELASI`/`SISA`, peta label timeline dari registry; (3) uji registry yang
menagih konsistensi backend↔frontend (scan teks, pola `test_penjaga_senyap.py`).
**Kalau (1)–(3) digabung, ini berubah menjadi penulisan ulang lintas-modul.**

**U3 · Cakupan uji lapisan handler HTTP: 29% vs 83% pada lapisan util**
Diukur ulang secara langsung (`pytest-cov` **tidak ada** di `requirements.txt`; dipasang di
lingkungan uji lalu dihapus jejaknya): `routes/*` → 22.550 pernyataan, 15.926 miss, **29%**;
`--omit='backend/routes/*,backend/tests/*'` → 11.043 pernyataan, 1.886 miss, **83%**; total 63%.
Terburuk: `documents.py` 5%, `lbp.py` 5%, `imports.py` 10%, `backup.py` 12%, `cards.py` 13%,
`reports.py` 14%, `auth.py` 22%, `users.py` 21%. **37 dari 62** modul route tidak dirujuk satu
pun uji unit.
*Usul (XS lalu S per modul):* (1) tambahkan `pytest-cov` ke `requirements.txt` + langkah
`--cov=backend --cov-fail-under=60` di CI (posisi sekarang 63%) — **tujuannya mencegah TURUN**,
bukan mengejar angka; (2) pakai pola yang sudah terbukti (`mongomock_motor` +
`monkeypatch.setattr(modul, "db", fake)`, sudah dipakai 23 kali) untuk route paling merusak dulu:
`imports.py` → `backup.py` (restore) → `auth.py`+`users.py` → `batch.py`. **Jangan kejar
`reports.py`** — 6.611 baris, hasilnya kecil per PR.

**U4 · `routes/reports.py` sudah menjadi pustaka PDF de-facto**
`grep -rn "from routes.reports import" backend --include=*.py | grep -v server.py | grep -v tests`
→ **28** impor dari **11** berkas rute, semuanya di dalam badan fungsi untuk menghindari siklus.
Blok `reports.py:186-329` terbukti murni ReportLab tanpa sentuhan `db` (hit `db` pertama baru di
`:337`).
*Dua koreksi yang mengubah pelaksanaannya:*
1. **`from pdf_kit import *` TIDAK akan bekerja** — seluruh simbol yang dipindahkan berawalan
   garis bawah (`_PALETTE`, `_get_report_styles`, `_std_doc`, …), dan `import *` tidak mengekspor
   nama berawalan `_`. Shim itu akan mematikan 28 titik impor sekaligus. **Pakai impor eksplisit**
   `from pdf_kit import _PALETTE, _get_report_styles, … # noqa: F401`.
2. **Bukan `compileall` yang akan menangkap salah ketik simbol** — `compileall` tidak pernah
   menyelesaikan nama impor. Yang menangkapnya adalah `pytest`, karena
   `tests/unit/test_pure_logic.py:299` menjalankan `import server`. Manfaatnya tetap nyata, tapi
   sebutkan mekanismenya dengan benar.
*Usul (M, 2 PR):* PR-1 pindahkan blok `186-329` ke `backend/pdf_kit.py` + impor eksplisit di
`reports.py` + `tests/unit/test_pdf_kit.py`. PR-2 pindahkan `_kop_surat_flowables`,
`_signature_block`, `_page_footer_factory`. Konversi 11 berkas ke impor level-modul boleh
satu berkas per PR berikutnya.

**U5 · Handler raksasa: 61,2% baris `routes/` ada di badan handler**
Pengukurannya sah: 29.808 dari 48.704 baris ada di badan handler; 9 handler ≥300 baris
(`bast.py:933-1594 bast_pdf` 662, `lbp.py:172-818` 647, `documents.py:526-1060` 535,
`assets.py:2090-2596 patch_asset` 507, …).
*Premis "tak teruji sama sekali" GUGUR* — lihat Bagian 4. Yang tersisa: handler raksasa
memperlambat perubahan (mengubah aturan kapitalisasi berarti membaca 662 baris untuk menemukan
tiga baris relevan).
*Usul yang BENAR (bukan yang semula diusulkan):* jangan pecah dulu. **Perluas pola yang sudah
terbukti di repo** — tambahkan `tests/unit/test_bast_pdf.py` bergaya `test_belah_endpoint.py`
yang memanggil handler yang sudah di-unwrap di atas `AsyncMongoMockClient`. Itu menguji handler
**apa adanya** tanpa membedah 662 baris — jauh lebih murah dan aman untuk sistem produksi.
Ekstraksi fungsi murni menyusul **belakangan**, dengan uji itu sebagai jaring. Pemeriksa CI
"gagal bila handler baru >250 baris" tetap layak dan berdiri sendiri.

#### Prioritas menengah

| # | Temuan | Jangkar | Usul | Ukuran |
|---|---|---|---|---|
| U6 | **`shared_utils.py` tempat sampah bersama** — 1.309 baris, fan-in **62**, ≥9 concern tak berhubungan. Termasuk siklus logis `shared_utils → gerbang_media → routes.media → shared_utils` (`:107,154` ⇄ `gerbang_media.py:194`) | `shared_utils.py:65-1240` | **Kirim HANYA PR-1:** ekstrak `satker_scope.py` ← `:893-1021`. Simbol yang dipindah TIDAK berawalan garis bawah, jadi `from satker_scope import *` di sini **bekerja** (beda dari U4). Ini pemisahan berdasar tingkat risiko, bukan estetika, dan `tests/unit/test_m_scope.py` sudah ada. PR untuk `email_otp.py`/`idempotensi.py` adalah kosmetik murni — boleh tidak pernah dikerjakan | S |
| U7 | **`assets` tidak menyimpan `kode_satker`** — isolasi lewat `$in` daftar kegiatan; `grep -c '"kode_satker"' routes/assets.py` → 0; nol dari 39 indeks aset memuatnya | `shared_utils.py:898-923`, `indexes.py` | **Framing performa DIBUANG** — `scope_query_aset` punya jalan keluar dini (`:915-917 if not kode or "activity_id" in q: return q`) dan daftar aset utama selalu mengisi `activity_id`, jadi jalur panas tidak pernah membayar biaya `$in`. Yang tersisa: isolasi TIDAK BISA ditegakkan di lapisan indeks, tiap fitur baru harus ingat memanggil helper. **Kirim HANYA cache `id_kegiatan_satker` 30–60 detik**. Migrasi model data (tulis field → backfill → tukar scope) adalah perubahan pada penjaga KEAMANAN di produksi multi-satker — risikonya melebihi manfaat yang terbukti | XS (cache) |
| U8 | **Isolasi ditegakkan per-route dengan tangan, semantiknya FAIL-OPEN** untuk dokumen tanpa stempel (`shared_utils.py:970-979`) | 494 titik panggil manual di 584 endpoint | Jangan ganti mekanismenya — ia bekerja. **Tambahkan jaring**: uji meta yang mem-parse AST `routes/*.py`, mengumpulkan `db.<koleksi>.insert_one`, dan menagih stempel untuk koleksi yang dikenal, dengan **daftar pengecualian eksplisit** (daftar itu sendiri menjadi dokumentasi yang bisa ditinjau) | S |
| U9 | **`mutasi_bmn` disebut jurnal induk tetapi best-effort; DELETE aset tidak menjurnal keluar** | `shared_utils.py:1107-1153`; `assets.py:2598-2660` | **Kerjakan usul (2) DULU** — tulis kegagalan ke koleksi `mutasi_bmn_gagal` dan tampilkan hitungannya. Tanpa risiko, dan memberi data untuk memutuskan usul (1). **Usul (1) BERBAHAYA seperti tertulis**: menambah 301 di `delete_asset` akan menjurnal kurang DUA KALI untuk aset yang keluar lewat SK (`penghapusan.py:249-266`) — repo sudah pernah digigit kelas ini dan menuliskannya di `penghapusan.py:243-251`. Kode transaksi hard-delete harus DIBEDAKAN | S (usul 2) |
| U10 | **CaLBMN menyaring jurnal dengan `$in` seluruh id aset, dan `to_list(100000)` memotong senyap** | `routes/lbp.py:285-289` | **JANGAN salin mekanis dari `mutasi_bmn.py:70`.** `assets` di `lbp.py:194-201` sudah disaring `filter_aset_perhitungan`, jadi mengganti ke scope per-satker akan MENARIK MASUK jurnal aset yang sengaja dikeluarkan dari basis perhitungan — menukar satu ketidakcocokan dengan yang baru. Butuh keputusan sadar ("apa definisi Rincian Mutasi?"). **Yang layak dikirim sekarang: penjaga pemotongan senyap pada `to_list(100000)`** — lebih tajam dan lebih murah | S |
| U11 | **Empat tulisan aset menyentuh field dalam proyeksi luring tanpa menyegarkan `updated_at`** | `siman.py:539-544`; `ttd.py:1492-1494`, `:1762-1764`; `bast.py:764-766` | Badge "TTD dibatalkan" dan status SIMAN berubah di server tetapi tak pernah ikut delta snapshot. Tambahkan `"updated_at"` pada `$set` — dan **JANGAN** tambahkan `$inc: {"version": 1}` (alasan `pengadaan_utils.py:208-210` tetap berlaku: OCC 409 palsu). Uji anti-regresi menegaskan pemisahan itu | XS |
| U12 | **Kerangka cek integritas hanya memeriksa drift identitas, nol invarian angka** | `integritas_utils.py:1-143` | PR **read-only** yang menambah tiga fungsi murni + tiga "bagian" pada dasbor integritas yang sudah ada: jurnal tanpa pasangan, jurnal tanpa stempel satker, `persediaan.stok` vs Σ sisa batches. Nol perubahan jalur tulis, dan hasilnya langsung memberi tahu seberapa besar utang data yang sudah terakumulasi **sebelum** memutuskan urutan perbaikan berikutnya | S |
| U13 | **Duplikasi salin-tempel** — ~920 baris plumbing lampiran ×8, 28 endpoint CSV, 9 mesin status ditulis tangan | 8 salinan `_lampiran_ext`; `grep -rho "csv_module.writer\|csv.writer" routes/*.py \| wc -l` → 28; `grep -rn "def validate_transisi" backend/*.py` → 9 | **Inilah MEKANISME C35**: perbaikan pada satu salinan tidak pernah sampai ke tujuh lainnya. Faktorisasinya sudah terbukti di `pemanfaatan.py:337-429`. Tiga PR terpisah dan tidak berurutan: `lampiran_utils.py`, `csv_utils.py::respons_csv`, `mesin_status.py`. Konversi 2 modul dulu, ukur, lanjutkan | M ×3 |
| U14 | **`App.js` saklar halaman manual** — 27 `useState` boolean + 26 blok `if` sebelas-baris identik, 896 baris; `react-router-dom` diimpor tapi hanya melayani `/403` | `App.js:13,455-799,858-879` | Biaya perilakunya nyata: halaman modul tak bisa di-bookmark, Back keluar dari aplikasi, refresh melempar ke dasbor — pada PWA lapangan refresh tak sengaja adalah kejadian biasa. **Bertahap:** PR-1 ekstrak `<HalamanModul>` (26 blok jadi 3 baris, nol risiko); PR-2 satu peta data + satu state string (menghapus kelas bug "dua `show*` true"); PR-3 opsional `<Route path="/modul/:id">` | S ×2 |
| U15 | **`memo()` pada 26 komponen dikalahkan prop arrow inline** | `DashboardPage.jsx:1834-1843`, `:968` (`refreshData` bukan `useCallback`) | Tiap ketukan huruf di kotak cari dan tiap `touchmove` me-render ulang `DashboardToolbar` (23,4 KB, beberapa dropdown Radix). Ongkos perbaikan nyaris nol: pekerjaan memoisasi 90% SUDAH dilakukan, hanya empat prop yang membocorkannya. `refreshData` sudah membaca semua parameternya dari `fetchParamsRef.current` sehingga `useCallback([])` sekaligus menghapus tiga peringatan exhaustive-deps | S |
| U16 | **`React.lazy(PhotoLightbox)` tidak menghasilkan potongan** | `DashboardPage.jsx:45` lazy, tapi **DUA** impor statis: `AssetGalleryView.jsx:6` **dan `AssetMapFullView.jsx:33`** | **Mengubah satu saja TIDAK cukup** — webpack tetap harus menyediakannya untuk pengimpor kedua. Ubah keduanya bersamaan. Sebutkan hasilnya jujur: `DashboardPage` sendiri sudah lazy, jadi potongan 7152 (517 KB / 127 KB gzip) adalah potongan **halaman dasbor**, bukan potongan login — perolehannya dasbor lebih cepat tampil. Jaringnya cukup satu regex yang melarang impor statis `./PhotoLightbox`, bukan pembaca sourcemap (rapuh terhadap versi react-scripts) | S |
| U17 | **Frontend: 724 uji, hanya SATU berkas benar-benar merender komponen** | `grep -rl "@testing-library/react" frontend/src --include="*.test.js*"` → 1 (`lib/__tests__/menuKepalaRender.test.jsx`); 12 berkas / 142 kasus memakai `readFileSync` + regex | Uji berbasis-teks menangkap "pemanggil hilang" dengan baik dan **jangan dibuang** — ia menjaga hal yang berbeda; cukup berhenti menambahnya untuk hal yang bisa dirender. Ekstrak shim jsdom dari berkas itu ke `setupTests.js`, lalu satu PR per komponen: `AssetForm` ("render mode tambah + edit tanpa crash"), `LokasiTemuanDialog`, `BatasGalat` | S ×3 |
| U18 | **`reports.py` 6.611 baris, 160 fungsi, cakupan 14%, NOL uji menyentuh WeasyPrint** | 4 titik render (`:5467,5522,5820,6105`); `grep -rln weasyprint backend/tests/unit/*.py` → kosong. Ironisnya `ci.yml:46-47` **sudah** memasang `libpango` | **JANGAN pecah `reports.py` sekarang** — risiko besar, hasil kosmetik. Yang bernilai dan muat satu PR: **uji asap render** — 4 uji dengan `mongomock_motor`, seed 3 aset, assert `pdf_bytes[:5] == b"%PDF-"` dan `len > 1000`, plus satu uji data KOSONG (jalur yang paling sering meledak). ±150 baris, langsung memakai libpango yang sudah ada | S |
| U19 | **Pola registry anti-drift baru dipakai 2× dan berhenti di batas backend** | `asset_fields.py:14-17` menetapkan langkah ke-4 (frontend `TEXT_FIELDS`, `SNAPSHOT_FIELDS`) sebagai kewajiban, tapi nol penjaga lintas-bahasa. Diperiksa manual: **selaras hari ini**, nol drift | Risiko laten, bukan cacat aktif. Bentuk kegagalannya: field baru masuk registry + backend, lulus semua uji, tapi tidak masuk `SNAPSHOT_FIELDS` → nilainya HILANG saat pengguna mengedit luring lalu antreannya tersinkron. `backend/tests/unit/test_registry_frontend.py` yang membaca kedua berkas JS sebagai teks dan menagih `set(SCALAR_FIELD_NAMES) <= keduanya`. ~30 baris | S |
| U20 | **Referensi aturan tidak punya DIMENSI WAKTU** — polanya sudah ada di modul pejabat tapi tak dipakai untuk parameter hukum | `grep -rn "berlaku_sejak\|berlaku_mulai\|..." backend/` → 6 baris, **semuanya** di `pejabat_utils.py`/`routes/pejabat.py` | Ini akar C8: tak ada cara menjawab "berapa masa manfaat kelompok 30801 pada 30 Juni 2025?". Riwayat menunjukkan **tiga revisi Tabel Masa Manfaat dalam 6 tahun** (295/2019, 266/2023, 339/2024). **Bertahap:** PR-1 tambah field OPSIONAL `berlaku_mulai`/`berlaku_selesai` + pindahkan `_berlaku_pada` (`pejabat_utils.py:247-259`) ke util murni; PR-2 `_peta_masa_manfaat(per_iso)` + lima titik cetak meneruskan tanggal periode. Tanpa data terisi, perilaku identik → nol risiko rilis | M |

#### Prioritas rendah

| # | Temuan | Jangkar | Catatan |
|---|---|---|---|
| U21 | Blok nginx `/api/ws` tanpa `proxy_read_timeout` (default 60 dtk), bertentangan dengan panduan sendiri | `scripts/vps-deploy.sh:155-163` vs `DEPLOYMENT_GUIDE_HOSTINGER.md:1334-1335` | Tidak salah hari ini — heartbeat 25 dtk (`websocket.py:302-313`) menjaganya. Pentingnya: ini "garis patah" yang mengubah kelambatan >60 detik menjadi pemutusan massal. Satu baris; bukan pengganti perbaikan offload |
| U22 | API merangkap penjadwal: 5 loop latar di worker yang sama; 4 `asyncio.Task` tidak pernah di-`cancel()` | `server.py:110-207` | **Yang layak dikirim sekarang hanya `cancel()` sebelum `client.close()`** (XS, jelas benar). Flag `AMAN_ROLE` **jangan** diprioritaskan — klaim dampaknya spekulatif, dan `OPTIMASI-VPS.md §1-2` justru memerintahkan MENGUKUR (pidstat/top -H/mongotop) sebelum menyimpulkan |
| U23 | 39 indeks pada `assets` (plafon MongoDB 64); `indexes.py:49` dan `:53` terbukti redundan sebagai prefix | `grep -c "db.assets.create_index" backend/indexes.py` → 39 | Sebelum menghapus, buktikan dengan `explain()` bahwa rencana tidak berubah — perluas `tests/test_spasial_indeks.py` (yang sudah membaca `winningPlan`) ke kueri `assets`. Jadikan konvensi: filter baru harus diperiksa dulu apakah bisa dilayani indeks yang ada sebagai prefix |
| U24 | Buku Barang menyaring `kode_satker` tanpa indeks pendukung | `mutasi_bmn.py:70-75`; `indexes.py:292-293` | Tambahkan `[("kode_satker",1),("tanggal_buku",-1),("created_at",-1)]`. **Jangan janjikan sort gratis** — predikatnya `$in` tiga nilai, jadi tahap SORT kemungkinan tetap muncul. Minta `explain()` sebelum/sesudah dan simpan hasilnya di PR |
| U25 | Loop pemeliharaan berjalan di SEMUA worker tanpa lease, beda dari backup & konverter WebP | `jobs.py:196-201`; bandingkan `backup.py:957`, `webp_converter.py:483-498` | Tidak salah (sapuannya idempoten), tapi `selaraskan_inkremental` punya kursor bersama. Jadikan `_pegang_lease` generik dan bungkus putarannya. Tambahkan satu kalimat aturan di komentar modul supaya sapuan berikutnya tidak mengulang kebingungan |
| U26 | Plafon unggah tidak konsisten di 2 endpoint | `categories.py:135`, `pdf_compress.py:237` | **Bukan vektor OOM** (lihat Bagian 4). Nilainya: pesan 400 yang menyebut batas alih-alih 413 nginx yang membingungkan, dan konsistensi dengan `spasial.py:1069 _baca_terbatas`, `kodefikasi.py` 10 MB, `ttd.py:751` 20 MB |
| U27 | 70 endpoint menerima JWT lewat query string; token media 30 hari | `auth_utils.py:87,480-506` | Tidak salah hari ini — token tetap tervalidasi dan gugur saat reset password. Yang menumpuk: radius ledakan. Ikuti preseden `docfile` (`auth_utils.py:101-122`): scope `media_ro` 24 jam, persempit per kelompok rute mulai dari yang paling sensitif. **Jangan sekaligus** |
| U28 | Tail cursor `event_bus` dibuat ulang tiap ~2 detik | `event_bus.py:93-103` | Diregradasi dari RISIKO SKALA (lihat Bagian 4). Biayanya ≈1–1,5% satu core. **Usul alternatif `$_id` TIDAK bekerja** — kursor TAILABLE berjalan dalam urutan `$natural`, jadi mengganti penanda posisi tidak membuat mongod memakai indeks `_id`. Yang benar: pertahankan kursor dengan `cursor.try_next()`. Kerapian bernilai rendah |
| U29 | Indeks unik parsial untuk anti-jurnal-ganda | `shared_utils.py:1124-1148`; `indexes.py:292-293` | Diregradasi (lihat Bagian 4). Bila dikerjakan: `partialFilterExpression={"ref_id": {"$gt": ""}}` **bukan** `$type: "string"` (backfill menulis `ref_id: ""`). **Yang lebih bernilai:** beri `ref_id` pada dua penulis yang belum punya — `catat_jurnal_edit_harga` dan pasangan reklasifikasi |
| U30 | Tabel Masa Manfaat II (perbaikan, 90 kelompok) tidak punya jalur master data seperti Tabel I | `perbaikan_utils.py:27-125` vs `penilaian_utils.py:34-67` + `routes/penilaian.py:58-127` | Bukan cacat: hasilnya sudah di-snapshot ke aset saat BA (`pemeliharaan.py:592`). Tetapi saat KMK berikutnya mengubah baris Tabel II — dan riwayatnya menunjukkan itu rutin — satu-satunya jalan adalah deploy kode. Tiru pola Tabel I; endpoint tulis dijaga `_wajib_super_admin` **sejak awal** |
| U31 | Validasi keras berbasis angka regulasi MENOLAK fakta lapangan | `pemanfaatan_utils.py:14-21,47-51`; `mutasi_bmn_utils.py:15-32,46-48` | Bandingkan sikap yang dipilih untuk kodefikasi: NON-BLOCKING (`kodefikasi_utils.py:157`). Saat PMK berubah atau SAKTI menambah kode transaksi, petugas tidak bisa mencatat dokumen yang sudah ditandatangani sampai kode di-deploy ulang. Ubah jangka pemanfaatan menjadi `peringatan`; untuk kode transaksi, izinkan di luar daftar dengan `arah` wajib eksplisit |
| U32 | Kekhususan IKN belum masuk model: ADP tidak ada sebagai konsep, tidak ada jenjang UAPPB/UAPB | `grep -rniE "\badp\b" backend/` → 3 baris, semuanya teks dasar hukum; `penghapusan_utils.py:14-24` hanya `tidak_ditemukan`/`rusak_berat` | Belum menggigit selama OIKN berjalan sebagai satu satker; menggigit saat KPB kedua ditetapkan. **Dua PR kecil, bukan modul baru:** (1) jalur `"penetapan_adp"` + field boolean `adp` yang MENGELUARKAN aset dari `filter_aset_perhitungan` — cukup untuk membuat neraca benar; (2) dua field opsional pada master satker (`level_unit_akuntansi`, `induk_kode_satker`) agar datanya terekam sekarang sehingga PR agregasi kelak tidak perlu migrasi |
| U33 | Skrip penghancur data produksi berdampingan dengan skrip deploy harian | `scripts/vps-cleanup.sh:47-48` (`rm -rf /var/lib/mongodb`), pagar hanya ketik "YA" | Peluang paling nyata bukan sabotase, melainkan seseorang yang panik membuka `scripts/` dan memilih yang salah. Tambahkan pagar berbasis KEADAAN: tolak bila `/var/www/inventarisasi` atau `/var/lib/mongodb/WiredTiger` ada, dengan pengabaian eksplisit `AMAN_CLEANUP_PAKSA=1`. Pertimbangkan pindah ke `scripts/instalasi-baru/` |
| U34 | `PAGE_LIMIT = 1000` snapshot luring melawan tenggat 20 detik | `lib/offlineSnapshot.js:33,192-194`; `muatAndal.js:24,28` | **UKUR DULU, jangan ubah dari taksiran.** Seluruh argumennya bertumpu pada taksiran ~2–4 KB thumbnail/baris yang diturunkan dari taksiran lain. Jalankan `curl -s -o /dev/null -w '%{size_download}\n' "$URL/api/assets/offline-snapshot?activity_id=…&limit=1000"`. Bila ratusan KB, temuan gugur. Penulis SUDAH menimbang trade-off ini dan menuliskannya di `:185-193` — mengubahnya tanpa pengukuran adalah cara tercepat merusak kepercayaan pada komentar repo |
| U35 | Kunci idempotensi tidak pernah dilepas saat permintaan gagal | `shared_utils.py:487-489` | Preferensi, bukan cacat. `stale_seconds=30` sudah menebusnya, dan antrean luring mencetak kunci baru saat menggabungkan patch. Bila dirapikan: hapus hanya pada 4xx non-idempotensi, **jangan** pada 5xx (di sana menahan kunci adalah perilaku yang benar) |
| U36 | Foto BMN dikirim ke layanan kompresi pihak ketiga tanpa kebijakan tertulis | `routes/media.py:213-294`, `shared_utils.py:346-350` | Bukan cacat teknis — mitigasinya ada (`UPLOADCARE_STORE: "0"`, URL konstanta, fail-open). Ini keputusan TATA KELOLA (UU 27/2022 PDP) yang saat ini hanya terekam sebagai ada/tidaknya variabel lingkungan. Repo sudah peka soal PDP di tempat lain (`privasi_utils.py`, `/iot/perangkat/saya`), jadi ketimpangannya mencolok. Catat di `docs/` — jangan bangun saklar per-satker sebelum ada yang memintanya |

---

## 4. Yang diperiksa dan ternyata AMAN

Bagian ini sama pentingnya dengan daftar temuan. Delapan klaim di bawah **tidak bertahan** setelah
diperiksa ulang, dan tidak boleh dipakai sebagai dasar mengubah apa pun.

**A1 · `doc_ref` permintaan TTD dikira jalur baca-tulis silang ke satker lain — GUGUR total.**
Gerbangnya ada tepat di awal handler yang sama: `routes/ttd.py:635-655` memakai
`_KOLEKSI_BER_BACKLINK` dan `find_one(scope_query_field_satker(user, {"id": doc_ref}))` lalu
menolak 403 "rujukan tidak ditemukan pada satker Anda". Komentar `:611-634` bahkan menyebut
dirinya "GERBANG TUNGGAL". Karena `_ringkas_dokumen` baru dipanggil di `:722` — SETELAH gerbang —
tidak ada data satker lain yang bisa terbaca. Pintu belakang `POST /ttd/permintaan/unggah` juga
tertutup: ia menyetel `doc_type="dokumen_unggahan"` sedangkan kedua tulisan back-link bersyarat
`doc_type == "bast"`/`"lpb"`. **Jangan sampaikan kepada siapa pun bahwa data pribadi satker lain
bocor lewat TTD — itu tidak benar.**

**A2 · "29.808 baris handler tidak diuji sama sekali oleh CI" — GUGUR.**
`grep -rl mongomock backend/tests/unit/*.py | wc -l` → **23 berkas uji unit menjalankan handler
sungguhan in-process** lewat `mongomock_motor` (ada di `requirements.txt:64-65`), dengan pola
unwrap `while hasattr(fn, "__wrapped__")` untuk melepas bungkus limiter. Docstring
`tests/unit/test_belah_endpoint.py` bahkan menyebut masalah itu kata demi kata lalu memperbaikinya.
Yang benar: cakupan handler **tidak nol, tetapi tidak merata** — 23 dari 62 modul punya uji
endpoint, dan kesembilan handler raksasa kebetulan belum termasuk. Konsekuensinya rekomendasinya
berubah: **perluas pola yang ada**, jangan bedah handler lebih dulu.

**A3 · Penjaga anti-jurnal-ganda tanpa indeks unik dikira CACAT tinggi — diregradasi ke UTANG rendah.**
Semua transisi terminal yang menulis jurnal berdiri di belakang **CAS status**
(`penghapusan.py:230-236` `find_one_and_update({"id", "status"})` → 409; pola identik di
`pemindahtanganan.py:299-309`), dan jalur aset baru berdiri di belakang **kunci idempotensi**
(`assets.py:923-929`, `:1030`). Double-click, retry HTTP, dan replay antrean dari dua tab semuanya
ditolak SEBELUM jurnal disentuh. `catat_mutasi_bmn` adalah garis kedua, bukan satu-satunya.

**A4 · Dua endpoint unggah tanpa plafon dikira vektor OOM — GUGUR sebagai risiko skala.**
Nginx produksi menetapkan `client_max_body_size 50M` (`scripts/vps-deploy.sh:131`), dan Starlette
menampung `UploadFile` di `SpooledTemporaryFile` yang tumpah ke disk di atas 1 MB. Body 200–300 MB
yang menjadi dasar seluruh estimasi ditolak 413 sebelum menyentuh uvicorn. Skenario terburuk nyata
≈50 MB, bukan 400–500 MB. Tersisa sebagai U26 (konsistensi pesan galat).

**A5 · Tail cursor `event_bus` dikira beban skala permanen — GUGUR sebagai risiko skala.**
Memindai capped collection 10 MB yang panas di page cache adalah orde 10–30 ms, sekali per 2 detik
per worker ≈ 1–1,5% satu core. Premis "20 kegiatan aktif → ring penuh dalam 4 jam" tidak punya
dasar apa pun di repo. Dan usul penggantinya (`$_id`) **tidak bekerja** karena kursor TAILABLE
berjalan dalam urutan `$natural`. Tersisa sebagai U28 (kerapian).

**A6 · `masa_manfaat` dan `sbsk_standar` dikira tanpa pagar super-admin — SALAH; keduanya SUDAH dipagari.**
`routes/penilaian.py:122` memanggil `_wajib_super_admin(admin)` di `:124` (dan `:100`), dengan
helper di `:83-92` yang menuliskan alasannya kata demi kata (audit P4 #7).
`routes/perencanaan.py:389` memanggil `_wajib_super_admin_sbsk` di `:373` dan `:390`. Repo **sudah
menyelesaikan** kelas masalah ini untuk dua tabel; C16 hanya berlaku untuk sisanya. Pakai
`_wajib_super_admin` sebagai **pola yang sudah ada** (guard di dalam badan fungsi), bukan
mengganti `Depends`.

**A7 · Kunci PostHog `phc_…` dikira kredensial yang lolos pemeriksa rahasia — GUGUR.**
Itu **project API key publik** PostHog, dirancang untuk dikirim ke browser; ia ada di setiap
bundel PostHog di dunia. **Jangan tambahkan polanya ke `scripts/cek_rahasia.py`** — itu akan
menandai sesuatu yang bukan rahasia dan mengajari pemilik bahwa pemindai berbunyi untuk hal yang
tak perlu ditangani. Demikian pula, `cdn.tailwindcss.com` dan `assets.emergent.sh` dibungkus
`if (window.self !== window.top)` (`index.html:56-57`) — **hanya dimuat di dalam iframe**, bukan
ketergantungan pemuatan halaman produksi. Yang tanpa syarat hanya blok PostHog (C11).

**A8 · Beberapa angka dan atribusi yang salah, dikoreksi supaya laporan ini bisa dipercaya:**

| Klaim awal | Yang benar | Sumber koreksi |
|---|---|---|
| 117 indeks setelah titik rapuh | **105** | `awk 'NR>214 && /create_index/' backend/indexes.py \| wc -l` |
| 164 titik panggil `log_audit` | **131** di `routes/` (133 seluruh backend) | grep ulang |
| fan-in `shared_utils` = 61 | **62** | grep ulang |
| 36 dari 61 modul route tak diuji | **37 dari 62** | perintah yang sama, dijalankan ulang |
| Tiga nama DB berbeda di repo | **Dua** (`README.md:472` sama dengan `:1185`) | grep ulang |
| `compileall` menangkap salah ketik simbol impor | Tidak — `compileall` tidak menyelesaikan nama. Yang menangkap: `pytest` lewat `import server` | `tests/unit/test_pure_logic.py:299` |
| Gerbang deploy ≈75/105 detik | **≈30 detik** — port belum listen, curl gagal instan, hanya `sleep 2` menghitung | `deploy_vps.sh:34` sendiri menulis "sampai ~30 dtk" |
| Snapshot luring gagal "tanpa satu pesan pun" | Toast **ada** (`DashboardPage.jsx:1004-1010`); yang cacat adalah obat yang disarankannya | — |
| Peta Aset: 60 kueri per tiga kata kunci | ≈20 permintaan untuk kata kunci yang mengendap — ada penjaga `loadSeqRef` (`:472-473,487`) | — |
| `batch.py` blokir 0,6–1,6 detik | **≈0,3 detik** terukur (37 ms/thumbnail), terpotong-potong karena `auto_compress_image` sudah `to_thread` | pengukuran langsung |
| Retensi backup terhapus saat backup gagal | Retensi **sudah** digerbangi keberhasilan | `backup.py:930-938` |
| Safety-snapshot restore adalah "pola hemat yang tinggal ditiru" | Ia melakukan hal yang **sama** (satu koleksi + JSON penuh). Penulisan bertahap adalah pekerjaan baru dan harus dikenakan pada **kedua** jalur | `backup.py:462-469` |

---

## 5. PETA JALAN BERURUT

Urutan mengikuti aturan: **(a) cegah kehilangan data → (b) cegah sistem mati → (c) buat perubahan
berikutnya murah → (d) kenyamanan.**

---

### Gelombang 0 — Hari ini, nol atau hampir nol kode

**Kenapa duluan:** empat dari lima hal di bawah tidak menyentuh kode sama sekali, tetapi menutup
lubang operasional terbesar. Sebagian juga *mengukur*, sehingga gelombang berikutnya diputuskan
dari angka nyata, bukan taksiran.

| Aksi | Perintah / tempat |
|---|---|
| Pasang swap 4 GB + `vm.swappiness=10` | `docs/OPTIMASI-VPS.md:98-103` blok B |
| Daftarkan `https://domain/api/health/deep` di monitor eksternal, interval 5 menit, notifikasi ke ponsel | UptimeRobot / Better Stack. Endpoint sudah membalas 503 saat degraded — **langsung bekerja hari ini** |
| Verifikasi cron backup yang sesungguhnya terpasang | `crontab -l` dan `grep DB_NAME /var/www/inventarisasi/backend/.env` |
| Ukur konsumsi disk arsip | `du -sh backend/backup_arsip && df -h /` |
| `export NODE_OPTIONS=--max-old-space-size=2048` di `scripts/deploy_vps.sh` | Satu baris (bagian dari C6) |

**Yang akan terasa berbeda:** Anda akan tahu sistem sakit dari ponsel, bukan dari telepon pengguna.
Dan `yarn build` yang kehabisan memori akan gagal dengan pesan jelas alih-alih mengundang
OOM-killer membunuh mongod.

---

### Gelombang 1 — Cegah kehilangan data (C1, C20, C21, C5, C6, C7, C18, C19, C3, C9, C11)

**Kenapa urutannya begitu:** ini semua adalah jalur di mana data atau pekerjaan **hilang dan tidak
bisa dipulihkan** — foto surveyor yang tak pernah sampai, aset luring yang tak pernah tersinkron,
blob GridFS yang id-nya ikut terhapus, cadangan yang tidak ada padahal layar bilang ada, dan
produksi yang mati tanpa jalan pulang. Semuanya kecil, dan semuanya bisa dikirim satu PR sendiri.

| PR | Isi | Ukuran |
|---|---|---|
| 1.1 | **C1** — `photoItemsRef` di `AssetForm.jsx` (hanya `:1687` dan `:1758`) | XS |
| 1.2 | **C20** — jangan majukan `lastSync` saat `quotaHit` | XS |
| 1.3 | **C21** — `isQuotaExceeded` di `persistQueueItem` + toast `duration: 0` + uji di `lib/` | S |
| 1.4 | **C6a** — `BUILD_PATH=frontend/build.new` + tukar atomik `mv` | S |
| 1.5 | **C6b** — simpan `PREV`, rollback bila gerbang kesehatan gagal | S |
| 1.6 | **C7** — `origin/${DEPLOY_BRANCH:-main}` di 8 titik + pemeriksaan eksplisit, atau arsipkan kedua skrip | XS |
| 1.7 | **C5** — `terakhir_sukses`/`status_terakhir`/`galat_terakhir` + UI lencana merah + kosongkan `terakhir` saat gagal | S |
| 1.8 | **C18** — helper `cascade_hapus_blob_aset` dipanggil dari kedua jalur hapus + uji hitung `fs.files` | S |
| 1.9 | **C19** — satu `log_audit("bulk_delete", …)` sebelum `delete_many` di `activities.py` | XS |
| 1.10 | **C3** — scope persediaan di `reports.py:3893` + uji dua-satker | XS |
| 1.11 | **C9** — SIMAN: kunci numerik `None` bila kolom tak ada + laporkan kolom tak dikenali | S |
| 1.12 | **C11** — hapus blok PostHog + catat keputusan di `docs/DPIA-PELACAKAN-ASET.md` | XS |

**Yang akan terasa berbeda:** foto Mode Kamera Penuh berhenti hilang secara intermiten; perangkat
lapangan tidak lagi berangkat dengan cache yang diam-diam tak lengkap; deploy gagal tidak lagi
berarti situs mati sampai ada manusia; layar Pengaturan berhenti berbohong tentang cadangan; dan
berkas rekonsiliasi SAKTI mulai bisa di-tie-out.

---

### Gelombang 2 — Cegah sistem mati atau berhenti melayani (C31, C24, C25, C26, C27, C28, C29, C30, C32, S2, S6, U22)

**Kenapa urutannya begitu:** setelah data aman, prioritas berikutnya adalah *ketersediaan*.
Semua ini adalah jalur yang membekukan worker, memutus WebSocket massal, atau membiarkan sebagian
indeks tidak pernah dibuat tanpa siapa pun tahu. C31 diletakkan **sebelum** C32 karena C32
menambah indeks unik baru — persis jenis baris yang bisa membatalkan sisa daftar.

| PR | Isi | Ukuran |
|---|---|---|
| 2.1 | **C31** — helper `_idx()` per indeks + `checks["indexes"]` di `/api/health/deep` | S |
| 2.2 | **C4b** — `checks["disk"]` di `/api/health/deep` (memakai pola `backup.py:328`) | S |
| 2.3 | **C24** — `broadcast_local` paralel berbatas waktu + `ws.close()` pada socket mati + uji | S |
| 2.4 | **C25a** — plafon `MAKS_KARTU` + `@limiter.limit("3/minute")` pada `cards/bulk` (ukur 100/500/1000 dulu) | XS |
| 2.5 | **C26 + C27** — `to_thread` di `batch.py` dan `workbook.close()` | XS |
| 2.6 | **C28** — `to_thread` di `imports.py`, `kodefikasi.py`, `persediaan.py` (tiga baris) | XS |
| 2.7 | **C29** — `bersihkan_job_basi(menit=5)` di blok startup | XS |
| 2.8 | **S6** — penanda migrasi di `app_runtime` untuk tiga backfill startup + naikkan iterasi gerbang 15→45 | S |
| 2.9 | **U22** — `cancel()` empat task sebelum `client.close()` | XS |
| 2.10 | **S2** — tulis JSON bertahap pada `run_backup_task` **dan** safety-snapshot | M |
| 2.11 | **C30** — mode pemeliharaan saat restore, dengan `/api/health` **ikut melapor** | S |
| 2.12 | **C32** — dedupe `satker` lalu indeks unik dengan fallback non-unik | S |
| 2.13 | **C25b + S7** — `to_thread` untuk perakitan kartu dan render PDF TTD, hapus N+1 | S |
| 2.14 | **U21** — `proxy_read_timeout 3600s` pada blok `/api/ws` | XS |

**Yang akan terasa berbeda:** satu ponsel di area sinyal buruk berhenti menahan seluruh bus
realtime; "Cetak Kartu Massal" berhenti membekukan worker; impor XLSX tidak lagi menyendat seluruh
aplikasi; deploy berhenti gagal karena boot lambat; dan kegagalan indeks parsial menjadi **terlihat**
di health check alih-alih hanya tercatat satu baris di log.

---

### Gelombang 3 — Kebenaran angka & tata kelola (C2, C8, C10, C12–C17, C23, C36, C37, S1, S5)

**Kenapa urutannya begitu:** setelah data aman dan sistem hidup, yang tersisa adalah *apakah angka
dan jejaknya benar*. Untuk aplikasi penatausahaan BMN, laporan yang salah lebih berbahaya daripada
laporan yang gagal — dan jejak audit yang tak terlihat meniadakan tujuan modul auditnya sendiri.

| PR | Isi | Ukuran |
|---|---|---|
| 3.1 | **S1a** — penjaga plafon diam: `count_documents` + alihkan ke Pusat Unduhan di atas ambang | S |
| 3.2 | **S5a** — penanda `terpotong: true` pada daftar kegiatan | XS |
| 3.3 | **C2** (3 PR) — `purchase_price_num`: tulis → backfill+indeks → tukar pembaca | M |
| 3.4 | **C36** — teruskan ambang efektif ke Sheet 2, `pemeliharaan.py:476`, `pengadaan_utils.py:101` | XS |
| 3.5 | **C16** — angkat `_wajib_super_admin` ke `auth_utils.py`, pasang di endpoint tulis referensi + `log_audit` | S |
| 3.6 | **C12 + C15** — `require_super_admin` pada `categories-all`; `periksa_kekuatan_password` di `users.py` | XS |
| 3.7 | **C13** — `log_audit` di enam handler `users.py`, stempel satker **target** | S |
| 3.8 | **C14** — `kode_satker` pada `log_audit` di `ttd.py` dan `bast.py` dulu, lalu modul lain | S ×3 |
| 3.9 | **C17** — `backfill_saldo_awal` memakai `catat_mutasi_bmn` | XS |
| 3.10 | **C23** — try/except + kompensasi hapus jurnal pada reklasifikasi | XS |
| 3.11 | **C8** — cuplikan parameter saat kunci periode + pembacaan ber-fallback | M |
| 3.12 | **C10** — tolak penimpaan `masa_manfaat` lintas-kode di pagar `dilindungi` | S |
| 3.13 | **C37** — bekukan `dasar_hukum` ke record BAST (+ BA perbaikan, + LBP bersama 3.11) | XS |
| 3.14 | **U12** — tiga invarian angka di dasbor integritas (read-only) | S |

**Yang akan terasa berbeda:** "Harga Tertinggi" memberi hasil yang benar dan sama antara daring
dan luring; laporan berstempel FINAL tercetak ulang identik; berkas rekonsiliasi tidak lagi
membantah dirinya sendiri; admin satker bisa melihat siapa membatalkan TTD di satkernya; dan satu
admin satker tidak lagi bisa menggeser neraca satker lain.

---

### Gelombang 4 — Buat perubahan berikutnya murah (U1–U5, U6, U8, U13, U18, U19, C33, C34, C35, S3)

**Kenapa urutannya begitu:** semua di atas memperbaiki keadaan hari ini. Gelombang ini memperbaiki
*laju*. Ia diletakkan setelah gelombang 1–3 karena tidak satu pun mendesak, tetapi tanpa gelombang
ini setiap perbaikan berikutnya akan lebih mahal daripada yang sekarang.

| PR | Isi | Ukuran |
|---|---|---|
| 4.1 | **U1** — `test_urutan_rute.py` (nol perubahan produksi) | S |
| 4.2 | **C33** — `setdefault` env di conftest + arsipkan uji usang + job CI opsional `-m integration` | S |
| 4.3 | **U3a** — `pytest-cov` + `--cov-fail-under=60` di CI | XS |
| 4.4 | **C34** — satukan daftar koleksi ber-satker + uji registry | S |
| 4.5 | **C35 + U13a** — `lampiran_utils.py` + ganti 8 pemanggil + uji berbasis penemuan | S |
| 4.6 | **U18** — empat uji asap render PDF + satu uji data kosong | S |
| 4.7 | **U4** — `pdf_kit.py` dengan impor eksplisit + `test_pdf_kit.py` | M |
| 4.8 | **U6** — ekstrak `satker_scope.py` (hanya PR-1) | S |
| 4.9 | **U5** — `test_bast_pdf.py` bergaya `test_belah_endpoint.py` | S |
| 4.10 | **U19** — `test_registry_frontend.py` (menutup langkah ke-4 docstring) | S |
| 4.11 | **U8** — uji meta AST untuk stempel `kode_satker` pada `insert_one` | S |
| 4.12 | **U2** (3 PR) — `siklus_registry.py` deskriptif → turunkan daftar → uji registry | M |
| 4.13 | **S3** (4 PR) — `audit_logs`: field `ts` → backfill+indeks → **keyset** → arsip | M |
| 4.14 | **U3b** — uji endpoint `mongomock` per modul: `imports` → `backup` → `auth`+`users` → `batch` | S ×4 |

**Yang akan terasa berbeda:** pengurutan `include_router` berhenti menjadi ranjau; menambah field
aset atau modul siklus baru berhenti menuntut mengingat 14 daftar; dan cakupan uji berhenti turun
diam-diam. Ini gelombang yang membuat gelombang 5 dan seterusnya bisa dikerjakan dengan tenang.

---

### Gelombang 5 — Kenyamanan & skala jauh (S4, S5b, S8–S13, U7, U9–U11, U14–U17, U20, U23–U34)

Kerjakan **saat kebetulan menyentuh berkasnya**, atau saat ambang di Bagian 6 mendekat. Tidak ada
yang mendesak di sini.

Urutan yang saya sarankan bila ada waktu luang: **S4** (pindahkan arsip backup ke luar VPS — nilai
ketahanannya paling tinggi dari gelombang ini) → **U15** (`useCallback`, ongkos hampir nol,
langsung terasa saat mengetik) → **S13** (jitter + TTLCache reconnect) → **S9** (`asset_created`
per baris) → **S5b** (cache daftar kegiatan) → **U7** (cache `id_kegiatan_satker`) → **U24**
(indeks Buku Barang) → **U16** (dua impor statis PhotoLightbox) → **U14** (`App.js` bertahap) →
**S10** (cache snapshot luring) → sisanya.

---

## 6. Ambang & tanda bahaya

Tabel ini supaya Anda bisa memantau sendiri tanpa menunggu tinjauan berikutnya. Kolom "cara
memeriksa" sengaja berisi perintah yang bisa disalin apa adanya.

> Kolom **Waspada** bukan "sistem akan rusak di angka ini", melainkan "di sekitar sini mulai
> rencanakan perbaikan yang relevan". Di mana angkanya perkiraan, kolom Dasar menyebutkannya.

| Metrik | Aman | Waspada | Cara memeriksa | Dasar angka |
|---|---|---|---|---|
| Ruang disk bebas | > 30% | **< 15%** | `df -h /` | Disk penuh = mongod berhenti menulis = seluruh aplikasi mati. Batas 15% adalah ambang operasional konservatif, bukan hasil ukur |
| Ukuran arsip backup lokal | < 3× ukuran GridFS | **> 5×** | `du -sh backend/backup_arsip && mongosh --quiet --eval 'db.fs.files.aggregate([{$group:{_id:null,b:{$sum:"$length"}}}]).toArray()'` | Aturan pasti: kebutuhan ≈ (1 + retensi) × total byte GridFS |
| RAM bebas + swap terpasang | swap ≥ 4 GB | **swap 0** | `free -h` | `docs/OPTIMASI-VPS.md:17,31` menyatakan tanpa swap satu lonjakan bisa memicu OOM-killer |
| Jumlah aset per satker | < 50.000 | **> 150.000**; **500.000 = plafon keras** | `mongosh --quiet --eval 'db.assets.countDocuments({})'` | 500.000 pasti (`to_list(500000)` di `lbp.py`/`reports.py` memotong senyap). 150.000 adalah perkiraan dari jejak memori dict Python per dokumen ter-proyeksi — **belum diukur** |
| Baris `audit_logs` | < 500.000 | **> 2.000.000** | `mongosh --quiet --eval 'db.audit_logs.countDocuments({})'` | Perkiraan: `count_documents` + `skip` atas `$or` tanpa indeks yang melayaninya, ditambah `timestamp` string yang ~4× lebih boros dari BSON date |
| Baris `mutasi_bmn` | < 50.000 | **> 100.000 = plafon keras** | `mongosh --quiet --eval 'db.mutasi_bmn.countDocuments({})'` | 100.000 pasti: `to_list(100000)` di `lbp.py:289` memotong Rincian Mutasi CaLBMN **tanpa peringatan** |
| Kegiatan per satker | < 80 | **> 100 = pemotongan senyap** | `mongosh --quiet --eval 'db.inventory_activities.countDocuments({})'` | Pasti: `$limit: 100` di `activities.py:330` |
| Jumlah indeks pada `assets` | < 50 | **> 58** (plafon keras 64) | `mongosh --quiet --eval 'db.assets.getIndexes().length'` | Plafon 64 adalah batas MongoDB. Digabung C31, `create_index` ke-65 membatalkan sisa daftar |
| Backup terakhir **berhasil** | ≤ 1 hari | **> 3 hari** | Setelah C5: baca `terakhir_sukses` di layar Pengaturan. Sebelum C5: `ls -la backend/backup_arsip/` dan lihat **ukuran** berkas terbaru, bukan tanggalnya | Klaim tanggal saat ini tidak sama dengan bukti keberhasilan |
| Waktu boot backend (deploy) | < 15 detik | **> 25 detik** | `tail -f /var/log/supervisor/inventarisasi-backend.out.log` — hitung jarak dari restart sampai "Application started successfully" | Gerbang deploy efektif ≈30 detik (`deploy_vps.sh:34,37`) |
| Health check dalam | HTTP 200 | **503 atau timeout** | `curl -fsS -m 10 https://<domain>/api/health/deep \| jq` | Endpoint sudah dirancang membalas 503 saat degraded (`server.py:239-296`) |
| Cakupan uji `routes/` | ≥ 29% dan naik | **turun dari nilai sebelumnya** | `python -m pytest -q --cov=backend --cov-report=term` lalu `coverage report --include='backend/routes/*'` | Terukur hari ini: 29%. Tujuan gerbang CI adalah mencegah TURUN |
| Peringatan lint frontend | 15 (sekarang) | **naik** | `cd frontend && npx eslint src 2>&1 \| tail -3` | Terukur: 11 `exhaustive-deps` + 4 `eslint-disable` tak terpakai. Peringatan ke-16 yang berbahaya akan tenggelam bila daftarnya terus tumbuh |
| Ukuran satu halaman snapshot luring | belum diukur | ukur sebelum menyentuh U34 | `curl -s -o /dev/null -w '%{size_download}\n' "https://<domain>/api/assets/offline-snapshot?activity_id=<id>&limit=1000" -H "Authorization: Bearer <token>"` | Seluruh argumen U34 bergantung pada angka ini |

**Satu rutinitas bulanan yang saya sarankan (5 menit):** jalankan enam perintah `mongosh` di atas,
`df -h /`, `du -sh backend/backup_arsip`, dan `curl` health/deep. Catat hasilnya di CHANGELOG.
Deret angka dari waktu ke waktu jauh lebih berguna daripada satu snapshot, dan repo ini sudah punya
kebiasaan mencatat alasan — ini kandidat yang tepat untuknya.

---

## 7. Yang TIDAK saya sarankan

Menyebut apa yang tak perlu dikerjakan sama berharganya dengan menyebut apa yang perlu.
Setiap butir di bawah adalah saran yang terdengar masuk akal tetapi akan merugikan sistem ini.

**Jangan pecah menjadi microservice, dan jangan pisahkan layanan.**
Sistem ini berjalan di satu VPS 2 vCPU / 8 GB. Memecahnya menambah jaringan, serialisasi, dan mode
kegagalan baru pada mesin yang sumber dayanya justru sedang menjadi kendala. Titik jenuh pertama
adalah CPU event loop, dan itu diperbaiki dengan `asyncio.to_thread` (gelombang 2), bukan dengan
memindahkan kode ke proses lain. `docs/OPTIMASI-VPS.md:140-175` sudah menolak arah ini dengan
pemicu eskalasi konkret — penilaian itu masih benar.

**Jangan ganti MongoDB.**
Model datanya sudah menyatu dengan MongoDB (GridFS, TTL index, capped collection, keyset pagination,
indeks unik parsial sebagai penegak invarian). Semua keluhan performa di laporan ini bisa
diselesaikan dengan indeks, cache, dan mengubah cara membaca — bukan dengan mengganti mesin.
Migrasi ke Postgres berarti menulis ulang 70 koleksi, seluruh jalur backup/restore, dan seluruh
lapisan isolasi satker sekaligus.

**Jangan tulis ulang frontend, dan jangan migrasi ke Next.js atau framework lain.**
Code splitting sudah bekerja, virtualisasi sudah benar, batas galat sudah dipasang dengan tepat,
dan antrean simpan luring adalah bagian paling matang di seluruh aplikasi. Semua temuan frontend
di laporan ini muat dalam satu PR masing-masing. Menulis ulang berarti membuang `useOptimisticQueue`,
`offlineSnapshot`, dan `gabungAntrean` — tiga modul yang komentarnya menyebut kegagalan lapangan
konkret, artinya tiga modul yang sudah membayar biaya belajarnya.

**Jangan pasang Celery / RQ / worker khusus untuk job latar.**
Betul bahwa "job latar" di sini masih berbagi event loop. Tetapi urutan yang benar adalah:
(1) selesaikan `to_thread` di gelombang 2, karena setelah itu semaphore yang sudah ada baru
benar-benar bekerja; (2) **ukur** — tambahkan metrik "durasi terlama satu handler" ke middleware
durasi yang sudah ada di `log_setup.py`; (3) hanya bila (2) masih buruk pada beban nyata,
pertimbangkan satu proses uvicorn khusus dengan blok nginx sendiri — itu pun perubahan konfigurasi,
bukan kode.

**Jangan pasang Kafka, Debezium, ClickHouse, Loki, atau Prometheus self-hosted.**
`docs/LOGGING.md:29-53` dan `docs/OPTIMASI-VPS.md:140-175` sudah menolak arah ini secara tertulis
dengan alasan yang masih berlaku. Untuk kebutuhan pemantauan hari ini, satu monitor eksternal
gratis ke `/api/health/deep` (Gelombang 0) memberi 90% manfaatnya dengan 0% biaya pemeliharaan.

**Jangan pecah `routes/reports.py` sekarang.**
6.611 baris, cakupan 14%, dan 11 modul lain menariknya. Memecahnya sebelum ada uji asap render
adalah refactor tanpa jaring pada jalur yang menghasilkan dokumen resmi. Urutan yang benar: uji
asap dulu (4.6), ekstrak `pdf_kit.py` (4.7), baru — jauh belakangan, dan hanya bila memang perlu —
pindahkan blok Executive Summary sebagai PR tersendiri.

**Jangan kerjakan migrasi `kode_satker` pada koleksi `assets` (tulis field → backfill → tukar scope).**
Rangkaian tiga PR itu adalah migrasi model data pada **penjaga keamanan** di sistem produksi
multi-satker. Manfaat performanya sebagian besar gugur (jalur panas sudah punya jalan keluar dini),
dan risikonya jauh melebihi manfaat yang terbukti. Kirim cache `id_kegiatan_satker` saja.

**Jangan salin mekanis pola `mutasi_bmn.py:70` ke `lbp.py:285-289`.**
Terlihat seperti pembersihan konsistensi, tetapi `assets` di `lbp.py` sudah disaring
`filter_aset_perhitungan` — mengganti filter jurnal ke per-satker akan menarik masuk jurnal aset
yang sengaja dikeluarkan dari basis perhitungan. Itu menukar satu ketidakcocokan dengan
ketidakcocokan baru yang lebih sulit dijelaskan ke pemeriksa.

**Jangan tambahkan entri jurnal keluar (301) di `delete_asset` tanpa membedakan kode transaksi.**
Aset yang keluar lewat SK penghapusan sudah dijurnal di `penghapusan.py:249-266`. Menambahkan 301
di jalur hard-delete akan menjurnal kurang **dua kali** — dan repo ini sudah pernah digigit kelas
kesalahan yang sama, tercatat panjang di `penghapusan.py:243-251`.

**Jangan naikkan `react-hooks/exhaustive-deps` ke `error` secara massal.**
`eslint.config.mjs:52-55` sudah menuliskan alasannya: penjaga yang menyalak masal justru dimatikan
orang, bukan dipatuhi. Audit satu per satu menunjukkan 1 dari 11 peringatan berbahaya (C1) dan 10
aman. Perbaiki yang satu, bekukan yang sepuluh dengan komentar alasan, lalu targetkan nol peringatan
supaya peringatan ke-12 benar-benar berarti sesuatu.

**Jangan buang uji berbasis teks di frontend, dan jangan pangkas komentar panjang di mana pun.**
Uji `readFileSync` menjaga hal yang berbeda dari uji render — ia menangkap "pemanggil hilang", dan
komentarnya menyebut dua insiden nyata. Komentar panjang di repo ini menyebut kegagalan lapangan
konkret, bukan basa-basi; itu memori institusional yang menurunkan biaya perubahan berikutnya
secara nyata. Keduanya aset, bukan beban.

**Jangan tambahkan pola `phc_…` ke `scripts/cek_rahasia.py`.**
Itu kunci publik by design. Menandainya akan mengajari Anda bahwa pemindai rahasia berbunyi untuk
hal yang tak perlu ditangani — dan pemindai yang berbunyi palsu adalah pemindai yang akhirnya
diabaikan.

**Jangan kerjakan "jendela geser" untuk `mobileAssets` sebagai PR kecil.**
Ia menyentuh pembukuan halaman di lima titik dan diam-diam mengubah navigasi PhotoLightbox
(`siblings` yang terpotong). Bila memang mau dikerjakan, ia butuh perancangan tersendiri — bukan
slot di peta jalan.

**Jangan ubah `PAGE_LIMIT` snapshot luring dari 1000 tanpa mengukur satu halaman dulu.**
Penulisnya sudah menimbang trade-off itu secara sadar dan menuliskannya di
`lib/offlineSnapshot.js:185-193`. Mengubah keputusan yang berkomentar seperti itu berdasarkan
taksiran di atas taksiran adalah cara tercepat membuat orang berhenti mempercayai komentar-komentar
di repo ini — dan komentar itulah salah satu aset terbesarnya.

---

*Dokumen ini bersifat baca-saja: tidak ada berkas kode yang diubah dalam penyusunannya.
Setiap angka yang tidak berlabel "perkiraan" berasal dari perintah yang disebutkan di dekatnya.*
