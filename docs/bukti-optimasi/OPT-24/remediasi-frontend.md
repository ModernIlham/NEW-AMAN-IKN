# Remediasi dependency frontend dalam arsitektur CRA

Status: kandidat telah diterapkan pada source checkout dan seluruh gerbang lokal lulus; [594 berkas source/config cocok](frontend-remediasi-source.json) dengan kandidat yang diuji. Ini belum menjadi bukti CI atau rilis produksi. Audit baseline tetap disimpan utuh di `frontend-audit.json`.

## Perubahan yang dipilih

- Axios `1.13.2 → 1.20.0`; batas minimum langsung `^1.20.0`.
- React Router/DOM `7.11.0 → 7.18.4`; batas minimum DOM `^7.18.4`, tetap declarative BrowserRouter.
- ESLint dan `@eslint/js` `9.23.0 → 9.39.5`; pembaruan pemanggil ini memakai plugin-kit `^0.4.1` secara sah, sedangkan CRA tetap memakai ESLint 8 tersendiri.
- Resolusi ulang entri lock paket yang memiliki advisory memakai rentang pemanggil aslinya. Tidak ada `resolutions`, pemaksaan mayor, pemodifikasian isi `node_modules`, atau pergantian bundler.
- Patch kritis tooling: shell-quote `1.12.0`, websocket-driver `0.7.5`, proxy-addr `2.0.8`. TerserWebpackPlugin `5.6.1` menghapus dependency serialize-javascript miliknya. Express `4.22.3` memakai qs `~6.16.0`, sehingga qs `6.16.1` masuk tanpa override.
- Mapper **khusus Jest 27** untuk `react-router/dom` mengarah ke export CJS resmi versi terpasang. Webpack produksi tetap meresolusi export paket normal.

Salinan source dan node_modules terpisah dibuat di `/workspace/.aman/frontend-security-private/frontend`; instalasi maupun pengujian kandidat tidak mengubah node_modules checkout utama. Node validasi `22.23.2`, Yarn `1.22.22`; engine/peer perubahan menerima Node 22. Pemeriksaan semver juga menerima Node 20.20, tetapi itu bukan rekomendasi lifecycle Node atau pengganti preflight runtime produksi.

## Makna angka audit

Hasil Yarn audit adalah **jumlah kemunculan advisory**, bukan jumlah kerentanan yang dapat dieksploitasi atau jumlah jalur unik. Baseline: 501 kemunculan, 146 GHSA berbeda, 48 nama paket. Kandidat: **49 kemunculan, 25 GHSA berbeda, 13 nama paket; kritis 0** (rendah 3, sedang 25, tinggi 21). NDJSON kandidat berisi 37 string jalur dependency unik. Audit memuat paket build/dev yang berada di `dependencies` CRA; flag `dev:false` dari Yarn bukan bukti bahwa paket tersebut masuk bundle browser.

Audit kandidat tetap mengandung temuan. Penurunan jumlah tidak menggantikan penelusuran pemakaian atau bukti browser. [Audit ringkas](frontend-audit-remediasi.json) mempertahankan GHSA, rentang rentan/perbaikan vendor, versi terpasang, dan jalur dependency agar bisa diaudit ulang.

## Batas sisa per paket

| Paket terpasang | Kendala vendor/pemanggil saat ini | Langkah pemisah |
|---|---|---|
| @tootallnate/once 1.1.2 | http-proxy-agent 4.0.1 meminta major `1`; perbaikan ≥2.0.1 | Migrasi cohort Jest/jsdom/proxy-agent, bukan override global |
| braces 3.0.3 | Audit vendor tidak menerbitkan versi perbaikan (`<0.0.0`) | Pantau patch vendor; batasi build pada sumber tepercaya |
| node-forge 1.4.0 | Satu advisory tetap tanpa versi perbaikan vendor | TLS development selfsigned; pantau vendor atau ganti cohort dev-server |
| nth-check 1.0.2 | css-select/SVGO 1 meminta major 1; perbaikan ≥2.0.1 | Migrasi SVGR/SVGO bersama |
| postcss 7.0.39 | resolve-url-loader 4.0.0 meminta `^7.0.35`; loader 5 memakai PostCSS 8 | Migrasi loader/CSS pipeline, pertahankan resolusi source map |
| postcss-selector-parser 6.1.4 | Tailwind 3/postcss-nested 6/postcss-calc 8/stylehacks 5 meminta major 6; perbaikan ≥7.1.6 | Migrasi cohort CSS/Tailwind, uji hasil CSS/tema |
| serialize-javascript 4.0.0/6.0.2 | rollup-plugin-terser 7.0.2 meminta `^4.0.0`; CSSMinimizerPlugin 3.4.1 meminta `^6.0.0`; perbaikan ≥7.0.5 | Migrasi Workbox/Rollup dan CSS minimizer bersama |
| sprintf-js 1.0.3 | Advisory tidak menyediakan versi perbaikan vendor; rantai argparse/js-yaml lama | Pantau vendor dan migrasi cohort pemanggil YAML/CLI |
| svgo 1.3.2 | @svgr/plugin-svgo 5.5.0 meminta `^1.2.2` dan memakai API SVGO 1 | Migrasi SVGR/SVGO bersama; jangan paksa API major 2 |
| underscore 1.13.6 | jsonpath terbaru 1.3.0 mengunci **tepat** 1.13.6; patch ≥1.13.8 di luar kontrak exact itu | Perbarui/ganti pemanggil bfj/jsonpath sebagai perubahan teruji sendiri |
| uuid 8.3.2 | SockJS terbaru 0.3.24 meminta `^8.3.2`; perbaikan ≥11.1.1 | Migrasi cohort SockJS/dev-server, uji koneksi HMR |
| webpack-dev-middleware 5.3.4 | webpack-dev-server 4 meminta major 5; perbaikan ≥7.4.6 | Migrasi dev-server yang didukung bundler |
| webpack-dev-server 4.15.2 | CRA 5 meminta major 4; perbaikan ≥5.2.6 | Spike migrasi toolchain terpisah dengan bukti bundle, SW, alias, env, dan Jest |

