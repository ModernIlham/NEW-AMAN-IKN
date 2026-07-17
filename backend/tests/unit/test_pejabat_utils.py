"""Uji referensi pejabat penatausahaan BMN (#290, PMK 181/2016)."""
from pejabat_utils import (
    PERAN_PEJABAT, PERAN_PEJABAT_META, STATUS_KEPEGAWAIAN, UNIT_AKUNTANSI,
    peran_penyerah_bast, pejabat_aktif_untuk_peran, penandatangan_kpb,
    validate_pejabat,
)


def test_referensi_memuat_peran_dan_unit_inti():
    assert "kuasa_pengguna_barang" in PERAN_PEJABAT
    assert "penatausahaan_bmn" in PERAN_PEJABAT
    # Jenjang unit akuntansi PMK 181/2016 lengkap
    for k in ("uapb", "uappb_e1", "uappb_w", "uakpb", "uapkpb"):
        assert k in UNIT_AKUNTANSI and UNIT_AKUNTANSI[k]["penanggung_jawab"]


def test_metadata_peran_lengkap_dan_konsisten():
    # Tiap peran punya metadata (domain + ttd_bast + keterangan)
    for kode in PERAN_PEJABAT:
        m = PERAN_PEJABAT_META.get(kode)
        assert m, f"metadata peran '{kode}' hilang"
        assert m["domain"] in ("bmn", "bmd")
        assert m["ttd_bast"] in ("penyerah", "penerima", "mengetahui", "tidak")
        assert str(m.get("keterangan") or "").strip()
    # 'pengurus_barang' ditandai rezim DAERAH (bukan BMN pusat)
    assert PERAN_PEJABAT_META["pengurus_barang"]["domain"] == "bmd"
    # Peran BMN pusat baru tersedia sebagai pengganti yang benar
    assert "pengelola_bmn_satker" in PERAN_PEJABAT
    assert PERAN_PEJABAT_META["pengelola_bmn_satker"]["domain"] == "bmn"


def test_peran_penyerah_bast_hanya_pengelola_bmn():
    penyerah = peran_penyerah_bast()
    # KPB, Petugas Penatausahaan, & Pengelola BMN Satker layak jadi penyerah
    for k in ("kuasa_pengguna_barang", "penatausahaan_bmn", "pengelola_bmn_satker"):
        assert k in penyerah
    # PPK (BAST perolehan) & Penanggung Jawab Ruangan (penerima) bukan penyerah;
    # 'pengurus_barang' (rezim daerah) juga tidak boleh muncul
    for k in ("ppk", "penanggung_jawab_ruangan", "pengurus_barang",
              "pengguna_barang", "pemeriksa_lpb"):
        assert k not in penyerah


def test_status_kepegawaian_mencakup_klasifikasi_inti():
    # Adopsi klasifikasi kepegawaian (SIMAN-G/BKN)
    for k in ("pns", "cpns", "pppk", "tni", "polri", "non_asn"):
        assert k in STATUS_KEPEGAWAIAN and STATUS_KEPEGAWAIAN[k]


def test_validate_pejabat():
    ok = {"nama": "Budi", "peran": ["kuasa_pengguna_barang"], "unit_akuntansi": "uakpb"}
    assert validate_pejabat(ok) == []
    # nama wajib
    assert any("Nama" in e for e in validate_pejabat({"peran": ["ppk"]}))
    # peran wajib & harus dikenal
    assert any("peran" in e.lower() for e in validate_pejabat({"nama": "A", "peran": []}))
    assert any("tidak dikenal" in e for e in
               validate_pejabat({"nama": "A", "peran": ["operator_ajaib"]}))
    # unit akuntansi tak dikenal
    assert any("Unit akuntansi" in e for e in
               validate_pejabat({"nama": "A", "peran": ["ppk"], "unit_akuntansi": "xxx"}))
    # rentang tanggal terbalik
    assert any("berlaku" in e for e in validate_pejabat(
        {"nama": "A", "peran": ["ppk"],
         "berlaku_mulai": "2026-12-31", "berlaku_selesai": "2026-01-01"}))


def test_validate_pejabat_field_baru():
    # status kepegawaian valid & tak dikenal
    assert validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "status_kepegawaian": "pppk"}) == []
    assert any("Status kepegawaian" in e for e in validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "status_kepegawaian": "honorer"}))
    # email valid & tidak valid; kosong tidak error
    assert validate_pejabat(
        {"nama": "A", "peran": ["ppk"], "email": "budi@kemenkeu.go.id"}) == []
    assert validate_pejabat({"nama": "A", "peran": ["ppk"], "email": ""}) == []
    for bad in ("budi", "budi@", "budi@x", "a b@c.id"):
        assert any("email" in e.lower() for e in validate_pejabat(
            {"nama": "A", "peran": ["ppk"], "email": bad}))


def _pj(nama, peran, mulai="", selesai="", aktif=True):
    return {"nama": nama, "peran": peran, "berlaku_mulai": mulai,
            "berlaku_selesai": selesai, "aktif": aktif}


def test_pejabat_aktif_untuk_peran():
    daftar = [
        _pj("KPB Lama", ["kuasa_pengguna_barang"], "2023-01-01", "2025-06-30"),
        _pj("KPB Baru", ["kuasa_pengguna_barang"], "2025-07-01", ""),
        _pj("Operator", ["penatausahaan_bmn"], "2024-01-01", ""),
        _pj("Nonaktif", ["kuasa_pengguna_barang"], "2026-01-01", "", aktif=False),
    ]
    # Tanggal 2026 → KPB Baru (SK terbaru & masih berlaku); nonaktif diabaikan
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2026-07-16")
    assert pj and pj["nama"] == "KPB Baru"
    # Tanggal 2024 → KPB Lama (KPB Baru belum berlaku)
    pj = pejabat_aktif_untuk_peran(daftar, "kuasa_pengguna_barang", "2024-05-01")
    assert pj and pj["nama"] == "KPB Lama"
    # Peran lain
    assert pejabat_aktif_untuk_peran(daftar, "penatausahaan_bmn", "2026-07-16")["nama"] == "Operator"
    # Peran tanpa pejabat → None
    assert pejabat_aktif_untuk_peran(daftar, "ppk", "2026-07-16") is None
    # Rentang kosong = terbuka; input kosong aman
    assert pejabat_aktif_untuk_peran([], "ppk", None) is None


def test_penandatangan_kpb_registry_vs_fallback():
    settings = {"kasatker_nama": "Kasatker Lama", "kasatker_nip": "111",
                "kasatker_jabatan": "Kepala Kantor"}
    daftar = [_pj("KPB Aktif", ["kuasa_pengguna_barang"], "2025-07-01", "")]
    # Ada KPB aktif di registry → dipakai (bukan setelan)
    ttd = penandatangan_kpb(settings, daftar, "2026-07-16")
    assert ttd["nama"] == "KPB Aktif" and ttd["sumber"] == "registry"
    # Tak ada KPB berlaku pada tanggal → fallback ke setelan kasatker
    ttd = penandatangan_kpb(settings, daftar, "2024-01-01")
    assert ttd["nama"] == "Kasatker Lama" and ttd["nip"] == "111" and ttd["sumber"] == "setelan"
    # Registry kosong & setelan kosong → tetap aman ("-")
    ttd = penandatangan_kpb({}, [], "2026-07-16")
    assert ttd["nama"] == "-" and ttd["jabatan"] == "Kuasa Pengguna Barang"
