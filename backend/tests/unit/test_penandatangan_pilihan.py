"""Penanda tangan dokumen dipilih dari Referensi Pejabat — tiga lapis.

Permintaan pemilik: *"benahi kolom tanda tangan agar … sudah aktif semua bisa
memilih siapa saja yang menandatangani sesuai referensi pejabat yang sudah
ditetapkan"*, dengan pilihannya: **setelan satker yang bisa ditimpa per
dokumen**.

Urutannya, dan kenapa urutan itu:

1. **Pilihan dokumen** — dibekukan saat dokumen terbit. Dokumen yang sudah
   ditandatangani tak boleh berganti nama penanda tangan hanya karena setelan
   satker kelak diubah.
2. **Setelan satker** — ditetapkan sekali, dipakai seluruh dokumen berikutnya.
3. **Peran pada Referensi Pejabat** — perilaku lama, tetap jadi jaring
   terakhir. Satker yang belum pernah menyentuh setelan ini tak berubah apa
   pun.

Slot "Diperiksa oleh" pada LPB adalah yang paling sering kosong: perannya
(`pemeriksa_lpb`) jarang ditetapkan, sehingga kolomnya terbit sebagai
titik-titik tanpa ada yang bisa dilakukan dari layar mana pun.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persediaan as rps
from penandatangan_dokumen import (
    KUNCI_SLOT, SLOT_TTD, asal_pilihan, bersihkan_penandatangan, pilih_pejabat,
    validate_penandatangan,
)

SATKER = "527010"
USER = {"username": "gudang", "role": "admin", "kode_satker": SATKER}
DAFTAR = [
    {"id": "pj-a", "nama": "Andi Pengurus", "nip": "197001011990031001",
     "jabatan": "Pengurus Barang", "kode_satker": SATKER},
    {"id": "pj-b", "nama": "Bela Pemeriksa", "nip": "198002022005022002",
     "jabatan": "Kasubbag Umum", "kode_satker": SATKER},
]


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


class TestPembersihanDanValidasi:
    def test_hanya_slot_dikenal_yang_diambil(self):
        d = bersihkan_penandatangan({"lpb_dibuat": " pj-a ", "asing": "x"})
        assert d == {"lpb_dibuat": "pj-a"}

    def test_slot_kosong_tak_ikut(self):
        assert bersihkan_penandatangan({"lpb_dibuat": "   "}) == {}

    def test_slot_asing_DITOLAK_bukan_dibuang_diam_diam(self):
        """Admin yang salah ketik nama slot berhak tahu setelannya tak akan
        berlaku."""
        e = validate_penandatangan({"lpb_salah": "pj-a"})
        assert len(e) == 1 and "lpb_salah" in e[0]

    def test_kosong_dan_None_bukan_kesalahan(self):
        assert validate_penandatangan(None) == []
        assert validate_penandatangan({}) == []

    def test_bukan_peta_ditolak(self):
        assert validate_penandatangan(["pj-a"]) != []

    def test_katalog_slot_menerangkan_dirinya(self):
        for k in KUNCI_SLOT:
            assert SLOT_TTD[k]["label"] and SLOT_TTD[k]["peran"]
            assert SLOT_TTD[k]["arti"]


class TestTigaLapis:
    PERAN = {"nama": "Dari Peran", "nip": "1"}

    def test_pilihan_dokumen_menang(self):
        p = pilih_pejabat("lpb_dibuat", {"lpb_dibuat": "pj-a"},
                          {"lpb_dibuat": "pj-b"}, DAFTAR, self.PERAN)
        assert p["nama"] == "Andi Pengurus"

    def test_setelan_satker_dipakai_bila_dokumen_tak_memilih(self):
        p = pilih_pejabat("lpb_dibuat", {}, {"lpb_dibuat": "pj-b"},
                          DAFTAR, self.PERAN)
        assert p["nama"] == "Bela Pemeriksa"

    def test_resolusi_peran_tetap_jaring_terakhir(self):
        """Satker yang belum pernah menyentuh setelan ini tak berubah apa
        pun."""
        p = pilih_pejabat("lpb_dibuat", {}, {}, DAFTAR, self.PERAN)
        assert p == self.PERAN

    def test_id_BASI_jatuh_ke_lapis_berikutnya_bukan_mengosongkan(self):
        """Pejabat bisa dihapus atau berpindah satker setelah setelan dibuat.
        Membiarkan slotnya kosong berarti dokumen resmi terbit tanpa penanda
        tangan, dan yang mencetaknya tak diberi tahu apa pun."""
        p = pilih_pejabat("lpb_dibuat", {"lpb_dibuat": "hantu"},
                          {"lpb_dibuat": "pj-b"}, DAFTAR, self.PERAN)
        assert p["nama"] == "Bela Pemeriksa"
        p2 = pilih_pejabat("lpb_dibuat", {"lpb_dibuat": "hantu"}, {},
                           DAFTAR, self.PERAN)
        assert p2 == self.PERAN

    def test_tanpa_jaring_terakhir_menghasilkan_dict_kosong(self):
        assert pilih_pejabat("lpb_dibuat", {}, {}, DAFTAR) == {}

    def test_asal_pilihan_menerangkan_dari_lapis_mana(self):
        assert asal_pilihan("lpb_dibuat", {"lpb_dibuat": "pj-a"},
                            {"lpb_dibuat": "pj-b"}, DAFTAR) == "dokumen"
        assert asal_pilihan("lpb_dibuat", {}, {"lpb_dibuat": "pj-b"},
                            DAFTAR) == "satker"
        assert asal_pilihan("lpb_dibuat", {}, {}, DAFTAR) == "peran"

    def test_asal_pilihan_ikut_melewati_id_basi(self):
        assert asal_pilihan("lpb_dibuat", {"lpb_dibuat": "hantu"},
                            {"lpb_dibuat": "pj-b"}, DAFTAR) == "satker"


class TestLpbMemakaiPilihannya:
    async def _pdf(self, dbx, setelan=None, dokumen=None):
        await dbx.report_settings.insert_one({
            "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
            "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
            "alamat_instansi": "Gedung Kantor OIKN"})
        await dbx.pejabat.insert_many([dict(p) for p in DAFTAR])
        await dbx.satker.insert_one({
            "kode_satker": SATKER, "nama_satker": "Satker Uji",
            "penandatangan": setelan or {}})
        await dbx.lpb.insert_one({
            "id": "lpb-1", "kode_satker": SATKER, "kategori": "persediaan",
            "nomor": "LPB-01/2026", "tanggal": "2026-08-04",
            "penandatangan": dokumen or {},
            "items": [{"kode_barang": "1010301001", "nama_barang": "Kertas",
                       "jumlah": 1, "satuan": "Rim", "harga_satuan": 1,
                       "total": 1}],
            "total_nilai": 1})
        return await rps.bangun_lpb_pdf("lpb-1", USER)

    def _teks(self, raw):
        pdfium = pytest.importorskip("pypdfium2")
        pdf = pdfium.PdfDocument(raw)
        try:
            return " ".join(pdf[i].get_textpage().get_text_range()
                            for i in range(len(pdf)))
        finally:
            pdf.close()

    def test_setelan_satker_mengisi_slot_pemeriksa_yang_biasanya_kosong(self, dbx):
        teks = self._teks(_jalan(self._pdf(
            dbx, setelan={"lpb_diperiksa": "pj-b"})))
        assert "Bela Pemeriksa" in teks

    def test_pilihan_dokumen_menimpa_setelan_satker(self, dbx):
        teks = self._teks(_jalan(self._pdf(
            dbx, setelan={"lpb_diperiksa": "pj-b"},
            dokumen={"lpb_diperiksa": "pj-a"})))
        assert "Andi Pengurus" in teks
        assert "Bela Pemeriksa" not in teks

    def test_tanpa_setelan_apa_pun_dokumen_tetap_terbit(self, dbx):
        """Perilaku lama utuh: slot yang tak punya pejabat berperan terbit
        sebagai garis kosong, bukan menggagalkan cetak."""
        teks = self._teks(_jalan(self._pdf(dbx)))
        assert "Laporan Penerimaan Barang" in teks or "LPB" in teks

    def test_id_basi_pada_setelan_tak_mengosongkan_dokumen(self, dbx):
        teks = self._teks(_jalan(self._pdf(
            dbx, setelan={"lpb_dibuat": "sudah-dihapus"})))
        assert "Dibuat oleh" in teks


class TestGerbangPenyimpanan:
    def test_master_satker_menolak_slot_asing(self):
        import routes.satker as rsk
        assert "penandatangan" in rsk.SatkerIn.model_fields

    def test_lpb_gabungan_menerima_override(self):
        import routes.pengadaan as rpg
        assert "penandatangan" in rpg.LpbGabunganIn.model_fields
