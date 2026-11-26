"""Rantai kompresi beralih bersih ketika penyedia menolak atau sudah optimal.

Laporan pemilik (Nov 2026), dari layar Kompresi Gambar:
  1. "Saat Tinify masih ada saldonya, tiba-tiba ada 1 terhitung di Compresto."
  2. "Saat Compresto habis, masih tertinggal 1" — layar menulis 1/500,
     menandai Compresto "dipakai" sambil menampilkan "Batas laju layanan
     tercapai", sehingga peralihan ke Uploadcare tersendat.

Uji di sini memakai Mongo tiruan + transport HTTP tiruan; tidak ada panggilan
jaringan sungguhan.
"""
import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from mongomock_motor import AsyncMongoMockClient
from PIL import Image

import kompresi_diagnostik as kd
import routes.media as media


@pytest.fixture
def rig(monkeypatch):
    fake = AsyncMongoMockClient()["kompresi_penolakan"]
    monkeypatch.setattr(media, "db", fake)
    monkeypatch.setattr(media, "COMPRESTO_API_KEY", "kunci-uji")
    monkeypatch.setattr(media, "UPLOADCARE_PUBLIC_KEY", "kunci-uji")
    kd.reset_status()
    state = {"handler": None, "calls": []}
    asli = httpx.AsyncClient

    async def transport(request):
        state["calls"].append(str(request.url))
        return await state["handler"](request)

    monkeypatch.setattr(media.httpx, "AsyncClient",
                        lambda **kw: asli(transport=httpx.MockTransport(transport)))
    state["db"] = fake
    yield state
    kd.reset_status()


async def _bulan():
    return await media.get_current_month()


async def _set_used(db, service, used):
    await db.compression_quotas.insert_one(
        {"service": service, "month": await _bulan(), "used": used,
         "limit": media.SERVICE_LIMITS[service]})


async def _doc(db, service):
    return await db.compression_quotas.find_one({"service": service, "month": await _bulan()})


def _jawab(code, body=b"x"):
    async def h(request):
        return httpx.Response(code, content=body)
    return h


# ── 429/402 dari penyedia ──────────────────────────────────────────────────

def test_429_saat_sisa_tinggal_satu_menutup_kuota_bulan_ini(rig):
    async def run():
        await _set_used(rig["db"], "compresto", 499)
        rig["handler"] = _jawab(429)
        assert await media.compress_with_compresto(b"foto") is None
        doc = await _doc(rig["db"], "compresto")
        assert doc["used"] == 500 and doc["ditutup_penyedia"] == 429
        assert not await media.is_quota_available("compresto")
        # Permintaan berikutnya TIDAK lagi mengetuk Compresto.
        rig["calls"].clear()
        assert await media.compress_with_compresto(b"foto") is None
        assert rig["calls"] == []
    asyncio.run(run())


def test_402_menutup_kuota_walau_sisa_banyak(rig):
    async def run():
        await _set_used(rig["db"], "compresto", 10)
        rig["handler"] = _jawab(402)
        await media.compress_with_compresto(b"foto")
        assert (await _doc(rig["db"], "compresto"))["used"] == 500
    asyncio.run(run())


def test_429_saat_sisa_banyak_hanya_menahan_sementara(rig):
    async def run():
        await _set_used(rig["db"], "compresto", 100)
        rig["handler"] = _jawab(429)
        await media.compress_with_compresto(b"foto")
        doc = await _doc(rig["db"], "compresto")
        assert doc["used"] == 100 and doc["ditahan_kode"] == 429
        assert not await media.is_quota_available("compresto")
        # Penahanan berakhir → layanan dicoba lagi (tanpa membuang kuotanya).
        await rig["db"].compression_quotas.update_one(
            {"_id": doc["_id"]},
            {"$set": {"ditahan_sampai": datetime.now(timezone.utc) - timedelta(seconds=1)}})
        assert await media.is_quota_available("compresto")
    asyncio.run(run())


def test_uploadcare_ikut_aturan_yang_sama(rig):
    async def run():
        await _set_used(rig["db"], "uploadcare", 995)
        rig["handler"] = _jawab(429)
        assert await media.compress_with_uploadcare(b"foto") is None
        assert (await _doc(rig["db"], "uploadcare"))["used"] == 1000
    asyncio.run(run())


