"""Perhitungan murni untuk laporan eksekutif — LOGIKA MURNI (tanpa DB/IO).

Dipisah dari routes/reports.py agar dapat diuji unit tanpa WeasyPrint/Mongo.
"""


def hitung_status_stiker(assets):
    """(terpasang, belum, pct) status pemasangan stiker atas SELURUH aset.

    'Sudah Terpasang' = terpasang; SELAIN itu (termasuk kosong/None/'Belum
    Terpasang') = belum. Persen atas total aset. MURNI (teruji unit).

    Perbaikan bug: sebelumnya `belum` dihitung sebagai (jumlah 'Ditemukan' −
    terpasang), sehingga aset yang belum diinventarisasi (justru yang belum
    berstiker) tak terhitung dan `belum` bisa 0 walau ada aset tanpa stiker.
    """
    lst = assets or []
    total = len(lst)
    terpasang = sum(1 for a in lst if (a or {}).get("stiker_status") == "Sudah Terpasang")
    belum = total - terpasang
    pct = int(terpasang / total * 100) if total else 0
    return terpasang, belum, pct
