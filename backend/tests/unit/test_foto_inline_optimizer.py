"""Foto inline: bytes sintetis, Mongo tiruan, dan Tinify sepenuhnya dimock."""
import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient
from PIL import Image

import foto_inline_optimizer as fio
from tinify_service import HasilTinify


def _jalan(coro):
    return asyncio.run(coro)


def _foto(color=(70, 90, 120), size=(48, 36), fmt="JPEG"):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, format=fmt)
    return stream.getvalue()


def _uri(data):
    with Image.open(io.BytesIO(data)) as image:
        mime = "image/webp" if image.format == "WEBP" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _webp(data):
    stream = io.BytesIO()
    with Image.open(io.BytesIO(data)) as image:
        image.save(stream, format="WEBP", lossless=True)
    return stream.getvalue()


@pytest.fixture
def lingkungan(monkeypatch):
    database = AsyncMongoMockClient()["foto_inline_unit"]
    calls = []
    now = [datetime(2026, 10, 1, 5, tzinfo=timezone.utc)]

    async def kompres(data, **kwargs):
        calls.append((data, kwargs))
        return HasilTinify(data=_webp(data), status="ok")

    monkeypatch.setattr(fio, "db", database)
    monkeypatch.setattr(fio, "optimalkan", kompres)
    monkeypatch.setattr(fio, "_sekarang", lambda: now[0])
    return database, calls, now


def test_allowlist_hanya_foto_bukan_dokumen_ttd_logo_denah():
    owner = {"photos": ["utama"], "photo": "legacy",
             "document_checklist": [{"photos": ["perlengkapan"],
                                      "documents": [{"data": "jangan"}]}],
             "signature": "jangan", "logo": "jangan", "denah": "jangan"}
    assert [x[0] for x in fio._slot_foto(owner, "assets")] == [
        "photos.0", "photo", "document_checklist.0.photos.0"]
    assert [x[0] for x in fio._slot_foto(owner, "inventory_activities")] == ["photos.0"]


def test_foto_aset_diganti_tanpa_mengubah_urutan_cover_thumbnail(lingkungan):
    database, calls, clock = lingkungan
    source, second = _uri(_foto()), _uri(_foto((30, 40, 50)))

    async def run():
        await database.assets.insert_one({"id": "a", "version": 7,
            "photos": [source, second], "photo_thumbnails": ["thumb1", "thumb2"],
            "thumbnail": "cover", "gallery_thumbnail": "galeri", "thumbnail_index": 1,
            "updated_at": "lama", "asset_name": "jangan_masuk_ledger"})
        assert await fio.proses_satu(cadangan=50) == "sukses"
        owner = await database.assets.find_one({"id": "a"})
        assert owner["version"] == 8
        assert owner["photos"] == [_uri(_webp(_foto())), second]
        assert owner["photo_thumbnails"] == ["thumb1", "thumb2"]
        assert (owner["thumbnail"], owner["gallery_thumbnail"], owner["thumbnail_index"]) == ("cover", "galeri", 1)
        assert owner["updated_at"] == clock[0].isoformat()
        ledger = await database.foto_kompresi_status.find({}).to_list(None)
        assert "jangan_masuk_ledger" not in str(ledger)
        assert source not in str(ledger) and "data:image" not in str(ledger)

    _jalan(run())
    assert calls[0][1] == {"webp": True, "cadangan": 50}


def test_checklist_diganti_hanya_satu_slot_dokumen_dan_info_tetap(lingkungan):
    database, _, _ = lingkungan
    source = _uri(_foto())

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1,
            "document_checklist": [
                {"name": "pengisi_daya", "checked": True, "notes": "catatan",
                 "photos": [source], "photo_thumbnails": ["thumb"],
                 "documents": [{"data": "dokumen_tidak_diubah"}]},
                {"name": "manual", "photos": []}]})
        assert await fio.proses_satu() == "sukses"
        owner = await database.assets.find_one({"id": "a"})
        assert owner["version"] == 2
        item = owner["document_checklist"][0]
        assert item["photos"] == [_uri(_webp(_foto()))]
        assert item["photo_thumbnails"] == ["thumb"]
        assert item["documents"] == [{"data": "dokumen_tidak_diubah"}]
        assert (item["name"], item["notes"], item["checked"]) == ("pengisi_daya", "catatan", True)
        assert owner["document_checklist"][1] == {"name": "manual", "photos": []}

    _jalan(run())


