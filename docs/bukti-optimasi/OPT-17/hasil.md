# OPT-17 — Inventaris tersanitasi yang dapat dibaca melalui Checks API

Tooling inventaris baca-saja selesai. Bukti inventaris produksi harus diambil
sesudah workflow baru tersedia di main; angka kapasitas produksi tidak diisi
berdasarkan mesin cloud pengembangan ini.

## Perubahan

Workflow manual `Inventaris VPS (sanitized)` mengantre pada grup `deploy-vps`,
menjalankan satu pembacaan SSH, memvalidasi JSON pada runner, lalu membuat check
run pada SHA workflow yang tepat. Output check dibatasi 48 KiB dan hanya berisi
schema tetap. Hasil dapat diambil lewat REST Checks API ketika unduhan log
Actions tidak tersedia. Workflow lama tetap tersedia untuk kegunaan historis;
check baru tidak menyalin catatan pemilik, daftar proses, atau keluaran mentah.

`scripts/inventaris_vps_json.py` tidak menerima argumen target/jalur. Ia membaca
CPU, RAM, swap, disk/inode, load, jumlah proses uvicorn/gunicorn dan FD yang
teramati; versi Python sistem/venv, Node/Yarn, Mongo/Redis/nginx/Meili; state
systemd dan supervisor; SHA checkout dan digest manifest frontend. Pemindaian
proses dibatasi 4.096 entri dan tidak membaca/mencetak argv, user atau PID.
Pemanggilan Corepack tidak boleh mengunduh package manager saat inventaris.

Pembacaan Mongo menggunakan kredensial instalasi secara internal untuk ping,
versi/topologi, jumlah indeks, writeConcern acknowledged, status restore,
jumlah writer lease/job/unduhan aktif, serta umur sukses backup yang TERCATAT.
Ia tidak menyatakan timestamp legacy sebagai bukti arsip durable. Direktori
backup dibaca hanya untuk jumlah/ukuran/umur/beda device, tanpa nama/path arsip.
Kehadiran konfigurasi Redis/Meili/offsite/key hanya boolean dari field aplikasi
yang dikenal; `false` bukan bukti tidak adanya backup eksternal di luar aplikasi.

Probe health lokal yang sudah ada menyimpan hanya status HTTP, boolean dependency,
latensi numerik Mongo/GridFS/Redis, jumlah indeks gagal dan maintenance.
HTTP503 dependency primer dibedakan dari HTTP200 Redis/index warning serta
restore recovery. Exception driver, URL, hostname, data dokumen, username,
konfigurasi, search term, NIP, token dan isi foto tidak masuk output.

Validator menolak field asing, tipe yang salah, release digest yang bukan SHA,
versi/state yang bukan grammar/enum yang dikenal, angka tidak terbatas, dan
string arbitrary. Keluaran remote mentah tidak dicetak ke summary/check.

## Verifikasi

13 tes membuktikan sentinel password/hostname/user/internal collection/driver
error tidak muncul; nilai/field berbahaya ditolak; HTTP503, warning dependency
opsional, dan maintenance dibedakan; script tidak memiliki operasi tulis;
workflow hanya manual, permission minimal, limit output dan exact SHA dijaga.
Collect dan validasi lokal berhasil. Ini bukan bukti versi/topologi produksi.

Setelah workflow ada di main, jalankan manual dan ambil check:

```sh
gh workflow run inventaris-vps-json.yml --ref main
gh api repos/ModernIlham/NEW-AMAN-IKN/commits/RELEASE_SHA/check-runs \
  --jq '.check_runs[] | select(.name == "Inventaris VPS (sanitized)") | .output.summary'
```

Simpan JSON tersanitasi yang benar-benar dibaca beserta run URL/SHA/tanggal.
Tidak perlu mengunduh log penuh atau menambah jalur baca file arbitrary.

## Batas penyelesaian operasional

`capacity_claim=inventory_only_not_a_load_test`: jumlah pengguna/throughput belum
boleh dijanjikan dari inventaris ini. OPT-16 membuktikan workload dan kapasitas.
Latency health snapshot bukan distribusi p95/p99 semua route atau ukuran pool
wait. Reuse request ID/JSON log yang ada untuk pengukuran tersebut; collector
baru tidak dipasang otomatis. Monitor eksternal, pemilik kanal alert, interval,
dedup dan uji kegagalan/pemulihan aktual tetap membutuhkan konfigurasi operasional
yang disepakati. Tool ini tidak mengirim notifikasi atau mengklaim monitor hidup
hanya karena konfigurasi tersedia.
