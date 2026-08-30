"""Gelung tail event-bus tak boleh menerbitkan `find()` bertubi-tubi.

CACAT YANG DIPERBAIKI, dan bagaimana ia ketahuan.

Inventaris VPS 29 Agustus 2026 menemukan `mongod` memakai **93,1% CPU**
terus-menerus pada mesin 2 vCPU — beban 1,00 datar di jendela 1/5/15 menit
selama berminggu-minggu, tak peduli ada pengguna atau tidak. Diagnosa
berikutnya membaca:

===========================  =============
Query dalam 17,1 jam         6.943.415  (112,5 per detik)
Tulis dalam periode sama     1.220
`getmore`                    **59**
Akses indeks pada `assets`   236
Antrean baca / tulis         0 / 0
===========================  =============

Angka `getmore` itu yang menunjuk pelakunya. Kursor TAILABLE_AWAIT yang
benar-benar MENAHAN menghasilkan jutaan `getmore`; 59 berarti tiap putaran
adalah `find()` BARU, bukan kelanjutan kursor. `_tail_loop` tak punya satu pun
jeda pada jalur suksesnya, jadi begitu kursornya habis seketika ia langsung
menerbitkan `find()` berikutnya — dan tiap `find()` memindai seluruh 20.000
dokumen `ws_events`, koleksi yang hanya punya indeks `_id_`.

Diukur ulang di luar produksi dengan kursor tiruan yang habis seketika:

* tanpa I/O sama sekali → gelungnya **tak pernah melepas event loop**; probe-nya
  timeout. Bukan hanya Mongo yang terbebani — seluruh proses kelaparan.
* dengan round-trip 8 ms → **121 find()/detik**, cocok dengan 112,5/detik yang
  terbaca di produksi dalam 8%.

Sesudah diperbaiki, pada probe yang sama: **10 find()/detik**.

Uji di bawah mengunci perilakunya, bukan angkanya: gelung yang kursornya mati
harus TERTAHAN, dan gelung yang kursornya sehat TIDAK boleh ikut tertahan.
"""
import asyncio
import time

import pytest
from bson import ObjectId

import event_bus


class _KursorPalsu:
    """Kursor tailable tiruan. `tahan` = berapa lama ia menahan sebelum habis."""

    def __init__(self, dokumen, tahan, catatan):
        self._dokumen = list(dokumen)
        self._tahan = tahan
        self._catatan = catatan

    def max_await_time_ms(self, ms):
        """METODE BERANTAI, seperti Motor/PyMongo yang sesungguhnya.

        Dulu kode produksinya menulis `cursor.max_await_time_ms = 2000`, yang
        MENIMPA metode ini dengan sebuah integer — `maxAwaitTimeMS` tak pernah
        sampai ke server. Tiruan ini sengaja METODE, bukan atribut, supaya
        penugasan semacam itu tak bisa lagi lolos diam-diam.
        """
        self._catatan["max_await_time_ms"] = ms
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._dokumen:
            return self._dokumen.pop(0)
        if self._tahan:
            await asyncio.sleep(self._tahan)
        raise StopAsyncIteration


class _KoleksiPalsu:
    def __init__(self, dokumen=(), tahan=0.0, rtt=0.0, terakhir=None):
        self.jumlah_find = 0
        self.kueri_terakhir = None
        self.catatan = {}
        self._dokumen = list(dokumen)
        self._tahan = tahan
        self._rtt = rtt
        self._terakhir = terakhir

    async def find_one(self, *_a, **_k):
        return self._terakhir

    def find(self, kueri=None, *_a, **_k):
        self.jumlah_find += 1
        self.kueri_terakhir = kueri
        kirim, self._dokumen = self._dokumen, []
        return _KursorPalsu(kirim, self._tahan or self._rtt, self.catatan)


class _DbPalsu:
    def __init__(self, koleksi):
        self.koleksi = koleksi

    def __getitem__(self, _nama):
        return self.koleksi


