"""Bukti BAST otomatis: manifest immutable, validitas terkini dan retry hook."""
import asyncio
from copy import deepcopy
from datetime import date
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import portal_bast_validitas as pv
import routes.ttd as rt
import shared_utils as su
import tautan_pendek_utils as tp

PDF = b"%PDF-1.7\nbyte-final-setelah-kompresi"
USER = {"username": "operator", "role": "operator", "kode_satker": "111111"}
QR = {"halaman": 1, "x": .2, "y": .2, "lebar": .2}


def run(coro):
    return asyncio.run(coro)


def dokumen():
    return {"id": "b1", "kode_satker": "111111", "jenis": "mutasi_pengguna", "nomor": "BAST-01",
            "asset_ids": ["a1"], "pihak_kedua": {"pegawai_id": "p1", "nama": "Penerima"},
            "signature_request_id": "sr1", "portal_otomasi": {"version": 1, "items": [
                {"asset_id": "a1", "aksi": "serah", "penerima": {"pegawai_id": "p1"},
                 "ikatan_awal": {"asset_id": "a1", "user": "lama"}, "alias": ["barang1"]}]}}


def peserta(sid):
    return {"signer_id": sid, "nama": sid.upper(), "nip": "NIP-" + sid, "jabatan": "Pihak",
            "jumlah_ttd": 1, "status": "aktif", "jti": "jti-" + sid}


@pytest.fixture
def env(monkeypatch):
    db = AsyncMongoMockClient()["bast_validitas"]
    for module in (rt, su, tp):
        monkeypatch.setattr(module, "db", db)
    monkeypatch.setattr(su, "get_document_from_gridfs", AsyncMock(return_value=PDF))
    monkeypatch.setattr(rt, "log_audit", AsyncMock())
    monkeypatch.setattr(tp, "cabut_tautan", AsyncMock())
    monkeypatch.setattr(rt, "_sinkronkan_portal_bast", AsyncMock())
    run(db.bast_serah_terima.insert_one(dokumen()))
    run(db.signature_requests.insert_one({"id": "sr1", "kode_satker": "111111", "doc_type": "bast",
        "doc_ref": "b1", "status": "terkirim", "version": 1, "created_by": "operator",
        "dok_file_id": "pdf1", "dok_halaman": 1, "signers": [peserta("s1"), peserta("s2")]}))
    return db


async def beku(db):
    return await pv.bekukan_manifest_bast(db, await db.bast_serah_terima.find_one({"id": "b1"}), "sr1")


async def lengkap(db, qr=True):
    await beku(db)
    sr = await db.signature_requests.find_one({"id": "sr1"})
    for s in sr["signers"]:
        s.update(status="terverifikasi", signature_file_id="png-" + s["signer_id"], hash="hash-" + s["signer_id"],
                 posisi_ttd=dict(QR), validated_by="operator", validated_at="2026-10-03T01:00:00Z")
    await db.signature_requests.update_one({"id": "sr1"}, {"$set": {
        "status": "selesai", "signers": sr["signers"], "finalized_by": "operator", "version": 4,
        **({"posisi_qr": dict(QR)} if qr else {})}})


async def nilai(db):
    return await pv.evaluasi_bast_sah(db, await db.bast_serah_terima.find_one({"id": "b1"}))


def test_sidik_mengikat_isi_dan_pemetaan_bukan_status_runtime():
    b = dokumen()
    sidik = pv.sidik_isi_bast(b)
    berubah = deepcopy(b)
    berubah.update(tt_dicabut=False, tt_esign_selesai_pada="baru", signature_request_id="sr-lain")
    berubah["portal_otomasi"].update(status="efektif", version=8, hasil=["selesai"])
    assert pv.sidik_isi_bast(berubah) == sidik
    berubah["portal_otomasi"]["items"][0]["penerima"]["pegawai_id"] = "p-lain"
    assert pv.sidik_isi_bast(berubah) != sidik
    berubah = {**b, "nomor": "BAST-02"}
    assert pv.sidik_isi_bast(berubah) != sidik


