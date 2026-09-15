"""Label metadata e-sign, termasuk respons verifikasi yang nomornya disamarkan."""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt


@pytest.mark.parametrize("nomor,label", [
    ("3506042503900001", "NIK"),
    ("3506 0425.0390-0001", "NIK"),
    ("198801012010011001", "NIP"),
    ("198801012024211001", "NI PPPK"),
    ("85011234", "NRP"),
    ("123456", "NRP"),
    ("nomor-lama", "No. Identitas"),
    ("", ""), (None, ""),
])
def test_label_signer_tanpa_mengubah_nomor_atau_membuka_token(nomor, label):
    signer = {"nip": nomor, "jti": "rahasia-uji", "token": "rahasia-uji"}
    hasil = rt._publik_signer(signer)
    assert hasil["nip"] == nomor
    assert hasil["label_identitas"] == label
    assert "jti" not in hasil and "token" not in hasil
    assert "label_identitas" not in signer  # tidak menulis snapshot historis


def test_detail_dan_verifikasi_memakai_label_dari_nomor_utuh(monkeypatch):
    database = AsyncMongoMockClient()["uji_label_ttd"]
    monkeypatch.setattr(rt, "db", database)

    async def skenario():
        nomor = "3506042503900001"
        await database.signature_requests.insert_one({
            "id": "sr-uji", "kode_satker": "111111", "created_by": "operator",
            "status": "terkirim", "signers": [{
                "signer_id": "orang-1", "nama": "Pegawai Uji", "nip": nomor,
                "jabatan": "Konsultan Individu", "status": "aktif", "jti": "jti-uji",
            }],
        })
        detail = await rt.detail_permintaan("sr-uji", {
            "username": "operator", "role": "admin", "kode_satker": "111111",
        })
        signer = detail["signers"][0]
        assert signer["nip"] == nomor and signer["label_identitas"] == "NIK"
        assert "jti" not in signer
        publik = (await rt.verifikasi_publik("sr-uji"))["penanda_tangan"][0]
        assert publik["nip"] == "•" * 13 + "001"
        assert publik["label_identitas"] == "NIK"
        assert "jti" not in publik and "signature_file_id" not in publik
        tersimpan = await database.signature_requests.find_one({"id": "sr-uji"})
        assert "label_identitas" not in tersimpan["signers"][0]
        assert tersimpan["signers"][0]["nip"] == nomor

    asyncio.run(skenario())
