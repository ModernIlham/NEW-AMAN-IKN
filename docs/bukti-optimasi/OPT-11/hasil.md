# OPT-11 — Harga numerik dan batas eksak

Selesai pada reader tanpa migrasi nilai resmi. Daftar menggunakan konversi
Decimal128 sementara sebelum sort, laporan menggunakan parser Decimal128 yang
sama domainnya. Tie tetap `id` ascending untuk kedua arah. Batas harga API dan
geo export diterima sebagai Decimal, bukan float. Filter nol bersifat eksplisit;
minimum melebihi maksimum ditolak HTTP400. Reader tidak lagi membuat batas atas
buatan 999999999999 ketika pengguna hanya mengisi minimum.

Domain: angka desimal basis10 hingga 34 digit signifikan, termasuk nilai negatif
historis dan notasi eksponen; null, kosong, nonfinite, format rupiah, nilai di luar
Decimal128 dan teks invalid diperlakukan nol. String resmi tidak diubah. Angka
BSON double mengikuti presisi yang sudah tersimpan; string besar tetap eksak.
Parser filter laporan mempertahankan kompatibilitas lama: isian bukan angka
diabaikan; angka sah memakai Decimal dan min>max tetap ditolak.

Writer tetap: CRUD/draft/PATCH/rotasi media `routes/assets.py`, `routes/batch.py`,
`routes/imports.py`, `routes/siman.py`, alur transfer pada registry transaksi,
dan restore `routes/backup.py`/`backup_utils.py`. Tidak ada dual-write/backfill;
reader mixed schema mencakup semua jalur tersebut tanpa perubahan version.

Validasi:

- `test_numeric_price_contract.py`: domain kosong/invalid/negatif, 2/10/100,
  tie, dua arah, batas0, min>max, filter laporan besar eksak.
- Kontrak Mongo nyata `test_numeric_search_sync.py`: daftar HTTP dan sort Mongo
  sama dengan urutan laporan; `9007199254740992.01` dan `.02` tetap terpisah,
  batas sama memilih hanya satu baris. Mongo35digit/subnormal yang biasanya
  dibulatkan dicegah sebelum konversi:35digit nonzero/1.1e-6176 menjadi0,
  34digit dan35digit trailing-zero yang eksak tetap sah. Lingkup satker ditegakkan endpoint lama.
- 109 unit regresi filter/PDF/Meili lulus sebelum tambahan domain; suite domain
  dan regresi filter dijalankan ulang setelah kompatibilitas parser dipertahankan.
- Parity luring dikerjakan bersama paket frontend; bukti terpisah pada PR sama.

Biaya: `$convert`/sort computed bukan pemanfaatan indeks harga lama. Field turunan
hanya dipertimbangkan setelah hasil beban OPT-16/18; tidak mengklaim peningkatan
latensi dari koreksi ini. Rollback writer tidak diperlukan, karena schema resmi
tetap; jangan mengembalikan reader leksikal.

## Konsistensi snapshot frontend

`hargaEksak.js` membandingkan sign/coefficient/exponent desimal tanpa konversi
harga menjadi Number. Sesuai reader Decimal128: maksimum 34 digit signifikan,
trailing zero dapat dinormalisasi, exponent minimum -6176, adjusted exponent
maksimum 6144; invalid/null/empty/nonfinite/bool menjadi nol. Nilai negatif
historis tetap negatif. `querySnapshotAset.js` dipakai dashboard untuk filter
batas dan pengurutan snapshot, termasuk nol eksplisit dan tie ID ascending di
kedua arah harga. Array input tidak dimutasi.

Tes frontend: harga besar `9007199254740992.01` dan `.02`, batas negatif/nol,
34/35 digit, scientific notation, rentang Decimal128, trailing zero dan urutan
stabil dengan ID. `hargaEksak.test.js`: 26 tes lulus. Run bersama OPT-04:
4 suite / 42 tes lulus (`/tmp/aman-opt04-11-tests.log`).

## Agregasi nonfinite dan nilai di luar rentang JSON float

Seed50k mixed-schema menemukan `NaN` historis yang lolos `$convert` double dan
membuat stats/activity HTTP500 saat JSON encoding. Statistik/analytics/activity
list dan linked create kini menjumlah dengan ekspresi finite Decimal yang sama.
Respons menambah `total_value_exact`/`value_exact`; nilai biasa tetap JSON number,
nilai sah seperti1e6144 menjadi string desimal eksak (tidak Infinity). Overflow
agregat/renderer float ditolak413 eksplisit. Adapter monetary di laporan, kartu,
CSV/export dan LBP memakai parser domain yang sama agar NaN tidak masuk PDF.
Cache stats/analytics berpindah prefix finite2 untuk menghindari payload lama.
Dua kontrak HTTP Mongo nyata menguji BSON/string NaN/Infinity→0, agregat valid,
activity list/detail/create+rekap, dan nilai1e6144 tanpa JSON nonfinite. Smoke
runtime10k setelah perbaikan dikonfirmasi200 oleh koordinator; bukti beban
terpisah pada OPT-16 dan bukan klaim kapasitas produksi.

Agregat Python linked-create juga diperiksa kembali ke domain Decimal128 sesudah
penjumlahan34 digit: dua nilai9e6144 menghasilkan413, konsisten dengan Mongo,
sebelum kegiatan baru tersimpan. Detail kegiatan memakai total_value_exact yang
sudah disimpan, sehingga display float tidak memangkas pecahan nilai besar.
Kontrak GET detail dan overflow keduanya lulus dalam run data32 tes terakhir.

Nilai nonzero1e-6176 yang underflow ke float0 juga dikirim sebagai exactstring;
source invalid tetap0. Kontrak finite empat kasus lulus10,29 detik sesudah
penambahan parametrik overflow/underflow JSON. Run gabungan sebelumnya32 lulus;
case tambahan membuat total33 untuk gate penuh koordinator.
