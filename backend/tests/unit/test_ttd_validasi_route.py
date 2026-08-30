"""Gerbang validator E-sign dan koreksi satu penanda tangan."""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt
import shared_utils as su
import tautan_pendek_utils as tp


USER = {"username": "operator", "role": "operator", "kode_satker": "111111"}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _Req:
    def __init__(self, version="4", idem="uji-1"):
        self.headers = {"If-Match": version, "Idempotency-Key": idem}


async def _diam(*_a, **_k):
    return None


def _signer(sid, status, deklarasi=False):
    return {
        "signer_id": sid, "nama": sid.upper(), "email": "", "status": status,
        "jti": f"jti-{sid}", "token_exp": "2099-01-01T00:00:00+00:00",
        "signature_file_id": f"file-{sid}", "hash": f"hash-{sid}",
        "signed_at": "2026-08-30T01:00:00+00:00",
        "posisi_ttd": {"halaman": 1, "x": .2, "y": .3, "lebar": .2},
        "posisi_ttd_lain": [], "jumlah_ttd": 2 if deklarasi else 1,
        "deklarasi_tanpa_area": deklarasi,
        "deklarasi_jumlah_aktual": 1 if deklarasi else None,
        "deklarasi_jumlah_diminta": 2 if deklarasi else None,
    }


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rt, "db", fake, raising=False)
    monkeypatch.setattr(su, "db", fake, raising=False)
    monkeypatch.setattr(tp, "db", fake, raising=False)
    monkeypatch.setattr(rt, "log_audit", _diam, raising=False)
    monkeypatch.setattr(rt, "_cetak_token_signer",
                        lambda sr, sg, jti: (f"token-{jti}", "2099-01-01T00:00:00+00:00"))

    async def _link(_sr, _tok, **_kw):
        return "/s/link-baru"
    monkeypatch.setattr(rt, "_link_ttd_pendek", _link, raising=False)
    monkeypatch.setattr(tp, "cabut_tautan", _diam, raising=False)
    return fake


async def _seed(fake, *, status="menunggu_validasi", deklarasi=False):
    await fake.signature_requests.insert_one({
        "id": "sr-1", "judul": "BAST-035/OIKN/2026", "doc_type": "bast",
        "doc_ref": "bast-1", "kode_satker": "111111", "created_by": "operator",
        "status": status, "version": 4, "riwayat_validasi": [],
        "signers": [_signer("s1", "menunggu_validasi", deklarasi),
                    _signer("s2", "terverifikasi")],
    })
    await fake.bast_serah_terima.insert_one(
        {"id": "bast-1", "kode_satker": "111111", "tt_dicabut": True})


class TestSetujui:
    def test_validasi_terakhir_baru_memfinalkan_dan_menautkan_bast(self, dbx):
        async def skenario():
            await _seed(dbx)
            hasil = await rt.validasi_pembubuhan(
                "sr-1", "s1", rt.ValidasiPembubuhanIn(
                    aksi="setujui", alasan="Posisi dan isi sudah diperiksa"),
                _Req(), user=USER)
            sr = await dbx.signature_requests.find_one({"id": "sr-1"})
            bast = await dbx.bast_serah_terima.find_one({"id": "bast-1"})
            assert hasil["status"] == "selesai"
            assert sr["status"] == "selesai" and sr["version"] == 5
            assert sr["signers"][0]["status"] == "terverifikasi"
            assert sr["finalized_by"] == "operator"
            assert sr["riwayat_validasi"][-1]["aksi"] == "setujui"
            assert bast["signature_request_id"] == "sr-1"
            assert bast["tt_dicabut"] is False
        _jalan(skenario())

    def test_deklarasi_jumlah_memerlukan_catatan_validator(self, dbx):
        async def skenario():
            await _seed(dbx, deklarasi=True)
            with pytest.raises(rt.HTTPException) as e:
                await rt.validasi_pembubuhan(
                    "sr-1", "s1", rt.ValidasiPembubuhanIn(aksi="setujui"),
                    _Req(), user=USER)
            assert e.value.status_code == 400
            assert "Catatan pemeriksaan" in str(e.value.detail)
        _jalan(skenario())

    def test_if_match_wajib(self, dbx):
        async def skenario():
            await _seed(dbx)
            with pytest.raises(rt.HTTPException) as e:
                await rt.validasi_pembubuhan(
                    "sr-1", "s1", rt.ValidasiPembubuhanIn(aksi="setujui"),
                    _Req(version=""), user=USER)
            assert e.value.status_code == 428
        _jalan(skenario())

    def test_retry_idempoten_memutar_respons_tanpa_validasi_ganda(self, dbx):
        async def skenario():
            await _seed(dbx)
            payload = rt.ValidasiPembubuhanIn(
                aksi="setujui", alasan="Sudah diperiksa")
            req = _Req(version="4", idem="retry-sama")
            pertama = await rt.validasi_pembubuhan(
                "sr-1", "s1", payload, req, user=USER)
            kedua = await rt.validasi_pembubuhan(
                "sr-1", "s1", payload, req, user=USER)
            sr = await dbx.signature_requests.find_one({"id": "sr-1"})
            return pertama, kedua, sr
        pertama, kedua, sr = _jalan(skenario())
        assert kedua == pertama
        assert sr["version"] == 5
        assert len(sr["riwayat_validasi"]) == 1


class TestBukaUlangSatuOrang:
    def test_hanya_target_dibuka_dan_bukti_lama_diarsipkan(self, dbx):
        async def skenario():
            await _seed(dbx)
            hasil = await rt.validasi_pembubuhan(
                "sr-1", "s1", rt.ValidasiPembubuhanIn(
                    aksi="buka_ulang", alasan="Posisi menutupi teks"),
                _Req(), user=USER)
            sr = await dbx.signature_requests.find_one({"id": "sr-1"})
            s1, s2 = sr["signers"]
            assert hasil["link"] == "/s/link-baru"
            assert sr["status"] == "sebagian" and sr["version"] == 5
            assert s1["status"] == "aktif" and "signature_file_id" not in s1
            assert s1["jti"] != "jti-s1"
            assert s2["status"] == "terverifikasi"
            bukti = sr["riwayat_validasi"][-1]["bukti_lama"]
            assert bukti["signature_file_id"] == "file-s1"
            assert bukti["hash"] == "hash-s1"
        _jalan(skenario())

    def test_dokumen_final_tidak_boleh_dibuka_diam_diam(self, dbx):
        async def skenario():
            await _seed(dbx, status="selesai")
            with pytest.raises(rt.HTTPException) as e:
                await rt.validasi_pembubuhan(
                    "sr-1", "s1", rt.ValidasiPembubuhanIn(
                        aksi="buka_ulang", alasan="Salah"), _Req(), user=USER)
            assert e.value.status_code == 409
            assert "naskah ralat" in str(e.value.detail)
        _jalan(skenario())
