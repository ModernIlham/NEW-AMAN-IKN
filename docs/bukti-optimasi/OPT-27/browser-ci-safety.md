# Browser CI: isolasi, pemeriksaan gambar, dan jalur gagal

`scripts/uji_browser_ci.py` menjalankan backend asli lewat factory khusus tooling.
Sebelum lifespan, limiter menggunakan MemoryStorage; backup temp, arsip, uploads,
tempfile dan profile Chromium berada dalam sandbox privat. Endpoint identitas
fixture memeriksa marker seed Mongo yang benar, storage limiter yang sebenarnya,
serta lokasi ketiga direktori. `uji_browser.py` menolak menulis bila bukti ini
tidak cocok dengan run akun sintetisnya.

Database selalu bernama acak `aman_ci_browser_<UUID>`. Koleksi ownership kosong
dibuat sebelum seed agar kegagalan sebelum manifest tetap dapat dibersihkan.
Cleanup hanya drop database dengan nama dan marker ownership milik invocation
tersebut; database lain dipertahankan. Semua proses, log, database dan direktori
privat dibersihkan secara independen, sehingga kegagalan cleanup tidak menimpa
error pengujian pertama. Timeout child juga membersihkan grup Chrome dengan
verifikasi PID/start-time dan profile milik sandbox.

Guard bersama `backend/fixture_target.py` digunakan browser wrapper, seed,
profiler read/index, smoke runtime, spike driver dan fixture kontrak. Ia menolak
SRV, multi-host, credentials, path database, port invalid, serta replica-set/
load-balanced/discovery options. Koneksi memakai satu authority loopback dengan
`directConnection=true` eksplisit. Tidak ada query pengguna yang diteruskan.
Smoke runtime juga memindahkan direktori backup/arsip/uploads sebelum lifespan.

Input akun berizin 0600, sandbox berizin 0700, dan seluruh input privat berada
di luar direktori artifact. Pada kegagalan, `hasil.json`/`runner.json` mencatat
checkpoint dan kelas error, bukan expression CDP, payload, token, atau storage.
Log publik dibatasi ekor 64 KiB per proses, disensor dengan secret seed yang
persis dan redaksi log aplikasi. Screenshot login tidak diambil. Workflow CI
tetap mempertahankan artifact tujuh hari melalui langkah `if: always()`.

Pengujian bukan sekadar keberadaan DOM: item kelengkapan baru harus muncul pada
readback API, hapus seleksi harus membuat seluruh checkbox unchecked, dan foto
yang terlihat harus `complete && naturalWidth > 0` sebelum screenshot. Main
lightbox serta pratinjau penuh checklist diperiksa dengan decoder browser juga.
Pemeriksaan terakhir ini menemukan bug nyata STNK: rekomendasi memindahkan item
dari index server 0 ke index visual 4, sehingga URL media lama menghasilkan 404.
Perbaikan frontend mempertahankan index server; run akhir mendapat media 200 dan
gambar tampil. Foto fixture dibuat dengan Pillow, bukan base64 rusak.

Bukti lokal 15 Oktober 2026:

- Wrapper Chromium aktual memakai port terpisah 18127/18827 dan `BUILD_PATH`
  privat, sehingga tidak menyentuh build/proses pemeriksaan lain. **12 pemeriksaan
  UI lulus, delapan viewport/tema, 29,2 detik**, cleanup tanpa error. Ukuran layar
  320/360/768/1440, masing-masing terang/gelap; 16 screenshot disimpan di output
  lokal `/workspace/.aman/browser-ci-isolated-media-final`.
- Run dengan binary Chromium sengaja tidak ada gagal pada `browser_startup`,
  menyimpan kelas FileNotFoundError beserta log tersensor, dan cleanup tetap sukses.
- Chrome aktual yang Python parent-nya dibunuh dibersihkan oleh parent wrapper;
  PID/start fence lulus, browser tidak aktif, dan profile terhapus.
- Probe Chrome terpisah menolak gambar rusak yang tetap mempunyai elemen terlihat,
  lalu menerima foto PNG valid. Ini menjaga agar broken-image tidak dianggap lulus.
- **63 unit** harness/loadtest/profile guard, **7 unit** budget inventory pada
  security runtime, dan **1 kontrak seed Mongo nyata** lulus. Unit memaksa gagal
  seed tanpa manifest, gagal cleanup database, gagal constructor/CDP close,
  identitas PID salah, serta URI berbahaya ditolak sebelum client dibuat.

Hasil mesin yang aman berada di
[`browser-ci-isolation.json`](browser-ci-isolation.json). Ini smoke sintetis kecil,
bukan klaim kapasitas produksi atau semua alur aplikasi telah dicakup. Bukti
dependensi runtime bersih dicatat terpisah dari pengujian venv pengembangan ini.

```bash
python scripts/uji_browser_ci.py --mongo mongodb://127.0.0.1:27017/ \
  --api-port 18127 --frontend-port 18827 --chromium /usr/bin/chromium \
  --output /tmp/browser-evidence-new-run
```

Direktori output harus baru/kosong; build dibuat privat secara default. Opsi
`--skip-build` hanya untuk build existing yang sudah memakai URL API yang sesuai.
