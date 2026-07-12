"""Logika murni PENGAMANAN (Fase 3 — tahap awal: tertib administrasi data).

Dasbor "kesehatan data" per aset — pola penangkal kendala nyata satker
(pustaka §4: DBR tak mutakhir, barang tanpa label/foto/dokumen jadi
temuan BPK) — plus daftar pantau SENGKETA dari data yang sudah dicatat
modul inventarisasi (nomor perkara, pihak bersengketa).

Fungsi murni tanpa Mongo/IO agar teruji unit.
"""

# Kunci kekurangan → label Indonesia (dipakai UI & endpoint)
JENIS_KEKURANGAN = {
    "foto": "Tanpa foto",
    "register": "Tanpa kode register",
    "lokasi": "Tanpa lokasi",
    "pengguna": "Tanpa pengguna",
    "bast": "Tanpa BAST",
}


def _terisi(v) -> bool:
    return bool(str(v or "").strip())


def ada_foto(asset: dict) -> bool:
    """Aset punya foto: GridFS-first, fallback foto inline legacy."""
    return bool(asset.get("photo_gridfs_ids") or asset.get("photos"))


def kekurangan_aset(asset: dict):
    """Daftar kunci kekurangan sebuah aset (subset JENIS_KEKURANGAN)."""
    out = []
    if not ada_foto(asset):
        out.append("foto")
    if not _terisi(asset.get("kode_register")):
        out.append("register")
    if not _terisi(asset.get("location")):
        out.append("lokasi")
    if not _terisi(asset.get("user")):
        out.append("pengguna")
    if not _terisi(asset.get("bast_file_id")):
        out.append("bast")
    return out


def is_sengketa(asset: dict) -> bool:
    """Aset dalam sengketa: status Sengketa ATAU ada nomor perkara/pihak."""
    return (asset.get("inventory_status") == "Sengketa"
            or _terisi(asset.get("nomor_perkara"))
            or _terisi(asset.get("pihak_bersengketa")))


def rekap_kesehatan(assets):
    """Ringkasan → (jumlah_per_kekurangan, jumlah_lengkap, daftar_sengketa).

    jumlah_per_kekurangan: {kunci: n}; lengkap = aset tanpa kekurangan
    apa pun; daftar_sengketa: dict ringkas per aset sengketa.
    """
    per = {k: 0 for k in JENIS_KEKURANGAN}
    lengkap = 0
    sengketa = []
    for a in assets or []:
        kurang = kekurangan_aset(a)
        for k in kurang:
            per[k] += 1
        if not kurang:
            lengkap += 1
        if is_sengketa(a):
            sengketa.append({
                "id": a.get("id"),
                "asset_code": a.get("asset_code"),
                "NUP": a.get("NUP"),
                "asset_name": a.get("asset_name"),
                "nomor_perkara": str(a.get("nomor_perkara") or "").strip(),
                "pihak_bersengketa": str(a.get("pihak_bersengketa") or "").strip(),
                "keterangan": str(a.get("keterangan_sengketa") or "").strip(),
                "activity_id": a.get("activity_id"),
            })
    sengketa.sort(key=lambda x: (x["asset_name"] or "", x["asset_code"] or ""))
    return per, lengkap, sengketa
