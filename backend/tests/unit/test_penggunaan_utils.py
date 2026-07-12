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


class TestBmnIdle:
    def test_indikasi_idle(self):
        from penggunaan_utils import indikasi_idle
        ya, alasan = indikasi_idle({"status": "Nonaktif", "user": "Budi"})
        assert ya and "Nonaktif" in alasan
        ya, alasan = indikasi_idle({"status": "Aktif", "user": " "})
        assert ya and "pengguna" in alasan
        # Tidak Ditemukan bukan jalur idle (jalurnya penelusuran/TGR)
        ya, _ = indikasi_idle({"status": "Nonaktif", "user": "",
                               "inventory_status": "Tidak Ditemukan"})
        assert not ya
        ya, _ = indikasi_idle({"status": "Aktif", "user": "Budi"})
        assert not ya

    def test_transisi_dokumen_wajib(self):
        from penggunaan_utils import (
            STATUS_IDLE, TRANSISI_IDLE, validate_transisi_idle,
        )
        assert validate_transisi_idle("klarifikasi", "digunakan_kembali", {}) == []
        assert any("usulan" in e for e in
                   validate_transisi_idle("klarifikasi", "usul_serah", {}))
        assert validate_transisi_idle(
            "klarifikasi", "usul_serah", {"nomor_usulan": "S-1/2026"}) == []
        assert any("BAST" in e for e in
                   validate_transisi_idle("usul_serah", "diserahkan", {}))
        assert any("tidak sah" in e for e in
                   validate_transisi_idle("klarifikasi", "diserahkan", {}))
        assert TRANSISI_IDLE["diserahkan"] == set()
        for dari, tujuan in TRANSISI_IDLE.items():
            assert dari in STATUS_IDLE and tujuan <= set(STATUS_IDLE)

    def test_rekap_idle(self):
        from penggunaan_utils import rekap_idle
        r = rekap_idle([{"asset_id": "a1"}, {"asset_id": "a2"}],
                       [{"status": "klarifikasi"}, {"status": "diserahkan"}])
        assert r["kandidat"] == 2 and r["tiket"] == 2
        assert r["per_status"]["klarifikasi"] == 1
        assert r["per_status"]["diserahkan"] == 1
