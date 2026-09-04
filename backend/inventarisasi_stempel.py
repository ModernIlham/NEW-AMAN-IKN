"""Stempel WAKTU INVENTARISASI — helper MURNI, tanpa I/O dan tanpa DB.

Sebelum ini aset tak menyimpan kapan ia diperiksa. Linimasa progres karena
itu terpaksa diturunkan dari PERIODE KEGIATAN: seluruh aset satu kegiatan
dianggap terjadi pada bulan kegiatan itu dimulai — cukup untuk gambaran
kasar, tetapi tak bisa menjawab "berapa yang selesai minggu ini".

`updated_at` BUKAN penggantinya. Ia ter-cap pada SETIAP penyuntingan, jadi
aset yang diperiksa Mei lalu fotonya diperbaiki Juli akan meloncat ke Juli.
Linimasa yang memakainya tampak presisi justru pada saat ia paling keliru.

Karena itu ada `tanggal_inventarisasi`: dicap SEKALI, pada transisi PERTAMA
dari "Belum Diinventarisasi" ke status apa pun yang bukan itu.

DUA SIFAT yang membuatnya bisa dipercaya:

1. **Di-cap server, bukan diketik.** Ia bukan bagian `ASSET_SCALAR_FIELDS`:
   tak dapat diimpor, diubah massal, atau disunting lewat form. Tanggal yang
   bisa diketik akan mengubah linimasa dari catatan menjadi pendapat.
2. **Sekali seumur hidup aset.** Menginventarisasi ulang, mengoreksi kondisi,
   atau mengubah status dari "Ditemukan" ke "Sengketa" TIDAK menggesernya —
   yang dicatat adalah kapan barangnya PERTAMA diperiksa.

**Batas yang diketahui:** stempelnya adalah saat perubahan sampai ke server.
Pekerjaan lapangan berjalan luring dan tersinkron kemudian, jadi pemeriksaan
larut malam 31 Mei yang baru terkirim 1 Juni tercatat di Juni. Untuk linimasa
BULANAN selisih ini jarang dan kecil; menambal dengan tanggal kiriman klien
akan mengembalikan persoalan nomor 1 di atas.
"""

#: Nilai status yang berarti "belum pernah diperiksa". Kosong ikut dihitung:
#: dokumen lama sempat lahir tanpa field ini sama sekali.
BELUM = "Belum Diinventarisasi"

#: Nama fieldnya. Dipakai rute, laporan, dan uji — satu sumber, supaya salah
#: ketik di salah satu tempat tak menghasilkan field kembar yang senyap.
FIELD = "tanggal_inventarisasi"


def belum_diperiksa(status) -> bool:
    """True bila status ini berarti aset belum pernah diperiksa."""
    return str(status or "").strip() in ("", BELUM)


def sudah_berstempel(dokumen) -> bool:
    """True bila aset sudah pernah dicap — cap kedua tak boleh menggesernya."""
    return bool(str((dokumen or {}).get(FIELD) or "").strip())


def stempel(existing: dict, update_data: dict, sekarang_iso: str) -> bool:
    """Sisipkan stempel ke `update_data` bila ini transisi pertama.

    Mengembalikan True bila stempel dipasang. `update_data` diubah di tempat,
    sehingga stempelnya ikut dalam SATU tulisan atomik yang sama dengan
    perubahan statusnya — bukan tulisan susulan yang bisa gagal sendiri dan
    meninggalkan aset berstatus "Ditemukan" tanpa tanggal.
    """
    if FIELD not in update_data and sudah_berstempel(existing):
        return False
    if FIELD in update_data:
        # Jalur PUT menyalin seluruh dokumen; stempel lama harus dipertahankan
        # apa adanya, bukan ditimpa nilai baru dari badan permintaan.
        if sudah_berstempel(existing):
            update_data[FIELD] = existing[FIELD]
            return False
        update_data.pop(FIELD, None)
    if "inventory_status" not in update_data:
        return False
    if belum_diperiksa(update_data.get("inventory_status")):
        return False
    if not belum_diperiksa(existing.get("inventory_status")):
        # Sudah pernah diperiksa tetapi belum bercap (data lama): dicap
        # sekarang juga. Tanpa ini aset lama tak akan pernah punya tanggal,
        # dan linimasa selamanya bergantung pada perkiraan periode kegiatan.
        pass
    update_data[FIELD] = sekarang_iso
    return True


def filter_belum_berstempel() -> dict:
    """Fragmen query: aset yang BELUM punya stempel.

    Dipakai jalur ubah-massal, yang menulis dengan satu `update_many` dan
    karenanya tak bisa memeriksa dokumen satu per satu. Field yang HILANG dan
    field yang KOSONG sama-sama berarti belum bercap — memeriksa salah satu
    saja akan melewatkan separuh data lama.
    """
    return {"$or": [{FIELD: {"$exists": False}}, {FIELD: ""}, {FIELD: None}]}
