#!/usr/bin/env bash
# Update aplikasi AMAN di VPS Hostinger ke commit main yang sudah disetujui.
#
# Dijalankan otomatis oleh workflow "Deploy ke Hostinger VPS" lewat SSH,
# atau manual di VPS:  bash scripts/deploy_vps.sh <SHA-lengkap-yang-lulus-CI>
#
# ── Sifat deploy: SHA tetap, env privat, pemulihan setiap fase ──
#
# 1. PAGAR MEMORI. `yarn build` di VPS tanpa swap adalah kandidat OOM paling
#    besar di seluruh sistem. `grep -rn NODE_OPTIONS scripts/` dulu menemukan
#    pagar itu di vps-deploy.sh dan update-all.sh, TETAPI TIDAK di berkas ini —
#    justru skrip yang benar-benar dipakai otomatislah satu-satunya tanpa pagar.
#
# 2. BUILD KE DIREKTORI SEMENTARA. react-scripts memanggil `fs.emptyDirSync`
#    di awal build, dan docroot nginx menunjuk LANGSUNG ke frontend/build
#    (vps-deploy.sh: `root ${APP_DIR}/frontend/build`). Artinya setiap deploy
#    mengosongkan docroot lalu mengisinya ulang selama puluhan detik: sepanjang
#    itu pengunjung mendapat 404. Membangun ke `build.new` lalu menukar dengan
#    `mv` memperkecil jendela itu dari "selama build" menjadi "dua panggilan
#    rename" — dan `build.old` menjadi rollback frontend instan.
#
# 3. ROLLBACK BERDASARKAN FASE. EXIT mengompensasi semua kegagalan setelah
#    kode disentuh, termasuk dependency/build/rename/sinyal. Pemulihan baru
#    diumumkan berhasil setelah SHA, docroot, dan kedua health check terbukti.
# Helper bersama juga dipakai update-all.sh lewat source. Tetap berada di
# berkas ini: workflow mengirim HANYA deploy_vps.sh melalui stdin ke VPS.
# Source hanya mendefinisikan helper; tidak menjalankan deploy atau memasang trap.
aman_env_bersihkan() {
  local rc=$?
  trap - EXIT
  if [ -n "${AMAN_ENV_STAGE:-}" ]; then
    case "$AMAN_ENV_STAGE" in
      "$AMAN_ENV_APP_DIR"/backend/.env-restore.*|"$AMAN_ENV_APP_DIR"/frontend/.env-restore.*)
        rm -f -- "$AMAN_ENV_STAGE" || rc=1 ;;
      *) echo "GAGAL: jalur staging env tidak sesuai; tidak dihapus." >&2; rc=1 ;;
    esac
  fi
  if [ "${AMAN_ENV_PULIH_GAGAL:-0}" = 1 ]; then
    echo "PEMULIHAN ENV GAGAL: salinan privat dipertahankan di $AMAN_ENV_TMP_DIR; periksa sebelum membersihkan." >&2
    [ "$rc" -ne 0 ] || rc=1
  elif [ -n "${AMAN_ENV_TMP_DIR:-}" ]; then
    case "$AMAN_ENV_TMP_DIR" in
      /tmp/aman-env.??????????)
        if [ ! -L "$AMAN_ENV_TMP_DIR" ] && [ -d "$AMAN_ENV_TMP_DIR" ] \
            && [ "$(stat -c %u -- "$AMAN_ENV_TMP_DIR")" = "$EUID" ]; then
          if ! rm -f -- "$AMAN_ENV_TMP_DIR/backend.env" "$AMAN_ENV_TMP_DIR/frontend.env" \
              || ! rmdir -- "$AMAN_ENV_TMP_DIR"; then
            echo "GAGAL: salinan env sementara belum seluruhnya dibersihkan." >&2
            rc=1
          else
            echo "Salinan konfigurasi sementara sudah dibersihkan."
          fi
        else
          echo "GAGAL: direktori salinan env berubah; tidak dihapus." >&2
          rc=1
        fi ;;
      *) echo "GAGAL: jalur salinan env tidak sesuai; tidak dihapus." >&2; rc=1 ;;
    esac
  fi
  exit "$rc"
}

