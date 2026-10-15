# OPT-06 — Restore fail-closed dan recovery tahan proses mati

Core keselamatan restore diimplementasikan dan diuji. Seluruh-system quiesce
untuk backup DR tetap dependensi OPT-07: barrier di sini mencakup penulis HTTP
serta scheduler yang mengadopsi helper, belum membuktikan setiap penulis lama.

## Kontrak dan invariant

`restore_control` singleton `_id=GLOBAL` tidak ikut backup, restore, reset,
atau TTL. State aktif: `preparing`, `restoring`, `rolling_back`,
`recovery_required`; state terminal: `completed`, `rolled_back`, `aborted`.
`destructive_started` dipersistenkan sebelum wipe. Lease `backup_jobs` basi
bukan bukti data aman; stale cleanup tidak membuka recovery gate.

Kontrol menggunakan CAS dan `_id` unik. State `deploying` milik skrip deploy
menolak klaim restore. Deploy tidak menutup GET/health, tetapi admission HTTP
penulis menahan `deploying` dan semua state restore aktif.

Preflight membaca SEMUA entri sebelum wipe: nama/path/symlink/enkripsi,
duplikat, koleksi wajib/alias legacy, JSON/BSON, ID/media, seluruh blob,
ukuran/checksum/CRC, batas hasil dekompresi. Safety snapshot terpadu mencakup
seluruh koleksi, GridFS dan uploads; gagal membuat/validasi snapshot membatalkan
sebelum wipe. Maksimum 100 GiB hasil dekompresi, 500.000 entri, 64 MiB metadata,
dan 16 Mi karakter/dokumen adalah batas eksplisit, bukan muat satu koleksi.

`restore_write_leases` mencatat request mutasi yang sedang berjalan; sesudah
gate dinaikkan coordinator menunggu seluruh lease selesai. Writer mendaftar
lalu memeriksa gate tanpa cache, sehingga balapan admission vs awal restore
tertutup. Lease tidak punya TTL: worker yang terjeda tidak diasumsikan mati.
Restore menunggu jendela cache read 3 detik sebelum snapshot/wipe. Request baca
panjang dan penulis detached yang belum mengadopsi guard merupakan batas
quiesce yang perlu diukur/diselesaikan dalam OPT-07, bukan dijanjikan selesai.

Generasi batch dirotasi sebelum restore, rollback, dan recovery; retry operasi
lama tidak otomatis diterapkan ke dataset baru. Portal selalu dicabut, lease
portal dibuang, counter tiket diperbaiki dan indeks dibangun ulang. Verifikasi
memeriksa jumlah koleksi, blob hasil GridFS dengan SHA-256, serta uploads hasil.
Invalidasi seluruh namespace Redis ditunggu dan kegagalan tidak ditelan; cache
lokal dibersihkan, checkpoint Meili dipagari `force_mongo` sampai rebuild yang
dikonfirmasi. Mekanisme epoch cache lintas worker disediakan paket cache bersama.
Index gagal menahan layanan. Rollback gagal mempertahankan source ZIP dan
safety ZIP, serta menyatakan `recovery_required`; pesan tidak mengklaim data
sudah kembali. Temp cleanup/dismiss tidak menghapus recovery artifacts aktif.

## Jalur operator saat aplikasi ditahan

Jalankan sebagai operator Unix aplikasi, menggunakan `backend/.env` yang sudah
ada. Jangan menyalin URI/password ke command/log. Hentikan SELURUH backend
worker dan scheduler penulis sebelum mengambil alih proses yang terputus.

```sh
cd /var/www/inventarisasi/backend
venv/bin/python restore_recovery.py status
# Sesuaikan path interpreter dengan instalasi yang sebenarnya.
venv/bin/python restore_recovery.py clear-writer-leases --workers-stopped
venv/bin/python restore_recovery.py recover --job-id JOB_ID --workers-stopped
```

