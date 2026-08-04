"""Uji BAST × KPB per-satker + alamat multi-baris (mandat SURAT-2).

Dua mode gagal yang dilindungi di sini pernah/berpotensi terjadi senyap:

1. Blok "Mengetahui, Kuasa Pengguna Barang" pada PDF BAST dulu me-resolve KPB
   dari satker PEMINTA (`kode_satker_user`) — unduhan super-admin lintas-satker
   mencetak KPB satker lain (atau "-" padahal Referensi Pejabat satker dokumen
   punya KPB). Kini resolve mengikuti `kode_satker` DOKUMEN.
2. Identitas default PIHAK KESATU saat membuat BAST dulu membaca setelan
   kasatker mentah (bisa kosong/kedaluwarsa) dan mem-fallback PER FIELD —
   nama ketikan bisa tercampur NIP KPB. Kini: kosong = KPB aktif dari
   Referensi Pejabat satker aset; nama ketikan dipakai apa adanya.

Alamat kantor multi-baris ("2 alamat atau lebih") tidak boleh terpotong ke
baris pertama pada identitas pihak — digabung "; ".
"""
import asyncio

import pytest
from mongomock_motor import AsyncMongoMockClient

import routes.bast as rb

SATKER = "527010"
USER = {"username": "arsiparis", "role": "admin", "kode_satker": SATKER}
SUPER = {"username": "pusat", "role": "super_admin", "kode_satker": ""}


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
    import routes.persuratan as rsu
    import routes.reports as rrep
    for mod in (rb, su, rsu, rrep):
        monkeypatch.setattr(mod, "db", fake, raising=False)
        if hasattr(mod, "log_audit"):
            monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    monkeypatch.setattr(su, "log_audit", _diam, raising=False)
    return fake


async def _seed_dasar(dbx):
    await dbx.report_settings.insert_one({
        "type": "global", "nama_instansi": "OTORITA IBU KOTA NUSANTARA",
        "nama_unit_organisasi": "KUASA PENGGUNA BARANG",
        "alamat_instansi": "Gedung Kantor Otorita IKN, Nusantara\n"
                           "Perwakilan I: Menara Mandiri II Lt. 5, Jakarta",
        "kasatker_nama": "", "kasatker_nip": "",
    })
    await dbx.assets.insert_one({
        "id": "aset-1", "asset_code": "3100102001", "NUP": "1",
        "asset_name": "Laptop Kerja", "brand": "Thinkpad", "model": "X1",
        "serial_number": "SN-1", "condition": "Baik",
        "purchase_date": "2025-03-01", "purchase_price": 15_000_000,
    })
    # KPB satker dokumen (RANGKAP jabatan struktural Direktur — kasus nyata
    # pemilik) + KPB satker LAIN yang lebih baru — resolver tanpa scope
    # dokumen akan salah memilih yang lebih baru (satker lain).
    await dbx.pejabat.insert_many([
        {"id": "pj-1", "kode_satker": SATKER, "nama": "Ratna Pemilik Dokumen",
         "nip": "197001011990032001",
         "jabatan": "Direktur Pengembangan Ekosistem Digital",
         "peran": ["kuasa_pengguna_barang"], "berlaku_mulai": "2026-01-01"},
        {"id": "pj-2", "kode_satker": "999999", "nama": "Bambang Satker Lain",
         "nip": "196501011989031001", "jabatan": "Kepala Satker Lain",
         "peran": ["kuasa_pengguna_barang"], "berlaku_mulai": "2026-06-01"},
    ])


def _payload(**ganti):
    dasar = dict(jenis="penggunaan_melekat", asset_ids=["aset-1"],
                 pihak_kedua=rb.PihakIn(nama="Andi Penerima", nip="",
                                        jabatan="Staf", alamat="Gedung B Lt. 2"),
                 pihak_pertama=None, nomor="BAST-01", tanggal="2026-08-01",
                 booking_otomatis=False, terapkan_ke_aset=False)
    dasar.update(ganti)
    return rb.BastIn(**dasar)


