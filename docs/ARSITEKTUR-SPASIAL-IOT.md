# ARSITEKTUR SPASIAL & IoT — AMAN IKN

**Dokumen arsitektur tunggal** · Sintesis 5 dimensi riset · 2026-07-26
Repo: `/home/user/NEW-AMAN-IKN` · FastAPI + Motor/MongoDB 7.0.30 + React/Leaflet · VPS 8 GB, 4 worker uvicorn

**Legenda:** **[F]** fakta bersumber · **[O]** opini/keputusan arsitek · **[V]** terverifikasi di repo/mesin ini

---

## BAGIAN 0 — RINGKASAN KEPUTUSAN

| # | Topik | Keputusan | Alternatif ditolak |
|---|---|---|---|
| 1 | Hierarki spasial | **Kawasan → Zona(WP) → Distrik(SWP) → Blok → Persil → Tapak → Gedung → Lantai → Sayap → Ruangan** | Urutan pemilik apa adanya (kawasan salah posisi) |
| 2 | Fixed vs configurable | **Hybrid**: registry `spasial_level` (di-governance) + pohon generik `spasial_node` | 5 tingkat dikunci keras; pohon bebas total |
| 3 | Zona RDTR (R.2, K.3) | **Atribut** `zona_kode`, bukan level pohon | Zona sebagai node induk |
| 4 | Koleksi MongoDB | **Satu koleksi polimorfik** `spasial_node` | Satu koleksi per tingkat |
| 5 | Pola pohon | **Hybrid** `parent_id` + `ancestors[]` + `jalur` | Nested set; `$graphLookup` di jalur panas |
| 6 | Penomoran lantai | **`ordinal` integer rapat** (0 = akses utama, −1 basement) + `label` + `elevasi_m` | `lantai: str` teks bebas (kondisi sekarang); pecahan 1.5 untuk mezanin |
| 7 | Gedung→Lantai | **BUKAN containment** — model 2,5D, uji IoU ≥ 0,50 | `$geoWithin` ketat (basement selalu gagal) |
| 8 | Pustaka geometri backend | **shapely 2.1.2** (lazy-import, hanya jalur impor/validasi) | GDAL/geopandas/Fiona; pure-Python untuk topologi kompleks |
| 9 | CRS / reproyeksi | **`utm` (27 KB) + parser WKT regex + konfirmasi manusia di pratinjau** | pyproj (+33 MB) di fase awal |
| 10 | Baca KML | **`lxml` `recover=True`** (sudah ada) | fastkml (menolak KML nyata secara default) |
| 11 | Tulis KML | **`xml.etree` stdlib** (pola `_build_kml` sudah ada) | simplekml (LGPL, bug `schemaUrl="##9"`) |
| 12 | Shapefile | **pyshp 3.1.4 → 3.1.6** | GDAL/ogr |
| 13 | Gambar di Leaflet | **`@geoman-io/leaflet-geoman-free` 2.20.0** (MIT, lazy-load) | leaflet-draw (mati sejak 2018); terra-draw (tanpa cut/measure) |
| 14 | Vector tile | **JANGAN** — GeoJSON per-bbox + LOD + `L.canvas` | Leaflet.VectorGrid (rilis 2017, lisensi Beerware) |
| 15 | Transport IoT | **HTTP batch** saja | MQTT/Mosquitto (ditunda sampai ≥1.000 perangkat) |
| 16 | Antrean/stream | **`event_bus.py` (capped collection)** yang sudah ada | Kafka, Celery, RabbitMQ |
| 17 | Histori posisi | **Time-series** `iot_observasi` + koleksi biasa `iot_posisi_terakhir` | Time-series saja (tak dukung `$near`, tak bisa update) |
| 18 | Geofence | **State machine + histeresis** (buffer keluar 25 m, dwell 120/180 dtk) | Uji point-in-polygon polos (flapping di batas) |
| 19 | Privasi | **Degradasi presisi di INGEST** + dasar hukum PMK 207/2021, bukan persetujuan | Simpan presisi penuh lalu sembunyikan di UI |
| 20 | Kustodian | **Koleksi temporal `asset_custody` append-only** + cache di dokumen aset | Field kustodian di dokumen aset (kondisi sekarang) |

**Dependensi baru total:** backend **1 paket** (`shapely`) + 1 kenaikan versi (`pyshp`) + 1 paket mikro (`utm`, 27 KB). Frontend **1 paket** (`leaflet-geoman-free`, lazy). **Nol GDAL, nol PostGIS, nol Kafka, nol broker.**

---

## BAGIAN 1 — HIERARKI SPASIAL FINAL

### 1.1 Vonis atas urutan pemilik

Pemilik menyebut: **"zona, distrik, kawasan, gedung, lantai"**.

| Bagian | Status | Bukti |
|---|---|---|
| `gedung → lantai` | ✅ **Benar** | Persis IMDF `Building → Level` dan IFC `IfcBuilding → IfcBuildingStorey` **[F]** |
| `zona > distrik` | ✅ **Arah benar** | Cocok dengan WP > SWP dalam Permen ATR/BPN 11/2021 **[F]** |
| `kawasan` di posisi 3 (kecil) | ❌ **TERBALIK** | UU 26/2007 Pasal 1: *"Kawasan adalah wilayah yang memiliki fungsi utama lindung atau budi daya"*; PP 21/2021: *"Zona adalah **kawasan** dengan fungsi dan karakteristik tertentu"* → zona adalah **sejenis** kawasan, bukan induknya. Di IKN, "kawasan" = **KIKN & KPIKN**, payung tertinggi. **[F]** |
| `zona` sebagai wadah | ⚠️ **Salah jenis (dalam arti RDTR)** | Zona RDTR (`R.2`, `K.3`, `SPU-1`) adalah *pewarnaan fungsi* pada blok — satu zona bisa tersebar di banyak blok terputus → mustahil jadi node pohon **[F]** |
| `distrik` | ⚠️ **Bukan istilah tata ruang** | "Distrik" = padanan **kecamatan** khusus Papua (UU 21/2001 Otsus). Tidak muncul di terminologi resmi Otorita IKN, yang memakai `WP → SWP → Blok` **[F]** |
| Level hilang | ❌ | **Blok**, **Persil**, **Tapak**, dan **RUANGAN**. Ruangan justru jangkar KIR/DBR (PMK 181/2016) — tanpa itu seluruh fitur tidak menyambung ke penatausahaan BMN |

> **Kesalahan struktural sesungguhnya hanya SATU: posisi "kawasan".** Sisanya soal penamaan dan level yang belum disebut — bukan salah logika. Urutan pemilik **60% benar**, dan bagian yang paling teknis (`gedung → lantai`) justru sudah persis standar internasional.

### 1.2 Naskah koreksi untuk pemilik (siap dibacakan)

> "Urutan Bapak sudah benar arah mengerucutnya, dan `gedung → lantai` persis standar internasional (IMDF/OGC). Ada **satu penyesuaian** dari riset regulasi: menurut **UU 26/2007**, **kawasan** justru istilah yang **paling luas** — di IKN, 'kawasan' itu **KIKN dan KPIKN**, payung dari segalanya. Jadi urutannya menjadi:
>
> **Kawasan → Zona → Distrik → Blok → Tapak → Gedung → Lantai → Ruangan**
>
> Semua istilah Bapak tetap dipakai — 'kawasan' hanya naik ke posisi teratas. Kami menambahkan **Blok** (istilah resmi RDTR IKN), **Tapak** (kompleks kantor), dan **Ruangan** — Ruangan penting karena dialah dasar **KIR & DBR** sesuai PMK 181/2016.
>
> Satu hal lagi: 'zona' dalam arti dokumen RDTR (kode R.2, K.3, SPU) kami simpan sebagai **label fungsi** yang menempel di Blok, bukan tingkatan tersendiri — sebab satu zona bisa tersebar di banyak blok terpisah, sehingga kalau dijadikan tingkatan, aturan 'anak harus di dalam induk' tidak akan pernah bisa jalan."

### 1.3 Hierarki kanonik (tabel padanan lengkap)

Ordinal **berjarak 10** agar level baru bisa disisipkan tanpa migrasi.

| ordinal | Kode baku | Label UI (preset `ikn_akrab`) | Label baku (preset `rdtr_baku`) | Padanan internasional | Wajib | Geometri | Containment |
|---|---|---|---|---|---|---|---|
| 10 | `WILAYAH` | Wilayah | Wilayah / KSN | *Region* | tidak | MultiPolygon | akar |
| 20 | `KAWASAN` | **Kawasan** ⬆ | Kawasan | *Area (macro)* | tidak | MultiPolygon | ketat |
| 30 | `WP` | **Zona (WP)** | Wilayah Perencanaan | *Planning Area* | tidak | Polygon | ketat |
| 40 | `SWP` | **Distrik (Sub-WP)** | Sub Wilayah Perencanaan | *Sub-district* | tidak | Polygon | ketat |
| 50 | `BLOK` | Blok | Blok | *Block* | tidak | Polygon | ketat |
| 55 | `SUBBLOK` | Sub-Blok | Sub-Blok | *Sub-block* | tidak | Polygon | ketat |
| 60 | `PERSIL` | Persil / Bidang Tanah | Persil (NIB) | *Parcel / Lot* | tidak | Polygon | longgar |
| 70 | `TAPAK` | Kompleks / Tapak | Tapak | **IMDF `Venue`** | disarankan | Polygon | ketat |
| 80 | `GEDUNG` | **Gedung** | Gedung | **IMDF `Building`** / `IfcBuilding` | tidak | Polygon (footprint) | ketat |
| 90 | `LANTAI` | **Lantai** | Lantai | **IMDF `Level`** / `IfcBuildingStorey` | tidak | Polygon + `ordinal` | **sumbu_z** |
| 95 | `SAYAP` | Sayap / Zona Lantai | Seksi | **IMDF `Section`** | tidak | Polygon | ketat |
| 100 | `RUANGAN` | **Ruangan** | Ruangan | **IMDF `Unit`** / `IfcSpace` | **WAJIB (leaf)** | Polygon | ketat |
| 110 | `TITIK` | Titik / Sub-ruang | Fitur | IMDF `Fixture`/`Anchor` | tidak | Point | longgar |

**Satu data, dua tampilan:** `preset_penamaan` hanya mengganti `label_ui`. `kode_baku` tetap benar untuk ekspor/dokumen resmi.

### 1.4 Yang BUKAN level (atribut paralel)

| Konsep | Disimpan sebagai | Alasan |
|---|---|---|
| Zona/Sub-Zona RDTR (`R.2`, `K.3`, `SPU-1`) | field `zona_kode`, `subzona_kode` | Tersebar & terputus; bukan relasi induk-anak |
| Fungsi kawasan (lindung/budi daya) | field `fungsi_kawasan` | Klasifikasi UU 26/2007 |
| Toponim (Sumbu Kebangsaan, Plaza Bhinneka) | `nama_alias[]` (alias pencarian) | Landmark, bukan tingkatan. Pengguna Wasdal mengetik "Sumbu Kebangsaan", bukan "WP 1 SWP 1 Blok A.3" |
| Kecamatan/Kelurahan/Desa | `wilayah_admin{}` **paralel** | ⚠️ Batas administratif dan batas perencanaan **sering saling potong**. Kalau dipaksa satu pohon, validasi containment melapor pelanggaran palsu terus-menerus |

### 1.5 Fakta IKN yang WAJIB dipakai (seed preset)

**Angka UU 21/2023 — bukan UU 3/2022 [F]:**

| Entitas | Luas (UU 21/2023) | Catatan |
|---|---|---|
| Wilayah daratan IKN | **252.660 ha** | (UU 3/2022: 256.142 ha — **kedaluwarsa**) |
| Wilayah perairan | 69.769 ha | |
| **KIKN** | **56.159 ha** | Kawasan inti |
| **KPIKN** | **196.501 ha** | **SEJAJAR** KIKN, bukan induknya |
| **KIPP** | **6.671 ha** | Di **dalam** KIKN |

> **KOREKSI PENTING [F]:** `KIKN 56.159 + KPIKN 196.501 = 252.660 ha` = seluruh daratan, **pas**. Artinya KIKN dan KPIKN adalah **saudara sebaya yang saling lepas**, bukan induk-anak. Definisi resmi: *"KPIKN adalah kawasan **di sekitar** KIKN"*. Bila dimodelkan `KPIKN → KIKN → KIPP`, semua uji containment gagal dan luas dobel-hitung.

```
Wilayah IKN (KSN IKN, 252.660 ha darat)
├── KAWASAN: KIKN (56.159 ha)
│   ├── WP 1 — KIPP (6.671 ha)  ├─ SWP 1-A / 1-B / 1-C
│   ├── WP 2 — IKN Barat (17.206 ha)
│   ├── WP 3 — IKN Selatan (6.753 ha)
│   ├── WP 4 — IKN Timur 1 (9.761 ha)
│   ├── WP 5 — IKN Timur 2 (3.270 ha)
│   └── WP 6 — IKN Utara (12.067 ha)
└── KAWASAN: KPIKN (196.501 ha)
    └── WP 7–9 — Simpang Samboja, Kuala Samboja, Muara Jawa
```
*(Penomoran WP 3 & 6–9 hasil inferensi dari urutan penyebutan — verifikasi ke Perpres 64/2022 sebelum seed produksi. Enam WP perkotaan berjumlah ≈55.728 ha ≈ KIKN 56.159 ha, konsisten.)*

**Rujukan regulasi untuk `docs/PUSTAKA-REGULASI-BMN.md`:** UU 26/2007 · PP 21/2021 · Permen ATR/BPN 11/2021 jo. **6/2026** · **Permen ATR/BPN 14/2021** (basis data & penyajian peta — standar atribut SHP resmi Indonesia; template AMAN harus field-compatible) · UU 3/2022 jo. **UU 21/2023** · Perpres 63/2022 & 64/2022 · Perka OIKN 1/2023, 3/2023, **10/2024**.

### 1.6 Keputusan: HYBRID (bukan dikunci, bukan bebas total)

**Alasan menolak hierarki tetap 5 tingkat [F]:**
1. **IFC 4.3 = ISO 16739-1:2024 justru MENINGGALKAN hierarki kaku** — `IfcBuilding` digeneralisasi jadi `IfcFacility`, `IfcBuildingStorey` jadi `IfcFacilityPart`, dan `IfcSite`/`IfcFacilityPart`/`IfcSpace` semuanya **opsional**, dirangkai lewat `IfcRelAggregates`. Standar seberat IFC bergerak ke generik demi menampung rel/jalan/pelabuhan.
2. **CityGML 3.0 (2023)** melakukan hal sama: semua objek berbasis `Space`/`SpaceBoundary`, LOD4 **dihapus**.
3. **Realita BMN:** satker KIPP butuh 8 tingkat; satker daerah hanya `Tapak → Gedung → Lantai → Ruangan`; aset **Jalan-Irigasi-Jaringan** tidak punya gedung; **KIB Tanah** berhenti di persil. Hierarki tetap memaksa node kosong palsu.
4. **RDTR IKN masih terbit bertahap** (Perka 1/2023 → 3/2023 → 10/2024 …); Permen 11/2021 sudah diubah oleh Permen 6/2026.

**Alasan menolak pohon bebas total:** mematikan deteksi otomatis Wasdal, aturan overlay, ekspor sesuai Permen 14/2021, dan agregasi laporan per tingkat.

---

## BAGIAN 2 — SKEMA DOKUMEN MongoDB

Konvensi repo yang dipatuhi: field `id` (uuid aplikasi, bukan `_id`), stempel `kode_satker` di setiap INSERT, `datetime.now(timezone.utc)`.

### 2.1 `spasial_level` — registry tata kelola

Di-seed, hanya `require_super_admin` yang boleh mengubah.

```json
{
  "id": "lvl-swp",
  "kode_satker": "",
  "ordinal_level": 40,
  "kode_baku": "SWP",
  "label_ui": "Distrik (Sub-WP)",
  "label_baku": "Sub Wilayah Perencanaan",
  "label_jamak": "Distrik",
  "parent_kode": ["WP"],
  "geometri_diizinkan": ["Polygon", "MultiPolygon"],
  "wajib_dalam_induk": true,
  "validasi_containment": "ketat",
  "boleh_tumpang_tindih_sesama": false,
  "punya_ordinal_lantai": false,
  "ambang_sliver_m2": 200.0,
  "tol_snap_m": 1.0,
  "tol_simplifikasi_m": 2.0,
  "presisi_desimal": 6,
  "warna_default": "#0ea5e9",
  "zoom_min_render": 11,
  "standar": { "imdf": null, "permen14": "SWP", "ifc": "IfcSite" },
  "aktif": true
}
```

`validasi_containment` ∈ `akar` · `ketat` · `longgar` · **`sumbu_z`** (khusus `LANTAI`).

**Seed default (preset `ikn_akrab`):** 13 baris sesuai tabel §1.3.

### 2.2 `spasial_node` — data aktual (koleksi polimorfik)

**Contoh GEDUNG:**

