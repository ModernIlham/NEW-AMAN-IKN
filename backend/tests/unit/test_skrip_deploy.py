"""Skrip deploy — temuan C6 & C7 tinjauan sistem 2026-08.

Skrip shell adalah bagian sistem yang paling jarang diuji dan paling mahal
saat salah: ia berjalan tanpa penonton, jam berapa pun CI selesai, langsung di
produksi. Uji ini tidak menjalankan deploy (mustahil di CI) — ia mengurung
SIFAT-SIFAT yang membedakan deploy yang aman dari yang tidak, dibaca dari
sumbernya, plus pemeriksaan sintaks `bash -n` yang sungguhan.

C6 — tiga sifat yang hilang:
  (a) pagar memori. `grep -rn NODE_OPTIONS scripts/` dulu menemukannya di
      vps-deploy.sh dan update-all.sh TETAPI TIDAK di deploy_vps.sh — justru
      skrip yang benar-benar dipakai otomatis yang tanpa pagar, di VPS tanpa
      swap. `yarn build` adalah kandidat OOM terbesar di seluruh sistem.
  (b) react-scripts memanggil `fs.emptyDirSync` di awal build, dan docroot
      nginx menunjuk LANGSUNG ke frontend/build. Setiap deploy karenanya
      mengosongkan docroot lalu mengisinya ulang selama puluhan detik:
      sepanjang itu pengunjung mendapat 404.
  (c) gerbang kesehatan sudah ada dan benar, tetapi saat gagal skrip hanya
      keluar — meninggalkan produksi menjalankan commit yang baru saja terbukti
      TIDAK SEHAT, sampai ada manusia yang bangun.

C7 — `Deploy_Hostinger_VPS` muncul 8 kali di dua skrip pemulihan darurat,
padahal cabang itu sudah tidak ada. Yang lebih berbahaya dari "skrip berhenti"
adalah: bila klon di VPS masih menyimpan ref pelacak lama, `rev-parse` justru
BERHASIL dan `git reset --hard` memutar mundur produksi ke commit beku.
"""
import pathlib
import re
import subprocess

import pytest

SKRIP = pathlib.Path(__file__).resolve().parents[3] / "scripts"
DEPLOY = SKRIP / "deploy_vps.sh"


def _teks(p):
    return p.read_text(encoding="utf-8")


def _kode(p):
    """Isi skrip TANPA baris komentar.

    Berkas-berkas ini penuh penjelasan panjang yang MENYEBUT nama variabel
    (mis. komentar "grep -rn NODE_OPTIONS scripts/" yang menerangkan asal
    temuan). Mencocokkan teks mentah membuat penjaga di bawah lolos hanya
    karena prosanya menyebut hal yang tepat — dan penjaga yang bisa dipuaskan
    oleh komentar tidak menjaga apa pun.
    """
    return "\n".join(b for b in _teks(p).splitlines()
                     if not b.lstrip().startswith("#"))


