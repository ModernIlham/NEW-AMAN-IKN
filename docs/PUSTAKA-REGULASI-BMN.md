# Pustaka Regulasi & Alur Bisnis BMN

> Rangkuman riset regulasi dan praktik resmi sebagai **bahan rujukan wajib**
> sebelum membangun modul apa pun di AMAN — dipakai bersama
> `docs/MASTERPLAN-SIKLUS-BMN.md`. Disusun dari riset internet Juli 2026
> (sumber di §15). Butir bertanda **[perlu verifikasi]** belum terbaca dari
> teks asli peraturan (PDF JDIH tidak terjangkau dari lingkungan riset) —
> pastikan ke dokumen aslinya saat menulis spesifikasi teknis modulnya.
>
> Aturan main: bila alur bisnis sebuah fitur belum tercakup di sini,
> RISET DULU (internet + peraturan), tambahkan ke pustaka ini, baru bangun.

---

## 1. Peta Regulasi Induk

| Domain | Aturan | Catatan |
|---|---|---|
| Induk pengelolaan BMN/D | UU 1/2004; **PP 27/2014 jo. PP 28/2020** | Memuat kewajiban inventarisasi (5 tahunan; persediaan & KDP tahunan) |
| Penatausahaan (pembukuan·inventarisasi·pelaporan) | **PMK 181/PMK.06/2016** | Menggantikan PMK 120/2007; status "masih berlaku tanpa perubahan" [perlu verifikasi] |
| Penggolongan & kodefikasi barang | **PMK 29/PMK.06/2010** (sebelumnya 97/2007), lampiran diubah berkali-kali (terakhir KMK 532/KM.6/2015+) | Kode 10 digit: Golongan·Bidang·Kelompok·Sub·Sub-sub + NUP; golongan 1=Persediaan … 8=Aset Lainnya [urutan perlu verifikasi lampiran] |
| Kebijakan akuntansi pemerintah pusat | PMK 225/2019 → **PMK 234/2020 (FIFO mulai TA 2021)** → 231/2022 jo. 57/2023 → **PMK 100/2025** (LK TA 2025) | Bab VI = Kebijakan Akuntansi Persediaan [redaksi FIFO di PMK 100/2025 perlu verifikasi] |
| Standar akuntansi persediaan | **PSAP 05** (PP 71/2010) | Perpetual/periodik; FIFO/rata-rata; harga terakhir hanya bila tidak material |
| Penggunaan | PMK 40/2024; BMN idle PMK 120/2024 | Lihat diagram siklus resmi |
| Pemanfaatan | PMK 115/PMK.06/2020; fasilitas transaksi PMK 18/2024 (+ PMK 139/PMK.08/2022 khusus IKN) | — |
| Pemindahtanganan | PMK 111/PMK.06/2016 jo. 165/PMK.06/2021 | — |
| Pemusnahan & Penghapusan | PMK 83/PMK.06/2016 | — |
| Wasdal | PMK 207/PMK.06/2021 | Laporan wasdal via SIMAN — domain terpisah dari LBKP |
| Revaluasi BMN | PMK 97/PMK.06/2019 (per diagram resmi) | [perlu verifikasi — riset menemukan 97/2007 = kodefikasi; cek nomor pasti aturan revaluasi] |
| Ekosistem aplikasi Kemenkeu | **SAKTI** (modul Persediaan, Aset Tetap, GLP — menggantikan SIMAK-BMN sejak 2022), **MonSAKTI** (rekonsiliasi, ganti e-Rekon&LK), **SIMAN v2** (pengelolaan/wasdal; PMK 118/2023) | **Posisi AMAN: pendamping/penyiap data — bukan pengganti pencatatan resmi; output wajib mudah direkonsiliasi/diekspor mengikuti struktur SAKTI** |

---

## 2. Penatausahaan (PMK 181/PMK.06/2016)

### 2.1 Pembukuan

- **Daftar wajib tingkat UAKPB (satker):** DBKP per golongan (Persediaan;
  Tanah; Peralatan & Mesin; Gedung & Bangunan; Jalan-Irigasi-Jaringan; Aset
  Tetap Lainnya; KDP; Barang Bersejarah; Aset Lainnya); **Buku Barang**
  (Intrakomptabel, Ekstrakomptabel, Barang Bersejarah, Persediaan, KDP);
  **DBR** (Daftar Barang Ruangan — per ruangan, rangkap 2, dimutakhirkan
  setiap perpindahan) & **DBL** (barang di luar ruangan); label registrasi.
- **Intra vs ekstrakomptabel** dari nilai satuan minimum kapitalisasi:
  ≥ Rp1.000.000 (peralatan & mesin), ≥ Rp25.000.000 (gedung & bangunan);
  di bawahnya = ekstrakomptabel (tetap dibukukan, tidak masuk neraca).
  Barang bersejarah: kuantitas tanpa nilai. **Ambang = parameter aplikasi**
  (bisa berubah oleh aturan baru).
- **KIB resmi BMN = 6 jenis per aset**: Tanah; Gedung & Bangunan; Bangunan
  Air; Alat Angkutan Bermotor; Alat Besar; Senjata Api. (Penamaan huruf
  A–F adalah konvensi BMD/Permendagri — jangan dicampur.) Field indikatif:
  Tanah (luas, alamat, sertifikat — KIB per sertifikat, penggunaan); Gedung
  (luas, lantai, tahun, IMB, rujukan KIB tanah); Kendaraan (merk/tipe,
  no. polisi, BPKB, rangka/mesin); Senjata (kaliber, no. pabrik).
  **[Field lengkap per jenis: perlu verifikasi Lampiran PMK 181.]**

**Implikasi AMAN:** flag intra/ekstra otomatis dari harga vs ambang per
golongan (ambang dapat dikonfigurasi); entitas **Ruangan** + relasi
barang→ruangan (cetak DBR/DBL, riwayat pindah); form KIB per 6 jenis
dengan field berbeda; dukungan barang bersejarah (qty tanpa nilai).

### 2.2 Inventarisasi

- **Frekuensi:** sensus min. 1× per **5 tahun** (selain persediaan & KDP);
  **persediaan & KDP min. 1× per tahun** — praktik LK: **opname tiap
  semester** sebelum pelaporan.
- **Tahapan:** Persiapan (SK tim, rencana kerja, dokumen sumber, label
  sementara, Kertas Kerja) → Pelaksanaan (cek fisik per ruangan/luar
  ruangan, kondisi B/RR/RB, label sementara, verifikasi vs database,
  klasifikasi) → Pelaporan (**LHI** memuat **BAHI** + lampiran: **RHI**,
  **DBHI** 6 kategori: Baik/RR/RB/**Berlebih**/**Tidak Ditemukan**/
  **Sengketa**, Surat Pernyataan; persediaan: **BA Opname Fisik** dengan
  penghitung+saksi+mengetahui) → Tindak lanjut (pemutakhiran DBR/DBL/KIB,
  label permanen; tidak ditemukan → penelusuran/TGR/usul hapus; RB → usul
  hapus). Penyampaian hasil ke Pengelola Barang **maks. 3 bulan** setelah
  selesai [nomor pasal perlu verifikasi].
- ✅ Klasifikasi 6 kategori DBHI & laporan LHI/BAHI/RHI/DBHI **sudah
  diimplementasikan** modul Inventarisasi Aset AMAN.

**Implikasi AMAN (penajaman berikutnya):** penjadwalan siklus (pengingat
sensus 5-tahunan, opname semesteran, tenggat 3 bulan LHI); penanggung
jawab per ruangan; tindak lanjut per barang sebagai tiket berstatus
(usul hapus / TGR / penelusuran) — jembatan ke modul Penghapusan.

### 2.3 Pelaporan

- **LBKP semesteran & tahunan**, komponen: Intrakomptabel, Ekstrakomptabel,
  Gabungan, Persediaan, KDP, Aset Tak Berwujud/Lainnya, Barang Bersejarah,
  **Laporan Posisi BMN di Neraca**, penyusutan, **CaLBMN**; tahunan +
  **Laporan Kondisi Barang (LKB)** [rincian perlu verifikasi lampiran].
- **Jenjang:** UAKPB → UAPPB-W (atau langsung E1) + **KPKNL**; UAPPB-W →
  UAPPB-E1 + Kanwil DJKN; E1 → UAPB; UAPB → Menkeu c.q. DJKN (LBMN
  nasional). **Rekonsiliasi:** internal UAKPB↔UAKPA otomatis di SAKTI
  (pantau MonSAKTI); eksternal semesteran dengan KPKNL/Kanwil DJKN.
- Jadwal rinci ditetapkan per periode (contoh riil Unaudited TA 2025:
  UAKPB ≤ 3 Feb 2026) → **tenggat harus dapat dikonfigurasi per periode**.

**Implikasi AMAN:** entitas Periode Pelaporan (Sem I / Sem II-Tahunan /
Unaudited / Audited) + kunci periode; generator LBKP per komponen +
CaLBMN + LKB; checklist penyampaian per tujuan; ekspor pembanding
rekonsiliasi berformat selaras SAKTI/MonSAKTI.

#### 2.3a Struktur baku CaLBMN tingkat UAKPB (riset Jul 2026)

Pola konsisten lintas CaLBMN satker (pengadilan, KKP, Kemenag, KPU,
Komdigi; format dari Lampiran PMK 181/2016 — nomor lampiran perlu
verifikasi, §14 butir 16):

