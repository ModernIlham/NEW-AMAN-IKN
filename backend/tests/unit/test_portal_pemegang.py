"""Kontrak domain portal: isolasi, bukti asli, OCC, dan idempotensi.

Mongo tiruan; tidak ada akun, email, data produksi, atau jaringan.
"""
import asyncio
import base64
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from PIL import Image, ImageFile
from pydantic import ValidationError
from pymongo.errors import OperationFailure

import routes.portal_pemegang as rp
from portal_pemegang_utils import alias_identitas_aset, sidik_data, validasi_bukti


ADMIN = {"id": "u-admin", "username": "admin-uji", "role": "admin",
         "kode_satker": "001", "email": "admin@example.test"}
WRITER = {"id": "u-op", "username": "operator-uji", "role": "operator",
          "kode_satker": "001", "email": "operator@example.test"}
HOLDER = {"pegawai_id": "p1", "kode_satker": "001", "session_id": "s1"}


class Req:
    def __init__(self, key="idem-1", version=0):
        self.headers = {"Idempotency-Key": key, "If-Match": str(version)}


def run(coro):
    return asyncio.run(coro)


async def diam(*args, **kwargs):
    return None


@pytest.fixture
def basis(monkeypatch):
    fake = AsyncMongoMockClient()["uji_portal_domain"]
    monkeypatch.setattr(rp, "db", fake)
    monkeypatch.setattr(rp, "log_audit", diam)
    return fake


async def seed(db):
    await db.inventory_activities.insert_many([
        {"id": "act1", "kode_satker": "001"},
        {"id": "act2", "kode_satker": "001"},
        {"id": "act3", "kode_satker": "002"},
    ])
    await db.pegawai.insert_many([
        {"id": "p1", "nama": "Pemegang Satu", "nip": "123456789",
         "email": "pemegang@example.test", "kode_satker": "001", "status": "aktif"},
        {"id": "p2", "nama": "Pemegang Dua", "nip": "987654321",
         "email": "dua@example.test", "kode_satker": "001", "status": "aktif"},
        {"id": "p3", "nama": "Pegawai Lain", "nip": "222222222",
         "email": "lain@example.test", "kode_satker": "002", "status": "aktif"},
    ])
    await db.assets.insert_one({
        "id": "as1", "activity_id": "act1", "asset_code": "3050104001",
        "NUP": "1", "asset_name": "Laptop", "user": "Pemegang Satu",
        "pengguna_nip": "123456789", "condition": "Baik", "location": "Ruang A",
        "version": 7, "purchase_price": "15000000", "inventory_status": "Ditemukan",
    })


async def buat(db, *, accepted=False):
    await seed(db)
    before = await db.assets.find_one({"id": "as1"})
    result = await rp.buat_penugasan(rp.PenugasanIn(
        pegawai_id="p1", asset_id="as1", dasar_penugasan="BAST sah nomor 123 tahun 2026"),
        Req("map", 0), ADMIN)
    p = result["item"]
    if accepted:
        p = (await rp.konfirmasi_penugasan(p["id"], rp.KonfirmasiIn(
            version=1, keputusan="terima"), Req("terima", 1), HOLDER))["item"]
    assert await db.assets.find_one({"id": "as1"}) == before
    return p


def foto(fmt="PNG"):
    buf = io.BytesIO()
    Image.new("RGB", (20, 10), (52, 110, 150)).save(buf, format=fmt)
    raw = buf.getvalue()
    return {"nama": "bukti.png" if fmt == "PNG" else "bukti.jpg",
            "mime": "image/png" if fmt == "PNG" else "image/jpeg",
            "data_base64": base64.b64encode(raw).decode("ascii")}


def laporan(p, **kwargs):
    return rp.LaporanIn(**{
        "penugasan_id": p["id"], "penugasan_version": p["version"],
        "jenis": "berkala", "kondisi": "Baik", "status_operasional": "digunakan",
        "lokasi_laporan": "Ruang B", "catatan": "Barang diperiksa langsung",
        **kwargs,
    })


JENIS_UJI = ("berkala", "kerusakan", "kehilangan", "perbaikan", "pengembalian")


