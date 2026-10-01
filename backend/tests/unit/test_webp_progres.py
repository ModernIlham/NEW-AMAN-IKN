"""Progres konversi dengan Mongo/GridFS tiruan dan Tinify palsu saja.

Semua byte foto dibuat di memori. Tidak menghubungi Mongo, penyedia kompresi,
atau memakai foto pengguna; OCC dan query kandidat tetap benar-benar diuji.
"""
import asyncio
import copy
import io
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import mongomock
import pytest
from bson import ObjectId
from PIL import Image

import webp_converter as wc
from tinify_service import HasilTinify


class _Kursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def sort(self, *args):
        self.cursor.sort(*args)
        return self

    def limit(self, count):
        self.cursor.limit(count)
        return self

    async def to_list(self, length):
        return list(self.cursor)[:length]


class _Koleksi:
    def __init__(self, koleksi):
        self.koleksi = koleksi

    def find(self, *args, **kwargs):
        return _Kursor(self.koleksi.find(*args, **kwargs))

    def aggregate(self, *args, **kwargs):
        return _Kursor(self.koleksi.aggregate(*args, **kwargs))

    async def find_one(self, *args, **kwargs):
        return self.koleksi.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        # Mongomock belum mendukung positional-$ pada array skalar (Mongo
        # mendukungnya). Terjemahkan hanya posisi yang telah lolos query asli;
        # version/id/referensi tetap diuji, tidak mengganti swap dengan stub.
        if len(args) >= 2 and "photo_gridfs_ids.$" in args[1].get("$set", {}):
            query, update = args[:2]
            doc = self.koleksi.find_one(query)
            if doc:
                posisi = doc["photo_gridfs_ids"].index(query["photo_gridfs_ids"])
                update = copy.deepcopy(update)
                update["$set"][f"photo_gridfs_ids.{posisi}"] = update["$set"].pop("photo_gridfs_ids.$")
                return self.koleksi.update_one(query, update, **kwargs)
        return self.koleksi.update_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self.koleksi.find_one_and_update(*args, **kwargs)


class _DB:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, nama):
        return _Koleksi(self.data[nama])

    def __getattr__(self, nama):
        return self[nama]


def _gambar(format, color=(32, 64, 96), size=(128, 96)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format=format)
    return buf.getvalue()


@pytest.fixture
def dunia(monkeypatch):
    mem = mongomock.MongoClient(tz_aware=True).uji
    lama, baru = str(ObjectId()), str(ObjectId())
    sumber_bita, hasil_bita = _gambar("JPEG"), _gambar("WEBP")
    mem["fs.files"].insert_one({
        "_id": ObjectId(lama), "filename": "photo_lama.jpg",
        "metadata": {"content_type": "image/jpeg", "kompresi": {"asli": 9000, "v": 1}},
    })
    mem.assets.insert_one({"id": "A", "version": 1, "photo_gridfs_ids": [lama],
                           "updated_at": "sebelum"})
    bita = {lama: sumber_bita}

    async def simpan(data, metadata):
        bita[baru] = data
        meta = {**copy.deepcopy(metadata), "content_type": "image/webp", "size": len(data), "webp": True}
        mem["fs.files"].insert_one({"_id": ObjectId(baru), "filename": "photo_baru.webp", "metadata": meta})
        return baru

    async def hapus(ident):
        bita.pop(ident, None)
        mem["fs.files"].delete_one({"_id": ObjectId(ident)})

    baca = AsyncMock(side_effect=lambda ident: bita.get(ident))
    simpan_mock, hapus_mock = AsyncMock(side_effect=simpan), AsyncMock(side_effect=hapus)
    api = AsyncMock(return_value=HasilTinify(data=hasil_bita, status="ok"))
    lease = AsyncMock(return_value=True)
    monkeypatch.setattr(wc, "db", _DB(mem))
    monkeypatch.setattr(wc, "get_photo_from_gridfs", baca)
    monkeypatch.setattr(wc, "_simpan_webp", simpan_mock)
    monkeypatch.setattr(wc, "delete_photo_from_gridfs", hapus_mock)
    monkeypatch.setattr(wc, "konversi_ke_webp", api)
    monkeypatch.setattr(wc, "_lease_masih_milik", lease)
    return SimpleNamespace(mem=mem, lama=lama, baru=baru, bita=bita, hasil=hasil_bita,
                           api=api, baca=baca, simpan=simpan_mock, hapus=hapus_mock, lease=lease,
                           sumber=next(s for s in wc.SUMBER if s["nama"] == "aset"))


