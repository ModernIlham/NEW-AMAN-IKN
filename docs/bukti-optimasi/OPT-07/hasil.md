# OPT-07 — Tooling DR siap diuji; aktivasi offsite masih menunggu tujuan

**Status: implementasi adapter dan prosedur tersedia, paket belum dinyatakan
selesai operasional.** Belum ada bukti kredensial/destinasi provider yang disetujui,
escrow key di luar host, restore pada host terpisah, atau RPO/RTO produksi.
Backup ZIP online tetap berkelas `application_best_effort`.

## Tooling yang diimplementasikan

- `backend/backup_dr_cli.py snapshot`: operator menghentikan semua service
  penulis, menyediakan inventaris penulis eksplisit, lalu tool memverifikasi
  status supervisor STOPPED/EXITED. Template bawaan menolak dijalankan sampai
  inventaris benar-benar selesai. Tool mengklaim mutex yang juga dipakai restore
  dan deploy, menolak fsyncLock milik pihak lain, mengambil fsyncLock Mongo,
  menulis ZIP melalui helper baca-saja, memvalidasi seluruh ZIP, lalu membuka
  hanya lock miliknya. Sukses berkelas
  `database_fsync_locked_services_stopped`, bukan janji quiesce berdasarkan HTTP
  drain semata. Writer Mongo lain ikut tertahan; writer filesystem uploads
  harus sudah dihentikan berdasarkan inventaris operator yang diverifikasi.
- `upload`: enkripsi AES-256-GCM secara streaming, key acak 32 byte dari berkas
  mode 600, nonce baru setiap berkas, header ikut diautentikasi. S3/S3-compatible
  memakai konfigurasi kredensial SDK yang sudah dimiliki operator; tidak ada
  provider/bucket yang dibuat atau diaktifkan otomatis. Transport multipart
  dibatasi dua transfer 8 MiB. Tujuan wajib prefix tersendiri.
- Sukses offsite mensyaratkan upload, HEAD ukuran/metadata cocok, unduh ulang
  seluruh ciphertext, SHA-256 cocok, dekripsi dengan tag sah, dan ZIP/manifest
  valid. Receipt privat mencatat `uploaded_verified` dan secara eksplisit
  `source_independent_restore_drill: false`.
- `decrypt`: plaintext hanya dipublikasikan setelah tag sah; salah key/tamper
  menghapus berkas sementara dan tidak menimpa tujuan lama.
- `check-stale`: exit 0 hanya untuk receipt offsite terverifikasi dalam umur yang
  ditentukan, exit 2 untuk stale/unverified. Hubungkan ke monitoring yang sudah
  disetujui; tool tidak mengirim pesan/notifikasi baru.

## Prosedur aktivasi setelah tujuan tersedia

1. Inventaris seluruh worker supervisor, cron, import, sinkronisasi, scheduler
   dan penulis filesystem uploads. Simpan inventaris bertanggal dan pemiliknya.
   Pastikan konfigurasi aplikasi ini tidak berbagi Mongo dengan layanan lain
   yang tidak boleh ditahan fsyncLock.
2. Siapkan bucket/prefix dari provider yang sudah tersedia. Gunakan kredensial
   least privilege untuk prefix tersebut. Terapkan retensi/object lifecycle yang
   direview (usulan 30 hari, belum janji), serta kebijakan key escrow/restore di
   luar host. Jangan menghapus arsip valid lama sebelum drill baru berhasil.
3. Buat key 32 byte melalui generator kriptografis ke berkas mode 600; salin
   melalui kanal operator ke escrow di luar VPS. Jangan meletakkan key bersama
   arsip/bucket tanpa perlindungan terpisah, menulis key di CLI, atau memasukkan
   key/secret ke Git.
4. Pada jendela pemeliharaan yang dijadwalkan, hentikan semua service yang sudah
   diinventarisasi. Tool tidak menghentikan layanan otomatis. Contoh menggunakan
   interpreter instalasi saat ini:

   ```sh
   cd /var/www/inventarisasi/backend
   venv/bin/python backup_dr_cli.py snapshot --output /lokasi-private/dr.zip \
     --writer-inventory /lokasi-private/writers.json --service inventarisasi-backend
   venv/bin/python backup_dr_cli.py upload --archive /lokasi-private/dr.zip \
     --destination s3://BUCKET-TERSEDIA/PREFIX-KHUSUS \
     --key-file /lokasi-private/dr.key --escrow-attestation /lokasi-private/escrow-receipt.json \
     --receipt /lokasi-private/dr-receipt.json
   venv/bin/python backup_dr_cli.py check-stale --receipt /lokasi-private/dr-receipt.json
   ```

   Tambahkan `--service` untuk SETIAP service penulis. `AMAN_DR_S3_ENDPOINT`
   opsional untuk provider S3-compatible. Tidak ada contoh secret literal.
