"""Uji SEMANTIK PENCARIAN TEKS BEBAS (pencarian_utils + build_asset_search_query).

Mengunci janji: setiap kata wajib ada, boleh tersebar di field berbeda, dan
identitas yang sering diketik petugas (NUP, nomor kontrak/BAST) benar-benar
ikut dicari — sementara NIP sengaja tetap di luar pencarian bebas (privasi).
Semua uji murni logika — tanpa Mongo.
"""
import re

import pytest

from pencarian_utils import MAKS_KATA, klausa_teks, pecah_kata
from routes.assets import FIELD_CARI_ASET, build_asset_search_query


# ── Evaluator kecil: menjalankan klausa Mongo terhadap dokumen dict ──────────
def _cocok_kondisi(doc, kondisi):
    for field, kriteria in kondisi.items():
        nilai = doc.get(field)
        if isinstance(kriteria, dict) and "$regex" in kriteria:
            if isinstance(nilai, str) and re.search(kriteria["$regex"], nilai, re.I):
                return True
        elif nilai == kriteria:
            return True
    return False


def cocok(doc, klausa):
    """True bila `doc` lolos klausa {"$or": ...} / {"$and": [{"$or": ...}]}."""
    if not klausa:
        return True
    if "$and" in klausa:
        return all(cocok(doc, sub) for sub in klausa["$and"])
    return any(_cocok_kondisi(doc, k) for k in klausa["$or"])


def cari(search):
    q = build_asset_search_query(search=search)
    return {k: v for k, v in q.items() if k in ("$or", "$and")}


LAPTOP = {
    "asset_code": "3.10.01.02.001", "NUP": "00012",
    "asset_name": "Laptop Lenovo ThinkPad X1 Carbon", "brand": "Lenovo",
    "location": "Gudang Lantai 2", "user": "Budi Santoso",
    "pengguna_nip": "199001012015031002", "purchase_price": 12000000,
    "nomor_kontrak": "HK.02.03/123/2025", "nomor_bast": "BA-45/PPK/2025",
}
MEJA = {
    "asset_code": "3.05.01.04.007", "NUP": "00120",
    "asset_name": "Meja Rapat Kayu Jati", "brand": "Olympic",
    "location": "Ruang Rapat Utama", "user": "Siti Aminah",
    "purchase_price": 120000,
}


# ── pecah_kata ──────────────────────────────────────────────────────────────
def test_kata_kunci_terlalu_pendek_diabaikan():
    assert pecah_kata("a") == []
    assert pecah_kata("   ") == []
    assert pecah_kata("") == []


def test_kata_dipecah_dedup_dan_dibatasi():
    assert pecah_kata("meja meja jati") == ["meja", "jati"]
    banyak = " ".join(f"k{i}" for i in range(20))
    assert len(pecah_kata(banyak)) == MAKS_KATA


# ── Semantik multi-kata ─────────────────────────────────────────────────────
def test_urutan_kata_tidak_penting():
    assert cocok(LAPTOP, cari("Lenovo ThinkPad"))
    assert cocok(LAPTOP, cari("ThinkPad Lenovo"))


def test_kata_boleh_tersebar_di_field_berbeda():
    # "lenovo" di asset_name, "gudang" di location — dulu selalu nihil karena
    # kata kunci dicocokkan sebagai SATU frasa dalam SATU field.
    assert cocok(LAPTOP, cari("Lenovo Gudang"))
    assert not cocok(MEJA, cari("Lenovo Gudang"))


def test_kata_terpisah_di_dalam_satu_nama():
    assert cocok(MEJA, cari("meja jati"))


def test_menambah_kata_mempersempit_bukan_mengosongkan():
    satu = cari("rapat")
    dua = cari("rapat kayu")
    assert cocok(MEJA, satu) and cocok(MEJA, dua)
    # Kata yang tak ada di dokumen mana pun → dokumen gugur (AND ditegakkan).
    assert not cocok(MEJA, cari("rapat lenovo"))


# ── Field identitas yang dulu tidak dicari sama sekali ──────────────────────
@pytest.mark.parametrize("kata", [
    "00012",                    # NUP
    "HK.02.03/123/2025",        # nomor kontrak
    "BA-45/PPK/2025",           # nomor BAST
])
def test_identitas_bisa_dicari(kata):
    assert cocok(LAPTOP, cari(kata)), f"'{kata}' seharusnya menemukan aset"


