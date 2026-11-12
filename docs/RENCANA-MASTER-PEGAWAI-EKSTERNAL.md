# Rencana: Master Pegawai Tiga Kelompok — Internal, Instansi Eksternal, Pihak Ketiga

> **Status:** rencana, belum ada kode yang diubah.
> **Baseline:** `main` pada commit `7d1af3e` (PR #1111), 10 November 2026.
> **Pelaksana yang dituju:** Opus 5.5 (atau model/orang lain) — dokumen ini
> berdiri sendiri; tidak butuh riwayat percakapan yang melahirkannya.
> **Nomor baris** di bawah adalah petunjuk pada baseline. Baris bergeser;
> **nama fungsi** yang menjadi pegangan. Revalidasi sebelum menyunting.

> **Revisi 7 (10 November 2026) — menggantikan revisi sebelumnya.** Isinya
> sama dengan Revisi 6; dibaca ulang utuh dan diselaraskan antarbab.
> Arahan pemilik yang membentuknya, berurutan:
> 1. Master Pegawai internal **tidak berubah**; kelompok luar memakai
>    **struktur yang sama** (instansi → satker → unit kerja → pegawai).
> 2. Master luar adalah **satu direktori untuk seluruh instansi**, bukan per
>    satker.
> 3. Pengelompokan ini ada karena BMN dapat diserahkan pakai kepada instansi
>    lain dan kepada pihak di luar pemerintahan (sekolah swasta, BUMN/BUMD,
>    masyarakat, perusahaan swasta).
> 4. **Pihak ketiga disesuaikan lebih jauh**: ada field khusus, ada field
>    lama yang dinonaktifkan atau dimanfaatkan ulang.
> 5. Tiap kelompok punya **ikon sendiri** yang tampil di semua catatan
>    aplikasi — **kecuali persuratan**, demi keresmian naskah.
> 6. Pengelompokan menjadi dasar **kebijakan dan pasal yang berbeda** per
>    jenis penerima.
> 7. Catatan bersama boleh ditambah dan diubah **semua admin**, tercatat di
>    audit.
> 8. Naskah cetak **tanpa ikon**, kecuali **Laporan Eksekutif**: penggunanya
>    diberi ikon kelompok.
> 9. Data pribadi **tidak dikumpulkan** untuk instansi eksternal maupun pihak
>    ketiga.
> 10. Instansi dan satkernya **tidak boleh tercampur** satu dengan yang lain.
> 11. Tujuannya **mengelompokkan pegawai agar mudah dilihat**: layar dibuka
>     dengan memilih kelompok dulu — internal, instansi eksternal, atau pihak
>     ketiga — dan pilihan itu langsung menjadi saringan.
>
> 12. Instansi eksternal dipilah lagi: **pusat** (kementerian/lembaga) atau
>     **daerah** (pemda: provinsi/kabupaten/kota), masing-masing dengan
>     **ikonnya sendiri**.
> 13. Kabupaten/kota **ditautkan ke provinsinya**.
>
> Butir 11 juga menjadi batas lingkup: direktori ini memuat **identitas**
> (siapa orangnya, di instansi dan satker mana). Fakta hubungan satker dengan
> pihak tertentu — perjanjian, masa berlaku, tarif — tetap di transaksinya
> (BAST, Pemanfaatan, Penggunaan), tidak disalin ke direktori.

## 0. Cara memakai dokumen ini

### Prompt siap pakai — memulai

```text
Anda melanjutkan repositori ModernIlham/NEW-AMAN-IKN.
Baca .claude/skills/aman-dev/SKILL.md lalu
docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md sampai habis sebelum menyunting apa pun.

Kerjakan paket PGW berikutnya yang belum selesai menurut tabel status di
Bab 8, dengan dependency terpenuhi. Satu paket = satu PR.

Aturan yang tidak boleh dilanggar: Master Pegawai INTERNAL tidak berubah.
Jangan menyunting backend/routes/pegawai.py, routes/unit_kerja.py,
routes/satker.py, atau perilaku koleksi pegawai/unit_kerja/satker, kecuali
sebuah paket menyebut suntingan itu secara eksplisit.

Revalidasi dulu setiap fakta di Bab 2 terhadap main terbaru: bila sebuah
fungsi sudah berubah, laporkan selisihnya dan sesuaikan — jangan memaksakan
rencana pada kode yang sudah berbeda.

Keputusan di Bab 4 memakai nilai BAWAAN kecuali pemilik sudah menulis jawaban
lain di tabel itu. Jangan mengubah bawaan atas inisiatif sendiri.

Jangan menulis teks pasal atau nomor peraturan ke dokumen keluaran sebelum
PGW-00 selesai dan sitasinya terdaftar (lihat PGW-10).

Ikuti pipeline ship di skill aman-dev (unit test, eslint, build, PR draft,
CI hijau). Perbarui kolom status Bab 8 dan CHANGELOG di PR yang sama.
```

### Prompt siap pakai — satu paket

```text
Kerjakan PGW-XX dari docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md.
Periksa dependency-nya sudah ter-merge. Tulis ujinya dulu (harus gagal
sebelum perubahan), implementasikan, jalankan kriteria terima paket itu,
lalu buka PR draft. Jangan menyentuh berkas di luar daftar paket kecuali
uji anti-drift menagihnya — bila begitu, sebutkan di deskripsi PR.
```

### Aturan main

1. **Internal tidak disentuh.** Koleksi `pegawai`, `unit_kerja`, `satker`
   beserta rutenya tetap seperti hari ini. Uji lama untuk ketiganya harus
   lulus **tanpa disunting** di setiap paket.
2. **Ketergantungan satu arah.** Modul "luar" boleh mengimpor dari modul
   internal. Modul internal tidak pernah mengimpor dari modul luar.
3. **Modul luar tidak pernah menulis ke koleksi internal** (`pegawai`,
   `unit_kerja`, `satker`, `assets`). Ada uji yang menagihnya (PGW-03).
4. **Direktori luar bersama; data aset tetap per satker.** Jangan membungkus
   koleksi luar dengan `scope_query_field_satker`, dan jangan melepas scope
   dari kueri aset.
5. **Tanpa migrasi data.** Tidak ada dokumen lama yang diubah.
6. **Buktikan, jangan menyimpulkan.** Uji baru harus gagal sebelum perubahan.
7. **Konvensi repo tetap berlaku seluruhnya:** teks UI/commit/PR Indonesia,
   OCC + Idempotency-Key, aturan blok tanda tangan, registry sitasi,
   `data-testid`, aturan hover, komponen React di level modul, tap-target 44px.

---

## 1. Tujuan dan batasnya

### Bentuk yang dihasilkan

| Tingkat | Internal (hari ini, tetap) | Instansi eksternal | Pihak ketiga |
|---|---|---|---|
| Instansi | tersirat (instansi sendiri) | `instansi_luar` | `instansi_luar` — "Badan/Pihak" |
| Satker | `satker` | `satker_luar` | `satker_luar` — "Unit/Cabang" |
| Unit kerja | `unit_kerja` (Eselon I–V) | `unit_kerja_luar` (Eselon I–V) | `unit_kerja_luar` — "Tingkat I–V" |
| Orang | `pegawai` | `pegawai_luar` — field sama, tanpa data pribadi | `pegawai_luar` — disesuaikan (3.7) |
| Cakupan | per satker | **seluruh instansi** | **seluruh instansi** |
| Ikon | kartu pegawai | gedung pemerintah (pusat) · peta wilayah (daerah) | jabat tangan |

Layar Master Pegawai dibuka dengan **memilih kelompok** lebih dulu; pilihan
itu langsung menjadi saringan dan diingat untuk kunjungan berikutnya (3.10).

Kemampuan yang sama di ketiga kelompok: tambah/ubah, cari, saring, urut,
OCC, audit, foto, kartu tap, impor/ekspor/template Excel pulang-pergi,
struktur organisasi berjenjang, rekap per unit, bangun unit dari pegawai,
daftar aset yang dipegang, peringatan "masih memegang aset".

### Yang BUKAN tujuan (ditunda — akhir Bab 8)

- Mengganti kunci tautan aset dari `pengguna_nip` (teks NIP/NIK) menjadi FK.
- Akses portal BMN Saya untuk orang luar.
- Memindahkan seseorang antara master internal dan master luar.
- Menggantikan modul Pemanfaatan/Penggunaan/Pemindahtanganan: persetujuan
  Pengelola Barang, perjanjian, dan tarif tetap diurus di sana. Fitur ini
  hanya mengenali **siapa** pihaknya dan menyesuaikan naskah serah terima.

---

## 2. Keadaan sekarang (bukti dari kode dan naskah di repo)

### 2.1 Bentuk master internal

- `pegawai`: ±56 field isian form. Logika murni di
  `backend/pegawai_utils.py`; rute di `backend/routes/pegawai.py` (1.255
  baris); layar `frontend/src/pages/PegawaiPage.jsx` (1.954 baris).
- `unit_kerja`: pohon `{nama_unit, eselon "1".."5", parent_id}` per satker.
  Aturan pohon murni di `backend/organisasi_utils.py`; rute di
  `backend/routes/unit_kerja.py`. Pegawai menyimpan unitnya sebagai **nama**
  di `eselon1..5`; ganti nama unit dirambatkan (`_rambatkan_nama`) ke
  `pegawai` **dan** `assets`.
- `satker`: profil + kop per satker (`backend/routes/satker.py`). Puncak
  pohon unit = `eselon_satker`.

### 2.2 `kode_satker` adalah kunci ISOLASI

Seluruh isolasi multi-satker bertumpu pada field `kode_satker`:
`scope_query_field_satker`, `pastikan_akses_dok_satker`, ikatan akun, kop,
audit, dan `satker_referensi.ganti_kode_satker` (menyapu semua koleksi
ber-`kode_satker`). Dokumen **tanpa** `kode_satker` lolos saringan itu untuk
semua satker (semantik "era lama"). Skill aman-dev melarang dua arah
kesalahan: membiarkan yang privat terbuka, dan men-scope yang sengaja
bersama. Koleksi luar **sengaja bersama** (Bab 3.4).

### 2.3 Kunci tautan ke aset adalah TEKS NIP/NIK

Aset menyimpan `user`, `pengguna_nip`, `pengguna_jabatan`,
`pengguna_melekat_ke`. Rantai pemegang berkunci `pengguna_nip`. Orang tanpa
nomor identitas tidak bisa ditautkan sebagai pemegang — berlaku untuk
internal hari ini dan akan berlaku sama untuk orang luar (K5).

### 2.4 Pembaca Master Pegawai di luar rutenya

Koleksi `pegawai` disentuh di 57 tempat: 27 di `routes/pegawai.py`, 30 di 14
berkas lain. Sembilan di antaranya mencari orang lewat NIP dan layak ikut
mengenali orang luar (Bab 7.2). Pembaca frontend `GET /pegawai`:
`AssetForm.jsx:666`, `PenggunaanPage.jsx:325,479`, `PersediaanPage.jsx:209`,
`PemeliharaanPage.jsx:135`, `TtdPermintaanPage.jsx:130`,
`ActivitySelectionPage.jsx:222`, `PejabatPage.jsx:112`,
`PortalPemegangPanel.jsx:97`, `PegawaiPage.jsx:257`.

### 2.5 Uji yang membaca SUMBER `routes/pegawai.py`

`test_pegawai_impor_dedup.py`, `test_cpu_sinkron_di_thread.py`,
`test_gerbang_media.py`, `test_penjaga_senyap.py` membaca teks berkas itu;
`test_pegawai_cakupan_ekspor.py` membaca `const EMPTY` di `PegawaiPage.jsx`.
Merombak berkas internal mematahkannya — alasan desain 3.5.

### 2.6 Konsep yang bertumpang-tindih dengan permintaan

| Yang sudah ada | Kedudukannya |
|---|---|
| Non-ASN **outsourcing** + `perusahaan_penyedia` | Tenaga alih daya yang *ditempatkan di satker* — tetap **internal** (K4) |
| `status_pegawai_satker` perbantuan/dipekerjakan + `status_pegawai_instansi` | Bekerja di satker, berasal dari instansi lain — tetap **internal** |
| "Pihak luar — isi identitas manual" (`PilihPegawaiBast.jsx`) | Jalur manual **tetap ada** |
| `BENTUK_PEMANFAATAN` (`pemanfaatan_utils.py`), `JENIS_PSP` (`penggunaan_utils.py`) | Skema hukumnya sudah dikenal aplikasi; pihaknya masih teks bebas (`mitra`, `pihak`, `pihak_tujuan`) |

### 2.7 Foto pegawai dan pengonversi WebP

`webp_converter.py` menganggap berkas GridFS ber-`metadata.jenis:
"foto_pegawai"` milik koleksi `pegawai`. Foto orang luar dengan jenis yang
sama tidak akan menemukan pemiliknya (Jebakan 9.2).

### 2.8 Pasal BAST hari ini ditulis untuk PEGAWAI SENDIRI

`backend/bast_pasal.py` — `butir_waktu`, `butir_risiko` — menyebut surat
tugas atasan, hukuman disiplin, dan tuntutan ganti kerugian menurut UU
1/2004 jo. PP 38/2016. Semua itu mengandaikan PIHAK KEDUA adalah pegawai
negeri di bawah satker. `JENIS_BAST` tidak punya jenis untuk penerima di
luar satker; `penggunaan_sementara` di sana berarti pinjam pakai **internal**
berjangka.

### 2.9 Apa kata naskah peraturan yang tersimpan di `docs/regulasi/`

Dibaca langsung dari teks hasil ekstraksi di repo. **[Keyakinan tinggi]**
atas bunyi teksnya; **[keyakinan sedang]** atas keberlakuannya hari ini —
repo tidak dapat memastikan perubahan sesudah naskah diunduh. PGW-00 membaca
ulang pasal demi pasal sebelum apa pun dicetak.

> **Diperbarui PGW-00 (2026-11-11):** matriks lengkap per jenis penerima,
> jawaban pertanyaan wajib, dan temuan status PMK 115/2020 kini ada di
> `docs/PUSTAKA-REGULASI-BMN.md` §2.4d. Tabel di bawah dipertahankan sebagai
> ringkasan awal; bila berbeda, pustaka yang berlaku.

| Penerima | Skema yang dikenal naskah | Sumber di repo |
|---|---|---|
| Pengguna Barang lain (K/L lain) | **Penggunaan sementara** — setelah persetujuan Pengelola Barang | `pmk-40-2024-penggunaan.txt` (Pasal 32) |
| Pemerintah Daerah, Pemerintah Desa | **Pinjam Pakai** — "antara Pemerintah Pusat dan Pemerintah Daerah… dalam rangka penyelenggaraan pemerintahan", berdasarkan perjanjian; peminjam pakai = Pemda dan Pemdes | `pp-27-2014…txt` (Pasal 30, diubah PP 28/2020); `pmk-115-2020-pemanfaatan.txt` |
| BUMN/BUMD/BUMDes, perorangan, unit penunjang penyelenggaraan pemerintahan, badan usaha lain | **Sewa** — Pengguna Barang menyewakan dengan persetujuan Pengelola Barang | `pmk-115-2020-pemanfaatan.txt` |
| BUMN, BUMD, swasta **kecuali perorangan** | **KSP**, **BGS/BSG** | `pmk-115-2020-pemanfaatan.txt` |
| Pihak Lain (= selain K/L dan Pemda) | **Dioperasikan oleh Pihak Lain** — untuk pelayanan umum sesuai tugas dan fungsi; dilarang dialihkan | `pmk-40-2024-penggunaan.txt` |
| Di Ibu Kota Nusantara | Bentuk pemanfaatan sama; tata caranya mengikuti ketentuan umum pengelolaan BMN | `pmk-53-2023-ikn.txt` (Pasal 21) |

**Akibat yang menentukan desain:** dalam naskah itu, "pinjam pakai" **tidak**
tersedia untuk sekolah swasta, perusahaan, BUMN/BUMD, atau perorangan. Bagi
mereka penyerahan BMN berdiri di atas sewa, KSP, BGS/BSG, KSPI, KETUPI,
pengoperasian oleh pihak lain, atau pemindahtanganan — masing-masing dengan
persetujuan dan/atau perjanjian. Karena itu:

- kebijakan ditentukan oleh **jenis instansi penerima**, bukan hanya oleh
  kelompoknya (K/L dan pemda sama-sama "eksternal" tetapi skemanya beda);
- naskah serah terima kepada pihak luar harus **merujuk dokumen dasarnya**,
  bukan berdiri sendiri sebagai "peminjaman" (PGW-10).

### 2.10 Temuan sampingan (jangan diperbaiki diam-diam)

`snapshot_pemegang_aset` (`pegawai_utils.py:388`) mengisi
`pengguna_melekat_ke` dengan **nama unit kerja**, padahal `models.py:82` dan
`AssetForm.jsx` memperlakukannya sebagai enum `Individual | Jabatan |
Operasional`. **[Keyakinan sedang]** — belum ditelusuri apakah ada pembaca
yang mengharapkan nama unit. Fitur "Sinkron aset" karenanya tidak dibawa ke
master luar.

---

## 3. Keputusan desain (terkunci)

### 3.1 Koleksi sejajar; internal tidak disentuh

Empat koleksi baru untuk orang dan organisasi **di luar** instansi sendiri:
`instansi_luar`, `satker_luar`, `unit_kerja_luar`, `pegawai_luar`. Kedua
kelompok non-internal berbagi keempatnya, dibedakan field `kelompok`.

| | Satu koleksi `pegawai` + penanda | Koleksi sejajar (dipilih) |
|---|---|---|
| Perubahan pada internal | 57 titik pakai harus dipagari | nol |
| Bila satu titik terlewat | orang luar bocor ke rekap unit, pemilih pejabat, portal — cacat baru | orang luar tampil "belum terdaftar" — sama seperti hari ini |
| Cakupan data | bentrok: internal per satker, luar se-instansi, dalam satu koleksi | tiap koleksi satu aturan cakupan |
| Satker & unit kerja milik instansi lain | tak punya tempat | punya koleksinya sendiri |

### 3.2 Batas tiga kelompok — ditentukan oleh TEMPAT BEKERJA

| Kelompok | Definisi | Contoh |
|---|---|---|
| Internal | Bekerja pada satker instansi sendiri, apa pun status kepegawaiannya | PNS/PPPK; PPNPN; tenaga alih daya yang ditempatkan; pegawai dipekerjakan/diperbantukan **dari** instansi lain |
| `eksternal` | Aparatur instansi pemerintah lain — dipilah **pusat** (K/L) dan **daerah** (pemprov, pemkab/pemkot) | Pusat: pejabat K/L pemakai sementara BMN. Daerah: petugas pemda peminjam pakai |
| `pihak_ketiga` | Orang dari badan non-pemerintah, atau perorangan | Wakil sekolah swasta, BUMN/BUMD, perusahaan, koperasi, yayasan; warga yang menyewa |

### 3.3 Hierarki luar meniru hierarki internal

```
instansi_luar ─┬─ satker_luar ─┬─ unit_kerja_luar (pohon Eselon/Tingkat I–V)
               │               └─ pegawai_luar (eselon1..5 = NAMA unit, seperti internal)
               └─ satker_luar …
```

Orang luar **wajib** berada di satu `satker_luar`. Instansi dibuat bersama
satker pertamanya (untuk pihak ketiga, layar mengisi nama satker pertama =
nama badan, bisa diubah). Pengecualian: pemda boleh dicatat tanpa perangkat
daerah dulu, karena provinsi sering dicatat hanya sebagai induk
kabupaten/kotanya.

**Jenjang daerah.** Pemda saling bertaut lewat `induk_id`:

```
Pemprov ─┬─ (perangkat daerah provinsi)
         └─ Pemkab/Pemkot ─┬─ (perangkat daerah kabupaten/kota)
                           └─ Pemdes ── (perangkat desa)
```

- Provinsi tidak berinduk. Kabupaten/kota **wajib** berinduk satu provinsi.
  Desa **wajib** berinduk satu kabupaten/kota.
- Provinsi (dan, untuk desa, kabupaten/kotanya) disalin ke tiap pemda di
  bawahnya dan ke satker serta orangnya, sehingga "semua di Provinsi X"
  dapat disaring tanpa menelusuri jenjang.
- Induk harus sudah tercatat. Mencatat Pemkab Y saat Provinsi X belum ada →
  layar menawarkan mencatat provinsinya dulu (cukup nama dan kodenya).
- Induk dapat diganti (pemekaran wilayah), tercatat di audit, dan salinan
  provinsinya ikut merambat. Pemda yang masih punya anak tidak bisa
  dihapus atau diganti jenisnya.
- Di layar, kabupaten/kota selalu ditulis bersama provinsinya: "Kab. Y,
  Prov. X — Dinas Z".
- K/L dan pihak ketiga tidak berjenjang: `induk_id` selalu kosong.

**Perorangan/masyarakat** tidak punya badan. Agar strukturnya tetap satu,
ada satu instansi-wadah berjenis `perorangan` — "Masyarakat (Perorangan)" —
dengan satu satker-wadah. Keduanya dibuat sistem saat pertama dibutuhkan,
tidak bisa dihapus atau diganti nama, dan pohon unitnya dinonaktifkan. Ini
struktur, bukan data contoh.

**Tidak tercampur — aturan penampungan.** Banyak instansi, masing-masing
dengan banyak satker, hanya tetap terbaca bila tiap tingkat tertutup rapat
di dalam induknya:

1. Satu satker milik **tepat satu** instansi. `instansi_id` sebuah satker
   tidak bisa diubah setelah dibuat — salah tempat diperbaiki dengan membuat
   satker di instansi yang benar lalu memindahkan orangnya, bukan menggeser
   satkernya.
2. Satu orang berada di **tepat satu** satker. `kelompok`, `tataran`,
   `instansi_id`, dan salinan provinsinya selalu **diturunkan server** dari
   satkernya, tidak pernah dikirim klien — sehingga orang tidak bisa
   "nyasar" ke instansi yang bukan induk satkernya.
3. Satu unit kerja berada di **tepat satu** satker. Ganti nama, hapus, dan
   bangun-unit selalu dibatasi satker itu; unit senama di satker atau
   instansi lain tidak tersentuh.
4. Pusat dan daerah tidak bercampur: `tataran` sebuah instansi eksternal
   **diturunkan server dari `jenis`-nya** dan ikut tersalin ke satker serta
   orangnya; `jenis` yang sudah punya satker tidak bisa diganti ke tataran
   lain. Daftar pusat tidak pernah memuat pemda, dan sebaliknya.
5. Kelompok tidak bercampur: instansi `eksternal` tidak bisa berisi satker
   atau orang pihak ketiga, dan `kelompok` sebuah instansi tidak bisa diubah
   setelah ia punya satker.
6. Internal tidak bercampur dengan luar: kode satker **internal** tidak
   boleh didaftarkan sebagai `satker_luar`; NIP pegawai internal tidak boleh
   didaftarkan sebagai orang luar.
7. Nama satker boleh sama di dua instansi (unik **per instansi**), jadi di
   layar mana pun yang menampilkan lebih dari satu instansi, satker selalu
   ditulis bersama instansinya: "Kementerian X — Sekretariat".
8. Pemilih selalu berjenjang: kelompok → (pusat/daerah) → (provinsi) →
   instansi → satker. Tiap daftar hanya memuat isi pilihan di atasnya;
   mengganti satu tingkat mengosongkan semua pilihan di bawahnya.
9. Impor ke satu satker tidak pernah menulis ke satker lain.

### 3.4 Satu direktori untuk seluruh instansi

Keputusan pemilik. Keempat koleksi luar **tidak** distempel `kode_satker`
dan **tidak** dibungkus `scope_query_field_satker`.

| Tindakan | Siapa | Catatan |
|---|---|---|
| Lihat | semua pengguna login, semua satker | |
| Tambah, ubah | admin satker mana pun, super-admin (keputusan pemilik, K2a) | OCC `If-Match`; **setiap** tulis tercatat di audit dengan nama pengguna, satkernya, dan — untuk ubah — field apa yang berubah dari apa menjadi apa |
| Nonaktifkan | admin satker mana pun | `aktif: false` — tersembunyi dari pemilih, riwayat utuh |
| Hapus permanen | **super-admin saja** | Ditolak bila masih dirujuk di satker mana pun |

Jejak: tiap dokumen membawa `dicatat_oleh {username, kode_satker, pada}` dan
`diubah_oleh {…}`. Field itu **keterangan**, bukan kunci isolasi — jangan
diberi nama `kode_satker`.

Yang **tetap per satker**: aset, BAST, dan semua transaksi. Admin satker A
yang membuka "aset yang dipegang" seorang wakil perusahaan hanya melihat
aset satker A. Cacah yang ditampilkan kepada pengguna selalu ter-scope;
hanya pemeriksaan "masih dirujuk?" sebelum hapus permanen yang lintas satker,
dan pesannya tidak merinci satker lain.

Kode satker milik instansi lain disimpan di `satker_luar.kode_luar`.

**Direktori hanya memuat identitas.** Uji yang dipakai untuk tiap field:
*"kalau dua satker mengisinya berbeda, apakah keduanya benar?"* Nama, nomor
identitas, jabatan, badan dan satkernya — tidak; hanya ada satu yang benar,
maka itu milik direktori bersama. Perjanjian kami dengan mereka, masa
berlakunya, narahubung untuk urusan kami — ya; maka itu **bukan** isi
direktori, melainkan isi transaksi di satker masing-masing. Menaruhnya di
catatan bersama membuat satker B menimpa perjanjian satker A tanpa ada yang
salah mengetik.

### 3.5 Logika murni dipakai bersama; rute luar modul tersendiri

- **Dipakai ulang tanpa disalin:** `pegawai_utils.py`, `organisasi_utils.py`,
  `unit_kerja_utils.py`, dan pembantu di `routes/pegawai.py` yang diimpor
  (`PegawaiIn`, `_bersih`, `_build_pegawai_xlsx`,
  `_baris_dari_unggahan_pegawai`, `_kecilkan_foto_asli`,
  `_jumlah_aset_per_nip`, `KartuIn`).
- **Ditulis baru:** penangan rute luar — orkestrasi tipis.
- **Penjaga kesetaraan** (`test_pegawai_luar_setara.py`): daftar rute luar
  harus sama dengan rute internal dikurangi pengecualian yang tertulis.

Alternatif yang ditolak — merombak `routes/pegawai.py` menjadi inti
berparameter: menghapus duplikasi penangan, tetapi mengubah berkas internal
yang dijaga uji pembaca-sumber (2.5).

### 3.6 Orang luar dikenali lintas modul lewat direktori gabungan

`GET /pegawai` tetap hanya internal. Modul yang ingin memilih atau mengenali
siapa pun memakai lapis baru yang hanya membaca: `direktori_pegawai.py` +
`GET /direktori-pegawai`. Urutan menang bila satu NIP ada di dua tempat:
pejabat → pegawai internal → orang luar.

### 3.7 Pihak ketiga: badan + wakilnya, bukan pegawai

Praktik pemodelan data yang mapan memisahkan **pihak** (orang atau
organisasi) dari **peran** dan **hubungan**-nya: satu pihak bisa berperan
lebih dari satu, dan nama peran melekat pada hubungan, bukan pada orangnya
(rujukan di Bab 12). Untuk pihak ketiga, yang relevan secara hukum bukan
kepegawaiannya, melainkan **badan mana yang ia wakili dan atas dasar apa** —
pengurus yang berwenang mewakili badan, penerima kuasa tertulis, atau
perorangan atas nama sendiri. Maka penyesuaiannya tiga macam:

**a. Field khusus (baru)**

| Tempat | Field | Isi |
|---|---|---|
| `instansi_luar` (pihak ketiga) | `nomor_induk` | NIB badan usaha; NPSN satuan pendidikan; nomor registrasi lain — label mengikuti `jenis` |
| | `npwp` | NPWP badan |
| | `dasar_pendirian_nomor`, `dasar_pendirian_tanggal` | Akta pendirian/pengesahan badan hukum, atau SK izin operasional |
| | `badan_penyelenggara` | Khusus satuan pendidikan swasta: yayasan/badan penyelenggaranya |
| `pegawai_luar` (pihak ketiga) | `kapasitas_bertindak` | `pengurus_berwenang` \| `penerima_kuasa` \| `petugas` \| `diri_sendiri` |
| | `dasar_kewenangan_jenis` | `anggaran_dasar` \| `surat_kuasa` \| `surat_tugas` \| `tidak_ada` |
| | `dasar_kewenangan_nomor`, `dasar_kewenangan_tanggal` | Dokumen yang membuktikan kapasitas itu |

`kapasitas_bertindak` menentukan komparisi di naskah (PGW-10): "bertindak
untuk dan atas nama … berdasarkan …" atau "bertindak untuk diri sendiri".
`petugas` (mis. teknisi) **bukan** pihak yang sah menandatangani atas nama
badan; layar memperingatkannya saat ia dipilih sebagai penanda tangan.

Kapasitas dan dasar kewenangan di direktori adalah **bawaan**: ia mengisi
form BAST, dan di sanalah nilainya **dibekukan** untuk naskah itu. Surat
kuasa bisa berbeda dari satu perjanjian ke perjanjian lain; yang berlaku
secara hukum adalah yang tertulis di naskahnya, bukan yang kebetulan
terakhir disimpan di direktori.

**b. Field lama yang dimanfaatkan ulang (nama field tetap, sebutan berubah)**

| Field | Sebutan internal | Sebutan pihak ketiga |
|---|---|---|
| `nip` | NIP/NIK/NRP | NIK (opsional, K5) |
| `jabatan` | Jabatan | Jabatan pada badan |
| `alamat` | Alamat | Alamat korespondensi |
| `eselon1..5`, `unit_kerja` | Eselon I–V | Tingkat I–V (K9) |

**c. Field lama yang dinonaktifkan** (disembunyikan di layar, dikosongkan
server, tak berkolom di Excel pihak ketiga)

- Khusus ASN: `pangkat_golongan`, `kategori_pegawai`, `jenis_jabatan`,
  `eselon` (teks), `jenis_pelaksana`, `jabatan_pelaksana`, `tmt_jabatan`,
  `tanggal_akhir_jabatan`, `status_pegawai_satker`,
  `status_pegawai_instansi`, `kode_satker_lengkap`, `unit_organisasi`.
- Khusus tenaga satker: `sub_kategori_non_asn`, `jenis_kontrak_non_asn`,
  `perusahaan_penyedia`.
- Data pribadi tanpa keperluan BMN: `tempat_lahir`, `agama`,
  `status_perkawinan`, `pendidikan_terakhir`, `npwp` (pribadi), `nama_bank`,
  `no_rekening`.
- Ahli waris: `ahli_waris_*`, `pemberitahuan_ahli_waris_*` — rezim tuntutan
  ganti kerugian pegawai negeri. PGW-00: tanggung jawab pihak ketiga
  bertumpu pada perjanjian dan PP 27/2014 Ps. 99, bukan rezim TGR pegawai —
  field ini tetap nonaktif (pustaka §2.4d). `status: meninggal` + tanggalnya **tetap ada** karena
  itulah yang memblokir penugasan baru.
- Fakta hubungan dengan satu satker: `nomor_kontrak`, `tgl_mulai_kontrak`,
  `tgl_selesai_kontrak`. Bagi pihak ketiga ini perjanjian dengan satker
  tertentu, bukan identitas orangnya (3.4); tempatnya di BAST dan modul
  Pemanfaatan/Penggunaan. Peringatan "masih memegang aset" untuk pihak
  ketiga karenanya bertumpu pada `status` orangnya dan jangka waktu di
  naskah serah terimanya, bukan pada direktori.

`status_kepegawaian` dipaksa `non_asn` oleh server, sehingga aturan yang
sudah ada untuk Non-ASN — NIK tidak dicetak di blok tanda tangan, tanpa
perkiraan pensiun — berlaku tanpa menyentuh pemanggilnya.

**d. Instansi eksternal: sama dengan internal, tanpa data pribadi**
(keputusan pemilik, K8)

Field, sebutan, struktur unit, dan aturan kepegawaiannya sama persis dengan
internal — termasuk kontrak, yang bagi mereka adalah kontrak kerja pada
instansinya sendiri. Satu-satunya beda: tujuh field pribadi berikut
dinonaktifkan, karena direktori ini terlihat seluruh satker dan tak ada
keperluan BMN atasnya: `tempat_lahir`, `agama`, `status_perkawinan`,
`pendidikan_terakhir`, `npwp`, `nama_bank`, `no_rekening`. Empat field
khusus pihak ketiga (3.7a) juga kosong.

`tanggal_lahir` dan `jenis_kelamin` **tetap ada** di kedua kelompok luar:
keduanya terbaca dari NIP/NIK itu sendiri, dan tanggal lahir dipakai kunci
anti-ganda saat impor.

### 3.8 Ikon per kelompok — satu komponen, di semua layar kecuali persuratan

| Kelompok | Ikon (lucide-react) | Warna | Teks alternatif |
|---|---|---|---|
| Internal | `IdCard` | sky | "Pegawai internal" |
| Instansi eksternal — pusat | `Landmark` | amber | "Pegawai kementerian/lembaga" |
| Instansi eksternal — daerah | `MapPinned` | violet | "Pegawai pemda" |
| Pihak ketiga | `Handshake` | emerald | "Pihak ketiga" |
| Tak terdaftar di master mana pun | *(tanpa ikon)* | — | — |

- Dibedakan **bentuk**, bukan hanya warna; tiap ikon punya nama yang bisa
  dibaca pembaca layar dan tooltip yang bisa diketuk (`TooltipKetuk`). Warna
  saja tidak boleh menjadi satu-satunya pembawa arti.
- **Satu sumber gambar**: `backend/data/ikon_kelompok.json` — untuk tiap
  kelompok: label, teks alternatif, warna, dan gambar SVG-nya. Salinannya di
  `frontend/src/lib/ikonKelompok.json` dijaga uji agar **identik**. Layar
  merendernya lewat `components/pegawai/IkonKelompok.jsx`; Laporan Eksekutif
  merendernya sebagai SVG sebaris dari berkas yang sama. Tak ada berkas lain
  yang memilih ikon/warna kelompok sendiri. Gambar SVG diambil dari paket
  ikon yang sudah dipakai repo (`lucide`), dengan catatan lisensinya.
- **Dari mana kelompoknya diketahui:** (1) salinan `kelompok` pada catatan
  itu sendiri bila ada (BAST, penerima persediaan — ditulis sejak PGW-06);
  (2) selain itu, layar menanyakan **nomor identitas yang sedang tampil** ke
  `POST /direktori-pegawai/kelompok` — bertumpuk, sekali per sekumpulan
  nomor, hasilnya diingat. Tidak pernah ditebak dari nama. Server hanya
  menjawab nomor yang ditanyakan; seluruh isi direktori tidak pernah dikirim
  ke perangkat demi ikon.
- **Luring:** jawaban yang pernah diterima disimpan di perangkat; nomor yang
  belum pernah ditanyakan tampil tanpa ikon dan tak ada yang rusak.
- **Naskah cetak** (keputusan pemilik, K10): **tanpa ikon** — persuratan
  (`PersuratanPage.jsx`, `components/persuratan/*`), BAST, dan seluruh
  PDF/Word/Excel lain, halaman verifikasi publik TTD, dan email. Di sana
  kelompok — bila perlu disebut — ditulis sebagai kata.
  **Satu-satunya pengecualian: Laporan Eksekutif**, yang menampilkan ikon
  kelompok di samping tiap pengguna pada bagian Distribusi Per Pengguna,
  disertai keterangan (legenda) keempat ikon itu.
- Keempat nama ikon sudah dipakai di berkas lain repo ini; periksa
  ketersediaannya pada versi paket terpasang sebelum memakai.

### 3.9 Kebijakan per jenis penerima sebagai data, bukan `if` yang tersebar

Satu modul murni, `backend/kebijakan_penerima.py`, menjawab untuk tiap
**jenis instansi** (5.6): skema apa yang sah, dokumen dasar apa yang wajib
dirujuk, siapa yang layak menandatangani, rezim ganti rugi mana, dan butir
pasal mana yang dipakai. Modul lain **bertanya** kepadanya. Isinya dikunci
PGW-00 (6.6, pustaka §2.4d). Isi awalnya
diturunkan dari tabel 2.9 dan baru dikunci setelah PGW-00.

### 3.10 Pilih kelompok dulu; lalu instansi; lalu satker

**Pintu masuk.** Master Pegawai dibuka pada layar pilih kelompok: tiga
pilihan besar berikon — Pegawai Internal, Pegawai Instansi Eksternal, Pihak
Ketiga — masing-masing dengan cacahnya. Memilih satu langsung memuat daftar
tersaring kelompok itu; tidak ada tombol "terapkan". Pilihan terakhir
diingat di perangkat, jadi kunjungan berikutnya langsung membuka kelompok
yang sama; ketiga pilihan tetap terlihat di kepala halaman untuk berpindah.
Daftar "semua kelompok bercampur" **tidak disediakan** di layar ini.

**Instansi eksternal: pusat atau daerah.** Memilih Instansi Eksternal
memunculkan pilihan kedua — **Pusat (Kementerian/Lembaga)** atau **Daerah
(Pemerintah Provinsi/Kabupaten/Kota)** — juga dengan cacahnya, juga langsung
menyaring, juga diingat, dan masing-masing dengan ikonnya sendiri (K14).

- **Pusat:** kelompok → Pusat → kementerian/lembaga → satker.
- **Daerah:** kelompok → Daerah → **provinsi** → pemprov itu sendiri atau
  salah satu kabupaten/kotanya (→ desanya, bila ada) → perangkat daerah.
  Daftar kabupaten/kota hanya memuat yang berinduk provinsi terpilih.

Sebutan mengikuti tatarannya: pusat memakai "Kementerian/Lembaga" dan
"Satker"; daerah memakai "Pemda" dan "Perangkat Daerah" (K12).

**Pusat atau daerah ditentukan oleh milik siapa instansinya, bukan letak
kantornya** (K13). Kantor vertikal kementerian/lembaga di daerah — kantor
wilayah, kantor pelayanan, Polres, Kodim, kejaksaan negeri, kantor
Kemenag — adalah **satker dari kementerian/lembaganya**, jadi tercatat di
Pusat. Dinas, badan, sekretariat daerah, RSUD, kecamatan, dan kelurahan
adalah **perangkat daerah dari pemdanya**, jadi tercatat di Daerah. Layar
tambah-instansi memuat keterangan ini, karena inilah salah tempat yang
paling mungkin terjadi.

Pemilahan ini bukan sekadar tampilan: skema penyerahan BMN-nya memang
berbeda (2.9) — kepada K/L berupa penggunaan sementara, kepada pemda berupa
pinjam pakai.

**Pemilih di modul lain** (aset, BAST, persediaan, dan seterusnya) memakai
tiga pilihan yang sama sebagai saringan di kepala pemilih, dengan pilihan
pusat/daerah muncul saat Instansi Eksternal dipilih. Bawaannya Internal —
pemakaian tersering dan perilaku hari ini.

**Praktik untuk banyak instansi, masing-masing dengan banyak satker:**

1. **Catat saat dibutuhkan, bukan dimuat semua.** Jangan mengisi direktori
   dengan seluruh K/L, pemda, dan satkernya. Yang dicatat hanya instansi dan
   satker yang orangnya benar-benar berurusan dengan BMN instansi ini.
   Direktori yang kecil dan terpakai lebih mudah dijaga bersih daripada
   salinan separuh benar dari daftar nasional.
2. **Kode resmi sebagai pengenal, nama sebagai cadangan.** Instansi
   pemerintah punya kode resmi (kode bagian anggaran K/L, kode wilayah pemda,
   kode satker). Bila diisi, kode itulah yang menentukan "ini instansi/satker
   yang sama" — bukan ejaan namanya. `instansi_luar.kode_referensi` dan
   `satker_luar.kode_luar` unik bila terisi; `nama_kunci` baru dipakai bila
   kodenya kosong. Kode tidak ditebak dan tidak dibenihkan dari ingatan;
   diketik dari dokumen resmi pihak tersebut.
3. **Cari dulu sebelum menambah.** Form tambah instansi/satker menampilkan
   yang mirip saat mengetik, dan server menolak kembaran dengan menunjuk
   catatan yang sudah ada. Di direktori bersama, kembaran adalah kerusakan
   yang paling cepat menumpuk.
4. **Pencarian dan pemotongan halaman di server.** Daftar instansi, satker,
   dan orang luar dicari dan dipotong halamannya oleh server; layar tidak
   pernah memuat seluruh direktori lalu menyaringnya sendiri. Ini menjaga
   kecepatan saat direktori tumbuh dan mencegah seluruh nomor identitas
   orang luar terkirim ke setiap perangkat.
5. **Selalu tampil bersama induknya.** Di luar lingkup satu instansi, satker
   ditulis "instansi — satker" dan orang ditulis dengan keduanya (3.3
   butir 7). Nama satker saja tidak cukup untuk mengenali.
6. **Nonaktifkan, jangan hapus.** Instansi dilebur, satker dibubarkan, orang
   pindah: catatannya dinonaktifkan supaya hilang dari pemilih tetapi naskah
   lama yang merujuknya tetap terbaca.
7. **Setiap suntingan meninggalkan jejak.** Karena semua admin boleh
   mengubah, jejak audit — siapa, dari satker mana, apa yang berubah —
   adalah satu-satunya alat untuk menelusuri dan memulihkan suntingan yang
   keliru. Riwayat itu dapat dibuka dari catatan yang bersangkutan.

Butir 1–7 adalah praktik umum pengelolaan data induk bersama, dirumuskan
penyusun untuk keadaan repo ini; bukan kutipan dari satu sumber tertentu.

---

## 4. Keputusan yang milik pemilik

| # | Pertanyaan | Bawaan / keputusan | Jawaban pemilik |
|---|---|---|---|
| K1 | BUMN/BUMD masuk kelompok mana? | Pihak ketiga | **Dijawab:** pihak ketiga |
| K2 | Master luar per satker atau se-instansi? | — | **Dijawab:** satu direktori untuk seluruh instansi |
| K2a | Siapa boleh mengubah catatan bersama? | — | **Dijawab:** semua admin, dan tercatat di audit. (Hapus permanen tetap hanya super-admin — bawaan penyusun, belum disanggah) |
| K3 | Orang luar mendapat akses portal BMN Saya? | Tidak | |
| K4 | Tenaga alih daya yang sudah tercatat internal dipindah ke pihak ketiga? | Tidak | |
| K5 | NIK orang pihak ketiga wajib? | Opsional; tanpa nomor ia tak bisa jadi pemegang aset tertaut dan ikonnya tak bisa dicocokkan pada catatan lama | |
| K6 | Urutan modul yang ditautkan ke master instansi (PGW-11) | Pemanfaatan → Penggunaan (PSP) → Pemeliharaan → Pengadaan → Pemindahtanganan → Persediaan | |
| K7 | Orang luar boleh jadi pejabat di Referensi Pejabat? | Tidak | |
| K8 | Data pribadi untuk **instansi eksternal**? | — | **Dijawab:** tidak dikumpulkan (3.7d) |
| K9 | Sebutan tingkat unit pihak ketiga | "Tingkat I–V" | |
| K10 | Ikon di naskah cetak (PDF/Word) dan halaman verifikasi publik? | — | **Dijawab:** tidak, kecuali Laporan Eksekutif — penggunanya diberi ikon |
| K11 | Perorangan/masyarakat dicatat di bawah satu wadah "Masyarakat (Perorangan)"? | Ya (3.3) | |
| K12 | Sebutan untuk daerah | — | **Dijawab:** "Pemda" (dan "Perangkat Daerah" untuk satkernya — bawaan penyusun); nama field tetap |
| K13 | Batas pusat/daerah untuk kasus pinggir | **Rekomendasi penyusun, dipakai sebagai bawaan:** (a) semua lembaga non-kementerian pengguna anggaran negara — lembaga negara, LPNK, lembaga nonstruktural, TNI/Polri — masuk **Pusat** dan digabung dalam satu jenis "Kementerian/Lembaga"; (b) kantor vertikal K/L di daerah dicatat sebagai **satker K/L-nya**, bukan sebagai instansi daerah; (c) pemerintah desa masuk **Daerah**, berinduk kabupaten/kotanya | |
| K14 | Ikon terpisah untuk pusat dan daerah? | — | **Dijawab:** ya — masing-masing punya ikon sendiri (3.8) |
| K15 | Jenjang daerah | — | **Dijawab:** kabupaten/kota ditautkan ke provinsinya. (Desa ditautkan ke kabupaten/kotanya — perluasan penyusun, mengikuti K13c) |

---

## 5. Model data

Semua koleksi di bawah: `id` UUID unik, `version` (OCC), `created_at`,
`updated_at`, `dicatat_oleh`, `diubah_oleh`, `aktif`. **Tanpa `kode_satker`.**

### 5.1 `instansi_luar`

| Field | Aturan |
|---|---|
| `kelompok` | `eksternal` \| `pihak_ketiga`. Tak boleh diubah bila sudah punya satker |
| `jenis` | Lihat 5.6; harus cocok dengan `kelompok`. Menentukan kebijakan (3.9) |
| `tataran` | `pusat` \| `daerah` — **hanya eksternal**, diturunkan server dari `jenis` (5.6), tidak dikirim klien; kosong untuk pihak ketiga |
| `induk_id` | **Hanya daerah.** Kab/kota → id provinsinya (wajib); desa → id kab/kotanya (wajib); provinsi, K/L, dan pihak ketiga → kosong |
| `provinsi_id`, `provinsi_nama`, `kabkota_id`, `kabkota_nama` | Salinan jenjang, diisi server dari `induk_id`; ikut tersalin ke satker dan orangnya; merambat saat induk diganti nama atau dipindah |
| `nama` | Wajib |
| `nama_kunci` | Turunan server: huruf kecil, tanda baca dibuang, spasi tunggal, bentuk badan dinormalkan (`PT. Telkom` = `Telkom, PT`) |
| `kode_referensi` | Kode resmi instansi (kode bagian anggaran K/L, kode wilayah pemda). Opsional, teks bebas; **unik per kelompok bila terisi** dan menjadi pengenal utama (3.10 butir 2) |
| `singkatan`, `alamat`, `kota`, `telepon`, `email` | Opsional — kontak **umum** instansi, bukan narahubung urusan satu satker |
| `peran` | List kode (5.6) — gabungan dari semua satker; petunjuk, bukan pembatas. Peran sesungguhnya ada di tiap transaksi |
| `nomor_induk`, `npwp`, `dasar_pendirian_nomor`, `dasar_pendirian_tanggal`, `badan_penyelenggara` | Hanya pihak ketiga (3.7a); dikosongkan untuk eksternal |
| `wadah` | `true` hanya pada "Masyarakat (Perorangan)" — tak bisa diubah/hapus |

### 5.2 `satker_luar` — padanan `satker`

| Field `satker` internal | Di `satker_luar` |
|---|---|
| `kode_satker` (identitas) | **`kode_luar`** — kode milik satker itu; opsional; teks bebas; **unik per instansi bila terisi**; ditolak bila sama dengan kode satker internal |
| `nama_satker`, `nama_unit_organisasi`, `nama_sub_unit`, `alamat`, `telepon`, `email`, `aktif` | sama |
| `kode_satker_lengkap` | sama (kode lokasi BMN milik mereka; hanya eksternal) |
| `eselon_satker` | sama — puncak pohon unitnya; kosong = 1 |
| setelan kop & laporan (`logo_url`, `judul_laporan`, `penandatangan`, …) | **tidak dibawa** |
| — | tambahan: `instansi_id` (**tak bisa diubah** setelah dibuat), `instansi_nama`, `kelompok`, `tataran`, `jenis`, `provinsi_id`/`provinsi_nama`, `kabkota_id`/`kabkota_nama` (salinan dari instansinya), `nama_kunci` |

### 5.3 `unit_kerja_luar` — bentuk sama dengan `unit_kerja`

`{nama_unit, eselon "1".."5", parent_id, satker_luar_id, sumber}`. Aturan
pohon seluruhnya dari `organisasi_utils`, dengan `akar` = `eselon_satker`
milik satkernya.

### 5.4 `pegawai_luar`

Seluruh field `PegawaiIn`, ditambah:

| Field | Aturan |
|---|---|
| `satker_luar_id` | **Wajib** |
| `kelompok`, `tataran`, `jenis_instansi`, `instansi_id`, `instansi_nama`, `satker_luar_nama`, `provinsi_id`/`provinsi_nama`, `kabkota_id`/`kabkota_nama` | Diisi server dari master; merambat saat instansi/satker/induknya diganti nama atau dipindah |
| `kapasitas_bertindak`, `dasar_kewenangan_jenis`, `dasar_kewenangan_nomor`, `dasar_kewenangan_tanggal` | Hanya pihak ketiga (3.7a); dikosongkan untuk eksternal |

Makna field warisan: `kode_satker` **selalu kosong** di koleksi ini (ia kunci
isolasi internal; jangan diisi); `kode_satker_lengkap` = kode lokasi BMN
satker **mereka**; `eselon1..5` = nama unit pada pohon satker **mereka**.

### 5.5 Indeks, backup, GridFS

```python
for kol in ("instansi_luar", "satker_luar", "unit_kerja_luar", "pegawai_luar"):
    await _idx(db[kol], "id", unique=True)
# induk_id ikut kunci: nama desa berulang antar-kabupaten ("" bila tak berinduk)
await _idx(db.instansi_luar,
           [("kelompok", 1), ("induk_id", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.satker_luar, [("instansi_id", 1), ("nama_kunci", 1)], unique=True)
# kode resmi: unik bila terisi (indeks parsial, seperti NIP di bawah)
await db.instansi_luar.create_index(
    [("kelompok", 1), ("kode_referensi", 1)], unique=True,
    name="unique_kode_instansi_luar",
    partialFilterExpression={"kode_referensi": {"$gt": ""}})
await db.satker_luar.create_index(
    [("instansi_id", 1), ("kode_luar", 1)], unique=True,
    name="unique_kode_satker_luar",
    partialFilterExpression={"kode_luar": {"$gt": ""}})
await _idx(db.unit_kerja_luar, "satker_luar_id")
await _idx(db.pegawai_luar, [("kelompok", 1), ("satker_luar_id", 1), ("nama", 1)])
await _idx(db.instansi_luar, [("kelompok", 1), ("tataran", 1), ("jenis", 1), ("nama", 1)])
await _idx(db.pegawai_luar, [("kelompok", 1), ("tataran", 1), ("nama", 1)])
await _idx(db.instansi_luar, "induk_id")
await _idx(db.instansi_luar, [("provinsi_id", 1), ("jenis", 1), ("nama", 1)])
await _idx(db.pegawai_luar, [("provinsi_id", 1), ("nama", 1)])
# NIP unik se-direktori; string kosong dikecualikan lewat indeks parsial
await db.pegawai_luar.create_index(
    "nip", unique=True, name="unique_nip_luar",
    partialFilterExpression={"nip": {"$gt": ""}})
# kartu: sama dengan pegawai — unik+sparse, jatuh ke non-unik bila gagal
```

- `RESET_KEEP_COLLECTIONS` ditambah keempat koleksi.
- Foto orang luar memakai `metadata.jenis` **`foto_pegawai_luar`** dan
  **`foto_pegawai_luar_asli`**; keduanya ditambahkan ke
  `RESET_KEEP_GRIDFS_JENIS`. Tidak didaftarkan sebagai sumber
  `webp_converter`.
- `ganti_kode_satker` tidak menyentuh koleksi luar (tak ber-`kode_satker`);
  `dicatat_oleh.kode_satker` adalah fakta historis dan dibiarkan.

### 5.6 Kode referensi

```python
KELOMPOK_LUAR = {"eksternal": "Instansi Eksternal", "pihak_ketiga": "Pihak Ketiga"}
TATARAN_EKSTERNAL = {
    "pusat": "Pusat (Kementerian/Lembaga)",
    "daerah": "Daerah (Pemda)",
}
TATARAN_DARI_JENIS = {                       # satu-satunya penentu tataran
    "kementerian_lembaga": "pusat",                                      # K13a
    "pemerintah_provinsi": "daerah", "pemerintah_kabkota": "daerah",
    "pemerintah_desa": "daerah",                                         # K13c
}
INDUK_DAERAH = {                             # jenis → jenis induk yang sah
    "pemerintah_provinsi": None,
    "pemerintah_kabkota": "pemerintah_provinsi",
    "pemerintah_desa": "pemerintah_kabkota",
}
KUNCI_IKON = ("internal", "eksternal_pusat", "eksternal_daerah", "pihak_ketiga")
JENIS_INSTANSI = {
    "eksternal": {
        # mencakup lembaga negara, LPNK, lembaga nonstruktural, TNI/Polri (K13a)
        "kementerian_lembaga": "Kementerian/Lembaga",
        "pemerintah_provinsi": "Pemerintah Provinsi",
        "pemerintah_kabkota": "Pemerintah Kabupaten/Kota",
        "pemerintah_desa": "Pemerintah Desa",
    },
    "pihak_ketiga": {
        "bumn": "Badan Usaha Milik Negara",
        "bumd": "Badan Usaha Milik Daerah",
        "bumdes": "Badan Usaha Milik Desa",
        "badan_usaha_swasta": "Badan Usaha Swasta",
        "satuan_pendidikan_swasta": "Satuan Pendidikan Swasta",
        "koperasi": "Koperasi",
        "yayasan": "Yayasan",
        "badan_hukum_lain": "Badan Hukum/Lembaga Lain (bukan pengguna anggaran)",
        "kelompok_masyarakat": "Kelompok Masyarakat/Ormas",
        "perorangan": "Perorangan",
        "lembaga_internasional": "Pemerintah Negara Lain/Organisasi Internasional",
        "lainnya": "Lainnya",
    },
}
PERAN_INSTANSI = {
    "pengguna_sementara": "Pengguna sementara BMN",
    "peminjam_pakai": "Peminjam pakai",
    "penyewa": "Penyewa",
    "mitra_kerja_sama": "Mitra KSP/BGS-BSG/KSPI/KETUPI",
    "pengoperasi": "Mengoperasikan BMN (pihak lain)",
    "penerima_pemindahtanganan": "Penerima pemindahtanganan",
    "penyedia": "Penyedia barang/jasa",
    "pelaksana_pemeliharaan": "Pelaksana pemeliharaan",
    "pendamping": "Tim pendamping/peneliti",
    "lainnya": "Lainnya",
}
KAPASITAS_BERTINDAK = {
    "pengurus_berwenang": "Pengurus yang berwenang mewakili badan",
    "penerima_kuasa": "Penerima kuasa",
    "petugas": "Petugas/karyawan (bukan wakil badan)",
    "diri_sendiri": "Bertindak untuk diri sendiri",
}
DASAR_KEWENANGAN = {
    "anggaran_dasar": "Anggaran dasar/akta",
    "surat_kuasa": "Surat kuasa",
    "surat_tugas": "Surat tugas/penunjukan",
    "tidak_ada": "Tidak ada",
}
LABEL_TINGKAT = {
    "eksternal_pusat": {"instansi": "Kementerian/Lembaga", "satker": "Satker",
                        "level": "Eselon"},
    "eksternal_daerah": {"instansi": "Pemda",                            # K12
                         "satker": "Perangkat Daerah", "level": "Eselon"},
    "pihak_ketiga": {"instansi": "Badan/Pihak", "satker": "Unit/Cabang",
                     "level": "Tingkat"},
}
```

**Dikunci PGW-00 (2026-11-11).** Perubahan dari usulan: `yayasan_ormas`
dipecah — yayasan adalah badan hukum yang disebut sebagai penyewa (PMK
115/2020 Ps. 10(4) huruf b), sedangkan ormas/perkumpulan tak berbadan hukum
tidak disebut sehingga digabung ke `kelompok_masyarakat`; `badan_hukum_lain`
ditambah untuk PTN-BH dan lembaga/organisasi independen yang bukan pengguna
anggaran, yang disebut tersendiri sebagai pengoperasi BMN (PMK 40/2024 Ps.
28(1) huruf a). Jenis BAST baru dikunci bernama `penyerahan_pihak_luar` dan
`pengembalian_pihak_luar` (belum ada di `JENIS_BAST`). Tidak ada data benih instansi selain
wadah perorangan (3.3) — daftar kode K/L/pemda tidak boleh ditulis dari
ingatan.

### 5.7 Invarian

1. Setiap `pegawai_luar` menunjuk `satker_luar` yang ada; `kelompok`,
   `tataran`, `jenis_instansi`, `instansi_id`, dan salinan jenjangnya selalu
   sama dengan milik satkernya. `induk_id` instansi selalu string (kosong
   bila tak berinduk), tidak pernah `null`.
2. `kelompok == "pihak_ketiga"` ⇒ `status_kepegawaian == "non_asn"` dan
   seluruh field 3.7c kosong. `kelompok == "eksternal"` ⇒ field 3.7a dan
   tujuh field pribadi 3.7d kosong.
3. `jenis_instansi == "perorangan"` ⇒ `kapasitas_bertindak == "diri_sendiri"`
   dan `eselon1..5` kosong.
4. NIP unik se-direktori luar (indeks), dan tidak boleh sama dengan NIP
   pegawai internal **satker mana pun** — ditegakkan di sisi luar. Pesan
   galatnya tidak menyebut nama atau satker pegawai internal itu.
5. Satu kartu tap tidak boleh terdaftar pada dua orang luar, dan pendaftaran
   di sisi luar menolak kartu milik pegawai internal.
6. Tak ada dokumen luar ber-`kode_satker`; tak ada kueri luar yang
   dibungkus scope satker; tak ada kueri aset yang dilepas scope-nya kecuali
   pemeriksaan "masih dirujuk?" sebelum hapus permanen.
7. Tak ada jalur di modul luar yang menulis ke `pegawai`, `unit_kerja`,
   `satker`, atau `assets`.
8. **Penampungan** (3.3): `satker_luar.instansi_id` tidak pernah berubah;
   `instansi_luar.kelompok` tidak berubah setelah punya satker; setiap unit
   kerja luar menunjuk satker yang ada; induk sebuah unit selalu berada di
   satker yang sama.
9. Orang luar hanya dapat dipindah ke satker lain yang **sekelompok**.
   Pindah lintas kelompok ditolak — penyesuaian field-nya berbeda dan akan
   menghapus data tanpa disadari.
10. `satker_luar.kode_luar` tidak pernah sama dengan `satker.kode_satker`
    mana pun; `kode_referensi` dan `kode_luar` unik bila terisi.
11. `tataran` selalu sama dengan `TATARAN_DARI_JENIS[jenis]` untuk eksternal
    dan kosong untuk pihak ketiga, pada instansi, satker, dan orangnya;
    `jenis` instansi yang sudah punya satker tidak bisa diganti ke jenis
    bertataran lain.
12. **Jenjang daerah** (3.3): `induk_id` terisi **jika dan hanya jika**
    `INDUK_DAERAH[jenis]` bukan kosong, dan menunjuk instansi berjenis itu;
    tidak ada lingkaran; `provinsi_id`/`kabkota_id` selalu sama dengan yang
    diturunkan dari rantai induknya, pada pemda, satker, dan orangnya; pemda
    yang masih punya anak tidak bisa dihapus atau diganti jenisnya.

---

## 6. Kontrak API

Semua rute di bawah **baru**. Tak satu pun rute yang ada berubah.

### 6.1 Instansi & satker luar (`backend/routes/organisasi_luar.py`)

| Rute | Penjaga | Catatan |
|---|---|---|
| `GET /luar/referensi` | `require_user` | Semua kode 5.6 + `field_nonaktif` per kelompok + `label_field` (3.7b) + `ikon` (isi `ikon_kelompok.json`) — layar membaca ini, tidak menyalin daftar |
| `GET /luar/instansi?kelompok=&tataran=&jenis=&provinsi_id=&induk_id=&q=&aktif=&page=` | `require_user` | `kelompok` wajib; `tataran` hanya bermakna untuk eksternal. Dicari dan dipotong halamannya di server; + `jumlah_satker`, `jumlah_orang` (agregasi) |
| `GET /luar/riwayat/{jenis}/{id}` | `require_user` | Jejak audit satu catatan (instansi/satker/orang): siapa, satker mana, kapan, field apa berubah |
| `POST /luar/instansi` | `require_admin` | Payload memuat `satker_pertama` (wajib kecuali pemda) dan, untuk kab/kota dan desa, `induk_id`; induk yang salah jenis atau tak ada → 400; 400 bila `nama_kunci` sudah ada — jawaban menyertakan id yang sudah ada agar layar menawarkan "pakai yang ini" |
| `PUT /luar/instansi/{id}` | `require_admin` + `If-Match` | Ganti nama → rambatkan `instansi_nama` (dan `provinsi_nama`/`kabkota_nama` pada pemda di bawahnya). Ganti `induk_id` (pemekaran) → rambatkan salinan jenjang. `kelompok` dan — bila sudah punya satker atau anak — `jenis` tidak bisa diubah |
| `DELETE /luar/instansi/{id}` | `require_super_admin` | 409 bila masih punya satker berorang, masih punya pemda di bawahnya, atau dirujuk transaksi |
| `GET/POST /luar/satker`, `PUT`, `DELETE /luar/satker/{id}` | seperti instansi | `instansi_id` wajib pada daftar dan tidak diterima pada `PUT`. `kode_luar` yang sama dengan kode satker internal → 400. Hapus 409 bila masih berorang/ber-unit |

Tiap tulis ber-`log_audit` dengan `kode_satker=kode_satker_user(user)`, id
catatan di argumen `asset_id` (pola `buat_pegawai`), dan — untuk ubah —
`changes=[{field, from, to}]`, parameter yang sudah disediakan `log_audit`.
Karena audit di sini adalah alat pertanggungjawaban (K2a), panggil dengan
`strict=True`: kegagalan mencatat tidak boleh lewat diam-diam.

`GET /luar/riwayat` membaca `audit_logs` untuk id itu **tanpa** scope satker
— catatannya milik bersama, jadi jejaknya pun terlihat semua satker. Halaman
audit umum tetap ter-scope seperti hari ini.

### 6.2 Unit kerja luar (`backend/routes/unit_kerja_luar.py`)

Cermin `routes/unit_kerja.py`, semua ber-`satker_luar_id` wajib:
`GET /unit-kerja-luar`, `POST`, `PUT /{id}`, `DELETE /{id}`,
`POST /unit-kerja-luar/bangun-dari-pegawai`. Tanpa `cocokkan-lingkup`. Ganti
nama merambat ke `pegawai_luar` **saja** — tidak pernah ke `assets`. Ditolak
400 untuk satker-wadah perorangan.

### 6.3 Orang luar (`backend/routes/pegawai_luar.py`)

Cermin `routes/pegawai.py`. Saringan lewat kueri: `kelompok` (wajib pada
daftar), `instansi_id`, `satker_luar_id`.

| Rute internal | Padanan luar | Catatan |
|---|---|---|
| `GET /pegawai` | `GET /pegawai-luar` | + field 5.4; `info_masa` sama. Beda yang disengaja: menerima `q` dan `page` — dicari dan dipotong halamannya di server (3.10 butir 4) |
| `GET /pegawai/rekap-unit` | `GET /pegawai-luar/rekap-unit` | `satker_luar_id` wajib |
| — | `GET /pegawai-luar/rekap-lingkup?kelompok=&tataran=` | Baru: cacah per tataran (pusat/daerah), per instansi, dan per satker |
| `GET /pegawai/perlu-serah-terima` | padanan | Cacah aset **ter-scope satker pemanggil** |
| `GET /pegawai/{id}/aset` | padanan | Hanya aset satker pemanggil |
| `POST`, `PUT /pegawai…` | `POST`, `PUT /pegawai-luar…` | `require_admin`; `_bersih` + `validate_pegawai`, lalu `sesuaikan_orang_luar` |
| `DELETE /pegawai/{id}` | `DELETE /pegawai-luar/{id}` | `require_super_admin`; admin memakai nonaktifkan |
| template, ekspor, impor | padanan | Ekspor & impor wajib `satker_luar_id` (satu berkas = satu satker); header per kelompok (PGW-04) |
| foto, foto-asli | padanan | `jenis` GridFS berbeda (5.5) |
| kartu daftar/lepas | padanan | Cek silang kartu ke `pegawai` |

### 6.4 Pengecualian kesetaraan (terdaftar di uji kesetaraan)

| Rute internal tanpa padanan luar | Alasan |
|---|---|
| `/pegawai/referensi`, `/pegawai/deteksi-identitas` | Tidak ber-data; layar luar memakai rute yang sama |
| `/pegawai/{id}/sinkron-aset` (+ pratinjau) | Menulis ke `assets` dan membawa isu 2.10 |
| `/pegawai/kartu/identifikasi` | Digantikan identifikasi gabungan |

### 6.5 Direktori gabungan (`backend/direktori_pegawai.py` + rute)

| Rute | Catatan |
|---|---|
| `GET /direktori-pegawai?kelompok=internal\|eksternal\|pihak_ketiga&tataran=&q=&instansi_id=&satker_luar_id=&page=` | Hanya baca; `kelompok` wajib (bawaan pemilih: `internal`). Internal **ter-scope satker pemanggil** (persis `GET /pegawai`); luar se-instansi, hanya yang `aktif`, dicari dan dipotong halamannya di server. Field ringkas: `id`, `ranah`, `kelompok`, `jenis_instansi`, `nama`, `nip`, `jabatan`, `unit_kerja`, `email`, `alamat`, `status`, `status_kepegawaian`, `foto_file_id`, `tataran`, `kunci_ikon`, `instansi_nama`, `provinsi_nama`, `satker_luar_nama`, `kapasitas_bertindak`. Menerima juga `provinsi_id` |
| `POST /direktori-pegawai/kelompok` | Bahan ikon. Badan `{nomor: [...]}` (maks. 500) → `{nomor: kunci_ikon}` (`internal`, `eksternal_pusat`, `eksternal_daerah`, `pihak_ketiga`) hanya untuk nomor yang dikenal. Cakupan sama dengan baris di atas. Ber-batas laju. Server tidak pernah mengembalikan nomor yang tidak ditanyakan |
| `POST /direktori-pegawai/kartu/identifikasi` | Cari di `pegawai` dulu, lalu `pegawai_luar`; batas laju dan audit sama dengan rute internal |

```python
async def cari_orang(scope_internal, nip) -> dict | None      # + "ranah", "kelompok", "kunci_ikon"
async def cari_orang_banyak(scope_internal, nips) -> dict     # {nip: dok}; dua kueri $in
```

`scope_internal` diserahkan pemanggil dan **hanya** dikenakan pada pencarian
di `pegawai`; pencarian di `pegawai_luar` tidak ber-scope.

### 6.6 Kebijakan penerima (`backend/kebijakan_penerima.py`, murni)

```python
def kebijakan(jenis_instansi) -> dict
# {skema_sah: [...], dokumen_dasar_wajib: bool, rezim_ganti_rugi: "...",
#  butir_pasal: "internal"|"antar_pemerintah"|"pihak_ketiga", komparisi: "..."}
def periksa_penyerahan(skema, jenis_instansi, kapasitas, dasar) -> list[str]
```

Dibuka ke layar lewat `GET /luar/referensi`.

**Isi terkunci PGW-00** (sumber per sel: pustaka §2.4d). `skema_sah` hanya
memuat skema yang menyerahkan **penguasaan sementara**; hibah dan
pemindahtanganan lain tetap di modul Pemindahtanganan.

| Jenis | `skema_sah` | Dokumen dasar wajib | `butir_pasal` | Komparisi |
|---|---|---|---|---|
| (pegawai internal) | yang ada hari ini | — | `internal` | — |
| `kementerian_lembaga` | `penggunaan_sementara` | persetujuan Pengelola Barang; ≤ 6 bulan cukup perjanjian antar-Pengguna Barang (PMK 40/2024 Ps. 33(2)) | `antar_pemerintah` | atas nama instansi |
| `pemerintah_provinsi`, `pemerintah_kabkota`, `pemerintah_desa` | `pinjam_pakai` | persetujuan Pengelola Barang + perjanjian pinjam pakai | `antar_pemerintah` | atas nama pemda/pemdes |
| `bumn` | `sewa`, `ksp`, `bgs_bsg`, `kspi`, `dioperasikan_pihak_lain` | persetujuan/penetapan Pengelola Barang + perjanjian | `pihak_ketiga` | atas nama badan + dasar kewenangan |
| `bumd` | `sewa`, `ksp`, `bgs_bsg`, `kspi` | idem | `pihak_ketiga` | idem |
| `bumdes` | `sewa` | idem | `pihak_ketiga` | idem |
| `badan_usaha_swasta` | `sewa`, `ksp`, `bgs_bsg`; `kspi` hanya PT | idem | `pihak_ketiga` | idem |
| `koperasi` | `sewa`, `kspi`, `dioperasikan_pihak_lain` | idem | `pihak_ketiga` | idem |
| `yayasan` | `sewa`, `bgs_bsg` | idem | `pihak_ketiga` | idem |
| `satuan_pendidikan_swasta` | `sewa` (atas nama badan penyelenggara) | idem | `pihak_ketiga` | atas nama **badan penyelenggara** |
| `badan_hukum_lain` | `bgs_bsg`, `dioperasikan_pihak_lain` | idem | `pihak_ketiga` | atas nama badan |
| `kelompok_masyarakat` | — (tidak ada skema penguasaan sementara; hanya hibah) | — | — | — |
| `perorangan` | `sewa` | persetujuan Pengelola Barang + perjanjian sewa | `pihak_ketiga` | untuk diri sendiri |
| `lembaga_internasional` | `dioperasikan_pihak_lain` | penetapan Pengelola Barang + perjanjian | `pihak_ketiga` | atas nama pemerintah/organisasi |
| `lainnya` | — (ditetapkan per kasus; `periksa_penyerahan` mengembalikan peringatan) | — | — | — |

Sel bertanda "mungkin"/"perlu verifikasi" di pustaka **tidak** dimasukkan
ke `skema_sah` (bawaan konservatif) — mis. KSP bagi koperasi/yayasan dan
pengoperasian oleh BUMD/badan usaha swasta. Menambahkannya kelak cukup
dengan mengubah tabel data ini, tanpa menyentuh pemanggil.
`rezim_ganti_rugi` semua penerima luar = `"perjanjian"` (perjanjian/dokumen
dasar + PP 27/2014 Ps. 99); `"tgr_pegawai"` hanya untuk internal.

---

## 7. Peta perubahan

### 7.1 Yang TIDAK berubah

`routes/pegawai.py`, `routes/unit_kerja.py`, `routes/satker.py`,
`portal_auth.py`, `portal_bast.py`, `routes/portal_*.py`,
`webp_converter.py`, koleksi `pegawai`/`unit_kerja`/`satker`, `GET /pegawai`
dan `GET /unit-kerja` beserta bentuk jawabannya, `HEADER_IMPOR`, `const EMPTY`
di `PegawaiPage.jsx`, seluruh modul persuratan.

Akibat yang disengaja: orang luar tidak mendapat akses portal (K3) dan tidak
muncul di pemilih pejabat (K7).

### 7.2 Pembaca backend yang ikut mengenali orang luar (aditif)

| Berkas → fungsi | Yang berubah |
|---|---|
| `shared_utils.py` → `status_kepegawaian_by_nip` | Jatuh ke `pegawai_luar` setelah pejabat dan pegawai |
| → `enforce_pegawai_terdaftar` | Cek "meninggal" dan "terdaftar" mengenali orang luar |
| `penerima_utils.py` → `periksa_penerima`, `snapshot_penerima` | Mengenali orang luar; snapshot + `penerima_kelompok`, `penerima_instansi` |
| `routes/bast.py` → cek PIHAK KESATU meninggal; snapshot pihak | Mengenali orang luar; `PihakIn`/`PjTambahanIn` + `kelompok`, `tataran`, `instansi_nama` (dibekukan) |
| `routes/ttd.py` → dua cek penanda tangan meninggal | Mengenali orang luar |
| `routes/imports.py` → `nip_terdaftar` | Gabungan `distinct` kedua koleksi |
| `routes/penggunaan.py` → `daftar_pemegang` (pengaya) | + `pegawai_master_kelompok`, `pegawai_master_instansi` |
| `routes/reports.py` → `_peta_status_kepegawaian`, Laporan Eksekutif `peg_master` | Mengenali orang luar; pengelompokan tersendiri (PGW-09) |
| `routes/wasdal.py` → pegawai berisiko | Ikut membaca `pegawai_luar` |

### 7.3 Layar yang menampilkan ikon kelompok (`PERMUKAAN_IKON`)

Daftar ini adalah **registry** di `lib/kelompokOrang.js`; ujinya menagih tiap
berkas di sini mengimpor `IkonKelompok` (PGW-08).

| Layar | Tempat ikon |
|---|---|
| `pages/PegawaiPage.jsx` | Tab kelompok; baris daftar |
| `pages/DashboardPage.jsx` + daftar/kartu aset | Kolom/baris pengguna |
| `components/assets/AssetForm.jsx`, `InventoryFieldSheet.jsx`, `BatchEditPanel.jsx` | Isian pengguna; hasil pemilih |
| `components/assets/AssetMapFullView.jsx` | Popup pin (baris pengguna) |
| `components/assets/AuditLogPanel.jsx`, linimasa aset | Nama pemegang lama/baru |
| `pages/PenggunaanPage.jsx`, `components/penggunaan/*` | Rekap pemegang; pihak BAST; PJ tambahan |
| `pages/PersediaanPage.jsx` | Penerima pada transaksi & riwayat |
| `pages/PemeliharaanPage.jsx` | Pelaksana/penerima |
| `pages/TtdPermintaanPage.jsx`, `components/ttd/*` (bagian petugas) | Daftar penanda tangan |
| `pages/ActivitySelectionPage.jsx` | Anggota tim |
| `pages/PemanfaatanPage.jsx`, `PemindahtangananPage.jsx`, `PengadaanPage.jsx` | Di samping mitra/pihak yang tertaut ke `instansi_luar` (PGW-11) |
| `pages/WasdalPage.jsx` | Temuan pemegang berisiko |
| `components/pegawai/KartuTapDialog.jsx` | Hasil tap |
| **Laporan Eksekutif** (`backend/templates/executive_summary.html`) | Tiap pengguna pada Distribusi Per Pengguna + legenda — satu-satunya naskah cetak berikon (K10) |

**Tanpa ikon** (`LARANGAN_IKON`, juga ditagih uji): `pages/PersuratanPage.jsx`,
`components/persuratan/*`, `pages/TtdPublikPage.jsx`, dan seluruh keluaran
backend (PDF/Word/Excel/email) **selain** templat Laporan Eksekutif.

Nama berkas di tabel ini dicocokkan ulang dengan repo saat PGW-08 dimulai;
yang tidak ada dicoret, yang terlewat ditambahkan.

---

## 8. Paket kerja

### Status

| Paket | Isi | Bergantung | Status | PR |
|---|---|---|---|---|
| PGW-00 | Regulasi & kontrak modul | — | **selesai** | #1114 |
| PGW-01 | Fondasi murni | 00 | **selesai** | #1115 |
| PGW-02 | Master instansi & satker luar (backend) | 01 | **selesai** | #1116 |
| PGW-03 | Orang luar (backend) | 02 | **selesai** | #1117 |
| PGW-04 | Impor/ekspor/template orang luar | 03 | **selesai** | #1118 |
| PGW-05 | Unit kerja luar (backend) | 03 | **selesai** | #1119 |
| PGW-06 | Direktori gabungan, penjawab kelompok, pembaca backend | 03 | **selesai** | #1120 |
| PGW-07 | Layar Master Pegawai | 03, 04, 05 | **selesai** | #1121 |
| PGW-08 | Ikon kelompok & pemilih lintas modul | 06 | **selesai** | #1122 (08a + 08b) |
| PGW-09 | Laporan & dokumen | 06 | **selesai** | #1123 |
| PGW-10 | Kebijakan & pasal per jenis penerima | 00, 06, 09 | **kerangka selesai**; butir pasal & form menunggu verifikasi PMK 115/2020 | #1124 (kerangka) |
| PGW-11 | Tautan instansi di modul berpihak-luar | 02, 07 | sebagian — Pemanfaatan | |
| PGW-12 | Data uji & dokumentasi | 07–10 | **selesai** | #1125 |

PGW-04, 05, 06 boleh paralel setelah PGW-03. Sampai PGW-07 ter-merge,
pengguna tidak melihat perubahan apa pun.

---

### PGW-00 — Regulasi & kontrak modul (dokumen saja)

1. Tambah bagian di `docs/PUSTAKA-REGULASI-BMN.md` (dekat §2.4c): definisi
   tiga kelompok dan **matriks jenis penerima × skema** (2.9), dibaca ulang
   pasal demi pasal dari `docs/regulasi/` dan dilengkapi sumber. Yang tak
   terverifikasi ditandai "perlu verifikasi".
2. Pertanyaan yang **wajib** dijawab:
   - Keberlakuan hari ini atas PMK 115/2020, PMK 40/2024, PP 27/2014 jo.
     28/2020, PMK 53/2023 — adakah perubahan sesudah naskah diunduh?
   - Rezim khusus IKN: adakah ketentuan Otorita yang memperluas atau
     mempersempit pihak yang dapat menerima BMN?
   - Sekolah swasta, yayasan, kelompok masyarakat: skema mana yang benar-
     benar tersedia (sewa dengan faktor penyesuai? pengoperasian oleh pihak
     lain? hibah?) — naskah yang terbaca belum menjawab tuntas.
   - Rezim ganti rugi untuk pegawai instansi lain dan untuk pihak ketiga
     (tuntutan ganti kerugian negara vs tanggung jawab menurut perjanjian).
     Menentukan butir risiko di PGW-10 dan nasib field ahli waris (3.7c).
   - Siapa yang sah menandatangani penyerahan BMN kepada pihak di luar
     satker, dan siapa yang sah menerima atas nama badan (kapasitas & dasar
     kewenangan, 3.7a).
   - Batas pengumpulan data pribadi orang luar menurut UU 27/2022 — menguji keputusan K8.
   - Bentuk kode resmi yang dipakai sebagai pengenal: kode bagian anggaran
     K/L, kode satker, dan kode wilayah pemda (apakah kode kab/kota memang
     berawalan kode provinsinya). Sampai terjawab, kode hanya diperiksa
     keunikannya — bukan bentuknya, dan bukan kecocokan awalan dengan
     induknya.
3. Tambah kontrak di `docs/MASTERPLAN-SIKLUS-BMN.md`.
4. Kunci daftar kode 5.6 dan isi `kebijakan_penerima` (6.6).
5. Daftarkan sitasi yang akan tercetak ke `backend/sitasi_regulasi.py`
   dengan status yang jujur; "terverifikasi" menuntut naskahnya di
   `docs/regulasi/` (ditagih `test_sitasi_regulasi.py`).
   **Koreksi saat dikerjakan:** `test_registry_tidak_menyimpan_sitasi_hantu`
   menolak entri yang belum tercetak oleh kode mana pun, jadi pendaftaran
   ikut PR yang mencetaknya (PGW-10). Sitasi utama sudah `teks-primer`.

**Hasil (2026-11-11):** pustaka §2.4d (definisi tiga kelompok, matriks
jenis penerima × skema bersumber pasal, jawaban tiap pertanyaan beserta
keyakinan dan bawaannya), kontrak masterplan §5M, kode 5.6 dan tabel 6.6
terkunci. **Temuan yang menahan PGW-10:** status PMK 115/2020 bertentangan
antarsumber (JDIH berlabel "Dicabut" tanpa pencabut; BPK "Berlaku") — pustaka
§14 butir 26. PGW-01 s.d. PGW-09 tidak terhalang.

**Terima:** matriks ada di pustaka dan bersumber; tiap pertanyaan berjawaban
atau bertanda "perlu verifikasi" dengan bawaan konservatif yang dipakai.

---

### PGW-01 — Fondasi murni

**Berkas baru:** `backend/organisasi_luar_utils.py`,
`backend/tests/unit/test_organisasi_luar_utils.py`.

```python
# kode referensi 5.6
FIELD_PRIBADI_LUAR = ("tempat_lahir", "agama", "status_perkawinan",
                      "pendidikan_terakhir", "npwp", "nama_bank", "no_rekening")
FIELD_NONAKTIF = {"eksternal": FIELD_PRIBADI_LUAR,      # 3.7d
                  "pihak_ketiga": (...)}                # persis daftar 3.7c
FIELD_KHUSUS_PIHAK_KETIGA = ("kapasitas_bertindak", "dasar_kewenangan_jenis",
                             "dasar_kewenangan_nomor", "dasar_kewenangan_tanggal")
FIELD_KHUSUS_BADAN = ("nomor_induk", "npwp", "dasar_pendirian_nomor",
                      "dasar_pendirian_tanggal", "badan_penyelenggara")
LABEL_FIELD = {"pihak_ketiga": {"nip": "NIK", "jabatan": "Jabatan pada badan", ...}}

def nama_kunci(nama) -> str
def tataran_dari_jenis(kelompok, jenis) -> str     # "" utk pihak ketiga
def periksa_jenjang_daerah(doc, induk) -> list[str]   # invarian 12
def salinan_jenjang(doc, induk) -> dict     # provinsi_*/kabkota_* turunan
def kunci_ikon(kelompok, tataran) -> str    # salah satu KUNCI_IKON
def validate_instansi_luar(doc) -> list[str]
def validate_satker_luar(doc) -> list[str]
def bersihkan_instansi_luar(payload) -> dict     # kosongkan FIELD_KHUSUS_BADAN utk eksternal
def bersihkan_satker_luar(payload) -> dict
def sesuaikan_orang_luar(doc, kelompok, jenis_instansi) -> dict
    # eksternal: kosongkan FIELD_KHUSUS_PIHAK_KETIGA + FIELD_NONAKTIF["eksternal"]
    # pihak_ketiga: status_kepegawaian="non_asn"; kosongkan FIELD_NONAKTIF[...]
    # perorangan: kapasitas="diri_sendiri"; eselon1..5 kosong
def validate_orang_luar(doc, kelompok, jenis_instansi) -> list[str]
    # pengurus_berwenang/penerima_kuasa tanpa dasar_kewenangan → peringatan
def periksa_penampungan(satker_lama, satker_baru) -> list[str]
    # pindah satker hanya dalam kelompok yang sama (invarian 9)
def label_unit_orang(doc) -> str
    # internal: unit_kerja; luar: "instansi_nama — satker_luar_nama — unit"
```

**Uji minimum:**
- `nama_kunci("PT. Telkom Indonesia") == nama_kunci("Telkom  Indonesia, PT")`.
- `sesuaikan_orang_luar` eksternal: dokumen penuh keluar sama dengan masuk,
  kecuali tujuh field pribadi dan empat field khusus pihak ketiga kosong;
  `nomor_kontrak`, `pangkat_golongan`, `eselon3` **utuh**.
- Pihak ketiga: `non_asn`; setiap field 3.7c kosong (termasuk
  `nomor_kontrak`); `nama`, `nip`, `jabatan`, `eselon2`, `tanggal_lahir`,
  `tanggal_meninggal` utuh.
- Kesetaraan skema: `set(_bersih(PegawaiIn(nama="x")))` ⊇ gabungan
  `FIELD_NONAKTIF` — salah ketik nama field gagal di sini.
- `periksa_penampungan` menolak pindah ke satker berkelompok lain.
- `tataran_dari_jenis`: tiap jenis eksternal punya tepat satu tataran;
  setiap kunci `JENIS_INSTANSI["eksternal"]` ada di `TATARAN_DARI_JENIS`
  (jenis baru tanpa tataran gagal di sini); pihak ketiga → kosong.
- `periksa_jenjang_daerah`: kab/kota tanpa induk ditolak; kab/kota berinduk
  kab/kota ditolak; provinsi berinduk ditolak; K/L berinduk ditolak; desa
  berinduk kab/kota diterima. `salinan_jenjang` desa memuat kab/kota **dan**
  provinsinya.
- `jenis` yang tak cocok `kelompok` ditolak; perorangan dipaksa
  `diri_sendiri`.

**Terima:** uji lulus; belum ada pemanggil.

**Hasil (2026-11-11):** dibangun sesuai daftar di atas, dengan empat
penyesuaian yang harus diketahui paket berikutnya:
- `nama_kunci` hanya membuang singkatan bentuk usaha (PT, Tbk, Persero, CV,
  UD, Firma). "Koperasi"/"Yayasan" dipertahankan — keduanya pembeda nama yang
  sah, dan `nama_kunci` dipakai indeks unik PGW-02.
- Peringatan dipisah ke `peringatan_orang_luar(doc, kelompok)`;
  `validate_orang_luar` hanya mengembalikan galat yang menolak simpan.
- `periksa_penampungan` juga menolak pindah pusat ↔ daerah (invarian 11).
- `bersihkan_satker_luar(payload, instansi)` menerima dokumen instansi agar
  kelompok/tataran/jenjang selalu diturunkan dari induknya; tambahan
  `jenis_cocok` dan `KAPASITAS_WAKIL_BADAN`.

---

### PGW-02 — Master instansi & satker luar (backend)

**Berkas:** `backend/routes/organisasi_luar.py` (baru), `backend/server.py`,
`backend/indexes.py`, `backend/backup_utils.py`,
`backend/tests/unit/test_organisasi_luar_route.py`,
`backend/tests/unit/test_backup_utils.py`.

Kontrak 6.1 dan tata kelola 3.4. Pembuatan instansi + satker pertama:
sisipkan satker dulu; bila penyisipan instansi gagal, hapus satker itu.
Wadah perorangan dibuat lewat pembantu idempoten `pastikan_wadah_perorangan`.

**Uji minimum** (pola `mongomock_motor` di `test_unit_kerja_route.py`):
- Catatan buatan admin satker A **terlihat** oleh pengguna satker B.
- Admin B dapat mengubahnya; `diubah_oleh.kode_satker == B`; audit tercatat
  dengan satker B dan memuat `changes` field yang berubah (K2a).
- `DELETE` oleh admin → 403; oleh super-admin → berhasil bila tak dirujuk,
  409 bila dirujuk.
- Nama kembar beda tanda baca → 400 dengan id yang sudah ada.
- `POST /luar/instansi` tanpa `satker_pertama` → 400 untuk K/L dan pihak
  ketiga; diterima untuk pemda.
- `PUT` dengan `If-Match` usang → 409.
- Tak satu pun dokumen tersimpan memuat kunci `kode_satker`.
- Wadah perorangan tak bisa diubah/dihapus; pembuatannya idempoten.
- Field khusus badan pada instansi eksternal tersimpan kosong.
- **Tidak tercampur** (3.3): `PUT /luar/satker/{id}` yang mengirim
  `instansi_id` lain → 400 dan dokumen tak berubah; `kelompok` instansi
  yang sudah punya satker tak bisa diubah; daftar satker tanpa
  `instansi_id` → 400; nama satker yang sama diterima di dua instansi
  berbeda dan ditolak di instansi yang sama; `kode_luar` sama dengan kode
  satker internal → 400; `kode_referensi` kembar dalam satu kelompok → 400.
- **Pusat/daerah:** instansi berjenis `pemerintah_kabkota` tersimpan
  `tataran: "daerah"` walau klien mengirim `"pusat"`; daftar dengan
  `tataran=pusat` tidak memuatnya; mengganti jenis instansi yang sudah punya
  satker dari K/L ke pemprov → 400.
- **Jenjang daerah:** kab/kota tanpa `induk_id` → 400; berinduk K/L atau
  kab/kota lain → 400; daftar dengan `provinsi_id=X` memuat pemprov X,
  kab/kotanya, dan desa di bawahnya — tidak memuat milik provinsi lain;
  mengganti nama provinsi merambat ke `provinsi_nama` kab/kota, satker, dan
  orangnya; memindah kab/kota ke provinsi lain memperbarui salinan itu dan
  tercatat di audit; menghapus provinsi yang masih punya kab/kota → 409.
- `GET /luar/riwayat` menampilkan suntingan admin B kepada pengguna satker A.
- Daftar instansi dipotong halaman; `q` mencari pada nama, singkatan, kode;
  daftar tanpa `kelompok` → 400.

**Hasil (2026-11-11):** rute `routes/organisasi_luar.py` terdaftar di
`server.py`; indeks 5.5 untuk keempat koleksi; keempat koleksi dan dua jenis
foto luar masuk `RESET_KEEP_*`. Penyesuaian:
- `organisasi_luar_utils` kini **membuang** kunci `kode_satker` dari satker
  dan orang luar (invarian 6), bukan menyimpannya kosong.
- Jenis instansi tidak bisa diganti sama sekali bila sudah punya satker atau
  pemda di bawahnya (lebih ketat dari "ke tataran lain" — penggantian jenis
  juga mengubah aturan induknya).
- POST instansi berjenis `perorangan` ditolak — perorangan selalu di wadah.
- `GET /luar/referensi` mengembalikan `kunci_ikon`; isi `ikon_kelompok.json`
  menyusul di PGW-08.
- Belum ada `Idempotency-Key`: catatan direktori bukan dokumen resmi, dan
  kirim ulang ditolak oleh pemeriksa nama kembar dengan menunjuk id yang ada.
- "Dirujuk transaksi" pada hapus belum diperiksa (rujukannya baru lahir di
  PGW-10/11); hapus instansi kini 409 bila masih punya orang atau pemda di
  bawahnya, dan satker kosong ikut terhapus.

---

### PGW-03 — Orang luar (backend)

**Berkas:** `backend/routes/pegawai_luar.py` (baru), `backend/server.py`,
`backend/indexes.py`, `backend/backup_utils.py` (jenis GridFS),
`backend/tests/unit/test_pegawai_luar_route.py`,
`backend/tests/unit/test_pegawai_luar_setara.py`, dan penambahan
`routes/pegawai_luar.py` ke daftar berkas di `test_gerbang_media.py` dan
`test_penjaga_senyap.py`.

1. `PegawaiLuarIn(PegawaiIn)` + `satker_luar_id` + empat field khusus.
2. Pembantu `_stempel(doc, satker)`: mengisi `satker_luar_id`,
   `satker_luar_nama`, `instansi_id`, `instansi_nama`, `kelompok`,
   `tataran`, `jenis_instansi` dari master; memaksa `kode_satker = ""`.
   Salinan jenjang (`provinsi_*`, `kabkota_*`) ikut diisi. Satker tidak
   ada/nonaktif → 400. Nilai `kelompok`/`tataran`/`instansi_id` kiriman
   klien **diabaikan**. Pada ubah, satker tujuan yang berkelompok lain →
   400 (`periksa_penampungan`).
3. Buat/ubah: `_bersih` → `validate_pegawai` + `validate_orang_luar` →
   `sesuaikan_orang_luar` → `_stempel` → cek NIP (invarian 4) → tulis
   ber-OCC → `log_audit`. `DuplicateKeyError` pada indeks NIP → 400.
4. Daftar: `kelompok` wajib; `q` dan `page` di server; `info_masa_pegawai`
   yang sama; hanya `aktif` kecuali diminta. Tiap baris membawa
   `instansi_nama` dan `satker_luar_nama`.
5. Hapus (`require_super_admin`): hitung rujukan **lintas satker** — aset
   (`pengguna_nip`), BAST (`pihak_*.pegawai_id`), tautan modul. Dirujuk → 409
   "masih dirujuk; nonaktifkan saja", tanpa rincian satker.
6. Foto: `jenis` `foto_pegawai_luar`/`foto_pegawai_luar_asli`; wajib lewat
   `tulis_media`.
7. Kartu: daftar/lepas seperti internal + cek silang ke `db.pegawai`.
8. `perlu-serah-terima`, `{id}/aset`: `_jumlah_aset_per_nip(user)` dan
   `scope_query_aset(user, …)` — cacah hanya milik satker pemanggil.
9. Tidak ada pemanggilan `portal_auth`.

**Uji kesetaraan** (`test_pegawai_luar_setara.py`):
- Himpunan akhiran rute luar == rute internal − `PENGECUALIAN_SETARA` (6.4)
  + `rekap-lingkup`. Dibaca dari `router.routes`.
- `PegawaiLuarIn.model_fields` ⊇ `PegawaiIn.model_fields`.
- Sumber modul luar memuat `validate_pegawai(`, `_bersih(`,
  `info_masa_pegawai(`, `tulis_media(`.
- **Larangan tulis:** modul luar tidak cocok dengan
  `db\.(pegawai|unit_kerja|satker|assets)\.(insert|update|delete|bulk_write|replace)`.
- **Larangan scope:** modul luar tidak memanggil `scope_query_field_satker`.
- **Larangan balik:** `routes/pegawai.py`, `routes/unit_kerja.py`,
  `routes/satker.py` tidak memuat kata `_luar`.

**Uji rute minimum:** tiap invarian 5.7 satu uji; pihak ketiga dengan
`status_kepegawaian: "pns"` dan `agama` terisi → tersimpan `non_asn`, agama
kosong; eksternal dengan payload penuh tersimpan sama dengan `_bersih`-nya
kecuali tujuh field pribadi; payload yang mengirim `kelompok` atau
`instansi_id` berbeda dari satkernya → tersimpan milik satkernya; pindah ke
satker berkelompok lain → 400; orang di perangkat daerah sebuah kabupaten
tersimpan dengan `provinsi_nama` kabupaten itu; NIP milik pegawai internal
satker **lain** → 400 dan pesannya tidak memuat
nama orang itu; dua satker memegang aset atas orang yang sama → masing-masing
hanya melihat asetnya.

**Terima:** uji lama `test_pegawai_*`, `test_portal_*`, `test_unit_kerja_*`
lulus tanpa disunting; `git diff --stat` tidak memuat `routes/pegawai.py`.

**Hasil (2026-11-11):** `routes/pegawai_luar.py` + uji rute dan uji
kesetaraan; indeks NIP unik parsial dan kartu unik+sparse. Penyesuaian:
- Urutan proses: `_bersih` → `sesuaikan_orang_luar` → `_stempel` →
  `validate_orang_luar` (yang menjalankan `validate_pegawai` internal).
  Menyesuaikan lebih dulu agar field yang toh dikosongkan tidak menolak simpan.
- `kode_satker` **dibuang**, bukan dipaksa kosong (invarian 6, sejalan PGW-02).
- Daftar memakai `semua_status=true` untuk memuat yang tidak aktif, dan tiap
  baris membawa `label_unit` ("instansi — satker — unit").
- Templat/ekspor/impor menunggu PGW-04: uji kesetaraan memuat himpunan
  sementara `MENUNGGU_PGW04` yang harus dihapus di paket itu.
- Penjaga "tak memanggil portal/scope" memeriksa impor dan pemanggilan, bukan
  sebutan di docstring.

---

### PGW-04 — Impor/ekspor/template orang luar

**Berkas:** `backend/organisasi_luar_utils.py` (header),
`backend/routes/pegawai_luar.py`,
`backend/tests/unit/test_pegawai_luar_impor.py`, penambahan
`("pegawai_luar.py", "_baris_dari_unggahan_pegawai")` ke
`test_cpu_sinkron_di_thread.py`.

1. `pegawai_utils.py` tidak disunting. Di modul luar:
   ```python
   def header_impor_luar(kelompok) -> list
   # eksternal    → HEADER_IMPOR tanpa tujuh kolom field pribadi (3.7d)
   # pihak_ketiga → HEADER_IMPOR tanpa kolom field 3.7c, dengan sebutan
   #                3.7b, + "Kapasitas Bertindak", "Dasar Kewenangan",
   #                "Nomor Dasar Kewenangan", "Tgl Dasar Kewenangan"
   def baris_impor_luar(raw, kelompok) -> (doc, peringatan)
   def baris_ekspor_luar(doc, kelompok) -> list
   ```
   `baris_impor_luar` memetakan sebutan pihak ketiga kembali ke header baku
   lalu memanggil `baris_impor_ke_pegawai` — satu penormal, bukan dua.
2. Ekspor: `satker_luar_id` wajib — satu berkas = satu satker, dan nama
   berkasnya memuat instansi serta satkernya. Kedua kelompok memakai header
   dan baris dari langkah 1. `_build_pegawai_xlsx` mengeraskan
   `HEADER_IMPOR`, jadi modul luar memakai pembangun kecilnya sendiri dengan
   gaya yang sama — jangan menyunting yang internal.
3. Impor: `satker_luar_id` wajib (`Form`). Parsing di thread. Per baris:
   `baris_impor_luar` → validasi (keluhan NIP disaring, seperti internal) →
   `sesuaikan_orang_luar` → `kunci_dedup_pegawai` → `gabung_baris_pegawai`.
   - Pembanding dimuat **sekali**: orang luar di satker itu, seluruh NIP
     `pegawai_luar`, seluruh NIP `pegawai`. NIP yang sudah ada di internal
     atau di satker luar lain → baris dilewati dengan catatan (tanpa nama
     pegawai internal).
   - Saringan dedup selalu memuat `satker_luar_id`.
   - `$set` hanya field yang dipasok baris; sisanya dan stempel lingkup di
     `$setOnInsert`.

**Uji minimum:** pulang-pergi untuk eksternal dan pihak ketiga; header
eksternal = `HEADER_IMPOR` dikurangi tepat tujuh kolom pribadi dengan
urutan sisanya sama; header pihak ketiga tidak memuat satu pun kolom field
3.7c; impor ke satker X tidak mengubah satu pun dokumen satker lain; impor
ulang tidak menggandakan; berkas berisi NIP pegawai internal → internal tak
berubah; ekspor/impor tanpa
`satker_luar_id` → 400.

**Hasil (2026-11-11):** `GET /pegawai-luar/template-impor?kelompok=`,
`GET /pegawai-luar/export-xlsx?satker_luar_id=`, `POST /pegawai-luar/impor`
(form `satker_luar_id`). Penyesuaian:
- Tambahan `field_dipasok_luar(raw)` — padanan `field_dipasok_baris` yang
  mengenali sebutan pihak ketiga dan empat kolom khusus.
- Urutan per baris sama dengan PGW-03: sesuaikan → stempel → validasi.
- Stempel lingkup (`_FIELD_TURUNAN`) tidak pernah masuk `$set`; satker
  sudah dikunci oleh saringan dedup.
- Templat memerlukan `kelompok` (header-nya berbeda per kelompok).
- `MENUNGGU_PGW04` dihapus dari uji kesetaraan — himpunan rute luar kini
  persis internal − 6.4 + `rekap-lingkup`.

---

### PGW-05 — Unit kerja luar (backend)

**Berkas:** `backend/routes/unit_kerja_luar.py` (baru), `backend/server.py`,
`backend/indexes.py`, `backend/tests/unit/test_unit_kerja_luar_route.py`.

Kontrak 6.2. Aturan pohon dari `organisasi_utils`; derivasi dari
`unit_kerja_utils.unit_dari_pegawai`; `akar` dari
`satker_luar.eselon_satker`.

**Uji minimum:** kasus `test_unit_kerja_route.py` yang relevan, disalin
untuk lingkup luar; ganti nama unit di satker luar X tidak mengubah orang di
satker luar Y yang unitnya senama; `pegawai`, `unit_kerja`, `assets` **tidak
berubah sama sekali** sesudah setiap operasi; satker-wadah perorangan
menolak semua operasi unit.

**Hasil (2026-11-11):** `routes/unit_kerja_luar.py` terdaftar; indeks
tambahan `(satker_luar_id, parent_id, nama_unit)`. Penyesuaian:
- Hapus unit hanya super-admin — tata kelola 3.4 untuk direktori bersama
  (internal: admin). Ganti nama/pindah induk tetap untuk semua admin.
- Induk dari satker lain ditolak 400 (aturan penampungan 3).
- `bangun-dari-pegawai` menerima `satker_luar_id` di badan permintaan.
- Audit ketat (`strict=True`) dengan aksi `luar_unit_*`.

---

### PGW-06 — Direktori gabungan, penjawab kelompok, pembaca backend

**Berkas:** `backend/direktori_pegawai.py`,
`backend/routes/direktori_pegawai.py`, `backend/server.py`, sembilan titik di
7.2, `backend/tests/unit/test_direktori_pegawai.py`, perluasan
`test_penerima_persediaan.py`.

1. `cari_orang`, `cari_orang_banyak` — urutan menang: internal dulu.
2. `GET /direktori-pegawai` (dicari dan dipotong halamannya di server),
   `POST /direktori-pegawai/kelompok`, identifikasi kartu gabungan.
3. Sunting sembilan pembaca, **satu komit per berkas**, masing-masing dengan
   uji "orang luar terdaftar kini dikenali" dan uji "perilaku untuk orang
   internal tidak berubah".
4. `enforce_pegawai_terdaftar`: hari ini tanpa scope satker; pertahankan
   semantik itu.

**Uji minimum:** penjawab kelompok untuk pengguna satker A mengenali nomor
pegawai internal A dan orang luar aktif, **tidak** mengenali nomor pegawai
internal B, dan tidak pernah mengembalikan nomor yang tidak ditanyakan;
lebih dari 500 nomor → 400; NIP yang ada di internal dan luar → kelompok
internal; direktori tanpa `kelompok` → 400; hasil luar selalu membawa
`instansi_nama` dan `satker_luar_nama`.

**Hasil (2026-11-11):** `direktori_pegawai.py` + `routes/direktori_pegawai.py`;
pembaca 7.2 diubah satu komit per berkas (shared_utils, penerima_utils,
bast, ttd, imports, penggunaan, reports, wasdal) ditambah perluasan uji
penerima persediaan. Penyesuaian:
- **Laporan Eksekutif `peg_master` belum disentuh** — mengikutkan orang luar
  ke pembagi eselon satker akan menaruh mereka di bawah unit yang salah;
  pengelompokan tersendiri dikerjakan PGW-09. Yang diubah di `reports.py`
  baru `_peta_status_kepegawaian`.
- BAST: `kelompok`/`tataran`/`instansi_nama` pihak diisi server lewat NIP
  (`_bekukan_kelompok`), bukan dari kiriman klien.
- `cari_orang` menerima `database` opsional (dipakai `penerima_utils` yang
  menerima `db` sebagai argumen).
- Temuan saat mengerjakan: cek rujukan hapus orang luar (PGW-03) mencari
  `pj_tambahan.pegawai_id`, padahal BAST menyimpan
  `penanggung_jawab_tambahan` — diperbaiki di PR ini.

---

### PGW-07 — Layar Master Pegawai

**Berkas:** `frontend/src/pages/PegawaiPage.jsx`,
`frontend/src/lib/ranahPegawai.js` (+ uji),
`frontend/src/components/pegawai/PilihKelompok.jsx`,
`frontend/src/components/pegawai/BilahLingkupLuar.jsx`,
`frontend/src/components/pegawai/KelolaOrganisasiLuar.jsx`,
`frontend/src/pages/__tests__/PegawaiKelompok.test.jsx`.

1. `lib/ranahPegawai.js` (murni): tiga objek ranah — jalur API
   (`/pegawai` | `/pegawai-luar`, `/unit-kerja` | `/unit-kerja-luar`),
   pembuat parameter lingkup (`kelompok`, `tataran`, `provinsi_id`,
   `instansi_id`, `satker_luar_id`), dan `EMPTY_PIHAK_KETIGA` (empat field
   khusus).
   Sebutan dan daftar field nonaktif dibaca dari `GET /luar/referensi`.
2. Ganti 22 literal `${API}/pegawai` dan 5 literal `${API}/unit-kerja` di
   `PegawaiPage.jsx` dengan jalur dari ranah aktif. Untuk ranah internal
   hasilnya string yang sama persis.
3. **Pintu masuk pilih kelompok** (3.10), `PilihKelompok.jsx`: tiga pilihan
   besar berikon dengan cacahnya; memilih Instansi Eksternal memunculkan
   pilihan kedua **Pusat / Daerah** (`data-testid="pegawai-tataran-<kunci>"`)
   yang berperilaku sama — langsung menyaring, diingat, dan tampil sebagai
   bilah kedua di kepala halaman. Sebutan instansi/satker mengikuti
   `label_tingkat` tataran aktif. Belum ada pilihan tersimpan → hanya layar
   ini yang tampil dan **belum ada daftar yang dimuat**. Memilih satu →
   daftar kelompok itu langsung dimuat, tanpa tombol "terapkan". Pilihan
   disimpan di perangkat (baca/tulis dalam try/catch; tanpa simpanan,
   layar pilih yang tampil). Sesudahnya ketiga pilihan menjadi bilah di
   kepala halaman. `data-testid="pegawai-kelompok-<kunci>"`; tinggi ≥ 44px
   di ≤ 1023px; ranah dan lingkup masuk deps efek muat ulang. Tidak ada
   pilihan "semua".
4. **Bilah lingkup** (tab luar): instansi → satker, dicari di server, dengan
   cacah dari `rekap-lingkup`, saringan `jenis` (di tataran Daerah:
   Provinsi · Kabupaten/Kota · Desa), tombol "Kelola". Di tataran Daerah
   pemilih instansinya bertingkat: **provinsi dulu**, lalu pemprov itu atau
   kab/kotanya (lalu desanya); mengganti provinsi mengosongkan pilihan di
   bawahnya. Form tambah kab/kota meminta provinsinya dan menawarkan
   mencatat provinsi yang belum ada. Daftar instansi hanya memuat tataran
   terpilih; mengganti tataran mengosongkan instansi dan satker. Form
   tambah instansi membatasi pilihan `jenis` pada tataran aktif dan memuat
   keterangan batas pusat/daerah (3.10, K13). Daftar satker hanya memuat
   satker instansi terpilih; **mengganti instansi mengosongkan pilihan
   satker**; mengganti kelompok mengosongkan semuanya.
   Tombol Tambah, Impor, Ekspor, Struktur Organisasi, Kelola Unit nonaktif
   sampai satu satker dipilih (dengan keterangan). Di atas daftar selalu
   tertulis lingkup yang sedang dilihat: "Kementerian X — Sekretariat".
5. `KelolaOrganisasiLuar.jsx` — komponen level modul, dua tingkat (instansi
   → satker), dengan jenjang provinsi → kab/kota → desa di tataran Daerah.
   Saat
   mengetik nama, tampilkan yang mirip dari direktori ("sudah ada — pakai
   yang ini") **sebelum** simpan: direktori bersama cepat kotor oleh
   kembaran. Form badan pihak ketiga memuat field 3.7a dengan label
   `nomor_induk` mengikuti jenis. Hapus permanen hanya tampak bagi
   super-admin; yang lain melihat "Nonaktifkan".
6. **Form orang.** `EMPTY` tidak berubah. Kepala form menuliskan instansi
   dan satker tempat orang itu dicatat; keduanya tidak bisa diketik, hanya
   berasal dari lingkup aktif. Eksternal: form sama dengan internal
   dikurangi tujuh field pribadi (3.7d). Pihak ketiga: field 3.7c tidak dirender; sebutan 3.7b; Status Kepegawaian
   terkunci Non-ASN; bagian baru "Kapasitas & Dasar Kewenangan". Perorangan:
   bagian unit tidak dirender, kapasitas terkunci "diri sendiri".
7. Karena direktori bersama, kepala tab luar memuat keterangan satu baris:
   "Direktori ini dipakai bersama seluruh satker." Rincian tiap catatan
   punya tautan "Riwayat perubahan" (`GET /luar/riwayat`) yang menyebut
   siapa mengubah apa, dari satker mana.
8. Tab luar: tanpa "Sinkron aset"; tanpa jam ahli waris.
9. Daftar dirender dua kali (kartu HP dan tabel desktop) — ubah keduanya.
10. `hover:bg-muted`; uji terang dan gelap; jangan memperkecil tombol.

**Uji minimum (Jest):**
- **Regresi internal:** himpunan URL yang dipanggil tab internal sama dengan
  sebelum paket (daftar URL dibekukan di uji).
- Tab pihak ketiga tidak merender field agama, pangkat, rekening; merender
  Kapasitas Bertindak.
- Tab eksternal tidak merender agama dan rekening; tetap merender pangkat
  dan kontrak.
- Tanpa pilihan tersimpan: layar pilih kelompok tampil dan tak satu pun
  daftar pegawai diminta ke server. Dengan pilihan tersimpan: kelompok itu
  langsung dimuat.
- Mengganti instansi mengosongkan satker terpilih; daftar satker hanya
  berisi satker instansi itu.
- Memilih Instansi Eksternal menampilkan pilihan Pusat/Daerah; memilih
  Daerah meminta `tataran=daerah` ke server dan memakai sebutan "Perangkat
  Daerah"; berpindah ke Pusat mengosongkan instansi terpilih.
- Di Daerah: memilih provinsi meminta `provinsi_id` ke server dan hanya
  kab/kota provinsi itu yang ditawarkan; kab/kota tampil bersama nama
  provinsinya.
- Tanpa satker terpilih, tombol Tambah nonaktif.
- Tombol hapus permanen tidak ada untuk admin biasa.
- `PegawaiAkarEselon.test.jsx` dan backend `test_pegawai_cakupan_ekspor.py`
  lulus tanpa disunting.

**Terima:** `yarn lint`; `CI=true yarn test --watchAll=false`;
`CI=false yarn build`; periksa manual HP dan desktop, terang dan gelap.


**Hasil (2026-11-11):** `lib/ranahPegawai.js` (+ uji), `PilihKelompok.jsx`,
`BilahLingkupLuar.jsx`, `KelolaOrganisasiLuar.jsx`, `PegawaiPage.jsx`, dan
`PegawaiKelompok.test.jsx`. Penyesuaian:
- **Kontradiksi spesifikasi diselesaikan dengan prop.** Butir 3 meminta
  "tanpa pilihan tersimpan → hanya layar pilih, tanpa daftar", sedangkan
  `PegawaiAkarEselon.test.jsx` (wajib lulus tanpa disunting) merender halaman
  tanpa pilihan tersimpan dan langsung menekan Tambah. Keduanya tak mungkin
  sekaligus benar pada perilaku bawaan yang sama. Maka gerbang dipasang lewat
  prop `wajibPilihKelompok` yang diberikan `App.js`; tanpa prop itu halaman
  langsung membuka ranah internal (perilaku lama). Produksi memakai gerbang.
- Jalur internal sengaja dibiarkan sebagai literal lama di cabang internal
  (bukan dirakit dari ranah) — himpunan URL internal dibekukan di uji dan
  tetap empat GET yang sama. `/pegawai/referensi` dan
  `/pegawai/deteksi-identitas` dipakai ketiga ranah (tak ada padanan luar);
  sinkron aset hanya internal.
- Cacah di layar pilih: kelompok luar dari `rekap-lingkup`; **cacah internal
  tidak ditampilkan** karena satu-satunya sumbernya adalah daftar `/pegawai`,
  yang justru dilarang dimuat di layar pilih.
- Rute baru `POST /luar/wadah-perorangan` (admin): pembantu
  `pastikan_wadah_perorangan` (PGW-02) ternyata tak dipanggil dari rute mana
  pun, sehingga pilihan Perorangan tak terjangkau dari layar.
- Daftar orang luar dimuat maks. 200 per lingkup (batas server), dicari di
  server; kepala halaman menyebut "N dari total" bila terpotong.
- Kelola Unit di form orang luar hanya aktif bila satker orang itu sama
  dengan satker di bilah lingkup (master unit yang dimuat milik satker itu).
- Label `nomor_induk` per jenis badan didefinisikan di layar
  (`LABEL_NOMOR_INDUK`) — referensi server belum memuatnya.
- Belum: periksa manual HP/desktop terang/gelap di peramban sungguhan.

---

### PGW-08 — Ikon kelompok & pemilih lintas modul

Boleh dipecah: 08a (komponen + penjawab kelompok + aset + BAST), 08b (layar
lain).

**Berkas inti:** `frontend/src/components/pegawai/IkonKelompok.jsx`,
`frontend/src/lib/kelompokOrang.js` (+ uji),
`frontend/src/lib/ikonKelompok.json`,
`frontend/src/hooks/useKelompokOrang.js`,
`frontend/src/lib/__tests__/permukaanIkon.test.js`.

1. `lib/kelompokOrang.js`: membaca `ikonKelompok.json` (gambar, warna, teks
   alternatif — salinan identik `backend/data/ikon_kelompok.json`),
   `PERMUKAAN_IKON`, `LARANGAN_IKON`, `kelompokDari(catatan, jawaban)` —
   salinan pada catatan menang atas jawaban server.
2. `IkonKelompok`: prop `kunciIkon` atau `nomor`; `ukuran`; `denganLabel`.
   Empat ikon, satu per `KUNCI_IKON`; eksternal pusat dan daerah berbeda
   (K14). `role="img"` + `aria-label`; tooltip lewat `TooltipKetuk`; `min-w-0
   min-h-0` supaya aturan tap-target global tidak membengkakkannya di dalam
   baris. Kelompok tak dikenal → tidak merender apa pun.
3. `useKelompokOrang`: mengumpulkan nomor identitas yang sedang tampil,
   menanyakannya ke `POST /direktori-pegawai/kelompok` **sekali per
   tumpukan** (ditunda sebentar, tanpa nomor kembar, maks. 500), dan
   mengingat jawabannya — termasuk "tak dikenal" — di memori dan di
   perangkat untuk luring (baca/tulis dalam try/catch; halaman harus tetap
   benar tanpa simpanan itu). Satu penampung dibagi semua layar — jangan
   bertanya per baris.
4. Pemilih orang di `AssetForm.jsx`, `PilihPegawaiBast.jsx` +
   `PenggunaanPage.jsx`, `PersediaanPage.jsx` + `lib/penerimaPersediaan.js`,
   `PemeliharaanPage.jsx`, `TtdPermintaanPage.jsx`, dan tim
   peneliti/pendukung di `ActivitySelectionPage.jsx` (tim inti/pembantu
   tetap `/pegawai`; `dari_pihak` terisi nama instansi) berpindah ke
   `GET /direktori-pegawai`
   dengan tiga pilihan kelompok di kepala pemilih (bawaan Internal), pilihan
   pusat/daerah saat Instansi Eksternal dipilih, dan pencarian di server;
   hasil menampilkan ikon, tulisan "Pusat"/"Daerah" untuk eksternal,
   instansi, dan satkernya. `KartuTapDialog.jsx` memakai identifikasi
   gabungan. Peringatan "belum terdaftar" di form aset bertanya ke penjawab
   kelompok, bukan ke daftar yang termuat. `pihakDariPegawai`: untuk orang luar `alamat` = alamat orangnya, jatuh ke
   "instansi — satker". Memilih orang ber-kapasitas `petugas` sebagai pihak
   BAST/penanda tangan memunculkan peringatan lunak.
5. Pasang `IkonKelompok` di tiap layar `PERMUKAAN_IKON` (7.3).
   - Di dalam `FullCameraSheet` tetap elemen native.
   - Daftar aset: jangan menambah permintaan jaringan per baris; nomor yang
     tampil ditanyakan bersama lewat `useKelompokOrang`.
   - `PejabatPage.jsx` dan `PortalPemegangPanel.jsx` tetap memuat `/pegawai`.
6. Uji `permukaanIkon.test.js` (pembaca-sumber): tiap berkas di
   `PERMUKAAN_IKON` mengimpor `IkonKelompok`; tak satu pun berkas di
   `LARANGAN_IKON` mengimpornya; tak ada berkas selain `kelompokOrang.js`
   yang memetakan kelompok → gambar ikon; `ikonKelompok.json` di frontend
   sama byte demi byte dengan `backend/data/ikon_kelompok.json`.

**Uji minimum:** ikon punya nama terakses yang berbeda per kelompok; nomor
tak dikenal → tak ada ikon; penjawab kelompok gagal → layar tetap tampil;
seratus baris dengan sepuluh nomor berbeda → satu permintaan; lima
berkas uji Jest yang me-mock URL `/pegawai` diperbarui bila berkasnya
disentuh.

**Terima:** empat ikon terbedakan dalam skala abu-abu (bentuknya, bukan
warnanya); periksa terang/gelap, HP/desktop; halaman Persuratan tanpa ikon.


**Hasil 08a (2026-11-11):** `backend/data/ikon_kelompok.json` (dibangkitkan
dari ikon lucide-react 0.507.0, ISC) dan salinannya
`frontend/src/lib/ikonKelompok.json`; `lib/kelompokOrang.js`,
`IkonKelompok.jsx`, `hooks/useKelompokOrang.js`, `CariOrangLuar.jsx`; pemilih
pengguna di `AssetForm.jsx`, pihak BAST di `PilihPegawaiBast.jsx` +
`PenggunaanPage.jsx`, identifikasi kartu gabungan di `KartuTapDialog.jsx`.
Nama berkas 7.3 dicocokkan ulang: semuanya ada. Penyesuaian:
- **Ranah internal pemilih tetap memakai daftar `/pegawai` yang sudah
  dimuat**; hanya eksternal/pihak ketiga yang dicari di
  `GET /direktori-pegawai`. Alasan: daftar internal satu satker kecil dan
  sudah termuat (tetap bisa dicari tanpa jaringan sesudahnya), peringatan
  "pegawai tertaut tidak tersedia" bergantung padanya, dan lima uji yang
  me-mock `/pegawai` tetap sah. Peringatan "belum terdaftar" di form aset
  kini bertanya ke penjawab kelompok (NIP ditunda 500 ms).
- Pihak BAST orang luar: `pegawai_id` = id direktori luar (pengaman hapus
  orang luar menghitung rujukan lewat id ini); akses BMN Saya tetap hanya
  internal karena server mencocokkan NIP ke Master Pegawai satker.
- `PilihKelompok.jsx` (PGW-07) kini memakai `IkonKelompok` — sebelumnya
  memilih ikon/warnanya sendiri, melanggar "satu sumber".
- `IkonKelompok` punya mode `hiasan` untuk di dalam tombol (tanpa tooltip
  dan tanpa fokus, nama kelompok sebagai teks pembaca layar) — mencegah
  elemen interaktif bersarang.
- Rekap pemegang (`routes/penggunaan.py`) menambah
  `pegawai_master_kunci_ikon` (dengan tataran) supaya pusat/daerah tak
  tertukar.
- **Temuan & perbaikan:** pengaman hapus orang luar (PGW-03) mencari
  `pihak_kesatu.pegawai_id`, padahal BAST menyimpan `pihak_pertama` — kini
  `pihak_pertama`, dan juga dicocokkan lewat NIP.
- `PERMUKAAN_IKON` memuat yang sudah terpasang; sisanya di
  `PERMUKAAN_IKON_MENYUSUL` (08b/11) dan uji menagih keduanya tercatat.
- Belum: periksa skala abu-abu, terang/gelap, HP/desktop di peramban.


**Hasil 08b (2026-11-11):** `TombolOrangLuar.jsx` — pintu ke direktori orang
luar dari pemilih yang sudah ada — dipasang di Persediaan (penerima tunggal
& massal), Pemeliharaan (pelaksana & pihak BAPP), TTD (penanda tangan), dan
tim peneliti/pendukung kegiatan (`dari_satker`/`dari_pihak` terisi
instansinya). Ikon di daftar & kartu aset, field sheet, edit massal, popup
peta, jejak audit (`pengguna_nip`), riwayat SPPB, baris penanda tangan, dan
temuan Wasdal. Penyesuaian:
- Registry: daftar/kartu aset dirender `VirtualizedAssetTable.jsx` dan
  `AssetGalleryCard.jsx` — `DashboardPage.jsx` sendiri tak menampilkan
  pengguna, jadi dicoret dari registry. Pemanfaatan, Pemindahtanganan, dan
  Pengadaan tetap di `PERMUKAAN_IKON_MENYUSUL` untuk PGW-11.
- Popup peta dibangun Leaflet sebagai DOM mentah, bukan React: memakai
  `svgIkonKelompok` dari `kelompokOrang.js` (sumber gambar sama); uji
  permukaan menerima impor itu sebagai pengganti `IkonKelompok`.
- `IkonKelompok` dengan `nomor` menunda pertanyaan 400 ms selama nomornya
  diketik (jawaban tersimpan tetap tampil seketika) — tanpa ini isian NIP
  mengirim satu permintaan per ketukan, padahal batasnya 60/menit.
- Pelaksana pemeliharaan tercatat sebagai teks tanpa NIP, jadi ikonnya hanya
  tampil selama form terbuka; daftar pemeliharaan tetap tanpa ikon.
- Snapshot penerima persediaan menambah `penerima_tataran` (pusat ≠ daerah).
- Belum: periksa skala abu-abu, terang/gelap, HP/desktop di peramban.

---

### PGW-09 — Laporan & dokumen

1. **Tanpa ikon** di seluruh keluaran (K10) — BAST, daftar pemegang, laporan
   lain, Excel. Kelompok ditulis sebagai kata hanya bila menambah
   keterangan. **Kecuali Laporan Eksekutif** (butir 2).
2. **Laporan Eksekutif — Distribusi Per Pengguna**
   (`backend/templates/executive_summary.html`, `routes/reports.py` sekitar
   `peg_master`, `report_utils.distribusi_pengguna`,
   `laporan_jenjang.baris_hierarki_pengguna`):
   - Tiap baris pengguna yang terdaftar mendapat **ikon kelompoknya**,
     dirender sebagai SVG sebaris dari `backend/data/ikon_kelompok.json`
     dengan `<title>` berisi teks alternatifnya. Pengguna tak terdaftar
     tetap berlabel "(belum terdaftar)" tanpa ikon.
   - Satu baris **keterangan ikon** (legenda) di atas tabel, supaya laporan
     yang dicetak hitam-putih tetap terbaca.
   - Pastikan penyusun PDF laporan ini merender SVG sebaris pada templat
     itu (uji render nyata, bukan hanya HTML-nya); bila tidak, pakai gambar
     yang sama sebagai data-URI.
   - Pengguna luar membawa jalur eselon organisasi lain — jangan dilebur ke
     pohon satker sendiri. Pembagi tersendiri sesudah pengguna internal:
     "Instansi Eksternal — Pusat" → K/L → satker; "Instansi Eksternal —
     Daerah" → provinsi → pemda → perangkat daerah; lalu "Pihak Ketiga" → badan
     → unit. Urutan dan isi baris pengguna internal tidak berubah selain
     ikonnya.
3. **Rekap pemegang / daftar per pemegang PDF:** kolom unit memakai
   `label_unit_orang`.
4. **Wasdal:** temuan "pemegang berisiko" menyebut kelompok + instansi.
   Untuk pihak ketiga temuan bertumpu pada `status` orangnya, karena field
   kontraknya nonaktif (3.7c).
5. Aturan blok tanda tangan tidak berubah: tetap `baris_identitas_ttd`.

**Uji:** `test_laporan_eksekutif_pengguna_jenjang.py` diperluas; total tidak
berubah; laporan yang seluruh penggunanya internal menghasilkan baris yang
sama dengan sebelum paket selain ikon dan legendanya; tiap ikon di HTML
punya `<title>`; tak ada templat lain di `backend/templates/` yang memuat
gambar ikon kelompok. Smoke-render PDF dengan harness FakeDB.


**Hasil (2026-11-11):** `backend/ikon_kelompok.py` (SVG sebaris + `<title>`
dari `data/ikon_kelompok.json`); Laporan Eksekutif — ikon di tiap baris
pengguna terdaftar, satu baris "Keterangan ikon" di atas tabel, dan pembagi
pengguna luar sesudah internal (`laporan_jenjang.baris_hierarki_pengguna_luar`);
`distribusi_pengguna` membawa kelompok/instansi; daftar pemegang PDF/Word &
PDF per pemegang menyebut instansi orang luar (`label_unit_orang`); temuan
Wasdal menyebut kelompok + instansi. Penyesuaian:
- **SVG sebaris diuji dirender nyata** (WeasyPrint → pypdfium2: keempat warna
  ikon tergambar di halaman Distribusi Per Pengguna) — data-URI tak perlu.
- Potret baris laporan seluruh-internal dari kode sebelum paket dibekukan di
  uji; sesudah paket identik selain ikon & legenda.
- Tinggi legenda (`laporan_kolom.TINGGI_LEGENDA_IKON`) dan lebar ikon
  sesudah nama ikut dihitung penghitung halaman — tanpa itu lembar bisa
  meluber.
- Batang grafik pengguna luar ditandai per kelompok: kedalaman daun Daerah
  satu jenjang lebih dalam daripada Pusat/Pihak Ketiga.
- Daftar pemegang tak punya kolom unit; instansi orang luar ditulis di
  bawah jabatannya (baris internal tak berubah).
- Temuan Wasdal untuk orang luar yang meninggal **tanpa jam 3 tahun ahli
  waris** (rezim TGR pegawai negeri; PGW-00) — sebelumnya ikut terlampir.
- Kop jenjang tabel ("Eselon I › … › Pengguna") tetap menyebut jenjang
  internal; bagian luar berlabel lewat baris pembaginya sendiri.

---

### PGW-10 — Kebijakan & pasal per jenis penerima

**Prasyarat keras:** PGW-00 selesai; sitasi terdaftar. Tanpa itu paket ini
hanya boleh membangun kerangka dan uji, **bukan** teks pasal.

**Berkas:** `backend/kebijakan_penerima.py` (baru), `backend/bast_pasal.py`,
`backend/routes/bast.py`, `backend/sitasi_regulasi.py`,
`frontend/src/pages/PenggunaanPage.jsx` (form BAST), uji-ujinya.

1. `kebijakan_penerima.py` (6.6) — isi dari matriks PGW-00. Bentuk awalnya:

   | Jenis penerima | Skema sah | Dokumen dasar | Butir pasal |
   |---|---|---|---|
   | pegawai internal | penggunaan (yang ada) | — | `internal` (tak berubah) |
   | `kementerian_lembaga` | penggunaan sementara | persetujuan Pengelola Barang | `antar_pemerintah` |
   | `pemerintah_provinsi`, `_kabkota`, `_desa` | pinjam pakai | persetujuan + perjanjian | `antar_pemerintah` |
   | `bumn`, `bumd`, `bumdes`, `badan_usaha_swasta` | sewa; KSP; BGS/BSG; KSPI; KETUPI; dioperasikan pihak lain | persetujuan + perjanjian | `pihak_ketiga` |
   | `perorangan` | sewa | persetujuan + perjanjian | `pihak_ketiga` |
   | jenis lainnya | **lihat tabel terkunci 6.6** | **lihat 6.6** | `pihak_ketiga` |

2. **BAST kepada penerima luar adalah berita acara penyerahan FISIK yang
   melaksanakan dokumen dasar**, bukan dasar hukum itu sendiri.
   - Jenis BAST baru (dikunci PGW-00): `penyerahan_pihak_luar` dan
     `pengembalian_pihak_luar`. Jenis lama tidak diubah.
   - Wajib: `skema`, nomor & tanggal dokumen dasar, jangka waktu. Tanpa itu
     → 400 dengan pesan yang menyebut dokumen apa yang kurang.
   - `periksa_penyerahan` menolak kombinasi yang tak sah (mis. pinjam pakai
     kepada badan usaha) dengan pesan yang menyebut skema yang tersedia.
3. **Komparisi** dari `kapasitas_bertindak`: pegawai instansi lain — "…
   dalam hal ini bertindak untuk dan atas nama [instansi]"; wakil badan —
   "… bertindak untuk dan atas nama [badan] berdasarkan [dasar kewenangan]
   nomor … tanggal …"; perorangan — "… bertindak untuk diri sendiri".
   Kapasitas `petugas` sebagai PIHAK KEDUA → ditolak; yang menandatangani
   harus pengurus berwenang atau penerima kuasa.
4. **Butir pasal** di `bast_pasal.py` — fungsi baru, yang lama tidak
   disentuh: `butir_waktu`/`butir_risiko` tetap untuk internal; tambahkan
   himpunan `antar_pemerintah` dan `pihak_ketiga`. Yang **tidak boleh**
   terbawa ke penerima luar: surat tugas atasan, hukuman disiplin, dan
   tuntutan ganti kerugian pegawai — kecuali PGW-00 menyatakan berlaku.
   Isi minimum (rumusannya dari PGW-00): rujukan dokumen dasar; peruntukan
   sesuai skema; larangan mengalihkan; pemeliharaan dan pengamanan oleh
   penerima; tanggung jawab atas kerusakan/kehilangan menurut rezimnya;
   pengembalian saat jangka waktu berakhir atau dokumen dasar dicabut.
   Batas 2 halaman tetap berlaku.
5. **Portal/otomasi amanah:** BAST penerima luar tidak memicu
   `portal_bast` (tetap tinjauan petugas). Pemegang pada aset diperbarui
   lewat alur tinjauan yang ada.
6. Form BAST: memilih penerima berikon menyetel jenis yang tersedia dan
   menampilkan isian dokumen dasar; penerima internal → form persis hari ini.

**Uji:** tiap baris matriks satu uji lulus + satu uji tolak; BAST internal
menghasilkan pasal yang **identik** dengan sebelum paket (bekukan keluaran);
`test_sitasi_regulasi.py` lulus; naskah tetap ≤ 2 halaman pada kasus uji
terpanjang; tak ada kata "hukuman disiplin" di naskah penerima luar.


**Hasil kerangka (2026-11-11):** prasyarat keras belum terpenuhi — status
PMK 115/2020 masih bertentangan antarsumber (pustaka §2.4d, §14 butir 26)
dan belum ada yang membuka riwayat dokumennya di JDIH. Sesuai aturan paket,
yang dibangun hanya kerangka dan uji:
- `backend/kebijakan_penerima.py`: matriks terkunci 6.6, `kebijakan`,
  `periksa_penyerahan` (skema tak sah menyebut skema yang tersedia; dokumen
  dasar & jangka waktu yang kurang disebut satu per satu; `petugas` ditolak
  sebagai PIHAK KEDUA), `catatan_penyerahan` (KSPI hanya PT), `komparisi`
  (kalimat identitas, tanpa rujukan peraturan). Dibuka ke layar lewat
  `GET /luar/referensi` beserta `naskah_luar_siap`.
- `POST /bast` jenis `penyerahan_pihak_luar`/`pengembalian_pihak_luar`:
  PIHAK KEDUA wajib dari direktori orang luar (jenis instansi & kapasitas
  dibaca server); galat kelengkapan → 400; lolos → **409 gerbang**
  (`NASKAH_LUAR_SIAP = False`) karena tanpa butir pasal khusus naskahnya akan
  memakai pasal internal. `JENIS_BAST` lama tidak diubah. Otomasi BMN Saya
  tidak dipicu untuk jenis luar.
- **Belum** (menunggu verifikasi): butir pasal `antar_pemerintah` dan
  `pihak_ketiga` di `bast_pasal.py`, sitasi, dan form BAST (butir 6). Saat
  diverifikasi: tulis butirnya, setel `NASKAH_LUAR_SIAP = True`, tambahkan
  jenis luar ke form — uji gerbang di `test_kebijakan_penerima.py` menunjuk
  tempat yang harus diubah.

---

### PGW-11 — Tautan instansi di modul berpihak-luar (opsional, satu PR per modul)

Urutan K6. Pola aditif: kolom teks yang ada (`mitra`, `pihak`, `penyedia`, …)
**tetap disimpan** sebagai snapshot; tambah field opsional
`<kolom>_instansi_id`; layar memakai masukan teks ber-datalist dari
`GET /luar/instansi` dan menampilkan ikon kelompok; tanpa backfill. Modul
Pemanfaatan dan Penggunaan (PSP) memanggil `periksa_penyerahan` sebagai
**peringatan lunak** — keputusan sahnya tetap pada persetujuan Pengelola.

**Hasil Pemanfaatan (2026-11-12):** field opsional `mitra_instansi_id` di
perjanjian dan usulan; server menyalin snapshot `mitra_kelompok`,
`mitra_tataran`, `mitra_jenis_instansi` dari direktori (id tak dikenal → 400;
mitra yang dibuat tanpa tautan tetap sah). Usulan perpanjangan mewarisi
tautan perjanjian induknya; usulan yang menjadi perjanjian membawa tautannya.
Teks `mitra` tetap disimpan apa adanya. Layar: `IsianInstansiLuar` (teks
ber-datalist dari `GET /luar/instansi` eksternal + pihak ketiga; memilih
saran menautkan, mengubah teks melepas tautan) dan ikon kelompok di baris
usulan & register.
Penyimpangan dari rencana: yang dipanggil bukan `periksa_penyerahan` (itu
memeriksa orang penerima BAST), melainkan fungsi baru
`kebijakan_penerima.periksa_skema(skema, jenis_instansi)` — mencocokkan
bentuk pemanfaatan dengan skema yang lazim untuk jenis mitra. Hasilnya
dikembalikan sebagai `peringatan_kebijakan` dan ditampilkan sebagai toast
peringatan; **tidak pernah menolak simpan**. Mitra nonaktif di direktori juga
diberi peringatan. Isi tabel skema per jenis mitra masih menunggu verifikasi
PMK 115/2020 yang sama dengan PGW-10 — sampai itu, anggap peringatannya
petunjuk, bukan rujukan hukum.
Modul berikutnya menurut K6: Penggunaan (PSP) → Pemeliharaan → Pengadaan →
Pemindahtanganan → Persediaan.

---

### PGW-12 — Data uji & dokumentasi

- `backend/scripts/synthdata/generator.py`: pembangkit instansi, satker, dan
  orang luar; perbarui `test_synthdata_generator.py` dan skill
  `aman-testdata`.
- `README.md`, `frontend/src/pages/InfoPage.jsx`, `frontend/src/lib/bmnModules.js`.
- `.claude/skills/aman-dev/SKILL.md`: baris "Peta repo" untuk modul luar;
  catat keempat koleksi luar sebagai **sengaja bersama** (keputusan pemilik,
  tanggal, rujukan dokumen ini) agar sapuan isolasi berikutnya tidak
  men-scope-nya; aturan "ikon kelompok hanya lewat `IkonKelompok`".
- `CHANGELOG.md`: tiap PR mengisi entrinya. Penomoran mengikuti **kepala
  CHANGELOG.md** (pada baseline: nomor entri = nomor PR + 9).


**Hasil (2026-11-11):** `generate_organisasi_luar` (+ `--kind luar` di CLI) —
K/L, pemprov → kab/kota → desa, badan pihak ketiga, dan wadah perorangan,
lewat fungsi murni yang sama dengan rute dan lolos validatornya; tanpa
`kode_satker`, tanpa kode resmi tebakan. Skill `aman-dev`: baris peta repo
modul luar & ikon, catatan **koleksi luar sengaja bersama**, aturan ikon
hanya lewat `IkonKelompok`/`svgIkonKelompok`. Skill `aman-testdata`, README,
InfoPage, dan fitur modul Penggunaan di `bmnModules.js` diperbarui.
Catatan: daftar fitur modul selalu bercentang hijau, jadi BAST penerima luar
yang masih tertahan (PGW-10) **tidak** dicantumkan di sana.

---

### Ditunda (butuh keputusan pemilik tersendiri)

| Kode | Isi | Kenapa ditunda |
|---|---|---|
| X1 | FK `pengguna_pegawai_id` pada aset | Menyentuh registry field aset dan antrean offline |
| X3 | Portal BMN Saya untuk orang luar | Email di luar kendali instansi |
| X4 | Perbaikan `pengguna_melekat_ke` (2.10) | Isu lama |
| X5 | Pindah ranah internal ↔ luar dengan `id` tetap | Jarang; perlu aturan untuk BAST/portal yang merujuk `id` |
| X6 | Refaktor inti bersama rute pegawai (3.5) | Mengubah berkas internal |
| X7 | Spesimen TTD untuk orang luar | Belum ada kebutuhan yang disebut |
| X8 | Otomasi amanah BAST untuk penerima luar | Menyentuh `portal_bast` |

---

## 9. Jebakan khusus fitur ini

1. **Dua aturan cakupan hidup berdampingan.** Direktori luar bersama; aset
   per satker. Kesalahan yang paling mungkin: memakai kueri aset tanpa scope
   saat menghitung "aset yang dipegang" orang luar, sehingga satker A melihat
   jumlah aset satker B.
2. **Jenis GridFS foto.** `jenis: "foto_pegawai"` dianggap milik
   `db.pegawai` oleh pengonversi WebP. Pakai `foto_pegawai_luar`.
3. **Perambatan nama unit luar tidak boleh menyentuh `assets`.**
4. **Jangan men-scope koleksi luar.** `scope_query_field_satker` pada
   dokumen tanpa `kode_satker` tampak tak berpengaruh, lalu memecah direktori
   begitu seseorang "merapikan" dengan menambah stempel. Uji PGW-03
   melarangnya.
5. **Direktori bersama mudah berkembaran.** Tanpa pencarian-saat-mengetik
   dan `nama_kunci`, tiap satker mencatat "Kementerian X" versinya sendiri.
6. **Pesan galat adalah kebocoran.** "NIP sudah dipakai pegawai internal"
   tidak boleh menyebut nama atau satkernya.
7. **Kelompok ditanyakan bertumpuk, bukan per baris** — dan server hanya
   menjawab nomor yang ditanyakan. Bertanya per baris mengubah satu layar
   menjadi ribuan permintaan; mengirim seluruh direktori ke perangkat
   menyebarkan nomor identitas semua orang luar ke setiap pengguna.
8. **Ikon bukan pengganti teks.** Tanpa nama terakses dan bentuk yang
   berbeda, pembaca layar dan pengguna buta warna tidak mendapat apa-apa.
9. **Satu orang di dua master.** Sisi luar menolak NIP milik internal;
   sisi internal tidak diubah. Bila kelak NIP yang sama masuk internal,
   pencarian mengembalikan yang internal.
10. **Impor adalah jalur tulis yang melewati form.** `sesuaikan_orang_luar`
    dan stempel wajib dipanggil per baris.
11. **Jangan menambah ekspor multi-satker.** Berkasnya tampak bisa diimpor,
    padahal impor menuang semua baris ke satu satker.
12. **`validate_pegawai` di impor menyaring pesan yang memuat "NIP".** Pesan
    baru yang bukan tentang NIP jangan memuat kata itu.
13. **Teks pasal tanpa sitasi terdaftar akan menggagalkan
    `test_sitasi_regulasi.py`** — dan memang harus begitu.

---

## 10. Verifikasi

### Tiap paket

Pasang dulu `pip install -r backend/requirements-dev.txt` bila
`pytest`/`mongomock_motor` belum ada.

```bash
cd backend && python -m compileall -q . -x 'venv|__pycache__'
python -m pytest tests/unit -q
cd ../frontend && yarn lint
CI=true yarn test --watchAll=false
CI=false yarn build
git diff --stat origin/main -- backend/routes/pegawai.py \
    backend/routes/unit_kerja.py backend/routes/satker.py   # harus kosong
```

### Uji regresi kunci — harus lulus TANPA disunting di semua paket

`test_pegawai_utils.py`, `test_pegawai_impor_dedup.py`,
`test_pegawai_cakupan_ekspor.py`, `test_portal_*.py`,
`test_unit_kerja_*.py`, `test_satker_*.py`. Yang boleh **ditambah barisnya**:
daftar berkas di `test_gerbang_media.py`, `test_penjaga_senyap.py`,
`test_cpu_sinkron_di_thread.py`, `test_backup_utils.py`.

### Uji terima akhir (setelah PGW-10, di lingkungan uji — bukan produksi)

0. Membuka Master Pegawai pertama kali → layar pilih kelompok; memilih satu
   langsung menampilkan daftar kelompok itu; membuka lagi → kelompok yang
   sama langsung tampil. Memilih Instansi Eksternal → pilihan Pusat/Daerah;
   daftar Pusat tidak memuat satu pun pemda, daftar Daerah tidak memuat
   satu pun K/L.
1. Tab internal: tambah, ubah, impor, ekspor — sama dengan sebelum fitur ini.
2. Admin satker A membuat "Kementerian X" + satker, dan "PT Z" + unit.
   Admin satker B langsung melihat keduanya dan tidak bisa menghapusnya.
3. Mengetik "PT. Z" saat menambah badan → ditawari yang sudah ada.
4. Form pihak ketiga: tanpa agama/pangkat/rekening; ada Kapasitas & Dasar
   Kewenangan. Form eksternal: seperti internal tanpa agama/rekening.
5. Ekspor satu satker luar → ubah satu sel → impor → hanya sel itu berubah.
6. Di daftar aset, pengguna internal, eksternal, dan pihak ketiga tampil
   dengan ikon berbeda — eksternal pusat dan eksternal daerah pun berbeda;
   pengguna tak terdaftar tanpa ikon.
7. Halaman Persuratan dan PDF BAST: tanpa ikon. Laporan Eksekutif: tiap
   pengguna terdaftar berikon, ada legendanya.
8. Satker A dan B masing-masing menyerahkan aset ke orang luar yang sama →
   masing-masing hanya melihat aset miliknya pada orang itu.
9. BAST "pinjam pakai" kepada badan usaha → ditolak dengan skema yang
   tersedia. BAST penyerahan kepada pemda tanpa nomor perjanjian → ditolak.
10. BAST kepada wakil badan: komparisi memuat dasar kewenangannya; blok
    tanda tangan nama saja; tak ada klausul hukuman disiplin.
11. BAST kepada pegawai internal: naskah identik dengan sebelum fitur ini.
12. Pemilih pejabat dan panel portal tidak menampilkan orang luar.
13. Tidak tercampur: dua instansi masing-masing punya satker "Sekretariat"
    — keduanya tampil dengan nama instansinya; memilih instansi pertama
    hanya menawarkan satkernya sendiri; orang yang ditambahkan di sana
    tidak muncul di instansi kedua; ganti nama unit di satu satker tidak
    mengubah satker lain.
14. Admin B mengubah jabatan seseorang yang dicatat admin A → "Riwayat
    perubahan" pada catatan itu menyebut admin B, satkernya, dan nilai
    lama–baru.
15. Daerah: memilih Provinsi X hanya menawarkan pemprov X dan kab/kotanya;
    mencatat kabupaten tanpa provinsi ditolak; kabupaten tampil sebagai
    "Kab. Y, Prov. X"; mengganti nama provinsi langsung terlihat pada
    kab/kota dan orang-orangnya.
16. Polres atau kantor wilayah sebuah kementerian dicatat sebagai satker di
    bawah K/L-nya (Pusat) dan tampil berikon pusat; dinas kabupaten dicatat
    sebagai perangkat daerah (Daerah) dan tampil berikon daerah.

### Definisi selesai

CI hijau · terdeploy · UI Indonesia · CHANGELOG terisi · status Bab 8
diperbarui · tanpa uji lama yang dilonggarkan · tiga berkas rute internal
tanpa diff.

---

## 11. Risiko dan yang belum terverifikasi

| # | Risiko / ketidakpastian | Keyakinan | Mitigasi |
|---|---|---|---|
| R1 | Naskah serah terima kepada pihak ketiga dibuat tanpa dasar hukum yang benar (mis. disebut "pinjam pakai") | Tinggi bahwa naskah di repo membatasi pinjam pakai pada pemda/pemdes; sedang atas keberlakuannya hari ini | PGW-00 lalu PGW-10; `periksa_penyerahan`; sitasi terdaftar |
| R2 | Skema untuk sekolah swasta, yayasan, kelompok masyarakat belum jelas | **Rendah — belum diriset** | PGW-00; sampai itu, jenis-jenis ini bisa dicatat tetapi BAST penyerahannya ditahan |
| R3 | Direktori bersama rusak oleh suntingan satker lain atau kembaran | Sedang | Audit ketat dengan satker pengubah + riwayat per catatan; hapus hanya super-admin; kode resmi dan pencarian-saat-mengetik |
| R4 | Data pribadi orang luar terlihat seluruh satker | Sedang | Field pribadi dinonaktifkan untuk kedua kelompok luar; daftar dicari di server; penjawab kelompok hanya menjawab nomor yang ditanyakan |
| R5 | Penangan rute luar menyimpang dari internal seiring waktu | Tinggi bahwa ini harga desain koleksi sejajar | Uji kesetaraan; logika murni dipakai bersama |
| R6 | Ikon tak muncul pada catatan lama tanpa nomor identitas | Tinggi (sifat desain) | Disebut terang; tak pernah menebak dari nama |
| R7 | `PegawaiPage.jsx` (1.954 baris) sulit disunting aman | Tinggi | Penggantian jalur mekanis + uji regresi URL |
| R8 | Daftar `PERMUKAAN_IKON` tidak lengkap | Sedang — disusun dari nama berkas, belum dari penelusuran tiap layar | Dicocokkan ulang di awal PGW-08; uji menagih yang terdaftar |
| R9 | Kewenangan mewakili badan (pengurus, kuasa) dirumuskan keliru | Sedang — dari sumber sekunder | PGW-00; rumusan komparisi dikunci di sana |
| R10 | Temuan 2.10 ternyata disengaja | Sedang | Tidak diubah; hanya dilaporkan |

Dokumen ini tidak mengutip nomor pasal selain yang terbaca di
`docs/regulasi/` dan kode repo. Klaim regulasi baru harus melalui PGW-00.

---

## 12. Rujukan praktik (sekunder — bukan dasar hukum)

Dipakai untuk bentuk desain, bukan untuk teks naskah. Semuanya perlu dibaca
ulang oleh pelaksana sebelum dijadikan pegangan.

- Pemodelan pihak (orang/organisasi terpisah dari peran dan hubungan):
  [A Universal Person and Organization Data Model — TDAN](https://tdan.com/?p=5014);
  [Party and global address book — Microsoft Learn](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/data-entities/dual-write/party-gab).
- Ikon tidak boleh hanya dibedakan warna:
  [Understanding SC 1.4.1 Use of Color — W3C](https://w3.org/WAI/WCAG22/Understanding/use-of-color.html).
- Kewenangan mewakili badan dan pemberian kuasa (uraian praktisi, bukan
  naskah peraturan):
  [Hukumonline — yang berhak menandatangani atas nama perusahaan](https://www.hukumonline.com/klinik/a/siapa-yang-berhak-menandatangani-mou-perusahaan-lt4cbd141d8884e);
  [Hukumonline — dasar pemberian kuasa direksi kepada karyawan](https://www.hukumonline.com/klinik/a/dasar-pemberian-kuasa-direksi-kepada-karyawan-lt5bdfc94d1489d).
- Prinsip pemrosesan data pribadi "terbatas dan spesifik" (UU 27/2022 —
  **perlu verifikasi** pada naskahnya):
  [salinan JDIH Kemenkeu](https://jdih.kemenkeu.go.id/download/46c17b53-4a45-411c-9b76-c6799e5769fc/UU_Nomor_27_Tahun_2022%20Perlindungan%20Data%20Pribadi.pdf).
