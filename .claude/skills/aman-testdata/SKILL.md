---
name: aman-testdata
description: Perkakas data uji AMAN — generator data sintetis BMN realistis (registry-driven/adaptif), profil edge-case untuk cakupan anomali, harness load/stress Locust, dan wiring CI/CD (generate dataset tepat sebelum uji). Gunakan saat butuh mengisi DB uji, menjalankan load/stress test, menambah cakupan kasus tepi, atau memutuskan batas rate-limit/kapasitas.
---

# Data Uji & Pengujian Beban AMAN

Perkakas untuk **mempercepat & memperkuat** siklus pengujian AMAN (inventarisasi
BMN OIKN/IKN). Semuanya di luar runtime aplikasi — aman dijalankan tanpa
memengaruhi server/route.

| Komponen | Lokasi | Fungsi |
|---|---|---|
| Generator sintetis | `backend/scripts/synthdata/` | Data BMN realistis, adaptif, beranomali |
| Harness load/stress | `scripts/loadtest/locustfile.py` | Simulasi satker: login→telusuri→tambah→laporan |
| Workflow CI/CD | `.github/workflows/loadtest.yml` | Generate dataset tepat sebelum uji (manual) |

## 1. Generator data sintetis (`backend/scripts/synthdata`)

Menghasilkan data BMN yang **terasa nyata** (konteks OIKN/IKN), **deterministik**
(repro), dan **bebas dependency** (pustaka standar Python — ringan untuk CI).

### CLI (dari direktori `backend`)

```bash
# 500 aset campuran (sebagian beranomali), seed tetap → keluaran repro
python -m scripts.synthdata --count 500 --profile mixed --seed 42

# Volume besar, hemat memori (satu record per baris)
python -m scripts.synthdata -n 100000 -p edge --format ndjson --out aset.ndjson

# Jenis lain
python -m scripts.synthdata --kind pegawai -n 200 --out pegawai.json
python -m scripts.synthdata --kind satker
python -m scripts.synthdata --kind kegiatan -n 20

# Isi activity_id agar siap di-POST ke /api/assets
python -m scripts.synthdata -n 1000 --activity-id <id-kegiatan> -o aset.ndjson
```

### Program

```python
from scripts.synthdata import (
    generate_assets, generate_pegawai, generate_satker, generate_activity,
)
aset = generate_assets(500, seed=42, profile="mixed", activity_id="keg-1")
```

### Profil

| Profil | Rasio anomali | Kegunaan |
|---|---|---|
| `normal` | 0% | Data "sehat" mendekati produksi — demo, uji fungsional |
| `mixed` | ~15% | Realistis untuk uji ketahanan — campuran sehat + anomali |
| `edge` | ~60% | Fokus kasus tepi — uji stabilitas ekstrem |

## 2. Adaptif (anti-drift) — kunci "test case tetap relevan"

Field aset diambil dari **registry** `asset_fields.ASSET_SCALAR_FIELDS` (sumber
kebenaran yang sama dengan model/ekspor/impor), dan pilihan sah
(kondisi/status/inventarisasi/stiker/klasifikasi) dari `shared_utils.VALID_*`.
Konsekuensinya: **saat fitur bertambah, data uji ikut menyesuaikan** tanpa edit
manual di banyak tempat.

Penjaganya: `backend/tests/unit/test_synthdata_generator.py` menagih tiap field
registry punya **strategi** di `generator.FIELD_STRATEGIES`. Menambah field aset
ke registry TANPA menambah strateginya akan **menggagalkan CI**, dengan pesan
yang menunjuk field mana yang perlu strategi.

**Alur saat menambah field aset baru:** setelah mengikuti langkah registry di
`asset_fields.py`, tambahkan satu baris strategi di
`backend/scripts/synthdata/generator.py` (`FIELD_STRATEGIES["<field>"] =
_s("<jenis>", lambda r, c: ...)`), dengan `jenis` ∈ {`teks`, `tanggal`,
`angka`, `koordinat`} agar anomali yang cocok bisa disuntikkan.

## 3. Anomali / edge-case — menambah cakupan & stabilitas

