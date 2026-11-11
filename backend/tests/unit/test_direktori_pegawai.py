"""Direktori gabungan & pembaca backend yang mengenali orang luar (PGW-06).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kontrak 6.5, peta 7.2.
"""
import asyncio
from functools import partial

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import direktori_pegawai as dp
import routes.direktori_pegawai as rdp
from shared_utils import scope_query_field_satker

USER_A = {"username": "a", "role": "admin", "kode_satker": "111111"}
USER_B = {"username": "b", "role": "admin", "kode_satker": "222222"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _req():
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [],
                    "client": ("127.0.0.1", 1), "app": None})


def _galat(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import db as db_mod
    import shared_utils as su
    for mod in (rdp, su, db_mod):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(su.limiter, "enabled", False)
    _jalan(fake.pegawai.insert_many([
        {"id": "pa", "nama": "Ani Internal A", "nip": "111", "kode_satker": "111111",
         "status": "aktif"},
        {"id": "pb", "nama": "Budi Internal B", "nip": "222", "kode_satker": "222222",
         "status": "aktif"},
        {"id": "pk", "nama": "Kembar Internal", "nip": "999", "kode_satker": "111111"},
    ]))
    _jalan(fake.pegawai_luar.insert_many([
        {"id": "l1", "nama": "Citra Pusat", "nip": "333", "kelompok": "eksternal",
         "tataran": "pusat", "instansi_nama": "Kementerian X",
         "satker_luar_nama": "Setjen", "status": "aktif"},
        {"id": "l2", "nama": "Dedi Daerah", "nip": "444", "kelompok": "eksternal",
         "tataran": "daerah", "instansi_nama": "Kab Y", "provinsi_nama": "Prov Z",
         "satker_luar_nama": "Dinas", "status": "aktif"},
        {"id": "l3", "nama": "Eka Badan", "nip": "555", "kelompok": "pihak_ketiga",
         "tataran": "", "instansi_nama": "PT A", "satker_luar_nama": "Pusat",
         "status": "aktif", "kapasitas_bertindak": "pengurus_berwenang"},
        {"id": "l4", "nama": "Fajar Keluar", "nip": "666", "kelompok": "pihak_ketiga",
         "tataran": "", "instansi_nama": "PT A", "satker_luar_nama": "Pusat",
         "status": "nonaktif"},
        {"id": "l5", "nama": "Kembar Luar", "nip": "999", "kelompok": "eksternal",
         "tataran": "pusat", "instansi_nama": "K", "satker_luar_nama": "S",
         "status": "aktif"},
    ]))
    return fake


# ── penjawab kelompok ──────────────────────────────────────────────────────
def test_kelompok_mengenali_internal_sendiri_dan_luar_aktif_saja(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["111", "222", "333", "444", "555", "666", "777"]),
        user=USER_A))["nomor"]
    assert hasil == {"111": "internal", "333": "eksternal_pusat",
                     "444": "eksternal_daerah", "555": "pihak_ketiga"}


def test_kelompok_tidak_mengembalikan_nomor_yang_tak_ditanyakan(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["333"]), user=USER_A))["nomor"]
    assert set(hasil) == {"333"}


def test_kelompok_lebih_dari_500_nomor_ditolak(dbx):
    e = _galat(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=[str(i) for i in range(501)]), user=USER_A))
    assert e.status_code == 400


def test_nomor_di_internal_dan_luar_dikenali_internal(dbx):
    hasil = _jalan(rdp.kelompok_direktori_pegawai(
        _req(), rdp.NomorIn(nomor=["999"]), user=USER_A))["nomor"]
    assert hasil == {"999": "internal"}
    satu = _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_A), "999",
                                database=dbx))
    assert satu["ranah"] == "internal" and satu["nama"] == "Kembar Internal"


def test_cari_orang_luar_membawa_kelompok_dan_instansi(dbx):
    o = _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_B), "444", database=dbx))
    assert (o["ranah"], o["kunci_ikon"], o["instansi_nama"]) == \
        ("luar", "eksternal_daerah", "Kab Y")
    assert _jalan(dp.cari_orang(partial(scope_query_field_satker, USER_B), "111",
                                database=dbx)) is None


