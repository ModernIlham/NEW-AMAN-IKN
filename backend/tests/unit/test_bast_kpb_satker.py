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
    # KPB satker dokumen + KPB satker LAIN yang lebih baru — resolver tanpa
    # scope dokumen akan salah memilih yang lebih baru (satker lain).
    await dbx.pejabat.insert_many([
        {"id": "pj-1", "kode_satker": SATKER, "nama": "Ratna Pemilik Dokumen",
         "nip": "197001011990032001", "jabatan": "Kepala Satuan Kerja",
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
    """Kosong = KPB aktif dari Referensi Pejabat satker dokumen; alamat default
    menggabung SEMUA baris alamat kantor (bukan baris pertama saja)."""
    async def skenario():
        await _seed_dasar(dbx)
        await _unwrap(rb.buat_bast)(_payload(), request=None, user=USER)
        return await dbx.bast_serah_terima.find_one({})
    b = _jalan(skenario())
    p1 = b["pihak_pertama"]
    assert p1["nama"] == "Ratna Pemilik Dokumen"
    assert p1["nip"] == "197001011990032001"
    assert p1["jabatan"] == "Kepala Satuan Kerja"
    assert p1["alamat"] == ("Gedung Kantor Otorita IKN, Nusantara; "
                            "Perwakilan I: Menara Mandiri II Lt. 5, Jakarta")
    assert b["kode_satker"] == SATKER


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
