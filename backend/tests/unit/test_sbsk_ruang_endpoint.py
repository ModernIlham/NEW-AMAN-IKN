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
    # `scope_query_aset` membaca kegiatan lewat db milik shared_utils sendiri.
    import shared_utils as su_mod
    monkeypatch.setattr(su_mod, "db", fake)
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


class TestIsolasiSatkerAgregasi:
    """Agregasi gampang lolos dari penjagaan karena tak melewati find() —
    dan `ids` yang ter-scope satker TIDAK cukup: node ERA LAMA tanpa
    `kode_satker` terbuka untuk semua satker."""

    async def _seed_dua_satker(self, dbx):
        await dbx.inventory_activities.insert_many([
            {"id": "keg_a", "kode_satker": "SATA"},
            {"id": "keg_b", "kode_satker": "SATB"},
        ])
        await dbx.spasial_node.insert_many([
            {"id": "gedA", "nama": "Gedung A", "tipe": "GEDUNG",
             "status": "aktif", "kode_satker": "", "ancestors": [],
             "ancestors_nama": []},
            # Node ERA LAMA: kode_satker kosong → terlihat oleh SEMUA satker.
            {"id": "r305", "nama": "Ruang 305", "tipe": "RUANGAN",
             "status": "aktif", "kode_satker": "", "ancestors": ["gedA"],
             "ancestors_nama": ["Gedung A"], "peruntukan": "",
             "geometry": _kotak(-1.0, 116.7, 10.0, 5.0)},
        ])
        await dbx.assets.insert_many([
            {"id": "a1", "activity_id": "keg_a", "asset_name": "Meja SATA",
             "user": "Ani (SATA)", "lokasi_spasial": {"node_id": "r305"}},
            {"id": "b1", "activity_id": "keg_b", "asset_name": "Meja SATB",
             "user": "Budi (SATB)", "lokasi_spasial": {"node_id": "r305"}},
        ])

    def test_pemegang_dan_jumlah_aset_satker_lain_tak_ikut_terhitung(self, dbx):
        async def jalan():
            await self._seed_dua_satker(dbx)
            user_a = {"username": "u", "role": "admin", "kode_satker": "SATA"}
            return await _unwrap(rp.sbsk_ruang)("gedA", True, "RUANGAN", user_a)
        b = next(x for x in _jalan(jalan())["items"] if x["nama"] == "Ruang 305")
        assert b["jumlah_aset"] == 1
        assert b["pemegang"] == ["Ani (SATA)"]
        assert "Budi (SATB)" not in b["pemegang"]

    def test_super_admin_tetap_melihat_keduanya(self, dbx):
        # Penjaga tak boleh berubah jadi terlalu ketat: pusat memang lintas satker.
        async def jalan():
            await self._seed_dua_satker(dbx)
            return await _unwrap(rp.sbsk_ruang)("gedA", True, "RUANGAN", USER)
        b = next(x for x in _jalan(jalan())["items"] if x["nama"] == "Ruang 305")
        assert b["jumlah_aset"] == 2
        assert sorted(b["pemegang"]) == ["Ani (SATA)", "Budi (SATB)"]


class TestPlafonTakMenghapusRuangan:
    def test_plafon_membatasi_RUANGAN_bukan_ASET(self, dbx, monkeypatch):
        # Dulu `$limit` dipasang SEBELUM `$group`, sehingga ia memotong ASET:
        # ruangan yang asetnya berada di luar potongan HILANG UTUH dari peta
        # isi lalu dilaporkan MENGANGGUR — bukti palsu untuk menghentikan
        # pengadaan, persis kebalikan dari tujuan laporan ini.
        #
        # Plafon DITURUNKAN ke 2 selama uji. Tanpa itu, uji ini tak menjaga
        # apa pun: dengan plafon 800 dan 20 aset, posisi `$limit` tak
        # berpengaruh sama sekali dan implementasi yang salah pun lulus.
        # Dengan plafon 2: setelah `$group` → 2 grup (kedua ruangan utuh);
        # sebelum `$group` → hanya 2 ASET yang terbaca, dan hitungan kedua
        # ruangan runtuh dari 10 menjadi ≤1.
        monkeypatch.setattr(rp, "_MAKS_RUANGAN_SBSK", 2)

        async def jalan():
            await _seed(dbx)
            await dbx.assets.insert_many([
                {"id": f"x{i}", "activity_id": "keg1", "asset_name": f"Kursi {i}",
                 "user": f"Peg {i}",
                 "lokasi_spasial": {"node_id": "r305" if i % 2 else "r307"}}
                for i in range(20)
            ])
            return await _panggil()
        r = _jalan(jalan())
        for nama in ("Ruang 305", "Ruang 307"):
            b = next(x for x in r["items"] if x["nama"] == nama)
            assert b["jumlah_aset"] == 10, f"{nama} kehilangan hitungan asetnya"
            assert b["menganggur"] is False
        assert r["rekap"]["menganggur"] == 0