# ── Respons ambigu: penyedia mungkin sudah menagih ────────────────────────

@pytest.mark.parametrize("galat,dihitung", [
    (httpx.ReadTimeout("uji"), True),
    (httpx.RemoteProtocolError("uji"), True),
    (httpx.ConnectError("uji"), False),
    (httpx.ConnectTimeout("uji"), False),
])
def test_galat_transport_dihitung_hanya_bila_mungkin_ditagih(rig, galat, dihitung):
    async def run():
        async def h(request):
            raise galat
        rig["handler"] = h
        assert await media.compress_with_compresto(b"foto") is None
        doc = await _doc(rig["db"], "compresto")
        assert ((doc or {}).get("used", 0) == 1) is dihitung
    asyncio.run(run())


# ── Indikator mengikuti rantai ─────────────────────────────────────────────

def _endpoint_kuota(monkeypatch):
    async def tinify_habis():
        return {"used": 500, "remaining": 0, "limit": 500, "tersedia": False,
                "status": "kuota", "retry_at": None, "month": "x"}
    monkeypatch.setattr(media, "status_tinify", tinify_habis)
    return media.get_all_compression_quotas(_user={"username": "uji"})


@pytest.mark.parametrize("used,aktif", [(499, "uploadcare"), (100, "uploadcare")])
def test_indikator_beralih_ke_uploadcare_setelah_penolakan(rig, monkeypatch, used, aktif):
    async def run():
        await _set_used(rig["db"], "compresto", used)
        assert (await _endpoint_kuota(monkeypatch))["aktif"] == "compresto"
        rig["handler"] = _jawab(429)
        await media.compress_with_compresto(b"foto")
        hasil = await _endpoint_kuota(monkeypatch)
        assert hasil["aktif"] == aktif
        compresto = next(q for q in hasil["quotas"] if q["service"] == "compresto")
        assert compresto["status"] in ("kuota", "sementara") and compresto["alasan"]
        if used == 499:
            assert compresto["remaining"] == 0
    asyncio.run(run())


# ── Rantai: urutan & foto yang sudah optimal ───────────────────────────────

def _foto(size=(64, 48), kualitas=95):
    out = io.BytesIO()
    Image.new("RGB", size, (120, 60, 30)).save(out, format="JPEG", quality=kualitas)
    return out.getvalue()


def _rantai(monkeypatch, **fungsi):
    dipanggil = []
    for nama in ("tinify", "compresto", "uploadcare"):
        hasil = fungsi.get(nama)

        async def f(data, _nama=nama, _hasil=hasil):
            dipanggil.append(_nama)
            return _hasil(data) if callable(_hasil) else _hasil
        monkeypatch.setitem(media._FUNGSI_KOMPRESI, nama, f)
    return dipanggil


def test_hasil_tinify_tak_lebih_kecil_tidak_membakar_compresto(monkeypatch):
    foto = _foto()
    dipanggil = _rantai(monkeypatch, tinify=lambda d: d + b"\0" * 10,
                        compresto=lambda d: d[: len(d) // 2])
    b64 = base64.b64encode(foto).decode()
    data, metode, asal, akhir = asyncio.run(media.auto_compress_image(b64))
    assert dipanggil == ["tinify"]
    assert metode in ("pillow", "none") and akhir <= asal


def test_foto_optimal_tidak_dibengkakkan_pillow(monkeypatch):
    foto = _foto(kualitas=20)
    _rantai(monkeypatch, tinify=lambda d: d)
    monkeypatch.setattr(media, "compress_with_pillow", lambda d: d + b"\0" * 50)
    b64 = "data:image/jpeg;base64," + base64.b64encode(foto).decode()
    data, metode, asal, akhir = asyncio.run(media.auto_compress_image(b64))
    assert (data, metode, akhir) == (b64, "none", asal)


def test_tinify_gagal_tetap_jatuh_ke_compresto(monkeypatch):
    foto = _foto()
    dipanggil = _rantai(monkeypatch, tinify=None, compresto=lambda d: d[: len(d) // 2])
    _, metode, _, _ = asyncio.run(media.auto_compress_image(base64.b64encode(foto).decode()))
    assert dipanggil == ["tinify", "compresto"] and metode == "compresto"