@pytest.mark.parametrize("version", [None, "hilang"])
def test_photo_legacy_tetap_inline_dan_versi_dibuat(lingkungan, version):
    database, _, _ = lingkungan

    async def run():
        owner = {"id": "a", "photo": _uri(_foto())}
        if version != "hilang":
            owner["version"] = version
        await database.assets.insert_one(owner)
        assert await fio.proses_satu() == "sukses"
        owner = await database.assets.find_one({"id": "a"})
        assert owner["photo"].startswith("data:image/webp;base64,")
        assert owner["version"] == 1
        assert "photo_gridfs_ids" not in owner

    _jalan(run())


@pytest.mark.parametrize("version", [None, 3])
def test_foto_kegiatan_tidak_menciptakan_kontrak_versi_baru(lingkungan, version):
    database, _, _ = lingkungan

    async def run():
        owner = {"id": "k", "photos": [_uri(_foto())], "photo_thumbnails": ["thumb"]}
        if version is not None:
            owner["version"] = version
        await database.inventory_activities.insert_one(owner)
        assert await fio.proses_satu() == "sukses"
        owner = await database.inventory_activities.find_one({"id": "k"})
        assert owner["photo_thumbnails"] == ["thumb"]
        assert owner["photos"][0].startswith("data:image/webp;base64,")
        assert owner.get("version") == (4 if version is not None else None)

    _jalan(run())


def test_di_bawah_satu_persen_plateau_sumber_dipertahankan_dan_hash_dipakai_bersama(lingkungan):
    database, calls, _ = lingkungan
    source = _uri(_webp(_foto()))

    async def run():
        await database.assets.insert_many([
            {"id": "a", "version": 1, "photos": [source]},
            {"id": "b", "version": 1, "photos": [source]}])
        assert await fio.proses_satu() == "hemat_tipis"
        for _ in range(4):
            await fio.proses_satu()
        assert len(calls) == 1
        owners = await database.assets.find({}).to_list(None)
        assert all(a["photos"] == [source] and a["version"] == 1 for a in owners)
        state = await database.foto_kompresi_status.find_one({})
        assert state["status"] == "plateau"
        assert state["last_savings_percent"] == 0
        assert "processing_token" not in state

    _jalan(run())


@pytest.mark.parametrize("saving,expected", [(0.99, "hemat_tipis"), (1.0, "sukses"), (-2, "hemat_tipis")])
def test_ambang_satu_persen_inklusif(lingkungan, monkeypatch, saving, expected):
    database, _, _ = lingkungan
    monkeypatch.setattr(fio, "hemat_persen", lambda *args: saving)

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [_uri(_foto())]})
        assert await fio.proses_satu() == expected
        owner = await database.assets.find_one({"id": "a"})
        assert owner["version"] == (2 if saving >= 1 else 1)

    _jalan(run())


@pytest.mark.parametrize("output", [b"bukan_foto", _foto(), _webp(_foto(size=(8, 8))), _webp(_foto((255, 255, 255)))])
def test_hasil_rusak_berbeda_format_dimensi_atau_detail_ditolak(lingkungan, monkeypatch, output):
    database, _, _ = lingkungan
    source = _uri(_foto())

    async def bad(*args, **kwargs):
        return HasilTinify(data=output, status="ok")

    monkeypatch.setattr(fio, "optimalkan", bad)

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [source]})
        assert await fio.proses_satu() == "manual_review"
        assert (await database.assets.find_one({"id": "a"}))["photos"] == [source]
        assert (await database.foto_kompresi_status.find_one({}))["status"] == "manual_review"

    _jalan(run())


