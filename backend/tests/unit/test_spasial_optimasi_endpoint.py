"""Uji ENDPOINT optimalisasi geometri — Mongo in-process.

Satu janji menaungi seluruh berkas ini: **geometri ASLI tidak pernah berubah.**
Poligon denah adalah dasar perhitungan luas ruangan SBSK, dasar deteksi lokasi
otomatis, dan bahan ekspor ke QGIS. Optimasi yang bocor ke `geometry` berarti
presisi survei terbuang tanpa bisa dipulihkan — dan tanpa satu pun galat.
"""
import asyncio
import math

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.spasial as rs
import spasial_optimize as so

USER = {"username": "pemetaan", "role": "admin", "kode_satker": ""}


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
    import shared_utils as su
    for mod in (rs, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


def _lingkaran(lat0=-0.95, lon0=116.7, r=0.004, n=800):
    ring = [[lon0 + r * math.cos(t * 2 * math.pi / n),
             lat0 + r * math.sin(t * 2 * math.pi / n)] for t in range(n)]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


async def _seed(dbx, n_node=2):
    for i in range(n_node):
        await dbx.spasial_node.insert_one({
            "id": f"n{i}", "nama": f"Zona {i}", "tipe": "ZONA",
            "status": "aktif", "kode_satker": "", "ordinal_level": 2,
            "ancestors": [], "ancestors_nama": [], "parent_id": None,
            "geometry": _lingkaran(lon0=116.7 + i * 0.02),
            "bbox": [116.7, -0.96, 116.71, -0.94],
            "metrik": {"luas_m2": 12345.67}})


# ── Optimasi massal ────────────────────────────────────────────────────────

def test_optimasi_massal_tak_menyentuh_geometri_asli(dbx):
    """INTI SELURUH FITUR: yang ditulis hanya SALINAN."""
    async def skenario():
        await _seed(dbx)
        sebelum = {r["id"]: r["geometry"]
                   async for r in dbx.spasial_node.find({})}
        hasil = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        assert hasil["diproses"] == 2
        async for r in dbx.spasial_node.find({}):
            assert r["geometry"] == sebelum[r["id"]], (
                "geometri ASLI berubah — presisi survei hilang permanen")
            assert r["geometry_opt"] is not None
            assert so._titik_geom(r["geometry_opt"]) < so._titik_geom(r["geometry"])
    _jalan(skenario())


def test_optimasi_massal_tak_mengubah_luas_tersimpan(dbx):
    """`metrik.luas_m2` adalah dasar SBSK — ia dihitung dari geometri ASLI dan
    tak boleh ikut bergeser hanya karena peta diringankan."""
    async def skenario():
        await _seed(dbx)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        async for r in dbx.spasial_node.find({}):
            assert r["metrik"]["luas_m2"] == 12345.67
    _jalan(skenario())


def test_optimasi_massal_melewati_yang_sudah_dioptimalkan(dbx):
    """Menekan tombolnya dua kali tak membakar CPU mengulang pekerjaan sama."""
    async def skenario():
        await _seed(dbx)
        pertama = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        kedua = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        assert pertama["diproses"] == 2
        assert kedua["diproses"] == 0 and kedua["kandidat"] == 0
    _jalan(skenario())


def test_optimasi_massal_paksa_ulang_menghitung_lagi(dbx):
    async def skenario():
        await _seed(dbx)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        ulang = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(paksa_ulang=True), user=USER)
        assert ulang["diproses"] == 2
    _jalan(skenario())


def test_optimasi_massal_melaporkan_hemat_yang_terukur(dbx):
    async def skenario():
        await _seed(dbx)
        h = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        assert h["titik_sebelum"] > h["titik_sesudah"] > 0
        assert h["hemat_persen"] > 50
    _jalan(skenario())


def test_optimasi_massal_terisolasi_satker(dbx):
    async def skenario():
        await _seed(dbx)
        await dbx.spasial_node.update_one({"id": "n0"},
                                          {"$set": {"kode_satker": "999999"}})
        await dbx.spasial_node.update_one({"id": "n1"},
                                          {"$set": {"kode_satker": "111111"}})
        h = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(),
            user={"username": "a", "role": "admin", "kode_satker": "111111"})
        assert h["diproses"] == 1
        asing = await dbx.spasial_node.find_one({"id": "n0"})
        assert asing.get("geometry_opt") is None, "node satker lain ikut ditulis"
    _jalan(skenario())


# ── Peta memakai versi optimize ────────────────────────────────────────────

def test_peta_mengirim_versi_ringan_secara_bawaan(dbx):
    async def skenario():
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        fc = await _unwrap(rs.geojson_viewport)(
            bbox="", level_maks=100, induk="", dalam="", asli=False, _user=USER)
        assert fc["sumber"] == "optimize"
        assert fc["titik_dikirim"] < fc["titik_asli"]
        assert fc["hemat_persen"] > 50
        assert fc["features"][0]["properties"]["dioptimalkan"] is True
    _jalan(skenario())


def test_saklar_lihat_asli_mengirim_geometri_penuh(dbx):
    async def skenario():
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        fc = await _unwrap(rs.geojson_viewport)(
            bbox="", level_maks=100, induk="", dalam="", asli=True, _user=USER)
        assert fc["sumber"] == "asli"
        assert fc["titik_dikirim"] == fc["titik_asli"]
        assert fc["features"][0]["properties"]["dioptimalkan"] is False
    _jalan(skenario())


