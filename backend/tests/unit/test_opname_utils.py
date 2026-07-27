"""Uji helper murni rekonsiliasi opname (Fase 11).

Yang dijaga berkas ini bukan "fungsinya jalan", melainkan empat keputusan yang
kalau salah menghasilkan catatan opname yang MEYAKINKAN tetapi keliru:
stiker ber-NUP kosong yang tak pernah terpindai, scan di level gedung yang
dianggap perpindahan lalu menurunkan presisi ruangan, pindaian ulang yang
membekukan keadaan lama, dan ruangan kosong yang dilaporkan "100% selesai".
"""
import opname_utils as ou


class TestNormalisasiKode:
    def test_format_stiker_pagar(self):
        assert ou.normalisasi_kode("#3.05.01.05.007-12") == "3.05.01.05.007-12"
        assert ou.normalisasi_kode("  #REG-2024-001  ") == "REG-2024-001"

    def test_idempoten_atas_hasilnya_sendiri(self):
        # Klien sudah mengekstrak sebelum mengirim; server menormalkan lagi
        # sebagai jaring pengaman. Dua kali jalan harus sama dengan sekali.
        sekali = ou.normalisasi_kode("#3.05.01.05.007-12")
        assert ou.normalisasi_kode(sekali) == sekali

    def test_url_ambil_ruas_terakhir_yang_mirip_kode(self):
        assert ou.normalisasi_kode(
            "https://aman.example.id/aset/3.05.01.05.007") == "3.05.01.05.007"

    def test_teks_multi_bagian_ambil_token_terpanjang(self):
        # Datanya WAJIB punya lebih dari satu token ≥4 huruf, dan yang
        # terpanjang bukan yang pertama — kalau tidak, `token[0]` dan
        # `token[-1]` sama-sama meluluskan uji ini (temuan audit).
        assert ou.normalisasi_kode("ABCD;3.05.01.05.007") == "3.05.01.05.007"
        assert ou.normalisasi_kode("3.05.01.05.007|12") == "3.05.01.05.007"

    def test_kosong_dan_sampah(self):
        assert ou.normalisasi_kode("") == ""
        assert ou.normalisasi_kode(None) == ""
        assert ou.normalisasi_kode("   ") == ""

    def test_dipotong_pada_panjang_wajar(self):
        assert len(ou.normalisasi_kode("x" * 500)) <= ou.MAKS_PANJANG_KODE


class TestKandidatKriteria:
    def test_dua_bentuk_stiker_sama_sama_dicoba(self):
        k = ou.kandidat_kriteria("3.05.01.05.007-12")
        assert {"kode_register": "3.05.01.05.007-12"} in k
        assert {"asset_code": "3.05.01.05.007", "NUP": "12"} in k

    def test_nup_nol_juga_mencari_nup_kosong(self):
        # Stiker mencetak `nup or '0'` — aset ber-NUP kosong tercetak "-0".
        # Tanpa cabang ini stiker itu MUSTAHIL terpindai selamanya.
        k = ou.kandidat_kriteria("3.05.01.05.007-0")
        assert {"asset_code": "3.05.01.05.007",
                "NUP": {"$in": ["0", "", None]}} in k

    def test_kode_polos_tanpa_tanda_hubung(self):
        k = ou.kandidat_kriteria("REG001")
        assert {"kode_register": "REG001"} in k
        assert {"asset_code": "REG001"} in k
        assert len(k) == 2

    def test_kosong_tak_menghasilkan_kriteria(self):
        # Kriteria kosong tak boleh jadi `$or: []` — Mongo menolaknya, dan
        # lebih buruk: `$or` kosong yang lolos akan mencocokkan SEMUA aset.
        assert ou.kandidat_kriteria("") == []
        assert ou.kandidat_kriteria(None) == []


class TestKlasifikasiScan:
    def test_tanpa_node_tak_pernah_memindahkan(self):
        assert ou.klasifikasi_scan("n1", "") == "tanpa_lokasi"

    def test_aset_belum_pernah_ditempatkan(self):
        assert ou.klasifikasi_scan("", "n1") == "baru"

    def test_node_sama_berarti_cocok(self):
        assert ou.klasifikasi_scan("n1", "n1") == "sesuai"

    def test_scan_di_gedung_atas_barang_di_ruangan_BUKAN_pindah(self):
        # Buku: Ruang 305 (di dalam Gedung A). Petugas memindai di pintu
        # Gedung A. Menerapkannya sebagai "pindah" akan MENURUNKAN presisi
        # dari ruangan menjadi gedung — kehilangan informasi termahal.
        assert ou.klasifikasi_scan("r305", "gedA",
                                   ancestors_lama=["kwsn", "gedA", "lt3"]) == "sesuai"

    def test_scan_di_ruangan_atas_barang_di_gedung_TETAP_pindah(self):
        # Kebalikannya justru MEMPERTAJAM lokasi — layak diusulkan.
        assert ou.klasifikasi_scan("gedA", "r305",
                                   ancestors_lama=["kwsn"]) == "pindah"

    def test_ruangan_lain_di_gedung_yang_sama_tetap_pindah(self):
        assert ou.klasifikasi_scan("r305", "r307",
                                   ancestors_lama=["kwsn", "gedA", "lt3"]) == "pindah"

    def test_ancestors_berisi_none_tak_meledak(self):
        assert ou.klasifikasi_scan("r1", "r2", ancestors_lama=[None, ""]) == "pindah"


