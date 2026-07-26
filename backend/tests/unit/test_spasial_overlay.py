"""Uji helper overlay gambar denah (Fase 7) — validasi sudut, penempatan
bawaan, dan pemeriksaan gambar (termasuk bom dekompresi yang ditolak dari
METADATA, tanpa pernah mendekode piksel)."""
import io
import struct

import pytest

import spasial_utils as su

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402


def _png(lebar=10, tinggi=10) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (lebar, tinggi), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _png_header_palsu(lebar: int, tinggi: int) -> bytes:
    """PNG sungguhan 10×10 yang IHDR-nya DITULIS ULANG mengaku berdimensi
    raksasa — persis serangan bom dekompresi: file kecil, klaim piksel besar.
    Layout PNG: tanda 8B, panjang 4B, 'IHDR' 4B, data 13B (lebar+tinggi BE di
    offset 16..24), CRC 4B di offset 29. CRC DIHITUNG ULANG — PIL memverifikasi
    CRC IHDR saat open, dan bom sungguhan tentu berheader sah."""
    import zlib
    data = bytearray(_png())
    data[16:24] = struct.pack(">II", lebar, tinggi)
    data[29:33] = struct.pack(">I", zlib.crc32(bytes(data[12:29])) & 0xFFFFFFFF)
    return bytes(data)


# ── validasi_sudut_overlay ──────────────────────────────────────────────────

SUDUT_SAH = {"tl": [116.70, -1.39], "tr": [116.71, -1.39], "bl": [116.70, -1.40]}


def test_sudut_sah_lolos():
    assert su.validasi_sudut_overlay(SUDUT_SAH) is None


def test_sudut_bukan_dict_atau_kurang_kunci():
    assert su.validasi_sudut_overlay(None)
    assert su.validasi_sudut_overlay({"tl": [1, 1], "tr": [2, 2]})


def test_sudut_di_luar_dunia():
    s = dict(SUDUT_SAH, tr=[999, -1.39])
    assert "rentang" in su.validasi_sudut_overlay(s)


def test_sudut_bertumpuk_ditolak():
    s = {"tl": [116.70, -1.39], "tr": [116.70, -1.39], "bl": [116.70, -1.39]}
    assert "bertumpuk" in su.validasi_sudut_overlay(s)


def test_bentang_provinsi_ditolak():
    s = dict(SUDUT_SAH, tr=[117.9, -1.39])
    assert "bentang" in su.validasi_sudut_overlay(s)


def test_rapikan_sudut_buang_elevasi_dan_string():
    s = {"tl": ["116.70", "-1.39", 99], "tr": [116.71, -1.39], "bl": [116.70, -1.40]}
    r = su.rapikan_sudut_overlay(s)
    assert r["tl"] == [116.70, -1.39]
    assert all(len(v) == 2 for v in r.values())


def test_opasitas_dijepit_bukan_ditolak():
    assert su.opasitas_overlay_sah(0.5) == 0.5
    assert su.opasitas_overlay_sah(7) == 1.0
    assert su.opasitas_overlay_sah(-3) == 0.05
    assert su.opasitas_overlay_sah("x") == su.OPASITAS_OVERLAY_BAWAAN
    assert su.opasitas_overlay_sah(float("nan")) == su.OPASITAS_OVERLAY_BAWAAN


def test_sudut_bawaan_dari_bbox():
    s = su.sudut_overlay_bawaan([116.70, -1.40, 116.72, -1.38])
    assert s == {"tl": [116.70, -1.38], "tr": [116.72, -1.38],
                 "bl": [116.70, -1.40]}
    assert su.validasi_sudut_overlay(s) is None
    assert su.sudut_overlay_bawaan(None) is None
    assert su.sudut_overlay_bawaan([1, 2, 1, 2]) is None   # bbox degenerat


# ── periksa_gambar_overlay ──────────────────────────────────────────────────

def test_png_kecil_diterima():
    fmt, w, h = su.periksa_gambar_overlay(_png(32, 16))
    assert (fmt, w, h) == ("PNG", 32, 16)


def test_bukan_gambar_ditolak():
    with pytest.raises(ValueError, match="bukan gambar"):
        su.periksa_gambar_overlay(b"bukan gambar sama sekali")
    with pytest.raises(ValueError):
        su.periksa_gambar_overlay(b"")


