"""Perkiraan nomor booking bisa DISUNTING — "ibaratnya menulis nomer manual".

Permintaan pemilik: *"maksud menyisipkan atau menambahkan unsur baru yang
terserah letaknya itu adalah dibagian ini, jadi setiap contoh booking perkiraan
nomornya bisa diedit dan di tambahkan unsur baru sesuai keinginan. ibaratnya
menulis nomer manual kurang lebihnya jadinya seperti dimodifikasi."*

Yang disunting HANYA tulisannya. Nomor agenda tetap dikunci counter atomik
seperti biasa — dan itu invarian terpenting berkas ini. Membiarkan tulisan
tangan menggeser deret akan melahirkan nomor kembar pada surat BERIKUTNYA, dan
kembarnya baru ketahuan setelah dua-duanya resmi terbit.

Satu keputusan rancangan yang perlu diuji sendiri: nomor tulisan tangan yang
PERSIS SAMA dengan perkiraan dianggap "tidak disunting". Layar mengirim isi
kotaknya apa adanya, jadi operator yang membuka penyuntingan lalu tak mengubah
apa pun tetap mengirim teks. Teks itu bisa sudah basi — deretnya bergeser bila
ada booking lain menyela sedetik sebelumnya. Menyimpannya sebagai tulisan
tangan berarti membekukan nomor basi menjadi nomor resmi.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    MAKS_PANJANG_NOMOR, bersihkan_nomor_manual, validate_nomor_manual,
)

# Admin BER-SATKER. Registrasi persuratan kini menolak pemanggil tanpa
# satker (lihat satker_wajib.py): surat berstempel "" tampil di register
# SETIAP satker sekaligus menghabiskan nomor agenda mereka.
ADMIN = {"username": "admin", "role": "admin", "name": "Admin",
         "kode_satker": "527001"}


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
    return fake


async def _atur(**kw):
    dasar = dict(format_nomor="{kode_keamanan}-{urut}/{kode_unit}/"
                              "{bulan_romawi}/{tahun}", kode_unit="OIKN")
    dasar.update(kw)
    return await _unwrap(rp.set_pengaturan_persuratan)(
        rp.PengaturanIn(**dasar), user=ADMIN)


async def _booking(**kw):
    kw.setdefault("perihal", "Uji nomor manual")
    kw.setdefault("tanggal_surat", "2026-08-19")
    return await _unwrap(rp.booking_surat_keluar)(
        rp.SuratKeluarIn(**kw), user=ADMIN)


class TestPembersihan:
    def test_spasi_tepi_dan_beruntun_diratakan(self):
        assert bersihkan_nomor_manual("  B-003 /  OIKN  ") == "B-003 / OIKN"

    def test_baris_baru_tak_pernah_lolos(self):
        """Nomor bermuatan baris baru memecah kop surat, CSV, dan judul PDF —
        tiga tempat yang kerusakannya baru terlihat setelah dokumennya jadi."""
        assert "\n" not in bersihkan_nomor_manual("B-003\n/OIKN")
        assert bersihkan_nomor_manual("B-003\n/OIKN") == "B-003 /OIKN"

    def test_kosong_tetap_kosong(self):
        assert bersihkan_nomor_manual(None) == ""
        assert bersihkan_nomor_manual("   ") == ""


class TestValidasi:
    def test_kosong_bukan_kesalahan(self):
        """Kosong berarti "tak disunting", bukan "salah isi"."""
        assert validate_nomor_manual("") == []
        assert validate_nomor_manual(None) == []

    def test_bentuk_bebas_diterima(self):
        # Nomor naskah dinas berbeda-beda antarinstansi; menolak bentuk yang
        # tak kita duga mengembalikan kekakuan yang justru sedang dilepas.
        for n in ["B-003/OIKN/VIII/2026", "003.a/UND/SETJEN/2026",
                  "PL.02-003 OIKN VIII 2026", "B-003/OIKN/VIII/2026-REV1"]:
            assert validate_nomor_manual(n) == [], n

    def test_kurung_kurawal_ditolak(self):
        pesan = validate_nomor_manual("B-{urut}/OIKN")
        assert len(pesan) == 1 and "placeholder" in pesan[0]

    def test_terlalu_panjang_ditolak(self):
        assert validate_nomor_manual("A" * (MAKS_PANJANG_NOMOR + 1)) != []
        assert validate_nomor_manual("A" * MAKS_PANJANG_NOMOR) == []


class TestBookingMemakaiTulisanTangan:
    def test_nomor_tersimpan_apa_adanya(self, dbx):
        async def skenario():
            await _atur()
            hasil = await _booking(nomor_manual="B-003/UND/SETJEN/VIII/2026")
            assert hasil["nomor"] == "B-003/UND/SETJEN/VIII/2026"
            assert hasil["nomor_disunting"] is True
        _jalan(skenario())

    def test_nomor_otomatis_tetap_tersimpan_sebagai_pembanding(self, dbx):
        """Tanpa pembanding, nomor tulisan tangan tak terbedakan dari nomor
        terbitan sistem — dan pemeriksa yang bertanya "kenapa nomor ini
        menyimpang" tak punya apa pun untuk dibandingkan."""
        async def skenario():
            await _atur()
            hasil = await _booking(nomor_manual="B-003/UND/SETJEN/VIII/2026")
            assert hasil["nomor_otomatis"] == "B-001/OIKN/VIII/2026"
            assert hasil["nomor"] != hasil["nomor_otomatis"]
        _jalan(skenario())

    def test_riwayat_menyebut_penyuntingannya(self, dbx):
        async def skenario():
            await _atur()
            hasil = await _booking(nomor_manual="B-999/KHUSUS")
            catatan = hasil["riwayat"][0]["catatan"]
            assert "manual" in catatan and "B-001/OIKN/VIII/2026" in catatan
        _jalan(skenario())

    def test_tanpa_suntingan_tetap_nomor_otomatis(self, dbx):
        async def skenario():
            await _atur()
            hasil = await _booking()
            assert hasil["nomor"] == "B-001/OIKN/VIII/2026"
            assert hasil["nomor_disunting"] is False
            assert hasil["riwayat"][0]["catatan"] == ""
        _jalan(skenario())

    def test_teks_yang_SAMA_dianggap_tak_disunting(self, dbx):
        """Operator yang membuka kotaknya lalu tak mengubah apa pun tetap
        mengirim teks. Menandainya "tulisan tangan" akan membekukan nomor
        perkiraan yang bisa sudah basi menjadi nomor resmi."""
        async def skenario():
            await _atur()
            hasil = await _booking(nomor_manual="B-001/OIKN/VIII/2026")
            assert hasil["nomor_disunting"] is False
            assert hasil["riwayat"][0]["catatan"] == ""
        _jalan(skenario())

    def test_spasi_tepi_tak_membuatnya_terhitung_suntingan(self, dbx):
        async def skenario():
            await _atur()
            hasil = await _booking(nomor_manual="  B-001/OIKN/VIII/2026  ")
            assert hasil["nomor_disunting"] is False
        _jalan(skenario())


