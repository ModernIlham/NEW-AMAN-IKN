"""Pengelompokan berjenjang laporan — kodefikasi barang & denah ruang.

Permintaan pemilik: *"Per Kategori masih belum terbagi hingga ke per golongan,
bidang, kelompok, dan sub kelompok (dan bisa dipilih ingin ditampilkan seperti
apa), begitupun yang lokasi belum terbagi berdasarkan denah yang sudah
ditetapkan."*

Tiga sifat dijaga di sini:

1. **Tak ada aset yang hilang** — yang tanpa kode/penempatan dikumpulkan,
   bukan dibuang. Jumlah batang harus selalu sama dengan jumlah aset.
2. **Jenjang dipilih, dan pilihan tak sah jatuh ke bawaan** — bukan ke grafik
   kosong yang tampak sah.
3. **Label memuat kode DAN uraian** — uraian saja membuat kelompok bernama
   mirip tak terbedakan; kode saja tak terbaca manusia.
"""
import pytest

import kodefikasi_utils as kod
import laporan_jenjang as ljj


def _aset(kode, n=1):
    return [{"asset_code": kode} for _ in range(n)]


def _kode(a):
    return kod.normalize_kode(a.get("asset_code"))


# ── 1. Tak ada aset yang hilang ─────────────────────────────────────────
#
# Sifat-sifat di bawah dulu diuji lewat `kelompokkan_kode`/`kelompokkan_denah`.
# Keduanya sudah tak dipakai produksi sejak panelnya menjadi SATU hierarki, dan
# dihapus: fungsi mati yang tetap hijau karena ujinya sendiri terbaca sebagai
# kode yang hidup. Sifatnya tak hilang — diuji lewat `baris_hierarki_*` dengan
# SATU jenjang, yang persis setara pengelompokan rata dulu.

def _rata(aset, level, uraian_map=None):
    """Baris satu jenjang → [(label, jumlah)] — setara pengelompokan rata."""
    return [(b["label"], len(b["aset"])) for b in ljj.baris_hierarki_kode(
        aset, [kod.LEVEL_LENGTHS[level]], _kode, uraian_map)]


def test_JUMLAH_aset_utuh_di_tiap_jenjang():
    """Jumlah batang yang tak sama dengan jumlah aset berarti ada yang
    dibuang — dan selisihnya tak pernah ditanyakan siapa pun karena ia tak
    terlihat di grafiknya."""
    aset = (_aset("3010203001", 5) + _aset("3010204001", 3)
            + _aset("3020101001", 7) + _aset("4010101001", 2)
            + _aset("", 4) + _aset("3", 2))
    for level in (1, 2, 3, 4, 5):
        assert sum(n for _, n in _rata(aset, level)) == len(aset), level


def test_kode_LEBIH_PENDEK_dari_jenjang_masuk_TANPA_KODE():
    """Aset berkode "3" tak dapat dijawab pada jenjang Bidang, dan memotongnya
    menjadi dirinya sendiri akan mengarang bidang "3" yang tak pernah ada."""
    hasil = dict(_rata(_aset("3", 2) + _aset("3010203001", 1), 2))
    assert hasil[ljj.TANPA_KODE] == 2
    assert "3" not in hasil, "kode pendek dipaksa jadi bidang"


def test_kelompok_TANPA_KODE_selalu_di_AKHIR():
    """Ia hampir selalu besar; menaruhnya di puncak membuat baris pertama
    grafik berisi keterangan yang paling tak informatif."""
    hasil = _rata(_aset("", 50) + _aset("3010203001", 3), 2)
    assert hasil[-1][0] == ljj.TANPA_KODE, hasil
    assert hasil[0][0].startswith("301")


def test_terbanyak_lebih_dulu():
    hasil = _rata(_aset("3010101001", 2) + _aset("3020101001", 9)
                  + _aset("3030101001", 5), 2)
    assert [n for _, n in hasil] == [9, 5, 2]


# ── 2. Jenjang benar-benar membagi berbeda ──────────────────────────────

