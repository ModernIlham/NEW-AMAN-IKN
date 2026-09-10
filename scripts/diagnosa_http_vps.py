#!/usr/bin/env python3
"""Diagnosis insiden HTTP 9 September 2026; HANYA MEMBACA di VPS.

Dikirim lewat stdin SSH, bukan disalin/diinstal di produksi. Tanpa argumen,
variabel lingkungan, glob, konfigurasi, permintaan HTTP, atau subprocess.
Target dan jendela waktu sengaja tetap: alat ini bukan pembaca berkas umum.

Tidak satu pun potongan log/exception dicetak. Hanya enum, hitungan, tanggal,
dan mode berkas yang keluar. Runner memvalidasi skema sekali lagi sebelum
mempublikasikan keluaran SSH (banner shell pun tidak boleh lolos).
"""
import collections
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import re
import stat
import sys
import time

UTC = dt.timezone.utc
MULAI = dt.datetime(2026, 9, 9, 5, 50, tzinfo=UTC)
AKHIR = dt.datetime(2026, 9, 9, 6, 10, tzinfo=UTC)  # inklusif sampai detik ini
LOG_NAMES = ("error.log", "error.log.1", "error.log.2.gz", "error.log.3.gz",
             "error.log.4.gz", "error.log.5.gz", "error.log.6.gz", "error.log.7.gz")
LOG_DIR = Path("/var/log/nginx")
DOCROOT = "/var/www/inventarisasi/frontend/build"
METADATA_PATHS = {
    "build": Path(DOCROOT),
    "index": Path(DOCROOT + "/index.html"),
    "index-sebelumnya": Path("/var/www/inventarisasi/frontend/build.old/index.html"),
}
KATEGORI = ("directory-index-forbidden", "internal-redirect-cycle",
            "index-missing", "permission-denied")
STATUS_LOG = ("selesai", "tidak-ada", "ditolak", "gagal-baca", "bukan-berkas",
              "batas-byte", "batas-waktu")
STATUS_META = ("ada", "tidak-ada", "ditolak", "gagal-baca", "bukan-berkas")
BATAS_BERKAS = 16 * 1024 * 1024  # byte setelah dekompresi, bukan ukuran gzip
BATAS_TOTAL = 64 * 1024 * 1024
BATAS_BARIS = 32 * 1024
BATAS_DETIK = 15
BATAS_LAPORAN = 65536
POLA_WAKTU = re.compile(r"^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) ")
POLA_PESAN = re.compile(
    r"^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} "
    r"\[(?:error|crit|alert|emerg|warn|notice|info|debug)\] "
    r"\d+#\d+: (?:\*\d+ )?(.*)$"
)


def iso(waktu):
    return waktu.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def waktu_log(baris):
    cocok = POLA_WAKTU.match(baris)
    if not cocok:
        return None
    try:
        # Error log tidak membawa offset. astimezone pada datetime naif memakai
        # zona lokal mesin untuk TANGGAL LOG, termasuk aturan DST historis.
        return dt.datetime.strptime(cocok[1], "%Y/%m/%d %H:%M:%S").astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        return None


def kategori_log(baris):
    cocok = POLA_PESAN.match(baris)
    if not cocok:
        return None
    # Request/query klien bukan pesan sistem: jangan mengklasifikasi umpan
    # "Permission denied" yang kebetulan muncul pada URL atau User-Agent.
    pesan = cocok[1].split(", client:", 1)[0].split(", server:", 1)[0]
    akar = re.escape(DOCROOT)
    if re.fullmatch(r'directory index of "' + akar + r'/" is forbidden', pesan):
        return "directory-index-forbidden"
    if re.match(r'^(?:open|stat)\(\) "' + akar + r'/index\.html" failed '
                r'\(2: No such file or directory\)(?:$| )', pesan):
        return "index-missing"
    if re.match(r'^(?:open|stat)\(\) "' + akar + r'(?:/|/index\.html)?" failed '
                r'\(13: Permission denied\)(?:$| )', pesan):
        return "permission-denied"
    if pesan == 'rewrite or internal redirection cycle while internally redirecting to "/index.html"':
        # Pesan ini TIDAK memuat docroot. Atribusi harus berasal dari field
        # server nginx (bukan Host kiriman klien) + dua URI yang sedang diuji.
        # Mapping server ke docroot produksi tidak diasumsikan telah dibaca.
        if re.search(
            r', server: (?:www\.)?amanikn-inventarisasi\.com, request: '
            r'"(?:GET|HEAD) /(?:index\.html)?(?:\?[^"\r\n ]*)? '
            r'HTTP/(?:1\.[01]|2\.0|3\.0)"(?:,|$)', baris
        ):
            return "internal-redirect-cycle"
    return None