def test_pihak_kesatu_default_kpb_registry_dan_alamat_gabung(dbx):
    """Kosong = KPB aktif dari Referensi Pejabat satker dokumen; jabatan yang
    tercatat = KAPASITAS "Kuasa Pengguna Barang" (dokumen ber-kop KPB), bukan
    jabatan struktural "Direktur ..."; alamat default menggabung SEMUA baris
    alamat kantor (bukan baris pertama saja)."""
    async def skenario():
        await _seed_dasar(dbx)
        await _unwrap(rb.buat_bast)(_payload(), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    b = _jalan(skenario())
    p1 = b["pihak_pertama"]
    assert p1["nama"] == "Ratna Pemilik Dokumen"
    assert p1["nip"] == "197001011990032001"
    assert p1["jabatan"] == "Kuasa Pengguna Barang"
    assert p1["alamat"] == ("Gedung Kantor Otorita IKN, Nusantara; "
                            "Perwakilan I: Menara Mandiri II Lt. 5, Jakarta")
    assert b["kode_satker"] == SATKER


def test_pihak_kesatu_default_kpb_plh_berawalan(dbx):
    """KPB dijabat pelaksana harian → kapasitas "Plh. Kuasa Pengguna Barang"."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.pejabat.update_one({"id": "pj-1"},
                                     {"$set": {"jenis_pelaksana": "plh"}})
        await _unwrap(rb.buat_bast)(_payload(), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    p1 = _jalan(skenario())["pihak_pertama"]
    assert p1["jabatan"] == "Plh. Kuasa Pengguna Barang"


def test_pihak_kesatu_ketikan_tidak_dicampur_kpb(dbx):
    """Nama diketik di form → NIP/jabatan kosong TIDAK diisi silang dengan
    data KPB (identitas campur-aduk pada dokumen resmi); alamat manual menang."""
    async def skenario():
        await _seed_dasar(dbx)
        await _unwrap(rb.buat_bast)(_payload(
            jenis="mutasi_pengguna",
            pihak_pertama=rb.PihakIn(nama="Pak Pemegang Lama", nip="",
                                     jabatan="", alamat="Pos Jaga Timur"),
        ), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    p1 = _jalan(skenario())["pihak_pertama"]
    assert p1["nama"] == "Pak Pemegang Lama"
    assert p1["nip"] == ""          # bukan NIP KPB
    assert p1["jabatan"] == ""      # bukan jabatan KPB
    assert p1["alamat"] == "Pos Jaga Timur"


def test_tanpa_kpb_registry_dan_setelan_kosong_tetap_titik(dbx):
    """Registry kosong + setelan kasatker kosong → identitas tetap "" (PDF
    mencetak garis titik), BUKAN literal "-" dari placeholder resolver."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.pejabat.delete_many({})
        await _unwrap(rb.buat_bast)(_payload(), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    p1 = _jalan(skenario())["pihak_pertama"]
    assert p1["nama"] == ""
    assert p1["nip"] == ""
    assert p1["jabatan"] == "Kuasa Pengguna Barang"


def _teks_pdf(resp):
    import io
    import pypdfium2 as pdfium
    body = resp.body if hasattr(resp, "body") else None
    if body is None:
        buf = io.BytesIO()

        async def kumpul():
            async for potong in resp.body_iterator:
                buf.write(potong if isinstance(potong, bytes)
                          else potong.encode())
        _jalan(kumpul())
        body = buf.getvalue()
    pdf = pdfium.PdfDocument(body)
    try:
        return "\n".join(h.get_textpage().get_text_range() for h in pdf)
    finally:
        pdf.close()


def test_pdf_mengetahui_kpb_ikut_satker_dokumen(dbx):
    """PDF BAST mutasi diunduh SUPER-ADMIN lintas-satker: "Mengetahui, KPB"
    harus KPB satker DOKUMEN — bukan KPB satker lain yang SK-nya lebih baru
    (pilihan resolver tanpa scope) dan bukan "-"."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-1", "kode_satker": SATKER, "jenis": "mutasi_pengguna",
            "nomor": "BAST-01/2026", "tanggal": "2026-08-01",
            "pihak_pertama": {"nama": "Pak Lama", "nip": "", "jabatan": "Staf",
                              "alamat": "Pos Jaga Timur"},
            "pihak_kedua": {"nama": "Andi Penerima", "nip": "",
                            "jabatan": "Staf", "alamat": "Gedung B Lt. 2"},
            "asset_ids": ["aset-1"],
            "aset": [{"id": "aset-1", "asset_code": "3100102001", "NUP": "1",
                      "asset_name": "Laptop Kerja", "brand": "Thinkpad",
                      "model": "X1", "serial_number": "SN-1",
                      "condition": "Baik", "purchase_date": "2025-03-01",
                      "purchase_price": 15_000_000}],
            "saksi": [], "keterangan": "", "sertakan_foto": False,
        })
        return await _unwrap(rb.bast_pdf)("bast-1", _user=SUPER)
    teks = _teks_pdf(_jalan(skenario()))
    assert "Mengetahui" in teks
    assert "Ratna Pemilik Dokumen" in teks
    assert "Bambang Satker Lain" not in teks
    # Kapasitas mengikuti kop: pada BAST ber-kop KPB ia "Mengetahui" sebagai
    # Kuasa Pengguna Barang — jabatan strukturalnya TIDAK dicetak.
    assert "Kuasa Pengguna Barang" in teks
    assert "Direktur Pengembangan Ekosistem Digital" not in teks


def _y_teks_terbawah(body, potongan):
    """Koordinat-y kemunculan TERAKHIR `potongan` (halaman terakhir yang
    memuatnya, posisi paling bawah) — nama pihak juga tampil di tabel
    identitas di atas dokumen; yang diuji adalah baris NAMA pada blok tanda
    tangan di bagian bawah. Origin PDF di kiri-bawah → y kecil = lebih bawah."""
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(body)
    try:
        hasil = None  # (indeks_halaman, y_bawah)
        for no, hal in enumerate(pdf):
            tp = hal.get_textpage()
            teks = tp.get_text_range()
            i = teks.find(potongan)
            while i >= 0:
                _l, bawah, _r, _t = tp.get_charbox(i)
                if (hasil is None or no > hasil[0]
                        or (no == hasil[0] and bawah < hasil[1])):
                    hasil = (no, bawah)
                i = teks.find(potongan, i + 1)
        if hasil is None:
            raise AssertionError(f"teks tidak ditemukan di PDF: {potongan!r}")
        return hasil
    finally:
        pdf.close()


def test_pdf_nama_penandatangan_sejajar_meski_kepala_beda_tinggi(dbx):
    """Kolom PIHAK KESATU berkepala 4 baris (tempat-tanggal + header + role
    panjang "Yang Menyerahkan a.n. Kuasa Pengguna Barang," yang wrap) sementara
    PIHAK KEDUA hanya 2 — baris NAMA kedua kolom tetap harus SEJAJAR (dulu
    nama kolom kanan melorot sendirian; tangkapan layar pemilik)."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-2", "kode_satker": SATKER, "jenis": "penggunaan_melekat",
            "nomor": "BAST-02/2026", "tanggal": "2026-08-04",
            "penyerah_atas_nama_kpb": True,
            "pihak_pertama": {"nama": "Karlinus Ignasius Manek",
                              "nip": "198206022001121003",
                              "jabatan": "Petugas Penatausahaan",
                              "alamat": "Gedung A"},
            "pihak_kedua": {"nama": "Karina Lia Meirita Ulo",
                            "nip": "199005242025062002",
                            "jabatan": "Staf", "alamat": "Gedung B Lt. 2"},
            "asset_ids": ["aset-1"],
            "aset": [{"id": "aset-1", "asset_code": "3100102001", "NUP": "1",
                      "asset_name": "Laptop Kerja", "brand": "Thinkpad",
                      "model": "X1", "serial_number": "SN-1",
                      "condition": "Baik", "purchase_date": "2025-03-01",
                      "purchase_price": 15_000_000}],
            "saksi": [], "keterangan": "", "sertakan_foto": False,
        })
        resp = await _unwrap(rb.bast_pdf)("bast-2", _user=SUPER)
        import io
        buf = io.BytesIO()
        async for potong in resp.body_iterator:
            buf.write(potong if isinstance(potong, bytes) else potong.encode())
        return buf.getvalue()
    body = _jalan(skenario())
    hal_kiri, y_kiri = _y_teks_terbawah(body, "Karina Lia Meirita Ulo")
    hal_kanan, y_kanan = _y_teks_terbawah(body, "Karlinus Ignasius Manek")
    assert hal_kiri == hal_kanan, "kedua nama harus di halaman yang sama"
    assert abs(y_kiri - y_kanan) < 2, (
        f"nama tidak sejajar: kiri y={y_kiri:.1f} vs kanan y={y_kanan:.1f}")


