"""Tabel LPB: bundel sumber per barang, berkelompok per bidang.

Permintaan pemilik: *"keterangan rekanan/penyedia, PPK dll yang menempel pada
setiap barang pengadaannya masing-masing dijadikan satu bundle informasi di
dalam tabel, bertempat di row barang di bawahnya yang sudah dikategorikan…
dan pada setiap row barang tolong kategorikan dengan per bidang barangnya
masing-masing agar menambah kerapian. Dan juga kode barang ditambahkan
informasi mengenai sub-sub kelompok kode barangnya dan NUP informasi dari no
berapa sampai berapa."*

Dua hal yang membuat rancangan ini bukan sekadar kerapian:

1. **LPB gabungan merangkum banyak BAST PPK-KPB sekaligus.** Satu kepala surat
   hanya bisa menyebut SATU penyedia — pembaca yang ingin tahu barang ini
   datang dari rekanan mana harus bisa membacanya di barisnya sendiri.
2. **Bundelnya baris tersendiri, bukan kolom-kolom baru.** Tabel ini sudah
   berisi tujuh kolom; menambah enam kolom dokumen akan menyempitkan nama
   barang sampai tak terbaca, dan sebagian besarnya kosong karena tiap
   register hanya menempuh satu jalur pembayaran.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps
from lpb_utils import (
    baris_lpb_gabungan, bundel_sumber, rentang_nup, snapshot_sumber,
)

SATKER = "527010"
USER = {"username": "gudang", "role": "admin", "kode_satker": SATKER}


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


PEROLEHAN = {
    "id": "p-1", "pihak": "CV Sumber Rejeki", "nomor_bast": "BAST-01/2026",
    "bast_ppk": {"nomor": "BA-07/PPK/2026"},
    "ppk_nama": "Budi Komitmen", "ppk_nip": "197001011990031001",
    "sifat": "kontrak", "no_sp_spk": "SPK-014/PPK/VIII/2026",
    "no_spm": "02847T/621001/2024",
    "barang": [
        {"kode": "3100102001", "uraian": "PC All In One", "jumlah": 2,
         "harga_satuan": 9_000_000, "NUP": "1"},
        {"kode": "3050101001", "uraian": "Mesin Ketik", "jumlah": 1,
         "harga_satuan": 1_000_000, "NUP": "4"},
    ],
}


class TestRentangNup:
    def test_berurutan_jadi_satu_rentang(self):
        assert rentang_nup([3, 1, 2]) == "1–3"

    def test_celah_tetap_terlihat(self):
        """Menyatukan 1,4,5,6 menjadi "1–6" akan menyatakan kepemilikan NUP 2
        dan 3 yang tak pernah diterima."""
        assert rentang_nup([1, 4, 5, 6]) == "1, 4–6"

    def test_satu_nomor_tak_diberi_tanda_rentang(self):
        assert rentang_nup([7]) == "7" and rentang_nup(["7"]) == "7"

    def test_kembar_dan_bukan_angka_diabaikan(self):
        assert rentang_nup([2, 2, "x", None, 3]) == "2–3"

    def test_kosong_menghasilkan_kosong(self):
        assert rentang_nup([]) == "" and rentang_nup(None) == ""


class TestSnapshotSumber:
    def test_membekukan_penyedia_ppk_dan_dokumen(self):
        s = snapshot_sumber(PEROLEHAN)
        assert s["penyedia"] == "CV Sumber Rejeki"
        assert s["ppk_nama"] == "Budi Komitmen"
        assert s["sifat"] == "kontrak"
        assert s["no_sp_spk"] == "SPK-014/PPK/VIII/2026"
        assert s["nomor_bast_ppk"] == "BA-07/PPK/2026"

    def test_register_tanpa_dokumen_tetap_menghasilkan_kolom_kosong(self):
        s = snapshot_sumber({"pihak": "CV X"})
        assert s["no_sp_spk"] == "" and s["sifat"] == ""


class TestBundelSumber:
    def test_menyebut_penyedia_ppk_sifat_dokumen_dan_asalnya(self):
        t = bundel_sumber(snapshot_sumber(PEROLEHAN))
        for bagian in ("CV Sumber Rejeki", "Budi Komitmen", "Kontrak",
                       "SPK-014/PPK/VIII/2026", "02847T/621001/2024",
                       "BA-07/PPK/2026"):
            assert bagian in t, bagian

    def test_kolom_kosong_TIDAK_ikut(self):
        """Bundel yang separuhnya bertanda hubung membuat pembaca menghitung
        apa yang tak ada alih-alih membaca apa yang ada."""
        t = bundel_sumber({"penyedia": "CV X"})
        assert t == "Penyedia: CV X"

    def test_tanpa_apa_pun_menghasilkan_kosong(self):
        assert bundel_sumber({}) == "" and bundel_sumber(None) == ""

    def test_jatuh_ke_nomor_BAST_penyedia_bila_BAST_PPK_belum_terbit(self):
        t = bundel_sumber(snapshot_sumber({**PEROLEHAN, "bast_ppk": {}}))
        assert "BAST BAST-01/2026" in t


class TestBarisMembawaSumbernya:
    def test_tiap_baris_membawa_snapshot_sumbernya_sendiri(self):
        baris = baris_lpb_gabungan([PEROLEHAN])
        assert len(baris) == 2
        for b in baris:
            assert b["sumber"]["penyedia"] == "CV Sumber Rejeki"
            assert b["perolehan_id"] == "p-1"

    def test_dua_perolehan_membawa_penyedia_MASING_MASING(self):
        """Inilah alasan bundelnya per baris: satu kepala surat hanya bisa
        menyebut satu penyedia."""
        lain = {**PEROLEHAN, "id": "p-2", "pihak": "PT Kedua",
                "barang": [{"kode": "3060101001", "uraian": "Kamera",
                            "jumlah": 1, "harga_satuan": 5_000_000}]}
        baris = baris_lpb_gabungan([PEROLEHAN, lain])
        penyedia = {b["sumber"]["penyedia"] for b in baris}
        assert penyedia == {"CV Sumber Rejeki", "PT Kedua"}


class TestTabelLpbDiPdf:
    async def _pdf(self, dbx, items, kategori="gabungan"):
        await dbx.report_settings.insert_one({
            "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
            "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
            "alamat_instansi": "Gedung Kantor OIKN"})
        await dbx.kodefikasi.insert_many([
            {"kode": "310", "uraian": "KOMPUTER"},
            {"kode": "305", "uraian": "ALAT KANTOR"},
            {"kode": "3100102001", "uraian": "Lap Top"},
            {"kode": "3050101001", "uraian": "Mesin Ketik Manual Portable"},
        ])
        await dbx.lpb.insert_one({
            "id": "lpb-1", "kode_satker": SATKER, "kategori": kategori,
            "nomor": "LPB-01/2026", "tanggal": "2026-08-04",
            "items": items, "total_nilai": 19_000_000})
        return await rps.bangun_lpb_pdf("lpb-1", USER)

    def _teks(self, raw):
        pdfium = pytest.importorskip("pypdfium2")
        pdf = pdfium.PdfDocument(raw)
        try:
            return " ".join(pdf[i].get_textpage().get_text_range()
                            for i in range(len(pdf)))
        finally:
            pdf.close()

    def test_bundel_tercetak_di_bawah_barangnya(self, dbx):
        teks = self._teks(_jalan(
            self._pdf(dbx, baris_lpb_gabungan([PEROLEHAN]))))
        assert "CV Sumber Rejeki" in teks
        assert "Budi Komitmen" in teks
        assert "SPK-014/PPK/VIII/2026" in teks

    def test_berkelompok_per_bidang(self, dbx):
        teks = self._teks(_jalan(
            self._pdf(dbx, baris_lpb_gabungan([PEROLEHAN]))))
        assert "BIDANG 310" in teks and "BIDANG 305" in teks

    def test_kode_barang_membawa_sub_sub_kelompok(self, dbx):
        teks = self._teks(_jalan(
            self._pdf(dbx, baris_lpb_gabungan([PEROLEHAN]))))
        assert "Lap Top" in teks
        assert "Mesin Ketik Manual Portable" in teks

    def test_nup_melebur_ke_kolom_identitas(self, dbx):
        teks = self._teks(_jalan(
            self._pdf(dbx, baris_lpb_gabungan([PEROLEHAN]))))
        assert "NUP 1" in teks

    def test_lpb_persediaan_tanpa_sumber_tetap_terbit(self, dbx):
        """LPB persediaan lama tak punya kolom `sumber` sama sekali."""
        teks = self._teks(_jalan(self._pdf(dbx, [
            {"kode_barang": "1010301001", "nama_barang": "Kertas HVS",
             "jumlah": 5, "satuan": "Rim", "harga_satuan": 50_000,
             "total": 250_000, "keterangan": "BAST-9/2026"}],
            kategori="persediaan")))
        assert "Kertas HVS" in teks
        # Keterangan lama tetap tercetak sebagai bundel — tak ada yang hilang.
        assert "BAST-9/2026" in teks


class TestBundelMembawaInfoPerBAST:
    """Permintaan pemilik: *"informasi tanggal kedatangan, NIP PPK, No.
    Bukti/Faktur … harusnya menempel ke informasi row barang … agar saat
    memiliki banyak BAST sekaligus dalam 1 LPB dapat rapi tersusun."*

    Kepala surat hanya punya SATU baris untuk masing-masing. Pada LPB gabungan
    yang merangkum banyak BAST, satu nilai di kepala tak bisa mewakili
    semuanya — dan yang membacanya tak punya cara tahu nilai itu milik BAST
    yang mana.
    """

    LENGKAP = {**PEROLEHAN, "no_bukti": "INV-2026/08/0417",
               "ppk_status_kepegawaian": "pns", "tanggal_bast": "2026-08-01"}

    def test_tanggal_kedatangan_menempel_di_barisnya(self):
        t = bundel_sumber(snapshot_sumber(self.LENGKAP))
        assert "Tgl kedatangan: 1 Agustus 2026" in t

    def test_NIP_PPK_menempel_di_barisnya(self):
        t = bundel_sumber(snapshot_sumber(self.LENGKAP))
        assert "PPK: Budi Komitmen (NIP. 197001011990031001)" in t

    def test_no_bukti_faktur_menempel_di_barisnya(self):
        t = bundel_sumber(snapshot_sumber(self.LENGKAP))
        assert "No. Bukti/Faktur: INV-2026/08/0417" in t

    def test_NIP_PPK_Non_ASN_TIDAK_dicetak(self):
        """ATURAN SISTEM yang sama dengan blok tanda tangan — bundel bukan
        pintu belakang untuk membatalkannya."""
        t = bundel_sumber(snapshot_sumber(
            {**self.LENGKAP, "ppk_status_kepegawaian": "non_asn"}))
        assert "Budi Komitmen" in t
        assert "197001011990031001" not in t

    def test_NIP_berformat_NIK_juga_tertahan(self):
        t = bundel_sumber(snapshot_sumber(
            {**self.LENGKAP, "ppk_nip": "3506042503900001"}))
        assert "3506042503900001" not in t

    def test_dua_BAST_membawa_tanggal_dan_bukti_MASING_MASING(self):
        """Inilah alasan semuanya menempel per baris."""
        lain = {**self.LENGKAP, "id": "p-2", "tanggal_bast": "2026-08-20",
                "no_bukti": "INV-2026/08/0999",
                "barang": [{"kode": "3060101001", "uraian": "Kamera",
                            "jumlah": 1, "harga_satuan": 5_000_000}]}
        baris = baris_lpb_gabungan([self.LENGKAP, lain])
        teks = {bundel_sumber(b["sumber"]) for b in baris}
        assert any("1 Agustus 2026" in t and "INV-2026/08/0417" in t for t in teks)
        assert any("20 Agustus 2026" in t and "INV-2026/08/0999" in t for t in teks)

    def test_register_tanpa_tanggal_atau_bukti_tak_menyisakan_label_kosong(self):
        t = bundel_sumber(snapshot_sumber({"pihak": "CV X"}))
        assert t == "Penyedia: CV X"
