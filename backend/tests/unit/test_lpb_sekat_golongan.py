"""LPB: sekat golongan + bidang bernama & bernilai, sumber tak berulang.

Laporan pemilik atas keluaran LPB yang sudah terbit: *"pada per bidangnya
masih tidak ada nama bidangnya dan jumlah totalnya … dan detail akan lebih
spesifik lagi per golongan barang … dan khusus LPB tolong coba perbaiki
informasi mana yang sekiranya melekat bersama informasi row data dengan
meminimalisir informasi berulang … agar terorganisir dan terkelompokkan
dengan baik."*

Tiga hal yang diperbaiki, dan alasan masing-masing:

1. **Sekat bidang tanpa nama** terbaca seperti dokumennya yang rusak, padahal
   referensi kodefikasi satker itulah yang belum berisi bidang tersebut. Kini
   dinyatakan apa adanya sehingga yang membacanya tahu apa yang harus diisi.
2. **Sekat tanpa nilai** memaksa pembaca menjumlah sendiri kolom terakhir
   untuk tahu berapa nilai satu kelompok — pekerjaan yang justru dihindari
   dengan mengelompokkan.
3. **Bundel sumber yang terulang.** Pada LPB yang seluruh barangnya berasal
   dari satu register — bentuk yang paling sering — kalimat yang sama persis
   dulu tercetak sebanyak jumlah barangnya. Yang terulang berhenti dibaca, dan
   yang BERBEDA jadi ikut terlewat.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps

SATKER = "527010"
USER = {"username": "gudang", "role": "admin", "kode_satker": SATKER}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import routes.reports as rr
    import shared_utils as su
    for mod in (rps, su, rr):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


SUMBER_A = {"penyedia": "CV Sumber Rejeki", "ppk_nama": "Bimo",
            "sifat": "kontrak", "no_sp_spk": "SPK-014/PPK/VIII/2026",
            "nomor_bast_ppk": "B-001/2026"}
SUMBER_B = {"penyedia": "PT Dua Saudara", "ppk_nama": "Bimo",
            "sifat": "non_kontrak", "jenis_up": "up",
            "nomor_bast_ppk": "B-002/2026"}


def _it(kode, nama, jml, harga, sumber=None, nup=""):
    return {"kode_barang": kode, "nama_barang": nama, "jumlah": jml,
            "satuan": "unit", "harga_satuan": harga, "total": jml * harga,
            "nup": nup, "sumber": sumber}


async def _pdf(dbx, items):
    await dbx.kodefikasi.insert_many([
        {"kode": "305", "uraian": "Alat Kantor dan Rumah Tangga"},
        {"kode": "302", "uraian": "Alat Angkutan"},
    ])
    await dbx.lpb.insert_one({
        "id": "lpb-1", "kode_satker": SATKER, "kategori": "gabungan",
        "nomor": "LPB-01/2026", "tanggal": "2026-08-23", "items": items,
        "total_nilai": sum(x["total"] for x in items)})
    return await rps.bangun_lpb_pdf("lpb-1", USER)


def _teks(raw):
    pdfium = pytest.importorskip("pypdfium2")
    pdf = pdfium.PdfDocument(raw)
    try:
        return " ".join(pdf[i].get_textpage().get_text_range()
                        for i in range(len(pdf)))
    finally:
        pdf.close()


def _rapat(teks):
    """Sel PDF DIBUNGKUS; mencocokkan teks mentah membuat uji lolos untuk
    keadaan yang sebenarnya salah (sudah pernah terjadi)."""
    return "".join(str(teks or "").split())


CAMPUR = [
    _it("3050104001", "Laptop", 3, 15_000_000, SUMBER_A, "1–3"),
    _it("3020101001", "Kendaraan", 1, 350_000_000, SUMBER_A, "1"),
    _it("1010301001", "Kertas HVS", 50, 55_000, SUMBER_A),
]


def test_perapat_bekerja():
    assert "Golongan" in _rapat("Golong\r\nan")


class TestSekatGolongan:
    def test_golongan_bersekat_dengan_nama_jumlah_dan_nilai(self, dbx):
        r = _rapat(_teks(_jalan(_pdf(dbx, CAMPUR))))
        assert "GOLONGAN3—PeralatandanMesin·4unit·395.000.000" in r
        assert "GOLONGAN1—Persediaan·50unit·2.750.000" in r

    def test_bidang_bersarang_di_dalam_golongannya(self, dbx):
        t = _teks(_jalan(_pdf(dbx, CAMPUR)))
        assert t.index("GOLONGAN 1") < t.index("BIDANG 101")
        assert t.index("BIDANG 101") < t.index("GOLONGAN 3")


class TestSekatBidangLengkap:
    def test_bidang_terdaftar_menyebut_nama_dan_nilainya(self, dbx):
        r = _rapat(_teks(_jalan(_pdf(dbx, CAMPUR))))
        assert "BIDANG302—AlatAngkutan·1unit·350.000.000" in r
        assert "BIDANG305—AlatKantordanRumahTangga·3unit·45.000.000" in r

    def test_bidang_BELUM_TERDAFTAR_dinyatakan_apa_adanya(self, dbx):
        """Sekat tanpa nama terbaca seperti dokumennya yang rusak; yang
        sebenarnya kurang adalah isi referensi kodefikasi satker itu."""
        r = _rapat(_teks(_jalan(_pdf(dbx, CAMPUR))))
        assert "BIDANG101—(belumterdaftardireferensikodefikasi)" in r

    def test_jumlah_unit_menjumlah_QTY_bukan_menghitung_baris(self, dbx):
        """50 rim kertas pada satu baris adalah 50 unit, bukan 1."""
        r = _rapat(_teks(_jalan(_pdf(dbx, CAMPUR))))
        assert "·50unit·" in r


class TestSumberTidakBerulang:
    def test_satu_sumber_dicetak_SEKALI_di_bawah_tabel(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, CAMPUR)))
        assert teks.count("CV Sumber Rejeki") == 1, teks.count("CV Sumber Rejeki")
        assert "Seluruh barang di atas berasal dari" in teks

    def test_keterangannya_TIDAK_hilang_saat_dipadatkan(self, dbx):
        """Memangkas pengulangan tak boleh membuang informasinya."""
        teks = _teks(_jalan(_pdf(dbx, CAMPUR)))
        for bagian in ("CV Sumber Rejeki", "Bimo", "SPK-014/PPK/VIII/2026",
                       "B-001/2026"):
            assert bagian in teks, bagian

    def test_dua_sumber_berbeda_tetap_menempel_di_barisnya(self, dbx):
        """Inilah alasan bundel per baris ada: satu kepala surat hanya bisa
        menyebut satu penyedia."""
        teks = _teks(_jalan(_pdf(dbx, [
            _it("3050104001", "Laptop", 3, 15_000_000, SUMBER_A, "1–3"),
            _it("3020101001", "Kendaraan", 1, 350_000_000, SUMBER_B, "1")])))
        assert "CV Sumber Rejeki" in teks and "PT Dua Saudara" in teks
        assert "Seluruh barang di atas berasal dari" not in teks

    def test_sumber_sama_beruntun_tidak_dicetak_dua_kali(self, dbx):
        """Dua barang berurutan dari penyedia yang sama cukup satu keterangan."""
        teks = _teks(_jalan(_pdf(dbx, [
            _it("3050104001", "Laptop", 1, 15_000_000, SUMBER_A, "1"),
            _it("3050104002", "Monitor", 1, 2_000_000, SUMBER_A, "1"),
            _it("3020101001", "Kendaraan", 1, 350_000_000, SUMBER_B, "1")])))
        assert teks.count("CV Sumber Rejeki") == 1
        assert teks.count("PT Dua Saudara") == 1

    def test_tanpa_sumber_sama_sekali_tetap_terbit(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, [
            _it("1010301001", "Kertas HVS", 5, 50_000)])))
        assert "Kertas HVS" in teks


class TestKelengkapanBerkasDiLpb:
    """LPB adalah dokumen yang DIPEGANG pengurus barang — di sinilah daftar
    berkasnya paling sering dibuka kembali."""

    def test_blok_kelengkapan_terbit(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, CAMPUR)))
        assert "KELENGKAPAN BERKAS YANG MENYERTAI BARANG" in teks

    def test_kendaraan_diminta_BPKB(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, CAMPUR)))
        assert "BPKB" in teks

    def test_persediaan_TIDAK_diminta_BPKB(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, [
            _it("1010301001", "Kertas HVS", 5, 50_000)])))
        assert "KELENGKAPAN BERKAS YANG MENYERTAI BARANG" in teks
        assert "BPKB" not in teks

    def test_nilai_diambil_dari_total_baris_LPB(self, dbx):
        """Baris LPB membawa `total`, bukan hanya `harga_satuan` — ambangnya
        harus tetap kena."""
        teks = _teks(_jalan(_pdf(dbx, [
            _it("3050104001", "Server", 1, 250_000_000)])))
        assert "Rp100.000.000 atau lebih" in teks

    def test_barang_kecil_tidak_memunculkan_catatan_ambang(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, [
            _it("1010301001", "Kertas HVS", 5, 50_000)])))
        assert "atau lebih" not in teks

    def test_butir_disusun_dua_kolom_di_LPB_juga(self, dbx):
        teks = _teks(_jalan(_pdf(dbx, CAMPUR)))
        ganda = [b for b in teks.splitlines() if b.count("[ ]") >= 2]
        assert len(ganda) >= 2, [b for b in teks.splitlines() if "[ ]" in b]

    def test_isi_daftar_tidak_berkurang_setelah_dipadatkan(self, dbx):
        teks = _rapat(_teks(_jalan(_pdf(dbx, CAMPUR))))
        for butir in ("BPKBatasnamaPemerintahRIc.q.K/L",
                      "Kartu/beritaacarapenerimaangudang",
                      "BeritaAcaraPemeriksaan/Penerimaanbarang"):
            assert butir in teks, butir
