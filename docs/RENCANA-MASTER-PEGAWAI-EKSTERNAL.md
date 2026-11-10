# Rencana: Master Pegawai Tiga Kelompok — Internal, Instansi Eksternal, Pihak Ketiga

> **Status:** rencana, belum ada kode yang diubah.
> **Baseline:** `main` pada commit `7d1af3e` (PR #1111), 10 November 2026.
> **Pelaksana yang dituju:** Opus 5.5 (atau model/orang lain) — dokumen ini
> berdiri sendiri; tidak butuh riwayat percakapan yang melahirkannya.
> **Nomor baris** di bawah adalah petunjuk pada baseline. Baris bergeser;
> **nama fungsi** yang menjadi pegangan. Revalidasi sebelum menyunting.

## 0. Cara memakai dokumen ini

### Prompt siap pakai — memulai

```text
Anda melanjutkan repositori ModernIlham/NEW-AMAN-IKN.
Baca .claude/skills/aman-dev/SKILL.md lalu
docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md sampai habis sebelum menyunting apa pun.

Kerjakan paket PGW berikutnya yang belum selesai menurut tabel status di
Bab 8, dengan dependency terpenuhi. Satu paket = satu PR. Jangan menggabung
paket, jangan melompati PGW-02 (pagar baca) sebelum PGW-04 (jalur tulis).

Revalidasi dulu setiap fakta di Bab 2 terhadap main terbaru: bila sebuah
fungsi sudah berubah, laporkan selisihnya dan sesuaikan — jangan memaksakan
rencana pada kode yang sudah berbeda.

Keputusan K1–K8 di Bab 4 memakai nilai BAWAAN kecuali pemilik sudah menulis
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

1. **Pagar sebelum pintu.** Semua pembaca `db.pegawai` dibuat sadar-kelompok
   *sebelum* satu pun data non-internal bisa ditulis. Urutan PGW-02 → PGW-04
   tidak boleh dibalik.
2. **Tanpa migrasi data.** Dokumen pegawai lama tanpa field `kelompok` adalah
   internal. Jangan menjalankan backfill massal; pembaca yang toleran sudah
   cukup (pola sama dengan `kode_satker` era lama).
3. **Buktikan, jangan menyimpulkan.** Uji baru harus gagal sebelum perubahan.
4. **Konvensi repo tetap berlaku seluruhnya:** teks UI/commit/PR Indonesia,
   OCC + Idempotency-Key, lima titik isolasi satker, aturan blok tanda tangan,
   `data-testid`, aturan hover, komponen React di level modul, tap-target 44px.

---

## 1. Tujuan dan batasnya

### Yang diminta pemilik

Master Pegawai sekarang hanya mencatat pegawai **internal** — orang yang
bekerja pada satker-satker instansi sendiri. Pemilik meminta:

1. kemampuan yang sama untuk mencatat pegawai **instansi eksternal**
   (aparatur instansi pemerintah lain), beserta instansinya;
2. pencatatan **pegawai pihak ketiga** (orang dari badan di luar
   pemerintahan: penyedia, kontraktor, konsultan, mitra).

### Tafsir yang dipakai rencana ini

"Fitur yang sama" ditafsirkan sebagai **kemampuan yang sama**, bukan salinan
halaman dan bukan field yang sama:

| Kemampuan | Internal | Eksternal | Pihak ketiga |
|---|---|---|---|
| CRUD, cari, saring, urut, OCC, audit | ya | ya | ya |
| Foto, kartu tap (e-KTP/NFC) | ya | ya | ya |
| Impor/ekspor/template Excel pulang-pergi | ya | ya | ya |
| Jadi pemegang aset, pihak BAST, penerima persediaan, penanda tangan e-sign | ya | ya | ya |
| Peringatan "masih memegang aset padahal masa hubungan habis" | ya | ya | ya |
| Struktur unit Eselon I–V, rekap unit, bangun unit dari pegawai | ya | **tidak** | **tidak** |
| Data pribadi (agama, perkawinan, NPWP, rekening, pendidikan) | ya | **tidak** | **tidak** |
| Portal pemegang "BMN Saya" | ya | tidak (K3) | tidak (K3) |
| Jadi pejabat di Referensi Pejabat | ya | tidak (K7) | tidak (K7) |

### Yang BUKAN tujuan (sengaja ditunda — Bab 8 "Ditunda")

- Mengganti kunci tautan aset dari `pengguna_nip` (teks NIP/NIK) menjadi FK
  `pegawai.id`.
- Jenis BAST dan pasal baru khusus serah terima ke pihak luar.
- Akses portal BMN Saya untuk orang di luar instansi.
- Menjadikan master instansi sebagai pengganti kolom teks `pihak`/`mitra`/
  `penyedia` di modul lain (PGW-09 hanya menambah tautan opsional).

---

## 2. Keadaan sekarang (bukti dari kode)

### 2.1 Bentuk Master Pegawai

- Koleksi `pegawai`, ber-`kode_satker`, ±56 field isian form. Logika murni di
  `backend/pegawai_utils.py`, rute di `backend/routes/pegawai.py` (1.255
  baris), layar di `frontend/src/pages/PegawaiPage.jsx` (1.954 baris).
- Isolasi: `scope_query_field_satker` pada daftar/rekap/ekspor;
  `pastikan_akses_dok_satker` pada get-by-id/foto/kartu; NIP unik **per
  satker** (`_nip_bentrok`).
- `pegawai` ada di `RESET_KEEP_COLLECTIONS` (`backup_utils.py`), fotonya di
  `RESET_KEEP_GRIDFS_JENIS`.

### 2.2 Kunci tautan ke aset adalah TEKS NIP/NIK, bukan id

Aset menyimpan `user` (nama), `pengguna_nip`, `pengguna_jabatan`,
`pengguna_melekat_ke` (`asset_fields.py:58–60`, `models.py:82–90`). Seluruh
rantai pemegang berkunci `pengguna_nip`:

- `_jumlah_aset_per_nip`, `aset_dipegang_pegawai`, `_sinkron_pemegang_aset`
  (`routes/pegawai.py`);
- `rekap_pemegang` (`penggunaan_utils.py`), `distribusi_pengguna`
  (`report_utils.py`);
- `portal_bast._pegawai` menolak pihak tanpa `nip` ("Lengkapi identitas
  penerima").

**Akibat:** orang tanpa nomor identitas tidak bisa ditautkan sebagai pemegang
aset. Ini sudah berlaku untuk internal dan akan berlaku sama untuk pihak
ketiga (lihat K5).

### 2.3 Sudah ada tiga konsep yang BERTUMPANG-TINDIH dengan permintaan

| Yang sudah ada | Di mana | Hubungannya dengan fitur baru |
|---|---|---|
| Non-ASN **outsourcing** + `perusahaan_penyedia` (teks) | `jenis_kontrak_non_asn`, `validate_pegawai` | Tenaga alih daya yang *ditempatkan di satker* — tetap **internal** (K4) |
| `status_pegawai_satker` = perbantuan/dipekerjakan + `status_pegawai_instansi` (teks) | `STATUS_PEGAWAI_SATKER_BERINSTANSI` | Pegawai yang *bekerja di satker* tetapi berasal dari instansi lain — tetap **internal** |
| "Pihak luar — isi identitas manual" | `PilihPegawaiBast.jsx`, komentar `PjTambahanIn`, `penerima_utils.py` | Jalur manual ini **tetap ada**; master baru membuatnya tidak lagi satu-satunya jalan |

Tanpa batas yang tegas (Bab 3.2) orang yang sama akan tercatat dua kali.

### 2.4 Modul lain mencatat pihak luar sebagai teks bebas

Tidak ada koleksi penyedia/mitra/instansi. Yang ada hanya kolom teks:
`pengadaan.pihak`, `pemanfaatan.mitra` + `pelaksana_fasilitas`,
`pemindahtanganan.pihak`, `pemeliharaan.pelaksana`/`pihak_pelaksana`/
`pihak_penerima`, `penggunaan.pihak_asal`/`pihak_tujuan`,
`persediaan.penyedia`, `activities.tim_peneliti`/`tim_pendukung[].dari_pihak`.

### 2.5 Titik pakai `db.pegawai` di luar rutenya sendiri

Daftar lengkap beserta kebijakan ada di Bab 7. Pembaca frontend `GET
/pegawai` (tanpa parameter, memuat seluruh daftar): `AssetForm.jsx:666`,
`PenggunaanPage.jsx:325,479`, `PersediaanPage.jsx:209`,
`PemeliharaanPage.jsx:135`, `TtdPermintaanPage.jsx:130`,
`ActivitySelectionPage.jsx:222`, `PejabatPage.jsx:112`,
`PortalPemegangPanel.jsx:97`, `PegawaiPage.jsx:257`.

### 2.6 Penjaga anti-drift yang akan menagih perubahan

- `backend/tests/unit/test_pegawai_cakupan_ekspor.py` membaca `const EMPTY`
  dari `PegawaiPage.jsx`: **setiap field form wajib** punya kolom di
  `KOLOM_IMPOR` atau terdaftar di `TANPA_KOLOM`.
- `backend/tests/unit/test_backup_utils.py`: koleksi baru harus ditimbang.
- `test_pegawai_impor_dedup.py`, `test_pegawai_utils.py`,
  `test_portal_*.py`, `test_unit_kerja_route.py`.

### 2.7 Temuan sampingan (bukan bagian permintaan — jangan diperbaiki diam-diam)

`snapshot_pemegang_aset` (`pegawai_utils.py:388`) mengisi
`pengguna_melekat_ke` dengan **nama unit kerja**, dan `test_pegawai_utils.py`
menegaskannya (`== "Bagian Umum"`). Padahal `models.py:82` dan
`AssetForm.jsx` memperlakukan field itu sebagai enum
`Individual | Jabatan | Operasional`. Tombol "Sinkron aset" karenanya menimpa
enum dengan nama unit. **[Keyakinan sedang]** — terbaca dari tiga berkas itu;
belum ditelusuri apakah ada pembaca lain yang memang mengharapkan nama unit.
Tindakan: laporkan ke pemilik sebagai isu terpisah; di fitur ini cukup
**jangan memperluas** perilaku itu ke non-internal (PGW-04 butir 6).

---

## 3. Keputusan desain (terkunci)

### 3.1 Satu koleksi + sumbu `kelompok`, bukan tiga master

`pegawai` mendapat field `kelompok ∈ {internal, eksternal, pihak_ketiga}` dan
satu master pendamping baru `instansi_eksternal`.

**Kenapa bukan koleksi terpisah** (`pegawai_eksternal`, `pegawai_pihak_ketiga`):

- Koleksi `pegawai` disentuh di 57 tempat pada baseline: 27 di rutenya
  sendiri dan 30 di 14 berkas lain. Banyak di antaranya mencari orang lewat
  NIP (status kepegawaian untuk blok tanda tangan, penerima BAST/persediaan,
  penanda tangan e-sign, wajib-terdaftar, label "(belum terdaftar)" di
  laporan). Dengan koleksi terpisah semuanya harus mencari di tiga tempat;
  yang terlewat tidak galat — ia diam-diam menandai orang yang terdaftar
  sebagai "belum terdaftar".
- Foto, kartu tap, spesimen TTD (`routes/ttd.py` `_ENTITAS`), dan pencabutan
  portal sudah berkunci `pegawai.id`; menyalinnya = tiga implementasi.
- Orang berpindah kelompok (ASN eksternal yang mutasi masuk; orang penyedia
  yang lalu direkrut PPNPN). Satu koleksi = satu suntingan, `pegawai.id`
  tetap, riwayat BAST/portal utuh.

**Harga yang dibayar:** pembaca yang seharusnya internal-saja bisa ikut
membaca orang luar. Itu risiko terbesar desain ini dan ditutup dengan tiga
lapis: bawaan API internal-saja (3.4), helper kueri tunggal (PGW-01), dan uji
anti-drift titik pakai (PGW-02).

### 3.2 Batas tiga kelompok — ditentukan oleh TEMPAT BEKERJA, bukan pemberi gaji

| Kelompok | Definisi | Contoh |
|---|---|---|
| `internal` | Bekerja pada satker ini, apa pun status kepegawaiannya | PNS/PPPK satker; PPNPN; tenaga alih daya yang ditempatkan (satpam, pramubakti); pegawai dipekerjakan/diperbantukan **dari** instansi lain |
| `eksternal` | Aparatur instansi pemerintah lain yang **tidak** bekerja pada satker ini tetapi berhubungan dengan BMN-nya | Pejabat K/L lain pemakai BMN penggunaan sementara; petugas pemda penerima hibah; tim pendamping dari instansi lain |
| `pihak_ketiga` | Orang dari badan non-pemerintah yang tidak ditempatkan sebagai tenaga satker | Wakil penyedia saat serah terima pengadaan; teknisi vendor pemeliharaan; wakil mitra sewa/KSP; konsultan perusahaan |

Sumbu `kelompok` (asal organisasi) **ortogonal** terhadap `status_kepegawaian`
(jenis kepegawaian). Invarian: `pihak_ketiga ⇒ status_kepegawaian = "non_asn"`
(dipaksa server). Dengan begitu seluruh aturan yang sudah ada untuk Non-ASN —
NIK tidak dicetak di blok tanda tangan, tanpa BUP/pensiun, pantau masa
kontrak — berlaku otomatis tanpa menyentuh satu pun pemanggilnya.
`STATUS_KEPEGAWAIAN` (`pejabat_utils.py`) **tidak ditambah** kode baru.

### 3.3 Master `instansi_eksternal` per satker

Satu koleksi untuk dua jenis organisasi luar (instansi pemerintah dan badan
non-pemerintah), dibedakan field `kelompok` yang nilainya sama dengan milik
pegawainya. Distempel `kode_satker` (uji pemilik skill aman-dev: narahubung,
peran, dan dokumen dasar memang berbeda per satker). Lihat K2.

### 3.4 Bawaan `GET /pegawai` tetap internal-saja

`GET /pegawai` tanpa parameter mengembalikan **hanya internal** — persis hari
ini. Alasan: aplikasi ini PWA offline-first; bundel frontend lama yang masih
ter-cache akan memanggil tanpa parameter. Bawaan "semua" berarti orang luar
muncul di pemilih pejabat dan rekap internal pada klien yang belum
diperbarui. Pemanggil yang memang butuh semua orang harus memintanya
(`?kelompok=semua`).

### 3.5 Field non-internal dibersihkan server, bukan sekadar disembunyikan form

Field yang tak berlaku bagi sebuah kelompok **dikosongkan** di `_bersih`
(pola yang sama dengan blok kematian yang dikosongkan bila status bukan
meninggal). Menyembunyikan di form saja membuat impor dan klien lama tetap
bisa mengisinya. Matriksnya di Bab 5.2.

### 3.6 Masa hubungan memakai field kontrak yang sudah ada

`nomor_kontrak`, `tgl_mulai_kontrak`, `tgl_selesai_kontrak` dipakai ulang
untuk non-internal sebagai "dokumen dasar hubungan" (perjanjian, surat tugas,
kontrak). Hanya **label layarnya** yang berbeda. Hasilnya `status_kontrak` dan
`pegawai_perlu_serah_terima` langsung mendeteksi orang luar yang masih
memegang aset setelah masa hubungannya habis — tanpa logika baru.

---

## 4. Keputusan yang milik pemilik

Rencana berjalan dengan **bawaan** bila kolom jawaban kosong. Pelaksana tidak
boleh memilih selain bawaan atas inisiatif sendiri.

| # | Pertanyaan | Bawaan | Akibat bila diubah | Jawaban pemilik |
|---|---|---|---|---|
| K1 | BUMN/BUMD masuk kelompok mana? | `pihak_ketiga` (pegawainya bukan ASN) | Hanya daftar `jenis` instansi; tanpa perubahan struktur | |
| K2 | Master instansi per satker atau satu untuk seluruh instansi? | Per satker | Bila bersama: perlu penjaga tulis super-admin + indeks unik tanpa `kode_satker`; PGW-03 berubah | |
| K3 | Orang luar mendapat akses portal BMN Saya? | Tidak | Bila ya: paket tersendiri (Ditunda X3) — menyangkut email di luar kendali instansi | |
| K4 | Tenaga alih daya yang sudah tercatat internal dipindah ke pihak ketiga? | Tidak; tetap internal, tanpa migrasi | Bila ya: skrip pratinjau + pindah per orang oleh admin, bukan massal | |
| K5 | NIK orang pihak ketiga wajib? | Opsional; tanpa nomor ia tak bisa jadi pemegang aset tertaut (2.2) | Bila wajib: validasi keras di PGW-04; lebih banyak data pribadi terkumpul | |
| K6 | Modul mana dulu yang ditautkan ke master instansi (PGW-09)? | Penggunaan/BAST → Pemeliharaan → Pengadaan → Pemanfaatan → Pemindahtanganan → Persediaan | Hanya urutan PR | |
| K7 | Orang luar boleh dipilih jadi pejabat di Referensi Pejabat? | Tidak | Bila ya: `PejabatPage` memuat `kelompok=semua` | |
| K8 | Data pribadi (agama, perkawinan, NPWP, rekening, pendidikan, tempat lahir) dikumpulkan untuk orang luar? | Tidak | Bila ya: matriks 5.2 dilonggarkan — perlu dasar pemrosesan yang jelas | |

---

## 5. Model data

### 5.1 Field baru pada `pegawai`

| Field | Tipe | Aturan |
|---|---|---|
| `kelompok` | str | `internal` \| `eksternal` \| `pihak_ketiga`. Tak ada/kosong ⇒ dibaca `internal`. Ditulis eksplisit pada setiap create/update baru |
| `instansi_id` | str | FK → `instansi_eksternal.id`. **Wajib** bila non-internal; **dikosongkan** bila internal. Instansinya harus satu satker dan `kelompok`-nya sama |
| `instansi_nama` | str | Snapshot nama instansi (untuk daftar, cari, ekspor, dan bila master dihapus). Ikut merambat saat instansi diganti nama |

Tidak ada field lain yang ditambah. `unit_kerja` untuk non-internal menjadi
teks bebas "unit/divisi di instansi asal" dan **tidak** diturunkan dari
eselon.

### 5.2 Matriks field per kelompok

`✓` boleh diisi · `—` dikosongkan server · `(paksa)` nilai ditetapkan server.

| Kelompok field | Field | Internal | Eksternal | Pihak ketiga |
|---|---|---|---|---|
| Inti | `nama`, `nip`, `gelar_*`, `jenis_kelamin`, `tanggal_lahir`, `kewarganegaraan`, `jenis/nomor_identitas_wna`, `jabatan`, `no_hp`, `email`, `alamat`, `status`, `keterangan` | ✓ | ✓ | ✓ |
| Kematian | `tanggal_meninggal` … `pemberitahuan_ahli_waris_*` | ✓ | ✓ | ✓ |
| Kepegawaian | `status_kepegawaian` | ✓ | ✓ | (paksa `non_asn`) |
| | `pangkat_golongan`, `jenis_jabatan`, `kategori_pegawai`, `eselon` (teks), `jenis_pelaksana`, `jabatan_pelaksana`, `tmt_jabatan`, `tanggal_akhir_jabatan` | ✓ | ✓ | — |
| | `sub_kategori_non_asn` | ✓ | ✓ | — |
| | `status_pegawai_satker`, `status_pegawai_instansi` | ✓ | — | — |
| | `jenis_kontrak_non_asn`, `perusahaan_penyedia` | ✓ | — | — |
| Masa hubungan | `nomor_kontrak`, `tgl_mulai_kontrak`, `tgl_selesai_kontrak` | ✓ | ✓ | ✓ |
| Organisasi | `eselon1`…`eselon5`, `unit_organisasi`, `kode_satker_lengkap` | ✓ | — | — |
| | `unit_kerja` | ✓ (turun dari eselon bila kosong) | ✓ teks bebas | ✓ teks bebas |
| | `instansi_id`, `instansi_nama` | — | ✓ wajib | ✓ wajib |
| Pribadi | `tempat_lahir`, `agama`, `status_perkawinan`, `npwp`, `pendidikan_terakhir`, `nama_bank`, `no_rekening` | ✓ | — | — |

Catatan label layar (tanpa mengganti nama field):

- `nip`: internal "NIP/NIK/NRP"; eksternal "NIP/NRP/NIK"; pihak ketiga "NIK
  (opsional)".
- `nomor_kontrak`: non-internal "Nomor dokumen dasar (perjanjian/kontrak/
  surat tugas)"; `tgl_*_kontrak`: "Berlaku mulai/sampai".
- `alamat`: non-internal "Alamat korespondensi".

Blok kematian tetap boleh diisi di semua kelompok karena status meninggal
memblokir penugasan baru (`enforce_pegawai_terdaftar`, `periksa_penerima`).
**Jam 3 tahun pemberitahuan ahli waris** (`info_kewajiban_ahli_waris`,
UU 1/2004 Ps. 66 ayat (2)) hanya ditampilkan untuk **internal** sampai PGW-00
memastikan apakah dasar hukumnya berlaku bagi kelompok lain. **Perlu
verifikasi.**

### 5.3 Koleksi baru `instansi_eksternal`

| Field | Aturan |
|---|---|
| `id` | UUID, unik |
| `kode_satker` | Stempel pemilik (`kode_satker_user`); tulis lewat `require_admin_satker` agar tak pernah `""` |
| `kelompok` | `eksternal` \| `pihak_ketiga` |
| `jenis` | Lihat 5.4; harus cocok dengan `kelompok` |
| `nama` | Wajib |
| `nama_kunci` | Turunan server: huruf kecil, tanda baca dibuang, spasi tunggal, bentuk badan usaha di depan/belakang dinormalkan (`PT. Telkom` = `PT Telkom` = `Telkom, PT`). Untuk keunikan & pencocokan impor |
| `singkatan`, `kode_referensi`, `npwp`, `alamat`, `kota`, `telepon`, `email` | Opsional. `kode_referensi` = kode BA/kode pemda/NIB — teks bebas, tanpa validasi format |
| `narahubung_nama`, `narahubung_jabatan`, `narahubung_kontak` | Opsional |
| `peran` | List kode (5.4), boleh kosong |
| `aktif` | bool, bawaan `true` |
| `keterangan`, `version`, `created_at`, `updated_at` | OCC lewat `If-Match` (pola `ubah_pegawai`) |

Indeks (`backend/indexes.py`):

```python
await _idx(db.instansi_eksternal, "id", unique=True)
await _idx(db.instansi_eksternal,
           [("kode_satker", 1), ("kelompok", 1), ("nama_kunci", 1)], unique=True)
await _idx(db.pegawai, [("kode_satker", 1), ("kelompok", 1), ("nama", 1)])
await _idx(db.pegawai, "instansi_id")
```

Indeks unik menyertakan `kode_satker` (aturan skill: keunikan per satker ≠
indeks unik global). Indeks `pegawai (kode_satker, nama)` yang lama dibiarkan.

Backup/reset: tambahkan `instansi_eksternal` ke `RESET_KEEP_COLLECTIONS`
(master yang disusun manual, sekelas `pegawai`/`ruangan`).
`satker_referensi.ganti_kode_satker` menyapu semua koleksi ber-`kode_satker`
secara dinamis — tidak perlu didaftarkan.

### 5.4 Kode referensi

```python
KELOMPOK_PEGAWAI = {
    "internal": "Internal",
    "eksternal": "Instansi Eksternal",
    "pihak_ketiga": "Pihak Ketiga",
}
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
```

Daftar ini usulan kerja; PGW-00 memeriksanya terhadap istilah di
`docs/PUSTAKA-REGULASI-BMN.md` sebelum dikunci. Tidak ada data benih
instansi — repo ini melarang data dummy, dan daftar kode K/L/pemda tidak
boleh ditulis dari ingatan.

### 5.5 Invarian yang harus selalu benar

1. `kelompok` hanya salah satu dari tiga kode; kosong dibaca `internal`.
2. Non-internal ⇒ `instansi_id` menunjuk dokumen yang ada, satu satker,
   `kelompok` sama. Internal ⇒ `instansi_id == ""`.
3. `pihak_ketiga` ⇒ `status_kepegawaian == "non_asn"`.
4. Non-internal ⇒ `eselon1..5`, `unit_organisasi`, `kode_satker_lengkap`
   kosong.
5. NIP unik per satker **lintas kelompok** (satu orang tak boleh tercatat
   internal dan eksternal dengan nomor yang sama).
6. Impor tidak pernah mengubah `kelompok` dokumen yang sudah ada.
7. Daftar field `FIELD_IDENTITAS_PORTAL` **tidak berubah** (lihat Jebakan 9.1).

---

## 6. Kontrak API

### 6.1 Rute pegawai yang berubah

| Rute | Perubahan |
|---|---|
| `GET /pegawai` | Parameter `kelompok` = `internal` (bawaan) \| `eksternal` \| `pihak_ketiga` \| `semua`; nilai lain → 400. Tiap item selalu membawa `kelompok` (ternormalkan), `instansi_id`, `instansi_nama`. `info_masa` tetap |
| `GET /pegawai/referensi` | Tambah `kelompok`, `jenis_instansi`, `peran_instansi`, dan `field_per_kelompok` (matriks 5.2 sebagai `{kelompok: [field yang BOLEH]}`) — frontend membaca ini, tidak menyalin daftar |
| `GET /pegawai/rekap-unit` | Internal-saja. Tambah kunci `per_kelompok: {internal, eksternal, pihak_ketiga}` (cacah) |
| `GET /pegawai/rekap-instansi` | **Baru.** `?kelompok=` → `[{instansi_id, instansi_nama, jumlah}]`, ter-scope satker |
| `GET /pegawai/perlu-serah-terima` | Tetap **semua** kelompok; item ditambah `kelompok`, `instansi_nama` |
| `POST /pegawai`, `PUT /pegawai/{id}` | Terima `kelompok`, `instansi_id`. Aturan Bab 5 ditegakkan. `instansi_nama` selalu diisi server dari master (nilai klien diabaikan) |
| `GET /pegawai/template-impor`, `GET /pegawai/export-xlsx`, `POST /pegawai/impor` | Parameter `kelompok` (bawaan `internal`; impor: field `Form`). Internal = perilaku dan header hari ini, tak berubah satu byte pun |
| `POST /pegawai/kartu/identifikasi` | Proyeksi publik ditambah `kelompok`, `instansi_nama` |
| Rute by-id lain (foto, kartu, aset, sinkron) | Tidak berubah; berlaku semua kelompok |

### 6.2 Rute baru instansi (`backend/routes/instansi_eksternal.py`)

| Rute | Penjaga | Catatan |
|---|---|---|
| `GET /instansi-eksternal?kelompok=&q=&aktif=` | `require_user` + `scope_query_field_satker` | Tiap item + `jumlah_pegawai` (satu agregasi, bukan N kueri) |
| `GET /instansi-eksternal/referensi` | `require_user` | `kelompok`, `jenis`, `peran` |
| `POST /instansi-eksternal` | `require_admin_satker` | Stempel satker; 400 bila `nama_kunci` sudah ada di satker+kelompok |
| `PUT /instansi-eksternal/{id}` | `require_admin_satker` + `pastikan_akses_dok_satker` + `If-Match` | Ganti nama → rambatkan `instansi_nama` ke pegawai (`update_many` ter-scope satker **dan** `instansi_id`). `kelompok` **tidak boleh** diubah bila masih dipakai pegawai (409) |
| `DELETE /instansi-eksternal/{id}` | sama | 409 bila masih dirujuk pegawai — sarankan nonaktifkan (pola `hapus_unit_kerja`) |

Semua tulis ber-`log_audit` (`buat_instansi`, `ubah_instansi`,
`hapus_instansi`) dengan `kode_satker`.

### 6.3 Contoh

```http
POST /api/pegawai
{ "nama": "Rina Wulandari", "kelompok": "pihak_ketiga",
  "instansi_id": "8c1e…", "jabatan": "Teknisi Lapangan",
  "nip": "", "email": "rina@contoh.co.id",
  "nomor_kontrak": "SPK-014/2026", "tgl_selesai_kontrak": "2026-12-31" }
→ 200 { "ok": true, "id": "…" }
   tersimpan: status_kepegawaian "non_asn", eselon1..5 "", agama "", …
```

```http
POST /api/pegawai   { "nama": "X", "kelompok": "eksternal" }
→ 400 "Instansi wajib dipilih untuk pegawai instansi eksternal"
```

---

## 7. Peta titik pakai dan kebijakannya

Kebijakan: **INT** = internal-saja · **SEMUA** = semua kelompok ·
**ID** = lewat `pegawai.id`, tak perlu saringan.

### 7.1 Backend

| Berkas → fungsi | Hari ini | Kebijakan | Tindakan |
|---|---|---|---|
| `routes/pegawai.py` → `list_pegawai` | semua dok satker | parameter (bawaan INT) | PGW-02 |
| → `rekap_unit_pegawai` | semua dok satker | INT | PGW-02 |
| → `daftar_perlu_serah_terima` | semua dok satker | SEMUA + field label | PGW-02 |
| → `_nip_bentrok` | NIP per satker | SEMUA (invarian 5) | biarkan; tambah uji |
| → `impor_pegawai`, `_filter_dedup` | upsert per kunci | per kelompok; tolak silang | PGW-05 |
| → `export_pegawai_xlsx`, `template_impor_pegawai` | semua dok satker | parameter (bawaan INT) | PGW-02 (saring) + PGW-05 (header) |
| → `identifikasi_kartu` | hash kartu | SEMUA + field label | PGW-02 |
| → rute foto/kartu/aset/sinkron | by id | ID | biarkan |
| `shared_utils.py` → `status_kepegawaian_by_nip` | NIP (+satker) | SEMUA | biarkan |
| → `enforce_pegawai_terdaftar` | NIP, **tanpa scope satker** | SEMUA | biarkan (catat: tanpa scope adalah keadaan lama, di luar lingkup) |
| `penerima_utils.py` → `periksa_penerima` | NIP ter-scope | SEMUA | biarkan; PGW-08 menambah `penerima_instansi` ke snapshot |
| `portal_auth.py` → `pegawai_layak_portal` | status+email+kontrak | INT (K3) | PGW-02 |
| → `cabut_email_bentrok`, `pegawai_email_tunggal`, dan dua pembaca email lain di berkas itu | email lintas satker | SEMUA | biarkan (Jebakan 9.4) |
| `portal_bast.py` → `_pegawai`, `_akses_awal` | NIP unik di satker | SEMUA untuk amanah; akses portal ikut `pegawai_layak_portal` | PGW-02: pesan khusus non-internal |
| `routes/portal_auth.py`, `routes/portal_pemegang.py` | by id + `pegawai_layak_portal` | ID | biarkan |
| `routes/unit_kerja.py` → `_rambatkan_nama` | `update_many` jalur eselon | INT | PGW-02 |
| → `hapus_unit_kerja` (cacah pemakai) | `count_documents` | INT | PGW-02 |
| → `bangun_dari_pegawai` | semua dok satker | INT | PGW-02 |
| `routes/ttd.py` → `_ENTITAS` (spesimen) | by id | ID | biarkan |
| → cek penanda tangan meninggal (2 tempat) | NIP ter-scope | SEMUA | biarkan |
| `routes/bast.py` → cek PIHAK KESATU meninggal | NIP ter-scope | SEMUA | biarkan |
| `routes/wasdal.py` → pegawai berisiko | semua dok satker | SEMUA + label | PGW-08 |
| `routes/penggunaan.py` → `daftar_pemegang` (pengaya) | NIP ter-scope | SEMUA + `pegawai_master_kelompok`, `pegawai_master_instansi` | PGW-02 |
| `routes/reports.py` → `_peta_status_kepegawaian` | NIP | SEMUA | biarkan |
| → Laporan Eksekutif `peg_master` | NIP ter-scope satker kegiatan | SEMUA + pengelompokan | PGW-08 |
| `routes/imports.py` → `nip_terdaftar` | `distinct("nip")` | SEMUA | biarkan |
| `webp_converter.py` | by id | ID | biarkan |

### 7.2 Frontend

| Berkas | Dipakai untuk | Kebijakan | Paket |
|---|---|---|---|
| `pages/PegawaiPage.jsx` | Kelola master | per tab kelompok | PGW-06 |
| `components/assets/AssetForm.jsx` | Pemilih pengguna + peringatan "NIP belum terdaftar" | SEMUA (kalau tidak, orang luar terdaftar diperingatkan palsu) | PGW-07 |
| `components/penggunaan/PilihPegawaiBast.jsx` + `pages/PenggunaanPage.jsx` | Pihak BAST, PJ tambahan | SEMUA + lencana + instansi | PGW-07 |
| `pages/PersediaanPage.jsx` + `lib/penerimaPersediaan.js` | Penerima barang | SEMUA | PGW-07 |
| `pages/PemeliharaanPage.jsx` | Saran pelaksana/penerima | SEMUA | PGW-07 |
| `pages/TtdPermintaanPage.jsx` | Saran penanda tangan | SEMUA | PGW-07 |
| `pages/ActivitySelectionPage.jsx` | Tim inti/pembantu | INT | PGW-07 (eksplisit) |
| (sama) | Tim peneliti/pendukung | SEMUA; `dari_pihak` terisi dari `instansi_nama` | PGW-07 |
| `pages/PejabatPage.jsx` | Pemilih pejabat | INT (K7) | PGW-07 (eksplisit) |
| `components/penggunaan/PortalPemegangPanel.jsx` | Kelola akses portal | INT (K3) | PGW-07 (eksplisit) |
| `components/pegawai/KartuTapDialog.jsx` | Hasil tap | tampilkan lencana + instansi | PGW-07 |

"Eksplisit" = pemanggil menulis `?kelompok=internal` walau itu bawaan, supaya
niatnya terbaca dan tidak bergantung pada bawaan server.

---

## 8. Paket kerja

### Status

| Paket | Isi | Bergantung | Status | PR |
|---|---|---|---|---|
| PGW-00 | Regulasi & kontrak modul | — | belum | |
| PGW-01 | Fondasi murni | 00 | belum | |
| PGW-02 | Pagar baca (titik pakai sadar-kelompok) | 01 | belum | |
| PGW-03 | Master instansi (backend) | 01 | belum | |
| PGW-04 | Jalur tulis pegawai non-internal | 02, 03 | belum | |
| PGW-05 | Impor/ekspor/template per kelompok | 04 | belum | |
| PGW-06 | Layar Master Pegawai | 04, 05 | belum | |
| PGW-07 | Pemilih lintas modul | 04 | belum | |
| PGW-08 | Laporan & dokumen | 04 | belum | |
| PGW-09 | Tautan instansi di modul berpihak-luar | 03, 06 | belum | |
| PGW-10 | Data uji & dokumentasi | 06–08 | belum | |

PGW-02 dan PGW-03 boleh dikerjakan paralel. PGW-06, 07, 08 boleh paralel
setelah PGW-04. Sampai PGW-06 ter-merge, pengguna tidak melihat perubahan apa
pun — itu disengaja.

---

### PGW-00 — Regulasi & kontrak modul (dokumen saja)

**Tujuan:** memenuhi aturan "regulasi dulu, kode kemudian".

1. Tambah bagian baru di `docs/PUSTAKA-REGULASI-BMN.md` (dekat §2.4c Master
   Pegawai): definisi tiga kelompok (Bab 3.2) dan dasar hubungan tiap kelompok
   dengan BMN. Mulai dari yang **sudah** ada di pustaka — penggunaan sementara
   dan dioperasikan pihak lain (rujukan PMK 40/2024), pemanfaatan dan
   pemindahtanganan — lalu riset yang belum tercakup. Setiap butir bersumber;
   yang tak terverifikasi ditandai "perlu verifikasi".
2. Tiga pertanyaan yang **wajib** dijawab riset, karena menentukan perilaku:
   - Apakah jam 3 tahun pemberitahuan ahli waris berlaku bagi orang
     non-internal? (menentukan 5.2 catatan blok kematian)
   - Siapa yang sah menandatangani serah terima BMN kepada pihak di luar
     satker, dan apakah jenis BAST yang ada memadai? (bahan Ditunda X2)
   - Batas pengumpulan data pribadi orang luar menurut UU 27/2022 (PDP) —
     repo sudah merujuknya di `docs/DPIA-PELACAKAN-ASET.md`. Hasilnya
     mengukuhkan atau mengoreksi K5/K8.
3. Tambah kontrak di `docs/MASTERPLAN-SIKLUS-BMN.md`: master instansi dibaca
   modul mana, ditulis siapa.
4. Kunci daftar kode 5.4.
5. Patuhi registry sitasi: nomor peraturan yang kelak **tercetak di dokumen
   keluaran** wajib terdaftar di `backend/sitasi_regulasi.py` dengan status
   yang jujur terhadap pustaka; status "terverifikasi" menuntut naskahnya ada
   di `docs/regulasi/` (ditagih `test_sitasi_regulasi.py`, aturan di
   `docs/SITASI-DOKUMEN-RESMI.md`). Nomor peraturan di docstring/komentar
   tidak ditagih. Rencana ini sendiri tidak menambah sitasi ke dokumen
   keluaran mana pun sampai X2.

**Terima:** bagian pustaka ada, bersumber, dan ketiga pertanyaan berjawaban
(atau bertanda "perlu verifikasi" dengan bawaan yang dipakai).

---

### PGW-01 — Fondasi murni

**Berkas baru:** `backend/pegawai_kelompok.py`, `backend/instansi_utils.py`,
`backend/tests/unit/test_pegawai_kelompok.py`,
`backend/tests/unit/test_instansi_utils.py`.

`pegawai_kelompok.py` (tanpa Mongo/IO):

```python
KELOMPOK_PEGAWAI = {...}                       # Bab 5.4
KELOMPOK_BAWAAN = "internal"

def kelompok_pegawai(doc) -> str: ...          # kosong/asing → "internal"
def q_kelompok(kelompok, query=None) -> dict:  # SATU-SATUNYA pembuat saringan
    # "internal" → {"kelompok": {"$in": ["internal", "", None]}}
    # "eksternal"/"pihak_ketiga" → {"kelompok": <kode>}
    # "semua" → tanpa saringan
    # selain itu → ValueError
def FIELD_BOLEH(kelompok) -> frozenset: ...    # matriks Bab 5.2
def terapkan_aturan_kelompok(doc) -> dict: ... # kosongkan yang tak boleh;
                                               # paksa non_asn utk pihak_ketiga
def validate_kelompok(doc) -> list[str]: ...   # pesan Indonesia
def label_unit_pegawai(doc) -> str: ...        # internal: unit_kerja;
                                               # lain: "instansi_nama — unit"
```

`$in` yang memuat `None` juga mencocokkan field yang tidak ada — inilah yang
membuat dokumen lama terbaca internal tanpa backfill.

`instansi_utils.py`: `JENIS_INSTANSI`, `PERAN_INSTANSI`, `nama_kunci(nama)`,
`validate_instansi(doc)`, `bersihkan_instansi(payload)`.

**Uji minimum:**
- `kelompok_pegawai({})`, `({"kelompok": None})`, `({"kelompok": "ngawur"})`
  → `"internal"`.
- `q_kelompok("internal")` cocok dengan dok tanpa field (uji lewat
  `mongomock_motor`, pola `test_unit_kerja_route.py`).
- `terapkan_aturan_kelompok` pihak ketiga: `status_kepegawaian` jadi
  `non_asn`; `agama`, `eselon3`, `no_rekening` kosong; `nama`, `nip`,
  `nomor_kontrak` utuh.
- `terapkan_aturan_kelompok` internal: **identitas** — dokumen keluar sama
  persis dengan masuk kecuali `instansi_id/instansi_nama` dikosongkan.
- Uji kesetaraan: gabungan `FIELD_BOLEH` ketiga kelompok ⊇ seluruh kunci
  `_bersih(PegawaiIn(nama="x"))` — field form baru tak boleh lahir tanpa
  keputusan matriks.
- `nama_kunci("PT. Telkom Indonesia")` == `nama_kunci("Telkom  Indonesia, PT")`.

**Terima:** uji lulus; `grep -r pegawai_kelompok backend --include=*.py`
hanya menunjuk berkas baru (belum ada pemanggil → nol perubahan perilaku).

---

### PGW-02 — Pagar baca

**Tujuan:** setiap pembaca `db.pegawai` memutuskan kelompoknya secara
eksplisit, **selagi seluruh data masih internal** — sehingga paket ini
terbukti tidak mengubah perilaku apa pun di produksi.

**Langkah:**

1. `routes/pegawai.py`
   - `list_pegawai(kelompok: str = "internal")`: kueri =
     `scope_query_field_satker(user, q_kelompok(kelompok))`; `ValueError` →
     400. Normalisasi `it["kelompok"] = kelompok_pegawai(it)`; pastikan
     `instansi_id`/`instansi_nama` selalu ada (string kosong). Turunan
     `unit_kerja` dari eselon **hanya** untuk internal.
   - `rekap_unit_pegawai`: saring internal; tambah `per_kelompok` (satu
     agregasi `$group` ter-scope satker).
   - `rekap-instansi` baru.
   - `daftar_perlu_serah_terima`: proyeksi + keluaran ditambah `kelompok`,
     `instansi_nama`.
   - `export_pegawai_xlsx`, `template_impor_pegawai`: terima `kelompok`;
     di paket ini selain `internal` → 400 "belum tersedia" (dibuka PGW-05).
   - `_KARTU_PROYEKSI_PUBLIK`: tambah `kelompok`, `instansi_nama`.
2. `routes/unit_kerja.py`: tiga tempat (`_rambatkan_nama`,
   cacah pemakai di `hapus_unit_kerja`, `bangun_dari_pegawai`) dibungkus
   `q_kelompok("internal", …)`.
3. `portal_auth.py` → `pegawai_layak_portal`: baris pertama mengembalikan
   `False` bila `kelompok_pegawai(p) != "internal"`. **Jangan** menyentuh
   `FIELD_IDENTITAS_PORTAL`.
4. `portal_bast.py` → `_akses_awal`: sebelum cek kelayakan, bila non-internal
   kembalikan "Amanah tercatat; pemegang dari luar instansi tidak mendapat
   akses BMN Saya". Amanah ke aset tetap diterapkan.
5. `routes/penggunaan.py` → `daftar_pemegang`: proyeksi + dua kunci baru.
6. **Uji anti-drift** `backend/tests/unit/test_pegawai_titik_pakai.py`:
   memindai seluruh `backend/**/*.py` (kecuali `tests/`, `scripts/`) untuk
   pola `\.pegawai\.(find|find_one|count_documents|aggregate|distinct|update_many|update_one|delete_one|delete_many|bulk_write|insert_one)\(`
   dan baris yang memuat `db.pegawai` tanpa pemanggilan langsung
   (`_ENTITAS`, `for koleksi in (db.pejabat, db.pegawai)`). Jumlah per berkas
   harus sama dengan registry `TITIK_PAKAI_PEGAWAI` di `pegawai_kelompok.py`
   yang memetakan `berkas → {jumlah, kebijakan, catatan}` sesuai tabel 7.1.
   Pesan gagalnya menyuruh pembaca menimbang INT/SEMUA/ID lalu memperbarui
   registry. Sertakan uji anti-hampa (pemindai menemukan ≥ 50 titik; pada
   baseline 57 di 15 berkas — hitung ulang di awal paket).

**Uji minimum:**
- Dengan koleksi berisi dokumen lama (tanpa `kelompok`): `GET /pegawai`
  tanpa parameter mengembalikan semuanya (regresi nol).
- Sisipkan satu dokumen `kelompok: "eksternal"` langsung ke mongomock:
  tidak muncul di `GET /pegawai`, `rekap-unit`, `bangun-dari-pegawai`;
  muncul di `?kelompok=semua` dan `perlu-serah-terima`.
- `_rambatkan_nama` tidak mengubah dokumen eksternal yang kebetulan berisi
  `eselon2` sama.
- `pegawai_layak_portal` False untuk eksternal ber-email sah & status aktif.
- `identitas_portal_hash` atas satu dokumen internal **sama** sebelum dan
  sesudah paket ini (uji dengan nilai hash yang dibekukan di uji).

**Terima:** seluruh `test_portal_*`, `test_unit_kerja_*`, `test_pegawai_*`
lama lulus tanpa disunting. Bila ada uji lama yang harus diubah, itu tanda
perilaku internal bergeser — hentikan dan periksa.

---

### PGW-03 — Master instansi (backend)

**Berkas:** `backend/routes/instansi_eksternal.py` (baru), `backend/server.py`
(impor + `include_router`, dekat `pegawai_router`), `backend/indexes.py`,
`backend/backup_utils.py`, `backend/tests/unit/test_instansi_route.py` (baru),
`backend/tests/unit/test_backup_utils.py`.

**Langkah:** kontrak 6.2. Periksa **lima titik isolasi** satu per satu:
insert berstempel; daftar ter-scope; get-by-id dijaga; update/delete dijaga;
lookup silang (pegawai → instansi) ter-scope. Agregasi `jumlah_pegawai`
memakai `scope_query_field_satker` pada koleksi `pegawai`.

**Uji minimum:**
- Admin satker A tak dapat membaca/mengubah/menghapus instansi satker B
  (403/404), dan daftar A tak memuat milik B.
- Nama kembar (beda tanda baca) di satker+kelompok sama → 400; di satker
  lain → boleh.
- Hapus instansi yang dirujuk pegawai → 409 dengan jumlahnya.
- Ganti nama merambat ke `pegawai.instansi_nama` **hanya** pada satker dan
  `instansi_id` itu.
- `PUT` tanpa `If-Match` yang benar → 409.
- `instansi_eksternal ∈ RESET_KEEP_COLLECTIONS`.

**Terima:** uji lulus; `python -m compileall -q backend`.

---

### PGW-04 — Jalur tulis pegawai non-internal

**Berkas:** `backend/routes/pegawai.py`, `backend/pegawai_utils.py`,
`backend/tests/unit/test_pegawai_kelompok_route.py` (baru).

**Langkah:**

1. `PegawaiIn`: tambah `kelompok: Optional[str] = "internal"`,
   `instansi_id: Optional[str] = ""`.
2. `_bersih`: setelah perakitan, panggil `terapkan_aturan_kelompok`. Turunan
   `unit_kerja ← unit_kerja_terdalam` hanya untuk internal.
3. `validate_pegawai`: gabungkan `validate_kelompok`. Aturan "outsourcing
   wajib perusahaan penyedia" hanya internal.
4. Helper async `_resolusi_instansi(user, doc)`: untuk non-internal, ambil
   instansi lewat `scope_query_field_satker(user, {"id": instansi_id})`;
   tidak ada / beda kelompok / nonaktif (untuk **create**) → 400; isi
   `doc["instansi_nama"]` dari master.
5. `buat_pegawai` & `ubah_pegawai`: panggil resolusi; tulis `kelompok`
   eksplisit (termasuk `"internal"`).
6. **Perubahan kelompok** di `ubah_pegawai` (lama ≠ baru):
   - catat `log_audit("ubah_kelompok_pegawai", …)` dengan dari→ke;
   - set `portal_identitas_epoch` baru dan panggil
     `cabut_akses_portal_pegawai` bila keluar dari internal;
   - kembalikan `peringatan` bila NIP-nya masih dipakai `db.pejabat` satker
     itu (lunak, tidak memblokir);
   - **jangan** menawarkan/menjalankan sinkron aset untuk non-internal:
     `sinkron_aset` hanya dihitung bila kelompok baru internal (lihat 2.7).
7. `sinkron_aset_pemegang` & pratinjaunya: untuk non-internal kembalikan 400
   "Sinkron data pemegang hanya untuk pegawai internal".
8. `_nip_bentrok`: perilaku tetap; pesan galat menyebut kelompok pemilik NIP
   ("NIP … sudah terdaftar sebagai pegawai internal").

**Uji minimum:** invarian 5.5 butir 1–5 masing-masing satu uji; create
non-internal tanpa instansi → 400; instansi satker lain → 400 (bukan 403 —
jangan membocorkan keberadaannya); payload pihak ketiga berisi `agama` dan
`eselon2` → tersimpan kosong; pindah internal→eksternal mencabut akses portal
dan menulis audit; payload internal lama (tanpa `kelompok`) tersimpan identik
dengan hari ini + `kelompok: "internal"`.

**Terima:** uji lulus; `test_pegawai_cakupan_ekspor.py` masih lulus (layar
belum berubah).

---

### PGW-05 — Impor/ekspor/template per kelompok

**Berkas:** `backend/pegawai_utils.py`, `backend/routes/pegawai.py`,
`backend/tests/unit/test_pegawai_impor_kelompok.py` (baru), perluasan
`test_pegawai_cakupan_ekspor.py`.

**Keputusan:** kelompok ditentukan **parameter**, bukan kolom per baris. Satu
berkas = satu kelompok. Kolom "Kelompok" per baris akan memungkinkan satu
salah ketik mengubah pegawai internal menjadi pihak ketiga.

**Langkah:**

1. `KOLOM_IMPOR`: tambah `"instansi": "instansi_nama"`,
   `"nama instansi": "instansi_nama"`, `"jenis instansi": "_jenis_instansi"`
   (field semu, hanya dipakai saat instansi dibuat otomatis).
2. `HEADER_IMPOR` **tidak disentuh**. Tambah `header_impor(kelompok)`:
   internal → `HEADER_IMPOR`; lainnya → `["Instansi", "Jenis Instansi"]` +
   kolom `HEADER_IMPOR` yang field-nya ada di `FIELD_BOLEH(kelompok)`,
   urutan dipertahankan. `baris_ekspor_pegawai(doc, kelompok="internal")`
   menyusun baris mengikuti header itu.
3. `kunci_dedup_pegawai`: tingkat 4 (`"jabatan"`) memakai `instansi_nama`
   ternormalkan menggantikan `unit_kerja` bila non-internal.
4. `impor_pegawai`:
   - muat seluruh instansi satker+kelompok **sekali** jadi peta
     `nama_kunci → dok` (aturan performa: jangan `find_one` per baris);
   - baris tanpa "Instansi" → dilewati dengan catatan;
   - instansi tak dikenal → **dibuat otomatis** (`jenis` dari kolom bila sah,
     selain itu `lainnya`/`lembaga_negara_lain`), dikumpulkan di keluaran
     `instansi_dibuat: [nama…]` agar admin memeriksanya;
   - `_filter_dedup` untuk kunci NIP tetap lintas kelompok, **tetapi** bila
     dokumen yang cocok ber-kelompok lain → baris dilewati dengan catatan
     "NIP … sudah terdaftar sebagai pegawai <kelompok> — ubah kelompok lewat
     form". Lakukan lewat peta `lama_per_kunci` yang sudah dimuat sekali;
   - `$set` tidak pernah memuat `kelompok` untuk dokumen lama; `kelompok`
     hanya di `$setOnInsert`. `instansi_id`/`instansi_nama` di `$set` hanya
     bila kolom Instansi dipasok.
5. Template & ekspor: buka nilai `kelompok` selain internal (yang ditahan di
   PGW-02). Nama berkas `master_pegawai_<kelompok>_<kode>.xlsx`.
6. `TANPA_KOLOM` di uji cakupan: tambah `kelompok` (ditentukan parameter) dan
   `instansi_id` (diselesaikan dari kolom Instansi) — tulis alasannya di
   docstring seperti dua pengecualian yang ada.

**Uji minimum:** pulang-pergi (ekspor → impor → nilai sama) untuk ketiga
kelompok; impor berkas eksternal yang memuat NIP pegawai internal → internal
tak berubah sedikit pun; impor ulang berkas yang sama tidak menggandakan;
ekspor internal menghasilkan header **identik** dengan `HEADER_IMPOR`
baseline (uji membekukan daftar itu).

**Terima:** uji lulus; `test_pegawai_impor_dedup.py` lama lulus tanpa
disunting.

---

### PGW-06 — Layar Master Pegawai

**Berkas:** `frontend/src/pages/PegawaiPage.jsx`,
`frontend/src/lib/kelompokPegawai.js` (+ `.test.js`),
`frontend/src/components/pegawai/KelolaInstansi.jsx` (+ uji),
`frontend/src/components/pegawai/LencanaKelompok.jsx`,
`frontend/src/pages/__tests__/PegawaiKelompok.test.jsx`.

**Langkah:**

1. `lib/kelompokPegawai.js` (murni): `KELOMPOK`, `normalKelompok(p)`,
   `labelUnitPegawai(p)`, `fieldBoleh(ref, kelompok, field)`,
   `labelIdentitas(kelompok)`. Daftar opsi **dibaca dari**
   `/pegawai/referensi`; berkas ini hanya memuat label bawaan untuk keadaan
   belum-termuat.
2. **Pemilih kelompok** di bawah kepala halaman: tiga segmen — Internal ·
   Instansi Eksternal · Pihak Ketiga — masing-masing dengan cacah dari
   `rekap-unit.per_kelompok`. `data-testid="pegawai-kelompok-<kode>"`.
   Tinggi ≥ 44px di ≤ 1023px. Pilihan disimpan di state halaman; efek muat
   ulang **wajib** menyertakannya di deps (jebakan lama repo).
3. Semua pemanggilan daftar/template/ekspor/impor membawa `kelompok` aktif.
4. Judul & subjudul mengikuti tab. Tombol "Struktur Organisasi", saringan
   unit eselon, dan "Kelola unit" **hanya** pada tab internal. Tab lain:
   tombol "Kelola Instansi" + saringan instansi.
5. Daftar (kartu HP **dan** tabel desktop — dirender dua kali, ubah
   keduanya): baris kedua non-internal menampilkan `labelUnitPegawai`.
6. **Form:** `EMPTY` ditambah `kelompok: "internal"`, `instansi_id: ""`,
   `instansi_nama: ""`. Tab form dan field dirender bersyarat lewat
   `fieldBoleh`. Untuk non-internal tab "Pribadi" hilang; tab "Jabatan &
   Unit" menjadi "Jabatan & Instansi" berisi pemilih instansi
   (`PilihanRingkas`, opsi = instansi aktif kelompok itu + aksi "Tambah
   instansi baru") dan `unit_kerja` teks bebas. Bila tab aktif menjadi tak
   tersedia setelah kelompok berubah, pindahkan `tabForm` ke "identitas".
7. **Ubah kelompok** saat menyunting: pilihan di tab Identitas, disertai
   dialog konfirmasi yang **menyebut field yang akan dikosongkan** (hitung
   dari `ref.field_per_kelompok`). Tanpa konfirmasi, tidak tersimpan.
8. `KelolaInstansi.jsx`: komponen **level modul** (bukan di dalam
   `PegawaiPage`). Daftar + cari + tambah/ubah/nonaktifkan/hapus; `If-Match`
   pada ubah; pesan 409 server ditampilkan apa adanya.
9. Hasil impor menampilkan `instansi_dibuat` bila ada.
10. Aturan tampilan: `hover:bg-muted` (bukan `hover:bg-accent`); uji terang
    dan gelap; jangan memperkecil tombol.

**Uji minimum (Jest):** berganti tab memicu `GET /pegawai?kelompok=…`; form
pihak ketiga tidak merender field `agama`/`eselon1`; simpan non-internal
tanpa instansi menampilkan galat dan tidak memanggil API; konfirmasi ubah
kelompok muncul; `PegawaiAkarEselon.test.jsx` lama tetap lulus.
`test_pegawai_cakupan_ekspor.py` (backend) lulus dengan `EMPTY` baru.

**Terima:** `yarn lint` tanpa galat baru; `CI=true yarn test
--watchAll=false`; `CI=false yarn build`; periksa manual di lebar HP dan
desktop, terang dan gelap.

---

### PGW-07 — Pemilih lintas modul

Satu PR boleh memuat beberapa berkas di bawah, tetapi jangan lebih dari yang
bisa diuji sekaligus; pecah menjadi 07a (aset + BAST) dan 07b (sisanya) bila
perlu.

| Berkas | Perubahan |
|---|---|
| `AssetForm.jsx` | Muat `?kelompok=semua`. Baris hasil pemilih menampilkan `LencanaKelompok` + instansi. Peringatan "belum terdaftar" kini benar untuk orang luar. Di dalam `FullCameraSheet` tetap elemen native |
| `PilihPegawaiBast.jsx` | `description` memuat instansi; `pihakDariPegawai`: untuk non-internal `alamat` = `alamat` pegawai, jatuh ke `instansi_nama` (+ unit). Teks bantuan menyebut orang luar terdaftar tidak otomatis mendapat akses BMN Saya |
| `PenggunaanPage.jsx` | Dua pemuatan `/pegawai` → `kelompok=semua`; kolom rekap pemegang menampilkan `pegawai_master_instansi` |
| `PersediaanPage.jsx`, `lib/penerimaPersediaan.js` | `kelompok=semua`; `opsiPenerima` mengisi `unit` dari `labelUnitPegawai` |
| `PemeliharaanPage.jsx`, `TtdPermintaanPage.jsx` | `kelompok=semua`; saran menampilkan instansi |
| `ActivitySelectionPage.jsx` | Tim inti/pembantu `kelompok=internal`; tim peneliti/pendukung `kelompok=semua` dan `dari_pihak` terisi `instansi_nama` saat orangnya dipilih |
| `PejabatPage.jsx`, `PortalPemegangPanel.jsx` | Tulis `kelompok=internal` secara eksplisit |
| `KartuTapDialog.jsx` | Tampilkan lencana + instansi pada hasil tap |

**Uji:** perbarui/ tambah uji Jest tiap komponen yang disentuh
(`PilihPegawaiBast.test.jsx`, `penerimaPersediaan.test.js`, dst.). Pastikan
semua mock `axios.get` yang mencocokkan URL `/pegawai` persis diperbarui —
ini sumber kegagalan uji paling mungkin di paket ini.

**Terima:** seluruh suite Jest lulus; pemilih di form aset menampilkan orang
luar dengan lencana; pemilih pejabat tidak.

---

### PGW-08 — Laporan & dokumen

1. **Laporan Eksekutif — Distribusi Per Pengguna** (`routes/reports.py`
   sekitar `peg_master`, `report_utils.distribusi_pengguna`,
   `laporan_jenjang.baris_hierarki_pengguna`): proyeksi `peg_master` ditambah
   `kelompok`, `instansi_nama`; baris pengguna membawa keduanya; pengguna
   non-internal **tidak** jatuh ke "(tanpa unit organisasi)" melainkan ke
   pembagi tersendiri di akhir: "Instansi Eksternal" → nama instansi, lalu
   "Pihak Ketiga" → nama instansi. Pengguna internal tak berubah urutannya.
2. **Rekap pemegang / daftar per pemegang PDF** (modul Penggunaan): kolom
   unit memakai `label_unit_pegawai`.
3. **Wasdal** (`routes/wasdal.py`, `wasdal_utils.py`): temuan "pemegang
   berisiko" menyebut kelompok + instansi; untuk non-internal alasan
   "kontrak berakhir" berbunyi "masa hubungan berakhir".
4. **Penerima persediaan** (`penerima_utils.snapshot_penerima`): tambah
   `penerima_kelompok`, `penerima_instansi`; `penerima_unit` untuk
   non-internal = `label_unit_pegawai`.
5. **BAST:** tidak ada perubahan tata letak. Cukup pastikan `alamat` pihak
   terisi instansi (lewat PGW-07) dan snapshot pihak menyimpan `kelompok` +
   `instansi_nama` (tambahkan ke `PihakIn`/`PjTambahanIn` sebagai field
   opsional yang **dibekukan** saat terbit — BAST lama tidak disentuh).
6. Aturan blok tanda tangan **tidak berubah**: tetap lewat
   `baris_identitas_ttd`. Pihak ketiga otomatis nama-saja karena `non_asn`.

**Uji:** `test_laporan_eksekutif_pengguna_jenjang.py` diperluas (pengguna
eksternal masuk pembagi instansi; jumlah total tidak berubah);
`test_penerima_persediaan.py`; smoke-render PDF dengan harness FakeDB (pola
repo) — semua render lewat `asyncio.to_thread`/`run_renderer` seperti kini.

**Terima:** laporan lama (semua pengguna internal) menghasilkan baris yang
sama persis dengan sebelum paket.

---

### PGW-09 — Tautan instansi di modul berpihak-luar (opsional, satu PR per modul)

Urutan K6. Pola seragam, **aditif**:

- Kolom teks yang ada (`pihak`, `mitra`, `penyedia`, `pihak_pelaksana`, …)
  **tetap disimpan** sebagai snapshot — dokumen resmi harus menyebut nama
  pada saat terbit.
- Tambah field opsional `<kolom>_instansi_id`. Layar: masukan teks ber-
  datalist dari `GET /instansi-eksternal` (pola `penerimaPersediaan.js`:
  teks yang cocok menghasilkan id; yang tak cocok tetap diterima sebagai
  teks).
- Server memvalidasi id ter-scope satker (titik isolasi ke-5: lookup silang).
- Tidak ada backfill data lama.

**Terima per modul:** dokumen lama tanpa id tetap terbaca dan tercetak sama;
uji isolasi lookup silang.

---

### PGW-10 — Data uji & dokumentasi

- `backend/scripts/synthdata/generator.py` → `generate_pegawai`: parameter
  proporsi kelompok + pembangkit instansi; perbarui
  `test_synthdata_generator.py` dan skill `aman-testdata`.
- `README.md`, `frontend/src/pages/InfoPage.jsx` (PRD), teks
  `frontend/src/lib/bmnModules.js`.
- `.claude/skills/aman-dev/SKILL.md`: baris baru di "Peta repo" untuk
  `pegawai_kelompok.py` + aturan "pembaca baru `db.pegawai` wajib memilih
  kebijakan kelompok (uji titik pakai menagih)".
- `CHANGELOG.md`: tiap PR mengisi entrinya sendiri. Penomoran mengikuti
  **kepala CHANGELOG.md** (pada baseline: nomor entri = nomor PR + 9; angka
  "+2" di skill sudah usang).

---

### Ditunda (bukan bagian rencana ini; butuh keputusan pemilik tersendiri)

| Kode | Isi | Kenapa ditunda |
|---|---|---|
| X1 | FK `pengguna_pegawai_id` pada aset | Menyentuh registry field aset + ±10 turunan + antrean offline; memperbaiki 2.2 tetapi jauh lebih besar dari fitur ini |
| X2 | Jenis BAST & pasal khusus pihak luar | Bergantung hasil riset PGW-00 butir 2 |
| X3 | Portal BMN Saya untuk orang luar | Email di luar kendali instansi; perlu kajian keamanan |
| X4 | Perbaikan `pengguna_melekat_ke` (2.7) | Isu lama, bukan bagian permintaan |

---

## 9. Jebakan khusus fitur ini

1. **Jangan menambah field ke `FIELD_IDENTITAS_PORTAL`.** Hash identitas
   disimpan saat akses diberikan (`portal_pemegang_akses.identitas_hash`,
   dan `portal_otomasi.items[].identitas_pegawai` pada dokumen BAST) lalu
   **dibandingkan dengan hash
   yang dihitung ulang** (`portal_auth.py` sekitar baris 155,
   `portal_bast.py` 139 & 278). Mengubah daftar field mengubah hash semua
   pegawai → seluruh akses portal yang ada tercabut saat deploy. Perubahan
   kelompok dicabut lewat `portal_identitas_epoch`, yang sudah ada di daftar.
2. **`q_kelompok("internal")` harus `$in` dengan `None`.** Menulis
   `{"kelompok": "internal"}` membuang seluruh pegawai lama dari setiap
   daftar — tanpa galat.
3. **`scope_query_field_satker` meloloskan `kode_satker` kosong.** Instansi
   yang tertulis tanpa kode akan tampil di semua satker. Karena itu tulis
   lewat `require_admin_satker` (menolak super-admin tanpa Satker Aktif).
4. **Email kembar mencabut akses.** `cabut_email_bentrok` mencabut akses
   portal semua pegawai ber-email sama, lintas satker. Orang pihak ketiga
   sering memakai email perusahaan bersama; bila salah satunya sama dengan
   email pegawai internal, akses internal itu tercabut. Aturannya benar
   (email ambigu bukan kredensial) dan **tidak diubah** — tetapi form harus
   memperingatkan sebelum simpan bila email sudah dipakai orang lain.
5. **Bundel PWA lama.** Klien ter-cache memanggil `GET /pegawai` tanpa
   parameter dan mengirim payload tanpa `kelompok`. Keduanya harus tetap
   berarti "internal" selamanya.
6. **Daftar dirender dua kali** (kartu HP + tabel desktop). Mengubah satu
   saja membuat tampilan HP dan desktop berselisih.
7. **Impor adalah jalur tulis yang melewati form.** Semua aturan Bab 5 harus
   berlaku di impor juga — `terapkan_aturan_kelompok` dipanggil per baris.
8. **Unit kerja non-internal tidak boleh masuk master unit.** Selain
   saringan di `bangun_dari_pegawai`, invarian 4 (eselon dikosongkan)
   adalah lapis kedua. Keduanya diperlukan.
9. **`validate_pegawai` dipakai impor dengan keluhan NIP disaring**
   (`if "NIP" not in e`). Pesan validasi kelompok jangan memuat kata "NIP"
   kecuali memang tentang NIP, agar tidak ikut tersaring.

---

## 10. Verifikasi

### Tiap paket

Lingkungan sesi baru belum tentu punya `pytest`/`mongomock_motor`; pasang
dulu dengan `pip install -r backend/requirements-dev.txt` (CI memakai berkas
yang sama).

```bash
cd backend && python -m compileall -q . -x 'venv|__pycache__'
python -m pytest tests/unit -q
cd ../frontend && yarn lint
CI=true yarn test --watchAll=false
CI=false yarn build
```

### Uji regresi kunci (harus tetap lulus tanpa disunting sampai PGW-05)

`test_pegawai_utils.py`, `test_pegawai_impor_dedup.py`,
`test_pegawai_cakupan_ekspor.py` (hanya `TANPA_KOLOM` yang bertambah),
`test_portal_*.py`, `test_unit_kerja_*.py`, `test_penerima_persediaan.py`,
`test_laporan_eksekutif_pengguna_jenjang.py`, `test_backup_utils.py`.

### Uji terima akhir (setelah PGW-08, di lingkungan uji — bukan produksi)

1. Buat instansi "Kementerian X" (eksternal) dan "PT Y" (pihak ketiga).
2. Tambah satu orang di tiap kelompok; pastikan field terlarang tak tersimpan.
3. Ekspor tiap tab → ubah satu sel → impor → hanya sel itu berubah.
4. Impor berkas pihak ketiga yang memuat NIK pegawai internal → ditolak per
   baris, internal utuh.
5. Jadikan orang eksternal pemegang aset lewat BAST → aset menampilkan
   namanya; ia **tidak** mendapat akses portal; rekap pemegang menampilkan
   instansinya.
6. Set `tgl_selesai_kontrak` orang itu ke kemarin → muncul di "perlu serah
   terima" dan temuan Wasdal.
7. Login admin satker lain → tak satu pun data di atas terlihat.
8. `Bangun unit dari pegawai` → tidak ada unit baru dari orang luar.
9. Laporan Eksekutif: orang luar tampil di pembagi instansi; total sama.
10. Cetak BAST dengan pihak ketiga ber-NIK → blok tanda tangan nama saja.

### Definisi selesai

CI hijau · terdeploy · UI Indonesia · CHANGELOG terisi · status Bab 8
diperbarui · tanpa uji lama yang dilonggarkan.

---

## 11. Risiko dan yang belum terverifikasi

| # | Risiko / ketidakpastian | Keyakinan | Mitigasi |
|---|---|---|---|
| R1 | Pembaca internal-saja ikut membaca orang luar | Tinggi bahwa ini risiko utama (57 titik pakai terhitung, 30 di luar rute pegawai) | Urutan pagar-dulu + uji titik pakai + bawaan API |
| R2 | Daftar titik pakai Bab 7 tidak lengkap | Sedang — hasil `grep` pada baseline; pola tak langsung bisa terlewat | Uji anti-drift PGW-02 memindai ulang; revalidasi di awal PGW-02 |
| R3 | `PegawaiPage.jsx` (1.954 baris) sulit disunting aman | Tinggi | Ekstrak ke komponen level modul; jangan menulis ulang halaman |
| R4 | Dasar hukum per kelompok (ahli waris, penanda tangan BAST pihak luar, batas data pribadi) | **Rendah — belum diriset** | PGW-00; bawaan konservatif sampai terjawab |
| R5 | Daftar `JENIS_INSTANSI`/`PERAN_INSTANSI` tidak cocok istilah resmi | Sedang | Dikunci di PGW-00 |
| R6 | Instansi dibuat otomatis saat impor menghasilkan kembaran salah ketik | Sedang | `nama_kunci` + laporan `instansi_dibuat`; tidak menutup salah ketik sungguhan |
| R7 | Orang pihak ketiga tanpa NIK tak bisa jadi pemegang tertaut | Tinggi (sifat desain, 2.2) | Disebut terang di layar; X1 bila pemilik menghendaki |
| R8 | Temuan 2.7 ternyata disengaja | Sedang | Tidak diubah; hanya dilaporkan |

Dokumen ini tidak mengutip nomor pasal selain yang sudah tertulis di kode dan
`docs/` repo. Klaim regulasi baru harus melalui PGW-00 dan masuk pustaka
beserta sumbernya.
