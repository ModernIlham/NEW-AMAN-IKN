# Evaluasi Menyeluruh Fitur & Integrasi — AMAN BMN

Dokumen ini mengevaluasi keseluruhan fitur aplikasi AMAN dan **keterhubungan
(integrasi) antar-modulnya**, berdasarkan telaah kode (Juli 2026). Tujuannya:
memberi peta yang jujur — apa yang sudah tersambung, apa yang masih longgar/
belum, dan rekomendasi prioritas. Referensi memakai `file:baris`.

Arsitektur: FastAPI + Motor/MongoDB (backend), React CRA (frontend). Seluruh
40 router terdaftar di `backend/server.py`. Pola konsisten: `*_utils.py` (murni,
teruji unit) + `routes/*.py` (CRUD) + halaman React; field aset dijaga registry
anti-drift (`asset_fields.py`, `persediaan_fields.py`).

---

## 1. Peta Modul & Status

### 1.1 Penatausahaan inti (`frontend/src/lib/bmnModules.js`)
| Modul | Status | Catatan |
|---|---|---|
| Inventarisasi Aset | **Aktif** | Workspace utama (DashboardPage): daftar/peta/kamera, OCC, offline snapshot + antrean. |
| Inventarisasi Persediaan | **Aktif** | FIFO per layer, jenis transaksi SAKTI, tautan Pengadaan, layer FIFO, akun neraca, opname/BAOF. |
| Pelaporan | **Sebagian** | Hub arsip laporan lintas kegiatan; periode pelaporan (`periode_pelaporan`). |
| Pembukuan | **Segera** | Tak punya router/halaman sendiri; diwujudkan lewat `pembukuan_utils.py` di dalam laporan (DBKP/Neraca). |

### 1.2 Master/Referensi (fondasi lintas modul)
Kodefikasi Barang (`kodefikasi`), Master Pegawai (`pegawai`), Referensi Pejabat
(`pejabat`), Referensi Ruangan (`ruangan`), Referensi Akun Neraca/BAS (`akun_bas`),
Akun Persediaan (`persediaan_akun`), Kategori Aset (`categories`), Masa Manfaat
(`masa_manfaat`). Semua ada halaman kelola (kecuali masa manfaat via PenilaianPage).

### 1.3 Siklus BMN (`SIKLUS_MODULES`) — semua **Sebagian**
Perencanaan, Penganggaran, Pengadaan, Penggunaan, Pemanfaatan, Penilaian,
Pengamanan, Pemeliharaan, Pemindahtanganan, Pemusnahan, Penghapusan, Wasdal.
Masing-masing punya router + halaman + register koleksi sendiri; belum ada yang
berstatus "Aktif" penuh.

---

## 2. Matriks Integrasi Antar-Modul (apa membaca/menulis dari mana)

| Rantai | Bentuk keterhubungan | Kekuatan | Referensi |
|---|---|---|---|
| **Kodefikasi ↔ Aset** | `asset_code` dicek ke referensi (peringatan non-blocking) + pemilih kode + nama resmi | **Lunak** (tak ada FK saat simpan) | `routes/audit.py:197`, `AssetForm.jsx` pemilih kode, `kodefikasi_utils.py:112` |
| **Kodefikasi ↔ Persediaan** | Kode wajib berawalan '1'; auto nomor urut + NUP | **Keras** (validasi kode) | `routes/persediaan.py:844` |
| **Golongan → Akun Neraca ↔ Laporan** | `akun_untuk_golongan` mengisi kolom Akun di DBKP/Neraca | Sedang (default + override) | `akun_bas_utils.py:36`, `reports.py:1400,1526` |
| **Sub-kelompok → Akun Persediaan ↔ Laporan Posisi** | `akun_persediaan` + rekap per akun | Sedang (default 117111 + override) | `persediaan_akun_utils.py:36`, `routes/persediaan.py:514` |
| **Pegawai ↔ Pengguna Aset** | `pengguna_nip` (NIP key) — pemilih pegawai isi nama+NIP+jabatan; laporan Distribusi Per Pengguna join by NIP | **Lunak** (teks/NIP, peringatan bila belum terdaftar) | `AssetForm.jsx` pemilih pegawai, `report_utils.py:28` |
| **Pengadaan ↔ Persediaan** | `perolehan_id` pada transaksi masuk, snapshot BAST, 404 sebelum mutasi stok | **Keras** (FK tervalidasi) | `routes/persediaan.py:943`, `pengadaan_utils.py:194` |
| **Penilaian/Penyusutan ↔ Aset** | Baca `purchase_price/date`, `condition`, `asset_code` (golongan), revaluasi | Kuat (baca langsung field aset) | `penilaian_utils.py:92,166` |
| **Pejabat ↔ Laporan (tanda tangan)** | `penandatangan_kpb` (registry aktif per tanggal → fallback setelan) | Sedang (7 laporan satker) | `pejabat_utils.py:111`, `reports.py:1476` |
| **Ruangan ↔ Aset (KIR/DBR)** | Cocok string label ruangan; PJ ruangan dari pejabat (konseptual) | **Lunak** (teks) | `ruangan_utils.py:42,80` |
| **Backup/Restore/Reset ↔ SEMUA koleksi** | Enumerasi koleksi **dinamis** — modul baru otomatis tercakup | **Kuat** | `backup_utils.py:34,46,52`; `server.py:297` |

