# Rencana: Master Pegawai Tiga Kelompok — Internal, Instansi Eksternal, Pihak Ketiga

> **Status:** rencana, belum ada kode yang diubah.
> **Baseline:** `main` pada commit `7d1af3e` (PR #1111), 10 November 2026.
> **Pelaksana yang dituju:** Opus 5.5 (atau model/orang lain) — dokumen ini
> berdiri sendiri; tidak butuh riwayat percakapan yang melahirkannya.
> **Nomor baris** di bawah adalah petunjuk pada baseline. Baris bergeser;
> **nama fungsi** yang menjadi pegangan. Revalidasi sebelum menyunting.

> **Revisi 3 (10 November 2026) — menggantikan revisi sebelumnya.**
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
| Orang | `pegawai` | `pegawai_luar` — field sama | `pegawai_luar` — disesuaikan (3.7) |
| Cakupan | per satker | **seluruh instansi** | **seluruh instansi** |
| Ikon | kartu pegawai | gedung pemerintah | jabat tangan |

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
| `eksternal` | Aparatur instansi pemerintah lain | Pejabat K/L pemakai sementara BMN; petugas pemda/pemdes peminjam pakai; tim pendamping |
| `pihak_ketiga` | Orang dari badan non-pemerintah, atau perorangan | Wakil sekolah swasta, BUMN/BUMD, perusahaan, koperasi, yayasan; warga yang menyewa |

### 3.3 Hierarki luar meniru hierarki internal

```
instansi_luar ─┬─ satker_luar ─┬─ unit_kerja_luar (pohon Eselon/Tingkat I–V)
               │               └─ pegawai_luar (eselon1..5 = NAMA unit, seperti internal)
               └─ satker_luar …
```

Orang luar **wajib** berada di satu `satker_luar`. Instansi dibuat bersama
satker pertamanya (untuk pihak ketiga, layar mengisi nama satker pertama =
nama badan, bisa diubah).

**Perorangan/masyarakat** tidak punya badan. Agar strukturnya tetap satu,
ada satu instansi-wadah berjenis `perorangan` — "Masyarakat (Perorangan)" —
dengan satu satker-wadah. Keduanya dibuat sistem saat pertama dibutuhkan,
tidak bisa dihapus atau diganti nama, dan pohon unitnya dinonaktifkan. Ini
struktur, bukan data contoh.

### 3.4 Satu direktori untuk seluruh instansi

Keputusan pemilik. Keempat koleksi luar **tidak** distempel `kode_satker`
dan **tidak** dibungkus `scope_query_field_satker`.

| Tindakan | Siapa | Catatan |
|---|---|---|
| Lihat | semua pengguna login, semua satker | |
| Tambah, ubah | admin satker mana pun, super-admin | OCC `If-Match`; audit memuat satker pengubah (K2a) |
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

**b. Field lama yang dimanfaatkan ulang (nama field tetap, sebutan berubah)**

| Field | Sebutan internal | Sebutan pihak ketiga |
|---|---|---|
| `nip` | NIP/NIK/NRP | NIK (opsional, K5) |
| `jabatan` | Jabatan | Jabatan pada badan |
| `nomor_kontrak` | Nomor kontrak | Nomor dokumen dasar hubungan (perjanjian/persetujuan) |
| `tgl_mulai_kontrak`, `tgl_selesai_kontrak` | Mulai/selesai kontrak | Berlaku mulai/sampai — tetap menggerakkan peringatan "masih memegang aset" |
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
  ganti kerugian pegawai negeri; berlaku tidaknya bagi pihak ketiga belum
  diriset (PGW-00). `status: meninggal` + tanggalnya **tetap ada** karena
  itulah yang memblokir penugasan baru.

`status_kepegawaian` dipaksa `non_asn` oleh server, sehingga aturan yang
sudah ada untuk Non-ASN — NIK tidak dicetak di blok tanda tangan, tanpa
perkiraan pensiun — berlaku tanpa menyentuh pemanggilnya.

**Instansi eksternal tidak mengalami satu pun dari ini**: field, sebutan,
dan Excel-nya sama persis dengan internal.

### 3.8 Ikon per kelompok — satu komponen, di semua layar kecuali persuratan

| Kelompok | Ikon (lucide-react) | Warna | Teks alternatif |
|---|---|---|---|
| Internal | `IdCard` | sky | "Pegawai internal" |
| Instansi eksternal | `Landmark` | amber | "Pegawai instansi eksternal" |
| Pihak ketiga | `Handshake` | emerald | "Pihak ketiga" |
| Tak terdaftar di master mana pun | *(tanpa ikon)* | — | — |

- Dibedakan **bentuk**, bukan hanya warna; tiap ikon punya nama yang bisa
  dibaca pembaca layar dan tooltip yang bisa diketuk (`TooltipKetuk`). Warna
  saja tidak boleh menjadi satu-satunya pembawa arti.
- **Satu sumber**: `components/pegawai/IkonKelompok.jsx` +
  `lib/kelompokOrang.js`. Tak ada berkas lain yang memilih ikon/warna
  kelompok sendiri.
- **Dari mana kelompoknya diketahui:** (1) salinan `kelompok` pada catatan
  itu sendiri bila ada (BAST, penerima persediaan — ditulis sejak PGW-06);
  (2) selain itu, dicocokkan lewat **nomor identitas** ke indeks ringan
  `GET /direktori-pegawai/indeks`. Tidak pernah ditebak dari nama.
- **Luring:** indeks terakhir disimpan di perangkat; tanpa indeks, ikon tidak
  tampil dan tak ada yang rusak.
- **Tanpa ikon** (K10): persuratan (`PersuratanPage.jsx`,
  `components/persuratan/*`), semua naskah cetak (PDF/Word/Excel), halaman
  verifikasi publik TTD, dan email. Di sana kelompok — bila perlu disebut —
  ditulis sebagai kata.
- Ketiga nama ikon sudah dipakai di berkas lain repo ini; periksa
  ketersediaannya pada versi `lucide-react` terpasang sebelum memakai.

### 3.9 Kebijakan per jenis penerima sebagai data, bukan `if` yang tersebar

Satu modul murni, `backend/kebijakan_penerima.py`, menjawab untuk tiap
**jenis instansi** (5.6): skema apa yang sah, dokumen dasar apa yang wajib
dirujuk, siapa yang layak menandatangani, rezim ganti rugi mana, dan butir
pasal mana yang dipakai. Modul lain **bertanya** kepadanya. Isi awalnya
diturunkan dari tabel 2.9 dan baru dikunci setelah PGW-00.

---

## 4. Keputusan yang milik pemilik

| # | Pertanyaan | Bawaan / keputusan | Jawaban pemilik |
|---|---|---|---|
| K1 | BUMN/BUMD masuk kelompok mana? | Pihak ketiga | **Dijawab:** pihak ketiga |
| K2 | Master luar per satker atau se-instansi? | — | **Dijawab:** satu direktori untuk seluruh instansi |
| K2a | Siapa boleh mengubah catatan bersama? | Semua admin boleh tambah/ubah/nonaktifkan; hapus permanen hanya super-admin; semua ber-audit. Pilihan lain: hanya pencatat + super-admin yang boleh mengubah | |
| K3 | Orang luar mendapat akses portal BMN Saya? | Tidak | |
| K4 | Tenaga alih daya yang sudah tercatat internal dipindah ke pihak ketiga? | Tidak | |
| K5 | NIK orang pihak ketiga wajib? | Opsional; tanpa nomor ia tak bisa jadi pemegang aset tertaut dan ikonnya tak bisa dicocokkan pada catatan lama | |
| K6 | Urutan modul yang ditautkan ke master instansi (PGW-11) | Pemanfaatan → Penggunaan (PSP) → Pemeliharaan → Pengadaan → Pemindahtanganan → Persediaan | |
| K7 | Orang luar boleh jadi pejabat di Referensi Pejabat? | Tidak | |
| K8 | Tab data pribadi untuk **instansi eksternal**? | Tampil — mengikuti "struktur sama"; semuanya opsional. Rekomendasi penyusun: sembunyikan, karena direktori ini kini terlihat seluruh satker | |
| K9 | Sebutan tingkat unit pihak ketiga | "Tingkat I–V" | |
| K10 | Ikon di naskah cetak (PDF/Word) dan halaman verifikasi publik? | Tidak — sama seperti persuratan; kelompok ditulis sebagai kata | |
| K11 | Perorangan/masyarakat dicatat di bawah satu wadah "Masyarakat (Perorangan)"? | Ya (3.3) | |

---

## 5. Model data

Semua koleksi di bawah: `id` UUID unik, `version` (OCC), `created_at`,
`updated_at`, `dicatat_oleh`, `diubah_oleh`, `aktif`. **Tanpa `kode_satker`.**

### 5.1 `instansi_luar`

| Field | Aturan |
|---|---|
| `kelompok` | `eksternal` \| `pihak_ketiga`. Tak boleh diubah bila sudah punya satker |
| `jenis` | Lihat 5.6; harus cocok dengan `kelompok`. Menentukan kebijakan (3.9) |
| `nama` | Wajib |
| `nama_kunci` | Turunan server: huruf kecil, tanda baca dibuang, spasi tunggal, bentuk badan dinormalkan (`PT. Telkom` = `Telkom, PT`) |
| `singkatan`, `kode_referensi`, `alamat`, `kota`, `telepon`, `email` | Opsional. `kode_referensi` = kode BA/kode pemda, teks bebas |
| `narahubung_nama`, `narahubung_jabatan`, `narahubung_kontak` | Opsional |
| `peran` | List kode (5.6) — petunjuk, bukan pembatas; peran sesungguhnya ada di tiap transaksi |
| `nomor_induk`, `npwp`, `dasar_pendirian_nomor`, `dasar_pendirian_tanggal`, `badan_penyelenggara` | Hanya pihak ketiga (3.7a); dikosongkan untuk eksternal |
| `wadah` | `true` hanya pada "Masyarakat (Perorangan)" — tak bisa diubah/hapus |

### 5.2 `satker_luar` — padanan `satker`

| Field `satker` internal | Di `satker_luar` |
|---|---|
| `kode_satker` (identitas) | **`kode_luar`** — kode milik satker itu; opsional; teks bebas |
| `nama_satker`, `nama_unit_organisasi`, `nama_sub_unit`, `alamat`, `telepon`, `email`, `aktif` | sama |
| `kode_satker_lengkap` | sama (kode lokasi BMN milik mereka; hanya eksternal) |
| `eselon_satker` | sama — puncak pohon unitnya; kosong = 1 |
| setelan kop & laporan (`logo_url`, `judul_laporan`, `penandatangan`, …) | **tidak dibawa** |
| — | tambahan: `instansi_id`, `kelompok` dan `jenis` (salinan dari instansinya), `nama_kunci` |

### 5.3 `unit_kerja_luar` — bentuk sama dengan `unit_kerja`

`{nama_unit, eselon "1".."5", parent_id, satker_luar_id, sumber}`. Aturan
pohon seluruhnya dari `organisasi_utils`, dengan `akar` = `eselon_satker`
milik satkernya.

### 5.4 `pegawai_luar`

Seluruh field `PegawaiIn`, ditambah:

| Field | Aturan |
|---|---|
| `satker_luar_id` | **Wajib** |
| `kelompok`, `jenis_instansi`, `instansi_id`, `instansi_nama`, `satker_luar_nama` | Diisi server dari master; merambat saat instansi/satker diganti nama |
| `kapasitas_bertindak`, `dasar_kewenangan_jenis`, `dasar_kewenangan_nomor`, `dasar_kewenangan_tanggal` | Hanya pihak ketiga (3.7a); dikosongkan untuk eksternal |

Makna field warisan: `kode_satker` **selalu kosong** di koleksi ini (ia kunci
isolasi internal; jangan diisi); `kode_satker_lengkap` = kode lokasi BMN
satker **mereka**; `eselon1..5` = nama unit pada pohon satker **mereka**.

### 5.5 Indeks, backup, GridFS

```python
for kol in ("instansi_luar", "satker_luar", "unit_kerja_luar", "pegawai_luar"):
    await _idx(db[kol], "id", unique=True)
await _idx(db.instansi_luar, [("kelompok", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.satker_luar, [("instansi_id", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.unit_kerja_luar, "satker_luar_id")
await _idx(db.pegawai_luar, [("kelompok", 1), ("satker_luar_id", 1), ("nama", 1)])
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
JENIS_INSTANSI = {
    "eksternal": {
        "kementerian_lembaga": "Kementerian/Lembaga",
        "pemerintah_provinsi": "Pemerintah Provinsi",
        "pemerintah_kabkota": "Pemerintah Kabupaten/Kota",
        "pemerintah_desa": "Pemerintah Desa",
        "lembaga_negara_lain": "Lembaga Negara/Pemerintah Lainnya",
    },
    "pihak_ketiga": {
        "bumn": "Badan Usaha Milik Negara",
        "bumd": "Badan Usaha Milik Daerah",
        "bumdes": "Badan Usaha Milik Desa",
        "badan_usaha_swasta": "Badan Usaha Swasta",
        "satuan_pendidikan_swasta": "Satuan Pendidikan Swasta",
        "koperasi": "Koperasi",
        "yayasan_ormas": "Yayasan/Organisasi Masyarakat",
        "kelompok_masyarakat": "Kelompok Masyarakat",
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
    "eksternal": {"instansi": "Instansi", "satker": "Satker", "level": "Eselon"},
    "pihak_ketiga": {"instansi": "Badan/Pihak", "satker": "Unit/Cabang",
                     "level": "Tingkat"},
}
```

Usulan kerja; dikunci di PGW-00. Tidak ada data benih instansi selain
wadah perorangan (3.3) — daftar kode K/L/pemda tidak boleh ditulis dari
ingatan.

### 5.7 Invarian

1. Setiap `pegawai_luar` menunjuk `satker_luar` yang ada; `kelompok`,
   `jenis_instansi`, `instansi_id` selalu sama dengan milik satkernya.
2. `kelompok == "pihak_ketiga"` ⇒ `status_kepegawaian == "non_asn"` dan
   seluruh field 3.7c kosong. `kelompok == "eksternal"` ⇒ field 3.7a kosong.
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

---

## 6. Kontrak API

Semua rute di bawah **baru**. Tak satu pun rute yang ada berubah.

### 6.1 Instansi & satker luar (`backend/routes/organisasi_luar.py`)

| Rute | Penjaga | Catatan |
|---|---|---|
| `GET /luar/referensi` | `require_user` | Semua kode 5.6 + `field_nonaktif_pihak_ketiga` + `label_field` (3.7b) — layar membaca ini, tidak menyalin daftar |
| `GET /luar/instansi?kelompok=&jenis=&q=&aktif=` | `require_user` | + `jumlah_satker`, `jumlah_orang` (agregasi) |
| `POST /luar/instansi` | `require_admin` | Payload memuat `satker_pertama`; 400 bila `nama_kunci` sudah ada — jawaban menyertakan id yang sudah ada agar layar menawarkan "pakai yang ini" |
| `PUT /luar/instansi/{id}` | `require_admin` + `If-Match` | Ganti nama → rambatkan `instansi_nama` |
| `DELETE /luar/instansi/{id}` | `require_super_admin` | 409 bila masih punya satker berorang atau dirujuk transaksi |
| `GET/POST /luar/satker`, `PUT`, `DELETE /luar/satker/{id}` | seperti instansi | Hapus 409 bila masih berorang/ber-unit |

Tiap tulis ber-`log_audit` dengan `kode_satker=kode_satker_user(user)`.

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
| `GET /pegawai` | `GET /pegawai-luar` | + field 5.4; `info_masa` sama |
| `GET /pegawai/rekap-unit` | `GET /pegawai-luar/rekap-unit` | `satker_luar_id` wajib |
| — | `GET /pegawai-luar/rekap-lingkup?kelompok=` | Baru: cacah per instansi & satker |
| `GET /pegawai/perlu-serah-terima` | padanan | Cacah aset **ter-scope satker pemanggil** |
| `GET /pegawai/{id}/aset` | padanan | Hanya aset satker pemanggil |
| `POST`, `PUT /pegawai…` | `POST`, `PUT /pegawai-luar…` | `require_admin`; `_bersih` + `validate_pegawai`, lalu `sesuaikan_orang_luar` |
| `DELETE /pegawai/{id}` | `DELETE /pegawai-luar/{id}` | `require_super_admin`; admin memakai nonaktifkan |
| template, ekspor, impor | padanan | Ekspor & impor wajib `satker_luar_id`; header per kelompok (PGW-04) |
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
| `GET /direktori-pegawai?kelompok=semua\|internal\|eksternal\|pihak_ketiga` | Hanya baca. Bagian internal **ter-scope satker pemanggil** (persis `GET /pegawai`); bagian luar se-instansi, hanya yang `aktif`. Field ringkas: `id`, `ranah`, `kelompok`, `jenis_instansi`, `nama`, `nip`, `jabatan`, `unit_kerja`, `email`, `alamat`, `status`, `status_kepegawaian`, `foto_file_id`, `instansi_nama`, `satker_luar_nama`, `kapasitas_bertindak` |
| `GET /direktori-pegawai/indeks` | `{nomor_identitas: kelompok}` — bahan ikon. Cakupan sama dengan baris di atas. Ber-`ETag`; layar menyimpannya untuk luring |
| `POST /direktori-pegawai/kartu/identifikasi` | Cari di `pegawai` dulu, lalu `pegawai_luar`; batas laju dan audit sama dengan rute internal |

```python
async def cari_orang(scope_internal, nip) -> dict | None      # + "ranah", "kelompok"
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
| `routes/bast.py` → cek PIHAK KESATU meninggal; snapshot pihak | Mengenali orang luar; `PihakIn`/`PjTambahanIn` + `kelompok`, `instansi_nama` (dibekukan) |
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

**Tanpa ikon** (`LARANGAN_IKON`, juga ditagih uji): `pages/PersuratanPage.jsx`,
`components/persuratan/*`, `pages/TtdPublikPage.jsx`, dan seluruh keluaran
backend (PDF/Word/Excel/email).

Nama berkas di tabel ini dicocokkan ulang dengan repo saat PGW-08 dimulai;
yang tidak ada dicoret, yang terlewat ditambahkan.

---

## 8. Paket kerja

### Status

| Paket | Isi | Bergantung | Status | PR |
|---|---|---|---|---|
| PGW-00 | Regulasi & kontrak modul | — | belum | |
| PGW-01 | Fondasi murni | 00 | belum | |
| PGW-02 | Master instansi & satker luar (backend) | 01 | belum | |
| PGW-03 | Orang luar (backend) | 02 | belum | |
| PGW-04 | Impor/ekspor/template orang luar | 03 | belum | |
| PGW-05 | Unit kerja luar (backend) | 03 | belum | |
| PGW-06 | Direktori gabungan, indeks kelompok, pembaca backend | 03 | belum | |
| PGW-07 | Layar Master Pegawai | 03, 04, 05 | belum | |
| PGW-08 | Ikon kelompok & pemilih lintas modul | 06 | belum | |
| PGW-09 | Laporan & dokumen | 06 | belum | |
| PGW-10 | Kebijakan & pasal per jenis penerima | 00, 06, 09 | belum | |
| PGW-11 | Tautan instansi di modul berpihak-luar | 02, 07 | belum | |
| PGW-12 | Data uji & dokumentasi | 07–10 | belum | |

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
   - Batas pengumpulan data pribadi orang luar menurut UU 27/2022 — bahan K8.
3. Tambah kontrak di `docs/MASTERPLAN-SIKLUS-BMN.md`.
4. Kunci daftar kode 5.6 dan isi `kebijakan_penerima` (6.6).
5. Daftarkan sitasi yang akan tercetak ke `backend/sitasi_regulasi.py`
   dengan status yang jujur; "terverifikasi" menuntut naskahnya di
   `docs/regulasi/` (ditagih `test_sitasi_regulasi.py`).

**Terima:** matriks ada di pustaka dan bersumber; tiap pertanyaan berjawaban
atau bertanda "perlu verifikasi" dengan bawaan konservatif yang dipakai.

---

### PGW-01 — Fondasi murni

**Berkas baru:** `backend/organisasi_luar_utils.py`,
`backend/tests/unit/test_organisasi_luar_utils.py`.

```python
# kode referensi 5.6
FIELD_NONAKTIF_PIHAK_KETIGA = (...)        # persis daftar 3.7c
FIELD_KHUSUS_PIHAK_KETIGA = ("kapasitas_bertindak", "dasar_kewenangan_jenis",
                             "dasar_kewenangan_nomor", "dasar_kewenangan_tanggal")
FIELD_KHUSUS_BADAN = ("nomor_induk", "npwp", "dasar_pendirian_nomor",
                      "dasar_pendirian_tanggal", "badan_penyelenggara")
LABEL_FIELD = {"pihak_ketiga": {"nip": "NIK", "nomor_kontrak": "...", ...}}

def nama_kunci(nama) -> str
def validate_instansi_luar(doc) -> list[str]
def validate_satker_luar(doc) -> list[str]
def bersihkan_instansi_luar(payload) -> dict     # kosongkan FIELD_KHUSUS_BADAN utk eksternal
def bersihkan_satker_luar(payload) -> dict
def sesuaikan_orang_luar(doc, kelompok, jenis_instansi) -> dict
    # eksternal: kosongkan FIELD_KHUSUS_PIHAK_KETIGA; sisanya APA ADANYA
    # pihak_ketiga: status_kepegawaian="non_asn"; kosongkan FIELD_NONAKTIF_…
    # perorangan: kapasitas="diri_sendiri"; eselon1..5 kosong
def validate_orang_luar(doc, kelompok, jenis_instansi) -> list[str]
    # pengurus_berwenang/penerima_kuasa tanpa dasar_kewenangan → peringatan
def label_unit_orang(doc) -> str
    # internal: unit_kerja; luar: "instansi_nama — satker_luar_nama — unit"
```

**Uji minimum:**
- `nama_kunci("PT. Telkom Indonesia") == nama_kunci("Telkom  Indonesia, PT")`.
- `sesuaikan_orang_luar` eksternal: dokumen penuh keluar sama dengan masuk,
  kecuali empat field khusus pihak ketiga kosong.
- Pihak ketiga: `non_asn`; setiap field 3.7c kosong; `nama`, `nip`,
  `jabatan`, `nomor_kontrak`, `eselon2`, `tanggal_meninggal` utuh.
- Kesetaraan skema: `set(_bersih(PegawaiIn(nama="x")))` ⊇
  `FIELD_NONAKTIF_PIHAK_KETIGA` — salah ketik nama field gagal di sini.
- `jenis` yang tak cocok `kelompok` ditolak; perorangan dipaksa
  `diri_sendiri`.

**Terima:** uji lulus; belum ada pemanggil.

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
  dengan satker B (K2a bawaan).
- `DELETE` oleh admin → 403; oleh super-admin → berhasil bila tak dirujuk,
  409 bila dirujuk.
- Nama kembar beda tanda baca → 400 dengan id yang sudah ada.
- `POST /luar/instansi` tanpa `satker_pertama` → 400.
- `PUT` dengan `If-Match` usang → 409.
- Tak satu pun dokumen tersimpan memuat kunci `kode_satker`.
- Wadah perorangan tak bisa diubah/dihapus; pembuatannya idempoten.
- Field khusus badan pada instansi eksternal tersimpan kosong.

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
   `jenis_instansi` dari master; memaksa `kode_satker = ""`. Satker tidak
   ada/nonaktif → 400.
3. Buat/ubah: `_bersih` → `validate_pegawai` + `validate_orang_luar` →
   `sesuaikan_orang_luar` → `_stempel` → cek NIP (invarian 4) → tulis
   ber-OCC → `log_audit`. `DuplicateKeyError` pada indeks NIP → 400.
4. Daftar: `info_masa_pegawai` yang sama; hanya `aktif` kecuali diminta.
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
kosong; eksternal dengan payload penuh tersimpan sama dengan `_bersih`-nya;
NIP milik pegawai internal satker **lain** → 400 dan pesannya tidak memuat
nama orang itu; dua satker memegang aset atas orang yang sama → masing-masing
hanya melihat asetnya.

**Terima:** uji lama `test_pegawai_*`, `test_portal_*`, `test_unit_kerja_*`
lulus tanpa disunting; `git diff --stat` tidak memuat `routes/pegawai.py`.

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
   # eksternal    → HEADER_IMPOR (identik)
   # pihak_ketiga → HEADER_IMPOR tanpa kolom field 3.7c, dengan sebutan
   #                3.7b, + "Kapasitas Bertindak", "Dasar Kewenangan",
   #                "Nomor Dasar Kewenangan", "Tgl Dasar Kewenangan"
   def baris_impor_luar(raw, kelompok) -> (doc, peringatan)
   def baris_ekspor_luar(doc, kelompok) -> list
   ```
   `baris_impor_luar` memetakan sebutan pihak ketiga kembali ke header baku
   lalu memanggil `baris_impor_ke_pegawai` — satu penormal, bukan dua.
2. Ekspor: `satker_luar_id` wajib — satu berkas = satu satker. Eksternal
   memakai `_build_pegawai_xlsx` apa adanya; pihak ketiga memakai pembangun
   yang sama dengan header dan baris dari langkah 1 (bila pembangun itu
   mengeraskan `HEADER_IMPOR`, bungkus dengan pembangun kecil di modul luar —
   jangan menyunting yang internal).
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
eksternal **identik** dengan `HEADER_IMPOR`; header pihak ketiga tidak
memuat satu pun kolom field 3.7c; impor ulang tidak menggandakan; berkas
berisi NIP pegawai internal → internal tak berubah; ekspor/impor tanpa
`satker_luar_id` → 400.

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

---

### PGW-06 — Direktori gabungan, indeks kelompok, pembaca backend

**Berkas:** `backend/direktori_pegawai.py`,
`backend/routes/direktori_pegawai.py`, `backend/server.py`, sembilan titik di
7.2, `backend/tests/unit/test_direktori_pegawai.py`, perluasan
`test_penerima_persediaan.py`.

1. `cari_orang`, `cari_orang_banyak` — urutan menang: internal dulu.
2. `GET /direktori-pegawai`, `/indeks`, identifikasi kartu gabungan.
3. Sunting sembilan pembaca, **satu komit per berkas**, masing-masing dengan
   uji "orang luar terdaftar kini dikenali" dan uji "perilaku untuk orang
   internal tidak berubah".
4. `enforce_pegawai_terdaftar`: hari ini tanpa scope satker; pertahankan
   semantik itu.

**Uji minimum:** indeks untuk pengguna satker A memuat pegawai internal A
dan seluruh orang luar aktif, **tidak** memuat pegawai internal B; NIP yang
ada di internal dan luar → kelompok internal.

---

### PGW-07 — Layar Master Pegawai

**Berkas:** `frontend/src/pages/PegawaiPage.jsx`,
`frontend/src/lib/ranahPegawai.js` (+ uji),
`frontend/src/components/pegawai/BilahLingkupLuar.jsx`,
`frontend/src/components/pegawai/KelolaOrganisasiLuar.jsx`,
`frontend/src/pages/__tests__/PegawaiKelompok.test.jsx`.

1. `lib/ranahPegawai.js` (murni): tiga objek ranah — jalur API
   (`/pegawai` | `/pegawai-luar`, `/unit-kerja` | `/unit-kerja-luar`),
   pembuat parameter lingkup, dan `EMPTY_PIHAK_KETIGA` (empat field khusus).
   Sebutan dan daftar field nonaktif dibaca dari `GET /luar/referensi`.
2. Ganti 22 literal `${API}/pegawai` dan 5 literal `${API}/unit-kerja` di
   `PegawaiPage.jsx` dengan jalur dari ranah aktif. Untuk ranah internal
   hasilnya string yang sama persis.
3. **Pemilih kelompok** berikon (3.8): Internal · Instansi Eksternal · Pihak
   Ketiga. `data-testid="pegawai-kelompok-<kunci>"`; tinggi ≥ 44px di
   ≤ 1023px; ranah dan lingkup masuk deps efek muat ulang.
4. **Bilah lingkup** (tab luar): instansi → satker, dengan cacah dari
   `rekap-lingkup`, saringan `jenis`, tombol "Kelola". Tombol Tambah, Impor,
   Ekspor, Struktur Organisasi, Kelola Unit nonaktif sampai satu satker
   dipilih (dengan keterangan).
5. `KelolaOrganisasiLuar.jsx` — komponen level modul, dua tingkat. Saat
   mengetik nama, tampilkan yang mirip dari direktori ("sudah ada — pakai
   yang ini") **sebelum** simpan: direktori bersama cepat kotor oleh
   kembaran. Form badan pihak ketiga memuat field 3.7a dengan label
   `nomor_induk` mengikuti jenis. Hapus permanen hanya tampak bagi
   super-admin; yang lain melihat "Nonaktifkan".
6. **Form orang.** `EMPTY` tidak berubah. Eksternal: form sama persis.
   Pihak ketiga: field 3.7c tidak dirender; sebutan 3.7b; Status Kepegawaian
   terkunci Non-ASN; bagian baru "Kapasitas & Dasar Kewenangan". Perorangan:
   bagian unit tidak dirender, kapasitas terkunci "diri sendiri".
7. Karena direktori bersama, kepala tab luar memuat keterangan satu baris:
   "Direktori ini dipakai bersama seluruh satker." Baris daftar menampilkan
   satker pencatat pada rincian.
8. Tab luar: tanpa "Sinkron aset"; tanpa jam ahli waris.
9. Daftar dirender dua kali (kartu HP dan tabel desktop) — ubah keduanya.
10. `hover:bg-muted`; uji terang dan gelap; jangan memperkecil tombol.

**Uji minimum (Jest):**
- **Regresi internal:** himpunan URL yang dipanggil tab internal sama dengan
  sebelum paket (daftar URL dibekukan di uji).
- Tab pihak ketiga tidak merender field agama, pangkat, rekening; merender
  Kapasitas Bertindak.
- Tab eksternal merender form yang sama dengan internal.
- Tanpa satker terpilih, tombol Tambah nonaktif.
- Tombol hapus permanen tidak ada untuk admin biasa.
- `PegawaiAkarEselon.test.jsx` dan backend `test_pegawai_cakupan_ekspor.py`
  lulus tanpa disunting.

**Terima:** `yarn lint`; `CI=true yarn test --watchAll=false`;
`CI=false yarn build`; periksa manual HP dan desktop, terang dan gelap.

---

### PGW-08 — Ikon kelompok & pemilih lintas modul

Boleh dipecah: 08a (komponen + indeks + aset + BAST), 08b (layar lain).

**Berkas inti:** `frontend/src/components/pegawai/IkonKelompok.jsx`,
`frontend/src/lib/kelompokOrang.js` (+ uji),
`frontend/src/hooks/useIndeksKelompok.js`,
`frontend/src/lib/__tests__/permukaanIkon.test.js`.

1. `lib/kelompokOrang.js`: `KELOMPOK` (ikon, kelas warna terang/gelap, teks
   alternatif), `PERMUKAAN_IKON`, `LARANGAN_IKON`,
   `kelompokDari(catatan, indeks)` — salinan pada catatan menang atas indeks.
2. `IkonKelompok`: prop `kelompok` atau `nomor`; `ukuran`; `denganLabel`.
   `role="img"` + `aria-label`; tooltip lewat `TooltipKetuk`; `min-w-0
   min-h-0` supaya aturan tap-target global tidak membengkakkannya di dalam
   baris. Kelompok tak dikenal → tidak merender apa pun.
3. `useIndeksKelompok`: memuat `/direktori-pegawai/indeks` sekali per sesi
   (ber-`ETag`), menyimpannya di perangkat untuk luring (baca/tulis dalam
   try/catch; halaman harus tetap benar tanpa simpanan itu), dan
   menyegarkannya saat kembali daring. **Satu** pemuatan dibagi semua layar
   — jangan memuat per baris.
4. Pemilih di tiap berkas 7.2-frontend berpindah ke
   `GET /direktori-pegawai?kelompok=semua` dan menampilkan ikon + instansi.
   `pihakDariPegawai`: untuk orang luar `alamat` = alamat orangnya, jatuh ke
   "instansi — satker". Memilih orang ber-kapasitas `petugas` sebagai pihak
   BAST/penanda tangan memunculkan peringatan lunak.
5. Pasang `IkonKelompok` di tiap layar `PERMUKAAN_IKON` (7.3).
   - Di dalam `FullCameraSheet` tetap elemen native.
   - Daftar aset: jangan menambah permintaan jaringan per baris; ikon hanya
     membaca indeks yang sudah di memori.
   - `PejabatPage.jsx` dan `PortalPemegangPanel.jsx` tetap memuat `/pegawai`.
6. Uji `permukaanIkon.test.js` (pembaca-sumber): tiap berkas di
   `PERMUKAAN_IKON` mengimpor `IkonKelompok`; tak satu pun berkas di
   `LARANGAN_IKON` mengimpornya; tak ada berkas selain `kelompokOrang.js`
   yang memetakan kelompok → nama ikon.

**Uji minimum:** ikon punya nama terakses yang berbeda per kelompok; nomor
tak dikenal → tak ada ikon; gagal memuat indeks → layar tetap tampil; lima
berkas uji Jest yang me-mock URL `/pegawai` diperbarui bila berkasnya
disentuh.

**Terima:** tiga ikon terbedakan dalam skala abu-abu (bentuknya, bukan
warnanya); periksa terang/gelap, HP/desktop; halaman Persuratan tanpa ikon.

---

### PGW-09 — Laporan & dokumen

1. **Tanpa ikon** di seluruh keluaran (K10). Kelompok ditulis sebagai kata
   hanya bila menambah keterangan.
2. **Laporan Eksekutif — Distribusi Per Pengguna**: pengguna luar membawa
   jalur eselon organisasi lain — jangan dilebur ke pohon satker sendiri.
   Pembagi tersendiri sesudah pengguna internal: "Instansi Eksternal" →
   instansi → satker, lalu "Pihak Ketiga" → badan → unit. Baris pengguna
   internal tidak berubah.
3. **Rekap pemegang / daftar per pemegang PDF:** kolom unit memakai
   `label_unit_orang`.
4. **Wasdal:** temuan "pemegang berisiko" menyebut kelompok + instansi; untuk
   orang luar "kontrak berakhir" berbunyi "masa hubungan berakhir".
5. Aturan blok tanda tangan tidak berubah: tetap `baris_identitas_ttd`.

**Uji:** `test_laporan_eksekutif_pengguna_jenjang.py` diperluas; total tidak
berubah; laporan yang seluruh penggunanya internal menghasilkan baris yang
sama persis dengan sebelum paket. Smoke-render PDF dengan harness FakeDB.

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
   | `kementerian_lembaga`, `lembaga_negara_lain` | penggunaan sementara | persetujuan Pengelola Barang | `antar_pemerintah` |
   | `pemerintah_provinsi`, `_kabkota`, `_desa` | pinjam pakai | persetujuan + perjanjian | `antar_pemerintah` |
   | `bumn`, `bumd`, `bumdes`, `badan_usaha_swasta` | sewa; KSP; BGS/BSG; KSPI; KETUPI; dioperasikan pihak lain | persetujuan + perjanjian | `pihak_ketiga` |
   | `perorangan` | sewa | persetujuan + perjanjian | `pihak_ketiga` |
   | `satuan_pendidikan_swasta`, `yayasan_ormas`, `koperasi`, `kelompok_masyarakat`, `lembaga_internasional`, `lainnya` | **ditetapkan PGW-00** | **ditetapkan PGW-00** | `pihak_ketiga` |

2. **BAST kepada penerima luar adalah berita acara penyerahan FISIK yang
   melaksanakan dokumen dasar**, bukan dasar hukum itu sendiri.
   - Jenis BAST baru (nama dikunci PGW-00), mis. `penyerahan_pihak_luar` dan
     pengembaliannya. Jenis lama tidak diubah.
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

---

### PGW-11 — Tautan instansi di modul berpihak-luar (opsional, satu PR per modul)

Urutan K6. Pola aditif: kolom teks yang ada (`mitra`, `pihak`, `penyedia`, …)
**tetap disimpan** sebagai snapshot; tambah field opsional
`<kolom>_instansi_id`; layar memakai masukan teks ber-datalist dari
`GET /luar/instansi` dan menampilkan ikon kelompok; tanpa backfill. Modul
Pemanfaatan dan Penggunaan (PSP) memanggil `periksa_penyerahan` sebagai
**peringatan lunak** — keputusan sahnya tetap pada persetujuan Pengelola.

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
7. **Indeks kelompok dimuat sekali.** Memuatnya per baris daftar aset
   mengubah satu layar menjadi ribuan permintaan.
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

1. Tab internal: tambah, ubah, impor, ekspor — sama dengan sebelum fitur ini.
2. Admin satker A membuat "Kementerian X" + satker, dan "PT Z" + unit.
   Admin satker B langsung melihat keduanya dan tidak bisa menghapusnya.
3. Mengetik "PT. Z" saat menambah badan → ditawari yang sudah ada.
4. Form pihak ketiga: tanpa agama/pangkat/rekening; ada Kapasitas & Dasar
   Kewenangan. Form eksternal: sama dengan internal.
5. Ekspor satu satker luar → ubah satu sel → impor → hanya sel itu berubah.
6. Di daftar aset, pengguna internal, eksternal, dan pihak ketiga tampil
   dengan tiga ikon berbeda; pengguna tak terdaftar tanpa ikon.
7. Halaman Persuratan dan PDF BAST: tanpa ikon.
8. Satker A dan B masing-masing menyerahkan aset ke orang luar yang sama →
   masing-masing hanya melihat aset miliknya pada orang itu.
9. BAST "pinjam pakai" kepada badan usaha → ditolak dengan skema yang
   tersedia. BAST penyerahan kepada pemda tanpa nomor perjanjian → ditolak.
10. BAST kepada wakil badan: komparisi memuat dasar kewenangannya; blok
    tanda tangan nama saja; tak ada klausul hukuman disiplin.
11. BAST kepada pegawai internal: naskah identik dengan sebelum fitur ini.
12. Pemilih pejabat dan panel portal tidak menampilkan orang luar.

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
| R3 | Direktori bersama rusak oleh suntingan satker lain atau kembaran | Sedang | Audit dengan satker pengubah; hapus hanya super-admin; pencarian-saat-mengetik; K2a |
| R4 | Data pribadi orang luar terlihat seluruh satker | Sedang | Field pribadi pihak ketiga dinonaktifkan; K8 untuk eksternal |
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
