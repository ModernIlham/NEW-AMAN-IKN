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


#: Setiap (koleksi, kolom, label) yang menyimpan `<kolom>_instansi_id`.
#: Instansi yang masih dirujuk di sini tidak boleh dihapus dari direktori.
RUJUKAN = (
    ("pemanfaatan", "mitra", "Pemanfaatan"),
    ("pemanfaatan_usulan", "mitra", "Usulan pemanfaatan"),
    ("penggunaan_proses", "pihak_asal", "Proses penggunaan"),
    ("penggunaan_proses", "pihak_tujuan", "Proses penggunaan"),
    ("pemeliharaan", "pelaksana", "Pemeliharaan"),
    ("pengadaan", "pihak", "Pengadaan"),
    ("pemindahtanganan", "pihak", "Pemindahtanganan"),
)


async def modul_perujuk(db, instansi_id: str) -> list:
    """Label modul (unik, berurutan) yang masih merujuk instansi ini —
    lintas satker, TANPA merinci satker mana."""
    out = []
    for koleksi, kolom, label in RUJUKAN:
        if label in out:
            continue
        if await db[koleksi].find_one({f"{kolom}_instansi_id": instansi_id}, {"_id": 1}):
            out.append(label)
    return out


async def tautkan(db, data: dict, kolom: str, sebutan: str, lama: dict | None = None) -> tuple:
    """(field tautan, dokumen instansi atau None) untuk `kolom`.

    `lama` = dokumen yang sedang diubah: tautan yang TIDAK berubah dipertahankan
    apa adanya tanpa ditanyakan ulang ke direktori — mengubah keterangan
    tidak boleh gagal hanya karena instansinya sudah tak ada di direktori."""
    f_id, f_kel, f_tat, f_jen = field_tautan(kolom)
    iid = str((data or {}).get(f_id) or "").strip()
    if not iid:
        return {k: "" for k in field_tautan(kolom)}, None
    if lama is not None and iid == str(lama.get(f_id) or ""):
        return salin_tautan(lama, kolom), None
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
