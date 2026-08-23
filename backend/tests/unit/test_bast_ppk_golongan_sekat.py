"""Golongan barang jadi BARIS SEKAT, bukan kolom — BAST PPK→KPB.

Permintaan pemilik: *"pada bagian objek serah terima 'golongan barang' jangan
jadikan sebagai kolom akan tetapi jadikan sebagai row yang membagi data-data
row di bawahnya yang sudah dikategorikan per golongan barang, dan juga buat
pembagi lagi tambahan yaitu per bidangnya yang sudah rapi dan urut. Tambahkan
informasi juga apabila terdapat informasinya mengenai kontrak atau non-kontrak
seperti SP/SPK, SPP/SPM, UP/TUP, SPBy, No Dokumen. Buat informasinya teratur
dan terorganisasi dengan baik agar rapi dan mudah dipahami."*

Kenapa golongan tak layak jadi kolom: nilainya berulang identik pada setiap
baris satu kelompok, memakan lebar yang dibutuhkan uraian barang, dan tetap
tak menjawab pertanyaan yang orang bawa ke dokumen ini — "golongan apa saja
yang diserahkan, berapa banyak, berapa nilainya".

Uji ini merender PDF SUNGGUHAN lalu membaca teksnya kembali: susunan tabel
tidak bisa dibuktikan dari kode saja.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.pengadaan as rp
import routes.reports as rr
import shared_utils as su

USER = {"username": "op", "role": "admin", "kode_satker": "111111"}

BARANG = [
    {"kode": "3050104001", "uraian": "Laptop Dell", "jumlah": 3, "harga_satuan": 15000000},
    {"kode": "3020101001", "uraian": "Kendaraan Roda 4", "jumlah": 1, "harga_satuan": 350000000},
    {"kode": "3050102003", "uraian": "Printer Multifungsi", "jumlah": 2, "harga_satuan": 4500000},
    {"kode": "1010301001", "uraian": "Kertas HVS", "jumlah": 50, "harga_satuan": 55000},
    {"kode": "1010301004", "uraian": "Tinta Printer", "jumlah": 10, "harga_satuan": 320000},
]


def _rapat(teks):
    """Teks tanpa spasi/ganti-baris sama sekali.

    Sel tabel PDF DIBUNGKUS: judul kolom "Golongan" terbaca sebagai
    "Golong\r\nan" saat teksnya diekstrak. Menagih pada teks mentah membuat
    uji lolos untuk kolom yang sebenarnya MASIH ADA — sudah terjadi sekali.
    """
    return "".join(str(teks or "").split())


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _buka(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    for mod in (rp, rr, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


async def _seed(dbx, **ubah):
    dok = {
        "id": "pg-1", "kode_satker": "111111", "jenis": "pembelian",
        "pihak": "PT Maju Jaya", "nomor_bast": "BAST-9/PPK/2026",
        "tanggal_bast": "2026-08-10", "barang": BARANG,
        "bast_ppk": {"nomor": "BA-12/PPK-KPB/2026", "tanggal": "2026-08-12",
                     "ppk_nama": "Budi", "ppk_jabatan": "PPK",
                     "kpb_nama": "Sari", "kpb_jabatan": "Kuasa Pengguna Barang"},
    }
    dok.update(ubah)
    await dbx.pengadaan.insert_one(dok)
    await dbx.kodefikasi.insert_many([
        {"kode": "305", "uraian": "Alat Kantor dan Rumah Tangga"},
        {"kode": "302", "uraian": "Alat Angkutan"},
        {"kode": "101", "uraian": "Barang Konsumsi"},
    ])


async def _teks(dbx, **ubah):
    await _seed(dbx, **ubah)
    resp = await _buka(rp.bast_ppk_kpb_pdf)("pg-1", _user=USER)
    buf = io.BytesIO()
    async for potong in resp.body_iterator:
        buf.write(potong if isinstance(potong, bytes) else potong.encode())
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(buf.getvalue())
    return "\n".join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))


def test_perapat_menangkap_judul_yang_terbungkus():
    """Penjaga bagi penjaganya: perapat yang tak bekerja membuat SELURUH uji
    di berkas ini lolos tanpa memeriksa apa pun."""
    assert "Golongan" in _rapat("Golong\r\nan")
    assert "Golongan" not in _rapat("Gol ongna")


class TestGolonganBukanKolom:
    def test_tak_ada_lagi_kolom_golongan(self, dbx):
        teks = _jalan(_teks(dbx))
        kepala = teks.split("PASAL 1")[1].split("GOLONGAN")[0]
        assert "Golongan" not in _rapat(kepala), kepala

    def test_kolom_yang_tersisa_masih_lengkap(self, dbx):
        teks = _jalan(_teks(dbx))
        rapat = _rapat(teks)
        for kolom in ("KodeBarang", "UraianBarang", "Jumlah",
                      "HargaSatuan", "JumlahHarga"):
            assert kolom in rapat, kolom

    def test_sekat_golongan_menyebut_nama_jumlah_dan_nilai(self, dbx):
        teks = _jalan(_teks(dbx))
        rapat = _rapat(teks)
        assert "GOLONGAN3—PeralatandanMesin·6unit·404.000.000" in rapat
        assert "GOLONGAN1—Persediaan·60unit·5.950.000" in rapat

    def test_nilai_per_golongan_menjumlah_tanpa_baris_subtotal(self, dbx):
        """Nilai kelompok menumpang baris sekat: subtotal tersedia TANPA
        menggandakan tinggi tabel dengan baris sendiri."""
        teks = _jalan(_teks(dbx))
        assert "Subtotal" not in teks
        assert "404.000.000" in teks


class TestSekatBidangBersarang:
    def test_tiap_bidang_punya_sekatnya_sendiri(self, dbx):
        teks = _jalan(_teks(dbx))
        rapat = _rapat(teks)
        assert "BIDANG302—AlatAngkutan·1unit" in rapat
        assert "BIDANG305—AlatKantordanRumahTangga·5unit" in rapat
        assert "BIDANG101—BarangKonsumsi·60unit" in rapat

    def test_bidang_muncul_setelah_golongan_induknya(self, dbx):
        teks = _jalan(_teks(dbx))
        i_gol3 = teks.index("GOLONGAN 3")
        i_b302 = teks.index("BIDANG 302")
        i_b305 = teks.index("BIDANG 305")
        i_gol1 = teks.index("GOLONGAN 1")
        i_b101 = teks.index("BIDANG 101")
        assert i_gol1 < i_b101 < i_gol3 < i_b302 < i_b305

    def test_urut_menaik_bukan_urutan_penginputan(self, dbx):
        """Daftar diinput acak; dokumen resmi harus terurut kodefikasi."""
        teks = _jalan(_teks(dbx))
        assert teks.index("Kendaraan Roda 4") < teks.index("Printer Multifungsi")
        assert teks.index("Printer Multifungsi") < teks.index("Laptop Dell")

    def test_penomoran_berlanjut_menembus_sekat(self, dbx):
        """Nomor urut tak boleh mengulang dari 1 di tiap kelompok — pembaca
        memakainya untuk mencocokkan jumlah baris dokumen."""
        teks = _jalan(_teks(dbx))
        baris = [b for b in teks.splitlines() if "Laptop Dell" in b]
        assert baris and baris[0].strip().startswith("5"), baris


class TestBarangTanpaKodeTetapTerbit:
    def test_tanpa_kode_tidak_hilang_dari_dokumen(self, dbx):
        teks = _jalan(_teks(dbx, barang=[
            {"kode": "", "uraian": "Jasa Instalasi", "jumlah": 1,
             "harga_satuan": 1000000}]))
        assert "Jasa Instalasi" in teks
        assert "TANPAGOLONGAN" in _rapat(teks)


class TestBlokDokumenTerorganisasi:
    def test_kontrak_menyebut_sifat_dan_mengelompokkan(self, dbx):
        teks = _jalan(_teks(
            dbx, sifat="kontrak", no_sp_spk="SPK-014/PPK/VIII/2026",
            no_spp="SPP-105/LS/2026", no_spm="02847T/621001/2024",
            no_dokumen="ND-77/PBJ/2026"))
        rapat = _rapat(teks)
        assert "Sifatpengadaan:Kontrak" in rapat
        assert "Perikatan" in rapat and "Pembayaran" in rapat
        assert "SPK-014/PPK/VIII/2026" in teks
        assert "02847T/621001/2024" in teks
        assert "ND-77/PBJ/2026" in teks

    def test_non_kontrak_membawa_up_tup_dan_spby(self, dbx):
        teks = _jalan(_teks(dbx, sifat="non_kontrak", jenis_up="tup",
                            no_spby="SPBy-021/BP/VIII/2026"))
        rapat = _rapat(teks)
        assert "Sifatpengadaan:Non-Kontrak" in rapat
        assert "TUP(TambahanUP)" in rapat
        assert "SPBy-021/BP/VIII/2026" in teks

    def test_kelompok_kosong_TIDAK_dicetak(self, dbx):
        """Blok yang separuhnya bertanda hubung membuat pembaca menghitung apa
        yang tak ada alih-alih membaca apa yang ada."""
        teks = _jalan(_teks(dbx, sifat="kontrak", no_sp_spk="SPK-1"))
        blok = teks.split("DASAR DAN DOKUMEN PENGADAAN")[1].split("PASAL 1")[0]
        assert "Perikatan" in blok
        assert "Pembayaran" not in blok
        assert "Rujukan lain" not in blok

    def test_tanpa_dokumen_sama_sekali_bloknya_tak_muncul(self, dbx):
        teks = _jalan(_teks(dbx))
        assert "DASAR DAN DOKUMEN PENGADAAN" not in teks
