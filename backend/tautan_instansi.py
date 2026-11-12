"""Tautan kolom teks pihak ke direktori instansi luar (PGW-11).

Pola aditif yang dipakai modul berpihak-luar: kolom teks (`mitra`,
`pihak_asal`, ...) TETAP disimpan apa adanya sebagai snapshot; di sampingnya
field opsional `<kolom>_instansi_id` beserta salinan kelompok/tataran/jenis
dari direktori saat disimpan (agar ikon & pemeriksaan kebijakan tidak
bergantung pada direktori yang bisa berubah). Tanpa tautan → semua field
kosong (perilaku lama). Id yang tak ada di direktori → 400: tautan patah
lebih buruk daripada teks bebas.
"""
from fastapi import HTTPException


def field_tautan(kolom: str) -> tuple:
    return (f"{kolom}_instansi_id", f"{kolom}_kelompok", f"{kolom}_tataran",
            f"{kolom}_jenis_instansi")


def salin_tautan(sumber: dict, kolom: str) -> dict:
    """Field tautan `kolom` dari dokumen lain (mis. pewarisan induk)."""
    return {k: str((sumber or {}).get(k) or "") for k in field_tautan(kolom)}


async def tautkan(db, data: dict, kolom: str, sebutan: str) -> tuple:
    """(field tautan, dokumen instansi atau None) untuk `kolom`."""
    f_id, f_kel, f_tat, f_jen = field_tautan(kolom)
    iid = str((data or {}).get(f_id) or "").strip()
    if not iid:
        return {k: "" for k in field_tautan(kolom)}, None
    ins = await db.instansi_luar.find_one(
        {"id": iid}, {"_id": 0, "id": 1, "nama": 1, "kelompok": 1, "tataran": 1,
                      "jenis": 1, "aktif": 1})
    if not ins:
        raise HTTPException(status_code=400, detail=(
            f"{sebutan} yang ditautkan tidak ditemukan di direktori instansi luar"))
    return ({f_id: ins["id"], f_kel: str(ins.get("kelompok") or ""),
             f_tat: str(ins.get("tataran") or ""),
             f_jen: str(ins.get("jenis") or "")}, ins)


def peringatan_nonaktif(ins, sebutan: str) -> list:
    if ins and ins.get("aktif") is False:
        return [f"Instansi {sebutan.lower()} ini berstatus nonaktif di direktori"]
    return []
