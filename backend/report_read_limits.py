"""Complete bounded report reads; a partial official document is never success."""
from fastapi import HTTPException

# Rendering remains synchronous in the current architecture. This limits rows,
# not bytes/CPU: photos and expensive pages have their own existing budgets.
MAX_REPORT_ROWS = 100000


async def baca_laporan_lengkap(cursor, batas, nama="Data laporan"):
    limit = min(batas, MAX_REPORT_ROWS)
    rows = await cursor.limit(limit + 1).to_list(limit + 1)
    if len(rows) > limit:
        raise HTTPException(413, (
            f"{nama} melebihi batas {limit:,} baris. "
            "Persempit filter yang tersedia atau buat laporan per kegiatan; "
            "gunakan ekspor CSV untuk rincian data lengkap. Laporan tidak dibuat agar data tidak terpotong."
        ))
    return rows
