"""Lapisan eksisting peta: citra (ubin unggahan) dan gambar (titik/garis/area)."""
import asyncio
import io
from pathlib import Path

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from PIL import Image
from starlette.datastructures import Headers, UploadFile

import routes.peta_lapisan as rp
import shared_utils as su
from backup_utils import RESET_KEEP_COLLECTIONS
from peta_lapisan_utils import (
    isi_cocok_format, jumlah_ubin, nama_berkas_ubin, normalisasi_citra_baru,
    normalisasi_gambar, rentang_ubin, token_ubin, token_ubin_sah, ubin_x, ubin_y,
)

SUPER = {"id": "s", "username": "pusat", "role": "admin", "kode_satker": ""}
ADMIN_A = {"id": "a", "username": "adm_a", "role": "admin", "kode_satker": "A"}
ADMIN_B = {"id": "b", "username": "adm_b", "role": "admin", "kode_satker": "B"}
USER_B = {"id": "ub", "username": "staf_b", "role": "user", "kode_satker": "B"}

BATAS = {"barat": 116.695, "selatan": -0.975, "timur": 116.715, "utara": -0.955}
CITRA = {"jenis": "citra", "nama": "Citra KIPP", "sumber": "Tim", "tanggal_rekam": "2026-10-15",
         "batas": BATAS, "zoom_min": 14, "zoom_maks": 16, "format": "png", "crs_asal": "EPSG:32750"}
GARIS = {"id": "g1", "geometri": {"type": "LineString", "coordinates": [[116.70, -0.96], [116.71, -0.965]]},
         "gaya": {"warna": "#FF0000", "tebal": 5}, "label": {"teks": "Jl. Baru", "posisi": "ikut"}}


@pytest.fixture
def database(monkeypatch, tmp_path):
    fake = AsyncMongoMockClient()["peta_lapisan"]
    monkeypatch.setattr(rp, "db", fake)
    monkeypatch.setattr(su, "db", fake)
    monkeypatch.setenv("AMAN_UBIN_DIR", str(tmp_path / "ubin"))
    return fake


def _in(**d):
    return rp.LapisanIn(**d)


def _png():
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), (120, 100, 80, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _berkas(nama, data):
    return UploadFile(io.BytesIO(data), filename=nama, headers=Headers({"content-type": "image/png"}))


def _ubin_sah(z=15):
    x0, _, y0, _ = rentang_ubin(BATAS, z)
    return z, x0, y0


# ── murni ───────────────────────────────────────────────────────────────────

def test_matematika_ubin_xyz():
    assert (ubin_x(0, 1), ubin_y(0, 1)) == (1, 1)
    assert (ubin_x(-180, 2), ubin_y(85, 2)) == (0, 0)
    assert jumlah_ubin(BATAS, 14, 14) >= 1
    assert nama_berkas_ubin("15-27006-16471.webp") == (15, 27006, 16471, "webp")
    for buruk in ("../1-2-3.png", "15-27006-16471.gif", "a-b-c.png", "15-1-2.png.exe"):
        assert nama_berkas_ubin(buruk) is None


def test_tanda_tangan_berkas_diperiksa():
    assert isi_cocok_format(_png(), "png")
    assert not isi_cocok_format(b"<html>", "png")
    assert not isi_cocok_format(_png(), "webp")


def test_token_ubin_berganti_harian_dan_tak_bisa_dipalsukan():
    t = token_ubin("rahasia", 100)
    assert token_ubin_sah("rahasia", t, 100) and token_ubin_sah("rahasia", t, 101)
    assert not token_ubin_sah("rahasia", t, 102)
    assert not token_ubin_sah("lain", t, 100)
    assert not token_ubin_sah("rahasia", "100.palsu", 100)
    assert not token_ubin_sah("rahasia", "", 100)


def test_citra_terlalu_besar_atau_batas_rusak_ditolak():
    _, g = normalisasi_citra_baru({**CITRA, "zoom_min": 5, "zoom_maks": 22,
                                   "batas": {"barat": 110, "selatan": -5, "timur": 120, "utara": 5}})
    assert any("terlalu besar" in x for x in g)
    _, g = normalisasi_citra_baru({**CITRA, "batas": {"barat": 117, "selatan": -1, "timur": 116, "utara": 0}})
    assert g
    _, g = normalisasi_citra_baru({**CITRA, "format": "gif"})
    assert g


def test_gambar_dibersihkan_dan_dibatasi():
    dok, g = normalisasi_gambar({"nama": "Jalan baru", "fitur": [
        GARIS,
        {"geometri": {"type": "Point", "coordinates": [116.7, -0.96]},
         "label": {"teks": "<b>Pos</b>", "posisi": "ikut", "warna": "red"}},
        {"geometri": {"type": "Polygon", "coordinates": [[[116.70, -0.96], [116.71, -0.96], [116.71, -0.97]]]}},
    ]})
    assert g == []
    garis, titik, area = dok["fitur"]
    assert garis["gaya"]["warna"] == "#ff0000" and garis["gaya"]["tebal"] == 5
    assert garis["label"]["posisi"] == "ikut"
    assert titik["tipe"] == "titik" and titik["label"]["posisi"] == "atas"   # 'ikut' tak sah utk titik
    assert titik["label"]["warna"] == "#111827"                              # warna non-hex ditolak
    assert titik["label"]["teks"] == "<b>Pos</b>"   # teks disimpan apa adanya; dirender sbg TEKS
    ring = area["geometri"]["coordinates"][0]
    assert area["tipe"] == "area" and ring[0] == ring[-1]                    # cincin ditutup


@pytest.mark.parametrize("fitur", [
    {"geometri": {"type": "LineString", "coordinates": [[116.7, -0.96]]}},
    {"geometri": {"type": "Point", "coordinates": [200, 0]}},
    {"geometri": {"type": "MultiPolygon", "coordinates": []}},
    {"geometri": None},
])
def test_geometri_tak_sah_ditolak(fitur):
    _, g = normalisasi_gambar({"nama": "x", "fitur": [fitur]})
    assert g


# ── endpoint gambar ─────────────────────────────────────────────────────────

def test_gambar_dibaca_bersama_ditulis_terjaga(database):
    async def run():
        dok = await rp.buat_lapisan(_in(jenis="gambar", nama="Jalan", fitur=[GARIS]), user=ADMIN_A)
        hasil = await rp.daftar_lapisan(user=USER_B)
        assert [i["id"] for i in hasil["items"]] == [dok["id"]]
        assert hasil["items"][0]["fitur"][0]["label"]["teks"] == "Jl. Baru"
        assert "kode_satker" not in hasil["items"][0] and hasil["ubin_token"]
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(jenis="gambar", nama="X", version=1), user=ADMIN_B)
        assert e.value.status_code == 403
        baru = await rp.ubah_lapisan(dok["id"], _in(jenis="gambar", nama="Jalan 2", fitur=[], version=1),
                                     user=ADMIN_A)
        assert baru["version"] == 2 and baru["fitur"] == []
        with pytest.raises(HTTPException) as e:
            await rp.ubah_lapisan(dok["id"], _in(jenis="gambar", nama="Y", version=1), user=ADMIN_A)
        assert e.value.status_code == 409
    asyncio.run(run())