5. Unduh ciphertext ke host/DB terisolasi, ambil key dari escrow terpisah,
   dekripsi lalu jalankan prosedur restore aplikasi. Verifikasi login, counts,
   nilai/jurnal, blob/checklist/TTD, indeks, relasi dan pencabutan akses portal.
   Record waktu snapshot, waktu terakhir perubahan, waktu mulai/gagal/pulih,
   dan hasil smoke untuk menghitung RPO/RTO aktual. Jangan mengandalkan host
   sumber atau safety ZIP host sumber untuk drill offsite.
6. Setelah drill berhasil dan monitoring stale benar-benar menimbulkan alert,
   aktifkan SATU jadwal yang sesuai budget disk/memori. Hindari cron ganda.

## Pemulihan proses snapshot terputus

SIGKILL dapat meninggalkan Mongo fsyncLock dan mutex `preparing`. Ini sengaja
fail-closed. Operator harus memastikan seluruh proses snapshot/penulis berhenti,
memeriksa log dan status Mongo, serta membuktikan lock adalah milik operasi
snapshot ini sebelum membuka fsyncLock. Jangan membuka lock pihak lain hanya
karena lease tua. Setelah Mongo tidak terkunci dan belum ada destructive write,
`restore_recovery.py abort-preflight --job-id snapshot_ID --workers-stopped`
dapat membatalkan mutex. ZIP `.building` tidak dianggap snapshot valid.
Jika kepemilikan lock tidak dapat dipastikan, lakukan pemeriksaan operator;
tidak ada auto-expiry yang membuka layanan secara spekulatif.

## Bukti pengujian dan batasnya

22 unit tests menggunakan kriptografi nyata serta fake provider/lock: roundtrip,
tamper, key permission, target tidak tertimpa, readback korup/HEAD mismatch,
prefix tidak sah, stale receipt, writer masih hidup, fsync unlock setelah
kegagalan, serta ZIP konsisten berlabel benar. Ini membuktikan adapter/prosedur
kode dan batasnya; tidak mengklaim provider produksi sudah dikonfigurasi.

Drill terisolasi `scripts/uji_backup_recovery.py` membuktikan SIGKILL dan
pemulihan Mongo/GridFS asli pada host pengujian, bukan restore offsite. Bukti
itu termasuk OPT-06 dan belum memenuhi syarat source-independent OPT-07.


## Hardening sebelum aktivasi

`keygen --output PATH` menulis key acak 32 byte dengan mode 600, tanpa menimpa
key lama. `machine-fingerprint` menyediakan fingerprint anonim mesin sumber.
Salinan key yang benar-benar diambil kembali dari escrow pada mesin lain
menghasilkan receipt melalui:

```sh
venv/bin/python backup_dr_cli.py attest-key --key-file /escrow-private/dr.key \
  --source-machine FINGERPRINT_MESIN_SUMBER --output /escrow-private/escrow-receipt.json
```

Receipt tidak berisi key. Source memeriksa fingerprint key dan host, perbedaan
identitas mesin, waktu verifikasi maksimum satu tahun, serta HMAC bukti
kepemilikan key. Key/receipt yang salah, receipt tidak ada, atau berasal dari
mesin sumber ditolak sebelum SDK/kredensial provider dipanggil. Ini mencegah
salah konfigurasi dan key yang tidak tersalin; operator tetap harus membuktikan
pemisahan fisik/provider melalui inventaris. HMAC bukan remote attestation
terhadap operator jahat yang juga memegang key sumber. Source-independent
restore drill tetap wajib dan tidak digantikan oleh receipt ini.

Snapshot mencatat journal privat mode 600 dan fsync di filesystem sebelum
mencoba fsyncLock. Balasan acquire/unlock yang hilang berarti hasil belum
pasti: gate `preparing` dan journal tetap dipertahankan, tidak ada unlock
spekulatif/berulang, dan tidak ada Mongo write saat mungkin masih terkunci.
Hanya balasan unlock yang terkonfirmasi `lockCount=0` mengizinkan pelepasan
mutex milik operasi itu. Lock yang sudah ada tidak di-unlock; balapan lock
pihak lain hanya melepas satu increment yang terbukti milik operasi sendiri.
ZIP plaintext snapshot dibuat langsung mode 600 dan dipublikasikan tanpa
menimpa target. Uji failure injection mencakup semua jalur ownership ini.
