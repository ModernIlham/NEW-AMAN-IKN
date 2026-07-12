# Pustaka Regulasi & Alur Bisnis BMN

> Rangkuman riset regulasi dan praktik resmi sebagai **bahan rujukan wajib**
> sebelum membangun modul apa pun di AMAN — dipakai bersama
> `docs/MASTERPLAN-SIKLUS-BMN.md`. Disusun dari riset internet Juli 2026
> (sumber di §7). Butir bertanda **[perlu verifikasi]** belum terbaca dari
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
| Pemanfaatan | PMK 115/PMK.06/2020; PDF PMK 18/2024 | — |
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

## 5. Kendala Umum Satker → Fitur Penangkal AMAN

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

## 6. Implikasi Desain per Modul (ringkas)

| Modul (fase) | Keputusan desain dari pustaka ini |
|---|---|
| Kodefikasi (✅) | 5 level dari panjang prefix; golongan 1 vs 2–8; referensi dapat diimpor/diperbarui — jangan hard-code |
| Pembukuan (F2) | DBKP per golongan; flag intra/ekstra dari ambang kapitalisasi ber-parameter; Ruangan+DBR/DBL; KIB 6 jenis; barang bersejarah qty-saja |
| Persediaan (F2) | Perpetual + FIFO per layer; enum transaksi peta SAKTI; dua tahap usang/rusak; operator–approver; opname semesteran + BAOF + kunci back-date; mapping akun 1171xx |
| Pelaporan (F2, ✅ inti) | ✅ Hub arsip (#86) + Posisi BMN di Neraca (#93) + rekonsiliasi XLSX (#94) + LBKP mutasi per golongan (#95); menyusul: periode ber-kunci, CaLBMN + LKB, tenggat konfigurabel |
| Penggunaan (F3) | PSP/alih/sementara/pihak lain/bersama + BMN idle (PMK 40 & 120/2024) |
| Pemeliharaan (F3, ✅ tahap awal) | Riwayat per kejadian per aset (jenis ringan/sedang/berat DJKN); rekap per TA (bahan DHPB Ps. 47); kondisi sebelum/sesudah; penanda telaah kapitalisasi ≥ ambang PMK 181; jadwal berkala & DHPB PDF menyusul |
| Penghapusan (F6) | Kandidat dari "Tidak Ditemukan" + tiket TGR/penelusuran dari tindak lanjut inventarisasi |

---

## 7. Daftar Konsolidasi "Perlu Verifikasi"

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

---

## 8. Sumber Utama

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
Sampit).

Kendala lapangan: artikel KPKNL Tangerang I/Metro/Singkawang; DJKN
"Pentingnya Penatausahaan Persediaan"; knowledge sharing Ittama DPR;
jurnal UNJ/STIA LAN/UNRAM/Darmajaya; analisis kendala SAKTI (KPPN
Meulaboh); temuan BPK persediaan (media).

*(URL lengkap tersimpan pada laporan riset sesi 2026-07-12; cantuman di
atas cukup untuk menelusuri ulang tiap sumber.)*
