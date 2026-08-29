#!/usr/bin/env bash
# Inventaris VPS — HANYA MEMBACA. Dipipe ke VPS lewat SSH oleh workflow
# "Inventaris VPS" (.github/workflows/inventaris-vps.yml).
#
# KENAPA ADA. docs/OPTIMASI-VPS.md pernah MENYESATKAN diagnosis: pada 17-18
# Agustus 2026 tiga deploy gagal dan baris "tanpa swap" di dokumen itu — yang
# berasal dari laporan lisan, bukan dari mesin — dipakai sebagai dasar dugaan
# tekanan memori. Swap ternyata sudah lama terpasang. Skrip ini menggantikan
# "laporan lisan" dengan bacaan langsung yang bisa diulang siapa saja.
#
# ATURAN KERAS, jangan dilonggarkan tanpa membaca alasannya:
#
# 1. TIDAK ADA PARAMETER JALUR BERKAS. Berkas catatan dibaca dari pola tetap
#    /root/installed-software-*.txt. Kalau jalurnya bisa dikirim dari luar,
#    workflow ini berubah menjadi "cat berkas apa pun di VPS ke dalam log
#    Actions" — /root/.env, kunci privat, URL Mongo lengkap dengan sandinya.
#    Log Actions terbaca semua kolaborator repositori dan tersimpan
#    berbulan-bulan.
# 2. TIDAK MENULIS APA PUN. Tanpa rm/mv/cp, tanpa redireksi ke berkas, tanpa
#    apt install, tanpa systemctl start|stop|restart. Skrip ini boleh
#    dijalankan pada produksi tengah hari tanpa membangunkan siapa pun.
# 3. VERSI, BUKAN KONFIGURASI. `nginx -v` boleh; `cat nginx.conf` tidak —
#    berkas konfigurasi memuat host, port dalam, dan kadang kredensial.
#
# backend/tests/unit/test_inventaris_vps.py menagih ketiganya.
set -uo pipefail

judul() { printf '\n## %s\n\n' "$1"; }
baris() { printf '%s\n' "$1"; }

# Versi satu program. Program yang tidak terpasang dicatat sebagai "-", bukan
# membuat skrip berhenti: yang belum terpasang justru informasi yang dicari.
versi() {
  local nama="$1"; shift
  if ! command -v "$nama" >/dev/null 2>&1; then
    baris "| \`$nama\` | – (tidak terpasang) |"
    return
  fi
  local out
  out="$("$@" 2>&1 | head -1 | tr -d '\r' | sed 's/|/ /g')"
  baris "| \`$nama\` | ${out:-terpasang} |"
}

judul "Catatan pemilik di VPS"
ada_catatan=0
for f in /root/installed-software-*.txt; do
  [ -e "$f" ] || continue
  ada_catatan=1
  baris "### $f"
  baris ""
  baris "Terakhir diubah: $(date -r "$f" '+%Y-%m-%d %H:%M:%S %Z' 2>/dev/null || echo '?')"
  baris ""
  baris '```'
  head -c 60000 "$f"
  baris ""
  baris '```'
done
[ "$ada_catatan" -eq 1 ] || baris "_Tidak ada berkas \`/root/installed-software-*.txt\` di VPS._"

judul "Mesin"
baris "| Aspek | Bacaan |"
baris "|---|---|"
baris "| OS | $( (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || uname -s) |"
baris "| Kernel | $(uname -r) |"
baris "| Arsitektur | $(uname -m) |"
baris "| Uptime | $(uptime -p 2>/dev/null || echo '?') |"
baris "| CPU | $(nproc) vCPU |"
baris "| Beban | $(cut -d' ' -f1-3 /proc/loadavg) |"
baris "| Memori | $(free -h 2>/dev/null | awk '/^Mem:/{print $3" / "$2" terpakai, "$7" tersedia"}') |"
baris "| Swap | $(free -h 2>/dev/null | awk '/^Swap:/{print ($2=="0B"||$2=="0"?"tidak ada":$3" / "$2" terpakai")}') |"
baris "| Disk / | $(df -h --output=used,size,pcent / 2>/dev/null | tail -1 | awk '{print $1" / "$2" ("$3")"}') |"