aman_env_siapkan() {
  local komponen sumber wajib="${2:-1}"
  AMAN_ENV_APP_DIR="$(cd -- "$1" && pwd -P)" || return 1
  if [ "$AMAN_ENV_APP_DIR" = / ]; then
    echo "GAGAL: direktori aplikasi tidak boleh akar filesystem." >&2
    return 1
  fi
  for komponen in backend frontend; do
    sumber="$AMAN_ENV_APP_DIR/$komponen/.env"
    if [ -L "$AMAN_ENV_APP_DIR/$komponen" ] || [ ! -d "$AMAN_ENV_APP_DIR/$komponen" ] \
        || [ -L "$sumber" ] || { [ -e "$sumber" ] && [ ! -f "$sumber" ]; }; then
      echo "GAGAL: $komponen/.env harus berkas biasa di direktori aplikasi, bukan symlink." >&2
      return 1
    fi
    if [ "$wajib" = 1 ] && [ ! -f "$sumber" ]; then
      echo "GAGAL: $komponen/.env wajib tersedia sebelum deploy." >&2
      return 1
    fi
  done
  AMAN_ENV_TMP_DIR="$(umask 077; mktemp -d /tmp/aman-env.XXXXXXXXXX)" || return 1
  AMAN_ENV_STAGE=""
  AMAN_ENV_PULIH_GAGAL=0
  trap aman_env_bersihkan EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  chmod 700 -- "$AMAN_ENV_TMP_DIR" || return 1
  for komponen in backend frontend; do
    sumber="$AMAN_ENV_APP_DIR/$komponen/.env"
    # Ketidakhadiran asli dicatat dengan tidak adanya snapshot. Jangan pernah
    # menghidupkan konfigurasi dari salinan run lama ketika sumbernya hilang.
    if [ -f "$sumber" ]; then
      cp -p -- "$sumber" "$AMAN_ENV_TMP_DIR/$komponen.env" || return 1
      chmod 600 -- "$AMAN_ENV_TMP_DIR/$komponen.env" || return 1
    fi
  done
}

aman_env_pasang() {
  local komponen tujuan
  for komponen in backend frontend; do
    [ -f "$AMAN_ENV_TMP_DIR/$komponen.env" ] || continue
    tujuan="$AMAN_ENV_APP_DIR/$komponen/.env"
    if [ -L "$AMAN_ENV_APP_DIR/$komponen" ] || [ ! -d "$AMAN_ENV_APP_DIR/$komponen" ] \
        || [ -L "$tujuan" ] || { [ -e "$tujuan" ] && [ ! -f "$tujuan" ]; }; then
      AMAN_ENV_PULIH_GAGAL=1
      echo "GAGAL: tujuan pemulihan $komponen/.env tidak aman." >&2
      return 1
    fi
    # Staging ada pada filesystem tujuan. Kegagalan cp tidak memotong .env
    # aktif; rename mengganti inode (tidak mengikuti hardlink/symlink tujuan).
    AMAN_ENV_STAGE="$(umask 077; mktemp "$AMAN_ENV_APP_DIR/$komponen/.env-restore.XXXXXXXXXX")" || {
      AMAN_ENV_PULIH_GAGAL=1; return 1;
    }
    if ! cp -p -- "$AMAN_ENV_TMP_DIR/$komponen.env" "$AMAN_ENV_STAGE" \
        || ! chmod 600 -- "$AMAN_ENV_STAGE" \
        || ! mv -fT -- "$AMAN_ENV_STAGE" "$tujuan"; then
      AMAN_ENV_PULIH_GAGAL=1
      echo "GAGAL: pemulihan atomik $komponen/.env; salinan asli tetap diamankan." >&2
      return 1
    fi
    AMAN_ENV_STAGE=""
  done
}