def _meta(d, ident=None):
    return d.mem["fs.files"].find_one({"_id": ObjectId(ident or d.lama)})["metadata"]


@pytest.mark.asyncio
async def test_sukses_menjaga_metadata_awal_dan_occ(dunia):
    d = dunia
    d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
        "metadata.webp_skip": True, "metadata.webp_gagal": 2,
        "metadata.webp_progres": {"putaran": 2, "ukuran_awal_teramati": 7000},
    }})
    assert await wc._proses_satu(d.sumber, cadangan=50) == "sukses"
    d.api.assert_awaited_once_with(_gambar("JPEG"), cadangan=50)
    aset = d.mem.assets.find_one({"id": "A"})
    assert aset["photo_gridfs_ids"] == [d.baru]
    assert aset["version"] == 2
    assert aset["updated_at"] != "sebelum"
    meta = _meta(d, d.baru)
    assert meta["kompresi"] == {"asli": 9000, "v": 1}
    assert meta["webp_progres"]["putaran"] == 3
    assert meta["webp_progres"]["ukuran_awal_teramati"] == 7000
    assert meta["webp_progres"]["ukuran_sekarang"] == len(d.hasil)
    assert "webp_skip" not in meta and "webp_gagal" not in meta
    d.hapus.assert_awaited_once_with(d.lama)


@pytest.mark.asyncio
async def test_sumber_rusak_tidak_memakai_kuota(dunia):
    d = dunia
    d.bita[d.lama] = b"bukan foto"
    assert await wc._proses_satu(d.sumber) == "sumber_rusak"
    assert _meta(d)["webp_progres"]["status"] == "perlu_periksa"
    d.api.assert_not_awaited()
    d.hapus.assert_not_awaited()


@pytest.mark.asyncio
async def test_baca_gridfs_gagal_adalah_retry_bukan_foto_rusak(dunia):
    d = dunia
    d.bita.pop(d.lama)
    assert await wc._proses_satu(d.sumber) == "konversi_gagal"
    assert _meta(d)["webp_progres"]["status"] == "menunggu"
    assert _meta(d)["webp_progres"]["retry_at"] > datetime.now(timezone.utc)
    d.api.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("hasil", [b"sampah", _gambar("WEBP", color=(240, 240, 240)),
                                  _gambar("WEBP", size=(64, 48))])
async def test_hasil_tidak_aman_menahan_foto_asli(dunia, hasil):
    d = dunia
    d.api.return_value = HasilTinify(data=hasil, status="ok")
    assert await wc._proses_satu(d.sumber) == "verifikasi_gagal"
    assert _meta(d)["webp_progres"]["alasan"] == "hasil_tidak_aman"
    d.simpan.assert_not_awaited()
    d.hapus.assert_not_awaited()
    assert d.mem.assets.find_one({"id": "A"})["photo_gridfs_ids"] == [d.lama]


@pytest.mark.asyncio
@pytest.mark.parametrize("panjang,status", [(10001, "hemat_tipis"), (10000, "hemat_tipis"),
                                           (9901, "hemat_tipis"), (9900, "sukses"), (9899, "sukses")])
async def test_batas_satu_persen_tepat_dan_plateau_tidak_diulang(dunia, monkeypatch, panjang, status):
    # Dekode/kualitas sudah diuji sungguhan di atas. Hanya panjang bita dibuat
    # deterministik untuk menguji tepat <1%, =1%, dan >1% tanpa codec rounding.
    d = dunia
    d.bita[d.lama] = b"a" * 10000
    d.api.return_value = HasilTinify(data=b"b" * panjang, status="ok")
    monkeypatch.setattr(wc, "sumber_foto_valid", lambda data: True)
    monkeypatch.setattr(wc, "verifikasi_foto", lambda a, b: True)
    assert await wc._proses_satu(d.sumber) == status
    if status == "hemat_tipis":
        assert _meta(d)["webp_progres"]["status"] == "plateau"
        assert await wc._proses_satu(d.sumber) is None
        assert d.api.await_count == 1
        d.simpan.assert_not_awaited()
        d.hapus.assert_not_awaited()


