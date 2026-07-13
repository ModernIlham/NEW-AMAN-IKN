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

    def test_baris_csv_idle(self):
        from penggunaan_utils import HEADER_CSV_IDLE, baris_csv_idle
        assert baris_csv_idle([]) == [HEADER_CSV_IDLE]
        assert baris_csv_idle(None) == [HEADER_CSV_IDLE]
        rows = baris_csv_idle([{
            "asset_code": "30501", "NUP": "7", "asset_name": "Kursi",
            "alasan": "Tanpa pengguna", "status": "usul_serah",
            "nomor_usulan": "US-1", "nomor_bast_serah": "",
            "keterangan": "-", "created_by": "admin",
            "created_at": "2026-07-01T09:00:00",
        }])
        assert rows[0] == HEADER_CSV_IDLE
        r = rows[1]
        assert r[0] == "30501" and r[2] == "Kursi"
        assert r[4] == "Diusulkan Serah ke Pengelola"  # status → label
        assert r[9] == "2026-07-01"                     # tanggal dipangkas 10
        # Field hilang → string kosong
        kosong = baris_csv_idle([{"status": "klarifikasi"}])[1]
        assert kosong[0] == "" and kosong[4] == "Klarifikasi (diteliti penggunaannya)"


class TestPsp:
    def test_validasi_psp(self):
        from penggunaan_utils import validate_psp
        ok = {"nomor_sk": "KEP-1/MK.6/2026", "tanggal_sk": "2026-07-01",
              "jenis": "psp", "asset_ids": ["a1"]}
        assert validate_psp(ok, "2026-07-12") == []
        assert any("Nomor SK" in e for e in validate_psp(
            {**ok, "nomor_sk": " "}, "2026-07-12"))
        assert any("masa depan" in e for e in validate_psp(
            {**ok, "tanggal_sk": "2026-07-13"}, "2026-07-12"))
        assert any("Jenis" in e for e in validate_psp(
            {**ok, "jenis": "pinjam"}, "2026-07-12"))
        assert any("satu aset" in e for e in validate_psp(
            {**ok, "asset_ids": []}, "2026-07-12"))

    def test_rekap_psp_aset_unik(self):
        from penggunaan_utils import JENIS_PSP, rekap_psp
        sk = [
            # Tanpa field status (record lama) = dianggap ditetapkan
            {"jenis": "psp", "aset": [{"asset_id": "a1"}, {"asset_id": "a2"}]},
            {"jenis": "alih_status", "aset": [{"asset_id": "a2"}]},
            # Draf belum menetapkan apa pun — tak masuk cakupan aset
            {"jenis": "psp", "status_pengajuan": "draf",
             "aset": [{"asset_id": "a9"}]},
        ]
        r = rekap_psp(sk)
        assert r["jumlah_sk"] == 3 and r["aset_tercakup"] == 2
        assert r["per_jenis"]["psp"] == 2 and r["per_jenis"]["alih_status"] == 1
        assert r["per_status"]["ditetapkan"] == 2 and r["per_status"]["draf"] == 1
        assert set(JENIS_PSP) == set(r["per_jenis"])
        assert rekap_psp([])["jumlah_sk"] == 0

    def test_validasi_psp_draf(self):
        from penggunaan_utils import validate_psp
        draf = {"nomor_sk": "", "tanggal_sk": "", "jenis": "psp",
                "asset_ids": ["a1"]}
        assert validate_psp(draf, "2026-07-12", draf=True) == []
        # Tanggal (bila diisi) tetap divalidasi format + masa depan
        assert any("YYYY-MM-DD" in e for e in validate_psp(
            {**draf, "tanggal_sk": "12-07-2026"}, "2026-07-12", draf=True))
        assert any("masa depan" in e for e in validate_psp(
            {**draf, "tanggal_sk": "2026-07-13"}, "2026-07-12", draf=True))

    def test_transisi_pengajuan_psp(self):
        from penggunaan_utils import (
            STATUS_PENGAJUAN_PSP, TRANSISI_PENGAJUAN_PSP,
            status_pengajuan_psp, validate_transisi_pengajuan_psp,
        )
        hari = "2026-07-12"
        draf = {"status_pengajuan": "draf"}
        diajukan = {"status_pengajuan": "diajukan"}
        # Record lama tanpa field = ditetapkan (terminal)
        assert status_pengajuan_psp({}) == "ditetapkan"
        assert any("tidak sah" in e for e in
                   validate_transisi_pengajuan_psp({}, "diajukan", {}, hari))
        # draf → diajukan sah; draf → ditetapkan tidak (harus lewat diajukan)
        assert validate_transisi_pengajuan_psp(draf, "diajukan", {}, hari) == []
        assert any("tidak sah" in e for e in
                   validate_transisi_pengajuan_psp(draf, "ditetapkan", {}, hari))
        # Penetapan wajib nomor + tanggal SK sah
        errs = validate_transisi_pengajuan_psp(diajukan, "ditetapkan", {}, hari)
        assert any("Nomor SK" in e for e in errs)
        assert validate_transisi_pengajuan_psp(
            diajukan, "ditetapkan",
            {"nomor_sk": "KEP-2/MK.6/2026", "tanggal_sk": "2026-07-10"},
            hari) == []
        # Tolak/kembalikan wajib catatan
        assert any("Catatan" in e for e in
                   validate_transisi_pengajuan_psp(diajukan, "ditolak", {}, hari))
        assert validate_transisi_pengajuan_psp(
            diajukan, "draf", {"catatan": "lengkapi data aset"}, hari) == []
        # Registry konsisten
        for dari, tujuan in TRANSISI_PENGAJUAN_PSP.items():
            assert dari in STATUS_PENGAJUAN_PSP
            assert tujuan <= set(STATUS_PENGAJUAN_PSP)
        assert TRANSISI_PENGAJUAN_PSP["ditetapkan"] == set()
        assert TRANSISI_PENGAJUAN_PSP["ditolak"] == set()