if [[ -n "${BASH_SOURCE[0]:-}" && "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

set -euo pipefail

APP_DIR="${APP_DIR:-/var/www/inventarisasi}"
# Cabang tujuan bisa diganti untuk uji coba; bawaannya main.
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
# Argumen pertama menang atas environment supaya pemanggil otomatis tidak bisa
# berubah sasaran karena environment lama yang tertinggal di server.
DEPLOY_SHA="${1:-${DEPLOY_SHA:-}}"
# Mode otomatis wajib monoton; mode manual boleh memilih commit CI lama untuk
# rollback operator yang disengaja. Argumen kedua kembali menang atas env.
DEPLOY_MODE="${2:-${DEPLOY_MODE:-manual}}"

if [[ ! "$DEPLOY_SHA" =~ ^[0-9A-Fa-f]{40}$ ]]; then
  echo "DEPLOY DIBATALKAN: berikan DEPLOY_SHA berupa commit SHA lengkap 40 karakter." >&2
  echo "Contoh: bash scripts/deploy_vps.sh 0123456789abcdef0123456789abcdef01234567" >&2
  exit 2
fi
DEPLOY_SHA="${DEPLOY_SHA,,}"
if [[ "$DEPLOY_MODE" != "otomatis" && "$DEPLOY_MODE" != "manual" ]]; then
  echo "DEPLOY DIBATALKAN: DEPLOY_MODE hanya boleh 'otomatis' atau 'manual'." >&2
  exit 2
fi
cd "$APP_DIR"

# Commit yang SEDANG melayani produksi — tujuan rollback bila deploy gagal.
PREV="$(git rev-parse HEAD)"
echo "Commit saat ini (titik pulang bila gagal): $(git rev-parse --short HEAD)"

# Kontrol restore tidak memakai TTL: restore yang terhenti setelah wipe tetap
# memblokir deploy sampai recovery selesai. Mutex GLOBAL juga mencegah restore
# baru dimulai di antara pemeriksaan dan restart. Pemeriksa gagal = fail closed.
AMAN_DEPLOY_OWNER="deploy:${BASHPID}:$(date +%s):${RANDOM}${RANDOM}"
AMAN_DEPLOY_LOCK=0
kelola_kontrol_restore() {
  local tindakan="$1" uri dbn
  if [ -x backend/venv/bin/python ]; then
    AMAN_GUARD_ACTION="$tindakan" AMAN_GUARD_OWNER="$AMAN_DEPLOY_OWNER" backend/venv/bin/python - <<'PYGUARD'
import os
import sys
from datetime import datetime, timedelta, timezone
try:
    from dotenv import dotenv_values
    from pymongo import MongoClient, ReturnDocument
    from pymongo.errors import DuplicateKeyError
    config = dotenv_values("backend/.env")
    uri = config.get("MONGO_URL")
    if not uri:
        raise ValueError("MONGO_URL tidak tersedia")
    with MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                     socketTimeoutMS=5000) as client:
        db = client[config.get("DB_NAME") or "inventaris_bmn"]
        action = os.environ["AMAN_GUARD_ACTION"]
        owner = os.environ["AMAN_GUARD_OWNER"]
        terminal = ["completed", "rolled_back", "aborted"]
        now = datetime.now(timezone.utc).isoformat()
        if action == "drain":
            writers = db.restore_write_leases.count_documents({}, maxTimeMS=5000)
            jobs = db.unduhan.count_documents({"status": {"$in": ["queued", "running"]}}, maxTimeMS=5000)
            detached = db.background_jobs.count_documents({
                "status": {"$nin": ["done", "error", "completed", "failed", "cancelled", "canceled", "dismissed", "downloaded"]},
                "done": {"$ne": True},
                "$nor": [{"worker_protocol": "export_v1", "status": "queued"}]}, maxTimeMS=5000)
            print(1 if writers or jobs or detached else 0)
        elif action == "release":
            result = db.restore_control.update_one(
                {"_id": "GLOBAL", "state": "deploying", "owner": owner},
                {"$set": {"state": "completed", "active": False,
                          "updated_at": now, "completed_at": now}})
            print(0 if result.matched_count == 1 else 1)
        else:
            control = db.restore_control.find_one({"_id": "GLOBAL"})
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            legacy = db.backup_jobs.count_documents({
                "type": "restore", "active_lock": "GLOBAL",
                "status": {"$in": ["queued", "running"]},
                "updated_at": {"$gt": cutoff}})
            blocked = bool(legacy or (control and control.get("state") not in terminal))
            if action == "acquire" and not blocked:
                try:
                    claimed = db.restore_control.find_one_and_update(
                        {"_id": "GLOBAL", "state": {"$in": terminal}},
                        {"$set": {"state": "deploying", "owner": owner,
                                  "active": True, "destructive_started": False,
                                  "updated_at": now}}, upsert=True,
                        return_document=ReturnDocument.AFTER)
                    blocked = not claimed or claimed.get("owner") != owner
                except DuplicateKeyError:
                    blocked = True
            print(1 if blocked else 0)
except Exception:
    # Jangan cetak exception Mongo: dapat memuat URI/kredensial produksi.
    print("GAGAL: status kontrol restore tidak dapat diverifikasi.", file=sys.stderr)
    sys.exit(1)
PYGUARD
    return $?
  fi
  if ! command -v mongosh >/dev/null 2>&1; then
    echo "GAGAL: pemeriksa restore membutuhkan backend/venv/bin/python atau mongosh." >&2
    return 1
  fi
  uri="$(grep -E '^MONGO_URL=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  dbn="$(grep -E '^DB_NAME=' backend/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' || true)"
  [ -n "$uri" ] || { echo "GAGAL: MONGO_URL tidak tersedia; deploy dibatalkan." >&2; return 1; }
  case "$uri" in
    *\?*) uri="${uri}&serverSelectionTimeoutMS=5000&connectTimeoutMS=5000&socketTimeoutMS=5000" ;;
    *) uri="${uri}?serverSelectionTimeoutMS=5000&connectTimeoutMS=5000&socketTimeoutMS=5000" ;;
  esac
  AMAN_GUARD_ACTION="$tindakan" AMAN_GUARD_OWNER="$AMAN_DEPLOY_OWNER" \
    AMAN_GUARD_DB="${dbn:-inventaris_bmn}" mongosh "$uri" --quiet --eval '
      db = db.getSiblingDB(process.env.AMAN_GUARD_DB);
      const action = process.env.AMAN_GUARD_ACTION;
      const owner = process.env.AMAN_GUARD_OWNER;
      const terminal = ["completed", "rolled_back", "aborted"];
      const now = new Date().toISOString();
      if (action === "drain") {
        const writers = db.restore_write_leases.countDocuments({}, {maxTimeMS:5000});
        const jobs = db.unduhan.countDocuments({status:{$in:["queued","running"]}}, {maxTimeMS:5000});
        const detached = db.background_jobs.countDocuments({
          status:{$nin:["done","error","completed","failed","cancelled","canceled","dismissed","downloaded"]},
          done:{$ne:true}, $nor:[{worker_protocol:"export_v1",status:"queued"}]}, {maxTimeMS:5000});
        print(writers || jobs || detached ? 1 : 0);
      } else if (action === "release") {
        const result = db.restore_control.updateOne({_id:"GLOBAL", state:"deploying", owner},
          {$set:{state:"completed", active:false, updated_at:now, completed_at:now}});
        print(result.matchedCount === 1 ? 0 : 1);
      } else {
        const control = db.restore_control.findOne({_id:"GLOBAL"});
        const cutoff = new Date(Date.now() - 30*60*1000).toISOString();
        const legacy = db.backup_jobs.countDocuments({type:"restore", active_lock:"GLOBAL",
          status:{$in:["queued","running"]}, updated_at:{$gt:cutoff}});
        let blocked = !!legacy || !!(control && !terminal.includes(control.state));
        if (action === "acquire" && !blocked) {
          try {
            const claimed = db.restore_control.findOneAndUpdate(
              {_id:"GLOBAL", state:{$in:terminal}},
              {$set:{state:"deploying", owner, active:true, destructive_started:false, updated_at:now}},
              {upsert:true, returnDocument:"after"});
            blocked = !claimed || claimed.owner !== owner;
          } catch (error) { if (error.code === 11000) blocked = true; else throw error; }
        }
        print(blocked ? 1 : 0);
      }' 2>/dev/null
}
periksa_restore_aktif() {
  local hasil
  if ! hasil="$(kelola_kontrol_restore check)" || [ "$hasil" != 0 ]; then
    echo "DEPLOY DIBATALKAN: restore aktif, recovery_required, deployment lain, atau status Mongo tidak dapat dipastikan." >&2
    echo "Periksa restore_control GLOBAL dan pulihkan data sebelum deploy ulang; jangan menghapus lock restore." >&2
    return 1
  fi
}
periksa_restore_aktif

