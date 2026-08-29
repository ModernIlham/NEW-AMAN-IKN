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
versi ffmpeg       ffmpeg -version
versi git          git --version
versi certbot      certbot --version
versi fail2ban-client fail2ban-client --version

judul "Layanan systemd yang relevan"
baris "| Unit | Aktif | Otomatis saat boot |"
baris "|---|---|---|"
for unit in mongod nginx redis-server meilisearch aman-backend aman fail2ban; do
  if systemctl list-unit-files "$unit.service" >/dev/null 2>&1 \
     && systemctl list-unit-files "$unit.service" 2>/dev/null | grep -q "^$unit.service"; then
    baris "| \`$unit\` | $(systemctl is-active "$unit" 2>/dev/null || echo '?') | $(systemctl is-enabled "$unit" 2>/dev/null || echo '?') |"
  else
    baris "| \`$unit\` | – (unit tidak ada) | – |"
  fi
done

judul "Paket APT yang dipasang manual"
baris '```'
apt-mark showmanual 2>/dev/null | sort | tr '\n' ' ' | fold -s -w 100 | head -c 20000 || baris '?'
baris ""
baris '```'
