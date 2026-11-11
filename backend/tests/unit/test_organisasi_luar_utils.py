"""Uji logika murni direktori pegawai luar (PGW-01).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kode 5.6, invarian 5.7.
"""
import pytest

import organisasi_luar_utils as olu
from organisasi_luar_utils import (FIELD_KHUSUS_BADAN, FIELD_KHUSUS_PIHAK_KETIGA,
                                   FIELD_NONAKTIF, FIELD_PRIBADI_LUAR,
                                   INDUK_DAERAH, JENIS_INSTANSI, KUNCI_IKON,
                                   TATARAN_DARI_JENIS)


def _orang_penuh():
    """Satu dokumen dengan SETIAP field PegawaiIn terisi."""
    from routes.pegawai import PegawaiIn, _bersih
    doc = {k: f"isi-{k}" for k in _bersih(PegawaiIn(nama="x"))}
    doc.update({"nama": "Budi", "nip": "198001012005011001",
                "tanggal_lahir": "1980-01-01", "jenis_kelamin": "L",
                "status": "meninggal", "tanggal_meninggal": "2026-01-02",
                "status_kepegawaian": "pns", "satker_luar_id": "s1"})
    return doc


# ── nama kunci ─────────────────────────────────────────────────────────────
def test_nama_kunci_bentuk_badan_depan_belakang_sama():
    assert olu.nama_kunci("PT. Telkom Indonesia") == olu.nama_kunci("Telkom  Indonesia, PT")
    assert olu.nama_kunci("PT Telkom Indonesia (Persero) Tbk") == "telkom indonesia"


def test_nama_kunci_tidak_menyamakan_koperasi_dan_yayasan():
    assert olu.nama_kunci("Koperasi Maju") != olu.nama_kunci("Yayasan Maju")
    assert olu.nama_kunci("") == ""


# ── tataran & ikon ─────────────────────────────────────────────────────────
def test_setiap_jenis_eksternal_punya_tepat_satu_tataran():
    assert set(JENIS_INSTANSI["eksternal"]) == set(TATARAN_DARI_JENIS)
    for jenis in JENIS_INSTANSI["eksternal"]:
        assert olu.tataran_dari_jenis("eksternal", jenis) in olu.TATARAN_EKSTERNAL


def test_tataran_pihak_ketiga_kosong():
    for jenis in JENIS_INSTANSI["pihak_ketiga"]:
        assert olu.tataran_dari_jenis("pihak_ketiga", jenis) == ""
    assert olu.tataran_dari_jenis("eksternal", "bumn") == ""


def test_induk_daerah_hanya_untuk_jenis_daerah():
    for jenis in INDUK_DAERAH:
        assert TATARAN_DARI_JENIS[jenis] == "daerah"
    for jenis_induk in INDUK_DAERAH.values():
        assert jenis_induk is None or jenis_induk in INDUK_DAERAH


def test_kunci_ikon():
    assert olu.kunci_ikon("") == "internal"
    assert olu.kunci_ikon("eksternal", "pusat") == "eksternal_pusat"
    assert olu.kunci_ikon("eksternal", "daerah") == "eksternal_daerah"
    assert olu.kunci_ikon("pihak_ketiga", "") == "pihak_ketiga"
    for args in [("",), ("eksternal", ""), ("pihak_ketiga",), ("aneh", "x")]:
        assert olu.kunci_ikon(*args) in KUNCI_IKON


def test_label_tingkat_lengkap_untuk_ikon_luar():
    assert set(olu.LABEL_TINGKAT) == set(KUNCI_IKON) - {"internal"}


# ── jenjang daerah ─────────────────────────────────────────────────────────
PROV = {"id": "p1", "jenis": "pemerintah_provinsi", "nama": "Provinsi Kalimantan Timur"}
KAB = {"id": "k1", "jenis": "pemerintah_kabkota", "nama": "Kabupaten Penajam Paser Utara",
       "induk_id": "p1", "provinsi_id": "p1", "provinsi_nama": "Provinsi Kalimantan Timur"}


