# Audit Alur & Kenyamanan Aplikasi AMAN — Juli 2026

> Hasil **uji-alur menyeluruh seluruh fitur** (6 penelusur paralel membaca kode
> UI + backend dari kacamata pengguna: pengguna baru, operator BMN, pengelola
> satker, operator persediaan/pengadaan, KPB, admin). Tujuan: alur **tepat,
> nyaman, handal, dan matang** sesuai yang tampil. Temuan diperingkat per area,
> dikerjakan bertahap per GELOMBANG (task list sesi pengembangan). Perbaikan
> selesai ditandai ✔ + nomor PR.

## Ringkasan kondisi

Fondasi dinilai **matang**: offline/antrean sinkron lengkap dengan banner +
toast konflik, navigasi kembali seragam (`useBackGuard`), toast `sonner`
seragam, cakupan `data-testid` baik, dan halaman referensi (Kodefikasi,
Referensi Akun master, Masa Manfaat) menjadi **pola emas** yang patut ditiru.
Kelemahan utama yang berulang lintas halaman: (1) `window.prompt/confirm`
native untuk isian multi-field, (2) aksi hapus destruktif tanpa konfirmasi di
sebagian halaman, (3) integrasi "setengah jadi" — data/FK sudah ada di backend
tetapi UI tidak memakainya, (4) error jaringan yang ditelan senyap.

## Alur terbaik yang disarankan (per area)

1. **Alur inti**: pertahankan pola offline yang sudah matang; tambah afordansi
   navigasi awal — CTA "Masuk Modul ›" pada kartu siklus yang bisa dibuka ✔,
   saklar mode berlabel di semua breakpoint, jalur "Lupa Password" via OTP,
   dialog Buat Kegiatan ramping (2 field wajib + lipatan opsional).
2. **Persuratan–Pelaporan**: jadikan *booking → sahkan → cetak* satu untai —
   nomor terbooking mengalir otomatis ke PDF laporan (bukan nomor SK Tugas),
   dialog hasil booking menautkan "Buka di Persuratan", hub Pelaporan punya
   pintu "Pengaturan Kop/Sampul" sendiri + badge FINAL/terkunci pada dropdown
   unduh.
3. **Penggunaan/BAST**: Master Pegawai = satu sumber identitas orang; BAST =
   peristiwa yang menaikkan kelengkapan (isi `bast_file_id` saat bukti ttd
   terunggah sehingga badge "Lengkap/BAST x/y" hidup); penerima BAST dipilih
   dari picker pegawai; riwayat BAST difilter nama+NIP.
4. **Rantai perolehan**: bawa data ke depan, jangan salin ulang — RKBMN →
   usulan Penganggaran (FK `rkbmn_id` sudah ada), serapan nyata dari Pengadaan
   ditampilkan, BAST menjadi simpul yang memecah barang ke jalur Aset
   (per-NUP) atau Persediaan, LPB punya riwayat unduh ulang.
5. **Siklus lanjut**: satu `<AssetSearchSelect>` + satu `TransitionDialog`
   bersama (hapus semua `window.prompt`), kandidat otomatis tersambung ke
   aksinya (Rusak Berat → BA Pemusnahan; temuan Wasdal → tiket penertiban
   ter-prefill), dan penanda *in-flight* lintas modul pada master aset.
6. **Lintas**: setiap delete ber-konfirmasi ✔ (jalur utama), setiap kontrol
   admin-only dibungkus `isAdmin`, tidak ada `.catch(() => {})` senyap ✔
   (jalur utama), pencarian selalu debounce ✔, warna pakai token tema ✔,
   ikon-tombol padat wajib `min-w-0 min-h-0` ✔.

## GELOMBANG 1 — Keandalan & umpan balik dasar (✔ selesai, PR #354)

- ✔ Konfirmasi hapus: tiket Wasdal (penertiban & insidentil), periode
  pelaporan, override akun (golongan & sub-kelompok), catatan SK PSP, logo kop.
- ✔ Error tak lagi senyap: referensi persuratan gagal → toast; ringkasan SIMAN
  gagal → badge "coba lagi"; `apiErr` konsisten di pemetaan akun.
- ✔ Alasan buka-kunci periode kosong → pesan jelas (bukan diam).
- ✔ Guard "self" API users dari identitas terautentikasi (`_admin.id`):
  nonaktifkan/hapus/demote diri sendiri ditolak walau `admin_id` tak dikirim.
- ✔ Label & istilah: "Email atau Username" saat login; "On Going/Ongoing" →
  "Berlangsung"; empty-state kegiatan menyesuaikan peran (viewer tak lagi
  disuruh "membuat"); tooltip pil sinkron di header.
