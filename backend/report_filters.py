"""Filter query bersama untuk laporan BMN — SATU sumber agar tidak drift.

`active_asset_filter`: aset yang MASIH menjadi BMN, yakni belum ditandai
`dihapus=True` saat SK penghapusan terbit (proyeksi master #234, Prinsip 3
masterplan §5A). Digabung ke query laporan POSISI/NILAI (DBKP, Posisi BMN di
Neraca, rekap penyusutan) supaya aset yang sudah dihapus tidak ikut dihitung —
menghentikan *double-count* nilai BMN.

Sengaja TIDAK diterapkan ke laporan MUTASI (LBKP/CaLBMN): di sana penghapusan
harus muncul sebagai baris pengurangan agar saldo awal−mutasi=saldo akhir tetap
seimbang — itu langkah terpisah, bukan sekadar penyaringan.
"""


def active_asset_filter(base=None):
    """Kembalikan salinan `base` (dict query Mongo) + syarat aset belum dihapus.

    `{"dihapus": {"$ne": True}}` cocok untuk dokumen tanpa field `dihapus`
    (aset lama) maupun `dihapus=False`, dan hanya menyingkirkan `dihapus=True`.
    `base` tidak dimutasi (dibuat salinan) agar aman dipakai berulang.
    """
    q = dict(base or {})
    q["dihapus"] = {"$ne": True}
    return q
