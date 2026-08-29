# Analisis Optimalisasi VPS AMAN IKN

> Kondisi acuan (laporan pemilik, Agustus 2026): **VPS KVM 2** — Ubuntu 24.04
> LTS, Jakarta, **2 vCPU / 8 GB RAM**, disk 100 GB (terpakai ±15,7 GB),
> **CPU ±51% konstan stabil**, tanpa CPU limit, Docker belum terpasang,
> beban utama `mongod` + backend Python, query terberat pada koleksi
> `assets` (filter `activity_id`, `location`, `eselon1`, `eselon2`,
> `condition`, `status`, `stiker_status`), swap belum dikonfigurasi.

> **Status terverifikasi 29 Agustus 2026** — dibaca mesin lewat **Actions →
> "Inventaris VPS"** (`scripts/inventaris_vps.sh`), bukan laporan. Sejak alat
> itu ada, angka di dokumen ini bisa diperbarui siapa saja dengan satu klik;
> tak ada lagi alasan menaruh tebakan di sini.
>
> | Aspek | Bacaan 18 Agu | Bacaan 29 Agu |
> |---|---|---|
> | Beban (1/5/15 mnt) | 1,19 | **1,02 · 1,01 · 1,01** |
> | Memori | 36% terpakai, 4,8 GiB tersedia | **1,9 GiB / 7,8 GiB terpakai, 5,8 GiB tersedia** |
> | Swap | 4 GiB, terpakai 710 MiB (17%) | 4 GiB, terpakai **1,2 MiB (≈0%)** |
> | Disk `/` | 27,8 GB / 95,8 GB (29%) | **31 GB / 96 GB (32%)** |
> | Uptime | — | 3 hari 23 jam |
>
> **Tiga hal yang harus mengubah isi dokumen ini, bukan sekadar ditempel:**
>
> 1. **`fail2ban` TIDAK TERPASANG di VPS** (`fail2ban-client` tidak ada;
>    paketnya juga tak ada di daftar APT). Seluruh dugaan "fail2ban memblokir
>    IP runner" pada §4/§5 karena itu **tidak bisa benar di mesin ini**, dan
>    perintah `fail2ban-client status sshd` yang dianjurkan di sana **tidak
>    akan jalan**. `Connection timed out` pada deploy 18–19 Agustus tetap
>    berarti paket SYN dijatuhkan diam-diam — tetapi yang menjatuhkannya ada di
>    **hulu**: firewall/proteksi DDoS penyedia, bukan VPS-nya.
> 2. **Beban 1,00 datar di 1/5/15 menit pada 2 vCPU = satu core terbakar
>    terus-menerus.** Kalimat 18 Agustus *"beban sistem 1,19 — bukan lagi CPU
>    ±51% konstan"* **keliru**: 1,19 dari 2 vCPU justru ≈ 60%, dan 1,01 ≈ 50%.
>    Angkanya tak pernah membantah gejala aslinya, ia mengonfirmasinya. §2
>    butir 1 **masih terbuka**, dan tiga bacaan terpisah kini mendukungnya.
> 3. **Swap praktis tak tersentuh** (1,2 MiB dari 4 GiB) dan memori lapang
>    5,8 GiB. Tekanan memori bukan masalah mesin ini — dan `dmesg` 18 Agustus
>    juga tak menemukan satu pun OOM-killer. §2 butir 3 tetap tidak terbukti.
>
> Catatan cara kerja: dokumen ini pernah MENYESATKAN diagnosis — pada 17-18
> Agustus 2026 tiga deploy gagal dan "tanpa swap" di sini dijadikan dasar
> dugaan tekanan memori, padahal swap sudah ada dan memori lapang. Butir 1 dan
> 2 di atas adalah kesalahan sejenis yang baru ketahuan; keduanya sengaja
> ditulis sebagai koreksi, bukan diam-diam ditimpa.

---

## 1. Ringkasan kondisi VPS