@pytest.mark.parametrize("doc,induk,ditolak", [
    ({"jenis": "pemerintah_kabkota", "induk_id": ""}, None, True),
    ({"jenis": "pemerintah_kabkota", "induk_id": "k1"}, KAB, True),
    ({"jenis": "pemerintah_kabkota", "induk_id": "p1"}, PROV, False),
    ({"jenis": "pemerintah_kabkota", "induk_id": "p9"}, None, True),
    ({"jenis": "pemerintah_provinsi", "induk_id": "p1"}, PROV, True),
    ({"jenis": "pemerintah_provinsi", "induk_id": ""}, None, False),
    ({"jenis": "kementerian_lembaga", "induk_id": "p1"}, PROV, True),
    ({"jenis": "bumn", "induk_id": "p1"}, PROV, True),
    ({"jenis": "pemerintah_desa", "induk_id": "k1"}, KAB, False),
    ({"jenis": "pemerintah_desa", "induk_id": "p1"}, PROV, True),
    ({"id": "k1", "jenis": "pemerintah_kabkota", "induk_id": "k1"}, KAB, True),
])
def test_periksa_jenjang_daerah(doc, induk, ditolak):
    assert bool(olu.periksa_jenjang_daerah(doc, induk)) is ditolak


def test_salinan_jenjang_desa_memuat_kabkota_dan_provinsi():
    desa = {"id": "d1", "jenis": "pemerintah_desa", "nama": "Desa Bumi Harapan"}
    assert olu.salinan_jenjang(desa, KAB) == {
        "provinsi_id": "p1", "provinsi_nama": "Provinsi Kalimantan Timur",
        "kabkota_id": "k1", "kabkota_nama": "Kabupaten Penajam Paser Utara"}


def test_salinan_jenjang_provinsi_kabkota_dan_bukan_daerah():
    assert olu.salinan_jenjang(PROV)["provinsi_id"] == "p1"
    assert olu.salinan_jenjang(PROV)["kabkota_id"] == ""
    kab = olu.salinan_jenjang({"id": "k1", "jenis": "pemerintah_kabkota",
                               "nama": "Kab"}, PROV)
    assert (kab["provinsi_id"], kab["kabkota_id"]) == ("p1", "k1")
    kl = olu.salinan_jenjang({"id": "x", "jenis": "kementerian_lembaga"})
    assert kl == {k: "" for k in olu.FIELD_JENJANG}
    assert all(isinstance(v, str) for v in kl.values())


# ── instansi & satker ──────────────────────────────────────────────────────
def test_jenis_tak_cocok_kelompok_ditolak():
    assert olu.validate_instansi_luar(
        {"kelompok": "eksternal", "jenis": "bumn", "nama": "X"})
    assert olu.validate_instansi_luar(
        {"kelompok": "pihak_ketiga", "jenis": "kementerian_lembaga", "nama": "X"})
    assert not olu.validate_instansi_luar(
        {"kelompok": "pihak_ketiga", "jenis": "bumn", "nama": "X"})
    assert olu.validate_instansi_luar({"kelompok": "internal", "jenis": "bumn",
                                       "nama": "X"})


def test_bersihkan_instansi_eksternal_mengosongkan_field_badan():
    p = {"kelompok": "eksternal", "jenis": "pemerintah_kabkota", "nama": " Kab. X ",
         "tataran": "pusat", "induk_id": "p1",
         **{f: "isi" for f in FIELD_KHUSUS_BADAN}}
    hasil = olu.bersihkan_instansi_luar(p)
    assert hasil["tataran"] == "daerah"            # turunan server, bukan klien
    assert hasil["induk_id"] == "p1"
    assert all(hasil[f] == "" for f in FIELD_KHUSUS_BADAN)
    assert hasil["nama_kunci"] == "kab x"


def test_bersihkan_instansi_non_berjenjang_induk_selalu_string_kosong():
    for jenis, kelompok in [("kementerian_lembaga", "eksternal"),
                            ("pemerintah_provinsi", "eksternal"),
                            ("bumn", "pihak_ketiga")]:
        hasil = olu.bersihkan_instansi_luar(
            {"kelompok": kelompok, "jenis": jenis, "nama": "X", "induk_id": "p1"})
        assert hasil["induk_id"] == ""


