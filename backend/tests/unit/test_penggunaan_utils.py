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

    def test_baris_csv_psp(self):
        from penggunaan_utils import HEADER_CSV_PSP, baris_csv_psp
        assert baris_csv_psp([]) == [HEADER_CSV_PSP]
        assert baris_csv_psp(None) == [HEADER_CSV_PSP]
        # SK multi-aset (2 aset) → 2 baris; record lama tanpa status = ditetapkan
        rows = baris_csv_psp([{
            "nomor_sk": "KEP-1", "tanggal_sk": "2026-07-01T00:00", "jenis": "psp",
            "penetap": "KPKNL", "keterangan": "-", "created_by": "budi",
            "lampiran": [{"file_id": "x"}],
            "aset": [
                {"asset_code": "3.01", "NUP": "1", "asset_name": "Mobil"},
                {"asset_code": "3.01", "NUP": "2", "asset_name": "Motor"},
            ],
        }])
        assert rows[0] == HEADER_CSV_PSP
        assert len(rows) == 3
        r1 = rows[1]
        assert r1[0] == "3.01" and r1[2] == "Mobil"
        assert r1[3] == "KEP-1" and r1[4] == "2026-07-01"   # tanggal dipangkas
        assert r1[5] == "Penetapan Status Penggunaan (PSP)"  # label jenis
        assert r1[7] == "Ditetapkan (SK terbit)"             # status default
        assert r1[8] == 1                                     # jumlah lampiran
        assert rows[2][1] == "2"
        # Draf + jenis tak dikenal + tanpa aset → 1 baris, status "Draf Usulan"
        kosong = baris_csv_psp([{"jenis": "zz", "status_pengajuan": "draf"}])[1]
        assert kosong[0] == "" and kosong[5] == "zz"
        assert kosong[7] == "Draf Usulan" and kosong[8] == 0

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

    def test_baris_csv_proses(self):
        from penggunaan_utils import HEADER_CSV_PROSES, baris_csv_proses
        assert baris_csv_proses([], "2026-07-12") == [HEADER_CSV_PROSES]
        assert baris_csv_proses(None, "2026-07-12") == [HEADER_CSV_PROSES]
        # Tiket berjangka BERJALAN dengan 2 aset → 2 baris + status_tenggat
        rows = baris_csv_proses([{
            "jenis_proses": "penggunaan_sementara", "arah": "keluar",
            "pihak_asal": "Satker A", "pihak_tujuan": "K/L B",
            "status": "berjalan", "tanggal_berakhir": "2026-08-01",
            "nomor_permohonan": "P-1", "tanggal_permohonan": "2026-06-01",
            "tanggal_mulai": "2026-06-05", "keterangan": "-",
            "created_by": "budi",
            "aset": [
                {"asset_code": "3.01", "NUP": "1", "asset_name": "Mobil"},
                {"asset_code": "3.01", "NUP": "2", "asset_name": "Motor"},
            ],
        }], "2026-07-12")
        assert rows[0] == HEADER_CSV_PROSES
        assert len(rows) == 3   # header + 2 aset
        r1 = rows[1]
        assert r1[0] == "3.01" and r1[1] == "1" and r1[2] == "Mobil"
        assert r1[3] == "Penggunaan Sementara"       # label jenis
        assert r1[4] == "Keluar (satker sebagai asal)"  # label arah
        assert r1[7] == "Berjalan"                    # label status
        assert r1[8] == "20 hari lagi (perpanjang)"   # status_tenggat ≤90
        assert rows[2][1] == "2"                       # aset kedua
        # Tiket tanpa aset → tetap satu baris (kolom aset kosong); non-berjalan
        # → status_tenggat kosong; jenis tak dikenal → apa adanya
        kosong = baris_csv_proses([{"jenis_proses": "zz", "status": "draf"}],
                                  "2026-07-12")[1]
        assert kosong[0] == "" and kosong[3] == "zz" and kosong[8] == ""


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


