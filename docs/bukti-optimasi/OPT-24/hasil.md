# OPT-24 — Dependency terpin, hash lock dan spike kompatibilitas

**Bukti final keamanan Python:** [security.md](security.md). Baseline konservatif pada
bagian 24a di bawah adalah titik pembanding historis. Kandidat akhir memakai
137 paket, versi yang diperbaiki, dan audit nol advisory; SDK yang terbukti tidak
dipakai serta PyPDF2 telah dihapus. Jangan menggunakan pin baseline sebagai
rekomendasi rilis setelah hasil audit diketahui.

**Frontend:** [remediasi kompatibel](remediasi-frontend.md) dan [audit frontend](frontend-security.md) mencatat Axios 1.20.0/Router 7.18.4 serta patch tooling. Gerbang lokal 217 suite/2.308 tes, build, lint, dan Chromium 16 pemeriksaan lulus. Sisa 49 kemunculan/25 GHSA pada 13 paket tooling masih tercatat; tidak ada temuan kritis. Klaim nol Python di atas tidak berlaku untuk seluruh website.

**Font laporan lokal:** [local-font.md](local-font.md) mencatat bundling Inter
asli berlisensi OFL, penghapusan font HTTP, serta bukti PDF tanpa Inter host.

## 24a: implementasi dan bukti

- Pin `python-docx==1.2.0`, `python-pptx==1.0.2`; pin provider transitif yang
  sebelumnya mengikuti resolusi terbaru: `lxml==6.1.3`,
  `huggingface_hub==1.5.0`, sesuai baseline yang sudah terpasang/teruji.
- Runtime/dev input terpisah dan resolved lock SHA256 digenerasi **uv 0.12.23**.
  Entry pip tetap `requirements.txt` untuk produksi; CI/development memakai
  `requirements-dev.txt`. Keduanya `--require-hashes`. File pengunci dapat
  digenerasi ulang lewat `scripts/lock_dependencies.sh`.
- Input runtime139 pin konservatif; hasil resolusi Python 3.11 berisi140 paket
  (termasuk `async-timeout` yang dipilih oleh marker kompatibilitas). Tooling
  test/lint/type dan dependensinya dipisahkan. Paket SDK opsional lainnya
  dipertahankan; tidak ada penghapusan berdasarkan direct import saja.
- [runtime-inventory.json](runtime-inventory.json) mencatat import runtime,
  lokasi lazy/try-guarded, provider distribusi, dan dynamic import. Satu dynamic
  import shutdown di`server.py` berasal dari registry modul lokal jobs,
  webp_converter, routes.backup. Python 3.11 / Node 22 / Yarn 1.22.22 menjadi baseline;
  `.python-version` dan`.nvmrc` ditambahkan, packageManager Yarn sudah terpin.

Dua instalasi baru **Python 3.11.17** memakai runtime hash lock, tanpa pytest,
mongomock, black, mypy atau tool dev. `pip check` keduanya lulus. Manifest 140 paket
identik:

`06ef74fc9e464bace03f5a46898310011a0210cd6652dbb539ffdfb83c0e5fb4`

Instalasi dev lock dengan pip juga lulus; **138 tes unit terfokus** DOCX,
restore fail-closed, dan lifecycle unduhan lulus pada environment Python 3.11.17
tersebut. Lock yang digenerasi ulang identik byte-per-byte. Hash yang sengaja
dirusak ditolak pip dengan exit 1 pada venv kosong:
[hash-rejection.json](hash-rejection.json).

Kedua environment menjalankan API asli dan membaca ulang output:

| Pemeriksaan | Hasil kedua environment |
|---|---|
| Bootstrap, login, auth/me |200, identitas valid |
| PDF |1 halaman841,8898×595,2756pt |
| XLSX |4 worksheet, Data Aset 4 baris / 55 kolom |
| PPTX |10 slide,12191695×6858000EMU |
| DOCX |7772400×10058400EMU |
| NativeWeasyPrint/Pango |PDF1 halaman valid |
| Builder backup+manifest |lengkap,3 aset terverifikasi |

Geometri dokumen kedua instalasi sama. Bukti:
[runtime-a-smoke.json](runtime-a-smoke.json),
[runtime-b-smoke.json](runtime-b-smoke.json),
[runtime-b-packages.json](runtime-b-packages.json).
Smoke menggunakan data sintetis dan database localhost bernama acak yang
dibersihkan sesudah selesai. Limiter tetap asli memakai MemoryStorage pada
proses probe agar tidak menyentuh database ratelimit bersama; suite kontrak
Mongo/Redis menangani storage limiter terdistribusi.