@pytest.mark.parametrize("source", ["data:image/jpeg;base64,%%%", "data:image/jpeg;base64," + base64.b64encode(b"sampah").decode()])
def test_sumber_rusak_tidak_dikirim_ke_penyedia(lingkungan, source):
    database, calls, _ = lingkungan

    async def run():
        await database.assets.insert_one({"id": "a", "photos": [source]})
        assert await fio.proses_satu() == "rusak"
        assert (await database.foto_kompresi_status.find_one({}))["status"] == "corrupt"

    _jalan(run())
    assert not calls


def test_svg_dokumen_atau_url_salah_field_tidak_dikirim(lingkungan):
    database, calls, _ = lingkungan

    async def run():
        await database.assets.insert_one({"id": "a", "photos": [
            "data:image/svg+xml;base64,PHN2Zy8+", "data:application/pdf;base64,JVBERg==",
            "https://tidak-dikunjungi.invalid/photo", "__existing__:0"]})
        assert await fio.proses_satu() is None
        assert await database.foto_kompresi_status.count_documents({}) == 0

    _jalan(run())
    assert not calls


@pytest.mark.parametrize("fmt", ["GIF", "BMP", "presisi_16_bit"])
def test_format_atau_presisi_tidak_didukung_ditinjau_tanpa_bakar_kuota(lingkungan, fmt):
    database, calls, _ = lingkungan
    stream = io.BytesIO()
    if fmt == "presisi_16_bit":
        Image.new("I;16", (40, 30), 31000).save(stream, format="PNG")
        data = stream.getvalue()
    else:
        data = _foto(fmt=fmt)

    async def run():
        # Sniff bytes tetap wajib, tidak percaya MIME yang dipasang klien.
        source = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        await database.assets.insert_one({"id": "a", "photos": [source]})
        assert await fio.proses_satu() == "manual_review"
        assert (await database.assets.find_one({"id": "a"}))["photos"] == [source]

    _jalan(run())
    assert not calls


def test_transparansi_hasil_berubah_sumber_dipertahankan(lingkungan, monkeypatch):
    database, _, _ = lingkungan
    stream = io.BytesIO()
    Image.new("RGBA", (48, 36), (70, 90, 120, 100)).save(stream, format="PNG")
    source = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")

    async def alfa_hilang(*args, **kwargs):
        return HasilTinify(data=_webp(_foto()), status="ok")

    monkeypatch.setattr(fio, "optimalkan", alfa_hilang)

    async def run():
        await database.assets.insert_one({"id": "a", "photos": [source]})
        assert await fio.proses_satu() == "manual_review"
        assert (await database.assets.find_one({"id": "a"}))["photos"] == [source]

    _jalan(run())


def test_foto_avif_inline_diproses_bukan_dilewati_senyap(lingkungan):
    database, calls, _ = lingkungan
    original = _foto(fmt="AVIF")
    source = "data:image/avif;base64," + base64.b64encode(original).decode("ascii")

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [source]})
        assert await fio.proses_satu() == "sukses"
        owner = await database.assets.find_one({"id": "a"})
        assert owner["photos"][0].startswith("data:image/webp;base64,")
        assert calls[0][0] == original

    _jalan(run())


def test_pembatalan_worker_tidak_mengubah_foto(lingkungan, monkeypatch):
    database, _, _ = lingkungan

    async def dibatalkan(*args, **kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(fio, "optimalkan", dibatalkan)

    async def run():
        source = _uri(_foto())
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [source]})
        with pytest.raises(asyncio.CancelledError):
            await fio.proses_satu()
        owner = await database.assets.find_one({"id": "a"})
        assert owner["photos"] == [source] and owner["version"] == 1
        state = await database.foto_kompresi_status.find_one({})
        assert state["status"] == "pending" and state["busy_until"]

    _jalan(run())


