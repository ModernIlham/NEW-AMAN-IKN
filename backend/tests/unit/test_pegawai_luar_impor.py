"""Impor/ekspor/templat orang luar (PGW-04).

Rencana: docs/RENCANA-MASTER-PEGAWAI-EKSTERNAL.md — PGW-04, 3.7b–d.
"""
import asyncio
import io

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient
from openpyxl import load_workbook
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request

import organisasi_luar_utils as olu
import routes.organisasi_luar as rol
import routes.pegawai as rp
import routes.pegawai_luar as rpl
from pegawai_utils import HEADER_IMPOR

ADMIN_A = {"username": "admin_a", "role": "admin", "kode_satker": "111111"}
ADMIN_B = {"username": "admin_b", "role": "admin", "kode_satker": "222222"}


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
def dbx(monkeypatch, mongomock_update_sort_compat):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rol, rpl, rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(su.limiter, "enabled", False)

    async def langsung(fungsi, *a, **k):
        return fungsi(*a, **k)
    import render_executor
    monkeypatch.setattr(render_executor, "run_renderer", langsung)
    return fake


def _satker(kelompok="eksternal", jenis="kementerian_lembaga", nama="Kementerian X",
            satker="Sekretariat"):
    return _jalan(rol.buat_instansi_luar(rol.InstansiLuarIn(
        kelompok=kelompok, jenis=jenis, nama=nama,
        satker_pertama=rol.SatkerLuarIn(nama_satker=satker)), user=ADMIN_A))["satker"]


def _berkas(data: bytes, nama="impor.xlsx"):
    return UploadFile(file=io.BytesIO(data), filename=nama,
                      headers=Headers({"content-type": "application/octet-stream"}))


def _ekspor(satker_id):
    resp = _jalan(rpl.export_pegawai_luar_xlsx(satker_luar_id=satker_id, _user=ADMIN_A))
    return resp.body


def _impor(satker_id, data, user=ADMIN_A, nama="impor.xlsx"):
    return _jalan(rpl.impor_pegawai_luar(_req(), _berkas(data, nama),
                                         satker_luar_id=satker_id, user=user))


def _csv(header, *baris):
    import csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for b in baris:
        w.writerow([b.get(h, "") for h in header])
    return buf.getvalue().encode("utf-8-sig")


# ── header ─────────────────────────────────────────────────────────────────
def test_header_eksternal_tepat_tujuh_kolom_pribadi_berkurang_urutan_sama():
    e = olu.header_impor_luar("eksternal")
    hilang = [h for h in HEADER_IMPOR if h not in e]
    assert len(hilang) == 7
    assert {olu._field_header(h) for h in hilang} == set(olu.FIELD_PRIBADI_LUAR)
    assert e == [h for h in HEADER_IMPOR if h in e]


def test_header_pihak_ketiga_tanpa_kolom_37c():
    p = olu.header_impor_luar("pihak_ketiga")
    balik = {v: k for k, v in olu.SEBUTAN_KOLOM_PIHAK_KETIGA.items()}
    field = {olu._field_header(balik.get(h, h)) for h in p}
    assert not field & set(olu.FIELD_NONAKTIF["pihak_ketiga"])
    assert p[:1] == ["NIK"] and "Tingkat I" in p and "Eselon 1" not in p
    assert p[-4:] == list(olu.KOLOM_KHUSUS_PIHAK_KETIGA)


# ── pulang-pergi ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("kelompok,jenis,khusus", [
    ("eksternal", "kementerian_lembaga", {}),
    ("pihak_ketiga", "bumn", {"kapasitas_bertindak": "penerima_kuasa",
                              "dasar_kewenangan_jenis": "surat_kuasa",
                              "dasar_kewenangan_nomor": "SK-9",
                              "dasar_kewenangan_tanggal": "2026-01-02"}),
])
def test_pulang_pergi(dbx, kelompok, jenis, khusus):
    s = _satker(kelompok, jenis, nama=f"Instansi {kelompok}")
    _jalan(rpl.buat_pegawai_luar(rpl.PegawaiLuarIn(
        nama="Budi", nip="198001012005011001", jabatan="Analis", eselon1="Setjen",
        status="aktif", satker_luar_id=s["id"], **khusus), user=ADMIN_A))
    asli = _jalan(dbx.pegawai_luar.find_one({}, {"_id": 0}))
    data = _ekspor(s["id"])
    ws = load_workbook(io.BytesIO(data)).active
    assert [c.value for c in ws[1]] == olu.header_impor_luar(kelompok)
    hasil = _impor(s["id"], data)
    assert (hasil["dibuat"], hasil["dilewati"]) == (0, 0)
    assert _jalan(dbx.pegawai_luar.count_documents({})) == 1
    baru = _jalan(dbx.pegawai_luar.find_one({}, {"_id": 0}))
    for f in ("nama", "nip", "jabatan", "eselon1", "status", "status_kepegawaian",
              *olu.FIELD_KHUSUS_PIHAK_KETIGA):
        assert baru.get(f, "") == asli.get(f, ""), f


