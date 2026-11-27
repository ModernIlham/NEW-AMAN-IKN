# Lapisan Citra Eksisting pada Peta

Status: **fitur tersedia, data citra belum ada** (27 Nov 2026).

## Masalah

Peta dasar OpenStreetMap di kawasan yang sedang dibangun tertinggal dari kondisi
lapangan. Jalan dan gedung baru belum tergambar, sehingga pin aset tampak berdiri
di tengah hutan. Lapisan ini menumpangkan **foto udara terbaru** (drone/ortofoto)
di atas OSM, hanya di wilayah yang dipotret, dan bisa ditampilkan atau
disembunyikan kapan saja.

## Cara kerja

| Bagian | Lokasi | Catatan |
|---|---|---|
| Registri citra | koleksi `peta_lapisan`, `backend/routes/peta_lapisan.py`, validasi `backend/peta_lapisan_utils.py` | Nama, tanggal rekam, sumber, alamat ubin, batas wilayah, rentang zoom, opasitas, aktif/arsip |
| Peta dasar tunggal | `frontend/src/lib/petaDasar.js` | Satu sumber alamat OSM untuk Peta Aset, Peta Kolaborasi, Editor Denah, Lokasi Temuan |
| Pemasang lapisan | `frontend/src/lib/lapisanCitra.js` | Pane `citraEksisting` (z 250): di atas OSM (200), di bawah denah (380) dan pin (600) |
| Peta Aset | tombol **Eksisting** + panel **Citra Eksisting** | Tampil/sembunyi per citra, lompat ke area, transparansi |
| Peta lain | tombol ikon gambar di kanan atas | Memakai pilihan yang sama (disimpan per perangkat) |
| Kelola | Hierarki Spasial → **Citra Eksisting** (admin) | Daftar, ubah, arsipkan, hapus, dan **Periksa** ubin contoh |

### Aturan performa yang dijaga

1. **Mati = nol permintaan.** Daftar citra baru diambil saat tombol dinyalakan,
   sekali per sesi.
2. **Ubin hanya diminta di dalam batas & rentang zoom citra** (opsi Leaflet
   `bounds`, `minZoom`, `maxNativeZoom`). Menggeser peta di luar area tidak
   menghasilkan permintaan sia-sia. Di atas zoom maksimum, ubin terakhir diperbesar.
3. **Ubin adalah berkas statis yang disajikan nginx, bukan backend.** Uvicorn
   produksi hanya satu proses; satu layar peta bisa meminta 15–25 ubin sekaligus.
4. **Service worker tidak menyimpan ubin.** Jalur `/uploads/` tidak disentuh
   service worker; peramban memakai cache HTTP biasa. Deploy tidak ikut mengunduh
   ulang citra.
5. **Pin dan denah selalu di atas citra dan tetap bisa diklik** (pane citra
   `pointer-events: none`).

### Siapa boleh apa

- **Membaca**: semua pengguna yang login melihat citra **aktif**, lintas satker.
  Citra adalah rekaman geografis; satu foto kawasan benar bagi semua satker yang
  asetnya ada di sana (sama seperti OSM).
- **Menulis**: admin. Citra distempel satker pembuatnya dan hanya boleh diubah atau
  dihapus admin satker itu atau super-admin. Citra buatan super-admin tidak bisa
  diubah admin satker, karena tampil di peta semua satker.
- Ubah memakai versi (OCC); alamat ubin yang sama tidak bisa didaftarkan dua kali.

## Menyiapkan citra (dilakukan DI LUAR server)

Server produksi 2 vCPU dan sengaja tanpa GDAL (`docs/ARSITEKTUR-SPASIAL-IOT.md`
§0 #9), jadi pemotongan ubin dikerjakan di laptop.

1. **Masukan:** GeoTIFF ortofoto (hasil olah drone, mis. WebODM/Agisoft/Pix4D).
2. **QGIS:** Processing Toolbox → *Raster tools* → **Generate XYZ tiles (Directory)**.
   - *Extent*: batas citra (catat angka barat/selatan/timur/utara dalam derajat
     EPSG:4326 untuk registri).
   - *Minimum zoom*: 14. *Maximum zoom*: sesuai resolusi (lihat tabel).
   - *Tile format*: **JPG** (lebih kecil) bila citra berbentuk persegi penuh;
     **PNG** bila tepinya tidak beraturan dan perlu transparan.
   - **Matikan** *Use inverted tile Y axis (TMS convention)* — aplikasi memakai
     skema XYZ.
   - Alternatif baris perintah: `gdal2tiles.py --xyz -z 14-20 -w none ortofoto.tif keluaran/`
     (perlu diverifikasi sesuai versi GDAL Anda).
3. **Beri nama folder berversi**, mis. `kipp-2026-10`. Jangan pernah menimpa folder
   lama dengan citra baru: peramban menyimpan ubin hingga 30 hari, sehingga
   pengguna akan melihat campuran citra lama dan baru. Citra baru = folder baru +
   registri baru; yang lama diarsipkan (nonaktif).

### Perkiraan ukuran (belum diukur dengan data nyata)

Untuk area **5 × 5 km**:

| Zoom maksimum | Resolusi kira-kira | Jumlah ubin | Ukuran (JPG) |
|---|---|---|---|
| 18 | ±60 cm | ±1.500 | ±25–60 MB |
| 19 | ±30 cm | ±5.800 | ±100–250 MB |
| 20 | ±15 cm | ±23.000 | ±0,4–0,9 GB |
| 21 | ±7,5 cm | ±91.000 | ±1,5–3,5 GB |

Disk VPS 96 GB (terpakai ±31 GB per 29 Agu 2026 — periksa ulang sebelum
mengunggah citra besar).

## Mengunggah & mendaftarkan

1. Salin folder ke server:
   `rsync -a keluaran/ <user>@<vps>:/var/www/inventarisasi/backend/uploads/ubin/kipp-2026-10/`
   Folder `backend/uploads/` diabaikan git dan selamat dari deploy.
2. nginx sudah menyajikan `/uploads/` sebagai berkas statis (`scripts/vps-deploy.sh`:
   `location /uploads/ { alias …/backend/uploads/; expires 30d; }`). **Perlu
   diverifikasi** bahwa konfigurasi server produksi masih sama.
3. Hierarki Spasial → **Citra Eksisting** → *Daftarkan citra*:
   alamat `/uploads/ubin/kipp-2026-10/{z}/{x}/{y}.jpg`, batas, zoom, tanggal rekam.
4. Tekan **Periksa**. Hasil *"Server menjawab halaman web, bukan gambar"* berarti
   nginx belum menyajikan jalur itu dan permintaan jatuh ke halaman aplikasi.

## Sebelum mengunggah: kerahasiaan

`/uploads/` **terbuka tanpa login**. Siapa pun yang tahu alamatnya bisa mengunduh
ubin. Bila citra kawasan pemerintahan termasuk informasi yang dibatasi, **jangan
unggah ke `/uploads/`** sebelum akses dibatasi. Usulan: blok nginx tersendiri dengan
`secure_link` (tautan bertoken kedaluwarsa yang diterbitkan backend sekali per
sesi), bukan pemeriksaan login per ubin ke backend, yang akan membebani uvicorn.
Keputusan ini milik pemilik data.

## Belum dikerjakan (tahap berikut)

- Unggah ZIP ubin langsung dari web (validasi + ekstrak di latar belakang).
- Perlindungan akses ubin (`secure_link`) bila citra dinyatakan terbatas.
- Simpanan luring citra untuk lapangan tanpa sinyal (perlu batas ukuran di HP).
