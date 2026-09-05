"""Nota Dinas persediaan yang BENAR-BENAR terbit: bernomor, beku, dan dapat
ditemukan lagi.

Permintaan pemilik: *"saya tidak melihat integrasi nomer surat dan permintaan
ttd elektroniknya."* Memang tidak ada — nota dinas persediaan adalah satu-
satunya keluaran persuratan modul ini yang lahir sebagai GET tanpa jejak:
daftarnya dihitung ulang tiap unduh, tak ada dokumen tersimpan, sehingga tak
ada tempat menyimpan nomor dan tak ada `doc_ref` yang bisa ditandatangani.

Yang dijaga berkas ini:

1. **Nomor dibooking sekali, saat TERBIT** — bukan saat unduh. Tombol unduh
   ditekan berkali-kali; membooking di sana mengisi buku agenda dengan nomor
   yang tak pernah menjadi naskah apa pun.
2. **Daftarnya dibekukan.** Nota bernomor yang dicetak ulang dari peringatan
   yang dihitung ulang berubah isi tiap kali stok bergerak, sementara
   nomornya tetap sama.
3. **Pratinjau dan naskah terbit berbentuk sama** — satu spesifikasi bentuk,
   satu penyusun PDF.
4. **Isolasi satker** pada register maupun unduhannya.
"""
import asyncio

import pypdfium2 as pdfium
import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import persediaan_nota_utils as pnu
import routes.persediaan as rp

USER = {"username": "op1", "role": "operator", "kode_satker": "401234"}
LAIN = {"username": "op2", "role": "operator", "kode_satker": "509999"}


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


def _teks_pdf(resp):
    data = b"".join(_jalan(_kumpul(resp.body_iterator)))
    assert data[:5] == b"%PDF-"
    doc = pdfium.PdfDocument(data)
    return "\n".join(doc[i].get_textpage().get_text_range()
                     for i in range(len(doc)))


async def _kumpul(it):
    return [b async for b in it]


# ── Spesifikasi bentuk (murni) ──────────────────────────────────────────

PERINGATAN = {
    "tanggal": "2026-09-05", "horizon_hari": 30,
    "habis": [{"id": "b1", "kode_barang": "K001", "nama_barang": "Kertas A4",
               "satuan": "Rim", "stok": 0, "batas_kritis": 5,
               "nup": "1", "lewat": True}],
    "kritis": [{"id": "b2", "kode_barang": "K002", "nama_barang": "Tinta Hitam",
                "satuan": "Botol", "stok": 2, "batas_kritis": 5, "nup": "1"}],
    "kedaluwarsa": [{"id": "b3", "kode_barang": "K003",
                     "nama_barang": "Hand Sanitizer", "qty": 4,
                     "expired": "2026-08-01", "lewat": True}],
    "segera_kedaluwarsa": [{"id": "b4", "kode_barang": "K004",
                            "nama_barang": "Alkohol 70%", "qty": 7,
                            "expired": "2026-09-20", "lewat": False}],
}


def test_dua_sumber_peringatan_digabung_untuk_tiap_jenis():
    assert [r["id"] for r in pnu.baris_terpilih("kritis", PERINGATAN)] == ["b1", "b2"]
    assert [r["id"] for r in pnu.baris_terpilih("kedaluwarsa", PERINGATAN)] == ["b3", "b4"]


def test_ids_MENYARING_dan_bukan_menyisipkan():
    # Id karangan tak boleh menjadi baris nota: kalau `ids` menyisipkan,
    # siapa pun bisa memasukkan barang yang sebenarnya tidak kritis.
    hasil = pnu.baris_terpilih("kritis", PERINGATAN, {"b2", "b-palsu"})
    assert [r["id"] for r in hasil] == ["b2"]


def test_pembekuan_hanya_menyimpan_yang_dicetak():
    beku = pnu.bekukan("kritis", pnu.baris_terpilih("kritis", PERINGATAN))
    assert set(beku[0]) == set(pnu.FIELD_BEKU["kritis"])
    # `lewat`/`nup` ikut terbawa dari peringatan tetapi TIDAK dicetak —
    # menyimpannya membuat register tampak menjanjikan kesetiaan yang tak
    # ia jamin.
    assert "lewat" not in beku[0] and "nup" not in beku[0]


def test_kolom_tabel_sejajar_dengan_kepalanya():
    for jenis in pnu.JENIS_NOTA:
        baris = pnu.isi_tabel(jenis, pnu.baris_terpilih(jenis, PERINGATAN))
        assert baris, jenis
        for b in baris:
            assert len(b) == len(pnu.headers(jenis)) == len(pnu.widths(jenis)), jenis


def test_tanggal_kedaluwarsa_diformat_pemanggil():
    baris = pnu.isi_tabel("kedaluwarsa", PERINGATAN["kedaluwarsa"],
                          fmt_tanggal=lambda v: "TGL")
    assert baris[0][-1] == "TGL"
    # Tanpa pemformat, tanggal mentahnya tetap tercetak — bukan kosong.
    assert pnu.isi_tabel("kedaluwarsa",
                         PERINGATAN["kedaluwarsa"])[0][-1] == "2026-08-01"