def test_hash_memakai_byte_actual_dan_replay_tidak_menghapus_manifest_wajib(env):
    async def scenario():
        first = await beku(env)
        assert first["dok_sha256"] == hashlib.sha256(PDF).hexdigest()
        await env.signature_requests.update_one({"id": "sr1"}, {"$pull": {"signers": {"signer_id": "s2"}}})
        second = await beku(env)
        assert second == first and len(second["wajib"]) == 2
        assert su.get_document_from_gridfs.await_count == 1
    run(scenario())


@pytest.mark.parametrize("perubahan", [
    {"status": "batal"}, {"kode_satker": "222222"}, {"doc_ref": "b-lain"},
    {"dok_file_id": ""}, {"signers": [dict(peserta("s1"), status="menunggu_validasi", signature_file_id="sudah")]}])
def test_manifest_menolak_sumber_tidak_cocok_atau_pembubuhan_sudah_dimulai(env, perubahan):
    async def scenario():
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": perubahan})
        with pytest.raises(HTTPException):
            await beku(env)
        assert not (await env.signature_requests.find_one({"id": "sr1"})).get("bast_otomasi_manifest")
    run(scenario())


def test_race_pembubuhan_saat_pdf_dibaca_tidak_diberkati_manifest(env, monkeypatch):
    async def baca(fid):
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"signers.0.status": "menunggu_validasi"}})
        return PDF
    monkeypatch.setattr(su, "get_document_from_gridfs", baca)
    with pytest.raises(HTTPException):
        run(beku(env))


def test_esign_lengkap_tanpa_baca_ulang_pdf_per_akses(env):
    async def scenario():
        await lengkap(env)
        first = await nilai(env)
        second = await nilai(env)
        assert first == second
        assert first["sah"] and first["jenis"] == "esign" and first["file_id"] == "pdf1"
        assert first["kunci_bukti"].startswith("esign:") and first["oleh"] == "operator"
        assert su.get_document_from_gridfs.await_count == 1
    run(scenario())


@pytest.mark.parametrize("koleksi,perubahan", [
    ("bast_serah_terima", {"signature_request_id": "sr-lain"}),
    ("bast_serah_terima", {"kode_satker": ""}),
    ("bast_serah_terima", {"direvisi_oleh": "b2"}),
    ("bast_serah_terima", {"pihak_kedua.pegawai_id": "p2"}),
    ("signature_requests", {"status": "batal"}),
    ("signature_requests", {"status": "menunggu_validasi"}),
    ("signature_requests", {"posisi_qr": None}),
    ("signature_requests", {"dok_file_id": "pdf-berbeda"}),
    ("signature_requests", {"bast_otomasi_manifest.dok_sha256": "rusak"}),
    ("signature_requests", {"signers.0.status": "aktif"}),
    ("signature_requests", {"signers.0.signature_file_id": ""}),
    ("signature_requests", {"signers.0.nip": "orang-lain"}),
    ("signature_requests", {"signers.0.posisi_ttd": None}),
])
def test_sumber_berubah_ditolak_meski_marker_bast_lama_masih_aktif(env, koleksi, perubahan):
    async def scenario():
        await lengkap(env)
        await env[koleksi].update_one({"id": "b1" if koleksi == "bast_serah_terima" else "sr1"}, {"$set": perubahan})
        result = await nilai(env)
        assert not result["sah"] and result["alasan"] and not result["kunci_bukti"]
    run(scenario())


def test_peserta_wajib_dihapus_menolak_tambahan_tervalidasi_diizinkan(env):
    async def scenario():
        await lengkap(env)
        sr = await env.signature_requests.find_one({"id": "sr1"})
        tambahan = {**sr["signers"][0], "signer_id": "s3", "nama": "Tambahan"}
        await env.signature_requests.update_one({"id": "sr1"}, {"$push": {"signers": tambahan}})
        assert (await nilai(env))["sah"]
        await env.signature_requests.update_one({"id": "sr1"}, {"$pull": {"signers": {"signer_id": "s2"}}})
        assert not (await nilai(env))["sah"]
    run(scenario())


