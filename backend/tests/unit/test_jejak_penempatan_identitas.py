"""Satu simpanan aset tidak boleh tampil sebagai dua suntingan oleh dua orang.

Laporan pemilik: saat mencatat, panel Riwayat memperlihatkan DUA baris "Edit"
untuk aset yang sama — satu menyebut nama pengguna, satu menyebut alamat
surelnya. Penyebabnya bukan tulisan ganda:

1. Baris kedua sebenarnya PENEMPATAN DENAH OTOMATIS (`aset_lokasi_otomatis`),
   yang lahir dari koordinat GPS pada simpanan yang sama. Aksinya tidak
   terdaftar di `ACTION_MAP` panel, jadi jatuh ke label cadangan "Edit".
2. Jalur audit aset memakai nama tampilan, sedangkan `catat_penempatan`
   diberi `username` (alamat login) — satu orang, dua ejaan.
3. NUP tidak ikut dikirim, sehingga baris itu tampak membicarakan barang lain.

Uji di bawah mengunci ketiganya di sisi backend. Label panelnya dijaga uji
frontend `AuditLogPanel.test.js`.
"""
import asyncio
import ast
import os

import pytest
from mongomock_motor import AsyncMongoMockClient

import spasial_penempatan as sp
from shared_utils import nama_pelaku

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _sumber(*bagian):
    with open(os.path.join(BACKEND, *bagian), encoding="utf-8") as f:
        return f.read()


def _fungsi(src: str, nama: str) -> str:
    for simpul in ast.walk(ast.parse(src)):
        if (isinstance(simpul, (ast.FunctionDef, ast.AsyncFunctionDef))
                and simpul.name == nama):
            return ast.get_source_segment(src, simpul) or ""
    raise AssertionError(f"fungsi {nama} tidak ditemukan")


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_ASET = {"id": "a1", "activity_id": "k1", "asset_code": "3100204023",
         "NUP": "16", "asset_name": "ARUBA Instant On AP25"}
_LOKASI = {"node_id": "n1", "node_nama": "Ruang 305",
           "jalur_nama": "Gedung A / Lantai 3 / Ruang 305"}
_EMAIL = "arif.fahmirridho@gmail.com"
_NAMA = "Arif Fahmirridho"


class TestNamaPelaku:
    def test_nama_menang_atas_alamat_login(self):
        assert nama_pelaku({"name": _NAMA, "username": _EMAIL}) == _NAMA

    def test_jatuh_ke_alamat_login_bila_nama_kosong(self):
        assert nama_pelaku({"name": "", "username": _EMAIL}) == _EMAIL
        assert nama_pelaku({"username": _EMAIL}) == _EMAIL

    def test_masukan_kosong_aman(self):
        assert nama_pelaku({}) == ""
        assert nama_pelaku(None) == ""


