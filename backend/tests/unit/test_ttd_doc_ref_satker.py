"""Uji GERBANG KEPEMILIKAN `doc_ref` pada permintaan tanda tangan.

Temuan audit adversarial (TINGGI). `kirim_tandatangan` menulis back-link ke
dokumen yang ditunjuk `doc_ref` TANPA memeriksa satker — itu disengaja, karena
pemeriksaannya dilakukan SEKALI di muka saat permintaan dibuat. Konsekuensinya:
setiap `doc_type` yang punya back-link WAJIB terdaftar di gerbang itu.

`lpb` sempat punya back-link tanpa gerbang. `POST /persediaan/lpb/{id}/kirim-ttd`
memang ber-guard, tetapi `POST /ttd/permintaan` bisa dipanggil langsung dengan
`doc_type="lpb"` + id LPB satker lain — dan saat tandatangan selesai, servernya
sendiri yang menulis ke dokumen satker itu.
"""
import asyncio
import io

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.ttd as rt

# Dua satker, dua penulis. Yang satu mencoba menunjuk dokumen yang lain.
USER_A = {"username": "penulis-a", "role": "admin", "kode_satker": "111111"}
USER_B = {"username": "penulis-b", "role": "admin", "kode_satker": "222222"}


def _unwrap(fn):
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _jalan(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rt, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "send_esign_email", _diam, raising=False)
    return fake


def _permintaan(doc_type, doc_ref):
    return rt.PermintaanIn(
        judul="Uji", doc_type=doc_type, doc_ref=doc_ref, mode="paralel",
        signers=[rt.SignerIn(nama="Penanda Tangan")])


async def _seed(dbx):
    await dbx.lpb.insert_one({"id": "lpb-B", "kode_satker": "222222",
                              "nomor": "LPB-B/2026"})
    await dbx.bast_serah_terima.insert_one({"id": "bast-B",
                                            "kode_satker": "222222"})


def test_lpb_satker_lain_ditolak_403(dbx):
    """INTI: satker A tak boleh menunjuk LPB milik satker B."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "lpb-B"),
                                              user=USER_A)
        assert e.value.status_code == 403
        assert "LPB" in str(e.value.detail)
        # Tak ada permintaan yang tersisa — penolakan terjadi sebelum insert.
        assert await dbx.signature_requests.count_documents({}) == 0
    _jalan(skenario())


def test_bast_satker_lain_tetap_ditolak_403(dbx):
    """Perlindungan lama tak boleh ikut rusak saat gerbangnya digeneralisasi."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("bast", "bast-B"),
                                              user=USER_A)
        assert e.value.status_code == 403
        assert "BAST" in str(e.value.detail)
    _jalan(skenario())


def test_lpb_milik_sendiri_diterima(dbx):
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "lpb-B"),
                                                  user=USER_B)
        assert hasil["id"]
        sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
        assert sr["doc_type"] == "lpb" and sr["doc_ref"] == "lpb-B"
        assert sr["kode_satker"] == "222222"
    _jalan(skenario())


def test_lpb_yang_tak_ada_juga_ditolak(dbx):
    """id ngawur ditolak sama kerasnya — pesannya tak membedakan 'tak ada'
    dari 'milik orang lain' (cegah oracle keberadaan dokumen)."""
    async def skenario():
        await _seed(dbx)
        with pytest.raises(HTTPException) as e:
            await _unwrap(rt.buat_permintaan)(_permintaan("lpb", "tidak-ada"),
                                              user=USER_B)
        assert e.value.status_code == 403
    _jalan(skenario())


def test_doc_type_tanpa_backlink_tak_ikut_divalidasi(dbx):
    """`doc_ref` untuk surat/register adalah teks bebas tanpa back-link —
    memvalidasinya akan mematahkan alur yang memang memakainya begitu."""
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(
            _permintaan("dokumen_unggahan", "No. 123/BEBAS/2026"), user=USER_A)
        assert hasil["id"]
    _jalan(skenario())