# ── Kebijakan penyajian NILAI PEROLEHAN (mandat pemilik) ────────────────────

def _payload_nilai(**ganti):
    return _payload(**ganti)


def test_bast_membekukan_pilihan_nilai_dari_kebijakan_satker(dbx):
    """Satker berkebijakan "sembunyikan" → BAST baru tersimpan dengan pilihan
    tampilkan_nilai=False (dibekukan bersama dokumen), tanpa user memilih apa
    pun di form."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.satker.insert_one({"kode_satker": SATKER,
                                     "nama_satker": "Satker Uji",
                                     "nilai_dokumen": "sembunyikan"})
        await _unwrap(rb.buat_bast)(_payload_nilai(), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    assert _jalan(skenario())["tampilkan_nilai"] is False


def test_pdf_bast_tanpa_kolom_nilai_saat_disembunyikan(dbx):
    """PDF BAST milik satker ber-kebijakan sembunyikan: kolom "Nilai
    Perolehan" DAN angka nilainya benar-benar absen dari halaman (bukan
    sekadar dikosongkan), plus ada catatan jujur mengapa."""
    async def skenario(sembunyi):
        await dbx.bast_serah_terima.delete_many({})
        await dbx.satker.delete_many({})
        await _seed_dasar(dbx)
        if sembunyi:
            await dbx.satker.insert_one({"kode_satker": SATKER,
                                         "nama_satker": "Satker Uji",
                                         "nilai_dokumen": "sembunyikan"})
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-n", "kode_satker": SATKER,
            "jenis": "penggunaan_melekat", "nomor": "BAST-09/2026",
            "tanggal": "2026-08-04",
            "pihak_pertama": {"nama": "Penyerah", "nip": "", "jabatan": "",
                              "alamat": ""},
            "pihak_kedua": {"nama": "Andi Penerima", "nip": "",
                            "jabatan": "Staf", "alamat": ""},
            "asset_ids": ["aset-1"],
            "aset": [{"id": "aset-1", "asset_code": "3100102001", "NUP": "1",
                      "asset_name": "Laptop Kerja", "brand": "Thinkpad",
                      "model": "X1", "serial_number": "SN-1",
                      "condition": "Baik", "purchase_date": "2025-03-01",
                      "purchase_price": 15_000_000}],
            "saksi": [], "keterangan": "", "sertakan_foto": False,
        })
        return await _unwrap(rb.bast_pdf)("bast-n", _user=USER)

    teks_sembunyi = _teks_pdf(_jalan(skenario(True)))
    assert "Nilai Perolehan" not in teks_sembunyi
    assert "15.000.000" not in teks_sembunyi
    assert "tidak ditampilkan" in teks_sembunyi

    # Kontrol: kebijakan bawaan tetap mencetak nilai seperti sebelumnya.
    teks_tampil = _teks_pdf(_jalan(skenario(False)))
    assert "Nilai Perolehan" in teks_tampil
    assert "15.000.000" in teks_tampil


def test_pdf_bast_param_unduhan_menimpa_pilihan_dokumen(dbx):
    """Satu BAST, dua salinan: `?nilai=0` mencetak versi tanpa nilai walau
    dokumen dibekukan dengan pilihan tampilkan (arsip tetap utuh)."""
    async def skenario(param):
        await dbx.bast_serah_terima.delete_many({})
        await _seed_dasar(dbx)
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-p", "kode_satker": SATKER,
            "jenis": "penggunaan_melekat", "nomor": "BAST-10/2026",
            "tanggal": "2026-08-04", "tampilkan_nilai": True,
            "pihak_pertama": {"nama": "Penyerah", "nip": "", "jabatan": "",
                              "alamat": ""},
            "pihak_kedua": {"nama": "Andi Penerima", "nip": "",
                            "jabatan": "Staf", "alamat": ""},
            "asset_ids": ["aset-1"],
            "aset": [{"id": "aset-1", "asset_code": "3100102001", "NUP": "1",
                      "asset_name": "Laptop Kerja", "brand": "Thinkpad",
                      "model": "X1", "serial_number": "SN-1",
                      "condition": "Baik", "purchase_date": "2025-03-01",
                      "purchase_price": 15_000_000}],
            "saksi": [], "keterangan": "", "sertakan_foto": False,
        })
        return await _unwrap(rb.bast_pdf)("bast-p", nilai=param, _user=USER)

    assert "15.000.000" not in _teks_pdf(_jalan(skenario("0")))
    assert "15.000.000" in _teks_pdf(_jalan(skenario("")))


# ── Pasal khusus per BIDANG kode barang pada PDF nyata (mandat pemilik) ─────

def _bast_dgn_aset(dbx, bast_id, kode, nama, jenis="penggunaan_melekat"):
    return dbx.bast_serah_terima.insert_one({
        "id": bast_id, "kode_satker": SATKER, "jenis": jenis,
        "nomor": f"BAST-{bast_id}/2026", "tanggal": "2026-08-04",
        "pihak_pertama": {"nama": "Penyerah", "nip": "", "jabatan": "",
                          "alamat": ""},
        "pihak_kedua": {"nama": "Andi Penerima", "nip": "", "jabatan": "Staf",
                        "alamat": ""},
        "asset_ids": ["aset-x"],
        "aset": [{"id": "aset-x", "asset_code": kode, "NUP": "1",
                  "asset_name": nama, "brand": "-", "model": "-",
                  "serial_number": "-", "condition": "Baik",
                  "purchase_date": "2025-03-01", "purchase_price": 200_000_000}],
        "saksi": [], "keterangan": "", "sertakan_foto": False,
    })


def test_pdf_pasal_kendaraan_muncul_hanya_untuk_kendaraan(dbx):
    """BAST mobil memuat pasal kendaraan (SIM, pajak, larangan pemakaian
    pribadi di luar jam kerja); BAST laptop TIDAK — justru memuat pasal
    perangkat kerja. Ini inti "sistem membedakan berdasarkan kode barang"."""
    async def skenario(kode, nama, bast_id):
        await dbx.bast_serah_terima.delete_many({})
        await _seed_dasar(dbx)
        await _bast_dgn_aset(dbx, bast_id, kode, nama)
        return await _unwrap(rb.bast_pdf)(bast_id, _user=USER)

    teks_mobil = _teks_pdf(_jalan(skenario("3020104001", "Minibus", "bp-1")))
    assert "KETENTUAN KHUSUS SESUAI JENIS BARANG" in teks_mobil
    assert "Kendaraan Dinas" in teks_mobil
    assert "Surat Izin Mengemudi" in teks_mobil
    assert "Komputer dan Perangkat Kerja" not in teks_mobil

    teks_laptop = _teks_pdf(_jalan(skenario("3100102003", "Laptop", "bp-2")))
    assert "Komputer dan Perangkat Kerja" in teks_laptop
    assert "Kendaraan Dinas" not in teks_laptop
    assert "Surat Izin Mengemudi" not in teks_laptop


def test_pdf_pasal_waktu_dan_risiko_tercetak(dbx):
    """Pasal konteks waktu (luar jam kerja / hari libur / perjalanan dinas)
    dan pasal risiko (lapor 1x24 jam, TGR, kahar) hadir pada BAST penguasaan."""
    async def skenario():
        await dbx.bast_serah_terima.delete_many({})
        await _seed_dasar(dbx)
        await _bast_dgn_aset(dbx, "bp-3", "3100102003", "Laptop")
        return await _unwrap(rb.bast_pdf)("bp-3", _user=USER)
    teks = _teks_pdf(_jalan(skenario()))
    assert "TANGGUNG JAWAB DAN PENGGUNAAN" in teks
    assert "hari libur" in teks
    assert "perjalanan dinas" in teks
    assert "KEHILANGAN, KERUSAKAN, DAN GANTI RUGI" in teks
    assert "1x24 jam" in teks


def test_pdf_pengembalian_tanpa_pasal_kewajiban_penggunaan(dbx):
    """BAST pengembalian: barang kembali ke satker, sehingga pasal kewajiban
    penggunaan & risiko pemegang TIDAK dibebankan lagi."""
    async def skenario():
        await dbx.bast_serah_terima.delete_many({})
        await _seed_dasar(dbx)
        await _bast_dgn_aset(dbx, "bp-4", "3100102003", "Laptop",
                             jenis="pengembalian")
        return await _unwrap(rb.bast_pdf)("bp-4", _user=USER)
    teks = _teks_pdf(_jalan(skenario()))
    assert "KEHILANGAN, KERUSAKAN, DAN GANTI RUGI" not in teks
    assert "perjalanan dinas" not in teks           # butir waktu tak dibebankan
    assert "telah mengembalikan seluruh BMN" in teks  # inti pengembalian tetap


# ── Batas 2 lembar (mandat pemilik) ─────────────────────────────────────────

_MIN_ASET_DUA_HALAMAN = 12  # jumlah aset yang WAJIB muat pada tiap jenis BAST

_KODE_UJI = ["3020104001", "3100102003", "3050101001", "3060101001",
             "3080101001"]                       # lima BIDANG berbeda
_URAIAN_UJI = {"3020104001": "Mini Bus (Penumpang 14 Orang Kebawah)",
               "3100102003": "Lap Top",
               "3050101001": "Mesin Ketik Manual Portable",
               "3060101001": "Camera Digital",
               "3080101001": "Alat Kesehatan Umum Lainnya"}


def _jumlah_halaman(resp):
    import io
    import pypdfium2 as pdfium
    buf = io.BytesIO()

    async def kumpul():
        async for potong in resp.body_iterator:
            buf.write(potong if isinstance(potong, bytes) else potong.encode())
    _jalan(kumpul())
    pdf = pdfium.PdfDocument(buf.getvalue())
    try:
        return len(pdf)
    finally:
        pdf.close()


def _aset_uji(n):
    return [{"id": f"a{i}", "asset_code": _KODE_UJI[i % len(_KODE_UJI)],
             "NUP": str(i + 1),
             "asset_name": f"Barang Contoh Nama Agak Panjang {i + 1}",
             "brand": "Merk Contoh", "model": "Tipe-XYZ-2000",
             "serial_number": f"SN-{i:05d}", "condition": "Baik",
             "purchase_date": "2025-03-01", "purchase_price": 15_000_000 + i}
            for i in range(n)]


@pytest.mark.parametrize("jenis", list(rb.JENIS_BAST))
def test_semua_jenis_bast_maksimal_dua_halaman(dbx, jenis):
    """Mandat: SELURUH jenis BAST tersaji maksimal 2 lembar TERMASUK tanda
    tangan, pada muatan wajar (12 aset lintas 5 bidang → 5 sekat + 4 butir
    ketentuan khusus, kondisi TERBERAT tiap jenis).

    Dijaga di sini karena regresinya senyap: menambah satu pasal atau satu
    butir panjang mendorong blok tanda tangan ke halaman ketiga, dan tidak ada
    yang mengeluh sampai dokumen sudah dicetak. Skenario memakai kondisi
    TERBERAT tiap jenis (jangka waktu, penanggung jawab tambahan, ahli waris)
    dan MENGISI `db.kodefikasi` supaya baris tabel setinggi keadaan nyata.
    """
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.kodefikasi.insert_many(
            [{"kode": k, "uraian": u} for k, u in _URAIAN_UJI.items()])
        aset = _aset_uji(_MIN_ASET_DUA_HALAMAN)
        doc = {
            "id": "b-2h", "kode_satker": SATKER, "jenis": jenis,
            "nomor": "BAST-001/PPTHD/VIII/2026", "tanggal": "2026-08-04",
            "pihak_pertama": {"nama": "Karlinus Ignasius Manek",
                              "nip": "198206022001121003",
                              "jabatan": "Petugas Penatausahaan",
                              "alamat": "Gedung Kantor Otorita IKN, Nusantara"},
            "pihak_kedua": {"nama": "Karina Lia Meirita Ulo",
                            "nip": "199005242025062002", "jabatan": "Analis",
                            "alamat": "Gedung B Lantai 2"},
            "asset_ids": [a["id"] for a in aset], "aset": aset,
            "saksi": [], "keterangan": "", "sertakan_foto": False,
            "penyerah_atas_nama_kpb": jenis != "mutasi_pengguna",
            "jangka_dari": "2026-08-05", "jangka_sampai": "2026-12-31",
        }
        if jenis == "pengembalian_almarhum":
            doc["almarhum"] = {"nama": "Almarhum Contoh",
                               "nip": "196001011985031001",
                               "tanggal_meninggal": "2026-07-01",
                               "nomor_akta_kematian": "AK/123/2026"}
            doc["saksi"] = [{"nama": "Saksi Satu", "jabatan": "Ahli Waris",
                             "nip": ""},
                            {"nama": "Saksi Dua", "jabatan": "Atasan",
                             "nip": ""}]
        if jenis == "operasional_unit":
            doc["penanggung_jawab_tambahan"] = [
                {"nama": "Petugas A", "unit_tempat_tugas": "Ruang Server"},
                {"nama": "Petugas B", "unit_tempat_tugas": "Ruang Rapat"}]
        await dbx.bast_serah_terima.insert_one(doc)
        return await _unwrap(rb.bast_pdf)("b-2h", _user=USER)

    n = _jumlah_halaman(_jalan(skenario()))
    assert n <= 2, (f"BAST {jenis} memakan {n} halaman pada "
                    f"{_MIN_ASET_DUA_HALAMAN} aset — batas mandat 2 lembar")


# ── Sekat pembagi per BIDANG pada tabel objek serah terima (mandat pemilik) ──

def test_pdf_sekat_bidang_dengan_jumlah_unit_dan_urutan_nup(dbx):
    """Tabel Objek Serah Terima dibagi per BIDANG kode barang, tiap sekat
    menyebut jumlah unitnya, dan barang berderet menurut kode lalu NUP
    TERKECIL — sekalipun pengguna memilihnya dengan urutan acak (tangkapan
    layar pemilik: Camera NUP 1, VR, Camera NUP 2)."""
    async def skenario():
        await _seed_dasar(dbx)
        await dbx.kodefikasi.insert_many([
            {"kode": "305", "uraian": "Alat Kantor dan Rumah Tangga"},
            {"kode": "306", "uraian": "Alat Studio, Komunikasi dan Pemancar"},
        ])
        acak = [
            {"id": "k1", "asset_code": "3060102128", "NUP": "1",
             "asset_name": "Camera Digital", "brand": "Insta360",
             "model": "X5", "serial_number": "-", "condition": "Baik",
             "purchase_date": "2026-01-01", "purchase_price": 20_490_000},
            {"id": "v1", "asset_code": "3050105097", "NUP": "1",
             "asset_name": "Realitas Virtual Head set", "brand": "Meta",
             "model": "Quest 3", "serial_number": "-", "condition": "Baik",
             "purchase_date": "2026-01-01", "purchase_price": 15_990_000},
            {"id": "k2", "asset_code": "3060102128", "NUP": "2",
             "asset_name": "Camera Digital", "brand": "Insta360",
             "model": "X5", "serial_number": "-", "condition": "Baik",
             "purchase_date": "2026-01-01", "purchase_price": 20_490_000},
        ]
        await dbx.bast_serah_terima.insert_one({
            "id": "bast-sekat", "kode_satker": SATKER,
            "jenis": "penggunaan_melekat", "nomor": "BAST-11/2026",
            "tanggal": "2026-08-04",
            "pihak_pertama": {"nama": "Penyerah", "nip": "", "jabatan": "",
                              "alamat": ""},
            "pihak_kedua": {"nama": "Karina Lia Meirita Ulo", "nip": "",
                            "jabatan": "Perekayasa", "alamat": ""},
            "asset_ids": [a["id"] for a in acak], "aset": acak,
            "saksi": [], "keterangan": "", "sertakan_foto": False,
        })
        return await _unwrap(rb.bast_pdf)("bast-sekat", _user=USER)

    teks = _teks_pdf(_jalan(skenario()))
    # Sekat menyebut kode bidang, uraiannya, dan JUMLAH unit kelompok itu
    assert "BIDANG 305" in teks and "BIDANG 306" in teks
    assert "Alat Studio, Komunikasi dan Pemancar" in teks
    assert "1 unit" in teks and "2 unit" in teks
    # Bidang 305 (VR) mendahului 306 (kamera); dua kamera berdampingan
    assert teks.index("BIDANG 305") < teks.index("BIDANG 306")
    i_vr = teks.index("Realitas Virtual")
    i_kam = teks.index("Camera Digital", teks.index("BIDANG 306"))
    assert i_vr < i_kam, "kelompok bidang tidak boleh saling menyisip"
    # Nomor urut tetap menerus 1..3 melintasi sekat (bukan mulai ulang)
    assert "JUMLAH" in teks and "56.970.000" in teks