# .env privat: pertahankan helper EXIT bersama update-all.sh. Trap deploy
# membungkus helper, sehingga snapshot tetap dibersihkan pada semua jalur.
aman_env_siapkan "$APP_DIR" 1
DEPLOY_FASE=preflight
KODE_TERSENTUH=0
DEPENDENSI_TERSENTUH=0
FRONTEND_LAMA_DIPINDAH=0
FRONTEND_BARU_DICOBA=0
FRONTEND_SEBELUMNYA=0
DEPLOY_SELESAI=0
AMAN_DEPLOY_RECOVERY=0
PERCOBAAN_KESEHATAN=45
HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8001/api/health}"
DEEP_HEALTH_URL="${BACKEND_DEEP_HEALTH_URL:-http://127.0.0.1:8001/api/health/deep}"

pasang_env() { aman_env_pasang; }
pasang_dependensi_backend() {
  if [ -x backend/venv/bin/pip ]; then
    backend/venv/bin/pip install -q -r backend/requirements.txt
  fi
}
restart_backend() {
  sudo -n supervisorctl restart inventarisasi-backend 2>/dev/null \
    || supervisorctl restart inventarisasi-backend
}
periksa_kesehatan() {
  local i gagal=0
  echo "Cek kesehatan backend di ${HEALTH_URL} ..."
  for i in $(seq 1 "$PERCOBAAN_KESEHATAN"); do
    if curl -fsS --max-time 3 "$HEALTH_URL" >/dev/null 2>&1; then break; fi
    if [ "$i" -eq "$PERCOBAAN_KESEHATAN" ]; then
      echo "GAGAL: backend tidak sehat (health-check timeout)." >&2
      gagal=1
    else
      sleep 2
    fi
  done
  [ "$gagal" = 0 ] || return 1
  echo "Cek kesehatan mendalam (Mongo+GridFS) di ${DEEP_HEALTH_URL} ..."
  for i in $(seq 1 "$PERCOBAAN_KESEHATAN"); do
    if curl -fsS --max-time 5 "$DEEP_HEALTH_URL" >/dev/null 2>&1; then break; fi
    if [ "$i" -eq "$PERCOBAAN_KESEHATAN" ]; then
      echo "GAGAL: dependensi backend tidak sehat (deep health 503/timeout)." >&2
      gagal=1
    else
      sleep 2
    fi
  done
  [ "$gagal" = 0 ]
}

