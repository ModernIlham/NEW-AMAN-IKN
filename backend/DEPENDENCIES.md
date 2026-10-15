# Dependensi dan runtime yang dapat direproduksi

Runtime produksi memakai `requirements.txt` → `requirements-runtime.lock`.
Pengembangan/CI memakai `requirements-dev.txt` → `requirements-dev.lock`.
Keduanya mewajibkan SHA256. File `.in` adalah input yang ditinjau; `.lock`
menyimpan seluruh hasil resolusi. Jangan menyunting hash atau menambah paket
tanpa memperbarui lock dan menguji environment bersih.

CI utama memanggil reusable workflow dependency-audit untuk runtime dan dev.
Audit juga dijadwalkan mingguan dan dapat dipicu manual; lookup gagal, skip,
coverage tidak lengkap, maupun advisory menggagalkan gate. Auditor terpasang
di venv tooling terpisah, bukan environment aplikasi. Detail frontend yang
masih memiliki advisory ada pada
[inventaris Yarn](../docs/bukti-optimasi/OPT-24/frontend-security.md).

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m pip check
```

Produksi memasang `backend/requirements.txt` pada venv rilis yang terpisah.
`pip install` tidak menghapus paket lama yang sudah terpasang; untuk membuktikan
runtime bersih gunakan venv baru, bukan menghapus paket dari venv yang sedang
melayani pengguna. Lock sebelumnya dan rilis lama menjadi titik rollback.

Regenerasi memakai **uv 0.12.23**, tanpa memasang ke runtime:

```bash
bash scripts/lock_dependencies.sh
```

Python **3.11** menjadi baseline CI/produksi (`.python-version`); compatibility
suite lokal juga berjalan pada3.12. Node **22LTS** (`.nvmrc`) dan Yarn
**1.22.22** (`frontend/package.json#packageManager`) menjadi baseline frontend.
Gerbang final cloud memakai Node 22.23.2. Versi patch aktual dan native
libraries dicatat pada manifest build; Node VPS harus diperiksa sebelum menghapus
bypass engine pada skrip instalasi lama.

WeasyPrint memerlukan Pango/Fontconfig dan font yang sama untuk geometri laporan.
Lock pip tidak memasang library OS. Manifest bukti OPT-24 mencatat Pango/Cairo/
Fontconfig dan SHA256 Inter dari commit font yang terpin. Jalankan smoke pada
image/host rilis nyata sebelum mengaktifkan docroot.

```bash
python scripts/inventory_dependencies.py --output /tmp/runtime-inventory.json
python scripts/smoke_runtime.py --mongo-url mongodb://127.0.0.1:27017/ --output /tmp/runtime-smoke.json
```

Smoke hanya menerima loopback dan membuat/menghapus DB`aman_ci_runtime_*` miliknya
sendiri. Ia memakai handler API asli: bootstrap/login/me, PDF/XLSX/PPTX/DOCX
kemudian membaca ulang hasil+geometri, nativeWeasyPrint, serta backup+manifest.
Rate limiter memakai MemoryStorage pada proses probe agar tidak menulis database
ratelimit bersama; suite kontrak terpisah menguji Mongo/Redis nyata.

Inventaris AST mencakup import di dalam fungsi/try dan panggilan dinamis. Ia
**tidak** menyimpulkan paket aman dihapus dari ketiadaan direct import. Penghapusan
litellm/python-jose/ecdsa telah dibuktikan dengan inventaris import dinamis dan
reverse dependency; PyPDF2 dihapus setelah semua consumer dipindahkan ke pypdf
dan dokumen hasilnya diuji. SDK lain tetap dipertahankan. Runtime final berisi
137 paket yang ter-resolve; audit PyPI pip-audit 2.9.0 pada 15 Oktober 2026
melaporkan nol advisory untuk lock ini, tanpa ignore. Ulangi audit saat rilis
dan secara terjadwal karena advisory dapat terbit setelah lock dibuat.

Kandidat keamanan memperbarui ASGI/auth/multipart, Motor/PyMongo, serta decoder
media/PDF dalam kelompok yang diuji pada Python 3.11 bersih. Detail versi,
baseline audit, dan smoke render/startup/shutdown terdapat pada
[bukti keamanan OPT-24](../docs/bukti-optimasi/OPT-24/security.md).

```bash
python scripts/smoke_runtime.py --mongo-url mongodb://127.0.0.1:27017/ --lifespan --output /tmp/runtime-lifespan.json
```

## Driver Mongo dan CRA

Kandidat rilis memakai Motor **3.7.1** / PyMongo **4.19.0**; API tetap Motor.
CRA/CRACO tetap dipakai. Lifecycle vendor dan spike PyMongo Async 4.19.0 dibuktikan dalam
[OPT-24](../docs/bukti-optimasi/OPT-24/hasil.md). Migrasi driver memerlukan adapter
untuk `aggregate` dan penutupan client yang kini awaitable serta revisi mocks;
jangan mengganti import sebagai migrasi produksi. Jadwalkan migrasi native async
sebelum 31 Maret 2027, mendahului akhir critical fixes Motor 14 Mei 2027.
Migrasi bundler memerlukan
port alias, env publik, Jest, precache, manifest dan kontrak deploy sekaligus.