# ── isolasi & idempotensi ──────────────────────────────────────────────────
def test_impor_ke_satker_x_tidak_mengubah_satker_lain_dan_tak_menggandakan(dbx):
    x = _satker(nama="Kementerian X")
    y = _satker(nama="Kementerian Y")
    _jalan(rpl.buat_pegawai_luar(rpl.PegawaiLuarIn(
        nama="Sama Nama", tanggal_lahir="1980-01-01", jabatan="Lama",
        satker_luar_id=y["id"]), user=ADMIN_A))
    sebelum_y = _jalan(dbx.pegawai_luar.find({"satker_luar_id": y["id"]}, {"_id": 0}).to_list(10))
    header = olu.header_impor_luar("eksternal")
    berkas = _csv(header, {"Nama Lengkap": "Sama Nama", "Tgl Lahir": "1980-01-01",
                           "Jabatan": "Baru"},
                  {"Nama Lengkap": "Orang Dua", "NIP/NIK/NRP": "198101012005011002"})
    h1 = _impor(x["id"], berkas, nama="a.csv")
    assert h1["dibuat"] == 2
    h2 = _impor(x["id"], berkas, user=ADMIN_B, nama="a.csv")
    assert h2["dibuat"] == 0
    assert _jalan(dbx.pegawai_luar.count_documents({"satker_luar_id": x["id"]})) == 2
    sesudah_y = _jalan(dbx.pegawai_luar.find({"satker_luar_id": y["id"]}, {"_id": 0}).to_list(10))
    assert sesudah_y == sebelum_y
    satu = _jalan(dbx.pegawai_luar.find_one({"nama": "Orang Dua"}, {"_id": 0}))
    assert satu["instansi_nama"] == "Kementerian X" and "kode_satker" not in satu


def test_nip_pegawai_internal_dilewati_dan_internal_tak_berubah(dbx):
    internal = {"id": "p1", "nama": "Siti Rahayu", "nip": "198001012005011001",
                "kode_satker": "999999", "jabatan": "Kepala"}
    _jalan(dbx.pegawai.insert_one(dict(internal)))
    s = _satker()
    berkas = _csv(olu.header_impor_luar("eksternal"),
                  {"Nama Lengkap": "Siti Lain", "NIP/NIK/NRP": "198001012005011001",
                   "Jabatan": "Ditimpa"})
    hasil = _impor(s["id"], berkas, nama="a.csv")
    assert (hasil["dibuat"], hasil["dilewati"]) == (0, 1)
    assert "Siti Rahayu" not in str(hasil["catatan"])
    assert _jalan(dbx.pegawai.find_one({"id": "p1"}, {"_id": 0})) == internal
    assert _jalan(dbx.pegawai_luar.count_documents({})) == 0


def test_nip_di_satker_luar_lain_dilewati(dbx):
    x, y = _satker(nama="Kementerian X"), _satker(nama="Kementerian Y")
    _jalan(rpl.buat_pegawai_luar(rpl.PegawaiLuarIn(
        nama="Budi", nip="198001012005011001", satker_luar_id=y["id"]), user=ADMIN_A))
    berkas = _csv(olu.header_impor_luar("eksternal"),
                  {"Nama Lengkap": "Budi", "NIP/NIK/NRP": "198001012005011001"})
    hasil = _impor(x["id"], berkas, nama="a.csv")
    assert hasil["dilewati"] == 1
    assert _jalan(dbx.pegawai_luar.count_documents({"satker_luar_id": x["id"]})) == 0


def test_pihak_ketiga_kolom_pribadi_diabaikan_dan_non_asn(dbx):
    s = _satker("pihak_ketiga", "bumn", nama="PT A", satker="Kantor Pusat")
    header = olu.header_impor_luar("pihak_ketiga") + ["Agama", "NPWP"]
    berkas = _csv(header, {"Nama Lengkap": "Ani", "NIK": "6471010101850001",
                           "Agama": "Islam", "NPWP": "12.3", "Tingkat I": "Direksi",
                           "Kapasitas Bertindak": "Penerima kuasa",
                           "Status Kepegawaian": "PNS"})
    _impor(s["id"], berkas, nama="a.csv")
    o = _jalan(dbx.pegawai_luar.find_one({}, {"_id": 0}))
    assert (o["agama"], o["npwp"], o["status_kepegawaian"]) == ("", "", "non_asn")
    assert o["eselon1"] == "Direksi" and o["kapasitas_bertindak"] == "penerima_kuasa"


# ── wajib satker / kelompok ────────────────────────────────────────────────
def test_tanpa_satker_atau_kelompok_400(dbx):
    assert _galat(rpl.export_pegawai_luar_xlsx(_user=ADMIN_A)).status_code == 400
    assert _galat(rpl.impor_pegawai_luar(_req(), _berkas(b"x"), satker_luar_id="",
                                         user=ADMIN_A)).status_code == 400
    assert _galat(rpl.template_impor_pegawai_luar(_user=ADMIN_A)).status_code == 400


def test_templat_per_kelompok_selaras_header(dbx):
    for k in olu.KELOMPOK_LUAR:
        resp = _jalan(rpl.template_impor_pegawai_luar(kelompok=k, _user=ADMIN_A))
        baris = resp.body.decode("utf-8-sig").splitlines()
        import csv
        header, contoh = list(csv.reader(baris))[:2]
        assert header == olu.header_impor_luar(k) and len(contoh) == len(header)
