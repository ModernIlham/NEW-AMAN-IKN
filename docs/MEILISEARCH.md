# Pencarian Cepat dengan Meilisearch (Opsional)

Panduan mengaktifkan **Meilisearch** — mesin pencari eksternal — untuk
mempercepat pencarian teks bebas pada **Aset**, **Persuratan (surat)**, dan
**Persediaan**. Mode bawaan tetap substring literal melalui MongoDB.
Meilisearch memakai prefiks/toleransi typo hanya bila
`MEILI_SEARCH_SEMANTICS=prefix_typo` dipilih secara eksplisit serta indeks dan
checkpoint dinyatakan lengkap/terakui. Instalasi service atau URL/key saja
mempertahankan pencarian MongoDB.

---

## 1. Mengapa Meilisearch?

Pencarian teks bebas AMAN memakai `regex` infix (`$regex`, `$options:"i"`) pada
belasan field sekaligus. Regex infix tidak memberi pencarian teks melalui
index B-tree; indeks activity/satker/filter lain tetap dapat membatasi lingkup
kueri Mongo. Biaya pemindaian perlu dibuktikan dengan explain pada data sendiri.

MongoDB yang kita jalankan (self-hosted di VPS, **bukan** Atlas) tidak punya
Atlas Search. Meilisearch menawarkan semantik prefiks/typo yang berbeda dari
substring literal. Pilih mode tersebut secara eksplisit bila cocok dengan
kebutuhan pencarian. Meilisearch memberi:

- **Toleransi salah ketik** ("meaja" → "meja"),
- **Pencocokan prefiks** cepat (ketik sebagian kata),
- **Peringkat relevansi** bawaan,
- Kandidat teks dari indeks khusus; latensi/kapasitas aktual diukur pada beban sendiri.

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
- **Fallback**: mode literal, engine gagal, checkpoint belum lengkap/lebih lama
  dari 300 detik, restore yang belum direkonsiliasi, atau kandidat terpotong
  memakai Mongo. Daftar, count, dan ekspor memakai keputusan kelengkapan yang
  sama; hasil parsial Meili tidak dijadikan seluruh hasil pencarian.

## 3. Instalasi service dan pemilihan semantik

Periksa konfigurasi host terlebih dahulu. Jika service belum tersedia,
operator dapat menjalankan installer berikut pada jendela operasi yang sesuai:

```bash
cd /var/www/inventarisasi        # sesuaikan bila root aplikasi berbeda
sudo bash scripts/setup_meilisearch.sh
```

Skrip installer menyiapkan:

1. Mengunduh binari Meilisearch ke `/usr/local/bin/meilisearch`.
2. Membuat user sistem `meilisearch` + direktori data `/var/lib/meilisearch`.
3. Membuat **master key acak** + menulis `/etc/meilisearch.toml`
   (Meili **hanya** bind ke `127.0.0.1` — tidak terpapar internet).
4. Memasang & menyalakan service systemd `meilisearch`.
5. Menambahkan `MEILI_URL` & `MEILI_MASTER_KEY` ke `backend/.env`.
6. Merestart backend + **reindex** data awal dari Mongo.

Installer tidak mengubah `MEILI_SEARCH_SEMANTICS`. Biarkan nilai `literal`
untuk mempertahankan semantik substring. Untuk mode `prefix_typo`, uji engine
nyata, task acknowledgement, reindex/checkpoint, kelengkapan hasil serta scope
pada staging sebelum mengubah konfigurasi dan merestart backend secara terkontrol.
Status/kredensial service yang tersedia bukan bukti mode ini siap digunakan.

> **Deploy tidak terpengaruh.** Pipeline deploy (`scripts/deploy_vps.sh`)
> mem-backup lalu mengembalikan `backend/.env` di setiap rilis, jadi
> `MEILI_URL`/`MEILI_MASTER_KEY` **tetap awet** tanpa mengubah pipeline.

### Variabel env yang dipakai backend

| Variabel | Wajib | Contoh | Keterangan |
|---|---|---|---|
| `MEILI_URL` | ya | `http://127.0.0.1:7700` | Alamat lokal Meili. Kosong = fitur mati. |
| `MEILI_MASTER_KEY` | ya | `(hex 64 karakter)` | Kunci akses. Kosong = fitur mati. Rahasia. |
| `MEILI_MAX_HITS` | tidak | `5000` | Batas kandidat 100–10.000; hasil mencapai batas memicu Mongo (lihat §6). |
| `MEILI_SEARCH_SEMANTICS` | tidak | `literal` | Bawaan Mongo substring; `prefix_typo` memilih semantik Meili secara eksplisit. |

URL dan key mengaktifkan koneksi service. Pemakaian kandidat pencarian
memerlukan `prefix_typo` dan checkpoint lengkap/terakui yang masih segar.
Mengosongkan salah satu credential atau mengembalikan semantik `literal`
menggunakan MongoDB.

### (Opsional) Simpan master key sebagai GitHub secret

Karena `backend/.env` di VPS awet lintas deploy, GitHub secret **tidak
diperlukan** agar fitur berjalan. Namun untuk pemulihan bencana / catatan,
Anda boleh menyimpan `MEILI_MASTER_KEY` sebagai secret repositori
(Settings → Secrets and variables → Actions). **Jangan** menempel kunci ini di
chat, issue, atau kode.

## 4. Reindex massal

Sinkronisasi perubahan bersifat best-effort. Jalankan reindex penuh **setelah**:

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
  "search_semantics": "literal",
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

- **Batas kandidat** (`MEILI_MAX_HITS`, bawaan **5000**, rentang 100–10.000):
  jumlah hits yang mencapai batas, estimasi total yang melebihi hits, atau
  checkpoint yang tidak lengkap membuat kandidat tidak dapat dipakai. API
  kembali ke MongoDB sehingga count/paginasi/ekspor tidak diam-diam terpotong.
  Menaikkan batas memerlukan pengukuran latensi/memori; bukan cara melewati
  pemeriksaan kelengkapan.
- **Pemulihan:** restore memaksa Mongo sampai reindex terakui. Indeks eksternal
  yang masih dapat dihubungi tidak menghapus gate tersebut. Bukti kontrak dan
  batas engine nyata tersedia di [OPT-14](bukti-optimasi/OPT-14/hasil.md).
- **Field yang dicari** mengikuti registry `INDEKS` di
  [backend/meili_utils.py](../backend/meili_utils.py), termasuk nama/pengguna,
  kode, lokasi, supplier, dan catatan sesuai domain. Field identitas tertentu
  menonaktifkan typo agar kode berbeda tidak dianggap barang yang sama.
- **Keamanan**: master key hanya dipakai backend (server tepercaya), tak pernah
  dikirim ke browser. Meili bind ke localhost saja.

## 7. Rollback mode pencarian

Kembalikan `MEILI_SEARCH_SEMANTICS=literal` di konfigurasi backend, lalu restart
secara terkontrol melalui prosedur operasi host. Credential service dapat tetap
ada; pencarian memakai MongoDB. Jika service memang tidak diperlukan, operator
juga dapat mengosongkan URL/key dan menghentikan service. Perubahan ini tidak
menghapus data Mongo atau menggantikan prosedur pemulihan setelah restore.