def test_super_admin_lintas_satker_tetap_boleh(dbx):
    """kode_satker kosong = super-admin; itu perilaku yang disengaja."""
    async def skenario():
        await _seed(dbx)
        hasil = await _unwrap(rt.buat_permintaan)(
            _permintaan("lpb", "lpb-B"),
            user={"username": "sa", "role": "admin", "kode_satker": ""})
        assert hasil["id"]
    _jalan(skenario())


# ── Regresi 500 "membubuhi & minta TTD" (laporan pemilik) ───────────────────
#
# `buat_permintaan` meng-import `scope_query_field_satker` DI DALAM cabang
# `if doc_type in {bast,lpb} ...`. Import lokal membuat namanya LOKAL untuk
# SELURUH badan fungsi (aturan scoping Python), sehingga pemakaian di gerbang
# "Meninggal Dunia" — cabang yang berjalan untuk SEMUA doc_type — meledak
# UnboundLocalError → 500 pada `POST /ttd/permintaan/unggah` maupun
# `POST /ttd/permintaan` biasa, tiap kali ada penanda tangan ber-NIP.

def test_permintaan_dokumen_unggahan_dengan_nip_tak_meledak(dbx):
    """doc_type di luar {bast,lpb} + penanda tangan ber-NIP harus SUKSES.
    Inilah jalur "unggah dokumen lalu minta TTD" yang dilaporkan 500."""
    async def skenario():
        return await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen Unggahan", doc_type="dokumen_unggahan",
                doc_ref="", mode="paralel",
                signers=[rt.SignerIn(nama="Budi Penanda",
                                     nip="198001012005011001",
                                     jabatan="Kepala")]),
            user=USER_A)
    hasil = _jalan(skenario())
    assert len(hasil["links"]) == 1
    assert hasil["links"][0]["nama"] == "Budi Penanda"


def test_gerbang_meninggal_tetap_menolak_pada_doc_type_bebas(dbx):
    """Perbaikan tak boleh mematikan gerbangnya: penanda tangan berstatus
    meninggal tetap ditolak 400 walau doc_type bukan bast/lpb."""
    async def skenario():
        await dbx.pegawai.insert_one({
            "id": "p-1", "kode_satker": USER_A["kode_satker"],
            "nama": "Almarhum Contoh", "nip": "196001011985031001",
            "status": "meninggal"})
        return await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen", doc_type="dokumen", doc_ref="",
                mode="paralel",
                signers=[rt.SignerIn(nama="Almarhum Contoh",
                                     nip="196001011985031001")]),
            user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400
    assert "Meninggal Dunia" in e.value.detail


# ── Posisi QR: SEKALI di akhir oleh pemilik, bukan per penanda tangan ───────
#
# Mandat pemilik: fitur geser & perbesar QR dicabut dari halaman penanda
# tangan (tiap orang mengaturnya membingungkan, dan yang terakhir menang),
# lalu dipasang di langkah unduh dokumen ber-TTD — sekali jalan.

def _sr_dok(**ganti):
    dasar = {"id": "sr-dok", "judul": "Dokumen", "doc_type": "dokumen_unggahan",
             "doc_ref": "", "mode": "paralel", "status": "terkirim",
             "kode_satker": USER_A["kode_satker"], "created_by": USER_A["username"],
             "dok_file_id": "abc123", "dok_nama": "d.pdf", "dok_halaman": 2,
             "signers": []}
    dasar.update(ganti)
    return dasar


def test_spesimen_tak_lagi_menerima_posisi_qr(dbx):
    """Kontrak payload penanda tangan: field `posisi_qr` DIHAPUS — kiriman
    lama yang masih menyertakannya tidak boleh menyetel apa pun."""
    assert "posisi_qr" not in rt.SpesimenIn.model_fields
    s = rt.SpesimenIn(png_base64="x", posisi=None, posisi_qr={"halaman": 1})
    assert not hasattr(s, "posisi_qr")


