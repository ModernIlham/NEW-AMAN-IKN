"""Uji ENDPOINT belah — bukan hanya helper murninya (Fase 16).

`test_belah_utils.py` menguji geometrinya; berkas ini menguji apa yang terjadi
di DATABASE. Selama ini seluruh gerbang CI (compileall + pytest unit) tak
pernah MENJALANKAN satu endpoint pun, jadi jalur `update_one` / `_sisip_batch`
/ guard satker lolos hijau tanpa sekali pun dieksekusi — dan justru di situ
kesalahan yang mahal bersembunyi: identitas node asal terhapus, saudara lahir
dengan kode kembar, atau pratinjau diam-diam menulis.

Mongo-nya IN-PROCESS (`mongomock_motor`) — tanpa server, tanpa jaringan,
konsisten dengan aturan direktori `tests/unit`.
"""
import asyncio

import pytest
# Diimpor LANGSUNG, bukan lewat importorskip: `mongomock-motor` ada di
# requirements.txt, jadi ketiadaannya adalah kerusakan lingkungan yang harus
# berisik. Uji yang diam-diam di-skip tetap menghijaukan CI tanpa menguji apa
# pun — persis jebakan yang berulang kali muncul di fase-fase sebelumnya.
from mongomock_motor import AsyncMongoMockClient

import routes.spasial as sp
import spasial_utils as su

KOTAK = {"type": "Polygon", "coordinates": [[
    [116.700, -1.402], [116.704, -1.402], [116.704, -1.398],
    [116.700, -1.398], [116.700, -1.402]]]}

USER = {"username": "uji", "role": "admin", "kode_satker": "999999"}

# Melintas penuh dekat tepi bawah → bagian atas jauh lebih besar, sehingga
# "yang terbesar mewarisi asal" benar-benar teruji arahnya.
GARIS_LINTAS = [[116.699, -1.4015], [116.705, -1.4015]]
GARIS_TENGAH = [[116.699, -1.400], [116.705, -1.400]]
GARIS_BUNTU = [[116.701, -1.400], [116.703, -1.400]]   # berhenti di dalam


class _Req:
    """slowapi butuh objek request; endpoint di-unwrap dari limiter sehingga
    hanya atribut sepele ini yang tersentuh."""
    headers: dict = {}
    method = "POST"


def _garis(koor):
    return {"type": "LineString", "coordinates": koor}


def _fungsi():
    """Endpoint tanpa bungkus rate-limit."""
    fn = sp.belah_node
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


@pytest.fixture()
def dbx(monkeypatch):
    """DB in-process yang bersih per test + audit dimatikan (bukan yang diuji)."""
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(sp, "db", fake)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(sp, "log_audit", _diam)
    return fake


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _seed(fake, **ubah):
    dok = {
        "id": "sn_asal", "kode_satker": "999999", "tipe": "kawasan",
        "nama": "Kawasan Inti", "kode": "KW-01", "parent_id": "sn_induk",
        "ancestors": ["sn_induk"], "ancestors_nama": ["Zona A"],
        "jalur": ",sn_induk,sn_asal,", "kedalaman": 1, "ordinal_level": 40,
        "status": "aktif", "geometry": KOTAK, "versi": 3,
    }
    dok.update(ubah)
    await fake.spasial_node.insert_one(dok)
    return dok


async def _belah(nid, koor, terapkan, user=USER):
    return await _fungsi()(nid, sp.BelahIn(garis=_garis(koor), terapkan=terapkan),
                           _Req(), user)


# ── Pratinjau ───────────────────────────────────────────────────────────────

def test_pratinjau_tidak_menulis_apa_pun(dbx):
    """Pratinjau yang diam-diam menulis adalah kerusakan yang tak terlihat
    sampai operator membatalkan lalu menemukan node draft yang tak ia buat."""
    async def skenario():
        await _seed(dbx)
        r = await _belah("sn_asal", GARIS_TENGAH, terapkan=False)
        assert r["pratinjau"] is True and r["jumlah"] == 2
        assert await dbx.spasial_node.count_documents({}) == 1
        asal = await dbx.spasial_node.find_one({"id": "sn_asal"})
        assert asal["geometry"] == KOTAK
        assert asal["versi"] == 3
    _jalan(skenario())


def test_pratinjau_melaporkan_luas_tiap_bagian(dbx):
    async def skenario():
        await _seed(dbx)
        r = await _belah("sn_asal", GARIS_LINTAS, terapkan=False)
        luas = [b["luas_m2"] for b in r["bagian"]]
        assert all(v > 0 for v in luas)
        assert luas[0] > luas[1], "bagian tidak diurutkan dari yang terbesar"
        assert abs(sum(luas) - su.luas_kasar_m2(KOTAK)) / su.luas_kasar_m2(KOTAK) < 0.01
    _jalan(skenario())


# ── Terapkan ────────────────────────────────────────────────────────────────

def test_asal_mempertahankan_identitasnya(dbx):
    """Kode, nama, dan id asal WAJIB utuh — di sanalah aset serta riwayat
    menempel. Mengganti node lama dengan dua node baru memutus keduanya."""
    async def skenario():
        await _seed(dbx)
        await _belah("sn_asal", GARIS_LINTAS, terapkan=True)
        asal = await dbx.spasial_node.find_one({"id": "sn_asal"})
        assert asal["kode"] == "KW-01"
        assert asal["nama"] == "Kawasan Inti"
        assert asal["status"] == "aktif"
        assert asal["versi"] == 4, "versi tak naik — klien tak tahu data berubah"
        assert asal["geometry"] != KOTAK, "geometri asal tidak diperbarui"
        assert asal.get("bbox") and asal.get("titik_wakil")
    _jalan(skenario())


