# Panduan eksekusi optimasi AMAN untuk GPT-6.1 Sol

Mulai dari [rencana OPT-00–OPT-28](RENCANA-OPTIMASI-SKALABILITAS.md).
[Review](REVIEW-ARSITEKTUR-2026-10.md) menjelaskan bukti pada commit
`62e345422b0828f54d3ca3fd5b2c6cb876f01aa2`, 15 Oktober 2026.
[Bukti baseline](bukti-review-2026-10.json) menyimpan hasil pemeriksaan lokal.

Ini handoff implementasi. Penyusun rencana belum memperbaiki runtime berdasarkan
review ini. Status “rencana selesai” tidak berarti optimasi produksi sudah selesai.

## Prompt siap pakai: mulai pelaksanaan

```text
Anda GPT-6.1 Sol. Lanjutkan repositori ModernIlham/NEW-AMAN-IKN.
Baca docs/PANDUAN-EKSEKUSI-GPT-6.1-SOL.md,
docs/REVIEW-ARSITEKTUR-2026-10.md, dan
docs/RENCANA-OPTIMASI-SKALABILITAS.md.

Kerjakan rencana tersebut bertahap sampai tuntas. Revalidasi main, siapkan
baseline/fixture OPT-00 secukupnya dan inventaris OPT-17, lalu prioritaskan
OPT-05/06 (backup/restore), OPT-02→03→04 (batch), dan OPT-08 (deploy).
OPT-01/11/12/27 dapat dikerjakan paralel jika file tidak bertabrakan.
Ikuti dependency setiap paket. Satu PR menangani satu perubahan yang dapat diuji;
pecah paket besar menurut sub-PR di rencana.

Pertahankan monolit modular, scope satker, OCC, antrean luring, media/TTD,
perhitungan resmi, serta UI kompak dan perilaku hide/seleksi terbaru.
Buktikan cacat sebelum memperbaiki; ukur sebelum mengklaim percepatan.
Migrasi memakai expand/dual-write/backfill/verify/switch/contract.
Jangan load test produksi atau menghapus data untuk membuat test lulus.

Saya telah mengizinkan penerapan perubahan selesai ke produksi. Ikuti CI,
review/merge dan deploy SHA yang lulus; verifikasi hasil produksi dan rollback.
Jangan menandai paket selesai hanya karena commit atau CI lulus.
Perbarui status, PR/SHA, bukti dan handoff setiap paket. Jika akses eksternal
belum tersedia, selesaikan pekerjaan independen dan catat blocker secara tepat.
```

## Prompt siap pakai: satu paket

```text
Kerjakan OPT-XX dari docs/RENCANA-OPTIMASI-SKALABILITAS.md di NEW-AMAN-IKN.
Periksa dependency dan revalidasi temuan pada main terbaru. Implementasikan
sub-PR pertama yang belum selesai, beserta regression test/failure injection,
rollout dan rollback. Jangan mengerjakan paket lain sekaligus.
Pertahankan invarian di panduan eksekusi. Catat hasil dan pekerjaan berikutnya.
Terapkan melalui gerbang CI/deploy yang berlaku bila paket siap dirilis.
```

Ganti `OPT-XX` dengan ID nyata. Jika paket sudah diperbaiki oleh perubahan lain,
tunjukkan commit dan tesnya; jangan membangun implementasi kedua.

## Prosedur awal setiap sesi

1. Baca instruksi lingkungan/AGENTS/skill yang tersedia saat itu. Jangan menganggap
   tool, kredensial, proses Mongo, atau path cache sesi lama masih tersedia.
2. Periksa status Git, fetch main, catat SHA dan drift dari baseline. Lindungi
   perubahan pengguna; jangan reset pekerjaan belum disimpan.
3. Pilih paket siap dengan dependency terpenuhi. Baca fungsi/test yang disebut,
   bukan hanya nomor baris atau komentar historis.
4. Tetapkan lingkup PR dan acceptance. Untuk P1, uji reproduksi dahulu; untuk
   optimasi, simpan profil sebelum perubahan pada dataset/config yang sama.
5. Jalankan check relevan lalu gerbang CI lengkap. Jangan mengulang suite penuh
   tanpa perubahan/alasan baru atau melonggarkan assertion untuk menyembunyikan bug.

## Perintah verifikasi dasar

Dari root repo, setelah setup. Sesuaikan path interpreter lokal bila berbeda;
jangan memasang paket ke runtime produksi untuk menguji perubahan.

