# OPT-09 — Transport artifact berbatas

Implementasi 15 Oktober 2026:

- `backend/asgi_artifact.py` memanggil aplikasi ASGI asli, termasuk middleware,
  dependency, autentikasi, isolasi satker, dan rate limiter. Header Authorization
  serta X-Satker-Aktif hanya diteruskan di memori. Tidak menggunakan
  `httpx.ASGITransport`, `aread`, accumulator body, atau antrean producer bebas.
- Setiap `send(http.response.body)` menunggu penulisan GridFS. Payload ASGI besar
  dipecah menjadi penulisan maksimum 64 KiB. Producer tidak dapat melanjutkan
  ketika penulisan lambat. Error body hanya menyimpan maksimum 4 KiB.
- Cap 200 MiB ditegakkan sebelum menulis chunk yang melebihi batas. Deadline
  mencakup antre semaphore, jeda retry429, render dan unggah. Respons harus
  selesai dan sesuai Content-Length bila tersedia, aplikasi harus kembali tanpa
  galat, lalu GridFS close berhasil sebelum referensi artifact dipublikasikan.
- Producer gagal, timeout, cancel, write/close gagal: upload diaborsi dan blob
  parsial dibersihkan. Terminal state tidak bisa ditimpa worker terlambat.
  Reply Mongo yang hilang sesudah publikasi tidak menghapus blob yang ternyata
  sudah direferensikan; jika status DB belum dapat dibuktikan, blob dipertahankan
  untuk cleanup retensi, bukan membuat referensi menggantung.
- `/jobs/{id}/download` membuka GridOut lalu `readchunk` secara lazy; tidak
  memuat seluruh artifact ke bytes/BytesIO. Ownership/satker, nama, MIME, auth
  anchor, 403 dan 404 dipertahankan. Artifact lama tetap terbaca.

## Bukti

`backend/tests/unit/test_asgi_artifact.py` menggunakan producer ASGI nyata dan
FastAPI nyata, tanpa AsyncClient palsu: chunk pertama sudah ditulis sebelum
producer selesai; sink lambat menahan producer; cap menghentikan producer; 403
melewati middleware+dependency; 429 tetap tersedia untuk Retry-After; gagal
setelah chunk, timeout, cancel, write/close gagal, dan length mismatch abort.

`backend/tests/contract/test_unduhan.py` menggunakan Mongo/GridFS nyata pada
fixture DB localhost `aman_ci_*`. Artifact selesai cocok byte-per-byte; producer
gagal setelah chunk GridFS tersimpan tidak meninggalkan file/chunk atau artifact
siap diunduh.

Pengukuran [memory.json](memory.json), producer chunk nyata dan counting sink:

| Body | Peak alokasi Python transport | Penulisan terbesar |
|---|---:|---:|
| 8 MiB | 70.670 byte | 65.536 byte |
| 32 MiB | 70.318 byte | 65.536 byte |
| 64 MiB | 70.294 byte | 65.536 byte |

Ini mengukur overhead transport, bukan keseluruhan RSS backend, allocator
renderer PDF/XLSX, maupun buffer internal driver GridFS. Builder yang membuat
seluruh dokumen masih membutuhkan memori sesuai dokumen; budget worker global
adalah OPT-22. Cancellation Python bersifat kooperatif ketika producer kembali
ke event loop; tidak menjanjikan pemutusan CPU renderer sinkron seketika.

## Verifikasi ulang

Hasil lokal: **52 tes unit terfokus lulus** dan **3 tes kontrak Mongo/GridFS nyata
lulus**. Gerbang suite penuh dan deployment mengikuti PR gabungan di root.

```bash
.venv/bin/python -m pytest backend/tests/unit/test_asgi_artifact.py backend/tests/unit/test_unduhan.py backend/tests/unit/test_unduhan_lifecycle.py backend/tests/unit/test_denyut_job_dan_sapuan.py -q
AMAN_CONTRACT_MONGO_URL=mongodb://127.0.0.1:27017 AMAN_CONTRACT_REDIS_URL=redis://127.0.0.1:16379/15 .venv/bin/python -m pytest -m integration backend/tests/contract/test_unduhan.py -q
```

Rollback mempertahankan artifact lama dan metadata. Jangan mengaktifkan kembali
transport buffering tanpa cap konservatif. Perubahan unduhan dipasangkan dengan
klaim/heartbeat OPT-10; tunggu job aktif selesai sebelum mengganti worker.
