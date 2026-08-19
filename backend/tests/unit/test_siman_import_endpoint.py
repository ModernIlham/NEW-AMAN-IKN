"""Impor SIMAN V2 dijalankan UTUH — bukan hanya potongan-potongannya.

Laporan pemilik dari lapangan: `POST /api/siman/import` menjawab 500 untuk
setiap file. Penyebabnya bukan isi file melainkan sambungan kode: ketika
parsing dipindahkan ke `_parse_siman_xlsx` supaya bisa berjalan di thread,
`peta_header` dan `sheet_dipakai` ikut pindah — sementara handler masih
membaca keduanya. Python baru mengeluh saat baris itu dijalankan, jadi setiap
impor berakhir NameError.

Yang membuatnya lolos sampai lapangan: seluruh uji SIMAN yang ada menguji
FUNGSI MURNI (petakan_header, parse_baris, banding_aset). Semuanya lulus —
yang putus justru sambungan di antaranya. Berkas ini menutup celah itu dengan
memanggil endpoint-nya sungguhan.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.siman as rs

ADMIN = {"username": "admin", "role": "admin", "name": "Admin", "kode_satker": ""}

HEADER = ["Kode Barang", "NUP", "Nama Barang", "Nilai Perolehan", "Merk",
          "Tipe", "Kondisi", "Tanggal Perolehan", "Nama Pengguna",
          "Kode Register", "Kode Satker", "Umur Aset", "Nilai Penyusutan",
          "Nilai Buku"]

BARIS = ["3100102001", "1", "Laptop", "15000000", "Lenovo", "T14", "Baik",
         "2024-03-01", "Budi", "REG-1", "621001", "7", "1000000", "14000000"]


def _xlsx(baris_list, header=HEADER, sheet="Master Aset"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for b in baris_list:
        ws.append(b)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class _FileUnggahan:
    """UploadFile secukupnya: handler hanya memakai `.filename` dan `.read()`."""

    def __init__(self, isi, nama="siman.xlsx"):
        self.filename = nama
        self._isi = isi

    async def read(self):
        return self._isi


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


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rs, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    return fake


async def _seed(dbx):
    await dbx.inventory_activities.insert_one(
        {"id": "keg1", "nama_kegiatan": "Inv", "kode_satker": ""})
    await dbx.assets.insert_one(
        # "Nama Barang" pada ekspor SIMAN dibandingkan dengan `category`
        # (lihat siman_utils.PERBANDINGAN), bukan dengan `asset_name`.
        {"id": "a1", "activity_id": "keg1", "asset_code": "3100102001",
         "NUP": "1", "category": "Laptop", "asset_name": "Laptop",
         "purchase_price": "15000000",
         "brand": "Lenovo", "model": "T14", "condition": "Baik",
         "purchase_date": "2024-03-01", "user": "Budi",
         "kode_satker": "", "version": 1})


async def _impor(dbx, baris_list=None, header=HEADER, **kw):
    return await _unwrap(rs.import_siman)(
        request=None, file=_FileUnggahan(_xlsx(baris_list or [BARIS], header)),
        tandai_tidak_ditemukan=kw.get("tandai_tidak_ditemukan", False),
        user=ADMIN)


class TestImporBerjalanUtuh:
    def test_file_sah_tidak_meledak(self, dbx):
        """Regresi langsung dari laporan lapangan: 500 untuk SETIAP file."""
        async def skenario():
            await _seed(dbx)
            hasil = await _impor(dbx)
            assert hasil["total_baris"] == 1
            assert hasil["ringkasan"]["aset_dicek"] == 1
        _jalan(skenario())

    def test_aset_yang_cocok_benar_benar_dikenali(self, dbx):
        async def skenario():
            await _seed(dbx)
            hasil = await _impor(dbx)
            assert hasil["ringkasan"]["cocok"] == 1, hasil["ringkasan"]
            aset = await dbx.assets.find_one({"id": "a1"})
            assert aset["siman"]["status"] == "cocok"
        _jalan(skenario())

    def test_sheet_yang_dibaca_ikut_dilaporkan(self, dbx):
        """`sheet_dipakai` adalah salah satu nama yang dulu menggantung —
        memastikan ia sampai ke respons berarti sambungannya benar-benar ada."""
        async def skenario():
            await _seed(dbx)
            hasil = await _impor(dbx)
            assert hasil["sheet"] == "Master Aset"
        _jalan(skenario())

    def test_kolom_hilang_dilaporkan_bukan_didiamkan(self, dbx):
        """`peta_header` adalah nama menggantung yang satunya. Tanpa peta itu
        peringatan kolom hilang mustahil disusun — dan hilangnya "Nilai
        Perolehan" berarti seluruh perbandingan nilai tak ada artinya."""
        async def skenario():
            await _seed(dbx)
            tanpa_nilai = [h for h in HEADER if h != "Nilai Perolehan"]
            baris = [b for h, b in zip(HEADER, BARIS) if h != "Nilai Perolehan"]
            hasil = await _impor(dbx, [baris], header=tanpa_nilai)
            gabung = " ".join(hasil["peringatan"])
            assert "tidak ditemukan di file" in gabung, hasil["peringatan"]
        _jalan(skenario())

    def test_riwayat_impor_tersimpan(self, dbx):
        async def skenario():
            await _seed(dbx)
            hasil = await _impor(dbx)
            reg = await dbx.siman_imports.find_one({"id": hasil["id"]})
            assert reg is not None
        _jalan(skenario())


class TestGalatTetapBerbicara:
    """Kegagalan yang bisa dijelaskan harus tetap 400 berpesan, bukan 500."""

    def test_header_tak_dikenali_jadi_400(self, dbx):
        async def skenario():
            from fastapi import HTTPException
            await _seed(dbx)
            with pytest.raises(HTTPException) as e:
                await _impor(dbx, [["a", "b"]], header=["Entah", "Apa"])
            assert e.value.status_code == 400
            assert "Header tidak dikenali" in str(e.value.detail)
        _jalan(skenario())

    def test_file_bukan_xlsx_ditolak(self, dbx):
        async def skenario():
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as e:
                await _unwrap(rs.import_siman)(
                    request=None, file=_FileUnggahan(b"x", "data.csv"),
                    tandai_tidak_ditemukan=False, user=ADMIN)
            assert e.value.status_code == 400
        _jalan(skenario())

    def test_file_kosong_ditolak_dengan_alasan(self, dbx):
        async def skenario():
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as e:
                await _unwrap(rs.import_siman)(
                    request=None, file=_FileUnggahan(b"", "siman.xlsx"),
                    tandai_tidak_ditemukan=False, user=ADMIN)
            assert e.value.status_code == 400
            assert "kosong" in str(e.value.detail)
        _jalan(skenario())