def test_kalimat_seleksi_hanya_muncul_saat_daftar_dipilih_sebagian():
    for jenis in pnu.JENIS_NOTA:
        assert "sengaja tidak disertakan" not in pnu.pengantar(jenis)
        assert "sengaja tidak disertakan" in pnu.pengantar(jenis, seleksi=True)


def test_nama_berkas_pratinjau_tidak_berubah():
    # Pratinjau memakai nama lama; hanya nota TERBIT yang membawa nomor,
    # supaya dua nota terbit pada bulan yang sama tak saling menimpa.
    assert pnu.nama_berkas("kritis") == "Nota_Dinas_Stok_Kritis.pdf"
    assert pnu.nama_berkas("kedaluwarsa") == "Nota_Dinas_Kedaluwarsa.pdf"
    assert "/" not in pnu.nama_berkas("kritis", "B-7/PL.01/2026")


def test_perihal_agenda_satu_baris():
    # Judul dokumen memuat baris baru; perihal masuk ke daftar surat dan ke
    # pesan penanda tangan, dan di sana dua baris terbaca sebagai dua entri.
    for jenis in pnu.JENIS_NOTA:
        assert "\n" not in pnu.perihal_agenda(jenis)
        assert "\n" in pnu.judul(jenis)


# ── Register (dengan Mongo tiruan) ──────────────────────────────────────

@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rp, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    monkeypatch.setattr(rp, "log_audit", _diam, raising=False)
    _jalan(fake.report_settings.insert_one({
        "type": "global", "nama_instansi": "Otorita Ibu Kota Nusantara",
        "tempat_laporan": "Nusantara"}))
    _jalan(fake.persediaan.insert_many([
        {"id": "b1", "kode_barang": "K001", "kode_satker": "401234",
         "nama_barang": "Kertas A4 80gsm", "satuan": "Rim",
         "stok": 0, "batas_kritis": 5},
        {"id": "b2", "kode_barang": "K002", "kode_satker": "401234",
         "nama_barang": "Tinta Printer Hitam", "satuan": "Botol",
         "stok": 2, "batas_kritis": 5},
        # Barang ber-layer kedaluwarsa: stoknya AMAN, jadi ia hanya muncul di
        # nota kedaluwarsa. Tanpa ini, jenis "kedaluwarsa" tak pernah punya
        # baris dan setengah spesifikasi bentuknya tak teruji.
        {"id": "b3", "kode_barang": "K003", "kode_satker": "401234",
         "nama_barang": "Hand Sanitizer 500ml", "satuan": "Botol",
         "stok": 12, "batas_kritis": 2,
         "batches": [{"batch_id": "l1", "qty": 4, "harga": 25000,
                      "expired": "2020-01-31"}]},
    ]))
    return fake


@pytest.fixture()
def booking(monkeypatch):
    """Buku agenda tiruan — mencatat BERAPA KALI nomor dipesan."""
    panggilan = []
    import routes.persuratan as rsu

    async def _booking(*a, **k):
        panggilan.append(k)
        return f"B-{len(panggilan)}/PL.01/2026", f"sid-{len(panggilan)}"

    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _booking)
    return panggilan


def _terbit(user=USER, **kw):
    payload = rp.TerbitNotaDinasIn(jenis=kw.pop("jenis", "kritis"), **kw)
    return _jalan(_unwrap(rp.terbitkan_nota_dinas)(payload, user=user))


def _unduh(nid, user=USER):
    return _teks_pdf(_jalan(_unwrap(rp.unduh_nota_dinas)(nid, _user=user)))


def test_nomor_dibooking_SEKALI_saat_terbit_bukan_saat_unduh(dbx, booking):
    hasil = _terbit()
    assert hasil["nomor"] == "B-1/PL.01/2026"
    assert len(booking) == 1
    for _ in range(3):
        assert "B-1/PL.01/2026" in _unduh(hasil["id"])
    assert len(booking) == 1, "unduh ulang ikut memboroskan deret nomor"


def test_perihal_agenda_menyebut_jenis_notanya(dbx, booking):
    _terbit(jenis="kedaluwarsa")
    assert booking[0]["perihal"] == pnu.perihal_agenda("kedaluwarsa")
    assert booking[0]["jenis_naskah"] == "Nota Dinas"
    assert booking[0]["kode_satker"] == "401234"


def test_daftar_dibekukan_stok_yang_bergerak_tak_mengubah_naskah(dbx, booking):
    hasil = _terbit()
    assert "Kertas A4 80gsm" in _unduh(hasil["id"])
    # Barang direstok sampai di atas batas kritis — ia keluar dari peringatan.
    _jalan(dbx.persediaan.update_one({"id": "b1"}, {"$set": {"stok": 999}}))
    # Pratinjau memang ikut berubah…
    pratinjau = _teks_pdf(_jalan(rp.nota_dinas_persediaan(
        jenis="kritis", horizon_hari=30, ids="", _user=USER)))
    assert "Kertas A4 80gsm" not in pratinjau
    # …tetapi naskah yang SUDAH TERBIT tidak.
    assert "Kertas A4 80gsm" in _unduh(hasil["id"])


