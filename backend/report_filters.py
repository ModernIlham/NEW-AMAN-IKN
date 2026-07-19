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


# ── Gerbang perhitungan lintas modul (W9) ───────────────────────────────────
# Data inventarisasi yang BELUM final tidak boleh mengalir ke perhitungan
# modul lain: kegiatan berstatus belum dimulai / sedang berlangsung /
# menunggu validasi tanggal = lingkup modul Inventarisasi saja. Yang ikut
# dihitung hanya kegiatan DISAHKAN atau yang tanggal selesainya sudah
# lewat (fase selesai / belum lengkap). Aset berkategori dummy (data uji)
# tidak pernah dianggap aset.

def layak_hitung_kegiatan(activity, today_iso) -> bool:
    """True bila data kegiatan boleh ikut perhitungan modul lain. MURNI."""
    a = activity or {}
    if str(a.get("status_pengesahan") or "").strip() == "disahkan":
        return True
    ts = str(a.get("tanggal_selesai") or "").strip()[:10]
    return bool(ts) and str(today_iso or "")[:10] > ts


def tanpa_dummy_filter(base=None):
    """Salinan query + syarat kategori BUKAN dummy (case-insensitive).
    Tidak menimpa syarat `category` yang sudah ada di query."""
    q = dict(base or {})
    q.setdefault("category", {"$not": {"$regex": "dummy", "$options": "i"}})
    return q