# ── daftar direktori ───────────────────────────────────────────────────────
def test_direktori_wajib_kelompok(dbx):
    assert _galat(rdp.daftar_direktori_pegawai(user=USER_A)).status_code == 400


def test_direktori_internal_ter_scope_satker(dbx):
    hasil = _jalan(rdp.daftar_direktori_pegawai(kelompok="internal", user=USER_A))
    assert {i["nip"] for i in hasil["items"]} == {"111", "999"}
    assert all(i["kunci_ikon"] == "internal" for i in hasil["items"])


def test_direktori_luar_aktif_dan_membawa_instansi_serta_satker(dbx):
    hasil = _jalan(rdp.daftar_direktori_pegawai(kelompok="pihak_ketiga", user=USER_B))
    assert [i["nip"] for i in hasil["items"]] == ["555"]
    i = hasil["items"][0]
    assert i["instansi_nama"] == "PT A" and i["satker_luar_nama"] == "Pusat"
    assert i["kunci_ikon"] == "pihak_ketiga"
    daerah = _jalan(rdp.daftar_direktori_pegawai(kelompok="eksternal", tataran="daerah",
                                                 user=USER_A))
    assert [i["nip"] for i in daerah["items"]] == ["444"]
    cari = _jalan(rdp.daftar_direktori_pegawai(kelompok="eksternal", q="Kementerian",
                                               user=USER_A))
    assert [i["nip"] for i in cari["items"]] == ["333"]


def test_identifikasi_kartu_internal_dulu_lalu_luar(dbx):
    from kartu_utils import hash_kandidat
    _jalan(dbx.pegawai_luar.update_one({"id": "l1"}, {"$set": {
        "kartu_uid_hashes": hash_kandidat("04AABBCCDDEEFF")}}))
    hasil = _jalan(rdp.identifikasi_kartu_direktori(
        _req(), rdp.KartuDirektoriIn(uid="04AABBCCDDEEFF"), user=USER_A))
    assert hasil["pegawai"]["nip"] == "333" and hasil["pegawai"]["ranah"] == "luar"
    assert "kartu_uid_hashes" not in hasil["pegawai"]
    assert _galat(rdp.identifikasi_kartu_direktori(
        _req(), rdp.KartuDirektoriIn(uid="04112233445566"), user=USER_A)).status_code == 404


# ── pembaca 1: shared_utils ────────────────────────────────────────────────
def test_status_kepegawaian_mengenali_orang_luar_dan_internal_tetap(dbx):
    import shared_utils as su
    _jalan(dbx.pegawai.update_one({"id": "pa"}, {"$set": {"status_kepegawaian": "pns"}}))
    _jalan(dbx.pegawai_luar.update_one({"id": "l3"}, {"$set": {"status_kepegawaian": "non_asn"}}))
    assert _jalan(su.status_kepegawaian_by_nip("555")) == "non_asn"
    assert _jalan(su.status_kepegawaian_by_nip("111")) == "pns"
    assert _jalan(su.status_kepegawaian_by_nip("000")) == ""


def test_enforce_pegawai_terdaftar_mengenali_orang_luar(dbx):
    import shared_utils as su
    _jalan(dbx.report_settings.insert_one({"type": "global", "wajib_pegawai_terdaftar": True}))
    _jalan(su.enforce_pegawai_terdaftar("555"))          # luar terdaftar → lolos
    _jalan(su.enforce_pegawai_terdaftar("111"))          # internal → tetap lolos
    assert _galat(su.enforce_pegawai_terdaftar("000")).status_code == 400
    _jalan(dbx.pegawai_luar.update_one({"id": "l3"}, {"$set": {"status": "meninggal"}}))
    assert _galat(su.enforce_pegawai_terdaftar("555")).status_code == 400
    _jalan(su.enforce_pegawai_terdaftar("555", nip_lama="555"))   # pemegang tak berubah


