"""Urutan & tata letak laporan resmi — DIVERIFIKASI DARI BERKAS YANG DIRENDER,
bukan dari bentuk data di memori.

Alasannya: yang dipegang pemeriksa adalah PDF/Word-nya. Uji yang hanya
memastikan daftar Python sudah terurut tidak membuktikan barisnya keluar
terurut di kertas — perakitan tabel, pengulangan header, dan blok tanda tangan
semuanya ada di antara keduanya. Uji di bawah merender dokumen sungguhan lalu
membaca isinya kembali.

Yang dikunci:
  1. DBHI (PDF & Word) terurut KODE BARANG menaik lalu NUP menaik — NUP
     sebagai ANGKA, sehingga NUP 2 mendahului NUP 10.
  2. Header kolom nilai berbunyi "Nilai Perolehan", bukan "Nilai" saja.
  3. RHI POTRET dan muat satu halaman.
"""
import asyncio
import io
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

from routes.reports import kunci_urut_bmn, urut_bmn


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _isi(resp):
    """Bytes dari StreamingResponse maupun Response biasa."""
    if hasattr(resp, "body_iterator"):
        return b"".join([c async for c in resp.body_iterator])
    return resp.body


def _telanjangi(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


_USER = {"username": "adm", "role": "admin", "kode_satker": ""}

# Sengaja diacak: kode terkecil ada di TENGAH, dan NUP 2 datang SESUDAH NUP 10.
# Urutan penyimpanan ini yang dulu langsung tercetak apa adanya.
_SEED = [
    ("3050104001", "10"),
    ("3050104001", "2"),
    ("3010102001", "5"),
]


async def _siapkan(monkeypatch):
    import routes.reports as R
    import shared_utils as su

    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(R, "db", fake, raising=False)
    monkeypatch.setattr(su, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(su, "pastikan_akses_kegiatan_id", _diam, raising=False)
    monkeypatch.setattr(R, "pastikan_akses_kegiatan_id", _diam, raising=False)

    await fake.inventory_activities.insert_one(
        {"id": "k1", "nama_kegiatan": "Uji", "kode_satker": "123456"})
    for kode, nup in _SEED:
        await fake.assets.insert_one({
            "id": f"{kode}-{nup}", "activity_id": "k1", "asset_code": kode,
            "NUP": nup, "asset_name": f"Barang{nup}",
            "inventory_status": "Ditemukan", "condition": "Baik",
            "purchase_price": "1000", "purchase_date": "2020-01-01",
            "location": "Gudang A"})
    return fake


class TestKunciUrut:
    """Bagian murni — cepat, dan menjelaskan aturannya."""

    def test_nup_diurut_sebagai_angka(self):
        aset = [{"asset_code": "3050104001", "NUP": n} for n in ("10", "2", "9")]
        assert [a["NUP"] for a in urut_bmn(aset)] == ["2", "9", "10"]

    def test_kode_menang_atas_nup(self):
        aset = [{"asset_code": "3050104001", "NUP": "1"},
                {"asset_code": "3010102001", "NUP": "99"}]
        assert [a["asset_code"] for a in urut_bmn(aset)] == \
            ["3010102001", "3050104001"]

    def test_nup_bukan_angka_jatuh_ke_belakang(self):
        # "-" dan kosong tak boleh menyela deret angka di tengah daftar. Di
        # antara sesama non-angka urutannya mengikuti teks mentah (deterministik,
        # bukan acak): "" mendahului "-".
        aset = [{"asset_code": "3050104001", "NUP": n} for n in ("-", "3", "", "1")]
        assert [a["NUP"] for a in urut_bmn(aset)] == ["1", "3", "", "-"]

    def test_kode_dirapikan_dulu(self):
        # Artefak impor Excel (" 3050104001 ", "3050104001.0") harus disamakan
        # dengan kode bersihnya, bukan dianggap kode lain yang urutannya jauh.
        assert kunci_urut_bmn({"asset_code": " 3050104001 ", "NUP": "1"})[0] == \
            kunci_urut_bmn({"asset_code": "3050104001", "NUP": "1"})[0]

    def test_deterministik_dan_tak_memutasi(self):
        aset = [{"asset_code": "3050104001", "NUP": "-"},
                {"asset_code": "3050104001", "NUP": "-"}]
        asal = list(aset)
        urut_bmn(aset)
        assert aset == asal          # masukan utuh
        assert urut_bmn(aset) == urut_bmn(aset)   # dua cetakan sama urutannya

    def test_daftar_kosong_aman(self):
        assert urut_bmn([]) == []
        assert urut_bmn(None) == []


class TestDbhiPdf:
    def _teks(self, data):
        pypdf = pytest.importorskip("pypdf")
        r = pypdf.PdfReader(io.BytesIO(data))
        return len(r.pages), "\n".join(p.extract_text() for p in r.pages)

    def test_terurut_kode_lalu_nup_di_pdf(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_dbhi_pdf)(
                "k1", "kondisi-baik", _user=_USER))
            _, teks = self._teks(data)
            # Barang5 (kode terkecil) → Barang2 → Barang10 (NUP menaik).
            assert re.findall(r"Barang\d+", teks) == ["Barang5", "Barang2", "Barang10"]
        _jalan(skenario())

    def test_header_menyebut_nilai_perolehan(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_dbhi_pdf)(
                "k1", "kondisi-baik", _user=_USER))
            _, teks = self._teks(data)
            assert "Nilai Perolehan" in teks
            # Kolom tahun tetap terbaca utuh di sebelahnya (kolomnya dilebarkan
            # supaya "Perolehan" tak patah jadi "Peroleha"+"n").
            assert "Tahun\nPerolehan" in teks
        _jalan(skenario())

    def test_tetap_lanskap(self, monkeypatch):
        """DBHI punya 9–11 kolom; potret akan memerasnya. Hanya RHI yang potret."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_dbhi_pdf)(
                "k1", "kondisi-baik", _user=_USER))
            kotak = re.findall(rb"/MediaBox\s*\[([^\]]*)\]", data)[0].split()
            lebar, tinggi = float(kotak[2]), float(kotak[3])
            assert lebar > tinggi
        _jalan(skenario())


class TestDbhiDocx:
    def test_header_dan_urutan_sama_dengan_pdf(self, monkeypatch):
        docx = pytest.importorskip("docx")

        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_dbhi_docx)(
                "k1", "kondisi-baik", _user=_USER))
            d = docx.Document(io.BytesIO(data))
            tabel = [t for t in d.tables
                     if any("Kode Barang" in c.text for c in t.rows[0].cells)][0]
            header = [c.text for c in tabel.rows[0].cells]
            assert "Nilai Perolehan (Rp)" in header
            kolom_nama = header.index("Nama Barang")
            nama = [tabel.rows[i].cells[kolom_nama].text for i in range(1, 4)]
            assert nama == ["Barang5", "Barang2", "Barang10"]
        _jalan(skenario())


class TestRhiPotret:
    def test_pdf_potret_satu_halaman(self, monkeypatch):
        pypdf = pytest.importorskip("pypdf")

        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_rhi_pdf)(
                "k1", _user=_USER))
            kotak = re.findall(rb"/MediaBox\s*\[([^\]]*)\]", data)[0].split()
            lebar, tinggi = float(kotak[2]), float(kotak[3])
            assert tinggi > lebar, "RHI harus POTRET"
            assert len(pypdf.PdfReader(io.BytesIO(data)).pages) == 1
        _jalan(skenario())

    def test_docx_potret(self, monkeypatch):
        docx = pytest.importorskip("docx")

        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            data = await _isi(await _telanjangi(R.generate_rhi_docx)(
                "k1", _user=_USER))
            d = docx.Document(io.BytesIO(data))
            s = d.sections[0]
            assert s.page_height > s.page_width, "RHI Word harus POTRET"
        _jalan(skenario())