async def _jalankan(koleksi, detik, handler=None):
    """Putar _tail_loop selama `detik`, lalu batalkan."""
    async def _kosong(_a, _p):
        return None

    tugas = asyncio.create_task(
        event_bus._tail_loop(_DbPalsu(koleksi), handler or _kosong))
    mulai = time.monotonic()
    await asyncio.sleep(detik)
    lama = time.monotonic() - mulai
    tugas.cancel()
    try:
        await tugas
    except asyncio.CancelledError:
        pass
    return lama


@pytest.mark.asyncio
async def test_kursor_yang_mati_seketika_TIDAK_membanjiri_mongod():
    # Kursor habis setelah round-trip 8 ms, tanpa memberi dokumen apa pun —
    # persis gejala produksi (59 getmore berbanding 6,94 juta query).
    koleksi = _KoleksiPalsu(rtt=0.008)
    lama = await _jalankan(koleksi, 0.6)
    laju = koleksi.jumlah_find / lama
    # Tanpa perbaikan laju ini ±121/detik. Batasnya dipasang longgar (25)
    # supaya uji tak rapuh pada mesin CI yang lambat, tetapi tetap jauh di
    # bawah angka cacatnya.
    assert laju < 25, (
        f"gelung menerbitkan {laju:,.0f} find()/detik — ia berputar bebas lagi"
    )


@pytest.mark.asyncio
async def test_kursor_yang_SEHAT_tak_ikut_tertahan():
    # Kursor yang benar-benar menahan sudah melewati jendela jeda, jadi
    # perbaikannya tak boleh menambah keterlambatan apa pun. Kalau uji ini
    # dihapus, "perbaikan" berupa `sleep` tanpa syarat akan lolos.
    # Waktu tahan dipilih TEPAT DI ATAS JEDA_KURSOR_MATI supaya jeda tanpa
    # syarat hampir MELIPATGANDAKAN panjang siklusnya — versi pertama uji ini
    # memakai 0,15 s dan bedanya hanya 4 lawan 3 find, terlalu rapat untuk
    # membedakan apa pun. Mutasi "sleep tanpa syarat" lolos karenanya.
    tahan = event_bus.JEDA_KURSOR_MATI + 0.01
    koleksi = _KoleksiPalsu(tahan=tahan)
    lama = await _jalankan(koleksi, 0.8)
    # Benar  : siklus 0,11 s => ±7 find dalam 0,8 s.
    # Cacat  : siklus 0,21 s => ±3 find.
    assert koleksi.jumlah_find >= 5, (
        f"hanya {koleksi.jumlah_find} find() dalam {lama:.2f}s — kursor sehat "
        "ikut tertahan"
    )


@pytest.mark.asyncio
async def test_dokumen_tetap_diteruskan_ke_handler():
    # Penahanan laju tak boleh menelan peristiwanya. Tanpa uji ini, "perbaikan"
    # berupa `return` di awal gelung akan lolos kedua uji di atas.
    diterima = []

    async def handler(activity_id, payload):
        diterima.append((activity_id, payload))

    koleksi = _KoleksiPalsu(
        dokumen=[{"activity_id": "keg-1", "ts": None, "worker_id": "lain",
                  "_id": ObjectId(), "tipe": "aset_disimpan"}],
        rtt=0.008)
    await _jalankan(koleksi, 0.3, handler)
    assert diterima, "peristiwa tak pernah sampai ke handler"
    assert diterima[0][0] == "keg-1"
    # Metadata bus dilucuti, muatan diteruskan.
    assert diterima[0][1] == {"tipe": "aset_disimpan"}


