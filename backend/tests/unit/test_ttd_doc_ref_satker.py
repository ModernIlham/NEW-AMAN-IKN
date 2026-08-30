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
    import tautan_pendek_utils as tp
    for mod in (rt, su, tp):
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
        await dbx.signature_requests.insert_one(_sr_lengkap())
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
            _sr_lengkap(posisi_qr={"halaman": 1, "x": 0.1, "y": 0.1, "lebar": 0.2}))
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


def test_posisi_qr_ditolak_sebelum_validasi_final(dbx):
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok(
            status="menunggu_validasi",
            signers=[{"signer_id": "s1", "status": "menunggu_validasi",
                      "signature_file_id": "f1"}]))
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(
                posisi_qr={"halaman": 1, "x": .1, "y": .1, "lebar": .2}),
            user=USER_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 409
    assert "divalidasi" in str(e.value.detail)


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
         "signature_file_id": "f2", "jti": "j2"}], status="selesai")
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


# ── Operator ikut mengatur letak QR (bukan admin saja) ─────────────────────
#
# Mandat pemilik: langkah "atur letak QR" MENAHAN unduhan semua pihak, jadi ia
# tak boleh menunggu satu orang ber-role admin. Operator satker yang sama harus
# bisa membereskannya sendiri — berikut melihat penandanya di daftar.
#
# Yang TIDAK ikut dilonggarkan: isolasi lintas-satker (tetap 403), viewer
# (tetap pembaca murni), dan tindakan tak tertarik-kembali (batal permintaan
# tetap pembuat/admin).

OPERATOR_A = {"username": "operator-a", "role": "operator",
              "kode_satker": "111111"}          # satker sama, BUKAN pembuat
OPERATOR_B = {"username": "operator-b", "role": "operator",
              "kode_satker": "222222"}          # satker lain
PEMBACA_A = {"username": "pembaca-a", "role": "viewer",
             "kode_satker": "111111"}


def test_operator_satker_sama_boleh_atur_posisi_qr(dbx):
    """Inti mandat: operator yang BUKAN pembuat permintaan tetap boleh
    menempatkan QR — pekerjaan tak menggantung menunggu admin."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())
        r = await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr={"halaman": 1, "x": 0.3,
                                               "y": 0.7, "lebar": 0.2}),
            user=OPERATOR_A)
        return r, await dbx.signature_requests.find_one({"id": "sr-dok"})
    r, doc = _jalan(skenario())
    assert r["posisi_qr"]["lebar"] == 0.2
    assert doc["posisi_qr"]["halaman"] == 1     # benar-benar tersimpan


def test_operator_satker_lain_tetap_ditolak_atur_qr(dbx):
    """Yang dilonggarkan hanya sekat PERAN di dalam satker — sekat SATKER
    tetap berdiri."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr=None), user=OPERATOR_B)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_viewer_tak_boleh_atur_posisi_qr(dbx):
    """Viewer tetap pembaca murni: bukan pengelola, walau satkernya sama."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        return await rt.atur_posisi_qr(
            "sr-dok", rt.PosisiQrIn(posisi_qr=None), user=PEMBACA_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_operator_melihat_penanda_perlu_atur_qr_milik_orang_lain(dbx):
    """Penandanya harus SAMPAI ke operator — kalau daftarnya hanya berisi
    buatannya sendiri, ia tak pernah tahu ada yang perlu dibereskan."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())  # dibuat USER_A
        return await rt.daftar_permintaan(_user=OPERATOR_A)
    r = _jalan(skenario())
    assert len(r["items"]) == 1
    assert r["items"][0]["perlu_atur_qr"] is True


def test_daftar_viewer_tetap_sebatas_buatannya_sendiri(dbx):
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())  # dibuat USER_A
        return await rt.daftar_permintaan(_user=PEMBACA_A)
    assert _jalan(skenario())["items"] == []


