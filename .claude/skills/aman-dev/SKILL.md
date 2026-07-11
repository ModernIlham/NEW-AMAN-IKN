---
name: aman-dev
description: Panduan pengembangan bertahap aplikasi AMAN (inventarisasi BMN) — peta arsitektur, konvensi wajib, pipeline ship per fitur (verifikasi → PR → CI → merge → auto-deploy), jebakan umum, dan checklist pemilik proyek. Gunakan saat mengembangkan fitur apa pun di repo ini.
---

# Pengembangan AMAN — Proses Baku per Fitur

Aplikasi: **AMAN** — inventarisasi BMN offline-first (FastAPI + Motor/MongoDB
+ React CRA/craco + Tailwind/shadcn). Arah produk: platform siklus penuh
pengelolaan BMN — baca `docs/MASTERPLAN-SIKLUS-BMN.md` sebelum menambah modul.

## Peta repo (titik sentuh tersering)

| Area | Lokasi | Catatan |
|---|---|---|
| Registry field aset | `backend/asset_fields.py` | SATU sumber kebenaran 42 field skalar → proyeksi list, PATCH, batch, CSV, impor, audit. Tambah field = ikuti panduan di header file; test anti-drift menagih semua turunan |
| Route API | `backend/routes/*.py` | assets, exports (geo/xlsx/pdf), reports (ReportLab), activities, auth, backup |
| Laporan PDF | `backend/routes/reports.py` | Helper wajib dipakai: `_kop_surat_flowables`, `_activity_identity`, `_identity_table`, `_fmt_tanggal_id`, `_signature_block` ("Kuasa Pengguna Barang") |
| Test unit | `backend/tests/unit/` | Jalan tanpa Mongo; registry test menjaga drift |
| Halaman utama | `frontend/src/pages/DashboardPage.jsx` | Mode Dashboard/Inventarisasi, antrean simpan optimistis, peta, filter |
| Form aset | `frontend/src/components/assets/AssetForm.jsx` | Intent `camera:*`, validasi, photo_ops |
| Kamera lapangan | `frontend/src/components/assets/FullCameraSheet.jsx` | Watermark, flash/brightness, scan QR, panel Edit Info |
| Lembar edit cepat | `frontend/src/components/assets/InventoryFieldSheet.jsx` | Ekspor konstanta opsi — jangan duplikasi daftar opsi di tempat lain |
| Peta aset | `frontend/src/components/assets/AssetMapFullView.jsx` | Lembar dalam halaman; ikut filter aktif; ekspor geo |
| Offline | `frontend/src/lib/offlineSnapshot.js`, `hooks/useOptimisticQueue*` | Snapshot IndexedDB + antrean simpan persisten |
| Registry modul siklus | `frontend/src/lib/bmnModules.js` | Beranda Modul + status aktif/segera; modul baru daftar di sini |
| CI/CD | `.github/workflows/ci.yml`, `deploy.yml`, `scripts/deploy_vps.sh` | CI tiap PR; auto-deploy ke VPS saat merge ke main |

## Konvensi WAJIB

1. **Seluruh teks UI, commit, dan PR berbahasa Indonesia.**
2. **Field aset baru lewat registry** (`asset_fields.py`) + models.py +
   exports/templates + frontend (emptyForm/buildEditFormData/TEXT_FIELDS/
   SNAPSHOT_FIELDS) — test registry akan menagih yang terlewat.
3. **Semua tulis ber-OCC** (version/If-Match) + Idempotency-Key; jangan buat
   jalur tulis baru yang melewatinya.
4. **Fitur lapangan wajib jalan offline** (snapshot + antrean); fitur kantor
   boleh online-only.
5. **Laporan**: pakai helper desain reports.py; tanggal gaya Indonesia; tanpa
   data dummy; smoke-test dengan harness FakeDB sebelum ship.
6. **Jangan perkecil tombol** di ≤1023px — aturan tap-target 44px global di
   `index.css`. Elemen kecil yang membengkak → beri `min-w-0 min-h-0`.
   (Riwayat lengkap: header CHANGELOG.md.)
