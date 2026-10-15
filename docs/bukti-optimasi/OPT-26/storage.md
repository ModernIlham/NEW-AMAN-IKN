# OPT-26b — adapter checklist, kompatibilitas, dan migrasi terbatas

Implementasi di checklist_storage.py memahami data inline lama dan referensi
GridFS milik aset yang sama. Item dan dokumen mendapat ID stabil ketika field
checklist benar-benar ditulis; rename/reorder dengan ID mempertahankan identitas.
Klien lama tanpa ID masih didukung melalui antrean nama, termasuk nama duplikat.
Referensi foto dan foto inline berbagi posisi sehingga tambah foto sesudah data
refs-only tidak mengganti foto pertama.

Flag AMAN_CHECKLIST_GRIDFS_WRITE **mati secara default**. Saat dinyalakan di
staging, CREATE/PUT/PATCH/batch memakai adapter yang sama. Alokasi baru memuat
owner asset/item/file/kind dan SHA-256; setiap blob dibaca kembali dan diverifikasi
sebelum CAS aset. Dokumen PDF ditulis byte-identik, termasuk PDF bertanda tangan.
Dokumen yang mengirim ID lama beserta bytes baru tetap melewati validasi upload
baru; ID lama bukan izin untuk meloloskan isi baru.

GET penuh tetap menghidrasi inline untuk konsumen lama. GET exclude_media,
media, checklist-full, list/offline dan CSV/XLSX memakai jumlah foto inline/ref
yang benar; checklist-full tetap mengirim metadata/thumbnail. Kedua keluarga URL
foto/PDF memeriksa akses satker dan owner blob. Respons PDF mempertahankan bytes,
nosniff, ETag versi, dan nama UTF-8 aman.

Kompensasi hanya dilakukan sebelum dispatch atau setelah penolakan/CAS miss
yang diakui server. Write yang sudah dikirim tanpa acknowledgement mempertahankan
seluruh bytes, termasuk ketika pembacaan sesaat belum menemukan referensi:
operasi Mongo mungkin masih in-flight. Bukti commit positif boleh direkonsiliasi.
Admission writer yang tidak pasti dipertahankan tanpa TTL setelah respons,
sehingga restore/deploy tidak dapat melewati operasi server yang belum pasti.
Jalur operator OPT-06 memerlukan penghentian penulis dan verifikasi outcome
Mongo sebelum release eksplisit; pembacaan negatif tidak melepaskan lease.
Batch proof/receipt dan identitas operasi tetap
menjadi otoritas replay sehingga resume tidak menambah blob atau versi lagi.
Optimisasi inline lama melewati slot yang sudah memiliki referensi supaya dua
salinan tidak menyimpang.

## Backfill operator

Jalankan dari backend dengan konfigurasi instalasi yang benar:

    python checklist_storage_cli.py backfill --asset-id ID
    python checklist_storage_cli.py backfill --asset-id ID --apply

Perintah pertama dry-run. Setiap panggilan membatasi 1–25 ID eksplisit, memegang
writer admission, memeriksa epoch, dan memakai CAS versi + BSON checklist asal.
Backfill selalu mempertahankan seluruh inline; tidak ada opsi purge. Kegagalan
atau perubahan bersamaan tidak menimpa aset. Tidak ada backfill produksi yang
dijalankan sebagai bagian pekerjaan ini.

    python checklist_storage_cli.py audit-orphans --grace-days 7 --limit 100

Audit selalu read-only, membatasi kandidat dan dokumen yang dipindai. Semua
koleksi pemilik, termasuk modul tak dikenal dan riwayat, diperiksa konservatif.
Scan yang terpotong tidak menyatakan blob layak dihapus. Penghapusan aset untuk
blob managed menulis retirement; bytes dipertahankan. Kandidat baru masuk
pertimbangan operator setelah upload dan retirement lewat grace minimal tujuh
hari, serta tidak ada pemilik. Blob tanpa retirement tetap bukan kandidat
penghapusan meski tidak dirujuk. Tidak ada API/perintah broad GC delete.

## Bukti

- Unit storage/fault injection: owner mismatch, hash korup, exact signed PDF,
  staging parsial, commit ambigu, CAS kalah, backfill dry-run, semua riwayat
  pemilik, grace, dan scan tak lengkap.
- Payload PDF sintetis 2 MiB menghasilkan BSON checklist kurang dari 1% ukuran
  inline dan bytes asli identik. Ini membuktikan batas dokumen, bukan klaim
  throughput produksi.
- Suite unit storage + batch: 37 passed, termasuk konteks inner-task,
  kegagalan metadata uncertainty, dan validasi sebelum dispatch yang tetap
  melepas admission normal.
- Suite Mongo/GridFS nyata checklist + batch_v2 + limit: 25 passed. Meliputi
  flag-on CRUD, echo PUT klien lama, sentinel PATCH, isolasi dua satker, CSV
  photo links, CREATE/PUT/PATCH commit-then-raise, batch refs-only append,
  CAS miss, lost reply, late/in-flight commit batch/backfill, dan resume proof
  yang sama. Late commit dijalankan setelah pemeriksaan ownership negatif,
  sehingga pengujian tidak hanya mengandalkan commit-then-raise yang sudah tampak.
- Backup ZIP actual Mongo/GridFS lolos manifest/ref preflight, diimpor ke
  database pengujian lain, kemudian foto dan signed PDF dibaca byte-identik.
- Tidak ada flag produksi yang diaktifkan atau inline yang dipurge.

Aktivasi produksi tetap menunggu bukti staging pada batas lampiran nyata dan
pemeriksaan konsumen aplikasi yang dirilis. Runtime kompatibel dengan flag mati,
sehingga tahap penerapan kode tidak memaksakan migrasi data.
