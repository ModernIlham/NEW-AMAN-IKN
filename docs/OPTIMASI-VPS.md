# Analisis Optimalisasi VPS AMAN IKN

> Kondisi acuan (laporan pemilik, Agustus 2026): **VPS KVM 2** — Ubuntu 24.04
> LTS, Jakarta, **2 vCPU / 8 GB RAM**, disk 100 GB (terpakai ±15,7 GB),
> **CPU ±51% konstan stabil**, tanpa CPU limit, Docker belum terpasang,
> beban utama `mongod` + backend Python, query terberat pada koleksi
> `assets` (filter `activity_id`, `location`, `eselon1`, `eselon2`,
> `condition`, `status`, `stiker_status`), swap belum dikonfigurasi.

> **Status terverifikasi 18 Agustus 2026** (dibaca langsung dari mesin, bukan
> laporan): swap **4 GB SUDAH terpasang** (terpakai 17%) — rekomendasi §3a di
> bawah sudah dikerjakan. Memori terpakai **36%**, tersedia 4,8 GiB dari 7,8
> GiB. Beban sistem 1,19 — bukan lagi "CPU ±51% konstan". Disk **29% dari
> 95,82 GB (±27,8 GB)**, tumbuh ±12 GB dari catatan awal 15,7 GB; kemungkinan
> besar foto di GridFS, belum mendesak tetapi perlu dipantau.
>
> `dmesg | grep -i 'oom\|killed process'` **tidak menghasilkan apa pun** —
> tidak ada satu pun kejadian OOM-killer. Kekhawatiran §2 butir 3 tidak
> terbukti pada beban saat ini.
>
> Catatan cara kerja: angka-angka di atas menggantikan bagian "kondisi acuan"
> yang berasal dari laporan lisan. Dokumen ini pernah MENYESATKAN diagnosis —
> pada 17-18 Agustus 2026 tiga deploy gagal dan "tanpa swap" di dokumen ini
> dijadikan dasar dugaan tekanan memori, padahal swap sudah ada dan memori
> lapang. Penyebab sebenarnya ada di jalur jaringan penyedia (lihat §5).

---

## 1. Ringkasan kondisi VPS

| Aspek | Kondisi | Penilaian |
|---|---|---|
| CPU | ±51% konstan pada 2 vCPU (≈ 1 core penuh) | **Tidak wajar untuk idle** — wajar hanya bila job latar sedang berjalan; wajib diidentifikasi (lihat §2) |
| RAM 8 GB | mongod (WiredTiger default ≈ 3,5 GB) + uvicorn + Meilisearch + Redis + nginx | Cukup, tetapi **tanpa swap satu lonjakan ekspor/restore bisa memicu OOM-killer** |
| Disk 100 GB, terpakai 15,7 GB | Longgar | Aman; pantau pertumbuhan GridFS (foto) & log |
| Stack | MongoDB, FastAPI/uvicorn, Meilisearch, Redis, nginx, systemd timer/job aplikasi | Sudah tepat guna untuk skala satker |

**Pola "51% konstan stabil" itu ciri khas SATU proses yang memakan satu core terus-menerus** — bukan pola beban pengguna (yang naik-turun). Tiga tersangka utama berurutan kemungkinan:

1. **Job latar aplikasi yang memang adaptif-idle** — AMAN punya konversi foto→WebP terjadwal (Tinify) yang sengaja bekerja saat server senggang; kalau antrean fotonya besar, ia akan tampak sebagai CPU konstan. Ini *wajar dan by design*, selesai sendiri saat antrean habis.
2. **Query `assets` tanpa indeks komposit** yang dipanggil berulang oleh dashboard/polling — collection scan berulang membakar CPU mongod.
3. **Proses liar/miner** — harus disingkirkan lewat pemeriksaan §7 sebelum disimpulkan wajar.

## 2. Masalah utama (dan cara memastikannya)

