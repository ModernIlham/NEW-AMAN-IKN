# OPT-24 — Kelompok perbaikan keamanan dependency

Angka nol berikut khusus dependency **Python**. Inventaris Yarn frontend masih
memiliki advisory dan klasifikasi keterjangkauan tersendiri pada
[frontend-security.md](frontend-security.md); tidak ada klaim seluruh website
bebas advisory.

Audit 15 Oktober 2026 atas baseline menemukan **167 advisory pada 24 paket**.
Pin yang dapat direproduksi saja tidak cukup untuk merilis decoder media,
multipart, dan parser HTTP lama yang diketahui rentan. Bukti baseline lengkap:
[security-baseline-audit.json](security-baseline-audit.json).

Kandidat akhir menyelesaikan seluruh temuan pada dependency runtime yang
ter-resolve: **137 paket, nol advisory dikenal, tanpa ignore** menurut
pip-audit 2.9.0 / PyPI vulnerability service. Bukti hasil:
[security-audit.json](security-audit.json). Audit adalah snapshot informasi
vendor saat pemeriksaan; ulangi saat rilis dan secara terjadwal.

| Batas kompatibilitas | Pin akhir yang berubah |
|---|---|
| HTTP/ASGI dan auth | FastAPI 0.143.1, Starlette 1.8.0, AnyIO 4.14.2, PyJWT 2.15.1, python-multipart 0.0.32 |
| Mongo melalui API Motor | Motor 3.7.1, PyMongo 4.19.0 |
| Media/PDF dan enkripsi | Pillow 12.3.0, pypdf 6.20.1, WeasyPrint 70.0, cryptography 50.0.2 |
| Transport/provider transitif | aiohttp 3.14.3, requests 2.33.0, urllib3 2.8.0, idna 3.15, multidict 6.9.1, pyasn1 0.6.4 |
| Paket opsional/tool pendukung yang tetap terpasang | fsspec 2026.6.0, httplib2 0.32.0, oauthlib 4.0.0, Pygments 2.20.0, python-dotenv 1.2.2 |

Versi dipilih untuk menutup advisory yang ditemukan dan memenuhi metadata
kompatibilitas, bukan menaikkan setiap paket ke latest. Metadata vendor yang
diperiksa disimpan pada [security-core-metadata.json](security-core-metadata.json)
dan [security-metadata.json](security-metadata.json). Python 3.11 diperlukan oleh
Starlette/PyMongo baru dan sudah menjadi baseline CI. Motor tetap menjadi API
aplikasi; migrasi native async memakai adapter terpisah sebelum 31 Maret 2027.

Jalur yang menerima input tidak tepercaya mencakup form multipart, upload foto
dan PDF, parser/merge PDF laporan, serta token autentikasi. Guard ukuran/foto
tetap diperlukan setelah update library. Seluruh library terdampak yang masih
terpasang sudah dinaikkan; tidak ada pengecualian audit berdasarkan dugaan bahwa
sebuah jalur jarang dipakai. SDK litellm/python-jose/ecdsa dihapus hanya sesudah
inventaris AST + import dinamis + reverse dependency membuktikannya tidak dipakai.
PyPDF2 dihapus setelah consumer PDF dimigrasikan dan hasil dokumen diuji:
[pdf-migration-unused-sdks.md](pdf-migration-unused-sdks.md).

Hash lock runtime dan dev digenerasi ulang dengan uv 0.12.23. Instalasi awal
Python 3.11.17 `security-runtime-b` dan `security-runtime-c` memiliki **137 paket
runtime identik + 3 bootstrap tool**, yaitu pip 26.2.1 / setuptools 84.0.0 /
wheel 0.48.0 (**140 distribusi total**, bukan 137 total). Tidak ada satu pun
PyPDF2/litellm/python-jose/ecdsa. Manifest 137 paket runtime saja:

`811eb1aeb81a6e78491ebe88adb413dc73801d2d2cb0ee66f8313a8006092e25`

Keduanya lulus pip check serta handler API asli bootstrap/login/me,
PDF/XLSX/PPTX/DOCX, native WeasyPrint/Pango, dan builder backup+manifest.
Geometri dokumen sama dengan baseline: PDF 841,8898 × 595,2756 pt; XLSX Data
Aset 4 × 55; PPTX 10 slide 12191695 × 6858000 EMU; DOCX 7772400 × 10058400 EMU.
Tidak mengklaim kesetaraan byte ZIP/PDF yang memuat timestamp/metadata dinamis.
Bukti: [security-runtime-b-smoke.json](security-runtime-b-smoke.json),
[security-runtime-c-smoke.json](security-runtime-c-smoke.json).

Smoke tambahan menjalankan protokol **ASGI lifespan startup/shutdown sebenarnya**
dengan background scheduler/event bus, kemudian auth/render/backup pada runtime
bersih; keduanya selesai normal. Shutdown menutup Mongo client aplikasi, sehingga
probe memakai client terpisah untuk membersihkan hanya database lokal acaknya.
Bukti [security-lifespan-smoke.json](security-lifespan-smoke.json).

