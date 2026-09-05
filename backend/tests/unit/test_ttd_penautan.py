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
        created="2026-08-01T00:00:00+00:00", doc_type="bast"):
    return {"id": sr_id, "doc_type": doc_type, "doc_ref": doc_ref,
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
                                     "persetujuan_persediaan",
                                     "nota_persediaan"}

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
            assert hasil["judul"] == "bast-1/2026", (
                "jenis BAST disimpan terpisah; judul tidak boleh menjadi "
                "'BAST BAST-…'")
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
            _signer("ditandatangani"), _signer("ditandatangani")],
            status="selesai"))
        assert r["semua_selesai"] is True
        assert r["perlu_terbit_ulang"] is False

    def test_semua_membubuhkan_belum_dianggap_selesai_sebelum_validasi(self):
        r = tpn.ringkas_status_ttd(_sr(signers=[
            _signer("menunggu_validasi"), _signer("menunggu_validasi")],
            status="menunggu_validasi"))
        assert r["membubuhkan_jumlah"] == 2
        assert r["selesai_jumlah"] == 0
        assert r["semua_selesai"] is False

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
                _sr("sr-b", "bast-2", [_signer("ditandatangani")],
                    status="selesai"),
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


class TestEmpatDaftarMembawaStatusYangSAMA:
    """Empat daftar dokumen memakai potongan yang sama persis. Ditulis sekali
    di `lampirkan_status_ttd` supaya daftar KELIMA tak perlu menyalinnya — dan
    supaya tak ada yang diam-diam memakai kunci atau nama field berbeda, yang
    membuat layarnya sunyi tanpa satu pun galat.
    """

    def test_menempelkan_ringkasan_ke_tiap_item(self, dbx):
        async def skenario():
            await dbx.signature_requests.insert_one(
                _sr("sr-1", "dok-1", [_signer("aktif")]))
            items = [{"id": "dok-1"}, {"id": "dok-2"}]
            await tpn.lampirkan_status_ttd(dbx, "bast", items)
            assert items[0]["ttd"]["id"] == "sr-1"
            assert items[1]["ttd"] is None
        _jalan(skenario())

    def test_daftar_kosong_aman(self, dbx):
        async def skenario():
            assert await tpn.lampirkan_status_ttd(dbx, "bast", []) == []
            assert await tpn.lampirkan_status_ttd(dbx, "bast", None) == []
        _jalan(skenario())

    def test_riwayat_LPB_membawa_status(self, dbx):
        async def skenario():
            import routes.persediaan as rps
            rps.db = dbx
            await dbx.lpb.insert_one({"id": "lpb-1", "kode_satker": "111111",
                                      "nomor": "LPB-1", "kategori": "gabungan"})
            await dbx.signature_requests.insert_one(
                _sr("sr-lpb", "lpb-1", [_signer("aktif")], doc_type="lpb"))
            hasil = await _buka(rps.daftar_lpb)(_user=USER)
            assert hasil["items"][0]["ttd"]["id"] == "sr-lpb"
        _jalan(skenario())

    def test_daftar_permohonan_aset_membawa_status(self, dbx):
        async def skenario():
            import routes.aset_permohonan as rap
            rap.db = dbx
            await dbx.aset_permohonan.insert_one(
                {"id": "pm-1", "kode_satker": "111111", "status": "disetujui"})
            await dbx.signature_requests.insert_one(
                _sr("sr-pm", "pm-1", [_signer("aktif")],
                    doc_type="persetujuan_aset"))
            hasil = await _buka(rap.daftar_permohonan_aset)(
                page=1, page_size=30, _user=USER)
            assert hasil["items"][0]["ttd"]["id"] == "sr-pm"
        _jalan(skenario())

    def test_daftar_permohonan_persediaan_membawa_status(self, dbx):
        async def skenario():
            import routes.persediaan_permohonan as rpp
            rpp.db = dbx
            await dbx.persediaan_permohonan.insert_one(
                {"id": "pp-1", "kode_satker": "111111", "status": "disetujui"})
            await dbx.signature_requests.insert_one(
                _sr("sr-pp", "pp-1", [_signer("aktif")],
                    doc_type="persetujuan_persediaan"))
            hasil = await _buka(rpp.daftar_permohonan)(
                page=1, page_size=30, _user=USER)
            assert hasil["items"][0]["ttd"]["id"] == "sr-pp"
        _jalan(skenario())


