# OPT-23 — Batas form dan kontrak scalar

Validasi lokal 15 Oktober 2026. Perubahan ini memindahkan logika mekanis;
tidak mengganti state/form library dan tidak mengklaim percepatan render.

`frontend/src/lib/assetFormData.js` menyediakan `emptyAssetForm`,
`buildEditFormData`, dan pure `buildAssetPatch`. AssetForm tetap menjadi façade
untuk validasi, kompresi, pembacaan ref kamera terbaru, antrean, dan navigasi.
Builder tidak melakukan request, membaca storage/ref, atau mengompresi media.
Fallback nilai lama dipertahankan, termasuk perbandingan scalar melalui
`String(value ?? "")`, status inventarisasi otomatis, nullable indeks stiker,
omisi media yang belum dimuat, urutan `keep`, tambahan byte foto, dan
`photo_ops.base_version` untuk OCC. Checklist yang tidak diubah tetap dihilangkan
dari patch; sentinel media lama diteruskan tanpa perubahan.

Registry eksplisit `assetFields.json` memuat 51 field scalar, label, dan default.
Default form, builder patch, dan proyeksi snapshot luring memakai registry ini.
Kontrak Python membandingkan nama serta label ke registry backend yang digunakan
CSV/XLSX. Field contoh `barang_bersejarah` telah diuji melalui checkbox UI,
patch parsial `Ya` serta clear `""`, penyimpanan snapshot IndexedDB, dan API nyata
Mongo → detail → offline snapshot → ekspor CSV. Penambahan field berikutnya harus
melewati kontrak tersebut; tidak ada registry generik untuk semua domain.

Hasil verifikasi:

- 8 suite frontend, **50 test lulus** (19,321 detik): builder, ref kamera,
  form checkbox/resize/hide/tab, jenis operasional, koordinat, BAST, kontrol
  ringkas, dan snapshot luring. Input yang sedang fokus mempertahankan node DOM
  serta nilainya pada resize/hide; perpindahan tab mempertahankan draft.
- **1 test unit Python lulus**: kesetaraan seluruh 51 scalar/label/default.
- **1 test integrasi Mongo/Redis lulus** (6,88 detik): patch/read/offline/CSV,
  termasuk clear eksplisit. Fixture memakai database sintetis terpisah.
- ESLint terfokus pada seluruh berkas form/helper/test yang diubah.

Source guard kamera lama diperbaiki agar membedakan nama properti builder
`photoItems:` dari bacaan identifier state. Uji guard tambahan tetap menolak
`photoItems: photoItems` maupun shorthand `{ photoItems }`, sementara form tetap
membaca ref terbaru sebelum kompresi asynchronous. Source-scan barang bersejarah
yang hanya memeriksa literal diganti dengan uji UI dan API di atas.

Rollback cukup mengembalikan façade/helper ini bersama kontrak registry; tidak
ada migrasi schema. Refactor subform lain tidak diperlukan untuk batas mekanis
ini. Query snapshot, controller batch, service ekspor, dan builder backend
memiliki bukti terpisah pada OPT terkait.

Perbaikan pemilik form desktop/mobile dan bukti browser tampilan yang terlihat: [form-responsif.md](form-responsif.md).

Review visual berikutnya memperbaiki indeks lampiran setelah rekomendasi/reorder;
bukti dan batas smoke sebelumnya: [indeks-media.md](indeks-media.md).