1. **Sumber CPU 51% belum teridentifikasi.** Jalankan (§ perintah A) `pidstat` + `top -H` + `mongotop` selama 60 detik: bila pemakan CPU adalah `python` dengan thread yang sama terus → job latar aplikasi (cek antrean WebP di halaman admin); bila `mongod` → query tak berindeks; bila proses asing → insiden keamanan.
2. **Indeks komposit `assets` kurang.** Filter berat yang dilaporkan (`activity_id` + `location`/`eselon1`/`eselon2`/`condition`/`status`) selama ini hanya tertutup indeks tunggal — planner memilih indeks `activity_id` lalu menyaring sisanya baris-per-baris. **Sudah diperbaiki di aplikasi** (`backend/indexes.py`): lima indeks komposit baru dibuat otomatis saat backend restart pasca-deploy — tanpa tindakan manual.
3. **~~Tanpa swap~~ — SUDAH DIPASANG (verifikasi 18 Agu 2026: 4 GB, terpakai 17%).** Alasan aslinya tetap dicatat: 8 GB dipakai bersama mongod+python+Meili+Redis; lonjakan ekspor XLSX berfoto/restore backup bisa memicu OOM-killer membunuh mongod (terburuk) — swap adalah sabuk pengaman murah.
4. **WiredTiger cache default terlalu rakus untuk mesin bersama.** Default ≈ 50% × (RAM − 1 GB) ≈ 3,5 GB; untuk dataset belasan ribu dokumen, 1,5–2 GB lebih dari cukup dan menyisakan ruang untuk Python/Meili.
5. **Log & journal tanpa plafon** lama-lama menggerus disk dan I/O.

## 3. Rekomendasi optimalisasi

### a. Swap — PERLU, 4 GB — ✅ SUDAH DIKERJAKAN

> Terverifikasi 18 Agustus 2026: `free -h` menunjukkan swap 4,0 GiB (710 MiB
> terpakai). Bagian ini disimpan sebagai catatan alasan, bukan pekerjaan
> tertunda.

Aturan praktis RAM 8 GB tanpa hibernasi: swap 2–4 GB. Ambil **4 GB** (ruang disk longgar) dengan `vm.swappiness=10` (swap hanya saat benar-benar terdesak — mongod tidak boleh rutin ter-swap) — perintah blok B.

### b. MongoDB

- **Indeks komposit** — sudah otomatis lewat deploy (lihat §2 butir 2). Verifikasi dengan `db.assets.getIndexes()`.
- **Batasi WiredTiger cache ke 2 GB** — blok C.
- **Nyalakan profiler ambang lambat** (`slowms=100`, level 1) seminggu, baca `system.profile` untuk menangkap query lambat yang tersisa — blok C.
- **Pangkas indeks tak terpakai** (indeks juga membebani tulis): `db.assets.aggregate([{$indexStats:{}}])`, kandidat hapus = `accesses.ops` 0 setelah ≥ 1 bulan.
- Pastikan `mongod` hanya *bind* ke `127.0.0.1` (blok F memverifikasi).

### c. Backend Python

- **Jumlah worker uvicorn = 2** (sesuai vCPU). Lebih dari itu hanya menambah context-switch.
- Pastikan `.env` mengisi `REDIS_URL` dan `MEILI_URL` — cache statistik/filter/analytics dan pencarian sudah dialihkan ke sana oleh aplikasi; tanpa env itu semuanya jatuh kembali ke Mongo.
- Endpoint berat (PDF/ekspor/laporan) sudah ber-rate-limit dan berjalan di thread — tak perlu tindakan.
- Bila job WebP terbukti sumber CPU dan mengganggu: kecilkan jendela/batch-nya dari halaman pengaturan alih-alih mematikannya.

### d. Caching, cron, dan service

- `systemctl list-timers` + `crontab -l` (root & user aplikasi): kenali SETIAP timer; matikan yang tidak dikenal/dipakai (mis. `apt-daily` biarkan, `motd-news` boleh mati).
- `unattended-upgrades` biarkan aktif (keamanan), jadwalnya dini hari.
- Nginx: pastikan `gzip on` untuk `text/*, application/json` dan `expires` panjang untuk `/static/` build frontend.

### e. Disk, log, file besar

- Plafon journal systemd 200 MB + vacuum (blok D).
- `logrotate` untuk log nginx & mongod (paket bawaan biasanya sudah ada — verifikasi).
- Pantau pemakaian: `ncdu -x /` sebulan sekali; GridFS foto adalah pertumbuhan utama — alarm di 80% disk.
- Backup `mongodump` harian (cron) + salin mingguan ke LUAR VPS — fitur Backup aplikasi bukan pengganti backup infrastruktur.

### f. Keamanan dasar

- Blok F memeriksa: listener tak dikenal (`ss -tulpn`), proses CPU teratas bernama aneh (miner biasanya menyaru `kworker`/acak di `/tmp`), cron liar, `authorized_keys` asing, login gagal beruntun.
- Pastikan `ufw` default deny + allow 22/80/443 saja; Mongo/Redis/Meili TIDAK terekspos publik.
- `fail2ban` untuk SSH bila belum ada.
- Kredensial yang pernah bocor di riwayat chat/repo (JWT_SECRET, kunci API) **wajib dirotasi** — pengingat yang sama dengan sebelumnya.

