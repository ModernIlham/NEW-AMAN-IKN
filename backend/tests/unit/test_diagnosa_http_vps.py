"""Bukti perilaku parser dan pagar publikasi diagnosis produksi."""
import collections
import datetime as dt
import gzip
import importlib.util
import io
import json
from pathlib import Path
import re
import time

import pytest
import yaml

AKAR = Path(__file__).resolve().parents[3]
SKRIP = AKAR / "scripts/diagnosa_http_vps.py"
ALUR = AKAR / ".github/workflows/diagnosa-http-vps.yml"
spec = importlib.util.spec_from_file_location("diagnosa_http_vps_uji", SKRIP)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
CANARY = 'RAHASIA_UJI_JANGAN_KELUAR'


def baris(pesan, waktu=None, server="amanikn-inventarisasi.com", uri="/"):
    waktu = waktu or dt.datetime(2026, 9, 9, 5, 57, 30, tzinfo=dt.timezone.utc)
    lokal = waktu.astimezone().strftime("%Y/%m/%d %H:%M:%S")
    return (f'{lokal} [error] 123#123: *45 {pesan}, client: 192.0.2.42, '
            f'server: {server}, request: "GET {uri} HTTP/2.0", '
            f'host: "example.invalid", referrer: "https://example.invalid/?token={CANARY}"\n')


DIRECTORY = f'directory index of "{d.DOCROOT}/" is forbidden'
CYCLE = 'rewrite or internal redirection cycle while internally redirecting to "/index.html"'
MISSING = f'open() "{d.DOCROOT}/index.html" failed (2: No such file or directory)'
DENIED = f'open() "{d.DOCROOT}/index.html" failed (13: Permission denied)'


def pindai(teks, **kwargs):
    rekap = collections.Counter()
    hasil = d.baca_aliran(io.BytesIO(teks.encode()), "error.log", rekap,
                         100, kwargs.pop("anggaran", d.BATAS_TOTAL), jam=lambda: 0,
                         **kwargs)
    return hasil, rekap


@pytest.mark.parametrize("pesan,kategori", [
    (DIRECTORY, "directory-index-forbidden"), (CYCLE, "internal-redirect-cycle"),
    (MISSING, "index-missing"), (DENIED, "permission-denied"),
])
def test_menemukan_empat_gejala_dan_tidak_memantulkan_isi_log(pesan, kategori):
    hasil, rekap = pindai(baris(pesan))
    assert hasil["status"] == "selesai"
    assert rekap == {("2026-09-09T05:57:00Z", kategori): 1}
    assert hasil["awal_utc"] == hasil["akhir_utc"] == "2026-09-09T05:57:30Z"
    assert CANARY not in str((hasil, rekap))
    assert "192.0.2.42" not in str((hasil, rekap))


@pytest.mark.parametrize("teks", [
    baris(DIRECTORY.replace("/build/", "/build-lain/")),
    baris(MISSING.replace("index.html", "secret.env")),
    baris(DENIED.replace("/inventarisasi/", "/situs-lain/")),
    baris(CYCLE, server="evil-amanikn-inventarisasi.com"),
    baris(CYCLE, server="example.invalid", uri="/?amanikn-inventarisasi.com"),
    baris(CYCLE, uri="/api/health"),
    baris("upstream timed out", uri="/?" + DENIED.replace(" ", "%20")),
    baris("upstream timed out", uri="/?" + DIRECTORY.replace(" ", "%20")),
    baris(CYCLE.replace("/index.html", "/lain.html")),
    "2026/09/09 99:99:99 [error] 123#123: " + DIRECTORY + "\n",
    CANARY + "\n",
])
def test_bukan_gejala_aman_tidak_dianggap_temuan(teks):
    _, rekap = pindai(teks)
    assert not rekap


