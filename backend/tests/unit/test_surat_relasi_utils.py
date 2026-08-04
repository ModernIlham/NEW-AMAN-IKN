"""Uji pustaka relasi antar surat (murni) — label dua arah, validasi panah,
dan status keberlakuan terhitung.

Yang salah di sini tampil sebagai KEBOHONGAN buku agenda: surat yang sudah
dicabut tetap berbadge "Berlaku", dua surat saling mencabut tanpa pemenang,
atau label pasif/aktif tertukar sehingga pembaca mengira A dicabut B padahal
sebaliknya.
"""
from surat_relasi_utils import (
    JENIS_RELASI, STATUS_KEBERLAKUAN, baris_timeline, jenis_mematikan,
    label_relasi, status_keberlakuan, validate_relasi,
)

A = {"id": "a", "jenis": "keluar", "status": "disahkan", "nomor": "001"}
B = {"id": "b", "jenis": "keluar", "status": "disahkan", "nomor": "002"}


def _r(dari, ke, jenis, **extra):
    return {"dari_id": dari, "ke_id": ke, "jenis": jenis, **extra}


def test_label_dua_arah_tidak_tertukar():
    assert label_relasi("mencabut", "keluar") == "Mencabut"
    assert label_relasi("mencabut", "masuk") == "Dicabut oleh"
    assert label_relasi("mengubah", "masuk") == "Diubah oleh"
    assert label_relasi("asing", "masuk") == "asing"   # jujur, bukan crash


def test_semua_jenis_mandat_tersedia():
    """Mandat pemilik menyebut 5 kelompok — semuanya termodelkan."""
    for j in ("mencabut", "mencabut_sebagian", "mengubah", "menetapkan",
              "melaksanakan", "mendelegasikan", "membatalkan"):
        assert j in JENIS_RELASI
    assert jenis_mematikan("mencabut") and jenis_mematikan("membatalkan")
    assert not jenis_mematikan("mengubah")


def test_validasi_menolak_diri_sendiri_dan_duplikat():
    assert "dirinya sendiri" in validate_relasi(A, A, "mengubah")
    assert validate_relasi(A, B, "mengubah") == ""
    assert "sudah tercatat" in validate_relasi(
        A, B, "mengubah", sudah_ada=[_r("a", "b", "mengubah")])
    # Jenis berbeda antara pasangan yang sama tetap boleh.
    assert validate_relasi(A, B, "mencabut_sebagian",
                           sudah_ada=[_r("a", "b", "mengubah")]) == ""


def test_validasi_menolak_saling_mematikan():
    assert "saling" in validate_relasi(
        A, B, "mencabut", sudah_ada=[_r("b", "a", "membatalkan")])
    # Arah sebaliknya non-mematikan tidak menghalangi.
    assert validate_relasi(
        A, B, "mencabut", sudah_ada=[_r("b", "a", "melaksanakan")]) == ""


def test_validasi_menolak_sumber_yang_sudah_dibatalkan():
    batal = {**A, "status": "dibatalkan"}
    assert "dibatalkan" in validate_relasi(batal, B, "mencabut")


def test_keberlakuan_dicabut_jadi_tidak_berlaku():
    assert status_keberlakuan(B, [_r("a", "b", "mencabut")]) == "tidak_berlaku"
    assert status_keberlakuan(B, [_r("a", "b", "membatalkan")]) == "tidak_berlaku"


def test_keberlakuan_diubah_tetap_berlaku_dengan_perubahan():
    assert status_keberlakuan(B, [_r("a", "b", "mengubah")]) == "diubah"
    assert status_keberlakuan(B, [_r("a", "b", "mencabut_sebagian")]) == "diubah"
    # Relasi penetapan/pelaksanaan tidak mengubah keberlakuan.
    assert status_keberlakuan(B, [_r("a", "b", "menetapkan")]) == "berlaku"


def test_keberlakuan_panah_mati_tidak_ikut_dinilai():
    """Surat pencabut yang dirinya sudah dibatalkan tidak lagi mematikan
    sasaran — disaring lewat panah_hidup."""
    relasi = [_r("a", "b", "mencabut")]
    assert status_keberlakuan(B, relasi, panah_hidup=lambda r: False) == "berlaku"


def test_keberlakuan_status_surat_sendiri_menang():
    assert status_keberlakuan({**B, "status": "dibatalkan"}, []) == "tidak_berlaku"
    assert status_keberlakuan({**B, "status": "dibooking"}, []) == "draf"
    # Surat masuk tanpa relasi = berlaku (statusnya alur disposisi, bukan
    # keberlakuan naskah).
    assert status_keberlakuan({"id": "m", "jenis": "masuk",
                               "status": "diterima"}, []) == "berlaku"


def test_semua_status_keberlakuan_berlabel():
    for kode in ("berlaku", "diubah", "tidak_berlaku", "draf"):
        assert STATUS_KEBERLAKUAN[kode]


def test_timeline_terurut_dan_menaut_ujung_lain():
    surat = {**B, "riwayat": [
        {"status": "dibooking", "tanggal": "2026-08-01T01:00:00"},
        {"status": "disahkan", "tanggal": "2026-08-02T01:00:00"},
    ]}
    keluar = [_r("b", "c", "melaksanakan", created_at="2026-08-04T01:00:00",
                 ke_nomor="003")]
    masuk = [_r("a", "b", "mengubah", created_at="2026-08-03T01:00:00",
                dari_nomor="001", catatan="ralat pasal 2")]
    tl = baris_timeline(surat, keluar, masuk)
    assert [b["jenis"] for b in tl] == ["status", "status", "relasi", "relasi"]
    assert "Diubah oleh 001" in tl[2]["teks"] and "ralat pasal 2" in tl[2]["teks"]
    assert tl[2]["surat_id"] == "a" and tl[3]["surat_id"] == "c"
    assert "Melaksanakan" in tl[3]["teks"]
