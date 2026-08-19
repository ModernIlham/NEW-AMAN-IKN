"""Kode klasifikasi arsip benar-benar bisa masuk ke nomor surat.

Keluhan pemilik: "pada Format Nomor, Kode Klasifikasi Arsip masih belum masuk
ke dalam surat" — dan "biasanya mau pakai kode keamanan atau kode klasifikasi
arsip (atau bisa keduanya)".

Rantainya sebenarnya sudah tersambung: `pilih_klasifikasi` → `bangun_nomor` di
SEMUA jalur penerbitan nomor. Yang membuatnya tampak mati ada dua:

  1. Nomor hanya memuat kode klasifikasi bila templatenya memuat
     `{kode_klasifikasi}` — dan mengubah template berarti mengetik placeholder
     dengan benar; satu kurung salah, kodenya diam-diam tak pernah muncul.
  2. Kode di KATALOG tak menyentuh nomor apa pun sampai ia dipasang sebagai
     aturan otomatis atau kode bawaan. Layar tak pernah mengatakan itu, jadi
     nomor terbit tanpa kode klasifikasi tanpa satu pun galat.

Uji ini menjaga jalan keluar untuk keduanya: komposisi nomor yang bisa dipilih,
dan peringatan saat nomor MEMINTA kode yang tak akan pernah terisi.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp
from persuratan_utils import (
    FORMAT_NOMOR_DEFAULT, KOMPOSISI_NOMOR, bangun_nomor, komposisi_format,
    peringatan_klasifikasi, terapkan_komposisi,
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
    return fake


class TestMembacaKomposisi:
    def test_format_bawaan_memuat_keduanya(self):
        assert komposisi_format(FORMAT_NOMOR_DEFAULT) == "keamanan_klasifikasi"

    @pytest.mark.parametrize("template,harap", [
        ("{kode_keamanan}-{urut}/{tahun}", "keamanan_saja"),
        ("{urut}/{kode_klasifikasi}/{tahun}", "klasifikasi_saja"),
        ("{urut}/{kode_unit}/{tahun}", "tanpa"),
    ])
    def test_dibaca_dari_template_bukan_disimpan_terpisah(self, template, harap):
        assert komposisi_format(template) == harap


class TestMenerapkanKomposisi:
    @pytest.mark.parametrize("pilih", sorted(KOMPOSISI_NOMOR))
    def test_hasilnya_terbaca_kembali_sebagai_pilihan_itu(self, pilih):
        assert komposisi_format(terapkan_komposisi(FORMAT_NOMOR_DEFAULT, pilih)) == pilih

    def test_bagian_lain_template_tidak_disentuh(self):
        """Kode unit & pemisah khas satker sudah dipakai bertahun — mengubah
        komposisi tak boleh membuangnya."""
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_saja")
        for bagian in ("{urut}", "{kode_unit}", "{bulan_romawi}", "{tahun}"):
            assert bagian in t, t

    def test_bolak_balik_kembali_utuh(self):
        tanpa = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "tanpa")
        assert terapkan_komposisi(tanpa, "keamanan_klasifikasi") == FORMAT_NOMOR_DEFAULT

    def test_tak_meninggalkan_pemisah_menggantung(self):
        for pilih in KOMPOSISI_NOMOR:
            t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, pilih)
            assert "//" not in t and not t.startswith(("-", "/")) and not t.endswith(("-", "/")), t

    def test_urut_wajib_ada_kalau_tidak_dikembalikan_apa_adanya(self):
        """Template tanpa {urut} tak sah dan sudah ditolak route. Menyisipkan
        sesuatu ke dalamnya hanya menyamarkan kesalahan yang harus terlihat."""
        rusak = "{kode_unit}/{tahun}"
        assert terapkan_komposisi(rusak, "keduanya") == rusak

    def test_pilihan_asing_tidak_mengubah_apa_pun(self):
        assert terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "entah") == FORMAT_NOMOR_DEFAULT

    def test_nomor_jadi_yang_benar_benar_berubah(self):
        """Bukti akhirnya ada pada nomor yang terbit, bukan pada templatenya."""
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_saja")
        nomor = bangun_nomor(t, 1, "2026-08-19", kode_klasifikasi="PL.02",
                             kode_unit="OIKN", kode_keamanan="B")
        assert nomor == "001/PL.02/OIKN/VIII/2026", nomor
        assert not nomor.startswith("B-"), "kode keamanan masih ikut"

    def test_keamanan_saja_menghapus_klasifikasi_dari_nomor(self):
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "keamanan_saja")
        nomor = bangun_nomor(t, 1, "2026-08-19", kode_klasifikasi="PL.02",
                             kode_unit="OIKN", kode_keamanan="B")
        assert nomor == "B-001/OIKN/VIII/2026", nomor


class TestKlasifikasiDiDepan:
    """Maksud sesungguhnya Komposisi Nomor, menurut pemilik: apakah kode
    klasifikasi arsip IKUT, dan apakah ia MENGGANTIKAN POSISI kode keamanan
    yang berada di depan nomor.

    Bentuk lama hanya bisa menaruh klasifikasi SETELAH nomor urut
    (001/PL.02/…), sehingga satker yang menomori surat dengan klasifikasi di
    depan (PL.02-001/…) tak punya cara menyatakannya selain mengetik template
    ber-placeholder dengan benar.
    """

    def test_menempati_posisi_depan(self):
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_depan")
        assert t.startswith("{kode_klasifikasi}-{urut}"), t
        assert "{kode_keamanan}" not in t

    def test_nomor_yang_terbit_berbentuk_klasifikasi_di_depan(self):
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_depan")
        nomor = bangun_nomor(t, 1, "2026-08-19", kode_klasifikasi="PL.02",
                             kode_unit="OIKN", kode_keamanan="B")
        assert nomor == "PL.02-001/OIKN/VIII/2026", nomor

    def test_berpindah_dari_belakang_ke_depan_tanpa_menyisakan_salinan(self):
        """Perpindahan posisi paling gampang meninggalkan placeholder kembar —
        dan nomor yang terbit akan memuat kode klasifikasi DUA KALI."""
        belakang = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_saja")
        depan = terapkan_komposisi(belakang, "klasifikasi_depan")
        assert depan.count("{kode_klasifikasi}") == 1, depan
        assert depan.startswith("{kode_klasifikasi}-{urut}"), depan

    def test_kembali_ke_bentuk_baku_utuh(self):
        depan = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "klasifikasi_depan")
        assert terapkan_komposisi(depan, "keamanan_klasifikasi") == FORMAT_NOMOR_DEFAULT

    def test_unsur_lain_tetap_di_tempatnya(self):
        """Unsur tulisan milik satker tak boleh ikut tergeser saat posisi
        klasifikasi berubah."""
        khas = "{kode_keamanan}-{urut}/{kode_klasifikasi}/SETJEN/{kode_unit}/{bulan_romawi}/{tahun}"
        t = terapkan_komposisi(khas, "klasifikasi_depan")
        assert "/SETJEN/" in t, t
        assert "{kode_unit}" in t and "{bulan_romawi}" in t and "{tahun}" in t

    def test_contoh_tersedia_untuk_tiap_pilihan(self):
        """Layar menampilkan CONTOH tiap komposisi — pilihan terbaca dari
        bentuknya, bukan dari namanya."""
        from persuratan_utils import CONTOH_KOMPOSISI
        assert set(CONTOH_KOMPOSISI) == set(KOMPOSISI_NOMOR)
        assert CONTOH_KOMPOSISI["klasifikasi_depan"].startswith("PL.02-001")


class TestPeringatanKodeMenganggur:
    def test_diperingatkan_saat_nomor_meminta_kode_yang_tak_akan_terisi(self):
        pesan = peringatan_klasifikasi(FORMAT_NOMOR_DEFAULT, "", [])
        assert "TANPA kode" in pesan

    def test_diam_saat_ada_kode_bawaan(self):
        assert peringatan_klasifikasi(FORMAT_NOMOR_DEFAULT, "UM.01", []) == ""

    def test_diam_saat_ada_aturan_berkode(self):
        peta = [{"modul": "pengadaan", "jenis_naskah": "", "kode": "PL.02"}]
        assert peringatan_klasifikasi(FORMAT_NOMOR_DEFAULT, "", peta) == ""

    def test_aturan_tanpa_kode_tidak_dihitung(self):
        """Baris aturan yang kodenya belum diisi tak menerbitkan apa pun —
        menganggapnya cukup akan menyembunyikan keadaan yang justru dikeluhkan."""
        peta = [{"modul": "pengadaan", "jenis_naskah": "", "kode": "  "}]
        assert peringatan_klasifikasi(FORMAT_NOMOR_DEFAULT, "", peta) != ""

    def test_diam_saat_nomor_memang_tak_meminta_klasifikasi(self):
        t = terapkan_komposisi(FORMAT_NOMOR_DEFAULT, "keamanan_saja")
        assert peringatan_klasifikasi(t, "", []) == ""


class TestEndpointPengaturan:
    def test_menyimpan_komposisi_menulis_ulang_format(self, dbx):
        async def skenario():
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(komposisi_nomor="klasifikasi_saja"), user=ADMIN)
            assert "{kode_keamanan}" not in hasil["format_nomor"]
            assert "{kode_klasifikasi}" in hasil["format_nomor"]
            assert hasil["komposisi_nomor"] == "klasifikasi_saja"
            tersimpan = await dbx.persuratan_settings.find_one({"type": "global"})
            assert "komposisi_nomor" not in tersimpan, (
                "komposisi ikut tersimpan sebagai field — ia harus hanya "
                "menulis ulang format_nomor, bukan jadi sumber kebenaran kedua")
        _jalan(skenario())

    def test_komposisi_asing_ditolak(self, dbx):
        async def skenario():
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.set_pengaturan_persuratan)(
                    rp.PengaturanIn(komposisi_nomor="entah"), user=ADMIN)
            assert e.value.status_code == 400
        _jalan(skenario())

    def test_komposisi_diterapkan_di_atas_format_yang_dikirim(self, dbx):
        """Mengirim keduanya sekaligus harus deterministik: komposisi menang,
        di atas format yang DIKIRIM — bukan di atas format lama.

        Templatenya memuat {bulan_romawi} bukan sebagai hiasan: deret bulanan
        mewajibkan unsur bulan, kalau tidak nomor yang sama terbit ulang tiap
        bulan. Penjaga itu harus tetap berlaku setelah komposisi menulis ulang
        format — komposisi tak boleh jadi pintu belakang yang melewatinya.
        """
        async def skenario():
            hasil = await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(format_nomor="{urut}/{kode_unit}/{bulan_romawi}/{tahun}",
                                komposisi_nomor="keamanan_saja"), user=ADMIN)
            assert hasil["format_nomor"] == (
                "{kode_keamanan}-{urut}/{kode_unit}/{bulan_romawi}/{tahun}")
        _jalan(skenario())

    def test_komposisi_bukan_pintu_belakang_penjaga_deret(self, dbx):
        """Format tanpa unsur bulan tetap ditolak walau dikirim bersama
        komposisi — penjaga anti-nomor-kembar tak boleh bisa dilangkahi."""
        async def skenario():
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as e:
                await _unwrap(rp.set_pengaturan_persuratan)(
                    rp.PengaturanIn(format_nomor="{urut}/{kode_unit}/{tahun}",
                                    komposisi_nomor="keamanan_klasifikasi"), user=ADMIN)
            assert e.value.status_code == 400
            assert "bulan" in str(e.value.detail)
        _jalan(skenario())

    def test_respons_membawa_peringatan_dan_pilihan(self, dbx):
        async def skenario():
            hasil = await _unwrap(rp.get_pengaturan_persuratan)(_user=ADMIN)
            assert hasil["peringatan_klasifikasi"], (
                "belum ada aturan/kode bawaan, tapi tak diperingatkan")
            assert set(hasil["pilihan_komposisi"]) == set(KOMPOSISI_NOMOR)
        _jalan(skenario())

    def test_kode_bawaan_mematikan_peringatan(self, dbx):
        async def skenario():
            await _unwrap(rp.set_pengaturan_persuratan)(
                rp.PengaturanIn(kode_klasifikasi_default="UM.01"), user=ADMIN)
            hasil = await _unwrap(rp.get_pengaturan_persuratan)(_user=ADMIN)
            assert hasil["peringatan_klasifikasi"] == ""
        _jalan(skenario())
