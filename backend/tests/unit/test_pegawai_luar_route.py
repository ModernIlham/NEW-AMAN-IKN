"""Rute orang luar (PGW-03) — satu uji per invarian 5.7 yang menyentuh orang.

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kontrak 6.3, invarian 5.7.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import routes.organisasi_luar as rol
import routes.pegawai as rp
import routes.pegawai_luar as rpl
from routes.pegawai import PegawaiIn, _bersih
import organisasi_luar_utils as olu

ADMIN_A = {"username": "admin_a", "role": "admin", "kode_satker": "111111"}
ADMIN_B = {"username": "admin_b", "role": "admin", "kode_satker": "222222"}
SUPER = {"username": "pusat", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _req(if_match=None):
    headers = [] if if_match is None else [(b"if-match", str(if_match).encode())]
    return Request({"type": "http", "method": "PUT", "path": "/", "headers": headers,
                    "client": ("127.0.0.1", 1), "app": None})


def _galat(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rol, rpl, rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(su.limiter, "enabled", False)

    async def kegiatan(kode):
        return {"111111": ["k1"], "222222": ["k2"]}.get(kode, [])

    async def tanpa_filter(q=None):
        return dict(q or {})
    monkeypatch.setattr(su, "id_kegiatan_satker", kegiatan)
    monkeypatch.setattr(su, "filter_aset_perhitungan", tanpa_filter)
    return fake


def _instansi(kelompok="eksternal", jenis="kementerian_lembaga",
              nama="Kementerian Keuangan", satker="Sekretariat Jenderal", **kw):
    return _jalan(rol.buat_instansi_luar(rol.InstansiLuarIn(
        kelompok=kelompok, jenis=jenis, nama=nama,
        satker_pertama=rol.SatkerLuarIn(nama_satker=satker) if satker else None,
        **kw), user=ADMIN_A))


def _penuh(**kw):
    """Payload dengan SETIAP field PegawaiIn terisi nilai yang sah."""
    d = {k: "" for k in rpl.PegawaiLuarIn.model_fields}
    d.update({
        "nama": "Budi Santoso", "nip": "198001012005011001", "jenis_kelamin": "L",
        "tempat_lahir": "Samarinda", "tanggal_lahir": "1980-01-01",
        "agama": "islam", "status_perkawinan": "kawin",
        "status_kepegawaian": "pns", "pangkat_golongan": "III/c",
        "jabatan": "Analis", "eselon1": "Setjen", "eselon2": "Biro Umum",
        "eselon3": "Bagian RT", "unit_kerja": "Bagian RT", "npwp": "12.345",
        "pendidikan_terakhir": "S1", "nama_bank": "BRI", "no_rekening": "123",
        "nomor_kontrak": "K-1", "status": "aktif",
        "kapasitas_bertindak": "pengurus_berwenang",
        "dasar_kewenangan_jenis": "anggaran_dasar",
    })
    d.update(kw)
    return rpl.PegawaiLuarIn(**d)


def _buat(satker_id, user=ADMIN_A, **kw):
    hasil = _jalan(rpl.buat_pegawai_luar(_penuh(satker_luar_id=satker_id, **kw), user=user))
    return _jalan(dbx_global().pegawai_luar.find_one({"id": hasil["id"]}, {"_id": 0}))


_DB = {}


def dbx_global():
    return _DB["db"]


@pytest.fixture(autouse=True)
def _simpan_db(dbx):
    _DB["db"] = dbx


# ── invarian 1 & 2: turunan satker, penyesuaian per kelompok ───────────────
def test_eksternal_tersimpan_sama_kecuali_tujuh_field_pribadi(dbx):
    s = _instansi()["satker"]
    payload = _penuh(satker_luar_id=s["id"])
    simpan = _buat(s["id"])
    harapan = _bersih(PegawaiIn(**{k: getattr(payload, k)
                                   for k in PegawaiIn.model_fields}))
    for k, v in harapan.items():
        if k == "kode_satker":
            continue
        if k in olu.FIELD_PRIBADI_LUAR:
            assert simpan[k] == "", k
        else:
            assert simpan[k] == v, k
    assert all(simpan[f] == "" for f in olu.FIELD_KHUSUS_PIHAK_KETIGA)
    assert simpan["status_kepegawaian"] == "pns"


def test_pihak_ketiga_dipaksa_non_asn_dan_agama_kosong(dbx):
    s = _instansi("pihak_ketiga", "bumn", "PT Telkom Indonesia", "Kantor Pusat")["satker"]
    simpan = _buat(s["id"])
    assert simpan["status_kepegawaian"] == "non_asn"
    assert simpan["agama"] == ""
    assert all(simpan[f] == "" for f in olu.FIELD_NONAKTIF["pihak_ketiga"])
    assert simpan["kapasitas_bertindak"] == "pengurus_berwenang"


def test_kelompok_dan_instansi_kiriman_klien_diabaikan(dbx):
    a = _instansi()
    b = _instansi("pihak_ketiga", "bumn", "PT A", "Kantor Pusat")
    payload = _penuh(satker_luar_id=a["satker"]["id"]).model_dump()
    payload.update({"kelompok": "pihak_ketiga", "instansi_id": b["instansi"]["id"],
                    "tataran": "daerah"})
    hasil = _jalan(rpl.buat_pegawai_luar(rpl.PegawaiLuarIn(**payload), user=ADMIN_A))
    simpan = _jalan(dbx.pegawai_luar.find_one({"id": hasil["id"]}, {"_id": 0}))
    assert (simpan["kelompok"], simpan["tataran"], simpan["instansi_id"]) == \
        ("eksternal", "pusat", a["instansi"]["id"])
    assert simpan["satker_luar_nama"] == "Sekretariat Jenderal"


def test_orang_di_kabupaten_membawa_provinsinya(dbx):
    prov = _instansi(jenis="pemerintah_provinsi", nama="Provinsi Kalimantan Timur",
                     satker=None)["instansi"]
    kab = _instansi(jenis="pemerintah_kabkota", nama="Kabupaten Kutai Kartanegara",
                    satker="Dinas Pendidikan", induk_id=prov["id"])
    simpan = _buat(kab["satker"]["id"])
    assert simpan["provinsi_nama"] == "Provinsi Kalimantan Timur"
    assert simpan["kabkota_id"] == kab["instansi"]["id"]
    assert simpan["tataran"] == "daerah"


def test_satker_nonaktif_atau_tak_ada_ditolak(dbx):
    assert _galat(rpl.buat_pegawai_luar(_penuh(satker_luar_id="tak-ada"),
                                        user=ADMIN_A)).status_code == 400
    s = _instansi()["satker"]
    _jalan(dbx.satker_luar.update_one({"id": s["id"]}, {"$set": {"aktif": False}}))
    assert _galat(rpl.buat_pegawai_luar(_penuh(satker_luar_id=s["id"]),
                                        user=ADMIN_A)).status_code == 400


# ── invarian 3: perorangan ─────────────────────────────────────────────────
def test_perorangan_bertindak_untuk_diri_sendiri_tanpa_eselon(dbx):
    wadah = _jalan(rol.pastikan_wadah_perorangan(ADMIN_A))
    simpan = _buat(wadah["satker"]["id"], kapasitas_bertindak="penerima_kuasa")
    assert simpan["kapasitas_bertindak"] == "diri_sendiri"
    assert all(simpan[f"eselon{n}"] == "" for n in range(1, 6))


# ── invarian 4: NIP ────────────────────────────────────────────────────────
def test_nip_pegawai_internal_satker_lain_ditolak_tanpa_menyebut_namanya(dbx):
    _jalan(dbx.pegawai.insert_one({"id": "p1", "nama": "Siti Rahayu",
                                   "nip": "198001012005011001", "kode_satker": "999999"}))
    s = _instansi()["satker"]
    e = _galat(rpl.buat_pegawai_luar(_penuh(satker_luar_id=s["id"]), user=ADMIN_A))
    assert e.status_code == 400
    assert "Siti" not in str(e.detail) and "999999" not in str(e.detail)


def test_nip_unik_se_direktori_luar(dbx):
    a = _instansi()["satker"]
    b = _instansi("pihak_ketiga", "bumn", "PT A", "Kantor Pusat")["satker"]
    _buat(a["id"])
    e = _galat(rpl.buat_pegawai_luar(_penuh(satker_luar_id=b["id"]), user=ADMIN_B))
    assert e.status_code == 400 and "id_ada" in e.detail


# ── invarian 5: kartu ──────────────────────────────────────────────────────
def test_kartu_pegawai_internal_ditolak_dan_tak_terdaftar_ganda(dbx):
    from kartu_utils import hash_kandidat
    s = _instansi()["satker"]
    o1 = _buat(s["id"])
    o2 = _buat(s["id"], nip="198101012005011002", nama="Ani")
    uid_internal, uid = "04A1B2C3D4E5F6", "04112233445566"
    _jalan(dbx.pegawai.insert_one({"id": "p1", "nama": "Internal",
                                   "kartu_uid_hashes": hash_kandidat(uid_internal)}))
    e = _galat(rpl.daftar_kartu_pegawai_luar(_req(), o1["id"], rp.KartuIn(uid=uid_internal),
                                             admin=ADMIN_A))
    assert e.status_code == 409 and "Internal" not in str(e.detail)
    _jalan(rpl.daftar_kartu_pegawai_luar(_req(), o1["id"], rp.KartuIn(uid=uid), admin=ADMIN_A))
    assert _galat(rpl.daftar_kartu_pegawai_luar(
        _req(), o2["id"], rp.KartuIn(uid=uid), admin=ADMIN_B)).status_code == 409


# ── invarian 6 & 7: tanpa kode_satker, tak menulis koleksi internal ────────
def test_dokumen_orang_tanpa_kunci_kode_satker(dbx):
    s = _instansi()["satker"]
    simpan = _buat(s["id"], kode_satker="111111")
    assert "kode_satker" not in simpan


# ── invarian 9: pindah hanya sekelompok ────────────────────────────────────
def test_pindah_ke_satker_berkelompok_lain_ditolak(dbx):
    a = _instansi()
    lain = _jalan(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="Ditjen Pajak", instansi_id=a["instansi"]["id"]), user=ADMIN_A))
    p3 = _instansi("pihak_ketiga", "bumn", "PT A", "Kantor Pusat")["satker"]
    o = _buat(a["satker"]["id"])
    e = _galat(rpl.ubah_pegawai_luar(o["id"], _penuh(satker_luar_id=p3["id"]), _req(),
                                     user=ADMIN_B))
    assert e.status_code == 400
    # Sekelompok diterima, dan turunan satkernya ikut berganti.
    _jalan(rpl.ubah_pegawai_luar(o["id"], _penuh(satker_luar_id=lain["id"]), _req(1),
                                 user=ADMIN_B))
    simpan = _jalan(dbx.pegawai_luar.find_one({"id": o["id"]}, {"_id": 0}))
    assert simpan["satker_luar_nama"] == "Ditjen Pajak"
    assert simpan["diubah_oleh"]["kode_satker"] == "222222"


def test_ubah_dengan_if_match_usang_409_dan_teraudit(dbx):
    s = _instansi()["satker"]
    o = _buat(s["id"])
    _jalan(rpl.ubah_pegawai_luar(o["id"], _penuh(satker_luar_id=s["id"], jabatan="Kepala"),
                                 _req(1), user=ADMIN_B))
    assert _galat(rpl.ubah_pegawai_luar(o["id"], _penuh(satker_luar_id=s["id"]),
                                        _req(1), user=ADMIN_A)).status_code == 409
    log = _jalan(dbx.audit_logs.find_one({"action": "luar_orang_ubah"}, {"_id": 0}))
    assert {"field": "jabatan", "from": "Analis", "to": "Kepala"} in log["changes"]
    riwayat = _jalan(rol.riwayat_luar("orang", o["id"], _user=ADMIN_A))
    assert len(riwayat["items"]) == 2


# ── aset tetap per satker ──────────────────────────────────────────────────
def test_dua_satker_hanya_melihat_asetnya_masing_masing(dbx):
    s = _instansi("pihak_ketiga", "bumn", "PT A", "Kantor Pusat")["satker"]
    o = _buat(s["id"])
    nip = o["nip"]
    _jalan(dbx.assets.insert_many([
        {"id": "a1", "activity_id": "k1", "pengguna_nip": nip, "asset_code": "1"},
        {"id": "a2", "activity_id": "k2", "pengguna_nip": nip, "asset_code": "2"},
        {"id": "a3", "activity_id": "k2", "pengguna_nip": nip, "asset_code": "3"}]))
    a = _jalan(rpl.aset_dipegang_orang_luar(o["id"], _user=ADMIN_A))
    b = _jalan(rpl.aset_dipegang_orang_luar(o["id"], _user=ADMIN_B))
    assert [i["id"] for i in a["items"]] == ["a1"]
    assert [i["id"] for i in b["items"]] == ["a2", "a3"]


def test_hapus_super_admin_dan_409_bila_dirujuk_satker_mana_pun(dbx):
    s = _instansi()["satker"]
    o = _buat(s["id"])
    _jalan(dbx.assets.insert_one({"id": "a1", "activity_id": "k2",
                                  "pengguna_nip": o["nip"]}))
    e = _galat(rpl.hapus_pegawai_luar(o["id"], user=SUPER))
    assert e.status_code == 409 and "222222" not in str(e.detail)
    _jalan(dbx.assets.delete_many({}))
    _jalan(dbx.bast_serah_terima.insert_one({"id": "b1",
                                             "pihak_kedua": {"pegawai_id": o["id"]}}))
    assert _galat(rpl.hapus_pegawai_luar(o["id"], user=SUPER)).status_code == 409
    _jalan(dbx.bast_serah_terima.delete_many({}))
    # Penanggung jawab tambahan disimpan di `penanggung_jawab_tambahan`.
    _jalan(dbx.bast_serah_terima.insert_one({"id": "b2", "penanggung_jawab_tambahan": [
        {"pegawai_id": o["id"], "nama": o["nama"]}]}))
    assert _galat(rpl.hapus_pegawai_luar(o["id"], user=SUPER)).status_code == 409
    _jalan(dbx.bast_serah_terima.delete_many({}))
    _jalan(rpl.hapus_pegawai_luar(o["id"], user=SUPER))
    assert _jalan(dbx.pegawai_luar.count_documents({})) == 0


# ── daftar & rekap ─────────────────────────────────────────────────────────
def test_daftar_wajib_kelompok_aktif_saja_berhalaman(dbx):
    assert _galat(rpl.daftar_pegawai_luar(_user=ADMIN_A)).status_code == 400
    s = _instansi()["satker"]
    for n in range(4):
        _buat(s["id"], nip=f"19800101200501100{n}", nama=f"Orang {n}")
    _buat(s["id"], nip="198001012005011009", nama="Orang Keluar", status="nonaktif")
    hal = _jalan(rpl.daftar_pegawai_luar(kelompok="eksternal", page=2, page_size=3,
                                         _user=ADMIN_B))
    assert hal["total"] == 4 and len(hal["items"]) == 1
    assert hal["items"][0]["instansi_nama"] == "Kementerian Keuangan"
    assert "label_unit" in hal["items"][0] and "info_masa" in hal["items"][0]
    semua = _jalan(rpl.daftar_pegawai_luar(kelompok="eksternal", semua_status=True,
                                           _user=ADMIN_B))
    assert semua["total"] == 5
    cari = _jalan(rpl.daftar_pegawai_luar(kelompok="eksternal", q="Orang 2", _user=ADMIN_B))
    assert [i["nama"] for i in cari["items"]] == ["Orang 2"]
    assert "kartu_uid_hashes" not in str(hal["items"])


def test_rekap_lingkup_per_tataran_instansi_satker(dbx):
    s = _instansi()["satker"]
    prov = _instansi(jenis="pemerintah_provinsi", nama="Provinsi X", satker="Dinas A")
    _buat(s["id"])
    _buat(prov["satker"]["id"], nip="198101012005011002", nama="Ani")
    rekap = _jalan(rpl.rekap_lingkup_pegawai_luar(kelompok="eksternal", _user=ADMIN_A))
    assert rekap["per_tataran"] == {"pusat": 1, "daerah": 1}
    assert rekap["jumlah"] == 2
    assert {i["nama"] for i in rekap["per_instansi"]} == {"Kementerian Keuangan",
                                                         "Provinsi X"}
    assert _galat(rpl.rekap_lingkup_pegawai_luar(_user=ADMIN_A)).status_code == 400
    assert _galat(rpl.rekap_unit_pegawai_luar(_user=ADMIN_A)).status_code == 400