@pytest.mark.parametrize("nama", [
    "deploy_vps.sh", "vps-fix.sh", "update-all.sh", "vps-deploy.sh",
])
def test_sintaks_bash_sah(nama):
    """`bash -n` — skrip yang tak bisa diparse tak akan ketahuan sampai jam 2 pagi."""
    r = subprocess.run(["bash", "-n", str(SKRIP / nama)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


class TestPagarMemori:
    def test_deploy_otomatis_benar_benar_meng_export_NODE_OPTIONS(self):
        # `export`, bukan sekadar kata "NODE_OPTIONS" di suatu tempat.
        assert re.search(r"^\s*export NODE_OPTIONS=", _kode(DEPLOY), re.M)

    def test_batasnya_disebut_eksplisit(self):
        assert "max-old-space-size" in _kode(DEPLOY)

    def test_semua_skrip_yang_membangun_frontend_berpagar(self):
        """Aturan kelas: yang memanggil `yarn build` wajib punya pagarnya."""
        for p in SKRIP.glob("*.sh"):
            k = _kode(p)
            if "yarn build" in k:
                assert "NODE_OPTIONS" in k, f"{p.name} membangun tanpa pagar memori"


class TestDocrootTidakDikosongkan:
    def test_membangun_ke_direktori_sementara(self):
        t = _teks(DEPLOY)
        assert "BUILD_PATH=build.new" in t

    def test_ditukar_dengan_rename_bukan_dibangun_di_tempat(self):
        t = _teks(DEPLOY)
        assert "mv build.new build" in t

    def test_salinan_sebelumnya_disimpan_sebagai_rollback(self):
        t = _teks(DEPLOY)
        assert "build.old" in t

    def test_bundel_diverifikasi_SEBELUM_ditukar(self):
        """Menukar bundel kosong lebih buruk daripada tidak menukar sama sekali."""
        t = _teks(DEPLOY)
        i_cek = t.index("build.new/index.html")
        i_tukar = t.index("mv build.new build")
        assert i_cek < i_tukar

    def test_pemeriksaan_direktori_pakai_if_bukan_rantai_and(self):
        # Di bawah `set -e`, `[ -d build ] && mv ...` yang berakhir false
        # menghentikan SELURUH skrip — pada VPS baru yang belum punya build/,
        # deploy pertamanya akan mati tepat di langkah terakhir.
        t = _teks(DEPLOY)
        assert not re.search(r"^\s*\[ -d build \] &&", t, re.M)
        assert "if [ -d build ]; then" in t


class TestRollback:
    def test_commit_sebelumnya_disimpan(self):
        assert re.search(r"PREV=.*git rev-parse HEAD", _teks(DEPLOY))

    def test_disimpan_SEBELUM_reset(self):
        t = _teks(DEPLOY)
        assert t.index("PREV=") < t.index('git reset --hard "origin/')

    def test_kedua_gerbang_kesehatan_memanggil_pulihkan(self):
        """Dangkal DAN mendalam — melewatkan satu berarti separuh perlindungan."""
        t = _teks(DEPLOY)
        assert t.count("pulihkan") >= 3   # 1 definisi + 2 pemanggilan
        for penanda in ("health-check timeout", "deep health 503/timeout"):
            i = t.index(penanda)
            assert "pulihkan" in t[i:i + 500], penanda

    def test_pulihkan_kembali_ke_PREV(self):
        t = _teks(DEPLOY)
        i = t.index("pulihkan() {")
        assert 'git reset --hard "$PREV"' in t[i:i + 900]

    def test_pulihkan_menghidupkan_kembali_backend(self):
        # Mengembalikan kode tanpa restart = produksi tetap menjalankan proses
        # dari commit yang sudah terbukti tidak sehat.
        t = _teks(DEPLOY)
        i = t.index("pulihkan() {")
        assert "restart_backend" in t[i:i + 900]


class TestCabangTujuan:
    BERGANTUNG = ("vps-fix.sh", "update-all.sh", "deploy_vps.sh")

    def test_NOL_rujukan_cabang_yang_sudah_tiada(self):
        """Sapuan seluruh scripts/ — komentar sejarah dikecualikan."""
        pelanggar = []
        for p in SKRIP.glob("*.sh"):
            for n, baris in enumerate(_teks(p).splitlines(), 1):
                if "Deploy_Hostinger_VPS" in baris and not baris.lstrip().startswith("#"):
                    pelanggar.append(f"{p.name}:{n}")
        assert pelanggar == [], pelanggar

    @pytest.mark.parametrize("nama", BERGANTUNG)
    def test_cabang_jadi_variabel_berdefault_main(self, nama):
        assert 'DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"' in _teks(SKRIP / nama)

    @pytest.mark.parametrize("nama", ("vps-fix.sh", "update-all.sh"))
    def test_skrip_darurat_memeriksa_cabangnya_dulu(self, nama):
        """Berhenti dengan alasan > berhenti diam-diam > memulihkan yang salah."""
        t = _teks(SKRIP / nama)
        assert "rev-parse --verify --quiet" in t
        assert "tidak ada di remote" in t

    @pytest.mark.parametrize("nama", ("vps-fix.sh", "update-all.sh"))
    def test_fetch_memakai_prune(self, nama):
        # Tanpa --prune, ref pelacak lama bertahan di klon VPS — itulah varian
        # kegagalan yang berbahaya: reset --hard ke commit beku yang "ada".
        assert "fetch --prune" in _teks(SKRIP / nama)


class TestAnggaranGerbangKesehatan:
    """S6 — gerbang deploy 15×2 dtk ≈ 28 dtk itu pas-pasan bahkan hari ini.

    uvicorn bind() dulu, listen() baru SETELAH lifespan.startup — jadi selama
    create_indexes + backfill startup berjalan, port memantulkan RST, curl
    gagal instan, dan hanya `sleep` yang menghitung. Gerbang yang kalah cepat
    dari boot yang sehat men-503-kan deploy sehat → `pulihkan()` → rollback.
    Anggaran dinaikkan ke ≈90 dtk SEBELUM penanda migrasi mendarat, karena
    boot pertama pasca-penanda masih menjalankan ketiga backfill.
    """

    def _anggaran(self):
        k = _kode(DEPLOY)
        m = re.search(r"^PERCOBAAN_KESEHATAN=(\d+)$", k, re.M)
        assert m, "variabel PERCOBAAN_KESEHATAN hilang"
        tidur = re.findall(r"^\s*sleep (\d+)$", k, re.M)
        assert tidur, "sleep di badan gerbang hilang"
        return int(m.group(1)), min(int(t) for t in tidur)

    def test_anggaran_gerbang_minimal_80_detik(self):
        # Menghitung ANGGARAN (iterasi × tidur), bukan mencocokkan angka 45 —
        # supaya uji tetap sah kalau kelak orang memilih 60×2 atau 30×3.
        iterasi, tidur = self._anggaran()
        assert iterasi * tidur >= 80, (iterasi, tidur)

    def test_kedua_gerbang_memakai_variabel_yang_sama(self):
        k = _kode(DEPLOY)
        assert k.count('seq 1 "$PERCOBAAN_KESEHATAN"') == 2
        assert not re.search(r"seq 1 \d", k), "masih ada gerbang berangka literal"

    def test_ambang_kegagalan_ikut_variabel(self):
        # Mutasi paling mungkin lolos tinjauan mata: menaikkan `seq` tapi
        # lupa pembanding `-eq` — gerbang tampak jalan, diam-diam gagal
        # LEBIH cepat dari anggarannya.
        k = _kode(DEPLOY)
        pembanding = re.findall(r'\[ "\$i" -eq ([^ ]+) \]', k)
        assert len(pembanding) == 2, pembanding
        assert all(p == '"$PERCOBAAN_KESEHATAN"' for p in pembanding), pembanding

    def test_komentar_tidak_berbohong_soal_anggaran(self):
        # Komentar "~30 dtk" adalah satu-satunya dokumentasi anggaran boot
        # yang dibaca orang jam 2 pagi; angka basi = skrip berbohong tentang
        # dirinya sendiri.
        iterasi, _ = self._anggaran()
        if iterasi > 15:
            assert "~30 dtk" not in _teks(DEPLOY)


class TestGerbangRestoreDeploy:
    """Prasyarat C30 — deploy tak boleh menimpa pemulihan data yang berjalan.

    `restart_backend` membunuh task restore di TENGAH wipe; sampai gerbang
    ini ada, itu terjadi DIAM-DIAM dan meninggalkan DB separuh terisi.
    Gerbang memeriksa job restore aktif (active_lock GLOBAL, denyut < 30
    menit) langsung ke Mongo SEBELUM skrip menyentuh apa pun. GAGAL-BUKA
    disengaja: pemeriksa yang rusak (mongosh hilang, URI tak terbaca) tak
    boleh memblokir semua deploy selamanya.
    """

    def test_fungsinya_ada_dan_dipanggil(self):
        k = _kode(DEPLOY)
        assert "periksa_restore_aktif() {" in k
        # Pemanggilan telanjang (bukan hanya definisi).
        assert re.search(r"^periksa_restore_aktif$", k, re.M)

    def test_dipanggil_SEBELUM_kode_disentuh(self):
        # Gerbang yang jalan setelah `git reset --hard` sudah terlambat:
        # dependensi bisa berubah dan restart menyusul pasti.
        t = _teks(DEPLOY)
        i_panggil = t.index("\nperiksa_restore_aktif\n")
        assert i_panggil < t.index('git fetch origin "$DEPLOY_BRANCH"')
        assert i_panggil < t.index('git reset --hard "origin/')

    def test_kueri_menyaring_job_restore_aktif_dan_segar(self):
        k = _kode(DEPLOY)
        i = k.index("periksa_restore_aktif() {")
        badan = k[i:k.index("\n}", i)]
        assert "'restore'" in badan
        assert "'GLOBAL'" in badan
        assert "'queued'" in badan and "'running'" in badan
        # Kesegaran denyut: tanpa filter updated_at, job macet yang tak
        # pernah dibersihkan memblokir deploy SELAMANYA.
        assert "updated_at" in badan
        assert "30 minutes ago" in badan

    def test_gagal_buka_bukan_gagal_tutup(self):
        k = _kode(DEPLOY)
        i = k.index("periksa_restore_aktif() {")
        badan = k[i:k.index("\n}", i)]
        # Dua jalur lewat (mongosh hilang; URI tak terbaca) harus return 0,
        # dan HANYA temuan restore aktif yang boleh exit 1.
        assert badan.count("return 0") >= 2
        assert badan.count("exit 1") == 1
        assert "DIBATALKAN" in _teks(DEPLOY)


VPS = SKRIP / "vps-deploy.sh"
PANDUAN = SKRIP.parent / "DEPLOYMENT_GUIDE_HOSTINGER.md"


def _blok_lokasi(teks, prefix):
    """Isi blok `location <prefix> { ... }` PERSIS prefix itu, tanpa komentar.

    Ber-scope per blok itu inti penjaganya: `proxy_read_timeout` memang sudah
    ada di berkas ini (blok `/api/`), jadi `assert "proxy_read_timeout" in
    teks` hijau bahkan pada konfigurasi yang cacat. Hanya dipakai untuk
    `/api/ws` dan `/api/` yang tak punya blok bersarang — `index("}")`
    pertama memang penutupnya.
    """
    m = re.search(r"^\s*location\s+" + re.escape(prefix) + r"\s*\{", teks, re.M)
    assert m, f"blok location {prefix} hilang"
    isi = teks[m.end():teks.index("}", m.end())]
    return "\n".join(b for b in isi.splitlines()
                     if not b.lstrip().startswith("#"))


def _detik(blok, direktif):
    m = re.search(direktif + r"\s+(\d+)s\s*;", blok)
    return int(m.group(1)) if m else None


class TestTimeoutWebSocket:
    """U21 — blok nginx `/api/ws` tanpa `proxy_*_timeout` = default 60 dtk.

    Hari ini tak ada yang putus HANYA karena heartbeat 25 dtk (sisi server di
    routes/websocket.py, sisi klien di useWebSocket.js) me-reset timer nginx
    terus-menerus. Kedua heartbeat itu hidup di event loop yang sama — satu
    panggilan sinkron yang menahan loop >60 dtk mematikan keduanya sekaligus,
    dan dengan `--workers 2` itu berarti ±50% klien WS terputus serentak.
    §8 panduan Hostinger sudah lama menyuruh 3600s; blok §6.2 yang justru
    disalin operator saat setup adalah salinan blok cacat ini. Penjaga di
    sini menagih keduanya sekaligus supaya tak bisa menyimpang lagi.
    """

    def test_blok_ws_punya_read_timeout_panjang(self):
        b = _blok_lokasi(_teks(VPS), "/api/ws")
        assert (_detik(b, "proxy_read_timeout") or 0) >= 3600

    def test_blok_ws_punya_send_timeout_panjang(self):
        b = _blok_lokasi(_teks(VPS), "/api/ws")
        assert (_detik(b, "proxy_send_timeout") or 0) >= 3600

    def test_blok_api_biasa_tetap_pendek(self):
        # Perbaikannya BER-SCOPE: menaikkan seluruh `/api/` ke 3600s berarti
        # ekspor PDF yang menggantung menahan koneksi satu jam, bukan gagal
        # dalam dua menit.
        b = _blok_lokasi(_teks(VPS), "/api/")
        assert _detik(b, "proxy_read_timeout") == 120

    def test_panduan_setup_sejalan_dengan_skrip(self):
        # §6.2 adalah blok yang disalin-tempel operator; kalau ia menyimpang
        # dari skrip, resep yang salah tetap terpasang untuk operator
        # berikutnya walau skripnya sudah benar.
        skrip = _blok_lokasi(_teks(VPS), "/api/ws")
        panduan = _blok_lokasi(_teks(PANDUAN), "/api/ws")
        for d in ("proxy_read_timeout", "proxy_send_timeout"):
            assert _detik(panduan, d) == _detik(skrip, d), d