## 4. Urutan prioritas (paling berdampak dulu)

1. **Identifikasi sumber CPU 51%** (blok A) — semua langkah lain menunggu diagnosis ini; jangan restart-restart sebelum tahu penyebab.
2. **Deploy aplikasi terbaru** → indeks komposit `assets` terpasang otomatis (menghilangkan tersangka #2 secara permanen).
3. ~~**Pasang swap 4 GB + swappiness 10** (blok B)~~ — ✅ **selesai** (verifikasi 18 Agu 2026).
4. **Batasi WiredTiger 2 GB + profiler slowms** (blok C).
5. **Pemeriksaan keamanan dasar** (blok F).
6. **Plafon log/journal + verifikasi logrotate + backup cron** (blok D/E).
7. Peninjauan bulanan: `$indexStats`, `ncdu`, `system.profile`.

## 5. Perintah terminal siap jalan

```bash
# ── A. DIAGNOSIS SUMBER CPU (jalankan dulu, 2-3 menit) ──────────────────
sudo apt-get install -y sysstat
pidstat 5 6                       # proses pemakan CPU per 5 detik
top -H -b -n 1 | head -30         # thread teratas (python? mongod?)
mongotop 5 --rowcount 6           # koleksi Mongo tersibuk
mongosh --eval 'db.currentOp({"secs_running":{"$gte":2}})'   # op berjalan lama
systemctl list-timers --all       # timer terjadwal
crontab -l; sudo crontab -l       # cron user & root

# ── B. SWAP 4 GB + swappiness 10 ────────────────────────────────────────
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf
sudo sysctl -p /etc/sysctl.d/99-swap.conf
free -h                            # verifikasi

# ── C. MONGODB: cache 2 GB + profiler lambat ────────────────────────────
#  /etc/mongod.conf → tambahkan di bagian storage:
#    wiredTiger:
#      engineConfig:
#        cacheSizeGB: 2
sudo systemctl restart mongod
mongosh --eval 'db.getSiblingDB("NAMA_DB").setProfilingLevel(1, {slowms:100})'
# seminggu kemudian, baca hasilnya:
mongosh --eval 'db.getSiblingDB("NAMA_DB").system.profile.find().sort({ts:-1}).limit(10)'
# verifikasi indeks baru terpasang pasca-deploy:
mongosh --eval 'db.getSiblingDB("NAMA_DB").assets.getIndexes().map(i=>i.name)'
# indeks tak terpakai (setelah >=1 bulan uptime):
mongosh --eval 'db.getSiblingDB("NAMA_DB").assets.aggregate([{$indexStats:{}}]).map(i=>({n:i.name,ops:i.accesses.ops}))'

# ── D. LOG & JOURNAL ────────────────────────────────────────────────────
sudo journalctl --vacuum-size=200M
sudo sed -i 's/^#\?SystemMaxUse=.*/SystemMaxUse=200M/' /etc/systemd/journald.conf
sudo systemctl restart systemd-journald
du -xh /var/log | sort -h | tail -15

# ── E. DISK & FILE BESAR ────────────────────────────────────────────────
sudo apt-get install -y ncdu && sudo ncdu -x /
df -h; sudo du -sh /var/lib/mongodb

# ── F. KEAMANAN DASAR ───────────────────────────────────────────────────
ss -tulpn                          # listener: hanya 22/80/443 publik; 27017/6379/7700 lokal
ps aux --sort=-%cpu | head -15     # nama proses aneh? path /tmp//dev/shm = curiga
ls -la /etc/cron.d /etc/cron.daily /etc/cron.hourly
cat ~/.ssh/authorized_keys         # hanya kunci yang Anda kenal
sudo lastb | head -20              # percobaan login gagal
sudo ufw status verbose
sudo apt-get install -y fail2ban && sudo systemctl enable --now fail2ban
```

## 6. Saran lanjutan — bila CPU tetap tinggi (OLTP vs OLAP, dengan bijak)

Pertanyaan pemilik: perlukah alur **Debezium → Kafka → ClickHouse**?

**Rekomendasi tegas: JANGAN sekarang.** Alasannya bukan teknologinya jelek,
melainkan tidak proporsional:

- Skala data AMAN saat ini (ratusan–puluhan ribu dokumen aset per satker)
  masih 3–4 orde magnitudo di bawah titik di mana pipeline CDC mulai
  membayar dirinya sendiri.
- Kafka + Connect/Debezium + ClickHouse butuh ±4–6 GB RAM dan operasional
  harian sendiri — **di VPS 2 vCPU/8 GB, pipeline-nya akan memakan lebih
  banyak sumber daya daripada aplikasi yang mau ia ringankan**, dan menjadi
  titik gagal baru yang harus dirawat.
- Beban "OLAP" AMAN (LBKP/CaLBMN/LBP/analytics) sudah dimitigasi di dalam
  aplikasi: cache Redis ber-generasi, agregasi `$facet` satu lintasan,
  laporan berat di thread + rate-limit, ekspor async via job latar.

**Tangga eskalasi yang bijak** (naik satu anak tangga hanya bila anak tangga
sebelumnya terbukti tidak cukup):

1. **Sekarang**: indeks komposit + Redis/Meili aktif + WiredTiger 2 GB
   (semuanya sudah/di PR ini).
2. **Bila laporan mulai mengganggu transaksi**: jalankan **replika hidden
   MongoDB** di proses kedua/VPS kecil terpisah, arahkan endpoint laporan ke
   `readPreference=secondary` — tanpa teknologi baru.
3. **Bila butuh analitik ad-hoc berat**: ekspor malam hari ke **DuckDB**
   (file tunggal, nol infrastruktur) dari koleksi ringkas — kueri analitik
   secepat ClickHouse untuk skala GB-an.
4. **Baru bila** data > puluhan juta baris, multi-konsumen event, dan tim
   ops tersedia: pertimbangkan CDC (saat itu pun mulai dari MongoDB Change
   Streams → konsumen kecil, sebelum melompat ke Kafka).

Pemicu konkret untuk naik tangga: p95 waktu-respons daftar aset > 1,5 detik
SETELAH indeks terpasang, ATAU laporan semesteran membuat CPU jenuh > 15
menit, ATAU `system.profile` menunjukkan query laporan mendominasi jam kerja.

---

*Dokumen ini bagian dari PR optimalisasi; indeks komposit `assets` yang
disebut di §2 dibuat otomatis oleh `backend/indexes.py` saat deploy.*

---

## 5. Insiden jaringan penyedia — 17-18 Agustus 2026

Tiga deploy gagal dengan galat yang sama: `ssh-keyscan` tidak dapat menjangkau
VPS setelah lima percobaan. Yang menentukan justru apa yang **tidak** ada di
log VPS.

| Waktu (UTC) | Kejadian |
|---|---|
| 17 Agu 23:45:57 | sshd menerima koneksi runner — deploy 842 berhasil |
| 18 Agu 00:03:02 | deploy 843 berhasil |
| 18 Agu 00:20:30 | deploy 844 berhasil |
| **18 Agu 00:38:32-00:40:52** | **deploy 845 gagal — sshd TIDAK mencatat apa pun** |
| 18 Agu 00:51:17 | deploy 845 dijalankan ulang — berhasil |

Pada jendela yang gagal, `journalctl -u ssh` tidak memuat satu pun baris:
bukan koneksi ditolak, bukan negosiasi gagal, melainkan **paketnya tidak
pernah sampai**. Tidak ada pula `Stopped/Started` sshd, sehingga
`unattended-upgrades` yang me-restart layanan juga bukan penyebabnya.

Kesimpulan: gangguan berada di **jalur jaringan sebelum mesin** — firewall
atau proteksi edge di sisi penyedia VPS. Di luar kendali repo ini.

**Yang dikerjakan di repo:** jendela retry `deploy.yml` diperpanjang dari
5x(15s+20s) ≈ 2,9 menit menjadi 8x(15s+30s) ≈ 6 menit, supaya deploy bertahan
melewati blip beberapa menit. Itu **bantalan**, bukan perbaikan.

**Yang perlu ditanyakan ke penyedia:** mengapa pada 18 Agustus 2026
00:38-00:41 UTC koneksi masuk ke port 22 tidak sampai ke server, padahal
sebelum dan sesudahnya normal.

Catatan untuk pembaca berikutnya: baris `Unable to negotiate ... Their offer:
sk-ecdsa-sha2-nistp256@openssh.com` di log sshd adalah perilaku **normal**
`ssh-keyscan` yang mencoba beberapa tipe kunci host. Kehadirannya justru
menandakan koneksi sampai — bukan gejala masalah.
