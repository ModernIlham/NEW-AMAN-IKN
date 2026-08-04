"""Uji pustaka PASAL BAST (murni) — pemilihan pasal khusus per BIDANG kode
barang dan pasal konteks waktu/risiko.

Yang dijaga di sini adalah hal-hal yang gagal SENYAP kalau meleset: pasal
kendaraan menempel pada laptop (aturan yang salah tercetak pada dokumen
resmi), pasal khusus hilang karena kode barang berbeda panjang, atau daftar
pasal berubah urutan antar unduhan sehingga dua salinan dokumen yang sama
tidak identik.
"""
from bast_pasal import (
    JENIS_PENGUASAAN, PASAL_BIDANG, bidang_kode, nama_bidang_terpakai,
    pasal_khusus_bidang, pasal_khusus_ringkas, pasal_risiko,
    pasal_waktu_penggunaan,
)

MOBIL = "3020104001"      # Alat Angkutan
LAPTOP = "3100102003"     # Komputer
MEJA = "3050101001"       # Alat Kantor dan Rumah Tangga
SAPI = "6030101001"       # Hewan
TANAH = "2010101001"      # Tanah


def test_bidang_kode_tiga_digit():
    assert bidang_kode(MOBIL) == "302"
    assert bidang_kode("3.02.01.04.001") == "302"   # bertitik ikut terbaca
    assert bidang_kode("30") == "30"                 # kode pendek apa adanya
    assert bidang_kode("") == "" and bidang_kode(None) == ""


def test_pasal_kendaraan_hanya_untuk_kendaraan():
    """Aturan SIM/pajak/pool kendaraan tidak boleh menempel pada laptop."""
    judul_mobil = [j for j, _ in pasal_khusus_bidang([MOBIL])]
    judul_laptop = [j for j, _ in pasal_khusus_bidang([LAPTOP])]
    assert judul_mobil == ["KETENTUAN KHUSUS KENDARAAN DINAS"]
    assert judul_laptop == ["KETENTUAN KHUSUS KOMPUTER DAN PERANGKAT KERJA"]
    assert "KENDARAAN" not in " ".join(judul_laptop)


def test_bidang_mengalahkan_golongan():
    """Prefix TERPANJANG menang: 302 (Alat Angkutan) bukan 3 (Peralatan dan
    Mesin) — kalau terbalik, semua barang golongan 3 dapat pasal generik."""
    (judul, _butir), = pasal_khusus_bidang([MOBIL])
    assert judul == "KETENTUAN KHUSUS KENDARAAN DINAS"
    # bidang yang belum punya aturan sendiri turun ke golongan
    (judul_lain, _), = pasal_khusus_bidang(["3990101001"])
    assert judul_lain == "KETENTUAN KHUSUS PERALATAN DAN MESIN"


def test_gabungan_unik_dan_terurut():
    """Banyak aset satu bidang → satu blok; urutan deterministik menurut kode
    bidang, supaya dua unduhan dokumen yang sama identik."""
    kode = [LAPTOP, MOBIL, LAPTOP, MEJA, MOBIL]
    judul = [j for j, _ in pasal_khusus_bidang(kode)]
    assert judul == [
        "KETENTUAN KHUSUS KENDARAAN DINAS",            # 302
        "KETENTUAN KHUSUS ALAT KANTOR DAN RUMAH TANGGA",  # 305
        "KETENTUAN KHUSUS KOMPUTER DAN PERANGKAT KERJA",  # 310
    ]
    assert judul == [j for j, _ in pasal_khusus_bidang(list(reversed(kode)))]


def test_pemotongan_dilaporkan_bukan_disembunyikan():
    kode = [TANAH, "3010101001", MOBIL, MEJA, "3060101001", "3070101001",
            LAPTOP]
    dipakai, sisa = pasal_khusus_ringkas(kode, maks=5)
    assert dipakai == 5 and sisa == 2
    assert len(pasal_khusus_bidang(kode, maks=5)) == 5
    # nama bidang yang TIDAK tercetak masih bisa disebut pada naskah
    assert nama_bidang_terpakai(kode)[dipakai:] == ["Alat Kedokteran dan "
                                                    "Kesehatan", "Komputer"]


def test_hewan_diikat_perawatan_hari_libur():
    """Kebalikan kendaraan: hewan/tanaman justru WAJIB dirawat pada hari
    libur — pembeda inti mandat 'antisipasi hari libur'."""
    (_judul, butir), = pasal_khusus_bidang([SAPI])
    assert any("hari libur" in t.lower() for t in butir)


def test_kendaraan_membatasi_luar_jam_kerja():
    (_judul, butir), = pasal_khusus_bidang([MOBIL])
    teks = " ".join(butir).lower()
    assert "di luar jam kerja" in teks and "hari libur" in teks
    assert "surat tugas" in teks or "izin tertulis" in teks
    assert "pribadi" in teks          # larangan pemakaian pribadi


def test_komputer_membolehkan_dibawa_dengan_syarat():
    """Laptop justru DIIZINKAN dibawa keluar/di luar jam kerja untuk dinas —
    aturan yang berbeda arah dengan kendaraan, itulah gunanya per bidang."""
    (_judul, butir), = pasal_khusus_bidang([LAPTOP])
    teks = " ".join(butir).lower()
    assert "di luar kantor" in teks and "di luar jam kerja" in teks
    assert "kata sandi" in teks or "pin" in teks


def test_pasal_waktu_dan_risiko_hanya_saat_penguasaan_beralih():
    for jenis in JENIS_PENGUASAAN:
        assert pasal_waktu_penggunaan(jenis) is not None
        assert pasal_risiko(jenis) is not None
    # Pengembalian: barang kembali ke satker — kewajiban penggunaan tak lagi
    # dibebankan kepada mantan pemegang.
    for jenis in ("pengembalian", "pengembalian_almarhum"):
        assert pasal_waktu_penggunaan(jenis) is None
        assert pasal_risiko(jenis) is None


def test_pasal_waktu_meliputi_semua_konteks_mandat():
    _judul, butir = pasal_waktu_penggunaan("penggunaan_melekat")
    teks = " ".join(butir).lower()
    for kata in ("jam kerja", "hari libur", "lembur", "perjalanan dinas",
                 "surat tugas"):
        assert kata in teks, f"konteks '{kata}' tidak tercakup pasal waktu"


def test_pasal_risiko_menyebut_dasar_ganti_rugi_dan_kahar():
    _judul, butir = pasal_risiko("mutasi_pengguna")
    teks = " ".join(butir)
    assert "1x24 jam" in teks
    assert "38 Tahun 2016" in teks          # dasar TGR
    assert "KEADAAN KAHAR" in teks
    assert "kepolisian" in teks.lower()
    # kejadian di luar jam kerja punya jalur pelaporan yang jelas
    assert "hari libur" in teks.lower()


def test_pustaka_bidang_sehat():
    """Tiap entri: kunci angka, nama & judul terisi, minimal satu butir."""
    for kunci, (nama, judul, butir) in PASAL_BIDANG.items():
        assert kunci.isdigit(), kunci
        assert nama and judul.startswith("KETENTUAN KHUSUS")
        assert butir and all(isinstance(t, str) and t.strip() for t in butir)