- **I. Pendahuluan** — dasar hukum (UU 17/2003; UU 1/2004 Ps. 49(6) &
  55(2); PP 27/2014 jo. PP 28/2020; PMK 181/2016) + entitas & periode
  pelaporan (identitas UAKPB, Semester I/II/Tahunan).
- **II. Kebijakan Penatausahaan BMN** — penggolongan & kodefikasi;
  kapitalisasi intra/ekstrakomptabel (PM ≥ Rp1 jt; GB ≥ Rp25 jt; tanah/
  JIJ/koleksi perpustakaan ≥ Rp1); penyusutan (PMK 1/2013 jo. 65/2017);
  amortisasi ATB (PMK 251/2015); rekonsiliasi internal UAKPA + eksternal
  KPKNL.
- **III. Pendekatan Penyusunan Laporan** — sumber data (SIMAK-BMN/SAKTI
  modul Aset Tetap & Persediaan, basis akrual), cakupan, daftar lampiran
  (Neraca, LBKP Intra/Ekstra/Gabungan, Persediaan, KDP, ATB, Register
  Transaksi Harian, Laporan Penyusutan, LKB untuk tahunan).
- **IV. Ringkasan BMN** — saldo awal; ringkasan mutasi per akun neraca
  (Persediaan, Tanah, Peralatan & Mesin, Gedung & Bangunan, JIJ, Aset
  Tetap Lainnya, KDP, Aset Lainnya) dengan pola saldo awal → mutasi
  tambah/kurang per jenis transaksi → saldo akhir untuk intra/ekstra/
  gabungan; posisi BMN di neraca.
- **V. Informasi BMN Lainnya** — perkembangan nilai antarperiode; PSP,
  pemanfaatan, pemindahtanganan, penghapusan; BMN idle; sengketa; PNBP
  dari pengelolaan BMN; langkah strategis.

Istilah mutasi lazim (kode SIMAK/SAKTI): tambah — Saldo Awal (100),
Pembelian (101), Transfer Masuk (102), Hibah Masuk (103), Rampasan (104),
Penyelesaian Pembangunan Dengan KDP (105), Pembatalan Penghapusan (106),
Reklasifikasi Masuk (107), Perolehan Lainnya (112), Penyelesaian
Pembangunan Langsung (113), Pengembangan Nilai (202), Koreksi Bertambah
(204/205), Penerimaan ATR (206), Pengembangan via KDP (208); kurang —
Penghapusan (301), Transfer Keluar (302), Hibah Keluar (303),
Reklasifikasi Keluar (304), Koreksi Pencatatan (305), Penghentian dari
Penggunaan (401). Tahunan dilampiri LKB dan lazim terbit dua versi
(unaudited → audited).

**Implikasi AMAN (CaLBMN):** generator CaLBMN pra-isi per periode dengan
bab I–V terisi dari data yang ada (LBKP #95, posisi neraca #93, register
PSP/pemanfaatan/pemindahtanganan/penghapusan/idle/sengketa, kontribusi
PNBP #121) — AMAN penyiap bahan; dokumen resmi tetap dari SAKTI dan
finalisasi narasi oleh operator.

#### 2.3b Laporan Kondisi Barang (LKB) — format baku (riset Jul 2026)

- Cetakan resmi SIMAK-BMN/SAKTI kode laporan **LKBT-PKPB1** (SAKTI:
  modul Aset Tetap, "AstLaporanKondisiBarangUAKPB"); judul "LAPORAN
  KONDISI BARANG PER {BULAN TAHUN} UNTUK SEMUA KONDISI" (dapat difilter
  per kondisi) + identitas UAKPB.
- **Rincian per item/NUP** dikelompokkan di bawah kode-nama sub-sub
  kelompok barang; kolom terkonfirmasi: Kode Barang, Nama Barang, NUP,
  Kuantitas, Satuan, Kondisi, Harga Perolehan. Varian agregat B/RR/RB
  per golongan lazim sebagai tabel ringkasan di CaLBMN, bukan formulir
  LKB itu sendiri.
- Kondisi baku hanya 3: **Baik** (utuh & berfungsi), **Rusak Ringan**
  (utuh, kurang berfungsi; perbaikan ringan tanpa ganti komponen pokok),
  **Rusak Berat** (tidak utuh/tidak berfungsi; perbaikan besar tidak
  ekonomis). Perubahan kondisi direkam via transaksi 203 setelah cek
  fisik per ruangan (basis DBR).
- Waktu: lampiran wajib LBKP **tahunan** (ke KPKNL ≤15 hari setelah TA
  berakhir per modul pelatihan — [perlu verifikasi rezim PMK 181]);
  aplikasi bebas mencetak per bulan berjalan.
- Tanda tangan: **Penanggung Jawab UAKPB / Kuasa Pengguna Barang**
  (nama + NIP).

### 2.4 Organisasi penatausahaan

UAPB (K/L) ⟶ UAPPB-E1 (eselon I) ⟶ UAPPB-W (wilayah) ⟶ **UAKPB (satker —
fokus AMAN)** ⟶ opsional UAPKPB (pembantu). **Implikasi:** data satker
menyimpan identitas UAKPB + tujuan penyampaian (UAPPB-W/E1, KPKNL mana);
peran pengguna: operator BMN vs pejabat penanggung jawab/penandatangan.

---

## 3. Persediaan (PSAP 05 + praktik SAKTI)

### 3.1 Metode pencatatan & penilaian — KEPUTUSAN DESAIN TERVALIDASI ✅

- PSAP 05: pencatatan **perpetual atau periodik**; penilaian **FIFO atau
  rata-rata tertimbang** (harga pembelian terakhir hanya bila per unit
  tidak material & bermacam jenis).
- Kebijakan pemerintah pusat: **FIFO sejak TA 2021** (PMK 234/2020);
  **SAKTI Modul Persediaan = perpetual + FIFO per LAYER** (saldo per kode
  barang per layer dengan harga satuan masing-masing; ada laporan
  "Persediaan per Layer"; metode hanya boleh disetel di awal TA).
- ➡ **Rencana AMAN "FIFO per batch" SESUAI regulasi dan mereplikasi
  perilaku SAKTI.** Tambahan aturan: metode tidak boleh berubah di tengah
  tahun anggaran; nilai keluar dihitung dari harga layer terkonsumsi
  (boleh lintas layer dalam satu transaksi); sediakan laporan per layer.

### 3.2 Jenis transaksi resmi (peta enum AMAN → SAKTI)

- **Masuk:** Saldo Awal (M01) · Pembelian (M02) · Transfer Masuk · Hibah
  Masuk · Rampasan · Perolehan Lainnya · Reklasifikasi Masuk ·
  Reklasifikasi dari Aset.
- **Keluar:** Habis Pakai/Pemakaian (K01) · Transfer Keluar (K02) · Hibah
  Keluar (K03) · **Usang (K04)** · **Rusak (K05** — direkam berdasar hasil
  opname**)** · Penghapusan Lainnya · Reklasifikasi Keluar.
- **Lainnya:** Koreksi (qty/harga, teraudit) · Opname Fisik (penyesuaian)
  · **Penghapusan definitif usang/rusak (H01/H02** — dua tahap: keluar
  dari saldo dulu, hapus definitif berdasar SK**)** · Persediaan Dalam
  Proses. Kode M0x/K0x = warisan aplikasi lama [kode internal SAKTI perlu
  verifikasi]. Alur SAKTI: **operator merekam → approver menyetujui**.
- **Implikasi:** enum transaksi AMAN memetakan 1:1 ke daftar ini (demi
  rekonsiliasi); bedakan transfer antar satker vs pindah gudang internal;
  workflow operator–approver (pola approval staging masterplan §4).

### 3.3 Stock opname

- Kewajiban: persediaan & KDP inventarisasi **tiap tahun** (PP 27/2014);
  praktik LK: **tiap semester** sebelum penyusunan LK, dituangkan dalam
  **BAOF (Berita Acara Opname Fisik)**; saldo neraca akhir tahun wajib =
  hasil fisik.
- Alur SAKTI: **Cetak Bahan Opname** (kertas kerja saldo buku) → hitung
  fisik → **Rekam Hasil Opname** (hanya yang selisih) → saldo buku
  disetel = fisik; penjelasan selisih wajib diungkap di **CaLK**; barang
  rusak/usang teridentifikasi saat opname → transaksi Usang/Rusak
  (keluar dari neraca, tetap diungkap di CaLK); selisih kurang akibat
  kelalaian dapat berlanjut **TGR** [dasar formal perlu verifikasi].
- **Implikasi:** siklus opname semesteran (jadwal+pengingat), kertas
  kerja digital, selisih otomatis + alasan wajib, BAOF bernomor dengan
  3 penandatangan, kunci transaksi back-date setelah opname disahkan,
  daftar khusus usang/rusak (bahan CaLK).

### 3.4 Kodefikasi, akun, laporan

- Persediaan = **golongan 1** (kode hierarkis sampai sub-sub kelompok;
  contoh sub kelompok lazim: 1.01.01 Barang Konsumsi, 1.01.03 Bahan
  Pemeliharaan, 1.01.04 Suku Cadang, 1.02.xx barang untuk diserahkan,
  1.03.xx bahan baku [susunan mutakhir perlu verifikasi lampiran]).
- Pemetaan ke akun neraca **1171xx** (117111 Barang Konsumsi, 117113
  Bahan Pemeliharaan, 117114 Suku Cadang, 117199 Persediaan Lainnya —
  daftar lengkap perlu verifikasi BAS) → **kode barang wajib termapping
  ke akun** agar Laporan Posisi per akun otomatis.