def test_filter_jendela_inklusif_dan_agregasi_per_menit():
    satu_detik = dt.timedelta(seconds=1)
    waktu = [d.MULAI - satu_detik, d.MULAI, d.MULAI + satu_detik,
             d.AKHIR, d.AKHIR + satu_detik]
    hasil, rekap = pindai("".join(baris(DIRECTORY, t) for t in waktu))
    assert rekap == {("2026-09-09T05:50:00Z", "directory-index-forbidden"): 2,
                     ("2026-09-09T06:10:00Z", "directory-index-forbidden"): 1}
    assert hasil["awal_utc"] == "2026-09-09T05:49:59Z"
    assert hasil["akhir_utc"] == "2026-09-09T06:10:01Z"


def test_gzip_dibaca_sungguhan_dan_izin_gagal_tidak_membocorkan_exception(monkeypatch):
    def buka(nama):
        if nama == "error.log":
            return io.BytesIO(baris(DIRECTORY).encode())
        if nama == "error.log.1":
            raise PermissionError(CANARY)
        if nama == "error.log.2.gz":
            return io.BytesIO(gzip.compress(baris(CYCLE).encode()))
        if nama == "error.log.3.gz":
            return io.BytesIO(b"bukan-gzip-" + CANARY.encode())
        raise FileNotFoundError(CANARY)
    monkeypatch.setattr(d, "buka_log", buka)
    monkeypatch.setattr(d, "metadata", lambda: metadata_kosong())
    laporan = d.kumpulkan()
    assert [b["status"] for b in laporan["berkas"][:4]] == ["selesai", "ditolak", "selesai", "gagal-baca"]
    assert {b["kategori"] for b in laporan["kejadian"]} == {"directory-index-forbidden", "internal-redirect-cycle"}
    assert CANARY not in json.dumps(d.validasi_laporan(laporan))


def test_gzip_terpotong_dinyatakan_gagal_baca(monkeypatch):
    data = gzip.compress(baris(DIRECTORY).encode())[:-8]
    monkeypatch.setattr(d, "buka_log", lambda nama: io.BytesIO(data))
    monkeypatch.setattr(d, "metadata", lambda: metadata_kosong())
    laporan = d.kumpulkan()
    assert laporan["berkas"][2]["status"] == "gagal-baca"


def test_batas_byte_setelah_dekompresi(monkeypatch):
    monkeypatch.setattr(d, "BATAS_BERKAS", 100)
    data = gzip.compress((baris(DIRECTORY) * 100).encode())
    rekap = collections.Counter()
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as sumber:
        hasil = d.baca_aliran(sumber, "error.log.2.gz", rekap, 100, 200, jam=lambda: 0)
    assert hasil["status"] == "batas-byte"
    assert hasil["byte_dibaca"] == 100
    assert not rekap


def test_batas_total_dan_waktu_dilaporkan_sebagai_batas_bukan_eof(monkeypatch):
    hasil, rekap = pindai(baris(DIRECTORY), anggaran=20)
    assert hasil["status"] == "batas-byte" and hasil["byte_dibaca"] == 20
    hasil = d.baca_aliran(io.BytesIO(baris(DIRECTORY).encode()), "error.log", rekap,
                         1, 100, jam=lambda: 2)
    assert hasil["status"] == "batas-waktu" and hasil["byte_dibaca"] == 0
    monkeypatch.setattr(d, "BATAS_TOTAL", 0)
    monkeypatch.setattr(d, "metadata", lambda: metadata_kosong())
    monkeypatch.setattr(d, "buka_log", lambda nama: pytest.fail("Anggaran nol tidak boleh membuka file"))
    assert all(b["status"] == "batas-byte" for b in d.kumpulkan()["berkas"])


def test_baris_terpotong_dan_sambungan_panjang_tidak_dianggap_baris_baru(monkeypatch):
    monkeypatch.setattr(d, "BATAS_BARIS", 512)
    teks = "x" * 513 + baris(DIRECTORY) + baris(MISSING) + baris(DENIED).rstrip("\n")
    hasil, rekap = pindai(teks)
    assert hasil["baris_diabaikan"] == 2
    assert rekap == {("2026-09-09T05:57:00Z", "index-missing"): 1}


