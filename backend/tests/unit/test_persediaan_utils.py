"""Test logika murni persediaan (persediaan_utils.py + registry) — tanpa Mongo."""
import pytest

from persediaan_fields import (
    EDITABLE_FIELD_NAMES, FIELD_NAMES, MANAGED_FIELD_NAMES, PERSEDIAAN_SCALAR_FIELDS,
)
from persediaan_utils import (
    KODE_PENUH_LEN, KODE_PREFIX_LEN, SATUAN_BAKU, next_kode_penuh, next_nup,
    nilai_persediaan_dari_batches, status_stok, stok_dari_batches,
    validate_kode_persediaan,
)


class TestValidateKode:
    def test_valid_10_dan_16_digit(self):
        assert validate_kode_persediaan("1010101001") == (True, "")
        assert validate_kode_persediaan("1010101001000001") == (True, "")

    def test_wajib_berawalan_1(self):
        ok, err = validate_kode_persediaan("3010101001")
        assert not ok and "berawalan '1'" in err

    def test_wajib_angka(self):
        ok, err = validate_kode_persediaan("10101x1001")
        assert not ok and "angka" in err

    def test_panjang_selain_10_16_ditolak(self):
        for kode in ("1", "101", "10101010011", "101010100100000"):
            ok, err = validate_kode_persediaan(kode)
            assert not ok and "Panjang" in err

    def test_kosong(self):
        ok, err = validate_kode_persediaan("")
        assert not ok and "kosong" in err


class TestNextKodePenuh:
    def test_pertama_kali(self):
        assert next_kode_penuh("1010101001", None) == "1010101001000001"

    def test_increment_dari_terbesar(self):
        assert next_kode_penuh("1010101001", "1010101001000041") == "1010101001000042"

    def test_kode_lama_rusak_fallback_000001(self):
        assert next_kode_penuh("1010101001", "1010101001XXXXXX"[:16]) == "1010101001000001"

    def test_mentok_penuh(self):
        with pytest.raises(ValueError):
            next_kode_penuh("1010101001", "1010101001999999")

    def test_konstanta_panjang(self):
        assert KODE_PREFIX_LEN == 10 and KODE_PENUH_LEN == 16


class TestNextNup:
    def test_mulai_satu(self):
        assert next_nup(None) == "1"
        assert next_nup("") == "1"

    def test_increment(self):
        assert next_nup("7") == "8"
        assert next_nup(" 12 ") == "13"

    def test_nilai_kotor(self):
        assert next_nup("abc") == "1"


class TestBatches:
    def test_stok_dan_nilai_fifo(self):
        batches = [
            {"qty": 10, "harga": 5000},
            {"qty": 3, "harga": 6000},
            {"qty": 0, "harga": 9999},
        ]
        assert stok_dari_batches(batches) == 13
        assert nilai_persediaan_dari_batches(batches) == 10 * 5000 + 3 * 6000

    def test_toleran_data_kotor(self):
        batches = [{"qty": "x", "harga": "y"}, {"qty": -5, "harga": 100}, {}]
        assert stok_dari_batches(batches) == 0
        assert nilai_persediaan_dari_batches(batches) == 0.0
        assert stok_dari_batches(None) == 0
        assert nilai_persediaan_dari_batches(None) == 0.0


class TestStatusStok:
    def test_habis_kritis_aman(self):
        assert status_stok(0, 5) == "habis"
        assert status_stok(-1, 0) == "habis"
        assert status_stok(3, 5) == "kritis"
        assert status_stok(5, 5) == "kritis"   # tepat di batas = kritis
        assert status_stok(6, 5) == "aman"
        assert status_stok(6, 0) == "aman"     # tanpa batas kritis
        assert status_stok(6, None) == "aman"
        assert status_stok(6, "x") == "aman"   # batas kotor dianggap 0


class TestRegistry:
    def test_identitas_tidak_editable(self):
        assert "kode_barang" not in EDITABLE_FIELD_NAMES
        assert "nup" not in EDITABLE_FIELD_NAMES

    def test_field_terkelola_sistem_di_luar_registry(self):
        assert MANAGED_FIELD_NAMES.isdisjoint(FIELD_NAMES)
        for wajib in ("stok", "batches", "version"):
            assert wajib in MANAGED_FIELD_NAMES

    def test_registry_konsisten(self):
        assert len(FIELD_NAMES) == len(set(FIELD_NAMES))
        assert EDITABLE_FIELD_NAMES <= set(FIELD_NAMES)
        assert all(f.label for f in PERSEDIAAN_SCALAR_FIELDS)

    def test_satuan_baku_terisi_unik(self):
        assert len(SATUAN_BAKU) >= 10
        assert len(SATUAN_BAKU) == len(set(SATUAN_BAKU))
