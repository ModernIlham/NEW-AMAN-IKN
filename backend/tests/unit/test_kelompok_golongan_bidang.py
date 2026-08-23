"""Pengelompokan dua tingkat golongan → bidang, dan pengelompokan dokumen.

Keduanya MURNI, dan keduanya menentukan bentuk dokumen resmi: sekat yang
pecah dua kali untuk golongan yang sama, atau kelompok dokumen yang tercecer,
menghasilkan naskah yang tampak benar tetapi membingungkan pembacanya.
"""
from kodefikasi_utils import kelompokkan_per_golongan_bidang
from pengadaan_dokumen import (
    KELOMPOK_DOKUMEN, KUNCI_DOKUMEN, kelompok_dokumen, label_sifat,
)


def _b(kode, nup=""):
    return {"asset_code": kode, "NUP": nup}


class TestGolonganBidang:
    def test_bersarang_golongan_lalu_bidang(self):
        hasil = kelompokkan_per_golongan_bidang(
            [_b("3050104001"), _b("3020101001"), _b("1010301001")])
        assert [g for g, _ in hasil] == ["1", "3"]
        assert [b for b, _ in hasil[1][1]] == ["302", "305"]

    def test_golongan_sama_TIDAK_pecah_dua_sekat(self):
        """Sekat yang pecah membuat pembaca mengira ada dua golongan berbeda."""
        hasil = kelompokkan_per_golongan_bidang(
            [_b("3050104001"), _b("1010301001"), _b("3020101001"),
             _b("1010301004")])
        gol = [g for g, _ in hasil]
        assert len(gol) == len(set(gol)), gol

    def test_tanpa_kode_berkumpul_di_AKHIR_dan_dinyatakan(self):
        hasil = kelompokkan_per_golongan_bidang([_b(""), _b("3050104001")])
        assert hasil[-1][0] == ""
        assert hasil[-1][1][0][0] == ""

    def test_seluruh_aset_terbawa_tanpa_ada_yang_hilang(self):
        asal = [_b("3050104001", "2"), _b("3050104001", "1"), _b(""),
                _b("1010301001"), _b("4010101001")]
        keluar = [x for _, bs in kelompokkan_per_golongan_bidang(asal)
                  for _, isi in bs for x in isi]
        assert len(keluar) == len(asal)

    def test_bidang_selalu_berawalan_digit_golongannya(self):
        """Invarian bentuk: sekat bidang yang tak berawalan digit golongan
        induknya berarti barisnya tersarang pada kelompok yang salah."""
        for gol, bidang_list in kelompokkan_per_golongan_bidang(
                [_b("3050104001"), _b("1010301001"), _b("4010101001"), _b("")]):
            for bidang, _ in bidang_list:
                assert (bidang or "").startswith(gol)

    def test_bidang_baru_TIDAK_membuka_sekat_golongan_baru(self):
        """Yang paling mudah rusak: menyamakan "kelompok baru" dengan "bidang
        baru". Golongan 3 dengan tiga bidang akan tercetak sebagai TIGA sekat
        golongan — pembaca menyimpulkan ada tiga golongan berbeda."""
        hasil = kelompokkan_per_golongan_bidang(
            [_b("3050104001"), _b("3020101001"), _b("3060101001")])
        assert [g for g, _ in hasil] == ["3"]
        assert [b for b, _ in hasil[0][1]] == ["302", "305", "306"]

    def test_daftar_kosong_aman(self):
        assert kelompokkan_per_golongan_bidang([]) == []
        assert kelompokkan_per_golongan_bidang(None) == []


class TestKelompokDokumen:
    def test_kontrak_hanya_membawa_dokumen_yang_terisi(self):
        h = kelompok_dokumen("kontrak", {"no_sp_spk": "SPK-1", "no_spm": "SPM-2"})
        assert [j for j, _ in h] == ["Perikatan", "Pembayaran"]
        assert dict(h[0][1]) == {"No. SP/SPK": "SPK-1"}

    def test_non_kontrak_menguraikan_UP_TUP(self):
        h = dict(kelompok_dokumen("non_kontrak", {"jenis_up": "tup"})[0][1])
        assert h["UP/TUP"] == "TUP (Tambahan UP)"

    def test_kelompok_yang_kosong_TIDAK_muncul(self):
        h = kelompok_dokumen("kontrak", {"no_dokumen": "ND-1"})
        assert [j for j, _ in h] == ["Rujukan lain"]

    def test_tanpa_dokumen_sama_sekali_hasilnya_kosong(self):
        assert kelompok_dokumen("kontrak", {}) == []
        assert kelompok_dokumen("", None) == []

    def test_sifat_BUKAN_salah_satu_barisnya(self):
        """Sifat adalah judul blok; menjadikannya baris membuatnya terbaca
        sebagai nomor dokumen yang harus dicocokkan."""
        for _, isi in kelompok_dokumen("kontrak", {"no_sp_spk": "SPK-1"}):
            for lbl, _ in isi:
                assert "Sifat" not in lbl

    def test_semua_kunci_dokumen_punya_kelompok(self):
        """Kunci yang tercecer di luar kelompok TIDAK akan pernah tercetak —
        dan tak ada galat yang memberitahukannya."""
        terdaftar = [k for _, kunci in KELOMPOK_DOKUMEN for k in kunci]
        assert sorted(terdaftar) == sorted(KUNCI_DOKUMEN)

    def test_tak_ada_kunci_yang_masuk_dua_kelompok(self):
        terdaftar = [k for _, kunci in KELOMPOK_DOKUMEN for k in kunci]
        assert len(terdaftar) == len(set(terdaftar))


class TestLabelSifat:
    def test_menyebut_jalur_dokumennya(self):
        assert "SP/SPK" in label_sifat("kontrak")
        assert "UP/TUP" in label_sifat("non_kontrak")

    def test_sifat_tak_dikenal_tidak_dikarang(self):
        assert label_sifat("") == ""
        assert label_sifat("entah") == ""
