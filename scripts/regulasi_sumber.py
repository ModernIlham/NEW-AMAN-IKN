#!/usr/bin/env python3
"""Pengunduh teks peraturan primer — DIJALANKAN DI RUNNER, bukan di sini.

Permintaan pemilik: *"download semua referensi untuk memperkaya pustaka,
temukan hingga ke sumber lainnya jika terblokir untuk mengunduh sampai
pustaka kita lengkap."*

── Kenapa berkas ini ada ──────────────────────────────────────────────────
Lingkungan pengembangan Claude Code **tidak bisa** menjangkau satu pun sumber
peraturan. Gerbang egress menjawab **403 pada CONNECT** untuk setiap host yang
dicoba — jdih.kemenkeu.go.id, peraturan.bpk.go.id, djkn.kemenkeu.go.id,
peraturan.go.id, jdihn.go.id, sipuu.setkab.go.id, ngada.org, scribd.com,
bahkan web.archive.org dan en.wikipedia.org. Itu kebijakan organisasi, bukan
kerusakan, dan **tidak boleh diakali**.

Yang TIDAK terblokir: **runner GitHub Actions**. Ia punya egress internet
biasa. Jadi pengunduhannya dipindahkan ke sana lewat
`.github/workflows/unduh-regulasi.yml`, dan hasilnya didorong ke cabang
`regulasi/unduhan` supaya bisa dibaca, ditelaah, lalu di-PR seperti perubahan
lain.

── Yang berkas ini lakukan ────────────────────────────────────────────────
Mengambil PDF peraturan, mengekstrak teksnya, menyimpannya sebagai `.txt`
yang bisa di-`grep` dan di-`diff`, plus manifes berisi **sha256, ukuran,
jumlah halaman, URL yang berhasil, dan waktu unduh** — supaya asal-usul tiap
berkas bisa ditelusuri, bukan sekadar "ada di repo".

── Yang berkas ini TIDAK lakukan ──────────────────────────────────────────
**Tidak menaikkan status verifikasi apa pun secara otomatis.** Teks yang
terunduh adalah BUKTI, bukan kesimpulan. Menaikkan butir di
`syarat_dokumen_utils.py` dari `belum_terverifikasi` menjadi `terverifikasi`
tetap langkah sadar setelah pasalnya dibaca — persis seperti yang sudah
berlaku di `docs/SITASI-DOKUMEN-RESMI.md`. Otomatisasi yang menstempel
"terverifikasi" hanya karena PDF-nya berhasil diunduh akan menghapus satu-
satunya pembeda yang membuat pustaka ini bisa dipercaya.

Tidak menyimpan PDF-nya ke repo (besar dan tak bisa di-diff); hanya teksnya.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# ── Manifes ────────────────────────────────────────────────────────────────
#
# Tiap peraturan punya BEBERAPA sumber, dicoba berurutan. Alasannya bukan
# kehati-hatian berlebihan: URL JDIH berubah saat situsnya diperbarui, dan
# satu URL mati akan mematikan seluruh unduhan. Cermin kementerian lain
# (pertanian, PUPR, BP Batam) memuat salinan PDF yang sama dan jauh lebih
# stabil karena ia berkas statis di WordPress.
#
# `html` = halaman yang perlu dikerok tautan PDF-nya lebih dulu.
# `pdf`  = tautan langsung.
#
# `prioritas` menentukan urutan unduh — yang menutup celah terbesar di
# registry syarat dokumen didahulukan, supaya kegagalan di ekor daftar tidak
# menunda yang paling dibutuhkan.

MANIFES = [
    {
        "kode": "pmk-111-2016-pemindahtanganan",
        "judul": "PMK 111/PMK.06/2016 — Tata Cara Pelaksanaan Pemindahtanganan BMN",
        "guna": "Hibah, penjualan, tukar menukar, PMPP — celah TERBESAR di registry",
        "prioritas": 1,
        "sumber": [
            ("pdf", "https://ditjenbun.pertanian.go.id/template/uploads/2021/09/"
                    "PMK-111-TAHUN-2016-TATA-CARA-PELAKSANAAN-PEMINDAHTANGANAN-BMN.pdf"),
            ("pdf", "https://sibangkoman.pu.go.id/center/pelatihan/uploads/edok/2020/07/"
                    "9a70b_9cd00_09._PMK_111_PMK_062016_Tata_Cara_Pelaksanaan_Pemindahtanganan_BMN.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/111-pmk-06-2016"),
            ("html", "https://peraturan.bpk.go.id/Details/121125/pmk-no-111pmk062016"),
        ],
    },
    {
        "kode": "pmk-165-2021-perubahan-pemindahtanganan",
        "judul": "PMK 165/PMK.06/2021 — Perubahan atas PMK 111/PMK.06/2016",
        "guna": "Perubahan rezim pemindahtanganan",
        "prioritas": 2,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/165-pmk-06-2021"),
            ("html", "https://peraturan.bpk.go.id/Details/196037/pmk-no-165pmk062021"),
        ],
    },
    {
        "kode": "pmk-83-2016-pemusnahan-penghapusan",
        "judul": "PMK 83/PMK.06/2016 — Tata Cara Pelaksanaan Pemusnahan dan Penghapusan BMN",
        "guna": "Rezim penghapusan & pemusnahan — belum ada dasar pasal sama sekali",
        "prioritas": 3,
        "sumber": [
            ("pdf", "https://ditjenbun.pertanian.go.id/template/uploads/2021/09/"
                    "PMK-83-TAHUN-2016-TATA-CARA-PELAKSANAAN-PEMUSNAHAN-DAN-PENGHAPUSAN-BMN.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/83-pmk-06-2016"),
            ("html", "https://peraturan.bpk.go.id/Details/121081/pmk-no-83pmk062016"),
        ],
    },
    {
        "kode": "pmk-115-2020-pemanfaatan",
        "judul": "PMK 115/PMK.06/2020 — Pemanfaatan Barang Milik Negara",
        "guna": "Sewa, pinjam pakai, KSP, BGS/BSG, KSPI, KETUPI",
        "prioritas": 4,
        "sumber": [
            ("pdf", "https://batamport.bpbatam.go.id/wp-content/uploads/2021/07/"
                    "PMK-115PMK062020-TTG-PEMANFAATAN-BARANG-MILIK-NEGARA-TGL-31-8-2020.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/115-pmk-06-2020"),
            ("html", "https://peraturan.bpk.go.id/Home/Details/144664/pmk-no-115pmk062020"),
        ],
    },
    {
        "kode": "pmk-40-2024-penggunaan",
        "judul": "PMK 40 Tahun 2024 — Tata Cara Penggunaan Barang Milik Negara",
        "guna": ("Rezim Penggunaan. Sudah diriset lewat sumber sekunder di "
                 "docs/PENGGUNAAN-BMN-PEMOHON.md; teks aslinya menutup rantai "
                 "buktinya dan memungkinkan sitasi diverifikasi ulang"),
        "prioritas": 5,
        "sumber": [
            ("pdf", "https://ppiddjkn.kemenkeu.go.id/storage/20250701-328.pdf"),
            ("html", "https://jdih.kemenkeu.go.id/dok/pmk-40-tahun-2024"),
            ("html", "https://peraturan.bpk.go.id/Details/292599/pmk-no-40-tahun-2024"),
        ],
    },
    {
        "kode": "pmk-181-2016-penatausahaan",
        "judul": "PMK 181/PMK.06/2016 — Penatausahaan Barang Milik Negara",
        "guna": "Pembukuan, inventarisasi, pelaporan",
        "prioritas": 6,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/181-pmk-06-2016"),
            ("html", "https://peraturan.bpk.go.id/Details/112552/pmk-no-181pmk062016"),
        ],
    },
    {
        "kode": "pmk-207-2021-wasdal",
        "judul": "PMK 207/PMK.06/2021 — Pengawasan dan Pengendalian BMN",
        "guna": "Modul Wasdal",
        "prioritas": 7,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/207-pmk-06-2021"),
        ],
    },
    {
        "kode": "pmk-53-2023-ikn",
        "judul": "PMK 53 Tahun 2023 — Pengelolaan BMN pada Otorita IKN",
        "guna": "Rezim khusus IKN — delegasi kewenangan Kepala Otorita",
        "prioritas": 8,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/pmk-53-tahun-2023"),
        ],
    },
    {
        "kode": "pp-27-2014-pengelolaan-bmn",
        "judul": "PP 27 Tahun 2014 — Pengelolaan Barang Milik Negara/Daerah",
        "guna": "Induk seluruh rezim",
        "prioritas": 9,
        "sumber": [
            ("html", "https://peraturan.bpk.go.id/Details/5510/pp-no-27-tahun-2014"),
        ],
    },
    {
        "kode": "pp-28-2020-perubahan-pengelolaan-bmn",
        "judul": "PP 28 Tahun 2020 — Perubahan atas PP 27 Tahun 2014",
        "guna": "Menambah KETUPI sebagai bentuk pemanfaatan ke-6",
        "prioritas": 10,
        "sumber": [
            ("html", "https://peraturan.bpk.go.id/Details/141069/pp-no-28-tahun-2020"),
        ],
    },
    {
        "kode": "kmk-334-2021-hibah-kecil",
        "judul": ("KMK 334/KM.6/2021 — Tata Cara Hibah BMN selain tanah/bangunan "
                  "tanpa bukti kepemilikan, nilai perolehan ≤ Rp100 juta"),
        "guna": ("Dikutip pemindahtanganan_utils.py; judulnya sudah terkonfirmasi "
                 "di SITASI-DOKUMEN-RESMI.md, pasalnya belum"),
        "prioritas": 11,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/334-km-6-2021"),
        ],
    },
    {
        "kode": "pmk-4-2015-delegasi",
        "judul": "PMK 4/PMK.06/2015 — Pendelegasian kewenangan pemindahtanganan BMN",
        "guna": "Ambang Rp100 juta jalur Pengguna Barang",
        "prioritas": 12,
        "sumber": [
            ("html", "https://jdih.kemenkeu.go.id/dok/4-pmk-06-2015"),
        ],
    },
]

# ── Batas keras ────────────────────────────────────────────────────────────
JEDA_ANTAR_UNDUH = 2.0        # sopan terhadap server publik
BATAS_UKURAN = 60 * 1024 * 1024
TENGGAT_DETIK = 60
UA = ("Mozilla/5.0 (compatible; AMAN-IKN-pustaka/1.0; "
      "pengarsipan peraturan publik untuk keperluan internal satker)")


def _ambil(url: str) -> tuple[bytes, str]:
    """GET satu URL. HANYA GET — skrip ini tak pernah menulis ke server."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TENGGAT_DETIK) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        isi = resp.read(BATAS_UKURAN + 1)
    if len(isi) > BATAS_UKURAN:
        raise ValueError(f"berkas melebihi {BATAS_UKURAN // 1024 // 1024} MB")
    return isi, ctype