**Ringkas:** integrasi paling kuat = **Pengadaan→Persediaan** (FK 404-guarded) dan
**Backup dinamis** (semua koleksi). Integrasi paling longgar = tautan aset ke
master (kodefikasi/pegawai/ruangan) yang sengaja **berbasis teks/NIP + peringatan
lunak**, bukan FK — agar entri lapangan & data lama tetap jalan (offline-first).

---

## 3. Temuan Gap / Inkonsistensi

1. **`pengguna_nip` bukan FK.** Tak divalidasi ke `db.pegawai` saat simpan; hanya
   peringatan lunak (`AssetForm.jsx`) + filter cari (`routes/assets.py:252`). NIP
   salah ketik jadi grup tak tertaut di laporan (join best-effort `report_utils.py:48`).
2. **Belum ada `ruangan_id` FK per aset.** Ruangan berbasis teks (`location`/`user`),
   dicocokkan string (`ruangan_utils.cocok_ruangan_master`). Ditunda eksplisit
   (`docs/PUSTAKA-REGULASI-BMN.md:212`).
3. **Dua sistem akun paralel.** `akun_bas_utils` (golongan-level) & `persediaan_akun_utils`
   (sub-kelompok) sama-sama memetakan golongan "1"→117111 — logika ganda yang berisiko
   drift bila salah satu diubah.
4. **Inkonsistensi resolusi penanda tangan.** Laporan satker memakai registry pejabat
   (`_penandatangan_kpb`), tetapi **semua PDF persediaan** membaca `settings.kasatker_*`
   langsung (`routes/persediaan.py:187,449,599,688`) → KPB dari registry tak muncul di
   dokumen persediaan.
5. **Modul "Pembukuan" berstatus "segera"** tanpa router/halaman; hanya lewat
   `pembukuan_utils.py` di laporan. Semua `SIKLUS_MODULES` masih "sebagian".
6. **Pengadaan→aset auto-draft belum ada.** Docstring "menyusul" (`routes/pengadaan.py:7`);
   baru ada tautan manual `barang[].asset_id`.
7. **Pemeriksaan integritas hanya melaporkan, belum auto-perbaiki** drift snapshot
   (`routes/audit.py:134,190,244`).
8. **Penyusutan golongan 6 (Aset Tetap Lainnya) & 8 (ATB/amortisasi) belum ditangani**
   (`penilaian_utils.py:42`).

---

## 4. Rekomendasi Prioritas

