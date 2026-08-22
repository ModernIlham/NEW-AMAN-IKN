"""Dokumen pengadaan: SP/SPK, SPP/SPM, UP/TUP, SPBy, No Dokumen, dan sifatnya.

Permintaan pemilik: *"tambahan informasi mengenai no SP/SPK, SPP/SPM (validasi
agar sesuai pengertiannya…), UP/TUP, SPBY, No Dokumen. Dan tak lupa sifatnya
apakah kontrak/non kontrak."* — dengan pilihan **menolak kombinasi yang
bertentangan**, bukan sekadar memperingatkan.

Pembayaran belanja negara punya dua jalur yang dokumennya tidak bertukar:

    KONTRAK       SP/SPK → SPP-LS → SPM-LS
    NON-KONTRAK   UP/TUP → SPBy → (GUP: SPP-GUP → SPM-GUP)

SP/SPK pada register non-kontrak, atau UP/TUP dan SPBy pada register kontrak,
bukan sekadar tak lazim — ia menyatakan dua hal yang tak mungkin terjadi
bersamaan. SPP, SPM, dan No Dokumen berlaku di KEDUA jalur, jadi keduanya tak
pernah menjadi pertentangan.
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.pengadaan as rp
from pengadaan_dokumen import (
    DOKUMEN_PENGADAAN, JENIS_UP, KUNCI_DOKUMEN, MAKS_PANJANG_DOKUMEN,
    SIFAT_PENGADAAN, baris_dokumen, bersihkan_dokumen, bertentangan,
    milik_sifat, validate_dokumen,
)

ADMIN = {"username": "admin", "role": "admin", "kode_satker": ""}


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


class TestPembersihan:
    def test_hanya_kolom_dikenal_yang_diambil(self):
        d = bersihkan_dokumen({"no_spm": " X ", "rahasia": "bocor"})
        assert set(d) == set(KUNCI_DOKUMEN)
        assert d["no_spm"] == "X" and "rahasia" not in d

    def test_jenis_up_dinormalkan_huruf_kecil(self):
        assert bersihkan_dokumen({"jenis_up": "TUP"})["jenis_up"] == "tup"

    def test_tanpa_masukan_menghasilkan_kolom_kosong(self):
        assert bersihkan_dokumen(None) == {k: "" for k in KUNCI_DOKUMEN}


class TestMilikSifat:
    def test_kontrak_membawa_sp_spk_dan_yang_umum(self):
        m = milik_sifat("kontrak")
        assert "no_sp_spk" in m
        assert "jenis_up" not in m and "no_spby" not in m
        for k in ("no_spp", "no_spm", "no_dokumen"):
            assert k in m, k

    def test_non_kontrak_membawa_up_dan_spby(self):
        m = milik_sifat("non_kontrak")
        assert "jenis_up" in m and "no_spby" in m
        assert "no_sp_spk" not in m

    def test_kolom_umum_berlaku_di_kedua_jalur(self):
        umum = [d["kunci"] for d in DOKUMEN_PENGADAAN if not d["sifat"]]
        assert set(umum) == {"no_spp", "no_spm", "no_dokumen"}


class TestPertentanganDitolak:
    def test_spby_pada_kontrak_ditolak(self):
        e = validate_dokumen("kontrak", {"no_spby": "S-1"})
        assert len(e) == 1 and "Non-Kontrak" in e[0] and "SPBy" in e[0]

    def test_up_pada_kontrak_ditolak(self):
        assert validate_dokumen("kontrak", {"jenis_up": "up"}) != []

    def test_sp_spk_pada_non_kontrak_ditolak(self):
        e = validate_dokumen("non_kontrak", {"no_sp_spk": "SPK-1"})
        assert len(e) == 1 and "SP/SPK" in e[0]

    def test_kombinasi_yang_BENAR_lolos(self):
        assert validate_dokumen("kontrak", {
            "no_sp_spk": "SPK-1", "no_spp": "SPP-1", "no_spm": "SPM-1"}) == []
        assert validate_dokumen("non_kontrak", {
            "jenis_up": "tup", "no_spby": "S-1", "no_spm": "SPM-1"}) == []

    def test_sifat_BELUM_ditetapkan_tak_pernah_bertentangan(self):
        """Register lama tak punya kolom sifat sama sekali. Menuduhnya
        bertentangan hanya akan mengunci operator dari register yang sudah
        lama benar."""
        assert bertentangan("", {"no_sp_spk": "A", "no_spby": "B"}) == []
        assert validate_dokumen("", {"no_sp_spk": "A", "no_spby": "B"}) == []

    def test_sifat_asing_ditolak_dengan_pilihan_yang_sah(self):
        e = validate_dokumen("entah", {})
        assert len(e) == 1 and "kontrak" in e[0]

    def test_jenis_up_asing_ditolak(self):
        e = validate_dokumen("non_kontrak", {"jenis_up": "xxx"})
        assert any("up atau tup" in x for x in e)

    def test_terlalu_panjang_ditolak(self):
        e = validate_dokumen("", {"no_spm": "A" * (MAKS_PANJANG_DOKUMEN + 1)})
        assert len(e) == 1 and "terlalu panjang" in e[0]


class TestBarisCetak:
    def test_hanya_kolom_TERISI_yang_dicetak(self):
        """Blok yang separuhnya bertanda hubung membuat pembaca menghitung apa
        yang tak ada alih-alih membaca apa yang ada."""
        b = baris_dokumen("kontrak", {"no_sp_spk": "SPK-1"})
        label = [x[0] for x in b]
        assert label == ["Sifat Pengadaan", "No. SP/SPK"]

    def test_sifat_dicetak_dalam_bahasa_manusia(self):
        assert baris_dokumen("non_kontrak", {})[0] == ("Sifat Pengadaan", "Non-Kontrak")

    def test_up_tup_dicetak_kepanjangannya(self):
        b = dict(baris_dokumen("non_kontrak", {"jenis_up": "tup"}))
        assert b["UP/TUP"] == JENIS_UP["tup"]

    def test_tanpa_apa_pun_tak_menghasilkan_baris(self):
        assert baris_dokumen("", {}) == []


class TestGerbangEndpoint:
    async def _buat(self, **dok):
        payload = rp.PerolehanIn(
            jenis="pembelian", pihak="CV Uji", nomor_bast="BAST-1/2026",
            tanggal_bast="2026-08-01",
            barang=[rp.BarangIn(uraian="Laptop", kode="3100102001",
                                jumlah=1, harga_satuan=1_000_000)],
            **dok)
        return await _unwrap(rp.buat_perolehan)(payload, user=ADMIN)

    def test_kombinasi_bertentangan_ditolak_400(self, dbx):
        async def skenario():
            with pytest.raises(rp.HTTPException) as e:
                await self._buat(sifat="kontrak", no_spby="S-1")
            assert e.value.status_code == 400
            assert "SPBy" in e.value.detail
            assert await dbx.pengadaan.count_documents({}) == 0
        _jalan(skenario())

    def test_kombinasi_sah_tersimpan_apa_adanya(self, dbx):
        async def skenario():
            await self._buat(sifat="non_kontrak", jenis_up="up",
                             no_spby=" SPBy-9 ", no_spm="02847T/621001/2024")
            rec = await dbx.pengadaan.find_one({}, {"_id": 0})
            assert rec["sifat"] == "non_kontrak"
            assert rec["jenis_up"] == "up"
            assert rec["no_spby"] == "SPBy-9"        # spasi tepi dipangkas
            assert rec["no_spm"] == "02847T/621001/2024"
        _jalan(skenario())

    def test_model_membawa_seluruh_kolomnya(self):
        for m in (rp.PerolehanIn, rp.PerolehanUbahIn):
            assert "sifat" in m.model_fields, m
            for k in KUNCI_DOKUMEN:
                assert k in m.model_fields, (m, k)

    def test_sifat_yang_dikenal_hanya_dua(self):
        assert set(SIFAT_PENGADAAN) == {"kontrak", "non_kontrak"}