@pytest.mark.parametrize("jenis", JENIS_UJI)
@pytest.mark.parametrize("catatan", ["", "   ", "abcd", "abcde", "  abcde  "])
def test_catatan_kondisional_semua_jenis_batas_karakter(jenis, catatan):
    p = {"id": "penugasan-uji", "version": 2}
    if jenis != "berkala" and len(catatan.strip()) < 5:
        with pytest.raises(ValidationError, match="minimal 5 karakter"):
            laporan(p, jenis=jenis, catatan=catatan)
    else:
        assert laporan(p, jenis=jenis, catatan=catatan).catatan == catatan.strip()


@pytest.mark.parametrize("kondisi", ("Baik", "Rusak Ringan", "Rusak Berat", "Tidak diketahui"))
@pytest.mark.parametrize("status", ("digunakan", "tidak_digunakan", "diperbaiki", "tidak_diketahui"))
def test_berkala_non_normal_memerlukan_uraian(kondisi, status):
    p = {"id": "penugasan-uji", "version": 2}
    wajib = kondisi != "Baik" or status in ("diperbaiki", "tidak_diketahui")
    if wajib:
        with pytest.raises(ValidationError, match="minimal 5 karakter"):
            laporan(p, kondisi=kondisi, status_operasional=status, catatan="")
    else:
        assert laporan(p, kondisi=kondisi, status_operasional=status, catatan="").catatan == ""


@pytest.mark.parametrize("jenis", JENIS_UJI)
def test_klarifikasi_semua_jenis_tetap_wajib_uraian(jenis):
    p = {"id": "penugasan-uji", "version": 2}
    with pytest.raises(ValidationError, match="minimal 5 karakter"):
        laporan(p, jenis=jenis, catatan="", laporan_sebelumnya_id="laporan-lama")
    assert laporan(p, jenis=jenis, catatan="abcde", laporan_sebelumnya_id="laporan-lama").catatan == "abcde"


def test_berkala_normal_tanpa_field_catatan_dan_sidik_payload_lama_tetap():
    lama = {"penugasan_id": "penugasan-uji", "penugasan_version": 2,
            "jenis": "berkala", "kondisi": "Baik", "status_operasional": "digunakan",
            "lokasi_laporan": "Ruang B", "catatan": "Barang diperiksa langsung",
            "diambil_pada": None, "bukti": [], "laporan_sebelumnya_id": ""}
    model = rp.LaporanIn(**lama)
    assert model.model_dump() == lama
    assert rp._operasi(Req("lama", 2), HOLDER, "kirim_laporan", model, True)[1] == sidik_data({"payload": lama, "version": 2})
    tanpa = dict(lama)
    tanpa.pop("catatan")
    assert rp.LaporanIn(**tanpa).catatan == ""
    with pytest.raises(ValidationError):
        rp.LaporanIn(**{**lama, "catatan": "x" * 5001})


@pytest.mark.parametrize("keputusan", ("terverifikasi", "perlu_perbaikan", "ditolak"))
@pytest.mark.parametrize("catatan", ("", "   ", "abcd", "abcde"))
def test_catatan_peninjau_selalu_wajib(keputusan, catatan):
    if len(catatan.strip()) < 5:
        with pytest.raises(ValidationError):
            rp.TinjauIn(version=1, keputusan=keputusan, catatan=catatan)
    else:
        assert rp.TinjauIn(version=1, keputusan=keputusan, catatan=catatan).catatan == catatan