def test_node_belum_dioptimalkan_tetap_muncul_di_peta(dbx):
    """Peta TIDAK BOLEH kosong hanya karena tombol optimasi belum ditekan."""
    async def skenario():
        await _seed(dbx, 1)
        fc = await _unwrap(rs.geojson_viewport)(
            bbox="", level_maks=100, induk="", dalam="", asli=False, _user=USER)
        assert len(fc["features"]) == 1
        assert fc["titik_dikirim"] == fc["titik_asli"]
    _jalan(skenario())


# ── Ekspor: pilihan asli vs optimize ───────────────────────────────────────

def test_ekspor_bawaan_memberi_geometri_asli(dbx):
    """Bawaan ASLI, disengaja: berkas ekspor jadi arsip cadangan dan bahan
    QGIS. Diam-diam memberi versi sederhana = presisi hilang tiap putaran."""
    async def skenario():
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        r = await _unwrap(rs.ekspor_denah)(
            None, format="geojson", dalam="", sertakan_draft=True,
            geometri="asli", _user=USER)
        isi = r.body.decode("utf-8")
        assert "optimize" not in r.headers.get("content-disposition", "")
        node = await dbx.spasial_node.find_one({"id": "n0"})
        # Berkas memuat sebanyak verteks aslinya, bukan versi ringannya.
        import json
        fc = json.loads(isi)
        titik = sum(so._titik_geom(f["geometry"]) for f in fc["features"])
        assert titik == so._titik_geom(node["geometry"])
    _jalan(skenario())


def test_ekspor_optimize_memberi_versi_ringan_dan_ditandai(dbx):
    async def skenario():
        import json
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        r = await _unwrap(rs.ekspor_denah)(
            None, format="geojson", dalam="", sertakan_draft=True,
            geometri="optimize", _user=USER)
        fc = json.loads(r.body.decode("utf-8"))
        node = await dbx.spasial_node.find_one({"id": "n0"})
        titik = sum(so._titik_geom(f["geometry"]) for f in fc["features"])
        assert titik == so._titik_geom(node["geometry_opt"])
        assert titik < so._titik_geom(node["geometry"])
        # Penanda ikut di NAMA BERKAS — berkas berpindah tangan.
        assert "optimize" in r.headers.get("content-disposition", "")
    _jalan(skenario())


def test_ekspor_optimize_tak_melubangi_node_yang_belum_dioptimalkan(dbx):
    """Berkas bolong lebih berbahaya daripada berkas yang sebagian berat."""
    async def skenario():
        import json
        await _seed(dbx, 2)
        # Hanya satu yang dioptimalkan.
        await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(dalam="n0"), user=USER)
        r = await _unwrap(rs.ekspor_denah)(
            None, format="geojson", dalam="", sertakan_draft=True,
            geometri="optimize", _user=USER)
        fc = json.loads(r.body.decode("utf-8"))
        assert len(fc["features"]) == 2, "node tanpa versi optimize hilang"
    _jalan(skenario())


# ── Editor selalu menyunting yang ASLI ─────────────────────────────────────

def test_detail_node_tak_pernah_menyerahkan_versi_ringan(dbx):
    """Detail node adalah sumber bentuk yang DISUNTING di DenahEditor.

    Bila `geometry_opt` ikut terkirim, cepat atau lambat ada layar yang memakai
    "geometri mana pun yang tersedia" — dan penyimpanan berikutnya menuliskan
    versi sederhana KE ATAS geometri asli. Penyederhanaan yang seharusnya bisa
    dibatalkan berubah jadi permanen, tanpa satu pun galat. Maka: tak dikirim.
    """
    async def skenario():
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        node = await _unwrap(rs.detail_node)("n0", _user=USER)
        assert "geometry_opt" not in node
        tersimpan = await dbx.spasial_node.find_one({"id": "n0"})
        assert node["geometry"] == tersimpan["geometry"], "editor menerima bentuk lain"
        # Ringkasan metriknya tetap boleh ikut — itu sekadar angka untuk layar.
        assert node.get("optimasi", {}).get("hemat_persen", 0) > 0
    _jalan(skenario())


# ── Simpan node: optimasi otomatis ─────────────────────────────────────────

def test_menyimpan_geometri_langsung_menghasilkan_versi_ringan():
    """Gambar sendiri lewat DenahEditor pun langsung punya versi ringan —
    tanpa operator perlu tahu tombol optimasi ada."""
    doc = {}
    rs._terapkan_geometri(doc, _lingkaran())
    assert doc["geometry_opt"] is not None
    assert so._titik_geom(doc["geometry_opt"]) < so._titik_geom(doc["geometry"])
    assert doc["optimasi"]["hemat_persen"] > 50
    assert doc["optimasi"]["pada"]


def test_mengosongkan_geometri_ikut_membuang_salinannya():
    """Salinan yatim akan ditampilkan sebagai bentuk yang sudah tak ada."""
    doc = {}
    rs._terapkan_geometri(doc, _lingkaran())
    assert doc["geometry_opt"] is not None
    rs._terapkan_geometri(doc, {})
    assert doc["geometry"] is None
    assert doc["geometry_opt"] is None


def test_mengganti_geometri_memperbarui_salinannya():
    """Sisa dari geometri LAMA tak boleh bertahan setelah bentuknya diganti."""
    doc = {}
    rs._terapkan_geometri(doc, _lingkaran(n=800))
    lama = doc["geometry_opt"]
    rs._terapkan_geometri(doc, _lingkaran(lon0=117.2, n=600))
    assert doc["geometry_opt"] != lama