```json
{
  "id": "sn_9f3c1a7e-2b44-4d80-9c11-6a5e0d2f8b31",
  "kode_satker": "412345",

  "tipe": "GEDUNG",
  "ordinal_level": 80,

  "parent_id": "sn_tapak_kemenkeu",
  "ancestors": ["sn_ikn", "sn_kikn", "sn_wp1", "sn_swp1a", "sn_blok_a3", "sn_tapak_kemenkeu"],
  "jalur": ",sn_ikn,sn_kikn,sn_wp1,sn_swp1a,sn_blok_a3,sn_tapak_kemenkeu,",
  "ancestors_nama": ["IKN", "KIKN", "WP 1 — KIPP", "SWP 1-A", "Blok A.3", "Kompleks Kemenkeu"],
  "kedalaman": 6,

  "kode": "GD-KP01-A",
  "nama": "Gedung Kantor Kementerian A",
  "nama_alias": ["Gedung A", "Tower A"],

  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [[[
      [116.712345, -0.951234], [116.713012, -0.951234],
      [116.713012, -0.950610], [116.712345, -0.950610],
      [116.712345, -0.951234]
    ]]]
  },
  "geometry_ringkas": null,
  "bbox": [116.712345, -0.951234, 116.713012, -0.950610],
  "titik_wakil": { "type": "Point", "coordinates": [116.712679, -0.950922] },

  "metrik": {
    "luas_m2": 4612.8, "keliling_m": 276.4, "jumlah_verteks": 5,
    "thinness": 0.759, "dihitung_pada": "2026-07-26T02:11:04Z"
  },

  "lantai": null,
  "rentang_lantai": { "min": -2, "max": 12 },

  "zona_kode": "SPU-1",
  "subzona_kode": null,
  "fungsi_kawasan": "budi_daya",
  "wilayah_admin": { "provinsi": "64", "kabkota": "6403", "kecamatan": "640309", "kelurahan": null },

  "properties": {
    "fungsi": "perkantoran", "tahun_bangun": 2025,
    "nib": null, "kib_tanah_nup": null
  },

  "sumber": {
    "jenis": "impor_shp", "berkas_gridfs_id": "66a1f0c3e4b0a1c2d3e4f5a6",
    "nama_berkas": "gedung_kipp_2026.shp", "crs_asal": "EPSG:32750",
    "crs_dikonfirmasi_oleh": "operator_kpb_412345"
  },

  "prioritas": 0,
  "overlap_disengaja": false,
  "parent_sekunder_ids": [],
  "bagi_luas": null,

  "validasi": {
    "status": "peringatan",
    "diperiksa_pada": "2026-07-26T02:11:04Z",
    "temuan": [{
      "kode": "TUMPANG_SIBLING", "tingkat": "peringatan",
      "lawan_id": "sn_gedung_kp01_b", "lawan_nama": "Gedung Kantor Kementerian B",
      "rasio": 0.011, "luas_m2": 51.2,
      "pesan": "Berimpit 1,1% (51 m²) dengan Gedung Kantor Kementerian B. Biasanya ini garis batas yang belum rapat.",
      "aksi": ["rapikan_otomatis", "tandai_disengaja", "sorot_di_peta"]
    }]
  },

  "status": "aktif",
  "versi": 3,
  "versi_denah": 12,
  "berlaku_dari": "2026-07-01T00:00:00Z",
  "created_at": "2026-06-02T08:14:00Z", "created_by": "operator_kpb_412345",
  "updated_at": "2026-07-26T02:11:04Z", "updated_by": "operator_kpb_412345"
}
```

**Contoh LANTAI (skema lantai final):**

```json
{
  "id": "sn_lt_b1_gd_a",
  "kode_satker": "412345",
  "tipe": "LANTAI", "ordinal_level": 90,
  "parent_id": "sn_9f3c1a7e-2b44-4d80-9c11-6a5e0d2f8b31",
  "ancestors": ["sn_ikn","sn_kikn","sn_wp1","sn_swp1a","sn_blok_a3","sn_tapak_kemenkeu","sn_9f3c1a7e-…"],
  "jalur": ",sn_ikn,sn_kikn,sn_wp1,sn_swp1a,sn_blok_a3,sn_tapak_kemenkeu,sn_9f3c1a7e-…,",
  "kode": "GD-KP01-A-B1",
  "nama": "Basement 1",

  "lantai": {
    "ordinal": -1,
    "label": "Basement 1",
    "label_pendek": "B1",
    "elevasi_m": -4.20,
    "tinggi_bersih_m": 3.20,
    "kategori": "basement",
    "publik": true,
    "gedung_ids": ["sn_9f3c1a7e-…"]
  },

  "geometry": { "type": "MultiPolygon", "coordinates": [[[ /* … */ ]]] },

  "gambar_denah": {
    "gridfs_id": "66a1f0c3e4b0a1c2d3e4f5a6",
    "nama_berkas": "denah_b1_rev3.png",
    "opasitas": 0.75,
    "sudut_bumi": [
      [116.712300, -0.950570], [116.713060, -0.950570],
      [116.713060, -0.951280], [116.712300, -0.951280]
    ],
    "terkunci": true,
    "digeoreferensi_oleh": "operator_kpb_412345",
    "digeoreferensi_pada": "2026-07-10T04:02:11Z"
  },

  "status": "aktif", "versi": 1, "versi_denah": 12
}
```

**Contoh RUANGAN (jembatan ke master `ruangan` yang SUDAH ADA):**

```json
{
  "id": "sn_rg_b1_014",
  "kode_satker": "412345",
  "tipe": "RUANGAN", "ordinal_level": 100,
  "parent_id": "sn_lt_b1_gd_a",
  "ancestors": ["…", "sn_9f3c1a7e-…", "sn_lt_b1_gd_a"],
  "jalur": ",…,sn_9f3c1a7e-…,sn_lt_b1_gd_a,",
  "kode": "R-B1-014",
  "nama": "Gudang Arsip B1",
  "ruangan_id": "rgn_7c2b…",
  "lantai_ordinal": -1,
  "geometry": { "type": "MultiPolygon", "coordinates": [[[ /* … */ ]]] },
  "metrik": { "luas_m2": 232.1, "keliling_m": 62.0, "jumlah_verteks": 5, "thinness": 0.758 },
  "properties": { "kategori_imdf": "storage", "kapasitas_orang": 0 },
  "status": "aktif", "versi": 2, "versi_denah": 12
}
```

> **JANGAN duplikasi master.** Koleksi `ruangan` yang ada (`backend/routes/ruangan.py`, unik `kode_ruangan` **per satker** — sudah benar) tetap pemilik atribut administratif (Penanggung Jawab Ruangan, unit kerja, KIR/DBR). `spasial_node` hanya menambah **geometri** dan menautkan lewat `ruangan_id`; sebaliknya dokumen `ruangan` mendapat `spasial_node_id`. Ini menghindari perombakan `ruangan_utils.py` / KIR / DBR yang sudah teruji.

### 2.3 `spasial_riwayat` — versioning append-only

```json
{
  "id": "hist_01J…",
  "node_id": "sn_9f3c1a7e-…",
  "kode_satker": "412345",
  "versi": 2,
  "versi_denah": 11,
  "aksi": "ubah_geometri",
  "berlaku_dari": "2026-06-02T08:14:00Z",
  "berlaku_sampai": "2026-07-26T02:11:04Z",
  "geometry": { "type": "MultiPolygon", "coordinates": [ "…geometri LAMA…" ] },
  "geometry_hash": "sha1:3f2a…",
  "ubah_atribut": [{ "field": "nama", "dari": "Gedung A", "ke": "Gedung Kantor Kementerian A" }],
  "parent_id_lama": "sn_tapak_kemenkeu",
  "alasan": "Penyesuaian as-built hasil pengukuran BPN, BA-014/2026",
  "sumber": "gambar_manual",
  "oleh": "operator_kpb_412345", "pada": "2026-07-26T02:11:04Z"
}
```

**Aturan hemat ruang:**
1. Snapshot geometri **hanya** ditulis bila geometri benar-benar berubah (bandingkan `sha1` koordinat yang sudah dibulatkan). Ubah nama → cukup `ubah_atribut`, tanpa salinan geometri.
2. **Simpan versi LAMA** (closing record). Kondisi terkini selalu di koleksi utama → "ambil denah hari ini" tidak menyentuh riwayat sama sekali.
3. "Kondisi per tanggal T": `find({node_id: X, berlaku_dari: {$lte: T}, berlaku_sampai: {$gt: T}})`; kosong → pakai dokumen aktif.
4. **JANGAN** menyematkan array `riwayat[]` di dokumen utama — poligon WP 20.000 verteks × 30 revisi = >10 MB, mendekati batas 16 MB dan memperlambat SETIAP pembacaan.
5. **Tanpa TTL** — riwayat = bukti audit BMN. Kompresi: geometri riwayat pada presisi 6 desimal + `zlib` sebagai `BinData` bila > 200 KB.

### 2.4 `asset_custody` — kustodian temporal (append-only)

```json
{
  "id": "cus_…", "kode_satker": "412345", "asset_id": "ast_…",
  "lapisan": "pokok",
  "jenis": "jabatan",
  "subjek": {
    "nip": null, "jabatan_kode": "JAB-KASUBBAG-TU",
    "unit_kerja_kode": null, "ruangan_id": null, "pool_kode": null
  },
  "pemangku_snapshot": { "nip": "1985…", "nama": "Budi Santoso", "sejak": "2026-01-02T00:00:00Z" },
  "mulai": "2025-08-01T00:00:00Z", "selesai": null,
  "jatuh_tempo": null,
  "dasar": {
    "tipe": "bast", "bast_id": "bst_…", "nomor": "BA-014/PL.02/2025",
    "tanggal": "2025-08-01", "ttd_status": "ditandatangani"
  },
  "lokasi_kustodi": { "spasial_node_id": "sn_rg_b1_014", "ruangan_id": "rgn_7c2b…" },
  "alasan_koreksi": "",
  "created_at": "2025-08-01T03:00:00Z", "created_by": "operator_kpb_412345"
}
```

**Aturan bisnis:**
1. **Tepat satu** custody `pokok` aktif per aset; **nol atau satu** `overlay` (pinjam pakai) aktif. Lokasi efektif = overlay bila ada, jika tidak = pokok.
2. Semua perubahan wajib punya `dasar`. Tanpa BAST → memicu temuan Wasdal `pemegang_tanpa_bast` yang **sudah ada** di `wasdal_utils.py`.
3. **`jenis="jabatan"` tidak berubah saat pejabat berganti** — job sertijab hanya memperbarui `pemangku_snapshot`, **tanpa BAST aset baru**. Ini menjawab langsung permintaan pemilik "aset melekat ke jabatan".
4. Pegawai pensiun/mutasi/meninggal (`STATUS_PEGAWAI` di `pegawai_utils.py`) → semua custody `individu` masuk daftar "wajib serah terima".
5. **Append-only**: koreksi dengan entri baru `tipe="koreksi_administratif"` + alasan wajib — **tidak pernah** menghapus baris.
6. Cache di dokumen aset: `assets.custody_current = {jenis, nip, nama, jabatan_kode, ruangan_id, custody_id, sejak, overlay}` — untuk daftar/DBR cepat, **bukan** sumber kebenaran.

### 2.5 Koleksi IoT

**`iot_devices`** (registry perangkat):

```json
{
  "id": "dev_7f3a…", "kode_satker": "412345",
  "jenis": "tracker_gps",
  "identitas": {
    "imei": ["350000000000006"], "imei_terverifikasi_luhn": true, "tac": "35000000",
    "serial_number": "TLT-9932", "mac_wifi": null, "mac_bt": null,
    "traccar_unique_id": "860123456789012", "iccid": "8962…", "msisdn": "6281…"
  },
  "asset_id": "ast_tracker_01",
  "melekat_pada": [{ "asset_id": "ast_mobil_dinas_03", "mulai": "2026-03-01T00:00:00Z", "selesai": null }],
  "pemegang": { "nip": null, "nama": null, "jabatan_kode": null },
  "status": "aktif",
  "kredensial": {
    "token_hash": "$2b$12$…", "hmac_secret_enc": "gAAAAAB…",
    "kid": "k2", "kid_lama": "k1", "kid_lama_berlaku_sampai": "2026-08-25T00:00:00Z",
    "dibuat": "2026-02-25T00:00:00Z", "rotasi_berikutnya": "2026-08-24T00:00:00Z"
  },
  "kebijakan": {
    "profil_privasi": "kendaraan",
    "presisi_maks": "penuh",
    "jam_aktif": null,
    "interval_detik": 300, "interval_gerak_detik": 30
  },
  "kesehatan": { "terakhir_terdengar": "2026-07-26T03:10:00Z", "baterai_persen": 78,
                 "clock_skew_ms": -1240, "fw": "1.4.2" },
  "created_at": "2026-02-25T00:00:00Z", "updated_at": "2026-07-26T03:10:00Z"
}
```

**`iot_observasi`** (time-series, TTL 90 hari):

```json
{
  "ts_server": "2026-07-26T03:10:00Z",
  "meta": { "device_id": "dev_7f3a…", "asset_id": "ast_mobil_dinas_03",
            "kode_satker": "412345", "sumber": "gps" },
  "obs_id": "sha1:9c1d…",
  "ts_device": "2026-07-26T03:09:58Z",
  "geo": { "type": "Point", "coordinates": [116.712679, -0.950922] },
  "akurasi_m": 6.5, "hdop": 0.9, "kecepatan_kmh": 32.4, "arah_deg": 187,
  "baterai_persen": 78, "kualitas": "baik",
  "flags": { "ts_ragu": false, "ts_dikoreksi": false, "outlier": false, "retro": false },
  "lokasi_spasial": { "gedung_id": null, "blok_id": "sn_blok_a3", "ancestors": ["sn_ikn","sn_kikn","sn_wp1","sn_swp1a","sn_blok_a3"] },
  "schema_v": 1
}
```

**`iot_posisi_terakhir`** (koleksi biasa, 1 dok/perangkat, di-`upsert`): field sama + `diperbarui`, **plus indeks `2dsphere`** (time-series tidak mendukung `$near`).

**`iot_geofence_state`**, **`iot_dead_letter`**, **`iot_batch_receipts`** (TTL 24 jam), **`iot_rekap_harian`** (permanen).

**`ruangan_wifi_map`** (sidik jari BSSID → ruangan, untuk pelacakan laptop):
```json
{ "id": "wf_…", "kode_satker": "412345", "spasial_node_id": "sn_rg_b1_014",
  "bssid": "a4:2b:8c:11:22:33", "rssi_rata": -58, "sampel": 14,
  "disurvei_pada": "2026-06-10T02:00:00Z" }
```

### 2.6 Perubahan pada koleksi yang sudah ada

| Koleksi | Tambahan | Catatan |
|---|---|---|
| `assets` | `geo` (GeoJSON Point, **turunan** dari `koordinat_latitude/longitude` string) · `lokasi_spasial{}` (denormalisasi hasil deteksi) · `custody_current{}` | ⚠️ **[V]** `backend/asset_fields.py:73-74` menyimpan koordinat sebagai **string** dan `models.py:110-111` `Optional[str]` — **string tidak bisa diindeks 2dsphere**. Field string **dipertahankan** (kompatibilitas ekspor/impor/template), `geo` menjadi turunan |
| `ruangan` | `spasial_node_id` · `gedung_id` · `lantai_id` · `lantai_ordinal` | `gedung: str` / `lantai: str` **dipertahankan** sebagai string tampilan terdenormalisasi → backward-compat penuh dengan KIR/DBR & tes yang ada |

**`lokasi_spasial` pada aset/wasdal (denormalisasi — ini yang membuat agregasi murah):**
```json
"lokasi_spasial": {
  "kawasan_id": "sn_kikn", "wp_id": "sn_wp1", "swp_id": "sn_swp1a",
  "blok_id": "sn_blok_a3", "tapak_id": "sn_tapak_kemenkeu",
  "gedung_id": "sn_9f3c1a7e-…", "lantai_id": "sn_lt_b1_gd_a", "lantai_ordinal": -1,
  "ruangan_node_id": "sn_rg_b1_014", "ruangan_id": "rgn_7c2b…",
  "ancestors": ["sn_ikn","sn_kikn","sn_wp1","sn_swp1a","sn_blok_a3","sn_tapak_kemenkeu","sn_9f3c1a7e-…","sn_lt_b1_gd_a"],
  "label": "KIKN › WP 1 › SWP 1-A › Blok A.3 › Kompleks Kemenkeu › Gedung A › B1 › R-B1-014",
  "ditetapkan": "otomatis", "akurasi_m": 6.5,
  "versi_denah": 12, "diselesaikan_pada": "2026-07-26T03:12:00Z"
}
```
→ Agregasi aset per level menjadi `$match {"lokasi_spasial.ancestors": "<node_id>"}` + `$group`. **Tanpa kueri geo, tanpa `$graphLookup`, tanpa join.**

---

## BAGIAN 3 — INDEKS

Semua ditambahkan ke `backend/indexes.py` di dalam `create_indexes()`, dibungkus `try/except` dengan fallback non-unik (pola `indexes.py:29-33`).

