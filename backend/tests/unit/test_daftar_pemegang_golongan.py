"""Lampiran "Daftar Barang yang Digunakan" DIBAGI per bobot tanggung jawab.

Permintaan pemilik: *"bedakan dan bagi terhadap barang BMN BAST yang sudah
disahkan dan diunggah buktinya ... dibagi per jenis BAST-nya. Jika melekat ke
individu dan jabatan berarti memang menjadi tanggung jawabnya; untuk yang
operasional maka perpanjangan tangan atau jadi pendelegasian dan izin sesuai
nama-nama yang menjadi penanggung jawabnya dan ikut bertanggung jawab dalam
penjagaan barang tersebut. Dan jika dari awal digunakan untuk operasional dan
langsung menggunakan nama penandatangan maka hampir sama dengan tusinya."*

Dokumen ini diteken pemegang DAN KPB. Satu daftar datar menyamakan tiga hal
yang bobot hukumnya berbeda, dan tak ada galat apa pun yang memberitahunya —
karena itu pembagiannya dikunci di sini, bukan sekadar dipercayakan pada
fungsi murninya (yang diuji terpisah di test_golongan_tanggung_jawab.py).
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.penggunaan as rp

SATKER = "527010"
USER = {"username": "arsiparis", "role": "admin", "kode_satker": SATKER}
PEMEGANG = "Karina Lia Meirita Ulo"
NIP = "199005242025062002"


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    import routes.reports as rrep
    for mod in (rp, su, rrep):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "log_audit", _diam, raising=False)

    async def _lewat(query=None):
        return dict(query or {})
    monkeypatch.setattr(su, "filter_aset_perhitungan", _lewat, raising=False)
    return fake


def _teks_pdf(resp):
    import io
    import pypdfium2 as pdfium
    buf = io.BytesIO()

    async def kumpul():
        async for potong in resp.body_iterator:
            buf.write(potong if isinstance(potong, bytes) else potong.encode())
    _jalan(kumpul())
    pdf = pdfium.PdfDocument(buf.getvalue())
    try:
        return "\n".join(h.get_textpage().get_text_range() for h in pdf)
    finally:
        pdf.close()


def _aset(idx, nama, *, jenis=None, penerima=None, bukti="", nomor=""):
    a = {"id": f"a-{idx}", "asset_code": "3060102128", "NUP": str(idx),
         "asset_name": nama, "brand": "-", "model": "-", "serial_number": "-",
         "condition": "Baik", "location": "Kemenko 3 Tower 2",
         "user": PEMEGANG, "pengguna_nip": NIP,
         "pengguna_jabatan": "Perekayasa Ahli Pertama", "activity_id": "keg-1",
         "kode_satker": SATKER, "status_inventarisasi": "ditemukan",
         "bast_file_id": bukti}
    if jenis:
        a["bast_terakhir"] = {"id": f"b-{idx}", "jenis": jenis, "nomor": nomor,
                              "penerima": penerima or PEMEGANG,
                              "tt_dicabut": False}
    return a


async def _seed(dbx, aset):
    await dbx.inventory_activities.insert_one({
        "id": "keg-1", "kode_satker": SATKER,
        "status_pengesahan": "disahkan", "tanggal_selesai": "2026-07-01"})
    await dbx.report_settings.insert_one({
        "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
        "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
        "alamat_instansi": "Gedung Kantor Otorita IKN, Nusantara"})
    await dbx.kodefikasi.insert_one(
        {"kode": "306", "uraian": "Alat Studio, Komunikasi dan Pemancar"})
    await dbx.assets.insert_many(aset)


def _render(dbx, aset):
    async def skenario():
        await _seed(dbx, aset)
        return await _unwrap(rp.daftar_pemegang_pdf)(
            nama=PEMEGANG, nip=NIP, _user=USER)
    return _teks_pdf(_jalan(skenario()))


def test_tiga_bobot_tanggung_jawab_terpisah_dan_berurutan(dbx):
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat", bukti="f1"),
        _aset(2, "Printer Unit", jenis="operasional_unit",
              penerima="Sari Dewi", bukti="f2"),
        _aset(3, "Laptop Tusi", jenis="operasional_unit",
              penerima=PEMEGANG, bukti="f3"),
    ])
    assert "Melekat pada Pemegang" in teks
    assert "Operasional atas Nama Sendiri" in teks
    assert "Pendelegasian" in teks
    # Urutannya bukan selera: dari yang paling mengikat ke yang paling longgar.
    assert teks.index("Melekat pada Pemegang") < teks.index("Operasional atas Nama Sendiri")
    assert teks.index("Operasional atas Nama Sendiri") < teks.index("Pendelegasian")


def test_barang_tanpa_BAST_sah_dipisahkan_dan_dinyatakan_belum_membebani(dbx):
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat", bukti="f1"),
        _aset(2, "Kursi Tanpa Dasar", bukti=""),
    ])
    assert "Belum Ber-BAST Sah" in teks
    # Keterangannya yang menjaga penanda tangan: barang ini TETAP terdaftar
    # karena benar ada padanya, tetapi belum boleh dibebankan.
    assert "belum" in teks.lower()
    # Dan barangnya TIDAK hilang dari dokumen — menghapusnya membuat daftar
    # ini menyatakan lebih sedikit daripada yang benar-benar dipegang.
    assert "Kursi Tanpa Dasar" in teks


def test_ringkasan_menyebut_berapa_yang_berdasar_BAST_sah(dbx):
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat", bukti="f1"),
        _aset(2, "Kursi Tanpa Dasar", bukti=""),
        _aset(3, "Meja Tanpa Dasar", bukti=""),
    ])
    # 3 unit dipegang, 1 di antaranya berdasar BAST sah.
    assert "3" in teks and "disahkan" in teks


def test_penomoran_MENYAMBUNG_lintas_golongan(dbx):
    # Nomor pada lampiran ini dirujuk dari BAST induk dan berita acara lain,
    # jadi ia harus 1..N untuk seluruh barang — bukan mulai 1 lagi tiap
    # golongan, yang membuat dua baris berbeda memakai nomor yang sama.
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat", bukti="f1"),
        _aset(2, "Printer Unit", jenis="operasional_unit",
              penerima="Sari Dewi", bukti="f2"),
        _aset(3, "Kursi Tanpa Dasar", bukti=""),
    ])
    baris = [b.strip() for b in teks.splitlines()]
    # Tiga barang di TIGA golongan berbeda. Bila penomoran mengulang dari 1
    # tiap golongan, ketiganya bernomor "1" — jadi justru jumlah baris
    # bernomor 1 yang membuktikannya, bukan keberadaan nomor 3 saja.
    assert sum(1 for b in baris if b.startswith("1 ")) == 1, \
        "penomoran mengulang dari 1 di tiap golongan"
    assert any(b.startswith("3 ") for b in baris), \
        "nomor urut tidak menyambung sampai barang terakhir"


def test_kolom_BAST_memuat_NOMORnya_bukan_centang_belaka(dbx):
    # Sesudah dibagi per golongan, centang pada golongan ber-BAST sah SELALU
    # ✓ — kolom yang isinya selalu sama tak memberi tahu apa pun. Yang
    # dibutuhkan pembaca: dasar mana yang membebankan barang ini.
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat",
              bukti="f1", nomor="BA-77/OIKN/2026"),
    ])
    # Nomor panjang boleh TERLIPAT di dalam selnya — yang diuji ia tercetak,
    # bukan bahwa ia muat dalam satu baris.
    assert "BA-77/OIKN/2026" in "".join(teks.split())


def test_satu_golongan_saja_tetap_mencetak_judulnya(dbx):
    # Golongan tunggal pun butuh judul: pembaca harus tahu bobot apa yang
    # sedang ia teken, bukan menebaknya dari ketiadaan pembanding.
    teks = _render(dbx, [
        _aset(1, "Camera Digital", jenis="penggunaan_melekat", bukti="f1"),
    ])
    assert "Melekat pada Pemegang" in teks
    assert "Pendelegasian" not in teks


def test_pendelegasian_menerangkan_ikut_bertanggung_jawab_menjaga(dbx):
    # Inti permintaan pemilik: perpanjangan tangan TETAP ikut bertanggung
    # jawab menjaga, meski tanpa penguasaan pribadi.
    teks = _render(dbx, [
        _aset(1, "Printer Unit", jenis="operasional_unit",
              penerima="Sari Dewi", bukti="f2"),
    ])
    assert "ikut" in teks.lower()
    assert "perpanjangan tangan" in teks.lower()


class TestProyeksiMemuatYangDibaca:
    """Penjaga STRUKTURAL untuk kelalaian yang tak menimbulkan galat.

    `bast_terakhir` semula tidak ikut diproyeksikan, sehingga jenis BAST tak
    pernah sampai ke penggolong dan seluruh barang jatuh ke golongan "lain".
    Query tetap berhasil, tabel tetap tercetak — hanya isinya yang kosong.

    KOREKSI ATAS ALASAN PENJAGA INI. Semula ditulis di sini bahwa `mongomock`
    tak menghormati proyeksi sehingga uji render mustahil menangkapnya. Itu
    **salah**: mutasi yang seolah membuktikannya ternyata mengenai proyeksi
    fungsi LAIN di berkas yang sama (ada dua `"bast_terakhir": 1` di sana),
    jadi yang termutasi bukan fungsi yang diuji. Mencabut `bast_terakhir`
    dari proyeksi yang benar menggugurkan empat uji render.

    Penjaga ini tetap ada karena nilainya yang sebenarnya berbeda: uji render
    hanya menangkap field yang KEBETULAN sudah ada ujinya. Pembacaan BARU
    yang lupa diproyeksikan lolos semua uji render sampai seseorang menulis
    uji khusus untuknya — dan itu terbukti: mutasi "baca field baru tanpa
    memproyeksikannya" dibunuh HANYA oleh penjaga ini.
    """

    import ast as _ast
    import pathlib as _pathlib

    @classmethod
    def _sumber_fungsi(cls):
        berkas = cls._pathlib.Path(__file__).resolve().parents[2] / "routes" / "penggunaan.py"
        pohon = cls._ast.parse(berkas.read_text(encoding="utf-8"))
        for n in cls._ast.walk(pohon):
            if (isinstance(n, cls._ast.AsyncFunctionDef)
                    and n.name == "daftar_pemegang_pdf"):
                return n
        raise AssertionError("fungsi daftar_pemegang_pdf tak ditemukan")

    @classmethod
    def _proyeksi(cls):
        """Kunci proyeksi efektif: `_PROJ` + dict literal `proj` di fungsi."""
        import routes.penggunaan as rpen
        kunci = {k for k, v in rpen._PROJ.items() if v == 1}
        fn = cls._sumber_fungsi()
        for n in cls._ast.walk(fn):
            if (isinstance(n, cls._ast.Assign) and n.targets
                    and isinstance(n.targets[0], cls._ast.Name)
                    and n.targets[0].id == "proj"
                    and isinstance(n.value, cls._ast.Dict)):
                for k in n.value.keys:
                    if isinstance(k, cls._ast.Constant) and isinstance(k.value, str):
                        kunci.add(k.value)
        return kunci

    def test_setiap_field_aset_yang_DIBACA_ikut_diproyeksikan(self):
        """Diturunkan, bukan didaftar ulang: tiap `a.get("X")` di dalam fungsi
        wajib ada di proyeksi. Menambah pembacaan tanpa menambah proyeksinya
        akan gagal di sini, bukan diam-diam mencetak kosong."""
        fn = self._sumber_fungsi()
        proj = self._proyeksi()
        dibaca = set()
        for x in self._ast.walk(fn):
            if (isinstance(x, self._ast.Call)
                    and isinstance(x.func, self._ast.Attribute)
                    and x.func.attr == "get" and x.args
                    and isinstance(x.func.value, self._ast.Name)
                    and x.func.value.id == "a"
                    and isinstance(x.args[0], self._ast.Constant)
                    and isinstance(x.args[0].value, str)):
                dibaca.add(x.args[0].value)
        assert dibaca, "tak ada pembacaan a.get(...) — penjaga ini jadi hampa"
        kurang = dibaca - proj
        assert not kurang, (
            "dibaca tetapi tak diproyeksikan: " + ", ".join(sorted(kurang))
        )

    def test_field_yang_dibaca_PEMBANTU_ikut_diproyeksikan(self):
        """Yang tak bisa diturunkan: field yang dibaca fungsi pembantu
        (`_sel_bast`, `_sel_uraian_barang`, `kunci_pemegang`, `golongan_tj`)
        yang menerima dokumen aset hasil proyeksi ini. Didaftar eksplisit
        beserta pembacanya supaya jelas kenapa tiap nama ada di sini."""
        proj = self._proyeksi()
        pembaca = {
            "id": "kunci baris & bulk update",
            "asset_code": "kelompokkan_per_bidang, _sel_identitas_barang",
            "NUP": "kelompokkan_per_bidang, _sel_identitas_barang",
            "asset_name": "_sel_uraian_barang",
            "brand": "_sel_uraian_barang",
            "model": "_sel_uraian_barang",
            "serial_number": "_sel_uraian_barang",
            "location": "sel Lokasi",
            "condition": "sel Kondisi",
            "user": "kunci_pemegang, golongan_tj",
            "pengguna_nip": "kunci_pemegang",
            "bast_file_id": "bast_sah",
            "bast_terakhir": "golongan_tj (JENIS BAST) & _sel_bast (nomor)",
        }
        kurang = {k: v for k, v in pembaca.items() if k not in proj}
        assert not kurang, (
            "tak diproyeksikan padahal dibaca — "
            + "; ".join(f"{k} ({v})" for k, v in sorted(kurang.items()))
        )
