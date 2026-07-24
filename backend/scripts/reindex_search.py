#!/usr/bin/env python3
"""Reindex Meilisearch dari Mongo (CLI).

Bangun ulang seluruh indeks pencarian (aset, surat, persediaan) dari data
MongoDB. Dijalankan sekali setelah:
  - mengaktifkan Meilisearch pertama kali (set MEILI_URL/MEILI_MASTER_KEY),
  - impor massal Excel / restore backup / migrasi data,
  - atau kapan pun ingin menyamakan indeks dengan Mongo.

Sinkronisasi CRUD harian sudah otomatis (best-effort); skrip ini untuk
penambalan massal. Aman diulang (idempoten — dokumen ditimpa per id).

Cara pakai (dari direktori backend, venv aktif):
    python -m scripts.reindex_search
    # atau: python scripts/reindex_search.py

Membaca konfigurasi dari backend/.env (MEILI_URL, MEILI_MASTER_KEY, MONGO_URL,
DB_NAME). Bila Meilisearch nonaktif → keluar rapi tanpa melakukan apa pun.
"""
import asyncio
import os
import sys

# Pastikan direktori backend ada di sys.path saat dijalankan sebagai file lepas.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


async def _main() -> int:
    from meili_utils import meili_aktif, reindex_semua, tutup_client
    if not meili_aktif():
        print("Meilisearch NONAKTIF (MEILI_URL/MEILI_MASTER_KEY belum di-set). "
              "Tidak ada yang di-reindex; pencarian tetap memakai regex Mongo.")
        return 0
    print("Mulai reindex Meilisearch dari Mongo ...")
    try:
        hasil = await reindex_semua()
    finally:
        await tutup_client()
    for koleksi in ("assets", "surat", "persediaan"):
        info = hasil.get(koleksi) or {}
        print(f"  - {koleksi:12s}: {info.get('terindeks', 0)} dokumen")
    print(f"Total terindeks: {hasil.get('total', 0)} dokumen. Selesai.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