@pytest.mark.asyncio
async def test_keadaan_itu_diumumkan_ke_log(caplog):
    # Cacat ini berjalan berminggu-minggu tanpa satu pun baris log. Diam bukan
    # tanda sehat.
    asli = event_bus.AMBANG_LAPOR_KURSOR_MATI
    event_bus.AMBANG_LAPOR_KURSOR_MATI = 3
    try:
        with caplog.at_level("WARNING"):
            await _jalankan(_KoleksiPalsu(rtt=0.001), 0.6)
        assert any("awaitData" in r.message or "awaitData" in r.getMessage()
                   for r in caplog.records), (
            "kursor yang terus mati tak menghasilkan peringatan apa pun"
        )
    finally:
        event_bus.AMBANG_LAPOR_KURSOR_MATI = asli


class TestPenandaPosisiMemakaiIndeksYangADA:
    """`ws_events` hanya punya indeks `_id_`, dan ia dipakai **0 kali**.

    Diagnosa 30 Agustus 2026 setelah perbaikan laju:

    ==================================  ===============
    Waktu mongod di `ws_events`         **99,7%**
    Dokumen dipindai                    145.238.636.134
    Dipindai per dokumen dikembalikan   370.825 : 1
    Pindai koleksi                      7.263.861
    Indeks `_id_` pada `ws_events`      **0 ops**
    ==================================  ===============

    Filter `{"ts": {"$gt": …}}` memindai seluruh 20.000 dokumen tiap kali
    kursor dibuat, sementara indeks yang bisa menjawabnya menganggur di
    sebelahnya. `{"_id": {"$gt": …}}` mengubahnya jadi pencarian indeks.
    """

    @pytest.mark.asyncio
    async def test_filter_memakai_id_bukan_ts(self):
        koleksi = _KoleksiPalsu(rtt=0.005)
        await _jalankan(koleksi, 0.3)
        kueri = koleksi.kueri_terakhir
        assert "_id" in kueri, f"filter tak memakai `_id`: {kueri}"
        assert "ts" not in kueri, (
            f"filter masih memakai `ts` — memindai 20.000 dokumen tiap kali: {kueri}"
        )
        # Penyaring loopback tetap ada; tanpanya tiap worker memproses
        # peristiwanya sendiri.
        assert "worker_id" in kueri

    @pytest.mark.asyncio
    async def test_max_await_time_ms_DIPANGGIL_bukan_ditugaskan(self):
        # Kursor tiruan mengeksposnya sebagai METODE. Kode yang menulis
        # `cursor.max_await_time_ms = 2000` akan menimpanya dan catatan ini
        # tetap kosong — persis cacat yang berjalan berminggu-minggu.
        koleksi = _KoleksiPalsu(rtt=0.005)
        await _jalankan(koleksi, 0.3)
        assert koleksi.catatan.get("max_await_time_ms") == 2000, (
            "maxAwaitTimeMS tak pernah terpasang pada kursor"
        )

    @pytest.mark.asyncio
    async def test_posisi_awal_diambil_dari_dokumen_TERBARU(self):
        # Tanpa ini gelung mulai dari ObjectId waktu-sekarang dan bisa
        # melewatkan peristiwa yang tiba di detik yang sama.
        terbaru = ObjectId()
        koleksi = _KoleksiPalsu(rtt=0.005, terakhir={"_id": terbaru})
        await _jalankan(koleksi, 0.3)
        assert koleksi.kueri_terakhir["_id"] == {"$gt": terbaru}

    @pytest.mark.asyncio
    async def test_koleksi_kosong_tetap_jalan(self):
        # find_one mengembalikan None saat ring buffer masih kosong.
        koleksi = _KoleksiPalsu(rtt=0.005, terakhir=None)
        await _jalankan(koleksi, 0.3)
        assert isinstance(koleksi.kueri_terakhir["_id"]["$gt"], ObjectId)