@pytest.mark.parametrize("jenis", JENIS_UJI)
@pytest.mark.parametrize("keputusan", ("terverifikasi", "perlu_perbaikan", "ditolak"))
def test_semua_jenis_kirim_tinjau_tanpa_mengubah_induk_amanah_dan_transaksi(basis, jenis, keputusan):
    async def scenario():
        p = await buat(basis, accepted=True)
        aset_awal = await basis.assets.find_one({"id": "as1"})
        amanah_awal = await basis.portal_penugasan.find_one({"id": p["id"]})
        catatan = "" if jenis == "berkala" else "abcde"
        # Kehilangan tetap bisa dilaporkan tanpa foto/GPS barang yang tidak ada.
        body = laporan(p, jenis=jenis, catatan=catatan, bukti=[])
        req = Req("laporan-jenis", p["version"])
        result = await rp.kirim_laporan(body, req, HOLDER)
        assert await rp.kirim_laporan(body, req, HOLDER) == result
        assert await basis.portal_laporan.count_documents({}) == 1
        rid = result["item"]["id"]
        assert result["item"]["catatan"] == catatan
        assert result["item"]["bukti"] == []
        assert bool(result["item"]["perlu_tindak_lanjut"]) == (jenis != "berkala")
        asli = await basis.portal_laporan.find_one({"id": rid})
        for daftar in (await rp.laporan_saya(HOLDER), await rp.daftar_laporan_admin("", 1, 30, ADMIN)):
            assert daftar["total"] == 1
            assert daftar["items"][0]["jenis"] == jenis
        review = rp.TinjauIn(version=1, keputusan=keputusan, catatan="Hasil pemeriksaan dicatat petugas")
        reviewed = await rp.tinjau_laporan(rid, review, Req("tinjau-jenis", 1), WRITER)
        assert await rp.tinjau_laporan(rid, review, Req("tinjau-jenis", 1), WRITER) == reviewed
        assert reviewed["item"]["status"] == keputusan
        assert reviewed["item"]["version"] == 2
        akhir = await basis.portal_laporan.find_one({"id": rid})
        for field in ("jenis", "kondisi", "status_operasional", "lokasi_laporan", "catatan", "bukti", "created_at", "sidik_laporan_asli"):
            assert akhir[field] == asli[field]
        assert await basis.assets.find_one({"id": "as1"}) == aset_awal
        assert await basis.portal_penugasan.find_one({"id": p["id"]}) == amanah_awal
        for collection in ("pemeliharaan", "tgr", "mutasi_bmn", "usulan_penghapusan", "bast", "jurnal"):
            assert await basis[collection].count_documents({}) == 0
    run(scenario())