class TestDeretAgendaTakTerganggu:
    def test_nomor_urut_tetap_maju_meski_ditulis_tangan(self, dbx):
        """Invarian terpenting: tulisan tangan mengubah TULISANNYA, bukan
        deretnya. Kalau deret ikut tersandera, surat berikutnya terbit dengan
        nomor kembar — dan kembarnya baru ketahuan setelah dua-duanya resmi."""
        async def skenario():
            await _atur()
            a = await _booking(nomor_manual="NOMOR-TANGAN-SEMBARANG")
            b = await _booking()
            assert a["no_agenda"] == 1
            assert b["no_agenda"] == 2
            assert b["nomor"] == "B-002/OIKN/VIII/2026"
        _jalan(skenario())

    def test_nomor_sisipan_tetap_bisa_ditulis_tangan(self, dbx):
        async def skenario():
            await _atur()
            await _booking()
            hasil = await _booking(sisipan=True, nomor_manual="B-001.01/KHUSUS")
            assert hasil["nomor"] == "B-001.01/KHUSUS"
            assert hasil["sisipan"] == 1
            catatan = hasil["riwayat"][0]["catatan"]
            assert "sisipan" in catatan and "manual" in catatan
        _jalan(skenario())


class TestNomorResmiTakBolehKembar:
    def test_menolak_nomor_yang_sudah_dipakai(self, dbx):
        async def skenario():
            await _atur()
            await _booking()          # B-001/OIKN/VIII/2026
            with pytest.raises(rp.HTTPException) as e:
                await _booking(nomor_manual="B-001/OIKN/VIII/2026",
                               perihal="Surat kedua")
            assert e.value.status_code == 400
            assert "kembar" in e.value.detail
        _jalan(skenario())

    def test_penolakan_bentrok_terjadi_SEBELUM_surat_tersimpan(self, dbx):
        async def skenario():
            await _atur()
            await _booking()
            with pytest.raises(rp.HTTPException):
                await _booking(nomor_manual="B-001/OIKN/VIII/2026",
                               perihal="Surat kedua")
            assert await dbx.surat.count_documents({}) == 1
        _jalan(skenario())

    def test_kurung_kurawal_ditolak_di_endpoint(self, dbx):
        async def skenario():
            await _atur()
            with pytest.raises(rp.HTTPException) as e:
                await _booking(nomor_manual="B-{urut}/OIKN")
            assert e.value.status_code == 400
            assert await dbx.surat.count_documents({}) == 0
        _jalan(skenario())