# Kompensasi memakai keadaan filesystem nyata, bukan asumsi bahwa perintah
# terakhir selesai. Flag dipasang SEBELUM rename supaya TERM setelah rename
# tetapi sebelum assignment tetap memulihkan frontend yang benar.
pulihkan() {
  local gagal=0
  echo "ROLLBACK fase ${DEPLOY_FASE}: kembali ke ${PREV} ..." >&2
  cd "$APP_DIR" || return 1
  git reset --hard "$PREV" || gagal=1
  pasang_env || gagal=1
  if [ "$DEPENDENSI_TERSENTUH" = 1 ]; then
    pasang_dependensi_backend || { echo "ROLLBACK: pip install GAGAL." >&2; gagal=1; }
  fi
  if [ "$FRONTEND_LAMA_DIPINDAH" = 1 ] && [ -d frontend/build.old ]; then
    if rm -rf -- frontend/build; then
      mv frontend/build.old frontend/build || gagal=1
    else gagal=1; fi
  elif [ "$FRONTEND_SEBELUMNYA" = 1 ] && [ ! -f frontend/build/index.html ]; then
    echo "ROLLBACK: docroot sebelumnya tidak tersedia." >&2; gagal=1
  elif [ "$FRONTEND_SEBELUMNYA" = 0 ] && [ "$FRONTEND_BARU_DICOBA" = 1 ]; then
    rm -rf -- frontend/build || gagal=1
  fi
  restart_backend || { echo "ROLLBACK: restart backend GAGAL." >&2; gagal=1; }
  [ "$(git rev-parse HEAD)" = "$PREV" ] || gagal=1
  periksa_kesehatan || gagal=1
  if [ "$gagal" = 0 ]; then
    echo "ROLLBACK selesai: SHA dan kesehatan rilis sebelumnya terverifikasi." >&2
  else
    echo "RECOVERY_REQUIRED: rollback tidak terverifikasi; periksa kode, env, dependency, docroot, dan backend. Jangan menyatakan deploy sukses." >&2
  fi
  return "$gagal"
}
aman_deploy_keluar() {
  local rc=$? hasil
  trap - EXIT
  # Sinyal berulang jangan memutus kompensasi yang sedang memulihkan data.
  trap '' HUP INT TERM
  set +e
  if [ "$rc" -ne 0 ] && [ "$KODE_TERSENTUH" = 1 ] && [ "$DEPLOY_SELESAI" = 0 ]; then
    if ! pulihkan; then rc=70; AMAN_DEPLOY_RECOVERY=1; fi
  fi
  if [ "$AMAN_DEPLOY_LOCK" = 1 ] && [ "$AMAN_DEPLOY_RECOVERY" = 0 ]; then
    if ! hasil="$(kelola_kontrol_restore release)" || [ "$hasil" != 0 ]; then
      echo "RECOVERY_REQUIRED: mutex deployment tidak dapat dilepas; periksa restore_control GLOBAL milik run ini." >&2
      rc=70
    fi
  elif [ "$AMAN_DEPLOY_RECOVERY" = 1 ]; then
    echo "Mutex deployment dipertahankan: $AMAN_DEPLOY_OWNER; pemulihan operator wajib sebelum run berikutnya." >&2
  fi
  # aman_env_bersihkan mengambil status perintah sebelumnya. Jangan menimpa
  # exit kegagalan asli atau 70 ketika pemulihan belum terbukti.
  (exit "$rc")
  aman_env_bersihkan
}
trap aman_deploy_keluar EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# ── Ambil perubahan, dengan pengulangan yang SAH ────────────────────────
#
# Deploy 1 Sep 2026 gagal di sini: SSH ke VPS berhasil, skripnya jalan, lalu
#
#     fatal: unable to access 'https://github.com/…': Failed to connect to
#     github.com port 443 after 133334 ms: Couldn't connect to server
#
# Kaki jaringan yang putus bukan runner→VPS melainkan VPS→GitHub, dan workflow
# hanya mengulang kegagalan tingkat koneksi SSH (exit 255). Kegagalan ini
# exit 128, jadi tak diulang — padahal ia justru jenis yang paling pantas
# diulang.
#
# Mengulangnya DI SINI tidak melanggar aturan "jangan ulangi deploy yang sudah
# berjalan" (lihat deploy.yml dan test_jendela_retry_deploy.py). Aturan itu
# menahan pengulangan kegagalan yang MENGUBAH keadaan; `git fetch` berjalan
# SEBELUM `git reset` di bawah, jadi sampai titik ini belum ada apa pun yang
# berubah. Tiga percobaan, bukan lima: cukup melewati blip, tak cukup untuk
# terbaca sebagai tekanan.
#
# JANGAN git pull — selalu fetch lalu reset ke SHA immutable yang disetujui.
ambil_perubahan() {
  local n
  for n in 1 2 3; do
    if git fetch origin "$DEPLOY_BRANCH"; then
      return 0
    fi
    if [ "$n" -lt 3 ]; then
      echo "Percobaan $n/3 git fetch gagal — VPS belum menjangkau GitHub; ulang 30 detik…" >&2
      sleep 30
    fi
  done
  echo "GAGAL JARINGAN DI SISI VPS: github.com:443 tak terjangkau dari VPS setelah 3 percobaan." >&2
  echo "Ini BUKAN cacat kode dan BUKAN kegagalan koneksi runner→VPS. Tak ada yang diubah:" >&2
  echo "produksi tetap pada commit $(git rev-parse --short HEAD). Periksa DNS dan jalur keluar" >&2
  echo "jaringan VPS, lalu jalankan ulang deploy." >&2
  return 128
}
ambil_perubahan