def test_lapisan_pusat_tak_bisa_diubah_admin_satker(database):
    async def run():
        dok = await rp.buat_lapisan(_in(jenis="gambar", nama="Pusat"), user=SUPER)
        with pytest.raises(HTTPException) as e:
            await rp.hapus_lapisan(dok["id"], user=ADMIN_A)
        assert e.value.status_code == 403
    asyncio.run(run())


def test_urutan_diatur_dan_dipakai_daftar(database):
    async def run():
        a = await rp.buat_lapisan(_in(jenis="gambar", nama="A"), user=ADMIN_A)
        b = await rp.buat_lapisan(_in(jenis="gambar", nama="B"), user=ADMIN_A)
        assert [i["nama"] for i in (await rp.daftar_lapisan(user=USER_B))["items"]] == ["A", "B"]
        await rp.atur_urutan(rp.UrutanIn(ids=[b["id"], a["id"]]), user=ADMIN_B)
        assert [i["nama"] for i in (await rp.daftar_lapisan(user=USER_B))["items"]] == ["B", "A"]
    asyncio.run(run())


# ── endpoint citra & ubin ───────────────────────────────────────────────────

def test_alur_unggah_citra_lengkap(database):
    async def run():
        dok = await rp.buat_lapisan(_in(**CITRA), user=ADMIN_A)
        assert dok["status"] == "memproses" and dok["aktif"] is False
        # Belum selesai: pengguna biasa belum melihatnya.
        assert (await rp.daftar_lapisan(user=USER_B))["items"] == []
        z, x, y = _ubin_sah()
        r = await rp.unggah_ubin(dok["id"], files=[_berkas(f"{z}-{x}-{y}.png", _png())], user=ADMIN_A)
        assert r["tersimpan"] == 1
        akhir = await rp.selesai_unggah(dok["id"], user=ADMIN_A)
        assert akhir["status"] == "siap" and akhir["aktif"] and akhir["jumlah_ubin"] == 1
        daftar = await rp.daftar_lapisan(user=USER_B)
        assert [i["id"] for i in daftar["items"]] == [dok["id"]]
        # Ubin tersaji dengan token; tanpa token ditolak.
        resp = await rp.ambil_ubin(dok["id"], z, x, f"{y}.png", t=daftar["ubin_token"])
        assert Path(resp.path).read_bytes()[:4] == b"\x89PNG"
        assert "immutable" in resp.headers["cache-control"]
        with pytest.raises(HTTPException) as e:
            await rp.ambil_ubin(dok["id"], z, x, f"{y}.png", t="1.palsu")
        assert e.value.status_code == 403
        with pytest.raises(HTTPException) as e:
            await rp.ambil_ubin(dok["id"], z, x + 99, f"{y}.png", t=daftar["ubin_token"])
        assert e.value.status_code == 404
        # Sesudah selesai, unggahan baru ditolak.
        with pytest.raises(HTTPException) as e:
            await rp.unggah_ubin(dok["id"], files=[_berkas(f"{z}-{x}-{y}.png", _png())], user=ADMIN_A)
        assert e.value.status_code == 409
        # Hapus lapisan → folder ubin ikut hilang.
        folder = rp._folder_lapisan(dok["id"])
        assert folder.exists()
        await rp.hapus_lapisan(dok["id"], user=ADMIN_A)
        assert not folder.exists()
    asyncio.run(run())