def _legacy_webp(d, nama="aset_ulang"):
    d.bita[d.lama] = d.hasil
    meta = {"content_type": "image/webp", "webp_ulang_selesai": True}
    if nama != "aset_ulang":
        jenis = "foto_pegawai" if nama == "pegawai_ulang" else "foto_pegawai_asli"
        field = "foto_file_id" if nama == "pegawai_ulang" else "foto_asli_file_id"
        d.mem.assets.delete_many({})
        d.mem.pegawai.insert_one({"id": "P", field: d.lama})
        meta.update(jenis=jenis, pegawai_id="P")
    d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
        "metadata": meta, "filename": "photo_lama.webp",
    }})
    d.sumber = next(s for s in wc.SUMBER if s["nama"] == nama)


@pytest.mark.asyncio
@pytest.mark.parametrize("nama", ["aset_ulang", "pegawai_ulang", "pegawai_asli_ulang"])
async def test_plateau_legacy_diverifikasi_sekali_lalu_terminal_v2(dunia, nama):
    d = dunia
    _legacy_webp(d, nama)
    # Flag warisan mungkin dibuat saat env ambangnya 3%; tanpa bukti ambang
    # lama, satu pemeriksaan diperlukan, bukan langsung dianggap selesai 1%.
    assert await wc._proses_satu(d.sumber) == "hemat_tipis"
    progres = _meta(d)["webp_progres"]
    assert progres["v"] == wc.VERSI_PROGRES
    assert progres["status"] == "plateau"
    assert progres["ambang_persen"] == 1.0
    assert progres["hemat_terakhir"] < 1.0
    for _ in range(3):
        assert await wc._proses_satu(d.sumber) is None
    d.api.assert_awaited_once()
    d.simpan.assert_not_awaited()
    d.hapus.assert_not_awaited()


@pytest.mark.asyncio
async def test_plateau_legacy_galat_sementara_retry_bukan_terminal(dunia):
    d = dunia
    _legacy_webp(d)
    d.api.return_value = HasilTinify(status="sementara")
    assert await wc._proses_satu(d.sumber) == "sementara"
    assert _meta(d)["webp_progres"]["status"] == "menunggu"
    assert await wc._proses_satu(d.sumber) is None
    d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
        "metadata.webp_progres.retry_at": datetime.now(timezone.utc) - timedelta(seconds=1),
    }})
    d.api.return_value = HasilTinify(data=d.hasil, status="ok")
    assert await wc._proses_satu(d.sumber) == "hemat_tipis"
    assert _meta(d)["webp_progres"]["status"] == "plateau"
    assert await wc._proses_satu(d.sumber) is None
    assert d.api.await_count == 2


@pytest.mark.asyncio
async def test_foto_belum_diperiksa_dahulu_sebelum_validasi_plateau_legacy(dunia):
    d = dunia
    _legacy_webp(d)
    baru_belum_dicoba = str(ObjectId())
    d.mem["fs.files"].insert_one({"_id": ObjectId(baru_belum_dicoba), "filename": "photo_belum.webp",
                                "metadata": {"content_type": "image/webp"}})
    d.mem.assets.insert_one({"id": "B", "version": 1, "photo_gridfs_ids": [baru_belum_dicoba]})
    d.bita[baru_belum_dicoba] = d.hasil
    # Legacy dibuat lebih dahulu (ObjectId lebih kecil); sortir baru harus
    # tetap memberi jatah pertama ke foto tanpa penanda legacy.
    assert await wc._proses_satu(d.sumber) == "hemat_tipis"
    assert _meta(d, baru_belum_dicoba)["webp_progres"]["status"] == "plateau"
    assert "webp_progres" not in _meta(d)
    assert await wc._proses_satu(d.sumber) == "hemat_tipis"
    assert _meta(d)["webp_progres"]["status"] == "plateau"
    assert await wc._proses_satu(d.sumber) is None
    assert d.api.await_count == 2


