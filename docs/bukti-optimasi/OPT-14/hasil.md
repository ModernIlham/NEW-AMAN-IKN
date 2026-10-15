# OPT-14 — Search lengkap dan pemulihan checkpoint

Default pencarian literal substring tetap melalui Mongo. Meili adalah engine
prefix/typo yang maknanya berbeda; `MEILI_SEARCH_SEMANTICS=prefix_typo` merupakan
opt-in eksplisit. Mengisi MEILI_URL/key saja tidak diam-diam mengganti arti
pencarian. Status admin menampilkan semantik, phase, kelengkapan dan waktu siklus.
Tidak diperlukan provisioning/aktivasi Meili untuk rilis ini.

Library menyediakan metadata kandidat `ids`, `complete`, `truncated`,
`lag_seconds`, `semantics`, `usable`, `reason`. Halaman kandidat penuh pada cap
5000 atau estimasi melebihi hasil memicu fallback Mongo; checkpoint belum lengkap,
gagal, atau lebih tua300detik juga fallback. Seluruh konsumen lama menerima None
untuk fallback sehingga list/count/export tidak menganggap subset kandidat total
lengkap. Prefix opt-in memiliki konsistensi eventual yang ditunjukkan lag;
Mongo tetap menegakkan scope dan filter akhir.

Penyelarasan menggunakan tiga phase bounded: dokumen legacy tanpa waktu, cursor
`(updated_at,id)` dan rekonsiliasi deletion. Tiap cycle mengulang sumber, sehingga
perubahan dengan timestamp sama di belakang cursor dicakup cycle berikutnya.
Checkpoint timestamp-only lama di-reset ke cycle bounded schema2. Lease Mongo
120detik dan owner fencing mencegah dua worker memajukan checkpoint yang sama;
lease diperpanjang tiap checkpoint, crash menunggu expiry. Mutasi Meili menunggu
status task `succeeded`; HTTP202 tidak diartikan selesai. Gagal task atau timeout
mempertahankan cursor dan retry idempoten. Rekonsiliasi indeks membaca ID perpage,
menghapus yang tidak ada di Mongo, tidak memajukan offset ketika deletion menggeser
page. Full reindex menghapus isi lama setelah taskack dan membangun perbatch,
dengan search fallback selama rebuild/cycle verifikasi.

Bukti Mongo nyata: 2001/4001dokumen timestamp sama diproses tanpa kehilangan; HTTP
submission sukses/task gagal tidak memajukan cursor; lease kedua ditolak;
penghapusan tanpa hook dan edit bertimestamp sama dipulihkan. Explain query
cursor memakai index `(updated_at,id)` dan memeriksa maksimal2000dokumen untuk
page2000. Engine HTTP/task disimulasikan deterministik, database/cursor/lease nyata.
Cap5000/5001 dan semantik literal diuji melalui adapter fallback serta HTTP list/statistik dengan kecocokan di luar kandidat dan data satker asing; Meili server
nyata tidak diprovision, sehingga tidak ada klaim benchmark engine produksi.

Rollback: hilangkan opt-in/credential untuk Mongo. Pertahankan state checkpoint;
tidak mengubah sumber aset. Indeks cursor sumber assets/surat/persediaan dicatat
pada `indexes.py`; index `_id` bawaan menjaga singleton checkpoint per koleksi.

Sesudah restore atau rollback, `invalidate_after_restore()` wajib di-await sebelum
gate dibuka: flag durable `force_mongo` memaksa fallback, mereset cursor dan
mencabut owner lama. Siklus biasa tidak menghapus flag ini; hanya reindex penuh
yang acknowledged dapat membukanya, lalu masih menunggu cycle verifikasi.
Kontrak Mongo menguji flag tetap berlaku meskipun background complete=true.
Batas konfigurasi kandidat maksimum10000untuk mencegah `$in` tak berbatas.
Taskack unit juga membuktikan processing→succeeded, failed setelah HTTP sukses,
dan existing-index yang dilaporkan sebagai task error tetap menerapkan settings.