class TestSptjMenambahTempatTeken:
    """Permintaan pemilik: BAST ber-Surat Pernyataan Tanggung Jawab otomatis
    menambah tempat teken bagi orang yang namanya tercantum di lembar itu.

    Diuji lewat ENDPOINT-nya, bukan hanya modul murninya: yang menentukan
    dokumen terbit lengkap atau tidak adalah angka yang benar-benar tersimpan
    di `signature_requests`.
    """

    def test_tanpa_SPTJ_setiap_orang_satu_tempat(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            assert [s["jumlah_ttd"] for s in sr["signers"]] == [1, 1]
        _jalan(skenario())

    async def _kirim(self, dbx, **ubah):
        await dbx.bast_serah_terima.insert_one(
            {**_bast(), "surat_pernyataan": True, **ubah})
        hasil = await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
        sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
        return {s["nama"]: s["jumlah_ttd"] for s in sr["signers"]}

    def test_PEMEGANG_dapat_tempat_tambahan_pada_jenis_penguasaan(self, dbx):
        """Kasus yang dimaksud pemilik ("aset pemegang"): pada BAST penguasaan,
        yang MEMEGANG BMN sesudah serah terima adalah Pihak Kedua, dan dialah
        yang menyatakan tanggung jawab."""
        async def skenario():
            per_nama = await self._kirim(dbx, jenis="penggunaan_melekat")
            assert per_nama["Sari"] == 2, per_nama
            assert per_nama["Budi"] == 1, "penyerah tak ikut menyatakan"
        _jalan(skenario())

    def test_pada_PENGEMBALIAN_lembarnya_jatuh_ke_PIHAK_PERTAMA(self, dbx):
        """Aturannya mengikuti SIAPA YANG MEMEGANG sesudahnya, bukan posisi
        di dokumen — dan modul ini mengikuti `daftar_penyata` apa adanya,
        bukan memaksakan pendapatnya sendiri. Uji ini yang membuktikannya:
        seandainya kode di sini menebak "selalu Pihak Kedua", ia gagal."""
        async def skenario():
            per_nama = await self._kirim(dbx, jenis="operasional")
            assert per_nama["Budi"] == 2, per_nama
            assert per_nama["Sari"] == 1, per_nama
        _jalan(skenario())

    def test_gerbang_kelengkapan_ikut_menagihnya(self, dbx):
        """Angka itu baru berguna bila gerbang kelengkapan membacanya —
        kalau tidak, lembar pernyataan tetap bisa terbit kosong."""
        from ttd_kelengkapan import pesan_kurang

        async def skenario():
            await dbx.bast_serah_terima.insert_one(
                {**_bast(), "surat_pernyataan": True})
            hasil = await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            sari = next(s for s in sr["signers"] if s["nama"] == "Budi")
            # Satu pembubuhan saja BELUM cukup untuk orang ber-SPTJ.
            assert pesan_kurang(sari["jumlah_ttd"], {"halaman": 1}, []) != ""
        _jalan(skenario())


class TestPilihanUrutanDanUrgensi:
    """Permintaan pemilik: saat menekan "Kirim TTD" dapat memilih urutan teken
    (paralel/berurutan) dan sifat urgensi suratnya."""

    def test_bawaannya_sama_dengan_perilaku_lama(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)("bast-1", user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            assert sr["mode"] == "paralel"
            assert sr["sifat_urgensi"] == "biasa"
        _jalan(skenario())

    def test_pilihan_pengirim_benar_benar_tersimpan(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)(
                "bast-1", rb.KirimTtdIn(mode="berurutan",
                                        sifat_urgensi="sangat_segera"),
                user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            assert sr["mode"] == "berurutan"
            assert sr["sifat_urgensi"] == "sangat_segera"
        _jalan(skenario())

    def test_mode_BERURUTAN_hanya_mengaktifkan_giliran_pertama(self, dbx):
        """Pilihan itu baru berarti bila ia benar-benar mengubah siapa yang
        bisa meneken sekarang — kalau tidak, ia hanya label."""
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)(
                "bast-1", rb.KirimTtdIn(mode="berurutan"), user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            status = [s["status"] for s in sr["signers"]]
            assert status.count("aktif") == 1, status
            assert status.count("menunggu") == len(status) - 1, status
        _jalan(skenario())

    def test_urgensi_TAK_DIKENAL_ditolak_400(self, dbx):
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            with pytest.raises(rt.HTTPException) as e:
                await _buka(rb.kirim_bast_ke_ttd)(
                    "bast-1", rb.KirimTtdIn(sifat_urgensi="gawat_darurat"),
                    user=USER)
            assert e.value.status_code == 400
            assert "urgensi" in str(e.value.detail).lower()
        _jalan(skenario())

    def test_urgensi_sampai_ke_halaman_penanda_tangan(self, dbx):
        """Kalau hanya hidup di dokumen, "segera" tak mengubah apa pun bagi
        orang yang diminta meneken."""
        async def skenario():
            await dbx.bast_serah_terima.insert_one(_bast())
            hasil = await _buka(rb.kirim_bast_ke_ttd)(
                "bast-1", rb.KirimTtdIn(sifat_urgensi="segera"), user=USER)
            sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
            sg = sr["signers"][0]
            info = await _buka(rt.info_tandatangan)(
                sr["id"], tok={"sr": sr["id"], "signer": sg["signer_id"],
                               "jti": sg["jti"]})
            assert info["sifat_urgensi"] == "segera"
        _jalan(skenario())