```python
# ── spasial_node ────────────────────────────────────────────────────────────
await db.spasial_node.create_index("id", unique=True, name="spasial_node_id")

# INTI: deteksi otomatis titik → rantai level.
# CATATAN: 2dsphere SELALU sparse — node tanpa geometry (draft) TIDAK masuk
# indeks. Itu memang diinginkan; pencarian draft memakai indeks non-geo.
await db.spasial_node.create_index([("geometry", "2dsphere")], name="spasial_geometry_2dsphere")

await db.spasial_node.create_index(
    [("kode_satker", 1), ("ordinal_level", 1), ("status", 1)], name="spasial_satker_level_status")

# Keunikan kode PER SATKER PER TIPE (bukan global) — konvensi REVIEW-9 R9.
await db.spasial_node.create_index(
    [("kode_satker", 1), ("tipe", 1), ("kode", 1)], unique=True,
    partialFilterExpression={"status": {"$in": ["aktif", "draft"]}},
    name="spasial_unik_kode_per_satker_tipe")

await db.spasial_node.create_index([("parent_id", 1), ("ordinal_level", 1)], name="spasial_parent_level")
await db.spasial_node.create_index([("parent_id", 1), ("lantai.ordinal", 1)], name="spasial_parent_ordinal_lantai")
await db.spasial_node.create_index("ancestors", name="spasial_ancestors")       # multikey → subtree 1 hop
await db.spasial_node.create_index("jalur", name="spasial_jalur")               # breadcrumb & prefix ^,A,B,
await db.spasial_node.create_index([("kode_satker", 1), ("updated_at", -1)], name="spasial_satker_updated")
await db.spasial_node.create_index("ruangan_id", sparse=True, name="spasial_ruangan_id")
await db.spasial_node.create_index(
    [("kode_satker", 1), ("validasi.status", 1)],
    partialFilterExpression={"validasi.status": {"$in": ["peringatan", "galat"]}},
    name="spasial_validasi_bermasalah")
await db.spasial_node.create_index([("nama", "text"), ("kode", "text"), ("nama_alias", "text")],
                                   name="spasial_text")

# ── spasial_level ───────────────────────────────────────────────────────────
await db.spasial_level.create_index([("kode_satker", 1), ("ordinal_level", 1)], unique=True)
await db.spasial_level.create_index([("kode_satker", 1), ("kode_baku", 1)], unique=True)

# ── spasial_riwayat ─────────────────────────────────────────────────────────
await db.spasial_riwayat.create_index([("node_id", 1), ("versi", -1)], unique=True)
await db.spasial_riwayat.create_index([("node_id", 1), ("berlaku_dari", -1)])
await db.spasial_riwayat.create_index([("kode_satker", 1), ("pada", -1)])

# ── assets (tambahan) ───────────────────────────────────────────────────────
await db.assets.create_index([("geo", "2dsphere")], name="assets_geo_2dsphere")
await db.assets.create_index("lokasi_spasial.ancestors", name="assets_lokasi_ancestors")
await db.assets.create_index([("activity_id", 1), ("lokasi_spasial.ruangan_node_id", 1)],
                             name="assets_activity_ruangan_node")

# ── asset_custody ───────────────────────────────────────────────────────────
await db.asset_custody.create_index("id", unique=True)
await db.asset_custody.create_index([("asset_id", 1), ("lapisan", 1), ("selesai", 1)])
await db.asset_custody.create_index([("asset_id", 1), ("mulai", -1)])
await db.asset_custody.create_index([("subjek.nip", 1), ("selesai", 1)])
await db.asset_custody.create_index([("subjek.jabatan_kode", 1), ("selesai", 1)])
await db.asset_custody.create_index([("kode_satker", 1), ("jatuh_tempo", 1)])
await db.asset_custody.create_index([("asset_id", 1), ("lapisan", 1)], unique=True,
                                    partialFilterExpression={"selesai": None},
                                    name="custody_aktif_tunggal")

# ── iot_devices ─────────────────────────────────────────────────────────────
await db.iot_devices.create_index("id", unique=True)
await db.iot_devices.create_index("identitas.imei", sparse=True)
await db.iot_devices.create_index("identitas.traccar_unique_id", sparse=True)
await db.iot_devices.create_index([("kode_satker", 1), ("status", 1)])
await db.iot_devices.create_index([("kode_satker", 1), ("kesehatan.terakhir_terdengar", -1)])

# ── iot_posisi_terakhir ─────────────────────────────────────────────────────
await db.iot_posisi_terakhir.create_index("device_id", unique=True)
await db.iot_posisi_terakhir.create_index("asset_id")
await db.iot_posisi_terakhir.create_index([("geo", "2dsphere")], name="posisi_geo_2dsphere")
await db.iot_posisi_terakhir.create_index([("kode_satker", 1), ("diperbarui", -1)])

# ── iot_observasi (TIME-SERIES — dibuat via create_collection) ───────────────
# await db.create_collection("iot_observasi", timeseries={
#     "timeField": "ts_server", "metaField": "meta", "granularity": "seconds"},
#     expireAfterSeconds=7776000)                       # 90 hari
await db.iot_observasi.create_index([("meta.device_id", 1), ("ts_server", -1)])
await db.iot_observasi.create_index([("meta.asset_id", 1), ("ts_server", -1)])
await db.iot_observasi.create_index([("meta.kode_satker", 1), ("ts_server", -1)])

# ── iot_dead_letter / batch_receipts / geofence_state ───────────────────────
await db.iot_dead_letter.create_index([("kode_satker", 1), ("pada", -1)])
await db.iot_batch_receipts.create_index("created_at", expireAfterSeconds=86400)
await db.iot_batch_receipts.create_index([("device_id", 1), ("idem_key", 1)], unique=True)
await db.iot_geofence_state.create_index([("device_id", 1), ("area_id", 1)], unique=True)
```

**Catatan indeks compound-geo:** MongoDB mengizinkan `{"kode_satker":1, "ordinal_level":1, "geometry":"2dsphere"}` dan tidak mewajibkan field geo di posisi pertama. **TETAPI** super-admin (`kode_satker == ""`) tidak mengirim filter satker → tidak bisa memakai indeks itu. **Mulai dengan 2dsphere polos**; tambahkan compound hanya bila `.explain("executionStats")` menunjukkan `keysExamined >> nReturned`.

### 3.1 Registrasi backup — WAJIB, jangan terlewat

**[V]** `backend/backup_utils.py:38-53` — `RESET_KEEP_COLLECTIONS` sudah memuat `unit_kerja`, `pegawai`, `pejabat`, `ruangan`. Denah kawasan adalah **master referensi sekelas itu**, disusun payah-payah lewat survei & impor SHP.

```python
RESET_KEEP_COLLECTIONS = {
    …,
    # Master denah spasial berlapis — hasil survei/impor SHP, sekelas `ruangan`.
    "spasial_level", "spasial_node", "spasial_riwayat", "ruangan_wifi_map",
}
SKIP_COLLECTIONS = { …, "iot_batch_receipts", "iot_geofence_state" }   # transien
```
Berkas SHP/KMZ sumber & gambar denah di GridFS → tandai `metadata.jenis = "denah_sumber" | "denah_gambar"` dan daftarkan di `RESET_KEEP_GRIDFS_JENIS`.

> ⚠️ `iot_observasi` adalah **time-series = writable non-materialized view**; batasan view berlaku. Verifikasi perilakunya di `backup_utils.collections_to_process()` (enumerasi dinamis) sebelum rilis — bila bermasalah, masukkan ke `SKIP_COLLECTIONS` dan andalkan `iot_rekap_harian` untuk arsip.

---

## BAGIAN 4 — ALGORITMA VALIDASI TOPOLOGI

### 4.1 Fondasi: proyeksi ENU lokal (semua ambang dalam METER)

Shapely bekerja di bidang kartesian; menghitung luas langsung pada derajat = salah. Alih-alih menarik pyproj (+33 MB), pakai ekuirektangular lokal — error **< 0,2% untuk extent < 20 km**, jauh di bawah ketidakpastian digitasi.

```python
import math
M_PER_DEG_LAT = 110574.6      # φ ≈ −0,95° (IKN)

def proyektor(lat0: float, lon0: float):
    k_lon = 111412.84 * math.cos(math.radians(lat0)) - 93.5 * math.cos(math.radians(3 * lat0))
    maju  = lambda lon, lat: ((lon - lon0) * k_lon, (lat - lat0) * M_PER_DEG_LAT)
    balik = lambda x, y:     (lon0 + x / k_lon,     lat0 + y / M_PER_DEG_LAT)
    return maju, balik
```
**Satu proyektor per operasi validasi, berpusat pada centroid INDUK** (bukan tiap anak) agar semua sibling berada di bidang datar yang sama.

### 4.2 Sesama level (antar sibling)

```python
def periksa_sibling(anak_m):                     # {id: geometri_shapely_meter}
    temuan, ids = [], list(anak_m)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = anak_m[ids[i]], anak_m[ids[j]]
            if not a.envelope.intersects(b.envelope):     # pra-saring bbox: O(n²) jadi murah
                continue
            inter = a.intersection(b)
            if inter.is_empty:
                continue
            luas  = inter.area
            rasio = luas / min(a.area, b.area)
            thin  = 4 * math.pi * luas / (inter.length ** 2) if inter.length else 0.0
            temuan.append(klasifikasi(ids[i], ids[j], luas, rasio, thin))
    return temuan
```

**AMBANG (default; dapat di-override per level di `spasial_level`):**

| Kondisi | Tingkat | Aksi UI |
|---|---|---|
| `rasio < 0,005` **DAN** `luas < AMBANG_SLIVER_M2` **DAN** `thinness < 0,30` | **senyap** | auto-snap, tidak ditampilkan |
| `0,005 ≤ rasio < 0,02` | **peringatan** | "Berimpit 1,1% (51 m²)…" + **[Rapikan otomatis]** |
| `0,02 ≤ rasio < 0,90` | **peringatan keras** | wajib pilih **[Perbaiki]** / **[Tumpang tindih ini disengaja]** (+ alasan) |
| `rasio ≥ 0,90` | **galat** | "≥90% berimpit — kemungkinan impor ganda." + **[Tetap simpan sebagai revisi]** |
| `rasio ≥ 0,99` **DAN** `\|luas_a − luas_b\| / luas_a < 0,01` | **galat** | tawarkan **[Gabungkan]** |

`AMBANG_SLIVER_M2`: kawasan 500 · WP 500 · SWP 200 · blok 50 · tapak 20 · gedung 5 · lantai 2 · **ruangan 0,5**.

**Thinness ratio [F]:** `T = 4π·A / P²`, maksimum 1 untuk lingkaran; nilai < 0,30 adalah kandidat sliver. **Peringatan:** fitur besar berbentuk tak beraturan bisa ber-T rendah tanpa menjadi sliver → **selalu kombinasikan T dengan ambang LUAS ABSOLUT**, jangan pakai T sendirian.

**Kapan tumpang tindih WAJAR (jangan dianggap galat):** zona fungsi ganda (`boleh_tumpang_tindih_sesama: true` pada level itu) · kanopi/jembatan penghubung antar gedung · basement melebihi footprint · masa transisi denah (bedakan dengan `berlaku_dari`).

**Celah antar sibling:** `celah = induk_m.difference(unary_union(anak))`.
- `luas < AMBANG_SLIVER_M2` **dan** `thinness < 0,30` → celah sliver → tawarkan auto-fill.
- `luas ≥ AMBANG_SLIVER_M2` → **BUKAN galat**, tapi "area belum terklasifikasi" (jalan, taman, koridor). Tampilkan lapisan abu + **[Jadikan fitur baru]**. **Memaksa 100% cakupan adalah pemodelan yang salah untuk kawasan nyata.**

### 4.3 Antar level (anak ⊂ induk)

`rasio_luar = area(anak.difference(induk)) / area(anak)`

| `rasio_luar` | Tingkat | Aksi |
|---|---|---|
| ≤ 0,005 | **lolos** | presisi digitasi murni |
| 0,005 – 0,05 | **peringatan** | **[Potong ke batas induk]** / **[Perlebar induk]** / **[Abaikan]** |
| > 0,05 | **peringatan keras** (bukan penolakan) | sarankan induk lain (irisan terbesar), atau tandai `lintas_induk` |
| ≥ 0,999 | **galat** | "Fitur sepenuhnya di luar induk yang dipilih." |

**PENGECUALIAN WAJIB — `sumbu_z` (GEDUNG → LANTAI):**
Dua lantai punya footprint 2D **hampir sama** dengan gedungnya, dan **basement lazim MELEBIHI** footprint. Karena itu:
- `GEDUNG → LANTAI`: **JANGAN** terapkan containment. Ganti dengan **`IoU(lantai, gedung) ≥ 0,50`** (peringatan bila kurang) + `lantai.ordinal` unik per gedung. Bila `ordinal < 0` dan lantai melebihi footprint → **selalu lolos** (basement).
- `LANTAI → RUANGAN`: containment **ketat** (toleransi 0,5%) — di sinilah presisi benar-benar penting.
- **Inilah alasan teknis mengapa daftar pemilik bukan rantai containment murni: modelnya 2,5D.**

**Anak melintasi 2 induk:**
1. `bagi_luas = {induk_id: area(anak ∩ induk) / area(anak)}`.
2. `parent_id` = kandidat **terbesar** (induk dominan) — dipakai `ancestors`, breadcrumb, dan **seluruh agregasi aset** (agar total tidak dobel-hitung).
3. `parent_sekunder_ids = [id lain dengan bagi ≥ 0,05]`.
4. Bila dominan < 0,60 → peringatan "Fitur ini terbagi 55%/45% antara SWP 1-A dan 1-B. Pilih induk utama untuk pelaporan." — **user yang memutuskan**.
5. Tawarkan **[Pecah otomatis]**; jangan pernah memecah diam-diam.

### 4.4 Perbaikan otomatis

```python
from shapely import make_valid, set_precision, unary_union
from shapely.ops import snap

TOL_SNAP_M = {"KAWASAN":1.0,"WP":1.0,"SWP":1.0,"BLOK":0.50,"TAPAK":0.50,
              "GEDUNG":0.25,"LANTAI":0.10,"RUANGAN":0.05}

def rapikan(geom_m, tipe, tetangga_m=None):
    g = geom_m if geom_m.is_valid else make_valid(geom_m)
    tol = TOL_SNAP_M[tipe]
    g = set_precision(g, tol / 10.0)                 # grid snapping: hapus verteks kembar
    if tetangga_m is not None:
        g = snap(g, tetangga_m, tol)
    if g.geom_type == "GeometryCollection":
        polys = [p for p in g.geoms if p.geom_type in ("Polygon", "MultiPolygon")]
        g = unary_union(polys) if polys else g
    if g.geom_type == "MultiPolygon":
        amb = AMBANG_SLIVER_M2[tipe]
        besar = [p for p in g.geoms if p.area >= amb]
        g = unary_union(besar) if besar else max(g.geoms, key=lambda p: p.area)
    return g
```

> ### ⚠️ TIGA JEBAKAN YANG SEMUANYA GAGAL SENYAP
>
> **1. `buffer(0)` alih-alih `make_valid` — SEPARUH POLIGON HILANG TANPA ERROR. [V]**
> Diuji pada poligon dasi-kupu berluas benar 0,5: `make_valid()` → 0,5 ✓ · `buffer(0)` → **0,25 ✗**. Pada denah ruangan ini berarti kehilangan setengah ruangan tanpa satu pun peringatan. `buffer(0)` adalah trik era Shapely 1.x yang masih beredar di tutorial lama. **Dilarang di repo ini.**
> **Selalu bandingkan `luas_sebelum` vs `luas_sesudah`; selisih > 1% → jangan auto-apply, tampilkan ke user.**
>
> **2. `Transformer` tanpa `always_xy=True` — LON/LAT TERTUKAR TANPA ERROR. [V]**
> EPSG:4326 secara resmi lat,lon; PROJ ≥6 mematuhinya; GeoJSON & MongoDB menuntut lon,lat. Kesalahan ini menempatkan seluruh IKN di Samudra Hindia dan tidak memicu apa pun. **Jadikan aturan lint.**
>
> **3. Encoding DBF salah — NAMA RUANGAN RUSAK TANPA ERROR. [V]**
> Dengan `encodingErrors="replace"`: `"Zona Inti Café"` → `"Zona Inti Caf<?>"`, tanpa exception. Hanya `.cpg` yang menyelamatkan. Tambahkan heuristik mojibake (`�`, `Ã©`, `Ã¡`) dan tampilkan pratinjau sebelum simpan.

