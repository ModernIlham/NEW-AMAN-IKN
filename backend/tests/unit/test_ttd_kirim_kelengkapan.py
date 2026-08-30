"""ENDPOINT kirim tanda tangan menolak kiriman yang BELUM lengkap.

Laporan pemilik: satu penanda tangan hanya meneken satu lembar lalu menekan
Bubuhkan; lembar lain miliknya terbit kosong, dan karena tautan e-sign
sekali-pakai langsung tertutup, satu-satunya pemulihan adalah membatalkan
permintaan lalu meminta SEMUA orang meneken ulang.

Dua janji yang hanya terbukti dengan menjalankan handler-nya:

1. Kiriman kurang DITOLAK — dan penolakan itu tak boleh "menghanguskan"
   tautannya. Kalau statusnya terlanjur berubah, penolakan justru menciptakan
   kerusakan yang sama dengan yang hendak dicegah.
2. Penolakan tak meninggalkan berkas yatim di GridFS.
"""
import asyncio
import io

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _png_b64() -> str:
    import base64
    from PIL import Image
    buf = io.BytesIO()
    # Piksel BUKAN transparan penuh — `png_transparan_valid` menolak yang kosong.
    Image.new("RGBA", (60, 20), (10, 10, 120, 255)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class _Aliran:
    def __init__(self, catat):
        self._catat = catat

    async def write(self, data):
        self._catat.append(len(data))

    async def close(self):
        return None


class _Bucket:
    """Perekam GridFS: mencatat apakah blob PERNAH dibuka/dihapus."""

    def __init__(self):
        self.dibuka, self.dihapus = [], []

    def open_upload_stream_with_id(self, fid, filename, metadata=None):
        self.dibuka.append(str(fid))
        return _Aliran([])

    async def delete(self, fid):
        self.dihapus.append(str(fid))


class _Req:
    client = None


@pytest.fixture()
def sadapan(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    bucket = _Bucket()
    monkeypatch.setattr(rt, "db", fake, raising=False)
    monkeypatch.setattr(rt, "fs_bucket", bucket, raising=False)

    async def _diam(*a, **k):
        return None
    for nama in ("log_audit", "kirim_notifikasi_ttd_selesai"):
        if hasattr(rt, nama):
            monkeypatch.setattr(rt, nama, _diam, raising=False)
    return fake, bucket


async def _seed(fake, jumlah_ttd=2):
    await fake.signature_requests.insert_one({
        "id": "sr-1", "status": "menunggu", "judul": "BAST Uji",
        "kode_satker": "111111", "mode": "paralel", "dok_halaman": 4,
        "dok_file_id": "dok-1",
        "signers": [{"signer_id": "sg-1", "nama": "Sari", "nip": "1",
                     "jabatan": "PPK", "email": "", "urutan": 1,
                     "status": "aktif", "jti": "jti-1",
                     "jumlah_ttd": jumlah_ttd,
                     "signature_file_id": "", "hash": "", "signed_at": "",
                     "ip": ""}]})


def _tok():
    return {"sr": "sr-1", "signer": "sg-1", "jti": "jti-1"}


def _kirim(posisi, posisi_lain):
    return rt.SpesimenIn(png_base64=_png_b64(), posisi=posisi,
                         posisi_lain=posisi_lain)


def _pos(halaman):
    return {"halaman": halaman, "x": 0.5, "y": 0.7, "lebar": 0.25}


class TestKirimBelumLengkap:
    def test_kiriman_kurang_ditolak_400(self, sadapan):
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            with pytest.raises(rt.HTTPException) as e:
                await _unwrap(rt.kirim_tandatangan)(
                    "sr-1", _kirim(_pos(2), []), _Req(), tok=_tok())
            assert e.value.status_code == 400
            assert "2 tanda tangan" in str(e.value.detail)
            assert "Tanda tangan lagi" in str(e.value.detail)
        _jalan(skenario())

    def test_penolakan_TIDAK_menghanguskan_tautannya(self, sadapan):
        """Inti keselamatannya. Kalau status terlanjur berubah, penolakan
        justru menciptakan kerusakan yang sama dengan yang hendak dicegah —
        orang itu tak bisa mengulang, dan semua harus meneken dari awal."""
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            with pytest.raises(rt.HTTPException):
                await _unwrap(rt.kirim_tandatangan)(
                    "sr-1", _kirim(_pos(2), []), _Req(), tok=_tok())
            sr = await fake.signature_requests.find_one({"id": "sr-1"})
            sg = sr["signers"][0]
            assert sg["status"] == "aktif", "tautan hangus padahal ditolak"
            assert sg["jti"] == "jti-1", "jti berubah — link lama mati"
            assert sg["signature_file_id"] == ""
        _jalan(skenario())

    def test_penolakan_tak_meninggalkan_berkas_yatim(self, sadapan):
        fake, bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=3)
            with pytest.raises(rt.HTTPException):
                await _unwrap(rt.kirim_tandatangan)(
                    "sr-1", _kirim(_pos(2), [_pos(3)]), _Req(), tok=_tok())
            assert bucket.dibuka == [], "blob terlanjur diunggah sebelum diperiksa"
        _jalan(skenario())

    def test_kiriman_LENGKAP_diterima(self, sadapan):
        """Pembanding yang membuat uji di atas bermakna: penjaga yang menolak
        SEMUANYA juga akan melewatkan ketiga uji sebelumnya."""
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            await _unwrap(rt.kirim_tandatangan)(
                "sr-1", _kirim(_pos(2), [_pos(3)]), _Req(), tok=_tok())
            sr = await fake.signature_requests.find_one({"id": "sr-1"})
            sg = sr["signers"][0]
            assert sg["status"] == "menunggu_validasi"
            assert sr["status"] == "menunggu_validasi"
            assert [p["halaman"] for p in sg["posisi_ttd_lain"]] == [3]
        _jalan(skenario())

    def test_permintaan_LAMA_tanpa_jumlah_ttd_tetap_bisa_meneken_sekali(self, sadapan):
        """Permintaan yang sudah berjalan sebelum fitur ini ada tak boleh
        mendadak macet."""
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            await fake.signature_requests.update_one(
                {"id": "sr-1"}, {"$unset": {"signers.0.jumlah_ttd": ""}})
            await _unwrap(rt.kirim_tandatangan)(
                "sr-1", _kirim(_pos(2), []), _Req(), tok=_tok())
            sr = await fake.signature_requests.find_one({"id": "sr-1"})
            assert sr["signers"][0]["status"] == "menunggu_validasi"
        _jalan(skenario())

    def test_pembubuhan_LEBIH_dari_wajib_tetap_diterima(self, sadapan):
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            await _unwrap(rt.kirim_tandatangan)(
                "sr-1", _kirim(_pos(1), [_pos(2), _pos(3)]), _Req(), tok=_tok())
            sr = await fake.signature_requests.find_one({"id": "sr-1"})
            assert sr["signers"][0]["status"] == "menunggu_validasi"
        _jalan(skenario())

    def test_kiriman_kurang_dengan_deklarasi_masuk_antrean_validator(self, sadapan):
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=3)
            payload = _kirim(_pos(2), [])
            payload.deklarasi_tanpa_area = True
            payload.catatan_deklarasi = "Sudah memeriksa halaman 1 sampai 4"
            hasil = await _unwrap(rt.kirim_tandatangan)(
                "sr-1", payload, _Req(), tok=_tok())
            sr = await fake.signature_requests.find_one({"id": "sr-1"})
            sg = sr["signers"][0]
            assert hasil["menunggu_validasi"] is True
            assert sg["status"] == "menunggu_validasi"
            assert sg["deklarasi_tanpa_area"] is True
            assert sg["deklarasi_jumlah_aktual"] == 1
            assert sg["deklarasi_jumlah_diminta"] == 3
        _jalan(skenario())

    def test_entri_posisi_RUSAK_tak_terhitung_sebagai_pembubuhan(self, sadapan):
        """`_posisi_bersih_banyak` MEMBUANG entri cacat. Kalau kelengkapan
        dihitung dari kiriman mentah, entri rusak akan menyamar jadi
        pembubuhan yang sah dan lembarnya tetap terbit kosong."""
        fake, _bucket = sadapan

        async def skenario():
            await _seed(fake, jumlah_ttd=2)
            with pytest.raises(rt.HTTPException) as e:
                await _unwrap(rt.kirim_tandatangan)(
                    "sr-1", _kirim(_pos(2), [{"halaman": "bukan angka"}]),
                    _Req(), tok=_tok())
            assert e.value.status_code == 400
        _jalan(skenario())
