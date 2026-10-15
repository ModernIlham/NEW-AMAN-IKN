# Retensi static untuk tab lama — OPT-08/21/25

15 Oktober 2026. Layout produksi tetap `frontend/build`. Setelah build baru
berhasil tetapi sebelum aktivasi, `deploy_vps.sh` menjalankan helper stdlib
`scripts/retain_static_assets.py`. Tidak mengubah asset-manifest/precache build
baru, tidak bergantung pada plugin/SW frontend baru, dan tidak mengubah nginx.

Hanya path hashed `static/*` dari manifest rilis aktif dan ledger yang dilindungi
boleh disalin. Symlink/traversal/externalURL, source maps, file hilang/rusak, atau
nama hash sama dengan byte berbeda ditolak. SHA256 nyata diperiksa saat baca dan
copy streaming64KiB; copy+ledger memakai temp pada filesystem tujuan, fsync file,
rename atomik, lalu fsync direktori tujuan melalui fd `O_DIRECTORY`. Filesystem
yang menolak directory fsync menyebabkan kegagalan sebelum aktivasi.
Kegagalan tidak memodifikasi build aktif dan menyebabkan rollback
fase deploy. `.env`, index/HTML lama, dan metadata baru tidak dimasukkan manifest.

Grace `AMAN_STATIC_GRACE_HOURS` default24, minimal24 maksimal168. Aset milik
manifest current mendapat last_seen=sekarang saat cutover; aset warisan memakai
timestamp lama sehingga tidak diperpanjang selamanya. Aset expired tidak disalin
ke staging berikutnya; aset current selalu dilindungi24jam mulai cutover walaupun
build-nya lama. `build.old` tetap tersedia untuk rollback seperti sebelumnya.

Budget default `AMAN_STATIC_BUDGET_MB=256` mencakup semua hashed static baru dan
warisan protected, bukan hanya tambahan. Max20.000file; ledgermax8MiB. Budget
kurang menyebabkan deploy gagal sebelum aktivasi, **tidak menghapus file yang
masih dilindungi grace**. Headroom disk setelah copy minimal1GiB default
`AMAN_STATIC_MIN_FREE_MB=1024`. Angka budget bukan pengganti inventaris VPS dan
pemantauan disk. Tidak ada janji retensi tanpa batas bagi tab yang aktif>24jam.

## Bukti

- 10 tes helper lulus (0,76 detik): HTTP browser-path lama setelah docrootA→B dan rollback, expiry
warisan vs reset timestamp current, budget/headroom, ENOSPCcopy/ledger,
symlink/missingfile, collisionSHA256, penolakan grace<24jam, serta kegagalan
directory fsync setelah rename asset dan ledger.
- 94 tes deployment/env/SHA/retry existing lulus bersama 8 tes helper awal (102 lulus).
- Harness fase deploy nyata memakaihelper yang sama; failure retention menyebabkan
rollback pasangan oldcode/oldfrontend dan health ulang. 43skenario sebelumnya
serta1skenario retention tambahan dijalankan.
- BuildA adalah file hash aktual produksi main.c58ed824.js, diunduh baca-saja
sebagai fixture lokal (137file6.7MB tanpa maps). BuildB adalah frontend/build nyata
hasilCRACO main.a43e77a3.js. Chromium mempertahankan tabA, docroot digantiB,
lalu `<script>` dengan URL lazy chunkA di-load dan mendaftarkan webpackChunk
berhasil. SHA256 byte cocok, manifestB tetap byte-for-byte, rollbackA tetapHTTP200.
Retained64file, total201hashedfile10.504.686byte. Lihat static-browser.json.

Browser proof menguji fetch/registrasi chunk nyata dari tab yang sudah terbuka;
bukan klaim seluruhkompatibilitas N-client/API, queuedofflinewrites, atau
cutover layout immutable produksi. Keduanya tetap gate terpisah OPT-21/25.