judul "Versi perangkat lunak terpasang"
baris "| Program | Versi |"
baris "|---|---|"
versi mongod       mongod --version
versi node         node --version
versi npm          npm --version
versi yarn         yarn --version
versi python3      python3 --version
versi pip3         pip3 --version
versi nginx        nginx -v
versi redis-server redis-server --version
versi meilisearch  meilisearch --version
versi git          git --version
versi certbot      certbot --version
versi fail2ban-client fail2ban-client --version
# Versi Python yang BENAR-BENAR menjalankan backend. `python3` sistem sering
# beda dengan isi venv, dan dokumen sempat menebak yang salah karenanya.
# APP_DIR memakai default yang sama dengan scripts/deploy_vps.sh.
if [ -x /var/www/inventarisasi/backend/venv/bin/python ]; then
  baris "| venv backend | $(/var/www/inventarisasi/backend/venv/bin/python --version 2>&1 | head -1) |"
else
  baris "| venv backend | – (tidak ditemukan di /var/www/inventarisasi) |"
fi

# Status satu unit systemd — SENGAJA TANPA PIPA.
#
# Putaran pertama memakai `systemctl list-unit-files X | grep -q "^X"` dan
# melaporkan `redis-server` "unit tidak ada", padahal unitnya loaded, enabled,
# dan running sejak tiga hari. Sebabnya bukan systemd: `grep -q` berhenti pada
# kecocokan PERTAMA lalu menutup pipa, produsennya kena SIGPIPE, dan
# `set -o pipefail` di atas menjadikan seluruh pipeline gagal — meski grep-nya
# COCOK. Karena bergantung pada balapan siapa-selesai-duluan, ia lolos di mesin
# uji dan menggigit di produksi.
#
#   $ set -o pipefail; seq 1 2000000 | grep -q "^1$"; echo $?
#   1        # "tidak cocok", padahal 1 jelas ada
#
# `systemctl show -p LoadState` menjawab pertanyaan yang sama dengan satu
# perintah tanpa pipa: `loaded`, `not-found`, atau `masked`.
status_unit() {
  local unit="$1" load aktif boot
  load="$(systemctl show -p LoadState --value "$unit.service" 2>/dev/null || true)"
  if [ "$load" = "not-found" ]; then
    baris "| \`$unit\` | – (unit tidak ada) | – |"
    return
  fi
  if [ -z "$load" ]; then
    baris "| \`$unit\` | ? (systemd tak menjawab) | ? |"
    return
  fi
  aktif="$(systemctl is-active "$unit.service" 2>/dev/null || true)"
  boot="$(systemctl is-enabled "$unit.service" 2>/dev/null || true)"
  baris "| \`$unit\` | ${aktif:-?} | ${boot:-?} |"
}

judul "Layanan systemd yang relevan"
baris "| Unit | Aktif | Otomatis saat boot |"
baris "|---|---|---|"
# `aman-backend`/`aman` DIHAPUS dari daftar: backend AMAN tidak pernah jadi
# unit systemd — ia program supervisor `inventarisasi-backend` (lihat
# scripts/deploy_vps.sh). Menanyakannya ke systemd selalu menjawab "tidak ada"
# dan terbaca seolah backend mati padahal sehat.
for unit in mongod nginx redis-server meilisearch supervisor cron fail2ban ufw; do
  status_unit "$unit"
done

judul "Program supervisor"
if command -v supervisorctl >/dev/null 2>&1; then
  baris '```'
  supervisorctl status 2>&1 | head -30
  baris '```'
else
  baris "_\`supervisorctl\` tidak ada di mesin ini._"
fi

judul "Pemakan CPU teratas"
# Menjawab pertanyaan tertua di docs/OPTIMASI-VPS.md §2 butir 1: beban 1,00
# datar pada 2 vCPU = satu core terbakar terus-menerus, oleh SIAPA?
#
# `top -b` TANPA `-c`: kolom COMMAND berisi nama program saja. Baris perintah
# lengkap (`-c`) sengaja tidak diminta — ia bisa memuat kredensial pada
# argumen, dan keluaran ini masuk ke log Actions.
baris 'Sampel kedua `top` (yang pertama selalu rata-rata sejak boot):'
baris ""
baris '```'
if command -v top >/dev/null 2>&1; then
  top -b -w 512 -n 2 -d 1 2>/dev/null | awk 'BEGIN{n=0} /^ *PID +USER/{n++} n==2{print}' | head -12
else
  baris "top tidak ada"
fi
baris '```' 

judul "Paket APT yang dipasang manual"
baris '```'
apt-mark showmanual 2>/dev/null | sort | tr '\n' ' ' | fold -s -w 100 | head -c 20000 || baris '?'
baris ""
baris '```'
