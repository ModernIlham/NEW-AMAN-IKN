"""Struktur organisasi berjenjang Eselon I–V.

Permintaan pemilik: *"sistem memang hanya support sampai eselon II saja, akan
tetapi buat lebih berkembang lagi agar dapat mengakomodir hingga eselon ke 5
dengan indukannya yang terkoneksi ... eselon I dan II adalah default wajib."*

Lima sifat dijaga di sini:

1. **Tingkat tidak boleh dilompati** — Eselon III berinduk pada Eselon II yang
   nyata, bukan langsung pada Eselon I.
2. **`ancestors` dan `jalur` selalu DITURUNKAN** dari `parent_id`, tak pernah
   disimpan sebagai kebenaran terpisah.
3. **Unit yang masih punya anak tak boleh dihapus** — anaknya akan menggantung
   sebagai Eselon III tanpa Eselon II.
4. **Data pohon yang rusak tak boleh menggantung selamanya** — siklus dan
   kedalaman berlebih dihentikan.
5. **Lingkup kegiatan mencakup keturunan**, dan lingkup kosong berarti
   seluruhnya.
"""
import pytest

import organisasi_utils as org


# Pohon uji:
#   e1  Sekretariat Jenderal        (Eselon I)
#     e2  Biro Umum                 (Eselon II)
#       e3  Bagian Rumah Tangga     (Eselon III)
#         e4  Subbagian Perlengkapan (Eselon IV)
#           e5  Urusan Gudang        (Eselon V)
#     e2b Biro Keuangan             (Eselon II)
_POHON = [
    {"id": "e1", "nama": "Sekretariat Jenderal", "level": 1, "parent_id": ""},
    {"id": "e2", "nama": "Biro Umum", "level": 2, "parent_id": "e1"},
    {"id": "e2b", "nama": "Biro Keuangan", "level": 2, "parent_id": "e1"},
    {"id": "e3", "nama": "Bagian Rumah Tangga", "level": 3, "parent_id": "e2"},
    {"id": "e4", "nama": "Subbagian Perlengkapan", "level": 4, "parent_id": "e3"},
    {"id": "e5", "nama": "Urusan Gudang", "level": 5, "parent_id": "e4"},
]
_PETA_UNIT = {u["id"]: u for u in _POHON}
_PETA_PARENT = {u["id"]: u["parent_id"] for u in _POHON if u["parent_id"]}


# ── 1. Tingkat tidak boleh dilompati ────────────────────────────────────

def test_induk_wajib_TEPAT_satu_tingkat_di_atas():
    """Eselon adalah struktur yang ditetapkan peraturan, bukan kebiasaan
    setempat: "Eselon III di bawah Eselon I" bukan penyederhanaan, melainkan
    pernyataan yang keliru."""
    assert org.parent_level_sah(1, 2) is True
    assert org.parent_level_sah(2, 3) is True
    assert org.parent_level_sah(4, 5) is True
    # Melompat — ditolak.
    assert org.parent_level_sah(1, 3) is False
    assert org.parent_level_sah(2, 5) is False
    # Terbalik dan sejajar — ditolak.
    assert org.parent_level_sah(3, 2) is False
    assert org.parent_level_sah(2, 2) is False


@pytest.mark.parametrize("level", [0, 6, -1, "", None, "abc", 99])
def test_level_di_luar_I_sampai_V_ditolak(level):
    assert org.level_sah(level) is False
    ok, pesan = org.validasi_unit({"nama": "Unit", "level": level})
    assert ok is False and "tidak sah" in pesan


def test_ESELON_I_adalah_puncak_dan_tak_berinduk():
    ok, _ = org.validasi_unit({"nama": "Setjen", "level": 1})
    assert ok is True
    ok, pesan = org.validasi_unit({"nama": "Setjen", "level": 1},
                                  induk=_PETA_UNIT["e1"])
    assert ok is False and "puncak" in pesan


def test_ESELON_II_dan_ke_bawah_WAJIB_berinduk():
    """Eselon I dan II wajib ada sebelum tingkat di bawahnya boleh dipakai —
    unit Eselon III tanpa induk terbaca sebagai organisasi tanpa kepala."""
    for lv in (2, 3, 4, 5):
        ok, pesan = org.validasi_unit({"nama": "Unit", "level": lv})
        assert ok is False, lv
        assert "wajib berinduk" in pesan, pesan


