"""Satu ponsel di sinyal buruk tidak boleh menahan seluruh bus — temuan C24.

`broadcast_local` dulu mengirim SERIAL tanpa batas waktu:

    for ws in list(self.active[activity_id].keys()):
        await ws.send_json(message)

Klien dengan koneksi SETENGAH MATI — soketnya belum terputus, tetapi buffer
kirimnya tak lagi terkuras — membuat satu `await` itu menggantung tanpa batas.
Bukan hipotesis: itulah profil normal ponsel lapangan yang masuk basement atau
kehilangan sinyal di tengah kegiatan.

Yang membuatnya cacat dan bukan sekadar risiko skala adalah SIAPA yang ikut
menunggu:

  • `_on_remote_event` dipanggil dari SATU loop tail `event_bus`. Loop itu
    berhenti mengonsumsi, jadi SELURUH notifikasi lintas-worker di worker ini
    berhenti — termasuk untuk kegiatan yang tak ada hubungannya.
  • `notify_asset_change` di-await inline pada enam jalur tulis aset. Penyimpan
    lain di kegiatan yang sama ikut menunggu ponsel itu.

Satu klien lambat sudah cukup. Tidak perlu beban, tidak perlu skala.

Berkas ini mengurung empat hal yang masing-masing bisa hilang sendiri-sendiri:

  1. **Batas waktu** — broadcast selesai, bukan menggantung selamanya.
  2. **Paralel** — soket lambat tidak mengantre di belakang soket lambat lain.
  3. **Isolasi** — soket sehat tetap menerima pesannya.
  4. **Penutupan** — soket mati DITUTUP, tidak sekadar dilepas dari `active`.
     Melepas saja meninggalkan koneksi hidup beserta buffer penuhnya: memori
     tertahan dan klien tak pernah tahu ia harus menyambung ulang.
"""
import asyncio
import inspect
import re
import time

import pytest

from routes.websocket import ConnectionManager

KEG = "keg-uji"

# Batas kirim yang dipendekkan untuk uji. Angka produksi 5 detik benar, tetapi
# menunggunya di CI berarti setiap uji timeout membayar 5 detik. Yang diuji
# adalah PERILAKUNYA (ada batas, batasnya dihormati), bukan angkanya — angka
# produksinya dijaga terpisah di TestKonstanta.
BATAS_UJI = 0.05


def _kode(fn) -> str:
    """Sumber sebuah fungsi TANPA komentar & docstring.

    Penjaga struktural yang membaca sumber mentah bisa dipuaskan oleh PROSA:
    docstring di atas menyebut `asyncio.gather` dan `ws.send_json` beberapa
    kali. Tanpa pengupasan ini, menghapus `gather` yang sebenarnya tetap
    meninggalkan kata itu di berkas dan ujinya lolos — penjaga yang tak
    menjaga apa-apa.
    """
    src = inspect.getsource(fn)
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    src = re.sub(r"^\s*#.*$", "", src, flags=re.M)
    return src


class SoketPalsu:
    """Soket yang bisa disuruh berperilaku persis seperti klien bermasalah."""

    def __init__(self, nama, gantung=False, meledak=False,
                 tutup_meledak=False, tunda=0.0, tutup_gantung=False):
        self.nama = nama
        self.gantung = gantung
        self.meledak = meledak
        self.tutup_meledak = tutup_meledak
        self.tunda = tunda
        self.tutup_gantung = tutup_gantung
        self.terkirim = []
        self.ditutup = []

    async def send_json(self, message):
        if self.meledak:
            raise ConnectionResetError(f"transport {self.nama} hilang")
        if self.gantung:
            # Sinyal buruk: soket hidup, buffer tak terkuras, `await` diam.
            await asyncio.sleep(3600)
        if self.tunda:
            await asyncio.sleep(self.tunda)
        self.terkirim.append(message)

    async def close(self, code=1000):
        if self.tutup_meledak:
            raise RuntimeError(f"close {self.nama} gagal")
        if self.tutup_gantung:
            # Penutupan yang menggantung BUKAN karangan. `WebSocket.close()`
            # di uvicorn diteruskan ke protokol `websockets`, yang menunggu
            # handshake penutupan lalu teardown TCP — kelasnya sendiri
            # mendokumentasikan "close() completes in at most 4 * close_timeout
            # for servers", dan uvicorn tak meneruskan close_timeout sehingga
            # berlaku default 10 detik. Soket yang ditutup di sini justru soket
            # yang buffernya TIDAK terkuras: keadaan terburuknya.
            await asyncio.sleep(3600)
        self.ditutup.append(code)

    def __repr__(self):
        return f"<SoketPalsu {self.nama}>"