# Fetch boleh melihat main yang lebih baru daripada keputusan CI. Itu tidak
# boleh mengubah target: origin/main hanya menjadi bukti bahwa SHA yang diminta
# memang commit cabang tujuan, bukan nilai yang dipasang ke produksi.
if ! git cat-file -e "${DEPLOY_SHA}^{commit}" 2>/dev/null; then
  echo "DEPLOY DIBATALKAN: commit ${DEPLOY_SHA} tidak tersedia setelah fetch." >&2
  exit 1
fi
if ! git merge-base --is-ancestor "$DEPLOY_SHA" "origin/${DEPLOY_BRANCH}"; then
  echo "DEPLOY DIBATALKAN: commit ${DEPLOY_SHA} bukan bagian origin/${DEPLOY_BRANCH}." >&2
  exit 1
fi

# Concurrency menyerialkan job tetapi rerun CI lama tetap bisa datang setelah
# rilis baru. Auto-deploy tidak boleh menurunkan produksi; rollback ke ancestor
# lama hanya sah bila operator memilih mode manual secara eksplisit.
if [ "$DEPLOY_MODE" = "otomatis" ] && [ "$DEPLOY_SHA" != "$PREV" ] \
    && git merge-base --is-ancestor "$DEPLOY_SHA" "$PREV"; then
  echo "DEPLOY DIBATALKAN: auto-deploy ${DEPLOY_SHA} lebih lama daripada HEAD produksi ${PREV}." >&2
  echo "Untuk rollback yang disengaja, jalankan deploy manual dengan SHA yang sudah lulus CI." >&2
  exit 1
