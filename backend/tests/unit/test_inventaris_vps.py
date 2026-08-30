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
import os
import pathlib
import re
import subprocess

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
        """Dicocokkan sebagai PERINTAH, bukan sebagai potongan kata.

        Versi pertama uji ini mencocokkan substring dan menolak skrip yang
        sah: variabel `perlu_reboot` dan jalur `/var/run/reboot-required`
        memuat kata `reboot`, dan uji menuduhnya memanggil `reboot`. Pola di
        bawah menuntut kata itu berdiri di POSISI perintah — awal baris, atau
        sesudah `;` `&&` `|` `(` `$(`.
        """
        pola = re.compile(
            r"(?:^|[;&|(]|\$\()\s*" + re.escape(perintah) + r"(?![\w-])",
            re.M)
        assert not pola.search(_tanpa_komentar(isi_skrip)), (
            f"scripts/inventaris_vps.sh memanggil `{perintah}`. Skrip ini "
            "dipipe ke VPS PRODUKSI; ia harus aman dijalankan kapan pun tanpa "
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
        # Bagian "Pemutakhiran sistem". Tak satu pun memuat kredensial:
        # /boot hanya berisi nama berkas kernel; reboot-required adalah
        # penanda kosong beserta daftar nama paket; dari history.log yang
        # dibaca HANYA baris `Start-Date:` — berkas itu juga memuat
        # `Commandline:` dan tak ada alasan menumpahkannya ke log Actions.
        "/boot",
        "/boot/vmlinuz-*",
        "/vmlinuz-",  # potongan dari `sed 's|.*/vmlinuz-||'`
        "/var/run/reboot-required",
        "/var/run/reboot-required.pkgs",
        "/var/log/apt/history.log",
        # Direktori aplikasi (default yang sama dengan scripts/deploy_vps.sh).
        # Yang dibaca dari sana HANYA `venv/bin/python --version`; berkas
        # `.env` di direktori yang sama tetap dilarang oleh
        # test_tidak_mencetak_konfigurasi_atau_kredensial.
        "/var/www/inventarisasi",
        "/var/www/inventarisasi/backend/venv/bin/python",
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


class TestPelajaranPutaranPertama:
    """Cacat nyata yang lolos ke produksi pada putaran pertama, dikunci.

    Inventaris 29 Agustus melaporkan `redis-server` "unit tidak ada". Unitnya
    ternyata loaded, enabled, dan running sejak tiga hari. Laporan itu masuk ke
    docs/OPTIMASI-VPS.md sebagai temuan, dan sempat melahirkan hipotesis keliru
    bahwa cache aplikasi jatuh diam-diam ke Mongo.

    Sebabnya bukan systemd, melainkan bentuk perintahnya::

        set -o pipefail; seq 1 2000000 | grep -q "^1$"; echo $?
        1        # "tidak cocok", padahal 1 jelas ada

    `grep -q` berhenti pada kecocokan PERTAMA lalu menutup pipa; produsennya
    kena SIGPIPE; `pipefail` menjadikan seluruh pipeline gagal MESKI cocok.
    Karena bergantung pada balapan siapa-selesai-duluan, ia lolos di mesin uji
    dan menggigit di produksi - jenis cacat yang tak tertangkap dengan
    "jalankan sekali, lihat hasilnya".
    """

    def test_tidak_ada_grep_q_di_skrip_ber_pipefail(self, isi_skrip):
        perintah = _tanpa_komentar(isi_skrip)
        assert "pipefail" in perintah, (
            "Uji ini mengandaikan skrip memakai `set -o pipefail`; kalau itu "
            "dicabut, tinjau ulang alasan larangan di bawah."
        )
        assert "grep -q" not in perintah, (
            "`grep -q` di bawah `pipefail` melaporkan GAGAL meski cocok, bila "
            "produsennya belum selesai menulis saat grep menutup pipa. Itu "
            "yang membuat redis-server dilaporkan tidak ada. Pakai perintah "
            "tunggal tanpa pipa (mis. `systemctl show -p LoadState --value`)."
        )

    def test_unit_yang_ADA_tidak_dilaporkan_hilang(self, tmp_path):
        """Uji PERILAKU, bukan pencocokan teks.

        Versi pertama uji ini mencari pipa di dalam `status_unit` dengan regex
        dan tersandung pada `|` pemisah kolom Markdown di dalam tanda kutip —
        pencocokan teks tidak tahu beda pipa shell dan tabel yang dicetak.
        Jadi skripnya dijalankan sungguhan dengan `systemctl` tiruan.

        Tiruannya sengaja memuntahkan keluaran BESAR untuk `list-unit-files`:
        itulah yang memicu SIGPIPE bila pemanggilnya memipe ke `grep -q`, dan
        itulah yang membuat putaran pertama melaporkan redis-server hilang.
        """
        stub = tmp_path / "bin"
        stub.mkdir()
        (stub / "systemctl").write_text(
            "#!/bin/bash\n"
            "case \"$1\" in\n"
            "  list-unit-files)\n"
            "    echo 'UNIT FILE STATE PRESET'\n"
            "    echo \"$2 enabled enabled\"\n"
            "    seq 1 200000 | sed 's/^/pad.service enabled enabled /'\n"
            "    ;;\n"
            "  show)\n"
            "    for a in \"$@\"; do akhir=\"$a\"; done\n"
            "    case \"$akhir\" in\n"
            "      redis-server.service) echo loaded ;;\n"
            "      *) echo not-found ;;\n"
            "    esac ;;\n"
            "  is-active)  echo active ;;\n"
            "  is-enabled) echo enabled ;;\n"
            "esac\n"
        )
        (stub / "supervisorctl").write_text(
            "#!/bin/bash\necho 'inventarisasi-backend RUNNING pid 1, uptime 0:10:10'\n"
        )
        (stub / "top").write_text(
            "#!/bin/bash\n"
            "echo '  PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ COMMAND'\n"
            "echo '    1 root 20 0 1 1 1 S 99.0 1.0 1:00.00 mongod'\n"
            "echo '  PID USER PR NI VIRT RES SHR S %CPU %MEM TIME+ COMMAND'\n"
            "echo '    1 root 20 0 1 1 1 S 99.0 1.0 1:00.00 mongod'\n"
        )
        for f in stub.iterdir():
            f.chmod(0o755)

        lingkungan = dict(os.environ, PATH=f"{stub}:{os.environ['PATH']}")
        hasil = subprocess.run(
            ["bash", str(SKRIP)], capture_output=True, text=True,
            env=lingkungan, timeout=120,
        )
        keluaran = hasil.stdout

        # Ambil HANYA bagian tabel systemd: "`redis-server`" juga muncul di
        # tabel versi, dan mencocokkannya di seluruh keluaran akan menguji
        # baris yang salah.
        awal = keluaran.index("## Layanan systemd yang relevan")
        tabel = keluaran[awal:keluaran.index("## ", awal + 3)]

        baris_redis = [b for b in tabel.splitlines() if "`redis-server`" in b]
        assert baris_redis, "baris redis-server tidak ada di keluaran"
        assert "unit tidak ada" not in baris_redis[0], (
            "Unit yang ADA dilaporkan hilang — cacat 29 Agustus terulang. "
            "Barisnya: " + baris_redis[0]
        )
        assert "active" in baris_redis[0] and "enabled" in baris_redis[0]

        # Yang benar-benar tak ada tetap harus dilaporkan tak ada — kalau tidak,
        # uji di atas bisa lulus hanya karena skripnya selalu bilang "ada".
        baris_f2b = [b for b in tabel.splitlines() if "`fail2ban`" in b]
        assert baris_f2b and "unit tidak ada" in baris_f2b[0], (
            "Unit yang tak ada TIDAK dilaporkan hilang: " + str(baris_f2b)
        )

        assert "inventarisasi-backend" in keluaran, (
            "Status supervisor tak muncul — laporan tak menyebut apakah "
            "backend hidup."
        )

    def test_systemd_bukan_penanda_hidup_matinya_backend(self, isi_skrip):
        perintah = _tanpa_komentar(isi_skrip)
        for tebakan in ("aman-backend", "aman.service"):
            assert tebakan not in perintah, (
                f"Skrip menanyakan `{tebakan}` ke systemd. Unit itu tidak "
                "pernah ada; backend dikelola supervisor sebagai "
                "`inventarisasi-backend`, dan systemd akan selalu menjawab "
                "'tidak ada' - terbaca seolah backend mati padahal sehat."
            )
        assert "supervisorctl status" in perintah, (
            "Backend hanya bisa dilihat lewat supervisor - tanpa itu laporan "
            "tak pernah menyebut apakah aplikasinya hidup."
        )

    @pytest.mark.parametrize("cmd", [
        "supervisorctl start", "supervisorctl stop", "supervisorctl restart",
        "supervisorctl reload", "supervisorctl shutdown",
    ])
    def test_supervisor_hanya_dibaca(self, isi_skrip, cmd):
        assert cmd not in _tanpa_komentar(isi_skrip), (
            f"`{cmd}` mengubah keadaan produksi. Inventaris hanya boleh "
            "`supervisorctl status`."
        )

    def test_top_tidak_meminta_baris_perintah_lengkap(self, isi_skrip):
        perintah = _tanpa_komentar(isi_skrip)
        if "top -b" not in perintah:
            pytest.skip("skrip tidak lagi memakai top")
        assert "top -c" not in perintah and "-b -c" not in perintah, (
            "`top -c` mencetak baris perintah LENGKAP, yang bisa memuat "
            "kredensial pada argumen (mis. URL ber-sandi). Keluaran ini masuk "
            "ke log Actions - cukup nama program."
        )


class TestAptHanyaDisimulasikan:
    """`apt` boleh dipanggil, tetapi HANYA dalam mode simulasi.

    Bagian "Pemutakhiran sistem" perlu tahu berapa paket yang masih bisa
    dimutakhirkan, dan satu-satunya cara membacanya adalah lewat apt sendiri.
    `apt-get -s` (simulate) tak mengubah apa pun, tak mengambil kunci, dan tak
    mengunduh — tetapi jarak antara `-s` dan tanpa `-s` cuma dua karakter, dan
    yang tanpa `-s` akan MEMUTAKHIRKAN PRODUKSI di tengah jam kerja.
    """

    def test_setiap_apt_get_memakai_simulasi(self, isi_skrip):
        perintah = _tanpa_komentar(isi_skrip)
        panggilan = re.findall(r"apt-get[^\n|;]*", perintah)
        assert panggilan, "tak ada apt-get sama sekali — uji ini jadi hampa"
        for c in panggilan:
            assert re.search(r"(?:^|\s)-s(?:\s|$)|--simulate|--dry-run", c), (
                f"`{c.strip()}` bukan simulasi. Tanpa `-s`, perintah ini "
                "mengubah paket di VPS produksi."
            )

    @pytest.mark.parametrize("bahaya", [
        "apt-get upgrade", "apt-get dist-upgrade", "apt-get autoremove",
        "apt upgrade", "apt full-upgrade",
    ])
    def test_bentuk_apt_yang_mengubah_ditolak(self, isi_skrip, bahaya):
        assert bahaya not in _tanpa_komentar(isi_skrip), (
            f"`{bahaya}` memutakhirkan paket di VPS produksi."
        )


class TestPemutakhiranTerbaca:
    """Pemilik memutakhirkan VPS lalu bertanya apakah pemutakhirannya masuk.

    Alat ini semula TIDAK BISA menjawabnya: `uname -r` melaporkan kernel yang
    sedang BERJALAN, bukan yang terpasang. Sesudah `apt upgrade` yang
    menyertakan kernel, angka itu tak berubah sampai reboot — dan pembacanya
    akan menyimpulkan pemutakhirannya gagal, padahal ia hanya menunggu reboot.
    """

    def test_membedakan_kernel_berjalan_dari_yang_terpasang(self, isi_skrip):
        assert "Kernel berjalan" in isi_skrip
        assert "Kernel terpasang" in isi_skrip
        # Label lama "| Kernel |" tanpa keterangan justru yang menyesatkan.
        assert 'baris "| Kernel | ' not in isi_skrip

    def test_kernel_terpasang_diurutkan_menurut_VERSI(self, isi_skrip):
        # `sort` biasa menaruh 6.8.0-99 di atas 6.8.0-140 dan melaporkan
        # kernel yang salah sebagai "terbaru".
        assert "sort -V" in isi_skrip, (
            "urutan abjad akan menyebut 6.8.0-99 lebih baru daripada 6.8.0-140"
        )

    def test_menyebut_apakah_perlu_reboot(self, isi_skrip):
        assert "/var/run/reboot-required" in isi_skrip
        assert "Perlu reboot" in isi_skrip

    def test_menghitung_sisa_paket_dengan_grep_c_bukan_grep_q(self, isi_skrip):
        # `grep -c` membaca SELURUH masukan; `grep -q` berhenti pada kecocokan
        # pertama dan — di bawah `pipefail` — melaporkan gagal meski cocok.
        # Itu cacat yang pernah membuat alat ini salah lapor soal Redis.
        assert "grep -c '^Inst " in isi_skrip
