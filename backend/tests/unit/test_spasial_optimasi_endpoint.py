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


def test_optimasi_massal_berhenti_pada_anggaran_waktu(dbx, monkeypatch):
    """Plafon berupa CACAH node tidak cukup.

    Biaya per poligon berbeda satu orde besaran menurut verteksnya, jadi 500
    node hasil impor SHP berarti permintaan HTTP bermenit-menit — melewati
    batas waktu proxy, dan operator melihat 504 padahal servernya masih
    bekerja dan sebagian hasilnya sudah tersimpan tanpa pernah dilaporkan.
    """
    async def skenario():
        await _seed(dbx, 3)
        monkeypatch.setattr(rs, "ANGGARAN_OPTIMASI_DETIK", 0.0, raising=False)
        h = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        # Anggaran nol pun WAJIB menghasilkan kemajuan — kalau tidak,
        # "tekan sekali lagi" jadi lingkaran yang tak pernah maju.
        assert h["diproses"] == 1, "anggaran habis = tak ada kemajuan sama sekali"
        assert h["terpotong"] is True, "sisanya tak dilaporkan; operator mengira selesai"
        assert h["kandidat"] == 3
        # Dan yang belum sempat digarap memang belum tersentuh.
        belum = [r async for r in dbx.spasial_node.find({"geometry_opt": None})]
        assert len(belum) == 2
    _jalan(skenario())


def test_optimasi_massal_tuntas_tak_mengaku_terpotong(dbx):
    """Kebalikannya sama pentingnya: pekerjaan yang SELESAI tak boleh menyuruh
    operator menekan tombolnya lagi tanpa henti."""
    async def skenario():
        await _seed(dbx, 2)
        h = await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(), user=USER)
        assert h["diproses"] == 2 and h["terpotong"] is False
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


def test_saklar_asli_tak_ikut_menarik_salinan_ringan(dbx):
    """`asli=1` sudah paling berat; jangan ditambahi muatan yang tak dipakai.

    Pada mode asli, `geometry_opt` tak pernah dikirim maupun dibaca — menariknya
    dari DB hanya menambah beban di endpoint yang seluruh alasan keberadaannya
    justru memangkas beban. Dijaga lewat perilaku yang terlihat: fitur mode asli
    tak boleh membawa jejak salinan ringan sama sekali.
    """
    async def skenario():
        await _seed(dbx, 1)
        await _unwrap(rs.optimasi_massal)(None, rs.OptimasiMassalIn(), user=USER)
        fc = await _unwrap(rs.geojson_viewport)(
            bbox="", level_maks=100, induk="", dalam="", asli=True, _user=USER)
        f = fc["features"][0]
        assert "geometry_opt" not in f and "geometry_opt" not in f["properties"]
        assert f["properties"]["dioptimalkan"] is False
        # Dan yang dikirim memang geometri PENUH, bukan diam-diam yang ringan.
        node = await dbx.spasial_node.find_one({"id": "n0"})
        assert so._titik_geom(f["geometry"]) == so._titik_geom(node["geometry"])
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


# ── Daftar node tak boleh membawa geometri apa pun ─────────────────────────

def test_daftar_node_tak_membawa_geometri_ringan(dbx):
    """Daftar node sengaja membuang `geometry` demi SLA — dan `geometry_opt`
    tunduk pada alasan yang sama.

    Per node ia memang jauh lebih ringan, tetapi daftar ini memuat sampai
    20.000 node sekaligus. Ratusan verteks dikali puluhan ribu baris tetap
    payload raksasa, dan tak satu pun layar daftar menggambar poligon. Yang
    dibutuhkan hanya "sudah diringankan atau belum".
    """
    async def skenario():
        await _seed(dbx, 2)
        await _unwrap(rs.optimasi_massal)(
            None, rs.OptimasiMassalIn(dalam="n0"), user=USER)
        hasil = await _unwrap(rs.daftar_node)(
            parent_id="", tipe="", q="", _user=USER)
        for n in hasil["items"]:
            assert "geometry" not in n
            assert "geometry_opt" not in n, "versi ringan ikut terbawa daftar"
        by_id = {n["id"]: n for n in hasil["items"]}
        assert by_id["n0"]["dioptimalkan"] is True
        assert by_id["n1"]["dioptimalkan"] is False
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

def test_jalur_simpan_menghitung_di_thread_dengan_hasil_yang_sama():
    """`so.optimalkan` menaiki sembilan anak tangga toleransi, tiap anak tangga
    menjalankan simplify + Hausdorff shapely. Dijalankan langsung di event loop
    ia membekukan SELURUH server saat poligon impor SHP disimpan — termasuk
    permintaan pengguna lain yang tak ada urusannya dengan peta.

    Yang dijaga di sini: jalur thread menghasilkan dokumen yang SAMA. Optimasi
    yang dipindah ke thread lalu diam-diam berbeda isinya adalah kerusakan yang
    lebih halus daripada event loop yang tersendat.
    """
    async def skenario():
        g = _lingkaran()
        sinkron, lewat_thread = {}, {}
        rs._terapkan_geometri(sinkron, g)
        await rs._terapkan_geometri_async(lewat_thread, g)
        assert lewat_thread["geometry"] == sinkron["geometry"]
        assert lewat_thread["geometry_opt"] == sinkron["geometry_opt"]
        assert lewat_thread["optimasi"]["hemat_persen"] == sinkron["optimasi"]["hemat_persen"]
    _jalan(skenario())


def test_jalur_simpan_mengganti_geometri_tak_menyisakan_salinan_lama():
    """`optimalkan=False` BUKAN saklar "lewati optimasi".

    Bila pemanggil mematikannya lalu lupa memasang hasilnya, dokumen membawa
    `geometry_opt` warisan geometri LAMA — peta menggambar bentuk yang sudah
    tak ada, dan tak ada galat yang memberi tahu siapa pun.
    """
    async def skenario():
        doc = {}
        await rs._terapkan_geometri_async(doc, _lingkaran(n=800))
        lama = doc["geometry_opt"]
        await rs._terapkan_geometri_async(doc, _lingkaran(lon0=117.2, n=600))
        assert doc["geometry_opt"] != lama
        # Dan salinannya memang milik geometri yang SEKARANG tersimpan.
        assert so.ukur_penyimpangan(doc["geometry"], doc["geometry_opt"])["geser_m"] \
            <= so.MAKS_GESER_M
    _jalan(skenario())


def test_jalur_simpan_mengosongkan_geometri_ikut_membuang_salinannya():
    async def skenario():
        doc = {}
        await rs._terapkan_geometri_async(doc, _lingkaran())
        assert doc["geometry_opt"] is not None
        await rs._terapkan_geometri_async(doc, {})
        assert doc["geometry"] is None and doc["geometry_opt"] is None
    _jalan(skenario())


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
