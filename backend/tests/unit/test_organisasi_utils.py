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
    {"id": "e1", "nama_unit": "Sekretariat Jenderal", "eselon": "1", "parent_id": ""},
    {"id": "e2", "nama_unit": "Biro Umum", "eselon": "2", "parent_id": "e1"},
    {"id": "e2b", "nama_unit": "Biro Keuangan", "eselon": "2", "parent_id": "e1"},
    {"id": "e3", "nama_unit": "Bagian Rumah Tangga", "eselon": "3", "parent_id": "e2"},
    {"id": "e4", "nama_unit": "Subbagian Perlengkapan", "eselon": "4", "parent_id": "e3"},
    {"id": "e5", "nama_unit": "Urusan Gudang", "eselon": "5", "parent_id": "e4"},
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
    ok, pesan = org.validasi_unit({"nama_unit": "Unit", "eselon": level})
    assert ok is False and "tidak sah" in pesan


def test_ESELON_I_adalah_puncak_dan_tak_berinduk():
    ok, _ = org.validasi_unit({"nama_unit": "Setjen", "eselon": "1"})
    assert ok is True
    ok, pesan = org.validasi_unit({"nama_unit": "Setjen", "eselon": "1"},
                                  induk=_PETA_UNIT["e1"])
    assert ok is False and "puncak" in pesan


def test_ESELON_II_dan_ke_bawah_WAJIB_berinduk():
    """Eselon I dan II wajib ada sebelum tingkat di bawahnya boleh dipakai —
    unit Eselon III tanpa induk terbaca sebagai organisasi tanpa kepala."""
    for lv in (2, 3, 4, 5):
        ok, pesan = org.validasi_unit({"nama_unit": "Unit", "eselon": lv})
        assert ok is False, lv
        assert "wajib berinduk" in pesan, pesan


def test_pesan_penolakan_MENYEBUT_induk_yang_seharusnya():
    """Pesan "tidak sah" tanpa menyebut apa yang seharusnya memaksa
    pembacanya menebak — dan kebanyakan orang menebak salah."""
    ok, pesan = org.validasi_unit(
        {"nama_unit": "Bagian X", "eselon": "3"}, induk=_PETA_UNIT["e1"])
    assert ok is False
    assert "Eselon III" in pesan and "Eselon II" in pesan
    assert "tidak boleh dilompati" in pesan


def test_unit_sah_diterima():
    for anak, induk in (("e2", "e1"), ("e3", "e2"), ("e5", "e4")):
        ok, pesan = org.validasi_unit(_PETA_UNIT[anak], _PETA_UNIT[induk])
        assert ok is True, (anak, pesan)


def test_nama_kosong_ditolak():
    ok, pesan = org.validasi_unit({"nama_unit": "  ", "eselon": "1"})
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


# ── 6. Unit dapat DIPERBAIKI tanpa membongkar cabangnya ──────────────────
#
# Sebelum ada penyuntingan, unit yang salah ketik dan sudah punya anak tak
# dapat diperbaiki sama sekali: menghapusnya ditolak karena masih membawahi.
# Yang dijaga di sini adalah batas-batas perbaikannya — sampai mana ia boleh,
# dan di mana ia berhenti supaya pohonnya tetap pohon.

def test_keturunan_mengumpulkan_seluruh_cabang_bukan_anak_langsung():
    assert org.keturunan("e2", _POHON) == {"e3", "e4", "e5"}
    assert org.keturunan("e1", _POHON) == {"e2", "e2b", "e3", "e4", "e5"}
    assert org.keturunan("e5", _POHON) == set()


def test_keturunan_berhenti_pada_pohon_yang_melingkar():
    # a → b → a. Tanpa penjagaan, penelusurannya tak pernah selesai.
    gelang = [{"id": "a", "parent_id": "b"}, {"id": "b", "parent_id": "a"}]
    assert org.keturunan("a", gelang) == {"b"}


def test_unit_tak_boleh_berinduk_pada_dirinya_sendiri():
    ok, pesan = org.validasi_pindah("e2", "e2", _POHON)
    assert not ok and "dirinya sendiri" in pesan


def test_unit_tak_boleh_berinduk_pada_keturunannya():
    # Memindahkan Biro Umum ke bawah Subbagian Perlengkapan menutup gelang:
    # setelahnya tak satu pun unit pada gelang itu punya jalur ke puncak.
    ok, pesan = org.validasi_pindah("e2", "e4", _POHON)
    assert not ok and "melingkar" in pesan.lower()


def test_pindah_ke_saudara_atau_ke_puncak_tetap_boleh():
    assert org.validasi_pindah("e3", "e2b", _POHON)[0]
    assert org.validasi_pindah("e2", "", _POHON)[0] is True


