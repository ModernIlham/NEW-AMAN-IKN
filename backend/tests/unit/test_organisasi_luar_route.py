"""Rute direktori instansi & satker luar (PGW-02).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — kontrak 6.1, tata kelola
3.4, aturan penampungan 3.3, invarian 5.7.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from starlette.requests import Request

import routes.organisasi_luar as rol

ADMIN_A = {"username": "admin_a", "role": "admin", "kode_satker": "111111"}
ADMIN_B = {"username": "admin_b", "role": "admin", "kode_satker": "222222"}
USER_A = {"username": "op_a", "role": "operator", "kode_satker": "111111"}
SUPER = {"username": "pusat", "role": "admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _req(if_match=None):
    headers = [] if if_match is None else [(b"if-match", str(if_match).encode())]
    return Request({"type": "http", "method": "PUT", "path": "/", "headers": headers})


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rol, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


def _instansi(**kw):
    dasar = {"kelompok": "eksternal", "jenis": "kementerian_lembaga",
             "nama": "Kementerian Keuangan",
             "satker_pertama": rol.SatkerLuarIn(nama_satker="Sekretariat Jenderal")}
    dasar.update(kw)
    return rol.InstansiLuarIn(**dasar)


def _buat(user=ADMIN_A, **kw):
    return _jalan(rol.buat_instansi_luar(_instansi(**kw), user=user))


def _galat(coro):
    with pytest.raises(HTTPException) as e:
        _jalan(coro)
    return e.value


def _provinsi(nama="Provinsi Kalimantan Timur", **kw):
    return _buat(jenis="pemerintah_provinsi", nama=nama, satker_pertama=None, **kw)["instansi"]


def _kabkota(induk_id, nama="Kabupaten Penajam Paser Utara", **kw):
    return _buat(jenis="pemerintah_kabkota", nama=nama, induk_id=induk_id,
                 satker_pertama=rol.SatkerLuarIn(nama_satker="Dinas Pendidikan"),
                 **kw)


def _ubah_instansi(doc, user=ADMIN_B, if_match=None, **kw):
    data = {k: doc.get(k) for k in rol.InstansiLuarIn.model_fields
            if k in doc and k != "satker_pertama"}
    data.update(kw)
    return rol.ubah_instansi_luar(doc["id"], rol.InstansiLuarIn(**data), _req(if_match),
                                  user=user)


# ── direktori bersama & tata kelola (3.4, K2a) ─────────────────────────────
def test_catatan_admin_a_terlihat_pengguna_satker_b(dbx):
    hasil = _buat()
    daftar = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", _user=USER_A))
    assert [i["id"] for i in daftar["items"]] == [hasil["instansi"]["id"]]
    daftar_b = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", _user=ADMIN_B))
    assert daftar_b["total"] == 1
    assert daftar_b["items"][0]["jumlah_satker"] == 1


def test_admin_b_dapat_mengubah_dan_audit_mencatat_satker_b(dbx):
    i = _buat()["instansi"]
    baru = _jalan(_ubah_instansi(i, nama="Kementerian Keuangan RI", if_match=1))
    assert baru["diubah_oleh"]["kode_satker"] == "222222"
    assert baru["dicatat_oleh"]["kode_satker"] == "111111"
    log = _jalan(dbx.audit_logs.find_one({"action": "luar_instansi_ubah"}, {"_id": 0}))
    assert log["kode_satker"] == "222222"
    assert {"field": "nama", "from": "Kementerian Keuangan",
            "to": "Kementerian Keuangan RI"} in log["changes"]
    # Jejaknya terlihat pengguna satker A (riwayat tanpa scope).
    riwayat = _jalan(rol.riwayat_luar("instansi", i["id"], _user=USER_A))
    aksi = [r["action"] for r in riwayat["items"]]
    assert "luar_instansi_ubah" in aksi and "luar_instansi_tambah" in aksi


def test_audit_gagal_tidak_lewat_diam_diam(dbx, monkeypatch):
    async def gagal(*a, **k):
        assert k.get("strict") is True
        raise RuntimeError("audit mati")
    monkeypatch.setattr(rol, "log_audit", gagal)
    with pytest.raises(RuntimeError):
        _buat()


def test_hapus_hanya_super_admin_dan_409_bila_dirujuk(dbx):
    hasil = _buat()
    i = hasil["instansi"]
    # Penjaga require_super_admin menolak admin satker.
    from auth_utils import require_super_admin
    assert _galat(require_super_admin(ADMIN_A)).status_code == 403
    _jalan(dbx.pegawai_luar.insert_one({"id": "o1", "instansi_id": i["id"],
                                        "satker_luar_id": hasil["satker"]["id"]}))
    assert _galat(rol.hapus_instansi_luar(i["id"], user=SUPER)).status_code == 409
    _jalan(dbx.pegawai_luar.delete_many({}))
    hasil_hapus = _jalan(rol.hapus_instansi_luar(i["id"], user=SUPER))
    assert hasil_hapus["satker_dihapus"] == 1
    assert _jalan(dbx.instansi_luar.count_documents({})) == 0
    assert _jalan(dbx.satker_luar.count_documents({})) == 0


def test_nama_kembar_beda_tanda_baca_ditolak_dengan_id_yang_ada(dbx):
    i = _buat(kelompok="pihak_ketiga", jenis="bumn", nama="PT. Telkom Indonesia")["instansi"]
    e = _galat(rol.buat_instansi_luar(_instansi(
        kelompok="pihak_ketiga", jenis="bumn", nama="Telkom Indonesia, PT"), user=ADMIN_B))
    assert e.status_code == 400
    assert e.detail["id_ada"] == i["id"]


def test_satker_pertama_wajib_kecuali_pemda(dbx):
    for kelompok, jenis in (("eksternal", "kementerian_lembaga"), ("pihak_ketiga", "bumn")):
        e = _galat(rol.buat_instansi_luar(_instansi(
            kelompok=kelompok, jenis=jenis, nama=f"X {jenis}", satker_pertama=None),
            user=ADMIN_A))
        assert e.status_code == 400
    assert _provinsi()["tataran"] == "daerah"
    # Instansi yang ditolak tidak meninggalkan satker yatim.
    assert _jalan(dbx.satker_luar.count_documents({})) == 0


def test_satker_dibuang_bila_instansi_gagal_disisipkan(dbx, monkeypatch):
    class KoleksiGagal:
        def __init__(self, asli):
            self._asli = asli

        def __getattr__(self, nama):
            return getattr(self._asli, nama)

        async def insert_one(self, *a, **k):
            raise RuntimeError("duplikat")

    class DbBungkus:
        def __getattr__(self, nama):
            kol = getattr(dbx, nama)
            return KoleksiGagal(kol) if nama == "instansi_luar" else kol

        def __getitem__(self, nama):
            return getattr(self, nama)

    monkeypatch.setattr(rol, "db", DbBungkus())
    with pytest.raises(RuntimeError):
        _buat()
    assert _jalan(dbx.satker_luar.count_documents({})) == 0


def test_if_match_usang_409(dbx):
    i = _buat()["instansi"]
    _jalan(_ubah_instansi(i, nama="Kemenkeu", if_match=1))
    e = _galat(_ubah_instansi(i, nama="Kemenkeu Lagi", if_match=1))
    assert e.status_code == 409


def test_tak_ada_dokumen_luar_berkunci_kode_satker(dbx):
    hasil = _buat()
    _jalan(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="Ditjen Kekayaan Negara", instansi_id=hasil["instansi"]["id"]),
        user=ADMIN_B))
    _jalan(rol.pastikan_wadah_perorangan(ADMIN_A))
    for kol in ("instansi_luar", "satker_luar"):
        for d in _jalan(dbx[kol].find({}, {"_id": 0}).to_list(100)):
            assert "kode_satker" not in d, (kol, d)


def test_wadah_perorangan_idempoten_dan_terkunci(dbx):
    w1 = _jalan(rol.pastikan_wadah_perorangan(ADMIN_A))
    w2 = _jalan(rol.pastikan_wadah_perorangan(ADMIN_B))
    assert w1["instansi"]["id"] == w2["instansi"]["id"]
    assert w1["satker"]["id"] == w2["satker"]["id"]
    assert _jalan(dbx.instansi_luar.count_documents({})) == 1
    assert _galat(_ubah_instansi(w1["instansi"], nama="Lain")).status_code == 400
    assert _galat(rol.hapus_instansi_luar(w1["instansi"]["id"], user=SUPER)).status_code == 400
    assert _galat(rol.hapus_satker_luar(w1["satker"]["id"], user=SUPER)).status_code == 400
    assert _galat(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="Cabang", instansi_id=w1["instansi"]["id"]), user=ADMIN_A)).status_code == 400
    assert _galat(rol.buat_instansi_luar(_instansi(
        kelompok="pihak_ketiga", jenis="perorangan", nama="Budi"), user=ADMIN_A)).status_code == 400


def test_field_badan_pada_eksternal_tersimpan_kosong(dbx):
    i = _buat(nomor_induk="123", npwp="99.999", badan_penyelenggara="Yayasan X")["instansi"]
    simpan = _jalan(dbx.instansi_luar.find_one({"id": i["id"]}, {"_id": 0}))
    assert all(simpan[f] == "" for f in rol.olu.FIELD_KHUSUS_BADAN)


# ── tidak tercampur (3.3) ──────────────────────────────────────────────────
def test_satker_tak_bisa_dipindah_instansi(dbx):
    a = _buat()
    b = _buat(nama="Kementerian Dalam Negeri")
    s = a["satker"]
    e = _galat(rol.ubah_satker_luar(s["id"], rol.SatkerLuarIn(
        nama_satker=s["nama_satker"], instansi_id=b["instansi"]["id"]), _req(),
        user=ADMIN_B))
    assert e.status_code == 400
    tetap = _jalan(dbx.satker_luar.find_one({"id": s["id"]}, {"_id": 0}))
    assert tetap["instansi_id"] == a["instansi"]["id"]
    assert tetap["version"] == 1


def test_kelompok_tak_bisa_diubah_bila_punya_satker(dbx):
    i = _buat()["instansi"]
    e = _galat(_ubah_instansi(i, kelompok="pihak_ketiga", jenis="bumn"))
    assert e.status_code == 400


def test_daftar_satker_wajib_instansi(dbx):
    assert _galat(rol.daftar_satker_luar(_user=USER_A)).status_code == 400


def test_nama_satker_unik_per_instansi(dbx):
    a = _buat()
    b = _buat(nama="Kementerian Dalam Negeri",
              satker_pertama=rol.SatkerLuarIn(nama_satker="Inspektorat Jenderal"))
    # Nama sama di instansi lain diterima.
    s = _jalan(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="Sekretariat Jenderal", instansi_id=b["instansi"]["id"]), user=ADMIN_A))
    assert s["instansi_id"] == b["instansi"]["id"]
    # Nama sama (beda spasi/huruf) di instansi yang sama ditolak.
    e = _galat(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="sekretariat  jenderal", instansi_id=a["instansi"]["id"]), user=ADMIN_A))
    assert e.status_code == 400 and e.detail["id_ada"] == a["satker"]["id"]


def test_kode_luar_tak_boleh_kode_satker_internal(dbx):
    _jalan(dbx.satker.insert_one({"kode_satker": "690525", "nama_satker": "Internal"}))
    i = _buat()["instansi"]
    e = _galat(rol.buat_satker_luar(rol.SatkerLuarIn(
        nama_satker="Biro Umum", kode_luar="690525", instansi_id=i["id"]), user=ADMIN_A))
    assert e.status_code == 400
    assert _jalan(dbx.satker.count_documents({})) == 1   # internal tak tersentuh


def test_kode_referensi_kembar_dalam_kelompok_ditolak(dbx):
    _buat(kode_referensi="015")
    e = _galat(rol.buat_instansi_luar(_instansi(
        nama="Kementerian Lain", kode_referensi="015"), user=ADMIN_B))
    assert e.status_code == 400
    # Kelompok lain boleh memakai kode yang sama.
    _buat(kelompok="pihak_ketiga", jenis="bumn", nama="PT A", kode_referensi="015")


# ── pusat/daerah ───────────────────────────────────────────────────────────
def test_tataran_diturunkan_server(dbx):
    prov = _provinsi()
    kab = _kabkota(prov["id"], tataran="pusat")["instansi"]
    assert kab["tataran"] == "daerah"
    pusat = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", tataran="pusat",
                                            _user=USER_A))
    assert kab["id"] not in [i["id"] for i in pusat["items"]]


def test_jenis_tak_bisa_diganti_bila_punya_satker(dbx):
    i = _buat()["instansi"]
    e = _galat(_ubah_instansi(i, jenis="pemerintah_provinsi"))
    assert e.status_code == 400


# ── jenjang daerah ─────────────────────────────────────────────────────────
def test_kabkota_wajib_berinduk_provinsi(dbx):
    assert _galat(rol.buat_instansi_luar(_instansi(
        jenis="pemerintah_kabkota", nama="Kab X", satker_pertama=None),
        user=ADMIN_A)).status_code == 400
    kl = _buat()["instansi"]
    assert _galat(rol.buat_instansi_luar(_instansi(
        jenis="pemerintah_kabkota", nama="Kab X", induk_id=kl["id"]),
        user=ADMIN_A)).status_code == 400
    prov = _provinsi()
    kab = _kabkota(prov["id"])["instansi"]
    assert _galat(rol.buat_instansi_luar(_instansi(
        jenis="pemerintah_kabkota", nama="Kab Y", induk_id=kab["id"]),
        user=ADMIN_A)).status_code == 400


def test_daftar_per_provinsi_memuat_seluruh_jenjangnya_saja(dbx):
    kaltim = _provinsi()
    kab = _kabkota(kaltim["id"])["instansi"]
    desa = _buat(jenis="pemerintah_desa", nama="Desa Bumi Harapan", induk_id=kab["id"],
                 satker_pertama=None)["instansi"]
    kalsel = _provinsi("Provinsi Kalimantan Selatan")
    _kabkota(kalsel["id"], nama="Kabupaten Banjar")
    hasil = _jalan(rol.daftar_instansi_luar(kelompok="eksternal",
                                            provinsi_id=kaltim["id"], _user=USER_A))
    assert {i["id"] for i in hasil["items"]} == {kaltim["id"], kab["id"], desa["id"]}
    assert desa["kabkota_id"] == kab["id"] and desa["provinsi_id"] == kaltim["id"]


def test_ganti_nama_provinsi_merambat(dbx):
    prov = _provinsi()
    hasil = _kabkota(prov["id"])
    _jalan(dbx.pegawai_luar.insert_one({
        "id": "o1", "instansi_id": hasil["instansi"]["id"],
        "satker_luar_id": hasil["satker"]["id"], "provinsi_nama": prov["nama"]}))
    _jalan(_ubah_instansi(prov, nama="Provinsi Kaltim"))
    kab = _jalan(dbx.instansi_luar.find_one({"id": hasil["instansi"]["id"]}, {"_id": 0}))
    satker = _jalan(dbx.satker_luar.find_one({"id": hasil["satker"]["id"]}, {"_id": 0}))
    orang = _jalan(dbx.pegawai_luar.find_one({"id": "o1"}, {"_id": 0}))
    assert kab["provinsi_nama"] == satker["provinsi_nama"] == orang["provinsi_nama"] \
        == "Provinsi Kaltim"


def test_pindah_kabkota_ke_provinsi_lain_merambat_dan_teraudit(dbx):
    a = _provinsi()
    b = _provinsi("Provinsi Kalimantan Utara")
    hasil = _kabkota(a["id"])
    kab = hasil["instansi"]
    _jalan(_ubah_instansi(kab, induk_id=b["id"]))
    satker = _jalan(dbx.satker_luar.find_one({"id": hasil["satker"]["id"]}, {"_id": 0}))
    assert satker["provinsi_id"] == b["id"]
    log = _jalan(dbx.audit_logs.find_one(
        {"action": "luar_instansi_ubah", "asset_id": kab["id"]}, {"_id": 0}))
    assert {"field": "induk_id", "from": a["id"], "to": b["id"]} in log["changes"]


def test_hapus_provinsi_yang_masih_punya_kabkota_409(dbx):
    prov = _provinsi()
    _kabkota(prov["id"])
    assert _galat(rol.hapus_instansi_luar(prov["id"], user=SUPER)).status_code == 409


# ── daftar ─────────────────────────────────────────────────────────────────
def test_daftar_wajib_kelompok_terpotong_halaman_dan_dicari(dbx):
    assert _galat(rol.daftar_instansi_luar(_user=USER_A)).status_code == 400
    for n in range(5):
        _buat(nama=f"Lembaga {n}", singkatan=f"L{n}", kode_referensi=f"0{n}0")
    hal = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", page=2, page_size=2,
                                          _user=USER_A))
    assert hal["total"] == 5 and len(hal["items"]) == 2
    cari = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", q="L3", _user=USER_A))
    assert [i["nama"] for i in cari["items"]] == ["Lembaga 3"]
    kode = _jalan(rol.daftar_instansi_luar(kelompok="eksternal", q="040", _user=USER_A))
    assert [i["nama"] for i in kode["items"]] == ["Lembaga 4"]
    # Regex karakter khusus tidak meledak.
    _jalan(rol.daftar_instansi_luar(kelompok="eksternal", q="(*", _user=USER_A))


def test_modul_luar_tidak_menulis_koleksi_internal():
    """Invarian 7 — dipindai statis: tak ada operasi tulis ke koleksi internal."""
    import re
    from pathlib import Path
    sumber = Path(rol.__file__).read_text(encoding="utf-8")
    pola = re.compile(r"db\.(pegawai|unit_kerja|satker|assets)\."
                      r"(insert|update|delete|replace|find_one_and|bulk)")
    assert not pola.search(sumber)