| Aspek | Kondisi | Penilaian |
|---|---|---|
| CPU | ±51% konstan pada 2 vCPU (≈ 1 core penuh) | **Tidak wajar untuk idle** — wajar hanya bila job latar sedang berjalan; wajib diidentifikasi (lihat §2) |
| RAM 8 GB | mongod (WiredTiger default ≈ 3,5 GB) + uvicorn + Meilisearch + Redis + nginx | Cukup, tetapi **tanpa swap satu lonjakan ekspor/restore bisa memicu OOM-killer** |
| Disk 96 GB, terpakai **31 GB (32%)** — 29 Agu 2026 | Longgar | Aman; tumbuh ±3 GB dalam 11 hari (27,8 GB pada 18 Agu). Pada laju itu ambang 80% masih >1 tahun, tetapi GridFS foto adalah pertumbuhan utama — pasang alarm 80% |
| Stack | MongoDB **7.0.40**, FastAPI/uvicorn (Python sistem **3.12.3**; **3.11.15** ikut dipasang manual — versi di dalam `backend/venv` akan terbaca pada inventaris berikutnya), Meilisearch **1.11.3**, Redis **7.0.15**, nginx **1.24.0**, Node **22.23.2**, certbot **5.7.0** | Sudah tepat guna untuk skala satker; versi terverifikasi 29 Agu 2026 |

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

**Topologi layanan sebenarnya (terverifikasi 29 Agu 2026, dikoreksi hari yang
sama).** Bagian ini sempat memuat temuan yang SALAH; koreksinya ditulis di
sini alih-alih ditimpa, karena cara ia salah lebih berguna daripada hasil
akhirnya.

| Komponen | Dikelola oleh | Status terverifikasi |
|---|---|---|
| `mongod` | systemd | aktif, enabled |
| `nginx` | systemd | aktif, enabled |
| `meilisearch` | systemd | aktif, enabled |
| `redis-server` | systemd (`/usr/lib/systemd/system/redis-server.service`) | **aktif, enabled**, hidup sejak 26 Agu, `127.0.0.1:6379`, RAM 3,9 MB |
| Backend AMAN | **supervisor**, program `inventarisasi-backend` | **RUNNING** |

Dua hal yang sekarang **terjawab**:

1. **Backend berjalan di supervisor, bukan systemd.** `scripts/deploy_vps.sh`
   me-restart lewat `supervisorctl restart inventarisasi-backend`. Unit
   `aman-backend.service` tidak pernah ada — menanyakannya ke systemd selalu
   menjawab "tidak ada" dan **terbaca seolah backend mati padahal sehat**.
   Jangan pakai systemd sebagai penanda hidup-matinya.
2. **Redis hidup dan terlindungi.** `redis-cli ping` menjawab
   `(error) NOAUTH Authentication required` — itu **bukan kegagalan**, itu
   `requirepass` bekerja persis seperti yang diminta `docs/REDIS.md`. Redis
   mendengar hanya di `127.0.0.1`.

> **KOREKSI — inventaris putaran pertama melaporkan `redis-server` "unit tidak
> ada", dan itu salah.** Unitnya loaded, enabled, dan running sejak tiga hari.
> Dari laporan palsu itu dokumen ini sempat menyimpulkan bahwa cache aplikasi
> mungkin jatuh diam-diam ke Mongo dan itulah sebab beban satu core. **Dugaan
> itu batal.**
>
> Sebabnya bukan systemd, melainkan bentuk perintah di alat inventarisnya:
>
> ```bash
> set -o pipefail; seq 1 2000000 | grep -q "^1$"; echo $?
> 1        # "tidak cocok" — padahal 1 jelas ada
> ```
>
> `grep -q` berhenti pada kecocokan PERTAMA lalu menutup pipa; produsennya kena
> SIGPIPE; `pipefail` menjadikan seluruh pipeline gagal **meski grep-nya
> cocok**. Karena hasilnya bergantung pada balapan siapa-selesai-menulis-duluan,
> ia lolos di mesin uji dan menggigit di produksi — dan hanya pada SEBAGIAN
> unit, yang membuatnya tampak seperti temuan nyata alih-alih bug.
>
> Sudah diperbaiki: `systemctl show -p LoadState --value` menjawab pertanyaan
> yang sama dengan satu perintah tanpa pipa. Uji perilaku di
> `backend/tests/unit/test_inventaris_vps.py` menjalankan skripnya dengan
> `systemctl` tiruan yang sengaja memuntahkan keluaran besar, dan gagal bila
> cacat ini dipasang kembali.
>
> **Pelajarannya bukan tentang shell.** Bacaan mesin lebih dipercaya daripada
> laporan lisan — itulah alasan alat ini ada — tetapi alatnya sendiri tetap
> perangkat lunak yang bisa salah. Temuan tunggal yang mengejutkan (satu
> layanan hilang sementara tetangganya baik-baik saja) layak dikonfirmasi
> dengan perintah kedua yang berbeda bentuk, sebelum dijadikan dasar hipotesis.