def test_ganti_nama_unit_beranak_diperbolehkan():
    lama = _PETA_UNIT["e2"]
    baru = dict(lama, nama_unit="Biro Umum dan Keuangan")
    ok, pesan = org.validasi_perubahan(lama, baru, _PETA_UNIT["e1"], _POHON)
    assert ok, pesan


def test_eselon_unit_yang_masih_membawahi_TAK_boleh_diubah():
    # Anak-anaknya divalidasi terhadap eselon induknya saat dibuat; mengubahnya
    # belakangan membuat seluruh cabang itu melanggar tanpa satu pun diperiksa.
    lama = _PETA_UNIT["e2"]
    baru = dict(lama, eselon="3", parent_id="e2b")
    ok, pesan = org.validasi_perubahan(lama, baru, _PETA_UNIT["e2b"], _POHON)
    assert not ok and "membawahi" in pesan


def test_eselon_unit_TANPA_anak_boleh_diubah():
    lama = _PETA_UNIT["e2b"]                    # Biro Keuangan, tanpa anak
    baru = dict(lama, eselon="3", parent_id="e2")
    ok, pesan = org.validasi_perubahan(lama, baru, _PETA_UNIT["e2"], _POHON)
    assert ok, pesan


def test_perubahan_tetap_tunduk_pada_aturan_tingkat():
    lama = _PETA_UNIT["e3"]
    baru = dict(lama, parent_id="e1")           # Eselon III langsung di bawah I
    ok, pesan = org.validasi_perubahan(lama, baru, _PETA_UNIT["e1"], _POHON)
    assert not ok and "dilompati" in pesan


def test_perubahan_menolak_nama_kosong():
    lama = _PETA_UNIT["e2"]
    ok, pesan = org.validasi_perubahan(lama, dict(lama, nama_unit="   "),
                                       _PETA_UNIT["e1"], _POHON)
    assert not ok and "Nama" in pesan


# ── 7. Jalur nama: menemukan baris pegawai/aset milik satu unit ──────────
#
# `pegawai` dan `assets` menyimpan unitnya sebagai NAMA, bukan id. Mencocokkan
# nama saja menyeret unit lain yang kebetulan bernama sama di cabang berbeda.

def test_filter_jalur_menyertakan_leluhur_bukan_namanya_saja():
    fe = org.field_eselon("e3", _PETA_UNIT, _PETA_PARENT)
    assert org.filter_jalur(fe, 3) == {
        "eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum",
        "eselon3": "Bagian Rumah Tangga"}


def test_filter_jalur_melewati_tingkat_yang_kosong():
    # Baris pegawai lama kerap tak mengisi seluruh tingkat; menuntut ""
    # membuatnya tak pernah cocok.
    assert org.filter_jalur({"eselon1": "A", "eselon2": "", "eselon3": "C"},
                            3) == {"eselon1": "A", "eselon3": "C"}
    assert org.filter_jalur({}, 5) == {}
    assert org.filter_jalur({"eselon1": "A"}, 0) == {}


def test_perubahan_jalur_hanya_menyebut_yang_berubah():
    setel, hapus = org.perubahan_jalur(
        {"eselon1": "A", "eselon2": "B"}, {"eselon1": "A", "eselon2": "Z"}, 5)
    assert setel == {"eselon2": "Z"} and hapus == []


def test_perubahan_jalur_MENGHAPUS_tingkat_yang_tak_lagi_terpakai():
    # Unit yang naik dari Eselon III ke II meninggalkan eselon3 yang menyebut
    # unit yang sudah tak ada di sana — terbaca sebagai unit ketiga.
    setel, hapus = org.perubahan_jalur(
        {"eselon1": "A", "eselon2": "B", "eselon3": "C"},
        {"eselon1": "A", "eselon2": "C"}, 3)
    assert setel == {"eselon2": "C"} and hapus == ["eselon3"]


def test_perubahan_jalur_tak_menyentuh_tingkat_di_luar_batas():
    setel, hapus = org.perubahan_jalur(
        {"eselon1": "A", "eselon4": "D"}, {"eselon1": "Z", "eselon4": ""}, 2)
    assert setel == {"eselon1": "Z"} and hapus == []


# ── 8. Lingkup kegiatan: dari teks bebas ke rujukan pohon ────────────────
#
# Kegiatan mencatat lingkupnya sebagai teks bebas dua tingkat, tak pernah
# terhubung ke master unit mana pun. Yang dijaga di sini adalah pencocokannya
# — dan batas-batas di mana ia menolak menebak.

