"""Daftar peserta: bukti lama utuh, OCC, replay, satker, tautan dan BAST."""
import asyncio
import copy

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt
import shared_utils as su
from ttd_penautan import status_ttd_dokumen

USER = {"username": "operator", "role": "operator", "kode_satker": "111111"}


def run(coro):
    return asyncio.run(coro)


class Req:
    def __init__(self, version="4", idem="peserta-1"):
        self.headers = {"If-Match": version, "Idempotency-Key": idem}


@pytest.fixture
def dbx(monkeypatch):
    db = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rt, "db", db)
    monkeypatch.setattr(su, "db", db)
    async def diam(*a, **kw):
        pass
    monkeypatch.setattr(rt, "log_audit", diam)
    monkeypatch.setattr(rt, "_cetak_token_signer", lambda *a: ("token", "2099-01-01T00:00:00+00:00"))
    return db


async def seed(db, *, mode="paralel", status="sebagian", validasi="menunggu_validasi"):
    sr = {"id": "sr", "kode_satker": "111111", "created_by": "operator", "version": 4,
          "judul": "BAST-01", "doc_type": "bast", "doc_ref": "b1", "mode": mode,
          "status": status, "dok_file_id": "pdf-asli", "dok_hash": "hash-pdf",
          "signers": [
              {"signer_id": "s1", "nama": "Pertama", "urutan": 1, "status": validasi,
               "jti": "lama-1", "signature_file_id": "gambar-1", "hash": "bukti-1",
               "posisi_ttd": {"halaman": 1, "x": .1, "y": .2, "lebar": .2}},
              {"signer_id": "s2", "nama": "Kedua", "urutan": 2, "status": "aktif", "jti": "lama-2"}]}
    await db.signature_requests.insert_one(copy.deepcopy(sr))
    await db.bast_serah_terima.insert_one({"id": "b1", "kode_satker": "111111", "nomor": "BAST-01"})
    return sr


async def ubah(aksi="tambah", req=None, user=None, **kw):
    if aksi == "tambah" and "signer" not in kw:
        kw["signer"] = rt.SignerIn(nama="Tambahan", nip="3200000000000001", jumlah_ttd=2)
    return await rt.ubah_penandatangan("sr", rt.UbahPenandatanganIn(
        aksi=aksi, alasan="Peserta terlewat saat pengiriman", **kw), req or Req(), user=user or USER)


def test_tambah_bukti_dokumen_lama_utuh_dan_bast_mengikuti(dbx):
    async def skenario():
        lama = await seed(dbx)
        hasil = await ubah()
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert sr["signers"][:2] == lama["signers"]
        assert (sr["dok_file_id"], sr["dok_hash"]) == ("pdf-asli", "hash-pdf")
        assert sr["signers"][2]["jumlah_ttd"] == 2
        assert sr["signers"][2]["urutan"] == 3
        assert sr["signers"][2]["status"] == "aktif"
        assert hasil["version"] == 5 and sr["status"] == "sebagian"
        ringkas = (await status_ttd_dokumen(dbx, "bast", ["b1"]))["b1"]
        assert ringkas["jumlah"] == 3
        assert [s["nama"] for s in ringkas["penanda_tangan"]] == ["Pertama", "Kedua", "Tambahan"]
        assert (await dbx.bast_serah_terima.find_one({"id": "b1"}))["nomor"] == "BAST-01"
    run(skenario())


def test_berurutan_hapus_aktif_maju_dan_tautan_lama_tidak_dikenal(dbx):
    async def skenario():
        await seed(dbx, mode="berurutan")
        await ubah()
        sebelum = await dbx.signature_requests.find_one({"id": "sr"})
        assert sebelum["signers"][-1]["status"] == "menunggu"
        await ubah("hapus", Req("5", "hapus-1"), signer_id="s2")
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert [s["urutan"] for s in sr["signers"]] == [1, 3]
        assert sr["signers"][-1]["status"] == "aktif"
        with pytest.raises(rt.HTTPException) as e:
            await rt.info_tandatangan("sr", tok={"sr": "sr", "signer": "s2", "jti": "lama-2"})
        assert e.value.status_code in {403, 404}
    run(skenario())


