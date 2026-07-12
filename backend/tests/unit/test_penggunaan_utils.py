"""Test logika murni penggunaan (penggunaan_utils.py) — tanpa Mongo."""
from penggunaan_utils import kunci_pemegang, rekap_pemegang


class TestKunciPemegang:
    def test_normalisasi_nama(self):
        assert kunci_pemegang({"user": "  Budi   Santoso ", "pengguna_nip": "123"}) == ("budi santoso", "123")
        assert kunci_pemegang({"user": "BUDI SANTOSO", "pengguna_nip": "123"}) == ("budi santoso", "123")

    def test_tanpa_pengguna_none(self):
        assert kunci_pemegang({"user": ""}) is None
        assert kunci_pemegang({"user": None}) is None
        assert kunci_pemegang({}) is None

    def test_nip_beda_kunci_beda(self):
        a = kunci_pemegang({"user": "Budi", "pengguna_nip": "1"})
        b = kunci_pemegang({"user": "Budi", "pengguna_nip": "2"})
        assert a != b


class TestRekapPemegang:
    def _assets(self):
        return [
            {"user": "Budi Santoso", "pengguna_nip": "197001", "bast_file_id": "f1",
             "pengguna_melekat_ke": "Individual", "activity_id": "act1"},
            {"user": "budi  santoso", "pengguna_nip": "197001", "bast_file_id": "",
             "pengguna_melekat_ke": "Individual", "activity_id": "act2"},
            {"user": "Rina", "pengguna_nip": "", "bast_file_id": "f2",
             "pengguna_melekat_ke": "Jabatan", "pengguna_jabatan": "Kabag Umum",
             "activity_id": "act1"},
            {"user": "", "bast_file_id": "f3"},  # tanpa pengguna → diabaikan
        ]

    def test_gabung_nama_ternormalisasi_dan_hitung(self):
        rows = rekap_pemegang(self._assets())
        assert len(rows) == 2
        budi = rows[0]  # 2 aset > 1 aset → urut pertama
        assert budi["nama"] == "Budi Santoso"
        assert budi["jumlah_aset"] == 2
        assert budi["jumlah_bast"] == 1
        assert budi["jumlah_kegiatan"] == 2
        assert budi["melekat_ke"] == "Individual"
        assert budi["lengkap"] is False  # 1 aset belum ber-BAST

    def test_lengkap_butuh_nip_dan_semua_bast(self):
        rows = rekap_pemegang(self._assets())
        rina = rows[1]
        assert rina["jumlah_bast"] == rina["jumlah_aset"] == 1
        assert rina["lengkap"] is False  # NIP kosong
        rows2 = rekap_pemegang([
            {"user": "Sari", "pengguna_nip": "9", "bast_file_id": "x", "activity_id": "a"},
        ])
        assert rows2[0]["lengkap"] is True

    def test_jabatan_terisi_dari_aset_pertama_yang_punya(self):
        rows = rekap_pemegang(self._assets())
        assert rows[1]["jabatan"] == "Kabag Umum"

    def test_kosong(self):
        assert rekap_pemegang([]) == []
        assert rekap_pemegang(None) == []
