"""Anggaran Tinify dengan HTTP/Mongo tiruan: tidak pernah memakai API asli."""
import asyncio
import io
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import mongomock
import pytest
from PIL import Image

import tinify_service as ts


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    async def to_list(self, length):
        return list(self.cursor.limit(length))


class Collection:
    def __init__(self, coll):
        self.coll = coll

    async def find_one(self, *args, **kwargs):
        return self.coll.find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        return Cursor(self.coll.find(*args, **kwargs))

    async def update_one(self, *args, **kwargs):
        return self.coll.update_one(*args, **kwargs)

    async def find_one_and_update(self, *args, **kwargs):
        return self.coll.find_one_and_update(*args, **kwargs)


def gambar(fmt="JPEG", color="blue"):
    out = io.BytesIO()
    Image.new("RGB", (40, 30), color).save(out, format=fmt)
    return out.getvalue()


@pytest.fixture
def rig(monkeypatch):
    # Instans tiruan terisolasi per uji. Kunci hanya dummy, transport TIDAK
    # memiliki implementasi jaringan; semua permintaan dicatat di memori.
    database = mongomock.MongoClient(tz_aware=True).db
    monkeypatch.setattr(ts, "db", SimpleNamespace(
        tinify_budget=Collection(database.tinify_budget),
        compression_quotas=Collection(database.compression_quotas)))
    monkeypatch.setenv("TINIFY_API_KEY", "synthetic-key-for-mock-only")
    state = SimpleNamespace(now=datetime(2026, 10, 10, 12, tzinfo=timezone.utc),
                            count=0, calls=[], database=database, handler=None)
    monkeypatch.setattr(ts, "_now", lambda: state.now)

    async def handler(request):
        state.calls.append((request.method, str(request.url), request.content))
        if state.handler:
            answer = await state.handler(request)
            if answer is not None:
                return answer
        headers = {"compression-count": str(state.count)}
        if request.url.path == "/shrink" and not request.content:
            return httpx.Response(400, headers=headers, json={"error": "InputMissing"})
        if request.url.path == "/shrink":
            state.count += 1
            return httpx.Response(201, headers={"compression-count": str(state.count),
                                  "location": ts.API + "/output/example"}, json={})
        if request.method == "POST":
            assert json.loads(request.content) == {"convert": {"type": "image/webp"}}
            state.count += 1
        fmt = "WEBP" if request.method == "POST" or state.format == "WEBP" else "JPEG"
        return httpx.Response(200, headers={"compression-count": str(state.count)}, content=gambar(fmt))

    state.format = "JPEG"
    monkeypatch.setattr(ts, "_client", lambda key: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), auth=("api", key), follow_redirects=False))
    return state


def budget(rig):
    return rig.database.tinify_budget.find_one({"_id": "tinify:" + ts._bulan(rig.now)})


@pytest.mark.asyncio
@pytest.mark.parametrize("fmt,webp,cost", [("JPEG", False, 1), ("JPEG", True, 2),
                                         ("PNG", True, 2), ("WEBP", True, 1)])
async def test_biaya_operasi_bukan_jumlah_foto(rig, fmt, webp, cost):
    rig.format = fmt
    result = await ts.optimalkan(gambar(fmt), webp=webp)
    assert result.status == "ok" and result.data
    assert rig.count == budget(rig)["used"] == cost
    assert rig.calls[0][2] == b""  # rekonsiliasi tanpa foto sebelum kuota terpakai
    assert sum(m == "POST" and "/output/" in u for m, u, _ in rig.calls) == (cost == 2)


@pytest.mark.asyncio
async def test_migrasi_legacy_duplikat_tidak_dihapus_dan_provider_jadi_acuan(rig):
    rig.database.compression_quotas.insert_many([
        {"service": "tinify", "month": "2026-10", "used": 100},
        {"service": "tinify", "month": "2026-10", "used": 120}])
    rig.count = 499
    result = await ts.optimalkan(gambar())
    assert result.status == "ok"
    assert budget(rig)["used"] == 500
    assert rig.database.compression_quotas.count_documents({}) == 2
    denied = await ts.optimalkan(gambar())
    assert denied.status == "kuota" and rig.count == 500


