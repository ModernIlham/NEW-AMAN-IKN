# Advisory frontend: baseline dan remediasi

Kandidat lokal memperbarui Axios `1.13.2 → 1.20.0`, React Router/DOM
`7.11.0 → 7.18.4`, ESLint `9.23.0 → 9.39.5`, dan paket tooling yang dapat
berubah tanpa melanggar rentang pemanggil. Shell-quote, websocket-driver, dan
proxy-addr kini memakai versi perbaikan; tidak ada temuan kritis pada audit
kandidat. Tidak ada override mayor atau pergantian bundler.

Audit turun dari **501 menjadi 49 kemunculan advisory**, dan **146 menjadi 25
GHSA berbeda**. Sisa audit: 3 rendah, 25 sedang, 21 tinggi, **0 kritis**, pada
13 nama paket. Ini bukan klaim seluruh website bebas kerentanan. Hitungan
kemunculan Yarn bukan jumlah jalur dependency unik atau eksploitasi yang
terbukti. Rincian versi/rentang/jalur vendor:
[frontend-audit-remediasi.json](frontend-audit-remediasi.json).

Status kandidat, seluruh pemeriksaan, batas sisa per paket dan langkah lanjutan:
[remediasi-frontend.md](remediasi-frontend.md). Browser asli telah lulus 16
pemeriksaan, termasuk antrean offline dan media yang benar-benar terdekode;
CI/rilis akhir tetap dicatat oleh gerbang rilis utama. Bukti ini tidak mengganti
bukti deployment.

## Keterjangkauan kandidat

Source map dari 96 berkas JavaScript build produksi mengidentifikasi Axios dan
Router yang diperbarui. Tiga belas nama paket tersisa tidak muncul sebagai
sumber `node_modules` pada pemeriksaan tersebut:
[frontend-remediasi-bundle.json](frontend-remediasi-bundle.json). Pemeriksaan
nama sumber ini tidak menjamin keamanan kode vendor inline tanpa pemetaan.

Sisa dependency berada pada rantai CSS/SVG build, minifier, Jest/jsdom, dan
CRA dev-server. Nginx produksi melayani build statis; `yarn start` menjalankan
server pengembangan berbeda dengan prasyarat serangan tersendiri. Paket
`react-scripts` berada di `dependencies`, sehingga `dev:false` atau
`audit --production` tidak membuktikan bahwa paket masuk runtime browser.

Semua selector lock kandidat memenuhi rentang pemanggil; perubahan pada 76
selector lama tidak menaikkan major. Pembaruan Express 4.22.3 mengizinkan qs
6.16.1 secara normal. Perbaikan yang masih menuntut major/exact override atau
belum diterbitkan vendor dijelaskan per paket, bukan dianggap selesai.
Pemicu keamanan untuk spike toolchain lanjutan sudah nyata; penerapan Vite
memerlukan pekerjaan terpisah yang mempertahankan alias, env, Jest, CSS,
lazy chunk, manifest/SRI, worker offline, dan kontrak deploy.

## Baseline yang dipertahankan

Audit awal Yarn Classic 1.22.22 pada 15 Oktober 2026, lock SHA256
`564de6edb292337ffe01fbdac75ad222c95cda40a5dccded75ddfcf076cf8db1`,
berakhir dengan exit **30**: 501 kemunculan (27 low, 174 moderate, 295 high,
5 critical), 166 record berbeda menurut versi/advisory, 48 nama paket,
146 GHSA berbeda. Bukti awal tidak ditimpa:
[frontend-audit.json](frontend-audit.json),
[frontend-audit-classification.json](frontend-audit-classification.json).

Penelusuran baseline menemukan:

- Axios browser memakai konfigurasi internal, token/satker, upload/download dan
  abort; tidak ditemukan pemakaian HTTP2/proxy Node atau config utuh dari input
  pengguna. Prasyarat gadget prototype/config browser tetap perlu dievaluasi
  bila alur input berubah.
- Router dipakai sebagai BrowserRouter declarative dengan Navigate literal
  `/` dan `/login`; tidak ditemukan Framework Mode, SSR/RSC atau server action.
- Critical shell-quote/websocket-driver/proxy-addr berasal dari tooling CRA;
  ketiganya kini diperbaiki pada kandidat, meskipun belum dibuktikan sebagai
  eksploitasi nginx/browser produksi.
- Lodash pada bundle baseline berasal dari Geoman 4.18.1; Lodash 4.17.21 yang
  dilaporkan audit merupakan dependency tooling dan ikut diperbarui.

Tidak ditemukan rantai source → sink yang membuktikan high/critical runtime
browser pada penelusuran terbatas ini. Ini bukan audit keamanan aplikasi penuh
atau jaminan tidak ada rantai prototype pollution. **Nol advisory Python pada
OPT-24 hanya berlaku bagi lock Python yang diperiksa**, bukan frontend ini.
