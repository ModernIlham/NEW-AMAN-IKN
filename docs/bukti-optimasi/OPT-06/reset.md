# Reset sistem memakai koordinasi pemulihan

Temuan P1 setelah review: endpoint reset sebelumnya menghapus koleksi/GridFS
langsung, tanpa GLOBAL gate, drain penulis, safety snapshot, atau rollback.
Reset juga hanya mempertahankan berkas pegawai bertanda metadata; TTD kop dan
overlay denah yang masih dirujuk konfigurasi bisa hilang.

`server.reset_all_data` kini mempertahankan pemeriksaan super-admin pusat,
act-as satker, serta kata konfirmasi, lalu mendelegasikan ke `reset_service`.
Coordinator memakai unique admission backup_jobs dan mutex persisten GLOBAL,
rotasi dataset generation, drain seluruh lease fisik/job aktif, safety snapshot
seluruh data/berkas, dan mesin apply/verifikasi/index/cache milik restore.
Hanya lease HTTP reset sendiri yang dikecualikan, menggunakan ContextVar;
lease penulis lain tetap ditunggu. Safety dan target harus lolos preflight
lengkap dengan admin login yang sah sebelum destructive_started ditulis.

Target reset mengosongkan data operasional, mempertahankan koleksi RESET_KEEP
tanpa menulis ulang BSON hidup, mempertahankan uploads, serta mempertahankan
GridFS yang dirujuk data konfigurasi/master (termasuk nested ID/media URL dan
penanda pegawai lama). Berkas kerja dibuat eksklusif dengan mode 0600; cleanup
hanya menghapus berkas yang dimiliki operasi tersebut. Target di-fsync bersama
direktorinya sebelum dapat dipakai.

Kegagalan setelah wipe memulihkan safety melalui mesin restore yang sama.
Kegagalan rollback menyimpan source/safety dan meninggalkan gate
recovery_required. Proses yang mati mendadak meninggalkan preparing/restoring
persisten; heartbeat/TTL tidak dapat membuka layanan. Job menggunakan tipe
restore dengan operation=system_reset agar reaper dan operator recovery lama
tetap mengenali kontraknya.

Verifikasi lokal 15 Oktober 2026:

- **4 skenario integrasi lulus**, Mongo/Redis nyata + aplikasi ASGI sebenarnya,
  77,54 detik. Setiap probe memakai database aman_ci_reset_* terpisah dari
  fixture kontrak; tidak menjalankan reset terhadap database aplikasi.
- Berhasil: penulis yang sudah diterima menahan wipe sampai lease selesai;
  permintaan batch baru ditolak selama gate aktif; epoch lama tetap ditolak
  setelah ID aset dipakai ulang. Master/config BSON, akun login, TTD, overlay,
  media konfigurasi nested, foto pegawai lama, dan logo lokal tetap utuh.
- Fault setelah wipe: safety dipulihkan otomatis, data/media/uploads dan login
  kembali berfungsi. Fault kedua pada rollback: gate tetap tertutup, kedua ZIP
  dipertahankan; explicit recovery terverifikasi membuka layanan.
- Subprocess benar-benar keluar melalui os._exit(73) sesudah mesin wipe/apply;
  kontrol tetap restoring, login ditahan, safety tetap ada, lalu operator
  recover_restore mengembalikan data/media dan autentikasi.
- Probe ulang pada kelompok dependency keamanan baru membuktikan tautan job
  legacy dan Pusat Unduhan yang tadinya mengirim 200 berubah menjadi 404 dengan
  pesan kedaluwarsa sesudah reset menghapus artifact. Metadata job transien tetap
  mengikuti kebijakan SKIP; tidak ada NoFile yang lolos menjadi 500.
- Uji unit target ZIP mencakup referensi tanpa metadata legacy, target mode
  0600, archive invalid, dan file preexisting yang tidak boleh ditimpa/dihapus.

Untuk pemulihan proses HTTP yang mati, hentikan seluruh worker/scheduler lebih
dahulu; lease tanpa TTL sengaja tetap ada. Gunakan prosedur
`restore_recovery.py status`, verifikasi worker berhenti, lalu
`clear-writer-leases --workers-stopped` bila perlu dan
`recover --job-id ID --workers-stopped`. Jangan menghapus GLOBAL gate secara
manual. Preflight yang belum destructive dapat memakai abort-preflight setelah
worker dihentikan. Tidak ada reset produksi dijalankan dalam verifikasi ini.
