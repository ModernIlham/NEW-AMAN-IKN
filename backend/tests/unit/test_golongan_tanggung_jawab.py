"""Golongan tanggung jawab pada "Daftar Barang yang Digunakan".

Permintaan pemilik: *"bedakan dan bagi terhadap barang BMN BAST yang sudah
disahkan dan diunggah buktinya ... dibagi per jenis BAST-nya. Jika melekat ke
individu dan jabatan berarti memang menjadi tanggung jawabnya; untuk yang
operasional maka perpanjangan tangan atau jadi pendelegasian dan izin sesuai
nama-nama yang menjadi penanggung jawabnya dan ikut bertanggung jawab dalam
penjagaan barang tersebut. Dan jika dari awal digunakan untuk operasional dan
langsung menggunakan nama penandatangan maka hampir sama dengan tusinya."*

Kenapa ini penting sampai perlu dikunci uji: dokumen itu **ditandatangani
pemegang DAN KPB**. Satu daftar datar menyamakan tiga hal yang bobot hukumnya
berbeda — barang yang melekat pada orangnya, barang unit yang ia jaga sebagai
perpanjangan tangan, dan barang yang belum berdasar apa pun — sehingga orang
meneken tanggung jawab yang bukan miliknya, dan tak ada galat apa pun yang
memberitahunya.
"""
import pytest

from penggunaan_utils import (
    GOLONGAN_TJ, bast_sah, golongan_tj, kelompokkan_tanggung_jawab,
)

PEMEGANG = "Budi Santoso"


def aset(jenis=None, penerima=None, bukti="f-1", dicabut=False, **lain):
    a = {"id": lain.pop("id", "a-1"), "user": PEMEGANG, "bast_file_id": bukti}
    if jenis is not None:
        a["bast_terakhir"] = {"id": "b-1", "jenis": jenis,
                              "penerima": penerima if penerima is not None else PEMEGANG,
                              "tt_dicabut": dicabut}
    elif dicabut:
        a["bast_terakhir"] = {"id": "b-1", "tt_dicabut": True}
    a.update(lain)
    return a


class TestApaYangDianggapSah:
    """Mengunggah bukti tanda tangan ITULAH pengesahannya.

    Bukan tebakan: `unggah_bukti_bast` di routes/bast.py menyetel
    `bast_file_id` pada tiap aset objek BAST **dan** menaikkan nomor agenda
    dari "dibooking" ke "disahkan" dalam satu tindakan. Jadi `bast_file_id`
    terisi memenuhi kedua syarat pemilik sekaligus.
    """

    def test_bukti_terunggah_berarti_sah(self):
        assert bast_sah(aset("penggunaan_melekat")) is True

    def test_tanpa_bukti_tidak_sah(self):
        assert bast_sah(aset("penggunaan_melekat", bukti="")) is False
        assert bast_sah({"user": PEMEGANG}) is False

    def test_bukti_hanya_spasi_tidak_sah(self):
        assert bast_sah(aset("penggunaan_melekat", bukti="   ")) is False

    def test_tanda_tangan_yang_DICABUT_membatalkan_keabsahan(self):
        # Bukti masih ada berkasnya, tetapi tandatangannya sudah dicabut —
        # tanpa pemeriksaan ini barang itu tetap terhitung tanggung jawab.
        assert bast_sah(aset("penggunaan_melekat", dicabut=True)) is False

    def test_aset_None_tidak_meledak(self):
        assert bast_sah(None) is False


class TestPembagianPerJenis:
    def test_melekat_dan_mutasi_jadi_tanggung_jawab_pribadi(self):
        for j in ("penggunaan_melekat", "mutasi_pengguna"):
            assert golongan_tj(aset(j), PEMEGANG) == "melekat"

    def test_operasional_atas_nama_SENDIRI_setara_tusi(self):
        # "jika dari awal digunakan untuk operasional dan langsung memakai
        # nama penandatangan maka hampir sama dengan tusinya."
        a = aset("operasional_unit", penerima=PEMEGANG)
        assert golongan_tj(a, PEMEGANG) == "tusi"

    def test_operasional_atas_nama_ORANG_LAIN_adalah_pendelegasian(self):
        a = aset("operasional_unit", penerima="Sari Dewi")
        assert golongan_tj(a, PEMEGANG) == "delegasi"

    def test_pembandingan_nama_tahan_spasi_dan_huruf_besar(self):
        # "budi  santoso" dan "Budi Santoso" orang yang sama; kalau tidak,
        # barang tusi salah tergolong jadi pendelegasian.
        a = aset("operasional_unit", penerima="  budi   SANTOSO ")
        assert golongan_tj(a, PEMEGANG) == "tusi"

    def test_penerima_kosong_jatuh_ke_pendelegasian_bukan_tusi(self):
        # Konservatif: tanpa nama penerima kita TIDAK boleh menyimpulkan
        # bahwa ia meneken untuk dirinya sendiri.
        a = aset("operasional_unit", penerima="")
        assert golongan_tj(a, PEMEGANG) == "delegasi"

    def test_penggunaan_sementara_berdiri_sendiri(self):
        assert golongan_tj(aset("penggunaan_sementara"), PEMEGANG) == "sementara"

    def test_jenis_asing_masuk_golongan_lain_bukan_melekat(self):
        # Jenis baru yang belum dikenal TIDAK boleh diam-diam dihitung
        # sebagai tanggung jawab pribadi.
        assert golongan_tj(aset("jenis_yang_belum_ada"), PEMEGANG) == "lain"
        assert golongan_tj(aset("pengembalian"), PEMEGANG) == "lain"

    def test_tanpa_bast_sah_mendahului_jenis_apa_pun(self):
        # Jenisnya "melekat" tetapi buktinya belum ada → belum bisa
        # dibebankan, apa pun jenisnya.
        assert golongan_tj(aset("penggunaan_melekat", bukti=""), PEMEGANG) == "tanpa_bast"
        assert golongan_tj(aset("penggunaan_melekat", dicabut=True), PEMEGANG) == "tanpa_bast"