- ✔ CTA "Masuk Modul ›" / "Lihat Konsep ›" pada kartu Tahap Siklus.
- ✔ Editor Sampul: catatan "berlaku global", warna aman dark-mode, tap-target
  44px di tombol kecil, hover benar, `data-testid` tombol Tutup.
- ✔ Debounce pencarian Referensi Akun (350ms, pola Kodefikasi).

## Backlog bertahap (task list sesi — ringkasan temuan tersisa)

**GELOMBANG 2 — BAST ↔ kelengkapan pemegang**: `bast_file_id` terisi dari
bukti ttd (metrik "BAST x/y"/"Lengkap" hidup); badge aset satu sumber (kontra
"Tanpa BAST" vs "BAST <tgl>"); riwayat BAST per nama+NIP; picker Master
Pegawai untuk penerima; segarkan detail pasca-BAST non-mutasi; hint penyerah
kosong + tautan Referensi Pejabat; helper 1 baris per jenis BAST; chip "belum
di master" + "Daftarkan" 1-klik (enrichment backend sudah ada); jangan isi
Jabatan dengan unit kerja; handover idle bertaut BAST; disclosure bagian
lanjutan dialog BAST; paging kandidat idle.

**GELOMBANG 3 — Persuratan–Pelaporan satu untai**: nomor booking → PDF
laporan (sampul/BAHI — kini PDF memakai nomor SK Tugas!); tombol "Buka di
Persuratan" pasca-booking; pintu Pengaturan Kop dari hub Pelaporan; badge
FINAL/terkunci di dropdown LBKP/CaLBMN + pemilih tahun bebas; periode tahun
lalu bisa didaftarkan; opsi lanjutan (keamanan/klasifikasi) di
BookingNomorButton + pratinjau seragam; legenda "eks:" nomor eksternal;
konfirmasi status surat masuk "Selesai"; hak buat-vs-hapus periode selaras;
tombol Sampul disembunyikan untuk non-admin (backend 403).

**GELOMBANG 4 — Rantai perolehan tersambung**: dropdown RKBMN di usulan
Penganggaran (FK backend sudah lengkap); tampilkan `realisasi_pengadaan`
(serapan nyata); menu Riwayat LPB (unduh ulang); "Daftarkan ke Persediaan"
dari barang BAST konsumsi; auto-isi picker perolehan di dialog Massal; draft
aset pecah per-NUP bila jumlah>1; penjelas 3 pintu masuk barang (BAST vs LPB
vs jenis M/K); CSV register Perencanaan; aksi "Ubah tautan anggaran"
post-hoc; placeholder saat daftar perolehan kosong; hint urutan
Tautkan-vs-Draft; checklist dokumen optimistic.

**GELOMBANG 5 — Siklus lanjut seragam**: `TransitionDialog` bersama
menggantikan seluruh `window.prompt` (Pengamanan, PSP, Proses, tenggat
pelaporan, Perencanaan); `<AssetSearchSelect>` bersama (2 pola × page_size
beda → 1); kandidat Rusak Berat 1-klik di Pemusnahan; edit register saat
`diusulkan` (Pemindahtanganan/Pemusnahan); revert Penghapusan
diproses→diusulkan; temuan Wasdal → tombol "Tindak lanjuti" (prefill
penertiban + asset_id); penanda *in-flight* lintas modul + cross-check antar
register keluar; jalur TGR utk tidak-ditemukan (register/checklist); tautan
SK Penghapusan terlihat; glosarium akronim (PMPP/KSPI/KETUPI/LHIP/NTPN);
penempatan aksi utama+CSV seragam; jangan reset pencarian multi-aset;
lampiran wasdal perjanjian diberi label pembeda.

**GELOMBANG 6 — Navigasi & form inti**: Lupa Password via OTP (infrastruktur
sudah ada); saklar mode Dashboard|Inventarisasi berlabel di semua breakpoint
(desktop tak punya!); grup "Referensi & Master Data" di Beranda Modul (6 pil
→ grid bertajuk); dialog Buat Kegiatan ramping; pintu Info/Bantuan terlihat
(kini hanya 3-klik logo); ribbon status kartu kegiatan bergaya tombol;
sub-label dua tombol simpan field sheet; sliver buka-form desktop berlabel;
Debug OTP disembunyikan di produksi; loading state tab pemetaan akun.

> Rincian lokasi kode setiap temuan (file:baris) tersimpan pada laporan
> penelusur di sesi pengembangan 2026-07-17; gelombang dikerjakan berurutan,
> satu PR per gelombang.