@pytest.mark.asyncio
async def test_plateau_legacy_masih_hemat_dua_persen_dilanjutkan(dunia, monkeypatch):
    d = dunia
    _legacy_webp(d)
    d.bita[d.lama] = b"a" * 10000
    d.api.return_value = HasilTinify(data=b"b" * 9800, status="ok")
    monkeypatch.setattr(wc, "sumber_foto_valid", lambda data: True)
    monkeypatch.setattr(wc, "verifikasi_foto", lambda a, b: True)
    assert await wc._proses_satu(d.sumber) == "sukses"
    meta = _meta(d, d.baru)
    assert "webp_ulang_selesai" not in meta
    assert meta["webp_progres"]["status"] == "menunggu"
    assert meta["webp_progres"]["hemat_terakhir"] == 2.0
    assert meta["webp_progres"]["ambang_persen"] == 1.0
    assert await wc._proses_satu(d.sumber) == "hemat_tipis"
    assert _meta(d, d.baru)["webp_progres"]["status"] == "plateau"
    assert await wc._proses_satu(d.sumber) is None
    assert d.api.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["sementara", "kuota", "tidak_tersedia"])
async def test_lebih_dari_tiga_galat_sementara_tetap_bisa_retry(dunia, status):
    d = dunia
    d.api.return_value = HasilTinify(status=status)
    for n in range(1, 5):
        assert await wc._proses_satu(d.sumber) == status
        meta = _meta(d)
        assert meta["webp_progres"]["status"] == "menunggu"
        assert meta["webp_progres"]["percobaan_gagal"] == n
        assert not meta.get("webp_skip")
        assert await wc._proses_satu(d.sumber) is None  # tunggu retry_at
        d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
            "metadata.webp_progres.retry_at": datetime.now(timezone.utc) - timedelta(seconds=1),
        }})
    assert d.api.await_count == 4
    d.api.return_value = HasilTinify(data=d.hasil, status="ok")
    assert await wc._proses_satu(d.sumber) == "sukses"


@pytest.mark.asyncio
async def test_input_ditolak_ditandai_perlu_periksa_bukan_plateau(dunia):
    dunia.api.return_value = HasilTinify(status="input_rusak")
    assert await wc._proses_satu(dunia.sumber) == "input_rusak"
    assert _meta(dunia)["webp_progres"]["status"] == "perlu_periksa"
    assert await wc._proses_satu(dunia.sumber) is None
    dunia.hapus.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_tanggal_hasil_restore_string_diperiksa_kembali(dunia):
    d = dunia
    # Backup menggunakan default=str: BSON Date kembali sebagai ISO string.
    # Jangan membiarkannya terkunci selamanya oleh perbandingan tipe Mongo.
    future = datetime.now(timezone.utc) + timedelta(days=7)
    d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
        "metadata.webp_progres": {"status": "menunggu", "retry_at": future.isoformat()},
    }})
    assert await wc._proses_satu(d.sumber) == "sukses"
    d.api.assert_awaited_once()


@pytest.mark.asyncio
async def test_retry_tanggal_bson_masa_depan_tetap_ditunda(dunia):
    d = dunia
    d.mem["fs.files"].update_one({"_id": ObjectId(d.lama)}, {"$set": {
        "metadata.webp_progres": {"status": "menunggu", "retry_at": datetime.now(timezone.utc) + timedelta(days=7)},
    }})
    assert await wc._proses_satu(d.sumber) is None
    d.api.assert_not_awaited()
    d.simpan.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("format", ["PNG", "WEBP"])
async def test_animasi_ditolak_sebelum_api(dunia, format):
    d = dunia
    a, b = Image.new("RGB", (20, 20), "red"), Image.new("RGB", (20, 20), "blue")
    buf = io.BytesIO()
    a.save(buf, format=format, save_all=True, append_images=[b], duration=100, loop=0)
    d.bita[d.lama] = buf.getvalue()
    assert await wc._proses_satu(d.sumber) == "sumber_rusak"
    d.api.assert_not_awaited()
    d.hapus.assert_not_awaited()


@pytest.mark.asyncio
async def test_lease_hilang_sebelum_api_tidak_membakar_kuota(dunia):
    dunia.lease.return_value = False
    assert await wc._proses_satu(dunia.sumber) == "berubah"
    dunia.api.assert_not_awaited()
    dunia.simpan.assert_not_awaited()


@pytest.mark.asyncio
async def test_lease_hilang_sebelum_swap_buang_baru_bukan_asli(dunia):
    d = dunia
    d.lease.side_effect = [True, False]
    assert await wc._proses_satu(d.sumber) == "berubah"
    d.hapus.assert_awaited_once_with(d.baru)
    assert d.mem.assets.find_one({"id": "A"})["photo_gridfs_ids"] == [d.lama]
    assert d.lama in d.bita