class _DbCincin:
    """Db tiruan untuk menguji pengecilan cincin."""

    def __init__(self, maks, besar):
        self.perintah = []
        self._maks, self._besar = maks, besar

    async def list_collection_names(self):
        return [event_bus.COLLECTION_NAME]

    async def command(self, perintah, *_a, **_k):
        self.perintah.append(perintah)
        if isinstance(perintah, dict) and "listCollections" in perintah:
            opsi = {"capped": True}
            if self._maks is not None:
                opsi["max"] = self._maks
            if self._besar is not None:
                opsi["size"] = self._besar
            return {"cursor": {"firstBatch": [{"options": opsi}]}}
        return {"ok": 1}


class TestCincinDikecilkan:
    """Kursor tailable TIDAK memakai indeks — jadi ukuran cincin ADALAH biayanya.

    Klaim di [#948] bahwa mengganti filter ke `_id` mengubah pindai-koleksi
    menjadi pencarian indeks **terbukti SALAH**. Bacaan 30 Agustus 2026,
    2,45 jam setelah perbaikan itu ter-deploy:

    ===============================  ==========
    Pindai koleksi per query         **0,98**
    Dokumen dipindai per pindaian    **19.291**
    `ws_events._id_` dipakai         **0 ops**
    ===============================  ==========

    Setiap query masih memindai praktis seluruh cincin. Dokumentasi MongoDB
    menyebutnya terang: kursor tailable tidak memakai indeks.

    Yang tersisa karena itu bukan soal filter melainkan soal UKURAN: biaya
    pindaian sebanding lurus dengan isi cincin.
    """

    @pytest.mark.asyncio
    async def test_cincin_lama_yang_kebesaran_dikecilkan(self):
        db = _DbCincin(maks=20000, besar=10 * 1024 * 1024)
        assert await event_bus.ensure_capped_collection(db) is True
        mod = [p for p in db.perintah if isinstance(p, dict) and "collMod" in p]
        assert mod, "cincin kebesaran tidak dikecilkan"
        assert mod[0]["cappedMax"] == event_bus.CAPPED_MAX_DOCS
        assert mod[0]["cappedSize"] == event_bus.CAPPED_SIZE_BYTES

    @pytest.mark.asyncio
    async def test_cincin_yang_SUDAH_pas_tak_disentuh(self):
        # Tanpa ini, tiap start worker menulis collMod tanpa guna.
        db = _DbCincin(maks=event_bus.CAPPED_MAX_DOCS,
                       besar=event_bus.CAPPED_SIZE_BYTES)
        await event_bus.ensure_capped_collection(db)
        assert not [p for p in db.perintah if isinstance(p, dict) and "collMod" in p]

    @pytest.mark.asyncio
    async def test_cincin_yang_lebih_KECIL_tak_dibesarkan(self):
        # Hanya mengecilkan. Membesarkan tak memberi manfaat dan justru
        # menaikkan biaya pindaian tiap putaran.
        db = _DbCincin(maks=100, besar=64 * 1024)
        await event_bus.ensure_capped_collection(db)
        assert not [p for p in db.perintah if isinstance(p, dict) and "collMod" in p]

    @pytest.mark.asyncio
    async def test_server_yang_menolak_collMod_tidak_menjatuhkan_bus(self):
        class _Galat(_DbCincin):
            async def command(self, perintah, *a, **k):
                if isinstance(perintah, dict) and "collMod" in perintah:
                    raise RuntimeError("collMod tak didukung")
                return await super().command(perintah, *a, **k)

        db = _Galat(maks=20000, besar=10 * 1024 * 1024)
        assert await event_bus.ensure_capped_collection(db) is True

    def test_cincin_cukup_besar_untuk_penyangga_nyata(self):
        # Laju sisip terukur 485 dalam 22 jam = 0,006/detik. Seribu slot
        # adalah cadangan berjam-jam. Batas bawah ini menjaga agar
        # "mengecilkan" tak berubah jadi "membuang peristiwa".
        assert event_bus.CAPPED_MAX_DOCS >= 500
        assert event_bus.CAPPED_MAX_DOCS <= 5000, (
            "cincin terlalu besar — tiap pindaian kursor tailable membacanya utuh"
        )
