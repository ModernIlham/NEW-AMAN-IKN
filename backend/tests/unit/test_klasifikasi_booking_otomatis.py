"""Klasifikasi arsip bisa DIPILIH saat memesan nomor otomatis lintas modul.

Keluhan pemilik: *"pada setiap penomeran yang dilakukan di modul lain yang akan
menggenerate output PDF, kode klasifikasi arsip tidak sesuai dengan apa yang
sudah disetting di format nomor… ketika buat BAST dan klik nomor otomatis dari
registrasi persuratan, bagian klasifikasi arsip tidak ada dan tidak ada pilihan
memilih klasifikasi arsip yang ada."*

Persis begitu keadaannya. Booking manual di Registrasi Persuratan punya TIGA
sumber kode — isian manual, aturan pemetaan, lalu kosong. Jalur otomatis lintas
modul (BAST, LPB, transaksi massal) hanya pernah punya SATU: aturan pemetaan.
Tak ada aturan yang cocok berarti slot `{kode_klasifikasi}` pada nomor terbit
kosong — tanpa galat, dan tanpa cara memperbaikinya dari layar tempat
dokumennya dibuat.

Urutan prioritasnya kini SAMA PERSIS dengan booking manual. Dua jalur
penerbitan dengan urutan berbeda akan melahirkan dua kebiasaan yang saling
membantah pada arsip yang sama.
"""
import ast
import asyncio
import pathlib

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.persuratan as rp

ADMIN = {"username": "admin", "role": "admin", "name": "Admin", "kode_satker": ""}
AKAR = pathlib.Path(__file__).resolve().parents[2]
FORMAT = "{kode_keamanan}-{urut}/{kode_klasifikasi}/{kode_unit}/{bulan_romawi}/{tahun}"


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
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)

    async def _diam(*a, **k):
        return None

    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    return fake


async def _atur(peta=None):
    return await _unwrap(rp.set_pengaturan_persuratan)(
        rp.PengaturanIn(format_nomor=FORMAT, kode_unit="OIKN",
                        kode_klasifikasi_default="SATKER-D",
                        peta_klasifikasi=peta or []), user=ADMIN)


class TestPilihanOperatorMenang:
    def test_kode_pilihan_masuk_ke_nomor_dan_ke_surat(self, dbx):
        async def skenario():
            await _atur()
            nomor, sid = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "LPB uji", kode_klasifikasi="PL.02")
            assert "/PL.02/" in nomor
            surat = await dbx.surat.find_one({"id": sid})
            assert surat["kode_klasifikasi"] == "PL.02"
        _jalan(skenario())

    def test_pilihan_operator_mengalahkan_aturan_pemetaan(self, dbx):
        """Urutan yang sama persis dengan booking manual."""
        async def skenario():
            await _atur(peta=[{"modul": "persediaan", "jenis_naskah": "",
                               "kode": "UM.01"}])
            nomor, _ = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "LPB uji", kode_klasifikasi="PL.02")
            assert "/PL.02/" in nomor and "UM.01" not in nomor
        _jalan(skenario())

    def test_tanpa_pilihan_aturan_pemetaan_tetap_bekerja(self, dbx):
        async def skenario():
            await _atur(peta=[{"modul": "persediaan", "jenis_naskah": "",
                               "kode": "UM.01"}])
            nomor, _ = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "LPB uji")
            assert "/UM.01/" in nomor
        _jalan(skenario())

    def test_tanpa_keduanya_slotnya_kosong_dan_kode_bawaan_tak_menyusup(self, dbx):
        """Kode bawaan berdiri sendiri (lihat test_klasifikasi_berdiri_sendiri)
        — jalur otomatis pun tak boleh menariknya diam-diam ke slot ini."""
        async def skenario():
            await _atur()
            nomor, sid = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "LPB uji")
            assert "SATKER-D" not in nomor
            surat = await dbx.surat.find_one({"id": sid})
            assert surat["kode_klasifikasi"] == ""
        _jalan(skenario())

    def test_lpb_meneruskan_pilihan_ke_jalur_yang_sama(self, dbx):
        """`booking_nomor_lpb` delegator — kalau ia lupa meneruskan, LPB jadi
        satu-satunya dokumen yang pemilihnya tak berpengaruh."""
        async def skenario():
            await _atur()
            nomor, _ = await rp.booking_nomor_lpb(
                ADMIN, "2026-08-19", "LPB uji", kode_klasifikasi="PL.02")
            assert "/PL.02/" in nomor
        _jalan(skenario())

    def test_deret_agenda_tetap_satu_meski_kodenya_berbeda(self, dbx):
        """Kode klasifikasi berbeda tak boleh memecah buku agenda keluar —
        selama nomor tak dipisah per kode (fitur deret_per_kode mati)."""
        async def skenario():
            await _atur()
            _, a = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "Satu", kode_klasifikasi="PL.02")
            _, b = await rp.booking_nomor_otomatis(
                ADMIN, "2026-08-19", "Dua", kode_klasifikasi="UM.01")
            sa = await dbx.surat.find_one({"id": a})
            sb = await dbx.surat.find_one({"id": b})
            assert sa["no_agenda"] == 1 and sb["no_agenda"] == 2
        _jalan(skenario())


class TestJalurBastMemakaiPilihan:
    def test_payload_bast_punya_kolomnya(self):
        import routes.bast as rb
        assert "kode_klasifikasi" in rb.BastIn.model_fields

    def test_payload_pengadaan_dan_persediaan_punya_kolomnya(self):
        import routes.pengadaan as rpg
        import routes.persediaan as rps
        for model in (rpg.BastPpkIn, rpg.LpbGabunganIn, rpg.CatatSemuaIn,
                      rps.TransaksiMassalIn):
            assert "kode_klasifikasi" in model.model_fields, model


class TestPemindaiJalurPenerbitan:
    """Setiap pemanggil `pilih_klasifikasi` WAJIB menyalurkan `eksplisit`.

    Inilah bentuk cacatnya yang bisa berulang: generator baru yang menyalin
    pola lama akan memanggil `pilih_klasifikasi(peta, modul, jenis)` saja —
    dan dokumennya jadi satu-satunya yang klasifikasinya tak bisa dipilih.
    Cacat itu tak terlihat dari uji perilaku mana pun sampai ada yang
    memakainya, karena jalurnya berjalan di balik centang opsional.
    """

    def _berkas(self):
        return sorted((AKAR / "routes").glob("*.py"))

    def test_pemindaiannya_menyapu_berkas_sungguhan(self):
        nama = {f.name for f in self._berkas()}
        assert {"persuratan.py", "bast.py", "pengadaan.py"} <= nama

    def test_semua_pemanggil_menyalurkan_eksplisit(self):
        lupa, ketemu = [], 0
        for f in self._berkas():
            pohon = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            for n in ast.walk(pohon):
                if not isinstance(n, ast.Call):
                    continue
                nama = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                if nama != "pilih_klasifikasi":
                    continue
                ketemu += 1
                if not any(kw.arg == "eksplisit" for kw in n.keywords):
                    lupa.append(f"{f.name}:{n.lineno}")
        assert ketemu >= 4, f"hanya {ketemu} pemanggil terlihat — pemindai buta?"
        assert lupa == []
