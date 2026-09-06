"""Penempatan denah ikut ke baris daftar aset — sebagai RINGKASAN, bukan subdoc.

Permintaan pemilik: ikon lokasi pada baris/kartu aset harus sekaligus
menyatakan apakah asetnya sudah masuk denah. Layarnya tak dapat menjawab itu
kalau datanya tak pernah sampai: `lokasi_spasial` tidak termasuk
`LIST_PROJECTION`, dan baris daftar karena itu buta terhadap denah.

Yang dikirim adalah bendera + nama, bukan subdoc utuh. Baris daftar hanya perlu
menjawab "sudah masuk denah atau belum" dan "di node mana"; mengirim titik,
node_tipe, dan seluruh jalur untuk tiap baris hanya menggemukkan payload yang
justru sengaja diperkecil di proyeksi ini.

Diuji lewat pipeline agregasi Mongo SUNGGUHAN (mongomock), bukan dengan
membaca literalnya: ekspresi `$strLenCP`/`$toString` yang salah tetap terbaca
benar oleh mata, dan hanya mesinnya yang tahu.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

from routes.assets import LIST_PROJECTION


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx():
    return AsyncMongoMockClient()["uji"]


def _proyeksi(dbx, doc):
    """Jalankan `LIST_PROJECTION` atas satu dokumen → hasil proyeksinya."""
    async def skenario():
        await dbx.assets.delete_many({})
        await dbx.assets.insert_one({"id": "a1", **doc})
        hasil = await dbx.assets.aggregate(
            [{"$match": {"id": "a1"}}, {"$project": LIST_PROJECTION}]
        ).to_list(1)
        return hasil[0]
    return _jalan(skenario())


def test_aset_yang_ditempatkan_bertanda_di_denah(dbx):
    r = _proyeksi(dbx, {"lokasi_spasial": {
        "node_id": "n1", "node_nama": "R201",
        "jalur_nama": "Gedung A / Lt 2 / R201"}})
    assert r["di_denah"] is True
    assert r["denah_nama"] == "R201"
    assert r["denah_jalur"] == "Gedung A / Lt 2 / R201"


def test_aset_tanpa_penempatan_bertanda_belum(dbx):
    r = _proyeksi(dbx, {})
    assert r["di_denah"] is False
    assert r["denah_nama"] == "" and r["denah_jalur"] == ""


def test_penempatan_yang_DILEPAS_tak_lagi_terhitung(dbx):
    """Melepas penempatan menyisakan subdoc dengan node_id kosong.

    Memeriksa keberadaan subdocnya saja akan menandai aset itu masih di denah
    selamanya — dan penandanya di layar takkan pernah padam.
    """
    r = _proyeksi(dbx, {"lokasi_spasial": {
        "node_id": "", "node_nama": "", "node_tipe": "", "jalur_nama": ""}})
    assert r["di_denah"] is False


def test_subdoc_kosong_maupun_null_aman(dbx):
    assert _proyeksi(dbx, {"lokasi_spasial": {}})["di_denah"] is False
    assert _proyeksi(dbx, {"lokasi_spasial": None})["di_denah"] is False


def test_node_id_bukan_string_tetap_terbaca(dbx):
    # Dokumen era-lama bisa menyimpan id sebagai angka. `$strLenCP` menolak
    # nilai non-string dan akan meledakkan SELURUH proyeksi daftar — itulah
    # sebabnya perbandingan dengan "" yang dipakai, bukan pengukuran panjang.
    assert _proyeksi(dbx, {"lokasi_spasial": {"node_id": 12345}})["di_denah"] is True


def test_subdoc_utuh_TIDAK_ikut_ke_baris_daftar(dbx):
    # Ringkasan, bukan salinan: titik dan node_tipe tak dipakai baris daftar.
    r = _proyeksi(dbx, {"lokasi_spasial": {
        "node_id": "n1", "node_tipe": "ruangan", "titik": [116.7, -1.23]}})
    assert "lokasi_spasial" not in r


def test_proyeksi_menyebut_ketiga_bidangnya():
    # Penjaga anti-drift: bidang yang hilang dari proyeksi membuat penanda
    # denah padam di SELURUH layar tanpa satu pun galat.
    for bidang in ("di_denah", "denah_nama", "denah_jalur"):
        assert bidang in LIST_PROJECTION, bidang
