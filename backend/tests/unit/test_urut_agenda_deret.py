"""Buku agenda terurut & berlencana sesuai METODE DERET yang dipilih.

Laporan pemilik beserta tangkapan layarnya: daftar surat tampak tak beraturan,
dan ada DUA baris berlencana "K-001/2026".

Keduanya lahir dari satu sebab. Nomor agenda dipesan dari counter per-PERIODE
(`surat_keluar_2026-08`), jadi pada deret BULANAN `no_agenda` memang kembali ke
001 tiap awal bulan — itu benar dan sesuai setelan. Yang salah ada di dua
tempat lain:

  1. Lencana agenda hanya menampilkan TAHUN, sehingga 001 bulan Juli dan 001
     bulan Agustus tampil identik. Buku agenda kehilangan sifat paling
     mendasarnya: satu nomor menunjuk satu surat.
  2. Daftar diurutkan (tahun, no_agenda) tanpa bulan, sehingga bulan
     menyelang-nyeling: 001 bulan Agustus jatuh di bawah 008 bulan Juli.

Bulan hanya boleh ikut jadi kunci pada deret BULANAN. Pada deret tahunan nomor
agenda sudah unik sepanjang tahun, dan menyisipkan bulan justru mengacak surat
yang dibooking dengan tanggal mundur.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import label_agenda, periode_surat

USER = {"username": "op", "role": "admin", "name": "Op", "kode_satker": ""}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(rp, "cari_id_surat", _diam, raising=False)
    return fake


async def _pasang_reset(dbx, reset):
    await dbx.persuratan_settings.insert_one({"type": "global", "reset_urut": reset})


async def _seed(dbx):
    """Dua bulan berisi deret yang masing-masing mulai dari 001 — persis
    keadaan pada tangkapan layar pemilik."""
    await dbx.surat.insert_many([
        {"id": "j1", "jenis": "keluar", "no_agenda": 1, "sisipan": 0,
         "tahun": 2026, "tanggal_surat": "2026-07-20", "status": "disahkan",
         "kode_satker": "", "created_at": "2026-07-20T00:00:00+00:00"},
        {"id": "j2", "jenis": "keluar", "no_agenda": 8, "sisipan": 0,
         "tahun": 2026, "tanggal_surat": "2026-07-28", "status": "disahkan",
         "kode_satker": "", "created_at": "2026-07-28T00:00:00+00:00"},
        {"id": "a1", "jenis": "keluar", "no_agenda": 1, "sisipan": 0,
         "tahun": 2026, "tanggal_surat": "2026-08-19", "status": "dibooking",
         "kode_satker": "", "created_at": "2026-08-19T00:00:00+00:00"},
        {"id": "a2", "jenis": "keluar", "no_agenda": 2, "sisipan": 0,
         "tahun": 2026, "tanggal_surat": "2026-08-20", "status": "dibooking",
         "kode_satker": "", "created_at": "2026-08-20T00:00:00+00:00"},
    ])


class TestLencanaAgenda:
    def test_deret_bulanan_menyertakan_bulan(self):
        s = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
             "tanggal_surat": "2026-08-19"}
        assert label_agenda(s, "bulanan") == "K-001/VIII/2026"

    def test_deret_tahunan_tetap_ringkas(self):
        s = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
             "tanggal_surat": "2026-08-19"}
        assert label_agenda(s, "tahunan") == "K-001/2026"

    def test_dua_bulan_tak_lagi_berlencana_sama(self):
        juli = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
                "tanggal_surat": "2026-07-20"}
        agustus = {**juli, "tanggal_surat": "2026-08-19"}
        assert label_agenda(juli, "bulanan") != label_agenda(agustus, "bulanan")

    def test_surat_masuk_memakai_tanggal_agenda_bukan_tanggal_pengirim(self):
        """Nomor agenda surat masuk dipesan menurut tanggal PENCATATAN kita.
        Memakai tanggal surat pengirim membuat lencana menyimpang dari nomor
        yang sudah tercatat."""
        s = {"jenis": "masuk", "no_agenda": 2, "sisipan": 0, "tahun": 2026,
             "created_at": "2026-07-20T03:00:00+00:00",
             "tanggal_surat": "2026-01-05"}
        assert label_agenda(s, "bulanan") == "M-002/VII/2026"

    def test_sisipan_tetap_menempel_pada_induknya(self):
        s = {"jenis": "keluar", "no_agenda": 5, "sisipan": 1, "tahun": 2026,
             "tanggal_surat": "2026-08-19"}
        assert label_agenda(s, "bulanan") == "K-005.01/VIII/2026"

    def test_tanggal_tak_terbaca_jatuh_ke_tahun_bukan_kosong(self):
        s = {"jenis": "keluar", "no_agenda": 3, "sisipan": 0, "tahun": 2025}
        assert periode_surat(s, "bulanan") == "2025"
        assert label_agenda(s, "bulanan") == "K-003/2025"


class TestUrutanDaftar:
    def test_bulanan_terurut_per_bulan(self, dbx):
        async def skenario():
            await _pasang_reset(dbx, "bulanan")
            await _seed(dbx)
            r = await _unwrap(rp.daftar_surat)(_user=USER)
            assert [x["id"] for x in r["items"]] == ["a2", "a1", "j2", "j1"], (
                "urutan menyelang-nyeling bulan — 001 Agustus jatuh di bawah "
                "008 Juli")
        _jalan(skenario())

    def test_tahunan_terurut_nomor_agenda(self, dbx):
        """Pada deret tahunan bulan TIDAK boleh ikut jadi kunci: nomor agenda
        sudah unik sepanjang tahun."""
        async def skenario():
            await _pasang_reset(dbx, "tahunan")
            await dbx.surat.insert_many([
                {"id": "t1", "jenis": "keluar", "no_agenda": 1, "sisipan": 0,
                 "tahun": 2026, "tanggal_surat": "2026-08-01", "kode_satker": "",
                 "status": "disahkan", "created_at": "2026-08-01T00:00:00+00:00"},
                # Dibooking belakangan dengan tanggal MUNDUR — nomornya tetap
                # lebih besar, jadi ia harus berada di ATAS pada urutan agenda.
                {"id": "t2", "jenis": "keluar", "no_agenda": 2, "sisipan": 0,
                 "tahun": 2026, "tanggal_surat": "2026-07-15", "kode_satker": "",
                 "status": "disahkan", "created_at": "2026-08-05T00:00:00+00:00"},
            ])
            r = await _unwrap(rp.daftar_surat)(_user=USER)
            assert [x["id"] for x in r["items"]] == ["t2", "t1"]
        _jalan(skenario())

    def test_respons_menyebut_metode_deret(self, dbx):
        async def skenario():
            await _pasang_reset(dbx, "bulanan")
            await _seed(dbx)
            r = await _unwrap(rp.daftar_surat)(_user=USER)
            assert r["reset_urut"] == "bulanan"
        _jalan(skenario())

    def test_setiap_baris_membawa_lencana_siap_pakai(self, dbx):
        async def skenario():
            await _pasang_reset(dbx, "bulanan")
            await _seed(dbx)
            r = await _unwrap(rp.daftar_surat)(_user=USER)
            peta = {x["id"]: x["label_agenda"] for x in r["items"]}
            assert peta["j1"] == "K-001/VII/2026"
            assert peta["a1"] == "K-001/VIII/2026"
        _jalan(skenario())

    def test_kunci_urut_tidak_bocor_ke_respons(self, dbx):
        """`_periode` hanya alat bantu sort — ia tak boleh muncul di API."""
        async def skenario():
            await _pasang_reset(dbx, "bulanan")
            await _seed(dbx)
            r = await _unwrap(rp.daftar_surat)(_user=USER)
            assert all("_periode" not in x for x in r["items"])
        _jalan(skenario())

    def test_paginasi_tetap_utuh_pada_deret_bulanan(self, dbx):
        async def skenario():
            await _pasang_reset(dbx, "bulanan")
            await _seed(dbx)
            h1 = await _unwrap(rp.daftar_surat)(page=1, page_size=2, _user=USER)
            h2 = await _unwrap(rp.daftar_surat)(page=2, page_size=2, _user=USER)
            assert [x["id"] for x in h1["items"]] == ["a2", "a1"]
            assert [x["id"] for x in h2["items"]] == ["j2", "j1"]
            assert h1["total"] == 4
        _jalan(skenario())
