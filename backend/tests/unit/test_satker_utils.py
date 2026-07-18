"""Uji resolusi kop per-satker (Mandat-2, M-SATKER — logika murni)."""
from satker_utils import PETA_KOP_SATKER, gabung_kop

GLOBAL = {
    "nama_instansi": "KEMENTERIAN KEUANGAN",
    "nama_unit_organisasi": "DITJEN KEKAYAAN NEGARA",
    "nama_sub_unit": "SEKRETARIAT",
    "alamat_instansi": "Jl. Global No. 1",
    "tempat_laporan": "Jakarta",
    "tembusan_laporan": "Irjen",
    "tahun_anggaran": "2026",
    "logo_url": "data:image/png;base64,xyz",
}


def test_tanpa_satker_kembalikan_global_utuh():
    assert gabung_kop(GLOBAL, None) == GLOBAL
    assert gabung_kop(GLOBAL, {}) == GLOBAL
    # dict baru, bukan referensi yang sama
    assert gabung_kop(GLOBAL, None) is not GLOBAL


def test_field_satker_nonkosong_menimpa_global():
    satker = {"kode_satker": "527", "nama_satker": "KPKNL Balikpapan",
              "alamat": "Jl. Satker No. 9", "tempat_laporan": "Balikpapan",
              "nama_unit_organisasi": "", "tembusan_laporan": ""}
    out = gabung_kop(GLOBAL, satker)
    # override non-kosong
    assert out["alamat_instansi"] == "Jl. Satker No. 9"
    assert out["tempat_laporan"] == "Balikpapan"
    # kosong → tetap global
    assert out["nama_unit_organisasi"] == GLOBAL["nama_unit_organisasi"]
    assert out["tembusan_laporan"] == GLOBAL["tembusan_laporan"]
    # nilai murni global tak tersentuh
    assert out["nama_instansi"] == GLOBAL["nama_instansi"]
    assert out["logo_url"] == GLOBAL["logo_url"]


def test_baris_sub_unit_default_nama_satker():
    """Baris ke-3 kop = nama satker ybs. bila profil tak mengisi sub-unit —
    inti multi-satker: kop tiap satker menampilkan namanya sendiri."""
    out = gabung_kop(GLOBAL, {"nama_satker": "KPKNL Samarinda"})
    assert out["nama_sub_unit"] == "KPKNL Samarinda"
    # tapi bila sub-unit diisi eksplisit, itu yang menang
    out2 = gabung_kop(GLOBAL, {"nama_satker": "KPKNL Samarinda",
                               "nama_sub_unit": "Seksi PKN"})
    assert out2["nama_sub_unit"] == "Seksi PKN"


def test_peta_kop_konsisten():
    # Regression: pemetaan field tidak berubah diam-diam
    assert PETA_KOP_SATKER["alamat"] == "alamat_instansi"
    assert set(PETA_KOP_SATKER) == {"nama_unit_organisasi", "nama_sub_unit",
                                    "alamat", "tempat_laporan", "tembusan_laporan"}
