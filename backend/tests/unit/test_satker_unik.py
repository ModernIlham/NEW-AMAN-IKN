"""Master Satker satu kode = SATU dokumen — temuan C32.

`db.satker` adalah penjaga keunikan de-facto: `find_one({"kode_satker": ...})`
dipakai shared_utils (kop laporan), auth_utils (pengikatan akun), dan
users.py. Tanpa indeks unik, dua worker/dua admin bisa melahirkan dua master
satu kode — dan kop dokumen resmi menjadi tak deterministik.

Batas kejujuran uji ini: mongomock TIDAK menegakkan unik pada insert dan
BERBOHONG soal indeks parsial (unique+partialFilterExpression tetap menolak
dua dokumen ber-usulan_id "" padahal MongoDB asli menerimanya — diverifikasi
langsung di repo ini). Maka balapan itu sendiri tak bisa dibuktikan tertutup
di sini; yang dikunci adalah (a) dedupe MENGGABUNG dengan penyintas
deterministik, (b) urutan dedupe-SEBELUM-unik, (c) fallback non-unik +
pelaporannya, (d) hilangnya check-then-act di sinkron_satker, (e) dedupe
restore arsip lama, (f) bentuk indeks parsial via sumber.
"""
import asyncio
import inspect
import pathlib
import re

import pytest
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import DuplicateKeyError

import indexes as ix
import routes.satker as rs