def test_lingkup_teks_memakai_ESELON_II_bukan_induknya():
    # "Setjen, khususnya Biro Umum" berarti Biro Umum. Mencatat induknya akan
    # menarik Biro Keuangan yang justru sengaja tak disebut.
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "Sekretariat Jenderal", "eselon2": ["Biro Umum"]}], _POHON)
    assert ids == ["e2"] and tak == []


def test_lingkup_teks_tanpa_anak_memakai_eselon_satunya():
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "Sekretariat Jenderal", "eselon2": []}], _POHON)
    assert ids == ["e1"] and tak == []


def test_lingkup_teks_menerima_bentuk_daftar_string():
    ids, _ = org.cocokkan_lingkup_teks(["Sekretariat Jenderal"], _POHON)
    assert ids == ["e1"]


def test_nama_yang_tak_ditemukan_DILAPORKAN_bukan_dibuang():
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "Sekretariat Jenderal", "eselon2": ["Biro Hantu"]},
         {"nama": "Kedeputian Entah", "eselon2": ["Direktorat X"]}], _POHON)
    assert ids == []
    assert tak == ["Sekretariat Jenderal / Biro Hantu",
                   "Kedeputian Entah", "Direktorat X"]


def test_pencocokan_tak_peduli_besar_kecil_huruf_dan_spasi_tepi():
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "  sekretariat JENDERAL  ", "eselon2": ["biro umum"]}],
        _POHON)
    assert ids == ["e2"] and tak == []


def test_eselon_dua_dicocokkan_DI_BAWAH_induknya_saja():
    # Biro Keuangan ada, tetapi bukan di bawah Kedeputian.
    pohon = _POHON + [{"id": "x1", "nama_unit": "Kedeputian X", "eselon": "1",
                       "parent_id": ""}]
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "Kedeputian X", "eselon2": ["Biro Keuangan"]}], pohon)
    assert ids == [] and tak == ["Kedeputian X / Biro Keuangan"]


def test_nama_yang_MENDUA_tak_ditebak():
    # Dua unit sama-sama sah pada tingkat dan induk yang sama: menebak salah
    # satunya menghasilkan lingkup keliru tanpa satu pun tanda.
    kembar = _POHON + [{"id": "e2c", "nama_unit": "Biro Umum", "eselon": "2",
                        "parent_id": "e1"}]
    ids, tak = org.cocokkan_lingkup_teks(
        [{"nama": "Sekretariat Jenderal", "eselon2": ["Biro Umum"]}], kembar)
    assert ids == [] and tak == ["Sekretariat Jenderal / Biro Umum"]


def test_lingkup_teks_membuang_duplikat_dan_menjaga_urutan():
    ids, _ = org.cocokkan_lingkup_teks(
        [{"nama": "Sekretariat Jenderal", "eselon2": ["Biro Keuangan",
                                                      "Biro Umum",
                                                      "Biro Keuangan"]}],
        _POHON)
    assert ids == ["e2b", "e2"]


def test_lingkup_kegiatan_mengutamakan_rujukan_pohon():
    act = {"lingkup_unit": ["e3"],
           "eselon1": [{"nama": "Sekretariat Jenderal", "eselon2": []}]}
    assert org.lingkup_kegiatan(act, _POHON) == ["e3"]


def test_lingkup_kegiatan_JATUH_ke_teks_bila_belum_dipetakan():
    # Kegiatan lama tak boleh mendadak melebar ke seluruh satker hanya karena
    # field barunya masih kosong.
    act = {"lingkup_unit": [],
           "eselon1": [{"nama": "Sekretariat Jenderal",
                        "eselon2": ["Biro Umum"]}]}
    assert org.lingkup_kegiatan(act, _POHON) == ["e2"]


def test_lingkup_kegiatan_membuang_id_yang_tak_ada_di_pohon():
    act = {"lingkup_unit": ["e2", "hantu"]}
    assert org.lingkup_kegiatan(act, _POHON) == ["e2"]


def test_kegiatan_tanpa_lingkup_apa_pun_berarti_seluruh_satker():
    assert org.lingkup_kegiatan({}, _POHON) == []
    assert org.dalam_lingkup("e5", [], _PETA_PARENT) is True


# ── 9. Aset dinilai terhadap lingkup kegiatannya ────────────────────────
#
# Aset menyimpan unitnya sebagai lima kolom TEKS, bukan sebagai id, jadi
# penentuan "di dalam lingkup" adalah pencocokan jalur. Fungsi inilah yang
# memutuskan aset mana ditandai di luar lingkup pada laporan — keliru di sini
# berarti laporan menuduh aset yang benar, atau meloloskan yang salah.

