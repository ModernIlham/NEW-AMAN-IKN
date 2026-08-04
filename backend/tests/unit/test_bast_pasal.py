"""Uji pustaka PASAL BAST (murni) — pemilihan butir khusus per BIDANG kode
barang serta butir konteks waktu & risiko.

Yang dijaga di sini gagal SENYAP kalau meleset: aturan kendaraan menempel
pada laptop (aturan salah pada dokumen resmi), butir khusus hilang karena
panjang kode berbeda, urutan berubah antar unduhan sehingga dua salinan
dokumen sama tidak identik, atau pemotongan daftar bidang tak dilaporkan.
"""
from bast_pasal import (
    JENIS_PENGUASAAN, PASAL_BIDANG, bidang_kode, butir_khusus_bidang,
    butir_risiko, butir_waktu, nama_bidang_terpakai, sisa_bidang,
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


def test_butir_kendaraan_hanya_untuk_kendaraan():
    """Aturan SIM/pajak/pool tidak boleh menempel pada laptop, dan
    sebaliknya."""
    mobil = " ".join(butir_khusus_bidang([MOBIL]))
    laptop = " ".join(butir_khusus_bidang([LAPTOP]))
    assert "Kendaraan Dinas" in mobil and "Surat Izin Mengemudi" in mobil
    assert "Kendaraan Dinas" not in laptop
    assert "Komputer" in laptop and "kata sandi" in laptop


def test_bidang_mengalahkan_golongan():
    """Prefix TERPANJANG menang: 302 (Alat Angkutan) bukan 3 (Peralatan dan
    Mesin) — kalau terbalik, semua barang golongan 3 dapat butir generik."""
    assert "Kendaraan Dinas" in butir_khusus_bidang([MOBIL])[0]
    # bidang yang belum punya aturan sendiri turun ke golongan
    assert "Peralatan dan Mesin" in butir_khusus_bidang(["3990101001"])[0]


def test_gabungan_unik_dan_terurut():
    """Banyak aset satu bidang → satu butir; urutan deterministik menurut
    kode bidang supaya dua unduhan dokumen sama identik."""
    kode = [LAPTOP, MOBIL, LAPTOP, MEJA, MOBIL]
    nama = nama_bidang_terpakai(kode)
    assert nama == ["Kendaraan Dinas",              # 302
                    "Alat Kantor dan Rumah Tangga",  # 305
                    "Komputer dan Perangkat Kerja"]  # 310
    assert nama == nama_bidang_terpakai(list(reversed(kode)))
    assert len(butir_khusus_bidang(kode)) == 3


def test_pemotongan_dilaporkan_bukan_disembunyikan():
    kode = [TANAH, "3010101001", MOBIL, MEJA, "3060101001", "3070101001",
            LAPTOP]
    dipakai, sisa = sisa_bidang(kode, maks=4)
    assert dipakai == 4
    assert sisa == ["Alat Studio, Komunikasi dan Pemancar",
                    "Alat Kedokteran dan Kesehatan",
                    "Komputer dan Perangkat Kerja"]
    assert len(butir_khusus_bidang(kode, maks=4)) == 4


def test_hewan_diikat_perawatan_hari_libur():
    """Kebalikan kendaraan: hewan/tanaman WAJIB dirawat pada hari libur —
    pembeda inti mandat 'antisipasi hari libur'."""
    assert "hari libur" in butir_khusus_bidang([SAPI])[0].lower()


def test_butir_waktu_dan_risiko_hanya_saat_penguasaan_beralih():
    for jenis in JENIS_PENGUASAAN:
        assert butir_waktu(jenis) and butir_risiko(jenis)
    # Pengembalian: barang kembali ke satker — kewajiban penggunaan tak lagi
    # dibebankan kepada mantan pemegang.
    for jenis in ("pengembalian", "pengembalian_almarhum"):
        assert butir_waktu(jenis) == [] and butir_risiko(jenis) == []


def test_butir_waktu_meliputi_semua_konteks_mandat_dalam_dua_butir():
    """Diringkas menjadi 2 butir (dulu 5) TANPA kehilangan konteks apa pun."""
    butir = butir_waktu("penggunaan_melekat")
    assert len(butir) == 2
    teks = " ".join(butir).lower()
    for kata in ("jam kerja", "hari libur", "lembur", "perjalanan dinas",
                 "surat tugas", "pribadi"):
        assert kata in teks, f"konteks '{kata}' hilang dari butir waktu"


def test_butir_risiko_padat_tapi_lengkap():
    """Diringkas menjadi 3 butir (dulu 6): pelaporan, ganti rugi, kahar."""
    butir = butir_risiko("mutasi_pengguna")
    assert len(butir) == 3
    teks = " ".join(butir)
    assert "1x24 jam" in teks
    assert "hari libur" in teks.lower() and "kepolisian" in teks.lower()
    assert "38 Tahun 2016" in teks          # dasar ganti rugi
    assert "kahar" in teks.lower() and "asuransi" in teks.lower()


def test_pustaka_bidang_sehat():
    """Tiap entri: kunci angka, nama & kalimat kewajiban terisi dan ringkas."""
    for kunci, (nama, kalimat) in PASAL_BIDANG.items():
        assert kunci.isdigit(), kunci
        assert nama and kalimat and not kalimat.endswith(".")
        assert len(kalimat) < 700, f"butir bidang {kunci} terlalu panjang"
