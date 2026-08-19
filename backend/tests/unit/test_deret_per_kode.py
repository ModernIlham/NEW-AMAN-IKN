"""Deret nomor boleh dipisah per kode — tapi hanya bila kodenya tercetak.

Permintaan pemilik: nomor urut punya saklar aktif/non-aktif; saat aktif, deret
berjalan sendiri-sendiri per kode keamanan ATAU per kode klasifikasi arsip
sesuai komposisi yang dipilih; dan bila komposisi memuat KEDUA kode, fitur ini
dimatikan kembali ke bawaan.

Aturan itu bukan sekadar selera, dan uji ini menjaga alasannya: deret terpisah
hanya aman bila kode pembedanya IKUT TERCETAK di nomor. Kalau tidak, dua surat
berbeda memikul nomor yang sama persis — dan nomor surat resmi yang kembar tak
bisa diperbaiki belakangan.

Konsekuensi yang ikut dijaga: dengan deret terpisah, 001 milik B dan 001 milik
T memang ada bersamaan dalam satu bulan. Lencana agenda karena itu WAJIB
menyebut kodenya juga — kalau tidak, layar mengulang persis keambiguan yang
baru saja ditutup pada perbaikan urutan agenda.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    FORMAT_NOMOR_DEFAULT, dimensi_deret, kunci_deret, label_agenda,
    terapkan_komposisi,
)

ADMIN = {"username": "admin", "role": "admin", "name": "Admin", "kode_satker": ""}


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

    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    monkeypatch.setattr(rp, "jadwalkan_sync", lambda *a, **k: None, raising=False)
    return fake


async def _atur(dbx, komposisi="keamanan", deret_per_kode=True):
    await _unwrap(rp.set_pengaturan_persuratan)(
        rp.PengaturanIn(komposisi_nomor=komposisi,
                        deret_per_kode=deret_per_kode), user=ADMIN)


async def _booking(keamanan="B", klas="", tgl="2026-08-19", perihal="Uji"):
    return await _unwrap(rp.booking_surat_keluar)(
        rp.SuratKeluarIn(perihal=perihal, kode_keamanan=keamanan,
                         kode_klasifikasi=klas, tanggal_surat=tgl),
        user=ADMIN)


class TestSyaratAman:
    """Deret terpisah hanya sah bila kodenya ada di nomor."""

    @pytest.mark.parametrize("komposisi,harap", [
        ("keamanan", "keamanan"),
        ("klasifikasi", "klasifikasi"),
        ("keduanya", ""),
        ("tanpa", ""),
    ])
    def test_dimensi_mengikuti_komposisi(self, komposisi, harap):
        assert dimensi_deret(komposisi, True) == harap

    def test_saklar_mati_berarti_satu_deret(self):
        assert dimensi_deret("keamanan", False) == ""

    def test_klasifikasi_kosong_jatuh_ke_deret_tunggal(self):
        """Memisahkan deret berdasarkan kode yang tak ada sama saja dengan
        tidak memisahkan — dan kunci counter bernama '' hanya menyamarkannya."""
        assert kunci_deret("klasifikasi", "B", "") == ""
        assert kunci_deret("klasifikasi", "B", "  ") == ""

    def test_keamanan_kosong_dianggap_biasa(self):
        assert kunci_deret("keamanan", "", "") == "B"


class TestLencanaIkutKode:
    def test_menyebut_kode_saat_deret_dipisah(self):
        s = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
             "tanggal_surat": "2026-08-19", "kode_keamanan": "T",
             "kode_klasifikasi": "PL.02"}
        assert label_agenda(s, "bulanan", "keamanan") == "K-T-001/VIII/2026"
        assert label_agenda(s, "bulanan", "klasifikasi") == "K-PL.02-001/VIII/2026"

    def test_tanpa_pemisahan_bentuknya_tak_berubah(self):
        s = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
             "tanggal_surat": "2026-08-19", "kode_keamanan": "T"}
        assert label_agenda(s, "bulanan", "") == "K-001/VIII/2026"

    def test_dua_kode_tak_lagi_berlencana_sama(self):
        dasar = {"jenis": "keluar", "no_agenda": 1, "sisipan": 0, "tahun": 2026,
                 "tanggal_surat": "2026-08-19"}
        b = label_agenda({**dasar, "kode_keamanan": "B"}, "bulanan", "keamanan")
        t = label_agenda({**dasar, "kode_keamanan": "T"}, "bulanan", "keamanan")
        assert b != t, (b, t)


class TestDeretTerpisahSungguhan:
    def test_tiap_kode_keamanan_mulai_dari_satu(self, dbx):
        async def skenario():
            await _atur(dbx, "keamanan", True)
            b1 = await _booking("B")
            b2 = await _booking("B")
            t1 = await _booking("T")
            assert (b1["no_agenda"], b2["no_agenda"]) == (1, 2)
            assert t1["no_agenda"] == 1, (
                "deret 'T' ikut melanjutkan deret 'B' — padahal 001 miliknya "
                "belum pernah terbit")
            assert b2["nomor"].startswith("B-002")
            assert t1["nomor"].startswith("T-001")
        _jalan(skenario())

    def test_nomor_yang_terbit_tidak_kembar(self, dbx):
        """Bukti keamanannya: nomor 001 muncul dua kali, tetapi STRING nomornya
        berbeda karena kodenya ikut tercetak."""
        async def skenario():
            await _atur(dbx, "keamanan", True)
            b = await _booking("B")
            t = await _booking("T")
            assert b["no_agenda"] == t["no_agenda"] == 1
            assert b["nomor"] != t["nomor"]
        _jalan(skenario())

    def test_per_klasifikasi(self, dbx):
        async def skenario():
            await _atur(dbx, "klasifikasi", True)
            a1 = await _booking(klas="PL.02")
            a2 = await _booking(klas="PL.02")
            b1 = await _booking(klas="UM.01")
            assert (a1["no_agenda"], a2["no_agenda"], b1["no_agenda"]) == (1, 2, 1)
        _jalan(skenario())

    def test_saklar_mati_tetap_satu_deret(self, dbx):
        async def skenario():
            await _atur(dbx, "keamanan", False)
            b = await _booking("B")
            t = await _booking("T")
            assert (b["no_agenda"], t["no_agenda"]) == (1, 2)
        _jalan(skenario())

    def test_lencana_hasil_booking_menyebut_kode(self, dbx):
        async def skenario():
            await _atur(dbx, "keamanan", True)
            t = await _booking("T")
            assert t["label_agenda"] == "K-T-001/VIII/2026", t["label_agenda"]
        _jalan(skenario())


class TestDipaksaMatiSaatKeduanya:
    def test_komposisi_keduanya_mematikan_saklar(self, dbx):
        """Permintaan pemilik: kembali ke bawaan. Dimatikan sendiri, bukan
        ditolak — supaya tak ada setelan tertinggal yang diam-diam
        menerbitkan nomor kembar."""
        async def skenario():
            await _atur(dbx, "keamanan", True)
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(komposisi_nomor="keduanya"), user=ADMIN)
            assert hasil["deret_per_kode"] is False
            assert hasil["dimensi_deret"] == ""
            assert hasil["deret_per_kode_boleh"] is False
        _jalan(skenario())

    def test_komposisi_tanpa_kode_juga_mematikan(self, dbx):
        async def skenario():
            await _atur(dbx, "keamanan", True)
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(komposisi_nomor="tanpa"), user=ADMIN)
            assert hasil["deret_per_kode"] is False
        _jalan(skenario())

    def test_setelah_dipaksa_mati_deret_kembali_gabungan(self, dbx):
        async def skenario():
            await _atur(dbx, "keamanan", True)
            await _booking("B")
            await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(komposisi_nomor="keduanya"), user=ADMIN)
            t = await _booking("T")
            # Deret gabungan di-seed dari nomor tertinggi periode ini (1),
            # jadi nomor berikutnya 2 — bukan 1 yang sudah terpakai.
            assert t["no_agenda"] == 2, t["no_agenda"]
        _jalan(skenario())

    def test_menyalakan_saat_komposisi_keduanya_tak_berpengaruh(self, dbx):
        async def skenario():
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(komposisi_nomor="keduanya",
                                deret_per_kode=True), user=ADMIN)
            assert hasil["deret_per_kode"] is False
        _jalan(skenario())


class TestPratinjauSelarasDenganPenerbitan:
    def test_angka_yang_ditawarkan_sama_dengan_yang_terbit(self, dbx):
        """Pratinjau yang memakai deret lain akan menawarkan angka yang bukan
        angka sebenarnya — dan operator memesan nomor berdasarkan angka itu."""
        async def skenario():
            await _atur(dbx, "keamanan", True)
            await _booking("B")
            await _booking("B")
            pra = await _unwrap(rp.pratinjau_nomor)(
                kode_keamanan="T", tanggal_surat="2026-08-19", _user=ADMIN)
            assert pra["urut_berikut"] == 1, pra
            t = await _booking("T")
            assert t["no_agenda"] == 1
        _jalan(skenario())


class TestSisipanTetapDiDeretnya:
    def test_sisipan_menempel_pada_induk_sederet(self, dbx):
        """Tanpa penyaring deret, surat 'T' bisa menyisip di belakang nomor
        milik deret 'B' — nomor hasilnya menunjuk induk yang bukan miliknya."""
        async def skenario():
            await _atur(dbx, "keamanan", True)
            await _booking("B", tgl="2026-08-01")
            await _booking("B", tgl="2026-08-02")
            await _booking("T", tgl="2026-08-03")
            sisip = await _unwrap(rp.booking_surat_keluar)(
                rp.SuratKeluarIn(perihal="Sisipan", kode_keamanan="T",
                                 tanggal_surat="2026-08-05", sisipan=True),
                user=ADMIN)
            assert sisip["no_agenda"] == 1, (
                "menempel pada nomor deret lain")
            assert sisip["sisipan"] == 1
            assert sisip["nomor"].startswith("T-001.01")
        _jalan(skenario())


class TestDeretBaruTidakMewarisiPosisiDeretLama:
    """Deret per kode adalah deret BARU — bukan lanjutan deret gabungan.

    Saat fitur dinyalakan di tengah tahun, counter gabungan yang sudah
    berjalan TIDAK boleh menjadi lantainya: kode "T" harus mulai dari 001,
    sebab 001 miliknya memang belum pernah terbit dan tak akan bentrok —
    kodenya ikut tercetak di nomor.

    Tanpa uji ini penjaganya tak terlihat: pada basis data kosong, lantai dari
    counter lama kebetulan 0, jadi mencabut penjaganya tak mengubah apa pun.
    Uji-mutasi 2026-08-19 membuktikannya — mutasi lolos hijau sampai skenario
    ini ditambahkan.
    """

    def test_counter_tahunan_lama_tidak_melantai_deret_kode(self, dbx):
        async def skenario():
            # Counter tahunan era-lama, belum dimigrasi ke bulanan.
            await dbx.counters.insert_one({"_id": "surat_keluar_2026", "seq": 7})
            await _atur(dbx, "keamanan", True)
            t = await _booking("T")
            assert t["no_agenda"] == 1, (
                f"deret 'T' mewarisi posisi deret gabungan ({t['no_agenda']}) "
                "— 001 miliknya belum pernah terbit")
        _jalan(skenario())

    def test_deret_gabungan_TETAP_mewarisi_saat_fitur_mati(self, dbx):
        """Sisi sebaliknya, dan ini yang menjaga penjaganya tetap sempit:
        tanpa fitur, lantai counter lama HARUS tetap berlaku — kalau tidak,
        nomor 1..7 yang sudah beredar terbit ulang."""
        async def skenario():
            await dbx.counters.insert_one({"_id": "surat_keluar_2026", "seq": 7})
            await _atur(dbx, "keamanan", False)
            b = await _booking("B")
            assert b["no_agenda"] == 8, b["no_agenda"]
        _jalan(skenario())


class TestKompatibilitasDeretLama:
    def test_kunci_kosong_menghasilkan_id_counter_yang_sama(self):
        """Deret yang sudah berjalan tak boleh bergeser hanya karena ada
        parameter baru."""
        assert rp._cid_agenda("keluar", "2026-08", "621001") == \
            rp._cid_agenda("keluar", "2026-08", "621001", "")
        assert ":d=" not in rp._cid_agenda("keluar", "2026-08", "621001", "")

    def test_kunci_terisi_memisahkan_id(self):
        a = rp._cid_agenda("keluar", "2026-08", "621001", "B")
        b = rp._cid_agenda("keluar", "2026-08", "621001", "T")
        assert a != b and a.endswith(":d=B")