def test_minimum_area_manifest_tidak_dapat_diturunkan_dan_deklarasi_diperiksa(env):
    async def scenario():
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"signers.0.jumlah_ttd": 2}})
        await lengkap(env)
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"signers.0.jumlah_ttd": 1}})
        assert not (await nilai(env))["sah"]
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"signers.0.deklarasi_tanpa_area": True}})
        assert not (await nilai(env))["sah"]
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"signers.0.validation_note": "Tidak ada area lain; diperiksa"}})
        assert (await nilai(env))["sah"]
    run(scenario())


def test_bukti_basah_memerlukan_attestasi_sidik_dan_verifikasi_setelah_batal(env):
    async def scenario():
        b = await env.bast_serah_terima.find_one({"id": "b1"})
        bukti = {"file_id": "scan1", "sha256": hashlib.sha256(PDF).hexdigest(),
                 "verifikasi_lengkap": True, "diverifikasi_oleh": "operator", "diverifikasi_pada": "2026-10-03T01:00:00Z",
                 "bast_sidik": pv.sidik_isi_bast(b)}
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"bukti": bukti}})
        assert (await nilai(env))["jenis"] == "basah"
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"status": "batal", "batal_pada": "2026-10-03T02:00:00Z"}})
        assert not (await nilai(env))["sah"]
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"bukti.diverifikasi_pada": "2026-10-03T03:00:00Z"}})
        assert (await nilai(env))["sah"]
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"bukti.verifikasi_lengkap": False}})
        assert not (await nilai(env))["sah"]
    run(scenario())


@pytest.mark.parametrize("perubahan", [{"signature_request_id": "sr-baru"}, {"direvisi_oleh": "b2"}])
def test_callback_tidak_mengambil_alih_pointer_atau_bast_tergantikan(env, perubahan):
    async def scenario():
        await lengkap(env)
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {**perubahan, "tt_dicabut": True}})
        await rt._catat_penyelesaian_ttd({"status": "selesai"}, "sr1")
        b = await env.bast_serah_terima.find_one({"id": "b1"})
        assert b["tt_dicabut"] is True
        rt._sinkronkan_portal_bast.assert_not_awaited()
    run(scenario())


def test_callback_membaca_status_terkini_bukan_snapshot_lama(env):
    async def scenario():
        await lengkap(env)
        sr = await env.signature_requests.find_one({"id": "sr1"})
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"status": "batal"}})
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"tt_dicabut": True}})
        await rt._catat_penyelesaian_ttd(sr, "sr1")
        assert (await env.bast_serah_terima.find_one({"id": "b1"}))["tt_dicabut"] is True
    run(scenario())


def test_race_batal_diantara_callback_dan_write_dikoreksi_dan_guard_menolak(env, monkeypatch):
    async def scenario():
        await lengkap(env)
        col = env.bast_serah_terima
        original = col.update_one

        async def batal_sebelum_write(query, update, **kw):
            if update.get("$set", {}).get("tt_dicabut") is False:
                await env.signature_requests.update_one({"id": "sr1"}, {"$set": {"status": "batal", "batal_pada": "2026-10-03T02:00:00Z"}})
            return await original(query, update, **kw)

        monkeypatch.setattr(col, "update_one", batal_sebelum_write)
        monkeypatch.setattr(rt, "db", SimpleNamespace(bast_serah_terima=col,
                            signature_requests=env.signature_requests, assets=env.assets))
        await rt._catat_penyelesaian_ttd({}, "sr1")
        assert (await env.bast_serah_terima.find_one({"id": "b1"}))["tt_dicabut"] is True
        assert not (await nilai(env))["sah"]
    run(scenario())


class Req:
    headers = {"If-Match": "4", "Idempotency-Key": "validasi-akhir"}