# ── pembaca 2: penerima_utils ──────────────────────────────────────────────
def test_periksa_penerima_mengenali_orang_luar_dan_internal_tetap(dbx):
    import penerima_utils as pnu
    sc = partial(scope_query_field_satker, USER_A)
    peg, catatan = _jalan(pnu.periksa_penerima(dbx, sc, "555"))
    assert peg["nama"] == "Eka Badan" and catatan == ""
    s = pnu.snapshot_penerima(peg)
    assert (s["penerima_kelompok"], s["penerima_instansi"]) == ("pihak_ketiga", "PT A")
    peg_i, _ = _jalan(pnu.periksa_penerima(dbx, sc, "111"))
    s_i = pnu.snapshot_penerima(peg_i)
    assert (s_i["penerima_kelompok"], s_i["penerima_instansi"]) == ("internal", "")
    # Internal satker lain tetap tak dikenali (scope internal tak berubah).
    assert _jalan(pnu.periksa_penerima(dbx, sc, "222"))[0] is None
    assert pnu.snapshot_penerima(None)["penerima_kelompok"] == ""
    _jalan(dbx.pegawai_luar.update_one({"id": "l3"}, {"$set": {"status": "meninggal"}}))
    with pytest.raises(pnu.PenerimaMeninggal):
        _jalan(pnu.periksa_penerima(dbx, sc, "555"))


# ── pembaca 3: routes/bast.py ──────────────────────────────────────────────
def test_bast_membekukan_kelompok_pihak_dari_direktori(dbx, monkeypatch):
    import routes.bast as rb
    monkeypatch.setattr(rb, "db", dbx)
    luar = _jalan(rb._bekukan_kelompok(USER_A, {"nama": "x", "nip": "444",
                                                "kelompok": "internal"}))
    assert (luar["kelompok"], luar["tataran"], luar["instansi_nama"]) == \
        ("eksternal", "daerah", "Kab Y")
    internal = _jalan(rb._bekukan_kelompok(USER_A, {"nama": "Ani", "nip": "111"}))
    assert (internal["kelompok"], internal["instansi_nama"]) == ("internal", "")
    asing = _jalan(rb._bekukan_kelompok(USER_A, {"nama": "Budi", "nip": "222",
                                                 "kelompok": "pihak_ketiga"}))
    assert asing["kelompok"] == ""          # internal satker lain tak dikenali
    assert set(rb.PihakIn.model_fields) >= {"kelompok", "tataran", "instansi_nama"}


def test_bast_pihak_kesatu_orang_luar_meninggal_ditolak_lewat_sumber():
    """Cek PIHAK KESATU meninggal kini juga membaca pegawai_luar."""
    from pathlib import Path
    import routes.bast as rb
    src = Path(rb.__file__).read_text(encoding="utf-8")
    blok = src.split("nip1 = str(pihak_pertama.get(\"nip\")", 1)[1][:1200]
    assert "db.pegawai_luar.find_one" in blok and "is_meninggal(peg1)" in blok


# ── pembaca 4: routes/ttd.py ───────────────────────────────────────────────
def test_ttd_dua_cek_penanda_tangan_meninggal_membaca_orang_luar():
    """Kedua penolakan penanda tangan almarhum kini juga membaca pegawai_luar;
    pembacaan pegawai internal ber-scope tetap ada di tempatnya."""
    from pathlib import Path
    import routes.ttd as rt
    src = Path(rt.__file__).read_text(encoding="utf-8")
    a = src.split('_alm = await db.pegawai.find(', 1)[1][:900]
    assert 'scope_query_field_satker(' in a
    assert 'db.pegawai_luar.find(' in a and '"status": "meninggal"' in a
    b = src.split('pg = await db.pegawai.find_one(scope_query_field_satker(user, {"nip": baru["nip"]})', 1)[1][:500]
    assert 'db.pegawai_luar.find_one({"nip": baru["nip"]}' in b and "is_meninggal(pg)" in b


# ── pembaca 5: routes/imports.py ───────────────────────────────────────────
def test_impor_aset_nip_terdaftar_gabungan_kedua_koleksi():
    from pathlib import Path
    import routes.imports as ri
    src = Path(ri.__file__).read_text(encoding="utf-8")
    blok = src.split("nip_terdaftar = {str(n).strip()", 1)[1][:300]
    assert "db.pegawai, db.pegawai_luar" in blok and '.distinct("nip")' in blok


