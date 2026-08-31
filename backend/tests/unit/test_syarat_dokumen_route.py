"""Rute referensi syarat dokumen + penyambungannya ke lampiran PSP."""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rp
import routes.syarat_dokumen as rs

USER = {"username": "penulis", "role": "admin", "kode_satker": "111111"}
LAIN = {"username": "asing", "role": "admin", "kode_satker": "222222"}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


# ── Rute referensi ─────────────────────────────────────────────────────────

def test_daftar_rezim_menyebut_semuanya():
    r = _jalan(rs.daftar_rezim(_user=USER))
    kode = {x["kode"] for x in r["rezim"]}
    assert {"psp", "hibah", "alih_status", "penjualan_lelang"} <= kode
    assert len(r["jenis_objek"]) == 4


def test_rezim_tak_dikenal_ditolak_dengan_pilihannya():
    with pytest.raises(HTTPException) as e:
        _jalan(rs.daftar_syarat(rezim="entah", _user=USER))
    assert e.value.status_code == 400
    assert "psp" in str(e.value.detail)


def test_jenis_objek_tak_dikenal_ditolak():
    with pytest.raises(HTTPException) as e:
        _jalan(rs.daftar_syarat(rezim="psp", jenis_objek="gedung", _user=USER))
    assert e.value.status_code == 400


def test_syarat_psp_kendaraan_tanpa_sertipikat():
    r = _jalan(rs.daftar_syarat(rezim="psp", jenis_objek="selain_tb",
                                punya_dokumen_kepemilikan=True, _user=USER))
    wajib = {b["kode"] for b in r["butir"] if b["wajib"]}
    assert "sertipikat" not in wajib and "dok_kepemilikan" in wajib
    assert r["berdasar_pasal"] is True


def test_terunggah_mengurangi_kekurangan():
    kosong = _jalan(rs.daftar_syarat(rezim="psp", jenis_objek="tanah", _user=USER))
    isi = _jalan(rs.daftar_syarat(rezim="psp", jenis_objek="tanah",
                                  terunggah="surat_permohonan,sertipikat",
                                  _user=USER))
    assert isi["jumlah_terpenuhi"] == kosong["jumlah_terpenuhi"] + 2


def test_terunggah_mengabaikan_koma_kosong():
    r = _jalan(rs.daftar_syarat(rezim="psp", jenis_objek="tanah",
                                terunggah=" , ,surat_permohonan, ", _user=USER))
    assert r["jumlah_terpenuhi"] == 1


def test_pilihan_ikut_dikembalikan_untuk_dropdown():
    r = _jalan(rs.daftar_syarat(rezim="hibah", _user=USER))
    assert r["pilihan"] and r["pilihan"][-1]["kode"] == "dokumen_lainnya"


def test_rezim_belum_terverifikasi_ditandai():
    r = _jalan(rs.daftar_syarat(rezim="penjualan_lelang", _user=USER))
    assert r["berdasar_pasal"] is False


# ── Konteks dokumen pada SK PSP ────────────────────────────────────────────

async def _seed(dbx, **ganti):
    doc = {"id": "sk-1", "kode_satker": USER["kode_satker"], "jenis": "psp",
           "nomor_sk": "SK-1", "tanggal_sk": "2026-01-01",
           "status_pengajuan": "draf", "lampiran": [], "aset": []}
    doc.update(ganti)
    await dbx.psp.insert_one(doc)
    return doc


def test_konteks_tersimpan_dan_mengubah_kelengkapan(dbx):
    async def skenario():
        await _seed(dbx)
        return await rp.simpan_konteks_dokumen_psp(
            "sk-1", rp.KonteksDokumenIn(jenis_objek="tanah"), user=USER)
    r = _jalan(skenario())
    wajib = {b["kode"] for b in r["kelengkapan"]["butir"] if b["wajib"]}
    assert "sertipikat" in wajib and "imb_pbg" not in wajib
    assert r["konteks_dokumen"]["jenis_objek"] == "tanah"


def test_konteks_jenis_objek_ngawur_ditolak(dbx):
    async def skenario():
        await _seed(dbx)
        return await rp.simpan_konteks_dokumen_psp(
            "sk-1", rp.KonteksDokumenIn(jenis_objek="ruko"), user=USER)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400


def test_konteks_sk_tak_ada_404(dbx):
    async def skenario():
        return await rp.simpan_konteks_dokumen_psp(
            "sk-hantu", rp.KonteksDokumenIn(jenis_objek="tanah"), user=USER)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 404


def test_konteks_satker_lain_ditolak(dbx):
    """Keadaan objek menentukan berkas mana yang wajib — mengubahnya dari
    satker lain sama dengan melonggarkan syarat usulan orang."""
    async def skenario():
        await _seed(dbx)
        return await rp.simpan_konteks_dokumen_psp(
            "sk-1", rp.KonteksDokumenIn(jenis_objek="tanah"), user=LAIN)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code in (403, 404)


def test_kelengkapan_menghitung_jenis_lampiran_yang_sudah_ada(dbx):
    async def skenario():
        await _seed(dbx, lampiran=[
            {"file_id": "f1", "jenis": "surat_permohonan"},
            {"file_id": "f2", "jenis": "sertipikat"},
            {"file_id": "f3"},                       # warisan: tanpa jenis
        ])
        return await rp.simpan_konteks_dokumen_psp(
            "sk-1", rp.KonteksDokumenIn(jenis_objek="tanah"), user=USER)
    k = _jalan(skenario())["kelengkapan"]
    assert k["jumlah_terpenuhi"] == 2
    assert "surat_permohonan" not in [b["kode"] for b in k["kurang"]]
