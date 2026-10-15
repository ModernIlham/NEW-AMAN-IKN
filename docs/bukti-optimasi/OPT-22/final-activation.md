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

## Publikasi dengan acknowledgment tidak diketahui

Review terakhir menemukan bahwa read negatif segera setelah timeout terminal
CAS tidak membuktikan write tersebut batal. `_publish` kini menyimpan guard
`publication_pending` dengan token/attempt yang sama sebelum mengirim CAS
terminal. CAS sukses menghapus guard sekaligus menyimpan artifact. Jika balasan
marker maupun terminal write tidak diketahui, blob tetap hidup, writer lease
tanpa TTL dipertahankan dengan alasan `export_publish`, dan worker tidak
mengubah pekerjaan menjadi queued/error atau mengambil ulang attempt tersebut.
Reaper menghormati guard dan lease uncertain. Metadata GridFS untuk job/token
yang sama juga mencegah reclaim bila marker belum terlihat dan pembaruan
metadata uncertainty gagal. Hanya kegagalan sebelum dispatch atau CAS miss
yang diakui boleh membersihkan blob baru milik attempt tersebut.

Admission submit juga mempertahankan ticket jika insert job kehilangan balasan;
read negatif tidak boleh melepaskan batas antrean sebelum late insert selesai.
Kasus tidak pasti memerlukan pembuktian hasil write oleh operator sebelum
guard/lease/ticket diselesaikan. Usia heartbeat, PID mati, atau read negatif
saja tidak menjadi izin cleanup publikasi.

Runtime bersih: **12 kontrak worker lulus dalam15,79 detik**, termasuk actual
Mongo/GridFS late commit setelah exception/cancellation, commit terlihat dengan
reply hilang, marker terlambat, metadata uncertainty gagal pada kedua tahap,
reclaim/reap refusal saat expiry/PID mati, bytes download tetap utuh, dan late
insert mempertahankan admission. **22 unit worker lulus dalam1,66 detik**,
termasuk pre-publication authorization failure dan acknowledged terminal CAS
miss yang hanya membersihkan blob attempt sendiri. Feature worker tetap off.

## Isolasi kontrak terhadap kuota ekspor

CI yang lebih cepat memperlihatkan kontaminasi kuota antar pengujian yang
memakai `contract-a`: tiga kasus malformed-media sudah menghabiskan XLSX3/menit,
sehingga dua kasus harga mendapat429; akumulasi CSV membuat kasus scalar
heritage melewati5/menit. Subset tujuh kasus yang dijalankan cepat mereproduksi
tepat tiga kegagalan tersebut. Setelah kedua kasus harga dan kasus scalar
memakai principal tersimpan baru dengan satker/role identik dan JWT asli,
subset yang sama lulus7/7 dalam8,70 detik. Limiter nyata tetap aktif, seluruh
assertion matching ID/otorisasi/paritas nilai dipertahankan, dan konfigurasi
atau batas rate-limit produksi tidak berubah. Isolasi tidak bergantung pada
kecepatan mesin atau pergantian menit.

Sesudah isolasi tersebut dan checkpoint restart event-bus diperbaiki oleh
reviewer, suite kontrak lengkap terbaru lulus **134/134 dalam189,72 detik**,
tanpa failure/error/skip. Lima source worker/maintenance dan kontrak terkait
tetap identik sepanjang verifikasi hash; tidak ada perubahan kode selama run.
Ini bukti lokal pada runtime bersih dan Mongo/Redis nyata, bukan klaim bahwa
rerun GitHub atau deployment produksi telah selesai.
