"""Uji pengurutan & pengelompokan daftar BMN per BIDANG kode barang.

Dijaga di sini karena salahnya tidak kelihatan pada dokumen kecil: NUP
dibandingkan sebagai teks ("10" < "2") baru terasa saat satu jenis barang
mencapai dua digit, dan satu bidang yang pecah menjadi dua sekat baru terlihat
kalau data masuk tak berurutan.
"""
from kodefikasi_utils import (
    kelompokkan_per_bidang, kunci_urut_aset, urutkan_aset_bmn,
)


def _a(kode, nup, nama="Barang"):
    return {"asset_code": kode, "NUP": nup, "asset_name": nama}


def test_nup_diurut_sebagai_angka_bukan_teks():
    """NUP 2 sebelum NUP 10 — perbandingan teks akan membalik keduanya."""
    hasil = urutkan_aset_bmn([_a("3060102128", "10"), _a("3060102128", "2"),
                              _a("3060102128", "1")])
    assert [x["NUP"] for x in hasil] == ["1", "2", "10"]


def test_urut_bidang_lalu_kode_lalu_nup():
    """Kasus tangkapan layar pemilik: kamera (306) NUP 1 & 2 terpisah oleh
    VR (305) karena urutan pilih pengguna — kini berderet menurut bidang."""
    acak = [_a("3060102128", "1", "Camera Digital"),
            _a("3050105097", "1", "VR Head set"),
            _a("3060102128", "2", "Camera Digital")]
    assert [(x["asset_code"], x["NUP"]) for x in urutkan_aset_bmn(acak)] == [
        ("3050105097", "1"), ("3060102128", "1"), ("3060102128", "2")]


def test_kelompok_bidang_tak_pernah_pecah_dua_sekat():
    """Aset satu bidang yang masuk berselang-seling tetap menjadi SATU sekat
    (kalau pengelompokan tidak mengurutkan lebih dulu, bidang 306 akan muncul
    dua kali dan jumlah unitnya salah)."""
    kel = kelompokkan_per_bidang([
        _a("3060102128", "2"), _a("3050105097", "1"), _a("3060102128", "1")])
    assert [k for k, _ in kel] == ["305", "306"]
    assert [len(v) for _, v in kel] == [1, 2]


def test_jumlah_unit_per_sekat_menjumlah_seluruh_baris():
    aset = [_a("3020104001", str(i)) for i in range(1, 6)] + \
           [_a("3100102003", "1"), _a("3100102003", "2")]
    kel = kelompokkan_per_bidang(aset)
    assert dict((k, len(v)) for k, v in kel) == {"302": 5, "310": 2}
    assert sum(len(v) for _, v in kel) == len(aset)


def test_aset_tanpa_kode_atau_nup_terdorong_ke_belakang():
    """Kode/NUP kosong tidak boleh menyelinap ke depan hanya karena string
    kosong lebih kecil — barang beridentitas lengkap yang dibaca lebih dulu."""
    kel = kelompokkan_per_bidang([_a("", ""), _a("3100102003", "1")])
    assert [k for k, _ in kel] == ["310", ""]
    assert kunci_urut_aset({})[0] == 1


def test_nup_bukan_angka_tidak_menggagalkan_urutan():
    hasil = urutkan_aset_bmn([_a("3100102003", "A-1"), _a("3100102003", "2")])
    assert [x["NUP"] for x in hasil] == ["2", "A-1"]   # angka dulu, lalu teks


def test_daftar_asal_tidak_diubah():
    """Dokumen tersimpan tidak boleh ikut terurut — hanya tampilannya."""
    asal = [_a("3100102003", "2"), _a("3020104001", "1")]
    salinan = list(asal)
    urutkan_aset_bmn(asal)
    kelompokkan_per_bidang(asal)
    assert asal == salinan
