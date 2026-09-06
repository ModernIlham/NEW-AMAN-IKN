"""Pohon unit kerja berakar di tingkat SATKERNYA, bukan selalu di Eselon I.

Tidak semua satker berpuncak Eselon I. Unit kantor pusat (Direktorat Jenderal,
Badan, Inspektorat Jenderal) memang satker Eselon I, tetapi Kantor Wilayah
adalah satker Eselon II, sedangkan Kantor Pelayanan Pratama, Lapas, Madrasah
Negeri, dan Kantor Pertanahan kabupaten/kota adalah satker Eselon III/IV —
semuanya satker mandiri karena memegang DIPA sendiri.

Sebelum ini sistem memaksa SETIAP satker mengisi dari Eselon I. Akibatnya dua
cacat yang keduanya bekerja tanpa satu pun pesan galat:

1. **Lapas harus mengarang dua tingkat yang tak pernah ia miliki.** Eselon I
   sebuah Lapas adalah Ditjen di kementeriannya — bukan bagian struktur satker
   itu. Angka laporan lalu dikelompokkan menurut unit karangan tadi.

2. **"Bangun otomatis dari data pegawai" menghasilkan NOL unit.** Pegawai
   Lapas mengisi `eselon3` dan membiarkan `eselon1`–`eselon2` kosong, sehingga
   penelusuran yang selalu mulai dari 1 putus pada langkah pertama. Tombolnya
   tampak tak berbuat apa-apa, dan tak ada yang menjelaskan mengapa.

Yang dijaga berkas ini: akar itu DINYATAKAN sekali di master satker, seluruh
lapisan membacanya dari sana, dan di bawah akar tingkat TETAP tak boleh
dilompati — kelonggarannya hanya di puncak, bukan di mana-mana.
"""
import asyncio

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import routes.activities as ract
import routes.satker as rs
import routes.unit_kerja as ruk

#: Satker Eselon III — sebuah Lapas. Kode satkernya sengaja beda dari satker
#: bawaan test lain supaya keduanya dapat hidup berdampingan.
LAPAS = {"username": "admin", "role": "admin", "kode_satker": "333333"}
#: Satker Eselon I klasik — kontrol perilaku lama.
PUSAT = {"username": "admin", "role": "admin", "kode_satker": "111111"}


def _jalan(coro):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _diam(*a, **k):
    return None


@pytest.fixture()
def dbx(monkeypatch):
    fake = AsyncMongoMockClient()["uji"]
    import shared_utils as su
    for mod in (rs, ruk, ract, su):
        monkeypatch.setattr(mod, "db", fake, raising=False)
    for mod in (rs, ruk, ract):
        monkeypatch.setattr(mod, "log_audit", _diam, raising=False)
    return fake


def _daftarkan(user, **isi):
    """Daftarkan satker lewat rutenya sendiri — bukan menyuntik dokumen.

    Menyuntik langsung akan lolos meski PUT satker tak pernah menyimpan
    `eselon_satker`, dan justru itu yang harus terbukti tersimpan.
    """
    kode = user["kode_satker"]
    payload = rs.SatkerIn(**{"kode_satker": kode,
                             "nama_satker": f"Satker {kode}", **isi})
    return _jalan(rs.simpan_satker(kode, payload, admin=user))


def _buat(nama, eselon, parent_id="", user=LAPAS):
    return _jalan(ruk.buat_unit_kerja(
        ruk.UnitIn(nama_unit=nama, eselon=eselon, parent_id=parent_id),
        user=user))["id"]


# ── 1. Akar dinyatakan sekali, di master satker ─────────────────────────