def test_nota_kosong_tidak_pernah_terbit(dbx, booking):
    _jalan(dbx.persediaan.update_many({}, {"$set": {"stok": 999}}))
    with pytest.raises(HTTPException) as e:
        _terbit()
    assert e.value.status_code == 400
    assert not booking, "nomor terpesan untuk nota yang tak jadi terbit"
    assert _jalan(dbx.persediaan_nota.count_documents({})) == 0


def test_ids_menyaring_naskah_terbit(dbx, booking):
    hasil = _terbit(ids=["b2", "id-karangan"])
    assert hasil["jumlah_barang"] == 1
    t = _unduh(hasil["id"])
    assert "Tinta Printer Hitam" in t and "Kertas A4 80gsm" not in t
    assert "sengaja tidak disertakan" in t


def test_daftar_lengkap_tidak_mengaku_tersaring(dbx, booking):
    hasil = _terbit()
    assert "sengaja tidak disertakan" not in _unduh(hasil["id"])
    # `seleksi` DIBEKUKAN: barang kritis baru yang muncul kemudian tak boleh
    # membuat naskah lama tampak tersaring.
    _jalan(dbx.persediaan.insert_one(
        {"id": "b9", "kode_barang": "K009", "kode_satker": "401234",
         "nama_barang": "Map Folio", "satuan": "Buah", "stok": 0,
         "batas_kritis": 3}))
    assert "sengaja tidak disertakan" not in _unduh(hasil["id"])


def test_gagal_booking_tidak_membatalkan_penerbitan(dbx, monkeypatch):
    import routes.persuratan as rsu

    async def _gagal(*a, **k):
        raise RuntimeError("buku agenda tak merespons")

    monkeypatch.setattr(rsu, "booking_nomor_otomatis", _gagal)
    hasil = _terbit()
    assert hasil["nomor"] == ""
    assert _jalan(dbx.persediaan_nota.count_documents({"id": hasil["id"]})) == 1
    # Nomornya tampil sebagai garis isian, bukan hilang dari kepala naskah.
    assert "..." in _unduh(hasil["id"])


def test_kpb_dibekukan_pergantian_pejabat_tak_menulis_ulang_naskah(dbx, booking,
                                                                  monkeypatch):
    async def _kpb_a(*a, **k):
        return {"nama": "Budi Santoso", "nip": "198001012005011001",
                "jabatan": "Kepala Biro Umum"}

    monkeypatch.setattr(rp, "_kpb_signer", _kpb_a)
    hasil = _terbit()
    assert "Budi Santoso" in _unduh(hasil["id"])

    async def _kpb_b(*a, **k):
        return {"nama": "Siti Rahayu", "nip": "199002022010012002",
                "jabatan": "Kepala Biro Umum"}

    monkeypatch.setattr(rp, "_kpb_signer", _kpb_b)
    assert "Budi Santoso" in _unduh(hasil["id"])
    assert "Siti Rahayu" not in _unduh(hasil["id"])


# ── Isolasi satker ──────────────────────────────────────────────────────

def test_register_tidak_membocorkan_nota_satker_lain(dbx, booking):
    _terbit()
    _jalan(dbx.persediaan.insert_one(
        {"id": "x1", "kode_barang": "K900", "kode_satker": "509999",
         "nama_barang": "Barang Satker Lain", "satuan": "Buah", "stok": 0,
         "batas_kritis": 2}))
    _terbit(user=LAIN)
    milikku = _jalan(_unwrap(rp.daftar_nota_dinas)(
        page=1, page_size=30, jenis="", _user=USER))
    assert milikku["total"] == 1
    assert {i["kode_satker"] for i in milikku["items"]} == {"401234"}


def test_unduh_nota_satker_lain_ditolak(dbx, booking):
    _jalan(dbx.persediaan.insert_one(
        {"id": "x1", "kode_barang": "K900", "kode_satker": "509999",
         "nama_barang": "Barang Satker Lain", "satuan": "Buah", "stok": 0,
         "batas_kritis": 2}))
    punya_lain = _terbit(user=LAIN)
    with pytest.raises(HTTPException) as e:
        _unduh(punya_lain["id"], user=USER)
    assert e.value.status_code in (403, 404)


def test_saring_jenis_pada_register(dbx, booking):
    _terbit(jenis="kritis")
    hanya = _jalan(_unwrap(rp.daftar_nota_dinas)(
        page=1, page_size=30, jenis="kedaluwarsa", _user=USER))
    assert hanya["total"] == 0


def test_nota_kedaluwarsa_terbit_memakai_kolomnya_sendiri(dbx, booking):
    hasil = _terbit(jenis="kedaluwarsa")
    t = _unduh(hasil["id"])
    assert "Hand Sanitizer 500ml" in t
    # Tanggal bergaya Indonesia, bukan ISO mentah — pemformat memang sampai
    # ke penyusun PDF-nya.
    assert "31 Januari 2020" in t and "2020-01-31" not in t
    assert "Kedaluwarsa" in t
    # Barang yang hanya kritis tak boleh ikut ke nota kedaluwarsa.
    assert "Kertas A4 80gsm" not in t