def bikin(*soket, batas=BATAS_UJI, kegiatan=KEG):
    """ConnectionManager berisi soket-soket ini, dengan batas kirim pendek."""
    m = ConnectionManager()
    m.BATAS_KIRIM_DETIK = batas
    m.active[kegiatan] = {
        ws: {"user_id": f"u-{ws.nama}", "user_name": ws.nama} for ws in soket
    }
    return m


PESAN = {"type": "asset_updated", "asset_id": "a1"}


async def siarkan(m, *a, **kw):
    """Siarkan DENGAN pagar waktu di sisi uji.

    Bukan hiasan: setiap uji di berkas ini menaruh soket yang menggantung
    3600 detik. Kalau regresinya adalah "batas waktunya hilang", uji tanpa
    pagar tidak GAGAL — ia MENGGANTUNG, dan job CI mati kehabisan waktu
    berjam-jam kemudian tanpa menyebut penyebabnya. Pagar ini mengubah
    regresi itu menjadi kegagalan yang berbunyi dalam lima detik.
    """
    return await asyncio.wait_for(m.broadcast_local(*a, **kw), timeout=5)


@pytest.mark.asyncio
class TestSoketMenggantung:
    """Inti C24: satu klien setengah-mati, sisanya harus tetap hidup."""

    async def test_broadcast_SELESAI_tidak_menggantung_selamanya(self):
        gantung = SoketPalsu("gantung", gantung=True)
        m = bikin(gantung)
        mulai = time.monotonic()
        await siarkan(m, KEG, PESAN)
        # Batasnya 0,05 dtk; longgarkan ke 2 dtk untuk CI yang sibuk. Kalau
        # batasnya dihapus (atau di-hardcode 5), uji ini yang jatuh duluan.
        assert time.monotonic() - mulai < 2.0

    async def test_soket_sehat_TETAP_menerima_walau_ada_yang_menggantung(self):
        sehat_a = SoketPalsu("sehat-a")
        gantung = SoketPalsu("gantung", gantung=True)
        sehat_b = SoketPalsu("sehat-b")
        m = bikin(sehat_a, gantung, sehat_b)
        await siarkan(m, KEG, PESAN)
        assert sehat_a.terkirim == [PESAN]
        # sehat_b duduk SETELAH yang menggantung: pada versi serial ia tak
        # pernah kebagian sama sekali.
        assert sehat_b.terkirim == [PESAN]
        assert gantung.terkirim == []

    async def test_soket_menggantung_dikeluarkan_dari_active(self):
        sehat = SoketPalsu("sehat")
        gantung = SoketPalsu("gantung", gantung=True)
        m = bikin(sehat, gantung)
        await siarkan(m, KEG, PESAN)
        assert gantung not in m.active[KEG]
        assert sehat in m.active[KEG]

    async def test_soket_menggantung_DITUTUP_bukan_sekadar_dilepas(self):
        """Melepas tanpa menutup = koneksi hidup tanpa pemilik.

        Memorinya tertahan di proses, dan klien tak pernah menerima sinyal
        untuk menyambung ulang — ia diam mengira masih tersambung.
        """
        gantung = SoketPalsu("gantung", gantung=True)
        m = bikin(gantung)
        await siarkan(m, KEG, PESAN)
        assert gantung.ditutup, "soket mati tidak ditutup"
        assert gantung.ditutup[0] == 1011

    async def test_soket_sehat_TIDAK_ikut_ditutup(self):
        sehat = SoketPalsu("sehat")
        gantung = SoketPalsu("gantung", gantung=True)
        m = bikin(sehat, gantung)
        await siarkan(m, KEG, PESAN)
        assert sehat.ditutup == []

    async def test_siaran_berikutnya_tak_lagi_menunggu_soket_yang_sudah_mati(self):
        """Pembersihan harus PERMANEN, bukan per-panggilan.

        Kalau soket mati dibiarkan di `active`, setiap siaran berikutnya
        membayar timeout yang sama lagi — 5 detik, selamanya.
        """
        sehat = SoketPalsu("sehat")
        gantung = SoketPalsu("gantung", gantung=True)
        m = bikin(sehat, gantung)
        await siarkan(m, KEG, PESAN)
        mulai = time.monotonic()
        await siarkan(m, KEG, {"type": "kedua"})
        assert time.monotonic() - mulai < BATAS_UJI, "masih menunggu soket mati"
        assert len(sehat.terkirim) == 2


