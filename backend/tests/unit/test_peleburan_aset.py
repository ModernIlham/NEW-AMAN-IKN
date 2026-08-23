"""Peleburan baris pengadaan ke aset yang SUDAH tercatat (pengembangan nilai).

Permintaan pemilik: *"pastikan sistem pengadaan sekarang juga sudah dapat
melebur pengadaan jika kode asetnya sama … melalui fitur pengembangan aset
sehingga tidak merubah kuantitas barang tersebut karena tetap 1 kesatuan akan
tetapi dengan pengembangan nilai sesuai NUP yang ditunjuk (berikan peringatan
agar jika yang dikembangkan lebih dari 1 dan sasarannya hanya NUP hanya 1 maka
berikan proses harus 1 NUP 1 barang …). Dan juga pastikan fitur KDP juga dapat
dikerjakan dan dipisahkan fitur pengembangannya dengan kode barang definitif
karena masih berupa termin dan terus berkembang ke depannya."*

Yang membedakannya dari "Tautkan" yang sudah ada: menautkan hanya menyalin
kode/NUP/nama ke barisnya — NILAI asetnya tak berubah sama sekali. Untuk
belanja yang menambah nilai barang yang sudah ada, uangnya tercatat di
register pengadaan tetapi tak pernah sampai ke nilai perolehan asetnya.
"""
from peleburan_aset import (
    KODE_TRANSAKSI_LEBUR, nilai_leburan, ringkas_leburan, validate_leburan,
)

BARIS = {"kode": "3050104001", "uraian": "RAM tambahan", "jumlah": 1,
         "harga_satuan": 2_000_000}
ASET = {"asset_code": "3050104001", "NUP": "7", "asset_name": "Server Rak",
        "purchase_price": "15000000"}


class TestJalurYangSah:
    def test_kode_sama_jumlah_satu_diterima(self):
        assert validate_leburan(BARIS, ASET) == []

    def test_nilai_diambil_dari_harga_satuan(self):
        assert nilai_leburan(BARIS) == 2_000_000

    def test_ringkasnya_menjumlah_dengan_nilai_lama(self):
        r = ringkas_leburan(BARIS, ASET, "15000000")
        assert r["nilai_lama"] == 15_000_000
        assert r["nilai_ditambahkan"] == 2_000_000
        assert r["nilai_baru"] == 17_000_000
        assert r["nup"] == "7"

    def test_kode_transaksinya_202_bukan_503(self):
        """503 milik KDP. Memakainya untuk aset definitif membuat termin dan
        pengembangan aset bercampur di laporan mutasi."""
        assert KODE_TRANSAKSI_LEBUR == "202"
        assert ringkas_leburan(BARIS, ASET, 0)["kode_transaksi"] == "202"


class TestSatuNupSatuBarang:
    def test_jumlah_lebih_dari_satu_DITOLAK(self):
        """Permintaan pemilik verbatim: prosesnya harus diulang per barang.
        Menerima jumlah > 1 akan menambahkan nilai N barang ke SATU aset
        sekaligus, dan tak ada yang bisa memisahkannya kembali."""
        g = validate_leburan({**BARIS, "jumlah": 3}, ASET)
        assert any("1 NUP untuk 1 barang" in x for x in g), g
        assert any("ulangi peleburan" in x for x in g), g

    def test_jumlah_pecahan_juga_ditolak(self):
        assert validate_leburan({**BARIS, "jumlah": 1.5}, ASET) != []

    def test_pesannya_menyebut_jumlah_sebenarnya(self):
        g = validate_leburan({**BARIS, "jumlah": 4}, ASET)
        assert any("4 unit" in x for x in g), g


class TestKdpDipisahkan:
    def test_aset_KDP_ditolak_dengan_penunjuk_jalurnya(self):
        """Registry kode transaksi memisahkan keduanya sejak awal: KDP punya
        501/502/503/505, aset definitif memakai 202. Menerima KDP di sini
        mencatat termin konstruksi dengan kode aset definitif — jurnalnya
        tetap tertulis, nilainya tetap bertambah, dan tak ada galat apa pun."""
        kdp = {"asset_code": "7010101001", "NUP": "1", "asset_name": "Gedung KDP"}
        g = validate_leburan({**BARIS, "kode": "7010101001"}, kdp)
        assert any("KDP" in x and "503" in x for x in g), g

    def test_golongan_lain_TIDAK_ikut_tertolak(self):
        """Penolakan yang terlalu lebar akan mengunci jalur yang sah."""
        for gol in ("2", "3", "4", "5", "6", "8"):
            kode = f"{gol}050104001"
            assert validate_leburan({**BARIS, "kode": kode},
                                    {**ASET, "asset_code": kode}) == []


class TestSyaratLain:
    def test_kode_barang_harus_SAMA(self):
        g = validate_leburan(BARIS, {**ASET, "asset_code": "3060101001"})
        assert any("berbeda" in x for x in g), g

    def test_baris_persediaan_ditolak(self):
        g = validate_leburan({**BARIS, "kode": "1010301001"},
                             {**ASET, "asset_code": "1010301001"})
        assert any("persediaan" in x for x in g), g

    def test_baris_tanpa_kode_ditolak(self):
        assert validate_leburan({**BARIS, "kode": ""}, ASET) != []

    def test_baris_yang_sudah_tertaut_ditolak(self):
        g = validate_leburan({**BARIS, "asset_id": "a-lain"}, ASET)
        assert any("sudah tertaut" in x for x in g), g

    def test_baris_yang_sudah_jadi_persediaan_ditolak(self):
        assert validate_leburan({**BARIS, "psd_item_id": "i-1"}, ASET) != []

    def test_aset_yang_sudah_dihapus_ditolak(self):
        g = validate_leburan(BARIS, {**ASET, "dihapus": True})
        assert any("dihapus" in x for x in g), g

    def test_aset_tanpa_kode_barang_ditolak(self):
        assert validate_leburan(BARIS, {**ASET, "asset_code": ""}) != []


class TestMasukanKotor:
    def test_harga_tak_terbaca_jadi_nol_bukan_meledak(self):
        assert nilai_leburan({"harga_satuan": "entah"}) == 0.0
        assert nilai_leburan({"harga_satuan": float("nan")}) == 0.0
        assert nilai_leburan({}) == 0.0
        assert nilai_leburan(None) == 0.0

    def test_jumlah_tak_terbaca_dianggap_satu(self):
        """Baris era lama tanpa `jumlah` tak boleh tertolak hanya karena
        datanya tak lengkap — 1 adalah bacaan yang paling masuk akal."""
        assert validate_leburan({**BARIS, "jumlah": None}, ASET) == []
        assert validate_leburan({**BARIS, "jumlah": "abc"}, ASET) == []

    def test_masukan_kosong_tak_meledak(self):
        assert validate_leburan(None, None) != []
        assert ringkas_leburan(None, None, None)["nilai_baru"] == 0.0
