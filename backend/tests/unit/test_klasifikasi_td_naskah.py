"""BMN "Tidak Ditemukan" yang sebabnya BELUM diteliti tidak boleh diperlakukan
sebagai barang hilang oleh naskah resmi.

Latar: satu aset yang baru ditandai "Tidak Ditemukan" — sebabnya belum
disimpulkan tim — dulu langsung dihitung sebagai "Tidak Ditemukan Lainnya".
Akibatnya Berita Acara merekomendasikan PENGHAPUSAN atas barang yang belum
diteliti, menagih Surat Keterangan Kepolisian, dan SPTJM bermeterai
menyatakan Kuasa Pengguna Barang telah meneliti barang yang belum diteliti.
Pada saat yang sama aset "Kesalahan Pencatatan" — yang barangnya ADA, hanya
catatannya keliru — ikut masuk SPTJM, sehingga dalam satu berkas unduhan SPTJM
dan Surat Koreksi menyatakan dua hal yang bertentangan tentang aset yang sama.

Uji di bawah merender PDF/Word-nya sungguhan lalu membaca teksnya kembali,
karena yang ditandatangani pejabat adalah berkasnya, bukan daftar di memori.
"""
import asyncio
import io
import re

import pytest
from mongomock_motor import AsyncMongoMockClient

_USER = {"username": "adm", "role": "admin", "kode_satker": ""}

# Satu aset per klasifikasi, harga dibedakan supaya salah-ember langsung
# kelihatan dari angka totalnya.
_SEED = [
    ("MejaSalah", "Kesalahan Pencatatan", 1000000),
    ("MejaHilang", "Tidak Ditemukan Lainnya", 5000000),
    ("MejaBelum", "", 9000000),
]


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _isi(resp):
    if hasattr(resp, "body_iterator"):
        return b"".join([c async for c in resp.body_iterator])
    return resp.body