@pytest.mark.asyncio
class TestPenutupanJugaBerbatasWaktu:
    """Cacat yang PINDAH BARIS, bukan tertutup.

    Versi pertama C24 membatasi waktu KIRIM tetapi menutup soket mati secara
    BERURUTAN tanpa `wait_for`. Batas kirimnya dihormati — lalu `broadcast_local`
    menggantung di `close()`, berlipat dengan jumlah soket mati.

    Titik buta ujinya: `SoketPalsu.close()` dulu kembali seketika, jadi seluruh
    uji "soket ditutup" lolos tanpa pernah menguji LAMANYA. Diukur dengan close
    2 detik × 3 soket: `broadcast_local` memakan 6,06 detik meski
    BATAS_KIRIM_DETIK = 0,05.
    """

    async def test_penutupan_yang_menggantung_TIDAK_menahan_siaran(self):
        mati = [SoketPalsu(f"mati-{i}", gantung=True, tutup_gantung=True)
                for i in range(3)]
        m = bikin(*mati)
        mulai = time.monotonic()
        await siarkan(m, KEG, PESAN)
        lewat = time.monotonic() - mulai
        assert lewat < 1.0, f"tertahan di penutupan ({lewat:.2f} dtk)"

    async def test_soket_sehat_tetap_menerima_walau_penutupan_menggantung(self):
        sehat = SoketPalsu("sehat")
        mati = SoketPalsu("mati", gantung=True, tutup_gantung=True)
        m = bikin(sehat, mati)
        await siarkan(m, KEG, PESAN)
        assert sehat.terkirim == [PESAN]
        assert mati not in m.active[KEG]

    async def test_penutupan_TIDAK_berurutan(self):
        """Tiga penutupan @0,12 dtk: sejajar ≈0,12 dtk, berurutan ≈0,36 dtk."""
        class _Lambat(SoketPalsu):
            async def close(self, code=1000):
                await asyncio.sleep(0.12)
                self.ditutup.append(code)

        mati = [_Lambat(f"lambat-{i}", meledak=True) for i in range(3)]
        m = bikin(*mati, batas=5)
        mulai = time.monotonic()
        await siarkan(m, KEG, PESAN)
        lewat = time.monotonic() - mulai
        assert lewat < 0.30, f"penutupan tampak berurutan ({lewat:.2f} dtk)"
        assert all(s.ditutup == [1011] for s in mati)


@pytest.mark.asyncio
class TestKirimParalel:
    async def test_soket_lambat_TIDAK_mengantre_satu_sama_lain(self):
        """Empat klien @0,12 dtk: paralel ≈0,12 dtk, serial ≈0,48 dtk.

        Ini membedakan `asyncio.gather` dari `for ws in ...: await`. Keduanya
        sama-sama "selesai" — yang satu empat kali lebih lama, dan lamanya
        tumbuh linier dengan jumlah petugas di lapangan.
        """
        lambat = [SoketPalsu(f"lambat-{i}", tunda=0.12) for i in range(4)]
        m = bikin(*lambat, batas=5)
        mulai = time.monotonic()
        await siarkan(m, KEG, PESAN)
        lewat = time.monotonic() - mulai
        assert lewat < 0.36, f"kirim tampak serial ({lewat:.2f} dtk)"
        assert all(ws.terkirim == [PESAN] for ws in lambat)