def test_bersihkan_instansi_pihak_ketiga_menyimpan_field_badan():
    hasil = olu.bersihkan_instansi_luar(
        {"kelompok": "pihak_ketiga", "jenis": "satuan_pendidikan_swasta",
         "nama": "SMA Maju", "badan_penyelenggara": "Yayasan Maju", "wadah": True})
    assert hasil["badan_penyelenggara"] == "Yayasan Maju"
    assert hasil["tataran"] == ""
    assert hasil["wadah"] is False                 # wadah hanya untuk perorangan


def test_bersihkan_satker_menurunkan_dari_instansi_bukan_klien():
    instansi = {"id": "k1", "nama": "Kab. X", "kelompok": "eksternal",
                "jenis": "pemerintah_kabkota", "provinsi_id": "p1",
                "provinsi_nama": "Prov. Y", "kabkota_id": "k1", "kabkota_nama": "Kab. X"}
    hasil = olu.bersihkan_satker_luar(
        {"nama_satker": "Dinas Pendidikan", "kelompok": "pihak_ketiga",
         "tataran": "pusat", "instansi_id": "palsu", "kode_satker": "123456"},
        instansi)
    assert (hasil["kelompok"], hasil["tataran"], hasil["instansi_id"]) == \
        ("eksternal", "daerah", "k1")
    assert hasil["provinsi_nama"] == "Prov. Y"
    assert hasil["kode_satker"] == ""


def test_validate_satker_wajib_instansi():
    assert olu.validate_satker_luar({"nama_satker": "A"})
    assert not olu.validate_satker_luar({"nama_satker": "A", "instansi_id": "i1"})


# ── orang luar ─────────────────────────────────────────────────────────────
def test_kesetaraan_skema_field_nonaktif_ada_di_pegawai_in():
    """Salah ketik nama field di FIELD_NONAKTIF gagal di sini."""
    from routes.pegawai import PegawaiIn, _bersih
    skema = set(_bersih(PegawaiIn(nama="x")))
    gabungan = set(FIELD_NONAKTIF["eksternal"]) | set(FIELD_NONAKTIF["pihak_ketiga"])
    assert gabungan <= skema, gabungan - skema


def test_eksternal_hanya_mengosongkan_pribadi_dan_field_pihak_ketiga():
    masuk = {**_orang_penuh(), **{f: "isi" for f in FIELD_KHUSUS_PIHAK_KETIGA}}
    keluar = olu.sesuaikan_orang_luar(masuk, "eksternal", "kementerian_lembaga")
    dikosongkan = set(FIELD_PRIBADI_LUAR) | set(FIELD_KHUSUS_PIHAK_KETIGA) | {"kode_satker"}
    for k, v in masuk.items():
        if k in dikosongkan:
            assert keluar[k] == "", k
        else:
            assert keluar[k] == v, k
    for f in ("nomor_kontrak", "pangkat_golongan", "eselon3"):
        assert keluar[f] == masuk[f]


def test_pihak_ketiga_non_asn_dan_field_37c_kosong():
    masuk = _orang_penuh()
    keluar = olu.sesuaikan_orang_luar(masuk, "pihak_ketiga", "bumn")
    assert keluar["status_kepegawaian"] == "non_asn"
    for f in FIELD_NONAKTIF["pihak_ketiga"]:
        assert keluar[f] == "", f
    assert keluar["nomor_kontrak"] == ""
    for f in ("nama", "nip", "jabatan", "eselon2", "tanggal_lahir",
              "tanggal_meninggal"):
        assert keluar[f] == masuk[f], f


def test_perorangan_dipaksa_diri_sendiri_tanpa_eselon():
    masuk = {**_orang_penuh(), "kapasitas_bertindak": "penerima_kuasa"}
    keluar = olu.sesuaikan_orang_luar(masuk, "pihak_ketiga", "perorangan")
    assert keluar["kapasitas_bertindak"] == "diri_sendiri"
    assert all(keluar[f"eselon{n}"] == "" for n in range(1, 6))
    assert keluar["unit_kerja"] == ""