def test_bukti_kamera_gps_tersimpan_tanpa_mengubah_aset_dan_retry_lama(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        before = await basis.assets.find_one({"id": "as1"})
        capture = {"waktu": "2026-10-03T10:00:00+08:00",
                   "gps": {"lat": -0.96, "lng": 116.7, "accuracy": 15}}
        body = laporan(p, bukti=[{**foto(), "pengambilan": capture}])
        req = Req("kamera-gps", 2)
        result = await rp.kirim_laporan(body, req, HOLDER)
        assert await rp.kirim_laporan(body, req, HOLDER) == result
        evidence = result["item"]["bukti"][0]
        assert evidence["pengambilan"]["waktu"] == "2026-10-03T02:00:00+00:00"
        assert evidence["pengambilan"]["gps"] == capture["gps"]
        assert "data_base64" not in evidence
        assert await basis.assets.find_one({"id": "as1"}) == before
        assert (await basis.portal_laporan.find_one({"id": result["item"]["id"]}))["bukti"][0]["data_base64"] == foto()["data_base64"]
        # Digest lama tetap sama walaupun model bukti mendapat field opsional.
        legacy = laporan(p, bukti=[foto()])
        old = legacy.model_dump()
        for b in old["bukti"]:
            b.pop("pengambilan", None)
        assert rp._operasi(req, HOLDER, "uji", legacy, True)[1] == sidik_data({"payload": old, "version": 2})
        other = laporan(p, bukti=[{**foto(), "pengambilan": {**capture, "gps": None}}])
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(other, req, HOLDER)
        assert err.value.status_code == 409
    run(scenario())


@pytest.mark.parametrize("gps", [
    {"lat": 91, "lng": 116}, {"lat": 1, "lng": -181},
    {"lat": float("nan"), "lng": 116}, {"lat": 1, "lng": 116, "accuracy": -1},
])
def test_koordinat_kamera_invalid_ditolak(gps):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        rp.BuktiIn(**foto(), pengambilan={"waktu": "2026-10-03T10:00:00Z", "gps": gps})


def test_kamera_tanpa_gps_dan_waktu_invalid():
    meta = {"waktu": "2026-10-03T10:00:00Z", "gps": None}
    assert validasi_bukti([{**foto(), "pengambilan": meta}])[0]["pengambilan"]["gps"] is None
    with pytest.raises(ValueError, match="zona waktu"):
        validasi_bukti([{**foto(), "pengambilan": {"waktu": "2026-10-03T10:00:00"}}])


def test_register_hanya_dari_aset_penugasan_aktif(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        assert "kode_register" in (await rp.aset_saya(HOLDER))["items"][0]
        assert (await rp.aset_saya({**HOLDER, "pegawai_id": "p2"}))["items"] == []
        assert p["asset_id"] == "as1"
    run(scenario())


def test_mapping_konfirmasi_idempotensi_dan_tanpa_mutasi_master(basis):
    async def scenario():
        p = await buat(basis)
        req = Req("konfirmasi", 1)
        body = rp.KonfirmasiIn(version=1, keputusan="terima")
        result = await rp.konfirmasi_penugasan(p["id"], body, req, HOLDER)
        assert result["item"]["status"] == "diterima"
        assert result["item"]["version"] == 2
        assert await rp.konfirmasi_penugasan(p["id"], body, req, HOLDER) == result
        with pytest.raises(HTTPException) as err:
            await rp.konfirmasi_penugasan(p["id"], rp.KonfirmasiIn(
                version=1, keputusan="sanggah", catatan="Bukan aset saya"), req, HOLDER)
        assert err.value.status_code == 409
        assert (await basis.assets.find_one({"id": "as1"}))["version"] == 7
        assert await basis.mutasi_bmn.count_documents({}) == 0
        assert await basis.bast_serah_terima.count_documents({}) == 0
        assert (await rp.aset_saya(HOLDER))["total"] == 1
        assert (await rp.aset_saya({**HOLDER, "pegawai_id": "p2"}))["total"] == 0
    run(scenario())


def test_mapping_duplikat_lintas_kegiatan_register_dan_nup(basis):
    async def scenario():
        await buat(basis)
        sibling = await basis.assets.find_one({"id": "as1"}, {"_id": 0})
        sibling.update({"id": "as2", "activity_id": "act2", "NUP": "001", "kode_register": "ABC123"})
        await basis.assets.insert_one(sibling)
        with pytest.raises(HTTPException) as err:
            await rp.buat_penugasan(rp.PenugasanIn(pegawai_id="p1", asset_id="as2",
                dasar_penugasan="BAST sah nomor 123 tahun 2026"), Req("map-saudara", 0), ADMIN)
        assert err.value.status_code == 409
        assert await basis.portal_penugasan.count_documents({}) == 1
        a = alias_identitas_aset(sibling, "001")
        sibling["kode_register"] = ""
        assert set(a) & set(alias_identitas_aset(sibling, "001"))
    run(scenario())


def test_mapping_ditolak_beda_satker_holder_dan_scope_kosong(basis):
    async def scenario():
        await seed(basis)
        for peg, user, code in [("p2", ADMIN, 409), ("p3", ADMIN, 404),
                                ("p1", {**ADMIN, "kode_satker": ""}, 409)]:
            with pytest.raises(HTTPException) as err:
                await rp.buat_penugasan(rp.PenugasanIn(pegawai_id=peg, asset_id="as1",
                    dasar_penugasan="BAST sah nomor 123 tahun 2026"), Req("m-" + peg, 0), user)
            assert err.value.status_code == code
        assert await basis.portal_penugasan.count_documents({}) == 0
    run(scenario())


def test_index_gagal_menutup_mapping(basis, monkeypatch):
    async def broken(*args, **kwargs):
        raise OperationFailure("indeks belum siap")
    async def scenario():
        await seed(basis)
        from mongomock_motor import AsyncMongoMockCollection
        monkeypatch.setattr(AsyncMongoMockCollection, "create_index", broken)
        with pytest.raises(HTTPException) as err:
            await rp.buat_penugasan(rp.PenugasanIn(pegawai_id="p1", asset_id="as1",
                dasar_penugasan="BAST sah nomor 123 tahun 2026"), Req(), ADMIN)
        assert err.value.status_code == 503
        assert await basis.portal_penugasan.count_documents({}) == 0
    run(scenario())


def test_header_wajib_dan_occ_antrean_luring(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        req = Req("tanpa-header", 2)
        req.headers = {}
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p), req, HOLDER)
        assert err.value.status_code == 428
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p, penugasan_version=1), Req("basi", 1), HOLDER)
        assert err.value.status_code == 409
        assert await basis.portal_laporan.count_documents({}) == 0
    run(scenario())