BACKEND = pathlib.Path(__file__).resolve().parents[2]


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture()
def fake_db(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    monkeypatch.setattr(ix, "db", fake, raising=False)
    monkeypatch.setattr(rs, "db", fake, raising=False)
    return fake


def _satker(kode, **isi):
    d = {"id": f"id-{kode}-{len(str(isi))}", "kode_satker": kode,
         "nama_satker": f"Satker {kode}", "alamat": "", "telepon": "",
         "email": "", "created_at": "2026-01-01T00:00:00"}
    d.update(isi)
    return d


class TestDedupe:
    def test_menggabungkan_kop_bukan_membuangnya(self, fake_db):
        # Dua admin mengisi kop pada dua dokumen berbeda tanpa pernah tahu —
        # delete_many polos membuang persis data yang hendak diselamatkan.
        _jalan(fake_db.satker.insert_many([
            _satker("IKN01", alamat="Jl. Nusantara 1", logo_url="l.png"),
            _satker("IKN01", telepon="0541", email="a@ikn.go.id"),
        ]))
        _jalan(ix._rapikan_duplikat_satker())
        assert _jalan(fake_db.satker.count_documents({})) == 1
        sisa = _jalan(fake_db.satker.find_one({}))
        assert sisa["alamat"] == "Jl. Nusantara 1"
        assert sisa["logo_url"] == "l.png"
        assert sisa["telepon"] == "0541"
        assert sisa["email"] == "a@ikn.go.id"

    def test_penyintas_deterministik_tak_peduli_urutan_insert(self, fake_db):
        # Dua dokumen sama lengkap → created_at tertua menang; tanpa
        # tie-break penuh, dedupe cuma memindahkan nondeterminisme dari
        # waktu-baca ke waktu-dedupe.
        tua = _satker("IKN02", alamat="A", created_at="2024-01-01")
        muda = _satker("IKN02", alamat="B", created_at="2026-01-01")
        tua["id"], muda["id"] = "id-tua", "id-muda"

        _jalan(fake_db.satker.insert_many([dict(tua), dict(muda)]))
        _jalan(ix._rapikan_duplikat_satker())
        assert _jalan(fake_db.satker.find_one({}))["id"] == "id-tua"

        _jalan(fake_db.satker.delete_many({}))
        _jalan(fake_db.satker.insert_many([dict(muda), dict(tua)]))
        _jalan(ix._rapikan_duplikat_satker())
        assert _jalan(fake_db.satker.find_one({}))["id"] == "id-tua"

    def test_idempoten_dan_kode_tunggal_tak_tersentuh(self, fake_db):
        _jalan(fake_db.satker.insert_many([
            _satker("A1"), _satker("B2"),
            _satker("C3"), _satker("C3"), _satker("C3"),
        ]))
        utuh_sebelum = _jalan(fake_db.satker.find_one({"kode_satker": "A1"}))
        n1 = _jalan(ix._rapikan_duplikat_satker())
        assert n1 == 2
        assert _jalan(fake_db.satker.count_documents({})) == 3
        n2 = _jalan(ix._rapikan_duplikat_satker())
        assert n2 == 0
        assert _jalan(fake_db.satker.count_documents({})) == 3
        assert _jalan(fake_db.satker.find_one({"kode_satker": "A1"})) == utuh_sebelum


class TestUrutanDedupeSebelumUnik:
    def test_unik_hanya_bisa_dibuat_SETELAH_dedupe(self, fake_db):
        # Data ganda memang beracun bagi indeks unik — lalu dedupe
        # menawarkannya. Mutasi "dedupe dipindah ke setelah indeks" mati
        # di sini.
        _jalan(fake_db.satker.insert_many([_satker("X1"), _satker("X1")]))
        with pytest.raises(DuplicateKeyError):
            _jalan(fake_db.satker.create_index(
                "kode_satker", unique=True, name="satker_kode_unik"))
        _jalan(ix._rapikan_duplikat_satker())
        _jalan(fake_db.satker.create_index(
            "kode_satker", unique=True, name="satker_kode_unik"))
        info = _jalan(fake_db.satker.index_information())
        assert "satker_kode_unik" in info

    def test_urutan_di_sumber_create_indexes(self):
        # Pemanggilan dedupe harus MENDAHULUI percobaan unik di sumbernya.
        src = inspect.getsource(ix.create_indexes)
        i_dedupe = src.index("_rapikan_duplikat_satker()")
        i_drop = src.index('drop_index("satker_kode_lookup")')
        i_unik = src.index('name="satker_kode_unik"')
        assert i_dedupe < i_drop < i_unik


class _SatkerPalsu:
    """Koleksi palsu perekam urutan; bisa disuruh menolak unique=True."""

    def __init__(self, tolak_unik=False):
        self.name = "satker"
        self.urutan = []
        self.tolak_unik = tolak_unik

    async def create_index(self, *a, **kw):
        self.urutan.append(("create_index", kw.get("name")))
        if self.tolak_unik and kw.get("unique"):
            raise RuntimeError("E11000 duplicate key")

    async def drop_index(self, nama):
        self.urutan.append(("drop_index", nama))

    def aggregate(self, pipeline):
        async def _kosong():
            if False:
                yield None
        return _kosong()


class TestFallback:
    def _blok_satker(self, coll):
        """Jalankan HANYA blok satker dari create_indexes lewat koleksi palsu:
        dedupe (kosong), drop fallback, percobaan unik, fallback bila gagal.
        Meniru alur di sumber — uji urutan di atas menjaga sumbernya sendiri."""
        async def _blok():
            try:
                await coll.drop_index("satker_kode_lookup")
            except Exception:
                pass
            try:
                await coll.create_index("kode_satker", unique=True,
                                        name="satker_kode_unik")
            except Exception:
                ix._KEGAGALAN_INDEKS.append({
                    "koleksi": "satker", "indeks": "satker_kode_unik",
                    "galat": "duplikat kode_satker tersisa"})
                await ix._idx(coll, "kode_satker", name="satker_kode_lookup")
        _jalan(_blok())

    def test_fallback_nonunik_terbentuk_dan_DILAPORKAN(self):
        ix._KEGAGALAN_INDEKS.clear()
        c = _SatkerPalsu(tolak_unik=True)
        self._blok_satker(c)
        assert ("create_index", "satker_kode_lookup") in c.urutan
        assert any(g["koleksi"] == "satker" for g in ix._KEGAGALAN_INDEKS)
        ix._KEGAGALAN_INDEKS.clear()

    def test_fallback_lama_didrop_SEBELUM_percobaan_unik(self):
        # IndexOptionsConflict (kode 85): tanpa drop, satu boot yang pernah
        # jatuh ke fallback mengunci koleksi di non-unik SELAMANYA — mongomock
        # tak akan menangkapnya, hanya uji urutan ini.
        c = _SatkerPalsu()
        self._blok_satker(c)
        i_drop = c.urutan.index(("drop_index", "satker_kode_lookup"))
        i_unik = c.urutan.index(("create_index", "satker_kode_unik"))
        assert i_drop < i_unik

    def test_percobaan_unik_TIDAK_lewat_idx(self):
        """JEBAKAN UTAMA C32×C31: `_idx()` tidak pernah melempar, jadi
        `_idx(..., unique=True)` menelan kegagalannya — koleksi berakhir
        TANPA indeks dan tanpa fallback, sementara pembacanya mengira sudah
        terlindungi."""
        src = inspect.getsource(ix.create_indexes)
        blok = src[src.index("Master Satker"):src.index("komentar_aset")]
        assert not re.search(r"_idx\([^)]*satker[^)]*unique", blok)
        assert "await db.satker.create_index" in blok
        # Uji sumber test_indeks_tahan_gagal melarang create_index telanjang
        # di indentasi level-fungsi (8 spasi) — milik kita wajib 12 (dalam try).
        assert not re.search(r"^ {8}await db\.satker\.create_index",
                             src, re.M)


class TestSinkronSatkerTanpaCheckThenAct:
    def _panggil(self, fake_db):
        fn = rs.sinkron_satker
        return _jalan(fn.__wrapped__(admin={"username": "uji"})
                      if hasattr(fn, "__wrapped__")
                      else fn(admin={"username": "uji"}))

    def test_tidak_memakai_insert_one(self, fake_db, monkeypatch):
        """Uji perilaku, bukan regex: jalur insert_one diberi ranjau. Kalau
        check-then-act kembali, uji ini meledak — penulisan ulang kosmetik
        (ganti nama variabel, pindah baris) tak menyelamatkannya.

        Ranjau dipasang di KELAS koleksi, bukan instansi: mongomock_motor
        mengembalikan wrapper BARU pada tiap akses `db.satker` (diverifikasi
        `db.satker is db.satker == False`), jadi setattr pada satu instansi
        tak menyentuh instansi yang dipakai di dalam sinkron_satker — mutasi
        pengembalian check-then-act SELAMAT dari versi pertama uji ini.
        """
        kls = type(fake_db.satker)
        asli = kls.insert_one

        async def _ranjau(self, *a, **kw):
            if getattr(self, "name", "") == "satker":
                raise AssertionError("jalur check-then-act masih hidup")
            return await asli(self, *a, **kw)
        monkeypatch.setattr(kls, "insert_one", _ranjau)
        _jalan(fake_db.inventory_activities.insert_many([
            {"kode_satker": "K1", "nama_satker": "Satu"},
            {"kode_satker": "K1", "nama_satker": "Satu"},
            {"kode_satker": "K2", "nama_satker": "Dua"},
        ]))
        hasil = self._panggil(fake_db)
        assert hasil["baru"] == 2
        assert _jalan(fake_db.satker.count_documents({})) == 2

    def test_tidak_menimpa_kop_isian_admin(self, fake_db):
        # $setOnInsert, bukan $set: master yang sudah ada tak boleh tersentuh.
        _jalan(fake_db.satker.insert_one(
            _satker("K1", alamat="Alamat isian admin")))
        _jalan(fake_db.inventory_activities.insert_one(
            {"kode_satker": "K1", "nama_satker": "Satu",
             "alamat_satker": "Alamat dari kegiatan"}))
        hasil = self._panggil(fake_db)
        assert hasil["baru"] == 0
        assert _jalan(fake_db.satker.find_one(
            {"kode_satker": "K1"}))["alamat"] == "Alamat isian admin"


class TestRestoreArsipLama:
    def test_arsip_berduplikat_tidak_menggagalkan_restore(self, fake_db):
        # insert_many ordered melawan indeks unik = BulkWriteError = SELURUH
        # restore gagal SETELAH delete_many — persis momen paling berisiko.
        # Blok `if col_name == "satker":` di run_restore_task mengambil yang
        # pertama per kode; di sini logika saringan yang sama diuji langsung.
        docs = [_satker("D1"), _satker("D1"), _satker("D2")]
        _lihat = set()
        docs = [d for d in docs
                if not (d.get("kode_satker") in _lihat
                        or _lihat.add(d.get("kode_satker")))]
        _jalan(fake_db.satker.create_index(
            "kode_satker", unique=True, name="satker_kode_unik"))
        _jalan(fake_db.satker.insert_many(docs))
        assert _jalan(fake_db.satker.count_documents({})) == 2

    def test_blok_satker_ada_di_run_restore_task(self):
        src = (BACKEND / "routes" / "backup.py").read_text(encoding="utf-8")
        i_blok = src.index('if col_name == "satker":')
        i_insert = src.index("insert_many(docs)", i_blok)
        assert i_blok < i_insert


class TestKomentarAset:
    SRC = (BACKEND / "indexes.py").read_text(encoding="utf-8")

    def test_indeks_usulan_parsial_bukan_unik_polos(self):
        """Asersi SUMBER karena mongomock berbohong soal indeks parsial
        (unique+partial atas dua usulan_id "" tetap DuplicateKeyError padahal
        MongoDB asli menerima). `usulan_id` bisa "" untuk komentar non-usulan
        — unik polos menolak komentar non-usulan KEDUA di produksi."""
        i = self.SRC.index("komentar_usulan_unik")
        blok = self.SRC[i - 300:i + 300]
        assert "partialFilterExpression" in blok
        assert '{"usulan_id": {"$gt": ""}}' in blok
        assert "komentar_usulan_lookup" in self.SRC  # cabang fallback ada

    def test_indeks_daftar_menutupi_kuerinya(self):
        assert '[("activity_id", 1), ("created_at", 1)]' in self.SRC
        src_peta = (BACKEND / "routes" / "peta_kolaborasi.py").read_text(
            encoding="utf-8")
        i = src_peta.index("async def daftar_komentar_aset")
        badan = src_peta[i:i + 1500]
        assert "activity_id" in badan
        assert '.sort("created_at", 1)' in badan
