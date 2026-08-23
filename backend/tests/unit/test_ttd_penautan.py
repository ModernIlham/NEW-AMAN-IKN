"""Dokumen ↔ permintaan TTD saling tertaut — satu pintu, tanpa modul yang lupa.

Laporan pemilik: *"Riwayat BAST di bagian kirim tanda tangan selalu berakhir
dengan TTD sudah kedaluwarsa dan seperti tidak terhubung dengan modul TTD
elektronik."*

Sebabnya terukur: BAST adalah SATU-SATUNYA pintu "Kirim ke TTD" yang tidak
menulis tautan MAJU saat permintaan dibuat. LPB menulisnya, kedua permohonan
persetujuan menulisnya. Akibatnya Riwayat BAST tak pernah tahu permintaan
sudah dikirim; tautannya hilang bersama dialog, dan yang tersisa
berminggu-minggu kemudian di modul TTD hanya "tautan mati".
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.bast as rb
import routes.ttd as rt
import shared_utils as su
import tautan_pendek_utils as tp
import ttd_penautan as tpn

USER = {"username": "op", "role": "admin", "kode_satker": "111111"}


async def _diam(*a, **k):
    return None


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def _buka(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    for mod in (rb, rt, su, tp, tpn):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "send_esign_email", _diam, raising=False)
    return fake


def _bast(bid="bast-1"):
    return {"id": bid, "kode_satker": "111111", "nomor": f"{bid}/2026",
            "tanggal": "2026-08-01", "jenis": "operasional", "asset_ids": [],
            "pihak_pertama": {"nama": "Budi", "nip": "197001011990031001",
                              "jabatan": "Pengurus Barang"},
            "pihak_kedua": {"nama": "Sari", "nip": "198002022005022002",
                            "jabatan": "Pemegang"}}


def _sr(sr_id="sr-1", doc_ref="bast-1", signers=None, status="terkirim",
        created="2026-08-01T00:00:00+00:00"):
    return {"id": sr_id, "doc_type": "bast", "doc_ref": doc_ref,
            "judul": "BAST bast-1/2026", "status": status,
            "created_at": created, "signers": signers or []}


def _signer(status="aktif", sisa_hari=10):
    exp = (datetime.now(timezone.utc) + timedelta(days=sisa_hari)).isoformat()
    return {"signer_id": f"s-{status}-{sisa_hari}", "nama": "X",
            "status": status, "token_exp": exp}


class TestRegistriSatuPintu:
    def test_semua_doc_type_yang_menulis_tautan_maju_terdaftar(self):
        """Registry inilah yang menyalakan gerbang kepemilikan sekaligus
        penautan. `doc_type` yang tercecer kehilangan keduanya diam-diam."""
        assert set(tpn.TAUT_TTD) == {"bast", "lpb", "persetujuan_aset",
                                     "persetujuan_persediaan"}

    def test_tiap_entri_menyebut_koleksi_dan_label(self):
        for k, v in tpn.TAUT_TTD.items():
            assert v["koleksi"].strip(), k
            assert v["label"].strip(), k
            assert isinstance(v["backlink"], bool), k

    def test_gerbang_kepemilikan_memakai_registry_yang_sama(self):
        """Dulu daftarnya ditulis ulang di routes/ttd.py. Uji ini menagih agar
        tak ada daftar kedua yang bisa berselisih."""
        teks = (tpn.__file__ and open(rt.__file__, encoding="utf-8").read())
        assert "_KOLEKSI_BER_BACKLINK" not in teks
        assert "TAUT_TTD" in teks


class TestTautanMajuDitulisSaatDIKIRIM:
    def test_bast_tertaut_begitu_permintaan_dibuat(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
            b = await dbx.bast_serah_terima.find_one({"id": "bast-1"}, {"_id": 0})
            # INTI PERBAIKAN: tertaut SEKARANG, bukan nanti setelah semua teken.
            assert b["signature_request_id"] == hasil["id"]
            assert b["tt_dikirim_pada"]
        _jalan(skenario())

    def test_doc_type_tak_terdaftar_tidak_menggagalkan_permintaan(self, dbx):
        """Dokumen unggahan bebas memang tak bertaut — dan itu bukan galat."""
        async def skenario():
            assert await tpn.catat_pengiriman_ttd(dbx, "dokumen", "x", "sr-1") is False
            assert await tpn.catat_pengiriman_ttd(dbx, "bast", "", "sr-1") is False
        _jalan(skenario())


class TestRingkasStatus:
    def test_menunggu_menyebut_kemajuan(self):
        r = tpn.ringkas_status_ttd(_sr(signers=[
            _signer("ditandatangani"), _signer("aktif")]))
        assert r["jumlah"] == 2 and r["selesai_jumlah"] == 1
        assert r["semua_selesai"] is False
        assert r["perlu_terbit_ulang"] is False

    def test_semua_selesai(self):
        r = tpn.ringkas_status_ttd(_sr(signers=[
            _signer("ditandatangani"), _signer("ditandatangani")]))
        assert r["semua_selesai"] is True
        assert r["perlu_terbit_ulang"] is False

    def test_tautan_mati_TAPI_belum_lengkap_perlu_terbit_ulang(self):
        """Justru inilah keadaan yang dilaporkan pemilik — dan ia BUKAN jalan
        buntu: tautannya bisa diterbitkan ulang."""
        r = tpn.ringkas_status_ttd(_sr(signers=[_signer("aktif", sisa_hari=-1)]))
        assert r["perlu_terbit_ulang"] is True

    def test_permintaan_dibatalkan_tidak_menyuruh_terbit_ulang(self):
        r = tpn.ringkas_status_ttd(
            _sr(signers=[_signer("aktif", sisa_hari=-1)], status="batal"))
        assert r["perlu_terbit_ulang"] is False

    def test_yang_sudah_lengkap_walau_lewat_waktu_bukan_perlu_terbit_ulang(self):
        r = tpn.ringkas_status_ttd(_sr(signers=[
            _signer("ditandatangani", sisa_hari=-5)]))
        assert r["perlu_terbit_ulang"] is False

    def test_batas_terdekat_diambil_dari_yang_BELUM_teken(self):
        """Batas terjauh akan menyembunyikan tautan yang justru hampir mati."""
        sr = _sr(signers=[_signer("aktif", 2), _signer("aktif", 12)])
        assert tpn.kedaluwarsa_terdekat(sr)["sisa_detik"] < 3 * 86400

    def test_yang_sudah_teken_tidak_ikut_menentukan_batas(self):
        sr = _sr(signers=[_signer("ditandatangani", -9), _signer("aktif", 12)])
        assert tpn.kedaluwarsa_terdekat(sr)["sisa_detik"] > 10 * 86400

    def test_tanpa_permintaan_ringkasannya_kosong(self):
        assert tpn.ringkas_status_ttd(None) == {}


class TestStatusSehalamanDokumen:
    def test_satu_kueri_memetakan_banyak_dokumen(self, dbx):
        async def skenario():
            await dbx.signature_requests.insert_many([
                _sr("sr-a", "bast-1", [_signer("aktif")]),
                _sr("sr-b", "bast-2", [_signer("ditandatangani")]),
            ])
            peta = await tpn.status_ttd_dokumen(dbx, "bast", ["bast-1", "bast-2", "bast-9"])
            assert set(peta) == {"bast-1", "bast-2"}
            assert peta["bast-2"]["semua_selesai"] is True
        _jalan(skenario())

    def test_dikirim_ULANG_yang_diambil_permintaan_TERBARU(self, dbx):
        """Dokumen yang dikirim dua kali punya dua permintaan. Yang lama sudah
        mati; menampilkannya membuat layar bilang "kedaluwarsa" padahal
        permintaan barunya masih hidup — persis gejala yang dilaporkan."""
        async def skenario():
            await dbx.signature_requests.insert_many([
                _sr("sr-lama", "bast-1", [_signer("aktif", -3)],
                    created="2026-01-01T00:00:00+00:00"),
                _sr("sr-baru", "bast-1", [_signer("aktif", 13)],
                    created="2026-08-20T00:00:00+00:00"),
            ])
            peta = await tpn.status_ttd_dokumen(dbx, "bast", ["bast-1"])
            assert peta["bast-1"]["id"] == "sr-baru"
            assert peta["bast-1"]["perlu_terbit_ulang"] is False
        _jalan(skenario())

    def test_daftar_kosong_tidak_menembak_db(self, dbx):
        async def skenario():
            assert await tpn.status_ttd_dokumen(dbx, "bast", []) == {}
            assert await tpn.status_ttd_dokumen(dbx, "entah", ["x"]) == {}
        _jalan(skenario())


class TestRiwayatBastMembawaStatus:
    def test_daftar_bast_menyertakan_ttd(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
            hasil = await _buka(rb.daftar_bast)(_user=USER)
            it = hasil["items"][0]
            assert it["ttd"]["jumlah"] == 2
            assert it["ttd"]["selesai_jumlah"] == 0
            assert it["ttd"]["perlu_terbit_ulang"] is False
        _jalan(skenario())

    def test_bast_yang_belum_pernah_dikirim_ber_ttd_None(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast("bast-2"))
            hasil = await _buka(rb.daftar_bast)(_user=USER)
            assert hasil["items"][0]["ttd"] is None
        _jalan(skenario())