fi

# Klaim mutex atomik sesudah semua validasi read-only, sebelum mutasi pertama.
if ! hasil_kontrol="$(kelola_kontrol_restore acquire)" || [ "$hasil_kontrol" != 0 ]; then
  echo "DEPLOY DIBATALKAN: mutex restore/deploy tidak tersedia." >&2
  exit 1
fi
AMAN_DEPLOY_LOCK=1
# Admission versi baru menghormati mutex deploying; pekerjaan yang sudah
# berjalan harus selesai sebelum restart membunuh proses worker. Rilis backend
# lama belum mengenal mutex ini: rollout awal tetap butuh jendela tanpa writer.
if ! hasil_kontrol="$(kelola_kontrol_restore drain)" || [ "$hasil_kontrol" != 0 ]; then
  echo "DEPLOY DIBATALKAN: writer lease, background job, atau unduhan aktif masih ada; tunggu drain sebelum restart backend." >&2
  exit 1
fi
if [ -L frontend/build ] || [ -L frontend/build.old ] || [ -L frontend/build.new ]; then
  echo "DEPLOY DIBATALKAN: jalur build tidak boleh berupa symlink." >&2
  exit 1
fi
if [ -d frontend/build ]; then FRONTEND_SEBELUMNYA=1; fi
DEPLOY_FASE=kode
KODE_TERSENTUH=1
git reset --hard "$DEPLOY_SHA"
TERPASANG="$(git rev-parse HEAD)"
if [ "$TERPASANG" != "$DEPLOY_SHA" ]; then
  echo "DEPLOY DIBATALKAN: HEAD ${TERPASANG} tidak sama dengan DEPLOY_SHA ${DEPLOY_SHA}." >&2
  exit 1
fi
echo "Commit rilis terkunci dan terpasang: $(git rev-parse --short HEAD)"
DEPLOY_FASE=env
pasang_env
DEPLOY_FASE=dependency_backend
DEPENDENSI_TERSENTUH=1
pasang_dependensi_backend
DEPLOY_FASE=restart_backend
restart_backend
DEPLOY_FASE=kesehatan_backend
periksa_kesehatan

# Bangun ke staging; install/build gagal pun mengembalikan backend + kode.
DEPLOY_FASE=dependency_frontend
cd frontend
yarn install --frozen-lockfile --ignore-engines
export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=2048}"
DEPLOY_FASE=build_frontend
rm -rf build.new
BUILD_PATH=build.new yarn build
if [ ! -f build.new/index.html ]; then
  echo "GAGAL: build.new/index.html tidak ada — build tidak menghasilkan bundel." >&2
  exit 1
fi
DEPLOY_FASE=aktivasi_frontend
rm -rf build.old
if [ -d build ]; then
  FRONTEND_LAMA_DIPINDAH=1
  mv build build.old
fi
FRONTEND_BARU_DICOBA=1
mv build.new build
cd "$APP_DIR"
DEPLOY_FASE=verifikasi_akhir
[ -f frontend/build/index.html ]
[ "$(git rev-parse HEAD)" = "$DEPLOY_SHA" ]
periksa_kesehatan
DEPLOY_SELESAI=1
# Pelepasan mutex juga wajib berhasil SEBELUM pesan sukses final.
if ! hasil_kontrol="$(kelola_kontrol_restore release)" || [ "$hasil_kontrol" != 0 ]; then
  DEPLOY_SELESAI=0
  echo "GAGAL: mutex deployment gagal dilepas." >&2
  exit 1
fi
AMAN_DEPLOY_LOCK=0
echo "Bundel frontend ditukar; salinan sebelumnya tersimpan di frontend/build.old"
echo "Deploy selesai: $(git -C "$APP_DIR" rev-parse --short HEAD)"