def test_pemilik_atur_posisi_qr_tersimpan_terjepit(dbx):
    """Posisi tersimpan dan DIJEPIT: lebar di luar 0,10–0,40 ditarik ke batas,
    halaman di luar jumlah halaman dokumen ikut dijepit."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        r = await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr={"halaman": 9, "x": 0.5,
                                               "y": 0.5, "lebar": 0.99}),
            user=USER_A)
        return r, await dbx.signature_requests.find_one({"id": "sr-dok"})
    r, doc = _jalan(skenario())
    assert r["posisi_qr"]["lebar"] == 0.40      # dijepit dari 0,99
    assert r["posisi_qr"]["halaman"] == 2       # dijepit ke jumlah halaman
    assert doc["posisi_qr"]["lebar"] == 0.40    # benar-benar tersimpan


def test_posisi_qr_null_mengembalikan_ke_otomatis(dbx):
    async def skenario():
        await dbx.signature_requests.insert_one(
            _sr_dok(posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2}))
        r = await rt.atur_posisi_qr("sr-dok", rt.PosisiQrIn(posisi_qr=None),
                                    user=USER_A)
        return r, await dbx.signature_requests.find_one({"id": "sr-dok"})
    r, doc = _jalan(skenario())
    assert r["posisi_qr"] is None and doc["posisi_qr"] is None


def test_posisi_qr_satker_lain_ditolak(dbx):
    """Isolasi satker: dokumen satker A tak bisa diatur QR-nya oleh satker B."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr=None), user=USER_B)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_posisi_qr_tanpa_dokumen_ditolak_400(dbx):
    """Permintaan tanpa lampiran dokumen tak punya halaman untuk menaruh QR."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok(dok_file_id=""))
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr={"halaman": 1, "x": 0, "y": 0,
                                               "lebar": 0.2}), user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 400


# ── Gerbang "siap diunduh": semua TTD + QR sudah ditempatkan ────────────────
#
# Mandat pemilik: setelah semua meneken, link e-sign & halaman verifikasi
# memunculkan unduhan dokumen ber-TTD — TAPI hanya bila letak QR sudah
# diatur. Status "belum diatur" itulah penanda kerja bagi admin.

def _sr_lengkap(**ganti):
    dasar = _sr_dok(signers=[
        {"signer_id": "s1", "nama": "A", "status": "ditandatangani",
         "signature_file_id": "f1", "jti": "j1"},
        {"signer_id": "s2", "nama": "B", "status": "ditandatangani",
         "signature_file_id": "f2", "jti": "j2"}])
    dasar.update(ganti)
    return dasar


def test_siap_diunduh_hanya_setelah_semua_ttd_dan_qr_diatur():
    belum_qr = _sr_lengkap()
    assert rt._semua_sudah_ttd(belum_qr) is True
    assert rt._qr_sudah_diatur(belum_qr) is False
    assert rt._siap_diunduh(belum_qr) is False          # QR belum → tertahan

    siap = _sr_lengkap(posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2})
    assert rt._siap_diunduh(siap) is True


def test_belum_semua_ttd_tak_pernah_siap_walau_qr_diatur():
    sr = _sr_dok(posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2},
                 signers=[{"signer_id": "s1", "nama": "A", "signature_file_id": "f1"},
                          {"signer_id": "s2", "nama": "B", "signature_file_id": ""}])
    assert rt._semua_sudah_ttd(sr) is False
    assert rt._siap_diunduh(sr) is False


def test_permintaan_batal_tak_pernah_siap_diunduh():
    sr = _sr_lengkap(status="batal",
                     posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2})
    assert rt._siap_diunduh(sr) is False


def test_unduh_verifikasi_publik_ditolak_saat_qr_belum_diatur(dbx):
    """Halaman verifikasi (dibuka dari QR) tak boleh menyajikan dokumen
    sebelum QR ditempatkan — 409, bukan berkas setengah jadi."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())
        return await _unwrap(rt.dokumen_ber_ttd_verifikasi)("sr-dok", request=None)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 409


