"""Uji helper murni SBSK berbasis ruang nyata (Fase 15).

Yang dijaga di sini adalah hal-hal yang kalau salah menghasilkan laporan
perencanaan yang RAPI TETAPI KELIRU: standar yang tersambar baris yang salah,
ruangan yang praktis pas dilaporkan menyimpang karena pembulatan jiplakan
denah, dan gedung yang sibuk dilaporkan sebagai gedung kosong.
"""
import math

import sbsk_ruang_utils as sru
import spasial_utils as su

STANDAR = [
    {"kategori": "ruang_kerja", "peruntukan": "Menteri/pimpinan setingkat",
     "satuan": "m²", "standar": 247},
    {"kategori": "ruang_kerja", "peruntukan": "Kepala Biro", "satuan": "m²",
     "standar": 40},
    {"kategori": "kendaraan", "peruntukan": "Pejabat eselon I", "satuan": "unit",
     "standar": 1},
]


class TestCocokkanStandarRuang:
    def test_irisan_terbanyak_yang_menang_bukan_yang_pertama_ketemu(self):
        # Baris yang beririsan SEDIKIT tetapi berada LEBIH DULU di tabel tak
        # boleh menang. "Kepala Seksi" beririsan satu kata ("kepala") dengan
        # ruangan ini; kalau yang pertama-ketemu yang dipakai, standar 15 m²
        # milik seksi akan jadi acuan ruang kepala biro — dan seluruh laporan
        # luas mengukur terhadap angka yang salah.
        standar_berurut = [
            {"kategori": "ruang_kerja", "peruntukan": "Kepala Seksi",
             "satuan": "m²", "standar": 15},
            {"kategori": "ruang_kerja", "peruntukan": "Kepala Biro Umum",
             "satuan": "m²", "standar": 40},
        ]
        s = sru.cocokkan_standar_ruang("Ruang kerja Kepala Biro Umum",
                                       standar_berurut)
        assert s["peruntukan"] == "Kepala Biro Umum"
        assert s["standar"] == 40

    def test_baris_pimpinan_tak_menyambar_ruang_kepala_biro(self):
        s = sru.cocokkan_standar_ruang("Ruang kerja Kepala Biro Umum", STANDAR)
        assert s["peruntukan"] == "Kepala Biro"

    def test_kategori_selain_ruang_kerja_tak_pernah_ikut(self):
        # Baris KENDARAAN bersatuan "unit"; mencocokkannya ke ruangan berarti
        # membandingkan m² dengan unit.
        s = sru.cocokkan_standar_ruang("Ruang pejabat eselon I", STANDAR)
        assert s is None or s["kategori"] == "ruang_kerja"

    def test_tanpa_irisan_lebih_baik_kosong_daripada_keliru(self):
        assert sru.cocokkan_standar_ruang("Gudang arsip lama", STANDAR) is None

    def test_peruntukan_kosong_tak_meledak(self):
        assert sru.cocokkan_standar_ruang("", STANDAR) is None
        assert sru.cocokkan_standar_ruang(None, STANDAR) is None
        assert sru.cocokkan_standar_ruang("Kepala Biro", []) is None

    def test_kata_umum_saja_tak_cukup_untuk_mencocokkan(self):
        assert sru.cocokkan_standar_ruang("ruang kerja", STANDAR) is None


class TestStatusKesesuaian:
    def test_di_bawah_dan_melebihi(self):
        assert sru.status_kesesuaian(30, 40) == "di_bawah"
        assert sru.status_kesesuaian(60, 40) == "melebihi"

    def test_toleransi_dua_arah_menahan_presisi_palsu(self):
        # 246,8 m² vs standar 247 m² BUKAN penyimpangan — denah dijiplak,
        # ketelitiannya beberapa persen, bukan sentimeter.
        assert sru.status_kesesuaian(246.8, 247) == "sesuai"
        assert sru.status_kesesuaian(253, 247) == "sesuai"

    def test_tanpa_standar_saat_acuan_tak_ada(self):
        assert sru.status_kesesuaian(30, None) == "tanpa_standar"
        assert sru.status_kesesuaian(30, 0) == "tanpa_standar"
        assert sru.status_kesesuaian(None, 40) == "tanpa_standar"

    def test_masukan_sampah_tak_meledak(self):
        assert sru.status_kesesuaian("bukan angka", 40) == "tanpa_standar"
        assert sru.status_kesesuaian(float("nan"), 40) == "tanpa_standar"


class TestBarisRuang:
    NODE = {"id": "r1", "nama": "Ruang 305", "tipe": "RUANGAN",
            "jalur_nama": "Gedung A / Lantai 3 / Ruang 305",
            "peruntukan": "Kepala Biro Umum"}

    def test_selisih_dan_status_terisi_saat_standar_ketemu(self):
        b = sru.baris_ruang(self.NODE, 52.0, {"jumlah": 3, "pemegang": ["Budi"]},
                            STANDAR)
        assert b["standar_m2"] == 40
        assert b["selisih_m2"] == 12.0
        assert b["status"] == "melebihi"
        assert b["pemegang"] == ["Budi"]

    def test_ruangan_berisi_aset_tanpa_peruntukan_BUKAN_menganggur(self):
        # Ia kekurangan administrasi, bukan kekurangan penghuni. Menyatukannya
        # dengan ruang kosong akan melaporkan gedung sibuk sebagai gedung kosong.
        b = sru.baris_ruang({**self.NODE, "peruntukan": ""}, 30.0,
                            {"jumlah": 5, "pemegang": ["Ani"]}, STANDAR)
        assert b["menganggur"] is False
        assert b["status"] == "tanpa_standar"

    def test_ruangan_tergambar_tanpa_peruntukan_dan_tanpa_aset_menganggur(self):
        b = sru.baris_ruang({**self.NODE, "peruntukan": ""}, 30.0, None, STANDAR)
        assert b["menganggur"] is True

    def test_ruangan_tanpa_luas_bukan_ruang_menganggur(self):
        # Belum digambar = belum diketahui, bukan kosong.
        b = sru.baris_ruang({**self.NODE, "peruntukan": ""}, 0.0, None, STANDAR)
        assert b["menganggur"] is False

    def test_node_kosong_tak_meledak(self):
        b = sru.baris_ruang(None, None, None, None)
        assert b["luas_m2"] == 0.0 and b["status"] == "tanpa_standar"