def baca_aliran(aliran, nama, rekap, tenggat, anggaran, jam=time.monotonic):
    """Pemindai murni aliran biner; baris terlalu panjang dibuang seluruhnya."""
    hasil = {"nama": nama, "status": "selesai", "byte_dibaca": 0,
             "baris_diabaikan": 0, "awal_utc": None, "akhir_utc": None}
    buang_sambungan = False
    while True:
        if jam() >= tenggat:
            hasil["status"] = "batas-waktu"
            break
        sisa = min(BATAS_BERKAS - hasil["byte_dibaca"], anggaran)
        if sisa <= 0:
            hasil["status"] = "batas-byte"
            break
        try:
            mentah = aliran.readline(min(BATAS_BARIS + 1, sisa))
        except (OSError, EOFError, ValueError):
            hasil["status"] = "gagal-baca"
            break
        if not mentah:
            break
        hasil["byte_dibaca"] += len(mentah)
        anggaran -= len(mentah)
        utuh = mentah.endswith(b"\n")
        if buang_sambungan or not utuh or len(mentah) > BATAS_BARIS:
            if not buang_sambungan:
                hasil["baris_diabaikan"] += 1
            buang_sambungan = not utuh
            continue
        baris = mentah.decode("utf-8", errors="replace").rstrip("\r\n")
        waktu = waktu_log(baris)
        if waktu is None:
            hasil["baris_diabaikan"] += 1
            continue
        stempel = iso(waktu)
        hasil["awal_utc"] = min(hasil["awal_utc"] or stempel, stempel)
        hasil["akhir_utc"] = max(hasil["akhir_utc"] or stempel, stempel)
        if MULAI <= waktu <= AKHIR:
            kategori = kategori_log(baris)
            if kategori:
                rekap[(iso(waktu.replace(second=0)), kategori)] += 1
    return hasil


