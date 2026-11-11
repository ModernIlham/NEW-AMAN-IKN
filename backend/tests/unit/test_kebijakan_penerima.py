"""Kebijakan per jenis penerima BMN di luar satker (PGW-10, kerangka).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md 6.6; pustaka §2.4d.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import kebijakan_penerima as kp
import organisasi_luar_utils as olu

DASAR = {"nomor": "S-12/MK.6/2026", "tanggal": "2026-10-01",
         "jangka_dari": "2026-11-01", "jangka_sampai": "2027-10-31"}

#: (jenis, skema sah contoh, kapasitas sah, skema TAK sah contoh)
BARIS = [
    ("kementerian_lembaga", "penggunaan_sementara", "", "sewa"),
    ("pemerintah_provinsi", "pinjam_pakai", "", "sewa"),
    ("pemerintah_kabkota", "pinjam_pakai", "", "penggunaan_sementara"),
    ("pemerintah_desa", "pinjam_pakai", "", "ksp"),
    ("bumn", "dioperasikan_pihak_lain", "pengurus_berwenang", "pinjam_pakai"),
    ("bumd", "kspi", "penerima_kuasa", "dioperasikan_pihak_lain"),
    ("bumdes", "sewa", "pengurus_berwenang", "ksp"),
    ("badan_usaha_swasta", "bgs_bsg", "pengurus_berwenang", "pinjam_pakai"),
    ("koperasi", "kspi", "pengurus_berwenang", "ksp"),
    ("yayasan", "bgs_bsg", "penerima_kuasa", "kspi"),
    ("satuan_pendidikan_swasta", "sewa", "pengurus_berwenang", "bgs_bsg"),
    ("badan_hukum_lain", "dioperasikan_pihak_lain", "pengurus_berwenang", "sewa"),
    ("perorangan", "sewa", "diri_sendiri", "ksp"),
    ("lembaga_internasional", "dioperasikan_pihak_lain", "pengurus_berwenang", "sewa"),
]


def test_matriks_mencakup_seluruh_jenis_penerima_luar():
    semua = set(olu.JENIS_INSTANSI["eksternal"]) | set(olu.JENIS_INSTANSI["pihak_ketiga"])
    assert set(kp.MATRIKS) == semua
    for j, k in kp.MATRIKS.items():
        assert set(k["skema_sah"]) <= set(kp.SKEMA), j
        assert k["rezim_ganti_rugi"] in ("perjanjian", ""), j


@pytest.mark.parametrize("jenis,skema,kap,_", BARIS)
def test_tiap_baris_LULUS_dengan_skema_dan_dokumen_sah(jenis, skema, kap, _):
    assert kp.periksa_penyerahan(skema, jenis, kap, DASAR) == []


@pytest.mark.parametrize("jenis,_,kap,salah", BARIS)
def test_tiap_baris_DITOLAK_dengan_skema_tak_sah_dan_menyebut_yang_tersedia(jenis, _, kap, salah):
    galat = kp.periksa_penyerahan(salah, jenis, kap, DASAR)
    assert len(galat) == 1 and "tidak sah" in galat[0] and "yang tersedia" in galat[0]
    for s in kp.kebijakan(jenis)["skema_sah"]:
        assert kp.SKEMA[s] in galat[0]


def test_pinjam_pakai_kepada_badan_usaha_ditolak():
    galat = kp.periksa_penyerahan("pinjam_pakai", "badan_usaha_swasta",
                                  "pengurus_berwenang", DASAR)
    assert "Pinjam pakai" in galat[0] and "Sewa" in galat[0]


def test_dokumen_dasar_yang_kurang_disebut_satu_per_satu():
    galat = kp.periksa_penyerahan("pinjam_pakai", "pemerintah_kabkota", "",
                                  {"nomor": "", "tanggal": "2026-01-01"})
    assert galat == ["Lengkapi nomor dokumen dasar, awal jangka waktu, akhir jangka waktu "
                     "(persetujuan Pengelola Barang dan perjanjian pinjam pakai)"]
    terbalik = {**DASAR, "jangka_sampai": "2026-01-01"}
    assert kp.periksa_penyerahan("pinjam_pakai", "pemerintah_kabkota", "", terbalik) == [
        "Akhir jangka waktu tidak boleh sebelum awalnya"]


def test_petugas_tidak_boleh_menjadi_pihak_kedua():
    galat = kp.periksa_penyerahan("sewa", "bumn", "petugas", DASAR)
    assert len(galat) == 1 and "pengurus yang berwenang atau penerima kuasa" in galat[0]
    assert kp.periksa_penyerahan("sewa", "bumn", "", DASAR)  # kapasitas kosong juga ditolak
    assert kp.periksa_penyerahan("sewa", "perorangan", "pengurus_berwenang", DASAR)


def test_kelompok_masyarakat_dan_lainnya_tanpa_skema():
    assert "hibah" in kp.periksa_penyerahan("sewa", "kelompok_masyarakat", "", DASAR)[0]
    assert "lainnya" in kp.periksa_penyerahan("sewa", "lainnya", "", DASAR)[0]


def test_internal_tak_berubah_dan_kspi_swasta_berkatatan():
    k = kp.kebijakan("")
    assert k["butir_pasal"] == "internal" and k["rezim_ganti_rugi"] == "tgr_pegawai"
    assert kp.catatan_penyerahan("kspi", "badan_usaha_swasta") == [
        "KSPI hanya bagi badan usaha berbentuk perseroan terbatas (PT)"]
    assert kp.catatan_penyerahan("sewa", "badan_usaha_swasta") == []


def test_komparisi_menurut_kapasitas():
    assert kp.komparisi("Dewi", "", "pemerintah_kabkota", "Pemerintah Kabupaten X") == (
        "Dewi, dalam hal ini bertindak untuk dan atas nama Pemerintah Kabupaten X")
    assert kp.komparisi("Eka", "penerima_kuasa", "badan_usaha_swasta", "PT Maju",
                        "Surat kuasa", "12/SK/2026", "2026-09-01") == (
        "Eka, dalam hal ini bertindak untuk dan atas nama PT Maju berdasarkan "
        "Surat kuasa nomor 12/SK/2026 tanggal 2026-09-01")
    assert kp.komparisi("Budi", "diri_sendiri", "perorangan", "") == (
        "Budi, dalam hal ini bertindak untuk diri sendiri")
    assert "Yayasan Pendidikan Y" in kp.komparisi(
        "Sri", "pengurus_berwenang", "satuan_pendidikan_swasta", "SMA Z",
        badan_penyelenggara="Yayasan Pendidikan Y")


def test_kerangka_tidak_memuat_teks_pasal_atau_sitasi():
    from pathlib import Path
    src = Path(kp.__file__).read_text(encoding="utf-8")
    kode = src.split('"""', 2)[2]   # lewati docstring modul yang menjelaskan statusnya
    for kata in ("PMK", "Pasal ", "hukuman disiplin", "tuntutan ganti"):
        assert kata not in kode.replace("(PMK 115/2020)", ""), kata
    assert kp.NASKAH_LUAR_SIAP is False


