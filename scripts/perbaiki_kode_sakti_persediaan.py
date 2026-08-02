#!/usr/bin/env python3
"""Perbaiki `kode_sakti` warisan pada jurnal `transaksi_persediaan` di VPS.

KENAPA. Sebelum registry 45 kode SAKTI dipasang, aplikasi memakai kode
warisan yang lima di antaranya SALAH MAKNA terhadap standar SAKTI:

    jenis                      kode lama   kode SAKTI benar
    reklasifikasi_masuk        M06         M10
    reklasifikasi_dari_aset    M07         M11
    perolehan_lainnya          M99         M06
    reklasifikasi_keluar       K07         K10
    opname                     OPN         P01

(`penghapusan_lainnya` tetap K06, hanya labelnya yang dikoreksi menjadi
"Keluar Lainnya".) Aplikasi sendiri sudah kebal — semua pembacaan menurunkan
ulang kode dari kunci `jenis` lewat `persediaan_transaksi_ref` — tetapi field
tersimpan yang salah tetap berbahaya bagi konsumen di luar aplikasi
(query Mongo langsung, ekspor lama yang tersimpan). Skrip ini merapikannya.

CARA KERJA. Untuk tiap baris jurnal yang `kode_sakti` tersimpannya berbeda
dari hasil `kode_sakti_dari_jenis(jenis)`, field diperbarui. Baris tanpa
jenis terdaftar (mis. `pindah_gudang`) tidak disentuh.

Pakai (di VPS, virtualenv backend):
    python3 scripts/perbaiki_kode_sakti_persediaan.py            # DRY-RUN
    python3 scripts/perbaiki_kode_sakti_persediaan.py --terapkan # tulis

Baca MONGO_URL & DB_NAME dari environment (fallback .env backend bila ada).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _muat_env():
    """Isi MONGO_URL/DB_NAME dari backend/.env bila belum ada di environment."""
    jalur = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
    if not os.path.exists(jalur):
        return
    for baris in open(jalur, encoding="utf-8", errors="ignore"):
        baris = baris.strip()
        if not baris or baris.startswith("#") or "=" not in baris:
            continue
        k, _, v = baris.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k in ("MONGO_URL", "DB_NAME") and k not in os.environ:
            os.environ[k] = v


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terapkan", action="store_true",
                        help="tulis perubahan (tanpa ini: dry-run)")
    args = parser.parse_args()

    _muat_env()
    from pymongo import MongoClient

    from persediaan_transaksi_ref import JENIS_KE_KODE, kode_sakti_dari_jenis

    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    nama_db = os.environ.get("DB_NAME", "aman_ikn")
    db = MongoClient(url)[nama_db]

    mode = "TERAPKAN" if args.terapkan else "DRY-RUN"
    print(f"== Perbaiki kode_sakti jurnal persediaan ({mode}) — db={nama_db} ==")

    per_perubahan = {}
    total = 0
    for jenis in JENIS_KE_KODE:
        kode_benar = kode_sakti_dari_jenis(jenis)
        cocok = {"jenis": jenis, "kode_sakti": {"$ne": kode_benar}}
        n = db.transaksi_persediaan.count_documents(cocok)
        if not n:
            continue
        contoh = db.transaksi_persediaan.find_one(
            cocok, {"_id": 0, "kode_sakti": 1})
        label = f"{jenis}: {n} baris ({(contoh or {}).get('kode_sakti')!r} → {kode_benar!r})"
        per_perubahan[jenis] = label
        total += n
        if args.terapkan:
            db.transaksi_persediaan.update_many(
                cocok, {"$set": {"kode_sakti": kode_benar}})
        print(f"  [{'~' if args.terapkan else '+'}] {label}")

    if not per_perubahan:
        print("  Tidak ada baris yang perlu diperbaiki.")
    print(f"\nTOTAL: {total} baris. "
          + ("Perubahan DITULIS." if args.terapkan
             else "Dry-run — jalankan ulang dengan --terapkan untuk menulis."))


if __name__ == "__main__":
    main()
