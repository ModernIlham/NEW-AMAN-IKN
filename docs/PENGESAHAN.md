# Panduan Pengesahan Kegiatan & Kartu Inventarisasi

Panduan singkat untuk operator: alur **tiket → pengesahan → kunci → kartu
inventarisasi**, plus format QR pada kartu cetak aset.

---

## 1. Nomor Tiket Kegiatan

Setiap kegiatan inventarisasi otomatis mendapat **nomor tiket** dengan format:

```
INV-{tahun}-{urutan 4 digit}     contoh: INV-2026-0007
```

- Nomor diberikan saat kegiatan dibuat (kegiatan lama di-backfill otomatis).
- Berurutan per tahun dan dijamin unik (counter atomik di database).
- Tampil di kartu kegiatan (halaman pemilihan kegiatan) dan di header dashboard.
- Nomor tiket menjadi identitas kegiatan pada riwayat pengesahan (kartu
  inventarisasi) dan tidak pernah berubah.

## 2. Syarat Pengesahan

Kegiatan hanya bisa disahkan bila **semua** syarat berikut terpenuhi
(dialog Pengesahan menampilkan tiap syarat sebagai baris merah/hijau):

1. Kegiatan memiliki minimal 1 aset.
2. Semua aset sudah diinventarisasi (tidak ada status "Belum Diinventarisasi").
3. Semua aset memiliki minimal 1 foto.
4. Tidak ada aset yang masih berkategori *dummy*.
5. Semua aset memiliki **kode register**.
6. Semua aset memiliki **Eselon I atau Eselon II**.
7. Semua aset memiliki **lokasi**.
8. Semua aset memiliki **pengguna**.
9. Minimal **1 dokumen pengesahan** (PDF bertanda tangan, maks 20MB) sudah
   diunggah pada dialog Pengesahan.

Bila ada syarat yang belum terpenuhi, tombol "Sahkan" menolak dengan daftar
masalah yang teritemisasi (mis. "3 aset tanpa foto, 1 aset tanpa lokasi").

## 3. Menyahkan Kegiatan (khusus admin)

1. Buka kegiatan → menu **Pengesahan** di header dashboard.
2. Pastikan semua baris syarat hijau.
3. Unggah dokumen pengesahan (PDF hasil scan yang sudah ditandatangani) —
   boleh lebih dari satu; dokumen bisa dihapus selama kegiatan masih draft.
4. Klik **Sahkan**. Sistem akan:
   - mengunci kegiatan (`status_pengesahan = "disahkan"`) secara atomik;
   - menulis **satu record riwayat per aset** ke koleksi `inventory_history`
     (nomor tiket, nama kegiatan, satker, tanggal pengesahan, identitas aset,
     serta snapshot status/kondisi/lokasi/pengguna saat disahkan);
   - mencatat aksi ke audit log (termasuk unggah/hapus dokumen pengesahan).

## 4. Efek Kunci (423)

Setelah disahkan, kegiatan **terkunci permanen** — tidak ada fitur untuk
membatalkan pengesahan. Server menolak semua jalur perubahan dengan
**HTTP 423 "Kegiatan sudah disahkan dan terkunci"**:

- tambah/edit/hapus aset (termasuk PATCH dan unggah BAST);
- batch update dan hapus massal;
- import CSV/XLSX;
- unggah/hapus dokumen pengesahan;
- menghapus kegiatan itu sendiri.

Di frontend: banner "tersegel" dengan nomor tiket tampil, dan tombol
edit/hapus/import/batch/FAB disembunyikan.

**Catatan mode offline**: bila ada perubahan yang mengantri saat offline lalu
kegiatannya keburu disahkan, saat online kembali perubahan itu ditolak 423 —
muncul toast/pesan "Kegiatan sudah disahkan dan terkunci", dan antrian
**tidak** mencoba ulang otomatis. Perubahan tetap tersimpan di perangkat;
operator memutuskan sendiri: **Retry** (manual) atau **Dismiss** (buang).

## 5. Kartu Inventarisasi

Kartu inventarisasi menampilkan **riwayat pengesahan sebuah aset lintas
kegiatan** — setiap kali kegiatan disahkan, aset di dalamnya mendapat satu
baris riwayat.

- **Identitas aset**: prioritas `kode_register`; bila kosong, fallback ke
  pasangan `kode aset + NUP`.
- **Lingkup satker**: riwayat dibatasi pada satuan kerja kegiatan aktif —
  aset dengan identitas kebetulan sama di satker lain tidak ikut tampil.
  Record lama yang ditulis sebelum satker dicatat tetap tampil dan ditandai
  *legacy*.
- **Cara membuka**: dari header form edit aset, atau aksi baris pada tabel
  desktop.

## 6. Format QR pada Kartu Cetak

Kartu identitas aset (KTP aset) yang dicetak memuat QR dengan isi:

```
#{kode_register}          contoh: #3.05.01.05.007.2024.001
```

- Awalan `#` menandakan "cari verbatim sebagai kode register" — scanner
  aplikasi (tombol scan di dashboard, memakai kamera) membuang `#` dan
  mencari sisanya apa adanya, tanpa heuristik.
- Bila aset belum punya kode register, QR berisi `#{kode aset}-{NUP}`.
- QR/barcode lain (kode mentah, `kode|NUP`, URL) tetap didukung scanner
  lewat heuristik token — tetapi format `#...` adalah yang paling andal.

---

*Dokumen ini merangkum perilaku fitur PR #27–#28 — detail teknis di
`CHANGELOG.md` dan kode `backend/routes/pengesahan.py`.*