def buka_log(nama):
    if nama not in LOG_NAMES:
        raise ValueError("Target ditolak")
    # O_NOFOLLOW menolak symlink; fstat menolak FIFO/perangkat (O_NONBLOCK
    # mencegah FIFO menggantung sebelum fstat). Tidak menulis maupun atime
    # secara sengaja; filesystem dapat memperbarui atime ketika membaca.
    fd = os.open(LOG_DIR / nama, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("Bukan berkas biasa")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def metadata():
    keluaran = []
    for nama, jalur in METADATA_PATHS.items():
        baris = {"nama": nama, "status": "ada", "mode": None, "mtime_utc": None}
        try:
            info = jalur.lstat()  # jangan ikuti symlink ke target di luar daftar
            if not (stat.S_ISDIR(info.st_mode) if nama == "build" else stat.S_ISREG(info.st_mode)):
                baris["status"] = "bukan-berkas"
            else:
                baris["mode"] = format(stat.S_IMODE(info.st_mode), "04o")
                baris["mtime_utc"] = iso(dt.datetime.fromtimestamp(info.st_mtime, UTC))
        except FileNotFoundError:
            baris["status"] = "tidak-ada"
        except PermissionError:
            baris["status"] = "ditolak"
        except (OSError, ValueError, OverflowError):
            baris["status"] = "gagal-baca"
        keluaran.append(baris)
    return keluaran


def kumpulkan():
    rekap = collections.Counter()
    berkas = []
    tenggat = time.monotonic() + BATAS_DETIK
    anggaran = BATAS_TOTAL
    for nama in LOG_NAMES:
        hasil = {"nama": nama, "status": "selesai", "byte_dibaca": 0,
                 "baris_diabaikan": 0, "awal_utc": None, "akhir_utc": None}
        if time.monotonic() >= tenggat:
            hasil["status"] = "batas-waktu"
        elif anggaran <= 0:
            hasil["status"] = "batas-byte"
        else:
            try:
                with buka_log(nama) as mentah:
                    if nama.endswith(".gz"):
                        with gzip.GzipFile(fileobj=mentah) as aliran:
                            hasil = baca_aliran(aliran, nama, rekap, tenggat, anggaran)
                    else:
                        hasil = baca_aliran(mentah, nama, rekap, tenggat, anggaran)
            except FileNotFoundError:
                hasil["status"] = "tidak-ada"
            except PermissionError:
                hasil["status"] = "ditolak"
            except ValueError:
                hasil["status"] = "bukan-berkas"
            except (OSError, EOFError):
                hasil["status"] = "gagal-baca"
        anggaran -= hasil["byte_dibaca"]
        berkas.append(hasil)
    return {
        "versi": 1, "mulai_utc": iso(MULAI), "akhir_utc": iso(AKHIR),
        "dibaca_utc": iso(dt.datetime.now(UTC)), "berkas": berkas,
        "kejadian": [{"menit_utc": menit, "kategori": kategori, "jumlah": jumlah}
                     for (menit, kategori), jumlah in sorted(rekap.items())],
        "metadata": metadata(),
    }


def validasi_laporan(data):
    """Allowlist ketat: tidak pernah mengembalikan/mencetak nilai yang ditolak."""
    def bentuk(nilai, kunci):
        if type(nilai) is not dict or set(nilai) != set(kunci.split()):
            raise ValueError("Laporan ditolak")

    def tanggal(nilai, kosong=False):
        if kosong and nilai is None:
            return
        if type(nilai) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", nilai):
            raise ValueError("Laporan ditolak")
        dt.datetime.strptime(nilai, "%Y-%m-%dT%H:%M:%SZ")

    def angka(nilai, maksimum):
        if type(nilai) is not int or not 0 <= nilai <= maksimum:
            raise ValueError("Laporan ditolak")

    bentuk(data, "versi mulai_utc akhir_utc dibaca_utc berkas kejadian metadata")
    if type(data["versi"]) is not int or data["versi"] != 1 or data["mulai_utc"] != iso(MULAI) or data["akhir_utc"] != iso(AKHIR):
        raise ValueError("Laporan ditolak")
    tanggal(data["dibaca_utc"])
    if type(data["berkas"]) is not list or len(data["berkas"]) != len(LOG_NAMES):
        raise ValueError("Laporan ditolak")
    for baris, nama in zip(data["berkas"], LOG_NAMES):
        bentuk(baris, "nama status byte_dibaca baris_diabaikan awal_utc akhir_utc")
        if baris["nama"] != nama or baris["status"] not in STATUS_LOG:
            raise ValueError("Laporan ditolak")
        angka(baris["byte_dibaca"], BATAS_BERKAS)
        angka(baris["baris_diabaikan"], BATAS_BERKAS)
        tanggal(baris["awal_utc"], kosong=True)
        tanggal(baris["akhir_utc"], kosong=True)
    if type(data["kejadian"]) is not list or len(data["kejadian"]) > 84:
        raise ValueError("Laporan ditolak")
    for baris in data["kejadian"]:
        bentuk(baris, "menit_utc kategori jumlah")
        tanggal(baris["menit_utc"])
        if (baris["kategori"] not in KATEGORI or not baris["menit_utc"].endswith(":00Z")
                or not iso(MULAI) <= baris["menit_utc"] <= iso(AKHIR)):
            raise ValueError("Laporan ditolak")
        angka(baris["jumlah"], BATAS_TOTAL)
    if type(data["metadata"]) is not list or len(data["metadata"]) != len(METADATA_PATHS):
        raise ValueError("Laporan ditolak")
    for baris, nama in zip(data["metadata"], METADATA_PATHS):
        bentuk(baris, "nama status mode mtime_utc")
        if baris["nama"] != nama or baris["status"] not in STATUS_META:
            raise ValueError("Laporan ditolak")
        if baris["mode"] is not None and (type(baris["mode"]) is not str or not re.fullmatch(r"[0-7]{4}", baris["mode"])):
            raise ValueError("Laporan ditolak")
        tanggal(baris["mtime_utc"], kosong=True)
    return data


def ringkasan_dari_stdin():
    """Dipanggil HANYA di runner, keluaran SSH belum tepercaya."""
    try:
        teks = sys.stdin.read(BATAS_LAPORAN + 1)
        if len(teks) > BATAS_LAPORAN:
            raise ValueError("Laporan terlalu besar")
        data = validasi_laporan(json.loads(teks))
    except Exception:
        print("Laporan diagnosis ditolak; keluaran mentah tidak dipublikasikan.")
        return 1
    print("# Diagnosis HTTP VPS — 9 September 2026\n")
    print("Hanya empat kategori log nginx dan metadata saat dibaca. Jumlah nol BUKAN bukti tidak ada gangguan; log dapat hilang, terpotong, atau memakai jalur lain.\n")
    print("Timestamp error log memakai zona lokal VPS saat kejadian lalu diubah ke UTC. Perubahan zona mesin sejak kejadian belum dapat diverifikasi.\n")
    print("Redirect-cycle diatribusikan lewat field server AMAN dan URI akar/index; pesan nginx itu tidak memuat docroot. Konfigurasi tidak dibaca.\n")
    print("```json\n" + json.dumps(data, indent=2, ensure_ascii=True) + "\n```")
    return 0


def main():
    try:
        if len(sys.argv) != 1:
            return 2
        print(json.dumps(validasi_laporan(kumpulkan()), ensure_ascii=True))
        return 0
    except Exception:
        # Jangan cetak traceback, pesan OSError, nama file, atau isi lingkungan.
        return 1


if __name__ == "__main__":
    sys.exit(main())