class TestJejakPenempatan:
    """`catat_penempatan` menulis DUA hal dengan dua identitas berbeda —
    sengaja: jejak audit dibaca manusia, custody adalah identitas tetap."""

    async def _rekam(self, monkeypatch, **kw):
        import shared_utils as su
        fake = AsyncMongoMockClient()["uji"]
        monkeypatch.setattr(sp, "db", fake, raising=False)
        monkeypatch.setattr(su, "db", fake, raising=False)
        await sp.catat_penempatan(_ASET, _LOKASI, _EMAIL, "2026-08-16", **kw)
        audit = await fake.audit_logs.find_one({}, {"_id": 0})
        riwayat = await fake.riwayat_lokasi_aset.find_one({}, {"_id": 0})
        return audit, riwayat

    def test_audit_memakai_nama_custody_tetap_alamat_login(self, monkeypatch):
        async def skenario():
            audit, riwayat = await self._rekam(monkeypatch, nama_audit=_NAMA)
            assert audit["username"] == _NAMA
            # Custody TIDAK ikut berubah — alamat login adalah identitas
            # tetap di riwayat lokasi, sama seperti penempatan manual.
            assert riwayat["oleh"] == _EMAIL
        _jalan(skenario())

    def test_nup_ikut_supaya_menunjuk_barang_yang_sama(self, monkeypatch):
        async def skenario():
            audit, _ = await self._rekam(monkeypatch, nama_audit=_NAMA)
            assert audit["nup"] == "16"
            assert audit["asset_code"] == "3100204023"
        _jalan(skenario())

    def test_aksinya_bukan_update(self, monkeypatch):
        """Kalau aksinya "update", panel akan menampilkannya sebagai "Edit"
        SEKALIPUN ACTION_MAP sudah dilengkapi."""
        async def skenario():
            audit, _ = await self._rekam(monkeypatch, nama_audit=_NAMA)
            assert audit["action"] == "aset_lokasi_otomatis"
            # Keterangannya berisi jalur lokasi — itulah yang membedakan
            # baris ini dari baris suntingan di panel.
            assert audit["detail"] == _LOKASI["jalur_nama"]
        _jalan(skenario())

    def test_satu_simpanan_satu_ejaan_pelaku(self, monkeypatch):
        """Gejala yang dilaporkan pemilik, ditiru apa adanya: satu simpanan
        aset menulis DUA baris jejak (suntingan + penempatan otomatis). Kedua
        baris harus menyebut pelakunya dengan ejaan yang SAMA — kalau tidak,
        panel Riwayat terbaca seperti dua orang mengerjakan satu aset."""
        async def skenario():
            import shared_utils as su
            fake = AsyncMongoMockClient()["uji"]
            monkeypatch.setattr(sp, "db", fake, raising=False)
            monkeypatch.setattr(su, "db", fake, raising=False)
            pengguna = {"name": _NAMA, "username": _EMAIL}
            # Baris 1 — persis yang ditulis jalur PATCH/PUT/POST aset.
            await su.log_audit("update", "k1", _ASET["id"], _ASET["asset_code"],
                               _ASET["asset_name"], nama_pelaku(pengguna),
                               changes=[{"field": "condition",
                                         "from": "Baik", "to": "Rusak Ringan"}],
                               nup=_ASET["NUP"])
            # Baris 2 — penempatan otomatis dari koordinat simpanan yang sama.
            await sp.catat_penempatan(_ASET, _LOKASI, pengguna["username"],
                                      "2026-08-16",
                                      nama_audit=nama_pelaku(pengguna))
            baris = await fake.audit_logs.find({}, {"_id": 0}).to_list(10)
            assert len(baris) == 2
            assert {b["username"] for b in baris} == {_NAMA}
            # …dan menunjuk NUP yang sama, supaya tak terbaca sebagai dua barang.
            assert {b["nup"] for b in baris} == {"16"}
            # Aksinya tetap berbeda — panel harus bisa memberi label berbeda.
            assert {b["action"] for b in baris} == {"update", "aset_lokasi_otomatis"}
        _jalan(skenario())

    def test_tanpa_nama_audit_perilaku_lama_utuh(self, monkeypatch):
        async def skenario():
            audit, riwayat = await self._rekam(monkeypatch)
            assert audit["username"] == _EMAIL
            assert riwayat["oleh"] == _EMAIL
        _jalan(skenario())


class TestWiringTerpasang:
    """Perbaikan ini mudah hilang tanpa disadari: `nama_audit` opsional, jadi
    call site yang lupa mengirimnya tetap jalan — dan diam-diam kembali
    menulis alamat surel."""

    @pytest.mark.parametrize("nama", ["patch_asset", "create_asset", "update_asset"])
    def test_ketiga_jalur_tulis_aset_mengirim_nama_audit(self, nama):
        fn = _fungsi(_sumber("routes", "assets.py"), nama)
        i = fn.index("sp.catat_penempatan(")
        # Cari argumennya di dalam pemanggilan itu, bukan di mana pun di fungsi.
        potongan = fn[i:i + 400]
        assert "nama_audit=nama_pelaku(_user)" in potongan, nama

    def test_penempatan_manual_juga_memakai_nama(self):
        """Panel yang sama menampilkan penempatan manual. Kalau jalur itu
        tetap menulis alamat surel, ejaan gandanya cuma pindah tempat."""
        src = _sumber("routes", "spasial.py")
        fn = _fungsi(src, "set_lokasi_aset")
        assert 'username=nama_pelaku(_user) or "system"' in fn
        # Custody-nya justru TIDAK boleh ikut berubah.
        assert "entri_riwayat_lokasi(asset_id, lokasi_lama, lokasi,\n" \
               "                                    username, now)" in fn
        assert fn.count("nup=str(aset.get(\"NUP\") or \"\")") == 2
