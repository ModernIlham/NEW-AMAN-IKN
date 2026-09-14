"""Uji shell nyata: salinan konfigurasi privat, atomik, dan tidak lintas run."""
import os
from pathlib import Path
import subprocess

import pytest

AKAR = Path(__file__).resolve().parents[3]
SKRIP = AKAR / "scripts" / "deploy_vps.sh"


def jalankan(tmp_path, isi):
    # Source helper yang PERSIS dikirim workflow melalui stdin. Seluruh nilai
    # sintetis dan berkas aplikasi berada di direktori uji, bukan produksi.
    pembuka = r'''
set -euo pipefail
source "$1"
APP_UJI="$(cd "$2" && pwd -P)/aplikasi uji"
mkdir -p "$APP_UJI/backend" "$APP_UJI/frontend"
printf 'ENV_UJI=sintetis_backend\n' > "$APP_UJI/backend/.env"
printf 'URL_UJI=sintetis_frontend\n' > "$APP_UJI/frontend/.env"
# Penggunaan nama sementara lama adalah kegagalan sebelum cp menyentuhnya.
cp() {
  local arg
  for arg in "$@"; do
    case "$arg" in /tmp/backend_env_backup|/tmp/frontend_env_backup) return 99;; esac
  done
  command cp "$@"
}
'''
    return subprocess.run(
        ["bash", "-s", "--", SKRIP.as_posix(), tmp_path.as_posix()],
        input=pembuka + isi, text=True, encoding="utf-8", capture_output=True,
        timeout=25,
    )


def lulus(hasil):
    assert hasil.returncode == 0, hasil.stderr
    assert "sintetis_backend" not in hasil.stdout + hasil.stderr
    assert "sintetis_frontend" not in hasil.stdout + hasil.stderr


def test_source_tidak_menjalankan_deploy_atau_mengubah_trap(tmp_path):
    lulus(jalankan(tmp_path, r'''
test -z "$(trap -p EXIT)"
test -z "${AMAN_ENV_TMP_DIR:-}"
'''))


def test_pemulihan_mempertahankan_byte_dan_membersihkan_salinan(tmp_path):
    lulus(jalankan(tmp_path, r'''
(
  aman_env_siapkan "$APP_UJI" 1
  printf '%s' "$AMAN_ENV_TMP_DIR" > "$APP_UJI/lokasi-uji"
  pemilik="$(stat -c %u:%g "$APP_UJI/backend/.env")"
  printf 'isi-terganti' > "$APP_UJI/backend/.env"
  aman_env_pasang
  cmp "$APP_UJI/backend/.env" "$AMAN_ENV_TMP_DIR/backend.env"
  cmp "$APP_UJI/frontend/.env" "$AMAN_ENV_TMP_DIR/frontend.env"
  test "$(stat -c %u:%g "$APP_UJI/backend/.env")" = "$pemilik"
)
test ! -e "$(<"$APP_UJI/lokasi-uji")"
'''))


def test_salinan_dua_proses_terpisah_dan_status_gagal_tidak_hilang(tmp_path):
    lulus(jalankan(tmp_path, r'''
for n in 1 2; do
  if (
    aman_env_siapkan "$APP_UJI" 1
    printf '%s' "$AMAN_ENV_TMP_DIR" > "$APP_UJI/lokasi-$n"
    exit 23
  ); then exit 88; else test "$?" = 23; fi
  test ! -e "$(<"$APP_UJI/lokasi-$n")"
done
test "$(<"$APP_UJI/lokasi-1")" != "$(<"$APP_UJI/lokasi-2")"
'''))


def test_sumber_hilang_tidak_memulihkan_salinan_run_lama(tmp_path):
    lulus(jalankan(tmp_path, r'''
rm -- "$APP_UJI/backend/.env"
if aman_env_siapkan "$APP_UJI" 1; then exit 88; fi
test -z "${AMAN_ENV_TMP_DIR:-}"
aman_env_siapkan "$APP_UJI" 0
test ! -e "$AMAN_ENV_TMP_DIR/backend.env"
aman_env_pasang
test ! -e "$APP_UJI/backend/.env"
test -f "$APP_UJI/frontend/.env"
'''))


@pytest.mark.parametrize("sinyal,kode", [("HUP", 129), ("INT", 130), ("TERM", 143)])
def test_interupsi_keluar_dan_membersihkan_salinan(tmp_path, sinyal, kode):
    lulus(jalankan(tmp_path, r'''
if (
  aman_env_siapkan "$APP_UJI" 1
  printf '%s' "$AMAN_ENV_TMP_DIR" > "$APP_UJI/lokasi-uji"
  kill -SIGNAL "$BASHPID"
  exit 88
); then exit 89; else test "$?" = EXPECTED; fi
test ! -e "$(<"$APP_UJI/lokasi-uji")"
'''.replace("SIGNAL", sinyal).replace("EXPECTED", str(kode))))