def test_format_di_luar_daftar_ditolak():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="BMP")
    with pytest.raises(ValueError, match="tidak didukung"):
        su.periksa_gambar_overlay(buf.getvalue())


def test_bom_dekompresi_ditolak_dari_metadata():
    """File 200-an byte mengaku 48 MP (di bawah ambang peringatan PIL 89 MP,
    jadi lolos pagar PIL sendiri) — plafon kita yang harus menangkapnya."""
    with pytest.raises(ValueError, match="terlalu besar"):
        su.periksa_gambar_overlay(_png_header_palsu(8000, 6000))


def test_bom_raksasa_juga_ditolak():
    """Klaim 10 GP memicu DecompressionBombError PIL saat open — jalur mana
    pun yang menang, hasilnya harus ValueError, bukan gambar diterima."""
    with pytest.raises(ValueError):
        su.periksa_gambar_overlay(_png_header_palsu(100_000, 100_000))


# ── Semantik "None = tak diubah" pada _bersih_node (temuan Fase 7) ──────────
# Dua bug data-loss senyap dari default lama: klien yang tak mengirim
# `properties` MENGHAPUS jejak impor + overlay; klien yang tak mengirim
# `status` MENGAKTIFKAN draft diam-diam (form pohon memang tak mengirim
# keduanya). Kini None diteruskan sebagai penanda, pemanggil yang memutuskan.

def test_bersih_node_none_jadi_penanda_tak_diubah():
    from routes.spasial import NodeIn, _bersih_node
    doc = _bersih_node(NodeIn(tipe="GEDUNG", nama="X"))
    assert doc["properties"] is None
    assert doc["status"] is None


def test_bersih_node_nilai_eksplisit_tetap():
    from routes.spasial import NodeIn, _bersih_node
    doc = _bersih_node(NodeIn(tipe="GEDUNG", nama="X",
                              status="draft", properties={"a": 1}))
    assert doc["status"] == "draft"
    assert doc["properties"] == {"a": 1}


def test_bersih_node_status_liar_jadi_none_bukan_aktif():
    """'dihapus' (dan status ngawur lain) TIDAK boleh diselundupkan klien;
    dulu jatuh ke 'aktif' — kini None sehingga update mempertahankan status
    tersimpan, bukan mengaktifkan."""
    from routes.spasial import NodeIn, _bersih_node
    assert _bersih_node(NodeIn(tipe="G", nama="X", status="dihapus"))["status"] is None
    assert _bersih_node(NodeIn(tipe="G", nama="X", status="ngawur"))["status"] is None


# ── Regresi temuan tinjauan Fase 7 ──────────────────────────────────────────

def test_desimal_koma_lolos_validasi_dan_rapikan_sepakat():
    """Format Excel/lapangan Indonesia "116,70" lolos validasi (parse_koordinat
    menormalkan koma) — dulu rapikan memakai float() mentah dan meledak jadi
    500 pada input yang justru diiklankan didukung (temuan tinjauan)."""
    s = {"tl": ["116,70", "-1,39"], "tr": ["116,71", "-1,39"],
         "bl": ["116,70", "-1,40"]}
    assert su.validasi_sudut_overlay(s) is None
    assert su.rapikan_sudut_overlay(s) == {
        "tl": [116.70, -1.39], "tr": [116.71, -1.39], "bl": [116.70, -1.40]}


def test_gambar_terpotong_ditolak_bukan_tersimpan_diam():
    """Header sah + piksel terpotong dulu LOLOS (hanya header dibaca) lalu
    gagal render diam-diam di peramban; verify() menyusuri chunk+CRC tanpa
    mendekode piksel dan menangkapnya (temuan tinjauan)."""
    utuh = _png(64, 64)
    with pytest.raises(ValueError, match="rusak/terpotong"):
        su.periksa_gambar_overlay(utuh[:-30])


def test_sudut_bawaan_bbox_raksasa_tetap_sah():
    """bbox kawasan selebar provinsi dijepit — penempatan awal tak boleh
    berupa keadaan yang validator API-nya sendiri tolak (temuan tinjauan)."""
    s = su.sudut_overlay_bawaan([110.0, -5.0, 118.0, 1.0])
    assert s is not None
    assert su.validasi_sudut_overlay(s) is None
    assert su.sudut_overlay_bawaan([116.0, -1.0, float("inf"), 1.0]) is None
