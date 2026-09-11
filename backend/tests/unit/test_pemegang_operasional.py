"""Daftar pemegang operasional tidak menunggu pengesahan inventarisasi."""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rp
import shared_utils as su


USER = {"role": "admin", "kode_satker": "SAT-A"}
NIK = "6401010101900001"


def jalan(coro):
    return asyncio.run(coro)


@pytest.fixture
def dbx(monkeypatch, mongo_not_regex):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rp, "db", fake)
    monkeypatch.setattr(su, "db", fake)

    async def seed():
        await fake.inventory_activities.insert_many([
            {"id": "aktif", "kode_satker": "SAT-A", "tanggal_selesai": "9999-12-31"},
            {"id": "lain", "kode_satker": "SAT-B", "status_pengesahan": "disahkan"},
        ])
        dasar = {"user": "Pemegang Uji", "pengguna_nip": NIK,
                 "activity_id": "aktif", "asset_name": "Kursi Uji"}
        await fake.assets.insert_many([
            {**dasar, "id": "terlihat"},
            {**dasar, "id": "dummy", "category": "Data Dummy"},
            {**dasar, "id": "dihapus", "dihapus": True},
            {**dasar, "id": "lintas", "activity_id": "lain"},
        ])
        await fake.pegawai.insert_many([
            {"nip": NIK, "nama": "Pemegang Uji", "kode_satker": "SAT-A", "status_kepegawaian": "non_asn"},
            {"nip": NIK, "nama": "Rahasia satker lain", "kode_satker": "SAT-B"},
        ])
    jalan(seed())
    return fake


def test_daftar_aktif_tampil_tanpa_membuka_satker_dummy_atau_aset_dihapus(dbx):
    result = jalan(rp.daftar_pemegang(search="", page=1, page_size=50, _user=USER))
    assert result["total"] == 1
    row = result["items"][0]
    assert row["jumlah_aset"] == 1
    assert row["pegawai_master_nama"] == "Pemegang Uji"
    assert row["label_identitas"] == "NIK"


def test_detail_menggunakan_lingkup_operasional_yang_sama(dbx):
    result = jalan(rp.aset_pemegang(nama="  PEMEGANG   UJI ", nip=NIK, _user=USER))
    assert [a["id"] for a in result["items"]] == ["terlihat"]


def test_tanpa_nomor_tetap_tampil_dan_filter_laporan_final_tetap_tertutup(dbx):
    jalan(dbx.assets.update_one({"id": "terlihat"}, {"$set": {"pengguna_nip": ""}}))
    result = jalan(rp.daftar_pemegang(search="pemegang", page=1, page_size=50, _user=USER))
    assert result["total"] == 1
    assert result["items"][0]["nip"] == ""
    assert result["items"][0]["pegawai_terdaftar"] is False
    q = jalan(su.filter_aset_perhitungan({"activity_id": "aktif"}))
    assert jalan(dbx.assets.count_documents(q)) == 0


def test_lampiran_pdf_kegiatan_berjalan_memakai_data_sama(dbx, monkeypatch):
    import routes.reports as laporan
    import pypdfium2 as pdfium
    monkeypatch.setattr(laporan, "db", dbx)

    async def render():
        response = await rp.daftar_pemegang_pdf(nama="Pemegang Uji", nip=NIK, _user=USER)
        return b"".join([part async for part in response.body_iterator])
    with pdfium.PdfDocument(jalan(render())) as pdf:
        teks = "\n".join(page.get_textpage().get_text_range() for page in pdf)
    assert "Kursi Uji" in teks and "Pemegang Uji" in teks
    assert f"NIK: {NIK}" in teks
