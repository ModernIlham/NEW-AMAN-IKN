# Font Inter lokal untuk laporan HTML dan PDF

Font asli Inter 4.001 disertakan pada
`backend/assets/fonts/Inter.ttf`, bersama lisensi OFL 1.1 asli dan
`metadata.json`. Sumber: `google/fonts`, commit
`66928797f271fed5ee428544e7229685e2d90127`, berkas
`ofl/inter/Inter[opsz,wght].ttf`. Unduhan ulang pada commit tersebut identik
dengan font terpin yang dipakai pengujian lingkungan sebelumnya.

| Artefak | Byte | SHA256 |
|---|---:|---|
| Inter.ttf asli, tidak dimodifikasi |876576|29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031|
| OFL.txt asli |4377|5b9321a4298cfeb6b34354164a1c3afc3db114569984c502b9b35d988fd58c57|

`report_fonts.report_font_css()` memeriksa kedua checksum dan menyimpan CSS
data URI pada cache satu entri per proses. `_jinja_env()` mendaftarkannya
sebagai fungsi tepercaya. Tiga templat eksekutif tidak lagi mengimpor CSS
Google Fonts; `laporan_satker_v2` memakai font terpin yang sama. HTML preview
dan PDF tidak membutuhkan route font baru, akses font HTTP, URL filesystem,
atau instalasi Inter pada host. Field pengguna tetap di-autoescape.
Nama keluarga font lain dan generator ReportLab tidak diubah.

Data URI menambah sekitar **1,17 MB** pada HTML sebelum kompresi, dengan
batas tetap satu font per dokumen. Pembacaan berkas, hash dan encoding hanya
sekali per proses. Ini menukar ukuran HTML yang terukur dengan penghapusan
ketergantungan jaringan/font host pada setiap laporan. Font tetap asli agar
lisensi dan variasi bobot 100–900 serta optical size 14–32 dipertahankan.

## Pengujian pada 15 Oktober 2026

Lingkungan: Python 3.11.17, runtime/dev hash lock final, WeasyPrint 70,
Pango 1.56.3. Tidak ada dependency atau lock yang diubah untuk cohort ini.

- **146 uji unit lulus, 174,46 detik**, meliputi provenance/checksum font,
  kerusakan font/lisensi yang ditolak, escaping pengguna, hierarki kategori
  dan pengguna, serta pengujian render/pagination gabungan satker yang sudah
  ada. Tiga helper uji yang membuat Environment Jinja sendiri diarahkan ke
  façade `_jinja_env()` produksi, tanpa melemahkan assertion tata letak.
- **2 kontrak lulus, 37,27 detik**. Tiga pratinjau HTML dan empat endpoint
  PDF asli (summary, data, grouped dan satker) memakai data Mongo terisolasi.
  Fetcher WeasyPrint menolak HTTP; tidak ada percobaan HTTP. Keempat PDF
  memiliki font Inter yang benar-benar tertanam, dengan ukuran A4 dan
  orientasi portrait/landscape sesuai templat yang ada.
- Probe native berjalan dalam subprocess dengan konfigurasi Fontconfig
  privat yang **mengecualikan Inter host/XDG**; `fc-match Inter` hanya
  menemukan fallback DejaVu. PDF tetap memuat empat font Inter tertanam
  (regular, bold, ultra-bold dan heavy). Geometri A4 serta koordinat dan
  lebar teks identik dengan font terpin yang sama dari berkas lokal eksplisit.
  Bukti: [local-font-native-proof.json](local-font-native-proof.json).

WeasyPrint 70 belum memvalidasi descriptor CSS rentang `font-weight:100 900`
yang dipakai browser; ia mengabaikan descriptor itu dan membaca sumbu
variabel asli melalui Pango. Probe memverifikasi empat bobot tertanam dan
geometrinya, sehingga hasil tidak bergantung pada font host sebagai fallback.
Empat warning pytest berasal dari lifecycle FastAPI `on_event` yang sudah
ada. Tidak ada perubahan lifecycle dalam cohort font ini.

Perintah pengujian:

```sh
XDG_CACHE_HOME=/workspace/.cache XDG_DATA_HOME=/workspace/.local/share \
/workspace/.aman/security-runtime-a/bin/python -m pytest \
  backend/tests/unit/test_report_fonts.py \
  backend/tests/unit/test_laporan_eksekutif_kategori_jenjang.py \
  backend/tests/unit/test_laporan_eksekutif_pengguna_jenjang.py \
  backend/tests/unit/test_laporan_gabungan_satker.py -q

AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 \
AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 \
XDG_CACHE_HOME=/workspace/.cache XDG_DATA_HOME=/workspace/.local/share \
/workspace/.aman/security-runtime-a/bin/python -m pytest -m integration \
  backend/tests/contract/test_report_fonts.py -q
```

Ops menerima path, ukuran dan checksum dari metadata ini untuk preflight
native sebelum aktivasi release. Bukti instalasi Inter host pada tahap awal
tetap valid bila `XDG_DATA_HOME` yang benar dipakai; cohort ini menghilangkan
kebutuhan tersebut khusus untuk empat templat laporan di atas.
