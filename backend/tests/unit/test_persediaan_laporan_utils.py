"""Laporan persediaan gaya SAKTI — uji penyusun data murni + smoke render.

Angka-angka contoh meniru PDF resmi satker 691778 (Meterai 50 pcs ×
Rp10.000 = Rp500.000 pada akun 117111) supaya bentuk laporan bisa
dibandingkan langsung dengan contohnya.
"""
from persediaan_laporan_utils import (
    posisi_asof, susun_daftar_nonaktif, susun_lap_layer, susun_lap_mutasi,
    susun_lap_neraca, susun_lap_persediaan,
)

URAIAN_AKUN = {"117111": "Barang Konsumsi",
               "117113": "Bahan untuk Pemeliharaan"}


def _akun_of(kode):
    # meterai → 117111; bahan pemeliharaan (10105xxxxx) → 117113
    return "117113" if str(kode).startswith("10105") else "117111"


def _jurnal():
    return [
        # Meterai: masuk 91.102.844 total lalu keluar 90.602.844 → sisa 500rb
        {"persediaan_id": "p1", "arah": "masuk", "jumlah": 9110,
         "total": 91_102_844, "kode_barang": "1010309001000002",
         "nama_barang": "Meterai Tempel Rp 10.000",
         "timestamp": "2026-02-01T00:00:00"},
        {"persediaan_id": "p1", "arah": "keluar", "jumlah": 9060,
         "total": 90_602_844, "kode_barang": "1010309001000002",
         "nama_barang": "Meterai Tempel Rp 10.000",
         "timestamp": "2026-05-01T00:00:00"},
        # Bahan pemeliharaan: masuk & habis di periode
        {"persediaan_id": "p2", "arah": "masuk", "jumlah": 20,
         "total": 2_064_600, "kode_barang": "1010501001000001",
         "nama_barang": "Cat Tembok", "timestamp": "2026-03-01T00:00:00"},
        {"persediaan_id": "p2", "arah": "keluar", "jumlah": 20,
         "total": 2_064_600, "kode_barang": "1010501001000001",
         "nama_barang": "Cat Tembok", "timestamp": "2026-04-01T00:00:00"},
        # Transaksi SETELAH periode contoh — tak boleh ikut
        {"persediaan_id": "p1", "arah": "keluar", "jumlah": 10,
         "total": 100_000, "kode_barang": "1010309001000002",
         "nama_barang": "Meterai Tempel Rp 10.000",
         "timestamp": "2026-08-01T00:00:00"},
    ]


class TestPosisiAsof:
    def test_asof_menghormati_batas_tanggal(self):
        pos = posisi_asof(_jurnal(), "2026-06-30")
        assert pos["p1"]["qty"] == 50 and pos["p1"]["nilai"] == 500_000
        # p2 habis (qty 0, nilai 0) tetap ada di peta posisi (nilai 0)
        assert pos["p2"]["qty"] == 0 and pos["p2"]["nilai"] == 0
        sesudah = posisi_asof(_jurnal(), "2026-08-31")
        assert sesudah["p1"]["nilai"] == 400_000


class TestLapPersediaanDanNeraca:
    def test_persediaan_per_akun_per_kode10(self):
        pos = posisi_asof(_jurnal(), "2026-06-30")
        lap = susun_lap_persediaan(pos, _akun_of, URAIAN_AKUN,
                                   {"1010309001": "Meterai"})
        assert len(lap["akun"]) == 1                     # p2 nol → dilewati
        a = lap["akun"][0]
        assert a["akun"] == "117111" and a["nilai"] == 500_000
        assert a["baris"][0]["kode10"] == "1010309001"
        assert a["baris"][0]["uraian"] == "Meterai"
        assert lap["total"] == 500_000

    def test_neraca_akun_nol_tetap_tampil(self):
        pos = posisi_asof(_jurnal(), "2026-06-30")
        lap = susun_lap_neraca(pos, _akun_of, URAIAN_AKUN,
                               akun_terdaftar={"117111", "117113"})
        assert [b["akun"] for b in lap["baris"]] == ["117111", "117113"]
        assert lap["baris"][0]["nilai"] == 500_000
        assert lap["baris"][1]["nilai"] == 0             # pola contoh SAKTI
        assert lap["total"] == 500_000