@pytest.mark.parametrize("gagal", ["snapshot", "staging", "rename"])
def test_gagal_salin_tidak_merusak_asli_dan_tidak_menghilangkan_pemulihan(tmp_path, gagal):
    # Snapshot gagal: sumber utuh, temp dibersihkan. Restore gagal: asli tidak
    # terpotong dan backup privat tetap ada untuk pemulihan operator.
    lulus(jalankan(tmp_path, r'''
command cp "$APP_UJI/backend/.env" "$APP_UJI/asli-uji"
if (
  if [ FASE = snapshot ]; then
    cp() { return 7; }
    aman_env_siapkan "$APP_UJI" 1 || {
      printf '%s' "$AMAN_ENV_TMP_DIR" > "$APP_UJI/lokasi-uji"
      exit 7
    }
  else
    aman_env_siapkan "$APP_UJI" 1
    printf '%s' "$AMAN_ENV_TMP_DIR" > "$APP_UJI/lokasi-uji"
    if [ FASE = staging ]; then cp() { return 7; }; else mv() { return 7; }; fi
    # Bentuk ini sengaja meniru pasang_env || true dalam rollback.
    aman_env_pasang || true
  fi
); then exit 88; fi
cmp "$APP_UJI/backend/.env" "$APP_UJI/asli-uji"
snapshot="$(<"$APP_UJI/lokasi-uji")"
if [ FASE = snapshot ]; then test ! -e "$snapshot"; else
  test -f "$snapshot/backend.env"
  cmp "$snapshot/backend.env" "$APP_UJI/asli-uji"
  # Pembersihan milik fixture saja, bukan file pengguna/produksi.
  rm -- "$snapshot/backend.env" "$snapshot/frontend.env"
  rmdir -- "$snapshot"
fi
test -z "$(find "$APP_UJI/backend" -maxdepth 1 -name '.env-restore.*' -print)"
'''.replace("FASE", gagal)))


@pytest.mark.skipif(os.name == "nt", reason="Symlink/hardlink POSIX diuji pada CI Linux; Git Bash Windows mengemulasikan symlink.")
@pytest.mark.parametrize("bentuk", ["symlink", "hardlink", "direktori"])
def test_tujuan_berbahaya_tidak_menimpa_berkas_lain(tmp_path, bentuk):
    lulus(jalankan(tmp_path, r'''
printf 'jangan-diubah' > "$APP_UJI/korban"
(
  aman_env_siapkan "$APP_UJI" 1
  rm -- "$APP_UJI/backend/.env"
  case BENTUK in
    symlink) ln -s "$APP_UJI/korban" "$APP_UJI/backend/.env" ;;
    hardlink) ln "$APP_UJI/korban" "$APP_UJI/backend/.env" ;;
    direktori) mkdir "$APP_UJI/backend/.env" ;;
  esac
  if aman_env_pasang; then test BENTUK = hardlink; else
    test BENTUK != hardlink
    # Backup uji dapat dibersihkan: fixture tahu sumber aslinya masih ada.
    AMAN_ENV_PULIH_GAGAL=0
  fi
)
test "$(<"$APP_UJI/korban")" = jangan-diubah
'''.replace("BENTUK", bentuk)))


@pytest.mark.skipif(os.name == "nt", reason="Mode POSIX 0700/0600 tidak diemulasikan Git Bash; wajib diuji pada CI Linux.")
def test_izin_privat_sejak_pembuatan_dan_saat_pemulihan(tmp_path):
    lulus(jalankan(tmp_path, r'''
# Reproduksi sifat cp lama: target yang sudah ada tidak mewarisi mode sumber.
chmod 600 "$APP_UJI/backend/.env"
touch "$APP_UJI/salinan-lama-uji"
chmod 666 "$APP_UJI/salinan-lama-uji"
command cp "$APP_UJI/backend/.env" "$APP_UJI/salinan-lama-uji"
test "$(stat -c %a "$APP_UJI/salinan-lama-uji")" = 666
aman_env_siapkan "$APP_UJI" 1
test "$(stat -c %a "$AMAN_ENV_TMP_DIR")" = 700
test "$(stat -c %u "$AMAN_ENV_TMP_DIR")" = "$EUID"
test "$(stat -c %a "$AMAN_ENV_TMP_DIR/backend.env")" = 600
test "$(stat -c %a "$AMAN_ENV_TMP_DIR/frontend.env")" = 600
aman_env_pasang
test "$(stat -c %a "$APP_UJI/backend/.env")" = 600
test "$(stat -c %a "$APP_UJI/frontend/.env")" = 600
'''))


