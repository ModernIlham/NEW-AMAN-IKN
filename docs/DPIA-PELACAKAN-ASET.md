# DPIA — Penilaian Dampak Pelindungan Data Pribadi
## Pelacakan Lokasi Aset BMN (AMAN IKN)

> **Status:** Fase 10 program Spasial & IoT — **gerbang wajib sebelum satu baris
> data posisi pertama masuk sistem.**
> **Dasar hukum:** UU 27/2022 tentang Pelindungan Data Pribadi (UU PDP).
> **Dokumen induk teknis:** `docs/ARSITEKTUR-SPASIAL-IOT.md` §10.
> **Penegakan teknis:** `backend/privasi_utils.py` (+ 18 uji unit).

---

## 1. Mengapa DPIA ini ada

Melacak perangkat yang **dipegang perorangan** berarti memproses **data pribadi
orang itu** — bukan sekadar data barang negara. Sebuah laptop dinas yang
melaporkan posisinya tiap 5 menit selama 24 jam akan merekam, tanpa satu pun
niat buruk: rumah pemegangnya, jam berangkat dan pulang, kunjungan ke fasilitas
kesehatan, tempat ibadah, dan pola hidup keluarganya.

Karena itu DPIA disusun **sebelum** kode ingest dibangun, bukan sesudah. Kajian
privasi yang datang belakangan hanya bisa menambal; kajian yang datang lebih
dulu menentukan bentuk sistemnya.

## 2. Pernyataan kebijakan (satu kalimat)

> **Sistem ini melacak BARANG NEGARA, bukan ORANG.**
> Untuk perangkat yang dipegang perorangan, sistem **sengaja hanya menyimpan
> level gedung/wilayah** dan **hanya pada jam kerja**. Presisi penuh dibuka
> **hanya** saat barang dilaporkan hilang, dengan **persetujuan pejabat**,
> **beralasan tertulis**, **berbatas waktu**, dan **tercatat**.

Ini kepatuhan sekaligus keputusan teknis yang lebih murah: menyimpan "gedung X,
jam kerja" alih-alih jejak titik 24/7 memangkas volume data secara drastis.

## 3. Data yang diproses & dasar pemrosesan

| Kategori | Contoh | Dasar (UU PDP Ps. 20) |
|---|---|---|
| Data barang | NUP, kode barang, kondisi | Pelaksanaan kewenangan penatausahaan BMN |
| Lokasi barang tetap | Koordinat gedung, ruangan | Pelaksanaan kewenangan penatausahaan BMN |
| Lokasi kendaraan dinas | Jejak perjalanan kendaraan | Pelaksanaan kewenangan + pengawasan penggunaan BMN |
| **Lokasi perangkat pegangan perorangan** | Gedung tempat laptop berada | Pelaksanaan kewenangan, **dengan minimisasi ketat** (§4) |

Pemegang barang **bukan** subjek yang dilacak; ia terdampak sebagai **akibat**
dari melacak barang. Karena itu prinsip minimisasi diterapkan paling keras
justru pada kategori terakhir.

## 4. Minimisasi — tiga profil yang ditegakkan kode

Ditegakkan `privasi_utils.PROFIL_PRIVASI`; setiap observasi **wajib** melewati
`saring_observasi()` sebelum menyentuh disk.

| Profil | Presisi disimpan | Jendela waktu | Retensi |
|---|---|---|---|
| `aset_tetap` | Koordinat penuh | 24 jam | 365 hari |
| `kendaraan` | Koordinat penuh | 24 jam | 90 hari |
| **`personal`** | **Wilayah/gedung saja — koordinat DIBUANG** | **07:00–18:00, hari kerja** | **30 hari** |

**Gagal-tertutup.** Profil yang tak dikenal (salah ketik, perangkat baru belum
dikonfigurasi) jatuh ke `personal` — profil paling ketat. Perangkat yang lupa
diatur tidak akan merekam penuh 24/7.

**Tidak disimpan ≠ disimpan lalu disembunyikan.** Observasi personal di luar jam
kerja **ditolak sebelum penulisan**. Data yang tak pernah ada tak bisa bocor,
tak bisa disalahgunakan, dan tak bisa diminta lewat jalur hukum.

## 5. Pembukaan presisi darurat (barang hilang)