def _telanjangi(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


async def _siapkan(monkeypatch, seed=_SEED):
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
    for i, (nama, klas, harga) in enumerate(seed):
        await fake.assets.insert_one({
            "id": f"a{i}", "activity_id": "k1", "asset_code": f"305010400{i}",
            "NUP": str(i + 1), "asset_name": nama,
            "inventory_status": "Tidak Ditemukan",
            "klasifikasi_tidak_ditemukan": klas,
            "condition": "Baik", "purchase_price": str(harga),
            "purchase_date": "2020-01-01", "location": "Gudang A"})
    return fake


def _teks(data):
    """Teks PDF dengan spasi/pemenggalan baris dinormalkan — pemenggalan baris
    di dalam sel tabel bukan bagian dari makna kalimatnya."""
    pypdf = pytest.importorskip("pypdf")
    r = pypdf.PdfReader(io.BytesIO(data))
    return re.sub(r"\s+", " ", "\n".join(p.extract_text() for p in r.pages))


def _teks_docx(data):
    docx = pytest.importorskip("docx")
    d = docx.Document(io.BytesIO(data))
    bagian = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            bagian.extend(c.text for c in row.cells)
    return re.sub(r"\s+", " ", "\n".join(bagian))


class TestBeritaAcara:
    def test_rekap_memisahkan_ember_ketiga(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks(await _isi(await _telanjangi(R.generate_berita_acara_pdf)(
                "k1", _user=_USER)))
            # a + b + c harus genap dengan baris "BMN Tidak Ditemukan" = 3.
            assert "c. Belum Diklasifikasi" in t
            assert "Rp 9.000.000" in t     # nilainya ikut dipisah, bukan ke b
            # Kolom Klasifikasi pada rincian menyebutnya, bukan "-".
            assert "Belum Diklasifikasi" in t
        _jalan(skenario())

    def test_belum_diteliti_tidak_direkomendasikan_dihapus(self, monkeypatch):
        """Hanya ada aset belum-diklasifikasi → BA tidak boleh mengusulkan
        penghapusan, tidak menagih surat kepolisian, tidak menyeret SPTJM."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, [("MejaBelum", "", 9000000)])
            t = _teks(await _isi(await _telanjangi(R.generate_berita_acara_pdf)(
                "k1", _user=_USER)))
            assert "usul PENGHAPUSAN" not in t
            assert "Kepolisian" not in t
            assert "MELANJUTKAN penelitian" in t
            assert "BELUM dapat diusulkan penghapusan" in t
            assert "Kertas kerja penelitian lanjutan" in t
        _jalan(skenario())

    def test_yang_benar_hilang_tetap_diusulkan_hapus(self, monkeypatch):
        """Jangan sampai perbaikan ini justru membungkam kasus yang memang
        harus diusulkan penghapusan."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, [("MejaHilang", "Tidak Ditemukan Lainnya", 5000000)])
            t = _teks(await _isi(await _telanjangi(R.generate_berita_acara_pdf)(
                "k1", _user=_USER)))
            assert "usul PENGHAPUSAN" in t
            assert "Kepolisian" in t
            # tanpa aset belum-diklasifikasi, baris c tidak dicetak
            assert "c. Belum Diklasifikasi" not in t
        _jalan(skenario())

    def test_docx_sejalan_dengan_pdf(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks_docx(await _isi(await _telanjangi(R.generate_berita_acara_docx)(
                "k1", _user=_USER)))
            assert "c. Belum Diklasifikasi" in t
            assert "MELANJUTKAN penelitian" in t
        _jalan(skenario())


class TestSptjm:
    def test_hanya_memuat_yang_benar_benar_hilang(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks(await _isi(await _telanjangi(R.generate_sptjm_pdf)(
                "k1", _user=_USER)))
            assert "MejaHilang" in t
            # Kesalahan pencatatan ditangani Surat Koreksi; belum-diteliti belum
            # boleh dinyatakan hilang di atas meterai.
            assert "MejaSalah" not in t
            assert "MejaBelum" not in t
            assert "1 NUP BMN" in t
            assert "Rp 5.000.000" in t
            assert "Rp 15.000.000" not in t   # bukan total seluruh tidak-ditemukan
        _jalan(skenario())

    def test_menyebut_apa_yang_tidak_dicakup(self, monkeypatch):
        """Selisih angka dengan RHI/BAHI harus dijelaskan di suratnya sendiri,
        bukan menjadi teka-teki bagi pemeriksa."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks(await _isi(await _telanjangi(R.generate_sptjm_pdf)(
                "k1", _user=_USER)))
            assert "Tidak termasuk dalam pernyataan ini" in t
            assert "1 NUP berklasifikasi Kesalahan Pencatatan" in t
            assert "1 NUP yang klasifikasi sebabnya belum ditetapkan" in t
            # Angka utama surat harus konsisten dengan catatan itu: 1 dicakup,
            # 1+1 dikecualikan, dari 3 NUP tidak-ditemukan di kegiatan ini.
            assert "terdapat 1 NUP BMN dengan total nilai Rp 5.000.000" in t
            assert "terdapat 3 NUP BMN" not in t
        _jalan(skenario())

    def test_tanpa_pengecualian_tanpa_catatan(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch, [("MejaHilang", "Tidak Ditemukan Lainnya", 5000000)])
            t = _teks(await _isi(await _telanjangi(R.generate_sptjm_pdf)(
                "k1", _user=_USER)))
            assert "Tidak termasuk dalam pernyataan ini" not in t
            assert "MejaHilang" in t
        _jalan(skenario())

    def test_docx_sejalan_dengan_pdf(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks_docx(await _isi(await _telanjangi(R.generate_sptjm_docx)(
                "k1", _user=_USER)))
            assert "MejaHilang" in t
            assert "MejaSalah" not in t
            assert "MejaBelum" not in t
            assert "Tidak termasuk dalam pernyataan ini" in t
        _jalan(skenario())


class TestSuratKoreksiTetapUtuh:
    def test_hanya_memuat_kesalahan_pencatatan(self, monkeypatch):
        """Pasangan SPTJM: cakupannya tidak boleh ikut bergeser."""
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            t = _teks(await _isi(await _telanjangi(R.generate_surat_koreksi_pdf)(
                "k1", _user=_USER)))
            assert "MejaSalah" in t
            assert "MejaHilang" not in t
            assert "MejaBelum" not in t
        _jalan(skenario())


class TestRekapitulasiApi:
    def test_tiga_ember_genap_dengan_total(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await _siapkan(monkeypatch)
            d = await _telanjangi(R.get_rekapitulasi)("k1", _user=_USER)
            td = d["tidak_ditemukan"]
            assert td["count"] == 3
            assert (td["kesalahan_pencatatan"]["count"]
                    + td["tidak_ditemukan_lainnya"]["count"]
                    + td["belum_diklasifikasi"]["count"]) == td["count"]
            assert td["belum_diklasifikasi"]["count"] == 1
            assert td["belum_diklasifikasi"]["value"] == 9000000
        _jalan(skenario())


class TestRekapTemuanPencatatan:
    """Rekap temuan pencatatan lapangan.

    Yang paling mudah salah di sini: menghitungnya hanya dari aset yang TIDAK
    DITEMUKAN. Itu justru membalik gunanya — cacat pencatatan paling sering
    dijumpai pada barang yang KETEMU (kode tak sesuai fisik, stiker tertempel
    di barang lain), dan rekap yang melewatkannya akan selalu menampilkan nol
    pada kegiatan yang sebenarnya penuh temuan.
    """

    async def _siapkan_temuan(self, monkeypatch):
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
        baris = [
            # (status inventarisasi, temuan, harga)
            ("Ditemukan", "Kodefikasi Tidak Sesuai Fisik", 1000000),
            ("Ditemukan", "Stiker Tertempel di Barang Lain", 2000000),
            ("Ditemukan", "Stiker Tertempel di Barang Lain", 3000000),
            ("Tidak Ditemukan", "Kodefikasi Tidak Sesuai Fisik", 4000000),
            ("Ditemukan", "", 9000000),        # tanpa temuan
            ("Ditemukan", "Nilai Lawas Entah", 5000000),  # di luar daftar baku
        ]
        for i, (inv, temuan, harga) in enumerate(baris):
            await fake.assets.insert_one({
                "id": f"a{i}", "activity_id": "k1", "asset_code": f"30501040{i:02d}",
                "NUP": str(i + 1), "asset_name": f"Barang{i}",
                "inventory_status": inv, "temuan_pencatatan": temuan,
                "condition": "Baik", "purchase_price": str(harga),
                "purchase_date": "2020-01-01", "location": "Gudang A"})
        return fake

    def test_menghitung_juga_aset_yang_ditemukan(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await self._siapkan_temuan(monkeypatch)
            t = (await _telanjangi(R.get_rekapitulasi)("k1", _user=_USER))["temuan_pencatatan"]
            # 5 dari 6 aset punya temuan; satu di antaranya berstatus Ditemukan
            # dan satu lagi Tidak Ditemukan — keduanya wajib ikut terhitung.
            assert t["count"] == 5
            assert t["value"] == 15000000
        _jalan(skenario())

    def test_pecahan_per_jenis_benar(self, monkeypatch):
        async def skenario():
            import routes.reports as R
            await self._siapkan_temuan(monkeypatch)
            per = (await _telanjangi(R.get_rekapitulasi)(
                "k1", _user=_USER))["temuan_pencatatan"]["per_jenis"]
            assert per["Stiker Tertempel di Barang Lain"]["count"] == 2
            assert per["Stiker Tertempel di Barang Lain"]["value"] == 5000000
            assert per["Kodefikasi Tidak Sesuai Fisik"]["count"] == 2
        _jalan(skenario())

    def test_jenis_tanpa_temuan_tetap_dibawa(self, monkeypatch):
        """Kategori yang ada tapi belum terpakai harus tetap terlihat, supaya
        operator tahu pilihannya ada — bukan mengira kategorinya hilang."""
        async def skenario():
            import routes.reports as R
            from shared_utils import VALID_TEMUAN_PENCATATAN
            await self._siapkan_temuan(monkeypatch)
            per = (await _telanjangi(R.get_rekapitulasi)(
                "k1", _user=_USER))["temuan_pencatatan"]["per_jenis"]
            for jenis in VALID_TEMUAN_PENCATATAN:
                assert jenis in per
            assert per["NUP Ganda pada Fisik Berbeda"]["count"] == 0
        _jalan(skenario())

    def test_nilai_di_luar_daftar_baku_tak_raib(self, monkeypatch):
        """Data lama / hasil impor bisa memuat nilai di luar daftar. Kalau
        dibuang diam-diam, jumlah per-jenis tak lagi genap dengan totalnya."""
        async def skenario():
            import routes.reports as R
            await self._siapkan_temuan(monkeypatch)
            t = (await _telanjangi(R.get_rekapitulasi)("k1", _user=_USER))["temuan_pencatatan"]
            assert t["per_jenis"]["(di luar daftar baku)"]["count"] == 1
            assert sum(v["count"] for v in t["per_jenis"].values()) == t["count"]
        _jalan(skenario())
