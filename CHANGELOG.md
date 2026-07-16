# Changelog — AMAN IKN

Catatan perubahan aplikasi **AMAN** (Aplikasi Manajemen Aset Negara) IKN, dari
awal pengembangan di branch ini hingga rilis terakhir. Diurutkan dari yang
**terbaru** ke yang **terlama**. Setiap entri merujuk ke nomor Pull Request
(`#n`) dan commit pada branch `main`.

> Format tanggal: `YYYY-MM-DD`. Semua perubahan UI di bawah sudah di-`yarn build`
> (craco) hingga sukses sebelum di-merge.

---

## ⚠️ Catatan teknis penting — aturan tap-target 44px global

Banyak bug tata letak di layar kecil (PR #7, #9, #11 — dan berpotensi muncul lagi)
berakar dari **satu** aturan global di `frontend/src/index.css`:

```css
/* Mobile touch targets */
@media (max-width: 1023px) {
  button, a { min-height: 44px; min-width: 44px; }
}
```

Aturan ini bagus untuk tombol berdiri sendiri (target sentuh WCAG ~44px), tetapi
**memaksa SETIAP `<button>`/`<a>` di ≤1023px menjadi minimal 44×44px** — termasuk:

- baris ikon padat (footer kartu galeri),
- badge berbentuk tombol (ribbon status kegiatan),
- kontrol kecil seperti `Switch` (Radix `Switch` merender sebuah `<button>`).

Akibatnya elemen-elemen itu membengkak → meluber, terpotong, atau menutupi
elemen lain — **hanya** di ≤1023px (di atas itu aturan mati, jadi terlihat normal).

### Pola perbaikan baku

Tambahkan utility **`min-w-0 min-h-0`** pada elemen yang terdampak. Selector
class (`.min-w-0` = `0,0,1,0`) menang atas selector tipe (`button` = `0,0,0,1`),
jadi override-nya pasti berlaku tanpa `!important`. Gunakan ini untuk:

- ikon-tombol di dalam strip/baris padat,
- badge/ribbon yang kebetulan berupa `<button>`,
- `Switch`/kontrol kecil yang tak boleh ikut 44px.

> Jika nanti ada lagi elemen mobile yang "tiba-tiba kebesaran/menutupi" di
> ≤1023px, **cek dulu apakah itu `<button>`/`<a>`** — kemungkinan besar penyebabnya
> aturan ini. Solusinya `min-w-0 min-h-0` (dan kalau perlu `leading-none`).

---

## [#296] UI Kelola Referensi Ruangan — 2026-07-16

- **Melengkapi #295 di sisi UI.** Halaman **Referensi Ruangan** (`RuanganPage`)
  dibuka dari **Beranda Modul** (tombol di samping "Referensi Pejabat") — master
  ruangan #295 kini bisa dikelola pengguna.
- **Semua user login** melihat daftar ruangan (kode/nama, gedung/lantai,
  penanggung jawab, status); **admin** menambah/mengubah/menghapus lewat dialog:
  kode ruangan, nama, gedung, lantai, **Penanggung Jawab Ruangan** (dropdown dari
  pejabat berperan `penanggung_jawab_ruangan`, #290), unit kerja, status aktif.
- Pencarian sisi-klien (kode/nama/gedung/penanggung jawab); selaras tema
  terang/gelap; memakai `GET /ruangan` + `GET /pejabat` (#295/#290). Wiring
  lazy-route di `App.js`.
- Perubahan UI murni; **eslint bersih**, `yarn build` (craco) sukses.

---

## [#295] Master Referensi Ruangan — fondasi KIR/DBR & lokasi terstruktur — 2026-07-16

- **Referensi baru menutup celah lokasi teks-bebas** (temuan riset SIMAN-G:
  ruangan/lokasi tak terstruktur). Master `ruangan` menata lokasi BMN per
  ruangan — fondasi **KIR (Kartu Inventaris Ruangan)** & **DBR (Daftar Barang
  Ruangan)**, PMK 181/2016.
- **`ruangan_utils.py`** (murni): `validate_ruangan` (kode & nama wajib),
  `ringkas_lokasi` (string lokasi ringkas untuk label/laporan: *Gedung · Lt. N ·
  KODE — Nama*). **`routes/ruangan.py`**: CRUD admin + `GET /ruangan`; **kode
  ruangan unik** (ditolak bila bentrok). Tiap ruangan dapat menunjuk
  **Penanggung Jawab Ruangan** (tautan ke registry pejabat #290).
- Pustaka §2.4b; **2 unit test** murni; `py_compile` bersih. Slice fondasi —
  UI kelola + tautan lokasi aset → ruangan menyusul.

---

## [#294] KPB aktif menandatangani LBKP, CaLBMN & LKB juga — 2026-07-16

- **Meluaskan #293** ke laporan satker-level lain. Blok tanda tangan **LBKP**,
  **CaLBMN**, & **Laporan Kondisi Barang (LKB)** kini memakai **Kuasa Pengguna
  Barang aktif** dari registry `pejabat` (`_penandatangan_kpb`) — LBKP & CaLBMN
  pada tanggal **akhir periode** laporan, LKB pada **tanggal cetak**.
- **Fallback** ke setelan `kasatker` tetap berlaku bila registry belum diisi →
  tanpa regresi. Kelima laporan satker-level (Neraca, Penyusutan, LBKP, CaLBMN,
  LKB) kini seragam memakai satu sumber penanda tangan.
- Perubahan wiring murni (memakai ulang helper #293); `py_compile` bersih, 4 unit
  test pejabat tetap lulus. Laporan per-kegiatan (DBKP/DBHI/RHI) memakai
  identitas kegiatan — di luar cakupan.

---

## [#293] Laporan pakai penanda tangan KPB aktif dari registry pejabat — 2026-07-16

- **Menghubungkan registry pejabat (#291/#292) ke dokumen resmi.** Blok tanda
  tangan **Laporan Posisi BMN di Neraca** & **Laporan Penyusutan BMN** kini
  memakai **Kuasa Pengguna Barang (KPB) aktif** dari registry `pejabat` pada
  tanggal laporan — bukan lagi `kasatker` tunggal di setelan.
- **`pejabat_utils.penandatangan_kpb(settings, pejabat_list, per_iso)`** (murni):
  ambil KPB yang **masih berlaku dengan SK terbaru**; **fallback** ke setelan
  laporan (`kasatker_nama/nip/jabatan`) bila registry belum diisi — jadi laporan
  lama tetap jalan tanpa perubahan.
- Helper async `_penandatangan_kpb` di `routes/reports.py` (muat registry +
  resolusi). **4 unit test** (registry vs fallback vs kosong); `py_compile` bersih.
- Laporan lain (LBKP, CaLBMN, DHPB, DBKP, LKB) menyusul memakai pola yang sama.

---

## [#292] UI Kelola Referensi Pejabat Penatausahaan — 2026-07-16

- **Melengkapi #291 di sisi UI.** Halaman **Referensi Pejabat** (`PejabatPage`)
  dibuka dari **Beranda Modul** (tombol di samping "Referensi Kodefikasi Barang")
  — kini registry pejabat #291 bisa dikelola pengguna, bukan hanya API.
- **Semua user login** melihat daftar pejabat (nama/NIP, peran, masa berlaku,
  status); **admin** menambah/mengubah/menghapus lewat dialog: nama, NIP/NRP,
  jabatan, pangkat/golongan, **peran** (chip multi-pilih: KPB, Petugas
  Penatausahaan/Operator SIMAK-BMN, Pengurus Barang, Penanggung Jawab Ruangan,
  PPK, Pengguna Barang), **unit akuntansi** (UAPB…UAPKPB), **No/Tgl SK
  penunjukan**, **masa berlaku**, status aktif.
- Pencarian sisi-klien (nama/NIP/jabatan); selaras tema terang/gelap; memakai
  `GET /pejabat` + `/pejabat/referensi` (#291). Wiring lazy-route di `App.js`.
- Perubahan UI murni; **eslint bersih**, `yarn build` (craco) sukses.

---

## [#291] Referensi Pejabat Penatausahaan BMN — fondasi back-end (riset PMK 181/2016) — 2026-07-15

- **Fase baru: manajemen data pejabat/pegawai penatausahaan** — hasil riset
  mendalam repo pendahulu (SIMAN-G/KERJA-BARENG) + situs SAKTI Pelaporan +
  PMK 181/PMK.06/2016. Menutup celah "referensi penanda tangan" yang di SAKTI
  wajib (KPA/PPK/PPSPM/Bendahara + penanda tangan aset) namun di AMAN dulu
  hanya `kasatker_nama/nip` tunggal di setelan laporan.
- **Registry `pejabat`** (`pejabat_utils.py` murni + `routes/pejabat.py`): daftar
  pejabat dengan **peran** (Kuasa Pengguna Barang/KPB, Petugas Penatausahaan
  BMN/Operator SIMAK-BMN, Pengurus Barang, Penanggung Jawab Ruangan, PPK,
  Pengguna Barang), **unit akuntansi** (jenjang UAPB→UAPPB-E1→UAPPB-W→UAKPB→
  UAPKPB + penanggung jawabnya), **SK penunjukan & masa berlaku**.
- **Pejabat aktif per peran & tanggal**: `GET /pejabat/aktif?peran=&per_tanggal=`
  memilih pejabat yang **masih berlaku** dengan **SK terbaru** — agar dokumen
  resmi (KIB/BAST/LBKP/penghapusan) memakai penanda tangan yang benar untuk
  tanggalnya. CRUD admin + `GET /pejabat/referensi` (dropdown UI).
- Pustaka §2.4a diperbarui (struktur & pejabat penatausahaan). **3 unit test**
  murni (referensi, validasi, pemilihan pejabat aktif per tanggal); `py_compile`
  bersih (suite pure lokal 343 lulus). Slice
  fondasi — pemanfaatan di blok tanda tangan laporan & UI kelola menyusul.

---

## [#290] Backup / Pulihkan / Reset: cakup SEMUA koleksi secara dinamis (perbaikan data-safety) — 2026-07-15

- **Perbaikan penting keamanan data.** Daftar koleksi untuk **backup, restore,
  dan system-reset dulu di-HARDCODE** dan mentok di versi lama (v3.4.0) — hanya
  10 koleksi. Seluruh modul yang ditambahkan sejak itu **tidak ikut**:
  `kodefikasi`, `masa_manfaat`, `penilaian_koreksi`, `usulan_penghapusan`,
  `persediaan`, `transaksi_persediaan`, `jadwal_pemeliharaan`, `pemeliharaan`,
  `pemanfaatan`, `pemusnahan`, `pemindahtanganan`, `penertiban`,
  `pemantauan_insidentil`, `pengadaan`, `pengamanan_*`, `penganggaran`(+kalender),
  `penggunaan_proses`, `psp`, `perencanaan_usulan`, `periode_pelaporan`,
  `bmn_idle`. Akibatnya: **backup tidak lengkap** (restore kehilangan data itu)
  & **"reset semua" menyisakan data yatim + foto**.
- **Kini DINAMIS:** koleksi di-enumerasi otomatis dari database, jadi **setiap
  modul baru langsung ikut** ter-backup, ter-restore, & ter-reset tanpa update
  manual. Kebijakan murni di `backup_utils.py` (teruji unit).
  - **Backup**: seluruh koleksi aplikasi + GridFS + uploads (kecuali transient:
    lock/OTP/job/idempotency/ws-events/cache-preview).
  - **Restore**: memulihkan **semua** koleksi yang ada di file backup (bukan
    daftar tetap) — koleksi baru ikut walau DB tujuan kosong; alias legacy
    (`activities`→`inventory_activities`) tetap dikenali; safety-backup +
    rollback kini mencakup semua koleksi.
  - **System Reset** (`/system/reset-all`): menghapus **seluruh** data
    operasional & referensi **+ membersihkan GridFS (foto/lampiran)**, tetap
    mempertahankan akun (`users`) & konfigurasi (`report_settings`, kuota) agar
    admin bisa login & kop surat tak hilang.
- **4 unit test baru** (383 suite lulus) memverifikasi cakupan modul baru, aturan
  keep-reset, & parsing isi backup. `py_compile` bersih.

---

## [#289] Penyusutan: konvensi INKLUSIF pada tanggal tutup buku (30 Jun/31 Des) — 2026-07-15

- **Keputusan pemilik proyek** atas temuan review (finding #1). Laporan/posisi
  penyusutan yang dijalankan **tepat pada tanggal tutup buku (30 Juni / 31
  Desember)** kini **MEMUAT** semester yang ditutup hari itu — bebannya memang
  dibukukan pada tanggal tersebut ("dibukukan tiap akhir semester", PMK 65/2017;
  selaras praktik SAKTI).
- **Dampak:** posisi per **30 Jun 2026** kini menghitung Sem I 2026 (mis. mobil
  contoh 7 semester, bukan 6); aset yang genap habis masa manfaat pada 31 Des
  kini bernilai buku **0** tepat di tanggal itu (sebelumnya baru 1 Jan). Tanggal
  **tengah-semester tidak terpengaruh** (tetap seperti sebelumnya).
- Helper murni baru `akhir_semester(iso)`; `hitung_penyusutan` menambah 1
  semester bila `per` tepat 30 Jun/31 Des. **+1 uji** (total suite 379 lulus).
  Endpoint & PDF penyusutan + pustaka §5 dicatat memakai konvensi inklusif.

---

## [#288] Koreksi hasil review: aset revaluasi tanpa tanggal perolehan tetap disusutkan — 2026-07-15

- **Tindak lanjut review menyeluruh penyusutan.** Perbaikan **kebenaran** yang
  ditemukan reviewer independen:
  - **status_susut** kini menggerbang pada **titik-mulai efektif** penyusutan
    (tanggal revaluasi untuk aset revaluasi; lihat `dasar_penyusutan`) — bukan
    hanya `purchase_date`. Aset yang **sudah direvaluasi** tetapi tanggal
    perolehannya kosong kini **tetap disusutkan** atas basis revaluasi (dulu
    keliru masuk "tanpa referensi" & keluar dari hitungan).
  - **Daftar telaah henti-susut** menampilkan **basis tercatat efektif** (nilai
    revaluasi bila ada), bukan selalu harga perolehan historis (informasional).
- **2 unit test baru** (total 22 lulus): revaluasi tanpa tanggal perolehan →
  susut; revaluasi dengan tanggal invalid + perolehan kosong → tanpa_referensi
  (fallback aman); henti-susut ber-revaluasi → harga = nilai revaluasi.
- **Catatan:** satu temuan konvensi (posisi tepat pada tanggal tutup buku 30 Jun/
  31 Des memasukkan semester yang ditutup) SENGAJA belum diubah — menunggu
  keputusan pemilik proyek karena mengubah angka pelaporan. Nits kosmetik
  (pembulatan tampilan ±Rp1) dibiarkan.

---

## [#287] Laporan Penyusutan BMN per golongan (PDF siap tanda tangan) — 2026-07-15

- **Memenuhi harapan auditor (pustaka §5).** Tombol **"PDF"** di halaman
  *Penilaian — Posisi Penyusutan* mengunduh **Laporan Penyusutan BMN** resmi:
  kop surat KPB + tabel **per golongan** (Nilai Perolehan · Akumulasi Penyusutan
  · Nilai Buku) + baris TOTAL + blok tanda tangan Kuasa Pengguna Barang.
- **Selaras kaidah penyusutan yang sudah rampung:** garis lurus semesteran tanpa
  residu (PMK 65/2017); aset yang **sudah direvaluasi** disusutkan atas **nilai
  revaluasi** dengan masa manfaat reset penuh (#285) dan dicatat jumlahnya.
- **Kejujuran data:** ringkasan telaah di kaki laporan — jumlah aset *habis masa
  manfaat*, *henti-susut* (rusak berat/hilang telah diusulkan penghapusan),
  *tanpa referensi masa manfaat* (tidak ditebak), dan *tidak disusutkan*
  (tanah/KDP/aset bersejarah).
- Endpoint `GET /penilaian/penyusutan-pdf?per_tanggal=` (reportlab, memakai ulang
  `rekap_penyusutan`); mengikuti pola generator PDF Neraca/LBKP yang ada. Data
  ter-uji (376 unit test lulus), PDF ter-verifikasi lokal, eslint bersih, build sukses.

---

## [#286] Penilaian: catatan basis revaluasi di halaman Posisi Penyusutan — 2026-07-15

- **Melengkapi #285 di sisi UI.** Halaman **Penilaian — Posisi Penyusutan** kini
  menampilkan **catatan** saat ada aset yang disusutkan atas nilai revaluasi:
  *"N aset disusutkan atas nilai revaluasi — masa manfaat di-reset penuh sejak
  tanggal revaluasi, akumulasi lama dieliminasi (PMK 118/2017 + Buletin Teknis
  SAP 18)"*.
- Muncul **hanya bila** `jumlah_revaluasi > 0` (dari endpoint `GET
  /penilaian/penyusutan`) — tak mengganggu tampilan bila belum ada aset
  ber-revaluasi. Selaras tema terang/gelap (aksen sky), ikon `RefreshCw`.
- Perubahan UI murni; eslint bersih (0 error), `yarn build` (craco) sukses.

---

## [#285] Penyusutan PSAP 07 sadar-revaluasi: aset yang telah direvaluasi disusutkan atas nilai revaluasi (masa manfaat reset penuh) — 2026-07-15

- **Fitur inti PSAP 07 — kaidah TERVERIFIKASI sumber primer.** Sebelumnya semua
  aset disusutkan atas **nilai perolehan historis** meski sudah direvaluasi.
  Kini aset yang **sudah direvaluasi final** (punya `nilai_wajar_terakhir`
  status SAKTI tercatat) "terlahir kembali" sesuai **PMK 118/PMK.06/2017 jo.
  57/2018 jo. 107/2019 + Buletin Teknis SAP No. 18**:
  - **Nilai perolehan baru = nilai revaluasi** (nilai wajar hasil penilaian DJKN).
  - **Akumulasi penyusutan lama dieliminasi** (nol) pada tanggal revaluasi.
  - **Masa manfaat di-reset PENUH** per kelompok, dihitung ulang **sejak tanggal
    revaluasi** (bukan sisa masa manfaat).
  - Metode garis lurus, tanpa residu, semesteran, konvensi semester penuh
    **tidak berubah**.
- **Dampak:** posisi penyusutan (`GET /penilaian/penyusutan`) memakai basis &
  jadwal yang benar untuk aset pasca-revaluasi — nilai buku tidak lagi lebih/
  kurang saji; `jumlah_revaluasi` melaporkan berapa aset yang demikian.
- **Kejujuran data:** kaidah ini sempat ditandai "perlu verifikasi" (pustaka §14
  butir 23) karena PDF regulasi primer **terblokir** dari lingkungan build.
  Teks primer **dikonfirmasi pemilik proyek** sebelum kode ditulis — pustaka §5
  & butir 23 diperbarui jadi *terverifikasi*.
- Perubahan **murni & teruji**: helper `dasar_penyusutan(asset)` (basis + titik-
  mulai) memakai ulang mesin `hitung_penyusutan`; `rekap_penyusutan` +
  `GET /penilaian/penyusutan` menyertakan field revaluasi. **20 unit test** lulus
  (2 uji baru). Tanpa data ditebak.

---

## [#284] Penyusutan PSAP 07: henti-susut juga untuk aset HILANG (Tidak Ditemukan) yang telah diusulkan penghapusan — 2026-07-15

- **Lanjutan koreksi #282 (PMK 65/2017 · PSAP 07 · pustaka §5).** Pustaka §5
  menyebut *"aset **hilang** / rusak berat yang **telah diusulkan** →
  direklasifikasi keluar aset tetap"*. #282 sudah menangani **rusak berat**;
  PR ini melengkapi sisi **hilang**.
- **Aset berstatus inventarisasi "Tidak Ditemukan"** kini diperlakukan setara
  rusak berat untuk henti-susut: **tetap disusutkan** selama masih tercatat
  sebagai aset tetap, dan baru **dihentikan** penyusutannya bila **telah
  diusulkan** penghapusan (usulan aktif — belum ditolak).
- **Dampak angka:** aset hilang yang **belum** diusulkan tetap masuk nilai buku
  per golongan (tidak lebih/kurang saji); yang **sudah** diusulkan pindah ke
  daftar telaah *henti-susut* dengan alasan "Hilang (Tidak Ditemukan)".
- Perubahan **murni & teruji**: `status_susut` kini membaca `inventory_status`
  di samping `condition`; endpoint `GET /penilaian/penyusutan` menyertakan
  `inventory_status` pada proyeksi. **18 unit test** lulus (2 uji baru); tanpa
  data ditebak.

---

## [#283] Layar penuh foto: cubit & gulir untuk zoom in/out + seret untuk menggeser (tanpa tombol) — 2026-07-15

- **Penampil foto layar penuh (dari pop-up foto) kini bisa di-zoom** — sebelumnya
  foto tak bisa diperbesar/diperkecil sama sekali. Sesuai permintaan: **tanpa
  tombol apa pun**, murni lewat gestur natural:
  - **Gulir roda tetikus** (desktop) → perbesar/perkecil ke arah kursor.
  - **Cubit dua jari** (HP/tablet) → perbesar/perkecil ke arah titik cubit.
  - **Seret** (tetikus atau satu jari) saat sudah diperbesar → geser/menggeser foto.
  - **Ketuk-ganda** → toggle: pas-layar ⇄ perbesar 2,5× ke titik yang diketuk.
- **Cerdas & aman:** zoom di-*jepit* 1×–5×; geseran dibatasi agar foto tak hilang
  dari layar; balik ke 1× otomatis mengembalikan foto ke posisi pas-layar; ketuk
  latar hitam tetap menutup penampil (tak keliru saat habis menggeser). Rotasi &
  ganti foto otomatis me-reset zoom.
- **Interaksi tetap lancar** — listener native *non-passive* (`wheel`/`touch`)
  agar `preventDefault` berlaku (halaman tak ikut menggulir/zoom); transform
  `translate → scale → rotate` menyatu dengan fitur putar foto (#277/#279).
- Logika murni `lib/zoomPan.js` (zoom-ke-titik, skala cubit/gulir, jepit geser)
  + **6 unit test**; `PhotoLightbox.FullscreenPhoto` menyambungkan gestur. eslint
  bersih (0 error), `yarn build` sukses.

---

## [#282] Penyusutan PSAP 07: aset Rusak Berat berhenti disusutkan HANYA bila telah diusulkan penghapusan — 2026-07-15

- **Koreksi kebenaran akuntansi (PMK 65/2017 · PSAP 07 · pustaka §5).** Sebelumnya
  **setiap** aset berkondisi **Rusak Berat** langsung dianggap *henti-susut* dan
  dikeluarkan dari perhitungan posisi penyusutan. Itu **terlalu dini**: aset rusak
  berat tetap berstatus **aset tetap** dan **tetap disusutkan** selama masih
  tercatat sebagai aset tetap.
- **Aturan yang benar** — penyusutan baru **dihentikan** saat aset rusak berat itu
  **TELAH DIUSULKAN** penghapusan/pemindahtanganan/pemusnahan (direklasifikasi
  keluar aset tetap ke Aset Lain-lain). Sinyal "telah diusulkan" dibaca dari
  `usulan_penghapusan` berstatus **aktif** (belum ditolak) — konsisten dengan
  daftar kandidat Penghapusan.
- **Dampak angka:** aset rusak berat yang **belum** diusulkan kini **ikut**
  perhitungan nilai buku per golongan (tidak lagi hilang dari posisi); yang
  **sudah** diusulkan tetap tampil di daftar telaah *henti-susut*.
- Perubahan **murni & teruji**: `status_susut(asset, peta, diusulkan=False)` +
  `rekap_penyusutan(..., diusulkan_ids=None)`; endpoint `GET /penilaian/penyusutan`
  menghimpun id aset ber-usulan aktif. **17 unit test** lulus (termasuk 3 uji baru
  untuk perilaku ini); tak ada data ditebak.

---

## [#281] "Salin dari aset sebelumnya" kini ikut menyalin koordinat GPS (cerdas) — 2026-07-14

- **Fitur "Salin dari aset sebelumnya" (edit cepat/inventarisasi) kini juga
  menyalin koordinat GPS aset sebelumnya** — titik awal wajar karena aset yang
  diinventarisasi beruntun biasanya berdekatan. Sebelumnya hanya lokasi/eselon/
  pengguna yang tersalin; koordinat tidak.
- **Cerdas, bukan asal salin:**
  - **Fill-if-empty** — koordinat hanya diisi bila field koordinat form masih
    **kosong**; tak pernah menimpa GPS segar/manual.
  - **Guard kesegaran** — koordinat hanya disalin bila konteks aset sebelumnya
    **masih baru (≤30 menit)**; aset yang disimpan lama kemungkinan berada di
    lokasi jauh (timestamp `ts` disimpan bersama konteks).
  - **Sementara** — koordinat salinan otomatis **digantikan** GPS kamera yang
    akurat begitu dapat fix (selaras GPS-pintar #279 `bestGpsAccuracyRef`).
  - Toast & tooltip tombol memberi tahu bila koordinat ikut tersalin.
- Helper murni `lib/salinKonteks.js` (`bolehSalinKoordinat`) + **6 unit test**;
  `AssetForm` (simpan `koordinat_*`+`ts` ke `aman_last_asset_ctx`, `applyLastCtx`
  cerdas), `InventoryFieldSheet` (tooltip). eslint bersih, `yarn build` sukses.

---

## [#280] Perbaikan: badge dokumen tak lagi berkedip di lightbox + kotak select galeri tak buka lightbox — 2026-07-14

- **Bug: badge "Dok x/y" berkedip (muncul lalu langsung hilang) di popup foto.**
  Lightbox men-seed dari aset galeri (punya `doc_total`/`doc_checked`), lalu
  fetch `GET /assets/{id}?exclude_media=true` **mengganti** `fullAsset` dengan
  respons yang TIDAK menghitung field itu (hanya ada di proyeksi list) → badge
  hilang. Kini fullAsset **digabung** (`{...seed, ...data}`): field segar dari
  server menang, hitungan dokumen dari seed dipertahankan → badge stabil.
  (`components/assets/PhotoLightbox.jsx`)
- **Bug: klik kotak select di galeri malah membuka lightbox.** Checkbox berada di
  dalam area foto yang `onClick`-nya membuka lightbox; `stopPropagation` di
  `onChange` tak menahan event **klik** yang menggelembung. Kotak select kini
  dibungkus `<label>` ber-padding lebar dengan `onClick` stopPropagation →
  ketuk di area select **hanya menyeleksi**, tidak membuka foto (fokus pengguna
  saat memilih = seleksi). (`components/assets/AssetGalleryCard.jsx`)
- Frontend saja; eslint bersih (0 error), `yarn build` sukses.

---

## [#279] GPS pintar kamera: kunci koordinat aset ke jepretan PALING AKURAT — 2026-07-14

- **Koordinat aset kini memakai fix GPS terakurat selama sesi kamera**, bukan
  fix terakhir yang mungkin ber-jitter/kurang presisi. Saat kamera terbuka,
  `watchPosition` mengalirkan `{lat,lng,accuracy}` terus-menerus; koordinat aset
  hanya di-commit bila fix baru **lebih akurat** (accuracy lebih kecil) daripada
  yang terbaik sejauh ini (fix pertama selalu dipakai). Hasil akhir = koordinat
  dengan GPS paling presisi di antara semua jepretan foto aset tersebut.
- **Per-aset**: "fix terbaik" di-reset tiap ganti aset (edit) atau simpan-lalu-
  baru (`cameraSavedCount`), sehingga tiap aset memilih koordinat terakuratnya
  sendiri. Komit jadi jarang (akurasi membaik lalu berhenti) — juga ringan di HP
  low-end. Sepenuhnya offline-safe (murni state lokal).
- Helper murni `lib/gpsAkurasi.js` (`koordinatValid`, `akurasiValid`,
  `lebihAkurat`, `pilihKoordinatTerbaik`) + **10 unit test**; validasi ketat
  (tolak `""`/`null` yang `Number()` ubah jadi `0`). Integrasi di
  `AssetForm.handleCameraGpsFix`. eslint bersih, `yarn build` sukses.

---

## [#278] Kamera: info pengguna terstruktur (Melekat ke + Nama Pengguna) di overlay & watermark foto — 2026-07-14

- **Info pengguna barang tampil terstruktur 2 baris** di halaman kamera (tambah
  aset & edit) dan **ikut tercetak di watermark** hasil jepretan/unduh:
  - `Melekat ke: <Individual | Jabatan — <nama jabatan> | Operasional — <Kegiatan/Acara/Kebutuhan | Ruangan>>`
  - `Nama Pengguna: <nama>`
  Sebelumnya (dari #274) hanya satu baris `Pengguna: <nama> [<melekat>]` yang
  padat. Kini dirapikan: baris **Melekat ke** lalu baris **Nama Pengguna** di
  bawahnya — konsisten di overlay layar kamera dan di stempel foto.
- Helper murni `deskripsiMelekat(formData)` (di luar komponen) merangkai
  deskripsi melekat dari `pengguna_melekat_ke` + `operasional_jenis` /
  `pengguna_jabatan`; dipakai identik oleh overlay UI dan watermark canvas.
  Baris hanya muncul bila ada datanya.
- Frontend saja (`components/assets/FullCameraSheet.jsx`); eslint bersih,
  `yarn build` sukses.

---

## [#277] Putar foto PERMANEN: rotasi mengubah berkas asli di semua tampilan (thumbnail/galeri/unduh/layar penuh) — 2026-07-14

- **Tombol Putar di lightbox kini menyimpan rotasi ke server (permanen).**
  Sebelumnya putar hanya memutar tampilan sesaat. Sekarang menekan Putar
  memanggil endpoint baru `POST /assets/{id}/photos/{idx}/rotate` yang:
  memutar **byte foto ASLI** di GridFS 90° (Pillow, searah jarum jam,
  `expand=True`), me-regen **thumbnail per-foto**, dan bila foto **cover**
  ikut me-regen **thumbnail daftar + galeri**, lalu menaikkan `version`.
  Akibatnya rotasi tampil **di semua tempat tanpa terkecuali** — thumbnail
  list, kartu galeri, unduhan foto asli, dan penampil layar penuh — bukan
  sekadar sesaat. Cache preview otomatis basi (etag memuat versi).
- **OCC + Idempotency.** Endpoint memakai CAS pada `version` (`$inc`) — kalah
  balapan versi → `409` + blob baru dibuang agar GridFS tak yatim; blob lama
  (pra-rotasi) dihapus setelah tulis sukses. Header `Idempotency-Key`
  didukung. Ber-audit (`Putar foto #n sebesar 90°`).
- **UX lightbox.** Umpan balik instan (rotasi tampilan sementara) selagi server
  memproses; setelah sukses foto dimuat ulang dengan versi baru (sudah menyatu)
  dan tombol memperlihatkan spinner + nonaktif selama proses. Gagal/offline →
  toast + tampilan dikembalikan. Operasi online (butuh server GridFS).
- Helper murni `photo_rotate_utils.py` (`normalisasi_derajat`, `rotate_jpeg_bytes`)
  + **7 unit test** (pytest 371 lulus). `backend/routes/assets.py`,
  `frontend/src/components/assets/PhotoLightbox.jsx`. eslint bersih, `yarn build`
  sukses.

---

## [#276] Lightbox: layar penuh DALAM aplikasi (tombol Back kembali ke lightbox, bukan keluar app) — 2026-07-14

- **Perbaikan bug: tombol Back saat layar penuh malah keluar aplikasi.**
  Sebelumnya tombol "Layar Penuh" membuka foto HD di **tab baru** (`window.open`);
  di PWA/HP itu menavigasi keluar app sehingga Back **keluar aplikasi**, bukan
  kembali. Sekarang layar penuh memakai **penampil DALAM aplikasi**
  (komponen `FullscreenPhoto`): memakai **Fullscreen API** bila tersedia dan
  jatuh ke overlay `fixed inset-0` bila ditolak (mis. iOS). `useBackGuard`
  memastikan **Back / gesture geser menutup penampil** dan kembali ke lightbox —
  tidak pernah keluar aplikasi. Escape / keluar-fullscreen sistem juga menutup
  penampil. Rotasi tampilan lightbox ikut terbawa ke layar penuh.
  (`components/assets/PhotoLightbox.jsx`; `data-testid` `lightbox-fullscreen-view`,
  `lightbox-fullscreen-close`.)
- Frontend saja; eslint bersih (0 error), `yarn build` sukses.

---

## [#275] Lightbox foto: layar penuh (HD asli) + putar; perkecil "×" foto di HP/tablet; kolom Eselon II & Pengguna di list desktop — 2026-07-14

- **Lightbox — tombol Layar Penuh + Putar, tata letak ditata ulang.** Popup foto
  kini punya toolbar vertikal kiri-atas berisi **Unduh · Layar Penuh · Putar**
  (sebelumnya hanya Unduh). *Layar Penuh* membuka **foto HD asli** (resolusi
  penuh, tanpa `w=`) di **tab baru** — dibuka sinkron pada klik via
  `window.open` (token disematkan `authMediaUrl`, tak diblokir popup-blocker).
  *Putar* memutar tampilan 90°/180°/270° (preview; batas dimensi ditukar saat
  90°/270° agar tetap muat, reset otomatis saat ganti foto).
  (`components/assets/PhotoLightbox.jsx`)
- **Tombol "×" hapus foto lebih kecil di HP/tablet.** Di halaman tambah/edit
  aset, lingkaran ikon "×" per-foto tak lagi membengkak jadi 44px oleh aturan
  tap-target global ≤1023px — ditambah `min-w-0 min-h-0` (lingkaran ~20px konsisten
  di semua layar). (`components/assets/AssetForm.jsx`)
- **List mode desktop (≥xl): Eselon II & nama Pengguna.** Kolom **Eselon** kini
  menampilkan **Eselon II** dengan font lebih kecil tepat di bawah Eselon I;
  kolom **Lokasi** menambah **nama pengguna** di baris kedua (font kecil, ikon
  pengguna). Hanya tampilan desktop (`hidden xl:block`).
  (`components/assets/VirtualizedAssetTable.jsx`)
- Frontend saja; eslint bersih (0 error), `yarn build` sukses.

---

## [#274] Kamera lapangan: auto-status inventaris + suara rana + info pengguna/melekat di foto — 2026-07-14

- **Auto status inventarisasi (default ON, ada toggle).** Saat foto **dan**
  koordinat sudah terekam dan status masih default *"Belum Diinventarisasi"*,
  aset otomatis disimpan sebagai *"Sudah Diinventarisasi"* — surveyor cukup
  memotret + kunci GPS tanpa mengetuk status (kerja lapangan cepat). Berlaku di
  **halaman kamera penuh** dan **inventarisasi cepat** (keduanya menyimpan lewat
  `AssetForm.handleSubmit`). Status yang **sudah diubah manual** (Tidak
  Ditemukan/Berlebih/Sengketa/Sudah) TAK PERNAH diubah. Toggle **Auto-inventaris
  ON/OFF** di kedua lembar; preferensi `localStorage aman_auto_inventarisasi`.
  Helper murni `statusInventarisasiOtomatis` + `autoInventarisasiEnabled`
  (`lib/inventoryStatus.js`); diterapkan ke **payload saja** (validasi &
  logika cover foto tak tersentuh).
- **Suara rana kamera.** Klik rana **disintesis** via Web Audio API (tanpa aset,
  tetap bunyi offline; best-effort, tak pernah melempar) saat foto benar-benar
  terambil — melengkapi getar. Toggle 🔊/🔇 di overlay kamera; preferensi
  `localStorage aman_shutter_sound`. Helper `lib/shutterSound.js`.
- **Info pengguna + jenis melekat di foto.** Watermark foto kini menambah baris
  `Pengguna: <nama> [<melekat> — <jenis operasional>]` (hanya bila ada datanya).
- Frontend saja. 2 lib murni + **13 unit test** baru; eslint bersih, `yarn build`
  sukses.

---

## [#273] Ekspor CSV dasbor integritas `/integritas/ekspor-ringkasan` (read-only) — 2026-07-14

- **Unduhan CSV kesehatan data (§5A).** Endpoint read-only baru
  `GET /integritas/ekspor-ringkasan` menghasilkan CSV: satu baris per register
  (Usulan Penghapusan, Pemindahtanganan, SK PSP, Jadwal Pemeliharaan, Kodefikasi
  Aset) berisi jumlah temuan + rincian per jenis masalah, plus baris **TOTAL** —
  untuk arsip/tindak lanjut. Sumber data sama dengan `/integritas/ringkasan`
  (#266); tak mengubah data.
- **Helper murni `ringkasan_csv_baris(hasil, label_masalah)`**
  (`integritas_utils.py`) menyusun baris CSV dari `gabung_temuan_integritas`
  (label masalah manusiawi). **4 unit test**. Endpoint memakai helper internal
  `_kumpulkan_bagian_integritas` (di-refactor DRY dari ringkasan). pytest
  **364 lulus**, compileall OK. Backend saja (pola #158, UTF-8 BOM utk Excel).

---

## [#272] FK Pemindahtanganan→Penghapusan (`penghapusan_id`) — §5A gap #5 tuntas — 2026-07-14

- **Tautan dua arah ber-FK id.** Saat usulan pemindahtanganan berstatus
  **selesai** (SK Penghapusan terbit), `nomor_sk_penghapusan` dicocokkan ke
  tiket `usulan_penghapusan` (via `nomor_sk`). Bila cocok:
  - usulan pemindahtanganan menyimpan `penghapusan_id` (+ snapshot
    `penghapusan_nomor_sk`) — FK id, bukan sekadar teks;
  - tiket penghapusan menyimpan back-link `sumber_pemindahtanganan_id` +
    `sumber_pemindahtanganan_bentuk` (penelusuran dua arah, pola #228).
- **Best-effort non-blocking**: tak cocok → nomor teks tetap tersimpan tanpa FK,
  transisi tak digagalkan; back-link tak menyentuh `version` tiket (hindari OCC
  409 palsu). Helper murni `taut_penghapusan(nomor_sk, usulan)`
  (`pemindahtanganan_utils.py`) + **4 unit test**. pytest **362 lulus**.
- Menutup sisa §5A gap #5 (Dokumen Sumber = simpul; rantai Pemindahtanganan →
  Penghapusan kini tertaut FK). Backend saja.

---

## [#271] Peringatan kodefikasi live di form aset (non-blocking, §5A Prinsip 2) — 2026-07-14

- **Umpan balik langsung saat mengisi Kode Aset.** `AssetForm` kini memanggil
  `GET /integritas/cek-kode` (debounce 500ms) saat `asset_code` berubah dan
  menampilkan **peringatan kuning non-blocking** di bawah field bila prefix kode
  belum terdaftar di referensi kodefikasi (golongan/kode tak terdaftar / panjang
  kode tak valid). **Tak pernah memblokir simpan** — data lama dengan kode tak
  terdaftar tetap bisa disimpan.
- Best-effort: gagal/offline diabaikan diam-diam (tak mengganggu input); sembunyi
  bila sudah ada error field. Melengkapi endpoint `/integritas/cek-kode` (#269).
- Frontend saja. `yarn build` sukses, eslint bersih (hanya warning lama).

---

## [#270] Perbaikan UX HP: jaga posisi scroll setelah simpan + muat ulang cerdas (auto-sinkron) — 2026-07-14

- **Posisi scroll HP tak melompat lagi setelah simpan.** Saat menutup form
  sesudah menyimpan, `refreshData` dulu memuat ulang & **menyusun ulang jendela
  galeri HP** (mengganti `mobileAssets` dengan satu halaman) sehingga posisi
  scroll/baris terselect melompat. Kini penutupan form memakai opsi
  `preserveMobile`: rekonsiliasi hitungan/daftar desktop TANPA menyentuh jendela
  infinite-scroll HP — posisi & fokus pengguna ke data terjaga (baris tersimpan
  sudah diperbarui optimis + via `onRowSynced`).
- **Muat ulang cerdas, tanpa dialog mengganggu.** `useUnsyncedGuard` tak lagi
  selalu menampilkan dialog konfirmasi bawaan peramban. Perilaku baru:
  - tak ada antrian → **muat ulang biasa** (pembaruan aplikasi lancar, tak perlu
    hapus cache manual);
  - ada antrian & **online** → **otomatis sinkron** (best-effort, dipancing saat
    `pagehide`/`beforeunload`) lalu reload berjalan — antrian juga persist di
    IndexedDB + auto-flush saat load, jadi tak ada data tertinggal;
  - ada antrian & **offline** → tetap ditahan dengan konfirmasi (data belum bisa
    dikirim ke server).
- Frontend saja. `yarn build` sukses, eslint bersih, uji `unloadGuard` lulus.

---

## [#269] Validasi lunak kode aset `GET /integritas/cek-kode` (§5A Prinsip 2) — 2026-07-14

- **Endpoint read-only non-blocking** `GET /integritas/cek-kode?asset_code=...`
  yang memvalidasi SATU kode aset terhadap referensi `db.kodefikasi` dan
  mengembalikan `status`/`pesan` peringatan (bukan penolakan) — untuk umpan
  balik **langsung** saat mengisi/menyunting kode aset. Melengkapi
  `/integritas/kodefikasi-aset` (#262) yang memindai seluruh aset.
- **Helper murni `cek_kode_kodefikasi(kode, terdaftar)`** (`kodefikasi_utils.py`)
  → `{kode, level_kode, level_terdaftar, status, peringatan, pesan}`; status:
  `kosong` / `ok` / `panjang_kode_tak_valid` / `golongan_tak_terdaftar` /
  `kode_spesifik_tak_terdaftar`. Memakai `level_terdaftar_terdalam` yang sudah
  ada. **6 unit test**. pytest **358 lulus**. Masterplan §5A gap #7 diperbarui.
- Backend saja (pemasangan di form aset menyusul sebagai iterasi frontend).

---

## [#268] Tab "Integritas" di panel Riwayat — dasbor integritas data (§5A) di UI — 2026-07-14

- **Surface kapstone #266 ke UI.** Panel **Riwayat** (`AuditLogPanel`) kini punya
  tab ketiga **Integritas** yang memanggil `GET /integritas/ringkasan` dan
  menampilkan **read-only**: status keseluruhan (konsisten / N temuan), jumlah
  pemeriksaan bermasalah, lalu rincian per register (Usulan Penghapusan,
  Pemindahtanganan, SK PSP, Jadwal Pemeliharaan, Kodefikasi Aset) beserta chip
  per jenis masalah (identitas basi, aset induk hilang, golongan/kode tak
  terdaftar, panjang kode tak valid).
- Dimuat **sekali** saat tab dibuka (scan lintas-register) + tombol muat ulang;
  tak mengubah data apa pun. Theme-aware (light/dark), responsif.
- Frontend saja. `yarn build` (craco) sukses, eslint bersih.

---

## [#267] Perbaikan bug: cover foto tak berubah di mode daftar setelah hapus + ganti cover — 2026-07-14

- **Bug.** Saat mengedit foto aset: menghapus foto yang sedang jadi cover lalu
  menetapkan foto lain sebagai cover, saat disimpan `thumbnail_index` tersimpan
  benar (form menampilkan cover yang benar saat dibuka lagi) TAPI thumbnail cover
  di **mode daftar** (`asset.thumbnail`) tetap menampilkan cover lama. Baru
  berubah bila cover diganti sekali lagi (tanpa menghapus foto).
- **Akar masalah.** Jalur `photo_ops` (hapus/tambah foto) me-regen thumbnail
  daftar HANYA bila byte cover berhasil diambil, dan mengambilnya lewat
  `get_photo_from_gridfs` yang memakai `ObjectId(id)` **tanpa penjaga** — id yang
  bukan 24-hex membuatnya melempar → `None` diam-diam → thumbnail lama dibiarkan.
  Jalur "ganti cover saja" memakai koersi **toleran** (`ObjectId.is_valid`
  fallback), itulah mengapa mengganti cover lagi memperbaikinya.
- **Perbaikan.**
  1. Helper murni baru `coerce_gridfs_id` (`gridfs_id_utils.py`) — koersi ke
     ObjectId hanya bila valid; dipakai `get_photo_from_gridfs` (`shared_utils.py`)
     sehingga jalur unduh foto (cover `photo_ops`, stream galeri `w=256`,
     lightbox) selaras & tak gagal senyap. **4 unit test**.
  2. Penjaga di jalur `photo_ops` (`routes/assets.py`): bila byte full-res cover
     gagal diambil tetapi thumbnail per-foto cover tersedia, regen composite
     cover dari situ → cover daftar **tak pernah** basi saat cover berganti.
- Backend saja (tanpa perubahan frontend). pytest **352 lulus**, compileall OK.

---

## [#266] Kapstone dasbor gabungan integritas `/integritas/ringkasan` (read-only) — §5A gap #8 — 2026-07-14

- **Endpoint kapstone read-only `GET /integritas/ringkasan`.** Menggabungkan
  SELURUH cek integritas §5A dalam satu panggilan: hitungan temuan per register
  (identitas snapshot basi 4 register — penghapusan, pemindahtanganan, SK PSP,
  jadwal pemeliharaan — + kodefikasi FK aset) plus **total lintas-cek** dan
  `per_masalah` gabungan. Tak menyertakan daftar item detail (ambil dari
  endpoint `/integritas/*` per register bila perlu). Tak mengubah data apa pun.
- **Helper internal baru di `audit.py`** (`_ringkas_identitas_snapshot`,
  `_ringkas_identitas_daftar`, `_ringkas_kodefikasi`, `_master_identitas_by_id`)
  yang hanya MENGHITUNG temuan per register — master aset di-lookup **batch
  `$in`** (hindari N+1). Sengaja **tidak me-refactor** 5 endpoint detail lama
  (hindari regresi; tak ada uji endpoint).
- **Helper murni `gabung_temuan_integritas(bagian)`** (`integritas_utils.py`) —
  menyatukan ringkasan per-register jadi total dasbor (`total_temuan`,
  `per_masalah` gabungan, `jumlah_cek`, `jumlah_cek_bermasalah`). **3 unit
  test**. pytest **348 lulus**. Masterplan §5A gap #8 diperbarui (kapstone
  ringkasan).

---

## [#265] Deteksi identitas aset basi di register jadwal pemeliharaan (read-only) — §5A Prinsip 1 — 2026-07-14

- **Perluasan §5A gap #8 / Prinsip 1 (lanjutan #261/#263/#264).** Endpoint
  **read-only** `GET /integritas/identitas-jadwal-pemeliharaan` mendeteksi
  snapshot identitas aset basi pada register `jadwal_pemeliharaan` (membekukan
  identitas per record) — master di-lookup **batch `$in`** (hindari N+1);
  laporkan `snapshot_basi` / `aset_master_hilang` + hitungan.
- **Helper murni `drift_identitas_tunggal(snapshot, master)`**
  (`integritas_utils.py`) — temuan untuk SATU record (blok bangun register
  single-snapshot; melengkapi `drift_identitas_daftar` untuk list). **3 unit test**.
- Deteksi identitas basi kini mencakup **empat** register hilir (penghapusan
  #261, pemindahtanganan #263, SK PSP #264, jadwal pemeliharaan #265). Read-only.
  pytest **345 lulus**. Masterplan §5A gap #8 diperbarui.

---

## [#264] Deteksi identitas aset basi di register SK PSP Penggunaan (read-only) — §5A Prinsip 1 — 2026-07-14

- **Perluasan §5A gap #8 / Prinsip 1 (lanjutan #261/#263).** Endpoint **read-only**
  `GET /integritas/identitas-psp` mendeteksi snapshot identitas aset basi pada
  register **SK PSP Penggunaan** (`db.psp`, per baris `aset[]`) — pakai ulang
  `drift_identitas_daftar` dengan lookup master **batch `$in`** (hindari N+1);
  laporkan `snapshot_basi` / `aset_master_hilang` + hitungan.
- **Helper murni `hitung_masalah(temuan)`** (`integritas_utils.py`) — ringkas
  daftar temuan → dict hitungan per jenis masalah (ringkasan konsisten antar
  endpoint integritas). **2 unit test**.
- Deteksi identitas basi kini mencakup **tiga** register hilir (penghapusan #261,
  pemindahtanganan #263, SK PSP #264). Read-only — tak mengubah data. pytest
  **342 lulus**. Masterplan §5A gap #8 diperbarui.

---

## [#263] Deteksi identitas aset basi di register pemindahtanganan (read-only) — §5A Prinsip 1 — 2026-07-14

- **Perluasan §5A gap #8 / Prinsip 1 (lanjutan #261).** Endpoint **read-only**
  `GET /integritas/identitas-pemindahtanganan` mendeteksi snapshot identitas aset
  (`asset_code`/`NUP`/`asset_name`) yang **basi** pada register `pemindahtanganan`
  — yang membekukan identitas per baris `aset[]`. Master di-lookup **batch** via
  `$in` (hindari N+1); melaporkan `snapshot_basi` / `aset_master_hilang` + hitungan.
- **Helper murni `drift_identitas_daftar(aset_list, master_by_id)`**
  (`integritas_utils.py`) → daftar temuan per baris (pakai ulang `identitas_drift`).
  **4 unit test**. Read-only — tak mengubah data. Deteksi kini mencakup **dua**
  register hilir (penghapusan #261 + pemindahtanganan). pytest **340 lulus**.
  Masterplan §5A gap #8 diperbarui.

---

## [#262] Validasi FK kodefikasi aset (read-only, non-blocking) — §5A Prinsip 2 — 2026-07-14

- **Integrasi §5A gap #7 / Prinsip 2 (kodefikasi sebagai FK).** Kode barang aset
  diturunkan dari prefix tetapi tak pernah divalidasi sebagai FK ke referensi
  `kodefikasi`. Endpoint **read-only** `GET /integritas/kodefikasi-aset`
  mengagregasi `asset_code` DISTINCT (aset aktif) dan melaporkan kode yang
  prefix golongan/level-nya **tak terdaftar** di `db.kodefikasi`, dengan ambang
  `golongan_tak_terdaftar` / `kode_spesifik_tak_terdaftar` /
  `panjang_kode_tak_valid` + jumlah aset per kode.
- **Helper murni `level_terdaftar_terdalam(kode, terdaftar)`** (`kodefikasi_utils.py`)
  → level terdalam (1–5) yang prefix-nya ada di himpunan kode terdaftar (0 bila
  tak ada), memakai `hierarchy_prefixes`. **4 unit test**.
- **Non-blocking & read-only** — hanya peringatan; **tidak** menolak/mengubah
  data lama (create/impor tetap jalan). Validasi soft-warning saat create/impor
  = langkah terpisah. pytest **336 lulus**. Masterplan §5A gap #7 diperbarui.

---

## [#261] Deteksi snapshot identitas aset basi (read-only) — §5A Prinsip 1 — 2026-07-13

- **Integrasi §5A gap #8 / Prinsip 1 (langkah read-only pertama).** Register
  hilir membekukan `asset_code`/`NUP`/`asset_name` saat record dibuat; bila
  master aset kelak diedit, snapshot itu jadi **basi**. Endpoint **read-only**
  `GET /integritas/identitas-penghapusan` membandingkan tiap usulan penghapusan
  dengan master aset TERKINI (via `asset_id`) dan melaporkan yang **`snapshot_basi`**
  (field yang berbeda) atau yang **`aset_master_hilang`** (master tak ada lagi),
  lengkap dengan hitungan.
- **Helper murni `identitas_drift(snapshot, master)`** (`integritas_utils.py`) →
  dict `{field: {snapshot, master}}` hanya untuk field yang beda; perbandingan
  ter-strip (None/""/spasi tepi setara → tak ada drift palsu). **6 unit test**.
- **Tidak mengubah data apa pun** — hanya deteksi/laporan; penyegaran otomatis
  saat master diedit & perluasan ke register hilir lain (pemeliharaan/
  pemindahtanganan/…) adalah langkah terpisah. pytest **332 lulus**. Masterplan
  §5A gap #8 diperbarui.

---

## [#260] Konsolidasi §5A: ringkasan status integrasi siklus BMN — 2026-07-13

- **Dokumentasi (masterplan §5A).** Menambah ringkasan status integrasi yang
  ringkas di atas daftar gap: menandai yang **TUNTAS** (proyeksi hilir Prinsip 3
  #234/#254/#255/#256; gap #1 double-count; rantai FK+snapshot Perencanaan →
  Penganggaran → Pengadaan → Aset/Persediaan #199/#257/#258/#259 — simpul Dokumen
  Sumber Prinsip 4) dan yang **TERSISA** sebagai fitur lebih besar (dasar
  penyusutan nilai wajar; OCC/approval Prinsip 5; kodefikasi FK Prinsip 2;
  segarkan snapshot identitas Prinsip 1; proyeksi BA Pemusnahan; auto-daftar
  aset dari perolehan). Hanya dokumentasi — tanpa perubahan kode.

---

## [#259] Persediaan masuk bisa tertaut perolehan Pengadaan (`perolehan_id`) — 2026-07-13

- **Integrasi §5A gap #2 / Prinsip 4 (Dokumen Sumber untuk persediaan).**
  Transaksi **MASUK** persediaan kini dapat menyimpan **`perolehan_id`** (FK ke
  perolehan Pengadaan) + snapshot beku identitas dokumen sumber
  (`perolehan_nomor_bast`, `perolehan_tanggal_bast`, `perolehan_jenis`,
  `perolehan_pihak`) pada jurnal `transaksi_persediaan`. Melengkapi #258 (aset):
  kini **aset maupun persediaan** dapat merujuk balik ke record perolehan sebagai
  simpul dokumen sumber.
- **Pola `snapshot_penganggaran` (#199/#257/#258).** Helper murni
  `snapshot_perolehan(perolehan)` (bentuk rata untuk jurnal) +
  `_ambil_snapshot_perolehan(perolehan_id)` — **404** bila id tak ditemukan,
  divalidasi **sebelum** mutasi stok agar tak ada layer masuk tanpa perolehan
  valid; kosong = lepas tautan.
- Field **opsional** `perolehan_id` di `TransaksiMasukIn` — backward-compatible;
  transaksi tanpa taut & transaksi massal tetap jalan seperti semula.
- Helper murni + **3 unit test**. Masterplan §5A gap #2 diperbarui. pytest **326 lulus**.

---

## [#258] Pengadaan → Aset dua arah: aset simpan `perolehan_id` (dokumen sumber) — 2026-07-13

- **Integrasi §5A gap #6 / Prinsip 4 (simpul Dokumen Sumber).** Tautan
  perolehan→aset selama ini SATU arah (`perolehan.barang[].asset_id`). Kini saat
  baris barang perolehan Pengadaan ditautkan ke aset master (baik saat
  `buat_perolehan` maupun `tautkan_barang`), **aset menyimpan `perolehan_id`** +
  snapshot beku identitas dokumen sumber (`jenis`, `pihak`, `nomor_bast`,
  `tanggal_bast`, `nomor_kontrak`) → bisa ditelusuri **dua arah** (aset ⇄
  perolehan).
- **Lepas tautan aman.** Saat baris di-untautkan / dipindah ke aset lain,
  back-link pada aset lama dilepas **hanya bila `perolehan_id`-nya cocok** (tak
  mengganggu tautan milik perolehan lain).
- **Provenance, bukan keadaan neraca.** Helper murni
  `build_asset_perolehan_projection`; proyeksi **best-effort** (perolehan tetap
  jurnal sumber) dan **TANPA** `$inc version` — menghindari OCC 409 palsu pada
  form edit aset yang sedang terbuka. `purchase_price`/field laporan tak disentuh.
- **3 unit test** (snapshot lengkap, `None`/`{}` → lepas tautan, tanggal dipangkas
  10 char & id di-strip). Masterplan §5A gap #2 & #6 diperbarui. pytest **323 lulus**.

---

## [#257] Perencanaan → Penganggaran ber-FK: usulan anggaran simpan `rkbmn_id` — 2026-07-13

- **Integrasi §5A gap #4 (Prinsip 4 — dokumen/usulan sumber jadi simpul).** Usulan
  Penganggaran kini menyimpan **`rkbmn_id`** (FK ke usulan RKBMN Perencanaan) +
  **snapshot beku** identitasnya (`rkbmn_uraian`, `rkbmn_tahun`, `rkbmn_jenis`,
  `rkbmn_unit`) saat dibuat. Sebelumnya dua register paralel hanya tertaut lewat
  teks bebas `sumber` → tak bisa telusur balik ke usulan RKBMN asal.
- **Tiru pola `snapshot_penganggaran` (#199, Pengadaan→Penganggaran).** Helper
  murni `snapshot_rkbmn(usulan)` + `_ambil_snapshot_rkbmn(rkbmn_id)` (404 bila id
  tak ditemukan; kosong = lepas tautan). Snapshot **dibekukan** agar jejak asal
  RKBMN tetap utuh walau usulan sumber kelak berubah/terhapus.
- Dengan ini rantai **Perencanaan → Penganggaran → Pengadaan** tertaut penuh
  (Pengadaan→Penganggaran sudah ber-FK sejak #199).
- Field opsional `rkbmn_id` di `UsulanAnggaranIn`; `purchase_price`/register lain
  tak tersentuh. Helper murni + **3 unit test**. Masterplan §5A gap #4 ditandai
  tuntas. pytest **320 lulus**.

---

## [#256] Pemindahtanganan selesai memproyeksi master aset (`dihapus`) — 2026-07-13

- **Integrasi §5A Prinsip 3 (Pemindahtanganan → master).** Saat usulan
  pemindahtanganan (jual/tukar/hibah/PMPP) berstatus **`selesai`** (SK Penghapusan
  terbit), setiap aset di usulan kini diproyeksi ke master: **`dihapus=True`** +
  jejak `penghapusan.{jalur:"pemindahtanganan", bentuk, nomor_sk, tanggal_sk}` +
  `$inc version` (bust cache/OCC) + audit. Sebelumnya aset yang dipindahtangankan
  tetap "hidup & bernilai penuh" di master → **double-count** di laporan resmi.
- **Pakai ulang mesin penghapusan (#234/#248/#253).** Marker memakai bentuk yang
  SAMA dengan penghapusan langsung, jadi SELURUH laporan hilir ikut **otomatis**:
  penyaringan posisi/nilai (DBKP/Neraca/rekonsiliasi) dan **tombstone mutasi
  KURANG** LBKP/CaLBMN di periode SK — tanpa kode laporan tambahan.
- **Best-effort & idempoten** (pola #234/#254): register `pemindahtanganan` tetap
  jurnal sumber; filter `dihapus != true` membuat aman dipanggil ulang & tak
  menimpa jejak penghapusan jalur lain; kegagalan proyeksi tak menggagalkan
  transisi. `purchase_price`/`condition` tak disentuh (nilai perolehan historis
  utuh untuk tombstone & audit).
- Helper murni `build_asset_pemindahtanganan_projection` + **4 unit test**
  (termasuk cross-check aset ter-proyeksi menghasilkan mutasi kurang di
  `build_lbkp_rows`). Masterplan §5A diperbarui. pytest **317 lulus**.

---

## [#255] Laporan posisi/nilai memakai nilai wajar revaluasi (`nilai_wajar_terakhir`) — 2026-07-13

- **Integrasi §5A Prinsip 3 (lanjutan #254).** Laporan **POSISI/NILAI** kini
  menghitung nilai buku terkini aset: **nilai wajar hasil revaluasi**
  (`nilai_wajar_terakhir`, proyeksi #254) bila ada, jika tidak nilai perolehan
  (`purchase_price`). Sebelumnya selalu memakai `purchase_price` mentah sehingga
  aset yang sudah direvaluasi tampil dengan nilai lama di neraca.
- **Helper murni `nilai_buku_aset(a)`** di `pembukuan_utils` — pakai
  `nilai_wajar_terakhir` bila **`is not None`** (nilai wajar **0** pun dihormati,
  dibedakan dari 'belum pernah direvaluasi'), selain itu `purchase_price`.
  Dipakai di `build_dbkp_rows` (menggerakkan **DBKP**, **Posisi BMN di Neraca**,
  klasifikasi intra/ekstra) dan rincian per-NUP **rekonsiliasi XLSX SAKTI**
  (kolom kini "Nilai Buku") sehingga Sheet 2 **tie-out** dengan total Sheet 1.
- **Sengaja scoped:** dasar **penyusutan** (`rekap_penyusutan`) dan laporan
  **MUTASI** (LBKP/CaLBMN — revaluasi adalah jenis mutasi tersendiri) **TIDAK**
  diubah → langkah terpisah agar PR kecil & aman. `purchase_price` tak disentuh.
- Helper murni + **5 unit test** (nilai wajar dipakai, 0 dihormati, fallback
  `purchase_price`, keduanya kosong→0, klasifikasi intra/ekstra ikut nilai
  wajar). Masterplan §5A diperbarui. pytest **313 lulus**.

---

## [#254] Revaluasi Penilaian memproyeksi nilai wajar ke master aset — 2026-07-13

- **Integrasi §5A Prinsip 3 (Penilaian → master).** Saat koreksi/revaluasi nilai
  ditandai **tercatat SAKTI** (final), master aset kini diproyeksi: field
  **`nilai_wajar_terakhir`** (nilai wajar terkini) + jejak `revaluasi.{nilai,
  nilai_lama, jenis, nomor/tanggal dokumen, koreksi_id}` + `$inc version`
  (bust cache/OCC) + audit `action="revaluasi"`.
- **`purchase_price` historis TAK ditimpa** — nilai perolehan tetap utuh untuk
  audit; laporan yang ingin memakai nilai wajar cukup membaca
  `nilai_wajar_terakhir` (langkah lanjut).
- **Best-effort & idempoten** (pola sama #234): register `penilaian_koreksi`
  tetap jurnal sumber; kegagalan/no-op proyeksi tak menggagalkan transisi SAKTI;
  transisi hanya sekali (guard status), revaluasi terbaru menimpa yang lama.
  Helper murni `build_asset_revaluasi_projection` + **3 unit test**. Masterplan
  §5A diperbarui. pytest 308 lulus.

---

## [#253] LBKP/CaLBMN: penghapusan via SK tampil sebagai mutasi kurang (saldo seimbang) — 2026-07-13

- **Melengkapi §5A untuk laporan MUTASI.** Setelah laporan POSISI/NILAI
  mengecualikan aset dihapus (#248/#249), kini **LBKP** & **CaLBMN** menampilkan
  penghapusan lewat **SK** (`dihapus=True`, proyeksi master #234) sebagai
  **mutasi KURANG** pada periode SK terbit — melengkapi tombstone hard-delete
  audit yang sudah ada.
- **Identitas saldo tetap seimbang** (*saldo akhir = saldo awal + mutasi tambah
  − mutasi kurang*): `build_lbkp_rows` kini sadar-tanggal-SK — aset yang SK-nya
  terbit **sebelum** periode tak lagi ikut saldo awal (sudah lenyap), yang
  **dalam** periode masuk saldo awal lalu dikurangi, yang **setelah** periode
  tetap sebagai BMN di saldo akhir.
- Helper murni `tombstones_penghapusan(assets)` (`pembukuan_utils.py`) +
  **4 unit test** membuktikan keseimbangan untuk keempat kasus. Tanpa perubahan
  data; hanya penyajian mutasi yang kini lengkap.

---

## [#252] Ubah Massal: bisa TAMBAH kelengkapan dokumen baru (nama kustom) secara massal — 2026-07-13

- **Kini bisa menambah dokumen kelengkapan BARU dari panel Ubah Massal.**
  Sebelumnya bagian "Kelengkapan Dokumen & Peralatan" hanya bisa meng-*aktifkan*
  item dari daftar bawaan/ yang sudah ada — **tak ada cara menambah dokumen
  bernama baru**. Ditambahkan input **"Tambah dokumen baru…"** + tombol: item
  baru langsung **aktif** dan ikut diterapkan ke **semua aset terpilih**.
- Dedupe nama (case-insensitive) agar tak menduplikasi item bawaan/existing;
  bisa ditambah via tombol atau tekan **Enter**.
- **Frontend-only**: backend (`routes/batch.py`) sudah meng-*append* item
  ber-nama baru ke tiap aset saat `document_checklist_items` dikirim — jadi cukup
  melengkapi UI-nya. Verifikasi: eslint 0 error, `CI=false yarn build` sukses.

---

## [#251] Efek getar (haptics): GPS ≤4 m akurat, simpan, & pindah aset di kamera — 2026-07-13

- **Umpan balik taktil di lapangan** — terasa tanpa harus melihat layar:
  - **Getar "kunci akurat"** saat akurasi GPS menembus **≤4 m** (sekali, saat
    transisi — bukan bergetar terus).
  - **Getar berbeda saat SIMPAN** (Simpan & Baru / Simpan & Scan) — satu getar mantap.
  - **Getar berbeda saat PINDAH ASET** di halaman kamera — tik pendek untuk
    *Berikutnya*, tik ganda untuk *Sebelumnya* (arah terasa beda).
  - Tik sangat ringan saat **menjepret foto**; dan getar "perhatian" saat
    **konflik sinkron** (data diubah pengguna lain) di dasbor.
- Helper `lib/haptics.js` (Web Vibration API, **best-effort**: desktop & iOS
  Safari mengabaikan tanpa error). Pola tiap kejadian sengaja BEDA + helper
  murni `resolveHapticPattern` (+4 unit test). Bisa dimatikan via localStorage
  `aman_haptics` = `off`.

---

## [#250] Lightbox: animasi kartu tetangga menyala saat digeser + preload aset tetangga (seamless) — 2026-07-13

- **Pop-up foto lebih hidup saat pindah antar-aset.** Kartu tetangga (peek)
  kini mulai **samar** sebagai petunjuk, lalu **opacity-nya bertambah mengikuti
  jauhnya geseran** ke sisi itu — kartu berikutnya/sebelumnya seolah "muncul"
  makin jelas seiring jempol menggeser. Kartu depan menyusut halus (efek
  kedalaman/berlapis). Dihitung dari helper murni `peekAnim` (`lib/lightboxAnim.js`,
  +6 unit test) → mudah diuji & konsisten di **ukuran layar mana pun**.
- **Perpindahan antar-aset terasa instan & seamless.** Foto pertama + thumbnail
  aset **tetangga** (sebelum & sesudah, sesuai urutan/filter aktif) kini
  **di-preload dini** — saat kartu berganti, gambar tujuan sudah di cache
  sehingga tak ada jeda/kedip. Melengkapi preload antar-FOTO yang sudah ada.

---

## [#249] Rekonsiliasi XLSX SAKTI: ikut kecualikan aset dihapus (selaras Neraca) — 2026-07-13

- Lanjutan #248: ekspor **Rekonsiliasi Posisi BMN (XLSX)** — sandingan
  SAKTI/MonSAKTI — kini memakai `active_asset_filter` yang sama, sehingga posisi
  per golongannya **konsisten dengan Laporan Posisi BMN di Neraca**. Tanpa ini,
  rekonsiliasi bisa menunjukkan *selisih semu* hanya karena aset ber-SK
  penghapusan (`dihapus=True`) masih ikut terhitung di ekspor tetapi tidak lagi
  di Neraca.
- Dengan ini keluarga laporan **POSISI/NILAI** (DBKP, Posisi BMN/Neraca, rekap
  penyusutan, rekonsiliasi XLSX) seluruhnya konsisten mengecualikan aset
  dihapus. Laporan **MUTASI** (LBKP/CaLBMN) tetap ditunda (butuh baris
  pengurangan agar saldo seimbang). Verifikasi: pytest unit lulus.

---

## [#248] Laporan posisi/nilai: kecualikan aset yang sudah DIHAPUS (stop double-count) — 2026-07-13

- **Integrasi §5A Prinsip 3 (lanjutan #234/#200).** Saat SK penghapusan terbit,
  master aset ditandai `dihapus=True`. Kini laporan **POSISI/NILAI** —
  **DBKP**, **Posisi BMN di Neraca**, dan **rekap penyusutan** (Penilaian) —
  **mengecualikan** aset `dihapus` sehingga nilai BMN tidak lagi *double-count*
  (aset yang sudah dihapus tak lagi dihitung sebagai milik).
- Helper bersama `active_asset_filter(base)` (`backend/report_filters.py`,
  +5 unit test): menggabungkan `{"dihapus": {"$ne": True}}` ke query — cocok
  untuk aset lama (tanpa field) & `dihapus=False`, hanya menyingkirkan
  `dihapus=True`. SATU sumber agar tidak drift antar-laporan.
- **Sengaja di-scope:** laporan **MUTASI** (LBKP/CaLBMN) BELUM diubah — di sana
  penghapusan harus tampil sebagai **baris pengurangan** agar saldo
  awal−mutasi=akhir tetap seimbang (langkah terpisah). Register & jejak audit
  penghapusan tetap utuh. Masterplan §5A diperbarui.

---

## [#247] Ubah Massal: tata letak ringkas & terkategori (per seksi) — 2026-07-13

- **Panel Ubah Massal ditata ulang jadi berkategori & padat** (permintaan
  "perbaiki design tampilan ubah massal agar ringkas padat dan terkategori").
  Field yang sebelumnya berjejal dalam dua grid datar besar kini dikelompokkan
  ke **seksi berjudul**: **Klasifikasi & Lokasi**, **Kondisi & Status** (selalu
  tampil), lalu — saat "Tampilkan Semua Field" — **Administrasi Perolehan**,
  **Identitas & Catatan**, **Pengguna / Penanggung Jawab**, **Koordinat GPS**,
  **Foto**, dan **Kelengkapan Dokumen & Peralatan**.
- Tiap seksi punya header ringkas (ikon + judul kecil, huruf kapital tipis) +
  garis pemisah tipis — lebih mudah dipindai, tidak memakan banyak ruang.
- **Murni tata letak/pengelompokan** — komponen helper `Section` baru;
  TIDAK ada perubahan logika simpan, unggah foto (kamera+galeri+multi+kompresi),
  GPS ≤8 m, maupun kelengkapan dokumen. Semua field, penanda "Kosongkan", dan
  aksi tetap sama persis.

---

## [#246] Offline lebih tahan banting: sync snapshot tak crash saat penyimpanan penuh — 2026-07-13

- **Cache offline pada perangkat nyaris penuh tidak lagi crash / rusak.**
  `syncSnapshot` (unduh snapshot aset untuk mode inventarisasi offline) kini
  **toleran kuota IndexedDB**: bila penyimpanan penuh di tengah proses, sync
  berhenti dengan anggun dan **melayani cache sebagian** yang sudah tersimpan
  alih-alih gagal total.
- **Cegah cache menyusut keliru**: pada *full sync* yang kena kuota, langkah
  rekonsiliasi hapus-baris-usang **dilewati** — karena sync berhenti lebih awal,
  banyak id sah belum sempat tercatat; menghapusnya justru akan mengecilkan
  cache. Penulisan meta juga dibungkus toleransi kuota (snapshot parsial tetap
  konsisten, tak korup).
- **Umpan balik jelas**: saat parsial, muncul notifikasi sekali —
  "Penyimpanan perangkat hampir penuh — hanya N aset tersimpan untuk mode
  offline" — dan antrian **simpan** tetap utuh (jalur tulis independen).
- Helper murni `isQuotaExceeded(err)` (`lib/idbErrors.js`, lintas-peramban:
  `QuotaExceededError`/`NS_ERROR_DOM_QUOTA_REACHED`/kode 22/1014) + 6 unit test.
  Kolaborasi multi-pengguna tetap dijaga OCC (versi/If-Match) yang sudah ada.

---

## [#245] Muat ulang aman: tahan reload/pindah versi selagi data offline belum tersinkron — 2026-07-13

- **Cegah kehilangan/kerusakan data offline saat muat ulang atau berpindah ke
  versi aplikasi yang lebih baru.** Selama masih ada antrian yang perlu
  disinkronkan (pending atau macet), penutupan/​reload halaman kini ditahan
  dengan dialog konfirmasi bawaan peramban (`beforeunload`) — pengguna tak lagi
  bisa tanpa sadar menutup aplikasi di tengah proses sinkron.
- Antrian tulis offline sendiri **sudah aman**: persist di IndexedDB +
  rehydrate saat mount + auto-flush saat online (useOptimisticQueue, PR #233/#202).
  Guard ini adalah **lapisan pengaman terakhir** agar tak ada data yang
  ditinggalkan sebelum tersinkron ke server.
- Implementasi: helper murni `hasUnsyncedWork({pendingCount, actionCount})`
  (`lib/unloadGuard.js`, +5 unit test) + hook `useUnsyncedGuard`
  (`hooks/useUnsyncedGuard.js`) yang memasang/melepas listener `beforeunload`
  sesuai ada-tidaknya antrian. Dipasang di `DashboardPage`. Service worker tidak
  memaksa reload otomatis saat versi baru (registrasi minimal di `index.html`),
  jadi tak ada auto-reload yang bisa memutus sinkron.

---

## [#244] Search data: filter Nama Pengguna + NIK/NIP pengguna aset — 2026-07-13

- **Filter Data** (panel filter lanjutan) kini punya dua kolom baru: **Nama
  Pengguna** (field `user`) dan **NIK/NIP Pengguna** (field `pengguna_nip`) —
  keduanya pencarian *contains* (mengandung), literal-safe (`re.escape`, anti-ReDoS),
  dan bisa dikombinasikan dengan filter lain maupun kotak pencarian bebas.
  Alasan dedikasi kolom: NIK/NIP **tidak** termasuk daftar `$or` pencarian bebas,
  jadi sebelumnya tak bisa dicari; nama pengguna kini bisa dipersempit presisi
  tanpa mencampur hasil dari field lain.
- Backend: parameter `user_filter` + `pengguna_nip` ditambahkan ke
  `build_asset_search_query()` (satu builder dipakai `GET /assets` **dan** ekspor
  geo KML/KMZ/SHP), plus diteruskan di endpoint `GET /assets` & ekspor geo — jadi
  filter ini juga mempengaruhi titik & unduhan peta, konsisten dengan filter lain.
- Offline: jalur `filterSnapshotRows` (snapshot lokal) ikut menyaring `user` &
  `pengguna_nip` (keduanya ada di `LIST_PROJECTION`), sehingga hasil offline
  identik dengan online.
- Badge filter aktif "Pengguna: …" & "NIK/NIP: …" (nada violet) muncul saat terisi,
  dengan tombol hapus per-filter. Ditambah 5 unit test murni untuk builder query.

---

## [#243] Lightbox: navigasi antar-aset cukup SWIPE (tombol panah dihapus) — 2026-07-13

- Menindaklanjuti #240: **tombol panah ‹ ›** untuk pindah antar-aset di kartu
  info **dihapus** — cukup **geser (swipe) kiri/kanan** pada kartu info untuk ke
  aset sebelum/berikutnya (peek kartu tetangga + umpan-balik drag + pintasan
  ↑/↓ tetap). Tampilan kartu info jadi lebih bersih. Navigasi antar-FOTO (dalam
  satu aset) di area foto tak berubah.

---

## [#242] Ubah Massal: MULTI-foto massal (banyak foto sekaligus, tetap terkompres, hormati batas 6/aset) — 2026-07-13

Lanjutan #241.

- **Tambah BANYAK foto massal sekaligus.** Dulu hanya 1 foto per Ubah Massal.
  Kini bisa pilih **beberapa foto** (Galeri `multiple`) atau jepret berulang via
  Kamera; muncul **grid pratinjau** dengan tombol hapus per foto. Tiap foto tetap
  melewati kompresi klien (`compressImageFile`).
- **Backend `batch_photos` (list).** `routes/batch.py` kini menerima
  `batch_photos` (daftar) selain `batch_photo` (tunggal, kompat lama) — dikompres
  sekali per foto lalu didistribusikan ke tiap aset **menghormati batas 6
  foto/aset** (hanya mengisi sisa slot; parity indeks GridFS/thumbnail
  dipertahankan seperti sebelumnya). Cover thumbnail dari foto pertama untuk aset
  yang semula tanpa foto.
- Catatan: redesign tata letak Ubah Massal ringkas/terkategori menyusul.

---

## [#241] Ubah Massal: opsi foto KAMERA (bukan hanya galeri) + Ambil GPS ikut aturan ≤8 m — 2026-07-13

- **Tambah foto massal kini punya opsi KAMERA.** Dulu hanya "Tambah Foto"
  (pemilih berkas/galeri). Kini dua tombol: **Kamera** (`capture` — langsung
  jepret di HP) & **Galeri** (pilih berkas). Keduanya tetap melewati kompresi
  klien (`compressImageFile`) seperti input foto lain.
- **Ambil GPS massal ikut aturan ≤8 m.** Koordinat hanya disimpan bila akurasi
  **≤8 m** (sejalan gating kamera); di atas itu koordinat sementara dibuang &
  muncul peringatan — mencegah satu koordinat berrange lebar terekam ke banyak
  aset sekaligus.
- Catatan: bagian **Kelengkapan Dokumen & Peralatan** memang sudah tersedia di
  Ubah Massal. Multi-foto massal + redesign tata letak ringkas menyusul.

---

## [#240] Lightbox foto: unduh foto ASLI (ikon kontras) + navigasi antar-ASET via geser kartu info — 2026-07-13

- **Tombol unduh foto asli (resolusi penuh).** Yang tampil di popup hanya varian
  preview (`w=1280`). Ditambah tombol ikon **Unduh** di pojok foto yang mengambil
  **file ASLI** (endpoint tanpa `w` → byte penuh) via blob download. Ikon di
  **lingkaran gelap semi-transparan + cincin putih + backdrop-blur** → kontras &
  jelas di light/dark maupun di atas warna foto apa pun.
- **Navigasi antar-ASET langsung dari popup.** Geser kiri/kanan pada **kartu
  info** (bukan foto) → pindah ke aset **sebelum/sesudah** sesuai urutan & filter
  aktif. Ada **peek/bayangan kartu tetangga** sebagai petunjuk, umpan-balik drag,
  tombol **‹ ›** (untuk desktop), penunjuk "Aset i/N", dan pintasan **↑/↓**. Geser
  foto (di area foto) tetap berpindah antar-FOTO seperti biasa.
- Berlaku di ketiga tempat lightbox dipakai: mode list, galeri, dan popup peta
  (masing-masing memakai daftar aset-nya sendiri sesuai filter aktif).

---

## [#239] Kamera/GPS: toleransi ≤8 m (kuning 6–8 m) + perbaikan animasi titik fokus — 2026-07-13

Revisi #235 mengikuti alur lapangan agar lebih cepat.

- **Toleransi koordinat dilonggarkan ≤6→≤8 m.** Rana kamera kini terkunci hanya
  bila akurasi **>8 m** (dulu >6 m). Cincin: **hijau ≤6 m**, **kuning 6–8 m**
  (masih boleh potret — mempercepat pengambilan), **merah >8 m** (rana dikunci).
  **≤4 m** tetap "sangat akurat" (cincin heboh + badge). `acquireAccuratePosition`
  `desiredAccuracy` 6→8 m (berhenti begitu ≤8 m).
- **Perbaikan animasi titik fokus (tap-to-focus).** Dulu cincin fokus tak
  bermula di titik sentuh & menyebar dari pojok — karena `animate-ping` menimpa
  `transform: translate` yang dipakai untuk memusatkan. Kini reticle dipusatkan
  via **margin negatif** (anchor tanpa transform di titik sentuh) + titik pusat
  kecil, sehingga cincin **menyebar tepat dari titik ketukan**.

---

## [#238] Toolbar seleksi aset: satu-kesatuan (toolbar + Ubah Massal menyatu, tanpa header ganda) — 2026-07-13

- **Toolbar seleksi & panel Ubah Massal kini satu kartu menyatu.** Dulu keduanya
  dua kotak berbingkai terpisah dengan header **ganda** ("N terpilih" di toolbar
  + "N aset dipilih — Ubah Massal" di panel) → terlihat berantakan & tak
  estetik. Kini saat panel terbuka, toolbar kehilangan sudut & garis bawahnya
  dan panel kehilangan sudut & garis atasnya sehingga **menyambung mulus**
  menjadi satu bagian ringkas.
- **Hilangkan header ganda:** saat menyatu (`attached`), panel tak lagi
  menampilkan judul "N aset dipilih — Ubah Massal" maupun tombol tutup (X) —
  keduanya sudah ada di toolbar (hitungan + tombol **Tutup**). Sisa kontrol di
  panel hanya pengalih **"Tampilkan Semua Field"**.

---

## [#237] Peta — filter "Barang Serupa": tampil SEMUA + garis pemisah tabel + kode·nama·unit — 2026-07-13

- **Tampilkan semua kelompok terdeteksi.** Dulu daftar kelompok Barang Serupa
  di-`slice(0, 100)` → jenis ke-101 dst. tak muncul. Kini **tak dibatasi**
  (daftar bisa digulir), sesuai jumlah barang serupa yang benar-benar terdeteksi.
- **Garis pemisah seperti tabel.** Tiap baris kelompok kini punya **garis pemisah
  bawah** sehingga mudah membedakan aset atas dengan bawahnya — di dropdown
  desktop maupun menu HP.
- **Tata letak per baris jadi kolom rapi:** `kode` (mono) · `nama` (truncate) ·
  `N unit` (violet, kanan) — bukan lagi satu teks memanjang. Header "Semua
  barang" kini menampilkan jumlah jenis terdeteksi.

---

## [#236] Sinkron offline handal: cegah self-409 + toast konflik tak berulang + Sinkronkan menuntaskan bentrok — 2026-07-13

Lanjutan #233. Keluhan: toast "Aset telah diubah oleh pengguna lain" muncul
terus & tanda sinkron tetap minta disinkron walau sudah online dan sudah diklik.

- **Akar masalah utama: self-409 pada edit berantai.** Edit kedua atas aset yang
  sama mengirim `If-Match` versi lama (versi saat form dimuat), padahal simpanan
  pertama sudah menaikkan versi server → server menolak 409 walau **hanya satu
  pengguna**. Kini `If-Match` memakai **versi tertinggi yang diketahui**
  (`resolveBaseVersion` = `max(baseVersion, lastSavedVersion)`, helper murni
  teruji unit) — tak pernah menurunkan versi, jadi bentrok orang lain yang benar-
  benar baru tetap terdeteksi.
- **Tombol Sinkronkan kini menuntaskan item bentrok.** Dulu klik Sinkronkan tak
  menyentuh item konflik (macet selamanya). Kini sinkron **manual** meng-retry
  item bentrok: `onConflict` sudah memuat versi server terbaru ke daftar,
  sehingga retry membangun ulang di versi itu (*last-write-wins* dengan data
  pengguna) dan **berhasil** — tanda hilang permanen. Auto-flush saat reconnect
  tetap melewati item bentrok (hindari menimpa perubahan orang lain secara pasif).
- **Toast konflik di-throttle per-aset (≥8 dtk)** → tak lagi bertubi-tubi saat
  beberapa percobaan sinkron atas aset yang sama.
- Offline tetap tersimpan di perangkat (IndexedDB) & auto-sinkron saat online
  kembali seperti sebelumnya — kini benar-benar tuntas karena self-409 hilang.
- Uji: `resolveBaseVersion` (7 kasus) hijau; eslint bersih; `CI=false yarn build` sukses.

---

## [#235] Kamera/GPS: cutoff ≤6 m + effect "heboh" ≤4 m + tombol Ambil GPS theme-aware — 2026-07-13

- **Cutoff koordinat diperketat 8→6 m.** Rana kamera kini terkunci bila akurasi
  GPS **>6 m** (dulu >8 m), sehingga koordinat berrange lebar tak terekam. Cincin
  tepi kamera: **hijau ≤6 m** (boleh potret), **merah >6 m** (rana dikunci).
  `acquireAccuratePosition` `desiredAccuracy` juga 8→6 m.
- **≤4 m = "sangat akurat" (jarang) → effect lebih heboh.** Saat akurasi
  menyentuh **±≤4 m**, cincin hijau menebal + bercahaya ke dalam, muncul cincin
  ping kedua, dan badge memantul **"🎯 Akurasi ±N m — segera potret!"** untuk
  mendorong surveyor langsung menangkap titik paling presisi.
- **Tombol "Ambil GPS" saat mencari kini theme-aware.** Sebelumnya warnanya tak
  ikut light/dark (dan meredup karena `disabled:opacity-50`) → terlihat kusam.
  Kini state "Mencari…" memakai amber yang jelas di kedua tema; state normal
  biru dengan varian `dark:`. Diperbaiki di form edit, InventoryFieldSheet
  (2 tombol), dan konsisten dengan gating kamera.

---

## [#234] Integrasi: proyeksi Penghapusan → master aset saat SK terbit (Prinsip 3) — 2026-07-13

Gap integrasi teratas §5A masterplan (Prinsip 3 Bab 5: *transaksi = jurnal,
master = proyeksi*). Sebelumnya SK penghapusan hanya tercatat di register
`usulan_penghapusan`; master `db.assets` tak pernah tahu asetnya sudah dihapus
→ laporan resmi berisiko *double-count*.

- **Proyeksi otomatis saat SK terbit.** Ketika tiket usulan transisi ke
  `sk_terbit`, master aset ditandai: `dihapus=True` + sub-record
  `penghapusan { status, usulan_id, jalur, nomor_sk, tanggal_sk,
  diproyeksikan_pada }`, `version` di-`$inc` (bust cache media/ETag + picu OCC
  409 pada form edit usang atas aset itu — memang seharusnya konflik), dan
  entri **audit** `action="penghapusan"` (muncul di Riwayat, badge merah
  "Penghapusan (SK)").
- **Best-effort & idempoten.** Proyeksi berjalan **setelah** transisi CAS
  sukses; filter `dihapus != true` membuat aman diulang; kegagalan/no-op
  (aset sudah tak ada) **tidak** menggagalkan penerbitan SK.
- **Scoped anti-regresi laporan.** SENGAJA tidak mengubah field yang dibaca
  laporan (`inventory_status`/`condition`/`purchase_price`) — laporan
  (DBKP/neraca/penyusutan) tetap identik. Penyaringan aset `dihapus` dari
  laporan (agar *double-count* berhenti) adalah langkah lanjutan terpisah.
- Helper murni `build_asset_penghapusan_projection` (teruji unit, 2 kasus baru;
  total 291 unit backend hijau). `eslint` bersih; `CI=false yarn build` sukses.
- Masterplan §5A diperbarui: Prinsip 3 kini ⚠️ Sebagian (Persediaan +
  Penghapusan + Pemeliharaan); tersisa proyeksi dari BA Pemusnahan, PSP, revaluasi.

---

## [#233] Sinkron: bedakan "perlu tindakan" vs "sedang sinkron" (tanda tak lagi menyala palsu) — 2026-07-13

- **Bug:** tombol/tanda sinkron di header tetap menyala walau sudah online &
  sudah ditekan **Sinkronkan** hingga tanda hilang; lalu **muncul lagi** tiap
  kembali ke halaman. Penyebab: penghitung `pendingCount` ikut menghitung item
  **konflik versi (409)** dan **kegiatan terkunci (423)** sebagai "pending
  sinkron", padahal `flushPending` memang **melewati** keduanya (retry otomatis
  pasti gagal lagi). Item ini tersimpan di IndexedDB dan **direhidrasi sebagai
  "failed" generik** tiap buka halaman → tanda menyala terus.
- **Perbaikan — hitung yang jujur:** helper murni baru
  `summarizeSyncStatuses` (di `frontend/src/lib/syncStatus.js`, lepas dari
  axios/idb agar bisa diuji unit) memisahkan:
  - **`pendingCount`** → hanya item yang **benar-benar bisa** diselesaikan tombol
    Sinkronkan (queued/saving/**gagal jaringan**). Setelah tersinkron, tanda
    hilang **permanen** (salinan persist sudah dihapus saat server konfirmasi).
  - **`actionCount`** → item **macet** yang perlu **tindakan manual per-baris**
    (konflik 409 / terkunci 423). Ditandai badge oranye **"perlu tindakan"**
    terpisah (ikon segitiga) — **bukan** tombol sinkron biru/kuning yang
    menyesatkan.
- **Rehidrasi diperbaiki:** item konflik dikembalikan sebagai status `conflict`
  (bukan `failed`), item terkunci ditandai `{locked}` — jadi tak lagi salah
  dihitung sebagai antrian sinkron saat halaman dibuka ulang.
- **Tampilan HP:** kartu aset kini punya banner **konflik** (oranye, "Tinjau" +
  abaikan) seperti mode list desktop, sehingga item macet bisa ditindak dari HP.
- Uji: unit test `summarizeSyncStatuses` (8 kasus) hijau; `eslint` bersih;
  `CI=false yarn build` sukses.

---

## [#232] Kamera: tap-to-focus + gating akurasi GPS (ring hijau/kuning + kunci rana) — 2026-07-13

- **Ketuk area kamera → fokus di titik itu (tap-to-focus).** Ketukan cepat
  (bukan gestur geser kecerahan) di posisi mana pun pada pratinjau kamera kini
  memunculkan **reticle** di titik ketukan + upaya menyetel fokus kamera ke
  titik tersebut (`applyConstraints` `focusMode`/`pointsOfInterest` — best
  effort; efek visual tetap ada bila perangkat mengabaikannya). Berlaku di
  **scanner** maupun **tambah aset baru**.
- **Gating akurasi GPS demi ketepatan titik lokasi.** Cincin di tepi area
  kamera menandai akurasi fix: **hijau berkedip bila ±≤6 m**, **kuning bila
  ±≤8 m**, **merah bila >8 m**. Bila akurasi **>8 m** (atau fix akurat belum
  didapat), **tombol rana dikunci & diredupkan** sehingga foto berkoordinat
  range terlalu lebar tak terekam — surveyor mendekat/menunggu sinyal
  mengerucut dulu. GPS mati/ditolak tidak menggate (tak ada koordinat = tak
  ada risiko). Melengkapi pengetatan `acquireAccuratePosition` (fix ≤8 m, #227).

---

## [#231] Mode list: klik foto baris aset → lightbox seperti galeri — 2026-07-13

- **Foto di baris daftar aset kini bisa diklik → membuka lightbox foto** yang
  sama seperti mode galeri & popup peta (`PhotoLightbox`). Berlaku di **tabel
  desktop** (thumbnail baris) maupun **kartu HP** (mode list) — hanya bila
  aset punya foto (kursor `zoom-in` + cincin biru saat hover/tekan). Lightbox
  memuat foto beresolusi penuh + navigasi antar-foto + info aset. Prop
  `onOpenPhoto` diteruskan ke `VirtualizedAssetTable`, `VirtualizedMobileCards`
  → `AssetMobileCard`; state `photoLightboxAsset` di DashboardPage merender
  `PhotoLightbox` (lazy).

---

## [#230] Header HP: gabungkan Pengguna + Riwayat + Keluar ke satu menu — 2026-07-13

- **Header lebih ringkas di HP.** Di layar kecil, tombol **Pengguna**,
  **Riwayat**, dan **Keluar** yang sebelumnya berjajar (membuat header penuh)
  kini disatukan ke **satu menu ringkas** (tombol titik-tiga di pojok kanan) —
  indikator online/offline + tombol mode gelap tetap tampil. Di layar ≥`sm`
  ketiga tombol tetap tampil terpisah seperti semula. Aksi Keluar diberi warna
  merah di menu agar jelas.

---

## [#229] Peta: tombol aktif/nonaktif pengelompokan (cluster) marker — 2026-07-13

- **Tombol "Cluster: Aktif/Mati"** di toolbar peta (desktop) + item di menu
  gabungan (HP) untuk **menghidupkan/mematikan pengelompokan marker**. Saat
  aktif, pin berdekatan dikumpulkan jadi gelembung ber-angka (#227); saat
  dimatikan, semua pin tampil satu per satu. Peralihan **memindahkan** marker
  yang sudah ada antar-layer (cluster ↔ layer biasa) tanpa memuat ulang —
  popup, drag, dan autosave koordinat tetap berfungsi. Factory
  `buildClusterLayer` dipakai bersama oleh init peta & toggle.

---

## [#228] Integrasi: audit lintas-modul + taut sumber Pemusnahan → Penghapusan — 2026-07-13

- **Audit integrasi antar-modul (siklus BMN).** Peninjauan kepatuhan 5 prinsip
  arsitektur (masterplan Bab 5) dituangkan ke **§5A Status Integrasi &
  Daftar Gap** di `docs/MASTERPLAN-SIKLUS-BMN.md`: identitas aset ✅ (risiko
  snapshot basi); kodefikasi ⚠️ (diturunkan tapi belum FK tervalidasi);
  transaksi=jurnal ❌ kecuali Persediaan (master hilir tak diproyeksikan);
  dokumen-sumber ❌ (belum ada `dokumen_sumber_id`); approval-gate ❌
  (`pending_changes` belum ada, OCC penuh hanya di `assets.py`). Delapan gap
  diurutkan berdampak untuk ditutup bertahap per PR kecil.
- **Taut struktural Pemusnahan → Penghapusan (gap #5).** Usulan penghapusan
  yang dibuat otomatis dari BA Pemusnahan kini menyimpan **FK** `sumber_ba_id`
  + `sumber_ba_nomor` + `sumber_modul="pemusnahan"` — sebelumnya rantai hanya
  tertaut lewat teks bebas nomor BA, sulit ditelusuri balik. Helper murni
  `usulan_penghapusan_dari_ba` (teruji unit, +2 → 289 passed) membangun
  record; route memakainya. Baca-saja bagi pengguna; fondasi telusur-balik
  rantai hilir siklus.

---

## [#227] Peta: akurasi GPS diperketat + clustering marker berdekatan — 2026-07-13

- **Koordinat GPS lebih akurat (radius lebih sempit).** Ambang "cukup akurat"
  (`desiredAccuracy`) diperketat **15 → 8 meter** dan durasi pengumpulan fix
  (`maxWait`) diperpanjang **8 → 12 detik**, sehingga GPS punya waktu
  mengerucut ke fix yang lebih ketat sebelum diterima; bila sinyal tak sampai
  8 m, fix **terbaik** dalam 12 detik tetap dipakai dan koordinat tetap
  diperbarui **realtime** selama proses (`acquireAccuratePosition`). Berlaku
  di tombol Ambil GPS pada form aset & ubah massal.
- **Marker berdekatan kini di-cluster (mudah diklik).** Peta memakai
  `L.markerClusterGroup`: pin yang **saling mepet** (dalam ~44 px ≈ ukuran
  pin) dikumpulkan jadi satu **gelembung ber-angka** biru; **klik cluster →
  peta memperbesar** ke area anggotanya (memisahkan pin), dan di zoom maksimum
  pin yang benar-benar bertindih di-**spiderfy** (dikipas) agar tiap pin bisa
  diklik satu per satu. Radius kecil menjaga HANYA pin yang benar-benar
  berdekatan yang dikelompokkan; pin yang renggang tetap tampil sendiri.
  Marker tetap **draggable** (setelah dipisah) dan popup + autosave koordinat
  tetap berfungsi. Dependency baru: `leaflet.markercluster`.
- **Spiderfy saat hover** untuk pin yang bertindih. Pin berkoordinat sama /
  nyaris sama tak bisa dipisah dengan memperbesar; kini begitu kursor
  menyentuh cluster rapatnya (rentang < ~60 px, atau saat sudah zoom
  maksimum), cluster langsung **dikipas** tanpa harus diklik — sehingga pin
  yang benar-benar bertumpuk pun bisa diklik satu per satu. Hanya untuk
  cluster kecil (≤15 pin) agar cluster besar yang menyebar tetap
  "klik → perbesar", bukan meledak jadi puluhan kaki di hover.

---

## [#226] Kamera lapangan: info aset per-baris (nama/kategori/kode+NUP/lokasi) — 2026-07-13

- **Overlay info aset di kamera dipecah per-baris.** Sebelumnya nama, kode,
  NUP, dan lokasi ditumpuk dalam **satu baris** yang langsung terpotong
  (`truncate`) — kategori bahkan tak tampil. Kini tiap informasi punya
  **barisnya sendiri**: **nama barang**, **kategori**, **kode barang · NUP**,
  dan **lokasi**. Teks yang tak muat pada satu baris boleh **turun ke baris
  ke-2**, dan baru dipotong "…" bila masih melebihi (dua baris per field,
  `line-clamp-2`). Berlaku di kamera lapangan untuk **tambah aset baru**
  maupun **koreksi cepat via scan QR** (komponen `FullCameraSheet` dipakai
  bersama). Baris kosong disembunyikan agar tetap ringkas.

---

## [#225] Perbaikan bug inventarisasi: notifikasi konflik berulang + kedip/loading foto popup peta — 2026-07-13

- **Notifikasi "Aset telah diubah oleh pengguna lain" tak lagi muncul
  berulang saat membuka kegiatan.** Penyebab: antrean simpan optimistis
  me-*rehydrate* item lama dari perangkat dan meng-*auto-retry* semuanya saat
  masuk kegiatan — termasuk item yang **dulu bentrok (OCC 409)**. Saat itu
  daftar aset belum termuat, jadi versi (If-Match) yang dikirim basi → server
  menolak (409) lagi → toast muncul → item disimpan ulang → berulang **tiap
  kali** buka kegiatan. Perbaikan: **auto-flush (rehidrasi/rekoneksi) kini
  melewati item yang berakhir konflik** — dibiarkan untuk ditinjau &
  di-*retry* manual per-baris (yang menyegarkan versi lebih dulu) atau lewat
  tombol **Sinkronkan** (aksi eksplisit user). Mengirim ulang otomatis edit
  basi di atas perubahan orang lain juga memang keliru secara OCC.
- **Foto pada popup marker peta tak lagi loading lama & berkedip cepat saat
  diklik.** Dulu lightbox menunggu round-trip `/assets/{id}` sebelum bisa
  menampilkan foto (spinner pemblokir), lalu mengganti array foto setelah
  fetch (memicu efek "memuat" menyala lagi → kedip). Kini foto **diseed
  seketika** dari data aset yang sudah dibawa baris peta (`photo_count` +
  `version`) sehingga `<img>` langsung dimuat; fetch metadata hanya memperkaya
  panel info dan **hanya membangun ulang URL foto bila jumlah/versi berubah**
  (tak me-reset foto yang sedang tampil). Keadaan "memuat" awal juga
  diinisialisasi benar → placeholder blur langsung tampil, bukan foto
  tajam-lalu-hilang. Berlaku sama di galeri maupun popup peta (komponen
  `PhotoLightbox` dipakai bersama).

---

## [#224] Ringkas toolbar seleksi inventarisasi — 1 baris + bedakan tombol/teks — 2026-07-13

- **Toolbar seleksi aset dipadatkan.** Sebelumnya (#222) toolbar melebar dan
  membungkus jadi dua baris di tablet/desktop, memakan banyak ruang; aksinya
  (pilih semua, kosongkan) tampil seperti **teks** biasa sehingga tak jelas
  mana yang bisa diklik. Kini:
  - **Satu baris** yang padat (tinggi tombol 28px, jarak rapat) — tidak lagi
    membungkus di lebar wajar.
  - **Hitungan = teks** (`N terpilih`, tanpa bingkai); **aksi = tombol**
    berbingkai/solid: "Pilih semua" (chip biru + ikon centang, tooltip
    "Pilih/batal semua aset di tampilan ini"), "Kosongkan" (chip merah + X),
    dan tombol utama "Ubah Massal/Tutup" (biru solid, kanan). Perbedaan
    bentuk membuat mana tombol vs teks langsung terbaca.
  - Di layar sempit label aksi menciut jadi ikon saja (tetap ber-`title`),
    hemat ruang tanpa kehilangan makna.

---

## [#223] Ekspor CSV jurnal transaksi persediaan (Persediaan) — 2026-07-13

- **Ekspor CSV seluruh jurnal transaksi persediaan** (`GET
  /persediaan/transaksi/export`) — melengkapi ekspor Persediaan (master
  sudah ber-CSV; kini **jurnal transaksi** juga). Satu baris per gerakan
  stok (masuk / keluar / mutasi pindah-gudang / opname), terurut waktu,
  memuat **kode transaksi SAKTI**, identitas barang (kode/NUP/nama),
  jumlah, harga satuan & total (nilai FIFO, dibulatkan), **stok
  sebelum/sesudah** (saldo berjalan), data dokumen (no. bukti, jenis
  dokumen, tanggal, no. kontrak, penyedia), unit penerima, lokasi asal→
  tujuan (mutasi), petugas, dan keterangan. Bahan **rekonsiliasi SAKTI**
  (pustaka §3 — pencatatan perpetual + FIFO). Helper murni
  `baris_csv_transaksi` (tanpa Mongo, teruji unit — field khas tiap jenis
  transaksi dibiarkan kosong bila absen, bukan error) + tombol "Ekspor
  Jurnal Transaksi" di menu Data. Baca-saja. Unit test +4 → 287 passed.

---

## [#222] UX seleksi aset: tutup Ubah Massal tak menghapus seleksi + select-all semua tampilan + tombol Pengguna tampil di HP — 2026-07-13

- **Menutup panel "Ubah Massal" tidak lagi mengosongkan seleksi.** Dulu
  menutup panel (X/Batal) ikut menghapus seluruh centang per-baris. Kini
  tombol tutup hanya **menciutkan** panel; seleksi tetap dipertahankan
  sehingga bisa dibuka-tutup tanpa kehilangan aset terpilih. Panel muncul
  otomatis saat seleksi pertama (0 → >0) dan hilang saat seleksi benar-benar
  dikosongkan.
- **Toolbar seleksi di SEMUA tampilan (HP/tablet/desktop).** Menampilkan
  jumlah aset terpilih, tombol **"Pilih/batal semua tampilan ini"**
  (select-all/deselect untuk daftar viewport aktif — tabel desktop atau
  galeri/kartu HP/tablet), **"Kosongkan seleksi"**, dan toggle
  **Ubah Massal/Tutup**. Sebelumnya select-all hanya ada di header tabel
  desktop; kini tersedia di HP/tablet untuk menghapus (mengosongkan) seleksi
  massal.
- **Tombol "Pengguna" (kelola user) kini tampak di HP mode admin.** Dulu
  disembunyikan (`hidden sm:flex`) di layar kecil sehingga admin tak bisa
  membuka manajemen pengguna dari HP. Kini tampil sebagai tombol ikon ringkas
  (ikon `Users`, label muncul ≥`md`) dengan `aria-label`/`title`.

---

## [#221] Ekspor CSV jadwal pemeliharaan berkala (Pemeliharaan) — 2026-07-13

- **Ekspor CSV** jadwal pemeliharaan berkala (`GET
  /pemeliharaan/jadwal/export`) — melengkapi ekspor Pemeliharaan (riwayat
  sudah #167; kini **jadwal** juga ber-CSV). Kolom: identitas aset,
  interval (bulan), tanggal mulai, terakhir dilaksanakan, **jatuh tempo**
  (dihitung: belum dilaksanakan → = mulai; sesudahnya → terakhir + interval),
  **status** (label: Terlambat / Segera jatuh tempo / Terjadwal, ambang 14
  hari), keterangan, pembuat. Helper murni `baris_csv_jadwal`
  (jatuh_tempo/status_jadwal, tanpa Mongo, teruji unit) + tombol unduh CSV
  di panel "Jadwal Berkala" (muncul saat ada jadwal). Baca-saja. Unit test
  +1 → 283 passed. Pedoman DKPB Ps. 46(2) PP 27/2014.

## [#220] Konsolidasi dokumentasi #205–#219 (masterplan + README) — 2026-07-13

- **Dokumentasi saja** (tanpa perubahan aplikasi). Menyelaraskan
  `docs/MASTERPLAN-SIKLUS-BMN.md` & `README.md` dengan batch fitur
  #205–#219: (1) **ekspor CSV seluruh register** modul **Penggunaan**
  (idle #212, proses #218, SK PSP #219) & **Pengamanan** (polis #205,
  kasus #213, dokumen #214, checklist #216) ditandai di tabel status modul
  + baris Fase 3; (2) peningkatan **Peta Aset** (#217): seleksi memfilter
  titik & unduh GIS, foto popup → lightbox, bar skala metrik + kompas +
  info skala/zoom; (3) kontrol **segmented** Analytics/Rekapitulasi/Barang
  Serupa di dasbor (#215). Tanpa data dummy.

## [#219] Ekspor CSV register SK PSP (Penggunaan) — 2026-07-13

- **Ekspor CSV** register SK penetapan status penggunaan (`GET
  /penggunaan/psp/export`) — melengkapi ekspor Penggunaan (kini idle #212,
  proses #218, **SK PSP** semua ber-CSV). SK **multi-aset di-flatten**: satu
  baris per aset (field SK diulang). Kolom: identitas aset, nomor & tanggal
  SK, jenis (label: PSP / alih status / sementara / pihak lain / bersama),
  penetap, status pengajuan (label: Draf Usulan / Diajukan / Ditetapkan /
  Ditolak — record lama tanpa status = Ditetapkan), jumlah lampiran,
  keterangan, pembuat. Helper murni `baris_csv_psp` (tanpa Mongo, teruji
  unit) + tombol unduh CSV di panel "Penetapan Status Penggunaan" (muncul
  saat ada SK). Baca-saja. Unit test +1 → 282 passed. Dasar PMK 40/2024.

## [#218] Ekspor CSV register proses penggunaan (Penggunaan) — 2026-07-13

- **Ekspor CSV** register proses penggunaan (`GET
  /penggunaan/proses/export`) — melengkapi ekspor Penggunaan (setelah idle
  #212). Tiket **multi-aset di-flatten**: satu baris per aset (field tiket
  diulang). Kolom: identitas aset, jenis proses (label: alih status /
  penggunaan sementara / dioperasikan pihak lain / penggunaan bersama),
  arah (keluar/masuk), pihak asal & tujuan, status (label pipeline),
  **status_tenggat** (dihitung dari `info_proses_sementara` untuk tiket
  berjangka yang berjalan: "Lewat tenggat" / "N hari lagi" [+ "(perpanjang)"
  bila ≤90 hari]; kosong bila tak berlaku), nomor & tanggal permohonan,
  tanggal mulai & berakhir, keterangan, pembuat. Helper murni
  `baris_csv_proses` (tanpa Mongo, teruji unit) + tombol unduh CSV di panel
  "Proses Alih Status & Penggunaan Sementara" (muncul saat ada tiket).
  Baca-saja. Unit test +1 → 281 passed. Dasar PMK 40/2024.

## [#217] Peta: seleksi memfilter titik & unduh GIS, foto popup dapat diperbesar, skala + kompas + bar metrik + rapikan dasbor — 2026-07-13

**Penyempurnaan tampilan dasbor (menyertai peta di atas):**

4. **Jarak mode tablet dirapatkan.** Wadah utama dasbor pada rentang tablet
   (`sm`) sebelumnya lebih renggang (`p-4`, `space-y-3`) dibanding HP &
   desktop; kini disetarakan dengan desktop (`sm:p-3`, `sm:space-y-2`)
   sehingga rapi di semua ukuran.
5. **Badge jumlah pada kontrol Analytics/Rekapitulasi/Barang Serupa dibuat
   seperti notifikasi.** Sebelumnya badge menyatu di dalam segmen &
   menutupi teks label (mis. "R… 163 BMN"); kini badge **mengambang di
   atas-tengah** segmen, sedikit menjorok keluar tepi kotak (gaya
   notifikasi, ber-`ring`), sehingga label tampil penuh dan tak tertutup.
6. **Perbaikan "efek turun sedikit" saat scroll di atas header.** App-shell
   dasbor kini dikunci setinggi viewport (`h-screen` + `overflow-hidden`)
   sehingga dokumen tidak lagi ikut ter-scroll/rubber-band saat roda mouse
   berada di atas header (area non-scroll) — hanya `<main>` yang menggulir.

---



Tiga penyempurnaan **Peta Aset** (inventarisasi):

1. **Seleksi aset memengaruhi titik peta + unduh GIS.** Bila ada aset yang
   **dipilih** di daftar, peta kini **hanya menampilkan pin aset terpilih**
   (irisan dengan filter aktif), dan **unduh KML/KMZ/SHP** ikut dibatasi ke
   pilihan tersebut. Backend: parameter `ids` baru di `GET /export/geo`
   (irisan filter ∩ pilihan via `build_asset_search_query(ids=...)`).
   Frontend mengirim id terpilih (batas aman 200 id/URL; lebih dari itu
   diberi tahu untuk mempersempit pilihan — tanpa memotong data diam-diam).
   Bar info peta menandai "titik aset terpilih".
2. **Foto pada popup marker dapat diklik → lightbox.** Bingkai foto di popup
   pin kini ber-kursor *zoom-in*; diklik membuka **lightbox foto yang SAMA**
   seperti saat foto dibuka di mode galeri (navigasi antar-foto, info aset).
   Komponen `Lightbox` diekstrak ke `PhotoLightbox.jsx` dan dipakai bersama
   galeri + peta (tanpa mengubah perilaku galeri).
3. **Info skala + kompas + bar skala metrik.** Peta kini menampilkan **bar
   skala metrik** (m/km), **kompas arah utara** (peta selalu north-up), dan
   **info skala nominal 1:N + level zoom** yang diperbarui otomatis saat
   diperbesar/digeser (piksel OGC 0,28 mm).

Verifikasi: `pytest` → **280 passed** (unit `test_export_geo_ids` baru:
`ids` → `{"id": {"$in": [...]}}`, kosong/None tanpa filter, irisan dengan
filter lain); `eslint` bersih; `CI=false yarn build` sukses.

## [#216] Ekspor CSV checklist pengamanan (Pengamanan) — 2026-07-13

- **Ekspor CSV** checklist pengamanan per aset (`GET
  /pengamanan/checklist/export`) — melengkapi ekspor register modul
  Pengamanan (kini kasus #213, polis #205, dokumen #214, **checklist**
  semua ber-CSV). Kolom: identitas aset, jenis objek (label:
  Tanah/Gedung/Kendaraan/lainnya), terpenuhi, total butir, persen,
  **butir_belum** (label butir yang belum terpenuhi, dipisah "; " sebagai
  bahan tindak lanjut), keterangan, tanggal cek, petugas. Helper murni
  `baris_csv_checklist` (skor via `skor_checklist`, tanpa Mongo, teruji
  unit) + tombol unduh CSV di panel "Checklist Pengamanan per Aset"
  (muncul saat ada data). Baca-saja, alat bantu internal (pustaka §11.2).
  Unit test +1 → 277 passed.

## [#215] Satukan toggle Analytics/Rekapitulasi/Barang Serupa jadi satu baris — 2026-07-13

- **Inventarisasi Aset** — tiga panel di atas baris data (**Dashboard
  Analytics**, **Rekapitulasi Inventarisasi**, **Barang Serupa**) yang
  sebelumnya bertumpuk vertikal (tiga bar ~120px) kini disatukan menjadi
  **satu kontrol segmented menyamping** — satu kartu utuh ber-divider,
  bukan tiga tombol/kartu terpisah. Segmen aktif diberi warna (biru untuk
  Analytics/Rekapitulasi, ungu untuk Barang Serupa) + chevron; badge
  jumlah (mis. "163 BMN", "N grup") tetap tampil di segmennya.
- Berlaku **seragam di semua viewport** (desktop, tablet, HP) — menghemat
  ruang vertikal dan **memperlebar area data**. Isi panel dirender di
  bawah baris kontrol saat segmennya dibuka (mode *embedded*: panel hanya
  merender konten, header jadi segmen). Pegangan geser-tinggi grafik
  Analytics dipindah ke tepi bawah kartunya.
- Teknis: komponen `PanelSegment` baru di `DashboardPage`; `AnalyticsPanel`
  / `RekapitulasiPanel` / `AssetGroupsPanel` menerima prop `embedded`
  (+ callback `onTotal`/`onCount` untuk badge). Menggantikan baris chip
  mobile lama. `eslint` bersih; `CI=false yarn build` sukses.

## [#214] Ekspor CSV arsip dokumen kepemilikan (Pengamanan) — 2026-07-13

- **Ekspor CSV** arsip dokumen kepemilikan (`GET
  /pengamanan/dokumen/export`), melengkapi pola ekspor register di modul
  Pengamanan (setelah polis #205 & kasus #213). Kolom: identitas aset,
  jenis (label: sertipikat/BPKB/STNK/IMB-PBG/perolehan/lainnya), nomor,
  atas nama, lokasi simpan (label Pengelola/Pengguna Barang), kategori
  sertipikasi (label K1–K4/SHP, untuk jenis sertipikat), berlaku sampai,
  **status berlaku** (Berlaku / Kedaluwarsa dihitung dari tanggal vs hari
  ini; kosong bila tanpa masa berlaku), jumlah lampiran, keterangan,
  pembuat. Helper murni `baris_csv_dokumen` (tanpa Mongo, teruji unit) +
  tombol unduh CSV di panel "Arsip Dokumen Kepemilikan" (muncul saat ada
  dokumen). Baca-saja. Unit test +1 → 276 passed. Dasar PP 27/2014 Ps. 43.

## [#213] Ekspor CSV register kasus BMN bermasalah (Pengamanan) — 2026-07-13

- **Ekspor CSV** register kasus/sengketa BMN bermasalah (`GET
  /pengamanan/kasus/export`), melengkapi pola ekspor register di modul
  Pengamanan (setelah polis #205). Kolom: identitas aset (kode/NUP/nama/
  lokasi), kategori (label: dikuasai pihak lain / tumpang tindih
  sertipikat / berperkara), status (label: identifikasi → mediasi →
  blokir → litigasi → selesai), uraian, pihak lawan, nomor perkara,
  pendamping, tanggal dibuat & diperbarui, pembuat. Helper murni
  `baris_csv_kasus` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel "Register BMN Bermasalah" (muncul saat ada kasus). Baca-saja,
  bahan laporan wasdal/CaLBMN. Unit test +1 → 275 passed.

## [#212] Ekspor CSV register tiket BMN idle (Penggunaan) — 2026-07-13

- **Ekspor CSV** register tiket penanganan BMN idle (`GET
  /penggunaan/idle/export`), melengkapi pola ekspor register. Kolom:
  identitas aset, alasan indikasi idle, status (label:
  klarifikasi/digunakan kembali/usul serah/diserahkan), nomor usulan
  penyerahan, nomor BAST serah, keterangan, pembuat, tanggal dibuat.
  Helper murni `baris_csv_idle` (tanpa Mongo, teruji unit) + tombol unduh
  CSV di panel "BMN Idle — Daftar Pantau" (muncul saat ada tiket).
  Baca-saja. Unit test +1 → 274 passed. Dasar PMK 120/2024.

## [#211] List mode: auto-pindah halaman saat lewati baris terakhir + area data lebih luas (desktop) — 2026-07-13

- **List (tabel) mode — auto-pindah halaman:** saat menekan Simpan/Update
  pada **baris terakhir** halaman tabel desktop sementara masih ada
  halaman berikutnya, aplikasi kini **otomatis berpindah ke halaman
  berikutnya** (kontrol paginasi + tabel ikut geser) lalu membuka baris
  **pertama**-nya untuk diedit — ritme input tak lagi mentok di halaman
  lama. `doFetch`/`goToPage` mengembalikan baris halaman baru; navigasi
  memilih `goToPage` (mode list ≥lg) vs infinite scroll (galeri/kartu HP).
- **Area data lebih luas (desktop):** kartu statistik atas (Total Aset /
  Nilai / Aktif / Maintenance) dibuat **ringkas satu baris** (label–nilai
  sejajar, padding & ukuran font lebih kecil) dan jarak antar-seksi header
  dipadatkan khusus `lg` — memberi porsi layar lebih besar untuk baris
  data. Tampilan tablet/HP tak berubah.

## [#210] Ekspor CSV register pemantauan insidentil Wasdal — 2026-07-13

- **Ekspor CSV** register pemantauan insidentil wasdal (`GET
  /wasdal/insidentil/export`), melengkapi ekspor register Wasdal
  (penertiban #207). Kolom: pemicu (label), tanggal mulai, lokasi, objek
  pemantauan (label), uraian, status, **tenggat aktif** + **status
  tenggat** (Lewat tenggat / "N hk lagi" per tahap pelaksanaan/lapor /
  Selesai, dihitung via `info_tenggat_insidentil`), nomor & tanggal BA,
  hasil, tanggal lapor, keterangan lapor, pembuat. Helper murni
  `baris_csv_insidentil` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel pemantauan insidentil. Baca-saja. Unit test +1 → 273 passed.
  Dasar PMK 207/2021 (pelaksanaan ≤10 hk, lapor ≤5 hk sejak BA).

## [#209] Galeri: infinite scroll dua arah + jaga aset terseleksi terlihat — 2026-07-13

- **Scroll dua arah (muat halaman sebelumnya):** bila pengguna berada di
  halaman tabel yang jauh (mis. halaman 5) lalu beralih ke mode galeri,
  kini **scroll ke atas otomatis memuat halaman sebelumnya** (4, 3, 2, 1)
  dan scroll ke bawah memuat berikutnya — data tetap **urut & sesuai
  filter**. Sebelumnya galeri hanya menampilkan halaman masuk dan halaman
  yang lebih kecil tak terjangkau. Diperbaiki bug `doFetch` yang mereset
  jendela galeri ke halaman 1; ditambah state `mobileFirstPage`,
  `loadPrevMobile` (prepend + paritas offline), sentinel atas
  IntersectionObserver, dan **penjangkaran posisi scroll saat prepend**
  (useLayoutEffect) agar tampilan tak "melompat".
- **Aset terseleksi selalu terlihat:** saat aset yang diedit berganti
  (mis. auto-lanjut setelah simpan), galeri/kartu kini **otomatis
  menggulir kartu aset tersebut ke tengah layar** (`scrollToIndex`) —
  tak perlu mencari lagi. Hanya saat aset aktif berubah, tidak melawan
  gulir manual pengguna.

- **Ritme input tak putus lintas halaman:** saat menekan Simpan/Update pada
  aset **terakhir yang dimuat** sementara masih ada halaman berikutnya,
  aplikasi kini otomatis memuat halaman berikutnya lalu membuka aset
  **pertama**-nya untuk diedit — tak lagi berhenti/menutup form di baris
  terakhir. Berlaku di form penuh, sheet inventarisasi cepat, dan Mode
  Kamera (tombol ▶). `loadMoreMobile` mengembalikan baris baru (menghindari
  masalah closure basi); gerbang tombol memakai `hasMoreToLoad`
  (`mobileCurrentPage < totalPages`); aset baru dikunci seperti navigasi
  biasa. Di tabel (≥lg) tak mengubah paginasi; di galeri/kartu memakai
  infinite scroll yang sama.
- **Galeri auto-muat lebih sigap:** pemicu "muat lebih banyak" diganti dari
  pengecekan indeks baris virtual (baru ter-mount saat mepet bawah) menjadi
  **IntersectionObserver** pada sentinel nyata dengan **prefetch 600px** —
  daftar termuat otomatis SAAT gulir *hampir* sampai bawah, terasa lebih
  cepat. Ditambah `overscroll-behavior: contain` agar momentum gulir tak
  bocor ke halaman (mengunci kepemilikan scroll di kontainer galeri).

- **Ekspor CSV** register penertiban wasdal (`GET
  /wasdal/penertiban/export`), melengkapi pola ekspor register. Kolom:
  sumber (label), tanggal dasar, tenggat, **status tenggat** (Selesai /
  Lewat tenggat / "N hk lagi" dihitung dari `status_tenggat_penertiban`),
  status, objek pemantauan (label), uraian, tindak lanjut, tanggal
  selesai, identitas aset tertaut (opsional), pembuat. Helper murni
  `baris_csv_penertiban` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel penertiban (muncul saat ada data). Bersifat baca-saja. Unit test
  +1 → 272 passed. Dasar PMK 207/2021 (tenggat 15 hari kerja).

## [#206] Perbaiki: Simpan di mode galeri halaman 2+ menutup form & reload — 2026-07-13

- **Bug:** di tampilan **mode galeri** inventarisasi aset, menekan
  "Simpan" pada baris di **halaman kedua dan seterusnya** (hasil infinite
  scroll) membuat panel edit menutup sendiri dan daftar seolah dimuat
  ulang — padahal di halaman pertama Simpan lancar melanjutkan ke aset
  berikutnya. Terjadi di tablet/HP dan layout kartu.
- **Sebab:** galeri/kartu merender `mobileAssets` (superset infinite
  scroll), tetapi gerbang tombol Simpan + navigasi (`editAssetIndex`,
  `totalAssetsInView`, `handleSaveAndNavigate`) membaca `assets` yang
  **beku di halaman 1**. Baris halaman 2+ tak ditemukan di `assets`
  (indeks −1) → gerbang gagal → Simpan jatuh ke jalur tutup-form yang
  memicu `refreshData()` sehingga daftar kolaps ke halaman 1.
- **Perbaikan:** samakan indeks, jumlah, dan navigasi form agar semua
  membaca `mobileAssets` (di tabel ≥lg isinya sama dengan halaman aktif,
  jadi perilaku desktop tak berubah). Kini Simpan di galeri halaman 2+
  lanjut ke aset berikutnya tanpa menutup form / reload daftar.

## [#205] Ekspor CSV register polis asuransi BMN (Pengamanan) — 2026-07-13

- **Ekspor CSV** register polis asuransi BMN (`GET
  /pengamanan/polis/export`), melengkapi pola ekspor register. Kolom:
  identitas aset, nomor polis, penanggung, kategori objek & sumber dana
  premi (label terbaca), nilai pertanggungan & premi (rupiah bulat),
  masa berlaku (mulai–berakhir), status masa berlaku + sisa hari
  (dihitung via `info_polis`), keterangan, pembuat. Helper murni
  `baris_csv_polis` (tanpa Mongo, teruji unit) + tombol unduh CSV di
  panel polis (muncul saat ada data). Bersifat baca-saja. Unit test +1
  → 271 passed.

## [#204] Ekspor CSV register koreksi nilai (Penilaian) — 2026-07-13

- **Ekspor CSV** register koreksi nilai/hasil penilaian (`GET
  /penilaian/koreksi/export`), melengkapi pola ekspor register yang sudah
  ada (pemanfaatan/pemeliharaan/pemindahtanganan/pemusnahan/pengadaan/
  penganggaran/penghapusan). Kolom: identitas aset, jenis & dokumen
  (label terbaca), nomor & tanggal dokumen, nilai lama→baru + selisih
  (rupiah bulat, konsisten), dampak masa manfaat, penilai, status SAKTI,
  catatan, pembuat. Helper murni `baris_csv_koreksi` (tanpa Mongo, teruji
  unit) + tombol unduh CSV di panel koreksi (muncul saat ada data).
  Unit test +1 → 270 passed.

## [#203] Riwayat nilai per aset (Penilaian) — 2026-07-13

- **Riwayat Nilai per Aset** (read-only) di halaman Penilaian: cari satu
  aset lalu lihat jejak kronologis nilainya — **perolehan** (dari
  `purchase_date` + `purchase_price`) → tiap **koreksi/revaluasi** (LHIP/
  BA/Laporan Penilaian, urut tanggal dokumen) → **nilai terkini**. Nilai
  terkini mengikuti koreksi non-informasional terakhir; koreksi
  "penilaian tujuan tertentu" ditandai **informasional** dan tidak
  mengubah nilai buku. Endpoint `GET /penilaian/riwayat-nilai/{asset_id}`
  + helper murni `susun_riwayat_nilai` (tanpa Mongo, teruji unit). Tidak
  ada mutasi data — hanya menyusun ulang catatan yang sudah ada. Unit
  test +1 → 269 passed. Melengkapi butir "menyusul" pada modul Penilaian.

## [#202] Filter rentang waktu pakai tanggal beli (+ peta) — 2026-07-12

- **Filter rentang tanggal** di daftar inventarisasi aset kini menyaring
  berdasarkan **tanggal beli** (`purchase_date`), bukan tanggal input
  (`created_at`). Karena builder query dipakai bersama `/assets` + ekspor
  geo, dan peta memakai `buildParams` + `clientFilter` yang sama,
  **peta ikut tersaring**. Param → `beli_dari/beli_sampai` (batas atas
  inklusif); label UI "Tanggal Input" → "Tanggal Beli"; aset tanpa
  tanggal beli keluar saat rentang diisi; indeks `purchase_date` ditambah.

## [#201] Saran jenjang persetujuan Pemindahtanganan — 2026-07-12

- **Saran jenjang persetujuan (indikatif)** dari jenis BMN + nilai wajar:
  Pengelola Barang (≤Rp10 M) / Presiden (>10–100 M) / DPR (>100 M) untuk
  selain tanah/bangunan; tanah/bangunan umum → DPR, terkecuali Ps. 55(2)
  ikut nilai; PMPP lantai Presiden; hibah ≤Rp100 jt catatan Pengguna
  Barang (UU 1/2004 Ps. 45–46 + PP 27/2014). **Tidak memblok** — panduan
  saja. Pustaka §7 + verifikasi §14 no. 25. Unit test +1 → 251 passed.

## [#200] Konsolidasi dokumentasi #199 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + masterplan + pustaka §13
  baris Pengadaan (✅ tautan paket → Penganggaran #199; butir "menyusul"
  tautan paket ke register penganggaran tuntas).

## [#199] Tautan Pengadaan → usulan Penganggaran — 2026-07-12

- **Jembatan #117 ↔ #115**: register perolehan Pengadaan dapat ditautkan
  ke usulan Penganggaran (field `penganggaran_id` + snapshot uraian/nomor
  DIPA/tahun). Endpoint `POST /pengadaan/{id}/penganggaran` (tautkan/lepas);
  dropdown di form + baris info di register; kolom penganggaran + DIPA di
  CSV. Referensi lunak (tak memvalidasi nilai). Unit test +1 → 250 passed.

## [#198] Konsolidasi dokumentasi #197 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5–6 + masterplan + pustaka
  §13 baris Penghapusan (✅ Jejak Aset Terhapus #197 — butir "menyusul"
  arsip aset terhapus tuntas).

## [#197] Jejak Aset Terhapus (arsip read-only) — 2026-07-12

- **Aset yang dihapus permanen kini tetap tertelusur**: endpoint
  read-only `GET /audit-logs/aset-terhapus` (dari log audit; kode/NUP/
  nama/nilai perolehan/oleh/waktu, rekap jumlah + total nilai) + seksi
  "Jejak Aset Terhapus" di halaman Penghapusan. Tidak mengubah mekanisme
  hapus/offline-sync. Unit test +1 → 249 passed. Butir "menyusul"
  Penghapusan (arsip aset terhapus) tuntas.

## [#196] Peta: zoom maksimal dinaikkan ke 22 — 2026-07-12

- **Peta full-view** kini bisa diperbesar hingga zoom 22 (dari 19):
  `maxNativeZoom: 19` + `maxZoom: 22` pada TileLayer & objek peta →
  Leaflet memperbesar ubin OSM z19 pada z20–22, sehingga pin aset yang
  berdekatan dapat dipisahkan lebih presisi saat diperbesar. Auto-fit
  dibatasi z19 agar tampilan awal tetap tajam.

## [#195] Konsolidasi dokumentasi #194 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + masterplan + pustaka §13
  baris Penggunaan (✅ alur pengajuan PSP #194 — daftar "menyusul"
  Penggunaan tuntas).

## [#194] Alur pengajuan PSP berstatus — 2026-07-12

- **Alur pengajuan PSP** (butir "menyusul" terakhir Penggunaan): usulan
  dapat dibuat sebagai draf tanpa SK → diajukan → ditetapkan (nomor/
  tanggal SK wajib saat itu) / ditolak / dikembalikan (catatan wajib).
  Kompatibel mundur (SK lama tanpa status = ditetapkan); cakupan aset
  ter-PSP & BAST PDF hanya untuk yang ditetapkan; anti-balapan +
  riwayat. UI: checkbox draf + badge status + tombol transisi. Unit
  test +2 → 248 passed. **Daftar "menyusul" Penggunaan tuntas.**

## [#193] Konsolidasi dokumentasi #192 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + masterplan + pustaka §13
  baris Penggunaan (✅ BAST PSP PDF #192; sisa "menyusul" = alur
  pengajuan PSP berstatus).

## [#192] BAST penetapan status penggunaan PDF — 2026-07-12

- **BAST digital penetapan PSP**: PDF siap tanda tangan per SK dari
  register SK PSP (#129) — kop surat, narasi dasar SK (PMK 40/2024),
  tabel aset, tanda tangan pihak menyerahkan/menerima + KPB (pola BA
  pemusnahan #119; data murni register). Tombol unduh per SK di halaman
  Penggunaan; smoke test PDF lolos. Sisa "menyusul" Penggunaan: alur
  pengajuan PSP berstatus.

## [#191] Konsolidasi dokumentasi #190 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 butir Pemanfaatan
  (+ atribut fasilitas transaksi #190; daftar "menyusul" tuntas).

## [#190] Koreksi PMK 18/2024 + atribut fasilitas transaksi — 2026-07-12

- **Koreksi regulasi (riset)**: PMK 18/2024 = "Tata Cara Pemberian
  Fasilitas Penyiapan & Pelaksanaan Transaksi Pemanfaatan BMN"
  (pendampingan DJPPR, analog PDF KPBU) — BUKAN bentuk pemanfaatan ke-7;
  khusus IKN berlaku PMK 139/PMK.08/2022 (PT PII). Salah kaprah "bentuk
  PDF" dikoreksi di pustaka (sub-bab §6.a baru + butir verifikasi 24),
  masterplan, dan bmnModules.
- **Fitur**: atribut fasilitas transaksi opsional pada register
  perjanjian (dasar/nomor penetapan/pelaksana) — hanya KSP/BGS-BSG,
  nomor penetapan wajib bila ber-fasilitas; kolom CSV + blok form baru.
  Daftar "menyusul" Pemanfaatan tuntas. Unit test +1 → 246 passed.

## [#189] Konsolidasi dokumentasi #188 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 + tabel modul & roadmap
  masterplan (Pemanfaatan "Lengkap tahap awal") + pustaka §13 baris
  Pemanfaatan (✅ lampiran wasdal #188; "menyusul" tinggal PDF PMK
  18/2024).

## [#188] Lampiran wasdal per perjanjian pemanfaatan — 2026-07-12

- **Arsip lampiran wasdal terpisah** per perjanjian pemanfaatan: laporan
  monitoring/BA peninjauan lapangan (5 objek pemantauan KPB, pustaka §8)
  di array `lampiran_wasdal` + trio endpoint GridFS `/wasdal` — terpisah
  dari dokumen perjanjian (#131). Logika lampiran direfaktor jadi helper
  bersama; kolom `jumlah_lampiran_wasdal` di CSV; tombol "Wasdal" +
  dialog dua jenis di halaman Pemanfaatan. Butir "menyusul" Pemanfaatan
  tinggal PDF PMK 18/2024.

## [#187] Konsolidasi dokumentasi #186 + perapian status modul — 2026-07-12

- **Dokumentasi + data statis modul**: README Progres Fase 4 & masterplan
  (Penganggaran "Lengkap tahap awal", daftar "menyusul" tuntas #186);
  perapian baris pustaka §13 yang basi (Pemeliharaan #90/#91/#167,
  Pemanfaatan #121/#131/#158, Pemusnahan #119/#120/#132, Penghapusan
  #106/#134/#159); bmnModules: butir tiket proses 4 rezim (#181/#183)
  masuk checklist Penggunaan, blok Penilaian dimutakhirkan (dasar hukum
  PMK 99/2024 + Perpres 75/2017 + PMK 118/2017 jo. perubahannya).

## [#186] Sanding realisasi per triwulan (Penganggaran) — 2026-07-12

- **Sanding realisasi per triwulan per tahun anggaran**: realisasi
  dipetakan ke TW I–IV dari tanggal riwayat "terealisasi"; kumulatif +
  serapan kumulatif dibanding total DIPA. Usulan tanpa tanggal riwayat
  tetap masuk total (tidak hilang). Butir "menyusul" terakhir modul
  Penganggaran tuntas.
- Unit test +1 → 245 passed; seksi tabel baru di halaman Penganggaran.

## [#185] Konsolidasi dokumentasi #184 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 5 (Penilaian + koreksi nilai
  #184) + tabel modul & roadmap masterplan — dasar hukum dimutakhirkan:
  revaluasi Perpres 75/2017 + PMK 118/2017 jo. perubahannya, penilaian
  PMK 99/2024, asuransi PMK 43/2025; baris Pengamanan & Penggunaan
  menjadi "Lengkap tahap awal".

## [#184] Register koreksi nilai & hasil penilaian — 2026-07-12

- **Register koreksi nilai per aset** di modul Penilaian: catat hasil
  revaluasi (LHIP), koreksi inventarisasi, koreksi temuan/putusan,
  koreksi pencatatan, dan penilaian tujuan tertentu (informasional,
  tidak mengubah nilai buku) — nilai lama → baru, selisih otomatis,
  dampak masa manfaat (tetap / masa manfaat baru), dan status
  pencatatan SAKTI (tandai "tercatat di SAKTI", anti-race).
- Dasar riset: Perpres 75/2017 + PMK 118/2017 jo. 57/2018 jo. 107/2019
  (revaluasi), PMK 99 Tahun 2024 (penilaian) — pustaka §13 baris
  Penilaian dimutakhirkan + butir verifikasi 23 di §14.
- Unit test +2 → 244 passed; UI seksi baru + dialog pencarian aset di
  halaman Penilaian; indeks `penilaian_koreksi`.

## [#183] Tiket proses: dioperasikan pihak lain & penggunaan bersama — 2026-07-12

- **Dua rezim PMK 40/2024 tersisa** pada register tiket proses:
  dioperasikan pihak lain (penetapan Pengelola, pihak non-K/L) dan
  penggunaan bersama (Eminen + Kolaborator) — pipeline berjangka tanpa
  jalur pintas ≤6 bulan; pengingat perpanjangan ≤90 hari untuk semua
  jenis berjangka. Daftar "menyusul" Penggunaan tuntas (4 rezim).
- Unit test +2 → 242 passed; UI opsi jenis baru + dokumentasi
  (README/masterplan/pustaka/bmnModules) dalam PR yang sama.

## [#182] Konsolidasi dokumentasi #181 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Penggunaan (dimutakhirkan menyeluruh) + butir
  verifikasi 22 di §14 (tenggat/jangka waktu PMK 40/2024).

## [#181] Tiket proses alih status & penggunaan sementara — 2026-07-12

- **Tiket proses PMK 40/2024** di modul Penggunaan: alih status
  (draf → diajukan → disetujui → BAST → dihapus & dibukukan; tenggat
  1/2/1 bulan sebagai pengingat, [perlu verifikasi]) dan penggunaan
  sementara (5/2 tahun; ≤6 bulan boleh langsung berjalan tanpa
  persetujuan Pengelola; pengingat perpanjangan ≤90 hari).
- Endpoint GET/POST/status (dokumen tahap otomatis terpetakan)/DELETE +
  indeks; seksi UI + dialog buka tiket multi-aset di `PenggunaanPage`.
- Unit test +3 → 240 passed; checklist bmnModules.

## [#180] Konsolidasi dokumentasi #179 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + roadmap masterplan +
  pustaka §13 baris Perencanaan (usulan RKBMN per unit #179; menyusul
  tinggal sanding SBSK menunggu lampiran PMK 138/2024).

## [#179] Usulan RKBMN per unit berstatus — 2026-07-12

- **Register usulan RKBMN per unit** (PMK 153/2021 + KMK 128/KM.6/2022):
  pipeline draft → diajukan → disetujui PB → dikirim Pengelola (SIMAN)
  → disetujui/ditolak penelaahan, jalur dikembalikan wajib catatan;
  penanda SPTJM + reviu APIP; aset opsional ber-snapshot; anti-race.
- Temuan riset: PMK 138/2024 (SBSK) mencabut PMK 172/2020 — angka
  lampiran belum terverifikasi, kalkulator SBSK ditunda (pustaka §14
  butir 21).
- UI: seksi usulan + dialog buat usulan di `PerencanaanPage` (prop
  `user`); checklist bmnModules. Unit test +3 → 237 passed.

## [#178] Konsolidasi dokumentasi #177 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (polis asuransi #177 — seluruh item
  "menyusul" modul Pengamanan tuntas).

## [#177] Register polis Asuransi BMN (PMK 43/2025) — 2026-07-12

- **Subbab pustaka §11.5 Asuransi BMN** (riset dulu): PMK 97/2019
  ternyata sudah dicabut **PMK 43 Tahun 2025** (skema premi baru via
  Pooling Fund Bencana) — modul merujuk PMK 43/2025; butir verifikasi
  20 di §14.
- **Register polis** per aset di modul Pengamanan: nomor polis,
  penanggung (default Konsorsium Asuransi BMN), kategori objek
  Program/Nonprogram, nilai pertanggungan, premi + sumber dana
  (DIPA/PFB), masa berlaku dengan status akan datang/aktif/
  **segera berakhir ≤90 hari**/berakhir + ringkasan.
- UI seksi polis + dialog ber-pencarian aset; item "menyusul"
  Pengamanan kini TUNTAS semua. Unit test +2 → 234 passed.

## [#176] Konsolidasi dokumentasi #175 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (checklist per aset #175; menyusul
  tinggal asuransi BMN).

## [#175] Checklist pengamanan per aset per jenis — 2026-07-12

- **Checklist pengamanan** per aset (pustaka §11.2): butir fisik/
  administrasi/hukum per jenis objek (tanah/gedung/kendaraan/lainnya),
  skor terpenuhi + tanggal cek + petugas, upsert satu checklist per
  aset (`GET/POST /pengamanan/checklist`, DELETE admin).
- UI: seksi checklist dengan badge skor berwarna + tombol Perbarui
  pra-isi + dialog isi ber-pencarian aset (tebakan jenis dari golongan
  kode aset). Alat bantu internal — bukan bukti hukum.
- Unit test +2 → 232 passed; indeks `pengamanan_checklist`.

## [#174] Konsolidasi dokumentasi #173 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (status sertipikasi K1–K4 #173).

## [#173] Status sertipikasi tanah K1–K4 — 2026-07-12

- **Status sertipikasi** pada arsip dokumen jenis sertipikat (pustaka
  §11.4): belum/proses/K1–K4/SHP terbit + rekap per kategori di
  `GET /pengamanan/dokumen`; select hanya muncul untuk jenis sertipikat
  + badge ungu kategori di daftar. Unit test +2 → 230 passed.

## [#172] Konsolidasi dokumentasi #171 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan +
  pustaka §13 baris Pengamanan (arsip dokumen kepemilikan #171).

## [#171] Arsip dokumen kepemilikan per aset — 2026-07-12

- **Arsip dokumen kepemilikan** di modul Pengamanan (pustaka §11.3,
  PP 27/2014 Ps. 43 + PMK 218/2015): sertipikat/BPKB/STNK/IMB-PBG per
  aset, atas nama, lokasi penyimpanan (Pengelola vs Pengguna Barang),
  tanggal berlaku opsional dengan penanda kedaluwarsa, lampiran scan
  GridFS pola baku (unggah/unduh/hapus admin).
- UI: seksi arsip + dialog catat dokumen ber-pencarian aset + dialog
  lampiran di `PengamananPage`; lokasi simpan otomatis mengikuti jenis.
- Unit test +2 → 228 passed; indeks `pengamanan_dokumen`.

## [#170] Konsolidasi dokumentasi #169 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan
  (pengamanan: register BMN bermasalah #169, pustaka §11).

## [#169] Register BMN bermasalah + bab pustaka Pengamanan — 2026-07-12

- **Bab pustaka baru §11 "Pengamanan BMN"** (riset dulu): induk regulasi
  PP 27/2014 Ps. 42–43 jo. PP 28/2020 + UU 1/2004 Ps. 49 + PMK 218/2015
  (koreksi: PMK 244/2012 = Wasdal, sudah dicabut PMK 207/2021); bentuk
  pengamanan per jenis BMN; alur kasus; sertipikasi K1–K4; bab lama
  §11–§14 bergeser jadi §12–§15.
- **Register BMN bermasalah/sengketa** di modul Pengamanan: kategori
  (dikuasai pihak lain / sertipikat pihak lain / berperkara), pipeline
  identifikasi → mediasi → blokir → litigasi → selesai dengan riwayat +
  anti-race, satu kasus aktif per aset, hapus admin — bahan laporan
  wasdal/CaLBMN.
- UI: seksi register + dialog buka kasus ber-pencarian aset di
  `PengamananPage` (prop `user` dari App). Unit test +3 → 226 passed.

## [#168] Konsolidasi dokumentasi #167 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 3 + roadmap masterplan
  (pemeliharaan: ekspor CSV riwayat #167).

## [#167] Ekspor CSV riwayat pemeliharaan — 2026-07-12

- **Ekspor CSV** riwayat pemeliharaan (`GET /pemeliharaan/export`) —
  aset, tanggal, jenis DJKN, biaya, kondisi sebelum/sesudah, penanda
  telaah kapitalisasi PMK 181, pelaksana/bukti — melanjutkan pola
  #158–#163.
- Tombol **CSV** di header `PemeliharaanPage`; checklist bmnModules
  diperbarui.

## [#166] Konsolidasi dokumentasi #165 — 2026-07-12

- **Dokumentasi saja**: README Progres Fase 4 + roadmap masterplan +
  pustaka §12 baris Penganggaran (kalender tenggat #165; "menyusul"
  tinggal sanding per triwulan).

## [#165] Kalender penganggaran konfigurabel — 2026-07-12

- **Kalender penganggaran** (pustaka §9.4): register tahapan ber-tenggat
  yang dikelola admin (`GET/POST /penganggaran/kalender`, DELETE per
  tahapan) — tanggal konfigurabel karena tenggat internal tiap K/L
  berbeda; pengingat lewat tenggat (merah) dan ≤30 hari (kuning) di
  `PenganggaranPage` memakai pola tenggat pelaporan #150.
- Utils + 3 unit test baru (validasi tahapan, info tenggat, rekap);
  indeks `penganggaran_kalender`; checklist bmnModules — item "menyusul"
  terakhir modul Penganggaran tuntas.

## [#164] Konsolidasi dokumentasi #163 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 (penganggaran:
  penanda ekspor CSV #163) + roadmap masterplan fase 4.

## [#163] Ekspor CSV register penganggaran — 2026-07-12

- **Ekspor CSV** register usulan penganggaran (`GET /penganggaran/export`)
  — tahun, jenis, akun BAS berlabel, uraian, status, nilai per tahap
  (usulan/disetujui/DIPA/realisasi), nomor DIPA, jumlah aset tertaut,
  sumber, pembuat — menutup gelombang ekspor CSV register pendamping
  (#158–#161).
- Tombol **CSV** di header `PenganggaranPage` (`downloadFileWithProgress`,
  `utf-8-sig`); checklist `bmnModules.js` penganggaran diperbarui.

## [#162] Konsolidasi dokumentasi #161 — 2026-07-12

- **Dokumentasi saja**: README blok Progres (pemusnahan + pengadaan:
  penanda ekspor CSV #161) + roadmap masterplan fase 4 & 6.

## [#161] Ekspor CSV register pemusnahan & pengadaan — 2026-07-12

- **Ekspor CSV** dua register terakhir gelombang #158–#159: pemusnahan
  (`GET /pemusnahan/export` — nomor/tanggal BA, cara, persetujuan, jumlah
  aset, nilai perolehan, lampiran) dan pengadaan (`GET /pengadaan/export`
  — jenis, pihak, kontrak/BAST, jumlah barang, nilai, dokumen kurang,
  lampiran).
- Tombol **CSV** di header `PemusnahanPage` & `PengadaanPage`
  (`downloadFileWithProgress`, `utf-8-sig` agar aman dibuka Excel); rute
  literal `.../export` sebelum catch-all `/{id}`.
- Checklist `bmnModules.js` pemusnahan & pengadaan diberi penanda
  ekspor CSV ✅.

## [#160] Konsolidasi dokumentasi #158–#159 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + roadmap
  masterplan (ekspor CSV register hilir #158–#159).

## [#159] Ekspor CSV register penghapusan & pemindahtanganan — 2026-07-12

- **Ekspor CSV** dua register hilir lagi (pola #158): usulan penghapusan
  (jalur + status + SK + jumlah lampiran) dan pemindahtanganan (bentuk +
  status + dokumen per tahap + ringkas aset); tombol CSV di kedua
  halaman.

## [#158] Ekspor CSV register pemanfaatan — 2026-07-12

- **Ekspor CSV** register perjanjian (kolom lengkap + status turunan +
  rekap kontribusi tercatat + jumlah lampiran, UTF-8 BOM); tombol CSV
  di header halaman Pemanfaatan.

## [#157] Konsolidasi dokumentasi #156 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + roadmap
  masterplan fase 6 (lampiran tiket insidentil #156).

## [#156] Arsip lampiran tiket insidentil wasdal — 2026-07-12

- **Lampiran per tiket insidentil** (scan BA bertanda tangan + foto
  temuan, pola lampiran baku): tombol klip + dialog di seksi Pemantauan
  Insidentil halaman Wasdal; hapus tiket membersihkan berkasnya.

## [#155] Konsolidasi dokumentasi #154 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (pindah gudang ✅; fase 2 tersisa hanya KIB).

## [#154] Pindah gudang persediaan ber-jurnal — 2026-07-12

- **Pindah gudang per barang**: lokasi berpindah anti-balapan, stok &
  layer FIFO tak tersentuh, jurnal arah "mutasi" mencatat asal → tujuan
  (+kompensasi bila jurnal gagal); `mutasi_periode` kini mengabaikan
  arah mutasi agar saldo laporan tak terganggu. Dialog + render riwayat
  khusus. Suite 220.

## [#153] Konsolidasi dokumentasi #152 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (filter gudang ✅; tersisa KIB + transfer stok antar gudang).

## [#152] Filter Lokasi/Gudang persediaan — 2026-07-12

- **Dimensi gudang aktif**: daftar gudang unik + filter gudang di daftar
  master (paging benar di query) + **laporan posisi per gudang** dengan
  subjudul; dropdown filter + unduhan ikut filter aktif. Smoke pypdfium2
  dua skenario lulus.

## [#151] Konsolidasi dokumentasi #150 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  (implikasi Pelaporan §2.3 tuntas; tersisa KIB/gudang persediaan).

## [#150] Tenggat pelaporan konfigurabel per periode — 2026-07-12

- **Tenggat penyampaian per periode** (surat DJKN/K/L): atur/ubah/hapus
  oleh admin saat periode terbuka (tercatat riwayat); pengingat sisa
  hari + badge lewat tenggat di kartu Periode Pelaporan. Daftar
  "Implikasi AMAN" Pelaporan §2.3 tuntas. Suite 218.

## [#149] Konsolidasi dokumentasi #148 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (periode ber-kunci ✅; tersisa KIB/gudang persediaan).

## [#148] Periode pelaporan ber-kunci + penanda FINAL — 2026-07-12

- **Periode pelaporan** (Semester I/II/Tahunan) berstatus terbuka →
  terkunci (admin, anti-balapan; buka kembali wajib beralasan &
  tercatat); saat terkunci, **LBKP & CaLBMN berpenanda FINAL** di
  subjudul. Kartu kelola periode di hub Pelaporan. Suite 216; smoke
  pypdfium2 tiga skenario lulus.

## [#147] Konsolidasi dokumentasi #146 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (LKB ✅; tersisa KIB/gudang/periode ber-kunci).

## [#146] LKB — Laporan Kondisi Barang — 2026-07-12

- **LKB per NUP + ringkasan B/RR/RB per golongan** (format LKBT-PKPB1,
  riset → pustaka §2.3b): kondisi kosong tampil "(belum dicatat)",
  kolom satuan tidak difabrikasi; tombol di hub Pelaporan. Suite 211;
  smoke pypdfium2 lulus.

## [#145] Konsolidasi dokumentasi #144 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 + roadmap masterplan
  fase 2 (CaLBMN ✅; tersisa KIB/gudang/LKB/periode ber-kunci).

## [#144] CaLBMN pra-isi bab I–V per periode — 2026-07-12

- **CaLBMN pra-isi** (struktur lampiran PMK 181/2016, riset → pustaka
  §2.3a): bab I–V terisi dari data nyata — ringkasan mutasi LBKP per
  golongan, intra/ekstra, persediaan FIFO, cakupan PSP, PNBP kontribusi
  ber-NTPN periode berjalan, pemindahtanganan/penghapusan/idle/sengketa;
  dropdown periode di hub Pelaporan. Posisi: bahan penyusunan — dokumen
  resmi via SAKTI; smoke pypdfium2 lulus.

## [#143] Konsolidasi dokumentasi #142 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan fase 6 (pemantauan insidentil wasdal #142).

## [#142] Pemantauan insidentil wasdal (10+5 hari kerja) + PDF BA — 2026-07-12

- **Pemantauan insidentil** (PMK 207/2021): pemicu masyarakat/media/
  audit, alur berjalan → BA terbit → dilaporkan dengan tenggat
  pelaksanaan 10 hari kerja + lapor 5 hari kerja sejak BA, peringatan
  lewat tenggat; **PDF Berita Acara siap tanda tangan** (placeholder
  bila BA belum terbit, smoke pypdfium2). Suite 208.

## [#141] Konsolidasi dokumentasi #140 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan fase 6 (register penertiban wasdal #140).

## [#140] Register penertiban wasdal (tenggat 15 hari kerja) — 2026-07-12

- **Tiket penertiban KPB** (PMK 207/2021): sumber pemantauan/permintaan
  Pengelola/temuan APIP-BPK, tenggat otomatis 15 hari kerja
  (Senin–Jumat), peringatan lewat tenggat, selesai ber-tindak-lanjut
  (anti-balapan); seksi baru + 2 dialog di halaman Wasdal. Suite 204.

## [#139] Konsolidasi dokumentasi #137–#138 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 3 (arsip SK PSP #137) &
  Fase 5–6 (arsip lampiran pemindahtanganan #138) + penanda roadmap
  masterplan fase 3 dan 6.

## [#138] Arsip lampiran register pemindahtanganan — 2026-07-12

- **Lampiran per usulan** (PMK 111/2016 jo. 165/2021): scan persetujuan/
  risalah lelang/BAST/naskah hibah/bukti setor PNBP (pola lampiran baku);
  tombol klip + dialog di halaman Pemindahtanganan. Seluruh register
  hilir siklus BMN kini punya arsip berkas konsisten.

## [#137] Arsip scan SK PSP (lampiran register penetapan) — 2026-07-12

- **Lampiran per SK PSP** (PMK 40/2024): scan SK penetapan + dokumen
  pendukung (pola #131/#132/#134/#135 — GridFS, tautan ber-token,
  hapus admin, bersih saat SK dihapus); tombol klip + dialog di bagian
  PSP halaman Penggunaan.

## [#136] Konsolidasi dokumentasi #134–#135 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 (arsip berkas
  perolehan #135) & Fase 5–6 (arsip SK penghapusan #134) + penanda
  roadmap masterplan fase 4 dan 6.

## [#135] Lampiran berkas register perolehan — 2026-07-12

- **Arsip berkas per perolehan** (melengkapi checklist #117): scan
  kontrak/BAPHP/BAST/kuitansi/SP2D (pola lampiran baku); tombol klip +
  dialog di halaman Pengadaan. Semua register hilir kini punya arsip
  lampiran konsisten.

## [#134] Arsip SK penghapusan (lampiran tiket usulan) — 2026-07-12

- **Lampiran per tiket usulan** (PMK 83/2016): scan SK penghapusan +
  dokumen pendukung (pola #131/#132 — GridFS, tautan ber-token, hapus
  admin, bersih saat tiket dihapus); tombol klip + dialog di halaman
  Penghapusan.

## [#133] Konsolidasi dokumentasi #131–#132 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 5–6 + penanda roadmap
  masterplan diperluas dengan arsip lampiran (#131–#132).

## [#132] Lampiran bukti pelaksanaan pemusnahan — 2026-07-12

- **Lampiran per BA** (PMK 83/2016): foto pelaksanaan + scan BA
  bertanda tangan (pola #131 — GridFS, tautan ber-token, hapus admin,
  bersih saat BA dihapus); dialog Lampiran di halaman Pemusnahan.

## [#131] Arsip scan dokumen pemanfaatan — 2026-07-12

- **Lampiran per perjanjian** (pustaka §6): unggah scan persetujuan/
  perjanjian/bukti setor (PDF/gambar, GridFS, maks 10×10MB), buka via
  tautan ber-token, hapus admin; hapus register ikut membersihkan
  berkasnya. Dialog Lampiran di halaman Pemanfaatan.

## [#130] Konsolidasi dokumentasi #128–#129 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 2 & 3 + masterplan
  (baris Penggunaan & roadmap Fase 3) diperluas dengan #128–#129.

## [#129] Register SK penetapan penggunaan (PSP) — 2026-07-12

- **Register SK PSP multi-aset** (PMK 40/2024): 5 jenis penetapan,
  snapshot aset per SK, rekap per jenis + cakupan aset unik ter-PSP vs
  total; seksi baru + dialog catat di halaman Penggunaan. 2 unit test
  (suite 199).

## [#128] Pengingat opname semesteran persediaan — 2026-07-12

- **Banner pengingat opname fisik** (pustaka §3.3): status per semester
  berjalan dari transaksi opname terakhir; tampil di halaman Persediaan
  bila semester ini belum diopname. 3 unit test (suite 197).

## [#127] Konsolidasi dokumentasi Penggunaan #125–#126 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 3 + masterplan (baris
  Peta Siklus Penggunaan & roadmap Fase 3) diperluas dengan #125–#126.

## [#126] Daftar pantau BMN idle + tiket klarifikasi — 2026-07-12

- **BMN idle (PMK 120/2024)**: kandidat otomatis (Nonaktif / tanpa
  pengguna; Tidak Ditemukan dikecualikan), tiket klarifikasi →
  digunakan kembali / usul serah → diserahkan (dokumen wajib per tahap,
  anti-balapan, riwayat); seksi baru di halaman Penggunaan. 3 unit test
  (suite 194).

## [#125] Daftar Barang yang Digunakan per pemegang (PDF) — 2026-07-12

- **Lampiran BAST penggunaan** (PMK 40/2024): PDF per pemegang berisi
  identitas + tabel aset yang dipegang + penanda BAST + tanda tangan
  pemegang/KPB; unduh dari dialog aset pemegang. Smoke FakeDB + PNG
  lulus. PSP/alih status/BMN idle menyusul.

## [#124] Konsolidasi dokumentasi fitur #119–#123 — 2026-07-12

- **Dokumentasi saja**: README blok Progres Fase 4 & 5–6 + penanda
  roadmap masterplan diperluas dengan lima fitur pendalaman (#119–#123).

## [#123] Sanding per akun BAS di register penganggaran — 2026-07-12

- **Sanding rencana vs realisasi per akun** (pustaka §9): tabel per akun
  53x/523 dengan nilai usulan/disetujui/DIPA/realisasi + serapan persen;
  usulan tanpa akun digabung baris "lainnya". 1 unit test (suite 191).

## [#122] Laporan Hasil Pemantauan Wasdal PDF — 2026-07-12

- **Laporan pra-isi wasdal semesteran** (PMK 207/2021): rekap 5 objek
  pemantauan ber-total + rincian temuan per objek (maks 30/objek) + blok
  tanda tangan; unduh dari header dasbor Wasdal. Kanal resmi tetap Modul
  Wasdal SIMAN v2. Smoke FakeDB + PNG lulus.

## [#121] Kontribusi tahunan pemanfaatan + pengingat tunggakan — 2026-07-12

- **Kewajiban PNBP tahunan** (KSP/BGS/KSPI, pustaka §6): field kontribusi
  tahunan pada perjanjian, pencatatan pembayaran per tahun ber-NTPN
  (duplikat tahun ditolak), pengingat tunggakan otomatis dari tahun
  mulai s.d. tahun berjalan/berakhir. 2 unit test (suite 190).

## [#120] Usulan penghapusan otomatis dari BA Pemusnahan — 2026-07-12

- **Tindak lanjut PMK 83/2016 satu klik**: tombol Usulkan Hapus per BA
  membuat tiket usulan penghapusan tiap aset (keterangan merujuk nomor
  BA + persetujuan); aset ber-usulan aktif dilewati; lencana ✓ saat
  semua tercakup. 1 unit test baru (suite 188).

## [#119] PDF Berita Acara Pemusnahan — 2026-07-12

- **PDF BA Pemusnahan siap tanda tangan** (PMK 83/2016) dari register
  #110: kop surat, nomor BA + persetujuan, cara pemusnahan, tabel aset
  ber-total, blok tanda tangan pelaksana/saksi/KPB; tombol unduh per BA.
  Smoke FakeDB + PNG lulus. Foto bukti pelaksanaan menyusul.

## [#118] Konsolidasi dokumentasi Pengadaan — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Pengadaan →
  Sebagian, roadmap Fase 4 + #117), README (intro **SEMUA 14 modul
  siklus Sebagian Aktif** — tersisa sub-modul Pembukuan/KIB — + blok
  Progres Fase 4), dan pustaka §12 (baris implikasi Pengadaan).

## [#117] Pengadaan tahap awal: register perolehan per dokumen — 2026-07-12

- **Register perolehan** (bab pustaka §10, Perpres 16/2018 jo. 46/2025):
  satu entri per BAST/kontrak (jenis 101/102/103/105), checklist dokumen
  sumber per jenis (penangkal "BAST tercecer"), tautan barang → aset
  master + penanda ekstrakomptabel ambang PMK 181. Kartu naik Sebagian —
  Segera Hadir tersisa Pembukuan/KIB. 4 unit test (suite 187).

## [#116] Konsolidasi dokumentasi Penganggaran — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Penganggaran →
  Sebagian + PMK 62/2023, roadmap Fase 4 + #115), README (intro 13 modul
  Sebagian Aktif — sisa Pengadaan & Pembukuan/KIB — + blok Progres
  Fase 4), dan pustaka §11 (baris implikasi Penganggaran).

## [#115] Penganggaran tahap awal: register usulan berstatus — 2026-07-12

- **Register usulan penganggaran** (bab pustaka §9, PMK 62/2023 +
  PMK 153/2021): pipeline diusulkan → disetujui telaah → masuk DIPA →
  terealisasi dengan nilai wajib per tahap, akun BAS 53x/523 sesuai
  jenis, tautan aset opsional, rekap serapan. Kartu naik Sebagian —
  tinggal Pengadaan yang Segera Hadir. 4 unit test (suite 183).

## [#114] Konsolidasi dokumentasi Wasdal — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Wasdal → Sebagian,
  penanda roadmap Fase 6 + #113), README (intro 12 modul Sebagian Aktif +
  blok Progres Fase 5–6), dan pustaka §10 (baris implikasi Wasdal).

## [#113] Wasdal tahap awal: dasbor pemantauan 5 objek — 2026-07-12

- **Dasbor pemantauan Wasdal KPB** (bab pustaka §8, PMK 207/2021): mesin
  aturan membaca register yang ada → 12 jenis temuan per 5 objek
  pemantauan (BAST kosong, perjanjian berakhir/dokumen kurang, usulan
  hapus berlarut, kandidat belum diusulkan, tenggat lelang, data belum
  lengkap, sengketa, rusak tanpa pemeliharaan). Kartu naik Sebagian;
  8 unit test (suite 179). Penertiban & laporan formulir PMK menyusul.

## [#112] Konsolidasi dokumentasi Fase 6 — 2026-07-12

- **Dokumentasi saja**: masterplan (baris Peta Siklus Pemindahtanganan &
  Pemusnahan → Sebagian, penanda roadmap Fase 6 diperluas #106/#110/#111),
  README (intro 11 modul Sebagian Aktif + blok Progres Fase 5–6), dan
  pustaka §9 (baris implikasi Pemindahtanganan & Pemusnahan).

## [#111] Pemindahtanganan tahap awal: register usulan 4 bentuk — 2026-07-12

- **Register pemindahtanganan** (bab pustaka §7, PMK 111/2016 jo.
  165/2021): usulan multi-aset berstatus diusulkan → disetujui →
  dilaksanakan → selesai; dokumen wajib per tahap (persetujuan, risalah/
  BAST/naskah/PP, NTPN utk penjualan, SK Penghapusan) + peringatan
  tenggat lelang 6 bulan. Kartu naik Sebagian; 4 unit test (suite 171).

## [#110] Pemusnahan tahap awal: register BA multi-aset — 2026-07-12

- **Register BA Pemusnahan** (PMK 83/2016): nomor persetujuan wajib,
  objek dibatasi Rusak Berat (divalidasi per aset), cara pemusnahan
  baku, snapshot identitas + nilai; halaman baru dengan ringkasan +
  form multi-aset. Kartu naik Sebagian Aktif; 3 unit test (suite 167).

## [#109] Konsolidasi dokumentasi Pemanfaatan & status modul — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #106–#108; README kini
  menyebut 9 modul Sebagian Aktif (13 kartu siklus bisa dimasuki).

## [#108] Pemanfaatan tahap awal: register perjanjian 6 bentuk — 2026-07-12

- **Fase 5 Pemanfaatan dimulai** (bab pustaka §6, PMK 115/2020): register
  perjanjian Sewa/Pinjam Pakai/KSP/BGS-BSG/KSPI/KETUPI dengan validasi
  jangka maksimal per bentuk; status Aktif menuntut nomor persetujuan
  Pengelola + perjanjian (sewa: + NTPN) — pencegah temuan auditor;
  peringatan jatuh tempo ≤60 hari. Seluruh 13 kartu siklus kini bisa
  dimasuki. 4 unit test (suite 164).

## [#107] Referensi masa manfaat dapat dikelola — 2026-07-12

- **Referensi masa manfaat** per kelompok (KMK 295/2019 jo. 266/2023):
  daftar gabungan berlabel sumber; admin tambah/ubah/hapus entri satker
  (menimpa bawaan riset); posisi penyusutan langsung memakai peta terbaru.

## [#106] Tiket usulan penghapusan berstatus (usul → proses → SK) — 2026-07-12

- **Tiket usulan** per aset kandidat (jalur otomatis, duplikat aktif
  ditolak): transisi tervalidasi diusulkan → diproses → SK terbit /
  ditolak (admin; SK wajib bernomor; anti-balapan; riwayat tercatat);
  kandidat menampilkan status usulannya. 2 unit test (suite 159).

## [#105] Konsolidasi dokumentasi Fase 5–6 tahap awal — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #102–#104 (Penilaian &
  Penghapusan → Sebagian); README dapat blok Progres Fase 5–6.

## [#104] Penghapusan tahap awal: kandidat usul hapus — 2026-07-12

- **Fase 6 dimulai** — halaman Penghapusan: kandidat dijaring dari
  inventarisasi per jalur PMK 83/2016 (Tidak Ditemukan → penelusuran +
  telaah TGR; Rusak Berat → pemusnahan/pemindahtanganan) + nilai
  perolehan. Kartu naik Sebagian Aktif; 3 unit test (suite 157).

## [#103] Halaman Penilaian: posisi penyusutan + daftar telaah — 2026-07-12

- **Halaman Penilaian** (dari Beranda Modul): kartu perolehan/akumulasi/
  nilai buku/habis masa manfaat, tabel per golongan, telaah henti-susut &
  perlu-referensi, pemilih tanggal posisi. Kartu naik Sebagian Aktif.

## [#102] Penyusutan BMN: garis lurus semesteran per golongan (API) — 2026-07-12

- **Fase 5 dimulai** — bab pustaka §5 Penyusutan (koreksi: KMK 59/2013
  dicabut → KMK 295/2019 jo. 266/2023) + logika murni PMK 65/2017 (tanpa
  residu, konvensi semester penuh, nilai buku habis = 0, bucket telaah
  henti-susut/perlu-referensi tanpa menebak angka) + endpoint
  `/penilaian/penyusutan`. 7 unit test (suite 154); UI menyusul.

## [#101] Konsolidasi dokumentasi Fase 4 tahap awal — 2026-07-12

- Masterplan/README/pustaka diselaraskan dengan #99–#100 (Perencanaan
  → Sebagian); README dapat blok Progres Fase 4.

## [#100] Kertas kerja usulan RKBMN pemeliharaan (XLSX) — 2026-07-12

- **Kertas kerja RKBMN** siap diisi satker: sheet Layak (identitas +
  riwayat biaya + kolom kuning Usulan Pekerjaan & Perkiraan Biaya) +
  sheet Tidak Layak (alasan/jalur benar); tombol di halaman Perencanaan;
  nama file mengikuti TA usulan (+1). Smoke roundtrip openpyxl.

## [#99] Perencanaan tahap awal: kandidat RKBMN pemeliharaan — 2026-07-12

- **Fase 4 dimulai** — halaman Perencanaan: saringan kelayakan usulan
  pemeliharaan (PMK 153/2021: Baik/RR layak; rusak berat → jalur hapus;
  idle → penetapan status) + riwayat biaya per aset dari modul
  Pemeliharaan (terbesar dulu). Kartu naik Sebagian Aktif; 6 unit test
  (suite 147 lulus).

## [#98] Transaksi massal persediaan: satu dokumen banyak barang — 2026-07-12

- **Transaksi Massal** (tombol baru di toolbar): satu bukti untuk ≤100
  barang; tiap barang tetap lewat jalur transaksi FIFO tunggal yang sudah
  teruji; kegagalan per barang dilaporkan per item (baris disorot merah,
  dialog tetap terbuka) tanpa membatalkan barang lain.

## [#97] Kartu Barang Persediaan PDF: riwayat + saldo berjalan — 2026-07-12

- **Kartu Barang** per barang persediaan (form kendali standar): identitas
  + jurnal kronologis dengan kolom masuk/keluar/sisa (saldo berjalan) dan
  nilai FIFO; tombol di dialog Riwayat. Barang tanpa transaksi = 404.

## [#96] Konsolidasi status Pelaporan Fase 2 (dokumentasi) — 2026-07-12

- Masterplan/README/pustaka/kartu modul diselaraskan: inti Pelaporan
  Fase 2 lengkap (#86, #93–#95); sisa pekerjaan Fase 2 didaftar eksplisit
  (KIB menunggu verifikasi lampiran, gudang/massal persediaan, CaLBMN/LKB).

## [#95] LBKP per golongan: saldo awal + mutasi + saldo akhir — 2026-07-12

- **LBKP semesteran/tahunan** (PMK 181): tiga seksi Intra/Ekstra/Gabungan
  per golongan — saldo awal, mutasi tambah (pencatatan), mutasi kurang
  (tombstone audit; nilai terekam sejak #94, kasus lama diungkap jujur),
  saldo akhir = identitas mutasi; dropdown periode di hub Pelaporan.
- 3 unit test (suite 141); smoke render tervalidasi angka-per-angka.

## [#94] Ekspor rekonsiliasi XLSX — sandingan SAKTI — 2026-07-12

- **Rekonsiliasi XLSX** (3 sheet): Posisi per Golongan, Rincian Aset
  (klasifikasi per NUP), Rincian Persediaan (nilai FIFO) — tombol di hub
  Pelaporan; angka numerik agar bisa dihitung ulang di Excel.
- Fondasi LBKP: audit hapus aset kini merekam nilai perolehan (tombstone
  bernilai untuk mutasi kurang mendatang). Smoke roundtrip openpyxl.

## [#93] Laporan Posisi BMN di Neraca — komponen LBKP — 2026-07-12

- **Posisi BMN di Neraca** (PMK 181, pustaka §2.3): seluruh aset satker
  lintas kegiatan per golongan (intra/ekstra) + baris Persediaan (nilai
  FIFO per layer) + total posisi; unduh dari hub Pelaporan.
- Helper murni `posisi_neraca` + 2 test (suite 138); fix impor `timezone`
  reports.py (tertangkap smoke).

## [#92] Jadwal pemeliharaan berkala: jatuh tempo + status + auto-geser — 2026-07-12

- **Jadwal Berkala** per aset (pedoman DKPB Ps. 46(2) PP 27/2014): interval
  1–60 bulan, jatuh tempo dihitung dari pelaksanaan terakhir + interval,
  status **Terlambat / Segera (≤14 hari) / Terjadwal**; mencatat
  pemeliharaan otomatis menggeser jadwal aset tsb.
- Seksi baru di halaman Pemeliharaan: badge peringatan, aksi Catat
  (prefill aset), ubah, hapus admin. 5 unit test (suite 136 lulus).

## [#91] Konsolidasi dokumentasi Fase 3 (masterplan + README) — 2026-07-12

- Tabel peta siklus masterplan: 5 modul kini berstatus **Sebagian** dengan
  rujukan PR (#76–#90); README dapat blok **Progres Fase 3** (#87–#90) dan
  paragraf Beranda Modul yang menyebut modul-modul Sebagian Aktif.

## [#90] DHPB PDF semesteran/tahunan — laporan berkala pemeliharaan — 2026-07-12

- **DHPB (Daftar Hasil Pemeliharaan Barang)** per periode (tahun penuh /
  Semester I / II — Ps. 47 PP 27/2014): PDF landscape berkop surat, grup
  per aset + subtotal & total, tanda telaah kapitalisasi, ttd KPB; tombol
  dropdown di halaman Pemeliharaan. Periode kosong = 404 (tanpa dummy).
- Smoke render FakeDB menangkap bug label aset terjepit → SPAN baris grup.

## [#89] Pemeliharaan tahap awal: riwayat + biaya per aset (bahan DHPB) — 2026-07-12

- **Modul Pemeliharaan** (PP 27/2014 Ps. 46-47, riset regulasi → pustaka
  §4): catat kejadian per aset (jenis ringan/sedang/berat DJKN, biaya,
  pelaksana, bukti), kondisi sebelum/sesudah (opsional memperbarui kondisi
  aset), rekap per tahun anggaran/jenis + aset terboros, filter, dan
  **penanda telaah kapitalisasi** bila biaya ≥ ambang PMK 181/2016.
- Kartu Pemeliharaan naik Sebagian Aktif. 18 unit test (suite 128 lulus);
  koleksi baru `pemeliharaan` + indeks.

## [#88] Pengamanan tahap awal: dasbor tertib administrasi + sengketa — 2026-07-12

- **Dasbor kesehatan data aset**: 6 kartu (Data Lengkap + tanpa foto/
  register/lokasi/pengguna/BAST — klik → daftar aset bermasalah) +
  **Daftar Pantau Sengketa** (perkara, pihak) dari data inventarisasi.
- Kartu Pengamanan naik Sebagian Aktif. 8 unit test; tanpa koleksi baru.

## [#87] Penggunaan tahap awal: rekap aset per pemegang + BAST — 2026-07-12

- **Fase 3 dimulai** — halaman "Aset per Pemegang" (lintas kegiatan) dari
  data pengguna+NIP+BAST inventarisasi: badge Lengkap / BAST x/y, dialog
  daftar aset per pemegang; kunci nama ternormalisasi + NIP. Kartu
  Penggunaan naik Sebagian Aktif. 7 unit test; tanpa koleksi baru.

## [#86] Hub Pelaporan — arsip laporan lintas kegiatan satu pintu — 2026-07-12

- **Halaman Arsip Pelaporan** (dari Beranda Modul): daftar semua kegiatan
  (cari, badge Disahkan) + dropdown unduh 7 laporan resmi per kegiatan
  (LHI/RHI/BAHI/DBKP/SP/Eksekutif) + seksi laporan persediaan.
- Kartu Pelaporan kini bisa dimasuki; LBKP & rekonsiliasi menyusul.

## [#85] Impor/ekspor master persediaan + template + toolbar menu — 2026-07-12

- **Impor CSV/XLSX master persediaan**: identitas (kode 16 + NUP) sudah ada
  → perbarui field non-identitas; baru → jalur create (kode 10 digit
  auto-suffix, NUP otomatis); stok/layer tak tersentuh; laporan per baris.
- **Template CSV** + **Ekspor CSV** (master + stok & nilai FIFO terkini).
- Toolbar persediaan dirapikan: menu **Dokumen** (Posisi/Mutasi/Kertas
  Kerja/BAOF) + menu **Data** (Impor/Template/Ekspor) — ramah HP.
  5 unit test parser impor (48 total lulus).

## [#84] Konsolidasi status modul Persediaan (dokumentasi) — 2026-07-12

- Kartu modul Persediaan di Beranda Modul menampilkan fitur berjalan
  (✅ #77–#83) vs menyusul (gudang, impor massal, massal per dokumen);
  masterplan §7.4 ditandai per PR; README blok "Progres Fase 2".

## [#83] Stock opname persediaan + BAOF 3 penandatangan — 2026-07-12

- **Opname per barang**: stok fisik + alasan wajib → selisih dibukukan
  otomatis (kurang = konsumsi FIFO; lebih = layer penyesuaian harga layer
  termuda) + jurnal jenis opname (OPN); bersyarat versi + retry.
- **Kertas Kerja Opname** (kolom fisik kosong, pola SAKTI) & **BAOF** per
  tanggal (buku → fisik → selisih ± + alasan) — keduanya PDF berkop.
- `_signature_block` kini mendukung **3 penandatangan** (penghitung, saksi,
  mengetahui) — dulu ttd ke-3 terbuang diam-diam. 90 unit test lulus.

## [#82] Laporan persediaan: Posisi Stok + Mutasi Periode (PDF) — 2026-07-12

- **Laporan Posisi Persediaan**: per kelompok kodefikasi (uraian dari
  referensi), nilai per barang dihitung FIFO per layer, subtotal +
  grand total.
- **Laporan Mutasi Persediaan** per periode dari JURNAL: saldo awal →
  masuk (qty/nilai) → keluar (qty/nilai) → saldo akhir + TOTAL.
- Tombol Posisi & Mutasi (dialog rentang, default bulan berjalan) di
  toolbar Master Persediaan. 3 unit test mutasi_periode (39 total);
  smoke render tervalidasi visual.

## [#81] Peringatan kritis/kedaluwarsa + nota dinas PDF persediaan — 2026-07-12

- **Daftar pantau persediaan** (`/persediaan/peringatan`): habis, kritis
  (stok ≤ batas), layer kedaluwarsa & segera kedaluwarsa (horizon 30 hari).
- **Nota dinas PDF otomatis** (kritis/kedaluwarsa): kop surat + tabel +
  tanda tangan KPB — usulan pengadaan atau tindak lanjut kedaluwarsa.
- **Banner peringatan** kuning + tombol unduh nota dinas di halaman
  Master Persediaan. 3 unit test klasifikasi kedaluwarsa (36 total).

## [#80] Transaksi keluar FIFO persediaan — konsumsi layer tertua — 2026-07-12

- **Transaksi KELUAR persediaan**: konsumsi layer FIFO tertua dulu; nilai
  keluar = Σ qty terpakai × harga layer (FIFO murni); jenis peta SAKTI
  (Habis Pakai K01, Transfer K02, Hibah K03, Usang K04, Rusak K05);
  update master bersyarat versi + retry 3× (aman balapan); jurnal berisi
  rincian layer + unit penerima; jurnal gagal → snapshot dikembalikan.
- Tombol **Keluar** di halaman persediaan (nonaktif saat stok 0) + toast
  nilai keluar FIFO. 8 unit test konsumsi FIFO baru (33 total lulus).

## [#79] Transaksi masuk FIFO persediaan — layer + jurnal + UI — 2026-07-12

- **Transaksi MASUK persediaan**: jenis memetakan 1:1 ke SAKTI (Saldo Awal
  M01, Pembelian M02, Transfer M03, Hibah M04, Perolehan Lainnya M99);
  layer FIFO baru (harga & kedaluwarsa melekat di layer) + stok naik
  atomik + **jurnal** ber-stok sebelum/sesudah + dokumen sumber; bila
  jurnal gagal → layer & stok dikompensasi.
- Tombol **Masuk** & **Riwayat** per baris di halaman Master Persediaan
  (kartu jurnal: jenis + kode SAKTI, jumlah × harga, stok →, bukti,
  petugas). 5 unit test baru.

## [#78] UI Master Persediaan — modul naik Sebagian Aktif — 2026-07-12

- **Halaman Master Persediaan** dari Beranda Modul: cari + chip filter
  status stok (aman/kritis/habis, dihitung di server), tambah barang
  (kode '1' 10 digit → nomor urut otomatis; NUP otomatis; satuan baku),
  edit ber-OCC (If-Match; 409 memuat ulang), hapus admin berkonfirmasi.
- Kartu "Inventarisasi Persediaan" di Beranda Modul naik status
  **Sebagian Aktif** dan bisa dimasuki. Transaksi FIFO/gudang/opname
  menyusul (§7.4).

## [#77] Master Persediaan — langkah 1 modul Inventarisasi Persediaan — 2026-07-12

- **Master barang persediaan** (`/api/persediaan`): kode wajib berawalan '1'
  (10 digit → nomor urut otomatis; 16 digit penuh), NUP otomatis, identitas
  unik; stok lahir 0 dan **stok/nilai bersumber dari layer FIFO** (perpetual
  + FIFO per layer, selaras SAKTI — pustaka §3); status stok
  habis/kritis/aman terfilter di query; update ber-OCC (If-Match); hapus
  hanya saat stok 0. Registry field anti-drift + 20 unit test.
- KIB **ditunda** menunggu verifikasi Lampiran PMK 181 (aturan "regulasi
  dulu, kode kemudian") — tercatat di masterplan.

## [#76] DBKP per golongan — langkah pertama modul Pembukuan — 2026-07-12

- **Laporan DBKP (Daftar Barang Kuasa Pengguna) per golongan** sesuai PMK
  181/2016: pemilahan **intra/ekstrakomptabel** dari ambang kapitalisasi
  ber-parameter (Peralatan & Mesin ≥ Rp1 jt; Gedung & Bangunan ≥ Rp25 jt;
  lainnya selalu intra); uraian golongan dari referensi kodefikasi; barang
  tanpa golongan tampil sebagai baris "?" (tidak disembunyikan); catatan
  ambang + tanda tangan Kuasa Pengguna Barang.
- Tombol "DBKP per Golongan" di panel Laporan Resmi + masuk batch ZIP.
- `pembukuan_utils.py` + 14 unit test; smoke render FakeDB tervalidasi
  visual (menemukan & memperbaiki header patah + field nama kegiatan).

## [#75] Perbaikan hover light/dark + aturan anti-terulang + pustaka regulasi — 2026-07-12

- **Hover dibetulkan di kedua tema**: akar masalah = token `--accent`
  proyek adalah biru pekat + teks putih. `hover:bg-accent` → `hover:bg-muted`
  (Beranda Modul, Kodefikasi, bar peta); tombol **Kartu** di header edit
  aset diberi pasangan `hover:text-*` kedua tema (dulu teks putih di atas
  emerald terang → tak terbaca di light mode). Aturan anti-terulang 6b
  tertulis di SKILL.md.
- **`docs/PUSTAKA-REGULASI-BMN.md`** — rujukan wajib sebelum membangun
  modul: penatausahaan PMK 181/2016 (DBKP/DBR/KIB 6 jenis/LBKP/jenjang),
  persediaan (desain **FIFO per batch tervalidasi** — perpetual + FIFO per
  layer ala SAKTI sejak TA 2021; enum transaksi resmi; opname + BAOF;
  akun 1171xx), kendala satker → fitur penangkal, butir perlu-verifikasi,
  sumber. SKILL.md aturan 10: "regulasi dulu, kode kemudian".

## [#74] UI Referensi Kodefikasi — kelola & impor dari Beranda Modul — 2026-07-12

- **Halaman Referensi Kodefikasi**: cari kode/uraian (debounce), chip filter
  per level, tabel berpaging + badge level berwarna + penanda PERSEDIAAN
  (kode berawalan '1'); back-guard HP.
- **Admin**: tambah (level otomatis dari panjang kode), ubah uraian, hapus
  berkonfirmasi (turunan ditolak server), impor CSV/XLSX + ringkasan hasil,
  unduh template. Non-admin baca saja.
- Tombol perkakas "Referensi Kodefikasi Barang" di kartu Penatausahaan
  Beranda Modul.

## [#73] Kodefikasi referensi barang 5 level — fondasi Fase 2 — 2026-07-12

- **Referensi kodefikasi BMN** (`/api/kodefikasi`): struktur 5 level dari
  panjang prefix kode (1/3/5/7/10 digit — Golongan/Bidang/Kelompok/Sub/
  Sub-sub); digit pertama memisahkan domain ('1' persediaan, '2'-'8' aset).
- Endpoint: list (cari/filter/paging), `/golongan` (seed 8 golongan standar
  idempoten), `/lookup/{kode}` uraian berjenjang, `/template` CSV, CRUD
  admin (hapus ditolak bila punya turunan), `/import` CSV/XLSX upsert
  dengan laporan per baris. Index kode unik.
- 24 unit test logika murni (anti-drift) — level SELALU diturunkan dari
  panjang kode, tak bisa bertentangan dengan file impor.
- Fondasi untuk Pembukuan (DBKP/KIB), Inventarisasi Persediaan, dan
  Pengadaan pada iterasi loop fase berikutnya.

## [#70] Deploy: retry jangkauan VPS 5x + ulangi SSH sekali — 2026-07-11

- `deploy.yml` kini tahan gangguan sesaat: `ssh-keyscan` dicoba **5 kali**
  berjarak 20 detik (timeout 15 dtk/percobaan) dan eksekusi skrip deploy
  **diulang sekali** bila koneksi putus (skrip idempoten). Latar: run
  deploy pasca-merge #69 gagal keyscan padahal konfigurasi benar.

## [#69] Bar peta HP satu baris (menu gabungan) + siklus selaras diagram resmi Kemenkeu — 2026-07-11

- **Bar peta di HP jadi SATU baris**: filter Barang Serupa + Unduh
  (KML/KMZ/SHP) + Muat Ulang dilebur ke **satu tombol ber-menu** — ikon
  Layers menyala violet + titik penanda saat filter kelompok aktif,
  berganti spinner saat memuat; item menu ≥42px. ≥sm tetap kontrol
  terpisah.
- **Siklus selaras diagram resmi Kemenkeu** (12 tahap): Perencanaan
  Kebutuhan ≠ Penganggaran, Pengamanan ≠ Pemeliharaan; **dasar hukum
  (PMK) per tahap** tampil di dialog konsep; sub-kegiatan dirinci
  (Penggunaan: PSP/alih status/sementara/pihak lain/bersama + BMN idle;
  Pemanfaatan: Sewa/Pinjam Pakai/KSP/BGS/BSG/KSPI/KETUPI/PDF;
  Pemindahtanganan: Penjualan/Hibah/Tukar Menukar/Penyertaan Modal;
  Wasdal: pemantauan/investigasi/portofolio aset/analisis SBSK/
  penertiban); strip **6 asas pengelolaan** di Beranda Modul; masterplan
  diperbarui mengikuti diagram.

## [#68] Rumah modul Siklus BMN + masterplan pengembangan + skill proses baku — 2026-07-11

- **Beranda Modul** — halaman pertama setelah login: peta Siklus Pengelolaan
  BMN (PP 27/2014) dengan Penatausahaan sebagai poros. **Inventarisasi Aset
  AKTIF** (pintu ke aplikasi berjalan); Pembukuan, Inventarisasi Persediaan,
  Pelaporan + 10 tahap siklus lain berstatus **Segera Hadir** — klik kartu
  menampilkan konsep, rencana fitur, integrasi, dan fase roadmap.
- Registry modul `frontend/src/lib/bmnModules.js` (satu sumber kebenaran
  status & konsep modul); pilihan modul per-tab — reload di tengah kerja
  lapangan tidak terlempar; tombol **Modul** di halaman Pilih Kegiatan.
- **`docs/MASTERPLAN-SIKLUS-BMN.md`** — rencana induk hasil pendalaman repo
  referensi KERJA-BARENG (SIMAN-G): pola yang diadopsi (kodefikasi prefix
  5 level, transaksi stok vs atribut, approval `pending_changes`,
  reklasifikasi 2 langkah, dokumen sumber sebagai simpul, FIFO batch,
  interop SIMAN) & anti-pola yang dihindari; 7 prinsip integrasi antar
  modul; **konsep rinci Inventarisasi Persediaan** (master ber-batch FIFO,
  transaksi masuk/keluar per dokumen sumber, gudang, stock opname +
  penyesuaian otomatis, nota dinas kritis/kedaluwarsa); roadmap fase 1–6.
- **`.claude/skills/aman-dev/SKILL.md`** — proses baku pengembangan bertahap
  per fitur: peta repo, konvensi wajib, pipeline verifikasi→PR→CI→merge→
  auto-deploy, jebakan umum, checklist pemilik proyek.
- README: bagian "Arah Pengembangan — Siklus Penuh Pengelolaan BMN".

## [#67] Popup pin berbingkai foto + bar peta ringkas di HP + halaman PRD v2.3 — 2026-07-11

- **Popup marker peta dirombak** — padat & informatif: bingkai foto sampul
  62×62 (streaming 256px saat online, thumbnail snapshot saat offline; tanpa
  foto → blok judul melebar penuh), badge "N foto", pill status/kondisi
  berwarna + pill hijau "Pengguna lengkap ✓", baris info berlabel (Merk/Tipe,
  Kategori, Lokasi, Pengguna+NIP) yang hanya tampil bila terisi, tombol
  **Edit Aset** selebar popup.
- **Bar peta dua baris di HP**: [ikon · judul · tutup] lalu [filter kelompok
  (melebar) · unduh · muat ulang] — teks jumlah titik tidak lagi terpotong
  (versi ringkas "616/616 titik"); ≥sm tetap satu baris.
- **Halaman PRD tersembunyi → v2.3**: bagian baru "Apa yang Baru — Rilis
  v2.3" (6 kartu catatan rilis), hero dipoles (copy, chip kapabilitas, cahaya
  latar), grid statistik 5 kartu dibetulkan, timeline implementasi responsif.

## [#66] Hover ikon peta, tata letak mode pindai, & panel Edit Info kamera — 2026-07-11

- Tombol peta di toolbar: warna teks saat **hover di light mode** dibetulkan
  (dulu putih di atas latar terang → tidak terlihat).
- **Mode pindai kamera**: saat scanner aktif, tombol shutter/zoom/aksi
  disembunyikan dan diganti bilah pindai dengan tombol "Batal Scan" lebar
  penuh — tidak ada lagi kontrol bertumpuk.
- **Panel Edit Info kamera selengkap lembar edit cepat inventarisasi**:
  chip Status & Kondisi, blok detail kondisional (klasifikasi/sub, asal-usul,
  sengketa, tindak lanjut), stiker + ukuran, Pengguna Barang (melekat ke,
  jenis operasional, jabatan, nama, NIP/NIK) — konstanta diimpor dari
  `InventoryFieldSheet` (satu sumber). Tombol **"Simpan & Scan"** di dalam
  panel: simpan → kamera kembali memindai aset berikutnya.

## [#65] Peta jadi lembar di halaman utama + alur Simpan & Scan + pembaruan dokumen — 2026-07-11

- **Peta Aset kini lembar di halaman utama** (bukan overlay lepas): header,
  saklar Dashboard/Inventarisasi, dan toolbar filter tetap tampil; area baris
  data digantikan peta saat terbuka. Form tambah/edit aset tetap bisa muncul di
  samping (desktop) / di atasnya (HP) — selesai edit **kembali ke peta**.
- **Barang Serupa jadi filter peta**: dropdown kelompok (kode+nama, ≥2 unit)
  diturunkan dari data peta sendiri — ikut filter aktif dan jalan saat offline.
- Pin kini **satu popup** saja (tooltip hover dihapus — dulu tampil dobel di
  layar sentuh); tombol Edit menutup popup, peta tetap terbuka.
- **Alur scan-edit lapangan dirapikan**: tombol utama **"Simpan & Scan"**
  (simpan aset ini → scanner langsung terbuka lagi untuk stiker berikutnya),
  "Simpan & Aset Baru" jadi baris sekunder, tombol Batal Scan diperbesar.
  Intent `camera:stay` menyimpan tanpa berpindah aset.
- HP: padding & jarak antar blok diperkecil khusus layar kecil — baris data
  dapat ruang lebih (tinggi tombol tetap ≥44px sesuai aturan tap-target).
- Dokumentasi menyeluruh: CHANGELOG terisi ulang (#38–#65), README v2.3,
  halaman PRD tersembunyi diperbarui (peta, kamera, CI/CD, ekspor GIS).

## [#64] Ekspor peta KML/KMZ/SHP + marker berlapis info + filter tanggal + kop KPB — 2026-07-11

- **Unduh KML/KMZ/SHP** dari peta — 27 atribut per titik, mengikuti filter
  aktif (endpoint `/api/export/geo`, shapefile WGS84 via pyshp).
- Pin peta: **badge kamera** bila ada foto; **border hijau** bila pengguna +
  NIP/NIK + BAST lengkap.
- Filter Lanjutan: **rentang Tanggal Input** (server + offline + badge).
- **Kop surat 3 baris** sesuai format resmi (instansi besar; unit + sub-unit
  tebal) + **alamat multi-baris** (textarea; tiap Enter = baris kop).
- Seluruh tanda tangan laporan: "Kepala Satuan Kerja" → **"Kuasa Pengguna
  Barang"**.
- `build_asset_search_query` diekstrak dari GET /assets — daftar, peta, dan
  ekspor geo memakai SATU builder filter (tidak bisa drift).

## [#63] Peta Aset halaman penuh + filter aktif + tombol ikon toolbar — 2026-07-11

- Peta pindah dari panel bertumpuk ke tampilan penuh; tombol ikon pin teal di
  samping Cari & Scan (ikon saja di HP/tablet).
- Data peta mengikuti pencarian + kategori + filter lanjutan; offline memakai
  snapshot dengan filter yang sama.
- Backend: semua opsi sort GET /assets diberi tiebreaker `id` — paging
  skip/limit deterministik.

## [#59–#62] Auto-deploy ke VPS Hostinger — 2026-07-11

- Workflow **Deploy ke Hostinger VPS**: setiap merge ke `main` menjalankan
  `scripts/deploy_vps.sh` di VPS lewat SSH (fetch+reset, pip install, restart
  backend, yarn build). Manual dispatch juga tersedia.
- Secret `VPS_SSH_KEY` menerima format **base64 satu-baris** (anti salah
  tempel); validasi kunci & uji jangkauan host dengan pesan error berbahasa
  jelas. README deploy dibetulkan ke `origin/main`.

## [#58] Kamera lapangan: flash, gestur kecerahan, simpan instan; edit cepat scan QR; Peta Aset — 2026-07-11

- **Flash/senter** (menyala ulang setelah flip kamera) + **gestur kecerahan**
  (tahan & geser atas/bawah; dibakar ke hasil foto, termasuk fallback iOS ≤17).
- **Simpan & Baru instan**: alur kamera melewati validasi server & kompresi
  Tinify per foto (lokal saja) — antrean latar tetap memvalidasi & auto-renumber
  NUP saat sinkron.
- **Kamera + Scan QR** untuk edit cepat antar-aset di mode inventarisasi
  (cocok EKSAK pada register/kode/serial; ambigu → isi kotak pencarian).
- **Peta Aset** perdana (leaflet + OSM): pin status berwarna, geser pin =
  koordinat tersimpan otomatis lewat antrean (If-Match + Idempotency-Key).
- 19 temuan verifikasi adversarial (43 agen) diperbaiki pra-merge, termasuk
  XSS tooltip peta dan bypass OCC/row-lock.

## [#57] Gerbang CI + registry field aset + perbaikan menyeluruh laporan — 2026-07-11

- **CI GitHub Actions**: backend compileall + 26 test unit bebas-infra;
  frontend eslint (react-hooks) + build — jalan di setiap PR. Run pertamanya
  langsung menangkap `yarn.lock` yang drift (entri idb hilang).
- **Registry field aset** (`backend/asset_fields.py`): PATCH, ubah massal,
  audit, proyeksi list, CSV, impor diturunkan dari satu daftar + test
  anti-drift. Bonus: eselon1/2 kini terlacak audit.
- **Perbaikan laporan besar**: binding "Unit Organisasi" (dulu terisi nama
  kegiatan), blok identitas rata (tabel titik dua sejajar + baris NIP),
  penomoran BAHI/BA, "Halaman 2 dari N" eksekutif, Tim Inti/Pembantu muncul
  di Personil laporan satker, footer ekspor dobel, jam WIB, kartu KONDISI/
  STATUS tertukar, footer barang-serupa di tiap halaman, tanggal gaya
  Indonesia di semua laporan.
- pytest hygiene: 15 skrip test era scaffold dihapus, `pytest` default hanya
  test unit; test live-server ber-marker `integration`.

## [#38–#56] Ringkasan gelombang sebelumnya — 2026-07-08 s.d. 2026-07-10

Progres unduhan kartu; posisi tombol X pop-up; perbaikan header otorisasi
"pengguna melekat"; paritas ubah-massal dengan form edit; halaman riwayat
sebagai panel; verifikasi hasil scan terhadap kegiatan aktif; back/undo
browser tetap di aplikasi; GPS selalu realtime; baris terakhir laporan tak
tertimpa footer (running element); **Mode Kamera Penuh ala Timemark** dengan
alur beruntun + NUP dummy otomatis per perangkat; hapus baris optimistik
langsung hilang; **performa menyeluruh** (index Mongo, proyeksi list ramping,
virtualisasi kartu HP, streaming foto ber-ETag); **foto GridFS-only** dengan
migrasi terverifikasi; token media 30 hari; **deteksi versi baru otomatis**
("Muat Ulang" tanpa hapus cache); logo 3-klik ke halaman PRD; kartu tim
2 baris; **field NIP/NIK pegawai** end-to-end; label NIP/NIK + kolom Dari
Satker pada tim; gating auth batch endpoints; dokumen review refactoring.

## [#37] Kartu Inventarisasi cetak: presisi ke mockup + riwayat 8 baris — 2026-07-05

- **Riwayat** menyimpan: **petugas** (akun pelaku dari audit-log, fallback pelaku
  pengesahan), **nomor surat**, **dokumen** (checklist checked/total), dan
  **catatan** (notes aset) — semua di-snapshot saat pengesahan.
- **Depan Hal 1** disesuaikan presisi ke mockup: header dua baris (KARTU
  INVENTARIS + "Aset Tetap Milik Instansi"); **QR pindah ke kanan-atas** dekat
  kode (bukan footer); placeholder "FOTO ASET 4:3" + ikon kamera; badge jadi
  tiga kolom berlabel **STATUS · AKTIVITAS · NILAI PEROLEHAN**; footer **"ID
  ASET"** kotak gelap + ikon perisai + kode register, dan KODE|NUP di kanan.
- **Detail Administrasi**: KATEGORI → **PEROLEHAN DARI**, tile **KELENGKAPAN**
  (checked/total + %), Penanggung Jawab = pengguna + konteks melekat-ke; ikon
  vektor asli di semua label.
- **Riwayat 5 kolom** hemat ruang: NO · TIKET/TANGGAL · KEGIATAN (nama + No.
  Surat + Lokasi) · **PETUGAS/CATATAN** (catatan dapat ruang lebih) ·
  **KONDISI/DOK**. Menampilkan **8 baris** (4/halaman); bila >8, hanya **8
  terbaru** yang tampil (tertua mengalah), urut kronologis lama→baru.
- Panel **saling menempel** + garis lipat silang + label judul di tepi luar.
  Kartu massal memakai renderer sama.

## [#36] Redesain Kartu Inventarisasi cetak (4 panel + garis lipat + riwayat) — 2026-07-05

Kartu inventarisasi cetak (`cards.py`) dirombak sesuai contoh desain: **4 panel
dalam grid 2×2** pada satu halaman A4 landscape dengan **garis lipat** (dashed)
— vertikal antara Halaman 1 & 2, horizontal antara Tampak Depan & Belakang —
agar depan-belakang dan hal 1-2 menempel saat dilipat jadi kartu dua sisi:
- **Depan Hal 1**: header "KARTU INVENTARIS" + NUP, foto, KODE INVENTARIS besar,
  nama, grid spec (kategori/S-N/merek/lokasi), badge kondisi & status, Nilai
  Perolehan, footer QR asli (`#kode_register`) + ID/Kode/NUP.
- **Depan Hal 2**: "DETAIL ADMINISTRATIF" — tile eselon I/II, penanggung jawab,
  tgl/kontrak/BAST, lokasi/SPM/supplier/kategori.
- **Belakang Hal 1 & 2**: tabel "RIWAYAT INVENTARISASI" (No/Tanggal/Jenis
  Kegiatan/Lokasi/Petugas/Kondisi/Ket, 3 baris/halaman, footer "Halaman X dari 2").
- **Data riwayat** kini diambil dari `inventory_history` (per kode register /
  kode+NUP, scope satker) — sebelumnya kartu tak memuat riwayat.
Endpoint bulk memakai renderer sama (satu halaman lipat per aset). Diverifikasi
dengan render PDF → raster PNG.

## [#33] UX ronde B: validasi inline, aksesibilitas, empty/error state — 2026-07-05

- **Validasi inline**: error di form aset & kegiatan kini tampil di bawah field
  terkait (border merah + teks bantuan + `aria-invalid`), auto-scroll & pindah
  tab ke field pertama yang salah; toast jadi ringkasan singkat (bukan sumber
  detail).
- **Aksesibilitas**: baris tabel & kartu mobile bisa dioperasikan keyboard
  (Enter/Space, `role=button`, focus-ring); target sentuh aksi baris 20→28px;
  glyph status inventaris diberi label penuh + font dinaikkan; ukuran teks
  data (badge) di dua tampilan list utama dinaikkan; overlay buatan-sendiri
  (lightbox foto kegiatan, reset, restore) dapat `role=dialog aria-modal`,
  autofocus, Escape, dan focus-restore.
- **Empty/error state**: gagal muat kegiatan → kartu error + "Coba Lagi"
  (bukan seolah tak ada kegiatan); daftar aset kosong dibedakan: filter aktif →
  "tidak cocok" + Reset filter, vs kegiatan baru → "Belum ada aset" + CTA
  tambah; overlay blocking ekspor yang redundan dihapus.

## [#32] UX ronde A: pill pengesahan dashboard, dialog konfirmasi terpadu, paritas aksi mobile, branding — 2026-07-05

- **Pengesahan di layar kerja**: pill toolbar (admin) — "Siap disahkan" / "{n}
  syarat belum" / "Disahkan · {tiket}" — membuka dialog pengesahan langsung;
  tombol di kartu kegiatan dibuat selalu terlihat.
- **Dialog konfirmasi terpadu** (`ui/ConfirmDialog` + `useConfirm`): menggantikan
  semua `window.confirm`; hapus kegiatan (cascade) butuh ketik "HAPUS".
- **Paritas aksi mobile**: menu ⋯ (Kartu Inventarisasi / Riwayat / Cetak Kartu /
  Hapus) setara aksi baris desktop.
- **Branding/istilah**: wordmark AMAN, tahun copyright dinamis, "Users"→
  "Pengguna", "Logout"→"Keluar".

## [#31] Pengerasan keamanan menyeluruh (hasil audit) — 2026-07-05

> ⚠️ **Prasyarat deploy**: (1) `JWT_SECRET` **wajib** diset di environment —
> backend kini menolak boot tanpanya (menutup lubang secret hardcoded).
> (2) Set `ALLOWED_ORIGINS` (koma) bila domain frontend ≠
> `amanikn-inventarisasi.com`.

Audit adversarial menemukan bahwa banyak API inti **belum terproteksi auth**;
semua ditutup:

- **Auth gating ~54 handler**: seluruh CRUD aset & kegiatan, list/stats/
  analytics, ekspor CSV/PDF/XLSX, audit-log, semua generator laporan,
  report-settings (tulis→admin), compress-image, kartu cetak, validasi —
  kini `require_user`/`require_admin`. (Dulu bisa dihapus/dibaca **anonim**,
  termasuk `DELETE /inventory-activities` yang cascade hapus semua aset.)
- **JWT fail-fast** (tak ada lagi secret default), **CORS** dipin ke allowlist
  env (bukan `*` + credentials).
- **Auth media/preview via token** (`?token=`) untuk `<img>`/`window.open`
  (foto, checklist, BAST, dokumen pengesahan, preview laporan) — dulu terbuka
  anonim.
- **XSS**: Jinja `autoescape` diaktifkan di 7 environment (nilai user di-escape;
  HTML server-built dibungkus `Markup`); `doc-file` tak lagi menuruti MIME dari
  data user (paksa image/pdf + `X-Content-Type-Options: nosniff`).
- **ReDoS/regex injection**: input pencarian di-`re.escape` sebelum `$regex`.
- **Orphan GridFS**: hapus aset/kegiatan kini membersihkan foto/BAST/checklist.
- **Audit actor** diambil dari JWT (bukan header `X-Audit-User` yang bisa
  dipalsu); audit-log dibatasi `page_size` ≤200.
- **OTP debug** hanya keluar bila `ALLOW_DEBUG_OTP` & non-produksi; pesan error
  ke klien digeneralkan (detail hanya di log server).

Diverifikasi: 22/22 uji ASGI+mongomock (401 tanpa token, 200 dengan; delete
admin-only; regex literal; cleanup GridFS; XSS ter-escape); `yarn build`
bersih. Sisa yang di-defer terdokumentasi (mis. `doc-file` publik untuk tautan
spreadsheet — dikeraskan MIME/nosniff, konten sama tersedia lewat endpoint
checklist ber-token).

## [#28] Lingkup satker kartu, pengguna melekat-ke + BAST, validasi & backup parity — 2026-07-04

- **Kartu Inventarisasi per satker**: record `inventory_history` kini menyimpan
  kode/nama satker; query kartu difilter satker kegiatan aktif (record lama
  tanpa satker tetap tampil, ditandai legacy); satker tampil di header & baris.
- **Pengguna "Melekat ke"** (Individual/Jabatan/Operasional) + nama jabatan
  kondisional; **Nomor BAST + unggah dokumen BAST** per aset (PDF/JPG/PNG/WEBP
  ≤10MB, GridFS, preview setelah simpan, 423 saat terkunci, tanpa bump OCC).
  Field mengalir ke PATCH diff, list projection, snapshot offline, import,
  audit `TRACKED_FIELDS`, dan ekspor CSV (45 kolom) + XLSX.
- **Validasi pengesahan tambahan**: nol aset kategori dummy; semua aset wajib
  kode register, Eselon I/II, lokasi, dan pengguna — baris merah/hijau per
  syarat di dialog pengesahan; detail 400 teritemisasi pada `/sahkan`.
- **Pemeriksaan sistem lintas-fitur** (celah integrasi diperbaiki): whitelist
  snapshot offline kini membawa field pengguna/BAST (edit & tampilan offline
  tidak kehilangan nilainya); antrian offline **tidak auto-retry** simpanan
  yang ditolak 423 (kegiatan terkunci) — toast/pesan kunci jelas, hanya
  retry/dismiss manual; audit log untuk unggah/hapus dokumen pengesahan;
  label aksi "Pengesahan" + label field baru di panel audit; template import
  CSV/XLSX ikut memuat 3 kolom pengguna/BAST (dropdown Melekat Ke); reset
  sistem (HAPUS SEMUA) kini juga menghapus `inventory_history` + `counters`.
- **Paritas backup & restore**: backup kini mencakup `inventory_history` dan
  `counters` (sequence tiket — `_id` string dipertahankan); restore membangun
  ulang counter tiket dari `ticket_number` kegiatan (anti nomor duplikat saat
  restore backup lama) dan membangun ulang semua index; alasan skip koleksi
  transient (row_locks, otp_store, idempotency_keys, ws_events, backup_jobs)
  terdokumentasi. GridFS satu bucket `fs` — foto aset, dokumen kegiatan,
  dokumen pengesahan, dan BAST otomatis tercakup `export_gridfs`.
- **Dokumentasi**: `docs/PENGESAHAN.md` — alur tiket → pengesahan → kunci →
  kartu inventarisasi + format QR untuk operator.

## [#27] Tiket kegiatan, alur pengesahan + kunci, kartu inventarisasi, QR — 2026-07-04

- **Nomor tiket kegiatan** `INV-{tahun}-{seq}` (counter atomik di koleksi
  `counters`; backfill startup/lazy untuk kegiatan lama) — tampil di kartu
  kegiatan & header dashboard.
- **Pengesahan**: layak hanya bila semua aset sudah diinventarisasi & berfoto
  (dan total > 0); admin unggah ≥1 PDF bertanda tangan (GridFS, cek `%PDF`,
  ≤20MB) lalu `POST /sahkan` mengunci kegiatan secara atomik + menulis satu
  record `inventory_history` per aset (tiket, kegiatan, tanggal, identitas,
  snapshot status/kondisi/lokasi/pengguna).
- **Kunci ditegakkan server-side**: create/PUT/PATCH/DELETE/batch-update/
  bulk-delete/import (+ hapus kegiatan) → **423 "Kegiatan sudah disahkan dan
  terkunci"**; frontend menampilkan banner tersegel dengan tiket dan
  menyembunyikan edit/hapus/import/batch/FAB; antrian menampilkan 423 dengan
  jelas pada simpanan background.
- **Kartu Inventarisasi**: `GET /assets/kartu-inventarisasi` per
  `kode_register` atau `asset_code`+`NUP` → riwayat lintas kegiatan; dialog
  lazy dari header form edit & aksi baris tabel desktop.
- **QR**: hasil scan berawalan `#` dipakai verbatim sebagai kode_register;
  kartu cetak kini memuat QR asli berisi `#{kode_register}` (ReportLab
  QrCodeWidget — tanpa dependensi baru, fallback placeholder).

## [#26] Foto sebagai URL streaming cacheable + ruang teks baris maksimal — 2026-07-04

- **Media tidak lagi base64-in-JSON**: `GET /assets/{id}/photos/{i}` mendukung
  `?thumb=1` (thumbnail tersimpan per foto, generate on-the-fly untuk aset
  lama); ketiga endpoint streaming media mengirim `Cache-Control: private,
  max-age=86400` + ETag berbasis versi (304 If-None-Match).
- **Form edit tanpa roundtrip `/media`**: strip foto dibangun dari URL
  thumbnail per-index (`?thumb=1&v={version}`) dari `photo_count`/`version`
  fetch ringan — tiap `<img>` lazy-load progresif & ter-cache browser
  (`?v=` mem-bust cache setelah tiap edit); lightbox render foto pertama
  begitu byte-nya tiba (fallback data-URI dipertahankan).
- **UI list**: batas lebar keras (120/60/80px) kartu mobile dihapus —
  kategori/lokasi/eselon kini flex `min-w-0` (teks penuh tampil, ellipsis
  hanya saat benar-benar sempit); kolom Eselon/Lokasi tabel desktop xl
  berubah dari `w-20` tetap ke `flex-1 min-w-0` proporsional.

## [#25] Perbaikan offline: form edit dari cache + guard photo_ops destruktif — 2026-07-04

- **Edit offline berfungsi**: form edit kini terinisialisasi dari baris cache
  (snapshot offline) saat `GET /assets/{id}` tak terjangkau — dulu hanya toast
  error dan form kosong tak bisa disimpan. Simpan lewat PATCH diff
  non-destruktif dengan `If-Match` dari versi baris cache; notice amber bahwa
  foto/checklist penuh butuh koneksi. Error server nyata (404/401) tetap
  lewat jalur error eksplisit.
- **Guard data-loss laten**: bila media belum termuat, menambah foto tidak
  lagi mengirim `photo_ops keep:[]` yang menghapus semua foto lama
  server-side (`mediaLoadedRef` + `_photoCount` mempertahankan foto existing
  per index).
- Offline tanpa/kadaluarsa snapshot: pesan actionable ("Aktifkan Mode
  Inventarisasi saat online…") alih-alih "Gagal memuat data"; progress bar
  inventarisasi menampilkan angka terakhir yang diketahui per kegiatan
  (bukan 0/0).

## [#24] Laporan resmi: satu sistem desain rapi & profesional — 2026-07-04

Kedelapan laporan resmi ReportLab (Berita Acara, SPTJM, Surat Koreksi, DBHI ×6,
RHI, BAHI, SP Hasil, SP Pelaksanaan) kini memakai **satu sistem desain bersama**
(isi/teks hukum tidak diubah): blok judul+nomor seragam di bawah kop; gaya tabel
tunggal (header abu muda tebal, grid tipis, header berulang tiap halaman, zebra
lembut untuk DBHI/RHI, angka rata kanan, baris total tebal); blok tanda tangan
seragam (nama tebal bergaris bawah + NIP); **footer tiap halaman** (nama laporan
+ "Halaman X"); margin & tipografi Helvetica konsisten. Perbaikan nyata ikut:
sel NIP/nama panjang kini membungkus (dulu meluber), label total tak lagi patah
di tabel kosong. Laporan eksekutif tidak disentuh (sudah baik).

## [#23] Cache baca offline: mode inventarisasi berfungsi penuh tanpa koneksi — 2026-07-04

- **Snapshot data kegiatan** (proyeksi list + thumbnail, tanpa foto penuh) ke
  IndexedDB saat mode inventarisasi ON — sinkron **delta** via `updated_at`
  (endpoint ber-auth `GET /assets/offline-snapshot`, per-halaman 1000).
- **Saat offline**: daftar/cari/filter/sort dilayani dari cache lokal dengan
  banner "menampilkan data tersimpan (terakhir sinkron …)"; edit tetap lewat
  antrian persisten dan ikut di-upsert ke cache; lock dilewati optimistik
  (OCC menangkap konflik saat sinkron).
- **Online kembali**: flush antrian → delta-sync → data live.
- **Keamanan**: snapshot per user+kegiatan; dihapus saat logout manual & saat
  user berbeda login di perangkat sama (auto-logout 401/idle sengaja TIDAK
  menghapus — melindungi data lapangan); TTL 7 hari; `storage.persist()`.
- **Service worker**: precache app-shell agar aplikasi bisa dibuka cold-start
  saat offline.

## [#22] Tindak lanjut pematangan: kompresi offline, reachability, presence, WS auth — 2026-07-04

- **Kompresi foto offline**: bila server kompresi tak terjangkau/offline, foto
  dikompres lokal via canvas (1920px, q0.85) — base64 mentah hanya bila canvas
  gagal; berlaku di create, edit, dan foto checklist. Validasi pra-simpan
  dilewati saat offline (backend tetap memvalidasi saat sinkron).
- **Ping reachability**: `GET /api/health` baru; status online & auto-flush
  antrian diverifikasi dulu (timeout 3 dtk, retry 10 dtk) — Wi-Fi tanpa uplink
  tidak lagi mengaku online.
- **Presence lintas-worker**: daftar user online = gabungan snapshot semua
  worker via event bus (snapshot join/leave + periodik 30 dtk, kadaluarsa 60
  dtk, konvergensi cepat saat kontak pertama).
- **Autentikasi WebSocket**: koneksi WS wajib JWT (`?token=`); identitas
  diambil dari token, bukan parameter klien; token invalid ditutup kode 4401
  tanpa reconnect-loop.

## [#21] Pematangan kolaborasi & offline (hasil review menyeluruh) — 2026-07-04

Review mendalam stack kolaborasi + offline menemukan beberapa cacat serius;
semuanya diperbaiki:

- **Antrian simpan kini persisten (IndexedDB)** — sebelumnya hanya di RAM:
  app ditutup/di-logout (401) = semua simpanan offline **hilang**. Kini
  ter-rehydrate saat app dibuka lagi (baris + tombol retry muncul kembali)
  dan **auto-flush saat online kembali**. Indikator "N menunggu sinkron" &
  tombol Sync kini terhubung ke antrian sungguhan (dulu ke antrian mati).
- **Create gagal tidak menghapus barisnya lagi** — baris tetap tampil dengan
  status gagal + retry; hilang hanya lewat dismiss eksplisit.
- **Konflik 409 tidak lagi mengunci baris permanen di desktop** — status
  bersih otomatis (4 dtk), baris bisa diedit ulang; retry konflik memakai
  versi terbaru + idempotency key baru (dulu selalu 409 lagi selamanya).
- **Simpan ganda ke aset yang sama diserialisasi** — tak ada lagi 409 buatan
  sendiri saat save-cepat dua kali pada baris yang sama.
- **WebSocket**: reconnect kini melakukan satu catch-up refetch (event yang
  terlewat tidak hilang), tidak pernah menyerah permanen (backoff s/d 60 dtk),
  tab yang kembali visible + basi ikut refetch; refetch akibat event rekan
  di-debounce 2 dtk (anti badai refetch N×N saat banyak user menyimpan).
- **Backend**: TTL idempotency 5 menit → 24 jam (jeda offline realistis);
  TTL row-lock 300 dtk → 60 dtk (crash membebaskan baris ≤1 menit); broadcast
  unlock hanya setelah unlock DB sukses; bug fallback service-worker diperbaiki.

Tindak lanjut terdokumentasi (belum dikerjakan): kompresi foto client-side
saat offline, ping reachability (bukan hanya `navigator.onLine`), presence
lintas worker, autentikasi WebSocket, perampingan payload thumbnail per view.

## [#20] Toggle kolom di laporan Barang Serupa + progres unduhan seragam — 2026-07-04

- **Laporan Eksekutif per Barang Serupa kini ikut toggle kolom tambahan**
  (SPM/Perolehan/Kontrak/BAST/Supplier/S-N): nilai unik antar anggota kelompok
  ditampilkan ringkas di bawah Nama Barang (maks 3 + "+N lainnya"); param
  `detail_fields` yang sama dengan laporan data aset.
- **Progres unduhan seragam di seluruh aplikasi**: helper baru
  `downloadFileWithProgress` (toast: "Mengunduh … 2,4 MB (47%)"; tanpa persen
  bila server tak mengirim total; format KB/MB Indonesia) dipakai di **11 titik
  download**: export CSV/XLSX, laporan eksekutif + data per halaman + Barang
  Serupa, LHI/RHI/BAHI/SP/dokumen pendukung, 6 jenis DBHI, batch ZIP, laporan
  satker, template import CSV/XLSX, dan unduhan InfoPage (PPT/DOCX).
- Pengecualian sengaja: unduhan **backup** tetap anchor native — pendekatan
  blob terdokumentasi gagal di produksi untuk file ratusan MB; progres sudah
  ditampilkan UI unduhan browser.

## [#19] Lembar Inventarisasi Lapangan eksklusif (redesign) — 2026-07-04

Menggantikan panel "Aksi Cepat" tempelan (#18) dengan **tampilan input lapangan
eksklusif** (`InventoryFieldSheet`) yang mengambil alih seluruh body form saat
mode inventarisasi + edit aset:

- **Header identitas sticky** (read-only): kode aset mono + badge NUP + nama +
  penghitung "X/Y" — petugas memverifikasi barang, bukan mengetik ulang.
- **Kartu langkah bernomor** dengan bahasa visual seragam: 1 Status
  Inventarisasi (segmented 2×2), 2 Kondisi Fisik (segmented 3), kartu
  kondisional beraksen amber muncul sesuai status (Detail Tidak Ditemukan /
  Berlebih / Sengketa / Tindak Lanjut Rusak Berat — field sama persis dengan
  form penuh), 3 Foto (strip thumbnail + Kamera/Galeri), 4 Lokasi & Pengguna
  (+ baris GPS + salin dari aset sebelumnya), 5 Stiker, 6 Catatan (lipat).
- **Footer sticky**: "Simpan & Lanjut →" besar (jalur navigationIntent yang
  sama), Simpan, dan "Form Lengkap" (semua field tetap bisa diakses; banner
  "← Kembali ke Mode Cepat" di form penuh).
- Field meja (harga, SPM, kontrak, dsb.) tidak tampil di alur cepat.
- Logika simpan/validasi tidak diduplikasi — sheet murni presentasional di
  dalam `<form>` AssetForm yang sama.

## [#18] Mode Inventarisasi Lapangan: progres, aksi cepat, scan QR, GPS cache — 2026-07-04

Paket fitur untuk mempercepat input di lapangan (offline maupun kolaborasi online):

- **Bar progres inventarisasi** (`InventoryProgressBar`, tampil saat mode
  inventarisasi aktif): "Diinventarisasi X / Y" + persentase (refetch otomatis
  setelah save background & tiap 60 dtk), chip filter cepat **Belum / Ditemukan
  / Semua**, indikator offline + "N menunggu sinkron", dan badge **"N dikerjakan
  rekan"** (dari row-lock sesi lain).
- **Aksi Cepat Inventarisasi** di atas form (mode inventarisasi, saat edit):
  tombol besar sekali-ketuk untuk Status (Ditemukan/Tidak Ditemukan/Berlebih/
  Sengketa) dan Kondisi (Baik/RR/RB). Memakai logika clearing yang sama dengan
  Select lama (field klasifikasi ikut bersih saat status berganti).
- **"Salin dari aset sebelumnya"**: lokasi/eselon/pengguna aset yang baru
  disimpan tersimpan di `localStorage`; satu ketukan mengisi field yang masih
  kosong (tidak pernah menimpa isian).
- **Scan QR/barcode** (`QrScanButton` di samping kolom cari): kamera belakang +
  `BarcodeDetector`; hasil scan diekstrak (URL / `kode|NUP` / teks mentah) lalu
  masuk ke pencarian multi-kolom. Tombol tersembunyi otomatis di browser yang
  tak mendukung. Catatan: QR pada kartu cetak backend masih placeholder —
  scanner ini menyasar stiker bersistem eksternal (SIMAK-BMN dsb.).
- **Cache GPS**: fix terakhir (<5 menit) dipakai instan saat form butuh
  koordinat, lalu diperbarui di background — GPS indoor tidak lagi menahan
  input. (Tombol kamera langsung sudah ada sebelumnya — tidak diubah.)

## [#17] Laporan: Kop Surat di semua laporan resmi + Eksekutif per Barang Serupa + kolom detail opsional — 2026-06-16

- **Kop Surat (issue 6):** helper `_kop_surat_flowables()` baru — logo instansi
  (dari pengaturan "Sampul") + nama instansi/unit/alamat + garis ganda klasik —
  kini tampil di **semua 8 laporan resmi ReportLab**: Berita Acara, SPTJM,
  Surat Koreksi, DBHI (6 jenis), RHI, BAHI, SP Hasil, SP Pelaksanaan. Kop
  mengikuti pengaturan yang bisa diubah di panel "Sampul" (`ReportSettingsEditor`).
- **Laporan Eksekutif per Barang Serupa (issue 8):** endpoint & tombol unduh
  baru — aset dikelompokkan persis seperti panel Barang Serupa (kunci 6 kolom),
  termasuk aset tunggal, sehingga **total unit = total seluruh aset**. Foto
  perwakilan = anggota dengan **NUP terkecil**; NUP ditampilkan sebagai rentang
  ringkas ("1-3, 5, 7"). Template baru `executive_grouped.html`.
- **Kolom detail opsional (issue 9):** 6 toggle (SPM, Perolehan, Kontrak, BAST,
  Supplier, S/N) di bagian Laporan Eksekutif — jika aktif, ditambahkan rapi ke
  kolom "Kondisi & Status" laporan data aset (param `detail_fields`, tersimpan
  di localStorage).

## [#16] UX batch: input tak lagi terhapus, skeleton, auto-logout, dll — 2026-06-16
`80ac0e2`

- **Issue 1 (kritis):** ketikan hilang saat save background selesai → timer basi
  `handleFormClose` kini hanya menutup edit miliknya; init form di-key by id.
- **Issue 2/4/5:** skeleton loading (komponen `ListLoadingSkeleton`) untuk ganti
  page size / pindah halaman / filter / sort; refresh background tetap senyap.
- **Issue 3:** import — sel `status` kosong → "Aktif" (dan `condition` → "Baik").
- **Issue 7:** interceptor 401 → logout + redirect login; idle 30 menit → logout.
- **Issue 10:** kategori ber-label "dummy" → NUP otomatis via `GET /assets/next-nup`.

## [#15] Lightbox: efek glass kembali + panel info adaptif tema — 2026-06-16
`fba598f` — latar `bg-black/40` + blur; panel `bg-white/70`/`dark:bg-slate-900/70`;
badge dua-warna kontras di kedua mode.

## [#14] Lightbox: panel info gelap solid — 2026-06-16
`f4943c3` — digantikan oleh #15 (permintaan: efek glass dipertahankan).

## [#13] Lightbox: teks info tak terbaca di light mode — 2026-06-16
`97a988f` — `bg-black/92`/`bg-white/8` (step opacity non-standar) tidak
ter-generate Tailwind → overlay tak pernah gelap. Diganti step standar.

## [#11] Stats: tombol toggle Inventarisasi ringkas & seragam — 2026-06-16
`a3fdf5c`

- **Masalah:** di bar stat compact (tablet / HP-landscape, sm–lg / ≤1023px),
  kartu toggle "Inventarisasi" lebih **tinggi** dari kartu stat lain karena
  `Switch` (Radix `<button>`) dipaksa 44×44 oleh aturan global di atas.
- **Perbaikan (`StatsBar.jsx`):**
  - Hapus label teks "Inventarisasi" → cukup tombol toggle (hemat ruang);
    aksesibilitas dijaga via `aria-label` + `title`.
  - `min-h-0 min-w-0` pada `Switch` → kembali ke ukuran natural (`h-5 w-9`).
  - Baris compact dibuat `items-stretch` → kartu toggle setinggi kartu stat lain,
    switch di tengah.

## [#10] Stats: ruang lebih untuk "Total Nilai" di semua ukuran — 2026-06-16
`091ea1c`

- **Masalah:** angka rupiah ("Total Nilai") jauh lebih panjang dari kartu jumlah,
  tapi mendapat lebar yang sama → terasa sempit.
- **Perbaikan (`StatsBar.jsx`):**
  - Desktop (lg+): grid `grid-cols-4` → `grid-cols-[1fr_1.6fr_1fr_1fr]`
    (kolom Total Nilai **1.6×**); `min-w-0` agar nilai sangat panjang membungkus,
    bukan meluber.
  - Tablet/HP-landscape (sm–lg): kartu Total Nilai `flex-[1.7]` vs `flex-1`,
    plus `min-w-0` + `truncate` sebagai pengaman.
  - HP portrait (<sm): kartu stat memang tidak ditampilkan (hanya toggle).

## [#9] Kegiatan: badge status tidak lagi menutupi nomor surat — 2026-06-16
`2526f3a`

- **Masalah:** di ≤1023px, ribbon status (`Belum Dimulai`/`On Going`/…) — sebuah
  `<button>` `absolute top-0 left-0` — dipaksa setinggi 44px oleh aturan global,
  sehingga melewati jarak aman `pt-5` konten dan **menutupi baris nomor surat**.
- **Perbaikan (`ActivitySelectionPage.jsx`):** tambah `min-h-0 min-w-0 leading-none`
  pada tombol ribbon → kembali ke tinggi natural (~16px), nomor surat tampil penuh.

## [#8] List mobile: baris menyatu + "Barang Serupa" jadi batas scroll — 2026-06-16
`2170fd8`

- **Masalah A:** tiap kartu (`AssetMobileCard`) memakai `rounded-lg mb-1.5` → ada
  celah 6px di antara setiap baris.
- **Masalah B:** `VirtualizedMobileCards` berada di alur halaman biasa, jadi
  seluruh list (dan panel di atasnya, termasuk *Barang Serupa*) ikut ter-scroll
  hilang ke atas.
- **Perbaikan:**
  - `AssetMobileCard.jsx`: buang `rounded-lg` + `mb-1.5` → list rapi & menerus
    (pembatas baris tetap dari `border-y`).
  - `VirtualizedMobileCards.jsx`: bungkus dengan container scroll tinggi-tetap
    **sama dengan galeri** (`h-[calc(100dvh-140px)] sm:h-[calc(100dvh-280px)]`),
    dan `IntersectionObserver` infinite-scroll di-`root`-kan ke container itu →
    saat scroll, "Barang Serupa" mendarat di atas sebagai batas; muat-lebih-banyak
    tetap jalan.

## [#7] Galeri: ikon aksi kartu rapi & "Hapus" selalu tampil di HP — 2026-06-16
`8b2a829`

- **Masalah:** footer kartu galeri berisi 5 tombol ikon; aturan global memaksa
  tiap `<button>` ≥44px → 5×44=220px ke kartu ~158px → baris meluber dan
  `overflow-hidden` kartu **memotong ikon Hapus**. Terjadi di semua lebar HP
  (termasuk 375px).
- **Perbaikan:**
  - `AssetGalleryCard.jsx`: tiap tombol ikon footer `min-w-0 min-h-0`
    (+ `flex-shrink-0` pada ikon, `overflow-hidden` & jarak rata pada baris,
    hover state lembut) → strip rapi, semua ikon tampil.
  - `AssetGalleryView.jsx`: seed jumlah kolom **mobile-first** dari lebar viewport
    (default 2) → hilangkan "kedip" grid 4 kolom sesaat saat load.

## [#6] Pengamanan auth + integritas data — 2026-06-16
`e8e1074`

- **Auth endpoint destruktif:** endpoint yang sebelumnya jalan **tanpa verifikasi
  token** kini di-gate (frontend sudah mengirim `Authorization: Bearer` via
  interceptor axios global):
  - `require_user`: `POST /import`, `DELETE /assets/bulk-delete/{id}`,
    `PUT /assets/batch-update`, `POST /categories/import-bulk`,
    `POST /categories/import`.
  - `require_admin`: semua `/users/*` dan `DELETE /system/reset-all`
    (catatan: `change-password`/`change-role` sebelumnya tanpa auth sama sekali).
- **Idempotency race:** `reserve_idempotency_key()` mengklaim `Idempotency-Key`
  secara atomik sebelum bekerja (request kedua dengan key sama → `409`).
  **Fail-open** saat error infra; reservasi basi (>30s) bisa diambil alih.
- **Merge checklist:** PATCH `document_checklist` dulu mencocokkan item by-name via
  dict (item duplikat/kosong bisa saling tertukar / kehilangan foto). Sekarang
  mengonsumsi item existing by-name **berurutan** (deque) → duplikat aman.

## [#5] Testing + perbaikan audit log & broadcast batch — 2026-06-16
`e58e00d`

- **Audit log:** `compute_changes` dulu hanya mencatat penyelesaian dokumen saat
  **jumlah** item checklist berubah → centang/uncentang item yang sudah ada (jumlah
  tetap) tidak tercatat. Diperbaiki + test regresi.
- **Batch update WebSocket:** `batch.py` memanggil `notify_asset_change` dengan 1
  dict, padahal signature 5 argumen → `TypeError` (ditelan) sehingga viewer lain
  tak dapat refresh realtime setelah batch edit. Kini dipanggil benar.
- **Test:** tambah `backend/check_pure_logic.py` (auth hashing+JWT, `decode_data_url`,
  thumbnail/`_prepare_image`, `compute_changes`, formatter export, model pydantic,
  template Jinja2).

## [#4] Mobile: toggle mode ikon + scroll galeri berhenti di "Barang Serupa" — 2026-06-16
`b6e79fc`

- **StatsBar (HP):** toolbar atas diganti **satu tombol toggle ikon** yang jelas
  (Dashboard ↔ Inventarisasi).
- **Galeri:** offset window-scroll mobile diperbesar (170 → 140) supaya saat
  discroll ke bawah, "Barang Serupa" mendarat di dekat atas dan galeri mengisi
  sisanya. (Mekanisme ini kemudian disamakan untuk list mode di #8.)

## [#3] GPS opsional saat "Belum Diinventarisasi" + galeri mobile lebih padat — 2026-06-16
`546cce8`

- Tidak lagi mewajibkan titik GPS ketika status inventarisasi masih
  "Belum Diinventarisasi".
- Galeri mobile dibuat lebih padat (lebih banyak kartu per layar).

## [#2] Galeri mobile: densitas + popup foto (portal, scroll-lock, tombol) — 2026-06-16
`161e2d6`

- Perbaikan densitas galeri mobile dan popup foto: render via portal,
  penguncian scroll saat popup terbuka, serta tombol-tombolnya.

## [#1] Inisialisasi aplikasi AMAN — 2026-06-16
`36f8019`

- Menambahkan aplikasi AMAN secara lengkap, memperbaiki timeout export XLSX, dan
  merapikan repo.

---

## Peta file UI yang sering disentuh

| Area | File |
| --- | --- |
| Kartu galeri (footer ikon, dll.) | `frontend/src/components/assets/AssetGalleryCard.jsx` |
| Galeri (grid virtual, kolom, scroll) | `frontend/src/components/assets/AssetGalleryView.jsx` |
| Kartu list mobile | `frontend/src/components/assets/AssetMobileCard.jsx` |
| List mobile (scroll/infinite) | `frontend/src/components/assets/VirtualizedMobileCards.jsx` |
| Bar statistik + toggle inventarisasi | `frontend/src/components/assets/StatsBar.jsx` |
| Halaman pemilihan kegiatan (badge status) | `frontend/src/pages/ActivitySelectionPage.jsx` |
| Aturan global mobile (tap-target 44px) | `frontend/src/index.css` (≤1023px) |

## Breakpoint (Tailwind, lihat `frontend/tailwind.config.js`)

`xs 0` → `sm 640` → `md 768` → `lg 1024` → `xl 1280` → `2xl 1536`.
Aturan tap-target 44px aktif pada **≤1023px** (di bawah `lg`).
