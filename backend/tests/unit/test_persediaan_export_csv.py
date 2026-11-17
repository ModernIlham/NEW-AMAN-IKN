"""Uji ENDPOINT: ekspor CSV master persediaan (`GET /persediaan/export`).

Regresi PR #1082: `FIELD_NAMES` registry berubah menjadi tuple, lalu baris
`_TEMPLATE_HEADERS + ["stok", "nilai"]` melempar TypeError — tombol "Ekspor
Master Persediaan" mengembalikan 500 di SETIAP panggilan selama ±6 minggu
tanpa satu test pun menagih. Uji ini memanggil handler sungguhan.
"""
import csv
import io

import routes.persediaan as rps
from persediaan_fields import FIELD_NAMES
from test_lpb_persediaan_ppk import _jalan, _unwrap, dbx  # noqa: F401


def _baca(resp):
    teks = resp.body.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(teks)))


def test_ekspor_200_header_registry_plus_stok_nilai(dbx):
    _jalan(dbx.persediaan.insert_one({
        "id": "psd-1", "kode_satker": "527001", "kode_barang": "1010301001000001",
        "nup": "1", "nama_barang": "Kertas HVS A4", "satuan": "Rim", "merk": "SiDU",
        "keterangan": "uji", "stok": 7,
        "batches": [{"jumlah": 7, "sisa": 7, "harga_satuan": 50_000}]}))
    user = {"username": "gudang", "role": "admin", "kode_satker": "527001"}
    resp = _jalan(_unwrap(rps.export_persediaan)(_user=user))
    baris = _baca(resp)
    assert baris[0] == [*FIELD_NAMES, "stok", "nilai"]
    data = dict(zip(baris[0], baris[1]))
    # Kolom data sejajar dengan judulnya (diturunkan dari registry yang sama).
    assert data["kode_barang"] == "1010301001000001"
    assert data["nama_barang"] == "Kertas HVS A4"
    assert data["merk"] == "SiDU"
    assert data["keterangan"] == "uji"
    assert data["batas_kritis"] == "0"
    assert data["stok"] == "7"
    assert len(baris[1]) == len(baris[0])


def test_ekspor_ter_scope_satker(dbx):
    _jalan(dbx.persediaan.insert_many([
        {"id": "a", "kode_satker": "527001", "kode_barang": "1", "nup": "1",
         "nama_barang": "Milik A", "stok": 0, "batches": []},
        {"id": "b", "kode_satker": "527002", "kode_barang": "2", "nup": "1",
         "nama_barang": "Milik B", "stok": 0, "batches": []},
    ]))
    user = {"username": "a", "role": "admin", "kode_satker": "527001"}
    nama = [r[2] for r in _baca(_jalan(_unwrap(rps.export_persediaan)(_user=user)))[1:]]
    assert nama == ["Milik A"]
