# OPT-12 — Respons read terbaru dan pembatalan

Implementasi memakai penjaga tiket/generasi yang sudah digunakan dashboard.
`mulaiBaca` menambahkan AbortController per kanal. Mengganti tiket kanal,
mengubah scope, menutup hook, dan membatalkan kanal menghentikan read lama.
Tiket mutasi `mulai` tetap tidak memiliki signal, karena pembatalan HTTP bukan
pembatalan commit server.

- Dashboard: daftar desktop, jendela halaman, append/prepend mobile, statistik,
  opsi filter, rekonsiliasi baris dan pilih seluruh halaman memakai signal.
  Guard tiket tetap memeriksa semua hasil, error dan fallback snapshot; cancel
  read lama tidak beralih luring atau mengubah daftar/loading baru.
- Kodefikasi, Persediaan dan Penggunaan: daftar/pagination memakai tiket kanal;
  mengetik/clear langsung membatalkan read sebelumnya sebelum debounce baru.
  Respons/error lama tidak mengubah items, halaman, error atau loading terbaru.
  Scope mencakup user dan satker efektif (termasuk admin pusat).
- Picker persediaan massal, Pengadaan (referensi kode + stok dan tautan aset),
  Penggunaan (SK/proses/henti) dan Penilaian (kode, koreksi, riwayat) memakai
  debounce terjaga bersama `usePencarianBaca`. Empty query, scope, tutup form
  dan unmount membatalkan tiket+signal. Dua sumber Pengadaan tetap allSettled,
  sehingga satu sumber gagal tidak menyembunyikan sumber yang berhasil.
- Lookup detail Kodefikasi/Penggunaan, riwayat Penilaian dan posisi penyusutan
  juga dilindungi. Perubahan tanggal penyusutan membatalkan read sebelumnya.

## Verifikasi lokal

Tes terfokus memakai promise deferred sebenarnya, bukan pencocokan teks sumber:
A/B selesai terbalik, clear saat read aktif, pergantian satker, unmount,
AbortSignal lama, error usang, retensi loading baru, fallback luring yang tidak
terpanggil dan satu sumber picker gagal. Suite Penggunaan lama juga dijalankan
untuk memastikan alur pemegang, BAST dan penjagaan portal tetap berfungsi.

Perintah:

```sh
CI=true corepack yarn --cwd frontend test --watch=false --runInBand --runTestsByPath \
  src/pages/__tests__/PencarianHalamanTerjaga.test.jsx \
  src/hooks/__tests__/usePencarianBaca.test.jsx \
  src/hooks/__tests__/usePenjagaPermintaan.test.jsx \
  src/lib/__tests__/pemuatDaftarAset.test.js \
  src/pages/__tests__/KodeBarangPicker.test.jsx \
  src/pages/__tests__/PenggunaanPemegang.test.jsx \
  src/pages/__tests__/PenggunaanPortalPenjagaan.test.jsx \
  src/pages/__tests__/PenggunaanBastOtomasi.test.jsx
```

Hasil lokal: **8 suite / 76 tes lulus** (log `/tmp/aman-opt12-tests.log`).
Lint terarah: 0 error; `git diff --check` bersih.

Full lint/test/build, CI dan pemeriksaan produksi merupakan gerbang integrasi
bersama; bukti ini tidak mengklaim deployment sudah dilakukan.
