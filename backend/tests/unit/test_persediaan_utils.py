"""Test logika murni persediaan (persediaan_utils.py + registry) — tanpa Mongo."""
import pytest

from persediaan_fields import (
    EDITABLE_FIELD_NAMES, FIELD_NAMES, MANAGED_FIELD_NAMES, PERSEDIAAN_SCALAR_FIELDS,
)
from persediaan_utils import (
    HEADER_CSV_TRANSAKSI, JENIS_KELUAR, JENIS_MASUK, KODE_PENUH_LEN,
    KODE_PREFIX_LEN, SATUAN_BAKU, baris_csv_transaksi, buat_layer,
    klasifikasi_kedaluwarsa, konsumsi_fifo, mutasi_periode,
    next_kode_penuh, next_nup, nilai_persediaan_dari_batches,
    parse_import_persediaan_rows, penyesuaian_opname, status_stok,
    stok_dari_batches, validate_kode_persediaan, validate_transaksi_keluar,
    validate_pindah_gudang, validate_transaksi_masuk,
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


class TestTransaksiMasuk:
    def test_jenis_masuk_lengkap_dengan_kode_sakti(self):
        assert set(JENIS_MASUK) == {
            "saldo_awal", "pembelian", "transfer_masuk", "hibah_masuk", "perolehan_lainnya",
        }
        for label, kode in JENIS_MASUK.values():
            assert label and kode.startswith("M")

    def test_validasi_masuk_valid(self):
        assert validate_transaksi_masuk("pembelian", 5, 12000) == (True, "")
        assert validate_transaksi_masuk("saldo_awal", 1, 0) == (True, "")

    def test_validasi_masuk_jenis_tak_dikenal(self):
        ok, err = validate_transaksi_masuk("penjualan", 5, 100)
        assert not ok and "tidak dikenal" in err

    def test_validasi_masuk_jumlah_dan_harga(self):
        assert not validate_transaksi_masuk("pembelian", 0, 100)[0]
        assert not validate_transaksi_masuk("pembelian", -3, 100)[0]
        assert not validate_transaksi_masuk("pembelian", "x", 100)[0]
        assert not validate_transaksi_masuk("pembelian", 1, -5)[0]
        assert not validate_transaksi_masuk("pembelian", 1, float("nan"))[0]

    def test_buat_layer_bentuk_baku(self):
        layer = buat_layer("b1", "2026-07-12T00:00:00", 5, 12000.0, " 2027-01-01 ", " BAST-9 ")
        assert layer == {
            "batch_id": "b1", "tanggal": "2026-07-12T00:00:00",
            "qty": 5, "harga": 12000.0, "expired": "2027-01-01", "ref": "BAST-9",
        }
        # Bentuk layer harus dibaca benar oleh penghitung stok/nilai
        assert stok_dari_batches([layer]) == 5
        assert nilai_persediaan_dari_batches([layer]) == 60000.0


class TestTransaksiKeluar:
    def test_jenis_keluar_lengkap_dengan_kode_sakti(self):
        assert set(JENIS_KELUAR) == {
            "habis_pakai", "transfer_keluar", "hibah_keluar", "usang", "rusak",
        }
        for label, kode in JENIS_KELUAR.values():
            assert label and kode.startswith("K")

    def test_validasi_keluar(self):
        assert validate_transaksi_keluar("habis_pakai", 3, 10) == (True, "")
        assert not validate_transaksi_keluar("pembelian", 3, 10)[0]   # jenis masuk ≠ keluar
        assert not validate_transaksi_keluar("habis_pakai", 0, 10)[0]
        assert not validate_transaksi_keluar("habis_pakai", 11, 10)[0]  # stok kurang
        ok, err = validate_transaksi_keluar("habis_pakai", 11, 10)
        assert "tersedia 10" in err


class TestKonsumsiFifo:
    def _layers(self):
        return [
            {"batch_id": "b2", "tanggal": "2026-02-01T00:00:00", "qty": 4, "harga": 6000.0},
            {"batch_id": "b1", "tanggal": "2026-01-01T00:00:00", "qty": 10, "harga": 5000.0},
            {"batch_id": "b3", "tanggal": "2026-03-01T00:00:00", "qty": 2, "harga": 7000.0},
        ]

    def test_layer_tertua_terkonsumsi_dulu(self):
        sisa, nilai, rincian = konsumsi_fifo(self._layers(), 3)
        assert rincian == [{"batch_id": "b1", "qty": 3, "harga": 5000.0}]
        assert nilai == 15000.0
        by = {b["batch_id"]: b for b in sisa}
        assert by["b1"]["qty"] == 7 and by["b2"]["qty"] == 4 and by["b3"]["qty"] == 2

    def test_lintas_layer_dan_layer_habis_hilang(self):
        sisa, nilai, rincian = konsumsi_fifo(self._layers(), 12)
        # 10 @5000 (b1 habis) + 2 @6000 (b2 tersisa 2)
        assert nilai == 10 * 5000 + 2 * 6000
        assert [r["batch_id"] for r in rincian] == ["b1", "b2"]
        ids = [b["batch_id"] for b in sisa]
        assert "b1" not in ids
        assert {b["batch_id"]: b["qty"] for b in sisa} == {"b2": 2, "b3": 2}

    def test_konsumsi_semua(self):
        sisa, nilai, _ = konsumsi_fifo(self._layers(), 16)
        assert sisa == []
        assert nilai == 10 * 5000 + 4 * 6000 + 2 * 7000
        assert stok_dari_batches(sisa) == 0

    def test_stok_kurang_valueerror(self):
        with pytest.raises(ValueError):
            konsumsi_fifo(self._layers(), 17)
        with pytest.raises(ValueError):
            konsumsi_fifo([], 1)
        with pytest.raises(ValueError):
            konsumsi_fifo(self._layers(), 0)

    def test_layer_qty_nol_diabaikan_dan_input_tak_termutasi(self):
        layers = self._layers() + [{"batch_id": "b0", "tanggal": "2025-01-01", "qty": 0, "harga": 1.0}]
        salinan = [dict(b) for b in layers]
        sisa, _, rincian = konsumsi_fifo(layers, 1)
        assert all(r["batch_id"] != "b0" for r in rincian)
        assert layers == salinan  # fungsi murni — argumen tidak berubah

    def test_konsistensi_dengan_penghitung_stok(self):
        layers = self._layers()
        sisa, _, _ = konsumsi_fifo(layers, 5)
        assert stok_dari_batches(sisa) == stok_dari_batches(layers) - 5


class TestParseImportPersediaan:
    def test_baris_valid_10_dan_16_digit(self):
        entries, errors, dupes = parse_import_persediaan_rows([
            {"kode_barang": "1010101001", "nama_barang": "Kertas", "satuan": "Rim",
             "batas_kritis": "5"},
            {"kode": "1010101001000002", "nup": "1", "nama": "Tinta", "merk": "Epson"},
        ])
        assert errors == [] and dupes == 0
        assert entries[0]["kode_barang"] == "1010101001"
        assert entries[0]["batas_kritis"] == 5
        assert entries[1]["kode_barang"] == "1010101001000002"
        assert entries[1]["nup"] == "1" and entries[1]["satuan"] == "Buah"  # default

    def test_error_kode_dan_nama(self):
        entries, errors, _ = parse_import_persediaan_rows([
            {"kode_barang": "3010101001", "nama_barang": "Salah golongan"},
            {"kode_barang": "1010101001", "nama_barang": ""},
        ])
        assert entries == []
        assert len(errors) == 2
        assert "Baris 2" in errors[0] and "Baris 3" in errors[1]

    def test_duplikat_identitas_baris_terakhir_menang(self):
        entries, errors, dupes = parse_import_persediaan_rows([
            {"kode_barang": "1010101001000002", "nup": "1", "nama_barang": "Lama"},
            {"kode_barang": "1010101001000002", "nup": "1", "nama_barang": "Baru"},
            {"kode_barang": "1010101001", "nama_barang": "A"},
            {"kode_barang": "1010101001", "nama_barang": "B"},  # 10 digit ≠ duplikat
        ])
        assert errors == [] and dupes == 1
        assert len(entries) == 3
        assert entries[0]["nama_barang"] == "Baru"

    def test_artefak_excel_dan_batas_kotor(self):
        entries, errors, _ = parse_import_persediaan_rows([
            {"kode_barang": "1010101001.0", "nup": "2.0", "nama_barang": "X",
             "batas_kritis": "abc", "expired_default": "2027-01-01T00:00:00"},
        ])
        assert errors == []
        assert entries[0]["kode_barang"] == "1010101001"
        assert entries[0]["nup"] == "2"
        assert entries[0]["batas_kritis"] == 0
        assert entries[0]["expired_default"] == "2027-01-01"

    def test_baris_kosong_dilewati(self):
        assert parse_import_persediaan_rows([{"kode_barang": "", "nama_barang": ""}]) == ([], [], 0)
        assert parse_import_persediaan_rows(None) == ([], [], 0)


class TestPenyesuaianOpname:
    def _layers(self):
        return [
            {"batch_id": "b1", "tanggal": "2026-01-01", "qty": 10, "harga": 5000.0},
            {"batch_id": "b2", "tanggal": "2026-02-01", "qty": 4, "harga": 6000.0},
        ]

    def test_fisik_kurang_konsumsi_fifo(self):
        baru, d = penyesuaian_opname(self._layers(), 9, "bx", "2026-07-12T00:00:00")
        assert stok_dari_batches(baru) == 9
        assert d["arah"] == "keluar" and d["jumlah"] == 5
        assert d["nilai"] == 5 * 5000  # layer tertua (b1) terkonsumsi dulu
        assert d["rincian"][0]["batch_id"] == "b1"

    def test_fisik_lebih_layer_penyesuaian_harga_termuda(self):
        baru, d = penyesuaian_opname(self._layers(), 20, "bx", "2026-07-12T00:00:00")
        assert stok_dari_batches(baru) == 20
        assert d["arah"] == "masuk" and d["jumlah"] == 6
        assert d["harga"] == 6000.0  # harga layer termuda (b2)
        assert d["nilai"] == 6 * 6000
        tambahan = [b for b in baru if b["batch_id"] == "bx"][0]
        assert tambahan["ref"] == "OPNAME" and tambahan["qty"] == 6

    def test_fisik_lebih_tanpa_layer_harga_nol(self):
        baru, d = penyesuaian_opname([], 3, "bx", "2026-07-12T00:00:00")
        assert stok_dari_batches(baru) == 3
        assert d["harga"] == 0.0 and d["nilai"] == 0.0

    def test_tanpa_selisih_atau_negatif_valueerror(self):
        with pytest.raises(ValueError):
            penyesuaian_opname(self._layers(), 14, "bx", "2026-07-12")  # sama dengan buku
        with pytest.raises(ValueError):
            penyesuaian_opname(self._layers(), -1, "bx", "2026-07-12")


class TestMutasiPeriode:
    def _jurnal(self):
        def j(pid, arah, tgl, qty, nilai):
            return {"persediaan_id": pid, "arah": arah, "timestamp": f"{tgl}T10:00:00+00:00",
                    "jumlah": qty, "total": nilai, "kode_barang": f"K-{pid}",
                    "nup": "1", "nama_barang": f"Barang {pid}"}
        return [
            j("p1", "masuk", "2026-06-01", 10, 100000),   # sebelum periode → saldo awal +10
            j("p1", "keluar", "2026-06-15", 3, 30000),    # sebelum periode → saldo awal -3
            j("p1", "masuk", "2026-07-05", 5, 60000),     # dalam periode
            j("p1", "keluar", "2026-07-10", 2, 22000),    # dalam periode
            j("p1", "masuk", "2026-08-01", 99, 999999),   # setelah periode → diabaikan
            j("p2", "masuk", "2026-07-01", 4, 40000),     # barang lain, dalam periode
            {"arah": "masuk", "timestamp": "2026-07-02", "jumlah": 1, "total": 1},  # tanpa pid → abaikan
        ]

    def test_rekap_per_barang(self):
        rekap = mutasi_periode(self._jurnal(), "2026-07-01", "2026-07-31")
        p1 = rekap["p1"]
        assert p1["saldo_awal"] == 7            # 10 - 3
        assert p1["masuk_qty"] == 5 and p1["masuk_nilai"] == 60000
        assert p1["keluar_qty"] == 2 and p1["keluar_nilai"] == 22000
        assert p1["saldo_akhir"] == 10          # 7 + 5 - 2
        p2 = rekap["p2"]
        assert p2["saldo_awal"] == 0 and p2["saldo_akhir"] == 4
        assert set(rekap) == {"p1", "p2"}

    def test_batas_periode_inklusif(self):
        rekap = mutasi_periode(self._jurnal(), "2026-07-05", "2026-07-10")
        p1 = rekap["p1"]
        assert p1["masuk_qty"] == 5 and p1["keluar_qty"] == 2  # kedua batas ikut

    def test_kosong(self):
        assert mutasi_periode([], "2026-07-01", "2026-07-31") == {}
        assert mutasi_periode(None, "2026-07-01", "2026-07-31") == {}


class TestKlasifikasiKedaluwarsa:
    def _batches(self):
        return [
            {"batch_id": "a", "qty": 5, "harga": 100, "expired": "2026-07-01"},   # lewat
            {"batch_id": "b", "qty": 3, "harga": 200, "expired": "2026-07-12"},   # tepat hari ini = lewat
            {"batch_id": "c", "qty": 2, "harga": 300, "expired": "2026-08-01"},   # segera (<=30 hari)
            {"batch_id": "d", "qty": 1, "harga": 400, "expired": "2026-12-31"},   # aman
            {"batch_id": "e", "qty": 4, "harga": 500, "expired": ""},             # tanpa expired
            {"batch_id": "f", "qty": 0, "harga": 600, "expired": "2026-07-01"},   # qty 0 diabaikan
            {"batch_id": "g", "qty": 2, "harga": 700, "expired": "31-12-2026"},   # tanggal rusak
        ]

    def test_pilah_lewat_dan_segera(self):
        lewat, segera = klasifikasi_kedaluwarsa(self._batches(), "2026-07-12", 30)
        assert [b["batch_id"] for b in lewat] == ["a", "b"]
        assert [b["batch_id"] for b in segera] == ["c"]
        assert lewat[0] == {"batch_id": "a", "qty": 5, "harga": 100.0, "expired": "2026-07-01"}

    def test_horizon_mempengaruhi_segera(self):
        _, segera_pendek = klasifikasi_kedaluwarsa(self._batches(), "2026-07-12", 7)
        assert segera_pendek == []
        _, segera_panjang = klasifikasi_kedaluwarsa(self._batches(), "2026-07-12", 365)
        assert [b["batch_id"] for b in segera_panjang] == ["c", "d"]

    def test_input_kosong_atau_tanggal_rusak(self):
        assert klasifikasi_kedaluwarsa(None, "2026-07-12") == ([], [])
        assert klasifikasi_kedaluwarsa([], "2026-07-12") == ([], [])
        assert klasifikasi_kedaluwarsa(self._batches(), "bukan-tanggal") == ([], [])


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


class TestStatusOpnameSemester:
    def test_belum_pernah_opname(self):
        from persediaan_utils import status_opname_semester
        s = status_opname_semester(None, "2026-07-12")
        assert not s["sudah"] and s["label"] == "Semester II 2026"
        assert "belum pernah" in s["pesan"]

    def test_opname_semester_lalu_tetap_diingatkan(self):
        from persediaan_utils import status_opname_semester
        s = status_opname_semester("2026-06-30", "2026-07-12")
        assert not s["sudah"] and "2026-06-30" in s["pesan"]

    def test_opname_semester_ini_tertib(self):
        from persediaan_utils import status_opname_semester
        s = status_opname_semester("2026-07-01", "2026-07-12")
        assert s["sudah"] and s["pesan"] == ""
        # Semester I: batas awal 1 Januari
        s = status_opname_semester("2026-01-01", "2026-03-15")
        assert s["sudah"] and s["label"] == "Semester I 2026"


class TestPindahGudang:
    def test_validate(self):
        assert validate_pindah_gudang("Gudang A", "Gudang B") == (True, "")
        ok, err = validate_pindah_gudang("Gudang A", "  gudang a ")
        assert not ok and "sama" in err
        ok, err = validate_pindah_gudang("Gudang A", "   ")
        assert not ok and "wajib" in err

    def test_mutasi_periode_abaikan_arah_mutasi(self):
        rows = [
            {"persediaan_id": "p1", "arah": "masuk", "jumlah": 10,
             "total": 100_000, "timestamp": "2026-07-01T00:00:00"},
            {"persediaan_id": "p1", "arah": "mutasi", "jumlah": 10,
             "total": 0, "timestamp": "2026-07-05T00:00:00"},
            {"persediaan_id": "p1", "arah": "keluar", "jumlah": 3,
             "total": 30_000, "timestamp": "2026-07-10T00:00:00"},
        ]
        r = mutasi_periode(rows, "2026-07-01", "2026-07-31")["p1"]
        assert r["masuk_qty"] == 10 and r["keluar_qty"] == 3
        assert r["saldo_akhir"] == 7  # pindah gudang tidak mengubah saldo


class TestBarisCsvTransaksi:
    def test_kosong_hanya_header(self):
        rows = baris_csv_transaksi([])
        assert rows == [HEADER_CSV_TRANSAKSI]
        assert baris_csv_transaksi(None) == [HEADER_CSV_TRANSAKSI]

    def test_masuk_lengkap_dengan_dokumen(self):
        trx = {
            "timestamp": "2026-07-13T04:05:06+00:00", "arah": "masuk",
            "jenis": "pembelian", "jenis_label": "Pembelian",
            "kode_sakti": "M01", "kode_barang": "1010101001000001",
            "nup": "1", "nama_barang": "Kertas HVS A4", "jumlah": 10,
            "harga_satuan": 45000.0, "total": 450000.0,
            "stok_sebelum": 5, "stok_sesudah": 15, "no_bukti": "BAST-1",
            "jenis_dokumen": "BAST", "tgl_dokumen": "2026-07-10",
            "no_kontrak": "K-9", "penyedia": "CV Maju", "petugas": "budi",
            "keterangan": "stok awal",
        }
        header, baris = baris_csv_transaksi([trx])
        assert header == HEADER_CSV_TRANSAKSI
        d = dict(zip(HEADER_CSV_TRANSAKSI, baris))
        assert d["tanggal"] == "2026-07-13"           # dipangkas ke tanggal
        assert d["uraian"] == "Pembelian"             # jenis_label → uraian
        assert d["kode_sakti"] == "M01" and d["jumlah"] == 10
        assert d["total"] == 450000 and d["harga_satuan"] == 45000
        assert d["penyedia"] == "CV Maju" and d["no_kontrak"] == "K-9"
        # field khas transaksi lain kosong pada 'masuk'
        assert d["unit_penerima"] == "" and d["lokasi_dari"] == ""

    def test_keluar_dan_mutasi_isi_field_masing_masing(self):
        keluar = {"timestamp": "2026-07-13", "arah": "keluar",
                  "jenis_label": "Habis Pakai", "jumlah": 3,
                  "harga_satuan": 45000.4, "total": 135001.6,
                  "unit_penerima": "Subbag Umum"}
        mutasi = {"timestamp": "2026-07-14", "arah": "mutasi",
                  "jenis_label": "Pindah Gudang",
                  "lokasi_dari": "Gudang A", "lokasi_ke": "Gudang B"}
        _, br_keluar, br_mutasi = baris_csv_transaksi([keluar, mutasi])
        dk = dict(zip(HEADER_CSV_TRANSAKSI, br_keluar))
        dm = dict(zip(HEADER_CSV_TRANSAKSI, br_mutasi))
        assert dk["unit_penerima"] == "Subbag Umum"
        assert dk["harga_satuan"] == 45000 and dk["total"] == 135002  # bulat
        assert dm["lokasi_dari"] == "Gudang A" and dm["lokasi_ke"] == "Gudang B"
        assert dm["jumlah"] == 0  # field jumlah absen → 0, bukan error

    def test_jumlah_kolom_konsisten(self):
        trx = {"arah": "opname", "nama_barang": "X"}
        rows = baris_csv_transaksi([trx])
        assert all(len(r) == len(HEADER_CSV_TRANSAKSI) for r in rows)
