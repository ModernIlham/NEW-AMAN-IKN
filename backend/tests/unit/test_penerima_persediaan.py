"""Pengeluaran barang persediaan menyebut SIAPA penerimanya.

Permintaan pemilik: *"SPPB yang ditandatangani penerima barang persediaan
terkoneksi dengan master pegawai."* Prasyaratnya belum ada: transaksi keluar
hanya mencatat `unit_penerima` sebagai teks bebas — bukti pengeluaran tak
pernah menyebut siapa yang menerima, sehingga tak ada yang bisa dimintai
pertanggungjawaban maupun diminta menandatangani.

Aturan penerimanya SUDAH ADA dan sudah benar, tetapi hidup sebagai satu blok
di dalam badan `routes/bast.py`. Menyalinnya ke persediaan berarti dua tempat
yang harus sepakat selamanya — dan yang paling mudah tercecer justru cabang
penolakan almarhum, yang jarang dijalankan dan karena itu jarang diperiksa.
Karena itu ia diekstrak ke `penerima_utils` dan DIPAKAI keduanya.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import penerima_utils as pnu
import routes.persediaan as rp

USER = {"username": "op1", "role": "operator", "kode_satker": "401234"}


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


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    monkeypatch.setattr(rp, "jadwalkan_sync", _diam, raising=False)
    # mongomock: `find_one_and_update` mengembalikan None bila `projection`
    # DAN `return_document` diberikan bersamaan — keduanya sendiri-sendiri
    # baik-baik saja. Keterbatasan test double, bukan cacat kode: MongoDB
    # sungguhan melayani keduanya. Transaksi keluar memakai OCC lewat jalur
    # itu, jadi tanpa siasat ini setiap pengeluaran barang tampak sebagai
    # "barang sedang diubah pengguna lain".
    #
    # Siasat yang SAMA sudah tersalin di test_tgr, test_henti_mandiri,
    # test_pemanfaatan_usulan, dan test_penggunaan_henti_guna — pantas
    # dipindah ke conftest, tetapi itu perubahan tersendiri.
    from mongomock_motor import AsyncMongoMockCollection
    _asli_fau = AsyncMongoMockCollection.find_one_and_update

    async def _fau(self, filter, update, **kw):
        kw.pop("projection", None)
        doc = await _asli_fau(self, filter, update, **kw)
        if doc:
            doc.pop("_id", None)
        return doc

    monkeypatch.setattr(AsyncMongoMockCollection, "find_one_and_update", _fau)
    _jalan(fake.persediaan.insert_one({
        "id": "b1", "kode_barang": "K001", "kode_satker": "401234",
        "nama_barang": "Kertas A4 80gsm", "satuan": "Rim", "version": 1,
        "stok": 10, "batas_kritis": 2,
        "batches": [{"batch_id": "l1", "qty": 10, "harga": 50000,
                     "expired": "", "tanggal": "2026-01-02"}]}))
    _jalan(fake.pegawai.insert_many([
        {"id": "p1", "kode_satker": "401234", "nama": "Budi Santoso",
         "nip": "198001012005011001", "jabatan": "Pengelola BMN",
         "unit_kerja": "Bagian Umum", "status": "aktif",
         "status_kepegawaian": "PNS"},
        {"id": "p2", "kode_satker": "401234", "nama": "Almarhum Contoh",
         "nip": "196001011985031001", "jabatan": "Staf",
         "unit_kerja": "Bagian TU", "status": "meninggal"},
        {"id": "p3", "kode_satker": "401234", "nama": "Siti Pensiun",
         "nip": "196505052000032001", "jabatan": "Staf",
         "unit_kerja": "Bagian Keuangan", "status": "pensiun"},
    ]))
    return fake


def _keluar(**kw):
    data = rp.TransaksiKeluarIn(jenis="habis_pakai", jumlah=kw.pop("jumlah", 2),
                                **kw)
    return _jalan(_unwrap(rp.transaksi_keluar)("b1", data, user=USER))


# ── Helper murni ────────────────────────────────────────────────────────

def test_snapshot_mendahulukan_unit_master_bukan_isian_bebas():
    # Mendahulukan isian bebas membuat dokumen menyebut unit yang diketik
    # seseorang alih-alih unit yang sesungguhnya di master.
    s = pnu.snapshot_penerima({"nama": "Budi", "nip": "1",
                               "unit_kerja": "Bagian Umum"}, "Salah Ketik")
    assert s["penerima_unit"] == "Bagian Umum"


def test_isian_bebas_dipakai_hanya_saat_master_tak_punya_unit():
    s = pnu.snapshot_penerima({"nama": "Budi", "nip": "1"}, "Bagian Umum")
    assert s["penerima_unit"] == "Bagian Umum"


def test_pesan_almarhum_menyebut_jalan_keluarnya():
    # Menolak tanpa menyebut apa yang harus dilakukan membuat orang menyerah
    # atau mengarang NIP lain.
    p = pnu.pesan_almarhum("Almarhum Contoh")
    assert "ahli waris" in p and "pilih penerima lain" in p


# ── Transaksi keluar ────────────────────────────────────────────────────

def test_penerima_dibekukan_ke_jurnal(dbx):
    r = _keluar(penerima_nip="198001012005011001")
    j = r["transaksi"]
    assert j["penerima_nama"] == "Budi Santoso"
    assert j["penerima_nip"] == "198001012005011001"
    assert j["penerima_jabatan"] == "Pengelola BMN"
    assert j["penerima_terdaftar"] is True
    # Unit ikut dari master — bukti keluar menyebut unit yang sesungguhnya.
    assert j["unit_penerima"] == "Bagian Umum"
    assert "peringatan" not in r


def test_tanpa_nip_jurnal_tak_menulis_bidang_penerima_kosong(dbx):
    # Bidang yang ADA tetapi kosong terbaca sebagai "sudah diisi dan memang
    # tak bernama" — berbeda dari "tak pernah dicatat".
    j = _keluar(unit_penerima="Bagian Umum")["transaksi"]
    assert "penerima_nama" not in j and "penerima_nip" not in j
    assert j["unit_penerima"] == "Bagian Umum"


def test_penerima_meninggal_DITOLAK_dan_stok_tak_berkurang(dbx):
    with pytest.raises(HTTPException) as e:
        _keluar(penerima_nip="196001011985031001")
    assert e.value.status_code == 400
    assert "Meninggal Dunia" in e.value.detail
    item = _jalan(dbx.persediaan.find_one({"id": "b1"}))
    assert item["stok"] == 10, "barang keluar padahal penerimanya ditolak"
    assert _jalan(dbx.transaksi_persediaan.count_documents({})) == 0


def test_nip_tak_terdaftar_hanya_memperingatkan(dbx):
    # Master Pegawai bisa saja belum lengkap; memblokir karenanya menghukum
    # pengurus barang atas pekerjaan bagian kepegawaian.
    r = _keluar(penerima_nip="999999999999999999", unit_penerima="Bagian Umum")
    assert "belum terdaftar" in r["peringatan"]
    assert r["stok"] == 8, "transaksi ikut gagal padahal hanya peringatan"
    assert r["transaksi"]["penerima_terdaftar"] is False


def test_pegawai_nonaktif_diperingatkan_tetapi_tetap_boleh(dbx):
    r = _keluar(penerima_nip="196505052000032001")
    assert "pensiun" in r["peringatan"]
    assert r["stok"] == 8


def test_penerima_satker_lain_tak_dikenali(dbx):
    # Flag "terdaftar" dan nama penerima harus dari Master Pegawai SATKER INI.
    _jalan(dbx.pegawai.insert_one({
        "id": "p9", "kode_satker": "509999", "nama": "Orang Satker Lain",
        "nip": "197001011995031001", "status": "aktif"}))
    r = _keluar(penerima_nip="197001011995031001")
    assert "belum terdaftar" in r["peringatan"]
    assert r["transaksi"]["penerima_nama"] == ""


def test_penolakan_terjadi_sebelum_layer_disentuh(dbx, monkeypatch):
    """Memeriksa penerima DI DALAM loop percobaan berarti penolakan bisa
    terjadi setelah stok terlanjur berkurang pada percobaan sebelumnya."""
    dipanggil = []
    asli = rp.konsumsi_fifo

    def _rekam(*a, **k):
        dipanggil.append(1)
        return asli(*a, **k)

    monkeypatch.setattr(rp, "konsumsi_fifo", _rekam)
    with pytest.raises(HTTPException):
        _keluar(penerima_nip="196001011985031001")
    assert not dipanggil, "layer FIFO dihitung padahal penerimanya ditolak"


# ── Transaksi massal ────────────────────────────────────────────────────

def _massal(**kw):
    payload = rp.TransaksiMassalIn(
        arah="keluar", jenis="habis_pakai",
        items=[rp.ItemMassalIn(persediaan_id="b1", jumlah=1)], **kw)
    return _jalan(_unwrap(rp.transaksi_massal)(payload, user=USER))


def test_massal_membekukan_penerima_yang_sama_untuk_seluruh_baris(dbx):
    hasil = _massal(penerima_nip="198001012005011001")
    assert hasil["sukses"] == 1
    j = _jalan(dbx.transaksi_persediaan.find_one({}))
    assert j["penerima_nama"] == "Budi Santoso"


def test_massal_menolak_almarhum_sebelum_satu_pun_barang_keluar(dbx):
    # Jalur massal tak berkompensasi antarbaris: penolakan yang datang di
    # tengah daftar meninggalkan separuh barang sudah keluar.
    with pytest.raises(HTTPException) as e:
        _massal(penerima_nip="196001011985031001")
    assert e.value.status_code == 400
    item = _jalan(dbx.persediaan.find_one({"id": "b1"}))
    assert item["stok"] == 10
    assert _jalan(dbx.transaksi_persediaan.count_documents({})) == 0


def test_massal_meneruskan_peringatan_ke_pemanggilnya(dbx):
    hasil = _massal(penerima_nip="999999999999999999")
    assert "belum terdaftar" in hasil["peringatan"]
    assert hasil["sukses"] == 1


def test_massal_arah_masuk_tak_memeriksa_penerima(dbx):
    # Penerimaan barang tak punya "penerima" dalam arti ini; memeriksanya akan
    # menolak transaksi masuk yang sah hanya karena NIP kosong.
    payload = rp.TransaksiMassalIn(
        arah="masuk", jenis="pembelian",
        items=[rp.ItemMassalIn(persediaan_id="b1", jumlah=1,
                               harga_satuan=1000)])
    hasil = _jalan(_unwrap(rp.transaksi_massal)(payload, user=USER))
    assert hasil["sukses"] == 1
    assert "peringatan" not in hasil


# ── Sisi BAST: gerbang yang SAMA, dan sebelumnya tak berpenjaga ─────────
#
# Aturan penerima lahir di `routes/bast.py`, tetapi cabang penolakan
# almarhum — cabang yang jarang dijalankan — TIDAK punya satu pun uji. Mutasi
# yang menurunkannya menjadi peringatan lolos seluruh berkas uji BAST. Karena
# blok itu kini dipindah ke `penerima_utils`, penjaganya dipasang di sini.

import routes.bast as rb


@pytest.fixture()
def dbb(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rb, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    _jalan(fake.assets.insert_one({
        "id": "as-1", "asset_code": "3100102001", "NUP": "7",
        "asset_name": "Laptop Dinas", "kode_satker": "401234",
        "purchase_price": "12000000", "version": 1}))
    _jalan(fake.pegawai.insert_many([
        {"id": "p1", "kode_satker": "401234", "nama": "Budi Santoso",
         "nip": "198001012005011001", "status": "aktif"},
        {"id": "p2", "kode_satker": "401234", "nama": "Almarhum Contoh",
         "nip": "196001011985031001", "status": "meninggal"},
    ]))
    return fake


def _bast(nip):
    payload = rb.BastIn(
        jenis="penggunaan_melekat", asset_ids=["as-1"],
        pihak_pertama=rb.PihakIn(nama="Pengelola BMN", nip="",
                                 jabatan="Petugas Penatausahaan"),
        pihak_kedua=rb.PihakIn(nama="Penerima", nip=nip, jabatan="Analis"),
        tanggal="2026-09-05")
    return _jalan(_unwrap(rb.buat_bast)(payload, user=USER))


def test_bast_menolak_penerima_almarhum(dbb):
    with pytest.raises(HTTPException) as e:
        _bast("196001011985031001")
    assert e.value.status_code == 400
    assert "Meninggal Dunia" in e.value.detail
    assert _jalan(dbb.bast_serah_terima.count_documents({})) == 0


def test_bast_menandai_penerima_yang_terdaftar(dbb):
    _bast("198001012005011001")
    b = _jalan(dbb.bast_serah_terima.find_one({}))
    assert b["pihak_kedua_terdaftar"] is True


def test_bast_penerima_tak_terdaftar_tetap_tersimpan(dbb):
    _bast("999999999999999999")
    b = _jalan(dbb.bast_serah_terima.find_one({}))
    assert b["pihak_kedua_terdaftar"] is False