@pytest.mark.parametrize("status", ["kuota", "sementara", "tidak_tersedia"])
def test_kuota_gangguan_dan_kunci_tidak_mengunci_foto_permanen(lingkungan, monkeypatch, status):
    database, _, clock = lingkungan
    calls = []

    async def provider(data, **kwargs):
        calls.append(data)
        if len(calls) == 1:
            return HasilTinify(status=status, retry_at=clock[0] + timedelta(hours=1))
        return HasilTinify(data=_webp(data), status="ok")

    monkeypatch.setattr(fio, "optimalkan", provider)

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [_uri(_foto())]})
        assert await fio.proses_satu() == ("kuota" if status == "kuota" else "sementara")
        assert (await database.foto_kompresi_status.find_one({}))["status"] == "retry"
        for _ in range(4):
            await fio.proses_satu()
        assert len(calls) == 1
        clock[0] += timedelta(hours=2)
        assert await fio.proses_satu() == "sukses"
        assert len(calls) == 2

    _jalan(run())


def test_exception_penyedia_retry_bukan_plateau(lingkungan, monkeypatch):
    database, _, _ = lingkungan

    async def gagal(*args, **kwargs):
        raise TimeoutError("pesan_tidak_disalin_ke_ledger")

    monkeypatch.setattr(fio, "optimalkan", gagal)

    async def run():
        await database.assets.insert_one({"id": "a", "photos": [_uri(_foto())]})
        assert await fio.proses_satu() == "sementara"
        state = await database.foto_kompresi_status.find_one({})
        assert state["status"] == "retry" and state["retry_at"]
        assert "pesan_tidak_disalin" not in str(state)

    _jalan(run())


@pytest.mark.parametrize("collection", ["assets", "inventory_activities"])
def test_hasil_terlambat_tidak_menimpa_edit_foto_pengguna(lingkungan, monkeypatch, collection):
    database, _, _ = lingkungan
    source = _uri(_foto())
    changed = _uri(_foto((10, 20, 30)))

    async def edit_saat_tinify(data, **kwargs):
        update = {"$set": {"photos": [changed]}}
        if collection == "assets":
            update["$inc"] = {"version": 1}
        await database[collection].update_one({"id": "a"}, update)
        return HasilTinify(data=_webp(data), status="ok")

    monkeypatch.setattr(fio, "optimalkan", edit_saat_tinify)

    async def run():
        owner = {"id": "a", "photos": [source]}
        if collection == "assets":
            owner["version"] = 1
        await database[collection].insert_one(owner)
        assert await fio.proses_satu() == "berubah"
        assert (await database[collection].find_one({"id": "a"}))["photos"] == [changed]

    _jalan(run())


def test_versi_berubah_tanpa_edit_foto_juga_menolak_hasil_basi(lingkungan, monkeypatch):
    database, _, _ = lingkungan

    async def edit(data, **kwargs):
        await database.assets.update_one({"id": "a"}, {"$inc": {"version": 1}})
        return HasilTinify(data=_webp(data), status="ok")

    monkeypatch.setattr(fio, "optimalkan", edit)

    async def run():
        source = _uri(_foto())
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [source]})
        assert await fio.proses_satu() == "berubah"
        assert (await database.assets.find_one({"id": "a"}))["photos"] == [source]

    _jalan(run())


@pytest.mark.parametrize("lost_at", [1, 2])
def test_lease_hilang_sebelum_api_atau_cas_tidak_mengubah_sumber(lingkungan, lost_at):
    database, calls, _ = lingkungan
    checks = []

    async def berwenang():
        checks.append(True)
        return len(checks) < lost_at

    async def run():
        source = _uri(_foto())
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [source]})
        assert await fio.proses_satu(masih_berwenang=berwenang) == "berubah"
        assert (await database.assets.find_one({"id": "a"}))["photos"] == [source]

    _jalan(run())
    assert len(calls) == lost_at - 1