@pytest.mark.parametrize("mode", ["sukses", "backend_gagal", "frontend_gagal"])
def test_alur_deploy_stdin_sukses_rollback_dan_gagal_build(tmp_path, mode):
    app = tmp_path / "aplikasi"
    (app / "backend").mkdir(parents=True)
    (app / "frontend" / "build").mkdir(parents=True)
    (app / "backend" / ".env").write_text("ENV_UJI=backend\n")
    (app / "frontend" / ".env").write_text("ENV_UJI=frontend\n")
    (app / "frontend" / "build" / "index.html").write_text("bundel lama")
    target = "a" * 40
    # Hanya batas eksternal dimock. Snapshot/restore/trap/cp/mv/rm yang
    # berjalan adalah implementasi produksi dengan data dan direktori uji.
    stub = r'''
git() {
  case "$1" in
    rev-parse) if [ "$2" = --short ]; then echo aaaaaaaa; else echo TARGET; fi ;;
    -C) echo aaaaaaaa ;;
    *) return 0 ;;
  esac
}
mongosh() { echo 0; }
sudo() { return 0; }
sleep() { return 0; }
curl() { test "$MODE_UJI" != backend_gagal; }
yarn() {
  if [ "$1" = build ]; then
    [ "$MODE_UJI" != frontend_gagal ] || return 9
    mkdir -p build.new
    printf 'bundel baru' > build.new/index.html
  fi
}
mktemp() {
  local p
  p="$(command mktemp "$@")" || return 1
  case "$p" in /tmp/aman-env.*) printf '%s\n' "$p" >> "$APP_DIR/lokasi-uji";; esac
  printf '%s\n' "$p"
}
'''.replace("TARGET", target)
    # Trap verifikasi terpisah setelah anak bash selesai, termasuk exit gagal.
    lingkungan = dict(os.environ, APP_DIR=app.as_posix(), MODE_UJI=mode)
    hasil = subprocess.run(["bash", "-s", "--", target],
                           input=stub + SKRIP.read_text(encoding="utf-8"), env=lingkungan,
                           text=True, encoding="utf-8", capture_output=True, timeout=25)
    assert hasil.returncode == (0 if mode == "sukses" else 1 if mode == "backend_gagal" else 9), hasil.stderr
    if mode == "backend_gagal":
        assert "ROLLBACK selesai" in hasil.stderr
    assert (app / "backend" / ".env").read_text() == "ENV_UJI=backend\n"
    assert (app / "frontend" / ".env").read_text() == "ENV_UJI=frontend\n"
    assert (app / "frontend" / "build" / "index.html").read_text() == (
        "bundel baru" if mode == "sukses" else "bundel lama")
    assert "ENV_UJI=" not in hasil.stdout + hasil.stderr
    for direktori in (app / "lokasi-uji").read_text().splitlines():
        cek = subprocess.run(["bash", "-c", 'test ! -e "$1"', "uji", direktori])
        assert cek.returncode == 0


def test_deploy_stdin_tidak_memerlukan_helper_di_checkout_lama(tmp_path):
    # Alur riil adalah bash -s: BASH_SOURCE[0] kosong, bukan pemanggilan source.
    env = dict(os.environ, APP_DIR=str(tmp_path))
    hasil = subprocess.run(["bash", "-s", "--", "invalid"],
                           input=SKRIP.read_text(encoding="utf-8"), env=env,
                           text=True, encoding="utf-8", capture_output=True, timeout=20)
    assert hasil.returncode == 2
    assert "DEPLOY DIBATALKAN" in hasil.stderr


def test_kedua_pemanggil_memakai_helper_dan_frontend_lama_tidak_ditimpa():
    deploy = SKRIP.read_text(encoding="utf-8")
    updater = (AKAR / "scripts" / "update-all.sh").read_text(encoding="utf-8")
    for teks in (deploy, updater):
        kode = "\n".join(b for b in teks.splitlines() if not b.lstrip().startswith("#"))
        assert "/tmp/backend_env_backup" not in kode
        assert "/tmp/frontend_env_backup" not in kode
    assert 'aman_env_siapkan "$APP_DIR" 1' in deploy
    assert 'aman_env_siapkan "$APP_DIR" 0' in updater
    assert 'source "$(dirname -- "${BASH_SOURCE[0]}")/deploy_vps.sh"' in updater
    assert "\naman_env_pasang\n" in updater
    assert "if [ ! -f .env ]; then" in updater


def test_pembuatan_env_frontend_tidak_mewariskan_umask_privat_ke_build(tmp_path):
    updater = (AKAR / "scripts" / "update-all.sh").read_text(encoding="utf-8")
    awal = updater.index("if [ ! -f .env ]; then")
    blok = updater[awal:updater.index("\nfi", awal) + 3]
    lulus(jalankan(tmp_path, r'''
cd "$APP_UJI/frontend"
rm -- .env
umask 022
''' + blok + r'''
test -f .env
test "$(umask)" = 0022
'''))