def test_pesan_penolakan_MENYEBUT_induk_yang_seharusnya():
    """Pesan "tidak sah" tanpa menyebut apa yang seharusnya memaksa
    pembacanya menebak — dan kebanyakan orang menebak salah."""
    ok, pesan = org.validasi_unit(
        {"nama": "Bagian X", "level": 3}, induk=_PETA_UNIT["e1"])
    assert ok is False
    assert "Eselon III" in pesan and "Eselon II" in pesan
    assert "tidak boleh dilompati" in pesan


def test_unit_sah_diterima():
    for anak, induk in (("e2", "e1"), ("e3", "e2"), ("e5", "e4")):
        ok, pesan = org.validasi_unit(_PETA_UNIT[anak], _PETA_UNIT[induk])
        assert ok is True, (anak, pesan)


def test_nama_kosong_ditolak():
    ok, pesan = org.validasi_unit({"nama": "  ", "level": 1})
    assert ok is False and "Nama unit wajib" in pesan


# ── 2. ancestors & jalur DITURUNKAN ─────────────────────────────────────

def test_rantai_induk_dari_TERJAUH_ke_induk_langsung():
    assert org.rantai_induk("e5", _PETA_PARENT) == ["e1", "e2", "e3", "e4"]
    assert org.rantai_induk("e2", _PETA_PARENT) == ["e1"]
    assert org.rantai_induk("e1", _PETA_PARENT) == []


def test_ancestors_diturunkan_bukan_disimpan():
    """Menyimpan `parent_id`, `ancestors`, dan `jalur` sebagai tiga sumber
    kebenaran adalah resep pohon yang saling bertentangan."""
    assert org.turunkan_ancestors("e4", "e3", _PETA_PARENT) == ["e1", "e2", "e3"]
    assert org.turunkan_ancestors("e1", "", _PETA_PARENT) == []


def test_jalur_nama_memuat_leluhur_lalu_DIRINYA():
    assert org.jalur_nama("e4", _PETA_UNIT, _PETA_PARENT) == (
        "Sekretariat Jenderal / Biro Umum / Bagian Rumah Tangga / "
        "Subbagian Perlengkapan")
    assert org.jalur_nama("e1", _PETA_UNIT, _PETA_PARENT) == (
        "Sekretariat Jenderal")


# ── 3. Unit yang punya anak tak boleh dihapus ───────────────────────────

def test_unit_berANAK_tak_boleh_dihapus():
    """Menghapusnya membuat anaknya menggantung — terlihat sebagai Eselon III
    tanpa Eselon II, keadaan yang tak pernah sah."""
    ok, pesan = org.boleh_hapus("e2", _POHON)
    assert ok is False
    assert "masih membawahi 1 unit" in pesan, pesan


def test_unit_DAUN_boleh_dihapus():
    ok, pesan = org.boleh_hapus("e5", _POHON)
    assert ok is True and pesan == ""
    assert org.punya_anak("e5", _POHON) is False
    assert org.punya_anak("e1", _POHON) is True


# ── 4. Pohon rusak tak menggantung selamanya ────────────────────────────

def test_SIKLUS_dihentikan():
    """Data pohon yang rusak tak boleh membuat permintaan menggantung
    selamanya; yang sudah terkumpul dikembalikan apa adanya."""
    siklus = {"a": "b", "b": "c", "c": "a"}
    hasil = org.rantai_induk("a", siklus)
    assert len(hasil) <= 3, hasil
    assert len(set(hasil)) == len(hasil), "siklus terkumpul berulang"


def test_kedalaman_BERLEBIH_dibatasi():
    panjang = {f"n{i}": f"n{i + 1}" for i in range(200)}
    hasil = org.rantai_induk("n0", panjang)
    assert len(hasil) <= org.BATAS_RANTAI


def test_jalur_pada_pohon_rusak_tetap_mengembalikan_sesuatu():
    """Jalur kosong lebih baik daripada permintaan yang tak pernah selesai."""
    assert isinstance(org.jalur_nama("x", {}, {"x": "y", "y": "x"}), str)


