# Cache Bersama & Rate-Limit dengan Redis (Opsional)

Panduan mengaktifkan **Redis** untuk AMAN. Fitur ini **opsional** dan
**ber-feature-flag**: bila tidak diaktifkan, AMAN berjalan normal memakai cache
per-worker (in-memory) dan rate-limiter berbasis MongoDB seperti sebelumnya.

---

## 1. Mengapa Redis?

VPS menjalankan **2 worker uvicorn**. Dua hal jadi kurang optimal tanpa store
bersama:

1. **Cache ringkasan basi antar-worker.** Cache statistik/opsi-filter/analitik/
   kategori selama ini `TTLCache` **per-worker**. Setelah ada perubahan data,
   `invalidate_asset_cache()` hanya mengosongkan cache worker yang menangani
   tulis — **worker lain tetap menyajikan angka lama** sampai TTL habis
   (60–300 detik). Redis menjadikan cache **satu sumber bersama** dengan
   **invalidasi seketika di kedua worker**.
2. **Rate-limiter menyentuh MongoDB.** Storage rate-limit saat ini di MongoDB
   (sudah bersama & andal). Redis lebih cepat (sub-milidetik) untuk operasi
   penghitung ini.

## 2. Cara Kerja (ringkas & aman)

- **Cache bersama**: nilai disimpan di Redis dengan **penghitung generasi** per
  namespace. Kunci = `aman:cache:<ns>:<gen>:<key>`. Invalidasi cukup menaikkan
  generasi (`INCR aman:gen:<ns>`) — **O(1), atomik, seketika lintas worker**;
  kunci generasi lama menjadi yatim & kedaluwarsa via TTL. Kunci cache tetap
  menyertakan **kode_satker** sehingga **isolasi satker terjaga** (sama seperti
  cache in-memory sebelumnya).
- **Rate-limiter**: bila `REDIS_URL` di-set, storage rate-limit otomatis memakai
  Redis; bila tidak, tetap MongoDB. Keduanya ber-fallback in-memory bila store
  bermasalah.
- **Fallback aman**: bila `REDIS_URL` kosong → cache per-worker + rate-limit
  MongoDB (perilaku lama). Bila Redis mati/menolak → operasi cache di-swallow
  (miss → hitung ulang dari Mongo), rate-limit jatuh ke in-memory; **aplikasi
  tetap jalan**.

## 3. Aktivasi (sekali jalan di VPS)

```bash
cd /var/www/inventarisasi        # sesuaikan bila root aplikasi berbeda
sudo bash scripts/setup_redis.sh
```

Skrip ini (idempoten) akan:

1. Memasang `redis-server` (apt).
2. Bind **hanya** ke `127.0.0.1` (localhost) + set password (`requirepass`).
3. Menyalakan service systemd `redis-server`.
4. Menambahkan `REDIS_URL` ke `backend/.env`.
5. Merestart backend agar membaca env baru.

> **Deploy tidak terpengaruh.** Pipeline deploy mem-backup lalu mengembalikan
> `backend/.env` di setiap rilis, jadi `REDIS_URL` **tetap awet** tanpa mengubah
> pipeline.

### Variabel env yang dipakai backend

| Variabel | Wajib | Contoh | Keterangan |
|---|---|---|---|
| `REDIS_URL` | ya | `redis://:<password>@127.0.0.1:6379/0` | Alamat lokal Redis. Kosong = fitur mati. Rahasia (berisi password). |

Feature flag: fitur **aktif hanya bila `REDIS_URL` ter-set**. Kosongkan →
kembali ke cache per-worker + rate-limit MongoDB.

## 4. Verifikasi

```bash
systemctl status redis-server            # status service
redis-cli -a '<password>' ping           # → PONG
```

Lewat aplikasi (deep health, super-admin/monitor):

```
GET /api/health/deep   → { "checks": { "redis": { "ok": true, "latency_ms": ... } } }
```

Catatan: Redis yang tak sehat **tidak** menjatuhkan status `ok` keseluruhan —
cache jatuh-balik ke Mongo/in-memory, jadi dilaporkan sebagai info degradasi,
bukan kegagalan gerbang deploy.

## 5. Operasional

```bash
systemctl restart redis-server     # restart
journalctl -u redis-server -f      # log langsung
redis-cli -a '<password>' info memory   # pemakaian memori
```

- **Data** = cache turunan (sumber kebenaran tetap MongoDB). Aman di-flush kapan
  saja (`redis-cli -a '<password>' FLUSHDB`) — cache akan terisi ulang otomatis.
- **Memori**: cache ringkasan kecil; pantau `used_memory` bila khawatir.
  Bila perlu, batasi via `maxmemory` + `maxmemory-policy allkeys-lru` di
  `/etc/redis/redis.conf`.
- **Keamanan**: Redis bind ke `127.0.0.1` + password; tidak terpapar internet.
  `REDIS_URL` (berisi password) hanya di `backend/.env` sisi server.

## 6. Rollback (matikan fitur)

Hapus `REDIS_URL` dari `backend/.env` lalu restart backend:

```bash
sed -i '/^REDIS_URL=/d' backend/.env
supervisorctl restart inventarisasi-backend
```

Cache otomatis kembali ke per-worker dan rate-limiter ke MongoDB. Service Redis
boleh dibiarkan atau dihentikan: `sudo systemctl disable --now redis-server`.