class TestRekapSbskRuang:
    def test_rekap_memisahkan_menganggur_dari_tanpa_peruntukan(self):
        rows = [
            sru.baris_ruang({"id": "a", "nama": "A", "peruntukan": "Kepala Biro"},
                            40.0, {"jumlah": 2, "pemegang": ["X"]}, STANDAR),
            sru.baris_ruang({"id": "b", "nama": "B", "peruntukan": ""},
                            25.0, {"jumlah": 4, "pemegang": ["Y"]}, STANDAR),
            sru.baris_ruang({"id": "c", "nama": "C", "peruntukan": ""},
                            18.0, None, STANDAR),
        ]
        r = sru.rekap_sbsk_ruang(rows)
        assert r["jumlah_ruangan"] == 3
        assert r["berperuntukan"] == 1
        assert r["tanpa_peruntukan"] == 2      # B dan C
        assert r["menganggur"] == 1            # HANYA C
        assert r["luas_menganggur_m2"] == 18.0
        assert r["luas_total_m2"] == 83.0

    def test_kelebihan_dan_kekurangan_dijumlah_terpisah(self):
        rows = [
            sru.baris_ruang({"id": "a", "peruntukan": "Kepala Biro"}, 50.0, None, STANDAR),
            sru.baris_ruang({"id": "b", "peruntukan": "Kepala Biro"}, 30.0, None, STANDAR),
        ]
        r = sru.rekap_sbsk_ruang(rows)
        assert r["kelebihan_m2"] == 10.0
        assert r["kekurangan_m2"] == 10.0

    def test_lingkup_kosong_tak_meledak(self):
        r = sru.rekap_sbsk_ruang([])
        assert r["jumlah_ruangan"] == 0 and r["luas_total_m2"] == 0.0


class TestSebaranPerInduk:
    def test_dikelompokkan_per_induk_terdekat_dan_diurut_luas(self):
        rows = [
            {"jalur_nama": "Gedung A / Lantai 1 / R101", "luas_m2": 10,
             "jumlah_aset": 1},
            {"jalur_nama": "Gedung A / Lantai 3 / R305", "luas_m2": 50,
             "jumlah_aset": 2, "menganggur": True},
            {"jalur_nama": "Gedung A / Lantai 3 / R307", "luas_m2": 20,
             "jumlah_aset": 0},
        ]
        s = sru.sebaran_per_induk(rows)
        assert [e["induk"] for e in s] == ["Lantai 3", "Lantai 1"]
        assert s[0]["luas_m2"] == 70 and s[0]["menganggur"] == 1
        assert s[0]["jumlah_aset"] == 2

    def test_jalur_kosong_tetap_punya_keranjang(self):
        s = sru.sebaran_per_induk([{"jalur_nama": "", "luas_m2": 5}])
        assert s[0]["induk"] == "(tanpa induk)"


class TestLuasDariPoligon:
    def _kotak(self, lat0, lon0, m_lat, m_lon):
        """Persegi panjang m_lat × m_lon meter dengan sudut kiri-bawah (lat0, lon0)."""
        mlat, mlon = su.meter_per_derajat(lat0)
        dlat, dlon = m_lat / mlat, m_lon / mlon
        return {"type": "Polygon", "coordinates": [[
            [lon0, lat0], [lon0 + dlon, lat0], [lon0 + dlon, lat0 + dlat],
            [lon0, lat0 + dlat], [lon0, lat0]]]}

    def test_ruangan_10x20_meter_terhitung_200_m2(self):
        luas = su.luas_kasar_m2(self._kotak(-1.0, 116.7, 10.0, 20.0))
        assert math.isclose(luas, 200.0, rel_tol=0.01)

    def test_skala_wgs84_berbeda_nyata_dari_pendekatan_bola(self):
        # Bola MELEBIHKAN luas ~0,45% di lintang IKN. Untuk peringkat tak
        # berpengaruh; untuk angka yang masuk dokumen perencanaan, bias
        # sistematis sebesar itu tak boleh dipanggang diam-diam.
        m_lat, m_lon = su.meter_per_derajat(-1.0)
        bola = math.pi * su.RADIUS_BUMI_M / 180.0
        assert bola / m_lat > 1.004
        assert 0.99 < (bola * math.cos(math.radians(1.0))) / m_lon < 1.0

    def test_lubang_dikurangkan(self):
        luar = self._kotak(-1.0, 116.7, 20.0, 20.0)
        dalam = self._kotak(-1.0, 116.7, 10.0, 10.0)["coordinates"][0]
        geom = {"type": "Polygon", "coordinates": [luar["coordinates"][0], dalam]}
        assert math.isclose(su.luas_kasar_m2(geom), 300.0, rel_tol=0.02)

    def test_bukan_poligon_menghasilkan_nol(self):
        assert su.luas_kasar_m2({"type": "Point", "coordinates": [1, 2]}) == 0.0
        assert su.luas_kasar_m2(None) == 0.0

    def test_meter_per_derajat_di_kutub_tak_negatif(self):
        _, m_lon = su.meter_per_derajat(90.0)
        assert m_lon >= 0.0