7. **Overlay di atas kamera** (z-[120]): pakai elemen native (select, bukan
   Radix portal) di dalam FullCameraSheet.
8. **Data uji**: `data-testid` untuk elemen interaktif baru.
9. **Modul baru** ikut prinsip integrasi Bab 5 masterplan: satu identitas
   aset, satu kodefikasi, transaksi = jurnal, dokumen sumber = simpul,
   approval = gerbang, offline-first, registry anti-drift.

## Pipeline ship per fitur (urutan eksak)

```bash
# 1. Pastikan branch bersih di atas main terbaru
git fetch origin main && git checkout -B <branch-kerja> origin/main

# 2. Bangun fitur (kecil — satu fitur satu PR)

# 3. Verifikasi lokal
cd backend && python -m pytest tests/unit -q          # unit test
cd frontend && npx eslint <file-berubah> --max-warnings=0
CI=false yarn build                                    # build produksi

# 4. Commit (Indonesia) + push
git push -u origin <branch-kerja>

# 5. PR DRAFT → tunggu CI hijau (check-runs) → tandai ready → SQUASH merge
# 6. Merge ke main memicu deploy.yml → pantau sampai "Deploy selesai"
# 7. Reset branch kerja ke main untuk fitur berikutnya
git fetch origin main && git checkout -B <branch-kerja> origin/main
git push --force-with-lease -u origin <branch-kerja>
```

Definisi Selesai: CI hijau · terdeploy · UI Indonesia · offline OK (fitur
lapangan) · CHANGELOG terisi (entri `[#PR]`) · tanpa regresi lint/test.

**Dokumentasi ikut PR yang sama**: CHANGELOG selalu; README + halaman PRD
(`frontend/src/pages/InfoPage.jsx`) bila fitur besar; `bmnModules.js` bila
status modul berubah.

## Jebakan yang sudah pernah menggigit

- `yarn.lock` harus di-regenerate bila menambah dependency (CI pakai
  `--frozen-lockfile`).
- Deploy gagal `Permission denied` padahal kunci benar → cek
  `authorized_keys` baris menempel (butuh newline sebelum append).
- Re-run workflow lama ≠ menjalankan workflow baru — pakai "Run workflow".
- Test laporan: `scripts` smoke FakeDB di scratchpad sesi lama — pola:
  render semua laporan ke PDF via pypdfium2 tanpa Mongo.
- Radix Select di bawah overlay kamera tidak muncul (z-index portal).
- Tanggal `9999-12-31` → `OverflowError` pada strptime: tangkap
  `(ValueError, OverflowError)`.
- Efek refetch harus menyertakan SEMUA filter di deps — filter baru yang
  lupa didaftarkan tidak memicu muat ulang.

## Checklist pemilik proyek (setingan untuk kesuksesan bertahap)

Sekali pasang:
- [x] Secrets GitHub Actions: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`
      (+opsional `VPS_PORT`) — kunci privat HANYA di secret, jangan pernah
      ditempel di chat/tempat lain; rotasi bila bocor.
- [ ] Branch protection `main`: wajib CI hijau sebelum merge (Settings →
      Branches → Require status checks).
- [ ] Backup MongoDB terjadwal di VPS (cron `mongodump` harian + salin ke
      luar server mingguan) — fitur Backup aplikasi bukan pengganti backup
      infrastruktur.
- [ ] Pantau kapasitas disk VPS (foto GridFS tumbuh); siapkan alarm 80%.

Tiap siklus fitur:
- [ ] Tulis permintaan fitur sekecil mungkin & satu per satu — "satu fitur,
      satu PR" membuat rollback dan review mudah.
- [ ] Setelah deploy: uji singkat di HP lapangan (online + offline + kembali
      online) sebelum minta fitur berikutnya.
- [ ] Sebelum modul baru dibangun: sepakati kontraknya di
      `docs/MASTERPLAN-SIKLUS-BMN.md` (data apa dibaca/ditulis dari mana).
- [ ] Simpan file impor/ekspor contoh (Excel SIMAN dsb.) — bahan uji
      kompatibilitas saat modul pembukuan/rekonsiliasi dibangun.