def test_eselon_satker_TERSIMPAN_saat_profil_disimpan(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    doc = _jalan(dbx.satker.find_one({"kode_satker": "333333"}, {"_id": 0}))
    assert doc["eselon_satker"] == "3"


def test_satker_lama_tanpa_field_itu_dibaca_sebagai_Eselon_I(dbx):
    from shared_utils import eselon_satker
    _daftarkan(PUSAT)
    assert _jalan(eselon_satker("111111")) == 1
    # Satker yang bahkan tak terdaftar pun tak boleh membuat pembacaannya
    # gagal; pengelolaan unit harus tetap jalan seperti sebelumnya.
    assert _jalan(eselon_satker("999999")) == 1
    assert _jalan(eselon_satker("")) == 1


def test_nilai_di_luar_satu_sampai_lima_jatuh_ke_bawaan(dbx):
    from shared_utils import eselon_satker
    _daftarkan(LAPAS, eselon_satker="9")
    assert _jalan(eselon_satker("333333")) == 1


# ── 2. Puncak satker tak berinduk; di atasnya bukan miliknya ────────────

def test_lapas_membuat_unit_puncak_Eselon_III_tanpa_induk(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    assert _buat("Lapas Kelas IIA Nusantara", "3")


def test_tanpa_dinyatakan_puncak_Eselon_III_itu_DITOLAK(dbx):
    # Kontrol: yang membuat kasus di atas lolos benar-benar `eselon_satker`,
    # bukan aturan yang diam-diam dilonggarkan untuk semua satker.
    _daftarkan(LAPAS)
    with pytest.raises(HTTPException) as e:
        _buat("Lapas Kelas IIA Nusantara", "3")
    assert "berinduk" in str(e.value.detail)


def test_tingkat_DI_ATAS_puncak_satker_ditolak_dengan_alasan_yang_jelas(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    with pytest.raises(HTTPException) as e:
        _buat("Ditjen Pemasyarakatan", "1")
    pesan = str(e.value.detail)
    assert "DI ATAS" in pesan and "Eselon III" in pesan


def test_puncak_satker_TETAP_tak_boleh_berinduk(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    puncak = _buat("Lapas Kelas IIA Nusantara", "3")
    with pytest.raises(HTTPException) as e:
        _buat("Lapas Kelas IIB Sepaku", "3", puncak)
    assert "puncak" in str(e.value.detail)


# ── 3. Di BAWAH puncak, tingkat tetap tak boleh dilompati ───────────────

def test_Eselon_IV_lapas_wajib_berinduk_pada_Eselon_III_yang_nyata(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    with pytest.raises(HTTPException) as e:
        _buat("Subbagian Tata Usaha", "4")
    assert "berinduk" in str(e.value.detail)


def test_Eselon_V_tak_boleh_langsung_di_bawah_puncak(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    puncak = _buat("Lapas Kelas IIA Nusantara", "3")
    with pytest.raises(HTTPException) as e:
        _buat("Urusan Kepegawaian", "5", puncak)
    assert "dilompati" in str(e.value.detail)


def test_cabang_utuh_di_bawah_puncak_lapas_diterima(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    puncak = _buat("Lapas Kelas IIA Nusantara", "3")
    e4 = _buat("Subbagian Tata Usaha", "4", puncak)
    assert _buat("Urusan Kepegawaian", "5", e4)


# ── 4. Layar tak perlu menebak akarnya ──────────────────────────────────

def test_daftar_unit_menyebutkan_akar_dan_tingkat_yang_tersedia(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    r = _jalan(ruk.daftar_unit_kerja(_user=LAPAS))
    assert r["level_akar"] == 3
    assert [b["tersedia"] for b in r["level"]] == [False, False, True, True,
                                                   True]
    assert [b["wajib"] for b in r["level"]] == [False, False, True, False,
                                                False]


def test_satker_Eselon_I_melihat_daftar_yang_PERSIS_seperti_dulu(dbx):
    _daftarkan(PUSAT)
    r = _jalan(ruk.daftar_unit_kerja(_user=PUSAT))
    assert r["level_akar"] == 1
    assert all(b["tersedia"] for b in r["level"])
    assert [b["level"] for b in r["level"] if b["wajib"]] == [1]


# ── 5. Bangun otomatis dari data pegawai ────────────────────────────────

def _pegawai_lapas(dbx):
    _jalan(dbx.pegawai.insert_many([
        {"kode_satker": "333333", "eselon3": "Lapas Kelas IIA Nusantara",
         "eselon4": "Subbagian Tata Usaha"},
        {"kode_satker": "333333", "eselon3": "Lapas Kelas IIA Nusantara",
         "eselon4": "Seksi Pembinaan"},
    ]))


def test_bangun_otomatis_lapas_MENGHASILKAN_unit(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    _pegawai_lapas(dbx)
    r = _jalan(ruk.bangun_dari_pegawai(user=LAPAS))
    assert r["dibuat"] == 3, r
    unit = _jalan(dbx.unit_kerja.find({}, {"_id": 0}).to_list(50))
    assert {(u["eselon"], u["nama_unit"]) for u in unit} == {
        ("3", "Lapas Kelas IIA Nusantara"),
        ("4", "Subbagian Tata Usaha"), ("4", "Seksi Pembinaan")}
    puncak = next(u for u in unit if u["eselon"] == "3")
    assert puncak["parent_id"] is None
    assert all(u["parent_id"] == puncak["id"]
               for u in unit if u["eselon"] == "4")


def test_tanpa_dinyatakan_bangun_otomatis_lapas_menghasilkan_NOL(dbx):
    # Cacat aslinya, dipatok apa adanya: penelusuran yang selalu mulai dari
    # Eselon I putus pada langkah pertama. Ia hanya boleh terjadi pada satker
    # yang memang belum menyatakan tingkatnya.
    _daftarkan(LAPAS)
    _pegawai_lapas(dbx)
    assert _jalan(ruk.bangun_dari_pegawai(user=LAPAS))["dibuat"] == 0


# ── 6. Bentuk ringkas pada kegiatan ikut tingkat satkernya ──────────────

def test_dua_laci_bentuk_ringkas_relatif_terhadap_puncak():
    import organisasi_utils as org
    assert org.level_ringkas(1) == [1, 2]
    assert org.level_ringkas(3) == [3, 4]
    assert org.level_ringkas(None) == [1, 2]
    # Eselon V hanya punya satu laci: "Eselon VI" bukan tingkat mana pun.
    assert org.level_ringkas(5) == [5]


def _pohon_lapas(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    puncak = _buat("Lapas Kelas IIA Nusantara", "3")
    _buat("Subbagian Tata Usaha", "4", puncak)


def _cocokkan(user=LAPAS, eselon1=None):
    return _jalan(ruk.cocokkan_lingkup(
        ruk.LingkupTeksIn(eselon1=eselon1 or []), user=user))


def test_lingkup_yang_DIKETIK_lapas_cocok_dengan_masternya(dbx):
    _pohon_lapas(dbx)
    r = _cocokkan(eselon1=[{"nama": "Lapas Kelas IIA Nusantara",
                            "eselon2": ["Subbagian Tata Usaha"]}])
    assert len(r["lingkup_unit"]) == 2
    assert [u["eselon"] for u in r["unit"]] == ["3", "4"]
    assert r["tak_cocok"] == []


def test_tanpa_dinyatakan_pencocokan_lapas_GAGAL_seluruhnya(dbx):
    # Cacat aslinya, dipatok apa adanya: pencarian di tingkat 1 dan 2 pada
    # satker Eselon III tak pernah menemukan apa pun, dan layar terbaca seperti
    # masternya yang salah.
    _daftarkan(LAPAS)
    puncak = _jalan(dbx.unit_kerja.insert_one(
        {"id": "u3", "nama_unit": "Lapas Kelas IIA Nusantara", "eselon": "3",
         "parent_id": None, "kode_satker": "333333"}))
    assert puncak
    r = _cocokkan(eselon1=[{"nama": "Lapas Kelas IIA Nusantara",
                            "eselon2": []}])
    assert r["lingkup_unit"] == []
    assert r["tak_cocok"] == ["Lapas Kelas IIA Nusantara"]


def test_satker_Eselon_I_mencocokkan_PERSIS_seperti_sebelumnya(dbx):
    _daftarkan(PUSAT)
    e1 = _buat("Setjen", "1", user=PUSAT)
    _buat("Biro Umum", "2", e1, user=PUSAT)
    r = _cocokkan(user=PUSAT,
                  eselon1=[{"nama": "Setjen", "eselon2": ["Biro Umum"]}])
    assert [u["eselon"] for u in r["unit"]] == ["1", "2"]
    assert r["tak_cocok"] == []


# ── 7. Pencarian satker menyebutkan tingkatnya ──────────────────────────

def test_satker_lookup_menyebutkan_tingkat_satkernya(dbx):
    _daftarkan(LAPAS, eselon_satker="3")
    r = _jalan(ract.satker_lookup(kode="333333", _user=LAPAS))
    assert r["eselon_satker"] == 3


def test_lookup_yang_menemukan_KEGIATAN_tetap_membaca_master(dbx):
    # `satker-lookup` mencari kegiatan lebih dulu, dan kegiatan tak menyimpan
    # tingkat satker. Membacanya dari dokumen yang ketemu akan mengembalikan
    # Eselon I untuk setiap satker yang sudah punya kegiatan — yaitu justru
    # yang datanya paling banyak.
    _daftarkan(LAPAS, eselon_satker="3")
    _jalan(dbx.inventory_activities.insert_one(
        {"id": "k1", "kode_satker": "333333",
         "nama_satker": "Lapas Kelas IIA Nusantara"}))
    r = _jalan(ract.satker_lookup(kode="333333", _user=LAPAS))
    assert r["eselon_satker"] == 3
    # Dan dokumen kegiatan itu memang yang ditemukan lebih dulu.
    assert r["nama_satker"] == "Lapas Kelas IIA Nusantara"