def test_retry_setelah_sinkron_gagal_memulihkan_tanpa_validasi_dua_kali(env, monkeypatch):
    async def scenario():
        await lengkap(env, qr=False)
        await env.signature_requests.update_one({"id": "sr1"}, {"$set": {
            "status": "menunggu_validasi", "signers.0.status": "menunggu_validasi"}})
        sync = AsyncMock(side_effect=[RuntimeError("proses terputus"), None])
        monkeypatch.setattr(rt, "_sinkronkan_portal_bast", sync)
        payload = rt.ValidasiPembubuhanIn(aksi="setujui", alasan="Sudah diperiksa")
        with pytest.raises(RuntimeError):
            await rt.validasi_pembubuhan("sr1", "s1", payload, Req(), user=USER)
        response = await rt.validasi_pembubuhan("sr1", "s1", payload, Req(), user=USER)
        assert response["status"] == "selesai" and sync.await_count == 2
        sr = await env.signature_requests.find_one({"id": "sr1"})
        assert sr["version"] == 5 and len(sr["riwayat_validasi"]) == 1
        with pytest.raises(HTTPException) as e:
            await rt.validasi_pembubuhan("sr1", "s1", rt.ValidasiPembubuhanIn(aksi="setujui", alasan="Alasan berbeda"), Req(), user=USER)
        assert e.value.status_code == 409
    run(scenario())


def test_qr_otomasi_dibekukan_dan_replay_menyusul_sinkron(env):
    async def scenario():
        await lengkap(env, qr=False)
        payload = rt.PosisiQrIn(posisi_qr=dict(QR))
        await rt.atur_posisi_qr("sr1", payload, user=USER)
        await rt.atur_posisi_qr("sr1", payload, user=USER)
        assert rt._sinkronkan_portal_bast.await_count == 2
        assert (await nilai(env))["sah"]
        for posisi in (None, {**QR, "x": .5}):
            with pytest.raises(HTTPException) as e:
                await rt.atur_posisi_qr("sr1", rt.PosisiQrIn(posisi_qr=posisi), user=USER)
            assert e.value.status_code == 409
    run(scenario())


@pytest.mark.parametrize("surat", [None, {"kode_satker": "222222", "status": "disahkan"},
    {"kode_satker": "111111", "status": "dibatalkan"},
    {"kode_satker": "111111", "status": "disahkan", "dihapus": True}])
def test_surat_rujukan_hilang_asing_dan_batal_menolak_bukti_lengkap(env, surat):
    async def scenario():
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"surat_id": "agenda1"}})
        if surat:
            await env.surat.insert_one({"id": "agenda1", **surat})
        await lengkap(env)
        assert not (await nilai(env))["sah"]
    run(scenario())


@pytest.mark.parametrize("jenis", ["mencabut", "membatalkan", "mengubah", "mencabut_sebagian"])
def test_agenda_booking_sendiri_boleh_relasi_draf_belum_mematikan_tapi_final_menolak(env, jenis):
    async def scenario():
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {"surat_id": "agenda1"}})
        await env.surat.insert_many([
            {"id": "agenda1", "kode_satker": "111111", "status": "dibooking"},
            {"id": "agenda2", "kode_satker": "111111", "status": "dibooking"}])
        await env.surat_relasi.insert_one({"id": "rel1", "kode_satker": "111111", "dari_id": "agenda2", "ke_id": "agenda1", "jenis": jenis})
        await lengkap(env)
        assert (await nilai(env))["sah"]
        await env.surat.update_one({"id": "agenda2"}, {"$set": {"status": "disahkan"}})
        assert not (await nilai(env))["sah"]
        await env.surat.update_one({"id": "agenda2"}, {"$set": {"status": "dibatalkan"}})
        assert (await nilai(env))["sah"]
    run(scenario())


def test_penggunaan_sementara_pending_sebelum_mulai_dan_lewat_akhir_tetap_boleh_melapor(env, monkeypatch):
    async def scenario():
        await env.bast_serah_terima.update_one({"id": "b1"}, {"$set": {
            "jenis": "penggunaan_sementara", "jangka_dari": "2026-10-04", "jangka_sampai": "2026-10-05"}})
        await lengkap(env)
        monkeypatch.setattr(pv, "_hari_wita", lambda: date(2026, 10, 3))
        pending = await nilai(env)
        assert not pending["sah"] and "sinkronkan kembali" in pending["alasan"]
        monkeypatch.setattr(pv, "_hari_wita", lambda: date(2026, 10, 4))
        assert (await nilai(env))["sah"]
        monkeypatch.setattr(pv, "_hari_wita", lambda: date(2026, 10, 6))
        assert (await nilai(env))["sah"]
    run(scenario())
