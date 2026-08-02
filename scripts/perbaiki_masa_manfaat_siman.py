#!/usr/bin/env python3
"""Pulihkan referensi masa manfaat yang teracuni impor SIMAN lama (VPS).

KENAPA. Sebelum diperbaiki, alur "SIMAN menang" menafsirkan kolom "Umur Aset"
ekspor SIMAN V2 sebagai masa manfaat TAHUNAN — padahal kolom itu berisi SISA
masa manfaat dalam SEMESTER (dibuktikan 175/175 baris ekspor nyata). Setiap
impor menulis nilai keliru ke `db.masa_manfaat` (mis. kelompok 30801 terbaca
"15 tahun" padahal KMK menetapkan 8 tahun), sehingga beban penyusutan seluruh
laporan menciut dan hasil AMAN menyimpang dari SIMAN.

Skrip ini MENGHAPUS entri ber-`sumber: "siman"` (hasil penafsiran keliru) —
setelah itu penyusutan kembali memakai tabel KMK 295/266/339 bawaan aplikasi.
Impor SIMAN berikutnya (dengan kode yang sudah diperbaiki) akan mengisi ulang
referensi dari derivasi nilai yang benar.

Pakai (di VPS):
    python3 scripts/perbaiki_masa_manfaat_siman.py            # DRY-RUN (aman)
    python3 scripts/perbaiki_masa_manfaat_siman.py --terapkan # hapus beneran

Entri buatan MANUAL admin (tanpa sumber "siman") tidak disentuh.
"""
import argparse
import os


def _muat_env():
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--terapkan", action="store_true",
                    help="hapus entri sumber=siman (tanpa ini: dry-run)")
    args = ap.parse_args()

    _muat_env()
    from pymongo import MongoClient
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    nama_db = os.environ.get("DB_NAME", "test_database")
    db = MongoClient(url)[nama_db]

    entri = list(db.masa_manfaat.find({"sumber": "siman"}, {"_id": 0}))
    mode = "TERAPKAN" if args.terapkan else "DRY-RUN"
    print(f"== Pulihkan referensi masa manfaat ({mode}) — db={nama_db} ==")
    if not entri:
        print("Tidak ada entri sumber=siman — referensi sudah bersih.")
        return
    for e in sorted(entri, key=lambda x: x.get("kode", "")):
        print(f"  [-] kelompok {e.get('kode')}: {e.get('tahun')} \"tahun\" "
              f"(hasil penafsiran keliru) → dihapus, kembali ke tabel KMK")
    if args.terapkan:
        res = db.masa_manfaat.delete_many({"sumber": "siman"})
        print(f"\n{res.deleted_count} entri DIHAPUS. Jalankan ulang impor "
              "SIMAN untuk mengisi referensi dari derivasi yang benar.")
    else:
        print(f"\nDry-run: {len(entri)} entri akan dihapus — jalankan ulang "
              "dengan --terapkan untuk menulis.")


if __name__ == "__main__":
    main()