@pytest.mark.parametrize("nama,isi", [
    ("15-1-1.png", "png"),             # di luar batas citra
    ("SAH.webp", "png"),               # format beda dengan registri
    ("SAH.png", "html"),               # isi bukan PNG
    ("../../etc-1-1.png", "png"),      # nama tak sah
])
def test_ubin_tak_sah_ditolak(database, nama, isi):
    async def run():
        dok = await rp.buat_lapisan(_in(**CITRA), user=ADMIN_A)
        z, x, y = _ubin_sah()
        n = nama.replace("SAH", f"{z}-{x}-{y}")
        data = _png() if isi == "png" else b"<!doctype html>"
        with pytest.raises(HTTPException) as e:
            await rp.unggah_ubin(dok["id"], files=[_berkas(n, data)], user=ADMIN_A)
        assert e.value.status_code == 400
    asyncio.run(run())


def test_admin_lain_tak_bisa_mengunggah_ke_citra_orang(database):
    async def run():
        dok = await rp.buat_lapisan(_in(**CITRA), user=ADMIN_A)
        z, x, y = _ubin_sah()
        with pytest.raises(HTTPException) as e:
            await rp.unggah_ubin(dok["id"], files=[_berkas(f"{z}-{x}-{y}.png", _png())], user=ADMIN_B)
        assert e.value.status_code == 403
    asyncio.run(run())


def test_selesai_tanpa_ubin_ditolak(database):
    async def run():
        dok = await rp.buat_lapisan(_in(**CITRA), user=ADMIN_A)
        with pytest.raises(HTTPException) as e:
            await rp.selesai_unggah(dok["id"], user=ADMIN_A)
        assert e.value.status_code == 400
    asyncio.run(run())


def test_ubin_disimpan_di_luar_folder_uploads(database):
    assert "uploads" not in rp.akar_ubin().parts


def test_registri_selamat_dari_reset():
    assert "peta_lapisan" in RESET_KEEP_COLLECTIONS


def test_router_terdaftar_di_server():
    src = (Path(__file__).resolve().parents[2] / "server.py").read_text(encoding="utf-8")
    assert "from routes.peta_lapisan import peta_lapisan_router" in src
    assert "api_router.include_router(peta_lapisan_router)" in src


def test_unggah_multipart_lewat_http_sungguhan(database):
    """Format kiriman peramban (FormData, field `files` berulang) cocok dengan
    endpoint FastAPI — bukan hanya fungsi handler yang dipanggil langsung."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from auth_utils import require_admin, require_user

    app = FastAPI()
    app.include_router(rp.peta_lapisan_router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: ADMIN_A
    app.dependency_overrides[require_user] = lambda: ADMIN_A
    with TestClient(app) as c:
        dok = c.post("/api/peta-lapisan", json=CITRA).json()
        z, x, y = _ubin_sah()
        x2 = x + 1 if rp.ubin_dalam_batas(BATAS, z, x + 1, y) else x
        r = c.post(f"/api/peta-lapisan/{dok['id']}/ubin", files=[
            ("files", (f"{z}-{x}-{y}.png", _png(), "image/png")),
            ("files", (f"{z}-{x2}-{y}.png", _png(), "image/png")),
        ])
        assert r.status_code == 200, r.text
        assert r.json()["tersimpan"] == 2
        assert c.post(f"/api/peta-lapisan/{dok['id']}/selesai").json()["status"] == "siap"
        token = c.get("/api/peta-lapisan").json()["ubin_token"]
        u = c.get(f"/api/peta-lapisan/{dok['id']}/ubin/{z}/{x}/{y}.png", params={"t": token})
        assert u.status_code == 200 and u.headers["content-type"] == "image/png"
        assert c.get(f"/api/peta-lapisan/{dok['id']}/ubin/{z}/{x}/{y}.png").status_code == 403
