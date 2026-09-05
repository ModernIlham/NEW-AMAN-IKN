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

def test_JUMLAH_aset_utuh_di_tiap_jenjang():
    """Jumlah batang yang tak sama dengan jumlah aset berarti ada yang
    dibuang — dan selisihnya tak pernah ditanyakan siapa pun karena ia tak
    terlihat di grafiknya."""
    aset = (_aset("3010203001", 5) + _aset("3010204001", 3)
            + _aset("3020101001", 7) + _aset("4010101001", 2)
            + _aset("", 4) + _aset("3", 2))
    for level in (1, 2, 3, 4):
        grup = ljj.kelompokkan_kode(aset, kod.LEVEL_LENGTHS[level], _kode)
        assert sum(len(v) for _, v in grup) == len(aset), level


def test_kode_LEBIH_PENDEK_dari_jenjang_masuk_TANPA_KODE():
    """Aset berkode "3" tak dapat dijawab pada jenjang Bidang, dan memotongnya
    menjadi dirinya sendiri akan mengarang bidang "3" yang tak pernah ada."""
    grup = dict(ljj.kelompokkan_kode(
        _aset("3", 2) + _aset("3010203001", 1), kod.LEVEL_LENGTHS[2], _kode))
    assert grup[ljj.TANPA_KODE] and len(grup[ljj.TANPA_KODE]) == 2
    assert "3" not in grup, "kode pendek dipaksa jadi bidang"


def test_kelompok_TANPA_KODE_selalu_di_AKHIR():
    """Ia hampir selalu besar; menaruhnya di puncak membuat baris pertama
    grafik berisi keterangan yang paling tak informatif."""
    grup = ljj.kelompokkan_kode(
        _aset("", 50) + _aset("3010203001", 3), kod.LEVEL_LENGTHS[2], _kode)
    assert grup[-1][0] == ljj.TANPA_KODE, [g[0] for g in grup]
    assert grup[0][0].startswith("301")


def test_terbanyak_lebih_dulu():
    grup = ljj.kelompokkan_kode(
        _aset("3010101001", 2) + _aset("3020101001", 9)
        + _aset("3030101001", 5), kod.LEVEL_LENGTHS[2], _kode)
    assert [len(v) for _, v in grup] == [9, 5, 2]


# ── 2. Jenjang benar-benar membagi berbeda ──────────────────────────────

def test_jenjang_BERBEDA_menghasilkan_pembagian_berbeda():
    """Kalau keempatnya menghasilkan grafik yang sama, pemilihnya tak berguna
    dan permintaannya tak terjawab."""
    aset = (_aset("3010203001", 1) + _aset("3010204001", 1)
            + _aset("3010301001", 1) + _aset("3020101001", 1)
            + _aset("4010101001", 1))
    jml = {}
    for level in (1, 2, 3, 4):
        grup = ljj.kelompokkan_kode(aset, kod.LEVEL_LENGTHS[level], _kode)
        jml[level] = len(grup)
    # Golongan 3 dan 4 → 2 kelompok; makin dalam makin banyak.
    assert jml[1] == 2, jml
    assert jml[2] == 3, jml     # 301, 302, 401
    assert jml[3] == 4, jml     # 30102, 30103, 30201, 40101
    assert jml[4] == 5, jml     # seluruhnya berbeda
    assert jml[1] < jml[2] < jml[3] < jml[4]


@pytest.mark.parametrize("diminta", ["", None, "0", "9", "abc", "2.0", " "])
def test_jenjang_TAK_SAH_jatuh_ke_bawaan(diminta):
    """`?kat_level=99` harus jatuh ke bawaan, bukan menghasilkan grafik kosong
    yang tampak sah."""
    assert ljj.jenjang_terpilih(diminta, (1, 2, 3, 4), 2) == 2


def test_jenjang_sah_dipakai_apa_adanya():
    for v in (1, 2, 3, 4):
        assert ljj.jenjang_terpilih(str(v), (1, 2, 3, 4), 2) == v


# ── 3. Label memuat kode DAN uraian ─────────────────────────────────────

def test_label_memuat_kode_dan_uraian():
    grup = ljj.kelompokkan_kode(
        _aset("3010203001", 1), kod.LEVEL_LENGTHS[2], _kode,
        {"301": "Alat Besar Darat"})
    assert grup[0][0] == "301 — Alat Besar Darat"


def test_uraian_TAK_DIKENAL_tak_menyembunyikan_asetnya():
    """Referensi yang belum lengkap bukan alasan menyembunyikan asetnya;
    kodenya sendiri sudah keterangan yang sah."""
    grup = ljj.kelompokkan_kode(
        _aset("3010203001", 4), kod.LEVEL_LENGTHS[2], _kode, {})
    assert grup[0][0] == "301"
    assert len(grup[0][1]) == 4


def test_pilihan_jenjang_memakai_label_resmi():
    opsi = ljj.pilihan_jenjang((1, 2, 3, 4), kod.LEVEL_LABELS)
    assert [o["label"] for o in opsi] == [
        "Golongan", "Bidang", "Kelompok", "Sub Kelompok"]
    assert [o["nilai"] for o in opsi] == ["1", "2", "3", "4"]


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


def test_denah_mengelompokkan_menurut_LEVEL_yang_diminta():
    """Satu gedung memuat beberapa lantai, satu lantai beberapa ruangan —
    jenjangnya yang menentukan pertanyaan mana yang terjawab."""
    aset = _aset_di("r1", 4) + _aset_di("r2", 3) + _aset_di("r3", 2)
    gedung = dict(ljj.kelompokkan_denah(aset, "GEDUNG", _PETA))
    assert {k: len(v) for k, v in gedung.items()} == {"Menara A": 7,
                                                      "Menara B": 2}
    lantai = dict(ljj.kelompokkan_denah(aset, "LANTAI", _PETA))
    assert {k: len(v) for k, v in lantai.items()} == {"Lantai 1": 6,
                                                      "Lantai 2": 3}


def test_aset_TANPA_penempatan_dikumpulkan_bukan_dibuang():
    """Aset yang belum ditempatkan di denah justru yang paling perlu
    dibereskan."""
    aset = _aset_di("r1", 3) + [{}, {"lokasi_spasial": {}}]
    grup = dict(ljj.kelompokkan_denah(aset, "GEDUNG", _PETA))
    assert len(grup[ljj.TANPA_DENAH]) == 2
    assert sum(len(v) for v in grup.values()) == len(aset)


def test_node_yang_tak_punya_leluhur_di_level_itu_masuk_TANPA_DENAH():
    """Tingkat boleh dilompati — satker yang tak memakai Gedung tetap punya
    Ruangan, dan asetnya tak boleh lenyap saat dikelompokkan per Gedung."""
    peta = {"r9": {"level_nama": {"RUANGAN": "Ruang Serbaguna"}}}
    grup = dict(ljj.kelompokkan_denah(_aset_di("r9", 5), "GEDUNG", peta))
    assert len(grup[ljj.TANPA_DENAH]) == 5
    ruang = dict(ljj.kelompokkan_denah(_aset_di("r9", 5), "RUANGAN", peta))
    assert len(ruang["Ruang Serbaguna"]) == 5


def test_TANPA_DENAH_juga_di_akhir():
    aset = _aset_di("r1", 1) + [{} for _ in range(40)]
    grup = ljj.kelompokkan_denah(aset, "GEDUNG", _PETA)
    assert grup[-1][0] == ljj.TANPA_DENAH, [g[0] for g in grup]