- Laporan baku minimum: **Posisi Persediaan di Neraca** (per akun),
  **Rincian** (saldo awal-mutasi-akhir per barang), **Mutasi/Transaksi**
  (per jenis), **per Layer**. Satuan dari tabel referensi baku.

---

## 4. Pemeliharaan (PP 27/2014 Ps. 46-47)

**Tanggung jawab & dokumen.** Pengelola/Pengguna/Kuasa Pengguna Barang
bertanggung jawab atas pemeliharaan BMN di bawah penguasaannya; pedomannya
Daftar Kebutuhan Pemeliharaan Barang (DKPB); biaya dibebankan APBN — kecuali
BMN sedang dimanfaatkan pihak lain (sewa/pinjam pakai/KSP/BGS-BSG/KSPI):
biaya menjadi tanggungan mitra (Ps. 46). KPB **wajib membuat Daftar Hasil
Pemeliharaan Barang (DHPB)** dan melaporkannya tertulis ke Pengguna Barang
secara berkala (praktik baku: semesteran); Pengguna Barang merekap DHPB
per Tahun Anggaran sebagai bahan evaluasi efisiensi (Ps. 47). DHPB tahunan
juga input wajib RKBMN pemeliharaan (PMK 153/2021). PP 28/2020 tidak
mengubah Ps. 46-47.

**Klasifikasi jenis (bahan ajar DJKN/KLC):** *ringan* — harian oleh unit
pemakai tanpa membebani anggaran; *sedang* — berkala oleh tenaga
terdidik/terlatih; *berat* — sewaktu-waktu oleh tenaga ahli. (Gedung:
Permen PU 24/2008 & PUPR 22/2018 membedakan pemeliharaan-preventif vs
perawatan-kuratif dengan tingkat kerusakan ringan/sedang/berat.)

**Kapitalisasi vs beban.** Pengeluaran setelah perolehan dikapitalisasi bila
menambah masa manfaat ATAU kapasitas/mutu/standar kinerja (PSAP 07 par.
50-51) DAN ≥ nilai satuan minimum kapitalisasi PMK 181/2016 (peralatan-mesin
≥ Rp1 jt; gedung-bangunan ≥ Rp25 jt; tanah & JIJ tanpa batas minimum).
Yang hanya mempertahankan fungsi normal = beban akun 523xxx (523111 gedung,
523121 peralatan-mesin, 5231xx JIJ, 523191 lainnya). Renovasi terkapitalisasi
dapat menambah masa manfaat per tabel KMK 59/KM.6/2013; SIMAK-BMN/SAKTI
merekamnya sebagai "Pengembangan Nilai Aset" — pemeliharaan non-kapital
TIDAK punya riwayat per-NUP di aplikasi resmi (gap yang ditutup kartu
pemeliharaan manual → peluang AMAN).

**Harapan auditor (Itjen/BPK):** riwayat per aset (kode+NUP) terisi
berkelanjutan; kondisi B/RR/RB mutakhir & konsisten LKB; bukti per transaksi
(SPK/kuitansi, BA pemeriksaan pekerjaan, SPM/SP2D, foto); ketepatan akun
523 vs 53 (temuan berulang: layak kapital tapi tidak dikapitalisasi); DHPB
tersusun; RKBMN pemeliharaan hanya untuk BMN kondisi Baik/Rusak Ringan
(rusak berat / diusul hapus / dimanfaatkan pihak lain tidak boleh).

**Terapan AMAN (iterasi 16):** catatan per kejadian (tanggal, jenis
ringan/sedang/berat, uraian, biaya, pelaksana, no. bukti, kondisi
sebelum/sesudah otomatis) + rekap per tahun/jenis/aset + pembaruan kondisi
aset + penanda "telaah kapitalisasi" bila biaya ≥ ambang golongan.
Menyusul: jadwal berkala, DHPB PDF, akun 523/53 per catatan, foto bukti.

---

## 5. Penyusutan (PMK 65/PMK.06/2017 + KMK 295/KM.6/2019 jo. 266/KM.6/2023)

**Dasar & metode.** PMK 65/PMK.06/2017 (masih berlaku, dirujuk LBMN audited
2024/2025): metode tunggal **garis lurus tanpa nilai residu**, dihitung
**per unit aset**, dibukukan **tiap akhir semester** (30 Jun & 31 Des).
Basis = nilai perolehan setelah kapitalisasi. **Konvensi semester penuh**:
aset yang diperoleh kapan pun dalam semester dibebani satu semester penuh
(tanpa prorata harian).

**Tabel masa manfaat.** KMK 59/KM.6/2013 **DICABUT** — kini
**KMK 295/KM.6/2019** jo. **KMK 266/KM.6/2023**; kunci tabel = KELOMPOK
kodefikasi (level 3, prefix 5 digit). Contoh terverifikasi: alat angkutan
darat bermotor 7 th; alat kantor & alat rumah tangga 5 th; rentang
peralatan-mesin 2-20 th, gedung-bangunan 10-50 th, JIJ 5-40 th. Nilai lazim
lain (komputer unit & peralatan komputer 4 th; alat studio/komunikasi 5 th;
gedung permanen 50 th) *perlu validasi lampiran KMK*. Tabel II mengatur
penambahan masa manfaat akibat renovasi/overhaul (per rentang % biaya
terhadap nilai aset).

**Tidak disusutkan:** tanah (gol. 2), KDP (gol. 7), aset bersejarah
(kuantitas saja), ATL hewan/tanaman/bahan pustaka (ATL yang disusutkan
hanya alat musik modern 4 th); **henti susut**: aset hilang / rusak berat
yang TELAH diusulkan pemindahtanganan/pemusnahan/penghapusan →
direklasifikasi keluar aset tetap + diungkap CaLK. Aset habis masa manfaat:
nilai buku **0** (bukan Rp1), tetap tersaji bruto sampai SK penghapusan.

**Harapan auditor:** LBKP memuat Laporan Penyusutan per golongan; CaLK
mengungkap kebijakan (dasar hukum, metode, periodisitas, tabel); saldo
akumulasi penyusutan laporan barang = neraca keuangan (rekonsiliasi);
aset henti-susut/nilai-buku-nol diungkap jumlahnya.

**Terapan AMAN (iterasi 29):** logika murni penyusutan garis lurus
semesteran + rekap per golongan dari tanggal perolehan & harga aset;
kelompok tanpa masa manfaat terdaftar TIDAK ditebak — masuk daftar
"perlu referensi" (tanpa data dummy). Referensi masa manfaat editable &
seed lengkap dari lampiran KMK menyusul.

---

## 6. Pemanfaatan (PMK 115/PMK.06/2020 + PMK 18/2024)

**Status regulasi.** PMK 115/PMK.06/2020 MASIH BERLAKU (pokok pemanfaatan;
mencabut PMK 78/2014, 164/2014, 57/2016). **PMK 18/2024 BUKAN pengganti**
— isinya fasilitas penyiapan & pelaksanaan transaksi (ala PDF: kajian,
market sounding, pendampingan tender) bagi PJPB. KETUPI = bentuk ke-6
sejak PP 28/2020 (operasional a.l. KMK 361/KMK.6/2024).

