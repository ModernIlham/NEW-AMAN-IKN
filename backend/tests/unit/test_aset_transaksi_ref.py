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


def test_registry_lama_diturunkan_dari_registry_resmi():
    """mutasi_bmn_utils.KODE_TRANSAKSI_BMN (dulu subset 17 kode) kini
    diturunkan dari registry 99 kode + warisan — validasi jurnal harus
    menerima seluruh kode resmi, dan koreksi makna 305/401 mengikuti
    arah resmi SIMAK (aman: keduanya belum pernah ditulis)."""
    from mutasi_bmn_utils import (KODE_TRANSAKSI_BMN, arah_transaksi,
                                  validate_entri_mutasi)
    assert validate_entri_mutasi({
        "kode_transaksi": "502", "asset_id": "a",
        "tanggal_buku": "2026-08-09", "nilai": 1}) == []   # kode KDP diterima
    assert arah_transaksi("931") == "kurang"   # penyusutan
    assert arah_transaksi("305") == "tambah"   # resmi SIMAK: mutasi bertambah
    assert arah_transaksi("401") == "kurang"   # henti guna = berkurang
    assert arah_transaksi("205") == "kurang"   # warisan AMAN tetap sah
    assert arah_transaksi("203") == "netral"
    assert len(KODE_TRANSAKSI_BMN) == 101      # 99 resmi + 2 warisan


def test_lbp_menegatifkan_berdasar_arah_registry_bukan_prefiks():
    """Tabel 17 CaLBMN dulu menegatifkan SEMUA 3xx/4xx — salah untuk 305
    (Koreksi Pencatatan, bertambah) dan 402 (penggunaan kembali). Kini arah
    dibaca dari registry; prefiks hanya fallback kode tak dikenal."""
    from lbp_utils import susun_mutasi_per_transaksi
    hasil = susun_mutasi_per_transaksi([
        {"kode_transaksi": "305", "jumlah": 1, "nilai": 100},
        {"kode_transaksi": "402", "jumlah": 1, "nilai": 70},
        {"kode_transaksi": "931", "jumlah": 0, "nilai": 40},
        {"kode_transaksi": "205", "jumlah": 0, "nilai": 30},
        {"kode_transaksi": "302", "jumlah": 1, "nilai": 50},
    ], saldo_awal_qty=5, saldo_awal_nilai=1000)
    per = {b[0]: b for b in hasil["baris"]}
    assert per["305"][3] == 100    # bertambah — tak boleh dinegatifkan
    assert per["402"][3] == 70
    assert per["931"][3] == -40
    assert per["205"][3] == -30
    assert per["302"][3] == -50


def test_endpoint_referensi_mengirim_registry_lengkap():
    import asyncio

    import routes.mutasi_bmn as rmb

    fn = rmb.referensi_kode_mutasi
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        r = loop.run_until_complete(fn(_user={"role": "operator"}))
    finally:
        loop.close()
    assert len(r["referensi"]) == 99
    assert [w["kode"] for w in r["warisan"]] == ["203", "205"]
    assert "kdp" in r["label_kelompok"]


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