class TestProyeksiTerminal:
    """Temuan review #1: transisi terminal harus memproyeksikan master aset."""

    def test_alih_keluar_terminal_diproyeksikan(self):
        from penggunaan_utils import build_asset_alih_keluar_projection
        t = {"id": "tk1", "jenis_proses": "alih_status", "arah": "keluar",
             "status": "dihapus_dibukukan",
             "nomor_sk_penghapusan": "SK-9/2026",
             "tanggal_sk_penghapusan": "2026-07-10"}
        proj = build_asset_alih_keluar_projection(t, "2026-07-16T00:00:00")
        assert proj["dihapus"] is True
        p = proj["penghapusan"]
        assert p["jalur"] == "alih_status_keluar" and p["tiket_id"] == "tk1"
        assert p["nomor_sk"] == "SK-9/2026" and p["tanggal_sk"] == "2026-07-10"

    def test_alih_masuk_atau_status_lain_tidak(self):
        from penggunaan_utils import build_asset_alih_keluar_projection
        base = {"id": "x", "jenis_proses": "alih_status",
                "arah": "keluar", "status": "dihapus_dibukukan"}
        assert build_asset_alih_keluar_projection({**base, "arah": "masuk"}, "t") is None
        assert build_asset_alih_keluar_projection({**base, "status": "bast_selesai"}, "t") is None
        assert build_asset_alih_keluar_projection(
            {**base, "jenis_proses": "penggunaan_bersama"}, "t") is None
        assert build_asset_alih_keluar_projection(None, "t") is None

    def test_idle_diserahkan_diproyeksikan(self):
        from penggunaan_utils import build_asset_idle_serah_projection
        t = {"id": "id1", "status": "diserahkan", "nomor_bast_serah": "BAST-S/3"}
        proj = build_asset_idle_serah_projection(t, "2026-07-16T08:00:00")
        assert proj["dihapus"] is True
        p = proj["penghapusan"]
        assert p["jalur"] == "idle_diserahkan" and p["nomor_sk"] == "BAST-S/3"
        assert p["tanggal_sk"] == "2026-07-16"   # tanggal transisi → periode LBKP

    def test_idle_status_lain_tidak(self):
        from penggunaan_utils import build_asset_idle_serah_projection
        assert build_asset_idle_serah_projection({"status": "usul_serah"}, "t") is None
        assert build_asset_idle_serah_projection(None, "t") is None

    def test_tombstone_lbkp_menghitung_proyeksi_ini(self):
        # Aset terproyeksi alih-keluar/idle harus jadi mutasi KURANG di LBKP.
        from penggunaan_utils import build_asset_alih_keluar_projection
        from pembukuan_utils import tombstones_penghapusan
        proj = build_asset_alih_keluar_projection(
            {"id": "tk", "jenis_proses": "alih_status", "arah": "keluar",
             "status": "dihapus_dibukukan", "nomor_sk_penghapusan": "SK",
             "tanggal_sk_penghapusan": "2026-03-01"}, "now")
        aset = {"asset_code": "3010101001", "purchase_price": "1000000", **proj}
        ts = tombstones_penghapusan([aset])
        assert len(ts) == 1 and ts[0]["timestamp"] == "2026-03-01"


class TestKelompokkanPspSiman:
    """W5: PSP resmi dari data impor SIMAN V2 → kandidat register SK PSP."""

    def _aset(self, aid, no_psp, tanggal="2023-05-02", status="Digunakan Sendiri"):
        return {"id": aid, "asset_code": "3050104001", "NUP": aid[-1],
                "asset_name": "Lemari", "siman": {"referensi": {
                    "no_psp": no_psp, "tanggal_psp": tanggal,
                    "status_penggunaan": status}}}

    def test_kelompok_per_nomor_dan_urutan_terbaru(self):
        from penggunaan_utils import kelompokkan_psp_siman
        rows = [self._aset("A1", "S-1/2023", "2023-01-01"),
                self._aset("A2", "S-1/2023", "2023-01-01"),
                self._aset("A3", "S-9/2024", "2024-06-01")]
        hasil = kelompokkan_psp_siman(rows)
        assert [k["no_psp"] for k in hasil] == ["S-9/2024", "S-1/2023"]
        assert hasil[1]["jumlah"] == 2
        assert hasil[0]["sudah_tercatat"] is False
        assert len(hasil[1]["aset_belum"]) == 2

    def test_tanda_sudah_tercatat_dan_aset_tercakup(self):
        from penggunaan_utils import kelompokkan_psp_siman
        rows = [self._aset("A1", "S-1/2023"), self._aset("A2", "S-1/2023")]
        hasil = kelompokkan_psp_siman(
            rows, nomor_sk_tercatat={" s-1/2023 "},   # normalisasi case/spasi
            asset_id_tercakup={"A1"})
        assert hasil[0]["sudah_tercatat"] is True
        assert [a["asset_id"] for a in hasil[0]["aset_belum"]] == ["A2"]

    def test_tanggal_terisi_dari_aset_manapun_dan_input_kosong(self):
        from penggunaan_utils import kelompokkan_psp_siman
        rows = [self._aset("A1", "S-1/2023", tanggal="", status=""),
                self._aset("A2", "S-1/2023", tanggal="2023-05-02",
                           status="Digunakan Sendiri")]
        hasil = kelompokkan_psp_siman(rows)
        assert hasil[0]["tanggal_psp"] == "2023-05-02"
        assert hasil[0]["status_penggunaan"] == "Digunakan Sendiri"
        assert kelompokkan_psp_siman([]) == []
        assert kelompokkan_psp_siman(None) == []
        # Aset tanpa no_psp diabaikan
        assert kelompokkan_psp_siman([{"id": "X", "siman": {}}]) == []
