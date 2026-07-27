"""Uji ENDPOINT SBSK berbasis ruang nyata (Fase 15) — Mongo in-process.

Dua janji yang hanya bisa dibuktikan dengan menjalankan handler-nya:
luas dilaporkan dari POLIGON (bukan dari angka `metrik.luas_m2` yang tersimpan,
yang bisa ditulis rumus versi lama), dan `peruntukan` sebuah ruangan tidak
lenyap saat form pohon lama menyimpan perubahan nama.
"""
import asyncio
import math

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.perencanaan as rp
import routes.spasial as rs
import spasial_utils as su

USER = {"username": "perencana", "role": "admin", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    for mod in (rp, rs):
        monkeypatch.setattr(mod, "db", fake)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam)
    return fake


def _kotak(lat0, lon0, m_lat, m_lon):
    mlat, mlon = su.meter_per_derajat(lat0)
    dlat, dlon = m_lat / mlat, m_lon / mlon
    return {"type": "Polygon", "coordinates": [[
        [lon0, lat0], [lon0 + dlon, lat0], [lon0 + dlon, lat0 + dlat],
        [lon0, lat0 + dlat], [lon0, lat0]]]}


async def _seed(dbx, peruntukan_305="Kepala Biro Umum"):
    await dbx.spasial_node.insert_many([
        {"id": "gedA", "nama": "Gedung A", "tipe": "GEDUNG", "status": "aktif",
         "kode_satker": "", "ancestors": [], "ancestors_nama": []},
        {"id": "lt3", "nama": "Lantai 3", "tipe": "LANTAI", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA"], "ancestors_nama": ["Gedung A"]},
        {"id": "r305", "nama": "Ruang 305", "tipe": "RUANGAN", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA", "lt3"],
         "ancestors_nama": ["Gedung A", "Lantai 3"],
         "peruntukan": peruntukan_305,
         # Sengaja SALAH & basi: bukti bahwa endpoint tak membacanya.
         "metrik": {"luas_m2": 999.0},
         "geometry": _kotak(-1.0, 116.7, 10.0, 5.0)},           # 50 m²
        {"id": "r307", "nama": "Ruang 307", "tipe": "RUANGAN", "status": "aktif",
         "kode_satker": "", "ancestors": ["gedA", "lt3"],
         "ancestors_nama": ["Gedung A", "Lantai 3"], "peruntukan": "",
         "geometry": _kotak(-1.0, 116.71, 6.0, 5.0)},           # 30 m²
    ])
    await dbx.sbsk_standar.insert_many([
        {"id": "s1", "kategori": "ruang_kerja", "peruntukan": "Kepala Biro",
         "satuan": "m²", "standar": 40},
        {"id": "s2", "kategori": "kendaraan", "peruntukan": "Pejabat eselon I",
         "satuan": "unit", "standar": 1},
    ])


async def _panggil(node_id="gedA", dalam=True, tipe="RUANGAN"):
    return await _unwrap(rp.sbsk_ruang)(node_id, dalam, tipe, USER)


class TestLuasDariPoligon:
    def test_luas_dihitung_dari_geometri_bukan_dari_metrik_tersimpan(self, dbx):
        # `metrik.luas_m2` sengaja diisi 999 — kalau endpoint membacanya,
        # laporan perencanaan memakai angka yang tak bisa dipertanggungjawabkan.
        async def jalan():
            await _seed(dbx)
            return await _panggil()
        r = _jalan(jalan())
        luas = {b["nama"]: b["luas_m2"] for b in r["items"]}
        assert math.isclose(luas["Ruang 305"], 50.0, rel_tol=0.02)
        assert math.isclose(luas["Ruang 307"], 30.0, rel_tol=0.02)
        assert 999.0 not in luas.values()

    def test_baris_terbesar_di_atas(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _panggil()
        assert _jalan(jalan())["items"][0]["nama"] == "Ruang 305"


class TestSandingStandar:
    def test_standar_ruang_kerja_tersambung_dan_selisih_terhitung(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _panggil()
        b = next(x for x in _jalan(jalan())["items"] if x["nama"] == "Ruang 305")
        assert b["standar_m2"] == 40
        assert b["status"] == "melebihi"
        assert math.isclose(b["selisih_m2"], 10.0, abs_tol=1.0)

    def test_ruangan_tanpa_peruntukan_dan_tanpa_aset_ditandai_menganggur(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _panggil()
        r = _jalan(jalan())
        b = next(x for x in r["items"] if x["nama"] == "Ruang 307")
        assert b["menganggur"] is True
        assert r["rekap"]["menganggur"] == 1
        assert math.isclose(r["rekap"]["luas_menganggur_m2"], 30.0, rel_tol=0.02)

    def test_ruangan_berisi_aset_tak_dihitung_menganggur(self, dbx):
        async def jalan():
            await _seed(dbx)
            await dbx.assets.insert_one({
                "id": "a1", "activity_id": "keg1", "asset_name": "Meja",
                "user": "Ani", "lokasi_spasial": {"node_id": "r307"}})
            return await _panggil()
        r = _jalan(jalan())
        b = next(x for x in r["items"] if x["nama"] == "Ruang 307")
        assert b["menganggur"] is False
        assert b["jumlah_aset"] == 1 and b["pemegang"] == ["Ani"]
        assert r["rekap"]["menganggur"] == 0


class TestLingkup:
    def test_dalam_false_hanya_anak_langsung(self, dbx):
        # Anak langsung Gedung A adalah LANTAI, bukan RUANGAN → kosong.
        async def jalan():
            await _seed(dbx)
            return await _panggil(dalam=False)
        assert _jalan(jalan())["rekap"]["jumlah_ruangan"] == 0

    def test_lingkup_lantai_memuat_ruangannya(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _panggil(node_id="lt3")
        assert _jalan(jalan())["rekap"]["jumlah_ruangan"] == 2

    def test_sebaran_dikelompokkan_per_lantai(self, dbx):
        async def jalan():
            await _seed(dbx)
            return await _panggil()
        s = _jalan(jalan())["sebaran"]
        assert len(s) == 1 and s[0]["induk"] == "Lantai 3"
        assert s[0]["jumlah_ruangan"] == 2

    def test_node_tak_dikenal_404(self, dbx):
        from fastapi import HTTPException

        async def jalan():
            await _seed(dbx)
            await _panggil(node_id="entah")
        with pytest.raises(HTTPException) as ex:
            _jalan(jalan())
        assert ex.value.status_code == 404


class TestPeruntukanTidakLenyap:
    def test_form_lama_tanpa_field_peruntukan_tak_menghapusnya(self, dbx):
        # Klien pra-Fase-15 mengirim PUT tanpa `peruntukan`. Tanpa penjaga,
        # sekadar mengganti nama ruangan akan menghapus acuan standarnya.
        async def jalan():
            await _seed(dbx)
            payload = rs.NodeIn(tipe="RUANGAN", nama="Ruang 305A",
                                parent_id="lt3")
            await _unwrap(rs.ubah_node)("r305", payload, USER)
            return await dbx.spasial_node.find_one({"id": "r305"}, {"_id": 0})
        assert _jalan(jalan())["peruntukan"] == "Kepala Biro Umum"

    def test_string_kosong_yang_DISENGAJA_tetap_mengosongkan(self, dbx):
        async def jalan():
            await _seed(dbx)
            payload = rs.NodeIn(tipe="RUANGAN", nama="Ruang 305",
                                parent_id="lt3", peruntukan="")
            await _unwrap(rs.ubah_node)("r305", payload, USER)
            return await dbx.spasial_node.find_one({"id": "r305"}, {"_id": 0})
        assert _jalan(jalan())["peruntukan"] == ""

    def test_peruntukan_baru_tersimpan_dan_terpangkas(self, dbx):
        async def jalan():
            await _seed(dbx)
            payload = rs.NodeIn(tipe="RUANGAN", nama="Ruang 305",
                                parent_id="lt3", peruntukan="  " + "x" * 300)
            await _unwrap(rs.ubah_node)("r305", payload, USER)
            return await dbx.spasial_node.find_one({"id": "r305"}, {"_id": 0})
        assert len(_jalan(jalan())["peruntukan"]) == 160
