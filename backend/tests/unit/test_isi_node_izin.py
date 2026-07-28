"""Uji IZIN pada /spasial/node/{id}/isi — Mongo in-process, tanpa jaringan.

Endpoint ini dulu menyaring izin lewat GELUNG setelah hasil kembali:

    rows = ...find(...).to_list(500)          # dipotong DULU
    for r in rows:
        await pastikan_akses_aset(user, r)    # baru disaring

Dua cacat sekaligus, dan keduanya nyata:

1. BENAR. Pemotongan mendahului penyaringan, sehingga pengguna satker bisa
   menerima jauh kurang dari 500 aset yang BERHAK ia lihat — angka yang lalu
   dipakai untuk opname fisik.
2. CEPAT. `pastikan_akses_aset` menembak `inventory_activities.find_one` untuk
   TIAP baris: sampai 500 perjalanan bolak-balik berurutan.

Penyaring kini berjalan di dalam kueri. Memindahkan aturan OTORISASI ke tempat
lain berarti MENYALINNYA, dan salinan bisa menyimpang dari aslinya diam-diam.
Karena itu berkas ini tidak berhenti pada "hasilnya benar": uji terakhir
membandingkan hasil kueri BARIS-PER-BARIS terhadap gelung guard yang ASLI, atas
seluruh fixture — termasuk kasus tepi era-lama dan aset yatim.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.spasial as rs

SATKER_A = "111111"
SATKER_B = "222222"
USER_A = {"username": "a", "role": "admin", "kode_satker": SATKER_A}
USER_SUPER = {"username": "sa", "role": "super_admin", "kode_satker": ""}


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rs, "db", fake)
    monkeypatch.setattr(rs, "log_audit", _diam)
    import shared_utils as su_mod
    monkeypatch.setattr(su_mod, "db", fake)
    return fake


def _aset(i, keg, nama=None):
    return {"id": i, "activity_id": keg, "asset_code": "3.05.01.05.007",
            "NUP": i[-1], "asset_name": nama or f"Barang {i}",
            "lokasi_spasial": {"node_id": "r305", "node_nama": "Ruang 305"}}


async def _seed(dbx):
    """Satu ruangan, lima aset yang mewakili SELURUH cabang aturan izin."""
    await dbx.spasial_node.insert_one(
        {"id": "r305", "nama": "Ruang 305", "tipe": "RUANGAN", "status": "aktif",
         "kode_satker": SATKER_A, "ancestors": [], "ordinal_level": 60})
    await dbx.inventory_activities.insert_many([
        {"id": "kegA", "nama_kegiatan": "Inventarisasi A", "kode_satker": SATKER_A},
        {"id": "kegB", "nama_kegiatan": "Inventarisasi B", "kode_satker": SATKER_B},
        {"id": "kegLama", "nama_kegiatan": "Era lama", "kode_satker": ""},
    ])
    await dbx.assets.insert_many([
        _aset("a1", "kegA", "A satu"),        # boleh: kegiatan milik satker A
        _aset("a2", "kegB", "B satu"),        # TIDAK: milik satker B
        _aset("a3", "kegLama", "Lama"),       # boleh: kegiatan tanpa stempel satker
        _aset("a4", "", "Tanpa kegiatan"),    # boleh: guard lama return lebih awal
        _aset("a5", "kegHantu", "Yatim"),     # TIDAK: kegiatan induk sudah hilang
    ])


def _ambil(user, dalam=False):
    return _jalan(rs.isi_node("r305", dalam=dalam, _user=user))


def test_pengguna_satker_hanya_melihat_yang_berhak(dbx):
    _jalan(_seed(dbx))
    hasil = _ambil(USER_A)
    assert {i["id"] for i in hasil["items"]} == {"a1", "a3", "a4"}


def test_aset_satker_lain_tidak_bocor(dbx):
    """Penjaga utama: aset satker B menunjuk node satker A (bisa terjadi pada
    data era-lama) tetap TIDAK boleh terbaca."""
    _jalan(_seed(dbx))
    assert "a2" not in {i["id"] for i in _ambil(USER_A)["items"]}


def test_aset_yatim_ditolak_fail_closed(dbx):
    """Kegiatan induk sudah dihapus → kepemilikan tak dapat dipastikan. Guard
    lama sengaja menolak (REVIEW-9 R15); versi kueri harus sama."""
    _jalan(_seed(dbx))
    assert "a5" not in {i["id"] for i in _ambil(USER_A)["items"]}


def test_super_admin_melihat_semua(dbx):
    _jalan(_seed(dbx))
    assert {i["id"] for i in _ambil(USER_SUPER)["items"]} == {
        "a1", "a2", "a3", "a4", "a5"}


def test_penyaringan_terjadi_SEBELUM_pemotongan(dbx, monkeypatch):
    """INTI PERBAIKAN. Plafon diturunkan ke 2, lalu ruangan diisi aset satker
    LAIN yang namanya berurutan lebih dulu.

    Versi lama: 2 baris teratas (milik satker B) terambil, lalu keduanya
    tersaring keluar → pengguna melihat NOL aset padahal ia berhak atas dua.
    Versi kueri: yang tak berhak tak pernah ikut terambil sejak awal.
    """
    monkeypatch.setattr(rs, "_MAKS_ISI_NODE", 2)
    _jalan(dbx.spasial_node.insert_one(
        {"id": "r305", "nama": "Ruang 305", "tipe": "RUANGAN", "status": "aktif",
         "kode_satker": SATKER_A, "ancestors": [], "ordinal_level": 60}))
    _jalan(dbx.inventory_activities.insert_many([
        {"id": "kegA", "nama_kegiatan": "A", "kode_satker": SATKER_A},
        {"id": "kegB", "nama_kegiatan": "B", "kode_satker": SATKER_B},
    ]))
    _jalan(dbx.assets.insert_many([
        _aset("b1", "kegB", "AAA milik B"),   # urut pertama menurut asset_name
        _aset("b2", "kegB", "AAB milik B"),
        _aset("a1", "kegA", "ZZA milik A"),
        _aset("a2", "kegA", "ZZB milik A"),
    ]))
    hasil = _ambil(USER_A)
    assert {i["id"] for i in hasil["items"]} == {"a1", "a2"}, \
        "aset yang BERHAK dilihat hilang karena pemotongan mendahului penyaringan"


def test_penanda_terpotong_jujur(dbx, monkeypatch):
    """`terpotong` harus mencerminkan daftar SETELAH disaring, bukan sebelum."""
    monkeypatch.setattr(rs, "_MAKS_ISI_NODE", 2)
    _jalan(_seed(dbx))
    hasil = _ambil(USER_A)
    assert len(hasil["items"]) == 2 and hasil["terpotong"] is True
    assert hasil["jumlah"] == 2


def test_tanpa_pemotongan_terpotong_false(dbx):
    _jalan(_seed(dbx))
    assert _ambil(USER_A)["terpotong"] is False


# ── Penjaga anti-divergensi ─────────────────────────────────────────────────

def test_kueri_izin_SETARA_gelung_guard_asli(dbx):
    """Membandingkan penyaring kueri dengan gelung guard YANG ASLI.

    `_filter_aset_boleh` menyalin aturan otorisasi dari `shared_utils`. Salinan
    bisa menyimpang diam-diam bila aturan aslinya berubah — dan divergensi pada
    kode otorisasi berarti kebocoran atau data yang hilang. Uji ini menjalankan
    KEDUANYA atas fixture yang sama dan menuntut hasilnya identik, sehingga
    perubahan pada `pastikan_akses_aset` yang tak diikuti di sini akan gagal
    di CI, bukan di lapangan.
    """
    from shared_utils import pastikan_akses_aset
    _jalan(_seed(dbx))

    async def lewat_gelung(user):
        semua = [r async for r in dbx.assets.find(
            {"lokasi_spasial.node_id": "r305"}, {"_id": 0})]
        lolos = []
        for r in semua:
            try:
                await pastikan_akses_aset(user, r)
            except HTTPException:
                continue
            lolos.append(r["id"])
        return set(lolos)

    for user in (USER_A, USER_SUPER):
        lewat_kueri = {i["id"] for i in _ambil(user)["items"]}
        assert lewat_kueri == _jalan(lewat_gelung(user)), (
            f"penyaring kueri menyimpang dari guard asli untuk {user['username']}")
