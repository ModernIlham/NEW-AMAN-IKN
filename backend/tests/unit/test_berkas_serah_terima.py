"""Kelengkapan berkas yang wajib diserahkan bersama barangnya.

Permintaan pemilik: *"biasanya apa saja yang diserahterimakan yang menyangkut
barang tersebut, mulai dari memiliki bukti kepemilikan dan yang tidak memiliki
bukti kepemilikan, dan sifat selain tanah dan bangunan dan yang tanah dan
bangunan, dll-nya baik yang di atas dan di bawah 100 juta dll. Juga perhatikan
agar PPK menyerahkan lengkap berkasnya saat serah terima barang, tidak hanya
pengadaannya saja."*

Berkas yang tidak ikut saat serah terima hampir tak pernah menyusul. Ia baru
dicari bertahun-tahun kemudian — saat penghapusan, pemindahtanganan, atau
pemeriksaan — ketika PPK-nya sudah berpindah dan penyedianya sudah tak
terhubung.
"""
import berkas_serah_terima as bst
from berkas_serah_terima import (
    AMBANG_NILAI_PERHATIAN, BERKAS_DASAR, catatan_ambang, kelompok_berkas,
    klasifikasi_barang,
)

KENDARAAN = {"kode": "3020101001", "uraian": "Kendaraan Dinas",
             "jumlah": 1, "harga_satuan": 350_000_000}
LAPTOP = {"kode": "3050104001", "uraian": "Laptop", "jumlah": 3,
          "harga_satuan": 15_000_000}
TANAH = {"kode": "2010101001", "uraian": "Tanah Kantor", "jumlah": 1,
         "harga_satuan": 5_000_000_000}
GEDUNG = {"kode": "4010101001", "uraian": "Gedung Arsip", "jumlah": 1,
          "harga_satuan": 900_000_000}
KERTAS = {"kode": "1010301001", "uraian": "Kertas HVS", "jumlah": 50,
          "harga_satuan": 55_000}
TANPA_KODE = {"kode": "", "uraian": "Jasa Instalasi", "jumlah": 1,
              "harga_satuan": 1_000_000}


class TestKlasifikasi:
    def test_tanah_dan_gedung_masuk_kelompok_tanah_bangunan(self):
        assert klasifikasi_barang("2010101001")["tanah_bangunan"] is True
        assert klasifikasi_barang("4010101001")["tanah_bangunan"] is True

    def test_peralatan_dan_persediaan_bukan_tanah_bangunan(self):
        assert klasifikasi_barang("3050104001")["tanah_bangunan"] is False
        assert klasifikasi_barang("1010301001")["tanah_bangunan"] is False

    def test_kendaraan_BER_bukti_kepemilikan_meski_segolongan_peralatan(self):
        """Kendaraan ada di dalam golongan yang umumnya TANPA bukti
        kepemilikan — padahal justru kendaraanlah yang paling sering hilang
        BPKB-nya, dan tanpa BPKB ia tak bisa dijual maupun dihapuskan kelak."""
        k = klasifikasi_barang("3020101001")
        assert k["bukti_kepemilikan"] is True
        assert any("BPKB" in x for x in k["berkas"])

    def test_peralatan_biasa_TIDAK_diminta_BPKB(self):
        k = klasifikasi_barang("3050104001")
        assert k["bukti_kepemilikan"] is False
        assert not any("BPKB" in x for x in k["berkas"])

    def test_ambang_nilai_dihitung_per_unit(self):
        assert klasifikasi_barang("3050104001", 99_999_999)["di_atas_ambang"] is False
        assert klasifikasi_barang("3050104001", AMBANG_NILAI_PERHATIAN)["di_atas_ambang"] is True

    def test_nilai_tak_terbaca_tidak_meledak(self):
        assert klasifikasi_barang("3050104001", "entah")["di_atas_ambang"] is False
        assert klasifikasi_barang("3050104001", None)["di_atas_ambang"] is False

    def test_tanpa_kode_TIDAK_ditebak_masuk_golongan_mana_pun(self):
        """Menebak berarti dokumen resmi menuntut berkas yang tak relevan, dan
        pembacanya berhenti mempercayai seluruh daftarnya."""
        k = klasifikasi_barang("")
        assert k["golongan"] == "" and k["berkas"] == []
        assert k["bukti_kepemilikan"] is False

    def test_semua_golongan_terdaftar_punya_nama_dan_berkas(self):
        for gol, info in bst.GOLONGAN_BERKAS.items():
            assert info["nama"].strip(), gol
            assert info["berkas"], gol


