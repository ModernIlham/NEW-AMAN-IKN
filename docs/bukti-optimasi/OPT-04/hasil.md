# OPT-04 — Progres, status dan resume ubah massal

Frontend memakai protokol `batch_v2` OPT-02/03, bukan retry endpoint legacy.

- `operasiBatch.js` membagi 401/501 target menjadi potongan 200/200/1 atau
  200/200/101. Setiap potongan memiliki operation ID `b2_<epoch-ms>_<UUIDv4>`
  tetap, target, versi dan draf immutable. Versi aset yang terlihat diambil saat
  draf dibuka; target ID-only memakai preflight versi sebelum konfirmasi.
- Negosiasi `/preflight` memeriksa `protocol`, generasi dataset dan kapasitas.
  Seluruh `/prepare` harus selesai sebelum satu `/resume` pun dijalankan.
  Admission menyimpan payload/media di server; browser hanya menyimpan metadata
  pemulihan, ID target, ID operasi, status dan hitungan per akun/satker efektif.
  Bila penyimpanan checkpoint gagal, admission/mutasi tidak dimulai.
- Reload dan online memeriksa GET status. Tombol lanjut memeriksa status lagi,
  melewati potongan yang sudah selesai dan melanjutkan ID yang sama. Timeout
  sesudah commit direkonsiliasi melalui GET; tidak menciptakan ID baru.
- Status menampilkan berhasil, sudah sesuai, konflik, tidak ditemukan, gagal,
  menunggu dan rincian ID yang perlu tindakan. Izin dicabut, operasi expired,
  generasi dataset berubah dan status tidak tersedia ditahan untuk ditinjau.
- Draf parsial tetap ada dengan apply ditahan; pengguna melanjutkan operasi
  sebelumnya. Setelah seluruh hasil selesai, aksi eksplisit menyiapkan draf baru
  hanya untuk ID konflik/gagal. Draf lengkap sukses direset, seleksi dipertahankan,
  panel disembunyikan dan jendela daftar dimuat kembali pada jangkar sekarang.
  Hasil filter/kegiatan lama tidak menutup draf pada konteks baru.
- Persiapan terputus sebelum seluruh admission dapat dibatalkan hanya setelah
  status membuktikan tidak satu aset pun telah diterapkan. Riwayat server tetap
  dipertahankan. Tidak ada metadata operasi dihapus saat logout.

## Verifikasi lokal

Transport diuji dengan server simulasi stateful yang menyimpan request immutable
serta menghitung efek foto per aset: 401/501 target, potongan pertama berhasil
lalu timeout, timeout sesudah commit, reload, identitas anak tetap, foto sekali,
klik ganda, ownership checkpoint, 401/403/409 tanpa write ulang, admission parsial,
dan kegagalan penyimpanan sebelum write. Tes React memakai interaksi nyata untuk
versi draf yang tidak berubah oleh WS, preflight sebelum dialog konfirmasi,
klik ganda dan rincian hasil parsial. Tes hide-draft/seleksi lama tetap dijalankan.

Suite OPT-04: **3 suite / 16 tes lulus**. Log awal `/tmp/aman-opt04-tests.log`;
run bersama harga eksak OPT-11: **4 suite / 42 tes lulus**, log
`/tmp/aman-opt04-11-tests.log`. Lint terarah: 0 error.

Full lint/test/build, CI, uji backend Mongo sebenarnya dan smoke browser/produksi
adalah gerbang integrasi bersama. Bukti ini tidak mengklaim deploy sudah dilakukan.