def test_field_identitas_terdaftar_di_builder():
    for f in ("NUP", "nomor_kontrak", "nomor_bast", "nomor_bukti_perolehan"):
        assert f in FIELD_CARI_ASET


def test_nip_sengaja_di_luar_pencarian_bebas():
    """NIP adalah data pribadi yang tidak diindeks ke mesin pencari; agar hasil
    tidak berbeda antara jalur Meili dan Mongo, ia juga tidak ikut pencarian
    teks bebas. Penyaringan per-NIP tetap ada lewat parameter filter khusus."""
    assert "pengguna_nip" not in FIELD_CARI_ASET
    q = build_asset_search_query(pengguna_nip="199001012015031002")
    assert "pengguna_nip" in q


def test_daftar_field_sama_dengan_indeks_meili():
    """Bila kedua daftar berbeda, hasil pencarian berubah tergantung Meili
    hidup atau mati — sumber utama 'hasil pencarian tidak konsisten'."""
    import meili_utils
    assert list(FIELD_CARI_ASET) == meili_utils.INDEKS["assets"]["searchable"]


# ── Kebisingan harga ────────────────────────────────────────────────────────
def test_angka_pendek_tidak_menyeret_harga_berawalan_sama():
    # "35" bukan bagian dari field mana pun di MEJA; dulu bisa ikut tertarik
    # lewat regex awalan harga. Sekarang awalan harga baru berlaku ≥ 4 digit.
    assert not cocok({"purchase_price": "3500000"}, cari("35"))


def test_harga_penuh_tetap_bisa_dicari():
    assert cocok(LAPTOP, cari("12000000"))
    assert cocok(LAPTOP, cari("12.000.000"))   # format ribuan Indonesia


# ── Keamanan input ──────────────────────────────────────────────────────────
def test_input_regex_berbahaya_diperlakukan_literal():
    klausa = cari("(a+)+$")
    pola = klausa["$or"][0]["asset_code"]["$regex"]
    assert pola == re.escape("(a+)+$")     # literal, bukan regex aktif
    assert not cocok(LAPTOP, klausa)
    # Dokumen yang benar-benar memuat teks itu tetap ketemu.
    assert cocok({"asset_name": "kode (a+)+$ aneh"}, klausa)


def test_klausa_teks_kosong_saat_tak_layak():
    assert klausa_teks("a", ("asset_name",)) == {}
    assert klausa_teks("", ("asset_name",)) == {}


def test_satu_kata_pakai_or_banyak_kata_pakai_and():
    assert "$or" in klausa_teks("meja", ("asset_name",))
    assert "$and" in klausa_teks("meja jati", ("asset_name",))


# ── Kode & angka yang ditulis berbeda-beda (temuan lapangan gelombang 2) ────
def test_kode_barang_diketik_tanpa_titik():
    """Petugas kerap mengetik kode BMN tanpa pemisah; regex literal menolaknya."""
    aset = {"asset_code": "3.10.01.02.001"}
    assert cocok(aset, cari("3100102001"))
    assert cocok(aset, cari("3.10.01.02.001"))     # bentuk asli tetap jalan
    assert cocok(aset, cari("310.01.02"))          # awalan sebagian


def test_desimal_koma_vs_titik():
    """Data '1,5 PK' harus ketemu meski diketik '1.5' (dan sebaliknya)."""
    aset = {"asset_name": "AC Split 1,5 PK Daikin"}
    assert cocok(aset, cari("ac 1.5"))
    assert cocok(aset, cari("ac 1,5"))


def test_nilai_tersimpan_sebagai_angka_tetap_ketemu():
    """$regex tak pernah cocok ke nilai non-string: NUP/tahun yang tersimpan
    numerik (impor & sinkron lama) dulu mustahil ditemukan."""
    assert cocok({"NUP": 120}, cari("120"))
    assert cocok({"year": 2021}, cari("2021"))


def test_kata_bukan_angka_tidak_memicu_pola_longgar():
    """Pola angka longgar hanya untuk kata berangka — kata biasa tetap literal."""
    from pencarian_utils import rx_angka_longgar
    assert rx_angka_longgar("meja") is None
    assert rx_angka_longgar("A1") is None          # cuma 1 angka
    assert rx_angka_longgar("12") is not None


def test_pola_longgar_dibatasi_panjangnya():
    """Deret angka sangat panjang tidak dijadikan pola (jaga panjang regex)."""
    from pencarian_utils import rx_angka_longgar
    assert rx_angka_longgar("9" * 25) is None
