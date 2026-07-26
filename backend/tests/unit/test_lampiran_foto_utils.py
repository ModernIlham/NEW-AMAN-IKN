"""Uji penyusun grid LAMPIRAN FOTO BUKTI SERAH TERIMA BARANG."""
from lampiran_foto_utils import (
    SEL_PER_HALAMAN, bagi_baris, ringkas_lampiran, susun_sel_lampiran,
)


def _aset(n):
    return [{"id": f"a{i}", "asset_code": f"306010212{i}", "NUP": str(i),
             "asset_name": f"Barang {i}"} for i in range(1, n + 1)]


def test_pasangan_sampul_dan_serah_berdampingan():
    """Tiap aset ber-foto serah terima → 2 sel berdampingan (1 baris grid)."""
    sel = susun_sel_lampiran(_aset(3), {"a1": "f1", "a2": "f2", "a3": "f3"})
    assert [s["jenis"] for s in sel] == [
        "sampul", "serah", "sampul", "serah", "sampul", "serah"]
    # 3 aset × 2 foto = 6 sel = TEPAT satu halaman
    assert len(sel) == SEL_PER_HALAMAN
    assert ringkas_lampiran(sel)["perkiraan_halaman"] == 1
    baris = bagi_baris(sel)
    assert len(baris) == 3
    # pasangan tak terpisah antar baris
    for b in baris:
        assert b[0]["asset_id"] == b[1]["asset_id"]


def test_tanpa_foto_serah_terima_halaman_memuat_lebih_banyak_aset():
    """Kolom yang seharusnya diisi foto serah terima TIDAK dibiarkan kosong —
    aset berikutnya maju, sehingga 1 halaman memuat 6 aset (bukan 3)."""
    sel = susun_sel_lampiran(_aset(6), {})
    assert all(s["jenis"] == "sampul" for s in sel)
    assert len(sel) == SEL_PER_HALAMAN          # 6 aset masuk 1 halaman
    assert ringkas_lampiran(sel)["perkiraan_halaman"] == 1
    r = ringkas_lampiran(sel)
    assert r["aset"] == 6 and r["foto_serah_terima"] == 0


def test_satu_foto_perwakilan_dicetak_sekali_di_akhir():
    """Satu foto mewakili SEMUA barang → jangan diulang tiap aset."""
    sel = susun_sel_lampiran(_aset(4), {}, foto_st_bersama=True)
    assert [s["jenis"] for s in sel] == ["sampul"] * 4 + ["serah_bersama"]
    assert sel[-1]["asset_id"] == ""
    assert "seluruh barang" in sel[-1]["judul"]
    r = ringkas_lampiran(sel)
    assert r["ada_foto_bersama"] is True and r["foto_serah_terima"] == 0


def test_campuran_sebagian_aset_punya_foto_sendiri():
    """Kasus nyata: hanya sebagian barang difoto saat serah terima."""
    sel = susun_sel_lampiran(_aset(4), {"a2": "f2"})
    assert [(s["jenis"], s["asset_id"]) for s in sel] == [
        ("sampul", "a1"),
        ("sampul", "a2"), ("serah", "a2"),
        ("sampul", "a3"),
        ("sampul", "a4"),
    ]
    assert ringkas_lampiran(sel)["foto_serah_terima"] == 1


def test_foto_per_aset_menang_atas_foto_bersama():
    """Bila aset punya fotonya SENDIRI, itu yang dipakai; foto perwakilan
    tetap dicetak sekali di akhir untuk barang yang tak punya."""
    sel = susun_sel_lampiran(_aset(2), {"a1": "khusus"}, foto_st_bersama=True)
    serah = [s for s in sel if s["jenis"] == "serah"]
    assert len(serah) == 1 and serah[0]["kunci"] == "khusus"
    assert sel[-1]["jenis"] == "serah_bersama"


def test_baris_terakhir_dipadatkan_agar_tabel_persegi():
    sel = susun_sel_lampiran(_aset(3), {})
    baris = bagi_baris(sel)
    assert len(baris) == 2
    assert baris[-1][1] is None          # sel kosong, dirender tanpa bingkai


def test_tanpa_aset_sama_sekali():
    sel = susun_sel_lampiran([], {})
    assert sel == []
    assert ringkas_lampiran(sel)["perkiraan_halaman"] == 0


def test_judul_aman_saat_field_kosong():
    sel = susun_sel_lampiran([{"id": "x"}], {})
    assert sel[0]["judul"] == "(tanpa kode)"


def test_lebih_dari_satu_halaman():
    """8 aset berpasangan penuh = 16 sel → 3 halaman."""
    peta = {f"a{i}": f"f{i}" for i in range(1, 9)}
    sel = susun_sel_lampiran(_aset(8), peta)
    assert len(sel) == 16
    assert ringkas_lampiran(sel)["perkiraan_halaman"] == 3