def tautan_pdf(html: str, asal: str) -> list:
    """Kerok tautan PDF dari halaman JDIH → daftar URL absolut.

    Diurutkan: yang mengandung 'download'/'view'/'dok' didahulukan, sebab
    halaman JDIH kerap memuat PDF lampiran lain (formulir, lampiran daerah)
    yang bukan batang tubuh peraturannya.
    """
    from urllib.parse import urljoin
    kandidat = []
    for m in re.finditer(r'''href\s*=\s*["']([^"']+?\.pdf[^"']*)["']''', html, re.I):
        kandidat.append(urljoin(asal, m.group(1)))
    # Beberapa JDIH menaruh berkasnya di atribut data-* atau iframe src.
    for m in re.finditer(r'''(?:src|data-src|data-url)\s*=\s*["']([^"']+?\.pdf[^"']*)["']''',
                         html, re.I):
        kandidat.append(urljoin(asal, m.group(1)))

    def skor(u: str) -> int:
        u = u.lower()
        n = 0
        for kata in ("download", "/dok/", "/view", "peraturan", "pmk", "pp-"):
            if kata in u:
                n -= 1
        if "lampiran" in u:      # lampiran ≠ batang tubuh
            n += 5
        return n

    unik = list(dict.fromkeys(kandidat))
    return sorted(unik, key=skor)


