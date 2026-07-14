# Masterplan Pengembangan AMAN — Siklus Pengelolaan BMN

> Dokumen perencanaan induk pengembangan bertahap aplikasi **AMAN**
> (Aplikasi Manajemen Aset Negara) dari aplikasi inventarisasi menjadi
> platform siklus penuh pengelolaan Barang Milik Negara.
>
> Disusun: Juli 2026 · Referensi utama: **diagram resmi Kemenkeu "Siklus
> Pengelolaan Barang Milik Negara/Daerah"** (UU 1/2004, PP 27/2014 jo.
> PP 28/2020 — diberikan pemilik proyek sebagai acuan gambaran besar),
> SE-17/MK.1/2024, dan sistem **KERJA-BARENG (SIMAN-G)** —
> https://github.com/ModernIlham/KERJA-BARENG (proyek terdahulu pemilik,
> modul lengkap & berfungsi — dipelajari menyeluruh sebagai referensi desain).
>
> **Asas pengelolaan BMN** (legenda diagram): Fungsional · Kepastian Hukum ·
> Transparansi & Keterbukaan · Efisiensi · Akuntabilitas · Kepastian Nilai.

---

## 1. Ringkasan Eksekutif

AMAN hari ini adalah aplikasi **inventarisasi aset** yang matang: kegiatan
ber-tiket, mode lapangan offline-first, kolaborasi real-time aman (OCC +
locking), kamera + scan QR, peta GIS, 13+ laporan resmi, dan pengesahan
berkekuatan dokumen. Dalam siklus pengelolaan BMN, posisi ini adalah
**Penatausahaan › Inventarisasi**.

Masterplan ini mengarahkan pengembangan selanjutnya:

1. **Matangkan Penatausahaan dahulu** — Pembukuan (DBKP/KIB), Pelaporan
   (LBKP/arsip), dan **Inventarisasi Persediaan** (konsep dari KERJA-BARENG).
2. **Rumah modul sudah berdiri** — Beranda Modul menampilkan seluruh tahap
   siklus; modul yang belum dibangun berstatus *Segera Hadir* lengkap dengan
   konsep & rencana fiturnya (registry: `frontend/src/lib/bmnModules.js`).
3. **Semua modul saling terintegrasi** melalui prinsip arsitektur di Bab 5 —
   satu identitas aset, satu kodefikasi, transaksi sebagai jurnal, dokumen
   sumber sebagai simpul, dan approval sebagai gerbang.
4. **Pengembangan bertahap per fitur** — setiap fitur dikirim kecil-kecil:
   verifikasi → PR → CI hijau → merge → auto-deploy (proses baku di
   `.claude/skills/aman-dev/SKILL.md`).

---

## 2. Posisi Saat Ini

```
SIKLUS PENGELOLAAN BMN/D — diagram resmi Kemenkeu (12 tahap, searah jarum jam)

 1 Perencanaan Kebutuhan (RKBMN·SBSK) → 2 Penganggaran → 3 Pengadaan →
 4 Penggunaan (PSP·alih status·sementara·pihak lain·bersama·BMN idle) →
 5 Pemanfaatan (Sewa·Pinjam Pakai·KSP·BGS·BSG·KSPI·KETUPI·PDF) →
 6 Penilaian (Revaluasi BMN) → 7 Pengamanan (fisik·administrasi·hukum·
 asuransi) → 8 Pemeliharaan → 9 PENATAUSAHAAN ✅ → 10 Pemindahtanganan
 (penjualan·hibah·tukar menukar·penyertaan modal) → 11 Pemusnahan →
 12 Penghapusan → (kembali ke 1)

              ┌────────────────────────────────┐
              │  PENATAUSAHAAN (poros — kita)  │
              │  Pembukuan · INVENTARISASI ✅  │
              │  · Pelaporan  (PMK 181/2016)   │
              └────────────────────────────────┘
   Pembinaan · Pengawasan · Pengendalian melingkupi seluruh siklus
   (pemantauan · investigasi · portofolio aset · analisis SBSK · penertiban)
```

**Yang sudah berjalan (modul Inventarisasi Aset):** kegiatan + tim + satker,
45+ field aset ber-registry, mode lapangan offline penuh, kamera watermark +
scan QR beruntun, peta aset + ekspor KML/KMZ/SHP, klasifikasi SE-17
(ditemukan / tidak ditemukan / berlebih / sengketa), 13+ laporan + kop surat
resmi, pengesahan + kunci kegiatan, audit trail per field, CI/CD otomatis.

**Benih modul lain yang SUDAH tertanam** (jangan dibangun dua kali):

| Benih di modul sekarang | Menjadi bahan modul |
|---|---|
| Pengguna + NIP + jabatan + BAST per aset | Penggunaan (aset pegawai) |
| Klasifikasi Tidak Ditemukan + sub + kronologis | Penghapusan (berkas usulan) |
| Kondisi Rusak Berat + tindak lanjut | Pemusnahan (kandidat) |
| Data sengketa (perkara, pihak) | Pengamanan (daftar pantau) |
| Harga & tahun perolehan | Penilaian / Penyusutan |
| Audit trail per field | Wasdal (penelusuran) |
| Kondisi & jumlah aset per lokasi | Perencanaan (analisis kebutuhan) |

---

## 3. Peta Siklus → Modul Aplikasi

