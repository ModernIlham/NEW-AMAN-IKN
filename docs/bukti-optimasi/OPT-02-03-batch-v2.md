# OPT-02 / OPT-03: batch CAS dan operasi tahan retry

Implementasi berada pada `backend/batch_operations.py` dan rute additive
`backend/routes/batch.py`. Batas ini berlaku untuk protokol `batch_v2`; rute
`PUT /assets/batch-update` dipertahankan khusus kompatibilitas tab lama dan tidak
menerima kontrak hasil parsial baru secara diam-diam. Klien OPT-04 menggunakan
protokol baru, preflight, admission, dan resume.

## Kontrak API

Semua rute memerlukan `require_writer`. Identitas diambil dari akun terautentikasi,
bukan `X-User-Id`, `X-User-Name`, atau token Bearer yang disalin ke ledger.

1. `POST /api/assets/batch-v2/preflight` menerima `{asset_ids}` dan mengembalikan
   `dataset_generation`, batas, serta `targets:[{id,version,status:"ready"}]`.
   Aset yang hilang memiliki `status:"missing"`; ID dideduplikasi. Versi preflight
   dipertahankan sampai write, bukan dibaca ulang sebagai persetujuan baru.
2. `POST /api/assets/batch-v2/prepare` menerima payload write di bawah, menyimpan
   request immutable, dan mengembalikan hasil `pending` tanpa mengubah aset.
   Klien mendaftarkan seluruh child operation sebelum menjalankan child pertama.
3. `PUT /api/assets/batch-v2` menerima
   `{operation_id,dataset_generation,asset_ids,expected_versions,updates}`.
   Versi wajib untuk setiap ID unik, termasuk nilai 1 bagi target yang sudah
   hilang sejak preflight. Payload scalar/foto/checklist divalidasi sebelum admission.
4. `GET /api/assets/batch-v2/{operation_id}` mengembalikan status dan merekonsiliasi
   receipt dari bukti aset. Hanya owner dan satker efektif yang sama dapat membaca.
5. `POST /api/assets/batch-v2/{operation_id}/resume` memakai request immutable di
   server; browser cukup menyimpan identitas dan metadata checkpoint.

Hasil mencakup `requested_unique`, `applied`, `unchanged`, `conflicts`, `missing`,
`failed`, `pending`, `updated`, serta `results` per ID dengan `status`, versi hasil,
dan alasan bila diperlukan. `updated = applied + unchanged`: jumlah ID yang
benar-benar diproses dengan sukses. `unchanged` tidak menaikkan versi. Status
operasi adalah `running`, `partial`, atau `completed`. Kegagalan sementara bertanda
`retryable:true` dapat dilanjutkan dengan identitas yang sama; konflik memerlukan
rekonsiliasi pengguna dan preflight tindakan baru.

## Identitas, horizon, dan batas

- ID berbentuk `b2_<Unix-milliseconds>_<UUID-v4>`, misalnya dibuat dengan
  `` `b2_${Date.now()}_${crypto.randomUUID()}` ``. Timestamp merupakan bagian ID;
  key lama tidak dapat diperbarui umurnya dengan mengubah field waktu request.
- Horizon replay **7 hari**, toleransi waktu perangkat di masa depan **5 menit**.
  API menolak key kedaluwarsa dengan 409 `operation_expired`, termasuk pembacaan
  operasionalnya. Rekonsiliasi administratif memakai receipt yang masih disimpan;
  jangan membuat key pengganti untuk mengirim ulang hasil yang belum diketahui.
- Receipt disimpan **30 hari** melalui TTL `expires_at`; timestamp key tetap
  mencegah admission ulang setelah receipt dibersihkan.
- Maksimal **200 ID unik** per child operation, **8 MiB** JSON kanonik, **6 foto**,
  dan **50 item checklist**. Seleksi 401/501 dipartisi menjadi child operation
  stabil oleh klien. Menghapus semua dan menambah media yang sama sekaligus ditolak.
- Tiap aset menyimpan maksimal **128 bukti** yang masih berada dalam horizon.
  Bukti sah tidak pernah dieviksikan untuk menerima operasi baru. Batas tercapai
  menghasilkan kegagalan eksplisit `proof_budget_exceeded`; tidak ada overwrite.
  Bukti lama diselesaikan audit/jurnalnya sebelum dipangkas, termasuk bila TTL
  receipt sudah berakhir.

## Sifat atomik dan kompensasi

Scalar, referensi foto, checklist, koordinat turunan, cap inventarisasi, versi,
dan `_batch_applications` ditulis dalam **satu CAS per aset**. CAS juga membawa
`_batch_revision` supaya dua operasi `unchanged` tidak saling membuang bukti.
Dokumen legacy tanpa versi memakai versi logis 1 dan commit pertama menjadi 2.
Tidak ada klaim bahwa seluruh batch merupakan satu transaksi all-or-nothing.

Blob baru dicatat dan dibersihkan ketika unggah gagal atau CAS terbukti kalah.
Referensi lama diganti dulu; blob lama dilepas sesudah commit. Bila pengakuan
write hilang, server membaca bukti sebelum membersihkan blob. Pembacaan yang juga
gagal meninggalkan kemungkinan orphan yang aman; byte yang mungkin sudah
direferensikan tidak dihapus berdasarkan tebakan.