@pytest.mark.parametrize("status", ["selesai", "batal"])
def test_final_batal_ditolak(dbx, status):
    async def skenario():
        await seed(dbx, status=status)
        with pytest.raises(rt.HTTPException) as e:
            await ubah()
        assert e.value.status_code == 409
    run(skenario())


@pytest.mark.parametrize("user", [dict(USER, kode_satker="222222"), dict(USER, role="viewer"),
                                   dict(USER, username="operator-lain")])
def test_hak_akses_ditolak_bahkan_pembuat_pindah_satker(dbx, user):
    async def skenario():
        await seed(dbx)
        with pytest.raises(rt.HTTPException) as e:
            await ubah(user=user)
        assert e.value.status_code == 403
    run(skenario())


@pytest.mark.parametrize("req", [Req(""), Req("4", ""), Req("²"), Req("9" * 100)])
def test_header_wajib(dbx, req):
    async def skenario():
        await seed(dbx)
        with pytest.raises(rt.HTTPException) as e:
            await ubah(req=req)
        assert e.value.status_code == 428
    run(skenario())


def test_bubuhan_tidak_dihapus_dan_versi_basi_ditolak(dbx):
    async def skenario():
        lama = await seed(dbx)
        for args in [("hapus", Req(), {"signer_id": "s1"}), ("tambah", Req("3"), {})]:
            with pytest.raises(rt.HTTPException) as e:
                await ubah(args[0], args[1], **args[2])
            assert e.value.status_code == 409
        assert (await dbx.signature_requests.find_one({"id": "sr"}))["signers"] == lama["signers"]
    run(skenario())


def test_replay_atomik_dan_payload_berbeda_ditolak(dbx):
    async def skenario():
        await seed(dbx)
        pertama = await ubah()
        await dbx.idempotency_keys.delete_many({})  # simulasi cache hilang sesudah commit
        assert await ubah() == pertama
        with pytest.raises(rt.HTTPException) as e:
            await ubah(signer=rt.SignerIn(nama="Orang berbeda"))
        assert e.value.status_code == 409
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert len(sr["riwayat_penandatangan"]) == 1 and sr["version"] == 5
    run(skenario())


def test_hapus_terakhir_butuh_konfirmasi_final_dan_backlink(dbx):
    async def skenario():
        await seed(dbx, validasi="terverifikasi")
        with pytest.raises(rt.HTTPException) as e:
            await ubah("hapus", signer_id="s2")
        assert e.value.status_code == 409
        hasil = await ubah("hapus", signer_id="s2", konfirmasi_final=True)
        assert hasil["status"] == "selesai"
        bast = await dbx.bast_serah_terima.find_one({"id": "b1"})
        assert bast["signature_request_id"] == "sr" and bast["tt_esign_selesai_pada"]
    run(skenario())


def test_race_pembubuhan_tidak_tertimpa(dbx, monkeypatch):
    async def skenario():
        await seed(dbx)
        kelas = type(dbx.signature_requests)
        asli = kelas.update_one
        async def balapan(self, q, update, **kw):
            if "$push" in update and "riwayat_penandatangan" in update["$push"]:
                await asli(self, {"id": "sr", "signers.signer_id": "s2"}, {
                    "$set": {"signers.$.status": "menunggu_validasi", "signers.$.signature_file_id": "bukti-baru"},
                    "$inc": {"version": 1}})
            return await asli(self, q, update, **kw)
        monkeypatch.setattr(kelas, "update_one", balapan)
        with pytest.raises(rt.HTTPException) as e:
            await ubah("hapus", signer_id="s2")
        assert e.value.status_code == 409
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert sr["signers"][1]["signature_file_id"] == "bukti-baru"
    run(skenario())


def test_race_rotasi_tautan_tanpa_kenaikan_versi_tidak_tertimpa(dbx, monkeypatch):
    async def skenario():
        await seed(dbx)
        kelas = type(dbx.signature_requests)
        asli = kelas.update_one
        async def balapan(self, q, update, **kw):
            if "riwayat_penandatangan" in update.get("$push", {}):
                await asli(self, {"id": "sr", "signers.signer_id": "s2"},
                           {"$set": {"signers.$.jti": "tautan-baru"}})
            return await asli(self, q, update, **kw)
        monkeypatch.setattr(kelas, "update_one", balapan)
        with pytest.raises(rt.HTTPException) as e:
            await ubah()
        assert e.value.status_code == 409
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert sr["signers"][1]["jti"] == "tautan-baru" and len(sr["signers"]) == 2
    run(skenario())


