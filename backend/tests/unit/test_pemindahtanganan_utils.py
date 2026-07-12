"""Uji logika murni register pemindahtanganan (PMK 111/2016 jo. 165/2021)."""
import pytest

from pemindahtanganan_utils import (
    BENTUK_PEMINDAHTANGANAN, STATUS_USULAN_PT, TRANSISI_PT,
    peringatan_pt, rekap_pt, validate_transisi_pt, validate_usulan_pt,
)

HARI_INI = "2026-07-12"


def _u(**over):
    base = {"bentuk": "hibah", "pihak": "Pemerintah Desa Sukamaju",
            "asset_ids": ["a1"], "status": "diusulkan",
            "tanggal_persetujuan": ""}
    base.update(over)
    return base


def test_validasi_usulan():
    assert validate_usulan_pt(_u()) == []
    assert any("Bentuk" in e for e in validate_usulan_pt(_u(bentuk="lelang")))
    assert any("Pihak" in e for e in validate_usulan_pt(_u(pihak=" ")))
    assert any("satu aset" in e for e in validate_usulan_pt(_u(asset_ids=[])))


def test_transisi_dokumen_wajib_per_tahap():
    u = _u()
    # disetujui wajib nomor persetujuan
    assert any("persetujuan" in e for e in validate_transisi_pt(u, "disetujui", {}))
    assert validate_transisi_pt(u, "disetujui", {"nomor_persetujuan": "S-1/2026"}) == []
    # tidak boleh lompat ke dilaksanakan
    assert any("tidak sah" in e for e in validate_transisi_pt(u, "dilaksanakan", {}))
    # dilaksanakan: hibah butuh nomor dokumen; penjualan juga butuh NTPN
    u2 = _u(status="disetujui")
    assert any("Naskah Hibah" in e for e in validate_transisi_pt(u2, "dilaksanakan", {}))
    assert validate_transisi_pt(u2, "dilaksanakan", {"nomor_dokumen": "NH-1/2026"}) == []
    u3 = _u(bentuk="penjualan_lelang", status="disetujui")
    errs = validate_transisi_pt(u3, "dilaksanakan", {"nomor_dokumen": "RL-1/2026"})
    assert any("NTPN" in e for e in errs)
    assert validate_transisi_pt(
        u3, "dilaksanakan", {"nomor_dokumen": "RL-1/2026", "ntpn": "X1"}) == []
    # selesai wajib SK penghapusan; status final tak bisa mundur
    u4 = _u(status="dilaksanakan")
    assert any("SK Penghapusan" in e for e in validate_transisi_pt(u4, "selesai", {}))
    assert validate_transisi_pt(u4, "selesai", {"nomor_sk_penghapusan": "KEP-1"}) == []
    assert TRANSISI_PT["selesai"] == set() and TRANSISI_PT["ditolak"] == set()
    for dari, tujuan in TRANSISI_PT.items():
        assert dari in STATUS_USULAN_PT and tujuan <= set(STATUS_USULAN_PT)


def test_peringatan_tenggat_lelang():
    # Disetujui 6 bulan lalu tanpa pelaksanaan → lewat tenggat
    u = _u(bentuk="penjualan_lelang", status="disetujui",
           tanggal_persetujuan="2026-01-01")
    assert any("penilaian ulang" in w for w in peringatan_pt(u, HARI_INI))
    # Baru disetujui → tanpa peringatan
    u2 = _u(bentuk="penjualan_lelang", status="disetujui",
            tanggal_persetujuan="2026-07-01")
    assert peringatan_pt(u2, HARI_INI) == []
    # Mendekati tenggat (sisa ≤30 hari) → peringatan dini
    u3 = _u(bentuk="penjualan_lelang", status="disetujui",
            tanggal_persetujuan="2026-01-20")
    assert any("tinggal" in w for w in peringatan_pt(u3, HARI_INI))
    # Bentuk lain tidak kena tenggat lelang
    assert peringatan_pt(_u(status="disetujui",
                            tanggal_persetujuan="2025-01-01"), HARI_INI) == []


def test_rekap():
    items = [
        _u(aset=[{"harga": 1_000_000}, {"harga": "Rp500.000"}]),
        _u(bentuk="penjualan_lelang", status="selesai", aset=[{"harga": 250_000}]),
    ]
    r = rekap_pt(items)
    assert r["jumlah"] == 2 and r["jumlah_aset"] == 3
    assert r["per_status"]["diusulkan"] == 1 and r["per_status"]["selesai"] == 1
    assert r["per_bentuk"]["hibah"] == 1
    assert r["nilai"] == pytest.approx(1_750_000)
    assert set(BENTUK_PEMINDAHTANGANAN) == set(r["per_bentuk"])


def test_sarankan_jenjang():
    from pemindahtanganan_utils import (
        AMBANG_PERSETUJUAN_PT, JENJANG_PERSETUJUAN, sarankan_jenjang,
    )
    M = 1_000_000_000
    # Selain tanah/bangunan: tiga tingkat 10 M / 100 M
    assert sarankan_jenjang("penjualan_lelang", "selain_tanah_bangunan", 5 * M)["jenjang"] == "pengelola"
    assert sarankan_jenjang("penjualan_lelang", "selain_tanah_bangunan", 50 * M)["jenjang"] == "presiden"
    assert sarankan_jenjang("penjualan_lelang", "selain_tanah_bangunan", 150 * M)["jenjang"] == "dpr"
    # Batas persis: 10 M → pengelola (bukan presiden); 100 M → presiden (bukan dpr)
    assert sarankan_jenjang("hibah", "selain_tanah_bangunan", 10 * M)["jenjang"] == "pengelola"
    assert sarankan_jenjang("hibah", "selain_tanah_bangunan", 100 * M)["jenjang"] == "presiden"
    # Tanah/bangunan umum → DPR tanpa batas
    assert sarankan_jenjang("tukar_menukar", "tanah_bangunan", 1 * M)["jenjang"] == "dpr"
    # Tanah/bangunan terkecuali → ikut nilai (Presiden bila > 10 M)
    assert sarankan_jenjang("tukar_menukar", "tanah_bangunan", 5 * M, tb_terkecuali=True)["jenjang"] == "pengelola"
    assert sarankan_jenjang("tukar_menukar", "tanah_bangunan", 20 * M, tb_terkecuali=True)["jenjang"] == "presiden"
    # PMPP: naikkan floor ke Presiden bila hasil pengelola
    pmpp = sarankan_jenjang("pmpp", "selain_tanah_bangunan", 5 * M)
    assert pmpp["jenjang"] == "presiden" and any("PMPP" in c for c in pmpp["catatan"])
    # Hibah low-value: catatan Pengguna Barang, tetap jenjang pengelola
    hibah = sarankan_jenjang("hibah", "selain_tanah_bangunan", 50_000_000)
    assert hibah["jenjang"] == "pengelola" and any("Pengguna Barang" in c for c in hibah["catatan"])
    # Keluaran punya label + disclaimer
    s = sarankan_jenjang("penjualan_lelang", "selain_tanah_bangunan", 5 * M)
    assert s["jenjang_label"] == JENJANG_PERSETUJUAN["pengelola"]
    assert "Indikatif" in s["disclaimer"]
    # Referensi konsisten
    assert all(r["jenjang"] in JENJANG_PERSETUJUAN for r in AMBANG_PERSETUJUAN_PT)
