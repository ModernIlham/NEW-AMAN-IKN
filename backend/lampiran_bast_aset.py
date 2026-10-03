"""Pemilihan lampiran mengikuti BAST yang diterapkan, bukan scan historis aset."""
from fastapi import HTTPException

from portal_bast_validitas import evaluasi_bast_sah


async def sumber_lampiran_bast(database, asset):
    """None untuk unggahan manual lama; pointer terkelola gagal tertutup.

    Tidak mencari BAST berdasarkan tanggal: draf revisi tidak menggantikan
    dokumen yang sudah diterapkan. Tidak mengubah/menduplikasi arsip GridFS.
    """
    pointer = asset.get("amanah_bast") or {}
    if not pointer:
        return None
    bid = pointer.get("bast_id")
    if not bid or (asset.get("bast_terakhir") or {}).get("id") != bid:
        raise HTTPException(409, "Referensi BAST aset perlu diperiksa; arsip lama tidak dibuka sebagai dokumen terkini")
    bast = await database.bast_serah_terima.find_one({"id": bid}, {"_id": 0})
    activity = await database.inventory_activities.find_one({"id": asset.get("activity_id")})
    kode = str((activity or {}).get("kode_satker") or "").strip()
    if not bast or not kode or bast.get("kode_satker") != kode:
        raise HTTPException(409, "BAST terkini tidak tersedia dalam satker aset; periksa riwayat BAST")
    item = next((i for i in (bast.get("portal_otomasi") or {}).get("items", [])
                 if i.get("asset_id") == asset.get("id")), None)
    if (asset.get("id") not in (bast.get("asset_ids") or []) or not item
            or not pointer.get("aksi") or item.get("aksi") != pointer["aksi"]):
        raise HTTPException(409, "Aset tidak cocok dengan sumber BAST yang diterapkan")
    sah = await evaluasi_bast_sah(database, bast)
    if (not sah.get("sah") or not pointer.get("kunci_bukti")
            or pointer["kunci_bukti"] != sah.get("kunci_bukti")):
        raise HTTPException(409, "BAST terkini berubah, dicabut, atau belum sah. Periksa riwayat BAST; "
                            "arsip lama tidak digunakan sebagai pengganti")
    if sah.get("jenis") not in {"esign", "basah"}:
        raise HTTPException(409, "Jenis bukti BAST terkini perlu diperiksa")
    return bast, sah
