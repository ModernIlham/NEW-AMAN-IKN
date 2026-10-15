# OPT-26a — Budget media server dan bentuk legacy yang aman dibaca

Batas media baru ditegakkan sebelum GridFS/staging pada CREATE, PUT, PATCH dan
transformasi batch:50 item checklist/aset,3 foto dan1 PDF/item,6 foto utama.
Foto maksimal5 MiB byte asli, PDF8 MiB; encoding base64 valid dan magic
JPEG/PNG/GIF/WebP atau `%PDF-` diperiksa server. Nama≤200 karakter, catatan≤4000,
checked harus boolean; metadata objek tidak boleh menyamar sebagai teks.
Ukuran BSON checklist maksimal12 MiB dan aset14 MiB. Karena base64 menambah
ukuran, satu PDF8 MiB tidak menjamin semua tambahan item masih muat budget total.
Pesan413 meminta mengurangi lampiran; input rusak/referensi asing400.

Body mutasi aset dibatasi14 MiB sebelum JSON parsing, termasuk transfer chunked.
Maksimal4 mutasi aset aktif per proses; kelebihan429+Retry-After1 tanpa antrean
buffer tak berbatas. Slot dilepas sesudah route/response atau error/disconnect.
Angka ini membatasi parser aplikasi; proxy/body buffer upstream tetap perlu
memiliki konfigurasi yang sepadan. Pembatas tidak mengklaim RSS tepat56 MiB,
karena parsing, decoded media dan dokumen DB menambah alokasi terbatas lain.

Media legacy di atas limit baru dapat dibaca/dipertahankan saat reorder/uncheck
atau edit scalar, selama jumlah/media tidak bertambah. Allowance metadata4096
byte tidak boleh dipakai untuk pertumbuhan media sedikit demi sedikit; hard
safety BSON16 MiB−64 KiB tetap berlaku bahkan untuk legacy. PUT yang tidak
mengirim checklist mempertahankannya; `[]` eksplisit menghapus daftar. Sentinel
`__existing__:N` memakai normalizer yang sama dengan writer dan menjaga byte
asli PDF bertanda tangan. Referensi foto/PDF diverifikasi terpisah terhadap
kepemilikan aset asli; ref PDF tidak dapat digunakan sebagai foto atau sebaliknya.
Slot kosong hanya sah ketika ref foto owned/staged pada indeks yang sama.

Validasi akhir dilakukan setelah revision/version/marker batch terbentuk, sebelum
CAS. Gagal sebelum dispatch atau CASmiss terkonfirmasi dapat membersihkan blob baru.
Sesudah dispatch dengan hasil tidak diketahui, semua blob baru dipertahankan;
pembacaan referensi kosong tidak dianggap bukti bahwa operasi in-flight tidak
akan commit kemudian.
Referensi dihapus dari checklist tidak langsung dihapus fisik: accounting/GC
merupakan paket26b/c terpisah, dengan default write flag off.

Projection list/snapshot/CSV memakai `$isArray` sebelum map/size agar legacy
string/nonarray tidak menggagalkan seluruh daftar. CSV/XLSX toleran terhadap
item/nonlist dokumen lama; posisi item tetap dipertahankan untuk URL lampiran.
Dual-reader penuh/ref dan adapter GridFS ditangani pada hasil26b; paket26a tidak
melakukan migrasi atau purge inline produksi.

Histogram `histogram-sintetis-50k.json` berisi50.000 aset fixture: min1543,
max22131, rata-rata3696,11 byte; checklist maksimum201 byte. Distribusi BSON:
31614 row1–4 KiB,18329 row4–16 KiB,57 row16–64 KiB. Foto fixture kecil;
ini **bukan** distribusi media produksi, tidak membenarkan pembersihan/backfill
langsung, dan tidak mengklaim dampak heap produksi.

Verifikasi fokus:10 unit validator/body/admission serta6 guard profiler lulus.
Kontrak Mongo nyata mencakup penolakan jumlah sebelum blob commit, forged refs,
main photos7 ditolak, PDF signed byte-for-byte tetap sesudah sentinel/reorder/
uncheck dan PUT omission, serta legacy checklist/photo/document nonarray tetap
berhasil dibaca lewat list/snapshot/CSV. Pengujian flag-on ownership/hash/CAS/
backup-roundtrip dicatat oleh paket26b; aktivasi produksi menunggu semua jalur
consumer dan cleanup terbukti aman.

Frontend menampilkan batas ringkas pada checklist tunggal dan ubah massal;
PDF hasil kompresi di atas8 MiB ditolak sebelum masuk draft. Validasi server
foto5 MiB tetap otoritatif. Run gabungan32 kontrak data/limit lulus11,88 detik;
verifikasi flag-on26b dicatat terpisah oleh pemilik adapter.

## Balasan Mongo hilang setelah commit foto utama

Review lanjutan menemukan CREATE/PUT/PATCH foto utama menghapus blob baru ketika
operasi Mongo melempar exception, walaupun tulisan mungkin sudah diterapkan.
`asset_photo_commit.py` kini mencatat owner_asset_id/state pending pada metadata
fs.files sebelum CAS. Cleanup hanya boleh dipanggil untuk kegagalan predispatch atau penolakan CAS
terkonfirmasi, lalu memerlukan proof pemilik cocok dan pembacaan referensi
terkini yang menyatakan blob tidak digunakan (termasuk aset lain/checklist).
Read gagal/pemilik berbeda berarti bytes dipertahankan. Generic exception atau
cancellation sesudah dispatch tidak menjalankan cleanup, sekalipun immediate
read belum melihat referensi.
Success menandai committed best-effort, penghapusan foto lama tetap sesudah CAS
terkonfirmasi. Balasan hilang meninggalkan pending+referenced sebagai ledger
konservatif. Tidak ada TTL, purge, atau GC otomatis yang ditambahkan.

Tiga belas kontrak Mongo+GridFS nyata mencakup tiga writer dengan commit
sudah-visible, server commit tertunda hingga setelah respons exception, dan
cancellation saat write masih in-flight; refs/byte penuh tetap identik.
Persistent writer lease ditandai uncertain_write melalui shared ContextVar
sebelum middleware selesai, sehingga restore/reset/deploy tidak melewati writer
yang hasilnya belum pasti. Test menunggu future server sintetis benar-benar
selesai sebelum membersihkan lease fixture sendiri; produksi tidak memakai
negative-read untuk menghapus ketidakpastian.

PUT/PATCH CASmiss409 membersihkan hanya blob baru dan tidak menghapus foto lama;
DBunknown/wrong-owner mempertahankan bytes+pending ledger. Gagal prepare
checklist setelah upload mainphoto membersihkan mainphoto terdaftar sebelum
CAS; metadata ownership ditulis lebih awal sebelum await persiapan lanjutan.
Legacy cover regression tetap memeriksa byte lama, clean precommit/CASmiss dan
retensi pending untuk galat setelah dispatch. State pending sendiri tidak
pernah menjadi izin hapus. Tidak ada GC/purge otomatis yang ditambahkan.

Verifikasi setelah review independen:50 kontrak data Mongo+Redis lulus24,34 detik,
termasuk13 photo-commit,10 geo renderer boundary dan legacy CSV/XLSX sungguhan.
CSV null/nonarray main-photo count dihitung typed di projection; builder XLSX
menggunakan safe_checklist sebelum loop manual. Unit lintas domain/Meili/stats/
limit/profiler/G3/cover/geo/pure render:118 lulus9,75 detik. `git diff --check`
bersih; runtime dan test source dibekukan untuk gate snapshot koordinator.