def test_baris_lebih_satu_byte_tetap_ditolak_meski_berakhir_newline(monkeypatch):
    teks = baris(DIRECTORY)
    monkeypatch.setattr(d, "BATAS_BARIS", len(teks.encode()) - 1)
    hasil, rekap = pindai(teks)
    assert not rekap and hasil["baris_diabaikan"] == 1


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="tzset hanya tersedia pada POSIX; produksi Linux")
def test_timezone_historis_bukan_offset_hari_ini(monkeypatch):
    try:
        with monkeypatch.context() as m:
            m.setenv("TZ", "America/New_York")
            time.tzset()
            assert d.iso(d.waktu_log("2026/01/09 05:57:00 x")) == "2026-01-09T10:57:00Z"
            assert d.iso(d.waktu_log("2026/07/09 05:57:00 x")) == "2026-07-09T09:57:00Z"
    finally:
        time.tzset()


def metadata_kosong():
    return [{"nama": n, "status": "tidak-ada", "mode": None, "mtime_utc": None}
            for n in d.METADATA_PATHS]


@pytest.fixture
def laporan(monkeypatch):
    monkeypatch.setattr(d, "metadata", metadata_kosong)
    def tidak_ada(nama):
        raise FileNotFoundError(CANARY)
    monkeypatch.setattr(d, "buka_log", tidak_ada)
    return d.kumpulkan()


def test_metadata_hanya_stat_bukan_isi_berkas(tmp_path, monkeypatch):
    build = tmp_path / "build"
    build.mkdir()
    index = build / "index.html"
    index.write_text(CANARY)
    monkeypatch.setattr(d, "METADATA_PATHS", {"build": build, "index": index,
                                              "index-sebelumnya": tmp_path / "absen"})
    hasil = d.metadata()
    assert [b["status"] for b in hasil] == ["ada", "ada", "tidak-ada"]
    assert re.fullmatch(r"[0-7]{4}", hasil[1]["mode"])
    assert CANARY not in json.dumps(hasil)


def test_metadata_permission_error_tetap_terbaca_tanpa_pesan_asli(monkeypatch):
    class Dilarang:
        def lstat(self):
            raise PermissionError(CANARY)
    monkeypatch.setattr(d, "METADATA_PATHS", {"build": Dilarang()})
    assert d.metadata() == [{"nama": "build", "status": "ditolak", "mode": None, "mtime_utc": None}]


def test_pembukaan_log_readonly_menolak_fifo_dan_menutup_descriptor(monkeypatch):
    from types import SimpleNamespace
    panggilan = []
    monkeypatch.setattr(d.os, "O_NOFOLLOW", 0x40000, raising=False)
    monkeypatch.setattr(d.os, "O_NONBLOCK", 0x20000, raising=False)
    monkeypatch.setattr(d.os, "open", lambda path, flags: panggilan.append((str(path), flags)) or 99)
    monkeypatch.setattr(d.os, "fstat", lambda fd: SimpleNamespace(st_mode=d.stat.S_IFIFO))
    monkeypatch.setattr(d.os, "close", lambda fd: panggilan.append(fd))
    with pytest.raises(ValueError, match="Bukan berkas biasa"):
        d.buka_log("error.log")
    assert panggilan == [(str(d.LOG_DIR / "error.log"), d.os.O_RDONLY | 0x60000), 99]


@pytest.mark.parametrize("jalur", ["../secret.env", "/root/secret.env", "access.log", "error.log.8.gz"])
def test_target_asing_ditolak_sebelum_dibaca(jalur):
    with pytest.raises(ValueError, match="Target ditolak"):
        d.buka_log(jalur)


