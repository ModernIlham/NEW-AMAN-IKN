# OPT-27 — Tombstone tidak terpotong senyap

Delta snapshot membaca maksimal10001audit delete. Bila lebih10000,
`requires_full_refresh=true` dan `deleted_ids=[]` sehingga tidak ada daftar
terpotong yang terlihat lengkap. Bulk delete tetap mengharuskan full refresh.
Scope kegiatan tetap sama dan akses kegiatan diperiksa sebelum query. Tidak ada
perubahan schema/watermark atau penghapusan pending write/draf browser.

Kontrak Mongo/HTTP nyata membuktikan 9999 dan10000single delete dikembalikan
lengkap;10001mengharuskan full refresh. Bulkdelete kegiatan asing tidak memicu
refresh pada kegiatan yang sedang diuji. Klien menggunakan protokol full-refresh
yang sudah ada; uji quota/interrupted sync lama tetap menjadi regresi frontend.

Rollback kode tidak menghapus snapshot lokal; reader lama tidak dianjurkan karena
menghidupkan kehilangan tombstone. Tidak perlu migrasi data.
