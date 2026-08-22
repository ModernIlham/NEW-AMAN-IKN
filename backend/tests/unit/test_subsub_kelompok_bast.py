"""Nama Sub-sub Kelompok benar-benar tercetak di tabel objek BAST.

Laporan pemilik, dengan tangkapan layar: judul kolomnya berbunyi
**"Identitas Barang (Sub-sub Kelompok · Kode · NUP)"** tetapi selnya hanya
memuat `3100102001 · NUP 1` — namanya tak ada.

Sebabnya ambang: nama sub-sub kelompok hanya dicetak bila tabel masih pendek
(dulu **6 baris**), demi batas dua halaman. BAST pemilik berisi 6 aset dalam
satu bidang = 7 baris — lewat satu baris saja, dan namanya lenyap. Judul
kolomnya tetap menjanjikannya, jadi pembaca mengira datanya hilang. Pada
dokumen resmi, mengira data hilang sama buruknya dengan data yang benar-benar
hilang.

Dua hal diperbaiki dan dijaga di sini:

1. Ambangnya DIUKUR ulang. Dengan sub-sub tercetak, 13 aset lintas 5 bidang
   (18 baris) masih dua halaman; 14 aset (19 baris) menembus halaman ketiga.
   Muatan wajib mandat 12 aset karena itu selalu membawa sub-sub kelompoknya.
2. JUDUL kolom mengikuti isi tabelnya. Bila memang dilepas, judulnya berhenti
   menjanjikan.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.bast as rb

SATKER = "527010"
USER = {"username": "arsiparis", "role": "admin", "kode_satker": SATKER}
# Kode uji + uraian sub-sub kelompoknya (kodefikasi TERDALAM yang terdaftar).
SUBSUB = {"3020104001": "Mini Bus (Penumpang 14 Orang Kebawah)",
          "3100102003": "Lap Top",
          "3050101001": "Mesin Ketik Manual Portable",
          "3060101001": "Camera Digital",
          "3080101001": "Alat Kesehatan Umum Lainnya"}
KODE = list(SUBSUB)


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
    for mod in (rb, su, rr):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


def _aset(n, bidang=None):
    """n aset; `bidang` membatasi berapa kode berbeda yang dipakai."""
    kode = KODE[:bidang] if bidang else KODE
    return [{"id": f"a{i}", "asset_code": kode[i % len(kode)],
             "NUP": str(i + 1),
             "asset_name": f"Barang Contoh Nama Agak Panjang {i + 1}",
             "brand": "Merk Contoh", "model": "Tipe-XYZ-2000",
             "serial_number": f"SN-{i:05d}", "condition": "Baik",
             "purchase_date": "2025-03-01", "purchase_price": 15_000_000 + i}
            for i in range(n)]


async def _pdf(dbx, aset, tampil_nilai=True):
    await dbx.report_settings.insert_one({
        "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
        "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
        "alamat_instansi": "Gedung Kantor Otorita IKN",
        "kasatker_nama": "Kasatker Uji", "kasatker_nip": "197001011990032001"})
    await dbx.kodefikasi.insert_many(
        [{"kode": k, "uraian": u} for k, u in SUBSUB.items()])
    await dbx.bast_serah_terima.insert_one({
        "id": "b-ss", "kode_satker": SATKER, "jenis": "penggunaan_melekat",
        "nomor": "BAST-001/PPTHD/VIII/2026", "tanggal": "2026-08-04",
        "pihak_pertama": {"nama": "Andi Penyerah",
                          "nip": "198206022001121003",
                          "jabatan": "Petugas Penatausahaan",
                          "alamat": "Gedung Kantor OIKN"},
        "pihak_kedua": {"nama": "Sari Penerima",
                        "nip": "199005242025062002",
                        "jabatan": "Analis", "alamat": "Gedung B Lt 2"},
        "asset_ids": [a["id"] for a in aset], "aset": aset,
        "saksi": [], "keterangan": "", "sertakan_foto": False,
        "tampilkan_nilai": tampil_nilai, "penyerah_atas_nama_kpb": True,
        "penanggung_jawab_tambahan": []})
    resp = await _unwrap(rb.bast_pdf)("b-ss", _user=USER)
    buf = io.BytesIO()
    async for potong in resp.body_iterator:
        buf.write(potong if isinstance(potong, bytes) else potong.encode())
    return buf.getvalue()


def _halaman(raw):
    pdfium = pytest.importorskip("pypdfium2")
    pdf = pdfium.PdfDocument(raw)
    try:
        return [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
    finally:
        pdf.close()


class TestNamaSubSubKelompokTercetak:
    def test_kasus_pemilik_enam_aset_satu_bidang(self, dbx):
        """Persis muatan pada tangkapan layar: 6 aset, satu bidang — 7 baris,
        dulu lewat ambang lama (6) dan namanya lenyap."""
        teks = " ".join(_halaman(_jalan(
            _pdf(dbx, _aset(6, bidang=1)))))
        assert "Mini Bus" in teks

    def test_muatan_wajib_dua_belas_aset_tetap_membawa_namanya(self, dbx):
        teks = " ".join(_halaman(_jalan(_pdf(dbx, _aset(12)))))
        for nama in ("Lap Top", "Camera Digital", "Mesin Ketik"):
            assert nama in teks, nama

    def test_masih_dua_halaman_pada_muatan_wajib(self, dbx):
        """Nama sub-sub menambah satu baris pada tiap sel identitas — batas
        dua halaman tetap berlaku, dan angkanya diukur bukan dikira."""
        hal = _halaman(_jalan(_pdf(dbx, _aset(12))))
        assert len(hal) <= 2, f"memakan {len(hal)} halaman"

    def test_tiga_belas_aset_juga_masih_muat(self, dbx):
        hal = _halaman(_jalan(_pdf(dbx, _aset(13))))
        assert len(hal) <= 2


class TestJudulKolomMengikutiIsinya:
    def test_menyebut_sub_sub_kelompok_saat_memang_memuatnya(self, dbx):
        teks = " ".join(_halaman(_jalan(_pdf(dbx, _aset(6, bidang=1)))))
        assert "Sub-sub Kelompok" in teks

    def test_BERHENTI_menjanjikan_saat_dilepas(self, dbx):
        """Tabel yang terlalu panjang melepas nama sub-sub demi batas dua
        halaman. Judul yang tetap menjanjikannya membuat pembaca mengira
        datanya hilang."""
        teks = " ".join(_halaman(_jalan(_pdf(dbx, _aset(30)))))
        assert "Sub-sub Kelompok" not in teks
        assert "(Kode · NUP)" in teks

    def test_ambang_diukur_dalam_BARIS_bukan_jumlah_aset(self, dbx):
        """Sekat bidang ikut memakan baris: 12 aset dalam 5 bidang = 17 baris,
        sedangkan 12 aset dalam 1 bidang = 13 baris. Mengukur dari jumlah aset
        saja membuat BAST ber-banyak bidang menembus halaman ketiga."""
        import inspect
        sumber = inspect.getsource(rb.bast_pdf)
        assert "len(daftar) + len(_klp) > _AMBANG_BARIS_SUBSUB" in sumber