### Prioritas TINGGI
- **Samakan penanda tangan persediaan dengan registry pejabat** (pakai
  `penandatangan_kpb`) agar konsisten dengan laporan satker (gap #4). Kecil, berdampak.
- **Verifikasi akun neraca ke Lampiran BAS** (lihat §5) — akurasi finansial adalah
  prioritas; sub-akun 1171xx & golongan-level masih perlu konfirmasi.
- **Satukan sumber akun** (gap #3): jadikan `persediaan_akun` memakai `akun_bas` golongan
  "1" sebagai basis agar tak ada dua kebenaran.

### Prioritas SEDANG
- **Perkuat tautan pengguna↔pegawai** (gap #1): opsi "kunci ke master" (validasi saat
  simpan) yang **bisa dinyalakan admin**, tetap default lunak untuk offline/data lama.
- **`ruangan_id` FK opsional per aset** (gap #2) untuk KIR/DBR yang lebih rapi, dengan
  fallback teks.
- **Auto-draft aset dari Pengadaan** (gap #6) — menutup rantai perolehan→penatausahaan.

### Prioritas RENDAH
- Auto-perbaiki drift snapshot (gap #7) — kini cukup dilaporkan.
- Penyusutan golongan 6 & amortisasi ATB golongan 8 (gap #8).
- Naikkan status modul siklus "sebagian"→"aktif" setelah tiap modul lengkap
  (pola Persediaan #310).

---

## 5. Item yang Perlu Verifikasi Pemilik/Regulasi

Ditandai jelas di kode/pustaka (tidak ditebak diam-diam):
- **Akun neraca BAS**: golongan-level (`akun_bas_utils.py:1`) & sub-akun persediaan
  1171xx (`persediaan_akun_utils.py:8,18`) — hanya **117111 terkonfirmasi**; sisanya
  `[WAJIB VERIFIKASI Lampiran BAS / KEP-211/PB/2018]`. Sumber `.go.id` terblokir proxy
  saat riset (`docs/PUSTAKA-REGULASI-BMN.md:331`).
- **Masa manfaat**: entri "(lazim)" vs "(terverifikasi)" — validasi ke Lampiran KMK
  295/2019 jo. 266/2023 (`penilaian_utils.py:27`).
- **Ambang & kategori** penggunaan/pengamanan/pemindahtanganan `[perlu verifikasi]`
  (`penggunaan_utils.py:325`, `pengamanan_utils.py:259`, `pemindahtanganan_utils.py:277`).

---

## 6. Kesimpulan

Fondasi kuat: satu identitas aset, kodefikasi 5-level, master pegawai/pejabat/ruangan/
akun, backup dinamis (semua koleksi otomatis tercakup), dan dua integrasi keras
(Pengadaan→Persediaan, laporan tanda-tangan KPB). Yang perlu dimatangkan: **konsistensi
penanda tangan persediaan**, **penyatuan sumber akun**, **verifikasi akun BAS**, dan
**penguatan tautan aset↔master** (opsional-keras) — semuanya bisa dikerjakan bertahap
tanpa merusak alur offline-first yang sudah berjalan.

---

## 7. Status Perbaikan Rekomendasi #1–#5 (Jul 2026)

| # | Rekomendasi | Status | PR / Catatan |
|---|---|---|---|
| 1 | Samakan penanda tangan PDF Persediaan dengan registry Pejabat | **Selesai** | #319 (`_kpb_signer`, fallback setelan) |
| 2 | Satukan sumber akun golongan-1 (117111) | **Selesai** | #320 (`AKUN_PERSEDIAAN_UTAMA` dari `akun_bas`) |
| 3 | Kelola & verifikasi akun neraca persediaan 1171xx | **Selesai** | #321 (endpoint), #322 (UI), #323 (riset). **KOREKSI: 117131 = Bahan Baku** (bukan "untuk Diserahkan"); 117191 dihapus. **117112 & 117128 masih perlu verifikasi Lampiran BAS** (sumber `.go.id` terblokir proxy). |
| 4 | Perkuat tautan pengguna↔pegawai | **Selesai (opt-in)** | #324 (setelan `wajib_pegawai_terdaftar`, default OFF). **`ruangan_id` FK penuh: DITUNDA** (arsitektural — registry field aset + anti-drift). |
| 5 | Auto-draft aset dari Pengadaan | **Menunggu keputusan lingkup** | Endpoint backend menyusul; butuh keputusan pemilik (lingkup UI & kegiatan tujuan). |

**Bonus:** 3 bug UI daftar aset diperbaiki (#325) — filter Nama Pengguna memicu refresh+skeleton;
gap tinggi baris pasca-filter (virtualized) hilang; pesan gagal menyertakan Kode Aset · NUP · Kegiatan.