Pembuktian akhir meniru rilis: **dua venv baru `security-runtime-d/e` dibuat
--without-pip**, dipasang melalui pip 26.2.1 dari environment installer terpisah
dengan `--python target --only-binary=:all: --require-hashes`. Masing-masing
memuat **tepat 137 distribusi, tanpa bootstrap tool maupun paket sisa**; manifest
seluruh instalasinya sama dengan SHA256 137 paket di atas. Keduanya lulus pip
check eksternal serta smoke auth/render/backup/lifespan dengan semua path kerja
privat dipasang sebelum startup. Rincian seluruh distribusi b/c/d/e:
[security-clean-install-summary.json](security-clean-install-summary.json),
[security-runtime-d-inventory.json](security-runtime-d-inventory.json),
[security-runtime-e-inventory.json](security-runtime-e-inventory.json).
Bootstrap installer dipin ke wheel vendor ber-SHA256, terpisah dari runtime:
[installer-bootstrap.json](installer-bootstrap.json).
Audit terhadap daftar **yang benar-benar terpasang**, termasuk seluruh
bootstrap tool pada b/c, juga lulus: b=140, c=140, d=137, e=137 distribusi,
semuanya nol advisory/skip. Environment installer terpisah hanya berisi pip
26.2.1 dan lulus audit satu distribusi. Hasil per profile disimpan pada
security-runtime-*-installed-audit.json dan installer-audit.json; tidak ada
paket terpasang yang diam-diam dikecualikan dari pemeriksaan ini.

Environment dev baru memakai hash lock final dan lulus pip check. **220 test
terfokus lulus dalam 26,22 detik**: producer ASGI nyata/backpressure/cancel/cap,
unduhan, replay bus, backup DR, restore/reset, dan guard media. Full unit serta
kontrak Mongo/Redis merupakan gate integrasi keseluruhan rilis yang dijalankan
koordinator; hasil akhirnya dicatat pada bukti rilis, bukan diasumsikan dari
smoke ini.

Audit dev tambahan menemukan advisory formatter Black dan direktori sementara
pytest. Pin dev kemudian diperbaiki menjadi **Black 26.3.1 / pytest 9.0.3**,
hash digenerasi ulang, environment dev disinkronkan, dan pip check lulus.
Audit final **156 paket dev, nol advisory, tanpa skip/ignore**:
[security-dev-audit.json](security-dev-audit.json). Gate integrasi keseluruhan
menggunakan pytest 9.0.3 ini; 220 test terfokus sebelumnya memakai pytest 9.0.2.
Perubahan dua tool dev ini tidak mengubah runtime 137 paket di atas.

Reproduksi audit memakai environment tooling terpisah (jangan menambahkannya ke
runtime layanan):

```bash
python -m pip install pip-audit==2.9.0
python -m pip_audit --no-deps --disable-pip -r backend/requirements-runtime.lock --format json --output /tmp/security-audit.json
```

Gerbang CI memakai reusable workflow
`.github/workflows/dependency-audit.yml`, dipanggil oleh CI utama sehingga status
audit ikut menentukan sukses CI yang dipakai deploy. Workflow juga berjalan
setiap Senin 03:17 UTC dan dapat dipicu manual. Matrix runtime/dev memasang
pip-audit 2.9.0 pada venv tooling sendiri; tidak memasang paket aplikasi ke
environment auditor. Waktu job dibatasi 10 menit dan artifact disimpan 7 hari.
Tidak ada cache advisory persisten: cache temporer dibuat per pemanggilan.

`scripts/audit_dependencies.py` menjalankan CLI asli dengan --strict,
--no-deps, --disable-pip, --require-hashes, lalu memeriksa bahwa report mencakup
tepat seluruh nama/versi aktif pada hash lock. Skip, advisory, versi salah,
hasil kosong/tidak lengkap, lookup jaringan gagal atau deadline habis semuanya
menggagalkan gate. Tidak ada fix/ignore otomatis. Dua belas uji anti-false-green
lulus; pemanggilan nyata 137/156 paket lulus. Fault jaringan yang disuntikkan
pada CLI asli menghasilkan exit 1 serta membuang report sukses lama:
[audit-ci-proof.json](audit-ci-proof.json).
Auditor menerima format hash lock tetapi memeriksa advisory berdasarkan
nama/versi; ia tidak mengunduh wheel untuk membuktikan hash byte artifact.
Verifikasi integritas pemasangan tetap dilakukan oleh pip --require-hashes
pada instalasi bersih/rilis, terpisah dari lookup advisory ini.

Tidak ada schema/data aplikasi yang dimigrasikan oleh dependency cohort ini.
Rollback mengaktifkan kembali environment/rilis immutable sebelumnya; jangan
mengubah dependency pada venv yang sedang melayani permintaan. Jangan membuka
rilis baru bila full regression, auth, render, atau audit gate gagal.
