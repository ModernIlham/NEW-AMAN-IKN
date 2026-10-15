# OPT-22 — Penilaian aktivasi dan bukti akhir

Target menurut inventaris koordinator: satu VPS Linux,2 CPU/8 GB, satu proses
API. Budget global dapat diaktifkan terpisah dari worker durable. Penilaian ini
bukan bukti bahwa flag produksi sudah berubah; aktivasi dilaksanakan koordinator
sesudah rilis sehat dan preflight VPS terverifikasi.

## Budget global: layak rollout konservatif

Konfigurasi awal yang disepakati:

    AMAN_EXPORT_GLOBAL_BUDGET_ENABLED=1
    AMAN_EXPORT_GLOBAL_SLOTS=1
    AMAN_EXPORT_SATKER_SLOTS=1
    AMAN_EXPORT_LOCK_DIR=/var/lib/aman/export-locks
    AMAN_EXPORT_DURABLE_XLSX_ENABLED=0
    AMAN_CHECKLIST_GRIDFS_WRITE=0

Hanya key terkait yang diperbarui; seluruh env privat dan override Supervisor
dipertahankan. Tidak perlu service worker baru untuk mengaktifkan budget.
URL/scope/render output tetap sama bagi tab lama; slot sibuk dapat menghasilkan
429 dengan Retry-After yang sudah menjadi kontrak admission.

Preflight: UID API dan kernel/proc diketahui, lockdir di luar direktori rilis
milik UID aplikasi, mode0700, bukan symlink. Konfigurasi lock yang sudah ada
harus cocok; kapasitas/direktori tidak diubah atau file lock dihapus saat proses
masih hidup. Gunakan drain gate yang ada, verifikasi penulis/job selesai, lalu
restart terkontrol. Ops memverifikasi slot fisik di bawah GLOBAL deploy gate;
health hanya membuktikan worker API yang berjalan membaca flag/cap yang benar.

`/api/health` kini memiliki additive
`capabilities.export_global_budget={enabled,ok,slots,satker_slots,error_category}`.
Parser kapasitas yang sama digunakan admission:global1..8,satker1..global,
default2/2. Nilai invalid tidak diam-diam di-clamp atau dilaporkan siap:
capability okfalse,slots0,satker_slots0 dan kategori error tetap. Helper health
murni tanpa DB/FS I/O atau nilai PID/UID/path/secret. Reachability health yang
lama dan release_sha dipertahankan. Pemeriksa aktivasi mensyaratkan oktrue,
enabledtrue,slots1,satker_slots1, kemudian membuktikan lock fisik secara terpisah.

Sesudah aktivasi, smoke dua ekspor kecil terotorisasi dengan scope berbeda,
periksa artifact valid, health/deep/SHA, dan queue/holder/writer leases bersih.
Monitor RSS/CPU/latensi request ringan. Cap1 membatasi konkurensi, bukan jaminan
bahwa satu renderer lama tidak dapat menghabiskan RAM; plafon row/media tetap
berlaku dan ukuran laporan representatif masih perlu diamati.

## Worker durable: tetap off karena lifecycle deployment

Kontrak Linux/Mongo/kill-restart/authorization sudah ada, tetapi controller
rilis sekarang hanya menghentikan, memverifikasi dan memulai
inventarisasi-backend. Ia belum mengelola Supervisor export worker dan
attestation SHA proses tersebut. Mengaktifkan admission durable sekarang bisa
membiarkan worker kode/dependency lama tetap hidup setelah checkout/rollback.
Ini blocker operasional konkret, bukan keharusan menambah mesin/infra.

Aktivasi selanjutnya memerlukan satu Supervisor worker dengan UID/lockdir/cap
sama, lifecycle stop/drain/start yang ikut deploy/restore/rollback, bukti worker
fresh dari rilis yang benar, dan canary artifact dua scope. Tetap pertahankan
synchronous/legacy async saat flag0. Checklist GridFS write juga tetap0 sampai
rollback anchor server memahami refs; full GET adapter untuk tab lama tidak
membuat foundation server lama menjadi dual-reader.

## Koreksi domain harga worker

Review aktivasi menemukan artificial price bound1e18 pada JobSpec. Validator
kini memakai `asset_sorting.batas_harga`, sama domain Decimal128 eksak dengan
reader daftar/legacy export/filter laporan. Field tetap Decimal dan serialisasi
JSON memakai string, tanpa float. Nilai34 digit, negatif historis,1e6144 dan
1e-6176 didukung; nonfinite/out-of-range/35 digit inexact ditolak.

Dua kontrak baru menjalankan worker asli sampai artifact XLSX diterbitkan dan
diunduh. Matching ID dari list, XLSX sinkron legacy dan XLSX worker sama untuk
batas `1000000000000000000.01`–`.02` serta batas tunggal
`9007199254740992.02` yang harus membedakan tetangga `.01`/`.03`. Foreign satker
tidak ikut. JobSpec Mongo roundtrip mempertahankan batas desimal eksak.

Runtime bersih security-runtime-a:16 kontrak Mongo/Redis lulus13,47 detik
(6 health,5 ASGI budget,5 worker) dan53 unit budget/worker/numeric lulus20,21
detik. Compileall dan git diff --check bersih. Worker tetap nonaktif; perbaikan
harga tidak menghapus blocker lifecycle di atas.