# ── rute ──────────────────────────────────────────────────────────────────
def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


@pytest.fixture()
def dbx(monkeypatch):
    import routes.bast as rb
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rb, "db", fake, raising=False)
    return fake


def _payload(**kw):
    import routes.bast as rb
    dasar = {"jenis": "penyerahan_pihak_luar", "asset_ids": ["a1"],
             "pihak_kedua": rb.PihakIn(nama="Eka", nip="6471"), "skema": "sewa",
             "dokumen_dasar_nomor": "PRJ-1", "dokumen_dasar_tanggal": "2026-10-01",
             "jangka_dari": "2026-11-01", "jangka_sampai": "2027-10-31"}
    dasar.update(kw)
    return rb.BastIn(**dasar)


def _status(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


def test_bast_luar_lolos_pemeriksaan_lalu_ditahan_gerbang(dbx):
    import routes.bast as rb
    _jalan(dbx.pegawai_luar.insert_one({"nip": "6471", "jenis_instansi": "bumn",
                                        "kapasitas_bertindak": "pengurus_berwenang",
                                        "kelompok": "pihak_ketiga"}))
    e = _status(rb._periksa_bast_luar(_payload(), {}))
    assert e.status_code == 409 and "menunggu verifikasi" in e.detail
    assert _jalan(dbx.bast_serah_terima.count_documents({})) == 0


def test_bast_luar_galat_kelengkapan_400_sebelum_gerbang(dbx):
    import routes.bast as rb
    _jalan(dbx.pegawai_luar.insert_one({"nip": "6471", "jenis_instansi": "bumn",
                                        "kapasitas_bertindak": "petugas",
                                        "kelompok": "pihak_ketiga"}))
    e = _status(rb._periksa_bast_luar(_payload(skema="pinjam_pakai",
                                               dokumen_dasar_nomor=""), {}))
    assert e.status_code == 400
    assert "nomor dokumen dasar" in e.detail and "Pinjam pakai" in e.detail
    assert "penerima kuasa" in e.detail


def test_bast_luar_wajib_pihak_kedua_dari_direktori(dbx):
    import routes.bast as rb
    e = _status(rb._periksa_bast_luar(_payload(), {}))
    assert e.status_code == 400 and "direktori orang luar" in e.detail


def test_jenis_bast_lama_tak_berubah_dan_luar_tak_memicu_portal():
    from pathlib import Path
    import routes.bast as rb
    assert not set(kp.JENIS_BAST_LUAR) & set(rb.JENIS_BAST)
    src = Path(rb.__file__).read_text(encoding="utf-8")
    blok = src.split("from portal_bast import siapkan_otomasi_bast", 1)[1][:400]
    assert 'if record.get("jenis") not in kp.JENIS_BAST_LUAR:' in blok


def test_referensi_luar_membawa_kebijakan_dan_gerbang():
    import routes.organisasi_luar as rol
    ref = _jalan(rol.referensi_luar(_user={}))
    assert ref["naskah_luar_siap"] is False
    assert ref["kebijakan_penerima"]["pemerintah_desa"]["skema_sah"] == ["pinjam_pakai"]
    assert "penyerahan_pihak_luar" in ref["jenis_bast_luar"]