Tiga syarat kumulatif, ditegakkan `izin_darurat_sah()`:

1. **Alasan tertulis** ≥ 10 karakter — jejak akuntabilitas, bukan formalitas.
2. **Pejabat penyetuju** yang **bukan pemohon** — pemisahan peran mencegah satu
   orang membuka pelacakan atas rekannya sendiri.
3. **Masa berlaku ≤ 72 jam** — izin permanen sama dengan kebijakan yang
   dibatalkan diam-diam.

Setiap pembukaan tercatat di `audit_logs`.

## 6. Risiko & mitigasi

| Risiko | Mitigasi | Status |
|---|---|---|
| Pola hidup pemegang terekam | Profil `personal`: wilayah saja + jam kerja | **Ditegakkan kode** |
| Perangkat lupa dikonfigurasi → rekam penuh | Gagal-tertutup ke profil terketat | **Ditegakkan kode** |
| Izin darurat jadi permanen | Plafon 72 jam + wajib pejabat berbeda | **Ditegakkan kode** |
| Data menumpuk melewati kebutuhan | Retensi per profil + TTL index dari sumber angka yang sama | **Ditegakkan kode** |
| **Posisi bocor ke Peta Kolaborasi publik** | Posisi IoT disimpan TERPISAH (`iot_observasi`) & tak pernah menimpa `koordinat_*` aset; payload publik memakai **allowlist** `KUNCI_PUBLIK_TITIK` + uji regresi | **Ditegakkan kode** |
| Koordinat menyelinap lewat `lokasi_spasial.titik` | `saring_observasi` membuang kunci titik mentah di dalam snapshot lokasi | **Ditegakkan kode** |
| Retensi benar di DB tapi bocor lewat arsip backup | `iot_observasi` masuk `SKIP_COLLECTIONS` — observasi tak pernah ikut arsip | **Ditegakkan kode** |
| Akses lintas satker | `scope_query_field_satker` + guard aset (pola Fase 8–9) | Sudah berlaku |
| Kebocoran insiden | Runbook pemberitahuan sesuai UU PDP | **Perlu disusun** |

## 7. Hak subjek data

Pemegang barang berhak mengetahui bahwa perangkat dinas yang dipegangnya
melaporkan keberadaan **barang**. Kewajiban yang menyusul:

- **Pemberitahuan** saat serah-terima BMN (dicantumkan pada BAST).
- **Akses**: pemegang dapat meminta rekap data lokasi perangkat yang dipegangnya.
- **Penghapusan**: otomatis lewat retensi; permintaan lebih awal ditangani
  sepanjang tak bertentangan dengan kewajiban penatausahaan BMN.

## 8. Sifat yang muncul dari desain (bukan kebetulan)

Perangkat profil `personal` menyimpan **hanya node denah**, dan node hanya ada di
dalam kawasan yang dipetakan satker. Konsekuensinya: laptop dinas **di rumah
pemegangnya** berada di luar seluruh poligon → tak ada node → **tidak ada satu
baris pun yang tersimpan**. Rumah, klinik, dan tempat ibadah tak perlu
di-blacklist satu per satu; bentuk sistemnya yang membuat mereka tak terekam.

## 9. Yang BELUM dikerjakan (jujur, agar tak dianggap selesai)

- Runbook notifikasi insiden kebocoran (butuh keputusan pejabat, bukan kode).
- Teks pemberitahuan di BAST — naskahnya keputusan pejabat; kaitnya ke dokumen
  BAST menyusul di fase berikutnya.
- Alur permohonan & persetujuan izin darurat sebagai **endpoint**;
  `izin_darurat_sah()` sudah menegakkan syaratnya, tetapi pembukaan presisi
  belum punya antarmuka — untuk sekarang tak ada jalur yang bisa memakainya.
- Antarmuka pengelolaan perangkat di frontend (registry & ingest sudah jalan
  lewat API).

---

*Ditinjau ulang setiap kali profil privasi, retensi, atau cakupan pelacakan
berubah. Perubahan angka retensi WAJIB diubah di `privasi_utils.PROFIL_PRIVASI`
— dokumen ini mengikuti kode, bukan sebaliknya, agar tak ada kepatuhan yang
hanya benar di atas kertas.*