@pytest.mark.asyncio
async def test_edit_pengguna_selama_api_menang_occ(dunia):
    d = dunia

    async def api(*args, **kwargs):
        d.mem.assets.update_one({"id": "A"}, {"$inc": {"version": 1}, "$set": {"asset_name": "Edit pengguna"}})
        return HasilTinify(data=d.hasil, status="ok")

    d.api.side_effect = api
    assert await wc._proses_satu(d.sumber) == "berubah"
    aset = d.mem.assets.find_one({"id": "A"})
    assert aset["photo_gridfs_ids"] == [d.lama]
    assert aset["asset_name"] == "Edit pengguna"
    assert aset["version"] == 2
    d.hapus.assert_awaited_once_with(d.baru)


@pytest.mark.asyncio
async def test_readback_beda_walau_gambar_valid_tidak_boleh_swap(dunia):
    d = dunia
    d.baca.side_effect = lambda ident: d.bita.get(ident) if ident == d.lama else _gambar("WEBP", color=(33, 65, 97))
    assert await wc._proses_satu(d.sumber) == "simpan_gagal"
    d.hapus.assert_awaited_once_with(d.baru)
    assert d.mem.assets.find_one({"id": "A"})["photo_gridfs_ids"] == [d.lama]


@pytest.mark.asyncio
@pytest.mark.parametrize("pemilik_lain", ["aset", "pegawai", "pegawai_asli"])
async def test_blob_berbagi_referensi_tidak_dihapus(dunia, pemilik_lain):
    d = dunia
    if pemilik_lain == "aset":
        d.mem.assets.insert_one({"id": "B", "version": 1, "photo_gridfs_ids": [d.lama]})
    else:
        field = "foto_file_id" if pemilik_lain == "pegawai" else "foto_asli_file_id"
        d.mem.pegawai.insert_one({"id": "P", field: d.lama})
    assert await wc._proses_satu(d.sumber) == "sukses"
    d.hapus.assert_not_awaited()
    assert d.lama in d.bita


@pytest.mark.asyncio
async def test_tanpa_pemilik_tidak_memakai_kuota(dunia):
    dunia.mem.assets.delete_many({})
    assert await wc._proses_satu(dunia.sumber) == "yatim"
    dunia.api.assert_not_awaited()
    dunia.hapus.assert_not_awaited()


@pytest.mark.asyncio
async def test_round_robin_memberi_giliran_semua_sumber_termasuk_inline(monkeypatch):
    giliran = []

    async def gridfs(sumber, cadangan=0):
        giliran.append(sumber["nama"])
        assert cadangan == 50
        return "sukses"

    async def inline(cadangan=0, masih_berwenang=None):
        giliran.append("inline")
        assert cadangan == 50 and masih_berwenang is wc._lease_masih_milik
        return "sukses"

    monkeypatch.setattr(wc, "_sumber_berikut", 0)
    monkeypatch.setattr(wc, "_proses_satu", gridfs)
    monkeypatch.setitem(sys.modules, "foto_inline_optimizer", SimpleNamespace(proses_satu=inline))
    for _ in range(len(wc.SUMBER) + 2):
        assert await wc.konversi_satu(cadangan=50) == "sukses"
    assert giliran == [s["nama"] for s in wc.SUMBER] + ["inline", wc.SUMBER[0]["nama"]]


@pytest.mark.asyncio
async def test_round_robin_kosong_tetap_memeriksa_seluruh_sumber(monkeypatch):
    gridfs, inline = AsyncMock(return_value=None), AsyncMock(return_value=None)
    monkeypatch.setattr(wc, "_sumber_berikut", 3)
    monkeypatch.setattr(wc, "_proses_satu", gridfs)
    monkeypatch.setitem(sys.modules, "foto_inline_optimizer", SimpleNamespace(proses_satu=inline))
    assert await wc.konversi_satu() == "kosong"
    assert gridfs.await_count == len(wc.SUMBER)
    inline.assert_awaited_once()


@pytest.mark.asyncio
async def test_heartbeat_lease_hilang_membatalkan_pekerjaan(monkeypatch):
    dibatalkan = asyncio.Event()

    async def bekerja(**kwargs):
        try:
            await asyncio.Future()
        finally:
            dibatalkan.set()

    monkeypatch.setattr(wc, "LEASE_TTL", 0.04)
    monkeypatch.setattr(wc, "konversi_satu", bekerja)
    renew = AsyncMock(return_value=False)
    monkeypatch.setattr(wc, "_perpanjang_lease", renew)
    with pytest.raises(RuntimeError, match="lease_kompresi_hilang"):
        await asyncio.wait_for(wc._kerja_dengan_lease(50), timeout=1)
    assert dibatalkan.is_set()
    renew.assert_awaited_once()


