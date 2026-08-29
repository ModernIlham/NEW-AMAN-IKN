"""Penjaga keamanan untuk workflow "Inventaris VPS".

Permintaan pemilik: *"tolong cek di vps saya
/root/installed-software-2026-08-25.txt untuk mengecek update yang telah saya
lakukan."* Satu-satunya jalur SSH ke VPS ada di GitHub Actions, jadi bacaannya
dikerjakan lewat workflow. Yang berbahaya bukan membacanya, melainkan bentuk
yang gampang ditumbuhkan sesudahnya:

* satu input `jalur` supaya "sekalian bisa lihat berkas lain" — dan workflow
  berubah jadi `cat` berkas apa pun ke log Actions, termasuk `/root/.env`,
  kunci privat, dan URL Mongo lengkap dengan sandinya. Log itu terbaca semua
  kolaborator dan bertahan berbulan-bulan;
* satu `systemctl restart` "biar sekalian" — dan alat diagnosis berubah jadi
  alat yang bisa menjatuhkan produksi;
* satu pemicu `push` "biar selalu segar" — dan tiap commit menyeret sesi SSH
  baru ke VPS, pola yang persis diduga memicu pemblokiran fail2ban pada
  Agustus 2026 (riwayatnya di .github/workflows/deploy.yml).

Ketiganya tidak akan membuat satu pun uji lain gagal. Uji inilah gerbangnya.
"""
import pathlib
import re

import pytest
import yaml

AKAR = pathlib.Path(__file__).resolve().parents[3]
SKRIP = AKAR / "scripts" / "inventaris_vps.sh"
ALUR = AKAR / ".github" / "workflows" / "inventaris-vps.yml"


@pytest.fixture(scope="module")
def isi_skrip() -> str:
    return SKRIP.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def alur() -> dict:
    return yaml.safe_load(ALUR.read_text(encoding="utf-8"))


def _tanpa_komentar(isi: str) -> str:
    """Baris perintah saja — komentar boleh menyebut apa pun, termasuk
    contoh berbahaya yang justru sedang dilarangnya."""
    return "\n".join(
        b for b in isi.splitlines() if not b.lstrip().startswith("#")
    )


class TestSkripHanyaMembaca:
    # Perintah yang mengubah keadaan mesin. Daftar ini sengaja memuat yang
    # "kelihatannya tak berbahaya" juga (`touch`, `chmod`): begitu satu boleh,
    # argumen "yang ini kan cuma…" berlaku untuk semuanya.
    MENULIS = (
        "rm", "mv", "cp", "touch", "mkdir", "chmod", "chown", "ln",
        "truncate", "dd", "tee", "sed -i",
        "apt-get install", "apt install", "apt-get remove", "apt remove",
        "pip install", "npm install", "yarn add",
        "systemctl start", "systemctl stop", "systemctl restart",
        "systemctl enable", "systemctl disable", "systemctl reload",
        "service ", "kill", "pkill", "reboot", "shutdown",
        "mongo ", "mongosh", "mongodump", "mongorestore",
        # `git --version` boleh; sub-perintah yang menyentuh disk tidak.
        "git clone", "git checkout", "git pull", "git push",
        "curl ", "wget ",
    )

    @pytest.mark.parametrize("perintah", MENULIS)
    def test_tidak_memakai_perintah_yang_mengubah_keadaan(self, isi_skrip, perintah):
        assert perintah not in _tanpa_komentar(isi_skrip), (
            f"scripts/inventaris_vps.sh memakai `{perintah}`. Skrip ini dipipe "
            "ke VPS PRODUKSI; ia harus aman dijalankan kapan pun tanpa "
            "membangunkan siapa pun."
        )

    def test_tidak_meredireksi_keluaran_ke_berkas(self, isi_skrip):
        # Membuang keluaran (`2>/dev/null`) dan menggabung aliran (`2>&1`)
        # tidak menulis apa pun ke mesin — keduanya disingkirkan dulu supaya
        # yang tersisa benar-benar redireksi ke BERKAS.
        perintah = _tanpa_komentar(isi_skrip)
        perintah = re.sub(r"[0-9&]?>>?\s*(/dev/null|&[0-9-])", "", perintah)
        nakal = [b for b in perintah.splitlines() if re.search(r">>?\s*\S", b)]
        assert not nakal, (
            "Ada redireksi ke berkas di skrip inventaris: " + "; ".join(nakal)
        )