def test_operator_bukan_pembuat_tetap_tak_boleh_membatalkan(dbx):
    """Sengaja TIDAK ikut dilonggarkan: pembatalan berkaskade menandai
    BAST/aset 'dicabut' — tak bisa ditarik kembali, jadi tetap pembuat/admin."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_dok())
        return await rt.batal_permintaan("sr-dok", user=OPERATOR_A)
    with pytest.raises(HTTPException) as e:
        _jalan(skenario())
    assert e.value.status_code == 403


def test_operator_boleh_membaca_detail_untuk_membuka_dialog_qr(dbx):
    """Dialog "Atur QR & Unduh" berangkat dari detail — kalau detailnya 403,
    operator melihat penanda tapi tak bisa menindaklanjutinya."""
    async def skenario():
        await dbx.signature_requests.insert_one(_sr_lengkap())
        return await rt.detail_permintaan("sr-dok", user=OPERATOR_A)
    r = _jalan(skenario())
    assert r["perlu_atur_qr"] is True and r["siap_diunduh"] is False


# ── Tautan e-sign dipendekkan ──────────────────────────────────────────────
#
# Mandat pemilik: "link yang dibagikan terlalu panjang". Tautan lama ±396
# karakter (315 di antaranya token tanda tangan) — satu pesan WA penuh oleh
# satu tautan. Kini yang dibagikan berbentuk /s/{kode} ±46 karakter, dan
# token TIDAK lagi ikut di dalam pesan yang beredar/diteruskan.

def test_link_e_sign_yang_dibagikan_berbentuk_pendek(dbx, monkeypatch):
    monkeypatch.setenv("APP_PUBLIC_URL", "https://amanikn-inventarisasi.com")

    async def skenario():
        return await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen", doc_type="dokumen_unggahan", doc_ref="",
                mode="paralel", signers=[rt.SignerIn(nama="Budi")]),
            user=USER_A)
    hasil = _jalan(skenario())
    link = hasil["links"][0]["link"]
    assert "/s/" in link and "token=" not in link
    assert len(link) < 60          # dari ±396 karakter


def test_link_pendek_e_sign_menunjuk_tautan_asli(dbx, monkeypatch):
    """Pendek TIDAK boleh berarti putus: kodenya harus menukar kembali ke
    alamat tanda tangan yang sah, lengkap dengan tokennya."""
    monkeypatch.setenv("APP_PUBLIC_URL", "https://amanikn-inventarisasi.com")
    import tautan_pendek_utils as tp

    async def skenario():
        hasil = await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen", doc_type="dokumen_unggahan", doc_ref="",
                mode="paralel", signers=[rt.SignerIn(nama="Budi")]),
            user=USER_A)
        kode = hasil["links"][0]["link"].rsplit("/s/", 1)[1]
        return await tp.resolve_tautan(kode)
    tujuan = _jalan(skenario())
    assert tujuan and "/ttd/" in tujuan and "token=" in tujuan


def test_batal_permintaan_mematikan_tautan_pendeknya(dbx, monkeypatch):
    """Rute panjang sudah menolak permintaan batal (410); tautan pendek tak
    boleh jadi pintu belakang yang tampak masih hidup."""
    monkeypatch.setenv("APP_PUBLIC_URL", "https://amanikn-inventarisasi.com")
    import tautan_pendek_utils as tp

    async def skenario():
        hasil = await rt.buat_permintaan(
            payload=rt.PermintaanIn(
                judul="Dokumen", doc_type="dokumen_unggahan", doc_ref="",
                mode="paralel", signers=[rt.SignerIn(nama="Budi")]),
            user=USER_A)
        kode = hasil["links"][0]["link"].rsplit("/s/", 1)[1]
        await rt.batal_permintaan(hasil["id"], user=USER_A)
        return await tp.resolve_tautan(kode)
    assert _jalan(skenario()) is None


# ── Ringkasan dokumen untuk pesan WA/email ─────────────────────────────────
#
# Mandat pemilik: pesan lama hanya "judul + tautan", sehingga penanda tangan
# harus MEMBUKA tautan sekadar untuk tahu dokumen apa itu — dan berbulan-bulan
# kemudian tak ada jejak yang bisa dicari di riwayat percakapannya. Ringkasan
# DIBEKUKAN saat permintaan dibuat, sejalan dengan PDF-nya.

async def _seed_bast(dbx, **ganti):
    doc = {"id": "bast-1", "kode_satker": USER_A["kode_satker"],
           "nomor": "BAST-77/OIKN/2026", "jenis": "mutasi_pengguna",
           "tanggal": "2026-08-04",
           "pihak_pertama": {"nama": "Budi Santoso"},
           "pihak_kedua": {"nama": "Ani Lestari"},
           "aset": [{"asset_code": "3.05.01.01.001", "NUP": 12,
                     "asset_name": "Laptop"},
                    {"asset_code": "3.05.02.01.003", "NUP": 4,
                     "asset_name": "Printer"}]}
    doc.update(ganti)
    await dbx.bast_serah_terima.insert_one(doc)


def test_ringkasan_bast_memuat_nomor_pihak_dan_barang(dbx):
    async def skenario():
        await _seed_bast(dbx)
        return await rt._ringkas_dokumen("bast", "bast-1")
    r = _jalan(skenario())
    assert r["nomor"] == "BAST-77/OIKN/2026"
    assert r["perihal"] == "Mutasi/Alih Pemegang Barang Milik Negara"
    assert r["tanggal"] == "2026-08-04"
    assert r["pihak"] == ["Budi Santoso (Pihak Pertama)", "Ani Lestari (Pihak Kedua)"]
    assert r["jumlah_barang"] == 2
    assert r["barang"][0] == {"kode": "3.05.01.01.001", "nup": "12",
                              "nama": "Laptop"}


def test_ringkasan_membatasi_barang_tapi_jumlah_tetap_jujur(dbx):
    """Pesan WA tak boleh jadi daftar 200 baris — tapi jumlahnya TIDAK boleh
    ikut dipotong, karena penerima memakainya untuk mencocokkan dokumen."""
    async def skenario():
        await _seed_bast(dbx, aset=[{"asset_code": f"3.05.{i:02d}", "NUP": i,
                                     "asset_name": f"Barang {i}"}
                                    for i in range(1, 21)])
        return await rt._ringkas_dokumen("bast", "bast-1")
    r = _jalan(skenario())
    assert len(r["barang"]) == rt.MAKS_BARANG_RINGKAS == 3
    assert r["jumlah_barang"] == 20


def test_ringkasan_pakai_judul_lainnya_bila_diisi(dbx):
    async def skenario():
        await _seed_bast(dbx, jenis="lainnya", judul_lainnya="Serah Terima Khusus")
        return await rt._ringkas_dokumen("bast", "bast-1")
    assert _jalan(skenario())["perihal"] == "Serah Terima Khusus"


def test_ringkasan_kosong_untuk_dokumen_tanpa_rujukan(dbx):
    """Dokumen unggahan bebas tak punya BAST rujukan — pesannya menyusut
    sendiri, bukan menampilkan baris kosong yang membingungkan."""
    assert _jalan(rt._ringkas_dokumen("dokumen_unggahan", "")) == {}
    assert _jalan(rt._ringkas_dokumen("bast", "tidak-ada")) == {}


def test_permintaan_bast_membekukan_ringkasannya(dbx):
    """Ikut tersimpan di record + dikembalikan ke pemanggil, supaya pesan yang
    dibagikan cocok dengan dokumen yang benar-benar diteken."""
    async def skenario():
        await _seed_bast(dbx)
        hasil = await rt.buat_permintaan(
            payload=rt.PermintaanIn(judul="BAST BAST-77/OIKN/2026",
                                    doc_type="bast", doc_ref="bast-1",
                                    mode="paralel",
                                    signers=[rt.SignerIn(nama="Budi Santoso")]),
            user=USER_A)
        sr = await dbx.signature_requests.find_one({"id": hasil["id"]})
        return hasil, sr
    hasil, sr = _jalan(skenario())
    assert hasil["ringkas"]["nomor"] == "BAST-77/OIKN/2026"
    assert sr["ringkas"]["jumlah_barang"] == 2