def test_jenjang_BERBEDA_menghasilkan_pembagian_berbeda():
    """Kalau kelimanya menghasilkan grafik yang sama, pemilihnya tak berguna
    dan permintaannya tak terjawab."""
    aset = (_aset("3010203001", 1) + _aset("3010204001", 1)
            + _aset("3010301001", 1) + _aset("3020101001", 1)
            + _aset("4010101001", 1))
    jml = {lv: len(_rata(aset, lv)) for lv in (1, 2, 3, 4, 5)}
    assert jml[1] == 2, jml     # golongan 3 dan 4
    assert jml[2] == 3, jml     # 301, 302, 401
    assert jml[3] == 4, jml     # 30102, 30103, 30201, 40101
    assert jml[4] == 5, jml     # seluruhnya berbeda
    assert jml[5] == 5, jml
    assert jml[1] < jml[2] < jml[3] < jml[4]


# ── 3. Label memuat kode DAN uraian ─────────────────────────────────────

def test_label_memuat_kode_dan_uraian():
    hasil = _rata(_aset("3010203001", 1), 2, {"301": "Alat Besar Darat"})
    assert hasil[0][0] == "301 — Alat Besar Darat"


def test_uraian_TAK_DIKENAL_tak_menyembunyikan_asetnya():
    """Referensi yang belum lengkap bukan alasan menyembunyikan asetnya;
    kodenya sendiri sudah keterangan yang sah."""
    hasil = _rata(_aset("3010203001", 4), 2, {})
    assert hasil == [("301", 4)], hasil


def test_pilihan_jenjang_memakai_label_resmi():
    opsi = ljj.pilihan_jenjang((1, 2, 3, 4, 5), kod.LEVEL_LABELS)
    assert [o["label"] for o in opsi] == [
        "Golongan", "Bidang", "Kelompok", "Sub Kelompok", "Sub-sub Kelompok"]
    assert [o["nilai"] for o in opsi] == ["1", "2", "3", "4", "5"]


# ── 4. Denah ────────────────────────────────────────────────────────────

def _aset_di(node_id, n=1):
    return [{"lokasi_spasial": {"node_id": node_id}} for _ in range(n)]


_PETA = {
    "r1": {"level_nama": {"GEDUNG": "Menara A", "LANTAI": "Lantai 1",
                          "RUANGAN": "Ruang 101"}},
    "r2": {"level_nama": {"GEDUNG": "Menara A", "LANTAI": "Lantai 2",
                          "RUANGAN": "Ruang 201"}},
    "r3": {"level_nama": {"GEDUNG": "Menara B", "LANTAI": "Lantai 1",
                          "RUANGAN": "Ruang 101"}},
}


def _rata_denah(aset, level, peta=None):
    return {b["label"]: len(b["aset"]) for b in ljj.baris_hierarki_denah(
        aset, [level], peta if peta is not None else _PETA)}


def test_denah_mengelompokkan_menurut_LEVEL_yang_diminta():
    """Satu gedung memuat beberapa lantai, satu lantai beberapa ruangan —
    jenjangnya yang menentukan pertanyaan mana yang terjawab."""
    aset = _aset_di("r1", 4) + _aset_di("r2", 3) + _aset_di("r3", 2)
    assert _rata_denah(aset, "GEDUNG") == {"Menara A": 7, "Menara B": 2}
    assert _rata_denah(aset, "LANTAI") == {"Lantai 1": 6, "Lantai 2": 3}


def test_aset_TANPA_penempatan_dikumpulkan_bukan_dibuang():
    """Aset yang belum ditempatkan di denah justru yang paling perlu
    dibereskan."""
    aset = _aset_di("r1", 3) + [{}, {"lokasi_spasial": {}}]
    hasil = _rata_denah(aset, "GEDUNG")
    assert hasil[ljj.TANPA_DENAH] == 2
    assert sum(hasil.values()) == len(aset)


def test_node_yang_tak_punya_leluhur_di_level_itu_masuk_TANPA_DENAH():
    """Tingkat boleh dilompati — satker yang tak memakai Gedung tetap punya
    Ruangan, dan asetnya tak boleh lenyap saat dikelompokkan per Gedung."""
    peta = {"r9": {"level_nama": {"RUANGAN": "Ruang Serbaguna"}}}
    assert _rata_denah(_aset_di("r9", 5), "GEDUNG", peta) == {
        ljj.TANPA_DENAH: 5}
    assert _rata_denah(_aset_di("r9", 5), "RUANGAN", peta) == {
        "Ruang Serbaguna": 5}


def test_TANPA_DENAH_juga_di_akhir():
    aset = _aset_di("r1", 1) + [{} for _ in range(40)]
    baris = ljj.baris_hierarki_denah(aset, ["GEDUNG"], _PETA)
    assert baris[-1]["label"] == ljj.TANPA_DENAH, [b["label"] for b in baris]



