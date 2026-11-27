# Lapisan Eksisting pada Peta

Peta dasar OpenStreetMap di kawasan yang sedang dibangun tertinggal dari kondisi
lapangan. Lapisan eksisting menumpangkan dua hal di atasnya, dan bisa ditampilkan
atau disembunyikan kapan saja:

- **Citra**: foto udara terbaru (GeoTIFF drone/ortofoto).
- **Gambar**: titik, garis, dan area yang digambar langsung di peta, lengkap dengan
  warna, tebal, opasitas, dan label.

## Cara pakai (admin)

**Hierarki Spasial → Lapisan Eksisting.**

1. **Unggah citra** → pilih berkas `.tif`. Lokasi, resolusi, rentang zoom, dan tanggal
   rekam terbaca otomatis dari berkasnya. Tekan **Unggah**, lalu biarkan halaman
   terbuka sampai selesai.
2. **Gambar baru** → beri nama → editor terbuka di atas citra. Pakai tombol di kiri
   peta untuk menggambar titik, garis, atau area. Ketuk objek untuk mengatur warna,
   tebal, opasitas, putus-putus, warna isi, dan labelnya (teks, warna, ukuran, tebal,
   garis tepi, posisi).
3. **Urutan**: tombol ▲/▼ per jenis; yang di atas tampil paling depan. Gambar selalu
   di atas citra.
4. **Sakelar** menampilkan/menyembunyikan lapisan untuk semua pengguna.

Pengguna menyalakan lapisan lewat tombol **Eksisting** di Peta Aset, atau tombol
satelit di Peta Kolaborasi, Editor Denah, dan Lokasi Temuan.

## Berkas citra yang diterima

GeoTIFF dengan sistem koordinat:

- **UTM WGS84** (EPSG:32601–32660 / 32701–32760). Contoh: kawasan IKN = EPSG:32750 (UTM 50S).
- **WGS84 geografis** (EPSG:4326).
- **Web Mercator** (EPSG:3857).

Sistem lain (mis. DGN95 / TM-3) ditolak dengan pesan yang jelas. Ekspor ulang dari
QGIS/WebODM ke salah satu di atas. RGB 8-bit, dengan atau tanpa band alfa; piksel
NoData menjadi transparan.

Batas satu citra adalah **60.000 ubin**. Bila lebih, zoom maksimum diturunkan
otomatis (resolusi dikorbankan, wilayahnya tidak). Sebagai gambaran, citra 5 cm
seluas 5×5 km menjadi zoom 20 (±15 cm per piksel di layar).

## Cara kerjanya

| Bagian | Lokasi |
|---|---|
| Registri, unggah & sajikan ubin | `backend/routes/peta_lapisan.py`, validasi `backend/peta_lapisan_utils.py`, koleksi `peta_lapisan` |
| Proyeksi (UTM ↔ WGS84 ↔ Web Mercator, ubin XYZ) | `frontend/src/lib/proyeksiCitra.js` (murni, teruji silang dengan pustaka `utm`) |
| Pemotong ubin di peramban | `frontend/src/lib/ubinCitra.js` (geotiff.js, dimuat lazy) |
| Gambar & label | `frontend/src/lib/gambarPeta.js`, editor `frontend/src/components/spasial/EditorGambarPeta.jsx` |
| Tampil di peta | `frontend/src/lib/lapisanCitra.js` (pane citra z 250, gambar z 390, label z 395; pin aset 600) |

- **Citra dipotong di peramban admin**, bukan di server. Server 2 vCPU tanpa GDAL
  (`docs/ARSITEKTUR-SPASIAL-IOT.md` §0 #9). Peramban membaca berkas sepotong-sepotong,
  memproyeksikan ulang ke Web Mercator, lalu menyusun piramida: hanya zoom tertinggi
  yang dibaca dari citra, sedangkan zoom di bawahnya disusun dari 4 ubin anaknya.
  Uji: citra 4000×4000 px (10 cm) → 694 ubin dalam ±14 detik.
- **Ubin disimpan di `backend/data_ubin/<id>/z/x/y.(webp|png)`**, di luar `uploads/`.
  Folder `uploads/` ikut dibackup utuh dan dihapus saat restore, sedangkan citra bisa
  berukuran gigabyte. Konsekuensinya, **ubin tidak ikut backup aplikasi**: simpan
  GeoTIFF aslinya agar bisa diunggah ulang. Lokasi folder bisa diubah dengan env
  `AMAN_UBIN_DIR`. Unggahan ditolak bila sisa disk < 3 GB.
- **Ubin hanya untuk pengguna login.** Token HMAC harian dibagikan lewat daftar
  lapisan, jadi tidak ada kueri DB per ubin. Cache peramban 30 hari (`immutable`):
  citra baru selalu menjadi lapisan baru dengan id baru.
- **Performa peta**: saat lapisan mati, tidak ada permintaan sama sekali. Ubin hanya
  diminta di dalam batas citra. Label gambar tampil mulai zoom yang diatur per lapisan
  (bawaan 15). Gambar dibatasi 2.000 objek / 100.000 titik sudut / 2 MB per lapisan.
- **Label garis "ikut garis"** ditaruh di ruas lurus terpanjang bila teksnya muat
  (teks yang melintasi tikungan tajam sulit dibaca) dan selalu terbaca dari kiri ke
  kanan. Label area ada di tengah area; untuk bentuk cekung, dipakai titik tengah
  potongan terpanjang.

## Hak akses

- **Baca**: semua pengguna login, lintas satker. Citra dan gambar adalah rekaman
  geografis, sama seperti OSM.
- **Tulis**: admin satker pembuatnya atau super-admin. Lapisan buatan super-admin
  tidak bisa diubah admin satker. Ubah memakai versi (OCC).
- **Urutan**: admin mana pun (kosmetik, tercatat di audit).
