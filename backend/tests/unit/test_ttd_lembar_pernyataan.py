"""Surat Pernyataan Tanggung Jawab menambah tempat teken. MURNI.

Permintaan pemilik: *"pada aset pemegang, apabila disertakan surat pernyataan
tanggung jawab maka otomatis menambah +1 tempat dalam meneken dokumen tersebut
sesuai nama penandatangan."*

BAST ber-SPTJ mencetak SATU LEMBAR TERSENDIRI untuk tiap penyata. Selama
`jumlah_ttd` setiap penanda tangan selalu 1, lembar itu terbit KOSONG —
dokumen resmi yang tampak lengkap padahal belum diteken.
"""
from ttd_lembar_pernyataan import (
    jumlah_ttd_dengan_pernyataan, lembar_untuk, terapkan_lembar_pernyataan,
)

BUDI = {"nama": "Budi Santoso", "nip": "199001012015011001"}
SARI = {"nama": "Sari Wulandari", "nip": ""}


class TestLembarUntuk:
    def test_satu_lembar_atas_namanya(self):
        assert lembar_untuk(BUDI, [BUDI]) == 1

    def test_dua_lembar_atas_nama_yang_sama_dihitung_dua(self):
        """BAST operasional: penanggung jawab yang JUGA Pihak Kedua mendapat
        dua lembar. Menghitungnya satu membuat lembar keduanya terbit kosong."""
        assert lembar_untuk(BUDI, [BUDI, BUDI]) == 2

    def test_lembar_orang_lain_tak_terhitung(self):
        assert lembar_untuk(BUDI, [SARI]) == 0

    def test_tanpa_lembar_sama_sekali(self):
        assert lembar_untuk(BUDI, []) == 0
        assert lembar_untuk(BUDI, None) == 0


class TestPencocokanIdentitas:
    def test_NIP_menang_bila_KEDUANYA_punya(self):
        # Nama boleh berbeda tulisannya; NIP yang mengikat.
        assert lembar_untuk(BUDI, [{"nama": "B. Santoso",
                                    "nip": BUDI["nip"]}]) == 1

    def test_NIP_berbeda_bukan_orang_yang_sama_meski_senama(self):
        assert lembar_untuk(BUDI, [{"nama": "Budi Santoso",
                                    "nip": "888"}]) == 0

    def test_salah_satu_TANPA_nip_jatuh_ke_nama(self):
        """Cacat versi pertama modul ini: kunci tunggal "nip bila ada, jika
        tidak nama" membuat penanda tangan berNIP TAK PERNAH cocok dengan
        lembar yang hanya bernama — dan lembarnya tak menambah tempat teken.
        `daftar_penyata` memang kerap hanya membawa nama."""
        assert lembar_untuk(BUDI, [{"nama": "Budi Santoso", "nip": ""}]) == 1
        assert lembar_untuk({"nama": "Budi Santoso", "nip": ""},
                            [BUDI]) == 1

    def test_beda_kapital_dan_spasi_ganda_tetap_cocok(self):
        assert lembar_untuk(BUDI, [{"nama": "BUDI  SANTOSO", "nip": ""}]) == 1

    def test_lembar_TANPA_identitas_dilewati(self):
        # Menebak pemiliknya akan menambah tempat teken pada orang yang salah.
        assert lembar_untuk(BUDI, [{"nama": "", "nip": ""}]) == 0
        assert lembar_untuk({"nama": "", "nip": ""}, [{"nama": "", "nip": ""}]) == 0

    def test_entri_cacat_tak_melempar(self):
        assert lembar_untuk(BUDI, ["bukan dict", None, 7]) == 0
        assert lembar_untuk(None, [BUDI]) == 0


class TestJumlahTtd:
    def test_satu_untuk_dokumen_utama_plus_lembarnya(self):
        assert jumlah_ttd_dengan_pernyataan(BUDI, [BUDI]) == 2
        assert jumlah_ttd_dengan_pernyataan(BUDI, [BUDI, BUDI]) == 3

    def test_tanpa_lembar_tetap_satu(self):
        assert jumlah_ttd_dengan_pernyataan(BUDI, []) == 1


class TestTerapkan:
    def test_tiap_orang_dapat_jatahnya_sendiri(self):
        hasil = terapkan_lembar_pernyataan([BUDI, SARI], [SARI])
        assert [h["jumlah_ttd"] for h in hasil] == [1, 2]

    def test_field_lain_tak_tersentuh(self):
        hasil = terapkan_lembar_pernyataan(
            [{**BUDI, "jabatan": "PPK", "email": "a@b.c"}], [])
        assert hasil[0]["jabatan"] == "PPK" and hasil[0]["email"] == "a@b.c"

    def test_masukan_ASLI_tak_diubah(self):
        # Pemanggil memakai daftar yang sama untuk hal lain; memutasinya
        # diam-diam adalah cara paling mudah melahirkan bug jarak jauh.
        asli = [dict(BUDI)]
        terapkan_lembar_pernyataan(asli, [BUDI])
        assert "jumlah_ttd" not in asli[0]

    def test_tanpa_SPTJ_semua_tetap_satu(self):
        hasil = terapkan_lembar_pernyataan([BUDI, SARI], [])
        assert [h["jumlah_ttd"] for h in hasil] == [1, 1]

    def test_daftar_cacat_tak_melempar(self):
        assert terapkan_lembar_pernyataan(None, None) == []
        assert terapkan_lembar_pernyataan(["bukan dict"], []) == []