def test_laporan_butuh_penerimaan_dan_sanggahan_tidak_mengubah_master(basis):
    async def scenario():
        p = await buat(basis)
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p), Req("lapor-awal", 1), HOLDER)
        assert err.value.status_code == 409
        p = (await rp.konfirmasi_penugasan(p["id"], rp.KonfirmasiIn(
            version=1, keputusan="sanggah", catatan="Barang bukan milik penugasan saya"), Req("sanggah", 1), HOLDER))["item"]
        assert p["status"] == "disanggah"
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p), Req("lapor-sanggah", 2), HOLDER)
        assert err.value.status_code == 409
        assert (await basis.assets.find_one({"id": "as1"}))["pengguna_nip"] == "123456789"
    run(scenario())


def test_bukti_asli_idempotensi_review_dan_metadata_saja(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        body = laporan(p, bukti=[foto()], kondisi="Rusak Ringan", jenis="kerusakan")
        result = await rp.kirim_laporan(body, Req("laporan", 2), HOLDER)
        rid = result["item"]["id"]
        assert "data_base64" not in result["item"]["bukti"][0]
        assert await rp.kirim_laporan(body, Req("laporan", 2), HOLDER) == result
        assert await basis.portal_laporan.count_documents({}) == 1
        original = await basis.portal_laporan.find_one({"id": rid}, {"_id": 0})
        assert original["bukti"][0]["data_base64"] == foto()["data_base64"]
        assert len(original["bukti"][0]["sha256"]) == 64
        assert (await rp.bukti_saya(rid, 0, HOLDER)).body == base64.b64decode(foto()["data_base64"])
        for response in [await rp.laporan_saya(HOLDER), await rp.daftar_laporan_admin("", 1, 30, ADMIN)]:
            assert "data_base64" not in str(response)
            assert "_idem_buat" not in str(response)
        review = rp.TinjauIn(version=1, keputusan="terverifikasi", catatan="Sudah diperiksa petugas")
        reviewed = await rp.tinjau_laporan(rid, review, Req("review", 1), WRITER)
        assert reviewed["item"]["version"] == 2
        assert await rp.tinjau_laporan(rid, review, Req("review", 1), WRITER) == reviewed
        after = await basis.portal_laporan.find_one({"id": rid}, {"_id": 0})
        for field in ("jenis", "kondisi", "lokasi_laporan", "catatan", "bukti", "created_at", "sidik_laporan_asli"):
            assert after[field] == original[field]
        assert (await basis.assets.find_one({"id": "as1"}))["condition"] == "Baik"
        assert await basis.pemeliharaan.count_documents({}) == 0
        assert await basis.tgr.count_documents({}) == 0
    run(scenario())


@pytest.mark.parametrize("ubah", [
    {"pengguna_nip": "987654321"}, {"user": "Pemegang Baru"},
    {"kode_register": "REG-BARU"}, {"NUP": "2"}, {"dihapus": True},
    {"activity_id": "act3"}, {"bast_terakhir": {"id": "bast-baru"}},
])
def test_perubahan_sumber_mencabut_akses_efektif_tanpa_mutasi(basis, ubah):
    async def scenario():
        p = await buat(basis, accepted=True)
        result = await rp.kirim_laporan(laporan(p, bukti=[foto()]), Req("r", 2), HOLDER)
        await basis.assets.update_one({"id": "as1"}, {"$set": ubah})
        assert (await rp.aset_saya(HOLDER))["total"] == 0
        assert (await rp.laporan_saya(HOLDER))["total"] == 0
        with pytest.raises(HTTPException):
            await rp.kirim_laporan(laporan(p), Req("baru", 2), HOLDER)
        with pytest.raises(HTTPException):
            await rp.bukti_saya(result["item"]["id"], 0, HOLDER)
        # Arsip satker pembuat laporan tetap tersedia bagi petugas.
        assert (await rp.bukti_admin(result["item"]["id"], 0, ADMIN)).status_code == 200
        with pytest.raises(HTTPException) as err:
            await rp.bukti_admin(result["item"]["id"], 0, {**ADMIN, "kode_satker": "002"})
        assert err.value.status_code == 404
    run(scenario())


def test_cabut_menutup_laporan_dan_membuka_slot_bukan_tanggungjawab(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        body = rp.CabutIn(version=2, catatan="Akses portal ditutup oleh petugas")
        result = await rp.cabut_penugasan(p["id"], body, Req("cabut", 2), ADMIN)
        assert result["item"]["status"] == "dicabut"
        assert await rp.cabut_penugasan(p["id"], body, Req("cabut", 2), ADMIN) == result
        assert "slot_aktif" not in await basis.portal_penugasan.find_one({"id": p["id"]})
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p), Req("setelah-cabut", 2), HOLDER)
        assert err.value.status_code == 403
        assert (await basis.assets.find_one({"id": "as1"}))["user"] == "Pemegang Satu"
    run(scenario())