[build-environment.json](build-environment.json) mencatat versi Python/Node,
Pango/Cairo/Fontconfig dan hash font Inter. Dua install UV dengan cache bersama:
5,966 detik dan5,567 detik; peakRSS installer84.716 KiB / 173.372 KiB. Ini **bukan**
pengukuran unduh dingin atau ukuran runtime pada VPS. Ukuran disk terukur juga
tersimpan pada manifest; hardlink UV dihitung per environment.

## 24b: lifecycle dan hasil spike, tanpa upgrade produksi

Metadata PyPI resmi Motor diverifikasi saat eksekusi:
deprecation **14 Mei 2026**, critical fixes sampai **14 Mei 2027**. Catatan vendor dan
link migrasi disimpan pada[vendor-metadata.json](vendor-metadata.json). Halaman
docs vendor diblokir proxy cloud pada pemeriksaan ini; uraian paket resmi PyPI
memuat peringatan yang sama. Latest metadata saat diperiksa: Motor 3.7.1 dan
PyMongo 4.19.0; ini tidak otomatis menjadi versi produksi.

Spike **terpisah** PyMongo 4.19.0 pada Mongo standalone nyata:

- CAS dua penulis dan partial unique index lulus.
- Async cursor+Decimal128 presisi lulus.
- GridFS3.670.016 byte melalui15 chunk, abort membersihkan file/chunk parsial.
- Tailable getMore terkena timeout/cancel lalu cursor dapat ditutup.
- `aggregate(...)` dan `client.close()` memerlukan **await**; Motor lama tidak.
- `open_upload_stream_with_id` pada versi native yang diuji masih sinkron.
  Kesamaan satu metode tidak membuat seluruh driver menjadi drop-in.

Bukti[pymongo-async-spike.json](pymongo-async-spike.json), reproduksi:

```bash
python3.11 -m venv /tmp/aman-async-spike
/tmp/aman-async-spike/bin/python -m pip install pymongo==4.19.0 dnspython==2.8.0
/tmp/aman-async-spike/bin/python scripts/spike_pymongo_async.py --mongo-url mongodb://127.0.0.1:27017/
```

Kandidat keamanan kini memakai **Motor 3.7.1 / PyMongo 4.19.0**, mempertahankan
API Motor. Ini berbeda dari migrasi ke driver native PyMongo Async yang belum
diaktifkan: migrasi tersebut memerlukan adapter API aggregate/close dan revisi
mongomock_motor, lalu seluruh kontrak/unit pada driver native. Targetkan sebelum
31 Maret 2027, mendahului akhir critical fixes 14 Mei 2027. Spike di atas membuktikan
perbedaan API dan kontrak yang harus dipertahankan, bukan kesiapan native async
untuk diaktifkan tanpa adapter.

## 24c: keputusan CRA/CRACO

README resmi CRA mengonfirmasi deprecated/long-term stasis;
[cra-source-notice.json](cra-source-notice.json). Build produksi sekarang lulus
dalam 83,14 detik pada cloud; peakRSS belum diukur. Tidak ada bukti saat ini bahwa
memigrasikan bundler bersamaan dengan perbaikan integritas akan memperbaiki
kapasitas runtime. **Penerapan Vite ditunda**; audit frontend terbaru memberi pemicu nyata spike karena 25 GHSA tersisa terikat kontrak CRA/tooling atau belum memiliki patch vendor. Migrasi harus membuktikan seluruh kontrak pada checklist di bawah. Pemicu lainnya: build melampaui
budget CI/deploy, dependency security yang tak dapat diperbaiki padaCRA, atau
fitur yang memerlukan konfigurasi bundler baru.

Checklist migrasi berikutnya harus meliputi alias`@`, `REACT_APP_*`, public/base
path, Jest/jsdom dan mapper axios CommonJS, plugin lightbox precache, entrypoint
offline, asset-manifest/update checker, sourcemap, split chunks dan layout docroot
deploy. Tidak menghapus lock Yarn atau menggunakan engine bypass untuk menyatakan
toolchain baru sudah compatible. Versi Node VPS tetap perlu dibuktikan melalui
preflight rilis sebelum menonaktifkan bypass di skrip instalasi lama.

## Rollback

Gunakan environment/lock rilis lama yang dipertahankan; jangan uninstall atau
downgrade spekulatif pada venv yang sedang melayani pengguna. Split input+lock
dan pembaruan Motor/PyMongo tidak mengubah schema data. Driver native async dan
bundler belum diganti sehingga tidak ada migrasi penyimpanan yang perlu dibalik.