@pytest.mark.asyncio
async def test_pekerjaan_selesai_membatalkan_heartbeat(monkeypatch):
    monkeypatch.setattr(wc, "konversi_satu", AsyncMock(return_value="sukses"))
    renew = AsyncMock(return_value=True)
    monkeypatch.setattr(wc, "_perpanjang_lease", renew)
    sebelum = asyncio.all_tasks()
    assert await wc._kerja_dengan_lease(50) == "sukses"
    assert asyncio.all_tasks() == sebelum
    renew.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_membatalkan_pekerjaan_dan_heartbeat(monkeypatch):
    mulai, dibatalkan = asyncio.Event(), asyncio.Event()

    async def bekerja(**kwargs):
        mulai.set()
        try:
            await asyncio.Future()
        finally:
            dibatalkan.set()

    monkeypatch.setattr(wc, "konversi_satu", bekerja)
    monkeypatch.setattr(wc, "_perpanjang_lease", AsyncMock(return_value=True))
    sebelum = asyncio.all_tasks()
    task = asyncio.create_task(wc._kerja_dengan_lease(50))
    await mulai.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert dibatalkan.is_set()
    assert asyncio.all_tasks() == sebelum


@pytest.mark.asyncio
async def test_ringkasan_hanya_observasi_bukan_klaim_semua_selesai(dunia):
    d = dunia
    d.mem["fs.files"].delete_many({})
    for status in (None, None, "plateau", "menunggu", "perlu_periksa", "yatim", "plateau_lama"):
        meta = {"content_type": "image/webp"}
        if status == "plateau_lama":
            meta["webp_ulang_selesai"] = True
        elif status:
            meta["webp_progres"] = {"status": status}
        d.mem["fs.files"].insert_one({"_id": ObjectId(), "filename": "photo_uji.webp", "length": 100,
                                    "metadata": meta})
    # Gambar dokumen dan ikon/logo di luar registry bukan kandidat foto umum.
    for extra in ({"kind": "bast"}, {"jenis": "logo"}):
        d.mem["fs.files"].insert_one({"_id": ObjectId(), "filename": "photo_bukan_aset.webp", "length": 9000,
                                    "metadata": {"content_type": "image/webp", **extra}})
    for n, status in enumerate(("plateau", "plateau", "retry", "manual_review")):
        d.mem.foto_kompresi_status.insert_one({"_id": f"hash-{n}", "status": status})
    waktu = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    d.mem.app_runtime.insert_one({"_id": "foto_inline_cursor_v1", "updated_at": waktu})
    sebelum = list(d.mem["fs.files"].find())

    result = await wc.ringkasan_progres()
    groups = {g["status"]: (g["jumlah_blob"], g["bita"]) for g in result["gridfs"]}
    assert groups == {
        "belum_diperiksa": (2, 200), "plateau": (1, 100), "menunggu": (1, 100),
        "perlu_periksa": (1, 100), "yatim": (1, 100), "menunggu_verifikasi_ulang": (1, 100),
    }
    assert {g["status"]: g["jumlah_hash"] for g in result["inline_teramati"]} == {
        "plateau": 2, "retry": 1, "manual_review": 1,
    }
    assert result["ambang_persen"] == 1.0
    assert result["semua_selesai"] is None
    assert result["sapuan_inline_terakhir"] == waktu
    assert "bukan bukti" in result["catatan"]
    assert all("_id" not in g for g in result["gridfs"] + result["inline_teramati"])
    # pop(_id) hanya memformat keluaran agregasi; tidak memutasi koleksi.
    assert await wc.ringkasan_progres() == result
    assert list(d.mem["fs.files"].find()) == sebelum
    d.api.assert_not_awaited()


@pytest.mark.asyncio
async def test_ringkasan_kosong_bukan_berarti_semua_foto_tuntas(dunia):
    dunia.mem["fs.files"].delete_many({})
    result = await wc.ringkasan_progres()
    assert result["gridfs"] == []
    assert result["inline_teramati"] == []
    assert result["semua_selesai"] is None
    assert result["sapuan_inline_terakhir"] is None
