#!/usr/bin/env python3
"""Pemeriksa rahasia — mencegah kredensial ter-commit lagi.

KENAPA INI ADA. Kunci iLovePDF, Compresto, Uploadcare, WhipDoc, Tinify,
Resend, MONGO_URL, dan **JWT_SECRET** pernah tertulis apa adanya di
`scripts/*.sh` dan `DEPLOYMENT_GUIDE_HOSTINGER.md`, lalu ter-commit ke
repositori PUBLIK dan bertahan di sana berminggu-minggu. Tak ada satu pun
mekanisme yang menghalanginya.

JWT_SECRET yang terbaca publik adalah yang terburuk: siapa pun dapat menempa
token super-admin lalu membaca dan mengubah seluruh data BMN semua satker —
melewati begitu saja seluruh pekerjaan isolasi satker di repositori ini.

Skrip ini dijalankan CI pada tiap PR. Ia sengaja memeriksa **bentuk** kunci
(prefiks penyedia), bukan daftar kunci yang sudah bocor: daftar akan basi
begitu kunci dirotasi, sedangkan bentuknya tidak.

Pakai:  python3 scripts/cek_rahasia.py
Keluar 1 bila menemukan sesuatu.
"""
import re
import subprocess
import sys

# Pola per penyedia. Ditulis longgar di bagian acaknya, ketat di prefiksnya,
# supaya kunci BARU pun tertangkap — bukan hanya yang sudah telanjur bocor.
POLA = [
    ("iLovePDF public",  r"project_public_[0-9a-f]{16,}"),
    ("iLovePDF secret",  r"secret_key_[0-9a-f]{16,}"),
    ("Tinify",           r"\bTINIFY_API_KEY\s*=\s*['\"]?[A-Za-z0-9]{20,}"),
    ("Resend",           r"\bre_[A-Za-z0-9]{8}_[A-Za-z0-9]{20,}"),
    ("Compresto",        r"\bck_[A-Za-z0-9]{24,}"),
    ("Uploadcare",       r"\bUPLOADCARE_PUBLIC_KEY\s*=\s*['\"]?[0-9a-f]{16,}"),
    ("WhipDoc",          r"\bWHIPDOC_API_KEY\s*=\s*['\"]?[A-Za-z0-9_]{16,}"),
    ("JWT_SECRET",       r"\bJWT_SECRET\s*=\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    ("MongoDB ber-sandi", r"mongodb(\+srv)?://[^:/@\s]+:[^@\s]{4,}@"),
    ("Kunci privat",     r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]

# Berkas yang memang BOLEH memuat bentuk-bentuk itu: berkas ini sendiri
# (memuat polanya), dan uji yang sengaja memakai nilai palsu.
KECUALI = (
    "scripts/cek_rahasia.py",
    "backend/tests/",
    ".git/",
)

# Nilai contoh yang jelas-jelas placeholder — bukan rahasia sungguhan.
AMAN = re.compile(
    r"(ganti|contoh|example|placeholder|<[^>]+>|xxx+|your[-_]|dummy|"
    r"rand-hex|test|uji|fake|sample)", re.I)


def berkas_terlacak():
    keluar = subprocess.run(["git", "ls-files"], capture_output=True, text=True)
    return [b for b in keluar.stdout.split("\n") if b.strip()]


def main() -> int:
    temuan = []
    for berkas in berkas_terlacak():
        if any(berkas.startswith(k) or k in berkas for k in KECUALI):
            continue
        try:
            with open(berkas, encoding="utf-8", errors="ignore") as f:
                isi = f.read()
        except (OSError, IsADirectoryError):
            continue
        for nomor, baris in enumerate(isi.split("\n"), 1):
            for nama, pola in POLA:
                m = re.search(pola, baris)
                if not m:
                    continue
                # Placeholder yang terang-terangan bukan rahasia — lewati.
                if AMAN.search(baris):
                    continue
                temuan.append((berkas, nomor, nama, m.group(0)[:12]))

    if not temuan:
        print("✓ Tidak ada kredensial yang terdeteksi di berkas ter-track.")
        return 0

    print("✗ KREDENSIAL TERDETEKSI — jangan di-commit.\n")
    for berkas, nomor, nama, cuplik in temuan:
        # Cuplikan sengaja dipotong: pesan CI bisa terbaca publik juga.
        print(f"  {berkas}:{nomor}  [{nama}]  diawali '{cuplik}…'")
    print("\nYang harus dilakukan:")
    print("  1. Cabut nilainya dari kode; baca dari environment.")
    print("  2. ROTASI kunci itu di dasbor penyedia — yang pernah ter-commit")
    print("     harus dianggap bocor, bahkan setelah dihapus dari kode,")
    print("     karena riwayat git menyimpannya.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