class TestKelompokBerkas:
    def test_bidang_khusus_BERDIRI_SENDIRI(self):
        """Kalau kendaraan dilebur ke golongannya, BPKB ikut menempel pada
        laptop yang kebetulan segolongan — daftar yang salah bagi keduanya."""
        hasil = kelompok_berkas([KENDARAAN, LAPTOP])
        judul = [j for j, *_ in hasil]
        assert len(hasil) == 2
        assert any("Bidang 302" in j for j in judul)
        laptop = next(h for h in hasil if "Bidang 302" not in h[0])
        assert not any("BPKB" in x for x in laptop[2])

    def test_berkas_dasar_melekat_pada_SETIAP_kelompok(self):
        """Inilah "tidak hanya pengadaannya saja" — dokumen pengadaan sudah
        tercetak di blok tersendiri; yang ini menyangkut barangnya."""
        for _, _, berkas, _, _ in kelompok_berkas([KENDARAAN, KERTAS, TANAH]):
            for dasar in BERKAS_DASAR:
                assert dasar in berkas

    def test_tanah_meminta_sertipikat_gedung_meminta_IMB(self):
        peta = {j: b for j, _, b, _, _ in kelompok_berkas([TANAH, GEDUNG])}
        tanah = next(v for k, v in peta.items() if "Golongan 2" in k)
        gedung = next(v for k, v in peta.items() if "Golongan 4" in k)
        assert any("Sertipikat" in x for x in tanah)
        assert any("IMB" in x or "PBG" in x for x in gedung)

    def test_sifat_menyebut_KEDUA_sumbu_yang_diminta_pemilik(self):
        sifat = {j: s for j, s, *_ in kelompok_berkas([TANAH, LAPTOP])}
        assert any("Tanah dan/atau bangunan" in s and "ber-bukti" in s
                   for s in sifat.values())
        assert any("Selain tanah dan bangunan" in s and "tanpa bukti" in s
                   for s in sifat.values())

    def test_perhatian_menyala_hanya_pada_kelompok_yang_memuatnya(self):
        hasil = {j: p for j, _, _, _, p in kelompok_berkas([KENDARAAN, LAPTOP])}
        assert hasil[next(j for j in hasil if "Bidang 302" in j)] is True
        assert hasil[next(j for j in hasil if "Bidang 302" not in j)] is False

    def test_nilai_dihitung_dari_total_bila_harga_satuan_kosong(self):
        """Baris LPB membawa `total`; baris pengadaan membawa `harga_satuan`.
        Keduanya harus sampai ke ambang yang sama."""
        hasil = kelompok_berkas([{"kode_barang": "3050104001", "jumlah": 2,
                                  "total": 400_000_000}])
        assert hasil[0][4] is True

    def test_barang_disebut_namanya_dan_dipangkas_bila_kebanyakan(self):
        banyak = [{**LAPTOP, "uraian": f"Laptop {i}"} for i in range(10)]
        nama = kelompok_berkas(banyak)[0][3]
        assert len(nama) == 10          # pemangkasan terjadi saat DICETAK

    def test_nama_barang_kembar_tidak_diulang(self):
        nama = kelompok_berkas([LAPTOP, LAPTOP])[0][3]
        assert nama == ["Laptop"]

    def test_tanpa_kode_dikelompokkan_TERPISAH_dan_di_akhir(self):
        hasil = kelompok_berkas([TANPA_KODE, LAPTOP])
        assert hasil[-1][0] == "Barang tanpa kode barang"
        assert hasil[-1][2] == BERKAS_DASAR

    def test_daftar_kosong_menghasilkan_kosong(self):
        assert kelompok_berkas([]) == [] and kelompok_berkas(None) == []


class TestCatatanAmbang:
    def test_muncul_hanya_bila_ada_yang_mencapainya(self):
        assert catatan_ambang([KENDARAAN])
        assert catatan_ambang([LAPTOP, KERTAS]) == ""

    def test_menyebut_angkanya_berformat_indonesia(self):
        assert "Rp100.000.000" in catatan_ambang([KENDARAAN])

    def test_TIDAK_menyatakan_akibat_hukum(self):
        """Dokumen bermeterai tak boleh memuat klaim hukum yang teks aslinya
        belum dibaca (docs/SITASI-DOKUMEN-RESMI.md — sumber primer masih
        terblokir). Catatan ini mengingatkan, bukan memutuskan."""
        t = catatan_ambang([KENDARAAN]).lower()
        for klaim in ("pengelola barang", "pmk", "peraturan", "wajib disetujui",
                      "penetapan status penggunaan"):
            assert klaim not in t, klaim