class TestPengelompokan:
    def test_hanya_golongan_BERISI_yang_dikembalikan(self):
        hasil = kelompokkan_tanggung_jawab(
            [aset("penggunaan_melekat", id="a"), aset("penggunaan_melekat", id="b")],
            PEMEGANG)
        assert [k for k, *_ in hasil] == ["melekat"]

    def test_urutan_golongan_mengikuti_bobot_tanggung_jawabnya(self):
        semua = [
            aset("penggunaan_melekat", id="1"),
            aset("operasional_unit", penerima="Sari Dewi", id="2"),
            aset("operasional_unit", penerima=PEMEGANG, id="3"),
            aset("penggunaan_sementara", id="4"),
            aset("pengembalian", id="5"),
            aset(None, bukti="", id="6"),
        ]
        # Sengaja diacak masuknya; urutan keluarnya harus tetap menurut
        # GOLONGAN_TJ, dari yang paling mengikat ke yang belum mengikat.
        kunci = [k for k, *_ in kelompokkan_tanggung_jawab(semua, PEMEGANG)]
        assert kunci == ["melekat", "tusi", "delegasi", "sementara",
                         "lain", "tanpa_bast"]

    def test_tiap_aset_masuk_TEPAT_satu_golongan(self):
        semua = [aset("penggunaan_melekat", id=str(i)) for i in range(3)]
        semua += [aset("operasional_unit", penerima="X", id="x")]
        semua += [aset(None, bukti="", id="k")]
        hasil = kelompokkan_tanggung_jawab(semua, PEMEGANG)
        jumlah = sum(len(isi) for *_r, isi in hasil)
        assert jumlah == len(semua)
        ids = [a["id"] for *_r, isi in hasil for a in isi]
        assert sorted(ids) == sorted(a["id"] for a in semua)

    def test_urutan_di_DALAM_golongan_dipertahankan(self):
        # Pemanggil sudah mengurutkannya per bidang kode barang selaras BAST
        # induk; pengelompokan tak boleh mengacaknya.
        semua = [aset("penggunaan_melekat", id=str(i)) for i in range(5)]
        (_k, _j, _t, isi), = kelompokkan_tanggung_jawab(semua, PEMEGANG)
        assert [a["id"] for a in isi] == ["0", "1", "2", "3", "4"]

    def test_daftar_kosong_menghasilkan_kosong(self):
        assert kelompokkan_tanggung_jawab([], PEMEGANG) == []
        assert kelompokkan_tanggung_jawab(None, PEMEGANG) == []


class TestKeteranganTiapGolongan:
    """Judul dan keterangan ikut tercetak di PDF — ia yang menerangkan
    kepada penanda tangan APA yang sedang ia teken."""

    @pytest.mark.parametrize("kunci,judul,ket", GOLONGAN_TJ)
    def test_setiap_golongan_punya_judul_dan_keterangan(self, kunci, judul, ket):
        assert judul.strip() and len(ket.strip()) > 40, kunci

    def test_golongan_pendelegasian_menyebut_ikut_bertanggung_jawab(self):
        ket = dict((k, t) for k, _j, t in GOLONGAN_TJ)["delegasi"]
        # Justru inilah inti permintaan pemilik: perpanjangan tangan TETAP
        # ikut bertanggung jawab menjaga, meski tanpa penguasaan pribadi.
        assert "ikut" in ket.lower() and "tanggung jawab" in ket.lower()

    def test_golongan_tanpa_bast_menyatakan_BELUM_dapat_dibebankan(self):
        ket = dict((k, t) for k, _j, t in GOLONGAN_TJ)["tanpa_bast"]
        assert "belum" in ket.lower()