def test_kursor_memberi_giliran_sumber_dan_slot_berikutnya(lingkungan):
    database, calls, _ = lingkungan
    a, b, kegiatan = _foto(), _foto((10, 20, 30)), _foto((5, 70, 90))

    async def run():
        await database.assets.insert_one({"id": "a", "version": 1, "photos": [_uri(a), _uri(b)]})
        await database.inventory_activities.insert_one({"id": "k", "photos": [_uri(kegiatan)]})
        assert await fio.proses_satu() == "sukses"
        assert await fio.proses_satu() == "sukses"
        assert await fio.proses_satu() == "sukses"

    _jalan(run())
    assert [c[0] for c in calls] == [a, kegiatan, b]


def test_cursor_bounded_melampaui_banyak_foto_terminal_dan_memutar_ke_foto_baru(lingkungan, monkeypatch):
    database, calls, _ = lingkungan
    monkeypatch.setattr(fio, "BATAS_PEMILIK", 3)
    finished, pending = _uri(_webp(_foto())), _uri(_foto((10, 20, 30)))

    async def run():
        _, digest, _ = fio._decode(finished)
        await database.foto_kompresi_status.insert_one({"_id": digest, "status": "plateau"})
        await database.assets.insert_many([
            {"id": f"a{i}", "version": 1, "photos": [finished]} for i in range(8)])
        await database.assets.insert_one({"id": "z", "version": 1, "photos": [pending]})
        assert await fio.proses_satu() == "lewat"
        assert not calls
        for _ in range(8):
            if await fio.proses_satu() == "sukses":
                break
        assert len(calls) == 1
        # Tambahan dengan id sebelum cursor tidak hilang dari sapuan selanjutnya.
        await database.assets.insert_one({"id": "0baru", "photos": [_uri(_foto((60, 80, 99)))]})
        for _ in range(10):
            if await fio.proses_satu() == "sukses":
                break
        assert len(calls) >= 2
        assert (await database.assets.find_one({"id": "0baru"}))["photos"][0].startswith("data:image/webp")

    _jalan(run())


def test_batas_slot_tidak_melewatkan_slot_berikutnya(lingkungan, monkeypatch):
    database, calls, _ = lingkungan
    monkeypatch.setattr(fio, "BATAS_SLOT", 2)
    finished = _uri(_webp(_foto()))

    async def run():
        _, digest, _ = fio._decode(finished)
        await database.foto_kompresi_status.insert_one({"_id": digest, "status": "plateau"})
        await database.assets.insert_one({"id": "a", "photos": [finished] * 4 + [_uri(_foto((10, 20, 30)))]})
        assert await fio.proses_satu() == "lewat"
        assert await fio.proses_satu() == "lewat"
        assert await fio.proses_satu() == "sukses"
        assert len(calls) == 1

    _jalan(run())


def test_ledger_crash_lease_kadaluarsa_bisa_dicoba_lagi(lingkungan):
    database, calls, clock = lingkungan
    source = _uri(_foto())

    async def run():
        _, key, _ = fio._decode(source)
        await database.assets.insert_one({"id": "a", "photos": [source]})
        await database.foto_kompresi_status.insert_one({
            "_id": key, "status": "pending", "processing_token": "worker_mati",
            "busy_until": clock[0] + timedelta(minutes=10)})
        assert await fio.proses_satu() is None
        assert not calls
        clock[0] += timedelta(minutes=11)
        assert await fio.proses_satu() == "sukses"

    _jalan(run())


def test_lineage_baseline_dan_jumlah_putaran_tidak_hilang(lingkungan):
    database, _, _ = lingkungan
    original = _foto()

    async def run():
        await database.assets.insert_one({"id": "a", "photos": [_uri(original)]})
        assert await fio.proses_satu() == "sukses"
        assert await fio.proses_satu() == "lewat"
        assert await fio.proses_satu() == "hemat_tipis"
        result = _webp(original)
        _, key, _ = fio._decode(_uri(result))
        state = await database.foto_kompresi_status.find_one({"_id": key})
        assert state["baseline_bytes"] == len(original)
        assert state["current_bytes"] == len(result)
        assert state["pass_count"] == 1
        assert state["attempt_count"] == 1
        assert state["status"] == "plateau"

    _jalan(run())
