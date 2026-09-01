"""Tanggal surat tak boleh mundur dari nomor terakhir.

Permintaan pemilik: *"pada pembuatan nomor surat, buatkan validasi langsung
pada pemilihan tanggalnya agar semua yang terkait dengan penomoran pada surat
terakhir tidak bisa memilih tanggal lebih muda, sehingga urutannya
berkelanjutan sesuai tanggal dengan nomor terakhir."*

Buku agenda menomori surat BERURUTAN, dan urutan nomor seharusnya sejalan
dengan urutan tanggal. Nomor 010 bertanggal lebih awal daripada 009 membuat
arsip mustahil ditelusuri kronologis — dan tak ada satu pun galat yang muncul
saat itu terjadi.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import pesan_tanggal_mundur, tanggal_mundur

ADMIN = {"username": "admin", "role": "admin", "kode_satker": "527001"}
FORMAT = "B-{urut}/{kode_klasifikasi}/{bulan_romawi}/{tahun}"


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for m in (rp, su):
        monkeypatch.setattr(m, "db", fake, raising=False)
        if hasattr(m, "log_audit"):
            monkeypatch.setattr(m, "log_audit", _diam, raising=False)
    return fake


async def _atur():
    return await _unwrap(rp.set_pengaturan_persuratan)(
        rp.PengaturanIn(format_nomor=FORMAT, kode_unit="OIKN",
                        kode_klasifikasi_default="PL.02",
                        peta_klasifikasi=[]), user=ADMIN)


async def _booking(tanggal, **ubah):
    return await _unwrap(rp.booking_surat_keluar)(
        rp.SuratKeluarIn(perihal="Uji", tanggal_surat=tanggal, **ubah),
        user=ADMIN)


class TestAturanMurni:
    def test_lebih_awal_itu_mundur(self):
        assert tanggal_mundur("2026-08-01", "2026-08-05") is True

    def test_tanggal_SAMA_bukan_mundur(self):
        # Beberapa surat terbit pada hari yang sama adalah keadaan normal.
        assert tanggal_mundur("2026-08-05", "2026-08-05") is False

    def test_lebih_kemudian_bukan_mundur(self):
        assert tanggal_mundur("2026-08-09", "2026-08-05") is False

    def test_yang_tak_terbaca_TIDAK_ditolak(self):
        # Aturan ini menolak yang PASTI mundur, bukan menebak data cacat.
        for a, b in (("", "2026-08-05"), ("2026-08-01", ""),
                     ("kemarin", "2026-08-05"), (None, None)):
            assert tanggal_mundur(a, b) is False, (a, b)

    def test_pesannya_menyebut_nomor_pembanding(self):
        # Tanpa itu operator tak tahu surat mana yang jadi batas.
        p = pesan_tanggal_mundur("2026-08-01", "2026-08-05", "B-9/2026")
        assert "B-9/2026" in p and "2026-08-05" in p
        assert "sisipan" in p, "jalan keluarnya tak disebut"

    def test_yang_sah_tak_berpesan(self):
        assert pesan_tanggal_mundur("2026-08-09", "2026-08-05", "B-9") == ""


class TestGerbangSaatBooking:
    def test_surat_pertama_tak_terhalang(self, dbx):
        async def skenario():
            await _atur()
            r = await _booking("2026-08-05")
            assert r["nomor"]
        _jalan(skenario())

    def test_tanggal_MUNDUR_ditolak_400(self, dbx):
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            with pytest.raises(rp.HTTPException) as e:
                await _booking("2026-08-01")
            assert e.value.status_code == 400
            assert "lebih awal" in str(e.value.detail)
        _jalan(skenario())

    def test_penolakan_tak_menghabiskan_nomor(self, dbx):
        """Gerbangnya berdiri SEBELUM counter naik; kalau tidak, percobaan
        yang ditolak tetap membakar satu nomor agenda."""
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            with pytest.raises(rp.HTTPException):
                await _booking("2026-08-01")
            r = await _booking("2026-08-06")
            assert "-002/" in r["nomor"], r["nomor"]
        _jalan(skenario())

    def test_tanggal_SAMA_tetap_boleh(self, dbx):
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            r = await _booking("2026-08-05")
            assert r["nomor"]
        _jalan(skenario())

    def test_maju_tetap_boleh(self, dbx):
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            r = await _booking("2026-08-20")
            assert r["nomor"]
        _jalan(skenario())


class TestPratinjauMembawaBatasnya:
    def test_batas_dikirim_ke_layar(self, dbx):
        """Layar memakainya sebagai `min` pemilih tanggal — tanpa itu operator
        baru tahu batasnya setelah ditolak.

        `tanggal_surat` DIKIRIM eksplisit, dan itu bukan kerapian belaka.
        Versi pertama uji ini memanggil pratinjau tanpa tanggal, sehingga
        route memakai `datetime.now()`. Deret nomor di-reset BULANAN
        (`RESET_URUT_DEFAULT = "bulanan"`), jadi selama Agustus 2026 ia lulus
        dan pada detik pertama September 2026 ia gagal — surat yang dipesan
        di periode `2026-08` tak lagi terlihat dari periode `2026-09`.
        Uji yang lulusnya bergantung pada bulan berapa CI dijalankan tidak
        menjaga apa pun; ia hanya menunda kegagalannya.
        """
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            pra = await _unwrap(rp.pratinjau_nomor)(
                tanggal_surat="2026-08-06", _user=ADMIN)
            assert pra["tanggal_minimum"] == "2026-08-05"
            assert pra["nomor_terakhir"]
        _jalan(skenario())

    def test_batas_hanya_dari_deret_periode_yang_sama(self, dbx):
        """Perilaku yang dulu menjatuhkan uji di atas, kini dijaga sengaja.

        Deret bulanan berarti tiap bulan punya nomor 001-nya sendiri —
        maka surat bulan lalu BUKAN batas bawah bulan ini. Kalau ia ikut
        jadi batas, operator akan ditolak saat menomori surat awal bulan
        yang tanggalnya lebih awal daripada surat terakhir bulan lalu.
        """
        async def skenario():
            await _atur()
            await _booking("2026-08-05")
            pra = await _unwrap(rp.pratinjau_nomor)(
                tanggal_surat="2026-09-01", _user=ADMIN)
            assert pra["tanggal_minimum"] == ""
        _jalan(skenario())

    def test_tanpa_surat_apa_pun_batasnya_kosong(self, dbx):
        async def skenario():
            await _atur()
            pra = await _unwrap(rp.pratinjau_nomor)(_user=ADMIN)
            assert pra["tanggal_minimum"] == ""
        _jalan(skenario())
