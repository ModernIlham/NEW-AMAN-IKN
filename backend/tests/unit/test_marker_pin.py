"""Desain pin: skema, gambar standar, portabilitas, dan batas seleksi massal."""
import asyncio
import base64
import io
import json
import re
from pathlib import Path

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from PIL import Image, PngImagePlugin

from marker_pin import (
    AWAL_PNG, BAWAAN, IKON_PIN, _standarkan, bersihkan_marker_doc,
    marker_pin_publik, normalisasi_marker_pin,
)


def desain(**kw):
    return json.dumps({**BAWAAN, **kw})


def png(size=(64, 64), metadata=False):
    b = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    if metadata:
        info.add_text("Description", "metadata pribadi tidak boleh ikut")
    Image.new("RGBA", size, (0, 128, 0, 128)).save(b, "PNG", pnginfo=info)
    return AWAL_PNG + base64.b64encode(b.getvalue()).decode()


@pytest.mark.parametrize("mode", ["icon", "text", "custom"])
def test_desain_kanonik_idempoten(mode):
    raw = desain(mode=mode, image=png() if mode == "custom" else "", text="A1")
    result = _standarkan(raw)
    assert _standarkan(result) == result
    assert json.loads(result)["mode"] == mode


@pytest.mark.parametrize("bad", ["<svg/>", "[]", "null", "{}invalid", "x" * 14001,
    desain(v=True), desain(v=2), desain(mode="html"), desain(icon="evil"),
    desain(text="<A>"), desain(text="ABCD"), desain(text=""), desain(text="é"),
    desain(circle="true"), desain(strokeWidth=True), desain(strokeWidth=-1),
    desain(strokeWidth=4), desain(iconColor="red"), desain(circleColor="url(x)"),
    desain(strokeColor='#ffffff" onload="x'), desain(extra="x"),
    desain(mode="custom", image="https://example.com/a.png"),
    desain(mode="custom", image="data:image/svg+xml;base64,PHN2Zy8+"),
    desain(mode="custom", image=AWAL_PNG + "!invalid"),
    desain(mode="custom", image=AWAL_PNG + base64.b64encode(b"bad").decode()),
])
def test_payload_di_luar_standar_ditolak(bad):
    with pytest.raises(ValueError):
        _standarkan(bad)
    assert marker_pin_publik(bad) == ""


@pytest.mark.parametrize("image", [png((32, 64)), png((65, 64)), AWAL_PNG + base64.b64encode(b"\x89PNG\r\n\x1a\nrusak").decode()])
def test_png_salah_dimensi_atau_rusak_ditolak(image):
    with pytest.raises(ValueError):
        _standarkan(desain(mode="custom", image=image))


def test_metadata_dihapus_dan_transparansi_dipertahankan():
    d = json.loads(_standarkan(desain(mode="custom", image=png(metadata=True))))
    b = base64.b64decode(d["image"].split(",")[1])
    assert b"metadata pribadi" not in b
    with Image.open(io.BytesIO(b)) as img:
        assert img.size == (64, 64)
        assert img.getpixel((0, 0)) == (0, 128, 0, 128)


def test_polos_dan_ganti_jenis_membuang_isi_tak_relevan():
    assert normalisasi_marker_pin("") == ""
    assert normalisasi_marker_pin(None) == ""
    d = json.loads(normalisasi_marker_pin(desain(mode="icon", image="rahasia", text="XYZ")))
    assert d["image"] == "" and d["text"] == "A"