@pytest.mark.asyncio
async def test_legacy_lebih_tinggi_tidak_dinolkan(rig):
    rig.database.compression_quotas.insert_one({"service": "tinify", "month": "2026-10", "used": 500})
    assert (await ts.optimalkan(gambar())).status == "kuota"
    assert budget(rig)["used"] == 500 and rig.count == 0


@pytest.mark.asyncio
async def test_dua_pemanggil_terakhir_tidak_bisa_501(rig):
    rig.count = 499
    masuk, lanjut = asyncio.Event(), asyncio.Event()

    async def tahan(request):
        if request.url.path == "/shrink" and request.content:
            masuk.set()
            await lanjut.wait()

    rig.handler = tahan
    first = asyncio.create_task(ts.optimalkan(gambar()))
    await asyncio.wait_for(masuk.wait(), 2)
    second = await ts.optimalkan(gambar())
    assert second.status == "sementara"
    assert budget(rig)["used"] == 500  # dipesan SEBELUM foto dikirim
    lanjut.set()
    assert (await first).status == "ok"
    assert rig.count == 500


@pytest.mark.asyncio
async def test_convert_tidak_dimulai_bila_sisa_hanya_satu(rig):
    rig.count = 499
    assert (await ts.optimalkan(gambar(), webp=True)).status == "kuota"
    assert rig.count == 499 and len(rig.calls) == 1
    # Satu operasi masih dapat dipakai foto yang sudah WebP.
    rig.format = "WEBP"
    assert (await ts.optimalkan(gambar("WEBP"), webp=True)).status == "ok"
    assert rig.count == 500


@pytest.mark.asyncio
async def test_cadangan_tidak_memblokir_unggahan_dan_boleh_dilepas(rig):
    rig.count = 449
    result = await ts.optimalkan(gambar(), webp=True, cadangan=50)
    assert result.status == "kuota" and result.retry_at < ts._bulan_depan(rig.now)
    assert rig.count == 449
    assert (await ts.optimalkan(gambar(), webp=True, cadangan=0)).status == "ok"
    assert rig.count == 451


@pytest.mark.asyncio
async def test_shrink_berhasil_unduh_putus_tidak_memberi_refund(rig):
    rig.count = 498

    async def gagal(request):
        if "/output/" in request.url.path:
            raise httpx.ReadTimeout("synthetic timeout")

    rig.handler = gagal
    result = await ts.optimalkan(gambar(), webp=True)
    assert result.status == "sementara"
    assert rig.count == 499 and budget(rig)["used"] == 500
    rig.now += timedelta(minutes=6)
    # Rekonsiliasi resmi 499 tidak melepas operasi convert yang ambigu.
    assert (await ts.optimalkan(gambar())).status == "kuota"
    assert rig.count == 499 and budget(rig)["used"] == 500


@pytest.mark.asyncio
async def test_lease_kadaluwarsa_tidak_mengembalikan_anggaran(rig):
    rig.database.tinify_budget.insert_one({"_id": "tinify:2026-10", "month": "2026-10",
        "used": 500, "provider_used": 499, "lease": "worker-mati",
        "lease_until": rig.now - timedelta(seconds=1)})
    rig.count = 499
    assert (await ts.optimalkan(gambar())).status == "kuota"
    assert budget(rig)["used"] == 500 and rig.count == 499


@pytest.mark.asyncio
async def test_lease_hilang_sebelum_reservasi_bukan_kuota_habis(rig):
    async def ganti(request):
        rig.database.tinify_budget.update_one({"_id": "tinify:2026-10"}, {
            "$set": {"lease": "worker-baru"}})
    rig.handler = ganti
    result = await ts.optimalkan(gambar())
    assert result.status == "sementara"
    assert budget(rig)["used"] == 0 and budget(rig)["lease"] == "worker-baru"
    assert len(rig.calls) == 1


@pytest.mark.asyncio
async def test_worker_usang_tidak_convert_atau_menghapus_lease_baru(rig):
    async def ganti(request):
        if request.content:
            rig.database.tinify_budget.update_one({"_id": "tinify:2026-10"}, {
                "$set": {"lease": "worker-baru", "status": "kuota"}})
    rig.handler = ganti
    result = await ts.optimalkan(gambar(), webp=True)
    assert result.status == "sementara" and len(rig.calls) == 2
    assert rig.count == 1 and budget(rig)["used"] == 2
    assert budget(rig)["lease"] == "worker-baru" and budget(rig)["status"] == "kuota"


