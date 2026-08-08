"""Kartu inventaris massal: CPU di thread, riwayat dua kueri — temuan C25b.

Dulu seluruh badan `get_bulk_asset_cards` (decode Pillow + QR + ReportLab,
±104 ms/kartu — 69 ms di antaranya ReportLab yang memegang GIL) berjalan di
event loop, plus 2N round-trip riwayat (find_one kegiatan + find riwayat per
aset). Terukur: 30 kartu = event loop beku 2,66 detik (5 detak); lewat thread
waktu dinding nyaris sama (+6%) tapi jeda detak maksimum 0,088 detik.

Yang paling berbahaya dari penulisan ulang ini BUKAN kinerjanya: saringan
satker riwayat pindah dari kueri Mongo ke Python. Itu batas KEAMANAN — salah
menyalin berarti riwayat satker lain tercetak di kartu FISIK satker ini,
tanpa galat, tanpa tanda. Kelompok uji satker di bawah menagihnya baris demi
baris, termasuk kelonggaran legacy (record tanpa kode_satker tetap ikut).
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.cards as rc


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def fake_db(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(rc, "db", fake, raising=False)
    return fake


def _aset(i, **isi):
    d = {"id": f"aset-{i}", "asset_code": f"30501{i:05d}", "NUP": str(i),
         "asset_name": f"Aset Uji {i}", "kode_register": f"REG{i:04d}",
         "activity_id": "keg-1", "category": "Peralatan"}
    d.update(isi)
    return d


class TestBentukSumber:
    SRC = None

    @classmethod
    def setup_class(cls):
        import pathlib
        cls.SRC = (pathlib.Path(rc.__file__)).read_text(encoding="utf-8")

    def test_helper_kartu_TETAP_sinkron(self):
        # Menjadikannya async menyembunyikan biaya di balik `await` yang
        # tampak murah — kerjanya tetap di event loop.
        assert "def _gambar_kartu_ke_kanvas(" in self.SRC
        assert "async def _gambar_kartu_ke_kanvas(" not in self.SRC
        assert "def _tutup_kanvas(" in self.SRC
        assert "async def _tutup_kanvas(" not in self.SRC

    def test_kedua_endpoint_lewat_thread_dan_c_save_hilang_dari_coroutine(self):
        import ast
        assert self.SRC.count("await asyncio.to_thread(") >= 3
        pohon = ast.parse(self.SRC)
        buruk = []
        for n in ast.walk(pohon):
            if not isinstance(n, ast.AsyncFunctionDef):
                continue
            for m in ast.walk(n):
                if (isinstance(m, ast.Call) and isinstance(m.func, ast.Attribute)
                        and m.func.attr == "save"
                        and isinstance(m.func.value, ast.Name)
                        and m.func.value.id == "c"):
                    buruk.append((n.name, m.lineno))
        assert buruk == [], buruk


class TestHalamanPdf:
    def _render_berblok(self, pasangan, blok):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas as rl_canvas
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=landscape(A4))
        for i in range(0, len(pasangan), blok):
            rc._gambar_kartu_ke_kanvas(c, pasangan[i:i + blok], i > 0)
        return rc._tutup_kanvas(c, buf)

    def test_jumlah_halaman_sama_dengan_jumlah_aset(self):
        """BLOK kecil (2) supaya batas blok BENAR-BENAR terlewati — mutasi
        `if idx:` (tanpa `sudah_ada_halaman or`) membuat kartu pertama tiap
        blok menimpa kartu terakhir blok sebelumnya: dua aset satu halaman,
        PDF tetap sah, baru ketahuan setelah dipotong dan ditempel."""
        pdfium = pytest.importorskip("pypdfium2")
        data = self._render_berblok([(_aset(i), []) for i in range(5)], blok=2)
        assert len(pdfium.PdfDocument(io.BytesIO(data))) == 5

    def test_aset_ke_i_ada_di_halaman_ke_i(self):
        pdfium = pytest.importorskip("pypdfium2")
        data = self._render_berblok([(_aset(i), []) for i in range(4)], blok=2)
        dok = pdfium.PdfDocument(io.BytesIO(data))
        for i in range(4):
            teks = dok[i].get_textpage().get_text_range()
            assert f"REG{i:04d}" in teks
        # NUP aset lain tak boleh nyasar ke halaman 0.
        teks0 = dok[0].get_textpage().get_text_range()
        assert "REG0003" not in teks0

    def test_kartu_tanpa_foto_tetap_terbit(self):
        pdfium = pytest.importorskip("pypdfium2")
        a = _aset(1)
        a.pop("photo", None)
        data = self._render_berblok([(a, [])], blok=25)
        dok = pdfium.PdfDocument(io.BytesIO(data))
        assert "FOTO ASET" in dok[0].get_textpage().get_text_range()


class TestRiwayatMassal:
    def _seed(self, fake_db, records, kegiatan=None):
        _jalan(fake_db.inventory_activities.insert_many(
            kegiatan or [{"id": "keg-1", "kode_satker": "111111"}]))
        if records:
            _jalan(fake_db.inventory_history.insert_many(records))

    def test_dua_kueri_untuk_lima_puluh_aset(self, fake_db, monkeypatch):
        self._seed(fake_db, [])
        panggilan = {"n": 0}
        for koleksi in ("inventory_history", "inventory_activities"):
            kls = type(getattr(fake_db, koleksi))
        asli_find = type(fake_db.inventory_history).find

        def _hitung(self, *a, **kw):
            if getattr(self, "name", "") in ("inventory_history",
                                             "inventory_activities"):
                panggilan["n"] += 1
            return asli_find(self, *a, **kw)
        monkeypatch.setattr(type(fake_db.inventory_history), "find", _hitung)

        async def _ranjau_find_one(self, *a, **kw):
            if getattr(self, "name", "") == "inventory_activities":
                raise AssertionError("N+1 find_one kegiatan masih hidup")
            return None
        monkeypatch.setattr(type(fake_db.inventory_activities), "find_one",
                            _ranjau_find_one)

        hasil = _jalan(rc._fetch_riwayat_massal([_aset(i) for i in range(50)]))
        assert isinstance(hasil, dict)
        assert panggilan["n"] <= 2

    def test_riwayat_tidak_bocor_lintas_satker(self, fake_db):
        self._seed(fake_db, [
            {"kode_register": "REG0001", "kode_satker": "111111", "t": "a"},
            {"kode_register": "REG0001", "kode_satker": "222222", "t": "b"},
            {"kode_register": "REG0001", "kode_satker": "", "t": "c"},
            {"kode_register": "REG0001", "t": "d"},  # tanpa field (legacy)
        ])
        hasil = _jalan(rc._fetch_riwayat_massal([_aset(1)]))
        satker = [h.get("kode_satker") for h in hasil["aset-1"]]
        assert "222222" not in satker
        assert len(hasil["aset-1"]) == 3  # 111111 + "" + tanpa field

    def test_dua_aset_identitas_sama_lingkup_satker_beda(self, fake_db):
        self._seed(fake_db, [
            {"kode_register": "SAMA", "kode_satker": "111111"},
            {"kode_register": "SAMA", "kode_satker": "222222"},
        ], kegiatan=[{"id": "keg-1", "kode_satker": "111111"},
                     {"id": "keg-2", "kode_satker": "222222"}])
        a1 = _aset(1, kode_register="SAMA", activity_id="keg-1")
        a2 = _aset(2, kode_register="SAMA", activity_id="keg-2")
        hasil = _jalan(rc._fetch_riwayat_massal([a1, a2]))
        assert [h["kode_satker"] for h in hasil["aset-1"]] == ["111111"]
        assert [h["kode_satker"] for h in hasil["aset-2"]] == ["222222"]

    def test_identitas_cadangan_asset_code_dan_NUP(self, fake_db):
        self._seed(fake_db, [
            {"asset_code": "AC1", "NUP": "5", "kode_satker": "111111"},
            {"asset_code": "AC1", "NUP": "6", "kode_satker": "111111"},
        ])
        a = _aset(1, kode_register="", asset_code="AC1", NUP="5")
        hasil = _jalan(rc._fetch_riwayat_massal([a]))
        assert len(hasil["aset-1"]) == 1
        assert hasil["aset-1"][0]["NUP"] == "5"

    def test_batas_delapan_dan_terbaru_dulu(self, fake_db):
        rec = [{"kode_register": "REG0001", "kode_satker": "111111",
                "tanggal_pengesahan": f"2026-01-{d:02d}", "ticket_number": "T1"}
               for d in range(1, 13)]
        self._seed(fake_db, rec)
        hasil = _jalan(rc._fetch_riwayat_massal([_aset(1)]))
        r = hasil["aset-1"]
        assert len(r) == 8
        assert r[0]["tanggal_pengesahan"] == "2026-01-12"
        assert r[0]["tanggal_pengesahan"] >= r[-1]["tanggal_pengesahan"]

    def test_identitas_kosong_tidak_menyapu_koleksi(self, fake_db):
        self._seed(fake_db, [{"asset_code": "", "NUP": "", "x": i}
                             for i in range(20)])
        a = _aset(1, kode_register="", asset_code="", NUP="")
        assert rc._identitas_aset(a) is None
        hasil = _jalan(rc._fetch_riwayat_massal([a]))
        assert hasil == {}

    def test_gagal_mongo_tetap_kembalikan_kosong(self, fake_db, monkeypatch):
        def _meledak(self, *a, **kw):
            raise RuntimeError("mongo tumbang")
        monkeypatch.setattr(type(fake_db.inventory_history), "find", _meledak)
        monkeypatch.setattr(type(fake_db.inventory_activities), "find", _meledak)
        hasil = _jalan(rc._fetch_riwayat_massal([_aset(1)]))
        assert hasil == {}