**6.a Fasilitas transaksi pemanfaatan (riset #190).** Judul resmi PMK 18
Tahun 2024: "Tata Cara Pemberian **Fasilitas** Penyiapan dan Pelaksanaan
Transaksi Pemanfaatan BMN" (BN 2024/201) — "Fasilitas" = bantuan/dukungan
Menteri Keuangan (domain **DJPPR/PDPPI**, bukan DJKN) kepada
**Penanggung Jawab Pemanfaatan BMN (PJPB)**, analog Project Development
Facility (PDF) pada rezim KPBU (PMK 180/PMK.08/2020). **BUKAN bentuk
pemanfaatan ke-7** — bentuk tetap 6 sesuai PP 27/2014 jo. 28/2020 +
PMK 115/2020, dan fasilitas tidak menimbulkan PNBP baru (pendanaan APBN).
Alur: permohonan PJPB → penetapan Menteri (pelaksana dapat BUMN
penugasan) → tahap penyiapan (Kajian Peningkatan Nilai BMN, Kajian
Rekomendasi Transaksi, market sounding) → tahap pelaksanaan transaksi
bila rekomendasi **KSP/BGS/BSG** (pendampingan tender s.d. tanda tangan
perjanjian + pemantauan kewajiban awal mitra) → berakhir (tujuan
tercapai/jangka habis/diakhiri Menteri). Khusus aset lingkup **IKN**
berlaku fasilitas serupa **PMK 139/PMK.08/2022** (pelaksana PT PII,
berjangka s.d. 2032). Transaksi hasil fasilitas tetap tunduk penuh pada
PMK 115/2020. Rincian pasal belum terverifikasi dari teks resmi (§14
butir 24).

**Enam bentuk + jangka maksimal:** Sewa 5 th dapat diperpanjang (mitra:
badan usaha/perorangan; periodesitas jam-hari-bulan-tahun) · Pinjam Pakai
5 th (mitra HANYA Pemda/Pemdes; tanpa imbalan; perpanjangan diajukan ≥2
bulan sebelum berakhir) · KSP 30 th (infrastruktur 50 th; mitra badan
usaha non-perorangan via tender) · BGS/BSG 30 th **tidak dapat
diperpanjang** (dilaksanakan Pengelola Barang) · KSPI 50 th · KETUPI 50 th
(PJPB + BLU; objek ditetapkan Menkeu). Persetujuan SELALU di Pengelola
Barang (KPKNL/Kanwil/DJKN berjenjang nilai).

**Keuangan.** Sewa = tarif pokok (nilai wajar penilaian) × faktor
penyesuai (jenis kegiatan + periodesitas; per jam s.d. 190%), dibayar
sekaligus di muka oleh penyewa LANGSUNG ke Kas Negara (PNBP, kode billing
SIMPONI); KSP = kontribusi tetap tahunan (% × nilai wajar) + pembagian
keuntungan; BGS/BSG = kontribusi tahunan tiap ulang tahun perjanjian +
≥10% hasil untuk tusi; KSPI = clawback kelebihan keuntungan; KETUPI =
dana di muka. **Satker (KPB) = pengusul & penatausaha — DILARANG menerima/
memakai uang langsung (UU 1/2004).**

**Temuan auditor tersering:** pemanfaatan tanpa persetujuan Pengelola;
hasil sewa tidak disetor/dipakai langsung; perjanjian berakhir tapi objek
masih dipakai; tarif tanpa penilaian; tidak diungkap di LBKP/wasdal.

**Terapan AMAN (iterasi 35):** register + arsip, bukan sistem uang —
entitas per perjanjian (bentuk, objek BMN, mitra, persetujuan Pengelola,
perjanjian, nilai, NTPN, periode); status "aktif" HANYA bila nomor
persetujuan + perjanjian terisi (sewa: + NTPN) — mencegah dua temuan
tersering secara struktural; peringatan jatuh tempo H-60 (syarat
perpanjangan ≥2 bulan); pengingat kontribusi tahunan (#121); lampiran
wasdal per perjanjian (#188); atribut fasilitas transaksi PMK 18/2024 /
PMK 139/2022 pada perjanjian KSP/BGS-BSG (#190).

---

## 7. Pemindahtanganan (PMK 111/PMK.06/2016 jo. 165/PMK.06/2021)

**Status.** PMK 111/2016 jo. 165/2021 MASIH BERLAKU (melaksanakan Ps. 74A
PP 28/2020). Pelengkap baru: PMK 77/2024 (penjualan kendaraan perorangan
dinas tanpa lelang), PMK 122/2023 (juklak lelang), KMK 375/2024 (nilai
taksiran kendaraan: harga pasar lelang × faktor kondisi 0,7/0,6/0,5),
KMK 235/2023 (mandat DJKN). Empat bentuk: **Penjualan, Tukar Menukar,
Hibah, PMPP** (UU 1/2004 Ps. 45; PP 27/2014 Ps. 54).

**Jalur persetujuan bertingkat nilai** (UU 1/2004 Ps. 45-46; PP 27/2014
Ps. 55-58): tanah/bangunan → DPR (kecuali 5 pengecualian; yang
dikecualikan: >Rp10 M Presiden, ≤Rp10 M Pengelola); selain tanah/bangunan
→ >Rp100 M DPR, >Rp10-100 M Presiden, ≤Rp10 M Pengelola (KPKNL/Kanwil/
DJKN berjenjang). **Delegasi PMK 4/2015**: Pengguna Barang sendiri boleh
menyetujui penjualan/hibah BMN selain tanah/bangunan TANPA bukti
kepemilikan bernilai perolehan ≤Rp100 juta/unit — jalur tersering satker.

**Penjualan**: prinsip LELANG via KPKNL (permohonan ≤6 BULAN sejak
persetujuan; lewat = wajib penilaian ulang); tanpa lelang hanya kasus
khusus (rumah negara gol. III ke penghuni sah; kendaraan perorangan dinas
ke pejabat/ASN/TNI/Polri per PMK 77/2024; tanah kavling perumahan
pegawai; bangunan di atas tanah pihak lain; penetapan Pengelola). Nilai
limit dari penilaian/nilai taksiran; hasil disetor SELURUHNYA ke Kas
Negara (PNBP). **Hibah**: penerima sah = Pemda/Pemdes, lembaga sosial-
budaya-keagamaan-kemanusiaan-pendidikan non-komersial (wajib pernyataan
instansi teknis), masyarakat program pembangunan, pemerintah negara lain;
dokumen = Naskah Hibah + BAST. **Tukar Menukar**: penggantian barang
minimal seimbang; Perjanjian TM + BAST + setor selisih. **PMPP**:
ditetapkan PERATURAN PEMERINTAH; BAST ke BUMN/badan hukum penerima.

**Tindak lanjut wajib**: Risalah Lelang/BAST → SK Penghapusan → keluar
dari daftar barang → **lapor ke Pengelola ≤1 bulan** sejak SK.

**Terapan AMAN (iterasi 38):** register per USULAN multi-aset berstatus
(diusulkan → disetujui → dilaksanakan → selesai; tolak/batal), dokumen
wajib per tahap mengunci transisi (persetujuan → dokumen pelaksanaan per
bentuk + NTPN utk penjualan → SK penghapusan), peringatan tenggat lelang
6 bulan; jalur persetujuan & ambang nilai dicatat sebagai informasi
(tabel konfigurasi menyusul — sub-aturan bergerak).

---

## 8. Wasdal — Pengawasan & Pengendalian (PMK 207/PMK.06/2021)

### 8.1 Dasar & status
- **PMK 207/PMK.06/2021** tentang Pengawasan dan Pengendalian BMN — berlaku
  **1 Januari 2022**, mencabut PMK 244/PMK.06/2012 jo. PMK 52/PMK.06/2016.
  Masih berlaku per Juli 2026 (pelaporan Sem II/Tahunan 2025 dan Sem I 2026
  di K/L masih merujuk PMK ini); tidak ditemukan aturan pengubah.
- Ekosistem: **PMK 118/2023** (pengelolaan BMN via SIMAN), KMK 125/KM.6/2024
  (rollout SIMAN v2 penuh Jul–Des 2024), KMK 248/KM.6/2024 (juknis SIMAN v2,
  memuat Modul Wasdal) **[nomor perlu verifikasi]**; regulasi objek terkait:
  PMK 40/2024 (penggunaan), **PMK 120 Tahun 2024** (BMN idle — mencabut
  PMK 71/2016).

### 8.2 Bentuk wasdal Pengguna Barang/KPB
- **Pemantauan** (periodik & insidentil) + **penertiban** + tindak lanjut
  hasil audit APIP/BPKP/pemeriksaan BPK + **pelaporan berjenjang**.
  Investigasi, monev, penetapan indikator kinerja, dan evaluasi kinerja
  portofolio aset adalah domain **Pengelola Barang** (KPKNL–Kanwil–Kantor
  Pusat DJKN), bukan KPB.
- **Lima objek pemantauan KPB**: (1) Penggunaan, (2) Pemanfaatan,
  (3) Pemindahtanganan, (4) Penatausahaan, (5) Pengamanan & pemeliharaan —
  dicek kesesuaian pelaksanaannya dengan ketentuan, via penelitian
  administrasi dan/atau lapangan (boleh berbantuan teknologi). Pemantauan
  insidentil dapat dipicu informasi masyarakat/media/hasil audit.

### 8.3 Frekuensi & tenggat
| Hal | Ketentuan | Catatan |
|---|---|---|
| Pemantauan periodik | 1x/semester ATAU 1x/tahun (selesai akhir Februari) | **[KONFLIK SUMBER — verifikasi ke pasal PMK 207]**; siklus semesteran otomatis memenuhi kedua tafsir |
| Pemantauan insidentil | pelaksanaan ≤10 hari kerja; hasil dilaporkan ≤5 hari kerja sejak BA | — |
| Penertiban oleh KPB | selesai ≤**15 hari kerja** sejak pemantauan selesai / surat permintaan Pengelola diterima | juga dipicu temuan APIP/BPK |
| Laporan wasdal | **semesteran + tahunan**, berjenjang KPB → PPB-W → PPB-E1 → PB → Pengelola | tenggat statutori antar jenjang [perlu verifikasi]; praktik K/L: Sem I ± awal Juli, Sem II+Tahunan ± Januari |

- Kanal resmi pelaporan sejak Sem II/Tahunan 2024: **Modul Wasdal SIMAN v2**
  (sebelumnya Excel). Sanksi tidak melaksanakan wasdal: penundaan
  penyelesaian/pelaksanaan RKBMN + pengurangan indikator kinerja pengelolaan.

### 8.4 Keterkaitan dengan domain lain
- **Sertifikasi tanah** (objek pengamanan): tanah wajib bersertipikat a.n.
  Pemerintah RI c.q. K/L; temuan lazim: belum bersertipikat, dokumen
  kepemilikan tidak dikuasai satker.
- **BMN idle** (temuan pemantauan penggunaan): wajib diserahkan ke Pengelola
  — rezim teknis kini PMK 120/2024; SIMAN v2 punya Modul BMN Idle terpisah.
- **Investigasi Pengelola**: hasil 3 kategori (tanpa penyimpangan /
  penyimpangan tanpa indikasi kerugian negara / dengan indikasi) → kembali
  ke Pengguna sebagai permintaan penertiban; audit APIP atas permintaan
  PB/KPB bila ada indikasi penyimpangan.
- Temuan wasdal tersering (artikel Kanwil DJKN Jatim): RB belum dihapus,
  pemindahtanganan di luar ketentuan, BMN idle, dikuasai pihak ketiga,
  digunakan tanpa hak, tanah belum bersertipikat, aset belum tercatat.

### 8.5 Implikasi desain AMAN (dasbor pemantauan tingkat KPB)
- **Mesin aturan ringan membaca register yang SUDAH ada** (tanpa input
  ganda): aset (BAST/kondisi/foto/koordinat/nilai/sengketa), pemanfaatan
  (berakhir/dokumen kurang), penghapusan & pemindahtanganan (usulan
  berlarut, RB belum diusulkan, tenggat lelang), pemeliharaan (aset rusak
  tanpa penanganan tahun berjalan).
- Temuan dikelompokkan per **5 objek pemantauan PMK 207** + label periode
  (Semester I/II) sebagai bahan pra-isi laporan wasdal — **kanal resmi
  tetap SIMAN v2; AMAN memposisikan diri sebagai penyiap data**.
- ✅ Register penertiban ber-tenggat 15 hari kerja (sumber: pemantauan /
  surat permintaan Pengelola / temuan APIP-BPK; hitung hari kerja
  Senin–Jumat, libur nasional belum diperhitungkan; tindak lanjut
  tercatat saat selesai).
- ✅ Pemantauan insidentil ber-tenggat 10+5 hari kerja (pemicu: informasi
  masyarakat / pemberitaan media / hasil audit; alur berjalan → BA terbit
  → dilaporkan; PDF Berita Acara siap tanda tangan dengan placeholder
  bila BA belum terbit).
- Menyusul: generator laporan mengikuti formulir Lampiran PMK 207 (baca
  lampiran asli dulu), kalender tenggat konfigurabel (tenggat internal
  ditetapkan surat DJKN/K/L per tahun).

---

## 9. Penganggaran — Integrasi RKBMN ↔ RKA-K/L (PMK 62/2023 + PMK 153/PMK.06/2021)

### 9.1 Dasar & status
- **PMK 62 Tahun 2023** (Perencanaan Anggaran, Pelaksanaan Anggaran, serta
  Akuntansi dan Pelaporan Keuangan) — regulasi induk penganggaran; mencabut
  PMK 208/2019 (juknis RKA-K/L/DIPA) & PMK 199/2021 (revisi anggaran).
  Diubah **PMK 107/2024** dan **PMK 41/2026** (berlaku 22 Juni 2026;
  perubahan terpublikasi menyentuh sisi pelaksanaan — **[perlu verifikasi
  apakah bab perencanaan anggaran ikut berubah]**).
- **PMK 153/PMK.06/2021** (Perencanaan Kebutuhan BMN) masih berlaku;
  praktik: RKBMN disusun via **SIMAN V2 modul Perencanaan** (siklus t-2 —
  contoh: usulan RKBMN TA 2027 diinput Juli 2025). Kualitas RKBMN kini
  dinilai dalam Indeks Pengelolaan Aset (KMK 39/KM.6/2025).

### 9.2 Titik integrasi RKBMN → RKA-K/L
- Alur: usulan **KPB** → konsolidasi Pengguna Barang + **reviu APIP**
  (modul KMK 332/KM.6/2016) → penelaahan **Pengelola Barang (DJKN)** →
  **RKBMN Hasil Penelaahan** (ditandatangani kedua pihak, tembusan Dirjen
  Anggaran) → menjadi **dasar angka dasar & inisiatif baru** RKA-K/L dan
  dokumen pendukung penelaahan/reviu RKA; SBSK = batas tertinggi.
- Pemetaan belanja: usulan **pengadaan** → belanja modal **53x** (531
  tanah; 532 peralatan-mesin; 533 gedung-bangunan; 534 jalan-irigasi-
  jaringan; 536 modal lainnya); usulan **pemeliharaan** → **523**.
- Perubahan kebutuhan tahun berjalan hanya lewat **usulan perubahan
  RKBMN** — paling lambat 1 bulan sebelum batas revisi anggaran; revisi
  anggaran berjenjang KPA/Kanwil DJPb/Dit. PA/DJA (jo. PER-9/PB/2023).

### 9.3 Kalender & pelaksana tingkat satker
| Waktu (pola) | Tahap |
|---|---|
| Juli–Des (t-2) | Input usulan RKBMN satker (tenggat surat internal K/L) → reviu APIP → penelaahan DJKN |
| ± Maret–April | Pagu indikatif (Kemenkeu–Bappenas) |
| ± Juni–Juli | Pagu anggaran → penyusunan RKA-K/L satker di **SAKTI Web** (operator–validator–approver, tanggung jawab KPA; referensi program/KRO/RO dari **KRISNA**; KAK/RAB) |
| Agu–Okt | RUU APBN, pembahasan DPR, penelaahan RKA |
| ± Nov–Des | Alokasi anggaran (pagu definitif) → **DIPA petikan** + POK + Halaman III DIPA |
- Pemantauan realisasi: **IKPA** di OM-SPAN (a.l. penyerapan 20%, deviasi
  Halaman III DIPA 15%, capaian output 25%) + MonSAKTI.

### 9.4 Implikasi desain AMAN (modul Penganggaran tahap awal)
- **Register usulan penganggaran** per usulan (lahir dari kertas kerja
  RKBMN): pipeline **diusulkan → disetujui telaah (nilai disetujui) →
  masuk DIPA (nomor + nilai) → terealisasi (nilai realisasi)**; ditolak =
  terminal. Status diisi operator berdasar dokumen resmi — AMAN mencatat
  jejak per aset/NUP (granularitas yang tidak dimiliki SAKTI), bukan
  memutus.
- Sanding **rencana vs realisasi** per jenis (pengadaan 53x vs
  pemeliharaan 523) + serapan per usulan; pengingat kalender (tanggal
  konfigurabel — tenggat internal per K/L berbeda).
- **Yang TIDAK boleh diklaim**: bukan kanal resmi (RKBMN via SIMAN V2;
  RKA/DIPA/revisi via SAKTI; Renja via KRISNA — posisi AMAN seperti
  e-SADEWA di MA); tidak menghitung SBSK resmi; tidak menerbitkan dokumen
  menyerupai dokumen resmi; status register tak berkekuatan hukum.

---

## 10. Pengadaan — Perolehan & Dokumen Sumber (Perpres 16/2018 jo. 46/2025)

### 10.1 Dasar & status
- **Perpres 16/2018** jo. Perpres 12/2021 (perubahan pertama) jo.
  **Perpres 46/2025** (perubahan KEDUA — bukan ketiga; ditetapkan
  ±30 April 2025). Poin penting satker: **e-purchasing wajib** untuk
  produk yang sudah tayang di Katalog Elektronik (INAPROC/Katalog V6,
  tender = pilihan terakhir, berlaku juga jasa konsultansi); pengadaan
  langsung konstruksi naik **≤ Rp400 jt** (barang/jasa lain ≤ Rp200 jt,
  konsultansi ≤ Rp100 jt); PPK wajib sertifikat kompetensi PBJ.
- Turunan LKPP masih transisi (SE Kepala LKPP 1/2025): PerLKPP 11/2021
  (perencanaan) & 12/2021 jo. 4/2024 (pemilihan) tetap berlaku sepanjang
  tidak bertentangan; Katalog V6 (Kep. 177/2024), mini-kompetisi
  (Kep. 93/2025). **[PerLKPP payung baru belum ditemukan — pantau]**
- Pembayaran kini rezim **PMK 62/2023 jo. 107/2024** (SPP→SPM→SPD2D;
  mencabut PMK 190/2012).

### 10.2 Alur satker & titik sambung ke BMN
- Alur: RUP di **SiRUP** (setelah DIPA) → pemilihan via INAPROC/SPSE
  (e-purchasing / pengadaan langsung / tender) → kontrak (bukti
  pembelian/kuitansi/SPK/surat perjanjian) → **BAPHP → BAST** →
  SPP → SPM → SP2D.
- **BAST = pemicu pencatatan BMN** — di SAKTI pembelian aset dicatat
  berdasar BAST tanpa menunggu SP2D: rekam kontrak+BAST (rincian kode
  barang) di Modul Komitmen → pendetailan NUP di Modul Aset
  Tetap/Persediaan → jurnal otomatis. Hibah barang: BAST hibah →
  pendetailan → **MPHL-BJS** → pengesahan KPPN.
- Kode transaksi perolehan (referensi): **101** Pembelian · **102**
  Transfer Masuk · **103** Hibah Masuk · **105** Penyelesaian
  Pembangunan dengan KDP · **112** Perolehan Lainnya · **113**
  Penyelesaian Pembangunan Langsung.

### 10.3 Nilai perolehan & ambang kapitalisasi
- **PSAP 07 + Bultek 15**: nilai perolehan = harga beli/konstruksi +
  biaya atribusi langsung sampai siap pakai (persiapan tempat,
  pengiriman awal & bongkar-muat, instalasi, jasa profesional); biaya
  administrasi umum TIDAK dikapitalisasi.
- Ambang kapitalisasi **masih PMK 181/2016**: peralatan-mesin ≥ Rp1 jt,
  gedung-bangunan ≥ Rp25 jt; tanah/JIJ/KDP tanpa ambang; di bawah ambang
  → **ekstrakomptabel** (akun belanja tersendiri, S-454). Tidak ditemukan
  PMK pengubah per Juli 2026 **[cek ulang JDIH saat implementasi]**.

### 10.4 Temuan lapangan (BPK/DJPb)
Aset tidak/terlambat tercatat ("BMN belum diregister" saat rekonsiliasi);
**BAST tercecer/terlambat**; **salah pilih kode barang saat rekam BAST**
(persediaan vs aset — sampai terbit surat DJPb S-429); selisih kontrak vs
fisik; barang untuk pemda/masyarakat tidak segera di-BAST-kan.

### 10.5 Implikasi desain AMAN (modul Pengadaan tahap awal)
- **Register perolehan per dokumen** (satu entri per BAST/kontrak): jenis
  perolehan (pembelian/transfer/hibah/pembangunan — selaras kode
  101/102/103/105 sebagai referensi), penyedia/pemberi, nomor kontrak &
  BAST, tanggal, daftar barang (uraian, kode, jumlah, harga satuan).
- **Checklist kelengkapan dokumen sumber** per jenis (kontrak, BAPHP,
  BAST, kuitansi, SP2D; hibah: naskah hibah + MPHL-BJS) — penangkal
  temuan "BAST tercecer".
- **Tautan barang → aset master** (cegah entri ganda; daftar tunggu
  "belum dicatat") + penanda **ekstrakomptabel** bila harga satuan di
  bawah ambang PMK 181 (parameter, bukan konstanta terkubur).
- **Yang TIDAK boleh diklaim**: bukan pencatatan resmi (SAKTI) dan bukan
  kanal pengadaan (SiRUP/SPSE/e-Katalog); tidak menerbitkan dokumen
  berkekuatan hukum; NUP internal ≠ NUP resmi SAKTI.

---

## 11. Pengamanan BMN (PP 27/2014 Ps. 42-43 jo. PP 28/2020 + PMK 218/2015)

> Riset Juli 2026; seluruh fetch teks asli regulasi terblokir proxy (403)
> sehingga rincian bersumber cuplikan pencarian + artikel DJKN — butir
> [perlu verifikasi] dirangkum di §14 butir 18-19.

### 11.1 Dasar & status regulasi

- **Koreksi premis**: PMK 244/PMK.06/2012 BUKAN aturan pengamanan —
  itu PMK **Wasdal** (jo. PMK 52/2016), dan keduanya sudah DICABUT oleh
  **PMK 207/PMK.06/2021** (sudah dipakai modul Wasdal, §8). Tidak ada
  PMK nasional tunggal "tata cara pengamanan BMN"; norma pengamanan
  tersebar:
- **UU 1/2004 Ps. 49(1)**: tanah BMN wajib disertipikatkan atas nama
  **Pemerintah Republik Indonesia** (c.q. K/L pengguna).
- **PP 27/2014 jo. PP 28/2020 Ps. 42**: Pengelola/Pengguna/Kuasa
  Pengguna Barang **wajib** mengamankan BMN dalam penguasaannya,
  meliputi pengamanan **administrasi, fisik, dan hukum**. **Ps. 43**:
  bukti kepemilikan disimpan tertib — tanah/bangunan oleh **Pengelola
  Barang**, selain tanah/bangunan oleh **Pengguna Barang**.
- **PMK 218/PMK.06/2015**: tata cara penyimpanan dokumen kepemilikan
  (pejabat penyimpan, konversi media, permintaan dokumen pendukung).
- **Peraturan Bersama Menkeu-BPN 186/PMK.06/2009 & 24/2009**:
  pensertipikatan tanah BMN a.n. Pemerintah RI c.q. K/L.
- Pedoman teknis per K/L (contoh KMK 21/KMK.01/2012 di Kemenkeu) —
  wujud konkret pengamanan per jenis BMN diatur di level ini.

### 11.2 Bentuk pengamanan per jenis BMN (ringkas, [perlu verifikasi])

| Jenis | Fisik | Administrasi | Hukum |
|---|---|---|---|
| Tanah | patok/pagar/plang nama | catat + arsip dokumen perolehan | sertipikat Hak Pakai a.n. Pemerintah RI c.q. K/L; blokir bila sengketa |
| Gedung/bangunan | pagar, satpam, CCTV, APAR | arsip IMB/PBG, BAST, KIB | bukti kepemilikan a.n. Pemerintah RI |
| Kendaraan | kunci/alarm, simpan di pool kantor | arsip BPKB + salinan STNK | BPKB/STNK a.n. pemerintah; pajak tepat waktu |
| Selain tanah/bangunan | gudang terkunci, APAR | registrasi, DBR/DBL, opname | dokumen perolehan; TGR bila dikuasai pihak lain |

### 11.3 BMN bermasalah/sengketa

- Kategori kasus umum (artikel DJKN): (1) **dikuasai pihak lain** tanpa
  alas hak; (2) **disertipikatkan pihak lain / tumpang tindih**;
  (3) **sengketa/berperkara** di pengadilan.
- Alur penanganan praktik: preventif (dokumen + sertipikasi + kuasai
  fisik) → **mediasi/non-litigasi** (pokja satker + KPKNL, fasilitasi
  BPN) → **pemblokiran sertipikat** di Kantor Pertanahan (jaga status
  quo) → **litigasi** dengan pendampingan Jaksa Pengacara Negara →
  selesai (inkracht/pulih).
- BMN bermasalah masuk lingkup **laporan wasdal semesteran/tahunan**
  (PMK 207/2021) dan CaLBMN — tidak ada laporan khusus terpisah.
- Sertipikasi tanah BMN: kategori target **K1** (lengkap, siap SHP),
  **K2** (data kurang), **K3** (sengketa), **K4** (sudah sertipikat,
  perlu pemutakhiran SIMAN) [perlu verifikasi].

### 11.4 Implikasi desain AMAN

- ✅ **Register BMN bermasalah berstatus** (#169): kategori kasus (3 di
  atas), pipeline identifikasi → mediasi → blokir → litigasi → selesai,
  pihak lawan + nomor perkara + pendamping, riwayat per transisi —
  bahan mentah laporan wasdal & CaLBMN.
- Menyusul: checklist pengamanan per aset per jenis (turunan tabel
  11.2), arsip dokumen kepemilikan per aset dengan lokasi penyimpanan
  (Pengelola vs Pengguna, Ps. 43), field status sertipikasi K1-K4.
- **Yang TIDAK boleh diklaim**: bukan kanal laporan wasdal resmi; bukan
  penyimpanan dokumen kepemilikan yang sah (PMK 218/2015); tidak
  melakukan pemblokiran sertipikat / nasihat hukum; register tak
  berkekuatan hukum. Jangan merujuk PMK 244/2012 (dicabut).

### 11.5 Asuransi BMN (PMK 97/2019 → PMK 43 Tahun 2025)

> Riset Juli 2026; teks asli PMK tak terbaca (proxy 403) — seluruh butir
> dari cuplikan pencarian/artikel DJKN, dirangkum di §14 butir 20.

- **Status regulasi**: PMK 247/PMK.06/2016 → dicabut PMK 97/PMK.06/2019
  → **dicabut PMK 43 Tahun 2025** (berlaku 14 Juli 2025; polis lama
  tetap berlaku sampai habis masa). Induk: PP 27/2014 jo. PP 28/2020 —
  pengasuransian bagian pengamanan; sifat **"dapat"** (selektif,
  efisiensi, prioritas), bukan wajib mutlak.
- **Objek** (PMK 97/2019): **gedung dan bangunan** berdampak pelayanan
  umum / menunjang tusi (kantor, pendidikan, kesehatan) + opsional
  sarana-prasarana (struktural/mekanikal/elektrikal/tata ruang luar).
  PMK 43/2025 mengelompokkan: **BMN Program (Preferen/Nonpreferen)** dan
  **Nonprogram (Mandatory/Luar Negeri/Opsional)** [perlu verifikasi].
- **Mekanisme**: penanggung = **Konsorsium Asuransi BMN** (ketua
  Jasindo, administrator MAIPARK) via **Kontrak Payung** yang diteken
  Pengelola Barang; pemegang polis = Pengguna Barang; perencanaan via
  **SIMAN**, premi dianggarkan di DIPA — PMK 43/2025 menambah skema
  pendanaan **Pooling Fund Bencana** (Perpres 75/2021 + PMK 28/2025);
  laporan pelaksanaan menjadi bagian LBKP.
- **Data minimum polis**: nomor polis, penanggung, objek per NUP,
  nilai pertanggungan, premi (+sumber dana), jangka waktu (umumnya
  1 tahun), risiko yang dijamin, klaim.
- **Implikasi AMAN**: ✅ register polis per aset (#177) — nomor polis,
  penanggung, kategori objek (enum PMK 43/2025 sementara), nilai
  pertanggungan, premi + sumber dana DIPA/PFB, masa berlaku dengan
  pengingat segera-berakhir (≤90 hari); menyusul: sub-register klaim,
  lampiran scan polis. **Yang TIDAK boleh diklaim**: bukan kanal resmi
  perencanaan (SIMAN), tidak menerbitkan polis / menghitung tarif
  resmi / memproses klaim; register bukan laporan resmi pengasuransian.

---

## 12. Kendala Umum Satker → Fitur Penangkal AMAN

| Kendala nyata (temuan artikel DJKN/DJPb/BPK/jurnal) | Penangkal di AMAN |
|---|---|
| Operator terbatas/rangkap tugas; rotasi tanpa alih pengetahuan | Multi-user + peran ringan (penanggung jawab ruangan cek ruangannya sendiri); UI sekali-ketuk |
| DBR tak mutakhir; pencatatan paralel di Excel; temuan BPK | Entitas ruangan + DBR digital; impor/ekspor kompatibel |
| Label tidak terpasang/hilang | Cetak label/QR + scan cek fisik (sudah ada) |
| Fisik ≠ buku (revaluasi nasional: ±16,66% NUP tak ditemukan, ±4,16% berlebih); RB tak diusulkan hapus | Klasifikasi 6 kategori (sudah ada) + tiket tindak lanjut + dashboard "kesehatan data" (tanpa foto/ruangan/label; RB belum diusul hapus) |
| Pencatatan tidak real-time/tanpa dokumen sumber; persediaan "hilang" | Transaksi wajib rujuk dokumen sumber + lampiran; audit trail penuh; validasi keras (stok minus ditolak per layer, kode dari referensi, periode terbuka) |
| Opname formalitas/terlambat | Jadwal+pengingat opname semesteran; BAOF ter-generate; kunci periode |
| Jaringan lambat | Offline-first (keunggulan AMAN yang sudah terbukti) |
| Salah input kode/harga; data anomali migrasi | Referensi kodefikasi terpusat (✅ sudah dibangun #73–#74); template impor tervalidasi per baris |
| Dokumen kepemilikan tak tertib | Lampiran digital per aset (BAST sudah; sertifikat/BPKB menyusul di modul Pengamanan) |

---

## 13. Implikasi Desain per Modul (ringkas)

| Modul (fase) | Keputusan desain dari pustaka ini |
|---|---|
| Kodefikasi (✅) | 5 level dari panjang prefix; golongan 1 vs 2–8; referensi dapat diimpor/diperbarui — jangan hard-code |
| Pembukuan (F2) | DBKP per golongan; flag intra/ekstra dari ambang kapitalisasi ber-parameter; Ruangan+DBR/DBL; KIB 6 jenis; barang bersejarah qty-saja |
| Persediaan (F2) | Perpetual + FIFO per layer; enum transaksi peta SAKTI; dua tahap usang/rusak; operator–approver; opname semesteran + BAOF + kunci back-date; mapping akun 1171xx |
| Pelaporan (F2, ✅ inti) | ✅ Hub arsip (#86) + Posisi BMN di Neraca (#93) + rekonsiliasi XLSX (#94) + LBKP mutasi per golongan (#95) + CaLBMN pra-isi bab I–V (§2.3a) + LKB per NUP + ringkasan B/RR/RB (§2.3b) + periode ber-kunci dengan penanda FINAL + tenggat penyampaian konfigurabel per periode — daftar "Implikasi AMAN" §2.3 tuntas |
| Penggunaan (F3, ✅ tahap awal) | ✅ Rekap pemegang + BAST (#87), daftar per pemegang PDF (#125), BMN idle berjenjang (#126), register SK PSP 5 jenis + arsip (#129/#137); ✅ tiket proses 4 rezim PMK 40/2024 — alih status, penggunaan sementara, dioperasikan pihak lain, penggunaan bersama — ber-pipeline + pengingat (#181/#183); ✅ BAST penetapan status penggunaan PDF per SK (#192); ✅ alur pengajuan PSP berstatus draf→diajukan→ditetapkan/ditolak, kompatibel mundur (#194) — daftar "menyusul" Penggunaan tuntas |
| Pengamanan (F3, ✅ tahap awal) | ✅ Dasbor tertib administrasi + pantau sengketa dari data inventarisasi (#88); ✅ register BMN bermasalah berstatus identifikasi→mediasi→blokir→litigasi→selesai (#169, §11); ✅ arsip dokumen kepemilikan per aset + lokasi penyimpanan Ps. 43 + scan (#171); ✅ status sertipikasi K1-K4 per dokumen sertipikat (#173); ✅ checklist pengamanan per aset per jenis dengan skor (#175, §11.2); ✅ register polis Asuransi BMN + pengingat masa berlaku (#177, §11.5, PMK 43/2025) — daftar "menyusul" Pengamanan tuntas |
| Pemeliharaan (F3, ✅ tahap awal) | ✅ Riwayat per kejadian per aset (jenis ringan/sedang/berat DJKN); rekap per TA (bahan DHPB Ps. 47); kondisi sebelum/sesudah; penanda telaah kapitalisasi ≥ ambang PMK 181; ✅ jadwal berkala ber-jatuh tempo (#91) + DHPB PDF semesteran/tahunan (#90) + ekspor CSV riwayat (#167) |
| Perencanaan (F4, ✅ tahap awal) | ✅ Saringan kelayakan RKBMN pemeliharaan (#99) + kertas kerja XLSX (#100); ✅ usulan RKBMN per unit berstatus draft→diajukan→PB→Pengelola→telaah + SPTJM/reviu APIP (#179, PMK 153/2021 + KMK 128/KM.6/2022); menyusul: sanding SBSK (kalkulator menunggu lampiran PMK 138/2024, §14 butir 21) |
| Penganggaran (F4, ✅ tahap awal) | ✅ Register usulan berstatus diusulkan→telaah→DIPA→realisasi, nilai per tahap + akun BAS 53x/523 + serapan (#115, §9); AMAN pendamping — kanal resmi SIMAN V2/SAKTI/KRISNA; ✅ sanding per akun BAS (#123) + ekspor CSV (#163) + kalender tenggat konfigurabel (#165) + sanding realisasi per triwulan (#186) — daftar "menyusul" Penganggaran tuntas |
| Pengadaan (F4, ✅ tahap awal) | ✅ Register perolehan per BAST/kontrak (jenis 101/102/103/105) + checklist dokumen sumber + tautan aset + penanda ekstrakomptabel PMK 181 (#117, §10); pencatatan resmi di SAKTI; menyusul: auto-daftar draft aset, lampiran scan, tautan paket ke register penganggaran |
| Pemanfaatan (F5, ✅ tahap awal) | ✅ Register perjanjian 6 bentuk + penjaga dokumen & jatuh tempo (#108, §6); ✅ pengingat kontribusi tahunan ber-NTPN (#121) + arsip scan per perjanjian (#131) + ekspor CSV (#158) + lampiran wasdal terpisah per perjanjian (#188) + atribut fasilitas transaksi PMK 18/2024 / PMK 139/2022 pada KSP/BGS-BSG (#190, §6.a) — daftar "menyusul" Pemanfaatan tuntas (catatan: "PDF" PMK 18/2024 BUKAN bentuk pemanfaatan) |
| Penilaian (F5, ✅ tahap awal) | ✅ Penyusutan garis lurus semesteran + daftar telaah (#102-#103, §5) + referensi masa manfaat dikelola (#107); ✅ register koreksi nilai & hasil penilaian per aset (revaluasi/LHIP/BA + checklist tercatat SAKTI) (#184, PMK 99/2024 + Perpres 75/2017 + PMK 118/2017 jo. 57/2018 jo. 107/2019); AMAN bukan penilai — nilai wajar sah dari Laporan Penilaian DJKN |
| Pemindahtanganan (F6, ✅ tahap awal) | ✅ Register usulan 4 bentuk + dokumen wajib per tahap + tenggat lelang (#111, §7); menyusul: tabel konfigurasi jalur persetujuan/ambang nilai, arsip scan |
| Pemusnahan (F6, ✅ tahap awal) | ✅ Register BA multi-aset, persetujuan wajib, objek RB (#110); ✅ PDF BA siap tanda tangan (#119) + usulan penghapusan otomatis per aset BA (#120) + foto bukti pelaksanaan (#132) + ekspor CSV (#161) — daftar "menyusul" Pemusnahan tuntas |
| Penghapusan (F6, ✅ tahap awal) | ✅ Kandidat per jalur (#104): "Tidak Ditemukan" → penelusuran+TGR; RB → pemusnahan/pemindahtanganan; ✅ tiket usulan berstatus usul→proses→SK/tolak (#106) + arsip SK/berkas per tiket (#134) + ekspor CSV (#159); ✅ Jejak Aset Terhapus — arsip read-only dari log audit (kode/NUP/nama/nilai/oleh/waktu), aset dihapus permanen tetap tertelusur tanpa mengubah mekanisme hapus (#197) |
| Wasdal (F6, ✅ tahap awal) | ✅ Dasbor pemantauan 5 objek PMK 207 — mesin aturan atas register yang ada, tanpa input ganda (#113, §8); ✅ register penertiban ber-tenggat 15 hari kerja; ✅ pemantauan insidentil 10+5 hari kerja + PDF BA; AMAN penyiap data, kanal resmi SIMAN v2; menyusul: formulir lampiran PMK 207 |

---

## 14. Daftar Konsolidasi "Perlu Verifikasi"

1. Field lengkap KIB per 6 jenis → Lampiran PMK 181/2016.
2. Batas waktu statutori penyampaian laporan per jenjang → Lampiran PMK 181.
3. Redaksi FIFO/perpetual di Bab VI PMK 100/2025.
4. Susunan sub kelompok kodefikasi persediaan mutakhir + daftar akun 1171xx (BAS).
5. Status keberlakuan PMK 181/2016 per 2026 (tidak ada indikasi diganti).
6. Nomor PMK revaluasi BMN pada diagram (tertulis 97/PMK.06/2019).
7. Kode transaksi internal SAKTI (vs M0x/K0x aplikasi lama).
8. Dasar formal TGR atas selisih kurang persediaan.
9. Format baku DHPB (kolom minimal) — belum ada lampiran nasional seragam;
   sementara pakai kolom kartu pemeliharaan bahan ajar DJKN.
10. Periodisitas laporan DHPB KPB→PB: PP hanya menyebut "berkala";
    semesteran adalah praktik baku, konfirmasi kebijakan K/L masing-masing.
11. Angka lengkap Tabel I & II KMK 295/KM.6/2019 jo. 266/KM.6/2023 —
    lampiran belum dapat diunduh dari jaringan sesi riset; validasi via
    JDIH sebelum seed penuh referensi masa manfaat.
12. Frekuensi pemantauan periodik KPB dalam PMK 207/2021 — sumber DJKN
    terbelah (1x/semester vs 1x/tahun selesai akhir Februari); teks asli
    tidak terbaca dari lingkungan riset.
13. Struktur & jumlah formulir Lampiran PMK 207 (klaim "65 pemantauan +
    2 penertiban + 14 monev" hanya dari satu ringkasan pencarian) serta
    tenggat statutori pelaporan wasdal antar jenjang; nomor pasti KMK
    juknis SIMAN v2 (248/KM.6/2024).
14. Tenggat statutori PMK 153/2021 (penyampaian RKBMN & Hasil Penelaahan —
    sumber sekunder terbelah "minggu keempat Januari" vs "minggu ketiga
    Februari"); apakah PMK 41/2026 mengubah bab perencanaan anggaran
    PMK 62/2023; rincian akun BAS 6 digit terkini (pemutakhiran
    KEP-211/PB/2018).
15. Jenjang rupiah bentuk kontrak (bukti pembelian/kuitansi/SPK/surat
    perjanjian) pasca-Perpres 46/2025; ada-tidaknya PerLKPP payung baru
    pengganti PerLKPP 11/2021 & 12/2021; kepastian tidak adanya PMK
    pengubah ambang kapitalisasi PMK 181/2016 (cek daftar status JDIH).
16. Nomor lampiran PMK 181/2016 yang memuat format CaLBMN tingkat UAKPB
    (cuplikan terbelah "Lampiran IV" vs "Lampiran VI"); tenggat
    penyampaian LBKP semesteran "≤20 hari setelah semester berakhir"
    (aturan era SABMN lama — cek rezim PMK 181); kode transaksi
    pertukaran & reklasifikasi BPYBDS.
17. LKB (LKBT-PKPB1): urutan persis kolom kiri-ke-kanan, ada-tidaknya
    kolom Keterangan, dan tenggat "≤15 hari setelah TA berakhir" (dari
    modul pelatihan, bukan pasal PMK 181 langsung) — perlu satu PDF
    AstLaporanKondisiBarangUAKPB asli untuk verifikasi.
18. Pengamanan (§11): rincian bentuk per jenis BMN dari artikel DJKN &
    cuplikan KMK 21/KMK.01/2012 (bukan teks regulasi); ayat persis UU
    1/2004 Ps. 49 selain ayat (1); perubahan penjelasan Ps. 42 oleh
    PP 28/2020; taksonomi kasus & alur mediasi-blokir-litigasi.
19. PMK 218/PMK.06/2015: rincian pasal penyimpanan dokumen & status
    terkini; kategori sertipikasi K1-K4 + status Peraturan Bersama
    186/PMK.06/2009 & 24/2009 (belum dicek ke teks asli).
20. Asuransi BMN (§11.5): seluruh kutipan pasal PMK 97/2019 & PMK 43
    Tahun 2025 dari cuplikan (teks asli tak terbaca); definisi kategori
    BMN Program/Nonprogram; alur & tenggat perencanaan via SIMAN pasca
    PMK 43/2025; komposisi/syarat konsorsium; pengelola PFB (BPDLH) dan
    seluruh angka statistik cakupan/klaim.
21. SBSK & RKBMN per unit (riset Juli 2026, #179): PMK 138 Tahun 2024
    (SBSK) mencabut PMK 172/2020 dan berlaku untuk RKBMN mulai TA 2027
    [perlu verifikasi]; SEMUA angka m² per jenjang jabatan/ruang
    penunjang dari paparan PMK 172/2020 (saling konflik antar cuplikan
    — kalkulator SBSK DITUNDA sampai lampiran asli terbaca); alur
    berjenjang KPB→korwil→eselon I→PB + reviu APIP + SPTJM (PMK
    153/2021 + KMK 128/KM.6/2022) dari artikel DJKN/juknis MA.
22. Alih status & penggunaan sementara (riset Juli 2026, #181, PMK
    40/2024): tenggat BAST ≤1 bulan / SK penghapusan ≤2 bulan / lapor
    ≤1 bulan; jangka penggunaan sementara 5 th (tanah/bangunan) vs 2 th
    (lainnya); ≤6 bulan tanpa persetujuan Pengelola; apakah persetujuan
    alih status merangkap PSP baru — semua dari cuplikan, nomor pasal
    belum terkonfirmasi dari teks asli PMK 40/2024.
23. Penilaian/revaluasi (riset Juli 2026, #184): rantai PMK 111/2017 →
    173/2020 → PMK 99 Tahun 2024 (tanggal berlaku dua versi); status
    PMK 118/2017 jo. 57/2018 jo. 107/2019 "masih berlaku"; perlakuan
    akuntansi reval (nilai perolehan baru, akumulasi reset nol, masa
    manfaat baru = faktor kondisi × masa manfaat); alur koreksi
    revaluasi SAKTI (push pusat, verifikasi vs LHIP, validasi-approve);
    masa berlaku Laporan Penilaian — semua dari cuplikan (403).
24. Fasilitas transaksi pemanfaatan (riset Juli 2026, #190): PMK 18
    Tahun 2024 — tanggal penetapan (24 vs 25 Mar) & berlaku (15 vs 16
    Apr 2024); rumusan pasal definisi PJPB (Pengguna saja atau juga
    Pengelola); daftar persyaratan administratif & substantif
    permohonan; rincian objek yang dapat difasilitasi; jangka waktu
    maksimal fasilitas + perpanjangan; BUMN Pelaksana yang ditunjuk
    (PT SMI/PT PII baru terkonfirmasi untuk KPBU & PMK 139/2022-IKN);
    ada/tidaknya penggantian biaya fasilitas oleh mitra terpilih; isi
    Ketentuan Penutup (relasi ke PMK 139/PMK.08/2022); kepastian PMK
    115/2020 masih berlaku per Juli 2026 — semua dari cuplikan (403).

---

## 15. Sumber Utama

Regulasi: PSAP 05 (ksap.org/standar/PSAP05.pdf) · PMK 181/PMK.06/2016
(jdih.kemenkeu.go.id/dok/181-pmk-06-2016; peraturan.bpk.go.id/Details/121291)
· PMK 29/PMK.06/2010 kodefikasi · PMK 225/2019 → 234/2020 → 231/2022 jo.
57/2023 → PMK 100/2025 (kebijakan akuntansi; lampiran Bab VI persediaan di
peraturan.bpk.go.id/Download/96077) · PMK 207/2021 wasdal · PMK 118/2023
SIMAN · PP 27/2014 Ps. 46-47 jo. PP 28/2020 (pemeliharaan;
peraturan.bpk.go.id/Details/5464) · PSAP 07 par. 50-51 (kapitalisasi;
ksap.org/standar/PSAP07.pdf) · KMK 59/KM.6/2013 (masa manfaat + tabel
renovasi/overhaul) · PMK 153/PMK.06/2021 (RKBMN) · KEP-211/PB/2018 jo.
KEP-205/PB/2021 (akun 523xxx BAS) · Permen PU 24/PRT/M/2008 & PUPR
22/PRT/M/2018 (pemeliharaan vs perawatan gedung).

Materi resmi/teknis: materi DJKN "Penatausahaan BMN" 2017; Modul 5
Penatausahaan BMN (PUPR); modul e-learning KLC Kemenkeu; buku saku
inventarisasi Bawaslu; HAI DJPb "Penerapan FIFO Modul Persediaan SAKTI
TA 2021"; juknis perekaman transaksi & migrasi persediaan SAKTI (DJPb);
kamus SAKTI modul persediaan & rekam hasil opname (klinikakuntansi.net);
FAQ opname fisik SAKTI (KLC); batas waktu LBMN Unaudited 2025 (KPPN
Sampit); artikel wasdal DJKN (KPKNL Mamuju "Merindu BMN Seri 6",
Kanwil Suluttenggomalut "Pantau, Tertib, Lapor", Kanwil Jatim,
KPKNL Cirebon BMN idle); surat & pengumuman pelaporan wasdal
MA/BPS/PA 2024–2026 (Modul Wasdal SIMAN v2). Penganggaran: PMK 62/2023
jo. 107/2024 & 41/2026 · PMK 153/2021 (jdih.kemenkeu.go.id) ·
KMK 332/KM.6/2016 (reviu APIP) · KMK 39/KM.6/2025 (IPA) ·
PER-9/PB/2023 (revisi) · juknis RKA satker SAKTI (HAI DJPb) ·
artikel DJKN/DJPb/DJA (RKBMN, pagu indikatif, IKPA, e-SADEWA MA). Pengadaan: Perpres 16/2018 jo. 12/2021 jo. 46/2025
(jdih.lkpp.go.id) · SE Kepala LKPP 1/2025 · PerLKPP 11/2021 &
12/2021 jo. 4/2024 · Kep. 177/2024 (Katalog V6) & 93/2025 ·
PSAP 07 + Bultek 15 (KSAP) · surat DJPb S-429 & S-454 · LHP BPK
atas LKPP + Warta Pemeriksa · juknis SIMAK-BMN (kode transaksi).

Kendala lapangan: artikel KPKNL Tangerang I/Metro/Singkawang; DJKN
"Pentingnya Penatausahaan Persediaan"; knowledge sharing Ittama DPR;
jurnal UNJ/STIA LAN/UNRAM/Darmajaya; analisis kendala SAKTI (KPPN
Meulaboh); temuan BPK persediaan (media).

*(URL lengkap tersimpan pada laporan riset sesi 2026-07-12; cantuman di
atas cukup untuk menelusuri ulang tiap sumber.)*