@pytest.mark.asyncio
async def test_bulan_baru_punya_anggaran_baru_dan_tetap_rekonsiliasi(rig):
    rig.database.tinify_budget.insert_one({"_id": "tinify:2026-09", "month": "2026-09", "used": 500})
    rig.now = datetime(2026, 10, 1, 0, 1, tzinfo=timezone.utc)
    rig.count = 7
    assert (await ts.optimalkan(gambar())).status == "ok"
    assert budget(rig)["used"] == 8
    assert rig.database.tinify_budget.find_one({"_id": "tinify:2026-09"})["used"] == 500


@pytest.mark.asyncio
async def test_tidak_memulai_biaya_dekat_pergantian_bulan(rig):
    rig.now = datetime(2026, 10, 31, 23, 59, 40, tzinfo=timezone.utc)
    result = await ts.optimalkan(gambar())
    assert result.status == "sementara" and not rig.calls
    assert result.retry_at == datetime(2026, 11, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
@pytest.mark.parametrize("code,count,status", [(401, 0, "tidak_tersedia"), (429, 10, "sementara"),
                                               (429, 500, "kuota"), (503, 10, "sementara")])
async def test_gagal_layanan_bukan_gambar_rusak(rig, code, count, status):
    async def gagal(request):
        return httpx.Response(code, headers={"compression-count": str(count)})
    rig.handler = gagal
    result = await ts.optimalkan(gambar())
    assert result.status == status and result.retry_at
    assert len(rig.calls) == 1 and rig.calls[0][2] == b""


@pytest.mark.asyncio
async def test_tanpa_counter_resmi_fail_closed_bukan_kuota_gratis(rig):
    async def hilang(request):
        return httpx.Response(400)
    rig.handler = hilang
    assert (await ts.optimalkan(gambar())).status == "sementara"
    assert rig.count == 0 and len(rig.calls) == 1


@pytest.mark.asyncio
async def test_input_rusak_tanpa_api_dan_tanpa_anggaran(rig):
    assert (await ts.optimalkan(b"not-image")).status == "input_rusak"
    assert not rig.calls and budget(rig) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://evil.test/output/abc", "http://api.tinify.com/output/abc",
                                  "https://api.tinify.com.evil.test/output/abc", "https://user:pass@api.tinify.com/output/abc",
                                  "https://api.tinify.com:444/output/abc", "https://api.tinify.com/output/abc?next=evil"])
async def test_output_origin_divalidasi_sebelum_auth_dikirim(rig, url):
    async def salah(request):
        if request.content:
            return httpx.Response(201, headers={"location": url, "compression-count": "1"})
    rig.handler = salah
    assert (await ts.optimalkan(gambar())).status == "sementara"
    assert len(rig.calls) == 2 and all(u.startswith(ts.API) for _, u, _ in rig.calls)
    assert budget(rig)["used"] == 1


@pytest.mark.asyncio
async def test_redirect_tidak_diikuti(rig):
    async def redirect(request):
        if "/output/" in request.url.path:
            return httpx.Response(302, headers={"location": "https://evil.test/photo"})
    rig.handler = redirect
    assert (await ts.optimalkan(gambar())).status == "sementara"
    assert len(rig.calls) == 3


@pytest.mark.asyncio
async def test_status_async_dan_cache_mencegah_probe_tiap_poll(rig):
    masuk, lanjut = asyncio.Event(), asyncio.Event()
    async def tahan(request):
        masuk.set()
        await lanjut.wait()
    rig.handler = tahan
    task = asyncio.create_task(ts.status_kuota())
    await asyncio.wait_for(masuk.wait(), 2)
    await asyncio.sleep(0)  # event loop masih hidup ketika status menunggu HTTP
    lanjut.set()
    state = await task
    assert state["used"] == 0 and state["remaining"] == 500 and state["tersedia"]
    assert (await ts.status_kuota())["used"] == 0
    assert len(rig.calls) == 1


@pytest.mark.asyncio
async def test_timeout_total_menjaga_reservasi_dan_melepas_lease(rig, monkeypatch):
    monkeypatch.setattr(ts, "TOTAL_DETIK", .03)
    async def lambat(request):
        if request.content:
            await asyncio.sleep(1)
    rig.handler = lambat
    assert (await ts.optimalkan(gambar())).status == "sementara"
    doc = budget(rig)
    assert doc["used"] == 1 and "lease" not in doc