class TestSkripTidakMembocorkanRahasia:
    # Jalur absolut yang BOLEH dibaca. Berkas catatan pemilik masuk lewat pola
    # tetap; sisanya bacaan sistem tanpa kredensial.
    JALUR_BOLEH = {
        "/root/installed-software-*.txt",
        "/etc/os-release",
        "/proc/loadavg",
        "/usr/bin/env",
        "/dev/null",
        "/",
        "/g",  # akhiran `sed 's/|/ /g'`, bukan jalur
    }

    def test_hanya_menyentuh_jalur_yang_diizinkan(self, isi_skrip):
        ditemukan = set(re.findall(r"/[A-Za-z0-9_./*-]+", _tanpa_komentar(isi_skrip)))
        asing = {j for j in ditemukan if j not in self.JALUR_BOLEH}
        assert not asing, (
            "Jalur absolut baru di skrip inventaris: " + ", ".join(sorted(asing))
            + ". Bacaannya masuk ke log Actions yang terbaca semua kolaborator "
            "— tambahkan ke JALUR_BOLEH hanya bila jelas tak memuat kredensial."
        )

    def test_berkas_catatan_dibaca_dari_pola_tetap(self, isi_skrip):
        # Sumber berkas catatan HARUS glob harfiah di dalam skrip, bukan
        # variabel — variabel apa pun bisa diisi dari luar suatu hari nanti.
        assert re.search(
            r"^\s*for\s+\w+\s+in\s+/root/installed-software-\*\.txt\s*;?\s*do",
            _tanpa_komentar(isi_skrip),
            re.M,
        ), (
            "Berkas catatan tidak lagi dibaca dari glob harfiah "
            "/root/installed-software-*.txt di dalam skrip."
        )

    @pytest.mark.parametrize("bahaya", ["nginx.conf", ".env", "id_rsa",
                                        "authorized_keys", "printenv", "env |"])
    def test_tidak_mencetak_konfigurasi_atau_kredensial(self, isi_skrip, bahaya):
        assert bahaya not in _tanpa_komentar(isi_skrip), (
            f"Skrip inventaris menyentuh `{bahaya}` — berkas/perintah itu "
            "memuat kredensial atau topologi dalam."
        )


class TestWorkflownyaTerkunci:
    def test_hanya_bisa_dijalankan_manual(self, alur):
        # PyYAML membaca `on:` sebagai boolean True (YAML 1.1) — ambil apa pun
        # kuncinya, yang diuji isinya.
        pemicu = alur.get("on", alur.get(True))
        assert set(pemicu) == {"workflow_dispatch"}, (
            f"Pemicu workflow inventaris berubah jadi {sorted(pemicu)}. Pemicu "
            "otomatis berarti sesi SSH ke VPS pada tiap commit."
        )

    def test_tanpa_input_jalur_berkas(self, alur):
        pemicu = alur.get("on", alur.get(True))
        assert not (pemicu.get("workflow_dispatch") or {}).get("inputs"), (
            "Workflow inventaris punya input. Input jalur berkas mengubahnya "
            "menjadi `cat` berkas apa pun di VPS ke dalam log Actions."
        )

    def test_menjalankan_skrip_yang_diuji_di_berkas_ini(self, alur):
        langkah = alur["jobs"]["inventaris"]["steps"]
        skrip = "\n".join(s.get("run", "") for s in langkah)
        # Perintah jarak jauhnya HARUS `bash -s` tanpa argumen: satu
        # argumen saja di belakangnya menjadi jalan masuk nilai dari luar ke
        # dalam skrip, persis yang dicegah TestSkripTidakMembocorkanRahasia.
        assert "'bash -s' < scripts/inventaris_vps.sh" in skrip
        # Dan tidak ada perintah jarak jauh LAIN: satu-satunya yang berjalan
        # di VPS adalah skrip yang batasnya diuji di kelas-kelas di atas.
        assert skrip.count("ssh -i") == 1

    def test_berbagi_antrean_dengan_deploy(self, alur):
        assert alur["concurrency"]["group"] == "deploy-vps", (
            "Inventaris harus mengantre bersama deploy — dua sesi SSH beruntun "
            "ke VPS yang sama adalah pola yang diduga memicu fail2ban."
        )