# ── pembaca 6: routes/penggunaan.py ────────────────────────────────────────
def test_rekap_pemegang_memperkaya_orang_luar(dbx, monkeypatch):
    import routes.penggunaan as rpg
    monkeypatch.setattr(rpg, "db", dbx)

    async def tanpa_filter(user, q=None):
        return dict(q or {})
    monkeypatch.setattr(rpg, "scope_query_aset", tanpa_filter, raising=False)
    from pathlib import Path
    src = Path(rpg.__file__).read_text(encoding="utf-8")
    blok = src.split("# Perkaya dgn Master Pegawai via NIP", 1)[1][:2600]
    assert "db.pegawai_luar.find(" in blok
    assert 'r["pegawai_master_kelompok"]' in blok and 'r["pegawai_master_instansi"]' in blok
    assert 'scope_query_field_satker(_user, {"nip": {"$in": list(nips)}})' in blok
    # PGW-08: kunci ikon dari kelompok + tataran (pusat ≠ daerah).
    assert '"tataran": 1' in blok
    assert 'r["pegawai_master_kunci_ikon"] = (kunci_ikon(m.get("kelompok"), m.get("tataran"))' in blok


# ── pembaca 7: routes/reports.py ───────────────────────────────────────────
def test_peta_status_kepegawaian_mengenali_orang_luar_internal_menang(dbx, monkeypatch):
    import routes.reports as rr
    monkeypatch.setattr(rr, "db", dbx)
    _jalan(dbx.pegawai.update_one({"id": "pk"}, {"$set": {"status_kepegawaian": "pns"}}))
    _jalan(dbx.pegawai_luar.update_many({}, {"$set": {"status_kepegawaian": "non_asn"}}))
    peta = _jalan(rr._peta_status_kepegawaian(["555", "999", "000"]))
    assert peta == {"555": "non_asn", "999": "pns"}


# ── pembaca 8: routes/wasdal.py ────────────────────────────────────────────
def test_wasdal_pegawai_berisiko_ikut_membaca_orang_luar():
    from pathlib import Path
    import routes.wasdal as rw
    src = Path(rw.__file__).read_text(encoding="utf-8")
    blok = src.split("pegawai = [p async for p in db.pegawai.find(", 1)[1][:1800]
    assert "db.pegawai_luar.find(" in blok
    assert "not in _nip_internal" in blok          # internal menang, tak ganda
    assert "_jumlah_aset_per_nip(user)" in blok    # cacah aset tetap ter-scope


# ── PGW-09: unit orang luar untuk dokumen pemegang ──────────────────────
def test_unit_orang_luar_per_nip_internal_menang_dan_berinstansi(dbx):
    _jalan(dbx.pegawai.insert_one({"nip": "9111", "nama": "Internal", "kode_satker": "691778",
                                   "unit_kerja": "Bagian Umum"}))
    _jalan(dbx.pegawai_luar.insert_many([
        {"id": "l1", "nip": "9111", "nama": "Kembar Lama", "kelompok": "pihak_ketiga",
         "instansi_nama": "PT Lama"},
        {"id": "l2", "nip": "9222", "nama": "Dewi", "kelompok": "eksternal",
         "tataran": "daerah", "jenis_instansi": "pemerintah_kabkota",
         "instansi_nama": "Kabupaten X", "provinsi_nama": "Provinsi Y",
         "satker_luar_nama": "Dinas PU", "unit_kerja": "Bidang Jalan"}]))
    hasil = _jalan(dp.unit_orang_luar_per_nip(["9111", "9222", "9444", ""], database=dbx))
    assert hasil == {"9222": "Kabupaten X, Provinsi Y — Dinas PU — Bidang Jalan"}


def test_sel_jabatan_pemegang_luar_menyebut_instansi():
    import routes.reports as rp
    unit = {"222": "PT Mitra — Cabang"}
    assert rp._jabatan_pemegang({"nip": "222", "jabatan": "Teknisi"}, unit, str, "\n") \
        == "Teknisi\nPT Mitra — Cabang"
    # Pegawai internal tidak berubah.
    assert rp._jabatan_pemegang({"nip": "111", "jabatan": ""}, unit, str, "\n") == "-"