@pytest.mark.parametrize("mutasi", [
    lambda x: x.update({CANARY: CANARY}),
    lambda x: x["berkas"][0].update(nama=CANARY),
    lambda x: x["berkas"][0].update(status=CANARY),
    lambda x: x["berkas"][0].update(awal_utc=CANARY),
    lambda x: x["berkas"][0].update(byte_dibaca=CANARY),
    lambda x: x["berkas"][0].update(byte_dibaca=True),
    lambda x: x["metadata"][0].update(mode=CANARY),
    lambda x: x["metadata"][0].update(mtime_utc=CANARY),
    lambda x: x.update(dibaca_utc=CANARY),
    lambda x: x.update(kejadian=[{"menit_utc": "2026-09-09T05:57:00Z", "kategori": CANARY, "jumlah": 1}]),
    lambda x: x.update(kejadian=[{"menit_utc": "2026-09-09T05:57:00Z", "kategori": "index-missing", "jumlah": CANARY}]),
])
def test_runner_menolak_nilai_asing_tanpa_memantulkannya(laporan, mutasi, monkeypatch, capsys):
    mutasi(laporan)
    monkeypatch.setattr(d.sys, "stdin", io.StringIO(json.dumps(laporan)))
    assert d.ringkasan_dari_stdin() == 1
    assert CANARY not in capsys.readouterr().out


@pytest.mark.parametrize("mentah", [CANARY, CANARY + "\n{}", "x" * 65537, '{"rusak":'],
                         ids=["banner", "banner-dan-json", "terlalu-besar", "json-rusak"])
def test_banner_exception_dan_laporan_besar_tidak_dipublikasikan(mentah, monkeypatch, capsys):
    monkeypatch.setattr(d.sys, "stdin", io.StringIO(mentah))
    assert d.ringkasan_dari_stdin() == 1
    assert capsys.readouterr().out == "Laporan diagnosis ditolak; keluaran mentah tidak dipublikasikan.\n"


def test_laporan_sah_dipublikasikan_dengan_batas_penafsiran(laporan, monkeypatch, capsys):
    monkeypatch.setattr(d.sys, "stdin", io.StringIO(json.dumps(laporan)))
    assert d.ringkasan_dari_stdin() == 0
    keluar = capsys.readouterr().out
    assert "Jumlah nol BUKAN bukti" in keluar and "tidak memuat docroot" in keluar
    assert CANARY not in keluar


def test_exception_tingkat_atas_tidak_mencetak_traceback(monkeypatch, capsys):
    def gagal():
        raise RuntimeError(CANARY)
    monkeypatch.setattr(d, "kumpulkan", gagal)
    monkeypatch.setattr(d.sys, "argv", ["-"])
    assert d.main() == 1
    assert capsys.readouterr() == ("", "")


def test_workflow_manual_main_immutable_ci_dan_antrean_deploy():
    alur = yaml.safe_load(ALUR.read_text(encoding="utf-8"))
    pemicu = alur.get("on", alur.get(True))
    assert pemicu == {"workflow_dispatch": None}
    assert alur["concurrency"] == {"group": "deploy-vps", "cancel-in-progress": False}
    assert alur["permissions"] == {"contents": "read", "actions": "read"}
    job = alur["jobs"]["diagnosis"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert job["steps"][0]["with"]["ref"] == "${{ github.sha }}"
    langkah = "\n".join(s.get("run", "") for s in job["steps"])
    assert '"$(git rev-parse HEAD)" != "$GITHUB_SHA"' in langkah
    assert "head_sha=$GITHUB_SHA" in langkah and 'r.get("conclusion")=="success"' in langkah
    assert langkah.count("ssh -T") == 1
    assert "'python3 -B - 2>/dev/null'" in langkah
    assert '< scripts/diagnosa_http_vps.py > "$laporan" 2>/dev/null' in langkah
    assert 'cat "$laporan"' not in langkah
    assert 'm["ringkasan_dari_stdin"]()' in langkah
    assert langkah.index('m["ringkasan_dari_stdin"]()') < langkah.index('cat "$RUNNER_TEMP/diagnosa-http-vps.md"')


def test_skrip_remote_tidak_menulis_menjalankan_program_atau_menerima_path():
    import ast
    tree = ast.parse(SKRIP.read_text(encoding="utf-8"))
    imports = {n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)}
    assert not imports.intersection({"subprocess", "socket", "requests", "urllib", "shutil"})
    panggilan = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not panggilan.intersection({"open", "os.system", "os.chmod", "os.chown", "os.remove", "os.getenv", "os.environ.get"})
    assert "os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW" in SKRIP.read_text(encoding="utf-8")
    assert "len(sys.argv) != 1" in SKRIP.read_text(encoding="utf-8")