**Yang masih terbuka:** beban satu core datar itu **belum ada penjelasannya**.
Tersangka "cache jatuh ke Mongo" gugur bersama koreksi di atas. Inventaris
putaran berikutnya menyertakan sampel kedua `top`, yang menyebut nama proses
pemakannya langsung.

Perintah pemastinya, bila ingin dijalankan manual (semuanya hanya membaca):

```bash
supervisorctl status                                   # backend AMAN hidup?
systemctl status redis-server --no-pager               # unit Redis
redis-cli ping                                         # NOAUTH = sehat + ber-sandi
grep -c REDIS_URL /var/www/inventarisasi/backend/.env  # jalur LENGKAP-nya
```

> Catatan kecil yang menyelamatkan salah baca: `.env` ada di
> `/var/www/inventarisasi/backend/.env` (lihat `APP_DIR` di
> `scripts/deploy_vps.sh`). Menjalankan `grep ... backend/.env` dari `/root`
> menjawab *No such file or directory* — itu jalur yang salah, bukan berkas
> yang hilang.


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
- `fail2ban` untuk SSH — **terverifikasi 29 Agu 2026: belum terpasang**. Bila dipasang, masukkan rentang IP GitHub Actions ke `ignoreip` sejak awal, jika tidak deploy otomatis akan memblokir dirinya sendiri.
- Kredensial yang pernah bocor di riwayat chat/repo (JWT_SECRET, kunci API) **wajib dirotasi** — pengingat yang sama dengan sebelumnya.

## 4. Urutan prioritas (paling berdampak dulu)

