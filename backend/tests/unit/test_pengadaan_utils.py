"""Uji logika murni register perolehan pengadaan (Perpres 16/2018 jo. 46/2025)."""
import pytest

from pengadaan_utils import (
    DOKUMEN_PEROLEHAN, JENIS_PEROLEHAN, LABEL_DOKUMEN_SUMBER,
    dokumen_kurang_perolehan, is_ekstrakomptabel, nilai_perolehan,
    rekap_perolehan, validate_perolehan,
)

HARI_INI = "2026-07-12"


def _p(**over):
    base = {"jenis": "pembelian", "pihak": "CV Sumber Rejeki",
            "nomor_kontrak": "SPK-1/2026", "nomor_bast": "BAST-1/2026",
            "tanggal_bast": "2026-07-01",
            "dokumen": {"kontrak": True, "bast": True},
            "barang": [{"uraian": "PC Unit", "kode": "3100102001",
                        "jumlah": 2, "harga_satuan": 8_000_000,
                        "asset_id": "a1"}]}
    base.update(over)
    return base


def test_validasi_perolehan():
    assert validate_perolehan(_p(), HARI_INI) == []
    assert any("Jenis" in e for e in validate_perolehan(_p(jenis="beli"), HARI_INI))
    assert any("pemberi" in e for e in validate_perolehan(_p(pihak=" "), HARI_INI))
    assert any("Nomor BAST" in e
               for e in validate_perolehan(_p(nomor_bast=""), HARI_INI))
    assert any("masa depan" in e
               for e in validate_perolehan(_p(tanggal_bast="2027-01-01"), HARI_INI))
    assert any("minimal satu" in e
               for e in validate_perolehan(_p(barang=[]), HARI_INI))
    rusak = _p(barang=[{"uraian": " ", "jumlah": 0, "harga_satuan": -1}])
    errs = validate_perolehan(rusak, HARI_INI)
    assert any("uraian" in e for e in errs)
    assert any("jumlah" in e for e in errs)
    assert any("harga satuan" in e for e in errs)


def test_checklist_dokumen_per_jenis():
    # Pembelian: kontrak+bast tercentang → sisa BAPHP, kuitansi, SP2D
    kurang = dokumen_kurang_perolehan(_p())
    assert kurang == ["BAPHP", "Kuitansi/Faktur", "SP2D"]
    # Hibah masuk: butuh naskah hibah + BAST + MPHL-BJS
    hibah = _p(jenis="hibah_masuk", dokumen={"bast": True})
    assert dokumen_kurang_perolehan(hibah) == ["Naskah Hibah", "MPHL-BJS"]
    # Transfer masuk hanya BAST → lengkap
    assert dokumen_kurang_perolehan(
        _p(jenis="transfer_masuk", dokumen={"bast": True})) == []
    # Registry konsisten: semua kunci checklist punya label
    for wajib in DOKUMEN_PEROLEHAN.values():
        assert set(wajib) <= set(LABEL_DOKUMEN_SUMBER)
    assert set(DOKUMEN_PEROLEHAN) == set(JENIS_PEROLEHAN)


def test_ekstrakomptabel_ambang_pmk181():
    # Peralatan-mesin (gol. 3): < Rp1 jt → ekstrakomptabel
    assert is_ekstrakomptabel({"kode": "3050104001", "harga_satuan": 900_000})
    assert not is_ekstrakomptabel({"kode": "3050104001", "harga_satuan": 1_000_000})
    # Gedung (gol. 4): ambang Rp25 jt
    assert is_ekstrakomptabel({"kode": "4010101001", "harga_satuan": 20_000_000})
    # Tanpa kode / golongan tanpa ambang → tidak dinilai
    assert not is_ekstrakomptabel({"kode": "", "harga_satuan": 1})
    assert not is_ekstrakomptabel({"kode": "2010101001", "harga_satuan": 1})


def test_nilai_dan_rekap():
    items = [
        _p(),  # 2 × 8jt = 16jt, 1 barang tertaut
        _p(jenis="hibah_masuk", dokumen={"naskah_hibah": True, "bast": True,
                                         "mphl_bjs": True},
           barang=[{"uraian": "Printer", "kode": "3100102002", "jumlah": 1,
                    "harga_satuan": 750_000, "asset_id": ""}]),
    ]
    assert nilai_perolehan(items[0]) == pytest.approx(16_000_000)
    r = rekap_perolehan(items)
    assert r["jumlah"] == 2 and r["per_jenis"]["pembelian"] == 1
    assert r["nilai"] == pytest.approx(16_750_000)
    assert r["dokumen_lengkap"] == 1          # hanya hibah yang lengkap
    assert r["barang_total"] == 2 and r["belum_tertaut"] == 1
    assert r["ekstrakomptabel"] == 1          # printer 750rb < 1jt


def test_snapshot_penganggaran():
    from pengadaan_utils import snapshot_penganggaran
    kosong = snapshot_penganggaran(None)
    assert kosong == {"penganggaran_id": "", "penganggaran_uraian": "",
                      "penganggaran_nomor_dipa": "", "penganggaran_tahun": ""}
    assert snapshot_penganggaran({}) == kosong
    u = {"id": "u1", "uraian": " Genset 100kVA ", "nomor_dipa": "DIPA-1/2027",
         "tahun_anggaran": "2027", "status": "masuk_dipa"}
    snap = snapshot_penganggaran(u)
    assert snap["penganggaran_id"] == "u1"
    assert snap["penganggaran_uraian"] == "Genset 100kVA"
    assert snap["penganggaran_nomor_dipa"] == "DIPA-1/2027"
    assert snap["penganggaran_tahun"] == "2027"
    # Field asing (status) tidak ikut ke snapshot
    assert "status" not in snap


# ── Back-link dokumen sumber ke aset: build_asset_perolehan_projection (§5A gap #6, #258) ──
from pengadaan_utils import build_asset_perolehan_projection

NOW6 = "2026-07-13T18:30:00+00:00"


def _perolehan(**over):
    base = {"id": "prl-1", "jenis": "pembelian", "pihak": "PT Sumber Jaya",
            "nomor_bast": "BAST-7/2026", "tanggal_bast": "2026-03-15",
            "nomor_kontrak": "SPK-3/2026"}
    base.update(over)
    return base


def test_perolehan_projection_lengkap():
    proj = build_asset_perolehan_projection(_perolehan(), NOW6)
    assert proj["perolehan_id"] == "prl-1"
    p = proj["perolehan"]
    assert p["jenis"] == "pembelian" and p["pihak"] == "PT Sumber Jaya"
    assert p["nomor_bast"] == "BAST-7/2026" and p["tanggal_bast"] == "2026-03-15"
    assert p["nomor_kontrak"] == "SPK-3/2026"
    assert p["diproyeksikan_pada"] == NOW6
    # SENGAJA tak menyentuh field laporan / version
    assert "purchase_price" not in proj and "version" not in proj


def test_perolehan_projection_kosong_melepas_tautan():
    # None / dict kosong → back-link kosong (tautan dilepas)
    for x in (None, {}):
        proj = build_asset_perolehan_projection(x, NOW6)
        assert proj == {"perolehan_id": "", "perolehan": {}}


def test_perolehan_projection_tanggal_dipangkas_dan_strip():
    proj = build_asset_perolehan_projection(
        _perolehan(id=" prl-9 ", tanggal_bast="2026-03-15T00:00:00"), NOW6)
    assert proj["perolehan_id"] == "prl-9"                 # di-strip
    assert proj["perolehan"]["tanggal_bast"] == "2026-03-15"   # 10 char