@pytest.mark.parametrize("identity", [
    {"pegawai_id": "p1"}, {"email": "PEMEGANG@example.test"}, {"nip": "123456789"},
    {"username": "PEMEGANG@example.test"},
])
def test_tolak_review_sendiri(basis, identity):
    async def scenario():
        p = await buat(basis, accepted=True)
        r = await rp.kirim_laporan(laporan(p), Req("lapor", 2), HOLDER)
        with pytest.raises(HTTPException) as err:
            await rp.tinjau_laporan(r["item"]["id"], rp.TinjauIn(version=1,
                keputusan="terverifikasi", catatan="Saya periksa sendiri"), Req("cek", 1), {**WRITER, **identity})
        assert err.value.status_code == 403
        assert (await basis.portal_laporan.find_one({"id": r["item"]["id"]}))["status"] == "diajukan"
    run(scenario())


def test_klarifikasi_baru_mempertahankan_laporan_sebelumnya(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        r = await rp.kirim_laporan(laporan(p, jenis="kehilangan"), Req("hilang", 2), HOLDER)
        rid = r["item"]["id"]
        await rp.tinjau_laporan(rid, rp.TinjauIn(version=1, keputusan="perlu_perbaikan",
            catatan="Mohon lengkapi kronologi"), Req("review", 1), WRITER)
        before = await basis.portal_laporan.find_one({"id": rid})
        r2 = await rp.kirim_laporan(laporan(p, jenis="kehilangan", catatan="Kronologi dilengkapi di sini",
            laporan_sebelumnya_id=rid), Req("klarifikasi", 2), HOLDER)
        assert r2["item"]["id"] != rid
        assert r2["item"]["laporan_sebelumnya_id"] == rid
        assert r2["item"]["perlu_tindak_lanjut"]
        assert await basis.portal_laporan.find_one({"id": rid}) == before
        assert await basis.usulan_penghapusan.count_documents({}) == 0
    run(scenario())


def test_idem_isi_berbeda_ditolak_dan_klaim_pulih(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        body = laporan(p)
        await rp.kirim_laporan(body, Req("r1", 2), HOLDER)
        with pytest.raises(HTTPException) as err:
            await rp.kirim_laporan(laporan(p, lokasi_laporan="Tempat berbeda"), Req("r1", 2), HOLDER)
        assert err.value.status_code == 409
        assert "laporan_aktif" not in await basis.portal_penugasan.find_one({"id": p["id"]})
    run(scenario())


def test_validasi_foto_tipe_truncated_dan_batas(monkeypatch):
    source = foto("JPEG")
    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)
    raw = base64.b64decode(source["data_base64"])
    source["data_base64"] = base64.b64encode(raw[:-2]).decode("ascii")
    with pytest.raises(ValueError):
        validasi_bukti([source])
    with pytest.raises(ValueError):
        validasi_bukti([{**foto(), "mime": "image/jpeg"}])
    with pytest.raises(ValueError):
        validasi_bukti([{**foto(), "data_base64": "%%%%"}])
    with pytest.raises(ValueError):
        validasi_bukti([foto()] * 4)
    oversized = {**foto(), "data_base64": base64.b64encode(b"x" * (3 * 1024 * 1024 + 1)).decode("ascii")}
    with pytest.raises(ValueError):
        validasi_bukti([oversized])
    assert validasi_bukti([]) == []


def test_sidik_laporan_dapat_dihitung_dari_asli(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        result = await rp.kirim_laporan(laporan(p, bukti=[foto()]), Req("r", 2), HOLDER)
        doc = await basis.portal_laporan.find_one({"id": result["item"]["id"]}, {"_id": 0})
        original = {k: v for k, v in doc.items() if k not in (
            "version", "status", "updated_at", "tinjauan", "sidik_laporan_asli", "_idem_buat")}
        assert sidik_data(original) == doc["sidik_laporan_asli"]
    run(scenario())


@pytest.mark.parametrize("action", ["laporan", "cabut"])
def test_lease_proses_mati_dapat_dipulihkan(basis, action):
    async def scenario():
        p = await buat(basis, accepted=True)
        await basis.portal_penugasan.update_one({"id": p["id"]}, {"$set": {
            "laporan_aktif": {"id": "proses-mati", "sidik": "asli",
                               "expires_at": datetime.now(timezone.utc) - timedelta(seconds=5)}}})
        if action == "laporan":
            result = await rp.kirim_laporan(laporan(p), Req("pulih", 2), HOLDER)
            assert result["item"]["status"] == "diajukan"
        else:
            result = await rp.cabut_penugasan(p["id"], rp.CabutIn(version=2,
                catatan="Akses dicabut setelah proses mati"), Req("cabut-pulih", 2), ADMIN)
            assert result["item"]["status"] == "dicabut"
        assert "laporan_aktif" not in await basis.portal_penugasan.find_one({"id": p["id"]})
    run(scenario())


def test_petugas_meninjau_arsip_setelah_akses_dicabut(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        r = await rp.kirim_laporan(laporan(p, bukti=[foto()]), Req("r", 2), HOLDER)
        await rp.cabut_penugasan(p["id"], rp.CabutIn(version=2,
            catatan="Pegawai berganti tanggung jawab"), Req("cabut", 2), ADMIN)
        reviewed = await rp.tinjau_laporan(r["item"]["id"], rp.TinjauIn(version=1,
            keputusan="terverifikasi", catatan="Berdasarkan bukti saat masih bertugas"), Req("tinjau", 1), WRITER)
        assert reviewed["item"]["tinjauan"][0]["penugasan_valid"] is False
        assert (await rp.bukti_admin(r["item"]["id"], 0, ADMIN)).status_code == 200
        assert (await rp.daftar_laporan_admin("", 1, 30, ADMIN))["items"][0]["penugasan_valid"] is False
    run(scenario())


def test_filter_pegawai_dan_paginasi_laporan_admin(basis):
    async def scenario():
        p = await buat(basis, accepted=True)
        for i in range(32):
            await basis.portal_laporan.insert_one({
                "id": f"lap-{i}", "pegawai_id": "p1" if i < 31 else "p2",
                "penugasan_id": p["id"], "kode_satker": "001",
                "status": "diajukan", "created_at": f"2026-01-01T00:{i:02}:00Z"})
        hasil = await rp.daftar_laporan_admin("diajukan", 2, 30, ADMIN, "p1")
        assert hasil["total"] == 31
        assert len(hasil["items"]) == 1
        assert hasil["items"][0]["pegawai_id"] == "p1"
        assert (await rp.daftar_laporan_admin("ditolak", 1, 30, ADMIN, "p1"))["total"] == 0
    run(scenario())


@pytest.mark.parametrize("identitas_staf", [
    {"username": "pemegang@example.test"}, {"nip": "123456789"},
])
def test_identitas_historis_menolak_review_setelah_email_pegawai_berubah(basis, identitas_staf):
    async def scenario():
        p = await buat(basis, accepted=True)
        r = await rp.kirim_laporan(laporan(p), Req("r", 2), HOLDER)
        rid = r["item"]["id"]
        assert "_identitas_pelapor" not in r["item"]
        await basis.pegawai.update_one({"id": "p1"}, {"$set": {
            "email": "alamat-baru@example.test", "nip": "999999999"}})
        with pytest.raises(HTTPException) as err:
            await rp.tinjau_laporan(rid, rp.TinjauIn(version=1,
                keputusan="terverifikasi", catatan="Mencoba memeriksa laporan sendiri"),
                Req("review", 1), {**WRITER, **identitas_staf})
        assert err.value.status_code == 403
        staff_list = await rp.daftar_laporan_admin("", 1, 30, ADMIN)
        assert "_identitas_pelapor" not in str(staff_list)
        assert (await basis.portal_laporan.find_one({"id": rid}))["status"] == "diajukan"
    run(scenario())