def test_aset_di_bawah_unit_lingkup_termasuk_lingkupnya():
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum"}
    assert org.aset_dalam_lingkup(aset, ["e2"], _PETA_UNIT, _PETA_PARENT)


def test_KETURUNAN_unit_lingkup_ikut_termasuk():
    # Aset sebuah Subbagian tetap membawa nama Bironya di eselon2, sehingga ia
    # cocok pada prefiks yang sama. Itulah arti membawahi.
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum",
            "eselon3": "Bagian Rumah Tangga",
            "eselon4": "Subbagian Perlengkapan"}
    assert org.aset_dalam_lingkup(aset, ["e2"], _PETA_UNIT, _PETA_PARENT)


def test_aset_cabang_lain_TIDAK_termasuk():
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Keuangan"}
    assert not org.aset_dalam_lingkup(aset, ["e2"], _PETA_UNIT, _PETA_PARENT)


def test_pencocokan_menuntut_SELURUH_jalur_bukan_nama_terdalam_saja():
    # Dua "Biro Umum" di bawah dua induk berbeda adalah dua unit berlainan.
    # Mencocokkan nama tingkat terdalam saja akan menyeret keduanya.
    pohon = _POHON + [
        {"id": "x1", "nama_unit": "Kedeputian X", "eselon": "1",
         "parent_id": ""},
        {"id": "x2", "nama_unit": "Biro Umum", "eselon": "2",
         "parent_id": "x1"},
    ]
    peta_unit = {u["id"]: u for u in pohon}
    peta_parent = {u["id"]: u["parent_id"] for u in pohon if u["parent_id"]}
    aset = {"eselon1": "Kedeputian X", "eselon2": "Biro Umum"}
    assert org.aset_dalam_lingkup(aset, ["x2"], peta_unit, peta_parent)
    assert not org.aset_dalam_lingkup(aset, ["e2"], peta_unit, peta_parent)


def test_lingkup_KOSONG_berarti_seluruhnya():
    # Kegiatan yang belum mencatat lingkup tak boleh mendadak kehilangan
    # seluruh datanya — atau, lebih buruk, melihat SETIAP asetnya ditandai
    # "di luar lingkup".
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Keuangan"}
    assert org.aset_dalam_lingkup(aset, [], _PETA_UNIT, _PETA_PARENT)
    assert org.aset_dalam_lingkup({}, [], _PETA_UNIT, _PETA_PARENT)


def test_aset_tanpa_unit_tak_termasuk_lingkup_mana_pun():
    assert not org.aset_dalam_lingkup({}, ["e2"], _PETA_UNIT, _PETA_PARENT)


def test_lingkup_dua_cabang_menerima_keduanya():
    a1 = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum"}
    a2 = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Keuangan"}
    for a in (a1, a2):
        assert org.aset_dalam_lingkup(a, ["e2", "e2b"], _PETA_UNIT,
                                      _PETA_PARENT)


def test_id_lingkup_yang_tak_dikenal_tidak_meloloskan_apa_pun():
    # Unit yang sudah dihapus tak boleh berubah makna menjadi "cocokkan saja".
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Umum"}
    assert not org.aset_dalam_lingkup(aset, ["sudah-hilang"], _PETA_UNIT,
                                      _PETA_PARENT)


def test_spasi_tepi_pada_kolom_aset_tak_membuatnya_meleset():
    aset = {"eselon1": "  Sekretariat Jenderal  ", "eselon2": " Biro Umum "}
    assert org.aset_dalam_lingkup(aset, ["e2"], _PETA_UNIT, _PETA_PARENT)


def test_unit_lingkup_BERNAMA_KOSONG_tak_meloloskan_seluruh_aset():
    # Jalur kosong dicocokkan dengan `all()` atas nol syarat — dan `all([])`
    # bernilai benar. Tanpa penjagaan, SATU unit bernama kosong di dalam
    # lingkup membuat setiap aset dianggap masuk, sehingga penandaan "di luar
    # lingkup" mati diam-diam pada seluruh laporan. Data lama dan hasil
    # derivasi otomatis bisa menghasilkan unit seperti itu.
    pohon = _POHON + [{"id": "kosong", "nama_unit": "   ", "eselon": "2",
                       "parent_id": "e1"}]
    peta_unit = {u["id"]: u for u in pohon}
    peta_parent = {u["id"]: u["parent_id"] for u in pohon if u["parent_id"]}
    aset = {"eselon1": "Sekretariat Jenderal", "eselon2": "Biro Keuangan"}
    assert not org.aset_dalam_lingkup(aset, ["kosong"], peta_unit, peta_parent)
