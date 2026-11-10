# Rencana: Master Pegawai Tiga Kelompok — Internal, Instansi Eksternal, Pihak Ketiga

> **Status:** rencana, belum ada kode yang diubah.
> **Baseline:** `main` pada commit `7d1af3e` (PR #1111), 10 November 2026.
> **Pelaksana yang dituju:** Opus 5.5 (atau model/orang lain) — dokumen ini
> berdiri sendiri; tidak butuh riwayat percakapan yang melahirkannya.
> **Nomor baris** di bawah adalah petunjuk pada baseline. Baris bergeser;
> **nama fungsi** yang menjadi pegangan. Revalidasi sebelum menyunting.

> **Revisi 2 (10 November 2026) — menggantikan Revisi 1 seluruhnya.**
> Pemilik meluruskan dua hal: (1) Master Pegawai internal **tidak berubah**;
> (2) instansi eksternal dan pihak ketiga memakai **struktur data yang sama**
> dengan internal — instansi yang punya satker-satkernya, unit kerja, lalu
> pegawai — hanya disesuaikan seperlunya untuk pihak ketiga. Revisi 1
> menafsir orang luar sebagai catatan tipis di bawah satu master instansi,
> memangkas field-nya, dan menaruhnya di koleksi `pegawai` yang sama. Tafsir
> itu gugur; desainnya berganti menjadi **koleksi sejajar** (Bab 3.1).

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

Keputusan K1–K9 di Bab 4 memakai nilai BAWAAN kecuali pemilik sudah menulis
jawaban lain di tabel itu. Jangan mengubah bawaan atas inisiatif sendiri.

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
   internal (`pegawai_utils`, `organisasi_utils`, pembantu di
   `routes/pegawai.py`). Modul internal tidak pernah mengimpor dari modul
   luar.
3. **Modul luar tidak pernah menulis ke koleksi internal** (`pegawai`,
   `unit_kerja`, `satker`, `assets`). Ada uji yang menagihnya (PGW-03).
4. **Tanpa migrasi data.** Tidak ada dokumen lama yang diubah.
5. **Buktikan, jangan menyimpulkan.** Uji baru harus gagal sebelum perubahan.
6. **Konvensi repo tetap berlaku seluruhnya:** teks UI/commit/PR Indonesia,
   OCC + Idempotency-Key, lima titik isolasi satker, aturan blok tanda tangan,
   `data-testid`, aturan hover, komponen React di level modul, tap-target 44px.

---

## 1. Tujuan dan batasnya

### Yang diminta pemilik

Master Pegawai sekarang mencatat pegawai **instansi internal**, yang punya
banyak satker. Pemilik meminta dua kelompok tambahan dengan **struktur yang
sama**, tanpa mengubah yang internal:

1. **Instansi eksternal** — tetap pemerintahan; tiap instansi punya
   satker-satkernya; struktur datanya sama dengan internal.
2. **Pihak ketiga** — di luar pemerintahan; struktur datanya juga sama,
   disesuaikan agar pas.

### Bentuk yang dihasilkan

| Tingkat | Internal (hari ini, tetap) | Instansi eksternal | Pihak ketiga |
|---|---|---|---|
| Instansi | tersirat (instansi sendiri) | `instansi_luar` | `instansi_luar` — disebut "Perusahaan/Badan" |
| Satker | `satker` | `satker_luar` | `satker_luar` — disebut "Unit/Cabang" |
| Unit kerja | `unit_kerja` (Eselon I–V) | `unit_kerja_luar` (Eselon I–V) | `unit_kerja_luar` — disebut "Tingkat I–V" |
| Pegawai | `pegawai` | `pegawai_luar` — field sama | `pegawai_luar` — field sama, disesuaikan (3.7) |

Kemampuan yang sama di ketiga kelompok: tambah/ubah/hapus, cari, saring,
urut, OCC, audit, foto, kartu tap, impor/ekspor/template Excel pulang-pergi,
struktur organisasi berjenjang, rekap per unit, bangun unit dari pegawai,
daftar aset yang dipegang, peringatan "masih memegang aset".

### Yang BUKAN tujuan (sengaja ditunda — akhir Bab 8)

- Mengganti kunci tautan aset dari `pengguna_nip` (teks NIP/NIK) menjadi FK.
- Jenis BAST dan pasal baru khusus serah terima ke pihak luar; otomasi amanah
  BAST untuk penerima luar.
- Akses portal BMN Saya untuk orang luar.
- Memindahkan seseorang antara master internal dan master luar.
- Menjadikan master instansi pengganti kolom teks `pihak`/`mitra`/`penyedia`
  di modul lain (PGW-10 hanya menambah tautan opsional).

---

## 2. Keadaan sekarang (bukti dari kode)

### 2.1 Bentuk master internal

- `pegawai`: ±56 field isian form. Logika murni di
  `backend/pegawai_utils.py`; rute di `backend/routes/pegawai.py` (1.255
  baris); layar `frontend/src/pages/PegawaiPage.jsx` (1.954 baris).
- `unit_kerja`: pohon `{nama_unit, eselon "1".."5", parent_id}` per satker.
  Aturan pohon murni di `backend/organisasi_utils.py`; rute di
  `backend/routes/unit_kerja.py` (326 baris). Pegawai menyimpan unitnya
  sebagai **nama** di `eselon1..5`, bukan id; ganti nama unit dirambatkan
  (`_rambatkan_nama`) ke `pegawai` **dan** `assets`.
- `satker`: profil + kop per satker (`backend/routes/satker.py`, `SatkerIn`).
  Tingkat puncak pohon unit sebuah satker = `eselon_satker` (dibaca lewat
  `shared_utils.eselon_satker`).

### 2.2 `kode_satker` adalah kunci ISOLASI, bukan sekadar keanggotaan

Seluruh isolasi multi-satker bertumpu pada field `kode_satker`:
`scope_query_field_satker`, `pastikan_akses_dok_satker`, ikatan akun, kop,
audit, dan `satker_referensi.ganti_kode_satker` (yang menyapu **semua**
koleksi ber-`kode_satker`). Karena itu kode milik satker instansi lain tidak
boleh ditaruh di field bernama `kode_satker` (Bab 3.4).

### 2.3 Kunci tautan ke aset adalah TEKS NIP/NIK

Aset menyimpan `user`, `pengguna_nip`, `pengguna_jabatan`,
`pengguna_melekat_ke`. Rantai pemegang berkunci `pengguna_nip`:
`_jumlah_aset_per_nip`, `aset_dipegang_pegawai` (`routes/pegawai.py`),
`rekap_pemegang` (`penggunaan_utils.py`), `distribusi_pengguna`
(`report_utils.py`). Orang tanpa nomor identitas tidak bisa ditautkan sebagai
pemegang — berlaku untuk internal hari ini dan akan berlaku sama untuk orang
luar (K5).

### 2.4 Pembaca Master Pegawai di luar rutenya

Koleksi `pegawai` disentuh di 57 tempat: 27 di `routes/pegawai.py`, 30 di 14
berkas lain. Sembilan di antaranya mencari orang lewat NIP dan **layak** ikut
mengenali orang luar (daftar di Bab 7.2). Sisanya khusus internal atau lewat
`pegawai.id`, dan dibiarkan.

Pembaca frontend `GET /pegawai`: `AssetForm.jsx:666`,
`PenggunaanPage.jsx:325,479`, `PersediaanPage.jsx:209`,
`PemeliharaanPage.jsx:135`, `TtdPermintaanPage.jsx:130`,
`ActivitySelectionPage.jsx:222`, `PejabatPage.jsx:112`,
`PortalPemegangPanel.jsx:97`, `PegawaiPage.jsx:257`.

### 2.5 Uji yang membaca SUMBER `routes/pegawai.py`

Beberapa uji tidak memanggil fungsi, melainkan membaca teks berkasnya:
`test_pegawai_impor_dedup.py` (isi `impor_pegawai` dan `_filter_dedup`),
`test_cpu_sinkron_di_thread.py` (`_baris_dari_unggahan_pegawai` dijalankan di
thread; rute `.post("/pegawai/impor")`), `test_gerbang_media.py` dan
`test_penjaga_senyap.py` (foto lewat `tulis_media`),
`test_pegawai_cakupan_ekspor.py` (membaca `const EMPTY` di `PegawaiPage.jsx`).
Merombak `routes/pegawai.py` menjadi inti bersama akan mematahkan uji-uji ini
— salah satu alasan desain di Bab 3.5.

### 2.6 Konsep yang bertumpang-tindih dengan permintaan

| Yang sudah ada | Di mana | Kedudukannya |
|---|---|---|
| Non-ASN **outsourcing** + `perusahaan_penyedia` | `jenis_kontrak_non_asn` | Tenaga alih daya yang *ditempatkan di satker* — tetap **internal** (K4) |
| `status_pegawai_satker` perbantuan/dipekerjakan + `status_pegawai_instansi` | `STATUS_PEGAWAI_SATKER_BERINSTANSI` | Bekerja di satker, berasal dari instansi lain — tetap **internal** |
| "Pihak luar — isi identitas manual" | `PilihPegawaiBast.jsx`, `penerima_utils.py` | Jalur manual **tetap ada** |

### 2.7 Modul lain mencatat pihak luar sebagai teks bebas

`pengadaan.pihak`, `pemanfaatan.mitra`, `pemindahtanganan.pihak`,
`pemeliharaan.pelaksana`/`pihak_pelaksana`, `penggunaan.pihak_asal`/
`pihak_tujuan`, `persediaan.penyedia`, `activities.tim_pendukung[].dari_pihak`.
Tidak ada koleksi penyedia/mitra/instansi.

### 2.8 Foto pegawai dan pengonversi WebP

`webp_converter.py` menganggap berkas GridFS ber-`metadata.jenis:
"foto_pegawai"` milik koleksi `pegawai` (`_pegawai_pemilik`). Foto orang luar
yang disimpan dengan jenis yang sama tidak akan menemukan pemiliknya di sana
(Jebakan 9.2).

### 2.9 Temuan sampingan (bukan bagian permintaan — jangan diperbaiki diam-diam)

`snapshot_pemegang_aset` (`pegawai_utils.py:388`) mengisi
`pengguna_melekat_ke` dengan **nama unit kerja**, dan `test_pegawai_utils.py`
menegaskannya. Padahal `models.py:82` dan `AssetForm.jsx` memperlakukan field
itu sebagai enum `Individual | Jabatan | Operasional`. **[Keyakinan sedang]**
— belum ditelusuri apakah ada pembaca yang memang mengharapkan nama unit.
Dilaporkan sebagai isu terpisah; fitur "Sinkron aset" karenanya **tidak**
dibawa ke master luar (Bab 6.4).

---

## 3. Keputusan desain (terkunci)

### 3.1 Koleksi sejajar; internal tidak disentuh

Empat koleksi baru, semuanya untuk orang dan organisasi **di luar** instansi
sendiri: `instansi_luar`, `satker_luar`, `unit_kerja_luar`, `pegawai_luar`.
Kedua kelompok non-internal (eksternal dan pihak ketiga) berbagi keempatnya,
dibedakan field `kelompok`.

**Kenapa bukan satu koleksi `pegawai` dengan penanda kelompok** (Revisi 1):

| | Satu koleksi + penanda | Koleksi sejajar |
|---|---|---|
| Perubahan pada internal | 57 titik pakai harus dipagari, plus `unit_kerja` dan `satker` | nol |
| Bila satu titik terlewat | orang luar bocor ke rekap unit, bangun-unit, pemilih pejabat, portal — **cacat baru** | orang luar tampil "belum terdaftar" — **sama seperti hari ini** |
| Bundel PWA lama yang ter-cache | harus dijaga lewat bawaan parameter | tidak terpengaruh |
| Hash identitas & email portal | dua jebakan | tidak tersentuh |
| Satker & unit kerja milik instansi lain | tak punya tempat (lihat 3.4) | punya koleksinya sendiri |

Harga koleksi sejajar: pembaca yang memang ingin mengenali orang luar harus
ikut membaca koleksi kedua (sembilan titik, Bab 7.2), dan rute luar ditulis
sebagai modul sendiri (3.5).

### 3.2 Batas tiga kelompok — ditentukan oleh TEMPAT BEKERJA

| Kelompok | Definisi | Contoh |
|---|---|---|
| Internal | Bekerja pada satker instansi sendiri, apa pun status kepegawaiannya | PNS/PPPK; PPNPN; tenaga alih daya yang ditempatkan; pegawai dipekerjakan/diperbantukan **dari** instansi lain |
| `eksternal` | Aparatur instansi pemerintah lain yang **tidak** bekerja pada instansi sendiri | Pejabat K/L lain pemakai BMN; petugas pemda penerima hibah; tim pendamping |
| `pihak_ketiga` | Orang dari badan non-pemerintah yang tidak ditempatkan sebagai tenaga satker | Wakil penyedia; teknisi vendor; wakil mitra sewa/KSP; konsultan perusahaan |

### 3.3 Hierarki luar meniru hierarki internal

```
instansi_luar ─┬─ satker_luar ─┬─ unit_kerja_luar (pohon Eselon/Tingkat I–V)
               │               └─ pegawai_luar (eselon1..5 = NAMA unit, seperti internal)
               └─ satker_luar …
```

Pegawai luar **wajib** berada di satu `satker_luar`, sebagaimana pegawai
internal berada di satu satker. Instansi dibuat bersama satker pertamanya
(untuk pihak ketiga, layar mengisi nama satker pertama = nama instansi, bisa
diubah).

### 3.4 `kode_satker` tetap kunci isolasi; kode milik satker luar di `kode_luar`

Keempat koleksi baru distempel `kode_satker` = **satker internal yang
mencatat** (pemilik catatan), ditulis lewat `require_admin_satker` agar tak
pernah kosong. Dengan begitu seluruh penjaga isolasi yang ada bekerja apa
adanya, dan `ganti_kode_satker` ikut memindahkannya.

Kode satker milik instansi lain disimpan di `satker_luar.kode_luar`.
**Jangan pernah** menaruhnya di `kode_satker`: dokumen itu akan lenyap dari
pandangan semua admin satker, dan bisa ikut tersapu saat sebuah satker
internal berganti kode.

### 3.5 Logika murni dipakai bersama; rute luar modul tersendiri

- Yang **dipakai ulang tanpa disalin**: seluruh `pegawai_utils.py`
  (validasi, normalisasi impor, baris ekspor, kunci dedup, info masa, deteksi
  identitas), seluruh `organisasi_utils.py` dan `unit_kerja_utils.py`, serta
  pembantu di `routes/pegawai.py` yang diimpor: `PegawaiIn`, `_bersih`,
  `_build_pegawai_xlsx`, `_baris_dari_unggahan_pegawai`,
  `_kecilkan_foto_asli`, `_jumlah_aset_per_nip`, `KartuIn`.
- Yang **ditulis baru**: penangan rute luar (`routes/pegawai_luar.py`,
  `routes/unit_kerja_luar.py`, `routes/organisasi_luar.py`) — orkestrasi
  tipis: scope, kueri, stempel, audit.
- **Penjaga kesetaraan** (`test_pegawai_luar_setara.py`, PGW-03): daftar rute
  `/pegawai-luar/*` harus sama dengan `/pegawai/*` dikurangi daftar
  pengecualian yang tertulis; modul luar harus memanggil fungsi murni yang
  sama. Rute internal baru tanpa pasangan luarnya membuat uji ini gagal.

Alternatif yang ditolak — merombak `routes/pegawai.py` menjadi inti
berparameter yang dipakai dua rute: menghapus duplikasi penangan, tetapi
mengubah berkas internal yang dijaga uji pembaca-sumber (2.5) dan melanggar
"internal tidak berubah". Bisa ditinjau lagi kelak sebagai refaktor
tersendiri.

### 3.6 Orang luar dikenali lintas modul lewat direktori gabungan

`GET /pegawai` tetap hanya internal. Modul yang ingin memilih atau mengenali
siapa pun memakai lapis baru yang **hanya membaca**:
`backend/direktori_pegawai.py` + `GET /direktori-pegawai`. Urutan menang bila
satu NIP ada di dua tempat: pejabat → pegawai internal → pegawai luar.

### 3.7 Penyesuaian pihak ketiga ("disesuaikan agar pas")

Skema sama; yang disesuaikan hanya ini:

| Hal | Eksternal | Pihak ketiga |
|---|---|---|
| Sebutan tingkat di layar | Instansi · Satker · Eselon I–V | Perusahaan/Badan · Unit/Cabang · Tingkat I–V |
| Label nomor identitas | NIP/NRP/NIK | NIK/No. Identitas |
| `status_kepegawaian` | bebas, seperti internal | **dipaksa `non_asn`** oleh server |
| `pangkat_golongan`, `kategori_pegawai`, `status_pegawai_satker`, `status_pegawai_instansi`, `kode_satker_lengkap`, `jenis_kontrak_non_asn`, `perusahaan_penyedia` | seperti internal | disembunyikan di layar dan dikosongkan server — tak bermakna bagi karyawan badan non-pemerintah |
| Field lain (identitas, pribadi, jabatan, eselon1..5, kontak, bank, masa kontrak, kematian) | seperti internal | seperti internal |

`pihak_ketiga ⇒ non_asn` membuat seluruh aturan Non-ASN yang sudah ada — NIK
tidak dicetak di blok tanda tangan, tanpa perkiraan pensiun, pantau masa
kontrak — berlaku tanpa menyentuh pemanggilnya. `STATUS_KEPEGAWAIAN` tidak
ditambah kode baru.

---

## 4. Keputusan yang milik pemilik

Rencana berjalan dengan **bawaan** bila kolom jawaban kosong.

| # | Pertanyaan | Bawaan | Akibat bila diubah | Jawaban pemilik |
|---|---|---|---|---|
| K1 | BUMN/BUMD masuk kelompok mana? | Pihak ketiga | Hanya daftar `jenis` instansi | |
| K2 | Master luar dicatat per satker internal, atau satu untuk seluruh instansi? | Per satker internal (pola isolasi yang ada) | Bila bersama: penjaga tulis super-admin, indeks unik tanpa `kode_satker`, dan pertanyaan siapa boleh mengubah catatan yang dipakai satker lain — PGW-02 s.d. 05 berubah | |
| K3 | Orang luar mendapat akses portal BMN Saya? | Tidak | Paket tersendiri (X3) | |
| K4 | Tenaga alih daya yang sudah tercatat internal dipindah ke pihak ketiga? | Tidak | Butuh fitur pindah ranah (X5) | |
| K5 | NIK orang pihak ketiga wajib? | Opsional; tanpa nomor ia tak bisa jadi pemegang aset tertaut (2.3) | Validasi keras di PGW-03 | |
| K6 | Urutan modul yang ditautkan ke master instansi (PGW-10) | Penggunaan/BAST → Pemeliharaan → Pengadaan → Pemanfaatan → Pemindahtanganan → Persediaan | Hanya urutan PR | |
| K7 | Orang luar boleh jadi pejabat di Referensi Pejabat? | Tidak | `PejabatPage` memuat direktori gabungan | |
| K8 | Tab data pribadi (agama, perkawinan, NPWP, rekening, pendidikan) ditampilkan untuk orang luar? | Ya — mengikuti arahan "struktur sama"; semuanya opsional | Bila tidak: tab disembunyikan untuk luar, skema tetap. **Rekomendasi penyusun: sembunyikan** — tak ada keperluan BMN atas data itu, dan mengumpulkannya menambah kewajiban pelindungan data | |
| K9 | Sebutan tingkat unit pihak ketiga | "Tingkat I–V" | Hanya label layar | |

---

## 5. Model data

Semua koleksi di bawah: `id` UUID unik, `kode_satker` (pemilik catatan),
`version` (OCC), `created_at`, `updated_at`.

### 5.1 `instansi_luar`

| Field | Aturan |
|---|---|
| `kelompok` | `eksternal` \| `pihak_ketiga`. Tak boleh diubah bila sudah punya satker |
| `jenis` | Lihat 5.6; harus cocok dengan `kelompok` |
| `nama` | Wajib |
| `nama_kunci` | Turunan server: huruf kecil, tanda baca dibuang, spasi tunggal, bentuk badan usaha dinormalkan (`PT. Telkom` = `Telkom, PT`) |
| `singkatan`, `kode_referensi`, `npwp`, `alamat`, `kota`, `telepon`, `email` | Opsional. `kode_referensi` = kode BA/kode pemda/NIB, teks bebas |
| `narahubung_nama`, `narahubung_jabatan`, `narahubung_kontak` | Opsional |
| `peran` | List kode (5.6), boleh kosong |
| `aktif`, `keterangan` | |

### 5.2 `satker_luar` — padanan `satker`

| Field `satker` internal | Di `satker_luar` |
|---|---|
| `kode_satker` (identitas) | **`kode_luar`** — kode milik satker itu; opsional; teks bebas (3.4) |
| `nama_satker`, `nama_unit_organisasi`, `nama_sub_unit`, `alamat`, `telepon`, `email`, `aktif` | sama |
| `kode_satker_lengkap` | sama (kode lokasi BMN milik mereka; hanya eksternal) |
| `eselon_satker` | sama — puncak pohon unitnya; kosong = 1 |
| `tempat_laporan`, `tembusan_laporan`, `logo_url`, `judul_laporan`, `subjudul_laporan`, `tahun_anggaran`, `catatan_kaki`, `nilai_dokumen`, `header_stiker`, `penandatangan`, `eselon1` | **tidak dibawa** — setelan kop dan laporan milik satker internal |
| — | tambahan: `instansi_id`, `kelompok` (salinan dari instansinya), `nama_kunci` |

### 5.3 `unit_kerja_luar` — bentuk sama dengan `unit_kerja`

`{nama_unit, eselon "1".."5", parent_id, satker_luar_id, sumber}`. Aturan
pohon seluruhnya dari `organisasi_utils` (`validasi_unit`,
`validasi_perubahan`, `filter_jalur`, `perubahan_jalur`, `keturunan`), dengan
`akar` = `eselon_satker` milik `satker_luar`-nya.

### 5.4 `pegawai_luar` — field sama dengan `pegawai`

Seluruh field `PegawaiIn`, ditambah:

| Field | Aturan |
|---|---|
| `kelompok` | Salinan dari satkernya; tidak dikirim klien |
| `satker_luar_id` | **Wajib.** Harus milik satker pemilik yang sama |
| `instansi_id`, `instansi_nama`, `satker_luar_nama` | Diisi server dari master; ikut merambat saat instansi/satker diganti nama |

Field warisan yang maknanya perlu ditegaskan: `kode_satker` = pemilik catatan
(bukan satker tempat orang itu bekerja); `kode_satker_lengkap` = kode lokasi
BMN satker **mereka**; `eselon1..5` = nama unit pada pohon satker **mereka**.

### 5.5 Indeks, backup, GridFS

```python
for kol in ("instansi_luar", "satker_luar", "unit_kerja_luar", "pegawai_luar"):
    await _idx(db[kol], "id", unique=True)
await _idx(db.instansi_luar,
           [("kode_satker", 1), ("kelompok", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.satker_luar,
           [("kode_satker", 1), ("instansi_id", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.unit_kerja_luar, [("kode_satker", 1), ("satker_luar_id", 1)])
await _idx(db.pegawai_luar, "nip")
await _idx(db.pegawai_luar,
           [("kode_satker", 1), ("kelompok", 1), ("satker_luar_id", 1), ("nama", 1)])
# kartu: sama dengan pegawai — unik+sparse, jatuh ke non-unik bila gagal
```

- `RESET_KEEP_COLLECTIONS` ditambah keempat koleksi (master yang disusun
  manual, sekelas `pegawai`/`satker`/`unit_kerja`).
- Foto orang luar memakai `metadata.jenis` **`foto_pegawai_luar`** dan
  **`foto_pegawai_luar_asli`**; keduanya ditambahkan ke
  `RESET_KEEP_GRIDFS_JENIS`. Tidak didaftarkan sebagai sumber
  `webp_converter` (gerbang `tulis_media` sudah mengompresi saat tulis).

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
        "badan_usaha_swasta": "Badan Usaha Swasta",
        "bumn_bumd": "BUMN/BUMD",            # K1
        "koperasi": "Koperasi",
        "yayasan_ormas": "Yayasan/Organisasi Masyarakat",
        "lembaga_internasional": "Lembaga Internasional",
        "perorangan": "Perorangan",
        "lainnya": "Lainnya",
    },
}
PERAN_INSTANSI = {
    "pengguna_sementara": "Pengguna sementara BMN",
    "pengoperasi": "Mengoperasikan BMN (pihak lain)",
    "mitra_pemanfaatan": "Mitra pemanfaatan (sewa/pinjam pakai/KSP/BGS-BSG/KSPI)",
    "penerima_pemindahtanganan": "Penerima pemindahtanganan (hibah/penjualan/tukar)",
    "penyedia": "Penyedia barang/jasa",
    "pelaksana_pemeliharaan": "Pelaksana pemeliharaan",
    "pendamping": "Tim pendamping/peneliti",
    "lainnya": "Lainnya",
}
LABEL_TINGKAT = {   # sebutan di layar; nama field tetap
    "eksternal": {"instansi": "Instansi", "satker": "Satker", "level": "Eselon"},
    "pihak_ketiga": {"instansi": "Perusahaan/Badan", "satker": "Unit/Cabang",
                     "level": "Tingkat"},
}
```

Usulan kerja; PGW-00 memeriksanya terhadap istilah di
`docs/PUSTAKA-REGULASI-BMN.md` sebelum dikunci. Tidak ada data benih instansi
— repo melarang data dummy, dan daftar kode K/L/pemda tidak boleh ditulis
dari ingatan.

### 5.7 Invarian

1. Setiap `pegawai_luar` menunjuk `satker_luar` yang ada, pemilik sama;
   `kelompok`, `instansi_id` selalu sama dengan milik satkernya.
2. `kelompok == "pihak_ketiga"` ⇒ `status_kepegawaian == "non_asn"` dan
   tujuh field di 3.7 kosong.
3. NIP unik per satker pemilik **lintas** `pegawai` dan `pegawai_luar` —
   ditegakkan di sisi luar (buat/ubah/impor menolak NIP yang sudah ada di
   salah satunya). Sisi internal tidak diubah; bila kelak NIP yang sama
   didaftarkan di internal, urutan menang 3.6 yang berlaku.
4. Satu kartu tap tidak boleh terdaftar pada dua orang luar, dan pendaftaran
   di sisi luar menolak kartu yang sudah milik pegawai internal.
5. `kode_satker` pada keempat koleksi tidak pernah kosong.
6. Tak ada jalur di modul luar yang menulis ke `pegawai`, `unit_kerja`,
   `satker`, atau `assets`.

---

## 6. Kontrak API

Semua rute di bawah **baru**. Tak satu pun rute yang ada berubah.

### 6.1 Instansi & satker luar (`backend/routes/organisasi_luar.py`)

| Rute | Penjaga | Catatan |
|---|---|---|
| `GET /luar/referensi` | `require_user` | `kelompok`, `jenis_instansi`, `peran_instansi`, `label_tingkat` |
| `GET /luar/instansi?kelompok=&q=&aktif=` | `require_user` + scope | Tiap item + `jumlah_satker`, `jumlah_pegawai` (agregasi, bukan N kueri) |
| `POST /luar/instansi` | `require_admin_satker` | Payload memuat `satker_pertama` (nama) — instansi dan satker pertamanya dibuat bersama |
| `PUT /luar/instansi/{id}` | + `pastikan_akses_dok_satker`, `If-Match` | Ganti nama → rambatkan `instansi_nama` ke `pegawai_luar` |
| `DELETE /luar/instansi/{id}` | sama | 409 bila masih punya satker berpegawai |
| `GET /luar/satker?instansi_id=` | `require_user` + scope | + `jumlah_pegawai`, `level_akar` |
| `POST /luar/satker`, `PUT /luar/satker/{id}`, `DELETE /luar/satker/{id}` | seperti instansi | Ganti nama → rambatkan `satker_luar_nama`. Hapus 409 bila masih berpegawai/ber-unit |

### 6.2 Unit kerja luar (`backend/routes/unit_kerja_luar.py`)

Cermin `routes/unit_kerja.py`, semua ber-`satker_luar_id` wajib:
`GET /unit-kerja-luar`, `POST`, `PUT /{id}`, `DELETE /{id}`,
`POST /unit-kerja-luar/bangun-dari-pegawai`.

Beda yang disengaja: `cocokkan-lingkup` **tidak ada** (lingkup kegiatan hanya
internal); ganti nama merambat ke `pegawai_luar` **saja** — tidak pernah ke
`assets`.

### 6.3 Pegawai luar (`backend/routes/pegawai_luar.py`)

Cermin `routes/pegawai.py`. Saringan lingkup lewat kueri: `kelompok` (wajib
pada daftar), `instansi_id`, `satker_luar_id` (opsional kecuali disebut).

| Rute internal | Padanan luar | Catatan |
|---|---|---|
| `GET /pegawai` | `GET /pegawai-luar` | + `kelompok`, `instansi_nama`, `satker_luar_nama`; `info_masa` sama |
| `GET /pegawai/rekap-unit` | `GET /pegawai-luar/rekap-unit` | `satker_luar_id` wajib |
| — | `GET /pegawai-luar/rekap-lingkup?kelompok=` | Baru: cacah per instansi & satker, untuk bilah lingkup |
| `GET /pegawai/perlu-serah-terima` | `GET /pegawai-luar/perlu-serah-terima` | Pakai `_jumlah_aset_per_nip` yang sama |
| `GET /pegawai/{id}/aset` | `GET /pegawai-luar/{id}/aset` | |
| `POST /pegawai`, `PUT`, `DELETE` | `POST /pegawai-luar`, `PUT`, `DELETE` | `_bersih` + `validate_pegawai` yang sama, lalu `sesuaikan_pegawai_luar` |
| `GET /pegawai/template-impor`, `export-xlsx`, `POST /pegawai/impor` | padanan `/pegawai-luar/…` | Header **sama persis** (`HEADER_IMPOR`); ekspor dan impor wajib `satker_luar_id` (satu berkas = satu satker) |
| `POST/GET/DELETE /pegawai/{id}/foto`, `foto-asli` | padanan | `jenis` GridFS berbeda (5.5) |
| `POST/DELETE /pegawai/{id}/kartu` | padanan | Cek silang kartu ke `pegawai` |

### 6.4 Pengecualian kesetaraan (terdaftar di uji kesetaraan)

| Rute internal tanpa padanan luar | Alasan |
|---|---|
| `/pegawai/referensi`, `/pegawai/deteksi-identitas` | Tidak ber-data; layar luar memakai rute yang sama |
| `/pegawai/{id}/sinkron-aset` (+ pratinjau) | Menulis ke `assets` dan membawa isu 2.9 |
| `/pegawai/kartu/identifikasi` | Digantikan identifikasi gabungan (6.5) |

### 6.5 Direktori gabungan (`backend/direktori_pegawai.py` + rute)

| Rute | Catatan |
|---|---|
| `GET /direktori-pegawai?kelompok=semua\|internal\|eksternal\|pihak_ketiga` | Hanya baca. Gabungan `pegawai` + `pegawai_luar`, keduanya ter-scope satker. Field ringkas untuk pemilih: `id`, `ranah` (`internal`/`luar`), `kelompok`, `nama`, `nip`, `jabatan`, `unit_kerja`, `unit_organisasi`, `email`, `alamat`, `status`, `status_kepegawaian`, `foto_file_id`, `instansi_nama`, `satker_luar_nama` |
| `POST /direktori-pegawai/kartu/identifikasi` | Cari di `pegawai` dulu, lalu `pegawai_luar`; batas laju dan audit sama dengan rute internal |

Pembantu Python untuk pemanggil backend:

```python
async def cari_orang(scope_query, nip) -> dict | None      # + "ranah", "kelompok"
async def cari_orang_banyak(scope_query, nips) -> dict     # {nip: dok}; dua kueri $in
```

`scope_query` diserahkan pemanggil (pola `penerima_utils.periksa_penerima`),
tidak disimpulkan.

---

## 7. Peta perubahan

### 7.1 Yang TIDAK berubah

`routes/pegawai.py`, `routes/unit_kerja.py`, `routes/satker.py`,
`portal_auth.py`, `portal_bast.py`, `routes/portal_*.py`,
`webp_converter.py`, koleksi `pegawai`/`unit_kerja`/`satker`, `GET /pegawai`
dan `GET /unit-kerja` beserta bentuk jawabannya, `HEADER_IMPOR`, `const EMPTY`
di `PegawaiPage.jsx`.

Akibat yang disengaja: orang luar tidak mendapat akses portal (K3), tidak
muncul di pemilih pejabat (K7), dan BAST kepada orang luar tetap ditinjau
petugas seperti hari ini (X2).

### 7.2 Pembaca backend yang ikut mengenali orang luar (aditif)

Masing-masing mengganti satu pencarian NIP di `db.pegawai` dengan
`cari_orang`/`cari_orang_banyak`. Bila satu terlewat, akibatnya sama dengan
keadaan hari ini.

| Berkas → fungsi | Yang berubah |
|---|---|
| `shared_utils.py` → `status_kepegawaian_by_nip` | Jatuh ke `pegawai_luar` setelah pejabat dan pegawai |
| → `enforce_pegawai_terdaftar` | Cek "meninggal" dan "terdaftar" mengenali orang luar |
| `penerima_utils.py` → `periksa_penerima`, `snapshot_penerima` | Mengenali orang luar; snapshot + `penerima_kelompok`, `penerima_instansi` |
| `routes/bast.py` → cek PIHAK KESATU meninggal | Mengenali orang luar |
| `routes/ttd.py` → dua cek penanda tangan meninggal | Mengenali orang luar |
| `routes/imports.py` → `nip_terdaftar` | Gabungan `distinct` kedua koleksi |
| `routes/penggunaan.py` → `daftar_pemegang` (pengaya) | + `pegawai_master_kelompok`, `pegawai_master_instansi` |
| `routes/reports.py` → `_peta_status_kepegawaian`, Laporan Eksekutif `peg_master` | Mengenali orang luar; pengelompokan tersendiri (PGW-09) |
| `routes/wasdal.py` → pegawai berisiko | Ikut membaca `pegawai_luar` |

### 7.3 Frontend

| Berkas | Perubahan | Paket |
|---|---|---|
| `pages/PegawaiPage.jsx` | Tiga tab; jalur API lewat objek ranah; tab internal mengirim permintaan yang sama persis | PGW-07 |
| `components/assets/AssetForm.jsx` | Pemilih & peringatan "belum terdaftar" membaca direktori gabungan | PGW-08 |
| `components/penggunaan/PilihPegawaiBast.jsx`, `pages/PenggunaanPage.jsx` | Direktori gabungan + lencana + instansi | PGW-08 |
| `pages/PersediaanPage.jsx`, `lib/penerimaPersediaan.js` | Direktori gabungan | PGW-08 |
| `pages/PemeliharaanPage.jsx`, `pages/TtdPermintaanPage.jsx` | Direktori gabungan | PGW-08 |
| `pages/ActivitySelectionPage.jsx` | Tim inti/pembantu tetap `/pegawai`; tim peneliti/pendukung direktori gabungan, `dari_pihak` terisi instansi | PGW-08 |
| `components/pegawai/KartuTapDialog.jsx` | Identifikasi gabungan; tampilkan lencana + instansi | PGW-08 |
| `pages/PejabatPage.jsx`, `components/penggunaan/PortalPemegangPanel.jsx` | **Tidak berubah** (K7, K3) | — |

---

## 8. Paket kerja

### Status

| Paket | Isi | Bergantung | Status | PR |
|---|---|---|---|---|
| PGW-00 | Regulasi & kontrak modul | — | belum | |
| PGW-01 | Fondasi murni | 00 | belum | |
| PGW-02 | Master instansi & satker luar (backend) | 01 | belum | |
| PGW-03 | Pegawai luar (backend) | 02 | belum | |
| PGW-04 | Impor/ekspor/template pegawai luar | 03 | belum | |
| PGW-05 | Unit kerja luar (backend) | 03 | belum | |
| PGW-06 | Direktori gabungan + pembaca backend | 03 | belum | |
| PGW-07 | Layar Master Pegawai | 03, 04, 05 | belum | |
| PGW-08 | Pemilih lintas modul | 06 | belum | |
| PGW-09 | Laporan & dokumen | 06 | belum | |
| PGW-10 | Tautan instansi di modul berpihak-luar | 02, 07 | belum | |
| PGW-11 | Data uji & dokumentasi | 07–09 | belum | |

PGW-04, 05, 06 boleh paralel setelah PGW-03. Sampai PGW-07 ter-merge,
pengguna tidak melihat perubahan apa pun — itu disengaja.

---

### PGW-00 — Regulasi & kontrak modul (dokumen saja)

1. Tambah bagian di `docs/PUSTAKA-REGULASI-BMN.md` (dekat §2.4c): definisi
   tiga kelompok (3.2) dan dasar hubungan tiap kelompok dengan BMN. Mulai
   dari yang sudah ada di pustaka (penggunaan sementara, dioperasikan pihak
   lain, pemanfaatan, pemindahtanganan), lalu riset yang belum tercakup.
   Bersumber; yang tak terverifikasi ditandai "perlu verifikasi".
2. Tiga pertanyaan yang wajib dijawab:
   - Apakah jam 3 tahun pemberitahuan ahli waris (UU 1/2004 Ps. 66 ayat (2),
     dipakai `info_kewajiban_ahli_waris`) berlaku bagi orang luar? Sampai
     terjawab, layar luar **tidak** menampilkan jam itu.
   - Siapa yang sah menandatangani serah terima BMN kepada pihak di luar
     satker, dan apakah jenis BAST yang ada memadai? (bahan X2)
   - Batas pengumpulan data pribadi orang luar menurut UU 27/2022 — repo
     sudah merujuknya di `docs/DPIA-PELACAKAN-ASET.md`. Hasilnya bahan K8.
3. Tambah kontrak di `docs/MASTERPLAN-SIKLUS-BMN.md`: master luar dibaca
   modul mana, ditulis siapa.
4. Kunci daftar kode 5.6.
5. Patuhi registry sitasi: nomor peraturan yang kelak **tercetak di dokumen
   keluaran** wajib terdaftar di `backend/sitasi_regulasi.py`; status
   "terverifikasi" menuntut naskahnya di `docs/regulasi/` (ditagih
   `test_sitasi_regulasi.py`). Rencana ini tidak menambah sitasi ke dokumen
   keluaran mana pun.

**Terima:** bagian pustaka ada, bersumber, dan ketiga pertanyaan berjawaban
atau bertanda "perlu verifikasi" dengan bawaan yang dipakai.

---

### PGW-01 — Fondasi murni

**Berkas baru:** `backend/organisasi_luar_utils.py`,
`backend/tests/unit/test_organisasi_luar_utils.py`.

```python
KELOMPOK_LUAR, JENIS_INSTANSI, PERAN_INSTANSI, LABEL_TINGKAT     # 5.6
FIELD_KOSONG_PIHAK_KETIGA = ("pangkat_golongan", "kategori_pegawai",
    "status_pegawai_satker", "status_pegawai_instansi", "kode_satker_lengkap",
    "jenis_kontrak_non_asn", "perusahaan_penyedia")

