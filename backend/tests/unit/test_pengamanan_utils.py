"""Test logika murni pengamanan (pengamanan_utils.py) — tanpa Mongo."""
from pengamanan_utils import (
    JENIS_KEKURANGAN, ada_foto, is_sengketa, kekurangan_aset, rekap_kesehatan,
)


def _lengkap():
    return {"id": "a1", "asset_code": "3010101001", "NUP": "1",
            "asset_name": "Laptop", "kode_register": "ab12" * 8,
            "location": "Lt. 2", "user": "Budi", "bast_file_id": "f1",
            "photo_gridfs_ids": ["g1"], "inventory_status": "Ditemukan"}


class TestKekurangan:
    def test_aset_lengkap_tanpa_kekurangan(self):
        assert kekurangan_aset(_lengkap()) == []

    def test_semua_kekurangan_terdeteksi(self):
        kosong = {"photos": [], "photo_gridfs_ids": []}
        assert kekurangan_aset(kosong) == ["foto", "register", "lokasi", "pengguna", "bast"]

    def test_foto_inline_legacy_dihitung(self):
        a = {**_lengkap(), "photo_gridfs_ids": [], "photos": ["data:image/..."]}
        assert ada_foto(a) is True
        assert "foto" not in kekurangan_aset(a)

    def test_label_kekurangan_lengkap(self):
        assert set(JENIS_KEKURANGAN) == {"foto", "register", "lokasi", "pengguna", "bast"}
        assert all(JENIS_KEKURANGAN[k] for k in JENIS_KEKURANGAN)


class TestSengketa:
    def test_status_sengketa(self):
        assert is_sengketa({"inventory_status": "Sengketa"}) is True

    def test_nomor_perkara_atau_pihak(self):
        assert is_sengketa({"nomor_perkara": "12/PDT/2026"}) is True
        assert is_sengketa({"pihak_bersengketa": "PT X"}) is True
        assert is_sengketa({"inventory_status": "Ditemukan"}) is False


class TestRekap:
    def test_rekap_gabungan(self):
        assets = [
            _lengkap(),
            {"id": "a2", "asset_name": "Kursi", "photos": [], "photo_gridfs_ids": [],
             "location": "Gudang", "inventory_status": "Ditemukan"},
            {"id": "a3", "asset_name": "Tanah", "kode_register": "x", "location": "Kav B",
             "user": "Rina", "bast_file_id": "f", "photo_gridfs_ids": ["g"],
             "inventory_status": "Sengketa", "nomor_perkara": "12/PDT/2026",
             "pihak_bersengketa": "PT X", "keterangan_sengketa": "Batas lahan"},
        ]
        per, lengkap, sengketa = rekap_kesehatan(assets)
        assert lengkap == 2                      # a1 dan a3 lengkap datanya
        assert per["foto"] == 1 and per["register"] == 1
        assert per["pengguna"] == 1 and per["bast"] == 1
        assert per["lokasi"] == 0
        assert len(sengketa) == 1
        assert sengketa[0]["nomor_perkara"] == "12/PDT/2026"

    def test_kosong(self):
        per, lengkap, sengketa = rekap_kesehatan([])
        assert lengkap == 0 and sengketa == []
        assert all(v == 0 for v in per.values())