`recover` memvalidasi safety ZIP, mempertahankan gate, mengimpor lalu
memverifikasi data/media/indeks; hanya keberhasilan mengubah state terminal.
Jika proses mati dalam `preparing` sebelum destructive phase, gunakan
`abort-preflight --job-id JOB_ID --workers-stopped`; perintah menolak bila wipe
sudah dimulai. Jangan sekadar menghapus control atau safety ZIP. Recovery state
aktif melarang rollback kode dan deploy biasa. Setelah terminal terverifikasi,
nyalakan kembali layanan lalu periksa health, data dan login.

Endpoint status: `GET /api/backup/restore/recovery`, super-admin pusat.
Endpoint pemulihan: `POST /api/backup/restore/recovery/{job_id}` dengan
`confirm_workers_stopped=true`, super-admin pusat, act-as ditolak. CLI dipilih
untuk crash yang menghilangkan dokumen user atau memerlukan penghentian server.
Konfirmasi endpoint adalah pernyataan operator; expiry lease sendiri bukan
izin mengadopsi worker lama.

## Bukti

Unit fault injection: missing/corrupt blob, path traversal, checksum dan
manifest incomplete sebelum wipe; safety gagal; rollback berhasil dan gagal;
legacy archive, portal revocation; stale lease, retensi artifacts; mutex deploy,
writer admission dengan cache negatif lama dan lease terjeda.

Drill Mongo/GridFS asli:

```sh
.venv/bin/python scripts/uji_backup_recovery.py
```

Script tidak menerima URI/DB tujuan dari operator: hanya localhost dan nama
acak `aman_ci_backup_<uuid>`, dengan temp directory terpisah. Child di-SIGKILL
sesudah `assets.delete_many({})` nyata; proses baru membuktikan gate tetap
aktif, mengambil safety, dan memulihkan GridFS SHA-256, uploads, counter tiket,
portal revocation, serta autentikasi user hasil restore. DB uji di-drop setelah
validasi nama/host; tidak bergantung atau menulis produksi. Drill berhasil
secara lokal; belum merupakan offsite DR atau pengukuran RPO/RTO OPT-07.

## Frontend: recovery tetap terlihat

`recovery_required` menampilkan peringatan merah dan menahan tombol menutup hasil
pekerjaan. Bentuk minimal juga menyatakan pemulihan memerlukan tindakan.
Pengaturan membaca `/backup/restore/recovery`; kontrol restore menjelaskan bahwa
layanan ditahan bila rollback belum terverifikasi. Dialog tidak menjanjikan
pengembalian otomatis selalu berhasil. Tes BackgroundTaskBar membuktikan job
failed+recovery_required tidak dapat didismiss melalui UI.

## Pencegahan kehilangan akses admin

Preflight restore penuh mensyaratkan setidaknya satu admin pusat aktif dengan
`id`/`username` persisten, hash bcrypt berformat sah, serta field `name` dan
`created_at` yang dipakai respons login. Role/satker persisten menjadi otoritas;
flag act-as tidak dapat menciptakan super-admin. Admin tidak boleh terkunci
hingga waktu masa depan. Pemeriksaan hash hanya bentuk/encoding, tanpa
menjalankan cost bcrypt dari arsip dan tanpa meminta atau membuat password.

Safety snapshot memeriksa invariant autentikasi yang sama sebelum wipe, secara
terpisah dari keberadaan koleksi kosong opsional. Hasil impor/rollback diperiksa
kembali sebelum gate dibuka dan safety dihapus. Pengujian menolak arsip kosong,
semua admin nonaktif, admin satker, identitas/password/field login tidak lengkap,
serta otoritas efemeral palsu; kehilangan admin sesudah insert memicu rollback.
Drill terisolasi memakai password acak khusus proses uji dan benar-benar
memanggil handler login sesudah pemulihan, bukan hanya membuat JWT secara manual.