def test_bagian_terbesar_yang_mewarisi_node_asal(dbx):
    async def skenario():
        await _seed(dbx)
        r = await _belah("sn_asal", GARIS_LINTAS, terapkan=True)
        asal = await dbx.spasial_node.find_one({"id": "sn_asal"})
        baru = await dbx.spasial_node.find_one({"id": r["node_baru"][0]})
        assert asal["metrik"]["luas_m2"] > baru["metrik"]["luas_m2"]
    _jalan(skenario())


def test_saudara_lahir_draft_tanpa_kode_kembar(dbx):
    """Kode BMN harus unik; pecahan yang mewarisi kode asal membuat dua node
    berkode sama — persis jenis kerusakan yang sulit dilacak belakangan."""
    async def skenario():
        await _seed(dbx)
        r = await _belah("sn_asal", GARIS_LINTAS, terapkan=True)
        baru = await dbx.spasial_node.find_one({"id": r["node_baru"][0]})
        assert baru["kode"] == ""
        assert baru["status"] == "draft"
        assert baru["nama"] == "Kawasan Inti (2)"
        assert baru["properties"]["belah"]["dari"] == "sn_asal"
    _jalan(skenario())


def test_saudara_menempel_pada_induk_dan_tingkat_yang_sama(dbx):
    """Pecahan adalah SAUDARA, bukan anak. Salah menaruhnya di bawah node asal
    membuat luas terhitung ganda saat direkap per tingkat."""
    async def skenario():
        asal_awal = await _seed(dbx)
        r = await _belah("sn_asal", GARIS_LINTAS, terapkan=True)
        baru = await dbx.spasial_node.find_one({"id": r["node_baru"][0]})
        assert baru["parent_id"] == asal_awal["parent_id"]
        assert baru["ancestors"] == asal_awal["ancestors"]
        assert baru["ordinal_level"] == asal_awal["ordinal_level"]
        assert baru["kedalaman"] == asal_awal["kedalaman"]
        assert baru["jalur"] == f",sn_induk,{baru['id']},", baru["jalur"]
        assert baru["kode_satker"] == "999999"
    _jalan(skenario())


def test_luas_kekal_setelah_tertulis_ke_db(dbx):
    """Pemeriksaan di helper memakai geometri di memori; ini memeriksa angka
    yang BENAR-BENAR tersimpan, termasuk pembulatan dua desimal."""
    async def skenario():
        await _seed(dbx)
        r = await _belah("sn_asal", GARIS_LINTAS, terapkan=True)
        asal = await dbx.spasial_node.find_one({"id": "sn_asal"})
        baru = await dbx.spasial_node.find_one({"id": r["node_baru"][0]})
        total = asal["metrik"]["luas_m2"] + baru["metrik"]["luas_m2"]
        awal = su.luas_kasar_m2(KOTAK)
        assert abs(total - awal) / awal < 0.01
    _jalan(skenario())


# ── Penolakan ───────────────────────────────────────────────────────────────

def test_garis_buntu_ditolak_tanpa_menyentuh_db(dbx):
    """Kegagalan paling sering di lapangan. Yang diperiksa di sini bukan hanya
    status 400, melainkan bahwa DB tidak berubah sedikit pun."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(sp.HTTPException) as e:
            await _belah("sn_asal", GARIS_BUNTU, terapkan=True)
        assert e.value.status_code == 400
        assert "keluar melewati batas" in e.value.detail
        assert await dbx.spasial_node.count_documents({}) == 1
        asal = await dbx.spasial_node.find_one({"id": "sn_asal"})
        assert asal["versi"] == 3 and asal["geometry"] == KOTAK
    _jalan(skenario())


def test_node_tanpa_geometri_ditolak(dbx):
    async def skenario():
        await _seed(dbx, geometry=None)
        with pytest.raises(sp.HTTPException) as e:
            await _belah("sn_asal", GARIS_TENGAH, terapkan=True)
        assert e.value.status_code == 400
        assert "belum punya bentuk" in e.value.detail
    _jalan(skenario())


def test_node_dihapus_dan_tak_ada_sama_sama_404(dbx):
    """Node berstatus `dihapus` tak boleh bisa dibelah — membelahnya
    menghidupkan kembali wilayah lewat pintu belakang."""
    async def skenario():
        await _seed(dbx, status="dihapus")
        for nid in ("sn_asal", "sn_entah"):
            with pytest.raises(sp.HTTPException) as e:
                await _belah(nid, GARIS_TENGAH, terapkan=True)
            assert e.value.status_code == 404
    _jalan(skenario())


def test_satker_lain_tak_boleh_membelah(dbx):
    """Guard isolasi satker dijalankan SUNGGUHAN di jalur ini, bukan diasumsikan."""
    async def skenario():
        await _seed(dbx)
        lain = {"username": "orang_lain", "role": "admin", "kode_satker": "111111"}
        with pytest.raises(sp.HTTPException) as e:
            await _belah("sn_asal", GARIS_TENGAH, terapkan=True, user=lain)
        assert e.value.status_code == 403
        assert await dbx.spasial_node.count_documents({}) == 1
    _jalan(skenario())
