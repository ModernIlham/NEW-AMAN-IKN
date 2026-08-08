"""Dua lubang SIMETRIS pada penghapusan massal — temuan C18 & C19 tinjauan 2026-08.

Repo ini punya DUA pintu yang menghapus seluruh aset sebuah kegiatan, dan
masing-masing mengerjakan separuh pekerjaan yang benar:

  • `routes/exports.py` bulk-delete  → menulis `log_audit`, TAPI tak pernah
    mengumpulkan blob GridFS sebelum `delete_many`.
  • `routes/activities.py` hapus kegiatan → mengumpulkan blob dengan benar,
    TAPI `grep log_audit` di berkas itu tak menghasilkan apa pun.

Keduanya kehilangan sesuatu yang TIDAK BISA DIPULIHKAN:

  Blob yatim bersifat PERMANEN, bukan sekadar boros. Id blob hanya hidup di
  dokumen asetnya; begitu dokumen itu terhapus, id-nya ikut lenyap. Menghapus
  kegiatannya belakangan pun tak menolong — cascade di sana beriterasi atas
  kumpulan aset yang sudah kosong. Byte-nya tetap memakan disk VPS selamanya
  tanpa ada cara menemukannya lagi.

  Jejak audit yang absen membutakan DUA pembaca: feed delta luring di
  `routes/assets.py` (klien lapangan tak diberi tahu asetnya lenyap, antrean
  simpannya berakhir 404) dan tombstone LBKP di `routes/lbp.py` (saldo periode
  turun tanpa baris "mutasi kurang" — pemeriksa tak bisa merekonstruksinya).

Uji ini menghitung `fs.files` sebelum/sesudah dan menagih jejaknya, di KEDUA
pintu. Cascade-nya kini satu helper bersama supaya pintu ketiga tak bisa lagi
lupa; uji terakhir menguncinya di tingkat sumber.
"""
import asyncio
import inspect

import pytest
from mongomock_motor import AsyncMongoMockClient

import shared_utils as su
import routes.exports as rex
import routes.activities as ract

ADMIN = {"username": "adm", "name": "Admin Satu", "role": "admin", "kode_satker": "527010"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def lingkungan(monkeypatch):
    """DB palsu + GridFS palsu yang benar-benar bisa dihitung isinya."""
    fake = AsyncMongoMockClient()["uji"]
    # "GridFS": himpunan id yang masih hidup. Menghitungnya = menghitung fs.files.
    blob = {"foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran",
            "blob-kegiatan", "foto-tetangga"}
    jejak = []

    async def _hapus_foto(gid):
        blob.discard(gid)

    async def _hapus_dok(gid):
        blob.discard(gid)

    async def _catat(action, target, *a, **k):
        jejak.append({"action": action, "target": target, "detail": k.get("detail", "")})

    for mod in (su, rex, ract):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "delete_photo_from_gridfs"):
            monkeypatch.setattr(mod, "delete_photo_from_gridfs", _hapus_foto, raising=False)
        if hasattr(mod, "delete_document_from_gridfs"):
            monkeypatch.setattr(mod, "delete_document_from_gridfs", _hapus_dok, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _catat, raising=False)
    # Helper cascade memakai delete_* dari modulnya SENDIRI (shared_utils), dan
    # rex/ract memanggil helper itu — jadi tambalan di su yang menentukan.
    monkeypatch.setattr(rex, "cascade_hapus_blob_aset", su.cascade_hapus_blob_aset, raising=False)
    monkeypatch.setattr(ract, "cascade_hapus_blob_aset", su.cascade_hapus_blob_aset, raising=False)
    monkeypatch.setattr(rex, "invalidate_asset_cache", lambda *a, **k: None, raising=False)

    async def _lolos(*a, **k):
        return None
    monkeypatch.setattr(rex, "pastikan_akses_kegiatan_id", _lolos, raising=False)
    monkeypatch.setattr(ract, "pastikan_akses_kegiatan", _lolos, raising=False)
    import shared_utils
    monkeypatch.setattr(shared_utils, "pastikan_akses_kegiatan", _lolos, raising=False)
    return fake, blob, jejak