def test_katalog_frontend_backend_selaras():
    root = Path(__file__).resolve().parents[3]
    src = (root / "frontend/src/lib/markerPin.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'\["([a-z]+)", "[^"]+", "[^"]+", [A-Z]', src))
    assert ids == IKON_PIN


def test_peta_publik_hanya_desain_tervalidasi():
    from routes.peta_kolaborasi import baris_titik_publik
    val = desain(mode="text", text="B2")
    row = baris_titik_publik({"id": "a", "marker_pin": val, "pengguna_nip": "rahasia"}, 1, 2)
    assert json.loads(row["marker_pin"])["text"] == "B2"
    assert "pengguna_nip" not in row


@pytest.mark.parametrize("mode", ["icon", "text", "custom"])
def test_csv_roundtrip_mempertahankan_kutip_json(mode):
    from routes.imports import parse_csv_content
    from shared_utils import sel_csv
    value = _standarkan(desain(mode=mode, image=png() if mode == "custom" else "", text="AB1"))
    content = "asset_code,marker_pin\n" + ",".join(sel_csv(x) for x in ["3100102001", value]) + "\n"
    row = parse_csv_content(content.encode("utf-8-sig"))[0]
    assert row["marker_pin"] == value
    assert _standarkan(row["marker_pin"]) == value


def test_validator_doc_menolak_sebelum_tulisan():
    async def run():
        with pytest.raises(HTTPException) as e:
            await bersihkan_marker_doc({"marker_pin": desain(mode="custom", image=png((1, 1)))})
        assert e.value.status_code == 422
    asyncio.run(run())


async def diam(*a, **kw):
    return None


class Req:
    headers = {}
    def __init__(self, body=None, version=None):
        self.body = body
        self.headers = {"If-Match": str(version)} if version else {}
    async def json(self):
        return self.body


@pytest.fixture
def dbx(monkeypatch):
    import routes.assets as ra
    import routes.batch as rb
    import shared_utils as su
    db = AsyncMongoMockClient()["marker"]
    for mod in (ra, rb, su):
        monkeypatch.setattr(mod, "db", db)
    for mod in (ra, rb):
        for name in ("log_audit", "notify_asset_change"):
            monkeypatch.setattr(mod, name, diam)
        monkeypatch.setattr(mod, "invalidate_asset_cache", lambda: None)
    monkeypatch.setattr(ra, "jadwalkan_sync", lambda *a: None)
    monkeypatch.setattr(rb, "jadwalkan_sync_id", lambda *a: None)
    monkeypatch.setattr(ra.sp, "penempatan_dari_inventarisasi", diam)
    return db


@pytest.mark.parametrize("jumlah", [5, 1000])
def test_massal_hanya_seleksi_lalu_patch_menghormati_versi(dbx, jumlah):
    import routes.assets as ra
    import routes.batch as rb
    user = {"username": "uji", "role": "admin", "kode_satker": ""}
    async def run():
        await dbx.assets.insert_many([{"id": f"a{i}", "asset_code": f"3{i}", "asset_name": "Meja", "category": "Dummy", "created_at": "2026-09-25", "version": 1, "location": "Tidak berubah", "marker_pin": ""} for i in range(jumlah)])
        terpilih = set(range(1, jumlah, 2))
        val = desain(mode="text", text="IKN")
        await rb.batch_update_assets(rb.BatchUpdateRequest(asset_ids=[f"a{i}" for i in sorted(terpilih)], updates={"marker_pin": val}), Req(), None, None, None, user)
        for i in range(jumlah):
            a = await dbx.assets.find_one({"id": f"a{i}"})
            assert a["location"] == "Tidak berubah"
            assert bool(a["marker_pin"]) == (i in terpilih)
            assert a["version"] == (2 if i in terpilih else 1)
        with pytest.raises(HTTPException) as e:
            await ra.patch_asset("a1", Req({"marker_pin": ""}, 1), user)
        assert e.value.status_code == 409
        r = await ra.patch_asset("a1", Req({"marker_pin": ""}, 2), user)
        assert r.marker_pin == "" and r.version == 3
        assert (await dbx.assets.find_one({"id": "a3"}))["marker_pin"]
    asyncio.run(run())


@pytest.mark.parametrize("nilai_put", [None, "", desain(mode="text", text="C3")])
def test_create_put_menyimpan_desain_dan_klien_lama_tidak_menghapus(dbx, monkeypatch, nilai_put):
    import routes.assets as ra
    from models import AssetCreate
    monkeypatch.setattr(ra, "_enforce_pegawai_terdaftar", diam)
    user = {"username": "uji", "role": "admin", "kode_satker": ""}
    async def run():
        val = desain(mode="custom", image=png(metadata=True))
        fields = {"asset_code": "3", "asset_name": "Meja", "category": "Dummy", "NUP": "1"}
        r = await ra.create_asset(AssetCreate(**fields, marker_pin=val), Req(), user)
        assert json.loads(r.marker_pin)["mode"] == "custom"
        assert "metadata pribadi" not in base64.b64decode(json.loads(r.marker_pin)["image"].split(",")[1]).decode('latin1')
        if nilai_put is not None:
            fields["marker_pin"] = nilai_put
        updated = await ra.update_asset(r.id, AssetCreate(**fields), Req(version=1), user)
        assert updated.marker_pin == (r.marker_pin if nilai_put is None else normalisasi_marker_pin(nilai_put))
    asyncio.run(run())


@pytest.mark.parametrize("jenis", ["satker_lain", "disahkan", "desain_rusak"])
def test_massal_gagal_tidak_mengubah_aset(dbx, jenis):
    import routes.batch as rb
    async def run():
        await dbx.inventory_activities.insert_one({"id": "k", "kode_satker": "B", "status_pengesahan": "disahkan" if jenis == "disahkan" else "draft"})
        await dbx.assets.insert_one({"id": "a", "activity_id": "k", "version": 1, "marker_pin": ""})
        user = {"username": "uji", "role": "admin", "kode_satker": "A" if jenis == "satker_lain" else ""}
        val = "bad" if jenis == "desain_rusak" else desain()
        with pytest.raises(HTTPException) as e:
            await rb.batch_update_assets(rb.BatchUpdateRequest(asset_ids=["a"], updates={"marker_pin": val}), Req(), None, None, None, user)
        assert e.value.status_code == {"satker_lain": 403, "disahkan": 423, "desain_rusak": 422}[jenis]
        assert (await dbx.assets.find_one({"id": "a"}))["version"] == 1
    asyncio.run(run())
