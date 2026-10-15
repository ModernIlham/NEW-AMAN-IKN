# OPT-01 — Semantik seleksi halaman dan interaksi keyboard

Status: implementasi dan pemeriksaan terfokus selesai, 15 Oktober 2026.

Seleksi memakai keanggotaan setiap ID terlihat, bukan kesamaan jumlah ID.
Helper `frontend/src/lib/seleksiHalaman.js` dipakai header tabel dan tindakan
pilih/batalkan semua di dashboard. Toggle hanya mengubah ID tampilan aktif;
ID halaman lain tetap tersimpan. Pengambilan semua halaman menggabungkan ID
hasil ke seleksi yang sudah ada. `Hapus seleksi` tetap mengosongkan seluruh ID.
Banner memakai status keanggotaan tampilan aktif dan mengikuti breakpoint
desktop/galeri/HP ketika viewport berubah.

Checkbox header memiliki status DOM `indeterminate` dan `aria-checked="mixed"`
ketika sebagian halaman dipilih. Seluruh checkbox mempunyai nama aksesibel.
Handler keyboard baris tabel hanya bekerja jika target event baris itu sendiri;
Space pada checkbox dan Enter pada tombol foto tidak memicu editor.
Foto galeri memakai tombol HTML bernama, dengan checkbox dan tombol SIMAN
sebagai saudara, sehingga tidak ada tombol/input bersarang dalam tombol foto.

Loader penampil foto menyimpan pemicu sebelum portal dibuka. Tombol tutup
memperoleh fokus saat pemuatan maupun setelah penampil termuat; setelah tutup,
fokus kembali ke pemicu yang masih tersambung dengan `preventScroll: true`.
Fokus editor yang baru dibuka dipertahankan dan baris yang sudah keluar dari
virtualisasi tidak dipaksa muncul kembali.

Verifikasi terfokus menggunakan Jest melalui CRACO: **4 suite, 20 tes lulus**.

```sh
cd frontend
corepack yarn test --watchAll=false --runInBand --runTestsByPath \
  src/lib/__tests__/seleksiHalaman.test.js \
  src/components/assets/__tests__/SeleksiKeyboardAset.test.jsx \
  src/components/assets/__tests__/PhotoLightboxLoader.test.jsx \
  src/components/assets/__tests__/SelectionToolbar.test.jsx
```

Kasus meliputi halaman sama besar dengan ID berbeda, overlap, halaman kosong,
pilihan lintas halaman, pindah halaman melalui rerender komponen nyata, toggle
header, status mixed, event keyboard native checkbox/foto/baris, markup galeri,
dan pengembalian fokus setelah tutup pada fase loading maupun penampil termuat.
Tes toolbar yang sudah ada menjaga hide/draft serta seleksi setelah simpan.
Lint berkas terkait tidak menemukan error; satu warning dependensi hook yang
sudah ada tetap tercatat pada `PhotoLightbox.jsx`.

Ukuran kontrol 36 px, CSS kepadatan, mount panel tersembunyi, revisi draf setelah
simpan, dan mekanisme jangkar scroll tidak diubah. Tidak ada perubahan schema
atau migrasi data. Rollback: revert helper, komponen, dan tes OPT-01 bersama.
Validasi browser menyeluruh, CI penuh, serta rilis produksi dilakukan pada
integrasi seluruh paket; bukti ini tidak mengklaim tahapan tersebut sudah lewat.