def nama_kunci(nama) -> str: ...
def validate_instansi_luar(doc) -> list[str]: ...
def validate_satker_luar(doc) -> list[str]: ...
def bersihkan_instansi_luar(payload) -> dict: ...
def bersihkan_satker_luar(payload) -> dict: ...
def sesuaikan_pegawai_luar(doc, kelompok) -> dict:
    # eksternal: dikembalikan APA ADANYA
    # pihak_ketiga: status_kepegawaian = "non_asn"; FIELD_KOSONG_… dikosongkan
def label_unit_orang(doc) -> str:
    # internal: unit_kerja; luar: "instansi_nama — satker_luar_nama — unit"
```

**Uji minimum:**
- `nama_kunci("PT. Telkom Indonesia") == nama_kunci("Telkom  Indonesia, PT")`.
- `sesuaikan_pegawai_luar(doc, "eksternal") == doc` untuk dokumen penuh.
- Pihak ketiga: `status_kepegawaian` jadi `non_asn`; tujuh field kosong;
  `agama`, `eselon3`, `no_rekening`, `nomor_kontrak` **utuh**.
- Kesetaraan skema: `set(_bersih(PegawaiIn(nama="x")))` ⊇
  `FIELD_KOSONG_PIHAK_KETIGA` — nama field yang salah ketik gagal di sini.
- `jenis` yang tak cocok `kelompok` ditolak.

**Terima:** uji lulus; belum ada pemanggil → nol perubahan perilaku.

---

### PGW-02 — Master instansi & satker luar (backend)

**Berkas:** `backend/routes/organisasi_luar.py` (baru), `backend/server.py`
(impor + `include_router`), `backend/indexes.py`, `backend/backup_utils.py`,
`backend/tests/unit/test_organisasi_luar_route.py` (baru),
`backend/tests/unit/test_backup_utils.py`.

Kontrak 6.1. Periksa **lima titik isolasi** satu per satu. Pembuatan instansi
+ satker pertama: sisipkan satker dulu; bila penyisipan instansi gagal, hapus
satker itu (Mongo tanpa transaksi — jangan tinggalkan yatim).

**Uji minimum** (pola `mongomock_motor` di `test_unit_kerja_route.py`):
- Admin satker A tak dapat membaca/mengubah/menghapus milik satker B, dan
  daftar A tak memuat milik B.
- Nama instansi kembar (beda tanda baca) di satker+kelompok sama → 400; di
  satker pemilik lain → boleh.
- `POST /luar/instansi` tanpa `satker_pertama` → 400.
- Hapus instansi/satker yang masih berpegawai → 409 dengan jumlahnya.
- `PUT` dengan `If-Match` usang → 409.
- Dokumen tersimpan tidak pernah ber-`kode_satker` kosong; `kode_luar` tidak
  pernah tertulis ke `kode_satker`.
- Keempat koleksi ∈ `RESET_KEEP_COLLECTIONS`.

---

### PGW-03 — Pegawai luar (backend)

**Berkas:** `backend/routes/pegawai_luar.py` (baru), `backend/server.py`,
`backend/indexes.py`, `backend/backup_utils.py` (jenis GridFS),
`backend/tests/unit/test_pegawai_luar_route.py`,
`backend/tests/unit/test_pegawai_luar_setara.py`, dan penambahan
`routes/pegawai_luar.py` ke daftar berkas di `test_gerbang_media.py` dan
`test_penjaga_senyap.py`.

**Langkah:**

1. `PegawaiLuarIn(PegawaiIn)` + `satker_luar_id: str`.
2. Pembantu `_lingkup(user, kelompok, instansi_id, satker_luar_id) -> dict`:
   satu-satunya pembuat saringan daftar — selalu
   `scope_query_field_satker(user, {...})`.
3. Pembantu `_stempel(user, doc, satker)`: mengisi `kode_satker`,
   `satker_luar_id`, `satker_luar_nama`, `instansi_id`, `instansi_nama`,
   `kelompok` dari dokumen `satker_luar` (yang diambil **ter-scope**; tidak
   ditemukan → 400, bukan 403 — jangan membocorkan keberadaannya).
4. Buat/ubah: `_bersih(payload)` → `validate_pegawai` →
   `sesuaikan_pegawai_luar` → `_stempel` → cek NIP di **kedua** koleksi
   (invarian 3) → tulis ber-OCC (pola `ubah_pegawai`) → `log_audit`
   (`buat_pegawai_luar`, `ubah_pegawai_luar`, `hapus_pegawai_luar`).
5. Daftar: `info_masa_pegawai` yang sama; turunan `unit_kerja` dari eselon
   yang sama.
6. Hapus: tolak 409 bila NIP-nya masih dipakai aset (pola `hapus_pegawai`).
7. Foto: salin alur `upload_foto_pegawai` dengan `jenis`
   `foto_pegawai_luar`/`foto_pegawai_luar_asli`; **wajib** lewat
   `tulis_media`; get-by-id dijaga `pastikan_akses_dok_satker`.
8. Kartu: daftar/lepas seperti internal + cek silang ke `db.pegawai`
   (invarian 4).
9. `perlu-serah-terima`, `{id}/aset`: pakai `_jumlah_aset_per_nip` dan
   `pegawai_perlu_serah_terima` yang sama.
10. **Tidak ada** pemanggilan `portal_auth` di modul ini.

**Uji kesetaraan** (`test_pegawai_luar_setara.py`):
- Himpunan akhiran rute `pegawai_luar_router` == himpunan akhiran rute
  `pegawai_router` dikurangi `PENGECUALIAN_SETARA` (6.4) ditambah
  `rekap-lingkup`. Dibaca dari `router.routes`, bukan dari teks.
- `PegawaiLuarIn.model_fields` ⊇ `PegawaiIn.model_fields`.
- Sumber `routes/pegawai_luar.py` memuat pemanggilan `validate_pegawai(`,
  `_bersih(`, `info_masa_pegawai(`, `tulis_media(`.
- **Larangan tulis:** sumber modul luar tidak cocok dengan
  `db\.(pegawai|unit_kerja|satker|assets)\.(insert|update|delete|bulk_write|replace)`.
- **Larangan balik:** `routes/pegawai.py`, `routes/unit_kerja.py`,
  `routes/satker.py` tidak memuat kata `_luar`.

**Uji rute minimum:** invarian 5.7 butir 1–5 masing-masing satu uji; pihak
ketiga dengan `status_kepegawaian: "pns"` tersimpan `non_asn`; eksternal
dengan payload penuh tersimpan sama dengan `_bersih`-nya; isolasi A/B; NIP
yang sudah ada di `pegawai` satker yang sama → 400 menyebut "pegawai
internal".

**Terima:** seluruh `test_pegawai_*`, `test_portal_*`, `test_unit_kerja_*`
lama lulus tanpa disunting; `git diff --stat` tidak memuat
`routes/pegawai.py`.

---

### PGW-04 — Impor/ekspor/template pegawai luar

**Berkas:** `backend/routes/pegawai_luar.py`,
`backend/tests/unit/test_pegawai_luar_impor.py`, penambahan
`("pegawai_luar.py", "_baris_dari_unggahan_pegawai")` ke daftar di
`test_cpu_sinkron_di_thread.py`.

1. **Header sama persis:** `HEADER_IMPOR`, `baris_ekspor_pegawai`,
   `baris_impor_ke_pegawai`, `OPSI_DROPDOWN_EKSPOR` dipakai apa adanya.
   `pegawai_utils.py` tidak disunting.
2. Template: sama dengan internal; nama berkas
   `template_impor_pegawai_luar.csv`.
3. Ekspor: `_build_pegawai_xlsx` yang sama lewat `run_renderer`, tanpa
   pembungkus. `satker_luar_id` **wajib** — satu berkas = satu satker,
   sebagaimana ekspor internal = satu satker. Nama berkas memuat nama satker.
   Tidak ada ekspor multi-satker: berkas seperti itu akan tampak bisa diimpor
   padahal impor menuang semua barisnya ke satu satker.
4. Impor: `satker_luar_id` wajib (`Form`). Parsing di thread
   (`asyncio.to_thread(_baris_dari_unggahan_pegawai, …)`). Per baris:
   `baris_impor_ke_pegawai` → `validate_pegawai` (keluhan NIP disaring,
   seperti internal) → `sesuaikan_pegawai_luar` → `kunci_dedup_pegawai` →
   gabung baris berkunci sama (`gabung_baris_pegawai`).
   - Muat pembanding **sekali**: `pegawai_luar` satker itu, NIP seluruh
     `pegawai_luar` pemilik, dan NIP `pegawai` pemilik. NIP yang sudah ada di
     internal atau di satker luar lain → baris dilewati dengan catatan yang
     menyebut tempatnya.
   - Saringan dedup selalu memuat `kode_satker` pemilik **dan**
     `satker_luar_id`.
   - `$set` hanya field yang dipasok baris; sisanya `$setOnInsert` (pola
     `impor_pegawai`). Stempel lingkup selalu di `$setOnInsert`.

**Uji minimum:** pulang-pergi ekspor → impor untuk eksternal dan pihak
ketiga; impor ulang berkas yang sama tidak menggandakan; berkas berisi NIP
pegawai internal → internal tak berubah sedikit pun; impor pihak ketiga
dengan kolom Pangkat terisi → tersimpan kosong; berkas satker luar A yang
diimpor ke satker luar B → baris ber-NIP ditolak dengan catatan menyebut
satker A; ekspor/impor tanpa `satker_luar_id` → 400.

---

### PGW-05 — Unit kerja luar (backend)

**Berkas:** `backend/routes/unit_kerja_luar.py` (baru), `backend/server.py`,
`backend/indexes.py`, `backend/tests/unit/test_unit_kerja_luar_route.py`.

Kontrak 6.2. Seluruh aturan pohon dari `organisasi_utils`; derivasi dari
`unit_kerja_utils.unit_dari_pegawai`. `akar` dibaca dari
`satker_luar.eselon_satker` lewat `organisasi_utils.level_akar`.

Perambatan ganti nama: `update_many` pada `pegawai_luar` dengan saringan
`scope_query_field_satker(user, {satker_luar_id, **filter_jalur})`. **Tidak
ada** `update_many` ke `assets` — jalur eselon aset adalah unit internal.

**Uji minimum:** semua kasus `test_unit_kerja_route.py` yang relevan,
disalin untuk lingkup luar; ganti nama unit di satker luar X tidak mengubah
pegawai luar satker Y yang unitnya senama; koleksi `pegawai`, `unit_kerja`,
`assets` **tidak berubah sama sekali** sesudah setiap operasi (bandingkan
isi sebelum–sesudah); isolasi A/B.

---

### PGW-06 — Direktori gabungan + pembaca backend

**Berkas:** `backend/direktori_pegawai.py` (baru),
`backend/routes/direktori_pegawai.py` (baru), `backend/server.py`, sembilan
titik di Bab 7.2, `backend/tests/unit/test_direktori_pegawai.py`, perluasan
`test_penerima_persediaan.py`.

1. `cari_orang`, `cari_orang_banyak` (6.5) — urutan menang: internal dulu.
2. Rute `GET /direktori-pegawai` dan identifikasi kartu gabungan. Yang
   terakhir menyalin batas laju dan audit "kartu tak dikenal" dari rute
   internal.
3. Sunting sembilan pembaca, **satu komit per berkas**, masing-masing dengan
   uji "orang luar terdaftar kini dikenali" dan uji "perilaku untuk orang
   internal tidak berubah".
4. `enforce_pegawai_terdaftar`: hari ini tanpa scope satker. Pertahankan
   semantik itu untuk kedua koleksi — jangan menambah scope di paket ini.

**Terima:** uji lama modul-modul itu lulus tanpa disunting.

---

### PGW-07 — Layar Master Pegawai

**Berkas:** `frontend/src/pages/PegawaiPage.jsx`,
`frontend/src/lib/ranahPegawai.js` (+ uji),
`frontend/src/components/pegawai/BilahLingkupLuar.jsx`,
`frontend/src/components/pegawai/KelolaOrganisasiLuar.jsx`,
`frontend/src/components/pegawai/LencanaKelompok.jsx`,
`frontend/src/pages/__tests__/PegawaiKelompok.test.jsx`.

1. `lib/ranahPegawai.js` (murni): tiga objek ranah.
   ```js
   { kunci: "internal", apiPegawai: "/pegawai", apiUnit: "/unit-kerja",
     params: () => ({}), label: {...} }
   { kunci: "eksternal", apiPegawai: "/pegawai-luar", apiUnit: "/unit-kerja-luar",
     params: (l) => ({ kelompok: "eksternal", instansi_id: l.instansiId,
                       satker_luar_id: l.satkerId }), label: {...} }
   ```
   Label dibaca dari `GET /luar/referensi` (`label_tingkat`); berkas ini
   hanya memuat bawaan untuk keadaan belum-termuat.
2. **Ganti 22 literal `${API}/pegawai` dan 5 literal `${API}/unit-kerja`** di
   `PegawaiPage.jsx` dengan jalur dari ranah aktif — termasuk `AvatarPegawai`
   (URL foto), tombol template/ekspor, dan pratinjau foto. Untuk ranah
   internal hasilnya string yang sama persis.
3. **Pemilih kelompok** di bawah kepala halaman: Internal · Instansi
   Eksternal · Pihak Ketiga. `data-testid="pegawai-kelompok-<kunci>"`. Tinggi
   ≥ 44px di ≤ 1023px. Efek muat ulang **wajib** memuat ranah dan lingkup di
   deps.
4. **Bilah lingkup** (hanya tab luar): pilih instansi → pilih satker, dengan
   cacah dari `rekap-lingkup`, plus tombol "Kelola". Tanpa satker terpilih,
   daftar menampilkan seluruh satker instansi itu; tombol Tambah, Impor,
   Ekspor, Struktur Organisasi, dan Kelola Unit **nonaktif** sampai satu
   satker dipilih (dengan keterangan kenapa).
5. `KelolaOrganisasiLuar.jsx` — komponen **level modul**: dua tingkat
   (instansi → satker); tambah/ubah/nonaktifkan/hapus; `If-Match`; pesan 409
   server ditampilkan apa adanya.
6. **Form sama.** `EMPTY` tidak berubah. Penyesuaian per kelompok lewat
   label dan penyembunyian: pihak ketiga menyembunyikan tujuh field 3.7 dan
   mengunci Status Kepegawaian ke Non-ASN; sebutan Eselon → Tingkat (K9).
   `satker_luar_id` dikirim dari lingkup aktif, bukan dari isian form.
7. Tab luar: tombol "Sinkron aset" tidak ada (6.4); jam ahli waris tidak
   ditampilkan (PGW-00).
8. Daftar dirender dua kali (kartu HP dan tabel desktop) — ubah keduanya;
   baris luar menampilkan satker bila lingkupnya satu instansi penuh.
9. Aturan tampilan: `hover:bg-muted`; uji terang dan gelap; jangan
   memperkecil tombol.

**Uji minimum (Jest):**
- **Regresi internal:** dengan tab internal, himpunan URL yang dipanggil
  sama dengan sebelum paket (bekukan daftar URL di uji).
- Tab eksternal memanggil `/pegawai-luar` dengan `kelompok=eksternal`.
- Tanpa satker terpilih, tombol Tambah nonaktif.
- Form pihak ketiga tidak merender field Pangkat/Golongan.
- `PegawaiAkarEselon.test.jsx` lama lulus tanpa disunting.
- Backend `test_pegawai_cakupan_ekspor.py` lulus tanpa disunting (`EMPTY`
  tidak berubah).

**Terima:** `yarn lint` tanpa galat baru; `CI=true yarn test
--watchAll=false`; `CI=false yarn build`; periksa manual HP dan desktop,
terang dan gelap.

---

### PGW-08 — Pemilih lintas modul

Tiap berkas di Bab 7.3 berpindah dari `GET /pegawai` ke
`GET /direktori-pegawai?kelompok=semua`, menampilkan `LencanaKelompok` dan
instansi pada baris orang luar. Foto: jalur dipilih dari `ranah`.

- `pihakDariPegawai` (`PilihPegawaiBast.jsx`): untuk orang luar `alamat` =
  alamat orangnya, jatuh ke "instansi — satker".
- `AssetForm.jsx`: di dalam `FullCameraSheet` tetap elemen native.
- Offline: direktori gagal dimuat → perilaku "ketik manual" yang ada.
- Lima berkas uji Jest me-mock URL `/pegawai`; perbarui mock yang berkasnya
  disentuh — sumber kegagalan uji paling mungkin di paket ini.

Boleh dipecah 08a (aset + BAST) dan 08b (sisanya).

---

### PGW-09 — Laporan & dokumen

1. **Laporan Eksekutif — Distribusi Per Pengguna** (`routes/reports.py`
   sekitar `peg_master`, `report_utils.distribusi_pengguna`,
   `laporan_jenjang.baris_hierarki_pengguna`): pengguna luar membawa jalur
   eselon organisasi **lain** — jangan dilebur ke pohon satker sendiri.
   Tempatkan di pembagi tersendiri sesudah pengguna internal: "Instansi
   Eksternal" → instansi → satker, lalu "Pihak Ketiga" → instansi → satker.
   Urutan dan isi baris pengguna internal tidak berubah.
2. **Rekap pemegang / daftar per pemegang PDF:** kolom unit memakai
   `label_unit_orang`.
3. **Wasdal:** temuan "pemegang berisiko" menyebut kelompok + instansi; untuk
   orang luar "kontrak berakhir" berbunyi "masa hubungan berakhir".
4. **BAST:** tanpa perubahan tata letak. Snapshot pihak menyimpan `kelompok`,
   `instansi_nama` sebagai field opsional yang dibekukan saat terbit.
5. Aturan blok tanda tangan tidak berubah: tetap `baris_identitas_ttd`.

**Uji:** `test_laporan_eksekutif_pengguna_jenjang.py` diperluas; total tidak
berubah; laporan yang seluruh penggunanya internal menghasilkan baris yang
sama persis dengan sebelum paket. Smoke-render PDF dengan harness FakeDB.

---

### PGW-10 — Tautan instansi di modul berpihak-luar (opsional, satu PR per modul)

Urutan K6. Pola aditif: kolom teks yang ada (`pihak`, `mitra`, `penyedia`, …)
**tetap disimpan** sebagai snapshot; tambah field opsional
`<kolom>_instansi_id`; layar memakai masukan teks ber-datalist dari
`GET /luar/instansi` (pola `penerimaPersediaan.js`); server memvalidasi id
ter-scope; tanpa backfill.

---

### PGW-11 — Data uji & dokumentasi

- `backend/scripts/synthdata/generator.py`: pembangkit instansi, satker, dan
  pegawai luar; perbarui `test_synthdata_generator.py` dan skill
  `aman-testdata`.
- `README.md`, `frontend/src/pages/InfoPage.jsx`, `frontend/src/lib/bmnModules.js`.
- `.claude/skills/aman-dev/SKILL.md`: baris "Peta repo" untuk modul luar +
  tiga aturan di "Aturan main" dokumen ini.
- `CHANGELOG.md`: tiap PR mengisi entrinya. Penomoran mengikuti **kepala
  CHANGELOG.md** (pada baseline: nomor entri = nomor PR + 9; angka "+2" di
  skill sudah usang).

---

### Ditunda (butuh keputusan pemilik tersendiri)

| Kode | Isi | Kenapa ditunda |
|---|---|---|
| X1 | FK `pengguna_pegawai_id` pada aset | Menyentuh registry field aset dan antrean offline |
| X2 | Jenis BAST & pasal khusus pihak luar; otomasi amanah BAST untuk penerima luar | Bergantung riset PGW-00; menyentuh `portal_bast` |
| X3 | Portal BMN Saya untuk orang luar | Email di luar kendali instansi |
| X4 | Perbaikan `pengguna_melekat_ke` (2.9) | Isu lama, bukan bagian permintaan |
| X5 | Pindah ranah internal ↔ luar dengan `id` tetap | Jarang; perlu aturan untuk BAST/portal yang merujuk `id` |
| X6 | Refaktor inti bersama rute pegawai (3.5) | Mengubah berkas internal |
| X7 | Spesimen TTD untuk orang luar (`routes/ttd.py` `_ENTITAS`) | Belum ada kebutuhan yang disebut |

---

## 9. Jebakan khusus fitur ini

1. **`kode_satker` ≠ kode satker mereka.** Lihat 3.4. Uji PGW-02 menagihnya.
2. **Jenis GridFS foto.** Foto orang luar dengan `jenis: "foto_pegawai"`
   dianggap milik `db.pegawai` oleh pengonversi WebP dan tidak menemukan
   pemiliknya. Pakai `foto_pegawai_luar`.
3. **Perambatan nama unit luar tidak boleh menyentuh `assets`.** Rute
   internal merambat ke aset; salinan mentahnya ke modul luar akan mengubah
   jalur eselon aset satker sendiri bila kebetulan senama.
4. **`scope_query_field_satker` meloloskan `kode_satker` kosong.** Dokumen
   luar tanpa kode tampil di semua satker. Tulis lewat `require_admin_satker`.
5. **Satu orang di dua master.** Sisi luar menolak NIP yang sudah ada di
   internal, tetapi sisi internal tidak diubah. Bila kelak NIP yang sama
   masuk internal, pencarian mengembalikan yang internal; catatan luarnya
   tinggal dihapus admin.
6. **Daftar dirender dua kali** (kartu HP + tabel desktop).
7. **Impor adalah jalur tulis yang melewati form.** `sesuaikan_pegawai_luar`
   dan stempel lingkup wajib dipanggil per baris.
8. **Jangan menambah ekspor multi-satker.** Berkasnya akan tampak bisa
   diimpor, padahal impor menuang semua baris ke satu satker.
9. **`validate_pegawai` di impor menyaring pesan yang memuat "NIP".** Pesan
   baru yang bukan tentang NIP jangan memuat kata itu.
10. **Mengimpor pembantu privat** (`_bersih`, `_build_pegawai_xlsx`, …) dari
    `routes/pegawai.py` mengikat modul luar pada nama-nama itu. Itu
    disengaja; bila internal kelak menggantinya, impor yang gagal adalah
    sinyalnya.

---

## 10. Verifikasi

### Tiap paket

Lingkungan sesi baru belum tentu punya `pytest`/`mongomock_motor`; pasang
dulu dengan `pip install -r backend/requirements-dev.txt`.

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
`test_unit_kerja_*.py`, `test_satker_*.py`. Yang boleh **ditambah barisnya**
(bukan diubah maknanya): daftar berkas di `test_gerbang_media.py`,
`test_penjaga_senyap.py`, `test_cpu_sinkron_di_thread.py`, dan
`test_backup_utils.py`.

### Uji terima akhir (setelah PGW-09, di lingkungan uji — bukan produksi)

1. Tab internal: lakukan tambah, ubah, impor, ekspor — hasilnya sama dengan
   sebelum fitur ini.
2. Buat "Kementerian X" + satker "Kantor Y" (eksternal) dan "PT Z" + unit
   "Kantor Pusat" (pihak ketiga).
3. Tambah satu orang di tiap satker itu; isi eselon; "Bangun unit dari
   pegawai" menghasilkan pohon di satker luar itu saja — master unit internal
   tidak bertambah.
4. Ekspor satu satker luar → ubah satu sel → impor → hanya sel itu berubah.
5. Impor berkas pihak ketiga yang memuat NIK pegawai internal → ditolak per
   baris, internal utuh.
6. Di form aset, pemilih pengguna menampilkan orang luar dengan lencana;
   memilihnya tidak memunculkan peringatan "belum terdaftar".
7. Set `tgl_selesai_kontrak` orang luar pemegang aset ke kemarin → muncul di
   "perlu serah terima" tab luar dan temuan Wasdal.
8. Login admin satker lain → tak satu pun data luar di atas terlihat.
9. Pemilih pejabat dan panel portal tidak menampilkan orang luar.
10. Laporan Eksekutif: orang luar di pembagi instansi; total sama.
11. Cetak BAST dengan pihak ketiga ber-NIK → blok tanda tangan nama saja.

### Definisi selesai

CI hijau · terdeploy · UI Indonesia · CHANGELOG terisi · status Bab 8
diperbarui · tanpa uji lama yang dilonggarkan · tiga berkas rute internal
tanpa diff.

---

## 11. Risiko dan yang belum terverifikasi

| # | Risiko / ketidakpastian | Keyakinan | Mitigasi |
|---|---|---|---|
| R1 | Penangan rute luar menyimpang dari internal seiring waktu | Tinggi bahwa ini harga utama desain koleksi sejajar | Uji kesetaraan (PGW-03); logika murni dipakai bersama; X6 bila mulai memberatkan |
| R2 | K2 (pemilik catatan per satker) ternyata tidak sesuai cara kerja pemilik | Sedang — belum dijawab | Diputuskan sebelum PGW-02; mengubahnya sesudah ada data berarti migrasi |
| R3 | `PegawaiPage.jsx` (1.954 baris) sulit disunting aman | Tinggi | Penggantian jalur API mekanis + uji regresi URL; komponen baru di level modul |
| R4 | Dasar hukum per kelompok (ahli waris, penanda tangan BAST pihak luar, batas data pribadi) | **Rendah — belum diriset** | PGW-00; bawaan konservatif |
| R5 | Mengumpulkan data pribadi orang luar tanpa keperluan BMN (K8 bawaan "ya") | Sedang | Semua field opsional; rekomendasi menyembunyikan tab; diputuskan pemilik |
| R6 | Orang pihak ketiga tanpa NIK tak bisa jadi pemegang tertaut | Tinggi (sifat desain, 2.3) | Disebut terang di layar; X1 |
| R7 | Daftar `JENIS_INSTANSI`/`PERAN_INSTANSI` tidak cocok istilah resmi | Sedang | Dikunci di PGW-00 |
| R8 | Sembilan pembaca di 7.2 tidak lengkap | Sedang — hasil `grep` pada baseline | Yang terlewat berakibat sama dengan hari ini; bisa ditambah kapan saja |
| R9 | Temuan 2.9 ternyata disengaja | Sedang | Tidak diubah; hanya dilaporkan |

Dokumen ini tidak mengutip nomor pasal selain yang sudah tertulis di kode dan
`docs/` repo. Klaim regulasi baru harus melalui PGW-00 dan masuk pustaka
beserta sumbernya.
