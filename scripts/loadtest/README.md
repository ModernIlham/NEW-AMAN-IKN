# Load / Stress Test AMAN (Locust)

Perkakas pengukur **throughput maksimum** & **titik jenuh** aplikasi AMAN,
memakai data sintetis dari `backend/scripts/synthdata`. Dipakai untuk
mengambil keputusan berbasis-bukti soal batas rate-limit, jumlah worker
uvicorn, dan kapasitas VPS.

> ⚠️ **Hanya untuk lingkungan UJI/STAGING.** Jangan arahkan ke produksi —
> uji tulis (`POST /assets`) membuat data nyata dan uji beban dapat menjenuhkan
> server.

## Pasang

```bash
pip install locust
```

## Alur singkat (generate → uji)

```bash
# 1. Hasilkan dataset body aset realistis (dari direktori backend)
cd backend
python -m scripts.synthdata -n 5000 -p mixed --format ndjson \
    -o ../scripts/loadtest/dataset.ndjson
cd ..

# 2. Jalankan Locust (200 pengguna, ramp 20/dtk, 5 menit, headless)
AMAN_USERNAME=admin AMAN_PASSWORD=rahasia \
AMAN_ACTIVITY_ID=<id-kegiatan-uji> \
AMAN_DATASET_FILE=scripts/loadtest/dataset.ndjson \
locust -f scripts/loadtest/locustfile.py \
    --host https://staging.example.go.id \
    --headless -u 200 -r 20 -t 5m --csv hasil
```

Hasil ringkas tertulis ke `hasil_stats.csv` / `hasil_failures.csv`. Untuk UI
interaktif, jalankan tanpa `--headless` lalu buka `http://localhost:8089`.

## Environment

| Variabel | Arti | Default |
|---|---|---|
| `AMAN_USERNAME` / `AMAN_PASSWORD` | kredensial login | `admin` / `admin123` (DEV) |
| `AMAN_ACTIVITY_ID` | id kegiatan untuk uji-tulis; **kosong → baca saja** | `""` |
| `AMAN_DATASET_FILE` | NDJSON body aset (dari generator) | body minimal inline |
| `AMAN_ENABLE_HEAVY` | `1` → aktifkan tugas mahal (laporan/ekspor) | `0` |
| `AMAN_THINK_MIN` / `AMAN_THINK_MAX` | jeda "berpikir" pengguna (dtk) | `1` / `5` |

## Bobot perilaku (per pengguna)

Mendekati pemakaian lapangan: **baca ≫ tulis ≫ mahal**.

| Tugas | Endpoint | Bobot |
|---|---|---|
| Telusuri daftar | `GET /api/assets` | 10 |
| Statistik | `GET /api/assets/stats` | 4 |
| Analitik | `GET /api/assets/analytics` | 3 |
| Snapshot offline | `GET /api/assets/offline-snapshot` | 2 |
| Tambah aset | `POST /api/assets` | 1 (bila `AMAN_ACTIVITY_ID` diset) |
| Laporan mahal | — | 1 (bila `AMAN_ENABLE_HEAVY=1`) |

## Membaca hasil → keputusan rate-limit

1. Naikkan `-u` bertahap (50 → 100 → 200 → 400) sampai **p95 latensi** naik
   tajam atau **failure ratio > 1%** — itulah titik jenuh.
2. Bagi throughput jenuh (req/dtk) dengan perkiraan jumlah pengguna aktif
   serempak per satker untuk memperoleh anggaran **request per pengguna**.
3. Setel batas per-endpoint (auth/OTP, laporan, ekspor, TTD, pegawai) di
   `backend/routes/*` dengan margin di bawah titik jenuh. Rate-limiter sudah
   per-USER + storage bersama lintas-worker (lihat CHANGELOG #559), jadi batas
   berlaku konsisten walau ada 2 worker uvicorn.

Lihat pula skill `.claude/skills/aman-testdata/SKILL.md` untuk panduan
end-to-end (data sintetis → uji beban → wiring CI/CD).