# ── 5. Beberapa jenjang sekaligus ───────────────────────────────────────
#
# Permintaan pemilik: *"Jenjang Lokasi dan kategori jadikan juga pilihan dapat
# memilih [lebih] dari 1."* Memilih Golongan DAN Bidang menghasilkan dua panel
# berdampingan, sehingga sebaran kasar dan halus dapat dibandingkan tanpa
# memuat laporannya dua kali.

def test_beberapa_jenjang_dipakai_SEKALIGUS():
    assert ljj.jenjang_terpilih_banyak(["1", "3"], (1, 2, 3, 4), 2) == [1, 3]
    assert ljj.jenjang_terpilih_banyak(["1", "2", "3", "4"], (1, 2, 3, 4), 2) == [
        1, 2, 3, 4]


def test_urutannya_mengikuti_JENJANG_bukan_urutan_parameter():
    """Panel yang berpindah tempat setiap kali query string-nya disusun ulang
    membuat dua cetakan laporan yang sama terlihat berbeda."""
    assert ljj.jenjang_terpilih_banyak(["4", "1", "3"], (1, 2, 3, 4), 2) == [
        1, 3, 4]
    assert ljj.jenjang_terpilih_banyak(
        ["RUANGAN", "GEDUNG"], ("GEDUNG", "LANTAI", "RUANGAN"), "GEDUNG") == [
        "GEDUNG", "RUANGAN"]


def test_nilai_tak_sah_dibuang_dan_sisanya_TETAP_dipakai():
    """Satu nilai ngawur tak boleh membatalkan pilihan lain yang sah."""
    assert ljj.jenjang_terpilih_banyak(["99", "2", "abc"], (1, 2, 3, 4), 1) == [2]


def test_tanpa_pilihan_sah_jatuh_ke_BAWAAN():
    """Halaman tanpa panel apa pun akan terbaca sebagai laporan yang gagal
    dimuat, bukan sebagai pilihan yang keliru."""
    for buruk in ([], None, ["99"], ["", " "], "abc"):
        assert ljj.jenjang_terpilih_banyak(buruk, (1, 2, 3, 4), 2) == [2], buruk


def test_satu_nilai_TUNGGAL_tetap_diterima():
    """Query string lama (`?kat_level=3`) tak boleh mendadak berhenti bekerja."""
    assert ljj.jenjang_terpilih_banyak("3", (1, 2, 3, 4), 2) == [3]
    assert ljj.jenjang_terpilih_banyak(3, (1, 2, 3, 4), 2) == [3]


def test_tanpa_jenjang_sah_sama_sekali_hasilnya_KOSONG():
    """Satker tanpa satu pun penempatan denah tak punya jenjang lokasi; daftar
    kosong di sini yang membuat panelnya jatuh ke teks bebas."""
    assert ljj.jenjang_terpilih_banyak(["GEDUNG"], (), "") == []


# ── 6. Satu panel BERJENJANG, bukan panel terpisah ──────────────────────
#
# Permintaan pemilik: *"gunakan hingga ke sub-sub kelompok dan buat agar
# filternya tidak dibagi menjadi kartu terpisah akan tetapi buat hierarkinya,
# begitupun yang lokasi."*

def test_baris_hierarki_ANAK_mengikuti_INDUKNYA():
    """Panel terpisah per jenjang memaksa pembacanya mencocokkan sendiri baris
    mana milik baris mana — "301" pada satu panel dan "30101" pada panel lain
    tak punya garis yang menghubungkannya."""
    aset = (_aset("3010101001", 4) + _aset("3010201001", 2)
            + _aset("3020101001", 3) + _aset("4010101001", 1))
    baris = ljj.baris_hierarki_kode(
        aset, [kod.LEVEL_LENGTHS[1], kod.LEVEL_LENGTHS[2]], _kode,
        {"3": "Peralatan", "301": "Alat Besar"})
    ringkas = [(b["depth"], b["label"], len(b["aset"])) for b in baris]
    assert ringkas == [
        (0, "3 — Peralatan", 9),
        (1, "301 — Alat Besar", 6),
        (1, "302", 3),
        (0, "4", 1),
        (1, "401", 1),
    ], ringkas


