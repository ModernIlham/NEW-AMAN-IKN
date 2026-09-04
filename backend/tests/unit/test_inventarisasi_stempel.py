"""Stempel waktu inventarisasi — kapan aset BENAR-BENAR diperiksa.

Permintaan pemilik: *"lanjutkan dengan membuat lini masanya"* — linimasa
yang sungguhan, bukan turunan periode kegiatan.

Sebelum ini aset tak menyimpan kapan ia diperiksa, sehingga linimasa hanya
bisa menempatkan SELURUH aset satu kegiatan pada bulan kegiatan itu dimulai.
`updated_at` bukan penggantinya: ia ter-cap pada SETIAP penyuntingan, jadi
aset yang diperiksa Mei lalu fotonya diperbaiki Juli meloncat ke Juli —
linimasa tampak presisi justru pada saat ia paling keliru.
"""
import inventarisasi_stempel as st


def _cap(existing, update, sekarang="2026-05-10T08:00:00+00:00"):
    dipasang = st.stempel(existing, update, sekarang)
    return dipasang, update.get(st.FIELD)


# ── Kapan dicap ─────────────────────────────────────────────────────────

def test_transisi_pertama_dicap():
    dipasang, nilai = _cap({"inventory_status": st.BELUM},
                           {"inventory_status": "Ditemukan"})
    assert dipasang and nilai == "2026-05-10T08:00:00+00:00"


def test_status_kosong_dianggap_belum_diperiksa():
    """Dokumen lama sempat lahir tanpa field ini sama sekali; memperlakukan
    kosong sebagai 'sudah diperiksa' akan membuat aset itu tak pernah dicap."""
    assert _cap({}, {"inventory_status": "Ditemukan"})[0] is True
    assert _cap({"inventory_status": ""}, {"inventory_status": "Ditemukan"})[0] is True


def test_aset_berlebih_yang_baru_lahir_ikut_dicap():
    """Aset "Berlebih" diciptakan JUSTRU karena barangnya ada di lapangan.
    Tanpa cap, seluruh temuan berlebih hilang dari linimasa."""
    assert _cap({}, {"inventory_status": "Berlebih"})[0] is True


# ── Kapan TIDAK dicap ───────────────────────────────────────────────────

def test_cap_kedua_tak_menggeser_yang_pertama():
    """Sifat yang membuat linimasa stabil. Mengoreksi kondisi atau mengubah
    status dari Ditemukan ke Sengketa BUKAN pemeriksaan baru — kalau
    menggeser, batang bulan lalu menyusut tiap kali seseorang menyunting."""
    lama = {"inventory_status": "Ditemukan",
            st.FIELD: "2026-05-01T00:00:00+00:00"}
    dipasang, _ = _cap(lama, {"inventory_status": "Sengketa"},
                       sekarang="2026-09-01T00:00:00+00:00")
    assert dipasang is False


def test_kembali_ke_belum_tak_mencap():
    assert _cap({}, {"inventory_status": st.BELUM})[0] is False
    assert _cap({}, {"inventory_status": ""})[0] is False


def test_penyuntingan_yang_tak_menyentuh_status_tak_mencap():
    """Mengganti foto atau memperbaiki merk bukan pemeriksaan."""
    assert _cap({"inventory_status": st.BELUM}, {"brand": "Baru"})[0] is False


def test_nilai_dari_badan_permintaan_TIDAK_dipercaya():
    """Tanggal yang bisa diketik mengubah linimasa dari catatan menjadi
    pendapat. Bila klien menyertakan field ini, nilainya dibuang: yang
    berlaku adalah cap server (atau cap lama, bila sudah ada)."""
    u = {"inventory_status": "Ditemukan", st.FIELD: "1999-01-01T00:00:00"}
    dipasang, nilai = _cap({"inventory_status": st.BELUM}, u)
    assert dipasang and nilai == "2026-05-10T08:00:00+00:00"

    u2 = {"inventory_status": "Sengketa", st.FIELD: "1999-01-01T00:00:00"}
    dipasang2, nilai2 = _cap(
        {"inventory_status": "Ditemukan", st.FIELD: "2026-05-01T00:00:00"}, u2)
    assert dipasang2 is False
    assert nilai2 == "2026-05-01T00:00:00", "cap lama harus bertahan"


def test_aset_lama_sudah_diperiksa_tapi_belum_bercap_ikut_dicap():
    """Data yang ada sebelum stempel diperkenalkan: begitu disentuh dengan
    perubahan status, ia mendapat tanggal. Tanpa ini ia selamanya bergantung
    pada perkiraan periode kegiatan."""
    dipasang, nilai = _cap({"inventory_status": "Ditemukan"},
                           {"inventory_status": "Sengketa"})
    assert dipasang and nilai == "2026-05-10T08:00:00+00:00"


# ── Fragmen query untuk ubah massal ─────────────────────────────────────

def test_filter_menangkap_field_hilang_DAN_kosong():
    """Ubah massal menulis dengan satu `update_many` dan tak bisa memeriksa
    dokumen satu per satu. Memeriksa salah satu keadaan saja akan melewatkan
    separuh data lama."""
    f = st.filter_belum_berstempel()
    syarat = f["$or"]
    assert {"tanggal_inventarisasi": {"$exists": False}} in syarat
    assert {"tanggal_inventarisasi": ""} in syarat
    assert {"tanggal_inventarisasi": None} in syarat