def test_verifikasi_publik_menandai_menunggu_qr(dbx):
    """Halaman verifikasi menerangkan penantiannya (bukan tombol hilang
    tanpa sebab) — dan TIDAK menawarkan unduhan."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())
        return await rt.verifikasi_publik("sr-dok")
    r = _jalan(skenario())
    assert r["dapat_unduh"] is False and r["menunggu_qr"] is True


def test_daftar_permintaan_menandai_perlu_atur_qr(dbx):
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())
        return await rt.daftar_permintaan(_user=USER_A)
    r = _jalan(skenario())
    assert r["items"][0]["perlu_atur_qr"] is True
    assert r["items"][0]["siap_diunduh"] is False


# ── Pratinjau mode paralel: yang berikutnya melihat TTD yang sudah masuk ────
#
# Mandat pemilik: pada mode paralel, siapa pun yang meneken berikutnya harus
# MELIHAT tanda tangan yang sudah dibubuhkan lebih dulu. Pratinjau halaman
# karenanya dirakit ulang dengan TTD masuk, tanpa QR.
#
# Regresi yang ditangkap uji ini: bila SEMUA penanda tangan yang sudah teken
# memakai posisi pilihan sendiri DAN QR tidak digambar (pratinjau, atau
# unduhan dengan QR manual), kanvas "slot otomatis" tak pernah menerima satu
# operasi gambar pun → reportlab menghasilkan PDF NOL halaman → `pages[0]`
# melempar IndexError dan MENGGAGALKAN seluruh perakitan. Akibatnya pratinjau
# diam-diam jatuh ke dokumen asli (tanda tangan pertama tak terlihat) dan
# unduhan asli membalas 500.

def _pdf_dua_halaman() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas as rl_canvas
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    for h in (1, 2):
        c.drawString(72, 720, f"Halaman {h}")
        c.showPage()
    c.save()
    return buf.getvalue()


def _png_ttd() -> bytes:
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (120, 48), (0, 0, 0, 0))
    ImageDraw.Draw(im).line([(4, 40), (60, 8), (116, 40)], fill=(0, 0, 0, 255),
                            width=3)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _sr_kustom():
    """Satu penanda tangan sudah teken di posisi PILIHANNYA, satu belum."""
    return _sr_dok(signers=[
        {"signer_id": "s1", "nama": "A", "status": "ditandatangani",
         "signature_file_id": "f1", "jti": "j1", "signed_at": "2026-08-04",
         "posisi_ttd": {"halaman": 1, "x": 0.2, "y": 0.6, "lebar": 0.25}},
        {"signer_id": "s2", "nama": "B", "status": "menunggu",
         "signature_file_id": "", "jti": "j2"}])


def test_rakit_pdf_tanpa_slot_otomatis_tak_meledak(dbx, monkeypatch):
    png = _png_ttd()

    async def _ambil(fid):
        return png if fid == "f1" else b""
    monkeypatch.setattr(rt, "get_document_from_gridfs", _ambil, raising=False)
    out = _jalan(rt._bangun_pdf_ber_ttd(_sr_kustom(), "sr-dok",
                                        _pdf_dua_halaman(), sertakan_qr=False))
    assert out.getvalue().startswith(b"%PDF")


def test_pratinjau_menyertakan_ttd_yang_sudah_masuk(dbx, monkeypatch):
    """Bukti perilaku, bukan sekadar "tidak melempar": hasil pratinjau HARUS
    berbeda dari dokumen asli — di situlah tanda tangan pertama terlihat."""
    png = _png_ttd()

    async def _ambil(fid):
        return png if fid == "f1" else b""
    monkeypatch.setattr(rt, "get_document_from_gridfs", _ambil, raising=False)
    asli = _pdf_dua_halaman()
    hasil = _jalan(rt._dokumen_dengan_ttd_masuk(_sr_kustom(), "sr-dok", asli))
    assert hasil != asli and hasil.startswith(b"%PDF")


def test_pratinjau_tanpa_ttd_masuk_mengembalikan_dokumen_apa_adanya(dbx):
    """Belum ada yang meneken → tak ada yang perlu dirakit; kembalikan berkas
    asli (hemat, dan tak ada risiko gagal rakit di jalur pratinjau)."""
    asli = _pdf_dua_halaman()
    hasil = _jalan(rt._dokumen_dengan_ttd_masuk(_sr_dok(), "sr-dok", asli))
    assert hasil == asli