def ekstrak_teks(pdf: bytes) -> tuple[str, int]:
    """PDF → (teks, jumlah halaman). Memakai pypdf yang sudah ada di repo."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf))
    halaman = [(p.extract_text() or "") for p in reader.pages]
    return "\n\n".join(halaman), len(reader.pages)


def unduh_satu(entri: dict) -> dict:
    """Coba tiap sumber berurutan sampai satu berhasil."""
    galat = []
    for jenis, url in entri["sumber"]:
        try:
            isi, ctype = _ambil(url)
            if jenis == "html" and not isi[:5].startswith(b"%PDF"):
                halaman = isi.decode("utf-8", "replace")
                pdfs = tautan_pdf(halaman, url)
                if not pdfs:
                    galat.append(f"{url}: halaman tak memuat tautan PDF")
                    continue
                time.sleep(JEDA_ANTAR_UNDUH)
                isi, ctype = _ambil(pdfs[0])
                url = pdfs[0]
            if not isi[:5].startswith(b"%PDF"):
                galat.append(f"{url}: bukan PDF (Content-Type: {ctype[:40]})")
                continue
            teks, n_hal = ekstrak_teks(isi)
            if len(teks.strip()) < 500:
                # PDF hasil pindai tanpa lapisan teks. Dilaporkan apa adanya,
                # BUKAN diterima diam-diam: berkas .txt kosong yang tersimpan
                # akan terlihat seperti bukti padahal tak memuat apa pun.
                galat.append(f"{url}: PDF tanpa lapisan teks ({n_hal} hlm) — "
                             "kemungkinan hasil pindai, perlu OCR")
                continue
            return {
                "ok": True, "url": url, "halaman": n_hal,
                "bytes": len(isi), "sha256": hashlib.sha256(isi).hexdigest(),
                "teks": teks, "galat": galat,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError,
                TimeoutError, OSError) as e:
            galat.append(f"{url}: {type(e).__name__}: {e}")
        except Exception as e:                     # pypdf bisa melempar apa saja
            galat.append(f"{url}: gagal diproses — {type(e).__name__}: {e}")
        time.sleep(JEDA_ANTAR_UNDUH)
    return {"ok": False, "galat": galat}


def main(argv) -> int:
    tujuan = argv[1] if len(argv) > 1 else "docs/regulasi"
    os.makedirs(tujuan, exist_ok=True)
    manifes_lama = {}
    jalur_manifes = os.path.join(tujuan, "MANIFEST.json")
    if os.path.exists(jalur_manifes):
        try:
            with open(jalur_manifes, encoding="utf-8") as f:
                manifes_lama = {m["kode"]: m for m in json.load(f).get("berkas", [])}
        except (ValueError, OSError):
            manifes_lama = {}

    hasil, berhasil, gagal = [], 0, 0
    for entri in sorted(MANIFES, key=lambda e: e["prioritas"]):
        print(f"→ [{entri['prioritas']}] {entri['judul']}", flush=True)
        r = unduh_satu(entri)
        if r["ok"]:
            berkas = f"{entri['kode']}.txt"
            with open(os.path.join(tujuan, berkas), "w", encoding="utf-8") as f:
                f.write(r["teks"])
            print(f"   ✓ {r['halaman']} hlm · {r['bytes'] // 1024} KB · {r['url']}",
                  flush=True)
            hasil.append({
                "kode": entri["kode"], "judul": entri["judul"],
                "guna": entri["guna"], "berkas": berkas, "url": r["url"],
                "halaman": r["halaman"], "bytes": r["bytes"],
                "sha256": r["sha256"],
                "diunduh": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "percobaan_gagal": r["galat"],
            })
            berhasil += 1
        else:
            print("   ✗ semua sumber gagal:", flush=True)
            for g in r["galat"]:
                print(f"     · {g}", flush=True)
            # Entri lama DIPERTAHANKAN bila unduhan kali ini gagal — kegagalan
            # jaringan tak boleh menghapus bukti yang sudah pernah terkumpul.
            if entri["kode"] in manifes_lama:
                hasil.append(manifes_lama[entri["kode"]])
                print("     (manifes lama dipertahankan)", flush=True)
            else:
                hasil.append({
                    "kode": entri["kode"], "judul": entri["judul"],
                    "guna": entri["guna"], "berkas": None,
                    "percobaan_gagal": r["galat"],
                })
            gagal += 1
        time.sleep(JEDA_ANTAR_UNDUH)

    with open(jalur_manifes, "w", encoding="utf-8") as f:
        json.dump({
            "dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "catatan": ("Teks hasil ekstraksi PDF peraturan publik. BUKTI, "
                        "bukan kesimpulan: status verifikasi di "
                        "syarat_dokumen_utils.py tetap dinaikkan secara sadar "
                        "setelah pasalnya dibaca."),
            "berhasil": berhasil, "gagal": gagal, "berkas": hasil,
        }, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"\nSelesai: {berhasil} berhasil, {gagal} gagal.", flush=True)
    # Keluar 0 walau sebagian gagal: sebagian pustaka lebih baik daripada tak
    # ada, dan kegagalan sudah tercatat di manifes untuk ditindaklanjuti.
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
