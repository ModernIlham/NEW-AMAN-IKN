"""`/api/health/deep` diuji PERILAKUNYA, bukan sumbernya — penutup celah C31/C4b.

Sebelum berkas ini, seluruh penjaga endpoint itu berupa pencarian substring
atas `server.py` (`assert 'checks["indexes"]' in SRC`), dan tak satu pun uji di
repo pernah MEMANGGIL `deep_health_check()`. Dua mutasi terbukti lolos 15/15
uji: menghapus isi blok indeks (asal string-nya tersisa di komentar) dan
menukar logika `ok` — endpoint bisa berbohong sepenuhnya tanpa satu uji merah.

Itu genting justru karena dua pembaca endpoint ini bukan manusia:

  • `scripts/deploy_vps.sh` menjadikannya GERBANG DEPLOY — 503 memicu
    `pulihkan()` (`git reset --hard` ke commit sebelumnya).
  • C32 (butir berikutnya) menambah indeks unik baru — persis jenis indeks
    yang bisa gagal pada data lama. Pelaporannya harus TERBUKTI hidup sebelum
    ada yang bergantung padanya.

Uji di sini memanggil endpointnya sungguhan. `server.db` diganti tiruan agar
tiap cabang bisa dikendalikan — dan agar ping Mongo tak menunggu
server-selection timeout di lingkungan unit tanpa Mongo.
"""
import asyncio
import collections
import json
import shutil

import pytest

import server
import indexes as ix

_DU = collections.namedtuple("usage", "total used free")
GB = 1024 * 1024 * 1024


class _DbSehat:
    """Tiruan minimal: hanya dua operasi yang disentuh deep_health_check."""

    async def command(self, nama):
        assert nama == "ping"
        return {"ok": 1}

    def __getitem__(self, koleksi):
        assert koleksi == "fs.files"
        return self

    async def find_one(self, *a, **kw):
        return None            # koleksi kosong = konektivitas terbukti, sehat


class _DbMati(_DbSehat):
    async def command(self, nama):
        raise RuntimeError("mongo tak terjangkau")


def _panggil(monkeypatch, db=None, disk=None, gagal_indeks=None):
    monkeypatch.setattr(server, "db", db or _DbSehat())
    monkeypatch.setattr(shutil, "disk_usage",
                        lambda p: disk or _DU(100 * GB, 50 * GB, 50 * GB))
    ix._KEGAGALAN_INDEKS.clear()
    ix._KEGAGALAN_INDEKS.extend(gagal_indeks or [])
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        resp = loop.run_until_complete(server.deep_health_check())
    finally:
        loop.close()
        ix._KEGAGALAN_INDEKS.clear()
    return resp.status_code, json.loads(resp.body)


class TestJalurSehat:
    def test_semuanya_sehat_200(self, monkeypatch):
        status, body = _panggil(monkeypatch)
        assert status == 200
        assert body["ok"] is True
        assert body["checks"]["mongodb"]["ok"] is True
        assert body["checks"]["indexes"] == {"ok": True, "gagal": 0}
        assert body["checks"]["disk"]["ok"] is True
        assert body["checks"]["disk"]["kritis"] is False


class TestIndeks:
    def test_kegagalan_indeks_SAMPAI_ke_respons(self, monkeypatch):
        """Janji docstring test_indeks_tahan_gagal.py, kini benar-benar ditagih."""
        g = {"koleksi": "assets", "indeks": "unique_asset_id",
             "galat": "E11000 duplicate key"}
        status, body = _panggil(monkeypatch, gagal_indeks=[g])
        assert body["checks"]["indexes"]["ok"] is False
        assert body["checks"]["indexes"]["gagal"] == 1
        assert body["checks"]["indexes"]["detail"] == [g]

    def test_indeks_gagal_TIDAK_menjatuhkan_gerbang(self, monkeypatch):
        # Aplikasi masih melayani; 503 di sini melatih tim melewati gerbang.
        status, body = _panggil(monkeypatch,
                                gagal_indeks=[{"koleksi": "x", "indeks": "y",
                                               "galat": "z"}])
        assert status == 200
        assert body["ok"] is True

    def test_detail_dipotong_sepuluh(self, monkeypatch):
        banyak = [{"koleksi": "c", "indeks": f"i{n}", "galat": "g"}
                  for n in range(25)]
        _, body = _panggil(monkeypatch, gagal_indeks=banyak)
        assert body["checks"]["indexes"]["gagal"] == 25
        assert len(body["checks"]["indexes"]["detail"]) == 10


class TestDisk:
    def test_peringatan_14persen_TIDAK_503(self, monkeypatch):
        """Inti koreksi C4b: gerbang deploy membaca 503 ini sebagai perintah
        rollback. Disk 86% terpakai — aplikasi normal — tak boleh me-rollback
        setiap merge."""
        status, body = _panggil(monkeypatch,
                                disk=_DU(100 * GB, 86 * GB, 14 * GB))
        assert status == 200
        assert body["ok"] is True
        assert body["checks"]["disk"]["ok"] is False       # monitor tetap lihat
        assert body["checks"]["disk"]["kritis"] is False

    def test_di_bawah_1gb_503(self, monkeypatch):
        status, body = _panggil(monkeypatch,
                                disk=_DU(100 * GB, 100 * GB - 500 * 1024 * 1024,
                                         500 * 1024 * 1024))
        assert status == 503
        assert body["checks"]["disk"]["kritis"] is True

    def test_ambang_absolut_bukan_rasio(self, monkeypatch):
        # 3% dari 1 TB = 30 GB bebas: rasio kecil, ruang besar, tetap SEHAT.
        status, body = _panggil(monkeypatch,
                                disk=_DU(1000 * GB, 970 * GB, 30 * GB))
        assert status == 200
        assert body["checks"]["disk"]["kritis"] is False

    def test_angkanya_tetap_dilaporkan(self, monkeypatch):
        _, body = _panggil(monkeypatch, disk=_DU(100 * GB, 86 * GB, 14 * GB))
        d = body["checks"]["disk"]
        assert d["bebas_persen"] == 14.0
        assert d["bebas_mb"] == 14 * 1024
        assert d["total_mb"] == 100 * 1024


class TestMongo:
    def test_mongo_mati_tetap_503(self, monkeypatch):
        # Koreksi disk tak boleh ikut melonggarkan cek yang MEMANG harus keras.
        status, body = _panggil(monkeypatch, db=_DbMati())
        assert status == 503
        assert body["checks"]["mongodb"]["ok"] is False