class TestLapMutasi:
    def test_saldo_awal_tambah_kurang_akhir(self):
        # Periode Mar-Jun: saldo awal = mutasi sebelum 1 Mar (91,1 jt masuk
        # meterai), tambah = 2.064.600 (cat), kurang = 90.602.844 + 2.064.600
        lap = susun_lap_mutasi(_jurnal(), "2026-03-01", "2026-06-30",
                               _akun_of, URAIAN_AKUN)
        per = {b["akun"]: b for b in lap["baris"]}
        assert per["117111"]["awal"] == 91_102_844
        assert per["117111"]["kurang"] == 90_602_844
        assert per["117111"]["akhir"] == 500_000
        assert per["117113"]["awal"] == 0
        assert per["117113"]["tambah"] == 2_064_600
        assert per["117113"]["akhir"] == 0
        assert lap["total"]["akhir"] == 500_000

    def test_contoh_sakti_satu_periode_penuh(self):
        lap = susun_lap_mutasi(_jurnal(), "2026-01-01", "2026-06-30",
                               _akun_of, URAIAN_AKUN)
        per = {b["akun"]: b for b in lap["baris"]}
        # Persis pola contoh: awal 0, tambah 91.102.844, kurang 90.602.844
        assert per["117111"]["awal"] == 0
        assert per["117111"]["tambah"] == 91_102_844
        assert per["117111"]["kurang"] == 90_602_844


class TestLapLayer:
    def test_layer_urut_fifo_per_kode10(self):
        master = [{
            "kode_barang": "1010309001000002",
            "nama_barang": "Meterai Tempel Rp 10.000", "satuan": "Pcs",
            "batches": [
                {"batch_id": "b2", "tanggal": "2026-05-01", "qty": 20,
                 "harga": 10_000.0},
                {"batch_id": "b1", "tanggal": "2026-02-01", "qty": 30,
                 "harga": 10_000.0},
                {"batch_id": "b0", "tanggal": "2026-01-01", "qty": 0,
                 "harga": 9_000.0},   # layer habis tak tampil
            ],
        }, {"kode_barang": "1010101001000001", "nama_barang": "Kertas",
            "batches": []}]           # tanpa layer → dilewati
        lap = susun_lap_layer(master, {"1010309001": "Meterai"})
        assert len(lap["kelompok"]) == 1
        k = lap["kelompok"][0]
        assert k["kode10"] == "1010309001" and k["uraian"] == "Meterai"
        assert [b["layer"] for b in k["baris"]] == [1, 2]
        assert k["baris"][0]["qty"] == 30      # tanggal terlama = layer 1
        assert k["baris"][0]["uraian"] == "Meterai Tempel Rp 10.000 (Pcs)"
        assert lap["total"] == 500_000


def test_susun_daftar_nonaktif():
    rekap = {"p1": {"kode_barang": "1010309001000002", "nup": "1",
                    "nama_barang": "Meterai", "jumlah": 5, "nilai": 50_000,
                    "entri": []},
             "p0": {"kode_barang": "1010101001000001", "nup": "1",
                    "nama_barang": "Kertas", "jumlah": 2, "nilai": 20_000,
                    "entri": []}}
    lap = susun_daftar_nonaktif(rekap)
    assert [b["kode"] for b in lap["baris"]] == [
        "1010101001000001", "1010309001000002"]     # terurut kode
    assert lap["total_qty"] == 7 and lap["total_nilai"] == 70_000
    kosong = susun_daftar_nonaktif({})
    assert kosong["baris"] == [] and kosong["total_nilai"] == 0


def test_smoke_render_pdf_kop_dan_tabel_sakti():
    """Render nyata (ReportLab, tanpa Mongo): kop SAKTI + tabel bergaris
    harus menghasilkan bytes PDF yang sah."""
    from io import BytesIO
    from reportlab.platypus import Table
    from routes.persediaan_laporan import (
        _gaya_tabel_sakti, _kop_sakti, _p, _rp,
    )
    from routes.reports import _page_footer_factory, _std_doc

    ident = {"kode_uapb": "126", "nama_uapb": "OTORITA IBU KOTA NUSANTARA",
             "kode_uakpb": "691778",
             "nama_uakpb": "DEPUTI PENGENDALIAN PEMBANGUNAN"}
    buffer = BytesIO()
    doc = _std_doc(buffer)
    elements = _kop_sakti("LAPORAN BARANG PERSEDIAAN", "2026-06-30", ident,
                          "lap_bmn_sedia_satker", doc.width)
    data = [[_p("Kode", tebal=True, tengah=True),
             _p("Uraian", tebal=True, tengah=True),
             _p("Jumlah", tebal=True, tengah=True)],
            [_p("1010309001", tengah=True), _p("Meterai"),
             _p(_rp(500_000), kanan=True)]]
    tabel = Table(data, colWidths=[90, 300, 110])
    tabel.setStyle(_gaya_tabel_sakti())
    elements.append(tabel)
    footer = _page_footer_factory("Laporan Barang Persediaan")
    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    hasil = buffer.getvalue()
    assert hasil.startswith(b"%PDF") and len(hasil) > 1500
    assert _rp(91_102_844) == "91,102,844"
    assert _rp(None) == "0"