Lease operasi mengurangi worker ganda; kebenaran tetap dijaga bukti pada CAS aset,
bukan lease atau receipt terpisah. Audit dan jurnal memakai `_id` deterministik
per operasi/aset melalui upsert. Crash setelah CAS sebelum receipt dapat dipulihkan,
termasuk ketika operasi lain sudah mengubah aset setelahnya. Rekonsiliasi juga
memperbaiki invalidasi cache dan menjadwalkan ulang sinkronisasi indeks pencarian.
Lock hidup diperiksa untuk **seluruh ukuran** batch_v2, bukan hanya <=50 target.

## Penghapusan dan restore

Single delete memanggil `reconcile_before_asset_delete()` lalu `cas_filter()`.
CAS menyertakan `_id` Mongo dari snapshot selain semantic ID, version dan proof
revision. Aset yang dihapus lalu dibuat ulang dengan ID/version sama tidak dapat
ditulis atau dihapus oleh snapshot lama.
`asset_deletion.delete_activity_assets()` dipakai kedua pintu penghapusan massal:
rekonsiliasi bukti → CAS delete aset → cleanup media dari snapshot yang tersimpan.
Konflik mempertahankan aset dan medianya. Penghapusan kegiatan mempertahankan
parent dan dokumen kegiatan bila child berubah; dokumen parent dilepas setelah
parent delete berhasil. Audit intent ditulis sebelum penghapusan dimulai.

`dataset_state` dan `batch_operations` merupakan kontrol lokal yang dikecualikan
dari backup/restore/reset. Restore/rollback mengubah generasi sebelum tulisan
destruktif. Operasi generasi lama ditolak dengan 409 `dataset_changed`. Request
batch berjalan dalam lifetime HTTP dan mengikuti barrier writer/drain restore;
tidak ada mutasi batch yang dilepas sebagai BackgroundTask. Sebelum CAS, worker
memperbarui lease dan memeriksa generasi lagi setelah fase unggah.

Konsistensi penghapusan parent beserta seluruh child bukan transaksi lintas
dokumen. CAS menjaga bukti/media child; koordinasi penciptaan child baru dengan
penghapusan parent memerlukan admission kegiatan tersendiri bila kasus itu
diizinkan berbarengan. Optimasi ini tidak menjanjikan atomicity lintas koleksi.

## Bukti pengujian

- `backend/tests/unit/test_batch_operations_v2.py`: autentikasi handler, preflight,
  duplikat/hilang/unchanged, 51/200 lock hidup, 201 ditolak, versi legacy,
  scalar+foto+checklist atomik, gagal unggah/kompensasi, konflik media concurrent,
  crash sebelum receipt setelah CAS, operasi lain menyela lalu retry,
  penghapusan proof setelah receipt dipersist, owner/satker/payload mismatch,
  generasi berubah, horizon habis, batas marker, pruning audit/jurnal, prepare/resume.
- `backend/tests/unit/test_hapus_massal_cascade.py`: kedua pintu, audit intent dan
  media sebelum CAS masih utuh, cleanup setelah delete, konflik mempertahankan
  parent/media, serta receipt dipulihkan sebelum proof dihapus. Pemeriksaan perilaku
  menggantikan asumsi source-string `delete_many` lama.
- `backend/tests/contract/test_batch_v2.py`: **9 tes lulus pada MongoDB/GridFS/Redis
  lokal nyata**, lewat API terautentikasi: foto riil, CAS stale, dua request pada ID
  sama, owner/satker, prepare tanpa mutasi, crash → single/bulk/activity delete →
  resume tanpa foto/jurnal ganda. Fixture hanya mengizinkan host loopback dan nama
  database sintetis `aman_ci_<UUID>`; teardown hanya menghapus DB tersebut.
- Validasi BSON terakhir mencakup marker aplikasi/audit sebelum CAS. Bila satu
  target melampaui ukuran atau lampiran invalid, target tersebut mendapat hasil
  `failed`, `retryable=false` dengan reason `asset_payload_too_large`/`invalid_media`.
  Target lain tetap tercatat tepat; blob baru target ditolak dibersihkan. Resume
  memakai receipt permanen ini tanpa unggah ulang yang terus gagal.
- Race Mongo nyata mengganti dokumen dengan `_id` baru tetapi semantic ID/version
  sama, termasuk saat batch sudah membaca snapshot; CAS lama tidak cocok dan
  replacement tetap utuh.

Perintah kontrak:

```bash
AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 \
AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
.venv/bin/python -m pytest -m integration backend/tests/contract/test_batch_v2.py -q
```

Rollback writer tidak boleh menghapus receipt/proof aktif. Hentikan admission
batch_v2 baru, pertahankan pembacaan status dan resume, lalu drain/reconcile sampai
horizon berakhir. UI rollback tidak boleh mengganti operasi yang statusnya belum
diketahui dengan operasi baru atau membuang checkpoint aktif.