# ── 5. Jembatan ke kolom eselon yang sudah ada ──────────────────────────

def test_field_eselon_diturunkan_dari_POHON():
    """Teks eselon pada pegawai/aset kini BAYANGAN pohon, bukan sumber
    kebenaran kedua — keduanya tak lagi dapat saling bertentangan."""
    f = org.field_eselon("e4", _PETA_UNIT, _PETA_PARENT)
    assert f == {
        "eselon1": "Sekretariat Jenderal",
        "eselon2": "Biro Umum",
        "eselon3": "Bagian Rumah Tangga",
        "eselon4": "Subbagian Perlengkapan",
        "eselon5": "",
    }


def test_field_eselon_SELALU_lengkap_lima_kunci():
    """Kunci yang hilang dan kunci yang kosong ditangani berbeda oleh
    pemanggil; bentuk yang berubah-ubah adalah sumber cacat diam."""
    for uid in ("e1", "e5", "", None, "tak-ada"):
        f = org.field_eselon(uid, _PETA_UNIT, _PETA_PARENT)
        assert set(f) == set(org.FIELD_ESELON), uid
        assert all(isinstance(v, str) for v in f.values()), uid


def test_unit_terdalam_mengambil_yang_PALING_dalam():
    assert org.unit_terdalam(
        org.field_eselon("e5", _PETA_UNIT, _PETA_PARENT)) == "Urusan Gudang"
    assert org.unit_terdalam(
        org.field_eselon("e2", _PETA_UNIT, _PETA_PARENT)) == "Biro Umum"
    assert org.unit_terdalam({}) == ""


# ── 6. Lingkup kegiatan ─────────────────────────────────────────────────

def test_lingkup_KOSONG_berarti_seluruhnya():
    """Kegiatan yang belum mencatat lingkup tak boleh mendadak kehilangan
    seluruh datanya."""
    for lingkup in ([], None, set()):
        assert org.dalam_lingkup("e5", lingkup, _PETA_PARENT) is True
        assert org.dalam_lingkup("", lingkup, _PETA_PARENT) is True


def test_lingkup_mencakup_SELURUH_KETURUNAN():
    """Mencatat "Biro Umum" sebagai lingkup berarti Bagian dan Subbagian di
    bawahnya ikut — itulah arti membawahi."""
    lingkup = ["e2"]
    for uid in ("e2", "e3", "e4", "e5"):
        assert org.dalam_lingkup(uid, lingkup, _PETA_PARENT) is True, uid
    # Saudara dan induknya TIDAK ikut.
    assert org.dalam_lingkup("e2b", lingkup, _PETA_PARENT) is False
    assert org.dalam_lingkup("e1", lingkup, _PETA_PARENT) is False


def test_unit_TANPA_id_di_luar_lingkup_yang_diisi():
    """Aset yang belum berunit tak boleh diam-diam ikut lingkup mana pun —
    ia justru yang perlu dibereskan."""
    assert org.dalam_lingkup("", ["e2"], _PETA_PARENT) is False
    assert org.dalam_lingkup(None, ["e2"], _PETA_PARENT) is False


def test_beberapa_unit_lingkup_sekaligus():
    lingkup = ["e2b", "e3"]
    assert org.dalam_lingkup("e2b", lingkup, _PETA_PARENT) is True
    assert org.dalam_lingkup("e4", lingkup, _PETA_PARENT) is True   # di bawah e3
    assert org.dalam_lingkup("e2", lingkup, _PETA_PARENT) is False  # induk e3


# ── 7. Registry level ───────────────────────────────────────────────────

def test_daftar_level_menandai_yang_WAJIB():
    d = org.daftar_level()
    assert [x["label"] for x in d] == [
        "Eselon I", "Eselon II", "Eselon III", "Eselon IV", "Eselon V"]
    assert [x["wajib"] for x in d] == [True, True, False, False, False]


def test_label_level_dan_field_eselon_selaras():
    assert org.label_level(3) == "Eselon III"
    assert org.label_level(9) == ""
    assert org.FIELD_ESELON == ("eselon1", "eselon2", "eselon3",
                                "eselon4", "eselon5")