Versi pemanggil kompatibel terakhir diperiksa langsung dari metadata registry, termasuk Express 4.22.3, CSSMinimizerPlugin 3.4.1, resolve-url-loader 4.0.0, Tailwind 3.4.19, Workbox 6.6.1, dan rollup-plugin-terser 7.0.2. Pemaksaan mayor melewati kontrak paket bukan perbaikan yang dibuktikan cohort ini. Sisa advisory menjadi pemicu nyata spike toolchain pada OPT-24; keputusan mempertahankan CRA sekarang bersifat terbatas, bukan penundaan tanpa batas.

## Penelusuran dan uji

Axios menangani permintaan JWT/satker, header audit, OCC/idempotency, pembatalan baca, unggahan FormData, dan unduhan blob. Router dipakai sebagai BrowserRouter declarative dengan redirect internal; aplikasi tidak memakai SSR, Framework Mode, RSC, atau server Router. Pengujian baru menggunakan **adapter XHR Axios asli melalui HTTP localhost**, bukan mock Axios, untuk JSON/header/satker saat request, config antrean, boundary multipart/file, abort yang dikenali, blob/progres/403. Pengujian Router asli membuktikan redirect memakai replace (panjang history tetap), navigasi maju, dan riwayat back. Uji aplikasi yang sudah ada melengkapi penjaga antrean/baca/form/batch/media.

Peninjau baru yang hanya membaca kandidat memverifikasi 1.888 selector lock memenuhi rentang pemanggil, 76 selector lama berubah tanpa perubahan major, tidak ada override, engine/peer sesuai, serta tidak menemukan pembaruan pemanggil kompatibel lain untuk 25 GHSA tersisa. [Verifikasi lock](frontend-remediasi-lock.json) dan [hash sumber](frontend-remediasi-hashes.json) mencatat kandidat tepat yang diperiksa.


## Gerbang final lokal

[Ringkasan mesin](frontend-remediasi-gates.json) mencatat hasil dan percobaan awal:

- Frozen install tanpa engine bypass lulus; hash lock final `c029992a16b988f0778cf1f5dc4b9cdd3ddbbbbb53adb8595de6eef8622ee640`.
- Jest lengkap **217 suite / 2.308 tes lulus**, 172,925 detik, dijalankan berurutan tanpa build/browser bersamaan. Lint **0 error / 7 warning baseline**, 7,79 detik.
- Build produksi lulus 172,32 detik saat bersamaan dengan percobaan Jest awal; ini bukan pembanding performa. Build konfigurasi fixture browser tersendiri lulus 94,72 detik.
- [Inventaris 96 source map JS](frontend-remediasi-bundle.json) tidak mengidentifikasi 13 paket sisa sebagai sumber node_modules; kode vendor inline tanpa pemetaan tetap batas pemeriksaan ini.
- [Chromium asli](frontend-remediasi-browser.json) lulus **16 pemeriksaan / 55,95 detik**, pada 320/360/768/1440 × terang/gelap tanpa overflow. Thumbnail/fullpreview terdekode; save/batch dibaca ulang; snapshot/reload offline bekerja. Simpanan pending tidak mengubah backend, reconnect menaikkan versi 4→5 sekali, media bertahan, dan reconnect kedua tidak replay. [Runner](frontend-remediasi-runner.json) selesai dengan cleanup_errors kosong.

Percobaan Jest pertama bersamaan dengan build dingin meluluskan 216 suite / 2.307 tes; satu uji form melewati timeout 5 detik tanpa kegagalan assertion. Uji form+transport ulang tanpa build lulus 7 tes. Tidak ada timeout atau assertion yang dilonggarkan; seluruh suite kemudian lulus berurutan sebagaimana dicatat di atas.

Periksa lock terhadap baseline yang hash-nya sesuai bukti, kemudian ulangi gerbang pada Node 22:

```bash
node docs/bukti-optimasi/OPT-24/periksa-lock-frontend.cjs /path/to/baseline/frontend frontend
corepack yarn --cwd frontend install --frozen-lockfile --non-interactive
CI=true corepack yarn --cwd frontend test --watch=false --runInBand
corepack yarn --cwd frontend lint
CI=false corepack yarn --cwd frontend build
```

Browser menggunakan build kandidat privat yang dikompilasi untuk API fixture 18137, melalui wrapper `scripts/uji_browser_ci.py --skip-build --build-dir ... --api-port 18137 --frontend-port 18837`, bukan build checkout lama. Seluruh data/database/filesystem fixture sintetis dan dibersihkan. Bukti deployment dan SHA final ditambahkan oleh gerbang rilis utama; hasil lokal tidak menyatakan produksi sudah berubah.
