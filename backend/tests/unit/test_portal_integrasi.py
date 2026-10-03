"""Batas portal: transport pribadi dan arsip data tanpa kredensial."""
import pytest
from fastapi import FastAPI, Request, HTTPException
from httpx import ASGITransport, AsyncClient

from backup_utils import collections_from_backup, collections_to_process
from portal_middleware import PortalPemegangMiddleware


@pytest.mark.asyncio
async def test_respons_portal_berhasil_dan_gagal_tidak_boleh_dicache():
    app = FastAPI()
    app.add_middleware(PortalPemegangMiddleware)

    @app.get("/api/portal-pemegang/sesi")
    async def sesi():
        raise HTTPException(401, "Sesi berakhir")

    @app.post("/api/portal-pemegang/laporan")
    async def laporan(request: Request):
        return await request.json()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        gagal = await client.get("/api/portal-pemegang/sesi")
        berhasil = await client.post("/api/portal-pemegang/laporan", json={"catatan": "utuh"})
        assert gagal.status_code == 401
        assert berhasil.json() == {"catatan": "utuh"}
        for response in (gagal, berhasil):
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["referrer-policy"] == "no-referrer"
            assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_payload_chunked_dibatasi_sebelum_parser_dan_tidak_mengubah_api_lain(monkeypatch):
    monkeypatch.setattr(PortalPemegangMiddleware, "MAX_BODY", 10)
    app = FastAPI()
    app.add_middleware(PortalPemegangMiddleware)
    dipanggil = []

    @app.post("/{path:path}")
    async def echo(request: Request, path: str):
        dipanggil.append(path)
        return {"ukuran": len(await request.body())}

    async def chunks():
        yield b"123456"
        yield b"789012"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        besar = await client.post("/api/portal-pemegang/laporan", content=chunks())
        assert besar.status_code == 413
        assert besar.headers["cache-control"] == "private, no-store"
        assert not dipanggil
        biasa = await client.post("/api/assets", content=b"123456789012")
        assert biasa.status_code == 200 and biasa.json()["ukuran"] == 12
        assert "cache-control" not in biasa.headers


def test_arsip_menyimpan_riwayat_portal_bukan_token_dan_sesi():
    permanen = ["portal_penugasan", "portal_laporan", "portal_pemegang_akses"]
    transien = ["portal_pemegang_tokens", "portal_pemegang_sesi", "portal_pemegang_batas"]
    assert collections_to_process(permanen + transien) == sorted(permanen)
    assert collections_from_backup([f"{name}.json" for name in permanen + transien]) == sorted(permanen)


def test_timeline_tidak_mengubah_laporan_menjadi_fakta_akuntansi():
    from timeline_utils import event_portal_laporan, LABEL_STATUS, MODUL_LABEL
    doc = {"id": "r1", "jenis": "kehilangan", "pegawai_nama": "Pemegang Uji",
           "kondisi": "Tidak diketahui", "status": "terverifikasi", "created_at": "2026-10-03T01:00:00Z",
           "bukti": [{"data_base64": "JANGAN_KIRIM_BLOB"}],
           "tinjauan": [{"tanggal": "2026-10-03T02:00:00Z", "keputusan": "terverifikasi",
                         "catatan": "Perlu penelusuran lebih lanjut", "oleh": "operator"}]}
    events = event_portal_laporan(doc)
    assert len(events) == 2
    assert events[0]["status"] == "diajukan"  # riwayat pengajuan tidak diretcon
    assert events[1]["status"] == "terverifikasi"
    assert "Bukan perubahan master atau jurnal akuntansi" in events[0]["detail"]
    assert "Tidak mengubah catatan resmi BMN" in events[1]["detail"]
    assert "JANGAN_KIRIM_BLOB" not in str(events)
    assert all(e["modul"] in MODUL_LABEL and e["status"] in LABEL_STATUS for e in events)