```bash
git status --short --branch
git fetch origin main
git rev-parse HEAD
git diff --check
python scripts/cek_rahasia.py
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q backend -x 'venv|__pycache__'
.venv/bin/python -m pytest -q
```

Di `frontend`:

```bash
corepack yarn install --frozen-lockfile
corepack yarn lint
CI=true corepack yarn test --watchAll=false --runInBand
CI=false corepack yarn build
```

Lingkungan review memakai `COREPACK_HOME=/workspace/.cache/corepack`,
`YARN_CACHE_FOLDER=/workspace/.cache/yarn`, serta font melalui
`XDG_DATA_HOME=/workspace/.local/share` dan `XDG_CACHE_HOME=/workspace/.cache`.
Path ini bukan persyaratan universal; setup lingkungan baru harus memasang
font/native dependencies dan mencatat versinya.

Baseline lokal: **5.567 pytest; 198 suite/2.189 Jest lulus; lint 0 error/7 warning;
build berhasil**. Tes regresi baru akan menambah jumlah tersebut. Default pytest
belum membuktikan Mongo/Redis asli; OPT-00 membuat harness itu. Jangan mengarahkan
suite integrasi lama ke produksi atau menganggap fixture aman sebelum membacanya.

## Invarian

- **Data:** CAS membandingkan versi; retry punya identitas; hasil parsial jujur;
  audit/jurnal/foto tidak ganda. Cache/event bukan sumber kebenaran.
- **Satker:** scope efektif pada baca/tulis/media/lookup/laporan/job/cache.
  Jangan mengubah referensi global atau semantik legacy tanpa keputusan teruji.
- **Luring:** snapshot owner, TTL, quota, tombstone, antrean dan draf tetap.
  Cleanup cache tidak boleh menjadi cara membuang masalah state.
- **UI:** hide berbeda dari hapus seleksi; draf tetap saat hide; selection/filter/
  posisi tetap setelah simpan; unchecked tidak menghapus lampiran; ukuran kompak
  terbaru dipertahankan.
- **Media/dokumen:** upload→CAS referensi→cleanup; tidak menghapus blob committed.
  Registry field, TTD, nilai akuntansi dan regulasi tidak berubah sebagai efek
  samping refactor/performance.
- **Operasional:** exact-SHA CI/main, env privat, maintenance/recovery, lock,
  timeout, queue bounded, release rollback dan pemulihan backup tetap teruji.

## Catatan hasil per paket

Buat `docs/bukti-optimasi/OPT-XX/hasil.md` saat implementasi dimulai. Direktori
itu belum diisi pada planning sebagai bukti implementasi yang belum terjadi.

```markdown
# OPT-XX — Judul
- Status: Berjalan / Menunggu dependensi / Siap review / Terdeploy-terverifikasi /
  Tidak berlaku saat ini (bukti + pemicu peninjauan)
- Baseline dan hasil SHA:
- PR / main CI / deploy:
- Reproduksi dan hasil sebelum perubahan:
- Perubahan, kontrak dan invarian:
- Dataset/seed/count, toolchain/infra, perintah verifikasi:
- Hasil sesudah perubahan, fault injection, batas pembuktian:
- Migrasi: dry-run, checkpoint, konflik, dual-write coverage, parity:
- Rollout/observasi dan bukti rollback/recovery:
- Risiko/blocker:
- Sub-PR berikutnya dan dependency:
```

Lampirkan JSON metrik, explain tersanitasi, trace browser atau screenshot bila
bermanfaat. Jangan menyimpan isi aset nyata, kredensial, backup produksi atau log
pribadi. Update tabel status rencana dan tautkan bukti.

## Kapan dinyatakan selesai

Paket selesai setelah acceptance terbukti, CI wajib lulus, migrasi/rollback
tersedia, dan penerapan yang diotorisasi telah diverifikasi. Optimasi memerlukan
perbandingan setara. Paket kondisional seperti Vite/Meili/pemisahan host boleh
ditunda dengan hasil evaluasi dan pemicu yang jelas; cacat P1 yang masih berlaku
tidak boleh ditutup sebagai “tidak perlu”.

Saat berganti sesi/model, tulis status aktual, path/SHA, proses yang masih
berjalan, blocker dan langkah pertama berikutnya. Lanjutkan dari sana tanpa
mengulang setup/review seluruh repo. Penutupan akhir adalah OPT-28 setelah seluruh
P1 berlaku, kapasitas, batas layanan dan pemulihan memiliki bukti nyata.
