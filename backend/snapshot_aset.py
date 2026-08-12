"""Penyegaran snapshot identitas aset di register siklus (Prinsip 1 Bab 5).

Masterplan Bab 5 prinsip 1 — "satu identitas aset": register siklus merujuk
`asset_id` sebagai kunci, TAPI ikut menyimpan salinan identitas terbaca
(`asset_code` / `NUP` / `asset_name`) supaya daftar, CSV, dan dokumen resmi
tak perlu join ke master tiap kali.

Salinan itu selama ini tidak pernah disegarkan. Padahal identitas aset MEMANG
berubah di tiga jalur sah: reklasifikasi kodefikasi (SAKTI 304/107 — kode &
NUP diganti in-place), penyelesaian KDP (505/105 — pola sama), dan penyuntingan
nama/kode lewat form aset. Akibatnya register lama menampilkan kode/NUP/nama
USANG, dan Nota Dinas / BA / surat usulan yang lahir darinya ikut salah —
persis temuan "snapshot tak disegarkan bila master berubah".

Modul ini memisahkan bagian murni (registry + perakit operasi, teruji tanpa
Mongo) dari penyebarnya, dan bersifat BEST-EFFORT: snapshot adalah turunan,
bukan sumber kebenaran, jadi kegagalan menyegarkan tidak boleh menggagalkan
transaksi pembukuan yang memicunya.
"""
import logging

logger = logging.getLogger(__name__)

# Bentuk penyimpanan snapshot per koleksi register:
#   "datar" — `asset_id` + identitas di level atas dokumen
#   "aset"  — array `aset[]`, tiap baris membawa `asset_id` + identitas
REGISTER_SNAPSHOT_ASET = (
    ("pemanfaatan", "datar"),
    ("pemanfaatan_usulan", "datar"),
    ("usulan_penghapusan", "datar"),
    ("bmn_idle", "datar"),
    ("henti_guna", "datar"),
    ("tgr_register", "datar"),
    ("penilaian_koreksi", "datar"),
    ("pengamanan_kasus", "datar"),
    ("pengamanan_dokumen", "datar"),
    ("pengamanan_polis", "datar"),
    ("jadwal_pemeliharaan", "datar"),
    ("pemeliharaan", "datar"),
    ("pemusnahan", "aset"),
    ("pemusnahan_usulan", "aset"),
    ("pemindahtanganan", "aset"),
    ("psp", "aset"),
    ("penggunaan_proses", "aset"),
)

FIELD_IDENTITAS = ("asset_code", "NUP", "asset_name")


def operasi_segar(bentuk: str, asset_id: str, identitas: dict):
    """Rakit `(filter, update)` untuk `update_many` — MURNI, tanpa DB.

    Hanya field identitas yang DISEBUT yang ditulis: mengganti nama saja tak
    boleh ikut menimpa kode/NUP dengan nilai kosong. Mengembalikan
    `(None, None)` bila tak ada yang perlu ditulis.
    """
    nilai = {k: v for k, v in (identitas or {}).items()
             if k in FIELD_IDENTITAS and v is not None}
    if not nilai or not asset_id:
        return None, None
    if bentuk == "aset":
        # Positional `$` menyegarkan baris PERTAMA yang cocok — tiap modul
        # sudah menjaga satu aset muncul sekali per dokumen register (cek
        # anti-ganda saat buka tiket), jadi cukup. `arrayFilters` sengaja
        # dihindari: belum didukung mongomock, sehingga jalur ini akan lolos
        # uji tanpa pernah benar-benar dijalankan.
        return ({"aset.asset_id": asset_id},
                {"$set": {f"aset.$.{k}": v for k, v in nilai.items()}})
    return {"asset_id": asset_id}, {"$set": dict(nilai)}


async def segarkan_snapshot_aset(db, asset_id: str, **identitas) -> dict:
    """Sebar identitas baru ke seluruh register siklus — BEST-EFFORT.

    Satu koleksi gagal tidak menggagalkan koleksi lain maupun transaksi
    pemanggil (reklasifikasi/KDP/patch aset tetap sah). Mengembalikan
    `{koleksi: jumlah dokumen tersegar}` untuk log & jejak audit.
    """
    hasil = {}
    for koleksi, bentuk in REGISTER_SNAPSHOT_ASET:
        filt, upd = operasi_segar(bentuk, asset_id, identitas)
        if filt is None:
            continue
        try:
            res = await db[koleksi].update_many(filt, upd)
            n = int(getattr(res, "modified_count", 0) or 0)
            if n:
                hasil[koleksi] = n
        except Exception as e:  # noqa: BLE001 — turunan, jangan menggagalkan
            logger.warning("segarkan_snapshot_aset %s gagal: %s", koleksi, e)
    return hasil
