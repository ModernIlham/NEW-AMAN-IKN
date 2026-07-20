"""Test logika murni sinkronisasi SIMAN V2 (siman_utils.py) — tanpa Mongo."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from siman_utils import (  # noqa: E402
    banding_aset, deteksi_header, kunci_aset, nilai_terapkan, norm_kode,
    norm_kode_satker, norm_no_psp, norm_nup, norm_tanggal, parse_baris,
    petakan_header, referensi_siman, ringkas_baris_belum_tercatat,
    ringkas_import, validasi_satker,
)

HEADER_SIMAN = [
    "No", "Jenis BMN", "Kode Satker", "Nama Satker", "Kode Barang", "NUP",
    "Nama Barang", "Status BMN", "Merk", "Tipe", "Kondisi", "Umur Aset",
    "Intra / Extra", "Tanggal Perolehan", "Tanggal Pengapusan",
    "Nilai Perolehan", "Nilai Penyusutan", "Nilai Buku", "Status Penggunaan",
    "No PSP", "Tanggal PSP", "Lokasi Ruang", "Kode Register", "Nama Pengguna",
]


def _baris(**ganti):
    nilai = {
        "Kode Barang": "3030203001", "NUP": "1",
        "Nama Barang": "Perkakas Bengkel Service", "Status BMN": "Aktif",
        "Merk": "Multipurpose Hand Tool Set", "Tipe": "52pcs",
        "Kondisi": "Baik", "Umur Aset": "10", "Intra / Extra": "Intra",
        "Tanggal Perolehan": "2026-06-29 00:00:00",
        "Tanggal Pengapusan": "9999-12-31 00:00:00",
        "Nilai Perolehan": "1300000", "Nilai Penyusutan": "65000",
        "Nilai Buku": "1235000",
        "Status Penggunaan": "Digunakan sendiri untuk operasional",
        "No PSP": "", "Tanggal PSP": "9999-12-31 00:00:00",
        "Lokasi Ruang": "Belum berlokasi", "Kode Register": "REG123",
        "Nama Pengguna": "",
        "No": "1", "Jenis BMN": "MESIN", "Kode Satker": "126KP",
        "Nama Satker": "Deputi X",
    }
    nilai.update(ganti)
    return [nilai.get(h, "") for h in HEADER_SIMAN]


def _parse(**ganti):
    peta, hilang = petakan_header(HEADER_SIMAN)
    assert hilang == []
    return parse_baris(_baris(**ganti), peta)


class TestNormalisasi:
    def test_norm_kode_dan_nup(self):
        assert norm_kode("3.03.02.03.001") == "3030203001"
        assert norm_kode(3030203001) == "3030203001"
        assert norm_nup("001") == "1"
        assert norm_nup("12.0") == "12"
        assert norm_nup("") == ""
        assert norm_nup("0") == "0"

    def test_norm_tanggal_placeholder_9999_tanpa_overflow(self):
        assert norm_tanggal("9999-12-31 00:00:00") == ""
        assert norm_tanggal("2026-06-29 00:00:00") == "2026-06-29"
        assert norm_tanggal(None) == ""

    def test_kunci_aset(self):
        assert kunci_aset("3030203001", "001") == "3030203001|1"
        assert kunci_aset("", "1") == ""

    def test_norm_no_psp_placeholder_berarti_belum_psp(self):
        # Placeholder ekspor SIMAN utk barang BELUM ter-PSP → '' (bukan PSP)
        for v in ("", None, "-", "--", "0", "Tidak Ada Inputan",
                  "BELUM PSP", "belum ditetapkan", "N/A", "  -  "):
            assert norm_no_psp(v) == ""
        # Nomor SK sungguhan dipertahankan apa adanya (rapikan spasi saja)
        assert norm_no_psp(" KEP-123/MK.6/2023 ") == "KEP-123/MK.6/2023"
        assert norm_no_psp("S-11/MK.6/2023") == "S-11/MK.6/2023"

    def test_parse_no_psp_placeholder_jadi_kosong(self):
        # Barang belum PSP di file SIMAN ("-"/"Tidak Ada Inputan") TIDAK
        # boleh tersimpan sebagai nomor PSP — dulunya lolos & terhitung
        # "sudah PSP" di modul Penggunaan/timeline.
        assert _parse(**{"No PSP": "-"})["no_psp"] == ""
        assert _parse(**{"No PSP": "Tidak Ada Inputan"})["no_psp"] == ""
        assert _parse(**{"No PSP": "KEP-7/MK.6/2024"})["no_psp"] == "KEP-7/MK.6/2024"


class TestParseBaris:
    def test_header_wajib(self):
        peta, hilang = petakan_header(["No", "Nama Barang"])
        assert set(hilang) == {"kode_barang", "nup"}

    def test_parse_lengkap(self):
        b = _parse()
        assert b["kode_barang"] == "3030203001" and b["nup"] == "1"
        assert b["nilai_perolehan"] == 1300000.0
        assert b["nilai_penyusutan"] == 65000.0
        assert b["tanggal_perolehan"] == "2026-06-29"
        assert b["tanggal_penghapusan"] == ""  # placeholder 9999
        assert b["kode_register"] == "REG123"

    def test_baris_tanpa_kode_dilewati(self):
        peta, _ = petakan_header(HEADER_SIMAN)
        assert parse_baris(_baris(**{"Kode Barang": ""}), peta) is None


class TestBandingAset:
    ASET = {
        "asset_code": "3030203001", "NUP": "1",
        "category": "Perkakas Bengkel Service",
        "brand": "Multipurpose Hand Tool Set", "model": "52pcs",
        "condition": "Baik", "purchase_price": "1300000",
        "purchase_date": "2026-06-29", "user": "Budi",
        "kode_register": "REG123",
    }

    def test_cocok_tanpa_selisih(self):
        assert banding_aset(self.ASET, _parse(**{"Nama Pengguna": "Budi"})) == []

    def test_reklasifikasi_kode_terdeteksi(self):
        selisih = banding_aset(self.ASET, _parse(**{"Kode Barang": "3050104007"}))
        f = {s["field"]: s for s in selisih}
        assert "asset_code" in f
        assert f["asset_code"]["siman"] == "3050104007"
        assert f["asset_code"]["aman"] == "3030203001"

    def test_nilai_dan_kondisi_berbeda(self):
        selisih = banding_aset(self.ASET, _parse(**{
            "Nilai Perolehan": "1500000", "Kondisi": "Rusak Ringan"}))
        fields = {s["field"] for s in selisih}
        assert {"purchase_price", "condition"} <= fields

    def test_siman_kosong_bukan_selisih(self):
        # Merk kosong, lokasi 'Belum berlokasi', pengguna kosong → diabaikan.
        selisih = banding_aset(self.ASET, _parse(**{"Merk": "", "Tipe": "-"}))
        assert selisih == []

    def test_perbandingan_teks_abaikan_kapital(self):
        selisih = banding_aset(self.ASET, _parse(**{"Kondisi": "BAIK"}))
        assert selisih == []

    def test_register_kosong_di_aman_bukan_selisih(self):
        # AMAN belum punya kode_register → diadopsi saat impor, bukan selisih.
        aset = {**self.ASET, "kode_register": "", "user": "Budi"}
        assert banding_aset(aset, _parse(**{"Nama Pengguna": "Budi"})) == []

    def test_register_beda_terdeteksi(self):
        aset = {**self.ASET, "user": "Budi"}
        selisih = banding_aset(aset, _parse(**{"Kode Register": "REG999",
                                               "Nama Pengguna": "Budi"}))
        assert [s["field"] for s in selisih] == ["kode_register"]

    def test_nilai_terapkan_dari_selisih(self):
        selisih = banding_aset(self.ASET, _parse(**{"Nilai Perolehan": "1500000"}))
        item = next(s for s in selisih if s["field"] == "purchase_price")
        assert nilai_terapkan(item) == "1500000"


class TestRingkasan:
    def test_referensi_siman_terisi(self):
        r = referensi_siman(_parse())
        assert r["nilai_penyusutan"] == 65000.0
        assert r["nilai_buku"] == 1235000.0
        assert r["status_penggunaan"].startswith("Digunakan sendiri")

    def test_ringkas_import(self):
        hasil = [{"selisih": []}, {"selisih": [{"field": "condition"}]},
                 {"selisih": [{"field": "condition"}, {"field": "purchase_price"}]}]
        r = ringkas_import(hasil, [1, 2], [3])
        assert r["aset_dicek"] == 3 and r["cocok"] == 1 and r["selisih"] == 2
        assert r["per_field"] == {"condition": 2, "purchase_price": 1}
        assert r["siman_tanpa_aset"] == 2 and r["aman_tanpa_siman"] == 1


class TestDeteksiHeader:
    def test_header_di_baris_pertama(self):
        hasil = deteksi_header([HEADER_SIMAN, ("1", "MESIN", "126", "Dep")])
        assert hasil is not None
        idx, peta = hasil
        assert idx == 0 and "kode_barang" in peta and "nup" in peta

    def test_header_setelah_kop_judul(self):
        # Ekspor dengan judul/kop di baris-baris awal sebelum header tabel.
        rows = [("DAFTAR ASET SIMAN V2",), (None,), ("Per 30 Juni 2026",),
                tuple(HEADER_SIMAN), ("1", "MESIN")]
        idx, peta = deteksi_header(rows)
        assert idx == 3 and "kode_barang" in peta

    def test_tanpa_header_dikembalikan_none(self):
        assert deteksi_header([("a", "b"), ("c", "d")]) is None
        # Kolom kode barang tanpa NUP → tetap bukan header valid.
        assert deteksi_header([("Kode Barang", "Nama Barang")]) is None


class TestValidasiSatker:
    def test_norm_kode_satker(self):
        assert norm_kode_satker("126.01.1600691778.000-KP") == "126011600691778000KP"
        assert norm_kode_satker(" 126011600691778000kp ") == "126011600691778000KP"
        assert norm_kode_satker(None) == ""

    def test_cocok_bila_beririsan(self):
        r = validasi_satker({"126011600691778000KP"},
                            {"126.01.1600691778.000KP", "LAIN"})
        assert r["cocok"] is True

    def test_beda_terdeteksi(self):
        r = validasi_satker({"126011600691778000KP"}, {"999999000000000000XX"})
        assert r["cocok"] is False
        assert r["kode_file"] == ["126011600691778000KP"]

    def test_sisi_kosong_dianggap_cocok(self):
        assert validasi_satker(set(), {"X"})["cocok"] is True
        assert validasi_satker({"X"}, set())["cocok"] is True
        assert validasi_satker({""}, {"X"})["cocok"] is True

    def test_kode_6_digit_terkandung_dalam_20_digit_cocok(self):
        # AMAN 6 digit vs SIMAN V2 kode lengkap ±20 digit yang memuatnya.
        r = validasi_satker({"126011600691778000KP"}, {"160069"})
        assert r["cocok"] is True
        # Arah sebaliknya (file 6 digit, terdaftar 20 digit) juga cocok.
        r = validasi_satker({"160069"}, {"126.01.1600691778.000-KP"})
        assert r["cocok"] is True

    def test_kode_pendek_tidak_memicu_containment(self):
        # Kode <6 digit terlalu pendek untuk pencocokan terkandung —
        # hindari cocok palsu (mis. "01" ada di hampir semua kode).
        r = validasi_satker({"126011600691778000KP"}, {"01"})
        assert r["cocok"] is False


class TestRingkasBelumTercatat:
    def test_field_lengkap(self):
        b = _parse()
        r = ringkas_baris_belum_tercatat(b)
        assert r["kode_barang"] == "3030203001" and r["nup"] == "1"
        assert r["nilai_perolehan"] == 1300000.0
        assert r["kode_register"] == b["kode_register"]
        assert set(r) == {"kode_barang", "nup", "nama_barang", "merk", "tipe",
                          "kondisi", "nilai_perolehan", "tanggal_perolehan",
                          "kode_register"}
