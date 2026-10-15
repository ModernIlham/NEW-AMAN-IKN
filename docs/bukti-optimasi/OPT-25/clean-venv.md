# OPT-25 — Environment runtime bersih pada deploy sekarang

Perubahan ini mempertahankan checkout dan docroot produksi. Instalasi pip pada
venv aktif diganti persiapan Python3.11 terpisah, aktivasi setelah STOPPED, dan
rollback ke environment lama yang tidak diubah. Layout immutable aplikasi/nginx
penuh tetap conditional sesuai hasil.md.

## Urutan operasional

1. Target/controller SHA terpisah, ancestry main, CI push/main yang tepat,
   anti-downgrade otomatis, snapshot env privat, mutex GLOBAL, dan drain writer/job
   tetap wajib. Hanya typed export_v1 queued yang boleh tertahan; typed running,
   generic queued, unduhan queued/running dan semua writer lease memblokir.
2. Candidate dibuat eksklusif di path final `backend/.venv-releases/<sha>-<uuid>`.
   `venv --without-pip` mencegah bootstrap lama masuk runtime. Installer terpisah
   pip26.2.1 memakai wheel SHA256
   `71138adf1f4ca900cdb7d289c21b7494329f2332b6d85f0e1c42108c0384ed3e`,
   fixed HTTPS tanpa redirect, verifikasi TLS/CA, dan ZIP/ukuran berbatas.
3. Install `--only-binary=:all: --require-hashes`, external pip check dan
   importlib.metadata wajib persis137paket runtime lock. Native smoke<=30detik
   memverifikasi Inter SHA/embedding/geometri PDF dan XLSX/DOCX/PPTX di memori;
   HTTP/font eksternal ditolak sebelum service berhenti.
4. Config Supervisor dan identity process `/proc` diperiksa. Stopasgroup dan
   killasgroup wajib; STOPPED seluruh worker harus terbukti sebelum Git reset
   dan swap venv. Old real-directory disimpan, pointer `backend/venv` ditukar
   atomik. Fresh start wajib cocok PID/cwd/interpreter, SHA API, deep health dan
   source SHA frontend. Jangan rename candidate sesudah install: shebang memakai
   path final absolutnya.
5. Kegagalan sebelum final release memulihkan source/env/docroot dan venv lama,
   kemudian memeriksa fresh process/health. Rollback tidak menjalankan pip.
   Sesudah percobaan final release, ack Mongo yang hilang mungkin berarti owner
   baru sudah masuk: rilis baru yang sudah sehat dipertahankan, exit70, tanpa
   rollback/abort/retry release. Periksa owner GLOBAL aktual dahulu.

State privat `.run-*` memuat fase/inventory/SHA lock/disk dan inode/device
alokasi, tanpa isi env privat. Collision atau inode pengganti tidak memberi hak
hapus. Crash sebelum bukti alokasi durable meninggalkan orphan yang dipertahankan.

Persiapan memerlukan free>=3GiB dan>=20%; ready memerlukan>=1GiB dan>=20%.
Reserve ini bukan perkiraan pasti ukuran install. ENOSPC/fsync gagal menggagalkan
aktivasi. Tidak ada GC otomatis menurut umur/prefix; inventarisasi pointer aktif,
descriptor, inode dan proses sebelum merencanakan penghapusan retained-env.

## Rollback manual

Gunakan workflow **Deploy ke Hostinger VPS** dengan full target SHA yang lulus
CI push/main. Controller immutable baru dipilih terpisah dari target. Protokol:

```bash
bash /path/controller-terverifikasi/deploy_vps.sh TARGET_SHA manual CONTROLLER_SHA
```

Jangan checkout atau menjalankan deploy script target lama. Controller baru
memilih retained environment dengan descriptor/inventory persis target lock;
pipless target tidak mempunyai bin/pip dan tidak boleh memakai system pip.
`update-all.sh`, `vps-fix.sh`, dan rerun provisioning `vps-deploy.sh` menolak
managed/pipless layout sebelum mutasi.

Migrasi pertama mempertahankan satu foundation environment lama dengan fullSHA,
owned descriptor dan actual inventory. Penggunaannya kembali hanya manual,
STOPPED/fresh process, GitSHA, endpoint lama sehat dan frontend stamp controller
terpercaya. API lama tanpa release_sha tidak dinyatakan melaporkan SHA. Ini
fallback darurat yang dapat membawa dependency legacy. Kandidat tak terbukti
ditolak; tahan maintenance dan pulihkan retained directory/snapshot tercatat
setelah semua proses berhenti, tanpa menyiasati pagar dengan script lama.

## Bukti lokal

Pinned installer39kasus lulus. Environment transaksi25kasus dan2regresi alokasi
lulus memakai pipless venv/wheel nyata A→B→A. Matrix fase awal73lulus; identity
process nyata5representative dan5race release-ack/sinyal/new-owner lulus.
Matrix terbaru82kasus menjadi bagian final gate. Env/static/terminal status68
lulus, preflight/native16lulus. Native probe juga lulus pada security-runtime-b
dan exact137 pipless runtime-d. Root mencatat hasil final CI dan postdeploy
secara terpisah; fixture lokal bukan bukti native host produksi.

Durable export worker tetap off sampai lifecycle worker terpisah diintegrasikan
dan diatestasi. Pergantian venv ini tidak mengklaim zero downtime atau DR/offsite.