| # | Tahap siklus (diagram resmi) | Modul AMAN | Dasar hukum tahap | Status | Fase |
|---|---|---|---|---|---|
| 9 | Penatausahaan › Inventarisasi Aset | (aplikasi berjalan) | PMK 181/PMK.06/2016 + SE-17/MK.1/2024 | ✅ Aktif — peta: filter+seleksi memfilter titik & unduh GIS + foto popup ke lightbox + skala/kompas/bar metrik (#217); dasbor: kontrol segmented Analytics/Rekapitulasi/Barang Serupa (#215) | 1 |
| 9 | Penatausahaan › Pembukuan | DBKP + KIB | PMK 181/PMK.06/2016 | Sebagian (DBKP #76; KIB tunggu verifikasi lampiran) | 2 |
| 9 | Penatausahaan › Inventarisasi Persediaan | Persediaan + gudang + opname | PMK 181/PMK.06/2016 | Sebagian (inti lengkap #77–85) | 2 |
| 9 | Penatausahaan › Pelaporan | LBKP + arsip lintas kegiatan | PMK 181/PMK.06/2016 | Sebagian (hub #86, posisi neraca #93, rekonsiliasi #94, LBKP #95) | 2 |
| 1 | Perencanaan Kebutuhan | RKBMN + analisis SBSK | PMK 153/PMK.06/2021 (RKBMN); PMK 138/2024 (SBSK) | Sebagian (kandidat RKBMN pemeliharaan #99 + kertas kerja #100) | 4 |
| 2 | Penganggaran | Pagu & status usulan RKBMN → realisasi | PMK 62/2023 + PMK 153/PMK.06/2021 (titik "Integrasi") | Lengkap tahap awal (register usulan #115, sanding akun BAS #123, CSV #163, kalender #165, sanding triwulan #186) | 4 |
| 3 | Pengadaan | Perolehan + dokumen sumber | Perpres 16/2018 jo. 46/2025 | Sebagian (register perolehan #117, arsip #135, CSV #161, tautan Penganggaran #199) | 4 |
| 4 | Penggunaan | PSP · alih status · sementara · pihak lain · bersama · BMN idle · aset pegawai/BAST | PMK 40/2024; PMK 120/2024 (idle) | Lengkap tahap awal (rekap pemegang #87, daftar PDF pemegang #125, BMN idle #126, register SK PSP #129, tiket proses 4 rezim #181/#183, BAST PSP PDF #192, alur pengajuan PSP #194) + **ekspor CSV seluruh register** (idle #212, proses #218, SK PSP #219) | 3 |
| 5 | Pemanfaatan | Sewa · Pinjam Pakai · KSP · BGS · BSG · KSPI · KETUPI + PNBP | PMK 115/PMK.06/2020; fasilitas transaksi PMK 18/2024 + PMK 139/PMK.08/2022 (IKN) — bukan bentuk ke-7 | Lengkap tahap awal (register #108, kontribusi #121, arsip #131, CSV #158, lampiran wasdal #188, atribut fasilitas #190) | 5 |
| 6 | Penilaian | Revaluasi BMN + penyusutan + koreksi nilai | PMK 65/2017 + KMK 295/2019 jo. 266/2023 (penyusutan); Perpres 75/2017 + PMK 118/2017 jo. 57/2018 jo. 107/2019 (revaluasi); PMK 99/2024 (penilaian) | Sebagian (penyusutan #102-#103, koreksi nilai #184) | 5 |
| 7 | Pengamanan | Fisik · administrasi · hukum · Asuransi BMN | PP 27/2014 jo. 28/2020; PMK 43 Tahun 2025 (asuransi) | Lengkap tahap awal (dasbor #88, kasus #169, dokumen #171, sertipikasi #173, checklist #175, polis #177) + **ekspor CSV seluruh register** (polis #205, kasus #213, dokumen #214, checklist #216) | 3 |
| 8 | Pemeliharaan | Jadwal + riwayat + biaya per aset | PP 27/2014 | Sebagian (riwayat+biaya #89, DHPB #90) | 3 |
| 10 | Pemindahtanganan | Penjualan · Hibah · Tukar Menukar · Penyertaan Modal | PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 | Sebagian (register usulan berstatus #111) | 6 |
| 11 | Pemusnahan | Usulan + BA pemusnahan | PMK 83/PMK.06/2016 | Sebagian (register BA #110) | 6 |
| 12 | Penghapusan | SK + arsip aset terhapus | PMK 83/PMK.06/2016 | Sebagian (kandidat usul hapus #104, tiket usulan #106, jejak aset terhapus #197) | 6 |
| ∞ | Pembinaan, Pengawasan & Pengendalian | Pemantauan · investigasi · portofolio aset · analisis SBSK · penertiban | PMK 207/PMK.06/2021 | Sebagian (dasbor pemantauan #113) | 6 |

Konsep ringkas per modul (deskripsi, fitur rencana, integrasi) hidup di
`frontend/src/lib/bmnModules.js` dan tampil di aplikasi (Beranda Modul →
klik kartu). Registry itu dan tabel ini harus selalu selaras.

---

## 4. Pelajaran dari KERJA-BARENG (SIMAN-G)

KERJA-BARENG adalah sistem manajemen aset negara + kepegawaian yang modulnya
lengkap: master barang (aset tetap) & persediaan, 20+ jenis transaksi,
approval maker-checker, gudang, stock opname, KIB A–F, label/QR BMN, laporan,
dokumen sumber, surat, referensi kodefikasi, kepegawaian. Stack serupa
(FastAPI + MongoDB + React) sehingga polanya mudah diadopsi.

### 4.1 Pola yang DIADOPSI

| Pola KERJA-BARENG | Penerapan di AMAN |
|---|---|
| **Kodefikasi 5 level** dari prefix kode barang (digit 1: 1=Persediaan, 2=Tanah, 3=Peralatan & Mesin, 4=Gedung, 5=Jalan/Irigasi, 6=Aset Tetap Lainnya, 7=KDP, 8=ATB) di koleksi `kodefikasi` + endpoint lookup | Jadikan koleksi referensi kodefikasi saat modul Pembukuan/Persediaan dibangun; golongan diturunkan otomatis dari kode — bukan diketik |
| **Identitas aset = kode_barang + NUP; kode_register kunci dedup impor**; `next-nup` pakai *numeric collation* | Sudah selaras (kode 10 digit + NUP + register 32 hex); adopsi numeric collation saat perlu |
| **Pisahkan transaksi stok vs transaksi atribut/nilai** — MASUK/KELUAR/OPNAME menyentuh stok+batch; PERUBAHAN/KOREKSI/REKLASIFIKASI menyentuh atribut & wajib approval | Cetak biru modul transaksi semua fase: dua keluarga handler, jangan dicampur |
| **Approval = staging `pending_changes`** — master baru berubah saat approve (maker-checker, konfigurasi per jenis) | Pola gerbang untuk transaksi sensitif fase 2+; cocok dengan OCC yang sudah ada |
| **Reklasifikasi dua langkah** (KELUAR `PENDING_MASUK` → MASUK menutupnya) | Terapkan saat reklasifikasi antar golongan / persediaan↔aset |
| **Dokumen sumber sebagai simpul** — SPM/SP2D/BAST/kontrak direkam sekali; form transaksi auto-fill dan mengunci field yang tertaut (`dokumen_sumber_id`) | Fondasi modul Pengadaan; transaksi & aset menautkan diri ke dokumen |
| **FIFO batch** untuk valuasi keluar persediaan | Inti modul Persediaan (Bab 7) |
| **Lifecycle pegawai ↔ aset** — distribusi otomatis membuat `aset_pegawai` + riwayat pemegang; pegawai keluar memicu alert aset belum kembali | Cetak biru modul Penggunaan; data pengguna+BAST kita jadi titik awal |
| **Interop SIMAN kelas satu** — import/export ~75 kolom + rekonsiliasi Excel↔DB (ONLY_IN_EXCEL / ONLY_IN_APP / DIFFERENCE) | Fitur rekonsiliasi menyusul di modul Pelaporan (sanding SIMAK/SAKTI) |
| **UX transaksi**: tab berkode-warna + sub-tab kartu berdeskripsi; deep-link tab via URL; kolom tabel bisa dikustomisasi; seleksi lintas halaman; PDF berat via job async + polling | Panduan UI modul transaksi fase 2+ (pola job async sudah kita punya di backup/export) |

### 4.2 Anti-pola yang DIHINDARI (ditemukan di referensi)

1. **Endpoint laporan berisi data dummy** (`laporan_inti.py` menyajikan angka
   generator, bukan DB) — di AMAN semua laporan wajib dari agregasi data riil.
2. **Bug nama koleksi** (`laporan_bmn` PDF query `db.assets` padahal koleksi
   `db.barang` → laporan kosong) — pelajaran: test smoke laporan (kita sudah
   punya harness FakeDB) wajib untuk setiap laporan baru.
3. **Koneksi Mongo per-file + per-request** (setiap route file dan
   `get_current_user` membuka client baru) — AMAN tetap satu client lifespan.
4. **Statistik hardcoded di halaman produksi** (PengamananBMN) — kartu tanpa
   data riil tidak boleh tampil sebagai fakta; itulah alasan modul belum jadi
   di AMAN ditandai *Segera Hadir* secara eksplisit, bukan angka palsu.
5. **Konfigurasi bertumpuk dalam satu koleksi `system_settings` multi-key**
   — pertahankan pola koleksi/pengaturan per domain seperti sekarang.

---

## 5. Prinsip Integrasi Antar Modul (Arsitektur Target)

Semua modul baru wajib tunduk pada tujuh prinsip berikut:

1. **Satu identitas aset.** `kode_barang (10 digit) + NUP` unik per satker;
   `kode_register` (32 hex) kunci lintas sistem. Semua modul merujuk aset
   lewat `asset.id` internal + identitas ini — tidak ada duplikasi master.
2. **Satu kodefikasi.** Koleksi referensi kodefikasi (5 level, diturunkan dari
   prefix kode) dipakai bersama aset & persediaan. Digit pertama memisahkan
   domain: `1` = persediaan, `2–8` = aset tetap/lainnya.
3. **Transaksi sebagai jurnal, master sebagai proyeksi.** Perubahan penting
   (perolehan, mutasi, penghapusan, stok masuk/keluar, opname, koreksi)
   dicatat sebagai dokumen transaksi ber-timestamp dengan `*_sebelum/sesudah`;
   master menyimpan keadaan terkini. Laporan periode dibangun dari jurnal.
4. **Dokumen sumber sebagai simpul.** Kontrak/SPM/BAST direkam sekali di satu
   koleksi; transaksi & aset menautkan `dokumen_sumber_id`. Form melakukan
   auto-fill + mengunci field yang tertaut.
5. **Approval sebagai gerbang, OCC sebagai fondasi.** Transaksi sensitif
   menyimpan `pending_changes` sampai disetujui; semua tulis tetap ber-OCC
   (version/If-Match) + Idempotency-Key seperti sekarang.
6. **Offline-first tidak boleh mundur.** Modul lapangan baru (opname
   persediaan!) memakai pola snapshot + antrean simpan yang sudah terbukti.
   Modul kantor (pembukuan, approval) boleh online-only pada rilis awal.
7. **Registry anti-drift.** Setiap entitas baru mengikuti pola
   `backend/asset_fields.py`: satu registry field → proyeksi list, PATCH,
   audit, CSV, template impor + unit test penjaga. UI modul terdaftar di
   `frontend/src/lib/bmnModules.js`.

---

## 5A. Status Integrasi Antar-Modul & Daftar Gap (audit 2026-07-13)

Audit lintas-modul terhadap 5 prinsip Bab 5. Kepatuhan saat ini:

| Prinsip | Status | Ringkas bukti |
|---|---|---|
| 1. Satu identitas aset | ✅ Patuh (risiko drift) | Semua modul merujuk `asset_id` + snapshot `asset_code/NUP`; snapshot **tak disegarkan** bila master berubah |
| 2. Satu kodefikasi | ⚠️ Sebagian | Golongan **diturunkan** dari prefix di mana-mana; tapi kodefikasi **bukan FK tervalidasi** saat create aset/persediaan |
| 3. Transaksi = jurnal, master = proyeksi | ⚠️ Sebagian (Persediaan + **Penghapusan** + **Revaluasi** + **Pemindahtanganan** + Pemeliharaan) | **Penghapusan** proyeksi master saat SK terbit (#234); **Revaluasi** proyeksi `nilai_wajar_terakhir` (#254) & laporan posisi memakainya (#255); **Pemindahtanganan** *selesai* proyeksi `dihapus` (#256); Persediaan penuh; Pemeliharaan proyeksi kondisi. *Tersisa:* BA Pemusnahan final belum proyeksi langsung |
| 4. Dokumen sumber = simpul | ❌ Belum ada | `dokumen_sumber_id` 0 kecocokan; dokumen diketik ulang per modul |
| 5. Approval = gerbang, OCC fondasi | ❌ Melanggar | `pending_changes` 0; OCC penuh hanya di `assets.py`; modul lain cek peran saja |

**Ringkasan status integrasi (per 2026-07):** rangkaian PR kecil menutup gap
berdampak-tertinggi lebih dulu.

- ✅ **TUNTAS — Prinsip 3 (transaksi hilir → master):** Penghapusan proyeksi
  `dihapus` saat SK terbit (#234); Revaluasi proyeksi `nilai_wajar_terakhir`
  (#254) & laporan POSISI/NILAI memakainya lewat `nilai_buku_aset` (#255);
  Pemindahtanganan *selesai* proyeksi `dihapus` (#256). Semua *reuse* mesin
  laporan hilir (penyaringan posisi #248/#249 + tombstone mutasi LBKP #253).
- ✅ **TUNTAS — gap #1 double-count** aset dihapus di seluruh laporan
  posisi/nilai + mutasi (#248/#249/#253).
- ✅ **TUNTAS — rantai perencanaan→pengadaan (FK + snapshot):** Perencanaan
  (RKBMN) → Penganggaran `rkbmn_id` (#257); Pengadaan → Penganggaran `penganggaran_id`
  (#199); Pengadaan → Aset dua arah `perolehan_id` (#258); Persediaan masuk →
  Perolehan `perolehan_id` (#259) — **simpul Dokumen Sumber (Prinsip 4)** kini
  dirujuk aset & persediaan.
- ⏳ **TERSISA (fitur lebih besar, perlu desain khusus):** dasar **penyusutan**
  memakai nilai wajar (revaluasi mengganti basis + sisa masa manfaat per PSAP);
  **OCC/approval** seragam `pending_changes` (Prinsip 5); **kodefikasi** sebagai
  FK tervalidasi (Prinsip 2); **segarkan snapshot identitas** aset basi (Prinsip
  1); proyeksi master dari **BA Pemusnahan** final; auto-daftar draft aset dari
  perolehan.

**Daftar gap (dampak tertinggi → rendah), untuk ditutup bertahap per PR kecil:**

1. **Master tak diproyeksikan dari transaksi hilir** (Prinsip 3) — aset yang
   dimusnahkan/dipindahtangankan/direvaluasi tetap "hidup & bernilai penuh" di
   master → laporan resmi (DBKP/neraca/penyusutan) bisa *double-count*. Cicil per
   modul. ✅ **Penghapusan sudah:** saat **SK terbit**, master ditandai
   `dihapus=True` + jejak SK (`penghapusan.{nomor_sk,tanggal_sk,usulan_id}`) +
   `version` di-`$inc` (bust cache/OCC) + audit `action="penghapusan"` (#234).
   *Sengaja scoped:* field laporan (`inventory_status/condition/purchase_price`)
   TAK diubah → tanpa regresi. ✅ **Penyaringan aset `dihapus` dari laporan
   POSISI/NILAI sudah** — DBKP, Posisi BMN di Neraca, rekap penyusutan (#248),
   dan rekonsiliasi XLSX SAKTI (#249) kini mengecualikan `dihapus=True` lewat
   helper bersama `active_asset_filter` → berhenti *double-count* & sandingan
   SAKTI selaras. ✅ **Laporan MUTASI (LBKP & CaLBMN) juga sudah** — penghapusan
   via SK (`dihapus=True`) kini tampil sebagai **mutasi kurang** di periode SK
   terbit lewat helper murni `tombstones_penghapusan` + `build_lbkp_rows` yang
   sadar-tanggal-SK (#253), sehingga identitas *saldo akhir = awal + tambah −
   kurang* tetap seimbang (diuji unit). ✅ **Revaluasi Penilaian kini
   memproyeksi master** — saat koreksi nilai *tercatat SAKTI*, aset ditandai
   `nilai_wajar_terakhir` + jejak `revaluasi.{...}` + `$inc version` + audit
   `action="revaluasi"` (#254, helper murni `build_asset_revaluasi_projection`,
   best-effort/idempoten spt #234); `purchase_price` historis TAK ditimpa.
   ✅ **Laporan POSISI/NILAI kini MEMAKAI `nilai_wajar_terakhir`** — helper murni
   `nilai_buku_aset(a)` (= nilai wajar revaluasi bila `is not None` — 0 pun
   dihormati, jika tidak `purchase_price`) menggantikan `purchase_price` mentah di
   `build_dbkp_rows` (DBKP + Posisi BMN di Neraca) dan rincian per-NUP rekonsiliasi
   XLSX SAKTI (Sheet 2 kini *tie-out* dgn total Sheet 1), #255. *Sengaja scoped:*
   dasar penyusutan (`rekap_penyusutan`) & laporan MUTASI (LBKP/CaLBMN — revaluasi
   = jenis mutasi tersendiri) TAK diubah → langkah terpisah. ✅ **Pemindahtanganan
   kini memproyeksi master** — saat usulan *selesai* (SK Penghapusan terbit), tiap
   aset ditandai `dihapus=True` + jejak `penghapusan.{jalur:"pemindahtanganan",
   bentuk, nomor_sk, tanggal_sk}` + `$inc version` + audit (#256, helper murni
   `build_asset_pemindahtanganan_projection`, best-effort/idempoten spt #234).
   MEMAKAI ULANG bentuk marker penghapusan sehingga penyaringan posisi
   (#248/#249) & tombstone mutasi LBKP (#253) ikut otomatis. *Tersisa:* dasar
   penyusutan memakai nilai wajar, serta proyeksi master dari **BA Pemusnahan**
   final (Pemusnahan sudah ber-FK ke usulan Penghapusan #228 → proyeksi ikut saat
   SK penghapusan itu terbit; proyeksi langsung dari BA belum).
2. ⚠️ **Simpul Dokumen Sumber makin lengkap** (Prinsip 4) — record perolehan
   Pengadaan kini menjadi node yang **aset** rujuk balik via `perolehan_id` +
   snapshot (#258, gap #6) **dan** yang **transaksi masuk persediaan** rujuk via
   `perolehan_id` + snapshot di jurnal (#259, helper murni `snapshot_perolehan`).
   *Tersisa:* auto-daftar draft aset baru dari perolehan (pra-isi).
3. **Approval `pending_changes` + OCC belum seragam** (Prinsip 5).
4. ✅ **Perencanaan (RKBMN) → Penganggaran kini ber-FK** — usulan penganggaran
   menyimpan `rkbmn_id` + snapshot beku (`rkbmn_uraian/tahun/jenis/unit`) dari
   usulan RKBMN sumber saat dibuat (#257, helper murni `snapshot_rkbmn`, tiru
   pola `snapshot_penganggaran` Pengadaan→Penganggaran #199). Sebelumnya dua
   register paralel tanpa taut — kini rantai Perencanaan→Penganggaran→Pengadaan
   tertaut penuh.
5. ✅ **Pemusnahan → Penghapusan kini ber-FK** (`sumber_ba_id` + `sumber_ba_nomor`
   pada `usulan_penghapusan`, #228) — sebelumnya hanya teks bebas. ✅ **Pemindahtanganan
   *selesai* kini memproyeksi master** (`dihapus` + jejak SK, #256) sehingga aset
   yang dipindahtangankan berhenti terhitung di laporan. *Tersisa:* tautan
   Pemindahtanganan → tiket `usulan_penghapusan` masih via string `nomor_sk_penghapusan`
   (belum FK id) — dampak laporan sudah tertangani lewat proyeksi master.
6. ✅ **Pengadaan → Aset kini DUA arah** — saat baris barang perolehan ditautkan
   ke aset (`buat_perolehan`/`tautkan_barang`), aset menyimpan `perolehan_id` +
   snapshot beku dokumen sumber (BAST/kontrak) balik (#258, helper murni
   `build_asset_perolehan_projection`, best-effort, **tanpa** version bump agar
   tak memicu OCC 409 palsu). *Tersisa:* auto-daftar draft aset baru dari
   perolehan (pra-isi) belum.
7. ⚠️ **Kodefikasi bukan FK tervalidasi** (Prinsip 2). ✅ **Validasi READ-ONLY
   sudah** — helper murni `level_terdaftar_terdalam(kode, terdaftar)` + endpoint
   `GET /integritas/kodefikasi-aset` melaporkan kode aset yang golongan/level-nya
   TAK terdaftar di `db.kodefikasi` (peringatan non-blocking, agregasi per kode
   distinct; #262). *Tersisa:* validasi saat create/impor aset (soft-warning) &
   lengkapi referensi.
8. ⚠️ **Snapshot identitas aset basi** (Prinsip 1) — disalin, tak disegarkan.
   ✅ **Deteksi READ-ONLY sudah** — helper murni `identitas_drift(snapshot,
   master)` + endpoint `GET /integritas/identitas-penghapusan` melaporkan
   snapshot `asset_code/NUP/asset_name` yang basi (atau master hilang) di
   register `usulan_penghapusan` vs master terkini (#261). *Tersisa:* perluas
   deteksi ke register hilir lain (pemeliharaan/pemindahtanganan/…) & penyegaran
   otomatis saat master aset diedit.

> Aturan: tiap gap ditutup sebagai fitur kecil ber-PR (verifikasi → CI → deploy),
> dengan proyeksi master memakai pola OCC `find_one_and_update` bersyarat +
> audit log yang sudah terbukti di `assets.py`.

---

## 6. Rumah Modul (sudah dibangun)

- **Beranda Modul** (`frontend/src/pages/ModuleHomePage.jsx`) — halaman
  pertama setelah login: peta siklus dengan Penatausahaan sebagai poros.
  Inventarisasi Aset = kartu aktif (masuk ke aplikasi berjalan); modul lain =
  kartu *Segera Hadir* → dialog konsep (deskripsi, fitur rencana, integrasi,
  fase roadmap).
- Pilihan modul per-tab (sessionStorage) — reload di tengah pekerjaan lapangan
  tidak melempar keluar; login/tab baru kembali ke beranda.
- Tombol **Modul** di halaman Pilih Kegiatan mengembalikan ke beranda.
- Menambah/mengubah modul = edit `frontend/src/lib/bmnModules.js` saja.

Saat sebuah modul mulai dibangun: ubah `status` di registry menjadi `aktif`,
tambahkan `onEnter` route/halamannya — kartunya otomatis berubah dari konsep
menjadi pintu masuk.

---

## 7. Konsep Rinci: Inventarisasi Persediaan

Referensi langsung: `routes/persediaan.py`, `persediaan_transaksi.py`,
`persediaan_transaksi_grouped.py`, `gudang.py`, `opname.py` di KERJA-BARENG
(dipelajari baris per baris) — disesuaikan ke fondasi AMAN.

> ✅ **Tervalidasi regulasi** (riset 2026-07-12, rincian di
> `docs/PUSTAKA-REGULASI-BMN.md` §3): kebijakan akuntansi pemerintah pusat
> memakai **pencatatan perpetual + penilaian FIFO per layer** sejak TA 2021
> (PMK 234/2020; SAKTI Modul Persediaan) — desain FIFO per batch di bawah
> ini selaras. Enum jenis transaksi wajib memetakan 1:1 ke daftar transaksi
> SAKTI (saldo awal, pembelian, transfer/hibah masuk-keluar, pemakaian,
> usang/rusak dua-tahap, koreksi, opname) dan tiap kode barang termapping
> ke akun neraca 1171xx — lihat pustaka §3.2–3.4.

### 7.1 Entitas

| Entitas | Field kunci (dari referensi, disesuaikan) |
|---|---|
| `persediaan` (master) | kode_barang **16 digit berawalan '1'** (10 digit → 6 digit auto-increment), NUP otomatis, nama, merk/tipe, satuan, golongan (auto dari kodefikasi), lokasi/ruang/gudang, `stok`, `batas_kritis`, `expired_date`, `batches[]`, foto, satker |
| `batch` (embedded, FIFO) | batch_id, tanggal, qty, **harga per batch**, ref nota dinas/dokumen, kedaluwarsa per batch |
| `transaksi_persediaan` (jurnal) | jenis (`in`/`out`/`opname`), persediaan_id, jumlah, nilai_satuan, total, **stok_sebelum/sesudah**, unit_penerima, petugas, dokumen: no_bukti, tgl_dokumen, tgl_buku, jenis_dokumen, no_kontrak, PPK, penyedia+NPWP, `dokumen_sumber_id`, bukti_fotos[] |
| `gudang` | identitas gudang + ringkasan isi; movement: distribusi / pengembalian / transfer antar gudang |
| `opname` | per item: stok_sistem vs stok_fisik → selisih, keterangan, petugas; **penyesuaian otomatis** + jurnal `jenis="opname"` |

### 7.2 Alur inti

1. **Masuk (stock-in):** buat batch FIFO baru (qty, harga input, kedaluwarsa)
   → stok naik → `nilai_satuan` master dihitung ulang rata-rata tertimbang
   (untuk tampilan) → jurnal `in` + tautan dokumen sumber. Mode **massal**:
   banyak item dalam satu dokumen (no bukti/kontrak/PPK sama) — riwayat
   dikelompokkan per (dokumen, no bukti, jenis, hari).
2. **Keluar (stock-out):** validasi stok cukup → konsumsi batch **FIFO**
   (tertua dulu; sebagian/habis per batch) → nilai keluar = jumlah nilai batch
   terpakai (bukan rata-rata) → jurnal `out` + unit penerima + rincian batch
   terpakai. Data lama tanpa batch → batch legacy sintetis dari stok berjalan.
3. **Stock opname:** hitung fisik per item → selisih = fisik − sistem → stok
   master disetel ke fisik + jurnal penyesuaian `opname` → Berita Acara opname
   (pola cetak: grouping per sub-kelompok + 3 penandatangan tersimpan).
4. **Peringatan:** stok ≤ `batas_kritis` dan/atau kedaluwarsa → daftar pantau
   + **nota dinas otomatis (PDF)** untuk pengadaan/penghapusan persediaan.
5. **Gudang:** distribusi ke unit, pengembalian, transfer antar gudang —
   setiap gerakan tercatat sebagai movement.

### 7.3 Penyesuaian ke fondasi AMAN (perbaikan atas referensi)

- **Atomicity:** update stok + push jurnal di referensi adalah dua tulis
  terpisah (rawan setengah jadi). Di AMAN: `find_one_and_update` bersyarat
  (stok cukup + version) → tulis jurnal; kompensasi bila gagal — pola OCC yang
  sudah kita pakai.
- **Offline:** opname & keluar-harian adalah pekerjaan lapangan → snapshot
  persediaan per gudang + antrean simpan offline (pola inventarisasi aset).
- **Kegiatan opname ber-tiket:** opname berkala dibungkus "kegiatan" seperti
  inventarisasi aset (tim, periode, pengesahan BA, kunci) — konsistensi UX.
- **Registry field persediaan** (`persediaan_fields.py`) + test anti-drift,
  meniru `asset_fields.py`.
- **Laporan dari jurnal:** posisi stok, mutasi per periode (saldo awal →
  masuk → keluar → saldo akhir), kartu barang — semua agregasi
  `transaksi_persediaan`, tidak ada data dummy.

### 7.4 Urutan pembangunan modul Persediaan (fitur = PR kecil)

> Catatan urutan Fase 2 (2026-07-12): **KIB ditunda** sampai field per
> jenis terverifikasi dari Lampiran PMK 181 (aturan "regulasi dulu, kode
> kemudian" — pustaka §6 butir 1); DBKP sudah jalan (#76), pembangunan
> berlanjut ke Persediaan.

1. ✅ (#77) Registry field + model + koleksi + CRUD master (kodefikasi '1', NUP auto)
   — UI master ✅ (#78).
2. Import/export Excel master persediaan + template. *(tersisa)*
3. ✅ (#79) Transaksi masuk + batch FIFO + jurnal (massal per dokumen: *tersisa*).
4. ✅ (#80) Transaksi keluar FIFO (konsumsi layer tertua) + unit penerima
   (bukti foto: *tersisa*).
5. ✅ (#81) Peringatan kritis/kedaluwarsa + nota dinas PDF.
6. Gudang + movement (distribusi/pengembalian/transfer). *(tersisa)*
7. ✅ (#83) Opname + penyesuaian otomatis + kertas kerja & BAOF PDF
   (mode lapangan offline: *tersisa*).
8. ✅ (#82) Laporan posisi & mutasi periode dari jurnal (kartu barang &
   arsip lintas kegiatan: *tersisa*).

---

## 8. Roadmap Fase

> Setiap fase dipecah menjadi fitur-fitur kecil; satu fitur = satu PR
> ter-CI + terdeploy. Fase berikutnya tidak menunggu fase sebelumnya
> sempurna 100% — cukup fondasinya terpasang.

| Fase | Lingkup | Deliverable utama | Prasyarat |
|---|---|---|---|
| **1 — sekarang** | Pematangan Inventarisasi Aset | Perbaikan lapangan berkelanjutan; **rumah modul** ✅; masterplan ✅ | — |
| **2** | Penatausahaan penuh | Kodefikasi referensi; Pembukuan (DBKP + KIB A–F); **Persediaan** (Bab 7); Pelaporan (LBKP + arsip lintas kegiatan) — *inti ✅: kodefikasi (#73-74), DBKP (#76), persediaan (#77-85), hub Pelaporan (#86), posisi neraca (#93), rekonsiliasi XLSX (#94), LBKP mutasi (#95), CaLBMN pra-isi bab I–V (#144, §2.3a), LKB per NUP + ringkasan kondisi (#146, §2.3b), periode ber-kunci + penanda FINAL (#148), tenggat penyampaian konfigurabel (#150 — implikasi Pelaporan §2.3 tuntas), filter Lokasi/Gudang persediaan (#152), pindah gudang ber-jurnal (#154); tersisa: KIB (tunggu verifikasi lampiran PMK 181)* | Kodefikasi dibangun paling awal (dipakai semua) |
| **3** | Penggunaan + Pengamanan + Pemeliharaan | PSP + alih status/sementara/pihak lain/bersama (PMK 40/2024); BMN idle (PMK 120/2024); aset per pegawai/jabatan + BAST digital + alert pegawai keluar; pengamanan fisik/administrasi/hukum + asuransi; jadwal & riwayat & biaya pemeliharaan — *tahap awal ✅: rekap pemegang (#87), dasbor pengamanan (#88), riwayat & biaya pemeliharaan + telaah kapitalisasi (pustaka §4); daftar barang per pemegang PDF (#125), daftar pantau BMN idle berjenjang (#126), register SK PSP 5 jenis (#129), arsip lampiran SK PSP (#137); ekspor CSV riwayat pemeliharaan (#167); tiket proses 4 rezim penggunaan PMK 40/2024 (#181, #183); BAST penetapan status penggunaan PDF per SK (#192); alur pengajuan PSP berstatus (#194 — daftar "menyusul" Penggunaan tuntas); register BMN bermasalah/sengketa berstatus (#169, pustaka §11); arsip dokumen kepemilikan per aset + lampiran scan (#171); status sertipikasi K1-K4 per dokumen sertipikat (#173); checklist pengamanan per aset per jenis (#175); register polis Asuransi BMN PMK 43/2025 (#177); **ekspor CSV seluruh register Penggunaan (idle #212, proses #218, SK PSP #219) & Pengamanan (polis #205, kasus #213, dokumen #214, checklist #216)*** | Data pengguna+BAST fase 1 |
| **4** | Perencanaan Kebutuhan + Penganggaran + Pengadaan | RKBMN (PMK 153/2021) + analisis SBSK (PMK 138/2024) + sanding data eksisting; jembatan usulan→anggaran→realisasi; dokumen sumber (simpul); registrasi perolehan → auto-daftar master — *tahap awal ✅: saringan kelayakan RKBMN pemeliharaan (#99) + kertas kerja XLSX siap isi (#100), memakai balik kondisi aset + riwayat biaya Pemeliharaan; usulan RKBMN per unit berstatus + SPTJM/reviu APIP (#179, kalkulator SBSK menunggu lampiran PMK 138/2024); register usulan penganggaran berstatus diusulkan→telaah→DIPA→realisasi (#115, pustaka §9); register perolehan per BAST/kontrak + checklist dokumen sumber + tautan aset (#117, pustaka §10); sanding per akun BAS (#123); arsip lampiran berkas perolehan (#135); ekspor CSV register perolehan (#161); tautan paket perolehan → usulan penganggaran (#199, jembatan #117↔#115); ekspor CSV register penganggaran (#163); kalender penganggaran konfigurabel ber-pengingat (#165); sanding realisasi per triwulan per tahun anggaran (#186 — daftar "menyusul" Penganggaran tuntas)* | Kodefikasi (fase 2) |
| **5** | Pemanfaatan + Penilaian | Perjanjian per bentuk (Sewa/Pinjam Pakai/KSP/BGS/BSG/KSPI/KETUPI — PMK 115/2020; fasilitas transaksi PMK 18/2024, bukan bentuk ke-7) + kalender jatuh tempo + PNBP; revaluasi BMN (Perpres 75/2017 + PMK 118/2017 jo. perubahannya; penilaian PMK 99/2024) + penyusutan per golongan — *tahap awal ✅: penyusutan garis lurus semesteran + halaman Penilaian (#102-#103, §5) + referensi masa manfaat dikelola (#107) + register koreksi nilai per aset (revaluasi LHIP/inventarisasi/temuan/pencatatan + dampak masa manfaat + status pencatatan SAKTI) (#184, pustaka §13) + register pemanfaatan 6 bentuk (#108, §6) + kontribusi tahunan (#121) + arsip lampiran (#131) + ekspor CSV (#158) + lampiran wasdal terpisah per perjanjian (#188) + atribut fasilitas transaksi PMK 18/2024 / PMK 139/2022-IKN pada KSP/BGS-BSG (#190, pustaka §6.a)* | Pembukuan (fase 2) |
| **6** | Hilir + Wasdal | Pemindahtanganan (Penjualan/Hibah/Tukar Menukar/Penyertaan Modal — PMK 111/2016 jo. 165/2021); Pemusnahan (kandidat dari rusak berat); Penghapusan (kandidat dari tidak ditemukan) — PMK 83/2016; wasdal PMK 207/2021: pemantauan · investigasi · portofolio aset · analisis SBSK · penertiban — *tahap awal ✅: kandidat usul hapus (#104), tiket usulan berstatus (#106), register BA pemusnahan (#110), register pemindahtanganan 4 bentuk (#111, pustaka §7), dasbor pemantauan wasdal 5 objek (#113, pustaka §8), PDF BA pemusnahan + usulan hapus otomatis (#119-#120), laporan wasdal PDF pra-isi (#122), lampiran bukti pemusnahan (#132), arsip lampiran usulan penghapusan (#134), arsip lampiran pemindahtanganan (#138), register penertiban 15 hari kerja (#140), pemantauan insidentil 10+5 hari kerja + PDF BA (#142), arsip lampiran tiket insidentil (#156), ekspor CSV register hilir (#158-#159, #161), Jejak Aset Terhapus read-only dari log audit (#197)* | Approval gerbang (dibangun di fase 2–3) |

**Aturan emas antar fase:** modul baru TIDAK menyalin data modul lama — ia
merujuk. Sebelum membangun modul, tulis dulu kontrak integrasinya (field apa
yang dibaca dari mana, transaksi apa yang ditulis ke mana) di dokumen ini.

---

## 9. Cara Kerja Bertahap per Fitur

Proses baku (rinci + perintah eksak di `.claude/skills/aman-dev/SKILL.md`):

1. **Rancang kecil** — satu fitur, satu PR; jika desain melebar, pecah.
2. **Bangun mengikuti registry & konvensi** (Bab 5 prinsip 7).
3. **Verifikasi lokal** — pytest unit + eslint + `yarn build` + smoke laporan
   bila menyentuh laporan.
4. **PR draft → CI hijau → squash merge** — CI menjaga test/lint/build.
5. **Auto-deploy** ke VPS Hostinger saat merge ke `main`; pantau sampai sukses.
6. **Dokumentasi ikut PR** — CHANGELOG selalu; README/PRD bila fitur besar;
   registry modul bila menyentuh status modul.

Definisi Selesai (DoD) per fitur: CI hijau · terdeploy · UI Indonesia ·
jalan offline (bila fitur lapangan) · tercatat di CHANGELOG · tanpa data
dummy · tanpa regresi lint/test.

---

## 10. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| Lingkup fase 2 membengkak (3 modul) | Pecah per fitur (§7.4); kodefikasi dulu; Persediaan bisa dirilis bertahap (master → transaksi → gudang → opname) |
| Duplikasi konsep aset vs persediaan | Digit pertama kode memisahkan domain; UI & koleksi terpisah, kodefikasi & pola transaksi sama |
| Modul kantor merusak fondasi offline | Prinsip 6: fitur lapangan wajib offline; fitur kantor online-only dulu, jangan menyentuh jalur simpan lapangan |
| Data dummy menyusup ke laporan (pelajaran referensi) | Harness smoke FakeDB wajib untuk laporan baru; larangan keras di DoD |
| Beban VPS bertambah per modul | Tetap satu backend modular (routes per modul); pantau; skala vertikal dulu, pisah layanan hanya bila terbukti perlu |
| Kehilangan arah antar sesi pengembangan | Dokumen ini + registry modul + SKILL.md = memori proyek; perbarui setiap kali fase bergeser |

---

*Dokumen hidup — perbarui saat fase bergeser, modul naik status, atau
kontrak integrasi baru disepakati. Pasangan dokumen:
`frontend/src/lib/bmnModules.js` (konsep di aplikasi) dan
`.claude/skills/aman-dev/SKILL.md` (proses kerja).*
