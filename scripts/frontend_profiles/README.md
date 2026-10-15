# Profil browser lokal frontend

Fixture memakai modul aplikasi asli untuk snapshot/pagination dan template worker asli untuk lifecycle. Seluruh akun/ID/data dibuat sintetis; tidak ada akses produksi. Hasil contoh terdapat pada `docs/bukti-optimasi/OPT-{19,20,21}`. Jalankan dari root repo setelah dependensi frontend, Python `requests`/`websockets`, dan Chromium tersedia. Backend tidak diperlukan.

Jalankan Chromium terisolasi, memakai port/profil yang tidak sedang digunakan:

```sh
chromium --headless --no-sandbox --disable-gpu --disable-dev-shm-usage --disable-background-networking --no-first-run --enable-precise-memory-info --user-data-dir=/tmp/aman-frontend-profile --remote-debugging-port=9224 --remote-allow-origins=http://localhost:9224 about:blank
```

Snapshot (native IndexedDB 1k/10k/50k, 4KiB thumbnail/baris; mengosongkan aktivitas fixture saja):

```sh
NODE_ENV=production node scripts/frontend_profiles/build.cjs snapshot .aman/frontend-profile
python -m http.server 8787 --bind 127.0.0.1 --directory .aman/frontend-profile
# Terminal lain:
python scripts/frontend_profiles/snapshot.py --out .aman/frontend-profile
```

Jendela mobile/galeri, 200 halaman maju/mundur (memerlukan `frontend/build/static/css/main.*.css` hasil build agar geometri benar):

```sh
NODE_ENV=production node scripts/frontend_profiles/build.cjs window .aman/frontend-profile
# Gunakan server HTTP 8787 di atas, kemudian:
python scripts/frontend_profiles/window.py --out .aman/frontend-profile
```

Lifecycle native worker dua tab/dua rilis, HTTP disconnect dan quota:

```sh
python scripts/frontend_profiles/sw_server.py --out .aman/sw-profile
# Terminal lain:
python scripts/frontend_profiles/sw.py --out .aman/sw-profile
```

Runner worker membersihkan storage **hanya origin fixture localhost:8788**, menutup tab fixture sebelumnya, lalu memeriksa antrean/draf sintetis tidak dihapus worker. Jangan arahkan runner ke origin aplikasi yang memiliki data kerja. `--cdp`/`--port` dapat diganti pada pasangan server/runner. Hentikan proses Chromium/server sendiri setelah selesai. Angka heap berasal dari `performance.memory` dan GC CDP, bukan peak RSS; batas cache adalah estimasi isi, dengan pengecualian halaman yang sedang terlihat sebagaimana didokumentasikan.