def test_nama_field_satu_sumber():
    """Salah ketik di salah satu rute menghasilkan field kembar yang senyap —
    aset punya dua tanggal, laporan membaca yang kosong."""
    assert st.FIELD == "tanggal_inventarisasi"


# ── Penyambungan ke jalur tulis ─────────────────────────────────────────
#
# Modul di atas boleh benar sempurna dan tetap tak berguna bila tak ada yang
# memanggilnya. Mutasi "PATCH tak lagi mencap" LOLOS pada percobaan pertama:
# seluruh uji di atas hijau sementara linimasa diam-diam kembali ke perkiraan
# periode kegiatan. Bagian ini menutup celah itu.

import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.assets as ra
import routes.batch as rb


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


class _Permintaan:
    """Request tiruan seperlunya untuk `patch_asset`."""

    def __init__(self, badan):
        self._badan = badan
        self.headers = {}

    async def json(self):
        return self._badan


@pytest.fixture()
def dba(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (ra, rb, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        for nama in ("log_audit", "notify_asset_change", "invalidate_asset_cache",
                     "jadwalkan_sync", "jadwalkan_hapus", "catat_audit_aset",
                     "pastikan_akses_aset", "ensure_activity_not_sealed",
                     "pastikan_akses_kegiatan_id"):
            if hasattr(mod, nama):
                monkeypatch.setattr(mod, nama, _diam, raising=False)
    return fake


def test_PATCH_mencap_saat_status_berubah(dba, monkeypatch):
    """Jalur yang dipakai kamera lapangan, lembar edit cepat, dan antrean
    luring — semuanya bermuara ke PATCH ini."""
    async def _tanpa_penempatan(*a, **k):
        return None
    monkeypatch.setattr(ra.sp, "penempatan_dari_inventarisasi",
                        _tanpa_penempatan, raising=False)

    async def jalan():
        await dba.assets.insert_one({
            "id": "a1", "activity_id": "k1", "asset_name": "Kursi",
            "asset_code": "3050104001", "NUP": "1", "category": "Peralatan",
            "inventory_status": "Belum Diinventarisasi", "version": 1,
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        await ra.patch_asset("a1", _Permintaan({"inventory_status": "Ditemukan"}),
                             _user={"username": "op", "role": "admin",
                                    "kode_satker": "401234"})
        doc = await dba.assets.find_one({"id": "a1"})
        assert doc.get("tanggal_inventarisasi"), "PATCH tak mencap"
        # Cap kedua tak boleh menggeser.
        cap1 = doc["tanggal_inventarisasi"]
        await ra.patch_asset("a1", _Permintaan({"inventory_status": "Sengketa"}),
                             _user={"username": "op", "role": "admin",
                                    "kode_satker": "401234"})
        doc2 = await dba.assets.find_one({"id": "a1"})
        assert doc2["tanggal_inventarisasi"] == cap1
    _jalan(jalan())


def test_ubah_massal_mencap_hanya_yang_belum_bercap(dba):
    """Ubah massal menulis dengan satu `update_many`, jadi stempelnya dipasang
    lewat tulisan kedua yang disaring. Tanpa saringan itu, satu klik 'tandai
    ditemukan' akan menggeser tanggal SELURUH aset yang dipilih."""
    async def jalan():
        await dba.assets.insert_many([
            {"id": "b1", "activity_id": "k1", "inventory_status": "Belum Diinventarisasi", "version": 1},
            {"id": "b2", "activity_id": "k1", "inventory_status": "Ditemukan",
             "tanggal_inventarisasi": "2026-01-05T00:00:00+00:00", "version": 1},
        ])
        # Tulisan utama + tulisan stempel, persis seperti di rute.
        now = "2026-08-20T00:00:00+00:00"
        await dba.assets.update_many(
            {"id": {"$in": ["b1", "b2"]}},
            {"$set": {"inventory_status": "Ditemukan", "updated_at": now}})
        await dba.assets.update_many(
            {"id": {"$in": ["b1", "b2"]}, **st.filter_belum_berstempel()},
            {"$set": {st.FIELD: now}})
        b1 = await dba.assets.find_one({"id": "b1"})
        b2 = await dba.assets.find_one({"id": "b2"})
        assert b1[st.FIELD] == now, "aset baru tak dicap"
        assert b2[st.FIELD] == "2026-01-05T00:00:00+00:00", "cap lama tergeser"
    _jalan(jalan())


def test_setiap_jalur_tulis_memanggil_stempel():
    """Penjagaan terakhir, dibaca dari sumbernya: empat jalur dapat mengubah
    `inventory_status` — buat, PUT, PATCH, dan ubah massal. Jalur yang lupa
    memanggil stempel akan membuat sebagian pekerjaan lapangan hilang dari
    linimasa tanpa satu pun gejala."""
    import inspect
    sumber_aset = inspect.getsource(ra)
    assert sumber_aset.count("stempel_inv.stempel(") >= 3, (
        "buat, PUT, dan PATCH masing-masing harus mencap")
    sumber_batch = inspect.getsource(rb)
    assert "stempel_inv.filter_belum_berstempel()" in sumber_batch, (
        "ubah massal tak mencap")
