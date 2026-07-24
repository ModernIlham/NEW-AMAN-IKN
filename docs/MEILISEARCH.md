# Pencarian Cepat dengan Meilisearch (Opsional)

Panduan mengaktifkan **Meilisearch** — mesin pencari eksternal — untuk
mempercepat pencarian teks bebas pada **Aset**, **Persuratan (surat)**, dan
**Persediaan**. Fitur ini **opsional** dan **ber-feature-flag**: bila tidak
diaktifkan, AMAN tetap berjalan normal memakai pencarian regex MongoDB.

---

## 1. Mengapa Meilisearch?

Pencarian teks bebas AMAN memakai `regex` infix (`$regex`, `$options:"i"`) pada
belasan field sekaligus. Regex infix **tidak bisa memakai index B-tree** Mongo,
sehingga pada data yang sudah sangat banyak setiap pencarian memaksa
**pemindaian penuh** (COLLSCAN) dalam lingkup satker — makin lambat seiring data
bertambah.

MongoDB yang kita jalankan (self-hosted di VPS, **bukan** Atlas) tidak punya
Atlas Search. Padanan "trigram/n-gram" yang tepat adalah **mesin pencari
eksternal**. Meilisearch memberi:

- **Toleransi salah ketik** ("meaja" → "meja"),
- **Pencocokan prefiks** cepat (ketik sebagian kata),
- **Peringkat relevansi** bawaan,
- Hasil dalam hitungan milidetik walau data ratusan ribu baris.

## 2. Cara Kerja (ringkas & aman)

- **Pencarian**: Meilisearch me-resolve kata kunci menjadi **daftar id
  kandidat** (sudah ter-scope satker), lalu id itu diumpankan ke kueri Mongo
  yang sudah ada (`{"id": {"$in": [...]}}`). **Semua** filter lanjutan, urutan,
  paginasi, dan **isolasi satker tetap dijalankan MongoDB** (otoritatif) —
  Meilisearch hanya akselerator pencocokan teks, bukan sumber kebenaran. Hasil
  Meili **tidak bisa** membocorkan data lintas-satker karena kueri Mongo tetap
  menyaring ulang.
- **Sinkronisasi**: setiap buat/ubah/hapus (aset, surat, persediaan) otomatis
  memperbarui indeks Meili secara *best-effort* & non-blocking. Bila gagal /
  Meili mati, permintaan tetap sukses — reindex massal menambal selisih.
- **Fallback**: bila Meilisearch nonaktif, mati, atau menolak, pencarian
  **otomatis kembali** ke regex Mongo. Tidak ada yang rusak.

## 3. Aktivasi (sekali jalan di VPS)

Login SSH ke VPS lalu jalankan **satu perintah**:

```bash
cd /var/www/inventarisasi        # sesuaikan bila root aplikasi berbeda
sudo bash scripts/setup_meilisearch.sh
```

Skrip ini (idempoten — aman diulang) akan:

1. Mengunduh binari Meilisearch ke `/usr/local/bin/meilisearch`.
2. Membuat user sistem `meilisearch` + direktori data `/var/lib/meilisearch`.
3. Membuat **master key acak** + menulis `/etc/meilisearch.toml`
   (Meili **hanya** bind ke `127.0.0.1` — tidak terpapar internet).
4. Memasang & menyalakan service systemd `meilisearch`.
5. Menambahkan `MEILI_URL` & `MEILI_MASTER_KEY` ke `backend/.env`.
6. Merestart backend + **reindex** data awal dari Mongo.

Setelah selesai, pencarian aset/surat/persediaan otomatis memakai Meilisearch.

> **Deploy tidak terpengaruh.** Pipeline deploy (`scripts/deploy_vps.sh`)
> mem-backup lalu mengembalikan `backend/.env` di setiap rilis, jadi
> `MEILI_URL`/`MEILI_MASTER_KEY` **tetap awet** tanpa mengubah pipeline.

### Variabel env yang dipakai backend