class TestScanTerakhirPerAset:
    def test_yang_berlaku_adalah_pengamatan_terakhir(self):
        scans = [
            {"asset_id": "a1", "pada": "2026-07-01T08:00:00+00:00", "node_id": "r1"},
            {"asset_id": "a1", "pada": "2026-07-01T10:00:00+00:00", "node_id": "r2"},
        ]
        assert ou.scan_terakhir_per_aset(scans)["a1"]["node_id"] == "r2"

    def test_urutan_masukan_tak_mengubah_hasil(self):
        scans = [
            {"asset_id": "a1", "pada": "2026-07-01T10:00:00+00:00", "node_id": "r2"},
            {"asset_id": "a1", "pada": "2026-07-01T08:00:00+00:00", "node_id": "r1"},
        ]
        assert ou.scan_terakhir_per_aset(scans)["a1"]["node_id"] == "r2"

    def test_baris_tanpa_asset_id_dilewati(self):
        assert ou.scan_terakhir_per_aset([{"pada": "x"}, None]) == {}


class TestRekapRekonsiliasi:
    HARAPAN = [{"id": "a1", "asset_name": "Meja"},
               {"id": "a2", "asset_name": "Kursi"},
               {"id": "a3", "asset_name": "Lemari"}]

    def test_tiga_keranjang_terpisah_benar(self):
        scans = [
            {"asset_id": "a1", "pada": "2026-07-01T08:00:00+00:00"},   # tercatat & terpindai
            {"asset_id": "a9", "pada": "2026-07-01T09:00:00+00:00"},   # terpindai, buku di tempat lain
        ]
        r = ou.rekap_rekonsiliasi(self.HARAPAN, scans)
        assert [x["id"] for x in r["sesuai"]] == ["a1"]
        assert sorted(x["id"] for x in r["belum_terpindai"]) == ["a2", "a3"]
        assert [x["asset_id"] for x in r["pindah_masuk"]] == ["a9"]
        assert r["ringkas"] == {"harapan": 3, "sesuai": 1, "belum_terpindai": 2,
                                "pindah_masuk": 1, "terpindai": 2}

    def test_pindaian_ganda_tak_menggelembungkan_hitungan(self):
        scans = [{"asset_id": "a1", "pada": "2026-07-01T08:00:00+00:00"},
                 {"asset_id": "a1", "pada": "2026-07-01T09:00:00+00:00"}]
        r = ou.rekap_rekonsiliasi(self.HARAPAN, scans)
        assert r["ringkas"]["sesuai"] == 1
        assert r["ringkas"]["terpindai"] == 1

    def test_tanpa_scan_semuanya_belum_terpindai(self):
        r = ou.rekap_rekonsiliasi(self.HARAPAN, [])
        assert r["ringkas"]["belum_terpindai"] == 3
        assert r["ringkas"]["sesuai"] == 0

    def test_lingkup_kosong_tak_meledak(self):
        r = ou.rekap_rekonsiliasi([], [])
        assert r["ringkas"]["harapan"] == 0
        assert r["pindah_masuk"] == []

    def test_pindah_masuk_terbaru_di_atas(self):
        scans = [{"asset_id": "a8", "pada": "2026-07-01T08:00:00+00:00"},
                 {"asset_id": "a9", "pada": "2026-07-01T11:00:00+00:00"}]
        r = ou.rekap_rekonsiliasi(self.HARAPAN, scans)
        assert [x["asset_id"] for x in r["pindah_masuk"]] == ["a9", "a8"]


class TestPersenTerkonfirmasi:
    def test_hitungan_biasa(self):
        assert ou.persen_terkonfirmasi({"harapan": 4, "sesuai": 3}) == 75.0

    def test_ruangan_kosong_bukan_ruangan_yang_sudah_diperiksa(self):
        # Pembagian nol yang dijawab "100%" akan melaporkan seluruh gedung
        # kosong sebagai opname yang tuntas.
        assert ou.persen_terkonfirmasi({"harapan": 0, "sesuai": 0}) == 0.0

    def test_masukan_rusak_tak_meledak(self):
        assert ou.persen_terkonfirmasi(None) == 0.0
        assert ou.persen_terkonfirmasi({}) == 0.0