1. **Identifikasi sumber CPU 51%** (blok A) — semua langkah lain menunggu diagnosis ini; jangan restart-restart sebelum tahu penyebab. **Masih terbuka per 29 Agu 2026, dan buktinya menguat**: beban 1,02 · 1,01 · 1,01 pada 2 vCPU adalah satu core terbakar terus-menerus, datar di ketiga jendela waktu — pola satu proses, bukan pola beban pengguna.
2. **Deploy aplikasi terbaru** → indeks komposit `assets` terpasang otomatis (menghilangkan tersangka #2 secara permanen).
3. ~~**Pasang swap 4 GB + swappiness 10** (blok B)~~ — ✅ **selesai** (verifikasi 18 Agu 2026).
4. **Batasi WiredTiger 2 GB + profiler slowms** (blok C).
5. **Pemeriksaan keamanan dasar** (blok F).
6. **Plafon log/journal + verifikasi logrotate + backup cron** (blok D/E).
7. Peninjauan bulanan: `$indexStats`, `ncdu`, `system.profile`.

### 19 Agustus 2026 sore — gejalanya akhirnya bernama

Setelah probe `ssh-keyscan` diganti koneksi `ssh` langsung, pesan galatnya
menjadi spesifik:

```
ssh: connect to host *** port 22: Connection timed out
```

**Timed out**, bukan *refused*. Bedanya menentukan:

| Gejala | Artinya |
|---|---|
| `Connection refused` | sshd mati / port tertutup — mesin menjawab |
| `No route to host` | jaringan tak menemukan mesinnya |
| **`Connection timed out`** | **paket SYN dijatuhkan diam-diam** — persis aturan `iptables DROP` milik fail2ban |

Konsekuensinya untuk anggaran retry: **jendela yang lebih pendek daripada masa
blokir tak pernah berhasil**, seberapa pun banyak percobaannya — ia hanya
menunggu di dalam blokir lalu menyerah tepat sebelum blokirnya berakhir.
`bantime` bawaan fail2ban 10 menit, sementara jendela saat itu 6 menit.

Jendela karena itu diperpanjang jadi ~14 menit (5 percobaan berjeda 180 detik)
— tetap sedikit percobaan supaya tak menambah tekanan, tetapi cukup sabar untuk
melewati blokir 10 menit.

> **KOREKSI 29 Agustus 2026 — dugaan di bawah ini terbantah sebagian.**
> Inventaris VPS membaca langsung: `fail2ban-client` **tidak ada**, dan
> `fail2ban` **tidak ada di daftar paket APT**. fail2ban tidak pernah
> terpasang di mesin ini, jadi ia **tidak mungkin** yang menjatuhkan paket.
>
> Yang tetap berlaku: bacaan `Connection timed out` di atas benar, dan
> maknanya tak berubah — paket SYN **dijatuhkan diam-diam**, bukan ditolak.
> Yang berubah hanya SIAPA yang menjatuhkannya. Karena bukan VPS-nya, sisa
> tersangkanya ada di **hulu**: firewall atau proteksi DDoS penyedia, atau
> penyaringan di jalur antara runner GitHub dan Jakarta.
>
> Angka `bantime` 10 menit yang mendasari jendela retry ~14 menit karena itu
> **kehilangan dasarnya**. Jendelanya sendiri tidak diubah: ia sudah terbukti
> cukup pada semua deploy sesudahnya, dan mempersempitnya sekarang hanya
> menukar masalah yang sudah tenang dengan risiko baru tanpa imbalan. Yang
> dicatat di sini adalah bahwa **alasan angkanya tidak lagi sahih** — supaya
> orang berikutnya tak menyetelnya berdasarkan bantime yang tak pernah ada.

Perintah yang dulu dianjurkan untuk memastikannya **tidak akan jalan** di VPS
ini (`fail2ban-client: command not found`):

```
fail2ban-client status sshd     # ← TIDAK ADA di mesin ini
```

Gantinya, bila `Connection timed out` terulang, yang perlu ditanyakan ada di
sisi penyedia — apakah ada proteksi DDoS/rate-limit port 22 pada VPS ini, dan
apakah rentang IP runner GitHub bisa dikecualikan. Di sisi VPS yang masih bisa
diperiksa sendiri:

```
ss -tulpn | grep ':22'          # sshd memang mendengar?
journalctl -u ssh --since '1 hour ago' | tail -50
ufw status verbose              # ufw terpasang — pastikan 22 tidak ter-rate-limit
```

Bila kelak `fail2ban` dipasang (§3f masih menganjurkannya), masukkan rentang
IP GitHub Actions ke `ignoreip` **sejak awal** — supaya dugaan ini tidak
menjadi kenyataan di kemudian hari.

### 19 Agustus 2026 — dua kegagalan beruntun, dan dugaan yang menunjuk diri sendiri

Delapan deploy sukses pada hari itu (01:58–06:22). Lalu:

| Waktu (UTC) | Hasil |
|---|---|
| 07:15 | gagal — 8 percobaan, jendela 6 menit habis |
| 07:45 | gagal — 8 percobaan, jendela 6 menit habis |

Keduanya berhenti di tahap `ssh-keyscan`: port 22 tidak pernah menjawab, belum
sampai autentikasi.

**Yang menuntut kejujuran:** kegagalan pertama terjadi tepat pada run PERTAMA
yang memakai jendela retry lebar (8 percobaan) yang dipasang sehari sebelumnya
sebagai jawaban atas insiden 18 Agustus. Cerita yang konsisten dengan seluruh
fakta: blip sesaat → 8 percobaan beruntun → fail2ban/proteksi penyedia membaca
polanya sebagai percobaan penyusupan → IP runner diblokir → semua deploy
sesudahnya gagal.

**TERBANTAH 29 Agu 2026** — inventaris VPS membaca `fail2ban` tidak terpasang sama sekali di mesin ini, jadi ia bukan pelakunya; lihat kotak koreksi di atas. Tapi
rancangan retry sudah diubah karena perubahannya lebih baik pada KEDUA
kemungkinan: kesabaran dipertahankan (~6 menit) sementara tekanan dikurangi
separuh (4 percobaan berjeda 75 detik), probe `ssh-keyscan` dihapus sehingga
tiap percobaan hanya satu koneksi, dan hanya kegagalan tingkat koneksi (ssh
exit 255) yang diulang.

**Pelajaran yang layak diingat:** anggaran retry tak boleh disusun seolah ujung
sana pasif. Kesabaran dan tekanan adalah dua hal berbeda — memperpanjang yang
pertama dengan menambah yang kedua bisa menciptakan kegagalan yang hendak
dicegah.


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