**Jebakan keempat — `simplify()` bisa menghasilkan geometri invalid** (bug aktif shapely #1795, #2165 pada poligon berlubang). Selalu bungkus:
```python
def sederhanakan_aman(geom_m, tol_m):
    t = tol_m
    for _ in range(4):
        g = simplify(geom_m, t, preserve_topology=True)
        if g.is_valid and not g.is_empty:
            return g
        t /= 2.0
    return make_valid(geom_m)
```

### 4.5 Pagar keras — HANYA DUA yang benar-benar memblokir

**Prinsip: JANGAN memblokir keras data dunia nyata.** Denah nyata memang tumpang tindih dan tidak rapi. Aplikasi yang menolak menyimpan akan membuat operator menyerah dan kembali ke Excel.

Yang **memblokir**:
1. Geometri yang tidak bisa diindeks 2dsphere sama sekali — ring tidak tertutup, < 4 titik, koordinat di luar rentang, interior ring beririsan. MongoDB akan menolak `insert`-nya.
2. **Luas > 5.000 km²** → tolak dengan pesan **"kemungkinan lon/lat tertukar"**. Ini juga mencegah terpicunya perilaku "big polygon" MongoDB (poligon ≥ hemisfer dikueri sebagai komplemennya, diam-diam).

Selain itu: **selalu bisa disimpan**, dengan `status: "perlu_perbaikan"` bila perlu.

**Pagar aplikasi tambahan:** peringatan > 5.000 verteks/fitur; **tolak** > 50.000 verteks/fitur ("sederhanakan dulu di QGIS"). Batas 16 MB dokumen (~650.000 verteks) praktis tak tersentuh — yang menggigit adalah entri indeks S2 dan payload HTTP.

### 4.6 Pelaporan yang manusiawi — tiga tingkat

| Tingkat | Warna | Perilaku simpan | Contoh pesan |
|---|---|---|---|
| `info` | biru | selalu simpan | "Ada 3 area (total 1.240 m²) di dalam Blok A.3 yang belum diberi nama." |
| `peringatan` | kuning | **tetap simpan**, badge di daftar | "Gedung A berimpit 1,1% (51 m²) dengan Gedung B. Biasanya ini garis batas yang belum rapat." + **[Rapikan otomatis]** |
| `galat` | merah | simpan `status="perlu_perbaikan"` + konfirmasi 1 klik | "Poligon ini memotong dirinya sendiri sehingga luasnya tidak dapat dihitung." + **[Perbaiki otomatis]** |

Setiap temuan **wajib** memuat: **angka** (m² dan %), **nama lawan** (bukan UUID), **satu tombol aksi**, dan **[Sorot di peta]** yang men-zoom ke geometri irisan. Validasi impor massal dijalankan **asinkron** lewat `backend/jobs.py` — jangan blokir request impor 5.000 fitur menunggu O(n²).

---

## BAGIAN 5 — ENDPOINT API

Semua di bawah `api_router` (`prefix="/api"`, `server.py:39`). Router baru: `routes/spasial.py`, `routes/spasial_impor.py`, `routes/iot.py`.

### 5.1 Master & pohon

| Method | Path | Gate | Keterangan |
|---|---|---|---|
| GET | `/spasial/level` | `require_user` | Registry level + preset penamaan aktif |
| PUT | `/spasial/level/{kode_baku}` | `require_super_admin` | Ubah label/ambang/warna |
| GET | `/spasial/node` | `require_user` | `?tipe=&parent_id=&q=&status=` — **tanpa** geometry |
| GET | `/spasial/node/{id}` | `require_user` | Detail + geometry + breadcrumb |
| GET | `/spasial/node/{id}/anak` | `require_user` | Anak langsung (pemuatan bertahap pohon) |
| GET | `/spasial/node/{id}/subtree` | `require_user` | `{"ancestors": id}` — 1 kueri |
| POST | `/spasial/node` | `require_writer` | Buat; validasi level & induk; `Idempotency-Key` |
| PATCH | `/spasial/node/{id}` | `require_writer` | `If-Match` (OCC); geometri berubah → tulis `spasial_riwayat` |
| POST | `/spasial/node/{id}/pindah` | `require_admin` | Ganti `parent_id` → job backfill `ancestors`/`jalur` subtree |
| DELETE | `/spasial/node/{id}` | `require_admin` | Tolak bila punya anak atau dirujuk aset |
| GET | `/spasial/node/{id}/riwayat` | `require_user` | Timeline versi |
| GET | `/spasial/node/{id}/pada?tanggal=` | `require_user` | Kondisi bitemporal |
| GET | `/spasial/opsi-bertingkat` | `require_user` | Dropdown kaskade (pola `unit_kerja_utils.opsi_bertingkat`) |

### 5.2 Peta & render

| Method | Path | Keterangan |
|---|---|---|
| GET | `/spasial/geojson?bbox=&level_maks=&induk=` | FeatureCollection per-viewport + LOD. > 3.000 fitur → `{terpotong:true, jumlah_total:N}` + hanya bbox/titik_wakil. **Terpasang Fase 3** — dengan dua penyimpangan dari rencana ini: (a) `z`/`geometry_ringkas` TIDAK dipakai; LOD dikerjakan lewat `level_maks` per zoom (tingkat detail dibuang seluruhnya, bukan disederhanakan bentuknya) karena penyederhanaan geometri butuh shapely di jalur panas — dievaluasi ulang bila poligon nyata ternyata berat; (b) ditambah `induk=<node_id>` untuk memuat anak langsung satu node — dibutuhkan agar ruangan SATU lantai bisa dirender tanpa menumpuk seluruh lantai gedung (semua lantai berbagi jejak 2D yang sama) |
| GET | `/spasial/lantai/{gedung_id}` | Daftar lantai terurut `ordinal` (untuk level switcher) |
| GET | `/spasial/denah/{lantai_id}/gambar` | Stream gambar denah dari GridFS · `require_user_or_query_token` + `pastikan_akses_dok_satker` |
| PUT | `/spasial/denah/{lantai_id}/georef` | Simpan `sudut_bumi` (4 sudut) + opasitas + kunci |
| GET | `/spasial/publik/geojson?token=` | Layer read-only untuk Peta Kolaborasi · `require_map_token` |

### 5.3 Deteksi otomatis lokasi (inti permintaan pemilik #5)

| Method | Path | Keterangan |
|---|---|---|
| POST | `/spasial/lokasi-di-titik` | `{lon, lat, akurasi_m}` → **SATU** `$geoIntersects` (`ordinal_level ≤ 80`), sort ASC → rantai lengkap + daftar lantai gedung terdalam + `perlu_pilih_lantai` |
| GET | `/spasial/ruangan-di-titik?lon=&lat=&lantai_id=` | `{parent_id: lantai_id, geometry: {$geoIntersects: Point}}` → ruangan |
| POST | `/spasial/resolusi-massal` | Untuk job re-resolusi (daftar titik → daftar `lokasi_spasial`) |

**Kueri kunci (alasan utama koleksi polimorfik):**
```python
titik = {"type": "Point", "coordinates": [lon, lat]}      # lon DULU
q = scope_query_field_satker(user, {
    "status": "aktif",
    "ordinal_level": {"$lte": 80},                        # ruangan butuh lantai dulu
    "geometry": {"$geoIntersects": {"$geometry": titik}},
})
rantai = await db.spasial_node.find(
    q, {"_id": 0, "id": 1, "tipe": 1, "ordinal_level": 1, "nama": 1,
        "kode": 1, "parent_id": 1, "ancestors": 1, "jalur": 1}   # geometry TIDAK diproyeksikan
).sort("ordinal_level", 1).to_list(50)
```
**Target SLA:** < 5 ms di VPS kecil untuk skala IKN (< 15.000 node ber-geometri di level ≤ gedung), syarat: (1) `geometry` tidak diproyeksikan, (2) verteks < 5.000/fitur. **Wajib verifikasi** `.explain("executionStats")` → `IXSCAN`, bukan `COLLSCAN`.

**Kasus tepi deteksi:**

| Kasus | Perilaku |
|---|---|
| Titik di luar SEMUA poligon | `$near` `maxDistance:500` → "Di luar kawasan terpetakan. Terdekat: **Gedung A (42 m)**." **[Pakai Gedung A]** / **[Simpan sebagai luar kawasan]**. **JANGAN blokir** — aset di lapangan terbuka itu nyata |
| Titik di 2+ poligon sesama level | Kembalikan semua; urutkan `prioritas` DESC → **luas terkecil** (paling spesifik) → jarak ke `titik_wakil`. Preselect #1, tampilkan dropdown |
| Rantai tidak konsisten (gedung terdeteksi, kawasan tidak) | **Percayai fitur TERDALAM**, isi level di atasnya dari `ancestors`-nya, bukan dari hasil geo. Catat `catatan:"rantai_dilengkapi_dari_ancestors"` → hasil selalu konsisten dengan pohon |
| Akurasi GPS buruk (> 30 m) | Tetap deteksi + badge kuning "Akurasi GPS ±45 m"; **jangan** auto-commit ruangan |
| Titik di koridor (0 ruangan) | Bukan galat. "Titik berada di area sirkulasi Lantai B1." + daftar ruangan lantai itu + `$near` `maxDistance:15` |
| Denah berubah setelah aset dicatat | `versi_denah` aset < `versi_denah` satker → temuan Wasdal `lokasi_spasial_basi` + job re-resolusi |
| Gedung 1 lantai saja | Server langsung mengembalikan ruangan tanpa menunggu pilihan lantai |
| Operator inventarisasi satu lantai seharian | Klien mengirim `lantai_terakhir_dipakai` (dari `localStorage`) sebagai tebakan → tidak perlu memilih 200 kali |

### 5.4 Impor / ekspor

| Method | Path | Gate | Keterangan |
|---|---|---|---|
| POST | `/spasial/impor` | `require_writer` | Unggah ZIP/SHP/KML/KMZ/GeoJSON/GPKG → simpan mentah ke **GridFS** → `buat_job("impor_spasial", kode_satker=…)` → **202** + `job_id` |
| GET | `/spasial/impor/{job_id}/pratinjau` | `require_user` | GeoJSON hasil parse + **laporan galat** + CRS terdeteksi. **Belum tersimpan** |
| POST | `/spasial/impor/{job_id}/konfirmasi` | `require_writer` | `{crs_dikonfirmasi, pemetaan_kolom, tipe_target, parent_id, tindakan_per_fitur}` → simpan |
| DELETE | `/spasial/impor/{job_id}` | `require_writer` | Batalkan |
| GET | `/spasial/ekspor?format=geojson\|kml\|kmz\|shp\|gpkg&tipe=&parent_id=` | `require_user_or_query_token` | `@limiter.limit("10/minute")`; besar → job |
| GET | `/spasial/template?target=qgis\|google_earth` | `require_user` | Unduh paket template |

### 5.5 IoT

| Method | Path | Auth | Keterangan |
|---|---|---|---|
| POST | `/iot/ingest` | Token perangkat + HMAC | Batch ≤ 500 observasi; **202 Accepted** |
| POST | `/iot/traccar-webhook` | Bearer gateway | Adapter format `Position` Traccar |
| POST | `/iot/heartbeat` | Token perangkat | Keep-alive murah tanpa posisi |
| POST | `/iot/scan` | `require_user` (JWT pegawai) | Scan QR/stiker sebagai observasi `kepercayaan=0.99` |
| GET | `/iot/devices/{id}/config` | Token perangkat | Pull konfigurasi: interval, presisi, jam aktif |
| GET/POST/PATCH | `/iot/devices` | `require_admin` | Registry CRUD + rotasi kredensial |
| GET | `/iot/posisi?bbox=` | `require_user` | Posisi terakhir (sudah didegradasi presisinya) |
| GET | `/iot/lintasan/{asset_id}?dari=&sampai=` | `require_user` + **alasan wajib** | Riwayat; dicatat di `audit_logs` |
| POST | `/iot/darurat/{asset_id}` | `require_admin` × 2 (dual approval) | Mode break-glass 24 jam |
| POST | `/iot/dlq/{id}/replay` | `require_super_admin` | Replay idempoten |
| WS | `/ws/iot` | JWT | Fanout live — **reuse `event_bus.py`** |

**Header ingest:** `X-Device-Id`, `X-Kid`, `X-Timestamp`, `X-Nonce`, `X-Signature` (HMAC-SHA256 atas `body + timestamp + nonce`), toleransi ±5 menit, nonce TTL 10 menit.

---

## BAGIAN 6 — ALUR IMPOR & EKSPOR

### 6.1 Tumpukan pustaka final

| Paket | Versi | Lisensi | Wheel | Terpasang | RSS import | Status |
|---|---|---|---|---|---|---|
| `pyshp` | 3.1.4 → **3.1.6** | MIT | 72 KB | < 1 MB | +1 MB | **[V] sudah ada** |
| `shapely` | **2.1.2** | BSD-3 | 2,96 MB | 13 MB | **+22 MB** | **TAMBAH** (lazy-import) |
| `utm` | **0.8.1** | MIT | ~10 KB | **27 KB** | ~0 | **TAMBAH** |
| `lxml` | 6.1.1 | BSD-3 | 4,86 MB | 12 MB | +9 MB | **[V] sudah ada** |
| `numpy` | 2.4.2 | BSD | — | — | — | **[V] sudah ada** (prasyarat shapely) |
| ~~`pyproj`~~ | — | — | 9,11 MB | 33 MB | +21 MB | **DITOLAK fase 1–6** |
| ~~`simplekml`/`fastkml`~~ | — | LGPL | — | — | — | **DITOLAK** |

**Total tambahan disk ≈ 13 MB.** Shapely 2.1.2 membawa **GEOS 3.13.1** ter-bundle — tanpa kompilasi, tanpa `libgeos-dev` di VPS. **[V]**

**Alasan MENAMBAH shapely (menolak usulan "pure-Python saja"):** bukti `make_valid` vs `buffer(0)` (§4.4) menentukan — separuh poligon hilang senyap. `make_valid`, `set_precision`, `snap`, `unary_union`, `simplify(preserve_topology)` adalah operasi GEOS yang **tidak realistis** ditulis ulang dengan benar. **Mitigasi VPS kecil: `import shapely` diletakkan DI DALAM fungsi impor/validasi**, bukan di puncak modul — RAM +22 MB hanya dibayar saat ada yang benar-benar mengunggah file, bukan pada setiap request API. Point-in-polygon jalur panas tetap memakai **MongoDB 2dsphere** (server) dan **ray casting pure-Python** (klien offline + `spasial_utils.py` teruji unit).

**Alasan MENOLAK pyproj (33 MB) [O]:** yang sulit bukan matematika proyeksinya, melainkan mengidentifikasi CRS dari `.prj` WKT gaya ESRI. Kami menggantinya dengan **tiga lapis**:
1. Regex atas WKT: pola `UTM zone (\d+)([NS])` + `GEOGCS.*WGS_1984` → mencakup ~95% data Indonesia.
2. Transformasi dengan paket **`utm`** — **[V] selisih maksimum 6 µm** dari PROJ pada 16 titik Kalimantan Timur.
3. **Konfirmasi manusia wajib di layar pratinjau** — poligon dirender di atas basemap Leaflet; CRS salah membuat poligon mendarat di Samudra Hindia dan **terlihat langsung**. Ini pengecekan yang lebih kuat daripada `to_epsg()` diam-diam.

**Pintu keluar terdefinisi:** bila laporan lapangan menunjukkan `.prj` eksotis (TM-3 zona 54.1, grid nasional) yang gagal dikenali > 5% kasus, tambahkan `pyproj` sebagai **dependensi opsional** dengan `try: import pyproj except ImportError` — kode sudah dirancang untuk itu.

**Datum Indonesia — bukan masalah [V]:** diukur di IKN (116,85 BT, 0,95 LS): DGN95 (EPSG:4755) → WGS84 = **0,000 m** (PROJ memakai transformasi null); SRGI2013 (EPSG:9470) → WGS84 = **0,172 m**; bolak-balik UTM 50S ↔ WGS84 = **0,0000 mm**. Untuk penatausahaan BMN, 17 cm tidak relevan. **Catat CRS sumber di metadata; jangan menahan impor karenanya.**

### 6.2 Alur impor (11 langkah)

```
1.  Terima unggahan  → batas 50 MB; sniff tipe dari MAGIC BYTE (bukan ekstensi)
                        → simpan mentah ke GridFS (metadata.jenis="denah_sumber")
                        → buat_job(..., kode_satker=kode_satker_user(user)) → 202
2.  Bongkar          → ZIP? cek rasio dekompresi (tolak >100×) + path traversal (`../`)
                        → abaikan __MACOSX/ dan ._*  (penyebab "shapefile ganda" palsu)
                        → KMZ? ambil doc.kml dari akar zip
3.  Kelompokkan      → cocokkan .shp/.shx/.dbf/.prj/.cpg per BASENAME (bukan jalur)
                        → .shx hilang → pyshp bangun ulang; .dbf hilang → geometri saja + peringatan
                        → baca dari MEMORI: shapefile.Reader(shp=BytesIO(...), shx=..., dbf=...)
4.  Deteksi encoding → .cpg → header LDID DBF → utf-8 → cp1252/latin-1
                        → heuristik mojibake (�, Ã©, Ã¡) → tandai baris, tampilkan pratinjau
5.  Deteksi CRS      → .prj WKT via regex (UTM zone N/S, WGS84 geografis)
                        → KML → PAKSA EPSG:4326 (spesifikasi; tanpa reproyeksi sama sekali)
                        → tanpa .prj → tebak dari rentang: |x|≤180 & |y|≤90 → 4326 (sedang)
                                       1e5≤x≤1e6 & y≈9,8e6 → 327xx UTM selatan (sedang)
                        → keyakinan < tinggi → WAJIB konfirmasi pengguna di pratinjau
6.  Baca fitur       → pyshp (file-like) / lxml XMLParser(recover=True, resolve_entities=False,
                        huge_tree=False)   ← resolve_entities=False WAJIB (anti-XXE)
                        → KML: rekam JALUR FOLDER lengkap per Placemark (= hierarki!)
                        → baca KEDUA bentuk ExtendedData: <Data name=> DAN <SchemaData><SimpleData>
                        → kumpulkan parser.error_log → laporan
                        ⚠ mode recover MEMBUANG `&` telanjang DIAM-DIAM:
                          "R-101 & Lobi" → "R-101  Lobi". Selalu laporkan, jangan telan.
7.  Reproyeksi       → utm (jalur cepat) → lon,lat WGS84
8.  Bersihkan        → force_2d (buang Z; 2dsphere mengabaikannya & membengkakkan dokumen)
                        → make_valid (BUKAN buffer(0))
                        → orient(sign=1.0) (RFC 7946: exterior CCW)
                        → normalisasi SEMUA poligon ke MultiPolygon (make_valid bisa mengubah tipe)
                        → bandingkan luas sebelum/sesudah, tandai selisih > 1%
9.  Validasi         → §4: containment, sibling, sliver, pagar keras (§4.5)
                        → pemetaan kolom → field; induk ada; kode unik per satker
10. Pratinjau        → kembalikan GeoJSON + laporan galat; TAHAN komit
11. Konfirmasi       → simpan (tulis atomik), INCR aman:gen:spasial, naikkan versi_denah,
                        log_audit(), publish event_bus → WebSocket
```

**Winding order & MongoDB — nuansanya penting [F]:** untuk poligon lebih kecil dari hemisfer, MongoDB memperlakukan CRS kustom **identik** dengan CRS bawaan; winding **tidak akan pernah** mengubah hasil kueri untuk zona/gedung/ruangan IKN. **Tetap normalisasi ke RFC 7946** — biayanya satu pemanggilan, dan konsumen lain (Leaflet, pustaka JS, data pihak ketiga) memang peduli.

**Batasan pyshp yang WAJIB diketahui [V]:**
- **`.prj` TIDAK pernah ditulis** oleh `Writer.close()` — harus ditulis sendiri. `_WGS84_PRJ` sudah ada di `exports.py:428-430`.
- **Nama field dipotong ke 10 byte** dengan warning `PossibleDataLoss` yang **bisa ditangkap** — tangkap dengan `warnings.catch_warnings(record=True)` dan tampilkan ke pengguna. **Jangan andalkan pemotongan otomatis saat ekspor** — pakai kamus eksplisit (pola `_SHP_FIELDS` `exports.py:414-426` sudah benar).
- **Kegagalan tulis di tengah jalan meninggalkan shapefile RUSAK** (`records=0` tapi `shapes=1`, lalu `__del__` melempar exception kedua). **Selalu tulis ke file sementara, lalu `os.replace()` atomik hanya setelah berhasil.**
- Batas ukuran: 2 GB per komponen.

### 6.3 Alur ekspor

```
1. Kueri MongoDB (scope satker + level)  → GeoJSON 4326 lon,lat
2. GeoJSON → kirim apa adanya (kanonik)
3. KML/KMZ → bangun dengan xml.etree stdlib (perluas _build_kml exports.py:381
             ke <Polygon><outerBoundaryIs>) + Schema + ExtendedData
             + <Folder> per level + GroundOverlay denah lantai → zip → KMZ
4. SHP     → reproyeksi bila diminta; PETAKAN nama field ≤10 byte dengan KAMUS EKSPLISIT
             (perluas _SHP_FIELDS); tulis .prj SENDIRI; tulis .cpg="UTF-8";
             zip 5 komponen (perluas _build_shp_zip exports.py:433 ke shapefile.POLYGON)
5. GPKG    → sqlite3 stdlib + WKB shapely  [V: .gpkg valid 36 KB dibangun TANPA GDAL,
             application_id 1196444487 = 'GPKG', terbaca kembali dengan benar]
6. SELALU sertakan README.txt di dalam zip: CRS, kamus field, timestamp, satker, versi_denah
```

### 6.4 Paket template baku

**`Template_AMAN_QGIS_v1.zip`** — GeoPackage, **bukan** SHP:

```
template_kawasan.gpkg          # 8 layer kosong ber-skema, EPSG:4326
   ├─ kawasan / wp / swp / blok / tapak / gedung   (MultiPolygon)
   ├─ lantai                                        (MultiPolygon + lantai_ordinal INT)
   └─ ruangan                                       (MultiPolygon + lantai_ordinal INT)
gaya/  kawasan.qml … ruangan.qml     # QML: warna per level, label, opacity
AMAN_Kawasan.qgz                     # proyek siap pakai + basemap XYZ
AMAN_Kawasan.qlr                     # definisi layer (drag-and-drop)
PANDUAN.pdf                          # 2 halaman, bergambar
contoh_terisi.gpkg                   # 1 kawasan + 1 gedung + 1 lantai + 3 ruangan
contoh_rusak.gpkg                    # SENGAJA rusak — untuk menguji jalur galat di CI
```

**Mengapa GeoPackage untuk template, bukan SHP:** tanpa batas nama field 10 karakter · UTF-8 native · CRS tertanam (tidak ada `.prj` hilang) · banyak layer dalam satu file · tanpa batas 2 GB. Tetap **terima** SHP saat impor — hanya jangan mendorong orang membuat data baru di dalamnya.

QGIS memuat otomatis `.qml` yang bernama sama dengan layer di direktori sama; gaya juga bisa disimpan di tabel `layer_styles` di dalam GeoPackage. Pakai **Value Relation / value map** agar `tipe_ruangan` menjadi dropdown, bukan teks bebas — ini yang paling menekan galat surveyor.

> **[O] Verifikasi wajib sebelum rilis:** generator `.gpkg` dinamis (per-satker, kode gedung sudah terisi) terbukti bisa dibangun tanpa GDAL, tetapi **belum diuji dibuka di QGIS asli**. Rilis pertama: simpan template dasar sebagai **aset biner statis** yang dihasilkan sekali oleh QGIS/ogr secara luring; generator dinamis menyusul sebagai peningkatan.

**`Template_AMAN_GoogleEarth_v1.kmz`:**

```
doc.kml
├─ <Schema name="AMAN_Ruangan" id="AMAN_Ruangan">   ← id NON-NUMERIK, wajib awali HURUF
│     <SimpleField type="string" name="kode_ruangan"/> …
├─ <StyleMap> normal/highlight per level
└─ <Folder name="KIKN">
     └─ <Folder name="WP 1 — KIPP">
          └─ <Folder name="GD-01 Gedung A">
               ├─ <Folder name="L-01 Basement 1">   ← 1 folder per lantai,
               └─ <Folder name="L01 Lantai 1">        awalan ordinal → urut leksikografis
                    └─ <Placemark> CONTOH POLIGON TERISI + ExtendedData lengkap
```

**Aturan tegas:**
- **`id` Schema harus diawali huruf** [V] — `simplekml` memancarkan `id="1"` yang **gagal validasi XSD** (`'1' is not a valid value of the atomic type 'xs:ID'`); Google Earth menerimanya, validator tidak. Dua pustaka KML terpopuler Python **tidak bisa saling baca dengan setelan bawaan**.
- **Satu poligon contoh yang benar-benar terisi per level** — surveyor menyalinnya. **Ini penekan galat tunggal terbesar.**
- `<description>` berisi instruksi di setiap Folder (muncul di panel samping GE Pro).

### 6.5 Format laporan galat impor

```json
{
  "ringkasan": {"fitur_dibaca": 412, "diterima": 398, "peringatan": 11, "ditolak": 3},
  "crs": {"terdeteksi": "EPSG:32750", "sumber": ".prj", "keyakinan": "tinggi",
          "direproyeksi_ke": "EPSG:4326", "perlu_konfirmasi": false},
  "encoding": {"terdeteksi": "ISO-8859-1", "sumber": ".cpg", "curiga_mojibake": 2},
  "parser": {"peringatan_xml": ["baris 88: entitas '&' tidak ter-escape — karakter dibuang"]},
  "masalah": [
    {"fitur": 17, "id": "R-204", "tingkat": "diperbaiki", "kode": "GEOM_SELF_INTERSECT",
     "pesan": "Poligon berpotongan sendiri di 116.8501,-0.9503 — diperbaiki otomatis (make_valid). Luas berubah 24,5 → 24,5 m² (0,0%).",
     "tindakan": "Periksa bentuk di peta pratinjau."},
    {"fitur": 88, "id": null, "tingkat": "ditolak", "kode": "PARENT_NOT_FOUND",
     "pesan": "Kolom gedung_kode='GD-99' tidak ada di master gedung satker ini.",
     "tindakan": "Perbaiki kode gedung, atau daftarkan GD-99 lebih dulu."}
  ]
}
```
Tiga tingkat: `diperbaiki` (lanjut, catat) · `peringatan` (lanjut, minta konfirmasi) · `ditolak` (fitur dilewati). Selalu sertakan **nomor fitur + nilai pengenal + tindakan yang bisa dilakukan**.

---

## BAGIAN 7 — FRONTEND: GAMBAR & RENDER

### 7.1 Pustaka gambar — `@geoman-io/leaflet-geoman-free` 2.20.0

**Angka diukur langsung dari tarball npm [V]:**

| Pustaka | Rilis terakhir | Lisensi | min+gzip | Putusan |
|---|---|---|---|---|
| **`@geoman-io/leaflet-geoman-free` 2.20.0** | **2026-06-23** | **MIT** | **73,2 KB** JS + 6,4 KB CSS | ✅ **PILIH** |
| `terra-draw` 1.32.2 + adapter | 2026-07-22 | MIT | 40,7 KB | 🥈 cadangan |
| `leaflet-draw` 1.0.4 | **2018-10-24** | MIT | 13,9 KB | ❌ mati 8 tahun, tanpa snapping |
| `leaflet.vectorgrid` 1.3.0 | **2017-08-28** | **Beerware** | — | ❌ risiko audit legal instansi |
| `leaflet-distortableimage` | 2022-10-10 | MIT | ~1,5 MB unpacked | ❌ tidak perlu |

> **Koreksi klaim yang beredar:** artikel menyebut Terra Draw "~300 KB vs ~140 KB Leaflet" — itu membandingkan ukuran **raw**, bukan gzip. Terukur: Terra Draw **lebih kecil ter-gzip**. Klaim ukuran harus diverifikasi, bukan dikutip.

**Fitur versi FREE — diverifikasi dengan memindai token di `dist/leaflet-geoman.js@2.20.0` [V]:**

| Kebutuhan pemilik | FREE? | Token |
|---|---|---|
| Gambar poligon/persegi | ✅ | `drawPolygon`, `drawRectangle` |
| Edit vertex + midpoint | ✅ | `editMode`, `markerEditable` |
| **Snapping** | ✅ | `snappable`, `snapDistance`, `snapSegment`, `snapMiddle` |
| **Potong poligon** | ✅ | `cutPolygon` |
| **Ukur luas/panjang** | ✅ | `measurement` |
| Geser / putar / hapus | ✅ | `dragMode`, `rotateMode`, `removalMode` |
| Cegah self-intersect | ✅ | `allowSelfIntersection: false` |
| **Edit ImageOverlay** (georef denah!) | ✅ | `ImageOverlay` (ada di dist **dan** `.d.ts`) |
| Auto-trace batas tetangga | ❌ PRO | — |
| Split / Scale / requireContainment | ❌ PRO | — |

**Mengapa Geoman meski 30 KB lebih besar dari Terra Draw:** (1) empat fitur yang diminta pemilik (potong, snapping, ukur luas, edit vertex) ada di FREE; Terra Draw tak punya cut/merge maupun UI pengukuran → butuh turf tambahan, selisih ukuran hilang. (2) **Native Leaflet** — bekerja langsung di atas `L.geoJSON`/`L.LayerGroup` yang **[V] sudah dipakai** `AssetMapFullView.jsx` (1.473 baris) + `leaflet.markercluster`. (3) **`ImageOverlay` bawaan** menyelesaikan georeferensi denah tanpa `leaflet-distortableimage`. (4) MIT + aktif.

**Pengganti fitur PRO yang hilang:**
- `requireContainment` → **snapping ke poligon induk** + **validasi containment di SERVER** (§4.3) yang mengembalikan `rasio_luar`. Ini justru lebih benar: **klien tidak boleh jadi otoritas topologi**.
- `autotrace` → tombol **[Ikuti batas induk]** yang menyalin ring induk sebagai titik awal (± 20 baris: `L.polygon(indukLatLngs)` lalu `pm.enable()`).
- `splitMode` → substitusi dengan `cutPolygon`.

**Mitigasi bundle (WAJIB — [V] build saat ini 16 MB, `main.js` 361 KB):**

```jsx
const EditorDenah = React.lazy(() => import("./pages/EditorDenahPage"));  // App.js

// Di dalam EditorDenahPage — impor DINAMIS, bukan top-level:
useEffect(() => {
  let batal = false;
  (async () => {
    await import("@geoman-io/leaflet-geoman-free");
    await import("@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css");
    if (batal || !map) return;
    map.pm.setLang("id");
    map.pm.addControls({ position: "topright", drawCircle: false,
                         drawCircleMarker: false, drawText: false,
                         cutPolygon: true, rotateMode: true });
    map.pm.setGlobalOptions({
      snappable: true, snapDistance: 20, snapMiddle: true,
      allowSelfIntersection: false, continueDrawing: false,
      layerGroup: lapisanGambar,        // isolasi dari layer marker/cluster
    });
  })();
  return () => { batal = true; };
}, [map]);
```
Tandai layer yang **tidak boleh** disentuh alat gambar dengan `pmIgnore: true` (basemap aset, marker cluster) — tanpa ini `editMode` mengaktifkan handle di seluruh marker aset.

**Turf: impor per-modul.** Hanya `@turf/area` (19,2 KB) dan `@turf/boolean-point-in-polygon` (17,8 KB) untuk offline PIP. **JANGAN** `@turf/turf`. Geoman sudah menyeret turf + `polyclip-ts` + `lodash` ter-bundle di `dist` — impor dari `dist`, **jangan** dari `src/`.

⚠️ `yarn.lock` **harus di-regenerate** — CI memakai `--frozen-lockfile`.

### 7.2 Render banyak poligon — strategi bertingkat

1. **Canvas renderer** — wajib, dampak terbesar dengan perubahan satu baris: `L.geoJSON(data, { renderer: L.canvas({ padding: 0.5 }) })`. SVG membuat 1 elemen DOM per poligon.
2. **Pemuatan per-viewport + LOD per zoom.** `GET /spasial/geojson?bbox=…&level_maks=80&z=14`. Debounce `moveend` 300 ms, batalkan request lama dengan `AbortController` (pola sudah ada di `AssetMapFullView.jsx:131`).
   **LOD default:** z<10 → kawasan · 10–12 → +WP · 12–14 → +SWP/blok · 14–16 → +tapak · 16–17 → +gedung · z≥17 → +lantai aktif & ruangan.
3. **Satu `L.LayerGroup` per level** → `addTo`/`removeFrom` per tingkat menjadi O(1).
4. **Batas keras render:** > 3.000 fitur → server kirim bbox + `titik_wakil` saja + banner "Perbesar peta untuk melihat detail". Mencegah tab hang di HP lapangan.
5. **[F]** Analisis banding 2025: untuk hingga **50.000 garis dan 10.000 poligon, Leaflet dan OpenLayers paling cepat**; di atas ~50.000 fitur barulah MapLibre unggul. Skala AMAN jauh di dalam zona nyaman Leaflet → **tidak ada alasan pindah ke WebGL**.
6. Clustering hanya untuk **titik** — jangan cluster poligon.

### 7.3 Georeferensi denah lantai — `gx:LatLonQuad` (4 sudut)

Dua mekanisme standar KML: `<LatLonBox>`+`<rotation>` (persegi utara-atas) dan `<gx:LatLonQuad>` (4 sudut sembarang, CCW dari kiri-bawah, harus cembung).

**[O] Terapkan `gx:LatLonQuad` sebagai model utama**, `LatLonBox` sebagai kasus khusus. Empat sudut mencakup rotasi tanpa trigonometri terpisah, dan itulah tepatnya yang dihasilkan alur "seret 4 sudut denah di atas peta".

**Alur pengguna:**
1. Unggah gambar denah (PNG/JPG) → **GridFS**.
2. Tampilkan `L.imageOverlay(..., {opacity: 0.75, interactive: true})` di atas peta; **footprint gedung digambar garis merah tebal** sebagai target penyelarasan.
3. `ov.pm.enable({ draggable: true })` → geser/skala/putar sampai kolom & dinding lurus dengan citra satelit.
4. **[Kunci]** → `gambar_denah.terkunci = true`, simpan 4 pasang lon/lat sebagai `sudut_bumi`.
5. Gambar ruangan **di atas** overlay → hasilnya otomatis dalam WGS84.

**Rubber-sheeting (thin-plate spline) DITOLAK** — denah arsitektur adalah gambar **ortogonal**; transformasi affine (geser+skala+putar) Geoman sudah cukup secara matematis. Rubber-sheeting hanya perlu untuk foto udara miring, dan membutuhkan GDAL.

### 7.4 Level switcher indoor

```
┌────┐
│ 12 │  ordinal 12
│ …  │
│  1 │
│  D │  ordinal 0, label_pendek "D" — DEFAULT terpilih (konvensi IMDF)
│ B1 │  ordinal −1
│ B2 │
└────┘
```
1. Muncul hanya bila zoom ≥ z17 **dan** ada satu gedung dominan di viewport (atau user mengklik gedung).
2. Memilih lantai → ganti `ImageOverlay`, muat ulang layerGroup "Ruangan" untuk `parent_id = <lantai>`, redupkan poligon gedung jadi outline, simpan `?lantai=-1` di URL (bookmark-able).
3. **Default = ordinal 0**, bukan lantai terendah.
4. Tampilkan `label_pendek`, **urutkan dengan `ordinal`**. Jangan pernah mengurutkan lantai berdasarkan string ("10" < "2" secara leksikografis).
5. Hormati tap-target ≥44 px di ≤1023 px (`index.css` repo).

### 7.5 Konvensi lantai — enam aturan besi

**Bukti [F]:** IMDF (OGC Community Standard): *"The Level that models the lowest floor which supports ground-floor access MUST have an ordinal equal to 0"* · *"…nearest to ground-floor, but entirely below ground, MUST have an ordinal equal to -1"* · *"A Building MAY be referenced by more than one Level with the same ordinal…different floor naming conventions"*. OSM Simple Indoor Tagging independen mencapai pola sama: *"zero indicates the ground floor, negative numbers indicate underground"* dan *"Data consumers require values to be numeric and consecutive, even for basements and mezzanines known by mnemonics such as 'B', 'B1', 'G', 'M', and '2M'"*.

**Konvensi Indonesia [F]:** Indonesia memakai **KEDUA** sistem — Eropa (`G/0` untuk lantai dasar) **dan** Amerika (`Lantai 1` untuk lantai dasar), tergantung pengelola gedung. Mal memakai **LG/GF/UG**. **Tetraphobia:** banyak gedung menghilangkan lantai **4 dan 13**, diganti **"3A"** dan **"12A"**. → **"Lantai 1" di Indonesia AMBIGU. Jangan pernah pakai label sebagai kunci urutan.**

1. **`ordinal` = INTEGER, rapat & berurutan, unik per gedung. `0` = lantai dengan akses masuk utama.** Basement `-1, -2, …`. **JANGAN PERNAH menurunkan `ordinal` dari `label`.**
2. **Mezanin dapat `ordinal` sendiri**, bukan `x.5` (pecahan tidak konsisten didukung). Gedung `B1, G, M, 1, 2` → `-1, 0, 1, 2, 3`. **Konsekuensi yang disengaja: `label "Lantai 2"` ≠ `ordinal 2`. Itu justru gunanya pemisahan ini.**
3. **Lantai 4/13 hilang → hanya LABEL yang lompat, `ordinal` tetap rapat:** `{ord:3,"Lantai 3"}, {ord:4,"Lantai 3A"}, {ord:5,"Lantai 5"}`.
4. **`elevasi_m` adalah wasit terakhir** — split-level, podium+tower, bangunan di lereng. Dua lantai ber-`ordinal` sama dibedakan elevasinya (setara `ElevationOfRefHeight` di IFC).
5. **Podium + Tower → `Gedung` terpisah di bawah satu `Tapak`.** Lantai podium yang membentang di bawah kedua tower memakai `lantai.gedung_ids: [towerA, towerB]` — persis mekanisme IMDF `building_ids`.
6. **Enum `kategori`:** `basement` · `semi_basement` · `lower_ground` · `ground` · `upper_ground` · `mezzanine` · `normal` · `teknis_mep` · `refuge` · `parkir` · `rooftop` · `helipad` · `atap`.

**Migrasi aman dari kondisi sekarang [V]:** `backend/routes/ruangan.py:36-46` menyimpan `gedung: str` dan **`lantai: str` (teks bebas)**; `ruangan_utils.py:21` `ringkas_lokasi()` mencetak `f"Lt. {lantai}"`. **Pertahankan `gedung`/`lantai` sebagai string tampilan terdenormalisasi** (backward-compat penuh, tidak memecah KIR/DBR & tes), lalu **tambah** `spasial_node_id`, `gedung_id`, `lantai_id`, `lantai_ordinal`. Parser `normalisasi_ordinal_lantai("B2"|"LG"|"G"|"M"|"3A"|"12A"|"Rooftop")` menjadi fungsi **murni teruji unit** di `spasial_utils.py`.

---

## BAGIAN 8 — INGEST IoT

### 8.1 Prinsip arsitektur

> **SATU pipeline "Observasi Lokasi" untuk SEMUA sumber** — scan QR, aplikasi pendamping, Traccar, BLE gateway, RFID gate, entri manual — dengan skema seragam bermuatan `sumber` + `akurasi_m` + `kepercayaan`. Semua fitur lanjutan (geofence, Wasdal, KIR otomatis) dibangun di atas satu pipeline itu. **Jangan bangun 5 sistem terpisah per teknologi.**

**Tiga koreksi terhadap asumsi awal:**
1. **IMEI ≠ pelacakan [F].** IMEI adalah nomor identitas (TAC 8 + serial 6 + check digit Luhn). Tidak ada API yang mengubah IMEI menjadi koordinat. Lebih buruk: **sejak Android 10 aplikasi biasa tidak bisa membaca IMEI**; **MDM ber-mode Profile Owner pun tidak bisa di Android 12+**; di iOS tidak pernah bisa. → IMEI dipakai sebagai **identitas BMN + jalur blokir CEIR saat hilang**, bukan sumber lokasi.
2. **GPS mati di dalam gedung [F].** Semua skenario "aset di ruangan mana" **tidak bisa** diselesaikan GPS. Butuh jalur terpisah (QR / BLE / RFID gate).
3. **Melacak perangkat pegawai = melacak orang [F/O].** Tunduk UU 27/2022 (PDP). Lihat §10.

> **Jawaban langsung untuk permintaan pemilik #5:** "pengguna pilih lantai, ruangan terdeteksi otomatis" **tidak butuh IoT sama sekali** — cukup point-in-polygon GPS → rantai level, lalu pengguna memilih lantai, lalu titik diuji terhadap poligon ruangan pada lantai itu (§5.3).

### 8.2 Transport — HTTP, MQTT ditunda

| Kriteria | HTTP POST batch | MQTT |
|---|---|---|
| Perangkat tahap awal | HP/tablet (sudah HTTPS+JWT), laptop, Traccar | — |
| Reuse infra repo | **Penuh** (`auth_utils`, `slowapi`/`limits`, `audit_logs`, `event_bus`, WebSocket) | Broker + auth terpisah + subscriber worker |
| Overhead ops VPS kecil | Nol tambahan | +1 layanan, +1 titik gagal, +monitoring |
| Kapan MQTT WAJIB | — | **≥ ~1.000 perangkat mandiri**, interval < 60 dtk, atau NB-IoT hemat daya (overhead TLS-handshake HTTP membunuh baterai/kuota) |

**Bila nanti perlu:** Mosquitto lokal (bind 127.0.0.1, footprint ±200 KB **[F]**) → satu subscriber asyncio → menulis ke **fungsi ingest yang SAMA**. Migrasi: broker berdampingan → firmware publish MQTT dengan HTTP fallback → ingest pindah → HTTP deprecate.

**[V] Aset repo yang dipakai ulang:** `backend/event_bus.py` sudah mengimplementasikan **capped collection + tailable cursor** sebagai antrean lintas-worker tanpa Redis — **persis primitif** untuk fanout posisi live dan DLQ ringan. **Tidak perlu Kafka maupun Celery.**

### 8.3 Validasi IMEI (pure Python, nol dependensi)

```python
def imei_valid(s: str) -> bool:
    d = "".join(ch for ch in str(s or "") if ch.isdigit())
    if len(d) == 16:                       # IMEISV → 2 digit terakhir = versi software
        d = d[:14] + luhn_digit(d[:14])
    if len(d) != 15:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0
```
Dual-SIM (fisik atau eSIM) → **2 IMEI** → simpan sebagai array. Simpan juga **TAC** (8 digit pertama) untuk validasi silang merek/model saat pengadaan.

### 8.4 TABEL KONDISI TEPI IoT → PENANGANAN

**Prinsip [F]:** pengiriman IoT bersifat **at-least-once** — duplikat adalah trade-off bawaan. Idempotensi = **ID unik stabil per pesan** + konsumer menyimpan catatan item terproses di sistem pencatatan yang sama dengan efek sampingnya.

#### Kelompok 1 — Integritas pesan

| # | Kondisi | Penanganan |
|---|---|---|
| 1 | Paket duplikat | `obs_id = sha1(device_id + ts_device + lat + lon)` → **unique**; `insert_many(ordered=False)`, tangkap `BulkWriteError` duplikat sebagai **sukses**. Ack per-item |
| 2 | Batch dikirim ulang seluruhnya | Header `Idempotency-Key` → `iot_batch_receipts` (TTL 24 jam) → kembalikan respons tersimpan |
| 3 | Out-of-order | Simpan apa adanya ke history. `posisi_terakhir` di-update **bersyarat** `ts_device < ts_baru` → posisi lama **tidak pernah** menimpa yang baru |
| 4 | Clock skew / drift | Simpan **dua** stempel `ts_device` & `ts_server`; `skew = ts_server − ts_device` → `kesehatan.clock_skew_ms`. \|skew\| > 24 jam → `ts_ragu=true`, urutkan pakai `ts_server`, kirim perintah sinkron waktu |
| 5 | Timestamp masa depan | `ts_device > ts_server + 5 mnt` → klem ke `ts_server`, `ts_dikoreksi=true` |
| 6 | Payload rusak / skema asing | **Jangan gagalkan batch** → `iot_dead_letter` (payload mentah + alasan + device_id + waktu). **DLQ membengkak = indikator kegagalan utama [F]**; alert bila > 100/jam |
| 7 | Versi firmware berbeda | `schema_v` wajib; adapter per versi; versi tak dikenal → DLQ, **bukan crash** |

#### Kelompok 2 — Kualitas data lokasi

| # | Kondisi | Penanganan |
|---|---|---|
| 8 | Koordinat (0,0) "Null Island" | Tolak keras → DLQ `koordinat_null` |
| 9 | Koordinat di luar rentang | Validasi `-90≤lat≤90`, `-180≤lon≤180`; GeoJSON = **lon dulu** → DLQ |
| 10 | Akurasi buruk / HDOP tinggi | `akurasi_m > 100` atau `hdop > 5` → simpan tapi `kualitas="rendah"`, **tidak memicu geofence** |
| 11 | GPS drift saat diam | **Min-speed filter**: `speed < 3 km/jam` = stationer. **Snap-to-stop**: 3 titik berturut dalam radius `max(15 m, akurasi_m)` → pertahankan koordinat pertama, naikkan `durasi_diam`, **jangan tulis titik baru** (hemat storage besar) |
| 12 | Lompatan mustahil (teleport) | `jarak/Δt > 250 km/jam` (darat) → `outlier=true`, tidak dipakai geofence |
| 13 | Lintasan zigzag | Tahap 1: **median-of-3 + filter akurasi** cukup. Kalman filter hanya bila keluhan muncul |
| 14 | Indoor tanpa fix GPS | **Jangan buang** — simpan `sumber="wifi"/"ble"/"cell"` dengan `akurasi_m` besar; tetap berguna untuk "ada di gedung mana" |

#### Kelompok 3 — Konektivitas & volume

| # | Kondisi | Penanganan |
|---|---|---|
| 15 | Offline buffering / backfill masif | Batas **500 obs/batch**. Backfill (`ts_device` > 1 jam lalu) → **jalur lambat**: tidak memicu notifikasi real-time; evaluasi geofence retrospektif ditandai `retro=true`. Reuse pola antrean offline frontend yang sudah ada |
| 16 | Rate limiting / flood | `slowapi`+`limits` **[V] sudah di requirements**. 60 req/mnt & 5.000 obs/jam per perangkat → 429 + `Retry-After`. > 10× batas selama 3 jam → auto-`status="karantina"` + alert |
| 17 | Backpressure (DB lambat) | Ingest **hanya menulis** ke koleksi mentah → **202 Accepted**. Geofence/notifikasi/agregasi di `jobs.py`. Antrean > ambang → 503 + `Retry-After` |
| 18 | Retry badai setelah outage | Wajibkan **exponential backoff + jitter** di perangkat; server menyisipkan `Retry-After` acak 30–300 dtk |
| 19 | Koneksi putus di tengah batch | Aman — idempoten (#1, #2) |
| 20 | Kuota data mahal | Server-driven config: **diam = 15 mnt, bergerak = 60 dtk**; gzip; kirim delta |

#### Kelompok 4 — Kesehatan perangkat

| # | Kondisi | Penanganan |
|---|---|---|
| 21 | Baterai lemah | < 20% → event `baterai_rendah`; < 5% → "last gasp" posisi lalu berhenti |
| 22 | Hilang kontak | Heartbeat tiap `interval × 3`. Job periodik: `terakhir_terdengar > 2× interval` → `tak_terdengar`; > 24 jam → **temuan Wasdal** |
| 23 | Sinyal hilang di area tertentu | Bedakan dari "hilang": titik terakhir di dalam gedung/basement → `kemungkinan_indoor`, **jangan alarm merah** |
| 24 | Tamper / dicabut | Event tamper tracker → **prioritas tinggi Wasdal + notifikasi instan** |
| 25 | Kredensial bocor / dicuri | Revoke token (`status="dicuri"`) → ingest 401; posisi terakhir **dikunci sebagai barang bukti**; picu blokir IMEI + lapor polisi |
| 26 | Pemegang berganti, registry basi | `iot_devices.pemegang.nip` ≠ `asset_custody` aktif → temuan `registry_perangkat_tidak_sinkron` |
| 27 | Jam mundur setelah factory reset | `ts_device` turun drastis + uptime reset → minta sinkron NTP; sementara pakai `ts_server` |
| 28 | Spoofing perangkat lain | HMAC per-perangkat + tolak bila `device_id` di payload ≠ di kredensial |

#### Kelompok 5 — Operasional & tata kelola

| # | Kondisi | Penanganan |
|---|---|---|
| 29 | Perangkat lintas satker | Observasi distempel `kode_satker` **dari registry, BUKAN dari payload** → isolasi M-SCOPE utuh |
| 30 | DLQ menumpuk → replay | `POST /iot/dlq/{id}/replay` (idempoten). Backfill wajib menegakkan urutan + idempotensi + melacak progres/provenance |
| 31 | Ganti tracker pada aset sama | `melekat_pada[]` bertanggal → lintasan historis aset **kontinu** walau perangkatnya berganti |
| 32 | Lewat batas retensi | TTL index + job agregasi harian sebelum penghapusan |
| 33 | Waktu & zona waktu | **Semua UTC** (`datetime.now(timezone.utc)`, konsisten pola repo). Konversi ke **WITA (Asia/Makassar, UTC+8)** hanya di lapisan tampilan — IKN berada di WITA |

### 8.5 Retensi & volume

**Tiga lapis:** `iot_posisi_terakhir` (hot, 1 dok/perangkat) · `iot_observasi` (time-series, TTL **90 hari**) · `iot_rekap_harian` (permanen, murah).

**[F]** Granularity dipilih dari periode laju ingest (5 menit → `seconds`). TTL time-series mengevaluasi `timeField` **per-bucket** dan menghapus bucket kedaluwarsa otomatis — **tanpa job pembersih aplikasi**.

**Estimasi volume realistis IKN:**

| Sumber | Jumlah | Interval | Titik/hari |
|---|---|---|---|
| HP dinas (10 jam kerja, presisi diturunkan) | 300 | 5 mnt | 36.000 |
| Kendaraan dinas (12 jam) | 50 | 30 dtk | 72.000 |
| Laptop (agen) | 400 | 30 mnt | 6.400 |
| Scan QR opname | — | event | ~2.000 |
| **Total** | | | **≈ 116.000 titik/hari** |

≈ 23 MB/hari mentah → kompresi kolumnar time-series (3–10×) → **≈ 3–8 MB/hari** → **≈ 0,3–0,7 GB untuk 90 hari**. **Aman untuk VPS 8 GB.** Bila skala 10× → turunkan retensi presisi ke 30 hari. *(Rasio kompresi = estimasi; ukur ulang dengan `db.iot_observasi.stats()` setelah 1 minggu produksi.)*

**Downsampling:** job harian 02:00 WITA → `iot_rekap_harian` + **penipisan lintasan Douglas–Peucker** (pure Python ±30 baris, toleransi 10 m) untuk data > 7 hari → hemat 60–80% titik tanpa kehilangan bentuk rute.

### 8.6 Geofence engine — histeresis

**[F] Aturan anti-flapping terbukti:** dwell minimum sebelum "masuk" · "keluar" dikonfirmasi setelah tetap di luar sekian lama · hysteresis/sliding window · **radius minimum 100–150 m** untuk zona luar berbasis GPS (rekomendasi resmi Android).

```python
GEO_PARAM = {
    "buffer_masuk_m": 0,           # polygon apa adanya
    "buffer_keluar_m": 25,         # keluar dinilai pada polygon DIPERBESAR → histeresis
    "sampel_min": 3,
    "dwell_masuk_dtk": 120,
    "dwell_keluar_dtk": 180,
    "cooldown_dtk": 600,
    "abaikan_akurasi_di_atas_m": 100,
}
# status: LUAR → KANDIDAT_MASUK → DALAM → KANDIDAT_KELUAR → LUAR
```
**Kunci histeresis: ambang masuk dan keluar TIDAK sama.** Ini menghilangkan flapping di garis batas — masalah yang tidak bisa diselesaikan dwell saja.

**Event:** `masuk` · `keluar` · `dwell_terlampaui` (aset diam di luar area sah > X jam) · `tidak_kembali` (kendaraan tak balik ke pool setelah jam kerja) · `tamper` → publish ke `event_bus.py` → WebSocket + notifikasi + **temuan Wasdal**.

**Evaluasi tanpa round-trip DB per observasi:** cache poligon aktif di memori worker (refresh via `event_bus`), **bbox prefilter → ray casting pure-Python** (±40 baris, nol dependensi, teruji unit). Deteksi geofence **harus di jalur TULIS (ingest)**, bukan saat baca — time-series hanya mendukung `$geoNear` (aggregation), **tidak** `$near`/`$nearSphere`. Ini justru arsitektur yang benar.

---

## BAGIAN 9 — MATRIKS TEKNOLOGI PELACAKAN

### 9.1 HP / Tablet

| Jalur | Cara kerja | Akurasi | Biaya | Catatan |
|---|---|---|---|---|
| **① Aplikasi pendamping AMAN** (PWA/Android) | Lapor GPS + hasil scan QR ke `/api/iot/ingest` | 5–20 m outdoor | **Rp 0** | **Paling direkomendasikan.** Repo sudah offline-first (IndexedDB + antrean simpan) → buffer offline gratis |
| ② MDM fully-managed (Android Device Owner, Intune, Jamf) | MDM lapor lokasi | 5–50 m | Lisensi/perangkat/bulan | Perangkat harus **milik negara & di-enroll sejak factory reset**. **[F]** Admin **tidak bisa memaksa Location Services menyala**; work profile → admin **tidak punya visibilitas ke profil personal** |
| ③ Find My / Find Hub | Manual oleh pemegang/admin akun | Variatif | Rp 0 | **[F]** Tidak ada API enterprise. Prosedur darurat manual saja |
| ④ Data operator (Cell-ID) | Lawful interception | 100 m–3 km | — | **Hanya lewat permintaan resmi aparat** |

> ⚠️ Pustaka tidak resmi seperti `FindMy.py` yang login ke iCloud melanggar ToS Apple dan rapuh — **jangan** dipakai instansi.

**IMEI untuk AMAN:** kunci identitas BMN elektronik seluler (anti-tukar jeroan) · rekonsiliasi pengadaan via **CEIR** (Kemenperin mengatur database IMEI) · **jalur pemblokiran saat hilang** (Komdigi menyiapkan opsi pemblokiran IMEI) → jadikan **aksi standar** di modul Pengamanan: status aset `hilang` → checklist "ajukan blokir IMEI".

### 9.2 Laptop / Notebook

| Opsi | Akurasi lokasi | Biaya | Batasan |
|---|---|---|---|
| Serial / service tag / TPM EK | **tidak ada lokasi** | Rp 0 | Hanya pencocokan opname |
| **Agen ringan buatan sendiri** (Go/Python ±300 baris atau osquery) | **Level gedung/lantai** bila BSSID dipetakan | Rp 0 | Bisa dimatikan user |
| Prey | 10–100 m | SaaS/perangkat | ⚠️ **transfer data lintas negara** (UU PDP) |
| Absolute Persistence | 10–100 m | Termahal | Persistensi firmware; **tidak mendukung Linux**, butuh laptop OEM tertentu |

**[O] REKOMENDASI: "BSSID→Ruangan" milik sendiri.** Geolokasi BSSID via layanan publik sudah tidak layak (Mozilla Location Service tutup; Google Geolocation API berbayar & mengirim data keluar). **Tapi AMAN akan punya denah berlapis:**
1. Saat survei, petugas berjalan tiap ruangan/lantai dengan app AMAN → rekam BSSID + RSSI → `ruangan_wifi_map`.
2. Agen laptop melapor daftar BSSID → server mencocokkan → **"Laptop X terakhir terlihat di Gedung A, Lantai 3"**.
3. **Tanpa vendor, tanpa data keluar negeri, tanpa biaya**, dan presisi level-gedung sudah cukup untuk Wasdal **dan** untuk privasi.
4. Fallback: geolokasi IP publik → level kota (cukup untuk "laptop keluar kawasan IKN").

### 9.3 Tracker GPS khusus

**[F]** Protokol umum: **Teltonika FMB**, **Concox GT06** (biner TCP, header `0x78 0x78`, CRC-16), Queclink, TK103. **Traccar** open-source mendukung **200+ protokol / 2000+ model**, menormalisasi ke satu model `Position`.

**[O] Pola: Traccar = GATEWAY PROTOKOL, AMAN = SISTEM CATATAN.** Jangan menulis decoder biner sendiri.

```xml
<entry key='forward.enable'>true</entry>
<entry key='forward.type'>json</entry>
<entry key='forward.url'>https://aman.ikn.go.id/api/iot/traccar-webhook</entry>
<entry key='forward.header'>Authorization: Bearer &lt;TOKEN_GATEWAY&gt;</entry>
<entry key='forward.retry.enable'>true</entry>
```
**[O] Catatan VPS kecil:** Traccar berjalan di JVM (±512 MB–1 GB RAM) → **container/VPS terpisah** dari FastAPI. Atau pilih tracker yang mendukung **HTTP POST JSON langsung** dan lewati Traccar sepenuhnya.

**Konektivitas [F]:** Telkomsel NB-IoT "dapat dijangkau di kota-kota besar di Indonesia", daya sangat rendah; 4G >97% populasi. **[O]** IKN masih berkembang → **verifikasi coverage NB-IoT di lokasi sebelum membeli**; default paling aman = tracker **LTE Cat-1/Cat-M** dengan SIM IoT yang bisa fallback 2G/4G.

### 9.4 Indoor — memastikan aset di RUANGAN tertentu

**[F]** Angka vendor 2026 (verifikasi ulang saat pengadaan):

| Teknologi | Akurasi | Biaya tag | Infrastruktur | Sifat |
|---|---|---|---|---|
| BLE beacon RSSI | 3–5 m | $5–20 | Gateway per zona (HP/tablet bisa jadi reader) | Kontinu, level zona/lantai |
| BLE AoA | 0,3–0,5 m | Lebih mahal | Locator khusus | Presisi tinggi |
| UWB | 10–30 cm | Proprietary | **Anchor berkabel** — termahal | Sub-meter |
| Wi-Fi RTLS / FTM | 5–15 m | $0 | Reuse AP existing | Level-ruangan tanpa infra baru |
| **RFID UHF pasif (gerbang)** | Checkpoint | **$0,05–0,15** (>100k) | Reader **$500–2000** + antena $50–300 | **Peristiwa lintas-pintu** |

**[O] JANGAN kejar RTLS penuh. Tiga lapis:**
- **Lapis 1 (WAJIB, biaya ±0): Scan QR/stiker** saat opname/mutasi → observasi ruangan **kepercayaan 0,99**, frekuensi rendah. **[V]** `backend/stiker_utils.py` sudah ada.
- **Lapis 2 (nilai tertinggi per rupiah): Gerbang RFID UHF di pintu keluar gedung & gudang.** Menjawab pertanyaan Wasdal paling mahal: *"apakah aset KELUAR tanpa izin?"* — bukan *"aset di ruangan mana"*.
- **Lapis 3 (opsional, aset kelas A saja): BLE tag + 1 gateway per lantai/zona.** Presisi realistis = lantai/zona. Level ruangan sejati butuh gateway per ruangan atau AoA/UWB — **tidak dianjurkan fase awal**.

**[O] Perlakukan SCAN sebagai warga kelas satu**, bukan pelengkap: tanpa biaya, tanpa isu privasi (yang direkam adalah **aset**, bukan orang), akurasi ruangan **sempurna**. Kombinasikan: GPS/BLE memberi kontinuitas, QR memberi kebenaran.

### 9.5 Rekomendasi bertahap teknologi

| Tahap | Lingkup | Biaya | Nilai |
|---|---|---|---|
| **0 — Fondasi** | Registry perangkat, pipeline observasi, migrasi koordinat GeoJSON, geofence engine, kebijakan privasi | **Rp 0** (kode) | Semua tahap lain menumpang di sini |
| **1 — Cepat berdampak** | Scan QR sebagai observasi · app pendamping GPS untuk aset operasional/kendaraan · agen laptop + peta BSSID | **Rp 0** | Wasdal otomatis, DBR/KIR akurat |
| **2 — Hardware terarah** | Tracker GPS **kendaraan dinas & alat berat** via Traccar · gerbang RFID UHF pintu gudang/gedung utama | Tracker ±Rp 700rb–2,5jt + SIM IoT; reader $500–2000 | Aset bernilai tinggi terpantau |
| **3 — Opsional** | BLE tag kelas A per lantai · MDM fully-managed HP dinas · integrasi CEIR | Lisensi + tag | Hanya bila anggaran & kebutuhan terbukti |
| **JANGAN sekarang** | UWB · BLE-AoA · Absolute Persistence · SaaS pelacak asing | — | Biaya & risiko transfer data tidak sebanding |

---

## BAGIAN 10 — PRIVASI & KEPATUHAN (UU 27/2022 PDP)

### 10.1 Dasar hukum

**[F]** UU 27/2022 disahkan **17 Oktober 2022**, 16 bab / 76 pasal; berlaku untuk **sektor pemerintah maupun swasta**. Status aturan pelaksana per 2025–2026: **PP dan Perpres masih dalam harmonisasi; lembaga pengawas belum terbentuk**, peran sementara diampu Komdigi.

**[O]** Ketidakhadiran lembaga pengawas **bukan** alasan menunda kepatuhan — kewajiban material sudah berlaku dan sanksi administratif/pidana sudah ada. Desain harus konservatif karena aturan turunan berpotensi memperketat.

**Dasar pemrosesan [O]: JANGAN gunakan "persetujuan"** — hubungan atasan-bawahan membuat persetujuan tidak bebas, dan pegawai berhak menariknya kapan saja (yang akan mematahkan sistem). Gunakan:
1. **Pemenuhan kewajiban hukum Pengendali** — **PMK 207/PMK.06/2021** mewajibkan Pengguna Barang melakukan **pemantauan (administratif & lapangan, termasuk dengan teknologi informasi)**; PMK 181/2016 mewajibkan penatausahaan. **Ini dasar hukum terkuat untuk fitur pelacakan.**
2. Pelaksanaan tugas dalam rangka kepentingan umum / kewenangan Pengendali.
3. Perlindungan kepentingan sah Pengendali (mencegah kerugian negara) — dengan uji keseimbangan terdokumentasi.

**Regulasi pendukung:** PMK 40/2024 (Penggunaan BMN, sudah dirujuk `routes/bast.py`) · **PMK 43/2025 (Pengasuransian BMN — klaim BMN hilang butuh bukti lokasi/kronologi)** · PMK 53/2023 (BMN di IKN).

### 10.2 Enam belas kebijakan default — dipaksakan di SERVER

| # | Kebijakan | Implementasi teknis |
|---|---|---|
| 1 | **Hanya perangkat MILIK NEGARA yang dilacak.** BYOD dilarang | `iot_devices` wajib punya `asset_id` BMN terdaftar; tanpa itu → ingest **403** |
| 2 | **Degradasi presisi berbasis profil** — `personal` → dibulatkan ke level **GEDUNG/ZONA**; `kendaraan`/`operasional` → presisi penuh | `degradasi_presisi(obs, profil)` dipanggil **SEBELUM `insert`** — koordinat presisi **DIBUANG di ingest**, bukan disembunyikan di UI |
| 3 | **Hanya jam kerja untuk perangkat personal** (07:00–17:00 WITA) | Di luar jam → server **membuang** payload posisi; hanya simpan boolean `di_dalam_kawasan`. Perangkat juga diberi config agar tidak mengirim |
| 4 | **Mode Darurat (break-glass)** untuk aset hilang/dicuri: presisi penuh, 24 jam | **Dual approval pejabat berwenang** + **alasan wajib** + berbatas waktu + `audit_logs` + **notifikasi otomatis ke pemegang** |
| 5 | **Retensi berjenjang** | Lokasi presisi **90 hari** · agregat harian **2 tahun** · data profil-personal **30 hari**. TTL index + job agregasi |
| 6 | **Akses berbasis peran + alasan** | Peran baru `pemantau_bmn`. Setiap pembukaan riwayat mencatat **siapa melihat lokasi siapa, kapan, alasannya** |
| 7 | **Transparansi aktif** | Halaman `/profil/pelacakan` — pemegang melihat datanya sendiri penuh + "Apa yang direkam tentang saya" |
| 8 | **Indikator "sedang dilacak"** selalu tampil di app pendamping | UI wajib |
| 9 | **Larangan penggunaan sekunder** — **dilarang** untuk absensi, penilaian kinerja, disiplin kehadiran | Tertulis di kebijakan + **tidak disediakan endpoint**; `iot_rekap_harian` **tidak memuat jam masuk/pulang** |
| 10 | **Hak keberatan & penonaktifan** | Toggle + alur persetujuan atasan. Konsekuensi administratif (tanggung jawab penuh atas BMN + scan QR mingguan) — **bukan sanksi otomatis** |
| 11 | **Tidak ada keputusan otomatis merugikan** | Temuan Wasdal berbasis lokasi = **indikasi untuk diverifikasi manusia**; semua berstatus `perlu_verifikasi` |
| 12 | **Data tinggal di dalam negeri** | Hindari SaaS pelacak asing untuk perangkat yang dipegang pegawai. Traccar & broker **self-hosted di VPS Indonesia** |
| 13 | **Enkripsi & isolasi** | Lokasi di-scope `kode_satker`; koleksi lokasi **tidak masuk backup yang bisa diunduh operator biasa** (`routes/backup.py`) |
| 14 | **Pemberitahuan pemrosesan** ditandatangani saat penyerahan BMN | **Lampiran wajib pada BAST** — blok teks di generator `routes/bast.py` |
| 15 | **DPIA + Register Aktivitas Pemrosesan** dokumen hidup | `docs/DPIA-PELACAKAN-BMN.md`, ditinjau tiap fitur pelacakan baru |
| 16 | **Notifikasi insiden** | Runbook pemberitahuan kebocoran sesuai UU PDP |

> **[O] Satu kalimat untuk pemilik:** *"Sistem melacak BARANG NEGARA, bukan ORANG. Karena itu, untuk perangkat yang dipegang perorangan, sistem sengaja hanya menyimpan level gedung dan hanya pada jam kerja — presisi penuh dibuka hanya saat barang dilaporkan hilang, dengan persetujuan pejabat dan tercatat."*
> Kalimat ini adalah **kepatuhan sekaligus desain yang lebih murah** (data jauh lebih kecil).

**⚠️ Peta Kolaborasi publik WAJIB memiliki filter eksplisit** agar posisi perangkat personal **tidak pernah** bocor ke link publik (`routes/peta_kolaborasi.py`).

---

## BAGIAN 11 — MATRIKS INTEGRASI PER MODUL

| Modul | Titik sisip persis (path:baris) | Manfaat konkret |
|---|---|---|
| **WASDAL** ⭐ | `wasdal.py:373` `InsidentilIn.lokasi` → +`lat/lng/lantai_id` + auto-resolve · `wasdal.py:222-227` `PenertibanIn` (belum punya lokasi) · `wasdal_utils.py:395-411` `temuan_penatausahaan` — **sudah ada `"tanpa_koordinat"` di `:407-410`** · `WasdalPage.jsx:780-783` datalist → pemilih lantai + deteksi otomatis | **Nilai terbesar.** Titik ditancapkan → wilayah terdeteksi otomatis; pilih lantai → ruangan terdeteksi. **9 temuan baru**: `koordinat_di_luar_denah`, `tanpa_lokasi_spasial`, `lokasi_spasial_basi`, `aset_keluar_area`, `perangkat_tak_terdengar`, `lokasi_fisik_tidak_sesuai_kustodi`, `pinjam_pakai_lewat_jatuh_tempo`, `kendaraan_tidak_kembali_pool`, `tamper_perangkat`. Temuan `tanpa_koordinat` otomatis-tertutup begitu observasi masuk. **Sesuai amanat PMK 207/2021** |
| **Inventarisasi / Aset** | `asset_fields.py:73-74` · `models.py:110-111,180-181` · `AssetForm.jsx:846-856` (GPS) · `DashboardPage.jsx:1115-1135` (tambah via peta) & `:1187-1210` (geser pin) · `offlineSnapshot.js:52` | Rute opname optimal per lantai. **Auto-verifikasi**: aset terpantau di ruangan X selama periode opname → "terkonfirmasi lokasi"; hanya sisanya dicari manual. Klasifikasi "tidak ditemukan" mengecil drastis |
| **Pembukuan / DBKP** | `models.py:74` `location: Optional[str]` (teks bebas, **tanpa FK**) · `shared_utils.py:1067` `catat_mutasi_bmn` | Kolom lokasi berubah dari **teks bebas** menjadi **referensi berjenjang**. Rekonsiliasi ke SIMAN konsisten. ⚠️ Perpindahan ruangan **bukan** transaksi nilai — jangan buat kode transaksi baru; catat di audit + `timeline_utils` |
| **Penggunaan / BAST / PSP** | `penggunaan.py:239` `catat_psp`, `:49` `daftar_pemegang` · `bast.py:320` `bast_psp_pdf` | BAST memuat **lokasi kustodi terverifikasi** + lampiran peta. Mutasi pengguna otomatis menutup custody lama & membuka baru. **Sertijab tidak butuh BAST aset baru** (custody `jenis="jabatan"`) |
| **Pemeliharaan** | `pemeliharaan.py`, `jadwal_pemeliharaan` (indeks `indexes.py:152-153`) — **belum ada field lokasi** | Jadwal servis dikelompokkan **per gedung/lantai** (teknisi satu kali jalan). Aset keluar untuk perbaikan → overlay custody `pinjam_pakai` ke bengkel + geofence "di luar area servis" + deteksi **tidak kembali** |
| **Penilaian** | `penilaian_utils.py` | Nilai wajar dipengaruhi zona IKN. `iot_rekap_harian.jarak_km` kendaraan → dasar penyusutan lebih baik |
| **Pengamanan** | `pengamanan_utils.py:12` `JENIS_KEKURANGAN`, `:31` `kekurangan_aset`, `:370` `JENIS_OBJEK_CHECKLIST` · `pengamanan.py:232,303` `lokasi_simpan` | **Pengamanan fisik terukur**: alarm aset keluar gerbang tanpa izin. Status `hilang` → checklist otomatis (**blokir IMEI**, lapor polisi, **klaim asuransi PMK 43/2025 dengan bukti kronologi lokasi**). Jenis kekurangan baru `tanpa_ruangan_terdaftar` |
| **Persediaan** | `persediaan.py:95,107,1255` `lokasi` (gudang) · `:1578-1591` mutasi gudang · `:402,584,1149` filter | Gerbang RFID di pintu gudang → **pencatatan keluar-masuk otomatis** (jauh lebih cepat dari opname manual). Mutasi gudang jadi perpindahan antar-node denah |
| **Perencanaan (SBSK)** ⭐ | `perencanaan_utils.py:190-203` `SBSK_SEED_DEFAULT` — **sudah punya kategori `"ruang_kerja"` bersatuan `"m²"`** · `:206` `validate_sbsk` · `:237` `sanding_usulan_aset` | **SBSK berbasis RUANG NYATA**: luas ruangan dihitung **dari geometri poligon**, disandingkan otomatis dengan standar per jabatan. Data okupansi menunjukkan ruang kosong → **cegah pengadaan berlebih**. Nilai tambah terbesar setelah Wasdal |
| **Pelaporan / KIR / DBR** | `reports.py:2830-2880` KIR · `:2759-2768` DBR · `:2866` `cocok_ruangan_master` (string matching) | Ganti string-matching dengan join `ruangan_id`. Lampiran **peta sebaran BMN per zona/gedung**. Indikator "% aset dengan lokasi terverifikasi" |
| **Persuratan** | `persuratan_utils.py` | Nota dinas otomatis "konfirmasi keberadaan BMN" saat aset tak terdeteksi > 30 hari |
| **Master Pegawai** | `pegawai_utils.py` `STATUS_PEGAWAI` · `kartu_utils.py` + `kartu_uid_hashes` (`indexes.py:240-248`) | Sumber `pemangku_snapshot` custody jabatan. Pensiun/mutasi/meninggal → penutupan custody & serah terima. **[V] Infrastruktur identitas kartu RFID sudah setengah ada** |
| **Peta Aset & Kolaborasi** | `AssetMapFullView.jsx:505-513,526,547` (pola `L.Control` kustom sudah ada) · `peta_kolaborasi.py:412-451` `_titik_aset`, `:234-239` `TitikIn` | Layer poligon berlapis + level switcher + editor denah. **[V] Peta Kolaborasi belum menyimpan geometri poligon apa pun (hanya titik)** → perluas. **WAJIB filter agar posisi perangkat personal tidak pernah bocor** |

### 11.1 Bug yang ditemukan sambil riset — perbaiki di jalur ini

> **⚠️ KEBOCORAN LINTAS-SATKER [V]:** `backend/routes/reports.py:2848`
> ```python
> master = await db.ruangan.find({}, {"_id": 0}).to_list(5000)   # TANPA scope!
> ```
> Nama Penanggung Jawab Ruangan satker lain bisa tercetak di KIR satker ini bila kode/nama ruangan kebetulan sama. **Harus dibungkus `scope_query_field_satker(user, {})`.** Diperbaiki di Fase 1.

---

## BAGIAN 12 — KONVENSI REPO YANG WAJIB DIPATUHI

Diturunkan dari `.claude/skills/aman-dev/SKILL.md` dan survei kode.

1. **Pisahkan murni vs IO.** `backend/spasial_utils.py` (nol Mongo/IO, 100% teruji unit) + `backend/routes/spasial.py`. Meniru `ruangan_utils.py` ↔ `routes/ruangan.py`.
2. **Hierarki meniru `unit_kerja_utils.py`** — `validate_unit()` (anak wajib punya induk level di atasnya) dan `opsi_bertingkat()` (dropdown kaskade).
3. **Isolasi satker di 5 titik:** stempel `kode_satker` saat INSERT · `scope_query_field_satker` di LIST/agregasi · `pastikan_akses_dok_satker` di GET-by-id & stream berkas · guard di UPDATE/DELETE/transisi · **lookup silang antar-modul juga di-scope**. Keunikan kode per-satker ⇒ indeks unik **harus** menyertakan `kode_satker`.
4. **Satker Aktif (act-as) gratis** — `auth_utils.py:309-338` `_terapkan_satker_aktif` menyuntikkan `kode_satker` ke objek user, sehingga **seluruh mesin isolasi ikut tanpa menyentuh satu callsite pun**. Fitur baru tidak perlu kode khusus asalkan hanya memakai helper di atas.
5. **Auth gates:** `require_user` baca · `require_writer` tulis · `require_admin` kelola master · `require_super_admin` seluruh-DB. Berbagi denah publik → `create_map_token`/`require_map_token` (`auth_utils.py:185-209`). ⚠️ `require_admin` **BUKAN** gerbang satker.
6. **Impor besar lewat `jobs.py`** — `buat_job(..., kode_satker=kode_satker_user(user))` + `asyncio.create_task` + **set anti-GC** + `simpan_artifact` ke GridFS. Contoh yang ditiru: `exports.py:1375-1440`. **[V] 4 worker uvicorn → state in-memory RUSAK lintas worker.**
7. **Daftarkan koleksi di `backup_utils.RESET_KEEP_COLLECTIONS`** — kalau tidak, denah lenyap saat "Reset Hapus Semua".
8. **Indeks di `indexes.py`** dalam `create_indexes()`, `try/except` + fallback. Diulang oleh `routes/backup.py` pasca-restore.
9. **Cache:** daftarkan namespace `spasial` di **`_CACHE_LOCAL` DAN `_CACHE_TTL`** (`shared_utils.py:301-315`). Kunci **wajib** menyertakan `kode_satker_user(user) or '*'`. Redis opsional (`redis_utils.py` generation-counter, invalidasi O(1)) — deteksi lokasi **tidak boleh** bergantung Redis.
10. **Field aset baru lewat `asset_fields.py`** (4 langkah di header) + `models.py` + `exports.py` + `templates.py` + frontend `emptyForm`/`buildEditFormData`/`TEXT_FIELDS`/`SNAPSHOT_FIELDS`. Test registry akan menagih yang terlewat. Bonus: `compute_changes` membaca `SCALAR_FIELD_NAMES` → **field baru otomatis terlacak audit**.
11. **Semua tulis ber-OCC (`If-Match`) + `Idempotency-Key`**; render berat `await asyncio.to_thread(...)` + `@limiter.limit`.
12. **Offline-first:** deteksi ruangan harus jalan dari snapshot IndexedDB — poligon level ≤ gedung + ruangan lantai aktif ikut ke `offlineSnapshot.js`; PIP dijalankan **di klien** dengan fungsi murni yang sama (port JS). Hasil offline ditandai `ditetapkan:"otomatis_offline"` dan **diverifikasi ulang server** saat antrean disinkronkan.
13. **UI Bahasa Indonesia**, `data-testid` di elemen interaktif, tap-target ≥44 px di ≤1023 px, hindari `hover:bg-accent` polos, uji light **dan** dark.
14. **Satu fitur satu PR**; CHANGELOG wajib; CI hijau sebelum merge; merge ke main memicu auto-deploy.

### 12.1 Cache namespace `spasial`

| Cache | Kunci | TTL | Isi |
|---|---|---|---|
| Rantai per titik | `spasial:{satker\|'*'}:titik:{lon:.5f}:{lat:.5f}` | 300 s | rantai sampai gedung |
| Ruangan per titik+lantai | `spasial:{satker}:rg:{lantai_id}:{lon:.6f}:{lat:.6f}` | 300 s | daftar ruangan |
| Daftar lantai per gedung | `spasial:{satker}:lantai:{gedung_id}` | 1800 s | ordinal + label |
| Snapshot layer per level | `spasial:{satker}:layer:{ordinal}:{z}` | 600 s | GeoJSON ringkas |

**Kuantisasi kunci ke 5 desimal ≈ 1,1 m** — jauh di bawah akurasi GPS ponsel (3–10 m); untuk ruangan pakai 6 desimal ≈ 0,11 m.
**Invalidasi:** `INCR aman:gen:spasial` **satu kali** pada setiap create/update-geometri/delete/impor/perubahan level/perubahan denah. Naikkan `versi_denah` satker **hanya** untuk perubahan geometri — perubahan nama saja tetap invalidasi cache tapi **jangan** naikkan `versi_denah` (agar tidak memicu re-resolusi massal yang tak perlu).

### 12.2 Risiko operasional yang perlu dicatat pemilik

- **[F] Motor sudah lewat EOL fitur.** MongoDB mendeprekasi Motor 2025-05-14; **EOL 2026-05-14 (sudah lewat)**, perbaikan bug kritis saja hingga 2027-05-14. Repo memakai `motor==3.3.1` + `pymongo==4.5.0`. **Tidak menghalangi** fitur spasial (semua operator 2dsphere tersedia), tapi **jadwalkan migrasi ke PyMongo Async sebagai pekerjaan TERPISAH** — jangan digabung ke fitur ini.
- **Verifikasi versi server** dengan `await db.command("buildInfo")` sebelum implementasi: MultiPolygon/GeometryCollection butuh `2dsphereIndexVersion ≥ 2` (default v3 sejak MongoDB 3.2 ✓), **koleksi time-series butuh MongoDB ≥ 5.0** ([V] repo di 7.0.30 ✓).
- **[V] `yarn build` di VPS 8 GB** sudah butuh catatan swap (`DEPLOYMENT_GUIDE_HOSTINGER.md:604-606`). Menambah pustaka besar mempersempit margin → wajib lazy-load.
- **[V] `pip install` jalan tiap deploy** → argumen kuat menghindari pyproj (33 MB).

---

## BAGIAN 13 — BUTIR YANG MASIH PERLU VERIFIKASI

Sebelum masuk spesifikasi teknis final / seed produksi, cek ke sumber asli (mengikuti konvensi `docs/PUSTAKA-REGULASI-BMN.md`):

1. Nomor pasal definisi WP/SWP/Blok di Permen ATR/BPN 11/2021.
2. Isi perubahan **Permen ATR/BPN 6/2026** — apakah terminologi WP/SWP/Blok berubah.
3. **Penomoran WP 3 & 6–9 IKN** (inferensi dari urutan penyebutan) → Perpres 64/2022 Lampiran.
4. Aturan kode sub-blok berbasis Permendagri Kode & Data Wilayah Administrasi.
5. Daftar enum lengkap `Level.category` IMDF (`register.apple.com/resources/imdf/reference/categories`).
6. **Template `.gpkg` dinamis dibuka di QGIS asli** (belum diuji rendering).
7. Rasio kompresi time-series aktual — `db.iot_observasi.stats()` setelah 1 minggu produksi.
8. Coverage NB-IoT Telkomsel di lokasi IKN sebelum pengadaan tracker.
9. Harga tag/reader RFID & BLE 2026 (angka vendor — verifikasi ulang saat pengadaan).
10. Perilaku `backup_utils.collections_to_process()` terhadap koleksi time-series.

---

## BAGIAN 14 — RENCANA IMPLEMENTASI BERTAHAP

Tiap fase = **SATU PR yang bisa di-merge sendiri** dan memberi nilai nyata. CI hijau → auto-deploy.

| Fase | Judul | Ukuran | Bergantung |
|---|---|---|---|
| 1 | Fondasi geospasial aset: field `geo` + 2dsphere + perbaikan kebocoran KIR | kecil | — |
| 2 | Registry & pohon spasial (`spasial_level` + `spasial_node`) tanpa geometri | sedang | 1 |
| 3 | Geometri + peta berlapis baca-saja + deteksi lokasi otomatis | sedang | 2 |
| 4 | Menggambar di aplikasi (Geoman) + validasi topologi (shapely) | besar | 3 |
| 5 | Impor SHP/KML/KMZ/GeoJSON via job + pratinjau 2 tahap | besar | 4 |
| 6 | Ekspor berlapis + paket template QGIS & Google Earth | sedang | 5 |
| 7 | Indoor: lantai ordinal, georeferensi denah, level switcher, migrasi master `ruangan` | besar | 4 |
| 8 | Integrasi Wasdal: deteksi otomatis + temuan spasial baru | sedang | 7 |
| 9 | Kustodian temporal `asset_custody` + integrasi BAST/sertijab | sedang | 2 |
| 10 | Fondasi IoT: registry perangkat, ingest, idempotensi, DLQ, **privasi & DPIA** | besar | 3 |
| 11 | Scan QR sebagai observasi lokasi + rekonsiliasi opname | kecil | 10, 7 |
| 12 | Geofence engine + WebSocket live + temuan Wasdal berbasis lokasi | sedang | 10, 8 |
| 13 | Aplikasi pendamping GPS + deteksi lokasi offline di klien | sedang | 12 |
| 14 | Adapter Traccar + agen laptop + peta BSSID→ruangan | sedang | 12 |
| 15 | SBSK berbasis luas ruangan nyata + laporan peta sebaran | kecil | 7 |
| 16 | (Opsional) Gerbang RFID UHF + BLE tag kelas A | sedang | 12 |

**Mengapa Fase 1 bukan yang paling rumit:** ia menyentuh 3 berkas, nol dependensi baru, memperbaiki **kebocoran lintas-satker nyata**, dan memasang **indeks 2dsphere pertama di repo** — yang menjadi prasyarat teknis semua fase berikutnya. Nilai langsung: kueri peta per-bbox dan validasi koordinat Wasdal.

**Jalur paralel yang aman:** Fase 9 (kustodian) hanya bergantung pada Fase 2, sehingga bisa dikerjakan bersamaan dengan Fase 3–4 oleh orang berbeda. Fase 15 kecil dan bisa disisipkan kapan pun setelah Fase 7.

**Kunci pengurutan:** **privasi (Fase 10) datang SEBELUM pengumpulan GPS massal (Fase 13)** — degradasi presisi harus dipaksakan di ingest sejak hari pertama, bukan ditambal belakangan. Ini bukan preferensi, melainkan konsekuensi kebijakan #2 di §10.2: koordinat presisi **dibuang di ingest**, sehingga tidak ada jalan mundur bila datanya terlanjur tersimpan.

---

*Dokumen ini adalah sintesis lima dimensi riset. Semua klaim bertanda **[F]** memiliki URL sumber di laporan riset asal; **[V]** diverifikasi langsung di repo atau diuji di mesin ini; **[O]** adalah keputusan arsitek yang dapat diperdebatkan dengan bukti tandingan.*
