# SIMAN setelah pembaruan PyMongo

Validasi 15 Oktober 2026 menggunakan lingkungan final
`security-runtime-a` (PyMongo 4.19.0, mongomock 4.3.0).

Lima uji endpoint lama gagal karena PyMongo meneruskan `sort=None` ke builder
bulk mongomock yang belum menerima parameter itu. Produksi tidak diubah.
Fixture unit `mongomock_update_sort_compat` hanya membuang opsi `sort=None`,
lalu mendelegasikan seluruh selector, update operator dan upsert ke builder
asli. Nilai sort yang benar-benar diberikan tetap menghasilkan galat eksplisit.
Fixture bersifat opt-in pada uji SIMAN, bukan patch global seluruh suite.

Perintah unit:

```sh
/workspace/.aman/security-runtime-a/bin/python -m pytest \
  backend/tests/unit/test_siman_import_endpoint.py \
  backend/tests/unit/test_mongomock_bulk_compat.py -q
```

Hasil: **10 lulus, 4,77 detik**. Di samping delapan uji endpoint, adapter
diuji untuk filter yang tidak cocok, `$inc`, `$set`, `$setOnInsert`, upsert
dan penolakan sort yang tidak didukung.

Kontrak terpisah memanggil endpoint multipart melalui ASGI dengan MongoDB
nyata, tanpa fixture kompatibilitas mongomock:

```sh
AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 \
AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
XDG_CACHE_HOME=/workspace/.cache XDG_DATA_HOME=/workspace/.local/share \
/workspace/.aman/security-runtime-a/bin/python -m pytest -m integration \
  backend/tests/contract/test_siman_import.py -q
```

Hasil: **1 lulus, 20,74 detik**, exit 0. Dua impor berturut-turut membuktikan
versi aset bertambah tepat sekali per impor, kode register diadopsi, aset
yang hilang ditandai, aset satker lain tetap utuh, referensi masa manfaat
baru di-upsert tanpa duplikasi dan mempertahankan `created_at`, serta
referensi manual tidak ditimpa. Riwayat impor tersimpan dengan scope satker
yang benar. Fixture hanya memakai database lokal acak `aman_ci_*` yang
dihapus setelah pengujian. Empat peringatan deprecation `on_event` FastAPI
masih tercatat; tidak mengubah hasil kontrak.