def test_induk_BERJUMLAH_sama_dengan_anak_anaknya():
    """Induk yang jumlahnya tak sama dengan anak-anaknya berarti ada aset yang
    hilang di salah satu jenjang — dan batangnya tetap tergambar wajar."""
    aset = (_aset("3010101001", 5) + _aset("3020101001", 3)
            + _aset("", 4) + _aset("3", 2))
    baris = ljj.baris_hierarki_kode(
        aset, [kod.LEVEL_LENGTHS[lv] for lv in (1, 2, 3)], _kode)
    induk = [b for b in baris if b["depth"] == 0]
    assert sum(len(b["aset"]) for b in induk) == len(aset)

    # Anak ditentukan oleh POSISI, bukan awalan kode: aset berkode "3" tak
    # dapat dijawab pada jenjang Bidang dan jatuh ke anak "(tanpa kode
    # barang)" — yang jelas tidak berawalan "3". Mencocokkan dengan
    # `startswith` akan melewatkannya dan menyimpulkan induknya timpang.
    for i, b in enumerate(baris):
        anak, j = [], i + 1
        while j < len(baris) and baris[j]["depth"] > b["depth"]:
            if baris[j]["depth"] == b["depth"] + 1:
                anak.append(baris[j])
            j += 1
        if anak:
            assert sum(len(x["aset"]) for x in anak) == len(b["aset"]), b["label"]


def test_jenjang_boleh_MELOMPAT():
    """Golongan lalu Kelompok, tanpa Bidang: anaknya tetap bersarang di bawah
    induknya."""
    baris = ljj.baris_hierarki_kode(
        _aset("3010101001", 2) + _aset("3020101001", 1),
        [kod.LEVEL_LENGTHS[1], kod.LEVEL_LENGTHS[3]], _kode)
    assert [(b["depth"], b["kunci"]) for b in baris] == [
        (0, "3"), (1, "30101"), (1, "30201")]


def test_hierarki_sampai_SUB_SUB_KELOMPOK():
    """Level 5 (10 digit) kini ditawarkan — permintaan pemilik. Ia berguna
    karena barisnya bersarang, bukan berdiri sebagai daftar rata."""
    baris = ljj.baris_hierarki_kode(
        _aset("3010101001", 1) + _aset("3010101002", 1),
        [kod.LEVEL_LENGTHS[lv] for lv in (1, 2, 3, 4, 5)], _kode)
    assert max(b["depth"] for b in baris) == 4
    daun = [b for b in baris if b["depth"] == 4]
    assert sorted(b["kunci"] for b in daun) == ["3010101001", "3010101002"]


def test_SATU_jenjang_tetap_datar():
    """Satu jenjang tak boleh mendadak menjorok — tak ada induk untuk
    dijoroki."""
    baris = ljj.baris_hierarki_kode(
        _aset("3010101001", 2), [kod.LEVEL_LENGTHS[2]], _kode)
    assert [b["depth"] for b in baris] == [0]


def test_hierarki_DENAH_bersarang_sampai_ruangan():
    aset = _aset_di("r1", 4) + _aset_di("r2", 3) + _aset_di("r3", 2)
    baris = ljj.baris_hierarki_denah(aset, ["GEDUNG", "LANTAI", "RUANGAN"], _PETA)
    ringkas = [(b["depth"], b["label"], len(b["aset"])) for b in baris]
    assert ringkas[0] == (0, "Menara A", 7), ringkas
    assert (1, "Lantai 1", 4) in ringkas and (2, "Ruang 101", 4) in ringkas
    assert (0, "Menara B", 2) in ringkas
    # Seluruh aset terhitung di jenjang teratas.
    assert sum(len(b["aset"]) for b in baris if b["depth"] == 0) == len(aset)


def test_hierarki_denah_yang_BELUM_DITEMPATKAN_tetap_terhitung():
    aset = _aset_di("r1", 3) + [{} for _ in range(5)]
    baris = ljj.baris_hierarki_denah(aset, ["GEDUNG", "RUANGAN"], _PETA)
    induk = [b for b in baris if b["depth"] == 0]
    assert sum(len(b["aset"]) for b in induk) == 8
    assert induk[-1]["label"] == ljj.TANPA_DENAH, [b["label"] for b in induk]


# ── Unit organisasi berjenjang, dan lingkup kegiatannya ─────────────────
#
# Sebelumnya analisis eselon berupa DUA panel rata tanpa satu pun garis
# penghubung. Yang dijaga di sini: hubungan induk-anak terbaca, aset di luar
# lingkup dikumpulkan alih-alih disaring keluar, dan rantai "(tanpa …)" yang
# tak menyatakan apa pun tidak ikut memenuhi kertas.