Profil `edge`/`mixed` menyuntik nilai "aneh tapi mungkin" yang sering lolos dari
data buatan tangan (lihat `profiles.py`): tanggal ekstrem (`9999-12-31` jebakan
`OverflowError`, tanggal mustahil), harga/koordinat di luar rentang,
unicode/emoji/RTL, string sangat panjang, serta pola **mirip**
SQLi/NoSQL/XSS/path-traversal (disimpan sebagai teks polos — menguji apakah
parser/ekspor/PDF/peta tetap kokoh). Semua tetap berupa string sehingga record
tetap lolos skema `AssetCreate` — yang diuji adalah **ketahanan logika**, bukan
validasi tipe.

Gunakan `edge` untuk: uji impor Excel/CSV, render laporan PDF/XLSX, parsing
tanggal/koordinat di peta, dan batas panjang field.

## 4. Harness load/stress (`scripts/loadtest`)

Locust mensimulasikan pengguna satker realistis (**baca ≫ tulis ≫ mahal**).
Lihat `scripts/loadtest/README.md` untuk detail. Ringkas:

```bash
pip install locust
cd backend && python -m scripts.synthdata -n 5000 -p mixed --format ndjson \
    -o ../scripts/loadtest/dataset.ndjson && cd ..
AMAN_ACTIVITY_ID=<id> AMAN_DATASET_FILE=scripts/loadtest/dataset.ndjson \
locust -f scripts/loadtest/locustfile.py --host https://staging... \
    --headless -u 200 -r 20 -t 5m --csv hasil
```

> ⚠️ Hanya lingkungan **UJI/STAGING**. Uji-tulis membuat data nyata.

### Menentukan batas rate-limit dari hasil (metode)

1. Naikkan `-u` bertahap (50→100→200→400) sampai **p95 latensi** melonjak atau
   **failure ratio > 1%** → itu **titik jenuh** (req/dtk maksimum).
2. Perkirakan pengguna aktif serempak per satker; bagi throughput jenuh dengan
   angka itu → **anggaran request per pengguna**.
3. Setel batas per-endpoint (`backend/routes/*`) di bawah titik jenuh dengan
   margin. Rate-limiter sudah **per-USER + storage bersama lintas-worker**
   (CHANGELOG #559), jadi batas konsisten walau 2 worker uvicorn.

## 5. Efisiensi CI/CD — generate tepat sebelum uji

Workflow `.github/workflows/loadtest.yml` (manual `workflow_dispatch`,
**tidak** jalan otomatis tiap PR) menghasilkan dataset **tepat sebelum** uji lalu
menjalankan Locust — dataset tak disimpan di repo, siklus feedback cepat.

- Tanpa input `host` → **dry-run**: generate dataset + validasi locustfile.
  Selalu bisa dijalankan sebagai pemeriksaan sehat (tanpa secrets/staging).
- Dengan `host` + secrets `LOADTEST_USERNAME`/`LOADTEST_PASSWORD`
  (+opsional `LOADTEST_ACTIVITY_ID`) → uji beban live, hasil CSV jadi artifact.

Langkah generate **tak** memasang seluruh `requirements.txt`: generator hanya
butuh pustaka standar + `asset_fields` (import `shared_utils` opsional dengan
fallback), jadi cepat di runner.

Pola ini bisa diadopsi untuk suite lain: jadikan generator sebagai langkah
"seed" bagi pengujian integrasi yang butuh data besar.

## Jaminan & batasan

- **Deterministik**: `seed` sama → keluaran identik (aman untuk CI & repro bug).
- **Valid skema**: tiap record (semua profil) lolos `AssetCreate`.
- **Fiktif**: semua nilai buatan — bukan data BMN sungguhan; kode/NUP/NIP
  berpola realistis tapi acak.
- **Bukan runtime**: tak di-import server/route; ubah bebas tanpa risiko produksi.

## Verifikasi perkakas ini sendiri

```bash
python -m pytest backend/tests/unit/test_synthdata_generator.py -q
python -m compileall backend/scripts scripts/loadtest
python -m py_compile scripts/loadtest/locustfile.py
```