def test_validate_orang_luar():
    dasar = {"nama": "Ani", "satker_luar_id": "s1"}
    assert not olu.validate_orang_luar(dasar, "eksternal", "kementerian_lembaga")
    assert olu.validate_orang_luar(dasar, "eksternal", "bumn")
    assert olu.validate_orang_luar({"nama": "Ani"}, "pihak_ketiga", "bumn")
    assert olu.validate_orang_luar({**dasar, "kapasitas_bertindak": "direktur"},
                                   "pihak_ketiga", "bumn")
    assert olu.validate_orang_luar({**dasar, "kapasitas_bertindak": "petugas"},
                                   "pihak_ketiga", "perorangan")
    assert olu.validate_orang_luar({**dasar, "nama": ""}, "pihak_ketiga", "bumn")


def test_peringatan_wakil_badan_tanpa_dasar_dan_petugas():
    tanpa = {"kapasitas_bertindak": "pengurus_berwenang"}
    assert olu.peringatan_orang_luar(tanpa, "pihak_ketiga")
    lengkap = {"kapasitas_bertindak": "penerima_kuasa",
               "dasar_kewenangan_jenis": "surat_kuasa",
               "dasar_kewenangan_nomor": "SK-1/2026"}
    assert not olu.peringatan_orang_luar(lengkap, "pihak_ketiga")
    assert olu.peringatan_orang_luar({"kapasitas_bertindak": "petugas"}, "pihak_ketiga")
    assert not olu.peringatan_orang_luar(tanpa, "eksternal")


# ── penampungan ────────────────────────────────────────────────────────────
def test_periksa_penampungan():
    pusat = {"kelompok": "eksternal", "tataran": "pusat"}
    daerah = {"kelompok": "eksternal", "tataran": "daerah"}
    p3 = {"kelompok": "pihak_ketiga", "tataran": ""}
    assert olu.periksa_penampungan(pusat, p3)
    assert olu.periksa_penampungan(p3, pusat)
    assert olu.periksa_penampungan(pusat, daerah)
    assert not olu.periksa_penampungan(pusat, dict(pusat))
    assert not olu.periksa_penampungan(None, p3)
    assert olu.periksa_penampungan(pusat, None)


# ── label ──────────────────────────────────────────────────────────────────
def test_label_unit_orang():
    assert olu.label_unit_orang({"unit_kerja": "Biro Umum"}) == "Biro Umum"
    assert olu.label_unit_orang({
        "kelompok": "eksternal", "jenis_instansi": "pemerintah_kabkota",
        "instansi_nama": "Kabupaten Y", "provinsi_nama": "Provinsi X",
        "satker_luar_nama": "Dinas Z", "unit_kerja": ""}) == \
        "Kabupaten Y, Provinsi X — Dinas Z"
    assert olu.label_unit_orang({
        "kelompok": "pihak_ketiga", "jenis_instansi": "bumn",
        "instansi_nama": "PT A", "satker_luar_nama": "PT A",
        "unit_kerja": "Divisi Aset"}) == "PT A — Divisi Aset"


def test_label_field_pihak_ketiga_hanya_field_pegawai_in():
    from routes.pegawai import PegawaiIn, _bersih
    assert set(olu.LABEL_FIELD["pihak_ketiga"]) <= set(_bersih(PegawaiIn(nama="x")))


def test_modul_internal_tidak_mengimpor_modul_luar():
    """Ketergantungan satu arah (aturan main 2)."""
    from pathlib import Path
    akar = Path(olu.__file__).parent
    for nama in ("pegawai_utils.py", "pejabat_utils.py", "organisasi_utils.py",
                 "routes/pegawai.py", "routes/unit_kerja.py", "routes/satker.py"):
        assert "organisasi_luar_utils" not in (akar / nama).read_text(encoding="utf-8"), nama