def test_submit_basi_tidak_mengembalikan_status_setelah_peserta_ditambah(dbx, monkeypatch):
    from types import SimpleNamespace
    async def diam(*a, **kw):
        pass
    monkeypatch.setattr(rt, "_png_dari_base64", lambda _: b"uji-png")
    monkeypatch.setattr(rt, "png_transparan_valid", lambda _: True)
    monkeypatch.setattr(rt, "fs_bucket", SimpleNamespace(open_upload_stream_with_id=lambda *a, **kw:
                        SimpleNamespace(write=diam, close=diam), delete=diam))
    async def skenario():
        await seed(dbx)
        kelas = type(dbx.signature_requests)
        asli = kelas.update_one
        terjadi = []
        async def balapan(self, q, update, **kw):
            bidang = update.get("$set", {})
            if bidang.get("status") == "menunggu_validasi" and "signers.$.status" not in bidang and not terjadi:
                terjadi.append(True)
                await ubah(req=Req("5", "tambah-bersamaan"))
            return await asli(self, q, update, **kw)
        monkeypatch.setattr(kelas, "update_one", balapan)
        hasil = await rt.kirim_tandatangan.__wrapped__("sr", rt.SpesimenIn(png_base64="uji",
            posisi={"halaman": 1, "x": .3, "y": .3, "lebar": .2}),
            SimpleNamespace(client=None), tok={"sr": "sr", "signer": "s2", "jti": "lama-2"})
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert terjadi and len(sr["signers"]) == 3 and sr["version"] == 6
        assert sr["status"] == hasil["status_dokumen"] == "sebagian"
        assert sr["signers"][1]["signature_file_id"]
        assert sr["signers"][2]["status"] == "aktif"
    run(skenario())


def test_legacy_tanpa_versi_dan_tanpa_identitas_tetap_dapat_ditambah(dbx):
    async def skenario():
        await seed(dbx)
        await dbx.signature_requests.update_one({"id": "sr"}, {"$unset": {"version": ""}})
        hasil = await ubah(req=Req("1"), signer=rt.SignerIn(nama="Mitra eksternal"))
        assert hasil["version"] == 2
        sr = await dbx.signature_requests.find_one({"id": "sr"})
        assert sr["signers"][-1]["nip"] == ""
        with pytest.raises(rt.HTTPException) as e:
            await ubah(req=Req("2", "duplikat"), signer=rt.SignerIn(nama="  MITRA eksternal  "))
        assert e.value.status_code == 409
    run(skenario())


def test_hapus_satu_satunya_ditolak_dan_admin_satker_diizinkan(dbx):
    async def skenario():
        await seed(dbx)
        await dbx.signature_requests.update_one({"id": "sr"}, {"$pull": {"signers": {"signer_id": "s1"}}})
        with pytest.raises(rt.HTTPException) as e:
            await ubah("hapus", signer_id="s2")
        assert e.value.status_code == 409
        hasil = await ubah(user=dict(USER, role="admin", username="admin-satker"))
        assert hasil["ok"]
    run(skenario())


def test_detail_membawa_kemampuan_dan_riwayat_tanpa_kunci_internal(dbx):
    async def skenario():
        await seed(dbx)
        await ubah()
        detail = await rt.detail_permintaan("sr", user=USER)
        assert detail["dapat_kelola_penandatangan"] is True
        assert detail["riwayat_penandatangan"][0]["nama"] == "Tambahan"
        assert not {"kunci", "fingerprint", "hasil"} & detail["riwayat_penandatangan"][0].keys()
        assert all("jti" not in s for s in detail["signers"])
        detail = await rt.detail_permintaan("sr", user=dict(USER, username="operator-lain"))
        assert detail["dapat_kelola_penandatangan"] is False
    run(skenario())