_ASET_ES = [
    {"id": "a1", "eselon1": "Setjen", "eselon2": "Biro Umum",
     "eselon3": "Bagian RT"},
    {"id": "a2", "eselon1": "Setjen", "eselon2": "Biro Umum"},
    {"id": "a3", "eselon1": "Setjen", "eselon2": "Biro Keuangan"},
    {"id": "a4"},
]


def test_eselon_bersarang_induk_sama_dengan_jumlah_anaknya():
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1, 2])
    setjen = next(b for b in baris if b["label"] == "Setjen")
    anak = [b for b in baris if b["depth"] == 1
            and b["label"] in ("Biro Umum", "Biro Keuangan")]
    assert setjen["depth"] == 0 and len(setjen["aset"]) == 3
    assert sum(len(b["aset"]) for b in anak) == 3


def test_aset_tanpa_unit_dikumpulkan_bukan_dibuang():
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1])
    assert sum(len(b["aset"]) for b in baris) == len(_ASET_ES)
    assert any(b["label"] == ljj.TANPA_ESELON for b in baris)


def test_kelompok_tanpa_unit_selalu_di_akhir():
    baris = [b for b in ljj.baris_hierarki_eselon(_ASET_ES, [1])]
    assert baris[-1]["label"] == ljj.TANPA_ESELON


def test_aset_di_luar_lingkup_DIKUMPULKAN_pada_barisnya_sendiri():
    # Kegiatan yang mencatat tupoksinya pada satu Biro tetapi memuat aset Biro
    # lain sedang menunjukkan lingkup yang belum lengkap ATAU aset yang salah
    # kegiatan. Keduanya perlu dilihat; keduanya lenyap kalau barisnya disaring.
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1, 2], di_luar={"a3"})
    puncak = {b["label"]: len(b["aset"]) for b in baris if b["depth"] == 0}
    assert puncak == {"Setjen": 2, ljj.DI_LUAR_LINGKUP: 1,
                      ljj.TANPA_ESELON: 1}
    assert sum(puncak.values()) == len(_ASET_ES), "jumlah batang ≠ jumlah aset"


def test_penanda_di_luar_lingkup_hanya_di_jenjang_teratas():
    # Kalau ia ikut dinilai di tiap jenjang, aset itu muncul sebagai
    # "(di luar lingkup)" bersarang di bawah dirinya sendiri.
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1, 2], di_luar={"a3"})
    dalam = [b for b in baris if b["depth"] == 1]
    assert any(b["label"] == "Biro Keuangan" for b in dalam)
    assert not any(b["label"] == ljj.DI_LUAR_LINGKUP for b in dalam)


def test_rantai_tanpa_unit_yang_ANAK_TUNGGAL_tidak_ikut_dicetak():
    # Jalur eselon lazim putus di tengah. Pada panel lima tingkat, tiap unit
    # tanpa anak melahirkan rantai "(tanpa …)" sedalam sisa jenjangnya —
    # baris yang cacahnya persis sama dengan induknya dan tak menyatakan
    # satu pun hal baru.
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1, 2, 3, 4, 5])
    keuangan_i = next(i for i, b in enumerate(baris)
                      if b["label"] == "Biro Keuangan")
    berikut = baris[keuangan_i + 1] if keuangan_i + 1 < len(baris) else None
    assert berikut is None or berikut["depth"] <= 1, [b["label"] for b in baris]


def test_tanpa_unit_yang_PUNYA_SAUDARA_tetap_dicetak():
    # Di situ ia menyatakan sesuatu yang nyata: sekian aset di bawah Biro ini
    # belum ditempatkan pada Bagian mana pun, sementara sisanya sudah.
    baris = ljj.baris_hierarki_eselon(_ASET_ES, [1, 2, 3])
    umum_i = next(i for i, b in enumerate(baris) if b["label"] == "Biro Umum")
    anak = [b["label"] for b in baris[umum_i + 1:] if b["depth"] == 2]
    assert "Bagian RT" in anak and ljj.TANPA_ESELON in anak, anak


def test_jenjang_kosong_menghasilkan_panel_kosong():
    assert ljj.baris_hierarki_eselon(_ASET_ES, []) == []