@pytest.mark.asyncio
async def test_pembatalan_tidak_melepas_anggaran_dan_tidak_ditelan(rig):
    masuk = asyncio.Event()
    async def lambat(request):
        if request.content:
            masuk.set()
            await asyncio.sleep(2)
    rig.handler = lambat
    task = asyncio.create_task(ts.optimalkan(gambar(), webp=True))
    await asyncio.wait_for(masuk.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert budget(rig)["used"] == 2 and "lease" not in budget(rig)


@pytest.mark.asyncio
async def test_respons_terlalu_besar_dibatasi_tanpa_refund(rig, monkeypatch):
    monkeypatch.setattr(ts, "MAKS_BITA", 1024)
    async def besar(request):
        if "/output/" in request.url.path:
            return httpx.Response(200, content=b"x" * 1025)
    rig.handler = besar
    assert (await ts.optimalkan(gambar())).status == "sementara"
    assert budget(rig)["used"] == 1


@pytest.mark.asyncio
async def test_tanpa_kunci_tidak_mengaku_500_tersedia(rig, monkeypatch):
    monkeypatch.delenv("TINIFY_API_KEY")
    q = await ts.status_kuota()
    assert q["used"] is None and q["remaining"] == 0
    assert not q["tersedia"] and q["status"] == "tidak_tersedia"
    assert not rig.calls and budget(rig) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("code,status", [(503, "sementara"), (401, "tidak_tersedia")])
async def test_probe_pertama_gagal_bukan_bukti_sisa_500(rig, code, status):
    async def gagal(request):
        return httpx.Response(code)  # tidak ada counter provider terverifikasi
    rig.handler = gagal
    q = await ts.status_kuota()
    assert q["used"] is None and q["remaining"] == 0
    assert not q["tersedia"] and q["status"] == status
    assert budget(rig)["used"] == 0 and not budget(rig)["initialized"]
    # Respons cached saat masa tahan pun tidak mengubah unknown menjadi nol.
    cached = await ts.status_kuota()
    assert cached["used"] is None and cached["remaining"] == 0
    assert len(rig.calls) == 1


@pytest.mark.asyncio
async def test_probe_gagal_setelah_terverifikasi_mempertahankan_counter_dan_reservasi(rig):
    rig.count = 400
    first = await ts.status_kuota()
    assert first["used"] == 400 and first["tersedia"]
    rig.database.tinify_budget.update_one({"_id": "tinify:2026-10"}, {"$inc": {"used": 2}})
    rig.now += timedelta(minutes=6)
    async def gagal(request):
        return httpx.Response(503)
    rig.handler = gagal
    q = await ts.status_kuota()
    assert q["used"] == 402 and q["remaining"] == 98
    assert q["provider_used"] == 400 and not q["tersedia"] and q["status"] == "sementara"
    assert budget(rig)["used"] == 402 and budget(rig)["initialized"]


@pytest.mark.asyncio
async def test_counter_respons_bulan_lain_tidak_dicampur(rig):
    async def usang(request):
        return httpx.Response(400, headers={"compression-count": "499", "date": "Wed, 30 Sep 2026 23:59:59 GMT"})
    rig.handler = usang
    assert (await ts.optimalkan(gambar())).status == "sementara"
    assert budget(rig)["used"] == 0


@pytest.mark.asyncio
async def test_endpoint_lama_memakai_status_bersama_tanpa_sdk_sync(monkeypatch):
    from routes import media
    async def status():
        return {"used": 450, "remaining": 50, "limit": 500, "month": "2026-10",
                "tersedia": False, "status": "sementara"}
    async def quota(service):
        return {"used": 0}
    monkeypatch.setattr(media, "status_tinify", status)
    monkeypatch.setattr(media, "get_quota", quota)
    out = await media.get_all_compression_quotas({})
    assert out["quotas"][0]["used"] == 450
    assert out["aktif"] != "tinify"
    stats = await media.get_compression_stats({})
    assert stats["compressions_this_month"] == 450 and not stats["tinify_available"]


def test_progres_kompresi_hanya_admin_utama():
    from auth_utils import require_super_admin
    from routes.media import media_router
    route = next(r for r in media_router.routes if r.path == "/photo-compression-progress")
    assert route.methods == {"GET"}
    assert any(d.call is require_super_admin for d in route.dependant.dependencies)
