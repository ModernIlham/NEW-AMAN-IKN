"""Backfill `kode_satker` pada jurnal `transaksi_persediaan` lama.

Jurnal baru sudah berstempel `kode_satker` (derivasi dari master persediaan
saat tulis — lihat `_insert_jurnal` di routes/persediaan.py); skrip ini
melengkapi baris LAMA supaya isolasi satker kelak bisa memakai
`scope_query_field_satker` murni tanpa pola `$in` id master yang mahal.

Pemakaian (di VPS, dari folder backend, env .env termuat):
    python ../scripts/backfill_kode_satker_transaksi_persediaan.py            # dry-run
    python ../scripts/backfill_kode_satker_transaksi_persediaan.py --terapkan
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


async def main(terapkan: bool):
    from db import db
    # Peta persediaan_id → kode_satker dari master (sumber kebenaran stempel).
    peta = {}
    async for m in db.persediaan.find({}, {"_id": 0, "id": 1, "kode_satker": 1}):
        if m.get("id"):
            peta[m["id"]] = str(m.get("kode_satker") or "")

    kosong = 0
    terisi = 0
    tanpa_master = 0
    from pymongo import UpdateOne
    ops = []
    async for t in db.transaksi_persediaan.find(
            {"$or": [{"kode_satker": {"$exists": False}},
                     {"kode_satker": ""}, {"kode_satker": None}]},
            {"_id": 1, "persediaan_id": 1}):
        kosong += 1
        ks = peta.get(t.get("persediaan_id") or "")
        if not ks:
            tanpa_master += 1
            continue
        terisi += 1
        if terapkan:
            ops.append(UpdateOne({"_id": t["_id"]},
                                 {"$set": {"kode_satker": ks}}))
        if len(ops) >= 1000:
            await db.transaksi_persediaan.bulk_write(ops, ordered=False)
            ops = []
    if terapkan and ops:
        await db.transaksi_persediaan.bulk_write(ops, ordered=False)

    print(f"Baris tanpa kode_satker : {kosong}")
    print(f"  → bisa diisi dari master: {terisi}"
          + ("" if terapkan else " (dry-run, belum ditulis)"))
    print(f"  → master tak ditemukan  : {tanpa_master} (dibiarkan; tetap "
          "aman lewat scope relasi persediaan_id)")
    if not terapkan:
        print("Jalankan ulang dengan --terapkan untuk menulis.")


if __name__ == "__main__":
    asyncio.run(main("--terapkan" in sys.argv))
