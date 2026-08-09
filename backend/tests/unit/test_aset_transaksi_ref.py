"""Registry 99 kode mutasi aset tetap SIMAK — penjaga anti-penyusutan daftar.

Mandat pemilik (2026-08-09): mutasi aset tetap harus mencakup BERTAMBAH
(53 kode) dan BERKURANG (46 kode). Uji ini memaku jumlah per arah dan
beberapa kode jangkar per kelompok supaya "perapian" di masa depan tidak
diam-diam menghilangkan kode (kelas cacat yang sama pernah dijaga di
test registry persediaan).
"""
from aset_transaksi_ref import (
    KODE_MUTASI_ASET, LABEL_KELOMPOK_ASET, daftar_kode_mutasi_aset,
    info_kode_aset,
)


def test_jumlah_per_arah_terpaku():
    tambah = [k for k, v in KODE_MUTASI_ASET.items() if v[1] == "bertambah"]
    kurang = [k for k, v in KODE_MUTASI_ASET.items() if v[1] == "berkurang"]
    assert len(tambah) == 53
    assert len(kurang) == 46
    assert len(KODE_MUTASI_ASET) == 99


def test_kode_jangkar_tiap_keluarga():
    # Satu wakil per keluarga prefiks — hilangnya satu keluarga pasti ketahuan.
    assert info_kode_aset("100")["uraian"] == "Saldo Awal"
    assert info_kode_aset("101") == {
        "kode": "101", "uraian": "Pembelian", "arah": "bertambah",
        "kelompok": "perolehan", "label_kelompok": "Perolehan"}
    assert info_kode_aset("301")["arah"] == "berkurang"
    assert info_kode_aset("401")["kelompok"] == "henti_guna"
    assert info_kode_aset("502")["kelompok"] == "kdp"
    assert info_kode_aset("602")["kelompok"] == "bersejarah"
    assert info_kode_aset("701")["kelompok"] == "pihak_ketiga"
    assert info_kode_aset("801")["kelompok"] == "bpybds"
    assert info_kode_aset("931")["kelompok"] == "penyusutan"
    assert info_kode_aset("955")["kelompok"] == "atr"
    assert info_kode_aset("q34")["uraian"] == "Koreksi Penyusutan Minus"
    assert info_kode_aset("ZZZ") == {}


def test_semua_kelompok_berlabel_dan_daftar_terurut():
    kel = {v[2] for v in KODE_MUTASI_ASET.values()}
    assert kel <= set(LABEL_KELOMPOK_ASET)
    d = daftar_kode_mutasi_aset()
    assert len(d) == 99
    arah = [x["arah"] for x in d]
    # bertambah semua di depan, berkurang semua di belakang (tanpa selang-seling)
    assert arah == sorted(arah, key=lambda a: 0 if a == "bertambah" else 1)
    assert d[0]["kode"] == "100"
    assert d[-1]["kode"] == "Q34"   # Qxx paling akhir
