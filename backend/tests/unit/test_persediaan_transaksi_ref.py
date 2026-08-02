"""Registry 45 kode transaksi persediaan SAKTI — kunci uji:
kelengkapan daftar, koreksi makna kode warisan, dan penurunan ulang kode
dari `jenis` (baris jurnal lama tak boleh membocorkan kode salah)."""
from persediaan_transaksi_ref import (
    JENIS_KE_KODE, KODE_TRANSAKSI_PERSEDIAAN, LABEL_KELOMPOK,
    daftar_kode_transaksi, info_kode, kode_sakti_dari_jenis,
)


class TestRegistry:
    def test_45_kode_persis_sesuai_daftar_mandat(self):
        assert len(KODE_TRANSAKSI_PERSEDIAAN) == 45
        assert set(KODE_TRANSAKSI_PERSEDIAAN) == {
            "M01", "M02", "M03", "M04", "M05", "M06", "M07", "M08", "M09",
            "M10", "M11", "M12", "M13", "M14", "M15",
            "M90", "M94", "M95", "M96", "M97", "M98", "M99",
            "K01", "K02", "K03", "K04", "K05", "K06", "K07", "K08", "K09",
            "K10", "K11", "K13", "K14", "K15",
            "K90", "K96", "K97", "K98", "K99",
            "P01", "H01", "H02", "H03",
        }

    def test_makna_sakti_yang_dulu_salah_kaprah(self):
        # Lima kode ini dulu dipakai aplikasi untuk makna lain — registry
        # WAJIB memuat makna SAKTI resmi.
        assert KODE_TRANSAKSI_PERSEDIAAN["M06"][0] == "Perolehan Lainnya"
        assert KODE_TRANSAKSI_PERSEDIAAN["M07"][0] == "Internal Transfer Masuk"
        assert KODE_TRANSAKSI_PERSEDIAAN["M99"][0] == "Koreksi Kuantitas Tambah"
        assert KODE_TRANSAKSI_PERSEDIAAN["K06"][0] == "Keluar Lainnya"
        assert KODE_TRANSAKSI_PERSEDIAAN["K07"][0] == "Internal Transfer Keluar"

    def test_arah_konsisten_dengan_huruf_kode(self):
        for kode, (_uraian, arah, _kel) in KODE_TRANSAKSI_PERSEDIAAN.items():
            if kode.startswith("M"):
                assert arah in ("masuk", "nilai"), kode
            elif kode.startswith("K"):
                assert arah in ("keluar", "nilai"), kode
            elif kode == "P01":
                assert arah == "opname"
            else:
                assert kode.startswith("H") and arah == "hapus", kode

    def test_koreksi_nilai_tidak_menggeser_kuantitas(self):
        for kode in ("M97", "M98", "K97", "K98"):
            assert KODE_TRANSAKSI_PERSEDIAAN[kode][1] == "nilai", kode

    def test_semua_kelompok_punya_label(self):
        kelompok = {k for _u, _a, k in KODE_TRANSAKSI_PERSEDIAAN.values()}
        assert kelompok <= set(LABEL_KELOMPOK)


class TestPenurunanKode:
    def test_jenis_lama_dipetakan_ke_kode_sakti_benar(self):
        # kode_tersimpan warisan SENGAJA diabaikan — jenis yang menang
        assert kode_sakti_dari_jenis("reklasifikasi_masuk", "M06") == "M10"
        assert kode_sakti_dari_jenis("reklasifikasi_dari_aset", "M07") == "M11"
        assert kode_sakti_dari_jenis("perolehan_lainnya", "M99") == "M06"
        assert kode_sakti_dari_jenis("reklasifikasi_keluar", "K07") == "K10"
        assert kode_sakti_dari_jenis("opname", "OPN") == "P01"
        assert kode_sakti_dari_jenis("pembelian", "M02") == "M02"

    def test_jenis_tak_terdaftar_pakai_kode_tersimpan(self):
        # pindah_gudang memang internal non-SAKTI (kode kosong)
        assert kode_sakti_dari_jenis("pindah_gudang", "") == ""
        assert kode_sakti_dari_jenis("", "M02") == "M02"
        # "OPN" warisan tanpa jenis dikenal tak boleh bocor sebagai kode
        assert kode_sakti_dari_jenis("jenis_aneh", "OPN") == ""

    def test_setiap_jenis_menunjuk_kode_terdaftar(self):
        for jenis, kode in JENIS_KE_KODE.items():
            assert kode in KODE_TRANSAKSI_PERSEDIAAN, f"{jenis} → {kode}"


class TestDaftarReferensi:
    def test_terurut_m_k_p_h_dan_lengkap(self):
        rows = daftar_kode_transaksi()
        assert len(rows) == 45
        assert rows[0]["kode"] == "M01"
        huruf = [r["kode"][0] for r in rows]
        assert huruf == sorted(huruf, key=lambda h: "MKPH".index(h))
        assert rows[-1]["kode"] == "H03"

    def test_info_kode(self):
        info = info_kode("k05")   # huruf kecil pun dikenali
        assert info["uraian"] == "Rusak" and info["arah"] == "keluar"
        assert info["label_kelompok"] == LABEL_KELOMPOK["kondisi"]
        assert info_kode("Z99") == {}
        assert info_kode(None) == {}