@pytest.mark.asyncio
class TestSoketGalat:
    async def test_soket_yang_MELEMPAR_juga_ditutup_dan_dilepas(self):
        """Transport yang sudah putus melempar seketika, bukan menggantung —
        jalur pembersihannya harus sama."""
        sehat = SoketPalsu("sehat")
        rusak = SoketPalsu("rusak", meledak=True)
        m = bikin(sehat, rusak)
        await siarkan(m, KEG, PESAN)
        assert rusak not in m.active[KEG]
        assert rusak.ditutup == [1011]
        assert sehat.terkirim == [PESAN]

    async def test_close_yang_ikut_GAGAL_tidak_menjatuhkan_broadcast(self):
        """Soket yang transport-nya sudah lenyap bisa membuat `close()` sendiri
        melempar. Kalau itu merambat, satu soket mati kembali menjatuhkan
        seluruh siaran — persis cacat yang sedang ditutup, cuma pindah baris."""
        sehat = SoketPalsu("sehat")
        rusak = SoketPalsu("rusak", meledak=True, tutup_meledak=True)
        m = bikin(sehat, rusak)
        await siarkan(m, KEG, PESAN)  # tak boleh melempar
        assert rusak not in m.active[KEG]
        assert sehat.terkirim == [PESAN]

    async def test_semua_soket_mati_tidak_menyisakan_apa_pun(self):
        a = SoketPalsu("a", meledak=True)
        b = SoketPalsu("b", gantung=True)
        m = bikin(a, b)
        await siarkan(m, KEG, PESAN)
        assert m.active[KEG] == {}


@pytest.mark.asyncio
class TestPengecualianTetapDihormati:
    """Perbaikan performa tidak boleh diam-diam mengubah SIAPA yang dikirimi."""

    async def test_exclude_ws_tidak_menerima(self):
        pengirim = SoketPalsu("pengirim")
        lain = SoketPalsu("lain")
        m = bikin(pengirim, lain)
        await siarkan(m, KEG, PESAN, exclude_ws=pengirim)
        assert pengirim.terkirim == []
        assert lain.terkirim == [PESAN]

    async def test_exclude_user_id_tidak_menerima(self):
        a = SoketPalsu("a")
        b = SoketPalsu("b")
        m = bikin(a, b)
        await siarkan(m, KEG, PESAN, exclude_user_id="u-a")
        assert a.terkirim == []
        assert b.terkirim == [PESAN]

    async def test_pengecualian_TIDAK_menutup_soket_yang_dilewati(self):
        # Sasaran yang dikecualikan bukan sasaran yang gagal.
        pengirim = SoketPalsu("pengirim")
        m = bikin(pengirim)
        await siarkan(m, KEG, PESAN, exclude_ws=pengirim)
        assert pengirim.ditutup == []
        assert pengirim in m.active[KEG]

    async def test_kegiatan_tak_dikenal_aman(self):
        m = bikin()
        await siarkan(m, "kegiatan-yang-tak-ada", PESAN)  # tak boleh melempar


class TestSumberBroadcast:
    """Penjaga struktural — perilaku di atas bisa dipalsukan oleh implementasi
    yang kebetulan lolos; ini mengunci mekanismenya."""

    SRC = _kode(ConnectionManager.broadcast_local)

    def test_memakai_gather_bukan_loop_serial(self):
        assert "asyncio.gather" in self.SRC

    def test_setiap_kirim_dibungkus_wait_for(self):
        assert "asyncio.wait_for" in self.SRC

    def test_return_exceptions_true(self):
        # Tanpa ini `gather` melempar pada kegagalan PERTAMA: sisa hasil tak
        # pernah diperiksa, jadi soket mati lain tak pernah dibersihkan dan
        # pemanggil (loop tail event_bus) menerima galat yang tak diharapkannya.
        assert "return_exceptions=True" in self.SRC

    def test_soket_gagal_ditutup_di_dalam_fungsi_ini(self):
        assert ".close(" in self.SRC

    def test_penutupan_juga_berpagar_waktu_dan_sejajar(self):
        # Membatasi kirim tanpa membatasi tutup memindahkan cacatnya, tak
        # menutupnya — dan `close()` bisa jauh LEBIH lama daripada `send`.
        assert self.SRC.count("asyncio.wait_for") >= 2, self.SRC.count("asyncio.wait_for")
        assert self.SRC.count("asyncio.gather") >= 2, self.SRC.count("asyncio.gather")

    def test_batasnya_dari_KONSTANTA_bukan_angka_telanjang(self):
        # Angka telanjang di badan fungsi tak bisa dibaca uji maupun disetel
        # per-lingkungan.
        assert "BATAS_KIRIM_DETIK" in self.SRC


class TestKonstanta:
    def test_batas_produksi_masuk_akal(self):
        b = ConnectionManager.BATAS_KIRIM_DETIK
        # Terlalu pendek memutus klien sehat di jaringan lambat; terlalu
        # panjang mengembalikan cacatnya dalam bentuk yang lebih halus.
        assert 1 <= b <= 15, b