| Variabel | Wajib | Contoh | Keterangan |
|---|---|---|---|
| `MEILI_URL` | ya | `http://127.0.0.1:7700` | Alamat lokal Meili. Kosong = fitur mati. |
| `MEILI_MASTER_KEY` | ya | `(hex 64 karakter)` | Kunci akses. Kosong = fitur mati. Rahasia. |
| `MEILI_MAX_HITS` | tidak | `5000` | Batas id kandidat per pencarian (lihat §6). |

Feature flag: fitur **aktif hanya bila `MEILI_URL` DAN `MEILI_MASTER_KEY`
ter-set**. Kosongkan salah satu → kembali ke regex Mongo.

### (Opsional) Simpan master key sebagai GitHub secret

Karena `backend/.env` di VPS awet lintas deploy, GitHub secret **tidak
diperlukan** agar fitur berjalan. Namun untuk pemulihan bencana / catatan,
Anda boleh menyimpan `MEILI_MASTER_KEY` sebagai secret repositori
(Settings → Secrets and variables → Actions). **Jangan** menempel kunci ini di
chat, issue, atau kode.

## 4. Reindex massal

Sinkronisasi harian otomatis. Jalankan reindex penuh **setelah**:

- Mengaktifkan Meilisearch pertama kali (skrip setup sudah melakukannya),
- **Impor massal Excel**, **restore backup**, atau migrasi data,
- Ingin menyamakan indeks dengan Mongo kapan pun.

Dua cara:

**a. Lewat CLI di VPS**

```bash
cd /var/www/inventarisasi/backend
venv/bin/python -m scripts.reindex_search
```

**b. Lewat API (super-admin)**

```
POST /api/search/reindex?koleksi=all      # atau assets | surat | persediaan
```

Cek status kapan saja (admin):

```
GET /api/search/status
```

Contoh respons:

```json
{
  "aktif": true,
  "url": "http://127.0.0.1:7700",
  "max_hits": 5000,
  "indeks": {
    "assets":     {"uid": "aman_assets",     "jumlah_dokumen": 12345, "sedang_indexing": false},
    "surat":      {"uid": "aman_surat",      "jumlah_dokumen": 678,   "sedang_indexing": false},
    "persediaan": {"uid": "aman_persediaan", "jumlah_dokumen": 900,   "sedang_indexing": false}
  }
}
```

## 5. Operasional

```bash
systemctl status meilisearch      # status service
journalctl -u meilisearch -f      # log langsung
systemctl restart meilisearch     # restart
```

- **Data**: `/var/lib/meilisearch/data.ms`. Ini **indeks turunan** — sumber
  kebenaran tetap MongoDB. Boleh dihapus lalu reindex bila indeks korup.
- **Kapasitas**: indeks jauh lebih kecil dari data foto GridFS, tetapi tetap
  pantau disk (indeks ikut tumbuh dengan jumlah baris).

## 6. Batas & catatan

- **Batas kandidat** (`MEILI_MAX_HITS`, bawaan **5000**): satu pencarian
  mengambil paling banyak sekian id kandidat paling relevan. Untuk kata kunci
  yang sangat umum pada data raksasa, jumlah total bisa terpotong pada ambang
  ini (yang tampil adalah yang paling relevan) — tetap jauh lebih cepat dari
  COLLSCAN. Naikkan lewat env `MEILI_MAX_HITS` bila satker sangat besar
  (indeks otomatis menyesuaikan `pagination.maxTotalHits` saat startup/ reindex).
- **Field yang dicari** sama dengan sebelumnya: aset 16 field
  (kode/nama/seri/lokasi/merk/model/kategori/eselon1-2/pengguna/pemasok/
  kondisi/status/nomor SPM/kode register/catatan); surat 8 field; persediaan
  6 field. Harga/PII sensitif **tidak** diindeks.
- **Keamanan**: master key hanya dipakai backend (server tepercaya), tak pernah
  dikirim ke browser. Meili bind ke localhost saja.

## 7. Rollback (matikan fitur)

Hapus dua baris di `backend/.env` lalu restart backend:

```bash
sed -i '/^MEILI_URL=/d;/^MEILI_MASTER_KEY=/d' backend/.env
supervisorctl restart inventarisasi-backend
```

Pencarian otomatis kembali ke regex Mongo. Service Meili boleh dibiarkan atau
dihentikan: `sudo systemctl disable --now meilisearch`.