async def _seed(dbx):
    await dbx.inventory_activities.insert_one({
        "id": "keg-1", "kode_satker": "527010", "nomor_surat": "SR-1",
        "status_pengesahan": "draft",
        "documents": [{"gridfs_id": "blob-kegiatan"}],
    })
    await dbx.assets.insert_many([
        {"id": "a1", "activity_id": "keg-1", "asset_name": "Laptop",
         "photo_gridfs_ids": ["foto-1", "foto-2"], "bast_file_id": "dok-bast"},
        {"id": "a2", "activity_id": "keg-1", "asset_name": "Printer",
         "photo_gridfs_ids": ["foto-3"],
         "document_checklist": [{"documents": [{"gridfs_id": "dok-lampiran"}]}]},
        # Aset kegiatan LAIN — blob-nya tidak boleh ikut tersapu.
        {"id": "b1", "activity_id": "keg-2", "asset_name": "Meja",
         "photo_gridfs_ids": ["foto-tetangga"]},
    ])


class _Req:
    """Objek Request minimal — hanya dipakai oleh dekorator rate-limit."""
    class _C:
        host = "127.0.0.1"
    client = _C()
    headers = {}


def test_bulk_delete_ekspor_membebaskan_blob(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    assert {"foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran"} <= blob

    _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))

    # INI temuan C18: sebelum perbaikan, kelimanya tetap hidup selamanya.
    assert "foto-1" not in blob and "foto-2" not in blob and "foto-3" not in blob
    assert "dok-bast" not in blob and "dok-lampiran" not in blob


def test_bulk_delete_ekspor_tak_menyentuh_kegiatan_lain(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    _jalan(rex.bulk_delete_assets.__wrapped__(_Req(), "keg-1", _admin=ADMIN))
    # Cascade harus BERPAGAR activity_id — bukan sapu bersih.
    assert "foto-tetangga" in blob
    assert _jalan(dbx.assets.count_documents({"activity_id": "keg-2"})) == 1


def test_hapus_kegiatan_membebaskan_blob(lingkungan):
    dbx, blob, _ = lingkungan
    _jalan(_seed(dbx))
    _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))
    for gid in ("foto-1", "foto-2", "foto-3", "dok-bast", "dok-lampiran", "blob-kegiatan"):
        assert gid not in blob, gid
    assert "foto-tetangga" in blob


def test_hapus_kegiatan_menulis_jejak_audit(lingkungan):
    dbx, _, jejak = lingkungan
    _jalan(_seed(dbx))
    _jalan(ract.delete_inventory_activity("keg-1", _admin=ADMIN))

    # C19: handler ini dulu tak menulis satu baris pun. Feed delta luring dan
    # tombstone LBKP keduanya membacanya lewat action "bulk_delete" + target.
    baris = [j for j in jejak if j["action"] == "bulk_delete" and j["target"] == "keg-1"]
    assert len(baris) == 1, f"jejak yang tertulis: {jejak}"
    # Jumlah aset dihitung SEBELUM delete_many — kalau sesudah, isinya 0 dan
    # jejaknya tak berguna untuk merekonstruksi apa pun.
    assert "2 aset" in baris[0]["detail"]


def test_audit_ditulis_SEBELUM_delete_many():
    """Urutannya bagian dari perbaikan, bukan kebetulan.

    Kalau `log_audit` dipindah ke bawah `delete_many`, proses yang mati di
    tengah penghapusan meninggalkan aset yang sudah lenyap TANPA jejak —
    persis keadaan yang temuan C19 keluhkan. Dan `count_documents` yang
    dipanggil setelahnya akan mengembalikan 0, membuat detail jejaknya
    berbohong soal berapa aset yang hilang.
    """
    src = inspect.getsource(ract.delete_inventory_activity)
    i_audit = src.index("log_audit(")
    i_hapus = src.index("assets.delete_many(")
    i_hitung = src.index("count_documents(")
    assert i_hitung < i_audit < i_hapus, "urutan hitung → audit → hapus wajib"


def test_kedua_pintu_memakai_helper_yang_SAMA():
    """Penjaga struktural: sumber kebenaran cascade cuma boleh satu.

    Sebelum ini blok pengumpul blob ditulis inline di activities.py saja, dan
    exports.py melewatkannya. Menyalin blok itu ke pintu ketiga adalah cara
    paling mudah bug ini kembali — jadi keduanya wajib memanggil helper.
    """
    for mod in (rex, ract):
        src = inspect.getsource(mod)
        assert "cascade_hapus_blob_aset(activity_id)" in src, mod.__name__
        # Tidak boleh ada lagi pengumpul inline (penanda: nama variabel lamanya).
        assert "photo_gids.extend" not in src, mod.__name__