class TestProsesPenggunaan:
    def test_validasi_proses(self):
        from penggunaan_utils import validate_proses_penggunaan
        ok = {"jenis_proses": "alih_status", "arah": "keluar",
              "pihak_asal": "Satker A", "pihak_tujuan": "K/L B",
              "asset_ids": ["x"]}
        assert validate_proses_penggunaan(ok) == []
        sementara_ok = {**ok, "jenis_proses": "penggunaan_sementara",
                        "tanggal_mulai": "2026-08-01",
                        "tanggal_berakhir": "2028-08-01"}
        assert validate_proses_penggunaan(sementara_ok) == []
        errors = validate_proses_penggunaan(
            {"jenis_proses": "pinjam", "arah": "atas", "pihak_asal": " ",
             "pihak_tujuan": "", "asset_ids": []})
        assert len(errors) == 5
        # Penggunaan sementara tanpa tanggal → error
        assert validate_proses_penggunaan(
            {**ok, "jenis_proses": "penggunaan_sementara"})

    def test_transisi_proses(self):
        from penggunaan_utils import validate_transisi_proses
        assert validate_transisi_proses(
            {"jenis_proses": "alih_status", "status": "disetujui"},
            "bast_selesai") == []
        # Lompatan ≤6 bulan khusus penggunaan sementara
        assert validate_transisi_proses(
            {"jenis_proses": "penggunaan_sementara", "status": "diajukan"},
            "berjalan") == []
        assert validate_transisi_proses(
            {"jenis_proses": "alih_status", "status": "diajukan"}, "berjalan")
        assert validate_transisi_proses(
            {"jenis_proses": "alih_status", "status": "dihapus_dibukukan"},
            "diajukan")

    def test_info_dan_rekap_proses(self):
        from penggunaan_utils import (info_proses_sementara,
                                      rekap_proses_penggunaan)
        berjalan = {"jenis_proses": "penggunaan_sementara",
                    "status": "berjalan", "tanggal_berakhir": "2026-08-01"}
        info = info_proses_sementara(berjalan, "2026-07-12")
        assert info["sisa_hari"] == 20 and info["saatnya_perpanjangan"]
        alih = {"jenis_proses": "alih_status", "status": "diajukan"}
        assert info_proses_sementara(alih, "2026-07-12")["berakhir"] is None
        r = rekap_proses_penggunaan([berjalan, alih], "2026-07-12")
        assert r["jumlah"] == 2 and r["aktif"] == 2
        assert r["segera_berakhir"] == 1
        assert r["per_jenis"]["alih_status"] == 1


class TestProsesJenisBaru:
    def test_jenis_baru(self):
        from penggunaan_utils import (JENIS_PROSES_PENGGUNAAN,
                                      validate_proses_penggunaan,
                                      validate_transisi_proses)
        assert set(JENIS_PROSES_PENGGUNAAN) == {
            "alih_status", "penggunaan_sementara",
            "dioperasikan_pihak_lain", "penggunaan_bersama"}
        base = {"arah": "keluar", "pihak_asal": "Satker A",
                "pihak_tujuan": "BUMN X", "asset_ids": ["x"],
                "tanggal_mulai": "2026-08-01",
                "tanggal_berakhir": "2031-08-01"}
        assert validate_proses_penggunaan(
            {**base, "jenis_proses": "dioperasikan_pihak_lain"}) == []
        # Berjangka baru wajib tanggal
        assert validate_proses_penggunaan(
            {"jenis_proses": "penggunaan_bersama", "arah": "masuk",
             "pihak_asal": "A", "pihak_tujuan": "B", "asset_ids": ["x"]})
        # Tanpa jalur pintas ≤6 bulan (beda dgn penggunaan sementara)
        assert validate_transisi_proses(
            {"jenis_proses": "dioperasikan_pihak_lain",
             "status": "diajukan"}, "berjalan")
        assert validate_transisi_proses(
            {"jenis_proses": "penggunaan_bersama", "status": "disetujui"},
            "berjalan") == []

    def test_pengingat_jenis_baru(self):
        from penggunaan_utils import info_proses_sementara
        t = {"jenis_proses": "dioperasikan_pihak_lain", "status": "berjalan",
             "tanggal_berakhir": "2026-08-01"}
        info = info_proses_sementara(t, "2026-07-12")
        assert info["sisa_hari"] == 20 and info["saatnya_perpanjangan"]
