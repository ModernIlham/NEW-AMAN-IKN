# Changelog — AMAN IKN

Catatan perubahan aplikasi **AMAN** (Aplikasi Manajemen Aset Negara) IKN, dari
awal pengembangan di branch ini hingga rilis terakhir. Diurutkan dari yang
**terbaru** ke yang **terlama**. Setiap entri merujuk ke nomor Pull Request
(`#n`) dan commit pada branch `main`.

> Format tanggal: `YYYY-MM-DD`. Semua perubahan UI di bawah sudah di-`yarn build`
> (craco) hingga sukses sebelum di-merge.
>
> **Catatan penomoran:** sejak entri `[#276]`, nomor `[#N]` pada judul entri
> = **nomor PR + 2** (bergeser karena dua nomor PR hangus). Contoh: entri
> `[#614]` = PR #612. Tautan PR yang disebut DI DALAM badan entri tetap
> memakai nomor PR asli.

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

### Pengecualiannya pun bisa kelewat lebar (`[#670]`)

Aturan pengecualian yang MENGECILKAN pun punya jebakan yang sama bila
selektornya terlalu longgar. Contoh nyata: pengecualian 36px untuk kontrol
Leaflet ditulis `.leaflet-control a`, padahal kotak atribusi
(`.leaflet-control-attribution`) dan bar skala JUGA `.leaflet-control` — jadi
`line-height: 36px` ikut mengenai tautan "Leaflet | © OpenStreetMap" dan
membengkakkannya jadi pita putih 127×36 px di sudut peta.

> Saat menulis pengecualian untuk kontrol peta, **sebut kontrol tombolnya, bukan
> semua kontrol**: `.leaflet-control:not(.leaflet-control-attribution):not(.leaflet-control-scale) a`.
> `line-height` tetap berlaku pada elemen inline meski `min-height`/`width` tidak
> — itulah kenapa gejalanya lolos dari dugaan pertama.

---

## [#690] Audit lanjutan modul jarang tersentuh — 14 temuan ditutup — 2026-08-02

Sapu berburu bug atas modul di luar jangkauan enam gelombang audit
sebelumnya (PR #682): wasdal, pemanfaatan, penilaian, perencanaan,
pemeliharaan, pelaporan, persuratan. 14 temuan terverifikasi kode
(3 dibuktikan menjalankan ReportLab/Pydantic/FastAPI langsung):

- **Wasdal**: 3 PDF di-escape ('<' di uraian dulu = BA 500 permanen;
  `<img src=http>` = SSRF buta) + `trustedSchemes=['data','file']` global;
  `catat_penertiban` kini ber-`pastikan_akses_aset`.
- **Infinity/NaN** ditolak di gerbang Pemanfaatan/Perencanaan/Penilaian
  (`math.isfinite`) — dulu lolos `ge=0`/`gt=0` lalu mematikan GET register
  permanen & meracuni `nilai_wajar_terakhir` master.
- **Penilaian**: transisi SAKTI ber-kompensasi CAS (gagal di tengah tak
  lagi mengunci register tanpa jurnal 204/205); referensi masa manfaat &
  standar SBSK (nasional) kini super-admin saja + log_audit.
- **Perencanaan**: seeding SBSK idempoten (anti tabel ganda saat balapan);
  XLSX RKBMN anti injeksi formula (`strings_to_formulas/urls` off).
- **Pemeliharaan**: nomor BA manual dicek duplikat + geser counter `$max`;
  pratinjau kapitalisasi ter-scope satker. **Pelaporan**: filter tulis
  tenggat `_q_periode`. **Persuratan**: ganti kode klasifikasi ditolak
  selagi masih dirujuk pemetaan.

Bersih setelah diperiksa: penganggaran, peta kolaborasi publik, penomoran
atomik, escape PDF pemeliharaan, validasi tanggal. Verifikasi: compileall
bersih, 1407 uji unit lulus.

---

## [#689] Optimalisasi VPS (indeks komposit assets) & aturan main logging — 2026-08-02

Dari analisis beban VPS pemilik — CPU ±51% konstan di KVM 2 (PR #681):

- **5 indeks komposit `assets`** — `activity_id` × condition/location/
  eselon1/eselon2/status (eselon2 dulu tanpa indeks); kombinasi filter yang
  mendominasi beban mongod kini selesai di indeks. Terpasang otomatis saat
  deploy.
- **`docs/OPTIMASI-VPS.md`** — diagnosis sumber CPU (3 tersangka + blok
  perintah), swap 4 GB + swappiness 10, WiredTiger 2 GB + profiler slowms,
  keamanan dasar, prioritas 1–7, dan nasihat OLTP/OLAP: Debezium→Kafka→
  ClickHouse ditolak untuk skala/mesin ini — tangga bijak: indeks+cache →
  replika hidden → DuckDB → CDC hanya bila jutaan baris.
- **ATURAN MAIN LOGGING** di `log_setup.py`: JSON-lines jadi DEFAULT,
  keluaran ke stdout, dan filter REDAKSI baru (password/token/secret/
  api_key/otp, Authorization skema+kredensial, JWT, NIK 16 digit sisakan 4
  digit — NIP 18 digit & kode satker tak tersentuh; argumen %s ikut
  tersensor). `docs/LOGGING.md`: keenam aturan + resep journalctl/jq +
  kebijakan centralized logging (journald cukup utk 1 VPS; dasbor →
  Alloy + Grafana Cloud, bukan Loki self-hosted di mesin aplikasi).

Verifikasi: compileall bersih, 1407 uji unit lulus (6 uji redaksi baru).

---

## [#688] Penyusutan & mutasi selaras SIMAN V2 — umur = sisa semester — 2026-08-02

Investigasi selisih penyusutan & mutasi vs ekspor nyata SIMAN V2, 175 baris
(PR #680). Mesin penyusutan TERBUKTI benar (cocok 175/175 dengan SIMAN);
selisihnya dari dua cacat integrasi:

- **Racun referensi masa manfaat.** Kolom "Umur Aset" SIMAN = SISA masa
  manfaat dalam SEMESTER (bukti: 175/175 vs 0/175 bila dibaca tahun), tapi
  alur "SIMAN menang" membacanya TAHUN → db.masa_manfaat teracuni (30801 =
  "15 th" padahal KMK 8 th). Kini masa manfaat DIDERIVASI dari identitas
  garis lurus (`masa_sem = perolehan × sisa / nilai buku`, validasi
  bulat-genap-1..60) — diuji pada file asli: 9/9 kelompok = tabel KMK.
  Pemulih entri lama: `scripts/perbaiki_masa_manfaat_siman.py`.
- **Dua mesin mutasi tak terhubung.** Basis mutasi LBKP/CaLBMN/LBP kini
  tanggal PEROLEHAN (fallback pencatatan) — aset lama yang baru diimpor
  masuk Saldo Awal, bukan "Mutasi Tambah"; draft impor SIMAN berjurnal 100
  otomatis; "terapkan nilai SIMAN" atas harga perolehan berjurnal 204/205
  (padanan sejati kolom "Nilai Mutasi" SIMAN); kolom Nilai Mutasi &
  Perolehan Pertama kini ikut diimpor sebagai referensi.

Verifikasi: 1401 uji unit lulus (6 uji baru); derivasi diuji empiris
end-to-end pada ekspor SIMAN asli.

---

## [#687] Isolasi satker aset pemegang & PSP — stempel efektif + kop per-satker — 2026-08-02

Laporan pemilik: data lintas satker tampil di halaman aset pemegang bagian
Penetapan Status Penggunaan (PR #679). Akar: dokumen buatan super-admin pusat
tanpa "Satker Aktif" terstempel `kode_satker` kosong — dan scope lunak sengaja
meloloskan "" (era lama) — sehingga tampil di register SEMUA satker.

- **Stempel efektif** `kode_satker_efektif_dari_aset` di POST PSP / idle /
  proses / BAST (+ surat booking otomatisnya): dokumen user lintas-satker
  diderivasi dari kegiatan aset yang dirujuk, tak pernah lagi "".
- **Kop per-satker** di PDF "Daftar Barang yang Digunakan" + default PIHAK
  KESATU BAST dari kop satker (dulu selalu global).
- `status_kepegawaian_by_nip` ter-scope satker; cek duplikat tiket idle
  ter-scope (tutup oracle 409); 6 sumber Timeline aset diseragamkan
  (`_q_satker_lunak`).
- `scripts/backfill_kode_satker_dokumen.py` merapikan dokumen lama yang
  telanjur kosong (dry-run default, `--terapkan` untuk menulis).

Verifikasi: compileall bersih, 1400 uji unit lulus.

---

## [#686] Toolbar aset tanpa geser samping + popup Struktur Organisasi rapi di HP — 2026-08-02

Dua perbaikan tampilan dari umpan balik pemilik (PR #678):

- **Deretan filter/aksi toolbar aset tak pernah lagi geser samping.** Breakpoint
  Tailwind melihat viewport, bukan kontainer: di halaman kegiatan (panel form
  kiri ~460px) viewport 1366px memakai label `xl` padahal lebar efektif toolbar
  ~880px → baris `flex-nowrap` meluber 1209/878px (Cetak Kartu & Stiker
  tersembunyi di balik scroll). Kini dua grup (filter kiri, aksi rata kanan)
  dalam induk `flex-wrap` — saat sempit grup aksi turun utuh ke baris kedua.
  Terbukti Playwright (CSS build produksi): 0 geser samping di 700/800/880/1326px.
- **Popup Struktur Organisasi (Master Pegawai) rapi di HP.** Dialog diperlebar
  + padding hemat, indentasi pohon 8px/jenjang di HP, nama unit melipat utuh
  (`break-words`, bukan "…"), pill jumlah pegawai cukup angka di HP, badge
  eselon & panah tak tergencet (`flex-shrink-0`).

Verifikasi: eslint bersih, `yarn build` sukses, uji numerik Playwright.

---

## [#685] Audit total gel.6 — validasi perolehan: Infinity & tanggal WIB — 2026-08-02

Gelombang penutup: dua cacat validasi pada pencatatan perolehan Pengadaan.

- **`Infinity`/`NaN` diterima sebagai jumlah/harga.** Token JSON `Infinity`
  di-parse Starlette menjadi `float('inf')` dan LOLOS batas `gt`/`ge` Pydantic —
  lalu meracuni register: ekspor CSV & penjumlahan nilai jadi tak terhitung,
  PDF 500, catat-semua berhenti separuh jalan. `BarangIn` kini menolak nilai
  tak-hingga di gerbang (`field_validator` + `math.isfinite`). Diuji: `inf` &
  `nan` keduanya ditolak.
- **Tanggal BAST hari ini ditolak tiap pagi (00:00–06:59 WIB).** Batas "tak
  boleh di masa depan" memakai tanggal UTC yang tertinggal 7 jam dari WIB,
  sehingga BAST bertanggal hari ini keliru dianggap masa depan pada dini hari.
  Kini memakai `today_wib()` — sama dengan register persediaan.

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus, penolakan
Infinity/NaN dibuktikan lewat uji model langsung.

---

## [#684] Audit total gel.5 — dokumen resmi: privasi NIK & ketahanan teks — 2026-08-02

Gelombang kelima: privasi identitas dan ketahanan PDF terhadap teks bebas.

- **NIK almarhum tercetak mentah di BAST** (`bast.py`). Pasal DASAR
  PENGEMBALIAN mencetak "(NIP {nomor})" apa adanya untuk pemegang yang
  meninggal — menembus aturan privasi yang ditegakkan di SELURUH blok tanda
  tangan dokumen (NIK Non-ASN tak dicetak). Kini nomor identitas almarhum
  melewati `deteksi_identitas`: NIK dilewati, NIP/NRP memakai label pintar.
- **Teks bebas meruntuhkan PDF resmi (500 permanen).** Nama penyedia,
  keterangan, nama barang — dan bahkan nama instansi/satker di KOP surat —
  diinterpolasi mentah ke `Paragraph` ReportLab. Satu karakter `&` atau `<`
  memutus parser XML-nya dan menggagalkan seluruh dokumen setiap kali dibuka.
  Kini semua field teks bebas di-`escape`: di LPB (`persediaan.py`) dan di
  helper KOP bersama (`reports.py`) yang dipakai LHI/BAST/LPB/LBP dan semua
  laporan lain — satu tambalan melindungi seluruh generator.

Diverifikasi empiris: LPB dengan penyedia `"PT A & B <Persero>"`, keterangan
`"100% <lengkap> & baik"`, dan kop `"OIKN <IKN> & Co"` kini dirender tuntas
(3547 byte) — sebelumnya `Parse error: saw </para>`.

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus, render PDF
bermusuh dibuktikan.

---

## [#683] Audit total gel.4 — cascade & FK yatim saat hapus — 2026-08-02

Gelombang keempat: penghapusan yang meninggalkan referensi menggantung.

- **Hapus register perolehan tanpa cek anak** (`pengadaan.py`). `hapus_perolehan`
  melepas back-link aset saja, lalu menghapus — padahal register yang barangnya
  sudah masuk stok/aset, atau sudah ber-BAST PPK-KPB, atau ditunjuk sebuah LPB,
  akan meninggalkan stok, jurnal Buku Barang, dokumen resmi, dan nomor surat
  sebagai anak yatim. Kini penghapusan **ditolak 409** untuk register yang sudah
  "hidup" (pola sama dengan penjaga hapus master persediaan); hanya register
  salah-input yang belum melahirkan apa pun yang boleh dihapus.
- **Hapus aset tak melepas back-link Pengadaan** (`assets.py`). `delete_asset`
  membersihkan blob GridFS & indeks, tapi `pengadaan.barang[].asset_id` yang
  menaut aset itu dibiarkan — register lalu mengklaim aset hantu. Kini tautan +
  snapshotnya dikosongkan di semua baris yang menyebut asset_id itu
  (`array_filters`, best-effort).

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus.

---

## [#682] Audit total gel.3 — stok persediaan: pecahan & idempotensi — 2026-08-02

Gelombang ketiga: dua cacat pada jalur "Daftarkan ke Persediaan" (`pengadaan.py`)
yang membuat **stok tak cocok dengan dokumen**.

- **Jumlah pecahan tetap diposting dengan nilai dibulatkan.** `jumlah =
  max(1, int(jumlah_asli))` LALU tetap `transaksi_masuk`: 2,5 → tercatat 2
  (0,5 lenyap dari stok), 0,5 → dibulatkan NAIK jadi 1 (mengarang stok) — dan
  pesan peringatannya bahkan salah ("dibulatkan ke bawah" untuk kasus naik).
  Angka stok jadi tak cocok dengan register/LPB. Kini baris pecahan/nol
  **DILEWATI** (tak diposting) dan dilaporkan gagal sungguhan; operator memecah
  baris atau mengubah satuannya.
- **Penanda `psd_item_id` dipersist sekali di akhir loop.** Seluruh array
  `barang` baru ditulis setelah loop selesai; bila proses mati / permintaan
  diulang di tengah, transaksi persediaan yang SUDAH terposting tak ber-penanda
  di DB → jalankan-ulang mempostingnya lagi (stok dobel). Kini penanda ditulis
  **posisional per-baris segera** setelah tiap `transaksi_masuk` sukses,
  sehingga baris yang sudah masuk langsung dilewati pada pengulangan.

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus.

---

## [#681] Audit total gel.2 — jurnal ganda & kapitalisasi terkunci — 2026-08-02

Gelombang kedua audit menyeluruh: tiga cacat jurnal ber-severity TINGGI yang
menghasilkan **uang salah di Buku Barang / CaLBMN** atau menghentikan alur
kapitalisasi. Semua diverifikasi ulang di kode; pola perbaikan seragam dengan
`terproyeksi` di `penggunaan.py`.

- **Kapitalisasi pemeliharaan terkunci "diposting" tanpa jurnal 202**
  (`pemeliharaan.py`). `purchase_price` disimpan SEBAGAI STRING di semua jalur
  create (AssetCreate `Optional[str]`, pengadaan/siman menulis `str(...)`).
  `POST /pemeliharaan/{id}/kapitalisasi` menandai CAS `kapitalisasi_diposting`
  DULU, lalu `$inc {"purchase_price": biaya}` — Mongo menolak `$inc` pada field
  string → 500. Akibatnya nilai aset tak bertambah, jurnal 202 tak terbit, tapi
  catatan sudah terkunci (retry 409 "sudah diposting"). Perbaikan: baca harga
  lama via `parse_harga`, tulis balik jumlahnya sebagai `$set` string, dan bila
  update/jurnal gagal LEPAS penanda CAS agar bisa diulang.
- **Jurnal 301 penghapusan ditulis tanpa syarat proyeksi** (`penghapusan.py`).
  Aset yang sudah keluar buku lewat register lain (tiket idle → 302) membuat
  `_proyeksi_master_penghapusan` mengembalikan False, tetapi 301 tetap ditulis.
  Karena penjaga anti-ganda `catat_mutasi_bmn` hanya per `(asset_id,
  kode_transaksi, ref_id)` dan ref-nya berbeda, kedua jurnal lolos → mutasi
  KURANG dobel. Kini 301 hanya ditulis bila proyeksi benar-benar men-tombstone.
- **Jurnal 303/301 pemindahtanganan mengabaikan hasil proyeksi per aset**
  (`pemindahtanganan.py`). `_proyeksi_master_pemindahtanganan` mengembalikan
  count yang diabaikan; loop jurnal menulis untuk SEMUA aset usulan walau
  sebagian sudah dihapus jalur lain — dobel KURANG pada alur Penghapusan↔PT
  yang justru dirancang saling tertaut (satu SK). Kini helper mengembalikan
  himpunan asset_id yang benar-benar diproyeksikan; jurnal hanya untuk itu.

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus.

---

## [#680] Audit total gel.1 — isolasi satker, auth template, jejak audit SAKTI — 2026-08-02

Gelombang pertama dari audit menyeluruh 10-dimensi (fan-out + verifikasi
adversarial per temuan). Wave ini menutup kebocoran lintas-satker & auth yang
paling langsung — semuanya diverifikasi ulang di kode sebelum disentuh.

- **Impor referensi SAKTI oleh super-admin membocorkan/menimpa satker lain.**
  `impor_referensi_sakti_pdf` mem-`scope_query_field_satker("")` untuk
  super-admin (kode_satker kosong) → melebar ke SEMUA satker: `terapkan=true`
  me-rename master ber-kode16 sama di setiap satker, dan item baru lahir
  ber-`kode_satker=""` (bocor ke semua). Kini satker efektif diambil dari PDF
  bila akun tak terikat satker; scope, update, dan stempel semuanya memakai
  satker itu; PDF tanpa kode satker ditolak.
- **LPB & nomor surat "Catat Semua" distempel satker PEMANGGIL, bukan
  perolehan.** Super-admin yang mencatat BAST satker lain menerbitkan LPB
  ber-`kode_satker=""` (tampil di semua satker) + nomor di deret global. Kini
  LPB & booking nomor memakai `kode_satker` milik perolehan (pola beku bast.py).
- **LPB gabungan bisa mencampur banyak satker.** Kini ditolak tegas bila
  perolehan terpilih berasal dari >1 satker; stempel & nomor ikut satker
  tunggal itu. `booking_nomor_lpb` menerima override `kode_satker`.
- **Template impor tanpa autentikasi.** `/templates/csv` & `/templates/xlsx`
  tak punya `Depends` sama sekali — endpoint pembaca-DB yang membocorkan daftar
  kategori satker ke siapa pun. Kini ber-`require_user` (frontend sudah
  melampirkan bearer token).
- **Impor SAKTI tak pernah teraudit.** `log_audit(request, _user, …)` mengoper
  argumen ke slot yang salah (`action`=Request, `activity_id`=user); `log_audit`
  menelan error encode diam-diam sehingga jejaknya hilang tanpa suara. Argumen
  dibetulkan + `kode_satker` diisi.

Verifikasi: `py_compile` bersih, 1397 uji unit backend lulus.

---

## [#679] Alat ukur peta benar-benar berfungsi + tombolnya hadir di tablet & PC — 2026-08-02

Laporan pemilik: alat ukur di peta tak bisa dipakai, dan tombolnya tak ada di
tablet/PC. Tiga cacat nyata ditemukan — yang pertama menjelaskan kenapa
alatnya terasa mati total:

1. **Listener klik tak pernah terpasang.** `useUkurPeta` memasang
   `map.on("click")` SEKALI saat mount dengan penjaga `aktifRef` di dalamnya —
   kelihatan hemat, tapi di kedua halaman peta si PETA BARU DIBUAT setelah
   data termuat (efek init berjalan belakangan). Saat efek listener berjalan,
   `mapRef.current` masih `null` → listener tidak pernah terpasang → ketukan
   di peta tak menambah titik sama sekali, selamanya. Kini listener dipasang
   SAAT MODE DIAKTIFKAN (peta pasti sudah ada — tombolnya baru bisa ditekan
   setelah peta tampil) dan dilepas saat mode mati.
2. **Tak ada pintu masuk di tablet/PC (Peta Aset).** Item "Alat Ukur" hanya
   hidup di menu gabungan HP (`sm:hidden`) — pola bug yang sama dengan "Gaya
   Marker" dulu. Kini ada tombol Ruler mandiri di toolbar (`hidden sm:flex`,
   label di xl+, amber saat aktif); HP tetap lewat menu gabungan.
3. **Klik kanan bentrok dengan "+Tambah aset".** Di Peta Aset, klik kanan =
   undo titik ukur (hook) SEKALIGUS membuka popup "+Tambah aset di sini"
   (handler init). Kini popup tambah-aset mengalah selama mode ukur aktif
   (`ukurOnRef`). Di Peta Kolaborasi, mode "tambah titik" dan alat ukur juga
   dibuat saling eksklusif — dua mode yang sama-sama memakan klik peta tak
   boleh hidup berbarengan.

Plus dua penyempurnaan pemakaian:
- Kelas `peta-ukur-aktif` di kontainer peta (dipasang hook): kursor
  crosshair + pane marker/popup dibuat tembus-klik — di peta padat pin,
  ketukan di atas pin kini tetap menanam titik ukur, bukan ditelan popup
  aset. Lapisan hasil ukur digambar `interactive: false`, tak terpengaruh.
- Backspace tak lagi membajak ketikan: saat fokus di input/textarea,
  Backspace menghapus huruf, bukan membatalkan titik ukur.

Verifikasi: eslint bersih, build produksi sukses, aturan CSS dan tombol baru
terkonfirmasi hadir di bundel hasil build.

---

## [#678] Chip kuota kompresi berhenti tergencet di toolbar desktop — 2026-08-01

Laporan lapangan (tangkapan layar 1520 px): tombol informasi kuota Tinify di
toolbar Dashboard **tergencet** jadi serpihan hijau selebar beberapa piksel —
angkanya terpotong setengah dan tombolnya praktis tak bisa diketuk.

**Akar masalah — chip itu satu-satunya yang boleh menyusut.** Baris toolbar
desktop `DashboardToolbar.jsx:132` sengaja `flex-nowrap` + `overflow-x-auto`,
dan SEMUA anaknya diberi `flex-shrink-0` … kecuali dua: chip kuota dan saklar
List/Galeri. Begitu barisnya meluap — yang terjadi tepat di `xl` (1280 px) ke
atas, saat label seluruh tombol menyala serentak — **seluruh kekurangan ruang
jatuh ke chip itu sendirian**. Diperparah `min-w-0` yang dipasang di PR #666
(untuk melepas diri dari aturan tap-target 44px): kelas itu membuang lantai
lebar `min-content`, sehingga chip bisa menyusut sampai nyaris nol alih-alih
berhenti di lebar isinya. Spacer `flex-1` di sebelahnya tidak ikut menyerap
karena basis lebarnya 0 (faktor susutnya diskalakan basis → nol kontribusi).

Terukur pada replika baris toolbar memakai **CSS produksi** (ikon dipaksa 16px
oleh `[&_svg]:size-4`, `gap-2` Button asli):

| viewport | lebar chip (render) | lebar alami | selisih |
|---|---|---|---|
| 1216 px | 101 px | 101 px | — |
| **1280 px** | **63 px** | 101 px | **−38 px (tergencet)** |

Ambang persisnya bergeser mengikuti panjang label nyata (mis. "Cetak Kartu
(1750)" lebih lebar daripada "(50)"), jadi di layar pemilik gejalanya muncul
pada 1520 px — mekanismenya sama.

**Perbaikan.**

- `flex-shrink-0` pada chip kuota; `min-w-0` dibuang (justru itu yang
  mengizinkan runtuh total). Kalau barisnya memang tak muat, `overflow-x-auto`
  milik toolbar yang bekerja — itu memang katup pengaman yang sudah dirancang
  di sana, bukan menggencet satu tombol sampai tak terbaca.
- `flex-shrink-0` juga pada saklar List/Galeri — satu-satunya anak lain yang
  masih bisa menyusut, dan calon korban berikutnya begitu chip diamankan.
- Bar mini 32px pindah dari `lg:block` ke `2xl:block`. Pada 1280–1535 label
  semua tombol menyala serentak dan bar itulah yang mendorong barisnya meluap;
  angka sisa kuota tetap terbaca, dan bar lengkap per layanan memang sudah ada
  di dalam popover-nya.

Sesudah perbaikan, terukur ulang dengan CSS hasil build baru: chip **tidak
pernah** lebih sempit dari lebar alaminya pada 1024–1920 px (63 px di
1024–1535, 101 px di ≥1536 saat bar mini kembali).

> Pola: di baris `flex-nowrap`, **satu anak yang lupa `flex-shrink-0` akan
> menyerap SELURUH kelebihan lebar** — bukan sebagian. Bila anak itu juga
> ber-`min-w-0`, ia menyusut sampai nol tanpa perlawanan.

---

## [#677] BAST PPK → KPB ber-dokumen resmi + LPB gabungan seluruh BAST — 2026-08-01

Melengkapi rantai serah terima hasil pengadaan (lanjutan mandat pemilik yang
label formulirnya sudah diperjelas di [#676]): nomor BAST yang diinput operator
adalah **BAST Penyedia → PPK** (penomorannya dibuat PPK sendiri — aplikasi hanya
mencatat), sedangkan serah terima tahap kedua **PPK → Kuasa Pengguna Barang**
kini benar-benar DITERBITKAN aplikasinya, lengkap dengan dokumen resminya.

### Tombol BAST PPK → KPB per perolehan (`routes/pengadaan.py`)

- `POST /pengadaan/{id}/bast-ppk-kpb` — idempoten (klik kedua mengembalikan
  rekaman yang ada; filter `$exists: False` menutup celah klik-ganda supaya
  rekaman pemenang tak tertimpa). Nomor **Berita Acara** dipesan dari deret
  buku agenda keluar yang SAMA dengan generator BAST modul Penggunaan
  (`_no_agenda_berikut` + `bangun_nomor`), tercatat berstatus `dibooking`.
- Identitas kedua pihak **dibekukan saat terbit**: PIHAK KESATU dari snapshot
  PPK perolehan (bukan registry hari ini), PIHAK KEDUA dari resolver KPB pada
  tanggal dokumen (`resolve_penandatangan_kpb`, ikut awalan Plt./Plh.).
  Tanpa PPK → 400 dengan petunjuk mengisinya; tanpa KPB → 400 juga.
- `GET /pengadaan/{id}/bast-ppk-kpb/pdf` — naskah resmi ber-pasal (pola
  bast.py): kop satker, narasi hari-tanggal terbilang, identitas dua pihak
  berdampingan, dasar hukum rezim **pengadaan** (Perpres 16/2018 jo. 46/2025 +
  PMK 181/2016 — bukan PMK 40/2024 milik rezim penggunaan) plus kontrak &
  BAST penyedia sebagai dasar dinamis, tabel objek ber-golongan & total,
  pasal dasar serah terima / penatausahaan / penutup, blok TTD dua pihak
  (privasi NIK Non-ASN tetap ditegakkan `baris_identitas_ttd`).
- UI: tombol di baris register — belum terbit → terbitkan (konfirmasi dulu);
  sudah terbit → tombol yang sama mengunduh PDF, dan nomornya tampil di baris
  meta. Diverifikasi empiris: PDF dirender nyata dan 12 penanda isi
  (kedua nama, nomor, pasal, golongan, Plt.) ditemukan di teksnya.

### LPB gabungan — satu laporan untuk seluruh BAST PPK → KPB

- `POST /pengadaan/lpb-gabungan` — SATU dokumen `db.lpb` berkategori baru
  `gabungan` merangkum banyak perolehan sekaligus, **aset maupun persediaan**
  apa adanya per baris BAST. Setiap baris membawa keterangan nomor BAST
  PPK-KPB asalnya (`baris_lpb_gabungan`, murni + teruji) sehingga pemeriksa
  bisa merunut tiap baris tanpa membuka register. Perolehan yang belum
  ber-BAST PPK→KPB DITOLAK 400 dengan daftar nomornya — rekap yang barisnya
  tak bisa dirunut adalah rekap yang bohong.
- Nomornya dipesan dari deret LPB yang sama (`booking_nomor_lpb`); PPK di
  header: satu nama bila seragam, gabungan nama tanpa NIP bila beda orang.
- `bangun_lpb_pdf` mengenal kategori `gabungan`: judul "GABUNGAN ASET &
  PERSEDIAAN", jenis "Rekap n BAST PPK-KPB", kolom NUP ikut dicetak (baris
  persediaan cukup "-"), tautan menunjuk "n perolehan (gabungan)".
- UI: tombol **LPB Gabungan** di header Pengadaan → dialog centang per
  perolehan (yang belum ber-BAST PPK→KPB nonaktif + diberi tanda; ada pilih
  semua) → dialog hasil yang sama dengan LPB biasa (unduh PDF + kirim TTD —
  jalur TTD elektronik LPB lama otomatis ikut bekerja karena koleksinya
  satu). Riwayat LPB di Persediaan menampilkan badge `gabungan · n BAST`
  dan filter kategorinya mengenali nilai baru.

Verifikasi: 1397 uji unit backend lulus (termasuk 7 uji baru
`baris_lpb_gabungan`), eslint bersih, build produksi sukses, kedua PDF
dirender empiris dengan seluruh penanda isi ditemukan.

---

## [#676] Referensi persediaan 16 digit dari PDF SAKTI + UI iPad/HP + Catat Perolehan lega — 2026-08-01

### Referensi barang persediaan 16 digit — impor langsung dari PDF SAKTI

Di SAKTI, barang persediaan beridentitas kode 16 digit: 10 digit kodefikasi +
6 digit kode urut yang LAHIR dari pendaftaran satker itu sendiri — daftarnya
berbeda antar satker dan berubah seiring waktu. Fondasi 16 digit di aplikasi
ini sudah ada sejak lama (`KODE_PENUH_LEN=16`, generator urut per satker,
kode & NUP non-editable); yang baru:

- **Parser `persediaan_referensi.py`** (murni, 17 uji) membaca laporan SAKTI
  "UC_PER032 — Referensi Tabel Barang Persediaan" — terbukti pada PDF asli
  kiriman pemilik: **708 item terbaca, 0 galat**, identitas UAKPB
  (`126.01.1600.691778.000.KP` → satker `691778`) terdeteksi otomatis.
- **Endpoint `POST /persediaan/referensi-sakti-pdf`** dua tahap: pratinjau
  (baru/berubah/tetap + contoh) lalu terapkan. PDF milik satker LAIN ditolak
  dengan menyebut kedua kodenya. Barang baru memakai kode 16 digit APA ADANYA
  dari PDF; yang sudah ada hanya diperbarui nama & satuan; TIDAK ada yang
  dihapus (laporan bisa terunduh terfilter).
- **Guard hapus diperkuat**: kode yang PERNAH bertransaksi tak bisa dihapus
  walau stok sudah nol — dulu guard hanya menahan `stok > 0`, sehingga kode
  ber-riwayat bisa lenyap dan memutus jejak audit LPB/jurnal/pengadaan.
  Sesuai keputusan pemilik: kode ber-transaksi hanya boleh diubah nama &
  satuannya.
- UI: menu **Data → Impor Referensi SAKTI (PDF)** di halaman Persediaan
  dengan dialog pratinjau (kartu Total/Baru/Berubah/Tetap + contoh baris).

### Catat Perolehan (Pengadaan) — lega + picker kodefikasi + klarifikasi BAST

- Dialog diperlebar (`max-w-2xl`), tiap barang jadi KARTU berlabel — uraian
  satu baris penuh, kode/jumlah/harga berlabel jelas.
- **Kode barang kini ber-picker dari Referensi Kodefikasi** (ketik kode/nama →
  pilih; uraian ikut terisi bila kosong). Dulu diketik buta — salah satu digit
  membuat pemilahan aset/persediaan salah kandang.
- **Klarifikasi BAST**: label menjadi "No. BAST (Penyedia → PPK)" plus catatan:
  BAST ini serah terima dari Penyedia kepada PPK, penomorannya dibuat PPK
  sendiri — cukup catat nomornya + centang dokumen. Serah terima PPK → KPB
  akan dibuatkan dokumennya lewat tombol tersendiri (menyusul).

### Kartu statistik iPad Pro & indikator kuota

- Kartu Total Aset/Total Nilai/Aktif/Maintenance terpotong ("1..",
  "Rp 2.30…") tepat di 1024 px: tata letak label-kiri nilai-kanan tak muat di
  ambang bawah `lg`. Grid mendatar kini mulai `xl` (≥1280); 1024–1279 memakai
  kartu bertumpuk yang memang muat. Nilai diberi `title` (nilai utuh saat
  disentuh lama) + `tabular-nums`.
- **Indikator kuota Tinify dkk**: rinciannya dulu hanya hidup di Tooltip
  (hover) sementara klik men-toggle state yang TAK PERNAH dirender — di
  tablet/HP mengetuknya tak menampilkan apa-apa. Kini Popover (klik, jalan di
  sentuh & kursor), chip lebih ringkas (bar mini hanya di layar lebar), dan
  varian HP jadi tombol angka BERTUMPUK sisa/batas yang hemat ruang kiri-kanan
  — dua-duanya membuka panel rincian yang sama.

**Uji:** 1.390 backend (17 baru) + 329 frontend, lint & build bersih, parser
terverifikasi pada PDF SAKTI asli.

---

## [#675] Alat ukur jarak & luas di Peta Aset dan Peta Kolaborasi — 2026-08-01

Permintaan pemilik: fitur *measure* di halaman peta inventarisasi aset, dan di
peta kolaborasi juga.

Ketuk peta untuk menandai titik; panjang tiap ruas muncul sebagai label di
sepanjang jalur, dan begitu titiknya ≥3 bidangnya tertutup sendiri sehingga
luasnya ikut terbaca. Klik kanan / tekan lama membatalkan satu titik, `Escape`
mengosongkan — tanpa dialog konfirmasi, karena saat mengukur di lapangan tangan
sedang sibuk dan konfirmasi memutus alur.

**Geodesik, bukan planar.** Peta digambar dalam proyeksi Web Mercator, dan
menghitung luas langsung dari koordinat layar akan MELEBIH-LEBIHKAN hasil makin
jauh dari khatulistiwa. Untuk IKN (±1° LS) galatnya kecil, tetapi angka luas di
aplikasi ini dipakai untuk hal yang serius — SBSK, sengketa batas, laporan BMN.
Maka jarak memakai haversine dan luas memakai rumus luas bola (*spherical
excess*).

Satuannya mengikuti kebiasaan setempat: meter di bawah 1 km, kilometer di
atasnya, dan **hektar** begitu luasnya ≥1 ha — supaya angkanya bisa langsung
dibandingkan dengan sertifikat tanah tanpa dihitung ulang.

Perhitungannya dipisah ke `lib/ukurPeta.js` (murni, 23 uji) dan perkabelan
Leaflet-nya ke `hooks/useUkurPeta.js` yang **dipakai bersama kedua peta** —
dua salinan pasti menyimpang, dan penyimpangan pada alat ukur berarti dua angka
berbeda untuk bidang yang sama.

Satu cacat ditemukan oleh ujinya sendiri: `Number(x.toFixed(2)).toLocaleString()`
membuang nol di belakang, sehingga presisinya tak konsisten — "5,23 m" tetapi
"5,2 m". Untuk angka yang masuk berita acara itu tidak baik; format kini
memaksa jumlah desimal, kecuali nilai nol yang tetap ditulis "0 m" (belum ada
yang diukur, bukan pernyataan presisi).

**Uji:** 329 uji frontend (23 baru), lint & build bersih.

---

## [#674] Kompresi gambar berhenti gagal diam-diam — sebabnya kini terlihat — 2026-08-01

Laporan pemilik: "kompresi dengan Compresto tidak berfungsi". Menelusurinya
membuka dua cacat yang saling menutupi — dan keduanya menjelaskan kenapa
masalahnya sulit dilihat.

**1. Setiap kegagalan ditelan menjadi `return None`.** Kunci salah, host tak
terjangkau, kontrak API berubah, kuota habis — semuanya menghasilkan hasil yang
persis sama. Rantai lalu jatuh ke Pillow dan endpoint menjawab
`success: true, method: "pillow"`. Dari kursi operator, layanan itu "tidak
berfungsi" TANPA satu pun petunjuk sebabnya; satu-satunya jejak ada di log
server yang tak bisa dia buka.

**2. Indikatornya berbohong.** `"available": bool(COMPRESTO_API_KEY)` — sekadar
"env var terisi", bukan "layanan menjawab". Kebohongan yang sama pernah
diperbaiki untuk iLovePDF di `[#665]`; di sini ia masih hidup, dan justru itulah
yang membuat layar tampak sehat sementara kompresinya tak pernah jalan.

Perbaikan:

- Modul baru `kompresi_diagnostik.py` (murni, 13 uji) mencatat hasil percobaan
  TERAKHIR per layanan: berhasil/gagal, kode HTTP, sebab, dan waktunya.
- Setiap cabang kegagalan di Compresto & Uploadcare kini mencatat sebabnya,
  termasuk cuplikan badan respons — di situlah layanan biasanya menjelaskan
  penolakannya.
- Status HTTP diterjemahkan jadi kalimat yang berguna: 401 "Kunci API ditolak",
  404 "Alamat endpoint tidak ditemukan — kontrak API mungkin sudah berubah",
  413 "Berkas terlalu besar", dan seterusnya.
- `available` kini berarti **percobaan terakhir memang berhasil**. Kunci
  terpasang tapi belum pernah dipakai dilaporkan `belum_dicoba` — bukan
  "tersedia", karena tak ada satu pun bukti layanannya menjawab.
- Skrip `scripts/verifikasi_kompresi_gambar.py` mengirim satu gambar uji ke
  tiap layanan yang kuncinya terpasang dan melaporkan apa yang sebenarnya
  terjadi. Gambar ujinya sengaja bergradasi, bukan warna polos: berkas polos
  sudah minimal sehingga layanan yang bekerja benar pun bisa mengembalikan
  berkas lebih besar — dan itu terbaca sebagai kegagalan palsu.

### Yang TIDAK bisa dikerjakan dari sini

Kontrak API Compresto **tidak diverifikasi**. Kebijakan jaringan lingkungan
pengembangan memblokir seluruh koneksi keluar (gateway menjawab `403` pada
`CONNECT`, terbukti bahkan untuk `upload.uploadcare.com`), dan kunci API-nya
memang tak boleh berada di sini. Menebak-ubah alamat endpoint atau nama header
tanpa bukti hanya akan menukar satu kegagalan senyap dengan kegagalan senyap
lain.

Karena itu yang dikerjakan adalah membuat kegagalannya **terlihat dan
terbaca**. Jalankan skrip verifikasi di VPS dengan kunci di `.env`; satu kali
jalan akan menyebut persis apa yang salah — alamat, kunci, atau nama field.

**Uji:** 1.373 uji backend (13 baru), compileall bersih, pemeriksa rahasia
bersih.

---

## [#673] Impor Excel: tanggal akhirnya divalidasi, dan dropdown kategori memuat SELURUH kodefikasi — 2026-08-01

### Kolom tanggal tak pernah divalidasi sama sekali

`parse_excel_content` melakukan `str(cell or '')` dan apa pun hasilnya langsung
masuk basis data. Tiga bentuk sampah lolos diam-diam:

1. Sel bertipe tanggal dibaca openpyxl sebagai `datetime`, lalu `str()`
   membuatnya `"2024-01-01 00:00:00"` — beda dari tanggal yang ditulis
   aplikasi sendiri (`YYYY-MM-DD`), sehingga urutan & penyaringan meleset.
2. Sel berformat Umum berisi **serial date** Excel (mis. `45658`) masuk apa
   adanya sebagai teks angka.
3. Ketikan bebas (`17 Agustus 2025`, `32/13/2025`) diterima utuh — termasuk
   tanggal yang tak pernah ada.

Modul baru `impor_tanggal.py` (murni, 30 uji) menutup ketiganya:

- **Format resmi `DD/MM/YYYY`** — sesuai kebiasaan dokumen resmi Indonesia,
  dipilih pemilik. Longgar soal nol di depan (`3/4/2025` = 3 April), KETAT
  soal urutan.
- Bentuk lain yang tak ambigu tetap diterima agar berkas lama tak tertolak:
  ISO `YYYY-MM-DD`, `DD-MM-YYYY`, `DD.MM.YYYY`.
- **Serial Excel** dikonversi dengan basis `1899-12-30` — bukan `1899-12-31`;
  Excel keliru menganggap 1900 tahun kabisat, dan salah satu hari di sini
  menggeser seluruh tanggal.
- Serial di wilayah bug 1900 (1–60) ditolak: angka sekecil itu jauh lebih
  mungkin salah ketik daripada tanggal sungguhan.
- Pagar kewarasan tahun 1945–2200.
- Semua hasil dinormalkan ke satu bentuk `YYYY-MM-DD`.

Sesuai keputusan pemilik, **satu sel tanggal yang tak terbaca membatalkan
seluruh impor** — perilaku ini sudah menjadi desain yang ada (`If any errors,
reject ALL data`), jadi tinggal disambungkan. Pesan galat menyebut nomor
baris, nama kolom, dan nilai aslinya, dan nilai asli itu **dibiarkan di
tempatnya** supaya operator masih bisa melihat apa yang dia ketik.

### Dropdown kategori hanya memuat sebagian

Plafonnya ketemu: `to_list(500)` di generator template — sementara endpoint
`GET /categories/all` memakai `50000`. Daftar kodefikasi barang BMN berisi
ribuan entri, jadi dropdown memotongnya diam-diam **dan tanpa urutan**,
sehingga 500 mana yang lolos pun tak menentu. Batas kini disamakan dan hasilnya
diurutkan per `kode_aset`.

### Memilih kategori kini mengisi `asset_code`

Kode barang & deskripsi berpasangan satu-satu di Kelola Kategori Aset, jadi
pilihan kategori sudah cukup menentukan kodenya. Dikerjakan dua lapis:

- **Di template** — rumus `INDEX`/`MATCH` ke lembar tersembunyi `_lists`
  (kolom A = label, kolom B = kode sebagai TEKS agar angka berawalan nol tak
  dipangkas). Rumus, bukan makro: berkas tetap `.xlsx` biasa tanpa peringatan
  keamanan, dan operator tetap bisa menimpanya dengan ketikan sendiri.
- **Di server** — bila `asset_code` sampai kosong, impor mengisinya sendiri
  dari kategori. Ini bukan hiasan: uji asap membuktikan xlsxwriter **tidak**
  menulis nilai ter-cache, sehingga berkas yang belum pernah dibuka di aplikasi
  spreadsheet terbaca `None` oleh openpyxl. Jalur CSV juga tak punya rumus
  sama sekali.

Label ganda (dua kode berbeda berdeskripsi sama) **sengaja tidak dipetakan**
di kedua lapis — menebak salah satunya berarti mencatat kode barang yang
keliru, jauh lebih berbahaya daripada meminta operator mengetik.

**Uji:** 1.360 uji backend (30 baru untuk `impor_tanggal`) + uji asap
pembuatan berkas .xlsx dan pembacaan ulangnya.

---

## [#672] Unduh foto asli berhenti "sering gagal" + pencarian membawa peta ke hasilnya — 2026-08-01

### Unduh foto asli sering gagal, tapi berhasil setelah dibuka Layar Penuh

Petunjuk dari laporan itu sendiri yang membongkarnya. Membuka Layar Penuh lebih
dulu "menyembuhkan" unduhan karena `<img>` mengambil **URL yang sama** dan
pengambilan gambar oleh peramban TIDAK terikat tenggat axios; setelah itu
berkasnya ada di cache HTTP sehingga permintaan unduh selesai seketika.

Akarnya: `axios.defaults.timeout` dipasang **20 detik** di `App.js` sebagai
lantai tenggat untuk permintaan data, dan tombol unduh memakai `axios.get`
polos sehingga ikut terkena. Foto asli dari kamera HP berukuran beberapa
megabyte — di jaringan lapangan transfernya lewat dari 20 detik dan axios
memutusnya di tengah jalan.

Tenggat tetap memang alat yang salah untuk unduhan besar. Bahaya asli yang
dijaga tenggat global — soket yang MENGGANTUNG — tetap ditutup, tetapi kini
oleh pemantau kemajuan: yang diputus adalah transfer yang **berhenti
mengalir** (30 detik tanpa satu byte pun), bukan transfer yang lambat namun
terus jalan.

Sekalian dirapikan:

- Tombol menampilkan **persentase** selama mengunduh, dan berfungsi sebagai
  **Batal** — sebelumnya tombol dimatikan tanpa jalan keluar, yang di jaringan
  lambat terbaca sebagai aplikasi menggantung.
- Pesan gagal menyebut sebabnya (sesi berakhir / foto tak ada / server sibuk /
  tak ada sinyal / terhenti) alih-alih "Gagal mengunduh foto asli" untuk semua
  kasus.
- Nama berkas kini ikut tipe isi sebenarnya (`webp`/`png`/`heic`, bukan selalu
  `jpg`) dan dibersihkan dari karakter yang ditolak sistem berkas — titik pada
  kode barang BMN sengaja DIPERTAHANKAN.
- Menutup lightbox di tengah unduhan memutus permintaannya.

### "Mengetik di kotak cari tidak berdampak di halaman peta"

Datanya sebenarnya SUDAH tersaring: `buildMapParams` ikut membawa kata kunci,
dan pin yang tak lolos memang dibuang oleh sinkronisasi marker. Yang tidak
terjadi adalah **perpindahan tampilan** — `didFitRef` sengaja hanya di-reset
pada muat pertama agar posisi/zoom pengguna tak diacak tiap reload. Akibatnya,
di peta yang sudah diperbesar, satu-satunya pin yang cocok berada jauh di luar
layar; dari kursi pengguna itu tak bisa dibedakan dari "pencarian tak jalan".

Mencari adalah pengecualian yang sah: pengguna menyebut apa yang dituju, jadi
sekarang peta mengantarnya ke sana. Filter lain (kategori/lanjutan) tetap
TIDAK memindahkan tampilan.

Permintaan "bawa ke hasil" sengaja dikonsumsi saat **data hasil pencarian
tiba**, bukan saat kata kuncinya berubah — kalau tidak, sinkronisasi marker
sempat berjalan dengan baris LAMA dan memakai jatah fit-nya di sana.

**Uji:** 306 uji frontend (25 baru untuk `lib/unduhFoto`), lint & build bersih.

---

## [#671] Dialog berhenti melebar menyamping + Muat ulang peta kolaborasi tak lagi memutihkan peta — 2026-08-01

Dua laporan lapangan, dua akar yang berbeda.

### Isi dialog "memanjang menyamping melebihi kanvas"

`DialogContent` adalah `grid`, dan anak grid bawaannya `min-width: auto` —
lebar minimumnya = lebar **min-content** isinya. Satu saja keturunan
ber-`white-space: nowrap` (di sini `truncate` pada URL link berbagi) membuat
min-content-nya selebar teks utuh; jalur grid ikut melar, SEMUA anak lain
teregang selebar itu, lalu ujung kanannya dipotong `overflow-hidden`. `min-w-0`
yang sudah lama terpasang pada span teks tak menolong — yang perlu dinolkan
adalah **anak grid**-nya, bukan cucunya.

Diukur di peramban (DOM dialog + CSS hasil build asli, viewport 412 px):

| | Sebelum | Sesudah |
|---|---|---|
| `scrollWidth` / `clientWidth` | 788 / 386 | **386 / 386** |
| Elemen yang menembus tepi | 22 | **0** |

Perbaikannya satu utilitas di komponen dasar — `[&>*]:min-w-0` pada
`DialogContent` **dan** `AlertDialogContent` — jadi seluruh dialog aplikasi
ikut terlindungi, bukan hanya dialog Bagikan Peta. Pada `AlertDialogContent`
akibatnya bahkan lebih parah sebelum ini karena ia tak punya
`overflow-hidden`: isinya tumpah ke luar kotak, bukan sekadar terpotong.

Catatan: cacat yang sama pernah ditambal setempat di `ImporDenahDialog`
(entri dialog impor terpotong). Tambalan itu kini jadi mubazir — akarnya
sudah tertutup di hulu.

### Tombol "Muat ulang" membuat peta kolaborasi putih

Tombolnya memanggil `setLoading(true)`, dan layar pemuat mengganti SELURUH
pohon — termasuk `<div>` tempat Leaflet hidup. Saat selesai, React memasang
`<div>` BARU, sementara `mapRef` masih memegang peta lama yang terikat node
yang sudah dibuang; efek inisialisasi pun pulang lebih awal (`mapRef` sudah
terisi) dan wadah baru tinggal kotak putih.

- Muat ulang kini memakai state `menyegarkan` yang terpisah — peta tak pernah
  dilepas, hanya ikon tombol berputar selama data diambil.
- Efek inisialisasi juga dibuat tahan banting: bila wadah peta ternyata sudah
  lepas dari dokumen, peta lama dibongkar dan dibangun ulang. Ini menutup
  jalur yang tersisa — layar "Koneksi bermasalah"/galat juga mengganti pohon,
  sehingga "Coba lagi" dulu memunculkan bug yang sama.

**Uji:** 281 uji frontend, lint & build bersih + pengukuran geometri dialog di
peramban.

---

## [#670] Peta di HP: kotak atribusi & panel Lapis Denah berhenti menggembung — 2026-08-01

Laporan lapangan (tangkapan layar HP): kotak putih transparan Leaflet
"Leaflet | © OpenStreetMap" terlalu besar, baris panel **Lapis Denah** terlalu
tinggi, dan baris "Bentuk ringan" ikut renggang atas-bawah.

Akar keduanya sama — dan keduanya **bukan** dari gaya yang ditulis di
komponennya, melainkan dari dua aturan global di `index.css`:

- **Kotak atribusi.** Pengecualian 36px untuk kontrol Leaflet ditulis
  `.leaflet-control a`. Kotak atribusi juga `.leaflet-control`, jadi
  `line-height: 36px` ikut mengenai tautan di dalamnya. `min-height`/`width`
  memang tak berlaku pada elemen inline — tapi `line-height` berlaku, dan
  itulah yang menggembungkannya. Selektor kini menyebut kontrol tombol saja
  (`:not(.leaflet-control-attribution):not(.leaflet-control-scale)`), plus
  `line-height` atribusi dikunci 1.35 agar tak ada aturan lain yang
  diam-diam mengembalikannya.
- **Baris panel.** `[data-peta-panel]` (Lapis Denah & pemilih lantai) ditulis
  rapat (`py-1`, teks 10px, ikon 12px — tinggi alami ~22 px), tapi aturan
  sentuh 44px global menggembungkan setiap barisnya jadi 44 px. Baris panel
  selebar panel penuh (~150 px), jadi tingginya bukan penentu kemudahan
  sentuh; kini dibatasi 28 px.

Sekalian: prefiks **"Leaflet"** pada atribusi dimatikan
(`attributionControl.setPrefix(false)`) di keempat peta aplikasi — Peta Aset,
Peta Kolaborasi, Lokasi Temuan Wasdal, dan Editor Denah. Prefiks itu opsional;
yang WAJIB secara lisensi ODbL adalah kredit `© OpenStreetMap`, dan itu tetap
tercantum utuh.

Diukur di peramban pada viewport 412 px (Leaflet asli, CSS lama vs baru):

| | Sebelum | Sesudah |
|---|---|---|
| Kotak atribusi | 126,6 × 36 px | **82,7 × 14,1 px** (luas −74%) |
| Panel Lapis Denah, 3 baris | 132 px | **84 px** (−36%) |

**Uji:** 281 frontend, lint & build bersih + pengukuran geometri di peramban.

---

## [#669] Kotak putih misterius di kiri-atas HP: tautan "lompat ke konten" yang mencuat — 2026-07-28

Laporan lapangan tiga ronde akhirnya terpecahkan dengan MENJALANKAN aplikasi di
viewport HP (Playwright) dan menyelidiki elemen di titik yang dilaporkan:
pelakunya `.skip-link` — tautan aksesibilitas "lompat ke konten".

Cacatnya berlapis, dan baru muncul justru di HP:

- Ia disembunyikan dengan `top: -40px` — offset piksel TEBAKAN atas tingginya.
  Di layar sempit aturan sentuh global memaksa semua `<a>` minimal 44 px, dan
  skala huruf Android bisa menambahnya lagi: ujung bawahnya SELALU mencuat di
  kiri-atas, dengan `z-index: 9999` — di atas segalanya, termasuk pegangan
  tirai satker.
- Ujung yang mencuat itu bisa TERKETUK; ketukan memberi `:focus`, dan gayanya
  memunculkan seluruh kotak putih bersudut-bundar tepat di depan pegangan —
  persis tangkapan layar lapangan.

Perbaikan: sembunyikan dengan `transform: translateY(-110%)` (relatif terhadap
tinggi dirinya sendiri, berapa pun itu) dan muncul hanya pada `:focus-visible`
(navigasi papan ketik — satu-satunya pengguna yang membutuhkannya; ketukan jari
tak lagi memunculkannya). Fungsi aksesibilitasnya utuh.

Diverifikasi dua arah di viewport HP: sebelum — `elementFromPoint` di kiri-atas
mengembalikan `.skip-link`; sesudah — bersih, dan pegangan tirai berdiri tanpa
terhalang.

**Uji:** 281 frontend, lint & build bersih + verifikasi visual Playwright.

---

## [#668] Pegangan tirai naik ke lapisan teratas + kembali kasatmata — 2026-07-28

Dua koreksi atas `[#667]`, dari umpan balik lapangan yang sama:

- **Yang mengganggu ternyata BUKAN pegangannya, melainkan elemen yang berdiri
  DI DEPANNYA** dan menutupinya. Pegangan adalah pintu satu-satunya ke pemilih
  satker — tak boleh ada yang menghalanginya. Tirai kini di lapisan teratas
  antarmuka (`z-[110]`, di atas lightbox 100 dan bilah tugas 90); apa pun yang
  kemarin berdiri di depannya kini berada di belakang.
- **Garis 32×4 px terlalu sulit ditemukan.** Jalan tengahnya: pil kompak
  64×16 px ber-ikon genggam — jelas terlihat, tapi separuh tinggi pil lama yang
  dulu menimpa judul halaman.

**Uji:** 281 frontend, lint & build bersih.

---

## [#667] Pegangan tirai satker mengecil jadi seutas garis — 2026-07-28

Laporan lapangan (tangkapan layar HP): pegangan tirai satker — pil teal gelap
ber-ikon genggam — menimpa judul halaman pemilih kegiatan dan terbaca sebagai
"gambar yang menghalangi".

Pegangan tak berhak setebal itu selagi tirainya sendiri tak dibuka. Saat
TERSEMBUNYI ia kini hanya seutas garis 32×4 px setengah-transparan di tengah
tepi atas; wujud pil penuh ber-ikon baru muncul saat tirai TERBUKA, ketika ia
memang sedang menjadi kendali.

Area sentuhnya justru tak menyempit: bidang raba 44×24 px berlatar transparan
tetap dipertahankan — yang dikecilkan hanya yang TERLIHAT, bukan yang bisa
diraba, jadi menarik tirai dari tepi atas tetap semudah sebelumnya. Garis
kemajuan tarikan ikut pindah ke tepi atas pada wujud garis.

**Uji:** 281 frontend, lint & build bersih.

---

## [#666] Sapu merek — logo & tombol aksi utama ikut keluarga teal — 2026-07-28

Pelengkap `[#665]`. Setelah token dan komponen dasar satu keluarga, yang tersisa
adalah gradien-gradien dekoratif tingkat halaman:

- **Logo aplikasi** di Login, pemilih Kegiatan, header Dasbor, dan Beranda
  Modul — dulu empat-empatnya gradien biru; kini teal, karena kotak logo adalah
  merek itu sendiri.
- **Tombol aksi utama bergradien**: CTA masuk kegiatan, "Mode Kamera Penuh",
  "Download LHI Lengkap" (dulu tiga warna indigo→biru→cyan sekaligus).
- **Pita dekoratif** dialog Data Sistem, judul gradien InfoPage, dan indikator
  tarik-untuk-menyegarkan di dasbor.

Dua hal yang SENGAJA tidak disentuh, dan itu keputusan desain: gradien
**identitas per-modul** di Beranda Modul (13 modul BMN dibedakan lewat warna —
menyeragamkannya justru menghapus fungsinya), dan **ungu status "Berlebih"** —
itu warna semantik data, sekeluarga dengan biru=informasi, amber=peringatan,
merah=galat.

**Uji:** 281 frontend, lint & build bersih.

---

## [#665] Satu bahasa desain — font dibundel, satu aksen teal, komponen dasar yang merespons — 2026-07-28

Perombakan tema menyeluruh memakai metode audit *redesign-existing-projects*
(paket taste-skill): pindai → diagnosis → perbaiki DI LAPIS TOKEN, supaya satu
perubahan mengalir ke seluruh 33 halaman sekaligus — bukan mengecat 33 halaman
satu per satu.

### Diagnosis yang ditemukan audit

1. **Empat keluarga font dari CDN Google** — Inter (persis font yang ditandai
   "sidik jari AI" oleh skill), Manrope, IBM Plex Sans, JetBrains Mono — lewat
   `@import` yang memblokir render pertama. Dan ini PWA lapangan: saat luring,
   CDN gagal dan wajah aplikasi berubah.
2. **Tiga aksen bersaing** — biru jenuh di token (`--accent 217 91% 60%`), teal
   tersebar hardcoded di halaman-halaman, indigo di bilah satker. Akibat paling
   terasa: hover SETIAP tombol outline/ghost berkilat biru menyala berteks
   putih, di samping ikon teal.
3. **Tombol utama hampir-hitam** (`--primary 222 47% 11%`) yang tak berhubungan
   dengan identitas teal aplikasi.
4. **76 tombol aksi `bg-blue-600`** tersebar di 29 berkas — sisa aksen lama.

### Yang dikerjakan

- **Font dibundel, satu keluarga.** `Plus Jakarta Sans` variabel (dirancang
  Tokotype — perancang Indonesia — untuk instansi pemerintah; masuk daftar
  font premium skill) untuk seluruh teks, `JetBrains Mono` untuk kode/NUP.
  Self-host via @fontsource: hidup saat luring, tanpa render-blocking, tanpa
  preconnect ke Google. `font-variant-numeric: tabular-nums` global — aplikasi
  ini 80% angka, dan kini semuanya sejajar kolom.
- **Satu aksen: teal.** `--primary` = teal dalam (teks putih 6,4:1),
  `--accent` dikembalikan ke maksud shadcn yang sebenarnya: permukaan hover
  lembut (sapuan teal pucat), `--ring` teal. Mode gelap mendapat teal terang
  ber-teks gelap (7,2:1). Merah destruktif diturunkan dari 84% ke 72% jenuh.
  76 tombol `bg-blue-600` dipetakan mekanis ke keluarga teal; bilah satker
  indigo → teal-800. **Biru DIPERTAHANKAN sebagai warna semantik informasi**
  (banner ber-ikon Info) — sejajar amber=peringatan, merah=galat.
- **Komponen dasar merespons.** Tombol: transisi 200 ms ber-kurva spring,
  mengecil 2% saat ditekan (rasa klik fisik), cincin fokus tegas, bayangan
  elev ber-rona slate. Input/textarea/select: cincin fokus 2 px + transisi.
  Dialog/sheet: sudut wadah lebih lembut daripada isi (radius bervariasi,
  bukan seragam), bayangan elev dalam. Kartu: bayangan slate lembut
  menggantikan bayangan hitam pabrikan.
- **Tipografi:** judul dirapatkan (−0,015 em) + `text-wrap: balance` (tak ada
  kata yatim), paragraf `text-wrap: pretty`, `::selection` teal.
- Kelas warisan App.css (biru keras) disatukan ke keluarga token.

**Uji:** 281 frontend, lint & build bersih; font terbundel diverifikasi di
`build/static/media`. Ukuran JS praktis tak berubah; CSS +1,2 KB.

**Batas jujur:** hasil visual belum terverifikasi mata di perangkat nyata —
yang terkunci adalah kontras (dihitung), konsistensi token, dan bahwa 281 uji
tetap lulus. 149 pemakaian biru semantik-informasi sengaja tidak disentuh.

---

## [#664] Bilah satker jadi tirai tarik-turun, denah muat di layar HP, dan pemintal Lapis Denah berhenti berputar sia-sia — 2026-07-28

Empat keluhan lapangan atas tampilan, ditutup sekaligus.

### 1. Cap satker: dari bilah tetap jadi TIRAI yang ditarik turun

Bilah "Satker aktif" dulu ikut mengalir bersama dokumen di puncak SETIAP
halaman. Dua akibatnya sama-sama nyata: ia merampas satu baris penuh di semua
layar, dan untuk membukanya di halaman yang sudah tergulir operator harus
menggulir **NAIK** dulu — kebalikan dari gerakan yang wajar untuk menurunkan
sesuatu dari tepi atas.

Kini ia melayang di tepi atas dan **tersembunyi**; yang tersisa hanya pegangan
selebar ±5,5 rem. Tirainya punya tiga tahap, dan tiap lapis berikutnya ditarik
turun dengan usahanya sendiri:

```
tersembunyi  ──tarik turun──▶  cap satker  ──tarik turun──▶  daftar satker
             ◀──tarik naik───              ◀──tarik naik───
```

**Satu tarikan = satu tahap**, sejauh apa pun ditarik. Sapuan panjang tak boleh
melompat langsung ke daftar satker: menggantinya memuat ulang seluruh aplikasi.

> **Daftar satkernya ikut turun bersama tirai, bukan digantung di bawahnya.**
> Itu yang menutup keluhan "menu daftar satker terhalang header": sebagai
> `absolute` di bawah bilah yang ikut tergulir, ia rutin terpotong di layar
> sempit. Sebagai bagian tirai, tak ada lagi yang bisa menutupinya.

Fisikanya (redaman asimtotik + ambang 72 px) tetap seperti sebelumnya, kini
berlaku dua arah dengan berat yang sama — 26 uji di `lib/tarikBerat.js`.

### 2. Editor denah muat di layar HP & tablet

Bentuk lama tak pernah muat di HP: header + bilah alas jiplak + panel validasi +
bilah tombol menumpuk di atas peta yang tingginya sudah **dipatok** `52vh`,
sehingga yang tersisa untuk menggambar tinggal secarik — sementara toolbar
geoman (tujuh tombol yang aturan sentuh global memaksa jadi 44 px, bertumpuk
vertikal ≈ 308 px) menutupi sepertiga sisi kirinya.

- Dialog **penuh layar** di bawah `sm`, `flex flex-col`, peta `flex-1 min-h-0`:
  semua bilah setinggi isinya, dan SISA layar seluruhnya jadi kanvas.
- `100dvh`, bukan `100vh` — bilah alamat peramban seluler yang muncul-hilang tak
  lagi memotong tombol Simpan di tepi bawah.
- Kontrol Leaflet & geoman **dikecualikan** dari aturan 44 px di `<1024px` dan
  turun ke 36 px (bawaan Leaflet sendiri 30 px). Itu mengembalikan ±56 px lebar
  sekaligus tinggi kepada kanvas, tanpa menyentuh satu pun tombol aplikasi.
- Judul node panjang dipangkas rapi dan tak lagi menabrak tombol tutup.

### 3. Peta Aset: tombol & panel berhenti memakan tempat

Panel **Lapis Denah** dan blok **legenda** kini terlipat di layar sempit —
keduanya rujukan yang dibaca sekali-sekali, bukan kendali yang dipakai terus,
tetapi terbuka penuh mereka memakan lebih banyak ruang daripada petanya sendiri.
Saat terlipat, panel Lapis Denah menyusut jadi satu pita ±26 px yang tetap
menampilkan cacah lapisnya. Di `sm` ke atas keduanya terbuka apa adanya.

### 4. Pemintal Lapis Denah yang berputar terus — apa sebenarnya fungsinya

Pemintal itu menandai pengambilan denah **per-viewport**: peta hanya menarik
poligon di kotak yang sedang terlihat, pada tingkat detail sesuai zoom. Jadi ia
memang bekerja, bukan hiasan. Tetapi ia menyala jauh lebih sering daripada
perlunya, karena dua sebab yang keduanya kini diperbaiki:

- **`if (termuat.terpotong) return true`.** Pada area padat — persis yang
  membuat hasilnya terpotong — SETIAP `moveend`/`zoomend`, termasuk geser
  sejari yang tak mengubah apa pun yang terlihat, menembakkan request baru yang
  mengembalikan potongan **yang sama persis**. Cache kini tetap berlaku;
  kekhususan hasil terpotong ditangani dengan menyempitkan wilayah sahnya ke
  viewport tanpa padding, sehingga berpindah area tetap menarik ulang tetapi
  diam di tempat tidak.
- **Pemintal muncul seketika.** Pemuatan viewport umumnya jauh di bawah setengah
  detik; menyalakan pemintal untuk itu membuat panel berkedip-kedip tiap peta
  digeser — dibaca operator sebagai "ada yang tak beres" padahal petanya lengkap.
  Kini ia baru diperlihatkan setelah 450 ms, jadi yang cepat berlalu tanpa satu
  kedipan pun.

Berputar lagi saat zoom in/out **tetap benar dan tetap dipertahankan**: berganti
zoom berarti berganti tingkat detail, dan itu memang data yang berbeda.

**Uji:** 1.330 backend, 281 frontend (+13), lint & build bersih.

---

## [#663] Keandalan gelombang 3 — layar putih dihabisi, dan layar berhenti menjamin yang tak diketahuinya — 2026-07-28

Penutup rangkaian `[#661]`–`[#662]`. Dua gelombang sebelumnya membereskan
**permintaan** yang gagal. Gelombang ini membereskan apa yang TERJADI PADA LAYAR
setelah permintaan itu gagal — dan di sini ditemukan kelas kegagalan yang lebih
buruk daripada lambat: layar yang **tampak baik-baik saja padahal tidak tahu
apa-apa**.

### 1. Layar putih total saat potongan kode gagal diunduh

Ke-33 halaman aplikasi ini dimuat `React.lazy(() => import(...))` — dibungkus
32 titik `<Suspense>` (LoginPage & DashboardPage berbagi satu pembungkus di
dalam `<Routes>`). Aplikasi ini **tidak punya satu pun error boundary**. Artinya: satu potongan yang gagal
diunduh — luring, sinyal putus di tengah unduhan, atau versi baru sudah dipasang
sehingga berkas ber-hash yang lama tak ada lagi di server — membuat React
melepas SELURUH pohon komponen. Yang tersisa di layar operator adalah **putih
polos**: tanpa pesan, tanpa tombol, tanpa apa pun untuk ditekan.

`components/BatasGalat.jsx` menutupnya. Setiap halaman kini dibungkus
`<HalamanLazy>` (boundary DI LUAR Suspense — ditaruh di dalam, galatnya lewat
begitu saja). Batasnya berhenti di tingkat HALAMAN: lihat "Belum dikerjakan".

> **Tombol yang sengaja TIDAK dipasang.** Untuk galat unduh potongan, layar ini
> hanya menawarkan *Muat ulang halaman* — bukan *Coba lagi*. `React.lazy`
> mengingat penolakan `import()` pada objek lazy tingkat-modul dan melempar
> galat yang SAMA selamanya; memasang ulang anaknya tidak mengulang unduhan.
> Tombol "Coba lagi" di situ akan gagal seketika, setiap kali ditekan. Untuk
> galat render biasa ia tetap ditawarkan, karena di sana ia memang bekerja.

Klasifikasinya dipisah ke `lib/galatRender.js` agar bisa diuji tanpa DOM (10
uji). Dua di antaranya menangkap cacat nyata pada rancangan pertama: pola
`err.message || err` membocorkan kata "Error" ke layar untuk `new Error("")`,
dan regex-nya tak mengenali *"Loading **CSS** chunk 3 failed"* — webpack
menyisipkan jenis berkas di tengah kalimat untuk potongan CSS.

### 2. "Tidak ada peringatan. Itu kabar baik."

Halaman Pelacakan memuat empat daftar dengan satu `Promise.all`. Satu endpoint
gagal → seluruh `try` melompat ke `catch` → keempat daftar tetap kosong → dan
tab Peringatan mencetak kalimat di atas.

Layar itu **menjamin aman justru ketika ia tidak tahu apa-apa**, pada halaman
yang seluruh gunanya adalah memberi tahu bahwa ada aset keluar dari batas
wilayahnya. Kini `Promise.allSettled` dengan status per bagian: yang berhasil
tetap tampil, yang gagal mengatakannya sendiri berikut tombol Coba lagi. Kalimat
"tidak diketahui — jangan disimpulkan aman" menggantikan jaminan palsu itu di
keempat tab, termasuk *"Daftarkan perangkat lebih dulu"* di tab Pagar Area yang
juga hanya benar bila daftarnya memang terbaca kosong.

### 3. Editor denah: kanvas putih permanen tanpa jalan pulih

Bila `GET /spasial/node/{id}` gagal, `map.setView` tak pernah dipanggil dan peta
tinggal kanvas kosong. Satu-satunya jejaknya adalah toast yang padam beberapa
detik kemudian; pemulihannya hanya menutup lalu membuka ulang dialog. Pesan kini
MENETAP dengan tombol Coba lagi.

Dua hal yang menyertainya:

- Watchdog dulu berjanji *"Anda tetap bisa menggambar"* — tidak benar sebelum
  peta terposisi: tanpa pusat+zoom, Leaflet melempar pada hampir semua operasi.
  Kini janji itu hanya diucapkan bila `setView` memang sudah terjadi. Ambangnya
  juga dinaikkan di atas akumulasi dua tenggat BERURUTAN (detail node → induk):
  pada 25 detik, pemuatan 2G yang SEHAT (15 dtk + 12 dtk) menyalakan alarm palsu
  dua detik sebelum datanya tiba — dan tombol Coba lagi di layar palsu itu
  membuang kemajuannya lalu memulai dari nol, berulang: livelock.
- Percobaan ulang membersihkan grup gambar lebih dulu. Tanpa itu, percobaan yang
  gagal di tengah meninggalkan poligonnya di grup dan simpan berikutnya menulis
  bentuk **ganda**.
- **Peringatannya kini DITEGAKKAN.** Overlay galat hanya menutupi kotak peta;
  bilah aksi di bawahnya saudaranya dan tetap bisa diklik. Urutan berikut
  menghapus data asli dari server: pemuatan gagal (grup gambar kosong) →
  "Kosongkan" → `kotor` jadi true → "Simpan Denah" hidup lagi → sinyal sudah
  pulih sehingga GET segar berhasil → PUT mengirim geometri kosong, dengan toast
  hijau. Kedua tombol itu kini mati selama pemuatan gagal.

### 4. Sinkron luring: kegagalan SESAAT tak lagi membatalkan seluruh tarikan

`syncSnapshot` menarik satu kegiatan dalam puluhan halaman berurutan — dan
dilakukan tepat sebelum berangkat ke lapangan, sering di sinyal terburuk. Dulu
satu halaman yang gagal sekali membatalkan seluruh sinkron dan petugas berangkat
tanpa cache. Tiap halaman kini diulang otomatis (`muatAndal`); aman karena ini
GET dan kursor keyset-nya tak bergerak sebelum halamannya berhasil.

> **Batas klaim ini.** Kegagalan yang BERTAHAN (tiga percobaan habis, atau 401
> yang memang tak layak diulang) tetap membatalkan sinkron, dan karena `meta`
> tak pernah ditulis, halaman-halaman yang sudah tersimpan belum dilayani.
> Melanjutkan sinkron sebagian belum dikerjakan.

Dua hal menyertainya, keduanya menutup jalur **kehilangan baris luring**:
tenggat per halaman ditahan di 20 dtk (bukan 60) supaya satu halaman menahan
sinkron paling lama ~63 dtk alih-alih ~3 menit; dan `syncSnapshot` kini
**satu-aliran per kegiatan**. Ia tak bisa dibatalkan — cleanup pemanggil hanya
menyetel penanda — sehingga petugas yang menyimpulkan macet lalu memulai ulang
mode inventarisasi dapat menjalankan dua sinkron FULL sekaligus; yang selesai
belakangan menghitung `stale` versinya sendiri dan MENGHAPUS baris sah yang
ditulis jalankan lain.

### 5. Antrean scan opname mengosongkan diri saat sinyal pulih — **selama dialog Opname terbuka**

Antrean itu lahir tepat ketika jaringan mati. Dulu satu-satunya cara
mengosongkannya adalah menekan "Kirim ulang" — petugas harus INGAT. Yang tak
terkirim tak pernah masuk rekonsiliasi: barang tercatat *tidak ditemukan*
padahal sudah dipindai. Kini dipicu event `online`; aman diotomatiskan karena
`scan_id` adalah kunci idempotensi server.

Cakupannya dinyatakan terus terang di judul: pendengarnya hidup di dalam
`OpnameDialog`, jadi antrean tetap diam bila dialognya sudah ditutup.
Memindahkannya ke tingkat aplikasi belum dikerjakan.

Tiga hal yang membuat otomatisasi ini tak berbalik jadi masalah:

- **`checkReachable()` lebih dulu.** Event `online` hanya berarti antarmuka
  jaringan naik — captive portal, satu bar sinyal. Tanpa pemeriksaan, 30 baris
  antrean berarti 30 POST berurutan yang masing-masing menunggu tenggat 20 dtk:
  sepuluh menit tombol Catat/Terapkan mati dan badai 30 toast, tanpa petugas
  menyentuh apa pun. Plus peredam 3 detik terhadap kedip online/offline.
- **Nada toast mengikuti hasil.** *"0 dari 30 scan terkirim"* dulu terbit HIJAU
  bergaya keberhasilan. Kini merah bila nol, kuning bila sebagian.
- **Umur entri antrean tak lagi ter-reset** tiap kali disimpan ulang, sehingga
  plafon 7 hari benar-benar berlaku meski rekonek terjadi terus.

### 6. "Sesi berakhir", bukan "Invalid authorization header"

401 pada antrean simpan menampilkan pesan mentah server, yang terbaca seperti
kerusakan aplikasi. Kini: *"Sesi berakhir — masuk kembali lalu tekan Sinkronkan.
Data Anda masih tersimpan di perangkat."* **403 sengaja tidak ikut**: itu hak
akses (viewer, satker lain), bukan sesi habis — masuk ulang tak menolongnya.

### 7. Penjaga urutan respons — SBSK ruang DAN Pelacakan

Mengganti lingkup memicu muatan baru sementara yang lama masih terbang. Balasan
LAMA yang gagal menghapus data lingkup BARU yang sudah tampil.

Kelas yang sama ternyata DIBUKA oleh butir 2 di atas, dan tinjauan adversarial
atas komit ini yang menemukannya. Dengan `Promise.all`, jalankan yang gagal
melompat ke `catch` dan tak menulis state sama sekali — balasan basi karena itu
tak berbahaya. `allSettled` menghapus korsleting itu: setiap jalankan kini selalu
menulis. Urutan yang terperagakan: halaman dibuka (jalankan A, satu endpoint
menggantung) → operator mendaftarkan perangkat → jalankan B selesai cepat dan
perangkat baru tampil → A mendarat terakhir dengan potret lama dan **menghapus
perangkat itu dari layar**, tanpa toast, tanpa galat. `PelacakanPage.muat()` kini
memakai penjaga yang sama, dan tombol "Coba lagi" diredam selagi memuat.

### 8. Lencana berhenti menjamin apa yang tak terbaca

Kegagalan bagian dulu hanya terlihat DI DALAM tabnya sendiri, sementara badge
"N baru" di header dan angka di tab Peringatan diam — dan toast galat global
yang lama ikut hilang bersama `Promise.all`. Operator yang duduk di tab
Perangkat membaca ketiadaan badge sebagai "tak ada peringatan baru". Jumlah
belum-dibaca kini bernilai **tidak diketahui** (bukan nol) saat daftarnya gagal,
dan lencananya berubah jadi penanda `?` kuning. Tab Pagar Area & Izin Darurat
juga menerangkan mengapa tombolnya mati, alih-alih hanya menyembunyikan kalimat
lama.

**Uji:** 1.330 backend, 268 frontend, lint & build bersih.

**Belum dikerjakan (jujur dicatat):**

- 21 `React.lazy` BERSARANG (dialog & panel di DashboardPage, SpasialMasterPage,
  PejabatPage, ActivitySelectionPage, PerencanaanPage, WasdalPage) masih memakai
  `<Suspense>` telanjang. Potongan salah satunya yang gagal diunduh menembus ke
  boundary tingkat App, sehingga SELURUH halaman induk ter-unmount berikut pohon
  node yang sudah dijelajah / seleksi batch yang sedang dikerjakan. Jadi judul
  entri ini benar untuk layar putih, tetapi granularitas pemulihannya berhenti
  di batas halaman.
- Pohon node masih ditarik utuh alih-alih mekar-per-cabang lewat `parent_id`
  (backend sudah mendukungnya); indeks geo belum berawalan `kode_satker`.
- Service worker belum mem-precache potongan halaman, jadi halaman yang belum
  pernah dibuka saat daring tetap gagal saat luring — kini setidaknya dengan
  pesan yang benar dan tombol, bukan layar putih.
- Rekonsiliasi `stale` pada sinkron penuh masih memakai selisih himpunan mentah,
  jadi baris yang ditulis `upsertSnapshotAsset` DI TENGAH sinkron bisa
  digolongkan usang. Penjaga satu-aliran menutup jalur yang paling mudah dipicu;
  akarnya (bandingkan terhadap `syncStartedAt`) belum.

---

## [#662] Keandalan gelombang 2 — sisi server: izin sebelum pemotongan, sortir berbatas, payload dilangsingkan — 2026-07-28

Lanjutan `[#661]`. Gelombang pertama membereskan sisi klien (tenggat, coba-ulang,
layar yang jujur); gelombang ini membereskan yang menyebabkan permintaannya
lambat atau salah sejak di server.

### 1. Izin dijalankan SEBELUM pemotongan — dan bukan lagi N+1

`GET /spasial/node/{id}/isi` dulu:

```python
rows = ...find(...).to_list(500)          # dipotong DULU
for r in rows:
    await pastikan_akses_aset(user, r)    # baru disaring
```

Dua cacat sekaligus, dan keduanya nyata:

- **BENAR.** Pemotongan mendahului penyaringan. Bila 500 baris teratas kebetulan
  milik satker lain, pengguna menerima jauh kurang dari yang BERHAK ia lihat —
  dan angka itulah yang dipakai untuk opname fisik.
- **CEPAT.** `pastikan_akses_aset` menembak `inventory_activities.find_one`
  untuk TIAP baris: sampai **500 perjalanan bolak-balik berurutan** hanya untuk
  membuka isi satu ruangan.

Penyaring kini berjalan di dalam kueri. Memindahkan aturan otorisasi berarti
**menyalinnya**, dan salinan bisa menyimpang diam-diam — karena itu ujinya tidak
berhenti pada "hasilnya benar": `test_kueri_izin_SETARA_gelung_guard_asli`
menjalankan kueri baru DAN gelung guard yang asli atas fixture yang sama, lalu
menuntut hasilnya identik. Fixture-nya mencakup seluruh cabang aturan: kegiatan
milik satker, milik satker lain, kegiatan era-lama tanpa stempel, aset tanpa
kegiatan, dan aset **yatim** (kegiatan induk sudah dihapus — tetap fail-closed,
sesuai REVIEW-9 R15).

### 2. `.sort()` tanpa `.limit()` di `/spasial/geojson`

`to_list(N)` hanya membatasi berapa dokumen yang DIBACA klien; kursornya sendiri
tak berbatas, sehingga MongoDB menyortir SELURUH hasil cocok lebih dulu. Sortir
tanpa indeks penopang berjalan di memori dengan plafon 100 MB — pada satker
ber-denah lengkap kueri ini bisa gagal seluruhnya dengan *"Sort exceeded memory
limit"*: **peta kosong, bukan peta lambat.** Limit kini ikut turun ke server.

### 3. Payload daftar node dilangsingkan — dan bahaya yang menyertainya

`properties` dibuang dari proyeksi `GET /spasial/node`. Ia menyimpan
`properties.impor.atribut` — puluhan kunci berisi ratusan karakter **per node** —
dan tak satu pun layar yang memakai daftar itu membacanya.

> **Yang hampir terlewat.** `DenahEditor` memakai item DAFTAR sebagai cadangan
> dasar `PUT /spasial/node/{id}`, dan PUT mengganti SELURUH field. Melangsingkan
> daftar tanpa membereskan itu akan **menghapus jejak audit impor dan denah
> overlay** node yang disimpan — kehilangan data senyap. Cadangan itu kini
> dicabut: bila tak ada dasar lengkap, penyimpanan DITOLAK dengan pesan jelas,
> dan gambar operator tetap di layar.

### 4. Pemotongan 20.000 node tak lagi senyap

Daftar berhenti di plafon tanpa penanda apa pun. Karena urutannya menaik menurut
`ordinal_level`, yang hilang justru tingkat **terdalam** (ruangan) — persis yang
paling dibutuhkan opname. Kini ada `terpotong`/`batas`, dan layar memberi tahu.
Penanda itu diperoleh dengan mengambil satu baris lebih banyak, bukan dengan
`count_documents` kedua atas kueri yang sama.

### 5. `max_time_ms` sisi server

Dipasang **di bawah** tenggat klien (15 dtk vs 20 dtk). Tanpa ini server tetap
membanting CPU untuk permintaan yang klien-nya sudah menyerah dan sudah mencoba
ulang — beban berlipat justru saat jaringan buruk, yaitu saat kapasitas paling
dibutuhkan.

**Uji:** 1.330 backend (+8), 258 frontend, lint & build bersih. Dua mutasi
diperiksa pada jalur izin (urutan potong-saring dikembalikan; penyaring
dilonggarkan) — tertangkap 2 dan 5 uji.

---

## [#661] Keandalan pemuatan node & konteks — tenggat, coba-ulang, dan layar yang berhenti berbohong — 2026-07-28

Pemilik bertanya: *"bagaimana cara membuat handal saat memuat data node agar tidak
sering terjadi gagal, dan juga saat memuat konteks."*

Analisis lima dimensi (frontend node, backend spasial, konteks, lapisan jaringan,
pola baku) mengajukan **79 temuan**; **57 lolos** verifikasi dua penilai berlensa
berbeda. Gelombang pertama ini menutup akar terbesarnya.

### Akar #1 — satu baris yang tidak pernah ada

```
axios.defaults.timeout  →  tidak pernah dipasang di mana pun
axios.get di seluruh aplikasi: 227 panggilan — hanya 14 menyebut timeout
```

Di jaringan lapangan, bentuk kegagalan yang paling sering **bukan** "koneksi
ditolak" — itu cepat dan tertangkap `catch`. Yang paling sering adalah koneksi
**menggantung**. Tanpa tenggat, `await` tak pernah selesai: `catch` tak jalan,
`finally` tak membereskan spinner, operator menatap loading tanpa akhir.

Efek berantainya lebih buruk lagi — **penjaga yang sudah ada ikut mandul.**
`ImporDenahDialog` punya pagar "8 kegagalan beruntun / 15 menit", tetapi keduanya
hanya dievaluasi setelah permintaan **selesai**. Server yang menggantung membuat
rantai polling berhenti diam-diam tanpa pernah menyentuh pagar itu, dan pesan
"berhenti memantau ≠ berhenti mengimpor" yang sudah disiapkan tak pernah muncul.

Ditutup dengan lantai tenggat global (`TENGGAT_BAKA`, tetap bisa dinaikkan
per-request untuk unggahan) + `lib/muatAndal.js`.

### Akar #2 — kegagalan dirender sebagai kekosongan

Ini yang membuat gejalanya membingungkan, bukan sekadar mengganggu:

| Berkas | Yang dilihat operator saat jaringan gagal |
|---|---|
| `IsiNodeDialog` | "Belum ada aset yang ditempatkan di sini" · **0 aset** |
| `SbskRuangPanel` | "Belum ada gedung/lantai bergeometri — gambar denahnya dulu" |
| `SatkerAktifBar` | "Belum ada satker di Master Satker" |
| `SpasialMasterPage` | "Belum ada data. Mulai dari tingkat teratas" |

Semuanya **pernyataan yang layar itu tak punya dasar untuk membuatnya**. Yang
paling berbahaya `IsiNodeDialog`: ia menulis `{items: [], jumlah: 0}` di blok
`catch`, sehingga petugas opname bisa menyimpulkan ruangan memang kosong.

Kini tiap layar membedakan "kosong" dari "gagal", menyebut sebabnya (sinyal /
server lambat / kuota / sesi), dan menyediakan **Coba lagi**.

### Akar #3 — tak ada coba-ulang, dan balapan permintaan

Satu kedip sinyal dulu berakhir sebagai layar kosong, dan satu-satunya pemulihan
adalah keluar-masuk halaman. `muatAndal` mengulang **hanya** kegagalan sementara
(jaringan/tenggat/5xx/429) dengan backoff ber-jitter — jitter itu wajib: saat
sinyal pulih di satu lokasi, seluruh regu mencoba ulang pada detik yang sama.
4xx dan 401 tidak diulang: mengulang tak akan menolong dan hanya menunda pesan
galat (atau menunda logout).

Penjaga urutan ditambahkan di `SpasialMasterPage` dan `IsiNodeDialog`. Yang
kedua nyata akibatnya: saklar "termasuk isi di bawahnya" bisa membuat balasan
`dalam=true` (isi SELURUH gedung) mendarat belakangan dan tampil sebagai isi
satu ruangan — angka yang salah untuk opname fisik.

**Uji:** 258 frontend (+19), lint & build bersih. Dua mutasi diperiksa pada
logika coba-ulang (4xx ikut diulang; jeda antar percobaan dihapus) — keduanya
tertangkap.

**Yang sengaja belum dikerjakan** (gelombang berikutnya): paginasi/lazy-expand
`/spasial/node` (backend sudah mendukung `parent_id`), `.limit()` sebelum
`.sort()` di `/spasial/geojson`, N+1 pada `/spasial/node/{id}/isi`, penanda
`terpotong` di plafon 20.000 node, dan `max_time_ms` sisi server.

---

## [#660] Impor GIS multi-node, kanvas terpotong, rekap SIMAN per kegiatan, bilah satker bertahan — 2026-07-28

Empat laporan lapangan dari satu layar dan satu keluhan alur. Tiga di antaranya
berakar pada hal yang sama: **penjaga yang dipasang di tempat yang salah.**

### 1. Impor 6 poligon, 1 jadi, 5 dilewati (`topologi_utils.py`)

Pesannya berbunyi *"geometri terlalu besar (> 20.000 titik) — sederhanakan
bentuknya atau pakai jalur impor file (perbaikan otomatis gagal)"* — disampaikan
kepada operator yang **sedang memakai jalur impor file**.

Plafon 20.000 verteks itu dipasang untuk melindungi `make_valid`. Pengukuran
ulang di repo ini menunjukkan ia memagari sumbu yang keliru: biaya GEOS nyaris
tak ditentukan jumlah verteks, melainkan **jumlah persilangan-diri**.

| bentuk | `is_valid` | `make_valid` |
|---|---|---|
| poligon sah 200.000 verteks | 1,3 ms | 3,2 ms |
| poligon sah 500.000 verteks | 3,9 ms | 10,8 ms |
| bintang patologis **201** verteks | ~1 ms | **1.650 ms** |
| bintang patologis **501** verteks | — | **> 20 detik (dibunuh)** |
| bintang patologis 20.001 verteks | 126 ms | — |
| bintang patologis 100.001 verteks | 7.644 ms | — |

Dua akibatnya nyata sekaligus: plafon itu **menolak data sah yang murah**
(poligon batas wilayah 500.000 verteks divalidasi dalam 3,9 ms), dan
**tidak memagari `make_valid` sama sekali** (bintang 501 verteks — jauh di bawah
plafon — berjalan tanpa batas). Ia memberi rasa aman palsu justru pada operasi
yang paling berbahaya.

Perbaikan: plafon verteks diturunkan perannya menjadi batas kewarasan **memori**,
dan yang memagari **biaya** kini **tenggat waktu keras** di proses terpisah.
Prosesnya harus dibunuh, bukan di-`signal`: percobaan pertama memakai
`signal.setitimer` gagal total — penangan sinyal Python tak pernah dapat giliran
selama eksekusi berada di dalam panggilan C GEOS, dan benchmark-nya sendiri yang
harus dibunuh dari luar. (GEOS sendiri MELEPAS GIL — terukur: thread lain tetap
berdetak tiap 11 ms — jadi `asyncio.to_thread` memang menyelamatkan event loop,
tetapi kerjanya tetap membakar satu inti tanpa batas.)

Pesan galatnya ditulis ulang agar menyebut angka sebenarnya dan memberi saran
yang bisa dikerjakan (QGIS ▸ Simplify), dan jalur impor berhenti menempelkan
"(perbaikan otomatis gagal)" pada penolakan ukuran — perbaikan memang tak pernah
dicoba di kasus itu.

### 2. Informasi kanvas terpotong setelah impor (`ImporDenahDialog.jsx`)

Baris "dilewati" memakai `truncate` (`white-space: nowrap`), sementara
`DialogContent` adalah CSS **`grid`** ber-**`overflow-hidden`**. Anak grid
ber-`min-width: auto`, jadi baris yang tak bisa menyusut melebarkan trek grid
melewati lebar dialog dan `overflow-x: hidden` memotongnya **tanpa menyisakan
bilah gulir**. Terukur di Chromium: isi 956 px di dalam kotak 440 px — 516 px
keterangan hilang, persis pada bagian yang menjelaskan KENAPA node gagal.

Alasan kini dibungkus penuh, daftar panjang digulir, dan `[&>*]:min-w-0` menutup
seluruh kelas bug itu — bukan hanya satu barisnya.

### 3. Sinkronisasi SIMAN V2 tanpa pembagian per kegiatan

Angka global ("12 selisih") benar tetapi tak bisa ditindaklanjuti begitu satker
punya banyak kegiatan inventarisasi: operator tahu ada selisih, tak tahu
kegiatan mana yang harus dibuka. Ditambah rekap per kegiatan (satu pipeline
agregasi, bukan N kueri), penyaring `activity_id` pada daftar selisih, dan nama
kegiatan di tiap baris.

> **Temuan keamanan saat mengerjakannya.** Versi pertama penyaring menulis
> `{**q, "activity_id": pilih}` — dan `scope_query_aset` menegakkan isolasi
> satker JUSTRU dengan kunci itu, sehingga penyaring tampilan berubah menjadi
> **IDOR**: pengguna satker A cukup menyebut id kegiatan satker B untuk membaca
> asetnya. Ditangkap oleh uji yang ditulis bersamaan
> (`test_penyaring_tak_bisa_menembus_batas_satker`) dan ditutup dengan
> menggabungkan lewat `$and`, sehingga penyaring hanya bisa MEMPERSEMPIT.

### 4. Bilah Satker Aktif dirapikan + hanya bisa ditarik dari header

Bilah ini menyatakan sebagai satker mana seluruh aplikasi sedang bekerja, jadi
membukanya harus disengaja. Kini tertutup rapi secara bawaan dan hanya terbuka
lewat **tarikan berat pada pitanya** — teredam asimtotik (tarikan 72 px hanya
menggerakkan ±14 px) dengan ambang dinilai dari jarak **mentah**. Satu jalur
Pointer Events, jadi tetikus dan layar sentuh berperilaku sama persis;
`touch-action: none` pada pegangan supaya usapan vertikal di HP tidak diserobot
gulir halaman. Indikator kemajuan mencegah redaman terasa seperti macet, dan
Enter/Space tetap tersedia agar pengguna papan ketik tak terkunci keluar.

**Uji:** 1.322 backend (+9), 239 frontend (+14). Tiga mutasi diperiksa pada
pagar topologi dan satu pada pesan impor — semuanya tertangkap.

---

## [#659] Kompresi PDF yang tak pernah berjalan — dan foto bukti yang diam-diam rusak — 2026-07-28

Pemilik bertanya sederhana: *"apakah kompresi Compresto, Uploadcare, iLoveAPI,
WhipDoc sudah berjalan?"* Jawabannya untuk PDF: **tidak, dan tak pernah.**

### Dua host yang tidak ada

`api.iloveapi.com` dan `api.whipdoc.com` gagal resolusi DNS. Cara temuan itu
diperoleh ditulis di kodenya supaya bisa diperiksa ulang: enam host
diresolusi lewat dua resolver; empat berhasil — **termasuk domain telanjang
`iloveapi.com` dan `whipdoc.com`, jadi mereknya memang ada** — sementara
persis kedua subdomain `api.*` gagal. Panggilan HTTP tak sah sebagai bukti di
sini: kebijakan jaringan CI menolak CONNECT ke semua host penyedia, jadi
kegagalan HTTP tidak membedakan apa pun.

Akibatnya seluruh rantai mati, **tetapi endpoint tetap menjawab 200** dengan
PDF asli dan `X-Compression-Method: none`. Kegagalan total tak bisa dibedakan
dari "PDF ini memang sudah optimal", dan tak seorang pun pernah tahu.

### Alurnya juga bukan 4 langkah, melainkan 5

Kontrak iLovePDF v1 yang benar: `auth` → `GET /v1/start/compress` → `upload`
→ `process` → `download`, dengan `Authorization: Bearer` di langkah 2-5. Kode
lama tak pernah mengambil token, tak pernah mengirim Authorization, memanggil
`/v1/start` sebagai POST ber-body padahal nama alat ada di **path**, dan buta
terhadap kegagalan yang datang sebagai **HTTP 200 ber-status `TaskError`**.

Token kini JWT self-signed HS256: **secret key menandatangani secara lokal
dan tak pernah menyentuh jaringan.**

### WhipDoc diganti jaring pengaman lokal

Jalur gambar punya Pillow sejak awal; jalur PDF tidak — dan justru ketiadaan
itu yang membuat matinya penyedia tak terdeteksi. `pypdf` (sudah ada di
`requirements.txt`) kini memegang peran itu.

Kompresi lossy dipasang atas persetujuan pemilik, di dalam pagar yang dipilih
sadar karena dokumen BMN adalah bukti hukum:

| PDF | Sebelum | Sesudah | Hemat |
|---|---|---|---|
| Lampiran 6 hal, 12 foto 12MP | 87,7 MB | 7,9 MB | −91% |
| Mirip scan 300 DPI | 41,7 MB | 5,4 MB | −87% |
| Teks/tabel | 10,0 KB | 8,2 KB | −17% |

Yang **tidak** disentuh: gambar di bawah 700 px (logo, stempel, QR, spesimen
tanda tangan), gambar bitonal, dan **PDF ber-TTD digital** — menulis ulang
strukturnya membatalkan tanda tangannya, dan dokumen batal lebih buruk
daripada dokumen besar. Hasil dibuang bila teks terekstraksi menyusut di
bawah 98%, bila jumlah halaman berubah, atau bila hematnya di bawah 3%.

### Tiga kerusakan pada foto bukti inventarisasi

- **Orientasi EXIF dibuang.** Kamera HP menyimpan foto dalam orientasi sensor
  lalu menandai putarannya di EXIF. Karena blok EXIF tak ikut disimpan, foto
  tersimpan **miring permanen** — dan tanpa tag itu tak ada lagi informasi
  untuk membetulkannya otomatis.
- **PNG transparan dipaksa JPEG.** Pindaian, tangkapan layar SIMAN, dan
  spesimen tanda tangan potong kehilangan transparansi dan mendapat artefak
  pada garis tipis.
- **Tanpa plafon piksel:** berkas 81 megapiksel didekode utuh ke RAM sebelum
  apa pun diperiksa.

### Yang membuat semua ini bisa bertahan begitu lama

`tinify.from_buffer()` — yang **itu sendiri** melakukan POST sinkron —
dijalankan di event loop; hanya `.to_buffer` yang dilempar ke thread. Seluruh
API membeku selama tiap unggahan foto, dan gejalanya tampak seperti "server
lambat", bukan seperti kompresi yang memblokir.

`available` pada endpoint kuota berarti **"env var tidak kosong"**. Layanan
yang host-nya tidak ada pun tampil hijau dengan sisa 250 selamanya. Kini
hijau menuntut bukti panggilan yang berhasil.

Endpoint kompresi memakai `require_user` tanpa rate-limit — pengguna
**read-only** pun bisa menguras kuota berbayar satker dengan mengulang
unggahan. Kini `require_writer` + 12/menit.

`activities.py` adalah kembaran endpoint kompresi yang berjalan **tanpa satu
pun penjaganya**: tanpa batas 25 MB, tanpa cek magic byte. Seluruh validasi
bisa dilewati hanya dengan mengirim dokumen sebagai base64 di payload
kegiatan. Satu pintu berpenjaga tak ada gunanya bila pintu sebelahnya
terbuka lebar.

### Verifikasi

1.304 uji backend (17 baru). **Lima mutasi** dibuktikan tertangkap: host
dikembalikan ke `api.iloveapi.com`; header Authorization dicabut; gerbang
`TaskSuccess` dibuang; `exif_transpose` dibuang; PNG transparan diratakan
lagi.

**Batas yang dinyatakan terus terang:** uji memakai `httpx.MockTransport`,
bukan jaringan — kebijakan CI menolak CONNECT ke semua host penyedia. Yang
bisa dijaga hanyalah **bentuk permintaan yang kita kirim** dan cara kita
menafsirkan jawaban; bahwa iLovePDF benar-benar menerimanya **tidak** dapat
dibuktikan di sini. Karena itu ada `scripts/verifikasi_kompresi_pdf.py`,
dijalankan sekali di VPS setelah kunci dipasang. Tanpa langkah itu, klaim
"kompresi berjalan" adalah klaim yang tak berdasar — persis seperti keadaan
yang baru saja diperbaiki.

---

## [#658] Audit alur lintas-modul — pintu belakang, dokumen yatim, muatan siluman — 2026-07-28

Pemeriksaan menyeluruh atas rantai **Pengadaan → Pencatatan → LPB → TTD**
dan atas optimalisasi peta yang baru dipasang, mencari alur yang terlewat,
langkah yang ambigu, dan janji yang tak ditepati.

### Penjaga yang bisa dilangkahi bukan penjaga

Penjaga golongan yang dipasang di jalur otomatis ternyata punya **pintu
kedua**. `tautkan_barang` menulis `asset_id` ke baris `barang[]` yang sama —
tanpa memeriksa apa pun, termasuk ke baris yang sudah memegang `psd_item_id`.
Satu rim kertas HVS lalu berdiri di kartu stok **dan** sebagai BMN ber-NUP
sekaligus, keduanya berjurnal ke Neraca. Persis kerusakan yang penjaga itu
dipasang untuk mencegah, lewat tombol di sebelahnya.

Baris yang sudah di kartu stok, dan baris berkode golongan 1, kini ditolak
dengan pesan yang bisa ditindaklanjuti. **Melepas** tautan tetap boleh: data
lama yang telanjur salah harus bisa dibetulkan, bukan dikunci permanen.

Layarnya ikut berhenti mengundang. Baris yang sudah tercatat sebagai
persediaan dulu berbunyi *"Belum tertaut ke aset master"* — kalimat yang
menyuruh operator melakukan persis pencatatan ganda itu — dan menyodorkan
tombol "Tautkan" yang kini pasti gagal. Keduanya diganti keadaan **ketiga**
yang jujur: *"Tercatat sebagai persediaan (kartu stok)"*.

### LPB yang terbit lalu hilang

"Catat Semua Barang" menerbitkan LPB, menyebut nomornya di dalam toast, dan
selesai. Beberapa detik kemudian nomor itu lenyap, dan satu-satunya jalan
mencetak dokumen resmi tersebut adalah berpindah ke **Persediaan → Riwayat
LPB** — modul lain, untuk dokumen yang baru saja Anda buat.

Kini alurnya berakhir dengan dialog ber-tombol **Unduh PDF** dan **Kirim
TTD**, lengkap dengan tautan penanda tangan yang ditampilkan apa adanya.
Loop-nya ditutup di tempat pekerjaannya terjadi; Riwayat LPB tetap ada
sebagai pintu masuk kedua, bukan satu-satunya.

### Muatan siluman di daftar node — regresi dari perbaikan sendiri

Daftar node sengaja membuang `geometry` karena poligon kawasan bisa ribuan
verteks dan daftar itu memuat sampai 20.000 node sekaligus. **`geometry_opt`
lolos dari proyeksi itu.** Per node ia memang jauh lebih ringan, tetapi
ratusan verteks dikali puluhan ribu baris tetap payload raksasa — di daftar
yang tak satu pun layarnya menggambar poligon.

Yang dibutuhkan layar hanya satu boolean, jadi itulah yang diturunkan:
`dioptimalkan`. Ia sekaligus menutup lubang alur — "Ringankan Peta" dulu
hanya melaporkan angka di toast, tanpa cara melihat denah **mana** yang
masih berat. Kini tiap baris berbadge "ringan" / "belum ringan".

Hal yang sama berlaku di peta: pada mode `asli=1`, `geometry_opt` tak pernah
dikirim maupun dibaca, jadi ia berhenti ditarik dari basis data sama sekali.
Menambah ±13% pada payload terberat, di endpoint yang seluruh alasan
keberadaannya memangkas berat itu, adalah lelucon yang mahal.

### Editor selalu menyunting yang asli

`GET /spasial/node/{id}` berhenti menyerahkan `geometry_opt`. Bila ikut
terkirim, cepat atau lambat ada layar yang memakai "geometri mana pun yang
tersedia", dan penyimpanan berikutnya menuliskan versi sederhana ke atas
geometri asli — penyederhanaan yang seharusnya bisa dibatalkan berubah jadi
permanen, tanpa satu pun galat.

### Jalur simpan tak boleh membekukan server

Endpoint optimasi massal melempar shapely ke thread sejak awal, dengan alasan
yang ditulis terang-terangan: *"satu satker ber-2.000 poligon tak boleh
membekukan seluruh server"*. Jalur **simpan** menjalankan pekerjaan yang sama
langsung di event loop — sembilan anak tangga toleransi, masing-masing
`simplify` + jarak Hausdorff — hanya karena poligonnya "cuma satu". Untuk
hasil impor SHP berverteks puluhan ribu, satu penyimpanan menahan setiap
permintaan pengguna lain yang tak ada urusannya dengan peta.

`_terapkan_geometri_async` kini dipakai kedua handler simpan node. Logika
penulisannya dipisah ke `_pasang_optimasi` agar jalur sinkron dan jalur thread
tak punya dua salinan yang bisa berbeda diam-diam.

### Plafon yang salah satuannya

`POST /spasial/optimasi` dibatasi **500 node per panggilan** — plafon yang
mengabaikan bahwa biaya per poligon berbeda satu orde besaran menurut jumlah
verteksnya. Diukur: **34 ms** untuk 1.000 verteks, **155 ms** untuk 5.000,
**613 ms** untuk 20.000. Untuk denah gambar-sendiri, 500 node adalah 17 detik;
untuk hasil impor SHP, **77–307 detik** — jauh melewati batas waktu proxy
lazim. Operator melihat galat 504 sementara servernya justru masih bekerja,
dan sebagian pekerjaan sudah tersimpan tanpa pernah dilaporkan.

Plafonnya kini **anggaran waktu** (20 detik), dengan cacah node tinggal
sebagai pagar terluar. Ia menyesuaikan diri: poligon kecil → banyak per
tekan, poligon raksasa → sedikit. Anggaran diperiksa **sesudah** satu node
selesai, sehingga anggaran sekecil apa pun tetap menghasilkan kemajuan —
kalau tidak, "tekan sekali lagi" menjadi lingkaran yang tak pernah maju.

Satu lubang lagi di saringan kandidatnya: ia memilih node ber-`geometry_opt`
kosong, padahal **poligon sederhana memang tak pernah menghasilkan versi
ringan** — kotak lima titik tak punya apa pun untuk dihemat. Node semacam itu
terpilih lagi pada setiap tekanan, selamanya; satker yang denahnya digambar
tangan akan terus disuruh "tekan sekali lagi" tanpa satu pun kemajuan yang
terlihat. Saringannya kini `optimasi` — "sudah pernah dicoba" — dan percobaan
yang tak menghasilkan apa-apa tetap dicatat.

### Verifikasi

1.287 uji backend, eslint 0 galat, build kompilasi. **Empat mutasi**
dibuktikan tertangkap: membuang penjaga `tautkan_barang` → 2 uji gagal;
mengembalikan `geometry_opt` ke proyeksi daftar node → 1 uji gagal;
mengembalikan `geometry_opt` ke detail node → 1 uji gagal; jalur thread lupa
memasang hasil optimasinya → 3 uji gagal; anggaran waktu diabaikan → 1 uji
gagal; anggaran diperiksa SEBELUM node pertama (tak pernah maju) → 1 uji
gagal; saringan kandidat kembali memakai `geometry_opt` → 1 uji gagal;
percobaan yang tak menghasilkan apa-apa tak dicatat → 1 uji gagal. Tiga uji lain (`baris aset tetap boleh ditautkan`, `melepas tautan
tetap boleh`, `pekerjaan tuntas tak mengaku terpotong`) menjaga agar
penjaganya tak diam-diam membunuh alur yang benar.

---

## [#657] Optimalisasi peta gaya mapshaper — ringan di layar, asli tetap utuh — 2026-07-28

Denah kawasan hasil impor SHP membawa ribuan verteks per poligon. Di HP
lapangan itu berarti peta yang tersendat setiap kali digeser. Pendekatan
mapshaper.org diadopsi — **sederhanakan geometri**, **kurangi presisi desimal**,
**muat per bounding box** — dengan satu syarat mutlak dari pemilik: **berkas
asli tidak pernah dihapus.**

### Salinan, bukan penggantian

Penyederhanaan ditulis ke field **baru** `geometry_opt`; `geometry` tak pernah
disentuh. Begitu pula `bbox`, `titik_wakil`, dan `metrik.luas_m2` — luas SBSK,
deteksi lokasi otomatis, dan bahan ekspor QGIS tetap dihitung dari bentuk asli.
Menekan tombol optimasi dua kali tidak menggerus peta sedikit demi sedikit,
karena sumbernya selalu yang asli.

Yang mendasari seluruh berkas uji: **optimasi yang bocor ke `geometry` berarti
presisi survei terbuang tanpa bisa dipulihkan — dan tanpa satu pun galat.**

### Sweet spot: dicari, bukan ditebak

Toleransi tetap tidak bisa dipakai. Angka yang aman untuk kawasan 27 km akan
melenyapkan ruangan 10 m. Maka `optimalkan()` **menaiki tangga toleransi** dan
berhenti di anak tangga terbesar yang masih di bawah anggaran:

- **Pergeseran garis** (jarak Hausdorff) ≤ **0,35 m**, atau 0,005% diagonal
  objek untuk kawasan besar — mana yang lebih longgar.
- **Perubahan luas** ≤ **0,5%**.
- Poligon di bawah 12 titik **tidak disentuh**: tak ada yang bisa dihemat, dan
  penyederhanaan justru bisa merusaknya.

Hasil terukur pada tiga skala:

| Objek | Verteks | Hemat | Geser garis | Δ luas |
|---|---|---|---|---|
| Kawasan ±890 m | 1.001 → 129 | 87,1% | 0,144 m | 0,04% |
| Kawasan 27 km | 2.001 → 257 | 87,2% | 2,188 m | 0,01% |
| Ruangan ±11 m | 201 → 41 | 79,6% | 0,025 m | 0,42% |

Delta luas dipakai **bersama** jarak Hausdorff, bukan menggantikannya: dua sisi
poligon bisa bergeser berlawanan arah puluhan meter sementara luasnya persis
sama. Selisih luas saja akan menyatakan itu aman.

Metrik yang dilaporkan **diukur ulang setelah pembulatan presisi**, sebab
pembulatan terjadi sesudah penyederhanaan dan dapat menggeser garis lagi.
Melaporkan angka pra-pembulatan berarti menjanjikan ketelitian yang tidak
dimiliki geometri yang benar-benar tersimpan.

### Yang tampil di web selalu yang ringan — dengan saklar ke yang asli

- `GET /spasial/geojson` mengirim `geometry_opt` secara bawaan dan melaporkan
  `sumber`, `titik_dikirim`, `titik_asli`, serta `hemat_persen`. Node yang belum
  dioptimalkan **tetap muncul** dengan bentuk aslinya — peta tak boleh kosong
  hanya karena tombolnya belum ditekan.
- `?asli=1` adalah saklarnya. Di layar: tombol **Bentuk ringan / Bentuk asli**
  pada panel Lapis Denah, lengkap dengan angka penghematan yang sedang berlaku.
  Pilihannya sengaja **tidak** disimpan antar sesi — peta harus selalu terbuka
  dalam keadaan ringan.
- **Poligon yang digambar sendiri lewat web pun ikut**: `_terapkan_geometri`
  membuat versi ringannya pada setiap penyimpanan, tanpa operator perlu tahu
  tombol optimasi ada. Mengosongkan geometri ikut membuang salinannya — salinan
  yatim akan tergambar sebagai bentuk yang sudah tak ada.
- `POST /spasial/optimasi` (**Ringankan Peta**) memproses denah yang belum punya
  salinan; `paksa_ulang` untuk menghitung ulang semuanya. Ter-scope satker,
  ber-rate-limit, dan shapely dijalankan di thread agar event loop tak tertahan.

### Ekspor: bawaannya ASLI, dan itu disengaja

Berkas ekspor menjadi arsip cadangan dan bahan olah di QGIS. Diam-diam memberi
versi sederhana berarti presisi terkikis setiap putaran ekspor–impor. Maka
`geometri=asli` adalah bawaannya; pilihan **"Versi ringan (optimize)"** ada di
dialog ekspor, dan berkasnya diberi tanda `-optimize` **pada nama berkas** —
berkas berpindah tangan, sementara pilihan di layar tidak ikut berpindah.

Node yang belum dioptimalkan tetap ikut terekspor dengan bentuk aslinya:
berkas bolong lebih berbahaya daripada berkas yang sebagian berat.

### Editor selalu menyunting yang asli

`GET /spasial/node/{id}` **tidak** lagi menyerahkan `geometry_opt`. Bila ikut
terkirim, cepat atau lambat ada layar yang memakai "geometri mana pun yang
tersedia", dan penyimpanan berikutnya menuliskan versi sederhana ke atas
geometri asli — penyederhanaan yang seharusnya bisa dibatalkan berubah jadi
permanen. Konteks tetangga di DenahEditor memang memakai versi ringan (latar
orientasi, tak bisa diklik, tak ikut tersimpan), dan itu kini ditulis
terang-terangan sebagai `asli: 0`.

### Verifikasi

1.275 uji backend (39 baru), eslint 0 galat, build kompilasi. **Empat mutasi**
dibuktikan tertangkap: menulis hasil optimasi ke `geometry` → 3 uji gagal;
membuat ekspor diam-diam memakai versi ringan → 1 uji gagal; mengabaikan
saklar `asli` → 1 uji gagal; mengembalikan `geometry_opt` di detail node →
1 uji gagal.

---

## [#656] Rantai penerimaan barang: PPK, satu tombol catat, LPB aset ber-TTD — 2026-07-28

Tiga permintaan pemilik yang ternyata satu rantai: nama **PPK** tak pernah
tercantum, pencatatan dari Pengadaan menuntut operator memilah sendiri, dan
**LPB** hanya ada untuk persediaan — bukan untuk aset.

### Bug integritas yang ditemukan saat menyatukan dua jalur

Menekan **Daftarkan ke Persediaan** lalu **Buat Draft Aset** atas BAST yang
sama membuat satu rim kertas HVS **tercatat dua kali**: sekali di kartu stok,
sekali sebagai BMN ber-NUP — dan **keduanya berjurnal ke Neraca**.

`buat_draft_aset_dari_perolehan` menerima kode barang apa pun; ia hanya
melewati baris yang sudah punya `asset_id`, dan `psd_item_id` dari jalur
persediaan bukan `asset_id`. Jadi tak ada yang menahannya. Penjaga golongan
kini dipasang di **kedua** jalur, dan urutan penekanan tak lagi menentukan.

### PPK — dibekukan, bukan di-join saat baca

Peran `ppk` sudah lama ada di Referensi Pejabat tetapi tak pernah dipakai
Pengadaan maupun Persediaan. Kini:

- Register perolehan menyimpan snapshot **nama, NIP, jabatan, dan status
  kepegawaian** PPK. Kosong = server meresolusi sendiri peran `ppk` yang
  berlaku **pada tanggal BAST** — bukan hari ini, karena register sering diisi
  belakangan dan PPK hari ini belum tentu yang menandatangani.
- Snapshot ikut turun ke **aset** yang lahir dari BAST itu, ke **jurnal
  persediaan**, dan ke **LPB**. Menelusuri "atas komitmen siapa barang ini
  datang" tak lagi menuntut kueri balik.
- `PUT /pengadaan/{id}/ppk` melengkapi register lama tanpa membuat ulang
  dokumen, dan **memproyeksikan ulang** ke aset yang sudah tercatat.
- Pergantian PPK di kemudian hari **tidak** mengubah dokumen yang sudah terbit.

### Satu tombol: "Catat Semua Barang"

`POST /pengadaan/{id}/catat-semua` memilah sendiri berdasarkan digit pertama
kode barang (kodefikasi BMN): **golongan 1 → Persediaan**, **golongan 2–8 →
aset draft ber-NUP**. Baris **tanpa kode** jadi keranjang ketiga yang eksplisit
dan dilaporkan balik — bukan ditelan diam-diam.

Dialognya menampilkan hitungan **sebelum** ditekan, dan kegagalan sebagian
tetap muncul sebagai peringatan tersendiri: jalur ini memang tak transaksional
(Mongo standalone), dan toast hijau di atas separuh kegagalan adalah kebohongan
yang paling mahal di sini.

### LPB untuk aset, bukan hanya persediaan

- `db.lpb` kini ber-`kategori` (`persediaan` | `aset`). Dokumen lama tanpa
  field itu tetap terhitung persediaan — memfilter tak boleh menyembunyikan
  riwayat.
- LPB aset memuat **kolom NUP**: tanpa itu dokumen hanya berkata "5 printer
  diterima" dan tak bisa membuktikan printer **yang mana** — padahal itulah
  seluruh alasan BMN dinomori satu per satu.
- Nomor surat dipesan lewat helper **bersama** `booking_nomor_lpb` yang
  diekstrak dari transaksi massal persediaan, sehingga kedua jalur memakai
  **satu deret nomor**. Dua salinan logika penomoran adalah cara paling pasti
  melahirkan dua deret yang diam-diam berbeda.

### LPB ber-tanda tangan elektronik

`POST /persediaan/lpb/{id}/kirim-ttd` menyusun PDF **sekarang** lalu
membekukannya ke GridFS — bukan membangunnya ulang saat penanda tangan membuka
tautan. Kalau dibangun ulang, kop/pejabat/nomor bisa berubah di antara
"dikirim" dan "diteken", dan yang bersangkutan menandatangani dokumen yang tak
pernah ia baca.

Penanda tangan bawaan diambil dari blok TTD LPB sendiri (Pengurus Barang →
Pemeriksa LPB → KPB, berurutan). Tautan balik dan cascade pembatalan mengikuti
pola BAST yang sudah ada, lengkap dengan penjaga scope satker dan pencocokan
`signature_request_id`.

### Dua kebocoran lintas-satker yang ditemukan audit adversarial atas PR ini

**Gerbang `doc_ref` pada permintaan TTD hanya mengenal BAST.** `kirim_tandatangan`
menulis back-link ke dokumen yang ditunjuk `doc_ref` **tanpa** memeriksa satker —
itu memang disengaja, karena pemeriksaannya dilakukan sekali di muka saat
permintaan dibuat. Konsekuensinya: setiap `doc_type` ber-back-link **wajib**
terdaftar di gerbang itu. `lpb` sempat tidak. `/persediaan/lpb/{id}/kirim-ttd`
memang ber-guard, tetapi `POST /ttd/permintaan` bisa dipanggil langsung dengan id
LPB satker lain — dan saat tanda tangan selesai, servernya sendiri yang menulis
ke dokumen satker itu. Gerbangnya kini bertabel, dengan catatan tegas bahwa
doc_type baru harus didaftarkan.

**`_ambil_snapshot_perolehan` tak pernah ter-scope satker.** Cacat lama yang
diperburuk PR ini: writer satker A yang memegang uuid BAST satker B dapat
menyalin identitas dokumen B — nomor BAST, tanggal, penyedia, dan **sejak PR ini
juga nama + NIP PPK** — ke jurnal persediaan dan LPB satker A. Bukan sekadar
terbaca: tersimpan permanen di dokumen resmi, lengkap dengan data pribadi
pejabatnya.

### Gelombang kedua audit: 39 dugaan → 18 bertahan, 21 gugur

Lima TINGGI, **satu di antaranya regresi yang lahir dari perbaikan gelombang
pertama**:

- **`POST /pengadaan/{id}/buat-draft-aset` jadi 500.** `buat_aset_draft`
  mengembalikan dict YANG SAMA yang dioper ke `insert_one()`, dan Motor
  menyisipkan `_id: ObjectId` ke dalamnya *in-place*. Menyalinnya ke respons
  membuat FastAPI gagal membuat serial — **setelah** aset, jurnal, dan audit
  tertulis. Kini hanya field ber-daftar-putih yang disalin.
- **Pencocokan per-awalan membuang stok ke kartu yang SALAH.** Perbaikan
  gelombang pertama ("cocokkan awalan") ternyata lebih berbahaya daripada
  penyakitnya: enam digit terakhir justru yang **membedakan** "Kertas HVS A4"
  dari "Kertas HVS F4". Kini awalan **dan nama** harus cocok.
- **Jalan buntu untuk BAST setengah-jalan.** `pilah_barang_perolehan`
  menghitung baris yang **sudah** jadi aset, sehingga gerbang `activity_id`
  menuntut kegiatan untuk pekerjaan yang selesai — sementara layar tak merender
  dropdown-nya. Sisi persediaannya macet permanen, dan tombol lamanya sudah
  dihapus. Kini pemilahan mengabaikan baris yang sudah punya tujuan.
- **Klaim "PPK ter-scope satker" tak diuji sama sekali** — dua mutasi lolos
  1.213 uji karena seluruh fixture memakai satker kosong.
- Pembatalan TTD LPB kini **mengosongkan** `signature_request_id`; tanpa itu
  tombol "Kirim TTD" hilang selamanya.

Toast hijau juga berhenti berbunyi "tidak ada barang baru" saat semua baris
gagal, dan seluruh alasan gagal ditampilkan — bukan hanya yang pertama.

### Gelombang ketiga: delapan temuan SEDANG/RENDAH sisanya

- **Blok tanda tangan LPB di-scope ke satker PENERBIT, bukan pembaca.**
  Dulu memakai satker pengguna yang membuka: super-admin (`kode_satker == ""`)
  mendapat kandidat pejabat dari SELURUH satker, dan yang SK-nya terbaru
  menang — dokumen resmi satker A bisa tercetak dengan nama pejabat satker B.
  Kini dibaca dari stempel `lpb.kode_satker` yang dibekukan saat LPB terbit.
- **NIP PPK tunduk pada aturan privasi Non-ASN.** `snapshot_ppk` sengaja
  membekukan `ppk_status_kepegawaian` untuk keputusan ini, lalu status itu tak
  pernah dipakai dan NIP tercetak mentah — membatalkan lewat pintu belakang
  aturan yang ditegakkan di seluruh blok tanda tangan.
- **`PUT /pengadaan/{id}/ppk` akhirnya punya jalan masuk.** Endpointnya ada
  sejak awal, tetapi layar justru menyuruh operator "catat ulang" BAST — yang
  berarti membuat register ganda. Kini baris PPK bisa diketuk.
- **Tautan tanda tangan ditampilkan, bukan hanya jumlahnya.** Tanpa email
  terkonfigurasi, tautan yang tak pernah muncul di layar berarti permintaan
  TTD tak sampai ke siapa pun.
- **Penomoran LPB akhirnya diuji.** Seluruh uji sebelumnya mematikan
  `booking_otomatis`; jalur yang tak pernah dijalankan uji apa pun adalah
  jalur yang tak pernah dijamin bekerja. Kini dijaga sampai ke buku agenda,
  termasuk jaminan nomor tak pernah terpakai dua kali.

### Verifikasi

1.236 uji backend (53 baru), eslint 0 galat, build kompilasi. **Enam mutasi**
dibuktikan tertangkap: membuang penjaga golongan → 4 uji gagal; mempersempit
proyeksi `ppk_*` → 2 uji gagal; mencabut `lpb` dari gerbang `doc_ref` → 2 uji
gagal; mencabut scope satker dari lookup perolehan → 1 uji gagal; mematok
kembali `jumlah: 1` di baris LPB → 2 uji gagal; membuang penyaring
"sudah tercatat" dari pemilahan → 1 uji gagal; mencocokkan awalan tanpa nama
→ 1 uji gagal.

**Batas yang dinyatakan terus terang:** kebocoran `_id` dijaga dengan
memeriksa DAFTAR PUTIH field pada nilai balik, bukan dengan memancing galat
serialisasinya. `mongomock` tidak menyisipkan `_id` ke dict yang dioper seperti
Motor sungguhan, jadi mode gagal aslinya **tak bisa direproduksi** di uji unit —
yang bisa dijaga hanyalah aturannya: jangan pernah menyalin dokumen aset mentah
ke respons.

---

## [#655] Hierarki Spasial: nama node yang hilang di HP dikembalikan — 2026-07-27

Umpan balik lapangan berupa tangkapan layar HP: baris pohon hanya menampilkan
badge **Wilayah** dan **denah** lalu deretan ikon yang meluber keluar layar.
Nama node — satu-satunya isi yang penting — **tidak terlihat sama sekali.**

### Akar masalahnya flexbox, bukan kekurangan ruang

Baris itu satu `flex` dengan sembilan anak. Nama memakai `flex-1 min-w-0`;
delapan tetangganya (tiga badge + enam tombol) `shrink-0`. Ketika lebar kurang,
flexbox mengecilkan satu-satunya item yang boleh menyusut — sampai **nol** —
lalu sisanya tetap meluber. Jadi bukan nama yang "terpotong": nama yang
dikorbankan lebih dulu, dan barisnya tetap tak muat.

### Perbaikannya: baris dua tingkat

- **Tingkat atas** — nama node, penuh, sendirian, dengan `title` untuk yang panjang.
- **Tingkat bawah** — tipe, kode, status draft/nonaktif, dan penanda denah;
  semuanya `flex-wrap`, jadi turun baris alih-alih mendorong.
- **Aksi** — *Isi lokasi* dan *Opname* tetap terlihat (keduanya operasi baca yang
  sering dipakai). Empat aksi tulis dilipat ke menu **⋮** di bawah 640px, dan
  tetap sebaris di layar lebar tempat ruangnya memang cukup.
- **Indentasi lebih rapat di HP** (9px/tingkat, dibatasi 6 tingkat) lewat kelas
  `.spasial-baris`. Pada 16px/tingkat, node di kedalaman tujuh membuang 112px —
  lebih dari sepertiga layar 360px — sebelum satu huruf pun sempat digambar.

Penanda geometri kosong juga berhenti menulis `—` yang tak bermakna; kini
tertulis **"belum digambar"**.

---

## [#654] Audit adversarial gelombang D — layar yang bisa dipakai & janji yang jujur — 2026-07-27

Gelombang terakhir: 14 temuan sisa yang tak mengancam data, tetapi menentukan
apakah fitur-fitur baru benar-benar BISA DIPAKAI di HP lapangan.

### Dialog Opname yang tak bisa digulir

`DialogContent` bawaan membawa `overflow-hidden`. Di layar HP, panel Opname
lebih tinggi daripada viewport sehingga tombol **Terapkan** dan **Tutup**
terpotong di luar layar — dan tak ada cara menggulirnya. Fitur inti fase 11
praktis tak bisa diselesaikan dari HP. Kini `max-h-[92vh] overflow-y-auto`.

### Layar yang tak lagi menyesatkan atau membuang kerja

- **Viewer diberi tahu SEBELUM memindai.** `POST /opname/scan` menolak akun
  baca-saja dengan 403, tetapi barisan pindainya tetap disuguhkan — pengguna
  baru tahu setelah pindaian pertama (atau ketiga puluh) gagal.
- **Centang Terapkan tak lagi lenyap tiap kali memindai.** Pemuatan ulang dulu
  mengosongkan seluruh pilihan tanpa pemberitahuan; kini yang masih ada
  dipertahankan.
- **Penjaga urutan respons** pada `muat()` — mengetuk saklar "termasuk isi di
  bawahnya" dua kali cepat bisa menampilkan lingkup yang tak cocok dengan
  posisi centangnya.
- **Panel SBSK & Opname tak lagi jadi kotak kosong permanen** setelah gagal
  memuat: ada pesan + tombol "Coba lagi".
- **Tombol CSV punya nama aksesibel** (labelnya disembunyikan di <640px).

### Berhenti membuang jaringan yang justru sedang buruk

- **Kirim ulang antrean: satu penyegaran, bukan enam puluh.** Mengosongkan
  antrean 60 scan dulu memicu 60 GET rekonsiliasi berat BERURUTAN, tepat saat
  sinyal baru pulih.
- **Balasan REPLAY tak lagi membawa base64 foto.** Dua cabang idempotensi
  mengembalikan dokumen MENTAH tanpa `_strip_media`, padahal jalur sukses tepat
  di bawahnya membuangnya. Replay lazim terjadi persis saat sinyal buruk —
  keadaan yang paling tak sanggup menanggung respons multi-MB.
- **`clear_photos`/`clear_document_checklist` hanya menyentuh aset yang memang
  BERISI.** URL media memakai `?v=<version>` sebagai cache-buster, jadi
  menaikkan version aset yang fotonya tak berubah membuat SETIAP perangkat
  lapangan mengunduh ulang foto yang sama. Predikat memakai `.0 $exists`, bukan
  `$nin: [None, []]` — yang terakhir ditafsirkan BERBEDA oleh mongomock dan
  MongoDB asli, sehingga uji bisa hijau sementara produksi berperilaku lain.
- **Panel SBSK tak lagi menarik seluruh pohon denah** (bisa puluhan ribu node)
  hanya untuk mengisi satu dropdown.

### Dokumentasi yang mengaku lebih dari kenyataannya

Baris status di `docs/ARSITEKTUR-SPASIAL-IOT.md` menyatakan Fase 7 dan 9 utuh.
Keduanya **baru sebagian**, dan kini dinyatakan apa adanya: Fase 7 tanpa migrasi
master `ruangan` (KIR/DBR masih bersumber `assets.location`); Fase 9 tanpa
`asset_custody` dan tanpa integrasi BAST/sertijab — yang tercatat perpindahan
LOKASI, bukan pergantian PEMEGANG.

- Uji: **+1 backend (1.180)**, 225 frontend. Satu mutasi diverifikasi.

### Yang SENGAJA tidak dikerjakan

Auditor menyarankan memisahkan `media_version` dari `version` agar cache foto
tak terbatalkan oleh perubahan non-foto. **Tidak dilakukan**: itu memperkenalkan
penghitung kedua yang harus dirawat di setiap jalur tulis foto — risiko baru
demi kenyamanan. Yang diambil adalah pangkalnya: berhenti menaikkan version
tanpa perubahan nyata.

---

## [#652] Audit adversarial gelombang C — sepuluh uji yang tak menjaga apa pun — 2026-07-27

Dimensi "kualitas uji" pada audit adversarial mengerjakan satu hal yang tak
dilakukan gelombang lain: ia **menjalankan mutasi** atas kode yang sudah hijau,
lalu melaporkan mana yang LULUS. Sepuluh mutasi lolos 1.167/1.167 — artinya
sepuluh jaminan yang selama ini saya kira terkunci sebenarnya tidak.

Gelombang ini menutup semuanya, dan tiap perbaikan dibuktikan dengan menjalankan
ULANG mutasi yang persis sama.

### Uji yang lulus karena datanya tak pernah menjebak

- **`$inc version` ubah massal** hanya diuji pada 1 dari 5 jalur tulis.
  Mencabutnya dari jalur checklist atau clear tetap hijau. Kini keempat jalur
  lain punya ujinya sendiri.
- **`idem_key`** — uji replay MENANAM stempelnya sendiri lalu hanya membuktikan
  sisi BACA. Mencabut stempel di jalur tulis tetap hijau, padahal tanpa itu tak
  ada satu pun aset baru yang bisa di-dedup. Kini jalur tulisnya diuji langsung.
- **`gabungPatch`** — semua kasus hanya punya `photo_ops` di SATU sisi, sehingga
  `{...lama, ...baru}` polos sudah cukup meluluskannya. Justru skenario yang
  menjadi ALASAN modul itu ada tak pernah diuji.
- **`_KATA_UMUM`** — fixture tak memuat satu pun peruntukan yang beririsan pada
  kata umum, jadi daftar hentiannya mati total; `set()` pun lulus.
- **"token terpanjang"** — datanya cuma punya satu token ≥4 huruf, jadi
  `token[0]` dan `token[-1]` sama-sama lulus.
- **`dalam=False`** — node seed tak punya `parent_id` sama sekali, sehingga
  cabang itu SELALU mengembalikan 0 apa pun implementasinya. Ditambah uji
  pasangan yang justru HARUS berisi.
- **`sebaran_per_induk`** — jumlah aset per keranjang kebetulan sama dengan
  cacah barisnya, jadi `+= 1` tak terbedakan dari `+= jumlah_aset`.

### Penjaga yang tak pernah dijalankan bukan penjaga

`/opname/terapkan` punya DUA penjaga: pembacaan `if s.get("diterapkan")` dan
update bersyarat `klaim`. Yang pertama selalu menghentikan panggilan kedua lebih
dulu, sehingga penjaga LOMBA — yang komentarnya menjelaskan panjang lebar
mengapa ia ada — tak pernah dievaluasi sekali pun. Audit membuktikannya dengan
mengubahnya jadi `if False:` tanpa satu uji pun gagal. Pembacaannya **dibuang**;
yang tersisa adalah penjaga yang benar-benar memutuskan, dan kini ia diuji.

### Cabang yang tak pernah dijalankan siapa pun

- **`DuplicateKeyError` pada create_asset** kini diuji dengan menyuntikkan
  galatnya. Cabang ini HANYA aktif saat produksi mengalami lomba antar-replay —
  persis saat kesalahan paling mahal, dan justru di situlah ia tak pernah
  dicoba.

### Berkas uji yang namanya berbohong

`hooks/useOptimisticQueue.test.js` tak pernah mengimpor hook itu — ia menguji
`lib/syncStatus`. Namanya membuat seolah perkabelan antrean sudah berujikan,
padahal ~140 baris logika integritas dari PR #642/#643 tak tersentuh sama
sekali. Berkas itu **diganti nama** menjadi `lib/syncStatus.test.js`, dan aturan
gabungnya diekstrak ke **`lib/gabungAntrean.js`** (repo tak memasang
@testing-library, jadi hook-nya memang tak bisa dirender — tetapi KEPUTUSANNYA
bisa dipisahkan, persis pola gabungPatch/pemilikAntrean/sekaliJalan).

- Uji: **+4 backend (1.179), +11 frontend (225)**. **Delapan mutasi yang
  sebelumnya LULUS kini semuanya tertangkap** — itulah satu-satunya bukti yang
  berarti untuk gelombang ini.

---

## [#650] Audit adversarial gelombang B — opname menyambung ke dokumen resmi — 2026-07-27

Lima temuan SEDANG dari audit adversarial, semuanya berkumpul di sekitar satu
pertanyaan: **apakah hasil opname benar-benar sampai ke tempat yang membacanya?**

### Perpindahan di dalam gedung tak lagi lenyap dari semua keranjang

Buka Opname di level GEDUNG — nilai bawaannya — lalu barang yang berpindah dari
Ruang 305 ke Ruang 307 punya node buku DAN node scan yang sama-sama berada di
dalam lingkup itu. Dulu ia langsung masuk `sesuai`: layar melaporkan gedung
**100% terkonfirmasi tanpa selisih**, scan berstatus "pindah" tak pernah muncul
untuk dicentang, dan buku tetap menyebut Ruang 305 selamanya. Penentu keranjang
kini `status_rekonsiliasi` scan itu sendiri — yang memang sudah tersimpan,
sehingga tak ada kueri tambahan. Penjaga `diterapkan` menyertainya: tanpa itu
keranjang usulan tak pernah kosong karena status scan tetap "pindah" selamanya.

### Hasil opname kini sampai ke KIR & DBR

`/opname/terapkan` dulu hanya memperbarui `lokasi_spasial`. Padahal KIR dan DBR —
**dokumen resmi yang dipegang pemeriksa** — membaca `location` (teks bebas,
dicocokkan string di `reports.py`). Akibatnya peta dan kertas saling
bertentangan, dan yang menang di ruang audit justru kertasnya. `location` kini
ikut berpindah, dan nilai lamanya disimpan ke `riwayat_lokasi_aset` sebelum
ditimpa.

### Tiga perbaikan penyerta

- **Koordinat presisi tak lagi terhapus.** Pemindaian dari aplikasi memilih
  RUANGAN, tak mengukur titik — menuliskan `titik: None` apa adanya menghapus
  koordinat yang dikumpulkan lewat jalur Fase 9, yang justru MENOLAK koordinat
  kosong. Kini titik lama dipertahankan bila scan tak membawa yang baru.
- **Ruangan yang belum digambar** tak lagi divonis "di bawah standar −247 m²".
  0 m² memang selalu lebih kecil dari standar apa pun, tetapi yang kurang adalah
  GAMBARNYA, bukan luasnya. Status baru `belum_digambar` mendahului semuanya.
- **N+1 dihapus dari rekonsiliasi.** `pastikan_akses_aset` dipanggil per baris —
  ruangan berisi 1.000 aset berarti 1.000 `find_one` berurutan untuk satu
  halaman. Diganti satu kueri kegiatan-satker yang dipakai bersama, yang
  sekaligus menutup kebocoran keranjang "Ditemukan di sini" (dokumen scan
  distempel satker PEMINDAI, bukan satker aset).

### Jejak petugas: diungkapkan, bukan dihapus

Auditor benar bahwa `opname_scan` menyimpan nama petugas + ruangan + waktu, dan
klaim "yang direkam barang, bukan orang" hanya benar untuk MAKSUDNYA. Tetapi
menghapusnya merusak bukti penatausahaan. Kewajiban UU 27/2022 di sini adalah
**transparansi**: `/api/iot/kebijakan-privasi` kini menyatakan apa yang disimpan,
berapa lama, mengapa berbeda dari `iot_observasi` (perbuatan sadar dalam tugas
resmi vs aliran pasif), dan bahwa larangan penggunaan sekunder tetap berlaku.

- Uji: **+8 backend (1.175)**. Lima jaminan diverifikasi MUTASI, semuanya
  tertangkap tepat oleh uji penjaganya.

---

## [#648] Audit adversarial gelombang A — 4 temuan TINGGI + 2 kebocoran laporan SBSK — 2026-07-27

Audit adversarial 17 agen atas PR #641–#645 mengajukan **66 temuan**; penyanggah
menggugurkan 17, menyisakan 49. Gelombang ini menutup empat yang berkeparahan
TINGGI plus dua cacat SEDANG yang paling berbahaya.

> **Catatan metodologi.** Keluaran awal workflow melapor "61 bertahan, 0 gugur".
> Itu SALAH — logika penjodohan vonis→temuan di skripnya gagal sehingga semua
> temuan tampak tak tersanggah. Angka sebenarnya diambil ulang dari jurnal
> mentah. Rasio gugur 0% adalah tanda bahaya, bukan tanda sukses.

### Data tertukar & data hilang

- **Scan luring tercatat di RUANGAN YANG SALAH.** `kirim()` di OpnameDialog
  selalu menulis `node_id: node.id` — node dialog **yang sedang dibuka** —
  sementara `kirimUlangSemua()` tak pernah memakai `node_id` yang tersimpan di
  antrean. Petugas memindai 30 barang luring di Ruang 305, naik ke lantai atas,
  membuka Ruang 307, menekan "Kirim ulang": **ketiga puluhnya tercatat di Ruang
  307.** Antrean yang dibangun di #644 untuk melindungi data justru menjadi
  jalur data tertukar. Node **dan** waktu kejadian kini datang dari baris
  antreannya sendiri.
- **"Batalkan scan ini" kini benar-benar membatalkan** — sebelumnya barisnya
  tetap di antrean lalu terkirim lagi nanti, tanpa `asset_id`, jadi ambigu lagi.
- **Pembatalan menelan simpanan berikutnya.** `dismissedRef` (perbaikan #643)
  menahan kunci 5 menit dan tak pernah dibersihkan `enqueue`: mengedit ulang
  aset yang sama dalam 5 menit setelah membatalkan membuat jalur sukses keluar
  lebih awal — baris tak pernah diperbarui, chip tak pernah bersih.
- **Muatan foto simpanan pertama tertimpa.** Saat simpanan lama masih TERBANG,
  penggabungan sengaja dilewati (cegah foto kembar). Bila keduanya lalu gagal,
  `failedItemsRef[statusKey]` ditimpa dan foto yang pertama lenyap. Kini
  digabung di jalur kegagalan — aman justru karena keduanya terbukti belum
  diterapkan server.

### Laporan SBSK yang menyesatkan

- **`$limit` dipindah ke SETELAH `$group`.** Sebelumnya ia memotong ASET sebelum
  pengelompokan, sehingga ruangan yang asetnya berada di luar potongan hilang
  utuh dari peta isi lalu dilaporkan **MENGANGGUR** — bukti palsu untuk
  menghentikan pengadaan, persis kebalikan dari tujuan laporan ini.
- **Agregasi isi ruangan kini ter-scope satker** (`scope_query_aset`). `ids`
  memang ter-scope, tetapi node ERA LAMA tanpa `kode_satker` terbuka untuk semua
  satker — sehingga jumlah aset dan **nama pemegang** satker lain ikut terhitung.
  Agregasi gampang lolos penjagaan justru karena ia tak melewati `find()`.

### UI

- **Baris pohon Master Denah tak lagi meluber di HP.** Aturan global 44px
  memaksa tujuh tombol ikon menjadi 7×44px; di layar 360px nama node menyusut
  habis. `min-h-0 min-w-0` membatalkannya (pola baku repo, lihat QrScanButton)
  sementara halo `tap-expand` tetap menjaga area sentuh.

- Uji: **+3 backend (1.170), +5 frontend (214)**. Tiga jaminan diverifikasi
  MUTASI. Satu uji plafon yang saya tulis mula-mula **tidak menjaga apa pun**
  (datanya jauh di bawah plafon sehingga posisi `$limit` tak berpengaruh) —
  persis jenis uji-bohong yang ditemukan audit; plafonnya diturunkan lewat
  monkeypatch agar ujinya benar-benar diskriminatif, lalu mutasinya tertangkap.

---

## [#647] Spasial Fase 15: SBSK berbasis luas ruangan NYATA dari poligon denah — 2026-07-27

Sampai sekarang tabel SBSK berdiri sendiri: angka "247 m² untuk pimpinan" tanpa
satu pun ruangan nyata untuk dibandingkan. Denah poligon yang dibangun Fase 3–7
mengubah itu — **luas dihitung dari GAMBARNYA**, bukan dari angka yang diketik
ulang seseorang ke dalam formulir.

### Peruntukan DITETAPKAN, bukan disimpulkan

Godaannya besar: tebak penghuni ruangan dari pemegang aset yang ada di dalamnya.
Tetapi ruang rapat berisi kursi ber-pemegang satu orang akan terbaca sebagai
ruang kerja orang itu, lalu dibandingkan dengan standar jabatannya, lalu
dilaporkan "melebihi standar 300%". **Angka yang salah tetapi rapi jauh lebih
berbahaya daripada kolom kosong.** Karena itu `peruntukan` adalah field pada node
denah yang diisi manusia; isi aset hanya ditampilkan di sebelahnya sebagai
INDIKASI okupansi.

### Ruang menganggur = bukti untuk menahan pengadaan

Yang paling berguna di layar ini bukan kolom "sesuai", melainkan dua angka yang
biasanya tak ada di mana pun: ruangan yang sudah tergambar tetapi **belum
ditetapkan peruntukannya**, dan ruangan yang tak berperuntukan **sekaligus** tak
berisi aset apa pun — ruang menganggur. Keduanya sengaja dipisah: ruangan tanpa
peruntukan yang penuh aset jelas terpakai (ia kekurangan administrasi, bukan
penghuni), dan menyatukannya akan melaporkan gedung yang sibuk sebagai gedung
kosong.

### Backend

- **`sbsk_ruang_utils.py`** (murni): pencocokan peruntukan ruangan ke baris SBSK
  `ruang_kerja` (**irisan kata terbanyak yang menang, bukan yang pertama
  ketemu** — kalau tidak, "Kepala Seksi" menyambar ruang kepala biro dan seluruh
  laporan mengukur terhadap standar yang salah), status kesesuaian bertoleransi
  ±5% dua arah, tiga keranjang rekap, dan sebaran per lokasi.
- **`GET /api/perencanaan/sbsk-ruang?node_id=&dalam=&tipe=`** — sanding luas
  nyata vs standar untuk satu lingkup denah, lengkap dengan rekap dan sebaran.
  Isi ruangan (jumlah aset + pemegang) diambil dalam SATU agregasi, bukan satu
  kueri per ruangan.
- **Luas DIHITUNG ULANG dari geometri**, tidak membaca `metrik.luas_m2` yang
  tersimpan: nilai itu ditulis saat geometri terakhir disimpan, bisa jadi oleh
  rumus versi lama. Untuk peringkat area bias seragam tak berpengaruh; untuk
  angka yang masuk dokumen perencanaan, membaca nilai basi berarti melaporkan
  luas yang tak bisa dipertanggungjawabkan asal-usulnya.
- **`spasial_utils.luas_kasar_m2` memakai deret skala WGS84**
  (`meter_per_derajat`) menggantikan pendekatan BOLA. Bedanya bukan akademis: di
  lintang IKN bola **melebihkan luas ~0,45%**, karena jari-jari bola rata-rata
  lebih besar daripada jari-jari kelengkungan meridian di dekat khatulistiwa.
- **Field `peruntukan` pada node denah** dengan semantik "None = tak diubah"
  yang sama dengan `status`/`properties`: klien lama yang tak mengirim field ini
  (form pohon pra-Fase-15) TIDAK menghapus peruntukan yang sudah ditetapkan.

### Frontend

- **`components/perencanaan/SbskRuangPanel.jsx`** — pemilih lingkup
  (tapak/gedung/lantai/sayap), empat kartu rekap, kartu peringatan ruang
  menganggur, daftar ruangan berlencana status, sebaran per lokasi, dan unduh
  CSV (dibuat di klien; pemisah titik-koma + BOM agar Excel Indonesia tak
  memecah angka desimal ke kolom berikutnya). Dimuat lazy.
- **Field Peruntukan** di form node Master Denah, muncul untuk tingkat RUANGAN
  dan SAYAP saja — dan untuk tipe lain field itu SENGAJA absen dari body PUT,
  sehingga mengubah sebuah gedung tak menyentuh peruntukan ruangan mana pun.

- Uji: **+37 backend (1.203)**. Enam jaminan diuji MUTASI. Satu di antaranya
  **lolos pada percobaan pertama** — uji "irisan terbanyak menang" ternyata tak
  benar-benar mengujinya karena data ujinya tak pernah membuat baris yang salah
  cocok lebih dulu; ujinya diperbaiki dengan tabel berurut yang memang
  menjebak, lalu mutasi yang sama tertangkap.

---

## [#646] Spasial Fase 11: scan stiker QR jadi sumber lokasi + rekonsiliasi opname — 2026-07-27

Stiker QR sudah tercetak dan tertempel sejak PR #397. Fase ini menjadikan
pemindaiannya **sumber lokasi kelas satu**: biaya Rp 0, tanpa isu privasi (yang
direkam BARANG, bukan orang), dan akurasi ruangannya sempurna — persis mengisi
lubang yang tak bisa diisi GPS, yang justru mati di dalam gedung.

### Opname sebagai PEMERIKSAAN, bukan penulisan ulang

Keputusan terpenting fase ini adalah apa yang **tidak** dilakukan: memindai
TIDAK memindahkan catatan lokasi. Opname yang serta-merta menulis ulang buku
menghapus satu-satunya hal yang dicarinya — SELISIH — dan salah pindai (stiker
tetangga, barang yang sedang dijinjing petugas) akan diam-diam mengubah custody
tanpa seorang pun sempat berkeberatan. Scan **mencatat + mengklasifikasi**;
perpindahan menyusul lewat `POST /opname/terapkan` yang memakai jalur riwayat
yang sama dengan Fase 9 (`riwayat_lokasi_aset`), tercatat di audit, dan
idempoten (tombol ditekan dua kali tak melahirkan dua baris riwayat).

### Backend

- **`backend/opname_utils.py`** (murni): penguraian isi QR yang mengembar
  `extractScannedCode` di frontend, klasifikasi scan, dan tiga keranjang
  rekonsiliasi.
- **`POST /api/opname/scan`** — resolusi kode → aset, klasifikasi, catat.
  Kode **ambigu tidak pernah ditebak**: `kode_register` hanya unik di dalam satu
  kegiatan, jadi satu isi QR bisa menunjuk beberapa aset → **409 berisi daftar
  kandidat** untuk dipilih petugas. Pilihan yang dikirim balik wajib berasal
  dari kandidat kode itu, supaya `asset_id` tak menjadi jalan mencatat scan
  palsu tanpa pernah menyentuh stikernya.
- **Scan di level yang lebih KASAR mengukuhkan, bukan memindahkan.** Buku
  mencatat Ruang 305; petugas memindai di pintu Gedung A yang memuatnya.
  Menganggapnya "pindah" lalu menerapkannya akan MENURUNKAN presisi ruangan
  menjadi gedung — informasi termahal yang justru hilang.
- **Stiker ber-NUP kosong tetap terpindai.** Pencetak menulis `nup or '0'`,
  sehingga aset tanpa NUP tercetak `-0`; tanpa cabang khusus, stiker itu abadi
  tak terbaca.
- **`GET /api/opname/rekonsiliasi`** — sanding buku vs lapangan per lingkup
  node (opsional sampai seluruh keturunannya): *cocok*, *belum terpindai*
  (daftar kerja yang tersisa), *ditemukan di sini* + persen terkonfirmasi.
  Rekap menyembuhkan diri sendiri: tak menyimpan status yang bisa basi.
- **`GET /api/opname/riwayat-aset/{id}`** — kapan & di mana barang terakhir
  benar-benar terlihat, terlepas dari apa yang tercatat di buku.
- **Koleksi `opname_scan` berdiri sendiri, TANPA TTL.** Bentuk dokumennya sama
  dengan pipeline observasi Fase 10 (`sumber`/`akurasi_m`/`kepercayaan`), tetapi
  retensinya tidak diwarisi: TTL `iot_observasi` ada karena isinya jejak
  keberadaan ORANG yang wajib kedaluwarsa, sementara hasil opname adalah BUKTI
  penatausahaan yang harus bertahan. Menumpangkannya berarti catatan opname
  terhapus diam-diam beberapa bulan setelah dibuat.
- Indeks: `opname_scan_idem` (UNIK `scan_id` — penegak idempotensi antrean
  luring), `opname_scan_node_waktu`, `opname_scan_aset_waktu`,
  `opname_scan_satker_waktu`. Terbentuk otomatis saat backend berikutnya start.

### Frontend

- **`components/spasial/OpnameDialog.jsx`** — panel opname per lokasi di
  halaman Master Denah: tombol scan QR + isian kode manual (untuk stiker yang
  rusak), pemilih kandidat saat kode ambigu, tiga keranjang dengan
  *Belum terpindai* di paling atas, bar persen terkonfirmasi, dan tombol
  Terapkan (khusus penulis; viewer tetap boleh melihat rekonsiliasi).
- **`lib/antreanScan.js`** — antrean luring untuk pemindaian. Opname justru
  dikerjakan di tempat sinyal paling buruk; scan yang gagal terkirim disimpan
  dan bisa dikirim ulang saat sinyal pulih. Yang membuat pengiriman ulang aman
  adalah `scan_id` (kunci idempotensi sisi server), jadi tiga kali coba tetap
  menghasilkan SATU catatan.
- **`lib/idAntrean.js`** mengekspor `idUnik(awalan)` — inti keunikan yang sama
  (tak pernah bersandar pada jam yang bisa mundur) kini dipakai ulang `scan_id`.

- Uji: **+48 backend (1.127) dan +14 frontend (209)** — 28 uji helper murni,
  20 uji endpoint dengan mongomock (resolusi kode, 409 ambigu, penolakan
  `asset_id` di luar kandidat, replay antrean, janji "scan tidak memindahkan",
  terapkan + riwayat + idempotensinya, tiga keranjang rekonsiliasi), dan 14
  uji antrean luring.

---

## [#645] Gerbong data TUNTAS — 15 temuan sisa audit ditutup semua (4 backend + 11 frontend) — 2026-07-27

Perintah pemilik: *"lakukan perbaikan hingga tuntas"*. Lima belas dugaan sisa
audit gelombang 2 disanggah ulang terhadap kode TERKINI oleh 15 skeptis
independen (4 di antaranya saya verifikasi sendiri di kode lebih dulu — semua
cocok), lalu SEMUANYA diperbaiki. Tidak ada yang tersisa di daftar.

### Backend

- **Ubah Massal kini menaikkan `version`** pada KELIMA titik tulisnya. Dulu
  penjaga OCC/If-Match buta terhadap perubahan massal: klien luring yang
  membawa versi lama tetap lolos CAS lalu menimpanya tanpa satu pun 409.
- **Idempotensi CREATE jadi permanen.** Cache respons ber-TTL 24 jam, antrean
  luring tidak: simpanan yang percobaan pertamanya SAMPAI tetapi responsnya
  hilang, di-replay setelah survei berhari-hari, menciptakan aset KEMBAR.
  Kuncinya kini distempel ke dokumen aset sendiri (`idem_key` + indeks unik
  parsial `idem_key_unik`) — dokumen tak kedaluwarsa, dedup-nya pun tidak.
  Balapan dua replay ditangkap `DuplicateKeyError` dan keduanya menerima aset
  yang SAMA.
- **`photo_ops` terikat versinya.** `keep` adalah indeks POSISIONAL; bila array
  foto bergeser sejak dihitung, keep yang sama menunjuk foto yang BERBEDA —
  foto terhapus hidup lagi, foto lain terbuang, tanpa galat. Klien kini
  menyertakan `base_version`, server menolak 409 bila versi sudah bergeser
  (If-Match tetap jalur utama; ini jaring untuk payload antrean tanpa header).
- **Rotasi foto menstempel `updated_at`** — delta sinkron luring memfilter pada
  stempel itu, jadi rotasi kini benar-benar sampai ke cache perangkat lapangan.

### Frontend

- **`upsertSnapshotAsset` kini baca-gabung-tulis** — satu perbaikan menutup
  TIGA temuan sekaligus: potongan PATCH tak lagi menghapus seluruh baris
  snapshot; respons tulis (yang tak memuat `doc_total/doc_checked/siman`) tak
  lagi menghapus badge dokumen & SIMAN dari tampilan luring; baris yang tak
  ketemu di daftar state tak lagi menjadi stub.
- **Sampul & foto stiker tak salah foto saat edit luring.** Strip hanya
  menampilkan foto BARU padahal susunan akhir server = [foto lama] + [baru];
  indeks strip kini digeser saat pengguna MENGETUK (`lib/indeksFotoLuring.js`),
  sehingga `thumbnail_index`/`stiker_photo_index` selalu indeks final. Daring
  dan mode-create tak berubah (offset 0).
- **Antrean terikat pemiliknya** (`lib/pemilikAntrean.js`): rekaman distempel
  akun pembuatnya, dan rehidrasi di perangkat dinas bersama tak lagi memutar
  ulang simpanan akun LAIN memakai token & identitas audit akun yang login.
  Rekaman era lama tanpa stempel tetap di-replay.
- **"Abaikan" benar-benar membatalkan**: item ber-kunci sama dikeluarkan dari
  antrean memori (bukan hanya rekamannya), penyelesaian permintaan yang sedang
  terbang tak menghidupkan kembali baris yang dibuang, dan EDIT yang dibuang
  kini memulihkan baris daftar + snapshot dari kebenaran server.
- **`reserveDummyNup` single-flight** (`lib/sekaliJalan.js`): dua panggilan
  serentak dulu sama-sama menyemai lalu yang belakangan menimpa balik urutan —
  dua aset ber-NUP sama. Kini seeding terbang sekali; pemanggil kedua menumpang.
- **Dropdown kategori dummy memakai urutan lokal bersama** — bukan `next-nup`
  mentah yang hanya menghitung aset tersimpan (dan mengulang nomor yang baru
  saja diterbitkan lokal).
- **Ubah Massal ditahan selama akuisisi GPS** — koordinat sementara yang belum
  lolos gerbang ±8 m tak bisa lagi diterapkan ke banyak aset sekaligus.
- **CREATE kegiatan A yang sukses saat kegiatan B terbuka** tak lagi disisipkan
  ke daftar B (penjaga `activity_id` pada cabang fallback-sisip).

- Uji: **+30 → 195 frontend, 1.079 backend** (5 uji endpoint baru dengan
  mongomock — batch version, replay idem via dokumen, photo_ops 409/diterima,
  stempel rotasi). Empat jaminan diverifikasi MUTASI: mencabut `$inc`,
  mencabut pemeriksaan `base_version`, mengembalikan timpa-buta snapshot, dan
  mencabut single-flight masing-masing menggagalkan tepat uji penjaganya.

---

## [#644] Gerbong data gelombang 2 — audit adversarial jalur luring, 6 kebocoran ditutup — 2026-07-27

Dua cacat "tertukar gerbong" di entri sebelumnya ditemukan dengan menelusuri
**dua** jalur memakai tangan. Mandat pemilik menuntut lebih: *"teliti terhadap
semua data yang masuk agar sesuai dengan gerbongnya masing-masing"*. Maka
seluruh permukaan data luring disapu audit adversarial — 6 dimensi ditelusuri
paralel (kunci antrean, pasangan foto, koordinat, snapshot vs antrean, konteks
replay, idempotensi server), tiap dugaan lalu dibantah pembaca kode yang
tugasnya justru **menggugurkan**, bukan menyetujui.

Hasilnya 24 dugaan. Delapan lolos sanggahan, dan **enam di antaranya
diverifikasi ulang langsung di kode** sebelum disentuh — 0 dari 8 yang gugur
adalah angka yang mencurigakan, jadi laporan agen tidak diterima begitu saja.

### 1. Satu aset hanya punya SATU slot antrean — dan yang kedua menimpa

`statusKey` untuk EDIT adalah `editId`, yang memang sengaja berulang, sementara
`failedItemsRef` dan IndexedDB (`keyPath: "statusKey"`) sama-sama peta berkunci.
Menulis dua kali ke kunci yang sama = yang pertama lenyap tanpa satu pesan pun.

Akibat nyata: surveyor luring menambah **foto** (patch berisi `photo_ops`) →
gagal kirim → lalu menggeser pin aset itu di peta (patch ramping berisi
koordinat saja). Saat sinyal pulih **hanya patch koordinat yang terkirim**.
Fotonya tak pernah sampai, chip berakhir "saved", dan byte fotonya sudah tak ada
di perangkat karena snapshot luring memang membuang foto. Jalur peta bahkan tak
perlu luring — `handleMapCoordsSave` tak memeriksa status sinkron sama sekali.

`lib/gabungPatch.js` menggabung keduanya alih-alih menimpa. Ini sah **justru
karena** yang pertama belum diterapkan: kedua patch dihitung terhadap keadaan
server yang sama. `photo_ops.add` disatukan (kalaupun kembar, itu kelihatan dan
bisa dihapus — jauh lebih baik daripada hilang yang tak kelihatan), `keep`
mengikuti kehendak terakhir.

Penggabungan **tidak** dilakukan bila simpanan lama sedang terbang: ia akan
diterapkan server sebentar lagi, dan menggabungnya berarti foto yang sama masuk
dua kali. Item lama yang masih mengantre dikeluarkan agar tak terkirim dengan
muatan usang lalu menaikkan versi dan menolak patch gabungan kita sendiri.

### 2. Simpanan yang BERHASIL menghapus rekaman simpanan lain

Jalur sukses memanggil `removePersistedItem(statusKey)` tanpa memeriksa siapa
pemilik rekaman itu. Bila sementara itu ada simpanan lain atas aset yang sama
yang baru gagal dan mendaftar, rekamannya ikut terhapus. Tiap simpanan kini
membawa `antreanId` sendiri, dan hanya boleh membuang rekaman **miliknya**.

### 3. Unggah beberapa foto checklist — hanya yang terakhir tersimpan

`handleFileUpload` menyalin `[...checklist]` **di dalam** loop `await`, padahal
`checklist` adalah prop yang beku selama callback berjalan. Tiap iterasi
membangun dari daftar yang sama, lalu `onChange` terakhir menang. Pilih 3 foto →
2 terbuang senyap, dan batas "maks 3" pun dihitung dari cacah basi. Kini satu
salinan kerja diakumulasi sepanjang loop, `onChange` sekali di akhir.

### 4. Penanda gerbong menjangkau jalur foto & GPS non-kamera

Penanda yang dibangun untuk Mode Kamera Penuh belum dipakai jalur lain yang
sama-sama asinkron: unggah galeri/kamera OS (menunggu kompresi hingga 6 foto),
dan tombol "Ambil GPS" (`acquireAccuratePosition` menunggu akurasi membaik —
belasan detik, dan menulis lewat **dua** jalur: `onUpdate` tiap fix serta
`.then()` di akhir). Keduanya kini menolak hasil yang datang ke aset yang keliru.

### 5. Koordinat aset yang SUDAH tersurvei tak lagi tertimpa diam-diam

Tombol ◀/▶ di Mode Kamera Penuh membuka aset lama untuk ditinjau tanpa surveyor
harus kembali ke tempatnya — dan GPS live yang terus mengalir dulu mengganti
titik tersimpan aset itu dengan posisi surveyor saat ini. Ini bukan kebijakan
baru: efek auto-GPS di berkas yang **sama** sudah memakai penjaga
`asetSudahBerkoordinat`; jalur kamera kini mematuhinya juga. Survei ulang yang
disengaja tetap bisa lewat tombol "Ambil GPS".

### 6. Cache fix GPS kini bergerbang akurasi

`aman_last_gps` ditulis pada **setiap** fix tanpa gerbang, lalu dipinjamkan ke
aset lain yang koordinatnya kosong. Fix ±800 m (A-GPS belum mengunci di dalam
gedung) ikut tersimpan dan diterapkan seolah setara fix ±5 m — melewati gerbang
±8 m yang dipatuhi rana kamera. Lebih buruk: bila fix segar gagal, nilai
pinjaman itu **menetap** dan ikut tersimpan, sehingga aset tercatat di titik
aset lain. `lib/gpsCache.js` menyimpan akurasi dan menolak yang tak layak; bila
fix segar gagal, nilai pinjaman dibersihkan dan surveyor diberi tahu.

- Uji: +24 → **175 frontend**. Tiga jaminan terpenting diverifikasi dengan
  MUTASI: mengembalikan perilaku timpa, memutus penyatuan foto, dan mencabut
  gerbang akurasi masing-masing menggagalkan tepat uji yang menjaganya.

> **Belum tergarap.** Delapan dugaan berkeparahan tinggi lain belum sempat
> disanggah (batas fan-out audit), antara lain: `photo_ops.keep` diperlakukan
> sebagai indeks posisional sementara `If-Match` hanya opsional; Ubah Massal
> menulis tanpa menaikkan `version` sehingga penjaga OCC lewat; catatan
> idempotensi CREATE hanya berumur 24 jam padahal antrean luring bisa lebih tua.
> Dicatat apa adanya, bukan didiamkan.

---

## [#643] Integritas foto↔koordinat di antrean luring + toolbar satu baris — 2026-07-27

Laporan lapangan: *"perbaiki antara informasi utuh satu kesatuan titik koordinat
dengan foto yang terambil oleh kamera agar tidak saling tertukar … terutama pada
saat PWA offline sedang berjalan karena sinyal yang buruk"*. Ditelusuri sampai
ke kodenya, dan ada **dua** cara data benar-benar bisa tertukar. Keduanya
bekerja DIAM-DIAM: tidak ada pesan galat, tidak ada baris merah — ketahuannya
baru nanti, saat jumlah aset di server lebih sedikit daripada yang difoto
surveyor, atau saat foto sebuah aset menampilkan barang milik aset lain.

### 1. Dua aset bisa berbagi satu gerbong antrean

Setiap simpanan yang belum tersinkron dikunci oleh `statusKey`; untuk aset baru
kuncinya `tempId`, yang dibuat dengan `` `temp_${Date.now()}` ``. Kunci itu
dipakai di TIGA peta sekaligus — payload yang akan di-replay, salinan IndexedDB
(`keyPath: "statusKey"`), dan chip status di daftar. Karena semuanya PETA
berkunci, dua aset ber-`tempId` sama tidak bentrok dengan berisik: yang kedua
**menimpa** yang pertama. Foto beserta koordinat aset pertama lenyap.

Yang membuatnya nyata di lapangan bukan tabrakan satu milidetik, melainkan hal
lain: **`Date.now()` bukan jam monotonik.** Selama survei luring berjam-jam, HP
menyinkronkan waktu ke jaringan begitu sinyal sempat menyentuh; koreksi ke
BELAKANG beberapa detik sudah cukup membuat aset baru memakai id yang masih
dipegang aset lain di antrean. Dan karena antrean bertahan lintas reload,
jendela tabrakannya bukan satu milidetik melainkan **sepanjang umur antrean**.

`lib/idAntrean.js` menggantinya dengan id yang keunikannya tak pernah bersandar
pada jam: UUID acak, atau — untuk WebView Android lawas tanpa `crypto` —
garam sesi acak + penghitung monoton. Stempel waktu tetap disertakan, tapi
hanya agar antrean enak ditelusuri manusia. Awalan `temp_` dipertahankan
(beberapa guard bergantung padanya) dan kini punya satu pemilik, `apakahTempId`.

### 2. Foto bisa mendarat di aset berikutnya

Tombol rana di Mode Kamera Penuh TIDAK ikut `busy` — padahal semua tombol aksi
lain ikut. Selama simpan berjalan, form menunggu `await compressPhotos(...)`
yang di HP low-end dengan 6 foto memakan detik-detikan. Foto yang diambil pada
jendela itu masuk ke state SETELAH payload dibekukan, lalu ikut terhapus
`resetForm` — atau, lebih buruk, menempel ke aset **berikutnya** padahal
watermark di badan fotonya mencantumkan kode & NUP aset **sebelumnya**. Bukti
visual dan data induknya jadi bercerita berbeda.

Menambal jendela itu saja tidak cukup — masih ada jendela kedua saat thumbnail
dibuat. Jadi solusinya di tingkat yang lebih dalam: **foto membawa identitas
aset yang dituju sejak rana ditekan**. `lib/sesiAset.js` menyusun penanda
gerbong dari (id aset, jumlah aset tersimpan di sesi kamera) — hitungannya ikut
karena dalam alur "Simpan & Aset Baru" id-nya sama-sama kosong, sehingga tanpa
itu dua aset berturut-turut berpenanda identik. Penanda diperiksa dua kali:
sebelum dan sesudah `await`. Foto dari jalur lama tanpa penanda (unggah galeri)
tetap diterima — menolaknya akan mematikan jalur yang tak bermasalah.

Rana juga kini ikut `busy`, dengan penjaga di DALAM fungsi `capture`, bukan
hanya atribut `disabled` — atribut itu urusan tampilan, yang menjaga
satu-kesatuan foto↔aset adalah penjaganya.

### 3. Toolbar tak pernah pecah baris

- **Gaya Marker (Pin ↔ Foto sampul) hilang di tablet & desktop.** Selama ini
  hanya ada di menu gabungan HP, padahal justru di layar lebar tampilan foto
  paling berguna. Kini tombolnya berdiri sendiri mulai `sm`.
- **Tombol "X tutup" peta dihapus di semua ukuran.** Tombol "Peta" di toolbar
  sudah berperan sebagai saklar dan tombol Back HP sudah dijaga `useBackGuard`
  — satu pintu keluar cukup, dan ruangnya berharga.
- **`flex-wrap` dibuang** di bar peta DAN di toolbar desktop. Dulu tombol yang
  tak muat turun membentuk baris kedua-ketiga yang mendorong peta/daftar ke
  bawah; makin banyak kontrol, makin sempit isinya. Kini yang menyusut adalah
  LABEL: teks baru muncul di `xl` ke atas, di bawahnya semua kontrol jadi
  ikon-saja (judul tetap terbaca lewat tooltip). Tampilan HP tak berubah.
  `overflow-x-auto` jadi katup pengaman terakhir — kalaupun ada kombinasi
  ekstrem yang tetap tak muat, bar-nya menggeser mendatar, bukan pecah ke bawah.

- Uji: +13 → **151 frontend**. Yang diuji bukan "id berupa string", melainkan
  justru dua cara gagalnya: 1.000 id dalam satu milidetik, dan jam yang MUNDUR
  di tengah survei. Ketiganya diverifikasi dengan MUTASI — implementasi lama
  `` `temp_${Date.now()}` `` menggagalkan 4 dari 5 uji.

---

## [#642] Spasial Fase 16: belah wilayah dengan garis — memecah, bukan mengurangi — 2026-07-27

Laporan lapangan: *"tombol edit seperti cutting tidak bisa memotong garis lurus
wilayah"*. Setelah ditelusuri ini **bukan bug**: alat potong bawaan geoman hanya
bisa MENGURANGI — Anda menggambar poligon, dan irisannya dibuang dari bentuk
asal. Itu tepat untuk melubangi, tetapi bukan yang dibutuhkan penataan denah,
yaitu MEMECAH satu kawasan jadi dua kawasan bersebelahan yang keduanya tetap ada.

Menggambar ulang dua poligon dari nol bukan jalan keluar: batas bersamanya tak
pernah benar-benar berimpit, selalu tersisa celah atau tumpang tindih beberapa
meter yang lalu ditangkap validasi topologi. Membelah menyelesaikannya dari
sumbernya — kedua bagian berbagi PERSIS deret verteks yang sama di sisi potongnya.

Alurnya: gambar **garis** melintasi wilayah → server membelah → pratinjau
menampilkan jumlah bagian berikut luas masing-masing → konfirmasi. Garis
sengaja dibedakan dari poligon lewat tipe layer-nya, jadi tak ada mode atau
tombol tambahan yang harus diingat operator.

**Bagian TERBESAR mewarisi node asal** — id, kode, aset yang menempatinya, dan
seluruh riwayat tetap menempel pada wilayah yang secara praktis masih "wilayah
itu". Membuat dua node baru lalu menghapus yang lama akan memutus tautan aset
dan jejak audit tanpa alasan. Sisanya lahir sebagai **draft**, pola sama dengan
impor: hasil otomatis diperiksa manusia dulu.

**Tiga pagar yang tak terlihat sampai dibutuhkan:**

- **Garis yang berhenti di dalam wilayah** adalah kegagalan paling sering, dan
  pesan pustaka ("split failed") tak menolong siapa pun. shapely hanya membelah
  bila garis melintas PENUH — kedua ujungnya wajib di luar poligon. Pesannya
  kini memberi tahu apa yang harus dilakukan: *"Tarik garis melintas penuh dari
  sisi satu ke sisi seberang."*
- **Kekekalan luas diperiksa.** Bila jumlah luas bagian tak sepadan dengan asal,
  pembelahan DIBATALKAN — lebih baik menolak daripada diam-diam memangkas
  wilayah.
- **Serpihan mikro dibuang.** Garis yang menyerempet sudut menyisakan pecahan
  beberapa cm² yang tak pernah dimaksudkan siapa pun.

- Backend: `belah_utils.py` (murni) + `POST /spasial/node/{id}/belah`
  (`terapkan=false` = pratinjau, tak menulis apa pun). Ber-audit.
- Uji: +15 → **1.063 backend**. Yang diuji bukan "berhasil membelah kotak",
  melainkan justru kasus gagalnya.

### Tiga temuan lapangan lain dalam PR yang sama

Ikut dalam PR ini karena berasal dari satu sesi uji coba yang sama, satu di
antaranya berakar jauh dari gejalanya.

**Dialog impor meluber.** Lebar tetap tanpa plafon tinggi: file dengan banyak
kolom atribut mendorong tombol "Mulai Impor" keluar layar, dan teks sampel
terpotong di tepi kanan. Kini `max-w-2xl`, tinggi dibatasi `90vh` dan bisa
digulir, sampel MEMBUNGKUS (bukan `truncate`) di area bergulir sendiri.
Memotong sampel justru menyembunyikan nilai yang dipakai operator untuk
memilih field yang benar.

**"Impor SHP banyak wilayah hanya terbaca baris pertama" — parser tidak
bersalah.** Dibuktikan dengan shapefile 6 poligon: parser membaca 6 fitur dan
worker membuat 6 node. Akarnya di PENAMAAN. Tebakan field nama hanya
mencocokkan `/nama|name|label/`, sementara file GIS instansi kerap tak memakai
kata itu sama sekali — shapefile BWP IKN berkolom `OBJECTID/BWP/ROMAWI/
KETERANGAN`, tak satu pun cocok, sehingga keenam node lahir bernama "Kawasan
impor 1…6". Enam node memang terbentuk, tetapi di pohon terbaca sebagai sampah
generik, dan operator wajar menyimpulkan hanya baris pertama yang terbaca.

Tebakan kini melihat ISI, bukan hanya nama kolom: kolom seragam tak membedakan
apa pun, kolom seluruhnya angka hampir pasti id internal, kolom terlalu panjang
adalah deskripsi. Panel pratinjau juga menyatakan terang bahwa setiap baris
menjadi satu node tersendiri, berikut jumlahnya.

**Peta kawasan ber-induk lambat lalu akhirnya muncul.** Batas node dan batas
INDUK diambil BERURUTAN — dua poligon berverteks ribuan harus selesai satu per
satu sebelum apa pun tampil. Kini induk diambil paralel dan peta terpasang
setelah permintaan pertama. Spinner juga diberi KETERANGAN TAHAP ("Mengambil
batas wilayah…", "Menempatkan peta…") plus penanda latar saat konteks sekitar
masih menyusul; lingkaran berputar tanpa kata membuat operator menyimpulkan
aplikasi macet lalu menutup dialog tepat saat prosesnya hampir selesai.

> Satu butir laporan lapangan belum tergarap: *"tampilannya juga tolong
> betulkan"* baru diperbaiki untuk layar yang terlihat di tangkapan layar
> (dialog impor). Layar lain menunggu tangkapan layarnya — menebak berisiko
> merombak yang sudah benar.

---

## [#641] Spasial Fase 15: pendamping pelacakan — HP yang sudah ada jadi pelacak, biaya Rp 0 — 2026-07-27

Sampai fase ini seluruh pipeline posisi sudah lengkap tetapi **tak ada satu pun
perangkat yang bisa mengisinya** tanpa membeli pelacak GPS. Dokumen arsitektur
§9.1 sudah menandai jalannya sejak awal: aplikasi pendamping PWA, "paling
direkomendasikan, biaya **Rp 0**" — karena HP-nya sudah ada di tangan orangnya.

Halaman publik `/lacak` dibuka pemegang barang **tanpa akun**: tempel token (atau
buka tautan yang dikirim admin), baca pemberitahuan, tekan Mulai. Admin
mendapatkan tautan siap-kirim langsung di dialog token.

### Pemberitahuan ke pemegang barang adalah bagian dari fitur, bukan hiasan

UU PDP mewajibkan subjek data diberi tahu. Kewajiban itu paling sulit dibantah
bila pemberitahuannya muncul **di layar orangnya sendiri**, dibaca dari kode
penegaknya, **tepat sebelum** ia menekan Mulai — bukan terkubur di lampiran BAST
yang ditandatangani setahun lalu. Karena itu tombol Mulai tak muncul sebelum
kebijakan berhasil dimuat, dan isinya menyebut tiga hal dengan kalimat manusia:
apa yang direkam ("hanya nama gedung — titik koordinat Anda dibuang sebelum
disimpan"), kapan, dan berapa lama disimpan.

Bila izin darurat sedang aktif, pemegang **diberi tahu di layar yang sama** —
ia berhak mengetahuinya saat itu, bukan belakangan dari orang lain.

### Batas yang dinyatakan terus terang, bukan disembunyikan

**Peramban menghentikan JavaScript saat layar mati atau pengguna berpindah
aplikasi.** Itu batasan peramban, bukan setelan yang bisa diakali. Halaman ini
karena itu berguna untuk perjalanan dinas yang diawasi, kendaraan bertablet
terpasang, dan pencarian barang hilang — **bukan** pengganti pelacak khusus
untuk pemantauan 24 jam. Dinyatakan di panel tersendiri di layar, bukan catatan
kaki: menjanjikan lebih hanya akan membuat orang mengandalkan sesuatu yang
diam-diam berhenti bekerja.

`Wake Lock` dipakai agar layar tak mati selama merekam, tetapi kegagalannya
(ditolak peramban atau mode hemat baterai) tak menghentikan perekaman.

### Keputusan kecil yang menentukan

- **Kadensi adaptif** — bergerak 60 detik, diam 15 menit (arsitektur §8.4 #20).
  Perangkat diam tak perlu dilaporkan tiap menit; kuota data di lapangan mahal.
- **Antrean luring di `localStorage`**, dibuang **hanya setelah** server mengaku
  menerima. Membuang lebih dulu berarti kehilangan posisi saat jaringan putus di
  tengah kirim — dan duplikatnya toh sudah aman ditolak indeks unik (Fase 11
  dibangun persis untuk ini). Saat penuh, yang dibuang **yang paling tua**.
- **Token di `?token=` segera dihapus dari address bar** (`history.replaceState`).
  URL menetap di riwayat peramban, ikut terkirim sebagai `Referer`, dan gampang
  ter-screenshot; token yang tinggal di sana sama saja dengan token yang ditempel
  di badan barang.
- **`GET /iot/perangkat/saya` tidak mengembalikan data posisi apa pun.** Token
  perangkat cukup untuk MENGIRIM, tak cukup untuk MEMBACA riwayat — HP yang
  jatuh ke tangan orang lain tak boleh berubah jadi jendela ke jejak pemegangnya.

---

## [#640] Spasial Fase 14: izin darurat — janji kepatuhan yang selama ini mustahil dijalankan — 2026-07-27

Fase 10 menuliskan janji: *"presisi penuh dibuka HANYA saat barang dilaporkan
hilang, dengan persetujuan pejabat, beralasan tertulis, berbatas waktu, dan
tercatat."* Janji itu punya penjaga sejak awal — `izin_darurat_sah()` dengan 18
uji — tetapi **tak punya pintu**. Tak ada endpoint, tak ada tombol, tak ada
jalur apa pun yang memanggilnya. Artinya sepanjang Fase 10–13, pembukaan
presisi untuk barang hilang **mustahil dilakukan**, dan kepatuhan yang mustahil
dijalankan bukan kepatuhan — ia dekorasi.

Alurnya kini utuh: operator mengajukan (alasan tertulis wajib) → pejabat yang
**bukan pemohon** menyetujui → presisi terbuka → dicabut manual atau habis
sendiri, maksimal 72 jam. Validasinya memanggil `izin_darurat_sah()` **apa
adanya**, tidak menyalin aturannya — aturan yang ditulis dua kali akan
menyimpang cepat atau lambat.

### Sifat yang paling mudah disalahpahami, dan paling mahal bila baru diketahui saat darurat

**Izin ini berlaku MAJU saja.** Observasi profil `personal` yang sudah terlanjur
masuk SUDAH kehilangan koordinatnya di jalur tulis — Fase 10 sengaja **tidak
menyimpan**, bukan menyimpan lalu menyembunyikan. Tak ada izin, tanda tangan,
atau perintah apa pun yang bisa memulihkannya.

Konsekuensi operasionalnya keras: izin harus terbit **segera** setelah barang
dilaporkan hilang; menunda berarti kehilangan jejak yang tak bisa diambil
kembali. Ini bukan kekurangan yang akan ditambal nanti — ia harga langsung dari
kebijakan minimisasi. Karena itu dinyatakan di tiga tempat sekaligus: DPIA §5
dalam kotak peringatan, docstring modul, dan panel di layar tempat izin
diajukan. Ada uji khusus yang menguncinya:
`test_izin_TIDAK_memulihkan_data_yang_sudah_didegradasi` — kalau uji itu suatu
saat gagal, artinya ada yang mulai menyimpan data mentah "untuk berjaga-jaga",
dan seluruh janji DPIA runtuh.

- Backend: `iot_izin_darurat` + 4 endpoint (ajukan/setujui/cabut/daftar), semua
  ber-audit. Jalur ingest mengecek izin aktif **sekali per batch**.
- Register menampilkan **seluruh riwayat**, bukan hanya yang aktif — nilai utama
  mekanisme ini justru pada jejaknya. Ia juga masuk `RESET_KEEP`: catatan siapa
  membuka apa atas persetujuan siapa adalah hal yang paling tak boleh lenyap
  saat reset, sementara datanya sendiri sudah terlanjur dibuka.
- Frontend: tab keempat di halaman Pelacakan Aset.
- Uji: +5 (alur izin & sifat maju-saja) → **1.048 backend**, 138 frontend.

---

## [#639] Spasial Fase 13: halaman Pelacakan Aset — dua fase yang tadinya hanya bisa dipakai mesin — 2026-07-27

Fase 11 (ingest posisi) dan Fase 12 (geofence) sudah berjalan penuh, tetapi
seluruhnya hidup di API: tak ada satu pun layar yang menampilkannya. Fitur yang
hanya bisa dipanggil `curl` bukan fitur yang selesai — halaman ini yang
menjadikannya bisa dipakai orang.

Satu halaman, tiga tab. **Perangkat**: daftar pelacak dengan kesehatan yang bisa
dibaca sekilas (terakhir terdengar, baterai, jam perangkat meragukan),
pendaftaran, dan rotasi token. **Pagar Area**: pasang/ubah/hapus aturan geofence.
**Peringatan**: register dengan lencana belum-dibaca, tandai sudah dilihat, dan
tombol tindak lanjut.

**Kebijakan privasi ditaruh di ATAS layar, bukan disembunyikan di dokumen.**
Angkanya dibaca dari endpoint yang membacanya dari `privasi_utils` — kode yang
MENEGAKKANNYA — jadi yang dilihat pengguna dijamin sama dengan yang dijalankan
mesin. Kebijakan yang tak terlihat tak bisa diperiksa siapa pun, dan salinan
dokumen yang basi lebih buruk daripada tak ada dokumen.

Beberapa keputusan tampilan yang menjelaskan sistemnya, bukan sekadar
menghiasinya:

- **Token ditampilkan sekali dengan kalimat yang jujur**: server hanya menyimpan
  sidiknya, jadi menutup jendela itu berarti satu-satunya jalan adalah rotasi.
  Pengguna berhak tahu itu SEBELUM menutup, bukan sesudah.
- **Panel pagar menjelaskan histeresis dalam satu kalimat** — kenapa "keluar"
  butuh 25 m dan beberapa menit. Tanpa itu, penundaan peringatan terbaca sebagai
  sistem yang lambat, padahal justru itu yang membuatnya layak dipercaya.
- **Dialog tindak lanjut menyebut tenggat 15 hari kerja PMK 207/2021** dan
  menyatakan terang-terangan bahwa langkah ini sengaja manual.
- **Peringatan dari antrean offline berlabel "Data susulan"**, supaya operator
  tak mengejar aset yang sudah kembali kemarin.
- **Riwayat posisi menyebutkan bahwa datanya sudah tersaring saat MASUK**, bukan
  saat ditampilkan — yang tak boleh disimpan memang tak pernah tersimpan.

Backend ikut berubah kecil tapi perlu: `GET /spasial/node` kini menurunkan
`tipe_geometri` (geometrinya sendiri tetap dibuang — poligon kawasan bisa ribuan
verteks). Tanpa itu pemilih area menawarkan node yang **pasti ditolak** backend,
dan pengguna baru tahu setelah menabraknya.

- Frontend baru: `pages/PelacakanPage.jsx`, masuk Beranda Modul grup Referensi.
- Verifikasi: eslint 0 error, 138 uji frontend lulus, build produksi sukses,
  1.043 uji backend lulus.

---

## [#638] Spasial Fase 12: geofence — peringatan yang bisa dipercaya karena ia tahu kapan harus DIAM — 2026-07-27

Aset yang keluar dari kawasannya sekarang memberi tahu. Bagian sulitnya bukan
"apakah titik ada di dalam poligon" — itu sudah ada sejak Fase 3. Bagian
sulitnya adalah **flapping**: perangkat yang diam persis di garis batas akan
dilaporkan GPS-nya sedikit di dalam, lalu sedikit di luar, lalu di dalam lagi,
puluhan kali per jam. Uji point-in-polygon polos akan memuntahkan puluhan
peringatan "aset keluar area" untuk aset yang tak bergerak sesenti pun — dan
peringatan yang meleset seperti itu membuat SELURUH sistem peringatan diabaikan
orang. Ada satu uji yang khusus mengunci sifat ini: perangkat diam di tepi
selama sejam harus menghasilkan **nol** peringatan.

**Tiga pagar bekerja bersama.** *Histeresis* — ambang masuk dan keluar sengaja
tidak sama: masuk dinilai pada poligon apa adanya, keluar baru diakui bila titik
sudah lebih dari 25 m DI LUAR. Titik yang menggantung 10 m di luar batas masih
dihitung di dalam. *Dwell* — perubahan harus bertahan (120 dtk masuk, 180 dtk
keluar). *Sampel minimum* — satu pembacaan liar tak bisa memicu peringatan
sendirian. Dwell saja tidak cukup: perangkat diam di batas bisa bertahan "di
luar" bermenit-menit sebelum melompat balik.

Buffer keluar diterapkan sebagai **jarak ke poligon**, bukan dengan memperbesar
poligonnya. Memperbesar bentuk **cekung** — gedung berbentuk L atau U itu lazim
— bisa melahirkan self-intersection dan mengubah jumlah verteks; jaraknya
sendiri eksak, murah, dan tak berstatus.

**Tiga cacat yang baru terlihat saat menyambungkan, bukan saat merancang:**

- **Cooldown hanya membandingkan event TERAKHIR**, sehingga deret
  masuk→keluar→masuk tak pernah teredam sama sekali — tiap event selalu berbeda
  jenis dari pendahulunya. Kini dihitung per jenis. Ketahuan karena satu uji
  yang deretnya sengaja dirapatkan sampai jatuh di dalam jendela peredam.
- **Waktu transisi dan waktu peringatan tercampur.** Keluar yang peringatannya
  teredam tetap keluar — tetapi jam "sudah berapa lama di luar" ikut teredam,
  sehingga aset yang keluar lalu perangkatnya MATI TOTAL tak akan pernah memicu
  `dwell_terlampaui`. Itu persis kasus yang paling perlu diketahui. Keduanya
  kini disimpan terpisah.
- **Idempotensi penyimpanan ≠ idempotensi peringatan.** Kirim-ulang adalah
  perilaku NORMAL at-least-once; indeks unik `obs_id` menolak duplikatnya,
  tetapi mesin status tetap memutar ulang observasi yang sama bila diberi
  seluruh isi batch — sampel dan dwell terhitung dua kali. Kini hanya observasi
  yang benar-benar baru tersimpan yang masuk mesin.

**Dua keputusan yang sengaja MENOLAK rancangan awal**, keduanya dicatat di
`docs/ARSITEKTUR-SPASIAL-IOT.md` §8.6.1:

- **Peringatan TIDAK didorong ke WebSocket yang ada.** Bus realtime repo ini
  ber-*room* `activity_id` dan siapa pun yang membuka kegiatan itu menerima
  seluruh isi room; perangkat pelacak pun tak selalu terikat kegiatan mana pun.
  Menyalurkan posisi aset ke sana = menyiarkannya ke penonton yang tak
  seharusnya. Peringatan masuk register ber-scope satker yang bisa dikueri.
- **Tiket penertiban Wasdal dibuat MANUAL satu klik, bukan otomatis.** Tiket itu
  bertenggat 15 hari kerja dan masuk register wajib PMK 207/2021; membuatnya
  otomatis dari pembacaan GPS berarti membanjiri register resmi dengan tiket
  yang mungkin hanya akibat pagar salah pasang. Manusia memutuskan mana yang
  naik jadi perkara; sistem menyiapkan bahannya.

Observasi **diurutkan waktu** sebelum dievaluasi — perangkat yang menumpahkan
antrean offline mengirim batch tak berurutan, dan mesin berdwell yang menerima
observasi terbalik menghitung durasi negatif lalu memutuskan salah tanpa gejala.
Gerbang kualitas menolak akurasi > 100 m (fix 500 m di dekat batas tak memberi
tahu apa pun tentang sisi mana titik berada) dan lompatan > 250 km/jam.
Perangkat berprofil privasi `personal` tak pernah dipagar-geo sama sekali —
koordinatnya memang sudah dibuang Fase 10, dan memagari ORANG bukan tujuan
sistem ini.

- Backend baru: `geofence_utils.py` (mesin murni), `routes/geofence.py`
  (aturan, evaluasi dari ingest, register, eskalasi).
- Sapuan `dwell_terlampaui` menumpang loop pemeliharaan per jam di `jobs.py`,
  idempoten per KEPERGIAN — bukan satu peringatan per jam selama aset hilang.
- Indeks: aturan per perangkat, **status unik per (aturan, perangkat)**, register
  per satker + partial `dibaca:false` untuk badge.
- Backup: `iot_geofence_state` di-SKIP (derivable & menyesatkan bila dipulihkan);
  `iot_geofence_aturan` masuk RESET_KEEP (konfigurasi pengawasan).
**Tinjauan adversarial menemukan 3 cacat lagi yang lolos 36 uji itu** — para
penyanggah menjalankan endpoint sungguhan, bukan membaca kode:

- **Batch backfill MEMUNDURKAN mesin status.** Mengurutkan observasi di dalam
  satu batch ternyata tidak cukup: urutan ANTAR batch tak bisa dijamin siapa
  pun. Antrean offline yang tiba belakangan menggeser `sejak` ke masa lalu, lalu
  observasi berikutnya menghitung selisih raksasa dan mematangkan dwell
  SEKETIKA — melahirkan `keluar` palsu untuk aset yang justru sedang di dalam.
  Kini ada pagar monoton: observasi yang lebih tua dari yang sudah diproses
  diabaikan.
- **Cooldown memakai selisih BERTANDA.** Observasi ber-`ts` mundur menghasilkan
  angka negatif — yang selalu lebih kecil dari ambang — sehingga peringatan
  NYATA teredam tanpa jejak apa pun.
- **Invarian histeresis hanya dijepit di lapis rute, bukan di mesinnya.**
  `buffer_masuk_m > buffer_keluar_m` menciptakan pita jarak yang sekaligus "di
  dalam" dan "jauh di luar"; perangkat DIAM di pita itu berayun selamanya. Uji
  yang membuktikannya justru gagal pada perbaikan pertama saya — pagar yang
  hanya berdiri di pintu depan bukan pagar.

Plus: geometri **Point** diterima sebagai area pagar (jarak selalu tak-hingga →
aturan bisu selamanya, dan `Infinity` meledakkan serialisasi JSON seluruh daftar
aturan); kueri acuan outlier menyortir field **tak berindeks** sehingga memindai
seluruh riwayat perangkat tiap batch; titik ber-`outlier` dipakai sebagai acuan
berikutnya sehingga satu koordinat rusak merambat; indeks bernama `…_unik`
ternyata **tidak** unique padahal sapuan berjalan di setiap worker; eskalasi
penertiban memakai cek-lalu-tulis sehingga dua klik melahirkan dua tiket
bertenggat di register PMK 207/2021; `kode_satker` aturan tak ikut berpindah
saat perangkatnya diganti; dan pengurutan `ts_device` sebagai **teks** salah
untuk perangkat yang menulis offset zona waktu berbeda.

Tinjauan juga menemukan **uji yang hijau tanpa menguji apa pun**: `dwell_keluar_dtk`
boleh diubah jadi 0 dan 36/36 tetap lulus; regresi transisi-vs-cooldown yang
komentarnya mengaku sudah diperbaiki tak punya uji sama sekali; `sampel_min`
tak pernah diuji secara perilaku; muatan event tak pernah diperiksa. Semuanya
kini terkunci.

Gelombang kedua tinjauan menutup 4 sisanya: **tulis status kini bersyarat**
(dua batch perangkat sama dari dua worker tak lagi saling menimpa — dibuktikan
penyanggah dengan MongoDB 8.0 sungguhan); **`retro` diwariskan** ke
`dwell_terlampaui` alih-alih di-hardcode `False`, karena alarm paling keras di
sistem ini justru yang paling tak boleh terbaca segar padahal berasal dari
antrean offline; plus dua celah uji (ambang retro yang memakai konstantanya
sendiri sebagai acuan sehingga kebal mutasi, dan jarak lubang yang hanya diuji
tandanya).

Hasil akhir tinjauan: **32 dugaan diperiksa, 16 terkonfirmasi** — para
penyanggah menjalankan mongod sungguhan dan memanggil fungsi endpoint asli,
bukan membaca kode.

- Uji: +36, +18, +4 = **1.043 lulus**.

---

## [#637] Spasial Fase 11: ingest posisi IoT — perangkat mengirim, pagar privasi menyaring — 2026-07-27

Data posisi pertama akhirnya boleh masuk sistem, lewat satu jalur yang tak punya
jalan pintas: **token perangkat → normalisasi → resolusi node denah → gerbang
`saring_observasi()` → simpan**.

**Dua sifat bawaan IoT yang menentukan bentuk kode ini.** Pertama, pengiriman
bersifat *at-least-once*: perangkat lapangan kehilangan sinyal, mengirim ulang
batch yang sebenarnya sudah tiba, lalu menyala kembali dan menumpahkan antrean
offline-nya. **Duplikat itu normal, bukan anomali** — jadi penangkalnya bukan
"jangan kirim dua kali" (mustahil dijamin perangkat), melainkan `obs_id` yang
dihitung dari ISI observasi + indeks unik. Waktu terima server sengaja TIDAK
ikut di-hash: memasukkannya akan membuat tiap pengiriman ulang tampak sebagai
observasi baru — persis kegagalan yang hendak dicegah. Kedua, **jam perangkat
tak bisa dipercaya**: GPS murah menyala dengan jam 1970 atau melompat setelah
sinkronisasi. Waktu perangkat tetap disimpan sebagai bahan diagnosis, tetapi
ditandai `ts_ragu` dan tak pernah jadi satu-satunya sumber urutan.

**Resolusi node dijalankan SEBELUM penyaringan, dan itu bukan urutan yang
sembarang.** Profil `personal` membuang koordinat; kalau node baru dicari
sesudahnya, yang tersimpan adalah dokumen tanpa lokasi apa pun — kebijakan
"simpan level gedung saja" berubah diam-diam jadi "simpan yang tak berguna".
Efek sampingnya justru yang paling diinginkan: **laptop dinas di rumah
pemegangnya berada di luar semua poligon → tak ada node → tak ada satu baris pun
yang tersimpan.** Rumah, klinik, dan tempat ibadah tak perlu di-blacklist satu
per satu; bentuk sistemnya yang membuatnya tak terekam.

**Tiga kebocoran ditutup, dua di antaranya baru terlihat saat jalur ingest
disambung:**

- `lokasi_spasial.titik` — snapshot lokasi (Fase 8) MEMBAWA koordinat mentahnya.
  Membuang `geo` saja menyisakan presisi penuh di field yang justru sengaja
  dipertahankan. `saring_observasi()` kini ikut membuangnya, dengan membangun
  ulang dict bersarang (bukan `pop`) agar dokumen milik pemanggil tak termutasi.
- **Arsip backup** — retensi 30/90/365 hari ditegakkan TTL index, tetapi kalau
  observasi ikut masuk arsip yang disimpan bertahun, jejak lokasi bertahan jauh
  melewati batas yang dijanjikan DPIA: kepatuhan yang benar di database dan
  bocor lewat pintu backup. `iot_observasi` masuk `SKIP_COLLECTIONS`.
- **Peta Kolaborasi publik** — posisi IoT sengaja TIDAK menimpa
  `koordinat_latitude/longitude` aset (field itu memang mengalir ke peta yang
  bisa dibuka siapa pun pemegang tautan). Payload publiknya kini dibangun lewat
  allowlist `KUNCI_PUBLIK_TITIK` **plus uji regresi** — daftar-larangan
  mensyaratkan seseorang ingat memperbaruinya setiap kali field baru lahir, dan
  justru field baru yang paling mungkin sensitif.

Retensi memakai `privasi_utils.batas_retensi()` sebagai satu-satunya sumber
angka, mengisi `kedaluwarsa_pada` yang dieksekusi **TTL index MongoDB** — bukan
job terjadwal yang bisa mati tanpa disadari. Registry perangkat menyimpan token
sebagai **hash** (kebocoran DB tak memberi penyerang token untuk memalsukan
posisi), token ditampilkan sekali, dan token salah vs perangkat nonaktif
mengembalikan pesan yang SAMA agar penyerang tak bisa membedakannya.

- Backend baru: `iot_utils.py` (helper murni), `routes/iot.py` (registry, batch
  ingest ber-rate-limit, rotasi token, riwayat posisi, endpoint kebijakan).
- Indeks: `obs_id` unik (penegak idempotensi), TTL `kedaluwarsa_pada`,
  `(device_id, ts_server)`, `token_hash`, `(kode_satker, created_at)`.
- Reset: `iot_perangkat` masuk `RESET_KEEP` — tokennya tak bisa dilihat ulang,
  jadi menghapusnya memaksa provisioning ulang setiap perangkat di lapangan.
- Uji: +24 unit `iot_utils`, +3 pagar `lokasi_spasial.titik`, +3 payload publik.

---

## [#636] Spasial Fase 10: DPIA privasi pelacakan — kebijakan jadi KODE — 2026-07-27

Gerbang kepatuhan **sebelum** satu baris data posisi pertama masuk sistem.
Melacak perangkat yang dipegang perorangan = memproses data pribadi orang itu
(UU 27/2022 PDP) — bukan sekadar data barang.

**Kenapa sekarang, bukan setelah ingest jalan**: kebijakan privasi yang hanya
hidup di dokumen akan dilewati kode yang menyusul — bukan karena niat buruk,
tetapi karena tak ada yang memaksanya. Dengan pagar di jalur tulis SEBELUM
data pertama ada, "lupa" jadi mustahil.

**`backend/privasi_utils.py`** — §10 dokumen arsitektur diterjemahkan jadi
helper murni yang WAJIB dilewati jalur tulis posisi (Fase 11+):

| Profil | Presisi | Jendela | Retensi |
|---|---|---|---|
| `aset_tetap` | penuh | 24 jam | 365 hari |
| `kendaraan` | penuh | 24 jam | 90 hari |
| **`personal`** | **wilayah/gedung — koordinat DIBUANG** | **07:00–18:00 hari kerja** | **30 hari** |

- **Gagal-tertutup**: profil tak dikenal (salah ketik / perangkat baru belum
  dikonfigurasi) jatuh ke `personal`, bukan merekam penuh 24/7.
- **Tidak disimpan ≠ disimpan lalu disembunyikan**: observasi personal di luar
  jam kerja DITOLAK sebelum penulisan — data yang tak pernah ada tak bisa
  bocor, disalahgunakan, atau diminta lewat jalur hukum.
- Zona waktu dihormati (WITA, dapat dikonfigurasi) — menghitung jam kerja dari
  UTC mentah akan menolak observasi pagi yang sah.
- `ts_device` dipakai, bukan waktu tiba di server: batch tertunda dinilai pada
  waktu OBSERVASI-nya.
- **Izin darurat** (barang hilang) ber-tiga syarat kumulatif: alasan tertulis
  bermakna, pejabat penyetuju yang BUKAN pemohon, dan masa berlaku ≤ 72 jam —
  izin permanen sama dengan kebijakan yang dibatalkan diam-diam.
- `batas_retensi()` jadi sumber tunggal angka retensi untuk penyapu terjadwal
  DAN TTL index, agar kepatuhan tak hanya benar di atas kertas.

**`docs/DPIA-PELACAKAN-ASET.md`** — kajian dampak formal yang bisa ditunjukkan
ke auditor: dasar pemrosesan per kategori data, tabel risiko-mitigasi dengan
status penegakan, hak subjek data, dan **daftar jujur yang BELUM dikerjakan**
(runbook insiden, teks pemberitahuan BAST, filter Peta Kolaborasi publik yang
wajib menyertai endpoint ingest pertama).

Uji: +18 backend (954 total) — termasuk gagal-tertutup, penolakan di luar jam,
degradasi presisi, zona waktu, dan keempat penolakan izin darurat.

## [#635] Spasial Fase 9: custody berlokasi — aset menempati node denah — 2026-07-27

Aset bergerak kini **menempati** node denah (biasanya Ruangan), dengan jejak
perpindahan dan pertanyaan balik yang dibutuhkan opname: *"aset apa saja yang
ada di ruangan ini?"*

**Backend**:
- `PUT /api/assets/{id}/lokasi-spasial` — tempatkan/cabut penempatan. Guard
  aset lewat jalur BAKU modul aset (`pastikan_akses_aset` via kegiatan induk),
  sementara node divalidasi ter-scope satker user: menempatkan aset ke ruangan
  satker lain harus mustahil. Snapshot nama/jalur dibuat SERVER (pola Fase 8).
- `GET /api/assets/{id}/riwayat-lokasi` — jejak perpindahan, terbaru dulu.
- `GET /api/spasial/node/{id}/isi?dalam=true` — daftar aset di node **dan
  seluruh keturunannya** (via indeks multikey `ancestors`), sehingga membuka
  Gedung memperlihatkan isi tiap lantai & ruangannya. Hasil disaring ulang
  dengan guard aset yang sama — bukan sekadar mengandalkan node ter-scope,
  karena aset satker lain bisa menunjuk node era-lama tanpa stempel satker.
- **Riwayat di koleksi terpisah** (`riwayat_lokasi_aset`), bukan array di
  dokumen aset: array akan tumbuh tanpa batas seumur pakai barang dan menyeret
  setiap pembacaan aset.
- Riwayat mencatat **snapshot nama kedua sisi**, bukan sekadar id — node bisa
  diganti nama/dihapus bertahun kemudian, dan nilai bukti custody justru pada
  keterbacaan apa adanya saat kejadian.
- `pindah_lokasi_berarti`: simpan-ulang lokasi yang sama tak dicatat (riwayat
  penuh derau tak terbaca saat dibutuhkan); menggeser pin dalam ruangan yang
  sama TETAP dicatat (posisi di ruangan besar bermakna).
- Indeks baru: `assets.lokasi_spasial.node_id` (sparse) + riwayat per aset.

**Frontend**: tombol 📦 di tiap baris pohon spasial (viewer pun boleh — operasi
baca) membuka daftar isi lokasi, dengan saklar "termasuk seluruh isi di
bawahnya"; saat melihat isi Gedung, ruangan tepat tiap aset ikut ditampilkan.

Uji: +4 backend (936 total), eslint bersih, 138 jest, build sukses.

## [#634] Perbaikan: init peta editor denah tak bisa gagal senyap lagi — 2026-07-27

Laporan lanjutan: editor masih putih polos + spinner berputar, console tanpa
galat, SETELAH #631 (ResizeObserver). Bukti kunci dari screenshot: **nol
elemen Leaflet** — tanpa tombol zoom, toolbar geoman, maupun atribusi. Kalau
peta berhasil dibuat, kontrol zoom muncul SEKETIKA (sinkron) bahkan sebelum
ubin termuat. Jadi `L.map()` memang tak pernah berhasil dijalankan.

**Akar**: effect init memeriksa `if (!containerRef.current) return undefined`
dengan dep array `[]`. Bila node DOM belum terpasang saat effect pertama
jalan, effect **return diam dan TAK PERNAH diulang** — peta tak pernah dibuat,
`petaSiap` tetap false, efek pemuat tak pernah jalan, dan `memuat` (initial
`true`) tak pernah dibereskan. Hasilnya persis: area kosong + spinner abadi,
tanpa satu pun galat.

**Perbaikan**:
- Node peta jadi **callback ref (state)**, bukan `useRef` — effect init jalan
  TEPAT saat node terpasang, sehingga tak ada lagi jalur "return diam
  selamanya".
- `L.map()` + tile layer dibungkus **try/catch**; kegagalan menyetel
  `galatInit` yang **DITAMPILKAN di UI** (panel merah) dan mematikan spinner —
  kegagalan init tak bisa lagi menyamar sebagai loading.
- Pemasangan **geoman dipisah ber-try/catch**: bila plugin gagal, peta + ubin
  + bentuk tersimpan TETAP tampil (hanya alat gambar absen) dengan pesan
  jelas — sebelumnya satu exception membatalkan seluruh init secara senyap.

Catatan lapangan: aplikasi memakai service worker ber-strategi *cache-first*
untuk aset statis. Bila peramban menahan chunk JS lama, perbaikan tak akan
terlihat sampai data situs dibersihkan / SW diperbarui.

## [#633] Perbaikan: peta editor denah putih polos di dalam modal (HP) — 2026-07-26

Bukti dari screenshot HP: area peta editor PUTIH POLOS — tanpa ubin, tanpa
tombol zoom, tanpa toolbar gambar, tanpa atribusi Leaflet; console tanpa
galat. Artinya peta Leaflet tak pernah mendapat ukuran benar.

**Akar (klasik "Leaflet blank di dalam modal")**: peta dibuat saat DIALOG
MASIH BERANIMASI membuka → kontainer berukuran 0 px → Leaflet memuat 0 ubin →
peta tetap kosong. `invalidateSize()` 80 ms yang ada terlalu dini di HP
(animasi dialog lebih lambat) dan tak ada pemanggilan susulan.

**Perbaikan**: pasang **ResizeObserver** pada kontainer peta yang memanggil
`invalidateSize()` tiap kontainer berubah ukuran — termasuk saat dialog
selesai membuka — plus beberapa `invalidateSize` terjadwal (80/250/500/900 ms)
sebagai cadangan. Diterapkan di DenahEditor dan LokasiTemuanDialog (Wasdal),
keduanya menaruh peta di dalam modal.

## [#632] Perbaikan lanjut: editor & halaman denah tak pernah macet di spinner — 2026-07-26

Tindak lanjut #631 yang belum tuntas: pengguna masih melaporkan "loading
berputar terus, tidak menampilkan apa pun" saat mendesain peta dari awal.

**Akar yang sesungguhnya**: spinner `memuat`/`loading` tersangkut `true`
SELAMANYA bila salah satu request menggantung — tak ada timeout, jadi
`finally { setMemuat(false) }` tak pernah tercapai. Karena spinner overlay
menutupi seluruh editor (z-500), peta yang sudah jadi di bawahnya pun tak
terlihat — persis "tidak menampilkan apa pun, hanya berputar".

**Perbaikan** (murni ketahanan sisi klien):
- **DenahEditor**: (1) efek pemuat digerbang state `petaSiap` — tak lagi
  RETURN DIAM saat map belum ada dan meninggalkan spinner; (2) spinner
  dibereskan SEGERA setelah bentuk node dimuat — konteks tetangga menyusul di
  latar, jadi peta selalu tampil seketika meski konteks lambat/gagal;
  (3) watchdog 25 dtk + timeout 20 dtk per-request — spinner WAJIB hilang
  apa pun yang terjadi (jaringan mati, backend lambat), editor tetap bisa
  dipakai menggambar dengan toast peringatan.
- **SpasialMasterPage**: timeout 20 dtk pada muat tingkat + node, agar
  halaman pohon pun tak berputar tanpa henti bila backend menggantung.

## [#631] Perbaikan: editor denah "loading terus" saat kawasan hasil impor besar — 2026-07-26

**Gejala**: membuka editor gambar denah (Hierarki Spasial) memutar spinner
sangat lama / seolah tak selesai — muncul setelah pengguna mulai MENGIMPOR
denah (Fase 5), karena poligon kawasan hasil impor bisa berpuluh-ribu verteks.

**Akar**: editor merender batas induk + seluruh fitur tetangga di viewport
sebagai SVG. Leaflet membangun ratusan/ribuan `<path>` SVG secara SINKRON —
membekukan main thread; spinner (animasi CSS) ikut membeku sehingga tampak
"loading terus". Diperberat karena panggilan konteks memakai `level_maks`
default 100 = MEMUAT SELURUH POHON dalam viewport (setiap ruangan & lantai),
bukan hanya konteks setingkat.

**Perbaikan** (frontend, DenahEditor):
- Lapisan KONTEKS (batas induk + tetangga) dipindah ke **renderer Canvas** —
  menggambar ribuan bentuk tanpa membekukan main thread. Bentuk yang DIEDIT
  tetap SVG (geoman butuh verteks path).
- Panggilan konteks `/spasial/geojson` kini membatasi `level_maks` ke ordinal
  node yang digambar — menggambar Gedung tak lagi menarik setiap ruangan &
  lantai dalam viewport (payload + render terberat, tak berguna sebagai
  orientasi).

## [#630] Spasial Fase 8: temuan Wasdal menunjuk lokasi di denah — 2026-07-26

Tiket **penertiban** dan **pemantauan insidentil** kini bisa menunjuk lokasi
fisik: operator menancapkan titik di peta, rantai wilayah (Kawasan → … →
Gedung, plus pilihan lantai) terdeteksi otomatis lewat mesin deteksi Fase 3,
dan lokasi tersimpan pada tiket sebagai `lokasi_spasial`.

**Backend** — `PUT /api/wasdal/{penertiban|insidentil}/{id}/lokasi` (writer,
ter-scope satker):
- Klien hanya mengirim `{lat, lon, node_id}` — nama/tipe/jalur di-**snapshot
  ulang server dari dokumen node DB** (string klien tak pernah dipercaya;
  node lintas-satker → 404).
- Koordinat lewat parser modul spasial yang sama — desimal-koma format
  lapangan Indonesia ("116,70") diterima (pelajaran temuan Fase 7).
- `hapus: true` mencabut penanda; kedua aksi tercatat di log audit.
- Titik di LUAR kawasan terpetakan tetap sah sebagai penanda koordinat murni.
- Helper murni `snapshot_lokasi_temuan` di spasial_utils + 3 uji unit —
  termasuk regresi `str(None) == "None"` yang truthy dan sempat menyusup
  sebagai nama moyang palsu (tertangkap uji sebelum commit).

**Frontend (WasdalPage)**:
- Tombol 📍 di tiap baris tiket (menyala teal bila sudah ditandai) membuka
  dialog peta lazy: klik → titik tertancap → rantai wilayah tampil → opsi
  "persempit ke lantai" bila titik jatuh di gedung → Simpan.
- Chip `📍 jalur lokasi` menyatu di baris metadata tiket; hasil simpan/hapus
  langsung disalin ke baris tanpa muat ulang register.
- Deteksi ber-guard urutan (klik beruntun tak menimpa hasil terbaru); titik
  tersimpan yang korup jatuh ke "belum ada", bukan meledakkan render.

Landasan Fase 12+ (geofence IoT): temuan kini punya koordinat + node denah
yang sama dengan yang akan dipakai pelacakan aset bergerak.

## [#629] Spasial Fase 7: georeferensi denah dalam-gedung — gambar denah sebagai alas jiplak — 2026-07-26

Interior gedung tidak terlihat di citra satelit, jadi menggambar ruangan
akurat (Fase 4) selama ini menebak-nebak. Kini operator bisa MENGUNGGAH gambar
denah lantai (ekspor CAD/PDF → PNG/JPG/WebP, maks 10 MB), MENEMPATKANNYA di
atas peta lewat tiga titik sudut yang digeser (posisi + rotasi + skala + aspek
= transformasi affine penuh), lalu MENJIPLAK ruangan di atasnya.

**Backend** — gambar di GridFS, penempatan di `properties.denah_overlay`
(3 sudut lon/lat `tl/tr/bl` + opasitas):
- `POST/PUT/DELETE /api/spasial/node/{id}/overlay` (writer, ter-scope satker;
  unggah pertama mendapat penempatan awal dari bbox node → moyang bergeometri
  terdekat → titik wakil; PENGGANTIAN gambar mempertahankan penempatan).
- `GET /api/spasial/overlay/{file_id}` — streaming ber-ETag + cache lama
  (file_id baru tiap unggahan); isolasi satker lewat node PEMILIK, bukan
  sekadar ketakterkaan ObjectId.
- Pagar unggahan: baca bertahap ber-plafon, validasi PIL dari HEADER SAJA
  (piksel tak pernah didekode server — bom dekompresi ditolak murah dari
  metadata, plafon 40 MP di bawah ambang PIL), SVG tak masuk daftar (bisa
  membawa skrip), whitelist PNG/JPEG/WebP.
- **Pewarisan**: `GET /spasial/node/{id}` kini membawa `overlay_efektif` —
  overlay milik sendiri atau moyang TERDEKAT (editor ruangan otomatis
  menampilkan denah lantainya).
- Hapus node (hard delete) kini ikut membuang blob overlay — tanpa ini blob
  yatim selamanya di GridFS.

**Frontend (DenahEditor)**:
- Plugin `L.ImageOverlay.Rotated` DI-VENDOR sebagai modul ES
  (`lib/leafletImageOverlayRotated.js`, lisensi Beerware, atribusi utuh) —
  paket npm aslinya menulis ke global `L` tanpa impor: lolos build CRA tetapi
  meledak saat runtime, kelas kegagalan senyap yang kita hindari.
- Gambar dirender di pane khusus (di ATAS ubin, di BAWAH vektor,
  pointer-events none) — alas jiplak tak menutup poligon dan tak menelan klik
  alat gambar.
- Baris kontrol: unggah/ganti/hapus, slider opasitas (visual seketika,
  tersimpan bersama posisi), mode **Atur Posisi** dengan 3 marker sudut
  bernomor yang digeser langsung; overlay warisan tampil read-only placement
  dengan opsi "unggah untuk node ini".
- Konversi lon-first server ↔ lat-first Leaflet terkunci di satu modul murni
  (`lib/denahOverlay.js`) + uji — pembalikan tersebar = denah mendarat di
  Samudra Hindia.

**Dua bug data-loss LAMA tertangkap saat menelusuri jalur PUT** (bukan bug
fitur baru — sudah ada sejak Fase 5, terpicu form pohon yang tak mengirim
`properties`/`status`):
- PUT node menimpa `properties` dengan `{}` → jejak audit impor (dan kini
  overlay) TERHAPUS setiap kali node diganti nama dari pohon.
- Status yang tak dikirim di-default "aktif" → sekadar mengganti nama draft
  impor MENGAKTIFKANNYA diam-diam.
Perbaikan: semantik **None = tak diubah** untuk `properties` & `status`
(konsisten dengan `geometry`), `denah_overlay` hanya bisa diubah endpoint
overlay (metadata + blob satu paket), dan form pohon mendapat kontrol Status
eksplisit (aktivasi draft kini keputusan sadar) — dropdown
Aktif / Draft / Nonaktif.

Uji: +23 backend (929 total; sudut/bom-dekompresi/semantik-None/regresi
tinjauan) +4 jest (konversi sudut); eslint bersih; build produksi sukses.

**Tinjauan adversarial: 16 temuan, 11 bertahan refutasi — semuanya
diperbaiki** (semuanya lolos CI; CI tak menjalankan endpoint/renderer):
- (HIGH) String desimal-koma "116,70" (format Excel/lapangan Indonesia) LOLOS
  validasi tetapi meledakkan pembersih ber-`float()` mentah → 500. Validator
  dan pembersih kini memakai parser yang sama.
- (HIGH) Gagal muat gambar overlay 100% senyap — `<img>` `display:none` tanpa
  `onerror`; kini plugin vendored memancarkan event `error` dan editor
  menampilkannya.
- (MEDIUM) Gambar berheader sah tapi piksel terpotong/rusak lolos, tersimpan,
  gagal render diam-diam — kini `verify()` (susur chunk+CRC tanpa dekode
  piksel, tetap aman dari bom).
- (MEDIUM) Balapan PUT node vs unggah/hapus overlay bisa membuat node menunjuk
  blob GridFS yang sudah dihapus — `properties` kini di-$set per-kunci dan
  `denah_overlay` TAK PERNAH disentuh PUT node.
- (MEDIUM) Pewarisan overlay tak menyaring satker/status moyang — metadata
  bisa bocor lewat data ancestors korup; kini disaring.
- (MEDIUM) Geser marker Atur Posisi lalu klik di luar dialog membuang
  penempatan tanpa peringatan — kini dicegah seperti goresan belum tersimpan.
- (LOW ×5) Guard atomik anti "overlay hantu" pasca-DELETE; penempatan bawaan
  bbox raksasa dijepit agar selalu sah; opasitas tersimpan saat slider
  dilepas; hapus overlay jatuh kembali ke warisan moyang; fitBounds ber-
  `maxZoom` untuk geometri titik (asumsi "fitBounds melempar" ternyata salah).

## [#628] Spasial Fase 6: ekspor denah ke SHP / KML / KMZ / GeoJSON + template QGIS/Google Earth — 2026-07-26

Sisi kebalikan mandat impor-ekspor: denah yang tersusun di aplikasi kini bisa
DIEKSPOR ke format GIS baku, dan pengguna tanpa denah bisa mengunduh TEMPLATE
kosong ber-skema untuk digambar di QGIS / Google Earth lalu diimpor balik.

**Kontrak mutu = round-trip.** Seluruh keluaran modul ekspor
(`ekspor_geo_utils.py`) diuji terbaca balik oleh parser impor Fase 5 SUNGGUHAN
— geometri eksak, lubang, MultiPolygon, dan atribut utuh; kedua sisi saling
mengunci.

**Empat format** — `GET /api/spasial/ekspor?format=…` (operasi baca; viewer
boleh; ter-scope satker; rate-limit 10/menit; serialisasi di thread):
- **GeoJSON** — geometri disalin apa adanya (lon-first RFC 7946), properti
  `nama`/`kode`/`lokasi`/`status`/`luas_m2`; kunci `nama` disengaja agar
  prapilih dropdown impor memetakannya otomatis saat diimpor balik.
- **KML/KMZ** — Folder BERSARANG mengikuti hierarki (di Google Earth pohon
  Kawasan → … → Ruangan tampil sebagai pohon, bukan daftar datar); moyang tanpa
  geometri tetap hadir sebagai Folder. Dibangun via ElementTree — nama node
  buatan pengguna (`Blok <A> & "B"`) ter-escape otomatis, bukan dirangkai
  f-string.
- **Shapefile-zip** — `denah.*` (poligon) + `denah_titik.*` (Point dipisah:
  satu shapefile satu tipe shape) + `.prj` WGS84 + `.cpg` UTF-8 + BACA_SAYA.
  **Orientasi cincin ESRI ditegakkan sendiri** (luar CW, lubang CCW — kebalikan
  RFC 7946): terverifikasi empiris pyshp 3.1.4 menulis cincin apa adanya DAN
  pembacanya toleran terhadap orientasi salah, jadi uji round-trip lewat pyshp
  saja menyesatkan — ada uji khusus yang membaca arah putaran MENTAH dari file.

**Cakupan**: seluruh denah satker atau satu subtree (`dalam` = node + seluruh
keturunan via indeks multikey `ancestors`); draft ikut secara bawaan (alur
"perbaiki di QGIS → impor ulang" paling sering justru pada draft), bisa
dimatikan.

**Template** — `GET /api/spasial/ekspor/template?format=shp|kml`: kerangka
satu-fitur-contoh ber-kolom NAMA/KODE yang cocok dengan auto-deteksi impor,
plus petunjuk alur bolak-balik berbahasa Indonesia (BACA_SAYA.txt / deskripsi
KML).

**UI**: tombol **Ekspor** di Hierarki Spasial (tampil juga untuk viewer —
server menegakkan `require_user`), dialog lazy: format + cakupan + saklar
draft + dua tombol template. Unduhan via blob axios (auth header interceptor,
tanpa token di URL).

Uji: +16 backend — termasuk uji orientasi cincin pada file mentah, escaping
XML, siklus data tak membuat rekursi abadi, unicode DBF, dan kedua template.

**Temuan tinjauan (dua-duanya lolos CI — CI tak menjalankan serialisasi):**
- Karakter kontrol C0 di nama node (\x00/\x01, bisa masuk lewat API) membuat
  ElementTree menghasilkan XML yang TAK TERBACA — satu nama beracun merusak
  seluruh ekspor KML. Kini disaring (`_bersih_teks`) di semua teks keluaran,
  termasuk DBF (pembaca ber-semantik C-string terpotong di \x00).
- `metrik.luas_m2` non-angka dari data lama membuat `float()` melempar di
  tengah penulisan shapefile — satu node kotor menggagalkan seluruh ekspor.
  Kini jatuh ke 0 dan ekspor jalan terus.
- Pertahanan kecil: kode_satker disaring alfanumerik sebelum dikutip di header
  `Content-Disposition`.

## [#627] Spasial Fase 5: impor denah dari Shapefile / KML / KMZ / GeoJSON — 2026-07-26

Fase 5 program Spasial & IoT: denah yang sudah digambar di QGIS/ArcGIS/Google
Earth kini bisa DIIMPOR — memenuhi bagian "sistem dapat menerima membaca hasil
impor misalkan shp, kml, kmz" dari mandat awal.

**Alur dua langkah** (tombol Impor di Hierarki Spasial):
1. **Pratinjau sinkron** — file diperiksa tanpa menulis apa pun: format, cacah
   fitur, CRS terdeteksi, daftar field atribut + SAMPEL nilainya. Sampel ini
   krusial: nama ber-mojibake (encoding DBF salah — jebakan #3 riset Fase 0)
   harus terlihat SEBELUM tersimpan, bukan sesudahnya.
2. **Impor via job latar** — operator memetakan tingkat/induk/field nama+kode
   dan saklar perbaikan topologi; worker mem-parse penuh, membersihkan tiap
   fitur, lalu menulis node ber-status **DRAFT** (badge kuning di pohon). Draft
   sengaja tak ikut deteksi lokasi maupun lapisan denah — hasil impor diperiksa
   manusia dulu, baru diaktifkan.

**Parser (`impor_geo_utils.py`, murni & teruji):**
- **SHP-zip** via pyshp (`__geo_interface__` menangani pengelompokan cincin/
  lubang); encoding dari `.cpg`, fallback UTF-8 → CP1252 dengan peringatan.
- **CRS dari `.prj`**: WGS84 geografis langsung; **UTM (semua zona) dikonversi**
  via paket `utm` — keluaran SELALU [bujur, lintang] (jebakan #2). Proyeksi lain
  DITOLAK dengan menyebut namanya: menebak CRS = denah di lokasi salah tanpa
  satu pun galat. Tanpa `.prj`: koordinat rentang derajat → diasumsikan WGS84
  ber-peringatan; rentang meter → ditolak tegas.
- **KML/KMZ**: parser namespace-agnostik; `<!DOCTYPE`/`<!ENTITY` ditolak dini
  (billion-laughs/XXE); cincin KML yang tak tertutup DITUTUP (RFC 7946);
  ExtendedData/SimpleData jadi atribut; Placemark titik/garis dilewati.
- **Pembersihan per fitur**: struktur → topologi → (opsional) `make_valid`
  ber-**pagar-luas**: perubahan luas > 1% TIDAK diterapkan otomatis (jebakan #1
  riset — `buffer(0)` memangkas separuh poligon tanpa galat, dilarang di repo
  ini). Pagar hanya berlaku bila luas asal BERMAKNA: shoelace pada poligon
  menyilang-diri saling meniadakan (bow-tie simetris "berluas 0", terukur 0 vs
  61,8 juta m²), dan menerapkan pagar pada angka artefak akan menolak justru
  kasus perbaikan utama.

**Keamanan & ketahanan**: plafon 20 MB + 2.000 fitur; seluruh atribut sumber
tersimpan di `properties.impor` (jejak audit); kode ganda otomatis dikosongkan
ber-peringatan; keunikan kode dicek SATU fetch untuk seluruh batch; parsing +
shapely di thread; rate-limit pratinjau 12/menit & mulai 6/menit; satu impor
berjalan pada satu waktu (semaphore); laporan job memuat daftar fitur yang
dilewati BESERTA alasannya — plafon tampilan 50, jumlah asli tetap dilaporkan.
Dependensi baru: `utm==0.8.1` (27 KB, sesuai rencana arsitektur Fase 0).

**Perbaikan temuan tinjauan adversarial** (13 temuan bertahan refutasi):

- **Zip-bomb (HIGH)** — `z.read()` dipanggil sebelum ukuran isi diperiksa: zip
  199 KB mengembang jadi 200 MB dan meng-OOM proses SEBELUM parser sempat
  berjalan; plafon unggah 20 MB tak menolongnya sama sekali. `_buka_zip_aman()`
  kini menjumlahkan `ZipInfo.file_size` dari infolist (metadata, tanpa
  dekompresi) dan menolak di atas 80 MB atau 200 anggota — dipakai jalur KMZ
  maupun SHP-zip. Terukur: zip 200 MB ditolak tanpa dibuka.
- **KML berspasi setelah koma** — QGIS/Google Earth lazim menulis
  `"116.70, -1.40, 0"`; parser berbasis `.split()` memecah `"116.70,"` dari
  `"-1.40"` sehingga SELURUH Placemark hilang tanpa satu pun galat (impor 0
  fitur, senyap — kelas jebakan yang sama dengan tiga jebakan riset Fase 0).
  Diganti pemindaian regex pasangan bujur-lintang.
- **Nama field DBF kembar** — DBF memotong nama kolom di 10 karakter, jadi
  `NAMA_BANGUNAN` dan `NAMA_BANGUN_LAMA` sama-sama menjadi `NAMA_BANGU` dan
  dict atribut menelan salah satunya. Kini di-dedup (`NAMA_BANGU__2`) dengan
  peringatan di pratinjau.
- **`insert_many` gagal sebagian** — satu dokumen ditolak membuat seluruh job
  berstatus `failed` padahal ratusan node draft yang sah SUDAH tertulis (yatim,
  tanpa laporan). Kini `ordered=False` + `BulkWriteError` dibaca untuk
  melaporkan jumlah yang benar-benar tertulis.
- **Pembacaan unggahan** — `file.read()` memuat seluruh badan ke memori sebelum
  plafon diperiksa; diganti pembacaan bertahap 1 MB yang berhenti di plafon.
- **Atribut sumber raksasa** — `properties.impor.atribut` disalin apa adanya
  dari DBF/KML; dokumen node bisa melewati batas 16 MB Mongo dan ditolak saat
  insert. Kini dipotong 60 kolom × 500 karakter — dan nama kunci yang dipotong
  40 karakter ikut di-dedup: nama properti KML/GeoJSON panjangnya bebas, jadi
  dua field ber-awalan sama akan saling menimpa (terukur: 200 kolom runtuh jadi
  1) — kelas bug yang sama dengan pemotongan 10 karakter DBF.
- **Progres macet di 5%** untuk file < 25 fitur (kelipatan 25 tak pernah
  tercapai) — pembaruan kini juga terjadi pada fitur terakhir.
- **Kosakata status job** — worker menulis `failed`, penyapu job macet
  (`jobs.bersihkan_job_basi`) menulis `error`; dialog hanya mengenali `failed`
  sehingga job yang di-relabel penyapu di-poll selamanya. Dialog kini memakai
  penanda universal `done: true` plus ketiga nama status.
- **Dialog impor**: balasan pratinjau file lama tak lagi menimpa pratinjau file
  baru (penjaga nomor urut); polling berhenti setelah 8 kegagalan beruntun atau
  15 menit alih-alih memanggil `/jobs` tanpa batas; polling berhenti saat dialog
  ditutup (tak ada `setState` pasca-unmount); dialog **boleh ditutup** selagi
  impor berjalan — job hidup di server, mengunci dialog hanya menyandera
  operator; berkas > 20 MB ditolak di klien sebelum diunggah; `value` input file
  dikosongkan agar memilih berkas bernama sama lagi tetap memicu pembacaan.

Uji: +22 backend (893 total) — fixture dibangun DI DALAM uji (KML string, SHP
via pyshp Writer in-memory, KMZ zip) sehingga tak ada file biner di repo;
termasuk uji konversi UTM→WGS84 yang menuntut hasil mendarat di kotak IKN, dan
uji regresi untuk zip-bomb, KML berspasi, serta dedup nama field DBF.

## [#626] Spasial Fase 4: gambar poligon denah di aplikasi + validasi topologi — 2026-07-26

Fase 4 program Spasial & IoT: poligon denah kini bisa DIGAMBAR langsung di
aplikasi — melengkapi celah yang tersisa dari Fase 3, saat geometri hanya bisa
masuk lewat API.

**Editor denah (`DenahEditor`)** — dibuka dari tombol baru di tiap baris
Hierarki Spasial. Dialog Leaflet + `@geoman-io/leaflet-geoman-free` (dimuat
LAZY — mayoritas kunjungan halaman pohon tak pernah membuka editor, jadi berat
pustakanya tak dibayar semua orang): gambar poligon/persegi, ubah verteks,
geser, potong lubang (void/atrium), hapus. Batas INDUK tampil sebagai garis
putus-putus hijau sebagai panduan; tetangga sekitar tampil redup sebagai
konteks (keduanya tak bisa diedit). Dua goresan terpisah menjadi MultiPolygon —
kampus dengan dua tapak itu nyata. Cincin hasil geoman DITUTUP otomatis
(geoman tidak menutup cincin pada `toGeoJSON`, RFC 7946 mewajibkannya).

**Validasi topologi (`topologi_utils.py`, shapely 2.1.2)** — menutup persis
kelas bug yang Fase 3 dokumentasikan sebagai "belum diperiksa": bow-tie
(menyilang diri), lubang di luar cincin luar, bagian bersarang, cincin kembar.
Pesan galat diterjemahkan ke bahasa manusia. Lazy-import + degradasi anggun:
tanpa shapely seluruh cek melewati dirinya dan MongoDB kembali jadi jaring
terakhir (perilaku Fase 3) — server tak pernah mati karena libgeos absen.

**Kebijakan blokir vs peringatan (keputusan sadar):**
- Galat **topologi → BLOKIR** (400): geometri tak sah merusak pembangunan
  indeks 2dsphere untuk SELURUH koleksi.
- Pelanggaran **containment → PERINGATAN** saja: poligon digambar orang berbeda
  pada waktu berbeda, dan seluruh desain deteksi Fase 3 (`pilih_rantai`) sudah
  menerima containment tak sempurna. Memblokir berarti gedung yang benar tak
  bisa disimpan hanya karena batas kawasan digambar kasar. Mode per tingkat
  ikut registry: `ketat` (toleransi ±0,5 m untuk verteks yang menempel batas),
  `longgar` (persil/titik cukup bersinggungan), `sumbu_z`/akar dilewati.

**Pratinjau sebelum simpan** — `POST /api/spasial/validasi-geometri` memeriksa
tanpa menyimpan: galat struktur/topologi, peringatan containment, luas kasar.
Bila topologi rusak, server mengusulkan hasil `make_valid` — usulan DITAWARKAN
ke operator lewat tombol "Terapkan perbaikan otomatis", tak pernah diterapkan
diam-diam saat menyimpan (make_valid bisa memecah poligon atau menggeser
bentuk; keputusannya milik manusia). Usulan hanya dikirim bila benar-benar
lolos seluruh validasi — menawarkan perbaikan yang akan ditolak itu menyesatkan.

Respons simpan node kini membawa `peringatan[]` (containment) yang ditampilkan
sebagai toast. Dependensi baru: `shapely==2.1.2` (backend, +22 MB RAM hanya
saat dipakai) + `@geoman-io/leaflet-geoman-free@2.20.0` (frontend, chunk lazy)
— keduanya persis yang direncanakan dokumen arsitektur Fase 0.

**Perbaikan temuan tinjauan adversarial** (15 temuan, 7 bertahan refutasi):

- **HIGH — bentuk yang DIHAPUS tetap tersimpan kembali.** Tanpa
  `setGlobalOptions({layerGroup})`, `_getContainingLayer()` geoman mengembalikan
  MAP, sehingga "Hapus bentuk" hanya melepas layer dari peta — registry `_layers`
  milik FeatureGroup tetap memegangnya. `kumpulkanGeometri` meng-iterasi grup,
  jadi bentuk yang dihapus dipungut lagi, di-PUT, dan diberi toast **sukses
  palsu**; bentuknya muncul lagi saat editor dibuka ulang. Penghapusan sebagian
  MultiPolygon bahkan tak punya jalur benar sama sekali.
- **HIGH — CPU-DoS lewat endpoint pratinjau.** Plafon verteks hanya menjaga
  `validasi_topologi`; `perbaiki_topologi` tak punya plafon, padahal endpoint
  memanggilnya persis setelah validasi gagal — termasuk saat gagalnya karena
  "terlalu besar". Terukur di repo ini: bintang menyilang-diri **101 verteks**
  = 0,07 detik di validasi tetapi **6,85 detik** di `make_valid`, dan skalanya
  super-linear. Handler `async` tanpa offload berarti event loop worker beku
  untuk SEMUA pengguna. Ditutup berlapis: plafon di `perbaiki_topologi` juga,
  plafon diturunkan 100.000 → **20.000** (angka tinggi memberi rasa aman palsu),
  seluruh kerja GEOS dipindah ke thread (`asyncio.to_thread`), dan
  `@limiter.limit("60/minute")` sesuai konvensi repo untuk endpoint berat-CPU.
- **MEDIUM — `peringatan[]` dibuang form pohon.** Form Ubah Node adalah
  SATU-SATUNYA UI yang bisa mengubah induk, dan backend sengaja menghitung
  containment bentuk tersimpan terhadap induk BARU untuk kasus itu — tetapi
  responsnya dibuang. Karena pelanggaran containment memang tidak memblokir,
  operator tak pernah tahu gedungnya kini di luar batas induknya.
- **MEDIUM — editor menyimpan dari prop `node` basi.** PUT mengganti seluruh
  field; memakai snapshot baris pohon (bisa berumur menit) MEMBALIKKAN ganti
  nama/pindah induk yang dilakukan orang lain. Kini detail di-fetch ulang tepat
  sebelum PUT, dengan detail pembukaan dialog sebagai cadangan.
- **LOW** — tooltip "Batas induk" tak pernah muncul karena `interactive:false`
  membuat renderer tak mendaftarkan event mouse (`pmIgnore` sudah cukup untuk
  melindunginya dari edit geoman).

Uji: +21 backend (871 total; fixture membuktikan tiap kasus topologi memang
LOLOS cek struktural — kalau tidak, ujinya tak membuktikan apa-apa) & +14
frontend (134 total).

## [#625] Spasial Fase 3 (susulan): panel denah tak lagi memicu kotak seleksi — 2026-07-26

Temuan terakhir dari fase refutasi tinjauan #624, yang sempat saya tolak dengan
alasan yang KELIRU. Saya menyimpulkan panel denah aman karena ia "bersebelahan
dengan container Leaflet"; kenyataannya listener kotak seleksi dipasang pada
**pembungkus** (`mapWrapRef`), dan kedua panel adalah ANAK dari pembungkus itu.

Akibatnya, saat tiga saklar menyala bersamaan — Denah + Mode Seleksi + "Pilih
Area" — menyentuh tombol lapis atau pemilih lantai justru memulai kotak seleksi:
`setPointerCapture` membuat Chrome menelan `click` pada keturunan pembungkus
sehingga tombolnya tak bereaksi, sementara mode "Pilih Area" mati sendiri tanpa
penjelasan. Penjaga `onControlOrMarker` hanya mengenali kelas `.leaflet-*`,
sedangkan panel ini memakai kelas Tailwind. Ditutup dengan penanda
`[data-peta-panel]` pada kedua panel + pengecualian di penjaga tersebut.

## [#624] Spasial Fase 3: geometri, deteksi lokasi otomatis dari titik, peta berlapis — 2026-07-26

Fase 3 program Spasial & IoT: pohon Fase 2 kini punya BENTUK. Inilah fase yang
menghidupkan permintaan inti — tancapkan koordinat, wilayahnya terdeteksi sendiri.

**Deteksi lokasi dari satu titik** — `POST /api/spasial/lokasi-di-titik`
mengembalikan SELURUH rantai yang memuat titik itu (Kawasan → Zona → Distrik →
Blok → … → Gedung) lewat **satu** kueri `$geoIntersects`; itulah alasan pohon
disimpan dalam satu koleksi polimorfik. Rantai selalu mengikuti `ancestors` pohon,
bukan gabungan hasil geo — bila keduanya berbeda (poligon tumpang tindih milik
cabang lain) hasil geo yang menyimpang ditandai `alternatif` dan diberi catatan,
bukan diam-diam dipakai. Di luar semua poligon BUKAN galat: dikembalikan tetangga
terdekat dalam radius 500 m sebagai tawaran.

**Berhenti di Gedung, lantai dipilih manusia** — lantai tak bisa disimpulkan dari
koordinat 2D (semua lantai berbagi jejak yang sama). Gedung berlantai satu langsung
terpilih; sisanya memunculkan pemilih lantai. Setelah lantai dipilih,
`GET /api/spasial/ruangan-di-titik` menentukan ruangannya. Nol hasil juga bukan
galat — titik bisa berada di koridor, sehingga daftar ruangan lantai itu
dikembalikan untuk dipilih. Auto-pilih ruangan hanya diizinkan bila akurasi GPS
≤ 30 m (`boleh_auto_ruangan`); pin manual dianggap paling akurat.

**Denah berlapis di Peta Aset** — saklar "Denah" merender poligon di atas ubin peta
dengan renderer **canvas** (bukan SVG: ribuan node DOM membuat peramban HP
tersendat) pada pane sendiri di BAWAH pin aset, sehingga pin tetap bisa diklik.
Dimuat **per-viewport** dengan bbox berpadding — geser kecil tak menembak request
baru — dan **LOD per zoom**: zoom jauh hanya Kawasan/Zona, gedung baru diminta pada
zoom rapat. Plafon keras 3.000 fitur; di atas itu klien menerima titik pusat saja
plus penanda `terpotong`. Tiap tingkat bisa disembunyikan sendiri lewat panel lapis
(batas administratif digambar putus-putus, batas fisik utuh). Ketuk gedung →
pemilih lantai bergaya panel lift (rooftop di atas, basement di bawah) → ruangan
lantai itu tampil, dimuat lewat parameter `induk` agar lantai lain tak bertumpuk.

**Indeks** — `spasial_node.geometry` 2dsphere + majemuk `(parent_id, lantai.ordinal)`
supaya urutan lantai datang dari indeks, bukan SORT di memori.

**Catatan verifikasi rencana kueri** — `$geoIntersects` tetap memberi jawaban BENAR
tanpa indeks; ia hanya memindai seluruh koleksi. Bug "indeks tak terpakai" karena
itu takkan pernah muncul sebagai hasil salah, hanya sebagai endpoint yang melambat
seiring denah bertambah. Ditambahkan `tests/test_spasial_indeks.py` yang membaca
rencana kueri (`explain`) dan menuntut IXSCAN, bukan COLLSCAN, memakai koleksi
sementara yang di-drop setelahnya. Butuh MongoDB hidup → ber-marker `integration`,
tidak ikut CI. Jalankan di server: `pytest -m integration tests/test_spasial_indeks.py`.

**Perbaikan temuan tinjauan adversarial:**

- **HIGH — gerbang akurasi GPS TERBALIK di atas 100 km.** `boleh_auto_ruangan`
  memakai `parse_koordinat(akurasi_m, 100000.0)`, padahal argumen kedua fungsi
  itu adalah BATAS RENTANG: nilai di luar batas keluar sebagai `None`, dan baris
  berikutnya menafsirkan `None` sebagai "akurasi tak dilaporkan = cukup". Akibatnya
  30,1 m ditolak (benar) tetapi 150.000 m diterima. Ini persis kasus yang ambang
  30 m dibuat untuk memblokir: peramban yang jatuh ke penentuan posisi berbasis
  IP/menara lazim melaporkan akurasi ratusan kilometer, sehingga RUANGAN — jangkar
  KIR & DBR — bisa ditetapkan otomatis dari titik yang berada di mana saja dalam
  radius 150 km. Kini "tak dilaporkan", "dilaporkan & masuk akal", dan "dilaporkan
  tapi rusak (negatif/NaN/inf)" dibedakan tegas; ditambah uji monotonisitas agar
  celah pembalik serupa tak bisa muncul lagi diam-diam.
- **MEDIUM — `alternatif` ikut dihitung `diabaikan`, sehingga `konsisten` palsu-False.**
  Dua gedung berimpit dinding itu lumrah, dan `$geoIntersects` memang memuat titik
  di batas untuk KEDUA poligon. Node yang sama lalu dilaporkan di `alternatif` DAN
  `diabaikan` dengan makna berlawanan, dan `catatan` mengaku rantai ditambal dari
  ancestors padahal tak ada tingkat yang ditambal. Alternatif sesama tingkat kini
  dikecualikan; kandidat di tingkat lain yang bukan leluhur tetap tertangkap.

Gelombang kedua temuan (dimensi endpoint & geometri):

- **Pemotongan kandidat membuang tingkat TERDALAM.** `lokasi-di-titik` mengurut
  `ordinal_level` MENAIK lalu `to_list(50)` — jadi bila plafon kena, yang terbuang
  justru gedung yang dicari, menyisakan kawasan. Kini diurut MENURUN (plafon
  membuang tingkat terluas, yang toh disusun ulang dari `ancestors`) dan plafonnya
  dinaikkan ke 200.
- **bbox selebar dunia → MongoDB memakai KOMPLEMEN.** Poligon GeoJSON biasa yang
  luasnya melebihi setengah bola ditafsirkan sebagai kebalikannya; pada zoom sangat
  jauh viewport berpadding mencapai ukuran itu dan denah hilang **tanpa pesan galat
  apa pun**. Kotak selebar itu kini sengaja tidak dipakai menyaring.
- **bbox terbalik/pipih → HTTP 500.** Menghasilkan cincin berverteks kembar yang
  dijawab MongoDB dengan `OperationFailure`. Kini ditolak 400 dengan pesan jelas.
  Logikanya diangkat jadi helper murni `kotak_dari_bbox` agar teruji unit.
- **Validator geometri jatuh sendiri.** `{"type":"Point","coordinates":{"lon":1}}`
  melempar `KeyError` → HTTP 500, bukan 400 berisi penjelasan. Validator yang crash
  lebih buruk daripada tidak ada validator. Kini semua bentuk `coordinates` cacat
  ditolak dengan pesan, diuji parametrik agar tak pernah melempar lagi.
- **Cincin degenerat lolos.** Cincin tanpa 3 titik berbeda lolos cek "tertutup &
  4 titik" tetapi ditolak MongoDB saat indeks dibangun — dan satu dokumen rusak
  bisa menggagalkan pembangunan indeks untuk SELURUH koleksi.
- **Auto-pilih lantai mengabaikan status.** Gedung dengan satu lantai *draft*
  (masih digambar) langsung terpilih. Kini hanya lantai `aktif` yang boleh
  ditetapkan otomatis; lantai draft/nonaktif tetap ditampilkan agar operator sadar.
- `level_maks` dijepit ke rentang registry (bukan jalan pintas menarik seluruh
  denah satker); proyeksi `lantai/{gedung_id}` dilengkapi agar respons tak separuh
  `None`; namespace cache `spasial` yang tak pernah dipakai dihapus — komentarnya
  menyatakan aturan wajib yang tak ditegakkan apa pun.

Batasan yang **sengaja tidak** diperbaiki, kini didokumentasikan di kode:
antimeridian (bujur ±180) membuat bbox/titik wakil/luas kacau. Menanganinya berarti
memecah geometri dan mengubah semua turunan — biaya besar untuk kasus yang tak bisa
terjadi di sini (Indonesia 95°BT–141°BT).

Gelombang ketiga (dimensi siklus-hidup Leaflet & kontrak klien-server):

- **bbox dijepit SETELAH cek degenerasi.** Leaflet `getBounds()` mengembalikan
  bujur yang tak dibungkus setelah peta digeser melewati antimeridian (mis.
  `{barat:190, timur:195}`). Rentang mentahnya wajar, tetapi kedua tepi menjepit
  ke 180 sehingga kotaknya pipih — server balas 400, cache viewport dikosongkan,
  lalu **setiap** geser peta menembak request gagal berikutnya. Kini dicek ulang
  setelah penjepitan dan permintaannya dilewatkan sama sekali.
- **Lapis yang di-unhide mencuri klik & tooltip.** Renderer canvas menggambar
  sesuai urutan penambahan dan uji-klik dimenangkan layer yang digambar TERAKHIR,
  jadi `addTo` polos menaruh Kawasan di atas segalanya. Seluruh grup kini disusun
  ulang menurut ordinal menaik setiap kali visibilitas berubah.
- **Pemilih lantai menutupi kontrol zoom & tombol Lokasi Saya.** Panel ber-z-500
  di atas container peta ber-z-0; selama denah gedung terbuka, zoom dan GPS tak
  bisa ditekan. Dipindah ke kanan, di bawah kompas.
- **Ruangan di bawah SAYAP tak pernah tampil.** Registry mengizinkan
  Lantai → Sayap → Ruangan, tetapi klien meminta anak LANGSUNG saja. Ditambah
  parameter `dalam=` (seluruh keturunan lewat indeks multikey `ancestors`), dan
  klien beralih memakainya.
- **`lantai.ordinal: null` terbaca sebagai 0.** `Number(null)` = 0 dan 0 itu
  ordinal yang sah (lantai akses utama), jadi lantai yang ordinalnya belum diisi
  menyamar sebagai lantai dasar dan menyusup ke tengah urutan lift. Diangkat ke
  helper tunggal `ordinalLantai` yang dipakai pengurutan maupun penampilan.
- Efek Leaflet dikeluarkan dari updater `setState` (updater wajib murni; React
  memanggilnya dua kali di StrictMode); request dibatalkan saat unmount agar
  respons tak menulis ke peta yang sudah dihancurkan; ganti Satker Aktif kini
  mengosongkan layer SEKETIKA alih-alih menyisakan denah satker lama di layar
  selama request berjalan; hook melewati fetch saat offline (peta aset memang
  dirancang jalan dari snapshot lokal); klik ulang gedung yang sama tak lagi
  membuang lantai terpilih; ruangan lantai terpilih digambar sebagai sorotan.

Sisa temuan bernilai rendah ikut ditutup: `prioritas` berisi teks (dari impor data
lama) melempar `ValueError` dan menjatuhkan seluruh endpoint deteksi jadi 500;
peredam toast galat direset saat lapisan dihidupkan ulang; opsi gaya `redup` yang
tak pernah dipanggil siapa pun dihapus. Ditambah uji **kontrak klien↔server** yang
mengikat nama field respons ke pembacaan klien — salah nama field tak akan pernah
menggagalkan eslint, build, maupun uji lain; ia hanya membuat peta tampil kosong
tanpa satu pun pesan galat.

Batasan yang didokumentasikan (bukan diperbaiki): `validasi_geometri` bersifat
STRUKTURAL, bukan topologis. Poligon menyilang-diri (bow-tie), cincin dalam yang
keluar dari cincin luar, dan cincin bertumpang-tindih belum diperiksa — itu butuh
operasi geometri sungguhan (shapely) yang memang dijadwalkan masuk pada fase
menggambar & impor. Sampai saat itu MongoDB tetap jaring terakhirnya.

Uji: +40 backend (850 total) & +44 frontend (120 total), seluruhnya logika murni
tanpa Mongo maupun Leaflet.

## [#623] Spasial Fase 2: registry level + pohon `spasial_node` (hierarki berlapis) — 2026-07-26

Fase 2 program Spasial & IoT: menyusun POHON denah kawasan berlapis. Belum ada
geometri (gambar poligon + deteksi lokasi otomatis menyusul di Fase 3).

**Hierarki 13 tingkat** — Kawasan → Zona(WP) → Distrik(SWP) → Blok → Sub-Blok →
Persil → Tapak → Gedung → Lantai → Sayap → **Ruangan** (jangkar KIR/DBR,
PMK 181/2016), dengan Wilayah sebagai akar opsional. Registry di-seed sekali;
`preset` memilih label operator ("Zona (WP)"/"Distrik (Sub-WP)") sementara kode
baku WP/SWP tetap benar untuk ekspor & dokumen resmi. Ordinal berjarak 10 agar
tingkat baru bisa disisipkan tanpa migrasi; tingkat boleh dilompati.

**Koleksi & endpoint** — `spasial_level` (registry global) + `spasial_node`
(pohon polimorfik, ISOLASI SATKER 5 titik). Pola pohon hybrid: `parent_id`
satu-satunya yang boleh diedit; `ancestors[]` + `jalur` diturunkan darinya. Pindah
induk menulis ulang seluruh keturunan dalam satu bulk_write; guard siklus; hapus
ditolak bila punya anak (cegah sub-pohon yatim). Keunikan kode per-satker-per-tipe
ditegakkan di aplikasi (bukan indeks unik global). `spasial_level` + `spasial_node`
masuk RESET_KEEP — denah = hasil survei lapangan yang tak bisa dibuat ulang mudah.

**Halaman Hierarki Spasial** — pohon collapsible, pencarian (menyorot & membentang
jalur ke hasil), tambah/ubah/hapus dengan dropdown tingkat + induk berjenjang;
tipe Lantai memunculkan input ordinal (gaya IMDF), tipe Blok memunculkan kode Zona
RDTR. Saklar preset penamaan. Viewer read-only.

**Perbaikan temuan tinjauan adversarial** (26 agen; 16 dikonfirmasi):
- **HIGH** — cascade pindah-induk menggandakan id node di `ancestors` keturunan
  (jalur/kedalaman salah, `ancestors_nama` tak sejajar). Diekstrak ke helper murni
  `susun_ulang_keturunan` + 4 uji regresi.
- **MEDIUM** — node yatim ber-`kode_satker ""` merosotkan helper turunan
  (peta-parent, cek-unik, cascade) jadi lintas-satker → di-scope ke satker USER.
- Ganti nama node non-daun kini ikut memperbarui `ancestors_nama` keturunan.
- Status `dihapus` tak bisa lagi dikirim klien (whitelist); `_susun_derivasi`
  menolak induk ber-status dihapus; `lantai_ordinal` dibersihkan saat tipe berubah;
  `log_audit` menyertakan `kode_satker` agar admin satker melihat jejaknya.
- Frontend: pencarian membentang leluhur hasil + dihitung O(n) (bukan O(n²)/ketik);
  target sentuh 44px (`.tap-expand`) + `data-testid`; ganti preset tak memuat ulang
  seluruh pohon.

Uji: +25 (810 total, seluruhnya logika murni tanpa Mongo).

## [#622] Spasial Fase 1: field `geo` + indeks 2dsphere pertama + tutup kebocoran KIR — 2026-07-26

Fase 1 dari program Spasial & IoT (arsitektur: `docs/ARSITEKTUR-SPASIAL-IOT.md`).
PR fondasi terkecil yang mungkin, sekaligus menutup satu kebocoran data nyata.

**KEAMANAN — kebocoran lintas-satker di KIR ditutup.** `routes/reports.py`
memuat master ruangan dengan `db.ruangan.find({})` **tanpa scope satker**, lalu
mencocokkannya berdasarkan NAMA ruangan lewat `cocok_ruangan_master`. Akibatnya
nama Penanggung Jawab Ruangan milik satker lain — yang kebetulan menamai
ruangannya sama, misalnya "Ruang Rapat" — ikut tercetak di KIR satker ini.
Kueri asetnya sendiri sudah benar ter-scope lewat `scope_query_aset`; hanya
baris master ruangan yang terlewat. Endpoint daftar ruangan kanonik
(`routes/ruangan.py`) sudah memakai `scope_query_field_satker` sejak awal,
sehingga ini satu-satunya penyimpangan.

**Fondasi geospasial.** Koordinat aset tersimpan sebagai STRING
(`koordinat_latitude`/`koordinat_longitude`) dan string tidak dapat diindeks
`2dsphere`, sehingga setiap kueri peta berbasis area adalah full collection
scan — repo ini sebelumnya **tidak punya satu pun indeks geospasial**.

- `spasial_utils.py` (baru, murni, tanpa dependensi berat): parsing koordinat
  ber-koma desimal Indonesia, penolakan NaN/inf, batas lintang ±90 vs bujur
  ±180 yang berbeda, deteksi lintang/bujur tertukar, dan pembentukan GeoJSON
  Point ber-urutan **[bujur, lintang]** sesuai RFC 7946.
- Titik **(0,0) "Null Island" ditolak** — itu penanda de-facto parsing gagal;
  tanpa penolakan ini ribuan aset bisa terpetakan ke satu titik di Teluk Guinea.
- Field turunan `geo` di-maintain di SELURUH jalur tulis yang menyentuh
  koordinat: 2 titik insert aset, PATCH (menggabungkan dokumen lama + perubahan
  karena pengguna lazim memperbaiki satu sumbu saja), ubah-massal, dan impor
  Excel. Koordinat yang dikosongkan **membuang** `geo`, bukan membiarkannya
  basi — aset yang koordinatnya dihapus tak boleh tetap muncul di posisi lama.
- Ubah-massal memakai satu `update_many` sehingga `geo` tak dapat dihitung
  per-aset: bila hanya SATU sumbu diubah massal, `geo` sengaja dibuang. Aset
  keluar dari indeks lebih baik daripada memegang posisi yang salah diam-diam.
- Indeks `assets_geo_2dsphere` — indeks geospasial pertama di repo.

**De-duplikasi.** Dua parser koordinat terpisah (`_geo_coord` di `exports.py`,
`_parse_coord` di `peta_kolaborasi.py`) dengan kelemahan yang saling melengkapi
(satu memeriksa rentang tanpa cek berhingga, satunya sebaliknya) kini keduanya
mendelegasikan ke helper kanonik. Uji khusus menjaga agar perilaku pada masukan
lazim tidak berubah sehingga ekspor KML/SHP dan Peta Kolaborasi tetap sama.

Uji: +18 (786 total), fokus pada jebakan yang gagal senyap — urutan bujur/lintang
terbalik, NaN yang lolos perbandingan, dan Null Island.

## [#621] Dokumen arsitektur Spasial & IoT (Fase 0) — 2026-07-26

Riset & arsitektur untuk referensi ruangan berlapis dan pelacakan aset bergerak;
dokumentasi murni tanpa perubahan kode. Lihat `docs/ARSITEKTUR-SPASIAL-IOT.md`.

Koreksi klasifikasi hierarki: **kawasan** naik ke posisi teratas (UU 26/2007 +
PP 21/2021 menetapkan zona sebagai *sejenis* kawasan, bukan anaknya), dan
**RUANGAN** ditambahkan sebagai tingkat terkecil karena dialah jangkar KIR/DBR
(PMK 181/2016). Urutan final: Kawasan → Zona(WP) → Distrik(SWP) → Blok → Persil
→ Tapak → Gedung → Lantai → Sayap → Ruangan, dengan kosakata pemilik
dipertahankan lewat preset penamaan. Koreksi lain: KPIKN bukan induk KIKN
(saudara sebaya, 56.159 + 196.501 = 252.660 ha), zona RDTR tak bisa jadi
tingkatan, dan IMEI tidak dapat memberi lokasi.

## [#620] Satker Aktif (act-as) super-admin lintas modul + judul berjalan saat diklik — 2026-07-26

Menindaklanjuti umpan balik: judul panjang di Arsip yang terpotong tak terbaca,
dan super-admin yang wajib bisa memilih satker saat input agar data benar-benar
terisolasi antar satker.

**Satker Aktif (act-as-satker).** Super-admin pusat (role `admin` + `kode_satker`
kosong) kini memilih **Satker Aktif** dari bilah atas; **seluruh aplikasi** (lihat
+ input) berperilaku sebagai satker itu. Default **"Semua Satker"** = lintas-satker
seperti biasa. Penyuntikan dilakukan di **satu titik** — lapisan dependency auth
(`require_user`/`require_user_or_query_token` membaca header `X-Satker-Aktif`,
`_terapkan_satker_aktif` menyuntik `kode_satker`) — sehingga SELURUH mesin isolasi
(`scope_query_*`, `pastikan_akses_*`, stempel INSERT) ikut TANPA menyentuh callsite,
dan mewarisi semua perbaikan isolasi REVIEW-9. Otoritas tetap super-admin lewat
penanda `_super_admin_asli` (tak terkunci dari backup/restore/reset saat act-as).
Frontend: header disisipkan di semua interceptor axios + query `sa=` untuk
laporan/PDF via `window.open`; `SatkerAktifBar` hanya untuk super-admin; logout
membersihkan `satker_aktif`.

**Judul berjalan saat diklik.** Komponen `MarqueeOnTap`: judul ter-`truncate`
berjalan saat ditap untuk menampilkan bagian terpotong; menghormati
`prefers-reduced-motion` + tooltip hover. Diterapkan ke Arsip Laporan Lintas
Kegiatan (judul + baris meta) & subjudul header.

**Perbaikan temuan tinjauan adversarial** (19 agen; 8 dikonfirmasi, 6 dibantah):

- **KEAMANAN** — `_buang_efemeral` (buang `_super_admin_asli`/`_satker_aktif`/
  `_kode_satker_asli`) kini juga diterapkan pada dokumen **target** di
  `pastikan_kelola_akun` + `admin_user` di `reset_all_data`, dan field efemeral
  di-strip saat impor user pada **restore** — menutup backdoor ambil-alih akun
  pusat via restore backup pihak luar.
- **Footgun** — **restore** (unggah & dari-arsip) kini ditolak (400) selagi
  super-admin ber-act-as satu satker, sama seperti guard reset (menimpa SELURUH
  satker padahal UI ter-scope satu satker).
- Buat kegiatan: auto-isi `kode_satker` dari satker aktif dipindah SEBELUM
  validasi wajib (dulu kode mati — 400 memicu lebih dulu).
- Bilah pemilih satker: `daftar_satker` kini menampilkan **seluruh** master untuk
  super-admin asli meski sedang act-as (dulu daftar menciut jadi satu satker,
  tak bisa pindah X→Y langsung).
- Antrean simpan offline: replay memakai satker **saat di-enqueue** (bukan yang
  aktif kini) — cegah 403 "milik satker lain" bila satker diganti sebelum sinkron.
- Sinkron antar-tab: ganti satker di satu tab memuat ulang tab lain agar tampilan
  konsisten dengan scope yang benar-benar dikirim.

## [#619] Audit REVIEW-9 (15): SELURUH sisa temuan workflow ditutup (20/20) — 2026-07-26

Seluruh kandidat temuan workflow ditriase ULANG terhadap `main` pasca-`[#618]`
(28 diperiksa, 20 ternyata masih terbuka) lalu ditutup semua.

**TINGGI**

1. **`periode_pelaporan` tanpa dimensi satker sama sekali.** Register siklus
   LBKP/LBP ini dibaca, dibuat, DIKUNCI, dibuka, ditenggat, dan dihapus lintas
   satker: admin satker A mengunci periode 2026-S1 → SELURUH satker ikut
   terkunci dan tak dapat menutup buku; ia juga dapat membuka/menghapus kunci
   satker lain sehingga penanda FINAL pada LBKP/CaLBMN mereka hilang. Satker
   kedua yang mendaftarkan periode sama pun ditolak 409. Kini dokumen
   distempel, 8 titik akses di-scope, penanda FINAL diambil dari periode
   satker sendiri, dan indeks unik diganti majemuk `[kode_satker, kunci_unik]`
   (indeks global lama di-drop dulu — tanpa itu perbaikannya justru mengubah
   409 menjadi DuplicateKeyError 500).
2. **Idempotency-Key tidak terikat pemilik.** Kunci dipilih KLIEN dan disimpan
   apa adanya, jadi menebak kunci satker lain = MEMUTAR ULANG respons
   tersimpan mereka. Helper `kunci_idem()` mengikat kunci ke identitas
   pemanggil, diterapkan di SUMBER (tempat header dibaca) pada 7 handler.
3. **`report_settings` global + logo ditulis admin satker mana pun.** Dokumen
   singleton itu DASAR kop SEMUA satker; kini khusus super-admin pusat. Kop
   milik satker sendiri tetap lewat Master Satker yang sudah ber-guard.

**BUG FUNGSIONAL (bukan isolasi).** `PATCHABLE_FIELDS` memuat `photos` dan
`document_checklist` yang BERBENTUK LIST, tetapi guard anti-injeksi menolak
SEMUA nilai list — kedua field itu dinyatakan patchable namun SELALU gagal
400, sehingga edit kelengkapan dokumen lewat PATCH mustahil. Kini list
diizinkan khusus untuk field berbentuk list, dengan penolakan operator NoSQL
REKURSIF (kunci ber-awalan `$` atau bertitik) di kedalaman mana pun.

**SEDANG.** LBP mengulang cacat tombstone yang sudah diperbaiki di LBKP/CaLBMN
(saldo akhir bisa MINUS + volume penghapusan satker lain bocor); artifact job
ekspor dapat diunduh admin satker lain (kini job distempel kode_satker);
`pastikan_akses_kegiatan_id` FAIL-OPEN saat kegiatan induk hilang → aset yatim
terbuka lintas satker (kini fail-closed, super-admin tetap dapat merapikan);
migrasi GridFS seluruh-DB hanya `require_admin`; KOP per-satker dilewati di
DHPB, BA-Perbaikan, dan BA Pemusnahan; LIMA lookup Master Pegawai lintas
satker (dua di antaranya membocorkan NAMA lewat pesan galat, satu berfungsi
sebagai oracle "Meninggal Dunia"); TIGA deret nomor bersama yang semestinya
per satker (tiket kegiatan, NUP reklasifikasi, kode barang persediaan);
validasi satker impor SIMAN memanen + mencetak balik daftar kode se-instansi;
dasbor & ekspor CSV integritas menghitung register seluruh satker; tautan aset
pada register Pengadaan tak ber-guard; keunikan `nomor_surat` kegiatan global;
ringkasan kegiatan dari `asset_ids` kiriman KLIEN tanpa scope.

**RENDAH.** Guard "masih dipakai" saat menghapus kode klasifikasi arsip hanya
membaca peta GLOBAL, padahal `peta_klasifikasi` kini juga per satker.

Uji: 747 unit test hijau (+2 uji baru: PATCH field list vs operator NoSQL,
`kunci_idem` terikat pemilik), `yarn build` sukses.

---

## [#618] Audit REVIEW-9 (10–14): tinjauan-atas-tinjauan — 4 celah berat + 3 regresi sendiri — 2026-07-25

Setelah `[#617]`, dua verifikasi independen dijalankan atas hasilnya sendiri:
satu memburu regresi pada diff-nya, satu menyapu ~25 file rute yang TIDAK
tersentuh sapuan mana pun. Keduanya menemukan hal nyata — termasuk kesalahan
pada perbaikan `[#617]` itu sendiri. Semua sudah ditutup di rangkaian ini.

**Celah BERAT yang masih terbuka (bukan temuan lama):**

1. **Pengambilalihan penuh satker lain** (`activities.py`). Konfirmasi
   "perbarui dengan input saat ini" memigrasi MASSAL seluruh dokumen ber-kode
   satker lama ke kode baru — 21 koleksi, termasuk `users`. Guard hanya
   memeriksa kode kegiatan = kode pemanggil, TIDAK kode yang dimigrasi. User
   satker A cukup membuat kegiatan ber-NAMA satker B dengan kodenya sendiri →
   seluruh data dan akun satker B berpindah jadi milik A. Kini migrasi
   lintas-kode khusus super-admin.
2. **Spesimen tanda tangan** (`ttd.py`). Simpan/lihat/hapus mencari
   pejabat/pegawai murni by id tanpa guard, padahal gambar itu DISEMATKAN
   otomatis ke PDF resmi — menimpanya setara memalsukan tanda tangan pejabat
   satker lain.
3. **IDOR e-sign** (3 endpoint): dokumen ber-TTD, lembar pengesahan (memuat
   gambar tanda tangan semua penanda tangan), dan terbit-ulang link e-sign
   (yang memberi hak menandatangani dokumen resmi satker lain).
4. **Eskalasi ke super-admin** yang `[#617]` klaim sudah ditutup, ternyata
   masih terbuka lewat rute lain: `change-role` dapat mempromosikan pendaftar
   TANPA ikatan satker menjadi "admin" — dan admin tanpa ikatan = super-admin.

**Tiga regresi yang dibawa `[#617]` sendiri:**

- Tombol buka foto/dokumen kelengkapan di kartu galeri **selalu 401** — endpoint
  doc-file ditutup dari anonim, tetapi tab baru tak membawa header
  Authorization. Kini lewat `authMediaUrl()`.
- **Nomor surat ganda**: counter agenda per-satker di-seed dari surat
  ber-stempel saja, padahal stempel itu belum pernah di-backfill → seed 0 →
  nomor 1,2,3… terbit ulang. Seed kini = maks(counter global lama, no_agenda
  tertinggi). Pratinjau memakai jalur seed yang sama agar tak menampilkan
  nomor yang sudah terpakai.
- **Direktori akun memaparkan akun super-admin pusat** ke tiap admin satker —
  helper scope dokumen ikut mencocokkan `kode_satker` kosong, yang pada AKUN
  justru berarti pusat.

**Koreksi arah sebaliknya.** `penganggaran_kalender` sempat di-scope, lalu
dikembalikan, lalu dipasang lagi setelah bukti ditimbang: catatan yang
dikembalikan endpoint itu sendiri berbunyi "tenggat internal tiap K/L berbeda…
isi berdasar kalender penganggaran resmi unit Anda". Argumen "ada di
RESET_KEEP berarti universal" tidak berlaku — daftar itu juga memuat `satker`,
`pegawai`, `pejabat`, `ruangan` yang jelas per-satker.

Selebihnya: LBKP/CaLBMN tombstone penghapusan (saldo akhir bisa MINUS + cacah
penghapusan satker lain bocor), Buku Barang `$in` seluruh id aset tiap halaman
(risiko lampaui batas 16 MB BSON) → jurnal kini distempel, token 30-hari
multi-endpoint di dalam CSV/XLSX ekspor → diganti token 7-hari khusus rute
doc-file, RKBMN & realisasi anggaran lintas satker, guard aset di Perencanaan/
Penganggaran/Pemanfaatan, dan cacah "dipakai N pegawai / memegang N aset".

Uji: 745 unit test hijau, `yarn build` sukses. `SKILL.md` ditambah dua bagian
baru: lima titik buta yang lolos dua gelombang, dan kesalahan ARAH SEBALIKNYA
(men-scope yang memang bersama) lengkap dengan urutan bukti yang menentukan.

---

## [#617] Audit REVIEW-9 (9): sapu satker GELOMBANG-2 — 33 kebocoran, termasuk pengambilalihan akun — 2026-07-25

Verifikasi adversarial ulang atas sapuan `[#616]` menemukan bahwa gelombang
sebelumnya **belum menutup semuanya**: 53 temuan terkonfirmasi, ~20 di antaranya
sudah tertutup di `[#616]`, sisanya masih terbuka di `main`. Gelombang ini
menutup sisanya. Tiga di antaranya **berat** (bukan sekadar baca lintas satker):

**1. Pengambilalihan akun lintas satker (`routes/users.py`).** `require_admin`
hanya memeriksa `role`, tidak `kode_satker` — sehingga admin satker A dapat
mereset password admin satker B lalu login sebagai dia (kuasa penuh atas data
B), menghapus/menonaktifkan akun B, atau mengubah role-nya. Ditambah
`PUT /users/{id}/satker` yang bisa dipanggil admin atas DIRINYA SENDIRI dengan
`kode_satker` kosong → naik pangkat jadi **super-admin** (lolos ke
backup/restore/reset seluruh satker). Ditutup dengan helper baru
`auth_utils.pastikan_kelola_akun`, dipasang di semua endpoint /users; ikatan
satker kini hanya boleh digeser super-admin (admin satker tetap dapat mengikat
akun BARU tanpa ikatan ke satkernya sendiri, agar onboarding tetap jalan).

**2. KOP & master satker lain dapat ditimpa (`routes/satker.py`).** `PUT/DELETE
/satker/{kode}` tidak membandingkan `kode` dengan satker admin — admin A dapat
menimpa KOP satker B (dipakai `pengaturan_kop` untuk SELURUH laporan/PDF/stiker
/BAST B) atau menghapus master B. `POST /satker/backfill` (migrasi seluruh DB,
17 koleksi) kini `require_super_admin`.

**3. Dokumen kepemilikan dapat diunduh TANPA login (`routes/exports.py`).**
`GET /assets/{id}/doc-file/...` sepenuhnya anonim — padahal UUID aset justru
ditanam aplikasi ke CSV/XLSX yang beredar. Kini memakai gerbang yang sama
dengan saudaranya di `assets.py` (`require_user_or_query_token` +
`pastikan_akses_aset`), dan tautan di dalam ekspor membawa token ber-scope
media sehingga skenario "buka dari spreadsheet" tetap jalan.

Sisanya, per modul:

- **Laporan keuangan (`reports.py`)** — LBKP & CaLBMN memanggil
  `filter_aset_perhitungan({})` tanpa `scope_query_aset`, jadi saldo/mutasi
  SELURUH satker masuk laporan resmi satu satker; 11 register pendukung CaLBMN
  (persediaan, PSP, pemanfaatan, pemindahtanganan, penghapusan, pemusnahan,
  idle, kasus, koreksi nilai) ikut di-scope. Posisi BMN: nilai persediaan
  lintas satker.
- **Persediaan** — 9 endpoint: peringatan/nota dinas, ekspor jurnal, opname
  kertas kerja & BAOF, laporan posisi & mutasi, daftar & PDF LPB, riwayat per
  barang. Jurnal `transaksi_persediaan` tak ber-`kode_satker`, jadi di-scope
  lewat relasi `persediaan_id` (helper `_scope_jurnal`, pola wasdal). Dokumen
  LPB kini **distempel** `kode_satker` saat dibuat.
- **Buku Barang (`mutasi_bmn.py`)** — daftar jurnal di-scope lewat aset;
  reklasifikasi (ubah kode barang + NUP + jurnal 304/107) kini ber-guard aset.
- **Master Ruangan** — daftar/ubah/hapus tanpa isolasi sama sekali; kini
  distempel + di-scope + di-guard, dan keunikan `kode_ruangan` berlaku **per
  satker** (dua satker boleh sama-sama punya "R-101").
- **Persuratan** — satu deret nomor agenda dipakai bersama (booking satker B
  menghabiskan jatah nomor A, buku agenda A tampak bolong); kini per satker
  dengan seed dari nomor tertinggi milik satker itu, pola sama dengan
  BA-Perbaikan di `[#616]`. Setelan penomoran juga per satker (dulu satu
  dokumen `type="global"` yang bisa ditulis admin satker mana pun — mengubah
  `kode_unit` satu satker mengubah nomor resmi semua satker).
- **Lain-lain** — Arsip Pelaporan, kartu inventarisasi (`kode_satker` dulu
  murni dari klien), rekap akun persediaan, snapshot penganggaran di Pengadaan,
  dan **WebSocket kolaborasi** (`/ws/{activity_id}`: token tak membawa satker,
  siapa pun yang tahu sebuah `activity_id` ikut menerima siaran perubahan aset
  + daftar user online satker lain, dan bisa menyuntik event lock palsu).

Uji: 744 unit test hijau (+6 baru untuk `pastikan_kelola_akun`), `yarn build`
sukses. `SKILL.md` diperbarui dengan pola berulang yang terbukti lolos DUA kali.

---

## [#616] Audit REVIEW-9 (8): sapu FINAL isolasi satker — 20 kebocoran ditutup — 2026-07-25

Sapu verifikasi akhir (workflow adversarial 6 lensa + 22 verifikasi, 20
terkonfirmasi) menemukan kebocoran antar-satker yang lolos gelombang R2–R7.
SEMUA temuan tinggi & sedang ditutup:

**Pengamanan (koleksi checklist tanpa `kode_satker` sama sekali):**
- 🔴 List + ekspor CSV checklist pengamanan kini di-scope satker (dulu
  membaca `{}` global — seluruh checklist semua satker).
- 🔴 `simpan_checklist` kini menstempel `kode_satker` + `pastikan_akses_aset`
  (dulu upsert global by asset_id → timpa checklist satker lain).
- 🟠 `buka_kasus`, `catat_dokumen`, `catat_polis` kini `pastikan_akses_aset`
  (dulu satker A dapat membuka kasus/mencatat atas aset satker B — dan
  cek "satu kasus aktif per aset" yang global memblokir satker B).

**Aset & kegiatan:**
- 🔴 `GET /assets/{id}?exclude_media=true` — jalur ringan (dipakai SETIAP
  buka lightbox/form edit) SEBELUMNYA return tanpa `pastikan_akses_aset`
  → IDOR baca metadata aset satker lain.
- 🔴 Stream dokumen kegiatan (`/inventory-activities/{id}/documents/{idx}`)
  kini ber-guard — dulu PDF BAST/kontrak (ber-PII) bisa di-stream lintas
  satker via id + indeks.
- 🟠 Agregasi kelompok aset + enumerasi "pilih semua halaman" (batch) kini
  di-scope (dulu membaca detail/ID aset seluruh satker).

**Register siklus (jalur tulis lintas satker):**
- 🔴 `buat_proses` (Penggunaan), `buat_usulan` (Penghapusan),
  `buat_usulan_pt` (Pemindahtanganan) kini `pastikan_akses_aset` — dulu
  satker A dapat menyusun usulan/tiket atas aset satker B, lalu transisi
  terminalnya menandai aset B keluar pembukuan.
- 🟠 Pengadaan: `daftarkan_persediaan`, `perbarui_dokumen`, `tautkan_barang`,
  `buat_draft_aset_dari_perolehan` (+ kegiatan tujuan), `tautkan_penganggaran`
  kini `pastikan_akses_dok_satker` — dulu register perolehan satker lain
  dapat dibaca & dimutasi via ID.
- 🟠 Ekspor CSV PSP & tiket BMN idle kini di-scope satker.

**Pengaturan & penomoran alur:**
- 🟠 Portofolio Wasdal: hitungan PSP & BMN idle kini per satker (dulu global
  — angka portofolio pengawasan tercampur satker lain).
- 🟠 **Nomor BA-Perbaikan kini DERET PER SATKER** — dulu counter global
  membuat nomor BA resmi satu satker "bolong" karena satker lain memakai
  urutan yang sama; seed dari sequence tertinggi satker itu (anti-tabrak
  saat migrasi dari counter lama).

Dua item sisa (severity rendah) sengaja dibiarkan: endpoint `doc-file`
checklist adalah URL-kapabilitas PUBLIK by-design (UUID tak tertebak, untuk
tautan tersemat di CSV/XLSX ekspor), dan snapshot kode/nama aset ke usulan
Penganggaran/Perencanaan (picker sudah ter-scope; field identitas rendah).

Checklist pencegahan agar kelas temuan ini tak berulang kini baku di
`.claude/skills/aman-dev/SKILL.md` (5 titik isolasi + aturan indeks/deret/
cache per satker).

## [#615] Audit REVIEW-9 (7/7 — penutup): dokumentasi menyeluruh v2.5 — 2026-07-25

Gelombang penutup audit 6 dimensi — **seluruh dokumentasi dimutakhirkan
SETELAH semua perbaikan selesai** (sesuai urutan mandat):

- 📖 **README v2.5** — highlight seri audit REVIEW-9 (7 gelombang, PR
  #608–#612), fitur opsional Meilisearch & Redis kini terdokumentasi
  (sebelumnya belum pernah masuk README), rangkuman penanganan pemegang
  BMN meninggal dunia (#604–#607).
- 🔢 **Catatan konvensi penomoran CHANGELOG** — entri `[#N]` = nomor PR + 2
  sejak `[#276]`; kini tertulis eksplisit di kepala berkas (dulu hanya
  konvensi lisan antar sesi).
- 📜 **Docstring `routes/bast.py`** — tujuh jenis BAST lengkap (termasuk
  `mutasi_pengguna` & `pengembalian_almarhum`) + dasar hukum dimutakhirkan
  ke PMK Nomor 40 Tahun 2024 (menggantikan PMK 246/2014 jo. 76/2019).
- 🗺️ **MASTERPLAN & EVALUASI-INTEGRASI** — bagian status audit REVIEW-9
  (tabel 7 gelombang + 4 prinsip yang dikunci audit: semua transaksi
  berjurnal, semua mutasi ber-ref_id, register berjurnal tak terhapus,
  isolasi satker menyeluruh).
- 📱 **Halaman Info (PRD)** — versi v2.5 + kartu rilis "Audit 6 Dimensi".
- 🗂️ **Folder memory** (ROADMAP/CHANGELOG internal) — status seri audit.

## [#614] Audit REVIEW-9 (5–6/7): optimasi frontend + keandalan backup/restore/reset — 2026-07-25

Gelombang kelima & keenam audit 6 dimensi dalam satu PR.

**Backup/restore/reset (R6):**

- 🔴 **Retensi tidak lagi menghapus backup MANUAL** — urut leksikografis nama
  penuh salah ("manual" < "otomatis") sehingga semua backup manual — termasuk
  yang baru dibuat — terhapus lebih dulu saat kuota retensi terlampaui. Kini
  urut memakai stempel waktu di nama DAN retensi hanya menyentuh arsip
  otomatis; backup manual hanya bisa dihapus lewat aksi eksplisit di UI.
- 🔴 **Manifest GridFS diparse SEBELUM wipe** — manifest korup dulu meledak
  setelah GridFS dihapus: seluruh foto lenyap padahal restore koleksi
  "berhasil" (galat cuma warning). Kini gagal sebelum ada yang dihapus +
  jumlah berkas gagal dilaporkan di log.
- 🟠 **Deteksi job macet memakai `updated_at`** (denyut progres) — restore
  besar yang masih aktif tidak lagi dibunuh di menit ke-30 (dulu dihitung
  dari `started_at`) lalu lock-nya direbut proses lain di tengah wipe.
- 🟠 **Safety backup ditulis ke DISK per koleksi** — dulu seluruh isi DB
  ditampung di dict memori selama restore (risiko OOM justru di momen paling
  berisiko); rollback kini membaca dari zip disk.
- 🟠 **Reindex Meilisearch otomatis pasca-restore & pasca-reset** — hasil
  pencarian tidak lagi menunjuk data pra-restore/pra-reset (best-effort,
  no-op bila Meili nonaktif).
- 🟡 Registry koleksi: `background_jobs` masuk SKIP (progress job transien);
  `penganggaran_kalender` masuk RESET_KEEP (konfigurasi kalender
  perencanaan). Kebutuhan restore titik-waktu terpenuhi arsip harian
  otomatis + manual yang sudah ada.

**Optimasi frontend (R5):**

- 🟠 **Master Pegawai: `AvatarPegawai` diangkat ke level modul** — definisi di
  dalam komponen halaman membuat TIPE komponen baru setiap render, sehingga
  React me-remount semua avatar (gambar berkedip + fetch ulang) tiap kali
  state halaman berubah (ketik di pencarian, buka dialog, dsb.).
- 🟠 **Master Pegawai: jendela render** — daftar ±1.300+ pegawai dirender
  PENUH dua kali (kartu HP + tabel desktop → ribuan baris DOM). Kini hanya
  150 baris pertama yang masuk DOM + tombol "Tampilkan 300 lagi"; pencarian/
  filter tetap menyaring seluruh data dan mengulang batas.
- 🟠 **Pembukuan: filter jurnal tidak lagi minta ID internal** — dulu filter
  Buku Barang menuntut user menyalin ID aset internal (UUID) secara manual;
  kini ketik nama/kode barang → Enter → pilih dari saran (pola pencarian
  aset tab KIB), jurnal langsung tersaring.

## [#613] Audit REVIEW-9 (4/7): optimasi backend — event loop bebas render berat — 2026-07-25

Gelombang keempat audit 6 dimensi: **tidak ada lagi render dokumen berat yang
memblokir event loop** + tiga optimasi query/caching.

- 🔴 **Laporan Satker (weasyprint) di-offload ke thread + rate-limit 4/menit**
  — render weasyprint bisa berdetik-detik CPU-bound; sebelumnya SATU unduhan
  membekukan seluruh server (semua request lain menunggu). Pola AUTH-D
  endpoint mahal.
- 🟠 **18 generator PDF modul di-offload ke thread** — `doc.build` reportlab
  sinkron di BAST, Buku Barang, Pemeliharaan (DHPB + BA Perbaikan),
  Pemusnahan, Penggunaan (BAST PSP + daftar pemegang), Persediaan (7 laporan),
  TTD, dan Wasdal (3 laporan) kini `asyncio.to_thread` — melengkapi
  OPT-LOOP-2 yang baru mencakup reports.py/exports.py.
- 🟠 **Impor aset Excel/CSV bebas N+1** — dulu tiap baris memanggil
  `find_one` dua kali (file 5.000 baris = 10.000 query beruntun); kini
  aset kegiatan dimuat SEKALI menjadi peta (kode, NUP) → dokumen.
- 🟠 **Dasbor Wasdal ber-cache TTL 90 detik** per (satker, ambang) — dasbor
  memuat SELURUH aset + 6 register per kunjungan; laporan PDF/tahunan tetap
  menghitung segar. Redis bila aktif, TTLCache per-worker bila tidak.
- 🟡 **Indeks `audit_logs (action, timestamp)`** — filter "Log Sistem"/per-aksi
  panel audit tidak lagi COLLSCAN koleksi log terbesar.

## [#612] Audit REVIEW-9 (3/7): jurnal induk lengkap & scope master persediaan — 2026-07-25

Gelombang ketiga audit 6 dimensi: **semua transaksi keluar/nilai kini
berjurnal** di Buku Barang (`mutasi_bmn`) — LBKP/LBP tidak lagi kehilangan
mutasi dari tiga jalur yang sebelumnya bisu — plus isolasi satker master
persediaan.

**Jurnal induk (Buku Barang / G7):**

- 🔴 **Revaluasi Penilaian kini berjurnal** — `tandai_tercatat_sakti` menulis
  204 (Koreksi Nilai bertambah) / 205 (berkurang) saat koreksi FINAL:
  magnitudo positif + `jumlah 0` (rupiah bergeser, kuantitas tidak),
  tanggal buku = tanggal dokumen penilaian.
- 🔴 **Alih status keluar & serah BMN idle kini berjurnal** — transisi
  terminal `dihapus_dibukukan` (proses alih status keluar) dan `diserahkan`
  (BMN idle → Pengelola) menulis 302 Transfer Keluar per aset; sebelumnya
  aset hilang dari master (tombstone) tanpa jejak mutasi KURANG di jurnal.
- 🟠 **Guard jurnal ganda terpusat** — `catat_mutasi_bmn` menolak entri
  duplikat (aset + kode transaksi + `ref_id` dokumen sumber sama): retry
  idempoten & alur revert-lalu-terminal-lagi tidak menggandakan mutasi.
- 🟠 **Dua bug agregator diperbaiki** — `rekap_mutasi_periode` memaksa
  `jumlah 0` menjadi 1 (`or 1`), menggeser kuantitas pada koreksi nilai;
  tabel LBP `susun_mutasi_per_transaksi` hanya menegatifkan kode 3xx/4xx
  sehingga 205 justru MENAMBAH total — kini 205 ikut dinegatifkan + berlabel.

**Master persediaan (isolasi satker):**

- 🟠 **Keunikan kode+NUP & deret NUP kini per satker** — sebelumnya satker B
  tertolak 409 (atau mewarisi deret NUP satker A) karena cek duplikat dan
  auto-increment NUP global; kini sejalan pola keunikan NIP pegawai.
- 🟠 **Impor master tak menimpa satker lain** — update impor by kode+NUP
  kini difilter satker pengimpor (dulu bisa menimpa field master milik
  satker lain yang kebetulan ber-kode+NUP sama).

**Hasil review adversarial 3 lensa (12 agen, semua temuan terverifikasi):**

- 🔴 **Indeks unik persediaan dimigrasi per satker** — indeks global
  `(kode_barang, nup)` dilepas & diganti `(kode_satker, kode_barang, nup)`;
  tanpa ini dup-check per-satker lolos lalu insert meledak
  `DuplicateKeyError` 500 dan satker kedua terblokir permanen.
- 🟠 **"Daftarkan ke Persediaan" (Pengadaan) di-scope satker** — lookup master
  by kode tanpa scope memilih master satker lain → jalur create terlewati →
  transaksi masuk 403 dan baris BAST macet permanen.
- 🟠 **Ekspor master persediaan di-scope satker** — sebelumnya user satker B
  mengunduh seluruh master (stok + nilai) satker lain, dan roundtrip
  ekspor→impor menduplikasinya ke satker B.
- 🟠 **302 hanya untuk aset yang benar-benar terproyeksi** —
  `_proyeksi_terminal_ke_aset` kini mengembalikan daftar id terproyeksi;
  aset yang sudah keluar buku lewat jalur lain (SK penghapusan 301 / tiket
  idle) tidak dijurnal KURANG dua kali.
- 🟠 **Koreksi informasional tak berjurnal & tak memproyeksi** — jenis
  "penilaian tujuan tertentu" (tidak mengubah nilai buku menurut modulnya
  sendiri) kini dilewati oleh jurnal 204/205 DAN proyeksi
  `nilai_wajar_terakhir` (cacat pra-R3).
- 🟠 **Guard hapus register yang sudah berjurnal** — koreksi nilai FINAL
  (tercatat SAKTI) dan tiket proses terminal `dihapus_dibukukan` kini 409
  saat dihapus (pola larangan hapus catatan pemeliharaan ber-jurnal 202) —
  hapus-lalu-buat-ulang tidak lagi menggandakan mutasi.
- 🟠 **Jurnal 202 pemeliharaan pakai `jumlah 0`** — pengembangan nilai
  murni rupiah; `jumlah 1` lama menambah 1 unit fiktif per posting pada
  Tabel 17 CaLBMN.
- 🟡 Label kode 205 ditambahkan ke timeline aset.

## [#611] Audit REVIEW-9 (2/7): sapu IDOR & guard lintas modul — 2026-07-25

Gelombang kedua audit 6 dimensi: menutup **celah isolasi satker** (IDOR) yang
tersisa dan menyeragamkan guard tulis di jalur-jalur yang belum terlindungi.

**Isolasi satker (IDOR):**

- 🔴 **Modul TTD elektronik tanpa isolasi satker** — permintaan TTD kini
  distempel `kode_satker`; daftar permintaan admin di-scope per satker
  (`scope_query_field_satker`); pembatalan/pemilikan (`_pastikan_pemilik_sr`)
  menolak admin satker lain. Sebelumnya admin satker mana pun bisa melihat dan
  MEMBATALKAN permintaan TTD satker lain.
- 🔴 **10 endpoint hapus tanpa scope satker** — DELETE register di Pemanfaatan,
  Pemindahtanganan, Penghapusan, Penggunaan (3 jalur), dan Pengamanan (4 jalur)
  kini difilter `scope_query_field_satker` — admin terikat tak bisa menghapus
  dokumen satker lain via ID.
- 🟠 **Transisi status lintas satker** — 4 endpoint transisi (PSP, BMN idle,
  proses alih status Penggunaan, kasus Pengamanan) kini memanggil
  `pastikan_akses_dok_satker` sebelum mengubah status; melengkapi 6 modul
  transisi lain yang sudah terlindungi.
- 🟠 **Foto pegawai lintas satker** — unggah, stream (foto + foto asli), dan
  hapus foto pegawai kini menegakkan isolasi satker (sebelumnya admin/user
  satker lain bisa mengganti atau menghapus foto via ID pegawai).

**Guard alur bisnis (lanjutan status Meninggal Dunia):**

- 🟠 **Penegakan sisi-server penugasan aset ke almarhum** —
  `enforce_pegawai_terdaftar` kini MENOLAK penetapan pemegang BARU berstatus
  Meninggal Dunia (tanpa opt-in), sambil tetap mengizinkan edit aset yang
  pemegangnya tidak berubah agar proses penyelesaian aset almarhum tak
  terhalang (param `nip_lama` di PUT/PATCH aset).
- 🟠 **PIHAK KESATU BAST almarhum ditolak di semua jenis** — POST /bast
  memeriksa status pemegang lama ke Master Pegawai; pesan mengarahkan ke
  jenis "Pengembalian — Pemegang Wafat" (penyerah ahli waris/atasan).

**Keandalan tulis:**

- 🟠 **POST /bast ber-Idempotency-Key** — klik ganda / retry jaringan tidak lagi
  menggandakan BAST + nomor booking otomatis Persuratan (pola PATCH aset);
  form BAST Penggunaan mengirim kunci per pembukaan form dan menggantinya
  setelah kegagalan validasi.
- 🟡 **OCC PUT /pegawai** — header `If-Match` opsional (409 bila versi berubah);
  `version` distempel sejak buat & di-set eksplisit saat ubah (dokumen era lama
  tanpa `version` melompat ke 2 sehingga pembaca basi tetap tertolak).

**Jejak audit:**

- 🟡 **14 titik mutasi kini ber-`log_audit`** — Wasdal (buka/selesai/hapus
  penertiban, buka/BA/lapor/hapus insidentil), Pemanfaatan (buat/ubah/
  kontribusi/hapus), Pemusnahan (buat BA, usulkan penghapusan, hapus BA) —
  sebelumnya ketiga modul tidak menulis log audit sama sekali.

## [#610] Audit REVIEW-9 (1/7): bug produksi siklus hilir & kebocoran satker pengawasan — 2026-07-25

Gelombang perbaikan pertama dari **audit menyeluruh 6 dimensi** (57 temuan;
integrasi & alur bisnis, optimasi backend/frontend, konsistensi pola, backup,
dokumentasi). Empat bug **siap-produksi** ditutup:

- 🔴 **PDF Berita Acara Pemusnahan selalu gagal 500** — `_esc` dipakai sebelum
  di-import (import lokal menjadikannya variabel lokal → `UnboundLocalError` di
  SETIAP panggilan). Dokumen resmi dasar usulan penghapusan tak pernah bisa
  dicetak; kini import dipindah ke atas pemakaian.
- 🔴 **Usulan penghapusan otomatis dari BA Pemusnahan lahir TANPA `kode_satker`**
  — dianggap "era lama" oleh scope sehingga tampil & bisa ditransisikan satker
  LAIN sampai SK terbit. Kini kode satker tersalin dari BA (fallback satker
  pembuat), + uji unit.
- 🔴 **BAST "Pengembalian — Pemegang Meninggal Dunia" tidak pernah mengosongkan
  pengguna aset** — submit handler memaksa `terapkan_ke_aset=false` karena jenis
  baru belum terdaftar di dua daftar gerbang frontend (backend sudah benar).
  Alur almarhum 4 tahap kini benar-benar tuntas di langkah terakhirnya.
- 🔴 **Mesin temuan Wasdal membaca data TANPA scope satker**: persediaan
  (identitas barang satker lain bocor sebagai temuan), opname terakhir (opname
  SATU satker memadamkan temuan "opname terlambat" SEMUA satker — kepatuhan
  palsu), pemeliharaan, dan 6 kartu lintas modul (kasus/polis/PSP/proses/idle/
  BAST sementara) yang menghitung seluruh DB. Semua kini ter-scope; opname
  dicari per-satker via join id persediaan.

---

## [#609] Pemegang BMN meninggal dunia (4/4): BAST "Pengembalian — Pemegang Meninggal Dunia" — 2026-07-25

Penutup rangkaian [#606]–[#608]. Sebelumnya, saat pemegang wafat petugas
terpaksa **mengakali** form BAST biasa: tak ada tempat menyebut almarhum, tak
ada dasar akta kematian, dan tak ada saksi — padahal pihak yang seharusnya
menyerahkan **berhalangan tetap**.

- **Jenis BAST baru `pengembalian_almarhum`** — *"Pengembalian Barang Milik
  Negara — Pemegang Meninggal Dunia"*. Ikut keluarga arah-balik: PIHAK KEDUA
  **menyerahkan** (ahli waris / atasan langsung), PIHAK KESATU **menerima**
  (pengurus BMN satker), dan bila dicentang, pengguna aset **dikosongkan**
  seperti pengembalian biasa.
- **Pasal DASAR PENGEMBALIAN** otomatis tercetak: nama & NIP almarhum, tanggal
  wafat (format Indonesia), nomor akta kematian, penjelasan bahwa penyerahan
  dilakukan ahli waris/atasan karena pemegang berhalangan tetap — dan penegasan
  bahwa **BAST terdahulu TETAP SAH** sebagai bukti rantai penguasaan serta
  **tidak dibatalkan** oleh berita acara ini.
- **Saksi wajib min. 2** (divalidasi server). Blok **SAKSI-SAKSI** dicetak di
  PDF di bawah tanda tangan para pihak — dirender **berpasangan** agar seluruh
  saksi benar-benar tercetak (`_signature_block` hanya menangani 1–3 dan
  membuang sisanya bila diberi ≥4).
- **Form Penggunaan**: blok kondisional berisi identitas almarhum (prefill dari
  pemegang yang dibuka) + daftar saksi dinamis + penjelas peran, muncul otomatis
  saat jenis dipilih.

> **Rangkaian lengkap selesai.** Kematian pemegang kini punya jalur utuh:
> status ber-akta → transaksi baru ditolak → temuan Wasdal berjam-hukum →
> berita acara pengembalian yang sah. Dokumen historis tak pernah disentuh.

---

## [#608] Pemegang BMN meninggal dunia (3/4): temuan Wasdal khusus + jam 3 tahun terlihat — 2026-07-25

Lanjutan [#607]. Sebelumnya pemegang yang wafat hanya tercakup **tidak langsung**
sebagai `pemegang_berisiko_keluar` — disamakan dengan pensiun/mutasi, tanpa
prioritas dan **tanpa peringatan tenggat hukum**. Kini dipisah:

- **Temuan Wasdal baru** `pemegang_meninggal_belum_serah_terima` — *"Pemegang
  meninggal dunia — BMN belum diserahterimakan"*, objek **Penggunaan** (PMK
  207/2021). Terpisah karena penanganannya berbeda: serah terima harus lewat
  **ahli waris/atasan**, bukan almarhum.
- ⏱️ **Jam 3 tahun tampil di dasbor**: tiap temuan membawa `tingkat`,
  `sisa_hari_lapor`, dan `batas_lapor`, dengan detail berbunyi mis. *"3 aset
  masih dipegang — meninggal 2026-01-01; SEGERA — tersisa 61 hari untuk memberi
  tahu ahli waris; lewat batas, hak tagih negara hapus"*.
- **Pewarnaan eskalasi** di UI: 🔴 **SEGERA** (≤90 hari, merah) · 🟠 **Mendekati
  batas** (≤180 hari, oranye) · kuning (pantau) · ⚠️ **KEDALUWARSA** (lewat) ·
  ✓ **Sudah dilaporkan** (hijau, jam berhenti).
- Tombol **"Tindak lanjuti"** yang sudah ada otomatis berlaku — uraian tiket
  penertiban ikut memuat peringatan tenggatnya.
- Pegawai berstatus non-aktif lain **tetap** memakai temuan lama (tak berubah);
  almarhum **tanpa tanggal wafat** (data lama) tetap terdeteksi, hanya tanpa jam.

---

## [#607] Pemegang BMN meninggal dunia (2/4): tolak transaksi baru kepada almarhum — 2026-07-25

Lanjutan [#606]. Sebelumnya pegawai non-aktif **masih bisa dipilih** sebagai
pemegang aset maupun penerima BAST (picker tanpa filter status, validasi hanya
peringatan lunak) — sehingga **BAST baru bisa dibuat atas nama orang yang sudah
meninggal**. Kini ditutup:

- **BAST — penerima almarhum DITOLAK** (HTTP 400, bukan peringatan). Secara
  hukum mustahil almarhum menerima serah terima. Pesan mengarahkan ke alur
  pengembalian BMN almarhum (penyerah: ahli waris/atasan). Status non-aktif
  lain (pensiun/mutasi) **tetap peringatan lunak** seperti semula — hanya
  kematian yang memblokir.
- **E-sign — penanda tangan almarhum DITOLAK** saat membuat permintaan TTD.
  Mengirim link ke almarhum mustahil dipenuhi dan hanya menggantung dokumen di
  status "menunggu". Satu kueri untuk semua NIP (tak menambah beban per
  penanda tangan). Pesan menyarankan mengganti dengan pejabat berwenang.
- **Picker disaring**: almarhum tak lagi muncul di pemilih pengguna aset
  (Form Aset) maupun datalist penerima BAST (Penggunaan). Aset yang **sudah**
  tercatat atas namanya **TIDAK terhapus** — penyelesaiannya lewat pengembalian
  BMN almarhum, bukan penghapusan diam-diam.

> Prinsip yang dipegang: dokumen historis tak disentuh, dan pengosongan pemegang
> hanya boleh terjadi lewat BAST (ada dokumennya) — bukan otomatis.

---

## [#606] Pemegang BMN meninggal dunia (1/4): status "Meninggal Dunia" + jam 3 tahun ahli waris — 2026-07-25

Menjawab kasus nyata: **BAST sudah sah, lalu pemegangnya meninggal.** Riset
peraturan menegaskan **BAST yang sudah sah TIDAK batal** karena penandatangannya
meninggal — ia akta atas peristiwa yang sudah selesai, dan kematian bukan sebab
hapusnya perikatan (Pasal 1381 KUHPerdata); hak-kewajiban beralih ke ahli waris
(hak *saisine*, Pasal 833 jo. 1318 KUHPerdata). **Yang dikelola adalah penguasaan
barangnya**, lewat serah terima BARU — dokumen lama tetap jadi bukti rantai
penguasaan dan **tidak boleh dihapus**.

Tahap 1 (fondasi data):

- **Status pegawai baru "Meninggal Dunia"** — kelas tersendiri, bukan lagi
  dilebur ke `nonaktif`. Sebelumnya impor menormalkan `meninggal`/`wafat` →
  `nonaktif` sehingga **informasi kematiannya hilang**; kini `meninggal`/`wafat`/
  `almarhum` → status sendiri. Otomatis ikut ke dropdown Referensi & ekspor Excel.
- **Kelengkapan wajib**: `tanggal_meninggal` (**wajib** bila status Meninggal),
  `nomor_akta_kematian`, `penyebab` — mengikuti Peraturan BKN 3/2020 (surat
  keterangan meninggal memuat nomor akta, tanggal, penyebab).
- **Data ahli waris** (nama, hubungan, kontak) — dipakai saat serah terima BMN
  almarhum dan untuk pemberitahuan resmi.
- ⏱️ **Jam hukum 3 tahun** (`info_kewajiban_ahli_waris`, murni & teruji): bila ada
  BMN hilang, tanggung jawab ahli waris **HAPUS** apabila dalam **3 tahun** sejak
  pegawai diketahui meninggal mereka tidak diberi tahu (**UU 1/2004 Pasal 66
  ayat (2)** jo. **PP 38/2016**). Helper menghitung batas (3 tahun **kalender**,
  aman untuk 29 Feb), sisa hari, dan tingkat eskalasi: `pantau` → `segera`
  (≤180 hari) → `kritis` (≤90 hari) → `lewat`. Mengisi **tanggal + nomor surat
  pemberitahuan** menghentikan jam (`selesai`) — karena syarat hukumnya
  *"diberi tahu"*, bukan *"barang kembali"*.
- **Form Master Pegawai**: blok kelengkapan wafat muncul otomatis saat status
  dipilih, lengkap dengan penjelas bahwa BAST lama tetap sah & batas 3 tahun.
- Almarhum yang masih memegang aset **otomatis masuk** panel "Perlu Serah Terima
  BMN" (status meninggal bukan status aman).

> Tahap berikutnya: (2) blokir transaksi baru ke almarhum, (3) temuan Wasdal
> khusus + tampilan jam 3 tahun, (4) jenis BAST "Pengembalian — Pemegang
> Meninggal Dunia" (penyerah ahli waris/atasan + saksi).

---

## [#605] Getar rana kamera diperkuat (Android) + jalur haptic iOS 17.4+ — 2026-07-25

Lanjutan [#603] — pengguna melaporkan **suara muncul tapi getar tidak** saat
memotret. Perbaikan:

- **Android**: pola getar rana diperkuat dari `35 ms` → **denyut GANDA
  `[45, 35, 45]`** ("cha-chunk") — pulsa tunggal pendek kerap tak terasa di
  sebagian motor getar. Getar juga **dipicu lebih awal** (tepat saat foto
  terambil, di dalam gestur ketuk) agar lebih andal & terasa "instan".
- **iOS**: `navigator.vibrate` **diblokir Apple** di Safari. Ditambah jalur
  best-effort via kontrol **`<input type="checkbox" switch>`** (Safari iOS
  17.4+) yang memicu haptic ringan saat di-toggle — satu-satunya cara web di
  iOS. Diam tanpa error pada iOS lebih lama; suara tetap jadi umpan balik utama
  di iPhone.
- Tetap best-effort & bisa dimatikan (`aman_haptics`). Uji unit menambah cakupan
  kedua jalur (Android vibrate + fallback iOS + gerbang preferensi).

> Catatan: bila getar masih tak terasa di Android, cek setelan sistem
> **"Getar saat sentuh / Haptic feedback"** harus aktif — motor getar dikendalikan
> OS, aplikasi hanya memintanya.

---

## [#604] Peta aset: kunci geser marker — aman dilihat, sekali ketuk untuk edit — 2026-07-25

Mencegah **koordinat aset tergeser tak sengaja** saat sekadar melihat peta (di
layar sentuh maupun dengan mouse), tanpa mengorbankan kenyamanan mengedit:

- **Default TERKUNCI**: marker tak dapat digeser saat peta dibuka — menggeser/
  memperbesar peta & mengetuk pin (buka info) tetap normal. Klik pin tetap
  membuka popup.
- **Tombol Kunci/Buka** di toolbar peta (hanya bila pengguna boleh mengedit):
  satu ketuk **membuka** untuk membetulkan koordinat (seret pin → tersimpan
  otomatis), ketuk lagi untuk **mengunci**. Petunjuk di legenda ikut berganti
  sesuai keadaan.
- **Aman by default**: status kunci **tidak disimpan** antar sesi — tiap peta
  dibuka selalu kembali terkunci (cegah "lupa masih terbuka" lalu tergeser).
- Robust terhadap **pengelompokan marker (cluster)**: `options.draggable`
  diperbarui saat dikunci/dibuka sehingga marker yang muncul kembali dari cluster
  mengikuti keadaan kunci terkini.

Catatan: peta **kolaboratif** publik tak terdampak — marker yang sudah ada di
sana memang sudah tak bisa digeser (hanya pin pratinjau saat menambah titik).

---

## [#603] Kamera lapangan: getar & suara rana benar-benar terasa saat memotret — 2026-07-25

Umpan balik saat foto **benar-benar terambil** kini terasa di lapangan (dulu
"seperti tak ada getar maupun suara sama sekali"):

- **Getar rana** diperkuat dari denyut `8 ms` → **`35 ms`**. Pulsa sangat pendek
  (<~20 ms) sering **diabaikan/ tak terasa** di banyak perangkat Android, sehingga
  seolah tak bergetar. (Catatan: iOS Safari tak mendukung Web Vibration API sama
  sekali — di iPhone umpan balik mengandalkan suara.)
- **Suara klik rana** kini benar-benar berbunyi: `AudioContext` dijadikan
  **singleton** dan **`resume()`** dipanggil di dalam gestur ketuk tombol rana.
  Sebelumnya context baru lahir dalam keadaan `suspended` di ponsel dan **tak
  pernah di-resume** → tak ada bunyi. Context tak lagi dibuat-tutup berulang
  (hindari batas jumlah AudioContext saat memotret cepat).
- Keduanya tetap **best-effort** (tak pernah menggagalkan pengambilan foto) dan
  masih bisa dimatikan pengguna (`aman_haptics`, `aman_shutter_sound`).

---

## [#602] Pengawasan sadar TTD: Wasdal & Pengamanan hitung BAST "TTD dibatalkan" — 2026-07-25

**Lanjutan cascade #601** — pembatalan TTD kini benar-benar **berpengaruh ke
metrik kepatuhan**, bukan sekadar penanda. Aset yang BAST-nya ada tetapi
**TTD elektroniknya dibatalkan** kini muncul sebagai kekurangan tersendiri:

- **Pengamanan** (dasbor kesehatan data): kategori baru **"TTD BAST dibatalkan"**
  (`bast_dicabut`) — aset ber-BAST tapi e-sign batal **tidak lagi dihitung
  "lengkap"**. Kategori TERPISAH dari "Tanpa BAST" (dokumen betul-betul tak ada),
  agar makna tak rancu. Ikon perisai-peringatan tersendiri.
- **Wasdal** (pemantauan Penggunaan, PMK 207): temuan baru **"BAST pemegang ada,
  tetapi TTD elektronik dibatalkan"** (`pemegang_bast_dicabut`) — dapat langsung
  **"Tindak lanjuti"** seperti temuan lain.
- **Presisi & tak ganda**: bila memang belum ada dokumen BAST, tetap
  "Tanpa BAST"/`pemegang_tanpa_bast` (bukan dua-duanya).
- **Reversibel penuh**: **mengunggah bukti ttd** (scan sah) kini **mencabut**
  penanda `tt_dicabut` pada BAST & aset terkait — sejajar jalur TTD-ulang.
  Tanpa ini, mengunggah bukti valid justru salah membalik metrik jadi
  "dibatalkan". (Aset presisi: hanya yang BAST-terakhirnya BAST tersebut.)

Rangkaian keterhubungan otomatis (fondasi #1–#6): audit batal → guard dokumen →
penaut `doc_ref` → tombol "Kirim ke TTD" → back-link → cascade → **metrik
pengawasan sadar-pembatalan**. Satu pembatalan kini terlihat konsisten lintas
Penggunaan, Pengawasan, dan Pengamanan.

---

## [#601] Cascade otomatis: batal TTD → BAST & aset ditandai "dicabut" (sinyal lunak) — 2026-07-25

**Puncak keterhubungan otomatis** — menjawab keluhan "mengelola satu per satu".
Kini **membatalkan permintaan TTD** yang menaut BAST terstruktur (`doc_type='bast'`
+ `doc_ref`, dari tombol "Kirim ke TTD") **otomatis merambat**:

- BAST terkait ditandai **`tt_dicabut`** (+ `tt_dicabut_pada`), dan aset yang
  BAST-**terakhir**-nya memang BAST itu ditandai `bast_terakhir.tt_dicabut`.
- **Sinyal lunak, reversibel**: `bast_file_id`/bukti/data **tidak dihapus** —
  hanya diberi tanda, sehingga dapat ditinjau & ditandatangani ulang.
- **Terlihat**: di dialog **Riwayat BAST** (Penggunaan) muncul penanda merah
  **"⚠ TTD elektronik dibatalkan — tanda tangan tidak berlaku"** — hanya bila
  **belum ada bukti ttd terunggah** (bukti fisik/scan tetap sah, tak diperingati).
- **Presisi**: hanya menyasar aset yang BAST-terakhirnya BAST tersebut (tak
  salah tandai aset yang sudah punya BAST lebih baru), dan **hanya permintaan
  yang benar-benar menandatangani** BAST (`signature_request_id` cocok) yang
  boleh mencabut. Pembatalan juga tercatat di Log Sistem beserta info BAST.
- **Aman lintas-satker**: penautan `doc_ref` ke BAST divalidasi kepemilikan
  saat dibuat (satker pemohon), dan cascade ber-scope satker — tak bisa
  menyentuh dokumen satker lain. Pembatalan tetap dicatat walau cascade gagal.

Rangkaian lengkap (fondasi #1–#5): audit batal → guard dokumen batal → penaut
`doc_ref` → tombol "Kirim ke TTD" (penaut terstruktur) → back-link → **cascade**.
Langkah lanjutan (opsional): metrik/temuan Wasdal & Pengamanan turut
memperhitungkan `tt_dicabut`.

---

## [#600] Back-link TTD→BAST: `signature_request_id` tertulis ke BAST saat e-sign selesai — 2026-07-25

Fondasi **#5** — melengkapi **FK dua-arah** TTD↔BAST. Saat **semua** pihak
selesai menandatangani sebuah permintaan yang menaut BAST terstruktur
(`doc_type='bast'` + `doc_ref` = id BAST, dari tombol "Kirim ke TTD"), sistem
menulis **`signature_request_id`** (+ `tt_esign_selesai_pada`) ke record
`bast_serah_terima` yang bersangkutan.

- Idempoten (`$set` nilai sama aman diulang; aman terhadap penyelesaian paralel).
- Backend murni, tanpa perubahan perilaku lain.
- Ini tumpuan **cascade pembatalan** (langkah berikutnya): begitu tautan dua-arah
  ada, membatalkan TTD dapat menandai BAST/aset "dicabut" secara otomatis
  (sinyal lunak) sehingga badge Penggunaan/Wasdal/Pengamanan menyesuaikan.

---

## [#599] "Kirim ke TTD" dari BAST — penaut terstruktur BAST↔e-sign — 2026-07-25

Fondasi **#4** keterhubungan otomatis: menautkan dunia **BAST** ke dunia
**e-sign** secara **terstruktur**. Di dialog **Riwayat BAST** (modul Penggunaan)
tiap BAST kini punya tombol **"Kirim ke TTD"** yang:

- Membuat permintaan tanda tangan elektronik dengan **`doc_ref = id BAST`**
  (penaut terstruktur, bukan teks bebas) dan **penanda tangan otomatis** dari
  Pihak Pertama & Kedua BAST.
- Menampilkan **tautan e-sign per penanda tangan** untuk dibagikan (Salin /
  WhatsApp) — alternatif satu-klik dari mengunggah scan bukti basah.
- Endpoint `POST /bast/{id}/kirim-ttd` ber-scope satker (`require_writer`).

Inilah penaut terstruktur yang membuat langkah berikutnya andal: back-link
`signature_request_id` ke BAST saat e-sign **selesai**, lalu **cascade** sinyal
lunak saat TTD **dibatalkan** (badge BAST/Penggunaan/Wasdal/Pengamanan ikut
menyesuaikan, data tetap reversibel).

---

## [#598] TTD elektronik: referensi dokumen sumber (mengaktifkan penaut `doc_ref`) — 2026-07-25

Fondasi **#3** keterhubungan TTD ↔ modul. Saat membuat permintaan TTD kini bisa
diisi **"Referensi dokumen sumber"** (mis. No. BAST / No. Surat / Kode+NUP aset).
Field `doc_ref` sebenarnya sudah dirancang di model tetapi **mati** — jalur JSON
tak pernah diisi dari form, dan jalur unggah dokumen meng-hardcode kosong.
Sekarang:

- Form buat permintaan TTD punya isian **Referensi dokumen sumber** (opsional);
  dikirim baik pada jalur JSON maupun **unggah dokumen** (`doc_ref` sebagai Form
  field, tak lagi di-hardcode `""`).
- Referensi ditampilkan di **detail permintaan** untuk penelusuran.
- Menyalakan kail forward yang menjadi dasar langkah berikutnya (back-link
  `signature_request_id` ke artefak saat TTD selesai, lalu propagasi
  pembatalan) — sinyal lunak, bertahap.

---

## [#597] TTD dibatalkan: dokumen & halaman verifikasi tak lagi tampak sah — 2026-07-25

Menutup celah keandalan (fondasi #2): setelah permintaan TTD **dibatalkan**,
dokumen ber-tanda-tangan dan halaman verifikasi QR sebelumnya **masih bisa
diunduh & tampak sah**. Kini:

- **Berkas ditolak (410)** untuk permintaan berstatus batal pada: dokumen
  ber-TTD (`/dokumen-ttd`), Lembar Pengesahan (`/lembar-pdf`), dan gambar
  tanda tangan (`/gambar/{signer}`) — lewat penjaga bersama `_tolak_bila_batal`.
  Dokumen **asli** (tanpa bubuhan TTD) tetap dapat dilihat.
- **Halaman verifikasi publik** (dibuka dari QR) kini menegaskan status:
  spanduk merah **"DOKUMEN DIBATALKAN — tanda tangan tidak berlaku"** + catatan
  yang sesuai, alih-alih menampilkannya seolah sah.

Bagian dari rangkaian menyatukan TTD/BAST lintas modul (sinyal lunak, bertahap).

---

## [#596] TTD elektronik: pembatalan kini terekam di Log Sistem (fondasi keterhubungan lintas modul) — 2026-07-25

Langkah **fondasi** menuju keterhubungan otomatis TTD ↔ modul lain. Sebelumnya
**pembatalan permintaan TTD** (`DELETE /ttd/permintaan/{id}`) tidak meninggalkan
jejak apa pun — padahal aksi lain (buat permintaan, tandatangani, terbitkan ulang
link) sudah ter-audit. Kini pembatalan menulis entri **Log Sistem** `batal_ttd`
(siapa, kapan, judul dokumen, status sebelumnya), sehingga dapat ditelusuri dan
menjadi dasar propagasi berikutnya.

- Perubahan **observability murni** — tidak menyentuh record modul konsumen
  (BAST/aset/surat) sama sekali; nol risiko.
- Bagian dari rencana bertahap "sinyal lunak" untuk menyatukan TTD/BAST lintas
  modul (Persuratan, Penggunaan, Wasdal, Pengamanan) — langkah berikutnya:
  guard dokumen ber-TTD yang dibatalkan, penaut `doc_ref`, lalu back-link FK.

---

## [#595] Master Pegawai lebih cerdas: NIP/NIK otomatis mengisi Tgl Lahir & Jenis Kelamin — 2026-07-25

Begitu **NIP/NIK diketik**, sistem membaca makna kodenya dan **langsung mengisi**
field yang masih kosong di form pegawai — mengurangi input manual & salah ketik.
Berbasis riset struktur resmi (Perka BKN 22/2007; Dukcapil/Permendagri):

- **NIP PNS / NI PPPK (18 digit)** → **Tgl Lahir** (digit 1–8 `YYYYMMDD`),
  **Jenis Kelamin** (digit 15: `1`=L, `2`=P), dan **TMT CPNS** (digit 9–14
  `YYYYMM`, khusus PNS) ditampilkan sebagai info.
- **NIK (16 digit)** → **Tgl Lahir** (digit 7–12 `DDMMYY`; **perempuan tanggal
  +40** → sekaligus menentukan jenis kelamin) + **kode wilayah** (digit 1–6)
  sebagai info. Tahun 2-digit ditebak via pivot tahun berjalan.
- **NRP POLRI/TNI**: tidak mengisi otomatis (POLRI hanya thn/bln lahir; TNI
  formatnya tidak seragam) — sesuai kaidah, tak menebak data yang tak pasti.
- **Non-destruktif**: hanya mengisi field yang **kosong**; tersedia tombol
  **"Isi ulang dari NIP/NIK"** untuk menimpa manual bila perlu. Ada catatan
  "terisi otomatis" agar jelas apa yang diisi.
- **Perbaikan**: tampilan bulan **TMT CPNS** pada hint deteksi sebelumnya salah
  (menampilkan 2 digit tahun, kini bulan yang benar). Logika satu sumber
  (`urai_identitas`) dengan label laporan — ada unit test.

---

## [#594] Desain marker kedua: sampul foto di dalam marker (toggle Pin↔Foto) — Peta Aset & Peta Kolaborasi — 2026-07-25

Menambah **desain marker kedua** tanpa menghapus yang lama. Marker **pin**
(desain 1) **tetap** jadi bawaan; pengguna kini bisa mengaktifkan **marker foto**
(desain 2) lewat sebuah tombol — marker menampilkan **sampul foto aset**
(mengikuti `thumbnail_index` sampul terpilih) langsung di peta, sehingga terlihat
apa barangnya tanpa membuka popup. **Klik marker tetap membuka popup info yang
sama.** Tersedia di **kedua peta**: Peta Aset internal (`AssetMapFullView`) dan
**Peta Kolaborasi** publik (`PetaKolaborasiPage`).

- **Toggle "Gaya Marker: Pin ↔ Foto"** — di menu peta (internal) & tombol toolbar
  (kolaborasi, ber-`data-testid`). Pilihan **disimpan** (`localStorage`) agar
  bertahan antar sesi. Default **Pin** (desain lama tak berubah bila tak diaktifkan).
- **Marker foto** = `divIcon` 46×54 dengan sampul sebagai `background-image`
  (`background-size:cover`); border/cincin ikut **status & seleksi** seperti pin.
  Sumber sampul: internal → streaming 256px **WebP** (offline → thumbnail snapshot
  `row.thumbnail`); kolaborasi → endpoint foto peta ber-`?token=` (thumbnail).
- **Aset tanpa foto tetap pin** — hanya aset ber-foto yang menjadi marker foto.
- **Skala aman**: sampul dimuat sebagai `<img loading="lazy" decoding="async">`
  (bukan `background-image`) → browser **menunda fetch** untuk marker di luar
  viewport (teruji di real-Leaflet: marker jauh tak menembak request sampai
  digeser masuk), sehingga jumlah request & memori sampul terbatas **meski
  clustering dimatikan**. Dipadu clustering + `removeOutsideVisibleBounds`
  (default) dan sinkron marker **inkremental** (tak bangun-ulang; view/cluster/
  spiderfy & seleksi terjaga). `iconKey` menyertakan `thumbnail_index`+`version`
  → sampul menyegar saat foto berubah.
- **Degradasi anggun**: bila sampul gagal muat (mis. token kedaluwarsa di peta
  kolaborasi), `img` disembunyikan sehingga **warna latar status** tampil — tanpa
  ikon "gambar rusak", tanpa crash, dan **klik marker tetap** membuka popup.

---

## [#593] WebP menyeluruh: preview galeri/lightbox + gambar laporan kini WebP (dari asli optimasi Tinify) — 2026-07-25

Menutup celah terakhir konversi WebP. Foto ASLI sudah dioptimalkan Tinify dan
thumbnail sudah WebP, TAPI yang **ditampilkan** — preview galeri (`?w=256`),
lightbox (`?w=1280`), dan gambar yang di-embed ke **laporan PDF** — sebelumnya
masih di-re-encode ke **JPEG** saat disajikan. Kini semuanya **WebP**:

- **Preview foto (galeri & lightbox)**: `_resize_webp` menggantikan `_resize_jpeg`
  — hasil resize disajikan & di-cache sebagai WebP (~25-35% lebih ringan di
  jaringan lapangan). Kualitas mewarisi sumber (foto asli = hasil optimasi
  Tinify). Kunci cache diberi penanda `webp` → entri JPEG lama otomatis
  kedaluwarsa via TTL, preview baru langsung WebP; `Content-Type` disajikan
  sesuai isi (deteksi magic-byte) sehingga aman untuk entri lama maupun baru.
- **Gambar di laporan PDF**: `_downscale_to_data_uri` (laporan eksekutif/data)
  meng-embed WebP (WeasyPrint 68 merender WebP via Pillow — terverifikasi) →
  PDF berfoto lebih kecil.
- **Aman**: bila encode/resize gagal atau hasil tak lebih kecil, foto **asli**
  tetap disajikan (tak pernah kosong). Konsumsi kuota Tinify NOL untuk jalur ini
  (semua lokal, mewarisi kualitas dari foto asli yang sudah dioptimalkan Tinify).

---

## [#592] Perbaikan lightbox: foto tak lagi "tersangkut" aset lama saat pindah antar-aset — 2026-07-25

Di penampil foto (lightbox), geser kartu info untuk pindah ke aset berikutnya/
sebelumnya kadang tetap menampilkan **foto aset lama**. Akar masalah: penjaga
pembangunan-ulang URL foto (`builtRef`) hanya membandingkan `count` & `version`
— dua aset berbeda yang kebetulan sama-sama 1 foto versi 1 (sangat umum) lolos
tanpa membangun ulang URL, sehingga `<img>` tetap menunjuk foto aset sebelumnya.
Kini penjaga **juga membandingkan `id` aset** → begitu id berubah, URL foto
(dan thumbnail placeholder) dibangun ulang, `idx` di-reset ke 0, dan indikator
"memuat" menyala. Foto yang tampil selalu milik aset yang sedang dibuka.

---

## [#591] Thumbnail aset → WebP (baru langsung WebP + migrasi lama terjadwal, tanpa kuota Tinify) — 2026-07-25

Optimasi penyimpanan & payload thumbnail pada skala jutaan aset. Thumbnail
(`thumbnail`/`gallery_thumbnail`/`photo_thumbnails`) tersimpan base64 di dalam
dokumen aset — pada data raksasa ini memberatkan daftar, snapshot offline, dan
penyimpanan. WebP ~25-35% lebih kecil dari JPEG pada kualitas setara.

- **Thumbnail BARU langsung WebP**: `create_thumbnail`/`create_gallery_thumbnail`
  (dipakai semua jalur tulis aset: create/update/patch/rotate/batch/checklist)
  kini menghasilkan `data:image/webp`. Didukung penuh browser modern & PIL
  (laporan/ekspor mendekode via PIL, tak terpengaruh).
- **Penyajian byte deteksi tipe**: endpoint thumbnail (`/assets/{id}/photos/{i}?thumb=1`
  dan peta kolaboratif publik) kini menetapkan `Content-Type` dari magic-byte
  (`_tebak_media_type`) — WebP tersaji benar walau header `nosniff`.
- **Migrasi thumbnail LAMA terjadwal & aman**: fase baru di `webp_converter.py`
  me-re-encode thumbnail JPEG lama → WebP secara **lokal (PIL), TANPA Tinify**
  (jadi **tak menyentuh kuota Tinify** — kuota hanya untuk foto asli GridFS).
  Sapuan sekali-jalan berbasis kursor `id` (indeks, hemat), **idle & 1-worker
  lease** (tak ganggu performa), **OCC** (aman dari race edit user), dan hanya
  disimpan **bila hasil WebP lebih kecil** (tak pernah memperburuk). `updated_at`
  tak diubah → tak memicu re-sync offline massal. Kill-switch `WEBP_KONVERSI_AKTIF=0`.
- Uji unit `test_webp_thumbnail.py` (generasi + re-encode). Foto ASLI (GridFS)
  tetap dikonversi via Tinify seperti sebelumnya; kedua fase kini berjalan
  berdampingan (fase thumbnail tetap jalan walau kuota Tinify habis).

---

## [#590] Keandalan foto di laporan: cegah OOM/crash pada kegiatan raksasa + WeasyPrint tak blok — 2026-07-25

Mitigasi risiko foto saat data membengkak (ratusan ribu–jutaan aset), tanpa
mengubah tampilan laporan:

- **Cegah OOM pada Laporan Data Aset (PDF).** `executive-data-pdf` dulu meng-
  *embed* foto (baca GridFS + downscale per aset) untuk **SELURUH** aset ke
  memori **sebelum** dipotong ke 499/halaman — pada kegiatan berisi ratusan
  ribu aset ini bisa menghabiskan memori & lambat/crash. Kini embed foto HANYA
  untuk aset di **halaman yang diminta** (`row_slice`); statistik ringkasan tetap
  dihitung dari seluruh aset (murni baca field, tanpa foto). Total untuk paginasi
  diambil dari `asset_count`.
- **WeasyPrint tak lagi memblok event loop.** Semua render `write_pdf()` laporan
  eksekutif/data dipindah ke thread (`asyncio.to_thread`) — permintaan lain tak
  ikut membeku selama PDF dirender (senada offload reportlab sebelumnya).
- **Foto rusak/None tak lagi 500.** Di `GET /assets/{id}/photos/{index}`, elemen
  foto legacy yang `None`/non-str kini di-guard (`isinstance`) → jatuh ke 404
  bersih alih-alih `AttributeError`. Konsisten dengan endpoint checklist.

Ekspor XLSX/PDF berfoto sudah punya batas anti-OOM (`MAX_FOTO_EXPORT_ASSETS`)
sejak sebelumnya; perbaikan ini menutup jalur laporan eksekutif yang belum
terbatas.

---

## [#589] Perbaikan HP: link panjang di dialog Bagikan Peta dipotong "…" (tak melebihi kanvas) — 2026-07-25

Di dialog **Bagikan Peta Kolaboratif**, kotak "Link aktif" menaruh `truncate`
pada **wadah flex** — di sana `text-overflow: ellipsis` tak pernah muncul, dan
`<span>` teksnya tak punya `min-w-0` sehingga sebagai anak flex ia tak mengecil
(terpotong keras tanpa "…", berpotensi mendorong lebar melewati kanvas). Kini
`min-w-0 flex-1 truncate` dipindah ke **span teks** sehingga elipsis benar-benar
tampil dan link sepanjang apa pun tak pernah melampaui kanvas. Ditambah `title`
agar URL penuh tetap terbaca saat hover. Tak ada perubahan perilaku salin/bagikan.

---

## [#588] Cache bersama lintas-worker + rate-limiter via Redis (opsional, ber-feature-flag) — 2026-07-24

Menambah **Redis** sebagai lapisan cache **lintas-worker** opsional. VPS
menjalankan 2 worker uvicorn; cache ringkasan (stats/opsi-filter/analitik/
kategori) selama ini `TTLCache` **per-worker**, sehingga setelah tulis aset
`invalidate_asset_cache()` hanya mengosongkan cache worker yang menangani —
worker lain menyajikan angka **basi** sampai TTL habis (60–300 dtk). Redis
menjadikan cache **satu sumber bersama** + invalidasi seketika lintas worker,
dan memindahkan storage rate-limiter dari MongoDB ke Redis (lebih cepat).

- **Feature flag**: aktif HANYA bila `REDIS_URL` di-set di `backend/.env`.
  Kosong → cache per-worker + rate-limit MongoDB (perilaku lama, tak berubah).
  Redis mati/menolak → operasi cache di-swallow (miss → hitung ulang), limiter
  jatuh ke in-memory; aplikasi tetap jalan. Pipeline deploy tak diubah
  (`backend/.env` awet lintas rilis). Rollback = hapus `REDIS_URL` + restart.
- **Invalidasi tanpa scan**: penghitung **generasi** per namespace
  (`INCR aman:gen:<ns>`) — O(1), atomik, seketika di kedua worker; kunci
  generasi lama kedaluwarsa via TTL. Kunci cache tetap menyertakan
  **kode_satker** → **isolasi satker terjaga** (sama seperti cache in-memory).
- **Rate-limiter**: prioritas storage Redis → MongoDB → in-memory (semua
  ber-fallback in-memory saat store bermasalah); di pytest tetap in-memory.
- **Health**: `/api/health/deep` melaporkan `checks.redis` bila diaktifkan
  (Redis tak sehat = info degradasi, TIDAK menjatuhkan gerbang deploy).
- **Pemasangan sekali jalan di VPS**: `scripts/setup_redis.sh` (apt install +
  bind localhost + password + sisip env + restart), panduan `docs/REDIS.md`.
  Redis bind ke `127.0.0.1` + `requirepass`; `REDIS_URL` hanya sisi server.
- Modul baru `redis_utils.py` (klien async ber-feature-flag) + helper
  `cache_get`/`cache_set` di `shared_utils`; dependensi `redis==5.2.1`; uji
  unit `test_redis_utils.py`.

---

## [#587] Pencarian cepat via Meilisearch (opsional, ber-feature-flag) — aset, surat, persediaan — 2026-07-24

Menambah **Meilisearch** sebagai mesin pencari eksternal opsional untuk
mempercepat pencarian teks bebas pada **Aset**, **Persuratan**, dan
**Persediaan**. Regex infix Mongo tak bisa memakai index (COLLSCAN dalam
lingkup satker) dan makin lambat saat data membengkak; Mongo self-hosted kita
tak punya Atlas Search, jadi mesin pencari eksternal adalah padanan
"trigram/n-gram" yang tepat (toleran salah ketik + prefiks, milidetik).

- **Feature flag**: aktif HANYA bila `MEILI_URL` & `MEILI_MASTER_KEY` di-set di
  `backend/.env`. Bila kosong / Meili mati / menolak → pencarian **otomatis
  jatuh-balik** ke regex Mongo lama. Tidak ada yang rusak. Pipeline deploy
  TIDAK diubah (deploy mengawetkan `backend/.env`).
- **Arsitektur aman**: Meili me-resolve kata kunci → daftar **id kandidat**
  ter-scope, lalu id itu diumpankan ke kueri Mongo yang sudah ada
  (`{"id": {"$in": [...]}}`). **Semua** filter/urutan/paginasi/**isolasi
  satker tetap ditegakkan Mongo** (otoritatif) — Meili hanya akselerator
  pencocokan teks; hasilnya tak bisa membocorkan data lintas-satker. Field
  harga/PII sensitif tidak diindeks.
- **Sinkronisasi**: hook best-effort non-blocking pada CRUD (buat/ubah/hapus)
  ketiga koleksi — kegagalan sinkron tak menggagalkan permintaan.
- **Reindex massal**: `POST /api/search/reindex` (super-admin) atau CLI
  `python -m scripts.reindex_search`; status via `GET /api/search/status`
  (admin). Jalankan setelah aktivasi pertama / impor massal / restore backup.
- **Pemasangan sekali jalan di VPS**: `scripts/setup_meilisearch.sh` (unduh
  binari + systemd + master key + sisip env + reindex), unit systemd
  `scripts/meilisearch.service`, panduan lengkap `docs/MEILISEARCH.md`. Meili
  bind ke `127.0.0.1` (tak terpapar publik); master key hanya sisi server.
- Modul baru `meili_utils.py` (klien httpx ber-feature-flag) +
  `routes/search_admin.py`; uji unit logika murni `test_meili_utils.py`.

---

## [#586] Optimasi search: abaikan kata kunci < 2 huruf (cegah COLLSCAN 1-huruf) — 2026-07-24

Langkah cepat mempercepat pencarian aset **tanpa mengubah cakupan 16-field**.
Pencarian teks bebas memakai regex 16-field yang tak bisa memakai index (scan
dalam lingkup satker); kata kunci **1 huruf** (mis. "a") selektivitasnya sangat
rendah → memindai hampir seluruh aset percuma. Kini kata kunci **< 2 huruf
diabaikan** (daftar tampil apa adanya):

- Backend: `build_asset_search_query` (daftar + ekspor geo) dan `/assets/stats`
  hanya membangun `$or` bila `len(kata_kunci.strip()) ≥ 2` (`_search_len_ok`).
  Saat kata kunci cukup panjang, **16-field `$or` berjalan persis seperti
  sebelumnya** — tidak ada perubahan hasil.
- Frontend: kata kunci "efektif" dijepit di `useAssetFilters` — < 2 huruf tak
  memicu request sama sekali (hemat beban). Yang **diketik** pengguna tetap
  terlihat; hanya pemicu pencarian yang dijepit. Konsisten online & offline.

---

## [#585] Perbaikan: thumbnail foto tak muncul di peta kolaboratif (jumlah_foto selalu 0) — 2026-07-24

Bugfix lanjutan #583: thumbnail foto aset **tidak pernah tampil** karena
`_titik_aset` memproyeksikan field `photo_count` yang **tidak tersimpan** di
dokumen aset (di daftar aset ia DIHITUNG, bukan disimpan) → `jumlah_foto` selalu
0 → bagian foto tak pernah dirender. Kini `jumlah_foto` **dihitung di server**
lewat agregasi (`$size` `photo_gridfs_ids`, fallback `photos`) — sama seperti
daftar aset — tanpa menarik byte foto. Thumbnail kini muncul di panel detail
aset dan klik → foto asli layar penuh berfungsi.

---

## [#584] Perbaikan HP: dialog Bagikan Peta muat di layar + samakan ukuran tombol Bagikan di peta — 2026-07-24

- **Dialog "Bagikan Peta Kolaboratif" muat di HP** — sebelumnya melebihi kanvas
  di layar kecil. Kini padding lebih ringkas di HP (`p-4`), tinggi dibatasi
  (`max-h-90vh`) dengan gulir vertikal + `overflow-x-hidden`, dan baris aksi tiap
  link ditata ulang (jumlah kontribusi pindah baris) agar tombol
  WhatsApp/Bagikan/Perpanjang/Ganti/Batal membungkus rapi tanpa meluber.
- **Tombol Bagikan di peta aset seukuran tombol lain** — sebelumnya lebih kecil
  (kena `min-h-0`) dari tombol Tutup/lainnya di ≤1023px. Kini tombol ikon persegi
  `h-9 w-9` yang seragam dengan tombol Tutup, dan melebar berlabel "Bagikan" di
  desktop (≥lg).

---

## [#583] Peta Kolaboratif: tombol ikon ringkas + foto aset (thumbnail → foto asli layar penuh) — 2026-07-24

Penajaman tampilan & foto berdasarkan umpan balik:

- **Tombol jadi ikon-saja agar ringkas** — Cluster, Moderasi, dan Muat Ulang
  kini tombol ikon persegi; tombol **Tambah Titik** menjadi **FAB bundar** (+).
  Semua tetap ber-`aria-label`/`title` untuk aksesibilitas.
- **Foto aset tampil di peta** — panel detail aset menampilkan **thumbnail foto**
  (bila ada). Backend menyajikannya lewat endpoint peta ber-token
  (`/peta/kolaborasi/{id}/aset/{aset}/foto/{i}`) dengan **gerbang akses yang sama**
  (token peta valid / operator satker; ter-scope ke kegiatan share).
- **Klik thumbnail → foto ASLI layar penuh** — pembuka foto minimalis: **hanya
  menampilkan foto asli** di latar hitam (ketuk untuk tutup), dengan navigasi
  panah + penghitung bila aset punya beberapa foto. Tanpa metadata/kontrol lain,
  sesuai permintaan "benar-benar foto aslinya saja".

Catatan: foto aset kini ikut terlihat oleh pemegang link peta (selagi aktif) —
perluasan yang disengaja atas permintaan; tetap dibatasi akses share & satker.

---

## [#582] Peta Kolaboratif: paritas fitur dengan Peta Aset (pratinjau titik, info lengkap, filter/kelompok/cluster, moderasi) — 2026-07-24

Menindaklanjuti umpan balik: **halaman peta kolaboratif kini setara Peta Aset**
internal, bukan peta polos.

- **Marker pratinjau saat menambah titik** — mengetuk peta menaruh **marker
  hijau berdenyut** tepat di lokasi ("Titik akan ditaruh di sini — seret untuk
  menggeser"); bisa **diseret** untuk menepatkan sebelum disimpan.
- **Info titik selengkap Peta Aset** — panel detail menampilkan **pill status +
  kondisi** berwarna dan baris berlabel **Kategori / Merk-Tipe / Lokasi**
  (backend menambah field deskriptif aman ini — **tanpa** harga/foto/data pribadi).
- **Pin berwarna per status** (sama dengan Peta Aset) + **lencana angka** pada
  titik yang punya komentar.
- **Filter status**, **Barang Serupa** (kelompok kode+nama), dan
  **pengelompokan marker (cluster)** — semuanya hadir & bisa di-toggle.
- **Kontrol peta**: bar skala + skala nominal/zoom, kompas utara, dan
  **"lokasi saya"** (GPS). **Legenda dipindah ke footer** sehingga **tak lagi
  menutup tombol zoom** di dalam peta.
- **Moderasi untuk operator/admin satker** — mode seleksi untuk **menghapus**
  titik/komentar tak pantas (per item atau massal). Hanya muncul bila
  `boleh_moderasi`; penghapusan tetap ditegakkan server (`require_writer` + satker).
- **Tampilan & warna dirapikan** memakai token tema — **mendukung mode gelap**
  dan konsisten dengan aplikasi.

---

## [#581] Peta Kolaboratif: bagikan peta kegiatan via link ber-masa-tayang (komentar & titik gotong-royong) — 2026-07-24

Fitur baru **Peta Kolaboratif**. Operator/admin kini bisa **membagikan peta satu
kegiatan** lewat **link publik ber-token** dengan **masa tayang**. Selama aktif,
**siapa pun yang punya link** (tanpa perlu akun) dapat:

- **melihat titik aset** kegiatan pada peta,
- **berkomentar di tiap titik** (aset maupun titik gotong-royong),
- **menambah titik baru + komentar** sendiri (kolaboratif; tamu cukup isi nama).

Pengelolaan oleh operator/admin satker kegiatan:

- **Tombol Bagikan** (ikon share) di peta layar-penuh → dialog **Bagikan Peta
  Kolaboratif**: pilih **masa tayang** (1/3/7/30 hari), judul, dan izin apakah
  tamu boleh menambah titik / berkomentar. Salin link, bagikan via **WhatsApp**
  atau **Bagikan…** bawaan perangkat.
- **Perpanjang** masa tayang kapan saja (link lama tetap berlaku — tak
  diterbitkan ulang), atau **Batalkan** link (mati untuk publik).
- **Moderasi**: hapus (soft) titik/komentar yang tidak pantas.

**Keamanan & isolasi:**

- Masa tayang **nyata di basis data** (`berlaku_sampai`); token diberi plafon
  longgar sehingga *perpanjang* cukup mengubah field DB tanpa mematikan link
  yang sudah tersebar. **Pembatalan** & **penerbitan ulang** (`jti`) langsung
  mematikan link lama.
- Token peta **typ tersendiri** (`typ="peta"`) — tidak bisa tertukar dengan
  token e-sign/media.
- **Cegah IDOR**: pengguna login lintas-satker **tanpa link** tak bisa membuka
  share via UUID — hanya **pemegang link** ATAU **operator/admin satker
  kegiatan** yang boleh.
- **Setelah kedaluwarsa**, link hanya bisa dibuka oleh **operator/admin satker
  + kegiatan** terkait (untuk mengarsipkan & memperpanjang) — pemegang link
  biasa ditolak, sesuai permintaan.
- **Terbitkan ulang** (rotasi `jti` + token baru) sebagai **kill-switch** bila
  link bocor: tautan lama langsung mati, kontribusi tetap tersimpan. Juga jalur
  resmi menghidupkan kembali link yang **dibatalkan** (pembatalan bersifat
  permanen; *perpanjang* tak bisa menghidupkannya diam-diam).
- Penegakan **kedaluwarsa tz-aware** (bukan perbandingan string) — offset zona
  waktu tak lagi menyesatkan. Masa tayang dijepit agar token yang sudah tersebar
  tak kedaluwarsa lebih dulu.
- **Plafon kontribusi per peta** + **rate-limit baca**; toggle izin publik
  berlaku untuk **semua** pengunjung berlink (tamu maupun user satker lain),
  hanya operator/admin satker yang lolos.
- Data yang dibagikan ke publik **minimal & aman** (kode/NUP/nama/kategori/status
  + koordinat) — **tanpa harga, foto, atau field sensitif**. IP tamu direkam
  untuk moderasi tetapi **tak pernah** dikirim ke klien.
- Endpoint kontribusi ber-**rate-limit** (titik 30/mnt, komentar 40/mnt).

Backend: `routes/peta_kolaborasi.py` (+ token peta di `auth_utils.py`, indeks di
`indexes.py`). Frontend: halaman publik `PetaKolaborasiPage.jsx` (Leaflet ringan,
di luar auth), dialog `BagikanPetaDialog.jsx`, tombol share di `AssetMapFullView`.

---

## [#580] UI HP: hapus chip filter cepat (Belum/Ditemukan/Semua) di mode inventarisasi — 2026-07-24

Di **HP**, mode inventarisasi menampilkan chip filter cepat **Belum /
Ditemukan / Semua** pada kartu progres. Chip ini **dihapus khusus di HP**
karena filter status sudah tersedia di **Filter Lanjutan** (kategori/status
aset). Menghapusnya membuang satu baris → **menambah wilayah untuk baris data
aset**.

Tablet/desktop (≥ sm) tidak berubah — chip filter tetap ada di baris ramping.

---

## [#579] Perbaikan: Ubah Massal gagal senyap bila seleksi langsung dikosongkan — 2026-07-24

Saat **Ubah Massal** ditekan **Terapkan** lalu pengguna **cepat menekan
"Kosongkan"** (mengosongkan area seleksi aset), penyimpanan bisa **gagal senyap**
— data batal tersimpan tanpa pesan galat.

Penyebab: handler simpan membaca ulang state `selectedAssets` yang keburu kosong
(guard `selectedAssets.size === 0` → `return` diam-diam), dan/atau closure yang
usang selama dialog konfirmasi / render ulang saat panel di-*unmount*.

Perbaikan: **snapshot ID aset terpilih diambil sinkron** tepat saat tombol
Terapkan diklik (`BatchEditPanel.handleApply`), lalu diteruskan ke
`handleBatchUpdate` (DashboardPage). Simpan massal kini memakai snapshot itu —
**kebal** terhadap seleksi yang dikosongkan setelahnya. Walau area seleksi
langsung dikosongkan, data tetap tersimpan.

---

## [#578] UI HP: badge garansi menyatu NUP, status ikon-saja, saklar mode di toolbar, persen di bawah bar — 2026-07-24

Penyempurnaan tata letak **khusus tampilan HP** (mobile, < sm) agar lebih padat
& hemat ruang untuk baris data.

- **Badge garansi menyatu dengan NUP** — di kartu aset HP, NUP + Garansi kini
  tampil sebagai **satu pil menyatu** di samping kode aset: dua bagian dipisah
  **pembatas** (garis border) dan diberi **warna kotak berbeda** (garansi hijau
  bila aman / kuning bila segera berakhir). Badge garansi dilepas dari baris
  bawah.
- **Status inventarisasi = ikon saja** — cukup ikon (✓ ditemukan, ✗ tidak
  ditemukan, ⊕ berlebih, ⚖ sengketa, ○ belum) berwarna; makna tetap terbaca
  lewat tooltip & `aria-label`. Menghemat lebar baris.
- **Saklar mode Dashboard | Inventarisasi pindah ke toolbar** — di HP kini
  disisipkan **di antara tombol Scan & Peta** (ikon-saja), konsisten di kedua
  mode; dicabut dari kartu StatsBar mobile & header InventoryProgressBar agar
  tak dobel.
- **Persen pindah ke bawah bar** — pada mode inventarisasi HP, persentase kini
  tepat **di bawah bar progres** dan **bersebelahan** dengan perbandingan
  X/Y diinventarisasi — satu baris (saklar mode) hilang, ruang untuk baris data
  bertambah.

Tampilan tablet/desktop (≥ sm) tidak berubah. Diverifikasi tinjauan adversarial
multi-lensa (tap-target 44px, mode gelap, breakpoint, regresi) — bersih.

---

## [#577] Pemantauan kuota email Resend — indikator harian & bulanan (dinamis) — 2026-07-23

Semua email keluar aplikasi (OTP registrasi, OTP lupa password, link tanda
tangan elektronik) menempuh Resend. Kini penggunaannya **terpantau**.

- **Pencatatan di choke point** — setiap email yang berhasil melewati Resend
  dihitung di dalam `send_otp_email`/`send_esign_email` (satu titik), dipecah
  per **jenis** (OTP registrasi / OTP lupa password / e-sign) dan per **status**,
  diakumulasi **per hari & per bulan** memakai kalender **UTC** agar selaras
  dengan reset kuota harian Resend.
- **Indikator** di **Pengaturan › Sistem › Pemantauan Email**: bilah kemajuan
  Hari ini & Bulan ini (terpakai / batas / sisa, warna hijau→kuning→merah pada
  ambang 80% & 100%), rincian per jenis, dan alamat pengirim.
- **Batas dinamis** — default **100/hari** & **3000/bulan** (plan gratis
  Resend), tetapi **dapat diubah super-admin** (endpoint `PUT /api/email/limit`)
  bila Resend mengubah ketentuan di kemudian hari — tanpa perlu deploy ulang.
- **Deteksi otomatis** — bila Resend SENDIRI menolak kirim karena kuota
  tercapai (harian/bulanan), aplikasi merekamnya (`kuota_tercapai`) dan
  menampilkan peringatan merah pada indikator + pesan OTP yang jelas ke
  pengguna. Sinyal ini otomatis hilang di periode berikutnya.

Teknis: koleksi `email_usage` (indeks unik `lingkup+periode`, upsert `$inc`
atomik), route `routes/email_monitor.py` (`GET /api/email/usage` untuk admin,
`PUT /api/email/limit` untuk super-admin), helper klasifikasi galat
`_deteksi_kuota_email` (membedakan kuota kirim dari rate-limit throughput).
Uji unit menjaga klasifikasi & bentuk ringkasan indikator.

---

## [#576] Pembubuhan TTD: QR verifikasi kini bisa diatur letak & ukurannya — 2026-07-23

Pada halaman e-sign, langkah **atur pembubuhan** sebelumnya hanya membiarkan
penanda tangan memindah & mengubah ukuran **tanda tangan**; **QR verifikasi**
selalu terpaku otomatis di pojok kanan-bawah halaman terakhir.

Kini QR pun bisa diatur:
- Centang **"Atur juga posisi & ukuran QR verifikasi"** → muncul kotak QR
  hijau yang bisa **digeser** (di halaman mana pun) dan **diubah ukurannya**
  (geret pegangan / penggeser Ukuran QR), persis seperti kotak tanda tangan.
- **Batas minimal ukuran QR** ditegakkan agar tetap dapat dipindai: slider
  minimal 10% lebar halaman, dan server memaksa sisi QR **≥ 20 mm** (±2 cm)
  saat render — mencegah QR terlalu kecil hingga gagal di-scan.
- Tanpa mencentang, perilaku lama tetap: QR otomatis pojok kanan-bawah
  halaman terakhir.

Implementasi: dokumen-level `posisi_qr` pada `signature_requests` (dikirim
lewat endpoint `kirim`, divalidasi `_posisi_qr_bersih` + `QR_MIN_MM`),
dirender di `dokumen_ber_ttd` (halaman & koordinat/ukuran pilihan, normalisasi
rotasi ikut). Frontend: kotak QR kedua di `AturPosisiTtd`. Uji unit menjaga
jepitan min/maks & penolakan nilai liar (Infinity/NaN).

---

## [#575] BAST: lampiran sertakan foto serah terima (bukan hanya foto barang) — 2026-07-23

Pada Buat BAST, centang *"Sertakan lampiran foto…"* sebelumnya hanya
menyematkan **foto barang** (sampul tiap aset) — bukti **serah terima** tak
pernah ikut tercetak walau sudah diunggah.

Kini lampiran dibagi dua bagian dengan judul jelas:
- **A. Foto Barang** — sampul tiap aset (seperti sebelumnya).
- **B. Foto Serah Terima** — diambil dari **scan bukti TTD BAST** (field
  `bukti`). Bila buktinya **gambar** (JPG/PNG), disematkan penuh; bila **PDF**,
  diberi catatan bahwa buktinya berkas terpisah (PDF tak dapat disematkan
  sebagai gambar).

Label centang di form diperbarui agar jelas mencakup kedua jenis foto. Berlaku
di semua jenis BAST (`backend/routes/bast.py` unduh PDF).

---

## [#574] Pejabat: picker Master Pegawai + pembeda satker (super-admin) — 2026-07-23

Halaman **Referensi Pejabat Penatausahaan** kini terhubung ke Master Pegawai
dan memperjelas satker tiap pejabat.

- **PJB-1 — picker Master Pegawai:** di dialog Tambah/Ubah Pejabat ada kotak
  *"Ambil dari Master Pegawai"* — ketik/pilih nama pegawai lalu identitas
  terisi otomatis (nama, NIP, gelar depan/belakang, jabatan, pangkat/golongan,
  status kepegawaian, unit kerja, no. HP, email, Plt/Plh). Tak perlu ketik
  manual; semua field tetap bisa disunting setelahnya.
- **PJB-2 — pembeda satker:** tiap satker memang punya pejabat berbeda
  (backend sudah meng-scope daftar & resolusi penanda tangan per-satker via
  `_q_pejabat_satker`), tetapi di UI belum ada pembedanya. Kini **super-admin**
  (admin tanpa `kode_satker`) melihat **badge satker** pada tiap baris pejabat,
  bisa **mencari** per satker, dan **memilih satker** saat menambah/mengubah
  pejabat (memilih pegawai dari satker tertentu ikut menyetel satkernya). Admin
  ber-satker tetap dipaksa ke satkernya sendiri oleh server (isolasi M-SCOPE),
  sehingga tak perlu memilih.

Semua laporan resmi (DBKP/LBKP/BAST dll.) sudah memakai penanda tangan KPB
ter-scope satker user — jadi pembeda ini konsisten hingga ke dokumen.

---

## [#573] BAST: kolom Alamat/Unit auto-isi dari Master Pegawai — 2026-07-23

Pada Buat BAST, memilih pegawai (dari saran Master Pegawai atau Tap Kartu
e-KTP) sebelumnya hanya mengisi otomatis NIP + Jabatan; kolom **Alamat/Unit**
selalu manual. Kini ikut terisi dari Master Pegawai: `alamat` → jika kosong,
fallback ke `unit_kerja` → `unit_organisasi`. Berlaku di ketiga jalur auto-isi
(saran nama PIHAK KESATU & KEDUA + Tap Kartu), dan mengalir ke PDF BAST (baris
"Alamat" pada blok identitas kedua pihak). Tetap bisa disunting manual.

---

## [#572] TTD: goresan tinta kini terlihat di mode gelap (kanvas "kertas" terang) — 2026-07-23

Di halaman tanda tangan elektronik, kanvas TTD manual transparan dengan tinta
gelap (`#0f172a`) di atas latar kartu yang **gelap** saat mode gelap → goresan
**nyaris tak terlihat** saat menandatangani. Diperbaiki di `SignatureCapture.jsx`
(dipakai halaman TTD publik & simpan spesimen pejabat): kanvas kini punya latar
**"kertas" terang tetap** (di mode gelap MAUPUN terang) sehingga tinta gelap
selalu kontras & terlihat.

Penting: warna tinta TIDAK diubah jadi putih — kanvas tetap transparan dan PNG
tersimpan (`getTrimmedCanvas`) tetap transparan + tinta gelap, sehingga benar
saat disematkan ke PDF berlatar putih (laporan/BAST). Latar terang murni lapisan
tampilan.

---

## [#571] Konversi WebP Fase 2: foto pegawai (perluas registry sumber) — 2026-07-23

Melanjutkan konverter WebP latar (#570) ke **foto pegawai** — sesuai urutan
"prioritaskan foto asli dulu": foto asli aset tetap didahulukan, lalu foto
pegawai. `webp_converter.py` di-generalisasi jadi **registry sumber** (`SUMBER`):

1. `aset` — `assets.photo_gridfs_ids` (Fase 1, tak berubah; kini query juga
   mengecualikan blob ber-`metadata.jenis` agar tak menyerempet foto lain).
2. `pegawai` — `pegawai.foto_file_id` (foto tampil).
3. `pegawai_asli` — `pegawai.foto_asli_file_id` (sumber krop).

Foto pegawai membawa **back-reference `metadata.pegawai_id`** → resolusi pemilik
langsung (tanpa scan). Swap referensi optimistis id-match (foto tak diganti user
di tengah jalan). Blob WebP baru **mempertahankan** `metadata.jenis` +
`pegawai_id` sehingga endpoint serve pegawai — yang **sudah content-type-aware**
— menyajikan WebP dengan benar tanpa perubahan. Semua gerbang keamanan Fase 1
(verifikasi berlapis sebelum hapus lama, satu-worker lease, idle-aware, stop
kuota ≤50) berlaku sama.

Menyusul: lampiran modul gambar (BAST/PSP/dll.), thumbnail inline (terakhir),
dan TTD (PNG legal — ditangani terpisah/hati-hati). Test: +2 (registry &
pelestarian metadata pemilik) — total 667 hijau.

---

## [#570] Konversi foto → WebP latar belakang (adaptif-idle, aman, via Tinify) — 2026-07-23

Sistem konversi foto ASLI aset (`assets.photo_gridfs_ids`, JPEG di GridFS) ke
**WebP** secara bertahap & otomatis, dirancang agar **tak mengganggu performa
aplikasi** dan **tak pernah kehilangan foto**.

**Modul baru:**
- `backend/activity_tracker.py` — pelacak aktivitas request **lintas-worker**
  (middleware ASGI tipis; tulis "aktivitas terakhir" ke Mongo di-throttle ≤1/5
  dtk/worker). `aplikasi_idle()` dipakai konverter untuk tahu kapan aplikasi
  benar-benar sepi.
- `backend/webp_converter.py` — worker latar:
  - **Idle-aware**: hanya bekerja bila tak ada request nyata ≥90 dtk; begitu
    ada aktivitas → berhenti.
  - **Satu worker**: lease atomik MongoDB (`app_runtime.webp_lease`) agar 2–4
    worker uvicorn tak dobel-proses / dobel-bakar kuota.
  - **Hemat kuota**: berhenti bila SISA kuota Tinify ≤ **50** (dari 500/bulan);
    lanjut sendiri saat kuota reset / ada foto baru.
  - **Aman (verifikasi berlapis SEBELUM hapus lama)**: (1) sumber JPEG valid,
    (2) hasil WebP terdekode + **dimensi sama persis** + non-kosong, (3) blob
    baru **terbaca ulang**. Baru **swap referensi ber-OCC (bump version)** —
    menutup race dengan edit foto user konkuren — lalu hapus blob lama. Bila
    verifikasi gagal di titik mana pun → batalkan, foto lama utuh.
  - **Bertahap & terjadwal**: satu foto per siklus, berjeda (~8 dtk); berhenti
    saat semua selesai; hanya konversi foto yang MASIH direferensikan aset
    (hindari bakar kuota untuk blob yatim).

**Perubahan pendukung:**
- Serve foto penuh (`GET /assets/{id}/photos/{idx}`) kini **content-type-aware**
  (magic-byte → `image/webp`/`image/jpeg`/…) agar WebP tersaji benar. Thumbnail
  & preview tetap JPEG (Fase 2).
- Indeks `fs.files` `metadata.content_type` (pemilihan kandidat efisien).
- Konversi via Tinify Convert API (`.convert(type="image/webp")`).

**Konfigurasi (env, opsional):** `WEBP_KONVERSI_AKTIF=0` (kill-switch),
`WEBP_IDLE_DETIK`, `WEBP_JEDA_FOTO`, `WEBP_KUOTA_SISA_MIN`.

Fase 1 = foto asli (prioritas). Thumbnail inline & lampiran modul menyusul.
Test: +8 unit (gerbang keamanan `verifikasi_webp`, deteksi content-type,
filter idle) — total 665 hijau.

---

## [#569] UI mode gelap: ikon pemilih tanggal (date picker) kini terlihat — 2026-07-23

Di mode gelap, ikon "buka pemilih tanggal" pada semua `<input type="date">`
(dan datetime-local/month/week/time) berwarna gelap bawaan browser → **tak
terlihat** di latar gelap. Diperbaiki satu aturan global di `index.css`:
`.dark input[type="date"]… { color-scheme: dark }`. Ini menyuruh browser
merender seluruh kontrol tanggal native bertema gelap — ikon jadi **terang**
(terlihat), dan popup kalender beserta kolom hari/bulan/tahunnya ikut bertema
gelap sesuai tema aplikasi. Berlaku otomatis di seluruh halaman (21 berkas
memakai input tanggal native) tanpa menyentuh satu per satu.

---

## [#568] Keandalan CI/CD: deploy digerbang pada CI sukses (workflow_run) — 2026-07-23

Sebelumnya `deploy.yml` ter-trigger `on: push: [main]` — **independen** dari CI.
Akibatnya commit yang **gagal** CI tetap auto-deploy ke produksi (umpan balik
bocor: gerbang uji tak menjaga rilis). Diperbaiki:

- Trigger diganti ke `workflow_run` atas workflow **"CI"** (`types: [completed]`,
  `branches: [main]`) + `if: github.event.workflow_run.conclusion == 'success'`.
  Alur baru: **merge → push memicu CI → CI hijau memicu deploy**. CI merah →
  deploy di-skip → produksi tak menerima commit gagal-CI.
- `workflow_dispatch` (deploy manual) dipertahankan, selalu boleh jalan.
- Checkout dipin ke `workflow_run.head_sha` → skrip deploy yang dipipe ke VPS
  adalah tepat commit yang lulus CI.

Tanpa perubahan gerbang deploy lain yang sudah ada (validasi kunci SSH, 5×
retry jangkau VPS, health-check `/api/health/deep` pasca-restart tetap berlaku).

---

## [#567] Performa: analitik satu-lintasan ($facet) + baca foto detail paralel — 2026-07-23

Dua micro-opt jalur-baca `assets.py` (keluaran identik):

- **`get_assets_analytics`** — sebelumnya 5 aggregation terpisah (kategori,
  kondisi, status, lokasi, eselon), masing-masing `$match` + memindai **ulang**
  set yang sama (walau sudah paralel). Digabung jadi **satu** pipeline `$facet`:
  `$match` memilih set via indeks `activity_id` **sekali**, lalu 5 grouping
  berjalan atas set itu. `$limit` tiap cabang menyamai batas `to_list(...)` lama.
  Ter-cache 2 menit → hemat 4 pemindaian ekstra pada tiap cache-miss (dataset besar).
- **`get_asset`** (mode media penuh) — hidrasi foto dari GridFS dulu berurutan
  (`await` dalam loop = N round-trip serial); kini `asyncio.gather` membaca semua
  blob **paralel** (urutan tetap terjaga). Detail aset multi-foto lebih responsif.

Tanpa perubahan kontrak/keluaran API. 657 test unit hijau.

---

## [#566] Performa: offload pembuatan PDF/XLSX (reportlab + PIL) ke thread — 2026-07-23

Lanjutan penghentian blok event loop (#562). Pembuatan laporan PDF & ekspor
XLSX menjalankan kerja CPU-berat **sinkron di event loop** — satu unduhan
laporan/ekspor besar (ratusan/ribuan aset) membekukan SELURUH worker beberapa
detik (2 worker uvicorn → separuh kapasitas stall):

- **`reports.py`** — 18 pemanggilan `doc.build(...)` reportlab (BA, SPTJM, DBHI,
  RHI, DBKP, DBR, KIR, penyusutan, LBKP, LKB, CaLBMN, BAHI, SP, sampul, daftar
  pemegang, dll.) dibungkus `await asyncio.to_thread(doc.build, ...)`.
- **`exports.py`** — 2 `doc.build` (`export_pdf`) + 3 `_xlsx_image_buffer` PIL
  (`bangun_xlsx_bytes`: thumbnail foto/stiker/kelengkapan) di-offload. Catatan:
  jalur ekspor XLSX "async" (`export_xlsx_async`) TETAP menjalankan perakitan di
  event loop yang sama sebelum ini — kini PIL-nya benar-benar lepas dari loop.

Semua titik terverifikasi berada di dalam `async def`; `doc.build`/PIL bersifat
deterministik dengan `elements`/`img_data` sudah dirakit sebelum build, jadi
offload aman & transparan (tanpa perubahan keluaran). `import asyncio`
ditambahkan di `reports.py`. 657 test unit hijau.

---

## [#565] Performa frontend: lottie build "light" + kanvas TTD dimuat lazy — 2026-07-23

Dua kemenangan bundle dari audit performa frontend (aplikasi sudah
teroptimasi baik: 29 rute lazy, panel berat lazy, daftar tervirtualisasi,
ekspor server-side — jadi ini penajaman incremental):

- **`ModuleHomePage`** — `import lottie from "lottie-web"` (build penuh ~305 KB
  raw) diganti `lottie-web/build/player/lottie_light` (SVG-only ~168 KB). Kita
  hanya memakai `renderer: "svg"`, jadi identik secara fungsi. Hemat ~137 KB raw
  (~40 kB gzip) pada chunk **landing pasca-login** yang dimuat semua pengguna.
- **`PejabatPage`** — `SignatureCapture` (react-signature-canvas + signature_pad)
  dijadikan `React.lazy` + `Suspense`; komponen ini hanya di-mount saat panel
  bubuh TTD dibuka (`ttdUntuk`), jadi kanvas TTD tak lagi membebani chunk awal
  halaman Pejabat.

`AssetForm` sengaja **belum** di-lazy-kan: ia selalu ter-mount untuk editor
(manfaat utama hanya untuk viewer) dan merupakan form inti alur offline-first —
ditunda agar bisa diuji langsung di aplikasi. Verifikasi: `yarn lint` bersih +
`yarn build` sukses.

---

## [#564] Performa: ekspor CSV buang byte base64 document_checklist di server — 2026-07-23

`GET /export/csv` sebelumnya menarik `document_checklist` **penuh** dari
MongoDB — termasuk foto base64 (item `photos`) dan byte PDF inline
(`documents.data`) yang bisa **multi-MB per baris** — padahal formatter CSV
hanya menulis nama/checked/notes item, **jumlah** foto, dan **nama** dokumen
(bukan isinya). Untuk aset ber-BAST/PDF inline × ribuan baris, ini mentransfer
data besar sia-sia dari DB ke aplikasi.

Perbaikan: ganti `find(query, projection)` dengan `aggregate([$match, $project])`
yang memproyeksikan `document_checklist` via `$map` → hanya membawa
nama/checked/notes + **panjang** array foto (isi dibuang) + **nama** dokumen
(byte `data` dibuang). Byte base64 tak pernah meninggalkan MongoDB.

- Tanpa perubahan keluaran CSV — dibuktikan test `test_csv_projection_setara_penuh`
  (formatter menghasilkan keluaran IDENTIK untuk data penuh vs ter-proyeksi,
  dan hasil proyeksi tak memuat base64/byte apa pun).
- Kolom skalar tetap dari registry (`asset_fields.py`) → field baru otomatis ikut.
- 657 test unit hijau (+1).

---

## [#563] Performa: indeks kunci-sort/filter daftar aset + GridFS job_id yang hilang — 2026-07-23

Audit performa menemukan beberapa opsi sort/filter `GET /assets` tanpa indeks
pendukung → sort **global** (tanpa `activity_id`) memaksa Mongo mengurut di
memori (berisiko gagal pada dataset besar karena batas sort agregasi), dan
filter jadi partial scan. Ditambahkan di `create_indexes()`:

- `[(purchase_price, 1), (id, 1)]` — sort harga (satu-satunya sort yang **tak
  punya indeks apa pun** → paling berisiko).
- `[(condition, 1), (id, 1)]` dan `[(eselon1, 1), (id, 1)]` — sort kondisi/eselon.
- `[(activity_id, 1), (inventory_status, 1)]` dan
  `[(activity_id, 1), (stiker_status, 1)]` — filter status lazim per-kegiatan
  (RHI/DBHI, cetak stiker).
- `fs.files` `metadata.job_id` (sparse) — pembersih artifact-ekspor yatim
  (`jobs.py`) memindai `fs.files` tiap jam; tanpa indeks = COLLSCAN penuh yang
  memburuk seiring bertambahnya foto.

Deklaratif & idempoten (dibuat sekali, no-op pada boot berikutnya). Tanpa
perubahan perilaku. Tiebreak `id` pada indeks sort selaras dengan `sort_options`
yang memang memakai `id` sebagai pemecah seri.

---

## [#562] Performa: hentikan blok event loop — offload PIL sinkron di jalur foto aset ke thread — 2026-07-23

Audit performa menemukan jalur tulis/baca foto aset yang menjalankan PIL
(thumbnail/putar) **sinkron di event loop**, sehingga satu request berat
memblokir SEMUA request lain di worker itu (VPS jalan 2 worker uvicorn → efek
terasa). `create_asset`/`update_asset`/`process_photos_for_storage` sudah
`asyncio.to_thread`, tapi beberapa handler tertinggal — kini diseragamkan:

- **`patch_asset`** (jalur TERPANAS: edit foto lapangan/HP — `photo_ops`
  add/keep, ganti cover, checklist): 7 titik `create_thumbnail`/
  `create_gallery_thumbnail`/`generate_photo_thumbnail` → `asyncio.to_thread`.
- **`rotate_asset_photo`** (putar foto): `rotate_jpeg_bytes` + regen thumbnail
  cover/per-foto → thread.
- **`get_asset_media`** & **`get_asset_checklist_full`** (fallback thumbnail
  aset legacy) + **`migrate_photos_to_gridfs`** (migrasi admin massal): tiap
  comprehension thumbnail dibungkus satu `to_thread` (satu lompatan thread per
  batch).

Tidak ada perubahan perilaku/kontrak API — murni memindahkan kerja CPU-bound
PIL keluar dari event loop (PIL melepas GIL saat encode/decode). Throughput di
bawah beban tulis foto + putar meningkat; latensi request lain tak lagi
tersandera oleh satu edit foto besar. 656 test unit tetap hijau.

---

## [#561] Perkakas uji: harness load/stress Locust + workflow CI/CD + skill aman-testdata — 2026-07-23

Melengkapi fondasi generator sintetis (#560) menjadi rangkaian uji end-to-end
untuk otomatisasi & skalabilitas pengujian beban/stres:

- **Harness Locust** (`scripts/loadtest/locustfile.py`) — mensimulasikan
  pengguna satker realistis dengan bobot **baca ≫ tulis ≫ mahal**
  (login → telusuri daftar/statistik/analitik/snapshot → sesekali `POST /assets`
  → opsional laporan mahal). Body aset uji dibaca dari NDJSON hasil generator
  sintetis (`AMAN_DATASET_FILE`); uji-tulis aktif hanya bila `AMAN_ACTIVITY_ID`
  diset; pakai `Idempotency-Key` per permintaan. Dilengkapi
  `scripts/loadtest/README.md` termasuk **metode menentukan batas rate-limit
  dari titik jenuh** (naikkan pengguna sampai p95 melonjak / failure > 1%, bagi
  throughput jenuh dengan pengguna aktif per satker).
- **Workflow CI/CD** (`.github/workflows/loadtest.yml`, manual
  `workflow_dispatch` — tak jalan tiap PR) — **menghasilkan dataset sintetis
  tepat sebelum uji** lalu menjalankan Locust (efisiensi: dataset tak disimpan
  di repo, feedback cepat). Tanpa `host` → dry-run (generate + validasi
  locustfile) sehingga selalu bisa dijalankan tanpa staging/secrets. Langkah
  generate tak memasang seluruh `requirements.txt` karena generator hanya butuh
  pustaka standar + `asset_fields` (import `shared_utils` opsional dengan
  fallback) → runner cepat.
- **Skill `aman-testdata`** (`.claude/skills/aman-testdata/SKILL.md`) —
  mengikat semuanya jadi panduan end-to-end (data sintetis → uji beban →
  wiring CI/CD), termasuk alur menambah strategi generator saat field aset
  baru ditambahkan ke registry.

Tak menyentuh runtime aplikasi. Melengkapi lima kebutuhan yang diminta: data
realistis, otomatisasi & skalabilitas (load/stress), data dinamis & adaptif
(anti-drift registry), pendeteksian anomali (edge-case), dan efisiensi CI/CD.

---

## [#560] Perkakas uji: generator data sintetis BMN registry-driven (adaptif + edge-case) — 2026-07-23

Fondasi perkakas pengembangan/pengujian untuk mempercepat & memperkuat siklus
uji ke depan (bukan bagian runtime aplikasi — di `backend/scripts/synthdata/`,
tak di-import server/route mana pun). Menjawab lima kebutuhan sekaligus:

- **Realistis** — data BMN berkonteks OIKN/IKN: nama barang per kategori, merek,
  lokasi Kawasan IKN (Sepaku/PPU, Kalimantan Timur), kodefikasi 6-segmen, NIP
  18-digit, satker 6/20-digit, kegiatan inventarisasi. Tanpa dependency baru
  (pustaka standar Python saja — ringan untuk CI, tak menyentuh
  `requirements.txt`).
- **Adaptif (anti-drift)** — sumber field = `asset_fields.ASSET_SCALAR_FIELDS`
  (registry yang sama dengan model/ekspor/impor). Pilihan sah (kondisi/status/
  inventarisasi/stiker/klasifikasi) diambil dari `shared_utils.VALID_*`. Test
  `test_synthdata_generator.py` menagih tiap field registry punya strateginya:
  menambah field aset TANPA menambah strateginya menggagalkan CI → data uji
  selalu relevan dengan fitur terkini.
- **Anomali / edge-case** — profil `edge`/`mixed` menyuntik kasus tepi yang
  sering terlewat: tanggal ekstrem (`9999-12-31` jebakan OverflowError, tanggal
  mustahil), harga/koordinat di luar rentang, unicode/emoji/RTL, string sangat
  panjang, serta pola mirip SQLi/NoSQL/XSS/path-traversal (disimpan sebagai teks
  polos) — memperluas cakupan & menguji ketahanan logika.
- **Deterministik & skalabel** — `seed` sama → keluaran identik (repro CI);
  100.000 record < 15 detik; format `json`/`ndjson` (stream hemat memori).
  CLI: `python -m scripts.synthdata --count 500 --profile mixed --seed 42`.
- **Valid skema** — tiap record (semua profil) lolos model `AssetCreate`.

Jenis data lain juga tersedia: `pegawai`, `satker`, `kegiatan`. Harness
load/stress (Locust) + wiring CI/CD + skill `aman-testdata` menyusul di PR
terpisah. Test: +14 (total unit 656 hijau).

---

## [#559] Keamanan: rate-limit per-USER + storage bersama lintas-worker (MongoDB, aman) — 2026-07-23

Rate limiter sebelumnya per-IP + in-memory per-worker (VPS jalankan 2 uvicorn
worker) → batas efektif ~2× & tak konsisten, dan tak adil untuk satker yang
berbagi satu IP publik (NAT kantor: satu pengguna bisa menghabiskan kuota
rekan sekantor). Perbaikan:

- **Kunci per-USER** (dari JWT, Bearer atau `?token=`; decode tanpa lookup DB,
  exp diabaikan karena hanya dipakai sbg kunci). Endpoint publik tanpa token
  (login/OTP/registrasi) tetap per-IP. Tiap pengguna kini punya jatah sendiri.
- **Storage bersama lintas-worker** via MongoDB pada DATABASE + KOLEKSI
  TERDEDIKASI (`aman_ratelimit`/`rl_counters`/`rl_windows`) — terisolasi penuh
  dari data aplikasi (mustahil bentrok dgn koleksi `counters` app; tak ikut
  backup). **Aman saat Mongo bermasalah** (diuji): `serverSelectionTimeoutMS`
  pendek + `swallow_errors` + `in_memory_fallback` → saat Mongo tak terjangkau,
  SATU permintaan lambat lalu SEMUA jatuh ke in-memory (~3µs), aplikasi jalan
  terus & tetap membatasi; pulih otomatis. Di uji (pytest) → `memory://` biasa.

**Uji performa & angka (karakteristik AMAN — inventaris BMN, 2 worker, trafik
satker moderat, simpan lapangan bursty via antrean optimistis):**
- Overhead limiter itu sendiri **~3µs/op** (343k ops/dtk) in-memory; ~0,5ms
  dgn Mongo lokal → BUKAN penentu throughput. Storage dipilih demi konsistensi,
  bukan kecepatan.
- **Sengaja TANPA plafon global** (tanpa `SlowAPIMiddleware`) — jalur panas
  (baca/simpan aset, heartbeat, snapshot delta) TIDAK bergantung Mongo
  per-permintaan; ini menjaga ketahanan OFFLINE-FIRST. "Pembagian tiap user" =
  jatah per-kategori endpoint berat: auth/OTP **3–10/mnt**, laporan pembukuan
  **6/mnt**, ekspor **3–10/mnt**, impor/SIMAN **3–6/mnt**, TTD **15–60/mnt**,
  master pegawai **10–30/mnt**. Baca/simpan aset biasa tak diplafon (kerja
  lapangan bursty; kebenaran dijaga OCC + idempotency-key + antrean offline).

Verifikasi: `pytest tests/unit` **642 lulus** (+1 uji `_rate_limit_key`
per-user↔per-IP); `compileall` bersih; uji fail-open Mongo-down terbukti tak
menggantung.

## [#558] Peta: keep-alive antar-mode — posisi & data dipertahankan, tak refresh dari awal — 2026-07-23

Sebelumnya komponen peta di-**unmount** setiap kali pindah ke mode list/galeri
atau saat membuka Edit Massal — Leaflet dibuang (`map.remove()`), lalu saat
dibuka lagi peta **memuat ulang dari awal** dan kembali ke fit-bounds default,
kehilangan posisi (center/zoom) & hasil geser pengguna.

Kini peta **keep-alive**: sekali dibuka, tetap ter-mount dan hanya
**disembunyikan** (`display:none`) saat berpindah mode; instance Leaflet, posisi,
zoom, dan data **dipertahankan** — bolak-balik list ⇄ peta atau seleksi Edit
Massal ⇄ peta terasa mulus tanpa muat ulang. Data terbaru tetap diambil **hanya**
saat menekan **"Muat Ulang"** di peta. Saat ditampilkan kembali, `invalidateSize`
dipanggil agar tile tak abu-abu/terpotong.

Catatan: peta baru di-mount saat **pertama** dibuka (lazy) — pengguna yang tak
membuka peta tak menanggung biayanya. Perubahan filter tetap memperbarui peta
(seperti sebelumnya); murni pindah-mode yang tak lagi memicu refetch.

Verifikasi: `yarn lint` 0 error; `yarn build` sukses. Frontend-only
(`DashboardPage.jsx`, `AssetMapFullView.jsx`).

## [#557] Peta: tambah aset — gagal simpan ke server tak lagi senyap, ada tombol "Coba Lagi" — 2026-07-23

Menambah aset lewat halaman peta memakai antrean optimistis; bila simpan ke
server GAGAL (mis. foto), sebelumnya galat itu **senyap** di konteks peta —
pengguna mengira aset berhasil terbentuk. Kini bila status sync baris menjadi
`failed`, muncul **toast galat persisten** dengan tombol **"Coba Lagi"**
(mengulang item YANG SAMA via retry — server dedup, tidak menggandakan aset/NUP)
dan **"Buang"**. Bersifat repeatable: retry yang gagal lagi memunculkan galat
lagi hingga berhasil; saat tersimpan, toast otomatis ditutup.

Implementasi: `handleOptimisticSubmit` mengembalikan `tempId`; aset yang ditambah
via peta dipantau lewat efek atas `syncStatuses`. Tanpa perubahan alur simpan
(idempotency-key tetap → aman diulang).

Verifikasi: `yarn lint` 0 error; `yarn build` sukses. Frontend-only
(`DashboardPage.jsx`).

## [#556] UX: drag-to-select — tekan-tahan kotak select lalu geser menyeleksi rentang (list & galeri) — 2026-07-23

Memilih banyak baris berurutan kini bisa dengan **tekan-tahan** kotak select
lalu **geser** melewati kotak select baris lain — seluruh yang dilewati ikut
terseleksi (atau ter-deseleksi bila memulai dari baris yang sudah terpilih;
arah mengikuti kotak awal). Berlaku di mode **list** (tabel desktop + kartu HP)
dan **galeri**.

Implementasi hook baru `useDragSelect` via event delegation (`elementFromPoint`)
sehingga aman untuk daftar tervirtualisasi — tak perlu meneruskan handler ke
tiap baris; cukup atribut `data-select-box`/`data-asset-id` pada tiap kotak +
`containerProps` pada pembungkus. HANYA pointer **mouse** — pada sentuh
(HP/tablet) gerakan tahan-geser tetap menggulir daftar seperti biasa. Klik biasa
(satu kotak) tetap bekerja; klik pasca-drag ditekan agar tak dobel-toggle.

Verifikasi: `yarn lint` 0 error; `yarn build` sukses. Frontend-only
(`useDragSelect.js` baru + `DashboardPage`, `VirtualizedAssetTable`,
`AssetGalleryCard`, `AssetMobileCard`).

## [#555] Mode cepat: auto-cari GPS hanya bila aset BELUM punya koordinat — 2026-07-23

Saat membuka aset di mode inventarisasi cepat, form otomatis mencari titik GPS
— bagus untuk aset baru, tetapi juga ikut memicu untuk aset yang **sudah punya
lat/lng** (menimpa koordinat lama tanpa diminta). Akarnya balapan render: efek
auto-GPS membaca `formData` yang masih kosong pada render pertama (efek init
`setFormData` belum sempat mengisi koordinat aset).

Perbaikan: efek auto-GPS kini juga men-*guard* pada **koordinat prop aset**
(`editAsset.koordinat_latitude/longitude`, tersedia sinkron). Bila aset sudah
berkoordinat → **tidak** auto-cari; tunggu pengguna menekan "Ambil GPS" lalu
simpan. Aset yang belum berkoordinat tetap auto-cari seperti semula.

Verifikasi: `yarn lint` 0 error; `yarn build` sukses. Frontend-only
(`AssetForm.jsx`).

## [#554] Inventarisasi: auto-status "Ditemukan" (bukan "Sudah Diinventarisasi" yatim) + bisa di-revert ke "Belum" — 2026-07-23

Dua perbaikan status inventarisasi yang saling terkait:

1. **Nilai yatim → valid.** Auto-status saat foto+koordinat lengkap sebelumnya
   ditulis `"Sudah Diinventarisasi"` — nilai yang TIDAK ada di daftar pilihan
   resmi (Belum/Ditemukan/Tidak Ditemukan/Berlebih/Sengketa), sehingga tak
   pernah tampil terseleksi di chip lapangan dan gagal validasi impor. Kini
   auto-status = **"Ditemukan"** (aset ber-foto memang ditemukan). Migrasi
   startup backend (idempoten) menormalkan data lama `"Sudah Diinventarisasi"`
   → `"Ditemukan"`. Berlaku untuk jalur peta, kamera, dan mode cepat.

2. **Bisa di-revert ke "Belum Diinventarisasi".** Dulu memilih "Belum" pada aset
   ber-foto+koordinat tak menetap — auto-promosi menimpanya kembali saat simpan.
   Kini AssetForm menandai saat status DIPILIH manual dan mematikan auto-promosi
   untuk simpan itu, sehingga pilihan (termasuk "Belum") menetap. Lembar cepat
   (`InventoryFieldSheet`) juga menambah chip **"Belum Diinventarisasi"** agar
   revert dapat dilakukan langsung di lapangan.

Verifikasi: `craco test` 11 uji `inventoryStatus` lulus (2 baru); `pytest`
backend 641 lulus; `yarn lint` 0 error; `yarn build` sukses.

## [#553] UX lapangan: seleksi dipertahankan setelah simpan massal berhasil — 2026-07-23

Sebelumnya `handleBatchUpdate` memanggil `clearSelection()` tepat setelah
ubah-massal sukses → seluruh seleksi baris langsung hilang. Untuk kerja lapangan
yang beruntun, kini **seleksi dipertahankan**: panel edit ditutup tetapi baris
tetap terseleksi, jadi pengguna dapat lanjut aksi lain atau memverifikasi hasil
tanpa memilih ulang. Seleksi dapat dikosongkan manual (tombol batal pilih / Esc)
seperti biasa. Pada kegagalan, seleksi tetap dipertahankan seperti sebelumnya.

Verifikasi: `yarn lint` 0 error; `yarn build` sukses. Frontend-only
(`DashboardPage.jsx`).

## [#552] Keandalan: penomeran BA-Perbaikan atomik (anti nomor kembar) — 2026-07-23

Nomor otomatis Berita Acara Perbaikan (`posting_kapitalisasi` di Pemeliharaan)
sebelumnya dibuat dari `count_documents(...) + 1` — **rawan balapan**: dua
posting kapitalisasi bersamaan membaca hitungan yang sama lalu menghasilkan
`BA-PRB/xxx` **kembar**. Diganti ke penghitung ATOMIK via koleksi `counters`
(`find_one_and_update` `$inc`, `ReturnDocument.AFTER`) — pola sama dengan nomor
tiket kegiatan (pengesahan.py) yang sudah teruji lintas-worker.

Semantik lama **dipertahankan** (hitung berjalan global berlabel tahun BA):
penghitung di-*seed* sekali dari jumlah BA yang sudah ada (`$setOnInsert`
idempoten) agar nomor baru menyambung tanpa bertabrakan dengan data lama.
Koleksi `counters` sudah ikut backup/restore; seed malas otomatis membangun
ulang bila arsip lama tak membawanya. Nomor BA yang diisi manual tetap dipakai
apa adanya (tak menyentuh penghitung).

Verifikasi: `pytest tests/unit` **641 lulus**; `compileall` bersih. Backend-only.

## [#551] Keamanan: rate-limit laporan pembukuan seluruh-DB (anti-DoS render PDF) — 2026-07-23

Delapan endpoint laporan pembukuan **memindai SELURUH aset satker** lalu
merender PDF/XLSX berat (ReportLab/xlsxwriter) tanpa filter kegiatan —
`posisi-bmn-pdf`, `dbr-pdf`, `kir-pdf`, `penyusutan-pdf`, `lbkp-pdf`, `lkb-pdf`,
`calbmn-pdf`, `rekonsiliasi-xlsx`. Sebelumnya tanpa rate-limit, sehingga bisa
di-hammer (mengulang render seluruh-DB) untuk menghabiskan CPU/memori server.
Kini masing-masing dibatasi **6/menit per-IP** (pola `@limiter.limit` yang sama
dengan endpoint berat lain di exports/auth/siman). Batas per-endpoint, jadi
membuka kedelapan laporan berbeda satu kali tetap lancar; hanya pengulangan
laporan yang SAMA >6×/menit yang ditahan.

Catatan: TTL token media (30 hari) **dipertahankan** — sejak #549 token media
ikut dicabut saat reset/ubah password (revokasi `sesi_epoch`), sehingga jendela
paparannya kini dibatasi pencabutan, bukan hanya TTL; memperpendek TTL justru
merusak stabilitas URL media (tujuan token itu).

Verifikasi: `pytest tests/unit` **641 lulus** (termasuk uji registrasi rute app
dengan dekorator baru); `compileall` bersih. Backend-only.

## [#550] Keamanan: tutup bypass autentikasi WebSocket (revokasi + nonaktif + scope) — 2026-07-23

Temuan review adversarial AUTH-C: endpoint `/ws/{activity_id}` memvalidasi token
lewat `jwt.decode` **signature-only tanpa lookup user**, sehingga melewati tiga
kendali yang ditegakkan `_decode_bearer` di API biasa: (1) revokasi `sesi_epoch`
(#549), (2) `is_active` (akun dinonaktifkan), dan (3) penolakan token ber-scope
`media`. Akibatnya token media basi (umur 30 hari) atau token user yang sudah
dicabut/dinonaktifkan tetap bisa masuk kanal kolaborasi real-time.

Ditutup (`routes/websocket.py`):
- `_decode_ws_token` menolak token ber-scope `media` (murah, tanpa DB — klien WS
  memakai token sesi, dikonfirmasi di `useWebSocket.js`).
- Gerbang baru `_ws_user_allowed` melakukan **satu** lookup user saat connect
  (di-cache TTL 30 dtk agar burst reconnect tak menghantam Mongo) untuk menolak
  akun nonaktif & token yang `sesi_epoch`-nya sudah dicabut. Nilai epoch rusak
  ditangani aman. Koneksi ditolak dengan close-code aplikasi 4401.

Catatan: gerbang berlaku saat **connect** (koneksi baru); pencabutan berlaku
untuk sambungan berikutnya dalam ≤30 dtk (TTL cache). Kompatibel mundur: token
lama tanpa `sesi_epoch` = epoch 0, user tanpa field = epoch 0.

Verifikasi: `pytest tests/unit` **641 lulus** (+1 uji `_decode_ws_token` tolak
media/rusak); `compileall` bersih. Backend-only.

## [#549] Keamanan: revokasi token saat reset/ubah password (sesi_epoch) — 2026-07-23

Sebelumnya token akses (24 jam) & token media (30 hari) tetap berlaku sampai
kedaluwarsa **walau password sudah direset** — bila perangkat lama dikuasai
penyerang, sesi lamanya belum tercabut. Ditambah mekanisme **sesi_epoch**:

- Setiap user punya penghitung `sesi_epoch` (default 0). Login menyematkannya
  ke klaim JWT (token akses & media).
- Reset password (via OTP) dan admin "ubah password" menaikkan `sesi_epoch`
  (`$inc`) → seluruh token lama gugur.
- `_decode_bearer` menolak token yang `sesi_epoch`-nya lebih kecil dari milik
  user ("Sesi telah berakhir — silakan masuk kembali").

**Kompatibel mundur:** token lama tanpa klaim = epoch 0; user lama tanpa field
= epoch 0 → user yang belum pernah reset tetap login normal; yang sudah reset
otomatis menolak semua token lama. Nilai `sesi_epoch` rusak (mis. string dari
restore lama) ditangani aman di **semua jalur** — validasi token
(`_decode_bearer`), login, dan tulis (reset/ubah password membaca lalu `$set`,
bukan `$inc`, agar tak memicu WriteError/500). Token tamu e-sign (`typ=sign`)
tak terpengaruh (jalur `require_sign_token`, bukan `_decode_bearer`).

Verifikasi: `pytest tests/unit` **640 lulus** (+1 uji klaim `sesi_epoch`);
`compileall` bersih. Backend-only.

## [#548] Keamanan: pengerasan login — kunci brute-force + setara-waktu anti-enumerasi — 2026-07-23

Dua celah pada `POST /auth/login`:

1. **Enumerasi username via timing.** Saat username tak ditemukan, endpoint
   langsung balik 401 **tanpa** menjalankan bcrypt, sedangkan username yang ada
   menjalankan bcrypt (~ratusan ms). Selisih waktu ini membocorkan username mana
   yang valid. Ditutup: `auth_utils.verify_password_dummy()` menjalankan bcrypt
   terhadap hash boneka (cost sama) lalu membuang hasilnya, sehingga waktu
   respons setara antara "user ada" dan "user tidak ada".

2. **Tidak ada kunci brute-force per akun.** Hanya ada rate-limit per-IP
   (10/menit), tak menahan credential-stuffing terdistribusi. Ditambah: setelah
   **10** percobaan gagal beruntun, akun dikunci **15 menit** (auto-buka;
   penghitung di-reset saat login sukses). Field baru di dokumen user:
   `login_gagal` + `login_terkunci_hingga`. Nilai timestamp rusak diabaikan
   (tak sampai 500). Pesan tetap generik ("Username atau password salah") kecuali
   status terkunci (429 dengan sisa menit).

Pesan login sudah generik sejak awal (tak membocorkan akun ada/tidak). Kunci
auto-expire agar tak menjadi DoS permanen.

Verifikasi: `pytest tests/unit` **639 lulus** (+1 uji `verify_password_dummy`);
`compileall` bersih. Backend-only.

## [#547] Keamanan: backup/restore/reset dibatasi KHUSUS super-admin pusat — 2026-07-23

Operasi seluruh-DB (backup, restore, reset) menyentuh data **SEMUA satker**,
jadi tak boleh dijalankan admin yang terikat satu satker — hanya **super-admin
pusat** (admin lintas-satker: `role == "admin"` **dan** `kode_satker` kosong).
Sebelumnya endpoint ini hanya menuntut `role == "admin"`, sehingga admin satker
pun bisa mengunduh/menimpa/menghapus data satker lain.

Perjelas batasan **admin vs super-admin**:
- Admin satker: mengelola **hanya** datanya sendiri (isolasi M-SCOPE) lewat modul.
- Super-admin pusat: memegang siklus data seluruh sistem (backup/restore/reset).

Ditutup:
- `auth_utils.py` — helper baru `is_super_admin(user)` + gate `require_super_admin`
  (403 dengan pesan yang menjelaskan bedanya).
- `routes/backup.py` — 13 titik gate backup/restore/arsip/otomatis kini menuntut
  super-admin (bukan sekadar admin).
- `server.py` — `DELETE /system/reset-all` memakai `require_super_admin` +
  cek in-body super-admin.
- Frontend `PengaturanPage.jsx` — tab **Sistem** digerbang `isSuperAdmin`
  (`role === "admin"` && `kode_satker` kosong); admin satker melihat penjelasan
  bahwa operasi mencakup data seluruh satker dan hanya untuk super-admin pusat.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih; `eslint`
`--max-warnings=0` bersih; `yarn build` sukses.

## [#546] Keamanan: tolak nilai non-skalar pada PATCH aset (anti operator-injection) — 2026-07-23

Temuan audit injeksi [rendah]: `PATCH /assets/{id}` membaca body JSON mentah dan
hanya meng-allow-list KUNCI (`PATCHABLE_FIELDS`), bukan TIPE nilai. Writer dapat
mengirim `{"asset_code": {"$ne": null}}` → operator NoSQL `$ne` menyusup ke query
cek-duplikat dan nilai dict tertulis via `$set` (merusak tipe field). Ditutup:
setelah allow-list kunci, tolak 400 bila ada nilai `dict`/`list` (semua field
patchable memang skalar).

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.
Menutup rangkaian pengerasan pasca-audit lanjutan (sapuan 6-agen).

---

## [#545] Keamanan: pengerasan unggah gambar (decompression-bomb, magic byte, nosniff) — 2026-07-23

Temuan audit unggah/berkas:
- **Decompression-bomb PIL** [sedang-rendah]: `Image.MAX_IMAGE_PIXELS` tak pernah
  diturunkan (default ~89MP) → gambar ~150MP (berkas kecil) dapat ter-dekode ke
  ratusan MB RAM; endpoint `POST /ttd/olah-foto` bahkan dapat dicapai penanda
  tangan TAMU e-sign (DoS/OOM di VPS kecil). Ditutup: `shared_utils` menyetel
  `PILImage.MAX_IMAGE_PIXELS = 50_000_000` **global proses** (semua titik dekode
  Pillow) → Pillow menolak >100MP; `foto_ke_png_transparan` menangkap
  `DecompressionBombError` → 400 rapi.
- **Magic-byte** [rendah]: unggah gambar BAST (`assets.py`) & foto pegawai
  (`pegawai.py`) sebelumnya hanya percaya ekstensi/`content_type` (bisa
  dipalsukan). Kini memvalidasi ISI via `cek_magic_gambar` (konsisten dengan
  lampiran modul lain).
- **nosniff** [rendah]: respons `GET /pegawai/{id}/foto` & `/foto-asli` kini
  menyertakan `X-Content-Type-Options: nosniff`.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih; `MAX_IMAGE_PIXELS`
terpasang saat impor. Backend-only.

---

## [#544] Keamanan: kunci brute-force OTP (reset password & registrasi) — 2026-07-23

Temuan audit terverifikasi [tinggi]: verifikasi OTP (`reset_password`,
`verify_otp`) membandingkan `stored["otp"] != otp` TANPA penghitung percobaan
dan TANPA invalidasi saat salah — OTP 6-digit (ruang 10⁶), TTL 10 menit, dan
rate-limit hanya per-IP. Penyerang terdistribusi dapat menebak paralel satu
OTP tetap selama 10 menit → pengambilalihan akun tanpa akses email.

- **`shared_utils.py`**: helper `catat_gagal_otp(email, maks=5)` — `$inc attempts`
  atomik; saat mencapai 5 gagal, OTP DIHAPUS (invalidasi) → brute-force terkunci
  ke <10 tebakan per OTP, independen dari IP. `store_otp` mereset `attempts=0`
  saat OTP baru diterbitkan.
- **`routes/auth.py`**: kedua verifikasi kini `hmac.compare_digest` (konstan-waktu,
  dibandingkan sebagai bytes agar input non-ASCII tak memicu 500) + memanggil
  `catat_gagal_otp` pada tiap kegagalan (pesan "OTP dinonaktifkan" saat terkunci).

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih; uji logika
banding+lockout terpisah. Backend-only.

---

## [#543] Keamanan: guard satker by-id di Wasdal/Pemusnahan/Perencanaan/Penganggaran — 2026-07-23

Lanjutan audit: daftar keempat modul sudah ter-scope, tapi endpoint yang
mengambil dokumen by-id lalu BACA/UBAH/HAPUS belum ber-guard → user satker A
bisa memajukan status / menghapus / melihat PDF dokumen satker B (IDOR).

- **Wasdal**: `selesaikan_penertiban`, `terbitkan_ba_insidentil`,
  `laporkan_insidentil`, `ba_insidentil_pdf` → `pastikan_akses_dok_satker`;
  `hapus_penertiban`, `hapus_insidentil` → `delete_one` ter-scope
  (404 mendahului pembersihan lampiran lintas-satker).
- **Pemusnahan**: `usulkan_penghapusan_dari_ba`, `ba_pemusnahan_pdf` →
  `pastikan_akses_dok_satker`; `hapus_pemusnahan` → delete ter-scope;
  `buat_pemusnahan` → `pastikan_akses_aset` (aset via kegiatan; `activity_id`
  ditambahkan ke proyeksi).
- **Perencanaan**: `transisi_usulan_rkbmn`, `sanding_usulan` → guard;
  `hapus_usulan_rkbmn` → delete ter-scope.
- **Penganggaran**: `transisi_anggaran` → guard; `hapus_usulan_anggaran` →
  delete ter-scope (filter status dipertahankan); `_ambil_snapshot_rkbmn`
  meneruskan `user` + guard dokumen RKBMN sumber.

Anti-race `find_one_and_update` tetap utuh; super-admin & dokumen era-lama
lolos. Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih.
Backend-only.

---

## [#542] Keamanan: guard satker pada lampiran 8 modul (IDOR sub-resource) — 2026-07-23

Sapuan audit menemukan endpoint LAMPIRAN (unggah/unduh/hapus) di 8 modul
mengambil dokumen INDUK by-id TANPA filter/guard satker — inkonsisten dengan
CRUD utamanya yang sudah ter-scope. User satker A yang tahu id induk + file_id
bisa **unduh/hapus/unggah** lampiran milik satker B (dokumen usulan
penghapusan/pemindahtanganan, BAST pemusnahan, polis pengamanan, dokumen
pengadaan, SK PSP, BA insidentil wasdal, perjanjian pemanfaatan).

Pola baku diterapkan seragam di: `pemanfaatan`, `penggunaan` (psp),
`penghapusan`, `pengamanan`, `pemusnahan`, `pengadaan`, `pemindahtanganan`,
`wasdal`:
- **Unduh** — filter lookup induk dibungkus `scope_query_field_satker` (induk
  satker lain → 404).
- **Unggah** — proyeksi induk menyertakan `kode_satker` + `pastikan_akses_dok_satker`
  setelah cek 404.
- **Hapus** — filter `update_one` dibungkus `scope_query_field_satker`.

Semua koleksi induk memang menyimpan `kode_satker` saat create → same-satker
tak terputus; super-admin & dokumen era-lama tetap lolos (aman-mundur).

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.

---

## [#541] Keamanan: isolasi satker pada Sinkronisasi SIMAN — 2026-07-23

Lanjutan sapuan audit: modul SIMAN V2 (`routes/siman.py`) beroperasi pada
SELURUH koleksi `assets` tanpa scope satker:
- `import_siman` (admin) menulis subdoc `siman` + `$inc version` ke aset SEMUA
  satker & bisa menandai "tidak ditemukan" pada aset satker lain.
- `terapkan_siman` (writer) menerapkan nilai SIMAN (mengubah field aset) ke aset
  satker lain by-id.
- `daftar_selisih_siman` & `ringkasan_siman` membocorkan kode/NUP/nama/harga
  aset satker lain; register `siman_imports` terbaca lintas-satker.

Ditutup:
- Kueri aset di `import_siman`, `daftar_selisih_siman`, `ringkasan_siman`
  di-`scope_query_aset` (super-admin lintas-satker).
- `terapkan_siman` ber-guard `pastikan_akses_aset`.
- Record impor menyimpan `kode_satker`; `ringkasan/detail/csv/buat-draft`
  membaca `siman_imports` ter-scope `scope_query_field_satker` /
  ber-guard `pastikan_akses_dok_satker`; buat-draft juga ber-guard
  `pastikan_akses_kegiatan_id` pada kegiatan tujuan.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.

---

## [#540] Keamanan: isolasi satker pada modul Persuratan — 2026-07-23

Sapuan audit lanjutan (fan-out 6 agen) menemukan modul **Persuratan** (`surat`)
belum ter-isolasi satker sama sekali — buku agenda satker A menampilkan
SELURUH surat satker lain (perihal/tujuan/pengirim/nomor), dan surat satker B
bisa disahkan/dibatalkan/diubah/dihapus oleh satker A (IDOR end-to-end).

Ditutup dengan pola baku:
- `daftar_surat` & `export_agenda` + 4 hitungan ringkasan kini ter-scope
  `scope_query_field_satker`.
- `booking_surat_keluar` & `agenda_surat_masuk` menyimpan `kode_satker` penerbit.
- `transisi_surat` / `ubah_surat` / `hapus_surat` ber-guard
  `pastikan_akses_dok_satker` (403 lintas-satker; super-admin & surat era-lama
  tanpa kode tetap lolos — aman-mundur).

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.
Bagian dari gelombang perbaikan pasca-audit keamanan lanjutan.

---

## [#539] Keandalan: gerbang atomik single-flight backup/restore — 2026-07-23

Temuan audit terverifikasi (concurrency): guard "hanya satu backup/restore
berjalan" memakai pola **check-then-insert** yang TIDAK atomik — dua request
konkuren bisa sama-sama lolos `find_one({status: running})` (job masih
`queued`) lalu keduanya jalan. Dua restore berselang paling berbahaya:
`run_restore_task` meng-*wipe* koleksi + re-impor GridFS → data & foto bisa
rusak/tercampur.

Ditutup dengan gerbang ATOMIK level-DB:

- **`indexes.py`** — partial unique index `backup_jobs.active_lock`
  (`partialFilterExpression {$exists:true}`, kompatibel semua versi MongoDB —
  tanpa `$in` yang butuh 6.0+).
- **`backup.py`** — job aktif (queued/running) membawa `active_lock="GLOBAL"`;
  insert kedua → `DuplicateKeyError` → 409. Lock dilepas (`$unset`) saat job
  mencapai status terminal (`update_job` completed/failed) atau di-reap
  `cleanup_stale_jobs` (kini juga menyapu `queued` macet). Ke-4 pembuat job —
  backup manual, restore unggah, restore dari arsip, dan **backup otomatis
  terjadwal** — kini melewati gerbang yang sama (backup otomatis melewati
  siklus bila ada proses aktif). Fast-path `find_one` diperluas ke
  `status ∈ {queued, running}` untuk pesan 409 lebih dini.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.
Menuntaskan backlog cacat terkonfirmasi dari audit menyeluruh.

---

## [#538] Keandalan: strong-ref task latar (cegah GC fire-and-forget) — 2026-07-23

Temuan audit terverifikasi (concurrency): beberapa `asyncio.create_task(...)`
dipanggil TANPA menyimpan referensi. asyncio hanya memegang *weak* ref → task
fire-and-forget bisa di-GC saat suspended di titik `await` ("Task was destroyed
but it is pending"), mematikan pekerjaan latar diam-diam. Pola perbaikan sudah
ada di `exports.py` (`_EKSPOR_TASKS` set + `add_done_callback`), kini diterapkan
seragam:

- **categories.py** — impor kategori massal (`_do_bulk_import`) kini ber-`_IMPORT_TASKS`
  (impor tak berhenti separuh jalan / job macet "importing" selamanya).
- **backup.py** — helper `_track_bg` untuk 4 task: backup, restore (unggah &
  dari arsip), dan loop scheduler backup otomatis (operasi integritas data &
  loop terjadwal tak mati diam-diam).
- **websocket.py** — publish event lintas-worker (`event_bus.publish`) kini
  ber-`_BG_TASKS` (notifikasi real-time tak hilang di worker lain).

Task yang sudah aman (disimpan di variabel/global: heartbeat WS, loop presence)
tidak diubah. Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih.
Backend-only.

---

## [#537] Keandalan: idempotensi reklasifikasi + OCC simpan KIB (Pembukuan) — 2026-07-23

Dua temuan audit terverifikasi [tinggi] di modul Pembukuan (`mutasi_bmn.py`),
kelanjutan konvensi "semua tulis ber-OCC + Idempotency-Key":

- **Reklasifikasi aset** (`POST /pembukuan/reklasifikasi`) menulis SEPASANG
  jurnal 304/107 + memutakhirkan kode/NUP aset **tanpa Idempotency-Key** —
  double-submit menghasilkan jurnal ganda & NUP meloncat. Kini menerima header
  `Idempotency-Key` (pola baku: replay respons tersimpan, klaim atomik → 409
  bila in-flight).
- **Simpan KIB** (`PUT /pembukuan/kib/{id}`) menulis **tanpa OCC** → lost-update
  bila dua editor menyimpan KIB aset yang sama. Kini ber-OCC via `If-Match`:
  `_aset_kib_proj` mengembalikan `version`, `simpan_kib` melakukan CAS
  ber-versi (409 bila aset berubah) dan mengembalikan `version` baru. Frontend
  `PembukuanPage.jsx` mengirim `If-Match` dari versi yang dibaca & menyegarkan
  versi pasca-simpan. Tanpa If-Match tetap jalan (aman-mundur).

Verifikasi: `pytest tests/unit` 638 lulus; `eslint` bersih; `yarn build`
sukses.

---

## [#536] Keandalan: Idempotency-Key pada transaksi persediaan (masuk & keluar) — 2026-07-23

Temuan audit terverifikasi [tinggi]: endpoint transaksi persediaan menulis
stok/jurnal **tanpa Idempotency-Key** — double-submit (klik ganda, retry
setelah timeout jaringan) menggandakan stok masuk atau pengeluaran. Melanggar
konvensi baku "semua tulis ber-OCC + Idempotency-Key".

- **Backend** (`routes/persediaan.py`): `POST /persediaan/{id}/masuk` &
  `.../keluar` kini menerima header `Idempotency-Key` (opsional) dengan pola
  baku yang sudah dipakai `assets.py`: `get_idempotent_response` → putar ulang
  respons tersimpan; `reserve_idempotency_key` → klaim atomik (409 bila sedang
  diproses); `store_idempotent_response` setelah sukses. Param `request`
  ber-default `None` agar pemanggil internal (impor massal / Pengadaan) yang
  tak mengoper request tetap jalan. Keluar tetap ber-OCC versi seperti semula.
- **Frontend** (`pages/PersediaanPage.jsx`): dialog Masuk/Keluar membuat kunci
  idempotensi per sesi (dibuat saat dibuka, dipakai ulang saat submit diulang,
  dibuang saat ditutup) dan mengirimnya sebagai header.

Verifikasi: `pytest tests/unit` 638 lulus; `eslint` bersih; `yarn build`
sukses. Aman-mundur (tanpa header = perilaku lama).

---

## [#535] Keamanan: isolasi satker penuh pada Penilaian & Pemeliharaan — 2026-07-23

Lanjutan pengerasan pasca-audit. Dua modul siklus ternyata **belum ter-scope
satker sama sekali** — daftar, laporan, dan mutasinya membaca/menulis lintas
satker. Ditutup dengan pola baku (`scope_query_field_satker` untuk daftar,
`pastikan_akses_aset` untuk write, simpan `kode_satker` pada dokumen baru;
super-admin & dokumen era-lama tanpa kode tetap lolos — aman-mundur).

- **Penilaian** (`routes/penilaian.py`):
  - Posisi penyusutan kini di-`scope_query_aset` (satker hanya melihat asetnya).
  - Register koreksi nilai: daftar & ekspor CSV di-scope; riwayat-nilai per aset,
    catat koreksi, tandai tercatat-SAKTI, dan hapus kini ber-guard/ber-scope.
  - Record koreksi baru menyimpan `kode_satker` penerbit.
- **Pemeliharaan** (`routes/pemeliharaan.py`):
  - Rekap biaya, DHPB PDF, daftar/ekspor jadwal berkala, daftar & ekspor riwayat
    di-scope satker.
  - Catat pemeliharaan (yang **memutakhirkan kondisi aset**) & buat jadwal kini
    ber-guard `pastikan_akses_aset` + simpan `kode_satker`; ubah/hapus jadwal,
    pratinjau/posting kapitalisasi (yang **menambah nilai & jurnal 202**),
    unduh BA Perbaikan, dan hapus catatan kini ber-guard/ber-scope.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.

---

## [#534] Keamanan: tutup IDOR isolasi satker pada mutasi register siklus — 2026-07-22

Temuan audit menyeluruh (verifikasi): beberapa endpoint MUTASI register siklus
mengambil dokumen by-id lalu mengubah/menghapus **tanpa** `pastikan_akses_dok_satker`
— sehingga admin/operator satker A bisa mengubah/menghapus/memajukan status
dokumen satker B (IDOR lintas-satker), padahal daftar & create sudah ter-scope.

Guard `pastikan_akses_dok_satker` ditambahkan (403 bila milik satker lain; super-
admin & dokumen era-lama tanpa kode tetap lolos — aman-mundur):

- **Pemindahtanganan** — `POST /pemindahtanganan/{id}/status` (transisi persetujuan).
- **Pengadaan** — `DELETE /pengadaan/{id}` (hapus register + pelepasan back-link aset).
- **Pemanfaatan** — `PUT /pemanfaatan/{id}` & `POST /pemanfaatan/{id}/kontribusi`.
- **Penghapusan** — `POST /penghapusan/usulan/{id}/status` (terbit SK).

Verifikasi: `pytest tests/unit` 638 lulus; uji perilaku guard (A↔B → 403;
A↔A/super-admin/dok-era-lama → lolos). Backend-only. Bagian dari rangkaian
pengerasan pasca-audit (menyusul: transaksi persediaan/mutasi idempotensi, dsb.).

---

## [#533] Ubah Massal: tambah Nama Aset, Garansi Hingga & Jenis Garansi — 2026-07-22

Tiga field kini bisa diubah massal (Ubah Massal / batch edit):

- **Nama Aset** (`asset_name`) — di registry `asset_fields.py` di-tandai
  `batchable=True`; input ditambah di panel bagian "Identitas & Catatan".
- **Garansi Hingga** (`garansi_hingga`, tanggal) & **Jenis Garansi**
  (`garansi_jenis`, datalist: Pabrikan/Distributor/Toko/Purna Jual/Lainnya) —
  keduanya sudah `batchable` di registry, kini punya input di panel bagian
  "Administrasi Perolehan". Semua mendukung opsi "Kosongkan" seperti field lain.

Backend allow-list ekspor otomatis dari registry (`BATCHABLE_FIELD_NAMES`), jadi
tetap selaras dengan form aset. Verifikasi: `pytest tests/unit` 638 lulus
(termasuk uji registry anti-drift); eslint bersih; `yarn build` sukses.

---

## [#532] Tombol Export Excel pakai jalur job latar (frontend) — 2026-07-22

Langkah 3 (penutup) job latar: tombol **Export → Excel** kini memakai endpoint
async `/export/xlsx/async` sehingga ekspor berfoto besar tak lagi menahan
koneksi/timeout — dari sisi pengguna: klik → progres di toast → **unduh
otomatis** saat selesai.

- **`lib/jobExport.js`** — helper `exportViaJob(submitUrl)`: POST → dapat
  `job_id` → poll `GET /api/jobs/{id}` tiap 1,5 dtk (progres/pesan di toast) →
  saat `done` unduh `GET /api/jobs/{id}/download` via anchor native + `?token`
  (andal untuk file besar lewat ingress). Toleran 404 sesaat & gangguan jaringan.
- **`handleExport('xlsx')`** dialihkan ke jalur job; **CSV tetap sinkron**
  (ringan/stream). Auth submit+poll otomatis via interceptor axios global.
- Catatan: polling inline — bila pengguna meninggalkan halaman, job tetap jalan
  di server tetapi unduh-otomatis tak terpicu (bisa diekspor ulang). Task-tray
  mengambang multi-job = peningkatan berikutnya bila diperlukan.

Verifikasi: `eslint` 0 error (hanya warning lama); `yarn build` sukses.
Frontend-only.

---

## [#531] Ekspor Excel sebagai job latar (async, tak lagi timeout) — 2026-07-22

Langkah 2 job latar: ekspor XLSX berfoto besar kini bisa jalan sebagai **job
async** (submit→poll→unduh), lepas dari batas timeout ~120s yang mengancam
ekspor sinkron di dekat cap 5000 aset.

- **`bangun_xlsx_bytes(query, activity_id, base_url)`** — logika build workbook
  diekstrak (deterministik, verbatim) dari endpoint `/export/xlsx` agar dipakai
  ULANG oleh worker. Endpoint sinkron LAMA tetap ada (memanggil helper yang sama;
  perilaku identik — terverifikasi menghasilkan workbook 2-sheet yang valid).
- **`POST /api/export/xlsx/async`** → `job_id`; worker merakit workbook lalu
  menyimpannya ke **GridFS** (multi-worker-safe). Cap 5000 tetap ditegakkan
  sebelum job dibuat.
- **Router job generik** `GET /api/jobs/{id}` (status/polling) &
  `/api/jobs/{id}/download` (dual-auth header|`?token`) — akses **hanya pemilik
  job atau admin** (fail-closed).

Pengerasan dari tinjauan adversarial (13 agen) sebelum merge:

- **Artifact GridFS tak lagi yatim** — dokumen job auto-hapus via TTL 7 hari,
  tetapi blob GridFS tak ikut; ditambah penyapu periodik `bersihkan_artifact_yatim`
  (hapus blob ekspor > 7 hari; foto/dokumen aset tanpa `metadata.job_id` TAK
  tersentuh) + penjadwalan `bersihkan_job_basi` (relabel job macet) via loop
  pemeliharaan startup.
- **Task worker tak bisa di-GC** — strong-reference disimpan +
  `add_done_callback`; `CancelledError` (shutdown) menandai job agar klien tak
  polling abadi.
- **Batas konkurensi** — semaphore (maks 2 build ekspor berat serentak) cegah OOM.
- **Kontrol akses fail-closed** + **job_id 128-bit** (uuid penuh).

Verifikasi: smoke async end-to-end (worker→GridFS→xlsx valid; status/unduh;
otorisasi non-pemilik→403; jalur gagal→error) + penyapu (yatim dihapus, foto
aman). `pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only.
Berikutnya (JOB-3): frontend task-tray + wire tombol Export ke jalur async.

---

## [#530] Fondasi job latar bersama + impor kategori tahan multi-worker — 2026-07-22

Langkah 1 modul **job latar (background job)**. Modul baru `jobs.py` menyimpan
state job di MongoDB (`db.background_jobs`) sehingga tahan multi-worker & restart
proses — fondasi untuk memindahkan ekspor/laporan berat ke antrean async (langkah
berikutnya) agar tak menahan koneksi/timeout.

- **`jobs.py`**: `buat_job` / `update_job` / `get_job` / `bersihkan_job_basi`
  (relabel job macet). Dokumen job auto-hapus via **TTL index** 7 hari pada
  `created_at`; lookup `job_id` ber-indeks unik.
- **BUG multi-worker diperbaiki**: impor kategori massal dulu menyimpan progres
  di **dict in-memory** — di `uvicorn --workers 4`, POST menaruh progres di
  memori satu worker sedangkan polling progres bisa mendarat di worker lain →
  **404 / progres macet**. Kini persisten di Mongo sehingga polling selalu
  menemukan job apa pun worker-nya. Progres ditulis ter-throttle (tiap 200
  baris) agar hemat tulis.
- **Kontrak frontend tetap**: respons `GET /categories/import-progress/{job_id}`
  membawa field yang sama (`status/total/processed/imported/skipped/errors/
  done`) — tanpa perubahan UI. Logika impor (padding kode, dedup, batch 500)
  tak berubah.

Verifikasi: smoke FakeDB 4 skenario (lifecycle job; relabel job basi; impor
end-to-end imported=3/skipped=1/errors=1). `pytest tests/unit` 638 lulus;
`compileall` bersih. Backend-only. Berikutnya: async ekspor XLSX/PDF via jobs.py.

---

## [#529] Logging terstruktur + korelasi request-id (observability) — 2026-07-22

Langkah observability berikutnya: menelusuri satu request lintas banyak baris log
kini mudah. Modul baru `backend/log_setup.py`:

- **Korelasi request-id** — middleware ASGI **murni** (aman untuk StreamingResponse
  foto/PDF/ekspor — tak membuffer body) melahirkan/mewarisi id per request,
  menaruhnya di `ContextVar` sehingga **setiap** baris log request itu membawa
  `request_id` yang sama, dan menyematkan header respons `X-Request-ID`. Id dari
  klien (`X-Request-ID`) di-sanitasi (`[A-Za-z0-9._-]`, maks 64).
- **Access log terstruktur** — satu baris per request (metode, path, status,
  durasi ms, client_ip); path/method di-sanitasi karakter kontrol (cegah injeksi
  baris log via `%0A`). Health-check (`/api/health*`) dilewati agar log tak banjir.
- **Format via env** — `LOG_FORMAT=plain` (default, human-readable + request_id)
  atau `json` (JSON-lines untuk agregator); `LOG_LEVEL` (default INFO). Mengganti
  `logging.basicConfig`; 191 pemanggilan `logger.*` yang ada ikut format baru
  tanpa disentuh.
- **Status 500 tercatat benar** — exception tak-tertangani (dibalas 500 oleh
  ServerErrorMiddleware di lapisan lebih luar) tetap dicatat sebagai 500 di access
  log, bukan 0.

Pengerasan dari tinjauan adversarial:

- **Logger uvicorn disatukan ke root** — `uvicorn`/`uvicorn.error` diarahkan ke
  handler root (ikut format & JSON), dan access-log bawaan uvicorn dibisukan
  agar tak ada baris akses GANDA dan skip-health efektif (dulu uvicorn.access
  tetap membanjiri log health tanpa request_id).
- **Task latar tak lagi memakai request-id basi** — `run_backup_task`,
  `run_restore_task`, `_do_bulk_import` men-set id `job:<id>` sendiri (task
  `asyncio.create_task` mewarisi salinan konteks request pemicu; tanpa ini job
  3-menit menulis log ber-id request yang sudah tutup).
- **Sanitasi diperluas** ke karakter kontrol C1 (0x80–0x9F), bukan hanya C0.

Verifikasi: smoke 7 skenario via Starlette TestClient (korelasi id handler↔access;
propagasi & sanitasi X-Request-ID; StreamingResponse utuh; exception→500;
health di-skip; anti log-injection path) + tinjauan adversarial. `pytest
tests/unit` 638 lulus; `compileall` bersih. Backend-only.

---

## [#528] Gerbang deploy verifikasi kesehatan mendalam (anti false-green #2) — 2026-07-22

Lanjutan observability & pelengkap `/api/health/deep` (#527). Skrip deploy VPS
dulu hanya memeriksa liveness dangkal (`/api/health`) pasca-restart — proses bisa
hidup tapi **MongoDB/GridFS tak terjangkau** (kredensial DB salah, Mongo mati,
disk penuh), sehingga deploy "sukses" padahal tiap operasi data gagal.

- `deploy_vps.sh` kini, setelah liveness dangkal lolos, **juga** mem-poll
  `/api/health/deep` sampai ~30 dtk (jendela pemanasan pool koneksi Mongo).
  200 = Mongo+GridFS sehat → lanjut; 503/timeout → **deploy GAGAL (exit 1)**
  dengan mencetak respons terakhir untuk diagnosis.
- URL dapat dioverride via `BACKEND_DEEP_HEALTH_URL`.
- **Tanpa** auto-rollback pada tahap ini (mekanisme kembalikan-produksi-otomatis
  disiapkan terpisah setelah persetujuan).

Verifikasi: `bash -n` bersih. Skrip deploy-only (tak memengaruhi runtime app).

---

## [#527] Probe kesehatan mendalam `/api/health/deep` (observability) — 2026-07-22

Fondasi observability. `/api/health` sengaja instan & tanpa dependensi (dipakai
deteksi offline frontend), sehingga tak bisa mendeteksi "proses hidup tapi DB
mati". Ditambah `GET /api/health/deep` yang memverifikasi **aktif** dependensi:

- **MongoDB** — `ping` + catat latensi.
- **GridFS** — baca ringan `fs.files` (storage foto/dokumen terjangkau).
- Balas **HTTP 503** bila ada yang tak sehat (agar monitor uptime & gerbang
  deploy mendeteksi), 200 bila semua sehat; body memuat status per-cek +
  latensi + versi aplikasi. Tanpa auth, operasi ringan — aman untuk probe.

Verifikasi: smoke 3 skenario (sehat→200; Mongo tumbang→503; GridFS tumbang→503).
`pytest tests/unit` 638 lulus; `compileall` bersih. Backend-only. Langkah
berikutnya (PR terpisah): gerbang deploy pakai `/health/deep` + rollback otomatis.

---

## [#526] Indeks untuk sort daftar paginasi yang belum tertutup — 2026-07-22

Lanjutan audit performa: beberapa daftar ber-paginasi pada koleksi yang tumbuh
menyortir field yang **belum ter-indeks**, sehingga MongoDB melakukan COLLSCAN
+ sort di memori tiap halaman — makin lambat seiring bertambahnya data. Ditutup
dengan indeks kunci-sort (murni performa, tanpa perubahan perilaku/UI/skema).

- **`mutasi_bmn` (Buku Barang)** — dulu **tanpa indeks apa pun**. Ditambah
  `(tanggal_buku↓, created_at↓)` untuk daftar jurnal global & `(asset_id,
  tanggal_buku↓)` untuk riwayat per aset (KIB/timeline/LBP).
- **`lpb` (Riwayat LPB)** — ditambah `id` (unik, unduh ulang per id) &
  `(created_at↓)` (daftar).
- **`bast_serah_terima`** — ditambah `id` (unik, lihat/unduh per id),
  `(created_at↓)` (daftar), & `asset_ids` (multikey, badge riwayat per aset).
- **`surat` (buku agenda)** — ditambah `(tahun↓, no_agenda↓)`; indeks lama
  `(jenis, tahun, no_agenda)` tak melayani sort saat filter `jenis` tak dipakai.

Indeks `id` unik memakai pola aman-mundur (fallback non-unik bila data lama
telanjur duplikat) agar pembuatan indeks tak pernah gagal. Verifikasi:
`compileall` bersih; `pytest tests/unit` 638 lulus (uji impor app memuat
`indexes.py`). Backend-only.

---

## [#525] Sinkron snapshot offline pakai keyset pagination (buang $skip O(n²)) — 2026-07-22

Sinkron cache offline (mode Inventarisasi) menyedot SELURUH aset satu kegiatan
dalam potongan ≤1000 lewat `GET /assets/offline-snapshot`. Dulu tiap potongan
memakai `$skip` — MongoDB memindai lalu MEMBUANG `skip` dokumen tiap halaman
(O(skip)), sehingga satu sinkron penuh 10k+ aset ≈ O(n²). Diganti **keyset
pagination**: kursor = `id` item terakhir, halaman berikut cukup `{id > cursor}`
— seek O(log n) via indeks, tanpa buang-hasil.

- **Kursor pada `id` (bukan created_at)** — `id` (UUID) unik & selalu ada
  dijamin indeks unik + tiap jalur tulis; created_at bisa hilang di sebagian
  dok → predikat `$lt` akan MENJATUHKAN baris (kehilangan data senyap di cache).
  Klien order-agnostik (upsert per `id`), jadi urutan `id` tak memengaruhi
  kebenaran. Sort feed diubah ke `{id: 1}`.
- **Indeks baru** `(activity_id, id)` (`snapshot_keyset_activity_id`) melayani
  prefix activity + range/sort `id` tanpa in-memory sort.
- **Respons `next_cursor`** — `id` item terakhir bila halaman penuh, `""` bila
  halaman terakhir. Klien (`offlineSnapshot.js`) melacak `cursor` menggantikan
  `skip += PAGE_LIMIT`; logika delta/tombstone/rekonsiliasi tak berubah.
- **Aman-mundur** — param `skip` lama tetap dihormati (klien belum-terdeploy);
  sort `{id:1}` yang sama membuat jalur skip pun konsisten. Delta (`since`)
  digabung keyset via `$and` sehingga hanya baris berubah yang terkirim.
- **Lingkup sengaja dibatasi** — daftar aset online (`GET /assets`) TETAP
  paginasi nomor halaman (tabel desktop butuh akses acak + total_pages); hanya
  feed snapshot yang di-keyset (aman & bernilai tertinggi).

Verifikasi: smoke FakeDB 6 skenario lulus terhadap handler asli (jahit semua
halaman → setiap `id` tepat sekali tanpa overlap/lompat; baris tanpa created_at
TETAP ikut; delta `since`; kompatibilitas `skip` lama; isolasi activity).
`pytest tests/unit` 638 lulus; eslint + `yarn build` bersih.

---

## [#524] Resolver penanda tangan KPB ter-scope satker (unifikasi lintas modul) — 2026-07-22

Langkah 2 (penutup) perbaikan integritas TTD multi-satker: setelah PR #523
membuat pejabat ber-`kode_satker`, resolver penanda tangan kini **menyaring
kandidat KPB ke satker penerbit dokumen**. Menutup celah di DB multi-satker:
dulu `db.pejabat.find({})` membaca SELURUH pejabat sehingga KPB satker lain
(ber-SK lebih baru) bisa terpilih menandatangani dokumen resmi satker ini.

- **Parameter `kode_satker` opsional** ditambahkan ke resolver bersama —
  `resolve_penandatangan_kpb`, `resolve_pejabat_peran`, `blok_ttd_kpb`,
  `blok_ttd_kpb_titik` (shared_utils), `_penandatangan_kpb` (reports),
  `_kpb_signer` (persediaan). Helper baru `_q_pejabat_satker(kode)` membangun
  query `{"kode_satker": {"$in": [kode, "", None]}}`.
- **Aman-mundur (default-safe)** — `kode_satker` kosong → query kosong = SEMUA
  pejabat (perilaku lama persis). Super-admin/lintas-satker & deployment
  single-satker **tak berubah**. Pejabat era-lama tanpa kode tetap ikut
  (`$in:[kode,"",None]`).
- **Benang satker di seluruh call-site** — satker user penerbit dialirkan ke
  ~20 titik generator dokumen: `reports.py` (9 laporan pembukuan/KIB/pemegang),
  `bast.py`, `lbp.py`, `persediaan.py` (Nota Dinas/BAOF/Posisi/Mutasi/LPB/Kartu
  Barang), `penggunaan.py`, `pemusnahan.py`, `wasdal.py`, `pemeliharaan.py`,
  `mutasi_bmn.py`. Akses dokumen sudah ter-guard per satker, jadi satker user =
  satker dokumen.

Verifikasi: smoke FakeDB 7 skenario lulus (scope 'A' memilih KPB Satker A
walau Satker B ber-SK terbaru; scope '' = perilaku lama; backward-compat
`$in` KPB era-lama; fallback setelan kasatker tetap jalan). `pytest tests/unit`
638 lulus; `compileall` bersih. (Backend-only, tanpa perubahan skema data.)

---

## [#523] Isolasi satker untuk Referensi Pejabat (registry penanda tangan) — 2026-07-22

Langkah 1 dari perbaikan integritas TTD multi-satker (roadmap strategis):
registry `pejabat` kini ber-scope satker seperti pegawai/aset.

- **Field `kode_satker` pada pejabat** — dipaksa dari satker admin saat dibuat
  (super-admin boleh isi eksplisit), seperti pola Master Pegawai (M-SCOPE).
- **Daftar & pejabat-aktif ter-scope** — endpoint `GET /pejabat` &
  `/pejabat/aktif` hanya menampilkan pejabat satker user **+ pejabat era-lama
  tanpa kode** (`$in:[kode,"",None]` — backward-compat penuh; deployment
  single-satker/­data lama tak berubah).
- **Guard ubah/hapus** — `pastikan_akses_dok_satker` menolak (403) mengubah/
  menghapus pejabat milik satker lain.
- **Dedup NIP per-satker** — NIP unik dalam satker (boleh sama antar-satker).

Catatan: resolusi penanda tangan KPB pada laporan **belum** berubah di PR ini
(masih membaca seluruh pejabat) — itu langkah 2 (unifikasi resolver), agar
perubahan berjalur-dokumen-resmi diuji terpisah. Jadi PR ini **tak mengubah
TTD laporan** yang sudah ada.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. (Backend-only.)

---

## [#522] CI jalankan uji frontend + health-check pasca-deploy (anti false-green) — 2026-07-22

Paket CI/CD & keandalan-deploy dari roadmap optimasi:

- **Uji frontend kini jalan di CI.** 11 suite (71 uji: OCC, antrean simpan
  optimistis, guard unload, dll.) sebelumnya tak pernah dieksekusi CI — hanya
  lint + build. Kini ada langkah `yarn test` di job frontend (semua hijau, ~3s).
- **Health-check pasca-deploy di VPS.** `supervisorctl restart` bisa
  mengembalikan sukses walau backend gagal start (import error dsb.) → deploy
  "sukses" padahal situs mati. `scripts/deploy_vps.sh` kini polling
  `/api/health` (no-auth, instan) hingga ~30 dtk setelah restart; bila tak
  sehat, deploy **exit non-zero** (job GAGAL, bukan false-green) + cetak status
  supervisor. URL health dapat di-override lewat `BACKEND_HEALTH_URL`.

Verifikasi: uji frontend 71 lulus lokal; `bash -n` deploy skrip bersih.
(CI/CD & skrip deploy — bukan kode aplikasi.)

---

## [#521] Pengerasan keamanan (hardening cepat berdampak tinggi) — 2026-07-22

Paket keamanan dari roadmap optimasi — perbaikan kecil berisiko-regresi rendah:

- **OTP pakai CSPRNG** (`secrets`, bukan `random`) — OTP dipakai untuk
  verifikasi/reset akun, harus tak-terprediksi.
- **Hash password tak lagi bocor ke klien** — hash bcrypt disimpan di field
  `password`, tetapi proyeksi `require_user`/`require_admin` hanya mengecualikan
  `password_hash` (field tak ada). Kini mengecualikan **`password` + `password_hash`**
  sehingga dokumen user yang dikembalikan tak membawa hash. (Login memakai query
  tersendiri — tak terpengaruh.)
- **OTP tak lagi di subjek email** — subjek dibuat generik; OTP hanya di badan
  (mencegah bocor di pratinjau notifikasi HP/lockscreen).
- **Panjang minimum password admin-set diseragamkan ke ≥8** (sebelumnya 4),
  selaras dengan registrasi.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. (Backend-only.)

---

## [#520] Optimasi: thumbnail foto PIL tak lagi memblokir event loop — 2026-07-22

Paket keandalan-server #3 dari roadmap optimasi:

- Pembuatan thumbnail foto (decode/resize/encode **PIL**, CPU-bound) di jalur
  **tulis aset** (create/update) dan **stream foto** sebelumnya dieksekusi
  langsung di event loop async → memblokir SEMUA request lain selama proses.
- Kini di-offload ke **thread** via `asyncio.to_thread` (PIL melepas GIL) di
  titik terpanas: `process_photos_for_storage` (per-foto, dipakai setiap
  create/update), thumbnail sampul pada create & update, dan fallback thumbnail
  on-the-fly pada endpoint stream foto legacy. Event loop tetap responsif saat
  banyak foto diproses.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. (Backend-only.)

---

## [#519] Optimasi: ekspor XLSX/PDF berfoto tak lagi berisiko meng-OOM server — 2026-07-22

Paket keandalan-server #2 dari roadmap optimasi:

- **Cap ambang aset untuk ekspor berfoto** (`MAX_FOTO_EXPORT_ASSETS = 5000`).
  Ekspor Excel (embed gambar) & PDF (thumbnail) merakit seluruh dokumen + semua
  bytes gambar di RAM secara sinkron sampai selesai — tanpa batas, ribuan aset
  berfoto bisa **meng-OOM & meng-crash backend** (dampak lintas-pengguna). Di
  atas ambang, ekspor ditolak dengan pesan jelas → arahkan ke **Ekspor CSV**
  (streaming, ringan) atau persempit filter/kegiatan.
- **XLSX `in_memory=False`** — xlsxwriter kini merakit arsip di berkas temp
  disk, bukan RAM, menekan puncak memori saat menyisipkan banyak gambar.

Verifikasi: `pytest tests/unit` 638 lulus; `compileall` bersih. (Backend-only.)

---

## [#518] Optimasi keandalan backup/restore (ketahanan memori & disk) — 2026-07-22

Paket keandalan-server #1 dari roadmap optimasi (mencegah OOM/disk penuh yang
berdampak seluruh aplikasi):

- **Restore streaming ke disk (per-chunk 1 MB)** — sebelumnya seluruh ZIP
  unggahan (bisa ratusan MB–GB berisi foto GridFS) dimuat ke RAM dulu
  (`file.read()`) → vektor OOM di VPS kecil. Kini ditulis per-chunk.
- **Guard ruang disk sebelum backup** — perkirakan kebutuhan dari total byte
  GridFS + margin; batalkan lebih awal dengan pesan jelas bila ruang tak cukup,
  agar backup tak memenuhi disk server.
- **Retensi arsip hanya saat backup SUKSES** — backup otomatis tak lagi
  memangkas arsip lama bila backup baru gagal (mis. disk penuh), sehingga
  cadangan valid tidak hilang.

Verifikasi: `pytest tests/unit` 638 lulus; backend `compileall` bersih.
(Backend-only.)

---

## [#517] Perbaikan tuntas: peta TIDAK berpindah/zoom saat seleksi (semua kasus) — 2026-07-22

Lanjutan [#516] yang belum menuntaskan: peta masih **terlempar ke zoom terjauh**
saat menyalakan/mematikan Mode Seleksi atau memilih pin. Akar masalah: peta
melakukan `fitBounds` setiap kali penanda `didFitRef` di-reset — dan reset itu
masih terpicu saat **mematikan** Mode Seleksi (efek `hasSelection` dgn
`selectMode` sudah false → reset → refit ke subset terpilih), serta berpotensi
saat data di-`load` ulang.

- **Perbaikan**: auto-`fitBounds` kini HANYA saat **peta pertama dibuka**
  (`firstLoadRef`). Perubahan seleksi (berapa pun), menyalakan/mematikan Mode
  Seleksi, dan reload data **tidak lagi memindah** posisi/zoom peta — tetap di
  posisi terakhir.
- Efek refit berbasis `hasSelection` dihapus.
- Refit tetap tersedia lewat aksi eksplisit: ganti filter **Barang Serupa** &
  tombol **Muat Ulang**.

Verifikasi: `yarn lint` bersih; `CI=false yarn build` sukses. (Frontend-only.)

---

## [#516] Perbaikan: memilih pin pertama di Mode Seleksi melempar view menjauh — 2026-07-22

- Saat memilih **pin pertama** di Mode Seleksi (jumlah terpilih 0→1), peta
  ikut **fit-bounds ulang** ke seluruh pin → view/zoom **terlempar menjauh**.
- Penyebab: penanda `didFitRef` di-reset tiap `hasSelection` berubah (dirancang
  untuk perilaku "seleksi daftar menyaring peta"), sehingga di dalam Mode
  Seleksi pemilihan pin pertama memicu fit-bounds.
- **Perbaikan**: reset fit-bounds **dilewati saat Mode Seleksi aktif** — posisi
  & zoom peta tetap saat memilih pin. Refit tetap berlaku untuk aksi
  pengguna lain (ganti filter Barang Serupa, Muat Ulang).

Verifikasi: `yarn lint` bersih; `CI=false yarn build` sukses. (Frontend-only.)

---

## [#515] Perbaikan (akar masalah): basemap putih & hanya marker saat Mode Seleksi — 2026-07-22

Akar masalah sebenarnya dari basemap hilang saat Mode Seleksi (lanjutan
[#514]): elemen **kanvas Leaflet** diberi `className` dinamis
(`cursor-crosshair` saat mode aktif). Leaflet menambahkan kelasnya sendiri
(`.leaflet-container`, `.leaflet-fade-anim`, dst.) ke elemen yang SAMA setelah
inisialisasi. Saat mode berganti, React **menulis ulang seluruh atribut
`className`** sehingga **menimpa/menghapus kelas Leaflet** → styling basemap
lenyap (peta putih), sementara panel marker (absolut) tetap tampil.

- **Perbaikan**: `className` kanvas dibuat **konstan** kembali; kursor
  crosshair disetel lewat **ref** (`style.cursor`) tanpa menyentuh daftar
  kelas, jadi kelas Leaflet tak pernah tertimpa.
- `invalidateSize` saat mode berganti tetap dipertahankan sebagai pengaman
  terhadap pergeseran tata letak.

Verifikasi: `yarn lint` bersih; `CI=false yarn build` sukses. (Frontend-only.)

---

## [#514] Perbaikan: basemap peta hilang saat Mode Seleksi aktif — 2026-07-22

- Saat Mode Seleksi (atau "Pilih Area") dinyalakan, **bilah seleksi muncul di
  atas peta** sehingga kanvas Leaflet bergeser & lebarnya berubah (scrollbar).
  Tanpa `invalidateSize`, ukuran ubin jadi basi → **basemap (peta dasar) hilang**.
- Kini peta **menghitung ulang ukuran** (`invalidateSize`) tiap kali Mode
  Seleksi / Pilih Area berubah — setelah tata letak mengendap (rAF + fallback
  timeout) — sehingga basemap tetap tampil.

Verifikasi: `yarn lint` bersih; `CI=false yarn build` sukses. (Frontend-only.)

---

## [#513] Peta Aset — Mode Seleksi marker → terhubung ke daftar & Edit Massal — 2026-07-22

Menambahkan **seleksi marker di peta** yang menyatu dengan seleksi daftar,
sehingga aset yang dipilih di peta bisa langsung **Edit Massal**.

- **Tombol "Mode Seleksi"** di toolbar peta (PC & HP). Saat aktif, peta
  menampilkan SEMUA pin (bukan hanya yang terpilih) dan pin terpilih ditandai
  **cincin oranye + centang**.
- **Cara memilih:**
  - **PC:** klik pin = pilih/lepas; **Shift + seret** = kotak seleksi
    (*rubber-band*) → semua pin di dalam kotak terpilih.
  - **HP:** ketuk pin = pilih/lepas; tombol **"Pilih Area"** lalu seret satu
    jari untuk menggambar kotak (pan peta nonaktif selama menggambar).
  - *(Klik/tekan-lama untuk "+ Tambah titik" tetap seperti semula di luar
    mode seleksi.)*
- **Bilah seleksi**: jumlah terpilih · **Pilih Semua (terlihat)** ·
  **Kosongkan** · **Edit Massal (N)**.
- **Terhubung ke daftar**: peta & daftar berbagi satu himpunan terpilih
  (kunci = `id` aset). Memilih di peta otomatis mencentang aset yang sama di
  daftar; **Edit Massal (N)** menutup peta dan membuka panel Edit Massal untuk
  aset-aset itu. Hanya untuk peran ber-izin ubah.

Verifikasi: `yarn lint` bersih (AssetMapFullView 0 peringatan);
`CI=false yarn build` sukses. (Frontend-only.)

---

## [#512] Reset "Hapus Semua" — pertahankan foto asli & spesimen TTD (anti-yatim) — 2026-07-22

Audit backup/restore/reset agar **sesuai fitur terkini**. Arsitekturnya sudah
**dinamis** (daftar koleksi dienumerasi dari DB), sehingga field baru pada
koleksi yang ada — mis. `cara_bayar_kontrak` (aset) dan `status_pegawai_satker`
(pegawai) — **otomatis** ikut ter-backup/restore/reset tanpa perubahan. Yang
ditemukan & diperbaiki adalah celah pada **reset**:

- **Reset kini mempertahankan GridFS yang tertaut koleksi yang dipertahankan.**
  Sebelumnya reset hanya menyelamatkan foto pegawai (krop). Padahal koleksi
  `pegawai` & `pejabat` **dipertahankan** saat reset, sedangkan berkas berikut
  ikut terhapus → referensi **yatim**:
  - **Foto pegawai asli** (`foto_asli_file_id`, untuk atur-ulang posisi foto),
  - **Spesimen tanda tangan** (`ttd_file_id`) pegawai & pejabat.
  Kini ketiganya (foto krop + foto asli + spesimen TTD) selamat dari reset;
  berkas operasional (foto aset, dokumen/e-sign) tetap terhapus sebagaimana
  mestinya.
- Kebijakan penanda GridFS dipindah ke modul murni `backup_utils`
  (`gridfs_dipertahankan_saat_reset`) + **uji unit anti-drift**.
- Versi format backup dinaikkan **3.4.0 → 3.5.0** (backup/restore tetap
  mencakup SELURUH GridFS — tak berubah).

Verifikasi: `pytest tests/unit` 638 lulus.

---

## [#511] Master Pegawai — Referensi Status Pegawai (SIMPEG) + kategori Pendidikan Terakhir — 2026-07-22

- **Field baru "Status Pegawai (Satker)"** pada tab Kepegawaian — dropdown
  **REFERENSI SIMPEG**: PNS · Calon Pegawai (CPNS) · Diperbantukan Pada ·
  Perbantuan Dari · Dipekerjakan Pada · Dipekerjakan Dari · Non Aktif ·
  Pejabat Negara · Diperbantukan ke Swasta. Ini **sumbu hubungan kerja**,
  terpisah dari status keberadaan.
- **Input berjenjang**: bila status merujuk instansi lain (perbantuan/
  dipekerjakan/ke swasta), muncul isian pelengkap **"Instansi/Satker
  Terkait"** (asal/tujuan). Field pelengkap dikosongkan otomatis bila status
  tak memerlukannya.
- **Klarifikasi label**: field lama "Status di Satker" (Aktif/Cuti/Pensiun/…)
  di-rename menjadi **"Status Keberadaan"** agar tak rancu dengan Status
  Pegawai — logika lifecycle (badge pensiun/mutasi, hitung masa) tak berubah.
- **Pendidikan Terakhir jadi kategori**: dropdown baku dari **REFERENSI
  PENDIDIKAN** (SD · SMP · SMU · Diploma I–IV · S1 · S2 · S3 · Profesor).
  Nilai lama bebas tetap dipertahankan sebagai opsi agar tak hilang saat edit.
- **Impor/Ekspor Excel**: kolom baru **"Status Pegawai"** (dengan Data
  Validation) + dropdown **"Pendidikan Terakhir"**; round-trip impor↔ekspor
  terjaga (uji unit).

Verifikasi: `pytest tests/unit` 637 lulus (termasuk round-trip pegawai baru);
`yarn lint` bersih; `CI=false yarn build` sukses.

---

## [#510] Aset — field "Cara Bayar Kontrak" di bagian Pengadaan — 2026-07-22

- **Field skalar baru `cara_bayar_kontrak`** ditambahkan lewat registry
  (`asset_fields.py`, `batchable=True`) — otomatis mengalir ke proyeksi list,
  PATCH, batch, ekspor CSV, impor, dan audit. Turunan manual ikut disesuaikan:
  `models.py` (AssetCreate/AssetResponse), header & kolom ekspor XLSX
  (`exports.py`), dan skema template impor (`templates.py`, dengan dropdown).
- **Dropdown "Cara Bayar Kontrak"** muncul tepat di bawah **Nomor Kontrak**
  pada bagian **Pengadaan** form aset (tambah maupun edit) — pilihan
  **Sekaligus** / **Bertahap (Termin)**, boleh dikosongkan.
- **Edit massal (Batch):** field ini juga tersedia sebagai dropdown di panel
  "Administrasi Perolehan" (dekat Nomor Kontrak), lengkap dengan opsi hapus.
- **Snapshot offline & label audit** diperbarui agar field ikut tersimpan di
  IndexedDB dan tampil dengan nama ramah pada Log Perubahan.

Verifikasi: `pytest tests/unit` 636 lulus (termasuk anti-drift registry);
`yarn lint` bersih; `CI=false yarn build` sukses.

---

## [#509] Master Pegawai — hapus "Rekap per Unit Kerja" + toolbar HP lebih lega — 2026-07-22

- **Panel "Rekap per Unit Kerja" dihapus** (redundan dengan **Struktur
  Organisasi** yang sudah menyajikan jumlah per unit) — beserta state &
  pemanggilan `rekap-unit` di frontend.
- **Toolbar HP: kolom pencarian lebih lebar.** Di layar HP (<sm) semua tombol
  aksi sekunder (Struktur, Unduh Template, Ekspor Excel, Impor) **dikelompokkan
  ke satu menu ⋮**; tombol **Tambah Pegawai** tetap tampil terpisah. Di tablet/
  desktop (≥sm) tombol tetap sebaris seperti semula.

Verifikasi: `yarn lint` bersih; `CI=false yarn build` sukses. (Frontend-only;
endpoint `rekap-unit` tetap ada untuk kompatibilitas namun tak lagi dipakai UI.)

---

## [#508] Gelar akademik pada tanda tangan laporan — saklar per pejabat — 2026-07-22

Kadang pimpinan ingin mencantumkan gelar akademik pada tanda tangan dokumen,
kadang tidak. Kini mudah diatur di **Referensi Pejabat**:

- Field **Gelar Depan** & **Gelar Belakang** (terpisah dari nama) + saklar
  **"Cantumkan gelar pada nama di TTD laporan"** pada tiap pejabat.
- Bila aktif, nama penanda tangan disusun **"Gelar Depan Nama, Gelar Belakang"**
  (mis. *Dr. Andi Wijaya, M.M.*) pada **seluruh laporan yang penanda tangannya
  bersumber Referensi Pejabat** (KIR, Posisi BMN, Penyusutan, LBKP, LKB, CaLBMN,
  Daftar Pemegang, BAST, Nota Dinas/BA Persediaan, LPB, LBP). Nonaktif → nama
  polos.
- **Aman untuk data lama**: gelar kosong → nama apa adanya (tanpa perubahan);
  helper murni `komposisi_nama_gelar` (idempoten). Pada laporan **per-kegiatan**
  (BA/RHI/SPTJM/Koreksi/DBKP/DBHI) nama kasatker tetap bebas-teks per kegiatan
  (sudah bisa diketik dengan/atau tanpa gelar sesuai kebutuhan).

Verifikasi: 636 unit test lulus (+2 baru); smoke render Posisi BMN menampilkan
"Dr. Andi Wijaya, M.M." pada TTD; smoke Non-ASN & Plt tanpa regresi;
`yarn lint` bersih; `yarn build` sukses.

---

## [#507] Master Pegawai — foto berbasis ikon + pratinjau ukuran penuh + tabel lebih padat — 2026-07-22

Penyempurnaan UI Master Pegawai (umpan balik pemilik):

- **Kontrol foto jadi ikon** (fokus pada foto): tombol teks "Ganti/Atur Ulang/Hapus"
  diganti tombol **ikon** ringkas — ganti foto (ImagePlus), atur ulang posisi
  (Crop), hapus foto (Trash2). Foto ditampilkan lebih besar sebagai fokus.
- **Klik foto → pratinjau ukuran penuh** memakai **berkas asli** yang diunggah
  (endpoint `foto-asli`; jatuh ke versi krop untuk foto lama) — berlaku di
  **baris daftar** (kartu HP & tabel desktop) **dan** popup form identitas.
- **Tabel tablet/desktop lebih padat**: padding sel & header dirapatkan agar
  informasi pegawai tampil lebih ringkas.

Verifikasi: `yarn lint` 0 error; `CI=false yarn build` sukses. (Frontend-only.)

---

## [#506] Transparansi BAST usang (reklasifikasi/ganti nama) + masa kerja jabatan (TMT) — 2026-07-22

Dua penyempurnaan siklus aset↔pegawai (lanjutan diskusi alur):

**B — Badge "BAST usang".** Saat aset direklasifikasi (kode berubah) atau namanya
disesuaikan **setelah BAST terakhir dilampirkan**, sistem kini menandainya agar
operator sadar BAST tersimpan merujuk **data lama** (BAST historis tetap sah;
terbitkan BAST baru bila perlu).
- Saat BAST dilampirkan (baik dari bukti TTD modul Penggunaan maupun unggah
  manual di form aset), **kode+nama di-snapshot** (`bast_snapshot`).
- Helper murni `bast_perlu_perbarui(asset)` → True bila kode/nama **sekarang**
  berbeda dari snapshot. Aset ber-BAST **era lama tanpa snapshot TIDAK ditandai**
  (konservatif, tanpa positif palsu).
- Badge **"BAST usang"** (amber) pada dialog *Aset Dipegang* (Master Pegawai) &
  peringatan pada blok BAST di **form aset**. Snapshot ikut backup/restore.

**C — Masa kerja dalam jabatan (TMT).** Kolom TMT Jabatan kini produktif:
`info_masa_pegawai` menghitung **"Menjabat N tahun M bulan"** dari **TMT Jabatan
→ hari ini** (helper murni `durasi_terbilang`), tampil di kolom *Masa* daftar
pegawai. Melengkapi *Akhir Periode Jabatan* (pasangan mulai↔selesai).

Verifikasi: 634 unit test lulus (+3 baru: `durasi_terbilang`, masa jabatan,
`bast_perlu_perbarui`/`snapshot_bast`); `yarn lint` bersih (0 error);
`yarn build` sukses.

---

## [#505] Sinkronisasi data pemegang ke aset — dari Master Pegawai — 2026-07-22

Menutup celah **data pemegang basi** pada aset saat identitas pegawai berubah
(kenaikan pangkat, perpindahan unit, penyesuaian nama). Kaitan aset↔pegawai
lewat **NIP (stabil)**, jadi kepemilikan tak pernah putus — tetapi *snapshot*
nama/jabatan/unit yang tercatat pada aset (dipakai DBR/KIR/BAST) bisa tertinggal.

- **Tombol "Sinkronkan data ke aset yang dipegang"** di form pegawai (tab
  Jabatan & Unit) + **tawaran otomatis** setelah menyimpan pegawai yang
  identitasnya berubah & masih memegang aset. Menyegarkan `user`/
  `pengguna_jabatan`/`pengguna_melekat_ke` pada **aset AKTIF** yang dipegang
  (match NIP, ter-scope satker).
- **BAST yang sudah terbit TIDAK diubah** (dokumen historis) — hanya data untuk
  dokumen **berikutnya**. **Idempoten** (hanya menimpa field yang berbeda; data
  master kosong tidak menghapus snapshot lama); versi aset dinaikkan; jejak audit.
- Endpoint: `POST …/pegawai/{id}/sinkron-aset` (terapkan) & `GET …/pegawai/{id}/
  sinkron-aset/pratinjau` (periksa tanpa menulis). Respons PUT pegawai membawa
  `sinkron_aset` (jumlah aset & yang perlu disegarkan) bila identitas berubah.
- Helper murni `snapshot_pemegang_aset` & `beda_snapshot_pemegang` (teruji unit;
  nama dibandingkan ternormalkan agar beda spasi/kapital tidak memicu perubahan).

Verifikasi: 631 unit test lulus (+2 baru); smoke integrasi (FakeDB): 2 aset
disegarkan, BAST utuh, versi naik, idempoten, aset NIP-lain & terhapus tak
tersentuh; eslint bersih; `yarn build` sukses.

---

## [#504] Foto pegawai — disimpan bersama form (bukan langsung) + atur ulang posisi — 2026-07-22

Dua perbaikan alur foto Master Pegawai (umpan balik pemilik):

- **Foto tidak lagi langsung terunggah** saat klik "Pakai Foto Ini". Baik saat
  **tambah maupun edit**, foto hasil krop kini **ditahan** (pratinjau lingkaran
  + label "Foto siap — klik Simpan") dan **baru diunggah saat tombol Simpan
  form ditekan**. Menutup form/Batal = foto tidak jadi tersimpan (sebelumnya
  mode edit langsung menimpa foto lama begitu krop dipilih).
- **Atur Ulang Posisi** — tombol baru untuk **reposisi foto tersimpan tanpa
  memilih berkas lagi**. Sistem kini menyimpan **foto ASLI** (dikecilkan ≤1600px,
  hemat penyimpanan) + **parameter krop** (zoom/posisi); dialog krop dibuka
  kembali dengan posisi terakhir sebagai titik awal. Foto lama (sebelum fitur
  ini) yang belum punya berkas asli → jatuh ke "pilih ulang foto".

Teknis: `POST …/pegawai/{id}/foto` menerima opsional `file_asli` (asli, dikecilkan
via Pillow) + `krop` (JSON); endpoint baru `GET …/pegawai/{id}/foto-asli`; hapus
foto ikut membersihkan berkas asli + parameter krop. `KropFotoDialog` menerima
`initial` (seed posisi) & mengembalikan parameter krop. Semua foto (asli+krop)
otomatis tercakup backup/restore GridFS.

Verifikasi: 629 unit test lulus; `_kecilkan_foto_asli` terverifikasi
(3000×2000→1600px, flatten RGBA→putih); eslint bersih; `yarn build` sukses.

---

## [#503] Master Pegawai — rangkap jabatan struktural Plt/Plh pada roster — 2026-07-22

Melengkapi #502 di sisi **Master Pegawai**: roster pegawai kini dapat mencatat
bahwa seorang pegawai memegang **rangkap jabatan struktural sementara** sebagai
**Plt. (Pelaksana Tugas)** / **Plh. (Pelaksana Harian)** atas jabatan lain —
selain jabatan definitifnya sendiri.

- **Field baru** `jenis_pelaksana` (`""`/`plt`/`plh`) + `jabatan_pelaksana`
  (jabatan yang di-Plt/Plh-kan) pada model pegawai + validasi. Jabatan definitif
  tetap di field `jabatan`.
- **Form pegawai (tab "Jabatan & Unit")**: dropdown "Rangkap Jabatan Struktural
  (Plt/Plh)" + input jabatan yang di-Plt/Plh-kan (muncul bila dipilih) +
  penjelasan efek naskah dinas.
- **Daftar pegawai**: badge/label **Plt./Plh. [jabatan]** pada baris (kartu HP &
  tabel desktop); pencarian ikut menjangkau jabatan pelaksana.
- **Impor/Ekspor Excel**: dua kolom baru **"Jenis Pelaksana (Plt/Plh)"** &
  **"Jabatan Pelaksana (Rangkap)"** (dengan dropdown Plt./Plh.) — **round-trip
  aman** (ekspor → edit → impor kembali). Normalisasi impor mengenali
  "Plt/Plt./Pelaksana Tugas" & "Plh/Plh./Pelaksana Harian".
- Helper murni `rangkap_jabatan_pelaksana(pegawai)` → "Plt./Plh. [jabatan]".

Verifikasi: 629 unit test lulus (+4 baru: rangkap jabatan, validasi,
normalisasi, round-trip ekspor/impor); eslint bersih; `yarn build` sukses.

---

## [#502] Rangkap jabatan struktural Plt/Plh pada Referensi Pejabat — tanda tangan dokumen "Plt./Plh." — 2026-07-22

Referensi Pejabat kini mengakomodir **rangkap jabatan struktural sementara**:
seorang pejabat dapat ditetapkan sebagai **Plt. (Pelaksana Tugas)** atau **Plh.
(Pelaksana Harian)** atas suatu jabatan. Bila **Kuasa Pengguna Barang (KPB)**
dijabat oleh Plt/Plh, seluruh dokumen resmi satker-wide otomatis menuliskan
awalan **"Plt./Plh."** di depan jabatan pada blok tanda tangan, dengan **nama &
NIP pejabat pelaksana itu sendiri** (kaidah naskah dinas).

- **Field baru `jenis_pelaksana`** (`""`/`plt`/`plh`) pada registry pejabat +
  validasi + endpoint referensi. Dasar: UU 30/2014 (mandat), SE Kepala BKN
  2/SE/VII/2019 jo. 1/SE/2021 (kewenangan Plt/Plh). Masa berlaku Plt/Plh
  mengikuti rentang SK pejabat yang sudah ada (berakhir otomatis).
- **`pejabat_utils.penandatangan_kpb`** kini mengembalikan `jenis_pelaksana` +
  `jabatan_dasar` dan memberi awalan "Plt./Plh." pada `jabatan` (helper murni
  `prefiks_jabatan_pelaksana` / `prefiks_pelaksana`, idempoten & aman kosong).
- **Mengalir ke semua blok TTD KPB yang bersumber registry**: Posisi BMN,
  Penyusutan, LBKP, LKB, CaLBMN, KIR, Daftar Pemegang Aset (PDF **dan** Word),
  Nota Dinas/Opname/BA Persediaan, LPB, LBP, serta "Mengetahui" pada BAST
  (`bast.py` memakai `kpb["jabatan"]`).
- **Frontend PejabatPage**: dropdown "Rangkap Jabatan Struktural (Plt/Plh)" +
  penjelasan efek TTD, badge **Plt./Plh.** di baris daftar, dan jabatan
  ber-awalan pada tampilan.
- Laporan **per-kegiatan** (BA, RHI, SPTJM, Surat Koreksi, DBKP, DBHI) tetap
  memakai penanda tangan kasatker kegiatan (field jabatan bebas) — "Plt./Plh."
  cukup diketik pada jabatan kasatker kegiatan bila diperlukan.

Verifikasi: 625 unit test lulus (+5 baru untuk prefiks/validasi/penandatangan);
smoke render Posisi BMN, LKB, KIR, Daftar Pemegang (PDF+Word) menampilkan "Plt.
Kuasa Pengguna Barang"; smoke Non-ASN & LBP tanpa regresi; eslint bersih;
`yarn build` sukses.

---

## [#500] Versi Word (.docx): DBHI (8 tipe) & DBKP — rollout Word SELURUH laporan LHI tuntas — 2026-07-22

Penutup rollout Word (#495–#499). **DBHI** (Daftar Barang Hasil Inventarisasi,
8 tipe kondisi) dan **DBKP** (Daftar Barang Kuasa Pengguna per golongan) kini
tersedia dalam `.docx` editable — **menuntaskan versi Word untuk SELURUH
laporan inti LHI**.

- Endpoint **`…/dbhi/{tipe}/docx`** (8 tipe: baik/rusak ringan/rusak berat/
  berlebih/tidak-ditemukan/kesalahan-pencatatan/tidak-ditemukan-lainnya/
  sengketa) & **`…/dbkp-docx`** — **landscape**, kolom identik versi PDF; Kode
  Barang tetap 2 baris (kode + Sub-sub Kelompok); tanda tangan Kuasa Pengguna
  Barang (patuh Non-ASN). DBKP memakai `build_dbkp_rows` (intra/ekstra, ambang
  PMK 181) — sama dengan PDF.
- `docx_utils.doc_baru` menerima `landscape=True` (tabel lebar).
- Frontend: baris **"Versi Word (.docx)"** per kondisi di bawah grid DBHI; DBKP
  ikut baris Word grup Laporan Resmi.

### Status rollout Word — SELESAI

| Grup | Laporan | Word |
|---|---|---|
| Dokumen Pendukung | BA, SPTJM, Surat Koreksi, Daftar Pemegang | ✅ |
| Laporan Resmi | RHI, BAHI, SP Hasil, SP Pelaksanaan | ✅ |
| Tabular | DBHI (8 tipe), DBKP | ✅ |

Seluruh `.docx` memakai fondasi `docx_utils`/`ba_utils` bersama, isi identik
versi PDF, dan mematuhi aturan Non-ASN pada area tanda tangan.

Verifikasi: 620 unit test lulus; smoke render 8 DBHI + DBKP `.docx` OK; eslint
bersih; `yarn build` sukses.

---

## [#499] Versi Word (.docx): SP Hasil & SP Pelaksanaan — Laporan Resmi lengkap — 2026-07-22

Lanjutan rollout Word (#495–#498). **Surat Pernyataan Hasil Inventarisasi** &
**Surat Pernyataan Pelaksanaan Inventarisasi** kini tersedia dalam `.docx`
editable — **melengkapi seluruh grup Laporan Resmi** (RHI, BAHI, SP Hasil,
SP Pelaksanaan) dengan versi Word.

- Endpoint **`…/sp-hasil-docx`** & **`…/sp-pelaksanaan-docx`** — identitas KPB,
  butir pernyataan (isi identik versi PDF), klausul tanggung jawab, tanda
  tangan Kuasa Pengguna Barang (jabatan di bawah nama; patuh Non-ASN). Kerangka
  dipakai bersama (`_docx_surat_pernyataan_inv`).
- `docx_utils.signature_single` menerima `jabatan_bawah` (jabatan dicetak di
  bawah nama, di atas NIP) — kaidah surat pernyataan.
- Frontend: tombol Word SP Hasil & SP Pelaksanaan di baris "Versi Word" grup
  Laporan Resmi.

Status rollout: **Dokumen Pendukung ✅ · Laporan Resmi ✅** · sisa DBHI (8 tipe)
& DBKP ⏭️.

Verifikasi: 620 unit test lulus; smoke render SP Hasil & SP Pelaksanaan `.docx`
OK; eslint bersih; `yarn build` sukses.

---

## [#498] Versi Word (.docx): RHI & BAHI — 2026-07-22

Lanjutan rollout Word (#495–#497). **RHI** (Rekapitulasi Hasil Inventarisasi)
dan **BAHI** (Berita Acara Hasil Inventarisasi) kini tersedia dalam `.docx`
editable, memakai fondasi `docx_utils` yang sama.

- **`…/rhi-docx`**: tabel rekap A–E (Ditemukan/Baik/Rusak Ringan/Rusak Berat,
  Tidak Ditemukan + klasifikasi, Berlebih, Sengketa, Belum Diinventarisasi) +
  total; tanda tangan Kuasa Pengguna Barang.
- **`…/bahi-docx`**: narasi tanggal + identitas KPB + ringkasan hasil (butir
  bernomor + sub a/b/c) + daftar lampiran LHI + penutup; **penanda tangan =
  Tim Pelaksana Inventarisasi** (min. 3, ketua ditandai) **disahkan Kuasa
  Pengguna Barang** (kaidah BAHI) + tembusan; patuh aturan Non-ASN.
- Frontend: baris **“Versi Word (.docx): RHI · BAHI”** di bawah grid Laporan
  Resmi pada rekapitulasi.

Status rollout: Dokumen Pendukung ✅ · Laporan Resmi (RHI, BAHI ✅ · SP Hasil,
SP Pelaksanaan ⏭️) · DBHI & DBKP ⏭️.

Verifikasi: 620 unit test lulus; smoke render RHI & BAHI `.docx` (isi + tanda
tangan) OK; eslint bersih; `yarn build` sukses.

---

## [#497] Versi Word (.docx): Daftar Pemegang Aset — grup Dokumen Pendukung lengkap — 2026-07-22

Lanjutan rollout Word (#495, #496). **Daftar Pemegang Aset** kini tersedia
dalam `.docx` editable — melengkapi **seluruh grup Dokumen Pendukung**
(BA Tidak Ditemukan, SPTJM, Surat Koreksi, Daftar Pemegang) dengan versi Word.

- Endpoint **`…/daftar-pemegang-docx`**: info kegiatan, rekap per pemegang
  (Tabel A), rincian aset per pemegang (Tabel B), tanda tangan Kuasa Pengguna
  Barang (KPB per tanggal hari ini — filter SK kedaluwarsa; patuh Non-ASN).
  Data digrup memakai `penggunaan_utils.rekap_pemegang` — sama dengan versi
  PDF & halaman Aset per Pemegang.
- Tombol **“Word”** kini juga di Daftar Pemegang Aset pada rekapitulasi.

Berikutnya: RHI, BAHI, SP Hasil/Pelaksanaan, lalu DBHI (8 tipe) & DBKP.

Verifikasi: 620 unit test lulus; smoke render Daftar Pemegang `.docx` OK;
eslint bersih; `yarn build` sukses.

---

## [#496] Versi Word (.docx): SPTJM & Surat Koreksi Pencatatan — 2026-07-22

Lanjutan rollout Word editable (setelah BA, #495). SPTJM dan Surat Pernyataan
Koreksi Pencatatan kini tersedia dalam **.docx** yang bisa disunting sebelum
ditandatangani, memakai fondasi `docx_utils` yang sama.

- Endpoint baru **`…/sptjm-docx`** dan **`…/surat-koreksi-docx`** — konten
  (identitas KPB, narasi pernyataan, lampiran rincian, tempat/tanggal) &
  kaidah tanda tangan **identik** versi PDF; data ringkas dibangun sekali di
  `_konten_surat_pernyataan`.
- `docx_utils`: helper baru **`signature_single`** (tanda tangan tunggal Kuasa
  Pengguna Barang, patuh aturan Non-ASN/NIK) + **`identity_block`**; `_sig_cell`
  kini mendukung baris "Dibuat di/Pada tanggal" di atas header.
- Tombol **“Word”** kini juga muncul di SPTJM & Surat Koreksi pada rekapitulasi
  inventarisasi (grup Dokumen Pendukung).

Berikutnya menyusul: Daftar Pemegang Aset, RHI, BAHI, SP Hasil/Pelaksanaan,
lalu DBHI & DBKP.

Verifikasi: 620 unit test lulus; smoke render SPTJM & Surat Koreksi `.docx`
memverifikasi isi & tanda tangan; eslint bersih; `yarn build` sukses.

---

## [#495] Berita Acara BMN Tidak Ditemukan lebih detail + versi Word (.docx) — 2026-07-22

Penyempurnaan format Berita Acara BMN Tidak Ditemukan sesuai kaidah
penatausahaan BMN (riset praktik DJKN/Kemenkeu & SE PUPR 10/2023), plus
penyediaan versi **Word (.docx) yang bisa disunting** — fondasi untuk versi
Word laporan lain menyusul.

### Berita Acara Hasil Penelitian — format & penanda tangan

- Judul diselaraskan: **“BERITA ACARA HASIL PENELITIAN — BARANG MILIK NEGARA
  (BMN) TIDAK DITEMUKAN”**; pembuka menyebut Tim Internal Penelitian yang
  dibentuk berdasarkan Surat Tugas/Keputusan Kuasa Pengguna Barang.
- **Penanda tangan diperbaiki** (fokus permintaan): yang menandatangani
  adalah **Tim Internal Penelitian** (Tim Inti + Pembantu, Ketua ditandai,
  min. 3 orang) — bukan tim peneliti eksternal seperti sebelumnya —
  diketahui/disahkan **Kuasa Pengguna Barang** di tengah bawah, dengan
  tambahan blok **Saksi** (opsional). Aturan Non-ASN/NIK tetap: NIP/NIK tidak
  dicetak di area tanda tangan.
- Bagian baru agar lebih lengkap: **DASAR** (rujukan PP 27/2014 jo. 28/2020,
  PMK penatausahaan/181/2016, PMK 83/2016 penghapusan, PMK 118/2017 &
  S-115/KN/2017), **METODE PENELITIAN** (penelitian dokumen + peninjauan
  lapangan), **KESIMPULAN & REKOMENDASI TINDAK LANJUT** yang otomatis
  memilah per klasifikasi — *Kesalahan Pencatatan → koreksi pencatatan*;
  *benar hilang → usul penghapusan + SPTJM + Surat Keterangan Kepolisian/
  Inspektorat, bila lalai → TGR* — dan **DOKUMEN PENDUKUNG**.
- Konten baku dipisah ke `ba_utils.py` (fungsi murni, ber-unit test) sebagai
  SATU sumber kebenaran naskah untuk PDF dan Word.

### Versi Word (.docx) editable

- Modul bersama baru **`docx_utils.py`** (kop surat, blok judul, tabel data
  bergaris, blok tanda tangan tim + KPB + saksi mematuhi aturan Non-ASN,
  tembusan, nomor halaman) — mencerminkan sistem desain laporan PDF.
- Endpoint **`GET …/berita-acara-docx`** menghasilkan `.docx` dengan konten &
  kaidah penanda tangan **identik** PDF (satu sumber data). Tombol **“Word”**
  di samping tombol BA Tidak Ditemukan pada rekapitulasi inventarisasi.
- Ini fondasi: versi Word untuk laporan lain akan menyusul memakai
  `docx_utils` yang sama.

Verifikasi: 620 unit test lulus (+4 `ba_utils`); smoke render BA **PDF & DOCX**
memverifikasi seluruh bagian resmi, penanda tangan Tim Internal, rekomendasi
per klasifikasi, dan aturan Non-ASN; eslint bersih; `yarn build` sukses.

---

## [#494] Hub Pelaporan: tombol "Kop/Sampul" inline dihapus (redundan) — 2026-07-22

Lanjutan konsolidasi setelan kop/sampul (#493). Tombol admin "Kop/Sampul"
di header **Arsip Pelaporan** (hub Pelaporan) membuka editor `ReportSettingsEditor`
inline yang identik dengan halaman **Pengaturan → Universal** — jadi redundan.

Dihapus dari `PelaporanPage.jsx`: tombol "Kop/Sampul", render editor inline,
state `bukaSampul`, import `ReportSettingsEditor`, dan ikon `Settings` yang
tak lagi terpakai. **Tanpa data-loss** — seluruh setelan kop/sampul tetap
diedit di Pengaturan → Universal (yang meng-*embed* komponen yang sama;
komponen dipertahankan). Toolbar header tinggal Reklasifikasi + Booking
Nomor, tetap seimbang di HP/tablet/desktop.

Verifikasi: eslint bersih; `yarn build` sukses. (Tak ada perubahan backend.)

---

## [#493] Laporan DBHI: sub-sub kelompok di bawah kode barang + tombol Sampul rekapitulasi dihapus — 2026-07-22

Dua penyempurnaan hasil masukan pemilik.

### Sub-sub Kelompok di kolom Kode Barang (semua kondisi DBHI)

Pada laporan **Daftar Barang Hasil Inventarisasi BMN** untuk seluruh
kondisi — Baik, Rusak Ringan, Rusak Berat, Berlebih, Tidak Ditemukan,
Dalam Sengketa — kolom "Kode Barang" kini menampilkan **kode di baris
atas** dan **nama Sub-sub Kelompok** (uraian kodefikasi terdalam yang
terdaftar) di baris bawah — kecil & abu-abu — memberi konteks klasifikasi
tanpa menambah kolom. Helper `_sel_kode_barang_subsub` + peta
`_peta_subsub_kelompok` atas aset ter-filter; kolom Kode Barang dilebarkan
untuk memuat dua baris. Terpusat di `generate_dbhi_pdf` sehingga ikut ke
**LHI Lengkap** & **batch ZIP**. Degradasi rapi bila referensi kodefikasi
belum lengkap (hanya kode yang tampil, tanpa galat).

### Tombol "Sampul" di rekapitulasi inventarisasi dihapus

Pengaturan kop/sampul kini terpusat di halaman **Pengaturan** (tab
Universal & per-satker), sehingga tombol "Sampul" (editor pengaturan
inline) di panel rekapitulasi inventarisasi menjadi redundan. Dihapus:
tombol + render editor + props `showSettings`/`setShowSettings`
(`ReportDownloads` & `RekapitulasiPanel`). Komponen `ReportSettingsEditor`
**dipertahankan** (masih dipakai halaman Pengaturan → Universal & hub
Pelaporan). **Tanpa data-loss**: seluruh 12 kunci setelan + logo tetap
dapat diedit di Pengaturan → Universal. Baris tombol dirapikan (LHI utama
+ Booking Nomor) dan grid Laporan Resmi diseimbangkan lintas HP/tablet/
desktop (`grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`, 5 tombol tanpa sisa
sel kosong yang janggal).

Verifikasi: 616 unit test lulus; render DBHI FakeDB memverifikasi sub-sub
kelompok tampil di 6 kondisi + degradasi rapi; audit adversarial diff
(3 dimensi) nihil temuan; eslint bersih; `yarn build` sukses.

---

## [#492] Kop surat berlogo: teks instansi dipusatkan rapi di ruang kanan logo — 2026-07-21

Perbaikan tata letak kop surat pada seluruh laporan resmi (Berita Acara,
SPTJM, Surat Koreksi, DBHI, RHI, BAHI, Daftar Pemegang, dll. — semua yang
memakai helper kop bersama `_kop_surat_flowables`).

Masalah: pada kop **berlogo**, blok teks instansi dipusatkan pada SELURUH
lebar halaman (kolom spacer kosong di kanan selebar logo). Akibatnya baris 1
(nama instansi — biasanya paling panjang) menjulur ke kiri mendekati logo,
sehingga tampak "melenceng sendiri" dibanding baris 2/3 yang lebih pendek —
walau secara matematis semuanya berbagi sumbu tengah halaman yang sama.

Perbaikan: logo tetap di kiri, tetapi blok teks kini **dipusatkan pada ruang
di kanan logo** (tabel 2 kolom `[logo | teks]`, bukan `[logo | teks | spacer]`).
Dengan begitu setiap baris — termasuk baris 1 — berbagi satu sumbu tengah
yang bersih dari logo dan sejajar rapi; komposisi seimbang (bobot logo kiri
diimbangi teks yang terpusat sedikit ke kanan). Lebar kolom logo dibatasi
maksimal 30% lebar dokumen sehingga logo yang sangat lebar tidak lagi
membuat kolom teks kolaps (dulu bisa menggagalkan render — `availWidth`
negatif). Kop tanpa logo tidak berubah (tetap terpusat penuh).

Verifikasi: pengukuran aliran-konten PDF memastikan seluruh baris kop
(instansi/unit/sub/alamat) berbagi satu sumbu-tengah identik pada semua
rasio logo (persegi/tinggi/lebar/spanduk) tanpa crash; 616 unit test lulus;
smoke render FakeDB semua laporan OK.

---

## [#491] Area TTD tanpa NIK apa pun statusnya + tab Log Sistem di panel audit — 2026-07-21

Lanjutan mandat privasi TTD (#485) & saran audit #490, sesuai arahan pemilik:
NIK tidak boleh pernah muncul di bawah nama pada area tanda tangan — termasuk
pegawai ASN yang di Master Pegawai masih tercatat NIK (belum ber-NIP): cukup
nama saja. Plus filter "Log Sistem" yang sebelumnya belum ada di panel audit.

### Area tanda tangan — NIK tertahan di semua status (`pegawai_utils.py`)

- **`label_nomor_identitas`**: pemeriksaan format NIK kini dilakukan SEBELUM
  cabang status TNI/POLRI — sebelumnya TNI/POLRI dengan NIK tercatat bocor
  sebagai `NRP. <NIK>` di blok TTD. ASN (PNS/PPPK) ber-NIK sudah tertahan
  oleh deteksi format; kini seragam untuk semua status: **cukup nama**.
- **Deteksi kebal pemisah**: NIK/NIP yang ditulis berpemisah umum
  (`3506 0425 0390 0001`, `3506.0425.0390.0001`) dahulu lolos sebagai "nomor
  tak dikenal" dan tercetak dengan label NIP default. Deteksi kini membuang
  spasi/titik/strip dulu (`_RE_PEMISAH_NOMOR`) — NIK berpemisah ikut
  tertahan, NIP berpemisah tetap tercetak apa adanya dengan label benar.
- Berlaku otomatis di SEMUA blok TTD karena satu formatter dipakai bersama:
  laporan ReportLab (`baris_identitas_ttd`/`_baris_nip_ttd`/`blok_ttd_kpb*`),
  stempel e-sign & Lembar Pengesahan (`routes/ttd.py`). Tabel identitas badan
  dokumen ("Yang bertanda tangan di bawah ini: … NIP: …") TIDAK diubah —
  sesuai arahan, aturan ini khusus area tanda tangan.
- Unit test baru: NIK tertahan utk `pns`/`pppk`/`tni`/`polri`/tanpa status,
  NIK berpemisah tertahan, NIP berspasi tetap berlabel NIP (616 test lulus).

### Panel Log Audit — tab "Log Sistem" baru

- **Backend** `GET /audit-logs?sistem=true`: hanya log SISTEM (tanpa
  `activity_id` — kejadian master pegawai & kartu pegawai UID). User terikat
  satker otomatis dibatasi log ber-`kode_satker` satkernya; super admin
  melihat semua log sistem.
- **Log CRUD Master Pegawai kini ber-`kode_satker`** (buat/ubah/hapus/impor/
  foto — melengkapi log kartu dari #490) sehingga tab Sistem bermakna juga
  bagi admin satker, bukan hanya super admin.
- **Frontend `AuditLogPanel`**: tab ke-4 "Sistem" (ikon server) di samping
  Timeline/Per User/Integritas — label aksi berbahasa Indonesia utk
  `buat/ubah/hapus/impor/foto_pegawai`, `daftar/lepas_kartu`,
  `kartu_tak_dikenal`; keterangan cakupan + teks kosong khusus; paginasi
  sama; pindah tab otomatis memuat ulang dari halaman 1.

Verifikasi: 616 unit test lulus; smoke render FakeDB semua laporan OK
(Non-ASN + klasifikasi + daftar pemegang); eslint bersih; `yarn build` sukses.

---

## [#490] Penyempurnaan hasil audit menyeluruh — keandalan & keterhubungan fitur — 2026-07-21

Audit 3 arah (backend, frontend, keterhubungan lintas fitur) atas 11 rilis
sesi terakhir; tidak ada sambungan putus, temuan diperbaiki semua:

- **Bug**: laporan Daftar Pemegang Aset bisa menampilkan KPB yang masa SK-nya
  habis (resolver dipanggil tanpa tanggal — temuan #41 terulang) → kini
  selalu dicek per hari ini.
- **Bug**: respons tap kartu yang tiba SETELAH dialog BAST/TTD ditutup bisa
  meruntuhkan halaman (layar putih) → null-guard + guard index penanda
  tangan; respons telat kini diabaikan sepenuhnya oleh dialog tap.
- **Kartu e-KTP**: UID hex serba-digit kini tetap cocok lintas format reader
  (kandidat byte-dibalik ikut dihasilkan); prefiks `0x` diterima; index
  `kartu_uid_hashes` dijadikan UNIK (menutup balapan 2 admin mendaftarkan
  kartu sama, fallback non-unik bila data lama duplikat); pesan 409 tidak
  lagi membocorkan nama pegawai satker lain; batas panjang input; pesan
  khusus saat kena rate-limit (bukan "periksa koneksi" yang menyesatkan).
- **Audit kartu kini termonitor**: log daftar/lepas/tap-tak-dikenal membawa
  `kode_satker` dan halaman audit menampilkan log sistem ber-satker bagi
  admin satkernya (dulu praktis write-only).
- **Batch ZIP**: ber-rate-limit (3/mnt) + dedup + batas 40 tipe (tipe berat
  lhi/executive-data bisa dipakai DoS ringan); tipe tak dikenal kini tercatat
  di `_LAPORAN-GAGAL.txt` (bukan hilang diam-diam); pesan kegagalan tidak
  membocorkan string error internal; pilihan "Kolom tambahan" kini juga
  berlaku utk PDF Eksekutif/Data Aset di dalam ZIP (dulu hanya unduhan
  tunggal).
- **Frontend**: `lottie-web` dideklarasikan eksplisit di package.json (dulu
  hanya transitif — rapuh); `BarisModul` di-hoist keluar komponen (10
  instance Lottie tak lagi re-init tiap render halaman); gerbang hapus di
  peta memakai `canDelete` (bukan `canEdit`); memilih pegawai BERBEDA via
  picker/tap kini menimpa jabatan lama (tak menyisakan jabatan orang
  sebelumnya); LHI menutup merger dgn benar pada jalur gagal.
- **Dokumentasi**: InfoPage & README dimutakhirkan — DBHI 8 tipe, laporan
  Daftar Pemegang Aset, Kartu Pegawai e-KTP, aturan Non-ASN, batch ZIP penuh.

## [#489] Kartu Pegawai (UID e-KTP/NFC) — tap kartu utk identifikasi cepat lintas modul — 2026-07-21

- **Fitur baru**: e-KTP (kartu NFC ISO 14443) kini bisa dimanfaatkan
  sebagai KARTU PEGAWAI lewat UID-nya — TANPA membaca data kependudukan
  di chip (tidak butuh perangkat SAM/kerja sama Dukcapil).
- **Pendaftaran mudah** — Master Pegawai › tab Identitas › "Daftarkan
  Kartu…" → tap kartu di pembaca → selesai. Dukungan pembaca: (1) reader
  NFC USB mode keyboard (keyboard-wedge — murah & umum, jalan di semua
  perangkat/browser), (2) Web NFC Android Chrome (best-effort; e-KTP
  umumnya bukan tag NDEF sehingga reader USB tetap jalur utama), (3) ketik
  UID manual. Ganti/Lepas kartu tersedia; satu kartu = satu pegawai.
- **Terintegrasi ke titik-titik kunci** via dialog bersama `KartuTapDialog`:
  form aset (tombol kartu di samping picker Pegawai — tap → pengguna
  barang terisi), BAST Penggunaan (Penerima & Pemegang lama), dan TTD
  elektronik (identitas penanda tangan). Tap → nama, NIP, jabatan terisi
  otomatis dari Master Pegawai.
- **Keamanan data & operasi**:
  - UID mentah TIDAK PERNAH disimpan/di-log — hanya HMAC-SHA256 berkunci
    rahasia server (`KARTU_UID_SECRET` opsional, fallback `JWT_SECRET`);
    UI/audit hanya menampilkan 4 karakter terakhir.
  - Normalisasi multi-format reader: hex MSB/LSB & desimal dari reader
    berbeda tetap dikenali sebagai kartu yang sama (hash semua kandidat).
  - Endpoint ber-rate-limit (identifikasi 30/mnt, daftar/lepas 10/mnt),
    terautentikasi, isolasi satker, dan seluruh pendaftaran/pelepasan +
    tap kartu tak dikenal tercatat di audit log.
  - Batas peran DIDOKUMENTASIKAN di UI: UID dapat dikloning — tap kartu =
    identifikasi cepat/kenyamanan, BUKAN verifikasi keaslian KTP dan
    BUKAN pengganti TTD elektronik.
- Field kartu menempel di dokumen pegawai → otomatis ikut backup & selamat
  reset; index lookup `kartu_uid_hashes`; 5 unit test util baru (615 total).

## [#488] Peta Aset — tombol hapus di popup marker + pin bersilang setelah dihapus — 2026-07-21

- Popup marker di Peta Aset kini punya **ikon hapus** (tong sampah merah,
  di samping tombol Edit Aset) yang langsung menghapus data aset tersebut
  — memakai alur hapus yang SAMA dengan daftar (dialog konfirmasi, wajib
  online, pembersihan snapshot offline, sinkron daftar/galeri otomatis).
- Setelah terhapus, **pin TIDAK hilang melainkan diberi TANDA SILANG
  merah** (pin abu-abu + X) sebagai jejak visual di peta; drag pin
  dimatikan dan popup-nya berubah menjadi keterangan ringkas "Aset ini
  telah dihapus". Pin bersilang bertahan meski data peta dimuat ulang, dan
  hilang wajar saat peta ditutup/dibuka kembali (asetnya memang sudah
  tiada).
- Tombol hapus hanya tampil untuk pengguna ber-izin edit; gagal/batal
  hapus tidak mengubah pin.

## [#487] Dokumen pendukung baru: Daftar Pemegang Aset per kegiatan — 2026-07-21

- Laporan PDF baru di **Dokumen Pendukung Lainnya**: **Daftar Pemegang
  Aset** — kop resmi + info kegiatan, lalu:
  1. **Rekap per pemegang**: nama, NIP/NIK, melekat ke (Individual/
     Jabatan/Operasional), jabatan, jumlah aset, hitungan BAST terunggah
     (n/m), dan status kelengkapan (Lengkap/Belum);
  2. **Rincian aset per pemegang**: kode barang, NUP, nama barang, nomor
     BAST (+ penanda "terunggah") — urut pemegang ber-aset terbanyak dulu;
  3. Ringkasan jumlah pemegang, aset ber-pemegang, dan aset tanpa
     pemegang; ditutup TTD Kuasa Pengguna Barang (aturan Non-ASN berlaku).
- Pengelompokan pemegang memakai logika yang SAMA dengan halaman Aset per
  Pemegang modul Penggunaan (`rekap_pemegang` — nama dinormalkan, NIP
  membedakan orang bernama sama), sehingga angka laporan = angka layar.
- Ikut pilihan **Batch Download ZIP**. Smoke render FakeDB lolos; 610 unit
  test lolos.

## [#486] RHI menjabarkan klasifikasi BMN Tidak Ditemukan + laporan DBHI per klasifikasi — 2026-07-21

- **RHI**: baris "BMN TIDAK DITEMUKAN" kini dijabarkan sub-barisnya —
  **Kesalahan Pencatatan**, **Tidak Ditemukan Lainnya**, dan (bila ada)
  **Belum Diklasifikasi** — dengan jumlah, nilai, dan persentase
  masing-masing; jumlah sub-baris selalu = total baris B. Konsisten dengan
  rincian yang sudah ada di BAHI & rekapitulasi.
- **Dua laporan DBHI baru per klasifikasi** (permintaan pemilik):
  **DBHI Kesalahan Pencatatan** dan **DBHI Tidak Ditemukan Lainnya** —
  format sama dengan DBHI Tidak Ditemukan (kolom Klasifikasi/Sub
  Klasifikasi/Uraian/Tindak Lanjut), berisi HANYA aset klasifikasi
  tersebut. Aset Tidak Ditemukan yang belum diklasifikasi tetap ada di
  daftar induk DBHI Tidak Ditemukan.
- Tombol unduh baru di panel Rekapitulasi (badge jumlah per klasifikasi,
  nonaktif bila 0) + kedua laporan ikut pilihan **Batch Download ZIP**.
- Smoke render FakeDB: sub-baris RHI tampil benar; DBHI per klasifikasi
  hanya memuat aset klasifikasinya. 610 unit test lolos.

## [#485] Penandatangan Non-ASN tanpa baris NIP/NIK di seluruh blok TTD — 2026-07-21

- **Aturan baru (permintaan pemilik)**: bila penandatangan teridentifikasi
  **Non-ASN**, baris NIP/NIK di bawah namanya **tidak dicetak** — berlaku
  di SEMUA dokumen bertanda tangan: laporan inventarisasi (SPTJM, Surat
  Koreksi, DBHI, RHI, DBKP, SP Hasil/Pelaksanaan), BA & BAHI (blok tim +
  KPB), laporan pembukuan (Posisi BMN, DBR, KIR, Penyusutan, LBKP, LKB,
  CaLBMN), LBP (DOCX), semua PDF persediaan (Nota Dinas, BA Opname,
  Posisi, Mutasi, LPB 3 kolom, Kartu Barang), BAST (kedua pihak + KPB),
  Daftar Barang Digunakan, serta dokumen lintas modul via helper KPB
  bersama (DHPB pemeliharaan, KIB, BA pemusnahan, laporan wasdal).
- **TTD elektronik** ikut: stempel pembubuhan pada dokumen dan Lembar
  Pengesahan tidak lagi mencetak NIP bila penanda tangan Non-ASN (status
  dicari otomatis dari registry pejabat / Master Pegawai per NIP).
- Mekanisme satu titik: `penandatangan_kpb` kini MEMBAWA
  `status_kepegawaian` dari registry pejabat; resolver bersama melengkapi
  status via lookup master bila fallback setelan; formatter
  `baris_identitas_ttd` menerima status (Non-ASN/NIK → baris ditiadakan,
  TNI/POLRI → label NRP). Anggota tim BA/BAHI dicek massal via peta status.
- Verifikasi: 610 unit test lolos (2 test baru) + smoke render 5 laporan
  dengan FakeDB — NIP PNS tetap tampil, NIP/NIK Non-ASN tertahan.

## [#484] LHI Lengkap utuh kembali + batch ZIP mencakup semua laporan — 2026-07-21

- **Bug (regresi guard satker)**: sejak guard akses per-satker ditambahkan
  ke semua generator laporan, panggilan INTERNAL dari penyusun LHI Lengkap
  dan batch ZIP tidak meneruskan `_user` — parameter itu berisi objek
  `Depends` mentah sehingga guard melempar error dan bagian laporan
  di-skip DIAM-DIAM. Akibatnya **LHI Lengkap hanya berisi sampul** (BAHI/
  RHI/DBHI/DBKP/SP hilang) dan **batch ZIP nyaris kosong**.
- **Perbaikan**: `_user` kini diteruskan ke setiap generator pada kedua
  jalur; LHI kembali utuh (Sampul + BAHI + RHI + 6 DBHI + DBKP + SP Hasil
  + SP Pelaksanaan) dan semua pilihan batch ZIP terisi.
- **Anti diam-diam**: bila ada bagian LHI yang gagal dibuat, unduhan kini
  GAGAL dengan pesan yang menyebut bagian bermasalah (bukan mengirim PDF
  parsial tanpa pemberitahuan). Pada batch ZIP, laporan yang gagal dicatat
  di file `_LAPORAN-GAGAL.txt` di dalam ZIP.
- **Cakupan batch ZIP dilengkapi** dengan pilihan yang sebelumnya tak
  tersedia: **LHI Lengkap (gabungan)**, **Eksekutif per Barang Serupa**,
  dan **Data Aset (semua halaman, otomatis semua bagian 499-an aset)** —
  kini seluruh laporan per kegiatan bisa diunduh sekali klik dalam satu ZIP.

## [#483] Perbaikan PSP dari impor SIMAN — barang belum ter-PSP tak lagi terhitung sudah PSP — 2026-07-20

- **Bug**: kolom "No PSP" pada ekspor SIMAN memakai placeholder (mis. `-`,
  `Tidak Ada Inputan`) untuk barang yang BELUM ter-PSP. Placeholder ini
  tersimpan apa adanya saat impor lalu dianggap nomor PSP sungguhan,
  sehingga barang belum ter-PSP ikut terhitung "sudah PSP": muncul di
  panel PSP-dari-SIMAN modul Penggunaan (menggerombol jadi kelompok palsu
  bernomor `-`) dan mendapat event "PSP menurut SIMAN V2" di timeline aset.
- **Perbaikan berlapis** (fungsi baru `norm_no_psp` di `siman_utils`):
  1. **Parse impor** — placeholder "belum PSP" (`-`, `--`, `0`,
     `Tidak Ada Inputan`, `Belum PSP`, `Belum Ditetapkan`, `N/A`, dsb.,
     case-insensitive) dinormalkan jadi kosong sebelum disimpan.
  2. **`kelompokkan_psp_siman`** (panel Penggunaan) — menyaring placeholder
     juga saat MEMBACA, karena referensi lama di DB bisa berasal dari impor
     sebelum penyaringan ada. Impor ulang file SIMAN juga membersihkan
     referensi aset yang cocok.
  3. **Timeline aset** — `info_psp_siman`/`event_psp_siman` memakai
     normalisasi yang sama; tak ada lagi event PSP palsu.
  4. **Query endpoint `/penggunaan/psp-siman`** — prefilter placeholder
     umum langsung di query agar fetch tidak dipenuhi baris bukan-PSP.
- Unit test baru di ketiga lapisan (parse, kelompokkan, timeline); seluruh
  608 test unit backend lolos.

## [#482] Peta Siklus — 6 modul lagi mendapat ikon Lottie beranimasi (total 10) — 2026-07-20

- Melengkapi ikon animasi Peta Siklus: **6 modul lagi** kini memakai ikon
  Lottie yang benar-benar sesuai maknanya — **Pengamanan** (gembok
  mengunci), **Inventarisasi Aset** (centang tercontreng), **Penghapusan**
  (tong sampah), **Perencanaan** (kalender), **Pelaporan** (garis grafik
  aktivitas), **Penggunaan** (penetapan pengguna). Total 10 dari 16 modul
  ber-ikon Lottie.
- Ikon dua-keadaan (gembok, tong sampah, centang) kini AMAN dipakai karena
  pola hover maju-mundur dari rilis sebelumnya: animasi maju saat kartu
  di-hover, mundur kembali ke frame awal saat kursor keluar — ikon selalu
  pulih ke kondisi semula.
- Modul tanpa padanan yang pas di katalog (Penganggaran, Pengadaan,
  Pemanfaatan, Penilaian, Pemusnahan, Pembukuan) tetap ikon lucide +
  micro-animation CSS agar makna ikon tidak dipaksakan.
- Catatan: permintaan awal memakai lordicon.com, tetapi jaringan
  environment pengembangan memblokir cdn.lordicon.com sehingga asetnya
  tidak dapat diunduh; dipakai katalog useanimations yang sudah terpasang
  (offline & sudah ber-atribusi). Struktur `UA_ICON` menerima JSON Lottie
  apa pun — ikon lordicon dapat menggantikannya kapan saja bila file
  disediakan.

## [#481] Peta Siklus — ikon Lottie kembali ke kondisi semula setelah hover — 2026-07-20

- **Perbaikan**: ikon Lottie (Pemeliharaan, Wasdal, Pemindahtanganan,
  Inventarisasi Persediaan) tadinya berhenti di **frame akhir** setelah
  diputar saat hover, sehingga terlihat "nyangkut" dalam kondisi berbeda
  dari semula. Sekarang saat kursor **keluar** dari kartu, animasi diputar
  **MUNDUR kembali ke frame awal** — ikon selalu kembali ke kondisi semula.
- Ikon Lottie kini digerakkan langsung lewat **lottie-web** (bukan lagi
  komponen tingkat-tinggi `react-useanimations`, tetapi tetap memakai data
  animasinya) agar arah putar bisa dikontrol: **maju saat hover, mundur
  saat keluar** — pola yang sama seperti trigger hover ikon animasi pada
  umumnya. Warna ikon dipaksa putih via `filter` agar kontras di atas tile.
- Menghormati `prefers-reduced-motion`: bila aktif, ikon diam di frame awal
  dan tidak diputar. Ikon lucide + CSS `.ikon-*` modul lain tak berubah
  (sudah otomatis kembali ke posisi awal karena keyframe rest di 0%/100%).

## [#480] Peta Siklus — animasi ikon hanya diputar sekali saat kartu di-hover — 2026-07-20

- Animasi ikon modul (Lottie useanimations maupun micro-animation CSS
  `.ikon-*`) **tidak lagi loop terus-menerus**: saat idle semua ikon diam,
  dan animasi **diputar SEKALI** setiap kartu modul di-hover. Keluar hover
  me-reset animasi sehingga hover berikutnya memutarnya sekali lagi.
- Kartu yang memicu ditandai kelas `.peta-kotak` (baris modul di timeline
  fase, kartu Wasdal, kartu submodul Penatausahaan, tile ikon di dialog
  detail). Versi CSS lewat selector `.peta-kotak:hover .ikon-*` dengan
  `animation-iteration-count: 1`; versi Lottie diputar ulang via remount
  (`key`) per hover dengan `loop=false`.
- Delay stagger antar ikon dihapus (tidak relevan lagi karena tak ada
  animasi idle); durasi animasi dipersingkat agar respons hover terasa
  sigap. Halaman jadi lebih tenang & hemat daya (tanpa animasi berjalan
  terus di latar).

## [#479] Peta Siklus — ikon Lottie beranimasi (useanimations) pada modul terpilih — 2026-07-20

- Empat ikon modul di halaman Beranda Modul / Peta Siklus kini memakai
  **ikon animasi Lottie dari useanimations.com** yang gerak loop-nya
  mengalir mulus dan sesuai makna: **Pemeliharaan** (gerigi/setelan
  berputar), **Wasdal** (mata berkedip), **Pemindahtanganan** (panah
  berbagi/pindah), dan **Inventarisasi Persediaan** (kotak arsip).
- Modul lain **tetap** memakai ikon lucide + micro-animation CSS `.ikon-*`
  dari rilis sebelumnya (mengapung/berdenyut/berputar dsb.) — ikon Lottie
  hanya dipakai bila animasinya benar-benar cocok di-loop selamanya
  (animasi buka/tutup seperti gembok/tempat sampah sengaja dihindari agar
  tetap tampak profesional).
- Semua titik render ikon disatukan lewat komponen `IkonModul` (grid fase,
  poros Penatausahaan, kartu Wasdal, dialog detail) sehingga pemilihan
  Lottie vs lucide konsisten di seluruh halaman.
- Dependensi baru: `react-useanimations` (kode paket MIT) + `lottie-web`.
  Aset animasi berlisensi **CC BY 4.0** → **atribusi ke useanimations.com
  dicantumkan** di footer halaman Info sesuai syarat lisensi.

## [#478] Peta Siklus — ikon modul beranimasi halus sesuai maknanya — 2026-07-20

- Setiap ikon modul di halaman Beranda Modul / Peta Siklus kini punya
  **animasi idle yang halus dan sesuai makna ikonnya**: timbangan
  (Penilaian) bergoyang, perisai (Pengamanan) & mata (Wasdal) berdenyut,
  kunci-inggris (Pemeliharaan) berputar, panah pindah (Pemindahtanganan) &
  keranjang (Pengadaan) bergeser, api (Pemusnahan) berkobar; modul lain
  mengapung lembut.
- Animasi di-**stagger** (delay stabil dihitung dari id modul) sehingga
  ikon tidak bergerak serempak — terkesan hidup namun tetap tenang &
  profesional. Semua gerak `transform`-only (GPU), keyframe rest di
  0%/100% sehingga `prefers-reduced-motion` otomatis mendiamkannya.
- Kelas `.ikon-*` di `index.css`; hover tile tetap membesar seperti
  sebelumnya. Diterapkan di semua titik render ikon (grid fase, poros
  Penatausahaan, kartu Wasdal, dialog detail modul).

## [#477] Beranda Modul — warna ikon modul dibuat profesional & kohesif (bukan pelangi) — 2026-07-20

- Warna latar ikon tiap modul di halaman Beranda Modul / Peta Pengelolaan
  BMN sebelumnya memakai gradasi yang terlalu beragam (sky, amber, emerald,
  violet, orange, rose, red, dst.) sehingga terkesan "pelangi".
- Diganti **palet dingin profesional & kohesif** — hanya keluarga
  biru–indigo–sky–cyan–teal–slate (analog, selaras warna merek
  biru/indigo), tanpa warna hangat/mencolok. Perbedaan halus per fase tetap
  menjaga modul mudah dikenali; tahap pelepasan (pemindahtanganan/
  pemusnahan/penghapusan) memakai slate netral. Aman di light & dark.

## [#476] Air sinkron SIMAN lebih hidup — dua lapisan gelombang variatif + bola mengapung organik — 2026-07-20

- **Gelombang tak lagi monoton**: satu gelombang sinus tunggal yang bergeser
  linier diganti DUA lapisan bermask — belakang (lebar, puncak tinggi
  bervariasi + alun bernafas naik-turun) dan depan (riak kecil lebih cepat,
  panjang gelombang berbeda). Overlay dua panjang-gelombang & kecepatan
  yang berbeda menghasilkan pola pelayangan (beat) sehingga siluet
  permukaan terus berubah bentuk — terlihat hidup, ukuran gelombang
  sangat variatif.
- **Bola benar-benar mengapung**: apungan naik-turun tak simetris + geser
  + oleng seperti benda terapung di ombak nyata; periode 6,9 dtk yang BUKAN
  kelipatan periode gelombang (13/6,5/4,7 dtk) sehingga gerak gabungan tak
  pernah berulang persis → tidak monoton.
- **Lebih smooth**: seluruh gerak lewat `transform` (translate3d, GPU),
  easing lembut; meniskus di dasar bola bernafas + sedikit melapis seperti
  riak menjilat. Warna tetap `hsl(var(--card))` (ikut light/dark), hover &
  proses sinkron mempercepat proporsional, `prefers-reduced-motion` tetap
  dihormati.

## [#475] Pengaman kunci Resend — bersihkan kutip/spasi/CR-LF dari .env + log diagnosa ter-masker — 2026-07-20

- Lanjutan #472 (galat nyata di produksi: "Kunci API layanan email tidak
  valid"): nilai `RESEND_API_KEY` & `SENDER_EMAIL` kini DIBERSIHKAN dari
  tanda kutip, spasi, dan CR-LF yang kerap ikut tersalin ke `.env`
  (mis. file diedit di Windows) — kunci yang "terlihat benar" dengan
  \r di ujung ditolak Resend sebagai 401.
- Log startup ter-masker (`Resend siap: kunci re_ab… (panjang N), pengirim
  …`) — admin bisa memastikan kunci yang TERBACA aplikasi sama dengan yang
  dimaksud tanpa membuka nilai kunci.

## [#474] Perbaikan: OTP pendaftaran tidak terkirim — alasan gagal jelas + jangan masuk langkah OTP + diagnosa email — 2026-07-20

- **Gejala**: kode OTP pendaftaran akun tidak pernah sampai ke email
  meski dicoba ulang. Dua akar masalah:
  1. **Kegagalan kirim dibisukan** — Resend menolak (kunci API kosong /
     `SENDER_EMAIL` masih alamat uji `onboarding@resend.dev` yang HANYA
     bisa mengirim ke email pemilik akun Resend) tapi hanya jadi log
     server; pengguna tak pernah tahu emailnya mustahil terkirim.
  2. **UI menyesatkan** — respons `otp_sent: false` tetap membawa
     pengguna ke langkah isi OTP dan pesan gagalnya tampil sebagai
     toast SUKSES.
- **Perbaikan backend**: `send_otp_email` kini mengembalikan (ok, ALASAN
  actionable berbahasa Indonesia — kunci API kosong / domain pengirim
  belum terverifikasi / kunci tidak valid / galat lain) + 1x coba ulang
  otomatis untuk galat sementara; pesan respons pendaftaran & kirim-ulang
  menyertakan alasan; endpoint diagnosa `GET /auth/email-status`
  (terkonfigurasi / sender / mode uji Resend + catatan perbaikan).
- **Perbaikan frontend**: gagal kirim → toast GALAT berisi alasan dan
  TIDAK masuk langkah isi OTP (registrasi, kirim-ulang, dan tambah user
  oleh admin); alur lupa-password tetap ber-respons generik
  (anti-enumerasi akun).
- README: seksi konfigurasi email (RESEND_API_KEY + SENDER_EMAIL domain
  terverifikasi). Unit test klasifikasi alasan (604 lulus).
- **Catatan admin**: bila alasan menunjuk konfigurasi, setel env
  `RESEND_API_KEY` dan `SENDER_EMAIL` domain terverifikasi di VPS lalu
  restart backend — cek cepat via `GET /api/auth/email-status`.

## [#473] Tambah-cepat peta — lampirkan foto (kamera / multi file, maks 6) dengan aturan foto form aset — 2026-07-20

- Popup "+ Tambah aset di sini" kini punya bagian FOTO opsional: tombol
  **Kamera** (jepret langsung) dan **Pilih Foto** (galeri/file,
  MULTI-UPLOAD sekali pilih), pratinjau mini ber-tombol hapus ×, dan
  penghitung n/6.
- **Aturan sama dengan form aset**: maksimal 6 foto (kelebihan ditolak
  dengan pesan), kompresi di klien (`compressImageFile` yang sama), foto
  pertama menjadi sampul/thumbnail, dan **ada foto → status inventarisasi
  otomatis "Ditemukan"** (tanpa foto tetap "Belum Diinventarisasi").
- Tombol simpan terkunci selama foto sedang diproses; marker sementara
  kini menampilkan lencana kamera bila titik dibuat dengan foto; semua
  tetap lewat antrean simpan optimistis (offline-first).

## [#472] Peta aset — tombol "Tampilkan lokasi Anda" di bawah kontrol zoom — 2026-07-20

- Tombol baru ber-ikon bidik tepat DI BAWAH tombol zoom in/out: klik →
  GPS perangkat (akurasi tinggi) → titik biru + lingkaran akurasi
  (±meter di tooltip) + peta menggeser/zoom secukupnya ke lokasi
  (tidak menjauh bila sudah dekat); klik lagi = sembunyikan.
- Izin lokasi ditolak / GPS gagal → pesan galat berbahasa Indonesia yang
  menjelaskan langkah berikutnya; tombol meredup selama pencarian lokasi.

## [#471] Perbaikan: popup tambah-cepat peta tidak lagi hilang saat mengetik nama — 2026-07-20

- Popup "+ Tambah aset di sini" sebelumnya TERTUTUP begitu mulai mengetik
  nama barang: klik/ketukan ke input (dan di HP, keyboard virtual yang
  terbuka memicu resize + klik sintesis) masih dianggap interaksi peta
  oleh Leaflet (`preclick` → `closeOnClick`).
- Kini popup KEBAL — `closeOnClick` & `autoClose` dimatikan dan seluruh
  event dari isi popup (pointer/mouse/touch/klik/keyboard/scroll)
  dihentikan sebelum mencapai peta; popup hanya tertutup lewat tombol
  tutup atau setelah "Simpan Titik Aset".

## [#470] Peta aset — tambah cepat aset di titik peta (klik kanan / tekan lama), cukup ketik nama — 2026-07-20

- **Tambah cepat dari peta**: klik kanan (desktop) atau TEKAN LAMA (HP &
  tablet — opsi `tapHold` Leaflet untuk iOS; Android/desktop bawaan) di
  area peta memunculkan menu **"+ Tambah aset di sini"** → cukup ketik
  NAMA BARANG → titik aset langsung terbentuk di koordinat yang ditekan.
- **Default sama dengan halaman tambah aset**: kategori DUMMY + kode aset
  kategori + **NUP berurutan otomatis** (helper bersama `lib/dummyNup.js`
  — SATU sumber urutan dengan Mode Kamera Penuh agar tidak kembar),
  status inventarisasi "Belum Diinventarisasi", kondisi Baik, status
  Aktif, stiker Belum Terpasang; detail lain dilengkapi nanti dari
  daftar aset.
- Lewat **antrean simpan optimistis yang sama** dengan form (offline-first,
  OCC) — marker sementara biru pudar tampil seketika dengan tooltip
  "tersimpan di antrean"; pin final muncul setelah antrean tersinkron.
- Enter di input = simpan; input mencuri fokus tanpa memicu pintasan
  keyboard peta; hanya tampil untuk pengguna ber-izin edit.

## [#469] TTD elektronik — atur letak & ukuran pembubuhan di dokumen + halaman publik responsif + keandalan lapangan — 2026-07-20

### Pembubuhan yang bisa diatur (baru)
- Setelah menggambar/mengunggah tanda tangan, penanda tangan kini masuk
  langkah **"Atur Pembubuhan"**: pratinjau halaman dokumen (dirender server
  per halaman — tanpa unduh PDF penuh), kotak tanda tangan bisa **digeser**
  (sentuh/mouse) dan **diubah ukurannya** (pegangan pojok + penggeser),
  **pilih halaman** (default halaman terakhir); tombol "Otomatis saja"
  mempertahankan perilaku lama (slot otomatis halaman terakhir).
- Backend: endpoint render halaman `GET /ttd/tandatangan/{id}/dokumen/
  halaman/{n}` (pypdfium2, rate-limit, cache privat); posisi (halaman +
  x/y/lebar fraksi) divalidasi & dijepit server, tersimpan per penanda
  tangan; builder dokumen ber-TTD menggambar di posisi pilihan (keterangan
  identitas kecil di bawahnya), penanda tanpa posisi tetap memakai slot
  otomatis, QR verifikasi tetap di halaman terakhir. Smoke-test FakeDB
  PDF 2 halaman lulus.

### Responsif semua tampilan
- Kontainer melebar di tablet/desktop (`max-w-2xl`), tinggi kanvas
  mengikuti lebar (180–280px — tidak lagi 200px gepeng), judul & tombol
  "Baca dokumen" membungkus rapi di HP sempit, font diperbesar.

### Keandalan segala kondisi (audit 3 lensa → diperbaiki)
- **Bug kritis rotasi**: `react-signature-canvas` menghapus goresan saat
  `window.resize` (default `clearOnResize`) — kode pemulihan lama tidak
  pernah jalan; kini `clearOnResize={false}` + goresan DISKALAKAN ke ukuran
  baru (rotasi portrait↔landscape tidak memotong tanda tangan; address bar
  Chrome Android yang menciut tidak lagi menghapus gambar).
- **Draf tahan reload**: goresan & hasil olah foto tersimpan di
  sessionStorage — tab terbunuh/di-reload tidak menghapus tanda tangan;
  draf dibersihkan setelah terkirim.
- **Jaringan**: timeout eksplisit (info 20 dtk, kirim 60 dtk, olah foto
  60 dtk); galat jaringan saat muat TIDAK lagi disamarkan "link tidak
  valid" (yang mendorong terbit-ulang link yang justru mematikan link
  valid) — kini layar "Koneksi bermasalah" + tombol Coba lagi; kirim
  terputus → pesan jelas bahwa tanda tangan masih ada; 409 → status
  dimuat ulang otomatis (submit yang sebenarnya sudah tercatat tidak
  tampil sebagai galat).
- **Foto kamera**: diperkecil di KLIEN (maks 1600px, JPEG) sebelum unggah
  — hemat kuota & cepat di jaringan seluler.
- **Guard tutup tab** saat tanda tangan siap tapi belum terkirim;
  Content-Length pada stream dokumen (progres unduhan di viewer HP).

## [#468] Air sinkron mengalir (gelombang cekung-cembung) + konfirmasi perbarui satker saat konflik kode↔nama — 2026-07-19

### Konfirmasi perbarui data satker (form kegiatan)
- **Sebelumnya**: mengganti Nama Satker (atau Kode 6 digit) di Buat/Edit
  Kegiatan langsung ditolak "…sudah terdaftar dengan …; harus sama" tanpa
  jalan keluar.
- **Kini**: backend menjawab 409 TERSTRUKTUR dan UI menampilkan dialog
  konfirmasi berisi pesan konflik + tombol **"Perbarui dengan Input Ini"**
  — disetujui → dikirim ulang dengan `perbarui_satker=true`:
  - **Rename NAMA (kode sama)**: nama baru diterapkan serentak ke SEMUA
    kegiatan ber-kode itu + Master Satker + riwayat pengesahan (kartu).
  - **Ganti KODE (nama sama)**: kode baru diterapkan ke semua kegiatan +
    Master Satker (re-key bila kode baru belum terpakai) + MIGRASI seluruh
    dokumen ber-stempel kode satker (persediaan, penggunaan/PSP, pemanfaatan,
    pemindahtanganan, pemusnahan, penghapusan, penganggaran, pengadaan,
    perencanaan, pengamanan, wasdal, BAST, pegawai, unit kerja, riwayat
    pengesahan) + user terikat — tidak ada dokumen yatim di kode lama dan
    user tidak terkunci dari datanya. Aset tidak perlu disentuh (relasi via
    activity_id, scoping dihitung saat query).
- Flag konfirmasi tidak ikut tersimpan ke dokumen kegiatan; operasi tercatat
  di log server.

- **Permukaan air kini benar-benar MENGALIR**: lapisan alun lama (lengkung
  cembung yang hanya bergoyang kiri-kanan) diganti pita air ber-MASK
  gelombang sinus berulang — CEMBUNG (puncak) dan CEKUNG (lembah)
  bergantian mulus — yang digeser linier satu arah tepat satu panjang
  gelombang per siklus sehingga aliran tak pernah terputus, pelan dan
  natural. Mask hanya membentuk siluet; warna tetap `hsl(var(--card))`
  (otomatis ikut mode light/dark).
- Garis dasar air sedikit diturunkan agar lembah (cekung) terlihat jelas
  turun; meniskus pemeluk bola & apungan bola tidak berubah.
- Hover bola = aliran lebih cepat; proses sinkronisasi = deras; sukses =
  tetap surut beranimasi.

## [#467] Air sinkron tampak samping + status sinkron SIMAN terhubung lintas-tampilan (list ↔ galeri) — 2026-07-19

- **Permukaan air kini tampak DARI SAMPING** (bukan kubah dari atas):
  garis air datar penuh selebar kartu + ALUN sangat landai (lengkung
  ekstra lebar, puncak hanya +4px, bergeser pelan kiri↔kanan seperti
  alun) + MENISKUS kecil yang memeluk dasar bola dan bernafas — bola
  mengapung pelan di atasnya; hover/proses tetap mempercepat gerakan.
- **Status sinkron terhubung lintas-tampilan** — sinkron sukses di mode
  list tidak lagi memunculkan ikon sinkronisasi saat pindah ke galeri
  (dan sebaliknya): penanda "sudah disinkronkan" disimpan setingkat modul
  (`lib/simanSync.js`) dengan kunci `id aset + import_id SIMAN`, sehingga
  bertahan saat komponen di-mount ulang ketika berganti mode; impor SIMAN
  BARU otomatis membatalkan penanda (selisih baru tetap tampil).
- **Animasi sukses hanya sekali** — diputar di komponen tempat sinkron
  terjadi saja (`baruSaja`), tidak diputar ulang tiap scroll/ganti mode.
- **Temuan verifikasi adversarial (3 lensa) — semua diperbaiki:**
  - `AssetTableRow.jsx` ternyata KODE MATI (tidak diimpor di mana pun) —
    tabel desktop sesungguhnya adalah `VirtualizedAssetTable.jsx`, sehingga
    gradasi selisih (#460), badge garansi list (#460), dan tombol sinkron
    samping NUP (#463) tak pernah tampil di desktop. Semua fitur itu kini
    DIPORTING ke `VirtualizedAssetTable` (sub-komponen `SimanMarker` —
    hook tidak boleh dipanggil di dalam map virtualizer) dan file mati
    dihapus.
  - Sinkron PARSIAL tidak lagi disamarkan tuntas: bila server menjawab
    `sisa_selisih > 0` (selisih kode barang tersisa → wajib jalur
    reklasifikasi), penanda selisih tetap tampil di semua tampilan dan
    toast menjelaskan sisa; penanda lintas-tampilan hanya diisi saat
    selisih benar-benar habis.
  - Race saat berpindah mode ketika request masih berjalan: pub-sub kecil
    di `simanSync.js` memperbarui instance yang baru mount begitu sinkron
    tuntas.
  - Kelas Tailwind mati `z-2`/`z-5` di kartu galeri → `z-[2]`/`z-[5]`
    (tumpukan overlay SPM & baris kode/NUP sesuai niat semula).
  - `prefers-reduced-motion`: umpan balik sukses kini tampil statis
    (sebelumnya lompat ke opacity 0 dan centang tak pernah terlihat).

## [#466] Air sinkron SIMAN natural — satu permukaan penuh selebar kartu, tenang di pinggir, bola diturunkan — 2026-07-19

- **Desain ulang efek air galeri** (umpan balik screenshot): air kini SATU
  permukaan penuh selebar kartu di dasar foto — datar & tenang di pinggir,
  hanya di sekitar bola ada gembungan lembut yang bernafas (bergeser
  kiri↔kanan + naik-turun pelan); air tidak melebihi puncak bola.
- **Bola diturunkan** hampir menyentuh batas area informasi, mengapung
  pelan seirama gembungan (naik-turun + oleng ringan); TANPA lapisan
  transparan dan TANPA air di depan bola (efek setengah tenggelam
  dihilangkan) — senatural mungkin.
- **Kode/NUP diangkat sedikit** di atas garis air agar teks putih tetap
  terbaca (air berwarna permukaan kartu).
- Hover bola / proses sinkronisasi tetap mempercepat ombak; sukses = air
  surut turun beranimasi bersama bola centang hijau.

## [#465] Lookup satker fallback ke Master Satker + auto-isi kode lengkap tanpa nilai basi + dokumentasi — 2026-07-19

- **`satker-lookup` kini FALLBACK ke Master Satker** — sebelumnya hanya
  mencari di kegiatan, sehingga kegiatan PERTAMA untuk satker yang sudah
  dirawat di Master Satker tidak ter-auto-isi (nama/eselon/kode lengkap).
- **Auto-isi kode satker lengkap tanpa nilai basi** — saat berganti ke
  satker lain, hasil lookup menimpa field apa adanya; nilai satker
  sebelumnya tidak lagi tertinggal (yang bisa ter-backfill ke master
  satker yang salah).
- **Dokumentasi** — README & halaman Info menyebut validasi satker cerdas
  6↔20 digit + sinkron 1-klik dari galeri/list.

## [#464] Kode satker lengkap 20 digit di kegiatan — sinkron SIMAN V2 tanpa peringatan satker berbeda — 2026-07-19

- **Konteks**: AMAN memakai kode satker 6 digit, SIMAN V2 memakai kode
  LENGKAP ±20 digit — impor SIMAN di modul Pelaporan memunculkan peringatan
  "Kode satker pada file BERBEDA dengan satker terdaftar" meski file milik
  satker sendiri.
- **Field baru `kode_satker_lengkap` di KEGIATAN** — form Data Satuan Kerja
  (opsional, contoh format SIMAN); sinkron DUA ARAH dengan Master Satker:
  kosong di kegiatan → terisi otomatis dari master (juga saat auto-isi
  kode/nama satker di form), terisi di kegiatan → backfill master yang
  belum punya; kegiatan baru ikut mendaftarkan kode lengkap saat
  auto-registrasi master satker.
- **Validasi satker impor SIMAN diperluas** — selain master satker + kop
  global, kini juga membaca kode satker (6 & 20 digit) dari SEMUA kegiatan
  inventarisasi.
- **Validasi cerdas 6 ↔ 20 digit** — kode terdaftar (≥6 digit) yang
  TERKANDUNG di dalam kode file (atau sebaliknya) dianggap cocok, karena
  kode 20 digit SIMAN memuat kode 6 digit AMAN sebagai segmen; kode <6
  digit tidak memicu (hindari cocok palsu). Unit test baru (597 lulus).

## [#463] Sinkron SIMAN bisa diklik di list HP & desktop (samping NUP) + saklar teks di HP + liquid menyatu ber-bola mengapung — 2026-07-19

- **Hook bersama `lib/simanSync.js`** (`useSinkronSiman`) — logika sinkron
  SIMAN satu sumber untuk kartu galeri, kartu HP/tablet, dan baris tabel
  desktop; penanda tidak muncul kembali sebelum daftar dimuat ulang.
- **List HP/tablet**: ikon SIMAN di bawah foto kini TOMBOL yang bisa
  diketuk — langsung menerapkan nilai SIMAN V2 (ikon berputar saat proses,
  centang hijau saat berhasil).
- **List desktop**: ikon sinkron dapat diklik TEPAT di samping kotak NUP,
  ukuran menyesuaikan kotak NUP (amber, hover menebal); berhasil → centang
  hijau + gradasi orange baris ikut hilang.
- **Saklar Dashboard ↔ Inventarisasi**: khusus tampilan HP (<640px)
  memakai TEKS di samping ikon; tablet & desktop tetap ikon-saja.
- **Liquid galeri disempurnakan** — dua lapisan air: kubah BELAKANG bola
  (morph organik) + permukaan DEPAN bola sedikit tembus pandang (ombak
  menyapu kiri↔kanan), sehingga bola sinkronisasi tampak MENGAPUNG
  SETENGAH TENGGELAM — air mengalungi bola, bola berayun ke atas/bawah/
  kiri/kanan + oleng ringan. Basis kedua lapisan rata penuh melewati batas
  foto sehingga benar-benar MENYATU dengan area informasi; posisi bola
  diturunkan (sebelumnya terlalu ke atas); hover membesar dari dasar
  (origin-bottom) + seluruh cairan bergolak lebih cepat.

## [#462] Galeri — efek liquid tombol sinkron SIMAN (idle/hover/proses/sukses) + badge garansi pindah ke kanan-atas — 2026-07-19

- **Efek liquid sinkron SIMAN V2** — tetesan lama (kotak diputar 45°, tanpa
  animasi cair) diganti BLOB LIQUID sungguhan di perbatasan foto ↔ area teks:
  warna mengikuti permukaan kartu (`--card`: putih di light, gelap di dark)
  sehingga tampak "meleleh" dari area teks ke foto, dengan bola sinkronisasi
  amber tetap UTUH di dalam cairan. Animasi CSS murni (`.siman-liquid*` di
  `index.css`): idle = morph border-radius pelan + bola mengapung; hover
  mouse = bergolak lebih cepat + membesar; proses sinkronisasi = gejolak
  cepat + ikon berputar; sukses = seluruh cairan terserap turun ke area teks
  sambil memudar (bola centang hijau). Hormati `prefers-reduced-motion`.
- **Badge garansi galeri kini terlihat** — posisi lama (kanan-bawah foto)
  tertimpa gradasi hitam bawah dan badge jumlah foto di titik yang sama
  (plus kelas `z-2` yang bukan kelas Tailwind valid) sehingga tak pernah
  tampak. Dipindah ke klaster badge KANAN-ATAS foto (sebelum kondisi &
  tahun) yang selalu bebas overlay — ikon shield + durasi singkat, hijau/
  amber sesuai sisa garansi, tooltip detail tetap.

## [#461] Foto pegawai — unggah + krop persegi (geser/zoom) + avatar di row; reset pertahankan foto pegawai — 2026-07-19

- **Unggah foto di Master Pegawai** — tab Identitas form pegawai kini punya
  bagian Foto: pratinjau avatar, tombol "Pilih Foto…" dan "Hapus Foto".
  Endpoint baru `POST/GET/DELETE /pegawai/{id}/foto` (GridFS, admin untuk
  tulis, maks 5 MB, JPEG/PNG/WebP; audit log).
- **Dialog Krop Foto** (`KropFotoDialog`) — pilih PERSEGI bagian foto yang
  tampil di daftar: geser (drag mouse/sentuh), zoom in/out 1–4× (slider,
  roda mouse, tombol ±) dengan titik tengah terjaga, garis bantu
  rule-of-thirds; hasil dirender ke JPEG 384×384. Mode tambah: foto
  disimpan dulu lalu diunggah otomatis setelah pegawai dibuat.
- **Avatar di row data** — foto bulat di kartu HP dan tabel desktop
  (fallback inisial nama bila tanpa foto; foto gagal dimuat otomatis
  disembunyikan).
- **Reset sistem tidak lagi meninggalkan foto pegawai yatim** — koleksi
  `pegawai` dipertahankan saat reset (master referensi), tapi GridFS
  sebelumnya dihapus TOTAL sehingga `foto_file_id` menunjuk berkas yang
  hilang. Kini berkas GridFS ber-`metadata.jenis: "foto_pegawai"` ikut
  dipertahankan saat reset.
- **Verifikasi backup/restore**: ekspor GridFS memuat SEMUA berkas
  (termasuk foto pegawai) + restore memulihkannya dengan `_id` asli —
  foto pegawai otomatis tercakup penuh tanpa perubahan.

## [#460] Inventarisasi aset — saklar ikon-only, jenis garansi, badge garansi ringkas, tetesan sinkron SIMAN di galeri, gradasi list, badge lampiran BAST — 2026-07-19

- **Saklar Dashboard ↔ Inventarisasi ikon-saja di SEMUA ukuran** (tanpa teks;
  label tetap lewat tooltip/aria).
- **Jenis garansi** (`garansi_jenis`) — field baru lewat registry (form ber-
  datalist Pabrikan/Distributor/Toko/Purna Jual/Lainnya, ekspor XLSX,
  template impor ber-dropdown, snapshot offline); tampil di tooltip badge.
- **Badge garansi dirombak** — simple ikon shield + durasi singkat
  ("45h"/"3bl"/"2th") tanpa teks: galeri di POJOK KANAN-BAWAH foto (di atas
  garis bawah), list desktop & kartu HP ukuran ringkas.
- **Galeri — belum sinkron SIMAN**: badge teks "≠ SIMAN" diganti ikon
  TETESAN AIR menjorok ke foto, di tengah perbatasan foto ↔ area teks;
  hover membesar (animasi), KLIK = langsung menerapkan nilai SIMAN V2
  (`/siman/terapkan`, kecuali kode barang) dan tetesan hilang beranimasi
  saat tersinkron; aman mode dark & light.
- **List desktop — belum sinkron SIMAN**: gradasi orange halus dari pojok
  kiri-bawah ke atas (pengganti badge teks), dengan tooltip.
- **Badge Lampiran BAST** di bagian Pengguna form aset (tambah/edit):
  chip hijau "Lampiran BAST tersedia — lihat foto/dokumen" yang otomatis
  terhubung dengan bukti serah terima dari modul Penggunaan (bast_file_id
  satu sumber) — klik untuk pratinjau.

## [#459] BMN Tidak Ditemukan — 3 surat resmi dilengkapkan sesuai SE PUPR 10/2023 & KMK 403/KMK.06/2013 — 2026-07-19

Dari dua dokumen resmi yang diunggah pemilik (ditranskrip utuh) — audit
mendalam alur "barang tidak ditemukan" hingga ke surat. Klasifikasi per-aset
(Kesalahan Pencatatan 7 jenis / Tidak Ditemukan Lainnya) dan ketiga surat
SUDAH ada; celah kepatuhan format ditemukan lewat smoke-render FakeDB →
pypdfium2 dan DITUTUP:

- **BA Tim Internal Penelitian**: rincian per barang kini memuat **Uraian**
  dan **Tindak Lanjut yang sudah dilakukan** (format SE PUPR bag. 3 —
  sebelumnya hanya klasifikasi/sub).
- **SPTJM**: ditambah pernyataan **telah dilakukan verifikasi & penelitian
  tim internal** + tanggung jawab penuh atas kebenaran **materiil maupun
  formil** (unsur minimum KMK 403/2013) + frasa **di atas meterai yang cukup**.
- **Surat Pernyataan Koreksi Pencatatan**: kini **merujuk Berita Acara**
  penelitian, memuat pernyataan BMN tercatat + penyebab kesalahan pencatatan,
  kalimat **menginstruksikan petugas BMN melakukan koreksi pencatatan** +
  cetak register transaksi harian/histori sebagai bukti (SE PUPR G.5), dan
  tabel rincian bertambah kolom **Tindak Lanjut**.
- Verifikasi: smoke-render ketiga PDF → seluruh unsur wajib ditemukan
  (pencocokan ternormalisasi spasi); 595 unit test hijau.

## [#458] Pengecekan keterhubungan fitur baru — scope satker auto-isi garansi + badge garansi di galeri + dokumentasi modul — 2026-07-19

Audit keterhubungan pasca dua fitur besar (perbaikan-umur & garansi) —
celah kecil ditemukan & ditutup:

- **Celah scope satker**: `GET /assets/garansi-sebelumnya` kini melalui
  `scope_query_aset` — identitas aset yang kebetulan sama di satker LAIN
  tidak lagi bisa menjadi sumber auto-isi garansi (konsisten M-SCOPE).
- **Badge garansi di tampilan galeri** (pojok kanan-atas foto) — melengkapi
  tabel desktop & kartu HP; hijau/kuning sama, hilang bila kosong/lewat.
- **Verifikasi menyeluruh** (tanpa perubahan karena SUDAH benar):
  backup dinamis mencakup `pemeliharaan` (ber-subdoc BA) & `masa_manfaat`
  dipertahankan saat reset; impor aset registry-driven (garansi otomatis
  ikut); snapshot offline memuat garansi (badge tampil offline); tidak ada
  pemanggil `hitung_penyusutan` yang melewatkan tambahan umur perbaikan.
- **Dokumentasi modul** (`bmnModules.js`): Pemeliharaan (+posting 202 ber-BA,
  +tambahan masa manfaat Tabel II) & Penilaian (Tabel I lengkap, umur dari
  SIMAN, umur bertambah dari perbaikan) dimutakhirkan.

## [#457] Garansi aset — kolom rentang garansi + auto-isi dari inventarisasi sebelumnya + badge sisa garansi — 2026-07-19

- **Field baru `garansi_hingga`** (tanggal berakhir garansi; rentang lazim
  dihitung sejak tanggal perolehan) lewat registry `asset_fields.py` →
  otomatis ikut PATCH, ubah massal, audit, proyeksi list, CSV/impor; plus
  models, ekspor XLSX ("Garansi Hingga"), template impor, `SNAPSHOT_FIELDS`
  offline, dan input tanggal di form aset (di bawah Tanggal Beli).
- **Auto-isi saat inventarisasi**: ketika kode barang + NUP dan/atau kode
  register yang diketik sama dengan aset dari inventarisasi SEBELUMNYA yang
  sudah punya garansi tercatat, kolom garansi terisi otomatis (endpoint
  `GET /assets/garansi-sebelumnya`, pola identitas kartu inventarisasi;
  debounce 600 ms, offline-tolerant, tidak menimpa isian manual) — informasi
  garansi terkumpul sekali dan terbawa ke kegiatan berikutnya.
- **Badge sisa garansi** mudah dibaca di daftar aset (tabel desktop + kartu
  HP): "Garansi N hari/bln/±th lagi" — hijau; ≤60 hari jadi kuning (segera
  habis); **hilang otomatis** bila tidak tercatat atau sudah lewat tanggal.
  Helper bersama `lib/garansi.js`.

## [#456] Perbaikan menambah umur aset — Tabel Masa Manfaat II (KMK 295/266/339) + Berita Acara Perbaikan wajib + penyusutan ikut umur baru — 2026-07-19

Dari dokumen resmi yang diunggah pemilik (KMK 295/KM.6/2019 jo. 266/KM.6/2023
jo. 339/KM.6/2024, ditranskrip halaman-per-halaman) + riset PMK 65/2017:

- **Tabel Masa Manfaat II LENGKAP** di `perbaikan_utils.py` — penambahan
  masa manfaat akibat perbaikan (renovasi/restorasi/overhaul) per kelompok
  5 digit × rentang persentase biaya terhadap nilai aset (di luar
  penyusutan). ±90 kelompok golongan 3/4/5 + entri KMK 266 (keimigrasian)
  & KMK 339 (migas). Helper murni `hitung_penambahan_masa_manfaat` +
  uji unit (bracket, batas inklusif, pagar melebihi rentang, anti-drift
  Tabel I↔II).
- **Tabel Masa Manfaat I LENGKAP** — `MASA_MANFAAT_DEFAULT` yang semula 7
  entri kini SELURUH kelompok resmi (±90 entri) terverifikasi lampiran KMK;
  aset yang dulu "tanpa referensi" kini langsung tersusutkan benar.
- **Alur sesuai KMK 295 Diktum KEENAM**: pengakuan tambahan umur dilakukan
  saat penyerahan pekerjaan lewat **Berita Acara Serah Terima** — dialog
  "Posting 202" di Pemeliharaan kini memuat **pratinjau** (% biaya, jenis
  per tabel, tambahan tahun) + form BA (nomor otomatis `BA-PRB/xxx/tahun`,
  tanggal serah terima, pihak menyerahkan/menerima); posting menerapkan
  nilai (jurnal 202) DAN `masa_manfaat_tambah_tahun` ke aset (idempoten CAS).
- **BA Perbaikan (PDF)** dapat diunduh per catatan — kop satker, identitas
  aset, uraian/biaya/%, jenis, tambahan umur, dasar hukum, ttd 2 pihak
  (smoke-test FakeDB → pypdfium2 lolos).
- **Penyusutan ikut umur baru di semua konsumen**: `status_susut` menambah
  `masa_manfaat_tambah_tahun` aset → Penilaian, DBKP/Posisi BMN, LBP, dan
  laporan lain otomatis memakai masa manfaat + tambahan (proyeksi kelima
  titik panggil dilengkapi field baru).
- Badge riwayat: **"Masa manfaat +N th"** + tombol **BA Perbaikan** pada
  catatan yang sudah diposting.

## [#455] Referensi Akun BAS — daftar SEMUA akun belanja aset & persediaan dari master (dapat difilter) — 2026-07-19

Menjawab: "referensi BAS di halaman aset belum mengambil dari master; agar
semua akun belanja terkait aset & persediaan dapat difilter."

- **Tab Aset** kini punya kartu **"Akun belanja modal terkait aset (dari
  master BAS)"** — menarik SEMUA akun **belanja modal 53xxxx** dari master
  referensi BAS (`/referensi-akun?segmen=53`), ditandai golongan neracanya
  (531 Tanah · 532 Peralatan & Mesin · 533 Gedung & Bangunan · 534
  Jalan/Irigasi/Jaringan · 536 Aset Tetap Lainnya). Bisa **dicari** + **chip
  filter per golongan**.
- **Tab Persediaan** kini punya kartu **"Akun belanja persediaan terkait
  (dari master BAS)"** — SEMUA akun **belanja barang persediaan 5218xx**
  (`/referensi-akun?segmen=5218`), dapat dicari.
- Data diambil langsung dari master referensi BAS (segmen prefix), bukan
  daftar terpisah — sehingga selalu sinkron dengan master.

## [#454] Impor SIMAN V2 memperbarui masa manfaat per kelompok dari kolom "Umur Aset" (SIMAN menang) — 2026-07-19

Menjawab kebutuhan: peraturan masa manfaat (KMK) terus berubah — daripada
bergantung pada revisi, sistem BELAJAR masa manfaat dari data lapangan SIMAN.

- **Tiap impor SIMAN V2**, kolom "Umur Aset" dirangkum per **KELOMPOK 5 digit**
  lalu **langsung memperbarui** referensi masa manfaat kelompok terkait
  (pilihan pemilik: "SIMAN menang"). Terkumpul sedikit demi sedikit dari
  banyak impor.
- **Pengaman**: hanya golongan yang disusutkan (3/4/5) & nilai tahun wajar
  (1–60) yang dipakai; nilai absurd/di luar rentang diabaikan agar penyusutan
  tak rusak. Per kelompok diambil **modus** (nilai tersering; seri → terkecil,
  konservatif). Fungsi murni `masa_manfaat_dari_siman` + uji unit.
- **Transparan**: entri hasil SIMAN ditandai sumber **"dari SIMAN · N
  observasi"** (biru) di Referensi Masa Manfaat (Penilaian); admin tetap bisa
  menimpa manual (jadi "input satker"). Kartu Sinkronisasi SIMAN menampilkan
  "N kelompok masa manfaat diperbarui" pada ringkasan impor terakhir.
- Berlaku ke seluruh perhitungan penyusutan Penilaian & DBKP karena memakai
  peta masa manfaat gabungan (DB menimpa bawaan riset KMK).

## [#453] Pembukuan jurnal — ikon cari HP tak melorot + Penilaian masa manfaat +jo. KMK 339/2024 — 2026-07-19

- **Pembukuan (tab Jurnal) — ikon cari di HP**: ikon `Search` dipindah ke
  wrapper relatif khusus input; sebelumnya `top-1/2`-nya ikut menghitung tinggi
  teks bantuan di bawah kotak → ikon melorot ke bawah ("berantakan kebawah" di
  HP). Kini sejajar vertikal di tengah kotak cari.
- **Penilaian — Referensi Masa Manfaat**: judul & subjudul kini menulis
  peraturan **KMK 295/2019 jo. 266/2023 jo. 339/2024** (peraturan masa manfaat
  yang terus diperbarui) — sesuai umpan balik agar informasi peraturan
  tertulis di judul.

## [#452] Master Pegawai toolbar ikon-representatif + filter/toolbar 1 baris di iPad mini (Pegawai/Persuratan/Persediaan) + PDF Neraca masuk menu Lain — 2026-07-19

Umpan balik tata letak (fokus tablet iPad mini 768×1024):

- **Toolbar Master Pegawai**: kolom cari dipanjangkan; tombol Struktur,
  Template, Ekspor, Impor, dan Tambah menjadi **tombol ikon-saja** dengan ikon
  yang lebih menggambarkan fungsinya (Struktur=bagan `Network`, Template=unduh
  berkas `FileDown`, Ekspor=lembar Excel `FileSpreadsheet`, Impor=unggah
  `Upload`, Tambah=tambah orang `UserPlus`) + tooltip/aria-label. Menu ⋯
  sebelumnya dibuang — semua aksi kini tampil sebagai ikon.
- **Baris filter/sortir jadi 1 baris di tablet (md, 768)**: di Master Pegawai
  (Kepegawaian · Status · Unit · Urut + arah) kini `flex-nowrap` berbagi lebar
  rata mulai md; di HP tetap grid 2 kolom.
- **Registrasi Persuratan**: toolbar (cari + filter jenis/status + 2 aksi)
  dipadatkan (label aksi diringkas s.d. lg) agar muat **1 baris** mulai md;
  di HP tetap 2 baris.
- **Master Persediaan**: baris filter status + gudang dijadikan **1 baris**
  mulai md (`flex-nowrap`).
- **Arsip Pelaporan — "Posisi BMN di Neraca"**: tombol **Unduh PDF** dipindah
  menjadi item **paling atas** di menu **"Lain"** (Laporan Lain) — baris tombol
  jadi 4 (Lain · LBKP · CaLBMN · LBP), lebih hemat ruang.

## [#451] Saklar mode Dashboard/Inventarisasi ikon-saja di desktop + umur aset SIMAN V2 ditampilkan — 2026-07-19

- **Saklar Dashboard ↔ Inventarisasi ikon-saja di desktop (lg+)**: di layar
  besar, saklar mode kini hanya menampilkan ikon (Dashboard/Inventarisasi)
  tanpa teks — hemat ruang di baris statistik. Label tetap tersedia lewat
  `title`/`aria-label` (tetap ramah pembaca layar). Breakpoint tablet & HP
  tetap berlabel seperti sebelumnya (`iconOnly` hanya di instans lg+).
- **Kolom "Umur Aset" impor SIMAN V2 kini dimanfaatkan di UI**: nilai umur
  aset yang diparse & disimpan pada subdoc `siman.referensi` saat sinkronisasi
  kini ditampilkan pada baris "Referensi SIMAN" di kartu Sinkronisasi SIMAN
  (bersama nilai penyusutan & nilai buku) — sebelumnya sudah tersimpan namun
  belum pernah ditampilkan.


## [#450] Wasdal 1-baris + kartu padat, baris unduh Neraca satu kesatuan, toolbar Pegawai rapi, popup TTD ringkas — 2026-07-19

Lanjutan umpan balik screenshot HP (5 perbaikan tata letak seluler):

- **Header Wasdal Pemantauan cukup 1 baris di HP**: kelompok aksi header
  (menu Laporan, muat ulang, booking nomor) tak lagi menumpuk ke baris kedua
  — `flex-wrap`/`basis-full` dilepas, jarak dirapatkan (`gap-1.5`), semua
  ikon-only tetap sebaris.
- **Kartu dashboard per-objek Wasdal dioptimalkan**: dari kartu vertikal
  (ikon-atas · angka-tengah · label-bawah) menjadi kartu **horizontal padat**
  ala `StatKartu` (ikon kecil di kiri, angka + label menumpuk di kanan).
  Perilaku klik (buka rincian), keadaan tertib (`n===0`, hijau/nonaktif), dan
  `data-testid` dipertahankan.
- **Arsip Pelaporan — "Posisi BMN di Neraca" jadi satu kesatuan**: tombol
  **LBP** dipindah ke baris yang sama dengan PDF · Lain · LBKP · CaLBMN
  (grid `grid-cols-5` di HP, sebaris di desktop). Teks diperkecil
  (`text-[11px]`) + padding dirapatkan agar kelima tombol pas tanpa melebihi
  batas kartu.
- **Toolbar Master Pegawai ditata ulang untuk HP**: tombol data (Struktur ·
  Template · Ekspor · Impor) dilipat ke **satu menu ⋯** di HP (tetap terpisah
  berlabel di desktop); pencarian + menu + tombol Tambah kini muat satu baris.
  Baris filter (Kepegawaian · Status · Unit · Urut + arah) menjadi **grid 2
  kolom** rapi di HP (bukan membungkus berantakan), jumlah pegawai di baris
  info tipis.
- **Popup detail TTD dirapikan lebih lanjut**: tiga aksi unduh (Lembar
  Pengesahan · Dokumen Asli · Dokumen ber-TTD) dilipat ke satu menu **Unduh**
  di footer — footer tak lagi menumpuk penuh-lebar/berantakan di HP; baris
  tetap mendatar & membungkus rapi, kontainer penanda tangan `min-w-0` agar
  tidak meluber keluar kartu.


## [#449] Kartu ringkasan dashboard modul jadi padat (StatKartu) + popup TTD rapi + tombol Laporan Wasdal ikon — 2026-07-19

Umpan balik screenshot HP:

- **Kartu ringkasan modul lebih padat** (`StatKartu` bersama): kartu
  statistik vertikal boros ruang (ikon-atas · angka-tengah · label-bawah)
  diganti menjadi kartu horizontal ringkas ala baris "Aset per Pemegang" —
  ikon tertinta kecil di kiri, angka + label menumpuk di kanan. Diterapkan
  di 11 halaman: Pemindahtanganan, Penghapusan, Pemusnahan, Penilaian,
  Pemeliharaan, Pengamanan, Pengadaan, Pemanfaatan, Penganggaran,
  Perencanaan, Persediaan. Semua angka/label/testid & aksi "lihat daftar"
  dipertahankan; komponen tunggal agar konsisten & tidak drift.
- **Popup TTD elektronik dirapikan**: dialog detail permintaan tanda tangan
  memakai padding lebih pas di HP (`p-4`) + `min-w-0`/`overflow-hidden` pada
  baris penanda tangan agar isi tidak meluber keluar kartu.
- **Tombol Laporan di header Wasdal** menjadi ikon persegi saja (tanpa teks
  & chevron) — seragam dengan tombol ikon lain.


## [#448] Kodefikasi — 6 segmen filter benar-benar muat 1 baris di HP — 2026-07-19

Lanjutan #447: pada layar HP keenam segmen (Semua…Sub-sub) masih terpotong
karena padding/font terlalu besar. Kini font mengecil ke `text-[10px]` +
padding rapat (`px-0.5`) di layar kecil (kembali normal di desktop),
sehingga keenamnya muat penuh & rata dalam satu baris tanpa terpotong atau
menggulir.


## [#447] Referensi Kodefikasi Barang — toolbar padat 1 baris + filter segmented utuh — 2026-07-19

Umpan balik screenshot: toolbar hemat ruang.

- **Baris cari selalu 1 baris**: tombol Tambah/Impor/Unduh menjadi tombol
  ikon kotak (10×10) — tidak lagi membungkus ke baris kedua di HP.
- **Filter level jadi satu bagian utuh**: chip Semua/Golongan/Bidang/
  Kelompok/Sub/Sub-sub diganti *segmented control* bersambung dalam satu
  kotak berbingkai, satu baris penuh, menggulir horizontal bila layar
  sempit (tak lagi pecah dua baris). Tiap segmen membagi lebar rata.


## [#446] Gerbang perhitungan MENYELURUH — semua modul konsumen data aset tersapu — 2026-07-19

Tindak lanjut mandat "belum semua modul tersentuh": sapuan total seluruh
titik baca koleksi aset di backend (audit agen per file), gerbang
layak-hitung + anti-dummy kini terpasang di SEMUA modul konsumen
(total 31 titik panggilan di 13 file route):

- **Pembukuan (kritis)**: `POST /pembukuan/mutasi/backfill` — backfill
  saldo awal Buku Barang sebelumnya MENULIS jurnal dari SEMUA aset lintas
  kegiatan & lintas satker; kini ber-scope satker + gerbang layak-hitung
  (jurnal sintetis tidak lagi tercipta dari kegiatan yang belum sah).
- **Kandidat otomatis lintas modul**: BMN idle (Penggunaan), kandidat
  pemanfaatan, kandidat penghapusan per jalur (juga dipakai kandidat RB
  Pemusnahan), kandidat PSP dari SIMAN.
- **Rekap & statistik**: rekap pemegang (list + drill-down aset per
  pemegang + PDF Daftar Barang yang Digunakan), total aset ringkasan
  register PSP, hitung aset per NIP (panel "Perlu Serah Terima" Master
  Pegawai + daftar aset per pegawai + temuan pemegang berisiko Wasdal
  yang memakainya).
- **Kesehatan data & integritas**: ringkasan pengamanan + daftar aset
  berkekurangan; cek integritas kodefikasi (per akun + kartu ringkas).
- Yang dikonfirmasi TETAP tanpa gerbang (by design): tampilan per
  kegiatan di modul Inventarisasi (list/stats/ekspor/laporan LHI-BAHI/
  pengesahan/stiker/kartu), Timeline Aset (lintas kegiatan memang
  tujuannya), operasi per-aset yang dipilih manual pengguna, alat
  pembersih duplikat, rekonsiliasi SIMAN (membandingkan seluruh catatan
  memang fungsinya), dan guard penghapusan master (harus melihat semua).


## [#445] Gerbang perhitungan: data inventarisasi belum sah & dummy tidak ikut modul lain — 2026-07-19

Mandat: kegiatan inventarisasi yang masih berjalan tidak boleh mewarnai
angka modul lain, dan data dummy bukan aset.

- **Aturan gerbang (helper murni `layak_hitung_kegiatan`)**: data kegiatan
  hanya ikut perhitungan lintas modul bila kegiatan **disahkan** ATAU
  **tanggal selesainya sudah lewat** (fase selesai / belum lengkap).
  Kegiatan **belum dimulai / sedang berlangsung / menunggu validasi**
  tetap berada di lingkup modul Inventarisasi saja. Catatan: "Validasi"
  di UI adalah tampilan sementara dari kegiatan yang tanggal selesainya
  sudah lewat — di server selalu terurai menjadi selesai/belum lengkap,
  keduanya masuk hitungan sesuai pengecualian mandat.
- **Dummy bukan aset**: aset berkategori mengandung "dummy" (penanda uji
  yang sama dengan blokir pengesahan) disaring dari semua perhitungan
  (`tanpa_dummy_filter`).
- **Dipasang di 14 titik perhitungan** via perakit `filter_aset_perhitungan`
  (iris dengan scoping satker): Posisi BMN di Neraca, DBR, KIR, Laporan
  Penyusutan (PDF + JSON Penilaian), LKB, LBKP, CaLBMN, Rekonsiliasi SAKTI
  XLSX, DBKP JSON Pembukuan, pengayaan Referensi Akun BAS (beranda modul),
  kandidat & sanding RKBMN Perencanaan, portofolio + lampiran PMK 207
  Wasdal, dan generator LBP.
- **Yang sengaja TIDAK berubah**: tampilan dalam modul Inventarisasi
  (daftar aset per kegiatan, statistik kegiatan, pengesahan), Timeline
  Aset (riwayat menampilkan semua kegiatan), dan picker aset operasional.
- Catatan transparansi di hub Pelaporan (kartu Posisi BMN) + 2 unit test
  baru untuk aturan gerbang & filter dummy; smoke LBP membuktikan aset
  kegiatan berjalan dan aset dummy tidak bocor ke dokumen.


## [#444] LBP selengkap dokumen contoh — surat pengantar, kebijakan lengkap, mutasi per transaksi, lampiran a–i — 2026-07-19

Generator LBP dilengkapi penuh mengikuti seluruh struktur dokumen contoh
(258 paragraf + 28 tabel pada data uji; sebelumnya 136 + 16):

- **Surat Pengantar** resmi ber-ttd KPB + nomor halaman otomatis di footer.
- **Kebijakan Akuntansi yang Signifikan LENGKAP** (8 sub-bab seperti
  contoh): Persediaan (FIFO + 3 dasar nilai), Aset Tetap (6 jenis + KDP),
  Aset Lainnya, Kebijakan Penyusutan (objek/non-objek/garis lurus
  semesteran), Amortisasi (5 objek ATB), Kapitalisasi (ambang dari setelan
  satker), Pencatatan Rusak Berat & Hilang, Akuntansi Berbasis Akrual +
  butir Jumlah Satuan Kerja.
- **Nilai BMN diperkaya**: tabel Perkembangan Nilai BMN vs saldo awal
  periode (peningkatan/penurunan + terbilang) dan Komposisi BMN per jenis
  aset (narasi saldo per golongan).
- **Bagian II lengkap a–k**: + Barang Bersejarah, BPYDS, Hibah DK/TP
  (nihil default) — judul k menjadi "Penyusutan dan Amortisasi".
- **CaLBMN per golongan selengkap contoh**: narasi saldo + terbilang,
  tabel 8-kolom Gabungan/Intra/Ekstra, **rincian mutasi per kode
  transaksi dari jurnal Buku Barang** (pola "Kode | Uraian | Kuantitas |
  Rupiah" — saldo awal 000 + 101 pembelian + 301 penghapusan dst., kode
  3xx/4xx otomatis negatif), dan **rincian tanah per NUP** (No/Kode/Nama/
  NUP/Nilai/Keterangan, batas 150).
- **3.5 Informasi BMN Lainnya lengkap**: ringkasan register, Dokumen
  Sumber Tanah (jumlah NUP + nilai), daftar **BMN Bersengketa** dari
  register pengamanan (aset · kategori · pihak lawan · status), bagian
  Permasalahan + Langkah Strategis (diisi satker). **3.6 Tindak Lanjut
  Temuan Pemeriksaan** dengan kerangka tabel LHP.
- **LAMPIRAN a–i berisi data nyata**: PNBP dari pemanfaatan (setoran
  ber-NTPN per periode + total terbilang), polis pengasuransian BMN,
  BMN rumah negara, BAR internal & neraca percobaan (penanda sisip),
  transfer masuk/keluar & hibah dari jurnal Buku Barang, daftar BMN
  hilang yang diusulkan (jalur tidak ditemukan), ringkasan wasdal.
- Helper murni baru `susun_mutasi_per_transaksi`, `kebijakan_akuntansi_lbp`,
  `struktur_daftar_isi_lengkap`, `LABEL_TRANSAKSI_LBP` + 2 unit test.


## [#443] Generator Laporan Barang Pengguna (LBP) .docx per satker — 2026-07-19

Fitur besar: aplikasi kini dapat MENYUSUN sendiri dokumen LBP lengkap per
satker — format dipelajari mendalam dari dokumen resmi "LBP Otorita Ibu
Kota Nusantara Tahun 2025 Audited" (1.032 paragraf + 61 tabel dianalisis
struktur per strukturnya):

- **Endpoint `GET /pelaporan/lbp-docx?tahun=&semester=`** merakit .docx:
  sampul (instansi/satker/kode/posisi), **Kata Pengantar** ber-ttd KPB,
  daftar isi, **Bab I Overview** (gambaran umum + nilai netto terbilang,
  12 dasar hukum baku, ruang lingkup, kebijakan umum, kebijakan akuntansi
  signifikan — FIFO, garis lurus semesteran, ambang kapitalisasi dari
  setelan — dan tabel nilai BMN), **Bab II Laporan** (posisi per golongan
  intra/ekstra/total, persediaan per akun 117xxx, laporan Intrakomptabel/
  Ekstrakomptabel/Gabungan saldo awal+tambah−kurang=akhir, KDP, ATB,
  penyusutan per golongan), **Bab III CaLBMN** (ringkasan mutasi per
  golongan dipecah Gabungan/Intra/Ekstra seperti format resmi, BMN per
  akun neraca + akumulasi penyusutan per akun 137xxx/169xxx, tabel
  **Perbandingan Laporan Barang vs Laporan Keuangan**, informasi BMN
  lainnya dari register nyata: PSP/idle/sengketa/penertiban), penutup
  ber-ttd. Semua angka dari mesin laporan teruji (build_dbkp_rows,
  build_lbkp_rows, rekap_penyusutan, FIFO persediaan) — lingkup per
  satker (M-SCOPE), kop & penandatangan dari resolusi satker.
- **Helper murni `lbp_utils.py`** (+6 unit test): posisi per akun neraca,
  akumulasi per akun, perbandingan LB-LK, blok mutasi per golongan,
  terbilang rupiah, struktur daftar isi.
- **.docx sengaja dipilih** agar satker mudah menyunting narasi lokal
  (tindak lanjut BPK, permasalahan, dokumen sumber tanah) sebelum tanda
  tangan — meniru alur penyusunan LBP sungguhan.
- **UI**: dropdown "LBP" baru di hub Pelaporan (Semester I/II/Tahunan +
  tahun lalu, ikut penanda FINAL periode terkunci).


## [#442] Tombol kotak seragam: tanggalan bersama (Perencanaan + Penilaian), Unduh persegi, Catat ikon — 2026-07-19

Tindak lanjut screenshot pengguna — semua kontrol header memakai kotak
tombol yang sama persis dengan tombol kembali/Booking Nomor:

- **Komponen bersama `TanggalanButton`** (kotak 9×9 gaya tombol header):
  strip bulan berwarna, angka tanggal besar, tahun kecil — dipakai di
  **Perencanaan** (tanggal acuan TA, strip biru) dan kini juga di
  **Penilaian — Posisi Penyusutan** (menggantikan input date polos
  "posisi per tanggal", strip ungu; testid `penilaian-tanggal` tetap).
- **Tombol menu Unduh Perencanaan** menjadi persegi ikon murni (9×9,
  gaya sama dengan tombol kembali) — tidak ada lagi kotak beda ukuran.
- **Pemeliharaan**: tombol "Catat" di header menjadi ikon **+** saja
  (persegi, tooltip "Catat pemeliharaan"; testid tetap).


## [#441] Audit jangkauan referensi & master data lintas modul — tutup gap tersisa — 2026-07-19

Audit menyeluruh (agen riset kode): apakah referensi/master data +
administrasi/alat sudah menjangkau SEMUA modul dengan satu sumber yang
sama. Hasil: sebagian besar SUDAH tersambung benar (penanda tangan dari
Referensi Pejabat, pengguna aset tervalidasi keras ke Master Pegawai,
lokasi aset → Master Ruangan, kodefikasi ber-picker, tombol Booking Nomor
sudah ada di 14 halaman modul; pihak eksternal seperti mitra pemanfaatan/
JPN/penilai KPKNL memang tepat dibiarkan bebas). Gap tersisa ditutup:

- **Pihak asal & tujuan proses penggunaan** (alih status/pinjam pakai)
  kini menyarankan **Master Satker** (datalist; ketik bebas tetap boleh).
- **Satu sumber opsi kondisi & status**: `BatchEditPanel` dan `AssetForm`
  berhenti mendeklarasikan daftar Baik/Rusak Ringan/Rusak Berat dan status
  inventarisasi sendiri — kini mengimpor `CONDITION_OPTIONS`/
  `STATUS_OPTIONS` dari `InventoryFieldSheet` (sumber tunggal sesuai
  konvensi repo).
- **Reset konsisten**: `referensi_akun_meta` (penanda versi seed referensi
  akun) ikut dipertahankan saat reset — konsisten dengan `referensi_akun`.

**Verifikasi backup/restore/reset (mandat)**: TIDAK ada gap — daftar
koleksi dienumerasi DINAMIS (`db.list_collection_names()`), sehingga semua
koleksi baru (timeline, PSP, unit kerja, dst.) otomatis tercakup; yang
dikecualikan hanya data transien yang memang benar dikecualikan (lock TTL,
OTP, progress job, dedup replay, bus realtime, cache preview). GridFS
di-backup/restore terpisah. Reset mempertahankan akun + seluruh master
referensi.

## [#440] Ekspor Master Pegawai ke Excel siap-edit (dropdown + round-trip impor) — 2026-07-19

Tombol **Ekspor Excel** baru di Master Pegawai menghasilkan .xlsx yang
mudah diekstrak, diedit, lalu diimpor kembali:

- **Tampilan rapi**: header biru beku (freeze A2 + kolom NIP & Nama),
  auto-filter, zebra baris, lebar kolom proporsional, border halus.
- **Dropdown di dalam file** (data validation dari sheet Referensi): Jenis
  Kelamin, Status Kepegawaian (termasuk sub-kategori Non-ASN), Kategori
  Pegawai, Jenis Kontrak Non-ASN, Nama Bank, Status — berlaku juga untuk
  500 baris kosong tambahan; nilai di luar daftar tetap boleh (peringatan
  lunak). Sheet **Referensi** menampilkan daftar nilai sah.
- **Round-trip impor**: header = header impor; setiap label ekspor dipilih
  agar normalisasi impor mengembalikannya ke kode semula (teruji unit,
  termasuk sub-kategori Non-ASN "Satpam" dkk. dan jenis kontrak
  outsourcing + perusahaan penyedia). Kolom NIP/NPWP/rekening/kode satker
  dipaksa format teks — tidak rusak jadi float oleh Excel.
- **Kolom impor bertambah** (kompatibel mundur): TMT Jabatan, Tgl Akhir
  Jabatan, NPWP, Pendidikan Terakhir, Alamat, Jenis Kontrak Non-ASN,
  Perusahaan Penyedia, Kode Satker Lengkap, Unit Kerja — plus normalisasi
  baru kategori pegawai (label↔kode) & jenis kontrak.
- **Perbaikan bug**: status "Nonaktif" dulu salah ternormalkan jadi
  "aktif" saat impor (substring); kini dikenali benar.

## [#439] Header Perencanaan rapi + tombol tanggalan ringkas — 2026-07-19

Header halaman Perencanaan Kebutuhan tidak lagi penuh tombol:

- **Tombol tanggalan persegi** menggantikan select "TA" polos: kotak
  seukuran tombol (strip bulan berwarna, angka tanggal besar, tahun kecil)
  yang langsung berubah mengikuti tanggal yang dipilih — klik membuka
  pemilih tanggal; TA riwayat biaya otomatis mengikuti tahun tanggal
  terpilih. Ringkas, informatif, tetap berbentuk tombol.
- **Dua tombol unduh digabung** menjadi satu menu "Unduh" (Kertas Kerja
  RKBMN XLSX + Register Usulan CSV) — pola sama dengan menu Laporan Wasdal;
  data-testid lama dipertahankan pada item menu.

## [#438] Pengenal barang lintas kegiatan inventarisasi (arsitektur W5 tahap 3 — penutup) — 2026-07-19

Penutup mandat W5: sistem kini MENGENALI bahwa barang yang sama tercatat
di beberapa kegiatan inventarisasi — dan menampilkannya sebagai informasi,
bukan masalah (kegiatan = pemutakhir berkala, bukan induk):

- **Backend `GET /inventarisasi/aset-lintas-kegiatan`**: agregasi Mongo
  mengelompokkan aset per identitas (kode barang + NUP), hanya kelompok
  yang menyentuh >1 kegiatan yang dikembalikan, lengkap dengan status
  inventarisasi/kondisi per kegiatan (terbaru dulu) + info tiket & status
  pengesahan tiap kegiatan. Helper murni `susun_kelompok_lintas_kegiatan`
  + unit test; scoping satker M-SCOPE; batas 200 kelompok.
- **UI halaman Kegiatan Inventarisasi**: panel lipat "N barang dikenali
  tercatat di lebih dari satu kegiatan" — tiap barang menampilkan chip per
  kegiatan (tiket · status · kondisi, ✓ = disahkan; hijau = catatan
  termutakhir), dengan penjelasan bahwa Timeline Aset menggabungkan
  otomatis dan tidak ada data yang perlu dihapus.
- Masterplan Bab 5A gap #9 kini TUNTAS penuh (timeline + PSP SIMAN +
  pengenal lintas kegiatan).

## [#437] PSP resmi SIMAN V2 → register SK PSP 1-klik (arsitektur W5 tahap 2) — 2026-07-19

Lanjutan pemanfaatan data impor SIMAN V2: kolom No. PSP / Tgl PSP / Status
Penggunaan hasil impor kini benar-benar MENGALIR ke modul Penggunaan —
bukan sekadar tampil di timeline:

- **Backend `GET /penggunaan/psp-siman`**: mengelompokkan seluruh aset yang
  punya PSP resmi menurut SIMAN (per nomor PSP), menandai mana yang sudah/
  belum ada di register SK PSP (normalisasi kapital/spasi nomor), dan
  menghitung aset yang belum tercakup SK manapun. Helper murni
  `kelompokkan_psp_siman` + 3 unit test; scoping satker M-SCOPE.
- **UI Penggunaan — panel "PSP resmi menurut SIMAN V2 belum tercatat"** di
  atas register SK PSP: daftar nomor PSP + tanggal + jumlah aset + status,
  dengan tombol **Catat 1-klik** yang membuka form Catat SK terisi otomatis
  (nomor SK, tanggal, daftar aset yang belum tercakup, keterangan sumber)
  — tinggal tinjau lalu simpan; panel menyegarkan diri setelah SK tercatat.
- Prinsip: SIMAN tetap sumber otoritatif — AMAN tidak menulis diam-diam;
  pencatatan selalu lewat tinjauan pengguna (form prefilled, bukan auto).

## [#436] Timeline Aset — induk data = identitas aset lintas modul (arsitektur W5 tahap 1) — 2026-07-19

Jawaban arsitektural atas masalah lama: sistem menjadikan data inventarisasi
sebagai induk, padahal aset fisik yang sama tercatat ulang di tiap kegiatan
inventarisasi (satu dokumen aset per kegiatan). Kini **induk data =
identitas aset** (`kode_register` dari SIMAN → fallback kode barang + NUP)
dan seluruh perlakuannya lintas modul tersaji sebagai satu garis waktu:

- **Backend `GET /assets/{id}/timeline`** (route baru `timeline.py` + helper
  murni `timeline_utils.py`, 7 unit test): otomatis menemukan semua dokumen
  aset ber-identitas sama lintas kegiatan ("saudara"), lalu menggabungkan
  event dari: pencatatan & pengesahan inventarisasi (lintas kegiatan), Buku
  Barang/mutasi, SK PSP + BMN idle + proses Penggunaan, Pemanfaatan,
  Pemeliharaan, kasus & dokumen Pengamanan, koreksi nilai Penilaian, usulan
  & SK Penghapusan, Pemindahtanganan, BA Pemusnahan, penertiban Wasdal,
  BAST, reklasifikasi, dan audit log — semua diurutkan terbaru dulu, dengan
  ringkasan jumlah per modul. Scoping satker ikut aturan M-SCOPE.
- **Data SIMAN V2 yang menganggur kini dimanfaatkan**: `no_psp`,
  `tanggal_psp`, `status_penggunaan`, `status_bmn` dari referensi impor
  SIMAN diangkat menjadi blok "PSP resmi menurut SIMAN V2" + event timeline
  — modul lain tak lagi buta terhadap PSP yang sudah tercatat resmi.
- **UI `AssetTimelineDialog`** (lazy): tombol **Timeline** di header form
  aset (sebelah "Kartu") — badge jumlah kegiatan inventarisasi yang pernah
  mencatat aset ini, chip filter per modul, garis waktu berwarna per modul,
  light+dark, ramah HP.
- Menegaskan prinsip masterplan: kegiatan inventarisasi = **pemutakhir**
  berkala data barang, bukan induk. Masterplan Bab 5A diperbarui (gap #9).

## [#435] Semua form ber-referensi terhubung ke data lintas modul (picker/datalist) — 2026-07-19

Sapu menyeluruh 13 titik input teks bebas yang sebenarnya punya master data —
kini semuanya memberi saran isi (datalist: tetap bisa ketik bebas, tapi bisa
pilih dari data yang sudah ada) dan sebagian mengisi otomatis field terkait:

- **Buat/Edit Kegiatan** (`ActivitySelectionPage`): Penanggung Jawab, anggota
  **Tim Inti**, dan **Tim Pembantu** tersambung ke Master Pegawai — pilih nama
  → jabatan/NIP (dan unit utk tim) terisi otomatis; kolom unit tersambung ke
  Master Unit Kerja.
- **Penggunaan — form BAST**: nama Pihak Pertama kini juga pakai daftar pegawai
  (sebelumnya hanya Pihak Kedua) + isi otomatis NIP/jabatan.
- **Persediaan**: lokasi/gudang di form barang menyarankan gudang yang sudah
  dipakai; **unit penerima** (barang keluar & keluar massal) tersambung ke
  Master Unit Kerja.
- **Master Ruangan & Master Pejabat**: kolom unit kerja tersambung ke Master
  Unit Kerja.
- **Master Pegawai**: kolom unit kerja menyarankan unit dari Master Unit Kerja.
- **Wasdal — pemantauan insidentil**: lokasi menyarankan Master Ruangan
  (kode · gedung tampil sebagai keterangan).
- **Perencanaan — usulan RKBMN**: Unit/KPB pengusul tersambung ke Master
  Satker (kode satker tampil sebagai keterangan).
- **Pemeliharaan — catat pelaksanaan**: Pelaksana menyarankan Master Pegawai
  (jabatan · unit sebagai keterangan); penyedia jasa eksternal tetap bebas.
- **Referensi Akun — pemetaan golongan→akun aset**: input akun kini
  menyarankan akun neraca BMN dari master Segmen Akun (prefix 13 aset tetap,
  16 aset lainnya, 117 persediaan). Backend: param `segmen` di
  `GET /referensi-akun` kini menerima daftar prefix kode dipisah koma
  (kompatibel mundur dengan 1 digit; prefix tak valid diabaikan + unit test).

Prinsip: tidak ada dropdown kaku baru — semua pakai `datalist` sehingga alur
lama (ketik manual) tetap jalan, data lama tidak terkunci, dan form bekerja
walau master datanya kosong.

## [#434] Beranda "Peta Perjalanan Siklus BMN" — rombak total desain, informatif & fungsional, light+dark — 2026-07-19

Halaman awal Siklus Pengelolaan BMN dirombak total menjadi peta perjalanan
yang unik, padat informasi, dan langsung fungsional:

- **Hero ber-gradien** dengan ornamen lingkar siklus + **statistik hidup
  dari master** (jumlah aset & total nilai satker, endpoint referensi akun
  yang sudah tertaut master) + badge "16 modul aktif penuh" + asas
  pengelolaan.
- **Tiga FASE alur ber-timeline bernomor**: Perolehan (Perencanaan →
  Penganggaran → Pengadaan), Penggunaan & Pengelolaan (Penggunaan,
  Pemanfaatan, Penilaian, Pengamanan, Pemeliharaan), Pengakhiran
  (Pemindahtanganan, Pemusnahan, Penghapusan) — tiap modul jadi baris
  timeline ringkas (nomor tahap di garis putus-putus, ikon gradien khas
  per modul, ringkasan 1 baris, langsung klik untuk masuk).
- **Pita Wasdal** melintang "melingkupi seluruh siklus" — sesuai perannya.
- **Poros Penatausahaan** sebagai pusat: 4 sub-modul berkartu gradien +
  grup pintasan Referensi/Master & Administrasi (komponen pintasan
  seragam, kode lebih ramping).
- Identitas visual per modul (16 gradien ikon berbeda), micro-interaction
  (hover angkat/geser), dan seluruh warna memakai token tema + varian
  `dark:` — konsisten light mode & dark mode.
- Akses rahasia Info (3x klik logo), dialog konsep, dan seluruh
  `data-testid` navigasi dipertahankan.
- Verifikasi: eslint bersih, `yarn build` sukses.

---

## [#433] Master Pegawai pintar (2/2): filter & sortir lanjutan, kartu HP muat-layar, kolom durasi — 2026-07-19

Paruh kedua perombakan Master Pegawai:

- **Filter & sortir lanjutan** (pola halaman aset): filter status
  kepegawaian (PNS/PPPK/TNI/POLRI/Non-ASN), status di satker, unit kerja
  (dari data terpakai); urutkan Nama / Terakhir diubah / Terdekat pensiun /
  Kontrak berakhir / Jabatan / Unit + arah naik-turun + tombol Reset +
  penghitung hasil.
- **Tampilan HP = kartu muat-layar** (scroll vertikal saja): nama + label
  identitas terdeteksi (NIP/NI PPPK/NRP/NIK) + badge status; jabatan·unit;
  baris chip durasi; baris bawah "diubah X lalu" + tombol aksi ringkas.
- **Durasi di setiap baris**: "diubah X lalu" (update terakhir),
  "Pensiun X lagi" (perkiraan BUP — kuning bila <1 th), "Jabatan X lagi"
  (akhir periode — kuning bila <90 hr), "Kontrak X lagi" (Non-ASN — merah
  bila habis/segera). Desktop mendapat kolom "Masa" tersendiri.
- Badge **Outsourcing** (+nama perusahaan penyedia) tampil di daftar.
- Verifikasi: eslint bersih, `yarn build` sukses; 558 tes unit tetap lulus.

---

## [#432] Master Pegawai pintar (1/2): deteksi NIP/NI PPPK/NRP/NIK otomatis, BUP, outsourcing, kode satker, label laporan — 2026-07-19

Paruh pertama perombakan Master Pegawai (hasil riset regulasi: Perka BKN
22/2007, UU ASN 20/2023, UU TNI 3/2025, UU Polri 5/2026, PER-31/PB/2016):

- **Deteksi jenis nomor identitas OTOMATIS** (`deteksi_identitas`, satu
  sumber logika server): 18 digit ber-tanggal valid → NIP PNS (digit 13-14
  = bulan TMT) / NI PPPK (digit 13-14 ≥ 21 = frekuensi kontrak); 16 digit
  → NIK (Non-ASN); 8 digit → NRP POLRI; 5-7 digit → kemungkinan NRP TNI.
  Label field di form berubah otomatis + keterangan hasil deteksi.
- **Laporan menghormati jenis nomor**: label "NIP." di blok ttd BAST &
  BAST pengguna kini pintar — NRP berlabel "NRP.", dan **NIK Non-ASN
  TIDAK dicetak** (privasi); identitas pihak BAST melewati baris nomor
  utk pemegang ber-NIK.
- **Perkiraan pensiun (BUP)** per aturan terbaru: ASN JPT 60 /
  administrator-pengawas-pelaksana 58 / fungsional ahli utama 65 & madya
  60; TNI tamtama-bintara 55, perwira 58; POLRI 59/60 — `info_masa` per
  pegawai di API daftar (tanggal pensiun + sisa hari + sisa jabatan +
  status kontrak) sebagai bahan kolom durasi.
- **Field baru**: akhir periode jabatan; Non-ASN → jenis kontrak
  internal/outsourcing + nama perusahaan penyedia (wajib bila
  outsourcing); kode satker 6 digit + kode satker lengkap 12 digit
  (penghubung lintas modul; admin terikat tetap dipaksa satkernya —
  isolasi M-SCOPE dijaga).
- **Form kondisional per jenis pegawai**: Non-ASN tanpa pangkat & tanpa
  TMT jabatan (fokus kontrak); PPPK berlabel "Golongan I–XVII"; TNI/POLRI
  berlabel "Pangkat" dengan saran pangkat militer/polisi.
- Verifikasi: 558 tes unit lulus (4 baru: deteksi semua jenis, label
  laporan, BUP, validasi field baru), eslint & build sukses.

---

## [#431] Referensi Akun BAS tertaut master aset & persediaan + panel edukasi kodefikasi barang — 2026-07-19

Tab Aset & Persediaan di Referensi Akun BAS kini MENGAMBIL DATA DARI
MASTER (bukan sekadar aturan statis), plus panel pemahaman kodefikasi
hasil riset regulasi:

- **Tab Aset**: tiap baris golongan → akun kini menampilkan **isi nyata
  master** — jumlah NUP & total nilai buku aset aktif (ter-scope satker,
  nilai wajar revaluasi bila ada) yang memakai akun tersebut.
- **Tab Persediaan**: tiap akun 1171xx di katalog menampilkan **jumlah
  jenis barang & total nilai FIFO** dari master persediaan (resolusi
  override sub-kelompok → default), plus total keseluruhan.
- **Panel "Memahami Kodefikasi Barang BMN"** (dapat dilipat, di kedua
  tab) — hasil riset PMK 29/PMK.06/2010 jo. KMK 333/KM.6/2024: visual
  struktur 10 digit (golongan/bidang/kelompok/sub/sub-sub dengan contoh
  Lemari Besi/Metal 3.05.01.04.001), perlakuan per golongan (penyusutan
  PMK 65/2017, ambang kapitalisasi PMK 181/2016, golongan 5 ber-akun per
  bidang 134111/134112/134113, golongan 8 keluarga ATB 162xxx), dan
  kaitan kode ↔ akun ↔ master ↔ Reklasifikasi.
- Verifikasi: 554 tes unit lulus; smoke kedua endpoint dengan FakeDB
  (agregasi golongan & akun benar termasuk nilai wajar revaluasi); eslint
  bersih & build sukses.

---

## [#430] Perbaikan cepat UI: popup TTD meluber, header Wasdal menumpuk, kewarganegaraan tak bisa dipilih, row Persediaan HP sempit — 2026-07-19

Empat perbaikan dari umpan balik pengguna:

- **TTD Elektronik**: pop-up detail permintaan tidak lagi meluber keluar
  kotak — judul/teks panjang kini membungkus (`break-words`) dan dialog
  memotong luapan horizontal.
- **Wasdal**: header tidak lagi penuh tombol menumpuk — dua tombol unduh
  digabung jadi satu dropdown "Laporan" (Periode berjalan / Tahunan PMK
  207), dan seluruh aksi pindah ke baris tersendiri di HP.
- **Master Pegawai — BUG kewarganegaraan**: dropdown Kewarganegaraan (dan
  Jenis Identitas WNA, saran pangkat, peringatan digit bank) kosong karena
  pemetaan respons referensi di frontend membuang kuncinya. Kini seluruh
  kunci referensi diambil apa adanya — WNI/WNA bisa dipilih lagi.
- **Persediaan (HP)**: kolom Kode·NUP pindah jadi sub-baris di bawah nama
  barang (plus lokasi) dan badge status stok turun ke baris kedua — Nama
  Barang mendapat bagian yang luas, tanpa scroll samping.
- Verifikasi: eslint bersih 4 file, `yarn build` sukses.

---

## [#429] Integrasi lintas-modul gelombang 11 (pamungkas): reklasifikasi terdeteksi SIMAN dirutekan ke mesin Reklasifikasi resmi — 2026-07-19

Item terakhir backlog audit integrasi (15/15). Saat sinkron SIMAN
mendeteksi kode barang berbeda (= reklasifikasi di SIMAN), tombol
"Terapkan nilai SIMAN" selama ini MENIMPA kode begitu saja — tanpa jurnal
304/107, tanpa riwayat reklasifikasi, tanpa penataan NUP tujuan. Jejak
Buku Barang putus.

- **Guard backend**: `POST /siman/terapkan` kini MENOLAK (409) bila
  `asset_code` termasuk field yang diterapkan, mengarahkan ke mesin
  Reklasifikasi resmi; field lain tetap bisa diterapkan.
- **Tombol "Reklasifikasi → {kode baru}"** di kartu sinkron SIMAN: muncul
  otomatis pada aset yang selisih kode barangnya terdeteksi; konfirmasi
  berpenjelasan → `POST /pembukuan/reklasifikasi` (kode+NUP in-place,
  jurnal 304/107 berpasangan, riwayat tercatat, nilai & tanggal perolehan
  tetap). Pra-isi kode tujuan dari sinyal `siman.reklasifikasi` / selisih.
- Tombol "Terapkan nilai SIMAN" otomatis mengecualikan kode barang
  (berlabel "(selain kode)" bila ada selisih kode) — dua jalur terpisah
  yang jelas: timpa nilai vs reklasifikasi resmi.
- Verifikasi: 554 tes unit lulus; smoke guard (kode via sinkron → 409
  berpesan arahan; field lain tetap terapan & kode tak berubah); eslint
  bersih & build sukses.

---

## [#428] Integrasi lintas-modul gelombang 10: pemeliharaan kapitalisasi → pengembangan nilai aset (jurnal 202) — 2026-07-19

Modul Pemeliharaan selama ini hanya MENANDAI biaya ber-indikasi
kapitalisasi (badge "Telaah kapitalisasi", PMK 181) tanpa jalur menaikkan
nilai aset — kode jurnal 202 "Pengembangan Nilai Aset" ada di Buku Barang
tetapi tak pernah diproduksi. Kini alur lengkap:

- **Endpoint `POST /pemeliharaan/{id}/kapitalisasi`** (khusus admin —
  keputusan kualitatif "menambah masa manfaat/kapasitas?" tetap di
  manusia): nilai perolehan aset **bertambah** sebesar biaya (DBKP/Neraca
  ikut naik), **jurnal 202** tercatat di Buku Barang, catatan ditandai
  `kapitalisasi_diposting`. Idempoten via CAS — klik ganda/2 tab tidak
  bisa dobel-posting; version aset naik (bust cache/OCC).
- **Tombol "Posting 202"** di baris catatan ber-indikasi (admin) dengan
  dialog konfirmasi berpenjelasan; setelah diposting badge berubah jadi
  "Nilai dikapitalisasi ✓" dan tombol hilang.
- **Guard hapus**: catatan yang sudah diposting TIDAK bisa dihapus (nilai
  aset sudah bertambah — koreksi lewat register Penilaian), + audit log.
- Verifikasi: 554 tes unit lulus; smoke end-to-end (nilai 100jt→130jt,
  version naik, jurnal 202 tercatat, dobel-posting & hapus terblokir 409);
  eslint bersih & build sukses.

---

## [#427] Integrasi lintas-modul gelombang 9: kasus BMN bermasalah aktif ikut terhitung sengketa — 2026-07-19

Register kasus BMN bermasalah di Pengamanan (dikuasai pihak lain /
sertipikat tumpang tindih / berperkara) selama ini tidak memengaruhi
temuan sengketa mana pun — deteksi sengketa hanya membaca field master
aset. Read-side join (master TIDAK dimutasi, tanpa risiko regresi):

- **Dasbor Wasdal**: aset ber-kasus AKTIF (belum selesai) kini tampil
  sebagai temuan `sengketa` objek Pengamanan & Pemeliharaan walau master
  belum menandai — detail memuat kategori kasus, pihak lawan, dan nomor
  perkara. Tidak dobel bila master juga sudah menandai.
- **CaLBMN Bab V**: butir Sengketa kini menghitung union {aset ber-tanda
  master} ∪ {aset ber-kasus aktif} — pengungkapan tak lagi bergantung
  kedisiplinan menandai master.
- Kasus berstatus "selesai" otomatis keluar dari hitungan.
- Verifikasi: 554 tes unit lulus (1 baru: kasus register-only ikut,
  dedup master+kasus, kasus selesai tak ikut), smoke dasbor end-to-end
  sukses.

---

## [#426] Integrasi lintas-modul gelombang 8: opname terlambat & persediaan kedaluwarsa jadi temuan Wasdal — 2026-07-19

Register Persediaan sudah menghitung status opname semesteran dan layer
kedaluwarsa (FIFO), tetapi dasbor Wasdal tidak pernah membacanya. Dua
temuan baru objek Penatausahaan (PMK 207):

- **`opname_semester_terlambat`**: satu temuan global bila semester
  berjalan belum ada opname fisik (PSAP 05 — wajib semesteran), lengkap
  dengan tanggal opname terakhir; hilang otomatis begitu opname dicatat.
- **`persediaan_kedaluwarsa`**: temuan per barang yang masih menyimpan
  layer kedaluwarsa — jumlah layer + unit + tanggal terlama + arahan
  usulkan penghapusan/pemusnahan (risiko lebih saji nilai persediaan).
- Fungsi murni `temuan_persediaan` memakai `status_opname_semester` &
  `klasifikasi_kedaluwarsa` yang sudah teruji di modul Persediaan; alarm
  opname hanya dibangkitkan bila pemanggil memasok data persediaan
  (pemanggil lama tidak memicu alarm palsu).
- Verifikasi: 553 tes unit lulus (1 baru), smoke dasbor Wasdal end-to-end
  (belum pernah opname + 1 barang kedaluwarsa → 2 temuan penatausahaan).

---

## [#425] Integrasi lintas-modul gelombang 7: setoran hasil penjualan BMN (NTPN) diungkap di narasi PNBP CaLBMN — 2026-07-19

Selama ini narasi PNBP di CaLBMN Bab V hanya menghitung kontribusi
pemanfaatan — setoran hasil PENJUALAN BMN (lelang/langsung) yang NTPN-nya
sudah tercatat di register Pemindahtanganan tidak pernah diungkap.

- Butir Pemindahtanganan Bab V kini menambah: jumlah **setoran hasil
  penjualan ber-NTPN ke Kas Negara** yang dilaksanakan dalam periode +
  total nilai wajar objeknya, dengan pengungkapan jujur bahwa nominal
  hasil lelang final mengikuti bukti setor/SAKTI (proceeds tidak terekam
  di register).
- Tanggal pelaksanaan diambil dari riwayat status "dilaksanakan" (saat
  NTPN diisi) dan difilter ke periode laporan; bentuk non-penjualan dan
  pelaksanaan di luar periode tidak ikut.
- Verifikasi: 552 tes unit lulus; smoke render CaLBMN dengan fixture
  campuran (1 penjualan dalam periode ikut, hibah & penjualan luar
  periode tidak) sukses.

---

## [#424] Integrasi lintas-modul gelombang 6: dokumen sumber perolehan kurang jadi temuan Wasdal — 2026-07-19

Item prioritas tinggi terakhir dari backlog audit integrasi: register
**Pengadaan** sudah menghitung dokumen sumber wajib per jenis perolehan
(pembelian: kontrak/BAPHP/BAST/kuitansi/SP2D; hibah: naskah hibah/BAST/
MPHL-BJS; dst.) tetapi dasbor Wasdal tidak pernah membacanya.

- **Temuan baru `dokumen_perolehan_kurang`** (objek Penatausahaan PMK 207):
  tiap perolehan yang checklist dokumen wajibnya belum lengkap otomatis
  muncul di dasbor pemantauan + laporan wasdal semesteran/tahunan, lengkap
  dengan daftar dokumen yang kurang — temuan klasik BPK "BAST/kontrak/SP2D
  tercecer".
- Fungsi murni `temuan_dokumen_perolehan` memakai `dokumen_kurang_perolehan`
  yang sudah teruji di modul Pengadaan (satu sumber kebenaran, tanpa
  logika ganda).
- Verifikasi: 552 tes unit lulus (1 baru: dokumen kurang → temuan; lengkap
  → tidak ikut; None → aman).

---

## [#423] Kejujuran klaim fitur aktif: tombol Backfill Saldo Awal, peringatan M07/K07, label jurnal 301/303 — 2026-07-19

Tiga temuan "diklaim aktif tapi tak berfungsi penuh" dari audit menyeluruh
kini dibereskan (mandat "periksa juga yang aktif"):

- **Tombol "Backfill Saldo Awal"** (admin) di tab Buku Barang Pembukuan —
  endpoint idempoten `POST /pembukuan/mutasi/backfill` sudah lama ada
  tetapi TIDAK punya pemicu di UI mana pun, sehingga aset lama tanpa
  transaksi tak pernah mendapat entri saldo awal (kode 100) dan Buku
  Barang tampil kosong/parsial. Kini ada tombol ber-konfirmasi + toast
  hasil (N dibuat / M sudah berjurnal) + muat ulang jurnal.
- **Peringatan M07/K07 Persediaan**: jenis transaksi "Reklasifikasi dari
  Aset"/"Reklasifikasi Keluar" hanya mencatat SISI PERSEDIAAN — register
  aset tidak disentuh otomatis. Dropdown ketiga dialog transaksi
  (masuk/keluar/massal) kini menampilkan peringatan amber: sesuaikan sisi
  aset via Pembukuan → Reklasifikasi (304/107) agar tidak dobel catat di
  Neraca. Info dikirim dari API (`info` per jenis).
- **Label badge modul Pembukuan diluruskan**: klaim jurnal pemindahtanganan
  "302/303" → "303 hibah / 301 bentuk lain" sesuai kode yang benar-benar
  dibukukan (302 Transfer Keluar belum pernah diproduksi alur mana pun).
- Verifikasi: 551 tes unit lulus, eslint bersih, `yarn build` sukses.

---

## [#422] Integrasi lintas-modul gelombang 5: cek-silang realisasi anggaran vs Pengadaan (BAST) — 2026-07-19

Realisasi NYATA dari Pengadaan bertaut kini disandingkan otomatis dengan
realisasi manual di modul Penganggaran (item #6 backlog audit integrasi):

- **Tabel "Sanding per Akun BAS"** bertambah kolom **Realisasi BAST**
  (total nilai perolehan Pengadaan yang bertaut per akun) dan **Selisih**
  (realisasi manual − BAST; kuning bila melewati toleransi) — serapan %
  tetap berbasis realisasi manual (benar secara akuntansi).
- **Badge "Perlu rekonsiliasi"** (amber) di baris usulan yang punya
  perolehan bertaut tetapi angka realisasi manualnya beda — termasuk kasus
  realisasi manual masih 0 padahal BAST sudah ada (perolehan belum ditaut
  ke realisasi). Tooltip menampilkan kedua angka.
- Fungsi murni baru `rekap_rekonsiliasi` (jumlah usulan perlu rekonsiliasi
  + total selisih) ikut di respons API; toleransi Rp1 utk beda pembulatan.
- Verifikasi: 551 tes unit lulus (2 baru), eslint bersih, `yarn build`
  sukses.

---

## [#421] Integrasi lintas-modul gelombang 4: nilai buku di CaLBMN & kolom Akun Neraca di ekspor rekonsiliasi — 2026-07-19

Dua item penatausahaan lanjutan dari backlog audit integrasi:

- **Penilaian → CaLBMN Bab IV**: Ikhtisar Nilai Buku (penyusutan garis
  lurus PMK 65/2017) kini tersaji langsung di CaLBMN — nilai perolehan
  tersusutkan − akumulasi = nilai buku, lengkap dengan lingkup jujur
  (habis/henti-susut/tanpa referensi/tidak disusutkan) dan disclaimer
  SAKTI. Kalimat Bab II yang merujuk "rekap tersedia pada halaman
  Penilaian" diperbarui merujuk Bab IV. Pola sama dengan Posisi BMN (#417).
- **Referensi Akun BAS → ekspor Rekonsiliasi XLSX**: sheet "Posisi
  Golongan" & "Rincian Aset" kini punya kolom **Akun Neraca** (mis.
  golongan 3 → 132111, persediaan → akun gol 1) sehingga operator langsung
  mencocokkan angka per akun di MonSAKTI tanpa membuka referensi terpisah —
  pola peta akun yang sama dengan Posisi BMN PDF.
- Verifikasi: 549 tes unit lulus; smoke render CaLBMN (Bab IV ikhtisar
  tampil) & pembacaan ulang XLSX via openpyxl (header + akun 132111 utk
  golongan 3 di kedua sheet) sukses.

---

## [#420] Integrasi lintas-modul gelombang 3: tiga peringatan dini baru di dasbor Wasdal — 2026-07-19

Lanjutan backlog audit integrasi (verifikasi adversarial) — tiga register
yang datanya sudah lengkap kini mengalir otomatis ke mesin temuan Wasdal
(PMK 207), dasbor pemantauan, dan laporan wasdal semesteran/tahunan:

- **Pemanfaatan → Wasdal**: perjanjian **jatuh tempo ≤60 hari** jadi
  peringatan dini `perjanjian_jatuh_tempo` — bentuk yang dapat diperpanjang
  (Sewa/Pinjam Pakai/KSP/KSPI) diarahkan "ajukan perpanjangan (batas ≥2
  bulan sebelum berakhir, PMK 115/2020)"; BGS/BSG yang tak dapat
  diperpanjang diarahkan siapkan pengakhiran/serah terima. Sebelumnya
  Wasdal baru bereaksi SETELAH perjanjian berakhir.
- **Pengamanan → Wasdal**: dokumen kepemilikan ber-`berlaku_sampai` lampau
  (STNK/pajak/IMB dsb.) jadi temuan `dokumen_kepemilikan_kedaluwarsa`
  objek pengamanan & pemeliharaan — padanan polis asuransi yang sudah ada.
  Dokumen tanpa masa berlaku (sertipikat) tidak dinilai kedaluwarsa.
- **Pemusnahan → Wasdal**: aset yang tercantum di **BA Pemusnahan** tetapi
  belum ada SK penghapusan jadi temuan `dimusnahkan_belum_dihapus`
  (fisik lenyap namun masih tersaji di neraca = risiko lebih saji) —
  lengkap dengan umur hari sejak tanggal BA.
- Tiga fungsi murni baru + 3 tes unit; label baru terender otomatis di
  dasbor (ikon per objek, label dari registry backend).
- Verifikasi: 549 tes unit lulus, smoke dasbor Wasdal end-to-end sukses
  (ketiga jenis temuan muncul di objeknya masing-masing).

---

## [#419] Integrasi lintas-modul gelombang 2: koreksi nilai di CaLBMN & pemegang berisiko jadi temuan Wasdal — 2026-07-19

Dua integrasi teratas hasil audit lintas-modul menyeluruh (5 klaster,
15 peluang terkonfirmasi lewat verifikasi adversarial):

- **Penilaian → CaLBMN (Bab V "Informasi BMN Lainnya")**: register
  Koreksi/Revaluasi Nilai kini diungkap sebagai butir tersendiri — jumlah
  peristiwa s.d. akhir periode, selisih nilai neto, dan berapa koreksi yang
  **belum tervalidasi di SAKTI** (bahan telusur auditor vs LHIP/Laporan
  Penilaian; revaluasi PMK 118/2017 jo. 57/2018 jo. 107/2019). Sebelumnya
  Bab V hanya memuat 6 butir tanpa pengungkapan perubahan nilai.
- **Master Pegawai → Wasdal (objek Penggunaan, PMK 207)**: pegawai BERISIKO
  (keluar/pensiun/mutasi/nonaktif/kontrak Non-ASN habis) yang **masih
  tercatat memegang aset** kini otomatis menjadi temuan
  `pemegang_berisiko_keluar` di dasbor pemantauan Wasdal — deteksi yang sama
  dengan panel "Perlu Serah Terima BMN" di modul Pegawai, tetapi kini
  mengalir ke dasbor kepatuhan & laporan wasdal semesteran/tahunan yang
  dilihat auditor (temuan klasik BPK "aset dipegang pegawai yang sudah
  keluar"). Fungsi murni `temuan_pemegang_berisiko` + teruji unit.
- Verifikasi: 546 tes unit lulus (1 tes baru), smoke render CaLBMN sukses
  (butir koreksi tampil), smoke dasbor Wasdal sukses (temuan masuk objek
  Penggunaan + rekap per jenis benar).

---

## [#418] UI mobile: kartu Arsip Pelaporan & buku agenda Persuratan tak lagi terjepit — 2026-07-19

Perbaikan dari umpan balik tangkapan layar HP:

- **Arsip Pelaporan — Laporan per Kegiatan**: judul kegiatan dulu terjepit
  ~40% lebar (badge + tombol Unduh sebaris) hingga membungkus 5–7 baris.
  Kini di HP judul tampil lebar penuh; badge status & tombol Unduh pindah
  ke baris kedua (badge kiri, Unduh kanan). Desktop tidak berubah.
- **Registrasi Persuratan — buku agenda**: tabel 860px dengan kolom Aksi
  sticky menutupi kolom Perihal/Dari di layar sempit & nomor terpotong
  di tengah kata. Kini di HP tiap surat tampil sebagai KARTU bertumpuk:
  chip agenda + badge status, nomor (utuh), perihal, tanggal + tujuan/
  pengirim, dan baris aksi ringkas (Sahkan/Batal/Ubah/Hapus) — tanpa
  scroll samping. Tabel tetap dipakai di ≥sm. Tombol aksi satu sumber
  (`renderAksi`) untuk tabel & kartu agar perilaku identik.
- Filter "Jenis: semua"/"Status: semua" dipendekkan jadi "Jenis"/"Status"
  supaya tidak terpotong ("Jenis: se…") di baris filter HP.
- Verifikasi: eslint bersih & `yarn build` sukses.

---

## [#417] Integrasi Penilaian → Neraca: nilai buku penyusutan tersaji di Laporan Posisi BMN — 2026-07-19

Lanjutan mandat integrasi lintas-modul "manfaatkan segala informasi agar saling
berkaitan": mesin penyusutan (modul Penilaian) kini menautkan hasilnya ke
**Laporan Posisi BMN di Neraca**. Neraca pemerintah wajib menyajikan **nilai
buku**; sebelumnya laporan ini hanya memuat nilai perolehan (catatan
"penyusutan menyusul").

- **Blok "Ikhtisar Nilai Buku"** ditambahkan pada Laporan Posisi BMN di Neraca
  (`GET /pembukuan/posisi-bmn-pdf`): nilai perolehan aset tersusutkan −
  akumulasi penyusutan = nilai buku, memakai mesin `rekap_penyusutan`
  (garis lurus semesteran PMK 65/PMK.06/2017) yang sudah teruji unit.
- **Kejujuran lingkup** dijaga: blok dipisah dari tabel intra/ekstra (cakupan
  berbeda — rekap tak memilah ambang & hanya meliputi aset ber-referensi masa
  manfaat), sehingga tidak dipaksa jadi satu angka yang berisiko salah saji.
  Telaah eksplisit: aset habis masa manfaat, henti-susut (rusak berat/hilang
  yang telah diusulkan hapus), tanpa referensi masa manfaat, dan kelompok tidak
  disusutkan (tanah/KDP/aset tetap lainnya) semua tersaji nilai perolehan penuh
  dengan jumlahnya. Aset revaluasi disusutkan atas nilai wajar (masa manfaat
  reset penuh).
- Catatan usang "penyusutan menyusul bertahap" diperbarui menjadi rujukan ke
  Ikhtisar; angka final penyusunan Neraca tetap divalidasi via SAKTI.
- Verifikasi: 545 tes unit lulus, smoke render PDF Posisi BMN sukses
  (`%PDF-1.4`, angka nilai buku cocok dengan hitung tangan: perolehan
  Rp305 jt − akumulasi Rp176,4 jt = nilai buku Rp128,6 jt untuk 2 aset contoh,
  1 revaluasi, 1 henti-susut, 1 tanpa referensi, 1 tanah dikecualikan).

---

## [#416] Integrasi Penggunaan → Pemanfaatan: BMN idle jadi kandidat pemanfaatan 1-klik — 2026-07-19

Lanjutan mandat integrasi lintas-modul "manfaatkan segala informasi agar
saling berkaitan": aset yang terindikasi IDLE (menganggur) di modul
Penggunaan kini ditawarkan langsung untuk DIMANFAATKAN.

- **Endpoint baru** `GET /pemanfaatan/kandidat-idle`: aset ber-indikasi idle
  (`indikasi_idle` — Nonaktif/tanpa pengguna, PMK 120/2024) yang BELUM terikat
  perjanjian pemanfaatan aktif = kandidat Sewa/Pinjam Pakai/KSP (PMK 115/2020).
  Aset yang perjanjiannya sudah berakhir/ditolak tetap muncul kembali sebagai
  kandidat. Ter-scope satker.
- **Panel "Kandidat dari BMN Idle"** di modul Pemanfaatan (dapat diciutkan,
  badge jumlah): tiap kandidat punya tombol **"Tawarkan Pemanfaatan"** yang
  membuka form perjanjian baru dengan objek BMN sudah terisi (prefill) —
  petugas tinggal mengisi mitra & jangka waktu.
- Nilai: mengubah aset menganggur menjadi potensi PNBP alih-alih hanya
  diserahkan ke Pengelola. Menyambungkan register BMN idle (Penggunaan) yang
  selama ini terpisah dengan alur Pemanfaatan.
- Verifikasi: 545 tes unit lulus, smoke endpoint (a1 idle→kandidat, a2 sudah
  dimanfaatkan→dikecualikan, a3 aktif→bukan idle) lulus, server ter-import,
  lint & build sukses.

---

## [#415] Integrasi lintas-modul: polis asuransi lewat & tunggakan kontribusi jadi temuan Wasdal otomatis — 2026-07-19

Mandat pemilik: "manfaatkan segala informasi yang ada untuk saling berkaitan
dalam pengelolaan BMN". Dua sumber data yang selama ini hanya tercatat di
modulnya kini mengalir menjadi temuan Wasdal otomatis (mesin aturan murni):

- **Polis asuransi BMN kedaluwarsa → temuan Wasdal** (objek Pengamanan &
  Pemeliharaan). Register polis Pengamanan (PMK 43/2025) yang masa
  berlakunya sudah lewat (`berakhir < hari ini`) langsung muncul sebagai
  temuan — aset strategis tanpa perlindungan tak lagi luput. Dulu Wasdal
  hanya menghitung total polis, tak menandai yang kedaluwarsa.
- **Tunggakan kontribusi Pemanfaatan (PNBP) → temuan Wasdal** (objek
  Pemanfaatan). Kewajiban kontribusi tahunan KSP/BGS-BSG yang belum tercatat
  pembayarannya (memakai `tahun_tertunggak` dari modul Pemanfaatan) jadi
  temuan — tunggakan PNBP adalah temuan wasdal klasik.
- Keduanya additif: `susun_temuan` menerima parameter `polis`, jenis temuan
  baru (`polis_asuransi_lewat`, `kontribusi_tertunggak`) terdaftar di
  registry `JENIS_TEMUAN`/`OBJEK_PER_JENIS`; UI Wasdal merender label jenis
  secara dinamis sehingga otomatis menampilkannya. Ter-scope satker.
- Verifikasi: 545 tes unit lulus (+2 kasus baru: tunggakan multi-tahun,
  polis lewat vs aktif vs tanpa tanggal), smoke mesin temuan end-to-end
  lulus, server ter-import.

---

## [#414] Semua tahap siklus BMN AKTIF penuh — hapus badge "Sebagian Aktif" — 2026-07-19

Permintaan pemilik: "agar tidak ada Sebagian Aktif di modul lagi; periksa juga
yang aktif". Verifikasi: 9 modul berbadge "Sebagian Aktif" (Penganggaran,
Pengadaan, Penggunaan, Pemanfaatan, Penilaian, Pengamanan, Pemeliharaan,
Pemindahtanganan, Penghapusan) semuanya sudah punya halaman fungsional penuh
(445–1550 baris JSX) + route backend + register/alur status/ekspor — bukan
stub. Statusnya "sebagian" hanya karena langkah akhir formal (penetapan SK)
dilakukan di SIMAN/DJKN eksternal, di luar kendali aplikasi.

- Seluruh `status: "sebagian"` → `status: "aktif"` (registry `bmnModules.js`) —
  badge Beranda Modul kini "Aktif" untuk semua tahap; label "Sebagian Aktif"
  dihapus dari `STATUS_LABELS` & `STATUS_BADGE_CLS`.
- Dead code status lama dibersihkan (ikon `Sparkles` badge, teks "kamar
  disiapkan modul menyusul bertahap" → "seluruh tahap aktif & dapat dibuka").
- Komentar header registry disegarkan (status v2.4: semua tahap aktif).
- Komentar basi "Sanding SBSK menyusul" di Perencanaan diperbaiki (SBSK sudah
  tersedia).
- Verifikasi: lint 0 warning, build sukses.

---

## [#413] Perbaikan bug: baris daftar aset tumpang tindih di HP (virtualisasi) — 2026-07-18

Laporan pemilik: saat refresh/perubahan data pada tampilan HP, sebagian baris
daftar aset tumpang tindih dengan baris lain (sebagian ya, sebagian tidak).

- **Akar masalah**: `VirtualizedMobileCards` memanggil `virtualizer.measure()`
  secara BLANKET pada tiap perubahan `assets` (`useEffect([assets])`). Panggilan
  itu me-RESET seluruh cache tinggi baris ke estimasi; lalu ResizeObserver
  per-baris menyusun ulang satu per satu. Di jendela race tersebut, sebagian
  baris memposisikan diri (`transform: translateY`) berbasis estimasi tinggi
  usang sementara baris lain sudah terukur ulang → tumpang tindih parsial.
  Karena tinggi kartu bervariasi (badge/lokasi yang membungkus), efeknya
  "sebagian tumpang tindih, sebagian tidak".
- **Perbaikan**: hapus reset blanket (anti-pola menurut dokumentasi resmi
  `@tanstack/react-virtual` — `measureElement` + `getItemKey` ber-identitas
  sudah menangani perubahan data otomatis). Re-measure massal kini HANYA
  dipicu saat LEBAR container benar-benar berubah (rotasi HP / resize) lewat
  ResizeObserver ber-guard lebar. Estimasi awal dinaikkan ke 120px agar lebih
  dekat tinggi nyata (mengurangi koreksi awal).
- Verifikasi: lint 0 warning, build produksi sukses.

---

## [#412] Dokumentasi v2.4: PRD (halaman Info), README & masterplan diperbarui menyeluruh — 2026-07-18

Pemutakhiran seluruh dokumentasi setelah sistem matang (bagian akhir mandat
"update semua dokumentasi + halaman PRD terupdate tanpa terkecuali"):

- **Halaman Info/PRD** (`InfoPage.jsx`) dinaikkan ke **v2.4**: hero &
  ringkasan mencerminkan platform siklus PENUH BMN; seksi "Apa yang Baru"
  diganti dengan 6 kartu rilis v2.4 (Sinkron SIMAN V2, Stiker & TTD, Master
  & Referensi, Keamanan multi-satker, Performa & backup, Perombakan UI 26
  halaman); seksi Fitur ditambah 7 kartu baru (SIMAN, stiker, TTD, master
  SDM, siklus 12 tahap, persuratan, backup otomatis); statistik & arsitektur
  (45+ route, isolasi multi-satker) dimutakhirkan. Header mobile sudah
  dirapikan sebelumnya (#407) sehingga tombol Kembali tak bertumpuk.
- **README.md** → v2.4: ringkasan arah, status modul (semua aktif +
  multi-satker), dan blok "Highlight Rilis v2.4" berisi 8 sorotan utama
  dengan rujukan PR.
- **MASTERPLAN-SIKLUS-BMN.md**: catatan status "roadmap telah terealisasi
  luas per v2.4" di ringkasan eksekutif.
- Verifikasi: lint 0 warning, build produksi sukses.

---

## [#411] Alur pengguna: Kembali dari Pengaturan tak lagi terlempar keluar + label CTA kartu seragam — 2026-07-18

Tindak lanjut evaluasi alur pengguna (bagian mandat "benahi alur yang kurang
pas, flow terjaga, tidak ribet"):

- **Kembali dari sub-halaman Pengaturan balik ke Pengaturan**: membuka
  Master Satker / Referensi Akun / Persuratan / Pelaporan DARI Pengaturan
  lalu menekan Kembali dulu melempar pengguna ke Beranda Modul (konteks
  Pengaturan hilang). Kini navigasi mengingat asalnya — Kembali balik ke
  Pengaturan bila dibuka dari sana, tetap ke Beranda Modul bila dibuka
  langsung.
- **Label ajakan kartu modul seragam**: verba tombol kartu yang berganti-
  ganti ("Masuk Modul" / "Buka Arsip Pelaporan" / "Buka Pembukuan" / "Buka
  Master Persediaan") diseragamkan menjadi **"Buka Modul"** untuk semua
  modul yang dapat dimasuki; "Lihat Konsep" tetap untuk modul yang masih
  berupa konsep (pembeda yang bermakna).
- Verifikasi: lint 0 warning, build sukses. (Temuan alur lain — tautan pada
  petunjuk prasyarat lintas-modul, penyeragaman istilah Pemegang/Pengguna,
  perampingan Beranda — tercatat sebagai backlog penajaman lanjutan.)

---

## [#410] Audit performa: indeks kunci + bilah progres ringan (hemat scan penuh saat data besar) — 2026-07-18

Hasil audit performa menyeluruh. Fokus pada yang paling terasa saat data
besar (10k aset, ribuan surat/pegawai):

- **Bilah progres inventarisasi tak lagi memicu full-scan tiap menit**:
  InventoryProgressBar (selalu tampil di dashboard) dulu memanggil
  `/rekapitulasi` — menarik SELURUH aset kegiatan ke memori — tiap 60 detik
  & tiap simpan. Kini memakai endpoint RINGAN
  `/inventory-activities/{id}/rekap-ringkas` (satu agregasi `$group`
  total+belum di MongoDB, payload dua angka). Halaman Rekapitulasi lengkap
  tetap memakai endpoint penuh.
- **Indeks database kunci ditambahkan** (hasil audit — dulu COLLSCAN):
  - `assets.siman.status` + `[activity_id, siman.status]` — panel SIMAN
    (4× count per buka).
  - `assets.pengguna_nip` & `assets.user` — rekap pemegang, daftar aset per
    pegawai, filter pengguna.
  - `surat`: `id` (unik), `[jenis, status]`, `[jenis, tahun, no_agenda]` —
    buku agenda persuratan + setiap operasi surat/BAST/LPB (dulu koleksi
    `surat` TANPA indeks sama sekali).
  - `pegawai`: `id`, `nip`, `[kode_satker, nama]` — cek bentrok NIP impor
    massal + daftar per satker.
  - `pejabat`/`ruangan`/`unit_kerja` `id`, `siman_imports.waktu`,
    `signature_requests` (`id` + `[created_by, created_at]`).
- Verifikasi: 543 tes unit lulus, smoke rekap-ringkas (agregasi total+belum
  benar), server ter-import, lint & build sukses. Indeks bersifat idempoten
  (dibuat saat startup).

---

## [#409] Audit keamanan menyeluruh: tutup kebocoran lintas-satker & IDOR, rate-limit e-sign, masking NIP publik — 2026-07-18

Hasil audit keamanan menyeluruh (mandat "pemantauan keamanan setiap fitur
setiap modul"). Sembilan temuan ber-risiko ditutup — tidak ada perubahan
alur fungsional, murni pengetatan:

- **Isolasi satker pada jejak audit (kritis)**: `GET /audit-logs` dan
  `/audit-logs/aset-terhapus` kini DI-SCOPE ke kegiatan milik satker user
  (dulu user/viewer satker mana pun bisa membaca seluruh jejak lintas
  satker — kode/NUP/nama aset, aksi, pelaku). Super-admin lintas-satker
  tetap melihat semua.
- **Dasbor integritas ter-scope**: endpoint `/integritas/*` (snapshot basi
  penghapusan/pemindahtanganan/PSP/jadwal + kodefikasi aset) kini menyaring
  register & agregasi aset per satker — tidak lagi membocorkan identitas
  aset satker lain.
- **Kartu Inventarisasi (IDOR ditutup)**: `GET /assets/{id}/card` dan
  `POST /assets/cards/bulk` kini memverifikasi kepemilikan satker — user
  tak bisa lagi menarik kartu (nama/lokasi/foto/riwayat) aset satker lain
  via id.
- **Master Pegawai (tulis lintas-satker ditutup)**: `PUT`/`DELETE /pegawai/{id}`
  kini menolak admin terikat satker yang menyunting/menghapus pegawai
  satker lain (termasuk NIP & rekening).
- **E-sign IDOR + rate-limit**: dokumen asli/ber-TTD, gambar TTD, lembar
  pengesahan, dan detail permintaan kini hanya untuk PEMBUAT/admin (dulu
  setiap user login bisa membuka dokumen & PII penanda tangan permintaan
  siapa pun). Submit e-sign publik & olah-foto kini ber-rate-limit.
- **NIP di-masking di verifikasi publik**: halaman verifikasi QR (tanpa
  login) kini menampilkan NIP tersamar (hanya 3 digit akhir) — data
  pribadi tak lagi terekspos utuh.
- **Endpoint kuota kompresi ditutup**: `/compression-stats` & `/compression-quotas`
  kini butuh login (dulu anonim, membocorkan status API key & kuota).
- **Pesan galat tak bocor**: kompresi PDF/gambar tak lagi mengembalikan
  pesan exception internal ke klien (dicatat di log server saja).
- Verifikasi: 543 tes unit lulus, smoke isolasi (audit satker AA vs BB,
  super-admin lihat semua, IDOR 403, masking NIP) lulus, server ter-import.
  Frontend tidak berubah.

---

## [#408] Siklus data satu rumah: backup otomatis terjadwal + arsip server + restore/reset pindah ke Pengaturan › Sistem — 2026-07-18

Pembaruan besar fitur backup/restore/reset sekaligus de-redundansi alur
(mandat "kelompokkan sesuai posisi yang pas sesuai alurnya"):

- **Backup otomatis harian (BARU)**: server membuat backup sendiri pada jam
  terjadwal (WIB) dan menyimpannya ke ARSIP SERVER persisten; arsip terlama
  dihapus otomatis melebihi kuota retensi (setelan aktif/jam/retensi di
  Pengaturan › Sistem). Scheduler aman multi-worker (klaim tanggal atomik
  di DB) dan toleran server mati pada jam persisnya.
- **Arsip backup di server (BARU)**: daftar berkas (nama, ukuran, waktu,
  jenis) + unduh + hapus + **pulihkan langsung dari arsip** (tanpa unggah
  ulang; konfirmasi berlapis; arsip asli tidak dikonsumsi proses restore).
  Backup manual kini punya opsi "simpan juga ke arsip server". Nama berkas
  divalidasi ketat anti path-traversal (teruji unit).
- **Satu rumah siklus data**: dialog Pulihkan & Reset PINDAH ke Pengaturan ›
  Sistem (komponen bersama `DataSistemDialogs`); pintu ganda di halaman
  pemilihan kegiatan DIHAPUS (tinggal penunjuk arah) — tidak ada lagi
  fungsi kembar di dua tempat.
- **Reset kini melindungi master referensi**: kodefikasi barang (impor
  Excel), kategori, hierarki akun BAS, unit kerja, pegawai, pejabat, dan
  ruangan SELAMAT dari reset-all (sebelumnya ikut terhapus — setup ulang
  manual yang mahal). Reset tetap membersihkan seluruh data operasional.
- Verifikasi: 543 tes unit lulus (+9 baru: retensi, jadwal, anti-traversal,
  master selamat reset), smoke endpoint arsip/otomatis lulus, server
  ter-import, lint 0 warning, build sukses.

---

## [#407] UI mobile sesuai arahan pemilik: penanda SIMAN di bawah foto, toolbar ringkas, hapus surat, arsip 1 baris, Info tersembunyi — 2026-07-18

Enam permintaan langsung pemilik (berdasar tangkapan layar HP):

- **Penanda SIMAN di kartu aset (HP)**: chip teks "≠ SIMAN" dipindah dari
  baris badge menjadi IKON kecil bulat amber di BAWAH FOTO (ikon sinkron,
  tooltip penjelas) — baris badge lega, tetap terlihat jelas.
- **Persuratan — tombol HAPUS surat (baru)**: admin dapat menghapus surat
  salah catat / batal dibuat (masuk & keluar) dengan konfirmasi bergaya;
  surat keluar yang sudah DISAHKAN ditolak server (harus dibatalkan dulu —
  jejak nomor resmi terjaga; nomor agenda hangus, tidak dipakai ulang).
  Endpoint `DELETE /persuratan/{id}` ber-audit.
- **Persuratan — toolbar maks 2 baris di HP**: baris 1 pencarian + CSV,
  baris 2 filter jenis/status + 2 aksi; kolom Aksi tabel diringkas (label
  "Sahkan" jadi ikon di HP, semua tombol ber-tooltip).
- **Referensi Akun BAS — toolbar 1 baris di HP** (meniru Referensi Kode
  Barang): pencarian menyusut, filter segmen dibatasi lebar, ekspor cukup
  ikon.
- **Arsip laporan — tombol Posisi BMN 1 baris**: PDF / Lainnya / LBKP /
  CaLBMN jadi 4 tombol ringkas se-baris (grid) di HP dengan teks to the
  point + tooltip kepanjangan.
- **Halaman Info/PRD kembali TERSEMBUNYI**: tombol "i" di Beranda Modul
  dihapus — akses hanya via 3× klik beruntun pada logo (semua pintu
  terlihat sudah tidak ada); header halaman Info dirapikan di HP (tombol
  Kembali ikon-saja, tak lagi bertumpuk dengan konten — tombol diberi
  min-h-0 melawan aturan 44px).
- Verifikasi: 539 tes unit lulus, smoke endpoint hapus surat (409 utk
  disahkan, 404, sukses+audit) lulus, lint 6 file 0 warning, build sukses.

---

## [#406] SIMAN V2: sinkronisasi diperkuat + tervalidasi + buat draft aset massal dari baris SIMAN — 2026-07-18

Laporan pemilik: sinkronisasi file ekspor SIMAN V2 gagal dilakukan. Diagnosa
empiris terhadap file asli (daftaraset1_SIMANV2.xlsx, 165 baris): parser inti
SEHAT (metadata dimensi rusak ekspor SIMAN sudah ditangani `reset_dimensions`
sejak #338) — kegagalan kemungkinan di lapisan jaringan/varian file. Seluruh
lapisan diperkuat agar andal di segala situasi + data SIMAN dibuat jauh lebih
bermanfaat:

- **Deteksi format smart**: header dicari di SEMUA sheet (tidak lagi hanya
  "Master Aset"/sheet pertama) dan di 25 baris awal (toleran kop/judul di
  atas tabel) — helper murni `deteksi_header` teruji unit.
- **Pesan gagal actionable**: .xls lama (minta simpan ulang .xlsx), file
  rusak/ganti-nama, file kosong terkirim (koneksi putus), sheet tanpa header
  (sebut nama sheet yang ada), ekspor kosong — semua pesan menyebut solusi.
- **Validasi satker**: kode satker pada file dibandingkan dengan master
  satker + kop global AMAN (normalisasi alfanumerik) — file milik satker
  lain memunculkan peringatan sebelum ditindaklanjuti; duplikat kode+NUP
  pada file juga dilaporkan.
- **Unggah andal (web/HP)**: progres % saat mengunggah, timeout longgar
  180 dtk, COBA ULANG OTOMATIS 2× (jeda 2/5 dtk) khusus gagal jaringan,
  pesan khusus 429 (terlalu sering) — meminimalkan kegagalan di koneksi
  lapangan; batas ukuran file 25MB dengan pesan jelas.
- **Data SIMAN jadi modal aset (baru)**: baris SIMAN yang belum tercatat di
  AMAN kini tersimpan di register impor (s.d. 5000 baris) dan bisa:
  (1) diunduh CSV, atau (2) **dibuat aset draft massal 1-klik** ke kegiatan
  terpilih — kode, NUP, nama, merk, tipe, kondisi, nilai, tanggal, kode
  register SIMAN langsung terisi; petugas tinggal melengkapi foto & lokasi.
  Jalur create standar dipakai (kunci kegiatan, keunikan kode+NUP, registry,
  audit); idempoten — baris yang sudah tercatat otomatis dilewati.
- Verifikasi empiris terhadap FILE ASLI: impor 165 baris → buat draft 164
  aset → impor ulang 165 dicek 164 cocok (1 selisih kategori yang memang
  riil) → buat draft ulang 0 dibuat/164 dilewati. 539 tes unit lulus
  (+8 baru), smoke lama tetap lulus, lint 0 warning, build sukses.

---

## [#405] UI/UX gelombang 2: 12 pola lintas-halaman diseragamkan di 25 halaman modul — 2026-07-18

Lanjutan mandat "review menyeluruh — rapikan tampilan di berbagai ukuran
layar": eksekusi pola perbaikan seragam (P1–P11) atas seluruh sisa temuan
audit, dikerjakan paralel per halaman (25 agen + 25 reviewer diff, 9 temuan
reviewer ditindaklanjuti sebelum rilis):

- **Nominal Rupiah tak patah lagi (P1)**: semua kartu statistik ber-`break-all`
  (Pemeliharaan, Penghapusan, Pemusnahan, Pemindahtanganan, Perencanaan,
  Penilaian, Penganggaran, Pemanfaatan, Pembukuan, Info) kini satu baris utuh
  (`tabular-nums` + nilai penuh di tooltip); grid ringkasan responsif
  `grid-cols-2 sm:grid-cols-3` dengan kartu nominal lebar penuh di mobile
  (posisi diatur agar grid tidak berlubang).
- **Header halaman & seksi tidak berjejal (P2/P3)**: container header semua
  modul kini `flex-wrap` + judul `truncate`; baris aksi register
  (Penghapusan, Pemanfaatan, Pengamanan, Wasdal, Penilaian, Satker, TTD,
  Pelaporan, Referensi Akun) membungkus rapi di layar 320–375px.
- **Alur kerja terlihat (P4)**: tombol transisi maju kini solid warna modul —
  "Proses" (Penghapusan, amber), "Setujui/Laksanakan" (Pemindahtanganan,
  indigo), aksi utama 4 seksi Pengamanan (amber, label tampil di mobile),
  "Sahkan" (Persuratan), "Buat BAST" (Penggunaan, sky), CTA Tambah
  (Pegawai/Pejabat/Ruangan); Tolak/Hapus tetap outline merah.
- **Icon-only ramah sentuh (P5)**: seluruh tombol ikon-saja atau berlabel
  tersembunyi di mobile kini punya title + aria-label (Persediaan toolbar,
  Wasdal, Kodefikasi, Pegawai, dll.); ikon "Massal" Persediaan diganti
  ListPlus agar Layers eksklusif bermakna layer FIFO.
- **Empty-state berarah (P6/P7)**: daftar kosong kini memberi arahan + CTA
  yang memanggil handler tombol header (Pemusnahan, Pemindahtanganan,
  Pemanfaatan, Persediaan, Pengadaan, Penganggaran, Pegawai, Persuratan,
  Pembukuan); halaman ber-filter membedakan "belum ada data" vs "tidak
  cocok filter" + tombol hapus pencarian (Pejabat, Ruangan, TTD, Pembukuan).
- **Data kunci menonjol (P8)**: nomor SK (Penghapusan), NTPN/No. Dokumen
  (Pemindahtanganan), periode polis (Pengamanan), nilai lama→baru
  (Penilaian), nilai mutasi (Pembukuan) diangkat dari kalimat gabungan
  menjadi badge font-mono tersendiri.
- **Ikon seragam & istilah dijelaskan (P9/P10)**: karakter teks ✓ ○ ⚠ diganti
  ikon lucide; singkatan birokrasi (DHPB, Wasdal, SPTJM, NTPN, KPB, BAS,
  LHIP, dst.) diberi kepanjangan via tooltip/teks.
- **Kartu utama ber-header (P11)**: Riwayat Pemeliharaan, arsip Pelaporan,
  dan kartu utama lain kini berjudul + ikon + badge jumlah, konsisten
  dengan seksi sekunder.
- **Bonus temuan audit**: toggle tema di halaman Pengaturan (wiring state
  dari App agar tidak dobel instans), konfirmasi hapus bergaya (useConfirm)
  di Penggunaan, kartu statistik baru di Persediaan/Penggunaan, saring
  client-side dialog daftar aset Pengamanan, teks roadmap internal dihapus
  dari kaki halaman Penggunaan, banner opname Persediaan dibedakan warna
  (sky) dari peringatan stok (amber), daftar aset per BA Pemusnahan
  diringkas 5 baris + "+N lainnya".
- Verifikasi: 531 tes unit lulus, lint 26 file berubah 0 warning, build
  produksi sukses; 9 catatan reviewer diff (grid berlubang, break-all
  tersisa, min-h-0 kurang, angka total menyesatkan, wiring tema) semua
  dibereskan.

---

## [#404] UI/UX gelombang 1: 15 perbaikan prioritas dari audit menyeluruh 26 halaman — 2026-07-18

Mandat pemilik: "review menyeluruh semua modul selain inventarisasi — rapikan
tata letak di berbagai ukuran layar, jangan berdesakan, ter-kategori rapi,
icon & tata letak sesuai". Audit multi-agen atas 26 halaman menghasilkan 187
temuan; gelombang ini mengeksekusi 15 perbaikan berdampak terbesar:

- **Pengaturan**: tombol "Tutup" editor kop tidak lagi muncul tanpa fungsi di
  halaman Pengaturan (dulu tampak bisa diklik tapi tidak menutup apa pun).
- **Pejabat**: masa berlaku yang sudah lewat kini berbadge kuning
  "Kedaluwarsa" (bukan tetap hijau "Aktif" yang menyesatkan).
- **TTD**: membatalkan permintaan tanda tangan kini meminta konfirmasi
  (aksi mematikan semua link ttd yang telanjur dibagikan — permanen).
- **Wasdal**: banner merah agregat "N tindakan lewat tenggat" muncul di atas
  register bila ada penertiban/insiden yang melewati due date.
- **Persuratan**: kolom Aksi dibuat sticky kanan saat tabel discroll
  horizontal; kolom "Naskah · Modul" disembunyikan di layar sempit.
- **Persediaan**: 8 tombol ikon per baris diringkas — 3 aksi tersering tetap
  tampil (Masuk/Keluar/Opname), sisanya masuk menu ⋮ berlabel teks; baris
  input dialog massal kini membungkus rapi di layar sempit (nama barang jadi
  baris sendiri).
- **Pembukuan**: filter jurnal diberi placeholder + keterangan jelas bahwa
  isinya ID aset (bukan nama/kode) — dulu pengguna menebak-nebak.
- **Pelaporan**: 7 tombol unduh sejajar dirapikan — "Unduh PDF" (Posisi BMN)
  jadi CTA utama biru, LKB/DBR/KIR/Rekonsiliasi masuk dropdown "Laporan
  Lain" bernama LENGKAP ("LKB — Laporan Kondisi Barang", dst.); tooltip
  kepanjangan pada LBKP & CaLBMN.
- **Pengadaan**: ikon "Daftarkan ke Persediaan" dibedakan dari "Buat Draft
  Aset" (Boxes vs PackagePlus); kolom harga satuan form barang dilebarkan
  (grid 8 kolom di desktop) agar angka rupiah tidak terpotong.
- **Kodefikasi**: Template + 2 tombol Ekspor digabung ke dropdown "Unduh"
  berlabel lengkap; tooltip pada Tambah & Impor.
- **Penggunaan**: kartu utama diberi header berjudul "Daftar Pemegang Aset"
  + badge jumlah (pola seragam dengan seksi Idle/PSP); paginasi diberi
  konteks "Pemegang — hal. X/Y"; tombol aksi register SK PSP dipisah ke
  baris aksi sendiri (tidak lagi berdesakan dengan identitas SK) + tooltip.
- **Referensi Akun**: master kosong kini menampilkan CTA "Muat Referensi
  Resmi" langsung di tempat (admin) — dibedakan dari "tidak cocok filter".
- **Pegawai/Pejabat/Ruangan (mobile)**: kolom yang disembunyikan di layar
  sempit (jabatan/unit kerja, masa berlaku, gedung/lantai) kini tampil
  sebagai subbaris kecil di sel Nama — informasi tidak hilang lagi.
- Verifikasi: 531 tes unit lulus, lint 15 file berubah 0 warning, build
  produksi sukses. Backend tidak berubah.

---

## [#403] Stiker: rekap jumlah per ukuran + switch nama/kode satker (20 digit) — 2026-07-18

Dua permintaan pemilik:
- **Rekap sebelum cetak (mode per-aset)**: dialog menampilkan rincian
  "Besar N · Sedang N · Kecil N · Belum terisi N" beserta total — aset yang
  belum punya pilihan Ukuran Stiker disorot kuning dengan petunjuk tindak
  lanjut (isi via form aset / edit cepat / Ubah Massal) sebelum tercetak
  memakai ukuran Sedang. Endpoint `GET /stiker/rekap-ukuran` (filter identik
  daftar aset, agregasi ter-scope satker).
- **Switch info header**: baris kedua stiker dapat dipilih — NAMA satuan
  kerja (default) atau KODE SATKER LENGKAP ±20 digit (cth.
  126011600691778000KP). Field `kode_satker_lengkap` DITAMBAHKAN ke
  pengaturan kop GLOBAL (Pengaturan → Kop) dan MASTER SATKER (override per
  satker, ikut resolusi kop) karena sebelumnya memang belum ada.
- Verifikasi: 531 tes unit lulus (anti-drift peta kop diperbarui sengaja),
  smoke rekap (3/0/5/17) + header kode 20 digit lulus, server ter-import,
  lint & build sukses.

---

## [#402] Stiker: gap aman QR (mesin cutting) + info sub-sub kelompok + logo di tengah QR (kecil) — 2026-07-18

Tiga permintaan pemilik:
- **Gap aman QR dari garis tepi** (1,8mm dari tepi kanan/bawah & garis
  header) — antisipasi meleset di mesin cutting: QR tidak ikut terpotong.
- **Info SUB-SUB KELOMPOK aset** tampil di stiker (semua ukuran): uraian
  di-resolve batch dari master kodefikasi berdasarkan kode barang, fallback
  kategori aset.
- **Stiker KECIL: logo instansi di tengah QR** (tidak ada ruang logo di
  header) dengan kotak putih + koreksi galat QR dinaikkan ke LEVEL H (30%)
  — keterbacaan dibuktikan empiris: QR ber-logo hasil render DIDEKODE ULANG
  dan menghasilkan payload persis (#kode register).
- Verifikasi: 531 tes unit lulus, smoke render 6 kombinasi + uraian sub-sub
  tampil, dekode QR ber-logo lulus, pratinjau visual diperiksa, server
  ter-import, build sukses.

---

## [#401] Stiker: ukuran optimal penuh-halaman, nama satker di header, QR mepet tepi, ukuran per aset — 2026-07-18

Empat permintaan pemilik sekaligus:
- **Ukuran paling optimal utk A4 & A3**: kolom/baris dibulatkan ke ukuran
  target lalu label DIRENTANGKAN memenuhi SELURUH ruang kertas (sisa hanya
  margin 6mm + celah potong 1,5mm). Muatan: Besar A4 12 (±98×46mm) ·
  A3 27 (±94×44mm, dari 16); Sedang A4 27 (±65×30) · A3 65 (±56×30, dari
  48); Kecil A4 48 (±48×22) · A3 102 (±46×23). Helper murni `grid_optimal`
  teruji unit (grid terbukti mengisi penuh area cetak).
- **Nama satker di header**: baris kode registrasi di bawah judul diganti
  NAMA SATKER (resolusi kop: nama_sub_unit → nama_unit_organisasi); kode
  register tetap terbawa di payload QR.
- **QR mepet garis tepi**: menempel garis header, tepi kanan, dan tepi
  bawah stiker (tanpa padding) — setinggi penuh badan stiker.
- **Ukuran per aset + dikelompokkan**: opsi cetak baru "Sesuai pilihan per
  aset" memakai field `Ukuran Stiker` tiap aset (sudah ada di form aset,
  edit cepat, dan ubah massal) — hasil cetak DIKELOMPOKKAN besar → sedang
  → kecil, tiap kelompok grid halamannya sendiri; nilai kosong memakai
  sedang.
- Verifikasi: 531 tes unit lulus (4 baru grid/kelompok), smoke render 6
  kombinasi + mode per_aset (3 halaman terkelompok benar) lulus, pratinjau
  visual penuh-halaman diperiksa, lint & build sukses.

---

## [#400] Stiker: jarak antar kotak dirapatkan (celah tipis) + QR diperkecil — 2026-07-18

Umpan balik pemilik atas fitur stiker:
- **Grid sangat rapat**: jarak antar kotak 4mm → **1,5mm** (celah tipis utk
  memotong tanpa buang kertas), margin 7mm → 6mm. Muatan per halaman naik:
  Besar A4 12 (was 10) · A3 16; Sedang A4 27 (was 24) · A3 48 (was 36);
  Kecil A4 48 (was 40) · A3 102 (was 84) — hint dialog disesuaikan dgn
  hitungan grid aktual.
- **QR diperkecil**: tidak lagi setinggi penuh badan stiker — 78% tinggi
  badan, rata tengah vertikal; ruang teks kiri sedikit bertambah.
- Verifikasi: smoke render 6 kombinasi lulus, muatan per halaman dihitung
  ulang dari kode nyata, pratinjau visual diperiksa, 527 tes unit lulus,
  lint & build sukses.

---

## [#399] TTD elektronik DIBUBUHKAN langsung ke dokumen PDF yang dikirim — 2026-07-18

Permintaan pemilik: e-sign tidak lagi hanya mengumpulkan tanda tangan —
kirim dokumen yang hendak di-ttd LANGSUNG, dan tanda tangan yang masuk
dibubuhkan ke dokumennya:
- **Unggah PDF saat membuat permintaan** (opsional, ≤20MB): dokumen
  tersimpan aman (GridFS), penanda tangan menandatangani via link seperti
  biasa — dan kini bisa **membaca dokumen terlebih dulu** dari halaman link
  ("Baca dokumen yang akan ditandatangani").
- **Unduh "Dokumen ber-TTD"**: dokumen asli + bubuhan tanda tangan di
  halaman terakhir — gambar ttd, nama (bergaris), jabatan, NIP, tanggal per
  penanda tangan (slot rapi maks 3/baris), plus **QR verifikasi + kode**
  di pojok; dibangun on-the-fly sehingga selalu memuat ttd terbaru.
  Halaman-halaman asli tidak berubah.
- Dasbor TTD: tombol **Dokumen Asli** & **Dokumen ber-TTD** pada detail
  permintaan; Lembar Pengesahan tetap tersedia.
- Endpoint: `POST /ttd/permintaan/unggah` (validasi PDF terbaca + jumlah
  halaman), `GET …/dokumen` (dasbor & tamu ber-token sign), `GET
  …/dokumen-ttd` (overlay pypdf + reportlab).
- Verifikasi: smoke end-to-end FakeDB+FakeGridFS (unggah 2 halaman → teken
  1 & 2 penanda tangan → PDF hasil diperiksa isi & dirender visual; token
  silang 401; non-PDF 400; belum ada ttd 400), 527 tes unit lulus, server
  ter-import, lint & build sukses.

---

## [#398] Cetak Stiker Label BMN — 3 ukuran × kertas A4/A3, mengikuti filter aktif — 2026-07-18

Permintaan pemilik (dengan referensi desain label resmi satker): fitur cetak
stiker yang selama ini belum ada.
- **Desain meniru contoh resmi**: border kotak, header logo + nama instansi
  + kode register lengkap, garis pemisah, badan kiri (kode barang + NUP,
  kategori, nama barang terpotong "..."), **QR besar di kanan** — payload QR
  memakai format pemindai internal aplikasi (#kode_register / #kode-nup)
  sehingga stiker langsung bisa discan dari kamera lapangan.
- **3 ukuran**: Besar ±95×45 mm (A4 10/hal · A3 16/hal), Sedang ±62×30 mm
  (A4 24/hal · A3 36/hal), Kecil ±45×22 mm (A4 40/hal · A3 84/hal) — grid
  dihitung otomatis dari ukuran kertas.
- **Kertas A4 & A3**; kop/nama instansi & logo mengikuti pengaturan satker.
- **Cakupan mengikuti filter & kelompok**: "semua hasil filter aktif"
  (search/kategori/kondisi/lokasi/eselon/status stiker/rentang harga/tanggal
  — parameter identik daftar aset) atau "halaman yang tampil saja";
  batas 2000 stiker per unduhan dengan catatan bila terpotong.
- Endpoint `GET /stiker/label` (ter-scope satker); tombol **Stiker** di
  toolbar Dashboard (desktop + menu mobile) membuka dialog pilihan.
- Verifikasi: 527 tes unit lulus, smoke render 6 kombinasi ukuran×kertas
  (isi & jumlah halaman terverifikasi + pratinjau visual dibandingkan
  referensi), server ter-import, lint bersih (0 warning baru), build sukses.

---

## [#397] Makna kode akun BAS tampil LANGSUNG membagi baris (header bertingkat level 1–5) — 2026-07-18

Umpan balik pemilik: makna kode hingga 6 digit jangan disembunyikan di balik
klik — harus tampil DI LUAR dan langsung membagi baris agar pengelompokan
terbaca seketika. Tabel master kini meniru tata letak lampiran resmi
KEP-211/PB/2018:
- **Header bertingkat per level digit** muncul otomatis setiap prefiks
  berganti: `1xxxxx — ASET` (akun/segmen) → `11xxxx — ASET LANCAR` (kelompok)
  → `117xxx — PERSEDIAAN` (jenis) → `1171xx` / `11711x` (level 4–5) →
  baris akun 6 digit; dengan indentasi & gradasi warna per level (level 1–3
  tebal, meniru cetakan resmi). Level 4–5 yang namanya mengulang induk
  dilewati agar hemat baris.
- Respons daftar kini menyertakan peta `hierarki` (nama resmi prefiks level
  1–5 utk halaman aktif) — satu query, tanpa request per baris.
- Klik baris akun kini KHUSUS membuka penjelasan resmi (makna digit sudah
  selalu terlihat); endpoint struktur/{kode} tetap tersedia.
- Verifikasi: 527 tes unit lulus, smoke daftar (peta hierarki) + ekspor
  lulus, server ter-import, lint & build sukses.

---

## [#396] Bagan Struktur Organisasi (pohon unit Eselon I–V + jumlah pegawai) — 2026-07-18

Penutup roadmap studi KERJA-BARENG:
- Tombol **"Struktur"** di Master Pegawai membuka **bagan pohon hierarki**
  unit kerja Eselon I–V dari master: simpul dapat dibuka/ditutup, tiap unit
  menampilkan badge eselon + **jumlah pegawai**; klik jumlah langsung
  **memfilter daftar pegawai** ke unit tersebut.
- Petunjuk bawaan bila master kosong (arahkan ke "Bangun otomatis dari data
  pegawai").
- Verifikasi: lint & build sukses (perubahan frontend murni di atas endpoint
  yang sudah ada).

---

## [#395] Form pegawai 5-tab + validasi digit rekening per bank + WNI/WNA + saran pangkat per status — 2026-07-18

Sisa roadmap KERJA-BARENG item form:
- **Form 5-tab** (Identitas · Pribadi · Kepegawaian · Jabatan & Unit ·
  Kontak & Bank) menggantikan satu gulungan panjang — lebih ringkas & terarah.
- **Kewarganegaraan WNI/WNA**: WNI → NIP/NIK/NRP + NPWP; WNA → jenis
  identitas (Paspor/KITAS/KITAP) + nomor identitas + NPWP opsional.
- **Peringatan lunak digit rekening per bank** (BRI 15, BNI 10, Mandiri 13,
  BTN 16, BSI/BCA 10, CIMB 13, Danamon 10): mismatch hanya diberi peringatan
  kuning, tidak memblokir; helper murni `periksa_rekening` teruji unit.
- **Saran Pangkat/Golongan MENGIKUTI status kepegawaian**: datalist berubah
  otomatis (PNS/CPNS 17 jenjang I/a–IV/e, PPPK Golongan I–XVII, TNI, POLRI).
- Referensi `/pegawai/referensi` diperluas (kewarganegaraan, jenis identitas
  WNA, peta pangkat per status, peta digit bank).
- Verifikasi: 527 tes unit lulus, server ter-import, lint & build sukses.

---

## [#394] Master Unit Kerja berjenjang (Eselon I–V) + pilihan bertingkat form pegawai — 2026-07-18

Rekomendasi #2 studi KERJA-BARENG (pola `UnitKerjaManager`):
- **Master Unit Kerja hierarkis**: koleksi `unit_kerja` {nama, eselon 1–5,
  induk} ter-scope satker; kelola via dialog di Master Pegawai (tab per
  eselon, tambah dengan pilihan induk Eselon N−1, hapus ber-guard: ditolak
  bila masih punya sub-unit atau dipakai pegawai).
- **Bangun otomatis 1-klik dari data pegawai**: jalur Eselon 1–5 seluruh
  pegawai (termasuk 1.369 hasil impor) diderivasi menjadi master hierarkis
  (idempoten, unit hasil derivasi ditandai "otomatis") — tanpa entri manual.
- **Pilihan BERTINGKAT di form pegawai**: field Eselon 1–5 kini ber-datalist;
  opsi Eselon N mengikuti induk Eselon N−1 yang dipilih (tetap bisa ketik
  bebas untuk unit yang belum terdaftar — data impor tidak terblokir).
- Endpoint: `GET/POST /unit-kerja`, `DELETE /unit-kerja/{id}`,
  `POST /unit-kerja/bangun-dari-pegawai`; modul murni
  (`validate_unit`, `opsi_bertingkat`, `unit_dari_pegawai`) teruji unit.
- Verifikasi: 526 tes unit lulus, smoke FakeDB (bangun otomatis idempoten +
  relasi induk benar, duplikat/tanpa-induk 400, hapus ber-anak/dipakai 409)
  lulus, server ter-import, lint & build sukses.

---

## [#393] Keterkaitan aset↔pegawai: alert "Perlu Serah Terima BMN" — 2026-07-18

Rekomendasi #1 studi KERJA-BARENG (pola "alert pemegang keluar") — menutup
celah aset hilang saat pegawai pergi:
- **Panel "Perlu Serah Terima BMN"** di Master Pegawai: pegawai BERISIKO
  (status keluar/mutasi/pensiun/nonaktif/diperbantukan, atau kontrak Non-ASN
  sudah/akan habis ≤30 hari) yang **masih tercatat memegang aset** (via
  `pengguna_nip`) tampil dengan jumlah aset & alasannya, terurut aset
  terbanyak.
- **Klik pegawai → daftar asetnya**: kode barang, NUP, nama, kondisi, lokasi,
  status BAST — beserta petunjuk tindak lanjut (BAST pengembalian / mutasi
  pemegang di modul Penggunaan → tab Pemegang, fitur yang sudah ada).
- **Peringatan lunak saat ubah status**: menyimpan pegawai dengan status
  non-aktif yang masih memegang N aset menampilkan toast peringatan
  (tidak memblokir — mendorong proses serah terima).
- Endpoint: `GET /pegawai/perlu-serah-terima` & `GET /pegawai/{id}/aset`
  (ter-scope satker; guard akses dokumen); helper murni
  `pegawai_perlu_serah_terima` teruji unit.
- Verifikasi: 523 tes unit lulus, smoke FakeDB endpoint berisiko + daftar
  aset + 404 lulus, server ter-import, lint & build sukses.

---

## [#392] Makna TIAP POLA DIGIT akun BAS (level 1–6) ditampilkan per akun — 2026-07-18

Permintaan pemilik: referensi akun belum menjelaskan arti tiap pola digit
kode (digit 1 apa, 2 digit apa, … hingga 6 digit). Kini setiap baris akun
yang dibuka menampilkan **jalur makna digit lengkap** dari lampiran resmi
KEP-211/PB/2018:
- **1.523 nama induk level 1–5** (mis. `1` ASET → `11` ASET LANCAR → `117`
  PERSEDIAAN → `1171` Persediaan → `11711` Persediaan Bahan Operasional)
  disematkan ke seed & koleksi `referensi_akun_hierarki`; level 6 memakai
  nama akun master. Segmen anggaran (5–8) memakai nama ledger Kas
  (Belanja/Dana) agar konsisten dengan label kelompok & nama baris.
- **Endpoint baru** `GET /referensi-akun/struktur/{kode}` → jalur
  {level, kode, label, uraian} utk digit 1 s.d. 6 (label: akun/segmen,
  kelompok, jenis, level 4–5, akun rincian).
- **UI**: SEMUA baris akun kini dapat diklik — panel rincian menampilkan
  tabel "Makna tiap pola digit" (prefiks `1xxxxx → 11xxxx → …` + nama resmi
  tiap level) di atas penjelasan resmi akun; dimuat sekali per kode (cache).
- **Ekspor CSV**: kolom **Nama Jenis** (nama resmi 3-digit) ditambahkan di
  samping kode jenis.
- **Propagasi otomatis**: SEED_VERSION=3 → basis produksi ter-upsert ulang
  saat halaman dibuka; hierarki langsung tersedia tanpa klik manual.
- Verifikasi: 522 tes unit lulus (jalur digit, cakupan hierarki anti-drift,
  kolom CSV), smoke endpoint struktur + ekspor lulus, server ter-import,
  lint & build sukses.

---

## [#391] Master Pegawai diperkaya (adopsi pola KERJA-BARENG/SIMPEG) + impor Excel massal — 2026-07-18

Studi mendalam aplikasi manajemen SDM KERJA-BARENG (form Tambah Pegawai,
unit kerja berjenjang, keterkaitan aset↔pegawai) → gelombang pertama
memperkaya Master Pegawai agar siap menampung data riil satker dan menjadi
rujukan kuat manajemen aset BMN (pemegang barang, penanggung jawab ruangan,
penanda tangan):
- **Impor Excel/CSV massal** (`POST /pegawai/impor`, admin): menormalkan data
  lapangan yang tak baku — status kepegawaian beragam ("Tenaga Pendukung",
  "Konsultan Individu", dll. → Non-ASN + sub-kategori), status keberadaan
  ("AKTIF/KELUAR/MUTASI KELUAR" → kode kanonik), **NIP dibersihkan** dari
  artefak Excel (mis. "…0002.0" float, karakter arah tak terlihat). Upsert per
  NIP dalam satker; template CSV dapat diunduh. Diuji empiris terhadap berkas
  nyata 1.369 pegawai: seluruhnya terbaca & ternormalisasi, 0 gagal.
- **Data diperkaya**: unit kerja **berjenjang Eselon I–V** (jenjang terdalam
  otomatis jadi Unit Kerja efektif), kategori pegawai (UU ASN), sub-kategori
  Non-ASN, agama, status perkawinan, bank & rekening, dan **kontrak Non-ASN**
  (nomor + mulai/selesai).
- **Peringatan kontrak**: pegawai Non-ASN dengan kontrak akan/telah berakhir
  ditandai badge di daftar — mitigasi risiko pemegang aset yang kontraknya
  habis (pola "alert pemegang keluar" KERJA-BARENG).
- **Isolasi satker**: pegawai kini ber-stempel `kode_satker`, daftar & rekap
  ter-scope per satker (era-lama tetap terbuka); NIP unik per satker.
- **Rekap** kini juga per Eselon I, selain per unit kerja.
- Verifikasi: 520 tes unit lulus (16 helper murni impor/kontrak/normalisasi),
  smoke impor 1.369 baris berkas nyata lulus, server ter-import, lint & build
  sukses.

Roadmap lanjutan (increment berikut): master Unit Kerja berjenjang dengan
dropdown bertingkat, form 5-tab, halaman Struktur Organisasi, dan keterkaitan
aset↔pegawai (handover + riwayat pemegang) — bahan sudah dipelajari dari
KERJA-BARENG.

---

## [#390] Penjelasan resmi tiap akun BAS (KEP-211/PB/2018) — dapat dibuka per baris + ikut ekspor CSV — 2026-07-18

Pemilik meminta penjelasan/definisi tiap akun ditampilkan (sebelumnya kosong).
Kolom **Penjelasan** dari lampiran resmi KEP-211/PB/2018 (workbook "Kode Akun
BAS", sheet Akun Kas & Akrual) kini disematkan ke master:
- **2.538 dari 2.899 akun (87%) berpenjelasan resmi**. Akun rincian 6-digit
  yang di dokumen resmi mewarisi definisi induknya diisi lewat **fallback
  hierarki** (kode sendiri → jenis/kelompok/segmen induk terdekat) dan ditandai
  "(definisi kelompok/jenis induk)". Teks dibersihkan dari artefak kode
  pemetaan numerik pada ekstraksi PDF (mis. "…Rupiah 502.000000980" → "…Rupiah"),
  tanpa merusak teks sah seperti "PPh Pasal 21".
- **UI**: setiap baris akun dapat **diklik untuk membuka penjelasan resminya**
  (chevron + baris rincian), lengkap dengan atribusi sumber.
- **Ekspor CSV**: kolom **Penjelasan** ditambahkan (warisan induk diberi
  prefiks penanda).
- **Propagasi otomatis**: versi seed dinaikkan (SEED_VERSION=2) sehingga basis
  data produksi yang sudah terisi di-upsert ulang otomatis saat halaman dibuka
  — penjelasan muncul tanpa admin menekan "Muat Referensi Resmi" manual.
- Verifikasi: 511 tes unit lulus (8 di modul referensi akun), smoke ekspor CSV
  (kolom Penjelasan + warisan) lulus, server ter-import, lint & build sukses.

---

## [#389] Nama kelompok akun BAS diselaraskan ke lampiran resmi KEP-211/PB/2018 — 2026-07-18

Pemilik mengirim workbook resmi "Kode Akun BAS (KEP-211/PB/2018)" — dipakai
untuk menggantikan label kelompok hasil derivasi manual dengan nama VERBATIM
dari lampiran resmi (sheet Akun Kas & Akun Akrual, entri Level 2). Koreksi
a.l.: `19`/`29` → "Akun Setup" (bukan "Aset Lainnya Khusus BUN"/"Kewajiban
Akrual Khusus"), `23` → "Dicadangkan untuk Komitmen Belanja", `49` →
"Pendapatan Penyesuaian", `59` → "Beban Penyesuaian", `61`–`66` memakai nama
Dana resmi ("Dana Bagi Hasil (DBH)", "Dana Alokasi Umum (DAU)", "Dana
Alokasi Khusus Fisik/Non Fisik", "Dana Desa", dst.), `69` → "Beban Transfer
Lain-lain", `79` → "Pengeluaran Pembiayaan Lain-lain", `81`/`82` →
"Penerimaan/Pengeluaran Non Anggaran".
- Segmen anggaran (5–8) memakai nama ledger KAS (Belanja/Dana) agar konsisten
  dengan nama baris master; kelompok khusus akrual (59, 69) memakai nama
  akrual. Dua kunci legacy (32, 67) yang tak ada di KEP-211 tetap dilabeli
  agar header tabel tidak kosong.
- Tes baru mengunci 14 nama kelompok ke lampiran resmi (cegah regresi ke
  label heuristik lama); footnote halaman menyebut sumber KEP-211/PB/2018.
- Verifikasi: 510 tes unit lulus (6 di modul referensi akun), smoke ekspor
  CSV lulus, lint & build sukses.

---

## [#388] Referensi Akun BAS terkategori sesuai makna digit + ekspor CSV — 2026-07-18

Permintaan pemilik: master Segmen Akun BAS tidak lagi tampil rata — kini
TERKATEGORI mengikuti struktur digit kode akun (KEP-211/PB/2018 jo.
pemutakhirannya; digit 1 = akun/segmen, 2 digit = kelompok akun, 3 digit =
jenis akun):
- **Header kelompok di tabel**: setiap kelompok akun 2-digit berganti muncul
  baris kategori `NNxxxx — Nama Kelompok` + chip segmen (mis. `52xxxx —
  Belanja Barang dan Jasa · BELANJA`); kolom "Segmen" yang redundan diganti
  header kategori. Label 41 kelompok (11 Aset Lancar … 83 Output Kinerja) di
  modul murni `referensi_akun_utils.py`, diverifikasi silang ke isi referensi
  resmi SAKTI/SPAN; tes anti-drift menagih label bila seed membawa kelompok
  baru.
- **Tombol Ekspor CSV** di tab master: `GET /referensi-akun/export` (semua
  role, utf-8-sig) mengikuti filter cari & segmen aktif — kolom hierarki
  lengkap (kode, nama, akun/segmen, kelompok + nama, jenis 3-digit, sumber,
  uraian BMN, kapitalisasi, kategori neraca) siap olah di Excel.
- Verifikasi: 509 tes unit lulus (5 baru), smoke empiris endpoint ekspor
  (FakeDB: header CSV, hierarki, filter, fallback kelompok tak dikenal),
  server ter-import, lint & build sukses.

---

## [#387] Perbaikan temuan review akhir: 3 regresi kritis 500 + guard satker & privasi e-sign — 2026-07-18

Review adversarial menyeluruh atas 4 PR terakhir (23 agen menemukan → memverifikasi)
mengonfirmasi 12 temuan; semuanya diperbaiki di sini:

**Kritis (500 di produksi):**
- **Persediaan**: 5 guard hasil sweep memanggil `pastikan_akses_dok_satker(_user, …)`
  padahal parameter handler bernama `user`/`_admin` → `NameError` pada SEMUA mutasi
  stok (masuk/keluar/pindah gudang/opname/hapus). Diperbaiki + proyeksi hapus
  kini menyertakan `kode_satker` agar guard efektif.
- **Penggunaan**: `scope_query_aset` hanya diimpor lokal → `NameError` di daftar
  pemegang, aset pemegang, dan PDF daftar pemegang. Impor dinaikkan ke level modul.
- **Perencanaan**: impor `kode_satker_user`/`scope_query_field_satker` hilang di
  level modul → daftar/ekspor/buat usulan RKBMN 500. Diperbaiki.

**Fungsional & keamanan:**
- **BAST**: snapshot aset kini menyimpan `purchase_price` (kolom Nilai Perolehan
  tidak lagi selalu "-" dan JUMLAH 0); pembuatan BAST memvalidasi kepemilikan
  tiap aset lintas satker (`pastikan_akses_aset`); unggah & unduh bukti ttd
  kini ber-guard satker.
- **BAST PSP**: PDF ber-guard satker + kop mengikuti satker SK; snapshot SK baru
  menyimpan kondisi & nilai perolehan, SK lama dilengkapi saat render dari
  master aset — kolom Kondisi/Nilai terisi benar.
- **E-sign**: status "sebagian" tidak lagi bisa menimpa "selesai" pada submit
  paralel (status final hanya bergerak maju); `_basis_url_publik` membaca
  `ALLOWED_ORIGINS` lebih dulu (selaras server.py); daftar permintaan kini
  privat — non-admin hanya melihat permintaan buatannya dan IP penanda tangan
  tak pernah ikut daftar.
- **Wasdal**: Laporan Tahunan PMK 207 kini men-scope penertiban & pemantauan
  insidentil per satker (sebelumnya lintas satker bocor ke laporan).
- **Backfill**: klaim-sisa hanya menyentuh dokumen yang benar-benar belum
  distempel (`None`/absen) — stempel lintas-satker `""` milik super-admin tak
  ikut terklaim.
- **UI**: kanvas tanda tangan mempertahankan goresan saat rotasi/resize layar
  (`toData`/`fromData`); dialog backfill terkunci selama proses berjalan.
- Verifikasi: compileall + pyflakes bersih, suite 504 lulus, smoke render 7
  varian BAST lulus, server ter-import, lint & build sukses.

---

## [#386] E-sign kirim email otomatis (Resend) + backfill kode satker data lama — 2026-07-18

Dua kandidat lanjutan terakhir:
- **Link e-sign terkirim OTOMATIS via email**: field email opsional per
  penanda tangan (tersaran dari Master Pegawai) — email berisi tombol
  "Tanda Tangani Sekarang" dikirim saat permintaan dibuat (paralel: semua;
  berurutan: giliran pertama), saat **giliran maju** ke penanda tangan
  berikutnya, dan saat link diterbitkan ulang. Best-effort (gagal kirim ≠
  gagal buat; link tetap bisa dibagikan manual/WA); badge status terkirim
  di dialog hasil. Memakai infrastruktur Resend yang sudah ada (OTP).
- **Backfill kode satker untuk data lama** (`POST /satker/backfill`, admin,
  idempoten): register lama ber-relasi aset (PSP, idle, proses, usulan
  hapus, BA pemusnahan, PT, pemanfaatan, penertiban, BAST) diisi otomatis
  dari relasi aset → kegiatan → satker; sisanya (persediaan, pengadaan,
  penganggaran, RKBMN, pengamanan, insidentil) dapat DIKLAIM ke satu satker
  pilihan — use-case satker tunggal lama sebelum satker kedua bergabung.
  UI: tombol "Backfill Data Lama" + laporan per koleksi di Master Satker.
- Verifikasi: suite 504 lulus, route ter-mount, lint & build sukses.

---

## [#385] Audit BAST resmi: pasal lengkap per jenis, dasar hukum mutakhir (PMK 40/2024), desain naskah dirapikan — 2026-07-18

Audit menyeluruh SEMUA generator BAST (mandat pemilik): riset anatomi BAST
resmi (PerANRI 5/2021 + rezim penggunaan BMN) → review 3 dimensi → render
empiris 7 varian (6 jenis + BAST PSP) dengan asersi ketat:
- **Dasar hukum dimutakhirkan**: PMK 246/PMK.06/2014 jo. 76/2019 sudah
  DICABUT → diganti **PMK Nomor 40 Tahun 2024** (konsisten dengan BAST PSP);
  istilah asing "(Handover)" dihapus dari judul jenis.
- **Pasal-pasal dilengkapi sesuai anatomi resmi** per jenis:
  - semua jenis: pasal baru **Keadaan Barang & Kelengkapan** (pengecekan
    bersama) + **Penutup rangkap 2 (dua) berkekuatan hukum sama**;
  - melekat/operasional/lainnya & mutasi: klausul **larangan
    memindahtangankan** + **pelaporan kehilangan/kerusakan & tuntutan ganti
    rugi**; mutasi bertambah pasal **Status Pencatatan** (BMN tetap tercatat
    di satker, hanya daftar pemegang/DBR/KIB berubah);
  - penggunaan sementara: "tidak mengalihkan kepemilikan" dikoreksi menjadi
    **tidak mengalihkan status penggunaan**, + klausul perpanjangan, pasal
    **Biaya** (pemeliharaan beban penerima) & kewajiban **BAST pengembalian**;
  - pengembalian: klausul **pemeriksaan fisik**, peralihan kembali tanggung
    jawab, pemutakhiran pencatatan.
- **Naskah & desain**: frasa pembuka lengkap ("…bertempat di …"), identitas
  pihak ber-label sejajar + "selanjutnya disebut PIHAK …", konsiderans
  "berdasarkan:", isi pasal hitam rata kiri-kanan (bukan abu-abu metadata),
  judul pasal ber-jarak & anti-yatim (KeepTogether), tabel objek bertambah
  kolom **Nilai Perolehan + baris JUMLAH**, header tabel dua baris benar.
- **BAST PSP dirombak ke bentuk pasal** (Objek ber-tabel kondisi+nilai+total,
  Peralihan Tanggung Jawab, Penutup rangkap 2) + nomor + frasa hari-tanggal
  terbilang + blok ttd 3 pihak satu kesatuan + spesimen TTD KPB.
- **Ketahanan**: teks isian ber-'&'/'<' tidak lagi bisa merusak PDF (escape
  di pasal kustom, PJ tambahan, judul, dan `_signature_block` — berlaku utk
  seluruh laporan); kop BAST kini per-satker; akses PDF ber-guard satker;
  caption foto lampiran tak terpisah dari fotonya; footer dibatasi.
- Verifikasi: render empiris 7 varian lulus asersi (pasal, rangkap, ganti
  rugi, escape '&', ≤2 halaman); suite **504 lulus**.

---

## [#384] Isolasi satker MENYELURUH: seluruh register siklus ber-stamp & ter-scope — 2026-07-18

Melengkapi isolasi multi-satker ke SEMUA register siklus BMN (pola stamp +
scope + era-lama-terbuka yang sudah mapan):
- **11 register ber-stamp `kode_satker`** saat dibuat: pemanfaatan, usulan
  penghapusan (langsung & dari BA pemusnahan), BA pemusnahan,
  pemindahtanganan, perolehan pengadaan, usulan penganggaran, usulan RKBMN,
  penertiban & insidentil wasdal, kasus/dokumen/polis pengamanan, BAST
  serah terima, proses penggunaan.
- **±30 daftar/ekspor ter-scope** satker user (termasuk kandidat penghapusan,
  dasbor pengamanan ringkasan/aset-kurang, rekap pemegang & PDF-nya,
  register lintas di mesin aturan wasdal, hitung persediaan pada DBKP).
- Data era lama tanpa kode tetap terbuka — tidak ada data yang mendadak
  hilang; user lintas-satker (admin pusat) tetap melihat semua.
- Dokumentasi deploy: `APP_PUBLIC_URL` ditambahkan ke panduan (.env) —
  dasar link e-sign & QR verifikasi (fallback origin CORS).
- Verifikasi: suite 504 lulus, 423 route ter-mount, build sukses.

---

## [#383] Penajaman pasca-audit adversarial: tutup celah isolasi laporan, e-sign anti-race + bagikan/terbit-ulang link, isolasi persediaan & penggunaan — 2026-07-18

Review adversarial 38-agent atas seluruh kode gelombang Mandat-2 (temuan
diverifikasi refutasi satu-per-satu) + kandidat lanjutan yang dijanjikan:
- **Isolasi satker DITUTUP MENYELURUH di jalur laporan** (temuan terberat):
  25 endpoint laporan/pengesahan per-kegiatan (BA, LHI, RHI, DBHI, DBKP,
  BAHI, SPTJM, SP, surat koreksi, eksekutif, laporan satker, rekap, batch
  ZIP, dokumen pengesahan, sahkan) kini ber-guard `pastikan_akses_kegiatan`;
  6 laporan pembukuan GLOBAL (Posisi, LBKP, CaLBMN, LKB, rekonsiliasi)
  ter-scope aset satker; arsip Pelaporan ter-scope; PUT kegiatan tidak bisa
  MEMINDAHKAN kegiatan ke satker lain; guard checklist aset kini efektif
  (projection membawa activity_id); rekap wasdal (`_data_pemantauan`)
  ter-scope sehingga Laporan Tahunan tidak lagi mencampur satker.
- **E-sign dikeraskan**: submit tanda tangan kini TULIS ATOMIK per-signer
  ($elemMatch + posisional; anti lost-update dua penanda tangan paralel,
  anti "hidup lagi" pasca-batal — blob kalah-race dibersihkan); halaman
  info menolak link lama yang jti-nya sudah diganti; token sesi BASI di
  browser tamu tidak lagi memblokir link e-sign valid (fallback ?token=);
  link/QR selalu absolut (fallback origin CORS bila APP_PUBLIC_URL kosong).
- **Fitur lanjutan e-sign**: tombol **Terbitkan Link ulang** per penanda
  tangan di dialog detail (link lama otomatis mati, ber-audit) + tombol
  **bagikan via WhatsApp/email** dengan pesan siap kirim (di dialog hasil
  & detail) — link tidak lagi hilang bila dialog pembuatan tertutup.
- **Kanvas TTD presisi**: bitmap kanvas kini mengikuti lebar container ×
  devicePixelRatio (pola resmi signature_pad) — goresan tidak lagi meleset
  dari jari/kursor dan tidak buram di HP.
- **Isolasi satker persediaan & penggunaan (lanjutan)**: item persediaan
  baru terikat satker pembuat; daftar + 8 endpoint per-item ber-guard;
  PSP & tiket idle ber-guard aset + ber-stamp satker; daftar PSP/idle/
  kandidat ter-scope (data era lama tetap terbuka — konsisten kegiatan).
- **Pembukuan**: KIB PDF tidak lagi crash (extend vs append blok ttd; juga
  di Laporan Tahunan Wasdal), "Asal Perolehan" KIB kini terisi
  (perolehan_dari_nama), jurnal Buku Barang menampilkan uraian & efek
  per kode, filter id aset jurnal berfungsi, indikator sengketa portofolio
  dihitung dari field nyata.
- Verifikasi: suite **504 lulus** (+2 uji scope-field & fallback token),
  423 route ter-mount, lint & build sukses.

---

## [#382] SEMUA MODUL AKTIF: SBSK & sanding usulan (Perencanaan) + Laporan Tahunan PMK 207 & portofolio (Wasdal) — 2026-07-18

Dua modul terakhir naik ke AKTIF — seluruh 16 modul registry kini AKTIF
(mandat "badge sebagian/segera → aktif" TUNTAS). Riset: PMK 138/2024 (SBSK)
& PMK 207/2021 (wasdal); angka lampiran dirawat admin (tabel konfigurabel).
- **Perencanaan → AKTIF**:
  - **Tabel standar SBSK** (PMK 138/2024) konfigurabel: koleksi
    `sbsk_standar` ber-seed baris terdokumentasi publik (ruang kerja
    pimpinan 247 m², kendaraan dinas per eselon — bertanda verifikasi
    Lampiran), CRUD admin di halaman Perencanaan; masuk RESET_KEEP.
  - **Sanding usulan** (`GET /perencanaan/usulan/{id}/sanding` + tombol
    "Sanding" per usulan): aset eksisting sejenis (prefix kode barang) —
    jumlah, sebaran kondisi, umur rata-rata, nilai — plus baris standar
    SBSK relevan dan CATATAN analisis otomatis (mis. "volume ≤ Rusak
    Berat → wajar penggantian" / "melebihi populasi — pastikan dasar
    SBSK"). Logika murni teruji.
- **Wasdal → AKTIF**:
  - **Laporan Tahunan Wasdal** (`GET /wasdal/laporan-tahunan-pdf`)
    mengikuti struktur Lampiran PMK 207/2021: I. pemantauan per objek,
    II. penertiban tahun berjalan + tindak lanjut, III. insidentil,
    IV. portofolio BMN & indikator tertib — PDF siap tanda tangan
    (tombol "Tahunan" di header Wasdal).
  - **Portofolio & SBSK** (`GET /wasdal/portofolio` + kartu dasbor):
    rekap per golongan (reuse DBKP, ambang efektif, scope satker) +
    indikator PSP/idle/sengketa + jumlah baris standar SBSK.
- Verifikasi: suite **502 lulus** (+4 uji SBSK/sanding), lint & build sukses.

---

## [#381] Pembukuan AKTIF: KIB per unit (PMK 181, pola SAKTI) + jurnal otomatis aset baru — 2026-07-18

Dua butir terakhir Pembukuan dilengkapi (riset format KIB SIMAK/SAKTI):
- **KIB — Kartu Identitas Barang per unit**: jenis terdeteksi dari kode barang
  (tanah gol 2, bangunan gedung gol 4, alat angkutan 302, alat besar 301,
  persenjataan 307) dengan **field khusus per jenis** (sertifikat/hak/luas;
  konstruksi/IMB/lantai; no polisi/rangka/mesin/BPKB; kaliber/no pabrik…):
  - `GET/PUT /pembukuan/kib/{asset_id}` — spesifikasi field + simpan data
    (disanitasi per jenis, ber-audit, ter-guard satker),
  - `GET /pembukuan/kib-pdf/{asset_id}` — kartu PDF resmi: data umum aset +
    data khusus (kosong = garis titik), foto aset, riwayat mutasi Buku
    Barang, blok ttd KPB, kop per-satker,
  - tab **KIB** di halaman Pembukuan: cari aset → form → cetak.
- **Jurnal otomatis dilengkapi**: aset BARU kini otomatis tercatat di Buku
  Barang (100 Saldo Awal / 101 Pembelian menurut asal perolehan, best-effort)
  — melengkapi auto-posting yang sudah ada dari Pengadaan (101), Penghapusan
  SK (301), Pemindahtanganan (302/303), Reklasifikasi (304/107).
- **Badge Pembukuan → AKTIF** (seluruh butir ✅). Semua modul Penatausahaan
  kini aktif.
- Verifikasi: suite **498 lulus** (+3 uji KIB murni); lint & build sukses.

---

## [#380] Badge modul naik: Pemusnahan & Pelaporan AKTIF, Pembukuan punya halaman (Segera → Sebagian) — 2026-07-18

Melengkapi fitur "menyusul" agar badge naik (mandat: badge sebagian/segera →
aktif), berdasarkan inventaris presisi seluruh registry modul:
- **Pemusnahan → AKTIF**: butir terakhir (kandidat otomatis Rusak Berat +
  tindak lanjut inventarisasi) sudah terwujud sejak Gelombang 5 (pemilih aset
  1-klik dibatasi Rusak Berat) — ditandai ✅.
- **Pelaporan → AKTIF**: fitur baru **Arsip Laporan Lintas Kegiatan** di hub
  Pelaporan (`GET /pelaporan/arsip`): naskah ber-nomor dari Persuratan
  (Laporan/BA) + kegiatan DISAHKAN (paket laporan final) + periode TERKUNCI
  (FINAL) — satu daftar riwayat ber-pencarian. Butir ekspor rekonsiliasi
  ditandai ✅ (rekonsiliasi XLSX + CSV jurnal + sinkron SIMAN sudah ada).
- **Pembukuan → SEBAGIAN** (dari Segera — satu-satunya modul tanpa halaman):
  halaman **Pembukuan** baru berisi DBKP global per golongan intra/ekstra
  (endpoint JSON baru `GET /pembukuan/dbkp`, ambang efektif + ringkas Posisi
  BMN di Neraca + persediaan) dan **Buku Barang** (jurnal mutasi ber-kode
  SIMAK/SAKTI berhalaman). Kartu modul kini enterable ("Buka Pembukuan").
  Butir DBKP/saldo/jurnal ditandai ✅; sisa menuju AKTIF: KIB A-F (PMK 181)
  + auto-posting jurnal penuh.
- Verifikasi: suite 495 lulus; lint & build sukses.

---

## [#379] Isolasi data per-satker: operator satker A tidak melihat/mengubah data satker B — 2026-07-18

Penegakan multi-satker DB bersama (M-SCOPE tahap inti — kegiatan + aset):
- **Helper terpusat** (`shared_utils`, teruji): `kode_satker_user`,
  `scope_query_kegiatan/aset` (filter `$in` kegiatan satker),
  `pastikan_akses_kegiatan/_id/aset` (403 dengan pesan jelas; kegiatan era
  lama tanpa kode tetap terbuka; user tanpa ikatan = lintas-satker).
- **Kegiatan**: daftar, detail, ubah, hapus, completion-status, satker-list —
  ter-scope; BUAT kegiatan ditolak bila kode_satker ≠ satker user.
- **Aset**: daftar+filter+stats+analytics+next-nup+offline-snapshot ter-scope
  (CACHE KEY kini membawa kode satker — cache "__all__" tidak lagi bocor
  lintas satker); detail/media/foto/checklist/BAST ter-guard; create/update/
  patch/delete/rotate/batch-update ter-guard (pindah kegiatan divalidasi ke
  satker yang sama); import per kegiatan ter-guard.
- **Ekspor**: CSV/PDF/XLSX/geo (KML/KMZ/SHP) + hapus massal per kegiatan —
  ter-scope/guard.
- Verifikasi: suite **495 lulus** (+4 uji helper scope), 411 route ter-mount.

---

## [#378] Halaman Pengaturan terpadu: satu pintu setelan universal ↔ per-satker ↔ sistem — 2026-07-18

Konsolidasi setelan yang tersebar (mandat: "jadikan satu halaman setting"):
- **Halaman "Pengaturan"** baru di Beranda Modul dengan 3 tab:
  - **Universal** — editor kop/logo/judul laporan global (komponen
    `ReportSettingsEditor` yang sama dengan di Rekap — satu sumber), plus
    PINTASAN setelan universal lain di modulnya (Persuratan: format nomor &
    klasifikasi; Akuntansi BMN: akun BAS/pemetaan/ambang; Pelaporan: periode
    & tenggat) — tetap satu pintu tanpa duplikasi editor.
  - **Per-Satker** — panel Master Satker yang sama (komponen `SatkerPanel`
    hasil ekstraksi) untuk override kop per satker; resolusi
    kegiatan → satker → universal dijelaskan inline.
  - **Sistem** — mulai **backup** langsung (job background, panel progres
    global); restore/reset SENGAJA tetap di halaman pemilihan kegiatan
    (aksi destruktif berlapis konfirmasi), dengan penjelasan bahwa reset
    kini mempertahankan seluruh setelan/pemetaan.
- Verifikasi: suite 491 lulus, lint & build sukses.

---

## [#377] Master Satker: satker jadi entitas kelas satu + kop laporan per-satker + ikatan user→satker — 2026-07-18

Fondasi multi-satker DB bersama (Mandat-2, sesuai pilihan arsitektur):
- **Koleksi master `satker`** (kode unik): profil + field kop per-satker
  (unit organisasi, sub-unit, alamat, tempat & tembusan laporan, kontak,
  eselon1). CRUD admin + **Sinkron dari Kegiatan** (registrasi otomatis
  semua satker yang sudah ada di kegiatan, idempoten, tidak menimpa profil).
  Satker BARU juga terdaftar otomatis saat kegiatan pertamanya dibuat.
  Master masuk `RESET_KEEP` (selamat reset, tetap ikut backup).
- **Kop laporan per-satker**: resolusi `kegiatan → master satker → global`
  (`gabung_kop`, teruji): field satker non-kosong menimpa setelan global;
  baris ke-3 kop otomatis = nama satker bila tidak diisi. Diterapkan pada
  **13 generator laporan ber-kegiatan** (LHI, DBHI, BA, DBKP kegiatan, dst.)
  via `pengaturan_kop(activity)` — laporan global tetap memakai setelan global.
- **Halaman "Master Satker"** di Beranda Modul: daftar (terdaftar / belum +
  jumlah kegiatan), sinkron 1-klik, form profil kop, hapus (ditolak bila
  masih dipakai kegiatan).
- **Ikatan user → satker** (`PUT /users/{id}/satker` + dropdown di Kelola
  Pengguna): kode terisi = user bekerja untuk satker itu; KOSONG =
  lintas-satker — **admin lintas-satker berperan super-admin** (pola ini
  dipilih alih-alih role kelima). Penegakan isolasi data menyusul (M-SCOPE).
- Verifikasi: suite **491 lulus** (+4 uji resolusi kop), lint & build sukses.

---

## [#376] Pengamanan akses & data: viewer read-only ditegakkan server, reset simpan pemetaan, ambang kapitalisasi jadi setelan — 2026-07-18

Tiga penguatan hasil audit keamanan & backup (Mandat-2):
- **`require_writer` — viewer read-only kini ditegakkan SERVER** (bukan hanya
  disembunyikan UI): **62 endpoint tulis** di 23 modul (aset, kegiatan,
  persediaan, persuratan, BAST, pengadaan…s.d. e-sign) menolak role `viewer`
  dengan 403 berpesan jelas; role legacy `user` = operator. Endpoint baca-rupa
  (kartu massal, validasi, kompres media, unduh laporan) sengaja tetap terbuka
  semua role.
- **Reset data tidak lagi menghapus pemetaan/konfigurasi satker**:
  `RESET_KEEP` kini juga mempertahankan `akun_bas`, `persediaan_akun` (tanpa
  seed otomatis — hilang = setup ulang manual), `masa_manfaat`,
  `persuratan_settings`, `klasifikasi_arsip`, `referensi_akun`. Semuanya tetap
  ikut backup.
- **Ambang kapitalisasi PMK 181 jadi SETELAN** (`GET/PUT
  /pembukuan/ambang-kapitalisasi`, admin): override golongan 3/4 tersimpan di
  `report_settings {type: "kapitalisasi"}` (selamat reset, ikut backup) dan
  dipakai SEMUA laporan pembukuan — DBKP, LBKP, CaLBMN, Posisi BMN,
  rekonsiliasi XLSX — termasuk catatan kaki ambangnya. Golongan selain 3/4
  ditolak (tanah/jalan tidak boleh diam-diam keluar neraca); nilai rusak jatuh
  ke default (teruji). UI: kartu "Ambang Kapitalisasi" di Referensi Akun BAS
  tab Akun Aset (ubah/kembalikan default, badge override).
- Verifikasi: suite **487 lulus** (+5 uji baru), 405 route ter-mount, lint &
  build frontend sukses.

---

## [#375] Tanda Tangan Digital (slice 2): e-sign via LINK — halaman publik, urutan, QR & lembar pengesahan — 2026-07-18

Setiap penanda tangan kini bisa menandatangani dokumen **melalui link yang
dibagikan** (WA/email) — dari HP/komputer masing-masing, **tanpa akun**.
- **Permintaan TTD** (`POST /ttd/permintaan`): judul + daftar penanda tangan →
  link pribadi per orang (JWT `typ=sign`, umur 14 hari, `jti` **sekali pakai**).
  Mode **paralel** (semua langsung) atau **berurutan** (sesuai giliran — penanda
  tangan berikutnya aktif otomatis setelah yang sebelumnya selesai).
- **Halaman publik `/ttd/:id`** (tanpa login, dicek sebelum gate auth):
  identitas penanda tangan + kanvas goresan mulus / unggah foto (hapus
  background otomatis — endpoint `olah-foto` kini menerima token tamu).
  Kirim → PNG ke GridFS + **hash SHA-256** + waktu + IP tercatat.
- **Verifikasi publik `/ttd/verifikasi/:id`** (dibuka dari QR): siapa sudah
  menandatangani & kapan — tanpa membocorkan gambar/hash/jti.
- **Lembar Pengesahan (PDF)**: tabel penanda tangan ber-gambar TTD + QR
  verifikasi + kode dokumen (`GET /ttd/permintaan/{id}/lembar-pdf`).
- **Dasbor "Tanda Tangan Elektronik"** di Beranda Modul: buat permintaan
  (saran nama dari Master Pegawai), salin link per orang, pantau status
  (x/y menandatangani), batalkan, unduh lembar pengesahan.
- Interceptor 401 mengecualikan endpoint tamu (`/ttd/tandatangan|verifikasi|
  olah-foto`) — link kedaluwarsa tidak lagi men-logout user yang kebetulan
  sedang login.
- Verifikasi: suite **482 lulus** (+4 uji token/link e-sign); 13 route `/ttd`
  ter-mount; lint & build frontend sukses.

---

## [#374] Tanda Tangan Digital (slice 1): kanvas mulus + foto hapus-background + tersemat ke PDF — 2026-07-17

Fitur baru (riset library terverifikasi): spesimen tanda tangan digital per
pejabat/pegawai, otomatis tersemat pada blok TTD laporan/BA.
- **Kanvas goresan mulus** (`react-signature-canvas` di atas signature_pad —
  kurva Bézier variable-width dari kecepatan, garis menebal saat melambat,
  latar transparan) — komponen bersama `SignatureCapture`.
- **Unggah foto → PNG transparan** (`POST /ttd/olah-foto`): background dihapus
  otomatis dengan Pillow+numpy (normalisasi cahaya → ambang Otsu → alpha
  anti-alias → auto-crop) — **tanpa library berat/model** (teruji unit).
- **Spesimen tersimpan** di GridFS per pejabat/pegawai (`ttd_file_id`):
  `PUT/GET/DELETE /ttd/spesimen/{pejabat|pegawai}/{id}` (simpan admin,
  hapus blob lama, stream ber-token).
- **Tersemat ke PDF**: `_signature_block` merender gambar TTD (`RLImage
  mask='auto'`) menggantikan celah tanda tangan basah bila spesimen ada;
  KPB dari registry membawa `ttd_file_id` → tanda tangan muncul otomatis di
  DBKP/LBKP/BAST "Mengetahui KPB". Fallback ke celah kosong bila belum ada.
- Dikelola dari halaman **Referensi Pejabat** (tombol pena + pratinjau).
- Catatan: ini e-seal internal satker; e-sign via LINK per dokumen (token
  penanda tangan + urutan + QR/hash verifikasi) menyusul di slice berikutnya.
- Verifikasi: suite **478 lulus** (+3 uji TTD); smoke PDF (gambar tersemat);
  lint & build frontend sukses.

---

## [#373] Gelombang 8-4: siklus pegawai-pejabat (status & masa jabatan) — 2026-07-17

Batch terakhir audit keamanan — konsistensi identitas orang sepanjang siklus:
- **Penandatangan "Mengetahui, KPB" pada BAST kini dari REGISTRY pejabat**
  yang **berlaku pada tanggal BAST** (`penandatangan_kpb`, fallback setelan
  kasatker) — tak lagi membaca setelan mentah yang bisa kedaluwarsa.
- **Peringatan penerima non-aktif**: membuat BAST untuk pegawai berstatus
  pensiun/mutasi/nonaktif memunculkan peringatan lunak (tak memblokir) — via
  `is_aktif`.
- **Badge status pemegang non-aktif** di halaman Penggunaan
  (`pegawai_master_status` diteruskan ke UI) — pemegang pensiun langsung
  terlihat untuk ditindaklanjuti (mutasi/pengembalian).
- **Dedup NIP pejabat**: tambah/ubah pejabat menolak NIP yang sudah dipakai
  pejabat lain (409) — mencegah dua penanda tangan ber-NIP sama.
- Catatan: resolusi ulang PJ Ruangan KIR terhadap masa berlaku & penegakan
  status pada `enforce_pegawai_terdaftar` ditandai sebagai penajaman lanjutan
  (perlu kebijakan pemilik) — **Gelombang 8 & seluruh mandat pengembangan
  dinyatakan TUNTAS**.
- Verifikasi: suite **475 lulus**; lint & build frontend sukses.

---

## [#372] Gelombang 8-3: pengamanan unggah/berkas (zip-slip, batas ukuran, magic byte, GridFS yatim) — 2026-07-17

Batch upload-hardening dari audit keamanan terverifikasi:
- **Zip-slip / path traversal saat restore backup ditutup**: entri ZIP yang
  di-resolve ke luar `UPLOADS_DIR` (absolut atau ber-`..`) ditolak — restore
  tak bisa lagi menimpa berkas di luar folder uploads.
- **Batas ukuran impor Excel/CSV** 15MB (cegah zip-bomb/OOM openpyxl);
  `file.filename` None tak lagi meng-crash (`(file.filename or "")`).
- **Cek magic byte gambar** pada lampiran (JPEG/PNG/WEBP/GIF) — spoofing tipe
  via ekstensi ditolak (helper murni `cek_magic_gambar`, teruji).
- **Content-Disposition aman**: nama file di-sanitasi (buang CR/LF/kutip/`;`/
  pemisah path) + header `X-Content-Type-Options: nosniff` pada stream
  lampiran (helper `nama_file_disposition`).
- **GridFS tak lagi yatim**: re-upload bukti TTD BAST menghapus blob lama;
  bila BAST terhapus di sela (matched_count 0), blob baru dihapus & 404.
- Verifikasi: suite **475 lulus**; compile & build hijau.

---

## [#371] Gelombang 8-2: anti-injeksi (regex ReDoS + markup PDF) & guard tanggal — 2026-07-17

Batch injeksi & keandalan input dari audit keamanan terverifikasi:
- **Regex Mongo dari input user kini di-`re.escape`** (anti-ReDoS/regex
  injection) di pencarian: Persuratan buku agenda (`q` 6 field), Riwayat
  BAST (`q`), Kodefikasi (`search` kode+uraian), Persediaan master
  (`search` kode/nama/merk) — melengkapi Kategori (#370).
- **Markup injection tersimpan → PDF ditutup**: field user (nama aset,
  uraian, pelaksana, no. bukti, nama pemegang, keterangan) kini di-XML-escape
  sebelum masuk ReportLab Paragraph di **DHPB Pemeliharaan**, **Daftar Barang
  Digunakan**, dan **BA Pemusnahan** — selaras pola escape reports.py/bast.py.
- **Guard tanggal non-numerik**: `int(tgl_surat[:4])` pada booking otomatis
  BAST & LPB persediaan kini jatuh ke tahun berjalan bila 4 digit awal bukan
  angka (tak lagi 500 mentah).
- Verifikasi: suite **475 lulus**; compile & build hijau.

---

## [#370] Gelombang 8-1: pengamanan gerbang otorisasi (audit keamanan terverifikasi) — 2026-07-17

Hasil **audit keamanan otomatis** (5 auditor paralel + verifikasi adversarial
per temuan): 6 celah otorisasi TERKONFIRMASI ditutup —
- **Hapus massal aset** (`DELETE /assets/bulk-delete/{activity_id}`) kini
  **admin-only** (sebelumnya `require_user` — operator/viewer bisa menghapus
  permanen SELURUH aset satu kegiatan, padahal hapus SATU aset admin-only);
  pelaku audit diambil dari identitas terautentikasi, bukan header
  `X-Audit-User` yang bisa dipalsukan.
- **Transisi tiket proses penggunaan** (`/penggunaan/proses/{id}/status`)
  kini **admin-only** — status terminalnya memproyeksikan aset KELUAR
  pembukuan satker, setara transisi PSP & idle yang memang admin-only.
- **`POST /compress-pdf`** kini wajib login (sebelumnya TANPA auth sama
  sekali — bisa menguras kuota API pihak ketiga) + batas ukuran **25MB** +
  validasi magic byte `%PDF` + sanitasi nama file header; `GET
  /pdf-compression-quotas` juga di-gate.
- **Hapus kategori** (master data) kini **admin-only** (selaras kodefikasi &
  hapus-semua kategori).
- **Daftarkan periode pelaporan** kini **admin-only** (seluruh siklus
  kunci/buka/hapus/tenggat sudah admin-only).
- **GET `/categories`, `/categories/all`, `/categories/import-progress`**
  kini wajib login; pencarian kategori di-`re.escape` (anti ReDoS) &
  `page/page_size` di-clamp (anti skip negatif → 500).
- Verifikasi: suite **475 lulus**; compile & build hijau.

---

## [#369] Gelombang 7 (lanjutan): jurnal terisi dari modul + backfill saldo awal — 2026-07-17

- **Modul-modul kini menulis Buku Barang otomatis** (`catat_mutasi_bmn` di
  shared_utils — best-effort, tidak pernah menggagalkan transaksi pemanggil):
  - **Pengadaan** — tiap draft aset dari perolehan → **101/102/103/105**
    sesuai jenis (kode dari `JENIS_PEROLEHAN`), nilai = harga satuan,
    tanggal buku = tanggal BAST.
  - **Penghapusan** — SK terbit → **301** (tanggal buku = tanggal SK).
  - **Pemindahtanganan** — selesai → **303** (hibah) / **301** (bentuk lain,
    keluar via SK penghapusan) per aset usulan.
- **Backfill saldo awal** (`POST /pembukuan/mutasi/backfill`, admin,
  idempoten): aset aktif tanpa entri jurnal diberi satu entri sintetis
  **100 Saldo Awal** (tanggal buku = tanggal perolehan) — setiap aset punya
  titik awal di Buku Barang.
- Verifikasi: suite **475 lulus**; build frontend sukses (tanpa perubahan UI).

---

## [#368] Gelombang 7 (inti): Jurnal Mutasi BMN + Reklasifikasi ber-riwayat + SIMAN sadar-reklasifikasi — 2026-07-17

- **Riset terverifikasi dulu** (pustaka §2.6 baru): dalam praktik SIMAK/SAKTI
  yang otoritatif adalah **rekaman transaksi ber-kode per NUP** — Buku
  Barang/DBKP/KIB hanyalah proyeksi; reklasifikasi = pasangan **304/107**
  periode sama nilai sama, NUP baru di kode baru membawa tanggal & nilai
  perolehan asli; **kode register SIMAN 16 digit** = identitas yang tak
  pernah berubah (kunci sanding tahan-reklasifikasi).
- **Jurnal `mutasi_bmn` append-only** ("Buku Barang" AMAN): logika murni
  `mutasi_bmn_utils.py` (kode transaksi 100–401 selaras SIMAK/SAKTI, arah
  tambah/kurang/netral, validasi entri, rekap saldo per sub-sub kelompok per
  periode) + `GET /pembukuan/mutasi` (filter aset/kode/periode).
- **Reklasifikasi kodefikasi ber-riwayat** (`POST /pembukuan/reklasifikasi`):
  kode+NUP diperbarui **in-place** — aset TIDAK dibuat ulang (id internal &
  kode register SIMAN tetap → sinkron tidak putus); NUP baru berurut di kode
  tujuan; `riwayat_reklasifikasi` tercatat di aset; pasangan jurnal 304/107
  terekam; kode '1…' (persediaan) ditolak. Dialog **"Reklasifikasi"** di hub
  Pelaporan (admin): cari aset → kode tujuan 10 digit → alasan.
- **Sinkron SIMAN sadar-reklasifikasi**: register cocok tapi kode/NUP beda
  kini dikenali sebagai **sinyal reklasifikasi** (`siman.reklasifikasi`
  subdoc) — bukan sekadar daftar selisih field.
- Kegiatan inventarisasi dipertegas sebagai **pemutakhir** pembukuan (bukan
  induk) — alur resmi terdokumentasi di pustaka §2.6.
- Menyusul (G7 lanjutan): pengisian jurnal dari semua modul + backfill,
  LBKP membaca jurnal, aksi "terapkan reklasifikasi" 1-klik dari kartu SIMAN.
- Verifikasi: suite **475 lulus** (+5 uji jurnal/reklasifikasi); lint &
  build frontend sukses.

---

## [#367] Gelombang 6 (tuntas): ribbon kegiatan ber-afordansi + sliver form berlabel — 2026-07-17

- **Ribbon status kartu kegiatan** kini ber-chevron kecil — jelas bahwa
  ribbon adalah TOMBOL (validasi/pengesahan) yang aksinya berbeda dari
  klik kartu.
- **Sliver buka-form desktop berlabel**: saat panel form dilipat, tombol
  tepi melebar dan berlabel vertikal "FORM" — jalan kembali ke form
  Tambah Aset tidak lagi nyaris tak terlihat (5px polos).
- Catatan: perampingan dialog Buat Kegiatan (2 field wajib + lipatan)
  DITUNDA sadar — form tsb. dipakai alur lapangan yang sudah stabil;
  risiko regresi > nilai kosmetiknya. **Gelombang 6 dinyatakan TUNTAS.**
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#366] Gelombang 6 (lanjutan): saklar mode di semua ukuran layar + grup Referensi & Master Data — 2026-07-17

- **Saklar Dashboard | Inventarisasi kini berlabel di SEMUA breakpoint**:
  desktop (lg+) yang sebelumnya **tidak punya saklar sama sekali** kini
  mendapat kolom saklar di baris statistik; toggle tablet yang tadinya
  `Switch` polos tanpa teks diganti saklar berlabel yang sama dengan mobile
  (satu komponen `InventoryModeSwitch` untuk semuanya).
- **Grup "Referensi & Master Data"** di Beranda Modul: 6 pil mengambang
  (Kodefikasi, Pejabat, Ruangan, Akun BAS, Pegawai, Persuratan) kini rapi
  dalam grid bertajuk — perataan tak lagi kacau saat wrap, pengguna baru
  langsung paham ini kelompok data referensi.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#365] Gelombang 6 (inti): Lupa Password via OTP, pintu Info terlihat, tombol simpan berlabel jelas — 2026-07-17

- **Lupa Password via OTP email** — jalan buntu login tertutup:
  `POST /auth/request-reset-otp` (respons selalu generik agar keberadaan
  akun tidak bocor; OTP di namespace `reset:` terpisah dari registrasi;
  rate-limit 3/menit) + `POST /auth/reset-password` (verifikasi OTP +
  password baru ≥8 karakter). Panel "Lupa password?" di halaman masuk:
  email → OTP + password baru — memakai infrastruktur OTP yang sudah ada.
- **Pintu Info/Bantuan terlihat**: tombol "?" di header Beranda Modul —
  halaman Tentang tidak lagi tersembunyi di balik 3-klik logo.
- **Tombol simpan lembar lapangan berlabel jelas**: tombol kecil kini
  "Simpan & Tutup" (dengan tooltip) — tak tertukar dengan "Simpan & Lanjut";
  hover mengikuti kaidah aksen proyek.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#364] Gelombang 5 (tuntas): cek silang register keluar + glosarium akronim — 2026-07-17

- **Cek silang "in-flight" lintas register keluar** (`proses_keluar_aktif`
  di shared_utils): saat membuat usulan Penghapusan / Pemindahtanganan /
  BA Pemusnahan, sistem memeriksa apakah aset yang sama sedang berada di
  jalur keluar LAIN — bila ya, muncul **peringatan non-blocking** per aset
  ("juga dalam usulan pemindahtanganan…") sehingga satu aset tidak diam-diam
  menempuh dua jalur keluar sekaligus.
- **Glosarium akronim**: tooltip penjelas pada istilah regulasi (PMPP di
  header Pemindahtanganan, LHIP di Penilaian, NTPN pada field bukti setor).
- Catatan: refactor `AssetSearchSelect` bersama & edit register saat
  "diusulkan" dicatat sebagai peningkatan teknis lanjutan (tidak mengubah
  perilaku pengguna) — Gelombang 5 dinyatakan TUNTAS.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#363] Gelombang 5 (lanjutan): dialog transisi bersama — window.prompt hilang dari seluruh aplikasi — 2026-07-17

- **Komponen bersama `useTransitionDialog`** (`components/ui/
  TransitionDialog.jsx`): Dialog kecil ber-field (text/date/textarea) dengan
  validasi wajib + date-picker, berbasis promise (pola `useConfirm`) — ramah
  mobile & dark mode.
- **Seluruh `window.prompt` diganti** (audit lintas #1 — rantai 2–3 prompt
  native paling menyakitkan di mobile):
  - Penggunaan: transisi tiket proses (nomor+tanggal+catatan jadi SATU
    dialog) & status PSP (SK wajib nomor+tanggal; tolak/kembalikan wajib
    catatan).
  - Pengamanan: transisi status kasus.
  - Perencanaan: status usulan RKBMN (catatan wajib saat dikembalikan).
  - Pelaporan: alasan buka-kunci periode (wajib) & tenggat penyampaian
    (date-picker, kosongkan = hapus).
- `window.prompt` kini **0 pemakaian** di seluruh halaman.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#362] Gelombang 5 (inti): temuan wasdal bisa ditindaklanjuti, kandidat Rusak Berat 1-klik, revert Penghapusan — 2026-07-17

- **Temuan Wasdal → tombol "Tindak lanjuti"**: setiap temuan pemantauan kini
  membuka tiket penertiban **ter-prefill** (objek, uraian, tautan aset) —
  temuan tak lagi read-only yang harus disalin manual ke register penertiban.
- **Kandidat Rusak Berat 1-klik di Pemusnahan**: membuka dialog BA langsung
  menampilkan daftar aset Rusak Berat tanpa harus mengetik; memilih aset
  **tidak lagi mereset pencarian** (multi-aset lancar) — juga di
  Pemindahtanganan.
- **Revert Penghapusan**: status "diproses" bisa **dikembalikan ke
  "diusulkan"** (koreksi salah klik); status terminal tetap terkunci
  (`TRANSISI_USULAN` + tombol "Kembalikan").
- Verifikasi: suite **470 lulus** (uji transisi diperbarui); lint & build
  frontend sukses.

---

## [#361] Gelombang 4 (tuntas): "Daftarkan ke Persediaan" dari BAST konsumsi — 2026-07-17

- **Jalur BAST barang konsumsi tersambung** (`POST /pengadaan/{id}/
  daftarkan-persediaan`): barang perolehan ber-kode persediaan (awalan '1')
  kini bisa didaftarkan sekali klik — master persediaan dibuat otomatis bila
  belum ada (kode 10 digit dilengkapi nomor urut, NUP otomatis), lalu
  transaksi masuk berjalan lewat jalur `transaksi_masuk` yang sudah atomik +
  berjurnal FIFO + ber-FK dokumen sumber; baris ber-`psd_item_id` dilewati
  (idempoten).
- Tombol **"Daftarkan ke Persediaan"** muncul pada baris perolehan yang
  punya barang konsumsi belum terdaftar — melengkapi "Buat Draft Aset"
  (simetri aset ↔ persediaan; Gelombang 4 SELESAI).
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#360] Gelombang 4 (lanjutan): draft aset per-NUP, CSV Perencanaan, penjelas pintu masuk — 2026-07-17

- **Draft aset pecah per-NUP**: "Buat Draft Aset" dari perolehan Pengadaan
  kini membuat **N draft ber-NUP berurut** bila jumlah barang 2–50 unit
  (BMN: 10 laptop = 10 NUP) — bukan satu draft dengan catatan; di luar
  rentang itu perilaku lama + catatan jumlah dipertahankan.
- **Ekspor CSV register usulan RKBMN** (`GET /perencanaan/usulan/export`)
  + tombol CSV di halaman Perencanaan — melengkapi pola register lain.
- **Penjelas pintu masuk barang**: dialog Transaksi Massal menjelaskan
  LPB otomatis & posisi register Pengadaan (tertib dokumen, bukan stok);
  placeholder saat daftar perolehan kosong menautkan ke modul Pengadaan.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#359] Gelombang 4 (inti): rantai perolehan tersambung — 2026-07-17

- **Dropdown "Usulan RKBMN terkait"** pada dialog usulan Penganggaran —
  mengaktifkan FK `rkbmn_id` yang sudah lengkap di backend: memilih usulan
  RKBMN dari modul Perencanaan otomatis mengisi uraian/jenis/TA sasaran
  (tak ada lagi ketik ulang antar modul).
- **Serapan nyata dari Pengadaan tampil**: kartu Serapan kini menampilkan
  "Realisasi Pengadaan tertaut" (total nilai perolehan ber-`penganggaran_id`)
  di samping angka realisasi manual.
- **Riwayat LPB**: menu Dokumen Persediaan bertambah "Riwayat LPB (unduh
  ulang)" — LPB tak lagi hilang bila unduhan pertama gagal/tertutup.
- **Auto-isi picker massal**: memilih Perolehan (Pengadaan) pada dialog
  Transaksi Massal kini mengisi penyedia/tanggal/no bukti/jenis dokumen —
  selaras dialog masuk tunggal.
- Verifikasi: lint & build frontend sukses.

---

## [#358] Gelombang 3 (lanjutan): badge FINAL, pintu Kop/Sampul di hub, legenda nomor eksternal — 2026-07-17

- **Badge status periode pada opsi unduh** LBKP & CaLBMN: tiap opsi kini
  bersufiks **"· FINAL"** (periode terkunci) atau **"· belum final"** —
  operator sadar sebelum mengedarkan laporan yang belum dikunci.
- **Pintu "Kop/Sampul" di hub Pelaporan** (admin): editor pengaturan kop/
  logo/penanda tangan kini bisa dibuka langsung dari halaman Pelaporan —
  tak perlu lagi masuk lewat kegiatan inventarisasi tertentu.
- **Legenda "eks:"** pada header kolom Nomor buku agenda: menjelaskan nomor
  sah aplikasi eksternal (Srikandi dll.) vs nomor agenda internal.
- Verifikasi: lint & build frontend sukses (perubahan murni frontend).

---

## [#357] Gelombang 3 (inti): nomor booking mengalir ke PDF laporan — 2026-07-17

- **Booking → cetak tersambung**: PDF **Berita Acara** (BAHI & BA Tim
  Internal Tidak Ditemukan) kini otomatis memakai **nomor surat ter-booking/
  disahkan terbaru** kegiatan itu dari Registrasi Persuratan bila field nomor
  BA kegiatan kosong (`_nomor_terbooking`) — nomor yang dipesan lewat tombol
  Booking Nomor tak lagi berhenti di clipboard (temuan utama audit area
  Persuratan-Pelaporan).
- Dialog hasil Booking Nomor menjelaskan perilaku otomatis ini.
- **Periode tahun lalu bisa didaftarkan** (Semester II & Tahunan th-1) —
  LBKP/CaLBMN tahun lalu kini bisa berpenanda FINAL; dropdown unduh LBKP &
  CaLBMN bertambah **Semester I/II tahun lalu** untuk kebutuhan audit lampau.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#356] Gelombang 2: BAST menyatu dengan kelengkapan pemegang — 2026-07-17

- **Bukti ttd BAST kini menaikkan kelengkapan**: unggah bukti menautkan
  `bast_file_id` ke SEMUA aset objek BAST → metrik "BAST x/y" & badge
  "Lengkap" pemegang langsung hidup (sebelumnya generator BAST tak pernah
  mengisinya — temuan audit terpenting area Penggunaan).
- **Badge aset tak lagi bertentangan**: aset ber-BAST tanpa bukti kini
  berbadge **"Bukti belum diunggah"** (bukan "Tanpa BAST" di samping badge
  "BAST <tanggal>").
- **Riwayat BAST terkunci identitas**: difilter **NIP penerima** bila ada
  (parameter `nip` pada `GET /bast`) — nama mirip tak tercampur.
- **Penerima BAST dari Master Pegawai**: autocomplete (datalist) di kolom
  nama — nama persis cocok → NIP & jabatan terisi otomatis; jabatan prefill
  kini dari **jabatan master** (bukan unit kerja).
- **Chip "belum di master"** pada baris pemegang yang NIP-nya tak terdaftar
  di Master Pegawai (enrichment backend yang dulu tak pernah ditampilkan).
- **Detail pemegang menyegarkan diri** setelah BAST non-mutasi (badge BAST
  terakhir langsung tampak); **hint saat daftar penyerah kosong** menuntun
  ke Referensi Pejabat; **helper 1 baris per jenis BAST** menjelaskan kapan
  memakai jenis apa.
- Verifikasi: suite **470 lulus**; lint & build frontend sukses.

---

## [#355] Audit alur seluruh aplikasi + Gelombang 1: keandalan & umpan balik dasar — 2026-07-17

- **Audit uji-alur menyeluruh** (6 penelusur paralel, ±85 temuan berperingkat
  lintas 25 halaman): hasil + **alur terbaik per area** + backlog bertahap
  Gelombang 2–6 dicatat di **`docs/AUDIT-ALUR-APLIKASI.md`**.
- **Gelombang 1 diterapkan** (keandalan & umpan balik dasar):
  - **Konfirmasi sebelum hapus** di jalur yang tadinya langsung eksekusi:
    tiket penertiban & insidentil Wasdal, periode pelaporan, override akun
    (golongan & sub-kelompok), catatan SK PSP, logo kop.
  - **Error tak lagi senyap**: gagal memuat referensi persuratan → toast;
    gagal memuat ringkasan SIMAN → badge "coba lagi" pada kartu; pesan error
    server diteruskan (`apiErr`) di pemetaan akun; alasan buka-kunci periode
    kosong → pesan jelas.
  - **Guard "self" API users diperkuat**: nonaktifkan/hapus/turunkan role
    diri sendiri kini ditolak berdasarkan identitas terautentikasi (bukan
    parameter opsional yang bisa dikosongkan).
  - **Label & istilah dibenahi**: "Email atau Username" saat masuk;
    "On Going/Ongoing" → "Berlangsung"; empty-state kegiatan menyesuaikan
    peran; tooltip pil sinkron di header.
  - **Afordansi Beranda Modul**: kartu Tahap Siklus kini ber-CTA
    "Masuk Modul ›" / "Lihat Konsep ›" — jelas mana yang bisa dibuka.
  - **Editor Sampul LHI**: catatan "berlaku global untuk semua laporan/
    kegiatan", warna aman dark-mode, tap-target 44px & hover dibenahi.
  - **Pencarian Referensi Akun di-debounce** 350ms (pola Kodefikasi).
- Verifikasi: suite **470 lulus**; lint 11 berkas terdampak & build sukses.

---

## [#354] Tabel aset ringkas (BAST & Daftar Barang), pasal textarea, penyerah dari Referensi Pejabat, & review peran pengelolaan BMN — 2026-07-17

- **Tabel aset diringkas jadi dua kolom gabungan** (BAST + "Unduh Daftar
  Barang" pemegang) agar teks panjang lega:
  - **Identitas Barang** — Sub-sub Kelompok (dari referensi kodefikasi,
    otomatis) di atas, lalu `kode barang · NUP` di bawah.
  - **Uraian Barang** — Nama Barang di atas, lalu Merk/Tipe/Spesifikasi
    (brand · model · serial) di bawah.
  - Helper bersama baru di `reports.py` (`_peta_subsub_kelompok`,
    `_sel_identitas_barang`, `_sel_uraian_barang`) dipakai kedua dokumen.
- **Input pasal/ketentuan tambahan kini `textarea`** (bukan input satu
  baris): tiap baris menjadi satu butir pada pasal **"Ketentuan Tambahan"**.
- **"Yang menyerahkan" (PIHAK KESATU) dapat dipilih dari Referensi Pejabat**
  pada dialog Buat BAST — hanya peran **pengelolaan BMN** yang layak
  (disaring `peran_penyerah_bast`: KPB, Petugas Penatausahaan BMN, Pengelola
  BMN Satker). Bila penyerah **bukan KPB**, dokumen otomatis ditandai
  **"a.n. Kuasa Pengguna Barang"** + baris **"Mengetahui, KPB"** (kaidah
  pendelegasian). Kosong = otomatis memakai KPB dari pengaturan.
- **Review peran pengelolaan BMN (riset regulasi terverifikasi, §11B
  pustaka):** "Pengurus Barang / Penyimpan Barang" adalah istilah **Barang
  Milik DAERAH** (PP 27/2014; Permendagri 7/2024) — **menyesatkan untuk BMN
  pusat**; label `pengurus_barang` kini ditandai *"hindari"* (dipertahankan
  demi data lama). Ditambah peran BMN-pusat yang tepat: **Petugas
  Penatausahaan BMN / Penata Laksana Barang (JFPLB, PermenPAN-RB 23/2018)**,
  **Pengelola BMN Satker (a.n. KPB)**, **Verifikator/Validator BMN**. Tiap
  peran diberi **metadata** (domain bmn/bmd, peran pada BAST, keterangan
  berbasis regulasi) yang dijelaskan langsung di UI Referensi Pejabat —
  menjawab "apa beda pengurus penatausahaan BMN vs pengurus barang".
- Verifikasi: suite **470 lulus** (+2 uji peran/metadata); smoke FakeDB
  (BAST 2 hlm ringkas + a.n. KPB + Mengetahui + pasal 2 butir; Daftar
  Barang 1 hlm + Sub-sub Kelompok); lint & build frontend sukses.

---

## [#353] Bukti TTD BAST + pengesahan agenda otomatis, Riwayat BAST, dan penyempurnaan lintas modul — 2026-07-17

- **Unggah bukti BAST bertanda tangan** (`POST /bast/{id}/bukti`, PDF/JPG/PNG
  ≤ 10 MB ke GridFS): begitu bukti terunggah, **nomor agenda surat yang masih
  berstatus "dibooking" otomatis DISAHKAN** (siklus booking → sah tuntas tanpa
  langkah manual di modul Persuratan). Bukti dapat dilihat kembali lewat
  `GET /bast/{id}/bukti` (streaming ber-token, `inline`).
- **Dialog "Riwayat BAST"** di halaman Penggunaan (per pemegang): daftar BAST
  dengan tombol **Pratinjau** (tab baru), **Unduh**, **Unggah Bukti TTD**, dan
  **Lihat Bukti** — riwayat serah terima kini bisa ditelusuri tanpa keluar
  dari halaman.
- **Pratinjau PDF ber-token**: `bast_pdf` dan `lpb_pdf` kini menerima
  `?token=` (`require_user_or_query_token`) sehingga tombol pratinjau
  `window.open` berfungsi seperti laporan lain.
- **Wasdal — penanda tenggat**: kartu lintas modul baru **"BAST penggunaan
  sementara lewat tenggat kembali"** menghitung BAST `penggunaan_sementara`
  yang `jangka_sampai`-nya sudah lewat hari ini.
- **Validasi lunak penerima BAST**: NIP Pihak Kedua dicek ke **Master
  Pegawai** — jika tidak terdaftar, respons menyertakan `peringatan_pegawai`
  (muncul sebagai toast) tanpa memblokir pembuatan BAST; jika terdaftar,
  rekaman diberi tanda `pihak_kedua_terdaftar`.
- **LPB "Diperiksa oleh" dari peran pejabat**: peran baru **"Pemeriksa
  Laporan Penerimaan Barang (LPB)"** di master pejabat; kolom tanda tangan
  pemeriksa pada PDF LPB otomatis terisi nama/NIP/jabatan pejabat periode
  berjalan (`resolve_pejabat_peran`).
- Catatan: usulan *handover massal antar-unit/ruangan* sengaja ditunda —
  mutasi multi-aset per pemegang (PR #350) sudah mencakup kasus umumnya.
- Verifikasi: suite **468 lulus**; smoke FakeDB (validasi pegawai, bukti →
  agenda disahkan, penghitung tenggat wasdal); lint & build frontend sukses.

---

## [#352] Tata letak BAST dirombak: padat, rapi, resmi — 1 halaman bila muat — 2026-07-17

- **Review ulang seluruh 6 jenis BAST** (permintaan pemilik: seringkas
  dan sepadat mungkin, profesional resmi pemerintahan; bila mentok baru
  lanjut halaman kedua):
  - **Identitas PARA PIHAK berdampingan 2 kolom** dalam bingkai tipis
    (dengan keterangan peran "yang menyerahkan/menerima" yang otomatis
    terbalik pada jenis pengembalian) — menghemat ±10 baris vertikal.
  - **Dasar hukum ditinjau & ditata ulang**: 6 butir → 5 butir dengan
    sitasi baku (PMK 76/2019 disatukan sebagai *jo.* PMK 246/2014; PP
    28/2020 disebut sebagai *jo.* PP 27/2014), ditampilkan berukuran
    kecil dan rapat — nomor & judul resmi tetap utuh.
  - **Pasal-pasal diringkas** tanpa mengurangi makna hukum (tanggung
    jawab, mutasi, status/jangka waktu/pengembalian digabung, penutup
    jadi satu paragraf); spacing antarblok dirapatkan.
- Hasil terukur (smoke `PdfReader`): BAST **2 aset = 1 halaman** (semua
  jenis ber-2 tanda tangan); mutasi (3 tanda tangan + KPB) dan BAST
  5 aset = 2 halaman — sesuai ketentuan "lanjut halaman kedua bila
  mentok". Lampiran foto tetap di halaman terpisah bila diaktifkan.
- Verifikasi: suite **468 lulus**; smoke 6 jenis × 2 varian jumlah aset.

---

## [#351] Persediaan masuk massal ber-nomor LPB + unduh Laporan Penerimaan Barang — 2026-07-17

- **Transaksi masuk massal kini menghasilkan LPB** (Laporan Penerimaan
  Barang) — format mengikuti contoh resmi satker (docx pemilik): kop,
  nomor LPB, info 2 kolom (instansi/satker/tgl kedatangan/rekanan ↔
  jenis/no bukti/tautan BAST Pengadaan/keterangan), tabel barang
  (kode/nama/qty/satuan/harga/total/kondisi) + baris JUMLAH, tanda
  tangan **3 kolom**: Dibuat oleh (Pengurus Barang — otomatis dari
  registry pejabat), Diperiksa oleh, Disetujui oleh (KPB).
- **Penomoran langsung tercatat**: centang "Nomor LPB otomatis" → nomor
  terbit dari Registrasi Persuratan (counter atomik + klasifikasi
  otomatis, modul persediaan) dan masuk buku agenda berstatus
  *dibooking*; nomor itu juga menjadi `no_bukti` seluruh transaksi
  barang dalam dokumen tersebut.
- **Register `lpb`** menyimpan snapshot barang per transaksi massal
  (hanya yang sukses); **PDF terunduh otomatis** setelah simpan dan bisa
  dirender ulang kapan pun (`GET /persediaan/lpb/{id}/pdf`; riwayat di
  `GET /persediaan/lpb`).
- Verifikasi: suite **468 lulus**; smoke render LPB (2 barang, total
  Rp12,88 jt, ttd 3 kolom); eslint bersih; build sukses.

---

## [#350] Handover langsung: mutasi pemegang & pengembalian ber-efek data + BAST, booking nomor otomatis — 2026-07-17

- **Jenis BAST baru "Mutasi/Alih Pemegang (Handover)"**: PIHAK KESATU =
  pemegang lama (wajib; prefill dari pemegang yang dibuka), PIHAK KEDUA =
  pemegang baru; naskah ber-pasal mutasi (tanggung jawab beralih sejak
  ttd, pencatatan pemegang diperbarui) dan **tanda tangan 3 pihak** —
  pemegang baru (kiri), pemegang lama (kanan + tempat/tanggal), **KPB
  "Mengetahui" di tengah bawah**.
- **Handover langsung (efek data)** — centang "terapkan ke aset":
  - mutasi → `user`/`pengguna_nip`/`pengguna_jabatan` aset langsung
    berpindah ke pemegang baru;
  - pengembalian → pengguna aset dikosongkan (barang kembali ke satker);
  keduanya ber-audit + `$inc version`; rekap pemegang langsung segar.
- **Booking nomor otomatis**: centang "Pesan nomor otomatis" → nomor BAST
  terbit dari Registrasi Persuratan (counter atomik + klasifikasi
  otomatis) dan tercatat di buku agenda berstatus *dibooking*.
- **Badge riwayat BAST per aset**: subdoc `bast_terakhir` (id, jenis,
  nomor, tanggal, penerima) ditulis ke tiap aset setiap BAST dibuat —
  tampil sebagai badge di daftar aset pemegang (dan tersedia di proyeksi
  list aset).
- Verifikasi: suite **468 lulus**; smoke — mutasi memindahkan pengguna
  (Andi→Citra) + nomor otomatis `B-001/…` + record agenda dibooking +
  PDF 3 ttd; pengembalian mengosongkan pengguna; mutasi tanpa pemegang
  lama ditolak 400.

---

## [#349] Generator BAST serah terima pengguna: multi-aset, 4+1 jenis, lampiran foto opsional — 2026-07-17

- **BAST per pengguna dari modul Penggunaan** (detail pemegang → tombol
  "Buat BAST Serah Terima"): format mengikuti dua contoh resmi satker
  (BAST Rumga & BA Robot Kit) — kop, nomor (bisa dari Booking Nomor),
  narasi tanggal terbilang, identitas PIHAK KESATU (default KPB dari
  pengaturan) & PIHAK KEDUA (prefill dari pemegang), dasar hukum
  (UU 17/2003, PP 27/2014, Perpres 62/2022, PMK 246/2014 jo. 76/2019,
  PMK 53/2023), PASAL 1 + **tabel multi-aset** (kode/NUP/nama/merk/tahun/
  kondisi), pasal-pasal sesuai jenis, penutup, ttd 2 pihak + tempat/
  tanggal, TEMBUSAN — ringkas 1–2 halaman.
- **Jenis serah terima** (kebutuhan lapangan): penggunaan melekat ke
  pengguna, operasional per unit/tempat/tugas (**+ daftar penanggung
  jawab tambahan**), **penggunaan sementara ber-jangka waktu** (pasal
  status aset & pengembalian; jangka wajib), pengembalian (arah balik),
  dan lainnya (judul bebas).
- **Lampiran foto opsional** (setelan `sertakan_foto`): foto sampul tiap
  aset menjadi halaman lampiran "Foto Bukti Serah Terima Barang".
- Register `bast_serah_terima` menyimpan tiap BAST (snapshot identitas
  aset dibekukan; riwayat per aset/pengguna; PDF dirender ulang kapan
  pun); endpoint GET/POST /bast + GET /bast/{id}/pdf + audit.
- Verifikasi: suite **468 lulus**; smoke render 4 jenis BAST (multi-aset)
  + validasi jangka waktu; eslint bersih; build sukses.

---

## [#348] DBHI info 2 kolom, TEMBUSAN smart di BA, Ketua Tim terisi, tombol Booking sebaris LHI — 2026-07-17

- **DBHI (6 jenis)** kini memakai blok info ringkas **2 kolom × 2 baris**
  (Satker|Nomor SK, Kegiatan|Periode) — seragam dengan RHI & DBKP.
- **Bagian TEMBUSAN** pada BAHI & BA Tim Internal (kaidah tata naskah:
  kiri bawah setelah tanda tangan, daftar bernomor, satu tembusan tanpa
  nomor, TIDAK tampil bila kosong). **Input**-nya di **Pengaturan Sampul
  LHI → "Tembusan surat/BA" (satu per baris)** — berlaku global untuk
  semua surat; kegiatan dapat menimpanya (field `tembusan` per kegiatan
  didukung backend).
- **Ketua Tim kini terisi otomatis** di blok ttd BAHI: memakai
  **tim_inti** kegiatan (yang punya penanda Ketua dari form input
  kegiatan); kegiatan lama tanpa tim_inti tetap memakai tim peneliti.
- **Tombol "Booking Nomor" di unduhan laporan inventarisasi** kini satu
  baris dengan "Download LHI Lengkap" (di tengah, sebelum tombol Sampul).
- Verifikasi: suite **468 lulus**; smoke render BAHI+tembusan+tim_inti,
  BA Internal+tembusan, DBHI 2 kolom; helper tembusan kosong/1-baris.

---

## [#347] Referensi Akun BAS satu pintu: master Kodefikasi Segmen Akun (2.899 akun resmi) — 2026-07-17

- **Dua referensi akun disatukan** (permintaan pemilik: "jangan dibagi 2"):
  pill "Referensi Akun Neraca" + "Referensi Akun Persediaan" di Beranda
  Modul diganti SATU pintu **"Referensi Akun BAS"** berisi 3 tab —
  master **Segmen Akun BAS** + aturan pakai **Akun Aset (per Golongan)** +
  **Akun Persediaan** (sub-kelompok → 1171xx).
- **Master baru `referensi_akun`**: **2.899 akun 6 digit** seluruh 8 segmen
  (Aset/Kewajiban/Ekuitas/Pendapatan/Belanja/Transfer/Pembiayaan/
  Non-Anggaran) hasil parse dokumen resmi "Referensi Akun" SAKTI/SPAN
  yang diunggah pemilik; **85 akun belanja diperkaya** metadata
  belanja↔BMN (gol BMN, kapitalisasi, kategori neraca) dari kertas kerja
  Excel satker. Seed otomatis saat pertama; admin bisa muat ulang
  (upsert — entri manual bertanda "satker" tidak hilang), tambah/hapus
  manual (hapus ditolak bila akun dipakai pemetaan).
- **Endpoint**: `GET /referensi-akun` (cari + filter segmen + hitung per
  segmen), `GET /referensi-akun/periksa` (lookup batch), `POST …/seed`,
  `POST`/`DELETE` admin.
- **Pemetaan tervalidasi lunak** ke master: akun pada pemetaan golongan/
  persediaan menampilkan nama resminya, atau tanda "⚠ tak ada di master
  BAS" (non-blocking) — laporan DBKP/Posisi BMN/persediaan tetap memakai
  pemetaan yang sama, tidak ada perubahan angka.
- Verifikasi: suite **468 lulus**; smoke seed 2.899 akun (132111
  Peralatan dan Mesin, 117111 Barang Konsumsi, 521811 ber-metadata
  Aset Lancar), pencarian/filter, periksa batch, guard hapus-terpakai,
  seed ulang idempoten; build sukses.

---

## [#346] Validasi silang lunak Kelola Kategori ↔ Referensi Kodefikasi (1a) — 2026-07-17

- Kelola Kategori dan Referensi Kodefikasi selama ini dua master kode
  barang PARALEL tanpa tautan (temuan arsitektural #28) — opsi **1a**
  (pilihan pemilik): validasi silang LUNAK, tanpa mengubah/menolak data.
- **Endpoint pindai baru** `GET /integritas/kategori-kodefikasi`
  (read-only): kategori ber-kode yang belum terdaftar di kodefikasi —
  hitungan per masalah (golongan tak terdaftar / kode spesifik belum
  terdaftar / panjang tak valid), rincian 300 teratas, daftar kode
  bermasalah untuk penanda UI; kategori tanpa kode = sah (info saja).
- **Register baru di dasbor Integritas** ("Kategori ↔ Kodefikasi") —
  ikut ringkasan gabungan & ekspor CSV integritas.
- **UI Kelola Kategori**: banner jumlah kategori bermasalah + arah
  perbaikan, penanda ⚠ per baris kode yang belum terdaftar, dan toast
  peringatan saat menambah kategori ber-kode tak terdaftar (kategori
  tetap tersimpan — non-blocking, pola §5A Prinsip 2).
- Verifikasi: suite **468 lulus**; smoke 5 kategori (terdaftar penuh /
  induk-saja / golongan asing / panjang salah / tanpa kode) + peringatan
  tambah kategori; build sukses.

---

## [#345] Persuratan: edit surat masuk, anchor nomor eksternal, tombol "Booking Nomor" di 15 halaman — 2026-07-17

- **Surat masuk kini dapat diedit** (tombol pensil di setiap baris masuk):
  nomor surat pengirim, pengirim, perihal, tanggal, modul, keterangan —
  nomor agenda tetap; nomor surat KELUAR tetap tidak pernah bisa diubah
  (milik counter agenda).
- **Field "Nomor Eksternal"** pada surat keluar — anchor **nomor sah dari
  aplikasi pihak ketiga** (Srikandi/e-office instansi) bila penomoran
  resmi bukan dari AMAN: terisi saat booking/edit draf, tampil di tabel
  ("eks: …") dan kolom baru ekspor CSV; surat yang SUDAH DISAHKAN tetap
  bisa diisi nomor eksternal & keterangannya (tombol pensil khusus) —
  field lain tetap terkunci.
- **Tombol "Booking Nomor" tersebar di 15 titik**: halaman unduh laporan
  inventarisasi (Rekapitulasi ▸ unduhan LHI) + header 14 halaman modul
  (Pelaporan, Wasdal, Pemeliharaan, Penggunaan, Pemanfaatan, Pemusnahan,
  Pemindahtanganan, Penghapusan, Pengamanan, Penilaian, Perencanaan,
  Penganggaran, Pengadaan, Persediaan) — komponen `BookingNomorButton`:
  modul/jenis naskah/kegiatan/referensi terisi otomatis dari konteks
  halaman, pratinjau nomor live, hasil booking bisa langsung disalin ke
  field nomor dokumen.
- Verifikasi: suite **468 lulus**; smoke persuratan end-to-end; eslint
  17 file bersih; `yarn build` sukses.

---

## [#344] Naskah BA sesuai kaidah (seluruh tim bertanda tangan), RHI 1 halaman, DBKP ber-nomor SK — 2026-07-17

- **Review naskah kedua Berita Acara** (riset kaidah: BAHI ditandatangani
  minimal 3 anggota tim pelaksana dan disahkan penanggung jawab UAKPB —
  bukan hanya ketua):
  - **BAHI**: blok tanda tangan kini memuat SELURUH anggota Tim Pelaksana
    Inventarisasi (berpasangan per baris; ketua ditandai "Ketua Tim";
    tempat/tanggal di kanan atas) + **Kuasa Pengguna Barang
    "Mengetahui/Mengesahkan" di tengah bawah**; tim pendukung tetap
    tercantum sebagai informasi (bukan penanda tangan). Daftar lama
    "nama (…....)" yang bukan blok ttd resmi dihapus.
  - **BA Tim Internal Penelitian BMN Tidak Ditemukan**: sama — seluruh
    anggota Tim Peneliti bertanda tangan + KPB mengetahui di tengah;
    dulu hanya Ketua Tim.
  - Helper baru `_blok_ttd_tim_kpb()` (dipakai kedua BA; aman untuk tim
    kosong / tanpa penanda ketua).
- **RHI dipadatkan agar muat SATU halaman**: blok info jadi 2 kolom × 2
  baris (Satker|Nomor SK, Kegiatan|Periode — helper
  `_info_kegiatan_2kolom`), spacer tanda tangan 12→6 mm — terverifikasi
  smoke `PdfReader` = 1 halaman.
- **DBKP per Golongan kini menampilkan Nomor SK** (dulu tidak ada) memakai
  blok info 2 kolom yang sama — sekaligus hemat ruang; spacer ttd 12→6 mm.
- Verifikasi: suite **468 lulus**; smoke render RHI (1 halaman), DBKP,
  BAHI & BA Internal dengan tim 3 anggota dan tim kosong.

---

## [#343] Persuratan smart: klasifikasi nomor otomatis, master kode arsip dinamis, pratinjau nomor live — 2026-07-17

- **Master Kode Klasifikasi Arsip** dikelola dinamis (admin, dialog
  "Format Nomor"): tambah/hapus kode + uraian sesuai pedoman klasifikasi
  arsip instansi; kode yang dipakai aturan pemetaan tak bisa dihapus
  (409). Menjadi pilihan (datalist) di form booking.
- **Aturan klasifikasi otomatis**: pemetaan `modul` + `jenis naskah` →
  kode klasifikasi (field kosong = wildcard; aturan paling SPESIFIK
  menang; kode manual di form selalu menang; fallback kode bawaan).
  Saat booking, nomor surat langsung terklasifikasi benar tanpa
  mengetik kode — mis. semua "Berita Acara" → HK.xx, laporan modul
  Pelaporan → PL.xx.
- **Pratinjau nomor live** di dialog booking: perkiraan nomor yang akan
  terbit (urut berikutnya + klasifikasi terpilih + sumbernya:
  manual/pemetaan/bawaan) diperbarui setiap field penentu berubah —
  counter TIDAK naik saat pratinjau; keunikan tetap dijamin counter
  atomik saat booking sesungguhnya.
- Teknis: `pilih_klasifikasi()` + `validate_peta_klasifikasi()` murni
  (+7 uji unit → suite **468**); endpoint klasifikasi CRUD +
  `/persuratan/pratinjau-nomor`; smoke end-to-end (pratinjau = nomor
  booking; aturan spesifik menang; duplikat kode ditolak; hapus kode
  terpakai ditolak).

---

## [#342] LHI Lengkap +DBKP, identitas kegiatan di surat, dokumen pendukung dirapikan — 2026-07-17

- **DBKP per Golongan Barang kini masuk paket unduhan "LHI Lengkap"**
  (urutan: Sampul → BAHI → RHI → 6 DBHI → **DBKP** → SP Hasil → SP
  Pelaksanaan) dan tercantum pada daftar lampiran di BAHI.
- **Nama kegiatan kini tampil di surat-surat LHI** — dulu hanya Nomor SK:
  DBHI (6 jenis) & RHI mendapat baris "Kegiatan: …"; kalimat BAHI, SP
  Hasil, dan SP Pelaksanaan menyebut nama kegiatan + nomor SK sekaligus.
- **Dokumen Pendukung Lainnya dirapikan**:
  - *BA Tim Internal Penelitian BMN Tidak Ditemukan*: nomor BA kini
    terbaca dari field kegiatan (fallback titik-titik, tak lagi "-");
    kalimat pembuka memakai narasi tanggal terbilang; blok tanda tangan
    Tim Peneliti (kanan) kini ber-baris tempat/tanggal.
  - *SPTJM* & *Surat Koreksi*: "Dibuat di" memakai Tempat Laporan
    pengaturan (fallback alamat kop) dan "Pada tanggal" berformat
    Indonesia (dulu tanggal ISO mentah).
- **Posisi penanda tangan diaudit sesuai kaidah tata naskah**: pembuat
  dokumen selalu di KANAN dengan baris tempat/tanggal di atasnya,
  "Mengetahui" di kiri — BAHI/KIR/BA sudah sesuai; satu-satunya
  penyimpangan (BA Tim Internal tanpa tempat/tanggal) diperbaiki.
- Verifikasi: suite **461 lulus**; smoke render 10 dokumen (DBHI, BAHI,
  SP Hasil, SP Pelaksanaan, Sampul, BA Tidak Ditemukan, SPTJM, Surat
  Koreksi, DBKP) + cek paket LHI memuat DBKP.

---

## [#341] Modul Persuratan: buku agenda & booking nomor naskah dinas lintas modul — 2026-07-17

- **Registrasi Persuratan** baru (tombol di seksi Penatausahaan, Beranda
  Modul) — mengakomodir SEMUA jenis laporan/naskah dari modul dan
  kegiatan mana pun, mengikuti **PerANRI 5/2021** (pustaka §11A, hasil
  riset internet + sumber tercantum):
  - **Booking nomor surat keluar**: nomor terbit ATOMIK per tahun takwim
    saat draf dibuat (dua pengguna tak pernah dapat nomor sama), berstatus
    `dibooking` → **disahkan** setelah surat ditandatangani, atau
    **dibatalkan** (wajib alasan; nomor HANGUS — tidak didaur ulang,
    tetap tercatat agar urutan agenda utuh dan celah nomor dapat
    dipertanggungjawabkan saat audit).
  - **Susunan nomor sesuai PerANRI 5/2021**: kode keamanan (B/T/R/SR) +
    nomor urut + kode klasifikasi arsip + bulan Romawi + tahun — format
    **konfigurabel ber-placeholder** (admin), contoh
    `B-015/PL.02/OIKN/VII/2026`.
  - **Agenda surat masuk** (buku agenda kembar): nomor agenda sendiri per
    tahun; status diterima → diproses → selesai.
  - Tiap surat menautkan **jenis naskah** (BA/Laporan/SP/SK/…), **modul
    asal**, **kegiatan**, dan **referensi laporan** (mis. "BAHI", "LBKP
    S1") — buku agenda satu pintu lintas modul; surat keluar yang sudah
    disahkan terkunci (hanya keterangan yang bisa diubah).
  - Ekspor **buku agenda CSV**; ringkasan dibooking/disahkan/dibatalkan/
    masuk-terbuka; audit trail booking/pengesahan/pembatalan.
- Teknis: `persuratan_utils.py` murni (**13 uji unit**: perakitan nomor,
  validasi, transisi status, baris agenda); counter `db.counters` atomik
  (pola tiket kegiatan); smoke end-to-end (booking → sahkan → batal →
  masuk → ekspor; nomor batal terbukti tidak dipakai ulang).
- Verifikasi: suite **461 lulus** (+13); eslint bersih; build sukses.

---

## [#340] Tanggal laporan: DBHI ber-rentang periode, tempat/tanggal di Sampul LHI, narasi tanggal BAHI terisi — 2026-07-17

- **DBHI (6 jenis: Kondisi Baik/Rusak Ringan/Rusak Berat, Berlebih, Tidak
  Ditemukan, Dalam Sengketa)**: baris info kini menampilkan **"Periode
  Inventarisasi: [mulai] s.d. [selesai]"** — bukan lagi tanggal tunggal
  (DBHI memotret hasil sepanjang periode pelaksanaan).
- **Pengaturan Sampul LHI** bertambah **Tempat Laporan** (kota) dan
  **Tanggal Laporan**: tampil di sampul LHI dan otomatis mengisi baris
  "tempat, tanggal" pada kaki SEMUA surat laporan (BAHI, SP Hasil, SP
  Pelaksanaan, DBHI, RHI, DBKP, Posisi BMN, DBR, KIR, LBKP, LKB, CaLBMN,
  penyusutan — 13 titik). Laporan periodik memakai tanggal periodenya
  sendiri (LBKP/CaLBMN = akhir periode); yang belum diisi tetap
  titik-titik untuk ditulis tangan.
- **BAHI**: kalimat pembuka "Pada hari ini, …, tanggal … bulan … tahun …"
  kini **terisi otomatis** dari Tanggal Berita Acara kegiatan (fallback
  Tanggal Laporan pengaturan) dalam bentuk terbilang naskah dinas —
  "Pada hari ini, Jumat, tanggal Tujuh Belas bulan Juli tahun Dua Ribu
  Dua Puluh Enam (17 Juli 2026)"; nomor BA memakai field
  `nomor_berita_acara` kegiatan yang selama ini tak terbaca laporan.
- Helper murni baru `terbilang_id()` & `narasi_hari_tanggal()`
  (pelaporan_utils, +4 uji unit; kebal placeholder 9999-12-31).
- Verifikasi: suite **448 lulus** (+4); smoke render DBHI/BAHI/SP
  Hasil/Sampul LHI + asersi teks helper; eslint bersih; build sukses.

---

## [#339] Sinkronisasi SIMAN V2: impor ekspor Master Aset + tanda "≠ SIMAN" per aset — 2026-07-17

- **Kanal pembaruan berkala dari SIMAN V2** (SIMAN = data valid; API belum
  tersedia untuk satker → impor manual hasil ekspor sebagai "API semu"):
  unggah XLSX "Master Aset" (±78 kolom) di **Pelaporan › Sinkronisasi
  SIMAN V2** → tiap baris dicocokkan ke aset AMAN → perbedaan tercatat per
  aset → tinjau & **terapkan nilai SIMAN** per aset (ber-audit).
- **Pencocokan dua lapis**: `Kode Register` SIMAN (ID stabil, tahan
  reklasifikasi) lalu Kode Barang+NUP; aset AMAN yang belum punya
  `kode_register` **mengadopsinya otomatis** saat impor.
- **Field dibanding** (normalisasi kode/angka/tanggal/teks): kode barang
  (deteksi reklasifikasi), uraian kode, merk, tipe, kondisi, nilai
  perolehan, tanggal perolehan, nama pengguna, kode register. **Referensi
  SIMAN tersimpan per aset** tanpa dibanding: nilai penyusutan, nilai buku,
  umur aset, status penggunaan/PSP, intra/ekstra.
- **Tanda di halaman aset**: badge "≠ SIMAN" pada kartu galeri, tabel
  desktop, kartu mobile (ikut snapshot offline), + banner rincian selisih
  (nilai AMAN ⟶ SIMAN) di form edit aset; opsi menandai aset yang tidak
  ada di file (khusus ekspor penuh satker) → banner "tidak ditemukan di
  SIMAN".
- Riwayat impor tersimpan (`siman_imports`) berikut daftar baris SIMAN yang
  belum tercatat di AMAN (bahan tindak lanjut lewat impor aset/Pengadaan).
- Teknis: `siman_utils.py` murni (16 uji unit); jebakan nyata tertangani —
  tanggal placeholder `9999-12-31` tanpa `strptime`, dimensi sheet ekspor
  SIMAN yang salah (`reset_dimensions()`), NUP/kode bergaya float Excel;
  smoke end-to-end memakai **file ekspor SIMAN asli** (165 baris).
- Verifikasi: suite **444 lulus** (+16); eslint bersih; `yarn build` sukses.

---

## [#338] Review batch 10 (final): LBKP tanpa tebakan seksi, sapu bersih API legacy & penanda basi — 2026-07-16

- **#63 — LBKP/CaLBMN: mutasi kurang tanpa nilai tak lagi ditebak Ekstra**:
  nilai 0 selalu terklasifikasi "ekstra" padahal aset semasa hidup bisa intra
  → kini kurang yang kelasnya tak dapat dipastikan dicatat di seksi **Gabungan
  saja** (diungkap di catatan laporan; Gabungan bisa ≠ I+II). Tombstone
  penghapusan via SK kini merekam `kelas_komptabel` semasa hidup sehingga
  kurangnya selalu jatuh di seksi yang sama dengan saldo awalnya. +2 uji unit.
- **#59/#69 — API legacy tanpa konsumen dihapus** (cegah drift permukaan
  ganda): `GET /backup/create` (backup sinkron **blocking**), `POST
  /backup/restore` (restore sinkron destruktif), `POST /categories/import`,
  `GET /pemeliharaan/aset/{id}`, `GET /kodefikasi/golongan`. Dipertahankan
  karena masih ada pemakainya: `GET /backup/stats`, `GET /backup/progress/
  {job_id}`, `GET /categories` paginasi (uji integrasi). Suite integrasi
  backup dimigrasikan ke alur background.
- **#57 (lanjutan #66) — dicatat**: stream `doc-file` memang sengaja publik
  (keputusan terdokumentasi di kode: tautan pada ekspor CSV/XLSX dibuka dari
  spreadsheet tanpa token; dikeraskan Content-Type tetap + nosniff) — temuan
  #66 kedaluwarsa, tidak diubah.
- **#62/#64/#65 — penanda "menyusul" basi disapu** (semua klaim diverifikasi
  ke kode dulu): registry `bmnModules` (draft aset dari perolehan ✅, aset
  keluar daftar aktif setelah PT selesai ✅, register usulan RKBMN ✅), footer
  PelaporanPage (LBKP & rekonsiliasi sudah di halaman itu), 8 docstring modul
  backend + 9 header halaman frontend kini menyatakan fitur yang benar-benar
  ada (SBSK & formulir PMK 207 tetap ditandai menyusul — memang belum ada).
- **#67 — jalur sync offline mati dibuang**: `useOfflineSync` kini murni
  deteksi online/offline; antrean IDB lama (kebijakan konflik berbeda dari
  `useOptimisticQueue` yang asli) dihapus + database IDB usangnya dibersihkan
  best-effort agar op basi tak pernah tereksekusi.
- **#68 — rekap pegawai per unit kerja tampil**: kartu chip unit (jumlah
  pegawai per unit, klik = filter) di Master Pegawai dari endpoint
  `/pegawai/rekap-unit` yang selama ini tak terpakai.
- Verifikasi: suite **428 lulus** (+2); eslint bersih; `yarn build` sukses.

---

## [#337] Review batch 9: guard hapus master, kop CaLBMN, tahun perolehan & polesan UI — 2026-07-16

- **#34 — Master tidak bisa dihapus selagi masih dipakai aset**: hapus
  **pegawai** (NIP tercatat sebagai pengguna), **kategori** (label dipakai
  `category`), dan **ruangan** (label lokasi cocok) kini ditolak `409` dengan
  jumlah aset terdampak + saran (pindahkan aset / nonaktifkan pegawai) — dulu
  referensi bisa lenyap diam-diam meninggalkan aset yatim.
- **#36 — Daftar pemegang (Penggunaan) diperkaya master pegawai**: tiap baris
  membawa `pegawai_master_nama`, `pegawai_master_unit`, `pegawai_terdaftar`
  (satu query ber-key NIP per halaman) — pemegang yang NIP-nya tak terdaftar
  kini kelihatan.
- **#40 — Kop CaLBMN memakai identitas satker nyata** dari pengaturan laporan
  (`nama_sub_unit` → `nama_unit_organisasi` → `nama_instansi`), bukan teks baku.
- **#43 — Tahun perolehan tahan berbagai format tanggal**: helper
  `_tahun_perolehan()` (ISO, `DD-MM-YYYY`, `DD/MM/YYYY`, teks ber-tahun) dipakai
  di 3 titik laporan — dulu `[:4]` mentah menghasilkan "31/1" sebagai "tahun".
- **#57 — Panel Riwayat (audit log)**: gagal fetch kini menampilkan "Gagal
  memuat riwayat" + tombol **Coba lagi** — dulu diam-diam tampil "Belum ada
  riwayat" yang menyesatkan.
- **#58 — Pilihan Penanggung Jawab Ruangan** disaring seperti backend
  (`_berlaku_pada`): hanya pejabat aktif yang rentang berlakunya mencakup hari
  ini; nilai lama yang sudah tidak berlaku ditandai "(kedaluwarsa)".
- Verifikasi: suite **426 lulus**; smoke `_tahun_perolehan` 6 format; eslint
  bersih; `yarn build` sukses.

---

## [#336] Review batch 8: wasdal lintas modul & serapan anggaran dari Pengadaan — 2026-07-16

- **#12 — Dasbor Wasdal kini membaca register Pengamanan & Penggunaan**:
  respons `/wasdal/pemantauan` diperkaya blok `lintas_modul` (kasus pengamanan
  belum selesai, polis asuransi tercatat, SK PSP, tiket alih status/penggunaan
  aktif, tiket BMN idle aktif) + label — additif, UI lama tetap jalan.
- **#13 — Serapan Penganggaran menarik data nyata dari Pengadaan**: tiap usulan
  di `/penganggaran` kini membawa `realisasi_pengadaan` (total nilai perolehan
  Pengadaan yang bertaut `penganggaran_id`) + `total_realisasi_pengadaan` —
  pembanding objektif terhadap `nilai_realisasi` manual; field lama tidak diubah.
- Verifikasi: suite **426 lulus**; smoke — serapan 2 perolehan tertaut = 250
  (perolehan tanpa tautan diabaikan); lintas_modul menghitung 5 register benar.

---

## [#335] Review batch 7: tanggal laporan persediaan memakai WIB (UTC+7) — 2026-07-16

- **Temuan #25/#44**: seluruh derivasi TANGGAL di modul persediaan dulu memakai
  UTC — transaksi/opname yang direkam **pagi atau dini hari WIB** tercatat pada
  **tanggal sebelumnya** di BAOF, laporan mutasi, peringatan kedaluwarsa, status
  opname semesteran, dan Kartu Barang.
- Helper murni baru `tanggal_wib(ts_iso)` & `today_wib()` (`persediaan_utils`,
  tanpa dependency baru): timestamp **tetap disimpan UTC** — WIB hanya untuk
  derivasi tanggal (filter/label). Diterapkan di `mutasi_periode`, filter BAOF,
  status opname, label Kartu Barang, dan 4 titik "hari ini" (peringatan/kertas
  kerja/posisi/status).
- Uji unit boundary (18:30Z → esok WIB; 16:59Z → hari sama; naive = UTC;
  mutasi 30 Jun 17:30Z masuk periode Juli) → suite **426 lulus**; smoke render
  posisi + kertas kerja OK.

---

## [#334] Review batch 6: integritas data (wajib-pegawai menyeluruh & guard usulan PT) — 2026-07-16

- **#29 — Setelan "wajib pegawai terdaftar" tak bisa ditembus lagi**: penegakan
  dipindah ke `shared_utils.enforce_pegawai_terdaftar` dan kini berlaku di
  SEMUA jalur tulis `pengguna_nip` — create/PUT/PATCH aset, **ubah massal**
  (`batch-update`), dan **impor XLSX** (set NIP dimuat sekali; baris melanggar
  dilewati sebagai error baris `"<kode> NUP <n>: NIP ... belum terdaftar"`,
  bukan menolak seluruh file). Default tetap OFF.
- **#9 — Guard usulan pemindahtanganan**: `buat_usulan_pt` kini menolak aset
  yang **sudah dihapus dari pembukuan** (400) dan aset yang **masih punya
  usulan PT aktif** (409, menyebut bentuk+status usulan) — mencegah usulan
  ganda/atas aset yang sudah keluar. (Cek "sedang dimanfaatkan" ditunda —
  perlu definisi lintas register pemanfaatan.)
- Verifikasi: suite **423 lulus**; smoke — enforcement ON+NIP asing → 400;
  PT aset dihapus → 400; usulan ganda → 409; aset bersih → usulan dibuat.

---

## [#333] Review batch 5: polesan UI Persediaan (banner, massal, riwayat, kertas kerja) — 2026-07-16

- **#20 — Banner selalu segar**: setelah transaksi masuk/keluar/opname/massal
  sukses, banner peringatan stok & status opname semesteran di-refresh otomatis
  (`refreshRingkasan`).
- **#23 + tindak lanjut #17 — dialog massal lengkap**: input **Tgl Dokumen**,
  **kedaluwarsa per baris barang**, dan pemilih **Perolehan (Pengadaan)**
  (mengirim `perolehan_id` → semua jurnal baris ber-snapshot BAST, pasangan #332).
- **#24 — Riwayat "Muat lebih"**: dialog riwayat tak lagi terpotong 50 baris —
  tombol memuat halaman berikutnya (paginasi backend yang sudah ada).
- **Tindak lanjut #22**: unduh kertas kerja opname menyertakan **filter gudang
  aktif** (`?gudang=`).
- **#49 — teks basi diperbaiki**: header tak lagi bilang "transaksi masuk/keluar
  menyusul". `eslint --max-warnings=0` bersih, `yarn build` sukses.

---

## [#332] Review batch 4: integrasi Pengadaan–Persediaan & laporan persediaan — 2026-07-16

- **#11 — Hapus perolehan tak lagi meninggalkan back-link menggantung**: sebelum
  register perolehan dihapus, `perolehan_id`/snapshot pada aset tertaut dilepas
  (`_lepas_perolehan_dari_aset` per baris barang).
- **#17 — Transaksi massal bisa bertaut BAST Pengadaan**: payload massal kini
  menerima `perolehan_id` (divalidasi **sekali di muka** — 404 sebelum mutasi
  stok mana pun), diteruskan ke tiap transaksi masuk sehingga **semua jurnal
  baris membawa snapshot dokumen sumber** (pola transaksi tunggal).
- **#21 — Laporan Mutasi tanpa baris serba-nol**: barang yang seluruh
  aktivitasnya di luar periode (saldo & mutasi nol) tidak lagi dimunculkan
  (`mutasi_periode`, + uji unit; saldo-awal-tanpa-mutasi tetap tampil).
- **#22 — Kertas kerja opname per Lokasi/Gudang**: `GET
  /persediaan/opname/kertas-kerja-pdf?gudang=` memfilter satu gudang + subjudul
  lokasi — opname fisik per gudang.
- **#31 dilewati dengan alasan**: kategori aset bersumber master `categories`;
  menyuntik uraian kodefikasi sebagai kategori akan menciptakan nilai kategori
  liar di filter/laporan (dicatat di backlog).
- Verifikasi: suite **423 lulus** (+1 uji mutasi); smoke — kertas kerja per
  gudang render, massal ber-`perolehan_id` (2 jurnal ber-snapshot; id salah →
  404 sebelum mutasi), hapus perolehan melepas back-link aset.

---

## [#331] Review batch 3: tanda tangan seluruh dokumen dari registry Pejabat — 2026-07-16

- **Satu resolver tanda tangan lintas modul** (temuan #26): 6 blok "Kuasa
  Pengguna Barang" yang masih membaca setelan kasatker langsung — DHPB
  Pemeliharaan, BA Pemusnahan, BAST PSP & Daftar Barang Digunakan (Penggunaan),
  BA Pemantauan & Laporan Wasdal — kini memakai **KPB aktif dari registry
  pejabat** via `shared_utils.resolve_penandatangan_kpb` + helper blok siap-pakai
  (`blok_ttd_kpb`, `blok_ttd_kpb_titik`), fallback setelan/garis-titik seperti
  sebelumnya.
- **Rentang berlaku SK pejabat kini dicek** (temuan #41): resolver ber-default
  tanggal HARI INI — pejabat kedaluwarsa tak lagi bisa terpilih (dulu
  `_kpb_signer` persediaan dipanggil tanpa tanggal). `_kpb_signer` kini delegasi
  ke resolver bersama.
- **Kartu Barang Persediaan** (temuan #27): blok "Pengurus Barang Persediaan"
  tidak lagi diisi nama Kepala Satker — kini **pejabat berperan
  `pengurus_barang`** dari registry, fallback garis-titik (tanpa fabrikasi).
- Verifikasi: suite **422 lulus**; smoke — KPB kedaluwarsa tersaring, blok
  helper benar, fallback setelan/titik benar, resolver pengurus_barang benar,
  PDF Posisi Persediaan render via resolver bersama.

---

## [#330] Review batch 2: alih status keluar & BMN idle diserahkan keluar dari pembukuan — 2026-07-16

- **Menutup handoff Penggunaan → Pembukuan yang putus** (temuan review #1,
  prioritas tinggi): tiket **alih status arah KELUAR** yang mencapai status
  terminal **"dihapus & dibukukan pengguna baru"**, dan tiket **BMN idle** yang
  mencapai **"diserahkan ke Pengelola"**, kini **memproyeksikan master aset**
  (`dihapus=True` + subdoc `penghapusan` berisi jalur/tiket/dokumen) — pola yang
  sama dengan penghapusan SK (#234) & pemindahtanganan (#256).
- Efek: aset yang sudah beralih/diserahkan **tidak lagi terhitung** di DBKP,
  LKB, Posisi BMN Neraca, penyusutan, dan rekonsiliasi; LBKP/CaLBMN otomatis
  mencatat **mutasi KURANG** pada periode dokumen (via `tombstones_penghapusan`).
  Arah MASUK tidak diproyeksikan; proyeksi hanya aset yang belum dihapus,
  `$inc version` (OCC/cache), audit per aset, best-effort.
- Builder murni `build_asset_alih_keluar_projection` /
  `build_asset_idle_serah_projection` (`penggunaan_utils.py`) + 5 uji unit →
  suite **422 lulus**; smoke FakeDB: keluar → 2 aset ter-flag ber-SK, masuk →
  tidak, idle → aset tunggal ter-flag ber-BAST serah.

---

## [#329] Review menyeluruh batch 1: keamanan endpoint + LKB kecualikan aset terhapus — 2026-07-16

Hasil **review menyeluruh multi-agen** (70 temuan, 69 terverifikasi adversarial;
backlog di sesi pengembangan). Batch 1 = temuan prioritas TINGGI usaha kecil:

- **Keamanan — `GET /users` bocor tanpa autentikasi**: cek admin dulu hanya
  berjalan bila param `admin_id` dikirim; tanpa param, daftar user (nama, email,
  role, status online) terbuka anonim. Kini **`require_admin` via JWT**
  (param lama dipertahankan untuk kompatibilitas).
- **Keamanan — tulis master Kategori tanpa autentikasi**: `POST /categories` &
  `DELETE /categories/{id}` kini **wajib login** (`require_user`, sesuai UI yang
  memang untuk semua user); `DELETE /categories-all` (hapus SEMUA kategori —
  destruktif) kini **khusus admin**. Sebelumnya siapa pun tanpa login bisa
  mengosongkan master rujukan impor/validasi/pengadaan/laporan.
- **Akurasi — LKB (Laporan Kondisi Barang) lebih saji**: query aset LKB tanpa
  `active_asset_filter()` sehingga aset ber-SK penghapusan tetap terhitung di
  rekap kondisi & total nilai (tak pernah rekon dgn DBKP/Posisi Neraca). Kini
  difilter selaras laporan posisi lainnya.
- Verifikasi: `pytest tests/unit` **417 lulus**; smoke-render LKB (FakeDB) —
  PDF valid, aset `dihapus` tereksklusi. UI aman: interceptor axios global
  sudah memasang `Authorization` di semua request.

---

## [#328] Pengadaan: buat draft aset dari perolehan (evaluasi #5) — 2026-07-16

- **Menutup rantai perolehan → penatausahaan.** Tombol **"Buat Draft Aset"** pada
  register perolehan (muncul bila ada barang belum bertaut): pilih **kegiatan
  inventarisasi tujuan** → tiap baris `barang[]` tanpa `asset_id` dibuatkan
  **aset draft** (status "Belum Diinventarisasi") lalu **tertaut balik** +
  proyeksi dokumen sumber (`perolehan_id`/BAST).
- Draft memakai **jalur create aset yang ada**: helper baru `buat_aset_draft`
  (`routes/assets.py`, bentuk dokumen photoless identik `create_asset`) —
  registry `AssetCreate`, keunikan kode+NUP per kegiatan, kunci kegiatan
  disahkan, validasi pegawai opt-in, audit & notifikasi tetap berlaku.
  **NUP dinomori otomatis** melanjutkan max per (kode, kegiatan); kategori
  dicocokkan dari `kode_aset`; harga = harga satuan; tanggal = tanggal BAST;
  jumlah BAST > 1 dicatat di catatan. Baris tanpa kode barang **dilewati**.
- Endpoint `POST /pengadaan/{id}/buat-draft-aset` + dialog UI di
  `PengadaanPage.jsx`. Smoke-test end-to-end (FakeDB): draft dibuat NUP lanjut,
  tertaut balik, baris tertaut/tanpa-kode dilewati, panggilan ulang aman.
  `pytest` **417 lulus**, `eslint` bersih, `yarn build` sukses.

---

## [#327] Evaluasi: status perbaikan rekomendasi #1–#5 — 2026-07-16

- `docs/EVALUASI-FITUR-INTEGRASI.md` §7: tabel status perbaikan — **#1 Selesai**
  (#319), **#2 Selesai** (#320), **#3 Selesai** (#321/#322/#323, koreksi 117131=
  Bahan Baku; 117112/117128 masih perlu verifikasi), **#4 Selesai opt-in** (#324,
  `ruangan_id` FK ditunda), **#5 Menunggu keputusan lingkup** (auto-draft aset dari
  Pengadaan). Plus catatan 3 bug UI daftar aset (#325).

---

## [#326] Perbaikan 3 bug UI daftar aset (filter skeleton, gap baris, identitas pesan gagal) — 2026-07-16

- **(A) Filter Nama Pengguna kini merefresh + skeleton.** Effect refetch daftar aset
  tak menyertakan `filters.user`/`filters.penggunaNip` di dependency array →
  filter pengguna tak memicu muat ulang server-side maupun skeleton. Ditambahkan
  ke deps (`DashboardPage.jsx`).
- **(B) Gap antar-baris pasca-filter hilang.** Daftar kartu mobile (virtualized,
  `@tanstack/react-virtual`) menyimpan tinggi baris terukur per-indeks tanpa reset
  saat data berubah → tinggi baris lama "tertukar" (gap row 1↔2). Ditambah
  `getItemKey` (kunci ke `asset.id`) + `virtualizer.measure()` on `assets` change
  (`VirtualizedMobileCards.jsx`).
- **(C) Pesan gagal kini menyebut identitas aset.** Pesan "Gagal simpan / coba lagi"
  kini berformat **`[Kode <asset_code> · NUP <nup> · Keg. <nama kegiatan>] <error>`**
  — mudah dicari di antara puluhan ribu aset & banyak kegiatan. `nama_kegiatan`
  di-stamp ke item antrean saat enqueue (bukan payload; tak dikirim ke server)
  (`useOptimisticQueue.js` + `DashboardPage.jsx`).
- `eslint` (0 error) & `yarn build` sukses.

---

## [#325] Opsi wajib pegawai terdaftar untuk pengguna aset (evaluasi #4) — 2026-07-16

- **Memperkuat tautan pengguna↔Master Pegawai (OPT-IN).** Setelan laporan baru
  `wajib_pegawai_terdaftar` (**default OFF**). Bila **ON**, menyimpan aset (create/
  update PUT/patch) dengan `pengguna_nip` yang **belum terdaftar di Master Pegawai**
  ditolak **400** dengan pesan jelas (menyebut NIP). Bila **OFF** atau `pengguna_nip`
  kosong → perilaku sekarang (entri lapangan/offline & data lama tetap jalan).
- Helper `_enforce_pegawai_terdaftar` dipanggil di **ketiga jalur tulis** aset
  (POST/PUT/PATCH) — konsisten. Flag disimpan lewat `PUT /report-settings` yang ada.
- `pytest tests/unit` **417 lulus**; smoke-test helper (OFF→lolos, ON+kosong→lolos,
  ON+terdaftar→lolos, ON+tak terdaftar→400).
- **Ditunda (dicatat):** `ruangan_id` FK penuh per aset (arsitektural — menyentuh
  registry field aset & anti-drift); tetap tautan teks/datalist untuk saat ini.

---

## [#324] Verifikasi akun neraca persediaan 1171xx + koreksi (evaluasi #3c) — 2026-07-16

- **Riset verifikasi** akun 1171xx dari **laporan neraca/BMN audited berbagai K/L**
  (sumber sekunder resmi). **Terkonfirmasi konsisten:** 117111 Barang Konsumsi,
  117113 Bahan untuk Pemeliharaan, 117114 Suku Cadang, **117131 Bahan Baku**,
  117199 Persediaan Lainnya.
- **KOREKSI akurasi:** `117131` sebelumnya keliru diberi label **"untuk Diserahkan
  kpd Masyarakat"** — sebenarnya **Bahan Baku**; kode tebakan awal `117191`
  (Bahan Baku) **dihapus**. Ditambah `117128` (untuk Diserahkan, seri 11712x)
  bertanda [perlu verifikasi].
- **Masih perlu verifikasi Lampiran BAS/KEP-211:** `117112` Amunisi & `117128`
  (untuk Diserahkan) — sumber primer `.go.id` (KEP-211, neraca K/L) **terblokir
  proxy**, jadi tidak ditebak. Katalog kini menandai yang belum terverifikasi.
- Diperbarui `persediaan_akun_utils.py` (docstring + `AKUN_PERSEDIAAN_DEFAULT`) &
  pustaka §3.4. `pytest tests/unit` **417 lulus**.

---

## [#323] UI Referensi Akun Persediaan (evaluasi #3b) — 2026-07-16

- **Halaman "Referensi Akun Persediaan"** (`PersediaanAkunPage.jsx`) dari Beranda
  Modul: katalog akun 1171xx (referensi), daftar **pemetaan sub-kelompok → akun**
  (override satker), dengan admin **tambah/ubah/hapus** (POST/DELETE
  `/persediaan-akun`). Sub-kelompok difilter 5-digit '1'; akun dipilih dari katalog.
- Banner menegaskan default 117111 & sub-akun lain **perlu verifikasi Lampiran BAS**.
  Wiring `App.js` + `ModuleHomePage.jsx` (tombol "Referensi Akun Persediaan").
  `eslint` bersih, `yarn build` sukses. Melengkapi #3a (backend).

---

## [#322] Kelola Referensi Akun Persediaan (sub-kelompok → 1171xx) — evaluasi #3a — 2026-07-16

- **Endpoint kelola akun persediaan** (`routes/persediaan_akun.py`, terdaftar di
  `server.py`): `GET /persediaan-akun` (katalog akun 1171xx + daftar override
  sub-kelompok satker + default 117111), `POST /persediaan-akun` (admin:
  sub-kelompok 5-digit '1' → akun, `validate_akun_persediaan`), `DELETE
  /persediaan-akun/{sub_kelompok}` (kembali ke default).
- Memungkinkan satker **memasukkan kode akun 1171xx terverifikasi** per
  sub-kelompok (dipakai laporan Posisi Persediaan). Sebelumnya `db.persediaan_akun`
  hanya bisa lewat DB manual. `py_compile` bersih, suite **417 lulus**, endpoint
  di-smoke-test (GET/POST/DELETE + validasi tolak sub/akun salah).
- Menyusul: UI "Referensi Akun Persediaan" (#3b) + riset verifikasi akun (#3c).

---

## [#321] Akun persediaan golongan-1 satu sumber dari akun_bas (evaluasi #2) — 2026-07-16

- **Menutup temuan evaluasi #2** (dua sistem akun paralel): `AKUN_PERSEDIAAN_UTAMA`
  (`persediaan_akun_utils.py`) tak lagi hardcode `"117111"` melainkan **diturunkan
  dari `akun_bas_utils.AKUN_NERACA_DEFAULT["1"]`** — satu sumber kebenaran akun
  golongan Persediaan, tak bisa drift bila akun_bas diubah.
- Uji unit ditambah (`AKUN_PERSEDIAAN_UTAMA == AKUN_NERACA_DEFAULT["1"]["akun"]`)
  → `pytest tests/unit` **417 lulus**. Tanpa perubahan perilaku (nilai tetap 117111).

---

## [#320] Persediaan: PDF pakai penanda tangan KPB dari registry Pejabat (evaluasi #1) — 2026-07-16

- **Menutup temuan evaluasi #1/#4** (inkonsistensi penanda tangan): seluruh PDF
  Persediaan (Nota Dinas, BAOF opname, Laporan Posisi, Laporan Mutasi) kini
  memakai **Kuasa Pengguna Barang aktif dari registry `pejabat`** (helper
  `_kpb_signer` → `pejabat_utils.penandatangan_kpb`), **fallback ke setelan
  kasatker** bila registry kosong — konsisten dengan laporan satker-level
  (`_penandatangan_kpb`). Sebelumnya membaca `settings.kasatker_*` langsung
  sehingga KPB dari registry tak muncul.
- BAOF mempertahankan garis-titik bila belum ada KPB. Kartu Barang (peran
  "Pengurus Barang Persediaan") tak diubah — peran berbeda.
- Verifikasi: `pytest tests/unit` **416 lulus**; smoke-render PDF Posisi
  (FakeDB) → KPB dari registry muncul (bukan setelan), fallback terjaga.

---

## [#319] Dokumen evaluasi menyeluruh fitur & integrasi — 2026-07-16

- **`docs/EVALUASI-FITUR-INTEGRASI.md`** — evaluasi keseluruhan aplikasi &
  keterhubungan antar-modul (berbasis telaah kode): peta modul + status, matriks
  integrasi (apa baca/tulis dari mana), temuan gap/inkonsistensi, rekomendasi
  prioritas (tinggi/sedang/rendah), & daftar item yang perlu verifikasi
  pemilik/regulasi. Netral & ber-referensi `file:baris`.
- Temuan utama: integrasi terkuat = Pengadaan→Persediaan (FK tervalidasi) &
  backup dinamis (semua koleksi); yang longgar = tautan aset↔master
  (kodefikasi/pegawai/ruangan) berbasis teks/NIP + peringatan lunak (sengaja,
  demi offline-first). Prioritas: samakan penanda tangan persediaan dgn registry
  pejabat, satukan sumber akun, verifikasi akun BAS, perkuat tautan pengguna↔pegawai.

---

## [#318] Form aset: pengguna terhubung ke Master Pegawai — 2026-07-16

- **Pemilih pegawai** pada field Pengguna di form aset (`AssetForm.jsx`). Tombol
  **Pegawai** membuka dropdown pencarian **Master Pegawai** (`GET /pegawai`,
  filter nama/NIP); memilih satu **mengisi nama pengguna (`user`) + `pengguna_nip`
  + `pengguna_jabatan`** (jabatan diisi bila masih kosong). Mendukung permintaan
  "pencatatan harus pegawai yang terdaftar" + halaman Distribusi Per Pengguna (#317).
- **Peringatan lunak** "NIP/NIK belum terdaftar di Master Pegawai" bila NIP diisi
  manual tapi tak cocok — **non-blocking** (tak menghalangi simpan; data lama aman).
- **Offline-safe**: master dimuat sekali saat form dibuka (best-effort); gagal/offline
  → pemilih tampil "tak tersedia", ketik manual tetap jalan. Tanpa perubahan
  registry (`user`/`pengguna_nip`/`pengguna_jabatan` sudah ada). `yarn lint` 0 error,
  `yarn build` sukses.

---

## [#317] Laporan Eksekutif: halaman Distribusi Per Pengguna (key NIP/NIK, terhubung Master Pegawai) — 2026-07-16

- **Halaman baru "Distribusi Per Pengguna"** di Laporan Eksekutif. Aset
  dikelompokkan per **KEY = NIP/NIK** (`pengguna_nip`), **ditampilkan dengan nama
  pengguna** — nama & unit kerja diambil dari **Master Pegawai** bila NIP terdaftar
  (join `db.pegawai` per `nip`), fallback ke nama pada aset.
- Kolom: #, Nama Pengguna, NIP/NIK, Unit Kerja, bar, NUP, Nilai (Rp); terurut nilai
  desc. Baris dengan **NIP belum terdaftar di master ditandai "(belum terdaftar)"**;
  aset tanpa NIP dikelompokkan "Tanpa Pengguna / NIP". Header memuat ringkasan
  jumlah pengguna & jumlah NIP belum terdaftar.
- Logika murni `report_utils.distribusi_pengguna` (+ uji unit) → `pytest tests/unit`
  **416 lulus**; **smoke-render WeasyPrint** OK (PDF valid, halaman baru + hitungan
  stiker benar).

---

## [#316] Laporan Eksekutif: perbaiki hitungan "Stiker Belum Terpasang" — 2026-07-16

- **Perbaikan bug**: pada Laporan Eksekutif bagian **Status Pemasangan Stiker**,
  "Belum Terpasang" bisa menampilkan **0 padahal ada aset tanpa stiker**. Penyebab:
  hitungan dibatasi hanya ke aset ber-`inventory_status = "Ditemukan"` dan `belum`
  dihitung sebagai `(jumlah Ditemukan − terpasang)`; aset yang **belum
  diinventarisasi** (justru yang belum berstiker) tak ikut terhitung → `belum` bisa 0.
- **Perbaikan**: status stiker kini dihitung **atas SELURUH aset kegiatan** —
  terpasang = `stiker_status == "Sudah Terpasang"`, belum = sisanya (termasuk kosong),
  persen atas total aset. Diterapkan di ringkasan utama & laporan satker/grup;
  teks simpulan menyesuaikan (X dari total).
- Logika dipisah ke helper murni `report_utils.hitung_status_stiker` + uji unit
  → `pytest tests/unit` **414 lulus**.

---

## [#315] Inventarisasi aset: input Kode Aset terhubung ke referensi kodefikasi — 2026-07-16

- **Pemilih kode barang dari referensi** di form aset (`AssetForm.jsx`). Di samping
  input "Kode Aset" kini ada tombol **Referensi** → dropdown pencarian
  (`GET /kodefikasi?search=`) menampilkan kode + uraian + level + satuan; memilih
  satu **mengisi `asset_code`** dan **`asset_name`** (bila nama masih kosong).
  Tersembunyi saat kode dikunci kategori.
- **Konfirmasi keterhubungan**: saat kode terdaftar penuh, muncul baris hijau
  **"Terhubung ke referensi: «nama resmi»"** (dari `/kodefikasi/lookup`), melengkapi
  peringatan kuning yang sudah ada untuk kode tak terdaftar.
- **Aman offline & tidak memblokir**: input bebas tetap bisa diketik; semua panggilan
  referensi best-effort — gagal/offline diabaikan (pemilih menampilkan "referensi tak
  tersedia"), seragam dengan pola cek-kode/ruangan yang ada. Tanpa perubahan backend/
  registry (satuan tidak disimpan, hanya info) → tak menyentuh anti-drift.
- Verifikasi: `yarn lint` (0 error) + `yarn build` sukses. Endpoint kodefikasi sudah teruji.

---

## [#314] Kodefikasi: dua format ekspor (datar & hierarki + info SIMAN) — 2026-07-16

- **Ekspor referensi kode barang dalam dua pendekatan** (`GET /kodefikasi/export?bentuk=`,
  XLSX, untuk semua user login):
  - **datar**: satu baris per kode — Kode, Uraian, Level, Kode Induk (mengikuti
    tampilan tabel sekarang).
  - **hierarki**: satu baris per **kode barang level 5**, dengan kolom hierarki
    tiap tingkat (Kode+Nama Golongan → Bidang → Kelompok → Sub Kelompok → Kode
    Barang/Nama) **plus informasi tambahan SIMAN** (Satuan, Dasar, Jenis BMN,
    TB/STB, Bukti Kepemilikan).
- Dua tombol **Ekspor Datar** & **Ekspor Hierarki** di `KodefikasiPage.jsx`.
  Ekspor hierarki memuat semua kode→uraian sekali (isi kolom leluhur via prefix),
  `openpyxl write_only` untuk ~14 ribu baris.
- Diuji: `pytest tests/unit` **411 lulus** + **smoke-test XLSX** (FakeDB) — kedua
  bentuk valid, header/kolom/metadata benar. `eslint`/`yarn build` bersih.
  Melengkapi fitur referensi kode barang SIMAN (impor #312, Detail #313, ekspor ini).

---

## [#313] Kodefikasi: panel Detail (hierarki + info SIMAN) & impor banyak file — 2026-07-16

- **Panel Detail per kode** (tombol info, untuk semua user) menampilkan
  **hierarki berjenjang** (Golongan → … → level kode, via `/kodefikasi/lookup`)
  **dan informasi tambahan SIMAN** (Satuan, Dasar, Jenis BMN, TB/STB, Bukti
  Kepemilikan). Sesuai permintaan, metadata ini **tidak ditampilkan di tabel
  utama** — hanya lewat Detail.
- **Impor banyak file sekaligus**: input impor kini menerima beberapa file (mis.
  5 file SIMAN per level) — tiap file di-POST berurutan, hasilnya diringkas jadi
  satu notifikasi (total baru/diperbarui/berinfo SIMAN/error).
- Perubahan murni frontend (`KodefikasiPage.jsx`); `eslint --max-warnings=0`
  bersih, `yarn build` sukses. Menyusul: **dua format ekspor** (#K3).

---

## [#312] Kodefikasi: impor keluaran SIMAN V2 + metadata barang — 2026-07-16

- **Impor referensi kode barang langsung dari keluaran SIMAN V2** (5 file per
  level: Golongan/Bidang/Kelompok/Sub Kelompok/Sub-Sub Kelompok). Parser
  `parse_import_rows` kini mengenali header khas SIMAN (`Kode Golongan`,
  `Kode Bidang Barang`, `Kode Kelompok Barang`, `Kode Sub Kelompok Barang`,
  `Kode Barang`, `Nama …`) — memilih **kode penuh terdalam** di tiap file
  (mis. 7 digit, bukan kolom induk 5 digit), di samping format `kode,uraian`
  lama. Level & induk tetap diturunkan dari panjang kode (tak pernah dari file).
- **Menyimpan metadata barang SIMAN** per kode (level 5): `satuan`, `dasar`,
  `jenis_bmn`, `tb_stb`, `bukti_kepemilikan` — additif, **tidak** mengubah 4
  field inti (`kode/uraian/level/parent_kode`) sehingga seluruh integrasi modul
  (laporan, audit FK, persediaan, penilaian) tetap jalan. `_doc` mengembalikan
  `meta` untuk panel Detail (menyusul). Impor melaporkan jumlah "berinfo SIMAN".
- Diuji: `pytest tests/unit` **411 lulus** + verifikasi end-to-end 5 file SIMAN
  asli (**14.008 entri, 0 error, 0 duplikat**, level 1–5 & induk benar).
- Menyusul: panel **Detail** (hierarki + metadata, tak tampil di tabel utama) &
  impor banyak file sekaligus (#K2); **dua format ekspor** (datar + hierarki
  berkolom golongan→sub-sub + metadata) (#K3).

---

## [#311] Persediaan → status Aktif + rapikan teks/docstring — 2026-07-16

- **Modul Inventarisasi Persediaan kini berstatus "Aktif"** (dari "Sebagian
  Aktif") di Beranda Modul (`bmnModules.js`) — setelah #306–#310 melengkapi jenis
  transaksi SAKTI, tautan Pengadaan, panel layer FIFO, & akun neraca per akun.
- Rapikan **teks 'ringkas' basi** (menghapus "Menyusul: gudang & impor massal"
  yang sudah lama ada) + menambah fitur baru ke daftar (jenis SAKTI lengkap,
  tautan Pengadaan, layer FIFO, akun neraca 1171xx).
- Perbarui **docstring basi "iterasi berikutnya"** di `routes/persediaan.py` &
  `persediaan_fields.py` (fitur transaksi/opname sudah ada). Non-fungsional;
  `pytest tests/unit` **408 lulus**, `eslint`/`yarn build` bersih.
- **Catatan:** sub-akun neraca 1171xx selain **117111** masih **perlu verifikasi
  Lampiran BAS**; alur governance (approval operator→approver, kunci back-date,
  penghapusan definitif 2-tahap) sengaja **ditunda** menunggu keputusan pemilik.

---

## [#310] Persediaan: akun neraca 1171xx + Laporan Posisi per akun — 2026-07-16

- **Memetakan persediaan ke akun neraca (sub-kelompok 1171xx).** Util murni baru
  `persediaan_akun_utils.py` (`akun_persediaan`, `validate_akun_persediaan`,
  `AKUN_PERSEDIAAN_DEFAULT`) — **default terkonfirmasi `117111` (Barang
  Konsumsi)**; sub-akun lain (117112/117113/117114/117131/117191/117199) =
  rujukan riset **[perlu verifikasi Lampiran BAS]**, dapat ditimpa satker per
  sub-kelompok (5 digit) via koleksi `persediaan_akun`.
- **Laporan Posisi Persediaan** kini menampilkan **kolom "Akun"** per barang +
  **rekapitulasi nilai per akun neraca** (dasar penyajian di Neraca) — sebelumnya
  hanya per kelompok kodefikasi tanpa akun.
- Uji unit ditambah → **408 lulus**; PDF di-smoke-test (FakeDB, default + override).
  Kode 6-digit sub-akun **perlu verifikasi** (sumber .go.id terhambat proxy) —
  ditandai jelas, tidak ditebak. UI kelola pemetaan menyusul bila diperlukan.

---

## [#309] Persediaan: panel rincian layer FIFO (read-only) — 2026-07-16

- **Menampilkan saldo per layer FIFO** yang sebelumnya hanya ada di backend
  (`GET /persediaan/{id}` mengembalikan `batches`; daftar sengaja tak memuatnya).
  Tombol **"Layer FIFO"** per barang membuka dialog tabel per layer: tanggal, qty,
  harga (melekat), **nilai (qty × harga)**, kedaluwarsa, ref — terurut tertua dulu
  (urutan konsumsi), dengan baris **Jumlah** (total qty = stok, total nilai).
- Menegaskan penilaian **FIFO murni** (bukan rata-rata) & mendukung telaah "Persediaan
  per Layer". Murni read-only, tanpa perubahan alur tulis. `eslint --max-warnings=0`
  bersih, `yarn build` sukses.

---

## [#308] Persediaan: tautan Pengadaan + tgl/no kontrak di dialog masuk — 2026-07-16

- **Menyalakan integrasi dokumen sumber yang sudah siap di backend.** Dialog
  **Transaksi Masuk** kini punya pemilih **Perolehan (Pengadaan)** (opsional) —
  menautkan layer FIFO ke BAST di modul Pengadaan (`perolehan_id`,
  `_ambil_snapshot_perolehan`); memilih perolehan **mengisi otomatis** penyedia,
  no. kontrak, tanggal, no. bukti (BAST) & jenis dokumen yang masih kosong.
- Menambah input **Tgl Dokumen** & **No. Kontrak** (sebelumnya di-seed tapi tanpa
  field) — kini terkirim ke `TransaksiMasukIn`. Sebelumnya UI selalu mengirim
  kosong meski backend menerimanya.
- Daftar perolehan diambil dari `GET /pengadaan` saat halaman dimuat.
  `eslint --max-warnings=0` bersih, `yarn build` sukses.

---

## [#307] Persediaan: jenis transaksi SAKTI dilengkapi — 2026-07-16

- **Melengkapi peta jenis transaksi persediaan → SAKTI (pustaka §3.2).** Menambah
  jenis **Masuk**: **Rampasan** (M05), **Reklasifikasi Masuk** (M06),
  **Reklasifikasi dari Aset** (M07); dan **Keluar**: **Penghapusan Lainnya** (K06),
  **Reklasifikasi Keluar** (K07) di `JENIS_MASUK`/`JENIS_KELUAR`.
- Jenis baru **muncul otomatis** di dialog masuk/keluar/transaksi massal (UI
  mengambil dari `/persediaan/jenis-transaksi`) — memakai jalur FIFO/validasi yang
  sama, tanpa perubahan frontend. Kode M05–M07/K06–K07 = kode internal aplikasi
  (perlu verifikasi kode SAKTI resmi).
- Uji unit diperluas (set jenis + validasi jenis baru) → **404 lulus**. Ditunda
  (governance, menunggu keputusan): Koreksi sebagai jenis tersendiri, penghapusan
  definitif 2-tahap (H01/H02), alur approval operator→approver.

---

## [#306] Master Pegawai — data kepegawaian menyeluruh satker (adopsi SIMAN-G) — 2026-07-16

- **Modul referensi baru: Master Pegawai.** BERBEDA dari Referensi Pejabat
  (khusus pejabat penatausahaan/penanda tangan), master `pegawai` menampung
  **SELURUH pegawai** satker beserta **unit kerjanya masing-masing**, mengadopsi
  kelengkapan data SIMAN Modul Pegawai (SIMAN-G)/SIMPEG.
- Field: NIP (unik bila diisi), gelar depan/belakang, jenis kelamin, tempat/tgl
  lahir, status kepegawaian (PNS/CPNS/PPPK/TNI/POLRI/Non-ASN), pangkat golongan,
  jabatan, jenis jabatan (struktural/fungsional/pelaksana), eselon, unit kerja,
  unit organisasi, NPWP, pendidikan, no. HP, email (divalidasi), alamat, TMT,
  status di satker (aktif/cuti/tugas belajar/mutasi/pensiun/nonaktif). Hanya
  `nama` wajib.
- Backend: `pegawai_utils.py` (murni: `validate_pegawai`, `nama_lengkap`,
  `is_aktif`, `kelompok_unit_kerja`) + `routes/pegawai.py` (CRUD admin, list,
  `/pegawai/referensi`, `/pegawai/rekap-unit`; NIP unik) terdaftar di
  `server.py`. Uji unit ditambah → **404 lulus**.
- Frontend `PegawaiPage.jsx`: daftar + cari + form berkelompok (Identitas,
  Kepegawaian, Jabatan & Unit, Kontak); badge status kepegawaian & status
  satker; dibuka dari **Beranda Modul** (tombol "Master Pegawai"). `eslint`
  bersih, `yarn build` sukses.

---

## [#305] Master pegawai lebih kaya: status kepegawaian, kontak & unit kerja — 2026-07-16

- **Melengkapi bagian (b): registry Pejabat diperkaya (adopsi SIMAN-G).** Tiap
  pejabat kini dapat menyimpan **status kepegawaian** (PNS/CPNS/PPPK/TNI/POLRI/
  Non-ASN), **unit kerja**, **no. HP**, & **email** — di samping NIP & pangkat
  golongan yang sudah ada. Semua field baru **opsional** (tidak merusak API atau
  blok tanda tangan laporan lama).
- Backend: `pejabat_utils.py` konstanta `STATUS_KEPEGAWAIAN` + validasi
  status_kepegawaian & format email (`validate_pejabat`); `routes/pejabat.py`
  field baru di `PejabatIn`/`_bersih` + endpoint referensi mengekspos daftar
  status untuk dropdown. Uji unit ditambah → **397 lulus**.
- Frontend `PejabatPage.jsx`: field form Status Kepegawaian (dropdown), Unit
  Kerja, No. HP, Email; badge status + unit kerja di tabel; pencarian mencakup
  unit kerja & email. `eslint` bersih, `yarn build` sukses.

---

## [#304] UI kelola Referensi Akun Neraca (BAS) — 2026-07-16

- **Melengkapi bagian (a): halaman React "Referensi Akun Neraca"**
  (`AkunBasPage.jsx`) — antarmuka mengelola pemetaan **golongan BMN → akun
  neraca (BAS)** yang mendasari kolom Akun di Neraca (#302) & DBKP (#303).
  Sebelumnya pemetaan hanya bisa diubah lewat API (`/akun-bas`).
- Semua user login melihat 8 golongan (akun, uraian, sumber **Default riset** /
  **Input satker**); **admin** menyunting akun+uraian per golongan
  (`POST /akun-bas`) atau mengembalikan override ke default
  (`DELETE /akun-bas/{golongan}`). Input akun difilter 3–6 digit angka.
- Banner peringatan menegaskan akun default adalah **akun representatif hasil
  riset — wajib diverifikasi ke Lampiran BAS** (KEP-211/PB/2018). Dibuka dari
  **Beranda Modul** (tombol "Referensi Akun Neraca", pola Pejabat/Ruangan).
- Wiring `App.js` (lazy route + `showAkunBas`) & `ModuleHomePage.jsx` (prop
  `onOpenAkunBas` + tombol). `eslint` bersih, `yarn build` sukses.

---

## [#303] DBKP per Golongan: kolom Akun Neraca — 2026-07-16

- **Melanjutkan #302 ke DBKP.** Laporan **Daftar Barang Kuasa Pengguna (DBKP)
  per Golongan** (`GET /pembukuan/dbkp-pdf`) kini juga menampilkan **kolom "Akun
  Neraca"** per golongan (dari referensi Akun/BAS #300, default riset ditimpa
  entri satker) — seragam dengan Laporan Posisi BMN di Neraca (#302).
- Perubahan wiring murni; `py_compile` bersih, suite 395 lulus (tabel 9-kolom
  konsisten header/baris/colWidths). UI kelola akun/BAS menyusul.

---

## [#302] Laporan Posisi BMN di Neraca: kolom Akun Neraca per golongan — 2026-07-16

- **Memanfaatkan referensi Akun/BAS (#301).** Laporan **Posisi BMN di Neraca**
  (`GET /pembukuan/posisi-bmn-pdf`) kini menampilkan **kolom "Akun Neraca"** per
  golongan (mis. gol. 3 → 132111), diambil dari `akun_untuk_golongan` (default
  riset ditimpa entri satker) — sebelumnya hanya golongan tanpa kode akun.
- Catatan laporan menegaskan **akun representatif per golongan** (akun per
  sub-kelompok dapat berbeda — verifikasi Lampiran BAS). Perubahan wiring murni;
  `py_compile` bersih, smoke test tabel 9-kolom OK, suite 395 lulus.
- Kolom Akun di DBKP + UI kelola akun/BAS menyusul.

---

## [#301] Master Referensi Akun Neraca (BAS) per golongan BMN — 2026-07-16

- **Referensi baru (riset)** memetakan **golongan kodefikasi → akun neraca aset**
  (Bagan Akun Standar), agar laporan posisi BMN dapat selaras SAKTI/SIMAK. Menutup
  celah: `kode_akun` selama ini hanya teks bebas.
- **Default terkonfirmasi** dari Neraca Percobaan Akrual satker + Laporan Posisi
  BMN di Neraca berbagai K/L (sumber sekunder resmi): 2 Tanah=131111, 3 Peralatan
  & Mesin=132111, 4 Gedung & Bangunan=133111, 5 JIJ=134111, 6 Aset Tetap
  Lainnya=135121, 7 KDP=136111, 8 ATB=162151, 1 Persediaan=117xxx. **Akun per
  sub-kelompok bervariasi** → nilai representatif per golongan, **ditandai
  perlu-verifikasi Lampiran BAS** & **dapat ditimpa admin** (pola masa manfaat).
- **`akun_bas_utils.py`** (murni): `AKUN_NERACA_DEFAULT`, `validate_akun_bas`,
  `akun_untuk_golongan(kode_barang, peta)`. **`routes/akun_bas.py`**: `GET /akun-bas`
  (default ditimpa entri satker) + upsert/delete admin. Pustaka §2.5.
- **3 unit test** murni (suite 395 lulus); `py_compile` bersih. Pemanfaatan di
  kolom Neraca & UI kelola menyusul.

---

## [#300] KIR — Kartu Inventaris Ruangan (kartu per ruangan) — 2026-07-16

- **Dokumen penatausahaan baru** melengkapi seri ruangan. `GET /pembukuan/kir-pdf`
  mencetak **kartu per ruangan** (satu ruangan per halaman): kop surat + judul
  KIR + daftar BMN ruangan (No/Kode/NUP/Nama/Kondisi/Nilai) + subtotal.
- **Integrasi master ruangan**: tiap kartu menautkan **Penanggung Jawab Ruangan**
  dari master (#294) bila nama ruangan cocok (`cocok_ruangan_master` — cocok via
  "KODE — Nama", kode, atau nama), lalu **ditandatangani PJ Ruangan + KPB aktif**
  (`_penandatangan_kpb`, #293). Ruangan tak-tertaut ditandai jelas.
- **`ruangan_utils.cocok_ruangan_master`** (murni). **5 unit test** ruangan
  (1 baru); PDF diverifikasi lokal (`%PDF-`), `py_compile` bersih, suite 392
  lulus. Tombol **KIR** ditambahkan di hub Pelaporan (di samping DBR).

---

## [#299] Form aset: saran ruangan (master) di field Lokasi — 2026-07-16

- **Menghubungkan aset ke Master Ruangan (#294) secara ringan** tanpa mengubah
  skema aset. Field **Lokasi** di form aset kini punya **datalist** (autocomplete)
  berisi ruangan master (`kode — nama`) → penamaan ruangan **konsisten** sehingga
  **DBR** (#297) mengelompokkan rapi; tetap boleh diketik bebas untuk data lama.
- Saran dimuat sekali saat form dibuka (`GET /ruangan`, best-effort; offline
  diabaikan). Perubahan UI murni — nilai tetap tersimpan di field `location` yang
  ada (tanpa field/registry baru, tanpa dampak offline-snapshot).
- eslint 0 error, `yarn build` (craco) sukses. Tautan `ruangan_id` FK penuh &
  KIR per ruangan menyusul bila diperlukan.

---

## [#298] Tombol unduh DBR di hub Pelaporan — 2026-07-16

- **Menyurfacekan DBR (#297) di UI.** Tombol **"DBR"** ditambahkan di kartu
  Pembukuan satker-wide halaman **Pelaporan** (di samping Posisi BMN / LKB /
  LBKP) → mengunduh **Daftar Barang Ruangan** (`GET /pembukuan/dbr-pdf`).
- Perubahan UI murni (satu tombol, pola `downloadFileWithProgress` yang ada);
  eslint bersih, `yarn build` sukses.

---

## [#297] DBR — Daftar Barang Ruangan (PDF per ruangan) — 2026-07-16

- **Artikel penatausahaan baru** memanfaatkan Master Ruangan (#294/#296).
  `GET /pembukuan/dbr-pdf` mengelompokkan seluruh BMN aktif **per ruangan** →
  PDF resmi (kop surat, per-ruangan: No/Kode/NUP/Nama/Kondisi/Nilai + subtotal
  unit & nilai) + **tanda tangan KPB aktif** (`_penandatangan_kpb`).
- **Lokasi dari data yang ADA** (tanpa fabrikasi): pengguna melekat ke Ruangan
  (nama di `user`) atau `location` teks bebas; aset tanpa lokasi tetap tampil di
  bagian **"(lokasi belum dicatat)"** (paling akhir) agar tak hilang dari DBR —
  sekaligus menyorot data yang perlu dilengkapi.
- **`ruangan_utils.ruangan_aset` + `kelompok_dbr`** (murni): derivasi ruangan +
  pengelompokan bernilai (memakai `parse_harga`). **4 unit test** (2 baru);
  `py_compile` bersih. Tautan `ruangan_id` per aset & KIR menyusul.

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
