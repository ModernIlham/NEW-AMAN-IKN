"""Uji parser referensi persediaan 16 digit (UC_PER032 SAKTI)."""
import pytest

from persediaan_referensi import (
    kode16, pecah_kode16, parse_teks_uc_per032, rencana_sinkron,
)

# Cuplikan NYATA dari PDF UC_PER032 (hasil ekstraksi pypdf) — termasuk header
# dua baris, judul kolom yang urutannya kacau, dan baris data.
TEKS_NYATA = """REFERENSI BARANG
UAKPB :DEPUTI PENGENDALIAN PEMBANGUNAN, TRANSFORMASI HIJAU DAN
DIGITAL
KODE UAKPB :126.01.1600.691778.000.KP
Halaman
Tanggal
 22
:
1 dari:
01-08-2026
DeskripsiKd Brng SatuanKd Barang
000001 1010301001 Pack Highlighter / Stabilo - Biru (Pack)
000002 1010301001 Pcs Highlighter / Stabilo - Biru (Pcs)
000011 1010301001 Pcs Isi Pensil Mekanik (Lead Refill) - 0.3mm (Pcs)
000099 1010301001 Box Pulpen BallLiner Hitam
"""


class TestKode16:
    def test_gabung_dan_pecah_bolak_balik(self):
        k = kode16("1010301001", "000001")
        assert k == "1010301001000001"
        assert pecah_kode16(k) == ("1010301001", "000001")

    def test_kode_barang_salah_panjang_ditolak(self):
        with pytest.raises(ValueError):
            kode16("101030100", "000001")
        with pytest.raises(ValueError):
            kode16("1010301001x", "000001")

    def test_kode_urut_salah_ditolak(self):
        with pytest.raises(ValueError):
            kode16("1010301001", "1")
        with pytest.raises(ValueError):
            kode16("1010301001", "00000a")

    def test_pecah_menolak_yang_bukan_16_digit(self):
        assert pecah_kode16("123") is None
        assert pecah_kode16("") is None
        assert pecah_kode16(None) is None
        assert pecah_kode16("1010301001-00001") is None


class TestParse:
    def test_membaca_identitas_uakpb_dan_kode_satker(self):
        h = parse_teks_uc_per032(TEKS_NYATA)
        assert h["uakpb_kode"] == "126.01.1600.691778.000.KP"
        assert h["kode_satker"] == "691778"
        assert h["uakpb_nama"].startswith("DEPUTI PENGENDALIAN")

    def test_membaca_baris_data(self):
        h = parse_teks_uc_per032(TEKS_NYATA)
        assert len(h["items"]) == 4
        it = h["items"][0]
        assert it["kode16"] == "1010301001000001"
        assert it["satuan"] == "Pack"
        assert it["deskripsi"] == "Highlighter / Stabilo - Biru (Pack)"

    def test_deskripsi_ber_tanda_kurung_dan_titik_aman(self):
        h = parse_teks_uc_per032(TEKS_NYATA)
        lead = next(i for i in h["items"] if i["kode_urut"] == "000011")
        assert lead["deskripsi"] == "Isi Pensil Mekanik (Lead Refill) - 0.3mm (Pcs)"

    def test_deskripsi_tanpa_kurung_satuan_juga_terbaca(self):
        h = parse_teks_uc_per032(TEKS_NYATA)
        box = next(i for i in h["items"] if i["kode_urut"] == "000099")
        assert box["satuan"] == "Box"
        assert box["deskripsi"] == "Pulpen BallLiner Hitam"

    def test_header_halaman_TIDAK_dianggap_galat(self):
        h = parse_teks_uc_per032(TEKS_NYATA)
        assert h["galat"] == []

    def test_baris_mirip_data_tapi_rusak_DILAPORKAN_bukan_dibuang_senyap(self):
        h = parse_teks_uc_per032("000123 10103 Pack Rusak — kode cuma 5 digit\n")
        assert h["items"] == []
        assert len(h["galat"]) == 1
        assert "000123" in h["galat"][0]

    def test_duplikat_mengambil_kemunculan_terakhir(self):
        teks = ("000001 1010301001 Pack Nama Lama\n"
                "000001 1010301001 Pcs Nama Baru\n")
        h = parse_teks_uc_per032(teks)
        assert len(h["items"]) == 1
        assert h["items"][0]["satuan"] == "Pcs"
        assert h["items"][0]["deskripsi"] == "Nama Baru"

    def test_teks_kosong_aman(self):
        h = parse_teks_uc_per032("")
        assert h["items"] == [] and h["kode_satker"] is None

    def test_uakpb_tanpa_segmen_6_digit_menghasilkan_None(self):
        h = parse_teks_uc_per032("KODE UAKPB : 126.01.KP\n")
        assert h["kode_satker"] is None


class TestRencanaSinkron:
    ITEMS = [
        {"kode16": "1010301001000001", "kode_barang": "1010301001",
         "kode_urut": "000001", "satuan": "Pack", "deskripsi": "Stabilo Biru"},
        {"kode16": "1010301001000002", "kode_barang": "1010301001",
         "kode_urut": "000002", "satuan": "Pcs", "deskripsi": "Stabilo Hijau"},
    ]

    def test_semua_baru_bila_db_kosong(self):
        r = rencana_sinkron(self.ITEMS, {})
        assert len(r["baru"]) == 2 and r["ubah"] == [] and r["hilang_dari_pdf"] == []

    def test_perubahan_nama_atau_satuan_terdeteksi(self):
        ada = {"1010301001000001": {"deskripsi": "Stabilo Biru", "satuan": "Pcs"}}
        r = rencana_sinkron(self.ITEMS, ada)
        assert [i["kode16"] for i in r["ubah"]] == ["1010301001000001"]
        assert [i["kode16"] for i in r["baru"]] == ["1010301001000002"]

    def test_identik_masuk_tetap(self):
        ada = {"1010301001000001": {"deskripsi": "Stabilo Biru", "satuan": "Pack"}}
        r = rencana_sinkron(self.ITEMS, ada)
        assert [i["kode16"] for i in r["tetap"]] == ["1010301001000001"]

    def test_yang_hilang_dari_pdf_dilaporkan_TANPA_dihapus(self):
        # Laporan bisa diunduh terfilter; menghapus referensi yang dipakai
        # transaksi adalah kerusakan data. Cukup dilaporkan.
        ada = {"9999999999000001": {"deskripsi": "Barang lama", "satuan": "Pcs"}}
        r = rencana_sinkron(self.ITEMS, ada)
        assert r["hilang_dari_pdf"] == ["9999999999000001"]
